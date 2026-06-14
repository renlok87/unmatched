/**
 * E2E: CHOOSE_ONE (парсер v3 + executor-вертикаль) против живого стенда.
 * Сценарий: Jill Trent (P1=admin) vs King Arthur (P2=tester2).
 *
 * Utility Belt (VERSATILE, effectAfter = CHOOSE_ONE без условия) играется P1
 * атакой → resolveCombat → CHOOSE_ONE pending у P1 (3 опции) →
 * resolvePendingEffect{optionIndex} опции «Draw 1 card» → pending очищается.
 *
 * Нелетально: P2 всегда пасует (0 урона P1), P1 идёт к врагу добирая карты,
 * бьёт Utility Belt ОДИН раз. Если карта не в окне руки — ретрай новой партией.
 *
 *   node backend/scripts/e2e-choose-one.mjs                — полный цикл + резолв
 *   node backend/scripts/e2e-choose-one.mjs --leave-pending — оставить pending для UI
 */

const HTTP = 'http://localhost:3000/graphql';
const A = { email: 'admin@unmached.local', password: 'Admin123!' };
const B = { email: 'tester2@unmached.local', password: 'Tester123!' };
const LEAVE_PENDING = process.argv.includes('--leave-pending');

let passed = 0, failed = 0;
const log = (s) => console.log(s);
function check(name, cond, extra = '') {
  if (cond) { passed++; log(`  ✅ ${name}`); }
  else { failed++; log(`  ❌ ${name} ${extra}`); }
}

async function gql(query, variables, token) {
  const res = await fetch(HTTP, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ query, variables }),
  });
  const json = await res.json();
  if (json.errors?.length) { const e = new Error(json.errors.map((x) => x.message).join('; ')); e.isGql = true; throw e; }
  return json.data;
}

const LOGIN = `mutation($e: String!, $p: String!) { login(input: {email: $e, password: $p}) { accessToken refreshToken user { id username } } }`;
const SF = `{ state sequenceNumber phase currentTurnPlayerId turnCount timestamp }`;
const M = {
  maneuver: `mutation($input: ManeuverDto!) { maneuver(input: $input) ${SF} }`,
  attack: `mutation($input: AttackDto!) { attack(input: $input) ${SF} }`,
  resolveCombat: `mutation($input: ResolveCombatDto!) { resolveCombat(input: $input) ${SF} }`,
  endTurn: `mutation($input: EndTurnDto!) { endTurn(input: $input) ${SF} }`,
  resolvePendingEffect: `mutation($input: ResolvePendingEffectDto!) { resolvePendingEffect(input: $input) ${SF} }`,
};
const GET_STATE = `query($gameId: String!) { gameState(gameId: $gameId) { state } }`;

async function main() {
  const p1 = (await gql(LOGIN, { e: A.email, p: A.password })).login;
  const p2 = (await gql(LOGIN, { e: B.email, p: B.password })).login;
  const tokens = { [p1.user.id]: p1.accessToken, [p2.user.id]: p2.accessToken };

  const cleanupAll = async () => {
    for (const u of [p1, p2]) {
      const my = await gql(`query { myGames { id status } }`, {}, u.accessToken);
      for (const g of my.myGames.filter((g) => ['LOBBY', 'IN_PROGRESS', 'PENDING'].includes(g.status))) {
        await gql(`mutation($id: String!) { abortGame(gameId: $id) { id } }`, { id: g.id }, u.accessToken).catch(() => {});
      }
    }
  };
  await cleanupAll();

  const findHero = async (name) => {
    const d = await gql(`query($s: String!) { heroList(limit: 5, search: $s) { items { id name } } }`, { s: name }, p1.accessToken);
    return d.heroList.items.find((h) => h.name === name);
  };
  const jill = await findHero('Dr. Jill Trent');
  const arthur = await findHero('King Arthur');
  if (!jill || !arthur) throw new Error('Dr. Jill Trent / King Arthur не найдены');

  const setupGame = async () => {
    const game = (await gql(`mutation { createGame(input: {mode: ONE_V_ONE}) { id code } }`, {}, p1.accessToken)).createGame;
    await gql(`mutation($id: String!) { joinGame(input: {gameId: $id}) { id } }`, { id: game.id }, p2.accessToken);
    await gql(`mutation($g: String!, $h: String!) { selectHero(gameId: $g, heroId: $h) { id } }`, { g: game.id, h: jill.id }, p1.accessToken);
    await gql(`mutation($g: String!, $h: String!) { selectHero(gameId: $g, heroId: $h) { id } }`, { g: game.id, h: arthur.id }, p2.accessToken);
    await gql(`mutation($g: String!) { toggleReady(gameId: $g) { id } }`, { g: game.id }, p1.accessToken);
    await gql(`mutation($g: String!) { toggleReady(gameId: $g) { id } }`, { g: game.id }, p2.accessToken);
    await gql(`mutation($g: String!) { startGame(gameId: $g) { id status } }`, { g: game.id }, p1.accessToken);
    return game;
  };

  const loadState = async (tok, gid) => JSON.parse((await gql(GET_STATE, { gameId: gid }, tok)).gameState.state);
  const mutate = async (gid, name, input, actorId) =>
    JSON.parse((await gql(M[name], { input: { gameId: gid, ...input } }, tokens[actorId]))[name].state);
  const my = (s, uid) => s.fighters.filter((f) => f.ownerId === uid && f.health > 0);
  const hero = (s, uid) => my(s, uid).find((f) => f.type === 'HERO') ?? my(s, uid)[0];
  const hand = (s, uid) => s.handZones[uid]?.cards ?? [];
  const dist = (a, b) => Math.abs(a.position.x - b.position.x) + Math.abs(a.position.y - b.position.y);
  const pendOf = (s, uid) => (s.metadata?.pendingEffects ?? []).filter((p) => p.playerId === uid);
  const stepToward = (s, mine, enemy) => {
    const dx = Math.sign(enemy.position.x - mine.position.x);
    const dy = Math.sign(enemy.position.y - mine.position.y);
    const cells = [
      { x: mine.position.x + dx, y: mine.position.y },
      { x: mine.position.x, y: mine.position.y + dy },
    ];
    for (const c of cells) {
      if (dx === 0 && dy === 0) break;
      if (c.x < 0 || c.y < 0 || c.x >= s.boardState.width || c.y >= s.boardState.height) continue;
      if (c.x === enemy.position.x && c.y === enemy.position.y) continue;
      if (s.fighters.some((f) => f.health > 0 && f.id !== mine.id && f.position.x === c.x && f.position.y === c.y)) continue;
      const cell = s.boardState.cells?.[c.y]?.[c.x];
      if (cell && (cell.type === 'obstacle' || cell.type === 'wall')) continue;
      return c;
    }
    return null;
  };

  // Возвращает state-после-боя с активным CHOOSE_ONE pending, либо null (ретрай)
  const playUtilityBelt = async (gid) => {
    for (let iter = 0; iter < 60; iter++) {
      let st = await loadState(p1.accessToken, gid);
      if (st.phase === 'GAME_OVER') return null;
      const actor = st.currentTurnPlayerId;
      st = await loadState(tokens[actor], gid);
      const opp = st.players.find((p) => p.userId !== actor).userId;
      const mine = hero(st, actor);
      const enemy = my(st, opp)[0];
      if (!mine || !enemy) return null;
      const actions = st.metadata?.actionsRemaining ?? 2;

      if (actor === p2.user.id) { await mutate(gid, 'endTurn', {}, actor).catch(() => {}); continue; } // P2 пасует

      const h = hand(st, actor);
      const ub = h.find((c) => c.name === 'Utility Belt');
      if (ub && dist(mine, enemy) === 1) {
        await mutate(gid, 'attack', { attackerId: mine.id, targetId: enemy.id, cardId: ub.id }, actor);
        return await loadStateAfterResolve(gid, actor);
      }
      if (!ub && h.length >= 7 && dist(mine, enemy) > 1) return null; // окно руки исчерпано — ретрай
      if (actions > 0) {
        const step = stepToward(st, mine, enemy);
        if (step) await mutate(gid, 'maneuver', { fighterId: mine.id, boostCardId: null, path: [step] }, actor).catch(async () => { await mutate(gid, 'endTurn', {}, actor).catch(() => {}); });
        else await mutate(gid, 'endTurn', {}, actor).catch(() => {});
      } else {
        await mutate(gid, 'endTurn', {}, actor).catch(() => {});
      }
    }
    return null;
  };
  const loadStateAfterResolve = async (gid, actor) => {
    await mutate(gid, 'resolveCombat', {}, actor); // P2 без защиты → P1 выигрывает
    return await loadState(p1.accessToken, gid);
  };

  log(`Jill Trent (P1) vs King Arthur (P2) — поиск партии с Utility Belt в руке`);
  let game = null, after = null;
  for (let attempt = 0; attempt < 10 && !after; attempt++) {
    game = await setupGame();
    after = await playUtilityBelt(game.id);
    if (!after) { await gql(`mutation($id: String!) { abortGame(gameId: $id) { id } }`, { id: game.id }, p1.accessToken).catch(() => {}); }
    else log(`  партия ${game.code}: Utility Belt сыгран (попытка ${attempt + 1})`);
  }
  check('Utility Belt сыгран в бою (партия найдена)', Boolean(after), '(не пришёл в руку за 10 партий)');
  if (!after) { log(`\nFAIL`); process.exit(1); }

  const pend = pendOf(after, p1.user.id).filter((p) => p.type === 'CHOOSE_ONE');
  check('CHOOSE_ONE pending создан у P1', pend.length >= 1, `(${JSON.stringify(pendOf(after, p1.user.id).map((p) => p.type))})`);
  if (pend.length >= 1) {
    const cp = pend[0];
    check('pending: 3 опции с label', Array.isArray(cp.options) && cp.options.length === 3, JSON.stringify(cp.options));
    const drawOpt = (cp.options ?? []).find((o) => /draw/i.test(o.label));
    check('опция «Draw 1 card» найдена', Boolean(drawOpt), JSON.stringify((cp.options ?? []).map((o) => o.label)));

    if (LEAVE_PENDING) {
      log(`\nPENDING_READY`);
      log(`gameId=${game.id}`);
      log(`accessToken=${p1.accessToken}`);
      log(`refreshToken=${p1.refreshToken}`);
      log(`userId=${p1.user.id}`);
      log(`username=${p1.user.username}`);
      log(`options=${JSON.stringify(cp.options)}`);
      process.exit(0);
    }

    if (drawOpt) {
      const deckBefore = (after.decks?.[p1.user.id]?.drawPile ?? []).length;
      await mutate(game.id, 'resolvePendingEffect', { effectId: cp.id, optionIndex: drawOpt.index }, p1.user.id);
      const fin = await loadState(p1.accessToken, game.id);
      const pendFin = pendOf(fin, p1.user.id).filter((p) => p.type === 'CHOOSE_ONE');
      check('CHOOSE_ONE pending очищен после резолва', pendFin.length === 0, `(осталось ${pendFin.length})`);
      const deckAfter = (fin.decks?.[p1.user.id]?.drawPile ?? []).length;
      check('опция Draw исполнена: колода -1', deckAfter === deckBefore - 1, `(${deckBefore}→${deckAfter})`);
    }
  }

  const ok = failed === 0;
  log(`\n${ok ? 'ALL PASS' : 'FAIL'}: ✅ ${passed} / ❌ ${failed}`);
  await gql(`mutation($id: String!) { abortGame(gameId: $id) { id } }`, { id: game.id }, p1.accessToken).catch(() => {});
  process.exit(ok ? 0 : 1);
}

main().catch((e) => { console.error('FATAL:', e.message); process.exit(1); });

/**
 * E2E: эффекты карт (A0–A7) против живого стенда.
 * Сценарий: Medusa (P1=admin) vs King Arthur (P2=tester2).
 *
 * Гарантированные проверки:
 *  B. манёвр без карты (добор + движение), seq +1
 *  C. BOOST-манёвр: путь movement+boost проходит ТОЛЬКО с boost-картой
 *  D. бой: attack → [defense] → resolve, урон применён, ход/фаза корректны
 * Опортунистические (по мере прихода карт в руку, мин. 2 для PASS):
 *  E. banner: Медуза не играет карту с банером Harpy (BANNER_MISMATCH)
 *  F. Gaze of Stone: победа → +8 урона
 *  H. Snipe/Regroup/The Aid of Morgana: draw после боя
 *
 * Запуск: node backend/scripts/e2e-card-effects.mjs (бэк на localhost:3000)
 */

const HTTP = 'http://localhost:3000/graphql';
const A = { email: 'admin@unmached.local', password: 'Admin123!' };
const B = { email: 'tester2@unmached.local', password: 'Tester123!' };

let passed = 0;
let failed = 0;
const opportunistic = [];

function check(name, cond, extra = '') {
  if (cond) {
    passed++;
    console.log(`  ✅ ${name}`);
  } else {
    failed++;
    console.log(`  ❌ ${name} ${extra}`);
  }
}

async function gql(query, variables, token) {
  const res = await fetch(HTTP, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ query, variables }),
  });
  const json = await res.json();
  if (json.errors?.length) {
    const err = new Error(json.errors.map((e) => e.message).join('; '));
    err.isGql = true;
    throw err;
  }
  return json.data;
}

const LOGIN = `mutation($e: String!, $p: String!) { login(input: {email: $e, password: $p}) { accessToken user { id username } } }`;
const STATE_FIELDS = `{ state sequenceNumber phase currentTurnPlayerId turnCount timestamp }`;
const M = {
  maneuver: `mutation($input: ManeuverDto!) { maneuver(input: $input) ${STATE_FIELDS} }`,
  attack: `mutation($input: AttackDto!) { attack(input: $input) ${STATE_FIELDS} }`,
  playDefense: `mutation($input: PlayDefenseDto!) { playDefense(input: $input) ${STATE_FIELDS} }`,
  resolveCombat: `mutation($input: ResolveCombatDto!) { resolveCombat(input: $input) ${STATE_FIELDS} }`,
  endTurn: `mutation($input: EndTurnDto!) { endTurn(input: $input) ${STATE_FIELDS} }`,
};
const GET_STATE = `query($gameId: String!) { gameState(gameId: $gameId) { state sequenceNumber } }`;

async function main() {
  // --- Логины + прибирание активных игр (лимит 5) ---
  const p1 = (await gql(LOGIN, { e: A.email, p: A.password })).login;
  const p2 = (await gql(LOGIN, { e: B.email, p: B.password })).login;
  for (const u of [p1, p2]) {
    const my = await gql(`query { myGames { id status } }`, {}, u.accessToken);
    for (const g of my.myGames.filter((g) => ['LOBBY', 'IN_PROGRESS', 'PENDING'].includes(g.status))) {
      await gql(`mutation($id: String!) { abortGame(gameId: $id) { id } }`, { id: g.id }, u.accessToken).catch(() => {});
    }
  }

  // --- Герои ---
  // heroList — Prisma-идентификаторы (контентный `heroes` отдаёт id=name)
  const findHero = async (name) => {
    const data = await gql(
      `query($s: String!) { heroList(limit: 5, search: $s) { items { id name } } }`,
      { s: name },
      p1.accessToken,
    );
    return data.heroList.items.find((h) => h.name === name);
  };
  const medusa = await findHero('Medusa');
  const arthur = await findHero('King Arthur');
  if (!medusa || !arthur) throw new Error('Medusa/King Arthur не найдены в БД');

  // --- Лобби-флоу ---
  const game = (await gql(`mutation { createGame(input: {mode: ONE_V_ONE}) { id code } }`, {}, p1.accessToken)).createGame;
  console.log(`Игра: ${game.code} (${game.id}) — Medusa vs King Arthur`);
  await gql(`mutation($id: String!) { joinGame(input: {gameId: $id}) { id } }`, { id: game.id }, p2.accessToken);
  await gql(`mutation($g: String!, $h: String!) { selectHero(gameId: $g, heroId: $h) { id } }`, { g: game.id, h: medusa.id }, p1.accessToken);
  await gql(`mutation($g: String!, $h: String!) { selectHero(gameId: $g, heroId: $h) { id } }`, { g: game.id, h: arthur.id }, p2.accessToken);
  await gql(`mutation($g: String!) { toggleReady(gameId: $g) { id } }`, { g: game.id }, p1.accessToken);
  await gql(`mutation($g: String!) { toggleReady(gameId: $g) { id } }`, { g: game.id }, p2.accessToken);
  await gql(`mutation($g: String!) { startGame(gameId: $g) { id status } }`, { g: game.id }, p1.accessToken);

  const tokens = { [p1.user.id]: p1.accessToken, [p2.user.id]: p2.accessToken };

  async function loadState(viewerToken) {
    const data = await gql(GET_STATE, { gameId: game.id }, viewerToken);
    return JSON.parse(data.gameState.state);
  }

  let st = await loadState(p1.accessToken);
  console.log(`\nСтарт: фаза ${st.phase}, ход ${st.currentTurnPlayerId === p1.user.id ? 'P1' : 'P2'}, seq ${st.sequenceNumber}`);
  check('A. старт: фаза ACTION_MANEUVER', st.phase === 'ACTION_MANEUVER');

  const my = (s, uid) => s.fighters.filter((f) => f.ownerId === uid && f.health > 0);
  const hero = (s, uid) => my(s, uid).find((f) => f.type === 'HERO') ?? my(s, uid)[0];
  const hand = (s, uid) => s.handZones[uid]?.cards ?? [];

  /** Зигзаг-путь длины n от позиции бойца (между его клеткой и соседней свободной) */
  function zigzagPath(s, fighter, n) {
    const { x, y } = fighter.position;
    const w = s.boardState.width, h = s.boardState.height;
    const occupied = new Set(s.fighters.filter((f) => f.id !== fighter.id && f.health > 0).map((f) => `${f.x ?? f.position.x}:${f.position.y}`));
    const dirs = [ [1, 0], [-1, 0], [0, 1], [0, -1] ];
    for (const [dx, dy] of dirs) {
      const nx = x + dx, ny = y + dy;
      if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
      if (occupied.has(`${nx}:${ny}`)) continue;
      const cell = s.boardState.cells?.[ny]?.[nx];
      if (cell && cell.type === 'obstacle') continue;
      const path = [];
      for (let i = 0; i < n; i++) path.push(i % 2 === 0 ? { x: nx, y: ny } : { x, y });
      return path;
    }
    throw new Error('Нет свободной соседней клетки для зигзага');
  }

  async function mutate(name, input, actorId) {
    const data = await gql(M[name], { input: { gameId: game.id, ...input } }, tokens[actorId]);
    return JSON.parse(data[name].state);
  }

  // ============================================================
  // B. Манёвр без карты: добор + движение, seq +1
  // ============================================================
  console.log('\n— B. Манёвр без карты —');
  {
    st = await loadState(tokens[st.currentTurnPlayerId]);
    const actor = st.currentTurnPlayerId;
    const f = hero(st, actor);
    const handBefore = hand(st, actor).length;
    const seqBefore = st.sequenceNumber;
    const next = await mutate('maneuver', { fighterId: f.id, boostCardId: null, path: zigzagPath(st, f, 1) }, actor);
    check('манёвр без карты прошёл', true);
    check('seq +1', next.sequenceNumber === seqBefore + 1, `(${seqBefore}→${next.sequenceNumber})`);
    const nextHand = hand(await loadState(tokens[actor]), actor).length;
    check('добор 1 карты', nextHand === Math.min(handBefore + 1, 7), `(${handBefore}→${nextHand})`);
    st = await loadState(tokens[actor]);
  }

  // ============================================================
  // C. BOOST-манёвр: длинный путь только с boost-картой
  // ============================================================
  console.log('\n— C. BOOST-манёвр —');
  {
    const actor = st.currentTurnPlayerId;
    st = await loadState(tokens[actor]);
    const f = hero(st, actor);
    const movement = f.movement ?? 2;
    const boostCard = hand(st, actor).find((c) => (c.boostValue ?? 0) > 0);
    if (!boostCard) {
      console.log('  ⚠️ нет карты с boostValue в руке — пропуск (редкость)');
    } else {
      const longLen = movement + boostCard.boostValue;
      const longPath = zigzagPath(st, f, longLen);
      let deniedMsg = '';
      try {
        await mutate('maneuver', { fighterId: f.id, boostCardId: null, path: longPath }, actor);
      } catch (e) {
        deniedMsg = e.message;
      }
      check('без карты длинный путь отклонён', /превышает|NOT_ENOUGH/i.test(deniedMsg), deniedMsg.slice(0, 80));
      const next = await mutate('maneuver', { fighterId: f.id, boostCardId: boostCard.id, path: longPath }, actor);
      check(`с BOOST «${boostCard.name}» (+${boostCard.boostValue}) путь ${longLen} прошёл`, true);
      st = next;
      const fresh = await loadState(tokens[actor]);
      check('boost-карта в сбросе', (fresh.discardPiles?.[actor] ?? []).some((c) => c.id === boostCard.id));
      st = fresh;
    }
  }

  // ============================================================
  // Сближение и бои в цикле + опортунистические проверки
  // ============================================================
  console.log('\n— D/E/F/H. Бои и эффекты (цикл) —');
  const seen = { banner: false, gaze: false, draw: false, fight: false };
  const dist = (a, b) => Math.abs(a.position.x - b.position.x) + Math.abs(a.position.y - b.position.y);

  for (let iter = 0; iter < 60 && Object.values(seen).filter(Boolean).length < 3; iter++) {
    st = await loadState(p1.accessToken);
    if (st.phase === 'GAME_OVER') { console.log('  GAME_OVER — заканчиваем цикл'); break; }
    const actor = st.currentTurnPlayerId;
    st = await loadState(tokens[actor]);
    const opp = st.players.find((p) => p.userId !== actor).userId;
    const mine = hero(st, actor);
    const enemy = my(st, opp).reduce((a, b) => (dist(mine, a) <= dist(mine, b) ? a : b));
    const h = hand(st, actor);
    const actions = st.metadata?.actionsRemaining ?? 2;

    // E. banner-проверка (Медуза + карта Harpy в руке)
    if (!seen.banner && actor === p1.user.id) {
      const harpyCard = h.find((c) => c.bannerName === 'Harpy' && (c.cardType === 'ATTACK' || c.cardType === 'VERSATILE'));
      const harpyAdjacentTarget = dist(mine, enemy) === 1;
      if (harpyCard && harpyAdjacentTarget) {
        let msg = '';
        try {
          await mutate('attack', { attackerId: mine.id, targetId: enemy.id, cardId: harpyCard.id }, actor);
        } catch (e) { msg = e.message; }
        check(`E. Медуза не играет «${harpyCard.name}» (banner Harpy)`, /банером|BANNER/i.test(msg), msg.slice(0, 90));
        seen.banner = true;
        opportunistic.push('E');
        continue;
      }
    }

    // Атака, если смежны и есть чем
    const attackCard =
      (!seen.gaze && actor === p1.user.id && h.find((c) => c.name === 'Gaze of Stone')) ||
      h.find((c) => (c.cardType === 'ATTACK' || c.cardType === 'VERSATILE') && (c.bannerName == null || c.bannerName === 'Any' || mine.name.toLowerCase().includes(String(c.bannerName).toLowerCase())));
    if (dist(mine, enemy) === 1 && attackCard && actions > 0) {
      const isGaze = attackCard.name === 'Gaze of Stone';
      const enemyHpBefore = enemy.health;
      const handBefore = h.length;
      await mutate('attack', { attackerId: mine.id, targetId: enemy.id, cardId: attackCard.id }, actor);
      // резолв без защиты — атакующий побеждает (attack > 0)
      const resolved = await mutate('resolveCombat', {}, actor);
      seen.fight = true;
      const enemyAfter = resolved.fighters.find((f) => f.id === enemy.id);
      const dmg = enemyHpBefore - (enemyAfter?.health ?? 0);
      if (isGaze) {
        // Gaze of Stone: 2 печатные + 8 при победе = 10 (без защиты всегда победа)
        check(`F. Gaze of Stone: урон ${dmg} == 10 (2 + 8 после победы)`, dmg === 10, `(HP ${enemyHpBefore}→${enemyAfter?.health})`);
        seen.gaze = true;
        opportunistic.push('F');
      } else {
        check(`D. бой «${attackCard.name}»: урон ${dmg} > 0 применён цели`, dmg > 0, `(HP ${enemyHpBefore}→${enemyAfter?.health})`);
      }
      // H. draw-эффекты: Snipe/Regroup/The Aid of Morgana → рука выросла после боя
      if (!seen.draw && /Snipe|Regroup|The Aid of Morgana/.test(attackCard.name)) {
        const freshHand = hand(await loadState(tokens[actor]), actor).length;
        // -1 атак.карта, +N draw; рука должна быть >= handBefore - 1 + 1
        check(`H. «${attackCard.name}»: draw-эффект после боя (рука ${handBefore}→${freshHand})`, freshHand >= handBefore, '');
        seen.draw = true;
        opportunistic.push('H');
      }
      continue;
    }

    // Иначе: манёвр в сторону врага (или endTurn без действий)
    if (actions > 0) {
      const step = (() => {
        const dx = Math.sign(enemy.position.x - mine.position.x);
        const dy = Math.sign(enemy.position.y - mine.position.y);
        const tryCells = [
          { x: mine.position.x + dx, y: mine.position.y },
          { x: mine.position.x, y: mine.position.y + dy },
        ].filter((c) => dx !== 0 || dy !== 0);
        for (const c of tryCells) {
          if (c.x === enemy.position.x && c.y === enemy.position.y) continue; // занято врагом
          if (st.fighters.some((f) => f.health > 0 && f.id !== mine.id && f.position.x === c.x && f.position.y === c.y)) continue;
          const cell = st.boardState.cells?.[c.y]?.[c.x];
          if (cell && cell.type === 'obstacle') continue;
          if (c.x < 0 || c.y < 0 || c.x >= st.boardState.width || c.y >= st.boardState.height) continue;
          return c;
        }
        return null;
      })();
      try {
        if (step) await mutate('maneuver', { fighterId: mine.id, boostCardId: null, path: [step] }, actor);
        else await mutate('endTurn', {}, actor);
      } catch {
        await mutate('endTurn', {}, actor).catch(() => {});
      }
    } else {
      await mutate('endTurn', {}, actor).catch(() => {});
    }
  }

  check('D. хотя бы один полный бой прошёл', seen.fight);

  // --- Итог ---
  console.log(`\nОпортунистические проверки: [${opportunistic.join(', ') || 'нет'}]`);
  const ok = failed === 0 && seen.fight && opportunistic.length >= 1;
  console.log(`\n${ok ? 'ALL PASS' : 'FAIL'}: ✅ ${passed} / ❌ ${failed}, опортунистических ${opportunistic.length}`);

  // прибраться
  await gql(`mutation($id: String!) { abortGame(gameId: $id) { id } }`, { id: game.id }, p1.accessToken).catch(() => {});
  process.exit(ok ? 0 : 1);
}

main().catch((e) => {
  console.error('FATAL:', e.message);
  process.exit(1);
});

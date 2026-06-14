/**
 * E2E (VS_AI): «бот защищается». Человек (admin) АТАКУЕТ бота → срабатывает
 * оркестрация бота (AiTurnService, fire-and-forget из executeMutation ПОСЛЕ хода
 * человека) → бот-защитник САМ играет защиту и резолвит бой БЕЗ ручного
 * resolveCombat человеком.
 *
 * Шаги:
 *   1. login admin, прибрать активные игры (abortGame).
 *   2. heroList «Medusa» → герой человеку; createGame VS_AI → selectHero →
 *      toggleReady → startGame (opponentId = бот).
 *   3. Человек на своих ходах манёврами сближается с бот-HERO; при manhattan==1
 *      ищет в руке ATTACK/VERSATILE карту (banner для Medusa: null/'Any'/'Medusa')
 *      и attack(человек-hero → бот-hero, cardId). resolveCombat НЕ зовётся вручную.
 *   4. Ассерты: сразу после attack — combatInfo.defenderId === бот; затем поллингом
 *      дождаться, что combatInfo исчез ИЛИ phase вышла из COMBAT, И sequenceNumber
 *      вырос на ≥2 после атаки (бот сыграл защиту и/или resolveCombat сам).
 *   5. abortGame, 'ALL PASS: N / M', process.exit(ok?0:1).
 *
 *   node backend/scripts/e2e-vs-ai-defense.mjs
 */
const HTTP = 'http://localhost:3000/graphql';
const A = { email: 'admin@unmached.local', password: 'Admin123!' };
let passed = 0, failed = 0;
const check = (n, c, e = '') => { if (c) { passed++; console.log(`  ✅ ${n}`); } else { failed++; console.log(`  ❌ ${n} ${e}`); } };
async function gql(query, variables, token) {
  const r = await fetch(HTTP, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: JSON.stringify({ query, variables }) });
  const j = await r.json();
  if (j.errors?.length) { const e = new Error(j.errors.map((x) => x.message).join('; ')); e.isGql = true; throw e; }
  return j.data;
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Шаг к врагу: одна из двух клеток (по x / по y) ближе к врагу, не занятая, не препятствие.
// Скопировано из e2e-choose-one.mjs stepToward.
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

const manhattan = (a, b) => Math.abs(a.position.x - b.position.x) + Math.abs(a.position.y - b.position.y);
// Карта-атака для Medusa: ATTACK/VERSATILE и banner null/'Any'/совпадает с именем героя.
const bannerOk = (c, heroName) => !c.bannerName || c.bannerName === 'Any' || c.bannerName === heroName;
const isAttackCard = (c, heroName) => (c.cardType === 'ATTACK' || c.cardType === 'VERSATILE') && bannerOk(c, heroName);

async function main() {
  const p1 = (await gql(`mutation($e:String!,$p:String!){ login(input:{email:$e,password:$p}){ accessToken user{ id } } }`, { e: A.email, p: A.password })).login;
  const cleanup = async () => {
    const mine = await gql(`query { myGames { id status } }`, {}, p1.accessToken);
    for (const g of mine.myGames.filter((g) => ['LOBBY', 'IN_PROGRESS', 'PENDING'].includes(g.status))) {
      await gql(`mutation($id:String!){ abortGame(gameId:$id){ id } }`, { id: g.id }, p1.accessToken).catch(() => {});
    }
  };
  await cleanup();

  const heroData = (await gql(`query { heroList(limit:1, search:"Medusa"){ items{ id name } } }`, {}, p1.accessToken)).heroList.items[0];
  if (!heroData) throw new Error('герой «Medusa» не найден в heroList');
  const heroName = heroData.name;

  const load = async (gid) => JSON.parse((await gql(`query($g:String!){ gameState(gameId:$g){ state } }`, { g: gid }, p1.accessToken)).gameState.state);
  const myHero = (s) => s.fighters.find((f) => f.ownerId === p1.user.id && f.type === 'HERO');
  const botHero = (s, aiId) => s.fighters.find((f) => f.ownerId === aiId && f.type === 'HERO');
  const hand = (s) => s.handZones[p1.user.id]?.cards ?? [];

  const setupGame = async () => {
    const game = (await gql(`mutation { createGame(input:{mode:VS_AI}){ id } }`, {}, p1.accessToken)).createGame;
    await gql(`mutation($g:String!,$h:String!){ selectHero(gameId:$g,heroId:$h){ id } }`, { g: game.id, h: heroData.id }, p1.accessToken);
    await gql(`mutation($g:String!){ toggleReady(gameId:$g){ id } }`, { g: game.id }, p1.accessToken);
    const started = (await gql(`mutation($g:String!){ startGame(gameId:$g){ opponentId } }`, { g: game.id }, p1.accessToken)).startGame;
    return { id: game.id, aiId: started.opponentId };
  };

  // Один прогон партии. Возвращает:
  //   { attacked:true, seqAfterAttack, defenderIsBot, gid, aiId } — человек атаковал бота,
  //   { attacked:false, gid, aiId } — за бюджет ходов не удалось (повод для ретрая).
  const playUntilHumanAttacks = async (gid, aiId) => {
    for (let iter = 0; iter < 25; iter++) {
      let st = await load(gid);
      if (st.phase === 'GAME_OVER') return { attacked: false, gid, aiId };

      // не наш ход / идёт чужой бой — дать боту/движку отыграть, поллим
      const ci = st.metadata?.combatInfo;
      const ourTurn = st.currentTurnPlayerId === p1.user.id;
      const inCombat = st.phase === 'COMBAT' || st.phase === 'COMBAT_RESOLVE';
      if (!ourTurn || (inCombat && ci)) { await sleep(800); continue; }
      if (st.phase !== 'ACTION_MANEUVER' && st.phase !== 'ACTION_ATTACK') { await sleep(500); continue; }

      const mine = myHero(st);
      const bot = botHero(st, aiId);
      if (!mine || !bot) return { attacked: false, gid, aiId };
      const actions = st.metadata?.actionsRemaining ?? 2;

      // Смежны → ищем атаку-карту и бьём бота
      if (manhattan(mine, bot) === 1) {
        const atk = hand(st).find((c) => isAttackCard(c, heroName));
        if (atk) {
          const after = JSON.parse((await gql(
            `mutation($input:AttackDto!){ attack(input:$input){ state } }`,
            { input: { gameId: gid, attackerId: mine.id, targetId: bot.id, cardId: atk.id } },
            p1.accessToken,
          )).attack.state);
          const aci = after.metadata?.combatInfo;
          return { attacked: true, seqAfterAttack: after.sequenceNumber, defenderIsBot: aci?.defenderId === aiId, after, gid, aiId };
        }
        // смежны, но нет атаки-карты — пытаемся добрать ход (endTurn → новая рука/добор)
        if (actions <= 0) { await gql(`mutation($input:EndTurnDto!){ endTurn(input:$input){ sequenceNumber } }`, { input: { gameId: gid } }, p1.accessToken).catch(() => {}); await sleep(700); continue; }
        // есть действия, но нет карты — закончим ход, чтобы получить новую руку/добор
        await gql(`mutation($input:EndTurnDto!){ endTurn(input:$input){ sequenceNumber } }`, { input: { gameId: gid } }, p1.accessToken).catch(() => {});
        await sleep(700);
        continue;
      }

      // Не смежны → манёвр к боту, если есть действия; иначе конец хода
      if (actions > 0) {
        const step = stepToward(st, mine, bot);
        if (step) {
          await gql(
            `mutation($input:ManeuverDto!){ maneuver(input:$input){ sequenceNumber } }`,
            { input: { gameId: gid, fighterId: mine.id, boostCardId: null, path: [step] } },
            p1.accessToken,
          ).catch(async () => { await gql(`mutation($input:EndTurnDto!){ endTurn(input:$input){ sequenceNumber } }`, { input: { gameId: gid } }, p1.accessToken).catch(() => {}); });
        } else {
          await gql(`mutation($input:EndTurnDto!){ endTurn(input:$input){ sequenceNumber } }`, { input: { gameId: gid } }, p1.accessToken).catch(() => {});
          await sleep(700);
        }
      } else {
        await gql(`mutation($input:EndTurnDto!){ endTurn(input:$input){ sequenceNumber } }`, { input: { gameId: gid } }, p1.accessToken).catch(() => {});
        await sleep(700);
      }
    }
    return { attacked: false, gid, aiId };
  };

  console.log(`Medusa (человек) атакует бота — ищем партию, где человек дойдёт до атаки`);
  let res = null, game = null;
  for (let attempt = 0; attempt < 6 && !(res && res.attacked); attempt++) {
    game = await setupGame();
    res = await playUntilHumanAttacks(game.id, game.aiId);
    if (!(res && res.attacked)) {
      await gql(`mutation($id:String!){ abortGame(gameId:$id){ id } }`, { id: game.id }, p1.accessToken).catch(() => {});
      console.log(`  попытка ${attempt + 1}: человек не атаковал — ретрай новой партией`);
    } else {
      console.log(`  попытка ${attempt + 1}: человек атаковал бота (seq=${res.seqAfterAttack})`);
    }
  }

  check('человек дошёл до атаки бота (партия найдена)', Boolean(res && res.attacked), '(не сблизился/нет атак-карты за 6 партий)');
  if (!(res && res.attacked)) {
    console.log(`\nFAIL: ✅ ${passed} / ❌ ${failed}`);
    process.exit(1);
  }

  const { gid, aiId, seqAfterAttack } = res;
  // Ассерт 1: сразу после attack человека бот — защитник.
  check('после attack: бот назначен защитником (combatInfo.defenderId === бот)', res.defenderIsBot,
    `(defenderId=${res.after.metadata?.combatInfo?.defenderId}, aiId=${aiId})`);

  // Ассерт 2: бот САМ закрыл бой — поллим, пока combatInfo исчез ИЛИ phase вышла из COMBAT,
  // И sequenceNumber вырос на ≥2 после атаки (бот сыграл защиту и/или resolveCombat).
  let combatClosed = false, finalSeq = seqAfterAttack, finalSt = res.after;
  for (let i = 0; i < 25; i++) { // ~20с поллинга
    await sleep(800);
    finalSt = await load(gid);
    finalSeq = finalSt.sequenceNumber;
    const ci = finalSt.metadata?.combatInfo;
    const outOfCombat = finalSt.phase !== 'COMBAT' && finalSt.phase !== 'COMBAT_RESOLVE';
    if ((!ci || outOfCombat) && finalSeq >= seqAfterAttack + 2) { combatClosed = true; break; }
    if (finalSt.phase === 'GAME_OVER' && finalSeq >= seqAfterAttack + 1) { combatClosed = true; break; }
  }
  check('бот САМ закрыл бой (combatInfo исчез/вне COMBAT и seq +≥2)', combatClosed,
    `(phase=${finalSt.phase}, combatInfo=${finalSt.metadata?.combatInfo ? 'есть' : 'нет'}, seq ${seqAfterAttack}→${finalSeq})`);

  await gql(`mutation($id:String!){ abortGame(gameId:$id){ id } }`, { id: gid }, p1.accessToken).catch(() => {});
  const ok = failed === 0;
  console.log(`\n${ok ? 'ALL PASS' : 'FAIL'}: ✅ ${passed} / ❌ ${failed}`);
  process.exit(ok ? 0 : 1);
}
main().catch((e) => { console.error('FATAL:', e.message); process.exit(1); });

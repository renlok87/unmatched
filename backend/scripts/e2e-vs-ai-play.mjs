/**
 * E2E Inc3 (VS_AI): бот реально играет. Человек (admin) завершает ход →
 * срабатывает оркестрация бота (AiTurnService, fire-and-forget) → бот делает
 * свои действия (двигается/атакует) → ход возвращается человеку.
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

async function main() {
  const p1 = (await gql(`mutation($e:String!,$p:String!){ login(input:{email:$e,password:$p}){ accessToken user{ id } } }`, { e: A.email, p: A.password })).login;
  const mine = await gql(`query { myGames { id status } }`, {}, p1.accessToken);
  for (const g of mine.myGames.filter((g) => ['LOBBY', 'IN_PROGRESS', 'PENDING'].includes(g.status))) {
    await gql(`mutation($id:String!){ abortGame(gameId:$id){ id } }`, { id: g.id }, p1.accessToken).catch(() => {});
  }
  const hero = (await gql(`query { heroList(limit:1, search:"Medusa"){ items{ id } } }`, {}, p1.accessToken)).heroList.items[0];

  const game = (await gql(`mutation { createGame(input:{mode:VS_AI}){ id } }`, {}, p1.accessToken)).createGame;
  await gql(`mutation($g:String!,$h:String!){ selectHero(gameId:$g,heroId:$h){ id } }`, { g: game.id, h: hero.id }, p1.accessToken);
  await gql(`mutation($g:String!){ toggleReady(gameId:$g){ id } }`, { g: game.id }, p1.accessToken);
  const started = (await gql(`mutation($g:String!){ startGame(gameId:$g){ opponentId } }`, { g: game.id }, p1.accessToken)).startGame;
  const aiId = started.opponentId;

  const load = async () => JSON.parse((await gql(`query($g:String!){ gameState(gameId:$g){ state } }`, { g: game.id }, p1.accessToken)).gameState.state);
  const botHero = (s) => s.fighters.find((f) => f.ownerId === aiId && f.type === 'HERO');

  let st = await load();
  check('старт: ход человека', st.currentTurnPlayerId === p1.user.id, st.currentTurnPlayerId);
  const botStart = { ...botHero(st).position };
  const seqStart = st.sequenceNumber;
  console.log(`  бот-герой старт: (${botStart.x},${botStart.y}), seq ${seqStart}`);

  // Человек завершает ход → ход переходит боту → оркестрация бота
  await gql(`mutation($g:String!){ endTurn(input:{gameId:$g}){ sequenceNumber } }`, { g: game.id }, p1.accessToken);

  // Бот ходит асинхронно (fire-and-forget) — поллим до «мяч у человека»:
  // либо ход вернулся человеку (action-фаза), либо бот атаковал → человек защищается (COMBAT).
  let humanToAct = false, botMoved = false, finalSeq = seqStart;
  for (let i = 0; i < 25; i++) {
    await sleep(800);
    st = await load();
    finalSeq = st.sequenceNumber;
    const bh = botHero(st);
    if (bh && (bh.position.x !== botStart.x || bh.position.y !== botStart.y)) botMoved = true;
    if (st.phase === 'GAME_OVER') { humanToAct = true; break; }
    const ci = st.metadata?.combatInfo;
    const humanDefends = st.phase === 'COMBAT' && ci?.defenderId === p1.user.id;
    const turnBack = st.currentTurnPlayerId === p1.user.id && st.phase !== 'COMBAT';
    if ((turnBack && st.sequenceNumber > seqStart + 1) || humanDefends) { humanToAct = true; break; }
  }

  const ci = st.metadata?.combatInfo;
  check('бот отыграл ход (seq вырос)', finalSeq > seqStart + 1, `(${seqStart}→${finalSeq})`);
  check('бот-герой сдвинулся к человеку (манёвр бота)', botMoved, `(старт ${botStart.x},${botStart.y} → ${JSON.stringify(botHero(st)?.position)})`);
  check('мяч у человека (его ход / он защитник / GAME_OVER)', humanToAct,
    `(turn=${st.currentTurnPlayerId === p1.user.id ? 'human' : 'AI'}, phase ${st.phase}, defender=${ci?.defenderId === p1.user.id ? 'human' : ci?.defenderId})`);
  // Если бот атаковал — проверим, что человек теперь защитник (полный combat-флоу бота)
  if (st.phase === 'COMBAT') {
    check('бот атаковал → человек назначен защитником', ci?.defenderId === p1.user.id, JSON.stringify(ci));
  }

  await gql(`mutation($id:String!){ abortGame(gameId:$id){ id } }`, { id: game.id }, p1.accessToken).catch(() => {});
  const ok = failed === 0;
  console.log(`\n${ok ? 'ALL PASS' : 'FAIL'}: ✅ ${passed} / ❌ ${failed}`);
  process.exit(ok ? 0 : 1);
}
main().catch((e) => { console.error('FATAL:', e.message); process.exit(1); });

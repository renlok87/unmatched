/**
 * E2E Inc1 (VS_AI): создание+старт VS_AI игры → бот автодобавляется вторым
 * игроком, состояние инициализируется (2 героя-бойца). Бот ходить ещё не умеет
 * (Inc 3) — проверяем только сетап.
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
async function main() {
  const p1 = (await gql(`mutation($e:String!,$p:String!){ login(input:{email:$e,password:$p}){ accessToken user{ id } } }`, { e: A.email, p: A.password })).login;
  // прибрать активные
  const mine = await gql(`query { myGames { id status } }`, {}, p1.accessToken);
  for (const g of mine.myGames.filter((g) => ['LOBBY', 'IN_PROGRESS', 'PENDING'].includes(g.status))) {
    await gql(`mutation($id:String!){ abortGame(gameId:$id){ id } }`, { id: g.id }, p1.accessToken).catch(() => {});
  }
  const hero = (await gql(`query { heroList(limit:1, search:"Medusa"){ items{ id name } } }`, {}, p1.accessToken)).heroList.items[0];

  const game = (await gql(`mutation { createGame(input:{mode:VS_AI}){ id code mode } }`, {}, p1.accessToken)).createGame;
  check('VS_AI игра создана', game.mode === 'VS_AI', game.mode);
  await gql(`mutation($g:String!,$h:String!){ selectHero(gameId:$g,heroId:$h){ id } }`, { g: game.id, h: hero.id }, p1.accessToken);
  await gql(`mutation($g:String!){ toggleReady(gameId:$g){ id } }`, { g: game.id }, p1.accessToken);
  const started = (await gql(`mutation($g:String!){ startGame(gameId:$g){ id status opponentId players{ userId heroId } } }`, { g: game.id }, p1.accessToken)).startGame;
  check('игра запущена (IN_PROGRESS)', started.status === 'IN_PROGRESS', started.status);
  check('бот назначен opponentId', Boolean(started.opponentId) && started.opponentId !== p1.user.id, `(${started.opponentId})`);
  check('2 игрока с героями', started.players.length === 2 && started.players.every((p) => p.heroId), JSON.stringify(started.players));

  const st = JSON.parse((await gql(`query($g:String!){ gameState(gameId:$g){ state } }`, { g: game.id }, p1.accessToken)).gameState.state);
  const heroes = st.fighters.filter((f) => f.type === 'HERO');
  check('состояние: 2 героя-бойца (человек + бот)', heroes.length === 2, `(${heroes.length})`);
  const owners = new Set(st.fighters.map((f) => f.ownerId));
  check('бойцы у двух владельцев', owners.size === 2, JSON.stringify([...owners]));
  const aiId = started.opponentId;
  check('у бота есть колода', (st.decks?.[aiId]?.drawPile ?? []).length > 0, `(${(st.decks?.[aiId]?.drawPile ?? []).length})`);
  check('у бота есть рука', (st.handZones?.[aiId]?.cards ?? []).length > 0, `(${(st.handZones?.[aiId]?.cards ?? []).length})`);

  await gql(`mutation($id:String!){ abortGame(gameId:$id){ id } }`, { id: game.id }, p1.accessToken).catch(() => {});
  const ok = failed === 0;
  console.log(`\n${ok ? 'ALL PASS' : 'FAIL'}: ✅ ${passed} / ❌ ${failed}`);
  process.exit(ok ? 0 : 1);
}
main().catch((e) => { console.error('FATAL:', e.message); process.exit(1); });

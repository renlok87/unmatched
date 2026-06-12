/**
 * Сетап тестовой партии Medusa vs King Arthur (без abort) — для ручной/
 * браузерной проверки фронта. Печатает gameId и accessToken'ы обоих игроков.
 */
const HTTP = 'http://localhost:3000/graphql';

async function gql(query, variables, token) {
  const res = await fetch(HTTP, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ query, variables }),
  });
  const json = await res.json();
  if (json.errors?.length) throw new Error(json.errors.map((e) => e.message).join('; '));
  return json.data;
}

const LOGIN = `mutation($e: String!, $p: String!) { login(input: {email: $e, password: $p}) { accessToken refreshToken user { id username } } }`;

const p1 = (await gql(LOGIN, { e: 'admin@unmached.local', p: 'Admin123!' })).login;
const p2 = (await gql(LOGIN, { e: 'tester2@unmached.local', p: 'Tester123!' })).login;

for (const u of [p1, p2]) {
  const my = await gql(`query { myGames { id status } }`, {}, u.accessToken);
  for (const g of my.myGames.filter((g) => ['LOBBY', 'IN_PROGRESS', 'PENDING'].includes(g.status))) {
    await gql(`mutation($id: String!) { abortGame(gameId: $id) { id } }`, { id: g.id }, u.accessToken).catch(() => {});
  }
}

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

const game = (await gql(`mutation { createGame(input: {mode: ONE_V_ONE}) { id code } }`, {}, p1.accessToken)).createGame;
await gql(`mutation($id: String!) { joinGame(input: {gameId: $id}) { id } }`, { id: game.id }, p2.accessToken);
await gql(`mutation($g: String!, $h: String!) { selectHero(gameId: $g, heroId: $h) { id } }`, { g: game.id, h: medusa.id }, p1.accessToken);
await gql(`mutation($g: String!, $h: String!) { selectHero(gameId: $g, heroId: $h) { id } }`, { g: game.id, h: arthur.id }, p2.accessToken);
await gql(`mutation($g: String!) { toggleReady(gameId: $g) { id } }`, { g: game.id }, p1.accessToken);
await gql(`mutation($g: String!) { toggleReady(gameId: $g) { id } }`, { g: game.id }, p2.accessToken);
await gql(`mutation($g: String!) { startGame(gameId: $g) { id status } }`, { g: game.id }, p1.accessToken);

console.log(JSON.stringify({
  gameId: game.id,
  code: game.code,
  p1: { userId: p1.user.id, accessToken: p1.accessToken, refreshToken: p1.refreshToken },
  p2: { userId: p2.user.id, accessToken: p2.accessToken, refreshToken: p2.refreshToken },
}, null, 2));

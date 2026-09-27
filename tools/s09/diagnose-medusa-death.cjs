// One-shot diagnostic: run a duel with NOTHING but pass turns (no schemes, no
// attacks) and watch Medusa's health. Any drop = a server-side periodic/
// ability effect, not the capture script.
const fs = require('fs');
const path = require('path');
const HTTP = 'http://localhost:3120/graphql';
const envPath = path.resolve(__dirname, '..', '..', 'backend', '.env');
for (const line of fs.readFileSync(envPath, 'utf8').split(/\r?\n/)) {
  const m = line.match(/^([A-Z0-9_]+)=(.*)$/);
  if (m && !process.env[m[1]]) process.env[m[1]] = m[2];
}
async function gqlRaw(query, variables, token) {
  const r = await fetch(HTTP, { method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ query, variables }) });
  return await r.text();
}
async function gql(query, variables, token) {
  const j = JSON.parse(await gqlRaw(query, variables, token));
  if (j.errors?.length) { const e = new Error(j.errors[0].message); throw e; }
  return j.data;
}
(async () => {
  const host = (await gql(`mutation L($i: LoginDto!) { login(input: $i) { accessToken user { id } } }`,
    { i: { email: process.env.S09_DEMO_HOST_EMAIL, password: process.env.S09_DEMO_HOST_PASSWORD } })).login;
  const joiner = (await gql(`mutation L($i: LoginDto!) { login(input: $i) { accessToken user { id } } }`,
    { i: { email: process.env.S09_DEMO_JOINER_EMAIL, password: process.env.S09_DEMO_JOINER_PASSWORD } })).login;
  const game = (await gql(`mutation C { createGame(input: { mode: ONE_V_ONE }) { id } }`, {}, host.accessToken)).createGame;
  const gameId = game.id;
  try {
    const heroes = (await gql(`query HL($limit: Int) { heroList(limit: $limit) { items { id name } } }`, { limit: 300 }, host.accessToken)).heroList.items;
    await gql(`mutation J($i: JoinGameDto!) { joinGame(input: $i) { id } }`, { i: { gameId } }, joiner.accessToken);
    await gql(`mutation S($g: String!, $h: String!) { selectHero(gameId: $g, heroId: $h) { id } }`, { g: gameId, h: heroes.find((h) => h.name === 'Medusa').id }, host.accessToken);
    await gql(`mutation S($g: String!, $h: String!) { selectHero(gameId: $g, heroId: $h) { id } }`, { g: gameId, h: heroes.find((h) => h.name === 'King Arthur').id }, joiner.accessToken);
    await gql(`mutation R($g: String!) { toggleReady(gameId: $g) { id } }`, { g: gameId }, host.accessToken);
    await gql(`mutation R($g: String!) { toggleReady(gameId: $g) { id } }`, { g: gameId }, joiner.accessToken);
    await gql(`mutation St($g: String!) { startGame(gameId: $g) { id } }`, { g: gameId }, host.accessToken);
    const stateFor = async () => JSON.parse((await gql(`query Q($g: String!) { gameState(gameId: $g) { state } }`, { g: gameId }, host.accessToken)).gameState.state);
    let prev = '';
    for (let turn = 0; turn < 60; turn++) {
      let s = await stateFor();
      const line = s.fighters.map((f) => `${f.name}:${f.health}${f.isDefeated ? 'X' : ''}`).join(' ');
      if (line !== prev) { console.log(`turn ${turn} seq ${s.sequenceNumber} phase ${s.phase}: ${line}`); prev = line; }
      if (s.metadata.pendingHandDiscard) {
        const actor = s.metadata.pendingHandDiscard.playerId === host.user.id ? host : joiner;
        const ids = (s.handZones[actor.user.id]?.cards ?? []).slice(0, s.metadata.pendingHandDiscard.count).map((c) => c.id);
        await gqlRaw(`mutation D($i: DiscardToLimitDto!) { discardToLimit(input: $i) { sequenceNumber } }`,
          { i: { gameId, pendingId: s.metadata.pendingHandDiscard.id, cardIds: ids } }, actor.accessToken);
        continue;
      }
      if (s.metadata.pendingEffects?.length) throw new Error('unexpected pending: ' + s.metadata.pendingEffects[0].type);
      const actor = s.currentTurnPlayerId === host.user.id ? host : joiner;
      if (s.phase === 'ACTION_MANEUVER' || s.phase === 'ACTION_ATTACK') {
        const begin = JSON.parse((await gql(`mutation B($i: BeginManeuverDto!) { beginManeuver(input: $i) { state } }`,
          { i: { gameId, expectedSequenceNumber: s.sequenceNumber } }, actor.accessToken)).beginManeuver.state);
        const pid = begin.metadata.pendingManeuver?.id;
        if (pid) await gqlRaw(`mutation M($i: ManeuverDto!) { maneuver(input: $i) { sequenceNumber } }`,
          { i: { gameId, maneuverId: pid, moves: [], boostCardId: null } }, actor.accessToken);
        continue;
      }
      await gqlRaw(`mutation E($g: String!) { endTurn(gameId: $g) { id } }`, { g: gameId }, actor.accessToken).catch((e) => console.log('endTurn err', String(e.message).slice(0, 100)));
    }
  } finally {
    await gql(`mutation AB($id: String!) { abortGame(gameId: $id) { id } }`, { id: gameId }, host.accessToken).catch(() => {});
  }
})().catch((e) => { console.error(e.message ?? e); process.exit(1); });

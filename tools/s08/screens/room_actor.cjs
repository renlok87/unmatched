// VS-7 S3 review tooling (SC-14...SC-20 live checks with ONE editor-build client): the second player of a ROOM, driven
// over the real GraphQL API (no UE). Credentials only from the process environment (S08_ACTOR_EMAIL /
// S08_ACTOR_PASSWORD) - never argv, never printed; no token, no room code on stdout (the code goes only to --code-file,
// outside git, for the UE guest's env).
//
//   node room_actor.cjs --api http://localhost:3000/graphql --role guest  [--hero "King Arthur"]
//        waits for a NEW open ONE_V_ONE room (not listed at start), joins it, waits for the host's hero, picks --hero,
//        toggles ready, waits until the room is IN_PROGRESS (or 240 s), then leaves the room / the match.
//   node room_actor.cjs --api ... --role host --code-file <path> [--hero Medusa] [--board <id>]
//        creates a ONE_V_ONE room on --board (Marmoreal original by default), picks --hero, writes the code to
//        --code-file, waits for a guest with a hero who is ready, toggles ready, starts the match, waits 60 s, leaves.
//        VS-7 S4: --play-after-ms <ms> plays the host's own turns after the start (two maneuvers without a move, then
//        endTurn) for --play-turns <n> turns (default 1), each step one {step: 'play', seq} line - the match goes on
//        while the UE guest has PAUSE open (SC-24: «партия на сервере не стоит»).
//   node room_actor.cjs --api ... --role cleanup
//        leaves the account's own LOBBY / IN_PROGRESS rooms of earlier runs.
// Every step prints one JSON line {t, step, ...counts}.
const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, all) => (v.startsWith('--') ? [...a, [v.slice(2), all[i + 1]]] : a), []));
const api = args.api || 'http://localhost:3000/graphql';
const role = args.role || 'guest';
const heroName = args.hero || (role === 'host' ? 'Medusa' : 'King Arthur');
const board = args.board || 'c121b47f8d6eb28daccb76d05';
const t0 = Date.now();
const log = (step, extra = {}) => {
  const line = JSON.stringify({ t: Date.now() - t0, step, ...extra }) + '\n';
  process.stdout.write(line);
  if (args.log) require('node:fs').appendFileSync(args.log, line);
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let token = '';

async function gql(query, variables = {}) {
  const r = await fetch(api, {
    method: 'POST',
    headers: { 'content-type': 'application/json', ...(token ? { authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ query, variables }),
  });
  const j = await r.json();
  if (j.errors && j.errors.length) throw new Error(j.errors[0].message);
  return j.data;
}

const ROOM = 'id code status mode hostId boardId players { userId username heroId isReady seatOrder }';

async function main() {
  const email = process.env.S08_ACTOR_EMAIL;
  const password = process.env.S08_ACTOR_PASSWORD;
  if (!email || !password) throw new Error('S08_ACTOR_EMAIL / S08_ACTOR_PASSWORD missing');
  const login = await gql('mutation L($input: LoginDto!) { login(input: $input) { accessToken user { id username } } }', { input: { email, password } });
  token = login.login.accessToken;
  const me = login.login.user.id;
  log('login');
  const heroes = (await gql('query { heroList(limit: 200) { items { id name } } }')).heroList.items;
  const hero = heroes.find((h) => h.name === heroName);
  if (!hero) throw new Error('hero not in heroList');
  if (role === 'cleanup') {
    // the account's own rooms / matches of earlier runs (LOBBY, IN_PROGRESS) are left
    for (const status of ['LOBBY', 'IN_PROGRESS']) {
      const games = (await gql('query M($s: GameStatus) { myGames(filters: { status: $s }) { id } }', { s: status })).myGames;
      for (const g of games) {
        try {
          await gql('mutation Lv($g: String!) { leaveGame(gameId: $g) }', { g: g.id });
          log('left', { status });
        } catch (e) {
          log('leave-failed', { status, error: String(e.message).slice(0, 80) });
        }
      }
    }
    return;
  }
  let room;
  const get = async () => (room = (await gql(`query G($id: String!) { game(id: $id) { ${ROOM} } }`, { id: room.id })).game);
  if (role === 'host') {
    room = (await gql(`mutation C($input: CreateGameDto!) { createGame(input: $input) { ${ROOM} } }`, { input: { mode: 'ONE_V_ONE', boardId: board } })).createGame;
    log('created', { board: room.boardId });
    room = (await gql(`mutation S($g: String!, $h: String!) { selectHero(gameId: $g, heroId: $h) { ${ROOM} } }`, { g: room.id, h: hero.id })).selectHero;
    log('picked');
    if (args['code-file']) require('node:fs').writeFileSync(args['code-file'], room.code);
    for (let i = 0; i < 240; i++) {
      await get();
      const other = room.players.find((p) => p.userId !== me);
      if (other && other.heroId && other.isReady) break;
      await sleep(1000);
    }
    log('guest-ready', { players: room.players.length });
    await sleep(Number(args['hold-ms'] || 4000));
    room = (await gql(`mutation R($g: String!) { toggleReady(gameId: $g) { ${ROOM} } }`, { g: room.id })).toggleReady;
    log('ready');
    await sleep(Number(args['start-after-ms'] || 3000));
    room = (await gql(`mutation St($g: String!) { startGame(gameId: $g) { ${ROOM} } }`, { g: room.id })).startGame;
    log('started', { status: room.status });
    if (args['play-after-ms']) await play(room.id, me);
    await sleep(Number(args['stay-ms'] || 60000));
  } else {
    const seen = new Set((await gql('query A { availableGames(mode: "ONE_V_ONE", limit: 50) { id } }')).availableGames.map((g) => g.id));
    for (let i = 0; i < 180 && !room; i++) {
      const list = (await gql('query A { availableGames(mode: "ONE_V_ONE", limit: 50) { id hostId } }')).availableGames;
      const fresh = list.find((g) => !seen.has(g.id) && g.hostId !== me);
      if (fresh) room = fresh;
      else await sleep(1000);
    }
    if (!room) throw new Error('no new room');
    room = (await gql(`mutation J($input: JoinGameDto!) { joinGame(input: $input) { ${ROOM} } }`, { input: { gameId: room.id } })).joinGame;
    log('joined');
    for (let i = 0; i < 180; i++) {
      await get();
      const host = room.players.find((p) => p.userId !== me);
      if (host && host.heroId) break;
      await sleep(1000);
    }
    log('host-picked');
    await sleep(Number(args['hold-ms'] || 4000));
    room = (await gql(`mutation S($g: String!, $h: String!) { selectHero(gameId: $g, heroId: $h) { ${ROOM} } }`, { g: room.id, h: hero.id })).selectHero;
    log('picked');
    await sleep(Number(args['hold-ms'] || 4000));
    room = (await gql(`mutation R($g: String!) { toggleReady(gameId: $g) { ${ROOM} } }`, { g: room.id })).toggleReady;
    log('ready');
    for (let i = 0; i < 240 && room.status !== 'IN_PROGRESS'; i++) {
      await sleep(1000);
      await get();
    }
    log('in-progress', { status: room.status });
    await sleep(Number(args['stay-ms'] || 60000));
  }
  try {
    await gql('mutation Lv($g: String!) { leaveGame(gameId: $g) }', { g: room.id });
    log('left');
  } catch (e) {
    log('leave-failed', { error: String(e.message).slice(0, 80) });
  }
}

// VS-7 S4: the host's own turns over the API (no UE): maneuver x2 without a move, then endTurn
async function play(gameId, me) {
  await sleep(Number(args['play-after-ms']));
  const turns = Number(args['play-turns'] || 1);
  let done = 0;
  for (let i = 0; i < 240 && done < turns; i++) {
    let st;
    try {
      st = JSON.parse((await gql('query GS($g: String!) { gameState(gameId: $g) { state } }', { g: gameId })).gameState.state);
    } catch (e) {
      log('play-state-failed', { error: String(e.message).slice(0, 80) });
      await sleep(1000);
      continue;
    }
    if (st.currentTurnPlayerId !== me || !String(st.phase || '').startsWith('ACTION')) {
      await sleep(1000);
      continue;
    }
    try {
      if ((st.metadata?.actionsRemaining ?? 0) > 0) {
        const begin = await gql('mutation B($input: BeginManeuverDto!) { beginManeuver(input: $input) { state } }',
          { input: { gameId, expectedSequenceNumber: st.sequenceNumber } });
        const after = JSON.parse(begin.beginManeuver.state);
        const m = await gql('mutation M($input: ManeuverDto!) { maneuver(input: $input) { sequenceNumber } }',
          { input: { gameId, maneuverId: after.metadata.pendingManeuver?.id, moves: [], boostCardId: null } });
        log('play', { action: 'maneuver', seq: m.maneuver.sequenceNumber });
      } else {
        await gql('mutation E($g: String!) { endTurn(gameId: $g) { id } }', { g: gameId });
        done++;
        log('play', { action: 'endTurn', seq: st.sequenceNumber });
      }
    } catch (e) {
      log('play-failed', { error: String(e.message).slice(0, 80) });
      await sleep(1000);
    }
    await sleep(1500);
  }
}

main().catch((e) => {
  log('error', { error: String(e.message).slice(0, 120) });
  process.exit(1);
});

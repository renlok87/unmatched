// GD-028: capture REAL contract fixtures from the live S08 backend.
// Credentials come from the orchestrator's environment
// (S08_FIXTURE_HOST_EMAIL/PASSWORD + S08_FIXTURE_GUEST_EMAIL/PASSWORD) -
// never hard-coded. The default target is the worktree-local stack
// (http://localhost:3100/graphql).
// Writes raw evidence fixtures; nothing here fabricates server state —
// malformed/wrong-scalar/auth fixtures are client-resilience inputs built
// from the real shapes, clearly named.
// The room created by THIS script is aborted in a finally block (scoped to
// the exact game id this run created, host-ownership validated); if creation
// hits the active-game cap the script FAILS instead of purging unrelated
// rooms.
import { createRequire } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { createClient } = require('graphql-ws');
const WebSocket = require('ws');

const HTTP_URL = process.env.S08_API ?? 'http://localhost:3100/graphql';
const WS_URL = HTTP_URL.replace('http://', 'ws://');
const OUT_DIR = resolve(dirname(fileURLToPath(import.meta.url)),
  '../../docs/game-design/evidence/S08/fixtures');
mkdirSync(OUT_DIR, { recursive: true });

const CREDS = {
  host: { email: process.env.S08_FIXTURE_HOST_EMAIL, password: process.env.S08_FIXTURE_HOST_PASSWORD },
  guest: { email: process.env.S08_FIXTURE_GUEST_EMAIL, password: process.env.S08_FIXTURE_GUEST_PASSWORD },
};
for (const [role, c] of Object.entries(CREDS)) {
  if (!c.email || !c.password) {
    console.error(`missing S08_FIXTURE_${role.toUpperCase()}_EMAIL/S08_FIXTURE_${role.toUpperCase()}_PASSWORD in environment`);
    process.exit(1);
  }
}

async function gql(token, query, variables) {
  const res = await fetch(HTTP_URL, {
    method: 'POST',
    headers: { 'content-type': 'application/json', ...(token && { authorization: `Bearer ${token}` }) },
    body: JSON.stringify({ query, variables }),
  });
  const body = await res.json();
  return { status: res.status, body };
}

const LOGIN = `mutation L($input: LoginDto!) { login(input: $input) { accessToken refreshToken user { id username } } }`;
const CREATE = `mutation C($input: CreateGameDto!, $key: String) { createGame(input: $input, idempotencyKey: $key) { id code status mode hostId players { userId username heroId isReady seatOrder } } }`;
const BY_CODE = `query BC($code: String!) { gameByCode(code: $code) { id code status mode hostId players { userId username heroId isReady seatOrder } } }`;
const JOIN = `mutation J($input: JoinGameDto!) { joinGame(input: $input) { id code status players { userId username heroId isReady seatOrder } } }`;
const SELECT = `mutation S($gameId: String!, $heroId: String!) { selectHero(gameId: $gameId, heroId: $heroId) { id players { userId heroId isReady } } }`;
const READY = `mutation R($gameId: String!) { toggleReady(gameId: $gameId) { id status players { userId isReady } } }`;
const START = `mutation ST($gameId: String!) { startGame(gameId: $gameId) { id status } }`;
const STATE = `query GS($gameId: String!) { gameState(gameId: $gameId) { id gameId state sequenceNumber phase turnCount currentTurnPlayerId updatedAt } }`;
const GAME = `query G($id: String!) { game(id: $id) { id code status hostId } }`;
const ABORT = `mutation AB($gameId: String!) { abortGame(gameId: $gameId) { id status } }`;
const SUB_STATE = `subscription SU($gameId: String!) { gameStateUpdated(gameId: $gameId) { gameId sequenceNumber phase turnCount currentTurnPlayerId players fighters handZones discardPiles boardState metadata } }`;

const redactEvidence = (obj) => JSON.parse(JSON.stringify(obj, (k, v) => {
  if (k === 'accessToken' || k === 'refreshToken') return '<redacted-in-evidence; real value used live>';
  if (k === 'code' && typeof v === 'string' && /^[A-Z0-9-]{4,12}$/.test(v)) return '<redacted>';
  return v;
}));

const save = (name, payload) => {
  writeFileSync(resolve(OUT_DIR, name), JSON.stringify(redactEvidence(payload), null, 2) + '\n');
  console.log('fixture:', name);
};

const fail = (stage, r) => { console.error(`FAIL at ${stage}:`, JSON.stringify(redactEvidence(r)).slice(0, 400)); process.exit(1); };

const secret = (obj) => JSON.parse(JSON.stringify(obj, (k, v) =>
  (k === 'accessToken' || k === 'refreshToken') ? '<redacted-in-evidence; real value used live>' : v));

// 1) logins
const logins = {};
for (const role of ['host', 'guest']) {
  const r = await gql(null, LOGIN, { input: CREDS[role] });
  if (r.body.errors) fail('login ' + role, r);
  logins[role] = { token: r.body.data.login.accessToken, user: r.body.data.login.user, raw: r.body };
}
save('01-login-response.json', { kind: 'login', httpStatus: 200, raw: secret(logins.host.raw) });

// Scoped cleanup of the room created by THIS script run (failed runs too):
// validate host ownership via game(id) before abortGame; never touch any
// other room.
async function abortThisRunsGame(gameId) {
  if (!gameId) { console.log('cleanup: no game created by this run - nothing to abort'); return; }
  try {
    const g = await gql(logins.host.token, GAME, { id: gameId });
    const game = g.body.data?.game;
    if (!game) { console.log('cleanup: game', gameId, 'no longer resolves - nothing to abort'); return; }
    if (game.hostId !== logins.host.user.id) {
      console.error('cleanup: REFUSING abort - host-ownership validation failed for', gameId);
      return;
    }
    if (['ABORTED', 'COMPLETED', 'FINISHED'].includes(game.status)) {
      console.log('cleanup: game', gameId, 'already terminal (' + game.status + ')');
      return;
    }
    const r = await gql(logins.host.token, ABORT, { gameId });
    if (r.body.errors) { console.error('cleanup: abortGame failed:', r.body.errors[0]?.message); return; }
    console.log('cleanup: aborted THIS run\'s game', r.body.data.abortGame.id, 'status', r.body.data.abortGame.status);
  } catch (e) {
    console.error('cleanup: FAILED to abort this run\'s game', gameId, ':', e.message);
  }
}

let game = null;
try {
  // 2) host creates a private room with a stable idempotency key; duplicate
  //    create with the SAME key must return the same room (no second room).
  //    Hitting the active-game cap FAILS the run (no purge of other rooms).
  const key = `fixture-${Date.now()}`;
  const created = await gql(logins.host.token, CREATE, { input: { mode: 'ONE_V_ONE' }, key });
  if (created.body.errors) {
    const msg = created.body.errors[0]?.message ?? '';
    if (/active games|Maximum allowed/i.test(msg)) {
      console.error(`FAIL at create: active-game cap reached for fixture account (${msg}). ` +
        'This script only aborts rooms IT created; clean stale fixture rooms manually.');
      process.exit(1);
    }
    fail('create', created);
  }
  const duplicate = await gql(logins.host.token, CREATE, { input: { mode: 'ONE_V_ONE' }, key });
  if (duplicate.body.errors) fail('duplicate create', duplicate);
  if (duplicate.body.data.createGame.id !== created.body.data.createGame.id) {
    fail('idempotency', { first: created.body.data.createGame.id, second: duplicate.body.data.createGame.id });
  }
  game = created.body.data.createGame;
  console.log('room', game.id, 'code <redacted>', '(duplicate create idempotent: ok)');
  save('02-create-duplicate-idempotent.json', {
    kind: 'idempotency', httpStatus: 200, firstCreate: created.body, secondCreate: duplicate.body,
    sameId: duplicate.body.data.createGame.id === created.body.data.createGame.id,
  });

  // 3) guest resolves code -> gameId and joins
  const byCode = await gql(logins.guest.token, BY_CODE, { code: game.code });
  if (byCode.body.errors || !byCode.body.data.gameByCode) fail('gameByCode', byCode);
  const joined = await gql(logins.guest.token, JOIN, { input: { gameId: byCode.body.data.gameByCode.id } });
  if (joined.body.errors) fail('join', joined);
  save('03-game-by-code-resolve.json', { kind: 'code-lookup', httpStatus: 200, raw: byCode.body });

  // 4) hero pick + ready (prisma cuid ids — selectHero validates against the DB,
  //    while content `heroes` serves scraped slug ids from static files)
  const heroList = await gql(logins.host.token, `query HL { heroList(limit: 200) { items { id name } } }`, {});
  const items = heroList.body.data.heroList.items;
  const pick = (name) => items.find(h => h.name === name) ?? items.find(h => h.nameEn === name);
  const heroA = pick('Medusa') ?? items[0];
  const heroB = pick('King Arthur') ?? items[1];
  const selA = await gql(logins.host.token, SELECT, { gameId: game.id, heroId: heroA.id });
  if (selA.body.errors) fail('select A', selA);
  const selB = await gql(logins.guest.token, SELECT, { gameId: game.id, heroId: heroB.id });
  if (selB.body.errors) fail('select B', selB);
  await gql(logins.host.token, READY, { gameId: game.id });
  await gql(logins.guest.token, READY, { gameId: game.id });

  // 5) host starts
  const started = await gql(logins.host.token, START, { gameId: game.id });
  if (started.body.errors) fail('start', started);

  // 6) HTTP gameState snapshots per viewer (two-stage JSON-string state)
  const [stateHost, stateGuest] = await Promise.all([
    gql(logins.host.token, STATE, { gameId: game.id }),
    gql(logins.guest.token, STATE, { gameId: game.id }),
  ]);
  if (stateHost.body.errors) fail('state host', stateHost);
  if (stateGuest.body.errors) fail('state guest', stateGuest);
  save('04-game-state-query-host.json', { kind: 'gameState-query', httpStatus: 200, raw: stateHost.body });
  save('05-game-state-query-guest.json', { kind: 'gameState-query', httpStatus: 200, raw: stateGuest.body });

  // 7) reordered/partial derived from the real snapshot: keys shuffled,
  //    discardPiles/metadata omitted from the inner state (legal partial).
  const reorder = (obj) => {
    const keys = Object.keys(obj).reverse();
    return Object.fromEntries(keys.map(k => [k, obj[k]]));
  };
  const partial = JSON.parse(JSON.stringify(stateHost.body));
  partial.data.gameState = reorder(partial.data.gameState);
  const inner = JSON.parse(partial.data.gameState.state);
  delete inner.discardPiles;
  delete inner.metadata;
  partial.data.gameState.state = JSON.stringify(reorder(inner));
  save('06-game-state-query-reordered-partial.json', { kind: 'gameState-query', httpStatus: 200, raw: partial });

  // 8) WS: real graphql-transport-ws next payload (barrier snapshot, since null)
  const wsMessage = await new Promise((resolvePromise, rejectPromise) => {
    const client = createClient({
      url: WS_URL,
      webSocketImpl: WebSocket,
      connectionParams: () => ({ authorization: `Bearer ${logins.guest.token}` }),
      retryAttempts: 0,
    });
    const timer = setTimeout(() => rejectPromise(new Error('WS barrier snapshot timeout')), 10000);
    client.subscribe({ query: SUB_STATE, variables: { gameId: game.id } }, {
      next: (data) => { clearTimeout(timer); client.dispose(); resolvePromise(data); },
      error: (e) => { clearTimeout(timer); rejectPromise(e); },
      complete: () => {},
    });
  });
  save('07-ws-game-state-updated-next.json', { kind: 'ws-next', raw: wsMessage });

  // 9) auth failure: real server rejection with a tampered token (HTTP 200 + errors[])
  const authFail = await gql('not-a-real-token', STATE, { gameId: game.id });
  save('08-auth-failure-errors.json', { kind: 'auth-failure', httpStatus: authFail.status, raw: authFail.body });

  // 10) protocol failure: unknown field on the subscription protocol level is
  //     covered by UE tests; here we record a server-side validation error shape.
  const wrongQuery = await gql(logins.host.token, `query X { gameState(gameId: "no-such-game") { id } }`, {});
  save('09-not-found-errors.json', { kind: 'graphql-error', httpStatus: wrongQuery.status, raw: wrongQuery.body });

  // 11) client-resilience synthetics derived from the real snapshot
  const wrongScalar = JSON.parse(JSON.stringify(stateHost.body));
  const asObject = JSON.parse(wrongScalar.data.gameState.state);
  wrongScalar.data.gameState.state = asObject; // wrong scalar: object instead of JSON string
  save('10-wrong-scalar-state-object.json', { kind: 'wrong-scalar', httpStatus: 200, raw: wrongScalar });

  // Deliberately crash-shaped truncation: the cut lands wherever byte 120
  // falls - including inside an escape sequence (trailing backslash, partial
  // \uXX) or mid-string. These exact shapes made UE 5.8's TJsonReader read
  // past its buffer and fatally crash; they are REGRESSION INPUTS, kept on
  // purpose. The client must reject them with a PARSE error via the
  // bounds-checked pre-scan (FS08Contracts::ValidateJsonText) BEFORE UE's
  // reader ever sees the text. Do not "sanitize" the cut to an escape-safe
  // boundary - that would delete the regression.
  const truncated = JSON.stringify(stateHost.body).slice(0, 120);
  save('11-malformed-truncated.json', { kind: 'malformed', httpStatus: 200, raw: truncated });

  console.log('DONE — fixtures captured from', HTTP_URL);
} finally {
  await abortThisRunsGame(game?.id);
}

// GD-035: capture REAL viewer-projected snapshots for EVERY pending-effect
// type of the starter-card matrix (Medusa + King Arthur) against the
// worktree-local backend (:3120). One driven duel; when a target card shows
// up in the owner's hand it is played as a scheme/attack/defense and both
// seats' gameState projections are frozen at the pending pause.
// Fixtures: { name, capturedAt, note, raw: <exact HTTP body> } (S08 shape).
// Credentials come from backend/.env (S09_DEMO_*) - never argv, never printed.
// CHOOSE_ONE has no starter card (27-record matrix, evidence/S06) - it is NOT
// captured here; the UE test synthesizes that head from the server model.
// 2026-09-27 gap-closing pass: DISCARD_CARDS captured live via the HOST's
// Harpy attacking with 'Clutching Claws' (VERSATILE, banner Harpy; printed
// OPPONENT_DISCARD without 'random' -> pending owned by the DEFENDER =
// joiner). The earlier Hiss-and-Slither defense path needed Hiss to coincide
// with a joiner attack window and never landed in bounded runs. PLACE is
// captured live via the Winged Frenzy revive path, BOOST_CHOICE via Second
// Shot, CHOOSE_SPACE stage 2 live after the zone backfill + stage-2 seq fix.
//
// 2026-09-27: the earlier missing-effectAfter blocker is fixed in
// GameInitializationService.resolveCardEffects. The dual-path driver below
// captures the real pending head and its successful resolution.
const fs = require('fs');
const path = require('path');
console.log('CAPTURE SCRIPT BUILD: v20-discard-live');

let DISCARD_FAIL_DUMPED = false;
async function discardToLimitCall(actor, gameId, input) {
  const body = await gqlRaw(
    `mutation D($input: DiscardToLimitDto!) { discardToLimit(input: $input) { sequenceNumber } }`,
    { input }, actor.token);
  const j = JSON.parse(body);
  if (j.errors?.length && !DISCARD_FAIL_DUMPED) {
    DISCARD_FAIL_DUMPED = true;
    console.log('FIRST DISCARD REJECTION - input: ' + JSON.stringify(input));
    console.log('FIRST DISCARD REJECTION - response: ' + body.slice(0, 2500));
  }
  return j;
}

const HTTP = 'http://localhost:3120/graphql';
const FIXTURE_DIR = path.resolve(__dirname, '..', '..', 'docs', 'game-design', 'evidence', 'S09', 'fixtures');

const envPath = path.resolve(__dirname, '..', '..', 'backend', '.env');
for (const line of fs.readFileSync(envPath, 'utf8').split(/\r?\n/)) {
  const m = line.match(/^([A-Z0-9_]+)=(.*)$/);
  if (m && !process.env[m[1]]) process.env[m[1]] = m[2];
}
const HOST = { email: process.env.S09_DEMO_HOST_EMAIL, password: process.env.S09_DEMO_HOST_PASSWORD };
const JOINER = { email: process.env.S09_DEMO_JOINER_EMAIL, password: process.env.S09_DEMO_JOINER_PASSWORD };
if (!HOST.email || !JOINER.email) throw new Error('S09_DEMO_* credentials missing in backend/.env');

async function gqlRaw(query, variables, token) {
  const r = await fetch(HTTP, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ query, variables }),
  });
  return await r.text();
}
async function gql(query, variables, token) {
  const text = await gqlRaw(query, variables, token);
  const j = JSON.parse(text);
  if (j.errors?.length) { const e = new Error(j.errors.map((x) => x.message).join('; ')); e.body = text; throw e; }
  return j.data;
}
const alive = (f) => f.health > 0 && !f.isDefeated;

async function login(account) {
  const d = await gql(`mutation L($input: LoginDto!) { login(input: $input) { accessToken user { id } } }`,
    { input: { email: account.email, password: account.password } });
  return { token: d.login.accessToken, id: d.login.user.id };
}
async function cleanupMine(token) {
  const mine = await gql(`query { myGames { id status } }`, {}, token);
  for (const g of mine.myGames.filter((g) => ['LOBBY', 'IN_PROGRESS', 'PENDING'].includes(g.status))) {
    await gql(`mutation AB($id: String!) { abortGame(gameId: $id) { id } }`, { id: g.id }, token).catch(() => {});
  }
}
async function heroByName(token, name) {
  const d = await gql(`query HL($limit: Int) { heroList(limit: $limit) { items { id name } } }`, { limit: 300 }, token);
  const hit = d.heroList.items.find((h) => h.name === name);
  if (!hit) throw new Error(`hero not found: ${name}`);
  return hit.id;
}

// ---- state helpers ---------------------------------------------------------
async function stateFor(token, gameId) {
  const d = await gql(`query GS($g: String!) { gameState(gameId: $g) { state } }`, { g: gameId }, token);
  return JSON.parse(d.gameState.state);
}
async function rawView(token, gameId) {
  return await gqlRaw(`query GS($g: String!) { gameState(gameId: $g) { id gameId state sequenceNumber phase turnCount currentTurnPlayerId updatedAt } }`, { g: gameId }, token);
}
const handOf = (state, userId) => state.handZones[userId]?.cards ?? [];
const headOf = (state) => state.metadata.pendingEffects?.[0] ?? null;
const isOver = (state) => state.phase === 'GAME_OVER';

// Movement BFS (orthogonal, impassable blocks, living enemies block transit,
// destination free of other living fighters); path WITHOUT the start cell.
function bfsStep(state, fighter, targets) {
  const W = state.boardState.width, H = state.boardState.height;
  const passable = (x, y) => {
    const c = state.boardState.cells?.[y]?.[x];
    if (!c) return false;
    if (c.type === 'WALL' || c.type === 'OBSTACLE') return false;
    if (c.type === 'DOOR' && c.isOpen === false) return false;
    return true;
  };
  const enemyCells = new Set(state.fighters.filter((f) => f.id !== fighter.id && alive(f) && f.ownerId !== fighter.ownerId)
    .map((f) => `${f.position.x},${f.position.y}`));
  const occupied = new Set(state.fighters.filter((f) => f.id !== fighter.id && alive(f))
    .map((f) => `${f.position.x},${f.position.y}`));
  const start = `${fighter.position.x},${fighter.position.y}`;
  const prev = new Map([[start, null]]);
  const queue = [start];
  const targetSet = new Set(targets.map((t) => `${t.x},${t.y}`));
  let found = null;
  while (queue.length && !found) {
    const cur = queue.shift();
    const [cx, cy] = cur.split(',').map(Number);
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const nx = cx + dx, ny = cy + dy;
      const key = `${nx},${ny}`;
      if (nx < 0 || ny < 0 || nx >= W || ny >= H || prev.has(key)) continue;
      if (!passable(nx, ny) || enemyCells.has(key)) continue;
      prev.set(key, cur);
      if (targetSet.has(key) && !occupied.has(key)) { found = key; break; }
      queue.push(key);
    }
  }
  if (!found) return null;
  const path = [];
  let cur = found;
  while (cur !== start) { const [x, y] = cur.split(',').map(Number); path.unshift({ x, y }); cur = prev.get(cur); }
  return path;
}
function cellsAdjacentToEnemies(state, ownerId, targetName = null) {
  const out = [];
  const foes = state.fighters.filter((f) => alive(f) && f.ownerId !== ownerId &&
    (!targetName || f.name.toLowerCase().includes(targetName.toLowerCase())));
  for (const e of foes) {
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      out.push({ x: e.position.x + dx, y: e.position.y + dy });
    }
  }
  return out;
}

function saveFixture(name, note, rawBody) {
  const file = path.join(FIXTURE_DIR, `${name}.json`);
  fs.writeFileSync(file, JSON.stringify({ name, capturedAt: new Date().toISOString(), note, raw: rawBody }, null, 1));
  console.log(`fixture: ${name} (${rawBody.length} bytes)`);
}

// ---- pending resolvers (drive the queue forward between captures) ---------
async function resolvePending(token, gameId, state, pick) {
  const head = headOf(state);
  if (!head) throw new Error('resolvePending: queue empty');
  const input = { gameId, effectId: head.id };
  if (pick.fighterId) input.fighterId = pick.fighterId;
  if (pick.x !== undefined) { input.x = pick.x; input.y = pick.y; }
  if (pick.optionIndex !== undefined) input.optionIndex = pick.optionIndex;
  if (pick.cardIds) input.cardIds = pick.cardIds;
  const body = await gqlRaw(
    `mutation R($input: ResolvePendingEffectDto!) { resolvePendingEffect(input: $input) { state sequenceNumber phase } }`,
    { input }, token);
  const j = JSON.parse(body);
  if (j.errors?.length) throw new Error(`resolvePendingEffect(${head.type}) failed: ${j.errors[0].message}`);
  return JSON.parse(j.data.resolvePendingEffect.state);
}

// ---- generic turn drivers --------------------------------------------------
async function passTurn(actor, gameId) {
  // Burn both actions with zero-move maneuvers, then end the turn. Handles
  // TURN_END discard when it opens. Returns the fresh state.
  let state = await stateFor(actor.token, gameId);
  let discardFails = 0;
  for (let guard = 0; guard < 12; guard++) {
    const me = state.currentTurnPlayerId === actor.id;
    if (!me) return state;
    if (state.metadata.pendingEffects?.length) {
      // Auto-resolve ANY pending deterministically (first legal choice) so
      // the duel never stalls between captures.
      const head = headOf(state);
      const owner = head.playerId === HOST_SIDE.id ? HOST_SIDE : JOINER_SIDE;
      state = await autoResolve(owner, gameId, state);
      continue;
    }
    if (state.metadata.pendingHandDiscard) {
      const pending = state.metadata.pendingHandDiscard;
      if (pending.playerId === actor.id) {
        // Keep the capture-critical cards in hand: hand-limit discards used
        // to slice the front of the hand and could permanently bury the only
        // producers (Hiss and Slither / Clutching Claws / Bewilderment /
        // Second Shot / Winged Frenzy / Restless Spirits), starving the
        // later blocks (discarded cards never return - the deck exhausts
        // instead of reshuffling).
        // Dedupe the ranked pick, not the server hand. The old script's
        // overlapping priority groups sent one id twice; the live hand was
        // unique (confirmed by S09 card-instance invariant tests). The DTO
        // requires distinct ids or discardToLimit rejects the whole choice.
        const precious = new Set(['Hiss and Slither', 'Clutching Claws', 'Bewilderment', 'Second Shot', 'Winged Frenzy', 'Restless Spirits']);
        const pool = [];
        {
          const seen = new Set();
          for (const c of handOf(state, actor.id)) {
            if (seen.has(c.id)) continue;
            seen.add(c.id);
            pool.push(c);
          }
        }
        const rankedSac = [
          ...pool.filter((c) => !precious.has(c.name) && c.cardType !== 'ATTACK' && c.cardType !== 'VERSATILE'),
          ...pool.filter((c) => !precious.has(c.name)),
          ...pool.filter((c) => precious.has(c.name)),
        ];
        // The priority groups overlap; dedupe again before slicing so a
        // non-combat card cannot be sent twice in one DTO.
        const ids = [...new Set(rankedSac.map((c) => c.id))].slice(0, pending.count);
        if (ids.length) {
          if (!globalThis.DEDUPE_MARKED) {
            globalThis.DEDUPE_MARKED = true;
            console.log(`DEDUPE ACTIVE: raw hand ${handOf(state, actor.id).length} -> pool ${pool.length}, ids ${JSON.stringify(ids)}`);
          }
          const j = await discardToLimitCall(actor, gameId, { gameId, pendingId: pending.id, cardIds: ids });
          if (j.errors?.length) {
            discardFails++;
            if (discardFails >= 3) {
              console.log(`passTurn: discardToLimit stuck (pending ${JSON.stringify(pending)}, phase ${state.phase}, hand ${pool.length}) - giving up this passTurn`);
              return state;
            }
          } else discardFails = 0;
        }
      }
      state = await stateFor(actor.token, gameId);
      continue;
    }
    if (state.phase === 'ACTION_MANEUVER' || state.phase === 'ACTION_ATTACK') {
      const begin = await gql(`mutation B($input: BeginManeuverDto!) { beginManeuver(input: $input) { state } }`,
        { input: { gameId, expectedSequenceNumber: state.sequenceNumber } }, actor.token);
      const after = JSON.parse(begin.beginManeuver.state);
      const pendingId = after.metadata.pendingManeuver?.id;
      if (!pendingId) {
        // Last action auto-advanced the turn (no open maneuver choice).
        state = after;
        continue;
      }
      await gql(`mutation M($input: ManeuverDto!) { maneuver(input: $input) { sequenceNumber } }`,
        { input: { gameId, maneuverId: pendingId, moves: [], boostCardId: null } }, actor.token);
      state = await stateFor(actor.token, gameId);
      continue;
    }
    if (state.phase === 'TURN_END' || (state.metadata.actionsRemaining ?? 2) === 0) {
      await gql(`mutation E($g: String!) { endTurn(gameId: $g) { id } }`, { g: gameId }, actor.token).catch(() => {});
      state = await stateFor(actor.token, gameId);
      continue;
    }
    break;
  }
  return state;
}

async function autoResolve(owner, gameId, state) {
  // Re-read the state from the HEAD OWNER's own projection: a viewer
  // projection hides the other seat's hand (count-only placeholders), so
  // card-pick answers (DISCARD/BOOST/DECK_TOP_PICK) built from a foreign
  // view would send hidden ids the server rejects.
  state = await stateFor(owner.token, gameId);
  const head = headOf(state);
  const t = head.type;
  if (t === 'MOVE' || t === 'PLACE') {
    const fid = (head.fighterIds ?? [])[0] ?? state.fighters.find((f) => alive(f))?.id;
    if (t === 'PLACE') {
      // PLACE never allows the fighter's own cell (occupied by itself):
      // first free passable cell, zone-restricted for revive heads
      // (zoneFighterName anchors the legal zone set).
      let zoneNames = null;
      if (head.zoneFighterName) {
        const anchor = state.fighters.find((f) =>
          f.name.toLowerCase().includes((head.zoneFighterName ?? '').toLowerCase()));
        zoneNames = state.boardState.cells?.[anchor?.position.y]?.[anchor?.position.x]?.zones ?? null;
      }
      for (let y = 0; y < state.boardState.height; y++) {
        for (let x = 0; x < state.boardState.width; x++) {
          const c = state.boardState.cells?.[y]?.[x];
          if (!c || c.type === 'WALL' || c.type === 'OBSTACLE') continue;
          if (c.type === 'DOOR' && c.isOpen === false) continue;
          if (state.fighters.some((f) => alive(f) && f.position.x === x && f.position.y === y)) continue;
          if (zoneNames && !(c.zones ?? []).some((z) => zoneNames.includes(z))) continue;
          return await resolvePending(owner.token, gameId, state, { fighterId: fid, x, y });
        }
      }
      if (head.optional) {
        await gqlRaw(`mutation DP($input: DeclinePendingEffectDto!) { declinePendingEffect(input: $input) { sequenceNumber } }`,
          { input: { gameId, effectId: head.id } }, owner.token);
        return await stateFor(owner.token, gameId);
      }
      throw new Error('autoResolve PLACE: no legal cell found');
    }
    const fighter = state.fighters.find((f) => f.id === fid);
    return await resolvePending(owner.token, gameId, state,
      { fighterId: fid, x: fighter.position.x, y: fighter.position.y });
  }
  if (t === 'CHOOSE_SPACE') {
    // stage 1: any cell in the zone of the named fighter; stage 2: adjacent.
    if (head.stage === 2) {
      // pick first passable orthogonal neighbour of the anchor
      for (const [dx, dy] of [[0, -1], [1, 0], [0, 1], [-1, 0]]) {
        const x = head.anchor.x + dx, y = head.anchor.y + dy;
        const c = state.boardState.cells?.[y]?.[x];
        if (!c || c.type === 'WALL' || c.type === 'OBSTACLE') continue;
        if (c.type === 'DOOR' && c.isOpen === false) continue;
        return await resolvePending(owner.token, gameId, state, { x, y });
      }
      throw new Error('CHOOSE_SPACE stage2: no passable neighbour');
    }
    const named = state.fighters.find((f) => f.name.toLowerCase().includes((head.zoneFighterName ?? '').toLowerCase()));
    if (!named) throw new Error('CHOOSE_SPACE stage1: zone anchor fighter not found');
    // Server zone rule: the cell's zones[] must intersect the anchor's
    // zones[] (cells without zones never qualify - even the anchor's own).
    const anchorZones = state.boardState.cells?.[named.position.y]?.[named.position.x]?.zones ?? [];
    for (let y = 0; y < state.boardState.height; y++) {
      for (let x = 0; x < state.boardState.width; x++) {
        const c = state.boardState.cells?.[y]?.[x];
        if (!c || c.type === 'WALL' || c.type === 'OBSTACLE') continue;
        if (c.type === 'DOOR' && c.isOpen === false) continue;
        if ((c.zones ?? []).some((z) => anchorZones.includes(z))) {
          return await resolvePending(owner.token, gameId, state, { x, y });
        }
      }
    }
    throw new Error('CHOOSE_SPACE stage1: no cell shares the anchor zone');
  }
  if (t === 'TARGET_FIGHTER') {
    const fid = (head.targetFighterIds ?? state.fighters.filter(alive).map((f) => f.id))[0];
    return await resolvePending(owner.token, gameId, state, { fighterId: fid });
  }
  if (t === 'CHOOSE_ONE') {
    return await resolvePending(owner.token, gameId, state, { optionIndex: 0 });
  }
  if (t === 'DISCARD_CARDS') {
    const n = head.value ?? 1;
    // Deduped instance ids (live hands can carry the same id twice - see the
    // passTurn note; the DTO demands unique ids).
    const ids = [...new Set(handOf(state, head.playerId).map((c) => c.id))].slice(0, n);
    return await resolvePending(owner.token, gameId, state, { cardIds: ids });
  }
  if (t === 'BOOST_CHOICE') {
    const card = handOf(state, head.playerId)[0];
    if (head.optional && card) return await resolvePending(owner.token, gameId, state, { cardIds: [card.id] });
    await gqlRaw(`mutation DP($input: DeclinePendingEffectDto!) { declinePendingEffect(input: $input) { sequenceNumber } }`,
      { input: { gameId, effectId: head.id } }, owner.token);
    return await stateFor(owner.token, gameId);
  }
  if (t === 'DECK_TOP_PICK') {
    const revealed = [...new Set((head.revealedCards ?? []).map((c) => c.id))];
    if ((head.mode ?? 'PICK') === 'PICK') {
      const n = head.value ?? 2;
      return await resolvePending(owner.token, gameId, state, { cardIds: revealed.slice(0, n) });
    }
    return await resolvePending(owner.token, gameId, state, { cardIds: revealed });
  }
  throw new Error(`autoResolve: unsupported type ${t}`);
}

// Play a named card from the owner's hand as a scheme; waits (cycling turns)
// until it shows up. Returns { state, played } - played=false means the card
// never reached the hand within the cycle budget (soft callers report a gap).
async function playSchemeCard(owner, other, gameId, cardName, maxCycles, soft = false) {
  for (let i = 0; i < maxCycles; i++) {
    let state = await stateFor(owner.token, gameId);
    if (state.metadata.pendingEffects?.length) state = await passTurn(owner, gameId);
    state = await stateFor(owner.token, gameId);
    if (state.currentTurnPlayerId === owner.id &&
        (state.phase === 'ACTION_MANEUVER' || state.phase === 'ACTION_ATTACK')) {
      const card = handOf(state, owner.id).find((c) => c.name === cardName);
      if (card) {
        const body = await gqlRaw(
          `mutation P($input: PlaySchemeDto!) { playScheme(input: $input) { state sequenceNumber } }`,
          { input: { gameId, cardId: card.id } }, owner.token);
        const j = JSON.parse(body);
        if (j.errors?.length) throw new Error(`playScheme(${cardName}) failed: ${j.errors[0].message}`);
        return { state: JSON.parse(j.data.playScheme.state), raw: body, played: true };
      }
    }
    // Not our card turn yet: the current seat passes.
    const seat = state.currentTurnPlayerId === HOST_SIDE.id ? HOST_SIDE : JOINER_SIDE;
    await passTurn(seat, gameId);
  }
  if (soft) return { state: await stateFor(owner.token, gameId), played: false };
  throw new Error(`playSchemeCard: ${cardName} never appeared within ${maxCycles} cycles`);
}

// Approach phase: cycles turns until any own-enemy pair is orthogonally
// adjacent; the turn owner spends maneuvers walking the host hero toward the
// nearest enemy (BFS, movement-capped).
async function ensureAdjacency(host, gameId, maxIter = 80, targetName = null, walkerName = null) {
  for (let i = 0; i < maxIter; i++) {
    const state = await stateFor(host.token, gameId);
    if (state.metadata.pendingEffects?.length) { await autoResolve(
      headOf(state).playerId === HOST_SIDE.id ? HOST_SIDE : JOINER_SIDE, gameId, state); continue; }
    const adjacent = state.fighters.some((a) => alive(a) && state.fighters.some((b) =>
      alive(b) && b.ownerId !== a.ownerId &&
      (!targetName || b.name.toLowerCase().includes(targetName.toLowerCase())) &&
      (!walkerName || a.name.toLowerCase().includes(walkerName.toLowerCase())) &&
      Math.abs(a.position.x - b.position.x) + Math.abs(a.position.y - b.position.y) === 1));
    if (adjacent) return true;
    const seat = state.currentTurnPlayerId === HOST_SIDE.id ? HOST_SIDE : JOINER_SIDE;
    if (seat.id !== host.id || state.phase !== 'ACTION_MANEUVER') { await passTurn(seat, gameId); continue; }
    const s2 = await stateFor(host.token, gameId);
    const hero = s2.fighters.find((f) => f.ownerId === host.id && alive(f) &&
      (!walkerName || f.name.toLowerCase().includes(walkerName.toLowerCase())));
    if (!hero) return false;
    const begin = await gql(`mutation B($input: BeginManeuverDto!) { beginManeuver(input: $input) { state } }`,
      { input: { gameId, expectedSequenceNumber: s2.sequenceNumber } }, host.token);
    const after = JSON.parse(begin.beginManeuver.state);
    const pendingId = after.metadata.pendingManeuver?.id;
    if (!pendingId) continue; // no open maneuver choice: loop re-evaluates the phase
    const heroAfter = after.fighters.find((f) => f.id === hero.id);
    const path = bfsStep(after, heroAfter, cellsAdjacentToEnemies(after, host.id, targetName)) || [];
    const trimmed = path.slice(0, heroAfter.movement);
    await gql(`mutation M($input: ManeuverDto!) { maneuver(input: $input) { sequenceNumber } }`,
      { input: { gameId, maneuverId: pendingId, moves: trimmed.length ? [{ fighterId: hero.id, path: trimmed }] : [], boostCardId: null } }, host.token);
  }
  return false;
}

let HOST_SIDE, JOINER_SIDE;

async function startDuel(host, joiner, heroA, heroB) {
  const game = (await gql(`mutation C { createGame(input: { mode: ONE_V_ONE }) { id code } }`, {}, host.token)).createGame;
  const gameId = game.id;
  await gql(`mutation J($input: JoinGameDto!) { joinGame(input: $input) { id } }`, { input: { gameId } }, joiner.token);
  await gql(`mutation S($g: String!, $h: String!) { selectHero(gameId: $g, heroId: $h) { id } }`, { g: gameId, h: heroA }, host.token);
  await gql(`mutation S($g: String!, $h: String!) { selectHero(gameId: $g, heroId: $h) { id } }`, { g: gameId, h: heroB }, joiner.token);
  await gql(`mutation R($g: String!) { toggleReady(gameId: $g) { id } }`, { g: gameId }, host.token);
  await gql(`mutation R($g: String!) { toggleReady(gameId: $g) { id } }`, { g: gameId }, joiner.token);
  await gql(`mutation St($g: String!) { startGame(gameId: $g) { id status } }`, { g: gameId }, host.token);
  console.log(`game started: ${gameId}`);
  return gameId;
}

async function main() {
  const host = await login(HOST);
  const joiner = await login(JOINER);
  HOST_SIDE = host; JOINER_SIDE = joiner;
  await cleanupMine(host.token);
  await cleanupMine(joiner.token);

  const heroA = await heroByName(host.token, 'Medusa');
  const heroB = await heroByName(joiner.token, 'King Arthur');
  let gameId = await startDuel(host, joiner, heroA, heroB);
  // HP trail: any unexpected damage source between blocks shows here.
  const hpTrail = async (label) => {
    const s = await stateFor(host.token, gameId);
    console.log(`hp ${label}: ` + s.fighters.map((f) => `${f.name}:${f.health}${f.isDefeated ? 'X' : ''}`).join(' '));
  };
  try {
    // ---- 1+2. MOVE: Medusa 'Winged Frenzy' scheme (per-fighter queue) ----
    // playScheme takes real SCHEME cards only (VERSATILE 'Dash' is rejected
    // server-side), so the MOVE fixture is the Winged Frenzy queue: head is
    // a single-fighter MOVE, the tail proves queue/stale-head semantics.
    {
      const { state } = await playSchemeCard(host, joiner, gameId, 'Winged Frenzy', 120);
      const head = headOf(state);
      if (head?.type !== 'MOVE') throw new Error(`Winged Frenzy produced ${head?.type}, expected MOVE queue`);
      const q = state.metadata.pendingEffects;
      saveFixture('gd035-move-open-host-view',
        `viewer-projected gameState at a MOVE pending (OWNER seat; Winged Frenzy queue length ${q.length}, head is the actionable choice)`, await rawView(host.token, gameId));
      saveFixture('gd035-move-open-joiner-view',
        'viewer-projected gameState at a MOVE pending (OPPONENT seat; queue visible, no private faces)', await rawView(joiner.token, gameId));
      saveFixture('gd035-move-queue-host-view',
        `viewer-projected gameState at the MULTI-entry MOVE queue (owner seat; entries after the head are NOT actionable)`, await rawView(host.token, gameId));
      let s = state;
      while (headOf(s)) s = await autoResolve(host, gameId, s);
    }

    // HP trail: any unexpected damage source between blocks shows here.
    await hpTrail('after-move');
    // DECK_TOP_PICK (Prophecy) and TARGET_FIGHTER (A Momentary Glance)
    // blocks REMOVED from this game: turn cycling drains decks (every
    // maneuver draws; a missing draw = 2 exhaustion damage to ALL own
    // living fighters - deck-management drawCards), and both fixture sets
    // are already captured (deckpick/deckorder refreshed + CHOOSE_SPACE
    // stage1/2 captured in the 2026-09-27 runs; TARGET_FIGHTER is proven
    // live by packaged run 100210). GAME A is MOVE-only; the combat-gated
    // DISCARD_CARDS capture runs in its OWN fresh duel below (deck
    // exhaustion + producer burn make late-game hunts unreliable).
    console.log('game A complete');
  } finally {
    await gql(`mutation AB($id: String!) { abortGame(gameId: $id) { id } }`, { id: gameId }, host.token).catch(() => {});
    console.log(`game aborted: ${gameId}`);
  }

  // ---- GAME A-D: DISCARD_CARDS in a fresh duel. Both producers are Medusa
  // (host) cards with printed non-random OPPONENT_DISCARD; either way the
  // discarder is the JOINER (card-effect-executor resolves OPPONENT_DISCARD
  // to a DISCARD_CARDS pending owned by the effect owner's OPPONENT), who
  // picks from their OWN hand while the combat chain pauses:
  //   PATH 1: the HOST's Harpy attacks an adjacent joiner fighter with
  //   'Clutching Claws' (VERSATILE, banner Harpy).
  //   PATH 2: the JOINER attacks any adjacent host fighter and the HOST
  //   defends with 'Hiss and Slither' (DEFENSE; validateDefense checks only
  //   the card type, not the banner). PATH 2 needs no host hand luck beyond
  //   Hiss itself, so it is tried first whenever the joiner owns the turn.
  // Both producers are draw-gated in a single duel (a buried producer never
  // surfaces once the deck exhausts), so the DISCARD duel retries with FRESH
  // decks until either path lands (bounded to 6 duels).
  let discarded = false;
  for (let duelIdx = 0; duelIdx < 6 && !discarded; duelIdx++) {
    if (duelIdx > 0) console.log(`DISCARD duel retry #${duelIdx} (fresh decks)`);
    gameId = await startDuel(host, joiner, heroA, heroB);
    try {
      await ensureAdjacency(host, gameId);
      await hpTrail('after-approach');
      const tryCaptureDiscard = async () => {
        let state = await stateFor(host.token, gameId);
        for (let guard = 0; guard < 8; guard++) {
          const head = headOf(state);
          if (!head) break;
          if (head.type === 'DISCARD_CARDS' && !discarded) {
            if (head.playerId !== joiner.id) throw new Error(`DISCARD_CARDS owner mismatch (expected joiner=discarder, got ${head.playerId})`);
            saveFixture('gd035-discard-owner-joiner-view',
              `viewer-projected gameState at DISCARD_CARDS pending (CHOICE OWNER = the discarder seat; exact own hand instance ids, value=${head.value}; opened by a Medusa OPPONENT_DISCARD producer)`, await rawView(joiner.token, gameId));
            saveFixture('gd035-discard-wait-host-view',
              'viewer-projected gameState at the OPPONENT-owned DISCARD_CARDS head (wait seat = the effect owner; queue head blocks actions, own hand exact, opponent hand hidden)', await rawView(host.token, gameId));
            // Successful-resolution proof (GD-034 resolve-echo pattern): the
            // OWNER seat resolves the head from their OWN projection; the raw
            // mutation response is the fixture. Saved even on GraphQL error -
            // the honest failure mode is a fixture with an errors array.
            {
              const ownView = await stateFor(joiner.token, gameId);
              const ids = [...new Set(handOf(ownView, joiner.id).map((c) => c.id))].slice(0, head.value ?? 1);
              const echo = await gqlRaw(
                `mutation R($input: ResolvePendingEffectDto!) { resolvePendingEffect(input: $input) { state sequenceNumber phase } }`,
                { input: { gameId, effectId: head.id, cardIds: ids } }, joiner.token);
              saveFixture('gd035-discard-resolve-echo',
                `raw resolvePendingEffect response closing the DISCARD_CARDS head (owner=discarder seat picks ${ids.length} card(s) from their own projected hand; success = errors absent, queue advances)`, echo);
              const resolved = JSON.parse(echo);
              if (resolved.errors?.length || !resolved.data?.resolvePendingEffect?.state) {
                throw new Error(`DISCARD_CARDS resolve failed: ${resolved.errors?.[0]?.message ?? 'missing state'}`);
              }
              const next = JSON.parse(resolved.data.resolvePendingEffect.state);
              if (headOf(next)?.id === head.id) {
                throw new Error('DISCARD_CARDS head remained open after resolution');
              }
            }
            discarded = true;
            return; // the captured head was consumed; do not auto-resolve it again
          }
          state = await autoResolve(headOf(state).playerId === HOST_SIDE.id ? HOST_SIDE : JOINER_SIDE, gameId, state);
        }
      };
      for (let attempt = 0; attempt < 24 && !discarded; attempt++) {
        let state = await stateFor(host.token, gameId);
        if (isOver(state)) { console.log('note: game over before DISCARD_CARDS window'); break; }
        while (headOf(state)) state = await autoResolve(
          headOf(state).playerId === HOST_SIDE.id ? HOST_SIDE : JOINER_SIDE, gameId, state);
        const hiss = handOf(state, host.id).find((c) => c.name === 'Hiss and Slither');
        const claw = handOf(state, host.id).find((c) => c.name === 'Clutching Claws');
        const inAction = state.phase === 'ACTION_MANEUVER' || state.phase === 'ACTION_ATTACK';
        // PATH 2 FIRST and BEFORE any ensureAdjacency call: ensureAdjacency
        // burns the CURRENT seat's whole turn when it is not the host's, so
        // running it at the loop head used to consume every joiner ACTION
        // window before PATH 2 could see it (Hiss never coincided).
        if (hiss && state.currentTurnPlayerId === joiner.id && inAction) {
          // Joiner's own projection (the host view hides the joiner hand).
          const joinerState = await stateFor(joiner.token, gameId);
          let pair = null;
          for (const f of joinerState.fighters.filter((x) => alive(x) && x.ownerId === joiner.id)) {
            const target = joinerState.fighters.find((e) => alive(e) && e.ownerId === host.id &&
              Math.abs(f.position.x - e.position.x) + Math.abs(f.position.y - e.position.y) === 1);
            if (target) { pair = { attacker: f, target }; break; }
          }
          const atk = pair && handOf(joinerState, joiner.id).find((c) =>
            (c.cardType === 'ATTACK' || c.cardType === 'VERSATILE') &&
            (c.bannerName === 'Any' || pair.attacker.name.includes(c.bannerName ?? 'Any')));
          if (!pair || !atk) {
            console.log(`attempt ${attempt}: hiss-path setup miss (pair=${pair ? 'yes' : 'no'}, atk=${atk ? 'yes' : 'no'})`);
            await passTurn(joiner, gameId);
            continue;
          }
          const body = await gqlRaw(
            `mutation A($input: AttackDto!) { attack(input: $input) { state sequenceNumber phase } }`,
            { input: { gameId, attackerId: pair.attacker.id, cardId: atk.id, targetId: pair.target.id } }, joiner.token);
          const j = JSON.parse(body);
          if (j.errors?.length) {
            console.log(`attempt ${attempt}: hiss-path attack failed: ${j.errors[0].message.slice(0, 120)}`);
            await passTurn(joiner, gameId);
            continue;
          }
          if (JSON.parse(j.data.attack.state).phase === 'COMBAT') {
            const dBody = await gqlRaw(`mutation PD($input: PlayDefenseDto!) { playDefense(input: $input) { sequenceNumber } }`,
              { input: { gameId, cardId: hiss.id } }, host.token);
            const d = JSON.parse(dBody);
            if (d.errors?.length) {
              console.log(`attempt ${attempt}: Hiss defense rejected: ${d.errors[0].message.slice(0, 120)}`);
              await passTurn(joiner, gameId);
              continue;
            }
          }
          // Defender = host closes a COMBAT window; either seat a RESOLVE one.
          const midState = await stateFor(host.token, gameId);
          if (midState.phase === 'COMBAT' || midState.phase === 'COMBAT_RESOLVE') {
            const resolver = midState.phase === 'COMBAT' ? host : joiner;
            const rcBody = await gqlRaw(`mutation RC($g: String!) { resolveCombat(input: { gameId: $g }) { sequenceNumber phase } }`, { g: gameId }, resolver.token)
              .catch((e) => { console.log(`attempt ${attempt}: resolveCombat transport error: ${String(e.message ?? e).slice(0, 120)}`); return null; });
            if (rcBody) {
              const rc = JSON.parse(rcBody);
              if (rc.errors?.length) console.log(`attempt ${attempt}: resolveCombat rejected: ${rc.errors[0].message.slice(0, 140)}`);
            }
          }
          await tryCaptureDiscard();
          continue;
        }
        // Not a PATH 2 window: burn the seat's turn (no ensureAdjacency here -
        // it would consume joiner ACTION windows PATH 2 still needs).
        if (state.currentTurnPlayerId !== host.id || !inAction) {
          await passTurn(state.currentTurnPlayerId === HOST_SIDE.id ? HOST_SIDE : JOINER_SIDE, gameId);
          continue;
        }
        // Host's turn: walk a Harpy next to a joiner fighter, then the claw.
        if (claw) await ensureAdjacency(host, gameId, 12, null, 'Harpies');
        state = await stateFor(host.token, gameId);
        const clawNow = handOf(state, host.id).find((c) => c.name === 'Clutching Claws');
        const harpy = clawNow && state.fighters.find((f) => f.ownerId === host.id && f.name.includes('Harpies') && alive(f) &&
          state.fighters.some((e) => alive(e) && e.ownerId === joiner.id &&
            Math.abs(f.position.x - e.position.x) + Math.abs(f.position.y - e.position.y) === 1));
        if (!harpy) {
          console.log(`attempt ${attempt}: waiting (claw=${clawNow ? 'yes' : 'no'}, hiss=${hiss ? 'yes' : 'no'}, turn=${state.currentTurnPlayerId === host.id ? 'host' : 'joiner'})`);
          await passTurn(host, gameId);
          continue;
        }
        const target = state.fighters.find((e) => alive(e) && e.ownerId === joiner.id &&
          Math.abs(harpy.position.x - e.position.x) + Math.abs(harpy.position.y - e.position.y) === 1);
        const body = await gqlRaw(
          `mutation A($input: AttackDto!) { attack(input: $input) { state sequenceNumber phase } }`,
          { input: { gameId, attackerId: harpy.id, cardId: clawNow.id, targetId: target.id } }, host.token);
        const j = JSON.parse(body);
        if (j.errors?.length) { console.log(`attempt ${attempt}: attack failed: ${j.errors[0].message.slice(0, 120)}`); await passTurn(host, gameId); continue; }
        // NO defense from the joiner: the undefended attack still carries the
        // card effects into the post-combat chain. In COMBAT only the DEFENDER
        // may close the window (no-defense); in COMBAT_RESOLVE either seat.
        const midState = await stateFor(host.token, gameId);
        if (midState.phase === 'COMBAT' || midState.phase === 'COMBAT_RESOLVE') {
          const resolver = midState.phase === 'COMBAT' ? joiner : host;
          const rcBody = await gqlRaw(`mutation RC($g: String!) { resolveCombat(input: { gameId: $g }) { sequenceNumber phase } }`, { g: gameId }, resolver.token)
            .catch((e) => { console.log(`attempt ${attempt}: resolveCombat transport error: ${String(e.message ?? e).slice(0, 120)}`); return null; });
          if (rcBody) {
            const rc = JSON.parse(rcBody);
            if (rc.errors?.length) console.log(`attempt ${attempt}: resolveCombat rejected: ${rc.errors[0].message.slice(0, 140)}`);
          }
        }
        await tryCaptureDiscard();
      }
      if (!discarded) console.log('note: DISCARD_CARDS head never opened in this duel (neither the Clutching Claws attack nor a Hiss-and-Slither defense landed)');
      await hpTrail('after-discard');
      console.log('game A-D complete');
    } finally {
      await gql(`mutation AB($id: String!) { abortGame(gameId: $id) { id } }`, { id: gameId }, host.token).catch(() => {});
      console.log(`game aborted: ${gameId}`);
    }
  }

  // ---- GAME A2 (fresh decks - turn cycling drains them, and every missing
  // draw is 2 exhaustion damage to ALL own living fighters): PLACE +
  // BOOST_CHOICE only.
  gameId = await startDuel(host, joiner, heroA, heroB);
  try {
    // ---- 8. PLACE + BOOST_CHOICE live. Two independent producers:
    //   PATH 1 (priority, no joiner card needed): the JOINER kills a HOST
    //   Harpy (HP 1 - one undefended attack), then the HOST scheme 'Winged
    //   Frenzy' queues per-fighter MOVE heads with an optional revive-PLACE
    //   tail (return a defeated Harpy into Medusa's zone, full health).
    //   PATH 2 (fallback, also covers BOOST_CHOICE): HOST attacks the
    //   JOINER's MERLIN with 'Second Shot' (BOOST -> optional BOOST_CHOICE
    //   for the attacker), JOINER defends with 'Bewilderment'
    //   (PREVENT_DAMAGE + optional post-combat PLACE of the defender into
    //   any space - even another zone).
    let placed = false, boosted = false, harpyDead = false;
    const drainCapture = async (startState) => {
      let s = startState;
      for (let guard = 0; guard < 10; guard++) {
        const head = headOf(s);
        if (!head) return s;
        if (head.type === 'PLACE' && !placed) {
          const ownerSeat = head.playerId === host.id ? 'host' : 'joiner';
          const waitSeat = ownerSeat === 'host' ? joiner : host;
          const waitName = ownerSeat === 'host' ? 'joiner' : 'host';
          saveFixture(`gd035-place-owner-${ownerSeat}-view`,
            `viewer-projected gameState at the optional PLACE pending (OWNER = ${ownerSeat} seat; fighterIds=${(head.fighterIds ?? []).join(',')}, optional=${head.optional}, zoneFighterName=${head.zoneFighterName ?? '-'})`,
            await rawView(ownerSeat === 'host' ? host.token : joiner.token, gameId));
          saveFixture(`gd035-place-wait-${waitName}-view`,
            `viewer-projected gameState at the OPPONENT-owned optional PLACE head (wait = ${waitName} seat)`, await rawView(waitSeat.token, gameId));
          placed = true;
        } else if (head.type === 'BOOST_CHOICE' && !boosted) {
          saveFixture('gd035-boost-host-view',
            `viewer-projected gameState at BOOST_CHOICE pause (owner = attacker seat; optional=${head.optional})`, await rawView(host.token, gameId));
          saveFixture('gd035-boost-joiner-view',
            'viewer-projected gameState at the OPPONENT-owned BOOST_CHOICE head (wait seat = the defender)', await rawView(joiner.token, gameId));
          boosted = true;
        }
        s = await autoResolve(head.playerId === HOST_SIDE.id ? HOST_SIDE : JOINER_SIDE, gameId, s);
      }
      return s;
    };
    for (let attempt = 0; attempt < 20 && !(placed && boosted); attempt++) {
      let state = await stateFor(host.token, gameId);
      if (isOver(state)) { console.log('note: game over before the PLACE/BOOST window'); break; }
      while (headOf(state)) state = await autoResolve(
        headOf(state).playerId === HOST_SIDE.id ? HOST_SIDE : JOINER_SIDE, gameId, state);
      if (!harpyDead && !placed) {
        // PATH 1a: kill a Harpy (HP 1) with an undefended joiner attack.
        await ensureAdjacency(host, gameId, 8, null, 'Harpies');
        state = await stateFor(host.token, gameId);
        const harpy = state.fighters.find((f) => f.ownerId === host.id && f.name.includes('Harpies') && alive(f) &&
          state.fighters.some((e) => alive(e) && e.ownerId === joiner.id &&
            Math.abs(f.position.x - e.position.x) + Math.abs(f.position.y - e.position.y) === 1));
        if (state.currentTurnPlayerId !== joiner.id ||
            !(state.phase === 'ACTION_MANEUVER' || state.phase === 'ACTION_ATTACK')) {
          await passTurn(state.currentTurnPlayerId === HOST_SIDE.id ? HOST_SIDE : JOINER_SIDE, gameId);
          continue;
        }
        if (!harpy) {
          console.log(`attempt ${attempt}: no Harpy adjacency yet`);
          await passTurn(joiner, gameId);
          continue;
        }
        {
          const adj = state.fighters.find((e) => alive(e) && e.ownerId === joiner.id &&
            Math.abs(harpy.position.x - e.position.x) + Math.abs(harpy.position.y - e.position.y) === 1);
          // Joiner's own projection (the host view hides the joiner hand).
          const joinerState = await stateFor(joiner.token, gameId);
          const atk = handOf(joinerState, joiner.id).find((c) =>
            (c.cardType === 'ATTACK' || c.cardType === 'VERSATILE') &&
            (c.bannerName === 'Any' || adj.name.includes(c.bannerName ?? 'Any')));
          if (!atk) { await passTurn(joiner, gameId); continue; }
          {
            const body = await gqlRaw(
              `mutation A($input: AttackDto!) { attack(input: $input) { state sequenceNumber phase } }`,
              { input: { gameId, attackerId: adj.id, cardId: atk.id, targetId: harpy.id } }, joiner.token);
            const j = JSON.parse(body);
            if (!j.errors?.length) {
              // NO defense from the host: the undefended combat value kills
              // the 1-HP Harpy. In COMBAT only the DEFENDER may end the
              // window (no-defense); in COMBAT_RESOLVE any participant may.
              const midState = await stateFor(host.token, gameId);
              if (midState.phase === 'COMBAT' || midState.phase === 'COMBAT_RESOLVE') {
                const resolver = midState.phase === 'COMBAT' ? host : joiner;
                await gqlRaw(`mutation RC($g: String!) { resolveCombat(input: { gameId: $g }) { sequenceNumber phase } }`, { g: gameId }, resolver.token)
                  .catch((e) => console.log(`attempt ${attempt}: resolveCombat transport error: ${String(e.message ?? e).slice(0, 120)}`));
              }
              await drainCapture(await stateFor(host.token, gameId));
              const after = await stateFor(host.token, gameId);
              harpyDead = !after.fighters.some((f) => f.ownerId === host.id && f.name.includes('Harpies') && alive(f));
              if (harpyDead) console.log(`attempt ${attempt}: a Harpy fell to an undefended attack`);
            } else {
              console.log(`attempt ${attempt}: harpy attack failed: ${j.errors[0].message.slice(0, 120)}`);
            }
          }
        }
        continue;
      }
      if (harpyDead && !placed) {
        // PATH 1b: Winged Frenzy revive-PLACE tail.
        if (state.currentTurnPlayerId !== host.id ||
            !(state.phase === 'ACTION_MANEUVER' || state.phase === 'ACTION_ATTACK')) {
          await passTurn(state.currentTurnPlayerId === HOST_SIDE.id ? HOST_SIDE : JOINER_SIDE, gameId);
          continue;
        }
        const wf = handOf(state, host.id).find((c) => c.name === 'Winged Frenzy');
        if (!wf) {
          console.log(`attempt ${attempt}: harpy dead, waiting for Winged Frenzy`);
          await passTurn(host, gameId);
          continue;
        }
        const body = await gqlRaw(
          `mutation P($input: PlaySchemeDto!) { playScheme(input: $input) { state sequenceNumber } }`,
          { input: { gameId, cardId: wf.id } }, host.token);
        const j = JSON.parse(body);
        if (j.errors?.length) { console.log(`attempt ${attempt}: Winged Frenzy rejected: ${j.errors[0].message.slice(0, 120)}`); await passTurn(host, gameId); continue; }
        console.log(`attempt ${attempt}: Winged Frenzy played for the revive-PLACE queue`);
        await drainCapture(JSON.parse(j.data.playScheme.state));
        continue;
      }
      // PATH 2: Merlin/Bewilderment fallback (also the BOOST_CHOICE source).
      await ensureAdjacency(host, gameId, 8, 'Merlin');
      state = await stateFor(host.token, gameId);
      const merlin = state.fighters.find((f) => f.ownerId === joiner.id && f.name.includes('Merlin') && alive(f));
      const secondShot = handOf(state, host.id).find((c) => c.name === 'Second Shot');
      // Joiner's own projection (the host view hides the joiner hand).
      const joinerState = await stateFor(joiner.token, gameId);
      const bew = handOf(joinerState, joiner.id).find((c) => c.name === 'Bewilderment');
      const adjacentHost = merlin && state.fighters.filter((f) => alive(f) && f.ownerId === host.id &&
        Math.abs(f.position.x - merlin.position.x) + Math.abs(f.position.y - merlin.position.y) === 1);
      if (state.currentTurnPlayerId !== host.id ||
          !(state.phase === 'ACTION_MANEUVER' || state.phase === 'ACTION_ATTACK')) {
        await passTurn(state.currentTurnPlayerId === HOST_SIDE.id ? HOST_SIDE : JOINER_SIDE, gameId);
        continue;
      }
      if (!merlin || !secondShot || !bew || !(adjacentHost ?? []).length) {
        console.log(`attempt ${attempt}: waiting for the Merlin path (merlin=${merlin ? 'yes' : 'no'} adjacent=${(adjacentHost ?? []).length}, secondShot=${secondShot ? 'yes' : 'no'}, bewilderment=${bew ? 'yes' : 'no'})`);
        await passTurn(host, gameId);
        continue;
      }
      const attacker = (adjacentHost ?? []).find((f) => f.name.includes(secondShot.bannerName ?? '')) ?? adjacentHost[0];
      const body = await gqlRaw(
        `mutation A($input: AttackDto!) { attack(input: $input) { state sequenceNumber phase } }`,
        { input: { gameId, attackerId: attacker.id, cardId: secondShot.id, targetId: merlin.id } }, host.token);
      const j = JSON.parse(body);
      if (j.errors?.length) { console.log(`attempt ${attempt}: attack failed: ${j.errors[0].message.slice(0, 120)}`); await passTurn(host, gameId); continue; }
      if (JSON.parse(j.data.attack.state).phase === 'COMBAT') {
        const dBody = await gqlRaw(`mutation PD($input: PlayDefenseDto!) { playDefense(input: $input) { sequenceNumber } }`,
          { input: { gameId, cardId: bew.id } }, joiner.token);
        const d = JSON.parse(dBody);
        if (d.errors?.length) console.log(`attempt ${attempt}: Bewilderment defense rejected: ${d.errors[0].message.slice(0, 120)}`);
      }
      const midState = await stateFor(host.token, gameId);
      if (midState.phase === 'COMBAT' || midState.phase === 'COMBAT_RESOLVE') {
        const resolver = midState.phase === 'COMBAT' ? joiner : host;
        const rcBody = await gqlRaw(`mutation RC($g: String!) { resolveCombat(input: { gameId: $g }) { sequenceNumber phase } }`, { g: gameId }, resolver.token)
          .catch((e) => { console.log(`attempt ${attempt}: resolveCombat transport error: ${String(e.message ?? e).slice(0, 120)}`); return null; });
        if (rcBody) {
          const rc = JSON.parse(rcBody);
          if (rc.errors?.length) console.log(`attempt ${attempt}: resolveCombat rejected: ${rc.errors[0].message.slice(0, 140)}`);
        }
      }
      await drainCapture(await stateFor(host.token, gameId));
    }
    if (!placed) console.log('note: PLACE head never opened (neither the Harpy revive path nor the Merlin/Bewilderment path landed)');
    if (!boosted) console.log('note: BOOST_CHOICE head never opened (Second Shot chain did not pause)');
    console.log('capture complete');
  } finally {
    await gql(`mutation AB($id: String!) { abortGame(gameId: $id) { id } }`, { id: gameId }, host.token).catch(() => {});
    console.log(`game aborted: ${gameId}`);
  }

  // ---- GAME B: CHOOSE_SPACE both stages. Board.cells zone data was
  // backfilled (bootstrap-s09-stack.cjs) and the stage-2 sequence bump was
  // fixed in game-action-executor, so BOTH stages resolve live now; the
  // stage-2 head is captured as a live fixture (it used to be
  // synthesized-only when boards carried no zone data).
  gameId = await startDuel(host, joiner, heroA, heroB);
  try {
    const { state } = await playSchemeCard(joiner, host, gameId, 'Restless Spirits', 60);
    const head = headOf(state);
    if (head?.type !== 'CHOOSE_SPACE' || head.stage !== 1) {
      throw new Error(`Restless Spirits produced ${head?.type} stage ${head?.stage}`);
    }
    saveFixture('gd035-space-stage1-joiner-view',
      'viewer-projected gameState at CHOOSE_SPACE stage 1 (owner seat; zone cell pending, zone data live in Board.cells)',
      await rawView(joiner.token, gameId));
    saveFixture('gd035-space-stage1-host-view',
      'viewer-projected gameState at the OPPONENT-owned CHOOSE_SPACE stage 1 head (wait seat; mandatory, no decline)', await rawView(host.token, gameId));
    let s = await autoResolve(joiner, gameId, state); // stage 1: first cell sharing the anchor zone
    const head2 = headOf(s);
    if (head2?.type === 'CHOOSE_SPACE' && head2.stage === 2) {
      saveFixture('gd035-space-stage2-joiner-view',
        'viewer-projected gameState at CHOOSE_SPACE stage 2 (owner seat; cell adjacent to the stage-1 anchor, live after the stage-2 seq fix)', await rawView(joiner.token, gameId));
      saveFixture('gd035-space-stage2-host-view',
        'viewer-projected gameState at the OPPONENT-owned CHOOSE_SPACE stage 2 head (wait seat)', await rawView(host.token, gameId));
      await autoResolve(joiner, gameId, s);
      console.log('CHOOSE_SPACE both stages resolved live (zone backfill + stage-2 seq fix)');
    } else {
      console.log(`note: CHOOSE_SPACE stage 2 did not open (${head2?.type} stage ${head2?.stage})`);
    }
  } finally {
    await gql(`mutation AB($id: String!) { abortGame(gameId: $id) { id } }`, { id: gameId }, host.token).catch(() => {});
    console.log(`game aborted: ${gameId}`);
  }
}

main().catch((e) => { console.error(e.message ?? e); if (e.body) console.error(e.body.slice(0, 400)); process.exit(1); });

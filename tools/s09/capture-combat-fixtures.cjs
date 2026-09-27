// GD-034: capture REAL viewer-projected combat snapshots + raw mutation
// response bodies against the worktree-local backend (:3120) for the UE
// automation tests. Drives one scoped ONE_V_ONE game: approach -> attack ->
// defense -> resolve, capturing both viewer perspectives at each stage.
// Fixtures land in docs/game-design/evidence/S09/fixtures/ as
// { name, capturedAt, note, raw: <exact HTTP response body> } (S08 shape).
// Credentials come from backend/.env (S09_DEMO_*) - never argv, never printed.
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const HTTP = 'http://localhost:3120/graphql';
const FIXTURE_DIR = path.resolve(__dirname, '..', '..', 'docs', 'game-design', 'evidence', 'S09', 'fixtures');

// env from backend/.env
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
const stateOf = (data, field) => JSON.parse(data[field].state);
const handOf = (state, userId) => state.handZones[userId]?.cards ?? [];
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
  return d.heroList.items.find((h) => h.name === name).id;
}

// Movement BFS mirroring backend traversal: orthogonal steps, impassable cells
// block, living enemies block transit, destination must hold no other living
// fighter. Returns a path WITHOUT the start cell.
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

function adjacentEnemy(state, fighter) {
  return state.fighters.find((f) => alive(f) && f.ownerId !== fighter.ownerId &&
    Math.abs(f.position.x - fighter.position.x) + Math.abs(f.position.y - fighter.position.y) === 1);
}
function cellsAdjacentToEnemies(state, ownerId) {
  const out = [];
  for (const e of state.fighters.filter((f) => alive(f) && f.ownerId !== ownerId)) {
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      out.push({ x: e.position.x + dx, y: e.position.y + dy });
    }
  }
  return out;
}
// Banner cards (e.g. 'Clutching Claws' -> Harpy) are only playable by the
// named fighter. Mirror the server's validateBanner: empty/'any' banner is
// universal, otherwise the fighter name must match the banner (Harpies ->
// 'Harpy' via substring, both directions).
function playableBy(card, fighter) {
  const b = (card.bannerName || '').trim().toLowerCase();
  if (!b || b === 'any') return true;
  const n = fighter.name.toLowerCase();
  return n.includes(b) || b.includes(n);
}
const firstCard = (state, userId, types, fighter) =>
  handOf(state, userId).find((c) => types.includes(c.cardType) && playableBy(c, fighter));

async function fetchState(token, gameId) {
  return await gql(`query GS($g: String!) { gameState(gameId: $g) { state sequenceNumber phase } }`, { g: gameId }, token);
}

function saveFixture(name, note, rawBody) {
  const file = path.join(FIXTURE_DIR, `${name}.json`);
  fs.writeFileSync(file, JSON.stringify({ name, capturedAt: new Date().toISOString(), note, raw: rawBody }, null, 1));
  console.log(`fixture: ${name} (${rawBody.length} bytes)`);
}

const hero0 = (state, userId) => state.fighters.find((f) => f.ownerId === userId && f.type === 'HERO' && alive(f))
  || state.fighters.find((f) => f.ownerId === userId && alive(f));

async function driveOneGame() {
  const host = await login(HOST);
  const joiner = await login(JOINER);
  await cleanupMine(host.token);
  await cleanupMine(joiner.token);

  const heroA = await heroByName(host.token, 'Medusa');
  const heroB = await heroByName(joiner.token, 'King Arthur');
  const game = (await gql(`mutation C { createGame(input: { mode: ONE_V_ONE }) { id code } }`, {}, host.token)).createGame;
  await gql(`mutation J($input: JoinGameDto!) { joinGame(input: $input) { id } }`, { input: { gameId: game.id } }, joiner.token);
  await gql(`mutation S($g: String!, $h: String!) { selectHero(gameId: $g, heroId: $h) { id } }`, { g: game.id, h: heroA }, host.token);
  await gql(`mutation S($g: String!, $h: String!) { selectHero(gameId: $g, heroId: $h) { id } }`, { g: game.id, h: heroB }, joiner.token);
  await gql(`mutation R($g: String!) { toggleReady(gameId: $g) { id } }`, { g: game.id }, host.token);
  await gql(`mutation R($g: String!) { toggleReady(gameId: $g) { id } }`, { g: game.id }, joiner.token);
  await gql(`mutation St($g: String!) { startGame(gameId: $g) { id status } }`, { g: game.id }, host.token);

  const seat = (state) => state.currentTurnPlayerId === host.id ? host : joiner;
  const other = (state) => state.currentTurnPlayerId === host.id ? joiner : host;

  // Approach phase: each turn owner maneuvers one own fighter toward the
  // nearest enemy until an adjacent pair exists; then the owner attacks.
  let attackEcho = null, attackState = null, attacker = null;
  for (let i = 0; i < 60 && !attackEcho; i++) {
    let state = JSON.parse((await gql(`query GS($g: String!) { gameState(gameId: $g) { state } }`, { g: game.id }, host.token)).gameState.state);
    const me = seat(state);
    // Hand data must come from the ACTING player's projection (a foreign
    // projection hides the other seat's hand behind placeholders).
    if (me.id !== host.id) {
      state = JSON.parse((await gql(`query GS($g: String!) { gameState(gameId: $g) { state } }`, { g: game.id }, me.token)).gameState.state);
    }
    const myFighters = state.fighters.filter((f) => f.ownerId === me.id && alive(f));
    if (state.phase === 'COMBAT' || state.phase === 'COMBAT_RESOLVE') throw new Error('unexpected combat during approach');
    if (state.phase !== 'ACTION_MANEUVER' && state.phase !== 'ACTION_ATTACK') {
      // TURN_END discard etc. - auto-resolve by discarding first N cards
      if (state.metadata.pendingHandDiscard?.playerId === me.id) {
        const pending = state.metadata.pendingHandDiscard;
        const ids = handOf(state, me.id).slice(0, pending.count).map((c) => c.id);
        console.log(`debug discard: seq=${state.sequenceNumber} phase=${state.phase} turn=${state.currentTurnPlayerId === host.id ? 'host' : 'joiner'} me=${me.id === host.id ? 'host' : 'joiner'} hand=${handOf(state, me.id).length} count=${pending.count} sending=${ids.length}`);
        const body = await gqlRaw(`mutation D($input: DiscardToLimitDto!) { discardToLimit(input: $input) { sequenceNumber } }`,
          { input: { gameId: game.id, pendingId: pending.id, cardIds: ids } }, me.token);
        const dj2 = JSON.parse(body);
        if (dj2.errors?.length) throw new Error('discardToLimit failed: ' + dj2.errors[0].message);
      }
      continue;
    }
    if (i % 4 === 0) {
      const heroPos = hero0(state, me.id);
      const nearest = heroPos ? Math.min(...state.fighters.filter((f) => f.ownerId !== me.id && alive(f))
        .map((f) => Math.abs(f.position.x - heroPos.x) + Math.abs(f.position.y - heroPos.y))) : -1;
      console.log(`debug approach: i=${i} seq=${state.sequenceNumber} phase=${state.phase} turn=${me.id === host.id ? 'host' : 'joiner'} hero@${heroPos ? heroPos.position.x + ',' + heroPos.position.y : 'MISSING'} nearest=${nearest}`);
    }
    let pick = null;
    for (const f of myFighters) {
      const e = adjacentEnemy(state, f);
      if (!e) continue;
      const c = firstCard(state, me.id, ['ATTACK', 'VERSATILE', 'UNIVERSAL'], f);
      if (c) { pick = { attacker: f, target: e, card: c }; break; }
    }
    if (pick) {
      const body = await gqlRaw(`mutation A($input: AttackDto!) { attack(input: $input) { state sequenceNumber phase turnCount currentTurnPlayerId } }`,
        { input: { gameId: game.id, attackerId: pick.attacker.id, cardId: pick.card.id, targetId: pick.target.id } }, me.token);
      const j = JSON.parse(body);
      if (j.errors?.length) throw new Error('attack failed: ' + j.errors[0].message);
      attackEcho = body;
      attackState = JSON.parse(j.data.attack.state);
      attacker = pick.attacker;
      break;
    }
    // maneuver toward enemies
    const hero = myFighters.find((f) => f.type === 'HERO') || myFighters[0];
    const begin = await gql(`mutation B($input: BeginManeuverDto!) { beginManeuver(input: $input) { state } }`,
      { input: { gameId: game.id, expectedSequenceNumber: state.sequenceNumber } }, me.token);
    const after = JSON.parse(begin.beginManeuver.state);
    const pendingId = after.metadata.pendingManeuver?.id;
    const heroAfter = after.fighters.find((f) => f.id === hero.id);
    const path = bfsStep(after, heroAfter, cellsAdjacentToEnemies(after, me.id)) || [];
    const trimmed = path.slice(0, heroAfter.movement);
    await gql(`mutation M($input: ManeuverDto!) { maneuver(input: $input) { sequenceNumber } }`,
      { input: { gameId: game.id, maneuverId: pendingId, moves: trimmed.length ? [{ fighterId: hero.id, path: trimmed }] : [], boostCardId: null } }, me.token);
  }
  if (!attackEcho) throw new Error('approach loop exhausted without an attack');
  saveFixture('gd034-attack-echo-attacker', 'raw attack mutation response (GameMutationResult, attacker seat)', attackEcho);

  // COMBAT open: both viewer projections (privacy split BEFORE reveal).
  const combatHost = await gqlRaw(`query GS($g: String!) { gameState(gameId: $g) { id gameId state sequenceNumber phase turnCount currentTurnPlayerId updatedAt } }`, { g: game.id }, host.token);
  const combatJoiner = await gqlRaw(`query GS($g: String!) { gameState(gameId: $g) { id gameId state sequenceNumber phase turnCount currentTurnPlayerId updatedAt } }`, { g: game.id }, joiner.token);
  const defenderId = attackState.metadata.combatInfo.defenderId;
  const isHostAttacker = defenderId !== host.id;
  saveFixture('gd034-combat-open-attacker-view', 'viewer-projected gameState during COMBAT (attacker seat; own card visible, defense hidden)', isHostAttacker ? combatHost : combatJoiner);
  saveFixture('gd034-combat-open-defender-view', 'viewer-projected gameState during COMBAT (defender seat; attack value/card hidden)', isHostAttacker ? combatJoiner : combatHost);

  // Defense: the DEFENDING FIGHTER (combatInfo.targetFighterId) plays the
  // card - banner legality is checked against it, not the hero. The card is
  // picked from the DEFENDER's own projection: the attacker's echo hides the
  // defender's hand behind placeholders ('Card not in hand').
  const defender = defenderId === host.id ? host : joiner;
  const defenderViewState = JSON.parse(JSON.parse(isHostAttacker ? combatJoiner : combatHost).data.gameState.state);
  const defFighter = defenderViewState.fighters.find((f) => f.id === defenderViewState.metadata.combatInfo.targetFighterId)
    || defenderViewState.fighters.find((f) => f.ownerId === defender.id && f.type === 'HERO');
  const defCard = firstCard(defenderViewState, defender.id, ['DEFENSE', 'VERSATILE', 'UNIVERSAL'], defFighter);
  if (!defCard) throw new Error('defender has no defense-typed card - rerun the capture');
  const defenseEcho = await gqlRaw(`mutation P($input: PlayDefenseDto!) { playDefense(input: $input) { state sequenceNumber phase turnCount currentTurnPlayerId } }`,
    { input: { gameId: game.id, cardId: defCard.id } }, defender.token);
  const dj = JSON.parse(defenseEcho);
  if (dj.errors?.length) throw new Error('playDefense failed: ' + dj.errors[0].message);
  saveFixture('gd034-defense-echo-defender', 'raw playDefense mutation response (defender seat)', defenseEcho);

  const resolveHost = await gqlRaw(`query GS($g: String!) { gameState(gameId: $g) { id gameId state sequenceNumber phase turnCount currentTurnPlayerId updatedAt } }`, { g: game.id }, host.token);
  const resolveJoiner = await gqlRaw(`query GS($g: String!) { gameState(gameId: $g) { id gameId state sequenceNumber phase turnCount currentTurnPlayerId updatedAt } }`, { g: game.id }, joiner.token);
  saveFixture('gd034-resolve-window-attacker-view', 'viewer-projected gameState during COMBAT_RESOLVE before reveal (attacker seat; defense value still hidden)', isHostAttacker ? resolveHost : resolveJoiner);
  saveFixture('gd034-resolve-window-defender-view', 'viewer-projected gameState during COMBAT_RESOLVE before reveal (defender seat; attack value still hidden)', isHostAttacker ? resolveJoiner : resolveHost);

  // Resolve (attacker seat presses it): may pause mid-pipeline on card
  // effects - drain pends through the production resolvers when needed.
  const resolver = isHostAttacker ? host : joiner;
  let resolveEcho = await gqlRaw(`mutation R($input: ResolveCombatDto!) { resolveCombat(input: $input) { state sequenceNumber phase turnCount currentTurnPlayerId } }`,
    { input: { gameId: game.id } }, resolver.token);
  let rj = JSON.parse(resolveEcho);
  if (rj.errors?.length) throw new Error('resolveCombat failed: ' + rj.errors[0].message);
  saveFixture('gd034-resolve-echo', 'raw resolveCombat mutation response', resolveEcho);
  let resolved = JSON.parse(rj.data.resolveCombat.state);
  for (let drain = 0; resolved.metadata.pendingEffects?.length && drain < 12; drain++) {
    const head = resolved.metadata.pendingEffects[0];
    const owner = head.playerId === host.id ? host : joiner;
    const optional = head.optional !== false;
    const isBoost = head.type === 'BOOST_CHOICE';
    // Card picks need the OWNER's projection: `resolved` is the resolver's
    // echo and hides the other seat's hand behind placeholders.
    let ownerState = resolved;
    if (head.playerId !== resolver.id) {
      ownerState = JSON.parse((await gql(`query GS($g: String!) { gameState(gameId: $g) { state } }`, { g: game.id }, owner.token)).gameState.state);
    }
    // Boost card legality is per the owner's fighter currently in combat.
    const ci = resolved.metadata.combatInfo;
    const attackerFighter = ci ? resolved.fighters.find((f) => f.id === ci.attackerId) : null;
    const ownerFighter = (attackerFighter && attackerFighter.ownerId === head.playerId ? attackerFighter
      : ci ? resolved.fighters.find((f) => f.id === ci.targetFighterId) : null)
      || resolved.fighters.find((f) => f.ownerId === head.playerId && f.type === 'HERO')
      || resolved.fighters.find((f) => f.ownerId === head.playerId);
    if (optional && !(isBoost && firstCard(ownerState, owner.id, ['DEFENSE', 'VERSATILE', 'ATTACK', 'UNIVERSAL'], ownerFighter))) {
      const body = await gqlRaw(`mutation Dec($input: DeclinePendingEffectDto!) { declinePendingEffect(input: $input) { state } }`,
        { input: { gameId: game.id, effectId: head.id } }, owner.token);
      const jj = JSON.parse(body);
      if (jj.errors?.length) throw new Error('declinePendingEffect failed: ' + jj.errors[0].message);
      resolved = JSON.parse(jj.data.declinePendingEffect.state);
      continue;
    }
    const card = firstCard(ownerState, owner.id, isBoost ? ['DEFENSE', 'VERSATILE', 'ATTACK', 'UNIVERSAL'] : [], ownerFighter);
    const body = await gqlRaw(`mutation Res($input: ResolvePendingEffectDto!) { resolvePendingEffect(input: $input) { state } }`,
      { input: { gameId: game.id, effectId: head.id, ...(isBoost && card ? { cardIds: [card.id] } : {}) } }, owner.token);
    const jj = JSON.parse(body);
    if (jj.errors?.length) throw new Error('resolvePendingEffect failed: ' + jj.errors[0].message);
    resolved = JSON.parse(jj.data.resolvePendingEffect.state);
  }
  if (resolved.metadata.combatInfo && resolved.phase !== 'GAME_OVER') {
    throw new Error('combat still open after resolve+drain: phase=' + resolved.phase);
  }

  // Post-combat states for both viewers (result readability data).
  const doneHost = await gqlRaw(`query GS($g: String!) { gameState(gameId: $g) { id gameId state sequenceNumber phase turnCount currentTurnPlayerId updatedAt } }`, { g: game.id }, host.token);
  const doneJoiner = await gqlRaw(`query GS($g: String!) { gameState(gameId: $g) { id gameId state sequenceNumber phase turnCount currentTurnPlayerId updatedAt } }`, { g: game.id }, joiner.token);
  saveFixture('gd034-combat-done-attacker-view', 'viewer-projected gameState after combat resolved (combatInfo cleared; damage in fighters)', isHostAttacker ? doneHost : doneJoiner);
  saveFixture('gd034-combat-done-defender-view', 'viewer-projected gameState after combat resolved (defender seat)', isHostAttacker ? doneJoiner : doneHost);

  return { gameId: game.id, hostToken: host.token };
}

async function main() {
  fs.mkdirSync(FIXTURE_DIR, { recursive: true });
  let lastError = null;
  for (let attempt = 1; attempt <= 4; attempt++) {
    let ctx = null;
    try {
      ctx = await driveOneGame();
      console.log('capture OK');
      return;
    } catch (e) {
      lastError = e;
      console.error(`attempt ${attempt} failed: ${e.message}`);
      if (e.body) fs.writeFileSync(path.join(FIXTURE_DIR, 'last-error-body.json'), e.body);
    }
  }
  throw lastError;
}

main().catch((e) => { console.error('FATAL:', e.message); process.exit(1); });

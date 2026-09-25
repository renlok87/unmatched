# S04 completion: GD-016 + GD-018

Base: `57156a7` (S04 GD-014/015 integrated). Isolated checkout, no commits.
Sources: 14-sprint-backlog.csv GD-016/GD-018; 15-rules ACC-017/ACC-008;
GDD-001/002/008/018; evidence/S01/rules-oracle.md; evidence/S03+S04 README.

## GD-016 — стартовая пара и расстановка (ACC-017 серверная часть)

Problems in current code (verified):
1. `GameService.selectHero` has NO server-side duplicate check — S01
   `duplicate-start.json` captured a real Medusa-vs-Medusa match.
2. `startGame` does not guard against duplicate heroIds either.
3. `GameInitializationService` places sidekicks by fixed `SIDEKICK_OFFSETS`
   around the hero — on the pinned 5×6 board harpies 2/3 of seat-0 Medusa
   land in the RED zone (2,3)/(3,3) while the hero stands in BLUE.
4. First player only implicit (`currentTurnPlayerId === seat-0 userId`).

Plan:
- `selectHero`: reject a hero already chosen by another player of the same
  LOBBY game (re-check inside `$transaction`). Keep free re-selection of
  own/other hero while LOBBY (GDD-001 cancel rule).
- `startGame`: reject duplicate heroIds across players (defense-in-depth
  closing any residual select race; match can never start duplicated).
- `GameInitializationService`: zone-legal sidekick placement — scan cells by
  Manhattan distance from the hero (existing findFreeCell scan order),
  keep only free, passable cells sharing ≥1 zone with the hero cell
  (`getCellZones` intersection); boards/cells without zone info keep the old
  proximity fallback (no zone data ⇒ no zone constraint). Distinct cells by
  construction (occupied set). Heroes keep the GD-014 corner algorithm.
- `metadata.firstPlayerId` set at init (explicit first player), added to
  `GameStateMetadata`, serializer (`fp`) and deserializer.
- Update `evidence/S04/board-contract.json` `starts` for both orientations
  (sidekick slots change under zone legality; capture provenance/hash of the
  5×6 source unchanged) + GD-014 `tasks.json` note + S04 README.
- Tests `backend/src/games/services/s04-start-selection.spec.ts`:
  both seat orientations; distinct cells; sidekicks share hero zone;
  boardState equals S01 capture; firstPlayerId/currentTurn explicit;
  saveState snapshot + serialize/deserialize roundtrip;
  concurrent selectHero (Promise.all same hero) ⇒ exactly one wins;
  startGame duplicate rejected. Production services with fixture
  prisma/redis adapters (board-contract spec pattern).
- Real API harness `backend/src/games/resolvers/s04-lobby-transport.spec.ts`
  (s03-transport pattern): HTTP create/join/select(both, distinct)/ready/
  start → IN_PROGRESS; gameState exposes legal setup + firstPlayerId;
  duplicate selectHero and premature start rejected over HTTP.

Not in scope: UE screen/hit-test, player-chosen placements (GDD-002/GAP №7
keeps server-owned setup; backlog acceptance demands legal server setup),
any restriction of the hero catalog (checks are generic uniqueness, not a
two-hero whitelist).

## GD-018 — последовательная очередь выборов (ACC-008)

Problems in current code (verified):
1. Sequential order enforced only under `combatResolutionProgress`
   (`pendingEffects[0]`); outside combat any pending resolvable in any order.
2. Open `pendingEffects` do NOT gate attack/playScheme/beginManeuver/endTurn/
   toggleDoor/setStance — second action can start while a choice is open.
3. `advanceTurn` expires pendings of the player the turn returns to —
   circle expiry silently replaces the decision (ACC-008 forbids).
4. No decline path at all (GAP №4): optional effects cannot be refused by
   server command; mandatory cannot be protected.
5. Turn transfer happens immediately at action exhaustion even when the
   action created pending choices.

Plan (no generic mega-queue; extend the existing pendingEffects chain):
- Model: `PendingEffect.optional?: boolean`; `CardEffect.optional?: boolean`
  propagated by `applyOneEffect` (MOVE/PLACE/CHOOSE_ONE);
  `GameStateMetadata.pendingTurnEnd?: { playerId }` — persisted continuation
  point "turn transfer awaits queue drain". Serialized (`pte`).
- Executor gates: every mutating action (beginManeuver/maneuver-complete is
  the staged flow — keep; attack, playDefense, playScheme, resolveCombat,
  endTurn, toggleDoor, setStance, discardToLimit, moveFighter stub) fails
  `Resolve the pending choice first` while `pendingEffects.length > 0`.
  `executeResolvePendingEffect`: head-of-queue enforcement ALWAYS (not only
  combat); foreign owner / unknown id / invalid target / replay fail without
  mutation (existing checks preserved).
- `advanceTurn`: at entry, if queue open → defer: set `pendingTurnEnd`,
  keep phase/actions/seq contract of the caller, no hooks, no transfer
  (hooks run exactly once at the real transfer). Turn-end hooks may create
  pendings → re-check after hooks, before hand-limit/transfer. Remove the
  circle-expiry filter (decisions are never replaced by timeout/expiry).
- Drain point shared by resolve/decline: when queue empties —
  a) combat continuation preserved: `combatResolutionProgress` ⇒ re-enter
  `executeResolveCombat` (existing behavior);
  b) else `pendingTurnEnd` ⇒ `advanceTurn` with `incrementSeq=false`
  (the resolving mutation already did its single +1) ⇒ exactly one transfer.
- New `executeDeclinePendingEffect({gameId, effectId})`: head-of-queue,
  owner-only, `optional===true` only (mandatory decline rejected), removes
  the choice, seq +1, same continuation. Resolver mutation
  `declinePendingEffect` (GqlAuthGuard+GameInProgressGuard+GamePlayerGuard,
  no phase guard), logged as CARD_PLAYED like resolvePendingEffect.
- Timeout never fabricates: `CombatTimeoutService.processAutoResolve` keeps
  pending queue untouched (stub already does; add regression assertion).
- AI: `AiDecisionService` uses the global queue head (null when head is not
  the bot — no skipping); new `declinePending` action for optional head when
  no useful decision (no fighter / no improving step);
  `AiTurnService.dispatch` case wired. No mandatory choice can strand a
  VS_AI match: decidePending covers CHOOSE_ONE/MOVE/PLACE classes.
- Clients: web `remoteGameStore.declinePendingEffect(effectId)` (hand-written
  gql document — codegen needs a live backend), `WirePendingEffect.optional`,
  GameView «Отказаться» button for optional head; admin game-tester
  `pdecline <effectId>` command + DECLINE_PENDING_EFFECT api const.
- Tests `backend/src/game-engine/services/s04-pending-queue.spec.ts`
  (engine-level, s03Engine fixture): out-of-order/foreign/replay/invalid
  rejected without mutation; mandatory decline rejected; optional decline
  continues; second action + endTurn gated while queue open; actions=0 +
  open queue ⇒ no transfer + pendingTurnEnd persisted; final resolution ⇒
  exactly one transfer (seq +1 per mutation, turn switches once); queue
  save/load roundtrip (serialize/deserialize) incl. optional + continuation
  resume after reload; combat pause/resume chain preserved (second-action
  attack creating after-combat pending: defense/resolve blocked until head
  resolved, then combat finishes, transfer once); GAME_OVER inside chain
  stops (immediate terminal preserved).
- HTTP/WS harness `backend/src/games/resolvers/s04-pending-transport.spec.ts`
  (s03-transport pattern, evidence via env var, deterministic/sanitized):
  seeded two-choice chain (mandatory MOVE + optional MOVE) with actions=0:
  HTTP attack/endTurn rejected; wrong-order resolve rejected; decline of
  mandatory rejected; resolve head via HTTP; decline optional via HTTP;
  after chain turn transferred once; both WS observers see updates;
  cache-evict + snapshot reconnect mid-chain restores queue/continuation.
- AI spec `backend/src/game-engine/services/s04-ai-queue.spec.ts`: head-only
  decisions, decline wiring, full drain loop through AiTurnService with
  fixture state service.

## Process

1. Tests first (capture failing assertions), then implementation.
2. Focused suites + `npm run build` (backend), vitest for touched client
   tests. Full baseline expectation: 931 passed / 3 known auth failures /
   49 suites — do not touch auth.
3. Evidence: S04 README sections, board-contract.json starts update,
   tasks.json entries for GD-016/GD-018 + backlog status → done only after
   proven; validation via `python docs/game-design/_validation/validate_package.py`.
4. Report: files, checks, failures, API examples, remaining acceptance
   (UE milestones stay open; ACC-017/ACC-008 not claimed fully closed).

# S09 Evidence - private UE duel (GD-032..GD-036)

All evidence in this directory was produced inside the S09 worktree
(`codex/s09-hud-flow` off integrated S08 commit f91362e) against a
worktree-local stack:

- backend on **:3120** (s09-start.cjs, `unreal/Unmatched/backend/.env`)
- docker `codex-s09-postgres` (:55434) + `codex-s09-redis` (:6381)
- full seed chain (admin -> reference -> scraped 84 heroes / 880 cards /
  30 boards, zero cards without values; scraped-data copied read-only from
  the main checkout because it is git-ignored)
- two scoped dev accounts (s09 host/joiner testers) - credentials only ever
  passed through process environment variables, never argv.

The prior worktree's :3100 stack was never touched.

## What is proven here

### GD-032 (exact private hand vs count-only opponent hand)

- UE automation tests `Unmatched.S09.HUD.*` - **5/5 green** in the same
  headless editor run (`run/automation-tests.log`):
  - host perspective: all 5 own hand cards carry **exact instance ids**
    (`drawn-new::9` style), opponent entry is count-only (`Cards.Num()==0`,
    summary `oppHand=5(hidden)`), deck counts exact (25/25) with the
    freshness marker only while the deck projection is stale, actions/turn
    exact.
  - guest perspective: roles flip exactly (guest sees own exact ids, host
    hand count-only).
  - privacy: a `hidden-N` placeholder decodes to an empty identity -
    the HUD model never constructs an opponent card object at all
    (privacy by construction, not by filtering).
  - freshness: the real WS `next` fixture 07 ships no `decks`; the model
    keeps the last HTTP deck counts and marks them stale (`~`) until the
    next deck-bearing snapshot merges.
  - new-card tracking: exactly one entry is flagged `*new*` after a draw,
    zero on the baseline turn.
- Fixtures are the S08 live captures 04/05/07 (per-viewer gameState, WS
  next) - no new fixtures were needed; the HUD model was validated against
  the real backend projections, not synthetic ones.

### GD-033 (click/key maneuver + exact-instance discard UI)

- UE automation tests `Unmatched.S09.CMD.*` - **9/9 green**:
  - begin gate: beginManeuver legal in ACTION phase with actions left;
    double-begin blocked while a pending maneuver exists ("already open");
    guest begin rejected ("not your turn"); in-flight duplicate suppressed.
  - zero-move: confirming with **no moves is legal** (draw-only maneuver),
    ManeuverId preserved into the submit command.
  - boost: the boost slot accepts exactly one own, non-hidden card id;
    `hidden-0` and opponent ids are rejected ("exact card instance");
    toggling outside the draft is rejected.
  - multi-fighter: hero (3,2) and sidekick (0,2) moves drafted in one
    command, both paths length 1; ClearMove on one keeps the other.
  - destinations: (19,19) rejected ("exceeds movement"), enemy fighter
    rejected, two fighters targeting the same cell rejected ("same cell").
  - cancel keeps the server draw: local cancel clears moves but keeps the
    draft resumable against the SAME pending id, blocks a second begin,
    and a fresh begin becomes legal again only after the pending resolves.
  - discard exact count: hidden/opponent ids rejected; under-select
    rejected ("exactly 2"); exactly 2 unique own instance ids accepted;
    over-select rejected ("excess"); in-flight duplicate suppressed.
  - regression (the live-demo bug, model level): hand of 5 ->
    beginManeuver draws a 6th card -> the same-seq re-apply (WS push +
    HTTP refetch merged) is replayed 3x against the HUD build - the
    drawn instance stays **exactly one `*new*` entry** with its exact id,
    stays boost-eligible, and one `ToggleBoostCard` + confirm consumes
    that exact instance once (`BoostCardId == drawn id`, moves=0, no
    misuse). Guards the `PreviousOwnHandIds` baseline update in
    `S08FlowGameMode.HandleApplied` (quiet-state-only baseline bump).
- `run/` - the two packaged-client demo (below) exercises the same command
  surface end-to-end through the real backend, including the UI-only
  gates above.

### Two packaged clients (GD-032 + GD-033 end to end)

- `run/run-<stamp>/` - two packaged Win64 Development clients
  (Saved/StagedBuilds/Windows, /Game/S08/S08Arena +
  S08FlowGameMode) run hidden (`-RenderOffScreen`, CreateNoWindow)
  against :3120:
  - host `-S09Flow`: T1 beginManeuver -> **zero-move confirm**
    (`MANEUVER-CONFIRM moves=0 boost=none`) -> second maneuver hero step ->
    endTurn; T2 **multi-fighter** (hero + sidekick, `moves=2`) -> step ->
    endTurn -> 9 cards -> `DISCARD-DRAFT count=2` -> **exactly 2**
    instance-id discards -> turn passes.
  - joiner `-S09FlowBoost`: T2 begin -> **boost the newly drawn card**
    (`S09AUTO boost(new card) set` + `MANEUVER-CONFIRM moves=0 boost=card`;
    the boost discards the card, so the hand math lands at 8 ->
    `DISCARD-DRAFT count=1` -> exactly 1 discard). Boosted-zero-maneuver
    coverage required a fix: a same-seq re-apply (WS push + HTTP refetch)
    used to absorb the freshly drawn card into the previous-hand baseline
    and the `*new*` marker died before the pick (`PreviousOwnHandIds`
    quiet-state guard in S08FlowGameMode.HandleApplied).
  - both: `DRAFT-OPEN draw committed` (server draw stays committed; no
    second begin), `turn=opp` handovers, seq convergence between the
    clients (max-seq within 4 + identical TURN_END seq sets; latest run
    035408: both clients maxSeq=154, 24 TURN_END views each, match ran
    through GAME_OVER).
  - **HUD rendering is proven by state-specific marker gates** (P1
    rework; replaces the earlier bright-pixel counts, which the bright
    3D board dominated): each draft panel renders a solid 220x14 marker
    that appears nowhere else in the frame - maneuver `#FF00FF`,
    mandatory discard `#00FFFF`. Shots are UI-inclusive
    (`FScreenshotRequest::RequestScreenshot(..., bShowUI=true)`), and
    the driver gates on measured pixels before publishing:
    - dimensions are read **from the PNG files** (the packaged client
      honors the SAVED resolution, not `-resx/-resy`, so the driver
      first publishes 1280x720 into the staged `GameUserSettings.ini`;
      every capture is asserted to be exactly 1280x720 or 1920x1080);
    - draft-open must have >= 200 magenta samples in the panel region
      (x<60%, y<50%) and **zero cyan anywhere**; discard-open the
      inverse; latest run 035408: host and joiner both 848 magenta
      region / 0 cyan-other and 600 cyan region / 0 magenta-other;
    - the idle (no-draft) frame is the live board-only negative
      control and carries **neither** marker (0/0 both clients);
    - swapped state/image pairs are asserted to **fail** the gates.
  - a standalone packaged probe (`tools/s09/run-hud-probe.ps1`,
    `-S09HudProbe`, no backend) drives the same HUD widgets from a
    fixture. It captures board-only (HUD hidden - negative control),
    maneuver-draft and discard-open states at 1280x720 and applies the
    same marker gates plus the swapped-pair failure assertions. It
    also proves the **manual key input path with a split verdict**:
    a real Slate `ProcessKeyDownEvent` is counted separately
    (`S09KeyRouteArmed=1`) from the direct `PlayerController->InputKey`
    fallback (`=2`); the probe passes only on the Slate route
    (`S09PROBE verdict slate-key-route seen=1 direct-key-route seen=0
    picks=1 -> SLATE-PASS`). The mouse/cursor path is explicitly
    reported `MANUAL-OPEN` (no real cursor hit-testing in the packaged
    probe) - not claimed as proven.
    The latest packaged replay, after the scrolling discard inspector,
    passed its marker, keyboard-route and negative-control gates;
    captures, trace and hashes are in `run/hud-probe-20260927-123236/`
    (driver log `run/hud-probe-final-20260927.log`). The pointer path
    is covered separately by the Unreal MCP PIE check below.
  - **P1 gameplay-UI fixes in this iteration** (adversarial-review
    rework): the legacy login/lobby/trace root collapses during
    gameplay and probe (F10 re-opens it as an optional debug panel),
    HUD panels are opaque dark SBrands with white bold text >= 14pt
    (measured cap-height bands in the captures correspond to ~18.7px
    em at DPI 1; headers 16pt), hand-card chips and confirm buttons
    are >= 32px tall targets, and the maneuver vs mandatory-discard
    panels carry distinct headers, marker colors, and
    required-count/selected feedback with disabled-confirm until the
    exact count is reached.
  - Turn end is **server-driven in the plain maneuver flow**: the backend
    auto-advances the turn the moment actions hit 0
    (consumeAction -> advanceTurn; excess > 0 becomes TURN_END +
    pendingHandDiscard automatically). The client END TURN button/mutation
    is implemented and gated (`finish the open draft first` / `not your
    turn` / `N action(s) remaining` / `a pending maneuver is open`), and
    the backend validator only accepts endTurn at actions==0 - a state
    this flow never exposes without card effects, so exercising the
    mutation against the live server is deferred to GD-034+ ability
    flows.
- Driver: `tools/s09/run-hud-demo.ps1` - room code redacted from output
  and from published traces, per-process env credentials with a
  command-line audit (`Assert-NoCredentialOnCmdLine`), scoped abort of
  only this run's game (host-ownership + code + ABORTED verified) in a
  `finally`, staged evidence published only after every assertion passed
  (manifest.json sha256 per file, latest.json flip with rollback).

### GD-034 (combat windows over the authoritative server)

- UE automation tests `Unmatched.S09.COMBAT.*` - 8/8 green (role gates,
  defense card pick with expired-deadline block, boost-choice mode with
  mandatory-cannot-decline, mutation echo parsing, per-seat privacy flags
  pre-reveal, seq guard incl. resolve echo + same-seq merge, and the
  double-Enter/discard in-flight gate regression).
- `run/combat-20260926-064623/` - two packaged clients drove a live
  attack -> defense -> resolve cycle against :3120: role-gated traces
  (the defender acted inside the attacker's COMBAT window, resolve in
  COMBAT_RESOLVE), state-specific marker shots (defense `#FF4040`,
  resolve `#40FF40`, result `#40FF80`, 1280x720, swap/negative controls
  asserted to fail), privacy-clean traces, seq convergence, sha256
  manifest. Driver: `tools/s09/run-combat-demo.ps1`.
- **Adversarial-review fixes GD-032/033/034 proven in
  `run/combat-20260926-093359/`** (the current published run):
  - GD-032 (double-fire): `DiscardToLimit`/`SubmitManeuver`/combat
    confirms now re-check the in-flight gate before sending, and the
    flag is synced from the controller **every tick** (a mutation
    reply - e.g. a rejected endTurn - used to clear the controller
    flag after the last applied snapshot, leaving a stale
    `CommandUi.bCommandInFlight=true` that silently blocked the next
    command; first observed as an auto-decline that never sent).
    Regression-tested at UE level (double-Enter suppressed) and
    exercised live by every published demo confirm.
  - GD-033 (reveal rendering): the resolve panel now renders the
    revealed values (`RESOLVE panel revealed: A3+B0 vs D2`) with a
    dedicated `#7CFC00` reveal block - present in the published
    `joiner/s09-combat-resolve-revealed.png` (1186 reveal pixels,
    bbox 8,54-470,108, plus the 928-px resolve marker; independent
    pixel re-check of the manifest file). Pre-reveal frames keep the
    privacy gates green (zero reveal pixels; per-seat value/card
    visibility asserted by the fixture tests). Reaching the live
    post-reveal pause required a backend fix: deck ingest dropped
    `effectDuring` text on ATTACK cards, so `BOOST_CHOICE` ("You may
    BOOST this attack", Second Shot / Noble Sacrifice) never paused
    the combat - `game-initialization.resolveCardEffects` now parses
    ATTACK `effectDuring` too. The non-owner seat keeps the resolve
    window open during the boost pause (revealed values stay
    rendered; premature R stays blocked by the pending queue gate on
    both seats).
  - GD-034 (unbounded waits): defense/resolve/pending/result shot
    waits are bounded at 12s - on timeout the drive logs
    "proceeding WITHOUT the shot" and the driver reports the missing
    file instead of hanging (the demo used to wait forever in
    defense/resolve/pending/discard branches when
    `FScreenshotRequest` never produced a frame).

### GD-035 (queue-head pending-choice UI + authoritative commands)

Client model (`S09ManeuverUi`): the server-side `pendingEffects` queue
is parsed per type; a **viewer-owned head** opens `PendingChoice` mode
at the highest priority (combat windows stay open behind it). A changed
head key (`id|type|stage|mode|chooseCount` - e.g. the CHOOSE_SPACE stage
swap or DECK_TOP_PICK PICK->ORDER swap) resets the draft; carried
selections are revalidated against each fresh snapshot (fighters left
the legal list, cells left the legal set, cards left the hand/revealed
set -> dropped before an illegal confirm is representable). A non-empty
queue (either seat) blocks beginManeuver/maneuver/attack/scheme mirrors
of the server gates; mandatory choices render loud (red header), only
`bOptional` heads expose decline. Unknown types surface
`unsupported pending type '%s' - no legal client command` - never a
client-side fallback payload.

Per-type command surfaces (exact `ResolvePendingEffectDto` payloads):
MOVE/PLACE (own fighter from the legal list + cell from a BFS-legal set,
zero-step legal), CHOOSE_SPACE (both stages, anchor/zone feedback),
TARGET_FIGHTER (legal-fighter list only), CHOOSE_ONE (option index,
multi-step via `chooseCount`), DISCARD_CARDS (exactly `value` distinct
own-hand instance ids), BOOST_CHOICE (exactly one own-hand id or
decline), DECK_TOP_PICK PICK (exactly the revealed instance ids) and
ORDER (all revealed, pick sequence = top->bottom). Opponent privacy is
preserved by construction: revealed ids are read only from the
owner-view projection; a non-owner head renders `revealedCards are not
available to this seat`.

- UE automation tests `Unmatched.S09.PENDING.*` - **10/10 green**
  (parser matrix over the live fixtures incl. privacy fields, malformed
  `pendingEffects` metadata degrading entry-by-entry without a crash,
  MOVE queue gates, DECK_TOP_PICK PICK/ORDER/privacy, CHOOSE_SPACE live
  zones + synthesized zone rule + stage-2 anchor, synthesized TARGET_FIGHTER
  and multi-step CHOOSE_ONE heads, DISCARD/BOOST exact-instance gates,
  live DISCARD_CARDS owner/wait/resolve projections,
  and the seq guard: pending-open apply -> resolve echo apply ->
  same-seq duplicate merge -> stale open ignore).
- Live fixtures (`fixtures/gd035-*.json`, exact HTTP bodies against
  :3120): MOVE head open (both seats + queue view), DECK_TOP_PICK PICK
  owner-view (exact `revealedCards` faces) vs opponent-view
  (`revealedCount` only), DECK_TOP_PICK ORDER, CHOOSE_SPACE stage-1 AND
  stage-2 (both seats; stage 2 captured live since the zone backfill -
  it used to be synthesized-only), and DISCARD_CARDS owner/wait/echo.
  Captured by
  `tools/s09/capture-pending-fixtures.cjs` (2026-09-27 runs; the script
  drives real GraphQL games over HTTP - see the exhaustion note in its
  header for why each capture gets a fresh game).
- **Live vs fixture-only, stated precisely (after the S09 follow-up
  iteration - zone backfill + stage-2 seq fix):**
  - MOVE - proven live end to end (fixtures + packaged demos).
  - CHOOSE_SPACE - **proven live both stages**: board zone data was
    backfilled (`tools/s09/bootstrap-s09-stack.cjs` backfills
    `Board.cells` zones for all seeded boards), and a live
    `resolveChooseSpace` **stage 2 used to crash the server's
    optimistic lock** (`Concurrent modification detected. Expected
    sequence 8, got 8`) because the stage-2 path skipped the
    `sequenceNumber + 1` bump that every other head resolver does -
    fixed in `game-action-executor` with seq assertions added to
    `s06-arthur-cards.spec` (one mutation = +1 seq, both stages).
    Published run 100210 picked CHOOSE_SPACE live.
  - TARGET_FIGHTER - **proven live** in run 100210 (picked; the head
    opens now that boards carry zones).
  - BOOST_CHOICE - **proven live**: the combat run 093359 held the
    post-reveal boost pause over the authoritative server (and a
    pre-publication pending run picked AND declined it; that run's
    decline initially exposed the stale in-flight-flag client bug -
    fixed, see GD-032 above). Live owner/wait fixtures
    (`gd035-boost-*-view`) captured 2026-09-27 from a scripted
    Second Shot attack over real GraphQL commands.
  - PLACE - **proven live 2026-09-27** via the Winged Frenzy revive
    path: a scripted undefended joiner attack defeated a 1-HP Harpy,
    the host then played Winged Frenzy and the server queued the
    per-fighter MOVE heads with an optional revive-PLACE tail
    (`zoneFighterName=Medusa`, `restoreFullHealth=true`,
    `fighterIds=[defeated harpies]` - exact head fields in
    `fixtures/gd035-place-owner-host-view.json`), both seat
    projections were frozen at the pause, and the head was resolved
    live with a zone-legal cell (the capture script's PLACE picker
    mirrors the server's first-free-passable-zone-cell rule). The
    other PLACE producer (Arthur's Bewilderment defense) is exercised
    by the s06 specs; its live capture stays luck-gated on the
    Second Shot + Bewilderment hand coincidence.
  - DECK_TOP_PICK - **proven live in the packaged duel 093227** (the
    earlier note "the auto driver has no picker" is obsolete): the auto
    driver's exact-count card picker (`PendingCardPickPlan`) answered a
    real DECK_TOP_PICK head - the joiner trace shows `S09AUTO pending
    picked (type=DECK_TOP_PICK stage=0)` twice with live
    `PEND-RESOLVE sent type=DECK_TOP_PICK` commands (PICK id
    `...-fullText-0-p0` resolved `PEND resolve done seq=101`, ORDER id
    `...-fullText-0-p0-order` resolved `seq=102`), plus the published
    `joiner/s09-pending-DECK_TOP_PICK-PICK.png` / `-ORDER.png` shots.
    Fixtures (owner/opponent/ORDER views) remain on disk from the
    fixture runs.
  - CHOOSE_ONE - no starter card produces it; synthesized head only.
  - DISCARD_CARDS - captured live after `resolveCardEffects` began parsing
    DEFENSE/VERSATILE `effectAfter`. `fixtures/gd035-discard-owner-joiner-view.json`
    and `gd035-discard-wait-host-view.json` record the two private projections;
    `gd035-discard-resolve-echo.json` records a successful owner choice and
    queue advance. The capture command completed with exit 0 on 2026-09-27.
- `run/pending-20260926-080739/` - first published GD-035 run: live
  MOVE head resolved; the CHOOSE_SPACE zone gap (0/30 boards with zone
  data) was reported as `gapObserved`, not faked.
- `run/pending-20260926-100210/` - **current published run, after the
  zone backfill + stage-2 seq fix**: two packaged clients resolved
  **CHOOSE_SPACE (both stages), MOVE and TARGET_FIGHTER live** over
  the authoritative server (`pendingPicked` in the manifest),
  `gapObserved` empty, first-head UI shot
  `host/s09-pending-TARGET_FIGHTER.png` (672 `#4080FF` samples,
  foreign markers zero, 1280x720), privacy-clean traces, seq
  convergence 95/95 through GAME_OVER-era lengths, sha256 manifest,
  scoped abort verified.

### GD-036 (minimum result screen + full packaged UE duel)

Server (`game-state.service.ts` `saveState`): a terminal state
(`phase === GAME_OVER`) marks the `Game` row `FINISHED` exactly once
(`updateMany` guarded by `status: not FINISHED`; `winnerId` from
`state.metadata.winnerId`, `endedAt` now) and invalidates both seats'
`myGames` cache lists. Before this, a finished duel stayed `IN_PROGRESS`,
so `leaveGame` from the result screen called `abortGame('player_left')`
and a real victory was indistinguishable from an abort. `saveState` is
the single central point (mutations, combat-timeout, AI moves), so the
marking cannot be bypassed. `GameInProgressGuard` then also blocks any
post-terminal mutation.

Client (`S09HudModel` + `S09ManeuverUi` + `S08FlowController` +
`S08FlowGameMode`): the result model derives strictly from the applied
snapshot (`phase == GAME_OVER` + `metadata.winnerId` matched against the
player projection): `bGameOver`, `bWinnerKnown`, `bViewerWon`,
`WinnerHeroName`, `OutcomeWord()` = VICTORY/DEFEAT/DRAW. An abort-shaped
body (the server never writes GAME_OVER for an abort) renders NOTHING - a
presented victory can only come from the server outcome. On the terminal
body `OnSnapshot` collapses every draft (Mode=None; maneuver/discard/
combat/pending state reset - the server cleared `pendingEffects`),
`CanBeginManeuver`/`CanOpenAttackDraft`/`CanIssueGameplayCommand`/
`CanIssueCombatCommand` all fail with "the duel is over", board clicks
are dead, and only L/Enter + the `RETURN TO LOBBY` button stay live
(`leaveGame` sent exactly once). A fresh model over a late/reconnect
snapshot derives the full result with no event replay; a same-seq merge
rebuilds the identical screen (no double-present). The scheme picker
mirrors the server `bannerAllows` gate (singular/plural/numeric-suffix
normalization, own-living-fighter requirement): a scheme whose banner
fighter fell is never re-sent (the 10:41 Merlin loop), Restless Spirits
is preferred only among legal cards.

`DriveS09ResultFlow` (S09AUTO tail): bounded result-screen shot
(`s09-result-screen.png`, #FFD700 marker) -> one `leaveGame` -> HUD clear
on lobby arrival (the terminal panel stops rendering over the lobby) ->
bounded lobby shot (`s09-lobby-return.png`) -> early `RequestExit` - the
10:37 lesson: never idle the run timeout after the evidence exists.

- UE automation tests `Unmatched.S09.RESULT.*` - **5/5 green** over the
  live `gd035-move-open-host-view` fixture (terminal variant swaps only
  `phase` + `metadata.winnerId`, exactly what `applyTerminalState`
  writes): winner/loser/draw/unknown-winner parse for both seats;
  strictly phase-driven (live phase and abort-shaped bodies render
  nothing; fresh-model late arrival; idempotent rebuild); terminal
  snapshot closes drafts + kills model/controller input gates incl.
  equal-seq merge dedupe; scheme banner legality mirror (dead-banner
  schemes unplayable, opponent-banner rejected, unknown banner allowed
  as dirty data, revived banner playable again).
- Backend: `game-state.service.spec.ts` - saveState marks the row
  FINISHED with `winnerId`/`endedAt` exactly once and invalidates both
  seats' caches; a FINISHED row is never re-marked and a live duel is
  never marked. Current full Jest regression: 1278 passed, 14 skipped.
- **Automated packaged two-client duel - current published run
  `run/duel-20260927-132445/`** (`tools/s09/run-duel-demo.ps1`): host Medusa (attack+scheme plan) vs joiner
  King Arthur (defend+resolve+scheme) over the authoritative :3120
  backend - sign-in, room join, placement, maneuvers, attacks with live
  defense/resolve choices, card effects through real pending heads,
  until the server wrote GAME_OVER: BOTH seats rendered the result
  screen (host VICTORY / joiner DEFEAT; header+outcome+support+button
  markers on both, every gameplay state marker zero),
  sent `leaveGame` exactly once each, both received `LEFT room=`, returned to the lobby and exited
  EARLY. Traces privacy-clean (room code redacted, no card ids with
  combat commands), seq convergence 120/120, sha256 manifest (30 files,
  independently rechecked with no mismatches), scoped
  cleanup validated. The manifest gates live attack, defense, resolve,
  scheme, pending choices, both result shots and both clean lobby shots.
  - **Server row is now proven POST-LEAVE (authoritative, not
    trace-derived)**: the backend terminal-state sidecar preserves
    FINISHED rows after `leaveGame`, and the driver's hard gate
    re-queries the row after both clients exited: `FINISHED`,
    `winnerId` matching the presented VICTORY seat (host), BOTH seats
    in `players`, `endedAt` set. FINISHED was ALSO observed live by
    the 1s poll (`LOBBY -> IN_PROGRESS -> FINISHED`); ABORTED never
    appeared.
  - **Lobby visual gate (added after the 2026-09-27 stale-fighter
    miss)**: human inspection of the first 2026-09-27 duel's lobby
    shots found four independently spawned fighter actors + clipped
    labels surviving the board teardown - none of which carry a UI
    marker color, so the marker-only gates passed. Fixes: (a)
    `AS08BoardActor::EndPlay -> ClearChildren` (fighter actors are
    world-spawned, not attachment children, so destroying the board
    alone leaked them); (b) the driver now gates the gameplay region
    (x >= 25%, y >= 12.5%) of each lobby shot to ZERO bright pixels
    (lum >= 120, tolerance 50; a live board measures ~5-9k samples per
     16th of the frame there - calibrated on run 091740). Run 132445:
    bright=0 on BOTH seats.
  - **Stale gameplay toast cleared**: a gameplay action toast (3-5s
    TTL) set just before GAME_OVER used to survive into the 2s-settled
    result capture; `HandleApplied` now clears the toast on every
    terminal apply. Toast-strip probe (bottom-center warm-text pixels)
    on the published result shots: 0 on both seats.
  - **Frame cap, stated precisely**: per-process console command
    `-ExecCmds="t.MaxFPS 30"` on each hidden client (the earlier
    staged `FrameRateLimit=30` write was dropped - the key vanished
    from the file after a run, its effect was unverified, and a
    persisted value overrides the packaged default of 60). Actual
    effective FPS / GPU frame time were NOT measured - no performance
    claim is made. GTX 1060/1660/RX 580 benchmark remains open.
  - **Stats hard gate (live):** the transactional finish path updated both
    participants. The driver required exact counters and K=32 Elo from
     the winner: host gamesPlayed 4->5, gamesWon 4->5, ELO 1256->1267;
     joiner gamesPlayed 4->5, gamesLost 4->5, ELO 1144->1133. Real PostgreSQL
    terminal tests cover win, draw, idempotency, participant mismatch
    and overlapping finishes (9/9).

## Regressions

- [Adversarial review and remaining acceptance](adversarial-review-2026-09-27.md)
  records the P1/P2 fixes, final gates and open human/performance checks.
- Latest headless editor run (2026-09-27, after room-generation and F10
  callback guards): **88/88 green** — `Unmatched.S09.*` 44/44 and
  `Unmatched.S08.*` 44/44. Deferred tests cover an old `startGame`, gameplay
  mutation, room-entry response and same-id rejoin after a newer match takes
  over. Exact log: `run/automation-tests-unmatched-final-guards-20260927.log`.
- Latest backend full Jest run (2026-09-27): **1278 passed, 14 skipped,
  73 suites passed, 2 skipped**. The real PostgreSQL terminal tests ran
  separately on :55434 and passed 9/9; `npm run build` passed. Timeout
  `GAME_ENDED` remains a lossy CUE per the network contract; a publication
  failure cannot roll back the committed terminal state or block subsequent
  cue attempts. `myGames` reads Postgres, including an empty previously
  cached FINISHED list after a failed eviction.
  Exact current logs: `run/automation-tests-unmatched-final-guards-20260927.log`,
  `run/package-final-guards-20260927.log`,
  `run/duel-final-guards-driver-20260927.log`,
  `run/backend-jest-final-20260927.log`,
  `run/backend-terminal-pg-after-review-20260927.log`,
  `run/backend-build-final-20260927.log` and
  `run/capture-v20-20260927.log`.
- The duplicate-instance report was traced to overlapping priority groups
  in the old fixture driver, not to a server hand. Driver v20 dedupes its
  outbound IDs; `s09-card-instance-dup.spec.ts` keeps card IDs unique and
  conserved across 60 seeded duels plus a projection round-trip (61/61).
- Full suite re-run 2026-09-26 after the GD-032/033/034 follow-up
  (fresh logs in `run/`):
  - Historical `Unmatched.S09.*` - **29/29 green** (5 HUD + 8 CMD + 7 COMBAT
    incl. the double-fire gate + 9 PENDING-style checks;
    `run/automation-tests-s09-gd034fix.log` update of the earlier
    gd035 log). Two COMBAT tests were updated for the new resolve
    semantics, deliberately: the privacy-fixture deadline sanity
    check used to rot with fixture age (live-captured 30s/10s windows
    fall out of a hardcoded -3600s clamp; it now re-derives the
    deadline from now and asserts the countdown runs), and the
    boost-choice test now expects the OTHER seat to keep the
    CombatResolve window open during the post-reveal pause (GD-033
    fix) instead of None.
  - `Unmatched.S08.*` - **23/23 green**.
- Backend Jest: **1165/1165, 69/69 suites green** - the previously
  reported 9 baseline failures are gone: the three transport suites
  needed a harness-only `GqlThrottlerGuard` override (the fixture
  module has no ThrottlerModule, so the resolver-level guard failed
  on missing `THROTTLER:MODULE_OPTIONS`), and the auth drift is
  covered by the same full-suite run. New this iteration:
  `game-initialization` parses ATTACK `effectDuring` (BOOST_CHOICE
  cards keep their effects in live games), and
  `game-action-executor` stage-2 CHOOSE_SPACE bumps the sequence
  number (regression-asserted in `s06-arthur-cards.spec`).

## Sensitive data

No tokens, passwords, or joinable room codes in committed evidence; the
driver redacts the room code and the UE trace writer scrubs `Bearer `,
`accessToken`, `refreshToken`, `password=`.

## Reproduction

```powershell
# stack (from backend/): docker codex-s09-postgres:55434 + codex-s09-redis:6381
node tools/s09/bootstrap-s09-stack.cjs   # seeds + backfills Board.cells zone data
node tools/s09/run-with-env.cjs node -r ts-node/register/transpile-only prisma/<seed>.ts
node s09-start.cjs   # backend :3120

# UE automation tests (after building UnmatchedEditor)
node tools/s08/run-ue-tests.cjs

# packaged demo (env credentials; publishes into this directory)
$env:S09_DEMO_HOST_EMAIL=...; $env:S09_DEMO_HOST_PASSWORD=...
$env:S09_DEMO_JOINER_EMAIL=...; $env:S09_DEMO_JOINER_PASSWORD=...
powershell -File tools/s09/run-hud-demo.ps1   # ShotMode request (default) = UI-inclusive capture required by the gates
powershell -File tools/s09/run-combat-demo.ps1   # GD-034 attack->defense->resolve two-client demo
powershell -File tools/s09/run-pending-demo.ps1   # GD-035 queue-head demo (reads backend/.env if env vars are unset)
powershell -File tools/s09/run-duel-demo.ps1   # GD-036 full-duel demo (GAME_OVER -> result screens -> lobby return -> early exit)

# live pending-effect fixtures (GD-035)
node tools/s09/capture-pending-fixtures.cjs

# packaged HUD probe (no backend; fixture-driven; proves key input path)
powershell -File tools/s09/run-hud-probe.ps1
```

## Not proved here

- **Legacy `updateStatsAfterGame` remains unused.** The authoritative
  `saveState` finish transaction now updates `UserStats` itself, proven by
  the 132445 packaged duel and PostgreSQL win/draw tests. The earlier
  093227 sample (unchanged statistics) is superseded.
- **Publish-after-abort race (KNOWN, narrow).** If an abort lands after
  `saveState`'s final status check but before the WS publication, the
  terminal snapshot can publish over an ABORTED row. The sidecar closes
  the earlier cache/startup-rollback/fallback-cancellation holes; this
  window remains and is reported honestly for backend follow-up.
- **t.MaxFPS effect is UNMEASURED.** The per-process console-command cap
  is applied to both hidden clients; no effective-FPS or GPU frame-time
  data exists for this run, and the GTX 1060/1660/RX 580 benchmark
  target remains open. `run/current-pc-gpu-duel-roomguard-20260927.csv`
  captured 10 total-system RTX 4090 samples during an active packaged
  duel (22–40%, mean 26.9%); they cannot establish per-client usage or
  a performance gain.
- **Superseded runs kept for history:** `duel-20260926-114708` (FINISHED
  only trace-provable then - row was deleted post-leave) and
  `duel-20260927-091740` (ran 09:18 on the staged binary predating the
  09:21 EndPlay packaging; its manifest verdict text overclaims a clean
  lobby and a FINISHED row it could not verify - the marker gates
  passed, the stale-fighter class of artifacts was invisible to them).
  The current authoritative automated run is `duel-20260927-132445`;
  runs `duel-20260927-093227`, `-113553`, `-122418`, `-123959`, and
  `-131314` are superseded by later code and gates.
- **Slate mouse path proved in PIE through Unreal MCP.** The packaged
  probe proves the manual *key* route (`ProcessKeyDownEvent` -> viewport
  -> controller -> discard pick, `SLATE-PASS`; direct `InputKey` fallback
  does not count). In [the MCP pointer check](mcp-pointer-review-2026-09-27.md),
  `SlateInspectorToolset.Click` opened both public discard piles and
  inspected owner/public-opponent cards through actual Slate pointer
  events; the hidden opponent placeholder remained faceless. The
  packaged duel driver still drives gameplay picks programmatically,
  and a physical mouse/visual pass in a 1280×720 packaged window is
  a separate owner acceptance check.
- **Human visual pass is OPEN.** All pixel gates (marker regions,
  dimensions, text band heights, panel geometry, the lobby
  gameplay-region brightness gate, the result-screen toast-strip
  probe) are measured programmatically from the published PNGs;
  an agent inspected the images in-session, but a human should eyeball
  the six published captures of run 035408 (private
  hand chips vs count-only opponent line, maneuver vs discard panel
  distinctness, legibility at 1280x720) and the four result/lobby
  captures of run 132445 (result completeness, lobby cleanliness).
  An [agent screenshot inspection](visual-review-2026-09-27.md) confirms the
  panel distinctions but flags overlapping fighter labels; it does not
  substitute for the human pass.
- The auto-handler's first-own-turn condition (the demo loop starting
  maneuvers on the first own turn) lives at GameMode level and has no
  headless test; the underlying model gates it covers are tested
  (`bZeroMove`, boost, exact discard).
- Hero abilities beyond plain maneuvers (tokens/stances/resources,
  GD-034..036) are out of scope for this slice; the `endTurn` mutation
  stays exercised only at the validator/gate level (see above).
- **GD-035 live-coverage status:** boards carry zone data (backfill),
  CHOOSE_SPACE resolves live through both stages, and TARGET_FIGHTER,
  BOOST_CHOICE, PLACE, MOVE, and DECK_TOP_PICK PICK/ORDER have live
  evidence above. DECK_TOP_PICK was resolved by the packaged duel driver
  in run 093227. Still open: no starter card produces CHOOSE_ONE
  (synthesized only). DISCARD_CARDS now has live owner/wait/resolve
  fixtures from the 2026-09-27 capture. The client
  implements no fallback for an unknown pending type.
- The published GD-035 demo run 100210 covered CHOOSE_SPACE + MOVE +
  TARGET_FIGHTER live; BOOST_CHOICE live proof lives in the combat
  run 093359 (reveal pause + revealed panel) and the pre-publication
  pending run.

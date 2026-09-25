# S08 Evidence - UE vertical (GD-028 / GD-029)

## What is proven here

### GD-028 (UE HTTP + authenticated graphql-transport-ws contracts)

- `live-schema.graphql` - SDL dumped from the running backend BEFORE the UE
  operations were written (backend on :3100, worktree-local docker
  Postgres/Redis). Key findings baked into the client:
  - `GameStateResponse.sequenceNumber` / `turnCount` are **Float!** (NestJS
    number) - parsed int-like (`ReadIntLike`).
  - WS `GameState.sequenceNumber` is `Int!`; `updatedAt` (DateTime)
    serializes as epoch-milliseconds.
  - `gameState(gameId).state` is a JSON **string** (two-stage parsing);
    inside it `players`/`fighters` arrive as native JSON **arrays**, the
    rest as objects.
  - WS `gameStateUpdated` ships every projection as a JSON **string** -
    decoded in the second stage (`DecodeJsonStringField`).
  - GraphQL failures arrive as **HTTP 200 + errors[]** and must block the
    parse (fixture 08, UNAUTHENTICATED).
- `fixtures/` - 11 captures from the live backend (login, idempotent
  duplicate create, code resolution, per-viewer gameState, reordered+partial
  body, real WS `next` snapshot, auth failure, not-found, wrong scalar,
  truncated body). Tokens and joinable room codes are redacted in evidence; the capture script
  (tools/s08/capture-fixtures.mjs) works against the live API.
- `run/automation-tests.log` - **23/23 UE automation tests green**
  (`Unmatched.S08`, UnrealEditor-Cmd headless, -nullrhi): the 9 GD-028
  contract tests (login parse, full two-stage gameState parse, Float->int,
  reordered+partial, WS next parse, wrong-scalar, malformed (including a
  truncated trailing escape that previously crashed UE's JSON reader), auth-failure
  errors[], seq guard, critically-incomplete input gate), the GD-030/GD-031
  Phase2 tests (board decode, reach/walls/doors, mutation parse, tile
  groove contract, state store), and the WsOp recovery tests
  (subscription-level `error`/`complete` frames on a healthy socket:
  operation ends + dead id ignored + fresh resubscribe id delivers; flow
  level bounded refetch+resubscribe with give-up bound surfacing through
  OnFlowError; unparseable `next` frames notify the owner and the flow
  recovers boundedly or surfaces a visible error instead of hanging on a
  stale seq).

### GD-029 (BOOT->LOGIN->LOBBY->ROOM grey flow, two packaged clients)

- `run/client-host.trace.log` + `run/client-joiner.trace.log` - two packaged
  Win64 Development clients (Saved/StagedBuilds/Windows, map /Game/S01/Smoke
  with `?game=/Script/Unmatched.S08FlowGameMode`) run hidden against the same
  real backend on :3100:
  - host: login -> createGame (code shown) -> selectHero -> toggleReady
    -> waits for guest -> startGame -> IN_PROGRESS -> HTTP snapshot
    seq=1 ACTION_MANEUVER applied (critical fields valid) -> WS
    gameStateUpdated subscribed since=1.
  - joiner: login -> `gameByCode` resolves the displayed code to a gameId
    -> joinGame -> selectHero -> toggleReady -> sees IN_PROGRESS via
    game(id) polling -> attaches the same snapshot+WS stream.
- Idempotency: createGame carries a stable per-session idempotency key;
  duplicate create returns the SAME room (fixture
  02-create-duplicate-idempotent.json + jest
  s08-lobby-contract.spec.ts).
- Recovery: `myGames(LOBBY)` re-derives an existing room without relying on
  named lobby events (no snapshot barrier on those, unmatched-net/1).

## Sensitive data

Committed evidence contains no tokens, passwords, or joinable room codes
(redacted at capture time; the UE trace writer additionally scrubs
`Bearer `, `accessToken`, `refreshToken`, and `password=`).

## Reproduction

```powershell
# backend (worktree backend/.env, docker postgres:55433 redis:6380)
node -e "require('dotenv').config({path:'.env'}); process.env.NODE_ENV='development'; require('./dist/src/main.js')"

# fixtures (credentials from the environment, see "Repeat-run safety")
#   S08_FIXTURE_HOST_EMAIL=... S08_FIXTURE_HOST_PASSWORD=... \
#   S08_FIXTURE_GUEST_EMAIL=... S08_FIXTURE_GUEST_PASSWORD=... \
#   node tools/s08/capture-fixtures.mjs

# UE automation tests (after building UnmatchedEditor)
& "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" `
  unreal/Unmatched/Unmatched.uproject `
  '-ExecCmds="Automation RunTests Unmatched.S08"' `
  -S08Fixtures=<abs fixtures dir> -unattended -nosplash -nullrhi -log

# two-client packaged demo (builds not included: run UAT BuildCookRun first).
# Credentials come from the orchestrator environment (S08_DEMO_HOST_EMAIL/
# PASSWORD + S08_DEMO_JOINER_EMAIL/PASSWORD); the joiner room code travels
# per-process env only and is redacted from published traces. The demo
# driver validates evidence and aborts its own game in a finally block.
powershell tools/s08/run-phase2-demo.ps1

# offline probe of the demo's scoped-cleanup state machine (mocked HTTP-200
# responses incl. errors[]; verifies ABORTED verification + failure
# propagation; no backend or packaged build needed)
powershell tools/s08/run-phase2-demo.ps1 -ProbeCleanupOnly

# strict validation of the latest published run (exact six artifacts, safe
# basenames, hashes/sizes, PNG 1920x1080, grid verdicts above thresholds,
# host/joiner markers, seq convergence); --selftest runs the negative cases
node tools/s08/validate-evidence.cjs docs/game-design/evidence/S08/run
node tools/s08/validate-evidence.cjs --selftest
```

Repeat-run safety: the demo driver aborts the game it created in a `finally`
block (scoped to the game id parsed from THIS run's host trace, host
ownership + room code validated against the API before `abortGame`; failed
runs clean up too). Every cleanup-side GraphQL response is checked for
HTTP-200 `errors[]`, the abort only counts after the terminal ABORTED
status was verified for precisely this game id, and a failed scoped cleanup
propagates (the demo exits nonzero instead of counting it as success) —
the `-ProbeCleanupOnly` mock probe pins those paths offline. No other room
is touched, and no manual cleanup between runs is needed — six successive
create+cleanup cycles plus a 7th create were verified against the
five-active-game cap. `capture-fixtures.mjs` applies
the same scoped abort to its own room and FAILS (rather than purging) if
creation ever hits the cap; its credentials come from the environment
(`S08_FIXTURE_HOST_EMAIL/PASSWORD`, `S08_FIXTURE_GUEST_EMAIL/PASSWORD`).

The original GD-029 grey-only driver (`tools/s08/run-grey-demo.ps1`) was
REMOVED: it passed the joinable room code on the joiner's argv and echoed
it to the console. The phase-2 driver is a strict superset (env-only code,
scoped cleanup, evidence validation) and is the supported reproduction
path; the archived GD-029 traces below remain as evidence.

## Known limitations

- The joiner auto-flow polls `game(id)` every 3 s to observe the start
  (named lobby events are CUE-only by design).
- `gameByCode` returns null for unknown/full/started codes alike
  (deliberate: no room enumeration).
- Heroes are picked from `heroList` (prisma cuid ids); the content
  `heroes` query serves a different slug id space and is NOT valid for
  selectHero.

## Phase-2 handoff (GD-030 board / GD-031 state store)

- GD-030 renders from `FS08Snapshot.BoardState`
  (decoded `{width,height,cells,doors}`) + `Fighters` projection. The S08
  runtime map is **/Game/S08/S08Arena** (see "S08 assets" below) and since
  the S08 review pass it is also the SHIPPED default:
  `DefaultEngine.ini` sets `GameDefaultMap`/`EditorStartupMap` to
  `/Game/S08/S08Arena` and `GlobalDefaultGameMode` to
  `/Script/Unmatched.S08FlowGameMode` — the staged exe boots straight into
  the S08 flow with no map override (verified from the packaged build's
  `S08_FLOW_READY map=S08Arena` boot line). `/Game/S01/Smoke` stays
  untouched for the S01 smoke pipeline (explicit-map loads are unaffected;
  S05 map entries return at their integration sprint).
- GD-031 consumes `FS08FlowController::ApplySnapshot` (seq guard +
  merge-never-replace + `ValidateCriticalFields` input gate) as the single
  state-store entry point; `IsInputBlocked()`/`GetCriticalProblems()` drive
  the action gate.

## S08 assets tracked in git (Content/ is gitignored - force-add exactly these)

- `unreal/Unmatched/Content/S08/S08Arena.umap` - dedicated S08 map
  (duplicate of S01 Smoke via editor AssetTools with the 30 S01 cell actors
  removed; the 20x20 board, camera and lighting come from
  `AS08FlowGameMode`/`AS08BoardActor` at runtime, so the map carries no
  scene-specific actors).
- `unreal/Unmatched/Content/S08/M_S08_Solid.uasset` - solid/emissive
  material (underlay, team bases, fighter capsules).
- `unreal/Unmatched/Content/S08/M_S08_Tile.uasset` - tile material with the
  groove gradient (readable-grid contract).
- Packaging (`MapsToCook` / `DirectoriesToAlwaysCook` in
  `unreal/Unmatched/Config/DefaultGame.ini`) depends ONLY on the
  committed-intent S08 assets: `/Game/S08/S08Arena` is the sole cooked map
  and `/Game/S08` is always-cooked. The previously cooked `/Game/S01/Smoke`
  map is ignored/untracked in this worktree and was removed (S05 map entries
  return at their integration sprint); the invalid
  `/Engine/Content/EngineMaterials` stage path was also removed.
  `tools/s08/package-client.ps1` gates packaging on the three S08 binaries
  existing and warns that `Content/` is gitignored (they must be force-added
  at commit time or a clean checkout cannot cook S08).

## Phase-2 run (GD-030 board readable / GD-031 maneuver+reconnect), 2026-09-26

Two hidden packaged Win64 Development clients (`-RenderOffScreen`) against
the real backend on :3100, map `/Game/S08/S08Arena` with
`?game=/Script/Unmatched.S08FlowGameMode`, driven by
`tools/s08/run-phase2-demo.ps1` (rebuild+package first via
`tools/s08/package-client.ps1`).

Evidence layout (rollback-safe publish): every run lands in its own complete
versioned directory `run/run-<stamp>/` containing the six artifacts plus a
`manifest.json` (per-file sizes + SHA-256 over the published bytes — traces
carry the room code redacted to `<redacted>`). The canonical current run is
pointed at by `run/latest.json`, flipped only after ALL trace/shot/grid
assertions passed: a unique temp file in the same directory, then
`[IO.File]::Replace` against the existing pointer (`[IO.File]::Move` for
the first publish) — a single rename-class swap with no window in which
the destination is missing; no stronger crash-atomicity is claimed (a
crash mid-sequence leaves an orphan `.tmp` and the previous pointer
intact). A failed run anywhere before the flip leaves the previous
`latest.json` target and its run directory untouched. Only the directory
named by `latest.json` is committed as phase-2 evidence; older runs and
`run/_pre-versioning/` are local diagnostics and are not part of Git.

- `phase2-client-host.trace.log` — login -> create (room code redacted at
  publish) -> hero -> ready -> startGame -> SNAPSHOT seq=1 -> one legal
  maneuver: `MANEUVER begin seq=2` -> `CUE move f-0-hero (2,2)->(3,2) seq=3`
  -> `MANEUVER done seq=3 fighters=6`. The joiner receives the room code via
  the per-process environment (`S08_ROOM_CODE`), never argv, and the driver
  audits the process command lines for credentials and the code.
- `phase2-client-joiner.trace.log` — join by code -> hero -> ready ->
  forced transport loss `WS DROPPED` -> `WS closed` -> bounded backoff
  `WS reconnect attempt` -> `WS reconnected` + refetch + resubscribe
  `since=1` -> converges on the same maneuver (same max applied seq on
  both clients).
- `phase2-board-host-1920x1080.png` + `...-joiner-1920x1080.png` —
  1920x1080 HighResShot per client after the board settles; all 6 fighters
  (2 heroes + 4 sidekicks) are logged projected+alive at their cells (the
  driver asserts exactly 6 `SHOT fighter ... projected=1 alive=1` lines per
  client plus the `FIGHTERS synced n=6` trace line; silhouette shapes in
  the PNGs additionally get a documented manual review — the image checker
  alone proves grid + team colors, not fighter count).
  Each client writes its own explicit `-S08Shot` path; the driver verifies
  the file is fresh from that run (mtime after the client process start)
  and refuses to copy staged `HighresScreenshot*` leftovers.
- `*-grid.json` — `tools/s08/check-board-shot.ps1` verdicts (20x20 grid
  grooves resolvable on both axes, team base pixels present both sides
  INSIDE the detected board box, `pass: true` for both shots), saved UTF-8;
  exact counts per run are in each run's grid json files.

## Grid checker proof: positive AND negative control

- Positive: the two fresh per-client shots above (current run: 14 vertical /
  19 horizontal grooves, both `pass: true`, above the 12/10 thresholds).
- Negative: `tools/s08/fixtures/flat-board-negative-1920x1080.png` (kept in
  git, regenerable via `tools/s08/make-flat-negative.ps1`) is a synthetic
  flat board - uniform grey slab, NO grooves, blue+red team patches painted
  OUTSIDE the slab on a non-black background. Since the team-pixel scan is
  bounded to the detected board box, the patches do NOT count (bluePx/redPx
  0) and the checker FAILS it on all four reasons (0 vertical < 12,
  0 horizontal < 10, 0 blue < 150, 0 red < 150) with exit code 1:

  ```powershell
  powershell tools/s08/make-flat-negative.ps1
  powershell tools/s08/check-board-shot.ps1 -Path tools/s08/fixtures/flat-board-negative-1920x1080.png
  # -> pass: false, exit 1 ("solid slab?")
  ```

## Editor MCP server (opt-in per session)

`Config/DefaultEditorPerProjectUserSettings.ini` keeps the Unreal MCP plugin
available but does NOT auto-start its HTTP server with every editor open
(no project-wide 8123 listener by default). For scene/asset work in an
editor session, start it explicitly from the editor console:

```
ModelContextProtocol.StartServer        ; default port from settings (8123)
ModelContextProtocol.StartServer 8123   ; explicit port
ModelContextProtocol.StopServer         ; stop it again
```

The server binds loopback only. Flip `bAutoStartServer=True` in that ini
only while an entire editor session should expose MCP by default.

## Open limitations

- The groove thresholds (12 vertical / 10 horizontal) were tuned on this
  workstation's GPU raster; a benchmark on the target low-end hardware
  (GTX 1060 / GTX 1660 / RX 580) is still open.
- Grid readability is verified by the luminance-profile checker, not by
  human acceptance - art-direction sign-off of the tile/groove look
  remains open.

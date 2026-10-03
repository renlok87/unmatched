# M1 live run, 2026-10-04: boost card + three fighters

Verdict: **not passed.** The host never began the maneuver. Milestone M1 stays open; see
`docs/game-design/move-selection/05-implementation-plan.md` §2, row M1.

## Setup

- Package: commit `ebc661df` (`BuildStamp.json`, sourceHash `8df07b4b…`). It adds the driver plan
  `-S08ManeuverPlan=boost3` (`FS09MoveInput::RunAutoManeuverPlan`).
- Backend: local dev docker on `:3000`, rebuilt to HEAD before the run (`docker exec unmatched-backend npm run build`,
  then `docker compose restart backend`).
- Run: `tools/s08/run-phase2-demo.ps1 -Api http://localhost:3000/graphql -ClientExtraArgs '-S08ManeuverPlan=boost3'`.
  - No `-ArtPreviewBoardId`, so the host gets `-S08Maneuver -S08ManeuverAfter=25`.
  - Two offscreen clients at 30 FPS, under the GPU lock `owner=M1-LIVE`.
  - The `S08_DEMO_*` accounts were placed in the child environment only.
- Heroes: the host plays Medusa (three Harpies); the joiner plays King Arthur (Merlin).

## What happened

Traces are in `run-20261004-034059-failed/`. The room code is redacted, and `*.trace.log` files were renamed to
`*.trace.txt` because `*.log` is gitignored.

- `AUTO maneuver plan=boost3 armed`: the flag reached the host.
- `BOARD 5x6 cells`: the default board on `:3000` is now Cobble City 5×6, not the 20×20 grid the stock demo expects.
- The board's opening placement surrounds Medusa at (2,2). This follows from the backend start corner and
  `findSidekickCell` on the Cobble zones; the traces carry no positions.
  - Harpies on (1,2), (3,2) and (2,1);
  - King Arthur on (2,3).
- `AutoManeuverTarget` therefore found no hero step, and the one-step driver returned silently on every poll. There is
  no `MANEUVER begin` line.
- Both clients stayed on `SNAPSHOT applied seq=1`. Neither took a shot, because those wait for a settled maneuver or a
  cue. The script failed on the missing host shot and then aborted this run's game (`status=ABORTED (verified)`).

## Fix and next step

- Commit `ce41dfa6`: with a plan, the driver begins without a pre-draft when the hero has no step
  (`FS09MoveInput::AutoManeuverBegins`). The plan then fills the draft, sidekicks first.
- The fix is covered by the boxed-hero case in `Unmatched.S09.MoveSel.AutoManeuverPlan` (the exact Cobble 5×6 opening).
  UE `Unmatched.S09` + `S08`: 247/247.
- Still needed: one package from `ce41dfa6`, then one live run.
- Judge that run by its traces. The script's `BOARD 20x20` gate and the 20×20 grid check of `check-board-shot.ps1` do
  not fit the 5×6 board. The host trace must show:
  - `AUTO maneuver plan=boost3 ok=1 moves=3 boost=<id> …`;
  - `MANEUVER-CONFIRM moves=3 boost=card`;
  - `MANEUVER done seq=… boost=card`.
- The joiner trace must show `CUE move` lines, and both clients must reach the same last applied seq.

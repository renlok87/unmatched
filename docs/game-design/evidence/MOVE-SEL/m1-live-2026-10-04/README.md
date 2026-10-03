# M1 live run, 2026-10-04: boost card + three fighters

Verdict: **passed**, on Marmoreal · original map, run `run-20261004-035600/`. That run closes the last open item of
milestone M1 (`docs/game-design/move-selection/05-implementation-plan.md` §2, row M1).

User decision of 2026-10-04: «Давай оставим только доски, которые осуществлены на реальных досках из игры.» So only a
run on a real map counts. The two runs on Cobble City 5×6, the default board on `:3000`, are history only.

## Setup of the run that counts

- Package: commit `606e7ec0`, read from `BuildStamp.json` (sourceHash `cb25fab2…`). It contains the driver plan
  `-S08ManeuverPlan=boost3` (`ebc661df`) and the boxed-hero begin (`ce41dfa6`).
- Backend: the local dev docker on `:3000`, built at HEAD. The backend code has not changed since.
- Board: Marmoreal · original map, Board row `c121b47f8d6eb28daccb76d05`, registry entry `marmoreal-original`.
  The board has 31 spaces and 42 links.
- Command, run under the GPU lock `owner=M1-LIVE2`:

  ```
  tools/s08/run-phase2-demo.ps1 -Api http://localhost:3000/graphql -ArtPreviewBoardId c121b47f8d6eb28daccb76d05
    -HostManeuver -ClientExtraArgs '-S08ManeuverPlan=boost3'
  ```

  - `-HostManeuver` (commit `48051537`) is a new opt-in switch. The art-board path drops the host's
    `-S08Maneuver -S08ManeuverAfter=25` unless it is set.
  - Two offscreen clients run at 30 FPS.
  - The `S08_DEMO_*` accounts go into the child environment only.
- Heroes: the host plays Medusa with three Harpies; the joiner plays King Arthur with Merlin.
- Script verdict: all map-board gates passed and the evidence was published. The pixel check passed for both shots.
  The run's game was aborted (`status=ABORTED (verified)`).
- The script published `*.trace.log`. Those files were renamed to `*.trace.txt` because `*.log` is gitignored; their
  bytes are unchanged, so `manifest.json` still lists the old names with the same hashes. The room code is redacted.

## Trace lines (run-20261004-035600)

Host, `phase2-client-host.trace.txt`:

```
2026.10.03-22.56.30 AUTO maneuver plan=boost3: the hero has no free step - begin without a pre-draft
2026.10.03-22.56.30 MANEUVER begin seq=2 (apply) pending=maneuver:1:1
2026.10.03-22.56.30 AUTO maneuver plan=boost3 ok=1 moves=3 boost=cmq7d7b4200rcwi74qgawzf62::0 value=4 maxRequired=4 sidekicks=3 confirmable=1 list=f-0-sk0@M24:7/7,f-0-sk1@M21:1/7,f-0-sk2@M02:1/7
2026.10.03-22.56.30 MS-PATH fighter=f-0-sk0 steps=7 allowance=7 key=canonical cells=M07>M08>M09>M15>M10>M19>M16>M24
2026.10.03-22.56.30 MANEUVER-CONFIRM moves=3 boost=card
2026.10.03-22.56.30 MANEUVER done seq=3 (apply) fighters=6 boost=card
```

Joiner, `phase2-client-joiner.trace.txt`:

```
2026.10.03-22.56.30 CUE move f-0-sk0 (0,1)->(6,3) seq=3
2026.10.03-22.56.30 CUE move f-0-sk1 (0,3)->(1,3) seq=3
2026.10.03-22.56.30 CUE move f-0-sk2 (0,0)->(1,0) seq=3
```

What these lines show:

- Convergence: both clients end on max applied seq 3 (`convergence: host max applied seq=3 joiner max applied seq=3`
  in `demo-stdout.txt`).
- No server rejection: there is no `MS-REJECT`, `MANEUVER failed` or `why.client.desync` line.
- The boost is spent: the far Harpy goes 7 steps on base 3 + BOOST 4.
- The boxed-hero begin was needed here too. Medusa starts on M13 with no free neighbour, so the plan moved the three
  Harpies.

## History: Cobble City 5×6 (does not count)

- `run-20261004-034059-failed/`: package `ebc661df`. The host never began the maneuver.
  - Cobble's opening surrounds Medusa at (2,2): Harpies on (1,2), (3,2) and (2,1), King Arthur on (2,3). This follows
    from the backend start corner and `findSidekickCell`; the traces carry no positions.
  - The one-step driver therefore waited silently until the run ended.
  - Fixed in `ce41dfa6`: with a plan, the driver begins without a pre-draft.
- `run-20261004-035208-cobble/`: package `606e7ec0`. Every trace criterion held: `ok=1 moves=3`, the boost card,
  `MANEUVER done seq=3 … boost=card`, three `CUE move` lines on the joiner, and seq 3 on both clients.
  - The script failed only on its synthetic `BOARD 20x20` gate.
  - Only the traces and the stdout are kept.

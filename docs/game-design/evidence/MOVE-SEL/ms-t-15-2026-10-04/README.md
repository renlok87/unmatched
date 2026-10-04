# MS-T-15 evidence, 2026-10-04: move cues with path, order, kind and source

Verdict: **passed**. The task row is `docs/game-design/move-selection/05-implementation-plan.md` MS-T-15. It closes
MS-R-48 and MS-R-60 and the MS-T-15 part of MS-AT-25 and MS-AT-28.

The animation half of MS-AT-25 and MS-AT-28 belongs to later tasks:
- MS-T-16: `jump_to_final`, the Tomoe damage cascade after the animation, snapping and the speed setting;
- MS-T-18: the step sound.

## What was built

- `FS08Cue` carries `Path` (with the start), `OrderInSeq`, `Kind` (Move/Place) and `PathSource` (Trail, Canonical or
  Straight).
- `FS08FlowController::ComputeCues` follows the table in 04 §4.6:
  - the `metadata.lastMovement` trail of the same seq;
  - otherwise the canonical path on the positions before the snapshot, with no step limit;
  - otherwise a straight line from → to;
  - a seq gap or a barrier body still fires no cue.
- MS-T-15 sets the rule for a trail entry that does not match the snapshot (04 §4.6, "Уточнение MS-T-15"). The cue
  falls back to the canonical path and the trace line ends with `trail=mismatch`.
- One `MS-CUE move` trace line per moved fighter. Its `start` / `ms` / `snapped` fields come from the 04 §6.3 schedule
  (`FS08MoveCueSchedule`, Normal speed).
- Contract CUE-007:
  - `cue-table.json` and its schema carry `cap_subject_ms` 1400, `cap_seq_ms` 2400, `min_step_ms` 90, `overlap` 0.3,
    `place_ms` 240 and `params`;
  - in `cue_contract.py`, `move_schedule` drives the reference dispatcher's `_duration`;
  - `check-trace` gates the `MS-CUE` lines with codes M1..M5 (`CUE-DISPATCHER.md` §6).

## Tests and builds

See `ue-tests.txt`. In short:
- UnmatchedEditor (`-NoXGE -MaxParallelActions=2`) and the Unmatched game target (`-NoXGE -MaxParallelActions=4`) both
  end with `Result: Succeeded`.
- Headless `Unmatched.S08` + `Unmatched.S09`: **248/248**. The baseline was 246; the two new tests are
  `Unmatched.S08.MoveAnim.CueSource` and `Unmatched.S08.MoveAnim.CueTrace`.
- `cue_contract.py`:
  - `validate-table` PASS;
  - `run-fixtures` 13/13, including the new `move-seq-caps`;
  - unit tests 23/23 (pytest and unittest);
  - `check-trace` on the automation log of the UE run: PASS with 25 `MS-CUE` lines in 13 seq sets. The C++ schedule
    agrees with the Python one.

## Live run (counts)

- Package: built once from commit `fd585184`. `BuildStamp.json` gives sourceHash `b7714a18…`, 137 files. The staged
  game binary is the game-target build of this session.
- Backend: the local dev docker on `:3000`, at HEAD. It was not changed.
- Board: Marmoreal · original map, row `c121b47f8d6eb28daccb76d05`, profile `marmoreal-original` (31 spaces, 42
  links). This is the demo default.
- Command, run under the GPU lock `owner=MST15`. The lock was taken after the t43 runner had exited and was removed by
  its owner afterwards.

  ```
  tools/s08/run-phase2-demo.ps1 -Api http://localhost:3000/graphql -HostManeuver -ClientExtraArgs '-S08ManeuverPlan=boost3'
    -EvidenceDir docs/game-design/evidence/MOVE-SEL/ms-t-15-2026-10-04
  ```

  - Two offscreen clients run at 30 FPS.
  - The `S08_DEMO_*` accounts were read from the env file into the child environment only.
- Script verdict:
  - exit 0, with every map-board gate passed;
  - convergence: `host max applied seq=3 joiner max applied seq=3`;
  - the run's game was aborted (`status=ABORTED (verified)`).
- Run directory: `run-20261004-054311/`.
  - The script published `*.trace.log`. Those files were renamed to `*.trace.txt` because `*.log` is gitignored. Their
    bytes are unchanged, so `manifest.json` still lists the old names with the same sha256: host `4e54bc79…`, joiner
    `2bbc4249…`.
  - The room code is redacted by the script.
  - `demo-stdout.txt` is the script output. `check-trace.txt` is the gate on both traces.

### Proving lines

Author, `phase2-client-host.trace.txt` (the paths the host's draft sent):

```
MS-PATH fighter=f-0-sk0 steps=6 allowance=6 key=canonical cells=M07>M01>M02>M03>M04>M05>M06
MS-PATH fighter=f-0-sk1 steps=1 allowance=6 key=canonical cells=M20>M21
MS-PATH fighter=f-0-sk2 steps=1 allowance=6 key=canonical cells=M01>M02
AUTO maneuver plan=boost3 ok=1 moves=3 boost=cmq7d7b4500riwi74bl62p4i9::2 value=3 maxRequired=3 sidekicks=3 confirmable=1 list=f-0-sk0@M06:6/6,f-0-sk1@M21:1/6,f-0-sk2@M02:1/6
MANEUVER done seq=3 (apply) fighters=6 boost=card
```

Opponent, `phase2-client-joiner.trace.txt` (the snapshot arrived over WS):

```
2026.10.04-00.43.41 MS-CUE move seq=3 fighter=f-0-sk0 order=0 of=3 kind=move steps=6 source=trail start=0 ms=1400 snapped=0 path=M07>M01>M02>M03>M04>M05>M06
2026.10.04-00.43.41 MS-CUE move seq=3 fighter=f-0-sk1 order=1 of=3 kind=move steps=1 source=trail start=980 ms=280 snapped=0 path=M20>M21
2026.10.04-00.43.41 MS-CUE move seq=3 fighter=f-0-sk2 order=2 of=3 kind=move steps=1 source=trail start=1176 ms=280 snapped=0 path=M01>M02
```

What these lines show:

- The three moved Harpies come from the trail, in the author's `moves[]` order (0, 1, 2).
- Every opponent path equals the author's `MS-PATH` cells, space for space. Harpy 1 passes M01 and M02, where its
  allies stand.
- The timing follows 04 §6.3:
  - 6 steps hit the 1400 ms fighter cap;
  - the next fighters start at 980 and 1176 ms (30 % overlap);
  - the total is 1456 ms, under the 2400 ms seq cap, so nothing snaps.
- The host writes the same three lines for its own maneuver. The legacy `CUE move` lines are unchanged.
- There is no `MS-REJECT`, `MANEUVER failed` or `why.client.desync` line in either trace.
- `check-trace --min-ms-cue 3` passes on both traces (`check-trace.txt`).

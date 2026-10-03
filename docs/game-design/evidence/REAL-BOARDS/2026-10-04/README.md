# Real boards only: UE, tools and demos, 2026-10-04

Verdict: **passed**. Both packaged two-client demos ran with **no board argument** and defaulted to Marmoreal ·
original map (Board row `c121b47f8d6eb28daccb76d05`, profile `marmoreal-original`). Every map-board gate held.

User decision of 2026-10-04: «Давай оставим только доски, которые осуществлены на реальных досках из игры.»
Decision record: `docs/game-design/decisions/2026-10-04-real-boards-only.md` (НД-4, НД-5, НД-6).

## What changed (commits on `fix/admin-panel`)

| Commit | Content |
|---|---|
| `ea09b99c` | UE board data and code, plus the tools that read them. Profiles rev 21 keep only the two original maps; the `cobble-5x6-mesh` surface is removed; `-Bench` defaults to Marmoreal; Art Tuner blocks are re-anchored by board id; tests are updated; the ART FIXTURE output is retired. |
| `284e6e52` | Demos: `run-phase2-demo.ps1` and `run-hud-demo.ps1` default to Marmoreal; the client gets `-S08BoardId`; the S09 step fallback is added; `check-board-shot.ps1` is deleted. |
| `f859f04b` | Tool defaults and docs: Art Tuner launcher and doc, LIVE-TUNE, `art004_live_k2`, `t52` marked HISTORICAL. |

## Build and package

- UnmatchedEditor: `Result: Succeeded`, built with `-NoXGE -MaxParallelActions=2`.
  - The first attempt ran through XGE, which ignores the action cap, and failed with C3859/C1076 (PCH memory). It was
    not a code error.
- Game target Unmatched Win64 Development: `Result: Succeeded`, built with `-NoXGE -MaxParallelActions=4`.
  - `Unmatched.Build.cs` was changed, so the makefile was regenerated.
- UE automation, headless (`Unmatched.S08+Unmatched.S09`): **246/246** (the last baseline was 247).
  - The committed art-fixture test was removed.
  - The Cobble legacy test became the in-code blue/red zone-mark geometry test.
- pytest `tools/art/tests` + `tools/art/map_surface`: 570 passed, 3 skipped (pre-existing skips).
- Package, built once after the last code commit: `tools/s08/package-client.ps1 -SkipBuild`, `UAT_EXIT=0`.
  - Stamp: commit `f859f04b`, sourceHash `033d845c…`, 136 files (`BuildStamp.json` here).
  - The staged inner exe has the same sha256 as `Binaries/Win64/Unmatched.exe`.
  - The pak lists `Config/ArtBoards/S08ArtBoardProfiles.json` plus `S08BenchMarmoreal.json` and
    `S08BenchSarpedon.json`. There is no `S08BenchCobble.json`.

## Runs

Both runs used the GPU lock `owner=BOARDS-UE` and the backend on `:3000`.

- Each run had two hidden clients (`-RenderOffScreen`) at 30 FPS.
- The `S08_DEMO_*` accounts were read from `C:/tmp/wt-envmaps/backend/.env` into the child environment only. The HUD demo
  got them as `S09_DEMO_*`.
- `*.log` files were renamed to `*.txt` because `*.log` is gitignored. Their bytes are unchanged, so each `manifest.json`
  still lists the old names. The room codes in the traces are redacted.

### `phase2/`: `run-phase2-demo.ps1 -Api http://localhost:3000/graphql` (no board argument)

The default board came from the script itself (`demo-stdout.txt`, `art-preview-status.json` `"boardIdDefault": true`):

```
art board: profile=marmoreal-original boardId=c121b47f8d6eb28daccb76d05 source=default size=7x6 light=marmoreal-night map=Marmoreal spaces=31 links=42
art-preview boardId verified against the authoritative game row
convergence: host max applied seq=1 joiner max applied seq=1
cleanup: aborted THIS run's game id=cmut1rjnt000lln4mwb84m407 status=ABORTED (verified)
```

Host trace (`run-20261004-045238/phase2-client-host.trace.txt`):

```
CREATE boardId=c121b47f8d6eb28daccb76d05 source=ArtPreviewBoardId
ARTPREVIEW board assets ready tiles=1 zoneMaterials=2
ARTPREVIEW board profile=marmoreal-original match=boardId board=7x6 boardId=c121b47f8d6eb28daccb76d05 surface=map-image light=marmoreal-night artFixture=0 map=Marmoreal
ARTPREVIEW board active profile=marmoreal-original 7x6 surface=map-image map=Marmoreal spaces=31 links=42 starts=4 ... expectOk=1
BOARD 7x6 cells | control points: (0,0)=(-319,-228,0) (6,5)=(300,250,0) | neighbor pair (dist 89 uu)
BOARD topology spaces=31 links=42 starts=3:M03,4:M11,1:M13,2:M31 ...
ARTPREVIEW reachable rings cells=8 placed=1 ...
```

- The joiner shows the same board lines, plus `WS DROPPED`, `SUBSCRIBED gameStateUpdated` and `WS reconnected`.
- The art pixel check passed on both 1920×1080 shots.
- Six fighter centres were in frame.
- The 'board assets ready' line no longer carries `cobbleMesh=`: the Cobble slab is gone.

### `hud/`: `run-hud-demo.ps1 -Api http://localhost:3000/graphql` (no board argument)

```
board: profile=marmoreal-original boardId=c121b47f8d6eb28daccb76d05 source=default size=7x6 spaces=31 links=42
boardId verified against the authoritative game row: c121b47f8d6eb28daccb76d05 (marmoreal-original)
markers host: draft magentaRegion=940 cyanAll=0 | discard cyanRegion=600 magentaAll=0 | idle magenta=0 cyan=0
markers joiner: draft magentaRegion=940 cyanAll=0 | discard cyanRegion=600 magentaAll=0 | idle magenta=0 cyan=0
convergence: host maxSeq=156 joiner maxSeq=156 | TURN_END views host=24 joiner=24
cleanup: game cmut1uq47001hln4m64a4spe3 already terminal (FINISHED)
```

Host trace (`run-20261004-045507/hud-client-host.trace.txt`):

```
CREATE boardId=c121b47f8d6eb28daccb76d05 source=S08BoardId
BOARD topology grey view 7x6 spaces=31 links=42 discs=31 bars=42 canvas=891.3x577.3 pick=QueryOnly lattice=0
BOARD 7x6 cells | ...
BOARD topology spaces=31 links=42 starts=3:M03,4:M11,1:M13,2:M31 ...
S09AUTO step fallback fighter=f-0-hero from=M13 to=M08 steps=2 allowance=3 (no free neighbour)
S09AUTO multi-fighter moves=2
MANEUVER-CONFIRM moves=2 boost=none
```

- The HUD demo creates the room with `-S08BoardId` and no `-ArtPreview`, so the HUD runs on the grey topology view of
  the map. Its marker gates are those of the earlier grey 20×20 runs.
- Medusa opens on M13 boxed in by her Harpies. Before this change the one-step driver could not move her, and the
  `moves=1` / `moves=2` gates were unreachable. The driver now moves her through her allies to the nearest free space.
- Neither trace has a `20x20` line.

## Kept on purpose

- **Fixture 04** (`docs/game-design/evidence/S08/fixtures/04-game-state-query-host.json`, the 20×20 server state) and
  every test on it. It is test data, listed under "not touched" in the decision.
- **Rule lattices** of `gen-move-fixtures`: the `*cobble*` and `*grid20*` move fixtures, MoveParity and S09 move
  selection.
- **In-code test geometry**: `MakeBoard(5, 6)`, the blue/red grid of the zone-mark test, the T. Rex 7×5 obstacle layout
  in AutoApproach, and the 278×328 tray size in the Diorama tests.
- **`/Game/ArtTests/ART005*` content and its cook entries**. The maps still use the ART-005H corner brackets and iron,
  the ART-005 glyph material, the zone MIs and the glyph meshes. The ART005E/F/G slab assets are no longer loaded, but
  no uasset was deleted. Their `DirectoriesToAlwaysCook` entries also stay: removing them changes the pak and needs a
  separate package.
- **The `tiles` grid surface** in the client. No profile ships one now; the parser and actor stay generic.
- **`validate-evidence.cjs`**, for the historical S08 20×20 evidence; its header says so.
- **`t52_art3_live.py`**, marked HISTORICAL and not rebased.
- **History docs and comments** that mention Cobble, and **"cobble" as the stone material** and `cobble-fog`.
- **`run-combat-demo.ps1` and `run-vs-ai-demo.ps1`**: unchanged. Without a board id they use the backend default
  (Marmoreal since НД-1) and assert no board size; the combat demo's `-ArtPreviewBoardId` path already gates map
  boards.
- **Art Tuner overrides**: there was no local `S08ArtTuner.overrides.json` in any checkout, so nothing needed
  migrating. Both the client and `art_tuner_fold.py` now re-anchor a saved block by board id.

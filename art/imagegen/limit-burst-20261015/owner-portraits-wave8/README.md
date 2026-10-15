# CP-34 — four blocked owner portrait calls; no PNG

Black Panther, Black Widow, Doctor Strange and Elektra were checked as real missing owner portrait keys, then each requested once by its explicit real character name using only its current project canonical front reference. Four independent built-in image_gen calls ran in one parallel batch after root GO. Every call returned HTTP400 `moderation_blocked` at output stage, category `other`. No PNG or source portrait candidate was created.

| Character | Key | Actual result | Request ID |
| --- | --- | --- | --- |
| Black Panther | `portrait:black-panther` | blocked; no PNG | `6a717c68-a0c4-4193-9fca-913ae9b9ed58` |
| Black Widow | `portrait:black-widow` | blocked; no PNG | `9229a7d0-9bfc-427b-9310-aadfdce3f959` |
| Doctor Strange | `portrait:doctor-strange` | blocked; no PNG | `b5d45fc8-1e4b-40b1-aec0-6c0db2675dc3` |
| Elektra | `portrait:elektra` | blocked; no PNG | `8b31205a-81c0-4d58-b27b-065e2de417ba` |

Exact prompts and tool arguments were saved before calls. Each `tool-error-g1.json` retains the actual error string plus structured error code and request ID. `generation-records.json` contains all four attempts with null original/output paths and selected hashes. No correction, euphemistic rewrite, moderation bypass, paid fallback or synthetic placeholder was attempted.

The four canonical reference PNGs were personally opened before calls; all heads were present. Source path and actual SHA are bound in `preflight.json` to the latest matching current-PNG acceptance cards. Black Widow has two pass8.1 cards and a paired final. Black Panther return6.9, Doctor Strange return6.9 and Elektra return7.5 each have a separate recorded user proceed1b override. Those overrides do not change the returned verdicts. Historical source README/checker limitations were not rewritten, and no new acceptance was claimed.

Fresh authoritative READ ONLY SQL evidence at2026-10-15T07:05:12.955661Z and its snapshot are copied as inputs. Live Hero has no slug field: decoded raw key/name is paired by exact name with live Hero id. Black Panther→Shuri×1, Black Widow→Maria Hill×1, Doctor Strange→Wong×1 and Elektra→The Hand×4 agree. Exact owner portrait hits were absent in frozen reviews1–7, current gallery and the runtime media before calls.

There is no output image to visually review or hash. Full100 circular fit and native40/80 output review are therefore not performed. No review sheet or preview image is fabricated. Upstream source defects, readiness and formal status remain unchanged.

`source-hashes-before.json` records input hashes before calls; `verification.json` reports actual unchanged/changed inputs and verifies copied input snapshots, exact prompt/arguments, errors and absence of PNG. `manifest-sha256.json` covers all package files except itself. `ledger-handoff.json` records4 calls,0 outputs,4 blocked; credit cost is unknown, not zero. Only this new package was written. No shared ledger/CSV/registry/gallery/runtime, canonical source or git change was made. This is a frozen evidence handoff, not completed portrait production.

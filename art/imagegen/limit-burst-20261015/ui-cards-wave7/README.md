# CP-33 — proposed sidekick portrait sources

Four original raster source candidates: Faith (Angel), Giles (Buffy), Daisy (Dr. Jill Trent), and one representative Archer (Yennenga, Archers ×2). Four independent built-in image_gen calls ran in one parallel batch; all selected g1, no corrections. Sources retain original PNG bytes and dimensions. This package is frozen after final hash verification.

| Source | Consumer key | Reference selection | Reference status |
| --- | --- | --- | --- |
| Faith | `portrait:angel:faith` | heroes/faith selected g2 | proposed-awaiting-independent-acceptance |
| Giles | `portrait:buffy:giles` | heroes/giles selected g1 | proposed-reference-only |
| Daisy | `portrait:dr-jill-trent:daisy` | heroes/daisy selected g2 | proposed-reference-only |
| Archer representative | `portrait:yennenga:archers` | heroes-wave2/yennenga-archer selected g2 | proposed-production-reference-only |

Ownership and exact labels were confirmed against decoded raw owner JSON and a fresh read-only live DB query by the independent auditor. See `CP33-live-owner-evidence.json`. Art-hub helper heroLinks are absent. These keys were absent from runtime media, and no matching original portrait source candidates were found before generation. Commercial scraped avatars may exist; their absence is not claimed and they were not used as references.

Actual selected concept paths were resolved through upstream generation records, then checked against equal-hash design aliases. `selected-reference-records.json` captures the selection and SHA256. Every reference was opened before the calls. Reference status is proposed only; no formal1a, 3D or runtime acceptance transfers to these portraits. Copied upstream README, provenance and generation records are in `source-provenance/` and retain their limitations.

The saved sources and the fresh `review-sheet.png` were opened. A centered full-source circle, cx=.5, cy=.5, diameter1.0, preserves each whole head and headgear. The sheet includes genuine native40 and native80 images plus enlarged diagnostic views. At40 the main hair/headband/glasses/costume blocks distinguish the sources; fine face details are limited. No tighter crop is approved. Daisy has a rounded generated lower bust edge on opaque navy. No head clipping or identity failure justified a retry.

Upstream limitations remain: delegated original appearance/costume is not actor likeness or scanned-token canon; source framing/base warnings are not resolved by a portrait. Faith's original upstream prompt contained an unrelated instruction tail; this clean new portrait prompt used the selected Faith image only. Giles's glasses/beard/tweed and Daisy's technician clothes remain interpretations. Daisy and Faith each had source alternatives. Archer gender/clothes are delegated archetype choices, and one representative covers the two equivalent Archers. Upstream orthography, thin base/bowstring and single-component production checks remain outside portrait scope.

`portrait-g1.png` and `portrait-source.png` are byte copies of the tool original whose absolute path is recorded. Analysis previews alone were resized/masked; source PNGs were not reencoded. Exact submitted prompts are stored per asset and in `generation-records.json`. `verification.json` retains BEFORE hashes and reports any concurrent context changes honestly. `manifest-sha256.json` covers all package files except itself.

All four remain proposed source candidates. Runtime import, media registration, heroLinks, final crop/native screenshots and formal acceptance are pending. No shared registry, ledger, existing source, runtime or git changes were made here. `ledger-handoff.json` provides four calls for the coordinator; credit cost is unknown, not zero. No SYNTX/Tripo calls were made.

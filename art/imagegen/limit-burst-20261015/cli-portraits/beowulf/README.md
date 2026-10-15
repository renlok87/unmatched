# Beowulf portrait source candidate — 2026-10-15

Status: **candidate only; unaccepted and unintegrated**. `portrait-source-candidate.png` is an opaque RGB PNG, 1254×1254, created with the built-in image_gen tool in one call, with no correction. It is a byte-identical copy of the tool output; no retouch, recoloring, crop or resize was applied.

The opened original project reference is `art/imagegen/concept-beowulf-codex/design/beowulf-front.png` (1086×1448). `ASSET-BEOWULF-001` and roster slug `beowulf` match the asset card. The concept history selects design-front g2 and uses it as the approved design in later views. Model stage-4 acceptance r1 is **pass 8.1**, while the overall registry status is **technically imported**, not an artistic acceptance act. That model/design history does not accept this new portrait.

An independent repository filename scan, original portrait folders and `S08CardMedia.json` inspection found no existing original Beowulf portrait source. The current portrait keys are king-arthur, king-arthur:merlin, medusa, medusa:harpies and t-rex; `portrait:beowulf` is absent. The five-key list includes t-rex in addition to MVP heroes. Known original Beowulf images were full-body concepts, views and a sheet. `UmPortrait::Find` and `UmCardMedia::FindPortrait` already use hero slug keys. Details, scan exclusions, inaccessible unrelated directories and source hashes are recorded in `preflight.json`.

The saved result was opened after generation and visually compared with the opened design: the iron/gold helmet and nose guard, central beard plait and side braids, brown fur, gold ring torc, mail and leather strap remain recognizable. The whole head, helmet and beard fit the square and a centered circular crop. Approximate landmark geometry for a 95%-diameter centered disc is documented in `self-review.json`; it is not a runtime UI test. Palette and painted miniature craft pass the source self-review; no text, border or watermark is visible.

The helmet crest has about **4.8% top margin**, less than the requested 14%, but remains complete and within the centered circle. Preserve the full canvas for review. Helmet engraving is reinterpreted and mail remains detailed. Final thumbnail readability, hero-specific crop settings, UE import and artistic acceptance remain open. No runtime-ready claim is made.

- `prompt.txt`: exact submitted prompt.
- `request.json`: exact image tool arguments, including the sole local reference path.
- `preflight.json`: evidence for identity/design, missing portrait source and input hashes/dimensions.
- `generation-record.json`: one-call provenance, tool output path, matching input/output SHA-256 and dimensions.
- `self-review.json`: crop, identity, palette/craft checks and limitations.
- `manifest-sha256.json`: package file hashes, excluding the manifest itself.

Only this assigned new folder was written. No git mutation, shared registry/ledger/code changes, agents, services, Tripo/SYNTX calls or external image API fallback. All foreground commands completed; no background process was started or left to clean up.

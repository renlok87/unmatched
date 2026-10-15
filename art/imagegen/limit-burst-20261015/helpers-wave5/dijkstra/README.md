# Dijkstra — AN-153

Status: **proposed / source-only**. One front design reference for Philippa's helper; independent review remains with the coordinating root. This folder is not stage0 registration, formal acceptance, or a game-ready asset.

## Selected source

- [design-front.png](design-front.png): 1024 × 1536, exact unmodified bytes of built-in tool attempt 02.
- SHA256: `6aad3d805e386723d4adbbab95650a1ec09427cc0b90b3901acb103ab6d6aede`.
- One initial `image_gen.imagegen` call and the single allowed framing correction. Both originals remain under [attempts/](attempts/); no image was cropped, painted over, resized, or re-encoded locally.

The proposed design is a heavy middle-aged human spymaster with a bald crown, short side hair, weathered face, dark teal quilted doublet, brown trousers, broad plain belt and calf boots. His left hand holds a closed leather folio; his right hand is empty. These appearance choices are authorized interpretation, not conclusions derived from gameplay stats. No actor likeness or existing game model/costume was targeted.

## Evidence and reference use

The supplied `../owner-evidence.json` identifies Dijkstra as Philippa's single sidekick: health 6, movement 2, melee. This worker hash-verified that file, the owner image and the local raw file, and directly decoded the flattened `scraped-data/api/heroes/philippa.json` sidekick entry. This worker did not independently re-query the live database.

Both required local images were opened with `view_image` before generation: `art/imagegen/concept-philippa-codex/design/philippa-front.png` and `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`. Their roles were finish, material readability, cohort and palette only. Philippa's identity and costume were not copied. The first call was new generation without image-path attachments, as required by the tool contract; the edit attached only this worker's preserved first result.

The supplied absence statement and completed local source-path / asset-card / hero-links searches found no pre-existing Dijkstra source. Temporary directories were excluded after an initial listing met one inaccessible unrelated temporary directory. This is a bounded source search, not an exhaustive image-similarity audit. Details and reference/raw hashes are in [preflight.json](preflight.json).

## Self-review and actual failures

Attempt 01 had a crown margin of approximately 3.2% rather than 6%; its base ended near 91.1%. The one correction requested only global framing.

Selected attempt 02 improves head clearance but **still misses exact framing**: crown near y=105, approximately 6.84%; pedestal bottom near y=1350, approximately 87.89%, instead of 6% / 90%. These are approximate raster observations with about 3 px uncertainty. No further correction was made because the authorized correction cap was exhausted.

The face and torso read frontally and both hands are visible. Both elbows bend and show background wedges; the legs have a gap. The folio touches the left hip, and fingers gripping it are naturally partly occluded. The boots toe slightly outward, so the exact feet-forward pose is imperfect. The background is plain charcoal with a subtle tonal gradient rather than a perfectly uniform fill.

One dark two-disc stone pedestal reads edge-on, with two straight horizontal sidewall bands and no broad visible top plane. No VFX, ground scene, text or UI is visible. An edge-on raster cannot prove the base's hidden round geometry or certify a mathematically orthographic camera. The correction re-synthesized face/material microdetails; pixel identity with attempt 01 is not claimed.

See [verification.json](verification.json) for the complete self-review. Exact layout, exhaustive actor-likeness/originality clearance, 3D suitability and game readiness are not claimed. No mesh, rig, animation, side/back view or engine integration was produced.

## Provenance files

- [prompts/attempt-01.txt](prompts/attempt-01.txt) and [prompts/attempt-02.txt](prompts/attempt-02.txt): exact UTF-8 tool prompts.
- [calls/](calls/): exact tool arguments, UTC call times, original output paths and tool output hints.
- [generation-records.json](generation-records.json): original and preserved SHA256, dimensions, reference/raw hashes, selection and call accounting.
- [verification.json](verification.json): actual failures and limits, with proposed/source-only status.
- [manifest-sha256.json](manifest-sha256.json): every file in this folder except the manifest itself.

Only the assigned new `dijkstra/` folder was written. No git, ledger, registry, code, running service, purchase, external generation fallback or subagent was used. No persistent process was launched. The task's pre-call registration is based on the explicit user assignment; this worker did not read or alter the ledger.

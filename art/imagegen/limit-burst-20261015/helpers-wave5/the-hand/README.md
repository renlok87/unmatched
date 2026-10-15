# The Hand — AN-153

Status: **proposed/source-only**. One original adult masked swordsman front design representing one member of Elektra's confirmed four-person support group. This is not four variants, stage0 registration, formal acceptance or a game-ready asset. Independent review is pending and coordinated by root.

Selected source: [design-front.png](design-front.png), 1024 × 1536 RGB PNG. It is a byte-identical copy of the built-in image_gen correction output and [attempt 02](attempts/attempt-02.png), without cropping, resizing, retouching or re-encoding.

**Remaining visual failures:** the corrected pedestal ends at approximately y=1318/1536 (**85.81%**, target 90%). The coif begins around y=96 (**6.25%**, target 6%). The charcoal background retains a subtle gradient/vignette and faint diffuse shading below the base. These failures are recorded explicitly; this source does not pass all requested visual criteria. The single allowed correction was used, so no further generation was attempted.

The second attempt was selected because its top margin is closer to the request and its two-disc pedestal has no appreciable exposed top plane. It preserves the adult masked identity, charcoal layered cloth, restrained crimson sash, visible hands, one lowered sword in the figure's own right hand (viewer-left), empty left hand, relaxed stance and limb gaps. Its bottom framing regressed. The first attempt remains available for independent comparison. True orthographic camera projection, round pedestal plan shape and every finger hidden by the sword grip cannot be proven from this raster.

## Evidence and references

The supplied [owner-evidence.json](../owner-evidence.json), queried 2026-10-15T06:18:12Z, identifies The Hand as Elektra's four identical helpers: **1 health, movement 2, melee per instance**. The raw flattened `scraped-data/api/heroes/elektra.json` was independently decoded and its SHA256 matched the evidence. The owner image hash also matched. The evidence records no existing same-helper source; a local path scan found none, with one unrelated inaccessible metadata directory disclosed in [preflight.json](preflight.json). No independent live-database query was made by this worker.

Both required images were opened using view_image before generation:

- Owner: `art/imagegen/concept-elektra-codex/design/elektra-front.png` — quality/cohort and charcoal/crimson palette only. The new figure does not copy her identity, red costume, long sash, headband or paired weapons.
- Quality benchmark: `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png` — material, anatomy and rendering quality only; no copying of her identity, costume, bow, snakes or composition.

The initial new-generation request omitted image-reference parameters; the inspected references informed its written constraints. The correction used only the first generated attempt as its edit reference. Costume, mask and sword details are authorized proposed art choices, not facts established by the game stats. No actor likeness target, franchise key art, commercial scan, purchase or external generation fallback was used.

## Reproduction and integrity

Built-in `image_gen.imagegen` was used for **one generation and one framing correction**, two calls total. The actual underlying model/seed is not exposed by the tool. Both original outputs were left in their default generated-images location and copied byte for byte into this folder.

- [generation-records.json](generation-records.json): exact prompts, exact tool arguments, timestamps, tool output hints, original/result paths, dimensions, SHA256 values and selection rationale.
- [prompts/attempt-01.txt](prompts/attempt-01.txt) and [prompts/attempt-02-correction.txt](prompts/attempt-02-correction.txt): exact prompt text, verified against the recorded arguments.
- [attempt-01-self-review.json](attempt-01-self-review.json): actual first-attempt framing failures that justified the correction.
- [self-review.json](self-review.json): selected-image observations, actual remaining failures and limitations.
- [verification.json](verification.json): image decode/hash equality, unchanged owner/raw/reference evidence, prompt equality and explicit `visual_requirements_all_met: false`.
- [manifest-sha256.json](manifest-sha256.json): SHA256 and byte size of every file in this folder except the manifest itself.

Selected original/result SHA256: `695c173eb1af9e437cd710580e94254df3b8cf047336fea10f7cae2f683f973a`.

First original/result SHA256: `bd6434fe1e62774065382cbcc59e2ee1b82a25f8f727b2ec8db159b1fbb4501e`.

Only this assigned folder was written. No git, ledger, registry, source code, running service or agent-spawning operations were performed. No persistent process was started. This package supplies a front raster only; it contains no model, rig, animation, gameplay integration or game-scale validation.

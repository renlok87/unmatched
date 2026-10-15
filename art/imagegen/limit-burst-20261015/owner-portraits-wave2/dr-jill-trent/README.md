# Dr. Jill Trent — portrait source candidate

Status: **candidate only**. One built-in image_gen call; zero correction calls. No import or runtime acceptance.

- `original-g1.png`: untouched built-in output, 1254 x 1254 PNG.
- `portrait-source-candidate.png`: selected byte-for-byte copy.
- `prompt-g1.txt`: exact prompt submitted; full tool arguments and provenance are in `generation-record.json`.
- `verification.json`: computed SHA256, dimensions, PNG integrity and byte-copy checks.

## Identity and source absence

The actual local owner record `scraped-data/api/heroes/dr-jill-trent.json` identifies **Dr. Jill Trent**, slug `dr-jill-trent`, with helper **Daisy**. `docs/art-pipeline/hero-links.json` agrees that this is an owner. The normalized file's top-level name is incorrectly Daisy; it was not used to identify the portrait subject. No remote avatar, miniature scan, actor image or card art was opened or used.

Before generation, the approved project `art/imagegen/concept-dr-jill-trent-codex/design/dr-jill-trent-front.png` was opened with view_image. A focused filename search of art/imagegen, art/cards-v1 and runtime Content/UI returned no owner-specific portrait/avatar PNG, WebP or uasset. The runtime registry contained five MVP portrait keys and none for Jill. Scope and the unrelated inaccessible temporary folder are recorded in the generation record.

## Honest visual review

The candidate keeps the recognizable chestnut waved hair, chrome goggles above unobstructed brown eyes, fair skin, red lips, off-white lab coat and teal collared dress. Both eyes, ears, hair and goggles are visible; no top or side clipping, text, border or UI is visible. Background is charcoal with mild lighting variation.

Identity is interpreted from the approved project design, not a pixel-locked facial reproduction: the face is softer and has a slight smile, and the skin treatment is more realistic than the source's miniature face. Hair and goggles read as crafted volumes, but miniature-style consistency remains a review concern. This is generated character art, not a retrieved avatar photograph; no actor likeness was requested or referenced.

**Composition limitation:** the highest goggle is only about 6% below the top edge, rather than the requested 15%. The eyes sit roughly 35–36% down the source, above the requested 43% line. The head has good side clearance, but overhead margin is not fully compliant. No correction was made because there is no actual square-source clipping or clear identity failure.

**Circular crop limitation:** a full-size centered inscribed circle appears able to retain the head and goggles, but this is visual estimation only. A tighter face zoom or a reduced-diameter centered crop can cut the goggles; lower shoulder corners and coat will naturally be lost. Moving the circle upward to center the eyes would trade away lower clothing. No exact disc center/diameter, small-size eye readability, runtime material or safe-crop acceptance is claimed. Any future crop must be reviewed from this unchanged original.

Both copies preserve the original tool output; no crop, padding, color correction, resampling or alpha processing was applied. This worker wrote only its assigned new folder and the other assigned owner's new folder. No git changes, registry/ledger/code edits or imports were performed.

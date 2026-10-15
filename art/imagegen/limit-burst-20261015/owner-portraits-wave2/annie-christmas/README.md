# Annie Christmas — portrait source candidate

Status: **candidate only**. One built-in image_gen call; zero correction calls. No import or runtime acceptance.

- `original-g1.png`: untouched built-in output, 1254 x 1254 PNG.
- `portrait-source-candidate.png`: selected byte-for-byte copy.
- `prompt-g1.txt`: exact prompt submitted; full tool arguments and provenance are in `generation-record.json`.
- `verification.json`: computed SHA256, dimensions, PNG integrity and byte-copy checks.

## Identity and source absence

The actual local owner record `scraped-data/api/heroes/annie-christmas.json` identifies **Annie Christmas**, slug `annie-christmas`, with helper **Charlie**. `docs/art-pipeline/hero-links.json` agrees that this is an owner. No remote avatar, miniature scan, actor image or card art was opened or used.

Before generation, the approved project `art/imagegen/concept-annie-christmas-codex/design/annie-christmas-front.png` was opened with view_image. A focused filename search of art/imagegen, art/cards-v1 and runtime Content/UI returned no owner-specific portrait/avatar PNG, WebP or uasset. The runtime registry contained five MVP portrait keys and none for Annie. Scope and the unrelated inaccessible temporary folder are recorded in the generation record.

## Honest visual review

The candidate keeps the approved Black heroine's warm brown skin, powerful face and shoulders, serious expression, rust-red knotted wrap, brass hoop earrings, cream blouse and brown/turquoise bead palette. Both eyes are centered and readable. The whole wrap, its top knot and tails, both earrings and facial outline are visible without square-source head clipping. No lettering, UI, border or watermark is visible; background is charcoal with mild lighting variation.

The result is clearly sculpted and painted character art. Surface brush/relief texture is substantially coarser than the approved miniature, especially on the blouse; the knot is more prominent, and necklace rows are fewer. Facial identity is a plausible design interpretation, not a pixel-locked match. These differences remain for future visual review. No actor likeness was requested or referenced.

**Composition limitation:** the highest wrap fold is only about 3% below the top edge, rather than the requested 18–20%. Eyes sit roughly 37% down the source, above the requested 43% line. The source therefore fails the generous-overhead-margin preference even though no headgear is actually clipped. Shoulders extend into the lower image edges as a head-and-shoulders portrait. No correction was made because there is no actual square-source head clipping or clear identity failure.

**Circular crop limitation:** a full-size centered inscribed circle appears able to retain the head, wrap and earrings, but this is visual estimation only. The wrap's highest folds leave little room for reducing the disc diameter, zooming or moving the crop downward; those choices can cut the knot. Shoulder corners and parts of the lower necklace will naturally be lost in a circle. No exact disc center/diameter, small-size eye readability, runtime material or safe-crop acceptance is claimed. Any future crop must be reviewed from this unchanged original.

Both copies preserve the original tool output; no crop, padding, color correction, resampling or alpha processing was applied. This worker wrote only its assigned new folder and the other assigned owner's new folder. No git changes, registry/ledger/code edits or imports were performed.

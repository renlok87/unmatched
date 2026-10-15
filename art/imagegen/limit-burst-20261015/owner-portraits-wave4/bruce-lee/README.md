# Bruce Lee — portrait source candidate (CP-29)

Status: **candidate only**. Built-in image_gen; one generation, zero corrections. No runtime import or acceptance.

- `original-g1.png`: untouched PNG byte copy of the built-in result; original tool file preserved.
- `portrait-source-candidate.png`: selected byte copy, full100, no crop or other processing.
- `prompt-g1.txt` and `tool-arguments-g1.json`: exact submitted prompt and arguments.
- `generation-record.json` and `verification.json`: provenance, accepted source/output SHA256, dimensions and integrity checks.

## Preflight and identity

Owner key `bruce-lee` is read from the raw local roster's fetchedHero.key/name. There is no separate Bruce Lee entry in hero-links.json; that mapping is not evidence for this owner. The same-day live PostgreSQL evidence in heroes-wave3/live-roster-evidence.json (2026-10-15T05:58:04.783135+00:00) contains Bruce Lee. That live capture has a placeholder Unknown helper; raw has an empty-name zero-value helper. Neither is used as a portrait subject. The owner name agrees. This worker could not requery live services: local GraphQL endpoints refused connections, Docker API access was denied, and the attempted local pg module was unavailable. Live identity is therefore corroborated by that existing captured evidence, not claimed as a fresh live query.

Before generation the own approved design was opened through view_image. The 1a r1 acceptance card has verdict pass and binds that exact reference to SHA256 `b55ae26171f5283d20abafb6e474580065b554cbb9d4fc82083344439125fe62`; the actual file matched. Older package README status is superseded by this later acceptance card.

Focused filename lookup of art/imagegen, art/cards-v1 and Content/UI found no Bruce Lee portrait/avatar image or uasset, including earlier waves; lookup was repeated immediately before his generation. Temporary metadata-check directories were deliberately excluded; no errors in the focused lookup. Runtime S08CardMedia.json exposed only five MVP portrait keys, with none for this owner. This is a focused absence check, not a claim about every unnamed bitmap's content. No commercial avatar, scan, remote image or movie still was opened.

## Honest self-review

Directly inspected the generated result and saved selected PNG. Whole head, all black hair, both ears and shoulders are visible in the square. The eyes are centered, level and readable; clean-shaven face, angular cheekbones, yellow round-neck suit and black shoulder stripes retain the approved design's cues. Sculpted hair and painted surface texture read as miniature craftsmanship. No lettering, UI, border, circle, prop or extra subject is visible. The plain charcoal backdrop has mild tonal variation.

Differences remain: the face appears somewhat softer/younger and less severe than the canonical miniature; the sculpted fringe is fuller, longer and rounder, while suit highlights are brighter yellow. This is a fresh miniature interpretation, not a pixel-locked likeness or an accepted identity result. At this magnification the skin texture is fairly naturalistic even though the overall asset reads as painted sculpture.

**Headroom:** the highest hair lock sits approximately 14% below the top, short of the requested 18–20%; eyes are approximately 44% down the source. Full head is present with ample side clearance. No correction was used because no actual clipping or clear identity failure was observed.

**Native circular-crop limitations:** keep this unchanged full100 source. A centered full-size inscribed circle appears to retain the whole head, hair and ears with useful reserve; native material, exact masking and small-size readability were not tested by this worker. A circle removes much of the lower outer shoulders and parts of the black sleeve stripes, so the face/hair/yellow collar must carry identity at small sizes. Any zoom/reposition needs a fresh check. No safe-crop or runtime acceptance is claimed; the independent reviewer owns native circular-crop review.

Only the two assigned new owner subfolders were written. No git mutation, shared/package-root edit, registry, ledger, code change, paid service, runtime import, subagent or background service.

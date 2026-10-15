# Oda Nobunaga — portrait source candidate (CP-29)

Status: **candidate only**. Built-in image_gen; one generation, zero corrections. No runtime import or acceptance.

- `original-g1.png`: untouched PNG byte copy of the built-in result; original tool file preserved.
- `portrait-source-candidate.png`: selected byte copy, full100, no crop or other processing.
- `prompt-g1.txt` and `tool-arguments-g1.json`: exact submitted prompt and arguments.
- `generation-record.json` and `verification.json`: provenance, accepted source/output SHA256, dimensions and integrity checks.

## Preflight and identity

Owner key `oda-nobunaga` is read from the raw local roster's fetchedHero.key/name and agrees with hero-links.json. The same-day live PostgreSQL evidence in heroes-wave3/live-roster-evidence.json (2026-10-15T05:58:04.783135+00:00) contains Oda Nobunaga and Honor Guard; the helper is excluded from this portrait. This worker could not requery live services: local GraphQL endpoints refused connections, Docker API access was denied, and the attempted local pg module was unavailable. Live identity is therefore corroborated by that existing captured evidence, not claimed as a fresh live query.

Before generation the own approved design was opened through view_image. The 1a r2 acceptance card has verdict pass and binds that exact reference to SHA256 `8a0b6f78b7285bad02be8b7fc193868dada058db3c1f8e97b6ef596d442a1664`; the actual file matched. Older package README status is superseded by this later acceptance card.

Focused filename lookup of art/imagegen, art/cards-v1 and Content/UI found no Oda portrait/avatar image or uasset, including earlier waves. Temporary metadata-check directories were deliberately excluded; no errors in the focused lookup. Runtime S08CardMedia.json exposed only five MVP portrait keys, with none for this owner. This is a focused absence check, not a claim about every unnamed bitmap's content. No commercial avatar, scan, remote image or movie still was opened.

## Honest self-review

Directly inspected the generated result and saved selected PNG. Full head, entire gold crescent with both long tips, side ornaments and neck guard are visible in the square. Centered brown eyes are clear; black lacquer, gold relief, red cords and vermilion cape preserve the reference's identity and palette. The asset reads as crafted painted miniature art. No lettering, UI, frame, mask or extra subject is visible. The charcoal background has slight tonal variation rather than an exactly flat RGB value.

Differences remain: the crescent is relatively larger/taller; floral relief and breastplate ornament are newly interpreted, and the face is slightly broader with a heavier moustache/goatee than the canonical figure. Surface texture is more magnified at this portrait scale. These are candidate review notes, not an identity acceptance.

**Headroom:** highest crest tips are approximately 9% below the top, less than the requested 20%. Eyes are approximately 46% down the source. Whole headgear is present with useful side clearance, but the generous-overhead-margin preference is only partly met. No correction was used because no actual square-source clipping or clear identity failure was observed.

**Native circular-crop limitations:** keep this unchanged full100 source. A centered full-size inscribed circle appears to retain face, crescent and helmet side guards, but native material, exact masking and small-size readability were not tested by this worker. Tall crest tips occupy the upper disc area and lose reserve if zoomed or shifted downward. A circle necessarily removes lower outer shoulders, cape and some armor. Thin gold tips and relief can weaken at native small icon sizes. No safe-crop or runtime acceptance is claimed; the independent reviewer owns native circular-crop review.

Only the two assigned new owner subfolders were written. No git mutation, shared/package-root edit, registry, ledger, code change, paid service, runtime import, subagent or background service.

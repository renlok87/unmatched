# Wong front design reference — AN-152

Status: **proposed/source-only**. Independent review is pending with root. This is a source concept, with no stage0 registration, formal acceptance or game-ready claim.

Selected image: `design-front.png` (1024×1536 RGB), a byte-identical copy of built-in image_gen attempt 02. The original-intent adult East Asian support scholar has a stocky build, short dark hair, ochre-brown robes, plain cloth sash, indigo trousers, practical shoes and empty relaxed hands.

Owner evidence confirms Doctor Strange → Wong, count 1, health 6, movement 2, ranged attack. The supplied owner reference and raw source SHA256 values were recomputed and match the evidence. The owner and Medusa quality PNGs were opened with view_image before generation. They informed cohort/finish and restrained palette, with no owner identity or wholesale costume reuse. Source evidence reports no matching existing helper source; the additional filename search found none, with one unrelated inaccessible temporary directory noted in `preflight.json`.

## Attempts and actual failures

- Attempt 01: initial generation. Full figure and hands are visible. Hair top is approximately 3.2% and base bottom approximately 92%, missing the requested 6%/90% boundaries. The charcoal background has mild tonal variation. Preserved unchanged as `attempt-01-original.png`.
- Attempt 02: the one allowed correction, targeted only at framing. Selected for clear full silhouette and at least 6% top clearance. Hair top is approximately 7% and base bottom approximately 86.1%; exact framing remains failed. The charcoal background still has mild tonal variation. Preserved unchanged as `attempt-02-original.png` and selected unchanged as `design-front.png`. No further calls or manual image edits were made.

Both hands are visible with thumbs and natural finger contours, though overlap prevents exact topology certification. The front view shows two stone side bands with a horizontal seam and no broad top ellipse; circular plan and exact orthographic projection cannot be proven from this raster. No actor was requested or referenced; absence of resemblance to every real person is not certified. The design does not visibly copy the owner face, red cloak, gold gloves or medallions.

## Provenance

Built-in `image_gen.imagegen` only: one generation plus one correction, two calls total. No purchase, external generation fallback, commercial scan, actor reference or copied franchise key art. The tool originals remain in the tool's default generated-images folder and were copied byte for byte into this assigned folder. No crops, repainting, resizing or re-encoding were performed.

Exact sent prompts and parameters, original paths, source/result SHA256 values, dimensions, input hashes, timing and self-review are in `generation-records.json`. Human-readable prompt files are `prompt-attempt-01.txt` and `prompt-attempt-02.txt` (files add a final newline; exact sent text is recorded in JSON). `verification.json` records remaining failures and scope limits. `manifest-sha256.json` hashes every file in this folder except itself.

This worker wrote only this assigned folder, did not touch git, code, ledgers, registries or services, and spawned no agents. Root owns independent review and any later workflow decision.

# Dandelion — AN-152

Status: **proposed/source-only**. Original adult humanoid front design reference for Geralt of Rivia’s helper. This is not stage0 registration, formal acceptance, a 3D model or a game-ready asset. Independent review belongs to the coordinating root and remains pending.

Selected file: [design-front.png](design-front.png), 1024 × 1536 RGB. It is an unchanged byte copy of built-in attempt 02. Both tool originals are preserved as [attempt-01-original.png](attempt-01-original.png) and [attempt-02-original.png](attempt-02-original.png). There was one initial call and one correction for observed framing and hand failures; no further calls or pixel editing.

The design is an adult chestnut-haired wandering bard with burgundy feathered cap, teal velvet, muted gold braid and a wooden lute. Owner-reference guidance was limited to serious fantasy cohort/material quality and restrained aged-metal accents. The owner identity, armor, hair, medallion and weapons were not copied. No actor reference, commercial scan or franchise key-art image was used; originality/likeness has not received independent clearance.

## Evidence

The supplied owner evidence and decoded raw roster agree: owner **Geralt of Rivia**, helper **Dandelion**, count **1**, health **5**, movement **2**, attack **range**. Both owner raw and reference hashes match the supplied evidence. The owner and Medusa quality references were opened with `view_image` before generation. Their hashes and dimensions are recorded in [preflight.json](preflight.json) and [generation-records.json](generation-records.json).

No same-helper source was found under `art/imagegen` using Dandelion/Jaskier aliases before folder creation. One unrelated `concept-elektra-codex/tmp-metadata-check-asb509mx` directory was unreadable. The evidence row also reports no matching production PNG/card path. The inventory therefore has a documented access limitation.

## Self-review and actual failures

Attempt 01 had the hands reversed, visible pedestal top, approximately 1.7% top margin, approximately 93.5% base bottom and insufficient arm separation. It remains unmodified.

Attempt 02 corrects the anatomical right hand on the neck and left hand supporting the lute. The two-disc stone pedestal reads edge-on and its bottom is approximately 90% down the frame. The complete figure, feather and lute are visible; bent-arm openings and leg separation are readable. No scenery, VFX, text or UI appears.

**Remaining failures:** feather tip is approximately 2.5% down the frame instead of 6%; not all five digits of each gripping/supporting hand can be independently read; the lute bowl overlaps the lower torso rather than sitting entirely beside it. Feet have a mild natural outward angle. Front orthographic is the design intent, not calibrated camera proof. Two side bands are visible, but a round footprint cannot be proved from an edge-on view. The charcoal background has subtle studio tonal variation. Framing figures are manual visual estimates, not automated measurements. The correction budget is exhausted; this selection does not pass every requested visual criterion.

See [review-attempt-01.json](review-attempt-01.json), [review-attempt-02.json](review-attempt-02.json) and [verification.json](verification.json). The generated outputs were visually inspected directly; the selected local PNG was also opened with `view_image`.

## Reproducibility and integrity

Built-in `image_gen.imagegen` was used exclusively; no external fallback or purchases. Exact prompts are [prompt-attempt-01.txt](prompt-attempt-01.txt) and [prompt-attempt-02.txt](prompt-attempt-02.txt). Full arguments, tool-reported original paths, timestamps, original/result hashes and dimensions are in [generation-records.json](generation-records.json) and the two tool-metadata files. The built-in tool does not expose model version or seed, so exact rerendering is not claimed.

[manifest-sha256.json](manifest-sha256.json) covers every file in this folder except itself. No ledger, registry, code, git state, other worker folder or running service was changed. No agents or persistent processes were started.

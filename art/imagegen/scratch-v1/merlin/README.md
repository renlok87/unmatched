# Merlin scratch 2D — images generated, package BLOCKED

ASSET-MERLIN-001 / MerlinSC. Run2 resumed on2026-10-02 at user request. **All requested image categories now exist**, but they do not satisfy the fixed numeric/visual contract. Four new front-shaded attempts failed; stop under CODEX-2D-PACKAGE-PROMPT §5. No HANDOFF.json and ZCode must not use these as accepted modelling projections.

## Images

- Full-body registered shaded views: `views/merlin-front-shaded.png` (try8), `merlin-side-shaded.png`, `merlin-back-shaded.png`.
- Flat-color generation attempts: `views/merlin-front-albedo.png`, `merlin-side-albedo.png`, `merlin-back-albedo.png`. They still contain gradients and changed contours; these are rejected albedo attempts.
- Close-up generated details: `details/merlin-face-front-shaded.png`, `merlin-face-side-shaded.png`, `merlin-weapon-front-shaded.png`. Face outputs1254×1254 despite requested1024×1024, and oversized framing; see `detail-check.json`.
- Every original in `raw/` without pixel edits, every exact prompt and visual check in `prompts.md`; masks and per-attempt diagnostic overlays retained. Historical run1 reports in `raw/round1-*`.
- Separate `guides-v2/` underpaintings and `detail-inputs/` crops/staff grid: generation inputs only, never final accepted projections. No3D geometry.

## Fixed inputs and results

`spec.json` and original templates/metadata are byte-identical to run1: hood45cm, staff49.5cm, baseØ24×5.5cm, weapon.R,26px/cm, baseline1413. `spec-check.json` has `checks_passed: true`. `registration-test-check.json` has `checks_passed: true`; synthetic maximum error0.400967px≤0.5px. Tools keep unchanged thresholds and ΔE76 mask extraction.

Current `views-check.json`: **checks_passed:false**. Every generated full-body view retains all registration marks and registers successfully; maximum residual across retained attempts=0.322318px (limit1.5px). But gray/cyan mixtures in the generated grid become foreground under the mandated ΔE76>12-to-both test, connect to the figure and contaminate the masks. Mask-derived numbers below are not reliable visual geometry measurements; they cannot count as acceptance.

| Check | Measured | Required |
|---|---:|---:|
| Final front mask baseline | 1535px |1413±2px|
| Front median width deviation |21.565934%|≤4%|
| Front↔back profile median / height |2.393162%|≤2%|
| Front↔back profile p95 / height |11.111111%|≤5%|
| Front shaded↔albedo IoU |0.585519|≥0.98|
| Side shaded↔albedo IoU |0.415004|≥0.98|
| Back shaded↔albedo IoU |0.421507|≥0.98|
| Maximum albedo zone L* range /100 |0.596991|≤0.12|

Attempt counts: front-shaded8 total (run1=4, run2=4); side-shaded1; back-shaded1; each albedo1; face-front1; face-side1; weapon-front1. New generation calls12; calibration remains the earlier1. SYNTX spend0 because image_gen is available.

## Visual findings and next decision

Front8 corrects the brown leather beard tie and wooden staff setting. Side/back and front-albedo came from front7 and retain different surface motifs or gold collars/ties; costume identity across them is not exact. Side facesLEFT, front staff viewerLEFT and back staff viewerRIGHT; no extra heads or limbs observed. Face detail is recognizable, but framing does not match its request.

A fresh copy of the same prompt cannot be assumed to preserve technical-grid pixels: raw PNGs already fail before registration. To obtain a usable modelling package, a future run needs a generation method that preserves the grid/contours, or explicit authorization for a different grid/mask/compositing protocol. This run does not change those rules or fit the spec to images. Existing images may be reviewed as visual drafts only.

## Reproduce

```powershell
python tools/scratch-model/check_spec.py art/imagegen/scratch-v1/merlin/spec.json
python tools/scratch-model/tests/test_registration.py --report art/imagegen/scratch-v1/merlin/registration-test-check.json
python tools/scratch-model/check_views.py art/imagegen/scratch-v1/merlin
```

Last command intentionally exits1. Source hashes in `blocked-files.json`. No3D/UE changes, remote push, stash/reset/clean or original-image repairs.

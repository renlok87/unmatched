# Merlin scratch 2D: BLOCKED — four front attempts rejected

ASSET-MERLIN-001, MerlinSC. Stop required by CODEX-2D-PACKAGE-PROMPT.md §5: no passing front-shaded after four attempts. All four attempts have detectable registration marks and count toward the limit. This is failure evidence, not an approved 2D package.

## Completed

- Immutable pre-generation `spec.json`: hood 45 cm, staff top 49.5 cm, base Ø24 × 5.5 cm, 5.25 heads, weapon.R, all 17 joints/parents, leaf tails, body widths and material palette.
- `spec-check.json`: `checks_passed: true`; head proportion ratio 1.0; all library/background-distance/joint checks passed. Equal base_top/sole follows the pipeline's own example; all later mandatory levels strictly increase.
- Generator resolution probe produced 1024×1536. `template.json`: 26 px/cm, baseline 1413, centre 512, front/left-side/back matrices. `templates/` contains the three grids.
- Registration synthetic regression tests: `registration-test-check.json`, `checks_passed: true`, maximum recovery error 0.400967 px (limit 0.5 px); missing marks and unmodelled rotation rejected.
- Four originals in `raw/`, unchanged bytes; exact requests and prompts in `prompts.md`, four attempt check reports, registered last front and masks; separate diagnostic overlays per attempt.

## Numeric failure evidence

Registration succeeds, but image generation does not preserve dimensions and grid color sufficiently for the required segmentation. These are values from the mandated ΔE76 >12 mask algorithm, **not reliable measurements of the visible painted geometry**, because cyan/gray mixtures join grid fragments to the silhouette. No threshold was relaxed and no original pixel was repaired.

| Front attempt | Maximum registration residual px | Scale | Mask bottom row | Mask-derived body height cm | Mask-derived base diameter cm | Median width deviation | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| 1 | 0.1007 | 0.99996575 | 1535 | 53.9615 | 26.9615 | 50.55% | FAIL |
| 2 | 0.0576 | 0.99998644 | 1535 | 49.9231 | 25.9615 | 22.25% | FAIL |
| 3 | 0.0878 | 1.00000660 | 1438 | 49.9615 | 29.9615 | 25.46% | FAIL |
| 4 | 0.0508 | 0.99997267 | 1535 | 47.6154 | 29.0385 | 15.44% | FAIL |

Expected: each registration residual ≤1.5 px; scale correction ≤3%; bottom 1413 ±2 px; height 45 ±1%; base diameter 24 ±2%; each landmark width ±8%, median ≤4%. Final `views-check.json`: `checks_passed: false`. Last grid contamination fraction 0.002506982708405802 exceeds 0.002. Final mask touches the frame edge and contains foreign grid fragments. Overlay: `diagnostics/front-shaded-try4-mask-overlay.png`.

Front↔back profile and shaded↔albedo IoU: **not measured**; no side/back/albedo was generated after the front blocker. Attempt counts: front-shaded 4; all other requested views/details 0; calibration 1 (not a character attempt). SYNTX token spend 0 because built-in image_gen was available.

## Required resolution before resuming

The generator must preserve the original grid/background colors and obey the fixed dimensional guides. Resume requires an explicit new attempt budget or an authorized different generation/masking protocol; §5 prohibits a fifth front attempt in this run. Changing thresholds, painting over the grid, or fitting spec numbers to these outputs is not an allowed resolution. Keep the spec immutable; compare a future generation against these same numeric values.

No `HANDOFF.json`: its required `checks_passed: true` statements would be false. ZCode must not model from the rejected views. No 3D geometry, Blender/Unreal changes or remote push. The blocked report, source evidence and tested partial tools can be integrated locally without declaring the package ready.

## Reproduce

```powershell
python tools/scratch-model/check_spec.py art/imagegen/scratch-v1/merlin/spec.json
python tools/scratch-model/make_template.py art/imagegen/scratch-v1/merlin/spec.json
python tools/scratch-model/tests/test_registration.py --report art/imagegen/scratch-v1/merlin/registration-test-check.json
python tools/scratch-model/register_views.py art/imagegen/scratch-v1/merlin --view front --variant shaded --attempt 4
python tools/scratch-model/check_views.py art/imagegen/scratch-v1/merlin
```

Last command intentionally exits 1. Tools depend on Python, Pillow, numpy and scipy. Tooling was exercised on this pilot and synthetic registration; full side/back/albedo pipeline remains unverified because generation stopped.

# Merlin scratch 2D generation log

Date: 2026-10-02. Built-in image_gen; transparent_background=false. Raw PNG bytes copied unchanged.

Calibration: request 1024x1536 portrait, actual 1024x1536. `raw/calibration-size.png`. Prompt: Technical calibration image only, no character. Portrait canvas exactly 1024 by 1536 pixels. Uniform light gray #B4B4B4 background with thin cyan #00C8FF square measurement grid, four small black circles with white crosses at the four corners inset 40 pixels. No text, no perspective. This output tests available image generator resolution for a subsequent Merlin 2D blueprint package.

Decisions are recorded in spec.json before the first character generation. Registration synthetic shift/scale test recovers transformed points <=0.5 px; missing marks and rotation are rejected.

## front shaded attempt 1

Date: 2026-10-02. Tool: image_gen.imagegen. transparent_background: false.

referenced_image_paths, exact order:

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/templates/merlin-front-template.png`

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/hero-quality-v1/merlin/merlin-front.png`

Exact prompt:

```text
Use case: stylized-concept. Image 1 EDIT TARGET is the exact 1024x1536 Merlin measurement template. Image 2 is ONLY premium painted-miniature surface craftsmanship reference, NOT character or proportions. Image 3 is ONLY Merlin face, costume, embroidery and palette reference, NOT silhouette, pose, base or proportions. Draw ONE elderly slightly hunched wizard on image 1, strict FRONT orthographic view, no perspective, no three-quarter. Keep the light gray background #B4B4B4 UNIFORM and the cyan grid #00C8FF and four black circle/white cross registration marks EXACTLY unchanged in location, size and color. Figure occludes grid completely; no lines showing through figure. Absolutely preserve canvas 1024x1536. Pixel/cm=26, centre x512, base bottom y1413, base top/boots soles y1270, base diameter exactly 624px: x200..824, base height143px. Camera horizontal: draw base as frontal round-cylinder elevation with straight top and bottom, no visible elliptical top face. Hood apex y243 (45cm); staff crystal tip y126 (49.5cm); eyes y334, chin y399, shoulders y464, chest y555, waist/belt y685, crotch y789, knees y997, ankle y1218. Body full silhouette widths EXCLUDING the separate staff: y997 knee364px (x330..694), y789 crotch338px (x343..681), y685 waist364px (x330..694), y555 chest416px (x304..720), y464 shoulders442px (x291..733), y334 hood208px (x408..616). Head roughly196px high. Fit these measurements, do not use Image 3 body shape. Deep midnight-blue wool hood and ground-length robe, broad sleeves, two vertical stoles, antique gold rune-like nonverbal embroidery and stars at hood border/cuffs/hem; long ivory white beard tied with brown leather, wise wrinkled face; worn brown belt, bronze buckle and dangling end, brown boots toe tips. LEFT hand at belt (viewer right); RIGHT hand holds crooked dark carved wooden support staff (viewer LEFT), one-handed. Grip around x325 y633, lower staff x278 y1270 then x278 y971, grip x325 y633, upper shaft x270 y373 and x226 y217, sapphire-blue faceted crystal center x213 y172, width78 height91, wooden claw frame. Staff contacts base. No magic effects. Detailed miniature shaded paint with soft studio light only on figure, no floor or cast background shadows. Team accents only belt, hood lining and thin OUTER cuff/hem edge, separate from gold embroidery. No new text, labels, watermark, cropping, extra limbs, extra heads or added props; preserve existing template landmarks for measurement.
```

Result: FAIL; `raw/front-shaded-try1-check.json`, checks_passed: false. Registration passed; see `views-registration.json` attempt entry.

Failed measurements:

```json
{
  "front.shaded.base_diameter": {
    "expected": {
      "diameter_cm": 24.0,
      "tolerance_rel": 0.02
    },
    "measured": 26.96153846153846,
    "note": "",
    "passed": false
  },
  "front.shaded.baseline": {
    "expected": {
      "baseline_px": 1413,
      "tolerance_px": 2
    },
    "measured": 1535,
    "note": "",
    "passed": false
  },
  "front.shaded.figure_height": {
    "expected": {
      "height_cm": 45.0,
      "tolerance_rel": 0.01
    },
    "measured": 53.96153846153846,
    "note": "",
    "passed": false
  },
  "front.shaded.frame_margin": {
    "expected": "no edge contact",
    "measured": true,
    "note": "",
    "passed": false
  },
  "front.shaded.width.chest": {
    "expected": {
      "tolerance_rel": 0.08,
      "width_cm": 16.0
    },
    "measured": 19.73076923076923,
    "note": "Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.",
    "passed": false
  },
  "front.shaded.width.crotch": {
    "expected": {
      "tolerance_rel": 0.08,
      "width_cm": 13.0
    },
    "measured": 20.03846153846154,
    "note": "Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.",
    "passed": false
  },
  "front.shaded.width.eye": {
    "expected": {
      "tolerance_rel": 0.08,
      "width_cm": 8.0
    },
    "measured": 14.961538461538462,
    "note": "Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.",
    "passed": false
  },
  "front.shaded.width.knee": {
    "expected": {
      "tolerance_rel": 0.08,
      "width_cm": 14.0
    },
    "measured": 20.576923076923077,
    "note": "Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.",
    "passed": false
  },
  "front.shaded.width.waist": {
    "expected": {
      "tolerance_rel": 0.08,
      "width_cm": 14.0
    },
    "measured": 21.576923076923077,
    "note": "Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.",
    "passed": false
  },
  "front.shaded.width_median": {
    "expected": "relative median <=0.04",
    "measured": 0.5054945054945055,
    "note": "",
    "passed": false
  }
}
```

Visual control: Strict front, one character, right-hand staff at viewer left, left hand at belt, costume matches concept. Base top remains slightly visible; hood, staff and body dimensions oversized. No extra limbs/heads.

## front shaded attempt 2

Date: 2026-10-02. Tool: image_gen.imagegen. transparent_background: false.

referenced_image_paths, exact order:

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/templates/merlin-front-template.png`

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/hero-quality-v1/merlin/merlin-front.png`

Exact prompt:

```text
Use case: stylized-concept. Image 1 EDIT TARGET is the exact 1024x1536 Merlin measurement template. Image 2 is ONLY premium painted-miniature surface craftsmanship reference, NOT character or proportions. Image 3 is ONLY Merlin face, costume, embroidery and palette reference, NOT silhouette, pose, base or proportions. Draw ONE elderly slightly hunched wizard on image 1, strict FRONT orthographic view, no perspective, no three-quarter. Keep the light gray background #B4B4B4 UNIFORM and the cyan grid #00C8FF and four black circle/white cross registration marks EXACTLY unchanged in location, size and color. Figure occludes grid completely; no lines showing through figure. Absolutely preserve canvas 1024x1536. Pixel/cm=26, centre x512, base bottom y1413, base top/boots soles y1270, base diameter exactly 624px: x200..824, base height143px. Camera horizontal: draw base as frontal round-cylinder elevation with straight top and bottom, no visible elliptical top face. Hood apex y243 (45cm); staff crystal tip y126 (49.5cm); eyes y334, chin y399, shoulders y464, chest y555, waist/belt y685, crotch y789, knees y997, ankle y1218. Body full silhouette widths EXCLUDING the separate staff: y997 knee364px (x330..694), y789 crotch338px (x343..681), y685 waist364px (x330..694), y555 chest416px (x304..720), y464 shoulders442px (x291..733), y334 hood208px (x408..616). Head roughly196px high. Fit these measurements, do not use Image 3 body shape. Deep midnight-blue wool hood and ground-length robe, broad sleeves, two vertical stoles, antique gold rune-like nonverbal embroidery and stars at hood border/cuffs/hem; long ivory white beard tied with brown leather, wise wrinkled face; worn brown belt, bronze buckle and dangling end, brown boots toe tips. LEFT hand at belt (viewer right); RIGHT hand holds crooked dark carved wooden support staff (viewer LEFT), one-handed. Grip around x325 y633, lower staff x278 y1270 then x278 y971, grip x325 y633, upper shaft x270 y373 and x226 y217, sapphire-blue faceted crystal center x213 y172, width78 height91, wooden claw frame. Staff contacts base. No magic effects. Detailed miniature shaded paint with soft studio light only on figure, no floor or cast background shadows. Team accents only belt, hood lining and thin OUTER cuff/hem edge, separate from gold embroidery. No new text, labels, watermark, cropping, extra limbs, extra heads or added props; preserve existing template landmarks for measurement.
CRITICAL RETRY 2: Previous attempt failed because figure, staff and base were too large, and grid strokes changed color. This is a dimensional BLUEPRINT, measurement adherence matters above aesthetics. Ignore any inferred old Merlin silhouette. Base bottom MUST be row1413, never1453; hood apex MUST row243, never194; crystal top MUST row126, never75. Waist width364, never560, knee width364, never535. Base must span exactly x200..824, not x180..840. Make the robe narrow and slender at these exact levels. Pure original cyan #00C8FF for every grid stroke, not muted/antialiased darker cyan; uniform #B4B4B4 background. No shadows on grid/background. Copy Image1 grid as literal unaltered pixels. Image3 provides color and facial features ONLY; do not borrow its wide pose, large sleeves or flared robe.
```

Result: FAIL; `raw/front-shaded-try2-check.json`, checks_passed: false. Registration passed; see `views-registration.json` attempt entry.

Failed measurements:

```json
{
  "front.shaded.base_diameter": {
    "expected": {
      "diameter_cm": 24.0,
      "tolerance_rel": 0.02
    },
    "measured": 25.96153846153846,
    "note": "",
    "passed": false
  },
  "front.shaded.baseline": {
    "expected": {
      "baseline_px": 1413,
      "tolerance_px": 2
    },
    "measured": 1535,
    "note": "",
    "passed": false
  },
  "front.shaded.figure_height": {
    "expected": {
      "height_cm": 45.0,
      "tolerance_rel": 0.01
    },
    "measured": 49.92307692307692,
    "note": "",
    "passed": false
  },
  "front.shaded.frame_margin": {
    "expected": "no edge contact",
    "measured": true,
    "note": "",
    "passed": false
  },
  "front.shaded.single_connected_figure": {
    "expected": "one substantial component (>=0.1% largest, >=100 px)",
    "measured": [
      945,
      1576,
      1614,
      1332,
      890,
      491734,
      623,
      1064,
      1590,
      744,
      657,
      555,
      667,
      1994,
      776
    ],
    "note": "",
    "passed": false
  },
  "front.shaded.width.chest": {
    "expected": {
      "tolerance_rel": 0.08,
      "width_cm": 16.0
    },
    "measured": 17.307692307692307,
    "note": "Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.",
    "passed": false
  },
  "front.shaded.width.crotch": {
    "expected": {
      "tolerance_rel": 0.08,
      "width_cm": 13.0
    },
    "measured": 17.26923076923077,
    "note": "Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.",
    "passed": false
  },
  "front.shaded.width.eye": {
    "expected": {
      "tolerance_rel": 0.08,
      "width_cm": 8.0
    },
    "measured": 13.961538461538462,
    "note": "Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.",
    "passed": false
  },
  "front.shaded.width.knee": {
    "expected": {
      "tolerance_rel": 0.08,
      "width_cm": 14.0
    },
    "measured": 15.73076923076923,
    "note": "Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.",
    "passed": false
  },
  "front.shaded.width.waist": {
    "expected": {
      "tolerance_rel": 0.08,
      "width_cm": 14.0
    },
    "measured": 18.5,
    "note": "Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.",
    "passed": false
  },
  "front.shaded.width_median": {
    "expected": "relative median <=0.04",
    "measured": 0.22252747252747251,
    "note": "",
    "passed": false
  }
}
```

Visual control: Strict front, one character and correct staff hand. Slimmer robe, but top/bottom/widths still drift. Base top slightly visible. No extra limbs/heads.

## front shaded attempt 3

Date: 2026-10-02. Tool: image_gen.imagegen. transparent_background: false.

referenced_image_paths, exact order:

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/templates/merlin-front-template.png`

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Exact prompt:

```text
Image 1 is the EDIT TARGET: preserve this EXACT 1024x1536 measurement sheet. Image 2 is ONLY painted miniature craftsmanship. Paint ONE Merlin FRONT strict orthographic elevation on Image 1, no perspective, no three-quarter. Every background pixel, cyan grid line and four black registration marks must be copied unchanged: background #B4B4B4, line color #00C8FF. No color shifting, filtering, lighting, vignette, shadows or texture on the background. Figure completely occludes grid. The numbers define the figure; do NOT invent proportions. Hood tip: pixel(512,243). Staff tip:(213,126). Base is a straight rectangular frontal cylinder elevation spanning x200..824, y1270..1413. Boots on y1270. Tiny rounded edges permitted, NEVER an ellipse showing the top. Body width at y997=364px, y789=338px, y685=364px, y555=416px, y464=442px, y334=208px. These are TOTAL left-to-right body/sleeve widths, excluding staff only; do not draw any part of the robe or sleeve outside these widths at these rows. Keep waist and hips slender. Face eyes at y334, chin at399; elderly hooded wizard, midnight navy blue full-length wool robe, white long beard tied brown, two vertical gold-embroidered stoles, gold stars and rune-like symbols at hood rim and cuffs/hem, worn brown belt with bronze buckle, brown boots. Left hand at belt (viewer RIGHT). Right hand grips wooden staff (viewer LEFT) at pixel325,633. Staff follows cyan left staff guide starting at278,1270,278,971,325,633,270,373,226,217; small wooden claw setting and blue sapphire faceted crystal width78,height91 centered213,172. One head, two arms, no extras, no magical effects. Illustrated painted-miniature surface quality, soft shading on figure only. Exact camera alignment and these dimensions take priority over beauty. No new text, no watermark, no crops.
```

Result: FAIL; `raw/front-shaded-try3-check.json`, checks_passed: false. Registration passed; see `views-registration.json` attempt entry.

Failed measurements:

```json
{
  "front.shaded.base_diameter": {
    "expected": {
      "diameter_cm": 24.0,
      "tolerance_rel": 0.02
    },
    "measured": 29.96153846153846,
    "note": "",
    "passed": false
  },
  "front.shaded.baseline": {
    "expected": {
      "baseline_px": 1413,
      "tolerance_px": 2
    },
    "measured": 1438,
    "note": "",
    "passed": false
  },
  "front.shaded.figure_height": {
    "expected": {
      "height_cm": 45.0,
      "tolerance_rel": 0.01
    },
    "measured": 49.96153846153846,
    "note": "",
    "passed": false
  },
  "front.shaded.single_connected_figure": {
    "expected": "one substantial component (>=0.1% largest, >=100 px)",
    "measured": [
      602,
      515646,
      537,
      723,
      554,
      920,
      785,
      708,
      565,
      868,
      613,
      538,
      635
    ],
    "note": "",
    "passed": false
  },
  "front.shaded.width.chest": {
    "expected": {
      "tolerance_rel": 0.08,
      "width_cm": 16.0
    },
    "measured": 19.884615384615383,
    "note": "Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.",
    "passed": false
  },
  "front.shaded.width.crotch": {
    "expected": {
      "tolerance_rel": 0.08,
      "width_cm": 13.0
    },
    "measured": 17.53846153846154,
    "note": "Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.",
    "passed": false
  },
  "front.shaded.width.eye": {
    "expected": {
      "tolerance_rel": 0.08,
      "width_cm": 8.0
    },
    "measured": 15.23076923076923,
    "note": "Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.",
    "passed": false
  },
  "front.shaded.width.knee": {
    "expected": {
      "tolerance_rel": 0.08,
      "width_cm": 14.0
    },
    "measured": 16.346153846153847,
    "note": "Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.",
    "passed": false
  },
  "front.shaded.width.waist": {
    "expected": {
      "tolerance_rel": 0.08,
      "width_cm": 14.0
    },
    "measured": 17.73076923076923,
    "note": "Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.",
    "passed": false
  },
  "front.shaded.width_median": {
    "expected": "relative median <=0.04",
    "measured": 0.25463598901098894,
    "note": "",
    "passed": false
  }
}
```

Visual control: Front and staff hand correct, face/costume recognizable. Added belt pouch violates no added props; dimensions still drift. No extra limbs/heads.

## front shaded attempt 4

Date: 2026-10-02. Tool: image_gen.imagegen. transparent_background: false.

referenced_image_paths, exact order:

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/templates/merlin-front-template.png`

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Exact prompt:

```text
Image 1 is the EDIT TARGET: preserve this EXACT 1024x1536 measurement sheet. Image 2 is ONLY painted miniature craftsmanship. Paint ONE Merlin FRONT strict orthographic elevation on Image 1, no perspective, no three-quarter. Every background pixel, cyan grid line and four black registration marks must be copied unchanged: background #B4B4B4, line color #00C8FF. No color shifting, filtering, lighting, vignette, shadows or texture on the background. Figure completely occludes grid. The numbers define the figure; do NOT invent proportions. Hood tip: pixel(512,243). Staff tip:(213,126). Base is a straight rectangular frontal cylinder elevation spanning x200..824, y1270..1413. Boots on y1270. Tiny rounded edges permitted, NEVER an ellipse showing the top. Body width at y997=364px, y789=338px, y685=364px, y555=416px, y464=442px, y334=208px. These are TOTAL left-to-right body/sleeve widths, excluding staff only; do not draw any part of the robe or sleeve outside these widths at these rows. Keep waist and hips slender. Face eyes at y334, chin at399; elderly hooded wizard, midnight navy blue full-length wool robe, white long beard tied brown, two vertical gold-embroidered stoles, gold stars and rune-like symbols at hood rim and cuffs/hem, worn brown belt with bronze buckle, brown boots. Left hand at belt (viewer RIGHT). Right hand grips wooden staff (viewer LEFT) at pixel325,633. Staff follows cyan left staff guide starting at278,1270,278,971,325,633,270,373,226,217; small wooden claw setting and blue sapphire faceted crystal width78,height91 centered213,172. One head, two arms, no extras, no magical effects. Illustrated painted-miniature surface quality, soft shading on figure only. Exact camera alignment and these dimensions take priority over beauty. No new text, no watermark, no crops.
FINAL DIMENSIONAL RETRY 4. Strict normalized framing: hood TOP at exactly 15.82% of image height; crystal TOP at8.20%; base BOTTOM at92.00%; base TOP at82.68%. Circular base FRONT elevation width60.94% of canvas, x19.53% to80.47%. Eyes at21.74% of height. At waist44.60% height figure width35.55% canvas; knees64.91% height figure width35.55% canvas; shoulders30.21% height figure width43.16% canvas. Place the figure as a small slender blueprint miniature within this larger sheet. Do not fill the canvas with a tall/wide portrait. Do not extend sleeves beyond specified width. Preserve staff within the exact cyan staff-guide line: center of crystal x20.8%, not26%. Hood top must be substantially LOWER than in typical full-canvas portrait. Use the unchanged cyan grid; paint may not tint background or create shadows. No bags or pouches or other extra objects.
```

Result: FAIL; `raw/front-shaded-try4-check.json`, checks_passed: false. Registration passed; see `views-registration.json` attempt entry.

Failed measurements:

```json
{
  "front.shaded.base_diameter": {
    "expected": {
      "diameter_cm": 24.0,
      "tolerance_rel": 0.02
    },
    "measured": 29.03846153846154,
    "note": "",
    "passed": false
  },
  "front.shaded.baseline": {
    "expected": {
      "baseline_px": 1413,
      "tolerance_px": 2
    },
    "measured": 1535,
    "note": "",
    "passed": false
  },
  "front.shaded.figure_height": {
    "expected": {
      "height_cm": 45.0,
      "tolerance_rel": 0.01
    },
    "measured": 47.61538461538461,
    "note": "",
    "passed": false
  },
  "front.shaded.frame_margin": {
    "expected": "no edge contact",
    "measured": true,
    "note": "",
    "passed": false
  },
  "front.shaded.grid_inside": {
    "expected": "<=0.002",
    "measured": 0.002506982708405802,
    "note": "",
    "passed": false
  },
  "front.shaded.single_connected_figure": {
    "expected": "one substantial component (>=0.1% largest, >=100 px)",
    "measured": [
      591,
      747,
      1081,
      558,
      949,
      588,
      923,
      1120,
      1238,
      416800,
      660,
      1101,
      466,
      514,
      732,
      427,
      567,
      548,
      942,
      429,
      506,
      1662,
      1236,
      812,
      816,
      612,
      1396,
      630,
      786,
      1151,
      692,
      511,
      1135,
      620
    ],
    "note": "",
    "passed": false
  },
  "front.shaded.width.crotch": {
    "expected": {
      "tolerance_rel": 0.08,
      "width_cm": 13.0
    },
    "measured": 16.076923076923077,
    "note": "Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.",
    "passed": false
  },
  "front.shaded.width.eye": {
    "expected": {
      "tolerance_rel": 0.08,
      "width_cm": 8.0
    },
    "measured": 15.73076923076923,
    "note": "Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.",
    "passed": false
  },
  "front.shaded.width.waist": {
    "expected": {
      "tolerance_rel": 0.08,
      "width_cm": 14.0
    },
    "measured": 17.692307692307693,
    "note": "Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.",
    "passed": false
  },
  "front.shaded.width_median": {
    "expected": "relative median <=0.04",
    "measured": 0.15440088757396442,
    "note": "",
    "passed": false
  }
}
```

Visual control: Strict front, one character and correct hand, no extra limbs/heads. Face/costume recognizable; cuff motifs changed, belt height/boots/base wrong despite better hood placement. Staff no longer matches immutable centreline. No profile/back produced.

## Stop

Front failed after four counted attempts; all four retained registration marks. Stop under CODEX-2D-PACKAGE-PROMPT §5. Side/back/albedo/details were not generated. No usable handoff. No pixel repairs and no post-generation spec changes. SYNTX was not used because image_gen was available.

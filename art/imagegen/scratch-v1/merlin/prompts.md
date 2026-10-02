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

# Run 2 — user requested regeneration

Date2026-10-02. New cycle authorized by user: «сгенерируй то что не смог». New front cycle capped at4 attempts, cumulative filenames try5–8. Original spec, original template metadata and original templates unchanged. Separate deterministic 2D underpaintings in guides-v2/ strengthen silhouette guidance; they are not final views or 3D geometry. Head reference crops are explicitly permitted by pipeline §4.1; raw originals remain unchanged.

## back-albedo-try1

Date2026-10-02; tool image_gen.imagegen; transparent_background:false.

referenced_image_paths in exact order:

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/raw/merlin-back-shaded-try1.png`

Exact prompt:

```text
Convert ONLY the painted Merlin miniature in Image1 into a FLAT UNLIT ALBEDO projection. Remove ALL lighting, shadows, ambient occlusion, specular highlights, rim lights and illumination gradients. Keep every exterior contour and pixel position, costume pattern and hand/staff position identical to Image1. Keep the technical gray background, cyan grid and four registration marks unchanged. Do not add text, labels, props or perspective. Canvas exactly1024x1536. Flat solid local colors, no 3D shading, no fabric/wood shading or painted shadow lines. Crisp clean color-zone illustration suitable for direct base-color projection. Palette: robe/hood/sleeves #182A49; gold embroidered motif #B68B39; belt #624029; boots/beard leather tie #4A3023; hood lining #4A3153; very thin cuff/hem outer edge #79513D; buckle #AD7C48; wooden staff/claw setting #35271C; sapphire crystal #2556AD; beard/eyebrows #EEE7D3; face/hands #BE9874; stone base #30343C. Crystal is the same flat blue on every facet, no bright facets; beard one flat ivory, face one flat tan. Patterns remain the same solid gold shapes. Background #B4B4B4 and grid #00C8FF. No gradients anywhere within each material color zone. Strict BACK view: NO face/beard on back, right-hand staff at viewerRIGHT and left hand at belt viewerLEFT; preserve all back hood, sleeve and robe contours and gold embroidery.
```

Result: FAIL; `raw/back-albedo-try1-check.json`, `checks_passed: false`. Registration itself passed.

Visual control: Back and staff viewer RIGHT maintained; subtle cloth/base gradients remain. Automated checks FAIL.

## back-shaded-try1

Date2026-10-02; tool image_gen.imagegen; transparent_background:false.

referenced_image_paths in exact order:

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/guides-v2/merlin-back-template.png`

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/raw/merlin-front-shaded-try7.png`

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/raw/merlin-side-shaded-try1.png`

Exact prompt:

```text
Image1 EDIT TARGET is the exact BACK dimensional stencil. Image2 FRONT and Image3 LEFT SIDE define the SAME Merlin character/costume. Paint ONE strict BACK orthographic horizontal-camera elevation, no perspective, no three-quarter, no face visible. Right hand holds crooked wooden staff viewerRIGHT (character anatomical RIGHT), left hand at belt viewerLEFT. Preserve Image1 silhouette/body/base/staff/crystal exterior bounds; do not change height or width. Hood apex243, staff/crystal top126, base x200..824 y1270..1413 rectangle seen horizontally with no top ellipse, body knee width364 at997, crotch338 at789,waist364 at685,chest416 at555,shoulder442 at464,eye-level hood208 at334. Same dark navy blue coarse wool hood and long robe, gold hood-border embroidery, cuffs and hem with small ancient nonverbal rune-like motifs and stars, restrained small stitched stars on back no enormous new emblem, worn brown belt and shoes. White beard only hidden front, no beard on back. Same staff and wooden claw sapphire crystal as other views, no magic. Soft premium painted miniature shading ONLY on figure. Keep background pure #B4B4B4 and cyan measurement grid #00C8FF and four registration marks exactly unchanged, crisp opaque original pixels, no gray/cyan blending or background shadow. Figure occludes grid. No added objects/limbs/heads, no new text/watermark/crop. Exact1024x1536 canvas.
```

Result: FAIL; `raw/back-shaded-try1-check.json`, `checks_passed: false`. Registration itself passed.

Visual control: Strict back, no face, right-hand staff at viewer RIGHT, one figure. Hood folds and hand position vary from front; staff collar gold. Mask FAIL.

## face-front-shaded-try1

Date2026-10-02; tool image_gen.imagegen; transparent_background:false.

referenced_image_paths in exact order:

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/detail-inputs/merlin-face-front-crop.png`

Exact prompt:

```text
Image1 is the cropped FRONT head of this exact Merlin miniature. Generate a 1024x1024 close-up reference, strict FRONT ORTHOGRAPHIC, not perspective, not three-quarter. Same wise elderly wrinkled face, nose/eyebrows/eye shapes, white long beard and dark navy wool hood with same antique gold rim embroidery and star. Brown LEATHER beard tie (not a metal ring). No shoulders or hands or staff. Hood/head/beard together occupy central80% of canvas height, from y102 to922, all contours visible and uncropped. Refine sculpted detail and painted miniature surface, soft studio light. Light gray #B4B4B4 background and crisp cyan #00C8FF measurement grid occluded by the head. Four black circles diameter24px/white crosses at (40,40),(983,40),(40,983),(983,983). No new text/watermark, no extra faces/heads/accessories. This is detail reference, keep character identity consistent.
```

Result: unapproved detail; see `detail-check.json`, `checks_passed: false`.

Visual control: One face, strict front, brown leather beard tie, character recognizable. Actual1254x1254, requested1024x1024; head almost fills canvas rather than80%; unapproved detail.

## face-side-shaded-try1

Date2026-10-02; tool image_gen.imagegen; transparent_background:false.

referenced_image_paths in exact order:

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/detail-inputs/merlin-face-side-crop.png`

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/raw/merlin-face-front-shaded-try1.png`

Exact prompt:

```text
Image1 is LEFT SIDE head crop of the same Merlin; Image2 is its detailed FRONT identity reference. Generate1024x1024 strict LEFT SIDE PROFILE of ONLY hood/head/long beard, facing LEFT, no perspective, no three-quarter, no shoulders/hands/staff. Preserve the wise elderly wrinkled face, white eyebrows, blue eyes, nose/profile and beard family. Brown leather beard tie. Same navy blue wool hood, exact star and gold ornamental rim embroidery, no added accessories. Hood/head/beard occupy central80% canvas height from y102..922 with uncropped contours and generous margin. Premium painted miniature detail with studio shading on head only. Gray #B4B4B4 background, cyan #00C8FF grid occluded by head. Four black registration circles diameter24px/white crosses (40,40),(983,40),(40,983),(983,983). No text/watermark/crop, no extra heads.
```

Result: unapproved detail; see `detail-check.json`, `checks_passed: false`.

Visual control: One face, strict left profile facing LEFT, same facial family and brown beard tie. Actual1254x1254; oversized framing; unapproved detail.

## front-albedo-try1

Date2026-10-02; tool image_gen.imagegen; transparent_background:false.

referenced_image_paths in exact order:

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/raw/merlin-front-shaded-try7.png`

Exact prompt:

```text
Convert ONLY the painted Merlin miniature in Image1 into a FLAT UNLIT ALBEDO projection. Remove ALL lighting, shadows, ambient occlusion, specular highlights, rim lights and illumination gradients. Keep every exterior contour and pixel position, costume pattern and hand/staff position identical to Image1. Keep the technical gray background, cyan grid and four registration marks unchanged. Do not add text, labels, props or perspective. Canvas exactly1024x1536. Flat solid local colors, no 3D shading, no fabric/wood shading or painted shadow lines. Crisp clean color-zone illustration suitable for direct base-color projection. Palette: robe/hood/sleeves #182A49; gold embroidered motif #B68B39; belt #624029; boots/beard leather tie #4A3023; hood lining #4A3153; very thin cuff/hem outer edge #79513D; buckle #AD7C48; wooden staff/claw setting #35271C; sapphire crystal #2556AD; beard/eyebrows #EEE7D3; face/hands #BE9874; stone base #30343C. Crystal is the same flat blue on every facet, no bright facets; beard one flat ivory, face one flat tan. Patterns remain the same solid gold shapes. Background #B4B4B4 and grid #00C8FF. No gradients anywhere within each material color zone. Strict FRONT view, staff viewerLEFT in RIGHT hand, left hand at belt viewerRIGHT.
```

Result: FAIL; `raw/front-albedo-try1-check.json`, `checks_passed: false`. Registration itself passed.

Visual control: Front contour approximately follows try7; solid-color approximation, but base/cloth gradients and some face shadow tones remain. Automated flatness and silhouette checks FAIL.

## front-shaded-try5

Date2026-10-02; tool image_gen.imagegen; transparent_background:false.

referenced_image_paths in exact order:

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/guides-v2/merlin-front-template.png`

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/hero-quality-v1/merlin/merlin-front.png`

Exact prompt:

```text
Use case: style-transfer. Image 1 EDIT TARGET is a dimensionally exact 2D underpainting on the Merlin measurement grid. Image 2 is ONLY painted-miniature craftsmanship. Image 3 is ONLY Merlin facial appearance, robe colors and gold embroidery. REFINE SURFACE DETAIL INSIDE THE ALREADY FILLED SHAPES OF IMAGE 1. Keep exactly the external contour and pixel position of the navy character, dark rectangular base, crooked brown staff and blue crystal in Image 1. Do not expand or shrink any shape. The simple beard/face patches are placeholders to refine internally. This is strict FRONT orthographic elevation, horizontal camera, no perspective, no 3/4. Base is a circular cylinder seen horizontally: preserve the rectangular elevation, no visible top ellipse. Preserve every gray background #B4B4B4 and cyan #00C8FF grid pixel and all four black-white registration circles exactly unchanged. No anti-alias color changes on grid, no vignette, no background shadows or gradient. Figure fully hides grid. Canvas exactly1024x1536. Hood top row243, staff crystal top126, base bottom1413, base top1270, base width624px x200..824. Body must keep the underpainting contour: total width364 at knees row997,338 at crotch789,364 at waist685,416 at chest555,442 at shoulders464,208 at eyes334. Render this slender elderly slightly hunched Merlin as premium painted-miniature illustration: deep midnight-blue coarse wool hood and ground-length robe, wide sleeves within existing silhouette, two vertical stoles, ancient gold embroidered rune-like nonverbal patterns and stars along hood rim, cuff and hem; long white beard tied brown leather, wise wrinkled face, brown worn leather belt bronze buckle/dangling end, boots visible internally above base top. RIGHT hand holds staff at x325,y633 on viewer LEFT; LEFT hand at belt viewer RIGHT. Pose and all exterior shapes from Image1 only, not Image3. Carved crooked dark wooden staff and wooden claw crystal setting contained in the existing guide, faceted sapphire-blue crystal, no magic. Soft studio shading and sculptural surface detail only within painted figure. Team accent only belt/hood lining/thin cuff and hem outer edge, gold pattern separate. One head, two arms, no extra props, no text/watermark/crop. Keep measurement sheet literally intact.
```

Result: FAIL; `raw/front-shaded-try5-check.json`, `checks_passed: false`. Registration itself passed.

Visual control: Strict front, one head/two arms, staff anatomical right viewer left. Brown leather belt, but beard tie changed to gold; contour closer to stencil. Mask FAIL due grid contamination.

## front-shaded-try6

Date2026-10-02; tool image_gen.imagegen; transparent_background:false.

referenced_image_paths in exact order:

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/guides-v2/merlin-front-template.png`

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Exact prompt:

```text
EDIT IMAGE 1 IN PLACE. Paint detailed Merlin ONLY INSIDE its colored underpainting, preserving its exact silhouette. Do not redraw, re-render, resize, recolor or soften ANY background/grid/registration-mark pixels. This is an engineering stencil: original gray #B4B4B4, original cyan #00C8FF, exact original canvas1024x1536. Image2 only shows miniature paint craftsmanship, not anatomy. Strict front orthographic no perspective. Exact existing hood apex row243, crystal126, base rectangle x200..824/y1270..1413. Keep all body widths and staff path from Image1 unchanged. Refine elderly wrinkled face, tied white beard, navy blue wool hood/robe, two gold embroidered stoles, wide sleeves within stencil, worn brown belt bronze buckle, boots at base top. Right hand on staff viewerLEFT at x325/y633, left hand at belt viewerRIGHT. Crooked dark wood staff with blue sapphire crystal. No magic, no extra objects, no text. Keep dark stone base dimensions and exact flat horizontal camera elevation. Studio shading only INSIDE figure; exterior grid/background pixel-for-pixel unchanged. Do NOT expand sleeves or hood. Preserve source colored shapes as hard masks.
```

Result: FAIL; `raw/front-shaded-try6-check.json`, `checks_passed: false`. Registration itself passed.

Visual control: Strict front, correct staff hand. Hard triangular hood envelope followed; beard tie is gold contrary to spec. Mask FAIL.

## front-shaded-try7

Date2026-10-02; tool image_gen.imagegen; transparent_background:false.

referenced_image_paths in exact order:

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/guides-v2/merlin-front-template.png`

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Exact prompt:

```text
Image1 is a fixed engineering drawing to be painted internally. Image2 craftsmanship reference only. Keep ALL of Image1 background, grid, four registration marks and outside edges of colored silhouette EXACTLY. Render ONE elderly Merlin in strict front orthographic elevation inside the colored stencil, without altering dimensions. Navy wool hood/robe, white tied beard, wise wrinkled face, brown leather belt/boots, bronze buckle, two gold embroidered stoles, gold stars and nonverbal rune-like embroidery; right hand on crooked wooden sapphire-topped staff viewerLEFT, left hand at belt. Soft painted shadows only INSIDE figure. Base is a dark stone rectangle in horizontal cylinder elevation x200..824 y1270..1413. Body hood top243, staff top126; preserve all stencil widths. CRITICAL PRINT PRODUCTION: background flat RGB180,180,180 and every grid pixel pure RGB0,200,255. Grid is bright saturated opaque cyan, NOT grayish cyan, NOT partially transparent or blurred, NOT a textured surface. Absolutely no antialiasing or shadows on the technical grid. Crisp clean digital engineering raster. Keep the source grid in its original hard pixels. No perspective, no extra objects, no watermark, no crop, no new text. Paint the character, never regenerate the technical sheet.
```

Result: FAIL; `raw/front-shaded-try7-check.json`, `checks_passed: false`. Registration itself passed.

Visual control: Strict front, correct staff hand. Gold beard/staff collars differ from leather/wood specification. Mask FAIL. This draft supplied appearance and contours to side/back and albedo, not an accepted view.

## front-shaded-try8

Date2026-10-02; tool image_gen.imagegen; transparent_background:false.

referenced_image_paths in exact order:

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/guides-v2/merlin-front-template.png`

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/raw/merlin-face-front-shaded-try1.png`

Exact prompt:

```text
EDIT Image1 in place, HARD contour preservation. Image2 is painted-miniature quality only; Image3 gives same Merlin face and BROWN LEATHER beard tie. Refine navy silhouette into elderly Merlin, only paint INSIDE original colored shapes. Preserve every grid/background/registration pixel and exact external silhouette. Original canvas1024x1536, pure gray RGB180,180,180, grid RGB0,200,255 with no transparency/blur/filter/shading/antialiasing; original four black-white corner circles. Strict FRONT orthographic horizontal camera, no perspective. Hood apex243, crystal top126, base rectangle x200..824 y1270..1413, no visible top. Body widths from original stencil unchanged, no expanded sleeves: knee364,crotch338,waist364,chest416,shoulder442,eye208. Darkblue wool hood/robe with two ancient gold-embroidered stoles, gold star/rune-like rim/cuffs/hem, wise face, long white beard with BROWN LEATHER WRAP (no gold band), worn brown belt bronze buckle and dangling end, brown boots. RIGHT hand on carved darkwood crooked staff viewerLEFT at x325/y633, LEFT hand at belt viewerRIGHT. Staff claw frame is WOOD ONLY, no gold collars, sapphire blue crystal and no magic. Studio shading ONLY within figure. No extra props/limbs/heads/new text/watermark/crop. Do not regenerate technical grid: keep source hard pixels literally unchanged.
```

Result: FAIL; `raw/front-shaded-try8-check.json`, `checks_passed: false`. Registration itself passed.

Visual control: Strict front, correct staff hand; brown beard wrap and wooden staff setting corrected. Hood/body dimensions visibly closer to stencil, but mandatory mask checks FAIL. Embroidery differs from try7, so frontalbedo from try7 is not an exact surface match.

## side-albedo-try1

Date2026-10-02; tool image_gen.imagegen; transparent_background:false.

referenced_image_paths in exact order:

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/raw/merlin-side-shaded-try1.png`

Exact prompt:

```text
Convert ONLY the painted Merlin miniature in Image1 into a FLAT UNLIT ALBEDO projection. Remove ALL lighting, shadows, ambient occlusion, specular highlights, rim lights and illumination gradients. Keep every exterior contour and pixel position, costume pattern and hand/staff position identical to Image1. Keep the technical gray background, cyan grid and four registration marks unchanged. Do not add text, labels, props or perspective. Canvas exactly1024x1536. Flat solid local colors, no 3D shading, no fabric/wood shading or painted shadow lines. Crisp clean color-zone illustration suitable for direct base-color projection. Palette: robe/hood/sleeves #182A49; gold embroidered motif #B68B39; belt #624029; boots/beard leather tie #4A3023; hood lining #4A3153; very thin cuff/hem outer edge #79513D; buckle #AD7C48; wooden staff/claw setting #35271C; sapphire crystal #2556AD; beard/eyebrows #EEE7D3; face/hands #BE9874; stone base #30343C. Crystal is the same flat blue on every facet, no bright facets; beard one flat ivory, face one flat tan. Patterns remain the same solid gold shapes. Background #B4B4B4 and grid #00C8FF. No gradients anywhere within each material color zone. Strict LEFT SIDE PROFILE facing LEFT; preserve the same anatomical RIGHT hand staff on the far side and LEFT hand at belt.
```

Result: FAIL; `raw/side-albedo-try1-check.json`, `checks_passed: false`. Registration itself passed.

Visual control: LEFT profile maintained; beard/hand contours changed slightly and subtle cloth/base gradients remain. Automated checks FAIL.

## side-shaded-try1

Date2026-10-02; tool image_gen.imagegen; transparent_background:false.

referenced_image_paths in exact order:

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/guides-v2/merlin-side-template.png`

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/raw/merlin-front-shaded-try7.png`

Exact prompt:

```text
Image1 EDIT TARGET is the LEFT SIDE dimension stencil for Merlin. Image2 defines the same character, costume and paint quality from FRONT; it is not side-view geometry. Paint one elderly Merlin STRICT LEFT SIDE PROFILE facing LEFT, orthographic horizontal camera, no perspective, no three-quarter. Character's anatomical LEFT side visible, RIGHT hand staff on far side; do NOT swap staff to left hand. Keep source stencil exterior body/base/staff/crystal positions and all technical gray/cyan grid and four corner marks unchanged. Canvas1024x1536, scale26px/cm, center512, baseline1413. Base frontal cylinder elevation width624px x200..824 y1270..1413, horizontal camera no top ellipse. Hood top y243, staff top126. Side body widths: knee y997=234px, crotch789=247px, waist685=260px, chest555=286px, shoulder464=260px, eye334=208px. Full figure darkblue wool robe/pointed deep hood, old wise wrinkled face nose pointing LEFT, long white beard brown leather tie projecting at front LEFT, gold embroidered rim/cuffs/hem and front stoles consistent with Image2, brown belt bronze buckle and boots, left hand at belt, right hand one-handed staff grip z30cm. Crooked carved dark wooden staff with wooden claw sapphire crystal; no magic. Soft painted-miniature studio shading ONLY INSIDE figure; background pure #B4B4B4 and grid pure #00C8FF crisp opaque no antialias colors, no shadows/vignette. Figure occludes grid. No extra limbs/heads/props, no new text/watermark/crop.
```

Result: FAIL; `raw/side-shaded-try1-check.json`, `checks_passed: false`. Registration itself passed.

Visual control: Strict left profile facing LEFT; one figure, staff retained in anatomical right hand on far side, foreground left hand at belt. Beard tie/staff collar gold instead of brown/wood. Mask FAIL.

## weapon-front-shaded-try1

Date2026-10-02; tool image_gen.imagegen; transparent_background:false.

referenced_image_paths in exact order:

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/detail-inputs/merlin-weapon-front-template.png`

- `C:/tmp/wt-scratch2d-merlin/art/imagegen/scratch-v1/merlin/raw/merlin-front-shaded-try7.png`

Exact prompt:

```text
Image1 EDIT TARGET is exact isolated Merlin STAFF front-orthographic dimensional guide, not a character. Image2 is surface/design reference for same staff and blue sapphire crystal. Refine ONLY within Image1 staff/crystal colored contours, preserve crooked centreline, shaft thickness and tip/bottom exactly. Single isolated wooden staff, strict FRONT orthographic no perspective, no person/hand/base/other prop. Crooked very dark brown carved wood with restrained ancient decorative incision, wooden claw setting, faceted sapphire-blue crystal. NO metallic gold rings, no magical effect. Full staff and tip uncropped. Canvas1024x1536, scale29px/cm, bottom1413, crystal tip137, total vertical44cm. Main shaft radius0.6cm; crystal width3cm/87px, height3.5cm/101.5px; crystal center x454,y187.75. Preserve Image1 cyan measurement grid #00C8FF, gray #B4B4B4 and four registration marks exactly unchanged and figure occludes grid, no antialias color shifts/background shadow. Premium painted-miniature surface detail with soft studio shading ONLY inside staff/crystal. No text/watermark/crop/additional objects.
```

Result: unapproved detail; see `detail-check.json`, `checks_passed: false`.

Visual control: Single staff, front orthographic, wooden claw setting with sapphire crystal, no magic or metal collars. Actual1024x1536, correct direction and broadly preserved centreline. Detail not approved while package blocked.

## Run2 stop

Four new front attempts all FAIL. All requested image categories now have outputs, but none constitutes an accepted full package. Stop required by §5. No fifth run2 front attempt, no threshold reduction, no pixel repair, no spec adaptation, no HANDOFF. Front↔back and shaded↔albedo values in current views-check.json are mask-derived and contaminated by grid artifacts.

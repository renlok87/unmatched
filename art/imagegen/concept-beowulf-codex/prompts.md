# Промпты ASSET-BEOWULF-001 — этап 1a

Дата: 2026-10-13.
Инструмент: image_gen, встроенный; режим generate.

## art/imagegen/concept-beowulf-codex/concepts/beowulf-design-front-g1.png

prompt_key: 1a/design-front/g1

referenced_image_paths, в порядке вызова:

```json
[
  "C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
]
```

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Beowulf, the Geatish hero: huge bearded warrior in chainmail-patterned tunic painted as large flat shapes, fur mantle over the shoulders, iron helmet with brow ridges, leather boots; broad longsword in his RIGHT hand, round wooden shield on his LEFT arm.
IDENTITY ANCHORS, each clearly visible: longsword in the figure's own RIGHT hand; round wooden shield on the LEFT arm; fur mantle; braided beard.
PALETTE: iron grey #5E6266, fur brown #6E5236, weathered wood #8B6A43, accent gold torc #C99A35. These are the main colours plus one accent; no other strong colours.
POSE: Neutral standing pose of a tabletop miniature: both feet planted on the pedestal, weight even, both arms held slightly away from the torso with a visible gap between each arm and the body, elbows slightly bent; not a T-pose and not an A-pose. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: one round dark stone pedestal under the feet, two low stacked discs with plain bevelled edges, diameter about 0.55 of the figure height, flat top, no cobbles, no scenery, no coloured ring and no metal band. The camera is level with the pedestal: the pedestal is seen exactly edge-on, its top surface is not visible, its front edge is a straight horizontal line.
VIEW: strict front orthographic view, camera exactly level with the subject at its mid-height (zero elevation, not
looking down), no perspective, no three-quarter turn, the subject faces the camera.
FRAMING: portrait aspect ratio 3:4; one isolated subject; the pedestal, or the bottom of the object if it has no pedestal,
centred at x50% with its bottom at y93%; the highest point of the subject or of anything it holds no higher than y4%
(y >= 4%: at least 4% of the image height below the top edge); the whole subject and the whole pedestal visible,
nothing cropped.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background, no gradient, no vignette, no floor, no cast
shadow on the background; soft even studio lighting, no strong rim light, no depth of field.
READABILITY: large clear shapes; arms, wings and held objects separated from the body by visible gaps; thin parts such
as strings, shafts and staffs clearly readable, not hair-thin; fine detail stays inside the silhouette.
FORBIDDEN: text, letters, numbers, logos, watermark, frame, collage or several views, extra figures, extra limbs,
heads, wings or weapons, team colours, a coloured ring or metal band on the pedestal.
Output one single image.
```

## art/imagegen/concept-beowulf-codex/concepts/beowulf-design-front-g2.png

prompt_key: 1a/design-front/g2

referenced_image_paths, в порядке вызова:

```json
[
  "C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
]
```

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Beowulf, the Geatish hero: huge bearded warrior in chainmail-patterned tunic painted as large flat shapes, fur mantle over the shoulders, iron helmet with brow ridges, leather boots; broad longsword in his RIGHT hand, round wooden shield on his LEFT arm.
IDENTITY ANCHORS, each clearly visible: longsword in the figure's own RIGHT hand; round wooden shield on the LEFT arm; fur mantle; braided beard.
PALETTE: iron grey #5E6266, fur brown #6E5236, weathered wood #8B6A43, accent gold torc #C99A35. These are the main colours plus one accent; no other strong colours.
POSE: Neutral standing pose of a tabletop miniature: both feet planted on the pedestal, weight even, both arms held slightly away from the torso with a visible gap between each arm and the body, elbows slightly bent; not a T-pose and not an A-pose. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: one round dark stone pedestal under the feet, two low stacked discs with plain bevelled edges, diameter about 0.55 of the figure height, flat top, no cobbles, no scenery, no coloured ring and no metal band. The camera is level with the pedestal: the pedestal is seen exactly edge-on, its top surface is not visible, its front edge is a straight horizontal line.
VIEW: strict front orthographic view, camera exactly level with the subject at its mid-height (zero elevation, not
looking down), no perspective, no three-quarter turn, the subject faces the camera.
FRAMING: portrait aspect ratio 3:4; one isolated subject; the pedestal, or the bottom of the object if it has no pedestal,
centred at x50% with its bottom at y93%; the highest point of the subject or of anything it holds no higher than y4%
(y >= 4%: at least 4% of the image height below the top edge); the whole subject and the whole pedestal visible,
nothing cropped.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background, no gradient, no vignette, no floor, no cast
shadow on the background; soft even studio lighting, no strong rim light, no depth of field.
READABILITY: large clear shapes; arms, wings and held objects separated from the body by visible gaps; thin parts such
as strings, shafts and staffs clearly readable, not hair-thin; fine detail stays inside the silhouette.
FORBIDDEN: text, letters, numbers, logos, watermark, frame, collage or several views, extra figures, extra limbs,
heads, wings or weapons, team colours, a coloured ring or metal band on the pedestal.
Output one single image.
CORRECTION (fix only this; everything above still applies):
- strict front orthographic view: pedestal top surface is visible -> make both stacked discs exactly edge-on, hide the top surfaces completely, use straight horizontal front edges and zero camera elevation.
- plain flat dark gray background: visible gradient and vignette -> use one uniform flat neutral charcoal gray across the entire background, with no floor or background shadow.
- both arms clearly apart from the torso: fur and shield obscure the arm-to-body gaps -> leave an unmistakable background gap between each arm and the torso, including behind the shield, with elbows slightly bent and the neutral standing pose preserved.
```

## Проверка и ограничения

На 1a создан только фронт; межвидовая согласованность не оценивается. Между g1 и g2 сохранены герой, сторона меча/щита, мех, плетёная борода и палитра. В g2 изменились детали костюма, положение щита/торка и пропорции; подставка показана с ребра, просветы у рук яснее, фон ровнее. Эти кандидаты не образуют набор разных ракурсов.

G1: код 0, WARN view.frame_top; визуальные замечания вызвали CORRECTION. G2 и финальный прогон: код 0, 13 PASS, 0 WARN, 0 FAIL. CHECKLIST у выбранного g2 пройден. Кольчуга содержит подробные кольца вместо полностью крупных плоских пятен; ограничение отмечено в verification.json. Художественная приёмка не выполнялась, статус «предложено». Пиксели не редактировались.

# Промпты ASSET-BEOWULF-001 — этап 1c

Дата: 2026-10-14.
Инструмент: image_gen, встроенный; режим edit/style-transfer; transparent_background=false.
Размер в вызове не задан; аспект 3:4 указан только в CORE.
Пути референсов ниже — от корня репозитория, в фактическом порядке вызова; инструмент получил их абсолютное разрешение через корень проекта.

## art/imagegen/concept-beowulf-codex/concepts/beowulf-front-g1.png

Дата: 2026-10-14T07:02:53.749947+00:00
Инструмент: image_gen; режим edit.
prompt_key: 1c/front/g1

referenced_image_paths, в порядке вызова:

```json
[
  "art/pipeline-candidates/ASSET-BEOWULF-001/20261013-draft-tripo/orthos/ortho_front.png",
  "art/imagegen/concept-beowulf-codex/design/beowulf-front.png"
]
```

Точный промпт:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, FRONT
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Beowulf, the Geatish hero: huge bearded warrior in chainmail-patterned tunic painted as large flat shapes, fur mantle over the shoulders, iron helmet with brow ridges, leather boots; broad longsword in his RIGHT hand, round wooden shield on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: longsword in the figure's own RIGHT hand; round wooden shield on the LEFT arm; fur mantle; braided beard.
PALETTE: iron grey #5E6266, fur brown #6E5236, weathered wood #8B6A43, accent gold torc #C99A35. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
VIEW: FRONT: strict front orthographic view, the figure faces the camera, no three-quarter turn.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x17.6%-82.4%, pedestal top y85.9%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

## art/imagegen/concept-beowulf-codex/concepts/beowulf-front-g2.png

Дата: 2026-10-14T07:04:31.339513+00:00
Инструмент: image_gen; режим edit.
prompt_key: 1c/front/g2

referenced_image_paths, в порядке вызова:

```json
[
  "art/pipeline-candidates/ASSET-BEOWULF-001/20261013-draft-tripo/orthos/ortho_front.png",
  "art/imagegen/concept-beowulf-codex/design/beowulf-front.png"
]
```

Точный промпт:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, FRONT
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Beowulf, the Geatish hero: huge bearded warrior in chainmail-patterned tunic painted as large flat shapes, fur mantle over the shoulders, iron helmet with brow ridges, leather boots; broad longsword in his RIGHT hand, round wooden shield on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: longsword in the figure's own RIGHT hand; round wooden shield on the LEFT arm; fur mantle; braided beard.
PALETTE: iron grey #5E6266, fur brown #6E5236, weathered wood #8B6A43, accent gold torc #C99A35. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
VIEW: FRONT: strict front orthographic view, the figure faces the camera, no three-quarter turn.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x17.6%-82.4%, pedestal top y85.9%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
CORRECTION (fix only this; everything above still applies):
- silhouette, pose, arm and weapon positions: the sword outline and grip position drift from image 1 -> paint within image 1's exact sword, hand, arm and body contours, keeping every edge and grip at the same frame coordinates.
- identity, costume, colours and materials: the pedestal is pale white -> transfer the approved design's dark charcoal stone material onto the unchanged pedestal shape from image 1.
- same plain flat dark gray background: a visible gradient remains -> make every background pixel one flat neutral charcoal gray tone like image 1, without vignette or lighter patches.
```

## art/imagegen/concept-beowulf-codex/concepts/beowulf-side-g1.png

Дата: 2026-10-14T07:05:45.566316+00:00
Инструмент: image_gen; режим edit.
prompt_key: 1c/side/g1

referenced_image_paths, в порядке вызова:

```json
[
  "art/pipeline-candidates/ASSET-BEOWULF-001/20261013-draft-tripo/orthos/ortho_left.png",
  "art/imagegen/concept-beowulf-codex/design/beowulf-front.png"
]
```

Точный промпт:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, LEFT SIDE
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Beowulf, the Geatish hero: huge bearded warrior in chainmail-patterned tunic painted as large flat shapes, fur mantle over the shoulders, iron helmet with brow ridges, leather boots; broad longsword in his RIGHT hand, round wooden shield on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: longsword in the figure's own RIGHT hand; round wooden shield on the LEFT arm; fur mantle; braided beard.
PALETTE: iron grey #5E6266, fur brown #6E5236, weathered wood #8B6A43, accent gold torc #C99A35. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
VIEW: LEFT SIDE: strict profile, the figure's OWN left side faces the camera, its face toward the left edge of the image, no three-quarter view.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x17.9%-82.1%, pedestal top y85.9%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

## art/imagegen/concept-beowulf-codex/concepts/beowulf-side-g2.png

Дата: 2026-10-14T07:06:48.317304+00:00
Инструмент: image_gen; режим edit.
prompt_key: 1c/side/g2

referenced_image_paths, в порядке вызова:

```json
[
  "art/pipeline-candidates/ASSET-BEOWULF-001/20261013-draft-tripo/orthos/ortho_left.png",
  "art/imagegen/concept-beowulf-codex/design/beowulf-front.png"
]
```

Точный промпт:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, LEFT SIDE
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Beowulf, the Geatish hero: huge bearded warrior in chainmail-patterned tunic painted as large flat shapes, fur mantle over the shoulders, iron helmet with brow ridges, leather boots; broad longsword in his RIGHT hand, round wooden shield on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: longsword in the figure's own RIGHT hand; round wooden shield on the LEFT arm; fur mantle; braided beard.
PALETTE: iron grey #5E6266, fur brown #6E5236, weathered wood #8B6A43, accent gold torc #C99A35. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
VIEW: LEFT SIDE: strict profile, the figure's OWN left side faces the camera, its face toward the left edge of the image, no three-quarter view.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x17.9%-82.1%, pedestal top y85.9%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
CORRECTION (fix only this; everything above still applies):
- silhouette, pose, arm and weapon positions: the blade outline and face contours drift from image 1 -> keep image 1's exact profile silhouette and all sword, shield, helmet, nose and beard edges at their original normalized frame coordinates.
- same plain flat dark gray background: there is slight background shading -> use one uniform flat neutral dark charcoal gray like image 1, without gradient, vignette or a lighter central zone.
```

## art/imagegen/concept-beowulf-codex/concepts/beowulf-back-g1.png

Дата: 2026-10-14T07:07:59.794831+00:00
Инструмент: image_gen; режим edit.
prompt_key: 1c/back/g1

referenced_image_paths, в порядке вызова:

```json
[
  "art/pipeline-candidates/ASSET-BEOWULF-001/20261013-draft-tripo/orthos/ortho_back.png",
  "art/imagegen/concept-beowulf-codex/design/beowulf-front.png",
  "art/imagegen/concept-beowulf-codex/beowulf-side.png"
]
```

Точный промпт:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, BACK
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
Image 3 is the finished side view of the SAME miniature, for continuity of colours and details only.
SUBJECT: Beowulf, the Geatish hero: huge bearded warrior in chainmail-patterned tunic painted as large flat shapes, fur mantle over the shoulders, iron helmet with brow ridges, leather boots; broad longsword in his RIGHT hand, round wooden shield on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: longsword in the figure's own RIGHT hand; round wooden shield on the LEFT arm; fur mantle; braided beard.
PALETTE: iron grey #5E6266, fur brown #6E5236, weathered wood #8B6A43, accent gold torc #C99A35. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
VIEW: BACK: camera directly behind, no face visible, no three-quarter view. The weapon in the figure's own RIGHT hand appears on the viewer's RIGHT.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x17.6%-82.4%, pedestal top y85.9%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

## art/imagegen/concept-beowulf-codex/concepts/beowulf-back-g2.png

Дата: 2026-10-14T07:09:10.168174+00:00
Инструмент: image_gen; режим edit.
prompt_key: 1c/back/g2

referenced_image_paths, в порядке вызова:

```json
[
  "art/pipeline-candidates/ASSET-BEOWULF-001/20261013-draft-tripo/orthos/ortho_back.png",
  "art/imagegen/concept-beowulf-codex/design/beowulf-front.png",
  "art/imagegen/concept-beowulf-codex/beowulf-side.png"
]
```

Точный промпт:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, BACK
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
Image 3 is the finished side view of the SAME miniature, for continuity of colours and details only.
SUBJECT: Beowulf, the Geatish hero: huge bearded warrior in chainmail-patterned tunic painted as large flat shapes, fur mantle over the shoulders, iron helmet with brow ridges, leather boots; broad longsword in his RIGHT hand, round wooden shield on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: longsword in the figure's own RIGHT hand; round wooden shield on the LEFT arm; fur mantle; braided beard.
PALETTE: iron grey #5E6266, fur brown #6E5236, weathered wood #8B6A43, accent gold torc #C99A35. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
VIEW: BACK: camera directly behind, no face visible, no three-quarter view. The weapon in the figure's own RIGHT hand appears on the viewer's RIGHT.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x17.6%-82.4%, pedestal top y85.9%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
CORRECTION (fix only this; everything above still applies):
- silhouette, pose, arm and weapon positions: the blade and cloak contours drift from image 1 -> paint within image 1's exact silhouette, retaining the sword width, tip shape, grip, arms and cloak edges at their original normalized coordinates.
- identity, costume, colours and materials: chainmail now covers the arms down to the bracers -> keep the approved design's short chainmail sleeves and exposed skin between sleeve hems and leather bracers, as visible in image 1.
- same plain flat dark gray background: slight shading and a different gray tone remain -> use image 1's single uniform neutral charcoal gray background without gradient or vignette.
```

## Проверка и ограничения

Выбраны front g2, side g1, back g2. Между видами сохранены герой, железный шлем, коричневый мех, кожаные сапоги/наручи, деревянный щит на левой руке и меч на правой, тёмная двухъярусная подставка. Борода и торк видны там, где позволяет ракурс. Back использует выбранный side g1 только для материалов и деталей.

Изменения при повторах: front — светлая подставка стала тёмной; side g2 — переработаны контуры и отделка шлема, кандидат отклонён в пользу g1; back — восстановлены короткие рукава и открытые руки. Точный контур меча и отдельных элементов силуэта, буквальная рамка и строго сплошной одинаковый фон не восстановлены. Эти пункты CHECKLIST провалены и внесены в limit_reached для всех трёх видов. Все 6 отдельных прогонов checker: код 0; финальный набор: код 0, 33 PASS, 0 WARN, 0 FAIL. Межвидовые размеры равны до пикселя; результаты не ретушировались и не перекодировались. Кольчуга детальнее плоских пятен CORE. Приёмщик определяет достаточность; статус «предложено».

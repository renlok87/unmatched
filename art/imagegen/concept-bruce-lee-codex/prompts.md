# Промпты концепта Bruce Lee — этап 1a

Дата: 2026-10-13.
Инструмент: image_gen, встроенный режим generate.
Один вызов — одно изображение — один фронтальный вид; размер не задавался, аспект 3:4 задан в CORE.

## art/imagegen/concept-bruce-lee-codex/concepts/bruce-lee-design-front-g1.png

Ключ: 1a/design-front/g1.
Выбрано: нет.
referenced_image_paths в порядке вызова (пути относительно корня репозитория):

- art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png — SHA-256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Bruce Lee, the martial artist (Unmatched: Bruce Lee): lean muscular martial artist in a yellow jumpsuit with black side stripes, bare-handed fighting stance, intense expression.
IDENTITY ANCHORS, each clearly visible: yellow jumpsuit with black side stripes; bare-handed fighting stance; short black hair.
PALETTE: suit yellow #E0B830, stripe black #141414, skin tan #C49A74, accent shoe black #1E1C1C. These are the main colours plus one accent; no other strong colours.
POSE: Neutral standing pose of a tabletop miniature: both feet planted on the pedestal, weight even, both arms held slightly away from the torso with a visible gap between each arm and the body, elbows slightly bent; not a T-pose and not an A-pose. No weapon or held object.
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

## art/imagegen/concept-bruce-lee-codex/concepts/bruce-lee-design-front-g2.png

Ключ: 1a/design-front/g2.
Выбрано: да.
referenced_image_paths в порядке вызова (пути относительно корня репозитория):

- art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png — SHA-256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Bruce Lee, the martial artist (Unmatched: Bruce Lee): lean muscular martial artist in a yellow jumpsuit with black side stripes, bare-handed fighting stance, intense expression.
IDENTITY ANCHORS, each clearly visible: yellow jumpsuit with black side stripes; bare-handed fighting stance; short black hair.
PALETTE: suit yellow #E0B830, stripe black #141414, skin tan #C49A74, accent shoe black #1E1C1C. These are the main colours plus one accent; no other strong colours.
POSE: Neutral standing pose of a tabletop miniature: both feet planted on the pedestal, weight even, both arms held slightly away from the torso with a visible gap between each arm and the body, elbows slightly bent; not a T-pose and not an A-pose. No weapon or held object.
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
- CHECKLIST strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: the pedestal top is visibly an ellipse -> show both discs exactly edge-on with straight horizontal front edges and zero visible top surface.
- CHECKLIST the whole subject and pedestal visible, nothing cropped; plain flat dark gray background: the background has subtle tonal variation -> use one completely uniform flat neutral dark gray tone throughout the empty background.
```

## Проверка и ограничения

Сгенерирован только design-front. Межвидовая согласованность на 1a не оценивается: бокового и заднего вида нет.
Между g1 и g2 сохранены персонаж, жёлто-чёрная палитра, короткие чёрные волосы, пустые руки, боевая стойка и двухдисковая каменная подставка. g2 — отдельная генерация по тому же неизменному CORE и двум строкам CORRECTION; g1 не использован как изображение-вход.
В g2 подставка стала видна с ребра без раскрытой верхней плоскости, фон стал нейтральнее и ровнее. Генератор также изменил положение кистей, складки, детали лица и обуви; это зафиксированные различия попыток, а не правка пикселей.
У g1 и g2 скрипт вернул 0: 12 PASS, 1 WARN, 0 FAIL. WARN view.frame_top: g1 3,177%, g2 3,453% при требовании 4%. Этот WARN допустим по заданию; изображения не кадрировались и не нормализовались.
Все шесть пунктов визуального CHECKLIST у выбранного g2 пройдены. Тон фона содержит слабое зерно генерации (p99 отклонения рамки 2 уровня RGB), сохранённое без ретуши.
Исходный эталон и palette.json не изменены. Все PNG скопированы побайтово; оригиналы image_gen сохранены.

## 1c (2026-10-21, Tripo Studio Image, GPT Image 2)

### bruce-lee-front-g1

referenced_image_paths: art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261013-draft-tripo/orthos/ortho_front.png, art/imagegen/concept-bruce-lee-codex/design/bruce-lee-front.png

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, FRONT
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Bruce Lee, the martial artist (Unmatched: Bruce Lee): lean muscular martial artist in a yellow jumpsuit with black side stripes, bare-handed fighting stance, intense expression.
IDENTITY ANCHORS, where visible from this side: yellow jumpsuit with black side stripes; bare-handed fighting stance; short black hair.
PALETTE: suit yellow #E0B830, stripe black #141414, skin tan #C49A74, accent shoe black #1E1C1C. No weapon or held object.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: FRONT: strict front orthographic view, the figure faces the camera, no three-quarter turn.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x15.0%-85.0%, pedestal top y84.1%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

### bruce-lee-side-g1

referenced_image_paths: art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261013-draft-tripo/orthos/ortho_left.png, art/imagegen/concept-bruce-lee-codex/design/bruce-lee-front.png

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, LEFT SIDE
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Bruce Lee, the martial artist (Unmatched: Bruce Lee): lean muscular martial artist in a yellow jumpsuit with black side stripes, bare-handed fighting stance, intense expression.
IDENTITY ANCHORS, where visible from this side: yellow jumpsuit with black side stripes; bare-handed fighting stance; short black hair.
PALETTE: suit yellow #E0B830, stripe black #141414, skin tan #C49A74, accent shoe black #1E1C1C. No weapon or held object.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: LEFT SIDE: strict profile, the figure's OWN left side faces the camera, its face toward the left edge of the image, no three-quarter view.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x15.3%-84.7%, pedestal top y84.1%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

### bruce-lee-back-g1

referenced_image_paths: art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261013-draft-tripo/orthos/ortho_back.png, art/imagegen/concept-bruce-lee-codex/design/bruce-lee-front.png, art/imagegen/concept-bruce-lee-codex/concepts/bruce-lee-side-g1.png

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, BACK
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
Image 3 is the finished side view of the SAME miniature, for continuity of colours and details only.
SUBJECT: Bruce Lee, the martial artist (Unmatched: Bruce Lee): lean muscular martial artist in a yellow jumpsuit with black side stripes, bare-handed fighting stance, intense expression.
IDENTITY ANCHORS, where visible from this side: yellow jumpsuit with black side stripes; bare-handed fighting stance; short black hair.
PALETTE: suit yellow #E0B830, stripe black #141414, skin tan #C49A74, accent shoe black #1E1C1C. No weapon or held object.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: BACK: camera directly behind, no face visible, no three-quarter view.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x15.0%-85.0%, pedestal top y84.1%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

### Проверка и ограничения

Силуэт и рамка держатся за орто (верх 3,9–4,2 %, земля 93,4–95,4 %); идентичность и палитра — от дизайна 1a. На back видны кончики пальцев правой руки сбоку (как на орто). Низ подставки side/back на 1,5–2,0 % ниже front (WARN set.base_bottom).

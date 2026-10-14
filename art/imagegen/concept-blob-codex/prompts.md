# ASSET-BLOB-001: concept prompts 1a

Date: 2026-10-13
Tool: image_gen (built-in), mode: generate

referenced_image_paths below are repository-relative, in call order; each call resolved the input to its absolute local path. No size argument was supplied.

## art/imagegen/concept-blob-codex/concepts/blob-design-front-g1.png

Date: 2026-10-13T08:04:43+00:00
Tool: image_gen
Prompt key: 1a/design-front/g1

referenced_image_paths:

- art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png (sha256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9)


```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Blob, a pulp-era monster (Unmatched: Tales to Amaze): amorphous mass of glossy translucent pink-red jelly piled into a lumpy mound with half-dissolved objects visible inside.
IDENTITY ANCHORS, each clearly visible: amorphous glossy jelly mound; translucent pink-red; objects visible inside.
PALETTE: jelly red #C8424A, jelly pink #E58FA3, core dark #6A1F2A, accent highlight white #F2E8E8. These are the main colours plus one accent; no other strong colours.
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

## art/imagegen/concept-blob-codex/concepts/blob-design-front-g2.png

Date: 2026-10-13T08:06:48+00:00
Tool: image_gen
Prompt key: 1a/design-front/g2

referenced_image_paths:

- art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png (sha256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9)


```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Blob, a pulp-era monster (Unmatched: Tales to Amaze): amorphous mass of glossy translucent pink-red jelly piled into a lumpy mound with half-dissolved objects visible inside.
IDENTITY ANCHORS, each clearly visible: amorphous glossy jelly mound; translucent pink-red; objects visible inside.
PALETTE: jelly red #C8424A, jelly pink #E58FA3, core dark #6A1F2A, accent highlight white #F2E8E8. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: a narrow crescent of the pedestal top is visible -> show both stacked discs strictly edge-on with straight horizontal upper edges and absolutely no visible top surface.
```

## Проверка и ограничения

Создан только design-front; сравнение с side/back не выполнялось. Между g1 и g2 сохранены аморфный холм, два боковых отростка, розово-красное желе, предметы внутри и два диска подставки. Изменились набор и положение внутренних предметов, детали силуэта и изгибы отростков; в g2 убрана видимая верхняя поверхность подставки. CORE не менялся; добавлена одна строка CORRECTION.

Все три проверки: exit 0, 13 PASS, 0 WARN, 0 FAIL. Все шесть пунктов CHECKLIST у g2 выполнены. Отклонения CORE: диаметр подставки около 0,81 высоты фигуры вместо 0,55; две отдельные стопы не читаются. Они записаны в unmet_requirements в art/imagegen/concept-blob-codex/verification.json. Лимит 2/2 использован. Изображения не редактировались, копии совпадают с оригиналами побайтово, входы неизменны. Статус «предложено».

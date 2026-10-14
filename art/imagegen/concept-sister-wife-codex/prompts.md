# ASSET-SISTER-WIFE-001 concept 1a

Date: 2026-10-13
Tool: image_gen
Mode: generate

## art/imagegen/concept-sister-wife-codex/concepts/sister-wife-design-front-g1.png

Prompt key: 1a/design-front/g1

referenced_image_paths (in call order):

- art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: A vampire bride, one of Dracula's three sisters: pale beautiful undead woman with long dark hair, flowing white burial gown with a torn hem, clawed hands held away from the body, red lips.
IDENTITY ANCHORS, each clearly visible: flowing white burial gown; clawed hands; long dark hair; pale skin with red lips.
PALETTE: gown white #E4DFD6, hair black #1E1A1C, pale skin #D9D2C9, accent blood red #8F1C1C. These are the main colours plus one accent; no other strong colours.
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

## art/imagegen/concept-sister-wife-codex/concepts/sister-wife-design-front-g2.png

Prompt key: 1a/design-front/g2

referenced_image_paths (in call order):

- art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: A vampire bride, one of Dracula's three sisters: pale beautiful undead woman with long dark hair, flowing white burial gown with a torn hem, clawed hands held away from the body, red lips.
IDENTITY ANCHORS, each clearly visible: flowing white burial gown; clawed hands; long dark hair; pale skin with red lips.
PALETTE: gown white #E4DFD6, hair black #1E1A1C, pale skin #D9D2C9, accent blood red #8F1C1C. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: a narrow ellipse of the pedestal top is visible and the front edge curves -> show both stacked discs exactly edge-on, with straight horizontal front edges and absolutely no visible top surface.
```

# Проверка и ограничения

Создан только один вид design-front этапа 1a. Между g1 и g2 совпадают основные якоря: белое рваное платье, тёмные длинные волосы, бледная кожа, красные губы и когти, фронтальное лицо, одна двухъярусная подставка. Это два самостоятельных варианта, не набор согласованных видов.

В g2 верх подставки скрыт и её передние края горизонтальны. Одновременно инструмент изменил украшения, добавил фату, красные розы и красные следы на ткани; эти изменения не задавались коррекцией. Выбрана g2 по выполнению чек-листа. Никакой обработки сгенерированных PNG не было.

Финальная проверка: код 0, 11 PASS, 2 WARN, 0 FAIL. WARN: view.frame_top и view.single_component. Верх маски y2,210% вместо ≥4%, низ y97,099% вместо 93%; отклонения внесены в verification.json. Точная ортографическая проекция оценена глазами, параметры камеры недоступны. Лимит использован полностью: 2/2; проваленных пунктов чек-листа у выбранной генерации нет.

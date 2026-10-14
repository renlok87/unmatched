# Промпты концепта Dr. Jekyll

Дата: 2026-10-13. Инструмент: image_gen.imagegen. Режим: generate.

Пути референсов ниже относительны корню репозитория и перечислены в порядке вызова; при передаче инструменту они разрешены в абсолютные пути. Размер не передавался; формат 3:4 указан только в CORE.

## concepts/dr-jekyll-design-front-g1.png

prompt_key: 1a/design-front/g1

referenced_image_paths:

1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Dr. Jekyll: respectable Victorian doctor in a grey frock coat, waistcoat and cravat, neat side-parted hair and sideburns, holding a glass vial of glowing green potion up in his LEFT hand, doctor's bag in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: glowing green potion vial in the LEFT hand; doctor's bag in the RIGHT hand; grey frock coat; cravat.
PALETTE: frock grey #5C5E63, cravat cream #DCD3BE, leather bag #5A3B26, accent potion green #5FD35A. These are the main colours plus one accent; no other strong colours.
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

## concepts/dr-jekyll-design-front-g2.png

prompt_key: 1a/design-front/g2

referenced_image_paths:

1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Dr. Jekyll: respectable Victorian doctor in a grey frock coat, waistcoat and cravat, neat side-parted hair and sideburns, holding a glass vial of glowing green potion up in his LEFT hand, doctor's bag in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: glowing green potion vial in the LEFT hand; doctor's bag in the RIGHT hand; grey frock coat; cravat.
PALETTE: frock grey #5C5E63, cravat cream #DCD3BE, leather bag #5A3B26, accent potion green #5FD35A. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: pedestal top is visible as an ellipse -> show both stacked discs exactly edge-on with straight horizontal front edges and no visible top surface.
```

## Проверка и ограничения

Есть только один вид design-front, сравнения front/side/back нет. Между g1 и g2 сохранены образ доктора, анатомические стороны предметов и основные цвета. Изменились скульптурные детали одежды, форма саквояжа и положение руки; повтора неизменного дизайна генератор не гарантирует. Целевая коррекция скрыла верх подставки и выпрямила края её ярусов.

Выбран g2. Все три запуска скрипта: код 0, 12 PASS, 1 WARN, 0 FAIL. WARN по верхнему отступу разрешён: у g2 2,970%. Низ основания g2 95,304%, а не 93%. Буквальный запрет предметов в руках несовместим с обязательными identity anchors; пункт CHECKLIST отмечен failed в verification.json и limit_reached. Лимит 2/2 использован. Сырые изображения не изменялись.

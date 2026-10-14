# Промпты — боцман-пират, этап 1a

Дата: 2026-10-13. Инструмент: встроенный image_gen. Режим: generate с референсом качества.

## 1a/design-front/g1

Файл: art/imagegen/concept-pirate-boatswain-codex/concepts/pirate-boatswain-design-front-g1.png

referenced_image_paths, в порядке вызова (пути в записи относительно корня репозитория; в инструмент переданы их абсолютные эквиваленты):

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png — SHA-256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9

Точный prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: A plump bespectacled pirate boatswain: round bald man with tiny spectacles, red knit cap, striped shirt, rolled trousers, holding a short cutlass in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: short cutlass in the figure's own RIGHT hand; red knit cap; tiny spectacles; striped shirt.
PALETTE: stripe blue #4A6FA5, cap red #B2342C, trouser tan #A08262, accent spectacle brass #C9A24A. These are the main colours plus one accent; no other strong colours.
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

## 1a/design-front/g2

Файл: art/imagegen/concept-pirate-boatswain-codex/concepts/pirate-boatswain-design-front-g2.png

referenced_image_paths, в порядке вызова (пути в записи относительно корня репозитория; в инструмент переданы их абсолютные эквиваленты):

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png — SHA-256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9

Точный prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: A plump bespectacled pirate boatswain: round bald man with tiny spectacles, red knit cap, striped shirt, rolled trousers, holding a short cutlass in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: short cutlass in the figure's own RIGHT hand; red knit cap; tiny spectacles; striped shirt.
PALETTE: stripe blue #4A6FA5, cap red #B2342C, trouser tan #A08262, accent spectacle brass #C9A24A. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: the pedestal's top surface and curved top edge are visible -> show both stacked discs exactly edge-on with straight horizontal front edges and no visible top surface.
```

## Проверка и ограничения

Создан только design-front; согласованность фронта, бока и спины на этапе 1a не проверяется. Между попытками сохранены полнота фигуры, красная шапка, маленькие латунные очки, полосатая рубашка, бежевые подвёрнутые брюки, оружие в правой руке персонажа (слева для зрителя), обе руки с зазорами от корпуса и двухъярусная тёмная каменная подставка.

В g1 была видна верхняя поверхность подставки; в g2 она скрыта, грани горизонтальны. При повторной генерации также изменились борода (в g2 остались усы и бакенбарды), ворот, ремни, расположение верёвки, носки и обувь. Запрошенная коррекция касалась только камеры и подставки; остальные различия внесены генератором при новой генерации из того же единственного референса. Ретуши и преобразований PNG нет.

g2 выбран после визуального осмотра всех шести пунктов CHECKLIST и скрипта с кодом 0. Сохраняется допустимый WARN view.single_component. Подставка шире ориентира CORE: около 0,75 роста фигуры вместо около 0,55; это ограничение записано в verification.json. Круглое сечение скрытой сверху подставки не подтверждается одним видом. Размеры обоих оригинальных PNG 1086 × 1448, аспект 3:4; размер инструменту не задавался. Две генерации из двух использованы, проваленных пунктов CHECKLIST у выбранного g2 нет.

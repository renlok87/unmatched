# Промпты концепта Титании — этап 1a

Дата: 2026-10-13.
Инструмент: image_gen.imagegen; режим: generate.

Каждый вызов создаёт один фронтальный дизайн. Единственный графический вход — эталон качества Medusa; палитра не передавалась как изображение. Пути referenced_image_paths ниже записаны относительно корня репозитория в порядке вызова; инструменту передавались соответствующие абсолютные пути. Размер не задавался, аспект 3:4 указан только в CORE.

## titania-design-front-g1.png

prompt_key: `1a/design-front/g1`.
Дата: 2026-10-13. Инструмент: image_gen.imagegen.
referenced_image_paths:

1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Titania, queen of the fairies from A Midsummer Night's Dream (Unmatched: Slings and Arrows): tall regal fairy queen with translucent dragonfly wings, gown of leaves and petals, flower crown, long silver hair, one hand raised with glowing pollen.
IDENTITY ANCHORS, each clearly visible: translucent dragonfly wings; gown of leaves and petals; flower crown; long silver hair; glowing pollen in a raised hand.
PALETTE: leaf green #4E7A3A, petal pink #D96A9A, hair silver #D0D4D8, accent glow gold #F0D060. These are the main colours plus one accent; no other strong colours.
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

## titania-design-front-g2.png

prompt_key: `1a/design-front/g2`.
Дата: 2026-10-13. Инструмент: image_gen.imagegen.
referenced_image_paths:

1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Titania, queen of the fairies from A Midsummer Night's Dream (Unmatched: Slings and Arrows): tall regal fairy queen with translucent dragonfly wings, gown of leaves and petals, flower crown, long silver hair, one hand raised with glowing pollen.
IDENTITY ANCHORS, each clearly visible: translucent dragonfly wings; gown of leaves and petals; flower crown; long silver hair; glowing pollen in a raised hand.
PALETTE: leaf green #4E7A3A, petal pink #D96A9A, hair silver #D0D4D8, accent glow gold #F0D060. These are the main colours plus one accent; no other strong colours.
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
- CHECKLIST strict front orthographic view: the pedestal shows a shallow top ellipse -> show both stacked discs exactly edge-on, with straight horizontal edges and no visible top surface; keep the figure square to the camera.
- CHECKLIST plain flat dark gray background: the background has a visible central gradient -> use one uniform charcoal gray tone everywhere outside the silhouette, without a gradient, vignette or shadow.
- CHECKLIST both arms clearly apart from the torso: hair, wings and hanging petals obscure the open gaps -> keep a clearly visible open gap between each arm and the torso, with no hair, wing or gown crossing either gap.
```

## Проверка и ограничения

Создан только вид design-front; согласованность разных видов ещё не оценивалась. Обе генерации сохраняют пять якорей, палитру, фронтальное положение и единственную подставку. В g2 края подставки горизонтальнее, фон ровнее и зазоры у рук яснее; рисунок листьев, цветов, короны, крыльев и положение свободной кисти изменились. Выбран g2.

Все три прогона check_concept_views.py завершились с кодом 0, каждый: PASS 12, WARN 1, FAIL 0. В g2 остаётся WARN view.frame_top: 3,246% вместо минимум 4%; низ подставки 95,442% вместо целевых 93%, её центр x48,665% вместо x50%. Это записано в verification.json. Вторая стопа скрыта платьем. Сырой результат не редактировался; обе копии и оригиналы совпадают побайтно. Все шесть пунктов CHECKLIST выбранного g2 прошли визуальную проверку. Художественная приёмка в этом запуске не выполнялась; статус «предложено».

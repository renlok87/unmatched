# Промпты концепта Martian Invader — этап 1a

Дата: 2026-10-13.
Инструмент: image_gen.imagegen; встроенный режим generate.
Два вызова, по одному изображению на вызов. Размер не передавался; аспект 3:4 задан текстом CORE.

## art/imagegen/concept-martian-invader-codex/concepts/martian-invader-design-front-g1.png

Date: 2026-10-13T08:17:59+00:00
Tool: image_gen.imagegen
Prompt key: 1a/design-front/g1

referenced_image_paths в порядке вызова, нормализованы относительно корня репозитория:

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png (sha256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9)

Точный текст промпта:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Martian Invader, a pulp-era villain (Unmatched: Tales to Amaze): big-brained alien with a large exposed head inside a glass dome helmet, slim body in a silver space suit with fins, ray gun in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: ray gun in the RIGHT hand; glass dome helmet; big exposed brain; silver space suit with fins.
PALETTE: suit silver #B8BEC4, skin green #7AA65A, fin red #B3202A, accent ray cyan #4AD9E0. These are the main colours plus one accent; no other strong colours.
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

## art/imagegen/concept-martian-invader-codex/concepts/martian-invader-design-front-g2.png

Date: 2026-10-13T08:19:55+00:00
Tool: image_gen.imagegen
Prompt key: 1a/design-front/g2

referenced_image_paths в порядке вызова, нормализованы относительно корня репозитория:

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png (sha256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9)

Точный текст промпта:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Martian Invader, a pulp-era villain (Unmatched: Tales to Amaze): big-brained alien with a large exposed head inside a glass dome helmet, slim body in a silver space suit with fins, ray gun in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: ray gun in the RIGHT hand; glass dome helmet; big exposed brain; silver space suit with fins.
PALETTE: suit silver #B8BEC4, skin green #7AA65A, fin red #B3202A, accent ray cyan #4AD9E0. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: the pedestal top face is visibly exposed and its front top edge is curved -> use true parallel front projection with zero elevation; hide the entire top surface of both discs and show their front edges as straight horizontal lines.
```

## Проверка и ограничения

Создан только design-front. Межвидовой согласованности пока нет: side и back здесь не генерировались.

Между g1 и g2 сохранены герой, сторона оружия, купол, большой мозг, серебряный костюм, красные плавники, циановый акцент и двухъярусная каменная подставка. В g2 верхняя плоскость подставки скрыта; инструмент также самостоятельно изменил детали костюма, форму плавников и оружия, выражение лица. CORE неизменён; добавлена одна строка CORRECTION. Ретуши и смешения изображений не было.

Выбрана g2: все шесть пунктов CHECKLIST пройдены визуально. Финальный скрипт вернул 0, FAIL 0, WARN 2. Верхний отступ 2,762% вместо 4%; маска разделяет отдельные детали, хотя визуально фигура одна. Низ подставки 95,166% вместо 93%; отношение ширины подставки к высоте фигуры около 0,67 вместо 0,55; правый локоть согнут заметнее, чем «слегка». Круглая форма в плане единственным фронтальным растром не подтверждается. Все ограничения записаны в verification.json. Генерации сохранены побайтово, без обработки.

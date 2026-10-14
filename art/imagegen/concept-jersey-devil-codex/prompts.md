# Промпты Jersey Devil — этап 1a

Дата: 2026-10-13.
Инструмент: `image_gen.imagegen`; режим `generate`, один вызов — одно изображение, размер в пикселях не передавался. Аспект 3:4 задан только текстом CORE.

## art/imagegen/concept-jersey-devil-codex/concepts/jersey-devil-design-front-g1.png

Ключ: `1a/design-front/g1`. Дата: 2026-10-13. Инструмент: `image_gen.imagegen`.

`referenced_image_paths` в точном порядке вызова:

```json
["C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"]
```

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Jersey Devil of American folklore (Unmatched: Tales to Amaze): lean winged creature with a horse-like head, small horns, bat wings, hooved legs and a forked tail.
IDENTITY ANCHORS, each clearly visible: horse-like head with small horns; bat wings; hooved legs; forked tail.
PALETTE: hide brown #4E3A2E, wing grey #5E5A56, horn bone #D9CFB8, accent eye red #C8322A. These are the main colours plus one accent; no other strong colours.
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

## art/imagegen/concept-jersey-devil-codex/concepts/jersey-devil-design-front-g2.png

Ключ: `1a/design-front/g2`. Дата: 2026-10-13. Инструмент: `image_gen.imagegen`.

`referenced_image_paths` в точном порядке вызова:

```json
["C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"]
```

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Jersey Devil of American folklore (Unmatched: Tales to Amaze): lean winged creature with a horse-like head, small horns, bat wings, hooved legs and a forked tail.
IDENTITY ANCHORS, each clearly visible: horse-like head with small horns; bat wings; hooved legs; forked tail.
PALETTE: hide brown #4E3A2E, wing grey #5E5A56, horn bone #D9CFB8, accent eye red #C8322A. These are the main colours plus one accent; no other strong colours.
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
- CHECKLIST strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: the pedestal top surface is visible and its front edge curves -> show both stacked discs exactly edge-on, with no visible top surface and a straight horizontal front edge, keeping a level front orthographic view.
```

## Проверка и ограничения

Две попытки одного фронтального дизайна сохраняют лошадиную голову с рогами, два крыла летучей мыши, копыта, раздвоенный хвост и заданную палитру. Во второй попытке исправлен профиль подставки: верхняя поверхность больше не видна, передние края горизонтальны. Также генератор изменил очертания перепонок, сделал морду симметричнее и перенёс раздвоенный конец хвоста справа в промежуток между ногами; эти изменения не задавались отдельными строками коррекции и не скрыты.

Выбран g2. Оба кандидата и финальный выбранный файл прошли `check_concept_views.py` с кодом 0, 12 PASS, 1 WARN, 0 FAIL. Визуальные пункты CHECKLIST выбранного файла отмечены в `verification.json`. Между разными ракурсами согласованность не проверялась: задача охватывает один ракурс design-front.

Остались числовые отклонения CORE: верх маски g2 на y=2,901% вместо y>=4% (допустимый WARN `view.frame_top`), низ подставки на y=94,682% вместо y=93%; центр подставки x=50,0%. Изображения не изменялись после генерации: копии побайтно совпадают с оригиналами инструмента. Статус пакета — «предложено».


## Корректирующий запуск 2026-10-13 — g3–g4

Предыдущие разделы описывают исходный запуск g1–g2. Ниже — новые точные промпты; выбранный дизайн теперь g4. Дата: 2026-10-13. Инструмент: `image_gen.imagegen`; один вызов — одно изображение. Единственный вход — QUALITY_REFERENCE; прежние кандидаты не передавались в инструмент. Размер не задавался.

## art/imagegen/concept-jersey-devil-codex/concepts/jersey-devil-design-front-g3.png

Ключ: `1a/design-front/g3`. Дата: 2026-10-13T09:49:45.419907+00:00. Инструмент: `image_gen.imagegen`.

`referenced_image_paths` в точном порядке вызова:

```json
["C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"]
```

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Jersey Devil of American folklore (Unmatched: Tales to Amaze): lean winged creature with a horse-like head, small horns, bat wings, hooved legs and a forked tail.
IDENTITY ANCHORS, each clearly visible: horse-like head with small horns; bat wings; hooved legs; forked tail.
PALETTE: hide brown #4E3A2E, wing grey #5E5A56, horn bone #D9CFB8, accent eye red #C8322A. These are the main colours plus one accent; no other strong colours.
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
- S design-front: Replace the symmetrical straight diagonal arm placement with a natural asymmetric creature stance, clearly bending both elbows at different angles while keeping both hands separated from the torso and preserving the strict front view.
- P design-front: Shorten both horns into small curved horns and darken the hide midtones toward #4E3A2E while preserving the grey wing membranes, bone-coloured horns and red eyes.
```

## art/imagegen/concept-jersey-devil-codex/concepts/jersey-devil-design-front-g4.png

Ключ: `1a/design-front/g4`. Дата: 2026-10-13T09:53:00.610689+00:00. Инструмент: `image_gen.imagegen`.

`referenced_image_paths` в точном порядке вызова:

```json
["C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"]
```

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Jersey Devil of American folklore (Unmatched: Tales to Amaze): lean winged creature with a horse-like head, small horns, bat wings, hooved legs and a forked tail.
IDENTITY ANCHORS, each clearly visible: horse-like head with small horns; bat wings; hooved legs; forked tail.
PALETTE: hide brown #4E3A2E, wing grey #5E5A56, horn bone #D9CFB8, accent eye red #C8322A. These are the main colours plus one accent; no other strong colours.
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
- S design-front: Replace the symmetrical straight diagonal arm placement with a natural asymmetric creature stance, clearly bending both elbows at different angles while keeping both hands separated from the torso and preserving the strict front view.
- P design-front: Shorten both horns into small curved horns and darken the hide midtones toward #4E3A2E while preserving the grey wing membranes, bone-coloured horns and red eyes.
- CHECKLIST strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: a strip of the pedestal top surface and a curved front edge are visible -> show both low stacked discs exactly edge-on, hide the entire top surface and keep their front edges straight and horizontal, with zero camera elevation.
```

## Проверка и ограничения

Выбран g4. В g3 и g4 неизменный CORE дополнен двумя заданными строками S и P; g4 сохраняет их дословно и добавляет одну строку по проваленному пункту ракурса подставки. У g3 была видна верхняя плоскость подставки. У g4 она скрыта, передние края горизонтальны. Оба кандидата и финальный g4: код 0, 13 PASS, 0 WARN, 0 FAIL. Все шесть визуальных пунктов CHECKLIST g4 пройдены.

Сохранились лошадиная голова, рога, крылья, копыта, раздвоенный хвост и палитра. Изменились углы локтей, форма и положение кистей, рога, полутона шкуры, контуры крыльев и положение хвоста: у g3 он справа, у g4 между ногами. Других видов нет; межвидовая согласованность не проверялась. Низ g4 находится на y=93,646% вместо 93%; отклонение раскрыто в verification.json. Изображения не редактировались. Использовано 2/2 генерации этого запуска и 4/4 суммарно. Статус — «предложено».

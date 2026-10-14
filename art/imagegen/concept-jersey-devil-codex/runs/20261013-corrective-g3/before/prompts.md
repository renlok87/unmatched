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

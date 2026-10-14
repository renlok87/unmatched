# ASSET-THE-GENIE-001 — дизайн-front, этап 1a

Дата: 2026-10-13. Инструмент: image_gen (встроенный image_gen.imagegen).
Режим: generate; одна генерация — одно изображение, один вид.
Размер не передавался; аспект 3:4 указан только в CORE. transparent_background: false.

Пути референсов ниже записаны относительно корня репозитория в порядке вызова.
При вызове инструмента локальный путь разрешён в абсолютный путь.
Единственный референс — уровень скульптуры и покраски, а не источник дизайна персонажа.
palette.json не передавалась как изображение.

## concepts/the-genie-design-front-g1.png

prompt_key: 1a/design-front/g1
referenced_image_paths:
1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Genie of the lamp (Unmatched: Houdini vs. The Genie): towering muscular blue-skinned djinn with a topknot, gold armbands and earrings, arms folded, the lower body tapering into a swirl of smoke rising from a small brass lamp on the base.
IDENTITY ANCHORS, each clearly visible: blue skin; topknot; gold armbands; arms folded; lower body is a swirl of smoke from a brass lamp.
PALETTE: skin blue #3E6AB3, gold #D4AE45, smoke blue #8AB0D9, accent sash red #B2342C. These are the main colours plus one accent; no other strong colours.
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

## concepts/the-genie-design-front-g2.png

prompt_key: 1a/design-front/g2
referenced_image_paths:
1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Genie of the lamp (Unmatched: Houdini vs. The Genie): towering muscular blue-skinned djinn with a topknot, gold armbands and earrings, arms folded, the lower body tapering into a swirl of smoke rising from a small brass lamp on the base.
IDENTITY ANCHORS, each clearly visible: blue skin; topknot; gold armbands; arms folded; lower body is a swirl of smoke from a brass lamp.
PALETTE: skin blue #3E6AB3, gold #D4AE45, smoke blue #8AB0D9, accent sash red #B2342C. These are the main colours plus one accent; no other strong colours.
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
- CHECKLIST strict front orthographic view: the pedestal top surface is visible -> show the pedestal exactly edge-on with no visible top surface and a straight horizontal front edge.
- CHECKLIST No weapon or held object (both arms clearly apart from the torso): no clear arm-to-torso gaps -> keep the arms folded, but space both upper arms away from the torso so a clear dark gap is visible on each side; no T-pose or A-pose.
```

## Проверка и ограничения

Создан только один вид — design-front; согласованность front/side/back ещё не проверялась.
В обеих генерациях совпадают идентификационные якоря, палитра, общий тип миниатюры и скрещённые руки.
В g2 изменились орнамент, пояс, форма дыма, сторона носика лампы и волосы; верхняя плоскость подставки перестала быть видна.
CORE одинаков побуквенно; g2 добавляет только две строки CORRECTION.
У обеих генераций код скрипта 0 и WARN view.frame_top; WARN не был причиной повтора.
Зазоры между руками и корпусом не получились. g2 выбран; лимит 2/2 исчерпан.
Прочие отклонения от CORE (верх и низ кадра, ширина подставки, отсутствие стоп из-за дымового низа) записаны в verification.json.
PNG не ретушировались, не масштабировались, не обрезались и не пересохранялись: оригиналы и копии сверены по SHA-256.

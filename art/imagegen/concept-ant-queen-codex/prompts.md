# Промпты — ASSET-ANT-QUEEN-001, этап 1a

Дата: 2026-10-13.
Инструмент: image_gen.imagegen, встроенный режим generate.
Один вызов — одно изображение, один фронтальный вид. Размер не передавался; отношение 3:4 задано только в тексте. transparent_background = false.

## concepts/ant-queen-design-front-g1.png

prompt_key: `1a/design-front/g1`.

referenced_image_paths в порядке вызова:
1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Ant Queen, a pulp-era monster (Unmatched: Tales to Amaze): giant queen ant with a glossy dark red exoskeleton, swollen abdomen, six legs, small crown-like head crest and mandibles.
IDENTITY ANCHORS, each clearly visible: giant ant; glossy red exoskeleton; swollen abdomen; six legs; crown-like head crest.
PALETTE: shell red #7A2A22, shell dark #3A1A16, leg black #1E1A18, accent eye amber #D9962A. These are the main colours plus one accent; no other strong colours.
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

## concepts/ant-queen-design-front-g2.png

prompt_key: `1a/design-front/g2`.

referenced_image_paths в порядке вызова:
1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Ant Queen, a pulp-era monster (Unmatched: Tales to Amaze): giant queen ant with a glossy dark red exoskeleton, swollen abdomen, six legs, small crown-like head crest and mandibles.
IDENTITY ANCHORS, each clearly visible: giant ant; glossy red exoskeleton; swollen abdomen; six legs; crown-like head crest.
PALETTE: shell red #7A2A22, shell dark #3A1A16, leg black #1E1A18, accent eye amber #D9962A. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view: the pedestal top is visibly exposed and its front edge curves -> use exact zero-elevation orthographic front projection; show only the two discs' vertical sides, with perfectly straight horizontal top/front edges and absolutely no visible top-surface area.
```

## Проверка и ограничения

Этап 1a содержит один вид; согласованность между front, side и back не оценивается. Между кандидатами сохранены общий фронтальный силуэт, красный панцирь, чёрные ноги, янтарные глаза, вздутое брюшко, шесть конечностей, коронообразный гребень и двухъярусная тёмная подставка. g2 исправляет показ верхней поверхности подставки. Повторная генерация также изменила пропорции брюшка, деталей панциря, жвал, гребня и ног; геометрическая идентичность кандидатов не заявляется.

Выбран g2: визуальный CHECKLIST пройден; финальная автопроверка — 13 PASS, 0 WARN, 0 FAIL, код 0. g1 не прошёл визуальный пункт ракурса подставки, но его автоматический WARN по верхнему отступу не был причиной повторной генерации. Подставка выбранного g2 шире пропорции CORE (приблизительно 0,74 вместо 0,55); гребень получился крупным. Эти ограничения занесены в verification.json. Круглую форму основания в плане нельзя независимо проверить по одному виду. Ретушь, масштабирование, обрезка, перекраска и повторное кодирование файлов не выполнялись.

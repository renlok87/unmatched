# Промпты концепта Rocksteady — 1a

Дата: 2026-10-13. Инструмент: `image_gen.imagegen`. Режим: `text-to-image`. По одному вызову и изображению на поколение; размер параметром не передавался, аспект 3:4 указан только в CORE. `transparent_background=false`.

Пути `referenced_image_paths` ниже записаны относительно корня репозитория, в порядке вызова. Инструменту передан абсолютный путь того же файла. Других входных изображений нет.

## concepts/bebop-rocksteady-2-design-front-g1.png

Дата: 2026-10-13. Tool: `image_gen.imagegen`. Prompt key: `1a/design-front/g1`.

referenced_image_paths:

1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png` — SHA-256 `e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9`.

Точный текст переданного промпта:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Rocksteady from Teenage Mutant Ninja Turtles (Unmatched: Adventures TMNT): hulking mutant rhinoceros soldier with a horn, grey hide, camouflage vest and army helmet, heavy rifle in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: heavy rifle in the RIGHT hand; rhino horn; camouflage vest; army helmet.
PALETTE: hide grey #7E7A74, camo green #4E5A36, helmet olive #5E6A3A, accent strap brown #6E4C2E. These are the main colours plus one accent; no other strong colours.
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

## concepts/bebop-rocksteady-2-design-front-g2.png

Дата: 2026-10-13. Tool: `image_gen.imagegen`. Prompt key: `1a/design-front/g2`.

referenced_image_paths:

1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png` — SHA-256 `e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9`.

Точный текст переданного промпта:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Rocksteady from Teenage Mutant Ninja Turtles (Unmatched: Adventures TMNT): hulking mutant rhinoceros soldier with a horn, grey hide, camouflage vest and army helmet, heavy rifle in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: heavy rifle in the RIGHT hand; rhino horn; camouflage vest; army helmet.
PALETTE: hide grey #7E7A74, camo green #4E5A36, helmet olive #5E6A3A, accent strap brown #6E4C2E. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view: the pedestal top is visible and its front edge is curved -> keep the camera at zero elevation, hide the entire flat top and make the front edge a straight horizontal line.
- plain flat dark gray background: a soft vignette is visible -> use one uniform dark charcoal gray across the entire background, with no tonal variation.
```

## Проверка и ограничения первого запуска (история)

Создан только один вид design-front, поэтому согласованность нескольких проекций ещё не проверена. Между g1 и g2 сохраняются идентичность носорога-солдата, четыре якоря, палитра и собственная правая рука с винтовкой. g2 изменил детали шлема, винтовки, экипировки и положение подставки; верх подставки больше не виден, передняя кромка горизонтальная. Генератор добавил гранату, нарушающую запрет дополнительного оружия.

g1: код 0, WARN view.frame_top (2,141%); WARN не использован как причина ретрая. g2 и финальный прогон: код 0, 13 PASS, 0 WARN, 0 FAIL. Все шесть обязательных пунктов визуального чек-листа g2 пройдены; дополнительная проверка CORE/FORBIDDEN: no extra weapons провалена. Лимит 2/2 исчерпан, ограничение записано в verification.json и README.md. Кадрирование g2 измерено как x=49,632%, низ y=93,992% против заданных 50% и 93%; изображение не нормализовалось. Выходные изображения нигде не ретушировались и не пересохранялись.

## concepts/bebop-rocksteady-2-design-front-g3.png

Дата: 2026-10-13. Tool: `image_gen.imagegen`. Режим: `text-to-image`. Prompt key: `1a/design-front/g3`.

referenced_image_paths (в порядке вызова):

1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png` — SHA-256 `e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9`.

Инструменту передан абсолютный путь этого же файла. Размер параметром не передавался, transparent_background=false.

Точный текст переданного промпта:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Rocksteady from Teenage Mutant Ninja Turtles (Unmatched: Adventures TMNT): hulking mutant rhinoceros soldier with a horn, grey hide, camouflage vest and army helmet, heavy rifle in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: heavy rifle in the RIGHT hand; rhino horn; camouflage vest; army helmet.
PALETTE: hide grey #7E7A74, camo green #4E5A36, helmet olive #5E6A3A, accent strap brown #6E4C2E. These are the main colours plus one accent; no other strong colours.
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
- S (design-front): Remove the hand grenade from the figure's own left hip (viewer right), leaving the heavy rifle in the figure's RIGHT hand as the only weapon while preserving the existing pose, identity anchors, palette and miniature detail.
```


## concepts/bebop-rocksteady-2-design-front-g4.png

Дата: 2026-10-13. Tool: `image_gen.imagegen`. Режим: `text-to-image`. Prompt key: `1a/design-front/g4`.

referenced_image_paths (в порядке вызова):

1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png` — SHA-256 `e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9`.

Инструменту передан абсолютный путь этого же файла. Размер параметром не передавался, transparent_background=false.

Точный текст переданного промпта:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Rocksteady from Teenage Mutant Ninja Turtles (Unmatched: Adventures TMNT): hulking mutant rhinoceros soldier with a horn, grey hide, camouflage vest and army helmet, heavy rifle in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: heavy rifle in the RIGHT hand; rhino horn; camouflage vest; army helmet.
PALETTE: hide grey #7E7A74, camo green #4E5A36, helmet olive #5E6A3A, accent strap brown #6E4C2E. These are the main colours plus one accent; no other strong colours.
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
- S (design-front): Remove the hand grenade from the figure's own left hip (viewer right), leaving the heavy rifle in the figure's RIGHT hand as the only weapon while preserving the existing pose, identity anchors, palette and miniature detail.
- strict front orthographic view: the pedestal top surface is visible and its front edge is curved -> hide the entire top surface at zero camera elevation and make the pedestal front edge a straight horizontal line, seen exactly edge-on.
- plain flat dark gray background: a faint vignette and darker bottom area are visible -> use one uniform neutral dark charcoal gray across the entire background, with no gradient or vignette.
```

## Проверка и ограничения

Создан только вид design-front; согласованность нескольких проекций ещё не проверена. Между g3 и g4 сохранены идентичность носорога-солдата, четыре якоря, основные цвета и акцент, собственная правая рука с винтовкой; гранаты нет. Новая генерация не является ретушью предыдущей: g4 изменил форму винтовки, детали жилета, шлема и ремней, добавил очки на шлем и изменил подставку.

g3: код 0, 12 PASS, 1 WARN, 0 FAIL. Визуально видны верх подставки и слабая неравномерность фона; эти пункты, вместе с сохранённой коррекцией S, составили ровно три строки CORRECTION g4. WARN view.frame_top не являлся причиной повтора. g4 и финальный прогон без --out: код 0, 13 PASS, 0 WARN, 0 FAIL.

Выбран g4: шесть основных пунктов CHECKLIST пройдены, дополнительного оружия не видно, но два отдельных низких диска подставки не читаются. Дополнительный пункт CORE/PEDESTAL: two low stacked discs провален. Использовано 2/2 новых вызова, всего 4/4; ограничение сохранено в verification.json и README.md. Верх y=5,594%, низ y=92,196%, центр x=49,632%; оценочное отношение ширины подставки к высоте фигуры без неё около 0,65. Кадрирование и изображение не исправлялись. Все прежние точные промпты и история первого запуска сохранены.

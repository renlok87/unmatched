# ASSET-BUFFY-001 — концепт 1a

Дата: 2026-10-13.
Инструмент: image_gen (встроенный); режим generate; один вызов — одно изображение.
Вход 1 — только эталон качества исполнения; palette.json — текстовый вход, не изображение.
Размер в вызове не задавался; аспект 3:4 указан только в CORE.

## buffy-design-front-g1.png

prompt_key: `1a/design-front/g1`
Файл: `art/imagegen/concept-buffy-codex/concepts/buffy-design-front-g1.png`
referenced_image_paths в порядке вызова (пути нормализованы относительно корня репозитория):
1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`
CORRECTION: отсутствует.

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Buffy Summers from Buffy the Vampire Slayer (Unmatched: Buffy the Vampire Slayer): young blonde vampire slayer in a leather jacket, top and trousers, wooden stake in her RIGHT hand, confident fighting stance.
IDENTITY ANCHORS, each clearly visible: wooden stake in the RIGHT hand; blonde hair; leather jacket.
PALETTE: jacket black #1E1C1E, hair blonde #D9B86A, top red #9B2E26, accent stake wood #9B7448. These are the main colours plus one accent; no other strong colours.
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

## Проверка и ограничения

Сделан только один фронтальный дизайн. Других видов в этом этапе нет, межвидовая согласованность не проверялась.
CORE передан без изменений; корректирующего блока и второй генерации нет.
После ошибки копирования проверка была преждевременно вызвана на отсутствующей папке design. Это ошибка входа, а не FAIL изображения; дальнейшие генерации остановлены по договору задания.
Результат g1 затем скопирован побайтно и проверен отдельно; итоговая копия выбранного изображения проверена без --out.
Изображение не ретушировалось, не масштабировалось, не обрезалось, не перекрашивалось и не перекодировалось; копия инструмента оставлена на месте.
Автопроверки кандидата и выбранного файла: код 0, 12 PASS, 1 WARN, 0 FAIL. WARN view.frame_top: верх 2,555% вместо минимум 4%; WARN не служит основанием для ретрая.
Не закрыт пункт CHECKLIST о строгой ортопроекции: у подставки видна верхняя поверхность. Остальные пять пунктов пройдены визуально.

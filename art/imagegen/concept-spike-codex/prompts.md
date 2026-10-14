# Точные промпты ASSET-SPIKE-001, этап 1a

Дата: 2026-10-13
Инструмент: image_gen (встроенный), mode: generate.

Входные пути ниже нормализованы относительно корня репозитория; порядок совпадает с referenced_image_paths каждого вызова. Размер в пикселях не передавался.

## art/imagegen/concept-spike-codex/concepts/spike-design-front-g1.png

Дата: 2026-10-13T09:02:50+00:00

Инструмент: image_gen

prompt_key: 1a/design-front/g1

referenced_image_paths (в порядке вызова):

- art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Точный prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Spike from Buffy the Vampire Slayer (Unmatched: Buffy the Vampire Slayer): punk vampire with slicked-back platinum blond hair, long black leather duster coat, black t-shirt and jeans, red shirt underneath, smirking.
IDENTITY ANCHORS, each clearly visible: platinum blond slicked hair; long black leather duster; black t-shirt; red shirt underneath.
PALETTE: coat black #1C1A1C, hair platinum #E8E0C8, shirt red #9B2E26, accent jeans dark #2A2E3A. These are the main colours plus one accent; no other strong colours.
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

## art/imagegen/concept-spike-codex/concepts/spike-design-front-g2.png

Дата: 2026-10-13T09:04:58+00:00

Инструмент: image_gen

prompt_key: 1a/design-front/g2

referenced_image_paths (в порядке вызова):

- art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Точный prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Spike from Buffy the Vampire Slayer (Unmatched: Buffy the Vampire Slayer): punk vampire with slicked-back platinum blond hair, long black leather duster coat, black t-shirt and jeans, red shirt underneath, smirking.
IDENTITY ANCHORS, each clearly visible: platinum blond slicked hair; long black leather duster; black t-shirt; red shirt underneath.
PALETTE: coat black #1C1A1C, hair platinum #E8E0C8, shirt red #9B2E26, accent jeans dark #2A2E3A. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: the pedestal top surface is visible and its upper front edge curves -> show the pedestal exactly edge-on, with no visible top surface and a straight horizontal front edge, using a strictly level orthographic camera.
```

## Проверка и ограничения

Создан только один вид design-front. Согласованность front/side/back здесь не оценивалась. Между двумя фронтальными кандидатами сохранены персонаж, все четыре якоря, основные цвета и акцент, пустые руки и двухдисковая каменная подставка.

Изменение, запрошенное в g2: вместо видимой верхней плоскости и дугообразной кромки подставки — строгое положение ребром и горизонтальные кромки. Генератор также изменил детали лица, складки и ширину силуэта плаща; это вариации генерации, а не ручная правка. Отступ сверху изменился с 1,312% до 2,762%, но по-прежнему меньше 4%.

Оба кандидата и финальный выбранный g2 получили код 0: PASS 12, WARN 1, FAIL 0. Единственное предупреждение — view.frame_top. У g1 визуально провален пункт ортографии подставки; g2 проходит все шесть пунктов CHECKLIST. Исходные PNG скопированы побайтно, оригиналы image_gen сохранены. Все ограничения отражены в verification.json.

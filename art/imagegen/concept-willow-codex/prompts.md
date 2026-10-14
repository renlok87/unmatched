# ASSET-WILLOW-001 concept 1a: exact generation prompts

Date: 2026-10-13
Tool: image_gen.imagegen (built-in); mode: generate

## 1a/design-front/g1

File: art/imagegen/concept-willow-codex/concepts/willow-design-front-g1.png

referenced_image_paths (call order; repository-relative):

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png (sha256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9)

Exact prompt:

~~~text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Willow Rosenberg from Buffy the Vampire Slayer (Unmatched: Buffy the Vampire Slayer): young witch with long red hair, colourful layered cardigan and long skirt, one hand raised casting a glowing spell.
IDENTITY ANCHORS, each clearly visible: long red hair; colourful layered cardigan; long skirt; glowing spell in a raised hand.
PALETTE: hair red #A8321E, cardigan green #5E8A4A, skirt purple #6A4A8A, accent spell glow #B8E0FF. These are the main colours plus one accent; no other strong colours.
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
~~~

## 1a/design-front/g2

File: art/imagegen/concept-willow-codex/concepts/willow-design-front-g2.png

referenced_image_paths (call order; repository-relative):

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png (sha256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9)

Exact prompt:

~~~text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Willow Rosenberg from Buffy the Vampire Slayer (Unmatched: Buffy the Vampire Slayer): young witch with long red hair, colourful layered cardigan and long skirt, one hand raised casting a glowing spell.
IDENTITY ANCHORS, each clearly visible: long red hair; colourful layered cardigan; long skirt; glowing spell in a raised hand.
PALETTE: hair red #A8321E, cardigan green #5E8A4A, skirt purple #6A4A8A, accent spell glow #B8E0FF. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: the pedestal top surface is visible and its front edge curves in perspective -> render strict level front orthographic projection, hide the pedestal top completely, and make its front edge a straight horizontal line.
~~~

## Проверка и ограничения

Выполнен только design-front; сравнение front/side/back неприменимо к этапу 1a.

Между g1 и g2 сохранены длинные рыжие волосы, зелёный многослойный кардиган, длинная фиолетовая юбка, голубое свечение поднятой кисти и тёмная двухъярусная подставка. В g2 скрыт верх подставки и горизонтальны передние кромки. Изменились лицо, орнаменты, украшения, складки юбки и рисунок заклинания; требования к этим деталям не добавлялись.

Выбран g2. Все шесть пунктов визуального CHECKLIST пройдены; финальный скрипт: код 0, 11 PASS / 2 WARN / 0 FAIL. Допустимые WARN: view.frame_top = 3.315% и view.single_component (дополнительная компонента 1.907%). Низ подставки 96.133% вместо 93%. Фон содержит мелкую фактуру и небольшую пиксельную вариацию без заметного градиента или виньетки. Изображения не ретушировались, не масштабировались, не обрезались и не перекодировались.


## Корректирующий прогон fix1 — 2026-10-13

Date: 2026-10-13
Tool: image_gen.imagegen (built-in); mode: generate

CORE сохранён дословно; в обоих вызовах после него переданы принятые строки CORRECTION S/P. В g4 добавлена третья строка только для непройденного пункта ортопроекции. Единственный визуальный вход — исходный QUALITY_REFERENCE; отклонённый дизайн не передавался.

### 1a/design-front/g3

Date: 2026-10-13T09:43:47+00:00
Tool: image_gen.imagegen

File: art/imagegen/concept-willow-codex/concepts/willow-design-front-g3.png

referenced_image_paths (call order; repository-relative):

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png (sha256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9)

Exact prompt:

~~~text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Willow Rosenberg from Buffy the Vampire Slayer (Unmatched: Buffy the Vampire Slayer): young witch with long red hair, colourful layered cardigan and long skirt, one hand raised casting a glowing spell.
IDENTITY ANCHORS, each clearly visible: long red hair; colourful layered cardigan; long skirt; glowing spell in a raised hand.
PALETTE: hair red #A8321E, cardigan green #5E8A4A, skirt purple #6A4A8A, accent spell glow #B8E0FF. These are the main colours plus one accent; no other strong colours.
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
- S (willow-front.png): Make the figure recognisably Willow Rosenberg from Buffy the Vampire Slayer through her distinctive youthful facial features and contemporary bohemian cardigan-and-skirt styling, replacing the ornate fantasy-robe appearance while preserving all four identity anchors and the separated casting pose.
- P (willow-front.png): Match the palette with deeper red hair (#A8321E), a greener cardigan (#5E8A4A), a more violet skirt (#6A4A8A), and pale-blue spell highlights (#B8E0FF), retaining natural material shading.
~~~

### 1a/design-front/g4

Date: 2026-10-13T09:45:12+00:00
Tool: image_gen.imagegen

File: art/imagegen/concept-willow-codex/concepts/willow-design-front-g4.png

referenced_image_paths (call order; repository-relative):

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png (sha256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9)

Exact prompt:

~~~text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Willow Rosenberg from Buffy the Vampire Slayer (Unmatched: Buffy the Vampire Slayer): young witch with long red hair, colourful layered cardigan and long skirt, one hand raised casting a glowing spell.
IDENTITY ANCHORS, each clearly visible: long red hair; colourful layered cardigan; long skirt; glowing spell in a raised hand.
PALETTE: hair red #A8321E, cardigan green #5E8A4A, skirt purple #6A4A8A, accent spell glow #B8E0FF. These are the main colours plus one accent; no other strong colours.
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
- S (willow-front.png): Make the figure recognisably Willow Rosenberg from Buffy the Vampire Slayer through her distinctive youthful facial features and contemporary bohemian cardigan-and-skirt styling, replacing the ornate fantasy-robe appearance while preserving all four identity anchors and the separated casting pose.
- P (willow-front.png): Match the palette with deeper red hair (#A8321E), a greener cardigan (#5E8A4A), a more violet skirt (#6A4A8A), and pale-blue spell highlights (#B8E0FF), retaining natural material shading.
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: a narrow top surface of the pedestal is visible behind and beside the feet -> show both stacked discs exactly edge-on with zero visible top surface and straight horizontal front edges; keep the figure strictly frontal.
~~~

## Проверка и ограничения

В этом прогоне выполнен только design-front этапа 1a: согласованность между front/side/back не оценивается, дополнительные виды не созданы. Между g3 и g4 сохранены четыре якоря, фронтальная стойка с разделёнными руками, основные цвета и голубое свечение. Изменились черты лица, вязка и вышивка кардигана, длина волос, складки юбки, обувь и форма свечения; g4 исправил видимость верха подставки. Ни одно изображение не редактировалось.

g3: код 0, 12 PASS / 1 WARN / 0 FAIL; визуально провален пункт строгой ортопроекции, виден верх подставки. WARN view.frame_top (3,315%) не стал причиной повтора. g4 и финальный выбранный файл: код 0, 13 PASS / 0 WARN / 0 FAIL; все шесть пунктов CHECKLIST пройдены.

Ограничения g4: низ маски подставки y95,235% вместо y93%; центр x49,862% вместо ровно x50%. Небольшая фактура и пиксельная вариация фона сохраняются. HEX — целевые цвета в промпте; при естественном освещении волосы имеют тёплые блики, кардиган местами выглядит оливковым. Точное совпадение каждого пикселя со свотчем не заявляется. Эти ограничения записаны в verification.json; художественную оценку выполняет приёмщик.

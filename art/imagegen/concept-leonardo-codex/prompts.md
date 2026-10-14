# Leonardo: exact image_gen prompts

Date: 2026-10-13
Tool: image_gen.imagegen
Stage: 1a

## art/imagegen/concept-leonardo-codex/concepts/leonardo-design-front-g1.png

Date: 2026-10-13 07:27:59 UTC
Tool: image_gen.imagegen
Prompt key: 1a/design-front/g1

referenced_image_paths (ordered, repository-relative):

```json
[
  "art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
]
```

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Leonardo from Teenage Mutant Ninja Turtles (Unmatched: Adventures TMNT): humanoid ninja turtle with a green skin, brown shell, blue eye mask, belt and knee pads, two katanas crossed in both hands.
IDENTITY ANCHORS, each clearly visible: two katanas, one in each hand; blue eye mask with tails; brown shell on the back; belt and knee pads.
PALETTE: skin green #4E8A3A, shell brown #6E5236, mask blue #2456B3, accent blade steel #C9CED3. These are the main colours plus one accent; no other strong colours.
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

## art/imagegen/concept-leonardo-codex/concepts/leonardo-design-front-g2.png

Date: 2026-10-13 07:31:01 UTC
Tool: image_gen.imagegen
Prompt key: 1a/design-front/g2

referenced_image_paths (ordered, repository-relative):

```json
[
  "art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
]
```

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Leonardo from Teenage Mutant Ninja Turtles (Unmatched: Adventures TMNT): humanoid ninja turtle with a green skin, brown shell, blue eye mask, belt and knee pads, two katanas crossed in both hands.
IDENTITY ANCHORS, each clearly visible: two katanas, one in each hand; blue eye mask with tails; brown shell on the back; belt and knee pads.
PALETTE: skin green #4E8A3A, shell brown #6E5236, mask blue #2456B3, accent blade steel #C9CED3. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: a narrow top surface of the pedestal is visible -> show both pedestal discs exactly edge-on, with straight horizontal front edges and no visible top surface.
```

## Проверка и ограничения

Это один вид design-front этапа 1a; согласованность разных видов не проверялась. Между g1 и g2 совпадают персонаж, фронтальная стойка, зелёная кожа, коричневый панцирь, синяя маска, пояс, наколенники и две катаны.

CORRECTION у g2 исправляет только видимую верхнюю поверхность подставки. Передние края стали горизонтальными, верх не виден. Генератор также перенёс хвосты маски на другую сторону изображения, добавил обмотки стоп и синюю ткань с эмблемной пряжкой; этих изменений коррекция не запрашивала.

Выбран g2. Оба кандидата и финальный запуск: код 0, 13 PASS, 0 WARN, 0 FAIL. Ручной CHECKLIST: запрет оружия и запрет логотипов не закрыты. CORE одновременно требует катаны и запрещает удерживаемые предметы; он оставлен неизменным. Клинки не скрещены, подставка шире заданной пропорции. Лимит 2/2 исчерпан, статус «предложено».

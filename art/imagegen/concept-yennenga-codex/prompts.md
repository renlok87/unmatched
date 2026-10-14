# Exact generation prompts ? ASSET-YENNENGA-001, stage 1a

Date: 2026-10-13
Tool: image_gen (built-in), mode: generate

Reference paths below are repository-relative, in the exact call order; the tool resolved them to the same local files.

## yennenga-design-front-g1.png

Date: 2026-10-13T08:30:44+00:00
Tool: image_gen

referenced_image_paths:
- `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png` ? sha256 `e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9`

prompt_key: `1a/design-front/g1`

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Princess Yennenga of the Mossi people of Burkina Faso (Unmatched: Battle of Legends Volume Two): proud warrior princess in a patterned wrap and leather armour, beaded jewellery, short spear in her RIGHT hand, small round shield on her LEFT arm.
IDENTITY ANCHORS, each clearly visible: short spear in the RIGHT hand; small round shield on the LEFT arm; patterned wrap; beaded jewellery.
PALETTE: wrap ochre #C88A2E, leather brown #6E4C2E, skin dark #5A3B2A, accent bead red #B2342C. These are the main colours plus one accent; no other strong colours.
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

## yennenga-design-front-g2.png

Date: 2026-10-13T08:32:35+00:00
Tool: image_gen

referenced_image_paths:
- `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png` ? sha256 `e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9`

prompt_key: `1a/design-front/g2`

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Princess Yennenga of the Mossi people of Burkina Faso (Unmatched: Battle of Legends Volume Two): proud warrior princess in a patterned wrap and leather armour, beaded jewellery, short spear in her RIGHT hand, small round shield on her LEFT arm.
IDENTITY ANCHORS, each clearly visible: short spear in the RIGHT hand; small round shield on the LEFT arm; patterned wrap; beaded jewellery.
PALETTE: wrap ochre #C88A2E, leather brown #6E4C2E, skin dark #5A3B2A, accent bead red #B2342C. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: the pedestal's top surface is visible and its front edge curves -> eliminate all visible top surface and draw the pedestal exactly edge-on with a straight horizontal front edge.
```

## Проверка и ограничения

Создан один вид design-front, поэтому согласованность front/side/back здесь не заявляется. Между g1 и g2 совпадают персонаж и четыре якоря идентичности, собственная правая рука с копьём слева для зрителя, левый щит, основная палитра, одна фигура и одна двухъярусная подставка.

Запрошенное изменение g2 — устранить видимую верхнюю плоскость подставки и сделать горизонтальную переднюю кромку. Генератор также изменил причёску, раскладку бус, рисунок и складки ткани, постановку рук и длину копья. CORE остался дословно тем же; добавлена одна строка CORRECTION.

g1: код автопроверки 0; визуальный пункт strict front orthographic провален. g2 выбран: код итоговой автопроверки 0, все шесть пунктов CHECKLIST выполнены. WARN view.frame_top сохранён: g1 2,624 %, g2 3,246 % при целевых ≥ 4 %. Низ g2 — y95,718 % вместо y93 %; центр подставки x50,000 %. Эти отклонения не исправлялись обработкой изображения. Лимит 2/2 использован, проваленных пунктов CHECKLIST у выбранного файла нет.

Оригиналы и копии сохранены побайтово. Входные файлы неизменны. Статус дизайна — «предложено», внешняя приёмка ещё не проведена.

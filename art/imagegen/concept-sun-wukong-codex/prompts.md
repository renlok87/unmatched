# Sun Wukong concept 1a - prompts

Date: 2026-10-13
Tool: image_gen; mode: generate

Reference paths below are repository-relative, in actual call order; the tool received their resolved absolute paths.

## 1a/design-front/g1

File: art/imagegen/concept-sun-wukong-codex/concepts/sun-wukong-design-front-g1.png

referenced_image_paths (in order):

- art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Sun Wukong, the Monkey King: agile monkey-faced warrior with golden fur, golden headband circlet, red-and-gold armour vest, cloud-patterned trousers, long red golden-capped staff held in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: golden staff with red shaft in the figure's own RIGHT hand; golden circlet on the head; monkey tail; red-and-gold armour.
PALETTE: golden fur #C99A4A, imperial red #B32A24, armour gold #D8B04A, accent cloud blue #5A8FC8. These are the main colours plus one accent; no other strong colours.
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

## 1a/design-front/g2

File: art/imagegen/concept-sun-wukong-codex/concepts/sun-wukong-design-front-g2.png

referenced_image_paths (in order):

- art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Sun Wukong, the Monkey King: agile monkey-faced warrior with golden fur, golden headband circlet, red-and-gold armour vest, cloud-patterned trousers, long red golden-capped staff held in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: golden staff with red shaft in the figure's own RIGHT hand; golden circlet on the head; monkey tail; red-and-gold armour.
PALETTE: golden fur #C99A4A, imperial red #B32A24, armour gold #D8B04A, accent cloud blue #5A8FC8. These are the main colours plus one accent; no other strong colours.
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
- CHECKLIST strict front orthographic view: pedestal top surface is visible and its front edge curves -> make the camera exactly level, show both pedestal discs edge-on with no visible top surface and a straight horizontal front edge.
- CHECKLIST plain flat dark gray background: background has a gradient/vignette -> use one uniform flat neutral dark charcoal gray everywhere, without gradient, vignette, floor or background shadow.
```

## Проверка и ограничения

Создан только один вид design-front; сравнение нескольких ракурсов на этапе 1a неприменимо. В обеих попытках совпадают персонаж, собственная правая рука с красно-золотым посохом, золотой обруч, хвост, красно-золотой доспех и синий облачный акцент.

CORRECTION g2 касается только камеры/подставки и ровности фона. Во второй генерации основание стало показано ребром и исчез длинный развевающийся шарф; орнамент доспеха, складки, подвески и распределение синего на брюках изменились как вариативность генератора. CORE не менялся. Гарантия идентичности мелкой геометрии между независимыми генерациями не заявляется.

g1: скрипт 0, WARN view.frame_top; визуально провалены ракурс подставки и ровность фона. g2: скрипт и финальный запуск 0, 13 PASS без WARN/FAIL; все шесть пунктов CHECKLIST пройдены. Тёмный фон g2 имеет лишь слабый шум 1–2 уровня RGB. Все изображения сохранены побайтно, без изменения пикселей. Пакет имеет статус «предложено» и передаётся внешнему приёмщику.


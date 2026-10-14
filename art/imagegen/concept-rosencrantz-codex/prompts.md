# ASSET-ROSENCRANTZ-001: exact generation prompts

## art/imagegen/concept-rosencrantz-codex/concepts/rosencrantz-design-front-g1.png

Date: 2026-10-13T04:45:20.144Z

Tool: image_gen; mode: generate; prompt_key: 1a/design-front/g1

referenced_image_paths (repository-relative, in call order):

```json
[
  "art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
]
```

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: A Danish courtier: young nobleman in a dark green doublet with puffed sleeves and a short cape, feathered cap, dagger in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: dagger in the figure's own RIGHT hand; feathered cap; puffed sleeves; short cape.
PALETTE: doublet green #2F5A45, cape black #1F1F24, ruff white #E9E4D8, accent feather gold #D4AE45. These are the main colours plus one accent; no other strong colours.
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

## art/imagegen/concept-rosencrantz-codex/concepts/rosencrantz-design-front-g2.png

Date: 2026-10-13T04:46:28.480Z

Tool: image_gen; mode: generate; prompt_key: 1a/design-front/g2

referenced_image_paths (repository-relative, in call order):

```json
[
  "art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
]
```

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: A Danish courtier: young nobleman in a dark green doublet with puffed sleeves and a short cape, feathered cap, dagger in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: dagger in the figure's own RIGHT hand; feathered cap; puffed sleeves; short cape.
PALETTE: doublet green #2F5A45, cape black #1F1F24, ruff white #E9E4D8, accent feather gold #D4AE45. These are the main colours plus one accent; no other strong colours.
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
- CHECKLIST item 2 (strict front orthographic view; pedestal exactly edge-on): the pedestal top surface is visible and its front edge curves -> zero camera elevation, no visible top surface, a straight horizontal front edge.
- CHECKLIST item 5 (every identity anchor is visible: dagger, feathered cap, puffed sleeves, short cape): the cape hangs to the knees and a second sheathed weapon is visible -> a clearly short cape ending at the waist or upper hips, and only the single dagger held in the RIGHT hand.
- CHECKLIST item 4 (RIGHT-hand dagger; both arms clearly apart from the torso, not a T-pose or A-pose): the cape fills the gaps between arms and torso -> visible dark-background gaps between each arm and the body, keeping elbows slightly bent and the RIGHT-hand dagger on the viewer's LEFT.
```

## Проверка и ограничения

Создан только вид design-front этапа 1a, сравнения front/side/back нет. В g1 и g2 сохранены молодой придворный, зелёный дублет, белый воротник, чёрный плащ, золотое перо, кинжал в собственной правой руке и одна подставка из двух дисков. В g2 укорочен плащ, убрано второе оружие, открыты просветы у рук и выпрямлен профиль подставки; сторона пера и мелкие орнаменты изменились.

Оба кандидата и финальная копия g2 получили код 0: 12 PASS, 1 WARN, 0 FAIL. Визуальные пункты 2, 4 и 5 g1 не выполнены; у выбранного g2 все шесть пунктов CHECKLIST выполнены. Остался допустимый WARN view.frame_top: 3,522% вместо минимум 4%; низ подставки 94,751% вместо 93%, центр 49,862% вместо 50%. Ограничения раскрыты в verification.json, изображение после генерации не правилось.

Использованы 2 из 2 генераций. Вторая получила неизменный CORE и три строки CORRECTION; WARN не был причиной повтора. Изображения инструмента и копии совпадают побайтно. Входы неизменны. Статус: предложено.

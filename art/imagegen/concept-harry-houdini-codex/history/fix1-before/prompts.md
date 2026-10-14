# Промпты концепта Гарри Гудини

Дата: 2026-10-13. Инструмент: `image_gen`, режим `generate`.

## harry-houdini-design-front-g1.png

prompt_key: `1a/design-front/g1`.

referenced_image_paths, в порядке вызова (пути от корня репозитория; инструмент получил абсолютные разрешения):

1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Harry Houdini, the escape artist: compact muscular man with curly dark hair, white shirt with rolled sleeves, black waistcoat and trousers, heavy iron chains and a padlock draped over his shoulders and wrapped around one forearm, hands open.
IDENTITY ANCHORS, each clearly visible: iron chains over the shoulders; padlock hanging at the chest; rolled white sleeves; black waistcoat.
PALETTE: stage black #1C1C20, shirt white #E6E2D8, iron #5C6064, accent brass padlock #C2963E. These are the main colours plus one accent; no other strong colours.
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

## harry-houdini-design-front-g2.png

prompt_key: `1a/design-front/g2`.

referenced_image_paths, в порядке вызова (пути от корня репозитория; инструмент получил абсолютные разрешения):

1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Harry Houdini, the escape artist: compact muscular man with curly dark hair, white shirt with rolled sleeves, black waistcoat and trousers, heavy iron chains and a padlock draped over his shoulders and wrapped around one forearm, hands open.
IDENTITY ANCHORS, each clearly visible: iron chains over the shoulders; padlock hanging at the chest; rolled white sleeves; black waistcoat.
PALETTE: stage black #1C1C20, shirt white #E6E2D8, iron #5C6064, accent brass padlock #C2963E. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: pedestal top and curved upper front edge are visible -> eliminate camera elevation and perspective; show both discs only as edge-on side faces with straight horizontal upper edges and zero visible top surface.
- the whole subject and pedestal visible, nothing cropped; plain flat dark gray background: background has tonal variation -> use a perfectly uniform solid neutral dark gray background across the entire image, without any gradient or vignette.
```

## Проверка и ограничения

Создан только front этапа 1a; согласованность разных видов не проверялась. Между g1 и g2 сохранены костюм, четыре якоря, палитра и открытые ладони. В g2 подставка видна с ребра; изменились форма замка и сторона обвитого цепью предплечья. Сторона CORE не задана, для продолжения выбран g2. Слабая неоднородность фона осталась. Все три прогона скрипта: 0 FAIL; WARN не служили причиной ретрая. Изображения не изменялись.

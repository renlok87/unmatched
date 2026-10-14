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

## Корректирующий запуск fix1

Дата: 2026-10-13. Инструмент: `image_gen`, режим `generate`. Только design-front; до запуска использовано 2/4, в fix1 использовано 2/2.

## harry-houdini-design-front-g3.png

Дата: 2026-10-13. Инструмент: `image_gen`, режим `generate`.

prompt_key: `1a/design-front/g3`.

referenced_image_paths, в порядке вызова (пути от корня; инструмент получил абсолютный путь):

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
- S design-front: Replace the symmetric A-pose with a natural asymmetric escape-artist stance: visibly bend the chain-wrapped arm and raise its open palm to waist height, keep the other open hand lower beside the hip with a distinct elbow bend, and preserve clear gaps between both arms and the torso.
```

## harry-houdini-design-front-g4.png

Дата: 2026-10-13. Инструмент: `image_gen`, режим `generate`.

prompt_key: `1a/design-front/g4`.

referenced_image_paths, в порядке вызова (пути от корня; инструмент получил абсолютный путь):

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
- S design-front: The lower unwrapped arm is nearly straight and the raised chain-wrapped palm is above the waist -> give the lower arm a distinct visible elbow bend with its empty open hand beside the hip, visibly bend the chain-wrapped arm with its empty open palm at waist height, and preserve clear gaps between both arms and the torso.
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: the pedestal top is visible and its upper front edge curves -> show both discs exactly edge-on with straight horizontal upper edges and zero visible top surface.
- the whole subject and pedestal visible, nothing cropped; plain flat dark gray background: background is mottled and lightens near the pedestal -> use a perfectly uniform solid neutral dark gray background across the entire image, without any gradient, vignette, floor or cast shadow.
```

## Проверка и ограничения

Создан только design-front этапа 1a; согласованность разных видов не проверялась. CORE g1, g3 и g4 совпадает дословно. g3 получил исходную CORRECTION пользователя без изменений; g4 получил три строки исправлений по g3. Во всех новых кандидатах сохранены костюм, палитра и четыре якоря. Между g3 и g4 изменились поза рук и ракурс подставки: g3 асимметричен, g4 вернул A-позу, хотя показал подставку с ребра. Выбран g3. Видимый верх подставки, слабая неоднородность фона, поднятая ладонь выше талии и слабый сгиб нижнего локтя остаются открытыми. Три прогона fix1: код 0, 0 FAIL; WARN не вызывал ретрай. Все изображения сохранены побайтно без обработки; все четыре генерации вида использованы. Приёмка не проводилась.

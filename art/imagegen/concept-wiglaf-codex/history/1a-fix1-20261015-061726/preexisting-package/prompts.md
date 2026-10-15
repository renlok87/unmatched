# Wiglaf — промпты 1c (2026-10-15)

Tool: `image_gen.imagegen`; mode: edit / style-transfer. Один вызов — один вид. `transparent_background=false`; размер не задавался. CORE извлечён только по заголовкам в начале строки CORE-FRONT, CORE-SIDE и CORE-BACK; в повторе back к неизменному CORE добавлен один CORRECTION. Порядок входов ниже соответствует вызовам, при передаче инструменту пути раскрывались в абсолютные пути текущего checkout.

## art/imagegen/concept-wiglaf-codex/concepts/wiglaf-front-g1.png

Date: 2026-10-15T05:51:09.081275+00:00
Tool: image_gen.imagegen
Prompt key: 1c/front/g1
Selected: true

referenced_image_paths (in call order):

- art/pipeline-candidates/ASSET-WIGLAF-001/20261015-draft-tripo/orthos/ortho_front.png (sha256 4671a2742bbcd7821739e0d105d707ef4fecdec1ea21b764bca151d5f223ab9c)
- art/imagegen/concept-wiglaf-codex/design/wiglaf-front.png (sha256 189ddfea5962e086cfa11dbc6545212cacfa5701d14d08445782969f1a74bc42)

Exact prompt:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, FRONT
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Wiglaf, Beowulf's young kinsman: slim young warrior in a leather jerkin and green cloak, conical iron helmet, axe in his RIGHT hand, round shield painted with a simple boar on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: hand axe in the figure's own RIGHT hand; round shield with a boar on the LEFT arm; conical helmet.
PALETTE: leather #7A5634, moss green #4E6B3A, iron #5E6266, accent boar red #9A3428. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: FRONT: strict front orthographic view, the figure faces the camera, no three-quarter turn.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x16.0%-84.0%, pedestal top y84.3%, pedestal bottom y94.0%, highest point
y5.8%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

Original path: C:\Users\ren\.codex\generated_images\01a13e1b-68a3-7b60-8f05-6c8cac13c133\exec-96d15625-080d-446b-94a6-f04a3dd6c1fd.png

## art/imagegen/concept-wiglaf-codex/concepts/wiglaf-side-g1.png

Date: 2026-10-15T05:52:20.723557+00:00
Tool: image_gen.imagegen
Prompt key: 1c/side/g1
Selected: true

referenced_image_paths (in call order):

- art/pipeline-candidates/ASSET-WIGLAF-001/20261015-draft-tripo/orthos/ortho_right.png (sha256 d4305efee66481fe149cb72c8ca3e90a9bb9b4262c6b3a1318b7f880d652868f)
- art/imagegen/concept-wiglaf-codex/design/wiglaf-front.png (sha256 189ddfea5962e086cfa11dbc6545212cacfa5701d14d08445782969f1a74bc42)

Exact prompt:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, RIGHT SIDE
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Wiglaf, Beowulf's young kinsman: slim young warrior in a leather jerkin and green cloak, conical iron helmet, axe in his RIGHT hand, round shield painted with a simple boar on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: hand axe in the figure's own RIGHT hand; round shield with a boar on the LEFT arm; conical helmet.
PALETTE: leather #7A5634, moss green #4E6B3A, iron #5E6266, accent boar red #9A3428. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: RIGHT SIDE: strict profile, the figure's OWN right side faces the camera, its face toward the right edge of the image, no three-quarter view.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x16.4%-83.6%, pedestal top y84.3%, pedestal bottom y94.0%, highest point
y5.8%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

Original path: C:\Users\ren\.codex\generated_images\01a13e1b-68a3-7b60-8f05-6c8cac13c133\exec-7c937c8c-d60b-4ac5-a18c-4e9433f626b0.png

## art/imagegen/concept-wiglaf-codex/concepts/wiglaf-back-g1.png

Date: 2026-10-15T05:53:28.721414+00:00
Tool: image_gen.imagegen
Prompt key: 1c/back/g1
Selected: false

referenced_image_paths (in call order):

- art/pipeline-candidates/ASSET-WIGLAF-001/20261015-draft-tripo/orthos/ortho_back.png (sha256 74718a7f915ff889393e4a8b46196f9166a5fd82af796a589711ba03a664cc96)
- art/imagegen/concept-wiglaf-codex/design/wiglaf-front.png (sha256 189ddfea5962e086cfa11dbc6545212cacfa5701d14d08445782969f1a74bc42)
- art/imagegen/concept-wiglaf-codex/wiglaf-side.png (sha256 4b6f5b59b504d36051e4d269ef0feba18bbaea27c7a1abd40f35139ae40ee2c5)

Exact prompt:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, BACK
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
Image 3 is the finished side view of the SAME miniature, for continuity of colours and details only.
SUBJECT: Wiglaf, Beowulf's young kinsman: slim young warrior in a leather jerkin and green cloak, conical iron helmet, axe in his RIGHT hand, round shield painted with a simple boar on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: hand axe in the figure's own RIGHT hand; round shield with a boar on the LEFT arm; conical helmet.
PALETTE: leather #7A5634, moss green #4E6B3A, iron #5E6266, accent boar red #9A3428. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: BACK: camera directly behind, no face visible, no three-quarter view. The weapon in the figure's own RIGHT hand appears on the viewer's RIGHT.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x16.0%-84.0%, pedestal top y84.3%, pedestal bottom y94.0%, highest point
y5.8%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

Original path: C:\Users\ren\.codex\generated_images\01a13e1b-68a3-7b60-8f05-6c8cac13c133\exec-67995954-f8a6-44eb-9079-a62bb7f1dc94.png

## art/imagegen/concept-wiglaf-codex/concepts/wiglaf-back-g2.png

Date: 2026-10-15T05:54:39.507015+00:00
Tool: image_gen.imagegen
Prompt key: 1c/back/g2
Selected: true

referenced_image_paths (in call order):

- art/pipeline-candidates/ASSET-WIGLAF-001/20261015-draft-tripo/orthos/ortho_back.png (sha256 74718a7f915ff889393e4a8b46196f9166a5fd82af796a589711ba03a664cc96)
- art/imagegen/concept-wiglaf-codex/design/wiglaf-front.png (sha256 189ddfea5962e086cfa11dbc6545212cacfa5701d14d08445782969f1a74bc42)
- art/imagegen/concept-wiglaf-codex/wiglaf-side.png (sha256 4b6f5b59b504d36051e4d269ef0feba18bbaea27c7a1abd40f35139ae40ee2c5)

Exact prompt:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, BACK
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
Image 3 is the finished side view of the SAME miniature, for continuity of colours and details only.
SUBJECT: Wiglaf, Beowulf's young kinsman: slim young warrior in a leather jerkin and green cloak, conical iron helmet, axe in his RIGHT hand, round shield painted with a simple boar on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: hand axe in the figure's own RIGHT hand; round shield with a boar on the LEFT arm; conical helmet.
PALETTE: leather #7A5634, moss green #4E6B3A, iron #5E6266, accent boar red #9A3428. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: BACK: camera directly behind, no face visible, no three-quarter view. The weapon in the figure's own RIGHT hand appears on the viewer's RIGHT.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x16.0%-84.0%, pedestal top y84.3%, pedestal bottom y94.0%, highest point
y5.8%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
CORRECTION (fix only this; everything above still applies):
- identity, costume, colours and materials (shield interior): back view wrongly shows the red boar exterior and outer boss underneath the hand -> match image 1: show only the plain unpainted wooden INTERIOR of the shield with its inner hand grip, no boar emblem, no red painted face, no exterior boss; keep the shield silhouette and hand position unchanged.
```

Original path: C:\Users\ren\.codex\generated_images\01a13e1b-68a3-7b60-8f05-6c8cac13c133\exec-153eba8d-4297-4e2f-8c8d-b419466d996d.png

## Проверка и ограничения

Front g1 и right side g1 выбраны с первого вызова; back g2 выбран после исправления ошибочной наружной росписи на внутренней поверхности щита в g1. Оба back использовали выбранный готовый side как третий вход. Согласованы молодой воин, конический железный шлем, зелёный плащ, коричневая кожа, топор в собственной правой руке и щит на левой. Кабан остаётся на лицевой стороне щита; сзади показаны дерево и внутренний хват.

Каждый кандидат: exit 0, 12 PASS, 0 WARN, 0 FAIL. Итог выбранных front/side/back с палитрой и листом: exit 0, 33 PASS, 0 WARN, 0 FAIL. Выбранные виды и лист просмотрены; failed пунктов CHECKLIST нет. Ошибка back g1 выявлена глазами, а не скриптом. Использовано 1/2, 1/2, 2/2 вызова соответственно.

Фактура, волосы, складки и мелкий орнамент немного различаются между видами; абсолютное геометрическое совпадение не заявляется. Верх side на 4,8% вместо 5,8% проходит заданные проверки; подгонка не выполнялась. Все PNG — 1086×1448, сохранены побайтово, без ретуши, обрезки, ресайза или пересохранения. Это 2D-концепты со статусом «предложено»; 3D и пригодность для игры не оценивались. Шесть входов неизменны. Все прежние записи промптов сохранены ниже.

---

# Wiglaf: exact image_gen prompts

Date: 2026-10-13
Tool: image_gen.imagegen
Mode: generate (craftsmanship reference only)

referenced_image_paths ниже нормализованы относительно корня репозитория; при вызове инструмента они разрешены в абсолютные пути. Порядок входов сохранён. palette.json не передавался как изображение. Размер не задавался; transparent_background=false.\n\n## art/imagegen/concept-wiglaf-codex/concepts/wiglaf-design-front-g1.png

Date: 2026-10-13T03:14:36.664296+00:00
Tool: image_gen.imagegen
Prompt key: 1a/design-front/g1

referenced_image_paths (in call order):

- art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png (sha256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9)

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Wiglaf, Beowulf's young kinsman: slim young warrior in a leather jerkin and green cloak, conical iron helmet, axe in his RIGHT hand, round shield painted with a simple boar on his LEFT arm.
IDENTITY ANCHORS, each clearly visible: hand axe in the figure's own RIGHT hand; round shield with a boar on the LEFT arm; conical helmet.
PALETTE: leather #7A5634, moss green #4E6B3A, iron #5E6266, accent boar red #9A3428. These are the main colours plus one accent; no other strong colours.
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

Original path: C:\Users\ren\.codex\generated_images\01a1333f-a46b-7c12-99a7-1b9a2445b577\exec-4fae5a22-4546-4e10-801f-99781b0ae90b.png

## art/imagegen/concept-wiglaf-codex/concepts/wiglaf-design-front-g2.png

Date: 2026-10-13T03:15:42.594644+00:00
Tool: image_gen.imagegen
Prompt key: 1a/design-front/g2

referenced_image_paths (in call order):

- art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png (sha256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9)

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Wiglaf, Beowulf's young kinsman: slim young warrior in a leather jerkin and green cloak, conical iron helmet, axe in his RIGHT hand, round shield painted with a simple boar on his LEFT arm.
IDENTITY ANCHORS, each clearly visible: hand axe in the figure's own RIGHT hand; round shield with a boar on the LEFT arm; conical helmet.
PALETTE: leather #7A5634, moss green #4E6B3A, iron #5E6266, accent boar red #9A3428. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view: the pedestal top is visible and the shield is angled -> show both pedestal discs exactly edge-on with straight horizontal front edges and no visible top; face the round shield squarely toward the level orthographic camera.
- weapon hand and arm separation: the shield hides the LEFT arm and its gap from the torso -> hold the shield farther to the figure's own LEFT, on viewer RIGHT, with both slightly bent arms and a clear background gap between each arm and torso.
```

Original path: C:\Users\ren\.codex\generated_images\01a1333f-a46b-7c12-99a7-1b9a2445b577\exec-a346a70c-7aea-4ea0-a554-563befe86ec1.png

## Проверка и ограничения

Создан только design-front; согласованность front/side/back на этапе 1a не проверяется. Между кандидатами сохранены молодой воин, конический шлем, кожаная одежда, зелёный плащ, топор в собственной правой руке и щит с кабаном слева. В g2 изменились скульптурные детали одежды, положение топора, оформление кабана (светлый на красном поле), фронтальность щита и подставки. Это новая генерация с тем же эталоном, а не редактирование g1.

Оба кандидата и финальный g2: exit 0, 0 FAIL, WARN view.frame_top. Повтор вызван визуальными нарушениями проекции и зазоров рук. В g2 они улучшены, но не устранены полностью; два пункта CHECKLIST остались failed. Лимит 2/2 исчерпан, выбран g2, статус «предложено».

Оба PNG имеют 1086×1448; размер не передавался, аспект 3:4 задан только в CORE. Все результаты сохранены побайтово, без ресайза, обрезки, перекраски, ретуши и пересохранения.

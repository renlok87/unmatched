# Этап 1c — Патрокл, 2026-10-15

Инструмент: встроенный image_gen.imagegen. Режим: edit / style-transfer. По одному виду за вызов; порядок front → side (right) → back. CORE извлечены по заголовкам в начале строк и переданы без дополнений. Коррекций не потребовалось.

## patroclus-front-g1.png

Date: 2026-10-15. Tool: image_gen.imagegen. Prompt key: 1c/front/g1

referenced_image_paths (in call order; repository-relative):

1. art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-draft-tripo/orthos/ortho_front.png
2. art/imagegen/concept-patroclus-codex/design/patroclus-front.png

Exact prompt:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, FRONT
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Patroclus, companion of Achilles: young Greek warrior in a linen corslet and blue cloak, simple bronze helmet, short sword in his RIGHT hand, small round shield on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: short sword in the figure's own RIGHT hand; small round shield on the LEFT arm; blue cloak.
PALETTE: linen #D9CBA6, aegean blue #2F5B85, bronze #A9773A, accent white plume #EDEBE4. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: FRONT: strict front orthographic view, the figure faces the camera, no three-quarter turn.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x19.9%-80.1%, pedestal top y85.9%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

original_path: C:\Users\ren\.codex\generated_images\01a13e15-3309-7ca0-afd8-f8ed65f015b5\exec-349009db-3aea-42a7-81a3-160acb2ac280.png

saved_path: art/imagegen/concept-patroclus-codex/concepts/patroclus-front-g1.png

## patroclus-side-g1.png

Date: 2026-10-15. Tool: image_gen.imagegen. Prompt key: 1c/side/g1

referenced_image_paths (in call order; repository-relative):

1. art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-draft-tripo/orthos/ortho_right.png
2. art/imagegen/concept-patroclus-codex/design/patroclus-front.png

Exact prompt:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, RIGHT SIDE
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Patroclus, companion of Achilles: young Greek warrior in a linen corslet and blue cloak, simple bronze helmet, short sword in his RIGHT hand, small round shield on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: short sword in the figure's own RIGHT hand; small round shield on the LEFT arm; blue cloak.
PALETTE: linen #D9CBA6, aegean blue #2F5B85, bronze #A9773A, accent white plume #EDEBE4. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: RIGHT SIDE: strict profile, the figure's OWN right side faces the camera, its face toward the right edge of the image, no three-quarter view.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x20.7%-79.3%, pedestal top y85.9%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

original_path: C:\Users\ren\.codex\generated_images\01a13e15-3309-7ca0-afd8-f8ed65f015b5\exec-81849b16-faa1-4ef0-9d7f-f95286781cd7.png

saved_path: art/imagegen/concept-patroclus-codex/concepts/patroclus-side-g1.png

## patroclus-back-g1.png

Date: 2026-10-15. Tool: image_gen.imagegen. Prompt key: 1c/back/g1

referenced_image_paths (in call order; repository-relative):

1. art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-draft-tripo/orthos/ortho_back.png
2. art/imagegen/concept-patroclus-codex/design/patroclus-front.png
3. art/imagegen/concept-patroclus-codex/patroclus-side.png

Exact prompt:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, BACK
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
Image 3 is the finished side view of the SAME miniature, for continuity of colours and details only.
SUBJECT: Patroclus, companion of Achilles: young Greek warrior in a linen corslet and blue cloak, simple bronze helmet, short sword in his RIGHT hand, small round shield on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: short sword in the figure's own RIGHT hand; small round shield on the LEFT arm; blue cloak.
PALETTE: linen #D9CBA6, aegean blue #2F5B85, bronze #A9773A, accent white plume #EDEBE4. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: BACK: camera directly behind, no face visible, no three-quarter view. The weapon in the figure's own RIGHT hand appears on the viewer's RIGHT.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x19.9%-80.1%, pedestal top y85.9%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

original_path: C:\Users\ren\.codex\generated_images\01a13e15-3309-7ca0-afd8-f8ed65f015b5\exec-eef8e8f5-3c1e-4a35-a161-568dfa6f4f68.png

saved_path: art/imagegen/concept-patroclus-codex/concepts/patroclus-back-g1.png

## Проверка и ограничения

Между видами совпадают личность, бронзовый шлем с белым плюмажем, льняной корсет, эгейский синий плащ, короткий меч в правой руке, щит на левой руке и тёмная двухъярусная подставка. Разные ракурсы следуют соответствующим рендерам 1b; side показывает собственную правую сторону персонажа лицом вправо, back использует выбранный side для непрерывности материалов и цвета. Мелкие орнаменты и складки нарисованы генератором и не гарантируют попиксельного или геометрического совпадения.

Все выбранные виды и контактный лист осмотрены. Все одиночные проверки завершились с exit 0 (12 PASS), итоговый набор — exit 0, 33 PASS, 0 WARN, 0 FAIL. Повторов и нарушений CHECKLIST не выявлено; расхождения кадра на доли процента допускаются заданием. Исходные результаты не редактировались, скопированы побайтно, оригиналы сохранены. Это растровые концепты со статусом «предложено»; готовность 3D-модели к игре не оценивалась.

---

# Промпты Патрокла

Дата: 2026-10-13. Инструмент: image_gen.imagegen; mode=generate.

referenced_image_paths записаны от корня репозитория; в вызовах инструмента разрешены в абсолютные пути. Порядок сохранён.

## patroclus-design-front-g1.png

Дата: 2026-10-13. Инструмент: image_gen.imagegen.

referenced_image_paths (по порядку):

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Ключ: 1a/design-front/g1

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Patroclus, companion of Achilles: young Greek warrior in a linen corslet and blue cloak, simple bronze helmet, short sword in his RIGHT hand, small round shield on his LEFT arm.
IDENTITY ANCHORS, each clearly visible: short sword in the figure's own RIGHT hand; small round shield on the LEFT arm; blue cloak.
PALETTE: linen #D9CBA6, aegean blue #2F5B85, bronze #A9773A, accent white plume #EDEBE4. These are the main colours plus one accent; no other strong colours.
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

original_path: C:\Users\ren\.codex\generated_images\01a1333a-564d-71a1-8bf9-1d7002be3fe1\exec-ee1876bb-64a0-4bd0-82cb-a29f83c818da.png

saved_path: art/imagegen/concept-patroclus-codex/concepts/patroclus-design-front-g1.png

## patroclus-design-front-g2.png

Дата: 2026-10-13. Инструмент: image_gen.imagegen.

referenced_image_paths (по порядку):

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Ключ: 1a/design-front/g2

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Patroclus, companion of Achilles: young Greek warrior in a linen corslet and blue cloak, simple bronze helmet, short sword in his RIGHT hand, small round shield on his LEFT arm.
IDENTITY ANCHORS, each clearly visible: short sword in the figure's own RIGHT hand; small round shield on the LEFT arm; blue cloak.
PALETTE: linen #D9CBA6, aegean blue #2F5B85, bronze #A9773A, accent white plume #EDEBE4. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view: the head turns toward the viewer's right and the pedestal's top surface is visible -> face and body must face straight ahead with zero turn; pedestal must be exactly edge-on with an invisible top surface and a straight horizontal front edge.
- the whole subject and pedestal visible, nothing cropped; plain flat dark gray background: the charcoal background has a lighter central gradient and darker edges -> use one uniform flat dark gray background with no gradient or vignette.
```

original_path: C:\Users\ren\.codex\generated_images\01a1333a-564d-71a1-8bf9-1d7002be3fe1\exec-32458222-e010-44fc-b10e-735285b5919f.png

saved_path: art/imagegen/concept-patroclus-codex/concepts/patroclus-design-front-g2.png

## Проверка и ограничения

Создан один вид design-front; межвидовая согласованность не оценивается. Между попытками совпадают персонаж, основные материалы и цвета, сторона меча и щита, синий плащ и белый плюмаж. Изменились направление лица, орнаменты, складки, подставка, кадрирование и тон фона. Это два кандидата, а не многовидовой набор.

Выбран g2. Финальный код 0, PASS 12, WARN 1, FAIL 0. WARN view.frame_top: 3,384 % вместо 4 %. Визуально не пройдена строгая невидимость верха подставки; лимит 2/2 исчерпан. Ограничение в verification.json; статус — предложено. Исходные PNG не изменялись.

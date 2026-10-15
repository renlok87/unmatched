# Промпты Sherlock Holmes — 1c

Дата: 2026-10-15. Инструмент: встроенный image_gen. Режим: edit / style-transfer.
Один вызов — один вид; размер аргументом не передавался, transparent_background=false.
Все локальные входные изображения открыты через view_image перед соответствующими вызовами.
referenced_image_paths ниже записаны относительно корня в порядке вызова; в image_gen передавались абсолютные пути, разрешённые относительно C:/Users/ren/WebstormProjects/unmached/unmached/.
CORE извлечены только по отдельным заголовкам в начале строки. Коррекций в этом запуске нет.

## art/imagegen/concept-sherlock-holmes-codex/concepts/sherlock-holmes-front-g1.png

prompt_key: 1c/front/g1

referenced_image_paths:

1. art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261015-draft-tripo/orthos/ortho_front.png
2. art/imagegen/concept-sherlock-holmes-codex/design/sherlock-holmes-front.png

Exact prompt:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, FRONT
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Sherlock Holmes, the detective: tall lean man in a deerstalker cap and Inverness cape over a tweed suit, curved pipe, holding a magnifying glass in his RIGHT hand.
IDENTITY ANCHORS, where visible from this side: magnifying glass in the figure's own RIGHT hand; deerstalker cap; Inverness cape; curved pipe.
PALETTE: tweed brown #7A6448, cape grey #6A6B66, pipe dark #3A2A20, accent brass lens #C9A24A. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: FRONT: strict front orthographic view, the figure faces the camera, no three-quarter turn.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x21.0%-79.0%, pedestal top y85.5%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

## art/imagegen/concept-sherlock-holmes-codex/concepts/sherlock-holmes-side-g1.png

prompt_key: 1c/side/g1

referenced_image_paths:

1. art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261015-draft-tripo/orthos/ortho_left.png
2. art/imagegen/concept-sherlock-holmes-codex/design/sherlock-holmes-front.png

Exact prompt:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, LEFT SIDE
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Sherlock Holmes, the detective: tall lean man in a deerstalker cap and Inverness cape over a tweed suit, curved pipe, holding a magnifying glass in his RIGHT hand.
IDENTITY ANCHORS, where visible from this side: magnifying glass in the figure's own RIGHT hand; deerstalker cap; Inverness cape; curved pipe.
PALETTE: tweed brown #7A6448, cape grey #6A6B66, pipe dark #3A2A20, accent brass lens #C9A24A. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: LEFT SIDE: strict profile, the figure's OWN left side faces the camera, its face toward the left edge of the image, no three-quarter view.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x21.0%-79.0%, pedestal top y85.5%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

## art/imagegen/concept-sherlock-holmes-codex/concepts/sherlock-holmes-back-g1.png

prompt_key: 1c/back/g1

referenced_image_paths:

1. art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261015-draft-tripo/orthos/ortho_back.png
2. art/imagegen/concept-sherlock-holmes-codex/design/sherlock-holmes-front.png
3. art/imagegen/concept-sherlock-holmes-codex/sherlock-holmes-side.png

Exact prompt:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, BACK
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
Image 3 is the finished side view of the SAME miniature, for continuity of colours and details only.
SUBJECT: Sherlock Holmes, the detective: tall lean man in a deerstalker cap and Inverness cape over a tweed suit, curved pipe, holding a magnifying glass in his RIGHT hand.
IDENTITY ANCHORS, where visible from this side: magnifying glass in the figure's own RIGHT hand; deerstalker cap; Inverness cape; curved pipe.
PALETTE: tweed brown #7A6448, cape grey #6A6B66, pipe dark #3A2A20, accent brass lens #C9A24A. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: BACK: camera directly behind, no face visible, no three-quarter view. The weapon in the figure's own RIGHT hand appears on the viewer's RIGHT.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x21.0%-79.0%, pedestal top y85.5%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

## Проверка и ограничения

Выбраны front g1, side g1 (left), back g1. Каждый отдельный запуск скрипта: код 0, 12 PASS; финал: код 0, 33 PASS, 0 WARN, 0 FAIL. Все три исходных PNG и сводный лист просмотрены. Совпадают образ, основная поза, сторона лупы, материалы и палитра; back использует завершённый side как третий вход. Складки, микрорельеф ткани, волосы и отражения линзы интерпретированы генератором. Трубка видна во front/side и закрыта фигурой в back. Геометрическая и попиксельная тождественность 1b не доказана; числовые отличия кадрирования и фона находятся в README и verification. Непройденных пунктов CHECKLIST в 1c не выявлено, повторов не было. Размеры инструмента 1086 × 1448 при исходных орторендерах 1152 × 1536; аспект сохранён. Генерации сохранены побайтно без изменения пикселей, внешние оригиналы оставлены на месте. Статус: предложено.

---

# Промпты Sherlock Holmes — 1a

Дата: 2026-10-13. Инструмент: image_gen. Режим: generate.
Один вызов — одна картинка; размер не задавался.
referenced_image_paths приведены относительно корня репозитория в порядке вызова; в инструмент передавался абсолютный путь, разрешённый относительно C:/Users/ren/WebstormProjects/unmached/unmached/.

## concepts/sherlock-holmes-design-front-g1.png

prompt_key: 1a/design-front/g1

referenced_image_paths:

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Sherlock Holmes, the detective: tall lean man in a deerstalker cap and Inverness cape over a tweed suit, curved pipe, holding a magnifying glass in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: magnifying glass in the figure's own RIGHT hand; deerstalker cap; Inverness cape; curved pipe.
PALETTE: tweed brown #7A6448, cape grey #6A6B66, pipe dark #3A2A20, accent brass lens #C9A24A. These are the main colours plus one accent; no other strong colours.
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

## concepts/sherlock-holmes-design-front-g2.png

prompt_key: 1a/design-front/g2

referenced_image_paths:

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Sherlock Holmes, the detective: tall lean man in a deerstalker cap and Inverness cape over a tweed suit, curved pipe, holding a magnifying glass in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: magnifying glass in the figure's own RIGHT hand; deerstalker cap; Inverness cape; curved pipe.
PALETTE: tweed brown #7A6448, cape grey #6A6B66, pipe dark #3A2A20, accent brass lens #C9A24A. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: head is slightly turned and pedestal top is visible -> face, torso and feet must face directly forward with no turn, and both pedestal discs must be exactly edge-on with no visible top plane.
- The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view. (both arms clearly apart from the torso, not a T-pose, not an A-pose): the figure's own LEFT hand is in a pocket and its arm merges with the body -> bring the left hand fully outside the pocket, with both arms slightly bent and separated from the torso and cape by clear visible background gaps; keep the magnifying glass in the right hand on the viewer's left.
- the whole subject and pedestal visible, nothing cropped; plain flat dark gray background: background has tonal shading -> use a single uniform flat neutral dark gray without gradient, vignette or texture.
```

## Проверка и ограничения

Один вид: межвидовое соответствие не оценивается. В обеих генерациях сохранены персонаж, палитра, четыре якоря и сторона лупы. g2 меняет положение левой кисти, фронтальность головы, ракурс подставки и складки плаща. Выбран g2. Просветы рук остаются закрыты плащом; лимит 2/2 исчерпан. Оба кандидата и финал прошли скрипт с WARN верхнего поля. Низ подставки отличается от y93%. Пиксели генераций не изменялись.

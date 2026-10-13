# Exact generation prompts
Date: 2026-10-13
Tool: image_gen.imagegen (built-in); mode: generate

## art/imagegen/concept-achilles-codex/concepts/achilles-design-front-g1.png
prompt_key: 1a/design-front/g1
referenced_image_paths in call order:
```json
[
  "C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
]
```
Exact prompt:
```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Achilles, the greatest Greek warrior: athletic young man in a bronze muscle cuirass, red cloak, crested Corinthian helmet pushed up on his head, greaves and sandals; spear held upright in his RIGHT hand, round bronze shield on his LEFT arm.
IDENTITY ANCHORS, each clearly visible: spear upright in the figure's own RIGHT hand; round bronze shield on the LEFT arm; tall horsehair crest; red cloak.
PALETTE: bronze #A9773A, crimson #8E2A23, olive skin #B98B66, accent gold crest trim #E0B54A. These are the main colours plus one accent; no other strong colours.
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

## art/imagegen/concept-achilles-codex/concepts/achilles-design-front-g2.png
prompt_key: 1a/design-front/g2
referenced_image_paths in call order:
```json
[
  "C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
]
```
Exact prompt:
```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Achilles, the greatest Greek warrior: athletic young man in a bronze muscle cuirass, red cloak, crested Corinthian helmet pushed up on his head, greaves and sandals; spear held upright in his RIGHT hand, round bronze shield on his LEFT arm.
IDENTITY ANCHORS, each clearly visible: spear upright in the figure's own RIGHT hand; round bronze shield on the LEFT arm; tall horsehair crest; red cloak.
PALETTE: bronze #A9773A, crimson #8E2A23, olive skin #B98B66, accent gold crest trim #E0B54A. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: the pedestal top is visible and the shield is foreshortened -> show the pedestal exactly edge-on with no visible top and a straight horizontal front edge; remove perspective and keep a strictly frontal orthographic camera.
- The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view. (both arms clearly apart from the torso, not a T-pose, not an A-pose): the LEFT arm is hidden behind a shield touching the torso -> make the LEFT arm visibly separate from the torso with a clear gap; hold the round shield farther to the viewer's RIGHT while keeping both elbows slightly bent and the upright spear in the RIGHT hand.
```

## Проверка и ограничения
Создан только design-front; сравнение front/side/back на этапе 1a не выполнялось. В g1 и g2 сохранены Ахиллес, бронзовая кираса, красный плащ, высокий гребень, копьё в собственной правой руке и щит на левой. Изменились орнамент, положение руки и щита, вид подставки и кадрирование. CORE не менялся; коррекция направлена только на два невыполненных пункта g1.
Выбран g2. Проверки каждого кандидата и финального файла дали код 0; финальный отчёт: 12 PASS, 1 WARN, 0 FAIL. Визуальный CHECKLIST g2: 6/6. Допустимый WARN view.frame_top (2,624% вместо минимум 4%) не послужил причиной ретрая. Низ и центр подставки отклоняются от точных координат CORE: 94,890% и 48,573%. Подробности и результаты всех прогонов — в verification.json. Исходные входы неизменны, изображения сохранены побайтово. Статус: предложено.



## Этап 1c — виды поверх черновых орто

Дата: 2026-10-13. Инструмент: image_gen.imagegen, mode=edit (style-transfer).

referenced_image_paths перечислены в порядке вызова относительно корня репозитория; инструменту переданы абсолютные пути. CORE сохранён дословно, на ретраях добавлен только CORRECTION. Размер не передавался.

### art/imagegen/concept-achilles-codex/concepts/achilles-front-g1.png

Дата: 2026-10-13. Инструмент: image_gen.imagegen. prompt_key: 1c/front/g1.

referenced_image_paths, в порядке вызова:

- art/pipeline-candidates/ASSET-ACHILLES-001/20261013-draft-tripo/orthos/ortho_front.png (sha256 fac8529cff026f5f0cfc93445fdd217ea20c619e350583412ed838d35cec7242)
- art/imagegen/concept-achilles-codex/design/achilles-front.png (sha256 1f2156d48e5113538642834091e1521d4be18a24f4be2db6a2fa6cfc557e1267)

Точный промпт:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, FRONT
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Achilles, the greatest Greek warrior: athletic young man in a bronze muscle cuirass, red cloak, crested Corinthian helmet pushed up on his head, greaves and sandals; spear held upright in his RIGHT hand, round bronze shield on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: spear upright in the figure's own RIGHT hand; round bronze shield on the LEFT arm; tall horsehair crest; red cloak.
PALETTE: bronze #A9773A, crimson #8E2A23, olive skin #B98B66, accent gold crest trim #E0B54A. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
VIEW: FRONT: strict front orthographic view, the figure faces the camera, no three-quarter turn.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x22.1%-77.9%, pedestal top y86.3%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

### art/imagegen/concept-achilles-codex/concepts/achilles-side-g1.png

Дата: 2026-10-13. Инструмент: image_gen.imagegen. prompt_key: 1c/side/g1.

referenced_image_paths, в порядке вызова:

- art/pipeline-candidates/ASSET-ACHILLES-001/20261013-draft-tripo/orthos/ortho_left.png (sha256 b3d5cfefd2b65dd918a0bcc19ea5d0664b4f95228791f73be8908c1ff01793de)
- art/imagegen/concept-achilles-codex/design/achilles-front.png (sha256 1f2156d48e5113538642834091e1521d4be18a24f4be2db6a2fa6cfc557e1267)

Точный промпт:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, LEFT SIDE
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Achilles, the greatest Greek warrior: athletic young man in a bronze muscle cuirass, red cloak, crested Corinthian helmet pushed up on his head, greaves and sandals; spear held upright in his RIGHT hand, round bronze shield on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: spear upright in the figure's own RIGHT hand; round bronze shield on the LEFT arm; tall horsehair crest; red cloak.
PALETTE: bronze #A9773A, crimson #8E2A23, olive skin #B98B66, accent gold crest trim #E0B54A. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
VIEW: LEFT SIDE: strict profile, the figure's OWN left side faces the camera, its face toward the left edge of the image, no three-quarter view.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x22.8%-77.2%, pedestal top y86.3%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

### art/imagegen/concept-achilles-codex/concepts/achilles-side-g2.png

Дата: 2026-10-13. Инструмент: image_gen.imagegen. prompt_key: 1c/side/g2.

referenced_image_paths, в порядке вызова:

- art/pipeline-candidates/ASSET-ACHILLES-001/20261013-draft-tripo/orthos/ortho_left.png (sha256 b3d5cfefd2b65dd918a0bcc19ea5d0664b4f95228791f73be8908c1ff01793de)
- art/imagegen/concept-achilles-codex/design/achilles-front.png (sha256 1f2156d48e5113538642834091e1521d4be18a24f4be2db6a2fa6cfc557e1267)

Точный промпт:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, LEFT SIDE
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Achilles, the greatest Greek warrior: athletic young man in a bronze muscle cuirass, red cloak, crested Corinthian helmet pushed up on his head, greaves and sandals; spear held upright in his RIGHT hand, round bronze shield on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: spear upright in the figure's own RIGHT hand; round bronze shield on the LEFT arm; tall horsehair crest; red cloak.
PALETTE: bronze #A9773A, crimson #8E2A23, olive skin #B98B66, accent gold crest trim #E0B54A. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
VIEW: LEFT SIDE: strict profile, the figure's OWN left side faces the camera, its face toward the left edge of the image, no three-quarter view.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x22.8%-77.2%, pedestal top y86.3%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
CORRECTION (fix only this; everything above still applies):
- silhouette, pose, arm and weapon positions follow image 1 (the draft render): the spearhead is broadened into a front-facing blade in the side view -> paint the original narrow edge-on spearhead exactly inside image 1's spearhead silhouette; preserve its position and hand grip.
```

### art/imagegen/concept-achilles-codex/concepts/achilles-back-g1.png

Дата: 2026-10-13. Инструмент: image_gen.imagegen. prompt_key: 1c/back/g1.

referenced_image_paths, в порядке вызова:

- art/pipeline-candidates/ASSET-ACHILLES-001/20261013-draft-tripo/orthos/ortho_back.png (sha256 91ba240a407e928f2343ce5b0faf38bb11f6b65e89098f6f18c46daaf7fb8f91)
- art/imagegen/concept-achilles-codex/design/achilles-front.png (sha256 1f2156d48e5113538642834091e1521d4be18a24f4be2db6a2fa6cfc557e1267)
- art/imagegen/concept-achilles-codex/achilles-side.png (sha256 0bc06f2ddcd5b474f0f9c42e54df1af72cf772cb6945db1cd4aa218b18f8fd14)

Точный промпт:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, BACK
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
Image 3 is the finished side view of the SAME miniature, for continuity of colours and details only.
SUBJECT: Achilles, the greatest Greek warrior: athletic young man in a bronze muscle cuirass, red cloak, crested Corinthian helmet pushed up on his head, greaves and sandals; spear held upright in his RIGHT hand, round bronze shield on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: spear upright in the figure's own RIGHT hand; round bronze shield on the LEFT arm; tall horsehair crest; red cloak.
PALETTE: bronze #A9773A, crimson #8E2A23, olive skin #B98B66, accent gold crest trim #E0B54A. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
VIEW: BACK: camera directly behind, no face visible, no three-quarter view. The weapon in the figure's own RIGHT hand appears on the viewer's RIGHT.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x22.1%-77.9%, pedestal top y86.3%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

### art/imagegen/concept-achilles-codex/concepts/achilles-back-g2.png

Дата: 2026-10-13. Инструмент: image_gen.imagegen. prompt_key: 1c/back/g2.

referenced_image_paths, в порядке вызова:

- art/pipeline-candidates/ASSET-ACHILLES-001/20261013-draft-tripo/orthos/ortho_back.png (sha256 91ba240a407e928f2343ce5b0faf38bb11f6b65e89098f6f18c46daaf7fb8f91)
- art/imagegen/concept-achilles-codex/design/achilles-front.png (sha256 1f2156d48e5113538642834091e1521d4be18a24f4be2db6a2fa6cfc557e1267)
- art/imagegen/concept-achilles-codex/achilles-side.png (sha256 0bc06f2ddcd5b474f0f9c42e54df1af72cf772cb6945db1cd4aa218b18f8fd14)

Точный промпт:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, BACK
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
Image 3 is the finished side view of the SAME miniature, for continuity of colours and details only.
SUBJECT: Achilles, the greatest Greek warrior: athletic young man in a bronze muscle cuirass, red cloak, crested Corinthian helmet pushed up on his head, greaves and sandals; spear held upright in his RIGHT hand, round bronze shield on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: spear upright in the figure's own RIGHT hand; round bronze shield on the LEFT arm; tall horsehair crest; red cloak.
PALETTE: bronze #A9773A, crimson #8E2A23, olive skin #B98B66, accent gold crest trim #E0B54A. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
VIEW: BACK: camera directly behind, no face visible, no three-quarter view. The weapon in the figure's own RIGHT hand appears on the viewer's RIGHT.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x22.1%-77.9%, pedestal top y86.3%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
CORRECTION (fix only this; everything above still applies):
- identity, costume, colours and materials follow the approved design; every anchor visible from this side is there: front lion reliefs are incorrectly painted on the rear-facing shield and greaves -> show image 1's plain inner bronze shield surface with its existing left-hand grip and plain rear greave panels; keep lion ornaments only on their front surfaces, with no shield flip or pose change.
```

### art/imagegen/concept-achilles-codex/concepts/achilles-front-g2.png

Дата: 2026-10-13. Инструмент: image_gen.imagegen. prompt_key: 1c/front/g2.

referenced_image_paths, в порядке вызова:

- art/pipeline-candidates/ASSET-ACHILLES-001/20261013-draft-tripo/orthos/ortho_front.png (sha256 fac8529cff026f5f0cfc93445fdd217ea20c619e350583412ed838d35cec7242)
- art/imagegen/concept-achilles-codex/design/achilles-front.png (sha256 1f2156d48e5113538642834091e1521d4be18a24f4be2db6a2fa6cfc557e1267)

Точный промпт:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, FRONT
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Achilles, the greatest Greek warrior: athletic young man in a bronze muscle cuirass, red cloak, crested Corinthian helmet pushed up on his head, greaves and sandals; spear held upright in his RIGHT hand, round bronze shield on his LEFT arm.
IDENTITY ANCHORS, where visible from this side: spear upright in the figure's own RIGHT hand; round bronze shield on the LEFT arm; tall horsehair crest; red cloak.
PALETTE: bronze #A9773A, crimson #8E2A23, olive skin #B98B66, accent gold crest trim #E0B54A. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
VIEW: FRONT: strict front orthographic view, the figure faces the camera, no three-quarter turn.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x22.1%-77.9%, pedestal top y86.3%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
CORRECTION (fix only this; everything above still applies):
- framing as in image 1: the same pedestal position and size; the same highest point: the top is y3.867%, pedestal bottom y94.268%, width 55.617% -> match image 1 exactly: highest point y4.0%, pedestal x22.1%-77.9%, top y86.3%, bottom y94.0%, preserving pose and silhouette.
```


## Проверка и ограничения

Выбраны front g1, side g2, back g2. Бронзовая кираса и щит, красный плащ и гребень, золотая отделка, кожа, сторона оружия, масштаб и двухъярусная база согласованы между видами. На side g2 исправлена ширина наконечника; на back g2 исправлены поверхности щита и поножей. Front g2 отклонён из-за белой базы и изменения положения ноги. Все оригиналы сохранены без обработки.

Итоговый скрипт: код 0, 33 PASS, 0 WARN, 0 FAIL. Точное кадрирование по числам CORE не закрыто ни для одного выбранного вида; по 2/2 генерации текущего запуска исчерпаны. Измерения, false в CHECKLIST и limit_reached находятся в verification.json. Фон отличается до трёх уровней RGB; рельефы и складки интерпретированы независимо. Статус: предложено; внешняя приёмка не выполнялась.

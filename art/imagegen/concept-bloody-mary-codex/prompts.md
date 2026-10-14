# Промпты Bloody Mary — concept 1a

Дата: 2026-10-13. Инструмент: image_gen.imagegen. Режим: text-to-image с референсом качества. Размер не передавался; аспект 3:4 задан только текстом CORE.

## concepts/bloody-mary-design-front-g1.png

prompt_key: `1a/design-front/g1`

referenced_image_paths в порядке вызова:

1. `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Путь от корня репозитория: `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`.
SHA-256: e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9.

Точный prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Bloody Mary, the mirror ghost: gaunt pale spectral woman in a long tattered grey funeral gown and veil, long dark hair, bare feet, holding an oval hand mirror close to her chest with both hands, the gown trailing over the pedestal.
IDENTITY ANCHORS, each clearly visible: oval hand mirror held with both hands; tattered veil; long dark hair; bare feet.
PALETTE: ghost grey #8E949A, pale skin #D9D4CC, ink black #1F1D22, accent blood red #8F1C1C. These are the main colours plus one accent; no other strong colours.
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

## concepts/bloody-mary-design-front-g2.png

prompt_key: `1a/design-front/g2`

referenced_image_paths в порядке вызова:

1. `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Путь от корня репозитория: `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`.
SHA-256: e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9.

Точный prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Bloody Mary, the mirror ghost: gaunt pale spectral woman in a long tattered grey funeral gown and veil, long dark hair, bare feet, holding an oval hand mirror close to her chest with both hands, the gown trailing over the pedestal.
IDENTITY ANCHORS, each clearly visible: oval hand mirror held with both hands; tattered veil; long dark hair; bare feet.
PALETTE: ghost grey #8E949A, pale skin #D9D4CC, ink black #1F1D22, accent blood red #8F1C1C. These are the main colours plus one accent; no other strong colours.
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
- CHECKLIST strict front orthographic view, camera exactly level: pedestal top surface is visible -> show the pedestal exactly edge-on with no visible top surface and a straight horizontal front edge.
- CHECKLIST plain flat dark gray background: the background has a gradient and vignette -> use one uniform flat dark gray everywhere, with no gradient or vignette.
- CHECKLIST both arms clearly apart from the torso: hair and veil fill the arm-to-body spaces -> show clear background gaps between both arms and torso while keeping the required oval mirror held with both hands.
```

## Проверка и ограничения

Создан один вид design-front и два его кандидата; side/back не создавались. Между кандидатами сохранены тип персонажа, зеркало в обеих руках, рваная вуаль, длинные тёмные волосы, босые ступни и основные цвета с красным акцентом. В g2 изменились складки и разрывы ткани, добавились цветы у вуали, ступни стали ближе; подставка показана с ребра, фон стал ровным.

Оба кандидата и итоговый файл проверены скриптом: каждый запуск — код 0, 12 PASS, 1 WARN, 0 FAIL. Верхний отступ меньше 4% — разрешённый WARN. Визуальная проверка выбрала g2. Четвёртый пункт CHECKLIST остаётся failed: обязательное зеркало противоречит буквальному запрету предмета в руках, а волосы и ткань частично закрывают требуемые чистые зазоры у рук. Рамка зеркала имеет небольшой приглушённый бронзовый оттенок вне четырёх HEX ядра. Лимит 2/2 исчерпан; ограничения раскрыты в README.md и verification.json.

CORE во втором вызове совпадает с первым побуквенно. Добавлен только приведённый выше CORRECTION из трёх строк. Исходные изображения не правились; все копии побайтны. Художественная приёмка и проверка межвидовой согласованности не выполнялись.

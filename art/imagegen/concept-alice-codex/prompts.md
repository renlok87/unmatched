# Промпты ASSET-ALICE-001, этап 1a

Дата: 2026-10-13
Инструмент: image_gen.imagegen
Режим: generate; transparent_background=false; размер не задан.

## design-front-g1

prompt_key: 1a/design-front/g1
Предполагаемый файл: art/imagegen/concept-alice-codex/concepts/alice-design-front-g1.png (не создан).
referenced_image_paths в порядке вызова:
1. C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Alice from Wonderland: brave girl in a blue dress with a white pinafore apron, black hair band, striped stockings, holding a vorpal sword in her RIGHT hand.
IDENTITY ANCHORS, each clearly visible: vorpal sword in the figure's own RIGHT hand; white pinafore apron; black hair band; blue dress.
PALETTE: dress blue #5B8BC9, pinafore white #EDEAE2, hair gold #D9B864, accent sword steel #B9C2C9. These are the main colours plus one accent; no other strong colours.
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

Результат: HTTP 400 moderation_blocked, output, other. Request ID: 3c4e8ce9-7740-47d0-9e90-79728f5f8c29. Файл изображения не выдан. CORRECTION отсутствует.

## Проверка и ограничения

Видов нет: сравнение между видами и визуальный CHECKLIST невозможны. CORE не менялся; входы не менялись. Кандидат и выбранный дизайн отсутствуют. Проверочный скрипт не запускался. Пакет сохраняет отказ сервиса как блокер, а не как FAIL изображения; лимит не исчерпан.


## 2026-10-13 — запуск 2026-10-13-r2 — image_gen.imagegen

### design-front g2

Файл кандидата не создан; планируемый путь: art/imagegen/concept-alice-codex/concepts/alice-design-front-g2.png.
prompt_key: `1a/design-front/g2`.

referenced_image_paths (в порядке вызова):
1. `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`
   SHA-256: `e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9`.

Точный промпт (CORE, без CORRECTION):

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Alice from Unmatched: Battle of Legends Volume One, inspired by Lewis Carroll's Alice: a young adult woman with long blonde hair and a black hair band, light blue dress with a white apron, striped stockings and black shoes, holding the vorpal sword in her RIGHT hand.
IDENTITY ANCHORS, each clearly visible: vorpal sword in the RIGHT hand; light blue dress with white apron; black hair band; striped stockings.
PALETTE: dress blue #7FA7D9, apron white #ECEAE4, hair blonde #D9B86A, accent sword steel #B8BEC4. These are the main colours plus one accent; no other strong colours.
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

Результат: HTTP 400, moderation_blocked; moderation_stage: output; categories: [other].
request_id: ebdb3a05-4786-4a1a-8525-f1e573b1d5e0.
Изображение и original_path не выданы; режим generate, transparent_background=false; size не передавался.

## Проверка и ограничения

Запрошен только дизайн-front этапа 1a; другие виды не создавались, сравнение между видами невозможно.
CORE этого запуска дословно соответствует заданию; CORRECTION не добавлялся.
После отказа сервиса изображение отсутствует; автопроверка и визуальный CHECKLIST не выполнялись.
Выбранного кандидата нет. Оба входа сохранились без изменения; предыдущие записи сохранены.

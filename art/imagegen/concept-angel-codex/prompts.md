# ASSET-ANGEL-001 — промпты концепта 1a

Дата: 2026-10-13

Инструмент: image_gen (встроенный); режим: generate; один вызов — одно изображение.

Единственный визуальный вход — эталон мастерства; palette.json задаёт цвета и не передаётся как изображение. Пути ниже записаны относительно корня репозитория; инструменту они переданы развёрнутыми в абсолютные пути. Порядок входов сохранён.

## art/imagegen/concept-angel-codex/concepts/angel-design-front-g1.png

Date: 2026-10-13T09:03:08+00:00

prompt_key: 1a/design-front/g1

referenced_image_paths (call order):

```json
[
  "art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
]
```

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Angel from Buffy the Vampire Slayer (Unmatched: Buffy the Vampire Slayer): brooding vampire with spiky dark hair, long black leather coat over a dark shirt, wooden-handled broadsword in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: broadsword in the RIGHT hand; long black leather coat; spiky dark hair; dark shirt.
PALETTE: coat black #1C1A1C, shirt grey #4A4A50, skin pale #D9BFA8, accent blade steel #B8BEC4. These are the main colours plus one accent; no other strong colours.
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

## art/imagegen/concept-angel-codex/concepts/angel-design-front-g2.png

Date: 2026-10-13T09:04:33+00:00

prompt_key: 1a/design-front/g2

referenced_image_paths (call order):

```json
[
  "art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
]
```

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Angel from Buffy the Vampire Slayer (Unmatched: Buffy the Vampire Slayer): brooding vampire with spiky dark hair, long black leather coat over a dark shirt, wooden-handled broadsword in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: broadsword in the RIGHT hand; long black leather coat; spiky dark hair; dark shirt.
PALETTE: coat black #1C1A1C, shirt grey #4A4A50, skin pale #D9BFA8, accent blade steel #B8BEC4. These are the main colours plus one accent; no other strong colours.
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
- CHECKLIST strict front orthographic view: the pedestal's top surface is visible as a shallow ellipse -> show the pedestal exactly edge-on at zero elevation, with no visible top surface and a straight horizontal front edge.
```

## Проверка и ограничения

Создан только design-front; соответствие front/side/back на этапе 1a не проверяется. Между кандидатами сохраняются персонаж, фронтальный вид, правая рука с мечом (слева для зрителя), длинный чёрный плащ, тёмная рубашка, заострённые волосы и палитра.

CORE в обеих генерациях неизменён. В g2 добавлена одна строка CORRECTION: скрыть верх подставки и показать её с ребра. Генератор сам изменил воротник, складки и оформление клинка. У g2 две ступени подставки не читаются; она выглядит единым диском. Это отклонение от CORE сохранено без ручного исправления.

Генерации: g1 — 13 PASS, 0 WARN, 0 FAIL, но верх подставки визуально виден; g2 и финальный прогон — 12 PASS, 1 WARN view.single_component, 0 FAIL. Визуально второй фигуры нет. WARN разрешён заданием.

Выбран g2. Две генерации использованы. Шесть пунктов CHECKLIST выбранного файла визуально пройдены; требование CORE о двух низких дисках не выполнено и записано в verification.json. Низ подставки y=92.265% вместо 93%, центр x=49.678% вместо 50%; отклонения сохранены.

Изображения не ретушированы, не масштабированы, не обрезаны, не перекрашены и не перекодированы. Копии проверены побайтно. Статус — предложено.

# ASSET-ANGEL-001 — промпты видов 1c

Дата: 2026-10-13

Инструмент: image_gen (встроенный), режим edit / style-transfer. Один вызов — один вид. Размер не передавался; аспект 3:4 задан только в CORE. Пути референсов записаны относительно корня репозитория; инструмент получил их абсолютные развёрнутые пути в указанном порядке.

## art/imagegen/concept-angel-codex/concepts/angel-front-g1.png

Date: 2026-10-13T16:13:29+00:00

Tool: image_gen

prompt_key: 1c/front/g1

referenced_image_paths (call order):

```json
[
  "art/pipeline-candidates/ASSET-ANGEL-001/20261013-draft-tripo/orthos/ortho_front.png",
  "art/imagegen/concept-angel-codex/design/angel-front.png"
]
```

Exact prompt:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, FRONT
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Angel from Buffy the Vampire Slayer (Unmatched: Buffy the Vampire Slayer): brooding vampire with spiky dark hair, long black leather coat over a dark shirt, wooden-handled broadsword in his RIGHT hand.
IDENTITY ANCHORS, where visible from this side: broadsword in the RIGHT hand; long black leather coat; spiky dark hair; dark shirt.
PALETTE: coat black #1C1A1C, shirt grey #4A4A50, skin pale #D9BFA8, accent blade steel #B8BEC4. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
VIEW: FRONT: strict front orthographic view, the figure faces the camera, no three-quarter turn.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x15.9%-84.1%, pedestal top y87.7%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

original_path: C:/Users/ren/.codex/generated_images/01a13606-e90d-7c03-a6b0-38bdc7b81ce8/exec-6a8e2f1d-c763-4f35-8b55-48bf8a5782af.png

checks: art/imagegen/concept-angel-codex/checks/front-g1/checks-report.json

## art/imagegen/concept-angel-codex/concepts/angel-side-g1.png

Date: 2026-10-13T16:15:02+00:00

Tool: image_gen

prompt_key: 1c/side/g1

referenced_image_paths (call order):

```json
[
  "art/pipeline-candidates/ASSET-ANGEL-001/20261013-draft-tripo/orthos/ortho_left.png",
  "art/imagegen/concept-angel-codex/design/angel-front.png"
]
```

Exact prompt:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, LEFT SIDE
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Angel from Buffy the Vampire Slayer (Unmatched: Buffy the Vampire Slayer): brooding vampire with spiky dark hair, long black leather coat over a dark shirt, wooden-handled broadsword in his RIGHT hand.
IDENTITY ANCHORS, where visible from this side: broadsword in the RIGHT hand; long black leather coat; spiky dark hair; dark shirt.
PALETTE: coat black #1C1A1C, shirt grey #4A4A50, skin pale #D9BFA8, accent blade steel #B8BEC4. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
VIEW: LEFT SIDE: strict profile, the figure's OWN left side faces the camera, its face toward the left edge of the image, no three-quarter view.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x16.6%-83.4%, pedestal top y87.7%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

original_path: C:/Users/ren/.codex/generated_images/01a13606-e90d-7c03-a6b0-38bdc7b81ce8/exec-37d5b5b0-cde0-425f-bd1c-c5f2f871bd0e.png

checks: art/imagegen/concept-angel-codex/checks/side-g1/checks-report.json

## art/imagegen/concept-angel-codex/concepts/angel-back-g1.png

Date: 2026-10-13T16:16:27+00:00

Tool: image_gen

prompt_key: 1c/back/g1

referenced_image_paths (call order):

```json
[
  "art/pipeline-candidates/ASSET-ANGEL-001/20261013-draft-tripo/orthos/ortho_back.png",
  "art/imagegen/concept-angel-codex/design/angel-front.png",
  "art/imagegen/concept-angel-codex/angel-side.png"
]
```

Exact prompt:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, BACK
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
Image 3 is the finished side view of the SAME miniature, for continuity of colours and details only.
SUBJECT: Angel from Buffy the Vampire Slayer (Unmatched: Buffy the Vampire Slayer): brooding vampire with spiky dark hair, long black leather coat over a dark shirt, wooden-handled broadsword in his RIGHT hand.
IDENTITY ANCHORS, where visible from this side: broadsword in the RIGHT hand; long black leather coat; spiky dark hair; dark shirt.
PALETTE: coat black #1C1A1C, shirt grey #4A4A50, skin pale #D9BFA8, accent blade steel #B8BEC4. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
VIEW: BACK: camera directly behind, no face visible, no three-quarter view. The weapon in the figure's own RIGHT hand appears on the viewer's RIGHT.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x15.9%-84.1%, pedestal top y87.7%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

original_path: C:/Users/ren/.codex/generated_images/01a13606-e90d-7c03-a6b0-38bdc7b81ce8/exec-bed9363d-115b-476f-ae5c-75329e5dc901.png

checks: art/imagegen/concept-angel-codex/checks/back-g1/checks-report.json

## Проверка и ограничения

Выбраны front g1, side g1, back g1. Каждый CORE передан дословно; CORRECTION не понадобился. Согласованы лицо во front/side, тёмные заострённые волосы, чёрная кожа плаща, серая рубашка, стальной клинок и деревянная рукоять; меч остаётся в правой руке. Side показывает собственный левый бок, back — спину без лица и меч справа для зрителя. Поза и силуэт визуально соответствуют своим ортопроекциям.

Генератор самостоятельно добавил фактуру кожи, швы, складки и стальной блик внутри контура. На спине рубашка закрыта плащом; это ожидаемая окклюзия. Раскладка мелкой фактуры между видами не является точной UV-проекцией. Никаких ручных правок, изменения размера, кадрирования или перекодирования PNG не было.

Все виды: 1086 × 1448, 3:4. Финальный скрипт: код 0, 32 PASS, 1 WARN, 0 FAIL. WARN view.single_component на back — результат отделения тёмной поверхности от фона; визуально лишних фигур нет. WARN не служил причиной ретрая.

Нормализованная рамка близка к исходной, но числа не воспроизведены математически точно: измеренные верх/низ/ширина/оценка верха подставки и отклонения записаны в verification.json. Медианы фона front [40,40,39], side [41,41,41], back [40,40,40]; исходные орто имеют [46,46,46]. Все фоны визуально ровные тёмно-серые; полной побайтовой идентичности фона нет.

Первое сохранение front не выполнилось из-за обработки кавычек PowerShell. Затем преждевременно запущенная проверка сообщила отсутствие angel-front.png и не создала отчёт (код оболочки 1). Данные переданы как UTF-8 hex, исходный PNG скопирован побайтно и тот же кандидат проверен успешно. Дополнительной генерации для исправления этого сбоя не было. Сбой сохранён в verification.json.

Проверка камеры, анатомии, материалов и руки визуальная; скрипт их не доказывает. Пакет предложен для приёмки Claude.

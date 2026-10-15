# Промпты этапа 1c — front / left side / back

Дата: 2026-10-15
Инструмент: image_gen (image_gen.imagegen), встроенный режим edit.
Размер не передавался; аспект 3:4 указан только в CORE.

## art/imagegen/concept-dr-watson-codex/concepts/dr-watson-front-g1.png

prompt_key: 1c/front/g1
referenced_image_paths (точный порядок; в вызове раскрыты в абсолютные пути):
1. art/pipeline-candidates/ASSET-DR-WATSON-001/20261015-draft-tripo/orthos/ortho_front.png
2. art/imagegen/concept-dr-watson-codex/design/dr-watson-front.png

original_path: C:\Users\ren\.codex\generated_images\01a13e3a-640b-7221-bd64-dcfc5ecbe194\exec-80489bee-94ee-4c52-aa67-e5a22a770502.png
CORRECTION: отсутствует.

Точный промпт:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, FRONT
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Dr. Watson, Holmes's companion: sturdy moustached Victorian gentleman in a bowler hat, brown overcoat and waistcoat, revolver held in his RIGHT hand, medical bag in his LEFT hand.
IDENTITY ANCHORS, where visible from this side: revolver in the figure's own RIGHT hand; medical bag in the LEFT hand; bowler hat; thick moustache.
PALETTE: coat brown #5E4532, bowler black #1F1E1E, waistcoat tan #A08262, accent watch chain gold #C9A24A. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: FRONT: strict front orthographic view, the figure faces the camera, no three-quarter turn.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x16.6%-83.4%, pedestal top y84.5%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

## art/imagegen/concept-dr-watson-codex/concepts/dr-watson-side-g1.png

prompt_key: 1c/side/g1
referenced_image_paths (точный порядок; в вызове раскрыты в абсолютные пути):
1. art/pipeline-candidates/ASSET-DR-WATSON-001/20261015-draft-tripo/orthos/ortho_left.png
2. art/imagegen/concept-dr-watson-codex/design/dr-watson-front.png

original_path: C:\Users\ren\.codex\generated_images\01a13e3a-640b-7221-bd64-dcfc5ecbe194\exec-6c54e03e-9917-468c-883e-228d5d8e9062.png
CORRECTION: отсутствует.

Точный промпт:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, LEFT SIDE
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
SUBJECT: Dr. Watson, Holmes's companion: sturdy moustached Victorian gentleman in a bowler hat, brown overcoat and waistcoat, revolver held in his RIGHT hand, medical bag in his LEFT hand.
IDENTITY ANCHORS, where visible from this side: revolver in the figure's own RIGHT hand; medical bag in the LEFT hand; bowler hat; thick moustache.
PALETTE: coat brown #5E4532, bowler black #1F1E1E, waistcoat tan #A08262, accent watch chain gold #C9A24A. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: LEFT SIDE: strict profile, the figure's OWN left side faces the camera, its face toward the left edge of the image, no three-quarter view.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x16.9%-83.1%, pedestal top y84.5%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

## art/imagegen/concept-dr-watson-codex/concepts/dr-watson-back-g1.png

prompt_key: 1c/back/g1
referenced_image_paths (точный порядок; в вызове раскрыты в абсолютные пути):
1. art/pipeline-candidates/ASSET-DR-WATSON-001/20261015-draft-tripo/orthos/ortho_back.png
2. art/imagegen/concept-dr-watson-codex/design/dr-watson-front.png
3. art/imagegen/concept-dr-watson-codex/dr-watson-side.png

original_path: C:\Users\ren\.codex\generated_images\01a13e3a-640b-7221-bd64-dcfc5ecbe194\exec-cfb29ad0-87e4-4d27-a3ad-bacf68dff20d.png
CORRECTION: отсутствует.

Точный промпт:

```text
Use case: style-transfer. Image 1 is the EDIT TARGET: the draft 3D model of this miniature, BACK
orthographic render. Paint directly over it. Keep exactly its silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing.
Image 2 is the APPROVED FRONT DESIGN of the SAME miniature: transfer its identity, face, costume, materials, colours,
ornament and painted detail level onto image 1. Do not copy its pose, proportions, framing or camera.
Image 3 is the finished side view of the SAME miniature, for continuity of colours and details only.
SUBJECT: Dr. Watson, Holmes's companion: sturdy moustached Victorian gentleman in a bowler hat, brown overcoat and waistcoat, revolver held in his RIGHT hand, medical bag in his LEFT hand.
IDENTITY ANCHORS, where visible from this side: revolver in the figure's own RIGHT hand; medical bag in the LEFT hand; bowler hat; thick moustache.
PALETTE: coat brown #5E4532, bowler black #1F1E1E, waistcoat tan #A08262, accent watch chain gold #C9A24A. The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.
PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no coloured ring and no metal band.
VIEW: BACK: camera directly behind, no face visible, no three-quarter view. The weapon in the figure's own RIGHT hand appears on the viewer's RIGHT.
FRAMING: the same portrait aspect ratio 3:4 and the same framing as image 1, uniform scale only: pedestal x16.6%-83.4%, pedestal top y84.5%, pedestal bottom y94.0%, highest point
y4.0%. The whole subject and the whole pedestal visible.
BACKGROUND AND LIGHT: plain flat neutral dark charcoal gray background like image 1, no gradient, no vignette, no cast
shadow on the background; soft even studio lighting like image 2, no strong rim light.
Surface detail only, inside the existing silhouette: no new silhouette elements, no added anatomy, do not create a new
weapon; keep thin parts readable.
No perspective, text, labels, watermark, cropping, collage or extra objects. Output one single image.
```

## Проверка и ограничения

Выполнено по одному вызову на вид. По каждому кандидату код 0 (12 PASS), итоговый набор — код 0 (33 PASS); WARN и FAIL нет. Выбранные PNG и лист осмотрены. Стороны рук, котелок, усы, коричневое пальто и кожаная сумка согласованы; back использует выбранный side как третий вход. Кадрирование и фон прошли измерения. Ручка сумки и рука с револьвером видны на левом профиле.

Изменены материалы и живописные детали белых черновых рендеров; сохранены соответствующие виды и позы. Точное геометрическое совпадение не доказано; мелкие швы и фурнитура интерпретированы генератором. Это растровые концепты для рассмотрения, без утверждений о готовности 3D или игры. Ретраев, изменений CORE и обработки PNG не было. Все входы и прежняя история 1a сохранены.

---

# Промпты концепта доктора Ватсона

Дата: 2026-10-13
Инструмент: image_gen (image_gen.imagegen)
Режим: generate. Размер не передавался; аспект 3:4 указан в CORE.

## concepts/dr-watson-design-front-g1.png

prompt_key: 1a/design-front/g1
referenced_image_paths (в порядке вызова, относительно корня репозитория):
1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

При вызове путь раскрыт в абсолютный путь локального файла. Других визуальных входов нет.
CORRECTION: отсутствует.

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Dr. Watson, Holmes's companion: sturdy moustached Victorian gentleman in a bowler hat, brown overcoat and waistcoat, revolver held in his RIGHT hand, medical bag in his LEFT hand.
IDENTITY ANCHORS, each clearly visible: revolver in the figure's own RIGHT hand; medical bag in the LEFT hand; bowler hat; thick moustache.
PALETTE: coat brown #5E4532, bowler black #1F1E1E, waistcoat tan #A08262, accent watch chain gold #C9A24A. These are the main colours plus one accent; no other strong colours.
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

## Проверка и ограничения

Существует только дизайн-front; согласованность между видами не оценивалась. Оригинал image_gen и обе копии совпадают побайтово. Ретраев, изменений CORE и обработки изображения не было.

Все якоря и палитра видны. Верхняя поверхность подставки видна, у левой руки нет ясного просвета от пальто. Скрипт вернул код 2: входной файл отсутствовал после ошибки команды копирования. Копирование восстановлено; новые генерации и финальная проверка не выполнялись по правилу остановки. Автоматический отчёт отсутствует.

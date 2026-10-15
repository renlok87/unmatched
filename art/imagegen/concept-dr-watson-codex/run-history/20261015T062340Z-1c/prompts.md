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

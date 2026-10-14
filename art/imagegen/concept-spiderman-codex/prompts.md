# Промпты ASSET-SPIDERMAN-001, этап 1a

Дата: 2026-10-13.
Инструмент: `image_gen.imagegen` (встроенный).
Режим: генерация нового дизайна по референсу качества.
Вызовов: 1 из 2. Изображений получено: 0.

## design-front g1 — файл не получен

prompt_key: `1a/design-front/g1`.

referenced_image_paths в порядке передачи:
1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`
   (в инструмент передан абсолютный путь `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`).

Точный отправленный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Spider-Man from the Marvel comics (Unmatched: Brains and Brawn): agile masked hero in a red and blue full-body suit with black web lines and a spider emblem on the chest, large white eye lenses, crouched ready pose, one hand raised as if shooting a web.
IDENTITY ANCHORS, each clearly visible: red and blue full-body suit with black web pattern; spider emblem on the chest; white eye lenses; one hand raised in a web-shooting gesture.
PALETTE: suit red #B3202A, suit blue #1F3E8A, web black #151518, accent lens white #EDEDED. These are the main colours plus one accent; no other strong colours.
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

Результат: HTTP 400, `moderation_blocked` на этапе `output`, категория `other`.
ID запроса: `4b6e86c2-12dc-4129-97e5-29c538b9684f`.
Оригинальный путь и путь сохранённого PNG отсутствуют: инструмент не вернул изображение.

## Проверка и ограничения

Запрошен только один фронтальный вид; сопоставление между видами неприменимо. CORE передан без изменений, блока CORRECTION нет. Результат генерации не получен, поэтому визуальная проверка и автопроверка невозможны. Исходный референс и палитра проверены по SHA-256 до и после вызова; изменения отсутствуют.

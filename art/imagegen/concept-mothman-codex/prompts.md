# Промпты ASSET-MOTHMAN-001 — этап 1a

Дата: 2026-10-13.
Инструмент: image_gen, встроенный режим generate.
Вид: design-front. SIDE_VIEW: null (боковой вид не создавался).
Пути referenced_image_paths ниже записаны относительно корня репозитория в порядке передачи; инструменту передавался абсолютный путь этого же файла.

## mothman-design-front-g1.png

Дата: 2026-10-13.
Инструмент: image_gen.
prompt_key: 1a/design-front/g1.
Файл: art/imagegen/concept-mothman-codex/concepts/mothman-design-front-g1.png.
referenced_image_paths:

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Mothman of West Virginia folklore (Unmatched: Tales to Amaze): tall dark humanoid with huge moth wings spread behind it, glowing red eyes, furry grey-brown body and thin clawed limbs.
IDENTITY ANCHORS, each clearly visible: huge moth wings spread behind; glowing red eyes; furry grey-brown body; thin clawed limbs.
PALETTE: fur grey #5E5A56, wing brown #5A4636, wing dark #2A2420, accent eye red #E0302A. These are the main colours plus one accent; no other strong colours.
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

## mothman-design-front-g2.png

Дата: 2026-10-13.
Инструмент: image_gen.
prompt_key: 1a/design-front/g2.
Файл: art/imagegen/concept-mothman-codex/concepts/mothman-design-front-g2.png.
referenced_image_paths:

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Mothman of West Virginia folklore (Unmatched: Tales to Amaze): tall dark humanoid with huge moth wings spread behind it, glowing red eyes, furry grey-brown body and thin clawed limbs.
IDENTITY ANCHORS, each clearly visible: huge moth wings spread behind; glowing red eyes; furry grey-brown body; thin clawed limbs.
PALETTE: fur grey #5E5A56, wing brown #5A4636, wing dark #2A2420, accent eye red #E0302A. These are the main colours plus one accent; no other strong colours.
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
- CHECKLIST strict front orthographic view / edge-on pedestal: a narrow top surface of the pedestal is visible -> show zero top surface; the front edges of both discs must be straight horizontal lines, with the camera at zero elevation.
```

## Проверка и ограничения

Создавался один фронтальный вид; согласованность front/side/back не проверялась. В g1 и g2 совпадают общая идентичность Mothman, серо-коричневая палитра, красные глаза, расправленные крылья и подставка из двух тёмных дисков. Между генерациями инструмент изменил рисунок крыльев, детали головы и опушения, размер подставки и поля кадра; это две независимые генерации, а не правка g1.

В g1 была видна узкая верхняя поверхность подставки, что стало единственной строкой CORRECTION. Выбран g2: верхняя поверхность скрыта. Финальная автопроверка: exit 0, 12 PASS, 1 WARN, 0 FAIL. Допустимый WARN view.frame_top — 3,315% вместо 4%. Визуальный CHECKLIST не полностью выполнен: фон немного темнеет книзу. Лимит 2/2 исчерпан, пункт записан в limit_reached. Дополнительные отклонения рамки и пропорции подставки перечислены в verification.json и README.md. Ретушь и преобразования PNG не выполнялись.

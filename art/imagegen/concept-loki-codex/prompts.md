# Промпты ASSET-LOKI-001, этап 1a

Дата задания: 2026-10-13.
Инструмент: image_gen.imagegen (встроенный).
Режим: generate; transparent_background=false; параметр size не передавался.

## design-front, g1

prompt_key: 1a/design-front/g1.
Планируемый файл: art/imagegen/concept-loki-codex/concepts/loki-design-front-g1.png.
Файл не создан: генерация отклонена на стадии output.

referenced_image_paths, в точном порядке переданного списка:

1. C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Точный переданный prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Loki, the Norse trickster god (Unmatched: Battle of Legends Volume Three): sly lean god with a narrow grinning face, swept-back dark hair, horned headband, green and gold layered robes, a curved dagger in his RIGHT hand, wisps of green magic.
IDENTITY ANCHORS, each clearly visible: curved dagger in the RIGHT hand; horned headband; green and gold robes; sly grin; green magic wisps.
PALETTE: robe green #2F5A3A, gold #C9A24A, hair black #1E1C1E, accent magic green #6FE07A. These are the main colours plus one accent; no other strong colours.
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

CORRECTION: null. Повторного вызова не было.

## Проверка и ограничения

Полученных изображений и выбранной генерации нет, поэтому сравнение видов и визуальный CHECKLIST не выполнены. Запрошен только фронтальный вид; другие виды не создавались. CORE не менялся, дополнительные изображения не передавались. palette.json использован только как текстовый источник заданной палитры.

image_gen вернул HTTP 400, moderation_blocked: отказ системы безопасности на стадии output, категория other. Request ID: 80d9538e-6175-434e-9d99-f97cd3ca1ff2. Исходного файла инструмента нет; побайтовое копирование и check_concept_views.py не выполнялись.

Использован 1 вызов из 2; 0 изображений получено. Лимит CHECKLIST не исчерпан. Продолжение требует устранения отказа инструмента.

# Промпты концепта Mr. Hyde

Дата: 2026-10-13
Инструмент: image_gen.imagegen
Режим: generate; transparent_background=false; размер не передавался.

## 1a/design-front/g1

Планируемый файл: art/imagegen/concept-mr-hyde-codex/concepts/mr-hyde-design-front-g1.png (не создан).
referenced_image_paths, порядок вызова:
1. C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Mr. Hyde: the hulking brutal alter ego, hunched huge torso bursting through a torn grey frock coat and shirt, wild hair, heavy brow, enormous clenched fists held away from the body.
IDENTITY ANCHORS, each clearly visible: huge clenched fists; torn grey frock coat; hunched back; wild hair.
PALETTE: frock grey #5C5E63, skin ruddy #B07A62, torn shirt #D8CFBC, accent bruise purple #6A3A6E. These are the main colours plus one accent; no other strong colours.
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

Результат: HTTP 400, moderation_blocked на этапе output. Request ID: 3c95ac66-e359-4ee5-9f6f-59c50a4674be. Изображение не получено; original_path и saved_path отсутствуют.

## Проверка и ограничения

Запрошен только один фронтальный вид; межвидовое сравнение не применимо. CORE и входы не изменены, CORRECTION не добавлялся. Кандидатов нет, поэтому визуальные признаки, поза, палитра и ортографичность не проверены. check_concept_views.py не запускался. Лимит генераций не исчерпан. Ошибка инструмента и недостигнутые требования отражены в verification.json.

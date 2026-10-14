# Промпты Blackbeard — 1a

Дата: 2026-10-13.
Инструмент: `image_gen`; режим: `generate`; прозрачный фон: false; размер не передавался.

## concepts/blackbeard-design-front-g1.png

prompt_key: `1a/design-front/g1`.
referenced_image_paths в порядке вызова (пути от корня репозитория, в API переданы их абсолютные разрешённые пути):

1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png` — только эталон качества изготовления и росписи.

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Blackbeard the pirate captain: tall menacing man with a huge braided black beard tied with ribbons, black tricorn hat, long dark red coat over a waistcoat, bandolier with pistols across the chest, tall boots; cutlass in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: cutlass in the figure's own RIGHT hand; braided black beard with ribbons; tricorn hat; pistol bandolier across the chest.
PALETTE: coat red #7A1F1F, pitch black #1E1C1C, brass #B08A3E, accent ribbon scarlet #C8322A. These are the main colours plus one accent; no other strong colours.
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

Создан только один вид — design-front; межвидовое соответствие на этапе 1a не оценивается. Коррекция не добавлялась, CORE не менялся. Ничего в сгенерированном изображении не изменялось: сохранены только побайтные копии.

Кандидат g1 и выбранный финал: код 0, 12 PASS, 1 WARN, 0 FAIL. Визуальный CHECKLIST: 6 из 6. Верхняя точка 2,693% вместо 4% отмечена как WARN view.frame_top; по заданию ретрай не выполнялся. Все якоря и палитра читаются. Камера оценена визуально; её внутренние параметры недоступны. Статус пакета — предложено.

# Промпты концепта Донателло — этап 1a

Дата: 2026-10-13. Инструмент: image_gen. Режим: generate с референсом качества.
Размер не передавался; аспект 3:4 указан только в CORE.
## concepts/donatello-design-front-g1.png

Date: 2026-10-13. tool: image_gen. mode: generate. prompt_key: 1a/design-front/g1.

referenced_image_paths (call order; repository-relative):

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png - sha256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Donatello from Teenage Mutant Ninja Turtles (Unmatched: Adventures TMNT): humanoid ninja turtle with green skin, brown shell, purple eye mask, belt with pouches and knee pads, long wooden bo staff held in both hands across the body.
IDENTITY ANCHORS, each clearly visible: long wooden bo staff held in both hands; purple eye mask with tails; brown shell on the back; belt with pouches and knee pads.
PALETTE: skin green #4E8A3A, shell brown #6E5236, mask purple #6A3FA0, accent staff wood #9B7448. These are the main colours plus one accent; no other strong colours.
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

## concepts/donatello-design-front-g2.png

Date: 2026-10-13. tool: image_gen. mode: generate. prompt_key: 1a/design-front/g2.

referenced_image_paths (call order; repository-relative):

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png - sha256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Donatello from Teenage Mutant Ninja Turtles (Unmatched: Adventures TMNT): humanoid ninja turtle with green skin, brown shell, purple eye mask, belt with pouches and knee pads, long wooden bo staff held in both hands across the body.
IDENTITY ANCHORS, each clearly visible: long wooden bo staff held in both hands; purple eye mask with tails; brown shell on the back; belt with pouches and knee pads.
PALETTE: skin green #4E8A3A, shell brown #6E5236, mask purple #6A3FA0, accent staff wood #9B7448. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level: the pedestal shows an exposed curved top surface -> use a true zero-elevation front orthographic projection with only its edge-on vertical faces visible and a straight horizontal front edge.
```

## Проверка и ограничения

Создан только design-front этапа 1a; side/back отсутствуют, согласованность между видами не оценивается. Между кандидатами сохраняются Донателло, зелёная кожа, коричневый спинной панцирь, фиолетовая маска с хвостами, посох в двух руках, пояс с подсумками, наколенники и двухъярусная тёмная подставка.

g2 исправляет видимую верхнюю площадку подставки; одновременно изменились наклон посоха, сгиб руки слева в кадре, детали ремней и фактура росписи. CORE не изменялся; добавлен только один пункт CORRECTION. Выбран g2. Финальный скрипт: exit 0, 12 PASS, 1 WARN (view.single_component), 0 FAIL.

Не выполнен пункт “No weapon or held object.”: он противоречит обязательному якорю “long wooden bo staff held in both hands”. Полный просвет обеих рук от торса не подтверждён слева в кадре. Лимит 2/2 исчерпан, эти замечания переданы приёмщику через verification.json → limit_reached.

База измерена по x48,665%, низ по y94,751%; требуемые x50% и y93% не достигнуты точно. Визуальный диаметр подставки около 0,7 высоты фигуры, больше ориентира ≈0,55. Все ограничения перечислены в verification.json. Результаты не ретушировались, не масштабировались, не обрезались и не перекодировались; оригиналы и копии совпадают по SHA-256.

# Промпты Michelangelo, этап 1a

Дата: 2026-10-13. Инструмент: встроенный `image_gen`. Режим: generate. Medusa — только craftsmanship reference. Размер не передавался, аспект 3:4 указан в CORE; `transparent_background=false`.

Пути входов ниже относительны корню репозитория; инструмент получил соответствующий абсолютный локальный путь. Предыдущие кандидаты, коммерческие материалы и другие изображения входами не были.

## concepts/michelangelo-design-front-g1.png

Дата: 2026-10-13T07:43:31+00:00. Инструмент: image_gen. prompt_key: `1a/design-front/g1`. correction: null.

referenced_image_paths, в порядке вызова:
1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`, SHA-256 `e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9` — эталон мастерства.

Точный prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Michelangelo from Teenage Mutant Ninja Turtles (Unmatched: Adventures TMNT): cheerful humanoid ninja turtle with green skin, brown shell, orange eye mask, belt and knee pads, a nunchaku in each hand, grinning.
IDENTITY ANCHORS, each clearly visible: a nunchaku in each hand; orange eye mask with tails; brown shell on the back; grinning face.
PALETTE: skin green #5A9440, shell brown #6E5236, mask orange #E07A22, accent chain steel #B8BEC4. These are the main colours plus one accent; no other strong colours.
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

## concepts/michelangelo-design-front-g2.png

Дата: 2026-10-13T07:45:17+00:00. Инструмент: image_gen. prompt_key: `1a/design-front/g2`.

referenced_image_paths, в порядке вызова:
1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`, SHA-256 `e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9` — эталон мастерства.

Точный prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Michelangelo from Teenage Mutant Ninja Turtles (Unmatched: Adventures TMNT): cheerful humanoid ninja turtle with green skin, brown shell, orange eye mask, belt and knee pads, a nunchaku in each hand, grinning.
IDENTITY ANCHORS, each clearly visible: a nunchaku in each hand; orange eye mask with tails; brown shell on the back; grinning face.
PALETTE: skin green #5A9440, shell brown #6E5236, mask orange #E07A22, accent chain steel #B8BEC4. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: the pedestal top is visible and its front edge curves -> show only two shallow vertical disc faces with straight horizontal edges, hiding every part of the top surface.
- the whole subject and pedestal visible, nothing cropped; plain flat dark gray background: background tone varies behind the figure -> use one uniform flat charcoal gray everywhere outside the silhouette, with no gradient or halo.
```

## Проверка и ограничения

Создан только design-front. Бокового и заднего видов ещё нет; межвидовая согласованность не заявляется. Между g1 и g2 сохранены одна фигура, зелёная кожа, коричневый спинной панцирь, оранжевая маска, улыбка, нунчаки в обеих руках со стальными цепями, нейтральная стойка с зазорами у рук и двухъярусная тёмная подставка.

У g2 скрыта верхняя поверхность подставки, границы выпрямлены и фон выровнен. Побочные изменения: хвосты маски переместились слева направо в кадре; изменились ремни, пряжка пояса, форма грудных пластин, обмотки рукоятей, детали кистей, стоп и пропорции фигуры. g1 не был входом g2: повтор использовал CORE и тот же единственный эталон.

g1: exit 0, 13 PASS, 0 WARN, 0 FAIL; визуально провалены ракурс подставки, ровный фон и конфликтующий запрет предметов. g2 и финальный прогон: exit 0, 12 PASS, 1 WARN, 0 FAIL. WARN `view.single_component` разрешён; визуально нет второго субъекта. CHECKLIST g2 имеет один failed: запрет предметов несовместим с обязательными нунчаками. После 2/2 генераций пункт передан приёмщику через `limit_reached`.

Диаметр подставки g2 относительно фигуры оценивается примерно в 0.747, тогда как CORE задаёт около 0,55. Отклонение записано отдельно в `verification.json`. Все изображения сохранены побайтно без правок; оригиналы на месте. Хэши входов проверены до и после.

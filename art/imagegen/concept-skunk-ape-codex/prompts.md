# ASSET-SKUNK-APE-001: промпты дизайна 1a

Дата: 2026-10-13.
Инструмент: image_gen, mode: edit; один вызов — одно изображение.
Единственный референс в каждом вызове — эталон мастерства Medusa. Пути ниже указаны относительно корня репозитория; инструменту передан тот же файл по абсолютному пути.

## design-front, g1

Файл: `art/imagegen/concept-skunk-ape-codex/concepts/skunk-ape-design-front-g1.png`.
prompt_key: `1a/design-front/g1`.

referenced_image_paths, в порядке вызова:

1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Skunk Ape of Florida folklore (Unmatched: Tales to Amaze): tall hunched ape-like creature with shaggy matted dark fur streaked with swamp moss, long arms and big feet.
IDENTITY ANCHORS, each clearly visible: tall hunched ape body; shaggy matted fur with swamp moss; long arms; big feet.
PALETTE: fur dark #3E3228, moss green #5E6A36, skin grey #6A625A, accent eye amber #D9962A. These are the main colours plus one accent; no other strong colours.
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

## design-front, g2 — выбран

Файл: `art/imagegen/concept-skunk-ape-codex/concepts/skunk-ape-design-front-g2.png`.
prompt_key: `1a/design-front/g2`.

referenced_image_paths, в порядке вызова:

1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Skunk Ape of Florida folklore (Unmatched: Tales to Amaze): tall hunched ape-like creature with shaggy matted dark fur streaked with swamp moss, long arms and big feet.
IDENTITY ANCHORS, each clearly visible: tall hunched ape body; shaggy matted fur with swamp moss; long arms; big feet.
PALETTE: fur dark #3E3228, moss green #5E6A36, skin grey #6A625A, accent eye amber #D9962A. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: a narrow strip of the pedestal top is visible -> show only the two stacked disc sidewalls, with a straight horizontal top/front edge and absolutely no visible top surface or ellipse.
- the whole subject and pedestal visible, nothing cropped; plain flat dark gray background: the background shows a visible brightness gradient -> use one uniform neutral dark gray across the entire background, with no gradient or vignette.
```

## Проверка и ограничения

Сгенерирован только design-front этапа 1a; бокового и заднего видов нет, согласованность между видами здесь не проверяется.
В обеих генерациях сохранены обезьяноподобная анатомия, длинные руки, крупные стопы, мох на спутанной шерсти, палитра и пустые кисти.
В g2 исправлен вид подставки: её верхняя поверхность скрыта; фон стал ровнее. Изменились рисунок шерсти и мха, пропорции корпуса и мелкие детали лица — g2 не является ретушью g1.
Все три прогона check_concept_views.py завершились кодом 0; финал: 11 PASS, 2 WARN, 0 FAIL.
WARN выбранного файла: view.frame_top (2,486% вместо минимум 4%) и view.single_component (дополнительная компонента маски 1,118%).
Низ маски находится на y96,133% вместо заданных y93%; центр подставки x49,770%.
WARN не стали причиной повторной генерации. Повтор сделан из-за визуальных пунктов о верхней поверхности подставки и ровном фоне.
Шесть пунктов CHECKLIST выбранного g2 выполнены по визуальному осмотру; это предложение для внешней приёмки, без художественного вердикта.
Генерации не изменялись и не пересохранялись; все копии PNG побайтовые, исходные файлы инструмента сохранены.

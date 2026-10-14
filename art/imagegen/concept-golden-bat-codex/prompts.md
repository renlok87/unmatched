# Точные промпты Golden Bat — этап 1a

Дата: 2026-10-13. Инструмент: image_gen. Режим: generate — новый дизайн с эталоном качества. transparent_background=false. Размер не передавался; портретный аспект 3:4 задан только текстом CORE.

referenced_image_paths перечислены в порядке вызова относительно корня репозитория. Инструменту передан абсолютный путь соответствующего файла.

## art/imagegen/concept-golden-bat-codex/concepts/golden-bat-design-front-g1.png

Дата: 2026-10-13. Инструмент: image_gen. prompt_key: `1a/design-front/g1`.
referenced_image_paths:
1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png` — только уровень изготовления и покраски.

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Golden Bat, the 1930s Japanese kamishibai hero (Unmatched: Tales to Amaze): golden skull-faced caped superhero in a dark red cloak with a high collar, golden body, ornate rapier-like staff in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: golden skull face; dark red high-collared cape; golden body; ornate staff in the RIGHT hand.
PALETTE: gold #D4AE45, cape red #7A1F24, cape lining black #1E1A1C, accent gem green #3FA74A. These are the main colours plus one accent; no other strong colours.
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

## art/imagegen/concept-golden-bat-codex/concepts/golden-bat-design-front-g2.png

Дата: 2026-10-13. Инструмент: image_gen. prompt_key: `1a/design-front/g2`.
referenced_image_paths:
1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png` — только уровень изготовления и покраски.

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Golden Bat, the 1930s Japanese kamishibai hero (Unmatched: Tales to Amaze): golden skull-faced caped superhero in a dark red cloak with a high collar, golden body, ornate rapier-like staff in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: golden skull face; dark red high-collared cape; golden body; ornate staff in the RIGHT hand.
PALETTE: gold #D4AE45, cape red #7A1F24, cape lining black #1E1A1C, accent gem green #3FA74A. These are the main colours plus one accent; no other strong colours.
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
CORRECTION (fix only this; everything above still applies):
- CHECKLIST item 2 (strict front orthographic view): a narrow top surface of the pedestal is visible and its front edge curves -> show both discs exactly edge-on with straight horizontal front edges and no visible top surface.
- CHECKLIST item 1 (no logo): bat-shaped insignias on the cape clasps and belt buckle read as logos -> replace these insignias with plain non-symbolic ornamental scrollwork.
```

## Проверка и ограничения

Создан только design-front; боковой и задний виды на этапе 1a не создавались, согласованность разных видов не проверяется. Между попытками сохранены золотой череп и тело, тёмно-красный высокий воротник, чёрная подкладка, зелёный акцент, посох в собственной правой руке, нейтральная стойка и одна подставка.

В g2 исправлены верхняя площадка подставки и эмблемы застёжек/пряжки; CORE не менялся. Инструмент также изменил детали скульптуры, навершие посоха и складки плаща. Обе генерации сохранены без обработки.

Каждый кандидат проверен в своём каталоге. Выбран g2; финальный код 0 (12 PASS, 1 WARN, 0 FAIL). Все пункты CHECKLIST пройдены визуально. WARN view.frame_top: y=3,177% вместо ≥4%; обрезки нет. Подставка шире ориентира CORE (визуально около 0,64 роста вместо около 0,55). Отклонения записаны в verification.json. Использовано 2/2 генерации. Статус «предложено».

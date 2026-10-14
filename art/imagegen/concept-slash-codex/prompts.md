# Точные промпты ASSET-SLASH-001, этап 1a

Дата: 2026-10-13.
Инструмент: image_gen (встроенный image_gen.imagegen); режим generate.
Единственный вход изображения — эталон мастерства. palette.json является текстовым входом.
referenced_image_paths ниже указаны относительно корня репозитория, в порядке вызова; инструмент получил разрешённый абсолютный путь того же файла.
Размер в параметрах вызова не задавался; аспект 3:4 указан только в CORE. transparent_background: false.

## art/imagegen/concept-slash-codex/concepts/slash-design-front-g1.png

Date: 2026-10-13
Tool: image_gen
prompt_key: 1a/design-front/g1
referenced_image_paths (call order):
1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Slash from Teenage Mutant Ninja Turtles (Unmatched: Adventures TMNT): hulking evil mutant turtle with dark green skin, spiked black shell, black eye mask, spiked mace in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: spiked mace in the RIGHT hand; spiked black shell; black eye mask.
PALETTE: skin dark green #2F4A2A, shell black #1E1C1C, mask black #141414, accent spike steel #9AA1A7. These are the main colours plus one accent; no other strong colours.
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

## art/imagegen/concept-slash-codex/concepts/slash-design-front-g2.png

Date: 2026-10-13
Tool: image_gen
prompt_key: 1a/design-front/g2
referenced_image_paths (call order):
1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Slash from Teenage Mutant Ninja Turtles (Unmatched: Adventures TMNT): hulking evil mutant turtle with dark green skin, spiked black shell, black eye mask, spiked mace in his RIGHT hand.
IDENTITY ANCHORS, each clearly visible: spiked mace in the RIGHT hand; spiked black shell; black eye mask.
PALETTE: skin dark green #2F4A2A, shell black #1E1C1C, mask black #141414, accent spike steel #9AA1A7. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: the pedestal's top surface is visible and its upper contour curves -> show the pedestal exactly edge-on with zero visible top surface and a straight horizontal front edge.
```

## Проверка и ограничения

Выполнен один вид design-front; согласованность между разными видами ещё не проверялась. Между g1 и g2 совпадают персонаж, булава в собственной правой руке (слева для зрителя), чёрный шипованный панцирь, чёрная маска, зелёная кожа, стальные шипы, нейтральная стойка, один субъект, тёмно-серый фон, размер и аспект.

CORRECTION второй генерации требовала только скрыть верх подставки и выпрямить передний край. Это исправлено. При независимой генерации также изменились ремни (перекрёстные в g1, диагональный в g2), пояс, лоскуты ткани, детали маски и шипов; подставка теперь читается как один диск. Эти изменения не добавлялись в промпт.

g1: скрипт 0, визуальный пункт о ракурсе подставки не пройден. g2: скрипт 0 с WARN view.single_component; все шесть пунктов CHECKLIST пройдены. Финальная проверка g2 без --out: код 0.

Не достигнуты все детали CORE: два диска, приблизительный диаметр 0.55 роста, точные x50%/y93% и строго ограниченная палитра без дополнительного бежевого пластрона. Ограничения записаны в verification.json и README.md. Успешный код скрипта не является внешней приёмкой. PNG не редактировались.

# Промпты концепта Rat King — этап 1a

Дата: 2026-10-13.
Инструмент: image_gen.imagegen, режим generate с единственным эталоном качества.
Размер инструменту не передавался; аспект 3:4 задан только в тексте CORE.
Пути referenced_image_paths ниже записаны относительно корня репозитория в порядке передачи инструменту.
Палитра прочитана из palette.json и не передавалась как изображение.

## art/imagegen/concept-rat-king-codex/concepts/rat-king-design-front-g1.png

Дата: 2026-10-13.
Инструмент: image_gen.imagegen.
prompt_key: 1a/design-front/g1.
referenced_image_paths, в порядке вызова:

1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Rat King from Teenage Mutant Ninja Turtles (Unmatched: Adventures TMNT): gaunt sinister man wrapped in ragged grey bandages and a hooded cloak, a crooked staff in his RIGHT hand, two rats on his shoulders.
IDENTITY ANCHORS, each clearly visible: crooked staff in the RIGHT hand; ragged bandage wrappings; hooded cloak; rats on the shoulders.
PALETTE: bandage grey #8C8A82, cloak brown #4E3E30, rat grey #6A6660, accent eye red #B2342C. These are the main colours plus one accent; no other strong colours.
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

## art/imagegen/concept-rat-king-codex/concepts/rat-king-design-front-g2.png

Дата: 2026-10-13.
Инструмент: image_gen.imagegen.
prompt_key: 1a/design-front/g2.
referenced_image_paths, в порядке вызова:

1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Rat King from Teenage Mutant Ninja Turtles (Unmatched: Adventures TMNT): gaunt sinister man wrapped in ragged grey bandages and a hooded cloak, a crooked staff in his RIGHT hand, two rats on his shoulders.
IDENTITY ANCHORS, each clearly visible: crooked staff in the RIGHT hand; ragged bandage wrappings; hooded cloak; rats on the shoulders.
PALETTE: bandage grey #8C8A82, cloak brown #4E3E30, rat grey #6A6660, accent eye red #B2342C. These are the main colours plus one accent; no other strong colours.
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
- CHECKLIST: strict front orthographic view: the pedestal top is visible as an ellipse -> use zero-elevation orthographic projection; show both pedestal discs strictly edge-on, no visible top plane, with a straight horizontal front edge.
```

## Проверка и ограничения

Сделан только один вид design-front. Бокового и заднего видов нет, согласованность между видами на этапе 1a не заявляется.

Между g1 и g2 совпадают ключевые признаки: посох в собственной правой руке (слева для зрителя), рваные серые бинты, коричневый плащ с капюшоном, две серые крысы на плечах, красный акцент глаз и одна тёмная подставка из двух ступеней. Обе руки отделены от корпуса; A/T-позы нет. В g2 верхняя плоскость подставки скрыта и её передние кромки горизонтальны — поэтому выбран g2. При повторной генерации изменились складки, обмотки, форма посоха и положение крыс; на посохе появился декоративный череп, которого задание не просило. Эта деталь отмечена в verification.json для приёмщика.

CORE в двух вызовах дословно одинаков. В g2 добавлен один CORRECTION-пункт только по проваленному пункту CHECKLIST о фронтальной ортографии и подставке. g1 не выбран из-за видимого верха подставки. Скрипт у обоих кандидатов и в финальном прогоне вернул 0: 12 PASS, 1 WARN, 0 FAIL. Единственный WARN view.frame_top: g1 — 2,141 %, g2 — 2,762 % при минимуме 4 %. WARN не использовался как основание для ретрая. У g2 низ подставки на y=92,956 %, центр x=49,954 %. Все шесть выбранных пунктов CHECKLIST проходят по визуальному осмотру.

Использованы 2 из 2 разрешённых генераций. Изображения скопированы побайтно, без ретуши, обрезки, ресайза, перекраски и пересохранения. Оба tool-оригинала оставлены на месте. Автопроверки и визуальный CHECKLIST не заменяют внешнюю художественную приёмку; статус пакета — «предложено».

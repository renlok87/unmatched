# ASSET-SHREDDER-001 — промпты дизайна front, этап 1a

Дата: 2026-10-13.
Инструмент: image_gen.imagegen; режим: generate с референсом качества.
Один вызов — один PNG и один вид. Размер не передавался; аспект 3:4 задан текстом CORE.

## shredder-design-front-g1.png

prompt_key: `1a/design-front/g1`
referenced_image_paths в точном порядке вызова:

```json
[
  "C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
]
```

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Shredder from Teenage Mutant Ninja Turtles (Unmatched: TMNT Shredder vs Krang): menacing ninja master in steel bladed armour over a dark purple robe, horned helmet with a face mask, bladed gauntlets on both forearms, long cape.
IDENTITY ANCHORS, each clearly visible: bladed steel gauntlets on both forearms; horned helmet with face mask; dark purple robe; long cape.
PALETTE: steel #9AA1A7, robe purple #3E2450, cape maroon #5E1F2A, accent eye red #C8322A. These are the main colours plus one accent; no other strong colours.
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

## shredder-design-front-g2.png

prompt_key: `1a/design-front/g2`
referenced_image_paths в точном порядке вызова:

```json
[
  "C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
]
```

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Shredder from Teenage Mutant Ninja Turtles (Unmatched: TMNT Shredder vs Krang): menacing ninja master in steel bladed armour over a dark purple robe, horned helmet with a face mask, bladed gauntlets on both forearms, long cape.
IDENTITY ANCHORS, each clearly visible: bladed steel gauntlets on both forearms; horned helmet with face mask; dark purple robe; long cape.
PALETTE: steel #9AA1A7, robe purple #3E2450, cape maroon #5E1F2A, accent eye red #C8322A. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: the pedestal top is visible as a narrow oval -> show only the vertical front faces of both discs with perfectly horizontal top edges and no visible top surface.
- the whole subject and pedestal visible, nothing cropped; plain flat dark gray background: the background has a gradient/vignette -> use one uniform neutral dark gray tone across the entire background.
```

## Проверка и ограничения

Этот запуск содержит один вид design-front, две генерации. Согласованность разных ракурсов на этапе 1a ещё не проверяется. Между g1 и g2 сохранены фронтальная поза, пустые кисти, оба лезвийных наруча, рогатый шлем с маской, фиолетовое одеяние, бордовый длинный плащ и красные глаза.

В g2 верх подставки скрыт, её кромки горизонтальны; плащ получил более цельную нижнюю кромку. Также изменились рисунок нагрудной и набедренной брони и детализация перчаток. CORE передан неизменно; добавлен только двухстрочный CORRECTION.

Все три запуска check_concept_views.py завершились кодом 0. У g2 и итоговой копии: WARN view.frame_top (2.21% вместо минимум 4%) и WARN view.single_component (вторичная компонента маски 1.71%). Визуально показаны одна фигура и одна подставка. Низ маски — 94.613% вместо заданных 93%, центр подставки — 50%. Ограничения сохранены в verification.json. Исходные PNG копировались побайтно, оригиналы image_gen сохранены по путям generation-records.json.

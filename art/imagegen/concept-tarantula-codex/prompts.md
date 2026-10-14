# ASSET-TARANTULA-001 concept 1a

Date: 2026-10-13
Tool: image_gen.imagegen
Mode: generate

## art/imagegen/concept-tarantula-codex/concepts/tarantula-design-front-g1.png

Date: 2026-10-13T08:16:28+00:00
Tool: image_gen.imagegen
Prompt key: 1a/design-front/g1
referenced_image_paths (call order; repository-relative):
```json
[
  "art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
]
```

Exact prompt:
```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The giant Tarantula, a pulp-era monster (Unmatched: Tales to Amaze): huge hairy spider with eight thick legs, dark brown body with orange leg bands, glossy black eyes and fangs.
IDENTITY ANCHORS, each clearly visible: huge hairy spider; eight thick legs with orange bands; glossy black eyes; fangs.
PALETTE: hair brown #4A3626, band orange #C8742A, body dark #2A2018, accent eye black #0E0E10. These are the main colours plus one accent; no other strong colours.
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

## art/imagegen/concept-tarantula-codex/concepts/tarantula-design-front-g2.png

Date: 2026-10-13T08:18:25+00:00
Tool: image_gen.imagegen
Prompt key: 1a/design-front/g2
referenced_image_paths (call order; repository-relative):
```json
[
  "art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
]
```

Exact prompt:
```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The giant Tarantula, a pulp-era monster (Unmatched: Tales to Amaze): huge hairy spider with eight thick legs, dark brown body with orange leg bands, glossy black eyes and fangs.
IDENTITY ANCHORS, each clearly visible: huge hairy spider; eight thick legs with orange bands; glossy black eyes; fangs.
PALETTE: hair brown #4A3626, band orange #C8742A, body dark #2A2018, accent eye black #0E0E10. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view: the pedestal shows a narrow top surface and curved front edges -> show both stacked discs exactly edge-on with no visible top surface and straight horizontal front edges.
```

## Проверка и ограничения

Сделан только design-front этапа 1a: сопоставимость front/side/back пока не проверялась. Между g1 и g2 сохранены общий фронтальный сюжет, волосатое коричневое тело, оранжевые полосы, чёрные глаза, клыки, две ступени тёмной подставки и аспект 3:4. g2 выпрямил кромки подставки и убрал её видимый верх, но изменил переднюю пару ног: она стала короткой и без полос. Поэтому выбран g1. Строгая ортография подставки у g1 остаётся непройденной; лимит 2/2 исчерпан. Дополнительные расхождения CORE: низ подставки y90,608 % вместо y93 %, диаметр около 0,92 высоты паука вместо около 0,55, равномерная опора всех видимых концов ног не подтверждена. Проверки кандидатов и выбранного файла: код 0, 13 PASS, без WARN/FAIL. Входные изображения не менялись; оба сгенерированных PNG сохранены побайтно. Решение о приёмке остаётся за приёмщиком.

# ASSET-INVISIBLE-MAN-001 concept 1a

Date: 2026-10-13
Tool: image_gen.imagegen

## art/imagegen/concept-invisible-man-codex/concepts/invisible-man-design-front-g1.png

referenced_image_paths (call order; repository-relative):
[
  "art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
]

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Invisible Man: a man whose head is completely wrapped in white bandages, dark round goggles, false nose, brown overcoat with raised collar, gloves and a hat; an empty space where the neck shows between collar and bandages.
IDENTITY ANCHORS, each clearly visible: head wrapped in bandages; dark round goggles; brown overcoat with raised collar; brimmed hat.
PALETTE: bandage white #E3DED2, coat brown #5E4632, goggle black #1C1C1E, accent glove tan #B48A5A. These are the main colours plus one accent; no other strong colours.
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

## art/imagegen/concept-invisible-man-codex/concepts/invisible-man-design-front-g2.png

referenced_image_paths (call order; repository-relative):
[
  "art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
]

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Invisible Man: a man whose head is completely wrapped in white bandages, dark round goggles, false nose, brown overcoat with raised collar, gloves and a hat; an empty space where the neck shows between collar and bandages.
IDENTITY ANCHORS, each clearly visible: head wrapped in bandages; dark round goggles; brown overcoat with raised collar; brimmed hat.
PALETTE: bandage white #E3DED2, coat brown #5E4632, goggle black #1C1C1E, accent glove tan #B48A5A. These are the main colours plus one accent; no other strong colours.
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
- CHECKLIST strict front orthographic view: the pedestal top surface is visible and its front edge is curved -> show the pedestal exactly edge-on, with no visible top surface and a straight horizontal front edge; keep strict front orthographic projection and zero camera elevation.
```

## Проверка и ограничения

Создан только design-front; межвидовое совпадение не применимо. CORE одинаков в обеих генерациях; g2 добавляет одну строку CORRECTION. Между g1 и g2 изменились отображение подставки, форма и детализация одежды, накладной нос и галстук; обе генерации независимы и используют только эталон мастерства. Палитра и четыре якоря идентичности сохранены.

Оба кандидата и финальный g2: код 0, 12 PASS, 1 WARN, 0 FAIL. g1 визуально не прошёл пункт ортографической проекции из-за видимой верхней плоскости подставки. g2 визуально проходит все шесть пунктов CHECKLIST. Верхний отступ g2 2,21% вместо 4% — разрешённый WARN view.frame_top. Изображения не ретушировались, не обрезались и не пересохранялись. Побайтовые копии и входы проверены по SHA-256. Статус предложено; художественная приёмка не выполнялась.

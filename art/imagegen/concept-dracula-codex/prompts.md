# Dracula prompts 1a

Date: 2026-10-13
Tool: image_gen; mode: text-to-image

## art/imagegen/concept-dracula-codex/concepts/dracula-design-front-g1.png

prompt_key: 1a/design-front/g1

referenced_image_paths (in call order):
- art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png (sha256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9)

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Count Dracula: tall elegant aristocratic vampire with slicked-back black hair and pale face, high-collared black cape with crimson lining, dark formal suit with a medallion on a red ribbon, both hands open with long fingers.
IDENTITY ANCHORS, each clearly visible: high-collared black cape with crimson lining; medallion on a red ribbon; slicked-back hair; pale face.
PALETTE: night black #1A1719, crimson #8E1B24, pale skin #D8D2C8, accent gold medallion #C8A040. These are the main colours plus one accent; no other strong colours.
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

## art/imagegen/concept-dracula-codex/concepts/dracula-design-front-g2.png

prompt_key: 1a/design-front/g2

referenced_image_paths (in call order):
- art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png (sha256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9)

Exact prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Count Dracula: tall elegant aristocratic vampire with slicked-back black hair and pale face, high-collared black cape with crimson lining, dark formal suit with a medallion on a red ribbon, both hands open with long fingers.
IDENTITY ANCHORS, each clearly visible: high-collared black cape with crimson lining; medallion on a red ribbon; slicked-back hair; pale face.
PALETTE: night black #1A1719, crimson #8E1B24, pale skin #D8D2C8, accent gold medallion #C8A040. These are the main colours plus one accent; no other strong colours.
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
- CHECKLIST strict front orthographic view: the pedestal top surface is visible and its front edge curves -> hide the top surface entirely and make the front edge a straight horizontal line, with zero camera elevation.
- CHECKLIST whole subject visible; plain flat dark gray background: the background varies in brightness -> use one uniform dark charcoal gray across the entire background, without any gradient or vignette.
- CHECKLIST both arms clearly apart from the torso: the cape fills the gaps between each arm and the body -> keep the high-collared cape and neutral bent elbows, but leave a clearly visible open gap between each arm and the torso.
```

## Проверка и ограничения

На этапе 1a создан только design-front; согласованность front/side/back не оценивалась. Между g1 и g2 сохранены персонаж, палитра, все четыре якоря, открытые кисти и двухъярусная каменная подставка. Изменились складки плаща, детали костюма, пальцы и геометрия подставки.

g2 выбран как более близкий к фронтальному виду подставки. Все проверки: 0 FAIL и один разрешённый WARN view.frame_top. У g2 остаются узкая видимая верхняя поверхность подставки и закрытые плащом просветы у рук; это отмечено в CHECKLIST и limit_reached. Фон визуально ровный, со слабым шумом. Пиксели не редактировались.

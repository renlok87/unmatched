# Точные промпты — Bess Houdini, этап 1a

## 2026-10-13T03:35:39.235685+00:00 — image_gen.imagegen — art/imagegen/concept-bess-houdini-codex/concepts/bess-houdini-design-front-g1.png

referenced_image_paths (порядок вызова):
- art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

prompt_key: 1a/design-front/g1

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Bess Houdini, stage assistant of the escape artist: petite woman in a 1910s stage costume, short bob hair, sequined jacket over a knee-length skirt, holding a large key ring in her RIGHT hand.
IDENTITY ANCHORS, each clearly visible: large key ring in the RIGHT hand; sequined jacket; bob haircut; stage heels.
PALETTE: stage black #1C1C20, sequin silver #B8BEC4, skirt plum #6A2E4F, accent key brass #C2963E. These are the main colours plus one accent; no other strong colours.
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

## 2026-10-13T03:36:34.593637+00:00 — image_gen.imagegen — art/imagegen/concept-bess-houdini-codex/concepts/bess-houdini-design-front-g2.png

referenced_image_paths (порядок вызова):
- art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

prompt_key: 1a/design-front/g2

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Bess Houdini, stage assistant of the escape artist: petite woman in a 1910s stage costume, short bob hair, sequined jacket over a knee-length skirt, holding a large key ring in her RIGHT hand.
IDENTITY ANCHORS, each clearly visible: large key ring in the RIGHT hand; sequined jacket; bob haircut; stage heels.
PALETTE: stage black #1C1C20, sequin silver #B8BEC4, skirt plum #6A2E4F, accent key brass #C2963E. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: the pedestal top is visible and its front edge curves -> show both discs exactly edge-on with zero visible top surface and a straight horizontal front edge.
- the whole subject and pedestal visible, nothing cropped; plain flat dark gray background: the background has uneven illumination and a vignette -> use a completely flat uniform dark gray background with no gradient or vignette.
```

## Проверка и ограничения

Сгенерирован только один вид design-front; сопоставления front/side/back на этапе 1a нет. Между g1 и g2 сохранены основные признаки: связка ключей в собственной правой руке, каре, серебряные пайетки, сливовая юбка, чёрные туфли и двухъярусная каменная подставка. В g2 изменены ракурс подставки, детали костюма и причёски (добавлено перо), положение рук; улучшен воспринимаемый фон. Это отдельная генерация, не ретушь g1. CORE неизменен; только g2 содержит CORRECTION из двух строк: ракурс подставки и ровный фон. WARN по верхнему полю не был причиной повторной генерации. Все проверки скрипта вернули 0; буквальный запрет удерживаемого предмета несовместим с обязательными ключами и отмечен failed. Лимит 2/2 исчерпан, выбран g2, статус «предложено».

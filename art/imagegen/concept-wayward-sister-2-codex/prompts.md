# Промпты ASSET-WAYWARD-SISTER-2-001 — этап 1a

Date: 2026-10-13
Tool: image_gen.imagegen
Mode: generate

## art/imagegen/concept-wayward-sister-2-codex/concepts/wayward-sister-2-design-front-g1.png

prompt_key: 1a/design-front/g1
referenced_image_paths (call order):
1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The second wayward sister, a tall gaunt witch with a long hooked nose, tattered grey-green robes and a cord belt with herb bundles, holding a gnarled wand in her LEFT hand.
IDENTITY ANCHORS, each clearly visible: gnarled wand in the figure's own LEFT hand; herb bundles on a cord belt; tattered grey-green robes.
PALETTE: robe grey-green #5F6A55, heath brown #4E3F30, bone white #D6CDB8, accent eerie violet #8A4FB8. These are the main colours plus one accent; no other strong colours.
POSE: Neutral standing pose of a tabletop miniature: both feet planted on the pedestal, weight even, both arms held slightly away from the torso with a visible gap between each arm and the body, elbows slightly bent; not a T-pose and not an A-pose. The weapon is held in the figure's own LEFT hand, which appears on the viewer's RIGHT in the front view.
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

## art/imagegen/concept-wayward-sister-2-codex/concepts/wayward-sister-2-design-front-g2.png

prompt_key: 1a/design-front/g2
referenced_image_paths (call order):
1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The second wayward sister, a tall gaunt witch with a long hooked nose, tattered grey-green robes and a cord belt with herb bundles, holding a gnarled wand in her LEFT hand.
IDENTITY ANCHORS, each clearly visible: gnarled wand in the figure's own LEFT hand; herb bundles on a cord belt; tattered grey-green robes.
PALETTE: robe grey-green #5F6A55, heath brown #4E3F30, bone white #D6CDB8, accent eerie violet #8A4FB8. These are the main colours plus one accent; no other strong colours.
POSE: Neutral standing pose of a tabletop miniature: both feet planted on the pedestal, weight even, both arms held slightly away from the torso with a visible gap between each arm and the body, elbows slightly bent; not a T-pose and not an A-pose. The weapon is held in the figure's own LEFT hand, which appears on the viewer's RIGHT in the front view.
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
- strict front orthographic view: a shallow top surface and curved front edge of the pedestal are visible -> zero-elevation orthographic front; hide the top entirely and make both discs' front edges straight horizontal lines.
- the whole subject and pedestal visible; plain flat dark gray background: the charcoal background has a gradient and vignette -> one uniform flat dark charcoal gray across the whole image, no gradient, vignette, floor or background shadow.
- The weapon is held in the figure's own LEFT hand; both arms clearly apart from the torso: hanging sleeves close the gaps between arms and torso -> keep the gnarled wand in the figure's LEFT hand on viewer RIGHT, elbows slightly bent, and expose visible background gaps under both arms without a T-pose or A-pose.
```

## Проверка и ограничения

Создан только design-front; согласованность между видами не проверяется. Между g1 и g2 сохранены ведьма, капюшон, косы, рваные одежды, травы, левая рука с оружием и палитра. Исправлены подставка, ровность фона и зазоры под руками; изменились мелкие подвески, травы и положение свободной кисти. CORE одинаков. Длинный посох вместо wand остаётся провалом CHECKLIST при лимите 2/2. Итоговый скрипт: 0 FAIL, WARN view.frame_top (3.108%). Низ подставки 96.271% вместо 93%. Байты изображений не менялись.

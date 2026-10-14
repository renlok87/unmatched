# ASSET-T-REX-001 — промпты концепта 1a

Дата: 2026-10-13.
Инструмент: image_gen.imagegen.
Режим: generate, единственный image input — craftsmanship reference.
Размер не передавался; аспект 3:4 задан текстом CORE. transparent_background=false.

## concepts/t-rex-design-front-g1.png

prompt_key: `1a/design-front/g1`.

referenced_image_paths (порядок вызова; пути от корня репозитория, при вызове разрешены в абсолютные):

```json
["art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"]
```

Точный prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Tyrannosaurus rex from Jurassic Park (Unmatched: Jurassic Park - Sattler vs. T-Rex): massive tyrannosaur in a striding pose, huge head with open jaws, tiny forelimbs, thick tail held level, brown-grey pebbled hide.
IDENTITY ANCHORS, each clearly visible: huge head with open jaws; tiny forelimbs; thick level tail; brown-grey pebbled hide.
PALETTE: hide brown #6E5A46, hide grey #6A665E, belly pale #B8A88A, accent tooth bone #E0D6C0. These are the main colours plus one accent; no other strong colours.
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

## concepts/t-rex-design-front-g2.png

prompt_key: `1a/design-front/g2`.

referenced_image_paths (порядок вызова; пути от корня репозитория, при вызове разрешены в абсолютные):

```json
["art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"]
```

Точный prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: The Tyrannosaurus rex from Jurassic Park (Unmatched: Jurassic Park - Sattler vs. T-Rex): massive tyrannosaur in a striding pose, huge head with open jaws, tiny forelimbs, thick tail held level, brown-grey pebbled hide.
IDENTITY ANCHORS, each clearly visible: huge head with open jaws; tiny forelimbs; thick level tail; brown-grey pebbled hide.
PALETTE: hide brown #6E5A46, hide grey #6A665E, belly pale #B8A88A, accent tooth bone #E0D6C0. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: the pedestal shows its upper surface and curved front edge -> use zero-elevation orthographic projection with both stacked discs edge-on, no visible top surface, and straight horizontal front edges.
- No weapon or held object. (both arms clearly apart from the torso, not a T-pose, not an A-pose): the tiny forelimbs overlap the torso and thighs without clear negative spaces -> place both slightly bent forelimbs so dark background gaps visibly separate each forelimb from the torso while retaining the neutral pose.
- the whole subject and pedestal visible, nothing cropped; plain flat dark gray background: the background has subtle uneven tone and vignette -> use one uniform flat neutral dark charcoal gray throughout the background.
```

## Проверка и ограничения

На этапе 1a создан только фронт; сравнение между видами неприменимо. Между кандидатами сохранены персонаж, открытая пасть, короткие передние лапы, толстый горизонтальный хвост, текстура кожи и основная палитра. g2 изменил подставку на проекцию с ребра, расширил просветы у передних лап и выровнял фон; автоматически также изменились пропорции, положение головы и поле сверху. CORE дословно одинаков; у g2 добавлен только CORRECTION из трёх строк.

Выбран g2: финальная проверка — 13 PASS, 0 WARN, 0 FAIL, код 0. CHECKLIST пройден; лимит использован полностью. Непройденные визуальные пункты g1 и отклонения g2 от размера/позиции подставки отражены в verification.json и README.md. Круглая форма подставки в плане не проверяема по фронту с ребра. Изображения не ретушировались, не масштабировались, не обрезались и не перекодировались.

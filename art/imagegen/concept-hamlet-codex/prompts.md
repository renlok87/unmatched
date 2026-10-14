# Промпты концепта Гамлета

Дата: 2026-10-13

Инструмент: image_gen, режим generate; один результат — одно изображение. Размер не передавался; аспект 3:4 только в CORE. transparent_background=false.

## hamlet-design-front-g1.png

prompt_key: `1a/design-front/g1`

referenced_image_paths (в порядке вызова, относительно корня репозитория):

1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

При передаче инструменту этот вход разрешён в абсолютный путь. Других image-input нет.

Точный prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Hamlet, Prince of Denmark: young brooding nobleman in a black doublet and hose, white ruff collar, short black cape over one shoulder, rapier in his RIGHT hand, a skull held in his LEFT hand.
IDENTITY ANCHORS, each clearly visible: rapier in the figure's own RIGHT hand; skull in the LEFT hand; white ruff collar; black doublet.
PALETTE: mourning black #1F1F24, ruff white #E8E4DA, silver #A9ADB2, accent royal blue lining #2B4A8A. These are the main colours plus one accent; no other strong colours.
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

## hamlet-design-front-g2.png

prompt_key: `1a/design-front/g2`

referenced_image_paths (в порядке вызова, относительно корня репозитория):

1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`

При передаче инструменту этот вход разрешён в абсолютный путь. Других image-input нет.

Точный prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Hamlet, Prince of Denmark: young brooding nobleman in a black doublet and hose, white ruff collar, short black cape over one shoulder, rapier in his RIGHT hand, a skull held in his LEFT hand.
IDENTITY ANCHORS, each clearly visible: rapier in the figure's own RIGHT hand; skull in the LEFT hand; white ruff collar; black doublet.
PALETTE: mourning black #1F1F24, ruff white #E8E4DA, silver #A9ADB2, accent royal blue lining #2B4A8A. These are the main colours plus one accent; no other strong colours.
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
- CHECKLIST strict front orthographic view: the pedestal top is visible and its front edge curves -> show the pedestal exactly edge-on with zero visible top surface and a straight horizontal front edge.
- CHECKLIST plain flat dark gray background: the background has a gradient and vignette -> use one uniform flat dark charcoal gray across the entire background.
```

## Проверка и ограничения

Разных ракурсов нет: только design-front. Между попытками сохранены чёрный дублет, белый раф, рапира в правой руке (слева для зрителя), череп в левой, синяя подкладка. g2 изменил детали костюма и исправил подставку: верх не виден, края горизонтальны. Подозрение на градиент g2 не подтвердилось при проверке свободных пикселей.

Все три запуска скрипта вернули 0. Выбран g2; все шесть CHECKLIST-пунктов проходят. WARN: верх 3.384% вместо 4% и компоненты маски тёмной фигуры. Плащ длиннее короткого из CORE, подставка шире приблизительной пропорции 0.55. Ограничения записаны в verification.json. Обе генерации сохранены без обработки; статус «предложено».

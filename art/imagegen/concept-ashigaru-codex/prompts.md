# Промпты ASSET-ASHIGARU-001, этап 1a

Дата: 2026-10-13. Инструмент: image_gen (image_gen.imagegen).

Пути referenced_image_paths ниже записаны относительно корня репозитория; в вызове инструмента они разрешены в абсолютный путь C:/Users/ren/WebstormProjects/unmached/unmached/. В каждом вызове передан только один референс, в указанном порядке. Размер не передавался; аспект 3:4 задан только текстом. transparent_background=false.

## concepts/ashigaru-design-front-g1.png

prompt_key: 1a/design-front/g1

referenced_image_paths (по порядку):

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: An ashigaru foot soldier of a Japanese warlord: lean soldier in lacquered jingasa hat and simple dark armour over blue cloth, long yari spear held upright in his RIGHT hand, small banner on his back.
IDENTITY ANCHORS, each clearly visible: yari spear upright in the figure's own RIGHT hand; jingasa hat; small back banner.
PALETTE: lacquer black #1E1C1E, indigo cloth #2F3F6A, wood #8B6A43, accent banner vermilion #C2462A. These are the main colours plus one accent; no other strong colours.
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

## concepts/ashigaru-design-front-g2.png

prompt_key: 1a/design-front/g2

referenced_image_paths (по порядку):

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: An ashigaru foot soldier of a Japanese warlord: lean soldier in lacquered jingasa hat and simple dark armour over blue cloth, long yari spear held upright in his RIGHT hand, small banner on his back.
IDENTITY ANCHORS, each clearly visible: yari spear upright in the figure's own RIGHT hand; jingasa hat; small back banner.
PALETTE: lacquer black #1E1C1E, indigo cloth #2F3F6A, wood #8B6A43, accent banner vermilion #C2462A. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: the pedestal top is visible and its front top edge is curved -> hide the entire top surface and show both discs exactly edge-on with straight horizontal edges.
- one subject, one pedestal, no collage, no second view, no text, letters, logo or watermark: crest emblems appear on the hat and banner, and an extra sheathed sword appears at the waist -> keep the hat and banner completely blank and remove the extra sword, leaving only the upright yari.
- the whole subject and pedestal visible, nothing cropped; plain flat dark gray background: the background has tonal variation -> use one perfectly uniform neutral dark charcoal gray throughout the background.
```

## Проверка и ограничения

Создан только фронтальный дизайн; межвидовое совпадение не проверялось. Между g1 и g2 сохранены асигару, правая рука с yari слева от зрителя, jingasa, заднее знамя, палитра и двухдисковая подставка. В g2 исчезли эмблемы и меч, изменилась отделка шнуров и доспехов, подставка показана с ребра. Исходные PNG не правились. Выбран g2; финальный код скрипта 0, 12 PASS / 1 WARN / 0 FAIL. WARN верхнего отступа 1,588% и низ подставки 95,58% записаны в verification.json. Все выбранные пункты CHECKLIST выполнены; лимит 2/2 использован. Первая техническая ошибка сохранения и преждевременная проверка без входного каталога также записаны. Статус — предложено.

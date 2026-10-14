# Промпты концепта Синдбада — этап 1a

Дата: 2026-10-13. Инструмент: image_gen (встроенный image_gen.imagegen), mode: generate.

Пути референсов приведены относительно корня репозитория; при вызове они разрешены в абсолютный путь того же файла. Размер инструменту не задавался; аспект указан только в CORE. transparent_background: false.

## concepts/sinbad-design-front-g1.png

prompt_key: 1a/design-front/g1

referenced_image_paths (в порядке вызова):

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Точный prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Sinbad the Sailor: weathered adult seafarer with a short black beard, white turban with a blue sash, open sleeveless vest over a loose shirt, wide sash belt, baggy trousers, curled slippers; curved scimitar in his RIGHT hand, scabbard on his LEFT hip.
IDENTITY ANCHORS, each clearly visible: scimitar in the figure's own RIGHT hand; white turban; wide blue sash belt; scabbard on the LEFT hip.
PALETTE: sail white #E6DCC6, sea blue #2E5C8A, sun-bleached tan #B8935E, accent gold trim #D4A63A. These are the main colours plus one accent; no other strong colours.
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

## concepts/sinbad-design-front-g2.png

prompt_key: 1a/design-front/g2

referenced_image_paths (в порядке вызова):

1. art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Точный prompt:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Sinbad the Sailor: weathered adult seafarer with a short black beard, white turban with a blue sash, open sleeveless vest over a loose shirt, wide sash belt, baggy trousers, curled slippers; curved scimitar in his RIGHT hand, scabbard on his LEFT hip.
IDENTITY ANCHORS, each clearly visible: scimitar in the figure's own RIGHT hand; white turban; wide blue sash belt; scabbard on the LEFT hip.
PALETTE: sail white #E6DCC6, sea blue #2E5C8A, sun-bleached tan #B8935E, accent gold trim #D4A63A. These are the main colours plus one accent; no other strong colours.
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
- strict front orthographic view, camera exactly level, no perspective, no three-quarter turn; the pedestal is seen exactly edge-on, its top surface is not visible: the pedestal top surface is visible -> hide the top surface completely, show both discs exactly edge-on with straight horizontal front edges.
```

## Проверка и ограничения

Создан только один вид design-front; согласование разных проекций не проверялось и не заявляется. g1 и g2 — альтернативные дизайны одного фронта. Совпадают якоря личности, сторона оружия, палитра, тип одежды, нейтральная стойка и подставка из двух дисков. Между генерациями изменились лицо, орнамент и складки, форма клинка и ножен. Цель единственной CORRECTION — скрыть верхнюю плоскость подставки; в g2 она достигнута.

Выбрана g2. Все шесть визуальных пунктов CHECKLIST пройдены; каждый прогон скрипта — код 0 (12 PASS, 1 WARN). Верхний отступ g1 — 2,693%, g2 — 3,522%, минимум CORE — 4%; это разрешённые WARN. Низ подставки g2 — 94,751% вместо 93%. Её диаметр визуально около 0,63 высоты фигуры вместо «about 0.55». Обе генерации содержат дополнительный эфес над ножнами, похожий на второе оружие, вопреки CORE.FORBIDDEN.extra_weapons. Лимит 2/2 использован. Полный перечень ограничений — verification.json#limitations. Изображения не изменялись.

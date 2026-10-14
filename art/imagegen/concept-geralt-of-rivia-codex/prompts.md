# Промпты концепта Геральта из Ривии — этап 1a

Дата: 2026-10-13T07:29:56+00:00
Инструмент: встроенный image_gen. Режим: generate; transparent_background: false.
Размер в вызов не передавался; соотношение сторон задано только в CORE.

## design-front — g1

prompt_key: 1a/design-front/g1.
Целевой файл: art/imagegen/concept-geralt-of-rivia-codex/concepts/geralt-of-rivia-design-front-g1.png.
Файл не создан: инструмент отклонил результат на стадии output.

referenced_image_paths в точном порядке вызова:
1. C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png

Единственный входной образ используется только как референс качества изготовления и покраски.
Точный промпт:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Geralt of Rivia from The Witcher (Unmatched: The Witcher - Steel & Silver): grim monster hunter with long white hair tied back, yellow cat eyes, a facial scar, dark leather armour with straps, wolf medallion on the chest, steel sword in his RIGHT hand, silver sword hilt over the shoulder.
IDENTITY ANCHORS, each clearly visible: steel sword in the figure's own RIGHT hand; silver sword hilt over the shoulder; long white hair; wolf medallion; dark leather armour.
PALETTE: leather black #24211F, hair white #E2E0DA, steel #9AA1A7, accent medallion silver #C0C6CC. These are the main colours plus one accent; no other strong colours.
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

## Проверка и ограничения

Изображение не получено: HTTP 400, moderation_blocked на стадии output, категория other.
Request ID: ea1c2665-aa85-4fd0-a36c-2329e804adfc.
Исходный путь инструмента, размер и SHA-256 результата неизвестны: файл не был возвращён.
Видов для сопоставления нет. CORE передан без изменений, блок CORRECTION не добавлялся.
Автопроверка и визуальный CHECKLIST не выполнялись; выбранного кандидата нет.
Оба входа и исходный palette.json сохранены без изменений. Повторная генерация не выполнялась:
условия ретрая шага 3 (FAIL скрипта либо CHECKLIST) не наступили.

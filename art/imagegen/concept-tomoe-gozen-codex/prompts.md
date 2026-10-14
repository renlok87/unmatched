# Промпты — Томоэ Годзэн, этап 1a

Дата: 2026-10-13.
Инструмент: image_gen.imagegen, встроенный режим generate.
Карточка: ASSET-TOMOE-GOZEN-001.
Число вызовов: 1. Размер инструменту не задавался; transparent_background=false.

## concepts/tomoe-gozen-design-front-g1.png

prompt_key: `1a/design-front/g1`.
view: `design-front`; side_view: null; attempt: 1; selected: true; correction: null.

referenced_image_paths, в порядке вызова (пути записаны относительно корня репозитория; инструмент получил разрешённый абсолютный путь того же файла):
1. `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png` — только эталон мастерства, SHA-256 e97c4a28be8adc63b560a323aa5283d791ae9c098473862f6f834ad7cb42bfc9.

palette.json — текстовый вход, не image input. Других изображений в вызове нет.

Точный текст промпта:

```text
Use case: original concept design of ONE collectible painted tabletop miniature, front view, as the input for
image-to-3D modelling.
Image 1 is ONLY the craftsmanship reference: a finished premium painted miniature. Match its level of sculpted and
painted detail, its matte hand-painted resin look and its studio presentation. Do not copy its anatomy, face, costume,
weapon, colours, pose, pedestal or framing.
SUBJECT: Tomoe Gozen, the onna-musha of the Genpei War (Unmatched: Sun's Origin): woman samurai in red lacquered o-yoroi armour, long black hair tied back with a white headband, naginata held in her RIGHT hand.
IDENTITY ANCHORS, each clearly visible: naginata in the RIGHT hand; red lacquered o-yoroi armour; white headband; long black hair.
PALETTE: lacquer red #9B2E26, cord blue #2F4F8F, hair black #1A1719, accent trim gold #D4AE45. These are the main colours plus one accent; no other strong colours.
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

Создан только фронтальный дизайн; сравнение между видами неприменимо. Все четыре якоря и палитра присутствуют, сторона нагинаты соблюдена. Фигура и подставка целиком в кадре; фон тёмно-серый. Между оригиналом, файлом concepts и выбранным design совпадают все байты. Изменений изображения и коррекции промпта не было.

Не выполнен визуальный пункт о подставке строго с ребра: видна узкая верхняя поверхность. Дополнительно появился меч в ножнах, запрещённый CORE. Верхний отступ 1,519% дал WARN view.frame_top; низ подставки 95,994% отличается от y93%. Подставка визуально шире ориентира 0,55 высоты фигуры.

Первоначальная команда сохранения данных не прошла из-за кавычек PowerShell; проверка, ошибочно запущенная до успешного копирования, получила отсутствующий каталог. После исправления копирования автопроверки кандидата и выбранного файла дали код 0, 12 PASS, 1 WARN, 0 FAIL. Новые генерации после ошибки входа не запускались; использована 1 из 2, лимит не исчерпан. Подробности в verification.json; статус «предложено».

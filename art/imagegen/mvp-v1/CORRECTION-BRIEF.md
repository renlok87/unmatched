# Бриф на коррекцию пакета imagegen mvp-v1 для генерации 3D и текстур

Дата: 2026-09-26. Основа: проверка 115 изображений пакета `art/imagegen/mvp-v1` (коммит `9f1845a`) на пригодность для image-to-3D (Hyper3D Rodin через blender-mcp, Hunyuan3D-2mv) и для текстур UE.
Исполнитель: Codex. Инструмент генерации: встроенный imagegen.

## 0. Пути

- Корень репозитория: `C:/Users/ren/WebstormProjects/unmached/unmached`
- Ветка: `fix/admin-panel`
- Пакет: `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/mvp-v1`
- Реестр пакета: `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/mvp-v1/manifest.json`
- Промпты: `C:/Users/ren/WebstormProjects/unmached/unmached/art/imagegen/mvp-v1/prompts/`
- Спецификация арта: `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/17-art-production-spec.md`
- Карточки моделей и размеры: `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/04-blender-production.md` (§3.1–3.4, стр. 92–180)
- Стиль и пропорции С-1: `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/03-art-direction.md` (стр. 19)
- Геометрия поля (источник истины): `C:/Users/ren/WebstormProjects/unmached/unmached/docs/game-design/evidence/S04/board-contract.json` (5×6 клеток, клетка 100 uu, зоны blue/red по 15 клеток)

## 1. Правила работы

1. Оригиналы не удалять и не перезаписывать. Исправленные версии сохранять рядом с суффиксом `-v2` (или `-v3`, если `-v2` уже есть); в `manifest.json` переключить выбранный путь, прежний оставить в истории.
2. Промпт каждой новой генерации сохранить в `prompts/` с тем же ID и суффиксом версии.
3. После каждой генерации обновить в `manifest.json` фактический размер, SHA-256 и статус `generated-reviewed`.
4. Не менять `docs/game-design/06-asset-manifest.csv` и документы 00–17: пакет остаётся визуальным исходником, а не принятым ассетом.
5. Статус результата — ПРЕДЛОЖЕНИЕ. Приёмку GD-058 это не закрывает.
6. Коммитить только файлы пакета; чужие изменения в рабочем дереве не трогать. Pre-commit хук сломан (нет prettier) — `--no-verify` допустим только для этого.

## 2. Общий формат для image-to-3D (для всех моделей)

Вставлять в начало каждого промпта модели:

```text
Redraw the attached concept as a production turnaround for image-to-3D generation.
Output: SEPARATE square images 1024x1024 (one file per view), views: FRONT, LEFT SIDE, BACK, RIGHT SIDE.
Strict orthographic projection, no perspective, camera at mid-height of the object, object centered.
Identical pose, proportions, scale and colors in all views; bottom of the base aligned to the same baseline in every view;
the whole object including base visible, nothing cropped, 10% margin on every side.
Plain uniform mid-gray background (#808080), no floor, no cast shadows, soft even frontal lighting,
no rim light, no ambient occlusion darkening, no depth of field.
Style: stylized tabletop miniature, matte hand-painted resin look, large simplified forms, readable silhouette,
low-poly friendly: remove micro-detail (chainmail rings, engravings, tiny emblems, individual small feathers),
keep big shapes, 2–3 main colors plus one accent. No text, no logos, no labels.
Thin elements (bowstrings, staff tips, sword edges) must be at least 2% of image width thick.
```

Выходные файлы вида: `characters/ref-<id>-v2-front.png`, `-left.png`, `-back.png`, `-right.png`. Лист-коллаж можно дополнительно сохранить как `ref-<id>-v2-sheet.png`, но генерация 3D берёт отдельные виды.

## 3. Коррекции по ассетам

### 3.1 Персонажи — обязательно (блокируют 3D)

Общие дефекты текущих листов `characters/ref-king-arthur.png`, `ref-medusa.png`, `ref-harpy.png`, `ref-merlin.png` (1774×887):
- все 4 вида в перспективе 3/4, ортогональных видов нет;
- виды 1 и 4 почти одинаковые (оба спереди 3/4), правого профиля нет;
- на вид приходится ~440 px ширины — мало для проекции текстуры;
- освещение и тени запечены в цвет;
- база с брусчаткой противоречит нейтральной базе `markers/ref-base-*` и сливается с полем Cobble City.

Общее исправление: формат §2 + нейтральная база как в `markers/ref-base-hero-p1.png` (тёмный камень, гладкий верх, без брусчатки; командное кольцо НЕ рисовать — это отдельный материал).

| ID | Размеры (ПРЕДЛОЖЕНИЕ, 04) | Что сохранить | Что изменить |
|---|---|---|---|
| king-arthur | высота 52–56 uu, база Ø 30 uu | корона, тёмная сталь с тусклой бронзой, тёмно-красный плащ, прямой меч у плеча — главный признак силуэта | один крупный простой герб вместо льва и лилий; без кольчужной чешуи; плащ 3–4 крупные складки; меч не перекрывает голову ни в одном виде |
| medusa | высота 50–55 uu, база Ø 30 uu, змеи не выше 60 uu | лук, змеи-волосы, зелено-серая кожа, тёмный хитон, бронза | ровно 7 змей в одинаковых позициях во всех видах; тетива толще (≥2% ширины); колчан за спиной одинаковый во всех видах; складки хитона крупнее |
| harpy | высота 35–42 uu, база Ø 22 uu, размах ≤ 80 uu | полураскрытые крылья, присед, когти, браслет на левой ноге | перья крупными группами (5–7 на крыле), без отдельного прорисованного пера; силуэт «шире, чем выше» |
| merlin | высота 40–48 uu, база Ø 24 uu, посох выше фигуры на голову | старый маг, посох — главный признак, сутулость | **убрать сходство с Гэндальфом**: без серой широкополой остроконечной шляпы и раздвоенного посоха; вместо этого индиго-капюшон или мягкий друидский колпак, кельтская кайма, короче заплетённая белая борода, посох из узловатого дерева с кристаллом или рогами наверху |

Дополнительные промпт-строки:

```text
King Arthur: heavy armored king, the tallest figure of the set, ~5.5 heads, sword 1.2–1.4x realistic length held upright near the shoulder, clearly separated from the head; calm ready stance, no shield.
Medusa: mythological archer, ~5.5 heads, exactly 7 snakes in the hair in the same positions in all views, bow held in the left hand, thick bowstring, quiver on the back identical in all views.
Harpy: crouched winged creature, wings half-open, silhouette wider than tall, feathers grouped into 5–7 large shapes per wing, bronze band on the left ankle.
Merlin: old court sorcerer of Arthurian legend, NOT a Tolkien-style wizard. No grey wide-brim pointed hat, no forked staff. Indigo hooded robe with Celtic-knot trim, shorter braided white beard, gnarled staff topped with a crystal or antlers, one head taller than the figure, slightly hunched.
```

Приёмка (каждый персонаж): 4 файла 1024×1024; силуэт в каждом виде ортогональный (линия плеч и база горизонтальны, база видна эллипсом не толще 10% её ширины в front/left/right/back); низ базы на одной высоте ±1% во всех видах; число змей/деталей совпадает между видами; фон однородный (стандартное отклонение яркости фона < 3); нет текста; Merlin не читается как Гэндальф (проверка человеком).

### 3.2 Поле — обязательно

`environment/ref-board-cobble.png` (1145×1374): сетка 5×6 верная, но синий и красный цвет зон запечён в камень.

Исправление: `environment/ref-board-cobble-v2.png` — тот же вид сверху, но **все 30 клеток одного нейтрального серого камня**; зоны не рисовать (они делаются отдельным оверлеем с цветом и глифом, AD-OPEN-25). Сохранить рамку, пропорцию 5:6, разделители клеток. Дополнительно `environment/ref-board-cobble-v2-side.png` — вид сбоку, ортогонально, толщина плиты и рамки.

Приёмка: ровно 5 столбцов × 6 рядов; отношение сторон игрового поля 5:6 ±2%; разброс средней яркости между клетками < 8 единиц из 255; ни одна клетка не окрашена в синий или красный.

### 3.3 Основание стола — желательно

`environment/ref-table-base.png`: квадратная плита, а поле 5:6. Исправление: `ref-table-base-v2` — плита с пропорцией верха 5:6 плюс поле 10% под рамку; виды: 3/4 сверху, front, side (ортогонально). Скальный низ сохранить (его удобно генерировать), рамку и верх затем моделируют вручную.

### 3.4 Пропсы — желательно

| Файл | Дефект | Исправление |
|---|---|---|
| `environment/ref-barrel.png` | виды 1 и 2 одинаковые | формат §2: front, side, top, 3/4 |
| `environment/ref-lantern.png` | виды 1 и 2 одинаковые; пламя запечено | формат §2; дополнительно вариант без свечения (стекло тёмное, пламя не рисовать) — свечение будет emissive-материалом |
| `environment/ref-crate.png`, `ref-facade-b.png`, `ref-facade-c.png` | **не проверены в этом проходе** | проверить по приёмке §3.1 (ортогональность, разные виды, фон); если виды дублируются — исправить форматом §2 |
| `environment/ref-facade-a.png` | годен | не трогать |
| `characters/ref-placeholder-mannequin.png` | годен | не трогать |

### 3.5 Материалы — техническая доработка (без перегенерации)

`materials/tex-*.png` (6 шт., 1254×1254): бесшовны, свет ровный — годны. Нужно:
1. Ресайз в 2048×2048 и 1024×1024 (Lanczos) → `materials/export/T_<name>_D_2048.png`, `_1024.png`.
2. Сгенерировать производные карты любым воспроизводимым скриптом/инструментом (например, Materialize или Blender bake из height): `T_<name>_N` (normal, DirectX/UE-ориентация: зелёный канал инвертирован относительно OpenGL), `T_<name>_ORM` (R=AO, G=roughness, B=metallic; для металлов iron/bronze metallic=1, остальные 0).
3. Приёмка: плитка 2×2 каждой карты без видимых швов; normal в диапазоне и нормализован; записать инструмент и параметры в `PRODUCTION-NOTES.md`.

### 3.6 VFX — техническая доработка

`vfx/*.png` — одиночные спрайты, годны как частицы. Для анимированных CUE (impact, damage, death-ash, petrify, heal) сгенерировать flipbook 4×4 (16 кадров) на прозрачном фоне → `vfx/vfx-<name>-flipbook-4x4.png`, 2048×2048, альфа на краях каждого кадра ≤ 8/255. Если imagegen не держит согласованность кадров — записать это в `PRODUCTION-NOTES.md` и оставить задачу на Niagara, не выдумывая результат.

### 3.7 UI, маркеры, зоны, портреты — без коррекции

Проверены выборочно на тёмном фоне: альфа чистая, читаемость хорошая. Runtime-подготовка (нормализация холста, nine-slice, точные размеры из 02) — отдельная задача, в этот бриф не входит.

## 4. Порядок выполнения

1. §3.1 персонажи (Arthur → Medusa → Merlin → Harpy).
2. §3.2 поле.
3. §3.4 проверка crate/facade-b/facade-c, затем barrel/lantern.
4. §3.3 основание.
5. §3.5 материалы, §3.6 VFX.
6. Обновить `manifest.json`, `index.html`, `SPEC-COVERAGE.md`; прогнать существующие проверки пакета (`node --check` для `.mjs`, проверка SHA-256 и альфы).

## 5. Отчёт исполнителя

В конце добавить в `PRODUCTION-NOTES.md` раздел «Коррекция v2»: список новых файлов, что прошло/не прошло приёмку §3, какие пункты не выполнены и почему. Не объявлять ассеты готовыми к игре: следующий шаг — генерация 3D (blender-mcp + Hyper3D Rodin, 4 вида на входе) и ручная доводка в Blender по `04-blender-production.md`.

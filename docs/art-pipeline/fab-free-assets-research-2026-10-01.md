# Бесплатные ассеты Fab для Unmatched: ресерч (2026-10-01)

Ветка `feat/env-original-maps`. Машиночитаемый шортлист: [fab-free-assets-shortlist-2026-10-01.json](fab-free-assets-shortlist-2026-10-01.json) (схема `unmatched.fab-shortlist/1`). Контекст: ENV-U13 в [решениях по картам](../game-design/decisions/2026-09-30-env-original-maps-decisions.md), гэпы — `docs/game-design/evidence/ENV-MAPS/p2-frames-2026-10-01/concept-review.json`.

Решения пользователя (дословно): «Дополнительно запусти ресерч. По поводу того, какие ассеты мы бесплатно можем взять из FAB в для нашего проекта.»; «И все только для личного и локального использования в локальной сети. Нигде это не будет публиковаться.» — значит, бесплатный уровень Personal подходит.

## 1. Короткий итог

- Брать в первую очередь VFX и атмосферу: стилизованный огонь (Stylish Fire VFX), светлячки и ветер (Particles and Wind Control System), лепестки и перья (Free Niagara Particles). Попадание в стиль высокое, работы мало, ночная сцена сразу оживает.
- Юбка подноса (gap 3): тёмные рисованные валуны Gerardo Justel «Stylized Rocks» почти совпадают с концептом. Сами модули обрыва по-прежнему собирать в Blender (ENV-U10), бесплатных модульных обрывов без NoAI нет.
- Растительность: Lux Art «Vegetation Stylized Kit» (розовое дерево под сакуру), Gairisa «Fantasy_Forest» (тёмный лес Sarpedon) и «Vine_Plants» (плющ). Всё дневное и яркое, поэтому нужен общий ночной MI-оверрайд листвы.
- Sarpedon: Poly Haven «Smuggler's Cove» — единственный пак с парусами, такелажем, пушками и причалом. Он фотореальный, нужен перекрас. Вода — только «Water Materials» (tharlevfx) с доработкой.
- Marmoreal: рисованный фонарь Tōrō закрывает тёплые источники (gaps #13/#14). Балюстраду, статую Медузы и фасад бесплатный Fab не даёт, их делаем в Blender/Tripo.
- Самые сильные бесплатные стилизованные паки (Nest Stylized Tree, StyleHex, Vefects, Good SKY, Low Poly Cliffs & Rocks и др.) помечены **NoAI**. Они не идут в кадры для AI-ревью, решение по ним за пользователем.
- У всех паков совместимость с UE 5.8 проверяется при добавлении. CC-BY требует атрибуции в `CREDITS`.

## 2. Правила отбора

**Лицензии.**
- *Personal (Личное)*: бесплатный уровень стандартной лицензии Fab, рассчитан на самостоятельного автора или небольшую команду. Нам подходит, потому что использование личное и локальное, без публикации.
- *Professional / Стандартная*: тоже подходит.
- *UE Marketplace License* (старые бесплатные паки): подходит.
- *CC-BY*: использование свободное, но нужна атрибуция: автор, название, ссылка, лицензия. Ведём её в `docs/art-pipeline/CREDITS-fab.md` (создать при первом импорте) и в `asset-registry.json`.
- Добавление пака в библиотеку Fab означает принятие его лицензии. Это делает пользователь (см. раздел 5).

**NoAI (`aiForbidden=true`) и почему это важно.** Наш пайплайн отдаёт отрендеренные кадры AI-агентам (Claude) на ревью и замеры (concept-review, K1–K3, evidence SHOT) и использует imagegen. Условие NoAI запрещает подавать контент на вход генеративному ИИ, так что кадр с NoAI-ассетом нельзя отдавать агенту. Поэтому:
- превью NoAI-листингов не скачивались и не просматривались, оценка только по тексту, в таблицах помечено «визуально оценивает пользователь»;
- в ранжировании NoAI-листинги стоят ниже и в топ-10 не входят;
- если пользователь всё же захочет NoAI-пак (как уже взятый Megaplants Yoshino Cherry), его нужно держать на отдельном уровне или варианте и не включать в кадры для агентов;
- у двух листингов Glowbox3D (`a708070e`, `d1f178c3`) флаг `aiForbidden=false`, но в описании есть оговорка NoAI. Считаем их NoAI (та же оговорка ещё у 4 листингов Glowbox3D вне темы: Ouija Board, Police Investigation Board, Chess Set, Dart Board);
- для аудио риск ниже (звук в кадры не попадает), но пометка остаётся.

**ИИ-сгенерированные (`aiGenerated=true`).** Вероятно, качество на уровне Tripo. Такие ассеты помечены, сетку и текстуры нужно проверять. В шортлисте их немного: Marble Materials, Free Braziers, Medusara, Harpy Assassin.

**Форматы.**
- *UE-пакет* ставится через Launcher (Add to project) и сразу приходит с материалами.
- *FBX/GLB/OBJ/.blend* скачиваются напрямую и проходят через наш Blender → FBX → UE (так же, как Tripo и env_kit_build).
- *Только Unity* и *только UEFN* (например, Stylized Lake Village) отклонены.

**Версия UE.** В данных Fab её нет. Проект на UE 5.8, у всех пиков стоит «проверить при добавлении». Старые паки обычно ставятся через выбор версии в Launcher или через staging-проект с последующей миграцией.

**Стиль.** Главный критерий — «Painted Miniature»: стилизованное, рисованное, матовое, читаемые силуэты, ночь с холодной луной и тёплыми фонарями. Фотореальные сканы годятся только как референс, источник формы или текстуры грунта. Почти всё найденное нарисовано под день, поэтому закладываем ночную перекраску (десатурация, затемнение, roughness ≥ 0.8).

**Источники и метод.**
- Основной источник — harvest `C:/tmp/envmaps-research/fab/fab-free-harvest-2026-10-01.json`: 1317 бесплатных листингов по 70 запросам, не больше 24 результатов на запрос, поэтому покрытие неполное.
- Шесть доменных агентов отфильтровали листинги по тексту и просмотрели превью примерно 40–50 кандидатов на домен (только без NoAI). Превью лежат в `C:/tmp/envmaps-research/fab/thumbs/`, контакт-листы — в `sheets_*`.
- Домен «Вода/небо/VFX» вышел за рамки задания (fab.com открывать не предполагалось). Он дополнительно прочитал JSON-поиск fab.com через уже открытую вкладку Chrome пользователя: 50 запросов, 1645 листингов, только чтение, без кликов, покупок и добавлений в библиотеку. Источник таких пиков в JSON — `live-fab-search`, сырые данные не сохранены.
- При этом попытка передать данные на localhost вызвала в Chrome запрос «доступ к локальной сети» для www.fab.com. Его закрыли кнопкой «Закрыть», ничего не разрешая и не блокируя.
- Вкладку Fab в Epic Games Launcher агенты не использовали по двум причинам: сетка результатов показывает превью NoAI-листингов, а параллельные агенты мешали бы друг другу в одном окне. Проход по Launcher — шаг 6 в разделе 5.

## 3. Топ-10 «брать сейчас»

Отбор из всех доменов: без NoAI, наибольшая польза для открытых гэпов на единицу работы.

| # | Ассет | Издатель | Лицензия | NoAI / ИИ | Формат | Домен | Что закрывает | Стиль 1–5 | Усилия | Риски |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | [Stylish Fire VFX (Free asset)](https://www.fab.com/listings/01e8534c-5877-4ce2-8948-9a696100de11) | VfxSTOCK | Personal | нет | UE-пакет | Вода, небо, атмосфера, VFX | Огонь костров, фонарей и факелов обеих карт; стиль 5/5, минимум работы | 5 | низкие | Свет в Niagara выключить и ставить свои point lights (бюджет 60/30 FPS). UE 5.8: проверить при добавлении |
| 2 | [Stylized Rocks](https://www.fab.com/listings/f00f1dcd-c855-4dc7-b222-c79cae2b698d) | Gerardo Justel | CC-BY | нет | FBX | Скалы, обрывы, грунт | Gap 3: тёмные рисованные валуны юбки подноса, почти один в один с sarpedon-v2 | 5 | низкие | Около 4 валунов — повторы, нужны поворот/масштаб/вариация тона. PBR-материал сделать матовым под Lumen. UE 5.8: проверить при добавлении |
| 3 | [Particles and Wind Control System](https://www.fab.com/listings/f673ef70-1c66-4c7f-8751-9f84ddb8b083) | Dragon Motion | Personal | нет | UE-пакет | Вода, небо, атмосфера, VFX | Gap 8: светлячки, парящие огоньки и ветер листвы — живость ночной сцены | 4 | низкие | Найден живым поиском Fab (в harvest нет). Пак 2019 г., недавно обновлён. Ограничить число частиц и яркость под эталон High/Lumen. UE 5.8: проверить при добавлении |
| 4 | [Vegetation Stylized Kit](https://www.fab.com/listings/52498d47-a865-4e7e-a7ec-6a3fcbe9e5f3) | Lux Art Studios | CC-BY | нет | .blend | Растительность | Сакура Marmoreal (розовое дерево после перекраски), цветы и трава; без NoAI, в отличие от Yoshino Cherry | 4 | средние | Только .blend: экспорт FBX и сборка foliage-материала (two-sided, ветер). Дневные кислотные цвета, перекраска под ночь. UE 5.8: проверить при добавлении |
| 5 | [Fantasy_Forest](https://www.fab.com/listings/ece3a551-6c18-47db-8fc3-d3d12698265f) | Gairisa | Personal | нет | UE-пакет | Растительность | Тёмный лес по кромке Sarpedon — в SilverSet Forest такого нет | 4 | низкие | Кроны ярко-салатовые, нужен MI-оверрайд цвета. Качество у продавца неровное, вблизи видны карточки листвы. UE 5.8: проверить при добавлении |
| 6 | [Vine_Plants](https://www.fab.com/listings/23286ced-250a-4720-bb61-9017fbdc2446) | Gairisa | Personal | нет | UE-пакет | Растительность | Плющ и лианы на колоннаде, задней стене и руинах форта — новый слой | 4 | низкие | Яркая листва с оранжевыми стеблями, перекрасить темнее и холоднее. Меши без сплайнов, раскладка вручную. UE 5.8: проверить при добавлении |
| 7 | [Stylized Tōrō japanese lantern](https://www.fab.com/listings/2d92680a-fb96-4546-99d4-04029d172505) | Lisandro Rodriguez | CC-BY | нет | FBX | Marmoreal: архитектура и пропсы | Gaps #13/#14: дополнительные тёплые фонари с рисованной текстурой | 4 | низкие | Японский мотив и красная лента рядом с греко-римским дворцом: ленту убрать/приглушить. Мох слегка зеленит. Одно превью |
| 8 | [Free Niagara Particles (CC BY 4.0)](https://www.fab.com/listings/183732bc-c2fb-465c-9453-f70a1ce7ba2c) | SoftTofuVFX | CC-BY | нет | UE-пакет | Вода, небо, атмосфера, VFX | Падающие лепестки сакуры и перья гарпий (Niagara) | 4 | низкие | Отзывов нет, найден живым поиском. UE 5.8: проверить при добавлении |
| 9 | [Smuggler’s Cove Asset Pack](https://www.fab.com/listings/a0935013-5959-47c2-97d9-75478ded0e6b) | Poly Haven | CC-BY | нет | UE-пакет | Sarpedon: пропсы | Паруса и такелаж корабля, пушки, причал, башня форта — единственный тематический пак (фотореал, нужен перекрас) | 3 | средние | Фотореал, корабли 100–150k трис: перекрас под Painted Miniature (roughness, тонирование, упрощение текстур), возможно децимация. Дневной тропический свет. UE 5.8: проверить при добавлении (или glTF/blend с polyhaven.com) |
| 10 | [Water Materials](https://www.fab.com/listings/063155ea-d9d2-4f29-b09f-33270b0bc861) | tharlevfx | CC-BY | нет | UE-пакет | Вода, небо, атмосфера, VFX | Gap Sarpedon 1: река, прибой, водопад — единственная не-NoAI вода для UE | 3 | средние | Ближе к реализму: упростить нормали, ступенчатая окраска, пена-ободок. Оригинал под UE 4.13+, обновлялся; на 5.8 Substrate/Lumen могут изменить прозрачность — проверить при добавлении |

Следующая волна (11–15): [Free Pack - Rocks Stylized](https://www.fab.com/listings/a0746c4b-428b-4556-b4c9-98f70c2a30d4) (PolyOne Studio); [TREE PACK V1](https://www.fab.com/listings/c48b3c3c-d1e4-4030-9b8d-165ff851a96e) (leo isidro); [Barrel: Stylized Wooden](https://www.fab.com/listings/870ce80d-e31a-4251-8307-9c07839ea3ae) (Cramb Studio); [GanzSe FREE Camping - Fantasy Low Poly Props](https://www.fab.com/listings/d03138fe-7e29-4b3d-9ea8-8ba67f24f845) (GanzSe); [Marble Vase 001 (+ Marble Vase 002, 8a54bbdb-e740-4aca-b777-43cafadbba8e)](https://www.fab.com/listings/9512a274-8d76-489f-a9e4-b5574c47b3cb) (PK 3D Art).

## 4. По доменам

В таблице до 8 лучших пиков домена без NoAI. Полный список (14–15 на домен, вместе с NoAI; общие пики указаны в обоих доменах) лежит в JSON. «Стиль (по тексту)» значит, что превью не смотрели.

### 4.1. Растительность

*Охват:* деревья (сакура, тёмный лес, кипарисы, пальмы), кусты, изгороди, клумбы, трава, плющ, лепестки.

**Shortlist.**

| # | Ассет | Издатель | Лицензия | NoAI / ИИ | Формат | Что закрывает | Стиль 1–5 | Усилия | Риски |
|---|---|---|---|---|---|---|---|---|---|
| 1 | [Vegetation Stylized Kit](https://www.fab.com/listings/52498d47-a865-4e7e-a7ec-6a3fcbe9e5f3) | Lux Art Studios | CC-BY | нет | .blend | Marmoreal: пурпурно-розовое живописное дерево после десатурации/осветления = сакура вдоль колоннады; Sarpedon: зелёные деревья (затемнить) по кромке; цветы и трава для клумб. Новые силуэты крон к SilverSet Forest | 4 | средние | Только .blend: экспорт FBX и сборка foliage-материала (two-sided, ветер). Дневные кислотные цвета, перекраска под ночь. UE 5.8: проверить при добавлении |
| 2 | [Fantasy_Forest](https://www.fab.com/listings/ece3a551-6c18-47db-8fc3-d3d12698265f) | Gairisa | Personal | нет | UE-пакет | Sarpedon: лесная кромка периметра (левая и верхняя стороны концепта). Пухлые кроны в духе Ghibli, рисованная кора, трава и камни; после затемнения и охлаждения = тёмный ночной лес | 4 | низкие | Кроны ярко-салатовые, нужен MI-оверрайд цвета. Качество у продавца неровное, вблизи видны карточки листвы. UE 5.8: проверить при добавлении |
| 3 | [TREE PACK V1](https://www.fab.com/listings/c48b3c3c-d1e4-4030-9b8d-165ff851a96e) | leo isidro | CC-BY | нет | OBJ | Marmoreal: розовые деревья с узловатыми скульптурными стволами, ближайший к сакуре бесплатный силуэт; оливковые варианты как фоновые садовые деревья | 4 | средние | Только OBJ: материалы и маски листвы собирать заново. Полигонаж не указан. Листинг лежит в категории characters-creatures |
| 4 | [Vine_Plants](https://www.fab.com/listings/23286ced-250a-4720-bb61-9017fbdc2446) | Gairisa | Personal | нет | UE-пакет | Плющ и свисающие лианы: Marmoreal — колонны аркады, задняя стена дворца, балюстрада; Sarpedon — руины форта и частокол. Такого слоя у нас нет | 4 | низкие | Яркая листва с оранжевыми стеблями, перекрасить темнее и холоднее. Меши без сплайнов, раскладка вручную. UE 5.8: проверить при добавлении |
| 5 | [Date palm and vegetation](https://www.fab.com/listings/48b44812-8895-47de-aec1-b1cda046a24d) | Barsh | CC-BY | нет | FBX | Sarpedon: пальмы на пляже и у бухты, тропический подлесок. Кора и листья расписаны вручную, стиль полуреалистичный | 3 | высокие | «Сырой» модульный набор: стволы и листья собирать вручную, ветра нет. Других AI-разрешённых стилизованных пальм в harvest нет |
| 6 | [Fantasy Botanical](https://www.fab.com/listings/8dcf83f2-7064-47a2-af81-95a6e6d65eda) | Gairisa | Personal | нет | UE-пакет | Marmoreal: живописные куртины цветов (голубые, розовые, красные) и крупная листва для клумб, вазонов и подножий лестниц | 4 | низкие | Пересекается с Garden Foliage того же автора. Листва тропическая, на мраморном саду чуть экзотично. UE 5.8: проверить при добавлении |
| 7 | [Garden Foliage](https://www.fab.com/listings/6fbe6321-4915-49c5-8350-fc7e04709376) | Gairisa | Personal | нет | UE-пакет | Sarpedon: папоротники и широколиственный подлесок у руин форта и лесной кромки; Marmoreal: зелень под деревьями | 4 | низкие | Тон чуть бирюзовый, подстроить. UE 5.8: проверить при добавлении |
| 8 | [simple stylized forest](https://www.fab.com/listings/a3a4a839-abf8-46f0-b61d-3bf1845af0a9) | Gairisa | Personal | нет | UE-пакет | Sarpedon: высокие стройные деревья для заднего плана и стены леса за фортом, в паре с Fantasy_Forest | 3 | низкие | Простые силуэты, однотонные кроны; почти дублирует Fantasy_Forest — достаточно одного из двух. UE 5.8: проверить при добавлении |

Ещё без NoAI (в JSON): [Stylized Bush](https://www.fab.com/listings/9cf84839-03f6-48e7-a239-f998998f3784) — Marmoreal: круглый куст из лепестков-листьев — топиари-шары у постаментов и фонарей, стриженые бордюры (масштаб + сплющивание); [Stylized garden pot tree with flowers](https://www.fab.com/listings/e789b0ab-0264-451b-8092-de9f79add70c) — Marmoreal: цветущее деревце в чаше с опавшими лепестками — акцент на террасе или у входа, «вишня в вазоне»; [Stylized Lupines](https://www.fab.com/listings/a40ee12a-44f8-4553-bcb2-e01f34c8ce81) — Marmoreal: лиловые свечи люпинов с ручной росписью — вертикальные акценты клумб, тон совпадает с лиловыми зонами карты; [Mayu's Stylized Trees](https://www.fab.com/listings/7b36c38a-08ac-441d-a8b0-cc2a72220c4b) — Дерево с кроной из шаров = топиари для Marmoreal; материалы листвы как образец для ночной перекраски SilverSet и Lux; [Stylized Garden](https://www.fab.com/listings/bac2be80-7788-41e2-a493-4816d15f490b) — 57 вариантов цветов и 50 мешей: точечное заполнение клумб Marmoreal, если Gairisa и Lux не хватит.

**NoAI-кандидаты (превью не смотрели, визуально оценивает пользователь; в кадры для AI-ревью не ставить):**
- [Stylized Tree](https://www.fab.com/listings/b39d5f78-9494-4a20-b029-24babc8405c5) (Nest, UE-пакет, стиль 3 по тексту) — По тексту: 90+ стилизованных деревьев (включая плакучую иву), ветер, PDO, градиенты кроны, мох/снег; 5★ (17 отзывов). Потенциально лучший бесплатный набор деревьев. Визуально оценивает пользователь
- [FREE Stylized Forest Sample - Stylized Trees & Foliage Pack](https://www.fab.com/listings/3c1a31b6-e523-4a0f-97d0-26b0db69b6bc) (StyleHex Studio, UE-пакет, стиль 3 по тексту) — По тексту: стилизованные деревья (берёза), трава, цветы в аниме-духе; парный пак b494d1c5 «FREE Stylized Foliage Pack». Визуально оценивает пользователь

**Отклонённые заметные.**
- Все Megaplants (Japanese Cypress 0843f3cf, Yoshino Cherry — уже взят, Giant Bamboo, Black Alder и др.): NoAI + фотореал + экспериментальный PVE/Nanite Foliage — не Painted Miniature.
- Palms Pack 01 Trachycarpus (9f81069d): NoAI, реалистичные пальмы, бесплатен для Personal только до октября 2026.
- Low Poly Seasonal Foliage and Rock Pack (a708070e, Glowbox3D): флаг aiForbidden=false, но в описании прямая оговорка NoAI — считаем NoAI, превью не смотрели.
- Tiny Talisman «Stylized Nature Pack», Polytope «Lowpoly Environment - Nature», Dungeon Mason «RPG Tiny Fantasy Forest», RAD «River Forest», JustCreate, Vertex Rage, FANTASTIC Village Pack, Paragon Agora: NoAI, визуально оценивает пользователь.
- Sakura Tree (46e92625), Sakura Blossoms (2a3842e0), Cartoon Grass (52d9c580) — Kamilla Kraus: aiGenerated, глянцевые бесформенные комки, хуже Tripo.
- Stylized Cartoon Tree Pack (84db1675): aiGenerated; силуэты приличные, но это Tripo-качество — резерв.
- Cozy Nature, ToonLab, Low Poly Nature Pack Lite, Low Poly Trees and Bushes Bundle, Stylized Medieval Environment Lite: плоский low-poly/toon без живописности.
- pagoda and cherry blossom scene (1053db66): запечённая сцена одним glb, сакура не отделяется. City Park LITE, Mobile Trees, Bald Cypress scan, Fan Palm, Palm Tree: фотореал/archviz.
- Stylized Tree danpetro (19c31d1e): 64k трис на одно дерево. Stylized Tree Samples (Symphonie): только Unity. Stylized Tree CGMA Week 2: 2.5D-диорама под один ракурс.

**Пробелы, которые бесплатный Fab не закрывает, и чем их закрыть.**

| Пробел | Чем закрыть |
|---|---|
| Колоновидные кипарисы и топиари-конусы для Marmoreal | наш Tripo-кипарис или простая сборка в Blender (конус + листва из SilverSet/Lux) |
| Бледно-розовая живописная сакура, читаемая ночью | перекраска SilverSet / Lux Vegetation Kit / TREE PACK V1 через общий ночной MI листвы |
| Опавшие лепестки (декали, ковёр на мраморе, падение) | Niagara — Free Niagara Particles (SoftTofuVFX); декали — свои (imagegen-текстура + DBuffer decal) |
| Тёмный ночной лес, густые заросли Sarpedon | все кандидаты дневные — общий ночной MI-оверрайд листвы (десатурация, затемнение, холодный сдвиг) |
| Стриженые прямоугольные изгороди (box hedge) | наш Tripo hedge bed или Blender-модуль с листвой SilverSet |
| Стилизованные кокосовые пальмы | Barsh Date palm (сборка вручную) или Tripo |
| Пучки травы и мха по кромке подноса | SilverSet Forest (уже есть) |

### 4.2. Скалы, обрывы, грунт

*Охват:* валуны, модули юбки подноса (gap 3), галька, песок, тайлящиеся материалы, декали.

**Shortlist.**

| # | Ассет | Издатель | Лицензия | NoAI / ИИ | Формат | Что закрывает | Стиль 1–5 | Усилия | Риски |
|---|---|---|---|---|---|---|---|---|---|
| 1 | [Stylized Rocks](https://www.fab.com/listings/f00f1dcd-c855-4dc7-b222-c79cae2b698d) | Gerardo Justel | CC-BY | нет | FBX | Gap 3: тёмные угольные рисованные валуны с трещинами — почти точь-в-точь камни юбки sarpedon-v2. Кластерами поверх модулей ENV-U10, на пляж Sarpedon и вдоль швов грунта (gap 5) | 5 | низкие | Около 4 валунов — повторы, нужны поворот/масштаб/вариация тона. PBR-материал сделать матовым под Lumen. UE 5.8: проверить при добавлении |
| 2 | [Stylized_set_of_stones](https://www.fab.com/listings/ed78ebf9-1df4-4c3a-82d5-8d8b62f0067d) | Gairisa | Personal | нет | UE-пакет | Gap 3/5: 50 рисованных камней и 150 скинов; плоские плитки = галька и ступени у устья реки, столбчатые сколы = зубчатый низ юбки; есть сине-серые варианты под луну | 4 | средние | Рейтинг 1 при единственном отзыве — проверить качество. Часть скинов коричневые/снежные. UE 5.8: проверить при добавлении |
| 3 | [Free Pack - Rocks Stylized](https://www.fab.com/listings/a0746c4b-428b-4556-b4c9-98f70c2a30d4) | PolyOne Studio | Personal | нет | FBX, .blend, OBJ, USD, UE-пакет, +др. | Gap 3: 11 крупных гранёных валунов с читаемым силуэтом — опорные камни на углах юбки, у обрыва под водопадом; Marmoreal — под мох и лепестки. Есть .blend для модулей ENV-U10 | 4 | низкие | Исходный цвет почти белый: тёмная перекраска (vertex color/MI) и полоса мха. Гранёный стиль чуть «чище» концепта. UE 5.8: проверить при добавлении |
| 4 | [Stylized Rock Pack - 11 Low Poly Game Ready Boulders](https://www.fab.com/listings/ad410335-4055-4deb-ad8b-7db8715b3dff) | Hoda Art | CC-BY | нет | .blend | Gap 3/5: 11 рисованных валунов с трещинами — разброс по краю юбки, пляж, камни у костров. .blend стыкуется с env_kit_build | 4 | низкие | Одно превью. Светлый тон, тёмная перекраска. Через Blender → FBX → UE |
| 5 | [Stylized Environment Pack](https://www.fab.com/listings/ba992476-1ad4-4138-b2b0-abc92326fa6e) | Forge of Fantasy | CC-BY | нет | UE-пакет | Gap 5 (грунт Sarpedon): landscape-автоматериал со слоями камня, травы, песка, леса, земли — донор стилизованных текстур песка и земли для ground_splat | 3 | средние | Дневная сочно-зелёная палитра. Рассчитан на Landscape, а у нас splat на меше — текстуры извлекать и переподключать. UE 5.8: проверить при добавлении |
| 6 | [Rock Pack Vol 01](https://www.fab.com/listings/f66023d1-7951-4c62-8ad5-121b4b0df349) | Vampawn | Personal | нет | FBX, UE-пакет | Gap 3: полуреалистичные тёмно-серые скалы и плиты (5★, 8 отзывов) для нижнего яруса юбки, где на K1 мелко и в тени | 3 | средние | Ближе к фотоскану: матовый MI с упрощённой нормалью и стилизованным градиентом. UE 5.8: проверить при добавлении |
| 7 | [Stylized hex stones](https://www.fab.com/listings/e8949b46-6836-41e3-916e-466d3539de87) | Gairisa | Personal | нет | UE-пакет | Гексагональные базальтовые блоки: ступенчатый верх обрыва, каменные ступени у берега Sarpedon, вариация юбки | 3 | средние | Светло-серые с синей мультяшной тенью — перекраска; гексы бросаются в глаза при частом повторе. UE 5.8: проверить при добавлении |
| 8 | [Stylize Material V4](https://www.fab.com/listings/c95535e6-441f-45bf-9bfd-95e31d38806a) | Stone Material | CC-BY | нет | UE-пакет | Мастер-материал стилизованных поверхностей; доски — основа для палубы и «торца из балки» вместо прямого шва (gap 5) | 3 | средние | Пёстрый набор (звёзды, сердечки, розовое), полезна часть. Доски затемнить и состарить. UE 5.8: проверить при добавлении |

Ещё без NoAI (в JSON): [Free Sample - Realistic Rock Set (Limestone Rock Strata)](https://www.fab.com/listings/d2c74eb7-4278-40ab-861a-fdca41855f5a) — Слоистые известняковые блоки как референс формы для модулей ENV-U10; затемнённые — на дальнем плане юбки; [Marble Materials](https://www.fab.com/listings/a44a27a5-9b47-454c-b408-4ddc4ca88cf8) (ИИ-сген.) — Marmoreal: 3 бело-золотых мраморных материала 4K — основа для мраморной брусчатки периметра и плит балюстрады; [river stone floor](https://www.fab.com/listings/2cbbb69d-819b-4fc4-86fd-cf8dc0c78e93) — Gap 1/5: источник тонкой каймы гальки у устьев реки (сейчас чёрный гравий Y 22–24), осветлить и вписать в песок; [Campfire Stone Pack — 3 Sizes / PBR Ready](https://www.fab.com/listings/831443c8-cffc-4ec8-ba07-74a5594e1035) — Sarpedon: каменное кольцо с песчано-гравийной подложкой в 3 размерах — вместо «стикерных» песчаных дисков под кострами (gap 5) или кольцо под наш Tripo-костёр; [Low Poly Rock Set](https://www.fab.com/listings/055e31fb-d30e-44d8-aa4f-645206300887) — 5 маленьких лёгких камней (текстуры 256 px) для дешёвого разброса вдоль швов грунта и у кромки воды (gap 5).

**NoAI-кандидаты (превью не смотрели, визуально оценивает пользователь; в кадры для AI-ревью не ставить):**
- [Low Poly Cliffs & Rocks](https://www.fab.com/listings/5665a40c-01f5-42c4-8e2b-2c0d92ab686e) (Jay Creations, UE-пакет, стиль 3 по тексту) — По описанию единственный бесплатный пак модульных обрывов: 51 меш, <4k трис, собираются вращением и склейкой. Прямо закрывает gap 3. Визуально оценивает пользователь
- [Stylized Painterly Rock Pack](https://www.fab.com/listings/7dcf8d2d-7b03-46a0-acc0-497e6735b05a) (ShatterChron Interactive, UE-пакет, стиль 4 по тексту) — По описанию painterly-камни с мастер-материалом (мазки, мох по высоте) — ровно полоса мха на верхнем крае юбки Marmoreal. Визуально оценивает пользователь

**Отклонённые заметные.**
- Quixel Megascans (Nordic Coastal Cliff, Beach Boulder, Beach Sand With Pebbles, Japanese Mossy Boulder, Black Marble Tiles и др.): NoAI + фотореал; максимум референс, визуально оценивает пользователь.
- Glowbox3D a708070e и d1f178c3 (Settlers of Catan): aiForbidden=false в данных, но оговорка NoAI в описании — считаем NoAI.
- Stylized Rocks FREE Pack (baff54d1, Markus-3D), FREE Stylized Rocks Pack (StyleHex 3edeea52), GF Stylized Rocks (b258a107, 4.7★), Jayant Chakradhari (fbf1b818, 378c3348), JustCreate, Nillusion, Stylized Rock Diorama (238393e8): NoAI — по тексту стилизованные камни, визуально оценивает пользователь.
- Tiny Talisman Stylized Nature Pack (b066de06), Stylized Surface Lite (ca9af8a8), Epic Stylized Materials Pack (bb829b8f): NoAI.
- Stylized Hand-Painted Stone Wall (f03d1007): NoAI и aiGenerated одновременно.
- Stylized Rocks & Cactus (fbd77632): красная пустыня. Monument Valley Rock Tower, Cliff Rock Boulder Field, Rocks (Helindu.Art): фотореал/тяжёлые.
- Stylized Wood Material (9c2b4aea) — резной орнамент, не доски; Gray Pavement, Grass Material Pack — не наш стиль; Animal Foot Print Decal Pack — без пользы.
- Плоский мультяшный low-poly: Tinymen Basic Tiles, Dirt Grass Block, ToonLab, Low Poly Nature Lite. Red marble slab, Marble AquaBlue — не тот цвет; Short marble stairs, Beach Sand Scan 2 — фотоскан (CC0-библиотека уже закрывает).

**Пробелы, которые бесплатный Fab не закрывает, и чем их закрыть.**

| Пробел | Чем закрыть |
|---|---|
| Модульная стилизованная юбка/обрыв (прямые модули, углы, рваный низ) | ENV-U10 в Blender; валуны Fab (Gerardo Justel, PolyOne, Hoda Art) как акценты сверху |
| Рисованная тайлящаяся мраморная брусчатка Marmoreal | CC0-мрамор (ambientCG/Poly Haven) + своя разметка плит / запекание в Blender |
| Тёплый стилизованный песок с рябью и мокрой кромкой | CC0 + подкраска (gap 5) или слой Sand из Forge of Fantasy Stylized Environment Pack |
| Стилизованные палубные доски и балки | частично Stylize Material V4 + доработка; иначе CC0-дерево с тонировкой |
| Декали: мох, лепестки на камне, пена, мокрый песок, трещины | свои декали (imagegen/CC0) |
| Камень с мхом (верхняя полоса юбки Marmoreal) | vertex color / height-blend в нашем MI |

### 4.3. Вода, небо, атмосфера, VFX

*Охват:* вода и водопад, ночное небо, туман, светлячки, огонь, боевые и магические эффекты.

**Shortlist.**

| # | Ассет | Издатель | Лицензия | NoAI / ИИ | Формат | Что закрывает | Стиль 1–5 | Усилия | Риски |
|---|---|---|---|---|---|---|---|---|---|
| 1 | [Particles and Wind Control System](https://www.fab.com/listings/f673ef70-1c66-4c7f-8751-9f84ddb8b083) | Dragon Motion | Personal | нет | UE-пакет | Gap 8 (атмосфера): светлячки над лесом и пляжем Sarpedon, тёплые огоньки и пыль в лунном свете Marmoreal, ветер для листвы. Niagara, 4.8★ (164 отзыва) | 4 | низкие | Найден живым поиском Fab (в harvest нет). Пак 2019 г., недавно обновлён. Ограничить число частиц и яркость под эталон High/Lumen. UE 5.8: проверить при добавлении |
| 2 | [Free Niagara Particles (CC BY 4.0)](https://www.fab.com/listings/183732bc-c2fb-465c-9453-f70a1ce7ba2c) | SoftTofuVFX | CC-BY | нет | UE-пакет | Падающие лепестки сакуры у колоннады Marmoreal (перекрасить листья в розовый), перья Harpy, искрящиеся частицы магии Мерлина | 4 | низкие | Отзывов нет, найден живым поиском. UE 5.8: проверить при добавлении |
| 3 | [Stylish Fire VFX (Free asset)](https://www.fab.com/listings/01e8534c-5877-4ce2-8948-9a696100de11) | VfxSTOCK | Personal | нет | UE-пакет | Мультяшный стилизованный огонь (4+ Niagara): костры Sarpedon (Tripo-campfire), пламя фонарей и постаментов Marmoreal, факелы форта. Лучше всех попадает в Painted Miniature | 5 | низкие | Свет в Niagara выключить и ставить свои point lights (бюджет 60/30 FPS). UE 5.8: проверить при добавлении |
| 4 | [Free Sparks & Embers Pack](https://www.fab.com/listings/48e20eb7-0812-4670-b206-44d3b5aa8a01) | CGHOW | CC-BY | нет | UE-пакет | Искры и угольки над кострами Sarpedon и у фонарей; искры удара меча по щиту при атаке Артура | 4 | низкие | Опубликован 2026-06, отзывов нет. UE 5.8: проверить при добавлении |
| 5 | [Stylized Sword Trails VFX](https://www.fab.com/listings/bd2ba790-7266-49f3-bb4f-8049f6797c01) | SERLO | Personal | нет | UE-пакет | Трейлы меча King Arthur и рубящих атак Harpy: стилизованные дуги Niagara, 4.7★ (27 отзывов) | 4 | средние | Привязка к сокетам меча и анимациям AM_*. Цвета в палитру C-11 (золото, серебро, синий). UE 5.8: проверить при добавлении |
| 6 | [Basic VFX Pack (Free)](https://www.fab.com/listings/75698e52-edfc-4f76-a86c-b4f26fcf5a29) | VfxSTOCK | Personal | нет | UE-пакет | 15+ эффектов (орбы, щиты, купола, вихри): магия Мерлина, защитные карты, баффы. Тот же автор, что Stylish Fire — единый стиль. 5.0★ (8 отзывов) | 4 | средние | Местами неоново-яркий: перекраска и снижение emissive под ночь. UE 5.8: проверить при добавлении |
| 7 | [Water Materials](https://www.fab.com/listings/063155ea-d9d2-4f29-b09f-33270b0bc861) | tharlevfx | CC-BY | нет | UE-пакет | Gap Sarpedon 1: 12 водных материалов + дешёвые варианты (океан с прибоем, река, водопад) с vertex paint — на нашу waterfall-меш, речку и кромку пляжа. 4.6★ (341 отзыв) | 3 | средние | Ближе к реализму: упростить нормали, ступенчатая окраска, пена-ободок. Оригинал под UE 4.13+, обновлялся; на 5.8 Substrate/Lumen могут изменить прозрачность — проверить при добавлении |
| 8 | [Niagara Slash](https://www.fab.com/listings/9baf4a11-d63a-4d9c-8ee1-bfedfd3eb696) | UE Game Work | Personal | нет | UE-пакет | Hit/slash-импакты: вспышка с искрами при попадании (меч Артура, когти Harpy). 4.7★ (6 отзывов) | 3 | низкие | Опубликован 2026-09. Блики яркие, снизить. UE 5.8: проверить при добавлении |

Ещё без NoAI (в JSON): [Mixed VFX](https://www.fab.com/listings/6518971c-c8ca-47d7-8611-1ff068b78dd5) — 17 снарядов со вспышками и попаданиями (дальние атаки Medusa и Мерлина), 5 слэшей, 7 огней, 5 взрывов — запасной боевой набор. 4.4★ (16 отзывов); [Stylized Smoke VFX - Fully Customizable](https://www.fab.com/listings/172235df-7a05-4d60-ac7b-23472e530ee7) — Стилизованный дым над кострами Sarpedon и от пушек корабля, низовая дымка по краю подноса; [Mayu's Orb VFX Collection](https://www.fab.com/listings/d13b3d78-9768-4952-b8e5-4cb476fa5b9f) — 5 орбов: тёмно-фиолетовый + каменная пыль = основа взгляда Medusa; водный/плазменный = снаряд Мерлина; [Mayu's Basic VFX Pack](https://www.fab.com/listings/35636320-5ff4-42cc-a233-34ee16a4a7a4) — Базовые Niagara-эффекты: стилизованная струя воды (идея для низа водопада и брызг), огонь, искры — донор для своих эффектов; [Light Vortex Shader - Dynamic Light Effects](https://www.fab.com/listings/49f5d158-1797-478e-94ba-858b331db5a9) — Световой вихрь и магический круг (light function на spot light): маркер каста Мерлина, зона взгляда Medusa, подсветка клетки. 4.2★ (20 отзывов); [Starfield FREE](https://www.fab.com/listings/349d203e-aac2-40bc-8c92-7a3f6f89cf31) — Gap 8: звёздный купол с BP-управлением для ночного неба за диорамой и в отражениях воды; [MOON AND CLOUDS](https://www.fab.com/listings/55e7d583-35b9-471e-90b1-61c861fdd6ac) — Gap 8: мультяшная Луна с пухлыми облаками как «театральный» проп-задник миниатюры или форма для своей расписной луны.

**Отклонённые заметные.**
- Stylized Lake Village (Epic, a467507b): идеальный референс ночи со стилизованной водой, но только UEFN — в UE 5.8 не импортируется.
- Good SKY (6eb8de95, 320 отзывов), Stylized Volumetric Clouds Shader (3dcea533): NoAI — сильные кандидаты на небо и облака, визуально оценивает пользователь.
- Vefects: Stylized Fire VFX, Perfect Fire VFX, Candle VFX, Easy Shockwaves, Easy Impact Frames, Anime Stars: NoAI.
- FX Variety Pack (Kakky, 262 отзыва), Water Planes (Epic), Swamp Water (Quixel), StylizedWeather, Fog Area, QMS Cartoon Skybox, Cloudz Hi5, [18] Free Spells Niagara, Niagara Examples Pack: NoAI.
- Lotus Swamp (Kigha, CC-BY): 3D-перенос чужой 2D-работы — риск по правам, к тому же цельная сцена.
- Stylized Waterfall & Lake Landscape: низкое качество. Fire Effect VFX (LitumVFX): aiGenerated, сине-зелёный огонь. Nebula Space Forest Skybox: автор пишет про AI, sci-fi.
- Atmospheric Skybox, HDRI/SKY BOX 8K: дневной фотореал. Stylized Clouds Pack Vol 07/09: воксельные облака. MagicCircle VFX: чужой аниме-IP.
- Только Unity: Toon VFX Pack, Campfires & Torches (PILOTO), Game VFX Magic Circle, RPG Sprite Sheet, Fog Particles, Water Shader URP.
- Free Torch Fire (7437ae0c), Free Flame Vfx Pack (30953ced): рабочие, но реалистичнее Stylish Fire — запасные.

**Пробелы, которые бесплатный Fab не закрывает, и чем их закрыть.**

| Пробел | Чем закрыть |
|---|---|
| Стилизованный шейдер реки, океана и прибоя без NoAI | Water Materials (tharlevfx) с доработкой, либо свой toon-материал на базе плагина UE Water / нашей waterfall-меши |
| Расписное ночное небо (sky dome) в стиле Painted Miniature | своя панорама через imagegen на sky-сфере + звёзды Starfield FREE |
| Низовой туман и дымка | встроенные ExponentialHeightFog и Local Fog Volume + Stylized Smoke VFX |
| Эффект окаменения (взгляд Medusa) | собрать: Mayu's Orb (тёмно-фиолетовый) + Light Vortex + свой dissolve-материал в камень |
| Брызги и пена под водопадом и у прибоя | частично Mayu's Basic VFX и Water Materials; остальное своё |
| Ночной HDRI | Poly Haven CC0 — только для освещения, не как видимый фон |

### 4.4. Marmoreal: архитектура и пропсы

*Охват:* колонны, арки, балюстрады, фонтаны, статуи, вазы, фонари.

**Shortlist.**

| # | Ассет | Издатель | Лицензия | NoAI / ИИ | Формат | Что закрывает | Стиль 1–5 | Усилия | Риски |
|---|---|---|---|---|---|---|---|---|---|
| 1 | [Stylized Tōrō japanese lantern](https://www.fab.com/listings/2d92680a-fb96-4546-99d4-04029d172505) | Lisandro Rodriguez | CC-BY | нет | FBX | Marmoreal: садовые фонари между вишнями и вдоль дорожек — дополнительные тёплые источники и светящаяся голова фонаря (gaps #13, #14). Рисованная текстура, хорошо читается ночью | 4 | низкие | Японский мотив и красная лента рядом с греко-римским дворцом: ленту убрать/приглушить. Мох слегка зеленит. Одно превью |
| 2 | [Stylized Сolumn, ancient ruins](https://www.fab.com/listings/18f1a830-3694-4618-a63f-38c84aae38d5) | Lowpoly89 | Personal | нет | FBX | Marmoreal: ионическая колонна, обломок, плиты и кладка — китбаш для пустых боковых полос и углов подноса (gap #6), руинный акцент у колоннады | 4 | средние | Текстура «подводная» (зелёно-золотой мох): перекрасить в белый/розоватый мрамор, 3 атласа |
| 3 | [Low Poly Greek Ruins](https://www.fab.com/listings/769148c8-2d09-4df7-ab5b-b702445539e7) | libblekibble | CC-BY | нет | FBX | Marmoreal: фрагмент колоннады с антаблементом и плющом — руинная колоннада по бокам или за дворцом, колонны для китбаша | 3 | средние | Плоский low-poly после decimate, грязная сетка; нужен наш расписной мрамор; зелёную подставку отрезать |
| 4 | [Marble Vase 001 (+ Marble Vase 002, 8a54bbdb-e740-4aca-b777-43cafadbba8e)](https://www.fab.com/listings/9512a274-8d76-489f-a9e4-b5574c47b3cb) | PK 3D Art | CC-BY | нет | GLB, OBJ | Marmoreal: вазы-кратеры на ступенях и постаментах, с цветами (gaps #6, #12). Силуэт почти как урны концепта; у 002 гадрон-декор | 3 | низкие | Глянцевый PBR-мрамор 4K: матовый расписной мрамор и пересэмплинг. Цветы отдельно. Vase 002 только obj |
| 5 | [Ruins Greek Doric Pillar](https://www.fab.com/listings/7b3610c5-8ea9-428d-ac7b-f45b26328769) | Jose Salas | Personal | нет | FBX, USD | Marmoreal: разрушенная дорическая колонна из барабанов (разбросать как упавшие) — угловые акценты у края утёса; развёртка готова под трипланарный мрамор | 3 | средние | Текстур нет. Сканоподобная неровная сетка, на K1 может шуметь — decimate |
| 6 | [Wall Lantern](https://www.fab.com/listings/a9f8b364-6ae6-4887-8d12-db16493c6142) | Mikhail Kadilnikov | CC-BY | нет | FBX | Marmoreal: квадратный стеклянный фонарь с крышкой, как на постаментах концепта — головы фонарей для доп. тёплых точек (#14) и светящегося матового стекла (#13) | 3 | низкие | Чёрный PBR-металл: тёплая бронза и эмиссив стекла. Крепление настенное, для постамента нужна ножка |
| 7 | [Free Prop Bundle](https://www.fab.com/listings/f0e98745-eba7-40dd-81c2-2d160598d042) | CGI-CORE-Center | CC-BY | нет | UE-пакет | Обе карты: по описанию 10 фонарей, 4 жаровни, 7 канделябров, факелы, свечи, люстры, 15 бочек, 17 ящиков — тёплые источники (#14) и наполнение лагеря Sarpedon | 3 | средние | На превью видны только бочки и ящики, фонари визуально не проверены. Ссылку на Google Drive из описания не открывать. Полустилизованное дерево. UE 5.8: проверить при добавлении |
| 8 | [Ancient Greek Temple](https://www.fab.com/listings/f1339798-76b8-4202-9e8d-3640ca6db78b) | FOXYSCA | CC-BY | нет | FBX | Marmoreal: круглая беседка-толос с коринфскими колоннами и балюстрадой — угловой акцент сада или образец балюстрады для своего модуля | 3 | средние | Мидполи, тёмный PBR, надпись на фризе — перекрасить. 2.5★ (2 отзыва). Может быть крупной для периметра |

Ещё без NoAI (в JSON): [Blood Temple](https://www.fab.com/listings/f46e4d4e-e2bf-49f2-a7bd-316b3279cdd4) — Marmoreal: белые мраморные арки и колонны ротонды для китбаша, статуя ангела как садовая скульптура; [Free Stone Sphere](https://www.fab.com/listings/2ec3a87a-222b-444d-a9d8-981df1ffb927) — Marmoreal: шар-навершие угловых столбиков (gap #6: ball-finial posts на 4 углах), стилизованная рубленая фактура; [Stylized Low Poly Ancient Temple – Game Ready with LODs](https://www.fab.com/listings/fb9e06f5-c921-48c6-baf1-7b83b7edcfda) — Marmoreal: колонны и фронтон с LOD для китбаша заднего плана за дворцом; [Hebe Fountain - Animated Courtyard Fountain](https://www.fab.com/listings/cd1dc9b7-be6e-46c8-8e7d-7367b1c4ac92) — Marmoreal: фонтан со статуей Гебы, анимированная вода и звук; статуя отдельно как садовая скульптура; [Free Braziers](https://www.fab.com/listings/8078b6a9-32c5-46b7-873c-47ebaafd2930) (ИИ-сген.) — Тёплые источники (#14): 3 стилизованные жаровни у входа во дворец Marmoreal или в лагере Sarpedon.

**NoAI-кандидаты (превью не смотрели, визуально оценивает пользователь; в кадры для AI-ревью не ставить):**
- [Lantern (Free Low Poly Hand-Painted Lantern)](https://www.fab.com/listings/51e37034-603d-42e1-a955-b4834ddb99e1) (Jen Abbott, FBX, .blend, OBJ, стиль 4 по тексту) — По тексту рисованный low-poly фонарный столб — потенциально лучшее попадание в стиль среди фонарей. Визуально оценивает пользователь
- [Stylized MOBA Fountain Base](https://www.fab.com/listings/04c88f27-b44d-4175-8732-9b4936103e10) (Agustin Honnun, FBX, стиль 3 по тексту) — По тексту стилизованное основание фонтана/пьедестал — единственный стилизованный фонтан. Визуально оценивает пользователь

**Отклонённые заметные.**
- Short marble stairs (4fb1673c): фотоскан 8K — ступени дешевле сделать в Blender. Stone Arch Pillars - Ruins: хайполи кирпич, средневековье.
- Caryatid, Faune au Chevreau, Marble bust of Hadrian, Statue retopology: фотосканы статуй (стиль 2) — статую Медузы лучше делать в Tripo.
- Medieval Fountain Empty (18418ed8): реалистичный, запасной; Saepinum Fountain Griffin: скан руин.
- PBR Greek Pottery: мелкая для периметра. Ancient Ruins – Free Asset Pack (Hyperdense): aiGenerated, красный кирпич.
- Lowpoly Temple Town, Japanese Torii Gate, Japanese Castle PSX, pagoda scene: уводят Marmoreal в японскую тему.
- Gazebo, Garden Seating, Stylized Decorative Balcony, Garden Lattice Pack: современные/модерн, не мраморный дворец.
- Victorian/Chinese/Garden/City/керосиновые лампы и прочие фонари: реализм или чужая эпоха; Ornate lantern (d2f9bc34) — восточный запасной.
- Mystic Runic Stone Brazier: aiGenerated, данжен. Корейские дворцы KHS/KCISA: фотосканы, огромные. Egypt Statues, Fantasy Desert Ruins: пустыня.
- NoAI (визуально оценивает пользователь): Quixel Japanese Stone Lantern и японские фонари/Komainu, Corinthian Column, Paestum column, Greek Pillar, Greco-Roman Ornamental Sculpture, Full temple of Apollo, White Marble bench, Roman Marble Table, Desert Ruins, Stylized Fantasy Provencal, Epic Zen Garden, Tori Gate Enviroment, Knight Statue.

**Пробелы, которые бесплатный Fab не закрывает, и чем их закрыть.**

| Пробел | Чем закрыть |
|---|---|
| Стилизованная мраморная балюстрада со столбиками и шарами (gap #6) | модуль в Blender (балясина, перила, столбик) + шар Free Stone Sphere |
| Статуя Медузы/горгоны в рисованном стиле | Tripo или imagegen → Tripo |
| Фасад дворца с окнами и тёплым коридором за арками (gap #12) | наш palace back wall (доработка) |
| Стилизованный мраморный фонтан | без NoAI только реалистичные (Hebe, Medieval Fountain) — Tripo/Blender или NoAI MOBA Fountain Base по решению пользователя |
| Широкая мраморная лестница | Blender, наш мраморный материал |
| Розы и цветы для ваз | домен растительности (Fantasy Botanical, Stylized Garden, Lupines) |

### 4.5. Sarpedon: пропсы

*Охват:* корабль, причал, бочки и ящики, пушки, частокол и форт, лагерь, сокровища.

**Shortlist.**

| # | Ассет | Издатель | Лицензия | NoAI / ИИ | Формат | Что закрывает | Стиль 1–5 | Усилия | Риски |
|---|---|---|---|---|---|---|---|---|---|
| 1 | [Smuggler’s Cove Asset Pack](https://www.fab.com/listings/a0935013-5959-47c2-97d9-75478ded0e6b) | Poly Haven | CC-BY | нет | UE-пакет | Sarpedon: корабль с мачтами, парусами и такелажем (gap «паруса/такелаж»), морские пушки и ядра, ящики, бочки, сундуки, сваи и настил причала, стены и круглая башня форта | 3 | средние | Фотореал, корабли 100–150k трис: перекрас под Painted Miniature (roughness, тонирование, упрощение текстур), возможно децимация. Дневной тропический свет. UE 5.8: проверить при добавлении (или glTF/blend с polyhaven.com) |
| 2 | [GanzSe FREE Camping - Fantasy Low Poly Props](https://www.fab.com/listings/d03138fe-7e29-4b3d-9ea8-8ba67f24f845) | GanzSe | CC-BY | нет | UE-пакет | Лагерь у костров Sarpedon: палатка-шатёр, тренога с котлом, костёр в кольце, поленница, бочка, сундук, фонарь, баннер, скамья | 3 | низкие | Плоский low-poly проще нашей геометрии: градиент ручной росписи. Яркий зелёный баннер и флажки перекрасить. UE 5.8: проверить при добавлении |
| 3 | [Barrel: Stylized Wooden](https://www.fab.com/listings/870ce80d-e31a-4251-8307-9c07839ea3ae) | Cramb Studio | Personal | нет | FBX, UE-пакет | Бочки на палубе, пляже и у форта: несколько вариантов (лежачие/стоячие), скульптурная резьба по дереву — ближе всех к ручной росписи | 4 | низкие | Металл обручей чуть глянцевый — поднять roughness. Заявлено UE 5.0+, 5.8 проверить при добавлении |
| 4 | [Campfire Stone Pack — 3 Sizes / PBR Ready](https://www.fab.com/listings/831443c8-cffc-4ec8-ba07-74a5594e1035) | BabyOfficiel | Personal | нет | FBX | (см. домен «Скалы, обрывы, грунт») Sarpedon: каменное кольцо с песчано-гравийной подложкой в 3 размерах — вместо «стикерных» песчаных дисков под кострами (gap 5) или кольцо под наш Tripo-костёр | 3 | низкие | Полуреалистичные камни и яркие брёвна: брёвна убрать, камни затемнить. Огня в комплекте нет |
| 5 | [Medieval Village Props – Furniture, Containers & Clutter](https://www.fab.com/listings/b8fc5a33-8dce-48d1-8175-1015aa4c9436) | DuplexG | Personal | нет | UE-пакет | Наполнение лагеря и причала: бочки, ящики, корзины, столы со скамьями, кружки, фонарный столб, клетка, тележка, жаровня, колодец (70 пропсов) | 3 | низкие | Чистый полуреализм; перекрас под роспись желателен. UE 5.8: проверить при добавлении |
| 6 | [Old Cannon](https://www.fab.com/listings/7996ed99-0b73-4133-ab41-e541e66c5b2a) | ClearMeshStudio | CC-BY | нет | FBX | Корабельная пушка на деревянном лафете с колёсами, брюками и ядрами — ряд пушек по борту, как в концепте | 3 | низкие | Демо-подставку убрать; проверить, что в бесплатном архиве есть модель с текстурами (описание ссылается на платный туториал). Ствол тонировать темнее |
| 7 | [Pirate Chest Ohoi!](https://www.fab.com/listings/88d4f5cb-c5d7-4a97-af6b-92116f3ae74c) | Bouncelight | CC-BY | нет | FBX | Сундук с сокровищами на палубе или пляже, крупный читаемый силуэт | 3 | низкие | Полуреалистичное дерево; сундук закрыт, золото отдельно |
| 8 | [Dock Pier](https://www.fab.com/listings/1c5a08b3-008e-4090-aa89-6902914ba895) | Pixol3d | CC-BY | нет | FBX | Причал и пирс на сваях у реки и бухты Sarpedon, мостки к кораблю | 3 | средние | Серое полуреалистичное дерево — тонировать тёплым; хижину, возможно, отрезать |

Ещё без NoAI (в JSON): [Free Palisade logs](https://www.fab.com/listings/740dd47b-a35b-441b-875b-e26e7e1a3994) — 3 заострённых бревна (334 полигона) — частокол любой длины вдоль периметра; [Ruined Tower Set (3 models)](https://www.fab.com/listings/f541f4f5-2653-400a-80aa-e81b301223eb) — Руины форта: 3 обрушенные круглые каменные башни разной высоты (угол с костром в концепте); [Advanced Village Pack](https://www.fab.com/listings/250a5622-d5fd-49fc-b1c4-0550a444e117) — Массовый деревянный кит для лагеря и форта: заборы, плетни, телеги, бочки, ящики, постройки, костры; [Pirate Base](https://www.fab.com/listings/fb9b6d20-a85a-418e-bf21-5a7c99d04b3e) — Китбаш: хижина на сваях, пиратский флаг, бочки, черепа, лодка — тематически ближе всех к «пиратской бухте»; [Wooden Watchtower lvl 1-3](https://www.fab.com/listings/d5f58d41-9c70-430d-9894-aa7173666a45) — Деревянная сторожевая вышка у палисада (3 уровня проработки); [Free Stylized Ship Wheel](https://www.fab.com/listings/ca9ae76b-ea1f-4c95-8514-54d7a4f40ce0) — Штурвал на корме — мелкая деталь палубы; [Shipwrecked Boat](https://www.fab.com/listings/3ade308e-f346-418d-94fc-c0e0865dfe68) — Разбитая лодка на пляже (как в концепте) — скорее референс формы или основа для ретопологии.

**Отклонённые заметные.**
- Age of sail Blender ship (NelloF, 7fc31661): NoAI — тематически лучший корабль (наполеоновская эпоха, полный такелаж), визуально оценивает пользователь.
- Harbor Props Pack vol.1, Stylized Cannon (Infinity3DGame), Cartoon Cannon (BatTheCat), Stylized Wooden Props Sample Pack (Lost Frames), Low Poly Survival Asset Pack, Modular Low poly Fences, Medieval Defense Spikes, Old West Fort (Mini): NoAI.
- Stylized Treasure Chest Scene, Stylized Pirate Coin, Pirate Book of Treasure, Stylized Barrel (Nemek), Stylized Wooden Barrel (Nillusion), Treasures VOL.1 (Dekogon): NoAI.
- Quixel (Palisade Spike, Campfire, Wooden Barrel/Crate, Old Cannon Trailer, Beach Rocks): NoAI + фотореал.
- Ancient Ruins (Hyperdense), Stylized Anchor – Tier I, Free Braziers: aiGenerated; Medieval Campfire (Zombified): NoAI + aiGenerated.
- Stylized Lake Village (Epic): только UEFN. pirate ship (Jmystigan): игрушечный, слабее нашего Tripo-корпуса. Low Poly Cargo Ship: современный.
- Medieval Wooden Ships (Drakkars): викинги, разве что донор парусов. Pirate Hideout, Mr. Craby's Lighthouse, Low Poly Lighthouse Scene: мультяшные диорамы.
- Non-realistic Cannon: кислотная палитра; Vintage Cannon: полевая; Wall Cannon, Beach campfire (Axonite), Shipwreck-сканы Arqueomodel3D: фотограмметрия.
- Smuggler's Cove есть и на polyhaven.com под CC0 (glTF/blend, без атрибуции) — альтернативный источник.

**Пробелы, которые бесплатный Fab не закрывает, и чем их закрыть.**

| Пробел | Чем закрыть |
|---|---|
| Пиратский корабль в стиле Painted Miniature с парусами и такелажем | перекрас Smuggler's Cove или доработка Tripo-корпуса с верёвочной оснасткой в Blender |
| Бухты верёвок, канаты, сети, ванты | Blender (кривые с bevel + верёвочная текстура CC0); у нас есть Tripo rope |
| Мешки и джутовые тюки | Tripo или Blender (cloth/sculpt) |
| Россыпи золота, открытый сундук с сокровищами | Tripo; монеты — Blender-инстансы |
| Стилизованная шлюпка и обломки на берегу | Tripo (по силуэту из Shipwrecked Boat) |
| Пляжные коряги, водоросли, ракушки | Tripo / Blender, мелкий масштаб |
| Модульный частокол с воротами и перевязкой | наш Tripo palisade + брёвна Joan Lahoz, ворота в Blender |

### 4.6. Доска, UI, персонажи, звук

*Охват:* стол и рамки, UI, шрифты, звук, герои и их оружие.

**Shortlist.**

| # | Ассет | Издатель | Лицензия | NoAI / ИИ | Формат | Что закрывает | Стиль 1–5 | Усилия | Риски |
|---|---|---|---|---|---|---|---|---|---|
| 1 | [The Wizard](https://www.fab.com/listings/fd57e5f9-cf0f-4e16-a1b8-8f8e8d2aca62) | Aminchok | CC-BY | нет | FBX | Merlin: седой маг в синей мантии с посохом и голубым огнём на круглой подставке — буквально настольная миниатюра; референс или замена Tripo-модели | 4 | средние | Описание пустое: риг, полигонаж, UV неизвестны; вероятно, нужен риг и ретаргет. Подставку с надписью удалить |
| 2 | [Medusara - The Coiled Sovereign Free Version (Idle Animation)](https://www.fab.com/listings/eb4bb1de-7111-4008-a8b1-e6e5621266f9) | PolyReady | Personal | ИИ-сген. | .blend, FBX, OBJ | Medusa: королева-змея со свёрнутым хвостом, риг и idle — референс или замена Tripo-Медузы | 3 | средние | aiGenerated=true (по словам автора — только улучшение текстур). Песочно-реалистичная палитра. Только idle и одна текстура. Руки-змеи вместо каноничного лука |
| 3 | [Harpy Assassin Free version (Idle Animation)](https://www.fab.com/listings/f3236252-d985-4775-8617-0f00bea931bd) | PolyReady | Personal | ИИ-сген. | FBX, OBJ, .blend | Harpy (x3): крылатая охотница с ригом и idle — референс крыльев/позы или замена Tripo-гарпии | 3 | средние | aiGenerated=true (AI-доработка текстур). Тёмный полуреализм. Только idle. Тяжёлые крылья x3 — бюджет |
| 4 | [GanzSe FREE Weapons - Fantasy Low Poly Pack](https://www.fab.com/listings/8d570eec-44d7-40eb-b02d-c77600146600) | GanzSe | CC-BY | нет | UE-пакет | King Arthur: меч и щит, оружие и аксессуары, стилизованный low-poly | 3 | низкие | Flat-стиль проще painterly, перекраска. Excalibur как такового нет. UE 5.8: проверить при добавлении |
| 5 | [Free Prop Bundle](https://www.fab.com/listings/f0e98745-eba7-40dd-81c2-2d160598d042) | CGI-CORE-Center | CC-BY | нет | UE-пакет | (см. домен «Marmoreal: архитектура и пропсы») Обе карты: по описанию 10 фонарей, 4 жаровни, 7 канделябров, факелы, свечи, люстры, 15 бочек, 17 ящиков — тёплые источники (#14) и наполнение лагеря Sarpedon | 3 | средние | На превью видны только бочки и ящики, фонари визуально не проверены. Ссылку на Google Drive из описания не открывать. Полустилизованное дерево. UE 5.8: проверить при добавлении |
| 6 | [Armored Guard Knight Rig](https://www.fab.com/listings/dfc7d8fe-6b8d-476c-876a-7574dbe023d4) | DM-913 | CC-BY | нет | .blend | King Arthur: референс доспеха и силуэта или ригнутая основа под перекраску | 3 | высокие | PBR-полуреализм, только .blend; нет короны и плаща |
| 7 | [Stylized magic staff of Water (game ready)](https://www.fab.com/listings/0dfd65ff-b191-4051-b121-c3fd607f3a0e) | LOLIPOP | CC-BY | нет | FBX | Посох Merlin: изогнутое дерево с синим кристаллом и свечением, 2K, хорошо ложится на лунный свет | 4 | низкие | Emissive настроить в нашем материале, масштаб под миниатюру |
| 8 | [Stylized Hand-Painted Diorama House - Game Ready](https://www.fab.com/listings/60466a7f-7d87-4cdb-bbe8-16b3f47fe3a7) | IGANIX_ART | CC-BY | нет | FBX, USDZ, GLB | Стилевой референс hand-painted диорамы (роспись края подставки, дерево, хвоя) для доводки T2b и периметра; ели — после перекраски в лес Sarpedon | 4 | низкие | Тематика не наша, напрямую не ставить |

Ещё без NoAI (в JSON): [Snake Cobra (Head Up) Animated](https://www.fab.com/listings/bc208c6c-9b64-433b-8824-62431223c061) — Medusa: ригнутая кобра с синусоидальным движением — референс анимации змей в волосах или змей-декора; [Board Game Essentials](https://www.fab.com/listings/b147ae21-6b56-4d7c-bbb5-f86d3e6b2ab1) — Болванки для стола: кубики, шейкер, жетоны, карта — под наши материалы; [Caves and Dungeons](https://www.fab.com/listings/9ef17452-1566-4cb8-a8a3-d41d2c9549ed) — Звук: 14 зацикленных фэнтези-амбиентов — фон матча или меню; единственный звуковой пак без NoAI в harvest.

**NoAI-кандидаты (превью не смотрели, визуально оценивает пользователь; в кадры для AI-ревью не ставить):**
- [Hand Painted Paladin Knight - Rigged & Game Ready](https://www.fab.com/listings/a98fd943-5a62-4544-bcc7-5dbb5decc2e7) (silverdelivery, FBX, .blend, стиль 4 по тексту) — King Arthur: по тексту ригнутый hand-painted паладин, по стилю ближе всех к Painted Miniature. Визуально оценивает пользователь
- [Lowpoly Modular Armors - Free - MEDIEVAL FANTASY SERIES](https://www.fab.com/listings/d32023d6-cc7c-4a6b-bbc6-b0821c3d3391) (Polytope Studio, UE-пакет, стиль 3 по тексту) — King Arthur: по тексту модульные доспехи на скелете UE5 (анимации манекена сразу). Визуально оценивает пользователь
- [Procedural Sea Waves](https://www.fab.com/listings/2b11f781-970a-4c37-9ab2-90d16137555f) (Timofei Shukshin, UE-пакет, стиль 3 по тексту) — Звук Sarpedon: процедурный прибой на MetaSound для ночной бухты. Оценивает пользователь на слух
- [Free UI Soundpack](https://www.fab.com/listings/4fe9dac3-1db6-4825-ad97-20f121032738) (Cyrex Studios, UE-пакет, стиль 2 по тексту) — UI-клики; ближе к настолке наборы Wood Block и Coffee. Оценивает пользователь на слух

**Отклонённые заметные.**
- Settlers of Catan Board Game (d1f178c3, Glowbox3D): оговорка NoAI в описании + чужой бренд.
- Medieval Board Game, Map Board & Telescope, Wooden Picture Frames, Worn wooden frame, CC0 Picture Frame 2, Ornate Cherub Mirror: реализм; наши T2b и рамка 002 лучше.
- Free Wooden Table, Old Wooden Table: простые реалистичные столы. King's Throne Diorama, Puzzle Islands At Night, Halloween on Yuki: чужие темы, разве что референс подачи.
- Chess Pack (ithappy), Stylized Battle Wizard, Wizard for Battle Polyart/PBR (Dungeon Mason — большой набор анимаций, вопрос к пользователю), Elf Male Wizard, Paragon Gideon/Greystone, Hand Painted Female Paladin: NoAI.
- Shadow Knight Armor, Stylized Female Character (Olympus Guardian), Dark Witch, Vampire, Draconic Sorceress, Selian Siren: не наши герои или не наш стиль.
- FREE Battlemage Wizard, Fox/Cat wizard, Wizard (f76da595), Rpg Magic Staff Pack: aiGenerated (Meshy и пр.), не лучше наших моделей.
- Thornblade Sword, FREE Sword + Animation, Snake Stylized Model, TCobra, Snake Stylized Watercolor (NoAI), Cartoon Yellow Canary, Bronze votive shield, GanzSe Character Accessories: мимо задачи.
- Звук/UI NoAI: SCI-FI UI SOUND EFFECTS PACK, Music For Your RPG, Outrider's Oath, Dark Dungeon Ambient, UI Effect Function Library / Lab / UI Navigation 3.0 (инструменты, не арт).

**Пробелы, которые бесплатный Fab не закрывает, и чем их закрыть.**

| Пробел | Чем закрыть |
|---|---|
| Fantasy UI kit (рамки, панели, кнопки, полоски HP, иконки карт) | в harvest нет; отдельный поиск (fantasy gui / rpg ui / card frame) или свой UMG-кит |
| Шрифты | вне Fab: Google Fonts под OFL (Cinzel, IM Fell, MedievalSharp) — проверить лицензию |
| Амбиент по биомам (сверчки, лес, прибой, костёр, ветер) | freesound.org CC0 / Sonniss GDC bundle; на Fab — отдельный поиск |
| Mocap и анимации (меч, лук, каст, полёт, hit/death) | Epic Game Animation Sample / анимации UE5-манекена, Mixamo с ретаргетом |
| Каноничная Медуза (лук, змеи в волосах), Артур, гарпия в painterly-стиле без NoAI/aiGenerated | продолжать Tripo-героев; Wizard/Medusara/Harpy Assassin — как референсы |
| Стол, доска, рамка диорамы | наш Blender-пайплайн (T2b, рамка 002, задняя стена) — лучше всего, что есть на Fab |
| Токены, кубики, карты в стиле Unmatched | делать самим |

## 5. Порядок действий

**Кто что делает.** Вход в Epic-аккаунт, капчи, принятие лицензии (кнопка добавления в библиотеку на Fab) и выбор уровня Personal делает **пользователь**. Агенты не вводят пароли и не проходят капчи. Покупок нет: все пики бесплатные. Если цена листинга внезапно стала ненулевой (бесплатные акции заканчиваются, например Palms Pack — до октября 2026), такой листинг пропустить.

1. **Подтвердить список.** Пользователь просматривает топ-10 и волну 11–15. Отдельно, по желанию, решает по NoAI-кандидатам: смотрит их сам и, если берёт, они живут только на отдельном варианте уровня, без AI-ревью кадров.
2. **Добавить в библиотеку (пользователь).** Fab в Epic Games Launcher или на fab.com: «Добавить в мою библиотеку» для каждого пака, уровень лицензии — Personal (Личное).
3. **UE-пакеты (формат UE-пакет).** Launcher → Библиотека → Fab Library → пак → «Add to project».
   - Если Launcher не предлагает 5.8 (пак собран под 5.0–5.7), ставим его в отдельный staging-проект `FabStaging` нужной версии вне репозитория (например `C:/tmp/FabStaging/`).
   - Затем в редакторе: Asset Actions → Migrate в `unreal/Unmatched/Content/Fab/<PackName>/`. Открываем в 5.8, делаем Fix Up Redirectors и Resave.
   - Так поступили с SilverSet (`Content/StylizedForest/`) и Megaplants (`Content/Megaplant_Library/`).
   - Каталог `Content/` в `unreal/Unmatched/.gitignore` игнорируется, так что паки в git не попадают.
4. **Прямые загрузки (FBX/GLB/OBJ/.blend).** На странице листинга: Download → архив в `C:/tmp/fab-downloads/<uid>/` (вне git).
   - Дальше Blender: чистка, масштаб, ночная перекраска и экспорт FBX нашими скриптами (как Tripo/env_kit_build).
   - Импорт в `Content/EnvKit/Fab/<Pack>/` (тоже gitignored).
   - Скачивание делает пользователь или агент в уже залогиненной сессии с его явного согласия на конкретный пак. Ссылки из описаний листингов (Google Drive и т. п.) не открывать.
   - Smuggler's Cove можно взять с polyhaven.com как CC0 (glTF/blend) без атрибуции.
5. **Регистрация.** Каждую запись заносим в `docs/art-pipeline/asset-registry.json`: uid, URL, издатель, лицензия и уровень, `aiForbidden`, `aiGenerated`, путь в Content, версия UE, из которой мигрировали. CC-BY добавляем в `docs/art-pipeline/CREDITS-fab.md`. NoAI-паки помечаем так, чтобы скрипты evidence и ревью их исключали.
6. **Проход по Launcher (по реплике пользователя «Ты можешь искать это там»).** Один последовательный проход по вкладке Fab в Epic Games Launcher, без параллельных агентов.
   - Цели: (а) проверить поддерживаемые версии UE у пиков топ-10 и волны 11–15; (б) добрать то, чего нет в harvest. Запросы: `fantasy gui`, `rpg ui`, `card frame`, `stylized balustrade`, `stylized marble`, `stylized fountain`, `stylized statue`, `pirate`, `stylized ship`, `rope`, `sack`, `dock`, `night ambience`, `campfire sound`, `sword animation`.
   - Сетка результатов показывает превью NoAI-листингов, поэтому агенту нужен текстовый режим (дерево доступности, без скриншотов), иначе этот проход делает пользователь сам.
7. **Ночная перекраска и проверка.** Делаем общий MI-оверрайд под ночь: листва, камень, дерево (десатурация, затемнение, roughness ≥ 0.8, холодный сдвиг).
   - У VFX выключаем встроенный свет Niagara и ставим свои point lights.
   - Затем рендерим K1–K3 с `RENDER`-отпечатком (эталон High) и прогоняем concept-review против 16 гэпов.
   - Стоимость нового (Lumen, Niagara, light function) меряем через `tools/art/render/render_bench.py`, а не по `gpuMs` с ограничением FPS.
8. **Волны.**
   - Волна 1: топ-10.
   - Волна 2: 11–15, затем остальные пики шортлиста по гэпам.
   - Персонажи (The Wizard, Medusara, Harpy Assassin) — только как референсы для Tripo-героев. Отдельное решение, в этот ресерч окружения не входит.

Ничего не скачано, кроме CDN-превью листингов без NoAI. Ничего не куплено и не добавлено в библиотеку. Этот документ не закоммичен.

## Проверка

Сверка 2026-10-01 скриптами `C:/tmp/envmaps-research/fab/synth/verify.py` и `verify_md.py` (вне репозитория) против harvest.

**Что проверено.**
- Все 88 пиков JSON и каждая строка таблиц документа с uid: url, издатель, лицензия, `aiForbidden`, `aiGenerated`, форматы. У 79 пиков из harvest всё совпадает, включая колонки «Лицензия», «NoAI / ИИ» и «Формат» во всех таблицах. Рейтинги и число отзывов, упомянутые в тексте (Water Materials 4.6★/341, Rock Pack Vol 01 5★/8, Stylized_set_of_stones 1★/1, Nest Stylized Tree 5★/17, Good SKY 320, FX Variety Pack 262 и др.), совпадают.
- Бесплатность: у всех пиков `startingPrice=0`. У Personal-пиков в harvest `isFree=false`: бесплатен только уровень Personal (Professional платный). Нам этого достаточно. Единственный листинг harvest с ненулевой ценой (Asian Canal Environment) в шортлист не входит.
- Флаги отклонённых, названных по uid или названию (Megaplants, Vefects, StyleHex, Jayant Chakradhari, Quixel, Kamilla Kraus, Hyperdense, PolyReady, Axinovium и др.): совпадают с harvest. Утверждения «единственный звуковой пак без NoAI» (Caves and Dungeons), «единственная не-NoAI вода для UE» (Water Materials) и «других AI-разрешённых стилизованных пальм нет» подтверждены: остальные пальмы без NoAI реалистичные.
- Правило NoAI: в `C:/tmp/envmaps-research/fab/thumbs/` (578 файлов, 247 uid) нет ни одного uid с `aiForbidden=true` из harvest и ни одного из 6 листингов Glowbox3D с оговоркой NoAI в описании. Удалять было нечего.

**Что исправлено.**
- JSON: `formats` у Free Pack - Rocks Stylized (`a0746c4b`), Rock Pack Vol 01 (`f66023d1`) и MOON AND CLOUDS (`55e7d583`) приведены к данным harvest (не хватало служебных `converted-files`/`additional-files`).
- JSON и раздел 2: оговорка NoAI в описании есть ещё у 4 листингов Glowbox3D (`d331a169`, `cd8f0463`, `10749c4d`, `4b305d88`). Они вне темы и в шортлист не входят.
- Раздел 4: у Marble Materials и Free Braziers в списках «Ещё без NoAI» добавлена пометка «ИИ-сген.».
- В JSON добавлен блок `verification` с теми же итогами.

**Что не удалось проверить.**
- 9 VFX-пиков с `source=live-fab-search` и названные в отклонённых Stylized Volumetric Clouds Shader (`3dcea533`), Water Planes, Swamp Water, Cloudz Hi5, [18] Free Spells Niagara, Niagara Examples Pack, Elf Male Wizard в harvest отсутствуют. Их лицензии и флаги не перепроверены.
- В `thumbs/` лежат превью 21 uid вне harvest (VFX-домен). Подтвердить, что среди них нет NoAI, нечем: сырые данные живого поиска не сохранены. Сверить при проходе по Launcher (шаг 6) и при NoAI удалить их превью.
- Косметические отличия title от harvest (пояснение в скобках у Marble Vase 001 и Lantern, убран эмодзи у Free Braziers, типографский апостроф у Smuggler's Cove) ошибкой не считаются.

**Пропущенные сильные кандидаты (без NoAI, превью просмотрены).**
- [Stylized Flowers Pots](https://www.fab.com/listings/4615cf5f-d95d-4e92-b815-65575488d4be) (Gairisa, Personal, UE-пакет). Расписные вазоны и горшки с цветами, тот же автор, что Fantasy_Forest и Vine_Plants. Прямо закрывает пробел «розы и цветы для ваз» Marmoreal. Глиняные цвета перекрасить в мрамор или бронзу. UE 5.8: проверить при добавлении.
- [Free Pack - Tree](https://www.fab.com/listings/97b20cea-a7e6-4104-a884-0ece175b707d) (PolyOne Studio, Personal, FBX/.blend/OBJ/USD). 8 стилизованных хвойных, 5★ (2 отзыва). Хвойный ярус тёмного леса Sarpedon в том же стиле, что PolyOne Rocks из волны 11–15.
- Мельче: Stylized Wooden Barrel (Enkarra3D, `bf58ae49`, CC-BY, рисованная бочка, запасная к Cramb), Stylized berry plant pack (LOLIPOP, `96833911`, CC-BY, подлесок). Остальные непомянутые листинги без NoAI с высоким рейтингом (Medieval Dungeon, Broadcast Studio, KHS-дворцы, City Park LITE и т. п.) не по теме или фотореал.

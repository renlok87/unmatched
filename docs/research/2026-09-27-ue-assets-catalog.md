# Каталог ассетов и библиотек для UE-клиента Unmatched

Проверено адверсаральным ревью 2026-09-27; подробности — docs/research/2026-09-27-ue-assets-review.md

**Дата проверки данных: 2026-09-27.** Источник — исследования шести агентов (Fab, itch.io, GitHub, Epic-документация); данные нормализованы и дедуплицированы в [2026-09-27-ue-assets-findings.json](2026-09-27-ue-assets-findings.json). Рекомендации по отбору — в [2026-09-27-ue-assets-shortlist.md](2026-09-27-ue-assets-shortlist.md).

Оценка применимости выполнена против решений проекта: тонкий клиент без клиентских правил (P4, INT-001, `docs/game-design/08-integration-decisions.md`), UE 5.8 C++ (`unreal/Unmatched/Unmatched.uproject`), камера фиксированного угла без панорамирования/вращения (D-10), лёгкий риг миниатюр (D-11), собственный арт-пайплайн (D-06, D-09), задачи этапов 0–6 (`docs/game-design/09-vertical-slice-and-backlog.md`).

## Резюме

- **Интеграция с бэкендом** — главная зона экономии времени. Готового graphql-ws-клиента под UE не существует; кратчайший путь: платный GraphQL Client (Pandores, заявлена UE 5.8) на queries/mutations + собственный тонкий слой graphql-transport-ws поверх встроенного модуля WebSockets (или плагина Pandores) с паттерном реконнекта из MIT-библиотеки CrowdyCPP. Для асинхронного C++ — корутины UE5Coro.
- **UI (UMG, RU/EN)** — готовых карточных фреймворков под UE 5.8 нет; CCG Toolkit годится только как референс раскладки руки. Реальная экономия: UMG MCP (AI-агент собирает виджеты в редакторе UE 5.8 — в проекте уже включён плагин ModelContextProtocol), UE-BUITween (твины карт), PoolManager (пулинг виджетов под бюджет 60 FPS).
- **Диорама** — бесплатный CC0-стек KayKit + Quaternius закрывает болванки, анимации (ровно D-11: idle/удар/урон/смерть/магия) и настольный реквизит; PolyArt3D Stylized Medieval Town — единственный пейд-пак с явной поддержкой UE 5.8. Всё это база/прототип — финальные модели по D-06 делаются в собственном Blender-пайплайне.
- **Камера и сетка** — несмотря на высокие оценки агентов, плагины камер избыточны при D-10 (фиксированный угол, только зум) — см. пометки в разделе. ATBTT полезен только подсветкой клеток, но тянет собственный «движок тактики» за $59.99 без подтверждённой 5.8.
- **Звук/VFX** — Tabletop SFX (JDSherbert) — прямое попадание в жанр за ~£5; Niagara-паки требуют сверки стиля с контрактом «мрачноватой атмосферной диорамы» (D-02).
- **Главные оговорки по данным**: Fab отдаёт листинги только браузеру (Cloudflare) — цены/версии части листингов сняты агентами через SSR-прокси и помечены ниже; UE 5.8 заявлена у 9 находок из 48 (после уточнения ревью: Fantasy UI Toolkit заявляет 5.0–5.8), из них независимо подтверждено ревью 5 (Easy RTS, PolyArt3D, Fantasy UI Toolkit, UMG MCP, IWebSocket); блоки версий ещё 4 (Game Animation Sample, Mixamo RT2, GraphQL Client, Content Examples) не перепроверены — рендерятся клиентски. Лицензионное ревью 2026-09-27: главные блокеры до публичного релиза лежат вне выбора ассетов — публичные репозитории проекта со скрап-артом и ТМ «Unmatched» (Restoration Games), см. раздел «Оговорки к данным» и review-отчёт. По итогам ревью добавлены категории: UI-иконки, материалы булыжника (Megascans), Send2UE, CC0-музыка — раздел 7.

Легенда UE 5.8: **5.8 ✓** — заявлена листингом/доками; **5.8 ?** — не заявлена, проверять; **n/a** — движко-независимый контент (FBX/PNG/WAV), импортируется в любую версию. ⚠ — сомнительная находка (лицензия/версия/репутация не подтверждены). Колонка «Релев.» — оценка агента до сверки с решениями проекта (D-xx); проектная оценка — в текстовом разделе и шорт-листе, у спорных строк приведена после «→».

## Сводная таблица (48 исходных + 5 добавленных по итогам ревью)

| #   | Находка                                                                                                                         | Категория                   | Тип                    | Цена                       | UE 5.8                              | Релев.                    |
| --- | ------------------------------------------------------------------------------------------------------------------------------- | --------------------------- | ---------------------- | -------------------------- | ----------------------------------- | ------------------------- |
| 1   | [CCG Toolkit](https://www.fab.com/listings/b9d7f0ae-d9f1-4086-9014-4c5c5bc04872)                                                | Карточный UI                | фреймворк (BP)         | $49.99–99.99               | заявлено 5.1–5.6, 5.8 нет           | high (агента) → не брать  |
| 2   | [Fantasy UI Toolkit](https://www.fab.com/listings/d77c8b5e-2912-40f2-87ea-0349b1890c7f) ⚠                                       | Карточный UI                | asset-pack             | $3.49 (+адд-оны)           | 5.8 ✓                               | medium                    |
| 3   | [Nice Card Game Template](https://chicogames.itch.io/card-game-template)                                                        | Карточный UI                | asset-pack (2D)        | $8.90+                     | n/a                                 | medium                    |
| 4   | [Fantasy Cards (Penusbmic)](https://penusbmic.itch.io/fantasy-cards)                                                            | Карточный UI                | asset-pack (2D)        | $19.99+                    | n/a                                 | medium                    |
| 5   | [Fantasy Card Assets (cafeDraw)](https://cafedraw.itch.io/fantasy-card-assets)                                                  | Карточный UI                | asset-pack (2D)        | $0+ (CC0)                  | n/a                                 | medium                    |
| 6   | [UltimateUI](https://github.com/DanialKama/UltimateUI)                                                                          | Карточный UI                | plugin (CommonUI)      | free / MIT                 | 5.8 ?                               | medium                    |
| 7   | [ATBTT](https://www.fab.com/listings/d9975a03-797a-47ca-8da0-06d8eee49b69)                                                      | Сетка и камера              | plugin                 | $59.99                     | 5.8 ? (форум: 5.5)                  | high (агента) → не в MVP  |
| 8   | [Easy RTS Controller](https://www.fab.com/listings/d19b65ae-4c0b-4653-8329-3abb0f61ce0a) ⚠                                      | Сетка и камера              | plugin (C++)           | $19.99                     | 5.8 ✓                               | high (агента) → после MVP |
| 9   | [Grid Manager](https://www.fab.com/listings/9eeaebe7-3a8a-46ed-be9d-e5b58aaaa6b6) ⚠                                             | Сетка и камера              | plugin                 | $49.99                     | 5.6                                 | medium                    |
| 10  | [Open RTS Camera](https://www.fab.com/listings/b4d7217d-c392-40da-a471-a55fd845ef41)                                            | Сетка и камера              | plugin (C++)           | free / MIT                 | сборка под 5.3                      | medium                    |
| 11  | [Ultimate C++ Interaction Framework](https://www.fab.com/listings/60a277c3-da63-438f-9e14-e64b015d4d02)                         | Сетка и камера              | plugin                 | $34.99                     | 5.8 ?                               | low                       |
| 12  | [RTSCamPro](https://www.fab.com/listings/afc29d33-c336-47f9-fbe4-fbf6aa6b72a8)                                                  | Сетка и камера              | plugin (BP)            | $9.99                      | 5.8 ?                               | low                       |
| 13  | [Ultimate RTS Camera](https://www.fab.com/listings/5516684a-2702-4e07-bf6a-ad5798c741d3)                                        | Сетка и камера              | plugin                 | $24.99                     | ≤5.2                                | low                       |
| 14  | [POLYGON — Fantasy Kingdom (Synty)](https://www.fab.com/listings/3d968be5-531f-4f6c-abf9-1a799dca2641) ⚠                        | Диорама и миниатюры         | asset-pack             | не отображена (~premium)   | 5.8 ?                               | high (агента) → референс  |
| 15  | [Stylized Medieval Town (PolyArt3D)](https://www.fab.com/listings/f752d38d-3460-4320-baf1-7be0bf6c2726)                         | Диорама и миниатюры         | asset-pack             | ≈$66–132                   | 5.8 ✓                               | high                      |
| 16  | [3D Card Kit — Fantasy (Quaternius)](https://quaternius.com/packs/3dcardkitfantasy.html)                                        | Диорама и миниатюры         | asset-pack (3D)        | free / PRO $9.99           | n/a (FBX)                           | high                      |
| 17  | [Medieval Village MegaKit (Quaternius)](https://quaternius.com/packs/medievalvillagemegakit.html)                               | Диорама и миниатюры         | asset-pack (3D)        | free / Patreon             | n/a (FBX)                           | high                      |
| 18  | [KayKit — Character Animations](https://kaylousberg.itch.io/kaykit-character-animations)                                        | Диорама и миниатюры         | asset-pack (анимации)  | free / $14.99 source       | n/a (FBX)                           | high                      |
| 19  | [KayKit — Board Game Bits](https://kaylousberg.itch.io/board-game-bits)                                                         | Диорама и миниатюры         | asset-pack (3D)        | free / EXTRA $4.99+        | n/a (FBX)                           | high                      |
| 20  | [KayKit — Adventurers](https://kaylousberg.itch.io/kaykit-adventurers)                                                          | Диорама и миниатюры         | asset-pack (персонажи) | free / EXTRA $7.95+        | n/a (FBX)                           | medium                    |
| 21  | [Ultimate Monsters (Quaternius)](https://quaternius.com/packs/ultimatemonsters.html)                                            | Диорама и миниатюры         | asset-pack (3D)        | free                       | n/a (FBX)                           | medium                    |
| 22  | [RPG Character Pack (Quaternius)](https://quaternius.com/packs/rpgcharacters.html)                                              | Диорама и миниатюры         | asset-pack (3D)        | free                       | n/a (FBX)                           | medium                    |
| 23  | [Animated Knight Pack (Quaternius)](https://quaternius.com/packs/knightcharacter.html)                                          | Диорама и миниатюры         | asset-pack (3D)        | free                       | n/a (FBX)                           | low                       |
| 24  | [Game Animation Sample (Epic)](https://www.fab.com/listings/880e319a-a59e-4ed2-b268-b32dac7fa016)                               | Анимации, VFX, звук         | open-project           | free                       | 5.8 ✓ (блок версий не перепроверен) | high (агента) → референс  |
| 25  | [Sword Animset Pro (Kubold)](https://www.fab.com/listings/12783d2f-2bcf-4f3e-9a4a-d554cc3c579a)                                 | Анимации, VFX, звук         | asset-pack (анимации)  | $64.99                     | ≤5.6                                | high                      |
| 26  | [Mixamo Animation Retargeting 2 (UNAmedia)](https://www.fab.com/listings/5eaf2746-1891-435a-837c-67c9f7a847f4)                  | Анимации, VFX, звук         | plugin                 | $39.99–79.99               | 5.8 ✓                               | high                      |
| 27  | [mixamo_converter (Blender)](https://github.com/enziop/mixamo_converter)                                                        | Анимации, VFX, звук         | code-library           | free / GPL-3               | n/a (Blender→FBX)                   | high                      |
| 28  | [Tabletop Games SFX (JDSherbert)](https://jdsherbert.itch.io/tabletop-games-sfx-pack)                                           | Анимации, VFX, звук         | asset-pack (звук)      | £4.99+ (есть free)         | n/a (WAV)                           | high                      |
| 29  | [Ultimate UI SFX (JDSherbert)](https://jdsherbert.itch.io/ultimate-ui-sfx-pack)                                                 | Анимации, VFX, звук         | asset-pack (звук)      | £4.99+ (есть free)         | n/a (WAV)                           | medium                    |
| 30  | [Niagara Slash VFX (KC Studio Asia)](https://kcstudioasia.itch.io/unreal-engine-niagara-slash-vfx) ⚠                            | Анимации, VFX, звук         | asset-pack (Niagara)   | $15+                       | ≤5.6                                | medium                    |
| 31  | [Stylized VFX Bundle (Vefects)](https://vefects.itch.io/stylized-vfx-bundle-unreal-engine) ⚠                                    | Анимации, VFX, звук         | asset-pack (Niagara)   | $89.99+                    | 5.8 ?                               | medium                    |
| 32  | [Content Examples (Epic)](https://www.fab.com/listings/4d251261-d98c-48e2-baee-8f4e47c67091)                                    | Анимации, VFX, звук         | open-project           | free                       | 5.8 ✓                               | medium                    |
| 33  | [Fantasy Medieval Ambient Music (alkakrab)](https://alkakrab.itch.io/free-fantasy-medieval-ambient-music-pack) ⚠                | Анимации, VFX, звук         | asset-pack (музыка)    | free                       | n/a (WAV/MP3)                       | medium                    |
| 34  | [UE5Coro](https://github.com/landelare/ue5coro)                                                                                 | Open-source код             | code-library           | free / BSD-3               | 5.8 ?                               | high                      |
| 35  | [PoolManager (JanSeliv)](https://github.com/JanSeliv/PoolManager)                                                               | Open-source код             | plugin                 | free / MIT                 | 5.7                                 | high                      |
| 36  | [UMG MCP (UnrealMotionGraphicsMCP)](https://github.com/winyunq/UnrealMotionGraphicsMCP)                                         | Open-source код             | tool (MCP)             | free / MIT                 | 5.8 ✓                               | high                      |
| 37  | [UE-BUITween (benui)](https://github.com/benui-dev/UE-BUITween)                                                                 | Open-source код             | code-library           | free / CC0                 | 5.8 ? (база UE4)                    | high                      |
| 38  | [ue5-cardgame (perfect-hand)](https://github.com/perfect-hand/ue5-cardgame) ⚠                                                   | Open-source код             | plugin                 | free / MIT                 | ранние 5.x, заброшен                | medium                    |
| 39  | [TurnBasedSample (BinaryBard996)](https://github.com/BinaryBard996/TurnBasedSample)                                             | Open-source код             | open-project           | free / MIT                 | 5.6–5.7                             | medium                    |
| 40  | [Bomber (JanSeliv)](https://github.com/JanSeliv/Bomber)                                                                         | Open-source код             | open-project           | free / MIT                 | UE5 (актуальный)                    | medium                    |
| 41  | [ACGCard (egojump)](https://github.com/egojump/ACGCard) ⚠                                                                       | Open-source код             | open-project           | просмотр (нет лицензии)    | UE 4.18                             | low                       |
| 42  | [GraphQL Client (Pandoa/Pandores)](https://www.fab.com/listings/531b2dce-cac7-42a5-905b-143ef7b64b75) ⚠                         | GraphQL-интеграция          | plugin                 | $14.99–29.99               | 5.8 ✓                               | high                      |
| 43  | [WebSocket Client (BlueprintWebSocket, Pandores)](https://github.com/pandoa/BlueprintWebSocket) ⚠                               | GraphQL-интеграция          | plugin                 | платный (цена ?)           | версии/платформы — не проверены     | medium (опция-дубль)      |
| 44  | [IWebSocket (встроенный модуль)](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/WebSockets/IWebSocket) | GraphQL-интеграция          | code-library           | входит в движок            | 5.8 ✓                               | high                      |
| 45  | [CrowdyCPP (Crowded Kingdoms)](https://github.com/CrowdedKingdoms/CrowdyCPP)                                                    | GraphQL-интеграция          | code-library           | free / MIT                 | C++20; UE-обёртка 5.8               | medium                    |
| 46  | [cppgraphqlgen (Microsoft)](https://github.com/microsoft/cppgraphqlgen)                                                         | GraphQL-интеграция          | code-library           | free / MIT                 | ThirdParty вручную                  | medium                    |
| 47  | [Easy Jwt (sha3sha3)](https://www.fab.com/listings/5a7b13f17ce04fc3b4a571a8faf58b4a)                                            | GraphQL-интеграция          | plugin                 | $9.99 (GitHub free)        | UE4/5                               | medium                    |
| 48  | [IXWebSocket (machinezone)](https://github.com/machinezone/IXWebSocket)                                                         | GraphQL-интеграция          | code-library           | free / BSD-3               | ThirdParty вручную                  | low                       |
| 49  | [Kenney Game Icons](https://kenney.nl/assets/game-icons)                                                                        | UI-иконки (ревью)           | asset-pack (2D)        | free / CC0                 | n/a (PNG)                           | high                      |
| 50  | [game-icons.net](https://game-icons.net)                                                                                        | UI-иконки (ревью)           | asset-pack (SVG)       | free / CC BY 3.0           | n/a (SVG)                           | medium                    |
| 51  | Megascans — cobblestone (Fab, поиск «cobblestone surface», фильтры Free + UE)                                                   | Материалы доски (ревью)     | asset-pack             | free для UE / Fab Standard | UE-native                           | medium                    |
| 52  | [Send2UE (Epic BlenderTools)](https://github.com/EpicGames/BlenderTools)                                                        | Пайплайн Blender→UE (ревью) | tool (аддон)           | free / MIT                 | n/a (Blender→UE)                    | high                      |
| 53  | [CC0-музыка: FreePD / Kenney Music](https://freepd.com)                                                                         | Анимации, VFX, звук (ревью) | asset-pack (музыка)    | free / CC0                 | n/a (WAV/MP3)                       | medium                    |

---

## 1. Карточный UI

Готовых карточных UMG-фреймворков под UE 5.8 не найдено; всё, что ниже, — либо референс, либо 2D-графика для прототипа виджета карты. По D-09 иллюстрации карт берутся из существующих 2D-артов проекта, поэтому паки ниже закрывают только рамки/рубашки/плашки (в т.ч. fallback-рамку INT-018 для карт без арта, TASK-052).

### 1.1. [CCG Toolkit (Multiplayer Card Game Framework)](https://www.fab.com/listings/b9d7f0ae-d9f1-4086-9014-4c5c5bc04872)

- **Тип:** фреймворк, 100% Blueprint (kind: open-project).
- **Цена:** $49.99–99.99 (Personal/Professional — права одинаковые по Fab EULA; убедиться, что дешёвый тир не Reference-Only; без налогов).
- **Лицензия:** Fab Standard License.
- **UE-совместимость:** листинг заявляет **UE 5.1–5.6; 5.8 не заявлена** (уточнено фактчекингом 2026-09-27 — прежняя формулировка «версии не заявлены» была неверна); UE5 подтверждён и отзывами.
- **Обновление:** 2025-10-01 (публикация 2016-07-07).
- **Чем поможет:** менеджер карт с профилями позиционирования (веер руки/стола), mouse-over превью, колода/сброс, deck builder — готовые механики для прототипа карточного UI (TASK-026 HUD: рука, колода/сброс).
- **Риски:** собственный «движок правил» + мультиплеер несовместимы с тонким клиентом (P4/INT-001) — вся логика лишняя; 100% BP против C++-модулей проекта; свежий отзыв (1★, 2025) о расхождении документации и кода; 5.8 не заявлена. **По решениям проекта: брать только как референс раскладки руки/превью, не как базу** — подробнее в шорт-листе, раздел «Что НЕ стоит брать».
- **Релевантность (агента):** high.

### 1.2. [Fantasy UI Toolkit (Monster Tooth Studios)](https://www.fab.com/listings/d77c8b5e-2912-40f2-87ea-0349b1890c7f) ⚠

- **Тип:** asset-pack (UI-кит).
- **Цена:** $3.49 (на момент проверки скидка 30% ≈ $2.45); адд-оны-наборы иконок по $3.49 (уточнено фактчекингом 2026-09-27 — прежние «$7.99–24.99» на листинге отсутствуют).
- **Лицензия:** Fab Standard License.
- **UE-совместимость:** заявлены **UE 5.0–5.8** — совместимость с 5.8 подтверждена листингом (уточнено фактчекингом 2026-09-27).
- **Обновление:** 2026-08-10 (опубликован 2023-09-21).
- **Чем поможет:** кнопки/попапы/окна для экранов лобби/настроек (TASK-025, UI-семейства TASK-051).
- **Риски:** ⚠ рейтинг 2.0 при единственном отзыве; неизвестно, есть ли готовые UMG-виджеты или только графика; стиль сверять с диорамой.
- **Релевантность:** medium.

### 1.3. [Nice Card Game Template (chicogames)](https://chicogames.itch.io/card-game-template)

- **Тип:** asset-pack (PNG + PSD + шрифты).
- **Цена:** $8.90+.
- **Лицензия:** **CC BY-SA 3.0** (по ответу автора в комментариях itch: «ATTRIBUTION-SHAREALIKE 3.0») — attribution + share-alike: производные ассетов обязаны распространяться под той же лицензией. Исправлено фактчекингом 2026-09-27: прежнее описание «custom royalty-free, no resale/redistribution» неверно — такого текста на странице нет. «No generative AI was used».
- **UE-совместимость:** n/a — импорт в UMG любой версии.
- **Обновление:** v1.3, дата не указана (рейтинг 5.0, 4 оценки).
- **Чем поможет:** рамки лицевой стороны/рубашки карт в духе Hearthstone — «скелет» виджета карты атаки/схемы/буста до подключения своего арта.
- **Риски:** share-alike делает пак **непригодным для проприетарного дистрибутива** — только внутренний прототип, до релиза полностью заменить (CC0-альтернатива — cafeDraw, п. 1.5); включены шрифты без указания лицензий и монстр-арт стороннего автора (jon_nego.artstation.com) без подтверждённых прав на сублицензирование; только 2D, без виджетов; стиль может не совпасть с генерируемыми иллюстрациями (D-09).
- **Релевантность:** medium.

### 1.4. [Fantasy Cards Asset Pack (Penusbmic)](https://penusbmic.itch.io/fantasy-cards)

- **Тип:** asset-pack (спрайты + исходники Aseprite).
- **Цена:** $19.99+ (также Tier 3 Patreon).
- **Лицензия:** CC BY 4.0 + условия автора (кредит «Penusbmic», без перепродажи ассетов по отдельности).
- **UE-совместимость:** n/a.
- **Обновление:** заявлен постоянно обновляемым, devlog активен в 2026.
- **Чем поможет:** 11 рамок/фонов, 25 собранных карт, иконки статов (сердца/мечи/щиты) — структурный референс карточного виджета и иконки HP/урона.
- **Риски:** пиксель-арт против объёмной диорамы (D-02); CC BY — атрибуция; низкое разрешение 106×138 — только прототип.
- **Релевантность:** medium.

### 1.5. [Fantasy Card Assets (cafeDraw)](https://cafedraw.itch.io/fantasy-card-assets)

- **Тип:** asset-pack (PNG).
- **Цена:** name-your-own-price (можно $0).
- **Лицензия:** CC0 1.0 (поле Asset license) + royalty-free текст автора, атрибуция не обязательна.
- **UE-совместимость:** n/a.
- **Обновление:** 2023-06-17 (релиз 2021).
- **Чем поможет:** CC0-рамки карт в 5 цветах, рубашки, плашки имени/описания, иконки, FX — нулезатратный каркас карточного виджета и кандидат на fallback-рамку INT-018 (TASK-052).
- **Риски:** пиксельно-векторный стиль, малые разрешения; обновления редки — только прототип.
- **Релевантность:** medium.

### 1.6. [UltimateUI (DanialKama)](https://github.com/DanialKama/UltimateUI)

- **Тип:** plugin поверх CommonUI.
- **Цена:** free.
- **Лицензия:** MIT.
- **UE-совместимость:** UE5; 5.8 не заявлена — проверять компиляцию.
- **Обновление:** 2025-05-03 (63★).
- **Чем поможет:** меню/пауза/настройки (графика/аудио/управление), кнопки, слайдеры, курсор — «обвязка» экранов TASK-025/054 (UI-SCR-PAUSE, настройки).
- **Риски:** один автор, низкая активность; карточной специфики нет; темизация под фэнтези; в проекте уже запланирован собственный FSM экранов (02 §1.3, слои CommonUI) — совместимость архитектур проверять.
- **Релевантность:** medium.

## 2. Сетка, ходы и камера

⚠️ **Общая поправка по решениям проекта**: агенты оценивали тему до сверения с D-10 и TASK-020. Фактически: камера — фиксированный угол, зум колесом, без панорамирования/вращения, follow-selection при зуме ≥1.2× (03 §2); доска строится параметрически из `boardState` (TASK-020), подсветка достижимости — собственный BFS, повторяющий серверные правила (TASK-027, GDD-014). RTS-камеры с edge scrolling/поворотом/миникартами и тулкиты с собственным поиском пути/менеджерами ходов в основном избыточны — детали ниже и в шорт-листе.

### 2.1. [Advanced Turn Based Tile Toolkit (ATBTT)](https://www.fab.com/listings/d9975a03-797a-47ca-8da0-06d8eee49b69)

- **Тип:** plugin.
- **Цена:** $59.99.
- **Лицензия:** Fab standard paid content license.
- **UE-совместимость:** список версий клиентский (не прочитан); форум подтверждает v3.7 с фиксами UE 5.5 (2024-11-25); changelog Fab до 2026-08-27; 5.6–5.8 не подтверждены.
- **Обновление:** 2026-08-27; рейтинг 4.9.
- **Чем поможет:** подсветка дальности хода/атаки с обводкой зон и сплайновое перемещение фигурок по клеткам — визуализация манёвров, которые присылает сервер (TASK-021/024, CUE-перемещение).
- **Риски:** «всё-в-одном»: своя пошаговая логика, AI, путь-поиск — всё это придётся отключать (правила у сервера, доска строится из boardState); 5.8 не заявлена; миграции обновлений перетирают контент (предупреждение автора). Соотношение цена/полезность для тонкого клиента спорное — см. шорт-лист.
- **Релевантность (агента):** high; **по решениям проекта — брать не в MVP**.

### 2.2. [Easy RTS Controller](https://www.fab.com/listings/d19b65ae-4c0b-4653-8329-3abb0f61ce0a) ⚠

- **Тип:** plugin (C++).
- **Цена:** $19.99.
- **Лицензия:** Fab standard paid content license.
- **UE-совместимость:** 5.8 заявлена прямо в листинге; Windows 64-bit; Enhanced Input + Gameplay Tags.
- **Обновление:** опубликован 2026-09-11 — плагину ~2 недели на дату проверки. ⚠
- **Чем поможет:** top-down камера с follow-target (плавный фокус на активной фигурке), зум, hover/клик-выделение со стилизацией. Философия «только презентация, без правил» совпадает с INT-001.
- **Риски:** ⚠ свежайший релиз без отзывов/рейтинга; один продавец; большинство функций (edge scrolling, поворот, рамочное выделение, миникарта) при D-10 не нужны и потребуют отключения. Реальная потребность проекта (зум + follow-selection) — ~день собственного C++ (03 §2).
- **Релевантность (агента):** high; **по решениям проекта — кандидат «после MVP», не обязательная покупка**.

### 2.3. [Grid Manager (Hex Grid Manager Basic)](https://www.fab.com/listings/9eeaebe7-3a8a-46ed-be9d-e5b58aaaa6b6) ⚠

- **Тип:** plugin.
- **Цена:** $49.99.
- **Лицензия:** Fab standard paid content license.
- **UE-совместимость:** заявлена 5.6.
- **Обновление:** 2025-09-09 (единственный релиз). ⚠
- **Чем поможет:** скелет квадратной сетки с пикингом тайлов мышью (28 BP-функций, события/делегаты) — каркас для кликов по клеткам (TASK-022).
- **Риски:** ⚠ один релиз нового продавца, без отзывов; подсветку допустимых ходов придётся делать самому; **дубдирует TASK-020**: доска по спецификации строится параметрически из `boardState` (width/height/cells/zones), а не из генератора сеток плагина.
- **Релевантность:** medium; по решениям проекта — не брать (конфликт с TASK-020/INT-019).

### 2.4. [Open RTS Camera (OpenRTSCamera)](https://www.fab.com/listings/b4d7217d-c392-40da-a471-a55fd845ef41)

- **Тип:** plugin (C++), open source.
- **Цена:** free на Fab; исходники на GitHub.
- **Лицензия:** MIT.
- **UE-совместимость:** последняя сборка под UE 5.3 — пересборка под 5.8 вручную.
- **Обновление:** GitHub push 2025-01-10 (114★); Fab changelog 2024-10-15; рейтинг 4.7 (13 оценок).
- **Чем поможет:** MIT-код top-down камеры (edge scrolling, зум, follow target, bounds, сглаживание) — бесплатный референс/основа для собственной камеры диорамы (03 §2).
- **Риски:** портирование на 5.8; редкие коммиты. Как и все RTS-камеры — больше функций, чем требует D-10; ценен скорее как код для чтения.
- **Релевантность:** medium.

### 2.5. [Ultimate C++ Interaction Framework](https://www.fab.com/listings/60a277c3-da63-438f-9e14-e64b015d4d02)

- **Тип:** plugin (C++).
- **Цена:** $34.99.
- **Лицензия:** Fab standard paid content license.
- **UE-совместимость:** версии не прочитаны (клиентский рендер) — проверять под 5.8.
- **Обновление:** 2026-07-21 (опубликован 2026-01-26).
- **Чем поможет:** паттерн пикинга интерактивных объектов и outline-подсветка выделенных целей (кольца выбора фигурок, TASK-022).
- **Риски:** обводка выбора в UE дёшево решается custom depth stencil без плагина (оценка агента верна); фреймворк шире задачи.
- **Релевантность:** low.

### 2.6. [RTSCamPro - Premium RTS Camera](https://www.fab.com/listings/afc29d33-c336-47f9-fbe4-fbf6aa6b72a8)

- **Тип:** plugin (Blueprint-only).
- **Цена:** $9.99.
- **Лицензия:** Fab standard paid content license.
- **UE-совместимость:** «designed for UE5», конкретные версии не прочитаны.
- **Обновление:** 2025-07-30 (после релиза — только правки цены/описания).
- **Чем поможет:** базовый набор пан/зум/поворот top-down камеры.
- **Риски:** BP-only в C++-проекте; обновления косметические; при D-10 (без пан/поворота) ценность минимальна.
- **Релевантность:** low.

### 2.7. [Ultimate RTS Camera](https://www.fab.com/listings/5516684a-2702-4e07-bf6a-ad5798c741d3)

- **Тип:** plugin.
- **Цена:** $24.99.
- **Лицензия:** Fab standard paid content license.
- **UE-совместимость:** заявлено 5.0/5.2; про 5.3+ данных нет, миграция на 5.8 не гарантирована.
- **Обновление:** 2024-09-24 (код с 2018; рейтинг 5.0).
- **Чем поможет:** референс поведения RTS-камеры, демо-уровень.
- **Риски:** устаревшая база (до 5.2) на фоне конкурентов с заявленной 5.8.
- **Релевантность:** low.

## 3. Диорама, миниатюры и реквизит

По D-06 финальные модели делаются с нуля в Blender; готовые паки — база/прототип и источник болванок. Все KayKit/Quaternius-паки — CC0 (у Quaternius общесайтовая QAL v1.0 строже: запрещает redistribution самих ассетов в любом виде, включая бесплатное, — **сами файлы паков в публичный репозиторий не класть**, для игры это некритично), т.е. без атрибуции и роялти. Прямых стилизованных аналогов Медузы и гарпий не найдено (все «medusa/harpy» на Sketchfab — рипы игр с юридическим риском) — герои MVP делаются в своём пайплайне.

### 3.1. [POLYGON — Fantasy Kingdom (Synty Studios)](https://www.fab.com/listings/3d968be5-531f-4f6c-abf9-1a799dca2641) ⚠

- **Тип:** asset-pack (2100+ low-poly моделей).
- **Цена:** ⚠ не отображается в статическом HTML (JS-заглушка); по стороннему упоминанию в поиске — порядка €190.
- **Лицензия:** Fab marketplace license (полные условия не прочитаны).
- **UE-совместимость:** формат «Unreal Engine only»; конкретные версии не указаны — проверять на странице.
- **Обновление:** опубликован 2020-05-12; дата последнего обновления JS-only; рейтинг 4.7 (13 оценок); издатель активен.
- **Чем поможет:** модульный город с интерьерами, рынок, оружие, персонажи King/Mage/Soldier — прототипы Arthur/Merlin и весь декор диорамы в едином стиле.
- **Риски:** персонажи статичные («poses indicative only»), без рига — под миниатюры риговать у себя; цена/версии не проверены; только формат UE. Примечание: заявление агента, что стиль Synty «прямо назван в ТЗ проекта», не подтверждается документами `docs/game-design/` (03 §1 описывает похожий, но безымянный контракт «окрашенной статуэтки»).
- **Релевантность:** high (как референс стиля/декора); для производственной базы — проверить цену и состав до покупки.

### 3.2. [Stylized Medieval Town — Low Poly Environment (PolyArt3D)](https://www.fab.com/listings/f752d38d-3460-4320-baf1-7be0bf6c2726)

- **Тип:** asset-pack (190 мешей + демо-сцена).
- **Цена:** ≈US$66–132 (¥474–948 по региональному рендеру, два ценовых тира — Personal/Professional с одинаковыми правами; убедиться, что дешёвый тир не Reference-Only), без налогов.
- **Лицензия:** Standard License.
- **UE-совместимость:** **4.25–4.27 и 5.0–5.8 заявлены явно** — единственный крупный окруженческий пак с подтверждённой 5.8.
- **Обновление:** публикация 2025-11-02, обновление 2026-06-18 — сопровождается; оценок пока нет.
- **Чем поможет:** фахверковые дома с интерьерами, прилавки, фонари, бочки + атмосферные партиклы (светлячки, туман, дым, листва, птицы) — готовые декорации и ambient-эффекты для TASK-040 (доска-диорама) и TASK-043 (свет/атмосфера).
- **Риски:** булыжное мощение в списке ассетов не названо — игровая плоскость Cobble City всё равно строится из своих тайлов по boardState (TASK-020/040), материал плиток/швов брать из Megascans (п. 7.3); персонажей нет; листинг молодой, без оценок.
- **Релевантность:** high.

### 3.3. [3D Card Kit — Fantasy (Quaternius)](https://quaternius.com/packs/3dcardkitfantasy.html)

_Объединённая находка двух агентов (quaternius.com + [itch.io](https://quaternius.itch.io/3d-card-kit-fantasy)); дубль удалён._

- **Тип:** asset-pack (50 3D-сцен-карт, 60+ моделей).
- **Цена:** free (30 карт) / PRO $9.99 (50 карт на itch); Source-тир через Patreon $10–50/мес (.BLEND + engine-ready проекты).
- **Лицензия:** CC0 на странице пака; общесайтовая — Quaternius Asset License v1.0 (обе разрешают коммерческие игры; запрещена перепродажа самих ассетов).
- **UE-совместимость:** n/a — FBX/OBJ/glTF в любую версию UE, включая 5.8; готовый UE-проект только 4.27.2 (платный тир); атлас 1024×1024.
- **Обновление:** июнь 2024 (страница пака); itch проверен 2026-09-27; издатель активен.
- **Чем поможет:** физические 3D-карты (герои/заклинания/эффекты/предметы), лежащие на столе диорамы — прототип подачи «карты на столе» и токенов-эффектов (CUE, TASK-050, ASSET-PROPS-CARDS-001).
- **Риски:** атлас 1024² ограничивает крупные планы; low-poly стиль сверять с контрактом С-2; только модели, без UI-логики; CC0-vs-QAL расхождение для игры некритично.
- **Релевантность:** high (агент 3; агент 1 оценил medium — итог повышен благодаря бесплатности и точному попаданию в тематику).

### 3.4. [Medieval Village MegaKit (Quaternius)](https://quaternius.com/packs/medievalvillagemegakit.html)

- **Тип:** asset-pack (304 модульных куска).
- **Цена:** free (60–70% пака); Source через Patreon $10–50.
- **Лицензия:** CC0 (страница пака) / QAL v1.0 (сайт).
- **UE-совместимость:** n/a — FBX/OBJ/glTF; UE-проект 4.27.2 только в Source-тире.
- **Обновление:** январь 2025.
- **Чем поможет:** модульные стены/полы/крыши/окна/двери, «snap perfectly to a grid» — бесплатная база для сборки подноса диорамы и фасадов точно под размер доски (TASK-040, ASSET-TABLE-BASE-001/ASSET-DECOR-KIT-001).
- **Риски:** ручной FBX-импорт в 5.8; стилистика проще Synty — смешение с PolyArt3D потребует подгонки материалов.
- **Релевантность:** high.

### 3.5. [KayKit — Character Animations (Kay Lousberg)](https://kaylousberg.itch.io/kaykit-character-animations)

- **Тип:** asset-pack (161 анимация, FBX/GLTF).
- **Цена:** free; SOURCE $14.99+ (.blend).
- **Лицензия:** CC0, без атрибуции.
- **UE-совместимость:** n/a — FBX/GLTF-импорт и ретаргет в UE 5.x; версии UE не заявлены.
- **Обновление:** devlog 1.1 от 2025-12-10; рейтинг 4.9 (52 оценки).
- **Чем поможет:** ровно набор D-11: idle, hit, death, спавн, одно-/двуручный мили, блоки, магия (spellcasting), эмоции — клипы Idle/LungeAttack/HitReact/DeathSettle для эталонной модели Medusa (TASK-041) и остальных фигурок (TASK-050), анимации Merlin (заклинания).
- **Риски:** заточен под скелеты KayKit (Rig_Medium/Rig_Large) — на своих моделях из Blender-пайплайна ретаргет через IK Retargeter.
- **Релевантность:** high. _(Входит в шорт-лист.)_

### 3.6. [KayKit — Board Game Bits (Kay Lousberg)](https://kaylousberg.itch.io/board-game-bits)

- **Тип:** asset-pack (162–243 модели настольного реквизита).
- **Цена:** free (162); EXTRA $4.99+ (шахматы/шашки/игральные карты); SOURCE $7.49+.
- **Лицензия:** CC0.
- **UE-совместимость:** n/a — OBJ/FBX/GLTF; атлас 1024×1024.
- **Обновление:** дата на странице не показана (статус Released); рейтинг 4.9 (23 оценки).
- **Чем поможет:** миплы, токены, кубы, монеты, пешки, кубики — прямая база для маркеров урона/эффектов и «настольной» подачи (ASSET-MARKERS-001, TASK-015 — маркеры нужны серой сцене раньше фигурок).
- **Риски:** круглые подставки-базы под миниатюры явно не заявлены; ручной импорт.
- **Релевантность:** high. _(Входит в шорт-лист.)_

### 3.7. [KayKit — Character Pack: Adventurers (Kay Lousberg)](https://kaylousberg.itch.io/kaykit-adventurers)

- **Тип:** asset-pack (5 персонажей, риг+анимации; EXTRA +3).
- **Цена:** free; EXTRA $7.95+; SOURCE $11.95+.
- **Лицензия:** CC0.
- **UE-совместимость:** n/a — FBX/GLTF.
- **Обновление:** «Updated 10 days ago» на 2026-09-27; рейтинг 4.9 (274 оценки).
- **Чем поможет:** ригованные+анимированные болванки для заселения диорамы и прототипа рига до готовности моделей героев.
- **Риски:** состав 5 базовых персонажей поимённо не расписан; нет аналогов Медузы/Артура/Мерлина; стиль очень простой.
- **Релевантность:** medium.

### 3.8. [Ultimate Monsters (Quaternius)](https://quaternius.com/packs/ultimatemonsters.html)

- **Тип:** asset-pack (50 анимированных монстров).
- **Цена:** free.
- **Лицензия:** CC0.
- **UE-совместимость:** n/a — FBX/OBJ/Blend/glTF.
- **Обновление:** октябрь 2022 (пак не обновляется).
- **Чем поможет:** пул анимированных болванок нечисти — кандидаты под гарпий (состав не подтверждён).
- **Риски:** наличие гарпии/горгоны не подтверждено страницей — проверять по превью до опоры на пак.
- **Релевантность:** medium.

### 3.9. [RPG Character Pack (Quaternius)](https://quaternius.com/packs/rpgcharacters.html)

- **Тип:** asset-pack (6 ригованных анимированных персонажей).
- **Цена:** free.
- **Лицензия:** CC0.
- **UE-совместимость:** n/a.
- **Обновление:** ноябрь 2020.
- **Чем поможет:** болванки волшебника/рыцаря, тест ретаргета KayKit-анимаций на сторонние риги.
- **Риски:** состав не расписан (wizard не подтверждён); старый пак.
- **Релевантность:** medium.

### 3.10. [Animated Knight Pack (Quaternius)](https://quaternius.com/packs/knightcharacter.html)

- **Тип:** asset-pack (рыцарь, 10 моделей, аксессуары).
- **Цена:** free.
- **Лицензия:** CC0.
- **UE-совместимость:** n/a.
- **Обновление:** июль 2018 (legacy).
- **Чем поможет:** самый дешёвый прототип «короля-рыцаря» для проверки пайплайна миниатюр (TASK-014/015).
- **Риски:** пак 2018 года, качество ниже современных; анимации не детализированы.
- **Релевантность:** low.

## 4. Анимации, VFX и звук

Потребности проекта по D-11 минимальны и конкретны (idle/выпад/вздрог/оседание; перемещение — скольжением, без walk-циклов), по 07 — CUE-001..018 с таймингами. Отсюда оценки ниже.

### 4.1. [Game Animation Sample (Epic Games)](https://www.fab.com/listings/880e319a-a59e-4ed2-b268-b32dac7fa016)

- **Тип:** open-project (500+ анимаций UE5-скелета, Motion Matching локомоция).
- **Цена:** free.
- **Лицензия:** Fab Standard License.
- **UE-совместимость:** заявлено 5.4–5.8 ✓.
- **Обновление:** 2026-08-17.
- **Чем поможет:** официальный эталон анимационной структуры и бесплатный пул клипов под UE5-манекен; отдельные клипы (hit/react) можно ретаргетить на миниатюры.
- **Риски:** центр — локомоция на Motion Matching, которая проекту не нужна: перемещение фигурок — плавное скольжение (D-11), а не walk/run; боевые удары/смерти не акцентированы; проект тяжёлый — переносить точечно.
- **Релевантность (агента):** high; **по решениям проекта — референс, не зависимость** (см. шорт-лист).

### 4.2. [Sword Animset Pro (Kubold)](https://www.fab.com/listings/12783d2f-2bcf-4f3e-9a4a-d554cc3c579a)

- **Тип:** asset-pack (178 mocap-анимаций с мечом).
- **Цена:** $64.99.
- **Лицензия:** Fab Standard License.
- **UE-совместимость:** 4.10–4.27, 5.0–5.6 (5.8 не заявлена; FBX обычно переносится).
- **Обновление:** 2025-06-13 (продаётся с 2016).
- **Чем поможет:** полный боевой набор мечом (атаки/комбо/блоки/реакции/уклонения) для King Arthur (TASK-050).
- **Риски:** реалистичный mocap против контракта «окрашенной статуэтки» (С-2) — ретаргет на стилизованные миниатюры с доводкой; нет анимаций посоха/магии для Merlin; KayKit закрывает мили бесплатно (п. 3.5).
- **Релевантность (агента):** high; **по решениям проекта — покупать только если KayKit-мили не хватит по качеству**.

### 4.3. [UE5 Mixamo Animation Retargeting 2 (UNAmedia)](https://www.fab.com/listings/5eaf2746-1891-435a-837c-67c9f7a847f4)

- **Тип:** editor-plugin.
- **Цена:** $39.99–79.99 (per-user!).
- **Лицензия:** Fab Standard License; **per-user-условие — сверить на листинге/у автора перед покупкой** (EULA-summary Fab разрешает шаринг ассета с соавторами, в т.ч. через приватный репозиторий — уточнено лицензионным ревью 2026-09-27).
- **UE-совместимость:** заявлено 5.0–5.8 ✓.
- **Обновление:** 2026-08-11 (с 2022, активно).
- **Чем поможет:** автоматизация Mixamo→UE5 (Retarget Pose, IK Rig/Retargeter, root bone, Root Motion, batch) — конвейер боевых анимаций дешевле покупки паков.
- **Риски:** платный (число лицензий — по условию листинга, см. выше); Mixamo почти не содержит анимаций крылатых существ (гарпии); нестандартные риги требуют ручной доводки. Бесплатная альтернатива в существующем Blender-пайплайне — mixamo_converter (п. 4.4).
- **Релевантность:** high (если выбран Mixamo-конвейер).

### 4.4. [mixamo_converter (enziop, Blender-аддон)](https://github.com/enziop/mixamo_converter)

- **Тип:** code-library (Blender-аддон).
- **Цена:** free.
- **Лицензия:** GPL-3.0 (на код аддона; на экспортируемые FBX-анимации не распространяется).
- **UE-совместимость:** n/a — экспорт root-motion FBX под скелет Mannequin; официально UE4, кости те же в UE5; 5.8 не заявлена.
- **Обновление:** последний коммит 2024-03-01 (818★).
- **Чем поможет:** пакетная конвертация Mixamo-анимаций (root motion, переименование костей, batch) внутри Blender-пайплайна проекта (D-06, файл 04) — бесплатная альтернатива п. 4.3.
- **Риски:** ориентация на UE4 без гарантий под новые Blender; редкие обновления.
- **Релевантность:** high (как бесплатный вариант Mixamo-конвейера).

### 4.5. [[SFX] Tabletop Games Sound Effect Pack (JDSherbert)](https://jdsherbert.itch.io/tabletop-games-sfx-pack)

- **Тип:** asset-pack (56 звуков, WAV HD/SD).
- **Цена:** £4.99+ (есть бесплатная версия).
- **Лицензия:** royalty-free, **атрибуция обязательна** (JDSherbert в титрах); перепродажа звуков запрещена.
- **UE-совместимость:** n/a.
- **Обновление:** не указана (Released).
- **Чем поможет:** раздача/тасовка/перелистывание карт, кубики, перемещение/удары фишек — ровно CUE-запросы карточного интерфейса (TASK-028 звук-заглушки, TASK-053 полный звук).
- **Риски:** обязательный кредит в титрах; нет UI-звуков кнопок (см. п. 4.6); дата обновления неизвестна.
- **Релевантность:** high. _(Входит в шорт-лист.)_

### 4.6. [[SFX] Ultimate UI Sound Effect Pack (JDSherbert)](https://jdsherbert.itch.io/ultimate-ui-sfx-pack)

- **Тип:** asset-pack (67 UI-звуков).
- **Цена:** £4.99+ (есть бесплатная версия).
- **Лицензия:** royalty-free, атрибуция обязательна.
- **UE-совместимость:** n/a.
- **Обновление:** не указана.
- **Чем поможет:** select/cancel/cursor/error/popup/swipe для UMG-интерфейса RU/EN.
- **Риски:** атрибуция; есть бесплатные CC0-альтернативы (Kenney Interface Sounds, подтверждена агентом: 100 файлов, CC0).
- **Релевантность:** medium.

### 4.7. [Niagara Slash VFX (KC Studio Asia)](https://kcstudioasia.itch.io/unreal-engine-niagara-slash-vfx) ⚠

- **Тип:** asset-pack (10 mesh-based Niagara-слэшей + hit-реакции).
- **Цена:** $15+.
- **Лицензия:** ⚠ **на странице отсутствует вовсе** (ни поля Asset license, ни условий); «стандартного itch.io asset EULA» не существует — без лицензии действует all rights reserved (установлено лицензионным ревью 2026-09-27). До использования получить от автора явное письменное разрешение (коммерческое использование + включение в packaged-сборку), иначе пакет не покупать.
- **UE-совместимость:** 5.0–5.6 (5.8 не заявлена; Niagara обычно обратно совместим).
- **Обновление:** не указана.
- **Чем поможет:** удары мечом и хиты для атак King Arthur (CUE-008..011, TASK-053).
- **Риски:** ⚠ лицензии нет вовсе — права на дистрибуцию не подтверждены (all rights reserved); версии; mesh-слэши подгонять под траектории своих анимаций; сверка стиля с D-02.
- **Релевантность:** medium.

### 4.8. [Stylized VFX Bundle (Vefects)](https://vefects.itch.io/stylized-vfx-bundle-unreal-engine) ⚠

- **Тип:** asset-pack (большой бандл Niagara-эффектов).
- **Цена:** $89.99+.
- **Лицензия:** ⚠ **полностью отсутствует** (нет ни поля Asset license, ни текста условий) — all rights reserved; «стандартного itch.io asset EULA» не существует (установлено лицензионным ревью 2026-09-27). Запросить у автора явный EULA (коммерческое использование, дистрибуция в сборке, ограничения на redistribution исходников Niagara) до оплаты; при молчании не использовать.
- **UE-совместимость:** «designed for Unreal Engine», версии не указаны.
- **Обновление:** опубликован ~16.09.2026, обновлён ~17.09.2026.
- **Чем поможет:** магия/способности (Merlin/Medusa) и AoE-эффекты.
- **Риски:** ⚠ нет ни лицензии, ни версий UE; аниме-уклон стиля против «мрачноватой атмосферной» диорамы (D-02); цена выше средней. Перед покупкой — запросить у автора EULA и проверку на 5.8.
- **Релевантность:** medium.

### 4.9. [Content Examples (Epic Games)](https://www.fab.com/listings/4d251261-d98c-48e2-baee-8f4e47c67091)

- **Тип:** open-project (демо-комнаты всех систем движка).
- **Цена:** free.
- **Лицензия:** Fab Standard License.
- **UE-совместимость:** 5.0–5.8 ✓.
- **Обновление:** 2026-06-17; рейтинг 4.6 (74 оценки).
- **Чем поможет:** Niagara-примеры (дым/частицы/ambient) как заготовки атмосферных эффектов (TASK-043) — копировать системы точечно.
- **Риски:** эффекты демонстрационные, не production-ready; проект тяжёлый.
- **Релевантность:** medium.

### 4.10. [Free Fantasy Medieval Ambient Music Pack (alkakrab)](https://alkakrab.itch.io/free-fantasy-medieval-ambient-music-pack) ⚠

- **Тип:** asset-pack (10 эмбиент-треков + лупы).
- **Цена:** free.
- **Лицензия:** ⚠ «Absolutely Free For Commercial use» — заявление автора без формального документа (поле Asset license отсутствует; на прямой вопрос о CC0/CC-BY автор ответил «подумаю» и лицензию не указал — подтверждено лицензионным ревью 2026-09-27).
- **UE-совместимость:** n/a (WAV/MP3/Ogg).
- **Обновление:** не указана; рейтинг 5.0 (14 оценок).
- **Чем поможет:** фоновая музыка партии/меню (музыка-стейты TASK-053).
- **Риски:** ⚠ для дистрибуции: письменное подтверждение от автора (alkakrab04@gmail.com) с указанием лицензии/атрибуции либо замена на проверяемую CC0-музыку — добавлены по итогам ревью 2026-09-27: FreePD и Kenney Music/Jingles (CC0), Incompetech (CC BY 4.0, обязательная атрибуция) — п. 7.4.
- **Релевантность:** medium.

## 5. Open-source проекты и код

### 5.1. [UE5Coro (landelare)](https://github.com/landelare/ue5coro)

- **Тип:** code-library (C++20-корутины для UE5).
- **Цена:** free.
- **Лицензия:** BSD-3-Clause-Clear.
- **UE-совместимость:** UE5 + C++20; матрицы версий нет — 5.8 проверять сборкой.
- **Обновление:** push и релиз v2.3.2 — 2026-07-19 (проверено gh api в этой сессии: 1110★, лицензия подтверждена).
- **Чем поможет:** латентные операции (HTTP-мутации, WS-события, таймеры CUE-очереди, загрузка ассетов) без callback-ад — ядро синхронизации TASK-023 и мутационный гейт INT-005.
- **Риски:** нет матрицы версий движка; Clang/LLVM-сборка нестабильна (по автору); брать только numbered release v2.3.2.
- **Релевантность:** high. _(Входит в шорт-лист.)_

### 5.2. [PoolManager (JanSeliv)](https://github.com/JanSeliv/PoolManager)

- **Тип:** plugin (пулинг UObject/акторов/виджетов).
- **Цена:** free.
- **Лицензия:** MIT.
- **UE-совместимость:** актуальный бейдж UE 5.7 (changelog: 5.7 2026-01, 5.6 2025-11, 5.5 2025-01); 5.8 не заявлена.
- **Обновление:** push 2026-07-21 (проверено gh api: 186★, MIT) — активная поддержка.
- **Чем поможет:** переиспользование виджетов карт/тултипов/эффектов урона — поддержка кадрового бюджета 1080p@60 (D-07, TASK-026/030).
- **Риски:** 5.8 не заявлена; API менялся между версиями — зафиксировать совместимый релиз.
- **Релевантность:** high.

### 5.3. [UMG MCP for Unreal Engine 5.8 (winyunq/UnrealMotionGraphicsMCP)](https://github.com/winyunq/UnrealMotionGraphicsMCP)

- **Тип:** tool (MCP-сервер для UMG).
- **Цена:** free (есть листинг и на Fab).
- **Лицензия:** MIT.
- **UE-совместимость:** заявлена UE 5.8, Win64 — точное совпадение с проектом (`.uproject`: EngineAssociation 5.8; плагин ModelContextProtocol уже включён).
- **Обновление:** push 2026-08-02 (проверено gh api: 204★, MIT).
- **Чем поможет:** AI-агент создаёт/правит UMG-виджеты, layout, материалы и UMG-анимации через явные tool-calls — ускорение сборки экранов TASK-025/026, семейств TASK-051, инспектора/паузы TASK-054.
- **Сверка с встроенным (ревью 2026-09-27):** в `.uproject` включён и `AllToolsets` — по докам Epic именно он поставляет в UE 5.8 MCP-инструменты редактора (SceneTools/ActorTools/MaterialInstanceTools/ObjectTools). До внедрения стороннего MCP-сервера — инвентаризация его toolset'ов; правки материалов по возможности вести встроенным MaterialInstanceTools, UMG MCP брать только за виджет-специфичными функциями (создание UMG-виджетов, layout, UMG-анимации), чтобы не дублировать встроенное. Источник: dev.epicgames.com/documentation/unreal-engine/unreal-mcp-in-unreal-editor.
- **Риски:** молодой проект одного автора; удалённое управление редактором — проверять на неважной ветке; генерируемые виджеты ревьюить.
- **Релевантность:** high. _(Входит в шорт-лист.)_

### 5.4. [UE-BUITween (benui-dev)](https://github.com/benui-dev/UE-BUITween)

- **Тип:** code-library (твины UMG-виджетов на C++).
- **Цена:** free.
- **Лицензия:** CC0-1.0 (проверено gh api).
- **UE-совместимость:** база UE4/UMG, .uplugin без привязки; на 5.x официально не тестировалась.
- **Обновление:** push 2023-08-05 (проверено gh api: 320★) — стабильна, не обновляется.
- **Чем поможет:** анимации руки/карт (выпад, hover, сброс, полёт в discard — CUE-005), появления панелей — вместо ручных таймлайнов; тикает на паузе.
- **Риски:** проверить компиляцию под 5.8; для сложных траекторий (дуга полёта карты) свой код.
- **Релевантность:** high. _(Входит в шорт-лист.)_

### 5.5. [ue5-cardgame (perfect-hand / Nick Pruehs)](https://github.com/perfect-hand/ue5-cardgame) ⚠

- **Тип:** plugin (каркас карточной игры).
- **Цена:** free.
- **Лицензия:** MIT.
- **UE-совместимость:** ранние UE5, версия 0.0.1 beta; не обновлялся под 5.8.
- **Обновление:** push 2023-03-19 — заброшен ~3.5 года. ⚠
- **Чем поможет:** паттерны модели (data assets карт/колод, пайлы, события) как отправная точка UmModel.
- **Риски:** бета 2023 года; собственный RPC-нетворкинг не нужен (бэкенд GraphQL); API UE устарели.
- **Релевантность:** medium (только чтение как референс).

### 5.6. [TurnBasedSample (BinaryBard996)](https://github.com/BinaryBard996/TurnBasedSample)

- **Тип:** open-project (пошаговый GAS).
- **Цена:** free.
- **Лицензия:** MIT.
- **UE-совместимость:** README: UE 5.6/5.7.
- **Обновление:** push 2026-02-08.
- **Чем поможет:** паттерн «эффекты, тикающие по ходам», если клиент будет визуализировать длительности бустов/схем.
- **Риски:** **прямое столкновение с 08 §1: GAS в проекте запрещён** («Запреты: ... GAS (Gameplay Ability System)»); кастомная копия GAS-плагина движка = отвал патчей при обновлениях UE; логика ходов у бэкенда. Как референс чтения — допустимо, как зависимость — нет.
- **Релевантность (агента):** medium; **по решениям проекта — не интегрировать.**

### 5.7. [Bomber (JanSeliv)](https://github.com/JanSeliv/Bomber)

- **Тип:** open-project (полная мультиплеер-игра).
- **Цена:** free.
- **Лицензия:** MIT.
- **UE-совместимость:** современный UE5.
- **Обновление:** push 2026-09-23 (388★) — очень активный.
- **Чем поможет:** эталон модульной архитектуры UE5 (Game Features, модули, CI, пулинг в бою) для организации UmNet/UmModel/UmClient (TASK-010).
- **Риски:** сетевой код (Steam/UE-replication) неприменим — у проекта GraphQL-бэкенд.
- **Релевантность:** medium (учебник, не кодовая база).

### 5.8. [ACGCard (egojump)](https://github.com/egojump/ACGCard) ⚠

- **Тип:** open-project (Hearthstone-like на UE 4.18).
- **Цена:** просмотр.
- **Лицензия:** ⚠ нет файла лицензии = all rights reserved — код копировать нельзя.
- **UE-совместимость:** UE 4.18 (2018).
- **Обновление:** push 2018-03-01 — мёртвый.
- **Чем поможет:** чтение о том, как в UE организуют стол/руку/таргетинг карточной игры.
- **Риски:** без лицензии, устаревший API.
- **Релевантность:** low.

## 6. Интеграция с GraphQL-бэкендом

Ключевой вывод обоих агентов темы: **готового UE-плагина с подписками graphql-ws (graphql-transport-ws) не существует** — ни на Fab, ни на GitHub. Queries/mutations закрываются плагином Pandores; подписки — тонким собственным слоем поверх WebSocket-транспорта. Авторизация JWT в connection_init и реконнект с replay подписок — паттерн есть в CrowdyCPP (MIT).

### 6.1. [GraphQL Client for Unreal Engine (Pandoa/Pandores)](https://www.fab.com/listings/531b2dce-cac7-42a5-905b-143ef7b64b75) ⚠

_Объединённая находка двух агентов; дубль удалён._

- **Тип:** plugin (C++ + Blueprints).
- **Цена:** $14.99–29.99 (Standard, по JSON-LD листинга).
- **Лицензия:** Fab Standard License; исходники — через покупку (GitHub-репозиторий только документация).
- **UE-совместимость:** на листинге заявлена **5.8** (обновление 2026-07-06).
- **Обновление:** Fab 2026-07-06; док-репозиторий push 2026-07-04 (проверено gh api в этой сессии).
- **Чем поможет:** асинхронные queries/mutations из C++/BP, запросы в .graphql-файлах, WalkResult по вложенным полям, хедеры на лету (JWT Bearer через SetHeader) — закрывает HTTP-половину интеграции (11 игровых мутаций, контент-queries, TASK-011/023–034).
- **Риски:** ⚠ подписки НЕ поддерживаются (в доках только queries/mutations — проверено агентом по тексту документации); закрытый код; один автор, отзывов нет; два ID листинга Fab: 531b2dce-… рендерится как живой листинг «GraphQL Client» (обновлён 2026-07-06 — подтверждено фактчекингом), 2e4c42bb-… напрямую заблокирован Cloudflare, но на него ссылаются собственные доки автора — оба, по-видимому, существуют, канонический не установлен; цена и блок версий UE не перепроверены — перед оплатой открыть листинг в браузере и сверить цену/версии.
- **Релевантность:** high. _(Входит в шорт-лист.)_

### 6.2. [WebSocket Client for Unreal Engine / BlueprintWebSocket (Pandores)](https://github.com/pandoa/BlueprintWebSocket) ⚠

- **Тип:** plugin (WS-клиент для C++/BP).
- **Цена:** ⚠ платный на Fab, точная цена не проверена (листинг за Cloudflare); документация бесплатна.
- **Лицензия:** Fab Standard License; GitHub — только документация (проверено gh api: push 2026-09-23, 44★, лицензии нет).
- **UE-совместимость:** C++/BP, автореконнект-хелперы и cacert.pem для пакетной сборки — по докам; версии UE и платформы в доках НЕ указаны — атрибуция только Fab-листингу, который не проверен (Cloudflare) (исправлено фактчекингом 2026-09-27).
- **Обновление:** docs-репозиторий push 2026-09-23 (активно поддерживается).
- **Чем поможет:** WS-транспорт с событиями OnConnected/OnMessage/OnClosed, хедерами (Authorization) и автореконнектом — база для подписок gameStateUpdated (TASK-011/023, реконнект TASK-033).
- **Риски:** протокол graphql-transport-ws (connection_init/subscribe/next/complete/ping-pong) всё равно пишется вручную — автореконнект плагина не знает о протоколе и INT-004 (переподписка с since=lastSeq), так что ключевое преимущество всё равно обёртывается своим кодом; цена/версии не проверены; тот же единственный автор, что и 6.1.
- **Релевантность:** medium — **опция-дубль встроенного модуля** (п. 6.3); ценна только helper-нодами автореконнекта (понижено с high по итогам ревью 2026-09-27).

### 6.3. [Unreal Engine WebSockets module (IWebSocket, встроенный)](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/WebSockets/IWebSocket)

- **Тип:** code-library (runtime-модуль движка).
- **Цена:** входит в движок.
- **Лицензия:** UE EULA.
- **UE-совместимость:** официальная документация версии 5.8 ✓.
- **Обновление:** документация актуальна для 5.8.
- **Чем поможет:** Connect/Close/Send + делегаты OnMessage и др. — подписки graphql-ws без сторонних плагинов и лицензий; токен передаётся в payload connection_init (хедеры handshake не нужны).
- **Риски:** нет автореконнекта/heartbeat — писать самому поверх OnClosed (паттерн — CrowdyCPP, п. 6.4); модуль подключается в Build.cs (UmNet).
- **Релевантность:** high — **транспорт рекомендованного решения о подписках** (шорт-лист №4; повышено с medium по итогам ревью 2026-09-27). _(Входит в шорт-лист как часть решения о подписках.)_

### 6.4. [CrowdyCPP (Crowded Kingdoms C++ SDK)](https://github.com/CrowdedKingdoms/CrowdyCPP)

- **Тип:** code-library (C++20).
- **Цена:** free.
- **Лицензия:** MIT (проверено gh api: push 2026-09-26).
- **UE-совместимость:** движко-независимый C++20; обёртка CrowdySDK-Unreal требует UE 5.8.
- **Обновление:** v0.29.x, push 26.09.2026 — очень активная разработка (0★ — экосистема молодая).
- **Чем поможет:** открытая реализация graphql-transport-ws: connection_init с авторизацией, bounded-реконнекты, **повтор активных подписок после переподключения** — ровно паттерн INT-004 (gap-протокол, переподписка с since) для TASK-023/033.
- **Риски:** написан под их платформу (двухтокенная модель) — адаптировать/вырезать graphql-слой; молодой проект; C++20 (совместим с тулчейном проекта).
- **Релевантность:** medium. _(Входит в шорт-лист как референс протокола.)_

### 6.5. [cppgraphqlgen (Microsoft)](https://github.com/microsoft/cppgraphqlgen)

- **Тип:** code-library (кодогенератор типизированных GraphQL-клиентов).
- **Цена:** free.
- **Лицензия:** MIT.
- **UE-совместимость:** не UE-плагин; C++20, CMake/vcpkg — интеграция как ThirdParty вручную.
- **Обновление:** коммиты до 15.09.2026; стабильный релиз v4.5.9 (дек. 2024).
- **Чем поможет:** clientgen генерирует C++-типы запросов/переменных/ответов из GraphQL-документа — убирает ручной JSON-парсинг queries/mutations.
- **Риски:** нет транспорта/подписок; нет UE-обвязки; редкие стабильные релизы; двойная фаза парсинга JSON-внутри-строк (INT-002) всё равно своя.
- **Релевантность:** medium (опционально, после спайка TASK-011).

### 6.6. [Easy Jwt (Dynamic Servers Systems / sha3sha3)](https://www.fab.com/listings/5a7b13f17ce04fc3b4a571a8faf58b4a)

- **Тип:** plugin (JWT Engine Subsystem).
- **Цена:** $9.99 на Fab; GitHub-версия бесплатна (HS256/384/512).
- **Лицензия:** MIT (GitHub) / Fab Standard (marketplace-версия).
- **UE-совместимость:** UE4/UE5 по README; Win64/Linux/ARM64.
- **Обновление:** Fab 2024-06-19; GitHub push 2024-06-01 — практически заморожен.
- **Чем поможет:** генерация/подпись/верификация JWT, извлечение claims, если клиенту понадобится локальная проверка токена.
- **Риски:** по схеме проекта клиенту достаточно хранить refresh в USaveGame и слать Bearer (02 §2.1) — криптографическая верификация не нужна; проект не поддерживается.
- **Релевантность:** medium (фактически опционален до появления реальной потребности).

### 6.7. [IXWebSocket (machinezone)](https://github.com/machinezone/IXWebSocket)

- **Тип:** code-library (зрелый C++ WS-клиент/сервер).
- **Цена:** free.
- **Лицензия:** BSD-3-Clause.
- **UE-совместимость:** не UE-плагин — ThirdParty; TLS через OpenSSL/MbedTLS (на Windows сборка сложнее).
- **Обновление:** v12.0.1 (25.06.2026), push 21.09.2026.
- **Чем поможет:** автореконнект с экспоненциальным backoff и heartbeat из коробки — если собственного контроля над реконнектом поверх IWebSocket не хватит.
- **Риски:** дублирует встроенный модуль движка; ручная интеграция; у автора мало времени на проект.
- **Релевантность:** low (запасной вариант).

## 7. Дополнения по итогам адверсарального ревью (2026-09-27)

Четыре категории, отсутствовавшие в исходном исследовании (замечания Рецензента-практика; ссылки проверены веб-поиском ревьюера, независимо фактчекером не перепроверялись — статусы в findings.json: unconfirmed, кроме Send2UE). В сводной таблице — строки 49–53.

### 7.1. UI-иконки и глифы

Потребность: UI-ICON-ZONE (12 зон: глиф+буква+штриховка), UI-ICON-ACTION («шаг», «меч», «метка»), UI-CURSOR, UI-LOADER — прямое требование P1/QA-011 («не только цвет»), нужное уже в прототипах подсветок TASK-027 и в полном объёме в TASK-051 (L). Из 48 исходных находок ближе всего Penusbmic и cafeDraw — оба отклонены по стилю/разрешению для чистового UI.

- **[Kenney Game Icons](https://kenney.nl/assets/game-icons)** — CC0, без атрибуции, ~2000 глифов; плюс UI-паки и input prompts ([kenney.nl/assets](https://kenney.nl/assets)). База для 12 зон; обводка/буквы — своим кодом.
- **[game-icons.net](https://game-icons.net)** — 4000+ векторных SVG (мечи/символы), CC BY 3.0 с атрибуцией — точечные тематические докупки.

### 7.2. Материалы поверхности доски (булыжник)

TASK-040 (L) — «булыжник, швы» финальной доски Cobble City, эталонный арт-объект по D-04. Единственный рекомендованный окруженческий пак (PolyArt3D) булыжного мощения в составе не имеет.

- **Megascans на Fab** — бесплатно для UE-проектов: поиск «cobblestone surface» с фильтрами Price: Free + Unreal Engine на [fab.com](https://www.fab.com) (сканы поверхностей и декалы под тайлы). Материал плиток — оттуда; геометрия остаётся параметрической из boardState (TASK-020), стиль сверять с D-02/03 §1.

### 7.3. Автоматизация конвейера Blender→UE

По D-06 весь арт идёт Blender→FBX→UE; четыре задачи (спайк D TASK-014, TASK-015, эталон Medusa TASK-041 L, остальные модели TASK-050 L) крутятся через ручной batch_export/импорт; единственный Blender-инструмент исходных находок — mixamo_converter (частный случай анимаций Mixamo).

- **[Send2UE (Epic Games BlenderTools)](https://github.com/EpicGames/BlenderTools)** — официальный open-source аддон (MIT): one-click экспорт мешей/скелетных мешей/анимаций из Blender в открытый UE-проект с реимпортом; [quickstart](https://epicgames.github.io/BlenderTools/send2ue/introduction/quickstart.html). Совместимость версий Blender/UE сверять по релизам (актуальны 2.6.x). Лицензия и активность проверены gh api в сессии финализации (MIT, не архивирован, push 2026-09-09).

### 7.4. CC0-музыка

Единственная исходная музыкальная находка (alkakrab) не имеет формальной лицензии (см. п. 4.10). Добавлены проверяемые источники для TASK-053 (музыка-стейты меню/партия/результат, кроссфейды, акценты победы/поражения):

- **[FreePD](https://freepd.com)** — CC0, без атрибуции.
- **[Kenney Music/Jingles](https://kenney.nl/assets)** — CC0.
- **[Incompetech](https://incompetech.com)** (Kevin MacLeod) — большой каталог, но CC BY 4.0 с обязательной атрибуцией.

Для внутреннего прототипа (GAP-019) атрибуция некритична, для вариантов «после MVP» предпочесть CC0.

---

## Оговорки к данным (сводно)

1. **Fab за Cloudflare**: цены/версии/даты для части листингов (Synty, BlueprintWebSocket, ряд версионных блоков) получены агентами через SSR-прокси и JSON-LD, а не напрямую; всё, что помечено «не проверено», требует открытия листинга в браузере перед покупкой.
2. **UE 5.8 заявлена** у 9 из 48: подтверждено ревью 2026-09-27 — Easy RTS Controller, Stylized Medieval Town (PolyArt3D), Fantasy UI Toolkit (5.0–5.8, уточнено ревью), UMG MCP, IWebSocket (доки); блок версий не перепроверен (клиентский рендер, замаскан в статике) у Game Animation Sample, Mixamo Retargeting 2, Content Examples, GraphQL Client (Pandores). Для остальных платных находок совместимость с 5.8 — риск покупки.
3. Компиляцию/импорт ни одного плагина/пака в реальный UE-проект агенты и ревьюеры не выполняли — все оценки совместимости по документации.
4. Лицензии: **Nice Card Game Template — CC BY-SA 3.0 share-alike** (только внутренний прототип, до релиза заменить); у Slash VFX (KC Studio), Stylized VFX Bundle (Vefects), Ambient Music (alkakrab) формальной лицензии **нет вовсе** («стандартного itch.io asset EULA» не существует — без лицензии действует all rights reserved); ACGCard — лицензии нет вообще; у Quaternius — расхождение CC0/QAL (для игры некритично, но сами файлы паков в публичный репозиторий не класть). MIT/BSD-компоненты (UltimateUI, PoolManager, CrowdyCPP, IXWebSocket, ue5coro и др.) и CC BY (Penusbmic) требуют сохранения нотисов/атрибуции при дистрибуции — реестр THIRD_PARTY_NOTICES см. в шорт-листе.
5. Прямых стилизованных аналогов Медузы/гарпий не найдено (найденное — рипы игр); заявление агента о Synty как «названном в ТЗ стиле» документами проекта не подтверждается.
6. **Главные лицензионные блокеры до публичного релиза — вне выбора ассетов** (лицензионное ревью 2026-09-27, детали — в review-отчёте и шорт-листе): (а) оба GitHub-репозитория проекта публичны (`gh api`: `private:false` у renlok87/unmatched и renalsafiulin/unmached — перепроверено финализатором) и содержат ~1938 закоммиченных .webp скрап-арта Unmatched (подтверждено `git ls-files` в репозитории), который RISK-003/GAP-019 разрешают только для внутреннего прототипа, — публичный репозиторий уже является распространением; сторонние Fab/JDSherbert/QAL-ассеты в публичный репо не класть (Fab EULA разрешает шаринг только через private repository, Terms JDSherbert прямо запрещают открытые репозитории); (б) имя «Unmatched», правила и контент — рекреация Restoration Games «Battle of Legends Vol. 1» (rulebook — нормативный источник по 12-validation-report) без разрешения и ТМ-анализа — до релиза либо явное разрешение правообладателя, либо ребрендинг + замена контента.

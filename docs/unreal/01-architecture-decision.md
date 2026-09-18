# 01. Architecture Decision Record — нативный UE 5.8-клиент Unmatched

> Статус: **принято**. Дата: 2026-09-02. Роль: главный архитектор. Ветка репозитория: `fix/admin-panel`.
> Входы: три кандидата (`docs/unreal/_design/candidate-1.md`, `candidate-2.md`, `candidate-3.md`), три независимых вердикта судей, `docs/unreal/00-mcp-verification.md`, research-файлы `docs/unreal/_research/R1…R9`. Все факты из вердиктов, на которые опирается решение, перепроверены напрямую по исходникам UE 5.8.2 (`$UE` = `C:\Program Files\Epic Games\UE_5.8\Engine`) и бэкенда (`backend/src/**`, `scripts/**`); ссылки вида `файл:строка` — на них. Ссылки `R3 §2.7` — на разделы research-файлов; `К1 §3.5.1` / `candidate-1.md:549` — на кандидатов.
> Назначение: основа следующей фазы — десяти подробных планов (`docs/unreal/02…11-*.md`) и сниппетов (`docs/unreal/snippets/`). Имена модулей, классов, файлов, ассетов и тегов в этом документе **окончательные**; планы обязаны их использовать без переименований.

---

## 1. Контекст и ограничения

### 1.1. Что дано

| Компонент | Факт | Источник |
|---|---|---|
| Бэкенд | NestJS 11 + Apollo Server 5.3 + `graphql-ws` 6.0.6; один endpoint `/graphql` (HTTP POST для queries/mutations, WebSocket-upgrade того же пути для подписок, сабпротокол строго `graphql-transport-ws`); JWT HS256, access 1 ч / refresh 24 ч с ротацией; `schema.gql` в репозитории нет (`autoSchemaFile: true`) | R1 §1 п.1-3, п.11; `backend/src/graphql/graphql.module.ts:14-35` |
| Игровой контракт | 11 gameplay-мутаций с единым `GameMutationResult { state: String, sequenceNumber, timestamp, phase, currentTurnPlayerId, turnCount }`; полный отфильтрованный `GameState` — JSON-строкой; подписка `gameStateUpdated` — пять JSON-строк **без** `decks`/`discardPiles`; `sequenceNumber` +1 на мутацию | R3 §1; `backend/src/games/dto/gameplay.dto.ts:437-495`; `backend/src/games/resolvers/game-subscription.resolver.ts:44-63` |
| Правила | Сервер — единственный арбитр; клиент только подсвечивает кандидатов и обрабатывает `BadRequestException` | R4 §1, §3.1 |
| Веб-клиент | Эталон production-пути `/lobby → /room → /game`; оптимистики нет; «мгновенный отклик» — применение `state` из ответа мутации; всё остальное (локальный движок, deprecated-мосты, неподключённые Phaser-подсистемы) не переносится | R7 §1 п.1, §2.8, §2.14 |
| Админка | Остаётся целиком; UE нужны только `heroList`/`boardList` (cuid героя/доски под JWT любого игрока) | R6 §1 п.1-2, §3.2 |
| Unreal MCP | Работает: встроенный Experimental-плагин `ModelContextProtocol` + `AllToolsets`, Streamable HTTP `http://127.0.0.1:8123/mcp`, один открытый проект = один сервер; C++ MCP не создаёт; `LiveCodingToolset` — отдельный EditorOnly-плагин вне `AllToolsets` | `docs/unreal/00-mcp-verification.md:5-14, 56-60` |
| Движок | UE 5.8.2 (CL 56702186); всё нужное для GraphQL есть в модулях `HTTP`, `WebSockets`, `Json`, `JsonUtilities`; готовых GraphQL-плагинов с `graphql-transport-ws` нет; WebP нативно не декодируется | R8 §1 п.1-4, п.7 |

### 1.2. Жёсткие ограничения решения

1. **Бэкенд не меняется**, кроме явно перечисленного реестра предпосылок §6 (каждая — с приоритетом и клиентским обходом до фикса). Клиент обязан корректно работать против текущего `HEAD` бэкенда с обходами.
2. **UE 5.8.2**, установленный локально; целевая платформа MVP — Win64 (Development Editor + Development Client); Mac/iOS/Android — v2 (R8 §2.15).
3. **Никаких Beta/Experimental плагинов в рантайме**: `GameFeatures`, `ModularGameplay`, `DataRegistry`, `ModelViewViewModel` — `IsBetaVersion: true` (R8 §2.13); `ModelContextProtocol`, `AllToolsets`, `LiveCodingToolset` — только `TargetAllowList: ["Editor"]`.
4. **Команда — 1 разработчик + агенты через MCP.** Всё, что агент может сделать тулсетами (UMG, DataTable, материалы, сцена, тесты), делается тулсетами; C++ пишется в файлы и собирается `Build.bat`/Live Coding.
5. **MVP — партия Medusa vs King Arthur** в приватной комнате между двумя UE-клиентами и между UE и веб-клиентом (кросс-проверка контракта). Критерии готовности — К1 §1.5 (пять пунктов) без изменений.
6. **Никакой локальной копии правил как истины и никакой предикции.** Подсветки — «советчик», сервер — арбитр (R4 §3.1, R7 §2.8).

### 1.3. Двенадцать фактов контракта, которые архитектура обязана соблюдать

| # | Факт | Источник |
|---|---|---|
| 1 | Сервер шлёт WS **ping-фрейм** каждые 12 с и `socket.terminate()` без close-фрейма, если pong-фрейм не пришёл за 12 с; окно обрыва ≈ 24 с. Прикладной JSON `{"type":"ping"}` — не pong-фрейм | R1 §2.4 п.9; `backend/node_modules/graphql-ws/dist/use/ws.js:5,44-58` |
| 2 | `connection_init` — ≤ 3 с после открытия сокета (иначе 4408); `connection_ack` приходит всегда и **не** подтверждает токен; auth-ошибка приходит на конкретный `subscribe` как `next{errors}`+`complete` либо `error`, без `extensions.code` | R1 §2.4; `graphql.module.ts:22-35` |
| 3 | Ошибки — в теле при HTTP 200/400; `code` читать из `extensions.code` **и** верхнеуровневого `code`; в production `formatError` маскирует всё, кроме `BAD_USER_INPUT`/`GRAPHQL_VALIDATION_FAILED`/подстрок `not found`/`unauthorized`, в `Internal server error` | R1 §2.10; `backend/src/graphql/graphql.module.ts:68-92` |
| 4 | Скаляры: `since`, `sinceSequence`, `gameSequence`, `GameStateResponse.sequenceNumber/turnCount`, `seatOrder`, `version` — `Float`; `DateTime` в GraphQL-полях — epoch-миллисекунды; даты внутри JSON-состояния — ISO-строки | R3 §2.4, §2.11 |
| 5 | `combatInfo.attackerId` — id **бойца**, `defenderId` — **userId**; `combatInfo.timeoutAt` никогда не выставляется — дедлайн защиты считается локально `startedAt + 30 с` | R3 §2.9.8, §4.2; R4 §2.5.2 |
| 6 | Auto-resolve по таймауту только переводит фазу в `COMBAT_RESOLVE` (+1 seq) и **не** наносит урон; бой висит до `resolveCombat` любым участником | `backend/src/games/services/combat-timeout.service.ts:260-282` |
| 7 | `resolvePendingEffect` без фазового guard'а; сдвиг seq в фазе `COMBAT` заставит auto-resolve пропустить срабатывание (`state.sequenceNumber > attackSequenceNumber → skip`) | R3 §4.12; `combat-timeout.service.ts:220` |
| 8 | `STATE_UPDATED` публикуется внутри `saveState` (шаг 7 конвейера), а `GameMutationResult` формируется на шаге 12 — эхо подписки для seq N может обогнать HTTP-ответ | R3 §2.2; `backend/src/games/game-state.service.ts:215`; `backend/src/games/resolvers/game-actions.resolver.ts:170,222-226` |
| 9 | После `GAME_OVER` `Game.status` остаётся `IN_PROGRESS` и занимает лимит 5 активных игр, пока участник не вызовет `leaveGame`/`abortGame`; победитель — `metadata.winnerId` | R2 §1 п.2, §3.13; `backend/src/games/game.service.ts:31,106-107` |
| 10 | `selectHero(heroId)`/`createGame(boardId)` принимают Prisma cuid, которые публичные `heroes`/`boards` не отдают (`id = name`); cuid — только из `heroList`/`boardList`. `hero(id:<cuid>)` заработает лишь после коммита незакоммиченной правки `getHeroBySlug` | R6 §2.4, §2.8; рабочее дерево `backend/src/content/content-db.service.ts:183-189` |
| 11 | `idempotencyKey` есть только у `createGame`; `ValidationPipe` с `forbidNonWhitelisted` отвергает любые лишние поля входных DTO | R1 §2.12, §2.3 |
| 12 | Матчмейкинг и presence по коду неработоспособны (нет guard'ов, `user.userId` vs `id`, `GamePlayer` не создаются, `presenceUpdated` не AsyncIterator); ranged-досягаемость — по legacy `cell.zone`, а не пересечению `zones[]`; дальности `attackRange` через GraphQL не экспортируются | R2 §4.1, §4.3, §4.4; R4 §2.6.1, §3.6 |

---

## 2. Решение

### 2.1. Вердикт судей

| Кандидат | Судья 1 (feas/contr/vel/risk/ext = total) | Судья 2 | Судья 3 | Сумма |
|---|---|---|---|---|
| **К1 «Тонкий server-authoritative клиент»** | 9/9/9/9/6 = **42** | 9/8/9/8/7 = **41** | 9/9/9/8/7 = **42** | **125** |
| К3 «Модульная Lyra-style архитектура» | 7/7/8/6/9 = 37 | 6/6/7/6/9 = 34 | 7/8/8/6/9 = 38 | 109 |
| К2 «Предиктивный клиент с зеркалом правил» | 6/8/5/5/7 = 31 | 6/8/5/5/8 = 32 | 5/9/6/4/6 = 30 | 93 |

Все три судьи независимо выбрали К1 победителем с обязательными графтами из К3 и К2. Общее у всех вердиктов: (а) К1 точнее всех по контракту в критичных местах (Float-скаляры, instance-id карт, `attackerId`/`defenderId`, отсутствие `timeoutAt`, auto-resolve без урона, отказ от `eventsSince`, wire-enum как строки); (б) К1 единственный закрывает протухание `decks/discardPiles` у защитника; (в) у К1 лучший профиль скорости с MCP (минимум C++, максимум UMG/DT через тулсеты); (г) слабость К1 — расширяемость (монолитный модуль, HUD через фиксированный C++-класс) и заниженная оценка 43 ч/д.

### 2.2. Формула решения

**Базис — Кандидат 1** (тонкий server-authoritative клиент: HTTP + graphql-transport-ws, снапшоты с дедупликацией по `sequenceNumber`, парсер + диф, UMG/CommonUI через MCP).

**Графты** (полный список — §2.3): из К3 — фаза 0 спайков, снимок introspection и тест операций, GameplayTags как язык состояний с гейтингом через `FGameplayTagQuery`, `PresentedState ≠ Current`, трёхуровневый фасад контента, cue-шина (без GAS), mobile-хуки раскладки, `UmMockBackend`, таблица тулсетов MCP, класс ошибки `Opaque`, разведение авто-резолва по времени; из К2 — `bDecksStale`, таблица паритета и намеренных отличий + `bServerWouldAllow`, паритет-фикстуры (узко), две функции слага, `WhyNot`, абстракции транспорта, реестр серверных предпосылок, запрет pending-резолва в `COMBAT`, порт MCP 8124, `FUmCombatPreview` (v1).

**Два структурных отклонения от К1**, продиктованных вердиктами: (1) четыре модуля вместо двух (`UmNet`, `UmModel`, `UmClient`, `UmEditor`) — чистая тестируемая модель отделяется от UObject-мира, а сеть — от игры; это дешёвый ответ на «extensibility 6» без 10 плагинов К3; (2) один персистентный уровень `L_Main` вместо трёх карт — снимает ловушку создания `WBP_RootLayout` в `ULocalPlayerSubsystem::Initialize` (К1 fatal #11) и весь класс проблем «WS/подписки переживают `OpenLevel`».

**Отвергнуто** (подробно §7): предикция и зеркало правил (К2), `GameFeatures`/`ModularGameplay`/`DataRegistry`/`GameplayAbilities` в рантайме (К3), ручной `FromJson` для DTO (К2), camelCase-`UPROPERTY` (К1), `PingPongInterval=0` (К2), UI «BLIND BOOST» (К2), классификация `BAD_USER_INPUT` как `ClientBug` (К3).

### 2.3. Обязательные графты — куда встроены

| # | Графт | Откуда | Куда в решении |
|---|---|---|---|
| G1 | Фаза 0 — пять блокирующих спайков E0.1–E0.5 с критериями приёмки | К3 §7 | §9.1; ворота перед эпиками MVP; E0.2 (подписка idle > 5 мин) — единственная проверка риска №1 (факт §1.3 п.1) |
| G2 | Снимок introspection в репозитории + автоматическая сверка каждого документа операции | К3 §3.2.6, §6.1 | `unreal/Schema/schema.introspection.json`, `unreal/Tools/ops-check.mjs` (graphql-js `validate`), генерация `UmOps.gen.h`, spec `Unmatched.Model.OpsGenerated` (§4.3, §5.9) |
| G3 | GameplayTags как язык состояний + гейтинг аффордансов `FGameplayTagQuery`; cue-ветка под корнем `GameplayCue.` | К3 §3.9, §3.6.1; fatal К3 #3 | `UmModel/Public/UmTags.h` (нативные теги), `UUmStateSubsystem::GetMatchTags()`, `FUmLegalActions`, `UUmGameHudModel::MatchTags` (§5.6) |
| G4 | Трёхуровневый фасад контента Baked → Runtime → Placeholder; пакетирование по сетам | К3 §3.5.1 | `UUmContentSubsystem`, `UUmHeroDefinition : UPrimaryDataAsset` через `AssetManager` (`PrimaryAssetTypesToScan`); сеты — папки `/Game/Heroes/<Set>/` + `UPrimaryAssetLabel` для чанков (core-механизм, не Beta); `DataRegistry` не используется (§4.5) |
| G5 | Хуки раскладки desktop/mobile через `UCommonVisibilitySwitcher` + bottom-sheet инспектор — сразу в `WBP_GameHUD` | К3 §3.7.2 | §4.6 (`WBP_GameHUD`, слоты `Desktop`/`Mobile`); `UCommonVisibilitySwitcher` подтверждён: `$UE/Plugins/Runtime/CommonUI/Source/CommonUI/Public/CommonVisibilitySwitcher.h:15` |
| G6 | `UmMockBackend`: in-process фейковые транспорт и сокет + фикстуры для SlateInspector/функциональных прогонов без бэкенда | К3 §6.3 | `UmNet` (`FUmFakeHttpTransport`, `FUmFakeWebSocket`), `UmClient/Dev/UmMockBackend` (§4.8) |
| G7 | Таблица «задача → тулсет MCP» целиком (включая `ConfigSettingsToolset`, `GameplayTagsToolset`, `LogsToolset`) | К3 §5.2 | §5.8 |
| G8 | Класс ошибки `Opaque` (prod-маскирование): `INTERNAL_SERVER_ERROR` + `Internal server error` + `Auth==Required` + `exp` access-JWT в пределах ±2 мин → один раз трактовать как `AuthExpired` | К3 §3.2.3 | `FUmErrorClassifier` (§5.3) |
| G9 | `PresentedState` (последний проигранный снапшот) ≠ `Current` (последний применённый); HUD биндится на `PresentedState` | К3 §3.10 | `UUmPresentationSubsystem::PresentedState`, `UUmGameHudModel` (§4.7) |
| G10 | Разведение авто-резолва: атакующий → `resolveCombat` через 1,5 с после `COMBAT_RESOLVE`; защитник получает кнопку через 5 с; против бота человек не резолвит | К3 §4.4 | `UUmStateSubsystem` таймеры (§5.5) |
| G11 | Spec `Unmatched.Model.DtoRoundTrip` — закрывает вопрос регистра ключей JSON ↔ `UPROPERTY` тестом, а не конвенцией | К3 §6.1 | §4.8; факт: `JsonAttributes.Find(GetAuthoredNameForField)` (`$UE/Source/Runtime/JsonUtilities/Private/JsonObjectConverter.cpp:1338-1339`), хеш `FString` регистронезависим (`$UE/Source/Runtime/Core/Public/Containers/UnrealString.h.inl:2128-2132`) |
| G12 | Флаг `bDecksStale`: пометка протухания `decks/discardPiles` + рефетч + визуализация «stale» в `WBP_DeckDiscard` | К2 §3.4.4 | `FUmGameSnapshotStore` (§5.2), `UUmGameHudModel::bDecksStale` |
| G13 | Таблица паритета и намеренных отличий + пунктирная подсветка `bServerWouldAllow` | К2 §3.5.3 | §5.7; `FUmLegalSet::ServerWouldAllow` |
| G14 | Паритет-фикстуры `{stateBefore, action, response\|error, stateAfter}` — **узко**: только для `FUmBoardGeometry`, `FUmRules` (banner, boost, range) и гейтов `FUmLegalActions` | К2 §3.5.5 | `unreal/Tools/export-rules-fixtures.mjs`, spec `Unmatched.Model.RulesParity` (§4.8) |
| G15 | Две разные функции слага: `HeroSlug(name)` и `AssetSlug(title)` | К2 §3.5.2 | `FUmSlug` (§4.3); источники `backend/src/game-engine/models/fighter.model.ts:80-85` и `scripts/sync-card-assets.mjs:23-31` |
| G16 | Единая точка `FUmLegalActions::Enumerate(...) → FUmLegalSet` с `WhyNot: TArray<FUmRejection>` для тултипов | К2 §3.5.2 | `UmModel` (§4.3), `UUmGameHudModel::WhyNot` |
| G17 | Абстракции `IUmHttpTransport` и `IUmWebSocket` с фейками для спеков auth/refresh/single-flight/лимитера | К2 §3.3.1-3.3.2 | `UmNet` (§4.1) |
| G18 | Реестр серверных предпосылок «что нужно → обход до фикса» как рабочий артефакт | К2 §7.4 | §6 |
| G19 | Запрет предлагать `resolvePendingEffect` при `phase == COMBAT` | К2 §4.5 | `FUmLegalActions` гейт `Pending.*` (§5.5) |
| G20 | `ServerPortNumber=8124` + второй профиль `mcpServers` в `~/.claude.json` | К2 §5.2 | §3.5 |
| G21 | `FUmCombatPreview` — read-only оценка «Атака N · Защита ?» без предикции | К2 §3.5.4 (только превью) | `UmModel`, v1 (§4.3); в MVP — `combatInfo.attackValue` из состояния |
| G22 | `{ "Name": "LiveCodingToolset", "Enabled": true, "TargetAllowList": ["Editor"] }` в `.uproject` | все судьи; `00-mcp-verification.md:58` | §3.1; факт: `$UE/Plugins/Experimental/Toolsets/LiveCodingToolset/LiveCodingToolset.uplugin` — `EnabledByDefault: false`, `EditorOnly: true`, `IsExperimentalVersion: true` |
| G23 | Приоритет источника при равном `sequenceNumber`: Query/Mutation перезаписывает уже применённый Subscription-снапшот того же seq | судья 2 (новое) | `FUmGameSnapshotStore::Apply` (§5.2) |

### 2.4. Фатальные ошибки кандидатов и как они исправлены в решении

| # | Ошибка (кандидат, место) | Проверка | Как исправлено |
|---|---|---|---|
| F1 | К3 `candidate-3.md:105`: ini-ключ `GameViewportClientClass` | Свойство называется `GameViewportClientClassName` (`$UE/Source/Runtime/Engine/Classes/Engine/Engine.h:807`; `$UE/Config/BaseEngine.ini:132`) | `DefaultEngine.ini` §3.5: `[/Script/Engine.Engine] GameViewportClientClassName=/Script/UmClient.UmGameViewportClient` |
| F2 | К3 `candidate-3.md:106`: `GameInstanceClass` в секции `[/Script/Engine.Engine]` | Принадлежит `UGameMapsSettings` (`$UE/Source/Runtime/EngineSettings/Classes/GameMapsSettings.h:203`; `BaseEngine.ini:12-13`) | §3.5: `[/Script/EngineSettings.GameMapsSettings] GameInstanceClass=/Script/UmClient.UmGameInstance` |
| F3 | К3 §3.9/§3.10: cue-теги `Cue.Match.*` вне корня `GameplayCue`; вызов `UGameplayCueManager::Get()` (не существует); `GameplayCueNotifyPaths` списком через запятую с glob | `UGameplayCueSet::BaseGameplayCueTag()` = тег `GameplayCue` (`$UE/Plugins/Runtime/GameplayAbilities/Source/GameplayAbilities/Private/GameplayCueSet.cpp:17,457-460`; выборка детей `:270,414`); аксессор — `UAbilitySystemGlobals::Get().GetGameplayCueManager()` (`Public/AbilitySystemGlobals.h:113`); `GameplayCueNotifyPaths` — `TArray<FString>` (`:361`) | GAS **не используется**. Собственная шина `UUmMatchCueSubsystem` + `DA_UmCueRegistry` (тег → `TSubclassOf<UUmCueNotify>`). Корень тегов cue — `GameplayCue.Match.*`, чтобы миграция на GAS (если понадобится) не требовала переименования (§5.6) |
| F4 | К3 §3.4.3: DTO с полями-`UENUM` через `FJsonObjectConverter` — одно неизвестное wire-значение роняет разбор всей структуры | `Enum->GetValueByName(...) == INDEX_NONE → return false` (`JsonObjectConverter.cpp:601-609`), вызывающий `JsonAttributesToUStructWithContainer` возвращает `false` для всей структуры (`:1360-1367`), независимо от `bStrictMode` | Все wire-enum в DTO и состоянии — `FString`; конверсия в `EUm*` толерантными функциями `UmEnums::Parse*` (неизвестное → `Unknown`, в `FUmParseReport`) (§5.2) |
| F5 | К3 §3.6.1 / R-9: нет триггера рефетча `decks/discardPiles` у защитника — `WC_CombatPanel` не найдёт карту атаки в сбросе | Подписка не несёт `decks`/`discardPiles` (`game-subscription.resolver.ts:53-63`) | Триггер К1 (изменение размеров руки/сброса или фазы) + явный флаг `bDecksStale` К2 + `RefreshFullStateDebounced(300 мс)` (§5.2) |
| F6 | К3 §3.2.3: `BAD_USER_INPUT` → `ClientBug` с тостом «Ошибка клиента» | В production allow-list `formatError` пропускает бизнес-ошибки ровно по `BAD_USER_INPUT`/`GRAPHQL_VALIDATION_FAILED` (`backend/src/graphql/graphql.module.ts:73-77`); реальный код `BadRequestException` под Apollo не подтверждён (R3 §4.9) | `BAD_REQUEST`, `BAD_USER_INPUT`, `GRAPHQL_VALIDATION_FAILED`, `GRAPHQL_PARSE_FAILED` → единый класс `Validation`; для gameplay — «ход отклонён» с `Message` (§5.3) |
| F7 | К3 §2.2: `Directories=((Path="/Game/Content/Heroes"))` | `/Game` уже соответствует `Content/` | `Directories=((Path="/Game/Heroes"))` (§3.5) |
| F8 | К3 §1.2/§2.1: `GameFeatures`, `ModularGameplay`, `DataRegistry` (все `IsBetaVersion: true`, R8 §2.13) и 25 плагинов `GF_HeroPack_<Set>` | Противоречит R8 §3.8 п.2 | Отвергнуто; контент — `UPrimaryDataAsset` + `AssetManager`, сеты — папки и `UPrimaryAssetLabel` (§4.5, §7) |
| F9 | К2 `candidate-2.md:171,152`: `PingPongInterval=0` + прикладной ping 25 с | Сервер требует pong-**фрейм** (факт §1.3 п.1); LWS-ping — единственный рычаг движка (`$UE/Source/Runtime/Online/WebSockets/Private/Lws/LwsWebSocketsManager.cpp:192-194`) | `[WebSockets.LibWebSockets] PingPongInterval=10`; прикладной `ping` каждые 10 с как liveness; живая проверка авто-pong — спайк E0.2 (§3.5, §9.1) |
| F10 | К2 §3.5.2/§3.6/§7.2: UI «BLIND BOOST» под несуществующую мутацию | 11 gameplay-мутаций без blind boost (R3 §2.7); ручной хендлер Daredevil в потоке не вызывается (R4 §2.7.2) | Нет такого UI; blind boost — серверный эффект `BOOST/SELF_DECK_TOP`, показывается через диф сброса/колоды |
| F11 | К2 §3.4.2: «в UE нет способа сопоставить camelCase-ключ с PascalCase-`UPROPERTY`» → ручной `FromJson` для ~35 DTO; К1 `candidate-1.md:233`: camelCase-конвенция `UPROPERTY` | Сопоставление по `TMap<FString,…>::Find(GetAuthoredNameForField)` (`JsonObjectConverter.cpp:1338-1339`) с регистронезависимым хешем `FString` (`UnrealString.h.inl:2128-2132`) | Идиоматичный PascalCase `UPROPERTY` + `FJsonObjectConverter` для GraphQL-DTO; подтверждение — spec `Unmatched.Model.DtoRoundTrip` в E0.1 (G11) |
| F12 | К2 §3.5.4: предикция `endTurn`/`advanceTurn` невозможна для MVP-пары (turn-start урон Medusa внутри `advanceTurn`) | R4 §2.4 шаг 8, §2.11.2 | Предикции нет вообще (§7) |
| F13 | К2 §3.4.4 vs §3.5.4: противоречие инварианта дедупликации (предсказанный seq в журнале отбрасывает авторитетный) | — | Предикции нет; дедупликация — §5.2 с приоритетом источника (G23) |
| F14 | К2 §3.5.2 vs §5.1: `FUnmAbilityRow` одновременно plain-структура без `CoreUObject` и строка DataTable | Строка DataTable обязана быть `USTRUCT : FTableRowBase` | В `UmModel` разрешён `CoreUObject`; `FUmAttackRangeRow : FTableRowBase` — один тип (§4.3) |
| F15 | К2 §7.4 B9: паритет-фикстуры требуют скрипт в `backend/scripts/` и CI бэкенда | Не в оценке, вне контроля клиента | Экспортёр живёт в `unreal/Tools/` и работает через публичное API; таблица дальностей экспортируется скриптом `unreal/Tools/export-ability-table.ts`, читающим `backend/src/game-engine/abilities/ability-config.ts` как модуль монорепозитория (без правок бэкенда) (§4.8) |
| F16 | К2 §3.8.3: бюджет «360 карт × 2 разрешения ≈ 200–250 МБ» | R9 §3 п.10 — 180 МБ для **одного** разрешения 512×716 | Бюджет считается по R9: MVP — только 512×716 (≈0,5 МБ BC7/карта); 1024×1432 — только для инспектора и только по мере необходимости (§4.5) |
| F17 | К1 `candidate-1.md:549`: `WBP_RootLayout` создаётся в `UUmUISubsystem::Initialize` (`ULocalPlayerSubsystem`) — до `APlayerController` и viewport | Известная ловушка порядка инициализации | `UUmUISubsystem::EnsureRootLayout(APlayerController*)` вызывается из `AUmPlayerController::BeginPlay()`; идемпотентно; один персистентный `L_Main` — layout создаётся один раз (§4.6) |
| F18 | К1 §3.6.4/§4.5 и К3 §3.6.4: pending-резолв «в любой фазе», включая `COMBAT` | Факт §1.3 п.7 | Гейт `phase != COMBAT` для всех `Pending.*` (G19, §5.5) |
| F19 | К1 §3.8.4: `DT_AttackRange` — «вручную синхронизируемая таблица» без контроля | `attackRange` через GraphQL не экспортируется (R4 §3.6); `ability-config.ts` меняется почти каждым коммитом движка (`git log`: 10 из 12 последних коммитов правят `game-engine`) | `unreal/Tools/export-ability-table.ts` → `Import/ability-table.json` + `DT_AttackRange.csv`; spec `Unmatched.Model.AttackRangeSync` падает при расхождении таблицы и снимка (§4.8) |
| F20 | К1 §7.1: 43 ч/д при E7 = 7 ч/д на 15+ виджетов; «два параллельных агента на UI» против сериализации MCP на game thread | К3 — 62 ч/д, К2 — 66 ч/д за тот же объём | Оценка §9.2: 52 ч/д MVP + 5 ч/д фазы 0, коридор 50–65; пересмотр после фазы 0 |
| F21 | К1 §2.6: конвенция camelCase-`UPROPERTY` | см. F11 | Снята (PascalCase) |
| F22 | К1 §2.5 и К3 §2.2: порт MCP 8123 — занят хост-проектом `MCPProject` | `00-mcp-verification.md:12`; `C:/Users/ren/Documents/Unreal Projects/MCPProject/Config/DefaultEditorPerProjectUserSettings.ini` (`ServerPortNumber=8123`) | `ServerPortNumber=8124` + профиль `unreal-mcp-unmatched` в `~/.claude.json` (G20, §3.5) |
| F23 | Все три: `LiveCodingToolset` не включён в `.uproject` | G22 | Включён (§3.1) |
| F24 | К1/К2/К3: `gameStateUpdated.currentTurnPlayerId: String!` (non-null) — при `null` в состоянии подписчик получит ошибку вместо события | `backend/src/games/dto/gameplay.dto.ts:474-475`; R2 §4.18 | Обработка `next{errors}` на живой подписке: лог + `RefetchState()` + продолжение; при `complete` — переподписка. Предпосылка B7 (§6) |

---

## 3. Целевая структура проекта

### 3.1. Расположение и `.uproject`

Проект живёт в монорепозитории: `C:/Users/ren/WebstormProjects/unmached/unmached/unreal/Unmatched/Unmatched.uproject` (каталог `unreal/` создаётся; сейчас его нет — проверено). Свой `.uproject` обязателен: MCP-сервер привязан к одному открытому проекту (`00-mcp-verification.md:60`).

```json
{
  "FileVersion": 3,
  "EngineAssociation": "5.8",
  "Category": "Game",
  "Description": "Unmatched digital client (server-authoritative GraphQL client)",
  "Modules": [
    { "Name": "UmNet",    "Type": "Runtime", "LoadingPhase": "PreDefault" },
    { "Name": "UmModel",  "Type": "Runtime", "LoadingPhase": "PreDefault" },
    { "Name": "UmClient", "Type": "Runtime", "LoadingPhase": "Default",
      "AdditionalDependencies": ["Engine", "CoreUObject", "UMG", "CommonUI", "UmNet", "UmModel"] },
    { "Name": "UmEditor", "Type": "Editor",  "LoadingPhase": "PostEngineInit" }
  ],
  "Plugins": [
    { "Name": "CommonUI",               "Enabled": true },
    { "Name": "EnhancedInput",          "Enabled": true },
    { "Name": "PlatformCrypto",         "Enabled": true },
    { "Name": "ModelContextProtocol",   "Enabled": true, "TargetAllowList": ["Editor"] },
    { "Name": "AllToolsets",            "Enabled": true, "TargetAllowList": ["Editor"] },
    { "Name": "LiveCodingToolset",      "Enabled": true, "TargetAllowList": ["Editor"] },
    { "Name": "FunctionalTestingEditor","Enabled": true, "TargetAllowList": ["Editor"] },
    { "Name": "Paper2D",                "Enabled": false },
    { "Name": "ModelViewViewModel",     "Enabled": false },
    { "Name": "GameFeatures",           "Enabled": false },
    { "Name": "DataRegistry",           "Enabled": false },
    { "Name": "GameplayAbilities",      "Enabled": false }
  ]
}
```

Таргеты: `Source/Unmatched.Target.cs` (Game, `ExtraModuleNames = { "UmNet", "UmModel", "UmClient" }`) и `Source/UnmatchedEditor.Target.cs` (Editor, + `"UmEditor"`). Команда сборки: `"C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\Build.bat" UnmatchedEditor Win64 Development -Project="<…>\unreal\Unmatched\Unmatched.uproject" -WaitMutex` (R8 §2.14). `UmClient` — primary game module (`IMPLEMENT_PRIMARY_GAME_MODULE`).

Обоснование плагинов: CommonUI — не beta, стек экранов и input routing (R8 §2.6); EnhancedInput — по умолчанию (R8 §2.7); PlatformCrypto — AES-256-GCM для refresh-токена (R8 §2.10); MCP + AllToolsets + LiveCodingToolset — агентный dev-loop, только Editor (`00-mcp-verification.md:5,58,60`); Paper2D не нужен — доска 3D + UMG (R8 §2.8); MVVM/GameFeatures/DataRegistry — Beta (R8 §2.13); GameplayAbilities — не beta, но не нужен (cue-шина своя, F3).

### 3.2. Модули

| Модуль | Тип | Содержимое | `PublicDependencyModuleNames` | Правило |
|---|---|---|---|---|
| `UmNet` | Runtime | GraphQL HTTP-клиент, `graphql-transport-ws` state machine, классификатор ошибок, retry/rate-limiter, auth (JWT, refresh, secure store), абстракции транспорта + фейки, `UUmNetSettings` | `Core, CoreUObject, Engine, HTTP, WebSockets, Json, JsonUtilities, PlatformCrypto, DeveloperSettings` (+ `PlatformCryptoOpenSSL` в Private) | Ничего игрового: не знает ни `GameState`, ни экранов. Тестируется без сети через фейки |
| `UmModel` | Runtime | UENUM + толерантные парсеры, все USTRUCT DTO, wire-модель `GameState`, парсер и диф, документы операций (`UmOps.gen.h`) и билдеры входных DTO, геометрия доски, правила-подсказки, `FUmLegalActions`, слаги, нативные GameplayTags | `Core, CoreUObject, Engine, Json, JsonUtilities, GameplayTags` | Не зависит от `UmNet`. Никаких субсистем, акторов, виджетов. Всё покрывается spec-тестами на фикстурах |
| `UmClient` | Runtime (primary) | Субсистемы (`State`, `Content`, `ImageCache`, `UI`, `Presentation`, `MatchCue`), game framework (`GameInstance`, `GameMode`, `PlayerController`, `ViewportClient`), HUD-модель, C++-базы виджетов, акторы доски, cue-шина, dev-инструменты (`UmMockBackend`, консоль), `UUmClientSettings` | `Core, CoreUObject, Engine, InputCore, EnhancedInput, UMG, Slate, SlateCore, CommonUI, CommonInput, GameplayTags, FieldNotification, ImageWrapper, DeveloperSettings, UmNet, UmModel` | Blueprint видит только `BlueprintCallable`/`BlueprintReadOnly` API `UmClient`; сеть и парсинг из Blueprint недоступны |
| `UmEditor` | Editor | Коммандлет импорта контента (`Import/` → `DA_*`/`DT_*`/`T_*`), редакторские валидаторы | `UnrealEd, AssetTools, EditorSubsystem, UmModel, UmClient` | Только редактор; в cooked-сборку не попадает |

Тесты: `Private/Tests/*.spec.cpp` в каждом модуле под `WITH_DEV_AUTOMATION_TESTS`; имена `Unmatched.<Area>.<Suite>` (§4.8).

### 3.3. Дерево `Source/`

```
unreal/Unmatched/Source/
  Unmatched.Target.cs
  UnmatchedEditor.Target.cs
  UmNet/
    UmNet.Build.cs
    Public/
      UmNetSettings.h                 # UDeveloperSettings: ApiBaseUrl, GraphQLPath, таймауты, WS-параметры
      UmGraphQLTypes.h                # FUmGraphQLRequest / FUmGraphQLError / FUmGraphQLResult / EUmErrorClass / EUmAuthMode
      UmErrorClassifier.h             # FUmErrorClassifier
      UmRateLimiter.h                 # FUmRateLimiter (token bucket по операции)
      UmRetryPolicy.h                 # FUmRetryPolicy
      Transport/IUmHttpTransport.h    # интерфейс + FUmHttpTransport (IHttpRequest) + FUmFakeHttpTransport
      Transport/IUmWebSocket.h        # интерфейс + FUmLwsWebSocket (IWebSocket) + FUmFakeWebSocket
      UmGraphQLWsClient.h             # FUmGraphQLWsClient — state machine graphql-transport-ws
      UmNetSubsystem.h                # UUmNetSubsystem : UGameInstanceSubsystem
      Auth/UmJwt.h                    # FUmJwt::DecodeExp (base64url, без проверки подписи)
      Auth/IUmSecureStore.h           # интерфейс; FUmSecureStore_Windows (DPAPI), FUmSecureStore_Generic (AES-256-GCM)
      Auth/UmAuthSubsystem.h          # UUmAuthSubsystem : UGameInstanceSubsystem, IUmAuthProvider
    Private/ … , Private/Tests/{UmWsStateMachine,UmErrorClassifier,UmRateLimiter,UmAuth}.spec.cpp
  UmModel/
    UmModel.Build.cs
    Public/
      UmEnums.h                       # EUm* + namespace UmEnums { Parse*/ToString }
      UmApiDtos.h                     # FUm*Dto (GraphQL-ответы), FUmDateTime
      UmGameState.h                   # wire-модель состояния (FUmGameState и вложенные)
      UmGameStateParser.h             # FUmGameStateParser, FUmParseReport
      UmSnapshotDiff.h                # FUmSnapshotDiff, FUmMatchEvent
      UmOps.gen.h                     # СГЕНЕРИРОВАННЫЕ документы операций (не править руками)
      UmOps.h                         # FUmOpsRegistry: имя → документ, EUmAuthMode, bucket, bIsMutation
      UmInputs.h                      # FUmInputs: билдеры входных DTO → TSharedPtr<FJsonObject>
      UmBoardGeometry.h               # FUmBoardGeometry
      UmRules.h                       # FUmRules: BannerAllows, BoostAllowed, IsInAttackRange, FighterFitsPending
      UmLegalActions.h                # FUmLegalActions, FUmLegalSet, FUmRejection
      UmCombatPreview.h               # FUmCombatPreview (v1)
      UmSlug.h                        # FUmSlug::HeroSlug / AssetSlug
      UmTags.h                        # нативные GameplayTags (UE_DECLARE_GAMEPLAY_TAG_EXTERN)
      UmTagMaps.h                     # FUmTagMaps: EUm* ↔ FGameplayTag
      UmTableRows.h                   # FUmAttackRangeRow, FUmCardArtRow, FUmHeroArtRow, FUmBoardArtRow, FUmServerErrorRow, FUmHeroCombatModRow
    Private/ … , Private/Tests/{UmDtoRoundTrip,UmOpsGenerated,UmInputsWhitelist,UmStateParser,UmSnapshotDiff,UmGeometry,UmLegalActions,UmBanner,UmSlug,UmRulesParity,UmAttackRangeSync}.spec.cpp
  UmClient/
    UmClient.Build.cs
    Public/
      UmClientSettings.h              # UDeveloperSettings: AssetBaseUrl, DefaultBoardName, DefenseTimeoutSec, AutoResolve*, feature-flags
      Core/UmGameInstance.h           # UUmGameInstance
      Core/UmGameMode.h               # AUmGameMode
      Core/UmPlayerController.h       # AUmPlayerController (EnhancedInput, EnsureRootLayout)
      Core/UmGameViewportClient.h     # UUmGameViewportClient : UCommonGameViewportClient
      State/UmStateSubsystem.h        # UUmStateSubsystem : UGameInstanceSubsystem
      State/UmGameSnapshotStore.h     # FUmGameSnapshotStore
      State/UmServerClock.h           # FUmServerClock
      State/UmActionGate.h            # FUmActionGate
      Content/UmContentSubsystem.h    # UUmContentSubsystem (фасад Baked→Runtime→Placeholder, id-map, стойки)
      Content/UmContentCache.h        # FUmContentCache (Saved/UmContent/*.json)
      Content/UmImageCacheSubsystem.h # UUmImageCacheSubsystem (URL → диск → UTexture2D)
      Content/UmHeroDefinition.h      # UUmHeroDefinition : UPrimaryDataAsset ("UmHero")
      Content/UmBoardDefinition.h     # UUmBoardDefinition : UPrimaryDataAsset ("UmBoard")
      UI/UmUISubsystem.h              # UUmUISubsystem : ULocalPlayerSubsystem
      UI/UmRootLayout.h               # UUmRootLayout : UCommonUserWidget (4 стека, BindWidget)
      UI/UmActivatableScreen.h        # UUmActivatableScreen : UCommonActivatableWidget; UUmModalBase
      UI/UmGameHudBase.h              # UUmGameHudBase : UUmActivatableScreen
      UI/UmCardViewBase.h             # UUmCardViewBase : UCommonUserWidget
      UI/UmGameHudModel.h             # UUmGameHudModel : UObject, INotifyFieldValueChanged
      UI/UmHudLibrary.h               # UUmHudLibrary (BlueprintFunctionLibrary): IsAffordanceEnabled(FGameplayTagQuery), WhyNot(...)
      Presentation/UmPresentationSubsystem.h  # UUmPresentationSubsystem : UWorldSubsystem
      Presentation/UmInputStateMachine.h      # FUmInputStateMachine
      Presentation/UmGameStage.h              # AUmGameStage (ISM клеток, камера, трассировка)
      Presentation/UmFighterActor.h           # AUmFighterActor
      Presentation/UmMatchCueSubsystem.h      # UUmMatchCueSubsystem : UWorldSubsystem
      Presentation/UmCueRegistry.h            # UUmCueRegistry : UDataAsset; UUmCueNotify : UObject
      Dev/UmMockBackend.h             # UUmMockBackend (фейковые транспорт/сокет + сценарии из фикстур)
      Dev/UmDevConsole.h              # консольные команды um.*
    Private/ … , Private/Tests/{UmSnapshotStore,UmInputFsm,UmPlayback,UmMockBackend,UmE2E}.spec.cpp
  UmEditor/
    UmEditor.Build.cs
    Public/UmContentImportCommandlet.h
    Private/…
```

### 3.4. Дерево `Content/`

```
unreal/Unmatched/Content/
  Maps/            L_Main.umap (единственный игровой уровень), L_Test_Game.umap (functional tests)
  Core/            BP_UmGameMode, BP_UmPlayerController, BP_UmGameStage, BP_UmFighter
  UI/
    Root/          WBP_RootLayout (родитель UUmRootLayout)
    Auth/          WBP_Boot, WBP_Login, WBP_Register
    Lobby/         WBP_Lobby, WBP_GameListRow, WBP_CreateGameDialog, WBP_JoinByIdDialog
    Room/          WBP_Room, WBP_PlayerSlot, WBP_HeroPicker, WBP_HeroCard
    Game/          WBP_GameHUD (UCommonVisibilitySwitcher: Desktop/Mobile), WBP_PlayerPanel, WBP_TurnPhasePill,
                   WBP_HandTray, WBP_CardView, WBP_OpponentHand, WBP_DeckDiscard, WBP_CombatPanel, WBP_BoostPicker,
                   WBP_PendingEffectBanner, WBP_ChooseOneDialog, WBP_StanceBar, WBP_CardInspector, WBP_ActionLog,
                   WBP_ManeuverBar, WBP_GameOver, WBP_FighterPlate
    Common/        WBP_ConfirmDialog, WBP_Toast, WBP_ConnectionBadge, WBP_ReconnectOverlay, WBP_UmButton,
                   DA_UmButtonStyle_*, DA_UmTextStyle_*, DA_UmTheme
    Input/         DA_UmCommonInputData, IA_Select, IA_Cancel, IA_Confirm, IA_Zoom, IA_Pan, IMC_Board, IMC_Menu
  Board/           SM_Cell, M_Cell, MI_Cell_Zone_<Zone> ×12, M_Highlight, MI_Highlight_Move, MI_Highlight_Attack,
                   MI_Highlight_Pending, MI_Highlight_ServerWouldAllow (пунктир), MI_Highlight_Selected
  Cues/            DA_UmCueRegistry, CUE_Fighter_Move, CUE_Fighter_Damage, CUE_Fighter_Heal, CUE_Fighter_Defeated,
                   CUE_Combat_AttackDeclared, CUE_Combat_DefenseRevealed, CUE_Combat_Resolved, CUE_Combat_Timeout,
                   CUE_Card_Play, CUE_Card_Draw, CUE_Card_Discard, CUE_Turn_Changed, CUE_Stance_Changed, CUE_Game_Over
  Data/            DT_CardArt, DT_HeroArt, DT_BoardArt, DT_AttackRange, DT_HeroCombatMods (v1), DT_ServerErrorMap, ST_UI
  Heroes/<Set>/    DA_Hero_<heroSlug> (UUmHeroDefinition), PAL_<Set> (UPrimaryAssetLabel — чанк сета)
  Boards/          DA_Board_<boardSlug> (UUmBoardDefinition)
  Textures/
    Cards/<heroSlug>/T_Card_<heroSlug>_<cardSlug>_EN|RU
    Heroes/<heroSlug>/T_Hero_<heroSlug>_Avatar|Mini|Cover
    Boards/T_Board_<boardSlug>
    UI/T_UI_CardBack, T_UI_Placeholder_Card, T_UI_Placeholder_Hero, T_UI_Vignette
  Fonts/           F_Inter (OFL, кириллица)
```

Правила: (а) `L_Main` — единственный уровень для меню и партии; `UUmPresentationSubsystem` спавнит `AUmGameStage` при `EnterGame` и уничтожает при `ExitGame`; `OpenLevel` в игре не вызывается; (б) `Heroes/<Set>/` — папка на сет (25 сетов, R5 §2.10), `PAL_<Set>` назначает чанк — это core-механизм `AssetManager` (`$UE/Source/Runtime/Engine/Classes/Engine/PrimaryAssetLabel.h:12`), без Beta-плагинов; (в) именование текстур — R9 §2.13 п.6.

### 3.5. `Config/`

`DefaultEngine.ini`:

```ini
[/Script/EngineSettings.GameMapsSettings]
GameInstanceClass=/Script/UmClient.UmGameInstance                ; GameMapsSettings.h:203, BaseEngine.ini:12-13
GameDefaultMap=/Game/Maps/L_Main.L_Main
GlobalDefaultGameMode=/Game/Core/BP_UmGameMode.BP_UmGameMode_C

[/Script/Engine.Engine]
GameViewportClientClassName=/Script/UmClient.UmGameViewportClient  ; Engine.h:807, BaseEngine.ini:132; требование CommonUI (R8 §2.6)

[/Script/CommonInput.CommonInputSettings]
InputData=/Game/UI/Input/DA_UmCommonInputData.DA_UmCommonInputData_C
bEnableEnhancedInputSupport=False                                ; Experimental (R8 §2.7); CommonInputSettings.h:114

[WebSockets]
TextMessageMemoryLimit=8388608                                   ; дефолт 1 МБ (LwsWebSocketsManager.cpp:528-529; R8 §2.3)

[WebSockets.LibWebSockets]
PingPongInterval=10                                              ; страховка от terminate() сервера через ~24 с (LwsWebSocketsManager.cpp:192-194; R1 §2.4)

[HTTP]
HttpConnectionTimeout=15
HttpActivityTimeout=20                                           ; тотальный таймаут задаётся SetTimeout в коде (R8 §2.2)

[/Script/Engine.AssetManagerSettings]
+PrimaryAssetTypesToScan=(PrimaryAssetType="UmHero",AssetBaseClass=/Script/UmClient.UmHeroDefinition,bHasBlueprintClasses=False,bIsEditorOnly=False,Directories=((Path="/Game/Heroes")),SpecificAssets=,Rules=(Priority=-1,ChunkId=-1,bApplyRecursively=True,CookRule=Unknown))
+PrimaryAssetTypesToScan=(PrimaryAssetType="UmBoard",AssetBaseClass=/Script/UmClient.UmBoardDefinition,bHasBlueprintClasses=False,bIsEditorOnly=False,Directories=((Path="/Game/Boards")),SpecificAssets=,Rules=(Priority=-1,ChunkId=-1,bApplyRecursively=True,CookRule=Unknown))
; синтаксис — по образцу $UE/Config/BaseGame.ini:254-255; поля — AssetManagerTypes.h:137-178
```

`DefaultGame.ini`:

```ini
[/Script/UmNet.UmNetSettings]
ApiBaseUrl=http://localhost:3000
GraphQLPath=/graphql
HttpTimeoutSec=15
WsConnectionAckTimeoutSec=5
WsReconnectMaxAttempts=5
WsReconnectBaseDelayMs=1000
WsAppPingIntervalSec=10
ProactiveRefreshLeadSec=300

[/Script/UmClient.UmClientSettings]
AssetBaseUrl=http://localhost:5174                 ; корневые /assets/... раздаёт веб-фронт (R5 §2.12, R9 §3.1)
DefaultBoardName=Cobble City
DefenseTimeoutSec=30                               ; DEFAULT_DEFENSE_TIMEOUT (R4 §2.7.4)
AttackerAutoResolveDelaySec=1.5
DefenderResolveButtonDelaySec=5
RefreshFullStateDebounceMs=300
bMatchmakingEnabled=false                          ; R2 §4.1-4.3
bPresenceEnabled=false                             ; R2 §4.4
bVsAiEnabled=false                                 ; v1
bMockBackend=false                                 ; dev/test

[/Script/UnrealEd.ProjectPackagingSettings]
+CulturesToStage=en
+CulturesToStage=ru                                ; R8 §2.12
```

`DefaultEditorPerProjectUserSettings.ini` (порт **8124**, чтобы `MCPProject` и `Unmatched` могли быть открыты одновременно — G20):

```ini
[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]
ServerUrlPath=/mcp
ServerPortNumber=8124                              ; ModelContextProtocolSettings.h:38
bAutoStartServer=True
bEnableToolSearch=True
```

`~/.claude.json`: добавить `mcpServers.unreal-mcp-unmatched = { "type": "http", "url": "http://127.0.0.1:8124/mcp" }` рядом с существующим `unreal-mcp` (8123) — `00-mcp-verification.md:14`.

Нативные GameplayTags объявляются в C++ (`UmTags.h/.cpp`), `DefaultGameplayTags.ini` содержит только `ImportTagsFromConfig=False` и пустой список — источник тегов один.

### 3.6. Конвенции именования

| Сущность | Правило | Пример |
|---|---|---|
| C++ классы/структуры/enum/интерфейсы | `UUm*`, `AUm*`, `FUm*`, `EUm*`, `IUm*` | `UUmStateSubsystem`, `FUmGameState`, `EUmGamePhase`, `IUmWebSocket` |
| USTRUCT GraphQL-ответов | `FUm<Type>Dto` | `FUmGameMutationResultDto` |
| USTRUCT wire-состояния | `FUm<Name>` без суффикса | `FUmFighter`, `FUmCombatState` |
| `UPROPERTY` в DTO | **PascalCase** (`SequenceNumber`), сопоставление с camelCase-JSON — регистронезависимое (F11); wire-enum — `FString` | `FString Phase; double SequenceNumber;` |
| Строки DataTable | `FUm<Name>Row : FTableRowBase` | `FUmAttackRangeRow` |
| Widget Blueprint / C++-база | `WBP_<Name>` / `UUm<Name>Base` | `WBP_GameHUD` / `UUmGameHudBase` |
| Акторы/BP | `AUm*` / `BP_Um*` | `AUmGameStage` / `BP_UmGameStage` |
| Данные/ассеты | `DT_`, `DA_`, `PAL_`, `ST_`, `M_`/`MI_`, `SM_`, `T_`, `F_`, `L_`, `IA_`, `IMC_`, `CUE_` | `DT_CardArt`, `DA_Hero_medusa`, `PAL_Marvel`, `CUE_Fighter_Damage` |
| GraphQL-операции | PascalCase имени поля; файлы `unreal/Ops/<Name>.graphql` | `GetGameState`, `Maneuver`, `GameStateUpdated` |
| Тесты | `Unmatched.<Net\|Model\|Client\|E2E>.<Suite>` | `Unmatched.Model.StateParser` |
| Логи | `LogUmNet`, `LogUmAuth`, `LogUmModel`, `LogUmSync`, `LogUmContent`, `LogUmUI`, `LogUmPresent` | |
| Слаг героя (`Fighter.heroSlug`, `heroStances`, `DT_AttackRange`, `DA_Hero_*`) | `FUmSlug::HeroSlug`: lowercase, `[^a-z0-9]+ → -`, trim `-` | `fighter.model.ts:80-85`: «King Arthur» → `king-arthur` |
| Слаг ассета карты (`DT_CardArt`, `T_Card_*`) | `FUmSlug::AssetSlug`: NFKD, без диакритики и апострофов `'`/`’`, lowercase, `[^a-z0-9]+ → -`, trim | `scripts/sync-card-assets.mjs:23-31`: «Queen Anne's Revenge» → `queen-annes-revenge` |
| GameplayTags | `Domain.Sub.Value`; cue — под корнем `GameplayCue.` | `Match.Phase.Combat`, `GameplayCue.Match.Fighter.Damage` |

### 3.7. Git, ассеты, инструменты

- `unreal/.gitignore`: `Binaries/`, `Intermediate/`, `Saved/`, `DerivedDataCache/`, `*.sln`, `.vs/`, `Import/`.
- `unreal/.gitattributes`: `*.uasset`, `*.umap` — Git LFS (исходные `public/assets` в git не отслеживаются и весят 229 МБ — R9 §1 п.1-2; решение о хранилище — открытый вопрос §8 п.5).
- `unreal/Ops/*.graphql` — единственный источник документов операций; `unreal/Schema/schema.introspection.json` — снимок introspection живого сервера.
- `unreal/Tools/` (Node, `package.json` с зависимостями `graphql`, `sharp`, `tsx`):
  - `snapshot-introspection.mjs` — introspection с `http://localhost:3000/graphql` → `Schema/schema.introspection.json`;
  - `ops-check.mjs` — `validate(schema, parse(doc))` для каждого `Ops/*.graphql` + генерация `Source/UmModel/Public/UmOps.gen.h` с SHA-256 набора документов;
  - `export-content.mjs` — `contentSummary` → `heroesPaginated` (без `cards`) → `hero(id)` по одному → `boards` → скачивание `imageUrl/imageUrlRu/urls.*` (Supabase и `/assets/…`) → `sharp` WebP/AVIF → PNG 512×716 (карты), 512×512 cover-crop (аватары), 512×704 (mini), ≤2048 (борды) → `Import/<set>/{heroes,cards,boards}.json` + PNG;
  - `export-ability-table.ts` (запуск `npx tsx`) — импортирует `ABILITY_CONFIGS` из `../../backend/src/game-engine/abilities/ability-config.ts` и константу Ms. Marvel (`ms-marvel.handler.ts:22`) → `Import/ability-table.json` + `Import/DT_AttackRange.csv` + `Import/DT_HeroStances.csv`;
  - `export-rules-fixtures.mjs` — поднимает партию через публичное API по сценарию Game Tester (R6 §2.6) и сохраняет `{stateBefore, action, response|error, stateAfter}` в `unreal/Unmatched/Tests/Fixtures/rules/<pair>/<n>.json`; пары MVP: `medusa-vs-king-arthur`, `bullseye-vs-t-rex` (дальности), `robin-hood-vs-leonardo` (pending), `alice-vs-muhammad-ali` (стойки);
  - `snapshot-fixtures.mjs` — снимки `gameState` под обоими токенами и payload подписки → `Tests/Fixtures/state/*.json`.
- Коммиты: явные пути, `--no-verify` (pre-commit hook сломан — память проекта).

---

## 4. Карта слоёв и ключевых классов

### 4.0. Направление зависимостей

```
Blueprint/UMG (WBP_*, BP_*)  ──►  UmClient  ──►  UmNet
                                      │
                                      └────►  UmModel  (GameplayTags)
UmEditor ──► UmClient, UmModel
```

Правило: `UmNet` и `UmModel` не знают друг о друге; `UmClient` — единственное место, где транспорт встречается с моделью (`UUmStateSubsystem`). Blueprint видит только `UUmStateSubsystem` (BlueprintCallable-действия), `UUmGameHudModel`, `UUmUISubsystem`, `UUmPresentationSubsystem`, `UUmHudLibrary`.

### 4.1. Сеть (`UmNet`)

| Класс | Ответственность | Зависимости | Источник поведения |
|---|---|---|---|
| `UUmNetSettings : UDeveloperSettings` | `ApiBaseUrl`, `GraphQLPath`, таймауты, WS-параметры, `ProactiveRefreshLeadSec` | `DeveloperSettings` | R1 §3 п.2 |
| `FUmGraphQLRequest` | `OperationName`, `Document`, `Variables: TSharedPtr<FJsonObject>`, `EUmAuthMode Auth {Required, Optional, None}`, `bIsMutation`, `TimeoutSec = 15`, `RateLimitBucket: FName` | `Json` | К1 §3.3.1, К3 §3.2.1 |
| `FUmGraphQLError` | `Message`, `Code` (из `extensions.code` **или** верхнеуровневого `code`), `Status` (`extensions.status`), `OriginalStatusCode`, `OriginalMessages[]`, `Path[]`, `Class: EUmErrorClass` | — | R1 §2.10, §3 п.24 |
| `FUmGraphQLResult` | `bTransportOk`, `HttpCode`, `Data` (может быть `null` при non-null корневом поле), `Errors[]`, `Class()` | — | R1 §2.3 |
| `EUmErrorClass` | `Network, Auth, Validation, Conflict, Concurrent, NotFound, Forbidden, RateLimited, Opaque, Unknown` | — | §5.3 |
| `IUmHttpTransport` / `FUmHttpTransport` / `FUmFakeHttpTransport` | POST JSON через `FHttpModule` (`SetVerb`, `SetURL`, `SetHeader`, `SetTimeout`, `OnProcessRequestComplete` на game thread); фейк — скриптованные ответы | `HTTP` | R8 §2.2, §3.1 п.2 |
| `IUmWebSocket` / `FUmLwsWebSocket` / `FUmFakeWebSocket` | Обёртка `IWebSocket` (создание только на game thread; `OnMessage` биндится **до** `Connect()`; объект переиспользуется после закрытия) | `WebSockets` | R8 §2.3 (`WebSocketsModule.cpp:77-86`, `LwsWebSocket.h:327-341`, `LwsWebSocket.cpp:625-648`) |
| `FUmGraphQLWsClient` | State machine `Idle → Connecting → AwaitingAck → Ready → Backoff/Failed/Closing`; `connection_init` немедленно в `OnConnected`; `subscribe/next/error/complete` по `id`; `ping → pong`; прикладной `ping` каждые 10 с; backoff `1 с × 2^(n−1)`, 5 попыток; переподписка с актуальными переменными (`since`) после `connection_ack`; `Reconnect(bForce)` после refresh; close-коды: 4406 — конфигурация (без ретрая), 4400/4401/4409/4429 — баг клиента (лог Error, 1 реконнект), 4408/4500/1001/1006 — backoff | `IUmWebSocket` | R1 §2.4, §3 п.7-12; К1 §3.3.4 |
| `FUmErrorClassifier` | Таблица §5.3 (включая `Opaque`) | — | R1 §2.10; К3 §3.2.3 |
| `FUmRateLimiter` | Token bucket по объявленным `@Throttle` (login 10/мин, register 5, refreshTokens 3, createGame 10, joinGame 15, startGame/abortGame 5, toggleReady 20, selectHero 10, attack/playDefense/playScheme/resolveCombat/pass 20, maneuver/moveFighter/endTurn/toggleDoor/setStance/resolvePendingEffect 30) | — | R1 §2.11; R3 §2.1 |
| `FUmRetryPolicy` | Только для `bIsMutation == false` при `Network`: 3 попытки, 300 мс → 10 с, jitter; мутации никогда; исключение — `createGame` с тем же `idempotencyKey` 1 повтор | — | R7 §2.2, §3 п.7; R1 §2.12 |
| `UUmNetSubsystem : UGameInstanceSubsystem` | `Execute(FUmGraphQLRequest, FUmOnResult)`, `Subscribe(...) → FUmSubscriptionHandle`, `Unsubscribe`, `ReconnectWebSocket(Reason)`, `GetNetState()` (тег `Net.State.*`), `OnNetStateChanged`; при классе `Auth` — вызывает `IUmAuthProvider::RefreshTokens()` (single-flight) и повторяет запрос один раз | `IUmHttpTransport`, `FUmGraphQLWsClient`, `IUmAuthProvider` | К1 §3.2 |
| `FUmJwt` | `DecodeExp(AccessToken) → FDateTime` (base64url payload `exp`, без проверки подписи) | — | R1 §3 п.14 |
| `IUmSecureStore` / `FUmSecureStore_Windows` / `FUmSecureStore_Generic` | Хранение refresh-токена + `UserId` + `Email`: Windows — DPAPI `CryptProtectData` (`#if PLATFORM_WINDOWS`); прочие — `PlatformCrypto Encrypt_AES_256_GCM` с ключом от `FPlatformMisc::GetDeviceId()` + соль (честно: обфускация) | `PlatformCrypto` | R8 §2.10, §3.5 |
| `UUmAuthSubsystem : UGameInstanceSubsystem, IUmAuthProvider` | `Login/Register/Logout/RestoreSession`, `RefreshTokens()` single-flight (`TSharedPtr<TPromise<bool>>`), проактивный refresh (`FTSTicker` раз в 15 с: `AccessExp − Now < 300 с`), очередь ожидающих операций, `GetAccessToken()`, `GetUser()` (`me.id` — единственный источник userId), `OnAuthStateChanged {LoggedOut, Refreshing, LoggedIn, SessionLost(reason)}`; после успешного refresh — `UUmNetSubsystem::ReconnectWebSocket("token-refreshed")`; `logout` на сервер — только при валидном access; локальная очистка всегда | `UUmNetSubsystem`, `IUmSecureStore`, `FUmJwt` | R1 §2.6, §3 п.13-17, §4.9; R7 §3 п.6 |

### 4.2. Модель контракта (`UmModel`) — данные

| Класс | Ответственность | Источник |
|---|---|---|
| `UmEnums.h` | `EUmGamePhase` (8 + `Unknown`), `EUmGameStatus`, `EUmGameMode`, `EUmGameEventType` (22 + `Unknown`), `EUmUserRole`, `EUmPresenceStatus`, `EUmFighterType` (`HERO/MINION/HUGE`), `EUmAttackType` (`melee/ranged`), `EUmCardType` (engine: 6), `EUmContentCardType` (4), `EUmPendingEffectType`, `EUmCellType`, `EUmZone` (12), `EUmBoostSource`, `EUmEffectType` (21 + `Unknown`), `EUmEffectTiming` (8 + `Unknown`); `UmEnums::Parse<E>(FStringView) → E` (неизвестное → `Unknown`), `ToWire(E) → FString` | R3 §2.3.1-2.3.2; К1 §3.4.2 |
| `UmApiDtos.h` | Все GraphQL-обёртки из К1 §3.4.3 с PascalCase-полями и `FString` для wire-enum: `FUmAuthUserDto`, `FUmAuthResponseDto`, `FUmMeDto`, `FUmUserSettingsDto`, `FUmGamePlayerDto` (`SeatOrder: double`), `FUmGameResponseDto` (`Version: double`; `Host.Id`/`Opponent.Id` = `User.id`, `Players[].Id` = id `GamePlayer`), `FUmGameStateResponseDto` (`SequenceNumber/TurnCount: double`, `Phase: FString`), `FUmGameMutationResultDto` (`Timestamp: FUmDateTime` epoch-ms), `FUmGameStateSubscriptionDto` (5 строк), `FUmGameEventDto`, `FUmTurnStateDto`, `FUmEventsSinceDto`, `FUmStanceOptionDto`, `FUmHeroListItemDto` (cuid), `FUmBoardListItemDto` (cuid), `FUmHeroDto` (`Id` = имя), `FUmCardDto` (без `effects{timing}`), `FUmBoardDto`/`FUmBoardSpaceDto` (сетка из `Spaces`), `FUmContentSummaryDto`, `FUmQueueStatusDto`, `FUmMatchFoundDto`, `FUmPenaltyInfoDto`, `FUmPresenceDto`, `FUmHeartbeatDto`; `FUmDateTime { FDateTime Utc; bool bSet; }` с `CustomImportCallback` (число → epoch-ms, строка → ISO 8601) | R1 §2.7-2.8; R2 §2.2; R3 §2.5, §2.8, §2.12; R5 §2.3, §4.1; R6 §2.2 |
| `UmGameState.h` | Wire-модель К1 §3.4.4 без изменений семантики: `FUmPosition`, `FUmFighterEffect`, `FUmFighter` (`Movement = 2`, `AttackType = "melee"`), `FUmGameStatePlayer`, `FUmCardEffect` (`Type`, `Timing`, `Target`, `BoostSource`, `Text`, `bOptional`, `bBlind`, `OptionLabels[]`, `ChooseCount`, `RawJson: FJsonObjectWrapper`; `IsBoostFromHand()`), `FUmCard` (`Id` — instance `<cardId>::n`, `CardId`, значения `-1` = отсутствует, `bHidden` = `Name == "???"`), `FUmDeckState`, `FUmCardList`, `FUmHandZone` (`MaxSize = 7`), `FUmCell` (`Zone` — legacy первая зона; `Zones[]`), `FUmCellRow`, `FUmBoardState` (`Rows[y].Cells[x]`, `Doors: TMap<FString,bool>` ключ `"x:y"`), `FUmCombatState` (`AttackerId` — боец, `DefenderId` — userId, `TargetFighterId`, `AttackerCardId`, `DefenderCardId`, `bHasDefenderCard`, `StartedAt`), `FUmPendingOption`, `FUmPendingEffect`, `FUmGameStateMetadata` (`ActionsRemaining = 2`, флаги `*ThisTurn = false`, `HeroStances`, `TurnStartPositions`, `bHasCombatInfo`), `FUmGameState` (`bHasDecks`, `bHasDiscardPiles`; хелперы `FindFighter`, `MyHand(userId)`, `IsMyTurn`, `AmIDefender`, `MyPendingEffects`, `MyStance`) | R3 §2.9; R4 §2.5 |
| `FUmGameStateParser` | `ParseFull(StateJson, Out, Report)`: `FJsonSerializer::Deserialize` → `JsonObjectToUStruct(bStrictMode=false)` → «ремонт» по DOM (`cells[y][x]` в `Rows`, строковые `handZones.cards` (R6 §2.6), флаги `bHas*`, `-1` для отсутствующих чисел, wire-enum в отчёт); `ParsePartial(FUmGameStateSubscriptionDto, InOut)`: пять `Deserialize`, `Decks/DiscardPiles` не трогает; `FUmParseReport` (неизвестные enum, отсутствующие обязательные поля) → `LogUmModel` Warning, не роняет применение | К1 §3.4.5; R3 §2.11 |
| `FUmSnapshotDiff` | `Compute(Prev, Next) → TArray<FUmMatchEvent { FGameplayTag EventTag; FString FighterId; int32 Magnitude; FIntPoint From, To; FString CardId; FString UserId; }>`: `Match.Event.Fighter.{Moved,Damaged,Healed,Defeated,Immobilized}`, `Match.Event.Combat.{Declared,DefenseRevealed,Resolved,AutoResolved}`, `Match.Event.Card.{Played,Drawn,Discarded}`, `Match.Event.Turn.Changed`, `Match.Event.Actions.Changed`, `Match.Event.Pending.{Added,Removed}`, `Match.Event.Stance.Changed`, `Match.Event.Game.Over`, `Match.Event.Decks.Refreshed`; итоги боя — по диффу `Fighters[].Health` (`combatSummary` не приходит — R4 §3.12); смена хода — по `CurrentTurnPlayerId/TurnCount` (`turnChanged` молчит при авто-передаче — R4 §3.3) | К1 §3.7.2; К3 §3.6.1 |
| `UmOps.gen.h` + `FUmOpsRegistry` | Сгенерированные `static const TCHAR*` документы + реестр `Name → {Document, EUmAuthMode, bIsMutation, RateLimitBucket}`; список операций — К3 Приложение A (точный контракт: `since: Float`, `sinceSequence: Float!`, `matchFound(userId: String!)`, без `idempotencyKey` у `joinGame`/очередей, `hero(id)` с `cards { … imageUrl imageUrlRu effects { id text } }` без `timing`) | К3 Приложение A; R3 §2.4; R1 §2.12 |
| `FUmInputs` | Билдеры входных DTO в `TSharedPtr<FJsonObject>` (только поля схемы; optional-поля **опускаются**, а не отправляются пустой строкой): `Login`, `Register`, `CreateGame(mode, boardCuid)` + `idempotencyKey` GUID отдельным аргументом, `JoinGame(gameId)`, `Maneuver(gameId, moves[], boostCardId?)` (только `moves[]`, legacy-поля не используются — R3 §4.13), `MoveFighter`, `Attack(gameId, attackerId, cardId, targetId, boostCardId?)`, `PlayDefense`, `PlayScheme`, `ResolvePendingEffect(effectId, fighterId?, x?, y?, optionIndex?)`, `GameId` (для `resolveCombat/endTurn/pass`), `ToggleDoor`, `SetStance`, `Settings`, `JoinQueue`, `Heartbeat` | R3 §2.7; R1 §2.3 (`forbidNonWhitelisted`) |

### 4.3. Модель контракта (`UmModel`) — правила-подсказки и теги

| Класс | Ответственность | Источник |
|---|---|---|
| `FUmBoardGeometry` | `Reachable(board, start, maxSteps, blocked) → TMap<FIntPoint,int32>` (BFS 4-связности; непроходимы `wall/obstacle/door && !isOpen` + клетки живых бойцов), `ShortestPath`, `IsAdjacent` (манхэттен == 1), `SameLegacyZone(a, b)` (`Cells[a].Zone == Cells[b].Zone`, оба непусты), `SharesAnyZone` (пересечение `Zones[]` — только для условий, **не** для атаки) | R4 §2.6.1; `backend/src/game-engine/engine/adjacency.service.ts:90-150, 201-218` |
| `FUmRules` | `BannerAllows(banner, fighterName)` (`Any`/пусто → ok; `sing()`: `ies→y`, `ves→f`, `([^s])s$→$1`; срез числового суффикса; неизвестный банер → ok), `BoostAllowed(card, fighter, role, heroSlug)` (эффект `BOOST` с `PLAYER_CHOICE_HAND`/без источника, или `heroSlug == "king-arthur"` для атаки; не та же карта), `IsInAttackRange(state, attacker, target, ranges: TArray<FUmAttackRangeRow>)` (adjacent; иначе `ranged && SameLegacyZone`; иначе `manhattan ≤ effectiveRange(stance ?? hero)`), `FighterFitsPending(pending, fighter, me)` | `backend/src/game-engine/validators/game-rules.validator.ts:559-604`; `game-action-executor.service.ts:136-154, 1008-1058`; `arthur.handler.ts:23,30`; `ability-config.ts:365-413`; `ms-marvel.handler.ts:22,75` |
| `FUmAttackRangeRow : FTableRowBase` | `HeroSlug`, `StanceId` (пусто = базовая), `Range` — источник `DT_AttackRange` (bullseye 5, t-rex 2, ms-marvel 2, muhammad-ali/float 2), генерируется `export-ability-table.ts` | R4 §2.7.1, §3.6 |
| `FUmLegalActions` | `Enumerate(state, myUserId, ranges, phaseGate) → FUmLegalSet { MoveTargets, ManeuverTargets, Attacks[{attackerId, cardId, targetId, bBoostAllowed}], PlayableSchemes, PlayableDefenses, MyPending, Stances, bCanEndTurn, bCanPass, bCanResolveCombat, ServerWouldAllow (клетки, достижимые только «через» бойца), WhyNot: TArray<FUmRejection{FGameplayTag Action; FText Reason}> }`; единственная точка вычисления аффордансов; реализует таблицу §5.7 | К2 §3.5.2; К1 §3.6.4 |
| `FUmCombatPreview` (v1) | `Estimate(state, attackerId, cardId, boostCardId?, targetId, mods: DT_HeroCombatMods) → { AttackKnown, bDefenseUnknown }` — только печатные значения + boost + известные модификаторы героев; «оценка», не предикция | R4 §2.8, §3 п.22; К2 §3.5.4 |
| `FUmSlug` | `HeroSlug(name)`, `AssetSlug(title)` — две разные функции (G15) | `fighter.model.ts:80-85`; `scripts/sync-card-assets.mjs:23-31` |
| `UmTags.h` | Нативные теги (`UE_DEFINE_GAMEPLAY_TAG`, `$UE/Source/Runtime/GameplayTags/Public/NativeGameplayTags.h`): таксономия §5.6 | К3 §3.9 |
| `FUmTagMaps` | `EUmGamePhase ↔ Match.Phase.*`, `EUmCardType ↔ Card.Type.*`, `EUmPendingEffectType ↔ Pending.Type.*`, `EUmZone ↔ Zone.*`, `EUmFighterType ↔ Fighter.Type.*` | К3 §3.9 |
| `UmTableRows.h` | `FUmCardArtRow { HeroSlug, CardSlug, Title; En, Ru: TSoftObjectPtr<UTexture2D> }`, `FUmHeroArtRow`, `FUmBoardArtRow`, `FUmServerErrorRow { Substring; Text: FText }`, `FUmHeroCombatModRow` (v1) | К1 §3.8.4 |

### 4.4. Состояние и синхронизация (`UmClient/State`)

| Класс | Ответственность | Зависимости | Источник |
|---|---|---|---|
| `UUmStateSubsystem : UGameInstanceSubsystem` | Оркестрация лобби/комнаты/партии: `EnterLobby/RefreshAvailableGames`, `CreateGame(mode, boardCuid)`, `JoinGame(gameId)`, `EnterRoom/LeaveRoom`, `SelectHero(cuid)`, `ToggleReady` (in-flight guard), `StartGame`, `EnterGame(gameId)`, `ExitGame`, 11 `Do*()` gameplay-действий через `FUmActionGate`; владеет `FUmGameSnapshotStore`, `FUmServerClock`, таймерами защиты и авто-резолва; `GetMatchTags() → FGameplayTagContainer`; `GetLegalSet()`; делегаты `OnLobbyUpdated`, `OnRoomUpdated`, `OnSnapshotApplied(prev, next, source, diff)`, `OnActionRejected(FUmGraphQLError)`, `OnGameEnded`, `OnSyncStatus(EUmSyncStatus)` | `UUmNetSubsystem`, `UUmAuthSubsystem`, `UUmContentSubsystem`, `UmModel` | К1 §3.2, §3.5.2-3.5.5 |
| `FUmGameSnapshotStore` | `Apply(FUmGameState&&, EUmSnapshotSource {Query, Mutation, Subscription}) → FUmApplyResult { EApplyResult {Applied, DroppedStale, GapDetected}; bool bDecksStale; TArray<FUmMatchEvent> Diff }`, `ForceReplace`, `Current()`, `LastSeq()`, `bDecksStale`; правила — §5.2 | `UmModel` | К1 §3.5.1; К2 §3.4.4; G23 |
| `FUmServerClock` | `OffsetMs = GameMutationResult.timestamp − LocalUtcNowMs` (скользящее среднее); `GetServerNow()`; дедлайн защиты `combatInfo.startedAt + DefenseTimeoutSec` | — | R3 §2.8; R4 §3.8 |
| `FUmActionGate` | Одна in-flight gameplay-мутация на клиент; на время запроса — тег `Input.Mode.Busy`; ретраев нет; при `Concurrent` — `RefetchState()` без повтора действия | — | R2 §3.21; R7 §3 п.7 |

### 4.5. Контент (`UmClient/Content`)

| Класс | Ответственность | Источник |
|---|---|---|
| `UUmContentSubsystem : UGameInstanceSubsystem` | Фасад трёх провайдеров: **Baked** (`UUmHeroDefinition`/`UUmBoardDefinition` через `UAssetManager::GetPrimaryAssetIdList("UmHero")`, `DT_CardArt`) → **Runtime** (`hero(id:<имя HERO-бойца>)`, `boards`, `board(id)`, `heroStances(heroSlug)` + `UUmImageCacheSubsystem`) → **Placeholder** (`T_UI_Placeholder_*` + текст); `EnsureHero(heroSlug, OnReady)`, `FindCardArt(cardCuid)`, `IdMap()` (`name ↔ cuid ↔ heroSlug` из `heroList(limit:300)`/`boardList(limit:100)` после логина), `GetStances(heroSlug)` с кэшем на сессию; контент никогда не блокирует старт партии; истина для чисел — только `GameState` | R6 §2.4, §3.2-3.4; R5 §3.1, §3.10; К3 §3.5.1 |
| `FUmContentCache` | `Saved/UmContent/<host>/{heroes.json, hero-<name>.json, boards.json, stances-<slug>.json}` с `fetchedAt`; ключ инвалидации — `contentSummary.heroesCount` + `contentSummary.boardsCount` + `max(updatedAt)` + TTL 1 ч (`contentVersion` — константа `2.0.0`); при входе в партию `hero(id)` перезапрашивается всегда | R6 §2.5, §4.4 |
| `UUmImageCacheSubsystem : UGameInstanceSubsystem` | `Get(Url, OnTexture)`: память (LRU 256) → диск `Saved/UmTextures/<sha1(url)>.png` → HTTP GET (≤ 4 параллельно) → `IImageWrapper` PNG/JPEG → `UTexture2D::CreateTransient` (`SRGB`, `NoMipmaps`, `TextureGroup UI`); корневые `/assets/…` → `AssetBaseUrl + path`, абсолютные Supabase-URL — как есть; `.webp/.avif/.gif` по URL **не декодируются** → placeholder (офлайн-конвертация в `export-content.mjs`) | R5 §2.12, §3.6; R8 §2.9; R9 §3.1 |
| `UUmHeroDefinition : UPrimaryDataAsset` | `PrimaryAssetType "UmHero"`; `HeroSlug`, `Name`, `Set`, `Avatar/Mini/Cover: TSoftObjectPtr<UTexture2D>`, `Cards: TArray<FUmCardArtRow>`, `AccentColor`; `GetPrimaryAssetId() = {"UmHero", HeroSlug}` | К3 §3.5.1; G4 |
| `UUmBoardDefinition : UPrimaryDataAsset` | `PrimaryAssetType "UmBoard"`; `BoardSlug`, `Name`, `Texture`; `cobble-city` ↔ арт `hells-kitchen` | R9 §2.3 |
| Пакетирование | Папка на сет `Content/Heroes/<Set>/` + `PAL_<Set> : UPrimaryAssetLabel` (чанк на сет) — core `AssetManager`; в MVP один сет (Medusa, King Arthur, Cobble City); бюджет текстур — по R9 §3 п.10 (512×716 ≈ 0,5 МБ BC7/карта; 1024×1432 только для инспектора по необходимости) | R8 §2.13; R9 §3 п.10; F16 |

### 4.6. UI (`UmClient/UI` + `Content/UI`)

| Класс / виджет | Ответственность | Источник |
|---|---|---|
| `UUmGameViewportClient : UCommonGameViewportClient` | Обязателен для input routing CommonUI | R8 §2.6; `$UE/Plugins/Runtime/CommonUI/Source/CommonUI/Public/CommonGameViewportClient.h` |
| `AUmPlayerController` | `BeginPlay()` → `UUmUISubsystem::EnsureRootLayout(this)`; EnhancedInput (`IMC_Board`: `IA_Select`, `IA_Cancel`, `IA_Confirm`, `IA_Zoom`, `IA_Pan`; `IMC_Menu`); события ввода → `UUmPresentationSubsystem` | F17; R8 §2.7 |
| `UUmUISubsystem : ULocalPlayerSubsystem` | `EnsureRootLayout(APlayerController*)` (идемпотентно, `CreateWidget<UUmRootLayout>(PC, WBP_RootLayout)` + `AddToViewport`), четыре `UCommonActivatableWidgetStack` под тегами `UI.Layer.{Game, Menu, Modal, Toast}`, FSM экранов по `UI.Screen.*` (переходы — К1 §3.6.2 без изменений), `PushScreen(tag)`, `PushModal(class, payload)`, `Toast(FText, kind)`, `ShowReconnectOverlay(bool)`; `FUIInputConfig`: Game — `ECommonInputMode::All`, Menu/Modal — `Menu` | К1 §3.6.1-3.6.2; F17 |
| `UUmRootLayout : UCommonUserWidget` | C++-родитель `WBP_RootLayout` с `BindWidget`-стеками | К3 §5.1 |
| `UUmActivatableScreen : UCommonActivatableWidget`, `UUmModalBase` (`bIsModal`), `UUmGameHudBase`, `UUmCardViewBase : UCommonUserWidget` (`BlueprintImplementableEvent OnCardChanged`) | C++-базы всех `WBP_*`: `BindWidget`-поля, логика в C++, внешний вид и анимации — в Blueprint через MCP | К3 §5.1; К1 §5.1 |
| `UUmGameHudModel : UObject, INotifyFieldValueChanged` | Модель для биндинга HUD (`FieldNotify`, модуль `FieldNotification` — `$UE/Source/Runtime/FieldNotification/Public/INotifyFieldValueChanged.h:22`): `TurnCount`, `PhaseTag`, `bIsMyTurn`, `ActionsRemaining`, `MyHand: TArray<FUmCardView>`, `OpponentHandCount`, `MyDeckCount/MyDiscardCount/OpponentDeckCount/OpponentDiscardCount`, `bDecksStale`, `Players[2]: FUmPlayerPanelView`, `Combat: FUmCombatView` (карты атаки/защиты из `DiscardPiles[attacker.OwnerId]` по `AttackerCardId/DefenderCardId`, `AttackValue`, дедлайн), `Pending: FUmPendingView`, `Stances: TArray<FUmStanceView>`, `Log: TArray<FText>`, **`MatchTags: FGameplayTagContainer`**, **`LegalSet`**, **`WhyNot`**; источник — `PresentedState` (G9) | К1 §3.6.3; К3 §3.9-3.10; К2 §3.5.2 |
| `UUmHudLibrary : UBlueprintFunctionLibrary` | `IsAffordanceEnabled(Model, FGameplayTagQuery)`, `GetWhyNot(Model, ActionTag) → FText` — декларативный гейтинг кнопок из Blueprint | G3, G16 |
| `WBP_GameHUD` | Раскладка финального веб-HUD (R9 §2.12): оппонент TL, фаза TC, рука оппонента TR, борд по центру, локальный игрок BL, рука BC (7 слотов), колода/сброс BR, инспектор — правая панель; корневой `UCommonVisibilitySwitcher` со слотами `Desktop` и `Mobile` (bottom-sheet инспектор, сворачиваемая рука); переключение по aspect ratio/`ECommonInputType` | R9 §3 п.8; К3 §3.7.2; G5 |
| `WBP_CombatPanel` | `COMBAT` + я защитник: открытая карта атаки, `AttackValue`, таймер, «выберите DEFENSE/VERSATILE», «Без защиты» (= `resolveCombat`); `COMBAT` + я атакующий: «Ждём защиту…», таймер, **без кнопки резолва**; `COMBAT_RESOLVE`: обе карты, `DefenseValue`, «Разрешить бой» атакующему (авто через 1,5 с), защитнику — через 5 с; `bDecksStale` → карты полупрозрачны до рефетча | R4 §3.9; G10, G12 |
| `WBP_PendingEffectBanner`, `WBP_ChooseOneDialog` | Первый из `MyPendingEffects()`; скрыт при `Match.Phase.Combat` (G19); MOVE/PLACE — подсказка + «Пропустить» (локально); CHOOSE_ONE — модалка `options[].label`, `chooseCount` | R4 §2.10; К1 §3.6.3 |
| Остальные `WBP_*` | Как в К1 §3.6.3 (`WBP_Lobby` с вкладкой «Мои игры» и действием «Покинуть», `WBP_Room` с поллингом `game(id)` 3 с, `WBP_StanceBar`, `WBP_GameOver` → `leaveGame`, `WBP_ReconnectOverlay`, `WBP_ConnectionBadge` по `Net.State.*`) | К1 §3.6.3 |
| Локализация | Весь «хром» — `FText` через `ST_UI`; тексты карт/способностей — с сервера; ошибки сервера — `DT_ServerErrorMap` по подстроке с фолбэком «Действие отклонено»; RU-арт при `ru` с фолбэком EN; `F_Inter` | R8 §2.12, §3.7; R4 §4.19; R5 §3.13 |

### 4.7. Презентация (`UmClient/Presentation` + `Content/Board`, `Content/Cues`)

| Класс | Ответственность | Источник |
|---|---|---|
| `UUmPresentationSubsystem : UWorldSubsystem` | Спавн/уничтожение `AUmGameStage` по `EnterGame/ExitGame`; **очередь воспроизведения** снапшотов (бурсты VS_AI до 40 шагов — R4 §2.16); `PresentedState` (последний проигранный) ≠ `Current`; каждый `FUmMatchEvent` → `UUmMatchCueSubsystem::Emit(tag, params) → duration`; fast-forward по клику/`IA_Confirm`; пока очередь не пуста — тег `Input.Mode.Busy`; `FUmInputStateMachine`; подсветки (`Highlight(cells, kind)`), курсор/трассировка | К1 §3.7; К3 §3.10; G9 |
| `FUmInputStateMachine` | Приоритеты как `GameView.handlePhaserEvent` (R7 §2.9.6): `Locked(in-flight\|playback)` → `ChooseOne(modal)` → `PendingMove/PendingPlace` → `Defense` (COMBAT и я защитник) → `ManeuverPlanning{paths, boostCardId?}` → `AttackTargeting{attackerId, cardId, boostCardId?}` → `Idle`; переходы гейтятся `FUmLegalSet`; основной способ движения — `maneuver` (добор + все бойцы + boost), `moveFighter` — кнопка «быстрый ход» | К1 §3.6.4; К3 §3.6.5; R7 §4 п.4 |
| `AUmGameStage` | `UInstancedStaticMeshComponent` клеток (100×100 uu; per-instance custom data: цвет зоны, `isObstacle`, highlightKind), `FightersRoot`, ортографическая камера сверху (`OrthoWidth = max(W,H) × 100 × 1.15`), плоскость арта доски под сеткой (alpha 0.72); геометрия **только из `boardState`** (`Width/Height/Rows[y].Cells[x]`) — возможен fallback 20×20 без зон; координаты мутаций 0..19 | R4 §3.7; `game-initialization.service.ts:279-289`; R9 §2.3 |
| `AUmFighterActor` | Плоскость с `T_Hero_<slug>_Mini` (вписывать по высоте) или диск с инициалами; `UWidgetComponent` (Screen) с `WBP_FighterPlate` (HP-бар `#4ecca3/#d7b84b/#ff4d5f`, иконки `Fighter.Status.*`); кольцо выбора; герой 62 %, MINION 48 % клетки; побеждённые скрываются через cue | R7 §2.10; R9 §3 п.4 |
| `UUmMatchCueSubsystem : UWorldSubsystem` | Собственная cue-шина без GAS: `Emit(FGameplayTag CueTag, const FUmCueParams&) → float Duration`; маппинг `Match.Event.* → GameplayCue.Match.*` через `DA_UmCueRegistry`; отсутствующий cue — нулевая длительность + лог | F3; К3 §3.10 вариант B |
| `UUmCueRegistry : UDataAsset`, `UUmCueNotify : UObject` | `TMap<FGameplayTag, TSubclassOf<UUmCueNotify>>`; `UUmCueNotify::Execute(World, Params) → Duration` — `BlueprintNativeEvent`, реализуется `CUE_*` Blueprint-ассетами (tween 280 мс на клетку, всплывающий урон 900 мс и т. д. — тайминги веба как референс R7 §2.10) | К3 §3.10 |

### 4.8. Тесты и dev-инструменты

| Набор / класс | Что проверяет / делает | Источник |
|---|---|---|
| `Unmatched.Net.WsStateMachine` | На `FUmFakeWebSocket`: init в `OnConnected`, ack, subscribe/next/error/complete по id, `ping → pong`, коды 4400/4401/4406/4408/4409/4429/1006, backoff 1/2/4/8/16 с, переподписка с новым `since`, `Reconnect` после refresh | R1 §2.4 |
| `Unmatched.Net.ErrorClassifier` | Все строки таблицы §5.3: dev-формат (`extensions.code`), prod-формат (верхнеуровневый `code` без `extensions`), `status 409/404`, `originalError.message[]`, auth-тексты на русском, `Concurrent modification`, `Opaque`, тело при HTTP 400/200 | R1 §2.10 |
| `Unmatched.Net.RateLimiter`, `Unmatched.Net.Auth` | Бакеты; на `FUmFakeHttpTransport`: декод `exp`, проактивный таймер, single-flight (N одновременных → 1 запрос), очередь повторов, `SessionLost`, `Logout` без валидного access не зовёт сервер | R1 §2.6, §4.9 |
| `Unmatched.Model.DtoRoundTrip` | `FJsonObjectConverter` для всех USTRUCT §4.2: camelCase-JSON ↔ PascalCase-`UPROPERTY`, `Float → double`, `FUmDateTime` числом и строкой, `TMap<FString,…>`, `null`-поля | G11 |
| `Unmatched.Model.OpsGenerated` | Хеш набора `unreal/Ops/*.graphql`, зашитый в `UmOps.gen.h`, совпадает с текущими файлами (защита от устаревшего заголовка); сама валидация против `schema.introspection.json` — `unreal/Tools/ops-check.mjs` (graphql-js) в CI | G2; R1 §1 п.11 |
| `Unmatched.Model.InputsWhitelist` | Каждый ключ, который эмитят `FUmInputs::*`, существует во входном DTO снимка introspection; optional-поля отсутствуют, а не пусты | R1 §2.3 |
| `Unmatched.Model.StateParser` | Фикстуры `Tests/Fixtures/state/*.json` (снятые `snapshot-fixtures.mjs`): `seq1_initial`, `after_attack`, `after_defense`, `pending_{move,place,choose_one}`, `game_over`, `subscription_payload` (5 строк), чужая рука `???`, `handZones.cards` строкой, неизвестные enum, fallback-доска 20×20 | R3 §2.15; R6 §2.6 |
| `Unmatched.Model.SnapshotDiff` | Движение, урон, гибель, смена хода без `turnChanged`, начало/конец боя, auto-resolve, авто-флип стойки, `Decks.Refreshed` | К1 §6.1 |
| `Unmatched.Model.Geometry`, `Unmatched.Model.Banner`, `Unmatched.Model.LegalActions`, `Unmatched.Model.Slug` | BFS с блокировкой, манхэттен, `SameLegacyZone` на мультизонной клетке Cobble City (`(1,1)`, `(3,1)`, `(1,2)` — `backend/src/content/data/boards/cobble-city.ts:14-53`); `Harpy ↔ Harpies 2`, `Arthur ↔ King Arthur`, `Wolves ↔ Wolf`; гейты и `WhyNot`; `HeroSlug`/`AssetSlug` («Devil of Hell's Kitchen» → `devil-of-hells-kitchen`, R9 §2.6) | R4 §2.6-2.7 |
| `Unmatched.Model.RulesParity` | Для каждой фикстуры `Tests/Fixtures/rules/**`: `FUmLegalActions` содержит действие ⇔ `response` без ошибки (с поправкой на намеренную строгость §5.7); `FUmSnapshotDiff(stateBefore, stateAfter)` даёт ожидаемые события | G14 |
| `Unmatched.Model.AttackRangeSync` | Строки `DT_AttackRange` совпадают с `Import/ability-table.json`; CI-шаг `npm run ability:check` падает при расхождении снимка с `ability-config.ts` | F19 |
| `Unmatched.Client.SnapshotStore` | Правила §5.2: seq-guard по источникам, перезапись при равном seq из Mutation/Query, мерж `decks`, `bDecksStale`, gap → refetch, `ForceReplace` | G12, G23 |
| `Unmatched.Client.InputFsm`, `Unmatched.Client.Playback` | Приоритеты состояний; очередь снапшотов: порядок, fast-forward, `PresentedState` отстаёт от `Current` ровно на непроигранные снапшоты | К3 §6.1 |
| `Unmatched.Client.MockBackend` | `UUmMockBackend`: `bMockBackend=true` подменяет транспорт и сокет фейками, проигрывает сценарии из фикстур (логин → лобби → комната → партия с бурстом снапшотов); используется SlateInspector-прогонами без `localhost:3000` | G6 |
| `Unmatched.E2E.*` (флаг `-UmE2E`, `LatentIt`) | Сценарий К1 §6.2 против `localhost:3000` (учётки `<LOCAL_P1_EMAIL>/<LOCAL_P1_PASSWORD>`, `<LOCAL_P2_EMAIL>/<LOCAL_P2_PASSWORD>` — R6 §2.9): abort активных игр → `heroList/boardList` → `createGame → joinGame → selectHero×2 → toggleReady×2 → startGame` → ходы → 31 с без защиты → `resolveCombat` → обрыв WS → `gameSequence/gameState` → forced refresh → `leaveGame` | R6 §2.6, §3.6 |
| `FT_Um_ApplySnapshotRendersBoard`, `FT_Um_DiffPlaysMoveTween`, `FT_Um_PendingBannerShown` (`AFunctionalTest`, `L_Test_Game`) | Рендер 24/400 клеток и 8 фишек из фикстуры; tween ≤ 0,4 с; баннер pending | К1 §6.3 |
| CLI | `UnrealEditor-Cmd.exe Unmatched.uproject -unattended -nopause -NullRHI -ExecCmds="Automation RunTests Unmatched.;Quit" -testexit="Automation Test Queue Empty" -log -ReportOutputPath=<dir>` (параметр по коду — `ReportOutputPath`, `$UE/Source/Developer/AutomationController/Private/AutomationControllerManager.cpp:213`) | R8 §2.11, §4.2 |
| `UUmDevConsole` | Команды `um.login <email> <pwd>`, `um.join <gameId>`, `um.mock on`, `um.mock off`, `um.refetch`, `um.dumpstate`, `um.toggledoor x y` (единственный доступ к `toggleDoor` — мёртвая механика, R4 §2.6.6) | К1 §3.6.4 |

---

## 5. Принципы

### 5.1. Что в C++, что в Blueprint, что через MCP

| Слой | C++ | Blueprint/ассеты | Создаётся/правится через MCP |
|---|---|---|---|
| Сеть, auth, модель, парсер, диф, правила-подсказки, store, таймеры, input-FSM, cue-шина, субсистемы, C++-базы виджетов/акторов, тесты | **100 %** | — | только запуск тестов (`AutomationTestToolset`) и чтение логов (`LogsToolset`) |
| Внешний вид `WBP_*` (дерево, стили, анимации UMG), `BP_UmGameStage`/`BP_UmFighter` (меши, материалы, тайминги), `CUE_*`, материалы зон/подсветок, `DT_*`, `DA_*`, `ST_UI`, `IA_*`/`IMC_*`, `L_Main` | — | **все** | `UMGToolSet`, `BlueprintTools.write_graph_dsl`/`set_parent`, `MaterialTools`/`MaterialInstanceTools`, `DataTableTools`, `DataAssetTools`, `StringTableTools`, `AssetTools`/`ObjectTools`, `SceneTools`/`ActorTools`, `TextureTools.import_file` (PNG) |
| Мелкая glue-логика виджетов (показать/скрыть по тегу, проиграть анимацию, кнопка → `BlueprintCallable`) | — | Blueprint DSL | `write_graph_dsl` (S-expression DSL, компилирует сразу) |

Принцип: **логику с состоянием и сетью — только в C++** (`00-mcp-verification.md:59`); Blueprint-графы через DSL — тонкие обвязки. Все `WBP_*` наследуют C++-базу с `BindWidget`-полями — MCP создаёт дерево, C++ владеет логикой.

### 5.2. GameState: двухфазный парсинг, дедупликация, приватность

**Двухфазный парсинг.** Фаза 1 — GraphQL-обёртка (`FJsonObjectConverter` → `FUm*Dto`, PascalCase, wire-enum строками). Фаза 2 — `FUmGameStateParser::ParseFull(Dto.State)` для `gameState`/ответов мутаций или `ParsePartial(FUmGameStateSubscriptionDto)` для подписки (пять строк, `Decks/DiscardPiles` не трогаются). Неизвестные enum-строки и отсутствующие поля — в `FUmParseReport` (Warning), применение не роняют (F4). `DateTime` — оба формата (число epoch-ms / ISO-строка). Серверные дефолты зашиты в поля: `Movement = 2`, `AttackType = "melee"`, `ActionsRemaining = 2`, флаги `*ThisTurn = false`, стойка — `isDefault` из `heroStances` (R3 §3 п.3).

**Правила `FUmGameSnapshotStore::Apply(Incoming, Source)`** (К1 §3.5.1 + G12 + G23):

| Условие | Действие |
|---|---|
| `Source == Subscription && Incoming.Seq <= LastSeq` | `DroppedStale` (эхо после ответа мутации — норма) |
| `Source ∈ {Query, Mutation} && Incoming.Seq < LastSeq && !bForce` | `DroppedStale` |
| `Source ∈ {Query, Mutation} && Incoming.Seq == LastSeq` | **Применить** (перезаписать): это единственный снапшот с `decks/discardPiles` для этого seq, если эхо подписки пришло первым (факт §1.3 п.8); диф — только `Match.Event.Decks.Refreshed`; `bDecksStale = false` |
| `LastSeq == 0` **или** `Incoming.Seq == LastSeq + 1` | Применить; диф → очередь презентации |
| `Incoming.Seq > LastSeq + 1` | Применить (снапшот полный) **и** `GapDetected` → `RefetchState()` (полный `gameState` ради `decks/discardPiles` и пропущенных промежуточных состояний) |
| `Source == Subscription && !Incoming.bHasDecks` | Мерж `Decks/DiscardPiles` из `Current`; если после мержа изменился размер руки/сброса любого игрока, фаза, `bHasCombatInfo` или `bHasDefenderCard` → `bDecksStale = true` → `RefreshFullStateDebounced(300 мс)`; HUD показывает stale-состояние (`WBP_DeckDiscard`, `WBP_CombatPanel`) до прихода полного снапшота |
| Ответ `Query`/`Mutation` применён | `bDecksStale = false` |

Дедупликация событий `gameEnded`: ключ `(gameId, "GAME_ENDED", seq)`. Реконнект: после `connection_ack` → переподписка `GameStateUpdated(since: LastSeq)`, `GameEnded` → `gameSequence(gameId)` → если `> LastSeq` → `gameState` → `ForceReplace` → `Live`. `eventsSince` для восстановления **не используется** (журнал без состояния, без ходов ИИ и auto-resolve, пишется асинхронно — R3 §4.10); в v1 читается один раз при входе для `WBP_ActionLog`.

**Приватность.** Своя рука — `HandZones[myUserId].Cards` (не по `isVisible`, R3 §3.13). Чужая рука — только рубашки по `Cards.Num()`; `CardId`/`BannerName` чужих карт и чужой `DrawPile` клиентом **не читаются** (утечка на сервере — R4 §4.10, предпосылка B8). Открытые карты боя — из `DiscardPiles[attacker.OwnerId]` по `AttackerCardId`/`DefenderCardId` (сброс в Unmatched открыт).

### 5.3. Ошибки, refresh, реконнект

Классификатор `FUmErrorClassifier` (R1 §2.10 + G8 + F6):

| Признак | `EUmErrorClass` | Реакция |
|---|---|---|
| `!bTransportOk`, таймаут, `HttpCode == 0`, тело не JSON | `Network` | ретрай для query по `FUmRetryPolicy`; тост для мутации; `Net.State.*` |
| `Code == UNAUTHENTICATED` **или** `Message ∈ {«Неавторизованный доступ», «Token revoked», «Пользователь не найден»}`, операция ∉ {`Login`, `ChangePassword`} | `Auth` | single-flight refresh → повтор 1 раз → при второй `Auth` → `SessionLost` |
| `Code == UNAUTHENTICATED` от `Login`/`ChangePassword` | `Validation` | показать сообщение (не refresh) |
| `Code ∈ {BAD_REQUEST, BAD_USER_INPUT, GRAPHQL_VALIDATION_FAILED, GRAPHQL_PARSE_FAILED}` | `Validation` | gameplay — «ход отклонён» с `Message` через `DT_ServerErrorMap`; `OriginalMessages[]` в лог; `Query is too complex` — дополнительно `ensure` в dev |
| `Code == INTERNAL_SERVER_ERROR && Status == 409 && Message ~ /Concurrent modification\|sequence/i` | `Concurrent` | `RefetchState()` один раз, без автоповтора действия |
| `Code == INTERNAL_SERVER_ERROR && Status == 409` иначе (`MaxActiveGames`, email/username занят) | `Conflict` | тост; для `MaxActiveGames` — предложить «Мои игры» → `leaveGame` |
| `Status == 404` или `Message ~ /not found\|не найден/i` | `NotFound` | тост / уйти в лобби |
| `Code == FORBIDDEN` | `Forbidden` | тост (не участник, статус игры) |
| `Status == 429` / `THROTTLED` / `TOO_MANY_REQUESTS` (код не подтверждён — R2 §4.15) | `RateLimited` | тост, без ретрая |
| `Code == INTERNAL_SERVER_ERROR && Message == "Internal server error"` (prod-маскирование) | `Opaque` | если `Auth == Required` и `exp` access-JWT в пределах ±2 мин → один раз как `Auth`; иначе «Действие отклонено сервером» + лог |
| остальное | `Unknown` | тост «Ошибка сервера» + лог |

WS-ошибки на `subscribe` (без `extensions.code`) классифицируются по подстрокам сообщения; `next{errors}` на живой подписке `GameStateUpdated` → лог + `RefetchState()` + подписка сохраняется (F24).

Auth: access — только в памяти; refresh — `IUmSecureStore`; проактивный refresh за 300 с до `exp` — основной путь в production; после refresh — обязательный `ReconnectWebSocket` (токен фиксируется в `connection_init` на всё время сокета; веб этого не делает — R7 §2.13 п.17); любая ошибка `refreshTokens` → `SessionLost`; `Refresh token has been revoked` → «вход с другого устройства».

### 5.4. Идемпотентность, лимиты, ретраи

| Механизм | Решение | Источник |
|---|---|---|
| `createGame(idempotencyKey)` | `FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphensLower)` на каждый клик; повтор при сетевой ошибке — тот же ключ | R1 §2.12; R2 §3.7 |
| `joinGame`, `joinQueue`, `leaveQueue`, `leaveAllQueues` | **без** `idempotencyKey`; `joinGame` — только `{ gameId }` | R1 §2.12; R2 §3.26 |
| `X-Idempotency-Key` | не отправляется (сервер не читает) | R1 §2.12 |
| `toggleReady` | не идемпотентен — клиентский in-flight guard; состояние из `players[].isReady` ответа | R2 §3.11 |
| Gameplay-мутации | одна in-flight (`FUmActionGate`); не ретраятся; `Concurrent` → `RefetchState()` | R2 §3.21; R7 §3 п.7 |
| Rate limits | `FUmRateLimiter` по объявленным значениям «мягко» (кнопка блокируется до окна), хотя `ThrottlerGuard` не привязан | R1 §2.11 |
| Complexity/depth | все документы ≤ depth 7; `heroes { cards }` не запрашивается (N+1); самая глубокая выборка — `hero { cards { effects { … } } }` | R1 §2.11; R5 §2.11 п.4 |

### 5.5. Обход известных дефектов бэкенда на клиенте

| Дефект (источник) | Клиентское поведение |
|---|---|
| `timeoutAt` не приходит (R3 §4.2) | Дедлайн = `combatInfo.startedAt + 30 с` по `FUmServerClock` |
| Auto-resolve без урона (R4 §2.7.4) | При `COMBAT_RESOLVE && bHasCombatInfo && !bHasDefenderCard`: атакующий → авто-`resolveCombat` через 1,5 с (если соперник не бот); защитник — кнопка «Разрешить бой» через 5 с; после `playDefense` атакующий также авто-резолвит через 1,5 с, кнопка — как fallback (G10) |
| Guard пускает атакующего резолвить в `COMBAT` до защиты (R4 §4.4) | Кнопки резолва атакующему в `COMBAT` нет (честная игра) |
| `resolvePendingEffect` в `COMBAT` ломает auto-resolve (R3 §4.12) | `FUmLegalActions`: все `Pending.*` заблокированы при `Match.Phase.Combat`; баннер показывает «после боя» (G19) |
| `GAME_OVER` не переводит `Game.status` в `FINISHED` (R2 §2.3) | `WBP_GameOver` → обязательный `leaveGame`; `WBP_Lobby` «Мои игры» с «Покинуть»; ошибка «Игра не найдена» после `leaveGame` хостом без соперника игнорируется (R2 §3.14) |
| Подписка без `decks/discardPiles` (R3 §2.11) | §5.2 (`bDecksStale` + рефетч) |
| `hero(id:<cuid>)` → `null` до деплоя правки (R6 §2.8) | `hero(id: <Fighter.name>)`; cuid ↔ name через `IdMap` из `heroList` |
| `playerJoined/playerLeft` публикуются (R2 §2.6, комментарии резолвера устарели), но событий на `isReady/heroId` нет (R2 §3.8) | Подписки `PlayerJoined/PlayerLeft/GameStateUpdated` в комнате **до** `startGame` + поллинг `game(id)` 3 с; первое `STATE_UPDATED` seq 1 — сигнал старта для гостя (R2 §3.9) |
| `turnChanged` молчит при авто-передаче хода (R4 §4.21) | Смена хода — по `CurrentTurnPlayerId/TurnCount` в дифе; событийные подписки `attackInitiated/defensePlayed/combatResolved/turnChanged` не используются |
| Prod-маскирование `UNAUTHENTICATED` (R1 §4.6) | Проактивный refresh по `exp` + класс `Opaque` |
| `logout` без guard — риск отзыва чужих refresh-токенов (R1 §4.9) | `logout` на сервер только с валидным access |
| Двери/туман/возвышенность мертвы (R4 §2.6.6-2.6.7) | UI нет; `toggleDoor` — только `um.toggledoor` в dev-консоли |
| Ranged по legacy `cell.zone` (R4 §4.1) | Подсветка по `SameLegacyZone`; при отказе сервера — тост |
| Fallback-доска 20×20 без зон (R4 §2.6.5) | Геометрия только из `boardState`; ортокамера масштабируется; ranged деградирует до смежности |
| `pass` не сбрасывает карту (R4 §4.8) | Подпись «Пропустить действие» |
| Матчмейкинг/presence неработоспособны (R2 §4.1-4.4) | `bMatchmakingEnabled=false`, `bPresenceEnabled=false`; экраны — v2 после B5 |
| Утечка чужого `drawPile`/`cardId` (R4 §4.10) | Не читаются (§5.2) |
| `heroStances` только у `alice`/`muhammad-ali` (R3 §4.18) | Кэш по `heroSlug`; `WBP_StanceBar` скрыт при пустом списке |
| `gameStateUpdated.currentTurnPlayerId: String!` (R2 §4.18) | F24 |

### 5.6. GameplayTags как язык состояний (G3)

Таксономия (нативные теги в `UmTags.h`):

```
Match.Phase.{Setup,TurnStart,ActionManeuver,ActionAttack,Combat,CombatResolve,TurnEnd,GameOver,Unknown}
Match.Turn.{Mine,Opponent}   Match.Actions.{Available,Exhausted}   Match.Role.{Attacker,Defender,None}
Match.Sync.{Live,Reconnecting,Resyncing,DecksStale}
Match.Event.Fighter.{Moved,Damaged,Healed,Defeated,Immobilized}
Match.Event.Combat.{Declared,DefenseRevealed,Resolved,AutoResolved}
Match.Event.Card.{Played,Drawn,Discarded}   Match.Event.Decks.Refreshed
Match.Event.{Turn.Changed,Actions.Changed,Pending.Added,Pending.Removed,Stance.Changed,Game.Over}
Action.{Maneuver,MoveFighter,Attack,PlayDefense,PlayScheme,ResolveCombat,EndTurn,Pass,SetStance,ToggleDoor,Pending.Move,Pending.Place,Pending.ChooseOne}
Fighter.Type.{Hero,Minion,Huge}   Fighter.Attack.{Melee,Ranged}   Fighter.Status.{Immobilized,Defeated}
Card.Type.{Attack,Defense,Scheme,Universal,Versatile,Maneuver}   Pending.Type.{Move,Place,ChooseOne}
Zone.{Blue,Green,Yellow,Red,Purple,Brown,Gray,Orange,Pink,White,Gold,Beige}
GameplayCue.Match.Fighter.{Move,Damage,Heal,Defeated,Select,Immobilized}
GameplayCue.Match.Combat.{AttackDeclared,DefenseRevealed,Resolved,Timeout}
GameplayCue.Match.Card.{Play,Draw,Discard,Boost}   GameplayCue.Match.{Turn.Changed,Stance.Changed,Game.Over,Zone.Pulse}
UI.Layer.{Game,Menu,Modal,Toast}   UI.Screen.{Boot,Login,Register,Lobby,Room,Game,GameOver,Settings}
Input.Mode.{Idle,FighterSelected,CardSelected,Maneuver,PendingMove,PendingPlace,ChooseOne,Defense,BoostPick,Busy}
Net.State.{Disconnected,Connecting,Connected,Reconnecting,Error}
Feature.{Matchmaking,Presence,VsAi,DevTools,MockBackend}
```

`UUmStateSubsystem::GetMatchTags()` возвращает контейнер текущего `PresentedState` (например, `Match.Phase.Combat + Match.Role.Defender + Match.Turn.Opponent + Match.Sync.Live`). Аффордансы кнопок — `FGameplayTagQuery` (пример: «Атака» = `ALL(Match.Turn.Mine, Match.Actions.Available, Match.Sync.Live) AND ANY(Match.Phase.ActionManeuver, Match.Phase.ActionAttack) AND NONE(Input.Mode.Busy)`), причины отказа — `WhyNot` из `FUmLegalActions`. Новый тип pending/механика = новые теги + `CUE_*`-ассет + строка в `FUmLegalActions`, без правки виджетов.

### 5.7. Таблица паритета и намеренных отличий (G13)

| Правило | Сервер | Клиент (подсветка/гейт) | Выход для игрока |
|---|---|---|---|
| Ranged-досягаемость | смежная или legacy `cell.zone` совпадает (`adjacency.service.ts:214-218`) | то же (`SameLegacyZone`) | при отказе сервера — тост с `Message` |
| Дальность `attackRange` героя/стойки | `canAttackAtRange` (только добавляет) | `DT_AttackRange`; при отсутствии строки — не подсвечивать, но **не блокировать** клик (сервер решит) | кнопка активна, отказ — тост |
| Промежуточные клетки манёвра | только `wall/obstacle`, занятость конечной (`validator.ts:235-249`, `executor:800-812`) | путь строится BFS с блокировкой живыми (строже); клетки, достижимые только «через» бойца, — `ServerWouldAllow` с пунктирной подсветкой `MI_Highlight_ServerWouldAllow` | игрок может выбрать пунктирную клетку — отправляется как есть |
| Закрытые двери в манёвре | не проверяются | не проверяются (дверей нет) | — |
| Banner | `bannerAllows` (`validator.ts:559-604`) | тот же алгоритм; неизвестный банер → разрешён | гейт мягкий: предупреждение, не блок (R5 §4.10) |
| BOOST | эффект `BOOST` из руки или `allowsAttackBoost` (`king-arthur`) | `FUmRules::BoostAllowed` | слот BOOST показывается по правилу; отказ — тост |
| `resolveCombat` атакующим в `COMBAT` | разрешено guard'ом | не предлагается | — |
| `resolvePendingEffect` в `COMBAT` | разрешено (нет guard'а) | заблокировано (G19) | баннер «после боя» |
| `pass` | тратит действие, карту не сбрасывает | то же | подпись «Пропустить действие» |
| `toggleDoor` | всегда `DOOR_NOT_FOUND` | не показывается | dev-консоль |
| Стойка по умолчанию | `default: true` или первая | то же (`heroStances`) | — |
| `movement` героя | `Fighter.movement` (дефолт 2), не контентный 3 | `Fighter.Movement` | — |
| `setStance` вне своего хода | `ActionPhaseGuard` (нет) | гейт по `Match.Turn.Mine` + action-фаза | — |

### 5.8. Dev-loop агента и таблица «задача → тулсет MCP» (G7)

| Задача | Тулсет / инструмент |
|---|---|
| Включить/проверить плагины проекта | `PluginToolset.ListEnabledPlugins`, `SetPluginEnabled` |
| Создать/изменить `WBP_*`, дерево, биндинги, компиляция | `UMGToolSet.CreateWidgetBlueprint` (parent = C++-база), `AddWidget`, `SetNamedSlotContent`, `WrapWidgets`, `BindToEventProperty`, `CompileWidgetBlueprint` |
| Glue-логика BP, родитель C++, переменные, компоненты | `BlueprintTools.write_graph_dsl`, `read_graph_dsl`, `set_parent` |
| Импорт PNG, DataTable/DataAsset из CSV/JSON | `TextureTools.import_file` (только форматы `TextureFactory`, без webp — R8 §2.9), `DataTableTools.create/import_file/add_rows/get_schema`, `DataAssetTools` |
| `ST_UI` | `StringTableTools` |
| Проверка наличия нативных тегов | `GameplayTagsToolset` |
| Материалы зон/подсветок | `MaterialTools`, `MaterialInstanceTools` |
| `L_Main`: `BP_UmGameStage`, камера, свет | `SceneTools.add_to_scene_from_class`, `ActorTools`, `PrimitiveTools` |
| Ini-настройки | `ConfigSettingsToolset` |
| PIE, скриншоты, клики, формы | `EditorAppToolset.StartPIE/StopPIE/IsPIERunning`, `SlateInspectorToolset.Snapshot/Screenshot/Click/Type/FillForm/WaitFor` |
| Логи | `LogsToolset.GetLogEntries(category="LogUmNet\|LogUmSync\|LogUmModel\|LogUmPresent")` |
| Тесты | `AutomationTestToolset.DiscoverTests/RunTests/GetTestResults` |
| Компиляция C++ из агента | `LiveCodingToolset` (спайк E0.1 — `describe_toolset`); fallback — `Build.bat UnmatchedEditor Win64 Development -Project=… -WaitMutex`; новые `UCLASS/UFUNCTION` — реинстансинг Live Coding (R8 §2.14) |
| Скрипты вне MCP | `unreal/Tools/*.mjs`, `unreal/Tools/*.ts` (Node) — introspection, генерация `UmOps.gen.h`, экспорт контента/фикстур/таблиц |

Цикл: правка C++ → компиляция (`LiveCodingToolset` или `Build.bat`) → редактор `Unmatched.uproject` открыт (порт 8124 через ~40 с) → ассеты тулсетами → `StartPIE` (с `bMockBackend=true` для UI-прогонов без бэкенда или против `localhost:3000`) → `SlateInspector` → `LogsToolset` → `AutomationTestToolset.RunTests("Unmatched.")` → коммит явными путями `--no-verify`. Ограничение: вызовы MCP сериализованы на game thread, один редактор = один сервер (R8 §2.16) — параллельные агенты делят редактор по очереди либо работают с C++ и CLI-тестами (`UnrealEditor-Cmd -NullRHI`).

### 5.9. Схема как контракт

`unreal/Ops/*.graphql` → `ops-check.mjs` (валидация против `Schema/schema.introspection.json` + генерация `UmOps.gen.h` с хешем) → spec `OpsGenerated`/`InputsWhitelist`. Снимок introspection обновляется командой `npm run schema:snapshot` при поднятом бэкенде и коммитится; расхождение схемы обнаруживается до e2e (закрывает R8 §4.10, R3 §3.16, ошибки веба с `idempotencyKey` у `joinGame` и `matchFound(userId: ID!)` — R7 §2.13 п.9-10).

---

## 6. Предпосылки на бэкенде

Приоритеты: **MVP** — без этого MVP-критерии не выполняются (или это проверка данных перед спайками); **v1** — нужно для честного онлайн-релиза; **v2** — расширения. Для каждого пункта указан клиентский обход, с которым MVP работает против текущего `HEAD`.

| # | Что нужно на сервере | Приоритет | Обход в клиенте до фикса | Источник |
|---|---|---|---|---|
| B1 | Cobble City в живой БД с валидной геометрией 6×4 и зонами (`Board.cells`), иначе партия идёт на fallback 20×20 без зон | **MVP** (данные, проверка в E0.2; заводится через админку — валидатор геометрии есть, R6 §2.7.3) | Рендер из `boardState`; ranged деградирует до смежности | R4 §2.6.5; `game-initialization.service.ts:284-289`; R5 §4.8 |
| B2 | Закоммитить/задеплоить правку `getHeroBySlug` (`OR [{id},{name}]`) — сейчас только в рабочем дереве | **MVP** (тривиально; иначе двойной путь кода в клиенте) | `hero(id:<Fighter.name>)` | R6 §2.8; `content-db.service.ts:183-189`, `git diff --stat` 4+/2- |
| B3 | Сидированные учётки для e2e (`<LOCAL_P1_EMAIL>`, `<LOCAL_P2_EMAIL>`) и стенд `docker compose` на `localhost:3000` | **MVP** | — | R6 §2.9; память проекта |
| B4 | `formatError` в production: добавить `UNAUTHENTICATED`, `FORBIDDEN`, `BAD_REQUEST` в allow-list бизнес-ошибок; подтвердить реальный `extensions.code` для `BadRequestException` | **v1** (блокер prod-релиза; на dev-стенде `NODE_ENV=development`) | Проактивный refresh по `exp`; класс `Opaque`; фолбэк «Действие отклонено» | R1 §4.6; R3 §4.9; `graphql.module.ts:73-77` |
| B5 | `logout` под `GqlAuthGuard` (без токена `user?.id === undefined` → `updateMany` без фильтра по `userId`) | **v1** (безопасность, срочно) | `logout` только с валидным access | R1 §4.9; `auth.resolver.ts:46-50` |
| B6 | Auto-resolve с реальным резолвом (урон) и/или `combatInfo.timeoutAt`; запрет резолва атакующим до защиты/таймаута | **v1** | Локальный таймер, авто-`resolveCombat` атакующим через 1,5 с, кнопка защитнику через 5 с | R4 §4.3-4.5; `combat-timeout.service.ts:273-281` |
| B7 | `gameStateUpdated.currentTurnPlayerId` сделать nullable (сейчас `String!`) | **v1** | Обработка `next{errors}` + refetch (F24) | R2 §4.18; `gameplay.dto.ts:474-475` |
| B8 | `decks/discardPiles` (или хотя бы счётчики и `attackerCard/defenderCard`) в `gameStateUpdated` | **v1** | `bDecksStale` + рефетч (§5.2) | R4 §4.11 |
| B9 | Фильтровать чужой `drawPile` и `cardId`/`bannerName` чужих карт в `filterPrivateData` | **v1** (честность) | Клиент не читает | R4 §4.10; `game-state.service.ts:494-541` |
| B10 | `resolvePendingEffect`: отклонять в `COMBAT` или не давать auto-resolve пропускать срабатывание по seq | **v1** | Гейт G19 | R3 §4.12 |
| B11 | `GAME_OVER` → `Game.status = FINISHED`, `winnerId`, `endedAt` | **v1** | Обязательный `leaveGame` из `WBP_GameOver` | R2 §2.3, §4.7 |
| B12 | Экспорт `attackRange`/стоечных модификаторов через GraphQL (например, `heroAbilityConfig(heroSlug)`), чтобы снять ручную `DT_AttackRange` | **v1** (желательно) | `export-ability-table.ts` + spec `AttackRangeSync` | R4 §3.6 |
| B13 | Матчмейкинг/presence: `GqlAuthGuard`, `user.id` вместо `user.userId`, `MatchmakingGuard` через `GqlExecutionContext`, создание `GamePlayer` при матче, `presenceUpdated` как AsyncIterator | **v2** | `bMatchmakingEnabled=false`, `bPresenceEnabled=false` | R2 §4.1, §4.3, §4.4 |
| B14 | Публичные `bannerName`, `attackType`, `sidekicks[]`, реальный `movement` в контентных `Hero`/`Card` | **v2** | В партии — из состояния; в комнате — без подсказок banner | R5 §4.6, §4.10, §4.16 |
| B15 | `combatSummary`/`manualEffects`/`effectText` в `GameMutationResult` | **v2** | Итоги боя по дифу `health`; лог из текста карт | R4 §4.12 |
| B16 | Query `gameByCode` для инвайтов по коду | **v2** | Deep-link по `gameId` | R2 §4.16 |
| B17 | `Card.effects[].timing` в публичном API сериализуется вне enum | **v2** | Не запрашивать `timing` | R5 §4.1 |
| B18 | `clearContentCache` под guard; инвалидация Redis-кэша контента при admin-мутациях | **v2** | TTL 1 ч + `max(updatedAt)`; `hero(id)` при входе в партию всегда | R6 §4.2-4.4 |
| B19 | Фантомный сайдкик «Unknown» у героев без сайдкиков (данные) | **v1** (проверить в E0.2; MVP-герои не затронуты) | Каталог переживает `MINION` «Unknown» | R5 §4.5 |
| B20 | TLS/`wss://` и reverse-proxy для production (не найдено в источниках) | **v1** (релиз) | `ws://`/`http://` на dev-стенде; `wss+insecure` для self-signed | R1 §3 п.2; R8 §3.1 п.8 |

---

## 7. Отвергнутые альтернативы

| Альтернатива | Почему отвергнута |
|---|---|
| **Предикция + зеркало правил (К2)** | Ответ мутации уже несёт полный `state`, production-веб оптимистику не использует (R7 §1 п.1, §2.8) — предикция экономит один RTT в пошаговой игре; платой были бы модуль-зеркало, предиктор, паритет-харнесс и постоянный дрейф от `game-engine` (10 из 12 последних коммитов правят движок); для MVP-пары предикция `advanceTurn` невозможна (turn-start урон Medusa, R4 §2.11.2); оценка 66 ч/д против 43–52 |
| **`GameFeatures`/`ModularGameplay`/`DataRegistry` (К3)** | Все `IsBetaVersion: true` (R8 §2.13); контент героя приходит данными с сервера, локально нужны только текстуры — достаточно `UPrimaryDataAsset` + `AssetManager` + `UPrimaryAssetLabel` |
| **`GameplayAbilities` ради cue (К3)** | Плагин не beta, но без ASC требует `InitGlobalData`, AR-скана, тегов строго под `GameplayCue.*` и `GameplayCueNotifyPaths`; собственная шина `UUmMatchCueSubsystem` — ~100 строк и без скрытых зависимостей; корень тегов `GameplayCue.Match.*` сохранён для возможной миграции |
| **10+ плагинов-модулей (К3)** | Для одного разработчика — лишняя стоимость сборки/навигации; 4 модуля дают ту же границу «модель ↔ сеть ↔ игра» |
| **Три уровня `L_Boot/L_Menu/L_Game` (К1)** | Один `L_Main` снимает ловушку F17 и класс проблем с `OpenLevel` при живом WS; доска спавнится субсистемой |
| **Ручной `FromJson` для DTO (К2) / camelCase-`UPROPERTY` (К1)** | Ложная посылка — F11 |
| **`PingPongInterval=0` + прикладной ping 25 с (К2)** | Не удовлетворяет keep-alive сервера — F9 |
| **UI «BLIND BOOST» (К2)** | Мутации нет — F10 |
| **`BAD_USER_INPUT → ClientBug` (К3)** | Скрывает от игрока причину отказа — F6 |
| **`DataRegistry` как фасад контента даже с fallback (К3)** | Два пути кода за переключателем ради Beta-плагина; `AssetManager` покрывает задачу |
| **Событийные подписки `attackInitiated/defensePlayed/combatResolved/turnChanged` как триггеры анимаций** | Payload только `{phase, turnCount, currentTurnPlayerId}`; `turnChanged` молчит при авто-передаче (R4 §3.3); диф снапшотов даёт всё (К1 §3.5.2) |
| **`eventsSince` для догоняния** | Без состояния, без ходов ИИ и auto-resolve, асинхронно (R3 §4.10) |
| **MVVM-плагин для биндинга HUD** | Beta (R8 §2.6); `FieldNotify`-делегаты в `UUmGameHudModel` достаточно |
| **CommonUI ↔ EnhancedInput интеграция** | Страница Experimental, «not recommended to ship» (R8 §2.7); EI — только для сцены |
| **Git LFS не для всех `.uasset`, а хранение текстур вне репозитория** | Решение отложено — открытый вопрос §8 п.5; по умолчанию LFS |
| **Сторонние GraphQL-плагины** | Не существуют/непригодны (R8 §2.5) |
| **Рантайм-декодер WebP (сторонние плагины) в MVP** | Не проверены в 5.8 (R8 §2.9); офлайн-конвертация покрывает MVP и v1 |

---

## 8. Открытые вопросы для владельца продукта (только блокирующие)

1. **Протокол авто-резолва боя.** Подтвердить, что до серверного фикса B6 клиент атакующего сам вызывает `resolveCombat` через 1,5 с после `COMBAT_RESOLVE` (auto-resolve без урона иначе оставляет бой висеть), а защитник получает кнопку через 5 с. Влияет на E4/E7 и на приоритет B6.
2. **Формат ошибок на стенде MVP.** MVP принимается на `NODE_ENV=development` (dev-формат ошибок, как сейчас в `docker-compose.yml:44`) или обязан работать в production-формате (тогда B4 — MVP-блокер, а не v1)?
3. **Геометрия Cobble City в БД (B1).** Кто и когда заводит 6×4 с 5 зонами через админку до спайка E0.2 — без этого MVP играется на 20×20 без зон, и ranged-механика Medusa не демонстрируется.
4. **Основная мутация движения в MVP.** Подтвердить `maneuver` (добор + все бойцы + BOOST, по правилам Unmatched) как основной способ с `moveFighter` как «быстрым ходом» — веб-клиент использует только `moveFighter` (R7 §4 п.4); это определяет UX `WBP_ManeuverBar`.
5. **Хранилище ассетов UE.** Git LFS для `unreal/Unmatched/Content/**` (≈180 МБ cooked-текстур при полном контенте, R9 §3 п.10) или внешнее хранилище/Perforce? Нужно до первого коммита текстур в E0.5.
6. **Мобильная раскладка: MVP или v1.** Хуки `Desktop/Mobile` закладываются сразу (G5), но содержание bottom-sheet и целевые разрешения нигде не специфицированы (R9 §4.10). Если mobile входит в MVP-демо — нужна спецификация до E7.
7. **VS_AI в MVP.** Режим против бота даёт второго игрока без второго человека и уже требует буферизации бурстов (R4 §2.16), но нуждается в сидированном `ai@unmached.local` (R2 §3.12). Включать в MVP (+≈2 ч/д) или оставить в v1?

---

## 9. Фаза 0 и дорожная карта (кратко; детали — в планах следующей фазы)

### 9.1. Фаза 0 — блокирующие спайки (G1), ≈ 5 ч/д

| # | Спайк | Критерий приёмки |
|---|---|---|
| E0.1 | Скелет `Unmatched.uproject` (4 модуля, плагины, ini §3.5, порт 8124), `Build.bat`; `describe_toolset(LiveCodingToolset)`; spec `Unmatched.Model.DtoRoundTrip` | Редактор + MCP `:8124`; компиляция из агента или зафиксированный fallback; `DtoRoundTrip` зелёный (camelCase ↔ PascalCase) |
| E0.2 | Живой WS: `graphql-transport-ws` handshake, `connection_init/ack`, `gameStateUpdated`, **подписка idle > 5 мин** (авто-pong LWS на серверные ping-фреймы); снимок introspection; `board(id:"Cobble City")`, `hero(id:"Medusa"){cards{imageUrl}}`, `heroes{fighterType}` (фантом «Unknown») | Подписка жива > 5 мин без `terminate()`; `schema.introspection.json` в репозитории; факты B1/B19/формат URL зафиксированы |
| E0.3 | Cue-шина: `UUmMatchCueSubsystem` + `DA_UmCueRegistry` + один `CUE_Fighter_Move` через MCP | Событие `Match.Event.Fighter.Moved` проигрывает tween и возвращает длительность |
| E0.4 | `UUmHeroDefinition` + `PrimaryAssetTypesToScan` + `PAL_Core` | `UAssetManager::GetPrimaryAssetIdList("UmHero")` возвращает `medusa`, `king-arthur` |
| E0.5 | `export-content.mjs` (2 героя + Cobble City, webp→png) + `TextureTools.import_file` + `DT_CardArt` | Текстуры и таблица в проекте; решение по хранилищу (§8 п.5) |

### 9.2. MVP — Medusa vs King Arthur (после фазы 0)

| # | Эпик | Содержание | ч/д |
|---|---|---|---|
| E1 | `UmNet` | HTTP-транспорт + фейк, классификатор, лимитер, retry, `UUmAuthSubsystem` (refresh, single-flight, `IUmSecureStore` DPAPI/AES), спеки | 5 |
| E2 | WS | `FUmGraphQLWsClient`, backoff, переподписка, ping/pong, `Reconnect` после refresh, спеки на фейке, живой тест | 4 |
| E3 | `UmModel` | UENUM/DTO/wire-модель, парсер + фикстуры, диф, `Ops` + генерация + `InputsWhitelist`, геометрия/правила/`LegalActions`/`WhyNot`, теги, `export-rules-fixtures.mjs` + `RulesParity`, `export-ability-table.ts` + `AttackRangeSync` | 6 |
| E4 | State + Content | `UUmStateSubsystem`, `FUmGameSnapshotStore` (§5.2), таймеры/авто-резолв, `EnterRoom/EnterGame`, реконнект-resync, `UUmContentSubsystem` (3 провайдера, `IdMap`), `UUmImageCacheSubsystem`, `UUmGameHudModel` | 6 |
| E5 | Экраны меню | `WBP_Boot/Login/Register/Lobby/CreateGameDialog/JoinByIdDialog/Room/HeroPicker`, FSM экранов, `EnsureRootLayout` | 4 |
| E6 | Презентация | `AUmGameStage` (ISM, камера, трассировка), `AUmFighterActor`, подсветки (в т. ч. `ServerWouldAllow`), input-FSM, очередь воспроизведения, `PresentedState`, cue-набор MVP | 6 |
| E7 | Game HUD | `WBP_GameHUD` (Desktop/Mobile switcher) и дочерние виджеты, `WBP_CombatPanel`, `WBP_BoostPicker`, pending/choose-one (с гейтом COMBAT), стойки, game over, тосты/reconnect overlay, `bDecksStale`-визуализация, `WhyNot`-тултипы | 10 |
| E8 | Контент MVP | `DT_HeroArt/BoardArt/AttackRange/ServerErrorMap`, `ST_UI` en/ru, `DA_Hero_medusa/king-arthur`, `DA_Board_cobble-city`, placeholder-текстуры | 3 |
| E9 | Тесты | `UUmMockBackend` + SlateInspector-сценарии, E2E-набор, функциональные тесты, кросс-проверка с веб-клиентом | 4 |
| E10 | Полировка | UX ошибок, «Мои игры»/освобождение слота, локализация, настройки, стабилизация | 4 |
| | **Итого MVP** | | **52 ч/д** (+ 5 ч/д фазы 0 = 57; коридор 50–65; пересмотр после фазы 0) |

Вертикальный срез «первая партия» (≈ день 18): E0 → E1 → E3 → E2 → E4 → E6 (доска без анимаций) → минимальный `WBP_GameHUD` (рука, атака/защита/резолв/конец хода) → `WBP_JoinByIdDialog` вместо лобби; вторым игроком — веб-клиент. v1/v2 — по К1 §7.2-7.3 с поправками: `FUmCombatPreview` и `DT_HeroCombatMods` — v1; матчмейкинг/presence — v2 после B13; мобильная раскладка — v1 (хуки уже в MVP).

---

## Приложение A. Источники

- Кандидаты: `docs/unreal/_design/candidate-1.md` (§1.5, §2.1-2.7, §3.2-3.8, §3.11, §5-§8), `candidate-2.md` (§2.4, §3.3-3.5, §3.8.3, §4.5, §5.2, §7.4, §8), `candidate-3.md` (§2.2, §3.2.3, §3.2.6, §3.4.3, §3.5.1, §3.6.1, §3.7.2, §3.9, §3.10, §4.4, §5.2, §6.1-6.3, §7, §8, Приложение A).
- Вердикты трёх судей (оценки, `must_graft`, `fatal_flaws`) — переданы во входных данных задачи.
- `docs/unreal/00-mcp-verification.md` — полностью.
- Research: `R1-transport-auth.md` (§1, §2.1-2.15, §3, §4), `R2-lobby-matchmaking-internals.md` (§1, §2.6, §3, §4), `R3-game-api-schema.md` (§1-§4), `R4-engine-mechanics.md` (§1-§4), `R5-content-cards-heroes.md` (§1, §3, §4), `R6-admin.md` (§1, §3, §4), `R7-web-client-port-catalog.md` (§1-§4), `R8-ue58-capabilities.md` (§1-§4), `R9-assets-design-system.md` (§1, §3, §4).
- Исходники UE 5.8.2 (перепроверено напрямую): `Source/Runtime/Engine/Classes/Engine/Engine.h:807`; `Config/BaseEngine.ini:12-13,132`; `Config/BaseGame.ini:254-255`; `Source/Runtime/EngineSettings/Classes/GameMapsSettings.h:203`; `Source/Runtime/Engine/Classes/Engine/AssetManagerTypes.h:137-178`; `Source/Runtime/Engine/Classes/Engine/PrimaryAssetLabel.h:12`; `Plugins/Runtime/GameplayAbilities/Source/GameplayAbilities/Private/GameplayCueSet.cpp:17,270,407,414,438,457-460`; `Plugins/Runtime/GameplayAbilities/Source/GameplayAbilities/Public/AbilitySystemGlobals.h:69,113,274-280,361`; `Plugins/Runtime/GameplayAbilities/GameplayAbilities.uplugin:13,15`; `Source/Runtime/JsonUtilities/Private/JsonObjectConverter.cpp:601-609,1338-1339,1360-1367`; `Source/Runtime/Core/Public/Containers/UnrealString.h.inl:2128-2132`; `Plugins/Experimental/Toolsets/LiveCodingToolset/LiveCodingToolset.uplugin`; `Source/Runtime/Online/WebSockets/Private/Lws/LwsWebSocketsManager.cpp:192-194,528-531`; `Plugins/Runtime/CommonUI/Source/CommonUI/Public/{CommonGameViewportClient.h,CommonVisibilitySwitcher.h:15}`; `Plugins/Runtime/CommonUI/Source/CommonInput/Public/CommonInputSettings.h:82,114`; `Source/Runtime/GameplayTags/Public/NativeGameplayTags.h`; `Source/Runtime/GameplayTags/Classes/GameplayTagContainer.h:464`; `Source/Runtime/FieldNotification/Public/INotifyFieldValueChanged.h:22`; `Plugins/Experimental/ModelContextProtocol/Source/ModelContextProtocolEngine/Public/ModelContextProtocolSettings.h:38-46`.
- Бэкенд (перепроверено напрямую): `backend/src/games/services/combat-timeout.service.ts:220,260-282`; `backend/src/games/game-state.service.ts:170,215`; `backend/src/games/resolvers/game-actions.resolver.ts:72,170,174,185,222-226`; `backend/src/games/resolvers/game-subscription.resolver.ts:44-64`; `backend/src/games/dto/gameplay.dto.ts:470-480`; `backend/src/graphql/graphql.module.ts:68-92`; `backend/src/game-engine/models/fighter.model.ts:80-85`; `backend/src/game-engine/validators/game-rules.validator.ts:559-604`; `backend/src/game-engine/abilities/ability-config.ts:365-413`; `backend/src/game-engine/abilities/heroes/ms-marvel.handler.ts:22,62,75`; `backend/src/game-engine/abilities/heroes/arthur.handler.ts:23,30`; `backend/src/games/services/ai-turn.service.ts:24`; `backend/src/games/game.service.ts:31,106-107`; `backend/src/games/services/game-initialization.service.ts:279-290`; `backend/src/auth/auth.resolver.ts:46-50`; `backend/src/content/content-db.service.ts:183-189` (рабочее дерево, `git diff --stat`: 4 добавления / 2 удаления); `scripts/sync-card-assets.mjs:23-31`; `git log --oneline -12`.
- Хост MCP: `C:/Users/ren/Documents/Unreal Projects/MCPProject/MCPProject.uproject`, `…/Config/DefaultEditorPerProjectUserSettings.ini` (порт 8123); `~/.claude.json` → `mcpServers.unreal-mcp = { type: http, url: http://127.0.0.1:8123/mcp }`.

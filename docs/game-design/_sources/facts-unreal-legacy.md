# Приложение: карта прежних планов Unreal (docs/unreal/)

Статус: `ПЛАН, не реализация` (материалы 2026-09-02; каталога `unreal/` в корне репо нет; код существует только как сниппеты в docs/unreal/snippets/). Использовать как входные идеи, проверяя поимённо по `docs/backend-api/`.

## Карта источников

- **00-mcp-verification.md** — верификация Unreal MCP: плагин UE 5.8 Experimental, Streamable HTTP 127.0.0.1:8123/mcp, хост — сторонний MCPProject (UE 5.8.2); 55 тулсетов; ограничения (нет «создать C++ класс» через MCP).
- **01-architecture-decision.md** (812 стр., главный ADR) — UE 5.8.2, Win64 MVP, тонкий server-authoritative C++-клиент поверх HTTP + graphql-transport-ws; 4 модуля UmNet/UmModel/UmClient/UmEditor; отвергнуты GAS/MVVM/предикция/Lyra-стиль; 23 «графта» (G1-G23), 24 фатальные ошибки кандидатов, 12 «фактов контракта», реестр серверных предпосылок B1-B20; roadmap: фаза 0 (5 спайков) → MVP 52 ч/д, Medusa vs King Arthur.
- **02-project-setup-and-phase0.md** (1171 стр.) — процедура создания unreal/Unmatched/Unmatched.uproject: модули, Build.cs, Target.cs, Config/*.ini (порт MCP 8124 и др.), 5 спайков фазы 0, git/LFS, Node-инструменты.
- **05-ui-screens.md** (374 стр.) — CommonUI-каркас: 4 слоя UI.Layer.{Game,Menu,Modal,Toast}, FSM экранов по тегам UI.Screen.*, реестр виджетов WBP_Boot/Login/Lobby/Room/HeroPicker/GameHUD + ~15 дочерних, UUmGameHudModel, аффордансы через GameplayTagQuery + WhyNot, дизайн-токены DA_UmTheme, UI-тесты SlateInspector.
- **06-board-and-presentation.md** (1029 стр.) — доска строится ТОЛЬКО из boardState (клетка 100×100 uu), UInstancedStaticMeshComponent, камера ортографическая сверху (Pitch −90), OrthoWidth = max(W,H)·100·1.15, зум ±20 %, панорамирование; AUmFighterActor — плоскость с мини-артом; подсветки-«советчики», FUmInputStateMachine, очередь PresentedState ≠ Current, cue-шина UUmMatchCueSubsystem (тайминги веба как референс: tween 280 мс/клетка, урон 900 мс).
- **07-content-and-assets-pipeline.md** (999 стр.) — 4 пространства идентификаторов; таблица дефектных полей публичного контента; фасад UUmContentSubsystem Baked (UPrimaryDataAsset) → Runtime → Placeholder; UUmImageCacheSubsystem (LRU 256); офлайн-конвейер export-content.mjs: WebP→PNG (UE 5.8 нативно НЕ декодирует WebP), карты 512×716, аватары 512×512; кэш Saved/UmContent, инвалидация по contentSummary.
- **08-gameplay-flows.md** (1014 стр.) — 20 потоков F1-F20; правила: одна in-flight мутация (FUmActionGate), мутации не ретраятся, дедлайн защиты локально startedAt+30 с; обходы дефектов: авто-resolveCombat атакующим через 1,5 с, обязательный leaveGame после GAME_OVER, гейт resolvePendingEffect в COMBAT.
- **09-testing-qa-and-devloop.md** (1004 стр.) — пирамида L0-L6 (статика контракта в Node → спеки на фейках → UUmMockBackend → функциональные → SlateInspector UI → E2E против localhost:3000 → кросс UE↔веб); фикстуры пар medusa-vs-king-arthur и др.; CLI-прогон Automation RunTests.
- **GDD-START-PROMPT-RU.md** — промпт-обёртка текущего дизайн-процесса.
- **_design/** — 3 кандидата архитектуры (победил «тонкий server-authoritative клиент»).
- **_research/** — 9 отчётов R1-R9 (входы ADR), вкл. R9: инвентаризация ассетов 388 файлов ≈229 МБ, три несогласованных слоя дизайн-токенов.
- **snippets/** — «бумажная» реализация: .uproject, Config, Source UmNet/UmModel/UmClient/UmEditor, graphql-операции, Tools. В сборке не существует.

## Ключевые предложения старых планов

- Первая партия MVP: **Medusa vs King Arthur на Cobble City**, приватная комната, 2 UE-клиента или UE+веб.
- Контент печь только для 2 героев; сайдкики из GameState.fighters (MINION); фантомный сайдкик «Unknown» (B19).
- Доска 3D из boardState (НЕ из контентного Board.cells); клетки 100×100 uu; 12 материалов зон; fallback 20×20 без зон; двери/туман/возвышенность не рисуются.
- Клиент: 100 % логики на C++, UI/анимации — Blueprint/UMG через MCP-тулсеты; CommonUI, EnhancedInput; без сторонних плагинов (свой GraphQL поверх HTTP/WebSockets/Json).
- Экраны: FSM по тегам UI.Screen.{Boot,Login,Register,Lobby,Room,Game,GameOver,Settings}; персистентный уровень L_Main; раскладка HUD как веб-финал (оппонент TL, фаза TC, рука оппонента TR, борд центр, игрок BL, рука BC 7 слотов, колода/сброс BR, инспектор справа).
- Камера: ортографическая сверху, зум ±20 %, панорамирование. **Отклонено решением D-13** (диорама + фиксированный перспективный угол).
- Привязка ассетов: слаг-функции HeroSlug/AssetSlug → имена T_Card_<heroSlug>_<cardSlug>_EN|RU, DA_Hero_<slug>, ключи <heroSlug>:<cardSlug>; cuid↔имя из heroList/boardList; офлайн WebP→PNG; истина чисел — GameState.

## Сверка с актуальными docs/backend-api

Покрыто бэкендом теперь официально: весь транспорт/auth/лобби/игровое API/стойки/VS_AI/контент; матчмейкинг и presence описаны как рабочие (старые планы считали их неработоспособными — устаревшее допущение; остался пережиток: matchFound-резолвер «без guard»).

Не закрыто нигде (клиентские/открытые пункты): decks/discardPiles в gameStateUpdated (B8); currentTurnPlayerId: String! (B7); экспорт attackRange через GraphQL (B12 — но значения задокументированы в 05/08); combatSummary/manualEffects (B15); gameByCode (B16); публикация playerJoined/playerLeft в игровой фазе.

## Противоречия старых планов актуальным докам (проверять поимённо)

1. Матчмейкинг: старые — «за флагом bMatchmakingEnabled до B13»; актуально — рабочий флоу описан.
2. combatInfo.timeoutAt: старые — «никогда не выставляется, считать локально»; актуальная 04 — поле есть в примерах, рекомендуется для таймера защиты. Проверить на живом сервере.
3. Скаляры: старые требуют Float для since/sequenceNumber/turnCount/seatOrder/version; актуальная 07 — Int/Int!. Критично для парсера; проверить introspection.
4. eventsSince: старые отвергают для восстановления; актуальные 04/03 рекомендуют именно его в реконнекте.
5. Оптимистика: 04 допускает оптимистичное применение своего хода; старые запрещают. Философское расхождение — решение в 08.
6. WS-коды: наборы старых (4400/4401/4406...) и новых (4403/4408/4409) не совпадают.
7. Фазы: старая модель из 8 фаз совпадает с 04; пример «MAIN» в 06 — ошибка дока.
8. Счётчики контента: термины «84 героя» (heroList с сайдкиками) vs «29 героев реестра» (ABILITY_CONFIGS) vs «70 героев контента» — не смешивать.
9. hero(id) по cuid (B2): статус не зафиксирован; безопасный обход — hero(id: <имя>) + IdMap.
10. Таблица «дефектных полей» из старого 07-плана в новых доках не маркирована — перепроверять, не переносить вслепую.

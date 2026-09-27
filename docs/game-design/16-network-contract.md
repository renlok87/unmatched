# 16. Сетевой контракт игры (snapshot / WS / since recovery)

> Версия контракта: **`unmatched-net/1`** (введён S07, GD-025..GD-027).
> Источник истины — код бэка; этот документ описывает обязательства сервера
> и клиента. Ломающие изменения требуют новой версии контракта.

## 1. Модель состояния и `sequenceNumber`

- Игровое состояние — единый документ `GameState` (Redis + Postgres
  `gameState.state`), сериализуемый в JSON.
- `sequenceNumber` — **строго монотонный** счётчик: `+1` на каждую успешную
  мутацию (ход, атака, защита, резолв, таймаут-резолв). Никаких дельт и
  внеочередных инкрементов.
- Запись состояния — только под distributed lock `game:${gameId}` c
  optimistic-проверкой версии. Конкурентные записи (защита vs таймаут vs
  ручной резолв) дают ровно один исход и один инкремент.
- Клиент применяет входящие состояния по правилу:
  `incoming.sequenceNumber < local` → игнор (устаревшее);
  `== local` → merge-семантика (идемпотентность, ACC-011);
  `> local` → применить (gap допустим — снапшот самодостаточен).

## 2. Полный снапшот vs частичная проекция

| Канал | Транспорт | Тело |
|---|---|---|
| `query gameState(gameId)` | HTTP | `{ state: JSON }` — полный **viewer-projected** снапшот |
| `subscription gameStateUpdated(gameId, since)` | WS | событие с полным **viewer-projected** снапшотом того же формата |
| `query eventsSince(gameId, sinceSequence)` | HTTP | журнал действий (НЕ состояние) |

- **Snapshot** — самодостаточен: клиент может перестроить весь UI без
  истории. Всегда полный набор полей.
- **Проекция события** — сервер отправляет полный projected-снапшот, но
  клиент ОБЯЗАН применять merge-семантику (не обнулять поля, которых нет во
  входящем теле): фронтовый `applyWireState` мержит `decks`/`discardPiles`.
  Контракт допускает частичные тела — клиент не имеет права ожидать все поля.
- Viewer-проекция (`GameStateService.filterPrivateData(state, viewerId)`)
  применяется единообразно в HTTP query/mutation, WS-событиях и
  барьер-снапшоте. Отдельных «админских» или «тестовых» тел нет.

## 3. Семантика `since`

- `since` — `sequenceNumber`, который клиент уже имеет (НЕ timestamp).
- `eventsSince(gameId, sinceSequence)` возвращает **журнальные** записи с
  `sequenceNumber > since`; входные данные мутаций (`input`) видны только
  автору действия. `lastSequence` — хвост журнала.
- **Replay не обещается**: подписка не восстанавливает события, случившиеся
  до её установки. Свежесть состояния гарантируется барьер-снапшотом (ниже):
  если сервер ушёл дальше `since`, клиент получает актуальный снапшот, а не
  пропущенные события.

## 4. Connection barrier (GD-027 / ACC-011+012)

Окно «HTTP-снапшот взят, WS ещё не установлен» закрывает сервер:

```
withSnapshotBarrier(gameId, since, upstream):
  1. firstUpstream = upstream.next()      // PubSub-подписка регистрируется
                                          // НЕМЕДЛЕННО (subscribeAll ленив:
                                          // срабатывает на первом next())
  2. state = loadState(gameId)            // параллельно с подпиской
     if since == null || state.sequenceNumber > since:
       yield STATE_UPDATED(state)         // барьер-снапшот
     loadState NotFound (лобби-фаза) → снапшот пропускается, только live
     иной отказ loadState → лог + проброс (upstream освобождается)
  3. yield firstUpstream, затем live-события
```

Гарантии:
- **Нет пропуска**: мутация, случившаяся между HTTP-снапшотом и установкой
  подписки, приходит либо барьер-снапшотом (уже с новым seq), либо
  live-событием. Шаг 1 критичен: `PubSubAsyncIterableIterator`
  (graphql-subscriptions v3) подписывается лениво — `next()` до `await`
  loadState, иначе события за время загрузки терялись бы.
- **Нет дублирования**: то же состояние может прийти дважды (HTTP + барьер +
  live одного seq) — клиентский seq-guard (`<` → игнор, `==` → merge)
  сворачивает повторы. Сервер дедупликацию не обещает.
- Подписка без `since` (первое подключение) всегда стартует со снапшота.
- **Ранняя отписка**: барьер — ручной async-iterator (не генератор): вызов
  `return()` потребителя во время ожидания `firstUpstream` немедленно
  отпускает underlying-подписку (`upstream.return()`), а висящий `next()`
  завершается `done` через гонку с сигналом отписки. PubSub-итератор сам
  in-flight `next()` не отменяет — гонка закрывает это ограничение без
  утечки подписки при тишине.
- **Отказы loadState не глотаются**: `NotFoundException` = валидное отсутствие
  состояния (лобби-фаза) → live-only поток; любой иной отказ (DB/Redis)
  логируется, пробрасывается в подписку и освобождает upstream —
  live-only поток при genuine outage лгал бы клиенту о свежести.

**Named-подписки барьера НЕ имеют.** `attackInitiated`, `defensePlayed`,
`combatResolved`, `turnChanged`, `playerJoined`, `playerLeft`, `gameEnded` —
тонкие CUE-события без снапшот-барьера: события в окне «HTTP-снапшот взят,
WS ещё не установлен» для них теряются и не восстанавливаются. Клиент НЕ
вправе строить состояние или полноту картины на named-событиях — источник
истины и восстановления состояния только `gameStateUpdated` + HTTP query.
Named-события — вспомогательные CUE (анимации/звук), отсутствие CUE не
нарушает контракт (это же правило наследует UE-спринт GD-028).

## 5. Приватность (GD-025 / ACC-009+018)

Матрица viewer-проекции до легитимного reveal (резолв боя = первый `pause()`
`executeResolveCombat`, пишет `combatResolutionProgress`):

| Поле | Атакующий | Защитник | Spectator |
|---|---|---|---|
| Своя рука | полностью | полностью | — (нет доступа) |
| Чужая рука | плейсхолдеры `hidden-*` без личин | плейсхолдеры | — |
| Порядок/личины колод (`drawPile`, `topCard`) | скрыты (только count) | скрыты | — |
| Своя committed-карта боя (значение, id) | видна | видна | — |
| Чужая committed-карта боя | скрыта (attackValue/attackerCardId вырезаны) | скрыта (defenseValue/defenderCardId) | — |
| Публичный сброс (discard) | полностью | полностью | — |
| Raw persisted/Redis state | никогда не отдаётся | никогда | — |
| Журнал `eventsSince` `input` | только свои действия | только свои | — |

После reveal обе стороны видят значения и личины обеих карт. Все 8 подписок
(`gameStateUpdated`, `attackInitiated`, `defensePlayed`, `combatResolved`,
`turnChanged`, `playerJoined`, `playerLeft`, `gameEnded`) и
`eventsSince` гейтятся участием (`isParticipant` по `gamePlayer`):
неучастник получает `ForbiddenException` — spectator-режима чтения
состояния в контракте нет.

## 6. Таймауты боя (GD-026 / ACC-010)

- `combatInfo.timeoutAt` — персистентный дедлайн ТЕКУЩЕЙ стадии:
  `COMBAT` → окно защиты `DEFENSE_TIMEOUT_SECONDS = 30`;
  `COMBAT_RESOLVE` → окно резолва `RESOLVE_TIMEOUT_SECONDS = 10` (после
  защиты).
- BullMQ delayed job (очередь `combat-timeout`, задача `auto-resolve`, stage
  `DEFENSE|RESOLVE`) персистентна в Redis; при рестарте
  `CombatTimeoutService.onModuleInit → recoverScheduledWork()` досматривает
  истёкшие дедлайны и переназначает будущие, а затем повторяет это periodic
  sweep-ом каждые 60 с: transient-отказ очереди (enqueue-failure при
  атаке/защите) и исчерпание round-cap дрейна чинятся БЕЗ рестарта процесса.
  Легаси-состояния без `timeoutAt` получают дедлайн от `startedAt`.
- Таймаут-финализация идёт **тем же** `executeResolveCombat({systemInitiator:
  true})`, что и ручная защита: идемпотентность, один инкремент seq, одна
  audit-запись (`reason: defense-timeout | resolve-timeout`).
- Ранний системный резолв запрещён (`Deadline has not expired`); атакующий
  не может закрыть окно защиты (`Defender has not responded yet`); поздняя
  джоба после защиты/резолва — no-op. Часы инъектируются (`service.now`).

### 6.1 Серверная прогрессия запаузенных выборов (mid-combat drain)

Истёкший дедлайн при непустой очереди `pendingEffects` (бой запаузен на
BOOST/mandatory-эффекте, оба клиента офлайн) больше не зависает:
`CombatTimeoutService.processAutoResolve` циклом «дрен → системный резолв →
дрен новых пауз» доводит бой до исхода. Каждый шаг очереди идёт ТОЛЬКО через
production pending-резолверы (`executeDeclinePendingEffect` /
  `executeResolvePendingEffect`) — эффекты не изобретаются, очередь вручную
не чистится; каждый шаг легален, даёт собственный `+1` seq, публикацию
`STATE_UPDATED` и audit `CARD_PLAYED {action: autoResolveChoice}` БЕЗ id
карт (приватность руки/порядка колоды). Финальный исход — один: одна
`COMBAT_RESOLVED` публикация и одна audit-запись.

Детерминированные фолбэки обязательных выборов (владелец офлайн;
`GameActionExecutorService.buildSystemPendingFallback`):

| Тип | Фолбэк | Приватность |
|---|---|---|
| `BOOST_CHOICE` (optional) | auto-decline | карта-буст не тратится |
| `CHOOSE_ONE` | `optionIndex: 0` на каждом шаге multi-step (chooseCount>1 снимает опцию за шаг, id pending сохраняется) | — |
| `TARGET_FIGHTER` | первый живой из допустимых целей | — |
| `DISCARD_CARDS` | первые `value` карт руки в хранимом порядке | сброс публичен по правилам; порядок колоды не раскрывается |
| `DECK_TOP_PICK` PICK | первые `value` из `revealedCards` (порядок reveal) | порядок reveal уже открыт эффектом |
| `DECK_TOP_PICK` ORDER | тождественная перестановка | порядок колоды не меняется и не раскрывается |
| `MOVE` | нулевой шаг (остаться на месте — легальный резолв «up to N») | — |
| `PLACE` / `CHOOSE_SPACE` | первая свободная проходимая клетка (row-major), удовлетворяющая зонным/смежным ограничениям (stage 1 → зона named-бойца, stage 2 → смежная с anchor) | — |

Прогресс шага дрейна: голова очереди сменилась ИЛИ multi-step pending
продвинулся при сохранённом id (`CHOOSE_ONE` chooseCount/options,
`CHOOSE_SPACE` stage 1→2, `DECK_TOP_PICK` PICK→ORDER). Полное отсутствие
изменений той же головы = no-op резолвера → блокер (защита от зацикливания);
дополнительно потолки: 32 шага на один дрен и 8 раундов «дрен → резолв» на
один processAutoResolve.

Round cap (honest open gate): если после 8 раундов бой всё ещё запаузен на
выборе, `processAutoResolve` НЕ публикует `COMBAT_RESOLVED`, НЕ пишет
audit исхода и возвращает `success: false` с причиной
`Auto-resolve round cap reached with pending choices; combat left open for
recovery sweep`. Каждый пройденный шаг легален и засейвлен; periodic
recovery sweep (60 с) снова входит в процесс по персистентному дедлайну и
дренирует дальше — фальшивой финализации открытого боя не бывает.

Блокеры (choice остаётся за игроком, очередь нетронута, `success: false`
с причиной `Cannot auto-resolve pending choice: …`): mandatory
`BOOST_CHOICE` (выбор боевой карты за игрока небезопасен), `DISCARD_CARDS`
при руке короче `value` (легального резолва не существует — движковый гэп,
равно блокирует и ручной путь), отсутствие свободной легальной клетки для
`PLACE`/`CHOOSE_SPACE` (вырожденная доска). Очередь при блокере не
повреждается: periodic recovery sweep повторяет попытку каждые 60 с (джоба
при этом completed с `success: false` — ретраи BullMQ не участвуют),
вмешательство оператора не требуется для остальных стадий.

### 6.2 Stage-специфичные job id

Джобы очереди `combat-timeout` (задача `auto-resolve`) получают id
`combat-scheduled-<gameId>-<stage>` (DEFENSE | RESOLVE; разделитель `-`:
BullMQ запрещает `:` в кастомном jobId — `Custom Id cannot contain :`), а не
один общий на бой: общий id создавал race «защита в момент срабатывания
DEFENSE-джобы» — `remove()` активной джобы бросает, а BullMQ `add` с
существующим jobId молча возвращает старую джобу, и RESOLVE-дедлайн
оказывался не запланирован.
Стейдж-специфичные id делают планирование RESOLVE независимым от состояния
DEFENSE-джобы; устаревшие джобы сами no-op-ятся по персистентному дедлайну
и фазе. Потеря расписания не глотается как успех: `scheduleAutoResolve`
пробрасывает отказ `add`, а `recoverScheduledWork` (старт + periodic sweep)
перепланирует по персистентному дедлайну — transient enqueue-failure
восстанавливается без рестарта процесса.

## 7. Обязательства клиента (адаптер `remoteGameStore`)

1. Применять состояния только через seq-guard (§1) — включая эхо мутации
   (ответ + подписка одного seq).
2. Merge, не replace: частичная проекция не обязана содержать `decks` /
   `discardPiles`.
3. `refetchState` — полный перевыгруз HTTP-снапшота (guard сбрасывается).
4. Подписываться с `since = lastSequenceNumber`; rely на барьер-снапшот,
   не на replay.
5. UI-гейты: кнопка Resolve — только в `COMBAT_RESOLVE`; «Без защиты» —
   только в `COMBAT` у защитника.

## 8. Совместимость

- Изменения, ломающие §1/§2/§4 — новая версия `unmatched-net/N`.
- Добавление полей в снапшок — обратно совместимо (клиент мержит).
- Добавление eventType — обратно совместимо; клиент обязан игнорировать
  неизвестные eventType.

# S07 — Сетевой контракт: приватность, таймауты, recovery (GD-025..GD-027): Evidence

Спринт закрывает сетевой слой production-путями: единая viewer-aware
projection (HTTP/WS/журнал), серверный defense timeout через тот же
идемпотентный резолв, snapshot/WS/since recovery-контракт с connection
barrier. Контракт документирован в `docs/game-design/16-network-contract.md`
(версия `unmatched-net/1`).

## Файлы

| Файл | Что это |
|---|---|
| `tasks.json` | Статус и проверенный объём GD-025..GD-027, незакрытые gates. |
| `raw-privacy-views.json` | Обезличенные viewer-проекции боя до reveal (атакующий/защитник) и после — реальные поля, на которых ассертят raw-JSON тесты `s07-privacy-projection.spec.ts`. |
| `raw-barrier-event.json` | Формат барьер-снапшота `gameStateUpdated` (первое событие подписки) и live-события — как их видит клиент. |
| `frontend-type-comparison.json` | Честное сравнение frontend TS против базлайна 19de668 одним и тем же методом (CompilerHost-оверлей, единый виртуальный пользовательский манифест): baseline 258 / current 258 / added = []. |

## Ключевые находки спринта

1. **Ленивая PubSub-подписка (реальный баг потери событий).**
   `graphql-subscriptions@3.0.0` `PubSubAsyncIterableIterator.subscribeAll()`
   вызывается при ПЕРВОМ `next()` — события, опубликованные до него,
   терялись. Барьер-генератор ждал `loadState` до первого `next()` → окно
   потери. Фикс: `upstream.next()` праймится ДО `loadState`
   (`game-subscription.resolver.ts:withSnapshotBarrier`), событие из окна
   доставляется после барьер-снапшота.
2. **Двойной префикс distributed lock.** `withLock(\`game:${id}\`)` давал ключ
   `game:game:<id>` (withLock сам префиксует) — таймаут-джоба НЕ
   сериализовалась с мутациями. Фикс: `withLockOptions(\`game:${id}\`)` —
   тот же ключ, что у `executeMutation`.
3. **Контракт резолва боя изменён (ломающий).** Раньше атакующий мог
   запустить `executeResolveCombat` в фазе COMBAT (до ответа защитника) —
   это закрывало окно защиты. Теперь: в COMBAT резолв стартует ТОЛЬКО
   защитник (пас «Без защиты»); атакующий — в COMBAT_RESOLVE; системный
   путь — только после истечения `combatInfo.timeoutAt`. Обновлены
   зависимые спеки S05/S06 (вызовы переведены на защитника).
4. **Зависание mid-resolve (P1 ревью, исправлено).** Резолв, запаузенный на
   BOOST_CHOICE/mandatory-эффекте при обоих офлайн-клиентах, застревал
   навсегда: таймаут-джоба отбивалась гейтом «Resolve the pending choice
   first», recovery повторял тот же отказ. Фикс: `processAutoResolve`
   циклом дренит очередь выборов через ПРОИЗВОДСТВЕННЫЕ pending-резолверы
   (optional → auto-decline; mandatory → детерминированный легальный
   фолбэк, `16-network-contract.md` §6.1), затем завершает бой тем же
   `executeResolveCombat`. Каждый шаг: +1 seq, `STATE_UPDATED`,
   audit без id карт; финал — один исход и одна audit. Блокеры (mandatory
   BOOST; DISCARD_CARDS при пустеющей руке; нет свободной клетки для
   PLACE/CHOOSE_SPACE) оставляют очередь нетронутой и репортятся причиной.
5. **Race потери RESOLVE-джобы (P2 ревью, исправлено).** Общий job id на обе
   стадии: `remove()` активной DEFENSE-джобы бросал, `add` с тем же jobId
   молча возвращал старую — RESOLVE-дедлайн не планировался. Фикс:
   stage-специфичные id `combat:scheduled:<gameId>:<stage>` (§6.2);
   `cancelAutoResolve`/`hasScheduledAutoResolve`/`getTimeUntilResolve`
   работают с обеими стадиями.
6. **Ложный блокер дрейна на multi-step CHOOSE_ONE chooseCount>1 (P1
   второго ревью, runtime-подтверждён, исправлено).** `resolveChooseOne`
   оставляет rest-pending с ТЕМ ЖЕ id и той же длиной очереди (снимает
   опцию за шаг) — прогресс-проверка дрейна по (id, length) отвергала
   легитимный шаг, бой зависал навсегда при обоих офлайн. Фикс: прогресс
   по кортежу (id, chooseCount, options.length, stage, mode,
   revealedCards.length) — любое изменение головы = advance, полный no-op
   той же головы = блокер (заодно распознаёт CHOOSE_SPACE stage 1→2 и
   DECK_TOP_PICK PICK→ORDER). Тест: 2-step CHOOSE_ONE в COMBAT_RESOLVE,
   обе стороны офлайн, RED→GREEN, один исход/audit, строго растущий seq,
   без дублей эффектов и без id карт в аудите.
7. **Honest round cap (P2 второго ревью, исправлено).** Исчерпание 8 раундов
   «дрен → резолв» при всё ещё открытом бое больше НЕ репортит success и НЕ
   публикует COMBAT_RESOLVED/audit: честный отказ, состояние открыто,
   periodic recovery sweep продолжает дренировать. Тест: контролируемая
   executor-последовательность из 8+ пауз → нет ложной финализации;
   recovery-прогон доводит бой с ровно одним COMBAT_RESOLVED.
8. **Ранняя отписка барьера (P2 второго ревью, исправлено).** Генератор,
   зависший в `await firstUpstream`, не входил в finally до первого
   PubSub-события — отписка при тишине держала underlying-подписку.
   Барьер переписан ручным async-iterator: `return()` немедленно отпускает
   upstream, висящий `next()` завершается гонкой с сигналом отписки.
   Отказы `loadState`: NotFound (лобби) → live-only; genuine outage (DB/
   Redis) → лог + проброс + освобождение upstream (раньше глотались
   молча).
9. **Periodic recovery sweep (60 c).** Transient-отказ очереди
   (enqueue-failure при атаке/защите — состояние уже персистентно) и
   исчерпание round-cap чинятся БЕЗ рестарта процесса: sweep перепланирует
   по персистентному дедлайну. Покрытие фолбэков док-таблицы §6.1
   доведено: CHOOSE_ONE (multi-step), TARGET_FIGHTER, PLACE, CHOOSE_SPACE
   stage1→stage2 и stage2 — production-резолверами.

## Прогон (точные команды)

```bash
# backend (repo root: backend/)
npx jest --runInBand --runTestsByPath \
  src/games/services/s07-privacy-projection.spec.ts \
  src/games/services/s07-combat-timeout.spec.ts \
  src/games/resolvers/s07-recovery-contract.spec.ts \
  src/game-engine/services/s04-pending-queue.spec.ts
# → 4 suites, 56 tests passed

npx tsc --noEmit -p tsconfig.json          # 0 ошибок

npx jest --runInBand                        # полная регрессия
# → 65 suites: 64 passed, 1 failed (auth.service.spec.ts, 3 теста —
#   известный базлайн, не связан с S07); 1147 passed / 3 failed

# frontend (repo root)
npx vitest run \
  src/store/remoteGameStore.s07.test.ts \
  src/store/remoteGameStore.s03.test.ts \
  src/components/game/GameView.s03.test.tsx \
  src/components/game/GameView.s06.test.tsx \
  src/components/game/turnResourceChoices.test.ts
# → 5 files, 25 tests passed

# admin (repo root: admin/)
npx tsc -b --noEmit                         # 0 ошибок
```

Frontend TS против S06-базлайна: честное сравнение ОДНИМ методом
(CompilerHost-оверлей на 19de668 + один и тот же виртуальный
пользовательский манифест `gameAssetManifest.ts`): **baseline 258 /
current 258 / added = []** — S07 (включая корректирующий проход) не
добавил ни одной ошибки TS. Результат — `frontend-type-comparison.json`.
Абсолютный счёт 258 (не 255 из раннего прогона) — slightly отличающаяся
подпись виртуального стаба; сравнимы baseline vs current одним методом.
Прежние формулировки «256 против 255, +1 легаси-дрейф» — артефакты
несравнимых методов, отозваны.

## Незакрытые gates (честно)

- Реальный WS-прогон против живого сервера (docker/WSL) — не выполнялся:
  работа в изолированном worktree без запуска видимых окон/сервисов.
  Контракт покрыт интеграционными спеками resolver-уровня.
- Мульти-инстанс Redis pub/sub (два backend-процесса) — не проверялся.
- Auth-базлайн: 3 известных падения `auth.service.spec.ts` остаются.
- Дегенеративные блокеры дрейна (см. §6.1 контракта): mandatory
  DISCARD_CARDS при руке короче value (легального резолва нет ни у игрока,
  ни у сервера), отсутствие свободной клетки для PLACE/CHOOSE_SPACE —
  очередь остаётся нетронутой, `processAutoResolve` возвращает причину,
  periodic sweep повторяет попытку.
- Round-cap дрейна (8 раундов за один processAutoResolve) при патологически
  длинных цепочках пауз: честный открытый гейт + sweep доводит бой, но
  живой нагрузки с 8+ последовательными паузами в текущем контенте нет —
  поведение подтверждено контролируемой executor-последовательностью, не
  production-контентом.

# Протокол выборов: исправление SEL-01/NET-2/DET-4, SEL-07, AI-03/SEL-04

Дата: 2026-10-20. Источник задачи: `VERDICT.md` §2. Коммиты: `e352ac207` (фикс), `aef148f43` (тесты и прокси).

## 1. Залипание ввода на многошаговом выборе (SEL-01 = NET-2 = DET-4)

### Воспроизведение до фикса

Сценарий: dev-клиент (`devexec.py`, worktree), аккаунт veteran, VS_AI, King Arthur против Medusa, доска
Marmoreal (`c121b47f8d6eb28daccb76d05`), Restless Spirits в руке. Прокси
`tools/s10/drop-graphql-reply-proxy.cjs` (`S10_DROP_FIELD=resolvePendingEffect`) обрывает ответ после коммита.

Трейс клиента:

```
16.58.56 PEND-RESOLVE sent type=CHOOSE_SPACE stage=1 id=cmq7d7b1j00obwi74q7vqenip-fullText-0-p0
16.58.56 PEND resolve failed: outcome unknown - ... input locked, refetching authoritative state (no resend)
16.58.56 RECOVERY refetch 1/5
16.58.56 RECOVERY held: pending choice cmq7d7b1j00obwi74q7vqenip-fullText-0-p0 is still open at seq 5
16.58.57 RECOVERY held: pending choice ... is still open at seq 5
```

После этого refetch больше не запускался. На экране оставалась плашка «Загрузка состояния…», под ней уже были
подсвечены клетки stage 2. Ввод был заблокирован все 3 минуты наблюдения. Состояние сервера в Redis:
`pendingEffects[0] = { id: "…-p0", type: CHOOSE_SPACE, stage: 2, anchor: (3,2) }`. Это stage 2 с тем же id, что и
stage 1. Вне боя дедлайна нет.

### Что изменено

- **Бэкенд, executor.**
  - Следующий шаг выбора получает новый id `<корень>#<n>` (`nextChoiceStepId`). Так сделано для stage 2 у
    CHOOSE_SPACE и для остатка CHOOSE_ONE при `chooseCount > 1`.
  - Повтор ответа на прежний шаг теперь получает `STATE_CHANGED` и ничего не применяет.
  - В Resolve/Decline DTO добавлен необязательный `expectedSequenceNumber`, как в `BeginManeuverDto`. Ответ на
    другом seq получает `STATE_CHANGED`.
  - Decline при исчезнувшем id или при id не в голове очереди теперь тоже отдаёт `STATE_CHANGED`.
- **UE, `S08FlowController`.**
  - Resolve и decline отправляют `expectedSequenceNumber` (локальный seq).
  - Лок восстановления снимается, если выбор всё ещё открыт, но выполнено одно из условий:
    - seq ушёл дальше guard: потерянный ответ уже не может примениться;
    - два свежих чтения на guard-seq: ответ не дошёл до сервера, а поздняя копия будет отклонена.
  - Если свежее чтение показывает, что выбор открыт, refetch-лестница перевзводится. Раньше клиент молча ждал
    WS-тело без этого id.
- **UE, `S09PendingPresenter`.** Шаг `<корень>#<n>` считается продолжением того же открытия: он не переоткрывает
  modal, не даёт toast с устаревшей предвыборкой и не увеличивает историю сигнатуры.

### Проверка после фикса (живьём, бэкенд worktree на :3200, тот же сценарий)

```
17.45.23 PEND-RESOLVE sent type=CHOOSE_SPACE stage=1 id=…-p0
17.45.23 PEND resolve failed: outcome unknown - ...
17.45.23 RECOVERY refetch 1/5
17.45.23 RECOVERY complete: authoritative state at seq 5
17.45.23 HUD-PENDING view=compact kind=CHOOSE_SPACE head=…-p0#2 … seq=5
17.45.45 PEND resolve done seq=6 (apply)   ← ответ на stage 2, ход и бот пошли дальше
```

Отдельно проверен случай «запрос не дошёл до сервера». Для этого у прокси появился режим `S10_DROP_BEFORE=1`, сценарий:
decline у optional MOVE от Command the Storms.

```
17.48.09 PEND decline failed: outcome unknown
17.48.10 RECOVERY held: pending choice …-p0 is still open at seq 11
17.48.10 RECOVERY re-read in 1s: the choice is still open
17.48.11 RECOVERY settled: … still open at the guarded seq 11 after 2 reads - the lost answer did not land
17.48.22 PEND decline done seq=12 (apply)   ← повторный ответ принят
```

## 2. Ложный окончательный отказ после коммита (SEL-07)

`executeMutation` вызывал `publishGameUpdate` и планирование дедлайнов боя после `saveState` без `try/catch`. Если
падал Redis, клиент получал `errors[]` по уже применённой мутации. Новый общий `commitDecision`
(`games/services/commit-decision.ts`) используют резолвер и ai-turn:

- сохранение: отказ `saveState` пробрасывается как отказ команды;
- дедлайн боя, журнал и публикация события: best-effort;
- `GAME_ENDED`: отдельная best-effort попытка.

Дублированная логика дедлайнов в ai-turn удалена. combat-timeout не тронут: там публикация уже была best-effort, а
многораундовый резолв устроен по-своему.

## 3. Бот VS_AI встаёт вне боя (AI-03 = SEL-04)

Если `decide` вернул null на собственном обязательстве бота или executor отверг его ход, `runOneStep` теперь
перебирает запасные легальные ответы. Порядок кандидатов:

1. `buildSystemPendingFallback`;
2. перебор опций CHOOSE_ONE, клеток CHOOSE_SPACE (по правилу «any space», занятые тоже), целей и карт руки для
   BOOST_CHOICE;
3. decline для optional;
4. `maneuver` без движения, `resolveCombat` защитника, `beginManeuver` и `endTurn` в свой ход.

Каждого кандидата проверяет production-executor, перебор ограничен 64 кандидатами. Удачный ответ даёт warn
`AI_FALLBACK game=… seq=… reason=<no-decision|rejected:kind> head=… -> kind`. Если подходящего ответа нет, пишется
error `AI_FALLBACK … бот стоит`. Чужой ход и чужой выбор фолбэк не трогает.

## Тесты

- **Бэкенд.** Новые: `s06-arthur-cards.spec.ts` (SEL-01, 5 тестов), `commit-decision.spec.ts` (4),
  `ai-turn.service.spec.ts` (AI-03, 4). Перепрогнаны вместе со смежными: s06, ai-turn, commit-decision, s07,
  maneuver-error-codes, s03/s04-transport, subscription-barrier, game-by-code — всё зелёное. `tsc --noEmit` проходит.
  Полный прогон `src/games src/game-engine` на 31 воркере уронил VM Docker по памяти: воркеры получили SIGKILL.
  Упавшие на этом спеки отдельно на 2 воркерах прошли. `attack-type-backfill` в worktree падает без
  `scraped-data`: этих данных нет в git.
- **UE.** `Unmatched.S09+Unmatched.S10`: 167 из 167. Новые тесты:
  - `S10.Recovery`: guarded lock, следующий шаг с новым id, «ответ не дошёл»;
  - `S09.PENDING`: SEL-01 presentation.

## Открыто

- Остаток CHOOSE_ONE по-прежнему ставится в хвост очереди, после вложенных выборов (FINDINGS, NET-2, «порядок
  выборов»). Эту часть я не трогал.
- У `discardToLimit` нет seq-guard. Его id `discard:<turn>:<seq>` уникален, но выбор, который остался открытым,
  держит лок до исчерпания лестницы. После исчерпания теперь показывается видимая ошибка, а не тишина.
- Два сбоя окружения 2026-10-20, к фиксу они не относятся:
  - Клиент для воспроизведения в 17:01:50 UTC закрыла стартовая сессия по просьбе пользователя. Он показывал серый
    fallback: в worktree не было gitignored `Content/`.
    - Сам дефект воспроизвёлся и на нём (протокол от арта не зависит).
    - Проверка после фикса шла уже после add-only robocopy арта. На кадре реальная Marmoreal с нарисованным
      задником и v2-фигурами.
  - VM Docker падала дважды. В первый раз её перезапускала соседняя сессия, во второй раз её уронил OOM от моего
    прогона jest.

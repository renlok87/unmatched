# S06 — Полные стартовые колоды (GD-021..GD-024): Evidence

Спринт закрывает игру реальными 30+30 колодами Medusa vs King Arthur (27
записей / 60 копий из замороженных снимков S01
`evidence/S01/content-{medusa,king-arthur}.json`) через production-пути:
`GameService.startGame → GameInitializationService` (ингест карт), реальный
`CardEffectExecutorService` (резолв эффектов), реальный `resolvePendingEffect`
(очередь GD-018), full game до GAME_OVER.

## Файлы

| Файл | Что это |
|---|---|
| `s06-card-registry.json` | Машиночитаемый реестр 27 записей / 60 копий: instanceCount, bannerName, честный статус (SUPPORTED / BLANK), effectTypes. Генерируется тестом `s06-registry.spec.ts` через production-start. |
| `s06-full-game-1.json` | Полная партия #1: seed `20260925`, Medusa(u1, первый) vs King Arthur(u2). Winner `u1`, 17 ходов, 86 шагов, 0 failed-шагов. |
| `s06-full-game-2.json` | Полная партия #2: seed `1337`, heroU1 = King Arthur, первый игрок `u2` (замена И героя, И первого игрока). Winner `u1` (Arthur), 14 ходов, 72 шага, 0 failed-шагов. |
| `tasks.json` | Статус и точный проверенный объём GD-021..024. |
| `adversarial-review-2026-09-25.md` | Независимое ревью, исправленные замечания и оставшиеся ограничения. |
| `frontend-type-comparison.json` | Артефакт оркестратора: CompilerHost baseline-overlay типов против `fcab551` с read-only виртуальным пользовательским `gameAssetManifest.ts`; baseline 255 = current 255, `added: []`. |
| `correction-pass.md` | Корректировочный проход по итогам независимого ревью: закрытие P2-1..P2-3 (CHOOSE_SPACE-блокеры, ложный manual у Skirmish, восстановленный S05-evidence) + расширение P2-2b (ложный manual у CHOOSE_ONE-с-опциями / фолбэка MOVE/PLACE / RETURN_DEFEATED — все легитимные executable pending исключены из manualEffects аудита), команды и счётчики. |

Обе партии: детерминированный LCG поверх `Math.random` (воспроизводимо),
консервация 30 карт на игрока, seq монотонен, победитель жив / проигравший
hp 0, после GAME_OVER никаких stranded-pending (`pendingEffects`,
`combatInfo`, `pendingManeuver`, `pendingHandDiscard` пусты).

## Прогон (точные команды)

```bash
# backend (repo root: backend/)
npx jest --runInBand --runTestsByPath \
  src/game-engine/services/s06-arthur-cards.spec.ts \
  src/games/services/s06-registry.spec.ts \
  src/games/services/s06-full-games.spec.ts \
  src/game-engine/effects/effect-text-parser.spec.ts
# → 4 suites, 99 tests passed

npx jest --runInBand --runTestsByPath \
  src/game-engine/services/ai-decision.service.spec.ts
# → 34 tests passed (5 новых S06: CHOOSE_SPACE stage1/stage2,
#    DECK_TOP_PICK PICK/ORDER/пустой-revealed→decline)

npx tsc --noEmit -p tsconfig.json   # 0 ошибок

# frontend (repo root)
npx vitest run \
  src/components/game/GameView.s06.test.tsx \
  src/components/game/GameView.s03.test.tsx \
  src/components/game/turnResourceChoices.test.ts \
  src/store/remoteGameStore.s03.test.ts
# → 4 files, 19 tests passed (6 новых S06)

# admin (admin/)
npx vitest run src/pages/game-tester/pendingCommand.test.ts
# → 7 tests passed
npx tsc --noEmit -p tsconfig.json   # 0 ошибок
```

Полный backend regression: `npx jest --runInBand` — только 3 известных
auth-падения (pre-existing, вне спринта), остальные suites зелёные.

## Счётчики S06-покрытия

| Suite | Тестов | Что покрывает |
|---|---|---|
| `s06-arthur-cards.spec.ts` | 32 | GD-021: Lady of the Lake (поиск deck+discard, изъятие, in-hand, no-op, чужой), Prophecy (PICK 2 из 4 + ORDER, негативы «ровно 2»/«порядок всех»/«чужой», остаток ≤3, пустая колода без истощения, privacy через filterPrivateData). GD-022: Command the Storms (последовательная очередь, «не добраться», «клетка занята», мёртвый Merlin), Restless Spirits (stage1/stage2, порог повержения → добор, свои не задеты), Holy Grail (SET_HEALTH по факту боя, пороги live/dead). GD-023: Skirmish (WON anyOwner), Bewilderment (PREVENT/PLACE/decline, баннер), Swift Strike, Divine Intervention, Morgana, Aid the Chosen One (WON/LOST), Regroup, Momentous Shift, Excalibur (BLANK), баннеры всех Arthur-карт. |
| `s06-registry.spec.ts` | 4 | 30+30, глобально уникальные instance ids `${cardId}::${copy}`, 5+25 без пересечений, копии одного имени различимы, баннеры доехали, все кроме Excalibur имеют исполняемые эффекты, запись реестра. |
| `s06-full-games.spec.ts` | 2 | Две полные партии (см. выше). |
| `ai-decision.service.spec.ts` (S06-часть) | 9 | Бот: CHOOSE_SPACE stage1 (клетка зоны с максимумом врагов) и stage2 (смежная с максимумом целей + anchor-бонус), блокеры stage1/stage2 непроходимы (wall/obstacle/закрытая дверь → легальная альтернатива; no-legal-cell → null), DECK_TOP_PICK PICK (первые value) и ORDER (полный порядок), пустой revealed → declinePending. |
| `GameView.s06.test.tsx` | 6 | UI: подсказки стадий CHOOSE_SPACE, клик клетки → resolvePendingEffect(x,y), клик бойца НЕ резолвит, DECK_TOP_PICK PICK/ORDER рендер revealed-кнопок (подтверждение до выбора скрыто), чужой pending не рендерит баннер. |
| `pendingCommand.test.ts` (admin) | 7 | game-tester `peffect`: `<id> 2,1` → CHOOSE_SPACE-инпут; `card c0 c2` индексирует revealedCards pending (не руку); ORDER полный порядок; id-префикс; вне диапазона — внятная ошибка; fallback на руку; legacy MOVE/PLACE/TARGET; ошибки аргументов. |

Runtime-правки спринта:

- `card-effect-executor.service.ts` — SEARCH_ADD_TO_HAND: сравнение имени
  карты регистронезависимо (печатный текст капсит «EXCALIBUR», БД хранит
  «Excalibur» — строгое сравнение ломало Lady of the Lake).
- `gameStateAdapter.ts` — `WirePendingEffect`: типы `CHOOSE_SPACE`/`DECK_TOP_PICK`
  + поля stage/anchor/drawIfDefeated/mode/revealedCards/revealedCount
  (privacy: чужому revealedCards вырезаны, виден только revealedCount).
- `GameView.tsx` — CHOOSE_SPACE: клик клетки → резолв координатами (без
  бойца), подсказки стадий; DECK_TOP_PICK: кнопки revealed-карт в баннере
  (PICK — мультитоггл до value, ORDER — последовательные клики с меткой #N).
- `admin GameTester.tsx` — `peffect` принимает `<id> <x>,<y>` (CHOOSE_SPACE) и
  индексирует revealedCards для DECK_TOP_PICK; листинг `pending` показывает
  revealed-карты (или счётчик, если скрыты). Логика вынесена в чистый
  `pendingCommand.ts` (юнит-тест). В admin добавлен devDep `vitest@^2.1.8`
  (vitest@5 требует vite 6, admin на vite 5).

## Honest claims (что НЕ покрыто отдельно)

- **Excalibur** — BLANK по печатному тексту (эффектов нет); это единственная
  запись не-SUPPORTED в реестре, инстанс существует, играется как обычная
  атака.
- **Momentous Shift** — покрыт parse-контрактом (effect-text-parser) и
  combat-smoke в `s06-arthur-cards.spec.ts` (SET_VALUE по
  MOVED_THIS_TURN); отдельного gameplay-fixture с полным манёвром нет.
- **Noble Sacrifice / Arthur Feint** — покрыты существующим
  `s05-boost-timing.spec.ts` (during-combat boost / fighter-choice боя).
- **Полные партии** — scripted-policy внутри spec (перебор всех pending-типов
  колод), НЕ `AiDecisionService`: production AI покрыт юнитами
  (resolveSpace/resolveDeckPick), но сквозной full-game ботом не гонялся.
- **Frontend tsc** — в worktree не сгенерированы gql-codegen-артефакты
  (`npm run codegen:build` требует живую схему), поэтому `tsc` сыпет
  pre-existing ошибками в legacy gql-dependent файлах (ApolloExample,
  phaser/*, authStore и т.п.). Правки спринта (gameStateAdapter, GameView,
  s06-тест) этих ошибок не добавляют. Vitest-прогон не зависит от codegen.
- **Seeds партий** выбраны прогоном кандидатов: нужны осмысленная длина и
  оба исхода «первый игрок»; seed 1337 даёт победу второго-seated игрока.

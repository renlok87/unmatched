# S06 — Корректировочный проход по итогам независимого ревью

Независимый адверсариальный ревьюер подтвердил PASS по GD-021..024 без
P0/P1 и предъявил 3 подтверждённых P2-замечания. Все три закрыты в этом
проходе узкими правками в минимальном ответственном слое; новых
production-фич нет, поведение S06 (обе полные партии, реестр, очереди)
сохранено. Коммитов/пушей не производилось.

## P2-1 — AiDecisionService CHOOSE_SPACE: непроходимые клетки

**Находка.** Stage 1 читал `(cell as { isBlocked? }).isBlocked` — поля
`isBlocked` у модели `Cell` (`models/board.model.ts`) не существует, поэтому
проверка всегда была undefined-ложной: стена/препятствие/закрытая дверь
считались проходимыми. Stage 2 перебирал `getAdjacentCells`, игнорируя
блокировку. Реальный выбор блокера отклонялся исполнителем
(`game-action-executor.service.ts`, `isCellPassable`), pending ИИ мог
зависнуть.

**Правка** (`backend/src/game-engine/services/ai-decision.service.ts`):

- обе стадии используют авторитетный `isCellPassable` из
  `movement/traversal.ts` (та же семантика GD-015, что у валидаторов,
  MovementService и A*):
  - stage 1: `passable(x, y) = isCellPassable(state.boardState.cells[y]?.[x])`;
  - stage 2: смежные кандидаты фильтруются `isCellPassable` до скоринга.

**Регресс-тесты** (`ai-decision.service.spec.ts`, через реальный
`AiDecisionService`, без зеркалирования хелпера):

1. stage 1: стена (2 врага, глобальный максимум), препятствие и закрытая
   дверь с врагами пропускаются — выбрана легальная клетка (2,0);
2. stage 1: в зоне нет ни одной проходимой клетки → `decide` = null;
3. stage 2: смежная закрытая дверь с врагом пропущена — легальная
   альтернатива (3,0);
4. stage 2: все 4 смежные клетки блокированы → null.

## P2-2 — Skirmish (COMBAT_FIGHTER): ложная manual-аннотация

**Находка.** Ветка COMBAT_FIGHTER в
`card-effect-executor.service.ts` создавала легитимный pending
(очередь GD-018) и одновременно возвращала `manual: text` — текст
попадал в `manualEffects` аудита как «неисполненный» эффект.

**Правка.** Убран `manual: text` из возврата Skirmish-ветки; pending и его
резолв не затронуты.

**Регресс-тест** (`s06-arthur-cards.spec.ts`, positive-кейс Skirmish):
при живом pending `resolved.metadata.manualEffects` строго `[]`.

### P2-2b — расширение: ещё три ветки с ложным manual-аннотированием

**Находка (повторный read-only аудит оркестратора).** Исходная правка P2-2
закрыла только Skirmish COMBAT_FIGHTER. Первоначальное обоснование
«фолбэк общего MOVE/PLACE намеренно не тронута — покрывает реально
manual-случаи» **опровергнуто кодом**: каждый создаваемый там pending
исполняется production-резолвом `executeResolvePendingEffect`
(`game-action-executor.service.ts`). Три ветки создавали легитимный
executable pending И возвращали `manual: text` (ложно попадая в
`manualEffects` аудита):

1. **CHOOSE_ONE с опциями** — pending `CHOOSE_ONE`; резолв
   `optionIndex` → `resolveChooseOne` (строки ~789+) → `executeChosenEffects`.
2. **Фолбэк общего MOVE/PLACE** — pending `MOVE|PLACE`; резолв
   `fighterId+x+y` → общий путь (~578-695: валидация цели/клетки,
   достижимость, зонное ограничение, мутация позиции, снятие pending).
3. **RETURN_DEFEATED** — optional revive-pending `PLACE`
   (`restoreFullHealth: true`); резолв тем же путём (исключение для
   поверженных ровно у этого pending-типа, ~587-590, revive ~680-683).
   Production-резолв end-to-end уже покрыт `s05-medusa-cards.spec.ts`
   GD-020 (Winged Frenzy: очередь MOVE×3+PLACE, revive в зоне Medusa).

В manualEffects остались ТОЛЬКО реальные UNSUPPORTED-семантики:
CHOOSE_ONE без распознанных опций и default-фолбэк (warn-лог + метрика).

**Правка** (`card-effect-executor.service.ts`): убран `manual: text` из
трёх перечисленных веток; контракт в шапке файла и комментарий
`EffectResult.manual` обновлены (manual = только UNSUPPORTED). Механика
выбора/резолва не менялась: пауза очереди и continuation определяются
ростом `pendingEffects`, а не полем `manual`. Устаревшие комментарии
«MOVE/PLACE → manualEffects» в `effect-text-parser.ts` поправлены на
pending-семантику. Game Tester продолжит получать manual-тексты для
реально неподдержанного, а pending этих веток резолвятся как раньше.

**Регресс-тесты** (`card-effect-executor.service.spec.ts`, новый describe
«легитимные pending ≠ manualEffects (аудит P2-2)» + обновлённые ассерты
трёх существующих тестов):

1. CHOOSE_ONE: pending существует → резолв опции (путь
   `resolveChooseOne`: `executeChosenEffects` с `optionEffects/card/
   effectContext`) применяет «Draw 1 card», `manualEffects === []`;
2. RETURN_DEFEATED: pending `PLACE` с `fighterIds/zoneFighterName/
   restoreFullHealth/optional`, `manualEffects === []`; вариант «нет
   поверженных ("if any")» — skip без pending и без manual;
3. общий MOVE (боевой и scheme-путь): pending `MOVE`, `manualEffects === []`
   (продолжение очереди после снятия pending уже покрыто резюм-тестом
   с UNSUPPORTED-хвостом: manual собирает только UNSUPPORTED-текст).

## P2-3 — Перезаписанный S05-evidence

**Находка.** `docs/game-design/evidence/S05/s05-card-registry.json` был
перезаписан S06-статусами (parser v9, SUPPORTED 24 против S05-эры 20), при
что комментарий в `s05-registry.spec.ts` утверждал, что S05-снимок
заморожен.

**Правка.**

- файл восстановлен байт-в-bайт из базового коммита `fcab551`
  (`git show fcab551:docs/game-design/evidence/S05/s05-card-registry.json`);
- опечатка в комментарии исправлена: «замороженный S06-снимок статусов S05»
  → «замороженный S05-снимок статусов»;
- проверено: ни один тест S05/S06 не пишет в S05-evidence (s05-spec только
  console.log; machine-readable реестр S06 пишется
  `s06-registry.spec.ts` → `evidence/S06/s06-card-registry.json`, актуальность
  подтверждена прогоном).

## Frontend typecheck: сравнение с базовой линией

Артефакт оркестратора: `frontend-type-comparison.json` (рядом с этим
файлом). Метод: TypeScript CompilerHost baseline-overlay по изменённым
tracked-файлам против `fcab551`, с одним и тем же read-only виртуальным
`src/phaser/assets/gameAssetManifest.ts` из исходного пользовательского
checkout'а для обеих сторон (манифест в Git не копируется и не читается
напрямую из чужого дерева).

Результат: baseline **255**, current **255**, `added: []` — правки спринта
не добавили ни одной ошибки типов.

Голый `tsc` в чистом worktree показывает **256** ошибок: это 255
pre-existing (legacy gql/phaser/authStore-файлы без codegen-артефактов,
см. README) + 1 отсутствующий виртуальный пользовательский
`gameAssetManifest.ts`, который не является tracked-файлом. Новых ошибок
нет.

## Прогон (точные команды и счётчики)

```bash
# backend (cwd: backend/)
npx jest --runInBand --runTestsByPath \
  src/game-engine/services/ai-decision.service.spec.ts \
  src/game-engine/services/s06-arthur-cards.spec.ts \
  src/game-engine/effects/s05-registry.spec.ts
# → 3 suites, 77 tests passed (ai-decision 38: +4 блокер-кейса CHOOSE_SPACE)

npx jest --runInBand --runTestsByPath \
  src/games/services/s06-registry.spec.ts \
  src/games/services/s06-full-games.spec.ts
# → 2 suites, 6 tests passed (реестр S06 переписан актуальным, партии целы)

npx jest --runInBand --runTestsByPath \
  src/game-engine/services/s05-boost-timing.spec.ts \
  src/game-engine/effects/card-effect-executor.service.spec.ts \
  src/games/services/ai-turn.service.spec.ts
# → 3 suites, 51 tests passed (исполнитель/AI-гейт не регрессировали)

npx jest --runInBand
# → 62 suites: 1100 passed, 3 failed — только известные auth-падения
#    (pre-existing baseline, вне спринта)

npm run type-check
# → tsc --noEmit, 0 ошибок

# frontend (cwd: repo root)
npx vitest run src/components/game/GameView.s06.test.tsx
# → 1 file, 6 tests passed

# admin (cwd: admin/)
npx vitest run src/pages/game-tester/pendingCommand.test.ts
# → 1 file, 7 tests passed

# repo root
git diff --check   # чисто (только CRLF-warning на восстановленный JSON)
```

## Изменённые файлы этого прохода

| Файл | Изменение |
|---|---|
| `backend/src/game-engine/services/ai-decision.service.ts` | P2-1: `isCellPassable` для обеих стадий CHOOSE_SPACE |
| `backend/src/game-engine/services/ai-decision.service.spec.ts` | P2-1: +4 регресс-теста (блокер → альтернатива, no-legal-cell → null) |
| `backend/src/game-engine/effects/card-effect-executor.service.ts` | P2-2: убран ложный `manual:` из Skirmish-ветки; P2-2b: убран `manual:` из CHOOSE_ONE-с-опциями / фолбэка MOVE/PLACE / RETURN_DEFEATED + обновлён контракт в шапке |
| `backend/src/game-engine/effects/card-effect-executor.service.spec.ts` | P2-2b: +3 теста (CHOOSE_ONE-резолв, RETURN_DEFEATED pending/skip), обновлены 3 ассерта (MOVE боевой, MOVE scheme, CHOOSE_ONE) на `manualEffects === []` |
| `backend/src/game-engine/effects/effect-text-parser.ts` | P2-2b: устаревшие комментарии MOVE/PLACE «→ manualEffects» заменены на pending-семантику (код не менялся) |
| `backend/src/game-engine/services/s06-arthur-cards.spec.ts` | P2-2: assertion `manualEffects === []` при живом pending |
| `backend/src/game-engine/effects/s05-registry.spec.ts` | P2-3: опечатка в комментарии (S05-снимок) |
| `docs/game-design/evidence/S05/s05-card-registry.json` | P2-3: восстановлен из `fcab551` (повторно не трогался; P2-2b его не меняет) |
| `docs/game-design/evidence/S06/frontend-type-comparison.json` | Артефакт сравнения типов (read-only копия) |
| `docs/game-design/evidence/S06/correction-pass.md` | Этот документ |
| `docs/game-design/evidence/S06/README.md` | Счётчики таблиц обновлены под +4 теста и новые файлы |

## Прогон корректировки P2-2b (повторно, после правки)

```bash
# backend (cwd: backend/)
npx jest --runInBand --runTestsByPath \
  src/game-engine/effects/card-effect-executor.service.spec.ts
# → 1 suite, 39 passed (+3 новых P2-2b)

npx jest --runInBand --runTestsByPath \
  src/game-engine/services/s06-arthur-cards.spec.ts \
  src/game-engine/services/s05-medusa-cards.spec.ts \
  src/game-engine/effects/s05-registry.spec.ts \
  src/game-engine/effects/effect-text-parser.spec.ts
# → 4 suites, 129 passed

npx jest --runInBand --runTestsByPath \
  src/games/services/s06-registry.spec.ts \
  src/games/services/s06-full-games.spec.ts \
  src/games/services/ai-turn.service.spec.ts \
  src/game-engine/services/ai-decision.service.spec.ts \
  src/games/game-state.service.spec.ts
# → 5 suites, 117 passed (полные партии/реестр/AI/подписка не регрессировали)

npx jest --runInBand
# → 62 suites: 1103 passed, 3 failed — только известные auth-падения
#    (тот же pre-existing baseline, что и до правки: 1100+3 новых)

npm run type-check
# → tsc --noEmit, 0 ошибок
```

Транскрипты полных партий (`s06-full-game-{1,2}.json`) manualEffects не
содержат и регенерации не потребовали; S05-snapshot
(`evidence/S05/s05-card-registry.json`) не тронут.

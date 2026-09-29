# Контракт FS08CueDispatcher (CUE-слой презентации)

Срез 2026-09-29, волна 4, задача W4-D. **Статус: предложено.** Это спецификация, JSON-схема, таблица данных и тестовые фикстуры без мира. Код движка здесь не пишется: реализация — GD-044 (S11, «Cue subsystem»), ассеты — ART-010 и GD-049.

Основание: меморандум engine-gate §1 п.8 («FS08CueDispatcher (таблица, трасса `CUE fx … result=`, тесты без мира)») и исследование R3.4 (вариант B: мира-независимый диспетчер по данным). Норматив событий — [07-animation-vfx-audio.csv](../../../game-design/07-animation-vfx-audio.csv) (18 CUE). Сеть и повторы — [08 §6.3](../../../game-design/08-integration-decisions.md). Доступность — [02](../../../game-design/02-ux-ui-spec.md) UI-ACC-005/006. Сокеты — [rig-contract.json](../../../art-pipeline/rig/rig-contract.json) `ue_import.sockets_v2`.

| Файл | Что это |
| --- | --- |
| [cue-table.json](cue-table.json) | данные 18 CUE (`unmatched.cue-table/1`): ассеты, сокет, длительности, поведение; сейчас все ассеты `missing` — это и есть missing-report ART-010 |
| [cue-table.schema.json](cue-table.schema.json) | JSON Schema таблицы (draft 2020-12) |
| [cue-fixture.schema.json](cue-fixture.schema.json) | схема фикстур `unmatched.cue-fixture/1` |
| [fixtures/](fixtures/) | 8 сценариев (события → точная трасса) и 4 негативные трассы для гейта |
| [tools/s08/cue_contract/cue_contract.py](../../../../tools/s08/cue_contract/cue_contract.py) | `validate-table`, `run-fixtures`, `check-trace`: валидатор таблицы, эталонная модель, гейт трассы |
| [tools/s08/cue_contract/test_cue_contract.py](../../../../tools/s08/cue_contract/test_cue_contract.py) | 10 юнит-тестов |

## 1. Зачем

Сейчас `FS08FlowController::ComputeCues` выводит два типа (`FighterMoved`, `FighterDamaged`), а `AS08FlowGameMode::HandleCues` рисует только цифры урона и пишет `CUE damage … seq=`. Если добавлять VFX, звук, клипы и материалы по месту, каждая система будет сама решать повтор seq, реконнект и отсутствие ассета. Ошибку «двойного урона» (ACC-012) потом ловить дороже. Один диспетчер по данным даёт одну точку для: дедупликации, запрета повтора после реконнекта, лимитов звука, fallback с логом, сокращённых анимаций и трассы для доказательств.

## 2. Границы

- Диспетчер **никогда не носит состояние игры**. Состояние доски, HP и фаза берутся из снапшота; диспетчер только показывает. Отсутствие ассета, обрыв клипа или выключенные эффекты не меняют и не задерживают состояние (ACC-022, GD-044 «состояние не ждёт клипа»).
- Вход — события презентации после `SeqGuard` в `ApplySnapshot`: `(cueId, subject, seq)` плюс параметры (шаги пути, значение урона). Сам диспетчер снапшоты не сравнивает.
- Выход — план презентации для тонкого UE-адаптера (спавн Niagara, звук, клип, параметр материала, виджет) и строки трассы. Адаптер не принимает решений о повторе и лимитах.
- Диспетчер не зависит от мира (`UWorld`), как `S08ArtHud`: его логику можно проверять автотестами без карты.

## 3. Данные (`cue-table.json`)

Одна строка на CUE. Поля (полностью — в схеме):

| Поле | Смысл |
| --- | --- |
| `source` | `local` (ввод игрока, без seq), `server` (событие снапшота, seq обязателен), `connection` (CUE-017/018) |
| `trigger` | тип события (`input.hover`, `state.fighter_damaged`, `net.recovered` …) — имя будущего `ES08CueType` |
| `subject` | над кем показ: `fighter`, `target`, `cursor`, `hud`, `scene` |
| `duration_ms` / `duration_per_step_ms` | из 07; у CUE-007 280 мс на клетку |
| `feedback_delay_ms`, `blocks_input`, `skippable` | из 07; блокировка ввода ≤ 1000 мс, кроме терминального CUE-016 |
| `vfx` | Niagara: `system` (soft path) или `status: missing` + `missing_reason`; `attach` `socket`/`world`, `socket` (`Weapon`, `Head`, `Root`, `Base`); `sim: cpu`, `deterministic: true`, `prewarm: true` |
| `sfx` | `sound` — **USoundBase** (SoundWave, SoundCue и MetaSoundSource взаимозаменяемы без правки кода); `sound_class` UI/SFX/Music; `priority` 1–3; `concurrency` → USoundConcurrency (`max_count` = MaxCount, `resolution` StopOldest/PreventNew, `retrigger_ms` = RetriggerTime) |
| `clip` | роль клипа драйвера анимации (`LungeAttack`, `HitReact`, `DeathSettle`); путь AnimSequence или `missing` |
| `material` | параметр Custom Primitive Data мастера `M_UM_Figure`: `FxFlash` (5–8), `Rim` (9–10), `Fade` (11) — раскладка меморандума §1 п.4 |
| `ui`, `marker`, `postprocess` | виджет HUD, маркер игрового слоя, дельта профиля света (CUE-016/017) |
| `on_new_event` | `replace`, `cascade` (CUE-005), `jump_to_final` (CUE-007, CUE-013), `interrupt` (CUE-008), `none` (терминальный CUE-016, длящийся CUE-017) |
| `replace_scope` | `cue` — новый показ обрывает любой активный показ этого CUE (наведение, выбор, баннер); `subject` — только у того же бойца |
| `interrupted_by` | какие CUE обрывают этот (CUE-008 обрывают 009/010/011/013) |
| `on_reconnect` | всегда `skip`: старая очередь не проигрывается (ACC-012, QA-108) |
| `reduced_motion` | UI-ACC-006: `shorten` (≤ `max_ms`, не больше 100), `snap` (0 мс, сразу финал), `keep` (движения нет) |
| `shake` | камера: `null` в MVP; если появится — ассет и `disabled_by: UI-ACC-005`; кадры доказательств снимаются без тряски |
| `fallback` | поведение при отсутствии ассета из 07 и `log: Warning` |

Правила ассетов:

- Пути — soft object path `/Game/…`. Строки `LoadObject` кукер не видит (ловушка 5): папки эффектов удерживаются в cook через PrimaryAssetLabel или `+DirectoriesToAlwaysCook`. Будущий `UPrimaryDataAsset` импортируется из этой таблицы скриптом (JSON — источник правды, как профиль света).
- Niagara: CPU-симуляция; пул компонентов (`ENCPoolMethod::AutoRelease`); один `UNiagaraEffectType` с бюджетами и CullReaction; `bDeterminism` + `RandomSeed` на System и Emitter, чтобы кадры доказательств повторялись; прогрев всех систем таблицы при загрузке матча. На DX12 (решение пользователя 2026-09-28, [журнал](../../../game-design/decisions/2026-09-29-render-ui-user-decisions.md)) доступен PSO precaching, но прогрев остаётся обязательным: первый показ не должен давать хитч на машинах без кэша PSO.
- VFX никогда не единственный носитель информации: урон дублируется цифрой (виджет) и HP в HUD.
- Звук: SoundClass Master → UI / SFX / Music (ползунки UI-ACC-007..009); окно без фокуса уже заглушено движком (`[Audio] UnfocusedVolumeMultiplier=0.0`), что совпадает с UI-ACC-011.

## 4. Семантика диспетчера (нормативно)

Правила пронумерованы; эталонная модель `ReferenceDispatcher` исполняет их в этом порядке, фикстуры фиксируют результат.

- **D1. Время.** События обрабатываются в порядке поступления, `t` (мс от начала партии) не убывает. Перед каждым событием завершаются показы, чей конец ≤ `t` (строка `done`).
- **D2. Дедупликация.** Серверный CUE идентифицируется тройкой `(cueId, subject, seq)`. Первая тройка показывается, повтор (тот же seq по HTTP и WS) даёт `result=duplicate` без показа. Общий seq у разных CUE одного снапшота допустим (урон и смерть — seq 30).
- **D3. Устаревшее.** Серверный CUE с seq меньше наибольшего уже показанного — `result=stale` (снапшот старше применённого; 08 §6.3).
- **D4. Реконнект.** Событие восстановления с `recovered_seq = R` пишет `CUE reconnect recovered_seq=R`, обрывает все активные показы (`cut=reconnect`), и дальше любой серверный CUE с seq ≤ R — `stale`. Пропущенное не проигрывается; сразу финальное состояние и тост CUE-018.
- **D5. Разрыв.** Повторный сигнал разрыва, пока связь не восстановлена, — `duplicate`.
- **D6. Замена.** Новый показ обрывает активный показ того же CUE: по `replace_scope` у любого объекта (`cue`) или только у того же `subject`. Метка обрыва — `replace`, для `jump_to_final` — `jump`. `cascade` не обрывает.
- **D7. Прерывание.** Показ CUE X обрывает активные показы тех CUE, у которых X в `interrupted_by` (`cut=interrupt`).
- **D8. Звук: частота.** Если с прошлого звука этого CUE прошло меньше `retrigger_ms`, звук не играет (`sfx=throttled`), остальной показ идёт.
- **D9. Звук: одновременность.** При `max_count` активных звуках этого CUE: `StopOldest` останавливает самый старый (строка `CUE sfx stop … reason=concurrency`), `PreventNew` не играет новый (`sfx=limited`).
- **D10. Отсутствие ассета.** Если путь не задан или ассет не загрузился, канал получает `missing`, показ получает `result=fallback`, UE-адаптер пишет Warning и выполняет `fallback.behaviour` из 07. Длительность и `done` сохраняются.
- **D11. Сокращённые анимации.** При включённой UI-ACC-006 длительность `shorten` ≤ `max_ms`, `snap` = 0; в строке `reduced=1`. `keep` не меняется (`reduced=0`).
- **D12. Длительность.** Показ длится `duration_ms` (или шаг × клетки); при 0 `done` пишется сразу. Звук считается активным на ту же длительность.

## 5. Трасса

Строки пишет `FS08Trace` без изменений формата; префикс лога допустим, гейт ищет подстроку `CUE `. Значения без пробелов.

```
CUE fx id=<CUE-NNN> subject=<id> seq=<N|-> t=<ms> vfx=<имя|none|missing> sfx=<имя|none|missing|throttled|limited> clip=<имя|none|missing> mat=<FxFlash|Rim|Fade|none> socket=<Weapon|Head|Root|Base|-> reduced=<0|1> result=<spawned|fallback>
CUE fx id=<CUE-NNN> subject=<id> seq=<N|-> t=<ms> result=<duplicate|stale>
CUE fx done id=<CUE-NNN> subject=<id> seq=<N|-> t=<ms> ms=<длительность> cut=<0|replace|jump|interrupt|reconnect>
CUE sfx stop id=<CUE-NNN> subject=<id> seq=<N|-> t=<ms> reason=concurrency
CUE reconnect recovered_seq=<R> t=<ms>
CUE settings reduced_motion=<0|1> t=<ms>
```

`имя` — короткое имя ассета (последний сегмент soft path). Строки `CUE damage` и `CUE move` текущего S08 остаются и гейтом игнорируются.

Пример (фикстура `attack-interrupt`):

```
CUE fx id=CUE-008 subject=arthur seq=50 t=0 vfx=NS_Test_Flash sfx=SW_Test_Attack clip=AS_Test_Lunge mat=none socket=Weapon reduced=0 result=spawned
CUE fx done id=CUE-008 subject=arthur seq=50 t=300 ms=300 cut=interrupt
CUE fx id=CUE-011 subject=medusa seq=51 t=300 vfx=NS_Test_Hit sfx=SW_Test_Hit clip=AS_Test_HitReact mat=FxFlash socket=Head reduced=0 result=spawned
CUE fx done id=CUE-011 subject=medusa seq=51 t=1200 ms=900 cut=0
```

## 6. Гейт доказательств (`check-trace`)

Кадр — иллюстрация, доказательство — трасса. `python tools/s08/cue_contract/cue_contract.py check-trace <Unmatched.log>` отклоняет:

| Код | Правило |
| --- | --- |
| G1 | строка без обязательного поля, неизвестный CUE или `result` |
| G2 | тройка `(cue, subject, seq)` показана больше одного раза: число `spawned`+`fallback` = числу уникальных троек |
| G3 | после `CUE reconnect recovered_seq=R` показан CUE с seq ≤ R |
| G4 | показ без `done`, `done` без показа, `ms` не равно разнице `t`, сокращённая анимация длиннее `max_ms`, `snap` не 0 |
| G5 | блокирующий ввод CUE длился больше 1000 мс (кроме терминального) |
| G6 | звуков одного CUE одновременно больше `max_count` (с учётом `sfx stop`) |
| G7 | звуки одного CUE чаще `retrigger_ms` |
| G8 | `result=fallback` не совпадает с наличием `missing` в vfx/sfx/clip |
| G9 | время строк убывает |

Сводка гейта: `presented`, `spawned`, `fallback`, `duplicate`, `stale`, `done`, `unique_triples`. Для ACC-012 в пакете доказательств записывается строка `CUE_TRACE PASS {…}`.

## 7. Фикстуры без мира

`python tools/s08/cue_contract/cue_contract.py run-fixtures` — эталонная модель даёт `expect_trace` строка в строку, гейт на ней чист, сводка совпадает с `expect_summary`; негативные трассы отклоняются ровно с кодами `expect_error_codes`.

| Фикстура | Что закрепляет |
| --- | --- |
| `dedupe-http-ws` | D2: один показ на seq, повтор по WS — `duplicate` (ACC-012, QA-007) |
| `reconnect-no-replay` | D4, D5: разрыв, повторный разрыв, восстановление R=14, запоздавшие seq 12 и 14 — `stale`, seq 15 — показ (QA-108) |
| `sfx-concurrency-stop-oldest` | D9: третий звук урона останавливает старейший, VFX показываются все |
| `hover-retrigger` | D6 (`replace_scope: cue`), D8: контур переходит сразу, тик не чаще 1/150 мс |
| `missing-assets-fallback` | D10: таблица без ассетов и незагрузившийся тестовый VFX → `fallback`, длительности сохраняются |
| `reduced-motion` | D11: урон 900 → 100 мс, перемещение `snap`, наведение `keep` |
| `attack-interrupt` | D7: LungeAttack обрывается уроном через 300 мс |
| `stale-seq-and-move-jump` | D3, D6 (`jump`): новое перемещение той же фигуры, запоздавший seq 59 |
| `neg-*` (4) | гейт ловит G2, G3, G4+G8, G5+G6 |

**Перенос в C++ (GD-044).** Автотесты `S08.CueDispatcher.*` (как 9 тестов `S08.ArtHud`) читают эти JSON, подают события в `FS08CueDispatcher` и сравнивают строки трассы побайтно. Эталонная модель на Python — исполняемая спецификация, её вывод не заменяет C++-тест.

## 8. Эскиз интерфейса (для GD-044, не код)

- `FS08CueEvent { FName CueId; FString Subject; TOptional<int32> Seq; int32 Steps; int64 TimeMs; }`.
- `FS08CuePlan { FName CueId; FString Subject; TOptional<int32> Seq; ES08CueResult Result; TSoftObjectPtr<UNiagaraSystem> Vfx; TSoftObjectPtr<USoundBase> Sfx; FName Socket; ES08ClipRole Clip; FName CpdParam; int32 DurationMs; bool bReduced; }`.
- `FS08CueDispatcher::Feed(const FS08CueEvent&, TArray<FS08CuePlan>& Out, TArray<FString>& TraceLines)`; `OnReconnect(int32 RecoveredSeq)`; `SetReducedMotion(bool)`; `Tick(int64 NowMs)` для `done`.
- UE-адаптер (`AS08FlowGameMode` или компонент презентации) исполняет план: `UNiagaraFunctionLibrary::SpawnSystemAttached` с пулом, `UGameplayStatics::PlaySound2D`/`SpawnSoundAttached` с Concurrency из таблицы, `SetCustomPrimitiveDataFloat`, драйвер анимации (`PlayOneShot(role)`), виджет. Решений о повторах адаптер не принимает.
- Новые типы события в `ComputeCues`: `AttackDeclared`, `FighterDefeated`, `FighterHealed`, `AbilityTriggered`, `TurnChanged` (R2.4: скрытие фигуры при смерти задерживается до ≤ 950 мс, QA-101).

## 9. Открытые вопросы

1. Стиль VFX (AD-OPEN-34) и библиотека ART-010 — ассеты таблицы остаются `missing` до них.
2. Длительности HitReact (0,4 с в 04 против 0,9 с CUE-011) и DeathSettle (0,9 против ≤ 0,95 с) — таблица берёт 07; при изменении 07 валидатор покажет расхождение.
3. CUE-014 у Medusa: луч от сокета `Head` к цели, у Arthur — свечение `Weapon`. Сейчас строка задаёт `Weapon`; сокет по герою — поле DataAsset героя (GD-044).
4. Бюджет: худший набор 2×CUE-011 + 013 + 007 + 014 — ΔGPU ≤ 1 мс по ProfileGPU (bench fx/ui меморандума §2). На DX12 + Lumen эмиссивные частицы могут попадать в Lumen-сцену: проверить на bench, при необходимости исключить эффекты из непрямого освещения.

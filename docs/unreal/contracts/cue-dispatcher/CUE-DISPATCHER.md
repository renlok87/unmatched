# Контракт FS08CueDispatcher (CUE-слой презентации)

Срез 2026-09-29, волна 4, задача W4-D. **Статус: предложено.** Это спецификация, JSON-схема, таблица данных и тестовые фикстуры без мира. Код движка здесь не пишется: реализация — GD-044 (S11, «Cue subsystem»), ассеты — ART-010 и GD-049.

**DE-018 (2026-10-04, первый срез GD-044):** диспетчер реализован для боевых строк CUE-008…011, 013, 014 — `FS08CueDispatcher` ([S08CueDispatcher.h](../../../../unreal/Unmatched/Source/Unmatched/S08/S08CueDispatcher.h)), постановка боя по §3.1 — `FS09CombatStage` ([S09CombatStage.h](../../../../unreal/Unmatched/Source/Unmatched/S09/S09CombatStage.h)), адаптер — `AS08FlowGameMode`. Остальные строки (наведение, перемещение, начало хода, связь) — по-прежнему GD-044.

**DE-019 (2026-10-05):** смерть по этапам F-09 и переход к экрану результата — `FS09DeathStage` и `FS09ResultGate` ([S09DeathStage.h](../../../../unreal/Unmatched/Source/Unmatched/S09/S09DeathStage.h)); фигура сама играет DeathSettle, неподвижность и растворение DE-011 (`AS08FighterActor`, `S08HeroesV2::FDeathPlan`). Трасса — строки `CUE death` и `RESULT screen` (§5), гейт — DS1–DS6 (§6).

Основание: меморандум engine-gate §1 п.8 («FS08CueDispatcher (таблица, трасса `CUE fx … result=`, тесты без мира)») и исследование R3.4 (вариант B: мира-независимый диспетчер по данным). Норматив событий — [07-animation-vfx-audio.csv](../../../game-design/07-animation-vfx-audio.csv) (18 CUE). Сеть и повторы — [08 §6.3](../../../game-design/08-integration-decisions.md). Доступность — [02](../../../game-design/02-ux-ui-spec.md) UI-ACC-005/006. Сокеты — [rig-contract.json](../../../art-pipeline/rig/rig-contract.json) `ue_import.sockets_v2`.

| Файл | Что это |
| --- | --- |
| [cue-table.json](cue-table.json) | данные 18 CUE (`unmatched.cue-table/1`): ассеты, сокет, длительности, поведение; VFX и звуки пока `missing` — это и есть missing-report ART-010; клипы HitReact и DeathSettle есть у всех v2-фигур (DE-003) |
| [cue-table.schema.json](cue-table.schema.json) | JSON Schema таблицы (draft 2020-12) |
| [cue-fixture.schema.json](cue-fixture.schema.json) | схема фикстур `unmatched.cue-fixture/1` |
| [fixtures/](fixtures/) | 12 сценариев (события → точная трасса; 3 из них — постановка боя DE-018 с блоком `staging` для C++) и 5 негативных трасс для гейта |
| [tools/s08/cue_contract/cue_contract.py](../../../../tools/s08/cue_contract/cue_contract.py) | `validate-table`, `run-fixtures`, `check-trace`: валидатор таблицы, эталонная модель, гейт трассы |
| [tools/s08/cue_contract/test_cue_contract.py](../../../../tools/s08/cue_contract/test_cue_contract.py) | юнит-тесты валидатора, расписания CUE-007, эталонной модели и гейта |

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
| `cap_subject_ms`, `cap_seq_ms`, `min_step_ms`, `overlap`, `place_ms`, `params` | только у CUE-007 (MS-T-15): потолки расписания перемещения [move-selection 04 §6.3](../../../game-design/move-selection/04-technical-design.md) — 1400 мс на бойца, 2400 мс на seq, шаг ≥ 90 мс, перекрытие 30 %, PLACE 240 мс; `params` описывает поля события (`path`, `order_in_seq`, `kind`, `steps`, `path_source`). Длительность показа = расписание по всем перемещениям seq |
| `feedback_delay_ms`, `blocks_input`, `skippable` | из 07; блокировка ввода ≤ 1000 мс, кроме терминального CUE-016 |
| `vfx` | Niagara: `system` (soft path) или `status: missing` + `missing_reason`; `attach` `socket`/`world`, `socket` (`Weapon`, `Head`, `Root`, `Base`); `sim: cpu`, `deterministic: true`, `prewarm: true` |
| `sfx` | `sound` — **USoundBase** (SoundWave, SoundCue и MetaSoundSource взаимозаменяемы без правки кода); `sound_class` UI/SFX/Music; `priority` 1–3; `concurrency` → USoundConcurrency (`max_count` = MaxCount, `resolution` StopOldest/PreventNew, `retrigger_ms` = RetriggerTime) |
| `clip` | роль клипа драйвера анимации (`LungeAttack`, `HitReact`, `DeathSettle`); путь AnimSequence (`sequence`) или клип у каждого скелета (`sequence_by_fighter`: `FHeroSpec.Key` → путь, DE-003), или `missing`; `null` — клипа у CUE нет (CUE-008, F-03). Валидатор проверяет, что `.uasset` каждого пути есть в `Content` |
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

### 3.1 Шкала боя, смерти и начала хода (DE-003, 2026-10-04)

Числа — из окончательных решений по живому исследованию DE ([01-decisions.md](../../../game-design/de-footage/task/01-decisions.md) F-01, F-03, F-04, F-07, F-09 и «Резолюция ревью»), основание — строки [timings-live.csv](../../../game-design/de-footage/live-2026-10-04/timings-live.csv). Схема `unmatched.cue-table/1` не допускает удержаний как полей строки CUE, поэтому они записаны здесь. В таблице `duration_ms` CUE-010/011/013 — анимированная часть, она блокирует ввод ≤ 1 с; удержания ниже ввод не блокируют: клик, Space или Enter их пропускают. Реализация в диспетчере, трассе и фикстурах — DE-018 (W-14) и DE-019 (W-16). DE-018 сделал шкалу боя: удержания живут внутри показа CUE-010 как `hold` (§4 D12), этапы — строки `CUE combat` (§5), гейт — C1–C7 (§6). Этапы смерти — DE-019 (от строки `stage=fall`): строки `CUE death` (§5), гейт DS1–DS6 (§6).

| Параметр | Значение (×1) | Скоростью | Пропуск | Основание |
| --- | --- | --- | --- | --- |
| CUE-008 объявление | 600 (+150), прицел и вспышка, **без клипа** | масштаб. | да | F-03; TL `combat_intro_to_defense_prompt` |
| CUE-010 анимация раскрытия и слэма | 800: переворот 130–200 на месте, атакующая первой, защитная +120; слэм ~180 | масштаб. | да | F-01; TL `defense_check_to_reveal`, `reveal_to_score` |
| `combat.readHoldMs` — «прочитать карту» | 1000, если на раскрытых картах есть текст эффекта, иначе 0 | нет | да | F-01; TL `reveal_to_score` (DE ~3000) |
| `combat.effectStepMs` — строка эффекта | 600 на сработавшую строку: подсветка 400 (масштаб.) + 200 | частично | да | F-01; TL `reveal_to_score_one_effect` (DE +1,6–1,7 с) |
| `combat.slamToLungeMs` — пауза «счёт» | 300 | нет | да | F-01; TL `score_to_attack_anim_start` (DE 1983) |
| Метка исхода «победил …» / «защита держит» | со слэма до конца CUE-011, ~1,5 с | нет | да | F-01; TL `wins_ribbon_hold` (DE 2500, не копируем) |
| Вступление CUE-011 — LungeAttack атакующего | старт = конец CUE-010; play rate × скорость | масштаб. | клип ≤ 0,9 с не обрывается | F-03, «Резолюция» п. 4 |
| Кадр контакта | AnimNotify `Contact` (DE-010); фолбэк — кадр профиля: Arthur к. 7 = 292, Merlin к. 8 = 333, Medusa к. 8 = 333 (выпуск стрелы), Harpy к. 7–9 = 292–375 мс | масштаб. | — | `art/pipeline-candidates/*/build-profiles/*-h2anim.json` |
| HitReact цели + заливка `FxFlash` | в кадр контакта; 450 (летально 550) | нет | клип не обрывается | F-03; TL `target_red_flash`, `target_red_flash_lethal` |
| «−N» | контакт +60; 900 × скорость (×0,5 → 450, ×1,5 → 1350) | масштаб. | да | F-04, SD-49; TL `hit_to_minus_n_popup`, `damage_popup_minus_n` |
| Новое число HP | контакт +80 | нет | — | F-03; TL `hit_to_hp_number` |
| CUE-011 `duration_ms` | 900 **от кадра контакта**; вступление в неё не входит | — | — | «Резолюция» п. 4 |
| Урон 0 | выпад играется, HitReact нет, метка «защита держит» | — | — | F-03 |
| Звук удара CUE-011 | в кадре контакта, а не в момент снапшота | — | — | SD-51; TL `sound_hit_vs_contact_frame` |

Бой без защиты, на раскрытой карте есть текст эффекта, сработавших строк 0: 600 + 800 + 1000 + 300 + ~300 + 900 ≈ **3,9 с**; без текста — ≈ 2,9 с; +0,6 с на каждую строку. Камера неподвижна (D-10). Крупные карты боя — в слое HUD у левого и правого края поля, не над центром доски (SD-48 п. 4).

Смерть (CUE-013), от кадра контакта, одна схема на все 6 v2-фигур (F-09):

| Этап | Герой (Arthur, Medusa) | Помощник (Merlin, Harpy) |
| --- | --- | --- |
| HitReact + заливка | 0–450 | 0–450 |
| DeathSettle (CUE-013 `duration_ms` 950 = клип 875 + запуск) | 450–1325 | 450–1325 |
| Крест на сердце плашки | +1100 | +1100 |
| Неподвижно | 300 | 0 |
| Растворение цветом команды С-11 через `Fade` (вид — DE-011; до арт-приёмки простой fade) | 500 | 400 |
| Фигура исчезла | ≈ 2125 | ≈ 1725 |
| Экран результата (CUE-016, только смерть героя) | исчезновение + 1000, удар → экран ≈ 3,1 с | — |

Начало хода (CUE-015, F-07): кольцо у портрета активного игрока у обеих сторон — вспышка всего обода 1000 мс, затем тлеющее кольцо (opacity ≈ 0,35, без искр) до конца хода; reduced motion — статичное кольцо. Баннер «Ваш ход» 600 мс только на свой ход. Ввод своего хода открыт с кадра применения снапшота: кольцо и баннер его не задерживают (SD-47).

## 4. Семантика диспетчера (нормативно)

Правила пронумерованы; эталонная модель `ReferenceDispatcher` исполняет их в этом порядке, фикстуры фиксируют результат.

- **D1. Время.** События обрабатываются в порядке поступления, `t` (мс от начала партии) не убывает. Перед каждым событием завершаются показы, чей конец ≤ `t` (строка `done`).
- **D2. Дедупликация.** Серверный CUE идентифицируется тройкой `(cueId, subject, seq)`. Первая тройка показывается, повтор (тот же seq по HTTP и WS) даёт `result=duplicate` без показа. Общий seq у разных CUE одного снапшота допустим (урон и смерть — seq 30).
- **D3. Устаревшее.** Серверный CUE с seq меньше наибольшего уже показанного — `result=stale` (снапшот старше применённого; 08 §6.3). Исключение — CUE постановки (`staged`): CUE-011 из кадра контакта (DE-018) и CUE-013 из падения боя (DE-019) идут с seq своего боя позже, чем приходят более новые снапшоты (следующий ход может объявить атаку, пока бой ещё ставится). К ним D3 не применяется; D2 и D4 применяются. Найдено живой приёмкой прогона C (2026-10-05, Sarpedon: CUE-011 seq 24 после CUE-008/009 seq 28/29 был `stale`, гейт C5); фикстура `staged-hit-after-newer-seq`.
- **D4. Реконнект.** Событие восстановления с `recovered_seq = R` пишет `CUE reconnect recovered_seq=R`, обрывает все активные показы (`cut=reconnect`), и дальше любой серверный CUE с seq ≤ R — `stale`. Пропущенное не проигрывается; сразу финальное состояние и тост CUE-018.
- **D5. Разрыв.** Повторный сигнал разрыва, пока связь не восстановлена, — `duplicate`.
- **D6. Замена.** Новый показ обрывает активный показ того же CUE: по `replace_scope` у любого объекта (`cue`) или только у того же `subject`. Метка обрыва — `replace`, для `jump_to_final` — `jump`. `cascade` не обрывает.
- **D7. Прерывание.** Показ CUE X обрывает активные показы тех CUE, у которых X в `interrupted_by` (`cut=interrupt`).
- **D8. Звук: частота.** Если с прошлого звука этого CUE прошло меньше `retrigger_ms`, звук не играет (`sfx=throttled`), остальной показ идёт.
- **D9. Звук: одновременность.** При `max_count` активных звуках этого CUE: `StopOldest` останавливает самый старый (строка `CUE sfx stop … reason=concurrency`), `PreventNew` не играет новый (`sfx=limited`).
- **D10. Отсутствие ассета.** Если путь не задан или ассет не загрузился, канал получает `missing`, показ получает `result=fallback`, UE-адаптер пишет Warning и выполняет `fallback.behaviour` из 07. Длительность и `done` сохраняются.
- **D11. Сокращённые анимации.** При включённой UI-ACC-006 длительность `shorten` ≤ `max_ms`, `snap` = 0; в строке `reduced=1`. `keep` не меняется (`reduced=0`).
- **D12. Длительность.** Показ длится `duration_ms` (или шаг × клетки); при 0 `done` пишется сразу. Звук считается активным на ту же длительность. DE-018: событие может задать свою длину (`duration_ms` — скорость анимации постановки) и **удержание** `hold_ms` — пропускаемое время чтения внутри CUE-010 между переворотом и слэмом. Удержание удлиняет показ, не сокращается reduced motion, строка `done` пишет `hold=<мс>`; блокирующая ввод часть показа — `ms − hold` (G5). Пропуск во время показа укорачивает удержание (`done` переезжает). Этапы смерти §3.1 — DE-019: показ CUE-013 (950 мс, `subject=<павший>`) стартует в кадр падения, этапы после него — строки `CUE death` (§5), не показы диспетчера.

## 5. Трасса

Строки пишет `FS08Trace` без изменений формата; префикс лога допустим, гейт ищет подстроку `CUE `. Значения без пробелов.

```
CUE fx id=<CUE-NNN> subject=<id> seq=<N|-> t=<ms> vfx=<имя|none|missing> sfx=<имя|none|missing|throttled|limited> clip=<имя|none|missing> mat=<FxFlash|Rim|Fade|none> socket=<Weapon|Head|Root|Base|-> reduced=<0|1> result=<spawned|fallback>
CUE fx id=<CUE-NNN> subject=<id> seq=<N|-> t=<ms> result=<duplicate|stale>
CUE fx done id=<CUE-NNN> subject=<id> seq=<N|-> t=<ms> ms=<длительность> cut=<0|replace|jump|interrupt|reconnect> [hold=<мс>]
CUE sfx stop id=<CUE-NNN> subject=<id> seq=<N|-> t=<ms> reason=concurrency
CUE reconnect recovered_seq=<R> t=<ms>
CUE settings reduced_motion=<0|1> t=<ms>
```

`имя` — короткое имя ассета (последний сегмент soft path). Строки `CUE damage` и `CUE move` текущего S08 остаются и гейтом игнорируются (урон постановки помечен `staged=contact`: он показывается в кадре контакта).

Постановка боя (DE-018, шкала §3.1). Время `t` — запланированное время этапа на часах клиента (мс), этап пишется в кадре, когда наступил:

```
CUE combat seq=<n> stage=start t=<ms> attacker=<id> target=<id> text=<0|1> lines=<n> damage=<n> lethal=<0|1> shown=<0|1> speed=<x> flip=<мс> contact=<мс> src=<notify|profile|default> a=<A> d=<D> outcome=<win|hold>
CUE combat seq=<n> stage=read t=<конец> ms=<факт> skipped=<0|1>          (только при тексте эффекта на раскрытой карте)
CUE combat seq=<n> stage=effect t=<конец> i=<k> ms=<факт> skipped=<0|1>  (на каждую сработавшую строку)
CUE combat seq=<n> stage=slam t=<ms> a=<A> d=<D> outcome=<win|hold>       (слэм и метка исхода)
CUE combat seq=<n> stage=pause t=<конец> ms=<факт> skipped=<0|1>          (пауза «счёт»)
CUE combat seq=<n> stage=lunge t=<ms> attacker=<id>                       (LungeAttack — вступление CUE-011)
CUE combat seq=<n> stage=contact t=<ms> offset=<мс> window=<мс> src=<…>  (кадр контакта; window — CUE-011 от контакта)
CUE combat seq=<n> stage=hit t=<ms> target=<id> tint=<450|550>            (HitReact + заливка)
CUE combat seq=<n> stage=minus t=<ms> amount=<n> life=<мс>                («−N»)
CUE combat seq=<n> stage=hp t=<ms> from=<a> to=<b>                        (новое число HP)
CUE combat seq=<n> stage=fall t=<ms> target=<id>                          (летально: начало DeathSettle, F-09)
CUE combat seq=<n> stage=skip t=<ms> src=<click|space|enter>
CUE combat seq=<n> stage=end t=<ms> total=<мс> skipped=<0|1> cut=<0|replace|reconnect|jump>
```

Смерть (DE-019, таблица F-09 §3.1). Падение — кадр, в котором фигура начала DeathSettle: у постановки боя это кадр этапа `fall` (контакт + 450), у прочей смерти (способность, эффект после боя, оборванная постановка) — кадр её снапшота. План (`settle`/`still`/`dissolve`) — собственный план фигуры: v2-фигура 875 / 300 (помощник 0) / 500 (помощник 400); без MIC растворения `dissolve=0 style=none` (фигура скрывается после неподвижности); фигура без клипа (серая доска, откат) — все нули, исчезает в кадр падения:

```
CUE death seq=<n> stage=fall t=<ms> fighter=<id> hero=<0|1> staged=<0|1> settle=<мс> still=<мс> dissolve=<мс> style=<fade|ash|none> gone=<ms>
CUE death seq=<n> stage=mark t=<ms> fighter=<id> heart=<dark|crossed>   (падение + 650 = контакт + 1100; dark — до приёмки глифа креста DE-012)
CUE death seq=<n> stage=dissolve t=<ms> fighter=<id> ms=<мс> style=<…>   (только при растворении)
CUE death seq=<n> stage=gone t=<ms> fighter=<id>
RESULT screen seq=<n> t=<ms> due=<ms> gameOver=<ms> heroGone=<ms|-> wait=<мс>
```

`RESULT screen` — кадр, в котором открылась панель результата (CUE-016): `due` = max(GAME_OVER, исчезновение героя + 1000), без смерти героя — кадр GAME_OVER; страховка — GAME_OVER + 10 000. Пока у постановки летальный удар по герою не дошёл до падения, экран не открывается. Состояние GAME_OVER применяется сразу: ждёт только панель.

`total` = CUE-008 (600 × скорость) + (конец − раскрытие) — величина «бой ≈ 3,9 с» из 01 F-01. CUE-010 — `subject=scene`, `done` с `hold=`; CUE-011 — `subject=<цель>`, показ из кадра контакта. Без урона (защита держит) или когда урон уже показан во время паузы боя (`shown=1`) строк `hit`/`minus`/`hp`/`fall` и CUE-011 нет. Пример — фикстура `combat-staging-text`.

Пример (фикстура `attack-interrupt`):

```
CUE fx id=CUE-008 subject=arthur seq=50 t=0 vfx=NS_Test_Flash sfx=SW_Test_Attack clip=none mat=none socket=Weapon reduced=0 result=spawned
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
| G5 | блокирующий ввод CUE длился больше 1000 мс (кроме терминального); у показа с `hold=` считается `ms − hold` |
| G6 | звуков одного CUE одновременно больше `max_count` (с учётом `sfx stop`) |
| G7 | звуки одного CUE чаще `retrigger_ms` |
| G8 | `result=fallback` не совпадает с наличием `missing` в vfx/sfx/clip |
| G9 | время строк убывает |

Трассы перемещения `MS-CUE move seq=… fighter=… order=… of=… kind=… steps=… source=… start=… ms=… snapped=… path=…` (MS-T-15, move-selection 04 §9) тот же гейт проверяет отдельно: M1 — формат и поля; M2 — набор строк одного seq (ровно `of` подряд, `order` 0..of−1, бойцы без повторов); M3 — шаги, вид и путь (`place` и `straight` — 1 шаг, в пути steps+1 клеток); M4 — `start`/`ms`/`snapped` по расписанию 04 §6.3 с потолками CUE-007 (±1 мс); M5 — строк меньше `--min-ms-cue N`.

Постановку боя `CUE combat …` (DE-018) гейт проверяет по seq: C1 — формат и поля `start`; C2 — ровно одна постановка на seq и один `end` (повтор seq не даёт второго показа, ACC-012); C3 — порядок этапов `start → read → effect → slam → pause → lunge → contact → hit → minus → hp → fall → end` и неубывающее время (`skip` — в любом месте); C4 — удержания: `read` есть тогда и только тогда, когда `text=1`, 1000 мс (меньше — только `skipped=1`), строк `effect` ровно `lines`, каждая 400 × скорость + 200, пауза 300, слэм = раскрытие + `flip` + удержания, `hold` у CUE-010 = удержаниям, пауза от конца слэма, выпад в конце паузы, контакт = выпад + `contact`; C5 — от кадра контакта: `hit` в кадре контакта с заливкой 450 (летально 550), `minus` +60, `hp` +80, `fall` +450 только у летального, CUE-011 с цели из кадра контакта и не дольше постановки, без урона — ни одной из этих строк, `outcome=win` тогда и только тогда, когда урон > 0, конец = контакт + max(`window`, 80, 450 у летального); C6 — `total`. Прерванная постановка (`cut≠0`) проверяется только по C1–C3. C7 — завершённых постановок меньше `--min-combat N` (живой бой).

Смерть `CUE death …` и экран `RESULT screen …` (DE-019): DS1 — формат и поля `fall`, поля `RESULT screen`; DS2 — одна смерть на (seq, боец), у неё ровно одна `mark` и одна `gone`, ничего до `fall`; DS3 — этапы F-09 от падения: `mark` +650, `dissolve` = падение + `settle` + `still` (есть тогда и только тогда, когда `dissolve` > 0), `gone` = + `dissolve` и равно полю `gone`, `style=none` тогда и только тогда, когда `dissolve=0`, у v2-фигуры (`settle` > 0) план 875 / 300 у героя и 0 у помощника / 500 или 400 (0 — фолбэк без MIC); DS4 — `staged=1`: есть этап `fall` постановки того же seq и цели, падение смерти — не раньше и не позже 100 мс после него; DS5 — `due` по правилу выше (исчезновение героя из смертей после прошлого экрана), `heroGone` совпадает, экран не раньше `due` и не позже `due` + 100, `wait` = `t` − `gameOver`. DS6 — смертей меньше `--min-death N` (живая партия до GAME_OVER). Сводка: `death_sets`, `death_heroes`, `result_screens`, `hit_to_screen` (контакт постановки → экран, «≈ 3,1 с»).

Сводка гейта: `presented`, `spawned`, `fallback`, `duplicate`, `stale`, `done`, `unique_triples`, `ms_cue`, `ms_cue_sets`, `ms_cue_sources`, `combat_sets`, `combat_cut`, `combat_skipped`, `combat_totals`, `death_sets`, `death_heroes`, `result_screens`, `hit_to_screen`. Для ACC-012 в пакете доказательств записывается строка `CUE_TRACE PASS {…}`.

## 7. Фикстуры без мира

`python tools/s08/cue_contract/cue_contract.py run-fixtures` — эталонная модель даёт `expect_trace` строка в строку, гейт на ней чист, сводка совпадает с `expect_summary`; негативные трассы отклоняются ровно с кодами `expect_error_codes`.

| Фикстура | Что закрепляет |
| --- | --- |
| `dedupe-http-ws` | D2: один показ на seq, повтор по WS — `duplicate` (ACC-012, QA-007) |
| `reconnect-no-replay` | D4, D5: разрыв, повторный разрыв, восстановление R=14, запоздавшие seq 12 и 14 — `stale`, seq 15 — показ (QA-108) |
| `sfx-concurrency-stop-oldest` | D9: третий звук урона останавливает старейший, VFX показываются все |
| `hover-retrigger` | D6 (`replace_scope: cue`), D8: контур переходит сразу, тик не чаще 1/150 мс |
| `missing-assets-fallback` | D10: таблица без VFX и звука (клип — свой у фигуры) и незагрузившийся тестовый VFX → `fallback`, длительности сохраняются |
| `reduced-motion` | D11: урон 900 → 100 мс, перемещение `snap`, наведение `keep` |
| `attack-interrupt` | D7: объявление атаки (без клипа, F-03) обрывается уроном через 300 мс |
| `stale-seq-and-move-jump` | D3, D6 (`jump`): новое перемещение той же фигуры, запоздавший seq 59 |
| `staged-hit-after-newer-seq` | D3 `staged`, D2, D4: CUE-011 постановки seq 24 после CUE-008/009 seq 28/29 показывается, повтор — duplicate, обычный seq 25 — stale, staged после реконнекта R=30 — stale |
| `combat-staging-text` | DE-018: бой по шкале F-01 — атака без защиты, текст эффекта, 0 строк, урон 2: CUE-010 `ms=1800 hold=1000`, контакт по notify 292, «−N» +60, HP +80, итог 3892 мс ≈ 3,9 с |
| `combat-staging-lethal-skip` | DE-018: летальный удар по помощнику без текста, пропуск Space в паузе «счёт» (100 мс), заливка 550, `fall` +450, итог 2733 |
| `combat-staging-defense-holds` | DE-018: урон 0 — выпад без HitReact, «−N» и CUE-011; пропуск кликом в чтении (380 мс), `hold=380` |
| `neg-*` (5) | гейт ловит G2, G3, G4+G8, G5+G6; постановка боя — C2, C3, C5, C6 (`neg-combat-staging`) |

**Перенос в C++ (DE-018).** `Unmatched.S08.CueDispatcher.Table` сверяет встроенные строки CUE-008…011, 013, 014 с `cue-table.json` поле за полем; `Unmatched.S08.CueDispatcher.Fixtures` прогоняет через `FS08CueDispatcher` каждый сценарий этих строк без блока `staging` (attack-interrupt, dedupe-http-ws, missing-assets-fallback, sfx-concurrency-stop-oldest) и сравнивает трассу побайтно; `Unmatched.S09.CombatStage.Fixtures` строит из блока `staging` ту же постановку через `FS09CombatStage` и сравнивает с `expect_trace` фикстур `combat-staging-*` побайтно. Фикстуры строк вне этого среза (наведение, перемещение, связь) переносятся с GD-044. Эталонная модель на Python — исполняемая спецификация, её вывод не заменяет C++-тест.

## 8. Эскиз интерфейса (для GD-044, не код)

- `FS08CueEvent { FName CueId; FString Subject; TOptional<int32> Seq; int32 Steps; int64 TimeMs; }`.
- `FS08CuePlan { FName CueId; FString Subject; TOptional<int32> Seq; ES08CueResult Result; TSoftObjectPtr<UNiagaraSystem> Vfx; TSoftObjectPtr<USoundBase> Sfx; FName Socket; ES08ClipRole Clip; FName CpdParam; int32 DurationMs; bool bReduced; }`.
- `FS08CueDispatcher::Feed(const FS08CueEvent&, TArray<FS08CuePlan>& Out, TArray<FString>& TraceLines)`; `OnReconnect(int32 RecoveredSeq)`; `SetReducedMotion(bool)`; `Tick(int64 NowMs)` для `done`.
- UE-адаптер (`AS08FlowGameMode` или компонент презентации) исполняет план: `UNiagaraFunctionLibrary::SpawnSystemAttached` с пулом, `UGameplayStatics::PlaySound2D`/`SpawnSoundAttached` с Concurrency из таблицы, `SetCustomPrimitiveDataFloat`, драйвер анимации (`PlayOneShot(role)`), виджет. Решений о повторах адаптер не принимает.
- Новые типы события в `ComputeCues`: `AttackDeclared`, `FighterDefeated`, `FighterHealed`, `AbilityTriggered`, `TurnChanged` (R2.4: скрытие фигуры при смерти задерживается до ≤ 950 мс, QA-101).

## 9. Открытые вопросы

1. Стиль VFX (AD-OPEN-34) и библиотека ART-010 — ассеты таблицы остаются `missing` до них.
2. Длительности HitReact (0,4 с в 04 против 0,9 с CUE-011) и DeathSettle (0,9 против ≤ 0,95 с) — таблица берёт 07; при изменении 07 валидатор покажет расхождение. Закрыто DE-003: CUE-011 = 900 мс от кадра контакта, внутри — клип HitReact 417 мс и заливка 450 / 550 мс (§3.1).
3. CUE-014 у Medusa: луч от сокета `Head` к цели, у Arthur — свечение `Weapon`. Сейчас строка задаёт `Weapon`; сокет по герою — поле DataAsset героя (GD-044).
4. Бюджет: худший набор 2×CUE-011 + 013 + 007 + 014 — ΔGPU ≤ 1 мс по ProfileGPU (bench fx/ui меморандума §2). На DX12 + Lumen эмиссивные частицы могут попадать в Lumen-сцену: проверить на bench, при необходимости исключить эффекты из непрямого освещения.

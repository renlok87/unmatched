# Контракт FS08CueDispatcher (CUE-слой презентации)

Срез 2026-09-29, волна 4, задача W4-D. **Статус: предложено.** Это спецификация, JSON-схема, таблица данных и тестовые фикстуры без мира. Код движка здесь не пишется: реализация — GD-044 (S11, «Cue subsystem»), ассеты — ART-010 и GD-049.

**DE-018 (2026-10-04, первый срез GD-044):** диспетчер реализован для боевых строк CUE-008…011, 013, 014 — `FS08CueDispatcher` ([S08CueDispatcher.h](../../../../unreal/Unmatched/Source/Unmatched/S08/S08CueDispatcher.h)), постановка боя по §3.1 — `FS09CombatStage` ([S09CombatStage.h](../../../../unreal/Unmatched/Source/Unmatched/S09/S09CombatStage.h)), адаптер — `AS08FlowGameMode`. Остальные строки (наведение, перемещение, начало хода, связь) — по-прежнему GD-044.

**DE-019 (2026-10-05):** смерть по этапам F-09 и переход к экрану результата — `FS09DeathStage` и `FS09ResultGate` ([S09DeathStage.h](../../../../unreal/Unmatched/Source/Unmatched/S09/S09DeathStage.h)); фигура сама играет DeathSettle, неподвижность и растворение DE-011 (`AS08FighterActor`, `S08HeroesV2::FDeathPlan`). Трасса — строки `CUE death` и `RESULT screen` (§5), гейт — DS1–DS6 (§6).

Основание: меморандум engine-gate §1 п.8 («FS08CueDispatcher (таблица, трасса `CUE fx … result=`, тесты без мира)») и исследование R3.4 (вариант B: мира-независимый диспетчер по данным). Норматив событий — [07-animation-vfx-audio.csv](../../../game-design/07-animation-vfx-audio.csv) (18 CUE). Сеть и повторы — [08 §6.3](../../../game-design/08-integration-decisions.md). Доступность — [02](../../../game-design/02-ux-ui-spec.md) UI-ACC-005/006. Сокеты — [rig-contract.json](../../../art-pipeline/rig/rig-contract.json) `ue_import.sockets_v2`.

| Файл | Что это |
| --- | --- |
| [cue-table.json](cue-table.json) | данные 18 CUE (`unmatched.cue-table/1`): ассеты, сокет, длительности, поведение; системы VFX — плановые пути `/Game/S08/FX/**` со `status: missing`, пока их не сделают строки FX (ревизия `fx-p4-2026-10`, FX-01) — это и есть missing-report ART-010; клипы HitReact и DeathSettle есть у всех v2-фигур (DE-003) |
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
| `pose` | только у CUE-007 (DE-021, 01 F-02): поза фигуры на ходу — `hop_height_rel` 0 (подскока нет, D-DE-02; A/B 0.08), `travel_lean_deg` 10 за `lean_in_ms` 60, `start_turn_ms` 50, `turn_ms` 120 (доворот на вершине без остановки), `settle_ms` 150 (возврат в Idle), `ease_ends` false; скоростью не масштабируется. Умолчания `FS08MoveAnimParams` равны этим значениям (UE `Unmatched.S08.MoveAnim.CueTrace`) |
| `feedback_delay_ms`, `blocks_input`, `skippable` | из 07; блокировка ввода ≤ 1000 мс, кроме терминального CUE-016 |
| `vfx` | Niagara: `system` (soft path); пока ассета нет — `status: missing` + `missing_reason` «ассет не создан: FX-xx», а `system` несёт плановый путь (FX-01); `fx_row` — строка [vfx.csv](../../../game-design/visual/06-tasks/vfx.csv), которая делает систему; `attach` `socket`/`world`, `socket` (`Weapon`, `Head`, `Root`, `Base`; при `world` — `null`); `sim: cpu`, `deterministic: true`, `prewarm: true`. Вид — [02 §9.2](../../../game-design/visual/02-visual-design.md): пыль CUE-007, шевроны на земле CUE-008, звезда у точки контакта CUE-011 (мир, не `Head`), точки лечения от `Base` CUE-012, угольки «пепла» CUE-013, по герою CUE-014 (FX-28); у CUE-005, 006, 009, 010 VFX нет (HUD или обод фигуры) |
| `sfx` | `sound` — **USoundBase** (SoundWave, SoundCue и MetaSoundSource взаимозаменяемы без правки кода); `sound_class` UI/SFX/Music; `priority` 1–3; `concurrency` → USoundConcurrency (`max_count` = MaxCount, `resolution` StopOldest/PreventNew, `retrigger_ms` = RetriggerTime) |
| `clip` | роль клипа драйвера анимации (`LungeAttack`, `HitReact`, `DeathSettle`); путь AnimSequence (`sequence`) или клип у каждого скелета (`sequence_by_fighter`: `FHeroSpec.Key` → путь, DE-003), или `missing`; `null` — клипа у CUE нет (CUE-008, F-03). Валидатор проверяет, что `.uasset` каждого пути есть в `Content` |
| `material` | параметр Custom Primitive Data мастера `M_UM_Figure`: `FxFlash` (5–8), `Rim` (9–10), `Fade` (11) — раскладка меморандума §1 п.4. FX-01: обод `Rim` — наведение CUE-001 (`fx.rim` 0,6) и защита CUE-009 (импульс 300 мс, ВР-23); CUE-011 — белая вспышка `FxFlash` 70 мс и обод (`note`), красная заливка только с `-S08HitTintLegacy` (ВР-20) |
| `ui`, `marker`, `postprocess` | виджет HUD (CUE-006 — UMG-вспышка рамки, ВР-74), маркер игрового слоя (CUE-003 — `M_UM_MovePlate`), постпроцесс: грейд CUE-016 по FX-34 (`profile_delta`, ВР-24) и насыщенность × 0,7 CUE-017 с возвратом в CUE-018 (FX-35, FX-36) |
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
- `status: present` ставится только на ассет, который есть в `Content` (`validate-table` проверяет `.uasset`); плановый путь при `missing` показ не меняет — `vfx=missing`, `result=fallback`. Слова старого вида («луч», «зелёные частицы», `M_HighlightGameLayer`, «встряска») в таблицу и 07 не возвращаются — их тоже ловит `validate-table` (FX-01).
- Звук: SoundClass Master → UI / SFX / Music (ползунки UI-ACC-007..009); окно без фокуса уже заглушено движком (`[Audio] UnfocusedVolumeMultiplier=0.0`), что совпадает с UI-ACC-011.

### 3.1 Шкала боя, смерти и начала хода (DE-003, 2026-10-04)

Числа — из окончательных решений по живому исследованию DE ([01-decisions.md](../../../game-design/de-footage/task/01-decisions.md) F-01, F-03, F-04, F-07, F-09 и «Резолюция ревью»), основание — строки [timings-live.csv](../../../game-design/de-footage/live-2026-10-04/timings-live.csv). Схема `unmatched.cue-table/1` не допускает удержаний как полей строки CUE, поэтому они записаны здесь. В таблице `duration_ms` CUE-010/011/013 — анимированная часть, она блокирует ввод ≤ 1 с; удержания ниже ввод не блокируют: клик, Space или Enter их пропускают. Реализация в диспетчере, трассе и фикстурах — DE-018 (W-14) и DE-019 (W-16). DE-018 сделал шкалу боя: удержания живут внутри показа CUE-010 как `hold` (§4 D12), этапы — строки `CUE combat` (§5), гейт — C1–C7 (§6). Этапы смерти — DE-019 (от строки `stage=fall`): строки `CUE death` (§5), гейт DS1–DS6 (§6).

| Параметр | Значение (×1) | Скоростью | Пропуск | Основание |
| --- | --- | --- | --- | --- |
| CUE-008 объявление | 600 (+150), прицел и вспышка, **без клипа** | масштаб. | да | F-03; TL `combat_intro_to_defense_prompt` |
| CUE-010 анимация раскрытия и слэма | 800: переворот 130–200 на месте, атакующая первой, защитная +120; слэм ~180 | масштаб. | да | F-01; TL `defense_check_to_reveal`, `reveal_to_score` |
| `combat.readHoldMs` — «прочитать карту» | 1000, если на раскрытых картах есть текст эффекта, иначе 0 | нет | да | F-01; TL `reveal_to_score` (DE ~3000) |
| `combat.effectStepMs` — строка эффекта | 600 на сработавшую строку (журнал сервера, R-01/R-02): подсветка 400 (масштаб.) + 200 | частично | да | F-01; TL `reveal_to_score_one_effect` (DE +1,6–1,7 с) |
| `combat.slamToLungeMs` — пауза «счёт» | 300 | нет | да | F-01; TL `score_to_attack_anim_start` (DE 1983) |
| Метка исхода «победил …» / «защита держит» | со слэма до конца CUE-011, ~1,5 с | нет | да | F-01; TL `wins_ribbon_hold` (DE 2500, не копируем) |
| Вступление CUE-011 — LungeAttack атакующего | старт = конец CUE-010; длительность × скорость (play rate = 1 / скорость: ×0,5 → 2, ×1,5 → 0,67; «Нет» — клип не играется, контакт в кадр выпада; DE-025) | масштаб. | клип ≤ 0,9 с не обрывается | F-03, «Резолюция» п. 4 |
| Кадр контакта | AnimNotify `Contact` (DE-010); фолбэк — кадр профиля: Arthur к. 7 = 292, Merlin к. 8 = 333, Medusa к. 8 = 333 (выпуск стрелы), Harpy к. 7–9 = 292–375 мс | масштаб. | — | `art/pipeline-candidates/*/build-profiles/*-h2anim.json` |
| HitReact цели + заливка `FxFlash` | в кадр контакта; 450 (летально 550) | нет | клип не обрывается | F-03; TL `target_red_flash`, `target_red_flash_lethal` |
| «−N» | контакт +60; 900 × скорость (×0,5 → 450, ×1,5 → 1350) | масштаб. | да | F-04, SD-49; TL `hit_to_minus_n_popup`, `damage_popup_minus_n` |
| Новое число HP | контакт +80 | нет | — | F-03; TL `hit_to_hp_number` |
| CUE-011 `duration_ms` | 900 **от кадра контакта**; вступление в неё не входит | — | — | «Резолюция» п. 4 |
| Урон 0 | выпад играется, HitReact нет, метка «защита держит» | — | — | F-03 |
| Звук удара CUE-011 | в кадре контакта, а не в момент снапшота | — | — | SD-51; TL `sound_hit_vs_contact_frame` |

Бой без защиты, на раскрытой карте есть текст эффекта, сработавших строк 0: 600 + 800 + 1000 + 300 + ~300 + 900 ≈ **3,9 с**; без текста — ≈ 2,9 с; +0,6 с на каждую строку. Камера неподвижна (D-10). Крупные карты боя — в слое HUD у левого и правого края поля, не над центром доски (SD-48 п. 4).

**Источник сработавших строк (R-01, прогон H 2026-10-05).** Сервер кладёт в снимок, который разрешил бой, публичную запись `metadata.lastCombat` ([16-network-contract.md](../../../game-design/16-network-contract.md) §5.1): `seq` — номер этого снимка, итог боя (`finalAttack`, `finalDefense`, `defenderDamage`, `attackerWon`, отмены карт) и `appliedEffects` — сработавшие эффекты карт по порядку применения. У каждой записи есть `timing` (`IMMEDIATELY` / `DURING` / `AFTER`), `side`, `source` (карта: instance id, каталожный id, имя), `kind`, `outcome` (`APPLIED` / `CHOICE` / `NO_TARGETS` / `MANUAL` / `FAILED`), `value`, `targets` (только бойцы и игроки), печатный `text` и `parent` (индекс записи-причины, например CHOOSE_ONE для выбранной опции). Какие записи дают строку эффекта (`lines` в строке `CUE combat`, +600 мс каждая), решил клиент в R-02 (ниже). Пока бой стоит на паузе выбора, записи нет: она появляется в снимке, который бой завершил. Способности героев (модификаторы, хуки после боя) в журнал пока не пишутся — CUE-014 / GD-044.

**Строки эффекта на клиенте (R-02, прогон H 2026-10-05).** `FS09LastCombat` ([S09CombatEffectLog.h](../../../../unreal/Unmatched/Source/Unmatched/S09/S09CombatEffectLog.h)) читает `metadata.lastCombat` снимка, который закрыл бой. Запись — этого боя, если её `seq` больше seq последнего применённого снимка открытого боя и не больше seq закрывшего снимка (снимки могли слиться), а атакующий и цель совпадают; иначе строк 0 (`src=other`), без записи — тоже 0 (`src=none`, сервер до R-01). Строка эффекта — запись с исходом `APPLIED`, `CHOICE` или `MANUAL`; выбранная опция CHOOSE_ONE (`parent`) не отдельная строка, а продолжение строки родителя («→ опция»); `NO_TARGETS` и `FAILED` строки не дают (пропуск без целей объясняет тост DE-016/DE-020). Поле `hidden` клиент не декодирует вовсе, поэтому владелец эффекта и соперник получают одинаковые строки. Если строка есть, а раскрытие не назвало карту (переподключение между открытием и итогом), удержание чтения 1000 всё равно включается: эффект карты сработал. Строки показываются на панели карты у края поля (атакующая слева, защитная справа) блоком EFFECTS: строка k появляется в начале своего шага 600, первые 400 × скорость подсвечена, затем остаётся до конца постановки; пропуск обнуляет оставшиеся шаги, и все строки встают на панель сразу — пропуск сокращает время, а не прячет текст. Перед постановкой клиент пишет строку `COMBAT-LOG` (§5), гейт — C8/C9 (§6).

**Догоняние очереди показа (R-03, прогон H 2026-10-05).** Состояние никогда не ждёт показа: строка статуса, лента `MS-LOG` и командная панель говорят о последнем применённом seq сразу (ввод открыт с применения, DE-015). Отставать может только постановка боя. Её отставание ограничено политикой `FS09PresentationCatchup` ([S09PresentationCatchup.h](../../../../unreal/Unmatched/Source/Unmatched/S09/S09PresentationCatchup.h)); образец — выпущенные игры, которые режут показ в пользу серверного тайминга (RESEARCH-2026-10-05, вывод 7). Правила:
- **короткая версия** (`hurry`): оставшиеся удержания (чтение, строки эффекта, пауза «счёт») снимаются так же, как пропуск игрока (`stage=skip src=catchup`), а удар (выпад, контакт, HitReact, «−N», HP) играет. Срабатывает, когда постановка отстаёт от более нового применённого снимка дольше T мс (`reason=lag`) или когда открыт более новый бой (`reason=combat`: его объявление и защита не идут под картами старого);
- **мгновенный итог** (`cut`): за постановкой больше K более новых снимков (по разнице seq, слитые снимки считаются по seq; `reason=queue`). Это тот же `Cut`, что у `replace`: удержанные HP и падение отпускаются сразу, `stage=end … cut=catchup`;
- новый **итог** боя по-прежнему заменяет постановку (`cut=replace`): полностью играет только самая свежая;
- `GAME_OVER` выключает политику: экран результата ждёт постановку сам (DE-019, страховка 10 с).

K = `s09.Catchup.MaxQueued` (по умолчанию 3), T = `s09.Catchup.MaxLagMs` (по умолчанию 1500 мс); 0 выключает только своё правило (`reason=queue` при K = 0, `reason=lag` при T = 0), `-S09CatchupQueued=` / `-S09CatchupLagMs=` перекрывают CVar. Правило `reason=combat` (открыт более новый бой) переключателя не имеет и работает всегда: K = T = 0 не выключает догоняние целиком (приёмка H, О-2). Текст опережает экран не больше чем на K снимков или на T + хвост короткой версии (остаток CUE-010 ≤ 800 × скорость, кадр контакта × скорость, CUE-011 ≤ 1000): при ×1 и контакте 292 это 3592 мс. Одиночный бой не режется: ход в Unmatched кончается в том же seq (`consumeAction`), и без ответа соперника за T постановка играет полностью. Строки трассы — §5, гейт — C10 (§6).

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

### 3.2 Звук по точкам синхронизации (DE-032, 2026-10-05)

Основание — 02 SD-51, R-12, колонка `sound` в 07 (CUE-002/003/007/011/015/016). Звуков DE нет и не будет (EULA); ассеты — лицензируемая библиотека DE-013 / ART-010. Пока `sfx.sound` в таблице `null`, каждая точка пишет строку `result=fallback`, ничего не играет и ошибок не пишет (D10). Код: `FS08CueSound` (`S08CueSound.h`, без мира) решает, когда и с какой громкостью; адаптер `S08FlowGameModeSound.cpp` играет решение в том же кадре, что и визуальное событие. Строки звука — встроенные (`S08SoundRows::All`), тест `Unmatched.S08.CueSound.Table` сверяет `sound_class`, `priority`, `retrigger_ms` и путь `sound` с этой таблицей.

| Точка | CUE | Кадр звука | Правило |
| --- | --- | --- | --- |
| `ui` | 002 / 003 / 004 | кадр отклика на отпускание (UI-INP-011, SD-46): нажатие HUD сработало → 003, отказано → 004; отпускание на поле: отказ (тост, недопустимая клетка) → 004, отправка команды → 003, выбор своей фигуры → 002, прочая смена выбора → 003, без отклика — без звука | CUE-004 не чаще 1 раза в 300 мс (D8, `result=throttled`) |
| `hit` | 011 | кадр контакта выпада: этап `contact` постановки боя (`due` = его `t`); удар без постановки (каскад после перемещения, способность) — в кадр своего HitReact | не в момент применения снапшота с уроном; урон 0 — без звука |
| `step` | 007 | кадр, в котором фигура начинает ребро: старт перемещения + k × шаг (`due`) | один звук на ребро; прыжок (reduced motion, скорость «Нет», потолок seq) — один звук в кадр посадки (`edge=snap`); пропуск перемещения (MS-E-70) и новое перемещение той же фигуры (`jump_to_final`) снимают оставшиеся шаги (`CUE sound drop`) |
| `turn` | 015 | кадр применения снапшота нового хода (кадр баннера) | только свой ход; начало хода соперника беззвучно (`result=silent reason=opponent`); вход и реконнект посреди хода (`initial`) — ни баннера, ни звука |
| `result` | 016 | кадр открытия экрана результата (`RESULT screen`) | стинг ~2–3 с — длина ассета; кроссфейд музыки — с музыкой GD-049 |

Громкости (DE-025 хранит, DE-032 применяет; 02 SD-55): «Общая» — громкость всего вывода процесса, `FAudioDevice::SetTransientPrimaryVolume`; «Окружение» — громкость класса `Ambience` (звук задника SD-51, пока его нет) поверх общей. Mute даёт 0. Изменение (`US08UserSettings::Save` → `OnChanged`, консоль `s08.Settings master=… ambience=…`) применяется сразу: строка `CUE audio … applied=change`, следующий звук идёт с новым `gain`. При общей громкости 0 точки пишут `result=silent reason=muted`. Одновременность (D9) у звука точек — `USoundConcurrency` ассета, когда ассет появится; частота (D8) решается здесь.

### 3.3 Звук игры: банк, шины, музыка, реплики, окружение (AU-S4, 2026-10-05)

Основание — [02-audio-design.md](../../../game-design/audio/02-audio-design.md), итог —
[07-production-log.md](../../../game-design/audio/07-production-log.md).
- **Банк.** `sfx.bank` строки — id реестра [03-sound-registry.csv](../../../game-design/audio/03-sound-registry.csv),
  `sfx.sound` — его первый вариант. Варианты (до 5) выбирает `FS08CueSound` без повтора; запрос может заменить банк
  (тип удара атакующего, смерть персонажа, стинг героя и исхода) — строка `CUE sound … bank=<id>`. Таблица банка
  генерируется (`tools/audio/ue_bank.py` → `S08AudioBankData.inl`, `S08VoLinesData.inl`).
- **Шины.** Громкость звука = общая (громкость устройства) × шина класса: Music 60, SFX 80, UI 80, VO 80, Ambience 60
  (`CUE audio … music= sfx= ui= vo= subtitles=`). Гейт AU8 считает так же; в старых трассах без полей шин — 100 %.
- **Точка `cue`.** CUE-005 (добор), 006 (розыгрыш схемы), 008 (объявление), 009 (защита), 010 (переворот, слэм),
  012 (лечение), 013 (смерть), 014 (способность), 017/018 (связь) — в кадре своего визуального события.
- **Удары.** Урон 0 — звук блока в кадре контакта (событие `Block` этапа боя). Удары одного кадра — один звук
  (`CMB-HIT-MULTI`, истощение — `CMB-EXHAUST`), остальные строки `result=silent reason=grouped`.
- **Слот `sfx` диспетчера** заполняется только `assets_present` фикстуры (как в C++-раннере): звук CUE играет
  `FS08CueSound`, строки `CUE fx` его не дублируют.
- **Музыка, реплики, окружение** — свои трассы: `MUSIC state=… theme=… t=… [sting=…]`, `VO event=… speaker=… t=…
  result=played|skipped line=… prio=… [reason=…]`, `VO subtitle line=… until=…`, `AMB map=… beds=… spots=…`,
  `AMB spot=…`, `SFX bank=… tag=… class=… t=… sound=… gain=…` (слои и звуки вне CUE).
- **AU-S5 (2026-10-06).** CUE-014 (способность) звучит в точке `cue`. Буст Arthur — `FX-ARTHUR-BOOST`: у атакующего
  при объявлении, у защитника при раскрытии. Луч Medusa — `FX-GAZE-BEAM` при выборе цели взгляда. Остальные новые
  звуки — строки `SFX bank=…`:
  - запрос и отказ взгляда;
  - угасание буста;
  - толчок, кандидаты, расстановка;
  - таймер защиты;
  - вход, комната, панели, инспектор, слот буста;
  - возвращение гарпии, «нет цели», голосовые слои эффектов.

  Перемещение `kind=place` звучит `BRD-PLACE` (банк строки CUE-007 заменён). Главный сабмикс несёт шину микса
  `US08MixLimiterPreset` (подъём +5 дБ, предпросмотровый лимитер −1,5 dBFS); строка
  `AUDIO-MIX limiter ceiling=… lookahead=… makeup=…`. Запись микса включает `-S08AudioRecord=<wav>`; в трассе
  `AUDIO-REC start|stop …`. Гейт этих строк не проверяет.
- **AU-S6 (2026-10-06).** CUE-017 / CUE-018 подаёт клиент: поток партии не готов дольше 1,5 с / снова готов
  (`IsStreamReady()`), с приглушением музыки. Звук экранов вызывается функциями `PlayScreenSound`, `SetAudioPaused`
  и `PlayHeroSelectSting` ([08-screen-audio-hooks.md](../../../game-design/audio/08-screen-audio-hooks.md)).
  Гейт AU5/AU6 прощает опоздание в первых двух кадрах после снимка доказательств (`SHOT captured`, `SHOT late end`),
  если второй кадр идёт не позже чем через 1 с; такие случаи считает `sound_late_shot`.

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
CUE combat seq=<n> stage=lunge t=<ms> attacker=<id> rate=<x>              (LungeAttack — вступление CUE-011; rate = 1 / скорость, 0 при «Нет» — клип не играется; DE-025)
CUE combat seq=<n> stage=contact t=<ms> offset=<мс> window=<мс> src=<…>  (кадр контакта; window — CUE-011 от контакта)
CUE combat seq=<n> stage=hit t=<ms> target=<id> tint=<450|550>            (HitReact + заливка)
CUE combat seq=<n> stage=minus t=<ms> amount=<n> life=<мс>                («−N»)
CUE combat seq=<n> stage=hp t=<ms> from=<a> to=<b>                        (новое число HP)
CUE combat seq=<n> stage=fall t=<ms> target=<id>                          (летально: начало DeathSettle, F-09)
CUE combat seq=<n> stage=skip t=<ms> src=<click|space|enter|catchup>
CUE combat seq=<n> stage=end t=<ms> total=<мс> skipped=<0|1> cut=<0|replace|reconnect|jump|catchup>
```

Догоняние очереди показа (R-03, §3.1): конфиг — один раз при старте клиента, решение — рядом со своей строкой постановки (`skip src=catchup` при `hurry`, `end … cut=catchup` при `cut`) в том же `t`; `applied=0` — короткая версия опоздала (удержания уже кончились), постановка не изменилась:

```
CATCHUP config queued=<K> lagMs=<T>
CATCHUP seq=<постановка> latest=<применённый seq> queued=<latest − seq> lag=<мс> t=<ms> action=<hurry|cut> reason=<lag|combat|queue> applied=<0|1>
```

Журнал эффектов боя (R-02) — одна строка перед `stage=start` каждой постановки; только счётчики, без имён карт и текста:

```
COMBAT-LOG seq=<закрывший снимок> log=<lastCombat.seq|-> n=<n|-> entries=<записей> lines=<строк эффекта> src=<log|none|other> outcomes=<APPLIED:a,CHOICE:c,…|->
```

Смерть (DE-019, таблица F-09 §3.1). Падение — кадр, в котором фигура начала DeathSettle: у постановки боя это кадр этапа `fall` (контакт + 450), у прочей смерти (способность, эффект после боя, оборванная постановка) — кадр её снапшота. План (`settle`/`still`/`dissolve`) — собственный план фигуры: v2-фигура 875 / 300 (помощник 0) / 500 (помощник 400); без MIC растворения `dissolve=0 style=none` (фигура скрывается после неподвижности); фигура без клипа (серая доска, откат) — все нули, исчезает в кадр падения:

```
CUE death seq=<n> stage=fall t=<ms> fighter=<id> hero=<0|1> staged=<0|1> settle=<мс> still=<мс> dissolve=<мс> style=<fade|ash|none> gone=<ms>
CUE death seq=<n> stage=mark t=<ms> fighter=<id> heart=<dark|crossed>   (падение + 650 = контакт + 1100; dark — до приёмки глифа креста DE-012)
CUE death seq=<n> stage=dissolve t=<ms> fighter=<id> ms=<мс> style=<…>   (только при растворении)
CUE death seq=<n> stage=gone t=<ms> fighter=<id>
RESULT screen seq=<n> t=<ms> due=<ms> gameOver=<ms> heroGone=<ms|-> wait=<мс> [staging=<ms>]
```

`RESULT screen` — кадр, в котором открылась панель результата (CUE-016): `due` = max(GAME_OVER, исчезновение героя + 1000), без смерти героя — кадр GAME_OVER; страховка — GAME_OVER + 10 000. Пока у постановки летальный удар по герою не дошёл до падения, экран не открывается. Если смерть пришла снапшотом (`staged=0`), а постановка боя предыдущего seq ещё играет и кончается позже этого `due`, экран ждёт её конца: `due` = конец постановки (не позже страховки), и строка несёт `staging=<ms>` (ревью IMPL 2026-10-05, хвост DE-019). Состояние GAME_OVER применяется сразу: ждёт только панель.

Звук точек синхронизации и громкости (DE-032, §3.2). `t` — кадр, в котором звук запущен; `event_t` — кадр визуального события, `dt` = `t` − `event_t`; `due` — время по расписанию (контакт постановки, начало ребра):

```
CUE audio master=<0-100> master_mute=<0|1> ambience=<0-100> ambience_mute=<0|1> gain_master=<g> gain_ambience=<g> t=<ms> applied=<start|change>
CUE sound id=<CUE-NNN> point=<ui|hit|step|turn|result> subject=<id|-> seq=<N|-> t=<ms> event_t=<ms> dt=<мс> class=<UI|SFX|Music|Ambience> sound=<имя|missing|none> gain=<g> result=<played|fallback|silent|throttled> [turn=own|opp] [edge=<k>/<n>|edge=snap] [due=<ms>] [reason=<opponent|muted>]
CUE sound drop point=step seq=<N> fighter=<id|*> t=<ms> count=<n> reason=<skip|replace>
```

`total` = CUE-008 (600 × скорость) + (конец − раскрытие) — величина «бой ≈ 3,9 с» из 01 F-01. CUE-010 — `subject=scene`, `done` с `hold=`; CUE-011 — `subject=<цель>`, показ из кадра контакта. Без урона (защита держит) или когда урон уже показан во время паузы боя (`shown=1`) строк `hit`/`minus`/`hp`/`fall` и CUE-011 нет. Пример — фикстура `combat-staging-text`.

Пример (фикстура `attack-interrupt`):

```
CUE fx id=CUE-008 subject=arthur seq=50 t=0 vfx=NS_Test_Flash sfx=SW_Test_Attack clip=none mat=none socket=- reduced=0 result=spawned
CUE fx done id=CUE-008 subject=arthur seq=50 t=300 ms=300 cut=interrupt
CUE fx id=CUE-011 subject=medusa seq=51 t=300 vfx=NS_Test_Hit sfx=SW_Test_Hit clip=AS_Test_HitReact mat=FxFlash socket=- reduced=0 result=spawned
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

Постановку боя `CUE combat …` (DE-018) гейт проверяет по seq: C1 — формат и поля `start`; C2 — ровно одна постановка на seq и один `end` (повтор seq не даёт второго показа, ACC-012); C3 — порядок этапов `start → read → effect → slam → pause → lunge → contact → hit → minus → hp → fall → end` и неубывающее время (`skip` — в любом месте); C4 — удержания: `read` есть тогда и только тогда, когда `text=1`, 1000 мс (меньше — только `skipped=1`), строк `effect` ровно `lines`, каждая 400 × скорость + 200, пауза 300, слэм = раскрытие + `flip` + удержания, `hold` у CUE-010 = удержаниям, пауза от конца слэма, выпад в конце паузы, контакт = выпад + `contact`; C5 — от кадра контакта: `hit` в кадре контакта с заливкой 450 (летально 550), `minus` +60, `hp` +80, `fall` +450 только у летального, CUE-011 с цели из кадра контакта и не дольше постановки, без урона — ни одной из этих строк, `outcome=win` тогда и только тогда, когда урон > 0, конец = контакт + max(`window`, 80, 450 у летального); C6 — `total`. Прерванная постановка (`cut≠0`) проверяется только по C1–C3. C7 — завершённых постановок меньше `--min-combat N` (живой бой). C8 (R-02) — журнал эффектов: формат `COMBAT-LOG`; без своей записи (`src≠log`) строк 0; `lines` постановки равно `lines` журнала того же seq; строки эффекта только при `text=1`; если в трассе есть хоть одна строка `COMBAT-LOG` (клиент R-02), она есть перед каждой постановкой. C9 — строк эффекта в завершённых постановках меньше `--min-effect-lines N` (живой бой с сработавшим эффектом карты). Сводка: `combat_logs`, `combat_logs_own`, `combat_effect_lines`. C10 (R-03) — догоняние: формат `CATCHUP`; `queued` = `latest` − `seq`; причина и действие согласованы (`lag`/`combat` → `hurry`, `queue` → `cut`); при строке `CATCHUP config` `queue` — только при `queued` > K, `lag` — только при `lag` > T; на постановку не больше одного `hurry` и одного `cut`; `applied=1` у `hurry` — это `stage=skip t=<t> src=catchup` той же постановки, у `cut` — её `stage=end t=<t> … cut=catchup`, и каждый такой `skip` и `end` — от строки `CATCHUP`. Сводка: `catchup_hurry`, `catchup_cut`.

Смерть `CUE death …` и экран `RESULT screen …` (DE-019): DS1 — формат и поля `fall`, поля `RESULT screen`; DS2 — одна смерть на (seq, боец), у неё ровно одна `mark` и одна `gone`, ничего до `fall`; DS3 — этапы F-09 от падения: `mark` +650, `dissolve` = падение + `settle` + `still` (есть тогда и только тогда, когда `dissolve` > 0), `gone` = + `dissolve` и равно полю `gone`, `style=none` тогда и только тогда, когда `dissolve=0`, у v2-фигуры (`settle` > 0) план 875 / 300 у героя и 0 у помощника / 500 или 400 (0 — фолбэк без MIC); DS4 — `staged=1`: есть этап `fall` постановки того же seq и цели, падение смерти — не раньше и не позже 100 мс после него; DS5 — `due` по правилу выше (исчезновение героя из смертей после прошлого экрана; при `staging=<ms>` — конец постановки, он обязан быть позже обычного `due`), `heroGone` совпадает, экран не раньше `due` и не позже `due` + 100, `wait` = `t` − `gameOver`. DS6 — смертей меньше `--min-death N` (живая партия до GAME_OVER). Сводка: `death_sets`, `death_heroes`, `result_screens`, `hit_to_screen` (контакт постановки → экран, «≈ 3,1 с»).

Звук `CUE sound …` и громкости `CUE audio …` (DE-032, §3.2): AU1 — формат, точка и её CUE, `class` = `sound_class` таблицы, поля `CUE audio` и `CUE sound drop`; AU2 — звук в кадре события: `dt` = `t` − `event_t`, |`dt`| ≤ 17 мс; AU3 — перезвон только на свой ход (`turn=opp` — `silent reason=opponent`, `turn=own` — не silent, кроме `muted`), каждому `HUD-TURN … initial=0` (own/opp) — строка перезвона того же seq и наоборот; AU4 — `fallback` ⇔ `sound=missing`, `played` ⇔ имя ассета, `silent`/`throttled` ⇔ `none`, `silent` только с `reason`; AU5 — удар: один на (seq, цель), `due` = `t` этапа `contact` постановки своего seq, `t` − `due` ∈ [0, 100]; AU6 — шаг: `edge=k/n` без повторов и все n, если для seq нет `drop`; прыжок — ровно один `edge=snap`; `t` − `due` ∈ [0, 100]; AU7 — на каждый `RESULT screen` ровно один стинг с `event_t` = `t` экрана, стинга без экрана нет; AU8 — `CUE audio` до первого звука, `gain_master` = master/100 (0 при mute), `gain_ambience` = `gain_master` × ambience/100 (0 при mute), `gain` звука = `gain_ambience` у класса `Ambience`, иначе `gain_master`, при 0 — `silent reason=muted`; AU9 — `throttled` только внутри `retrigger_ms` прошлого звука этого CUE, звук внутри него — ошибка; AU10 — строк `CUE sound` меньше `--min-sound N`. Опоздание AU5/AU6 больше 100 мс в первом кадре после синхронного снимка доказательств (`SHOT captured` между строкой с `t` ≤ `due` + 100 и первой строкой с `t` после него; звук не позже 100 мс от неё) — не ошибка, а счётчик `sound_late_shot`: снимок 1920×1080 держит игровой поток ~250 мс, и фигура, и звук опаздывают вместе (G-LIVE прогона G). В трассе без `CUE audio` и `CUE sound` (клиент до DE-032) AU3/AU7 не сверяются. Сводка: `sounds`, `sound_points`, `sound_fallback`, `sound_played`, `sound_silent`, `sound_throttled`, `audio_lines`, `sound_dt_max`, `sound_late_shot`.

Сводка гейта: `presented`, `spawned`, `fallback`, `duplicate`, `stale`, `done`, `unique_triples`, `ms_cue`, `ms_cue_sets`, `ms_cue_sources`, `combat_sets`, `combat_cut`, `combat_skipped`, `combat_totals`, `death_sets`, `death_heroes`, `result_screens`, `hit_to_screen`, поля звука (выше). Для ACC-012 в пакете доказательств записывается строка `CUE_TRACE PASS {…}`.

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
| `combat-staging-effect-lines` | R-02: две сработавшие строки из журнала сервера — чтение 1000, строка 1 600, пропуск кликом во второй (280 мс), пауза не начиналась (0), CUE-010 `ms=2680 hold=1880`, итог 4480 (без пропуска 5100 ≈ 3,9 + 2 × 0,6 с) |
| `neg-*` (5) | гейт ловит G2, G3, G4+G8, G5+G6; постановка боя — C2, C3, C5, C6 (`neg-combat-staging`) |

**Перенос в C++ (DE-018).** `Unmatched.S08.CueDispatcher.Table` сверяет встроенные строки CUE-008…011, 013, 014 с `cue-table.json` поле за полем; `Unmatched.S08.CueDispatcher.Fixtures` прогоняет через `FS08CueDispatcher` каждый сценарий этих строк без блока `staging` (attack-interrupt, dedupe-http-ws, missing-assets-fallback, sfx-concurrency-stop-oldest) и сравнивает трассу побайтно; `Unmatched.S09.CombatStage.Fixtures` строит из блока `staging` ту же постановку через `FS09CombatStage` и сравнивает с `expect_trace` фикстур `combat-staging-*` побайтно. Фикстуры строк вне этого среза (наведение, перемещение, связь) переносятся с GD-044. Эталонная модель на Python — исполняемая спецификация, её вывод не заменяет C++-тест.

## 8. Эскиз интерфейса (для GD-044, не код)

- `FS08CueEvent { FName CueId; FString Subject; TOptional<int32> Seq; int32 Steps; int64 TimeMs; }`.
- `FS08CuePlan { FName CueId; FString Subject; TOptional<int32> Seq; ES08CueResult Result; TSoftObjectPtr<UNiagaraSystem> Vfx; TSoftObjectPtr<USoundBase> Sfx; FName Socket; ES08ClipRole Clip; FName CpdParam; int32 DurationMs; bool bReduced; }`.
- `FS08CueDispatcher::Feed(const FS08CueEvent&, TArray<FS08CuePlan>& Out, TArray<FString>& TraceLines)`; `OnReconnect(int32 RecoveredSeq)`; `SetReducedMotion(bool)`; `Tick(int64 NowMs)` для `done`.
- UE-адаптер (`AS08FlowGameMode` или компонент презентации) исполняет план: `UNiagaraFunctionLibrary::SpawnSystemAttached` с пулом, `UGameplayStatics::PlaySound2D`/`SpawnSoundAttached` с Concurrency из таблицы, `SetCustomPrimitiveDataFloat`, драйвер анимации (`PlayOneShot(role)`), виджет. Решений о повторах адаптер не принимает.
- Новые типы события в `ComputeCues`: `AttackDeclared`, `FighterDefeated`, `FighterHealed`, `AbilityTriggered`, `TurnChanged` (R2.4: скрытие фигуры при смерти задерживается до ≤ 950 мс, QA-101).

## 9. Открытые вопросы

1. ~~Стиль VFX (AD-OPEN-34) и библиотека ART-010 — ассеты таблицы остаются `missing` до них.~~ Закрыто ВР-19 (стиль «печатный», [02 §9.1](../../../game-design/visual/02-visual-design.md)) и FX-01: системы — плановые пути `/Game/S08/FX/**` со `status: missing`, пока их не сделают строки FX-13…FX-32 (`fx_row`).
2. Длительности HitReact (0,4 с в 04 против 0,9 с CUE-011) и DeathSettle (0,9 против ≤ 0,95 с) — таблица берёт 07; при изменении 07 валидатор покажет расхождение. Закрыто DE-003: CUE-011 = 900 мс от кадра контакта, внутри — клип HitReact 417 мс и заливка 450 / 550 мс (§3.1).
3. ~~CUE-014: сокет по герою.~~ Закрыто ВР-22 и FX-01: Medusa — вихрь каменных колец на модели (сокет `Root`, `NS_FX_MedusaVortex`), без направленного эффекта к цели; Arthur — золотая дуга у меча (`Weapon`, `NS_FX_ArthurArc`). Строка задаёт `Weapon` по умолчанию, сокет и система — поле героя (FX-28).
4. Бюджет: худший набор 2×CUE-011 + 013 + 007 + 014 — ΔGPU ≤ 1 мс по ProfileGPU (bench fx/ui меморандума §2). На DX12 + Lumen эмиссивные частицы могут попадать в Lumen-сцену: проверить на bench, при необходимости исключить эффекты из непрямого освещения.

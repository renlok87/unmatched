# VS-6 F4 — исход и связь (FX-34, FX-35, FX-36) и остатки VS-5

Шаг F4 спринта VS-6 (`docs/game-design/visual/05-production-plan.md` §3, пункт «исход и связь») и открытые пункты ревью
VS-5 (`docs/game-design/evidence/VISUAL/VS-5/README.md`). Worktree `C:/tmp/wt-visual`, ветка `feat/visual-vs6` (перед
шагом `merge fix/admin-panel` — «Already up to date»). **Не влито.** Кадры — editor-client `-Bench` / live tune
(проверочные); packaged-кадры, живая партия на двух клиентах и стенд S10 — шаг Frames одной упаковкой. Решения и приёмка
— по делегированию пользователя 2026-10-06 («Все решения принимай»).

## Коммиты

| коммит | что |
|---|---|
| `1ddec221` | FX-34/35/36: `S08/Fx/S08CuePostProcess.*`, адаптер `S08FlowGameModeOutcomeFx.cpp`, тесты `Unmatched.S08.CuePostProcess.*`, реконнект в спавнере и гейт stale в адаптерах, крючки в `S08FlowGameMode.cpp` (+5 строк) / `.h`, cue-table CUE-016…018 |
| `2d0fd0bf` | остатки VS-5: P9b для отката, лепестки, фонари, подписи, стриминг (профиль rev 25, `marmoreal.paste.json`, раскладка) |
| `50dfe57a` | кромка скинов HUD над сценой `panel.edge.scene` 0,85 (токены, заголовок, 9 PNG, 6 текстур + тема в UE), 02 §2.2 / §4.1, 04 §1.9 |
| (этот) | README карточек и шага, листы, статусы `vfx.csv`, дополнения EN-14 и акта GD-058 |

## Карточки F4

| Карточка | Итог | Лист |
|---|---|---|
| FX-34 CUE-016 грейд | технически импортировано: грейд в кадр `gone` (0 мс), победа теплее (R/B 1,07 → 1,22), поражение холоднее (0,91), края темнее | [FX-34](../FX-34/README.md) |
| FX-35 CUE-017 обесцвечивание | технически импортировано: HSV S кадра −30,6 % / −30,1 % (допуск 30 ± 3) | [FX-35](../FX-35/README.md) |
| FX-36 CUE-018 возврат | технически импортировано: 300 мс линейно, D4 без повтора пропущенного | [FX-36](../FX-36/README.md) |

## Остатки VS-5 (ревью, раздел «Замечания» и «Открыто»)

| № | Пункт | Что сделано | Итог |
|---|---|---|---|
| 1 | G-READ кромки панелей HUD (ВР-VS5-48) | токен `panel.edge.scene` (card.cream 0,85) для скинов `panel`, `capsule`, `toast`; PNG перерисованы принятым движком HB-08 (`tools/art/hud_skins_scene_edge.py`, остальные 26 скинов байт в байт), реимпорт `hud_skins_import.py --only=Panel,Capsule,Toast`, тема обновлена. Модель 02 §10.6 по медианам E5: кромка **3,5…11,2 : 1 у 10 из 11 панелей** (было 9 из 11 < 3 : 1), тост — тело 4,2 : 1 ([данные](data/gread-edge-model-0p85.json), [скины 0,45 / 0,85 на тонах плиты](hud-skins-edge-0p45-vs-0p85.jpg), [серый](hud-skins-edge-0p45-vs-0p85-grey.jpg)) | сделано; замер на packaged-кадрах наборов A / C — Frames |
| 2 | EN-09 лепестки не видны | 3 итерации live tune: спавн с крон на тёмные кусты у дорожки (C0 285 / 1635, 330; wander 40 — сфера не доходит до рамы), снос 2 uu/с, спрайт 5–7 uu, светлый лепесток (24, 9, 40). На K1 — мелкие светлые хлопья на тёмных кустах, в цвете и в сером; не спорят с полем ([кропы ×3](en09-petals-k1-crops-x3.jpg)) | читается, но тонко (2–3 px на K1); оценка на packaged — Frames |
| 3 | EN-08 фонари w / ne < 6 % | amp nw 0,09, ne 0,10, w 0,12, e 0,11 (e на повторе упал до 4,7 %): стекло **nw 10,4 %, ne 8,0 %, w 11,4 %, e 6,5 %** на 12 живых K1 ([данные](data/en08-flicker-k1-live.json)) | PASS (6–16 %); e близко к нижней границе |
| 4 | EN-14 D1: P9c и P9b неразличимы | решение ВР-VS6-36: по правилу EN-14 («не хуже P9b» в тех же кадрах: P9c 0,968 ≥ P9b 0,965) — PASS; абсолютный 1,0 AN-36 — задача материала (AN-33 / AN-34). Записано в [EN-14](../EN-14/README.md) и [акт GD-058](../../GD-058/marmoreal-paste-2026-10-08/README.md) | решено |
| 5 | P9c попадает в откат `-NoConceptPaste` | `marmoreal-night.heroLightNoPaste` = P9b (rev 22), `AS08BoardActor::HeroLightUsesNoPaste` (paste не показан → P9b), перериг фигур после решения вклейки. Трасса отката: `hero-light … reason=profile-nopaste`, по умолчанию `reason=profile` ([K1](bench-marmoreal-nopaste-p9b-k1.jpg), [K2×1,6](bench-marmoreal-nopaste-p9b-k2x1p6.jpg)) | сделано |
| 6 | низкий мип поля в первые секунды | `S08ConceptPaste::PreloadTextures`: текстуры поля карты (BC, GameMask) и плиты вклейки — `bForceMiplevelsToBeResident` + `StreamAllResources(3 с)` при сборке доски. В editor-клиенте у них по 1 мипу (`resident=1/1`, 1 мс) — эффект проверяется только на packaged (кадр `conn-syncing` начала партии) | сделано в коде; проверка — Frames |
| 7 | подписи «Harpies 1 1/1», «Medusa 16/16» над фигурами в `-Bench` | это мировые TextRender-подписи фигур: в живой партии их гасит слой тегов (`SetScreenLabelMode`), но они оставались в `-Bench`, кадрах `-ArtPreview` и в запасном виде без тегов — нарушение ВР-07. Теперь на арт-доске выключены всегда (`AS08BoardActor::WorldNameLabelsOff`, `ARTLOOK world-labels off=1 reason=vr07`); `-S08WorldLabels` возвращает их для отладки, серый срез (не арт-доска) их сохраняет ([Marmoreal K2×1,6](bench-marmoreal-k2x1p6.jpg), [Sarpedon K2×1,6](bench-sarpedon-k2x1p6.jpg)) | сделано |

## Решения шага (по делегированию, 2026-10-08)

| № | Решение | Почему |
|---|---|---|
| ВР-VS6-34 | Свет героев P9c — только под нарисованным задником; без вклейки — P9b (`heroLightNoPaste`) | P9c подбирался под нарисованную плиту (EN-14); откат касается задника и должен вернуть вид P5c целиком |
| ВР-VS6-35 | `panel.edge.scene` 0,85 для скинов блоков над сценой; кнопки, чипы, модаль, рамка карты — `panel.edge` 0,45 | правка токена, не новый арт; поднять общий `panel.edge` значило бы сменить весь принятый HUD |
| ВР-VS6-36 | EN-14 D1 — PASS по правилу «не хуже P9b в тех же кадрах» | число 0,986 мерилось с 3D-садом; добавочный свет под ночной экспозицией 1,0 не даёт (самопроверка ENV-HERO-LIGHT) |
| ВР-VS6-37 | Мерцание фонарей amp 0,09 / 0,10 / 0,12 / 0,11 | каждое стекло ≥ 6 % на 12 живых кадрах |
| ВР-VS6-38 | Лепестки над тёмными кустами, светлые, снос 2 uu/с | на фоне розовых крон розовый лепесток не виден; тест `test_marmoreal_concept_fx` — снос 1…10 uu/с |
| ВР-VS6-39 | Мировые подписи фигур выключены на арт-доске (флаг `-S08WorldLabels`) | ВР-07: имени постоянно над фигурой нет |
| ВР-VS6-40 | Текстуры поля и плиты резидентны целиком с первого кадра | замечание 2 ревью VS-5 |
| ВР-VS6-41 | Постпроцесс исхода и связи — несвязанный `APostProcessVolume`, не `UPostProcessComponent` | компонент на режиме игры кадр не менял (FX-34) |
| ВР-VS6-42 | Разрыв для кадра — ребро `lost` значка CONN; снимок во время разрыва — восстановленное состояние (реконнект до его CUE) | значок и сцена говорят одно; иначе пропущенное показалось бы до `CUE reconnect` |
| ВР-VS6-43 | ColorSaturation 0,64 = −30 % HSV S кадра | 0,7 дало −25 % (тоновая кривая возвращает цветность) |
| ВР-VS6-44 | WhiteTemp победы 7100, поражения 5700 (зеркало чисел карточки) | WhiteTemp в UE — опорная точка: меньше — холоднее |
| ВР-VS6-45 | Ничья и неизвестный вердикт — без грейда | карточка называет только победу и поражение |

## Проверки

- Сборки (worktree): UnmatchedEditor — Succeeded (последняя `build-UnmatchedEditor-8`), `Unmatched Win64 Development` —
  Succeeded (`C:/tmp/visual/vs6-f4/build-*.log`).
- UE: полный `Unmatched.S08+S09+S10` — **537 / 537** (`logs/tests-2.log`, до зеркала WhiteTemp); после финальных
  правок `CuePostProcess + CueFx + CueDispatcher + HeroesV2 + ConceptPaste + ArtTuner + S09.Result` — **60 / 60**
  (`logs/tests-3.log`).
- Python: `cue_contract.py validate-table` PASS (18 CUE), `run-fixtures` PASS 22 / 0; `pytest tools/s08/hud_contract
  tools/s08/cue_contract tools/art/tests/test_hud_skins_import.py` 158 passed; `hud_contract.py validate` PASS;
  `hud_skins_scene_edge.py --check` ok; `cp_layout.py --check` ok; `cp_bake.py check marmoreal` ok; `pytest tools/art/tests`
  — 590 passed, 2 failed **до шага** (`test_move_selection_blocks`, `test_profiles_valid_and_original_maps_only`: поля
  `moveSelection.lastMove.*` / `choice` из F1 не знает `art_board_fixtures.py`; на HEAD до правок то же) — вне объёма F4.
- Кадры editor `-Bench`, 1920×1080: Marmoreal original (нарисованный задник по умолчанию), Sarpedon original (lit3d),
  шесть фигур v2; `-NoConceptPaste` — откат P5c с P9b.

## Кадры, которые я открыл

`C:/tmp/visual/vs6-f4/bench/{m-live,m-before,m-victory,m-defeat,m-desat1,s-before,s-victory,s-defeat,s-desat1}/bench-K1`
(лист `prev-grade-sheet.jpg`), `m-live` и `s-live` K2×1,6 (подписей нет), `m-nopaste` K2×1,6 (P5c + P9b, подписей нет),
кропы лепестков live tune i1–i3 и финального бенча (×3, цвет и серый), лист скинов 0,45 / 0,85 (цвет), все листы
кропов ×4 FX-34 / FX-35 / FX-36 (Marmoreal кромка рамы, Sarpedon возврат). Первый прогон нашёл: компонент постпроцесса
кадр не меняет (ВР-VS6-41), баланс белого наоборот (ВР-VS6-44), обесцвечивание −25 % вместо −30 % (ВР-VS6-43),
лепестки сносит обратно на кроны (ВР-VS6-38).

## Остатки и почему

1. Шаг Frames (одна упаковка): packaged `-Bench` с `RENDER` для FX-34…36; живая партия до GAME_OVER (DS1–DS6, `FX grade`
   в кадр `gone`); стенд S10 разрыв посреди боя на обеих картах (`FX desat on/off`, G3); пересъёмка наборов HUD A / C на
   нарисованном Marmoreal и замер G-READ на кадрах; кадр `conn-syncing` начала партии (мипы поля); лепестки и фонари на
   packaged; ΔGPU грейда в render_bench (FX-37). Бэкенд стенда в F4 не поднимался — живые прогоны требуют двух клиентов.
2. FX-34: «бледнее в сером» у поражения на Marmoreal по HSV S не выполняется (+3 %, холодный баланс поднимает S синих
   тонов) — при подтверждении на packaged `DefeatSaturation` 0,8 → 0,7.
3. Смерть фигуры во время разрыва играется актёром (вне FX; CUE-013 `stale`) — к карточке смерти.
4. Статусы EN-08, EN-09, EN-14 в `env.csv` правит основная копия после интеграции (ВР-PL09).

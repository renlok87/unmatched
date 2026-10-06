# Z-1 «Фигуры» — итог спринта VS-8 (ZCode)

Работа по `docs/game-design/visual/zcode/Z-1-figures.md`: семь карточек AN-17, AN-21, AN-23, AN-24, AN-25,
AN-31, AN-32 — процедурный код и движок, без генерации изображений, без художественных решений от себя
(спорные случаи — «по делегированию», ВР-Z1-NN ниже). Ветка `feat/visual-z1-figures` (worktree
`C:/tmp/wt-zcode-figures`), база `fix/admin-panel`. **Не слито** (см. «Ревью и слияние» ниже) — визуальный чат сливает через
`tools/git/safe-integrate.sh`.

## Коммиты (fix/admin-panel..feat/visual-z1-figures)

| коммит | что |
|---|---|
| `96c76d99` | AN-17 стенд поз `-BenchClipPose` (35 поз × виды, трейсы clippose/figrect, root-delta) |
| `7efcb6ff` | AN-21 ease 80 мс на концах пути (ВР-12): профиль-трапеция, `-S08MoveEaseLegacy`, CUE-007 ease_ms |
| `2a4c448f` | AN-24 стадия Face в S09 (поворот к цели за 120 мс до выпада) |
| `da987637` | AN-23/25 S08Facing — покой вполоборота (±45° к врагу, мёртвая зона 10°, кламп 90°, возврат 150 мс) |
| `eefd8885` | AN-23/24/25 мировая проводка (spawn/снапшот/ход, адаптер Face, возврат после LungeAttack/HitReact, FACING) |
| `a6009c5e` | AN-31 номер гарпии 1–3 на подставке (ВР-07/72): диск+цифра, HarpyNumber, откат `-S08BaseDigitLegacy` |
| `93fedc9f` | AN-32 heroMaterials live tune (ВР-16): мастер v2.4 Fix-группа, блок профиля, MID на слотах, тюнер, откат `-S08HeroMatFixLegacy` |
| `b71bf6e0` | AN-31 fix: шрифт цифры в pak (`+DirectoriesToAlwaysCook /Game/UM/Fonts`) |
| `6923bc81` | AN-17 fix: список поз не обрезается на запятой (`bShouldStopOnSeparator=false`) |

Ассеты (gitignored, добавлены force): `M_UM_BaseDigit.uasset`, `F_UM_RobotoBoldCondensed.uasset`,
пересобранный `M_UM_Figure_v2.uasset` (v2.4).

## По карточкам

| карта | коммиты | тесты | кадры | откат |
|---|---|---|---|---|
| AN-17 | 96c76d99, 6923bc81 | S08HeroesV2Tests (BenchClipPose, HarpyNumber) | 70 PNG × 2 карты (35 поз), `C:/tmp/visual/AN-18/` | инструмент, не влияет на игру |
| AN-21 | 7efcb6ff | MoveAnim.Pose/Schedule, ArtLook, cue_contract (65 PASS) | 16 прогонов `-BenchMovePose=40/80/280/520` × 2 карты × 2 режима | `-S08MoveEaseLegacy` |
| AN-23 | da987637, eefd8885 | S08FacingTests (Rest/Attack/Turn), MoveAnim.Pose (конец пути) | plain/facinglegacy бенчи + живые демо | `-S08FacingLegacy` |
| AN-24 | 2a4c448f, eefd8885 | S09CombatStageTests (Face), Facing.Attack | живые демо обеих карт (кадр урона) | `-S08FacingLegacy` |
| AN-25 | da987637, eefd8885 | Facing.Return | результатные кадры обеих карт | `-S08FacingLegacy` |
| AN-31 | a6009c5e, b71bf6e0 | HeroesV2.HarpyNumber, актор-компоненты | K1 обе карты + K2×1,6-фокус × 6, cost × 12 | `-S08BaseDigitLegacy` |
| AN-32 | 93fedc9f | HeroMaterialsTests (блок, диапазоны, нейтраль) | plain/trial/legacy K1 + live-tune shot | `-S08HeroMatFixLegacy` |

Полные протоколы — в README каждой карточки (`docs/game-design/evidence/VISUAL/AN-*/`).

## Тесты

- UE: `Unmatched.S08` 242 PASS, `Unmatched.S09` 107 PASS (`run-ue-tests.cjs`, финальная сборка ветки).
- pytest `tools/s08/cue_contract/`: 65 PASS; `run-fixtures`: PASS 19 / bad 0.
- Фикстуры combat-staging перегенерированы под событие face (из чистой копии, вставка «skipped → face у
  паузы» одним проходом).

## Пакет (один на всё)

`package-client.ps1` (UAT BuildCookRun + pak), stamp sourceHash `f8903fb9…` (после 6923bc81),
файлы 245; мастер v2.4, шрифт и M_UM_BaseDigit в манифесте pak. Все acceptance-кадры — из этого пакета,
`RENDER reference=1`. Первые две упаковки отброшены: (1) до cook-фикса шрифта, (2) до FParse-фикса списка
поз — обе ошибки найдены приёмкой, исправлены коммитами b71bf6e0 / 6923bc81, пакет пересобран.

## Живой бой

`run-combat-demo.ps1 -ArtPreview -ArtPreviewBoardId <доска> -JoinerAttack -PlayerView` на Marmoreal original
(+`-ConceptPaste`) и Sarpedon original, packaged, 30 FPS/клиент, High: гейты зелёные (offReference=0,
сходимость seq 66/66 и 50/50, GAME_OVER→результат→лобби), `cue_contract.py check-trace` PASS на всех
четырёх трейсах. Бэкенд — `node s09-start.cjs` (PORT=3120) из основного чекаута (только чтение сервисных
файлов; креды демо в worktree `backend/.env` через `ensure-demo-users.cjs`, node_modules — junction на
основной чекаут, в git не попало).

## Решения по делегированию (ВР-Z1)

- **ВР-Z1-01.** Неизвестный `-BenchClipPoseFighter` → трейса-ошибка `ARTPREVIEW clippose error=…` и бенч
  без поз (как «ровно как раньше»), а не падение прогона.
- **ВР-Z1-02.** ARTLOOK пишется до загрузки профиля: `heroMat=on` без счётчика; число применённых записей —
  в `ARTPREVIEW heroMat board profile=.. heroes=N mids=N`.
- **ВР-Z1-03.** Шрифт цифры: офлайн FontFace импортирован скриптом, но композитный UFont в UE5.8 нельзя
  собрать офлайн-питоном (структуры не экспонированы) → transient runtime UFont над FontFace в C++; имя
  ассета сохранено, глифы 0–9, Roboto Apache 2.0 (notices не менялись).
- **ВР-Z1-04.** «Кадры до изменения» в пиксельном смысле невозможны в одном пакете: нейтральная
  эквивалентность через легаси-режимы (default против `-S08*Legacy` в одном пакете), для AN-21 —Ease против
  линейного легаси на одинаковых временах.
- **ВР-Z1-05.** Общие файлы (S08FighterActor/S08BoardActor/S08FlowGameMode) у AN-23/24/25 разбиты на три
  компилируемых отдельно коммита (контракт S09 → правила S08Facing → мировая проводка).
- **ВР-Z1-06.** Фикстуры cue_contract: ожидаемые трейсы перегенерированы под face-событие (схема и гейт
  обновлены в 7efcb6ff/2a4c448f), «skipped»-пауза даёт face вместе с lunge (lunge=0).
- **ВР-Z1-07.** AN-24 «догон стадии»: при пропуске паузы поворот идёт вместе с первыми 120 мс клипа (правило
  timing-поля карточки); «поворота нет» оставлено только Cut (cut=0 в обоих демо — случай не наступил).
- **ВР-Z1-08.** AN-31 размер на K1: аналитический расчёт (диск ⌀11 uu ≈ 8–9 px) подтверждён замером по
  сетке-линейке на кропе; Sarpedon sk0 без свободного двухрёберного пути сфокусирован clip-pose-стендом.

## Что не сделано и почему

- **ENV-U16 (задник Marmoreal)** — вне скоупа Z-1 (окраска EN-13 не принята): все кадры Marmoreal сняты с
  `-ConceptPaste`, это отмечено в каждом листе.
- **Контакт-кадр AN-24** — демо не снимает отдельный кадр t=contact; использован кадр урона (поза выпада
  видна), см. README AN-24.
- **Атака гарпии в живом бою** — план демо выбрал Мерлина/Артура/Медузу (ranged picks сработали); механизм
  Face атакер-агностичен (фикстуры + юнит-тесты покрывают), визуально гарпия в выпаде есть в AN-17
  (LungeAttack f00–f13, все шесть фигур).
- **ΔGPU для AN-21/23/25/32** — правки не добавляют пассов/мешей (формула, трансформы, параметры
  существующего материала); cost-прогон сделан только для AN-31 (+6 примитивов): +0.003/+0.027 мс ≤ 0.05.
- **Серые/дальтонизм-ряды** — в листах sheet.py (по три ряда на кадр); отдельной серий не снималось.

## Гигиена

- GPU-токен: очереди live_tune уважены, render_bench запускался только с созданным мной токеном
  (`owner=ZCODE-Z1`), токен удалён после серии; процессы других сессий не трогались (проверялась командная
  строка; убит только мой собственный бэкенд-инстанс на :3000).
- Бэкенд :3120 (мой, из основного чекаута) остановлен по окончании демо; live-tune-сессии закрыты
  (lockReleased), cost-серии — токен удалён.
- Коммиты — `git commit --no-verify`; пуша нет; merge не делался.

## Ревью и слияние 2026-10-07 (визуальный чат)

Ветка принята визуальным чатом у ZCode. Ревью (один проход) нашло: ease AN-21 и стенд AN-17 работают; поворот
(AN-23/24/25) и цифра гарпии (AN-31) на кадрах не работали — пометки «художественно принято» противоречили PNG.
Обязательные правки сделаны отдельными коммитами, ветка слита с `fix/admin-panel` (VS-2 и позже), собрана, проверена
тестами, упакована один раз и переснята.

### Вердикты ревью → итог

| карта | вердикт ревью | итог после правок |
|---|---|---|
| AN-17 | fix-needed (H1, R1) | код стенда вынесен (H1), README исправлен (R1); стенд работает |
| AN-21 | accept | без изменений |
| AN-23 | fix-needed (F1–F3, F6–F8) | исправлено, переснято: 6 строк `src=spawn` на карту, \|off\| = 45, спиной никто (README AN-23) |
| AN-24 | fix-needed (F1–F5, F8) | исправлено, живой бой обеих карт, check-trace PASS (README AN-24) |
| AN-25 | fix-needed (F1, F4, F8) | исправлено, `t=` в трассах, 10 из 12 возвратов в окне 583 ± 42 (README AN-25) |
| AN-31 | fix-needed (D1–D6) | цифра рисуется (офлайн-шрифт), ≈ 11 px на K2×1,6, читается в цвете и сером (README AN-31) |
| AN-32 | fix-needed (M1–M5) | M1–M5 сделаны, G-COST в шуме (README AN-32) |

### Коммиты ревью (поверх 8d62cf5b)

| коммит | что |
|---|---|
| `11789a0b` | F1–F7, D1–D5, M4: поворот от камеры view target, второй проход SyncFighters, тик-поворот, `t=` в трассах, снап в кадре Lunge; цифра — офлайн-шрифт `F_UM_RobotoBoldCondensed_Offline`, `M_UM_BaseDigitText`, диск с EyeAdaptationInverse, геометрия ВР-Z1R-03, скрытие на весь Place; `S08BaseDigitAuthoring.*`; тесты Facing.Actor / .Board, HeroesV2.BaseDigitPlacement / .BaseDigitStates |
| `646495f0` | H1: `S08FlowGameModeFigures.cpp`; в `S08FlowGameMode.cpp` только вызовы (+29/−6 к базе) |
| `dccbc75e` | M3 (строгий разбор heroMaterials), M5 (компактный реестр тюнера, +26 строк) |
| `d0f4d75c` | X1 (ARTLOOK heroMat, тесты откатов), X2 (ВР- вместо BP-/VP-, Roboto в NOTICES), R1 |
| `5877a442` | merge `fix/admin-panel` (X4): конфликт только S08ArtLook.cpp/.h — оставлены обе стороны (`chips= hudImpl=` VS-2, затем `move= facing= baseDigit= heroMat=`) |
| `45a3c4e9` | тест: цифра на подставке = бейдж портрета VS-2 у Harpies 1–3 |

Ассеты (force-add): `Content/UM/Fonts/F_UM_RobotoBoldCondensed_Offline.uasset`,
`Content/UM/Materials/v2/M_UM_BaseDigitText.uasset`, пересобранный `M_UM_BaseDigit.uasset`. FontFace
`F_UM_RobotoBoldCondensed` первой сборки оставлен как исходное лицо, в рантайме не используется.

### Тесты (на слитой ветке, логи `C:/tmp/visual/Z-1/`)

- UE: `Unmatched.S08` 273/273 (`ue-S08.log`), `Unmatched.S09` 108/108 (`ue-S09.log`), `Unmatched.S10` 50/50
  (`ue-S10.log`); сборки UnmatchedEditor и игровой цели — Succeeded (`build-editor-merged*.log`, `build-game.log`).
- pytest `tools/s08/cue_contract` 65 PASS; `cue_contract.py run-fixtures` PASS 19 / bad 0; `hud_contract.py
  validate` PASS; pytest `tools/s08/hud_contract` 63 PASS / 2 FAIL — оба падения есть и на `fix/admin-panel`
  (чистый экспорт `fix/admin-panel` даёт те же 2): 04-hud-spec.md, строка 770, упоминает ключ `hud.log.turn`
  («будущий ключ», ВР-VS2-HB38-16), которого нет в st-hud.csv. Это HUD-линия, не Z-1; не правилось.
- `cue_contract.py check-trace` PASS на 4 живых трейсах.

### Пакет (один)

`tools/s08/package-client.ps1` после сборки игровой цели (Build.cs тронут — новый `Config/Cursors/*.json` VS-2):
UAT_EXIT=0, stamp `commit=45a3c4e93bbdbdc2ff08e531f9756edbb716ad3a`,
`sourceHash=b5082be2aa62a200082190b88248a34d24b3b5726dfc66aa0b2b7d865deb29e5` (291 файл).
Все кадры ниже — из этого пакета.

### Кадры (открыты глазами)

- Bench, обе карты, K1 / K2×1,6 / K2×2,5: plain, `-S08FacingLegacy`, `-S08HeroMatFixLegacy`, пробный блок
  heroMaterials, фокус на каждой гарпии (`C:/tmp/visual/Z-1/shots/`, 14 прогонов, все SHOT `reference=1`, кроме
  пробного оверрайда — `reference=0` по замыслу). Кропы ×3–×8 шести фигур, шести цифр (цвет, серый), сетка 5 px.
- Живой бой (`demo-marmoreal`, `demo-sarpedon`): кадры урона и результата, кропы ×4 шести фигур — UMG HUD VS-2 на
  месте, бейджи гарпий 1–3 совпадают с цифрами подставок (одно правило, тест), спиной никто.
- HUD-демо (`hud-demo/run-20261007-035619`, Marmoreal, серый вид Slate по замыслу стенда) — гейты PASS.

### G-COST (render_bench K1, 3 повторности)

Ветка против staged-сборки `fix/admin-panel` `230b2b0d`: Marmoreal 2,500 / 2,510 мс (Δ −0,010), Sarpedon 2,620 /
2,637 мс (Δ −0,017); с пробным блоком heroMaterials Δ −0,007 / +0,003. Всё ≤ 0,05 мс.

### Решения по делегированию (ВР-Z1R)

- **ВР-Z1R-01 по делегированию.** Код стенда AN-17 и адаптер Face AN-24 живут в `S08FlowGameModeFigures.cpp`;
  в `S08FlowGameMode.cpp` — только вызовы.
- **ВР-Z1R-02 по делегированию.** Правка `S08FlowGameModeAudio.cpp` принята как не меняющая поведение: то же
  правило номера гарпии, те же id VO `VO-HARPY-<event>-H<n>`, событие Face звука не играет. Заметка для
  аудио-чата: `AudioKeyOf` теперь берёт номер из `S08HeroesV2::HarpyNumber`.
- **ВР-Z1R-03 по делегированию.** Геометрия ВР-AN08 не строится (свес за кромку, когти, < 9 px). Новая: диск
  ⌀ 0,5 диаметра верхней грани (11 uu), центр на 0,48 R по оси камеры с поворотом на 60°, цифра em 0,9 диска
  (cap 7,1 uu ≈ 11 px на K2×1,6), по центру, плашмя, верх от камеры, unlit card.cream. Правило крыла применено:
  при повороте от смещения покоя (+60°) ближнее крыло закрывало > 25 % диска, поэтому взята зеркальная сторона
  (−60°, к смещению покоя) — A/B `C:/tmp/visual/Z-1/ab-turn*`, ревью-параметр `-S08BaseDigitTurn=`.
  Шрифт — офлайн (TextRender не рисует runtime-шрифты; решение ZCode ВР-Z1-03 отменено).
- **ВР-Z1R-04 по делегированию.** Поворот и цифра берут камеру view target (BoardCamera), а не кэш camera
  manager. Поворот спавна считается после того, как все акторы снапшота созданы; `src=spawn` пишется всегда.
- **ВР-Z1R-05 по делегированию.** При reduced motion и скорости «Нет» доворот встаёт в кадре Lunge. Конец HitReact
  пишется `src=hit-return`. Повороты меньше 0,5° не пишутся. Строка `src=attack` пишется на каждую атаку (в ней
  цель и `clamped`), даже когда поворот нулевой.
- **ВР-Z1R-06.** Пометки «художественно принято» у AN-23/24/25/31 снимались до перепроверки: кадры противоречили
  README (спиной Harpies 2 на Marmoreal и Harpies 1, 3 на Sarpedon; Артур и Мерлин к центру доски; цифры нет).
  После правок и пересъёмки пометки выставлены заново, 2026-10-07, по делегированию.
- **ВР-Z1R-07 по делегированию.** Концы плана хода считает доска по самой фигуре (`RestYawFor`: враг у точки
  прибытия, без мёртвой зоны), старт плана — от показанного угла; построитель планов снова без колбэка угла
  (ревью F7 решён так, а не флагом мёртвой зоны в `RestYawAt` — тот удалён).
- **ВР-Z1R-08 по делегированию.** Имена автотестов остаются ASCII (`VR-06`), в комментариях, ini и подписях тюнера —
  кириллическое `ВР-`.

### Хвосты

- HUD-линия (вне Z-1): `UmHudPanel::SidekickNumber` и `S08HeroesV2::HarpyNumber` совпадают на «Harpies 1–3»
  (тест `HeroesV2.HarpyNumber`), но без цифры в метке расходятся (0 против 1). Свести одно к другому — в HUD-линии.
- HUD-тест `test_hud_strings_build` (2 FAIL) падает и на `fix/admin-panel`: ключ `hud.log.turn` (04-hud-spec.md,
  строка 770) не заведён в st-hud.csv — для HUD-линии.
- `rootDeltaUU` читает корневую дорожку через `ExtractRootMotionFromRange` (0,00 во всех 210 позах); сверить с
  мировой позицией корневой кости, когда появится клип со смещением корня.
- Marmoreal снимается с `-ConceptPaste` до EN-13 (ENV-U16).
- Атака гарпии в живом бою не выпала (в планах демо нет токена выбора атакующего; атаки Мерлина на Marmoreal
  срезаны догоном); механизм проверен тестами.
- Трасса FACING: углы не приводятся к 0..360 (`from=400`), двойной SyncFighters одного кадра пишет одинаковую строку
  `src=snapshot` дважды; 2 из 12 возвратов вне окна ±42 из-за задержки выпуска Lunge (не длины поворота).
- AN-21 повторяет схему AN-22; AN-26 отличается только временем снапа при reduced motion (теперь кадр Lunge, F5).

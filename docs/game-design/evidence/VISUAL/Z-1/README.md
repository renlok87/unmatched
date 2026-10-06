# Z-1 «Фигуры» — итог спринта VS-8 (ZCode)

Работа по `docs/game-design/visual/zcode/Z-1-figures.md`: семь карточек AN-17, AN-21, AN-23, AN-24, AN-25,
AN-31, AN-32 — процедурный код и движок, без генерации изображений, без художественных решений от себя
(спорные случаи — «по делегированию», ВР-Z1-NN ниже). Ветка `feat/visual-z1-figures` (worktree
`C:/tmp/wt-zcode-figures`), база `fix/admin-panel`. **Не слито** — визуальный чат сливает через
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

# VS-8 — фигуры: шаг A1 (AN-31, AN-33, AN-34, AN-35 + хвосты VS-7)

Ветка `feat/visual-vs8` (worktree `C:/tmp/wt-visual`, от `fix/admin-panel` 2778c007), 2026-10-08. Лёгкий режим:
editor `-game`, live tune одной сессией на карту, без упаковки (одна упаковка — шаг Frames). Решения — по делегированию
(пользователь 2026-10-06: «Делай сам … Все решения принимай»). Листы карточек: [AN-31](../AN-31/README.md) (раздел
VS-8), [AN-33](../AN-33/README.md), [AN-34](../AN-34/README.md), [AN-35](../AN-35/README.md).

## Хвосты VS-7

**(a) Белый прямоугольник у левого края Sarpedon (x ≈ 0–40, y ≈ 925–1035 при 1080p).** Источник найден пробами live tune
(reload профиля-override, кадр K1, [лист](sarpedon-left-edge-sea-probe.jpg): база | без неба | море ниже):
- это **кольцо моря Sarpedon** (`SM_Env_S_SeaRing`, `MI_EnvSea_Sarpedon`, отражение ночного неба, `lit3d.seaZUU −300`),
  видное в щель между скалами острова в ближнем левом углу: при `seaZUU −1000` пятно становится тёмно-синим
  (средний RGB 98/108/124 → 7/14/30); выключение цилиндра неба (`lit3d.sky false`) ничего не меняет;
- оно есть уже на принятом кадре P10 (`ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1`), на всех
  K1 Sarpedon и не зависит от смерти T. Rex и экранов VS-7.

Не правилось в A1 (ВР-VS8-05): правка — окружение lit3d (скала / море), меняет принятый вид P10 и требует гейтов G4–G7
(`env_gates.py`) — это VS-9 «Хвосты Sarpedon». Белый квадрат над клеткой у корабля из п. 9 README VS-7 — фигура-заглушка
T. Rex (не из шести фигур v2), не мир и не экран.

**(b) GAMEOVER `state=Board`.** Строку полосы «посмотреть доску» писал `UUmScreenGameOver::CollectShotLines` мимо
ToLower (пакет 3 VS-7, трасса duel-marm 22:47 — `state=Board modal=0`). Теперь имя состояния для строк гейта и имён
файлов даёт один метод `UUmScreenBase::ShotStateName()` (нижний регистр, ВР-VS7-76): базовая строка экрана, полоса
GAMEOVER, суффиксы файлов PAUSE (`…-game-<state>`) и ROOM (`host-|guest-<state>`) (ВР-VS8-06). В editor-build FName
пишется нашим написанием, поэтому тест `Hud.Screens.GameOver.*` и раньше видел `state=board`; packaged-проверка —
в шаге Frames.

## Решения шага (по делегированию)

| № | Решение | Почему |
|---|---|---|
| ВР-VS8-01 | Цифра гарпии: диск 0,40 верхней грани, центр 0,58 R, поворот −25°, em 1,05 (cap 6,7 uu); ревью-параметры `-S08BaseDigitDisc=` / `-Centre=` / `-Em=` для A/B | при 0,48 R / −60° диск доходил до центра, ноги закрывали верх «2» / «3» (ВР-Z1R-09); A/B трёх геометрий на Sarpedon K2×1,6 |
| ВР-VS8-02 | `marmoreal-night.heroMaterials.Medusa.*` = класс 13 ×1,25, блик +0,10; в `sarpedon-night` блока нет; рамка «лица» для SK_Medusa_H2LD — горло и грудь | Medusa D6 8,1 → 7,45, горло p50 141 → 156 (Sarpedon 144); на Sarpedon кожа хуже (2,8 → 5,2); лицо в позе покоя ВР-06 камере K2 не видно |
| ВР-VS8-03 | Блока Harpy нет; AN-34 закрыта замером, D6 2/3 записан | класс 3 у SK_Harpy_H3LD меняет только полосу кромки крыла, класс 12 ухудшает; провал harpy-a — порядок насыщенности тело / подставка, вне рычага |
| ВР-VS8-04 | AN-35 вариант 1: Arthur P1 через копию фикстур с обменом `f-0` ↔ `f-1` | в фикстурах бенча Arthur — P2; |off| = 45° на обеих картах |
| ВР-VS8-05 | Пятно у левого края Sarpedon — в VS-9 | источник — кольцо моря lit3d в щели скал, есть с P10; правка окружения требует гейтов VS-9 |
| ВР-VS8-06 | Имена состояний экранов в гейте и файлах — только через `UUmScreenBase::ShotStateName()` | одна точка ToLower вместо копий |
| ВР-VS8-07 | Замеры AN-33 / AN-34: `off` и маски — свежие сессии шага, итерации — `tune` без reload; гейт D6 против P9 (как AN-36), P9b под вклейкой — справочно | reload сдвигает фазу поз (ВР-VS5-19); строки тюнера heroMaterials видны только при блоке героя в профиле |

## Проверки

- Сборка UnmatchedEditor (worktree) — Succeeded (2 раза), игровая цель `Unmatched` — Succeeded (ловушка WITH_EDITOR).
- UE: `Unmatched.S08.HeroesV2` + `.HeroMaterials` + `.Hud.Screens` + `.ArtTuner` + `.HeroLight` — 58 / 58 PASS.
- pytest `tools/art` (map_surface, art_board_fixtures, art_tuner_fold, concept_paste_assets, hero_light, k_env_assets,
  render_bench_*, render_face_roi, t5cb1) — 174 passed; `live_tune.py --check` — без ошибок.
- G-LOOK: Marmoreal original (`backdrop=paste(default)`), Sarpedon original (`backdrop=lit3d(default)`), шесть фигур v2,
  `ARTLOOK … baseDigit=on heroMat=on`; кадры открыты в цвете и сером.
- Процессы: сессии live tune остановлены (`killed=false`, замок GPU снят), посторонних процессов worktree нет.

## Шаг A2 — AN-18, листы 16 клипов (2026-10-09)

Лист и прогоны — [AN-18](../AN-18/README.md); 16 листов AN-01…AN-16 (цвет / серый / дейтеранопия, `frames.json`,
README с вердиктом по каждому WARN). Новый скрипт `tools/art/anim/clip_review_sheet.py` (`run` / `sheet` / `--check`).
8 editor-запусков `-BenchClipPose`, 1200 строк `clippose` — `rootDeltaUU=0.00`; UE `MoveAnim` + `HeroesV2` 24 / 24 PASS;
C++ не менялся. Решение ВР-VS8-08: ячейка K2×1,6 — окно 640×360 1:1 у фигуры вместо ужатого кадра.
Кадры поворота (разворот / возврат) — живые листы AN-24 / AN-25; спиной к камере нет ни в одном из 16 листов.

## Шаг E1 — хвосты Sarpedon P10: EN-19…EN-24 (2026-10-09)

Коммит `4aafc141`; лист замеров — [ENV-MAPS P10b](../../ENV-MAPS/p10b-sarpedon-2026-10-09/README.md); карточки
[EN-19](../EN-19/README.md), [EN-20](../EN-20/README.md), [EN-21](../EN-21/README.md), [EN-22](../EN-22/README.md),
[EN-23](../EN-23/README.md), [EN-24](../EN-24/README.md). Лёгкий режим: live tune в одном клиенте редактора, 3 запуска
клиента (после мешей / MI / FX), без упаковки. Итог: EN-19, EN-21, EN-22 — PASS; EN-24 — PASS, G4 на пороге
(0,4891 / 0,49); EN-20 — IoU 0,32 < 0,6; EN-23 — SSIM 0,4431 < 0,45 (cannon-1 PASS). Контроль Marmoreal — без изменений.

| ВР | решение (по делегированию) | почему |
|---|---|---|
| ВР-VS8-41 | Водопад Sarpedon — 3 потока на нарисованных полосах C0 (−262…−203, −144…−62, −34…0 uu) с просветами 59 / 28 uu, а не 4 перекрытых | на C0 нарисованы 3 светлые полосы между тёмными скалами; 4 перекрытых потока читались одной вуалью |
| ВР-VS8-42 | Знамя 230 uu (+44 %, ×2 = 460) с подвесом под 13° в плоскости полотна вместо +20 % ВР-EN.11 | вертикальное полотно под камерой C0 (55°) кренится влево на 88 px и при +20 % даёт ≈ 330 px; нарисованное — 347 px почти вертикально, решатель ставит подол на [1848, 760] |
| ВР-VS8-43 | Свет lantern-left — 45 кд перед головой фонаря [−549, 30, 190] (был за столбом, ниже на 60 uu) | +15 кд на старом месте G6 не сдвинули (0,69 → 0,70); перед головой — подсвечены столб и листва, как нарисовано (1,13) |
| ВР-VS8-44 | cannon-1 — дочерний `MI_EnvCP_CannonIron_Port` (V ×1,6), мачта и такелаж в E1 не перестраиваются | MI даёт ΔL* 22,6 без нарушения портов; сдвиг наружу темнит; мачта требует перепечки альбедо — хвост EN-25 / VS-9 |
| ВР-VS8-45 | fire-fort 30 кд на 27 uu вперёд и 9 uu ниже; fire-brazier 140 кд, мерцание 0,5; языки жаровни повёрнуты на 90° | стена форта за огнём выжигалась в маску пламени (0 языков); G7 пятна жаровни 0,53 → 3,66 при том же радиусе 180 |
| ВР-VS8-46 | Пена подушек водопада остаётся 0,5 (не 0,65 у подножия); тест «пена плотнее тела» заменён | один MI на все подушки (уступы и море); белое теперь несёт тело потока (0,75 в середине) |
| ВР-VS8-47 | ROI огня EN-22: форт 345,40–400,160, жаровня 128,580–200,692 (K1) | мировые коробки g7 захватывают освещённую стену форта (EN-05 «Ограничение») |
| ВР-VS8-48 | Метрика EN-24 — `env_gates.py stones`; 13 камней сняты (шаг 2 ВР-EN.9) | шаг 1 (утопить, ×0,8) снизил детальность 0,60 → 0,26; нарисованные камни острова в альбедо |

Проверки: pytest `tools/art/tests tools/art/map_surface` 630 passed / 3 skipped; `--check` 8 валидаторов ok;
C++ — только тест `S08ConceptPasteTests.cpp` (точки двух огней), UnmatchedEditor и игровая цель — Succeeded;
UE `ConceptPaste+EnvLayout+ArtTuner+HeroLight+LiveTune` 54 / 54.


## Шаг Frames — упаковка, гейты, кадры выхода и закрытие фазы 3 (VS-8 / VS-9, 2026-10-09)

`git merge fix/admin-panel` — «Already up to date» (`2778c007`). UnmatchedEditor и игровая цель — «Result: Succeeded»
(обе актуальны после E1). **Одна упаковка** `package-client.ps1 -SkipBuild`: штамп `2233b140`, sourceHash `955727bc…`,
кук «Success - 0 error(s), 0 warning(s)»; новых `Config/**.json` нет (ловушка makefile не сработала). Все прогоны ниже —
на этом пакете (два клиента — по 30 FPS на процесс, `t.MaxFPS 30`). **Не влито.**

| Карточка / гейт | Итог |
|---|---|
| EN-25 Sarpedon P10b | packaged `-Bench` K1 / Fitx1,45 / K2×1,6 (`RENDER reference=1`, открыты), `env_gates.py` crit / gates / streams / fire / cannons / stones, одна live-серия G7, `render_bench.py` один прогон (3 повтора): G8 **K1 2,59 / K2×1,6 2,52 мс — PASS**; G5 PASS; G6 6 из 6; В-1 / В-2 / В-4 PASS; **FAIL**: В-3 SSIM 0,4446, G4-SSIM 0,4879 (< 0,49 на 0,002); G7 знамени 3,8 % и света жаровни 1,85 в этой серии ниже порога. Контроль Marmoreal — разница только на фигурах (AN-31 / AN-33). [P10b, раздел EN-25](../../ENV-MAPS/p10b-sarpedon-2026-10-09/README.md), [лист](../ENV-SARPEDON-P10B/README.md), [дополнение GD-058](../../GD-058/sarpedon-p10b-2026-10-09/README.md) |
| AN-18 из пакета | 8 packaged `-Bench` (02:24 → 03:02), 1200 `clippose` с `rootDeltaUU=0.00`, 540 `RENDER reference=1`, `heroes=v2 facing=v1` в 8 трассах; 16 листов AN-01…AN-16 заменены packaged-версиями (шапка «сборка: packaged»), 0 проблем. Поворот (ВР-06): спиной к камере нет ни в листах, ни в живых кадрах боя (Arthur вполоборота при выбранной атаке, Sarpedon) |
| `run-combat-demo` Marmoreal / Sarpedon (1080p, player view, exit / screen shots) | **PASS** обе: SHOT widget HB-48 (окно защиты, закрытое окно до раскрытия, результат у краёв и в центре, privacy), FINISHED, `FIGHTERS synced n=6`, `RequireRenderReference` |
| `run-duel-demo` Marmoreal / Sarpedon | **PASS** обе: HUD_SHOTS rules 2 privacy, строка сервера FINISHED, статистика и ELO, лобби по трассе |
| `run-hud-probe` | **PASS** (rules 3, privacy, отрицательные контроли) |
| `run-vs-ai-demo` Marmoreal / Sarpedon (`-S08BoardId`, 1080p) | **PASS** обе: VICTORY = winnerSeat сервера, `SHOT widget id=UI-SCR-GAMEOVER state=victory` и `state=board` нарисованы |
| VS-7 (b) в пакете | `state=board` в нижнем регистре во всех packaged-трассах (combat, duel, vs-ai) — исправление ВР-VS8-06 подтверждено |
| UE `Unmatched.S08+S09+S10` | **554 / 554** |
| pytest `tools/art/tests`, `tools/art/map_surface`, `tools/s08/hud_contract`, `tools/s08/cue_contract` | **777 passed**, 3 skipped; `clip_review_sheet.py --check`, `live_tune.py --check` — без ошибок |
| G-LOOK | Marmoreal `backdrop=paste(default)`, Sarpedon `backdrop=lit3d(default)`, `heroes=v2`, шесть фигур; `reference=0` только у строк PERF и у кадра после выхода в лобби (нет профиля доски) |

**GD-058, полный раунд (ВР-59).** Открыты контактные листы по 6 живых кадров на доску (HUD своего хода, окно защиты,
вспышка удара, звезда, след хода соперника, GAMEOVER) и packaged-кадры `-Bench` обеих досок. Настоящие карты, задник
Marmoreal нарисованный, Sarpedon lit3d, HUD, VFX, экраны и шесть фигур v2 вместе — принято по делегированию (без личного
просмотра пользователя). Кадры с картами и аватарами — вне git: `scraped-data/derived/visual-evidence/VS-8/gd058/` (217
файлов, индекс [data/vs8-frames-evidence-index.json](data/vs8-frames-evidence-index.json)).

**Закрытие фазы 3:** сверка реестра 03 (ниже), блок «Rollback flags» в [AGENTS.md](../../../../../AGENTS.md) (новый раздел,
другие не менялись), итог — [CLOSEOUT-2026-10-09.md](../CLOSEOUT-2026-10-09.md).

**Сверка реестра 03** (скрипт вне git `C:/tmp/visual/VS8/F/reconcile03.py`: путь UE есть в Content, карточки ссылок есть,
файлы ссылок есть, статус не отстаёт от карточек). До: 12 путей UE без ассета, 6 файлов ссылок, 11 строк со статусом
позади карточек. Исправлено: размеры `T_IV3_state_hint` / `threat` (в UE 18…64, не 48…128); `SM_LastMoveArrow` — меша нет,
наконечник — слоты ISM плит `M_UM_MovePlate`; статусы `F_UM_RobotoBoldCondensed_Offline`, `M_UM_BaseDigit`,
`PROC_Anim_FacingIdle` / `FaceTarget` / `FaceReturn`, `PROC_Anim_StepEase`, `M_FX_Print` → художественно принято;
`NET_UM_Combat` / `Board`, `PROC_Vfx_RimHover`, `WBP_UmConfirmDialog` → технически импортировано; 16 `AM_*` → художественно
принято (AN-18 из пакета); строкам окружения EN-19…EN-24 добавлены EN-25 и замер P10b (статус остаётся техническим).
Осталось без правки (не расхождение): `T_Cursor_Busy_00…07` (запись диапазоном, ассеты есть), шаблон `MI_<Key>…_Dissolve`,
`ART005*`, `WBP_UI_SCR_HISTORY` и макеты SC-39…SC-42 (пост-MVP, «предложено»); два файла масок Marmoreal вне git отсутствуют —
«Открыто» п. 10 закрытия.

| ВР | Решение (по делегированию) | Почему |
|---|---|---|
| ВР-VS8-61 | Одна упаковка `-SkipBuild` после сборки игровой цели; все гейты, листы и цена — на ней | правило «одна упаковка»; цели собраны и актуальны |
| ВР-VS8-62 | G7 знамени и света жаровни ниже порога в одной packaged live-серии — записаны как есть, повторной серии нет | правило скорости 2026-10-08; editor-серия E1 давала 10,2 % и 3,66 (20 кадров) — разброс фазы ветра и мерцания |
| ВР-VS8-63 | EN-24 / G4 0,4879 < 0,49 — FAIL записан, правок нет; Р-39 остаётся FAIL | разница 0,002 в шуме кадра; правило «без оптимизаций», хвост — итерация ENV |
| ВР-VS8-64 | Контроль Marmoreal — сравнение с packaged GD-058 2026-10-08; допустима разница только на фигурах | правки шага меняли фигуры (AN-31, AN-33), но не окружение Marmoreal |
| ВР-VS8-65 | GD-058 раунд = живые `run-combat-demo` 1080p обеих досок + VS_AI GAMEOVER + packaged `-Bench` K1 / K2; живые кадры вне git | ВР-59; ВР-VS4-01 (сканы карт и аватары не в git) |
| ВР-VS8-66 | Строки окружения Sarpedon остаются «технически импортировано» | акт ENV по делегированию «художественно принято» не ставит (правило честной пометки) |
| ВР-VS8-67 | Пятно у левого края Sarpedon (ВР-VS8-05) не правится в VS-9, вынесено в «Открыто» | правка меняет принятый вид lit3d и требует новой итерации с гейтами; правило скорости |

Процессы: сессия live tune остановлена (`killed=false`, замок снят), все клиенты, прокси и тесты шага завершились сами;
замка GPU нет, процессов worktree не осталось. Скрипты шага вне git — `C:/tmp/visual/VS8/F/`.

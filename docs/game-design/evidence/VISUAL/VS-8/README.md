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

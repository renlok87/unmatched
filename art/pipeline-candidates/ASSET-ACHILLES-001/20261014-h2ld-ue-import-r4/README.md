# ASSET-ACHILLES-001 — UE-реимпорт модели r3 (этап 7a, профиль импорта r4), 2026-10-14

Пилот скилла 3d-model-pipeline. Делегирование пользователя: 2026-10-06 «Не знаю. Делай сам, меня это не касается. Все
решения принимай»; 2026-10-13 «Сгенерировать модели можно все Но сначала чтобы полностью обкатать скилл и итерационно его
улучшить, можно это сделать на небольшой выборке». Трат нет.

## Вход
- Модель r3 принята парой r3: Sol 8.1 + Opus 8.8 → итог 8.1 pass (`../evidence/acceptance/20261014-r3/final.json`).
  Доработка r3 — только веса: `rig.junctions` arm|cloak и arm|cuirass, полоса 0,04 м (рваная кромка за правой подмышкой).
- Профиль `../build-profiles/achilles-h2ld-lookdev-ue-import-r4.json` (rev 4) — копия rev 3, входы переведены на
  `../20261014-h2-lookdev-r3` (профиль `achilles-h2-lookdev/4`) и `../20261014-h2-bake-r3`. Генератор —
  `../evidence/stage7a-20261014/tasks/make_profile_r4.py` (проверяет каждое допущение assert-ом).
  - LUT остаётся UE look-dev r3 `T_UM_MatLUT_Achilles_UE_r3.dds` (`2a03ce7a…`: тёплая бронза через F0, sheen ткани 0,03).
    Основа его overrides — LUT look-dev r2; LUT look-dev r3, его overrides и TeamAccent байт-в-байт равны r2.
  - `TeamDyeGain` 22.779 и `TeamDyeCeiling` 8.6256 по правилу LDV-13 из `ld-team-accent-report.json` r3
    (Y_p50 0,03512, Y_p95 0,10434) — не изменились.
  - Не менялись: оси, `figure_top_part` tripo_part_6 (гребень 0,55 м), сокеты, подставка (верх 5,805 uu по rig-report r3),
    треугольники (43 604 + 1 200 + 1 348), настройки текстур.
- Конфиг съёмки и сверки `../20261014-h2ld-ldc-ue/review-config-r4.json` (генератор `tasks/make_review_config_r4.py`):
  `run_dir` → этот прогон, `concept_zones` → `measure-report.json` look-dev r3 (равен r2), `clips_reference` →
  `../20261014-h2anim-r3/reports/ue-measure-clips.json`.

## Шаги (references/ue-import-package.md §4.4; свой скрытый редактор, каждый шаг под `ue_lock.py`)
Редактор: `-RenderOffScreen` + `tools/tripo-pipeline/review/ue_py/console_drop.py` (`UE_CONSOLE_DROP`), MCP :8123.
1. Снимок `../evidence/stage7a-20261014/snapshot-before-r4.json` (0 dirty).
2. Удалены 17 ассетов прогона `../20261014-h2ld-ue-import-r3` (`tasks/delete_prev.py`): MI → меши → текстуры.
   В папке H2LD ничего не осталось (`left []`).
3. `init` → `register-source tripo-b467cd91-h2` → `run` → `ue-import --ue-folder /Game/PipelineCandidates/Achilles/H2LD`.
   Повтор дал `skipped`.
4. Носитель превью клипов и клипы — `../20261014-h2anim-r3/README.md`.
5. `ue_hero_lookdev.py verify` → `../20261014-h2ld-ldc-ue/review/verify/verify-v4.json`.
6. Look-dev съёмка r4 → `../20261014-h2ld-ldc-ue/review/r4/`.
7. Снимок после — `snapshot-after-r4.json`.
8. `M_UM_Figure_v2`, грязный после импорта MI, перезагружен без сохранения (`discard-master-r4.json`):
   грязных пакетов 0. Редактор закрыт по `quit-editor`.

## Результат
- `reports/ue-import-report.json`: `technically_imported`, 26/26 checks.
  - Верх фигуры 55,0 uu (гребень, сборка) / 54,9931 uu (UE).
  - Фронт +X однозначен (ошибка 0,0004 uu).
  - Скелет канонический, 18 костей (`weapon_R`).
  - Слот `M_Achilles_H2_Atlas`, UV 2 канала, дублей нет.
- `verify-v4`: 14/14, включая `h2anim_clips_play_on_mesh` и `nothing_dirty`; скаляры MI прочитаны обратно (TeamDyeGain
  22.779, TeamDyeCeiling 8.6256, UseTeamAccent, UseUV1Metres).
- Снимок после: `protected_unchanged: true`, добавленных ассетов нет. Изменились только `.uasset` Achilles: H2LD (17),
  H2Anim (4), `Rig/SK_Achilles` (носитель). Скелет `Rig/SK_Achilles_Skeleton` не изменён.
- Подставка без просвета (`tools/tripo-pipeline/review/base_seethrough.py` после фикса 9322d489, `--aim surface`) на
  импортированной паре `../20261014-h2-lookdev-r3/export/SM_Achilles_H2LD_Base.fbx` + `SK_Achilles_H2LD.fbx`:
  base_only 0,00 uu², with_figure 0,00 uu² во всех 5 направлениях — PASS (порог HANDBOOK §8 0,1).
  Отчёт `../evidence/stage7a-20261014/base-seethrough-v2-r4.json`. 8 открытых петель верха остаются (под сандалиями и
  пяткой копья), но доска сквозь них не видна.

## Look-dev UE r4 (лёгкая проверка регрессии; только диагностика, итераций нет)
`ue_hero_lookdev.py review --config ../20261014-h2ld-ldc-ue/review-config-r4.json --tag r4`.
Кадры успели сойтись (F153):
- прогрев `warmup_mean_abs_diff` начался с 0,99 и закончился на 0,30–0,40 (39 захватов);
- последний `settle` каждого кадра ≤ 0,75.

Глазами по листу `achilles-lookdev-sheet-r4.jpg`: тёплая бронза, плащ красный по концепту, кожа не розовая; P1 и P2 красят
только ремни и кайму. Регрессии против r3 нет.

| Зона | r3 (импорт r3), нейтр. / чтение −0,75 EV | r4 (импорт r4), нейтр. / чтение | концепт |
|---|---|---|---|
| бронза: hue / sat | 29,1 / 0,617 · 27,8 / 0,672 | 28,7 / 0,619 · 28,1 / 0,669 | 30,9 / 0,574 |
| бронза: Y линейная | 0,1729 · 0,0924 | 0,1739 · 0,0917 | 0,1136 |
| плащ (якорь): hue / sat | 1,2 / 0,678 · 0,7 / 0,730 | 1,8 / 0,675 · 0,0 / 0,721 | — |
| кожа: hue / sat | 28,5 / 0,584 · 25,9 / 0,648 | 28,8 / 0,582 · 25,9 / 0,648 | — |

- Якорь экспозиции k: 0,761 → 0,730 (нейтр.), 1,519 → 1,516 (чтение).
- Вердикты зон те же, кроме бронзы. Её отношение Y к якорю 1,159 → 1,118 вошло в допуск 0,15 на нейтральной экспозиции:
  «вне на обеих» → «вне только на экспозиции чтения».
- Сдвиг — шум съёмки, а не модель: LUT, текстуры и медианы концепта те же байты.

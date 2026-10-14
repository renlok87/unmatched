# ASSET-ANCIENT-LESHEN-001 — UE-реимпорт модели r3 (этап 7a, профиль импорта r5), 2026-10-14

Пилот скилла 3d-model-pipeline. Делегирование пользователя: 2026-10-06 «Не знаю. Делай сам, меня это не касается. Все
решения принимай». Трат нет.

## Вход
- Модель r3 принята парой r3: Sol 8.1 + Opus 8.8 → итог 8.1 pass (`../evidence/acceptance/20261014-r3/final.json`).
- Профиль `../build-profiles/ancient-leshen-h2ld-lookdev-ue-import-r5.json` (rev 5) — копия rev 4, входы переведены на
  `../20261014-h2-lookdev-r3` и `../20261014-h2-bake-r3`.
  - LUT и TeamAccent — выход look-dev r3 как есть.
  - `TeamDyeGain` 29.355 по тому же правилу LDV-13 (Y_p50 0.02725 из `ld-team-accent-report.json` r3; было 29.282).
    `TeamDyeCeiling` 15.0905 не изменился.
  - Не менялись: Saturation 1.22, Fix slot A, `figure_top_part` tripo_part_9, `axes.front_from_best_bound_fit`,
    сокеты, настройки текстур.

## Шаги (references/ue-import-package.md §4.4; свой скрытый редактор, каждый шаг под `ue_lock.py`)
1. Снимок `../evidence/stage7a-20261014/snapshot-before-r5.json`.
2. Удалены 17 ассетов прогона `../20261014-h2ld-ue-import-r4` (`tasks/delete_prev.py`). В папке H2LD ничего не осталось.
3. `init` → `register-source tripo-fd1d4e21-h2` → `run` → `ue-import --ue-folder /Game/PipelineCandidates/AncientLeshen/H2LD`.
   Повтор дал `skipped`.
4. Клипы — `../20261014-h2anim-r3/README.md`. Там же переимпорт носителя превью (пробел инструмента F145).
5. `ue_hero_lookdev.py verify` → `../20261014-h2ld-ldc-ue/review/verify/verify-v5.json`.
   Скаляры MI → `mi-scalars-v5.json`.
6. Снимок после — `snapshot-after-r5.json`.

## Результат
- `reports/ue-import-report.json`: `technically_imported`, 26/26 checks.
  - Высота по черепу 55,003 uu; верх рогов 73,56 uu.
  - Фронт +X однозначен (ошибка 0,0005 uu).
  - Скелет канонический.
- `verify-v5`: 14/14, включая `h2anim_clips_play_on_mesh` и `nothing_dirty`.
- Скаляры MI прочитаны обратно: Saturation 1.22, FixGainA 1.1, TeamDyeGain 29.355.
- Снимок после: `protected_unchanged: true`. Изменились только `.uasset` AncientLeshen: H2LD (17), H2Anim (4),
  `Rig/SK_AncientLeshen` (носитель). Скелет `Rig/SK_AncientLeshen_Skeleton` не изменён.

## Look-dev UE r4 (лёгкая проверка: регрессии нет; только диагностика, итераций нет)
`ue_hero_lookdev.py review --config ../20261014-h2ld-ldc-ue/review-config-r5.json --tag r4` →
`../20261014-h2ld-ldc-ue/review/r4/`. Глазами по листу `ancientleshen-lookdev-sheet-r4.jpg`:
- вороны сидят;
- кость, кора и мох — как в r3;
- P1 и P2 красят только ворон.

| Зона | r3 (импорт r4) | r4 (импорт r5) |
|---|---|---|
| кора (якорь), sat — нейтр. / чтение | 0,399 / 0,451 (d +0,008 / +0,060) | 0,489 / 0,524 (d +0,098 / +0,133, вне допуска 0,10 при чтении) |
| кость, `tasks/bone_measure.py` Y — нейтр. / чтение | 0,63 / 0,98 | 0,96 / 1,46 |

**Причина сдвига — сходимость кадра, не модель.** Входы коры совпадают:
- в таблице LUT r2 и r3 отличается 1 байт (только перья);
- значения коры в LUT те же;
- медианы коры в `measure-report.json` look-dev одинаковые.

Отличие — прогрев съёмки. Покадровая разность `warmup_mean_abs_diff` в r3 была 2,3–2,8 (кадр ещё не сошёлся, мягче и
светлее), в r4 — 0,3–0,8. Поэтому якорь экспозиции (кора) в r4 темнее: k 0,28 → 0,44. Значения Saturation и FixGain
подбирались в r2/r3 по кадрам, которые не сошлись.

Не правилось (лёгкий режим, порог приёмки не нарушен). Это открытый пункт для съёмки K1/K2 этапа 7b.

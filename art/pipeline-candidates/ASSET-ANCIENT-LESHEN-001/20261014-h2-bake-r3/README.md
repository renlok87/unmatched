# ASSET-ANCIENT-LESHEN-001 — модель r3 (этап 5, последний цикл модели), 2026-10-14

Пилот скилла 3d-model-pipeline. Делегирование пользователя: 2026-10-06 «Не знаю. Делай сам, меня это не касается. Все
решения принимай». Трат нет (Tripo/SYNTX не расходовались), Unreal не запускался.

## Зачем
- Приёмка клипа HitReact r1 (`../evidence/acceptance-anim/20261014-r1/HitReact/card.json`, 7,5, вето D=0): ворона на
  правом предплечье висит отдельно от руки.
- Замер: это зазор модели в покое, а не клипа. Часть Tripo 8 жёстко на `arm_lower.R`; в покое до кисти 2,90 см, до
  предплечья 2,97 см. Точка опоры под ней во всех клипах смещается ≤ 0,02 см.
- На концепте ворона сидит на предплечье. Решение оркестратора 2026-10-14: чинить моделью, а не ключами клипа.

## Что изменено
- Инструмент `tools/tripo-pipeline/blender/h2_bake`: необязательный ключ профиля
  `prepare.part_offsets_m = {tripo_part_N: [dx, dy, dz]}` (`profile.part_offsets`, `st_prepare.py`).
  - Сдвигает часть на обоих двойниках GLB в финальной рамке (м, −Y вперёд) после frame map. Сама карта и все остальные
    части не меняются ни на бит.
  - Без ключа код прежний. Тест `h2_bake/tests/test_part_offsets.py`: prepare-report Medusa совпадает байт в байт, сдвиг
    двигает только указанную часть. Весь набор `python -m pytest tools/tripo-pipeline/blender/h2_bake/tests -q` —
    71 passed.
- Профили (новые файлы, у каждого `history.previous_profiles`):
  - `../build-profiles/ancient-leshen-h2-bake-h2-r3.json` — только `prepare.part_offsets_m.tripo_part_8 = [0.0, 0.0425, 0.015]`.
    В осях арматуры это (−4,25; 0; +1,5) см: на 4,25 см назад и на 1,5 см вверх. Ворона садится на внешнюю сторону
    предплечья над запястьем, как на концепте.
  - `ancient-leshen-h2-lookdev-r3.json` и `ancient-leshen-h2-lookdev-teamaccent-r3.json` — только источник (прогон,
    профиль, пины).
- Как выбрана посадка (скрипты вне репо `C:/tmp/leshen-anim-r2/seat_search.py` и `seat_search2.py`):
  - Все вершины тела, кроме вороны, с весом `arm_lower.R` < 0,95 во всех кадрах четырёх клипов D-11 переведены в
    rest-рамку предплечья. Так учтены кисть, запястье, локоть и ствол.
  - Перебор по сетке 0,125 см с условиями: зазор до предплечья 0,05–0,2 см и не ближе 0,3 см к этому облаку.
  - Первый вариант (−3,25; +1; +1) см отклонён: когти правой кисти входили в ворону на замахе LungeAttack (к. 3–5).

## Результаты (отчёты этого прогона)
| Проверка | Значение |
|---|---|
| стадии prepare … manifest | все код 0 и `H2_BAKE_STAGE_OK`; `prepare-report.json#part_offsets_m`; сдвинута только часть 8 (frame_map как в r2) |
| треугольники | тело 44 438, подставка 2 268 (как r2); bounds как r2 |
| пробы | 7/7 `.blend` и 7/7 FBX, `validate_clip` skeletal mesh PASS |
| seams | passed; наибольшее новое пятно 8 px (как r2) |
| ворона на предплечье в покое | зазор 0,160 см, без пересечения (проверено чётностью лучей), опора под лапами 100 % `arm_lower.R`, до кисти 2,16 см |
| детерминизм (`reports/determinism-report.json`, повтор `C:/tmp/ASSET-ANCIENT-LESHEN-001-r3-repro`) | FBX, BC, ORM, TeamMask, UV и отчёты стадий identical (rig-report — после нормализации пути); N / N_OpenGL 4K — ≤ 1 уровень на 5 px (GPU, HANDBOOK §4.3); превью и compose не сравниваются |
| look-dev `../20261014-h2-lookdev-r3` | все стадии `ld_*`; таблица тона: `t_cap` 2.0, out_of_tolerance [], floor — feathers (как r2). Детерминизм против `C:/tmp/ASSET-ANCIENT-LESHEN-001-r3-ld-repro`: текстуры и FBX identical; превью и отчёты TeamAccent на Cycles различаются (как r2) |
| TeamAccent | `ta_maps` / `ta_report` passed, доля 6,04 % (перья, как r2) |

Крупные планы сдачи этапа 3 (`capture_acceptance_set.py` → `C:/tmp/leshen-stage5-r3-check/frames`, не evidence) осмотрены:
close-hands, turn-090/225, pose-01 … 04. Ворона сидит на предплечье в покое и при поднятой руке (pose-02); кисти, череп и
корни — как в r2.

Дальше — у оркестратора: приёмка модели r3, затем UE-реимпорт и приёмка клипов. Клипы на этом риге — `../20261014-h2anim-r3`.

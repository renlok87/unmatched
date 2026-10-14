# ASSET-ANCIENT-LESHEN-001 — этап 6, клипы на модели r3 (headless), 2026-10-14

Пилот скилла 3d-model-pipeline. Делегирование пользователя: 2026-10-06 «Не знаю. Делай сам, меня это не касается. Все
решения принимай». Трат нет. Unreal и приёмка — не здесь: их делает оркестратор после закрытия редактора Achilles 7a.

## Вход
- Приёмка клипа HitReact r1 (`../evidence/acceptance-anim/20261014-r1/HitReact/card.json`): вето D=0, ворона на правом
  предплечье висит отдельно от руки. Это зазор модели в покое (2,90 см), а не клипа. Модель исправлена на этапе 5 r3:
  `../20261014-h2-bake-r3/README.md`, ворона посажена на предплечье через `prepare.part_offsets_m`.
- Спека `../build-profiles/ancient-leshen-h2anim-r3.json` (`history.previous_profiles` = `ancient-leshen-h2anim.json`).
  Изменены только `target.sk_fbx`, `target.base_fbx`, `target.sha256` (`541086d4…ab55`, bake r3), `run_dir` и тексты.
  `clips.*` — без изменений.
- Прежние спека и прогон `../20261014-h2anim` не менялись. Строка `H2ANIM["AncientLeshen"]` в
  `tools/tripo-pipeline/anim/clip_manifest.py` переведена на спеку r3 (разрешено оркестратором).

## Результат (`reports/h2anim-run.json`, код 0)
| Клип | validate | контакты | WARN | FBX sha256 |
|---|---|---|---|---|
| Idle | PASS | PASS (loop_seam PASS) | — | `477e89f0…c514` |
| LungeAttack | PASS | PASS | skin_stretch: 1 ребро arm_upper.R к. 4–5, ×3,94 (как r1) | `b7835898…2214` |
| HitReact | PASS | PASS | — | `93493738…aafb` |
| DeathSettle | PASS | PASS | — | `d17cf6f3…58af` |

- Позы костей совпадают с r1 во всех кадрах (матрицы pose-костей и rest, разница 0,0;
  `C:/tmp/leshen-anim-r2/pose_compare.py`). FBX отличаются от r1 только мешем: сдвинута ворона.
- `ik_unreached_frames` и пики сдвига — как в r1.
- Корни: `reports/roots-planted.json` — те же числа, что в r1. Внешние корни r > 6 см ≤ 0,334 см (0,49 % H).

## Вороны (`reports/rider-gap.json`, скрипт `C:/tmp/leshen-anim-r2/rider_gap.py`)
| Ворона | r1: зазор до опоры по кадрам | r3: зазор до опоры по кадрам |
|---|---|---|
| правое предплечье (часть 8, `arm_lower.R`) | 1,84–2,96 см во всех клипах; HitReact к. 0…10: 2,90 / 2,68 / 2,45 / 2,54 / 2,66 / 2,71 / 2,77 / 2,82 / 2,86 / 2,89 / 2,90 | 0,160 см в каждом кадре всех четырёх клипов; без пересечения (со знаком ≥ +0,16 / +0,19 см); опора 100 % `arm_lower.R`; дрейф 0; ствол и череп ≥ 3,18 см |
| левое плечо (часть 10, `spine`) | касание 0,0001 см (лапы утоплены ≤ 0,04 см) | без изменений |
| левое предплечье (часть 11, `arm_lower.L`) | 0,152 см | без изменений |

- Крупные планы Workbench осмотрены: HitReact к. 0–4 (q34, left, front) и LungeAttack к. 3–5 (right, back, q34b).
  - HitReact: ворона сидит на предплечье, просвета нет.
  - LungeAttack: на замахе когти проходят рядом с вороной, но не входят в неё.
- Листы `preview/AncientLeshen-<Clip>-blender-sheet.jpg` — как r1.

## Манифест
`clip_manifest.py build` → `MANIFEST_CHECK PASS clips 35 production 28`.
- LESH-* в статусе `measured`: UE-импорта с новым sha256 FBX ещё нет. После `h2anim_ue.py import` сборка вернёт
  `technically_imported`.
- Побочно пересобраны записи ACH-* (`measured` → `technically_imported`) по UE-отчётам Achilles, которые лежат в рабочем
  дереве.

## Дальше (оркестратор, после закрытия редактора Achilles 7a)
1. UE-реимпорт модели r3 (H2LD из `../20261014-h2-lookdev-r3`) и приёмка модели r3.
2. Шаги §6.4 под `ue_lock.py` со спекой r3: `skeleton`, `import`, `measure`, `frames`, `sheet`. Затем `clip_manifest.py build`.
3. Приёмка клипов. Для HitReact — r2 с `previous_card` = карточка r1; остальные клипы получили новые FBX, их приёмку
   решает оркестратор.

## UE (этап 7a, свой скрытый редактор), 2026-10-14
Редактор `-RenderOffScreen` + `ue_py/console_drop.py` (`UE_CONSOLE_DROP`), MCP :8123, каждый шаг под `ue_lock.py`;
закрыт по `quit-editor`, грязных пакетов 0 (`M_UM_Figure_v2`, грязный после импорта MI, перезагружен —
`../evidence/stage7a-20261014/discard-master-r5.json`).

**Обход пилота: носитель превью клипов (пробел инструмента F145).** `h2anim_ue.py skeleton` ничего не делает, если скелет
уже есть (`canonical_skeleton.py`). Поэтому меш-носитель `/Game/PipelineCandidates/AncientLeshen/Rig/SK_AncientLeshen`
(его спека называет `ue.mesh_for_preview`, на нём снимают `frames` и `measure`) оставался с геометрией bake r2: ворона
висела отдельно от предплечья. По разрешению оркестратора носитель переимпортирован из `../20261014-h2-bake-r3/export/SK_AncientLeshen_H2.fbx`
на существующий скелет задачей `../evidence/stage7a-20261014/tasks/refresh_carrier.py`. Отчёт: `reports/ue-carrier-refresh.json`.
- Опции импорта те же, что в `canonical_skeleton.py`, плюс `options.skeleton` и `replace_existing`.
- Источник носителя теперь bake r3 (было bake r2).
- Скелет не изменился: опорная поза 17 костей до и после совпадает (`ref_pose_equal: true`), `.uasset` скелета не изменён.
  Сохранён только носитель.
- Число вершин и габариты прежние: ворона сдвигается внутри габарита.
- Проверка на кадре: на HitReact к. 2 (`preview/ue/*-f02-*`) больше нет висящей вороны, как в r1.

**Клипы** (спека `ancient-leshen-h2anim-r3.json`):
- `skeleton` — скелет уже есть, 17 костей.
- `import` — все 4 клипа, legacy-импорт, root lock. sha256 FBX = `export/` этого прогона.
- `measure` — длительности 2,333 / 0,583 / 0,417 / 0,875 с. Кость 0 неподвижна, масштаб 1,0, смещение кадра 0 равно 0.
  Пики те же, что в r1.
- `frames` по клипу: `--base …/SM_AncientLeshen_H2LD_Base` и `--light-pinned ASSET-HARPY-001/20260929-h3ld-ue/review/b3.2/review-b3.2.json`.
  Плюс крупный план LungeAttack к. 5, 7, 8, 10 (`--closeup`) и `sheet`.
- Отчёты: `reports/ue-*.json`, кадры: `preview/ue/`, лист: `preview/AncientLeshen-H2Anim-ue-sheet.jpg`.
- Манифест: `clip_manifest.py build` → `MANIFEST_CHECK PASS clips 35 production 28`, LESH-* `technically_imported`.

**Крупные планы Blender** `preview/closeups-blender/` — для приёмки клипов r2 (те же кадры и виды, что в r1):
- Рендер: Workbench 1100 px, `C:/tmp/leshen-anim-s6/closeup_probe.py` (скрипт r1).
- Центр и размер кадра в r1 не записаны, поэтому выбраны заново (см. команды ниже).
- Замер корней совпал с r1.
- Кадры и центры (см, оси арматуры) / ширина кадра (см):
  - HitReact к. 2 front/left/q34: (0, 0, 42) / 60.
  - LungeAttack:
    - к. 4 q34r, к. 5 front/q34r/back: (0, 0, 52) / 55;
    - к. 8 front/q34/right: (5, 0, 44) / 60;
    - к. 10 front: (0, 0, 40) / 60.
  - DeathSettle к. 21 front/left/q34: (0, 0, 33) / 75; к. 13 q34r: (0, 0, 40) / 65.
  - Idle к. 14 и к. 42 q34: (0, 0, 50) / 45; к. 14 front: (0, 0, 22) / 45.

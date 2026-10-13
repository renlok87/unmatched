# ASSET-ANGEL-001 — этап 6, доработка клипов r2 (2026-10-14)

Пилот скилла 3d-model-pipeline. Делегирование пользователя: 2026-10-06 «Не знаю. Делай сам, меня это не касается. Все
решения принимай». Трат нет (Tripo/SYNTX не расходовались).

## Вход
- Карточки приёмки r1: `../evidence/acceptance-anim/20261014-r1/LungeAttack/card.json` (5,6, rework_blender, вето D=0:
  рукоять уходит из кулака на к.5–9) и `../evidence/acceptance-anim/20261014-r1/DeathSettle/card.json` (7,5,
  rework_blender, C=1: правый локоть согнут на к.13–21). Исправлялись только пункты их `rework_fix_list`.
- Спека: `../build-profiles/angel-h2anim-r2.json` (`history.previous_profiles` = `angel-h2anim.json`); прежние спека и
  прогон `../20261014-h2anim` не менялись. Idle и HitReact — ключи без изменений, FBX побайтно совпали с r1.

## Что изменено
| Клип | Пункт r1 | Ключи спеки: было → стало |
|---|---|---|
| LungeAttack | D (к.5–9, хват) | `aim weapon.R` к.2/4/7/9/12 → `aim hand.R` с `from` = ось оружия в rest (0,181; −0,181; 0,967): кость `weapon.R` без ключей, меч жёстко в кулаке; `hand_follow.keep_weapon_world` и `hand_rot` убраны |
| LungeAttack | C (к.5–7 удар с весом) | к.7 и к.9: `aim arm_upper.R`/`arm_lower.R` с `from2/to2` (плечо поднято вбок, поворот плеча внутрь 75°, локоть 130°, без скрутки предплечья), клинок к.7 (0,45; 0,75; −0,48) — рубящая диагональ поперёк корпуса, к.9 (0,1; 0,85; −0,5) — проводка; к.12: `aim arm_upper.R`/`arm_lower.R` к rest (запястье ≤ 6°) |
| LungeAttack | R (к.2–4 замах) | к.4: spine (3; −8; −22) → (4; −15; −34), head (0; 2; 14) → (0; 4; 24), hips_loc (−0,4; 0; −0,1) → (−0,5; 0; −0,1), клинок (−0,1; −0,5; 0,86) → (−0,6; −0,2; 0,77) — вверх-назад над правым плечом |
| DeathSettle | C (к.13–21 опора) | spine к.12 (21,2; 11; −5) → (10; 11; −5), к.16 (25; 13; −5) → (7; 8; −5), к.21 (24,2; 12,6; −5) → (6; 7; −5): плечо не опускается к кисти, локоть почти прямой; острие в той же точке (8,5; −10,5; 6,0) см |

## Числа (своя проверка `C:/tmp/angel-anim-r2/grip_check.py`, headless, по FBX клипа)
- LungeAttack: поворот `weapon.R` относительно `hand.R` против rest — **0,00° на всех 15 кадрах** (r1: до 120,3°, к.8);
  излом запястья ≤ 31,0° (к.6), локоть 113–132°, скрутка локтя 0°, отклонение от оси сгиба ≤ 13,3°.
- DeathSettle: правый локоть к.13–21 **134,1–138,9°** (r1: 101,6–116,5°); хват — прежний механизм r1 (меч
  разворачивается в кулаке остриём вниз, 160–169° на к.13–21), острие на (8,5; −10,5; 6,0) см во всех кадрах опоры.
- Предел скина H2 правой руки (изолированные пробы на ключах, `clip_contact_check` skin_stretch): разгибание локтя
  > ~141° — FAIL (с 146°, WARN с 131°), скрутка предплечья > ~20° — FAIL, локоть, согнутый против оси сгиба (рука
  вперёд, предплечье вниз), — FAIL; плечо вперёд/вбок до 90° и поворот плеча — PASS; излом и скрутка кисти до 35° —
  без WARN. Поэтому опорная рука почти прямая, а не 180°.

## Результат (`reports/h2anim-run.json`, код 0)
| Клип | validate | контакты | WARN | FBX sha256 |
|---|---|---|---|---|
| Idle | PASS | PASS | — | `28ff7a6e…16c0` (= r1) |
| LungeAttack | PASS | PASS | skin_stretch: 2 ребра локтя к.6–9, max 3,5× | `1dd49a62…d2d0` |
| HitReact | PASS | PASS | — | `6a66844d…c7a0` (= r1) |
| DeathSettle | PASS | PASS | limb_body_L 1–2 пары (как r1), skin_stretch шея + 11 рёбер локтя | `f307445b…4841` |

## UE (свой скрытый редактор, MCP :8123, `-RenderOffScreen` + `ue_py/console_drop.py`, `UE_CONSOLE_DROP`)
- `h2anim_ue.py import` всех 4 клипов из этого прогона (Idle/HitReact — те же байты FBX), `measure`, `frames` по клипу с
  `--base /Game/PipelineCandidates/Angel/H2LD/Meshes/SM_Angel_H2LD_Base --light-pinned
  ASSET-HARPY-001/20260929-h3ld-ue/review/b3.2/review-b3.2.json`, крупный план LungeAttack к.5–9, `sheet`. Отчёты —
  `reports/ue-*.json`, кадры — `preview/ue/`, лист — `preview/Angel-H2Anim-ue-sheet.jpg`. Грязных пакетов 0 до и после.
- Регистрация манифеста: `H2ANIM["Angel"]` в `tools/tripo-pipeline/anim/clip_manifest.py` → `angel-h2anim-r2.json`
  (разрешено оркестратором); `clip_manifest.py build` → `MANIFEST_CHECK PASS`, ANG-* `technically_imported`.
- Notify `Contact` на новом LungeAttack нет (как и в r1): его ставит `de010.py apply` на шаге 7b.

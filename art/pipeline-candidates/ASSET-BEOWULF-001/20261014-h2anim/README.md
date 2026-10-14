# ASSET-BEOWULF-001 — этап 6: 4 клипа D-11 (headless), 2026-10-14

Фигура-проверка доработанного скилла 3d-model-pipeline (пользователь 2026-10-14: «Одна фигура-проверка»). Этап 6 —
только авторинг и валидаторы; приёмка клипов — шаг 7a.2 после UE-импорта (ДС-1).

## Входы
- Модель: `20261014-h2-bake-t4/export/SK_Beowulf_H2.fbx` (sha256 `f86c7b02…3eab0`) и `SM_Beowulf_H2_Base.fbx`; приёмка
  модели r1 — pass 8,1 (Sol 8,1 + Opus 8,1).
- Спека: `build-profiles/beowulf-h2anim.json` (sha256 `d3227542…9660`), `character` Beowulf, `ue_hero` Beowulf,
  `weapon.extra_parts` = `["weapon.R", {"bone": "arm_lower.L", "islands": true}]` (низ рукояти с навершием и щит с умбоном
  проверяются в `clip_contact_check` как оружие, RB-09).
- Источник движения (ДС-6): паттерн библиотеки того же класса оружия — спека Angel r2 (`ASSET-ANGEL-001/build-profiles/
  angel-h2anim-r2.json`, все 4 клипа приняты на 7a.2) ← клипы меча King Arthur. SYNTX не тратился.

## Отличия от образца Angel r2 (всё остальное — ключи образца как есть)
| Клип | Что | Почему (прогоны-пробы в `C:/tmp/beowulf-s6`, удалены) |
|---|---|---|
| все | `from`/`from2` в aim — rest-оси Beowulf (клинок (0,220; −0,192; 0,956), плечо, предплечье, нормаль локтя) | aim задаёт поворот от rest-направления своей кости |
| LungeAttack | `hand_follow.anchor_offset` (3; −11,5; 3) вместо (5; −12; 0) | у образца рука Beowulf не доставала цель на к.1–5 (дефицит 2,19 см, рука прямая); теперь запас 1,25 см, локоть 112–131° |
| DeathSettle | **переавторинг 2026-10-14** (разбор оркестратора): без опоры острием и без обратного хвата — меч в исходном хвате (weapon.R без ключей) опускается и ложится плашмя; `hand_follow` и `contact.weapon_tip_frames` сняты; правая рука — aim arm_upper.R/arm_lower.R/hand.R; корпус, таз, голова, левая рука — тайминг образца (к.3/6/7/9/12/16/21), spine к.12/16/21 (10; 15; −5), (8; 18; −5), (7; 17; −5) | обратный хват образца (меч в кулаке на 154–159°) нарушал вето F95 и открывал канал рукояти в кулаке (`-f21-front` прежнего прогона); опора острием в исходном хвате недостижима (рука 11,1 см, меч 23,6 см от хвата: хват пришлось бы опустить ниже бедра или перевернуть кисть). Вариант с опусканием таза с к.9 давал видимое рваное ребро у правой щиколотки на к.11 — оставлен тайминг таза образца |
| Idle | ключи `hips_loc` к.1 (0; −0,02; −0,03) и к.59 (0; 0,02; −0,03) | ноги в rest прямые (16,328 из 16,329 см): у к.0 сдвиг таза опережал опускание, IK стоп недотягивал на к.1–2, 58–59, скольжение 0,48 % H при допуске 0,5 %; стало 0,07 % |
| HitReact | к.7 `hips_loc` z −0,05 (было 0) | то же на к.7–8: скольжение 0,48 % H → 0,08 % |

## Результаты (машинные отчёты)
`h2anim_run.py` код 0 (`reports/h2anim-run.json`); `clip_manifest.py build` / `check` — `MANIFEST_CHECK PASS clips 39
production 32`, BEO-* `measured`; `clip_review_sheet.py --check` PASS.

| Клип | validate | contact | скольжение стоп, % H | меч в кулаке, ° | запястье R, ° | локоть R, ° | колено min, ° | меч/щит ∩ тело | щит к предплечью, см |
|---|---|---|---|---|---|---|---|---|---|
| Idle (60 к.) | pass | pass | 0,07 | 2,5 (волна образца) | 0 | 126–128 | 164,5 | 0 / 0 | 0,0 |
| LungeAttack (14 к.) | pass | pass (WARN skin_stretch скрытый, щиколотка) | 0,20 | 0,0 | 23,9 | 112–131 | 158,5 | 0 / 0 | 0,0 |
| HitReact (10 к.) | pass | pass | 0,08 | 8,0 (ключ образца) | 0 | 120–128 | 163,0 | 0 / 0 | 0,0 |
| DeathSettle (21 к.) | pass | pass (WARN skin_stretch скрытый: щиколотки, сгиб правого локтя) | 0,28 | 0,0 | 28,4 | 128–152,5 | 154,0 | 0 / 0 | 0,0 |

`reports/rider-gap.json` — PASS: рукоять щита (части 2+18) к левой кисти (часть 10) 0,00 мм / проникновение 0,12 мм в
rest и во всех 4 клипах; меч (части 7, 17) к кулаку ≤ 0,25 мм. Пара щит–предплечье (часть 12) — постоянные 5,6 мм в rest
и клипах (щит держит кисть, этап 3), в отчёт не включена.

Крупные планы `preview/closeups-blender/` (`clip_closeups.py`, камеры — `*-closeups.json`): Idle 4 + пара шва
f60/f00 (front, q34: 0 пикселей > 12), LungeAttack 12 (к.4, 7, 9, 10; кисть, плечо сзади, щит), HitReact 4,
DeathSettle 12 (к.13, 16, 17, 21; кисть, сгиб локтя `-f21-q34r-b`, щит, плечо сзади; после переавторинга — те же
камеры `--shots-from` прежнего отчёта плюс `-f21-q34r-b` и `-f21-right`).

## Что видно на кадрах (осмотр исполнителя)
- Щит ни в одном клипе не входит в корпус и ноги; мантия цела, рваных краёв на самой мантии нет; меч в LungeAttack и
  DeathSettle жёстко в кулаке, гарда на кулаке — дыры в кулаке нет (`-f21-front`, `-f13-q34r`); сгиб правого локтя на
  152° без разрыва (`-f21-q34r-b`); шов Idle невидим.
- Верх правого рукава под краем мантии сзади: при выносе руки виден открытый неровный срез рукава — LungeAttack к.4
  (`-f04-q34b`), DeathSettle (`-f17-q34b`). По разбору оркестратора не чинится на этапе 6 и не вносится в
  known-limits: его оценивает приёмщик клипов 7a.2 (маршрут позднего фикса, animation-vfx-sfx.md §10.5).

## Пределы фигуры
Один список для приёмщика: `evidence/acceptance-anim-prompts/known-limits.md`.

## Отступления от хендбука
- Движение — паттерн библиотеки (Angel r2 ← King Arthur), а не видео-референсы SYNTX HANDBOOK §4.5 (решение ДС-6).

## Отложено на этап 7
- 7a.1: `h2anim_ue.py skeleton | import | measure` (под `ue_lock.py`), затем `clip_manifest.py build` (`technically_imported`).
- 7a.2: `h2anim_ue.py frames --light-pinned …` по клипу, `--closeup` у LungeAttack, `sheet`; каталог цикла
  `python tools/tripo-pipeline/ue7a/prep_acceptance.py --asset-dir art/pipeline-candidates/ASSET-BEOWULF-001 --key Beowulf
  --run art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2anim --spec art/pipeline-candidates/ASSET-BEOWULF-001/build-profiles/beowulf-h2anim.json
  --date <дата> --cycle r1` (заготовки `evidence/acceptance-anim-prompts/<Clip>/acceptor-prompt.md` и `known-limits.md`
  проверены `fill_prompt`: плейсхолдеры заполняются, якорь заметки о носителе есть).
- 7b: CUE-011/013 `sequence_by_fighter.Beowulf` (Р7-6), `de010.py apply --only Beowulf` (notify Contact к.7),
  `S08AudioBank` `HitType` BLADE (Р7-5).

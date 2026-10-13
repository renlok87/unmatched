# ASSET-ANCIENT-LESHEN-001 — этап 6 (анимация, VFX, SFX), headless, 2026-10-14

Пилот скилла 3d-model-pipeline. Делегирование пользователя: 2026-10-06 «Не знаю. Делай сам, меня это не касается. Все
решения принимай»; 2026-10-13 «Сгенерировать модели можно все Но сначала чтобы полностью обкатать скилл и итерационно его
улучшить, можно это сделать на небольшой выборке». Объём прогона — всё, что идёт без Unreal; UE-шаги (§6.4) отложены на
этап 7a.

## Вход
- Цель: `../20261014-h2-bake-r2/export/SK_AncientLeshen_H2.fbx` (sha256 `d1ea65ec…51b5`) и `SM_AncientLeshen_H2_Base.fbx`;
  модель принята парой 8.1 (этап 4 r2, `../evidence/acceptance/20261014-r2/final.json`).
- Спека: `../build-profiles/ancient-leshen-h2anim.json` — копия образца без оружия (Harpy, `references/animation-vfx-sfx.md`
  §6.2) с заменой цели, мешей, оружия (`null`), `run_dir`, `ue` и авторского слоя. Idle 56 к., контакт LungeAttack к.8
  (поля заявки).
- Замер rest (оси арматуры, см; блок `rest_measured` спеки): плечи z 44, запястья z 28,5, когти до z 13,1; голова 48,8,
  рога до 73,6; таз 25; цепь ноги 16,72 при расстоянии таз–лодыжка 16,70 (почти прямая); верх подставки z 6,0, радиус 14,3;
  рост H 67,93 см.
- Видео-референсов SYNTX нет (оркестратор 2026-10-14: «No SYNTX spend … author from library patterns»), трат и строк
  журнала нет. Образцы библиотеки D-11 (поле `reference_kind` клипов, `CLIP_PATTERNS` заявки):

| Клип | Образец | Почему |
|---|---|---|
| Idle | Medusa Idle + тяжёлое дыхание Merlin | та же длина 56 к. (IDLE_SECONDS заявки), дыхание без опоры на оружие; древний дух дышит медленно и глубоко, как Merlin |
| LungeAttack | Merlin LungeAttack + удар когтями Harpy | контакт к.8 = выброс Merlin (длинная подготовка ~40 %, короткий бросок руки к цели — атака range); ударная часть без оружия — когти, как у Harpy |
| HitReact | Medusa HitReact | удар спереди: корпус и голова назад, руки взлетают (у Harpy — крылья, у Merlin — посох-опора) |
| DeathSettle | Medusa DeathSettle | поклон корпусом без падения на колени (ВР-14), руки повисают; опоры на оружие нет |

## Итерации (лёгкий режим, ≤ 3)
| Прогон | Что | Итог |
|---|---|---|
| r1 | спека с `hips_loc` (опускание таза 0,25–0,5 см по уроку Angel) | validate и контакты PASS у всех 4, но `clip_author` FAIL у всех: readback `pose_heads_max_diff_cm` 0,10 / 0,40 / 0,22 / 0,61 = ровно `hips_loc`. Причина: голова `hips` лежит на оси `root` (0; 0; 25), импорт FBX Blender ставит `root` хвост в голову `hips` и делает `hips` connected — location молча выбрасывается. h2anim_run код 1. По листам: HitReact — руки взлетают слишком высоко, DeathSettle — череп опрокинут за вертикаль |
| r2 | `hips_loc` убран (ствол — только поворот hips ≤ 6°); HitReact: руки ±7°/−6° (было ±10°/−12°); DeathSettle: голова 11–14° (было 16–20°) | все 4: author OK (readback ≤ 2e-5 см), validate PASS, контакты PASS; h2anim_run код 0 |
| r3 | только текст `design`/`rest_measured` спеки (без сдвига таза) — тот же прогон для актуального sha спеки | как r2 |

## Результат (`reports/h2anim-run.json`, код 0)
| Клип | Кадры | validate | контакты | пик сдвига, % H | WARN |
|---|---|---|---|---|---|
| Idle | 56 (2,333 с, петля) | PASS | PASS (loop_seam PASS) | 2,5 | — |
| LungeAttack | 14, Contact к.8 | PASS | PASS | 54,5 | `skin_stretch`: 1 ребро arm_upper.R к.4–5 (×3,9; FAIL-рёбер нет) — внутренний сгиб локтя |
| HitReact | 10 | PASS | PASS | 19,9 | — |
| DeathSettle | 21 | PASS | PASS | 54,7 | — |

`limb_body` 0 пар во всех клипах (когти и вороны не входят в ствол), `below_base_top` в пределах rest-заглубления корней
(0,55 % H), `below_ground` 0. FBX sha256 — `reports/author-<Clip>.json#fbx`.

**Корни.** `foot_slide` здесь пуст (стопа и голень без весов: `foot_vertices` 0), поэтому сдвиг корней измерен отдельно —
`reports/roots-planted.json`: внешние корни (r > 6 см, z < 8 см) ≤ 0,334 см = 0,49 % H (DeathSettle к.17), в остальных
клипах ≤ 0,17 см; больше (0,62 см) сдвигается только скрытая крышка `roots_floor` под стволом. Корни стоят.

**IK.** `ik_unreached_frames` в `author-Idle.json` и `author-DeathSettle.json` — прямая цепь ног внутри ствола: крен hips
поднимает голову бедра на ≤ 0,1 см, а цепь длиннее расстояния до лодыжки всего на 0,02 см. Голень и стопа весов не имеют,
поэтому на меше это не видно (не скольжение).

Листы `preview/AncientLeshen-<Clip>-blender-sheet.jpg` и крупные планы Workbench 1100 px
`preview/closeups-blender/` осмотрены: когти на пике подготовки (к.5) ниже и снаружи рогов, без пересечений; контакт к.8
читается с front, q34 и сбоку (рука почти прямая, когти раскрыты к цели); сгиб локтя к.4 без разрыва; поворот головы Idle
не задевает ворону на левом плече; финал DeathSettle — поклон ствола, рога вперёд, корни на подставке. Ворона на правом
предплечье при поднятой руке (к.3–5) висит вниз головой — следствие жёсткой посадки этапа 3, пересечений нет.

## Регистрация этапа 6 (`references/new-character-registration.md` §4)
- Р6-1: `CHARS["AncientLeshen"] = ("LESH", …)` и `H2ANIM["AncientLeshen"]` — отдельными строками после словарей
  (`tools/tripo-pipeline/anim/clip_manifest.py`; строку Angel не трогали), текст «24 слота = 4 × 6».
- Р6-2: `"AncientLeshen"` в `character.enum` — `docs/art-pipeline/animation-library/clip-manifest.schema.json`.
- Р6-3: `clip_manifest.py build` → `MANIFEST_CHECK PASS clips 31 production 24`; LESH-* в статусе `measured`
  (`technically_imported` — после UE-импорта).
- Р6-4: карточки AN-137…AN-140 (`docs/game-design/visual/06-tasks/anim.csv`, depends_on AN-38) и
  `"AncientLeshen": Hero("AncientLeshen", "LESH", 56.0 / 24.0, …)` в `tools/art/anim/clip_review_sheet.py`;
  `--check` → PASS.

## Слоты VFX и SFX (`references/animation-vfx-sfx.md` §8–§9; заявка `STAGE6_VFX`, `STAGE6_SFX`, `HIT_TYPE`)
- VFX: звезда удара CUE-011 и лечение CUE-012 — работают сразу; вспышка и обод CUE-011 — через MI героя на
  `M_UM_Figure_v2` (этап 7); пепел CUE-013 — MIC растворения `de011.py apply` (этап 7b); FX способности CUE-014 — нет
  (фолбэк «иконка способности в HUD без VFX и звука»), `fx_ability.py` не нужен.
- SFX: `HIT_TYPE` MAGIC (выбор этапа 3 подтверждён: бросок когтей к цели издалека — атака range; банки CLAW — ближний удар
  Harpy) — готовые `CMB-LUNGE-MAGIC` и `CMB-HIT-MAGIC`; смерть — `DTH-TEMPLATE`; способность и VO — нет. Новых рецептов
  нет, `sfx_build.py`/`ue_bank.py` не запускались. `CharacterKey` (подстрока «leshen» → `ANCIENTLESHEN`) и `HitType` →
  `MAGIC` в `S08AudioBank.cpp` — C++ этапа 7 (Р7-5). Прослушивание пользователем не проводилось — принято по
  делегированию с этой пометкой.

## Отложено на этап 7 (нужен UnrealEditor)
1. Под `ue_lock.py` (§6.4): `h2anim_ue.py state | skeleton | import | measure`, `frames` по клипу (LungeAttack ещё
   `--closeup --frames=7,8,10`), `sheet`; затем `clip_manifest.py build` → LESH-* `technically_imported`. Сокет `Weapon` —
   на `hand.R` в профиле UE-импорта (`WEAPON_SOCKET_BONE`).
2. Приёмка клипов kind anim r1 (§10, «Sol 6.1 xhigh»): промпты `../evidence/acceptance-anim-prompts/<Clip>/acceptor-prompt.md`
   и `run-acceptor.ps1`. Скопировать промпт в `../evidence/acceptance-anim/<YYYYMMDD>-r1/<Clip>/acceptor-prompt.md`,
   подставить `{{E}}`, `{{DATE}}`, `{{CYCLE}}` (r1), `{{PREVIOUS_CARD_JSON}}` (null), `{{FRAMES_FILES_JSON}}`, сверить
   sha256 в `accepted_object`; в `<Clip>/frames/` — кадры §10.3 и `preview/closeups-blender/AncientLeshen-<Clip>-*.jpg`;
   запустить, проверить события на сбой песочницы и кириллицу, `codex:pending` → `codex:<thread_id>`,
   `validate_card.py --print-verdict --check-files`; код 3 — второй приёмщик другим профилем.
3. Notify `Contact` к.8 (`de010.py apply`, Р7-1) и MIC растворения (`de011.py apply`, Р7-2) — шаг 7b.
4. CUE-011/013 `sequence_by_fighter.AncientLeshen` после импорта (Р7-6), `S08AudioBank.cpp` (Р7-5), строки
   `AM_AncientLeshen_*` в `docs/game-design/visual/03-asset-registry.csv`, лист AN-18 K1/K2
   (`clip_review_sheet.py run --packaged --heroes AncientLeshen …`).

# ASSET-ACHILLES-001 — этап 6 (анимация, VFX, SFX), headless, 2026-10-14

Пилот скилла 3d-model-pipeline. Делегирование пользователя: 2026-10-06 «Не знаю. Делай сам, меня это не касается. Все
решения принимай»; 2026-10-13 «Сгенерировать модели можно все Но сначала чтобы полностью обкатать скилл и итерационно его
улучшить, можно это сделать на небольшой выборке». Объём прогона — всё, что идёт без Unreal; UE-шаги (§6.4) отложены на
этап 7a.

## Вход
- Цель: `../20261014-h2-bake-r2/export/SK_Achilles_H2.fbx` (sha256 `e465e85b…10dd`) и `SM_Achilles_H2_Base.fbx`; модель
  принята на этапе 4 r2 — pass 8,8 (`../evidence/acceptance/20261014-r2/card.json`).
- Спека: `../build-profiles/achilles-h2anim.json` — копия образца «древковое или посох» (Merlin, `references/animation-vfx-sfx.md`
  §6.2) с заменой цели, мешей (`SK_Achilles_H2_Body`, `SK_Achilles_H2_Spear`), оружия (`weapon.R`), `run_dir`, `ue` и авторского
  слоя. Idle 60 к., контакт LungeAttack к.7 (поля заявки). Блок `rest_measured` спеки — замер rest.
- Замер rest (оси арматуры, см; `C:/tmp/achilles-anim-s6/rest.json`): хват `weapon.R` (7,16; −9,52; 33,7), копьё
  вертикально, пятка (6,92; −8,39; 5,75) стоит на верху подставки 5,81 внутри круга (r 10,9 из 15), наконечник (7,5; −10,3;
  53,75); правый локоть 97°, левый 143°; щит (вершины 100 % `arm_lower.L` дальше 2,5 см от кости) — центр (3,4; 12,1; 29,4),
  r ≈ 7,6; ноги прямые (цепь 16,83 = таз–лодыжка 16,83, колено 177°); голова `hips` (−0,6; 0,4; 25,0) не на оси `root` —
  `hips` при импорте FBX не connected, `hips_loc` сохраняется (readback ≤ 2e-5 см); рост H 49,32 см.
- Видео-референсов SYNTX нет (оркестратор 2026-10-14: «No SYNTX spend … author from library patterns»), трат и строк
  журнала нет. Образцы библиотеки D-11 (поле `reference_kind` клипов, `CLIP_PATTERNS` заявки):

| Клип | Образец | Почему |
|---|---|---|
| Idle | King Arthur Idle + Merlin Idle (hand_pin) | ближний бой, та же длина 60 к.; копьё — опора на подставке, как посох Merlin: кисть держится на месте, копьё качается вокруг пятки на ±1° с переносом веса |
| LungeAttack | Merlin LungeAttack (выброс древка) с контактом к.7 (King Arthur) | древковое оружие в правой руке: длинная подготовка (к.0–4), короткий выброс к цели; кадр контакта — из заявки (ближний бой, как Arthur) |
| HitReact | King Arthur HitReact + Merlin HitReact (hand_pin) | отдача корпуса назад; копьё остаётся пяткой на подставке |
| DeathSettle | King Arthur DeathSettle + Merlin DeathSettle (hand_pin) | наклон к оружию и опора почти прямой правой рукой (Arthur), пятка копья держится на подставке (посох Merlin); без падения на колени (ВР-14) |

## Метод (что нового против образцов)
- Копьё всё время жёстко в кулаке: кость `weapon.R` без ключей во всех клипах. В LungeAttack направление копья задаёт
  поворот кисти (`aim hand.R`, from = ось копья в rest, from2 = ось кисти), рука — `aim arm_upper.R/arm_lower.R` полными
  базисами (from2/to2 — ось сгиба локтя, без скрутки предплечья). Позы руки на ключах к.2/4/7/9/12 решены перебором
  (`C:/tmp/achilles-anim-s6/solve_lunge.py`): цель хвата и направление копья → плечо и предплечье (локоть 92–136°, излом
  запястья ≤ 26°). Пятка копья в выпаде уходит назад-наружу (y −18,7) мимо плаща (плащ справа до y −11,6).
- Idle, HitReact, DeathSettle — hand_pin: кисть держит rest-позицию + `hand_offset` и поворот `hand_world`; наклон копья
  вокруг пятки посчитан как B + R(w0 − B) − w0 (B — пятка). Явный полюс локтя `pole` = rest-полюс в осях арматуры
  (−0,756; −0,009; −0,655): без него hand_pin берёт rest-полюс в осях spine и при сжатии цепи на 3 % переключает его на
  «назад» — плоскость локтя проворачивалась относительно неподвижной кисти (излом запястья 26° в Idle, 45° в DeathSettle).
- DeathSettle: наклон копья вокруг пятки (12,5° на азимут −35°) и наклон корпуса подобраны IK-репликой
  (`C:/tmp/achilles-anim-s6/ik_death.py`, совпадает с Blender до 0,1°): опорная рука почти прямая (локоть 127–129° на
  к.14–21, урок Angel DeathSettle r1 — согнутый локоть), излом запястья ≤ 19°.
- Шаблон черновика Medusa — только в Idle (spine/head 0,8) и HitReact (0,6); в LungeAttack и DeathSettle шаблона нет (точные
  позиции плеча для решения руки).
- Ноги прямые → любое смещение таза с опусканием 0,1–0,55 см (урок Angel); колено ≥ 149°, подъём бедра ≤ 16°.

## Итерации
| Прогон | Что | Итог |
|---|---|---|
| r1 | спека по образцам | все 4: author OK, validate PASS, контакты PASS. Своя проверка: излом правого запястья Idle 26°, DeathSettle 45° (полюс локтя hand_pin в осях spine); в DeathSettle копьё вбок на 16°, `limb_body_L` WARN 137 пар (левая рука в кирасе) |
| r2 | явный `pole` = rest-полюс в hand_pin (Idle, HitReact, DeathSettle) | Idle 2,9°, HitReact 8,2°; DeathSettle 40,6° — пробы полюса и поворота кулака вокруг древка не помогли (полюс ≠ rest ломает кадр 0: `clip_boundary_rest` FAIL) |
| r3 | DeathSettle: наклон копья вперёд-вправо 12,5°, поклон 22° / крен 8° (IK-реплика); левая рука опускается наружу; LungeAttack к.9/к.12 перерешены (локоть ≤ 136°, локоть к.12 ≥ 92°) | DeathSettle запястье 18,6°, локоть 127–129°, `limb_body_L` WARN ушёл; все 4 PASS |
| final | только тексты `design`/`hand_note` спеки — тот же прогон для актуального sha спеки | как r3 |

## Результат (`reports/h2anim-run.json`, код 0)
| Клип | Кадры | validate | контакты | пик сдвига, % H | WARN | FBX sha256 |
|---|---|---|---|---|---|---|
| Idle | 60 (2,5 с, петля) | PASS | PASS (loop_seam PASS) | 2,5 | — | `adb9471a…537f` |
| LungeAttack | 14, Contact к.7 | PASS | PASS | 17,3 | `limb_body_R` до 7 пар с кирасой к.11–13 (мягкое); `skin_stretch` только скрытые рёбра (подол плаща у щиколоток, щиколотки) | `a78a6ad4…7cc3` |
| HitReact | 10 | PASS | PASS | 19,6 | `skin_stretch` скрытые (щиколотки, подол) | `4a7e134a…524e` |
| DeathSettle | 21 | PASS | PASS | 30,3 | `skin_stretch` скрытые (щиколотки, подол) | `d2294ca0…7bf9` |

Скольжение стоп ≤ 0,21 % H (порог 0,5 %); `below_base_top` и `hem_below_base_top` — на уровне rest.

## Своя проверка хвата и щита (`reports/grip-<Clip>.json`, скрипт `C:/tmp/achilles-anim-s6/grip_check.py`, headless по FBX)
| Клип | weapon.R в кулаке | излом правого запястья | локоть R | щит к предплечью | hand.L к предплечью | пятка в подставку (rest 0,06) | копьё/щит ∩ тело |
|---|---|---|---|---|---|---|---|
| Idle | 0,00° | ≤ 2,9° | 91–97° | 0,000 см | 0,00° | ≤ 0,06 см | 0 / 0 |
| LungeAttack | 0,00° | ≤ 26,2° (к.2), к.7 13,1° | 92–132° (к.7 129°) | 0,000 см | 0,00° | ≤ 0,06 см (к.1–13 над подставкой) | 0 / 0 |
| HitReact | 0,00° | ≤ 8,2° | 97–129° | 0,000 см | 0,00° | ≤ 0,07 см | 0 / 0 |
| DeathSettle | 0,00° | ≤ 18,6° | 97–129° (к.14–21 127–129°) | 0,000 см | 0,00° | ≤ 0,10 см | 0 / 0 |

Копьё/щит ∩ тело — BVH-пары: копьё (меш оружия + грани тела с доминирующей `weapon.R`) против корпуса, ног, головы и левой
руки; щит против корпуса, ног, правой руки и копья (стандартный `clip_contact_check` пятку копья не проверяет: её грани
доминируют на `weapon.R`, это не рука и не корпус).

## Осмотр
Листы `preview/Achilles-<Clip>-blender-sheet.jpg` и крупные планы Workbench 1100 px `preview/closeups-blender/` осмотрены.
- LungeAttack: замах (к.4) — копьё наклонено к цели, кисть у правого бока, щит вынесен вперёд; укол (к.7) с бока и q34
  читается: рука почти прямая, наконечник вперёд у плеча цели, корпус развёрнут влево; хват на крупных планах к.7/к.9 цел,
  кулак не проворачивается; строго спереди копьё сокращается (укол виден по руке и корпусу).
- HitReact: отдача назад, голова назад, щит вскинут; пятка копья на месте.
- DeathSettle: финал — поклон, голова повисла, Achilles висит на копье почти прямой рукой, копьё пяткой на подставке; читается
  как оседание, не как HitReact.
- Крышка контакта плаща за голенью (known_issue этапа 4, pose-04 — подъём бедра 35°): в клипах подъём бедра ≤ 16°, голень не
  поднимается, на видах сзади (`-f07-back`, `-f21-back`) тёмного овала нет (Workbench, без текстур — проверить на UE-кадрах).
- Известный предел (модель, не клип): у правой подмышки сзади кромка плаща (вырез по кирасе, стык частей рука/плащ) при выносе
  правой руки вперёд открывается рваной полоской — `-f07-q34b`, `-f21-q34b`, `-f21-right`; в rest закрыта рукой;
  `skin_stretch` видимых рваных рёбер не находит. Виды front/q34 листов и UE её не показывают. Если приёмка снизит D — путь
  этап 5 модели (веса/крышка выреза плаща у правой руки), а не клип.

## Регистрация этапа 6 (`references/new-character-registration.md` §4)
- Р6-1: `CHARS["Achilles"] = ("ACH", "ASSET-ACHILLES-001")` и `H2ANIM["Achilles"]` — отдельными строками после строк
  Ancient Leshen (`tools/tripo-pipeline/anim/clip_manifest.py`; строку Angel не трогали), текст «28 слотов = 4 × 7».
- Р6-2: `"Achilles"` в `character.enum` — `docs/art-pipeline/animation-library/clip-manifest.schema.json`.
- Р6-3: `clip_manifest.py build` → `MANIFEST_CHECK PASS clips 35 production 28`; ACH-* в статусе `measured`
  (`technically_imported` — после UE-импорта).
- Р6-4: карточки AN-141…AN-144 (`docs/game-design/visual/06-tasks/anim.csv`, depends_on AN-37) и
  `"Achilles": Hero("Achilles", "ACH", 2.5, …)` в `tools/art/anim/clip_review_sheet.py`; `--check` → PASS.

## Слоты VFX и SFX (`references/animation-vfx-sfx.md` §8–§9; заявка `STAGE6_VFX`, `STAGE6_SFX`, `HIT_TYPE`)
- VFX: звезда удара CUE-011 и лечение CUE-012 — работают сразу; вспышка и обод CUE-011 — через MI героя на
  `M_UM_Figure_v2` (этап 7); пепел CUE-013 — MIC растворения `de011.py apply` (этап 7b); FX способности CUE-014 — нет
  (фолбэк «иконка способности в HUD без VFX и звука»), `fx_ability.py` не нужен.
- SFX: `HIT_TYPE` BLADE (колющий удар копьём; выбор этапа 3 подтверждён) — готовые `CMB-LUNGE-BLADE` и `CMB-HIT-BLADE`;
  смерть — `DTH-TEMPLATE`; способность и VO — нет. Новых рецептов нет, `sfx_build.py`/`ue_bank.py` не запускались.
  `CharacterKey` (подстрока «achilles» → `ACHILLES`) и `HitType` → `BLADE` в `S08AudioBank.cpp` — C++ этапа 7 (Р7-5).
  Прослушивание пользователем не проводилось — принято по делегированию с этой пометкой.

## Отложено на этап 7 (нужен UnrealEditor)
1. Под `ue_lock.py` (§6.4): `h2anim_ue.py state | skeleton | import | measure`, `frames` по клипу (LungeAttack ещё
   `--closeup --frames=6,7,9`), `sheet`; затем `clip_manifest.py build` → ACH-* `technically_imported`. На UE-кадрах проверить
   крышку контакта плаща за голенью (pose-04 этапа 4) и бронзу (F120).
2. Приёмка клипов kind anim r1 (§10, «Sol 6.1 xhigh»): промпты `../evidence/acceptance-anim-prompts/<Clip>/acceptor-prompt.md`
   и `run-acceptor.ps1`. Скопировать промпт в `../evidence/acceptance-anim/<YYYYMMDD>-r1/<Clip>/acceptor-prompt.md`,
   подставить `{{E}}`, `{{DATE}}`, `{{CYCLE}}` (r1), `{{PREVIOUS_CARD_JSON}}` (null), `{{FRAMES_FILES_JSON}}`, сверить sha256
   в `accepted_object`; в `<Clip>/frames/` — кадры §10.3 и `preview/closeups-blender/Achilles-<Clip>-*.jpg`; запустить,
   проверить события на сбой песочницы и кириллицу, `codex:pending` → `codex:<thread_id>`, `validate_card.py --print-verdict
   --check-files`; код 3 — второй приёмщик другим профилем.
3. Notify `Contact` к.7 (`de010.py apply`, Р7-1) и MIC растворения (`de011.py apply`, Р7-2) — шаг 7b.
4. CUE-011/013 `sequence_by_fighter.Achilles` после импорта (Р7-6), `S08AudioBank.cpp` (Р7-5), строки `AM_Achilles_*` в
   `docs/game-design/visual/03-asset-registry.csv`, лист AN-18 K1/K2 (`clip_review_sheet.py run --packaged --heroes Achilles …`).

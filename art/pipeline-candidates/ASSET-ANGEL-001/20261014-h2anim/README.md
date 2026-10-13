# ASSET-ANGEL-001 — этап 6 (анимация, VFX, SFX), headless, 2026-10-14

Пилот скилла 3d-model-pipeline. Делегирование пользователя: 2026-10-06 «Не знаю. Делай сам, меня это не касается. Все
решения принимай»; 2026-10-13 «начинай делать все остальные параллельно согласно скиллу». Объём этого прогона — всё,
что идёт без Unreal; UE-шаги отложены на этап 7 (оркестратор собирает UE-работу трёх героев пилота в одно окно).

## Вход
- Цель: `../20261013-h2-bake/export/SK_Angel_H2.fbx` (sha256 `cf22e78f…d7f5`) и `SM_Angel_H2_Base.fbx`; приёмка
  модели этапа 4 r1 — pass 8,8 (`../evidence/acceptance/20261013-r1/card.json`).
- Спека: `../build-profiles/angel-h2anim.json` (sha256 `b7ab2708…b293`), копия образца King Arthur (меч в правой,
  `references/animation-vfx-sfx.md` §6.2) с заменой цели, мешей, оружия, `run_dir`, `ue` и авторского слоя.
- Видео-референсы SYNTX **не делались**: решение оркестратора 2026-10-14 («skip the SYNTX video references for Angel
  (no spend, no art/animation-refs writes)» — лимит визуала SYNTX 54 токена, потрачено 6, не покрывает даже трёх
  героев пилота). Движение — по образцам библиотеки D-11: клипы меча King Arthur (`king-arthur-h2anim.json`, его
  видео-референсы `art/animation-refs/ASSET-KING-ARTHUR-001/ARTH-*`), поле `reference` клипов указывает туда.
  Трат SYNTX нет, строк журнала нет.

## Итерации (лёгкий режим, ≤ 3)
| Прогон | Что | Итог |
|---|---|---|
| r1 | спека из образца Arthur | Idle, LungeAttack, HitReact PASS; DeathSettle — `foot_slide_L` FAIL 2,2 % роста (к.15): ноги Angel в rest прямые (таз–лодыжка 21,8 см = l1 + l2), доворот таза к.12–21 уводил левую лодыжку за досягаемость IK; LungeAttack — IK правой руки не доставал до цели замаха Arthur (дефицит 1,6 см, кисть в 5–7 см от цели, к.1–5); HitReact на листе почти не читался |
| r2 | `hips_loc` z −0,4 см на к.12–21 DeathSettle (−0,1 на к.9); якорь замаха (4; −14; −4) → (5; −12; 0) см; отдача HitReact сильнее (корпус −11°, голова −12°, левая рука назад, таз −0,6 см) | все 4 клипа validate PASS, контакты PASS, IK без недоступных кадров |
| проба | DeathSettle: левая рука ближе к корпусу (крен `arm_upper.L` −4…−9°) | `limb_body_L` FAIL (80 пар, рука в широком пальто) — откат к r2. Левая рука в смерти висит наружу: предел формы пальто |

## Результат (`reports/h2anim-run.json`, код 0)
| Клип | Кадры | validate | контакты | пик сдвига, % роста | WARN | FBX sha256 |
|---|---|---|---|---|---|---|
| Idle | 60 (2,5 с, петля) | PASS | PASS | 2,6 | — | `28ff7a6e…16c0` |
| LungeAttack | 14, Contact к.7 | PASS | PASS | 29,6 | — | `64eaf1af…5a08` |
| HitReact | 10 | PASS | PASS | 19,0 | — | `6a66844d…c7a0` |
| DeathSettle | 21 | PASS | PASS (`weapon_tip` к.13–21, стопы ≤ 0,05 %) | 35,5 | `limb_body_L` (1–2 пары левой руки со spine, к.15–20), `skin_stretch` (шея head/spine при падении головы, 0 видимых рваных рёбер) | `26b8d28a…d287` |

Листы: `preview/Angel-<Clip>-blender-sheet.jpg` (осмотрены). Крупные планы Workbench 1100 px ключевых кадров
(осмотрены, разрывов не видно; пятно на боку пальто есть и в rest — шейдинг модели, не клип):
`preview/closeups-blender/`. Подъёма бедра в клипах нет (стопы под IK, таз почти не поднимается), поэтому крышка
контакта брюк (known_issue этапа 4) в Blender-кадрах не открывается; проверить на UE-кадрах этапа 7.

## Регистрация этапа 6 (`references/new-character-registration.md` §4)
- Р6-1: `CHARS["Angel"] = ("ANG", "ASSET-ANGEL-001")`, `H2ANIM["Angel"]`, текст «20 слотов = 4 × 5» —
  `tools/tripo-pipeline/anim/clip_manifest.py`.
- Р6-2: `"Angel"` в `character.enum` — `docs/art-pipeline/animation-library/clip-manifest.schema.json`.
- Р6-3: `clip_manifest.py build` → `MANIFEST_CHECK PASS clips 27 production 20`; ANG-* в статусе `measured`
  (`technically_imported` — только после UE-импорта). Поле `skeleton.version` всех production-слотов обновилось до
  текущей ревизии контракта — так пишет `build`.
- Р6-4: карточки AN-133…AN-136 в `docs/game-design/visual/06-tasks/anim.csv`; `"Angel": Hero("Angel", "ANG", 2.5,
  …)` в `tools/art/anim/clip_review_sheet.py`; `--check` → PASS (после правки самотеста оркестратором: `_synthetic`
  падал StopIteration на любом новом герое).

## Слоты VFX и SFX (`references/animation-vfx-sfx.md` §8–§9; заявка `STAGE6_SLOTS`, `HIT_TYPE`)
- VFX: звезда удара CUE-011 и лечение CUE-012 — работают сразу; вспышка и обод CUE-011 — через MI героя на
  `M_UM_Figure_v2` (этап 7); пепел CUE-013 — MIC растворения `de011.py apply` (этап 7, строка Р7-1/Р7-2); FX
  способности CUE-014 — нет (фолбэк «иконка способности в HUD без VFX и звука»), `fx_ability.py` не нужен.
- SFX: `HIT_TYPE` BLADE — готовые банки `CMB-HIT-BLADE` и `CMB-LUNGE-BLADE`; смерть — `DTH-TEMPLATE` (своего
  `DTH-ANGEL` нет); способность и VO — нет. Новых аудиофайлов и рецептов нет, `sfx_build.py`/`ue_bank.py` не
  запускались. `CharacterKey` → `ANGEL` и `HitType` → `BLADE` в `S08AudioBank.cpp` — C++ этапа 7 (Р7-5; подстрока
  «angel» не пересекается с arthur/merlin/medusa/harp). Прослушивание пользователем не проводилось — принято по
  делегированию с этой пометкой.

## Отложено на этап 7 (нужен UnrealEditor)
1. `h2anim_ue.py state | skeleton | import | measure | frames` (по клипу, LungeAttack ещё `--closeup` вокруг к.7) и
   `sheet` под `ue_lock.py` (§6.4), затем `clip_manifest.py build` → ANG-* `technically_imported`.
2. Приёмка клипов kind anim r1 (§10, приёмщик «Sol 6.1 xhigh») — по готовым промптам
   `../evidence/acceptance-anim-prompts/<Clip>/acceptor-prompt.md` и `run-acceptor.ps1`: скопировать промпт в
   `../evidence/acceptance-anim/<YYYYMMDD>-r1/<Clip>/acceptor-prompt.md`, подставить `{{E}}`, `{{DATE}}`,
   `{{CYCLE}}` (r1), `{{PREVIOUS_CARD_JSON}}` (null), `{{FRAMES_FILES_JSON}}`, сверить sha256 в `accepted_object`,
   кадры §10.3 положить в `<Clip>/frames/`, запустить, проверить события на сбой песочницы и кириллицу (кракозябры —
   сбой окружения, не попытка), `codex:pending` → `codex:<thread_id>`, `validate_card.py --print-verdict
   --check-files`; код 3 — второй приёмщик (`acceptor-prompt-2.md`, другой профиль).
3. Notify `Contact` к.7 (`de010.py apply`, строка Р7-1) и MIC растворения (`de011.py apply`, Р7-2) — шаг 7b.
4. CUE-011/013 `sequence_by_fighter.Angel` после импорта (Р7-6), `S08AudioBank.cpp` (Р7-5), строки
   `AM_Angel_*` в `docs/game-design/visual/03-asset-registry.csv`, лист AN-18 K1/K2 (`clip_review_sheet.py run
   --packaged --heroes Angel …`).

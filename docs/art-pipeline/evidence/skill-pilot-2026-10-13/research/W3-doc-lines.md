# Волна 3: строки для документов скилла из отчётов исполнителей волн 1–2

Собрано оркестратором из отчётов пакетов. Каждая строка — что вписать и куда. Коммиты — в скобках.

## W1-a · инфраструктура (70905fa2)
- `credits-ledger.json`: `limits.*.until: null` поддерживается кодом (окно открыто); саму правку данных решает
  пользователь (RA-04 / RC-01). SKILL.md:19, 66, 80, 157, 384, 504; `tripo3d-stages.md`:28, 41, 62, 67;
  `concept-sheet.md`:569 — «лимит и срок из журнала (решение 2026-10-13), граница — баланс Studio».
- `PYTHONUTF8=1` больше не нужен: UTF-8 в точках входа h2anim_run, h2anim_ue, tripo_pipeline, base_seethrough, ledger,
  ue_hero_lookdev, ue_lock, cue_contract, render_fingerprint (+ de010, de011, clip_manifest, clip_review_sheet,
  run_h2_bake, rig_deform_probe, clip_contact_check).
- `ue_lock`: heartbeat — шаг дольше 25 мин не перехватывается; устаревшей блокировка становится, когда её процесс умер.
- Этапы 3/6/7: перед коммитом `pytest tools/tripo-pipeline/tests`, `tools/art/visual/tests`,
  `tools/tripo-pipeline/blender/h2_bake/tests`, `tools/art/acceptance` зелёные; допустимы только 3 xfail (F91/RA-16).

## W1-b · анимация и регистрация (76168867)
- `new-character-registration.md` §5.1 и чек-лист 7b: `de010.py apply --only <Key>` и `de011.py apply --only <Key>`,
  сначала `--dry-run`. Мастер пересобирается только при смене графа (`tools/art/de010/master-builds.json`). Базовая
  линия `validate_registry` — до de010 (RA-15).
- AN-18 (Д-3): `clip_review_sheet.py run --packaged --heroes <Key> --fixture <Key>:marmoreal=…,sarpedon=…` (несколько
  новых героев одним вызовом, F159); `sheet --heroes <Key>`; отказ карточки — переснять кадры; `--k1-from <dir>` —
  K1 объединения один раз на пачку (RC-09).
- Р6-1 и `animation-vfx-sfx.md` §10 (доработка клипа): строка `H2ANIM_CLIP["<Character>", "<Clip>"] = "…-h2anim-rN.json"`,
  затем `clip_manifest.py build`; `check` называет героя при битой регистрации (RB-07).
- `ue-import-package.md` §6: после любой переупаковки запуски AN-18 переснимаются сами (штамп сборки), `--force` не нужен.

## W1-c · приёмка (f14ffced; probes total — W1-d)
- `acceptance-and-blender.md` §5.3: «|dHue| > 15° — только у хроматических медиан (sat ≥ 0,15); оттенок серого — шум;
  поле `hue_checked`».
- §4, G-NAMES (5): «рост — верх `SK_<Key>_H2_Body` без оружия = `FIGURE_HEIGHT_M` ±1 %; деталь тела выше головы —
  `FIGURE_BOUNDS_TOP_M` ±1 %».
- §8.1 п.5–6: «`--check-files` пересчитывает G-TOPO/G-UV/G-TEX/G-RIG/G-NAMES и всегда читает `frames.json` и
  `tone.json`; расхождение гейта — код 1, тот же один повтор; ручная сверка п.6 — только для WARN „пересчитан не
  целиком“»; флаг `--asset-card`.
- §12.3: добавить `test_rules_pilot.py`.
- HANDBOOK §4.4: однострочник тона → `python tools/art/acceptance/_tone.py <run look-dev>` (код 0 — тон сдаётся).

## W1-d · h2_bake (ad9b2b8c; интеграция проб — следующий коммит)
- HANDBOOK §4.1: «Новый каталог — да, пересчёт — с первой изменённой стадии: `--reuse-from <прежний прогон>`, план в
  `work/reuse-plan.json`. Изменился код — `--reuse-allow-code-drift`, и тогда полный повтор детерминизма. Прогон старше
  0.7.0 даёт максимум `prepare…textures`.»
- HANDBOOK §4.2: `profile_version` (1 — Medusa и пилот, 2 — новый ассет; v2 требует `uv.density_reference_part` (body),
  `textures.team_mask.base_band.part` (base), `preview.frame` с `side`).
- HANDBOOK §4.3: таблица допусков `--compare-with` (PNG `max_abs_diff ≤ 2` на ≤ 0,01 % пикселей; JSON точно или с
  `<run>`; рендерные отчёты — только `passed`; список исключений); «код 1 = стоп; полный повтор — один раз на фигуру, на
  прогоне для UE; с `--reuse-from` — только пересчитанные стадии; каталог повтора удалить сразу после отчёта».
- HANDBOOK §4.4: «`ld_fbx` публикует FBX только при PASS; look-dev нового героя без `frame` — отказ; `--compare-with`
  работает в lookdev и teamaccent».
- SKILL этап 3: три ключа v2 явно; `--compare-with` код 1 — стоп. Этап 5: «r<N+1> = новый профиль + `--reuse-from`
  прежнего прогона; повтор только пересчитанных стадий, полный — один раз на прогоне для UE». Строку §7.1 «всегда новый
  run и профиль» сохранить.

## W1-e · пробы рига и контакт (00f358c7)
- HANDBOOK §4.3, стадия `probes`: «7/7» → «`probes.passed` (n/N)»; расширенные пробы блокируют только
  `profile_version ≥ 2`; фигура без голеней/стоп — `rig.probe_skip` (Leshen).
- HANDBOOK §2.10/§7.4: снять «F59 не исправлено» для оружия (нормировка по телу без оружия).
- HANDBOOK §2.6/§4.2 и `animation-vfx-sfx.md` §6.2–6.3: оружие из нескольких частей и щит — `weapon.extra_parts` в спеке
  h2anim (кость или `{"bone","islands"}`); WARN `foot_slide` «не измерено» при отсутствии стоп — проверить опору отдельно.
- `acceptance-and-blender.md` G-RIG: «probes n/N».
- Предел разгибания скина (класс F122) пробами не меряется.

## W2-b · UE-инструменты (172fd4f1)
- `ue-import-package.md` §3–§4: «Подстройка MI/LUT — `ue_hero_lookdev.py apply-mi --config … --out … --tag …
  [--profile <rev>] [--dry-run]`. Переимпорт §4.4 — только при смене FBX, текстур (кроме LUT) или структуры (apply-mi
  откажет с причиной). После доработки клипов обновить `verify.clips_reference` на последний `ue-measure-clips.json`»
  (у пилота было устаревшим — fabf5215).
- `animation-vfx-sfx.md` §6.4: «После доработки модели — `h2anim_ue.py skeleton <spec>`: меш превью переимпортируется по
  sha, `--refresh-preview` принудительно; `frames`/`measure` отказывают на устаревшем меше; подставка по умолчанию
  `SM_<Hero>_H2LD_Base` (`--no-base` без неё); камера отходит для фигур выше ~59 uu».
- HANDBOOK §0.2/§4.6: «`review`/`frames` сами выключают троттлинг фонового редактора; несошедшийся прогрев — exit 3
  (not_settled), `--allow-unsettled` только для диагностики; вердикт яркости с полосой ±4 %: MI по зоне в „noise band“
  не правят».

## Оркестратор
- de010/de011 пересохраняли MVP — в 7b откатывать поимённо, если не `--only` (F157, 3528ae0b).
- `.git/index.lock` от приложения Codex: lock старше 2 мин и нет живого git — удалить (F82, RC-21) — в SKILL §8.

## W1-d · интеграция проб (f04ee771 validate_card; h2_bake — вместе с W2-c)
- HANDBOOK §4.3 `probes`: «Расширенные пробы блокируют сборку при `profile_version ≥ 2`; у v1 они идут в отчёт с WARN
  (`extended_warnings`)»; `rig.probe_skip` (Leshen: shin_l_bend, shin_r_bend, foot_l_flex, foot_r_flex) — для обеих версий;
  прежние 7 проб пропускать нельзя.

## W2-a · клей в tools (ee301065)
- `concept-sheet.md` §13.2: стр. 20 → `tools/art/pipeline_batch/rebg.py`; стр. 22 → `check_concept_views.py --side-ortho
  <orthos>/ortho_<SIDE_VIEW>.png` (FAIL `view.facing` при зеркале, порог 0,05; пилот прямо 0,96–0,97, зеркало
  0,56–0,67); стр. 23 → `codex_lane.py --tasks --name --logs [--stop-file] [--grace]` + `make_tasks.py`, `make_1c.py`,
  `sheet_acceptance.py`. Ссылки на `C:/tmp/concept-wave/*` убрать.
- `tripo3d-stages.md`: §6 п.6 → `tripo_log.py`; п.7–10 → `post_h2.py` (рамки по вершинам, F10); §5.2 → `prep_1b.py`,
  `post_1b.py`.
- `acceptance-and-blender.md:1130` → `tools/art/pipeline_batch/finish_second.py`.
- `ue-import-package.md`: §3.1/§3.2 → `tools/tripo-pipeline/ue7a/write_import_profile.py` / `write_review_config.py`
  (шаблон, `--set` для смысловых ключей; сами ловят чужие объекты/верх по отчётам); §4.4 п.2 → `delete_prev.py`; носитель
  F145 → `refresh_carrier.py`; грязный `M_UM_Figure_v2` → `discard_master.py`; приёмка клипов 7a → `prep_acceptance.py`.
- `new-character-registration.md` §5 и §9 → `python tools/art/registration_check.py --heroes <Key>` = PASS в 7b и до
  safe-integrate.
- SKILL «Пакетный режим»: таблица `pipeline_batch/*` и `ue7a/*`, `git_lock.py` перед коммитом (F82),
  `registration_check.py`; этап 6 → `grip_check.py` (`--side`, `--shield-bone`, `--base`).
- Codex-полоса: отдельный `CODEX_HOME` без хуков (`--codex-home`) пробой не проверен (нужен живой Codex).

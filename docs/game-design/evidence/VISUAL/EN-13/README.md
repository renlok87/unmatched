# EN-13 — нарисованный задник Marmoreal по умолчанию (ENV-U16)

**Статус: сделано технически и по делегированию (ВР-60), 2026-10-07, VS-5 шаг E3, ветка `feat/visual-vs5`.** Решение
пользователя 2026-10-04: «Нарисованный задник». Приёмочные packaged `-Bench` и цена вида — EN-15 (одна упаковка
спринта); кадры здесь — live tune editor `-game` (`reference=1`).

## Что сделано

- Профиль `S08ArtBoardProfiles.json` rev 23 (заметка `envU16DefaultNoteRev23`): `marmoreal-original.conceptPaste` —
  `default` on, `mode` paste, `offVariant` p5c, `hide` += `baseFx` (`layoutLights` уже был); в заметке блока статус
  ENV-U16 закрыт, приёмка P5c от 2026-10-01 заменена 2026-10-04. Sarpedon не менялся (JSON-сравнение с HEAD: вне блока
  Marmoreal изменились только `revision` и новая заметка).
- `ResolveMode` не менялся: `offVariant` у Marmoreal даёт тот же откат, что у Sarpedon (ВР-EN.15). Откат:
  `-NoConceptPaste` = `-ConceptPaste=0` → `flag-off`, базовая раскладка (3D P5c с подносом T2b, туман, фон, свет
  раскладки); `-EnvLayoutVariant=p5c` → `variant-off`, то же.
- ARTLOOK: `S08ArtLook::BackdropField` / `BoardLine` и строка доски
  `ARTLOOK board=<profile> backdrop=paste|lit3d|p5c(<reason>)` (ВР-EN.8, ВР-VS5-17). Хук в
  `AS08BoardActor::UpdateDioramaTray` (11 строк), только на map-доске с арт-видом, раз на смену.
- Тесты: `ConceptPaste.Shipped` (Marmoreal ON, paste, offVariant p5c, hide, откаты, поле backdrop обеих карт),
  `ConceptPaste.Mode` (подпись), `ConceptPaste.Actor` (Marmoreal по умолчанию: вклейка, лист, туман и поднос скрыты, свет
  раскладки скрыт, 1 + ≤ 6 точек, `paste(default)`; `-NoConceptPaste`: P5c-пропы, поднос виден, туман, `p5c(flag-off)`),
  `ArtLook.Default` (таблица поля), `ArtLook.Actor` (без map-доски строки нет). Тесты, которые проверяют сам вид P5c
  (`BoardArt.FrameBackdropActor`, шаг 4 `EnvLayout.Actor`), идут под откатом `-NoConceptPaste` (ВР-VS5-20).
- Проверки контракта `ue_concept_material.py --check` и `ue_scene_material.py --check` и их pytest: Marmoreal ON, paste,
  offVariant p5c.

## Приёмка карточки

| п. | критерий | результат |
|---|---|---|
| 1 | трассы | без флагов: `concept-paste mode=on profile=marmoreal-original … reason=default … kind=paste`, `ARTLOOK board=marmoreal-original backdrop=paste(default)`; `-NoConceptPaste`: `mode=off … reason=flag-off`, `backdrop=p5c(flag-off)`; Sarpedon: `envVariant=scene:ok`, `backdrop=lit3d(default)` ([traces.txt](../../ENV-MAPS/env-u16-marmoreal-2026-10-07/default/traces.txt)) |
| 2 | UE-тесты и pytest | `Unmatched.S08.ConceptPaste / EnvLayout / ArtLook / LiveTune / BoardArt / HeroLight / HeroMaterials` — **76/76 Success**, EXIT 0, без предупреждений о пропущенных путях; `pytest tools/art/tests` — **593 passed, 4 skipped**; `tools/s08/hud_contract` — 74 passed; сборки UnmatchedEditor и игры — Succeeded |
| 3 | Read PNG K1 обеих карт без флагов | открыл: [Marmoreal](../../ENV-MAPS/env-u16-marmoreal-2026-10-07/default/marmoreal-K1-default.jpg) — настоящая карта, нарисованная плита с фонарями и сакурой, шесть фигур v2; [Sarpedon](../../ENV-MAPS/env-u16-marmoreal-2026-10-07/default/sarpedon-K1-default.jpg) — lit3d (остров, корабль, водопад), шесть фигур v2; откат [Marmoreal -NoConceptPaste](../../ENV-MAPS/env-u16-marmoreal-2026-10-07/default/marmoreal-K1-NoConceptPaste.jpg) — 3D P5c с подносом |
| 4 | `git diff AGENTS.md` — 2 правки | в «Rollback flags» добавлен `-NoConceptPaste`; абзац «Known gap at 2026-10-04» заменён строкой о закрытии с хэшем коммита (отдельный коммит в ветке; по задаче шага — в ветке worktree, не после интеграции) |

## Решения по делегированию

- **ВР-VS5-17.** Поле `backdrop` пишется отдельной строкой `ARTLOOK board=<profile> backdrop=…` на каждую map-доску:
  общая строка `ARTLOOK` пишется в BeginPlay до профиля доски и одна на прогон. Формат поля — как в ВР-EN.8.
- **ВР-VS5-20.** Тесты вида P5c (рамка и ночной фон, базовая раскладка) проверяют откат `-NoConceptPaste`; комментарии в
  `tools/art/render/render_bench.py` и `tools/s09/run-*-demo.ps1` («Marmoreal frames need -ConceptPaste until ENV-U16»)
  не трогал: это подсказки, не значения по умолчанию, флаг `-ConceptPaste` теперь безвреден (no-op).

## Остатки

- Packaged `-Bench` K1 обеих карт и цена вида (≤ P5c + 0,10 мс) — EN-15.

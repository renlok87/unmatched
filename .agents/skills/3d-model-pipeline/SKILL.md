---
name: 3d-model-pipeline
description: Сквозной пайплайн новой 3D-фигуры Unmatched (герой, помощник, крылатое существо-бипед, проп). Этапы — концепт-лист в Codex, генерация в Tripo3D Studio, сборка H2 в Blender, приёмка с коэффициентом и доработкой, анимация с VFX/SFX и упаковка с подключением в Unreal. Триггеры — «сгенерируй 3D-модель», «новый герой / помощник / существо / проп», «новая фигура», «3D model pipeline», «модель через Tripo», «концепт-лист героя». Статический проп (бочка, фонарь, ящик) — да, до импорта в UE; его размещение в раскладке доски — нет. НЕ для окружения, задников и сцен досок и размещения пропов в EnvLayouts (Marmoreal/Sarpedon — трек ENV-MAPS) и НЕ для разовых правок существующих ассетов.
---

# 3d-model-pipeline

Этот файл — навигация и оркестрация. Детали лежат в `references/` и открываются на своём этапе. Норма производства
героя и пропа — `docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md` (далее HANDBOOK). Он главнее скилла, а скилл его числа
не копирует. Пометка «решение скилла» означает, что источника в репо нет и значение выбрано здесь по делегированию
(`docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md`, далее «ВР-реестр»).

## 1. Когда использовать

- **Да:** новая фигура для игры, от заявки до `/Game/PipelineCandidates/<Key>/` и кадров в packaged-клиенте. Новый
  статический проп (бочка, фонарь, ящик, декор — HANDBOOK §1, строка «Статический пропс») — этим скиллом до импорта в
  UE (ветка `prop`, §3; `references/ue-import-package.md` §8).
  Запуск скилла заявкой пользователя считается согласием на Workflow-агентов приёмки и доработки (§4) и разрешением
  тратить кредиты Tripo и SYNTX в лимите и сроке журнала с записью каждой операции (§7.1, строка «Кредиты»). Лимит и
  срок берутся из `docs/game-design/visual/credits-ledger.json` (`limits.*`; для Tripo — решение 2026-10-13 «На триппо
  нет лимита»), `until: null` = окно открыто, граница — свежий баланс Studio (RA-04; `references/tripo3d-stages.md`
  §1). Отдельно о тратах не спрашивать: такого гейта в §5 нет.
- Сейчас скилл дорабатывается после пилота: «весь ростер героев пока делать не планируется сначала доработка скилла»
  (пользователь, 2026-10-14). Пачку больше пилотной (§11) без слова пользователя не запускать.
- **Нет:** окружение, задник, сцены досок и размещение пропов в `EnvLayouts` — отдельный трек ENV-MAPS (AGENTS.md
  «Board scenes and heroes», HANDBOOK §1 «Окружение/карты»). Не для разовых правок готового ассета: перекраска MI, замена текстуры,
  правка одного клипа. Они идут обычной задачей. Новая смысловая деталь существующей фигуры — это новая заявка.
- Ростер после MVP вне объёма ВР-18 (`docs/game-design/visual/02-visual-design.md` §8.6). Скилл пишет об этом
  предупреждение в поле `NOTES` карточки, но работу не останавливает: запрос пользователя и есть основание для запуска.

## 2. Карта этапов 0–7

| Этап | Что | Исполнитель | Выход | Критерий выхода |
|---|---|---|---|---|
| 0 | Заявка, проверка исполнителей, реестр | запускающий агент | `ASSET_DIR/asset-card.yaml`, `.gitignore` ассета, запись в `docs/art-pipeline/asset-registry.json`, строка карточки в `06-tasks/anim.csv` | все поля карточки заполнены (дефолты §7 разрешены); `validate_registry.py` без ERROR по `ASSET_ID` (по строкам ERROR, не по коду выхода); пробы исполнителей прошли; гейты §5 не сработали |
| 1 | Концепт-лист: 1a дизайн-front → 1b черновая модель Tripo → 1c виды поверх орто | Codex, приёмщик | `art/imagegen/concept-<key>-codex/` | `check_concept_views.py` 0 FAIL и коэффициент листа ≥ 8,0 |
| 2 | Генерация Tripo H2 | запускающий агент (Studio в браузере) или пользователь по чек-листу | `<ASSET_ID>/<YYYYMMDD>-h2-tripo/` + `source-specs/tripo-<task8>-h2.json` (проп — `<YYYYMMDD>-prop-tripo/`, `tripo-<task8>.json`) | чек-лист выхода этапа 2 в `references/tripo3d-stages.md` §9 |
| 3 | Регистрация персонажа → H2 bake → look-dev → TeamAccent (проп — сборка статического пропа) | запускающий агент, headless | `SK_<Key>_H2.fbx`, `SK_<Key>_H2LD.fbx`, текстуры (проп — `<YYYYMMDD>-prop-build/export/SM_<Name>.fbx` + `T_<Name>_{BC,N,ORM}`) | все стадии `run_h2_bake.py` OK, probes `n/N` (`probes.passed`; расширенные пробы блокируют при `profile_version` ≥ 2, ДС-5), чек-лист «Сдача модели» (HANDBOOK §4.4); проп — `reports/candidate-report.json` с `checks_passed: true` и `reports/fbx-readback.json` (HANDBOOK §5) |
| 4 | Приёмка модели (коэффициент) | приёмщик (при неустойчивом pass — второй, другим профилем) | `evidence/acceptance/<YYYYMMDD>-r<N>/card.json` (+ `card-2.json`, `final.json`) + `frames/` (`capture_acceptance_set.py --sheet`, JPEG 1200 px, ДС-8) | вердикт `validate_card.py`: код 0 — по карточке; код 3 — по `final.json` пары |
| 5 | Доработка в Blender | исполнитель доработки «Opus xhigh» (§4; профиль — фактом в заявку, RA-21) | новый профиль и run `…-r<N+1>` с `--reuse-from` прежнего (ДС-7) | чек-лист «Сдача модели» и повторный этап 4; не больше 2 циклов (r1→r2→r3) плюс один поздний фикс (§5 п.4) |
| 6 | Анимация (только headless-авторинг), VFX, SFX | запускающий агент; доработка клипа — «Opus xhigh» | `<ASSET_ID>/<YYYYMMDD>-h2anim/` (4 FBX), заготовки промптов `evidence/acceptance-anim-prompts/<Clip>/acceptor-prompt.md`, звуки и FX по слотам | 4 клипа авторены: `h2anim_run.py` код 0 (validate и contact PASS), `clip_manifest.py build` PASS. Приёмки клипов на этапе 6 нет (ДС-1) |
| 7 | 7a: импорт, look-dev и приёмка 4 клипов (7a.2) в агентском скрытом редакторе (MCP), один герой за раз (ДС-3); 7b: C++, сборка, автотесты, упаковка, кадры в игре — без редактора | запускающий агент; редактор 7a поднимает и закрывает оркестратор; приёмщик клипов | `/Game/PipelineCandidates/<Key>/…`, карточки `evidence/acceptance-anim/<YYYYMMDD>-r<N>/<Clip>/card.json`, правки C++ и конфигов | выход 7a — 4 клипа `pass` (ДС-1); `ue-import-report.json` passed, `registration_check.py` PASS, автотесты S08 PASS, кадры `-Bench` обеих досок осмотрены, реестры — по таблице статусов (`references/new-character-registration.md` §10) |

Порядок 6 → 7a (ДС-1). Приёмке клипа нужен UE-импорт: гейт `G-MANIFEST` требует статус `technically_imported`, а
кадры приёмки — UE-кадры редактора. Поэтому этап 6 только авторит клипы и гоняет валидаторы, а приёмка клипов — шаг
7a.2 после импорта (`references/ue-import-package.md` §4.5). Вход 7.0 — модель `pass` и 4 клипа с PASS валидаторов;
«4 клипа `pass`» — выход 7a. Пилот шёл так же (F43, RA-01).

Черновая модель шага 1b — платная операция Tripo внутри этапа 1 (маршрут «Черновик» в `references/tripo3d-stages.md`).
Старые «приёмка кандидата h31» и «этап 4.5» упразднены. Маршрут h31 и профиль `skeletal-candidate` остались
историей, а не образцом (HANDBOOK §1 «Не использовать как образец»).

## 3. Ветки по анатомии (поле `ANATOMY`)

| Ветка | Этапы | Особенности |
|---|---|---|
| `humanoid` (герой или помощник) | 0–7 | риг `UM_HUMANOID_17_v2`, 17 костей; новый персонаж — это рутинная регистрация (`references/new-character-registration.md`), а не эскалация |
| `winged-biped` (образец — Harpy) | 0–7 | крылья = цепочки `arm_upper → arm_lower → hand` базового скелета, как у Harpy; оружия нет (`WEAPON_BONE: null`), 16 костей (HANDBOOK §2.6, §0.3 п.4); `wing_tip.L/R` — только по решению (стоп §5 п.5); широкий кадр концепта (HANDBOOK §3.1) |
| `prop` | 0, 1, 2, 3, 4, 6?, 7 | Tripo — умная сетка (решение 2026-10-14, `docs/game-design/decisions/2026-10-14-tripo-smart-mesh-props-anim-presets.md`; на пропе ещё не проверена — первый проп её проверяет, multi-view — запасной маршрут, `references/tripo3d-stages.md` §5.3), слоты: front+side у осесимметричного, front+back у асимметричного; этап 3 — путь статического пропса (HANDBOOK §5, §6 «Этап 3 — проп»), регистрации персонажа нет; на этапе 4 `D = null` и `G-RIG = n/a`, съёмка `capture_acceptance_set.py --no-base` работает и на широком пропе (`references/acceptance-and-blender.md` §14); этап 6 только при CUE или звуке, иначе пропуск с записью «нет слотов» в `STAGE6_SLOTS`; этап 7 — статический импорт (HANDBOOK §5 п.7); проп с осевой симметрией может пропустить шаг 1b |
| `non-humanoid` (четвероногое, многоголовое, змеевидное) | **стоп на этапе 0** | гейт §5 п.1: пользователю уходит готовая постановка `<ASSET_DIR>/STOP-RIG-CONTRACT-3.md` по шаблону `references/intake-and-evidence.md` §2. До стопа пишется только `asset-card.yaml` (`ANATOMY: non-humanoid`, анатомия в `NOTES`); запись реестра, строка `anim.csv` и траты — нет. Правила поз четвероногих в справочниках действуют только после принятия rig-contract/3 |

Блок `optional_extensions` в `docs/art-pipeline/rig/rig-contract.json:169-184` (`crown_snakes`, `cloak`, `harpy_wings`)
имеет статус «предложено, не реализовано»: h2_bake и валидаторы этих костей не создают (HANDBOOK §2.6 «только по
решению»). Использовать расширение — стоп §5 п.5. Без новых костей работает база: змеи 100 % на `head`, плащ, капюшон
и юбка — плавные веса `hips`/`leg_upper.L/R`. Новый MatID-класс — тоже стоп §5 п.5.

## 4. Исполнители и как их вызывать

| Роль | Как вызвать | Правила |
|---|---|---|
| Codex (этап 1) | `codex.exe exec` после пробы exec (выбор exe, команда, кодировки — `references/concept-sheet.md` §5.2): exe приложения из `%LOCALAPPDATA%/OpenAI/Codex/bin/<hash>/` — только глобом, хэш и версию не закреплять (F37); флаг `-c 'windows.sandbox="unelevated"'` обязателен (без него песочница при открытом приложении не запускает команд, а код выхода 0). Exec не работает — приложение ChatGPT через управление рабочим столом (concept-sheet §5.3). Приложение пользователя не закрывать; npm-`codex` не работает. Пачка — полосы `codex_lane.py` (§11.3) | Промпт-файл пишет Claude: `docs/game-design/visual/06-tasks/prompts/<ASSET_ID>-concept.codex.md`. Codex пишет только в `art/imagegen/concept-<key>-codex/` и не коммитит |
| Приёмщик «Opus xhigh» (по умолчанию) | Агент Workflow `agent(prompt, {model: 'opus', effort: 'xhigh', schema: <строгая выходная схема своего вида>, label})`, свежий контекст (скрипт и промпт — `references/acceptance-and-blender.md` §8.2–8.3). Схема — `tools/art/acceptance/asset-acceptance-2.output-<kind>.schema.json`, как у Sol: с полной схемой Workflow возвращал строки `"null"` (F6, F102, RA-11). Второй приёмщик Opus — сохранённый workflow `.claude/workflows/second-acceptor.js` (`Workflow({name: "second-acceptor", args: {items, schema}})`), затем `finish_second.py` (там же §8.3). На вход — только кадры, отчёты, концепт и рубрика | Не правит. Его сессия отлична от сессии исполнителя. `session_id` обоих пишутся в карточку |
| Приёмщик «Sol 6.1 xhigh» | Тот же `$exe`, прошедший пробу exec (GUI-путь приёмщику не подходит — нужны `--output-schema` и `-o`). Обязательно: `--ignore-user-config -m gpt-6.1-sol -c 'model_reasoning_effort="xhigh"' -c 'windows.sandbox="unelevated"' -s read-only`, строгая схема своего вида `…output-<kind>.schema.json` (не полная — её строгий режим отвергает), каждый кадр отдельным `-i`, `--` перед `-`; затем `validate_card.py`. Полная команда, отказ схемы и разбор событий — `references/acceptance-and-blender.md` §8.4. Промпт несёт блок чтения кириллицы (OEM, `cmd /c type`) и строку «рубрика — только этот файл» дословно по `references/concept-sheet.md` §11 (RA-03; без них Sol читал рубрику кракозябрами при коде 0 и открывал SKILL.md, F36, F75). Сбой песочницы (код 0, карточка-заглушка) или карточка «СБОЙ ОКРУЖЕНИЯ» — сбой окружения, не попытка: цикл не тратится. Пилот: модель 10–14,5 мин, клип ≈ 5 мин | Только по явному выбору запускающего; второй приёмщик пары «другим профилем» — почти всегда Sol (в пилоте 13 из 16 карточек). Повторная приёмка — тем же профилем |
| Доработка «Opus xhigh» (этапы 5, 6) | Агент Workflow `{model: 'opus', effort: 'xhigh'}` с брифом доработки (модель — `references/acceptance-and-blender.md` §10, клип — `references/animation-vfx-sfx.md` §10.6), работает headless-скриптами. Фактический механизм и effort записываются (RA-21): блок этапа в заявке (`STAGE5[]`, `STAGE6.executor`, §7.2) и `executor_session_id` следующей карточки (субагент — `claude-code:<uuid>/agent:<name>`, F40) | Делает лично, не делегирует, свою работу не принимает |
| Tripo Studio (шаги 1b и 2) | Запускающий агент через Claude in Chrome в своей вкладке; расширение не подключено, а Studio открыта и залогинена в Chrome пользователя — клики Windows-MCP в этой вкладке (`references/tripo3d-stages.md` §2, F9). Разрешение трат — сама заявка пользователя (§1), в лимите и сроке журнала; отдельно не спрашивать. Если клик блокирует классификатор прав сессии (живая проверка 2026-10-09: Real-World Transactions) или пользователь — гейт §5 п.2: пользователь проходит чек-лист `references/tripo3d-stages.md` §8 сам, агент проверяет результат | Цена — с кнопки до клика. Строка журнала — после каждой операции |

Требование заказчика №3 исполняется буквально. Коэффициент ставит «Opus xhigh» или «Sol 6.1 xhigh». Ниже порога
дорабатывает лично «Opus xhigh». Затем повторная приёмка — новым агентом-приёмщиком, а не тем же контекстом.
Запускающий агент не принимает свою работу и не подменяет внешнего исполнителя. В каждый промпт агента Workflow
дословно цитируйте делегирование пользователя и разрешение на траты. Иначе агент примет за границу полномочий
последнее сообщение пользователя.

Профиль исполнителя доработки — факт, а не пометка (RA-21). В пилоте все 13 исполнителей были субагентами
`claude-code:<uuid>/agent:<name>` без записанного effort, а память пользователя велит новые workflow запускать «на
опус high» — против «Opus xhigh» требования №3. Это расхождение скилл не решает. Он требует записать, что запущено
на самом деле: механизм (`workflow` или `subagent`), модель, effort и id сессии (§7.2, блоки этапов).

## 5. Гейты стопа: два класса (ДС-2)

Стопов два класса (ДС-2, `docs/game-design/decisions/2026-10-14-skill-refinement-delegated-decisions.md`).
**Вопрос пользователю** — стоп до ответа: деньги, лимиты и покупки; лицензия и IP; решения вне делегирования
(контракт рига, новая кость или класс); необратимое (удаление чужих данных или ассетов, переписывание истории git).
Это пункты 1–5 и 7. **Разбор оркестратором** — пункт 6: FAIL стадии или инструмента пользователю не задаётся.
Пилот закрыл сам не меньше шести таких FAIL (F12, F45, F80, F91, F124, F149), и буквальный стоп на каждом противоречит
делегированию (RA-02).

1. Анатомия не покрыта контрактом рига (ветка `non-humanoid`, §3): стоп на этапе 0 с постановкой «rig-contract/3».
2. Внешний исполнитель недоступен **после попытки** вызова по §4: Codex или приёмщик не запускается, Studio не
   открывается, браузерный шаг запрещён правами сессии. Пользователь получает пакет «что нажать» по чек-листу.
3. Кредиты: предпроверка перед платной операцией не дала код 0 — Tripo `ledger.py check --service tripo --next-cost
   <цена>` (остатка лимита или свежего баланса меньше цены; окно журнала закрыто — `until` в прошлом, `null` = окно
   открыто; §7.1, строка «Кредиты»), SYNTX `ledger.py check --balance <баланс> --next-cost <цена> --next-kind <вид>`
   (`references/animation-vfx-sfx.md` §6.1); две неудачные генерации подряд.
4. Исчерпаны циклы: концепт — 3, модель — 2, клип — 2. Плюс один **поздний фикс** модели на фигуру (RC-06, правило
   скилла): дефект модели, который вскрыла приёмка клипов уже после pass модели, чинится этапом 5 и новой приёмкой
   модели. Поздний фикс тратит цикл модели, если цикл остался; если циклов нет — один раз сверх лимита (приёмка
   `r4`: схема карточки модели и `validate_card.py` её принимают, не-pass → `escalate_user`;
   `references/acceptance-and-blender.md` §6). Перепринятие клипов с неизменными ключами цикл клипа не тратит
   (маршрут — `references/animation-vfx-sfx.md` §10.5). Второй дефект модели из клипов — стоп.
5. Нужен новый MatID-класс, новая кость, расширение `optional_extensions` (§3) или новый режим generic `h2_bake` —
   мост-цилиндр для оружия без хвата (HANDBOOK §0.3 п.7, §4.2 «Оружие», §4.4). Тонкая деталь (тетива, древко,
   стрелы), которую профиль не сделал читаемой, — не стоп: пункт «не закрыто» и балл F
   (`references/acceptance-and-blender.md` §9.3).
6. **Разбор оркестратором, не вопрос пользователю.** FAIL производственной команды этапов 2, 3, 6 и 7: код 1/3/4/5
   CLI `tripo_pipeline.py`, FAIL стадии `run_h2_bake.py` (в любом режиме), код 1 `--compare-with`, код 1
   `capture_acceptance_set.py`, ошибка `ue-import`/`h2anim_ue.py`, падение редактора. Фигура дальше не идёт, пока
   оркестратор не разберёт причину:
   - баг инструмента — фикс или опция инструмента со старым значением по умолчанию; детерминизм Medusa не меняется
     (`--compare-with`), тесты зелёные; коммит фикса — вместе со строкой документа (§8);
   - строка F в NOTES текущей пачки; при выборе между вариантами — файл решения в `docs/game-design/decisions/`;
   - FAIL при тюнинге профиля (TeamAccent, тон, швы, MI в UE) — итерация, не больше 3, а не стоп.

   Вопросом пользователю FAIL становится, только если исправление попадает в первый класс: деньги, новая кость или
   класс, лицензия, удаление чужих ассетов из целевой папки (HANDBOOK §0.3 п.5). HANDBOOK §0.3 называет такие FAIL
   «вопросом к владельцу» — владелец этого решения по делегированию 2026-10-06 оркестратор (ДС-2).
   Штатные циклы своих этапов — не разбор и не стоп: FAIL автопроверок концепта `check_concept_views.py`
   (перегенерация с `CORRECTION:`, этап 1), FAIL-гейты и баллы приёмки (маршрут вердикта, этапы 4–6 и 7a.2), код 1
   `validate_card.py` (один повтор приёмщика, `references/acceptance-and-blender.md` §8.1 п.5), код 1 `ledger.py
   check` без строки `providerTerms` (записать условия и повторить). Стопом они становятся только по своим пунктам:
   циклы (п.4), приёмщик не дал валидной карточки после повтора (п.2), кредиты (п.3).
7. Шагу 7b нужен закрытый редактор, а открыт **интерактивный** редактор (ДС-3). Признак интерактивного запуска — в
   командной строке нет флагов агентского запуска `-unattended -RenderOffScreen`, он запущен из Epic Launcher или с
   `-LiveCoding`. Любой `UnrealEditor.exe` этого движка с Live Coding блокирует сборку `UnmatchedEditor` во всех
   чекаутах (`docs/unreal/UE-SESSION-DESIGN.md` F9), `UnrealEditor-Cmd` при открытом GUI-редакторе запрещён (HANDBOOK
   §0.1). Пакет пользователю: список шагов 7b и просьба закрыть редактор или разрешить агенту закрыть его (0
   dirty-пакетов). Такой редактор агент сам не закрывает; готовый текст пакета — `references/ue-import-package.md` §1
   п.4. Пользователь UE сам не открывает (2026-10-14: «я ничего сам вручную не открывал и не запускал»): в автономном
   прогоне редактор 7a — агентский, его поднимает и закрывает оркестратор (`references/ue-import-package.md` §1 п.1),
   и гейт не срабатывает.

Пункт 7 — производная норм выше скилла: AGENTS.md «Agent and process lifecycle» («Do not close the user's Unreal
Editor») и HANDBOOK §0.1. Запрос «разрешаете траты?» гейтом не является (§1).

Всё остальное закрывается дефолтами §7 с пометкой в карточке `decided_by: delegated (ВР-реестр 2026-10-06)`.
Вопрос пользователю — это стоп до ответа, а не «записал и пошёл дальше». Разбор оркестратором — не стоп пачки:
остальные фигуры идут дальше.

## 6. Этапы: шаги и выход

**Этап 0 — заявка.**
1. `ANATOMY` по §3 (`non-humanoid` — стоп). `ASSET_DIR`, `asset-card.yaml` по §7.2 (не заданное пользователем — дефолт
   §7.1 с `decided_by`), `.gitignore` ассета (`references/intake-and-evidence.md` §3).
   `ANATOMY` решается **для каждой фигуры** по её описанию (БД `Hero`, карты), а не дефолтом пачки: пакетная заявка
   2026-10-13 записала `humanoid` всем, и пять не-гуманоидов (Ant Queen, Blob, Tarantula, T. Rex, Raptors) и три
   крылатых (Jersey Devil, Mothman, Wingnut) нашлись только перед Tripo. Крылья плюс отдельные руки — стоп §5 п.5.
   `.gitignore` — гейт этапа 0: `git check-ignore -v <ASSET_DIR>/<YYYYMMDD>-draft-tripo/source/x.glb` печатает правило
   ассета (без него сырые GLB по 45–79 МБ попадают в коммит).
2. Запись в `docs/art-pipeline/asset-registry.json`: `status` «предложено», `stage` `planned`; `contentKey` = `CONTENT_KEY`,
   только если ключ есть в `docs/game-design/05-content-matrix.csv`, иначе `null`; `manifest06Row` — `null` без строки в
   `06-asset-manifest.csv`. Запись — по шаблону `references/intake-and-evidence.md` §1.
   Проверка — по строкам ERROR со своим `ASSET_ID`, **не по коду выхода**: на базовой линии 2026-10-09 инструмент
   уже даёт код 1 (1 ERROR `sharedDependencies[UM-MASTERS]` sha256, чужой). Команда (пусто и код 1 у `grep` — норма):
   `python tools/tripo-pipeline/validate_registry.py 2>&1 | grep '^ERROR' | grep -F '<ASSET_ID>'`.
   Чужие ERROR базовой линии (`… | grep '^ERROR'`) — строкой в `NOTES` карточки, не чинить.
3. Строка карточки в `docs/game-design/visual/06-tasks/anim.csv` (`area` `hero` по `07-prompt-templates.md` §0.1; у пропа `prop` — решение скилла; следующий `AN-NN`) →
   `VISUAL_CARD_ID`. Без неё `ledger.py add` откажет («no spend without a card»).
4. Пробный вызов исполнителей §4 — каждый с командой и критерием; не прошёл после повтора — гейт §5 п.2. В пачке
   пробы — один раз на сессию пачки, а не на фигуру (§11; пилот откладывал пробы до первой платной операции).
   - **Codex** — проба именно `exec` (`references/concept-sheet.md` §5.2, шаги 1–3:
     `exec … -c 'windows.sandbox="unelevated"' -s read-only --json "Run exactly one shell command: …"`). Прошла, если в
     событиях есть `command_execution` с `"exit_code":0`; `--version` и «Reply OK» не годятся — они проходят и при
     заблокированном exec или сломанной песочнице. Не прошла — путь через приложение (concept-sheet §5.3).
   - **Приёмщик «Opus xhigh» (Workflow).** Скрипт-проба с тем же вызовом, что у приёмки
     (`references/acceptance-and-blender.md` §8.3), но с крошечной схемой:
     ```js
     export const meta = {name: 'acceptor-probe', description: 'Проба приёмщика, этап 0 3d-model-pipeline'}
     return await agent('Ничего не читай и не меняй. Верни JSON {"ok": true}.', {
       model: 'opus', effort: 'xhigh', label: 'probe-acceptor-<ASSET_ID>',
       schema: {type: 'object', properties: {ok: {type: 'boolean'}}, required: ['ok'], additionalProperties: false},
     })
     ```
     Прошла — вернулся объект `{"ok": true}`. `null` или ошибка — один повтор. Приёмщик «Sol 6.1 xhigh» (только
     если выбран в `ACCEPTOR_PROFILE`) — проба `exec` выше тем же exe с `--ignore-user-config -m gpt-6.1-sol`.
   - **Claude in Chrome** (шаги 1b и 2). Инструменты загрузить одним `ToolSearch`
     (`select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__computer`).
     Критерий 1: `tabs_context_mcp` возвращает подключённый браузер и список вкладок; молчит — сначала
     `list_connected_browsers` и `select_browser` браузера с `onThisComputer: true` (сессия могла быть привязана к
     чужому браузеру, C1 проверки Beowulf), и только потом Windows-MCP. Критерий 2: в своей новой
     вкладке (`tabs_create_mcp`) `navigate` на `https://studio.tripo3d.ai/`, затем `get_page_text` или скриншот —
     открыта Studio под учётной записью пользователя и виден баланс кредитов (записать число в `NOTES`). Чужие
     вкладки не трогать. Расширение не подключено, но Studio открыта и залогинена в Chrome пользователя — клики через
     Windows-MCP в этой вкладке (`references/tripo3d-stages.md` §2, вторая строка; пилот 2026-10-13). Экран входа или
     нет ни того ни другого — гейт §5 п.2 (вход и пароль агент не вводит); тогда шаги 1b и 2 идут по чек-листу
     пользователю (`references/tripo3d-stages.md` §8).
5. Кредиты Tripo (`references/tripo3d-stages.md` §1): один раз на журнал — строка условий
   `python tools/art/visual/ledger.py terms --service Tripo --model "Tripo Studio H3.1" --url https://www.tripo3d.ai/terms`
   (без неё предпроверка Tripo даёт ERROR, ВР-05); затем
   `python tools/art/visual/ledger.py check --service tripo --next-cost <черновик + H2, §7.1> --model "Tripo Studio H3.1"`
   → код 0. На этапе 0 — **без `--balance`**: проверяются только остаток лимита и срок окна журнала (`until: null` —
   окно открыто) и строка условий (`ledger.py check` принимает Tripo-предпроверку без баланса). Свежий баланс Studio
   обязателен с шага 1b — перед каждой платной операцией `--balance <баланс Studio>` (§7.1, строка «Кредиты Tripo»).
   Доработки инструментов Д-1…Д-3 (сторона оружия в `h2_bake`, варианты bench-фикстур, лист клипов) уже сделаны
   (`references/new-character-registration.md` §2, там же команда проверки).

**Этап 1 — концепт-лист** (`references/concept-sheet.md`). Строгая сетка и набор проекций:
1. **1a дизайн-front.** image_gen text→image, единственный ref — первый файл `QUALITY_REFERENCE`. Подставка — словами
   (`{{PEDESTAL_EN}}`: круглая тёмная каменная, без кольца, «seen exactly edge-on, top surface not visible»):
   коллаж `ref-base-hero-p1.png` во входах тянул камеру вверх (живой тест 2026-10-09), строгого вида подставки сбоку в
   репо нет (`references/concept-sheet.md` §6.1). Проверка кандидата — с `--min-top-pct 4` (WARN `view.frame_top`).
   Приёмщик оценивает силуэт и идентичность (порог 8,0) до трат Tripo.
2. **1b черновая модель.** Tripo, маршрут «Черновик» (single-image, без 8K и «по частям»;
   `references/tripo3d-stages.md` §5.2), затем
   `python tools/art/concept/draft_orthos.py --glb <draft.glb> --out <ASSET_DIR>/<YYYYMMDD>-draft-tripo/orthos --views front,left,back,right --aspect 3:4`
   (winged-biped — `4:3`) → `ortho_{front,left,right,back}.png` + `ortho-framing.json`. Здесь же окончательно
   выбирается `SIDE_VIEW` (`references/concept-sheet.md` §4.1).
3. **1c виды.** image_gen style-transfer поверх `ortho_<view>` (силуэт, поза и хват неприкосновенны), второе
   изображение — утверждённый front (рецепт hero-quality-v1, HANDBOOK §3.1).
4. Набор front, side, back: один размер и аспект, ровный нейтральный тёмно-серый фон, фигура целиком с подставкой,
   одинаковое размещение в % кадра; разброс роста > 3 % — WARN, > 5 % — FAIL (двухступенчатые допуски —
   `references/concept-sheet.md` §4.3, калибровка `tools/art/concept/README.md`). Выход image_gen не правится, размер не задаётся. Поза —
   нейтральная стойка миниатюры, руки отделены от корпуса, оружие в `WEAPON_HAND`; не A/T-поза (`rig-contract.json` →
   `rest_pose`). Сетка — только на листе приёмки:
   `python tools/art/concept/check_concept_views.py --set <папка видов> --key <key> --views front,side,back --role <ROLE> --palette <папка>/palette.json --sheet`
   → `checks-report.json` + `sheet-<key>.png` (код 0 — 0 FAIL, 1 — есть FAIL, 2 — ошибка входа или сбой инструмента:
   не FAIL, без перегенерации; пайп cp1251 инструмент не роняет); приёмщик смотрит лист в цвете, в сером и силуэт на белом
   (`docs/game-design/visual/02-visual-design.md` §8.6, шаг 1).
5. Тонкие элементы (тетива, древко, стрелы) на концепте — не FAIL, в промпте только «thin parts readable»; их
   читаемость решают этап 3 (профиль) и этап 4 (баллы F/T). Ретраи — ≤ 4 генерации на вид, `CORRECTION:` ≤ 3 строк
   для любого вида (блок дословно в шаблонах заданий 1a/1c). Генерации запуска исчерпаны, а пункт чек-листа Codex
   провален при 0 FAIL автопроверок — лист идёт к приёмке с пометкой `verification.json#limit_reached`, решает
   приёмщик (`references/concept-sheet.md` §5.5 п.5). Цикл — одна приёмка листа; ≤ 3 цикла после первой приёмки
   (r1…r4), дальше §5 п.4.
6. Выход: 0 FAIL и карточка kind `concept` с `score` ≥ 8,0.

**Этап 2 — Tripo H2** (`references/tripo3d-stages.md`: 12 инструментов Studio, экспорт, API v3, цены).
1. До клика сверить sha256 входов со всеми `<ASSET_ID>/source-specs/*.json` (код 3 `prepare-generation` ловит дубль
   только внутри run). CLI: `init` в `generation-request/` с `--primary-source tripo-pending`, потом
   `prepare-generation --dry-run`.
2. Слоты: FRONT = front, слот `SIDE_VIEW` = side (по умолчанию LEFT, HANDBOOK §3.2 п.3), BACK = back, второй боковой
   слот пуст (`references/tripo3d-stages.md` §5.5). Операции: H3.1 «по частям» 60 → текстура 8K «Удалить освещение»
   30 → PBR 5; перед каждой — `ledger.py check --service tripo --next-cost <цена с кнопки> --balance <баланс>` (код 0),
   после — баланс и строка `ledger.py add --task <VISUAL_CARD_ID>`.
3. Выход — чек-лист этапа 2: GLB в `source/` с длиной по заголовку, source-spec, `reports/tripo-run.json`,
   `claims.art_accepted: false`.

**Этап 3 — сборка в Blender** (HANDBOOK §4.1–4.4, `references/acceptance-and-blender.md`).
0. Поля карточки этапа 3 пишет этап 0 (§7.2): `CHARACTER`, `FIGHTER_NAME`, `FIGURE_HEIGHT_M` и `_RANGE_M`,
   `UE_NAMES`, `CLIP_PREFIX`. Пакетная заявка пилота 2026-10-13 их не записала (F18). Нет поля — дефолт П3-5
   (`docs/game-design/decisions/2026-10-13-pilot-stage3-delegated-decisions.md`): `CHARACTER` = PascalCase ключа
   контента, рост 0,55 м, если пропорции концепта не говорят иного; в карточку с `decided_by: delegated (П3-5)`.
1. До первого прогона — регистрация этапа 3 (`references/new-character-registration.md` §3): `CHARACTER` в
   `docs/art-pipeline/rig/rig-contract.json` → `skeletons.UM_HUMANOID_17_v2.characters` с подъёмом `revision`;
   проверка `python -m unittest tools/tripo-pipeline/tests/test_rig_rules.py` → OK. Сторону оружия `h2_bake` берёт из
   контракта по `rig.character`; часть и меш оружия, кости `weapon.*` и сокет `Weapon` профиля — по `WEAPON_HAND`
   (таблица Д-1, там же §2; правша — проверка `export_frame_bow_on_rotated_right`, без оружия — без части `weapon`).
2. Новый файл профиля `<key>-h2-bake-h2.json` по HANDBOOK §4.2 (образец — `medusa-h2-bake-h2.json`, не драйверы
   `h2_bake_arthur/merlin/harpy`): каждый ключ пройти, кости — по геометрии своей фигуры. До профиля — разведка и
   чек-лист HANDBOOK §4.2 «Новый герой» (сечения частей, инвентарь петель `close`, толщина ткани, значения Medusa,
   которые перенастраиваются; выбор крышка / стык весов / оболочка). Гейты профиля нового героя:
   - `"profile_version": 2` (ДС-5; 1 — только Medusa и пилот): `validate()` требует `uv.density_reference_part` (часть
     body), `textures.team_mask.base_band.part` (часть base) и `preview.frame` с `side` (RB-15, F29); расширенные пробы
     рига блокируют сборку, `rig.probe_skip` — только фигуре без голеней и стоп, прежние 7 проб не пропускаются (RB-08);
   - `preview.previous_candidate` и `preview.baseline` удалить (кандидат W4-B и текстуры Medusa);
     `frame` = `{"checks_report": "<папка видов>/checks-report.json", "side": "<SIDE_VIEW>"}` — и в bake-, и в look-dev
     профиле: без него `ld_measure` отказывает концепту другого аспекта, а `tone.json` неверен (HANDBOOK §4.2, §4.4).
   Правила пилота П3 (`docs/game-design/decisions/2026-10-13-pilot-stage3-delegated-decisions.md`; подробно — HANDBOOK
   §2.6, §2.10, §4.2, §4.4): П3-1 — разрезанное Tripo оружие: одна часть `weapon`, остальные в `body` с `rigid` 100 %
   на кости оружия; П3-2 — предмет в руке без кости: `rigid` 100 % на `arm_lower`/`hand` (новая кость — стоп §5 п.5);
   П3-3 — лист ткани с изнанкой: сначала стыки и крышки, затем `rig.cloth_shell` после луча толщины; деталь выше
   головы — `scale.figure_top_part`; нет металла — без блока `textures.materials.metal`, нет ткани —
   `team_mask.cloth_parts: []`; ≤ 45k — итог тела с оружием на экспорте (`rig-report.json#meshes_pre_export`).
3. `python tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py` по одной стадии (HANDBOOK §4.3), затем
   `--mode lookdev` и `--mode teamaccent` (HANDBOOK §4.4). TeamAccent — компоненты `hem`/`ribbon` (хотя бы один) по
   HANDBOOK §4.4 и `docs/art-pipeline/material-library/team-accent.md`; разрешённых зон меньше 5 % — порог опускается до
   замера новым файлом профиля (П3-4, П3-4a, П3-4b), главный цвет не красится; `ta_maps` без акцента или `ta_report` с
   проваленной проверкой — код ≠ 0, читать `ld-team-report.json#checks` и выбрать классы заново (не стоп; новый класс
   MatID — стоп §5 п.5). Тонкое оружие (тетива, стрелы) — только средствами профиля (`retopo.target_tris`,
   `retopo.dense_regions`, `uv.texel_priority`): не читается — пункт `rework_fix_list` или «не закрыто», без стопа;
   оружие без хвата (нужен мост-цилиндр) — стоп §5 п.5 (`references/acceptance-and-blender.md` §9.3).
4. Выход: маркеры всех стадий, `probes-report.json` с `probes.passed` `n/N` на .blend и FBX, `ld-*`, `ld-team-*`.
   Детерминизм (ДС-7, HANDBOOK §4.3): полный повтор — один раз на фигуру, на прогоне, который идёт в UE (после pass
   приёмки, до 7a); прогон доработки с `--reuse-from` повторяет только пересчитанные стадии. Отчёт повтор пишет в
   repro — перенос в производственный прогон `--stages manifest --compare-with <repro>` (F33). Код 1 `--compare-with` —
   модель дальше не идёт, разбор оркестратором (§5 п.6). Каталог повтора — свой временный выход прогона: удалить сразу
   после `determinism-report.json` (HANDBOOK §4.3).
   Перед передачей на этап 4 — единый чек-лист **HANDBOOK §4.4 «Сдача модели»**, общий для этапов 3 и 5 (RA-09; пилот:
   обе приёмки — `rework_blender` из-за тона и непросмотренных крупных планов, F72, F79; дефекты подставки и
   «наездников» нашлись только на этапах 6–7, F134, F137, F144). Коротко, что в нём:
   - тон: `python tools/art/acceptance/_tone.py <run look-dev>` → код 0 и `t_cap` 2.0 (тот же код, что
     `frames/tone.json` съёмки). Иначе ещё итерация grade из `measure-report.json#gain_suggestion` (металл —
     демпфированно, причина в `note`); не дошло — числа и причина в отчёт этапа 3;
   - `capture_acceptance_set.py` в scratch-каталог (`C:/tmp/<key>-stage3-check`): исполнитель сам смотрит
     `close-head`, `close-hands`, `close-torso`, `close-legs-back`, `close-weapon`, `pose-01` … `pose-04` — те же кадры,
     что увидит приёмщик, — и чинит найденное до передачи;
   - подставка без просвета: `base_seethrough.py` (схема `/2`) по look-dev FBX → `with_figure` ≤ 0,1 uu²
     (`references/ue-import-package.md` §2, строка «Подставка без просвета»; F149 — ложный FAIL прежней схемы);
   - зазор «наездников» (жёсткие части на кости: ворона на руке, щит) к телу в rest — `prepare.part_offsets_m` (F137);
   - дымовой прогон клипов на паттерне того же оружия: `h2anim_run.py` + `clip_contact_check` и `grip_check.py`
     (кромки при руке вперёд со спины, зазор наездника; RC-06, F129). Спека дыма —
     `references/animation-vfx-sfx.md` §6.6.

**Этап 3 — проп** (ветка `prop`; регистрация персонажа, h2_bake, look-dev и TeamAccent не делаются).
1. Run-каталог `R=art/pipeline-candidates/<ASSET_ID>/<YYYYMMDD>-prop-build` (решение скилла; новый на каждый прогон,
   доработка — `…-prop-build-r<N>`). Вход — GLB этапа 2 из `<YYYYMMDD>-prop-tripo/source/`.
2. HANDBOOK §5 п.1–5: `candidate-params.json` по образцу пропа того же вида
   (`art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-{p15-barrel,lantern-tripo-h31}/reports/candidate-params.json`),
   `target_height_m` = `FIGURE_HEIGHT_M` заявки, `asset_name` `SM_<Name>`, `texture_prefix` `T_<Name>`; ремонт
   геометрии, фронт, свечение; сборка `static_prop_candidate.py` и read-back `check_static_prop_fbx.py`.
3. Выход: `$R/export/SM_<Name>.fbx` + `T_<Name>_{BC,N,ORM}.png`, `$R/reports/candidate-report.json` с
   `checks_passed: true` и пустым списком непройденных `checks`, `$R/reports/fbx-readback.json`. Дальше — этап 4 с
   `--no-base` (`references/acceptance-and-blender.md` §3).

**Этап 4 — приёмка модели** (`references/acceptance-and-blender.md`). Объект — отгружаемый H2LD-набор.
1. Кадры: `python tools/art/acceptance/capture_acceptance_set.py --fbx <SK_<Key>_H2LD.fbx> --textures <dir> --out <evidence>/frames --key <Key> --side-view <SIDE_VIEW> --sheet art/imagegen/concept-<key>-codex/sheet-<key>.png`
   → 8 `turn-*`, `close-{head,head-back,torso,torso-back,legs,legs-back,weapon,hands,base}`, `wire-{front,34,back}`,
   `uv-layout.png`, `pose-01…04` + `pose-03b`, `sheet.png`, `compare-{front,side,back}`, `tone.json` (из
   `measure-report.json` look-dev; у героя без него — код 1), `frames.json` (`references/acceptance-and-blender.md` §3).
   Кадры приёмщику — не больше 1200 px по длинной стороне, JPEG q92 (ДС-8; с 1920 px Sol терял WebSocket, RC-22). На
   r ≥ 2 — `--previous <frames прежнего цикла>`: `frames.json#changed_vs_previous` для второго приёмщика (F151, RC-19).
   Плейсхолдеры промпта (`{{UE_NAMES}}`, `{{HEIGHT_RULE}}`, `{{TA_REPORT}}`, `{{ANCHORS}}`, `{{PREV_FIX_LIST}}`) —
   `python tools/art/acceptance/acceptor_inputs.py --frames <evidence>/frames` (`references/acceptance-and-blender.md`
   §8.1): весь bake-профиль с заметками исполнителя приёмщику не идёт (F147, F152).
2. Гейты PASS/FAIL по отчётам: G-TOPO (по финальному FBX, `ld-fbx-report`), G-UV, G-TEX, G-RIG, G-NAMES. Баллы S/F/T/D
   0–2, `score = round(sum / (2 × n) × 10, 1)`; приёмщик возвращает только JSON, `card.json` пишет запускающий.
   Приёмщик «Sol 6.1 xhigh» — `codex exec` с `-c 'windows.sandbox="unelevated"'` и `--ignore-user-config`; сбой
   песочницы (код 0, карточка-заглушка) — сбой окружения, не попытка (`references/acceptance-and-blender.md` §8.4).
3. `python tools/art/acceptance/validate_card.py <card.json> --print-verdict --check-files`. Код 0: `pass` → этап 6;
   `rework_blender` → этап 5; `return_to_stage_1` или `return_to_stage_2` (S < 1,5 или дефект исходника) → назад;
   после r3 без pass — `escalate_user`. Код 3 `needs_second_acceptor` (pass с `score` 8,0–8,4; правило общее для
   модели, листа концепта и клипа): второй приёмщик другим профилем на тех же кадрах → `card-2.json`, затем
   `validate_card.py card.json --second card-2.json --final-json final.json` — итог по минимуму и более строгому
   маршруту (`references/acceptance-and-blender.md` §6, §8.5). Код 1 — карточка невалидна, баллы не править.
   До вызова приёмщика — «Сверка входа» (`references/acceptance-and-blender.md` §3): лист того же ассета
   (`frames.json#sheet.key_match`), `accepted_object` = `frames.json#accepted_object`; S = 0 (другой персонаж) после
   верного входа — `return_to_stage_1`.

**Этап 5 — доработка.** Исполнитель доработки «Opus xhigh» (§4) по `rework_fix_list` карточки — модели или, при
позднем фиксе, клипа (пункты с `tool: этап 5 модели`; список пишет приёмщик, не оркестратор, RA-08). Новый файл
профиля `…-r<N+1>.json` и новый run `…-r<N+1>` с `--reuse-from <прежний run>` (ДС-7, HANDBOOK §4.1): стадии с
неизменными блоками профиля, входами и кодом берутся из прежнего прогона, пересчёт — с первой изменённой стадии (план
`work/reuse-plan.json`); изменился код — `--reuse-allow-code-drift` и полный повтор детерминизма. Прежний прогон и
профиль не трогать. Силуэт, пропорции и палитра в Blender не правятся. Живой Blender (`--backend mcp`) — только
осмотр (HANDBOOK §6). Выход — тот же чек-лист HANDBOOK §4.4 «Сдача модели», что у этапа 3 (RA-09), затем снова
этап 4 новым приёмщиком. Механизм, модель и effort исполнителя — в `STAGE5[]` заявки (§7.2, RA-21).

**Этап 6 — анимация (headless-авторинг), VFX, SFX** (`references/animation-vfx-sfx.md`, HANDBOOK §2.6, §2.8, §4.5).
Приёмки клипов на этапе 6 нет (ДС-1): она — шаг 7a.2 после импорта в UE.
1. Регистрация этапа 6 (`references/new-character-registration.md` §4): `CHARS` и `H2ANIM` в
   `tools/tripo-pipeline/anim/clip_manifest.py`, `character.enum` в
   `docs/art-pipeline/animation-library/clip-manifest.schema.json`; проверка `clip_manifest.py build` →
   `MANIFEST_CHECK PASS` (`check` называет героя с битой регистрацией, RB-07). Четыре карточки клипов в
   `06-tasks/anim.csv` (нужны до трат SYNTX и листу AN-18; в пачке номера AN-NN выдаёт один писатель, §11) и запись
   `HEROES` в `tools/art/anim/clip_review_sheet.py` (`Hero(...)` с этими карточками, Р6-4) →
   `clip_review_sheet.py --check` PASS. FX способности `tools/art/fx/fx_ability.py` — только если у героя есть CUE-014
   (там же §6). `HIT_TYPE` выбрать и записать в заявку (`references/animation-vfx-sfx.md` §9).
2. Источник движения (ДС-6 и решение 2026-10-14,
   `docs/game-design/decisions/2026-10-14-tripo-smart-mesh-props-anim-presets.md`; порядок и шаги —
   `references/animation-vfx-sfx.md` §6.1): по умолчанию — паттерн библиотеки героя с тем же классом оружия; нет
   образца — бесплатный пресет Tripo как образец тайминга и ключевых поз, а не клип; видеорефы SYNTX — только для
   нестандартного движения, с причиной в поле `MOTION_SOURCE` заявки. Новый `<key>-h2anim.json` и 4 клипа D-11: Idle, LungeAttack, HitReact, DeathSettle.
   Затем `python tools/tripo-pipeline/anim/h2anim_run.py <spec>` → код 0.
3. Проверки исполнителя (не приёмка): `validate_clip.py` и `clip_contact_check.py` идут внутри `h2anim_run.py`;
   `grip_check.py` — хват, кисть, локоть (`references/animation-vfx-sfx.md` §6.3); крупные планы `clip_closeups.py`
   с парой шва Idle (§10.3 там же); `clip_manifest.py build` → `MANIFEST_CHECK PASS` (клипы `measured`). Заготовки
   промптов приёмки — `evidence/acceptance-anim-prompts/<Clip>/acceptor-prompt.md` по шаблону §10 справочника (с блоком
   OEM). Выход этапа: 4 клипа авторены с PASS валидаторов (ДС-1).
4. Звуки и FX — по слотам `docs/game-design/audio/02-audio-design.md` §8.1 и CUE-011/013/014 в
   `docs/unreal/contracts/cue-dispatcher/cue-table.json`; цепочка команд — в справочнике. Прослушивание
   пользователем не стоп: агент принимает по делегированию с пометкой.

**Этап 7 — UE и игра** (`references/ue-import-package.md`, HANDBOOK §4.6–4.7, `references/new-character-registration.md`
§5). Подключение S08 для героя и помощника обязательно. Два шага с разной средой.

**7a — в агентском скрытом редакторе (MCP), строго один герой за раз (ДС-3).** Evidence 7a — `$E7` =
`art/pipeline-candidates/<ASSET_ID>/evidence/stage7a-<YYYYMMDD>` (F94), логи и PNG — `$W` = `C:/tmp/<ASSET_ID>-stage7`.
1. Среда: редактор пачки поднимает и закрывает оркестратор, агенты героев только выполняют шаги (рецепт —
   `references/ue-import-package.md` §1 п.1: `-RenderOffScreen -unattended -nosplash -ModelContextProtocolPort=8123`,
   без Live Coding, `UE_CONSOLE_DROP`, PID в `$W/editor.pid`; чужой редактор опознаётся по командной строке).
   MCP `127.0.0.1:8123` (`netstat -ano | grep ':8123 .*LISTEN'`). Каждая MCP-команда — под
   `python tools/art/material_library/ue_lock.py --step "<шаг>" -- <команда>`; `ue_hero_lookdev.py
   review|verify|apply-mi` берут блокировку сами и не оборачиваются.
2. **7a.1 Импорт** (`references/ue-import-package.md` §3–§4.3): профили `ue7a/write_import_profile.py` и
   `write_review_config.py`; `um_masters.py verify` (только проверка, ДС-4); скелет и меш `skeletal-adopt` (проп —
   `static-candidate`); клипы `h2anim_ue.py import` и `measure`; `ue_hero_lookdev.py verify`; `clip_manifest.py build`
   (клипы `technically_imported`); look-dev съёмка `ue_hero_lookdev.py review` и подстройка MI/LUT `apply-mi
   --update-verify` без переимпорта (≤ 3 итерации, RC-10; флаг переносит план MI в ожидания `verify` конфига, C50).
   Переимпорт — только при новом FBX, текстуре или структуре (§4.4 там же).
3. **7a.2 UE-кадры и приёмка 4 клипов** (ДС-1; `references/ue-import-package.md` §4.5): `h2anim_ue.py frames
   --light-pinned <review report>` по клипу за вызов, `closeup`, `sheet`; каталог цикла — `ue7a/prep_acceptance.py`;
   приёмщики — `ue7a/run_clip_acceptors.py --evidence <цикл> --executor-session-id <фактический id исполнителя
   клипов>` (параллельно, `validate_card` сам, C51/C55); рубрика R/C/D/L и маршруты —
   `references/animation-vfx-sfx.md` §10. Выход 7a — 4 карточки клипов `pass` и блок `STAGE7A` заявки (§7.2; его
   проверяет `registration_check.py`, C57). Клип вскрыл дефект модели — поздний фикс (§5 п.4; маршрут — там же §10.5).
4. Правки без сборки C++ (регистрация §5.4–5.5): CUE-011/013 в `cue-table.json` →
   `python tools/s08/cue_contract/cue_contract.py validate-table`; `DirectoriesToAlwaysCook` в
   `unreal/Unmatched/Config/DefaultGame.ini`; `S08FighterNames.json`; варианты bench-фикстур обеих досок (Р7-11:
   `env_bench_fixtures.cts --variant <Key> --hero-name "<FIGHTER_NAME>" --hero-slug <HERO_SLUG>`, затем `--check`;
   помощник без нового героя — `--hero-name "<FighterName владельца>" --hero-slug <OWNER_HERO_SLUG> --sidekick-name
   "<FIGHTER_NAME>"`; запуск — внутри контейнера `unmatched-backend`, на хосте `backend/node_modules` пуст: регистрация
   Д-2 «Где запускать», C52);
   `git add -f` новых `.uasset`.
5. Перед закрытием редактора — 0 dirty-пакетов (`ue7a/discard_master.py` сбрасывает грязный `M_UM_Figure_v2`, F92),
   коммит результата 7a; редактор закрывает оркестратор по PID (`references/ue-import-package.md` §1 п.1).

**7b — без редактора (UBT, `UnrealEditor-Cmd`), одним окном на все фигуры пачки** (до 5–10, когда пользователь
разрешит пачку больше пилотной; §1, §11). Предусловие: ни один `UnrealEditor.exe` движка не держит Live Coding (F9) и
на этом чекауте нет GUI-редактора (HANDBOOK §0.1). Уже открытый
редактор новую строку `Specs()` не увидит (статическая таблица `S08HeroesV2.cpp:104`). Агентский редактор (пачки или
брошенный) оркестратор закрывает по PID при 0 dirty-пакетов. Открыт интерактивный редактор — гейт §5 п.7.
1. Базовая линия `validate_registry.py` до de010 (RA-15), затем `de010.py apply --only <Key>` и `de011.py apply --only
   <Key>` (пачка — `--only <Key1>,<Key2>,…`; сначала `--dry-run`) с `--frames $W/de010` / `$W/de011` под `ue_lock.py`
   (notify `Contact` и dissolve-MIC; регистрация §5.1, строки `HEROES`/`CAPTURE_LOOKS`). Без `--only` оба пересохраняют
   всех героев списка — в пилоте 12 файлов MVP и ERROR реестра 1 → 5 (F157). Каждый повторный импорт клипов снимает
   notify — тогда `de010.py apply --only <Key>` повторить. В том же окне — прочие `UnrealEditor-Cmd`-шаги этапа 6, если
   они есть: импорт и проверка новых звуков, `fx_ability.py` (`references/animation-vfx-sfx.md` §5, §9).
2. C++ (регистрация §5.2, Р7-3…Р7-5): `Specs()` в `unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.cpp` — 11 полей
   `FHeroSpec`; `S08HeroesV2Tests.cpp` — счётчик, имена, `WantMs`, `WantSeconds`; `S08AudioBank.cpp`
   `CharacterKey`/`HitType` (номера строк — в таблицах регистрации). Сборка `node tools/s08/build-editor.cjs UnmatchedEditor Win64 Development -Project=<abs>/unreal/Unmatched/Unmatched.uproject -WaitMutex -NoXGE -MaxParallelActions=4`
   (в выводе `Result: Succeeded`), затем весь набор `node tools/s08/run-ue-tests.cjs "Unmatched.S08" <abs log>` —
   `EXIT CODE: 0`, нет `Result={Fail}` (`references/ue-import-package.md` §5 п.4).
3. Запись `asset-registry.json` «технически импортировано», `ue-editor-frames` (п.5; `tools/art/registry_writer.py
   entry --phase 7b-frames`, C59), затем
   `python tools/art/registration_check.py --heroes <Key>` → код 0 (полнота регистрации, RB-04), затем одна упаковка
   `tools/s08/package-client.ps1` на окно 7b (новый `Config/**.json` → touch `Unmatched.Build.cs`, сборка игрового
   target, затем `-SkipBuild`; `references/ue-import-package.md` §6.1). Варианты фикстуры
   `Config/Bench/S08Bench<Map>-<Key>.json` — не повод для touch и сборки: их нет в `RuntimeDependencies`,
   packaged-клиент читает их loose-файлом, подтверждено пилотом (F158, F162, RA-25). Кадры:
   `python tools/art/render/live_tune.py bench --map marmoreal --fixture S08BenchMarmoreal-<Key>.json --views K1+K2x1.6+K2x2.5 --out <dir> --packaged --extra=-BenchFocusFighter=<Key>`,
   то же для `--map sarpedon` с `S08BenchSarpedon-<Key>.json`. Только реальные доски, PNG открыть глазами. Один замер
   стоимости `render_bench.py` на окно 7b — на самой тяжёлой фигуре, `--repeats 1`, GPU-токен,
   `--client-args=-BenchFocusFighter=<Key>`, `--out` в `$W` (F160; `references/ue-import-package.md` §6.5).
4. Проверки кадров и трасс — чек-лист `references/ue-import-package.md` §6.3: каждый PNG открыт глазами (реальная доска,
   её задник, все фигуры v2, новый боец крупно на K2); в `bench.trace.log` нет `BENCH FAILED fixture load`, `missing=`,
   `fallback=legacy`, `mi=missing`, есть `ARTLOOK … heroes=v2`, `BENCH focus fighter=<id> (<Key>)` и
   `ARTPREVIEW heroesV2 … clips=4/4`; отпечаток каждого кадра `render_fingerprint.py check … --shot bench-<View с p
   вместо точки>-1920x1080.png` → код 0. Лист K1/K2 в цвете и в сером (02 §8.6, шаг 6). Лист клипов AN-18 —
   `clip_review_sheet.py run --packaged --heroes <Key> --fixture marmoreal=…,sarpedon=…` и `sheet --heroes <Key>`
   (`--heroes` обязателен, RB-12; пачка — одним вызовом с картой фикстур на героя, F159; команды — там же §6.2); лист
   доказывает, что клип играет в игре, но плохо показывает, как читается DeathSettle (F163). Подставка без просвета —
   `base_seethrough.py` (схема `/2`) повтором по HANDBOOK §8; первый прогон был на сдаче модели (этап 3).
5. Редактор пользователя после 7b открывается только на пересобранном `UnmatchedEditor`. Реестры и статусы — по одной
   таблице `references/new-character-registration.md` §10 (RA-26): `asset-registry.json` — первая запись после этапа 0 в
   начале 7b («технически импортировано», `ue-editor-frames`), после осмотра кадров `-Bench` — `live-packaged-probe`,
   `validate_registry.py` без новых ERROR против базовой линии; строки `docs/game-design/visual/03-asset-registry.csv`
   (фигура, 4 клипа, звук и FX) с `rollback_flag` — на шаге 7.8; обе записи — `tools/art/registry_writer.py`
   (`entry` / `rows`, фазы таблицы §10; C59); `docs/art-pipeline/DIRECTORY-MAP.md` при новых
   каталогах. Перед `safe-integrate` — `registration_check.py --heroes <Key>` ещё раз (§8).

## 7. Дефолты и заявка

### 7.1 Дефолты по делегированию

| Точка | Дефолт | Источник |
|---|---|---|
| Приёмщик | «Opus xhigh»; «Sol 6.1 xhigh» — по явному выбору. В карточку (`acceptor.profile`) и в `ACCEPTOR_PROFILE` заявки пишется фактический профиль запуска: явный выбор запускающего важнее заявки (F76, F119, RA-17) | требование заказчика №3 |
| Исполнитель доработки | «Opus xhigh»; механизм (Workflow или субагент), модель и effort — фактические, в блоке этапа заявки (§7.2) | требование заказчика №3; RA-21 |
| Порог и вето | `score` ≥ 8,0; любое измерение < 1,0 → не pass; S < 1,5 → возврат на этап 1 или 2; pass модели с `score` 8,0–8,4 — второй приёмщик другим профилем, итог по минимуму | решение скилла (`references/acceptance-and-blender.md` §6, §8.5) |
| Циклы | концепт 3, модель 2 (r1→r3), клип 2; генераций на вид ≤ 4 | решение скилла |
| Кредиты Tripo | лимит и срок — из журнала `credits-ledger.json` (`limits.tripo.credits`, `limits.tripo.until`; решение 2026-10-13 «На триппо нет лимита» сняло потолок 3000 ВР-04); `until: null` = окно открыто; граница — свежий баланс Studio. На 2026-10-14 в журнале ещё `until` «2026-10-28»: снимает ли «нет лимита» и срок — решает пользователь, данные журнала агент не меняет (RA-04). Предпроверка — `ledger.py check --service tripo` (§5 п.3): на этапе 0 без `--balance`, с шага 1b — с `--balance <баланс Studio>` перед каждой операцией (`references/tripo3d-stages.md` §1). Ожидаемо на героя: черновик ≈ 30 + H2 95 (60 + 30 + 5); точная цена — с кнопки до клика (§3 там же) | ВР-реестр ВР-04; `references/tripo3d-stages.md` §1, §3 |
| Описание и имя бойца | `DESCRIPTION`, `ANCHORS`, `FIGHTER_NAME` — из `scraped-data/api/heroes/<slug>.json` и эталонной БД (имя, оружие, помощники) текстом; аватар и сканы в генератор не подаются. Персонажа там нет (новый помощник, например Sir Gawain) — пишутся по заявке пользователя с `decided_by: delegated (ВР-реестр 2026-10-06)`; это не гейт стопа | `07-prompt-templates.md` §3.1, ВР-PR08; решение скилла |
| Помощник без нового героя | `OWNER_HERO_SLUG` — слаг героя-владельца (из заявки; не задан — ближайший по сюжету герой ростера, решение по делегированию); `HERO_SLUG` = он же; вариант bench-фикстуры: `--hero-name "<FighterName владельца>" --hero-slug <OWNER_HERO_SLUG> --sidekick-name "<FIGHTER_NAME>"`; `S08FighterNames.json` не трогается (формат держит одного помощника на героя), строка в NOTES | решение скилла; `references/new-character-registration.md` §0, Д-2, Р7-8 |
| SYNTX и Codex | SYNTX — без подтверждения каждой генерации, в лимитах и сроке журнала (ВР-04/ВР-PR04); Codex — по подписке, строка журнала `ledger.py add --service Codex` на каждый пакет-запуск и на каждую приёмку Sol (квота общая, RC-12); бюджет сессий пачки — §11 | `07-prompt-templates.md` §4 |
| Источник движения клипов | паттерн библиотеки героя с тем же классом оружия (`MOTION_SOURCE: "library: <Key образца>"`); нет образца — бесплатный пресет Tripo как образец тайминга и поз (`"tripo-preset: <имя>"`, решение 2026-10-14); видеорефы SYNTX — только нестандартное движение, причина в `MOTION_SOURCE` (визуального лимита SYNTX хватает примерно на одного героя) | ДС-6; `references/animation-vfx-sfx.md` §6.1 |
| Редактор UE 7a | агентский скрытый редактор пачки, его поднимает и закрывает оркестратор; 7a — один герой за раз; гейт §5 п.7 — только интерактивный редактор | ДС-3; `references/ue-import-package.md` §1 п.1 |
| Кадры приёмки, листы, бенч | кадры приёмщику модели и клипа — 1200 px по длинной стороне, JPEG q92 (клипа — копии `prep_acceptance.py`, листы уменьшаются целиком); PNG листов K1/K2 и бенча — в рабочий каталог вне git, JPEG-листы инструментов — в git | ДС-8; HANDBOOK §8 |
| Бюджет полигонов | ≤ 45 000 tris LOD0 фигура с оружием, подставка ≤ 2 500 | `docs/game-design/evidence/GD-058/final-2026-10-03/README.md`; практика — HANDBOOK §2.10 |
| Рост и длительности | рост и кадр контакта — по ближайшему существующему герою той же роли и оружия (таблица `Specs()` в `unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.cpp:105-116`: MVP и герои пилота Angel, Ancient Leshen, Achilles; HANDBOOK §2.10; помощник к герою — 0,78 ± 0,06). Idle — тоже по ближайшему герою; совпадение с чужим Idle допустимо: лист K1/K2 опознаёт бойца по фокусу запуска (Д-3, `references/animation-vfx-sfx.md` §2.1) | решение скилла |
| Слоты этапа 6 | `HIT_TYPE` по оружию из `BLADE`, `CLAW`, `ARROW`, `MAGIC`; смерть — `DTH-TEMPLATE`; FX и звук способности, VO — нет | `references/animation-vfx-sfx.md` §8–§9 |
| Эталон качества | канон ВР-08 hero-quality-v1 | ВР-реестр ВР-08 |
| Прогоны и профили | всегда новый run-каталог и новый файл профиля; доработка r<N+1> — новый профиль и `--reuse-from` прежнего прогона (пересчёт с первой изменённой стадии); полный повтор детерминизма — один раз на фигуру, на прогоне для UE. Суффиксы — §9 | HANDBOOK §0.1, §4.1; ДС-7 |

### 7.2 Шаблон `asset-card.yaml`

Файл обязан читаться YAML-парсером (`python -c "import yaml,sys;yaml.safe_load(open(sys.argv[1],encoding='utf-8'))" <ASSET_DIR>/asset-card.yaml`
→ без ошибки): текст с двоеточиями и спецсимволами — только в двойных кавычках, числа — числами. Пометка «проп:»
в комментарии — значение поля у ветки `prop`; `null` у пропа пишется с `decided_by` «не применимо к пропу».
Поля этапа 3 — `CHARACTER`, `FIGHTER_NAME`, `FIGURE_HEIGHT_M`, `FIGURE_HEIGHT_RANGE_M`, `UE_NAMES`, `CLIP_PREFIX` —
пишутся на этапе 0, в пакетной заявке тоже. Пилот 2026-10-13 их не получил, и этап 3 брал дефолты П3-5 (F18).
`FIGURE_BOUNDS_TOP_M` пишет этап 3 по замеру (у Angel и Achilles пилота его не было, F49).

Блоки этапов `STAGE3`, `STAGE5`, `STAGE6`, `STAGE7A`, `STAGE7B` дописывает исполнитель своего этапа — одной формой для
всех фигур (RA-22: у трёх героев пилота вышли три разные формы). `decided_by` в файле один: решения этапов дописываются
в него ключом с префиксом этапа (`"stage7a.editor_flags"`); второй ключ `decided_by:` YAML молча затирает первый (F49).
Пакетный добор этих полей в карточки ростера — до запуска ростера, не сейчас (RA-19).

Поля, которые читают инструменты, — английские: `DESCRIPTION_EN`, `ANCHORS_EN` (`make_tasks.py`, `make_1c.py`,
`sheet_acceptance.py`, выдержка приёмщика `acceptor_inputs.py`; нет `ANCHORS_EN` — берётся `ANCHORS`, F39). Русские
`DESCRIPTION` и `ANCHORS` — для человека, необязательны; если есть, они того же содержания (RA-19).

```yaml
# Заявка этапа 0. Файл: <ASSET_DIR>/asset-card.yaml. Поле без значения пользователя берёт дефолт §7.1 с decided_by.
ASSET_ID: "ASSET-<NAME>-001"        # каталог art/pipeline-candidates/<ASSET_ID>; образец ASSET-KING-ARTHUR-001
CONTENT_KEY: "<kebab>"              # king-arthur; папка концепта art/imagegen/concept-<key>-codex/, имена профилей <key>-*
KEY: "<PascalCase>"                 # KingArthur; /Game/PipelineCandidates/<Key>/, Specs().Key, имена SK_/AM_/T_, cue-table
                                    #   проп: PascalCase без "_" для папки (DecorBarrel → /Game/PipelineCandidates/DecorBarrel/
                                    #   <run>/Candidate), имя меша — UE_NAMES.prop_name
CHARACTER: "<имя в rig-contract>"   # имя БЕЗ титула (King, Queen, Sir, Lady, Lord, Doctor, Captain…), PascalCase, только
                                    #   ASCII-буквы, уникально в rig-contract.json characters (решение оркестратора
                                    #   2026-10-09): King Arthur → Arthur (KEY KingArthur), Sir Gawain → Gawain,
                                    #   Robin Hood → RobinHood («Hood» — часть имени, не титул), Little John → LittleJohn.
                                    #   Занятые имена: references/new-character-registration.md §1 (команда).
                                    #   rig.character h2_bake, --character validate_clip, clip_manifest CHARS,
                                    #   LUT T_UM_MatLUT_<CHARACTER>, AUDIO_KEY; проп: null
FIGHTER_NAME: "<имя бойца сервера>" # "King Arthur", "Harpies"; Specs().FighterName (Find() без учёта регистра),
                                    #   --hero-name варианта bench-фикстуры (регистрация Р7-11); проп: null
FIGHTER_NAME_RU: "<имя по-русски>"  # S08FighterNames.json (регистрация Р7-8); проп: null
HERO_SLUG: "<slug>"                 # scraped-data/api/heroes/<slug>.json; heroSlug фикстуры и ключ S08FighterNames.json;
                                    #   помощник без нового героя: = OWNER_HERO_SLUG; проп: null
OWNER_HERO_SLUG: null               # только помощник без нового героя (GAME_ROLE sidekick, владелец уже в Specs()):
                                    #   слаг владельца, "king-arthur"; --hero-slug варианта фикстуры (регистрация Д-2);
                                    #   иначе и у пропа: null
ROLE: "hero"                        # hero | creature | prop; check_concept_views.py --role
ANATOMY: "humanoid"                 # humanoid | winged-biped | non-humanoid | prop; ветка §3; non-humanoid = стоп
GAME_ROLE: "hero"                   # hero | sidekick | none; Specs().bHero (dissolve 0,5/0,4 с), рост, подставка 1a,
                                    #   автотест «герой выше помощника»; проп: none
WEAPON_HAND: "right"                # left | right | none; промпты концепта; профиль h2-bake: часть, меш и кость
                                    #   оружия, сокет Weapon (таблица Д-1 регистрации); проп: none
WEAPON_BONE: "weapon.R"             # weapon.L | weapon.R | null; rig-contract characters.<CHARACTER>.weapon_bone;
                                    #   ue_weapon_bone = weapon_L|weapon_R; проп: null
WEAPON_SOCKET_BONE: null            # только при WEAPON_BONE null: кость сокета Weapon в профиле ue-import (Harpy — foot.R);
                                    #   проп: null
SIDE_VIEW: "left"                   # нарисованный бок вида side = слот Tripo; дефолт left, окончательно — на шаге 1b
                                    #   (правило — references/concept-sheet.md §4.1); проп асимметричный: null (виды front+back)
POLY_BUDGET: {figure_tris_max: 45000, base_tris_max: 2500}  # GD-058 final; гейт G-TOPO этапа 4
                                    #   проп: {figure_tris_max: <по пропу того же вида>, base_tris_max: null};
                                    #   бочка — 4000 в форме Tripo (references/tripo3d-stages.md §5.3)
FIGURE_HEIGHT_M: 0.55               # Specs().BudgetUU = м × 100; герой 0.55 (Arthur, Medusa), помощник 0.45 / 0.42
                                    #   верх БЮДЖЕТА = верх головы с прилегающим убором (шлем с гребнем Achilles, корона
                                    #   Arthur); поднятый клинок, посох, рога — выше бюджета (FIGURE_BOUNDS_TOP_M); такая
                                    #   деталь выше головы → в профиле bake scale.figure_top_part (HANDBOOK §2.10)
                                    #   проп: target_height_m candidate-params пропа того же вида (бочка 0.26, фонарь 0.95 —
                                    #   ASSET-DECOR-KIT-001/20260928-{p15-barrel,lantern-tripo-h31}/reports/candidate-params.json)
FIGURE_BOUNDS_TOP_M: null           # ОБЯЗАТЕЛЬНО пишет этап 3 (F49): верх bounds фигуры без подставки = rig-report.json
                                    #   #bounds_authored_m.skeletal[1][2] (Specs().BoundsTopUU = м × 100; меч Arthur
                                    #   0.6006, рога Ancient Leshen 0.7358); без детали выше головы ≈ FIGURE_HEIGHT_M;
                                    #   проп: null
FIGURE_HEIGHT_RANGE_M: [0.52, 0.56] # Specs() Min/MaxUU у ближайшего по роли и оружию (§7.1 «Рост и длительности»;
                                    #   S08HeroesV2.cpp:105-108): Arthur 52–56 (меч), Medusa 50–55 (лук), Merlin 40–48
                                    #   (посох, помощник), Harpy 35–42 (когти, крылатый помощник). Дефолт [0.52, 0.56] —
                                    #   только для героя ближнего боя; герой-лучник — [0.50, 0.55] (как Medusa);
                                    #   FIGURE_HEIGHT_M 0.55 в обоих случаях; проп: null
IDLE_SECONDS: 2.5                  # число, не дробь (56/24 → 2.3333); clips.Idle.frames = round(× 24) = 60; Specs() —
                                    #   2.5f или N.0f / 24.0f; совпадение с чужим Idle допустимо (§7.1); проп: null
LUNGE_CONTACT_FRAME: 7              # Specs().LungeContactFrame, de010: меч Arthur 7, посох Merlin 8, лук Medusa 8,
                                    #   когти Harpy 7; проп: null
PALETTE:                            # 2–3 основных + 1 акцент; формат palette.json (references/concept-sheet.md §4.5)
  main:                             # имена → {{PALETTE_EN}}
    - {name: "<english name>", hex: "#RRGGBB"}
    - {name: "<english name>", hex: "#RRGGBB"}
  accent: {name: "<english name>", hex: "#RRGGBB"}   # измерения P/S приёмки; TeamColor — только рантайм (HANDBOOK §2.9)
DESCRIPTION_EN: "<1–3 предложения: внешность, костюм, материалы, оружие и рука, признаки силуэта; из scraped-data и
                 БД (§7.1)>"                   # читают инструменты: блок SUBJECT промптов 1a/1c (make_tasks, make_1c)
DESCRIPTION: "<то же по-русски>"   # необязательно, для человека (RA-19)
ANCHORS_EN: "<что держит идентичность между видами: оружие и рука, головной убор, число голов или крыльев; 3–6
             признаков через '; '>"         # промпты 1a/1c, приёмка листа и модели (acceptor_inputs.py, F39)
ANCHORS: "<то же по-русски>"       # необязательно; инструменты берут его, только если нет ANCHORS_EN
                                    # колчан и ножны, если заявка не задала сторону, — против WEAPON_HAND (натягивающая
                                    #   или свободная рука): лук в левой → "quiver over the RIGHT shoulder"; меч в правой →
                                    #   "scabbard on the LEFT hip" (references/concept-sheet.md §9)
QUALITY_REFERENCE:                  # канон ВР-08; первый файл — image 1 промпта 1a, весь список — эталон приёмок
  - "art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
  - "art/imagegen/hero-quality-v1/<ближайший герой>/"  # harpy | king-arthur | medusa | merlin; ближайший — по роли
                                    #   и оружию, то же правило, что рост (§7.1 «Рост и длительности»): меч, ближний бой →
                                    #   king-arthur; лук → medusa; посох, магия → merlin; крылья, когти → harpy
UE_NAMES:                           # из KEY и поколения H2 (Stage = H2LD; H3LD только при втором поколении)
  stage: "H2LD"                     # Specs().Stage, папка /Game/PipelineCandidates/<Key>/<Stage>/; проп: null
  skeletal_mesh: "SK_<Key>_H2LD"    # проп: null
  base: "SM_<Key>_H2LD_Base"        # проп: null
  materials:                        # слот FBX — materials.atlas профиля bake: M_<Key>_H2_Atlas; проп: [MI по профилю §5 п.6]
    - "MI_<Key>_H2LD"
    - "MI_<Key>_H2LD_Base"
    - "MI_<Key>_H2LD_P1"
    - "MI_<Key>_H2LD_P2"
    - "MI_<Key>_H2LD_Base_P1"
    - "MI_<Key>_H2LD_Base_P2"
  dissolve: "/Game/UM/Materials/v2/Dissolve/MI_<Key>_H2LD_{P1,P2}_Dissolve"   # проп: null
  skeleton: "/Game/PipelineCandidates/<Key>/Rig/SK_<Key>_Skeleton"            # проп: null
  clips: "/Game/PipelineCandidates/<Key>/H2Anim/AM_<Key>_{Idle,LungeAttack,HitReact,DeathSettle}"  # проп: null
  textures:                         # файлы look-dev: T_<Key>_H2LD_2K_*.png, T_<Key>_H2LD_TeamAccent_2K.png
    - "T_<Key>_H2LD_{BC,N,ORM,MatID,TeamAccent}"
    - "T_<Key>_H2LD_Edge (или _EdgeMask)"
    - "T_UM_MatLUT_<CHARACTER>"
  prop_name: null                   # проп: "<Name>" по образцу Decor_Barrel → SM_<Name>, T_<Name>_{BC,N,ORM},
                                    #   папка /Game/PipelineCandidates/<Key>/<run>/Candidate (HANDBOOK §5 п.7)
CLIP_PREFIX: "<PRE>"                # 3–4 заглавные от CHARACTER, не MED|HAR|ARTH|MER; id клипов <PRE>-<Clip>; проп: null
AUDIO_KEY: "<CHARACTER заглавными>" # DTH-<AUDIO_KEY>, VO-<AUDIO_KEY>-…; S08AudioBank::CharacterKey (Р7-5); проп: null
HIT_TYPE: "BLADE"                   # BLADE | CLAW | ARROW | MAGIC; этап 6 (references/animation-vfx-sfx.md §9);
                                    #   S08AudioBank::HitType; проп: null
STAGE6_SLOTS: {death: "DTH-TEMPLATE", ability_fx: "none", ability_sfx: "none", vo: "none"}
                                    # проп без CUE/звука: "нет слотов"
MOTION_SOURCE: "library: <Key образца>"   # ДС-6: паттерн библиотеки героя с тем же классом оружия (меч — KingArthur,
                                    #   Angel; лук — Medusa; посох, копьё — Merlin, Achilles; когти — Harpy, AncientLeshen);
                                    #   | "tripo-preset: <имя пресета>" (нет образца в библиотеке; только образец
                                    #   тайминга и поз, не клип — решение 2026-10-14)
                                    #   | "syntx: <причина — нестандартное движение>"; смешанные — через «;»; проп: null
CREDITS:
  ledger: "docs/game-design/visual/credits-ledger.json"   # tools/art/visual/ledger.py add/check
  tripo_limit: "лимит и срок — из журнала (решение 2026-10-13; until: null = окно открыто); граница — баланс Studio"
  planned: "<черновик ≈ 30 + 95>"   # проп: "<multi-view 60–130>" (references/tripo3d-stages.md §3)
VISUAL_CARD_ID: "AN-<NN>"           # строка 06-tasks/anim.csv (area hero, проп — prop); --task ledger.py add (Codex, Tripo)
ACCEPTOR_PROFILE: "opus-xhigh"      # | sol-6.1-xhigh → acceptor.profile "Opus xhigh" | "Sol 6.1 xhigh"; повторы тем же.
                                    #   Пишется ФАКТ: запускающий выбрал другой профиль — поле переписать (RA-17, F119)
ASSET_DIR: "art/pipeline-candidates/<ASSET_ID>"
NOTES:
  - "ВР-18: ростер после MVP вне объёма; основание — запрос пользователя <дата>"
# --- блоки этапов: пишет исполнитель своего этапа (RA-22); пути — от корня репо ---
STAGE3:
  profile_version: 2                # h2-bake: 2 — новый герой (ДС-5); 1 — только Medusa и пилот
  bake_run: "<ASSET_DIR>/<YYYYMMDD>-h2-bake"
  lookdev_run: "<ASSET_DIR>/<YYYYMMDD>-h2-lookdev"
  teamaccent_run: null              # отдельный прогон TeamAccent, если был (F38)
  profiles: ["build-profiles/<key>-h2-bake-h2.json", "build-profiles/<key>-h2-lookdev.json",
             "build-profiles/<key>-h2-lookdev-teamaccent.json"]
  handover: "<HANDBOOK §4.4 «Сдача модели»: t_cap, base_seethrough with_figure, дым клипов — числа>"
  determinism: "<прогон, на котором был полный повтор, или «после pass, до 7a» (ДС-7)>"
  executor: {mechanism: "workflow|subagent", model: "<факт>", effort: "<факт>", session: "<id>"}   # RA-21
STAGE5: []                          # по циклу доработки модели: {cycle: "r2", run, profile, reuse_from, late_fix: false,
                                    #   source_card: "<карточка, чей rework_fix_list исполнялся>", executor: {…}}
STAGE6:
  run: "<ASSET_DIR>/<YYYYMMDD>-h2anim"
  spec: "build-profiles/<key>-h2anim.json"
  clip_cards: ["AN-<idle>", "AN-<lunge>", "AN-<hit>", "AN-<death>"]
  prompts: "<ASSET_DIR>/evidence/acceptance-anim-prompts/"   # заготовки промптов приёмки 7a.2
  vfx: "<решение по слотам §8 справочника анимации>"
  sfx: "<HIT_TYPE, смерть, новые рецепты; пометка о прослушивании>"
  executor: {mechanism: "workflow|subagent", model: "<факт>", effort: "<факт>", session: "<id>"}   # доработка клипа
STAGE7A:
  editor: "<командная строка и PID агентского редактора; кто закрыл, 0 dirty>"
  import_run: "<ASSET_DIR>/<YYYYMMDD>-h2ld-ue-import[-r<N>]"   # живой; прежние — в NOTES
  import_profile: "build-profiles/<key>-h2ld-lookdev-ue-import[-r<N>].json"
  review: "<ASSET_DIR>/<YYYYMMDD>-h2ld-ldc-ue"
  evidence: "<ASSET_DIR>/evidence/stage7a-<YYYYMMDD>"         # $E7
  clip_acceptance: "<цикл → вердикты и баллы 4 клипов>"
STAGE7B:
  window: "<окно 7b пачки: герои, коммит>"
  evidence: "docs/art-pipeline/evidence/<content-key>-<YYYYMMDD>"   # $E, README
decided_by:                         # ОДИН ключ на файл; по каждому полю, не заданному пользователем
  "<поле>": "delegated (ВР-реестр 2026-10-06)"   # | user | "не применимо к пропу"
  "stage7a.<решение>": "delegated: <что и почему>"   # решения этапов — с префиксом этапа (F49)
```

### 7.3 Шаблоны этапа 0 в справочнике

`references/intake-and-evidence.md`: §1 — запись `docs/art-pipeline/asset-registry.json` (все 21 ключ
`ASSET_REQUIRED`, `validate_registry.py:70-74`; проверено на копии реестра 2026-10-09 — ни одного ERROR), §2 —
постановка `<ASSET_DIR>/STOP-RIG-CONTRACT-3.md` для ветки `non-humanoid` (гейт §5 п.1), §3 — `.gitignore` ассета.

## 8. Правила проекта

- **Коммит** — только `git commit --no-verify` (AGENTS.md «Commits without hooks»), файлы добавляются списком путей
  (HANDBOOK §8). Без `git add -A`, `stash`, `reset`, `clean`, push. Чужие незакоммиченные файлы не трогать. Перед
  коммитом сверить `git diff` с объёмом задачи: агенты-исполнители выходят за рамки. В пачке коммитит один агент
  (оркестратор), агенты героев не коммитят параллельно (§11).
- **`.git/index.lock`.** Приложение Codex раз в несколько секунд гоняет `git diff` по главному чекауту и дважды
  оставило зависшую блокировку (F82, RC-21). Перед коммитом — `python tools/art/pipeline_batch/git_lock.py
  [--remove-stale]`: снимается только блокировка старше 2 мин (`--stale-sec 120`) при отсутствии живых процессов
  git; живую — ждать, чужую операцию не ломать.
- **Тесты перед коммитом этапов 3, 6, 7:** `python -m pytest tools/tripo-pipeline/tests tools/art/visual/tests
  tools/tripo-pipeline/blender/h2_bake/tests tools/art/acceptance -q` зелёные; допустимы только 3 xfail известного
  дрейфа данных (пресеты Merlin/Arthur, UM-MASTERS; F91, RA-16; `references/ue-import-package.md` §7.3). Этапы 6 и 7
  правят записи, которые проверяют ещё `tools/art/anim/tests tools/art/de010/tests tools/art/material_library/tests
  tools/art/pipeline_batch/tests tools/art/tests/test_registration_check.py` — их добавить (весь `tools/art/tests` не
  брать: в нём 2 известных падения `test_concept_paste_assets`, текстуры вне git).
- **Фикс инструмента — вместе с документом** (RA-05). Коммит fix/feat инструмента пайплайна несёт правку справочника
  скилла или HANDBOOK, где описан шаг или опция: пять коммитов пилота (cd3ee7fe, 22c19667, 3ed2d354, 8e00e5f0,
  9322d489) меняли только код, и опции `figure_top_part`, `--light-pinned`, скрытый редактор узнавали из NOTES.
- **Интеграция из worktree** — только `tools/git/safe-integrate.sh <branch>`: перед ним
  `python tools/art/registration_check.py --heroes <Key>` → код 0 на ветке со свежим `fix/admin-panel` (RB-04), затем
  сухой прогон и `--apply`.
  Скрипт требует: ветка содержит свежий `fix/admin-panel`; в основном чекауте нет git-операции и staged-файлов;
  входящие файлы там без незакоммиченных правок; при изменениях в `unreal/` не запущены UnrealEditor, UBT и клиент
  основного чекаута (`safe-integrate.sh:53-57`) — агентский редактор закрыт оркестратором, интерактивный — гейт §5 п.7.
  Затем в основном чекауте пересобрать UnmatchedEditor (команду печатает скрипт) и выполнить
  `tools/s08/sync-staged-build.ps1 -From <worktree>` без повторной упаковки.
- **Одна упаковка на изменение** (AGENTS.md «Iteration speed», ловушка нового `Config/**.json` — этап 7b п.3).
- **Режим.** Новый ассет — полный режим; ревью = приёмщик этапов 1, 4 и шага 7a.2. Новые меши и материалы требуют замера
  цены (AGENTS.md «Iteration speed»): ровно один прогон `render_bench.py` на шаге 7b после упаковки, на варианте
  фикстуры с новым бойцом; в пачке — один на окно 7b, на самой тяжёлой фигуре (команда —
  `references/ue-import-package.md` §6.5: `--repeats 1`, GPU-токен, `--client-args=-BenchFocusFighter=<Key>`, F160).
  Число записать в evidence; править только превышение порога (ACC-022 60 FPS) или поломку, оптимизации в пределах
  бюджета запрещены, повторных бенчей нет. Правка одного параметра после приёмки — лёгкий режим, без бенча.
- **Смотреть кадр перед отчётом:** открыть PNG и проверить реальную доску, верный задник и v2-фигуры (AGENTS.md
  «Look before you report»).
- **Процессы:** свои Blender headless, скрипты и клиенты останавливать по PID после проверки командной строки.
  Агентский редактор UE (флаги `-unattended -RenderOffScreen`, PID в `editor.pid` пачки) закрывает оркестратор при 0
  dirty-пакетов; интерактивный редактор не закрывать без слова пользователя (§5 п.7, ДС-3); живой Blender
  пользователя не закрывать. Одновременно — не больше 2 headless-прогонов Blender; GPU-шаги 7b (`-Bench`, AN-18,
  `render_bench`) — только когда своих Blender и UE нет (RC-23, §11).
- **Статусы** — одна таблица по этапам: `references/new-character-registration.md` §10 (RA-26). Коротко:
  `asset-registry.json` после этапа 0 не трогается до 7b (F161), выше «технически импортировано» исполнитель его не
  поднимает (HANDBOOK §0 п.3; «художественно принято» требует акта `docs/game-design/evidence/(ART|GD)-NNN/…`);
  «художественно принято, по делегированию» — в `status_note` карточек приёмки и в строках `03-asset-registry.csv`
  после осмотра листа K1/K2 на шаге 7.8 (ВР-17).

## 9. Evidence и реестры

```
art/pipeline-candidates/<ASSET_ID>/
  .gitignore                     # этап 0 (references/intake-and-evidence.md §3)
  asset-card.yaml
  source-specs/tripo-<task8>-h2.json   # этап 2 героя; черновик — tripo-<task8>-draft.json, проп — tripo-<task8>.json
  build-profiles/<key>-h2-bake-h2.json, <key>-h2-lookdev.json, <key>-h2-lookdev-teamaccent.json,
                 <key>-h2anim.json, <key>-h2ld-lookdev-ue-import.json      # только новые файлы; доработка — …-r<N>.json
  <YYYYMMDD>-draft-tripo/{generation-request,source,orthos,reports}/   # шаг 1b (решение скилла)
  <YYYYMMDD>-h2-tripo/  <YYYYMMDD>-prop-tripo/                         # этап 2 (references/tripo3d-stages.md §7)
  <YYYYMMDD>-h2-bake[-r<N>]/  <YYYYMMDD>-h2-lookdev[-r<N>]/            # этапы 3, 5 (r<N> — цикл приёмки, словарь ниже)
  <YYYYMMDD>-h2anim[-r<N>]/                                            # этап 6 и доработка клипа (ревизия спеки)
  <YYYYMMDD>-prop-build[-r<N>]/{reports,export,preview}/   # этап 3 пропа (HANDBOOK §5, решение скилла по имени)
  <YYYYMMDD>-h2ld-ue-import[-r<N>]/  <YYYYMMDD>-h2ld-ldc-ue/{review-config.json, review/<tag>/}   # 7a (r<N> — импорт)
  evidence/acceptance-concept/<YYYYMMDD>-<front|sheet>-r<N>/card.json   # этап 1 (решение скилла)
  evidence/acceptance/<YYYYMMDD>-r<N>/{card.json, card-2.json?, final.json?, acceptor-prompt.md,
                                       acceptor-inputs.json, frames/}   # этап 4
  evidence/acceptance-anim-prompts/<Clip>/acceptor-prompt.md            # этап 6: заготовки промптов приёмки (ДС-1)
  evidence/acceptance-anim/<YYYYMMDD>-r<N>[-m<M>]/<Clip>/{card.json, card-2.json?, final.json?, acceptor-prompt.md,
                                       frames/}                         # шаг 7a.2: приёмка клипов (ДС-1)
  evidence/stage7a-<YYYYMMDD>/          # $E7: снимки до/после, um-masters verify, discard-master, base-seethrough
art/imagegen/concept-<key>-codex/                     # пакет Codex (07 §1.1)
docs/game-design/visual/06-tasks/prompts/<ASSET_ID>-concept.codex.md, <ASSET_ID>-concept-views.codex.md
docs/art-pipeline/evidence/<content-key>-<YYYYMMDD>/  # $E: evidence и README 7b (references/ue-import-package.md §6.4)
C:/tmp/<ASSET_ID>-stage7/                             # $W, вне git: логи, PNG листов и бенча, drop/, editor.pid
```

Evidence 7a лежит в каталоге ассета `$E7`, а не в `$E`: объём записи 7a — каталог ассета (F94, пилот). README этапа
и всё 7b — в `$E` (`references/ue-import-package.md` §1, блок переменных).

**Словарь суффиксов** (RA-23; в пилоте один `r<N>` значил четыре разных вещи, ретраи назывались `-2`, `-b`, `h2b`):

| Суффикс | Где | Что значит | Как считать |
|---|---|---|---|
| `-r<N>` цикла приёмки | `evidence/acceptance/…-r<N>`, `acceptance-concept/…-r<N>` | цикл приёмки модели или листа | r1 — первая приёмка; лимит §5 п.4 |
| `-r<N>` прогона модели | `<YYYYMMDD>-h2-bake-r<N>`, `-h2-lookdev-r<N>`, профили `…-r<N>.json` | прогон доработки, который сдаётся приёмке цикла r<N> | равен номеру цикла приёмки, который его принимает; у первого прогона суффикса нет |
| `-r<N>` импорта | `<YYYYMMDD>-h2ld-ue-import-r<N>`, `…-ue-import-r<N>.json` | итерация импорта 7a (переимпорт `references/ue-import-package.md` §4.4) | своя нумерация: r2 — второй импорт, с циклами приёмки не связан |
| `-r<N>` спеки клипов | `<key>-h2anim-r<N>.json`, `<YYYYMMDD>-h2anim-r<N>` | ревизия спеки и прогона клипов: доработка клипа или новая модель | следующий свободный номер; под какую модель — `target` спеки (путь и sha) |
| `-r<N>` цикла клипа | `evidence/acceptance-anim/…-r<N>/<Clip>` | цикл приёмки клипа (свой у каждого клипа) | лимит — 2 доработки клипа |
| `-r<N>-m<M>` | `evidence/acceptance-anim/…-r<N>-m<M>` | перепринятие клипа с неизменными ключами после позднего фикса модели r<M> | цикл клипа не тратится (`cycle` = r<N>), §5 п.4 |
| `--tag r<N>` | `$V/review/r<N>` | итерация look-dev съёмки 7a | не больше 3 |
| `-t<K>` | любой прогон или профиль | повтор того же прогона после сбоя инструмента или правки профиля до приёмки | вместо `-2`, `-b`, `h2b`; причина — строка в NOTES |

`.gitignore` ассета — шаблон `references/intake-and-evidence.md` §3 (генерический `h2_bake` кладёт 4K-мастера прямо в
`textures/` без суффикса, родительский `art/pipeline-candidates/.gitignore` их не ловит). В git идут 2K-набор, MatID 4K
и LUT, как у Medusa; проверка после первого прогона этапа 3 — `git check-ignore -v` для 4K-мастера и 2K-карты.

Сырые GLB и 4K-мастера — локально, sha256 в source-spec и отчётах; кадры — JPEG 1200 px q92 (HANDBOOK §8, ДС-8);
PNG листов K1/K2 и бенча — только в `$W`, сырые кадры AN-18 — в `C:/tmp/visual/AN-18` (в пилоте 18 PNG листов на 45 МБ
ушли в коммит, RA-13); JPEG-листы, которые инструменты пишут в репозиторий (`h2anim_ue.py sheet`, лист AN-18), — evidence.
Реестров два, и они разведены. `docs/art-pipeline/asset-registry.json` создаётся на этапе 0, следующая запись — в
начале 7b; проверяется `validate_registry.py`. `docs/game-design/visual/03-asset-registry.csv` получает строки на
шаге 7.8 (таблица статусов — `references/new-character-registration.md` §10). Журнал трат —
`docs/game-design/visual/credits-ledger.json` (старые журналы не пополнять, `07-prompt-templates.md` §4.1).

## 10. Справочники

| Файл | Этапы | Что внутри |
|---|---|---|
| `references/concept-sheet.md` | 1 | промпт-пак 1a/1c, сетка и допуски, слоты видов, ретраи, `prompts.md` |
| `references/tripo3d-stages.md` | 1b, 2 | 12 инструментов Studio, экспорт, API v3, цены, маршруты «Черновик», H2 и проп, CLI, чек-лист выхода |
| `references/acceptance-and-blender.md` | 3, 4, 5 | рубрики S/F/T/D и концепта, схема карточки, калибровка, бриф доработки |
| `references/animation-vfx-sfx.md` | 6, 7a.2 | стандарт скелета и клипов, источник движения, дымовой прогон, приёмка клипа и маршрут позднего фикса, слоты VFX/SFX, команды аудио и FX |
| `references/ue-import-package.md` | 7 | агентский редактор, импорт, look-dev и `apply-mi`, UE-кадры и приёмка клипов (7.4a), подключение S08, упаковка, кадры, чек-лист |
| `references/new-character-registration.md` | 3, 6, 7 | все места в коде и конфигах, где перечислены герои, и проверки; Д-1…Д-3 (сделаны): профиль по стороне оружия, варианты bench-фикстур, лист клипов |
| `references/intake-and-evidence.md` | 0 | шаблоны записи `asset-registry.json`, `STOP-RIG-CONTRACT-3.md`, `.gitignore` ассета |
| `docs/art-pipeline/BLENDER-MODEL-HANDBOOK.md` | все | норма: §2 контракт, §3 входы, §4 герой (§4.4 «Сдача модели»), §5 проп, §6 живой Blender, §8 сдача |
| `docs/game-design/decisions/2026-10-14-skill-refinement-delegated-decisions.md` | все | решения ДС-1…ДС-8 после пилота: порядок 6/7a, два класса стопа, агентский редактор, `um_masters`, пробы рига, источник движения, `--reuse-from`, кадры 1200 px |
| `docs/art-pipeline/evidence/skill-pilot-2026-10-13/` | все | находки пилота F1–F163 (`NOTES.md`) и исследование RA/RB/RC (`research/`) |

## 11. Пакетный режим

Разделы выше написаны на одну фигуру, а пилот шёл пачкой из трёх (RA-20, RC-15). Здесь — что делается один раз на
пачку, что на каждую фигуру и какие ресурсы строго последовательны. Пачку больше пилотной без слова пользователя не
запускать (§1). Оркестратор пачки ведёт её состояние в `NOTES.md` своего evidence (фигура → этап, текущий run,
потраченные циклы, вопросы пользователю, кто держит редактор и GPU), как пилот
(`docs/art-pipeline/evidence/skill-pilot-2026-10-13/NOTES.md`); файл очереди `roster-queue.json` (RC-15) — до ростера.

### 11.1 На пачку и на фигуру

| Этап | Один раз на пачку | На каждую фигуру |
|---|---|---|
| 0 | пробы исполнителей на сессию (§6, этап 0 п.4); строка условий Tripo на журнал; место на диске (§11.5); бюджет Codex (§11.4); номера AN-NN — один писатель | `ANATOMY` по описанию фигуры, не дефолтом пачки (F1); `asset-card.yaml`, `.gitignore`, запись реестра |
| 1 | полосы Codex 4–5 (RC-24); задания `make_tasks.py`/`make_1c.py`; приёмка листов `sheet_acceptance.py`; второй приёмщик `finish_second.py` | приёмка фронта и листа, свой цикл |
| 1b, 2 | очередь Tripo `prep_1b.py`; одна вкладка Studio, герои конвейером; форма Studio — на пачку (F11) | строка журнала сразу после каждой операции (`tripo_log.py`); `post_1b.py`, `post_h2.py`; GLB выгружать сразу (RC-20) |
| 3–5 | не больше 2 прогонов Blender одновременно (§11.6) | профиль, прогон, сдача модели, приёмка |
| 6 | регистрация общих файлов — один писатель (RC-13); `clip_manifest.py build` — один сборщик за раз (F117) | спека, `h2anim_run.py`, проверки исполнителя, заготовки промптов |
| 7a | редактор пачки поднимает и закрывает оркестратор (ДС-3) | 7a строго по одному герою, шаги под `ue_lock` |
| 7b | одно окно на 5–10 героев: `de010`/`de011 --only <Key1>,<Key2>,…`, C++ и тесты, одна упаковка, один замер `render_bench` на самой тяжёлой фигуре | варианты фикстуры, `-Bench` обеих досок с `-BenchFocusFighter=<Key>`; AN-18 — одним вызовом с картой фикстур на героя (F159); `registration_check.py --heroes <Key>` |
| коммит | один коммитер; `git_lock.py` перед коммитом (§8) | — |

### 11.2 Ресурсы: что параллельно, что строго по одному

Таблица — по замерам пилота (`research/C-scale.md` §5) с поправками волн 1–2 исследования.

| Ресурс или этап | Режим | Замер пилота | Ограничение и что изменилось |
|---|---|---|---|
| Codex 1a/1c (полосы) | параллельно, 4–5 полос | прогон 3,5–6,5 мин в 2 полосы (3,6 мин на фигуру), 11–27 мин в 8 (2,1 мин на фигуру) | квота ChatGPT общая с Sol (RC-12); хвост процесса до 23 мин после ответа больше не держит полосу: `codex_lane.py` завершает задание по файлу `-o` и гасит своё дерево (RC-11) |
| Sol-приёмщик | параллельно | модель 10–14,5 мин, клип ≈ 5 (4 сразу) | та же квота; переподключения WebSocket на 1920 px — кадры 1200 px (ДС-8, RC-22) |
| Opus-приёмщик (Workflow) | параллельно | 9,3–9,9 мин | квота Claude не измерена; второй приёмщик на 8,0–8,4 срабатывает часто (3 из 7 приёмок модели — 8,1, RC-19), на r ≥ 2 он получает `changed_vs_previous` |
| Tripo Studio | строго одна вкладка, конвейер внутри | 1b ≈ 1,2 мин; H2 ≈ 12 мин на героя с подготовкой | рабочий стол пользователя: Claude in Chrome — основной путь, пачка Windows-MCP — в окно без пользователя (RC-18, `references/tripo3d-stages.md` §2) |
| Blender headless (этапы 3, 5, 6, дым) | не больше 2 одновременно | bake 11–19 мин; повтор детерминизма 12–19 мин | GPU (RC-23), диск (RC-03); доработка — `--reuse-from` (RC-07), полный повтор — один раз на фигуру (ДС-7, RC-08) |
| UE-редактор (7a, UE-кадры клипов) | строго один герой за раз | ≈ 73 мин на фигуру | `:8123`, `ue_lock` с heartbeat; редактор пачки — у оркестратора (ДС-3, RC-05); подстройка MI — `apply-mi` без переимпорта (RC-10) |
| UBT, `UnrealEditor-Cmd`, упаковка (7b) | окно на 5–10 героев | ≈ 12 мин на окно без кадров | ни одного редактора с Live Coding; `de010`/`de011 --only` не пересохраняют MVP (RC-14, F157) |
| Packaged-клиент (`-Bench`, AN-18, `render_bench`) | строго по одному, GPU-токен | `-Bench` 100 с на доску; AN-18 591 с на доску (K1 по всем `HEROES`) | K1 теперь — объединение группы запуска, а не всех `HEROES` (76168867): лист не дорожает с ростером. Но у каждого героя свой вариант фикстуры, поэтому K1 снимается на каждого; `--k1-from` экономит только повторную съёмку того же героя на той же сборке после доработки клипа (RC-09 перенесён частично, `research/W3-applied-D1.md`) |
| Регистрация общих файлов | один писатель на пачку | ≈ 20 общих файлов на героя | `anim.csv`, `clip_manifest.py`, схема манифеста, `rig-contract.json`, `Specs()` и тесты, `cue-table.json`, `DefaultGame.ini`, `S08FighterNames.json`, оба реестра (RC-13; регистрация §5) |
| Коммиты | один коммитер | — | `git_lock.py` (F82, RC-21) |
| Этап 0 | пачкой | 85 карточек одним коммитом | `ANATOMY` по фигуре (F1) |

### 11.3 Инструменты пачки (в репозитории, W2-a ee301065)

Разовые скрипты пачки больше не пишутся в `C:/tmp` и `evidence/*/tasks/`: агенты 7a пилота написали 964 строки
дублей (RA-12). Новый повторяющийся шаг — инструмент в `tools/` с тестами и строкой в документе (§8).

| Инструмент | Шаг | Что делает |
|---|---|---|
| `tools/art/pipeline_batch/make_tasks.py` | 0, 1a | поля этапа 1 `asset-card.yaml`, `palette.json` и задания 1a из файла ростера |
| `tools/art/pipeline_batch/codex_lane.py` | 1a, 1c | полоса Codex по claim-файлам; задание закрывается по ответу, а не по выходу процесса |
| `tools/art/pipeline_batch/rebg.py` | 1a | ровный серый фон фронта лицензионной фигуры (F7) |
| `tools/art/pipeline_batch/make_1c.py` | 1c | задания 1c по орто 1b |
| `tools/art/pipeline_batch/sheet_acceptance.py` | 1c | приёмка листов пачкой (Sol); промпт с блоком OEM и рубрикой (`references/concept-sheet.md` §5.6) |
| `.claude/workflows/second-acceptor.js` | 1, 4, 7a.2 | второй приёмщик «Opus xhigh» со строгой выходной схемой (`references/acceptance-and-blender.md` §8.3) |
| `tools/art/pipeline_batch/finish_second.py` | 1, 4, 7a.2 | вывод `second-acceptor` → `card-2.json` и пара `validate_card --second` (затем ещё раз с `--check-files`) |
| `tools/art/pipeline_batch/prep_1b.py`, `tripo_log.py`, `post_1b.py` | 1b | очередь Tripo, строка журнала, приём GLB и орто |
| `tools/art/pipeline_batch/post_h2.py` | 2 | source-spec, превью, рамки частей по вершинам (F10) |
| `tools/art/pipeline_batch/git_lock.py` | коммит | зависший `.git/index.lock` (F82) |
| `tools/tripo-pipeline/ue7a/write_import_profile.py`, `write_review_config.py` | 7a.1 | профиль импорта и конфиг съёмки из шаблона (`--set` для смысловых ключей) |
| `tools/tripo-pipeline/ue7a/delete_prev.py`, `refresh_carrier.py` | 7a, переимпорт | ассеты прежнего импорта; меш превью клипов после новой модели (F145) |
| `tools/tripo-pipeline/ue7a/discard_master.py` | 7a | сброс грязного `M_UM_Figure_v2` без сохранения (F92) |
| `tools/tripo-pipeline/ue7a/prep_acceptance.py` | 7a.2 | каталог цикла приёмки клипов: кадры, промпт из заготовки, сверка sha |
| `tools/tripo-pipeline/anim/grip_check.py`, `clip_closeups.py` | 6, 7a.2 | хват, кисть, локоть; крупные планы клипа и пара шва Idle |
| `tools/art/registration_check.py` | 7b, интеграция | полнота регистрации героя в коде и конфигах (RB-04) |

### 11.4 Бюджет сессий Codex (RC-12)

- Квота Codex общая для генерации и приёмщика Sol. Пилот: 11–15 сессий Codex на фигуру (1a, 1c, приёмка фронта и
  листа, 1–3 приёмки модели, 6–8 приёмок клипов) и 1–3 Opus. В плане пачки — оценка «фигуры × 15 сессий»; окна
  лимита в файлах не видно, поэтому отказ по лимиту — пауза полос, а приёмщик Sol заменяется Opus (другая квота) с
  записью факта в `ACCEPTOR_PROFILE`.
- Строка журнала `ledger.py add --service Codex` — на каждый пакет-запуск и на каждую приёмку Sol
  (`references/concept-sheet.md` §5.5 п.4, §5.6). За 2026-10-13 и 2026-10-14 таких строк нет (`codex_packages=69`, все
  до 2026-10-08) — пачка их не пропускает.

### 11.5 Диск (RC-03): правило очистки ждёт решения пользователя

Пилот: ≈ 22 ГБ на фигуру (прогон h2-bake 2,4–2,6 ГБ, из них `work/bake/*.npy` 7 × 192 МБ; повторы детерминизма),
черновики пилота в `C:/tmp` — 42 ГБ, на C: было свободно 228 ГБ. Предложение RC-03 — удалять `work/` прежних прогонов
после pass следующего, `work/bake/*.npy` после стадии `textures`, `work/` принятого прогона после коммита 7a. Это
удаление данных, и решает пользователь (SUMMARY исследования, «Решения пользователя» п.3); до ответа агент прежние
прогоны и черновики пилота не удаляет. Свои временные каталоги этого прогона — повтор детерминизма и дымовой прогон
клипов — удаляются сразу после отчёта (§6, этап 3 п.4; `references/animation-vfx-sfx.md` §6.6). Перед пачкой — свободное
место на C: (`Get-PSDrive C`): меньше 40 ГБ плюс ≈ 22 ГБ на фигуру пачки — вопрос пользователю (ДС-2, необратимое).

### 11.6 Blender, GPU и редактор (RC-23, ДС-3)

- Не больше 2 headless-прогонов Blender одновременно: у параллельных bake стадия `textures` шла 6,7 мин вместо 4,5.
- GPU-токен `C:/tmp/unmatched-gpu.lock` берут только `live_tune` и `render_bench`; Blender `h2_bake` и скрытый
  редактор 7a — нет. Поэтому GPU-шаги 7b (`-Bench`, AN-18, `render_bench`) — только когда своих Blender и UE нет
  (сверить по PID), а look-dev съёмка 7a — без параллельного Blender: неустоявшиеся кадры (F153) и шум якоря (F155)
  растут под нагрузкой.
- Редактор 7a — один на пачку, у оркестратора; агенты героев свой редактор не поднимают и чужой не закрывают
  (`references/ue-import-package.md` §1 п.1).

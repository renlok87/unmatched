# Ресерч: готовые скиллы и библиотеки для агентной разработки 3D-ассетов в Blender (от концепта до запекания)

- **Дата:** 2026-10-03
- **Вопрос:** существуют ли готовые скиллы / библиотеки для агентных кодинг-тулов (Claude Code и совместимых, включая ZCode/openskills) для создания и реализации 3D-модели в Blender по полному циклу: концепт → меш → UV/материалы → риг → запекание → экспорт.
- **Контекст проекта:** пайплайн уже работает headless — Blender 5.2.2 CLI (`blender --background --factory-startup --python …`, `blender/ASSET-MEDUSA-001/build_tripo_medusa.py`), источники мешей — Tripo h31 GLB (см. `art/pipeline-candidates/`), импорт в UE5, артефакты `art/imagegen/` на этапе концепта. Требования: `docs/game-design/17-art-production-spec.md`, `docs/game-design/04-blender-production.md`.
- **Актуальность данных:** звёзды, лицензии и версии зафиксированы на 2026-10-03 по страницам GitHub/PyPI/blender.org.

## TL;DR

1. **Готовый end-to-end скилл существует и совпадает с нашим пайплайном почти один-в-один:** [`majidmanzarpour/blender-game-skills`](https://github.com/majidmanzarpour/blender-game-skills) — «turn concept art into rigged, game-ready 3D assets»: gated-фазы blockout → формы → топология → UV → материалы → **запекание (normal/AO/base color/roughness/metallic через Cycles)** → риг → экспорт GLB/FBX с round-trip-проверкой. Работает headless (`blender --background --python`), Blender 4.2–5.2, без GPU. MIT, 123★, но проект молодой (1 коммит) — брать как базу, вендорить в репозиторий.
2. **Справочное заполнение пробелов API:** [`ra100/blender-claude-plugin`](https://github.com/ra100/blender-claude-plugin) — 8 доменных скиллов-справочников по Blender 5.x (geometry/shader nodes, модификаторы, риггинг, рендер). MIT, 16★.
3. **Официальный MCP-сервер Blender появился** ([blender.org/lab/mcp-server](https://www.blender.org/lab/mcp-server/)), но для прод-конвейера он не нужен: наш headless-CLI подход воспроизводимее; MCP — только для интерактивной отладки в открытой GUI-сессии, с учётом предупреждения blender.org об отсутствии песочницы.
4. **bpy как pip-модуль теперь точно нашей версии:** `pip install bpy==5.2.2` (CPython 3.13, колесо под Windows есть) — вариант для юнит-тестов пайплайна без запуска бинаря; для боевых билдов оставить Blender CLI.
5. **Генератив «концепт→меш»:** остаёмся на Tripo (уже используется, коммерческий API). Локальная альтернатива с чистой лицензией — TRELLIS.2-4B (MIT); Hunyuan3D — лицензионные ловушки (см. §5), не рекомендован.

---

## 1. Метод

Веб-поиск (Claude Code skills, Blender MCP, bpy, генератив text/image-to-3D, запекание) + выборочная верификация страниц GitHub, PyPI, blender.org. Уровень доверия помечен для каждой находки: **[verified]** — страница репо/пакета прочитана напрямую; **[search]** — только по поисковой выдаче, требует проверки перед использованием.

## 2. Готовые скиллы (формат SKILL.md, совместим с Claude Code / ZCode / openskills)

| Скилл / репо | Покрытие стадий | Лицензия | Зрелость | Вердикт |
|---|---|---|---|---|
| [majidmanzarpour/blender-game-skills](https://github.com/majidmanzarpour/blender-game-skills) `blender-image-to-3d` [verified] | концепт-бриф → blockout → формы → топология+LOD → UV → материалы → **бейк** → риг → экспорт GLB/FBX | MIT | 123★, 1 коммит, 0 открытых issues | **база для нас** |
| [ra100/blender-claude-plugin](https://github.com/ra100/blender-claude-plugin) [verified] | справочники API: ~373 geometry nodes, ~95 shader nodes, ~50 модификаторов, ~45 констрейнтов, рендер Cycles/EEVEE | MIT | 16★, 13 коммитов, Blender 5.0/5.1 | **дополнение-справочник** |
| [DirectorGunner/AI-SKILL-blender](https://github.com/DirectorGunner/AI-SKILL-blender) [verified] | роутер по Blender Manual + bpy (скриптинг, анимация, материалы, рендер, linked libraries) | **AGPL-3.0** | 4★, 2 коммита | осторожно: AGPL — не вендорить в кодовую базу |
| [freshtechbro/claudedesignskills](https://github.com/freshtechbro/claudedesignskills) `blender-web-pipeline` [search] | Blender → редукция полигонов → бейк → экспорт под Three.js | н/п | [search] | малорелевантен (веб, не UE) |
| [RobLe3/cc-blender-skill](https://github.com/RobLe3/cc-blender-skill) [search] | рецепты материалов (volume absorption и т.п.) | н/п | [search] | точечно, опционально |
| Маркетплейс-скиллы: «Script Blender Automation», «Agent 3D Modeler V2», «Blender Shader Nodes», «3d-web-experience» ([skillsdirectory.com](https://www.skillsdirectory.com), [mcpmarket.com](https://mcpmarket.com)) [search] | заявлены: bpy-автоматизация, полный цикл DCC, PBR-материалы | н/п | не проверены | только как указатели; перед использованием читать исходники |

### 2.1. `blender-image-to-3d` (majidmanzarpour) — главное совпадение с задачей [verified]

- **Вход:** референс-изображения (концепт-арт, model sheets, фото) → скилл сам пишет asset-бриф.
- **Фазы с гейтами по измеримым критериям, не «на глаз»:** силуэтный IoU с концептом, band-width-профили, проверки пропорций; на каждой фазе — compare-sheet и ожидание аппрувала.
- **Запекание:** `bake_maps.py` — normal/AO/base color/roughness/metallic через Cycles (CPU-fallback), без GPU.
- **Риг:** скелет, контролы, веса, сокеты (пропускается для статичных пропсов) + опциональная анимация.
- **Экспорт:** GLB/glTF/FBX + манифест + re-import round-trip верификация — тот же паттерн, что наш `art004_import_verify.py`.
- **Рантайм:** агент пишет и гоняет bpy-скрипты headless; работает с Blender 4.2…5.2; из зависимостей только Pillow в одном скрипте. Опционально подключается к живой сессии Blender через MCP.
- **Установка:** `npx skills add majidmanzarpour/blender-game-skills --skill blender-image-to-3d` или вручную скопировать `skills/blender-image-to-3d/` в скилл-каталог агента (у нас — `.agents/skills/`, формат совместим с openskills).
- **Ограничения (сам репо честно документирует):** пропорции требуют ортографических видов; невидимые сзади детали помечаются как `inferred`; протестирован только с Claude Code.
- **Риски зрелости:** 1 коммит, активный PR — проект молодой. Лицензия MIT позволяет вендорить и дорабатывать у себя.

### 2.2. `ra100/blender-claude-plugin` — справочная база по Blender 5.x [verified]

8 скиллов-справочников (API-референсы, каталоги нод, рецепты, гайды по отладке): geometry-nodes, shader-nodes, compositing, python-scripting (Python 3.13), animation-rigging, modeling-modifiers, physics, scene-rendering. Умеет работать и без MCP — просто генерирует запускаемые bpy-скрипты. Ставится как плагин или копированием каталога. Полезен как «документация, которую агент читает сам», в связке с нашим Blender 5.2.

### 2.3. Скиллы-маркетплейсы [search]

На агрегаторах ([skillsdirectory.com](https://www.skillsdirectory.com), [mcpmarket.com](https://www.mcpmarket.com), [aimcp.info](https://www.aimcp.info)) есть скиллы «Script Blender Automation», «Agent 3D Modeler V2», «Blender Shader Nodes», «3d-web-experience» — описания заявляют полный цикл (вплоть до «model → reduce → bake → export»), но содержимое/качество/лицензии не проверялись. Относить к списку «посмотреть при необходимости», не к базе.

## 3. MCP-серверы Blender (интерактивное управление из агента)

| Сервер | Что умеет | Лицензия | Зрелость | Примечание |
|---|---|---|---|---|
| **Официальный** [Blender Lab MCP Server](https://www.blender.org/lab/mcp-server/) ([projects.blender.org/lab/blender_mcp](https://projects.blender.org/lab/blender_mcp/wiki)) [verified] | natural-language доступ к bpy, `execute_blender_code`, инспекция сцены, док-поиск, рендер; блендер-аддон = TCP-мост на localhost:9876; Blender 5.x | GPL (репо Blender) | официальный Blender Lab, v5.1+ | **без песочницы**: предупреждение blender.org — «execute LLM generated code without any guards» |
| [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp) → PyPI `mcp-for-blender` [verified] | сцена/объекты/материалы, произвольный Python, библиотеки Poly Haven/Sketchfab/Poly Pizza, AI-генерация Rodin/Hunyuan3D/Tripo, экспорт GLB/FBX, «safe mode» | MIT | ~29.9k★, 233 коммита | сокет без аутентификации/шифрования; GUI-ориентированный |
| [sandraschi/blender-mcp](https://github.com/sandraschi/blender-mcp) [search] | форк с фокусом на headless-автоматизацию | н/п | [search] | проверить перед использованием |

**Вывод для проекта:** наш прод-путь — headless-CLI скрипты, они детерминированы, версионируются и повторяемы; MCP-серверы закрывают другой кейс — интерактивную отладку в открытой GUI-сессии Blender (например, ручной ретопо/риговый тюнинг). Если понадобится — брать официальный (Blender 5.x, поддерживается Blender Foundation), помня про отсутствие песочницы: разрешить только для доверенных задач, локально.

## 4. Python-библиотеки для headless-конвейера

- **[bpy на PyPI](https://pypi.org/project/bpy/)** [verified] — «Blender as a Python module» от Blender Foundation. **bpy 5.2.2 (15.09.2026) ровно соответствует нашему Blender 5.2.2**, есть Windows x86-64 колесо (~338 MB), требует **ровно CPython 3.13**. GPL-3.0. LTS-линии 4.5/4.2 сопровождаются. Известная ловушка версий 4.x — жёсткая привязка к точной версии Python (см. [docs.blender.org: Blender as a Python Module](https://docs.blender.org/manual/en/latest/advanced/extensions/python/wheels.html)).
  - Применение у нас: юнит-тесты пайплайна (валидация манифестов, сокетов, нод) в venv без запуска бинаря. Для боевых билдов оставить `blender --background` — не тянуть venv/3.13 в воспроизводимый прод-путь.
- **[fake-bpy-module](https://github.com/nutti/fake-bpy-module)** [search] — стабы API для типизации/автодополнения (не исполняет Blender). Полезно агенту при написании скриптов: меньше галлюцинаций по bpy-API. MIT.
- **Запекание:** базовый API — `bpy.ops.object.bake(type='NORMAL'|'AO'|…)` с image-нодой в материале и `use_selected_to_active`; аддоны **SimpleBake** ([SuperHive](https://superhivemarket.com/products/simplebake---simple-pbr-and-other-baking-in-blender-2), GPL) и **Easy Bake** лишь автоматизируют этот boilerplate и рассчитаны на GUI [search]. Для headless-пайплайна — свой код (у нас уже пишется в `build_tripo_medusa.py`); `bake_maps.py` из blender-game-skills — готовый референс. Код GPL-аддонов не копировать.
- **Смежные утилиты (если понадобится валидация/ремонт мешей вне Blender):** `trimesh`, `pymeshlab`, `pygltflib` [search — стандартные библиотеки экосистемы, версии не проверялись]. Ретопология: Quad Remesher — закрытый платный; Instant Meshes — открытый [search].

## 5. Генеративный этап «концепт → меш»

| Инструмент | Лицензия | Комментарий |
|---|---|---|
| **Tripo** (текущий выбор проекта, h31) | коммерческий API | уже интегрирован, есть retopo-выдача; продолжать |
| **TRELLIS.2-4B** ([Microsoft](https://github.com/microsoft/TRELLIS)) [search] | код MIT; TRELLIS.2-4B reported MIT (веса ранних версий — исследовательская лицензия MSRLA — проверять конкретный чекпоинт) | image-to-3D с PBR, локально; нужен GPU; рига не даёт — только меш/текстуры |
| **Hunyuan3D-2 / 2.1** ([Tencent-Hunyuan](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)) [search] | 2.0 — **non-commercial**; 2.1 — Community License: не действует в EU/UK/KR, порог по выручке компании | **лицензионные ловушки**; для коммерческого проекта не рекомендован без юр. проверки |
| **TripoSR** [search] | MIT | быстрый/лёгкий image-to-3D, качество заметно ниже — только черновой блокбаут |
| Hyper3D Rodin | коммерческий сервис | доступен из ahujasid-MCP; альтернатива Tripo того же класса |

**Вывод:** для MVP остаёмся на Tripo; локальный fallback с чистой лицензией — TRELLIS.2 (требует GPU и не решает риг/анимацию, т.е. не заменяет наш retopo+build-пайплайн, а только генерацию сырого меша).

## 6. Покрытие стадий нашего пайплайна

| Стадия | Есть в проекте сегодня | Готовое снаружи | Разрыв |
|---|---|---|---|
| Концепт | `art/imagegen/` | — | нет |
| Меш из концепта | Tripo h31 GLB | TRELLIS.2 (MIT, локально), Rodin, Tripo (уже) | нет |
| Клинап/ретопо | retopo-10k от Tripo + `build_tripo_medusa.py` | Quad Remesher (платный), Instant Meshes | нет |
| UV/материалы/бейк | свой bpy-код (T_Medusa_BC/N/RM) | `bake_maps.py` из blender-game-skills (референс), SimpleBake (GUI, GPL — только идеи) | **паттерн гейтов (IoU/профили) из скилла стоит перенять** |
| Риг/анимация | свой арматурный код; [аудит 2026-09-27](../2026-09-27-animation-audit/README.md) | Rigify (встроен), Auto-Rig Pro/Mixamo (платно/сервис), скилл умеет сокеты+веса | частично: сокет-контракт у нас свой |
| Запекание → экспорт → UE | FBX-экспорт + `art004_import_verify.py`, RENDER-фингерпринт | round-trip верификация в скилле (тот же паттерн) | нет |
| Агентная обвязка | openskills (`.agents/skills/`), свои tools/art-скрипты | blender-game-skills (end-to-end), ra100 (API-справочники), fake-bpy-module (типы) | **главный разрыв — отсутствие скилла; закрывается установкой/адаптацией** |

## 7. Рекомендации

1. **Установить и вендорить `blender-image-to-3d`** (MIT) в `.agents/skills/` как базу агентного скилла «концепт→game-ready»; адаптировать его гейты под наши bench-вью и маски (`tools/art/render/`), а экспортную фазу — под FBX-контракт UE и сокет-контракт из аудита анимации.
2. **Добавить `ra100/blender-claude-plugin`** как справочные скиллы по Blender 5.x API (MIT) — снижает галлюцинации агента по bpy/нодам.
3. **`fake-bpy-module` в dev-зависимости** — типизация bpy-скриптов для агента.
4. **MCP Blender Lab — опционально**, только для интерактивных GUI-сессий отладки; в прод-конвейер (headless CLI) не внедрять: воспроизводимость важнее.
5. **Пробовать `pip install bpy==5.2.2` (Python 3.13 venv)** для юнит-тестов пайплайна; прод-билды остаются на Blender CLI 5.2.2.
6. **Генератив:** Tripo продолжаем; TRELLIS.2 — единственный кандидат на локальный fallback (проверить лицензию конкретного чекпоинта весов); Hunyuan3D не брать без юр. проверки.
7. **Лицензионная гигиена:** AGPL-скилл (AI-SKILL-blender) — только читать, не копировать; GPL-код SimpleBake — не копировать в наш пайплайн; MIT-репо вендорить с сохранением копирайт-заголовков.

## 8. Риски и оговорки

- `blender-game-skills` — 1 коммит: репо молодое; API-контракт может меняться. Смягчение: вендорим копию, обновления осознанно.
- Маркетплейс-скиллы не проверялись постранично — помечены [search].
- Все MCP-серверы Blender исполняют LLM-код без песочницы (явное предупреждение blender.org); сокеты — без аутентификации. Только localhost, только доверенные задачи.
- Данные о звёздах/лицензиях — на 2026-10-03; перед внедрением перепроверить LICENSE-файлы в клонированных репо.

## 9. Источники

- https://github.com/majidmanzarpour/blender-game-skills
- https://github.com/ra100/blender-claude-plugin
- https://github.com/DirectorGunner/AI-SKILL-blender
- https://github.com/freshtechbro/claudedesignskills
- https://github.com/RobLe3/cc-blender-skill
- https://www.blender.org/lab/mcp-server/ и https://projects.blender.org/lab/blender_mcp
- https://github.com/ahujasid/blender-mcp (PyPI: `mcp-for-blender`)
- https://github.com/sandraschi/blender-mcp
- https://pypi.org/project/bpy/ и https://docs.blender.org/manual/en/latest/advanced/extensions/python/wheels.html
- https://github.com/nutti/fake-bpy-module
- https://superhivemarket.com/products/simplebake---simple-pbr-and-other-baking-in-blender-2
- https://github.com/microsoft/TRELLIS, https://github.com/Tencent-Hunyuan/Hunyuan3D-2
- Агрегаторы: https://www.skillsdirectory.com, https://www.mcpmarket.com, https://www.aimcp.info

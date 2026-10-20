# 3d-model-pipeline — мини-пачка 2026-10-20: Bruce Lee, Sherlock Holmes, Dr. Watson

Делегирование пользователя (2026-10-20, дословно): «Можем параллельно начать работу над остальными персонажами. У нас
сейчас есть условно работающий Артур и Медуза. Нужно прогнать скилл пайплайн для пары других персонажей. Заодно
проверим работу с генерацией ассетов Gemini. И ревью ассетов с помощью Z-Code.» Пачку больше этих трёх фигур не
запускать. Этапы 7a/7b — только после слова главной сессии (три другие сессии вливают правки в `fix/admin-panel`).

Первый боевой прогон после отмены ChatGPT (SKILL.md §0, AGENTS.md «AI tools and side models»): картинки — Gemini,
побочная модель и второй приёмщик — Z-Code (GLM-5.3 / GLM-5.3-Flash) через Computer Use.

## Состояние пачки

| Фигура | ASSET_ID | VISUAL_CARD_ID | Этап | Текущий run / шаг | Циклы | Заметки |
|---|---|---|---|---|---|---|
| Bruce Lee | ASSET-BRUCE-LEE-001 | AN-51 | 1 | 1a принят Sol 9,4 (Codex, 2026-10-13); 1b черновик 70729ed4 выгружен 2026-10-20 (`20261013-draft-tripo/source`, орто чистые); 1c — Gemini отказал (F2), путь лицензионной фигуры — unstability.ai | концепт: 1a r1 | — |
| Sherlock Holmes | ASSET-SHERLOCK-HOLMES-001 | AN-98 | 3 | этап 2 готов: `20261015-h2-tripo` 734b9954, 14 частей, 1 966 070 tris, parts14 + tex8k-pbr, register-source OK, превью чистое (лупа в правой) | концепт: 1a r1, 1c r1 | 95 кр. (60 + 30 + 5) |
| Dr. Watson | ASSET-DR-WATSON-001 | AN-64 | 3 | этап 2 готов: `20261020-h2-tripo` 5458aaff, 20 частей, 1 946 780 tris, parts20 + tex8k-pbr, register-source OK, превью чистое (револьвер в правой, саквояж в левой) | концепт: 1a r1, 1c r1 | 95 кр. |

Ресурсы: редактор UE — не поднимать до слова главной сессии; Blender headless — не больше 2; рабочий стол — одна
полоса Computer Use (Gemini, Z-Code) и Windows-MCP (Tripo в Chrome пользователя).

## Этап 0 (2026-10-20)

- `asset-card.yaml` трёх фигур дополнены полями этапов 3–7 (`CHARACTER`, `FIGHTER_NAME`, рост, `UE_NAMES`,
  `CLIP_PREFIX`, `HIT_TYPE`, `MOTION_SOURCE`, …) с `decided_by_stage0`. Реестр `asset-registry.json`: все три записи уже
  были (2026-10-13), собственных ERROR `validate_registry.py` нет; чужой ERROR базовой линии — 1 (UM-MASTERS, не чинить).
- `.gitignore` ассетов: `git check-ignore` печатает `*-tripo/source/*.glb` у всех трёх.
- Пробы исполнителей:
  - Claude in Chrome — подключён только браузер «Browser 1» на macOS (`isLocal: false`), к локальному Chrome доступа нет;
    встроенный браузер Claude не залогинен в Tripo Studio (кнопка «Sign up/Log in»). Tripo — по F9 пилота: клики
    Windows-MCP во вкладке Studio Chrome пользователя.
  - Z-Code — проект `unmached`, GLM-5.3-Flash (Vision), режим «Ask before changes»; агент сам открывает изображения
    инструментом Read (см. калибровку).

## Калибровка Z-Code (2026-10-20)

**Итог: не пройдена** (`zcode-calibration/RESULT.md`): C2 10,0 против 8,1 (+1,9), C1 — противоположный победитель
слепого сравнения; карточка Z-Code — невалидный JSON. **Второй приёмщик мини-пачки — Opus `second-acceptor`**
(свежий контекст), Z-Code — только побочная модель для текста.

См. `zcode-calibration/`. C1 — слепое сравнение витрин King Arthur / Medusa (раунд `blind-s2/r3`, оценки Opus в
`docs/game-design/select-screens/blind-s2/r3-REVIEW.md`). C2 — повтор принятого листа 1c Ancient Leshen по рубрике
concept-sheet §11 (Opus `card-2.json` 8,1: S 2, C 1,5, Q 1,5, P 1,5). Входы скопированы в `in/` (копии файлов из git,
в коммит не идут).

## Находки (F)

| # | Этап | Находка | Что сделано |
|---|---|---|---|
| F1 | 0 | Claude in Chrome привязан к чужому macOS-браузеру; локального нет. Встроенный браузер без входа в Tripo. | Tripo — Windows-MCP в Chrome пользователя (F9 пилота) |
| F2 | 1a/1c | **Gemini отказывает Bruce Lee** («I can help with images of people, but I can't depict some public figures»): 1a (промпт CORE + эталон Medusa) и 1c front (CORE-FRONT + орто 1b + дизайн 1a), Gemini Pro (Nano Banana), 3:4. Первая попытка 1a с битым промптом (моя выборка текста задания вместо CORE) Gemini нарисовал — крупный план без подставки, в зачёт не идёт. Отказ модерации непостоянный, обходные формулировки — запрет скилла (concept-sheet §20) | Bruce Lee 1c — по пути лицензионных фигур (unstability.ai по решению пользователя 2026-10-13); сравнение 1a Codex↔Gemini невозможно (Gemini не рисует) |
| F3 | 0 | Z-Code GLM-5.3-Flash сам открывает кадры инструментом Read из репо (вложения не нужны), но каждая запись файла ждёт «Allow» в режиме «Ask before changes»; карточка — невалидный JSON (лишняя `}`) | калибровка `zcode-calibration/RESULT.md`; второй приёмщик — Opus |
| F4 | 2 | Studio «Texture» на задаче прошлой сессии (Шерлок 734b9954) открылась с **пустыми** слотами видов; на свежей задаче (Ватсон 5458aaff) форма сама подставила Front/Left/Back задачи. Слоты Шерлока загружены вручную теми же файлами 1c (sha256 = input-preflight) | перед «Generate Texture» проверять слоты, не только 8K и Remove Lighting |
| F5 | 2 | Studio пометила генерацию Ватсона «Sensitive content detected — model set to private» (револьвер) — генерация прошла, приватность и так вкл. | нет действий |
| F6 | 2 | Экспорт Studio называет файл подписью модели («detective character 3d model.glb», «steampunk detective 3d model.glb»): у Шерлока и Ватсона подписи похожи — переносить сразу после каждой выгрузки, сверять число частей | перенос по одному файлу, `glbcheck` после каждого |
| F7 | 1c | **Gemini 1c на Ватсоне (вымышленный персонаж) работает:** front/side/back поверх орто 1b — `check_concept_views` 0 FAIL / 2 WARN, водяного знака в углах нет, рамка = орто (верх 4 %, земля ≈ 94 %), IoU силуэта с орто 0,67/0,74/0,82 (Codex 0,76/0,72/0,81). Выход — JPEG 1792×2400 (аспект 0,7467, не ровно 3:4). Принятый лист Codex не заменён — это проверка пути | `gemini/watson-1c/`, строка журнала AN-64 |
| F8 | 1c | **Bruce Lee 1c: маршрут — Tripo Studio «Image», GPT Image 2** (2026-10-21). Seedream v5.0 Pro в unstability.ai (2 референса + CORE-FRONT, 3:4, 2K) молча отбросил задание: ни картинки, ни ошибки. GPT Image 2 в Tripo нарисовал все три вида: рамка = орто (верх 3,9–4,2 %, земля 93,4–95,4 %), IoU front 0,735, side 0,635; `check_concept_views` 0 FAIL / 2 WARN. Квота Free n/1000 кончилась на back: кнопка показала 8, баланс в шапке Studio не изменился (20 125). Chrome блокирует второй файл «множественной загрузкой» — скачивается только первый кадр запуска | пакет `concept-bruce-lee-codex` 1c, 3 строки журнала AN-51; разрешение множественных загрузок не включал (настройка браузера пользователя) |
| F9 | 1c | `sheet_acceptance.py prepare` сравнивает `checks-report.json` пакета с повтором БЕЗ `--side-ortho`: отчёт, снятый с `--side-ortho` (проверка `view.facing`), даёт «повтор расходится» | основной отчёт — без `--side-ortho`, отчёт с проверкой ракурса — `checks/set-facing/` |
| F10 | — | Этапы 3 Шерлока и Ватсона: агенты прошлого процесса пережили его выход (Ватсон: «this agent never stopped»), Шерлок держал команду на запросе разрешения (mv в `C:/pb`) — запросы разрешений ночью никто не нажимает | агентам сказано писать только в свой ASSET_DIR и `C:/tmp/<key>-stage3*` |

## Решения 2026-10-21 (передано главной сессией, слова пользователя дословно)

«Хорошо, использую Opus High вместо Z-код для приемщика. Вот, и продолжай без меня, делай все сам. Касательно сетов тоже и 3D модели героев.»
- Приёмщики: первый «Opus xhigh», второй (полоса 8,0–8,4) «Opus high»; Z-Code баллов не ставит.
- Волна A (Bruce Lee, Sherlock Holmes, Dr. Watson) — этапы 3–7b, витринная хайполи со слепым ревью двух независимых Opus; 7a — один скрытый редактор, один герой за раз; одна упаковка после 7b всех фигур волны и повторная проверка полными матчами на обеих досках (`docs/game-design/evidence/PLAYTEST-2026-10-21-night/README.md`).
- Затем ростер по сетам `docs/art-pipeline/ROSTER-SETS-PLAN-2026-10-21.md`: волна B — Muhammad Ali, Sinbad + The Porter; не больше 3–4 фигур одновременно.

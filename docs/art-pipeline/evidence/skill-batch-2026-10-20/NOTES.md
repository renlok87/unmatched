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
| Bruce Lee | ASSET-BRUCE-LEE-001 | AN-51 | 1 | 1a принят Sol 9,4 (Codex, 2026-10-13); 1b черновик оплачен в Studio (70729ed4), GLB не выгружен; 1c — Gemini | концепт: 1a r1 | 1a переделать в Gemini для сравнения |
| Sherlock Holmes | ASSET-SHERLOCK-HOLMES-001 | AN-98 | 2 | 1c принят Sol 8,8 (2026-10-15); H2 геометрия в Studio (734b9954, 60 кр.), выгрузка не завершена; 8K/PBR не начаты | концепт: 1a r1, 1c r1 | — |
| Dr. Watson | ASSET-DR-WATSON-001 | AN-64 | 2 | 1c принят Sol 8,8 (2026-10-15); H2 не начат | концепт: 1a r1, 1c r1 | помощник Sherlock |

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

См. `zcode-calibration/`. C1 — слепое сравнение витрин King Arthur / Medusa (раунд `blind-s2/r3`, оценки Opus в
`docs/game-design/select-screens/blind-s2/r3-REVIEW.md`). C2 — повтор принятого листа 1c Ancient Leshen по рубрике
concept-sheet §11 (Opus `card-2.json` 8,1: S 2, C 1,5, Q 1,5, P 1,5). Входы скопированы в `in/` (копии файлов из git,
в коммит не идут).

## Находки (F)

| # | Этап | Находка | Что сделано |
|---|---|---|---|
| F1 | 0 | Claude in Chrome привязан к чужому macOS-браузеру; локального нет. Встроенный браузер без входа в Tripo. | Tripo — Windows-MCP в Chrome пользователя (F9 пилота) |

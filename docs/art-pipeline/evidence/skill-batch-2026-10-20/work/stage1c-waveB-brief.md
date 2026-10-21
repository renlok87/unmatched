# Бриф этапа 1b/1c: волна B (Muhammad Ali, Sinbad, The Porter)

Исполнитель — субагент оркестратора (Sonnet high — клики Gemini/Tripo по правилу AGENTS.md «Model and effort for new
agents»).

## Полномочия (дословно)

- Пользователь 2026-10-21: «Хорошо, использую Opus High вместо Z-код для приемщика. Вот, и продолжай без меня, делай
  все сам. Касательно сетов тоже и 3D модели героев.»
- Пользователь 2026-10-20: «…для ассетов можно использовать создание изображений в приложении Gemini…»
- Траты:
  - Gemini — подписка, строки журнала `ledger.py add --service Gemini`, terms уже записан;
  - Tripo Studio Image — только если у кнопки цена 0 или квота Free; платный Image — стоп и вопрос оркестратору.
- Пароли не вводить. На экране входа — стоп.

## Что сделать

Этап 1c скилла (`.agents/skills/3d-model-pipeline/SKILL.md` §6 «Этап 1», `references/concept-sheet.md` §1c, §7, §11,
§20): виды front, side, back поверх орто черновика 1b, затем пакет и лист.

- 1a принят: `art/imagegen/concept-<content-key>-codex/design/` и `concepts/`. 1b готов:
  `art/pipeline-candidates/<ASSET_ID>/20261013-draft-tripo/orthos/`.
- **Маршрут:**
  - **Sinbad и The Porter** (вымышленные) — Gemini: gemini.google.com в Chrome пользователя через **Claude in
    Chrome в своей группе вкладок**. Мышь и рабочий стол не трогать. Pro-модель, режим изображений, 3:4.
  - Промпт — CORE из `references/concept-sheet.md` для каждого вида. Сохранить его файлом в
    `docs/art-pipeline/evidence/skill-batch-2026-10-20/gemini/<content-key>-1c-<view>.txt`, как у Ватсона.
  - Референсы — орто 1b того же вида и дизайн 1a.
  - **Muhammad Ali** (реальный человек) — Gemini откажет (F2). Маршрут F8: Tripo Studio «Image» (GPT Image 2) в своей
    вкладке. Каждую попытку и отказ — строкой F в отчёт.
- **Выход** по образцу волны A:
  - Ватсон (Gemini): `docs/art-pipeline/evidence/skill-batch-2026-10-20/gemini/watson-1c/`;
  - пакет Bruce (Tripo Image): `art/imagegen/concept-bruce-lee-codex/` (виды, `checks/`, `generation-records.json`,
    `verification.json` с блоком `stage_1c`, `sheet-<key>.png`, `manifest-sha256.json`).
- Виды кладутся в `art/imagegen/concept-<content-key>-codex/<content-key>-{front,side,back}.png`. Перед этим проверить,
  что там лежит: прежний вид не затирать, старое — в `repair-history/`.
- **Проверка:** `check_concept_views` основной (без `--side-ortho`, F9), ракурс — в `checks/set-facing/`.
- **Не делать:**
  - не обходить отказ модерации переформулировками (§20);
  - не включать в браузере «множественные загрузки»;
  - при водяном знаке — перегенерация.
- **Последний шаг:** `python tools/art/acceptance/sheet_acceptance.py prepare` по каждому ассету. Workflow приёмки
  запускает оркестратор: агент отдаёт пути аргументов и останавливается.

## Правила

- Только Claude in Chrome в своей группе вкладок. Свои вкладки закрыть в конце.
- Сессия «Карты и пропсы» тоже работает в Tripo Studio: форму её задачи не трогать, работать в своей задаче/вкладке.
- Без git.
- Код инструментов не править.
- Не запускать команд, которым нужен запрос разрешения.
- Писать только в репозиторий (папки трёх ассетов и `gemini/`) и в `C:/tmp/wave-b-1c`.
- Каждый кадр, о котором пишете, открыть глазами.

## Отчёт

Для каждого ассета:
- маршрут и попытки;
- пути видов;
- `check_concept_views`;
- что видно на видах;
- путь к аргументам приёмки листа;
- строки журнала;
- строки F.

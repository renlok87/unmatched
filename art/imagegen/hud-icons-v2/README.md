# Значки HUD v2, волна 1

Дата: 2026-10-03. Статус: **ЗАМЕНЕНО v3** — пользователь отверг этот набор («нарисованы криво», «топорно»); актуальные
значки — [`../hud-icons-v3/`](../hud-icons-v3/README.md). Папка оставлена для истории и листа «было → стало».

Решения по каждому значку, правила языка значков (И-1..И-10) и задачи — в
[docs/unreal/contracts/hud/HUD-AND-ICONS.md](../../../docs/unreal/contracts/hud/HUD-AND-ICONS.md) (§1.9, §3.4).
Бриф для ImageGen — [IMAGEGEN-BRIEF-icons.md](../../../docs/unreal/contracts/hud/IMAGEGEN-BRIEF-icons.md).

## Как сделано

1. **ImageGen (Codex)** нарисовал 9 глиф-масок: белые плоские глифы на прозрачном фоне. Это `glyphs/*.png`,
   промпты лежат в `glyphs/prompts/`, попытки и хэши — в `glyphs/manifest.json`, нормализация Codex — в `glyphs/qa/`.
   Пометку «authorized_by_user» в `glyphs/manifest.json` и `qa/review-report.md` написал Codex. Отдельно
   нормализацию никто не утверждал: порог альфы, чистку краёв и вписывание в 768 px на холсте 1024 Codex сделал сам.
   Основная сессия проверила результат и приняла его.
2. **Скрипт** `_tools/compose_icons.py` собирает 23 итоговых значка и маску жетона цели. Он берёт маски, полигоны
   `tools/art/move_selection/card_icons.py` и щит из самого скрипта. Палитра — токены
   `docs/unreal/contracts/hud/hud-style-tokens.json` (`card.*`, `mark.keyline`, `state.error`, `zone.purple`,
   `icon.token.*`). Мастера 1024 px; плашки hint и threat — 2048×1024.
3. Проверка основной сессии: след ноги вернули Codex (вариант «подошва + каблук» при 24 px читался как «!»); принят
   вариант «два следа», 4-я попытка. Всего 18 генераций.
4. Цифры на значки не запекаются: «+N», порядок хода, число угроз и ранг подсказки игра рисует текстом.

Собрать заново:

```bash
python art/imagegen/hud-icons-v2/_tools/compose_icons.py
```

## Файлы

| Что | Где |
|---|---|
| Итоговые значки | `state-*.png` (8), `action-*.png` (5 + `action-attack-token-glyphmask.png`), `marker-status.png`, `loader-spinner.png`, `resource-*.png` (8) |
| Глиф-маски ImageGen | `glyphs/glyph-*.png` (9) |
| Исходные значки v2 для сравнения | `reference-v2/v2-<id>-256.png` (14, из `card_icons.py`) |
| Лист «было → стало» | `compare-sheet.png`: было, стало 128/32/24 px, 24 px на светлом, серый 128 и 24 px; пересборка — `python art/imagegen/hud-icons-v2/_tools/compare_icons.py` |
| Проверка в сером | `compare-gray-24px-x4.png`, `compare-gray-32px-x4.png` |
| Хэши и источники | `manifest.json` |

Ничто здесь не производное от сканов карт (ENV-U3): сканы служили только референсом стиля.

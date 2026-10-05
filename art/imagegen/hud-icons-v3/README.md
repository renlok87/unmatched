# Значки HUD v3 «Жетон-эмблема» на основе Unmatched: Digital Edition

Дата: 2026-10-03. Статус: **ПРЕДЛОЖЕНИЕ** до арт-приёмки пользователя (ART-011). Значки заменяют волну 1
(`../hud-icons-v2/`). Набор: 23 значка и маска, плюс четыре значка DE-012, принятые 2026-10-05; id и смысл по реестру
[HUD-AND-ICONS.md](../../../docs/unreal/contracts/hud/HUD-AND-ICONS.md) §3.4.

Спецификация стиля, правила, построение каждого значка, движение и правки после ревью —
[STYLE-v3.md](STYLE-v3.md). Основа — визуальный язык Unmatched: Digital Edition (решение пользователя). У неё взяты
идеи и приёмы, а не пиксели: каждый значок нарисован нашим векторным движком.

## Как сделано

1. **Концепция — workflow Fable xhigh.** Поштучный аудит v2, три направления с векторными прототипами и движением,
   судья. Победило направление «Жетон из коробки» с прививками двух других.
2. **Исследование Digital Edition.** Скриншоты и трейлер со страницы Steam, 18 текстовых источников.
3. **Сборка — второй workflow Fable xhigh.** Спецификация, движок, весь набор, независимое поштучное ревью, исправления.
4. **Поштучный осмотр основной сессией и восемь правок** (STYLE-v3 §10).

## Сборка

```bash
python art/imagegen/hud-icons-v3/_tools/draw_icons.py
```

Команда пересобирает `masters/`, `sizes/`, `layers/`, `sheets/`, `manifest.json` и `sheets/audit.json`. Остальные
инструменты:

- `python art/imagegen/hud-icons-v3/_tools/motion.py` — листы кадров и GIF в `sheets/motion/`;
- `python art/imagegen/hud-icons-v3/_tools/compare_v2_v3.py` — лист «было → стало»;
- `--review DIR` у `draw_icons.py` — листы на картах местности и рядом с кадрами Digital Edition. Их пишем только вне
  репозитория (ENV-U3).

## Файлы

| Что | Где |
|---|---|
| Мастера 1024 px (плашки 2048 × 1024), прозрачное поле ≥ 1 u | `masters/<id>.png` |
| Размеры из вектора с привязкой к пикселям | `sizes/<id>-{16,21,24,32,48,64,96}.png` |
| Слои для анимации (тело, глиф, блок команды) | `layers/<id>_{body,glyph,team}[-size].png` |
| Варианты того же id | `resource-hp-full-enemy` (чужое сердце), `marker-status-p1` / `-p2` (превью цвета команды) |
| Листы | `sheets/sheet-masters.png`, `sheet-sizes.png`, `sheet-context-panel.png`, `compare-v2-v3.png` |
| Движение (эталон контракта) | `sheets/motion/frames-*.png`, `*.gif`, `reel.mp4`, `index.html` |
| Метрики самопроверки | `sheets/audit.json`: поле, мусор по краю, симметрия, центроиды, масса глифа, швы |
| Хэши | `manifest.json` (sha1 мастеров, размеров и слоёв) |

Цифры (BOOST «+N», порядок хода, число угроз, ранг подсказки, HP) в текстуры не запекаются. Игра рисует их текстом
шрифтом Roboto Bold Condensed из движка UE 5.8. На листах цифры показаны только как образец.

Ничего здесь не производное от сканов карт, карт местности или кадров Digital Edition (ENV-U3). Они были только
референсом и фоном листов просмотра вне репозитория.

## Набор DE (DE-012): принят 2026-10-05

Пользователь принял набор DE 2026-10-05: ответ AB-5…AB-8 листа A/B DE-028, запись —
[01-decisions.md](../../../docs/game-design/de-footage/task/01-decisions.md). Принятые id в контракте — список
`accepted_de012`. Принятый арт — по умолчанию (AGENTS.md); включение в HUD — код HUD,
прогон I ([I-2026-10-05.md](../../../docs/game-design/de-footage/task/runs/I-2026-10-05.md)).

| id | Форма | Ответ |
|---|---|---|
| `marker-turn-ring` | v3 как есть: тёплая вспышка жёлтый → оранжевый → красный, тлеющий обод | AB-5 тёплое |
| `resource-hp-fallen` | Codex: почерневшее сердце (слой `heart`) + малый X (слой `cross`) | AB-8 |
| `marker-x-stamp` | Codex: компактный X | AB-8 |
| `marker-action-slot-de` | Codex: один оранжевый обод + серый диск-призрак | AB-7 трекер DE |
| слой `resource-hp-full_glow` | v3 как есть | AB-6 ореол вкл |

Формы Codex перенесены в `draw_icons.py` как принятые. Экспорт совпадает с
[`../hud-icons-de012-codex/vector-codex/`](../hud-icons-de012-codex/README.md) по альфе и цвету на 1024 / 32 / 24 / 16
px — это проверяет pytest `test_accepted_forms_match_codex_proposal`. Кандидатом остаётся только кольцо цвета команды
`marker-turn-ring-team` (список `candidates`, только галерея).

Всё рисует та же команда `draw_icons.py`. Лист набора — `sheets/de012/sheet-de012.png`; принятые id есть и на листах
`sheet-masters`, `sheet-sizes`, `sheet-context-panel`. `sheets/de012/sheet-candidates.png` — лист кандидатов до
приёмки (2026-10-04), генератор его больше не пишет. Принятые 23 значка не изменились побайтно. Построение и
поштучный осмотр — STYLE-v3 §11.

## Что не проверено

- В Slate и UMG: хинтинг Roboto Bold Condensed при 11–12 px, «+2» в диске, ширина ленты под «10», 9-slice.
- В реальной сцене клиента и мип-цепочке жетона цели.
- UI-материал песочных часов.
- Дальтонизм: проверен только серый.
- Экспорт `-light` для светлых панелей.

## Движение

План — [ICON-MOTION-PLAN.md](../../../docs/unreal/contracts/hud/ICON-MOTION-PLAN.md), раскадровка —
[ICON-MOTION.md](../../../docs/unreal/contracts/hud/ICON-MOTION.md).

| Что | Где |
|---|---|
| Контракт: слои, дорожки, ключи, удар, reduced motion | `docs/unreal/contracts/hud/icon-motion.json` (копия `unreal/Unmatched/Config/S08IconMotion.json`) |
| Генератор контракта и раскадровки | `_tools/motion_contract.py` |
| Вычислитель позы — эталон для C++ | `_tools/icon_motion.py`; позы для теста UE — `icon-motion-golden.json` |
| Эталонный рендер: листы, GIF, ролики, страница | `_tools/motion.py` → `sheets/motion/` (`index.html`, `reel.mp4`, `reel-reduced.mp4`) |
| Рантайм UE | `S08IconMotion.h`, `S08AnimatedIconWidget.h` (+ галерея `-S08IconGallery`) |
| UE против эталона | `_tools/compare_ue_gallery.py`, `docs/game-design/evidence/ICON-MOTION/2026-10-03/` |

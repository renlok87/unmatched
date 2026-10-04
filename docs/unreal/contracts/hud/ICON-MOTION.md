# Движение значков HUD v3: раскадровка

Сгенерировано из контракта [`icon-motion.json`](icon-motion.json) скриптом
`art/imagegen/hud-icons-v3/_tools/motion_contract.py` — не править руками. План и фазы —
[ICON-MOTION-PLAN.md](ICON-MOTION-PLAN.md). Ключи и модель позы — в шапке генератора и в `rules` контракта.
Исключение — ручной раздел в конце файла (ниже маркера `MANUAL_MARKER`): генератор переносит его без изменений.

Удар — момент события в цикле, на него позже вешается звук (±40 мс). Reduced motion — ветка `reduced`.

| Значок | Анимация | Вид | мс | Удар | Что двигается | Reduced motion |
|---|---|---|---|---|---|---|
| `state-boost` | appear | enter | 180 | — | all.opacity; all.scale — «кладут на стол»: 0,80 → 1,04 → 1,00; кадр 0 не пустой (opacity 0,15) | all.opacity 100 мс |
| `state-boost` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `state-boost` | tap | event | 150 | 50 | all.scale — смена числа на значке (цифру рисует игра): от текущего масштаба к 0,94 и обратно к нему же | статично |
| `state-boost` | reveal | event | 240 | 80 | all.scale_x — BOOST вскрыт: «переворот монеты» по X — схлопнулся ребром (удар 80) и раскрылся с перелётом | all.opacity 100 мс |
| `state-enemy` | appear | enter | 180 | 140 | all.opacity; all.scale; glyph.ty — фигурку ставят на клетку: глиф падает 2 u, «тук» при 140 | all.opacity 100 мс |
| `state-enemy` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `state-enemy` | tap | event | 150 | 50 | all.scale — смена числа на значке (цифру рисует игра): от текущего масштаба к 0,94 и обратно к нему же | статично |
| `state-sent` | appear | enter | 180 | — | all.opacity; all.scale — «кладут на стол»: 0,80 → 1,04 → 1,00; кадр 0 не пустой (opacity 0,15) | all.opacity 100 мс |
| `state-sent` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `state-sent` | cycle | loop | 1500 | 650 | glyph.frame; glyph.rotate — песок пересыпается (кадры 0–6, 550 мс), переворот 650–950 (удар 650), песок снова сверху (кадры 7–11) | статично |
| `state-pending-move` | appear | enter | 180 | — | all.opacity; all.scale — «кладут на стол»: 0,80 → 1,04 → 1,00; кадр 0 не пустой (opacity 0,15) | all.opacity 100 мс |
| `state-pending-move` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `state-pending-move` | cycle | loop | 1200 | 520 | glyph.scale — стрелки втягиваются и «щёлкают» наружу (удар 520) | статично |
| `state-pending-place` | appear | enter | 180 | — | all.opacity; all.scale — «кладут на стол»: 0,80 → 1,04 → 1,00; кадр 0 не пустой (opacity 0,15) | all.opacity 100 мс |
| `state-pending-place` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `state-pending-place` | cycle | loop | 1200 | 600 | arrow.ty — стрелка подпрыгивает и опускается на клетку («тук» 600) | статично |
| `state-hint` | appear | enter | 260 | 200 | all.opacity; all.scale_x; glyph.scale — плашка растёт слева (scaleX 0,5 → 1), лампа «загорается» импульсом; каскад по рангу 0 / 60 / 120 мс (stagger_ms задаёт игра) | all.opacity 100 мс |
| `state-hint` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `state-hint` | tap | event | 150 | 50 | all.scale — смена числа на значке (цифру рисует игра): от текущего масштаба к 0,94 и обратно к нему же | статично |
| `state-threat` | appear | enter | 200 | — | all.opacity; all.scale_x — плашка растёт слева; глаз не моргает | all.opacity 100 мс |
| `state-threat` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `state-threat` | tap | event | 150 | 50 | all.scale — смена числа на значке (цифру рисует игра): от текущего масштаба к 0,94 и обратно к нему же | статично |
| `state-threat` | rise | event | 220 | 60 | all.scale; glyph.scale — угроз стало больше: глаз «вглядывается» | статично |
| `state-immobilized` | appear | enter | 260 | 160 | all.opacity; all.scale; glyph.ty — «бросили якорь»: глиф падает 3 u, удар 160, плашка вздрагивает | all.opacity 100 мс |
| `state-immobilized` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `state-immobilized` | tap | event | 150 | 50 | all.scale — смена числа на значке (цифру рисует игра): от текущего масштаба к 0,94 и обратно к нему же | статично |
| `action-attack` | appear | enter | 180 | — | all.opacity; all.scale — «кладут на стол»: 0,80 → 1,04 → 1,00; кадр 0 не пустой (opacity 0,15) | all.opacity 100 мс |
| `action-attack` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `action-attack` | hover_in | event (hold) | 150 | — | all.scale — наведение: 1,06 | статично |
| `action-attack` | hover_out | event (hold) | 150 | — | all.scale — уход курсора: 1,00 | статично |
| `action-attack` | press | event (hold) | 80 | — | all.scale — нажатие: 0,96 | статично |
| `action-attack` | release | event (hold) | 80 | — | all.scale — отпускание: обратно к 1,06 | статично |
| `action-attack` | select | event | 200 | 70 | glyph.scale — действие выбрано: импульс глифа от текущего масштаба и обратно | статично |
| `action-attack` | spend | event (hold) | 150 | — | all.opacity — действие потрачено: opacity 0,4 (02:895) | all.opacity 100 мс |
| `action-attack` | restore | event (hold) | 150 | — | all.opacity — действие снова доступно | all.opacity 100 мс |
| `action-attack` | tap | event | 150 | 50 | all.scale — смена числа на значке (цифру рисует игра): от текущего масштаба к 0,94 и обратно к нему же | статично |
| `action-attack-token` | appear | enter | 220 | 140 | all.opacity; all.scale — жетон цели кладут на бойца сверху: 1,25 → 0,96 → 1,00, удар 140 | all.opacity 100 мс |
| `action-attack-token` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `action-attack-token` | cycle | loop | 1000 | 0 | all.scale — пульс цели 1 Гц (03 §6); reduced motion — без пульса | статично |
| `action-defense` | appear | enter | 180 | — | all.opacity; all.scale — «кладут на стол»: 0,80 → 1,04 → 1,00; кадр 0 не пустой (opacity 0,15) | all.opacity 100 мс |
| `action-defense` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `action-defense` | hover_in | event (hold) | 150 | — | all.scale — наведение: 1,06 | статично |
| `action-defense` | hover_out | event (hold) | 150 | — | all.scale — уход курсора: 1,00 | статично |
| `action-defense` | press | event (hold) | 80 | — | all.scale — нажатие: 0,96 | статично |
| `action-defense` | release | event (hold) | 80 | — | all.scale — отпускание: обратно к 1,06 | статично |
| `action-defense` | select | event | 200 | 70 | glyph.scale — действие выбрано: импульс глифа от текущего масштаба и обратно | статично |
| `action-defense` | spend | event (hold) | 150 | — | all.opacity — действие потрачено: opacity 0,4 (02:895) | all.opacity 100 мс |
| `action-defense` | restore | event (hold) | 150 | — | all.opacity — действие снова доступно | all.opacity 100 мс |
| `action-defense` | tap | event | 150 | 50 | all.scale — смена числа на значке (цифру рисует игра): от текущего масштаба к 0,94 и обратно к нему же | статично |
| `action-maneuver` | appear | enter | 180 | — | all.opacity; all.scale — «кладут на стол»: 0,80 → 1,04 → 1,00; кадр 0 не пустой (opacity 0,15) | all.opacity 100 мс |
| `action-maneuver` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `action-maneuver` | hover_in | event (hold) | 150 | — | all.scale — наведение: 1,06 | статично |
| `action-maneuver` | hover_out | event (hold) | 150 | — | all.scale — уход курсора: 1,00 | статично |
| `action-maneuver` | press | event (hold) | 80 | — | all.scale — нажатие: 0,96 | статично |
| `action-maneuver` | release | event (hold) | 80 | — | all.scale — отпускание: обратно к 1,06 | статично |
| `action-maneuver` | select | event | 200 | 70 | glyph.scale — действие выбрано: импульс глифа от текущего масштаба и обратно | статично |
| `action-maneuver` | spend | event (hold) | 150 | — | all.opacity — действие потрачено: opacity 0,4 (02:895) | all.opacity 100 мс |
| `action-maneuver` | restore | event (hold) | 150 | — | all.opacity — действие снова доступно | all.opacity 100 мс |
| `action-maneuver` | tap | event | 150 | 50 | all.scale — смена числа на значке (цифру рисует игра): от текущего масштаба к 0,94 и обратно к нему же | статично |
| `action-scheme` | appear | enter | 180 | — | all.opacity; all.scale — «кладут на стол»: 0,80 → 1,04 → 1,00; кадр 0 не пустой (opacity 0,15) | all.opacity 100 мс |
| `action-scheme` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `action-scheme` | hover_in | event (hold) | 150 | — | all.scale — наведение: 1,06 | статично |
| `action-scheme` | hover_out | event (hold) | 150 | — | all.scale — уход курсора: 1,00 | статично |
| `action-scheme` | press | event (hold) | 80 | — | all.scale — нажатие: 0,96 | статично |
| `action-scheme` | release | event (hold) | 80 | — | all.scale — отпускание: обратно к 1,06 | статично |
| `action-scheme` | select | event | 200 | 70 | glyph.scale — действие выбрано: импульс глифа от текущего масштаба и обратно | статично |
| `action-scheme` | spend | event (hold) | 150 | — | all.opacity — действие потрачено: opacity 0,4 (02:895) | all.opacity 100 мс |
| `action-scheme` | restore | event (hold) | 150 | — | all.opacity — действие снова доступно | all.opacity 100 мс |
| `action-scheme` | tap | event | 150 | 50 | all.scale — смена числа на значке (цифру рисует игра): от текущего масштаба к 0,94 и обратно к нему же | статично |
| `marker-status` | appear | enter | 220 | — | all.opacity; all.scale_y — лента разворачивается сверху вниз | all.opacity 100 мс |
| `marker-status` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `marker-status` | tap | event | 150 | 50 | all.scale — смена числа на значке (цифру рисует игра): от текущего масштаба к 0,94 и обратно к нему же | статично |
| `loader-spinner` | appear | enter | 150 | — | all.opacity — кроссфейд без масштаба (связь, спиннер) | all.opacity 100 мс |
| `loader-spinner` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `loader-spinner` | cycle | loop | 1000 | 0 | all.rotate — 8 ступеней по 45° (125 мс), без промежуточных кадров; reduced — ступени по 250 мс (индикатор прогресса оставлен) | all.rotate 2000 мс |
| `resource-action-full` | appear | enter | 180 | — | all.opacity; all.scale — «кладут на стол»: 0,80 → 1,04 → 1,00; кадр 0 не пустой (opacity 0,15) | all.opacity 100 мс |
| `resource-action-full` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `resource-action-full` | tap | event | 150 | 50 | all.scale — смена числа на значке (цифру рисует игра): от текущего масштаба к 0,94 и обратно к нему же | статично |
| `resource-action-full` | spend | event (hold) | 150 | 0 | icon.opacity; icon.scale; under.opacity — очко потрачено: светлый ромб гаснет поверх пустого (дальше игра ставит resource-action-empty) | icon.opacity; under.opacity 100 мс |
| `resource-action-full` | gain | event | 180 | 120 | icon.opacity; icon.scale; under.opacity — очко вернулось (новый ход) | icon.opacity 100 мс |
| `resource-action-empty` | appear | enter | 150 | — | all.opacity — кроссфейд без масштаба (связь, спиннер) | all.opacity 100 мс |
| `resource-action-empty` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `resource-card` | appear | enter | 180 | — | all.opacity; all.scale — «кладут на стол»: 0,80 → 1,04 → 1,00; кадр 0 не пустой (opacity 0,15) | all.opacity 100 мс |
| `resource-card` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `resource-card` | tap | event | 150 | 50 | all.scale — смена числа на значке (цифру рисует игра): от текущего масштаба к 0,94 и обратно к нему же | статично |
| `resource-card` | draw | event | 180 | 180 | all.scale; all.ty — добор карты: стопка «падает» на место, удар — приземление 180 | статично |
| `resource-connection-online` | appear | enter | 150 | — | all.opacity — кроссфейд без масштаба (связь, спиннер) | all.opacity 100 мс |
| `resource-connection-online` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `resource-connection-reconnecting` | appear | enter | 150 | — | all.opacity — кроссфейд без масштаба (связь, спиннер) | all.opacity 100 мс |
| `resource-connection-reconnecting` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `resource-connection-reconnecting` | cycle | loop | 1200 | 0 | sign.rotate — круговая стрелка вращается, столбики стоят | статично |
| `resource-connection-lost` | appear | enter | 180 | 110 | bars.opacity; sign.scale — связи нет с самого начала: приглушённые столбики проявляются, красный X «штампуется» (удар 110) | bars.opacity; sign.opacity 100 мс |
| `resource-connection-lost` | appear_from_online | enter | 180 | 110 | bars.opacity; bars.tx; from.opacity; from.tx; sign.scale — связь пропала во время игры (вместо online): столбики online уезжают вправо (3,75 u) на место приглушённых и гаснут, X «штампуется», без мигания | bars.opacity; from.opacity; sign.opacity 100 мс |
| `resource-connection-lost` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `resource-hp-full` | appear | enter | 180 | — | all.opacity; all.scale — «кладут на стол»: 0,80 → 1,04 → 1,00; кадр 0 не пустой (opacity 0,15) | all.opacity 100 мс |
| `resource-hp-full` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `resource-hp-full` | tap | event | 150 | 50 | all.scale — смена числа на значке (цифру рисует игра): от текущего масштаба к 0,94 и обратно к нему же | статично |
| `resource-hp-full` | damage | event | 200 | 60 | all.scale; all.tx — урон: сердце вздрагивает, число меняет игра; reduced — без движения | статично |
| `resource-hp-full` | deplete | event (hold) | 200 | 60 | icon.opacity; icon.scale; under.opacity — пип здоровья потерян: полное сердце 1 → 1,15 → 0 поверх пустого (hp_hit) | icon.opacity; under.opacity 100 мс |
| `resource-hp-full` | heal | event | 180 | 120 | icon.opacity; icon.scale; under.opacity — лечение: сердце наполняется | icon.opacity 100 мс |
| `resource-hp-empty` | appear | enter | 150 | — | all.opacity — кроссфейд без масштаба (связь, спиннер) | all.opacity 100 мс |
| `resource-hp-empty` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |

Варианты того же id играют анимации основного значка: `resource-hp-full-enemy` → `resource-hp-full`, `marker-status-p1` → `marker-status`, `marker-status-p2` → `marker-status`.

<!-- ручной раздел: motion_contract.py сохраняет всё ниже этой строки -->

## Запланированные записи набора DE (W-05, 2026-10-04): ещё не в контракте

Здесь — новые и изменённые записи движения из живой сверки с DE 2.2.1. Источник:
- дельты SD-34…SD-38 ([02-spec-deltas.md](../../../game-design/de-footage/task/02-spec-deltas.md), блок F и «Живая
  сверка блока F»);
- окончательные решения F-07, F-09, F-12 и «Резолюция ревью Fable High», пп. 6 и 9
  ([01-decisions.md](../../../game-design/de-footage/task/01-decisions.md)).

Это норматив для W-15 (DE-012). В W-05 (DE-007) правится только этот документ; `icon-motion.json` и
`Config/S08IconMotion.json` не тронуты, поэтому таблица выше этих записей не содержит. DE-012 вносит записи в контракт
генератором `motion_contract.py`, рисует глифы в `_tools/draw_icons.py`, вносит id в реестр
[HUD-AND-ICONS.md](HUD-AND-ICONS.md) и удаляет из этого раздела то, что попало в контракт.

**Общие правила записей:**
- Числа берутся из 01, а не из DE напрямую. Основание:
  - TL — строка `live-2026-10-04/timings-live.csv` (`event_type`, таймкод `sNN t`);
  - YT — строка `timings.csv` (разбор YouTube 2.1.0).
- У каждой записи есть ветка reduced: только opacity ≤ 100 мс или статика (`rules.reduced`, тест
  `test_reduced_motion_is_opacity_only_and_short`). `enter` кончается позой покоя (тест `test_appear_ends_at_master_pose`).
- Скорость анимации (02 UI-ACC-013) движение значков не масштабирует. Для кольца хода это прямо записано в UI-ACC-013.
- Вид новых глифов и цвета — арт-приёмка пользователя (DE-012). До неё новые глифы не включаются по умолчанию.
  Вариант DE трекера — только в галерее `-S08IconGallery`. Принятый набор v3 остаётся по умолчанию.
- Id ниже — рабочие. Окончательные id даёт реестр HUD-AND-ICONS.md в DE-012.
- Длящиеся анимации (кольцо, трекер) живут только на постоянном UMG-виджете или `US08AnimatedIconWidget`, а не на
  Slate-виджетах, которые `RefreshHud` пересоздаёт на каждое событие (02 §4.3 п. 4; реализация — DE-022, DE-023).
- Бюджет `rules.budget` (≤ 3 одновременно циклящих значка в кадре) не меняется. Кольцо хода цикла не имеет. Пульс слота
  трекера циклится только в галерее.

### 1. Кольцо хода: `marker-turn-ring` (новый значок; SD-34; по умолчанию, D-DE-07)

Кольцо стоит у портрета активного игрока у обеих сторон: свой ход и ход соперника. Это обод целиком, а не прорисовка по
кругу. Решение — 01 F-07 и «Резолюция» п. 6: вспышка 1000 мс (было ~900), затем тлеющее кольцо (opacity ≈ 0,35, без
искр) до конца хода. Ввод не блокирует. Баннер «Ваш ход» — отдельно, CUE-015.

Слои (рабочие):
- `rim` — тлеющий обод вокруг рамки портрета, покой opacity 0,35;
- `flash` — яркий обод вспышки, флипбук цвета жёлтый → оранжевый → красный, покой opacity 0.

Холст — рамка портрета UI-HUD-PANEL, а не 32 u.

| Значок | Анимация | Вид | мс | Удар | Что двигается | Reduced motion |
|---|---|---|---|---|---|---|
| `marker-turn-ring` | appear | enter | 1000 | 0 | flash.opacity 0 → 1 (0–120) → 0 (1000); flash.frame — жёлтый → оранжевый → красный за 1000; rim.opacity 0 → 0,35 к 1000 — старт хода стороны (CUE-015), смена кольца ≤ 1 кадр от снапшота | rim.opacity 100 мс (статичное кольцо 0,35, без вспышки) |
| `marker-turn-ring` | (покой) | — | — | — | rim 0,35 до конца хода; цикла и искр нет | то же |
| `marker-turn-ring` | leave | exit | 120 | — | all.opacity → 0 без масштаба — ход перешёл к другой стороне | all.opacity 100 мс |

- **Удар 0** — точка звука: перезвон хода только на свой ход, ход соперника без звука (07 CUE-015 `sound`, SD-51 п. 4).
- **Цвет.** Порядок и длительность вспышки — из 01 F-07. Тона жёлтый / оранжевый / красный — тёплые тона палитры
  карт, не `state.error`, поэтому правило STYLE-v3 §1.7 («красный `state.error` — только знак X») не нарушается.
  Точные тона и вариант «обод цветом команды С-11» (STYLE-v3 §5.1 «ж») показываются карточками галереи на арт-приёмке
  DE-012.
- **Основание.**
  - TL `turn_start_ring_own`: 1080 мс, n=5 (s02 162.367), и 983 мс (s04 647.967). Вспышка жёлтый → оранжевый →
    красный, затем тлеющее кольцо — S4HV-M07, medium.
  - TL `turn_start_ring_ai`: 950 мс (s02 340.967).
  - TL `end_turn_to_ai_ring`: 150 мс (s04 1141.100).
  - YT `turn_start_portrait_ring`: 885, n=12. Здесь «обвод по кругу», живьём не подтверждён (R-01 (live 2026-10-04)).
- **Не переносим блокировку ввода DE.** У DE ввод открывается только через 1,85–1,95 с после старта кольца
  (TL `turn_start_ring_to_prompt`); у нас ввод открыт сразу (01 F-07, MS-R-79).

### 2. Сердце: урон, `resource-hp-full` damage (изменение записи; SD-35; делегировано)

Сейчас запись длится 200 мс с ударом 60: вздрагивание (all.scale, all.tx); reduced — статично.

Станет 1000 мс:
- 0–200 — то же вздрагивание, удар 60;
- 200–1000 — вспышка и один пульс свечения на новом слое `glow`: glow.opacity 0 (200) → 1 (320) → 0,45 (560) → 0,85
  (760) → 0 (1000).

Свойства:
- reduced — без изменений, статично (SD-35);
- событие не `hold`;
- вариант `resource-hp-full-enemy` играет ту же запись;
- число меняет игра на +80 мс от кадра контакта (07 CUE-011, 01 F-04).

Основание:
- длина 1000 — верх диапазона 600–1000 мс из SD-35, ближе всего к данным DE;
- YT `hp_heart_glow` 1030 мс, n=5;
- живьём при нелетальном уроне не перемерено (R-05 (live 2026-10-04): «частично», WF1 AU-M17).

### 3. Павший: `resource-hp-fallen` (новый значок; SD-38; делегировано, вид — арт-приёмка)

Перечёркнутое сердце на плашке павшего бойца: контур `resource-hp-empty` плюс крест — знак X цвета `state.error`, тот
же глиф, что в п. 4 (правило v3 «красный только у X»). Одна схема для героя и помощника (01 F-09).

Слои (рабочие): `heart` — контур `resource-hp-empty`, `cross` — X.

| Значок | Анимация | Вид | мс | Удар | Что двигается | Reduced motion |
|---|---|---|---|---|---|---|
| `resource-hp-fallen` | appear | enter | 200 | 120 | cross.scale 0 → 1,08 (120) → 1,00 (200); heart без движения — крест «штампуется» на пустое сердце; игра запускает на +1100 мс от кадра контакта | cross.opacity 100 мс |
| `resource-hp-fallen` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 (только при новой партии) | all.opacity 100 мс |

Порядок от кадра контакта (01 F-09, 07 CUE-011 и CUE-013):
- HP меняется на +80;
- последний пип играет уже существующий `resource-hp-full` deplete: 200 мс, удар 60, то есть сердце пустеет к ≈ +140;
- на +1100 — `resource-hp-fallen` appear.

Плашка не исчезает. На экране результата в режиме «посмотреть доску» павший отмечен тем же значком (02 §2.9, §4.3 п. 3).

Основание: TL `death_hero_hit_to_heart_cross` 1083 мс (s05 923.017); сердце чернеет уже на +133 (S5V-LR-HEART). У
жетона-гарпии DE крест появляется ~0,7 с после контакта (S5-HA-1), но 01 F-09 задаёт +1100 для всех фигур, R-07 (live
2026-10-04).

### 4. Крест-штамп: `marker-x-stamp` (новый значок; SD-37; делегировано)

Красный крест «нет защиты / отменено». Глиф — X цвета `state.error`, как знак в `resource-connection-lost` (STYLE-v3
§1.7 и §5.1 «в»: отказ или конфликт получают тот же X). Движение — по образцу штампа `resource-connection-lost` appear,
растянутое до 200 мс.

| Значок | Анимация | Вид | мс | Удар | Что двигается | Reduced motion |
|---|---|---|---|---|---|---|
| `marker-x-stamp` | appear | enter | 200 | 120 | all.opacity 0,15 → 1 (0–150); sign.scale 0 → 1,08 (120) → 1,00 (200) — штамп | all.opacity 100 мс |
| `marker-x-stamp` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 (бой закрыт, CUE-016) | all.opacity 100 мс |

Где ставится:
- (а) «нет защиты» — в слоте защиты, вместе с переворотом атакующей карты: 07 CUE-009, 02 §4.5 «Слот защиты»;
  TL `defense_check_to_reveal` — 600 мс от исчезновения галочки до креста и переворота (s04 302.300);
- (б) «отменено» — на карте, чей эффект отменён (s04 combat3, Feint).

Почему 200 мс и без масштаба скоростью (R-04 (live 2026-10-04)):
- YT `no_defense_x_stamp` 200 мс, n=5 — это удар штампа;
- у DE штамп масштабируется скоростью: 699 → 316 мс при 4x (WF1 AU-O01). Но 699 — время до покоя, а не удар;
- поэтому у нас удар 200, скоростью не масштабируется.

### 5. Трекер действий (SD-36; D-DE-12, 01 F-12, «Резолюция» п. 9)

**Вид по умолчанию — v3 без изменений:**
- `action-*` spend = opacity 0,4 за 150 мс, `restore` — обратно (таблица выше);
- `resource-action-full` spend / gain — без изменений.

Меняется только поведение: какие события игра посылает и когда.

| Событие игры | Что играет | Когда | Основание |
|---|---|---|---|
| Выбор действия, до Confirm | `action-<тип>` spend (150 мс, hold) | в кадре выбора, а не по Confirm | TL `tracker_slot_fill` s04 635.283 (DE заливает слот в момент выбора) |
| Undo / отмена выбора | `action-<тип>` restore (150 мс) | в кадре отмены | 01 F-12 |
| End Turn / смена хода | сброс — поза покоя за 1 кадр, без `restore` 150 | ≤ 1 кадр от снапшота | TL `tracker_reset` 33 мс (s04 1141.133) |
| Начало хода соперника | контейнер трекера соперника: opacity 0 → 1 за 150 мс, без масштаба (уровень UMG, не запись значка); reduced — opacity 100 мс | в кадре снапшота смены хода | TL `tracker_ai_appear` 133–217 мс (s04 634.117) |
| Начало моего хода | трекер соперника скрыт за 1 кадр | в кадре снапшота | s04 647.900 |
| Свой трекер | виден всегда | — | 01 F-12 |

**Вариант DE — только галерея `-S08IconGallery`** для A/B на арт-приёмке DE-012. По умолчанию не включается.

| Значок | Анимация | Вид | мс | Удар | Что двигается | Reduced motion |
|---|---|---|---|---|---|---|
| `action-*` (вариант DE) | fill | event (hold) | 300 | 200 | all.opacity 0,4 → 1; glyph.scale 0,80 → 1,04 (200) → 1,00 — «потрачено = заполнено значком типа» вместо «погасло» | all.opacity 100 мс |
| слот трекера (вариант DE) | slot_pulse | loop | 770 | 0 | ring.scale 1,00 → 1,06 → 1,00; ring.opacity 0,6 → 1 → 0,6 — пульс текущего слота, пока выбирается действие (кольцо-призрак) | статично (обводка без пульса) |

Основание варианта:
- TL `tracker_slot_fill` 300 мс (s04, n=2) и 330–400 (s02);
- TL `tracker_pulse_period` 770 мс (s03 100–104.2, n=6).

### Что не меняется и что осталось

- `icon-motion.json` и `Config/S08IconMotion.json` не тронуты: они меняются в W-15 (DE-012) через генератор.
- 07 CUE-009, CUE-011, CUE-013, CUE-015 и 02 §4.3 пп. 1–4 уже синхронизированы (DE-003, DE-005). Записи выше согласованы
  с ними по числам.
- **Устаревшая ссылка.** Пометки «(02:895)» в сгенерированной таблице указывают на старую строку
  `02-ux-ui-spec.md`. Сейчас это §8 UI-ICON-ACTION, строка ≈ 994. Пометка живёт в `note` контракта, поэтому исправляется
  в DE-012 вместе с перегенерацией.

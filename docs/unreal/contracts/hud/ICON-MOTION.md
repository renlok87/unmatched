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
| `action-attack` | spend | event (hold) | 150 | — | all.opacity — действие потрачено: opacity 0,4 (02 §8 UI-ICON-ACTION) | all.opacity 100 мс |
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
| `action-defense` | spend | event (hold) | 150 | — | all.opacity — действие потрачено: opacity 0,4 (02 §8 UI-ICON-ACTION) | all.opacity 100 мс |
| `action-defense` | restore | event (hold) | 150 | — | all.opacity — действие снова доступно | all.opacity 100 мс |
| `action-defense` | tap | event | 150 | 50 | all.scale — смена числа на значке (цифру рисует игра): от текущего масштаба к 0,94 и обратно к нему же | статично |
| `action-maneuver` | appear | enter | 180 | — | all.opacity; all.scale — «кладут на стол»: 0,80 → 1,04 → 1,00; кадр 0 не пустой (opacity 0,15) | all.opacity 100 мс |
| `action-maneuver` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `action-maneuver` | hover_in | event (hold) | 150 | — | all.scale — наведение: 1,06 | статично |
| `action-maneuver` | hover_out | event (hold) | 150 | — | all.scale — уход курсора: 1,00 | статично |
| `action-maneuver` | press | event (hold) | 80 | — | all.scale — нажатие: 0,96 | статично |
| `action-maneuver` | release | event (hold) | 80 | — | all.scale — отпускание: обратно к 1,06 | статично |
| `action-maneuver` | select | event | 200 | 70 | glyph.scale — действие выбрано: импульс глифа от текущего масштаба и обратно | статично |
| `action-maneuver` | spend | event (hold) | 150 | — | all.opacity — действие потрачено: opacity 0,4 (02 §8 UI-ICON-ACTION) | all.opacity 100 мс |
| `action-maneuver` | restore | event (hold) | 150 | — | all.opacity — действие снова доступно | all.opacity 100 мс |
| `action-maneuver` | tap | event | 150 | 50 | all.scale — смена числа на значке (цифру рисует игра): от текущего масштаба к 0,94 и обратно к нему же | статично |
| `action-scheme` | appear | enter | 180 | — | all.opacity; all.scale — «кладут на стол»: 0,80 → 1,04 → 1,00; кадр 0 не пустой (opacity 0,15) | all.opacity 100 мс |
| `action-scheme` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `action-scheme` | hover_in | event (hold) | 150 | — | all.scale — наведение: 1,06 | статично |
| `action-scheme` | hover_out | event (hold) | 150 | — | all.scale — уход курсора: 1,00 | статично |
| `action-scheme` | press | event (hold) | 80 | — | all.scale — нажатие: 0,96 | статично |
| `action-scheme` | release | event (hold) | 80 | — | all.scale — отпускание: обратно к 1,06 | статично |
| `action-scheme` | select | event | 200 | 70 | glyph.scale — действие выбрано: импульс глифа от текущего масштаба и обратно | статично |
| `action-scheme` | spend | event (hold) | 150 | — | all.opacity — действие потрачено: opacity 0,4 (02 §8 UI-ICON-ACTION) | all.opacity 100 мс |
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
| `resource-hp-full` | damage | event | 1000 | 60 | all.scale; all.tx; glow.opacity — урон (SD-35, DE-012): 0–200 сердце вздрагивает (удар 60), 200–1000 вспышка и один пульс ореола glow (вид — кандидат до арт-приёмки); число меняет игра на +80 от контакта; reduced — без движения | статично |
| `resource-hp-full` | deplete | event (hold) | 200 | 60 | icon.opacity; icon.scale; under.opacity — пип здоровья потерян: полное сердце 1 → 1,15 → 0 поверх пустого (hp_hit) | icon.opacity; under.opacity 100 мс |
| `resource-hp-full` | heal | event | 180 | 120 | icon.opacity; icon.scale; under.opacity — лечение: сердце наполняется | icon.opacity 100 мс |
| `resource-hp-empty` | appear | enter | 150 | — | all.opacity — кроссфейд без масштаба (связь, спиннер) | all.opacity 100 мс |
| `resource-hp-empty` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `marker-turn-ring` | appear | enter | 1000 | 0 | flash.frame; flash.opacity; rim.opacity — старт хода стороны (CUE-015, 01 F-07): обод целиком вспыхивает жёлтый → оранжевый → красный за 1000 мс и гаснет в тлеющее кольцо 0,35 до конца хода; ввод не блокирует; reduced — статичное кольцо 0,35 | rim.opacity 100 мс |
| `marker-turn-ring` | leave | exit | 120 | — | all.opacity — ход перешёл к другой стороне: opacity → 0 без масштаба | all.opacity 100 мс |
| `marker-turn-ring-team` | appear | enter | 1000 | 0 | flash.opacity; rim.opacity — старт хода стороны (CUE-015, 01 F-07): обод целиком вспыхивает цветом команды С-11 за 1000 мс и гаснет в тлеющее кольцо 0,35 до конца хода; ввод не блокирует; reduced — статичное кольцо 0,35 | rim.opacity 100 мс |
| `marker-turn-ring-team` | leave | exit | 120 | — | all.opacity — ход перешёл к другой стороне: opacity → 0 без масштаба | all.opacity 100 мс |
| `resource-hp-fallen` | appear | enter | 200 | 120 | cross.scale — павший (SD-38): крест «штампуется» на пустое сердце, сердце неподвижно; игра запускает на +1100 от кадра контакта (01 F-09) | cross.opacity 100 мс |
| `resource-hp-fallen` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `marker-x-stamp` | appear | enter | 200 | 120 | all.opacity; sign.scale — крест-штамп (SD-37): «нет защиты» (CUE-009) / «отменено»; удар скоростью анимации не масштабируется | all.opacity 100 мс |
| `marker-x-stamp` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `marker-action-slot-de` | appear | enter | 180 | — | all.opacity; all.scale — «кладут на стол»: 0,80 → 1,04 → 1,00; кадр 0 не пустой (opacity 0,15) | all.opacity 100 мс |
| `marker-action-slot-de` | leave | exit | 120 | — | all.opacity; all.scale — opacity → 0, scale → 0,92 | all.opacity 100 мс |
| `marker-action-slot-de` | slot_pulse | loop | 770 | 0 | ring.opacity; ring.scale — вариант DE (01 F-12, только галерея): пульс текущего слота, пока выбирается действие; reduced — обводка без пульса | статично |
| `marker-action-slot-de` | fill | event (hold) | 300 | 200 | body.opacity; glyph.opacity; glyph.scale; ring.opacity — вариант DE: «потрачено = заполнено значком типа» 0,4 → 1 за 300 мс в момент выбора (слои action-<тип>; в галерее атака) | body.opacity; glyph.opacity; ring.opacity 100 мс |
| `marker-action-slot-de` | unfill | event (hold) | 150 | — | body.opacity; glyph.opacity; ring.opacity — вариант DE: Undo — слот снова пуст (01 F-12) | body.opacity; glyph.opacity; ring.opacity 100 мс |

Варианты того же id играют анимации основного значка: `resource-hp-full-enemy` → `resource-hp-full`, `marker-status-p1` → `marker-status`, `marker-status-p2` → `marker-status`.

<!-- ручной раздел: motion_contract.py сохраняет всё ниже этой строки -->

## Записи набора DE (DE-012, 2026-10-04): в контракте как кандидаты

Записи из живой сверки с DE 2.2.1 внесены в контракт ревизии `icon-motion-2026-10-04` генератором
`motion_contract.py` (DE-012; было запланировано в W-05 / DE-007). Числа — из окончательных решений F-07, F-09, F-12 и
«Резолюции ревью Fable High», пп. 6 и 9 ([01-decisions.md](../../../game-design/de-footage/task/01-decisions.md)), и
дельт SD-34…SD-38 ([02-spec-deltas.md](../../../game-design/de-footage/task/02-spec-deltas.md)). Таблица выше их
содержит, здесь — только то, чего в ней не видно.

**Кандидаты до арт-приёмки пользователя.** Новые id перечислены в `candidates` контракта:
`marker-turn-ring`, `marker-turn-ring-team`, `resource-hp-fallen`, `marker-x-stamp`, `marker-action-slot-de`.
- Они играют только в галерее `-S08IconGallery`. HUD их не использует: pytest `test_candidates_are_gallery_only`
  проверяет, что их id нет в коде UE вне автотестов.
- Вид — арт-приёмка пользователя: поштучно на 1024 px и на 16 / 24 / 32 px, лист
  `art/imagegen/hud-icons-v3/sheets/de012/sheet-candidates.png`. До неё принятый набор v3 остаётся по умолчанию.
- Подключение к HUD — DE-023 (кольцо, сердце, трекер), DE-019 (крест павшего) и задача слота защиты (CUE-009), после
  приёмки.
- **DE-023 (2026-10-05) подключил к HUD только принятые значки** (портрет `US08TurnPortraitWidget`): `resource-hp-full`
  (damage без слоя `glow`), `resource-action-full` (трекер). Кандидаты — только опциями A/B для листа DE-028:
  `-S08TurnRingIcon=<id>` (кольцо: `marker-turn-ring` или `marker-turn-ring-team`; id приходит с командной строки, в
  коде клиента его нет) и `-S08HeartGlow` (ореол сердца). После приёмки кольцо включается одной строкой — значением
  по умолчанию `FS08TurnHudLook::RingIcon`.

| Запись | Что в контракте | Основание |
|---|---|---|
| `marker-turn-ring` appear | вспышка `flash` 1000 мс, флипбук 7 кадров жёлтый → оранжевый → красный, затем тлеющий обод `rim` 0,35 до конца хода; удар 0 — точка звука хода (только свой ход, SD-51 п. 4); reduced — статичный обод 0,35 за 100 мс; цикла и искр нет; leave 120 мс без масштаба | 01 F-07; TL `turn_start_ring_own` 983–1080 мс, `turn_start_ring_ai` 950 мс |
| `marker-turn-ring-team` | тот же обод, `rim` и `flash` белые с `tint: team` — вариант «обод цветом команды С-11» (STYLE-v3 §5.1 «ж») для A/B | 01 F-07 (тона — арт-приёмка) |
| `resource-hp-full` damage | 1000 мс: 0–200 прежнее вздрагивание (удар 60), 200–1000 вспышка и пульс нового слоя `glow` (0 → 1 → 0,45 → 0,85 → 0); reduced — статично | SD-35; YT `hp_heart_glow` 1030 мс |
| `resource-hp-fallen` appear | крест `cross` 0 → 1,08 (120) → 1,00 (200) на неподвижное пустое сердце (`heart` = текстура `resource-hp-empty`); игра запускает на +1100 от кадра контакта | SD-38, 01 F-09; TL `death_hero_hit_to_heart_cross` 1083 мс |
| `marker-x-stamp` appear | opacity 0,15 → 1 (150), `sign` 0 → 1,08 (120) → 1,00 (200); скоростью анимации не масштабируется | SD-37; YT `no_defense_x_stamp` 200 мс; TL `defense_check_to_reveal` 600 мс |
| `marker-action-slot-de` | вариант DE трекера: `slot_pulse` (loop 770, кольцо 1,00 → 1,06, opacity 0,6 → 1), `fill` (hold 300, удар 200: слои `action-attack` 0,4 → 1, глиф 0,80 → 1,04 → 1,00, кольцо гаснет), `unfill` (Undo, 150) | 01 F-12; TL `tracker_slot_fill` 300 мс, `tracker_pulse_period` 770 мс |

Отличия от плана W-05 (решения DE-012, журнал `runs/A04-2026-10-04.md`):
- **Кольцо: вспышка начинается с opacity 0,15, а не 0.** Правило набора «кадр 0 не пустой» (STYLE-v3 §1.9).
- **Вариант DE трекера — отдельный id `marker-action-slot-de`, а не анимация `fill` у `action-*`.** Так принятые
  `action-*` и их демо не меняются. Слои `body` и `glyph` берутся из текстур `action-attack`; в HUD для других
  типов — `action-<тип>`. В покое слои типа скрыты (opacity 0): пустой слот — кольцо и серый призрак. Поэтому `fill`
  двигает opacity слоёв, а не `all`.
- **Вспышка кольца — плоский обод без ореола и градиента** (правило ДНК 1). Шире тлеющего обода внутрь на 0,75 u.
- **Холст кольца — 32 u, обод круглый**, окно портрета ⌀ 21 u: портрет в HUD обрезается кругом (DE) — это задача
  DE-023.

### Трекер действий: поведение игры (DE-022, DE-023)

**Вид по умолчанию — v3 без изменений:**
- `action-*` spend = opacity 0,4 за 150 мс, `restore` — обратно (таблица выше);
- `resource-action-full` spend / gain — без изменений.

**Слот трекера в HUD — `resource-action-full`** (DE-023): «потрачено = погасло» — `spend` гасит значок до пустого
жетона (150 мс, hold), отмена выбора — `gain`, сброс хода — поза покоя за 1 кадр. `action-*` остаются значками типа на
кнопках действий: у слота трекера типа нет, а у трекера соперника снапшот тип и не сообщает.

Меняется только поведение: какие события игра посылает и когда.

| Событие игры | Что играет | Когда | Основание |
|---|---|---|---|
| Выбор действия, до Confirm | слот `resource-action-full` spend (150 мс, hold) | в кадре выбора, а не по Confirm: открыт черновик атаки или выбор схемы, либо команда только что отправлена (метка держится до ответа сервера, ≤ 10 с) | TL `tracker_slot_fill` s04 635.283 (DE заливает слот в момент выбора) |
| Undo / отмена выбора | слот `resource-action-full` gain | в кадре отмены | 01 F-12 |
| End Turn / смена хода | сброс — поза покоя за 1 кадр, без `restore` 150 | ≤ 1 кадр от снапшота | TL `tracker_reset` 33 мс (s04 1141.133) |
| Начало хода соперника | контейнер трекера соперника: opacity 0 → 1 за 150 мс, без масштаба (уровень UMG, не запись значка); reduced — opacity 100 мс | в кадре снапшота смены хода | TL `tracker_ai_appear` 133–217 мс (s04 634.117) |
| Начало моего хода | трекер соперника скрыт за 1 кадр | в кадре снапшота | s04 647.900 |
| Свой трекер | виден всегда | — | 01 F-12 |

Вариант DE (`marker-action-slot-de`) — только галерея, для A/B на арт-приёмке.

### Что осталось

- Длящиеся анимации (кольцо, пульс слота) живут только на постоянном UMG-виджете или `US08AnimatedIconWidget`, а не
  на Slate-виджетах, которые `RefreshHud` пересоздаёт (02 §4.3 п. 4; DE-022, DE-023). Бюджет `rules.budget` не меняется:
  кольцо не циклится, пульс слота циклится только в галерее.
- Пометка «(02:895)» у `action-*` spend исправлена на «(02 §8 UI-ICON-ACTION)».
- После арт-приёмки: перенести выбранные кандидаты из `candidates` в принятый набор (README, HUD-AND-ICONS §3.4) и
  подключить в HUD; отклонённые удалить из контракта и `Content/S08/UI/IconsV3`.

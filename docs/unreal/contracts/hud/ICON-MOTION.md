# Движение значков HUD v3: раскадровка

Сгенерировано из контракта [`icon-motion.json`](icon-motion.json) скриптом
`art/imagegen/hud-icons-v3/_tools/motion_contract.py` — не править руками. План и фазы —
[ICON-MOTION-PLAN.md](ICON-MOTION-PLAN.md). Ключи и модель позы — в шапке генератора и в `rules` контракта.

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
| `resource-connection-lost` | appear_from_online | enter | 180 | 110 | bars.opacity; bars.tx; from.opacity; from.tx; sign.scale — связь пропала во время игры (вместо online): столбики online уезжают вправо на место приглушённых и гаснут, X «штампуется», без мигания | bars.opacity; from.opacity; sign.opacity 100 мс |
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

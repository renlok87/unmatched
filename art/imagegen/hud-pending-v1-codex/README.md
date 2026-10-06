# HB-34 — PENDING и SLOT

**Статус: предложено.**

Собраны 18 состояний на Marmoreal и Sarpedon в четырёх нативных холстах: 144 цветных + 144 серых макета; отдельная EN-проверка и её серый вариант. Генерации изображений нет. Все панели, текст и рамки рассчитаны в физических пикселях; сканы contain из исходника одним Lanczos.

Сканы карт, аватары, рубашки и иллюстрация доски — только для внутренней LAN-сборки (ВР-48, GAP-019); в git не входят, лежат в scraped-data/derived/hud-pending-v1-codex/.

## Рекомендация

Рекомендую единый вариант: бирюзовая кромка собственного выбора, спокойный серый компакт чужого выбора и ожидания боя, фиксированный SLOT с отдельной лентой. PICK отличается рамками, ORDER — номерными чипами вне сканов. Решения о внедрении остаются за ревью; это макет, не изменение клиента.

## Проверки и ограничения

Хеши 1780 источников: source_unchanged=True; outside_folder=[]. Минимальный текст 720p: 10.5 px.

Не прошедшие требования: нет. Полные численные результаты: [verification.json](verification.json).

Собственные элементы не сокращают строки. Если геометрия карточки противоречит безопасным маскам, пересечение показано в overlay и записано в overlap; оно не переименовано в transient. Модаль и летящая карта измерены отдельно как разрешённые временные элементы.

HB-08: замороженный генератор и наш нативный renderer сравниваются с шестью основными x1 skins и дополнительным ProgressTrack. Наибольшая разница каждого указана в skin_match_hb08. CP-13 сравнивается целиком, включая прозрачное окно, в frame_match_cp13.

Базовые skins HB-08 совпадают целиком. Фактическая PENDING-модаль по P6 имеет другую кромку (state.pending 2 su); её разница с исходной Modal отдельно указана в applied_pending_modal_max_channel_difference, не объявлена нулевой.

Палитра проверяется по собранному процедурному HUD на прозрачном нативном холсте. Считаются только непрозрачные пиксели, исключены независимо измеренные antialias-края и текстовое покрытие. Допустимые производные цвета кнопок HB-08 вычислены из исходных skins, записаны в palette. Сканы, иконки и фон исключены.

Открытый пункт HB-22: принятый boost-maneuver имеет тот же конфликт чипа над SLOT с TOP (640 px² на 1080p/100%). Здесь чип перенесён внутрь ленты; HB-22 не менялся.

СХЕМА — залитая лента; СБРОС — контурная (navy 0,92, secondary 2 su и secondary текст/глиф); BOOST — внутренний +N. Серые пары измерены по фактическим компонентам.

Модаль подогнана по содержимому до cap. Footer отделён от scan row на 16 su; прокрутка только при превышении cap. Счётчик только в PICK, в ORDER две карты и номера 20 su на чипах 24 su.

## Листы

- HB-34-marmoreal-1920x1080-100: [overlay](comparison/overlay-HB-34-marmoreal-1920x1080-100.png), [серый overlay](comparison/overlay-HB-34-marmoreal-1920x1080-100-gray.png), [цветной контакт](../../../scraped-data/derived/hud-pending-v1-codex/contact-HB-34-marmoreal-1920x1080-100.png), [серый контакт](../../../scraped-data/derived/hud-pending-v1-codex/contact-HB-34-marmoreal-1920x1080-100-gray.png).
- HB-34-marmoreal-1920x1080-150: [overlay](comparison/overlay-HB-34-marmoreal-1920x1080-150.png), [серый overlay](comparison/overlay-HB-34-marmoreal-1920x1080-150-gray.png), [цветной контакт](../../../scraped-data/derived/hud-pending-v1-codex/contact-HB-34-marmoreal-1920x1080-150.png), [серый контакт](../../../scraped-data/derived/hud-pending-v1-codex/contact-HB-34-marmoreal-1920x1080-150-gray.png).
- HB-34-marmoreal-1280x720-100: [overlay](comparison/overlay-HB-34-marmoreal-1280x720-100.png), [серый overlay](comparison/overlay-HB-34-marmoreal-1280x720-100-gray.png), [цветной контакт](../../../scraped-data/derived/hud-pending-v1-codex/contact-HB-34-marmoreal-1280x720-100.png), [серый контакт](../../../scraped-data/derived/hud-pending-v1-codex/contact-HB-34-marmoreal-1280x720-100-gray.png).
- HB-34-marmoreal-1280x720-150: [overlay](comparison/overlay-HB-34-marmoreal-1280x720-150.png), [серый overlay](comparison/overlay-HB-34-marmoreal-1280x720-150-gray.png), [цветной контакт](../../../scraped-data/derived/hud-pending-v1-codex/contact-HB-34-marmoreal-1280x720-150.png), [серый контакт](../../../scraped-data/derived/hud-pending-v1-codex/contact-HB-34-marmoreal-1280x720-150-gray.png).
- HB-34-sarpedon-1920x1080-100: [overlay](comparison/overlay-HB-34-sarpedon-1920x1080-100.png), [серый overlay](comparison/overlay-HB-34-sarpedon-1920x1080-100-gray.png), [цветной контакт](../../../scraped-data/derived/hud-pending-v1-codex/contact-HB-34-sarpedon-1920x1080-100.png), [серый контакт](../../../scraped-data/derived/hud-pending-v1-codex/contact-HB-34-sarpedon-1920x1080-100-gray.png).
- HB-34-sarpedon-1920x1080-150: [overlay](comparison/overlay-HB-34-sarpedon-1920x1080-150.png), [серый overlay](comparison/overlay-HB-34-sarpedon-1920x1080-150-gray.png), [цветной контакт](../../../scraped-data/derived/hud-pending-v1-codex/contact-HB-34-sarpedon-1920x1080-150.png), [серый контакт](../../../scraped-data/derived/hud-pending-v1-codex/contact-HB-34-sarpedon-1920x1080-150-gray.png).
- HB-34-sarpedon-1280x720-100: [overlay](comparison/overlay-HB-34-sarpedon-1280x720-100.png), [серый overlay](comparison/overlay-HB-34-sarpedon-1280x720-100-gray.png), [цветной контакт](../../../scraped-data/derived/hud-pending-v1-codex/contact-HB-34-sarpedon-1280x720-100.png), [серый контакт](../../../scraped-data/derived/hud-pending-v1-codex/contact-HB-34-sarpedon-1280x720-100-gray.png).
- HB-34-sarpedon-1280x720-150: [overlay](comparison/overlay-HB-34-sarpedon-1280x720-150.png), [серый overlay](comparison/overlay-HB-34-sarpedon-1280x720-150-gray.png), [цветной контакт](../../../scraped-data/derived/hud-pending-v1-codex/contact-HB-34-sarpedon-1280x720-150.png), [серый контакт](../../../scraped-data/derived/hud-pending-v1-codex/contact-HB-34-sarpedon-1280x720-150-gray.png).

Листы используют нативные плитки без уменьшения. Последние две плитки каждого overlay — только геометрия CHOOSE_ONE и number picker; финальных состояний для них нет.

## Данные и примеры

Тексты Medusa — card.i18n.ru, Arthur — английские поля scraped-data, как в проверке БД. Hero.name: Medusa, King Arthur; помощники Merlin, Harpies. Примеры не объявлены историческими снимками: позиции всегда из bench, а не run I.

Prophecy раскрывает Excalibur, The Aid of Morgana, Aid the Chosen One, Command the Storms — четыре разные реальные карты вне руки run I. PICK выбирает первые две, ORDER маркирует две оставшиеся 1/2. Очередь MOVE: Harpies 1, ещё 2. BFS проходит свои занятые клетки, исключает противников, заканчивается только на пустой клетке.

Способность Medusa помнит King Arthur (Marmoreal host, строка 2179). Для Sarpedon это пример переноса презентации на другую доску: цель из записанной трассы, позиции из другого bench, не одновременный snapshot.

Причина DISCARD_CARDS — Hiss and Slither: вывод из защиты Medusa hero и единственного подходящего эффекта в каталоге, цепочка строк в facts.json. Рука сброса — разрешённый пример из The Holy Grail, Noble Sacrifice, Swift Strike; выбрана Noble Sacrifice. В slot-discard используется The Holy Grail как пример: имя реально сброшенной карты отсутствует. BOOST манёвра — пример Noble Sacrifice (+3). В after-combat защита не названа: показана рубашка Medusa.

## Фигуры и клетки

- marmoreal: Harpies 3 → M01, Harpies 1 → M07, Medusa → M13, Harpies 2 → M20, Merlin → M23, King Arthur → M31.
  MOVE: M02, M03, M08, M09, M14, M15, M17, M21, M27.
  PLACE: M02, M03, M04, M05, M06, M08, M09, M10, M11, M12, M14, M15, M16, M17, M18, M19, M21, M22, M24, M25, M26, M27, M28, M29, M30.
  CHOOSE_SPACE: M16, M23, M24, M31.
  TARGET кандидаты: Harpies 3, Harpies 1, Medusa, Harpies 2.
- sarpedon: Harpies 2 → S18, Harpies 1 → S19, Harpies 3 → S23, Medusa → S20, Merlin → S25, King Arthur → S32.
  MOVE: S01, S03, S08, S09, S10, S11, S12, S21, S24, S28, S29, S30, S31, S34.
  PLACE: S01, S02, S03, S04, S05, S06, S07, S08, S09, S10, S11, S12, S13, S14, S15, S16, S17, S21, S22, S24, S26, S27, S28, S29, S30, S31, S33, S34, S35, S36, S37, S38.
  CHOOSE_SPACE: S05, S06, S07, S12, S13, S14, S16, S21, S22, S24, S25, S26, S30, S31, S32, S34, S35, S36.
  TARGET кандидаты: Harpies 2, Harpies 1, Harpies 3, Medusa.

## Малые решения

- L сохраняет исходный двухстрочный compact; S — одна строка до 720 su в свободной полосе SLOT+8 … PANEL-OPP/OPP-HAND−8. Hint собственного выбора в S перенесён в STATUS. BOOST везде содержит только две кнопки. Серые compacts имеют ширину по измеренному содержимому с padding 16 su.
- Модаль: фиксированный footer; тело скроллится при превышении cap. Представлен offset 0, скрытая часть записана численно. Сканы в логическом теле целые, видимая окклюзия viewport отличается от crop исходника.
- Лента COMBAT на 720p L размещается над картой по принятой дельте HB-22, чтобы не пересечь LOG. На S имя роли перенесено по словам.
- Иконки — только оригинальные v3 PNG и IC-36; СХЕМА печатает marker-status в navy, СБРОС — secondary; alpha-форма исходника сохранена.
- На фоне оставлены старые имена/HP над фигурами, служебные маленькие уголки кадра и замки лотка. Фон не ретуширован.

## Открытые данные

- Card actually discarded by King Arthur — PEND-RESOLVE has no card id/name; HUD reports hand 1→0, without identity. Uses explicitly labelled The Holy Grail example from run I opening hand.
- Exact hand at DISCARD_CARDS — HUD count is 1; no identities recorded. Task permits opening run I hand of 3 as labelled example.
- Defense identity in the first Swift Strike staged combat — Trace has no named defense. Uses Medusa back as explicitly allowed.

## Строки без ключа

- `hud.slot.*.owner` — «{hud.slot.* RU} · {Hero.name}», по fix1 Fix 9b; EN «SCHEME · Medusa».

- «Сбросьте 1: выбрано 1/1» — HB-34 P3 / 04 §2.8.
- «Выбрано 2/2» — HB-34 P3.
- Номера порядка 1/2 — HB-34 P3; текст отдельным runtime-слоем.

## Дельта 04

| Холст / состояние | Прямоугольник su | Причина |
|---|---|---|
| HB-34-marmoreal-compact-move-1920x1080-100 | 600.00, 80.00, 720.00, 60.00 | text-left |
| HB-34-marmoreal-compact-place-1920x1080-100 | 600.00, 80.00, 720.00, 60.00 | text-left |
| HB-34-marmoreal-compact-target-1920x1080-100 | 600.00, 80.00, 720.00, 60.00 | text-left |
| HB-34-marmoreal-compact-space-1920x1080-100 | 600.00, 80.00, 720.00, 60.00 | text-left |
| HB-34-marmoreal-collapsed-1920x1080-100 | 800.00, 80.00, 320.00, 44.00 | Grow width only if complete text + C + padding exceeds 320. |
| HB-34-marmoreal-discard-1920x1080-100 | 600.00, 80.00, 720.00, 60.00 | text-left |
| HB-34-marmoreal-boost-1920x1080-100 | 680.00, 80.00, 560.00, 56.00 | buttons-only |
| HB-34-marmoreal-opp-1920x1080-100 | 800.00, 80.00, 320.00, 60.00 | text-left |
| HB-34-marmoreal-slot-opp-show-1920x1080-100 | 800.00, 80.00, 320.00, 60.00 | text-left |
| HB-34-marmoreal-compact-move-1920x1080-150 | 283.33, 72.00, 713.33, 56.00 | single-row |
| HB-34-marmoreal-compact-place-1920x1080-150 | 360.00, 72.00, 560.00, 56.00 | single-row |
| HB-34-marmoreal-compact-target-1920x1080-150 | 360.00, 72.00, 560.00, 56.00 | single-row |
| HB-34-marmoreal-compact-space-1920x1080-150 | 360.00, 72.00, 560.00, 56.00 | single-row |
| HB-34-marmoreal-collapsed-1920x1080-150 | 480.00, 72.00, 320.00, 44.00 | Grow width only if complete text + C + padding exceeds 320. |
| HB-34-marmoreal-discard-1920x1080-150 | 360.00, 72.00, 560.00, 56.00 | single-row |
| HB-34-marmoreal-boost-1920x1080-150 | 358.33, 72.00, 563.33, 56.00 | buttons-only |
| HB-34-marmoreal-opp-1920x1080-150 | 417.00, 72.00, 446.00, 48.00 | single-row |
| HB-34-marmoreal-slot-opp-show-1920x1080-150 | 453.00, 72.00, 374.00, 48.00 | single-row |
| HB-34-marmoreal-compact-move-1280x720-100 | 493.33, 80.00, 720.00, 60.00 | text-left |
| HB-34-marmoreal-compact-place-1280x720-100 | 493.33, 80.00, 720.00, 60.00 | text-left |
| HB-34-marmoreal-compact-target-1280x720-100 | 493.33, 80.00, 720.00, 60.00 | text-left |
| HB-34-marmoreal-compact-space-1280x720-100 | 493.33, 80.00, 720.00, 60.00 | text-left |
| HB-34-marmoreal-collapsed-1280x720-100 | 693.33, 80.00, 320.00, 44.00 | Grow width only if complete text + C + padding exceeds 320. |
| HB-34-marmoreal-discard-1280x720-100 | 493.33, 80.00, 720.00, 60.00 | text-left |
| HB-34-marmoreal-boost-1280x720-100 | 573.33, 80.00, 560.00, 56.00 | buttons-only |
| HB-34-marmoreal-opp-1280x720-100 | 693.33, 80.00, 320.00, 60.00 | text-left |
| HB-34-marmoreal-slot-opp-show-1280x720-100 | 693.33, 80.00, 320.00, 60.00 | text-left |
| HB-34-marmoreal-compact-move-1280x720-150 | 151.56, 72.00, 714.67, 56.00 | single-row |
| HB-34-marmoreal-compact-place-1280x720-150 | 288.89, 72.00, 560.00, 56.00 | single-row |
| HB-34-marmoreal-compact-target-1280x720-150 | 288.89, 72.00, 560.00, 56.00 | single-row |
| HB-34-marmoreal-compact-space-1280x720-150 | 288.89, 72.00, 560.00, 56.00 | single-row |
| HB-34-marmoreal-collapsed-1280x720-150 | 408.89, 72.00, 320.00, 44.00 | Grow width only if complete text + C + padding exceeds 320. |
| HB-34-marmoreal-discard-1280x720-150 | 288.89, 72.00, 560.00, 56.00 | single-row |
| HB-34-marmoreal-boost-1280x720-150 | 283.78, 72.00, 570.22, 56.00 | buttons-only |
| HB-34-marmoreal-opp-1280x720-150 | 351.56, 72.00, 434.67, 48.00 | single-row |
| HB-34-marmoreal-slot-opp-show-1280x720-150 | 384.44, 72.00, 368.89, 48.00 | single-row |
| HB-34-sarpedon-compact-move-1920x1080-100 | 600.00, 80.00, 720.00, 60.00 | text-left |
| HB-34-sarpedon-compact-place-1920x1080-100 | 600.00, 80.00, 720.00, 60.00 | text-left |
| HB-34-sarpedon-compact-target-1920x1080-100 | 600.00, 80.00, 720.00, 60.00 | text-left |
| HB-34-sarpedon-compact-space-1920x1080-100 | 600.00, 80.00, 720.00, 60.00 | text-left |
| HB-34-sarpedon-collapsed-1920x1080-100 | 800.00, 80.00, 320.00, 44.00 | Grow width only if complete text + C + padding exceeds 320. |
| HB-34-sarpedon-discard-1920x1080-100 | 600.00, 80.00, 720.00, 60.00 | text-left |
| HB-34-sarpedon-boost-1920x1080-100 | 680.00, 80.00, 560.00, 56.00 | buttons-only |
| HB-34-sarpedon-opp-1920x1080-100 | 800.00, 80.00, 320.00, 60.00 | text-left |
| HB-34-sarpedon-slot-opp-show-1920x1080-100 | 800.00, 80.00, 320.00, 60.00 | text-left |
| HB-34-sarpedon-compact-move-1920x1080-150 | 283.33, 72.00, 713.33, 56.00 | single-row |
| HB-34-sarpedon-compact-place-1920x1080-150 | 360.00, 72.00, 560.00, 56.00 | single-row |
| HB-34-sarpedon-compact-target-1920x1080-150 | 360.00, 72.00, 560.00, 56.00 | single-row |
| HB-34-sarpedon-compact-space-1920x1080-150 | 360.00, 72.00, 560.00, 56.00 | single-row |
| HB-34-sarpedon-collapsed-1920x1080-150 | 480.00, 72.00, 320.00, 44.00 | Grow width only if complete text + C + padding exceeds 320. |
| HB-34-sarpedon-discard-1920x1080-150 | 360.00, 72.00, 560.00, 56.00 | single-row |
| HB-34-sarpedon-boost-1920x1080-150 | 358.33, 72.00, 563.33, 56.00 | buttons-only |
| HB-34-sarpedon-opp-1920x1080-150 | 417.00, 72.00, 446.00, 48.00 | single-row |
| HB-34-sarpedon-slot-opp-show-1920x1080-150 | 453.00, 72.00, 374.00, 48.00 | single-row |
| HB-34-sarpedon-compact-move-1280x720-100 | 493.33, 80.00, 720.00, 60.00 | text-left |
| HB-34-sarpedon-compact-place-1280x720-100 | 493.33, 80.00, 720.00, 60.00 | text-left |
| HB-34-sarpedon-compact-target-1280x720-100 | 493.33, 80.00, 720.00, 60.00 | text-left |
| HB-34-sarpedon-compact-space-1280x720-100 | 493.33, 80.00, 720.00, 60.00 | text-left |
| HB-34-sarpedon-collapsed-1280x720-100 | 693.33, 80.00, 320.00, 44.00 | Grow width only if complete text + C + padding exceeds 320. |
| HB-34-sarpedon-discard-1280x720-100 | 493.33, 80.00, 720.00, 60.00 | text-left |
| HB-34-sarpedon-boost-1280x720-100 | 573.33, 80.00, 560.00, 56.00 | buttons-only |
| HB-34-sarpedon-opp-1280x720-100 | 693.33, 80.00, 320.00, 60.00 | text-left |
| HB-34-sarpedon-slot-opp-show-1280x720-100 | 693.33, 80.00, 320.00, 60.00 | text-left |
| HB-34-sarpedon-compact-move-1280x720-150 | 151.56, 72.00, 714.67, 56.00 | single-row |
| HB-34-sarpedon-compact-place-1280x720-150 | 288.89, 72.00, 560.00, 56.00 | single-row |
| HB-34-sarpedon-compact-target-1280x720-150 | 288.89, 72.00, 560.00, 56.00 | single-row |
| HB-34-sarpedon-compact-space-1280x720-150 | 288.89, 72.00, 560.00, 56.00 | single-row |
| HB-34-sarpedon-collapsed-1280x720-150 | 408.89, 72.00, 320.00, 44.00 | Grow width only if complete text + C + padding exceeds 320. |
| HB-34-sarpedon-discard-1280x720-150 | 288.89, 72.00, 560.00, 56.00 | single-row |
| HB-34-sarpedon-boost-1280x720-150 | 283.78, 72.00, 570.22, 56.00 | buttons-only |
| HB-34-sarpedon-opp-1280x720-150 | 351.56, 72.00, 434.67, 48.00 | single-row |
| HB-34-sarpedon-slot-opp-show-1280x720-150 | 384.44, 72.00, 368.89, 48.00 | single-row |
| HB-34-marmoreal-compact-target-en-1920x1080-100 | 600.00, 80.00, 720.00, 60.00 | text-left |
| HB-34-marmoreal-after-combat-1920x1080-100 | 800.00, 80.00, 320.00, 60.00 | text-left |
| HB-34-marmoreal-after-combat-1920x1080-150 | 480.00, 72.00, 320.00, 48.00 | single-row |
| HB-34-marmoreal-after-combat-1280x720-100 | 693.33, 80.00, 320.00, 60.00 | text-left |
| HB-34-marmoreal-after-combat-1280x720-150 | 408.89, 72.00, 320.00, 48.00 | single-row |
| HB-34-sarpedon-after-combat-1920x1080-100 | 800.00, 80.00, 320.00, 60.00 | text-left |
| HB-34-sarpedon-after-combat-1920x1080-150 | 480.00, 72.00, 320.00, 48.00 | single-row |
| HB-34-sarpedon-after-combat-1280x720-100 | 693.33, 80.00, 320.00, 60.00 | text-left |
| HB-34-sarpedon-after-combat-1280x720-150 | 408.89, 72.00, 320.00, 48.00 | single-row |
| HB-34-marmoreal-modal-pick-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-compact-target-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-compact-space-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-collapsed-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-slot-opp-hold-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 302.00 | Карта + 4 su зазор + 28 su лента + 2 su gap + 4 su HOLD; ширина ленты 190 su |
| HB-34-marmoreal-slot-opp-show-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-slot-opp-fade-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-slot-discard-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-modal-pick-1920x1080-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-marmoreal-compact-target-1920x1080-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-marmoreal-compact-space-1920x1080-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-marmoreal-collapsed-1920x1080-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-marmoreal-slot-opp-hold-1920x1080-150 / SLOT + лента | 16.00, 64.00, 120.00, 216.00 | Карта + 4 su зазор + 40 su лента + 2 su gap + 4 su HOLD; ширина ленты 120 su |
| HB-34-marmoreal-slot-opp-show-1920x1080-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-marmoreal-slot-opp-fade-1920x1080-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-marmoreal-slot-discard-1920x1080-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-marmoreal-modal-pick-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-compact-target-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-compact-space-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-collapsed-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-slot-opp-hold-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 302.00 | Карта + 4 su зазор + 28 su лента + 2 su gap + 4 su HOLD; ширина ленты 190 su |
| HB-34-marmoreal-slot-opp-show-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-slot-opp-fade-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-slot-discard-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-modal-pick-1280x720-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-marmoreal-compact-target-1280x720-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-marmoreal-compact-space-1280x720-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-marmoreal-collapsed-1280x720-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-marmoreal-slot-opp-hold-1280x720-150 / SLOT + лента | 16.00, 64.00, 120.00, 216.00 | Карта + 4 su зазор + 40 su лента + 2 su gap + 4 su HOLD; ширина ленты 120 su |
| HB-34-marmoreal-slot-opp-show-1280x720-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-marmoreal-slot-opp-fade-1280x720-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-marmoreal-slot-discard-1280x720-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-sarpedon-modal-pick-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-compact-target-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-compact-space-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-collapsed-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-slot-opp-hold-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 302.00 | Карта + 4 su зазор + 28 su лента + 2 su gap + 4 su HOLD; ширина ленты 190 su |
| HB-34-sarpedon-slot-opp-show-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-slot-opp-fade-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-slot-discard-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-modal-pick-1920x1080-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-sarpedon-compact-target-1920x1080-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-sarpedon-compact-space-1920x1080-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-sarpedon-collapsed-1920x1080-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-sarpedon-slot-opp-hold-1920x1080-150 / SLOT + лента | 16.00, 64.00, 120.00, 216.00 | Карта + 4 su зазор + 40 su лента + 2 su gap + 4 su HOLD; ширина ленты 120 su |
| HB-34-sarpedon-slot-opp-show-1920x1080-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-sarpedon-slot-opp-fade-1920x1080-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-sarpedon-slot-discard-1920x1080-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-sarpedon-modal-pick-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-compact-target-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-compact-space-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-collapsed-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-slot-opp-hold-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 302.00 | Карта + 4 su зазор + 28 su лента + 2 su gap + 4 su HOLD; ширина ленты 190 su |
| HB-34-sarpedon-slot-opp-show-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-slot-opp-fade-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-slot-discard-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-modal-pick-1280x720-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-sarpedon-compact-target-1280x720-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-sarpedon-compact-space-1280x720-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-sarpedon-collapsed-1280x720-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-sarpedon-slot-opp-hold-1280x720-150 / SLOT + лента | 16.00, 64.00, 120.00, 216.00 | Карта + 4 su зазор + 40 su лента + 2 su gap + 4 su HOLD; ширина ленты 120 su |
| HB-34-sarpedon-slot-opp-show-1280x720-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-sarpedon-slot-opp-fade-1280x720-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-sarpedon-slot-discard-1280x720-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-marmoreal-compact-target-en-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-slot-boost-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-modal-order-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-slot-boost-1920x1080-150 / SLOT + лента | 16.00, 64.00, 190.00, 198.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-modal-order-1920x1080-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-marmoreal-slot-boost-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-modal-order-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-slot-boost-1280x720-150 / SLOT + лента | 16.00, 64.00, 190.00, 198.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-marmoreal-modal-order-1280x720-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-sarpedon-slot-boost-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-modal-order-1920x1080-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-slot-boost-1920x1080-150 / SLOT + лента | 16.00, 64.00, 190.00, 198.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-modal-order-1920x1080-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |
| HB-34-sarpedon-slot-boost-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-modal-order-1280x720-100 / SLOT + лента | 24.00, 84.00, 190.00, 296.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-slot-boost-1280x720-150 / SLOT + лента | 16.00, 64.00, 190.00, 198.00 | Карта + 4 su зазор + 28 su лента; ширина ленты 190 su |
| HB-34-sarpedon-modal-order-1280x720-150 / SLOT + лента | 16.00, 64.00, 120.00, 210.00 | Карта + 4 su зазор + 40 su лента; ширина ленты 120 su |

## Воспроизведение

`python -B -X utf8 art/imagegen/hud-pending-v1-codex/_tools/build_mockups.py`

Baseline создан до сборки; повторный запуск его не перезаписывает. Скрипт завершает запись manifest-sha256.json последним действием. Проверка: `python -B -X utf8 art/imagegen/hud-pending-v1-codex/_tools/audit_package.py`.

Git, unreal/, Unreal Editor, UBT и упаковка не запускались; файлы принятых пакетов не менялись.

## Исправления fix1

| № | До → после |
|---|---|
| 1 | M/A/S → M/A/G из st-hud; STATUS chips 24 su → 20 su, промежутки 8 su и 12 su до текста; resolve из hud.key.resolve. |
| 2 | Sentence case → upper() всех кнопок; 20 su Bold Condensed, источник и case_transform записаны, ширины пересчитаны. |
| 3 | PICK подъём 0 → 16 su; ORDER 4 → 2 карты, цифры 14 → 20 su на чипах 24 su; счётчик удалён из ORDER. Высота по содержимому, зазор до footer 16 su. |
| 4 | S compact высоты 60–84 → 48–56 su, одна строка; свободная полоса и точные ширины в compact_geometry. Общие непрошедшие overlap: 0. |
| 5 | King Arthur три раза → один раз в STATUS ms.ability.boost; BOOST compact содержит только две кнопки в одной строке. |
| 6 | Серые compacts 720/560 su → измеренная ширина + 32 su, min 320 su, cap класса; значения в дельте 04. |
| 7 | BOOST chip TOP overlap 640 px² → чип внутри ленты, от правого края 4 su, ничего выше SLOT. |
| 8 | HOLD 2 su на scheme, 1,55:1 → отдельный bar 4 su, gap 2 su, fill 50%; минимум 4.15:1 по PNG; SLOT group +6 su относительно новой ленты. |
| 9 | СХЕМА/СБРОС одна форма, Δluma 19,28 → filled/outline; на каждой ленте указан владелец, ни одна надпись не сокращена. |

### P5 — дельта ВР-VS2-HB34-12

| Состояние | L STATUS | S STATUS |
|---|---|
| compact-move | ms.choice.target(n=3) | ms.pending.move(Harpies,3) |
| compact-place | ms.status.choice(Bewilderment) | ms.pending.place(Merlin) |
| compact-target | ms.choice.target(n=1) | ms.choice.target(n=1) |
| compact-space | ms.status.choice(Restless Spirits) | первая фраза эффекта Restless Spirits |
| discard | ms.status.choice(Hiss and Slither) | «Сбросьте 1: выбрано 1/1» |
| boost | ms.ability.boost(King Arthur) | ms.ability.boost(King Arthur) |
| toast / after-combat | ms.status.action + M/A/G / ms.status.resolve + R | то же |

Смена входных хешей: нет. Исходный source-hashes-before.json сохранён.
Все точные изменения по холстам: fix1-before.json → facts.json / verification.json.

### Числа модалей до → после

| Холст / состояние | Высота su | Скрыто в scroll su |
|---|---|---|
| HB-34-marmoreal-modal-pick-1920x1080-100 | 420 → 396 | 0 → 0 |
| HB-34-marmoreal-modal-order-1920x1080-100 | 420 → 408 | 0 → 0 |
| HB-34-marmoreal-modal-pick-1920x1080-150 | 360 → 354 | 0 → 0 |
| HB-34-marmoreal-modal-order-1920x1080-150 | 360 → 360 | 0 → 6 |
| HB-34-marmoreal-modal-pick-1280x720-100 | 380 → 380 | 0 → 16 |
| HB-34-marmoreal-modal-order-1280x720-100 | 380 → 380 | 16 → 28 |
| HB-34-marmoreal-modal-pick-1280x720-150 | 360 → 354 | 0 → 0 |
| HB-34-marmoreal-modal-order-1280x720-150 | 360 → 360 | 0 → 6 |
| HB-34-sarpedon-modal-pick-1920x1080-100 | 420 → 396 | 0 → 0 |
| HB-34-sarpedon-modal-order-1920x1080-100 | 420 → 408 | 0 → 0 |
| HB-34-sarpedon-modal-pick-1920x1080-150 | 360 → 354 | 0 → 0 |
| HB-34-sarpedon-modal-order-1920x1080-150 | 360 → 360 | 0 → 6 |
| HB-34-sarpedon-modal-pick-1280x720-100 | 380 → 380 | 0 → 16 |
| HB-34-sarpedon-modal-order-1280x720-100 | 380 → 380 | 16 → 28 |
| HB-34-sarpedon-modal-pick-1280x720-150 | 360 → 354 | 0 → 0 |
| HB-34-sarpedon-modal-order-1280x720-150 | 360 → 360 | 0 → 6 |

### Ширина серых компактов до → после

| Холст / состояние | Ширина su |
|---|---|
| HB-34-marmoreal-opp-1920x1080-100 | 720.00 → 320.00 |
| HB-34-marmoreal-slot-opp-show-1920x1080-100 | 720.00 → 320.00 |
| HB-34-marmoreal-opp-1920x1080-150 | 560.00 → 446.00 |
| HB-34-marmoreal-slot-opp-show-1920x1080-150 | 560.00 → 374.00 |
| HB-34-marmoreal-opp-1280x720-100 | 720.00 → 320.00 |
| HB-34-marmoreal-slot-opp-show-1280x720-100 | 720.00 → 320.00 |
| HB-34-marmoreal-opp-1280x720-150 | 560.00 → 434.67 |
| HB-34-marmoreal-slot-opp-show-1280x720-150 | 560.00 → 368.89 |
| HB-34-sarpedon-opp-1920x1080-100 | 720.00 → 320.00 |
| HB-34-sarpedon-slot-opp-show-1920x1080-100 | 720.00 → 320.00 |
| HB-34-sarpedon-opp-1920x1080-150 | 560.00 → 446.00 |
| HB-34-sarpedon-slot-opp-show-1920x1080-150 | 560.00 → 374.00 |
| HB-34-sarpedon-opp-1280x720-100 | 720.00 → 320.00 |
| HB-34-sarpedon-slot-opp-show-1280x720-100 | 720.00 → 320.00 |
| HB-34-sarpedon-opp-1280x720-150 | 560.00 → 434.67 |
| HB-34-sarpedon-slot-opp-show-1280x720-150 | 560.00 → 368.89 |
| HB-34-marmoreal-after-combat-1920x1080-100 | 720.00 → 320.00 |
| HB-34-marmoreal-after-combat-1920x1080-150 | 560.00 → 320.00 |
| HB-34-marmoreal-after-combat-1280x720-100 | 720.00 → 320.00 |
| HB-34-marmoreal-after-combat-1280x720-150 | 560.00 → 320.00 |
| HB-34-sarpedon-after-combat-1920x1080-100 | 720.00 → 320.00 |
| HB-34-sarpedon-after-combat-1920x1080-150 | 560.00 → 320.00 |
| HB-34-sarpedon-after-combat-1280x720-100 | 720.00 → 320.00 |
| HB-34-sarpedon-after-combat-1280x720-150 | 560.00 → 320.00 |

Дополнение аудита P12 для нового scrollbar ORDER: производные RGB полупрозрачного ProgressTrack рассчитаны из неизменённого x1 HB-08 поверх card.navy тем же способом, что кромки кнопок; `allowed_hb08_derived_progress_colors` содержит источники и операции. Новых пигментов нет (material_off_token_pixels=0). STATUS KeyChip повторяет native Pillow-кромку HB-13.

Полное воспроизведение fix1: сначала `python -B -X utf8 art/imagegen/hud-pending-v1-codex/_tools/build_mockups.py`, затем `python -B -X utf8 art/imagegen/hud-pending-v1-codex/_tools/finalize_fix1.py` и read-only `audit_package.py`. Оба этапа завершают запись manifest последним действием.

Независимый аудит fix1: 580 проверок; минимум контраста HOLD по фактическому PNG 4.15:1.

## Ревью Claude (2026-10-06, CX-13, VS-2, единственный проход, по делегированию)

Итог: **принято по делегированию** (полномочие пользователя 2026-10-06 «Все решения принимай») как макет PENDING и
SLOT HB-34 для HB-35…HB-37 (`UUmHudPending`, `UUmHudSourceSlot`). Статус пакета остаётся «предложено» до листа
приёмки 02 §13.2; строки «дельта 04» переносятся в 04 §1.6 и §2.8 отдельным шагом документа.

История:
- Карточка HB-34 исправлена до прогона (решения ВР-VS2-HB34-01…12 в строке карточки, `06-tasks/hud.csv`): фон
  Marmoreal — кадр с нарисованным задником `-ConceptPaste` (ВР-VS2-01), база — принятые HB-07, HB-13, HB-22, CP-13,
  HB-08; «уточнить» на финалах нет; тексты King Arthur и способностей — английские значения БД (проверка
  `C:/tmp/visual/CX-13/db-cards-2026-10-06.txt`); четыре холста; матрица 18 состояний с владельцами.
- Прогон 1: 14:23–14:50. Ревью нашло девять правок, и был сделан один корректирующий прогон fix1 (14:58–15:12,
  задание `06-tasks/prompts/HB-34.fix1.codex.md`):
  - в STATUS тоста клавиша схемы была «S» вместо `hud.key.scheme` «G», чипы касались текста;
  - кнопки не капсом (02 §3.3 `type.button`);
  - отмеченные карты PICK в сером не отличались; в ORDER оставались все четыре карты и счётчик;
  - P9: компакт класса S (720p 150 %) в две-три строки заходил на клетки и фигуру (до 4314 px²);
  - BOOST-компакт: «King Arthur» трижды вверху;
  - серый компакт на 720 su с пустой правой половиной;
  - чип «+3» над SLOT пересекал резерв TOP (640 px²);
  - P12: линия удержания `card.glyph` на ленте СХЕМА — 1,55 : 1;
  - P13: ленты СХЕМА и СБРОС одной формы, Δluma 19,3; на ленте не было владельца карты.

Что проверено:
- **Рамки задачи.** `git status --porcelain` до и после каждого прогона: Codex создал только эту папку и
  `scraped-data/derived/hud-pending-v1-codex/` (в `.gitignore`). Прочие новые пути в основной копии — пакеты и
  задания параллельных сессий (HB-26, HB-29) и их строки журнала. `unreal/` не тронут, git-команд нет.
  `outside_folder: []`, `source_unchanged: true` (1780 входов).
- **Файлы.** `manifest-sha256.json`: 341 файл, хеши пересчитаны независимо, все совпали, покрытие полное. 144 цветных
  + 144 серых макета, EN-проверка, 16 контактных листов, 16 overlay-листов без сканов. Пакет без scraped-data —
  16 МБ. Генераций изображений 0. Картинок со сканами, рубашками и доской в этой папке нет.
- **Кадры.** Открыты (Read) все 144 цветных финала после fix1 — обе доски, 1080p и 720p, 100 % и 150 %, —
  EN-проверка, серые листы 18 состояний на каждую доску и холст (собраны вне git, `C:/tmp/visual/CX-13/gray-sheets/`),
  серые вырезки модали, компактов и лент, overlay Sarpedon 720p 150 %. Результат осмотра:
  - фон Marmoreal — нарисованный задник (`aeafe8f2…`), Sarpedon — `lit3d` (`bf36d5d6…`), без ретуши (0 изменённых
    пикселей вне HUD и подложек); на кадрах шесть фигур v2;
  - модаль Prophecy: заголовок, текст карты, 4 скана целиком в рамках CP-13, отмеченные подняты на 16 su с рамкой
    `state.pending`, «Выбрано 2/2», ПОДТВЕРДИТЬ / СВЕРНУТЬ (C); ORDER — две карты с чипами 1 и 2; на 720p 100 % и в
    классе S тело прокручивается, футер виден;
  - компакты: свой — бирюзовая кромка и кнопки, чужой и «после боя» — серые, без кнопок, по ширине текста; в классе S
    одна строка, подсказка шага в STATUS;
  - подложки V-11 (MOVE, Harpies 1 → 3 шага) и V-12 (PLACE, CHOOSE_SPACE в зоне Merlin) только на клетках из
    топологии; панели их не закрывают;
  - SLOT: скан или рубашка целиком, лента под картой: СХЕМА — залитая, СБРОС — контурная, BOOST — navy с «+3» внутри;
    на ленте владелец («СХЕМА · Medusa», «СХЕМА · King Arthur»); фазы fly / hold (полоса 50 %) / show / fade (0,5);
  - слова «уточнить», обрезанных подписей, мазков, брызг, градиентов, красных заливок на HUD нет.
- **Замеры** (`verification.json`, 07 §1.2; `_tools/audit_package.py` — PASS, все 26 строк приёмки пройдены):
  перекрытие постоянных блоков с масками фигур и клеток и резервами HB-07 — 0 px² на 144 макетах; модаль и летящая
  карта — в `transient_overlap`; мин. текст на 720p — 10,5 px; контраст текста ≥ 7,16 : 1, кромки к телу ≥ 3,09 : 1,
  глиф к подложке ≥ 4,75 : 1, полоса удержания 14,2 : 1; палитра — 0 пикселей вне токенов; рамки CP-13 и скины HB-08
  совпадают пиксель в пиксель (разница кромки модали `state.pending` с исходной Modal записана отдельно); 40/40 серых
  пар различимы.
- **Данные.** Каждая строка и число трассируются в `facts.json`: строки — `st-hud.csv`, `st-ms.csv`,
  `why-reasons.json`; карты — `medusa.json` (RU), `king-arthur.json` и проверка БД (EN); моменты прогона I —
  TARGET_FIGHTER A Momentary Glance (Marmoreal host), DISCARD_CARDS от Hiss and Slither и MOVE 4 Swift Strike
  (Sarpedon joiner), способность Medusa; примеры (Prophecy с Excalibur, The Aid of Morgana, Aid the Chosen One,
  Command the Storms; буст King Arthur Noble Sacrifice +3; сброс The Holy Grail; Bewilderment; Restless Spirits)
  помечены как не моменты прогона I.

Не входит в приёмку и остаётся открытым:
- **Чип «+N» HB-22.** В принятом HB-22 boost-maneuver чип над SLOT пересекает резерв TOP (640 px² на 1080p 100 %);
  здесь он внутри ленты. HB-22 не менялся — правка в HB-24/HB-25 или отдельной строкой 04.
- **Строки без ключа.** «Сбросьте {n}: выбрано {h}/{n}» (04 §2.8), «Выбрано {k}/2», шаблон ленты «{слот} · {владелец}»
  — нужны ключи `hud.pending.discard.count`, `hud.pending.pick.count`, `hud.slot.*.owner` (задача строк).
- **Тексты King Arthur и способностей по-английски** в RU-интерфейсе — данные БД (`Card.textRu` = EN), не пробел
  макета; RU-тексты — задача данных бэкенда.
- **Подписи фигур на фоне** («Harpies 3», «Medusa 16/16» и т. п.) — артефакт bench-кадров, не данные HUD.
- **Маски и подложки** — ручная регистрация HB-07 (остаток до 9,5 px на Sarpedon), а не проекция UE: эллипсы V-11 /
  V-12 местами смещены на несколько пикселей от нарисованных клеток. В UE подложки рисует поле, не HUD.
- **CHOOSE_ONE и число ▲▼** — только геометрия overlay-листов (карт MVP с ними нет, ВР-HB11).
- Время (прилёт 200 / 500, удержание 1500, уход 150, кроссфейд STATUS) в статичных макетах не проверялось — это
  HB-35…HB-37.

Решения ревью (по делегированию, серия ВР-VS2):

| ВР | Решение | Почему |
|---|---|---|
| ВР-VS2-HB34-13 | Класс S: компакт — одна строка (значок, имя карты, чип очереди, кнопки), подсказка шага — в STATUS; класс L — две строки внутри 720 su | Вторая и третья строка компакта на 720p 150 % заходили на клетки и фигуры; STATUS и так строка «что делать сейчас» |
| ВР-VS2-HB34-14 | BOOST King Arthur: вопрос `ms.ability.boost` — в STATUS, компакт — только две кнопки | Иначе имя героя три раза подряд вверху экрана |
| ВР-VS2-HB34-15 | Серый компакт (чужой выбор, после боя) — по ширине текста + 2 × 16 su, не меньше 320 su | Пустая половина плашки на 720 su читалась как поломка |
| ВР-VS2-HB34-16 | Чип «+N» буста — внутри ленты BOOST у правого края; ничего из группы SLOT не выше верха SLOT | Над картой чип пересекал резерв TOP |
| ВР-VS2-HB34-17 | Удержание 1500 мс — отдельная полоса 4 su под лентой (`card.navy` + заливка `card.glyph`) | Линия `card.glyph` на ленте СХЕМА — 1,55 : 1 |
| ВР-VS2-HB34-18 | Лента СБРОС — контурная (`card.navy` 0,92, кромка и текст `text.secondary`), СХЕМА — залитая; на ленте владелец: «{слот} · {имя героя}» | СХЕМА и СБРОС различались в сером только на 19 luma; своя и чужая схема в слоте были неразличимы |
| ВР-VS2-HB34-19 | DECK_TOP_PICK: отмеченная карта поднимается на 16 su; ORDER показывает только две упорядочиваемые карты, без счётчика | Рамка `state.pending` на navy в сером почти не видна; в ORDER выбранные в руку карты уже не участвуют |

Строка README в `manifest-sha256.json` снята Claude до этого раздела ревью (`note_review`). Остальные файлы пакета
после fix1 не менялись.

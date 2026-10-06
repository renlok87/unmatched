# CP-10 — портрет Merlin (помощник King Arthur)

VS-2, шаг B3, 2026-10-06, ветка `feat/visual-vs2`. Карточка — `cards-portraits.csv` CP-10; 04 §2.2, §1.4; 02 §6.4.
Общее для CP-09…CP-12 (реестр, код, решения ВР-VS2-63…69, проверки) — в [README CP-09](../CP-09/README.md).

**Статус:** круг из принятого CP-07 (вариант B), мини-портрет в PANEL-LOC и PANEL-OPP, павший — насыщенность 0. Тесты
и трасса готовы. Packaged-кадры — шаг «Кадры» VS-2. ROOM 40 su проверен на листе; экрана ROOM на UMG ещё нет (SC).
**Откат:** `-S08PortraitLegacy` — фолбэк «M» на card.navy, `tex=legacy`.

## Что сделано

| Пункт `do` | Где |
|---|---|
| 1. Импорт `--portraits` → `T_Portrait_king_arthur_merlin` (128²) | CP-02. Прогон `--portraits` дал `unchanged`. Текстура вне git. |
| 2. Реестр `portraits.king-arthur/merlin`: src 128², disc CP-07 | (0,50; 0,48; 0,69): круг 88,32 px. Запечённое красное кольцо (радиус 50–64 px) снаружи: дальняя точка круга на 46,7 px (тест `Portrait.Crops`, ВР-CP02). |
| 3. Пал (контакт + 1100 мс): насыщенность 0, плашка не исчезает | `UUmHudPlayerPanel::MakeMiniPortrait` → `UmPortrait::MakeDisc` с `State = Fallen` (Desaturation 1). Момент «пал» — метка стадии смерти (ВР-VS2-55, HB-18). Сердце павшего 24 su рядом ставит панель. |

Трасса мини-портрета: `PORTRAIT id=king-arthur/merlin tex=/Game/S08/UI/Portraits/T_Portrait_king_arthur_merlin… su=32.0
px=… scale=… show=panel side=own|opp state=avatar|fallen capped=0` (без `n`).

## Проверки

- UE `Unmatched.S08.Hud.Portrait.Sidekicks`: у Merlin одна строка PORTRAIT, `side=opp`, без `n` и без бейджа,
  `scale=0.362` при 1080p. `Portrait.Crops`: ≤ 1,25 при всех показах 32 / 40 su до 1,5 px/su.
- Scale по трассам галереи: 32 su — 0,272 (720p) / 0,362 (1080p) / 0,543 (1080p 150 %) / 0,725 (2160p) / 1,087
  (2160p 150 %); ROOM 40 su — до 0,679 при 1080p 150 % и 1,359 при 2160p 150 % (ВР-VS2-64: под кэпом 1,6).
- Листы вне git: `scraped-data/derived/visual-evidence/CP-10/CP-10-{720-100,1080-100,1080-150,2160-100,2160-150}.png`
  (32 и 40 su, живой и павший, фолбэк; цвет | серый | дейтеранопия); панели King Arthur с Merlin —
  `…/CP-09-12/sheet-*-p2.png`. Всё открыто (Read), 32 su ×1 — с увеличением ×4 nearest. Merlin читается по красному
  колпаку и белой бороде; это цвета иллюстрации внутри радиуса 50, они сохранены по CP-07. Цветного обода нет. В сером
  лицо и борода различимы при 32 su. Павший — серый круг. «7/7» и имя под панелью не изменились.

## Отложено (шаг «Кадры» VS-2, packaged)

- Кадр A на Marmoreal original (Arthur, свой ход, Merlin жив) и кадр с павшим Merlin на Sarpedon original, 1080p и
  720p 100 %, `-Bench` с RENDER, шесть фигур v2; ROOM 1080p — с экраном ROOM (SC). Трасса `PORTRAIT
  id=king-arthur/merlin scale ≤ 1,25`.

## Кадры VS-2 (2026-10-07, упаковка `230b2b0d`)

Кадры выхода и гейты — [VS-2](../VS-2/README.md). Прогоны `run-combat-demo -PlayerView -S08ExitShots` на Marmoreal original (`-ConceptPaste` до EN-13) и Sarpedon original, шесть фигур v2, 1080p 75 / 100 / 150 %, 720p 100 / 150 %; vs-ai `-PlayerView`. Листы цвет / серый / дейтеранопия — `sheet-0*.png` (`sheet.py`, вырезки по трассовым bbox). Все кадры и листы открыты (Read).

- **Решение:** художественно принято, по делегированию (2026-10-07).
- Merlin — мини 32 su рядом с именем и «7/7». Красная мантия узнаётся на 720p; в сером — по силуэту колпака.
- Кадр павшего Merlin в этой упаковке не встретился: Merlin в партиях выжил.

# HB-41 — субтитры: `UUmHudSubtitle` (шаг H5)

VS-4, шаг V2 (H5 + H11), 2026-10-07, ветка `feat/visual-vs4` (worktree `C:/tmp/wt-visual`), код — `6cdec6e1`.
Карточка — `hud.csv` HB-41; 04 §2.13 (с дельтами VS-2 и VS-4), §4.3, §7.1; принятый макет HB-38
(`art/imagegen/hud-feed-v1-codex/`, ВР-VS2-HB38-08, -15); `docs/game-design/audio/02-audio-design.md` §3.4, реплики —
`docs/game-design/audio/04-vo-script.md`. Тот же коммит — [HB-39](../HB-39/README.md), [HB-40](../HB-40/README.md),
[HB-36](../HB-36/README.md).

**Статус:** капсула, WBP, подключение к VO, тест и лист галереи готовы, по делегированию. Прогон со звуком (AU-S4) с
`UI-HUD-SUB shown` на обеих досках и кадр реплики 1080p / 720p 150 % из партии — шаг «Кадры». **Откат:**
`-S08SlateHud=sub` — прежний `SubtitleBox` Slate.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| 1. `UUmHudSubtitle` | `S08/UI/UmHudSubtitle.h/.cpp`, `/Game/S08/UI/Hud/WBP_UI_HUD_SUB`. BindWidget `Speaker` («{name}:», `hud.sub.speaker`, `type.tag` `card.cream`), `Line` (`type.body` `text.primary`), ещё `Root`, `Capsule` (`T_Skin_Capsule`), `Row`. Вход — `ApplyModel(FUmSubtitleModel{Speaker, Line, StartMs, DurationMs})` из `OfferVoLine` (хук `UmHudShowSubtitle`: имя — `SpeakerName` VO-директора, строка и длина — `FS08VoDecision` и длина звука). |
| 2. Место | одна группа с тостами (`UmHudFeed::Place`, 04 §2.12): низ капсулы на 4 su выше верха карт, по центру коридора руки, под тостами с зазором 8 su; при опущенной руке — над опущенными картами; если пересекает клетку, фигуру или блок — той же цепочкой вверх. |
| 3. Настройки | UI-ACC-015 «Субтитры» выкл — `OfferVoLine` не доходит до показа (как и прежде); UI-ACC-016 «Описывать звуки» — описанный крик гарпии в той же капсуле, без имени. |
| 4. Ввод | `HitTestInvisible` — мышь не ловит. |
| 5. `SHOT widget` | `id=UI-HUD-SUB impl=umg state=shown … lines=1|2 speaker=0|1 lowered=0|1` — без текста; трасса `HUD-SUB show speaker=0|1 ms=<n>` (и прежняя `VO subtitle line=… until=…`). |
| 6. Slate | `SubtitleBox` показывается только с `-S08SlateHud=sub`; остановка голоса (`StopMatchVoice`) прячет и капсулу (`UmHudHideSubtitle`). |
| 7. Тест | `Unmatched.S08.Hud.Subtitle.Duration`: ARTHUR-MATCHUP-MEDUSA-01 RU одной строкой ≤ 720 su, высота ≥ 28 su; видна до длины + 500 мс, скрыта после; новая реплика заменяет старую; «Защищайся!» при опущенной руке — `lowered=1`; строка длиннее 720 su — две строки, не режется; `HitTestInvisible`. |

Время: длина реплики + 500 мс, проявление 150 мс (`hover.ms`), с reduced motion — сразу.

## Решения по делегированию (шаг V2)

| № | Решение | Почему |
|---|---|---|
| ВР-VS4-23 | Капсула всегда в одной группе с тостами (не только в бою) | 04 §2.13 «под стопкой тостов»; одна цепочка — один расчёт |
| ВР-VS4-39 | Строка длиннее 720 su переносится во вторую (карточка: «иначе 2»), не режется; крик гарпии (UI-ACC-016) — без имени, как в аудио-чате | макет требовал одну строку для реплик VO-скрипта — они в неё входят |

## Лист

Галерея `-S08IconGalleryFeed` (см. [HB-40](../HB-40/README.md#лист)): 6 sub — длинная реплика (при руке в покое
встаёт в верхнюю полосу или ниже её: внизу она задевает клетки), 7 sub-lowered — «Защищайся!» над опущенной рукой,
8 combat — группа «два тоста + капсула» с 0 px² к фигурам и блокам на 8 холстах из 8.

- В git: plain-листы HB-40 (состояния 6–8).
- Вне git (ВР-VS4-01): `scraped-data/derived/visual-evidence/HB-41/sub-crops-*.png` — состояния 6, 7, 8 на 8 холстах в
  родных пикселях, цвет и серый — [`visual-evidence-index.json`](visual-evidence-index.json).

Что видно (Read: контакты Marmoreal 720p 150 %, Sarpedon 1080p 100 %, plain 720p 150 %, вырезки g2): капсула с тёмной
подложкой и кромкой, «King Arthur:» кремовым сжатым, реплика светлым одной строкой; над опущенной рукой «Защищайся!»;
в бою капсула под двумя тостами.

## Проверки

- Сборки, тесты UE (9 из 9 новых, 89 из 89 `Hud.*`, 491 из 491 полный), pytest, `hud_contract.py validate`, `check-trace`
  8 трасс галереи (`UI-HUD-SUB state=shown`) — как в [HB-39](../HB-39/README.md#проверки).
- WBP `WBP_UI_HUD_SUB` — created, up-to-date.

## Что не сделано в этом шаге

- Прогон со звуком (AU-S4) и кадр реплики из партии на обеих досках — шаг «Кадры».

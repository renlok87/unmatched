# CP-08 — материал круга и аватар в WBP_UmPortrait; монограмма — фолбэк и откат

VS-2 шаг A3, 2026-10-06, ветка `feat/visual-vs2` (worktree `C:/tmp/wt-visual`). Карточка —
`docs/game-design/visual/06-tasks/cards-portraits.csv` CP-08; 02 §6.4, §6.5; 04 §4.2, §4.3, §1.10, §2.2.

**Статус:** код, материал, WBP, тесты и трасса готовы; приёмочные кадры packaged (наборы A и B 04 §7.2 на Marmoreal
original и Sarpedon original) — шаг «Кадры» VS-2 (упаковки в этом шаге нет). Числа круга — стартовые ВР-CP01 (CP-07 ещё
не принят; после него меняются только числа `disc` реестра).
**Флаг отката:** `-S08PortraitLegacy` (ВР-CP08) — прежний вид: диск цвета команды + монограмма; ARTLOOK
`portraits=legacy(-S08PortraitLegacy)`; трасса `PORTRAIT … tex=legacy`.

## Что сделано (пункты do)

| № | Пункт | Где |
|---|---|---|
| 1 | Материал `/Game/S08/UI/Common/M_UmPortraitDisc` (домен User Interface, Translucent): `Avatar`, `UVRect`, `Desaturation` (Rec.709), `Opacity`, `EdgeColor`, `KeylineColor`, `FillColor`, `EdgeFrac`, `KeylineFrac`; круг и обе границы кромки сглажены на 1 px (`fwidth`) | `tools/art/cards/ue_portrait_disc_material.py` (одна Custom-нода, `--check` сверяет имена с `S08/UI/UmPortrait.h`); отчёт `art/cards-v1/portrait-disc-material-report.json`. Литералов цвета в коде нет: цвета — из `DA_UmHudTheme` (panel.edge с альфой токена 0,45, mark.keyline, card.navy) |
| 2 | В overlay `Avatar` — UImage с MID; диск цвета команды и монограмма — только фолбэк и откат | `US08TurnPortraitWidget`: `BuildDefaultTree` (BindWidget `Panel`, `Avatar`, `DiscBox`, `Disc`, `AvatarImage`, `MonogramText`, `NameText`, `StatusText`, `Stats`, `HpText`, `TrackerRow`), `SetPortrait(Key)` по реестру `Config/Cards/S08CardMedia.json` (ключи `king-arthur`, `medusa`, `king-arthur/merlin`, `medusa/harpies`), `/Game/S08/UI/Common/WBP_UmPortrait` (генерируется `ue_author_um_hud.py`) |
| 3 | Нет ключа или PNG → монограмма на диске card.navy, text.primary type.heading, Warning в лог; гарпия — цифра 1–3 (ВР-CP09) | `UmPortrait::FallbackText`, `ApplyPortraitLook` (`PORTRAIT fallback id=… reason=…` один раз на ключ) |
| 4 | `-S08PortraitLegacy` — прежний вид | `S08ArtLook::PortraitAvatars()` (флаг CP-02) |
| 5 | Кэп 1,6× в физических px (ВР-CP04) | `UmPortrait::CappedSu`: su = min(показ, 1,6 × px круга источника / (DPI × масштаб UI)); излишек — отступ (круг по центру ячейки 64 su) |
| 6 | Трасса PORTRAIT (ВР-CP10) и гейт | `PORTRAIT id=… tex=… su=… px=… scale=… show=panel side=own|opp state=…` — при смене вида и на каждом кадре-доказательстве; `tools/s08/hud_contract/hud_contract.py check-trace` падает при scale > 1,6 и при `tex=monogram` для ключа из реестра |
| 7, 8 | LOBBY (ВР-CP14), загрузка (ВР-CP15) | экраны ещё на Slate / не созданы — виджет готов к показу `show=lobby|loading`, подключение — шаги SC (дельта 04 §1.3 в screens.csv) |
| 9 | Тесты | `Unmatched.S08.Hud.Portrait.Tree`, `.Fallback`, `.Cap` (`S08/UI/UmPortraitTests.cpp`) |

Подключение (04 §5.1): `S08FlowGameModeTurnHud.cpp` +4 строки (виджет через `Create`, `SetPortrait(Hero->HeroSlug)` из
проекции), `S08FlowGameModeUmHud.cpp` +4 (строки PORTRAIT на кадре). Без явного ключа (галерея, стенд) ключ — slug имени.

## Решения по делегированию (ВР-VS2-NN)

- **ВР-VS2-31.** Кромка круга: снаружи mark.keyline 1 su, внутри panel.edge 1,5 su с альфой токена 0,45 (02 §6.4 толщин
  не задаёт; CP-07 может поменять); доли считаются от показанного диаметра.
- **ВР-VS2-32.** Ключ портрета — `heroSlug` проекции (`FS08BoardFighter::HeroSlug`, формат реестра `king-arthur`); без него
  (галерея, стенд) — slug имени героя.
- **ВР-VS2-33.** Шрифты портрета ставятся ещё раз при запуске: шрифт FCoreStyle (составной шрифт в коде) не переживает
  сериализацию WBP — без этого WBP_UmPortrait рисовал «тофу» (найдено на кадре галереи).
- **ВР-VS2-34.** «Пал» (насыщенность 0) — в кадр креста на сердце (`SetHeartFallen`, контакт + 1100); затухание
  проигравшего (0,6, 400 мс) — API `SetPortraitState(Loser)`, его вызывает экран GAMEOVER (UUmScreenGameOver, шаг H15).
- **ВР-VS2-35.** В виджете хода круг остаётся 42 su внутри холста кольца 64 su (кольцо AB-5 не трогаем); 80 su героя и
  40 su помощника (02 §6.4) — блоками PANEL-LOC / PANEL-OPP (H4, HB-18…HB-21).

## Проверки

- UE: `Unmatched.S08.Hud.Portrait.Tree`, `.Fallback`, `.Cap` — зелёные; весь `Unmatched.S08` 246/246, `Unmatched.S09` +
  `Unmatched.S10` 158/158 (IconMotion.TurnPortrait и .TurnHudRollbacks — прежний вид кольца, трекера, сердца не изменился).
- pytest: `tools/art/cards` 20/20 (`test_portrait_disc_material.py`), `tools/s08/hud_contract` 58/58 (гейт PORTRAIT);
  `hud_contract.py validate` PASS (G-TOKENS).
- Кадр галереи `-S08IconGallery -S08IconGalleryPortraits` в editor `-game` (не упаковка, 1080p): аватары Medusa и King
  Arthur в круге с кромкой, кольцо хода снаружи, текст имени / статуса / HP читается; трасса
  `PORTRAIT id=king-arthur tex=/Game/S08/UI/Portraits/T_Portrait_king_arthur… scale=0.087`, `check-trace` PASS. Цвет
  аватара против исходного PNG: ue ≈ 0,9 × src + 19 по каналам (размытие мипа на 42 px, без сдвига тона). Лист цвет /
  серый / дейтеранопия: круг отделён кромкой от panel.bg. Листы и кадр с аватарами — вне git
  (`scraped-data/derived/visual-evidence/CP-08/`, ВР-CP12); все открыты (Read).
- Число инструкций пиксельного шейдера не снято: `MaterialEditingLibrary.get_statistics` в коммандлете возвращает 0 для
  UI-материала; замер — шаг «Кадры» (ProfileGPU).

## Отложено (шаг «Кадры» VS-2, packaged)

- Кадры наборов A и B на Marmoreal original и Sarpedon original (шесть фигур v2), свой и чужой ход, 1080p 100 / 150 % и
  720p 100 %: в PANEL-LOC / PANEL-OPP аватары, кольцо снаружи, монограмм нет; трасса PORTRAIT tex ≠ monogram, scale ≤ 1,6.
- Кадр с `-S08PortraitLegacy` — прежний вид.
- Показы LOBBY / ROOM / загрузка / GAMEOVER — с их экранами (SC-шаги, H15); строка реестра 03 и статус карточки — в
  основной копии после интеграции (ВР-PL09).

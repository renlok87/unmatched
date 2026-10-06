# Правила HUD: «панель = класс», токены стиля, гейты по трассам, StringTable / why.*

Срез 2026-09-29, волна 4, задача W4-D (для исполнителя W4-C). **Статус: предложено.** Нормативы 02/03/17 этим документом не меняются: правки к ним — только предложенным diff ([proposals](../../../art-pipeline/proposals/)).

Основание: меморандум engine-gate §1 п.8 и таблица («панель = класс, токены стиля, гейты по трассам SHOT widget, StringTable/why.*»), исследования R3.0–R3.2. **Решение пользователя 2026-09-28: «HUD: гибрид UMG сейчас»** ([журнал решений](../../../game-design/decisions/2026-09-29-render-ui-user-decisions.md)). Рекомендация меморандума была «правила сейчас, порт в S12»; пользователь выбрал начать гибрид UMG сейчас. CommonUI этим решением не вводится.

| Файл | Что это |
| --- | --- |
| [hud-style-tokens.json](hud-style-tokens.json) | единая таблица токенов (цвета hex sRGB, кегли, отступы, радиусы, иконки, длительности) |
| [why-reasons.json](why-reasons.json) | коды причин недоступности `why.*` с текстами RU/EN для StringTable `ST_Why` |
| [tools/s08/hud_contract/hud_contract.py](../../../../tools/s08/hud_contract/hud_contract.py) | `validate` (токены, `why.*` против 02 §4.2), `linear` (hex → linear), `check-trace` (гейт `SHOT widget`) |
| [tools/s08/hud_contract/test_hud_contract.py](../../../../tools/s08/hud_contract/test_hud_contract.py) | 5 юнит-тестов |
| [tools/s08/hud_contract/hud_tokens_codegen.py](../../../../tools/s08/hud_contract/hud_tokens_codegen.py) | VS-1 HB-03 (ВР-77): JSON токенов → `unreal/Unmatched/Source/Unmatched/S08/S08HudTokens.generated.h` (namespace `S08HudTokens`, алиасы раскрыты, `kTokensJsonSha256`); `validate` падает «header stale» |
| [tools/s08/hud_contract/hud_theme_import.py](../../../../tools/s08/hud_contract/hud_theme_import.py) | VS-1 HB-04: тот же JSON → `/Game/S08/UI/Theme/DA_UmHudTheme` (`UUmHudTheme`, `Source/Unmatched/S08/UI/UmHudTheme.h`): цвета через `FromSRGBColor`, шрифты, отступы, радиусы, длительности, 29 кистей-фолбэков скинов (ВР-HB06), sha256 JSON; ассет — `git add -f` (П9) |

## 0. Что уже есть (факт, R3.0)

Весь интерфейс — Slate внутри `AS08FlowGameMode` (`S08FlowGameMode.cpp` ≈5,7 тыс. строк, из них ≈1,7 тыс. — отображение; `RefreshHud` на каждое событие пересоздаёт ≈80 виджетов). 51 вызов `FCoreStyle::GetDefaultFontStyle`, нет `FSlateStyleSet`, нет таблицы токенов (AD-OPEN-23). Модели уже отделены и тестируются без мира: `FS09HudModel`, конечный автомат `S09ManeuverUi`, хелперы `S08ArtHud`. В `Unmatched.Build.cs` нет модуля UMG, в Content нет WBP. Захват кадров и масштаб 150 % от фреймворка не зависят (UMG рисуется через Slate; `SGameLayerManager` оборачивает всё в `SDPIScaler`).

## 1. Гибрид UMG (решение пользователя)

- Пользовательские блоки HUD (UI-HUD-TOP, UI-HUD-BOARD, UI-HUD-HAND, UI-HUD-DECKS, UI-HUD-COMBAT, UI-HUD-PENDING, UI-HUD-LOG, UI-HUD-CONN, UI-HUD-PANEL-LOC, UI-HUD-PANEL-OPP, UI-HUD-OPP-HAND) и экраны UI-SCR-* переводятся на UMG: C++-база (`UUserWidget` с `meta=(BindWidget)`) держит логику и тестируемые методы, вёрстка — в `WBP_<UI-ID>`.
- Slate остаётся для операторской панели F10, трасс, проб (`-S09HudProbe`, key-probe) и мира-независимых хелперов.
- Модели не меняются: `FS09HudModel`, `S09ManeuverUi`, `S08ArtHud` остаются источником данных и 149 автотестов работают на них.
- Порядок: сначала один блок (UI-HUD-HAND) и одна панель (UI-HUD-PANEL-LOC) в UMG поверх той же модели — bench «fx/ui» меморандума §2: bbox UMG = Slate ± 1 px, ΔGT p95 ≤ 0,3 мс; затем остальные блоки. Модуль `UMG` добавляется в `Build.cs`.
- CommonUI — после MVP вместе с геймпадом (D-05): его маршрутизация ввода не проверена против опроса `WasInputKeyJustPressed` и S09 key-probe.

## 2. Правила (нормативно для нового кода HUD)

**П1. Панель = класс.** Каждый пользовательский блок и экран — отдельный класс-виджет с одним входом данных: `ApplyModel(const FS09HudModel&)` (или узкая структура для блока). Новые панели не добавляются инлайном в `RefreshHud`. Класс называется по UI-ID из 02 (`UUmHudHand` / `WBP_UI_HUD_HAND`), ID же пишется в трассу. Логика видимости и текста — в модели или в C++-базе, не в графе WBP.

**П2. Обновление только по событию.** Никакого Property Binding (опрос каждый кадр) и тика виджета ради данных: панель перерисовывается, когда модель изменилась (как сейчас по событию снапшота). Background Blur и Retainer Box — только после замера (нагрузка на GPU). Пересборка дерева на каждое событие заменяется обновлением существующих виджетов.

**П3. Токены стиля.** Цвета, шрифты, кегли, отступы, радиусы, размеры иконок и длительности берутся из одной таблицы ([hud-style-tokens.json](hud-style-tokens.json)), а не из литералов. В UE — один ассет стиля (DataAsset или `USlateWidgetStyleContainer`), импортируемый скриптом из JSON; WBP ссылаются на него. Цвет хранится hex sRGB и переводится **только** через `FLinearColor::FromSRGBColor` (AD-OPEN-39, решение по умолчанию); прямое `hex/255` в `FLinearColor` запрещено. Новые вызовы `FCoreStyle::GetDefaultFontStyle` запрещены; шрифт — composite font с кириллицей (Roboto движка проверен по cmap; фирменный — AD-OPEN-24).

**П4. Гейты по трассам, а не по пикселям.** Для каждого показанного блока при съёмке (`SHOT`) пишется строка из нарисованной геометрии:

```
SHOT widget id=<UI-ID> state=<состояние модели> bbox=<x>,<y>,<w>,<h> geom=painted visible=<0|1>
```

`bbox` — пиксели viewport из фактически нарисованной геометрии (`UUserWidget::TakeWidget` → `SWidget` → `GetPaintSpaceGeometry`, как у `SHOT plate … geom=painted`); не нарисован — `geom=unpainted`, это ошибка трассы. Гейт: `python tools/s08/hud_contract/hud_contract.py check-trace <Unmatched.log>` (UI-ID из 02, bbox в кадре, `geom=painted`). Новых неоновых маркеров не добавлять. На старте переноса существующие маркеры S09/S10 (≈17 цветов `SColorBlock`, `S08FlowGameMode.cpp:3821–3867`) уходят за флаг `-S09Markers`, а пиксельные гейты `tools/s09/run-hud-*.ps1` переводятся на эту трассу (вариант D из R3.1). Кадр остаётся иллюстрацией.

**П5. Локализация: StringTable и `why.*`.** Каждая новая пользовательская строка — `LOCTEXT`/`NSLOCTEXT` или StringTable (`ST_Hud`, `ST_Why`), динамика — `FText::Format` с именованными аргументами. Причины недоступности (P2) — коды `why.*` ([why-reasons.json](why-reasons.json), ключи 02 §4.2) с аргументами; модель (`S09ManeuverUi`) отдаёт код и аргументы, виджет — локализованный текст. Английская проза остаётся только в трассе. Автотесты сверяют коды, не прозу. RU и EN со старта (D-08), язык по умолчанию RU (UI-ACC-010). Массовый перевод существующих ≈250–300 литералов — GD-048; правило действует для нового и переносимого кода.

**П6. Масштаб и окно.** Проверка каждого блока при 1920×1080 и 1280×720, масштаб интерфейса 100 % и 150 % (кривая DPI `UUserInterfaceSettings`); обязательный выбор не перекрывается (трасса `PLATE overlapReachable=`). Якоря — в WBP, не абсолютные смещения из C++.

**П7. Ввод.** Виджеты HUD не забирают игровые клавиши: режим ввода `GameAndUI` без захвата клавиатуры фокусом виджета; S09 key-probe (`SimulateSlateKeyProbe`) даёт те же строки `S09PROBE`, что до переноса.

**П8. Бюджет.** HUD ≤ 0,5 мс GT p95 и ≤ 0,3 мс GPU при 1080p, кадр пересборки ≤ 2 мс (предложение R3.0); замер — packaged Development, ProfileGPU без лимита FPS, `stat Slate`/`stat UMG`, bench «ui» меморандума §2.

**П9. Бинарные ассеты.** `Content/` в `.gitignore`: WBP, ассет стиля и StringTable добавляются в git принудительно (`git add -f`, меморандум G09), либо генерируются скриптом (MCP UMGToolSet проверен smoke-тестом 2026-09-27). Иначе свежий worktree и слияние в `fix/admin-panel` потеряют вёрстку.

## 3. Чек-лист для W4-C

- [ ] `UMG` в `Unmatched.Build.cs`; C++-база панели с `ApplyModel` и `BindWidget`; первый блок UI-HUD-HAND и UI-HUD-PANEL-LOC поверх `FS09HudModel`.
- [ ] Ассет стиля из `hud-style-tokens.json` (скрипт импорта), цвета через `FromSRGBColor`.
- [ ] `ST_Why` из `why-reasons.json`; модель отдаёт коды `why.*`.
- [ ] Строки `SHOT widget …` для перенесённых блоков; `hud_contract.py check-trace` = PASS на packaged-логе.
- [ ] Маркеры за `-S09Markers`; план перевода пиксельных гейтов S09/S10.
- [ ] Bench «ui»: bbox UMG = Slate ± 1 px, ΔGT p95 ≤ 0,3 мс, кадры 1280×720 и 150 %.
- [ ] `git add -f` для WBP/стиля/StringTable или скрипт генерации.

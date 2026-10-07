# HB-47 — лоадеры и скелеты: UUmSpinner, полоса прогресса, скелет строк (04 §3.3)

VS-3, шаг U3, 2026-10-07, ветка `feat/visual-vs3` (worktree `C:/tmp/wt-visual`). Карточка — `hud.csv` HB-47; 04 §3.3,
§1.1, §1.3; 02 §11.2; значок `loader-spinner` (IC-16), скины `progress.track` / `progress.fill` (HB-08 / HB-10).
Пользователь в HUD — панель колоды [HB-28](../HB-28/README.md).

**Статус:** виджеты, трасса, тесты готовы; в HUD — скелет панели колоды и задержка спиннера скана карты. Код — коммит
`fa8ac76c`; `WBP_UmSpinner` сгенерирован и закоммичен вместе с HB-27 / HB-28 (`4a3ca23b`, общий скрипт
`ue_author_um_hud.py`). Кадр панели во время загрузки списка в партии (задержка через
`tools/s10/drop-graphql-reply-proxy.cjs`, обе доски, 1080p и 720p 150 %) — шаг «Кадры». Приёмка — «по делегированию».
**Откат:** `-S08SlateHud` (весь HUD) — Slate-строки «loading the deck list…»; `-S08SlateHud=deckpanel` — то же для панели.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| 1. `UUmSpinner`, `UmProgressBar`, `UmSkeletonRows` | `S08/UI/UmSpinner.{h,cpp}` — `UUmSpinner` (`/Game/S08/UI/Common/WBP_UmSpinner`): `US08AnimatedIconWidget` `loader-spinner` 32 или 48 su, контрактный цикл `cycle` — 8 ступеней по 45° через `icon.spinner.step.ms` 125, reduced — 250 (ветка reduced контракта). `S08/UI/UmProgressBar.{h,cpp}` — `UUmProgressBar`: `UProgressBar` 480×8 su со скинами `progress.track` / `progress.fill` и подписью этапа `type.caption` `text.secondary` под ней; без подписи дольше 2 с — `HasCaptionDefect`. `S08/UI/UmSkeletonRows.{h,cpp}` — `UUmSkeletonRows`: N строк `panel.bg.inset` с линией `panel.divider` 1 su, пульс прозрачности 0,6 ↔ 1,0 за 900 мс (косинус от 1,0), reduced — статично 0,8 (ВР-VS3-34). |
| 2. `FUmDelayedShow` | `UmSpinner.h`: показ только после 300 мс ожидания, скрытие сразу по готовности; повторный `Begin` не сдвигает начало. Скрытый лоадер свёрнут (`Collapsed`): Slate его не тикает. |
| 3. В HUD | панель колоды до ответа `gameDeckLists` — 6 строк скелета (HB-28); скан карты — спиннер 32 su на месте скана только после 300 мс загрузки (`UUmCardWidget::ApplySpinner`, CP-15); аватар — монограмма до PNG (CP-08, как было). |
| 4. Экраны | те же виджеты берут BOOT, LOBBY, загрузка партии (VS-7); в этом шаге не подключались. |
| 5. Трасса | `HUD-LOADER kind=spinner\|progress\|skeleton shown=0\|1 where=<owner> waitMs=<мс> reduced=0\|1` (у полосы ещё `caption=0\|1 percent=`), только при смене; панель колоды пишет её из `TickDeckPanel`. |
| 6. Тесты | `Unmatched.S08.Hud.Loader.Delay` (290 мс — скрыт, 310 мс — виден, готово — скрыт сразу; спиннер, скелет, полоса, правило подписи 2 с), `.Reduced` (пульс 0,6…1,0 за 900 мс, reduced статичен; контракт спиннера: 45° на 130 мс, reduced — 0° на 130 мс и 45° на 260 мс), `.Tree` (`S08/UI/UmLoaderTests.cpp`). |

## Решения по делегированию

| № | Решение | Почему |
|---|---|---|
| ВР-VS3-34 | Reduced motion: скелет статичен на 0,8 — середине пульса; пульс в обычном режиме стартует с 1,0 в кадр появления | карточка задаёт только «reduced — статично»; середина не темнее и не ярче пульса |

## Проверки

- `Unmatched.S08.Hud.Loader.*` — 3 из 3; полный прогон `Unmatched.S08 + S09 + S10` — 459 из 459 (HB-28).
- Скрытый спиннер не тикнул ни разу (`GetTickCount() == 0` в тесте); стоимость видимого лоадера — один `ApplyView`
  панели в кадр (p95 0,0005 мс вместе с панелью, тест `.Rows` HB-28).
- Кадры галереи (HB-28): состояние «loading» на +200 мс — пустое окно списка, на +600 мс — 6 строк скелета с
  разделителями; «failed» — «Сервер недоступен» и «ПОВТОРИТЬ»; reduced (`marm-1080-100-reduced-*`) — скелет без пульса.
  Трасса галереи: `HUD-LOADER kind=skeleton shown=1 where=deckpanel waitMs=600 reduced=0`.

## Что не сделано в этом шаге

- Полоса прогресса в BOOT / загрузке и скелет LOBBY — экраны VS-7.
- Кадр скелета в партии при задержанном `gameDeckLists` (прокси) — шаг «Кадры».

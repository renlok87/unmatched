# SC-32 — RECONNECT: ручное переподключение и истёкшая сессия

VS-7, шаг S5, 2026-10-08, ветка `feat/visual-vs7`. Карточка — `screens.csv` SC-32; 04 §1.9; макет CX-33
`art/imagegen/sc32-reconnect-manual-codex/` (ВР-VS5-SC32-01…03). Общее (оверлей, сборки, тесты, гейты, инструменты) —
[SC-31](../SC-31/README.md).

**Статус:** UE-часть готова; manual проверен вживую (editor-build, `s5c`), expired — тестом; packaged-кадры и листы — шаг
«Кадры». **Откат:** `-S08SlateHud=reconnect`.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| manual | после 5 × 10 с обрыва: значок `resource-connection-lost` (стрелка → X — смена формы), строки попытки нет, «Пропущено событий», Running; «ВЫЙТИ В ЛОББИ» обычная слева, «ПЕРЕПОДКЛЮЧИТЬ» — единственная главная справа, одной ширины, через 16 su (ВР-VS5-SC32-01). «Переподключить» начинает цикл попыток заново и вызывает `RetryMatchLoad` (сокет — сейчас). |
| expired | сессия умерла во время партии (`IsSessionExpired`, GD-038): «Сессия истекла — войдите снова» (`type.title`), одна главная «КО ВХОДУ», без «Переподключить», попыток и лобби (ВР-VS5-SC32-02/03); токены уже очищены `EnterSessionExpired`; маршрут держит LOGIN, пока не нажато «Ко входу» (`UmEndHoldsRoute`). |
| Строки | `screens.reconnect.retry`, `.session.expired` — были; `screens.reconnect.to.login` «Ко входу» / "To sign-in" — новая (дельта CX-33). |
| Трасса | `SHOT widget id=UI-SCR-RECONNECT state=manual … primary=retry card=302`, `state=expired … primary=login`; `RECONNECT expired -> LOGIN`. |

## Решения по делегированию

| № | Решение | Почему |
|---|---|---|
| ВР-VS7-60 | expired показывается, только если сессия истекла во время партии (на прошлом кадре — `Started` или обрыв); маршрут держит LOGIN до «Ко входу» | вне партии истёкшую сессию уже показывает LOGIN (SC-07); старым токеном не переподключаемся |

## Проверка

- `Unmatched.S08.Hud.Screens.Reconnect.Tree`: manual — X, нет строки попытки, «Переподключить» единственная главная, нажатие;
  expired — заголовок, «Ко входу» единственная главная, ни «Переподключить», ни «Выйти в лобби», карточка 218 su, нажатие.
  `.Reconnect.Model`: manual ровно с 50 с, expired сильнее остальных состояний.
- Живой `s5c` (720p, Sarpedon original): `RECONNECT state=manual attempt=5 … lost=50029`, `SHOT … state=manual … primary=retry
  card=302`, «Переподключить» (`-S08EndDrive retry`) → `restoring` → выход. Кадр открыт (Read).

## Кадры

Полный кадр — `scraped-data/derived/visual-evidence/SC-32/` (под вуалью сканы карт руки), индекс
`visual-evidence-index.json`; в git — `reconnect-manual-card-720p-100.jpg` (только карточка).

## Не сделано в этом шаге

- expired вживую (отозванный refresh-токен на стенде S10) — шаг «Кадры» / стенд; сейчас — тест.
- Набор F packaged, листы, G-READ / G-GRAY / G-LOOK, реестр 03 — шаг «Кадры».

# SC-16 — ROOM: «Просмотр колоды»

VS-7, шаг S3, 2026-10-08, коммит `323599df`. Карточка — `screens.csv` SC-16; 04 §1.4, §1.7 (режим колоды), F-05; макет CX-30
`art/imagegen/sc16-room-deck-codex/` (ВР-VS4-SC16-01, ВР-VS4-SC14-13). Общее — [SC-14](../SC-14/README.md).

**Статус:** UE-часть готова, живая проверка editor-build, по делегированию. **Откат:** `-S08SlateHud=room` (и `=inspect` —
без модали колоды: трасса `INSPECT deck refused`).

| Пункт | Где и как |
|---|---|
| Строка | `DeckCount` «Колода: 30 карт» (`screens.room.deck.count`, RU-plural; сумма `Card.count` каталога героя — `cardList(heroId)`) и `DeckButton` «Просмотр колоды»; без героя — только недоступная кнопка с `why.room.no.hero` «Выберите героя» (текстом рядом и подсказкой, ВР-VS4-SC14-13). |
| Модаль | своя `UUmScreenInspect` комнаты в `Modals` корня, режим колоды `UmInspect::FromList(…, EUmInspectSource::Room)` из каталога героя: сетка 150×208, «×N» рядом, порядок каталога (состав без порядка, F-05); Esc / I / Tab / Backspace — модали. |
| Звук | `UI-PANEL-OPEN` / `UI-PANEL-CLOSE` (ВР-VS7-34). |
| Трасса | `INSPECT open source=room mode=deck grid=<n> copies=<сумма>`, `SHOT widget id=UI-SCR-INSPECT … state=deck`, `SHOT widget id=UI-SCR-ROOM … state=deck … deck=<n> deckButton=0|1`. |

| № | Решение | Почему |
|---|---|---|
| ВР-VS7-34 | Звук модали колоды в ROOM — `UI-PANEL-OPEN` / `-CLOSE` (08), не `CRD-INSPECT-OPEN` карточки | 08 SC-16: «открыть / закрыть — вызвать UI-PANEL-*»; звуки инспектора идут сами только от состояния партии |

Проверка: `ROOM deck hero=<Arthur> unique=16 copies=30`, `hero=<Medusa> unique=11 copies=30` — 30 и 30, как в БД; `INSPECT open
source=room mode=deck grid=11 copies=30` (Medusa, `s3a` / `s3g`), `grid=16 copies=30` (King Arthur, `s3c`). Тест `Room.Tree`: «Колода:
30 карт», кнопка доступна с героем и недоступна без него. Открыты: deck 1080p (сканы карт, ×3 / ×2 рядом), host-picked, host-waiting.

Кадры: модаль показывает сканы карт — PNG в `scraped-data/derived/visual-evidence/SC-16/`, в git — `deck-row-1080p-100.jpg`
(строка колоды, только текст) и индекс. Не сделано: набор G, листы, реестр 03 — шаг «Кадры»; текст карт в режиме колоды ROOM пуст
(`cardList` не отдаёт текст — видны сканы; в партии текст идёт из `gameDeckLists`).

# SC-15 — ROOM: доска комнаты (`UUmBoardCard`)

VS-7, шаг S3, 2026-10-08, коммит `323599df`. Карточка — `screens.csv` SC-15; 04 §1.4 «Доска», ВР-H11; макет CX-30
`art/imagegen/sc15-room-board-codex/` (ВР-VS4-SC14-10, ВР-VS4-SC15-01). Общие сборки, тесты и гейты — [SC-14](../SC-14/README.md).

**Статус:** UE-часть готова, живая проверка editor-build, по делегированию. Набор G packaged и листы — шаг «Кадры».
**Откат:** `-S08SlateHud=room`.

| Пункт | Где и как |
|---|---|
| Блок | «Доска» (`screens.room.board.title`, `type.heading`), две `UUmBoardCard` 240×136 su (720p — 240×124): Marmoreal original слева, Sarpedon original справа; миниатюра всей иллюстрации карты (`T_BoardThumb_*`, только LAN, вне git), имя из `boardList` (запасное — AGENTS.md). |
| Доска комнаты | `FS08RoomState.BoardId`: кромка 3 su `state.pending` и чип `check.on` с глифом IC-57 `ui-check` 24 su в свободном углу (не поверх иллюстрации). |
| Вторая | иллюстрация 0,4, имя `text.secondary`, подсказка и текст рядом — `why.room.board.locked` «Доску выбирают при создании комнаты»; нажатия и наведения нет — смены доски в комнате не делаем (ВР-H11). |
| Трасса | `ROOM board=<id>` при входе / смене комнаты; `SHOT widget id=UI-SCR-ROOM … state=board … block=1 board=<marmoreal|sarpedon> locked=1 thumbs=2` (ВР-VS7-40). |

Проверка: `ROOM board=c121b47f8d6eb28daccb76d05` в комнате на Marmoreal (`s3a`, `s3g`, `s3h`), `ROOM board=c7fa64a26c29a0835f2383e63`
в комнате Sarpedon, созданной вторым игроком (`s3b2`; `room_actor.cjs --board`), и в VS_AI на Sarpedon (`s3d`, `s3e`) — совпадает с
`boardId` ответа комнаты. Тест `Room.Tree`: доска комнаты отмечена (чип показан), вторая заблокирована, причина. Открыты: host-picked
1080p (Marmoreal), guest-waiting-taken-sarpedon 720p (Sarpedon), host-ready-ai класса S.

Кадры: на всех видны миниатюры карт — индекс `visual-evidence-index.json`, PNG в `scraped-data/derived/visual-evidence/SC-15/`.
Не сделано: набор G packaged, листы, реестр 03 — шаг «Кадры».

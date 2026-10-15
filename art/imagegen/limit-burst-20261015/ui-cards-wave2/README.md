# Портреты ростера — вторая волна

Дата: 2026-10-15. Статус: **предложено**. Четыре новых оригинальных raster source candidates; **не runtime-ready**.

| Кандидат | Предложенный ключ | Исходник |
|---|---|---|
| Йенненга | `portrait:yennenga` | [portrait-source.png](yennenga/portrait-source.png) |
| Синдбад | `portrait:sinbad` | [portrait-source.png](sinbad/portrait-source.png) |
| Красная Шапочка | `portrait:little-red` | [portrait-source.png](little-red/portrait-source.png) |
| Дракула | `portrait:dracula` | [portrait-source.png](dracula/portrait-source.png) |

Потребитель — существующий generic `UmPortrait::Find` → `UmCardMedia::FindPortrait` по slug героя в PANEL, ROOM, LOBBY, загрузке и GAMEOVER. Этих четырёх ключей нет в просмотренном `S08CardMedia.json`; оригинальных generated portrait-файлов по этим именам не найдено в `art/`. Коммерческие scrape avatars существуют: здесь закрывается пробел собственного исходника, а не отсутствие любого изображения. Готовые принятые портреты не заменены.

У Sinbad, Little Red и Dracula связь heroLink подтверждена живым `/__art-hub/data` и `docs/art-pipeline/hero-links.json`. **У Yennenga heroLink отсутствует** в обоих источниках. Реальный roster slug `yennenga` и имя подтверждены `scraped-data/api/normalized/yennenga.json`, готовый проектный дизайн и карточка ASSET также существуют. Это source candidate по явно выбранному координатором slug; отсутствие связи оставлено открытым, связь и наличие в текущей БД не выдуманы. Снимок хаба — `art-hub-roster-snapshot.json`, хеши normalized roster и остальных входов — `source-hashes-before.json`.

Сделано встроенным `image_gen.imagegen`: **4 генерации, 4 выбранных g1**, без повторов и без CLI/API fallback. SYNTX и Tripo не использованы. Каждый `portrait-source.png` — побайтовая копия соответствующего `portrait-g1.png` и оригинала инструмента; оригиналы сохранены на месте. Фактический размер каждого source — 1254×1254 RGB, без ресайза, ретуши и перекодирования. Exact prompts, local task-cards, metadata лежат в каждой папке, журнал — `generation-records.json`.

Все project design front refs просмотрены перед генерацией. Каждый source PNG открыт через `view_image`, затем открыт [общий лист ревью](review-sheet.png): project design, квадратный исходник, полный круг 160 px, серый 160 px, native80 с увеличением ×2 nearest и отдельный native80 без увеличения. Во всех четырёх круг `cx=0.5, cy=0.5, d=1.0` сохраняет голову и головной убор, лица и оба глаза читаются. Tight crop не заявляется.

Ограничения: верхний запас меньше номинальных 8–12% из промпта; это сохранено, потому что реальный круг головы не режет. У Little Red декоративный мотив застёжки переинтерпретирован. У Sinbad, Yennenga и Dracula есть изменения мелкого орнамента; у Dracula чуть заострены уши. Новые повторы ради деталей одежды не делались. У Sinbad край хвоста тюрбана частично уходит в круг, второстепенная деталь. Фон визуально navy; равенство каждого пикселя `#061623` не заявляется. Все визуальные выводы и оговорки — `visual-review.json`, `metadata.json`.

Машинная проверка — `verification.json`: 15 из 16 входов сохранили SHA-256, включая все 4 image refs. Контекстная `cards-portraits.csv` параллельно изменилась: координатор подтвердил обновление статусов своих CP23/CP24 (коммит d0e07ea3). Поэтому `source_unchanged=false` сохранён честно; before hashes не переписаны. Все 4 исходника совпали с оригиналами инструмента. Отдельные diagnostic previews создаёт `_tools/build_review.py`; production source PNG он не изменяет. Manifest охватывает пакет.

За интегратором остаются официальный статус source, отсутствующий heroLink Yennenga, ключи реестра, импорт текстур, утверждение кропа на реальных экранах и LAN-кадры. Здесь нет правок runtime, кода, ledger, общих реестров или git. Первая волна `ui-cards/` не изменялась. Фоновые сервисы и длительные процессы не запускались.

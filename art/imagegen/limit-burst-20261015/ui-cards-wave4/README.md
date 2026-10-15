# CP-30 — оригинальные портреты помощников

Дата: 2026-10-15. Статус: **предложено**. Четыре новых source candidates; **не runtime-ready**, формальная арт-приёмка не объявлена. CP-30 прочитана до вызовов и сохранена в `CP-30-snapshot.json`.

| Канонический дизайн / source | Фактический label | Владелец | Текущий runtime media key |
|---|---|---|---|
| [Bess Houdini](bess-houdini/portrait-source.png) | Bess | Harry Houdini | `portrait:harry-houdini:bess` |
| [Huntsman](huntsman/portrait-source.png) | Huntsman | Little Red | `portrait:little-red:huntsman` |
| [Rosencrantz](rosencrantz/portrait-source.png) | Rosencrantz & Guildenstern | Hamlet | `portrait:hamlet:rosencrantz--guildenstern` |
| [Ashigaru](ashigaru/portrait-source.png) | Honor Guard ×2 | Oda Nobunaga | `portrait:oda-nobunaga:honor-guard` |

Владельцы и labels проверены по живому `/__art-hub/data` и index-decoding raw `scraped-data/api/heroes/{harry-houdini,little-red,hamlet,oda-nobunaga}.json` до вызовов; evidence — `art-hub-roster-snapshot.json`, `raw-owner-mapping.json`. Seed не использован. Matching source portraits по этим четырём именам в `art/` не найдены; media keys отсутствуют в `S08CardMedia.json`. Коммерческие avatars могут существовать, здесь создаётся собственный source candidate.

**Различие ключей R&G:** текущий `UmPortrait::SlugOf` удаляет `&`, а два пробела вокруг него превращает в два дефиса. ROOM и HUD передадут `hamlet/rosencrantz--guildenstern`, поэтому primary key выше содержит двойной дефис. Python `convert_card_media.slug()` сжимает любую последовательность небуквенных символов и дал бы `portrait:hamlet:rosencrantz-guildenstern`. Этот normalized alias записан отдельно; решение для импорта/алиасов остаётся открытым. Код и ключи рантайма здесь не исправляются.

**Различие группы R&G:** референс — канонический одиночный проектный Rosencrantz, а фактическая запись называет пару. Новый source сохраняет одного персонажа; соответствие полной паре и её художественная приёмка не заявлены. Для Honor Guard один source — представитель группы двух помощников, оба имеют один label и один runtime key.

Графические входы — только собственные canonical 1a `concept-<key>-codex/design/<key>-front.png`, без актёров, photos, коммерческих сканов и UI. Существующий статус дизайнов не наследуется новым портретом. Каждый референс и каждый source открыт через `view_image`.

Встроенный `image_gen.imagegen`: **4 вызова, 4 выбранных g1, 0 ретраев**, без CLI/API fallback, SYNTX и Tripo. Каждый `portrait-source.png` и `portrait-g1.png` — побайтовая копия tool original, 1254×1254 RGB, без ретуши, ресайза и перекодирования. Оригиналы оставлены на месте. Exact prompts, local task-cards и metadata — по папкам; журнал с хешами — `generation-records.json`; координатору для учёта — `ledger-handoff.json`. Ledger не изменялся, стоимость built-in в кредитах неизвестна и не выдумана.

[Лист ревью](review-sheet.png) лично открыт: canonical design, source square, full100 circle160, gray160, native80 ×2 nearest, отдельные native40 и native80 без увеличения. Полный круг `cx=0.5, cy=0.5, d=1.0` сохраняет все головы, перья и ширину jingasa. На source оба глаза видны, нет текста, рамок, UI, рук или оружия. На 40 px читаются отличительные силуэты; мелкие детали лица ограничены и не выданы за финальную арт-приёмку. Мелкий орнамент, пайетки, мех и крепления могут отличаться, точный flat navy `#061623` не гарантирован. Подробности — `visual-review.json`.

`verification.json` отдельно проверяет четыре image refs и четыре tool copies. Общий `source_unchanged=false` оставлен честно: контекстная `cards-portraits.csv` меняется параллельно координатором; before hashes не переписаны. Все image refs и остальные входы неизменны. `_tools/build_review.py` создаёт только диагностические previews и отчёты, source PNG не меняет. Manifest охватывает пакет; UTF-8 JSON проверены на отсутствие U+FFFD.

Независимое ревью координатора — в соседнем `review-wave4/`. Дальше нужны решения для R&G group/alias, официальный статус source, media registry/import, кроп на реальных экранах и LAN-кадры. Нет правок runtime, кода, ledger, shared registry или git; все предыдущие волны заморожены. Длительные процессы и сервисы не запускались.

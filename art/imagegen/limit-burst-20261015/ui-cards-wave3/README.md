# CP-28 — портреты ростера, волна 3

Дата: 2026-10-15. Статус: **предложено**. Четыре новых оригинальных source candidates; **не runtime-ready**. Карточка CP-28 прочитана и сохранена до вызовов в `CP-28-snapshot.json`.

| Кандидат | Предложенный media key | Widget key | Размер HUD |
|---|---|---|---|
| [Патрокл](patroclus/portrait-source.png) | `portrait:achilles:patroclus` | `achilles/patroclus` | 40 su |
| [Виглаф](wiglaf/portrait-source.png) | `portrait:beowulf:wiglaf` | `beowulf/wiglaf` | 40 su |
| [Баффи](buffy/portrait-source.png) | `portrait:buffy` | `buffy` | 80 su |
| [Доктор Сэттлер](dr-sattler/portrait-source.png) | `portrait:dr-sattler` | `dr-sattler` | 80 su |

В `S08CardMedia.json` этих ключей нет. Generic `UmPortrait::Find` уже разбивает widget key героя/помощника и вызывает `UmCardMedia::FindPortrait`. Matching original portrait-файлов по этим именам в `art/` не найдено. Коммерческие avatars могут существовать: создаётся собственный исходник, принятые изображения не заменяются.

Связи `Patroclus → Achilles/sidekick` и `Wiglaf → Beowulf/sidekick` подтверждены живым арт-хабом и `hero-links.json`. У Buffy и DrSattler heroLink отсутствует, что не скрыто: roster подтверждён raw `heroes/*.json`. В `normalized/dr-sattler.json.name` ошибочно записано `Feint`; index-decoding raw `heroes/dr-sattler.json` даёт настоящее имя `Dr. Sattler`, key `dr-sattler`. Ошибка скрапера не перенесена в портрет или имя пакета. Снимок хаба сохранён.

Графические входы — только **канонические 1a** `concept-<key>-codex/design/<key>-front.png`. У Patroclus/Wiglaf не используются новые 1c, optional Wiglaf alternative или файлы production sheets. Существующая приёмка канонического дизайна не наследуется производным портретом.

Встроенный `image_gen.imagegen`: **4 вызова, 4 выбранных g1**, без повторов, без CLI/API fallback, SYNTX и Tripo. Каждый reference и каждый результат открыт через `view_image`. Выбранные `portrait-source.png` и `portrait-g1.png` побайтно совпадают с tool originals; размер 1254×1254 RGB. Оригиналы инструмента сохранены. Exact prompts/task-cards/metadata — по папкам, полный журнал и SHA — в `generation-records.json`.

[Лист ревью](review-sheet.png) открыт: canonical design, source, круг 160 px, серый 160 px, native80 ×2 nearest и справа настоящий target40/80 без увеличения. Круг полного исходника `cx=0.5, cy=0.5, d=1.0` сохраняет все головы, волосы и гребень. Оба глаза видны на source, текста/UI/рамок нет. В сером типы персонажей различимы.

**Ограничение мини-портретов:** у Patroclus в native40 лицо около 9 px высотой из-за высокого белого гребня; узнаётся силуэт шлема/гребня и синего плаща, но художественная приёмка детального лица в 40 px не заявляется. У Wiglaf на 40 px детали лица также ограничены, читаются шлем с наносником и зелёный плащ. Гребень и шлем не обрезались ради более крупного лица, лишних повторов не делалось. Buffy и Sattler читаются в native80. Мелкие орнаменты и крепления переинтерпретированы; точное совпадение каждого пикселя и flat navy `#061623` не заявлено.

`verification.json` отдельно сообщает неизменность четырёх image refs и побайтовое совпадение четырёх copies. Контекстная `cards-portraits.csv` параллельно обновлена координатором: поэтому общий `source_unchanged=false` оставлен честно, before hashes не переписаны. Остальные входы и все image refs неизменны. Диагностические previews создаёт `_tools/build_review.py`; он не меняет source PNG. Manifest охватывает пакет.

Независимое ревью ведёт координатор в соседней `review-wave3/`; финальная приёмка рантайма здесь не объявлена. Осталось решить missing links, официальный статус source, registry/media keys, импорт, crop на реальных экранах и LAN-кадры. Нет изменений кода, ledger, общих таблиц, runtime или git; предыдущие пакеты заморожены и не менялись. Длительные процессы и сервисы не запускались.

# DE-017 — кольца-кандидаты V-17: кадры редакторного клиента (2026-10-04)

Это не приёмка. Кадры сняты редакторным `-game -Bench` (`live_tune.py bench`, D3D12 SM6, High), чтобы посмотреть
кольца до отчёта. Приёмочные кадры на упакованном клиенте снимает агент приёмки прогона B (G-LIVE).

- **Сцена 0** (`tools/s08/fixtures/move-draft/<карта>-0-candidates.json`) — MS-S-06 сразу после открытия черновика:
  боец не выбран, ходов нет. Флаги: `-S08MovePlates -BenchMoveDraft=<сцена>`, у Marmoreal ещё `-ConceptPaste`
  (IMPL п. 3: нарисованный задник; `concept-paste mode=on … status=ok`).
- **Трассы** (`<карта>-0.trace.txt`):
  - `MS-DRAFT op=candidates n=4 ids=f-0-hero,f-0-sk0,f-0-sk1,f-0-sk2 autoselect=-`;
  - `MS-HL view … plates=4 ring=4` — по кольцу V-17 на каждого своего бойца;
  - `MS-HL assets plate=M_UM_MovePlate ready=1`.
- **Что на кадрах.** Карты реальные (Marmoreal original, Sarpedon original), все шесть фигур — v2. Задник Sarpedon —
  lit3d, у Marmoreal — нарисованная вклейка. Тонкое кольцо V-17 стоит внутри кольца команды под Медузой и тремя
  Гарпиями. Под Артуром и Мерлином (соперник) колец нет.
- **До/после.** Пара вырезок Sarpedon:
  - «до» — `sarpedon-2-ms-t08-crop-before.jpg`, кадр MS-T-08 (`../ms-t08-editor-2026-10-04/`), колец-кандидатов нет;
  - «после» — `sarpedon-0-candidates-crop-after.jpg`.

  На «до» выбрана Медуза, а в выбранном состоянии кольца гаснут по MS-R-75. Поэтому разница под Гарпиями — это и есть
  V-17.
- **Замечание для арт-приёмки / MS-T-13.** Кольцо V-17 (`#FFC857` 70 %, ширина 1,2 uu) на жёлтых зонах Marmoreal
  малоконтрастно (`marmoreal-0-candidates-crop.jpg`). Числа взяты из 04 §6.1, без подстройки. Подстройка — live tune
  блока `candidate` в `moveSelection`.

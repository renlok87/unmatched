# MS-T-12 — pending MOVE / PLACE (MS-S-12): кадры редакторного клиента (2026-10-05)

Это не приёмка. Кадры сняты редакторным `-game -Bench` (`live_tune.py bench`, D3D12 SM6, High), чтобы посмотреть
подложки V-11 до отчёта. Живой выбор эффекта в бою двух клиентов — агент приёмки прогона C (G-LIVE), если карта с
MOVE-эффектом выпадет; синтетика `-BenchMoveDraft` с блоком `pending` — способ увидеть MS-S-12 без живого эффекта.

- **Сцены** (`tools/s08/fixtures/move-draft/`):
  - `marmoreal-3-pending-move.json` — свой обязательный MOVE «до 3» Медузы (M13), цель M21 (2 шага). Флаги:
    `-S08MovePlates -BenchMoveDraft=<сцена> -ConceptPaste` (IMPL п. 3: нарисованный задник, `concept-paste status=ok`).
  - `sarpedon-3-pending-move-enemy.json` — необязательный MOVE «до 2» чужого Мерлина (S25, `targetsOpponent`, как
    Command the Storms), цель не выбрана. Флаги: `-S08MovePlates -BenchMoveDraft=<сцена>`.
- **Трассы** (`<карта>-3.trace.txt`):
  - Marmoreal: `MS-PENDING open … type=MOVE value=3 optional=0 fighter=f-0-hero owner=own legal=1 targets=8 stay=1
    decline=0`, `MS-BENCH pending … cells=9 targets=8 to=M21`, `MS-HL view source=bench … plates=9 ring=8 paths=1`;
  - Sarpedon: `MS-PENDING open … value=2 optional=1 fighter=f-1-sk0 owner=opponent legal=1 targets=6 stay=1 decline=1`,
    `MS-HL view … plates=6 ring=6 paths=0`.
- **Что на кадрах.** Карты реальные (Marmoreal original, Sarpedon original), шесть фигур — v2 (`ARTLOOK … heroes=v2`).
  Задник Marmoreal — нарисованная вклейка, Sarpedon — lit3d. Подложки V-11 — длинный пунктир (6 штрихов) по кольцу
  на свободных пространствах в пределах `value`; под двигаемой фигурой подложки нет (оставить на месте — кнопка
  панели). На Marmoreal цель M21 — двойное кольцо V-04 (путь идёт через пространство Гарпии, точка пути под фигурой).
  На Sarpedon подложки стоят по правилам Мерлина: пространство Артура (его союзник) не цель, мои бойцы для него — стены.
- **Замечание для арт-приёмки / MS-T-13.** Пунктир V-11 цвета `plate.color` (`#FFC857`) на жёлтых зонах обеих карт
  малоконтрастен — то же, что у V-17 (DE-017). Числа из 03 §4.2 / 04 §6.1, без подстройки.

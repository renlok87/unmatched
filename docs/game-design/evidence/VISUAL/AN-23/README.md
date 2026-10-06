# AN-23 — лист приёмки

Лист собран `tools/art/visual/sheet.py` 2026-10-07 по 02-visual-design.md §13.2.

**Решение:** художественно принято, по делегированию (2026-10-06, ВР-06)
**Дата решения:** 2026-10-06
**Ревью:** ZCode (Z-1), один проход, арт и рамки задачи вместе (02 §13.3)
**Флаг отката:** `-S08FacingLegacy` (S08ArtLook.h, трасса ARTLOOK `facing=v1|legacy`)

## Что проверено (карта AN-23)

Packaged `-Bench` (stamp `f8903fb9`), Marmoreal original `c121b47f8d6eb28daccb76d05` (+`-ConceptPaste`,
окраска задника EN-13 ещё не принята) и Sarpedon original `c7fa64a26c29a0835f2383e63` (lit3d), K1 + K2×1,6 +
K2×2,5, plain и с `-S08FacingLegacy`, `RENDER reference=1`.

### Трейсы FACING (packaged)

- Marmoreal: `FACING fighter=f-1-hero src=spawn rest=-166 cam=-136 off=30 enemy=f-0-sk1`,
  `f-1-sk0 … off=17`; ARTLOOK `facing=v1`.
- Sarpedon: `f-1-hero … off=25`, `f-1-sk0 … off=8`; ARTLOOK `facing=v1`.
- |off| ≤ 45 у всех строк; фигуры команды f-0 в мёртвой зоне 10° (старый угол уже в допуске — трасса по
  карточке пишется только при смене угла).
- `-S08FacingLegacy`: 0 строк FACING (прежнее правило без событий), ARTLOOK `facing=legacy`; пиксельная
  сверка plain против легаси локализована на двух развёрнутых фигурах (K1: 1859/3077 px при |Δ|>24, остальное
  шум фона), т.е. углы «как до изменения» воспроизводятся откатом.

### Живой бой (run-combat-demo.ps1, обе карты, -PlayerView)

- `FACING src=spawn|snapshot|move` — 11 snapshot + 2 spawn на Marmoreal, 12 snapshot + 2 spawn на Sarpedon,
  нарушений |off| > 45 нет.
- ARTLOOK обеих карт: `facing=v1`.
- Демо-гейты зелёные (offReference=0, сходимость seq 66/66 и 50/50), G-CUE `cue_contract.py check-trace` PASS
  на всех четырёх трейсах.

### Глазами (Read PNG)

- Шесть кропов фигур с K1 обеих карт (по 5×): ни одна фигура не стоит спиной — лицо или профиль у всех шести;
  Артур/Мерлин развёрнуты к ближнему врагу (off 30/17 и 25/8), гарпии и Медуза вполоборота к камере.
- Кадр после боя (`s09-combat-result.png`, обе карты): шесть фигур не спиной (AN-25-контекст).
- G-GRAY: лицо/профиль различимы в сером и при дейтеранопии (ряды листа).

## Состав листа

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 2 | Цвет, серый, дейтеранопия | `sheet-01..04` | да |
| 3 | Обе настоящие доски, K1/K2, packaged, `RENDER` | листы 1–3 Marmoreal (вклейка), 3 Sarpedon (lit3d), 4 K2×1,6 | да |
| 6 | Трассы | `FACING`, `ARTLOOK facing=`, `RENDER reference=1` | да |
| 7 | README | этот файл | да |

## Входы

| файл | размер | sha256 |
|---|---|---|
| `C:/tmp/visual/AN-23/marmoreal-plain/bench-K1-1920x1080.png` | 1920×1080 | e0ca0a2967451d4411e12009af11b9ab7373af0143cbed7f9b7e81506fc33ac2 |
| `C:/tmp/visual/AN-23/marmoreal-facinglegacy/bench-K1-1920x1080.png` | 1920×1080 | eb2e763ed6b67629faba0e398879614037b64468a24f53993e6726b0cf3029f9 |
| `C:/tmp/visual/AN-23/sarpedon-plain/bench-K1-1920x1080.png` | 1920×1080 | 069fe7095030b0c95a85b7f7190f7b9ec1217712d8b78415f366ac36204284b6 |
| `C:/tmp/visual/AN-23/marmoreal-plain/bench-K2x1p6-1920x1080.png` | 1920×1080 | b379ed8f2b616b595a009d6537ae61dda23e273b48d15603fdadc533c5c6b63f |

Живые прогоны: `C:/tmp/visual/AN-24/demo-marmoreal/combat-20261007-020752/`,
`C:/tmp/visual/AN-24/demo-sarpedon/combat-20261007-020923/`.

## Замеры

- Бюджет ≤ 0,01 мс GT: пересчёт только по событиям (spawn/снапшот/конец хода), поворот — тот же BlendYaw,
  что settle F-02; новых объектов на кадр нет. ΔGPU не мерился (правка трансформа актора).
- Контраст / ΔE76: не применяется.

## Что не прошло

- Ничего по критериям. Ограничение: трейса FACING нет у фигур в мёртвой зоне (по конструкции карточки —
  «трасса при смене угла»); их соблюдение |off| ≤ 45 проверено по PNG.

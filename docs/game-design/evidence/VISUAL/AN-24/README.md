# AN-24 — лист приёмки

Лист собран `tools/art/visual/sheet.py` 2026-10-07 по 02-visual-design.md §13.2.

**Решение:** художественно принято, по делегированию (2026-10-06, ВР-06)
**Дата решения:** 2026-10-06
**Ревью:** ZCode (Z-1), один проход, арт и рамки задачи вместе (02 §13.3)
**Флаг отката:** `-S08FacingLegacy` (общий с AN-23; ARTLOOK `facing=`)

## Что проверено (карта AN-24 — живой бой, обе карты)

`tools/s09/run-combat-demo.ps1 -ArtPreview -ArtPreviewBoardId <доска> -JoinerAttack -PlayerView`
(Marmoreal `c121b47f8d6eb28daccb76d05` + `-ClientExtraArgs '-ConceptPaste'`; Sarpedon
`c7fa64a26c29a0835f2383e63`), packaged-клиенты (stamp `f8903fb9`), 30 FPS/клиент, High preset.

### stage=face за 120 мс до lunge

- Marmoreal (host-трейс): `stage=face t=54244 ms=120 lunge=120` → `stage=lunge t=54364` — ровно 120 мс;
  ещё 3 боя с пропущенной паузой: `face t=… ms=120 lunge=0` + `stage=pause ms=0 skipped=1` — поворот идёт
  одновременно с первыми 120 мс клипа (правило карточки «после пропуска паузы»).
- Sarpedon: `face … lunge=120` один, `lunge=0` + `skipped=1` три.
- Атакующие: f-1-sk0 (Мерлин, включая дальние — ranged picks=4/8), f-1-hero (Артур), f-0-hero (Медуза);
  поворот и выпад есть и при уроне 0 (defenses=7/4).

### FACING src=attack

- `FACING fighter=f-0-hero src=attack yaw=118 target=f-1-hero clamped=0` — угол на цель, кламп не нужен;
  4 строки src=attack на каждой карте, `clamped=1` не потребовался (углы в ±90° от оси камеры).
- Длина боя F-01 не выросла: `combat_totals [2592, 3933]` — 120 мс внутри существующей паузы «счёт».

### Глазами (Read PNG, кадр урона)

`s09-damage-combat.png` (обе карты): атакующий (Медуза) в выпаде, корпус направлен на цель, лицо/профиль
виден камере; спиной никто; задник по карте (вклейка / lit3d-остров), шесть фигур v2, маркеров нет (-PlayerView).

### G-CUE и гейты

`cue_contract.py check-trace` — PASS на всех 4 трейсах (host+joiner × 2 карты); `combat_cut=10,
catchup_hurry=8` — контракт допускает; offReference=0 (22-23 и 19-20 снимков), сходимость seq.

## Состав листа

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 2 | Цвет, серый, дейтеранопия | `sheet-01..03` | да |
| 3 | Обе настоящие доски, packaged | листы 1–2 бои Marmoreal/Sarpedon, 3 ход | да |
| 6 | Трассы | `CUE combat stage=face`, `FACING src=attack`, RENDER | да |
| 7 | README | этот файл | да |

## Входы

| файл | размер | sha256 |
|---|---|---|
| `C:/tmp/visual/AN-24/demo-marmoreal/combat-20261007-020752/host/s09-damage-combat.png` | 1280×720 | cda4d28f238be67dee1cf286f7f26c0f581f1a0df1cddb4465d822b601d4899b |
| `C:/tmp/visual/AN-24/demo-sarpedon/combat-20261007-020923/host/s09-damage-combat.png` | 1280×720 | b5edf9ec32cad187a62ee78bd909687a87262f32a8751669ed3c7d0e4670a9fd |
| `C:/tmp/visual/AN-24/demo-marmoreal/combat-20261007-020752/host/s09-opponent-move.png` | 1280×720 | e04f152842e993ece5dd2ae075eb845fca5c2e5c4954f01c0d5675a077a1a729 |

Прогоны: `C:/tmp/visual/AN-24/demo-marmoreal/combat-20261007-020752/`,
`C:/tmp/visual/AN-24/demo-sarpedon/combat-20261007-020923/`.

## Замеры

- Бюджет 120 мс внутри паузы: `combat_totals [2592, 3933]` (F-01 ≈ 3,9 с не выросло); ≤ 0,01 мс GT
  (поворот — трансформ актора по событию).
- Контраст / ΔE76 / ΔGPU: не применяется.

## Что не прошло

- Ничего по критериям. ГМ-оговорка: кадр «контакта» взят из кадра урона демо (t=hit), отдельного
  contact-кадра демо не снимает — поза выпада на нём видна (см. лист 1–2).

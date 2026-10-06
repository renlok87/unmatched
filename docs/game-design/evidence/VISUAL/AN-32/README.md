# AN-32 — лист приёмки

Лист собран `tools/art/visual/sheet.py` 2026-10-07 по 02-visual-design.md §13.2.

**Решение:** художественно принято, по делегированию (2026-10-06, ВР-16)
**Дата решения:** 2026-10-06
**Ревью:** ZCode (Z-1), один проход, арт и рамки задачи вместе (02 §13.3)
**Флаг отката:** `-S08HeroMatFixLegacy` (S08ArtLook.h, трасса ARTLOOK `heroMat=on|legacy`)

## Что сделано (карта AN-32)

Мастер `M_UM_Figure_v2` v2.4: группа Fix (FixClassA/B −1..15, FixGainA/B, FixSpecA/B) в
`um_v2_core.hlsl` (`[unroll] for (int fix...)` — bc *= gain, Spec = saturate(Spec + spec) при совпадении
класса MatID; нейтраль (class −1 / gain 1 / spec 0) ничего не меняет — ветки не срабатывают). Граф пересобран
`ue_v2_master.py` (host) + headless apply `tools/art/hero/figure_master_v24_apply.py` (6 скаляров, OPAQUE,
726 PS instr). Блок `heroMaterials` профиля (FS08HeroMaterialFix, looks P1|P2|*, диапазоны с текстом ошибки),
MID на слот-свапах, тюнер-группа heroMaterials (24 строки, scope HeroMaterials, ApplyTunedArtData без
ребилда), трейсы `ARTPREVIEW heroMat board profile=.. heroes=N mids=N`.

## Что проверено (packaged, stamp `f8903fb9`)

### Нейтральность по умолчанию

Default против `-S08HeroMatFixLegacy`, K1 обеих карт: mean |ΔRGB| = **0.279 (Marmoreal)** и **0.310
(Sarpedon)** — критерий |Δ| ≤ 1 выполнен; изменённых пикселей (|Δ|>24) 5 и 1093 (Sarpedon — анимированный
lit3d-фон), т.е. на фигурах разницы нет. ARTLOOK: `heroMat=on` / `heroMat=legacy(-S08HeroMatFixLegacy)`;
трейс plain: `heroMat board … heroes=0 mids=0` (блока нет — базовые луки).

### Trial-блок heroMaterials (проверка живого пути)

`lightProfiles.marmoreal-night.heroMaterials.Medusa.* = {FixClassA: 13 (skin), FixGainA: 1.3}` (файл-оверрайд
`-ArtBoardProfiles=C:/tmp/visual/AN-32/trial-profiles.json`, profilesSource=override): трейс
`heroMat board profile=marmoreal-night heroes=1 mids=1`; глазами (пара кропов plain/trial, 5×): кожа Медузы
заметно светлее, одежда/подставка/волосы без изменений; Артур (без записи) не изменился. Класс 13 = `skin`
(таблица классов material-library README).

### Live tune ≤ 1 с

`live_tune.py start --packaged --profiles <trial> --extra=-ConceptPaste --extra=-ArtTuner` →
`ARTTUNER ready … groups=9 rows=79` → `tune --set heroMaterials.Medusa.FixGainA=1.15` → **ok, ms=5.7**
(≪ 1 с), shot снят (reference=false by design — тюнер-сессия), stop чисто.

## Состав листа

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 2 | Цвет, серый, дейтеранопия | `sheet-01..04` | да |
| 3 | Обе настоящие доски, packaged | листы 1,4 plain (Marm/Sarp), 2 trial, 3 легаси | да |
| 6 | Трассы | `ARTPREVIEW heroMat board …`, `ARTTUNER ready/tune`, ARTLOOK `heroMat=` | да |
| 7 | README | этот файл | да |

## Входы

| файл | размер | sha256 |
|---|---|---|
| `C:/tmp/visual/AN-23/marmoreal-plain/bench-K1-1920x1080.png` | 1920×1080 | e0ca0a2967451d4411e12009af11b9ab7373af0143cbed7f9b7e81506fc33ac2 |
| `C:/tmp/visual/AN-32/marmoreal-trial/bench-K1-1920x1080.png` | 1920×1080 | dfc6e2f07536bcd97f490b9fc1997f1171a7de4dc3b42d516903cf380325badc |
| `C:/tmp/visual/AN-23/marmoreal-heromatlegacy/bench-K1-1920x1080.png` | 1920×1080 | c0430ea5efc5cc7fc6065cac220037a462d36773114054168340301cf1c8efd1 |
| `C:/tmp/visual/AN-23/sarpedon-plain/bench-K1-1920x1080.png` | 1920×1080 | 069fe7095030b0c95a85b7f7190f7b9ec1217712d8b78415f366ac36204284b6 |

Trial-профиль: `C:/tmp/visual/AN-32/trial-profiles.json` (в репозиторий не входит — проверочный оверрайд,
единственная правка против пакета).

## Замеры

- ΔGPU: нейтральная группа Fix не добавляет веток в шейдер при классе −1; cost-прогон не гонялся
  (правка — параметр существующего материала, не новый pass; +6 Constant2DScalar в MI).
- Контраст / ΔE76: не применяется (тюнинг лука).

## Что не прошло

- Ничего по критериям. Оговорки: (1) ARTLOOK пишется до загрузки профиля — число применённых heroMaterials
  живёт в строке `ARTPREVIEW heroMat board` (ВР-Z1-02); (2) «кадры до изменения» — нейтральная
  эквивалентность через `-S08HeroMatFixLegacy` (ВР-Z1-04).

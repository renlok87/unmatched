# AN-32 — лист приёмки

Лист собран `tools/art/visual/sheet.py` 2026-10-07 по 02-visual-design.md §13.2 (переснят после ревью Z-1).

**Решение:** художественно принято, по делегированию (2026-10-07, ВР-16; ревью Z-1 — доделки M1–M5)
**Дата решения:** 2026-10-07
**Ревью:** визуальный чат, ревью Z-1 + один проход по кадрам (02 §13.3)
**Флаг отката:** `-S08HeroMatFixLegacy` (S08ArtLook.h, трасса ARTLOOK `heroMat=on|legacy`)

## Что сделано (карта AN-32)

Мастер `M_UM_Figure_v2` v2.4: группа Fix (FixClassA/B −1..15, FixGainA/B, FixSpecA/B) в
`um_v2_core.hlsl` (`[unroll] for (int fix...)` — bc *= gain, Spec = saturate(Spec + spec) при совпадении
класса MatID; нейтраль (class −1 / gain 1 / spec 0) ничего не меняет — ветки не срабатывают). Граф пересобран
`ue_v2_master.py` (host) + headless apply `tools/art/hero/figure_master_v24_apply.py` (6 скаляров, OPAQUE,
726 PS instr). Блок `heroMaterials` профиля (FS08HeroMaterialFix, looks P1|P2|*, диапазоны с текстом ошибки),
MID на слот-свапах, тюнер-группа heroMaterials (24 строки, scope HeroMaterials, ApplyTunedArtData без
ребилда), трейсы `ARTPREVIEW heroMat board profile=.. heroes=N mids=N`.

## Доделки ревью 2026-10-07

- M3: неизвестный ключ героя, вид, поле Fix, не-число или значение вне диапазона — ошибка и запись героя целиком не
  применяется (карточка); `Unmatched.S08.HeroMaterials.Validate` покрывает каждый случай.
- M4: `ApplyHeroV2` переставляет MI тела на каждом снапшоте — кэшированный MID с тем же родителем возвращается на
  слот, новые MID не плодятся.
- M5: `S08ArtTunerParams.json` — прежняя компактная раскладка плюс одна группа heroMaterials (+26 строк к базе),
  подписи ВР-16.

## Что проверено — packaged `-Bench`, stamp `45a3c4e9`, обе карты

### Нейтральность по умолчанию (M2)

Default против `-S08HeroMatFixLegacy`, один пакет, K1 / K2×1,6 / K2×2,5:

| карта | K1 | K2×1,6 | K2×2,5 |
|---|---|---|---|
| Marmoreal | 0,246 (5 px > 24) | 0,316 (441) | 0,374 (1998) |
| Sarpedon | 0,313 (1141) | 0,340 (1988) | 0,364 (478) |

mean |ΔRGB| ≤ 1 уровня на всех видах; пиксели > 24 — огонь, вода и водопад (анимированный фон), не фигуры.
Трейс plain: `ARTPREVIEW heroMat board profile=marmoreal-night heroes=0 mids=0` (в профилях блока нет).

### Пробный блок, дифф по маске (M2)

`heroMaterials.Medusa.* = {FixClassA: 13 (skin), FixGainA: 1.3}` в `marmoreal-night` и `sarpedon-night`
(оверрайд `-ArtBoardProfiles=C:/tmp/visual/Z-1/trial-profiles.json`, profilesSource=override → `reference=0`
по замыслу). Трейсы `heroMat board … heroes=1 mids=1`, `heroMat fighter=f-0-hero hero=Medusa look=P1
A=13/1.30/0.00 B=-1/1.00/0.00`. Маска — пиксели, где trial отличается от plain больше чем на 8 уровней, а
нейтральная пара (plain против отката) — нет:

| вид | в прямоугольнике Медузы | вне его | mean |Δ| вне (trial / нейтраль) |
|---|---|---|---|
| Marmoreal K1 | 192 px, mean 1,06 | 159 px | 0,196 / 0,245 |
| Marmoreal K2×1,6 | 395 px, mean 0,69 | 200 px | 0,280 / 0,308 |
| Sarpedon K1 | 192 px, mean 1,11 | 1492 px | 0,274 / 0,312 |

Вне Медузы разница на уровне шума (меньше, чем у нейтральной пары); внутри маска ложится на кожу (торс, руки,
ноги), одежда, волосы, лук и подставка не меняются (листы 1–3, третья плитка — маска пурпуром).
Live tune ≤ 1 с — замер ZCode (`tune --set heroMaterials.Medusa.FixGainA=1.15` → ok, 5,7 мс).

### G-COST (M1; render_bench K1, без капа, 3 повторности, `C:/tmp/visual/Z-1/cost-summary.json`)

| карта | ветка v2.4 | fix/admin-panel `230b2b0d` v2.3 | ветка + пробный блок |
|---|---|---|---|
| Marmoreal | 2,500 мс | 2,510 мс (Δ −0,010) | 2,493 мс (Δ −0,007) |
| Sarpedon | 2,620 мс | 2,637 мс (Δ −0,017) | 2,623 мс (Δ +0,003) |

Все Δ в шуме и ≤ 0,05 мс. Сборка v2.3 — копия staged-сборки основного чекаута (stamp `230b2b0d`) в
`C:/tmp/visual/Z-1/staged-main`.

### Тесты

`Unmatched.S08.HeroMaterials.Parse / .Validate / .Apply`, `Unmatched.S08.ArtTuner.HeroMaterials`,
`Unmatched.S08.ArtLook.Default` (`heroMat=on`, `heroMat=legacy(-S08HeroMatFixLegacy)`) — PASS.

## Состав листа

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 2 | Цвет, серый, дейтеранопия | `sheet-01..03` | да |
| 3 | Обе настоящие доски, packaged | 1 Marmoreal K1, 2 Marmoreal K2×1,6, 3 Sarpedon K1 (plain / trial / маска) | да |
| 6 | Трассы | `ARTPREVIEW heroMat board/fighter`, ARTLOOK `heroMat=` | да |
| 7 | README | этот файл | да |

## Входы

Прогоны: `C:/tmp/visual/Z-1/shots/{marmoreal,sarpedon}-{plain,heromatlegacy,trial}/`, cost —
`C:/tmp/visual/Z-1/cost/`. Кропы — `C:/tmp/visual/Z-1/sheets-in/AN-32/`.

## Что не прошло

- Ничего по критериям. Оговорки: ARTLOOK пишется до загрузки профиля — число применённых heroMaterials живёт в
  строке `ARTPREVIEW heroMat board` (ВР-Z1-02); «кадры до изменения» — эквивалентность через откат (ВР-Z1-04).

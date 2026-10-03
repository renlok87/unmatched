# Art Tuner — проверка 2026-10-03

Статус: **технически импортировано / измерено**. «Художественно принято» — только решение пользователя.
План: [ART-TUNER-PLAN.md](../../../../art-pipeline/ART-TUNER-PLAN.md), инструкция: [tools/art/ART-TUNER.md](../../../../../tools/art/ART-TUNER.md).

Собранный клиент (Development, DX12 SM6 Lumen, High), упаковка на коммите `22694a8d`, Sarpedon. Запуски вне экрана через
live tune (`tools/art/render/live_tune.py start --packaged --art-view --tuner-file …`) — те же действия, что у ползунков.

## Что проверено

| Проверка | Результат |
|---|---|
| Окно без сервера `-ArtView=sarpedon` | доска 9×6, 6 фигур, арт-профиль `sarpedon-original`, эффекты живые (`fx=live`), готово за 23–24 с |
| Реестр строк в pak | `ARTTUNER ready … groups=10 rows=94` (собранный клиент читает `Config/ArtTuner/S08ArtTunerParams.json` из pak) |
| Три изменения через `tune` | ключ подсветки героев 7 → 10 лк, огонь форта 40 → 90 кд, яркость острова ×1,3 (новый блок `materialOverrides`): команда 13,7 мс, применение **1,5 мс**, пересборок 0 (цель ≤ 200 мс) |
| Кадры до / после | `03-before-after-packaged-K2x1p6.jpg`: ярче огонь слева и подсветка героев; доска не тронута |
| Панель на экране | `01-panel-packaged-K1.jpg`: «изменено: 3», отметка ● у изменённой строки, кнопка × |
| Справка F1 | `02-help-packaged-K1.jpg` |
| Свободная камера | `04-orbit-packaged-yaw-40-pitch-30.jpg` (поворот −40°, наклон 30°) |
| Сохранение | `S08ArtTuner.overrides.sample.json`: только 3 изменённых значения, у каждого `was` |
| Перезапуск с файлом | `ARTTUNER ready … loaded=3 skipped=0 warnings=0`, `tunerState`: те же 3 значения, `source=tuner` |
| Внесение в профиль | `fold-dry-run.txt` на копии профиля: меняются 3 строки (ревизия 20 → 21, `lux`, `intensityCd` + вставка `"materialOverrides": {"Island": {"tintGain": 1.3}}` в стиле объекта) |
| Материалы (editor `-game`) | `05-materials-diff-editor-K1.jpg` — карта разницы: меняются только остров, корабль и листва; `ARTPREVIEW concept-scene materials looks=3 mids=39 … Island:1 Ship:1 Foliage:37`, применение 1,1 мс |

## Без флагов игра прежняя

Свежий упакованный `-Bench` (аргументы эталонного прогона) против `C:/tmp/envmaps-research/lightcheck/sarpedon/bench-*.png`
(P9b, 2026-10-02 22:48 UTC) и A/B со старой сборкой `09c7d2f9`, снятой в тех же условиях:

| Средняя абсолютная разница | K1 | K2x1.6 | K2x2.5 |
|---|---|---|---|
| новая сборка (прогон 1) ↔ эталон | 0,623 | 0,730 | 0,822 |
| новая сборка (прогон 2) ↔ эталон | 0,586 | 0,749 | 0,825 |
| **старая сборка `09c7d2f9` сейчас ↔ эталон** | 0,590 | 0,741 | 0,814 |
| новая (1) ↔ старая сейчас | 0,468 | 0,407 | 0,456 |
| новая (2) ↔ старая сейчас | **0,411** | 0,556 | 0,494 |
| новая (1) ↔ новая (2) — шум запуск-к-запуску | 0,417 | 0,530 | 0,523 |

- Порог задания (≤ 0,5 к эталону) на K1 не выполнен: 0,59–0,62. Но **старая сборка без моих изменений** сейчас даёт ту же
  разницу с эталоном (0,59), а моя сборка от старой отличается на уровне шума запуск-к-запуску (0,41–0,47 при шуме 0,42).
  Расхождение с эталоном — состояние машины и времени кадра (вода, огонь, анимация), а не код тюнера.
- Отпечаток рендера: `render_fingerprint.py check … --shot bench-K1-1920x1080.png` → `reference=true`, `profilesSource=pak`,
  `profilesSha256=23e4ebed…` (профиль не менялся).
- Весь новый код за флагами `-ArtView` / `-ArtTuner`; без них — тест `Unmatched.S08.ArtView.OffByDefault`,
  `Unmatched.S08.ArtTuner.OffByDefault`.

## Тесты

- UE: `Unmatched.S08+Unmatched.S09+Unmatched.S10` — 272 теста, все зелёные (новые: `Unmatched.S08.ArtView.*` ×5,
  `Unmatched.S08.ArtTuner.*` ×9, в том числе `Ranges` — границы реестра совпадают с C++-парсером на всех досках профиля).
- pytest `tools/art/tests` — 544 passed, 3 skipped (новые: `test_art_tuner_fold.py` ×9, `test_live_tune.py` дополнен).

## Замеры времени (для оценок)

Сборка редактора 10–30 с, цели игры 22–103 с (после `touch Unmatched.Build.cs`), упаковка 1 мин 40 с, UE-тесты 25 с,
pytest `tools/art/tests` 7 мин 24 с, запуск клиента до готовности 23–40 с.

## Где лежат сырые кадры

PNG и трассы прогонов — вне git: `C:/tmp/arttuner/m6/` (before, after, panel, bench-noflags, bench-noflags2,
bench-old09c7, final-*), `C:/tmp/arttuner/m4/` (материалы, editor).

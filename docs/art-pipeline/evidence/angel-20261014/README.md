# ASSET-ANGEL-001 — этап 7 (UE и игра), 2026-10-14

Статус: технически импортировано (`asset-registry.json`, stage `live-packaged-probe`); в `03-asset-registry.csv` —
«художественно принято, по делегированию» (ВР-17, отступление от HANDBOOK §0 п.3 — таблица решений скилла)
Исполнитель: Claude Opus 5.5 (исполнитель этапа 7b пилота); UE 5.8.2, Blender 5.2.2 LTS (base_seethrough)
Делегирование: «Не знаю. Делай сам, меня это не касается. Все решения принимай» (2026-10-06); пилот 2026-10-13.

Run импорта: `art/pipeline-candidates/ASSET-ANGEL-001/20261014-h2ld-ue-import-r3/` (этап 7a)
Профили: `build-profiles/angel-h2ld-lookdev-ue-import-r3.json`, `20261014-h2ld-ldc-ue/review-config.json`
Клипы в UE: `20261014-h2anim-r2` (спека `build-profiles/angel-h2anim-r2.json`)
Карточки pass: модель `evidence/acceptance/20261013-r1/card.json` (8.8); клипы `evidence/acceptance-anim/20261014-r1/{Idle,HitReact}/card.json`
(8.8, 9.4), `20261014-r2/{LungeAttack,DeathSettle}/card.json` (8.8, 8.8)

## Входы
- source-spec и вход §2 — этап 7a (`asset-card.yaml`, блок `STAGE7A`; sha256 исходников сверены там).
- Профили этапа 7b новых файлов не добавляют.

## Результаты (числа из отчётов)
| Проверка | Значение | Порог | Итог |
|---|---|---|---|
| треугольники фигура (тело + меч) / подставка | 38 588 / 1 524 | 30–45k (практика H2) | ок |
| верх фигуры / верх bounds, uu | 55,000 (голова) / 55,909 (остриё меча) | бюджет 55 ± 1 % | ок, scale 1,0000 |
| ue-import checks | 26/26 | все | PASS |
| сокеты Weapon/Head | Δ 0,000 uu (как прогноз сборки) | ± 0,05 | PASS |
| base_seethrough with_figure (schema /2, aim surface) | 0,00 uu² во всех 5 направлениях (base_only ≤ 0,02) | ≤ 0,1 | PASS (`base-seethrough-v2.json`) |
| notify Contact (de010) | один, 0,29167 с = к.7; длина 0,58333 с, 14 к. до/после | один, к.7 ± ½ к. | PASS (`de010-apply.json`) |
| MIC растворения (de011) | `MI_Angel_H2LD_P{1,2}_Dissolve`, Masked, родитель MI тела | есть | PASS (`de011-apply.json`) |
| сборка UnmatchedEditor | `Result: Succeeded` (4 файла) | Succeeded | PASS |
| Unmatched.S08 | 393/393 Success, `EXIT CODE: 0`, Fail 0 (`ue-tests-s08.txt`) | 0 Fail | PASS |
| упаковка | одна, `-SkipBuild` после сборки игрового target; `.utoc`: 29 ассетов Angel + 2 MIC | ассеты в паке | PASS |
| RENDER-отпечаток кадров | код 0 × 6 | 0 | PASS |
| замер стоимости | один прогон на Achilles (самый тяжёлый из трёх) — `../achilles-20261014/README.md` | ACC-022 | см. там |

## Шаги 7b
1. Предусловие: ни одного `UnrealEditor.exe`, порт 8123 свободен (проверено перед de010 и перед упаковкой).
2. Регистрация Р7-1/Р7-2 (`de010.py` `HEROES`, `de011.py` `CAPTURE_LOOKS`), один `apply` каждого для трёх героев под
   `ue_lock.py` (`--frames C:/tmp/ASSET-ANGEL-001-stage7/de010|de011`).
3. Р7-3…Р7-5: строка `Specs()` `{"Angel","Angel","H2LD",true,55,52,56,55.0,55.909,2.5,7}`, тесты (семь героев,
   имена, `WantMs` 291.667, `WantSeconds` 0.5), `S08AudioBank` `ANGEL`/`BLADE` + тесты.
4. Одна упаковка; кадры `-Bench` обеих досок с `S08Bench{Marmoreal,Sarpedon}-Angel.json` и
   `-BenchFocusFighter=Angel` (cap 60 FPS); JPEG 1200 q92 + `*.evidence.json` в `bench-*/`, трассы `bench.trace.txt`.
5. Лист K1/K2 цвет / серый / дейтеранопия — `game-sheet/`; лист клипов AN-18 — `docs/game-design/evidence/VISUAL/AN-133…AN-136/`.

## Кадры: что видно глазами
- Marmoreal original: нарисованный задник (дворец, сакура, фонари), `ARTLOOK board=marmoreal-original backdrop=paste(default)`.
- Sarpedon original: lit3d путь 1 (остров, корабль, водопад), `backdrop=lit3d(default)`.
- Все 6 фигур — v2 (`heroesV2 summary fighters=6 mapped=6 v2=6`): Medusa, три гарпии, Merlin, Angel.
- Angel на K2×1,6 и K2×2,5 в центре кадра (`BENCH focus fighter=f-1-hero (Angel)`): тёмный длинный плащ, меч поднят,
  цвета концепта (почти чёрная кожаная одежда), подставка стоит на клетке, кольцо команды P2 читается и в сером.
- Трассы: `clips=4/4`, нет `fallback=legacy`, `mi=missing`, `dissolve=missing`, `anim … missing=1`, нет `BENCH FAILED`.

## Отступления от хендбука
- Статус 03 CSV «художественно принято, по делегированию» (ВР-17) — решение скилла (`references/ue-import-package.md`, вступление).
- Notify `Contact` ставит `de010.py apply` (решение скилла); прогон один на трёх героев пилота, его отчёт скопирован в каждый evidence.
- `base_seethrough` впервые снят на этапе 7b (у 7a Angel замера не было).

## Что не проверялось
- Растворение отдельным запуском `-BenchDissolve` (тест `HeroesV2.Dissolve` PASS, MIC в паке).
- Табличка имени при наведении (Р7-8) — кадры без наведения.
- Звук на кадрах (`-NoSound` в bench); `CMB-HIT/LUNGE-BLADE` проверены тестом `Unmatched.S08.Audio`.

## Открытые вопросы к владельцу
- Нет (боец Angel в эталонной БД сервера и FX/звук способности — вне скилла).

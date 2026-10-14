# ASSET-ACHILLES-001 — этап 7 (UE и игра), 2026-10-14

Статус: технически импортировано (`asset-registry.json`, stage `live-packaged-probe`); в `03-asset-registry.csv` —
«художественно принято, по делегированию» (ВР-17, отступление от HANDBOOK §0 п.3 — таблица решений скилла)
Исполнитель: Claude Opus 5.5 (исполнитель этапа 7b пилота); UE 5.8.2
Делегирование: «Не знаю. Делай сам, меня это не касается. Все решения принимай» (2026-10-06); пилот 2026-10-13.

Run импорта: `art/pipeline-candidates/ASSET-ACHILLES-001/20261014-h2ld-ue-import-r4/` (этап 7a, модель r3)
Профили: `build-profiles/achilles-h2ld-lookdev-ue-import-r4.json`, `20261014-h2ld-ldc-ue/review-config-r4.json`
Клипы в UE: `20261014-h2anim-r3` (спека `build-profiles/achilles-h2anim-r3.json`)
Карточки pass: модель `evidence/acceptance/20261014-r3/final.json` (пара 8.1); клипы
`evidence/acceptance-anim/20261014-r2/{Idle,LungeAttack,HitReact,DeathSettle}/card.json` (8.8, 9.4, 10.0, 9.4)

## Входы
- source-spec и вход §2 — этап 7a (`asset-card.yaml`, блок `STAGE7A`).
- Профили этапа 7b новых файлов не добавляют.

## Результаты (числа из отчётов)
| Проверка | Значение | Порог | Итог |
|---|---|---|---|
| треугольники фигура (тело + копьё) / подставка | 44 804 / 1 348 | 30–45k (практика H2) | ок |
| верх фигуры / верх bounds, uu | 55,000 (гребень шлема) / 54,9931 (bounds меша) | бюджет 55 ± 1 % | ок, scale 1,0000 |
| ue-import checks | 26/26 | все | PASS |
| сокеты Weapon/Head | Δ 0,000 uu | ± 0,05 | PASS |
| base_seethrough with_figure (schema /2) | 0,00 uu² (этап 7a, `evidence/stage7a-20261014/base-seethrough-v2-r4.json`) | ≤ 0,1 | PASS |
| notify Contact (de010) | один, 0,29167 с = к.7; длина 0,58333 с, 14 к. до/после | один, к.7 ± ½ к. | PASS (`de010-apply.json`) |
| MIC растворения (de011) | `MI_Achilles_H2LD_P{1,2}_Dissolve`, Masked, родитель MI тела | есть | PASS (`de011-apply.json`) |
| сборка UnmatchedEditor | `Result: Succeeded` | Succeeded | PASS |
| Unmatched.S08 | 393/393 Success, `EXIT CODE: 0`, Fail 0 (`ue-tests-s08.txt`) | 0 Fail | PASS |
| упаковка | одна (общая для трёх героев); `.utoc`: 29 ассетов Achilles + 2 MIC | ассеты в паке | PASS |
| RENDER-отпечаток кадров | код 0 × 6 | 0 | PASS |
| замер стоимости `render_bench.py` (один прогон, `dx12-lumen-high-v2 --repeats 1`, вариант Marmoreal, `-BenchFocusFighter=Achilles`, без кэпа FPS, RTX 4090) | K1 247,2 FPS, GPU 2,10 мс (p95 2,26); K2×5 на Ахиллесе 227,2 FPS, GPU 2,18 мс (p95 2,36); кадр p99 5,7 / 6,2 мс; RENDER reference true × 2 (`bench/achilles-stage7/r1/`) | ACC-022 (60 FPS) | в пороге — записано, оптимизаций нет |

## Шаги 7b
1. Предусловие: ни одного `UnrealEditor.exe`, порт 8123 свободен.
2. Р7-1/Р7-2: `("Achilles","H2LD",…/achilles-h2anim-r3.json, 7)` в `de010.py` `HEROES`, `"Achilles": "P1"` в
   `de011.py` `CAPTURE_LOOKS`; общий `apply` трёх героев под `ue_lock.py`.
3. Р7-3…Р7-5: `Specs()` `{"Achilles","Achilles","H2LD",true,55,52,56,55.0,54.9931,2.5,7}`, тесты (`WantMs` 291.667,
   `WantSeconds` 0.5), `S08AudioBank` `ACHILLES` / `BLADE` + тесты.
4. Кадры `-Bench` обеих досок с `S08Bench{Marmoreal,Sarpedon}-Achilles.json`, `-BenchFocusFighter=Achilles`;
   единственный замер стоимости пилота — на варианте Marmoreal Achilles (самая тяжёлая фигура из трёх, 44 804 tris).
5. Лист K1/K2 — `game-sheet/`; лист клипов AN-18 — `docs/game-design/evidence/VISUAL/AN-141…AN-144/`.

## Кадры: что видно глазами
- Marmoreal original — нарисованный задник (`backdrop=paste(default)`); Sarpedon original — lit3d путь 1 (`backdrop=lit3d(default)`).
- Все 6 фигур v2 (`fighters=6 mapped=6 v2=6`); на месте помощника f-1-sk0 — Merlin v2 (у Патрокла нет фигуры, F135).
- Ахиллес на K2 в центре (`BENCH focus fighter=f-1-hero (Achilles)`): красный гребень и плащ, тёплая бронза щита и
  доспеха, копьё в правой руке — цвета концепта. Двухъярусная подставка: полоса команды P2 идёт по кромке каждого
  яруса (две полосы, F143/F150), рваных пятен на K2×2,5 не видно; на клетке стоит, в сером кольцо читается.
- Трассы: `clips=4/4`, без `fallback=legacy` / `mi=missing` / `dissolve=missing` / `anim … missing=1` / `BENCH FAILED`.

## Отступления от хендбука
- `render_bench.py --out` — `C:/tmp/ASSET-ACHILLES-001-stage7/render-bench`, а не `$E/bench` (`references/ue-import-package.md` §6.5): в git идут только `bench-run.json`, `nvidia-smi.csv`, трасса `.txt` и JPEG 1200 q92 кадров (HANDBOOK §8 — PNG кадров не коммитятся; при расхождении выигрывает HANDBOOK). `--repeats 1` — «ровно один прогон» (по умолчанию инструмент делает 3); `--client-args=-BenchFocusFighter=Achilles`, чтобы K2×5 мерил нового героя, а не Medusa.
- Статус 03 CSV «художественно принято, по делегированию» (ВР-17) — решение скилла.
- Notify `Contact` ставит `de010.py apply` (решение скилла); прогон один на трёх героев, отчёт скопирован.

## Что не проверялось
- `-BenchDissolve` отдельным запуском (тест `HeroesV2.Dissolve` PASS, MIC в паке); табличка имени; звук (`-NoSound`).

## Открытые вопросы к владельцу
- Нет (боец в эталонной БД сервера, фигура Патрокла, FX/звук способности — вне скилла).

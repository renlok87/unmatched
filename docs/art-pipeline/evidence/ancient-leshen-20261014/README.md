# ASSET-ANCIENT-LESHEN-001 — этап 7 (UE и игра), 2026-10-14

Статус: технически импортировано (`asset-registry.json`, stage `live-packaged-probe`); в `03-asset-registry.csv` —
«художественно принято, по делегированию» (ВР-17, отступление от HANDBOOK §0 п.3 — таблица решений скилла)
Исполнитель: Claude Opus 5.5 (исполнитель этапа 7b пилота); UE 5.8.2
Делегирование: «Не знаю. Делай сам, меня это не касается. Все решения принимай» (2026-10-06); пилот 2026-10-13.

Run импорта: `art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/20261014-h2ld-ue-import-r5/` (этап 7a, модель r3)
Профили: `build-profiles/ancient-leshen-h2ld-lookdev-ue-import-r5.json`, `20261014-h2ld-ldc-ue/review-config-r5.json`
Клипы в UE: `20261014-h2anim-r3` (спека `build-profiles/ancient-leshen-h2anim-r3.json`)
Карточки pass: модель `evidence/acceptance/20261014-r3/final.json` (пара 8.1); клипы
`evidence/acceptance-anim/20261014-r2/{Idle,LungeAttack,HitReact,DeathSettle}/card.json` (9.4, 9.4, 10.0, 9.4)

## Входы
- source-spec и вход §2 — этап 7a (`asset-card.yaml`, блок `STAGE7A`).
- Профили этапа 7b новых файлов не добавляют.

## Результаты (числа из отчётов)
| Проверка | Значение | Порог | Итог |
|---|---|---|---|
| треугольники фигура / подставка | 44 438 / 2 268 | 30–45k (практика H2) | ок |
| верх фигуры / верх bounds, uu | 55,003 (череп) / 73,56 (рога) | бюджет 55 ± 1 % | ок, scale 0,9999 |
| ue-import checks | 26/26 | все | PASS |
| сокеты Weapon/Head | Δ 0,000 uu (Weapon на `hand_R`, оружия нет) | ± 0,05 | PASS |
| base_seethrough with_figure (schema /2) | ≤ 0,01 uu² (этап 7a, `evidence/stage7a-20261014/base-seethrough-v2-r3.json`) | ≤ 0,1 | PASS |
| notify Contact (de010) | один, 0,33333 с = к.8; длина 0,58333 с, 14 к. до/после | один, к.8 ± ½ к. | PASS (`de010-apply.json`) |
| MIC растворения (de011) | `MI_AncientLeshen_H2LD_P{1,2}_Dissolve`, Masked, родитель MI тела | есть | PASS (`de011-apply.json`) |
| сборка UnmatchedEditor | `Result: Succeeded` | Succeeded | PASS |
| Unmatched.S08 | 393/393 Success, `EXIT CODE: 0`, Fail 0 (`ue-tests-s08.txt`) | 0 Fail | PASS |
| упаковка | одна (общая для трёх героев); `.utoc`: 29 ассетов AncientLeshen + 2 MIC | ассеты в паке | PASS |
| RENDER-отпечаток кадров | код 0 × 6 | 0 | PASS |
| замер стоимости | один прогон на Achilles — `../achilles-20261014/README.md` | ACC-022 | см. там |

## Шаги 7b
1. Предусловие: ни одного `UnrealEditor.exe`, порт 8123 свободен.
2. Р7-1/Р7-2: строка `("AncientLeshen","H2LD",…/ancient-leshen-h2anim-r3.json, 8)` в `de010.py` `HEROES`,
   `"AncientLeshen": "P2"` в `de011.py` `CAPTURE_LOOKS`; общий `apply` трёх героев под `ue_lock.py`.
3. Р7-3…Р7-5: `Specs()` `{"Ancient Leshen","AncientLeshen","H2LD",true,55,50,55,55.003,73.56,56/24,8}`, тесты
   (`WantMs` 333.333, `WantSeconds` 0.5), `S08AudioBank` `ANCIENTLESHEN` (подстрока «leshen») / `MAGIC` + тесты.
4. Кадры `-Bench` обеих досок с `S08Bench{Marmoreal,Sarpedon}-AncientLeshen.json`, `-BenchFocusFighter=AncientLeshen`.
5. Лист K1/K2 — `game-sheet/`; лист клипов AN-18 — `docs/game-design/evidence/VISUAL/AN-137…AN-140/`.

## Кадры: что видно глазами
- Marmoreal original — нарисованный задник (`backdrop=paste(default)`); Sarpedon original — lit3d путь 1 (`backdrop=lit3d(default)`).
- Все 6 фигур v2 (`fighters=6 mapped=6 v2=6`); на месте помощника f-1-sk0 — Merlin v2 (у волка нет фигуры, F135).
- Леший на K2 в центре (`BENCH focus fighter=f-1-hero (AncientLeshen)`): светлые череп и рога, тёмно-коричневый ствол
  с вороньими перьями — цвета концепта; рога поднимаются выше соседних фигур, подставка на клетке, кольцо P2 читается и в сером.
- Трассы: `clips=4/4`, без `fallback=legacy` / `mi=missing` / `dissolve=missing` / `anim … missing=1` / `BENCH FAILED`.

## Отступления от хендбука
- Статус 03 CSV «художественно принято, по делегированию» (ВР-17) — решение скилла.
- Notify `Contact` ставит `de010.py apply` (решение скилла); прогон один на трёх героев, отчёт скопирован.

## Что не проверялось
- `-BenchDissolve` отдельным запуском (тест `HeroesV2.Dissolve` PASS, MIC в паке); табличка имени при наведении; звук (`-NoSound`).
- Насыщенность дерева на осевших кадрах UE выше концепта (F153) — открыто с 7a, на кадрах доски не бросается в глаза.

## Открытые вопросы к владельцу
- Нет (боец в эталонной БД сервера, фигура волка-помощника, FX/звук способности — вне скилла).

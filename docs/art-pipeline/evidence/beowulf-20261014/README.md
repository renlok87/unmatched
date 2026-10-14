# ASSET-BEOWULF-001 — этап 7 (UE и игра), 2026-10-14

Статус: технически импортировано (`asset-registry.json`, stage `live-packaged-probe`); в `03-asset-registry.csv` —
«художественно принято, по делегированию» (ВР-17, отступление от HANDBOOK §0 п.3 — таблица решений скилла)
Исполнитель: Claude Opus 5.5 (исполнитель этапа 7b фигуры-проверки доработанного скилла); UE 5.8.2
Делегирование: «Не знаю. Делай сам, меня это не касается. Все решения принимай» (2026-10-06); «Одна фигура-проверка»
(2026-10-14).

Run импорта: `art/pipeline-candidates/ASSET-BEOWULF-001/20261014-h2ld-ue-import/` (этап 7a, коммит 69fd9bf8)
Профили: `build-profiles/beowulf-h2ld-lookdev-ue-import.json` (+ `-r2`, `-r3` — apply-mi look-dev), `20261014-h2ld-ldc-ue/review-config.json`
Клипы в UE: `20261014-h2anim` (спека `build-profiles/beowulf-h2anim.json`)
Карточки pass: модель `evidence/acceptance/20261014-r1/final.json` (пара Sol 8.1 + Opus 8.1); клипы
`evidence/acceptance-anim/20261014-r1/{Idle,LungeAttack,HitReact,DeathSettle}/card.json` (8.8, 8.8, 9.4, 8.8)

## Входы
- source-spec и вход §2 — этапы 3 и 7a (`asset-card.yaml`, блоки `STAGE3`, `STAGE6`; evidence 7a — `evidence/stage7a-20261014/`).
- Профили этапа 7b новых файлов не добавляют.

## Результаты (числа из отчётов)
| Проверка | Значение | Порог | Итог |
|---|---|---|---|
| треугольники фигура (тело + меч) / подставка | 43 861 (42 462 + 1 399) / 1 430 | 30–45k (практика H2) | ок |
| верх фигуры / верх bounds, uu | 55,000 (купол шлема) / 55,0149 (bounds меша) | бюджет 55 ± 1 % | ок, scale 1,0000 |
| ue-import checks | 27/27 | все | PASS |
| базовая линия `validate_registry` до de010 → после 7b | 1 ERROR (UM-MASTERS sha256, F91) → тот же 1 ERROR | новых нет | PASS |
| notify Contact (de010 `--only Beowulf`) | один, 0,29167 с = к.7; длина 0,58333 с, 14 к. до/после | один, к.7 ± ½ к. | PASS (`de010-apply.json`) |
| MIC растворения (de011 `--only Beowulf`) | `MI_Beowulf_H2LD_P{1,2}_Dissolve`, Masked, родитель MI тела | есть | PASS (`de011-apply.json`) |
| пересохранённые чужие `.uasset` (MVP, пилот) | 0 (изменён только свой `AM_Beowulf_LungeAttack`, новые — 2 MIC) | 0 | PASS |
| сборка UnmatchedEditor | `Result: Succeeded` (7 действий, 16 с) | Succeeded | PASS |
| Unmatched.S08 | 393/393 Success, `EXIT CODE: 0`, Fail 0 (`ue-tests-s08.txt`) | 0 Fail | PASS |
| `registration_check.py --heroes Beowulf` | PASS 12, FAIL 0 | код 0 | PASS |
| упаковка | одна; BuildStamp commit 69fd9bf8 + правки 7b, sourceHash `3cf688db…`, 480 файлов; `.utoc`: 23 `.uasset` Beowulf + 2 MIC (31 запись с `.ubulk`) | ассеты в паке | PASS |
| варианты фикстуры в packaged-клиенте | `source: loose` (без touch `Build.cs`, F162), трасса `BENCH scene fixture=S08Bench<Map>-Beowulf.json` | без `BENCH FAILED` | PASS |
| RENDER-отпечаток кадров | код 0 × 6 | 0 | PASS |
| замер стоимости `render_bench.py` (один прогон, `dx12-lumen-high-v2 --repeats 1`, вариант Marmoreal, `-BenchFocusFighter=Beowulf`, без кэпа FPS, RTX 4090) | K1 223,8 FPS, GPU 2,16 мс (p95 2,3); K2×5 на Беовульфе 213,6 FPS, GPU 2,23 мс (p95 2,4); кадр p99 5,84 / 6,0 мс; RENDER reference true × 2 (`bench/beowulf-stage7/r1/`) | ACC-022 (60 FPS) | в пороге — записано, оптимизаций нет |

## Шаги 7b (время)
1. Предусловие: ни одного `UnrealEditor.exe`, порт 8123 свободен, блокировок `ue-editor.lock` / `unmatched-gpu.lock` нет.
   Базовая линия `validate_registry` — 1 ERROR (UM-MASTERS).
2. Р7-1/Р7-2: `("Beowulf","H2LD",…/beowulf-h2anim.json, 7)` в `de010.py` `HEROES`, `"Beowulf": "P2"` в
   `de011.py` `CAPTURE_LOOKS`; `--dry-run`, затем `apply --only Beowulf` под `ue_lock.py` (18 с и 16 с).
3. Р7-3…Р7-5: `Specs()` `{"Beowulf","Beowulf","H2LD",true,55,52,56,55.0,55.0149,2.5,7}`, тесты (`eight heroes`, имя в
   Mapping, `WantMs` 291.667, `WantSeconds` 0.5), `S08AudioBank` `BEOWULF` / `BLADE` + тесты. Сборка 16 с, тесты 93 с.
4. `asset-registry.json` → «технически импортировано» / `ue-editor-frames`; `registration_check` PASS; одна упаковка
   (1 мин 33 с).
5. Кадры `-Bench` обеих досок с `S08Bench{Marmoreal,Sarpedon}-Beowulf.json`, `-BenchFocusFighter=Beowulf` (104 с и 100 с,
   `-BenchFps=60`, клиенты строго по одному); лист K1/K2 — `game-sheet/` (JPEG, PNG — в `C:/tmp/ASSET-BEOWULF-001-stage7/game-sheet`).
6. Лист клипов AN-18: `clip_review_sheet.py run --packaged --heroes Beowulf --fixture marmoreal=…,sarpedon=…` (563 с на
   доску), `sheet --heroes Beowulf` → `docs/game-design/evidence/VISUAL/AN-145…AN-148/`, problems 0.
7. Единственный замер стоимости `render_bench.py` (97 с, GPU-токен свой, снят).

## Кадры: что видно глазами
- Marmoreal original — нарисованный задник (`backdrop=paste(default)`: дворец, сакуры, фонари); Sarpedon original —
  lit3d путь 1 (`backdrop=lit3d(default)`: 3D-остров, корабль, водопад).
- Все 6 фигур v2 (`fighters=6 mapped=6 v2=6`): Medusa и три Harpy с цифрами 1–3 (P1), Merlin v2 на месте помощника
  f-1-sk0 (у Wiglaf нет фигуры, F135) и Беовульф (P2).
- Беовульф на K2 в центре (`BENCH focus fighter=f-1-hero (Beowulf)`): бурая меховая мантия, железный шлем, круглый
  деревянный щит с железным умбоном на левой руке, меч в правой, кожаные сапоги, синий акцент команды на поясе —
  цвета концепта. Двухъярусная подставка стоит на клетке; кольцо команды P2 — тёмно-синяя полоса по боковине нижнего
  яруса, в сером читается как тёмная кромка.
- Трассы: `clips=4/4`, без `fallback=legacy` / `mi=missing` / `dissolve=missing` / `anim … missing=1` / `BENCH FAILED` /
  `focus error`.
- **Замечание 7a (DeathSettle f21-q34, чёрный провал между воротом мантии и затылком шлема) — в игре виден.** На листе
  AN-148 и в сырых кадрах K2×1,6 (`C:/tmp/visual/AN-18/{marmoreal,sarpedon}/Beowulf/bench-K2x1.6-DeathSettle-f16/f21-…`)
  на к.16–21, когда голова уходит в поклон, в вороте мантии за шлемом открывается чёрное овальное пятно ≈ 5×10 px
  (K2×1,6, 1920×1080), на обеих досках, в цвете и в сером; на K1 — 2–3 px, читается как тень. В Idle / LungeAttack /
  HitReact его нет. Вероятная причина — снятая на этапе 3 (t2) крышка `neck_top` под бородой: изнанка ворота не
  закрыта. Это дефект модели, вскрытый клипом (маршрут позднего фикса — решение оркестратора); 7b его не правит.

## Отступления от хендбука
- `render_bench.py --out` — `C:/tmp/ASSET-BEOWULF-001-stage7/render-bench`, в git только `bench-run.json`, `nvidia-smi.csv`,
  трасса `.txt` и JPEG 1200 q92 (HANDBOOK §8, ДС-8); `--repeats 1`; `--client-args=-BenchFocusFighter=Beowulf` (F160).
- Лист K1/K2 `game-sheet/` — JPEG-копии и `sheet-manifest.json` (ДС-8), PNG вне git.
- Статус 03 CSV «художественно принято, по делегированию» (ВР-17) — решение скилла.
- Notify `Contact` ставит `de010.py apply` (решение скилла).

## Что не проверялось
- `-BenchDissolve` отдельным запуском (тест `HeroesV2.Dissolve` PASS, MIC в паке); табличка имени (наведение); звук
  (`-NoSound`).

## Открытые вопросы к владельцу
- Нет. Провал ворота в DeathSettle — пункт оркестратору (поздний фикс модели или known issue). Боец в эталонной БД
  сервера, фигура Wiglaf, FX/звук способности — вне скилла.

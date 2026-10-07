# EN-15 — цена рендера нарисованного Marmoreal (packaged, render_bench.py)

**Итог: PASS по всем порогам карточки, технически, по делегированию (2026-10-08, VS-5 шаг E5, ветка `feat/visual-vs5`).**
Машина — **ПК разработки (RTX 4090 / i9-13900F), не D-07.**

## Сборка и режим

- Одна упаковка ветки: `tools/s08/package-client.ps1`, штамп `b4938cab` (`BuildStamp.json`, `exeSha256`
  `1464d7eb…` в `*/cmdline.txt`). Финальная упаковка шага `b68e21b4` отличается только тестом
  `S08ArtTunerTests.cpp` и ветром `ampPx` 0,5 → 0,4 (ВР-VS5-47); в `-Bench` ветер заморожен, кадры K1 / K2×1,6
  совпадают с `b4938cab` (средняя |разница| 0,25 / 0,55, отличия только в позах фигур:
  [compare](../../../VISUAL/ENV-U16/data/compare-marmoreal-b4938cab-vs-b68e21b4.json)).
- `python tools/art/render/render_bench.py run --variant dx12-lumen-high-v2 --repeats 3 --views K1+K1x0.65+K2x1.6+K2x2.5`:
  прогрев 30 с, settle 8 с, замер 20 с на вид, без лимита FPS, DX12 SM6 / Lumen / High / SP 100, фикстура
  Marmoreal original, шесть фигур v2. Варианты чередовались по повторам (r1: paste → p5c → nofx, затем r2, r3), чтобы
  дрейф фона делился поровну:
  - `marm-paste` — без флагов (нарисованный задник по умолчанию, трасса `ARTLOOK board=marmoreal-original backdrop=paste(default)`);
  - `marm-p5c` — `--client-args=-NoConceptPaste` (`backdrop=p5c(flag-off)`);
  - `marm-paste-nofx` — `--client-args=-ArtPreviewNoFx` (вклейка без лепестков и светлячков, `fx=0 … particles=0`).
- ACC-022: `--variant dx12-lumen-high-v2-fps60 --views K1+K2x1.6+K2x2.5`, 1 прогон, без флагов.
- Фон GPU до замера 26–30 % (`gpu-background-before.txt`), после 18–30 % (`gpu-background-after.txt`): чужие процессы
  рабочего стола пользователя (браузер, оверлеи), игровых клиентов и сборок других сессий не было; замок
  `C:/tmp/unmatched-gpu.lock` держал раннер шага.
- Кадры всех 9 прогонов: RENDER `reference=1` (проверка `render_bench`).

## Числа (GPU avg, мс; среднее 3 повторов, шум = max − min)

| Вид | marm-paste | marm-p5c | marm-paste-nofx | paste − p5c | paste − nofx |
|---|---|---|---|---|---|
| K1 | **2,137** (0,01) | 2,483 (0,01) | 2,070 (0,02) | −0,346 | +0,067 |
| K1 ×0,65 | 2,093 (0,01) | 2,417 (0,01) | 2,030 (0,02) | −0,324 | +0,063 |
| K2 ×1,6 | **2,203** (0,01) | 2,423 (0,01) | 2,143 (0,01) | −0,220 | +0,060 |
| K2 ×2,5 | 2,230 (0,00) | 2,413 (0,01) | 2,163 (0,01) | −0,183 | +0,067 |
| GPU p95 K1 | 2,27–2,28 | 2,64–2,66 | 2,23–2,24 | | |
| FPS K1 | 228–230 | 205–206 | 231–233 | | |
| VRAM max (система) | 3747 / 3764 / 3748 МиБ | 3888 / 3917 / 3907 МиБ | 3750 / 3777 / 3752 МиБ | −153 | |

| Порог карточки | Значение | Итог |
|---|---|---|
| K1 GPU avg ≤ 2,60 мс | 2,137 | PASS |
| K1 ≤ marm-p5c + 0,10 мс | 2,137 против 2,483 (−0,346) | PASS |
| K2 ×1,6 ≤ 3,8 мс | 2,203 | PASS |
| marm-paste − marm-paste-nofx ≤ 0,15 мс | 0,060–0,067 на 4 видах | PASS |
| VRAM max ≤ marm-p5c + 64 МиБ | 3764 против 3917 | PASS |
| ACC-022: 60,00 FPS, p95 ≤ 16,7 мс на 3 видах | K1 / K2×1,6 / K2×2,5: 60,00 / 60,00 / 60,00 FPS, p95 16,67 / 16,67 / 16,67, max 16,68 / 16,67 / 16,73, рывков 0; GPU avg 2,24 / 2,25 / 2,25 | PASS |
| шум ≤ 0,05 мс | 0,00–0,02 мс | записан |

Нарисованный задник дешевле 3D P5c на 0,18–0,35 мс (нет мешей сада, дворца и подноса); анимации (мерцание через 5
точек, ветер и туман в материале) и частицы стоят в `-Bench` 0,06–0,07 мс. Sarpedon (lit3d) этим шагом не менялся:
контроль — кадры и сравнение с P10 в [дополнении GD-058](../../../GD-058/marmoreal-paste-2026-10-08/README.md).

## Кадры (открыты глазами)

`marm-paste/r1-bench-K1…K2x2p5` — настоящая карта Marmoreal, нарисованная плита без 3D-окружения, шесть фигур v2;
`marm-p5c/r1-bench-K1` — откат: 3D-дворец, сакуры Forest, фонари на тумбах, поднос; `marm-paste-nofx` — та же плита
без частиц. JPEG q90 из PNG прогона (PNG вне git, `C:/tmp/visual/E5/bench`).

## Файлы

- `bench-summary.json` — числа выше и проверка порогов по повторам; `render-bench-summary.json` — сводка
  `render_bench.py summarize` (проходы CSV, ProfileGPU, яркость).
- `<вариант>/r1-bench.trace.txt` (RENDER, ARTLOOK, concept-paste), `cmdline.txt`, кадры r1.

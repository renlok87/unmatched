# DE-012: кандидаты значков набора DE в галерее UE (2026-10-04)

Задача — DE-012 (W-15 арт, прогон A04), журнал — [A04-2026-10-04.md](../../../de-footage/task/runs/A04-2026-10-04.md).
Контракт — [icon-motion.json](../../../../unreal/contracts/hud/icon-motion.json), ревизия `icon-motion-2026-10-04`:
23 принятых значка v3 и 5 кандидатов (`candidates`), плюс damage сердца 1000 мс со слоем `glow`. Кандидаты — до
арт-приёмки пользователя, HUD их не использует.

## Галерея

Редакторский клиент `-game` (UE 5.8, DX12), 1920 × 1080 вне экрана. Те же шаги, что 2026-10-03, но с `-ForceRes`:
без него `-RenderOffScreen` даёт окно 888 × 500.

```powershell
UnrealEditor.exe unreal\Unmatched\Unmatched.uproject /Game/S08/S08Arena -game -windowed -ResX=1920 -ResY=1080 -ForceRes -RenderOffScreen -nosound -S08IconGallery -S08IconGallerySize=64 -S08IconGalleryShots=<dir> -S08IconGalleryTimes=0,60,120,200,350,600,1000,1300,1800,2000,2300,2600
```

Серии: `normal` (64 px), `reduced` (+ `-S08ReducedMotion`), `normal-32` (`-S08IconGallerySize=32`) — по 12 кадров.
В каждой серии `compare.png` («UE | эталон | |Δ|×4») и `compare.json` от `compare_ue_gallery.py`.

Из Git Bash путь `/Game/...` портится (MSYS превращает его в `C:/Program Files/Git/Game/...`) — запускать из PowerShell.

## Совпадение с эталоном Python

| Серия | Пар «значок × момент» | Средняя \|Δ\| всех 28 | Порог (2026-10-03) |
|---|---|---|---|
| обычное движение, 64 px | 336 | **0,393** | 0,45 |
| reduced motion, 64 px | 336 | **0,020** | — |
| обычное движение, 32 px | 336 | **0,726** | 0,81 |

По новым и изменённым записям (средняя \|Δ\| по 12 моментам / худший p99):

| Значок | 64 px | reduced | 32 px |
|---|---|---|---|
| `marker-turn-ring` | 0,025 / 1 | 0,015 / 1 | 0,030 / 1 |
| `marker-turn-ring-team` | 0,126 / 5 | 0,070 / 2 | 0,125 / 4 |
| `resource-hp-fallen` | 0,110 / 24 | 0,007 / 1 | 0,119 / 16 |
| `marker-x-stamp` | 0,093 / 19 | 0,009 / 1 | 0,105 / 11 |
| `marker-action-slot-de` | 0,568 / 35 | 0,015 / 1 | 0,997 / 38 |
| `resource-hp-full` (damage + glow) | 0,297 / 39 | 0,006 / 0 | 0,479 / 46 |

Максимумы — как и раньше, края при дробном масштабе (пульс кольца слота 1,06, глиф заливки 0,8 → 1,04): билинейная
выборка UE против PIL. Пропущенных слоёв и сдвигов нет. Кадры просмотрены: на 120 мс кольцо хода жёлтое, на 600 мс —
оранжево-красное, к 2000 мс тлеющее; крест павшего и крест-штамп встали; слот трекера на 600 мс — призрак в оранжевом
кольце, на 2000 мс — заполнен атакой.

## Автотесты

- `Unmatched.S08.IconMotion` — 8 / 8 Success: `Golden` 4496 поз, расхождений 0; `Textures` 256 текстур (64 имени);
  `Load` — 28 значков, 5 кандидатов.
- `Unmatched.S08` + `Unmatched.S09.HUD` — 199 / 199 Success.
- pytest `tools/s08/hud_contract` — 23 passed (7 новых тестов кандидатов, в том числе «id кандидатов нет в коде UE»).

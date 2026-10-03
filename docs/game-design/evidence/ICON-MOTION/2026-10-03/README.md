# Движение значков HUD v3 в UE: доказательства 2026-10-03

План — [ICON-MOTION-PLAN.md](../../../../unreal/contracts/hud/ICON-MOTION-PLAN.md), контракт —
[icon-motion.json](../../../../unreal/contracts/hud/icon-motion.json).

## Галерея в игре

Режим `-S08IconGallery`, редакторский клиент `-game`, 1920×1080, значки 64 px. Все 23 значка на панели HUD, каждый
играет свой сценарий из контракта. Часы замораживаются в моменты 0, 40, 100, 180, 300, 500, 700, 900, 1100, 1300, 1600 и
2000 мс, в каждый момент снимается кадр с UI (`TakeEvidenceShot`).

```bash
UnrealEditor.exe unreal/Unmatched/Unmatched.uproject /Game/S08/S08Arena -game -windowed -ResX=1920 -ResY=1080 -S08IconGallery -S08IconGalleryPerfFrames=600 -S08IconGalleryShots=<dir> -S08IconGalleryTimes=0,40,100,180,300,500,700,900,1100,1300,1600,2000
```

Второй прогон — то же с `-S08ReducedMotion`.

| Что | Где |
|---|---|
| Кадры, обычное движение | `normal/icon-gallery-normal-<t>.png` (12) |
| Кадры, reduced motion | `reduced/icon-gallery-reduced-<t>.png` (12) |
| UE против эталона Python | `normal/compare.png`, `reduced/compare.png`: «UE \| эталон \| \|Δ\|×4» по значку и моменту |
| Метрики сравнения | `normal/compare.json`, `reduced/compare.json` |
| Трасса прогонов | `gallery-trace.log` |

Сравнение делает скрипт `art/imagegen/hud-icons-v3/_tools/compare_ue_gallery.py`. Значок вырезается из кадра UE, эталон
строится `motion.compose()` в момент `t mod (сценарий + 400 мс)`.

## Результаты

| Проверка | Обычное движение | Reduced motion |
|---|---|---|
| Пар «значок × момент» | 276 | 276 |
| Средняя \|Δ\| по каналам, 0..255 | **0,451** | **0,020** |
| Худший 99-перцентиль | 89 (`state-threat` при 1300 мс) | 27 (`loader-spinner`) |

Максимумы — тонкие контуры при дробном масштабе: билинейная выборка UE против PIL. Сдвигов и пропущенных слоёв нет.
Повторный прогон дал те же числа до пикселя, то есть движение в движке детерминировано.

Стоимость (`-S08IconGalleryPerfFrames=600`, 599 кадров):

| Режим | `EvaluateAt` всех 23 значков, мс: среднее / p95 / макс | Кадр игрового потока, мс: среднее / p95 |
|---|---|---|
| обычный | 0,075 / 0,092 / 0,177 | 2,78 / 2,46 |
| reduced | 0,069 / 0,084 / 0,131 | 2,82 / 2,54 |

Галерея каждый кадр заново проигрывает сценарии всех значков. Это верхняя граница: в игре виджет тикает по шагу
времени, а в покое ничего не считает. Бюджет HUD 0,5 мс GT p95 (П8) соблюдён с запасом.

## Автотесты UE

```bash
UnrealEditor-Cmd.exe unreal/Unmatched/Unmatched.uproject "-ExecCmds=Automation RunTests Unmatched.S08.IconMotion+Unmatched.S08.ArtHudUmg+Unmatched.S08.ArtHud+Unmatched.S09.HUD; Quit" -unattended -nosplash -nullrhi
```

Итог 2026-10-03: 32 из 32 Success. Из них 6 — `IconMotion`:

| Тест | Что проверяет |
|---|---|
| `Golden` | 3566 эталонных поз Python, расхождений 0 |
| `Load` | контракт загружается |
| `Reduced` | флаг reduced motion |
| `Textures` | 200 текстур в 4 размерах |
| `Widget` | виджет значка |
| `CombatView` | анимированный жетон цели |

Остальные 26 — HUD без регрессий.

## Что не проверено

- **Жетон цели в живом бою.** Он включается флагом `-S08IconMotion`. Пробник `-S09HudProbe` создаёт виджет, это видно в
  трассе (`HUD art widget icon … source=icon-motion-v3`), но без начатой партии на сервере жетон не показывается. Нужен
  упакованный клиент и двухклиентное демо: `tools/s08/run-phase2-demo.ps1 -ArtPreviewBoardId … -ArtPreviewIconProbe
  -ClientExtraArgs "-S08IconMotion"`.
- **Звук на удары** (`beat_ms`) — следующий шаг.
- **Состояния подбора хода V-02..V-16** в игре ещё не реализованы (MS-T). Их значки получат движение через API
  `US08AnimatedIconWidget::PlayAnim`.

# DE-029 — экран результата: кадры редактора (2026-10-05)

Это не живая приёмка. Живую партию до FINISHED на Marmoreal original и Sarpedon original (G-LIVE) снимает DE-031 и
агент приёмки прогона F. Здесь — проверка вида модали и режима «посмотреть доску» до упаковки.

Кадры уменьшены до 1280×720 (JPEG 85). Исходник — 1920×1080, редактор `-game`, offscreen, 30 FPS, High, бенч-сцена
`Config/Bench/S08BenchMarmoreal.json` (Marmoreal · original map, Board `c121b47f8d6eb28daccb76d05`, профиль
`marmoreal-original`, шесть v2-фигур):

```
UnrealEditor.exe unreal\Unmatched\Unmatched.uproject /Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode -game
  -windowed -resx=1920 -resy=1080 -ForceRes -RenderOffScreen -ArtPreview -Bench -BenchOut=<dir> -BenchViews=K1
  -BenchWarmup=20 -BenchSettle=3 -BenchMeasure=1 -BenchFps=30 -BenchNoProfileGPU -S08RenderPreset=High
  -BenchResult=results|board [-BenchResultLoser]
```

`-BenchResult` — инструмент ревью DE-029. Он превращает снапшот бенча в терминальное тело сервера при убийстве героя:
`phase = GAME_OVER`, `metadata.winnerId`, герой проигравшего с HP 0, игрок проигравшего `isAlive = false`. Затем он
открывает экран результата через тот же путь, что и живой клиент: ворота DE-019, `RefreshHud`, `FS09ResultView`.
Строки `game(id)` в бенче нет, поэтому длительности на кадре нет: показан только «Turn 1» снапшота.

| Кадр | Опции | Что видно |
|---|---|---|
| `de029-results-victory-marmoreal.jpg` | `-BenchResult=results` | модаль поверх затемнённой сцены. Полоса маркеров GD-036 (#FFD700 / #FF0064 / #00FFA0 / #8000FF). «VICTORY» и «MEDUSA WINS» — заголовок по герою-победителю. Причина «King Arthur's HP reached 0» и «Turn 1». Слева диск Medusa цвета команды, справа King Arthur — тёмный силуэт на красном ободе. Кнопки «VIEW BOARD (V)» и «RETURN TO LOBBY (Enter)», подсказка клавиш |
| `de029-board-defeat-marmoreal.jpg` | `-BenchResult=board -BenchResultLoser` | итоговая доска после кроссфейда 250 мс. Фигуры Medusa нет, гарпии, Merlin и King Arthur стоят. Портреты DE-023 вернулись: Medusa 0/16, King Arthur 18/18, трекеров после GAME_OVER нет. Внизу полоса «FINAL BOARD · DEFEAT» с кнопками «VIEW RESULTS (Esc)» и «RETURN TO LOBBY (L)». Панели команд, руки и сбоку свёрнуты |

Кадры просмотрены. Поле — реальная карта Marmoreal. Вокруг поля — 3D-окружение P5c, а не нарисованный задник: это
известный разрыв ENV-U16 (AGENTS.md, «Known gap»), к DE-029 он не относится. Аватар на дисках — монограмма героя,
как у портретов DE-023. Настоящий `Hero.avatarUrl` — задача HI-05: в БД аватары лежат в WebP, а ImageWrapper в
UE 5.8 WebP не декодирует.

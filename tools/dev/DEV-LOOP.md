# Интерактивный dev-цикл UE-клиента (без перепаковки)

Запрос пользователя (2026-10-15): «Я не хочу полностью пересобирать игру каждый раз во время фикса. Запусти ее так
чтобы ты мог интерактивно ее фиксить».

Один uncooked-клиент `UnrealEditor.exe Unmatched.uproject -game -LiveCoding` запускается один раз и живёт всю сессию.
Правки C++ попадают в него через Live Coding (~8–30 с), ассеты и конфиги читаются с диска, упаковка не нужна.
Агент управляет клиентом через файловый канал `-DevExec=<папка>` (`S08/S08DevExec.cpp`): клики, клавиши, текст и
кадры с UI — синтетическими событиями Slate, реальные мышь и клавиатура пользователя не трогаются, окно может быть
под другими окнами.

## Команды

```
python tools/dev/devexec.py start [--res 1920x1080] [--vsai] [--mute]   # ~10 с до ready (после первой сборки)
python tools/dev/devexec.py shot <имя>                                 # C:/tmp/devexec/shots/<имя>.png (вьюпорт + UI)
python tools/dev/devexec.py run "click 960 540" "wait 1" "key E" "shot C:/tmp/devexec/shots/a.png"
python tools/dev/devexec.py lc                                          # Live Coding: компиляция + патч, ждёт итог в логе
python tools/dev/devexec.py log --grep "Error|HUD" -n 40               # хвост лога клиента (C:/tmp/devexec/client.log)
python tools/dev/devexec.py stop
```

Строки `run` (координаты — пиксели вьюпорта, та же сетка, что у PNG `shot`):

| строка | что делает |
|---|---|
| `click X Y [right]` | наведение + нажатие + отпускание; следующий шаг — на следующем кадре (фокус Slate меняется кадром позже) |
| `move X Y` / `drag X0 Y0 X1 Y1` / `wheel X Y D` | наведение / перетаскивание / колесо |
| `key Имя [ctrl\|shift\|alt]` | клавиша по имени FKey: `Enter`, `Escape`, `M`, `A`, `G`, `E`, `BackSpace`, `F10` |
| `type текст` | символы в виджет с фокусом |
| `wait сек` | пауза перед следующими строками |
| `shot путь.png` | кадр с UI (`FScreenshotRequest`, bShowUI), ответ после записи файла |
| `res 1280x720w` | `r.SetRes` (w — окно, f — полный экран, wf — окно без рамки) |
| `info` | размер вьюпорта, DPI, позиция окна, мир, game mode |
| всё остальное | консольная команда (`stat fps`, `LiveCoding.Compile`, `quit`, CVars) |

Тестовые аккаунты — из сидов (`backend/prisma/seed.ts`). Аккаунт, которым пользователь играет сам, не занимать.

## Что требует чего

| правка | путь |
|---|---|
| тело функции в `.cpp` | `devexec.py lc` |
| новый файл `.cpp`, новый `UCLASS/USTRUCT/UPROPERTY`, правка `.Build.cs` | `devexec.py stop` → `node tools/s08/build-editor.cjs UnmatchedEditor Win64 Development -Project=<uproject> -WaitMutex` → `start` |
| `Config/*.json`, `*.ini`, ассеты | перечитываются кодом или после `stop`/`start` (10 с) |
| бэкенд | `docker exec unmatched-backend npm run build && docker compose restart backend` (bind mount) |

- Патч Live Coding живёт только в памяти: перезапуск клиента грузит DLL с диска. Перед `stop`/`start` после патчей —
  инкрементальная сборка (`build-editor.cjs`, ~20 с), иначе клиент поднимется со старым кодом. То же для правок кода,
  который строит виджеты при старте (BuildUi): патч его не перестроит, нужен рестарт со сборкой.
- Структуры (поля `struct`/`UCLASS`, в т.ч. объявленные в `.cpp`, например `FUmHudRuntime`) — только полная сборка:
  Live Coding поменяет раскладку, а живые объекты останутся старыми.
- Ввод драйвера: виртуальный курсор Slate (`UsePlatformCursorForCursorUser(false)`), нажатие и отпускание — в разных
  кадрах; `ViewportHasFocus()` при `-DevExec` считает окно активным. Играть руками в том же окне — `run "cursor os"`.
- Ошибки компиляции Live Coding `devexec.py lc` печатает из `%LOCALAPPDATA%/UnrealBuildTool/Log.txt`.
- Пока клиент с `-LiveCoding` жив, Build.bat `UnmatchedEditor` падает во **всех** чекаутах (мьютекс Live Coding,
  `docs/unreal/UE-SESSION-DESIGN.md` F9). Перед полной сборкой — `devexec.py stop`.
- Кадры uncooked `-game` годятся для итераций; приёмочные кадры по-прежнему из packaged `-Bench` (AGENTS.md).
- После задачи: `devexec.py stop` (убивает только PID своей сессии из `C:/tmp/devexec/session.json`).

# Бэкап ассетов Unmatched

Restic шифрует снимки проекта на компьютере, rclone передаёт их в Google Drive.
Рабочие файлы остаются в проекте на SSD. В Диске хранится зашифрованный репозиторий
`Unmatched-Backups/Assets`; его файлы нужно читать через restic.

## Что сохраняется

Весь проект с диска, включая неотслеживаемые и игнорируемые Git файлы:
`art`, `blender`, `scraped-data`, `public`, Unreal `Content`, `Config`, `Source`,
плагины, документы и концепты, аудио, исходники и инструменты.
`.blend1`, черновики и `Saved/Autosaves` сохраняются. Новые ассеты внутри проекта
попадают в следующий снимок автоматически. Файлы незаконченной загрузки или экспорта
могут нуждаться в следующем снимке.

Исключены зависимости, `.git`, кэши сборки, собранные клиенты, временные профили
браузера, локальные настройки агентов и файлы секретов (`.env*`, ключи, сертификаты).
Точные правила находятся в `policy.json`. Плагинные `Binaries` не исключены.

## Расписание и состояние

Задачи Windows: `Unmatched-Assets-Backup` — каждый час и при входе в Windows;
`Unmatched-Assets-Maintenance` — ежедневно в 03:30, пропущенный запуск при следующей возможности.
Компьютер должен быть включён, а пользователь — войти в Windows.
Пароль входа в Windows для задач не сохраняется. Сон компьютера не прерывается.
Параллельные запуски блокируются; ошибка помечается как ошибка и повторяется через 15 минут.

Хранятся 24 последних снимка, 14 дневных, 8 недельных и 12 месячных.
Ежедневная проверка читает структуру и одну из 30 частей данных; номер части меняется по дням.
Удаляются только старые снимки сверх этого срока. После удаления ассета на компьютере
он доступен в тех снимках, которые ещё хранятся.

Установленная копия и состояние: `%USERPROFILE%\.unmatched-backup`.
Папка находится вне AppData, чтобы её видел планировщик Windows даже при запуске установки из приложения Microsoft Store.
`status.json` — текущая операция и последний успешный снимок; `logs` — журналы.
Пароль защищён DPAPI этой учётной записи Windows. Папка доступна пользователю и SYSTEM.
Пароль, OAuth-токены и локальная конфигурация не попадают в Git и в бэкап.

**Сохрани `RECOVERY-KEY.txt` в менеджер паролей или на отдельный носитель.**
При потере пароля и этой учётной записи Windows зашифрованные файлы не восстановить.
При переустановке rclone сохрани собственные Google client ID и secret в том же хранилище паролей:
доступ `drive.file` привязан к создавшему файлы Google-приложению.

## Запуск и восстановление

```powershell
$runner = "$env:USERPROFILE\.unmatched-backup\backup.ps1"
& $runner -Action Status
& $runner -Action Backup
& $runner -Action Snapshots
& $runner -Action Restore -Snapshot latest -Target 'C:\Restored-Unmatched'
& $runner -Action Check
```

Восстановление пишет в новую пустую папку вне проекта; после проверки можно перенести
нужные файлы обратно. Для отдельных путей есть `-Include '*model.blend'`;
для прошлой версии передай её snapshot ID из `Snapshots`.

## Установка и обновление

1. `powershell -NoProfile -ExecutionPolicy Bypass -File tools\backup\setup.ps1`.
2. Настроить rclone remote `unmatched-gdrive` с отдельным OAuth client ID и областью доступа `drive.file`.
   Конфигурация: `%USERPROFILE%\.unmatched-backup\rclone.conf`.
3. Для **нового** хранилища: `backup.ps1 -Action Initialize`, затем `-Action Backup`, `-Action Check`.
4. `setup.ps1 -RegisterTasks` включает расписание и обновляет установленные скрипты.

При восстановлении **на другом компьютере** не создавай новый репозиторий.
Установи restic/rclone, подключи тот же Google Drive и OAuth-приложение. Пароль из `RECOVERY-KEY.txt`
введи в запрос restic при запуске:

```powershell
$env:RCLONE_CONFIG = 'C:\Path\To\rclone.conf'
restic -r rclone:unmatched-gdrive:Unmatched-Backups/Assets snapshots
restic -r rclone:unmatched-gdrive:Unmatched-Backups/Assets restore latest --target C:\Restored-Unmatched --verify
```

Если rclone не в PATH, добавь к restic `-o "rclone.program='C:/Path/To/rclone.exe'"`.
Перед сменой OAuth-приложения проверь доступ к старым файлам репозитория.

Локальная проверка без облака: `python -m unittest discover -s tools/backup -p test_backup.py -v`.

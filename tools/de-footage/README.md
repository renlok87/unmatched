# tools/de-footage — разбор видео и живое исследование Unmatched: Digital Edition

Инструменты к `docs/game-design/de-footage/`. Данные лежат вне репозитория: видео, листы, ленты и записи — в
`C:/tmp/de-footage/` и `C:/tmp/de-live/`. Кадры чужого видео и игры в git не кладутся.

| Файл | Что делает |
|---|---|
| `ytdl_doh.py` | yt-dlp с DoH-резолвом внутри процесса: роутер отвечает NXDOMAIN на youtube.com. Нужен `--cookies` (бот-проверка IP) и `--js-runtimes node`; запуск из venv `C:/tmp/de-footage/tools/venv` |
| `chapters.json` | главы ролика G6wJgtcOjVA |
| `prep.py` | `scan` — один проход NVDEC: листы 4x4 (кадр раз в 2 с) и таймлайн движения 30 fps; `segments` — отрезки движения |
| `vtt2txt.py` | автосубтитры YouTube → стенограмма по главам |
| `burst.py` | `strip` — лента кадров с метками мс; `frame` — кадр; `motion` и `segs` — только для ролика. Видео задаётся в `C:/tmp/de-footage/work/video.txt` |
| `de_record.py` | запись окна игры 60 fps (NVENC) и системного звука (WASAPI loopback, `soundcard`); стоп — файл `STOP` |
| `de_preflight.py` | проверка перед живой сессией: ffmpeg+NVENC, venv и loopback, нет клиентов Unreal проекта, окно DE из Steam, место на диске |

Процесс живой сессии — `docs/game-design/de-footage/task/06-live-study-runbook.md`.

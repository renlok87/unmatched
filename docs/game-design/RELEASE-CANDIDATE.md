# Release candidate — внутренний прототип (GD-054)

Состояние на 2026-10-16, пакет `9360ae41` (полоса стадий хода HB-50, шрифт Philosopher). Это инструкция запуска и отката одного кандидата, а не публичный релиз.

## Что входит

- **Клиент:** Development-пакет UE 5.8, `unreal/Unmatched/Saved/StagedBuilds/Windows/` (запуск
  `Unmatched.exe`, без редактора). Штамп `BuildStamp.json`: коммит и `sourceHash` сборки. Копия в другой чекаут —
  `tools/s08/sync-staged-build.ps1 -From <чекаут>` (отказывает, если штамп не совпадает с HEAD).
- **Сервер:** NestJS + Prisma + Redis в Docker (`docker compose up -d`): Postgres `127.0.0.1:5433`, Redis `6379`,
  backend `127.0.0.1:3000` (GraphQL `http://localhost:3000/graphql`, тот же адрес — WebSocket).
- **Контент:** локальный, в `.pak` клиента (арт карт, фигуры, доски Marmoreal и Sarpedon, звук, шрифты, строки RU/EN)
  и в Postgres (герои, карты, доски — сиды `backend/prisma`). Внешних CDN и сетевых загрузок нет.

## Запуск (чистая машина, Windows 10/11, GPU с DX12 SM6 или SM5)

1. Docker Desktop. В корне репозитория: `docker compose up -d`. Проверка: `docker ps` — `unmatched-postgres`,
   `unmatched-redis`, `unmatched-backend` в состоянии Up.
2. Если БД пустая (`docker exec unmatched-postgres psql -U unmatched -d unmatched -tc 'SELECT count(*) FROM "Hero";'`
   даёт 0), из `backend/` по порядку: `npx prisma db seed` (тестовые аккаунты, пароль в `prisma/seed.ts`),
   `npm run prisma:seed-admin`, затем `npx ts-node --transpile-only -e "require('./prisma/<файл>.ts')"` для
   `seed-scraped`, `seed-all-scraped`, `fix-card-gaps`, `fix-audit-findings`, `fix-roster-ru` (именно в этом порядке).
3. `unreal/Unmatched/Saved/StagedBuilds/Windows/Unmatched.exe`. Другой сервер — ключ `-S08Api=http://<host>:3000/graphql`.
4. Вход → «Против ИИ» → «Создать» → выбрать героя (Король Артур или Медуза) → «Готов» → «Начать партию». PvP: второй
   клиент входит в комнату по коду или из списка игр.

## Совместимость с сервером

- Клиент и сервер собираются из одного коммита (`BuildStamp.json` ↔ `git log` бэкенда). Номер протокола проверяется
  при входе: клиент спрашивает `serverInfo { protocol }` и при расхождении (или на сервере старше проверки) стоит на
  экране загрузки с «Сервер другой версии» и «Повторить». Номер меняется в двух местах вместе:
  `backend/src/health/protocol.ts` и `unreal/Unmatched/Source/Unmatched/S08/S08Protocol.h`
  (`tools/s08/test_protocol_version.py`).
- Ростер клиента — Король Артур и Медуза. Герой вне ростера на другом месте блокирует старт
  («Герой соперника пока не поддерживается в этой версии»).

## Откат

- **Клиент целиком:** предыдущий пакет — `git checkout <коммит штампа>` и `tools/s08/package-client.ps1`, либо копия
  прошлой папки `StagedBuilds`.
- **Отдельные части арта и HUD — флаги командной строки** (AGENTS.md «Rollback flags»): `-S08SlateHud` (весь UMG-HUD →
  Slate), `-S08FontLegacy` (шрифт Lora → Roboto), `-S08GreyBoard`, `-S08HeroesLegacy`, `-NoConceptPaste` и др.
- **Сервер:** `git checkout <коммит>` в `backend/` → `docker exec unmatched-backend npm run build` →
  `docker compose restart backend`. Данные — volume Postgres (бэкап `pg_dump` перед откатом схемы).

## Секреты

Пакет проверен поиском по `.pak/.ucas/.utoc` и всем несжатым файлам: нет паролей, JWT-секретов, `DATABASE_URL`,
токенов. Логин тестовых прогонов передаётся только через переменные окружения процесса (`S08_EMAIL` / `S08_PASSWORD`),
не через командную строку; в трассы и `client.log` пароли и токены не пишутся (проверено на 8 трассах вечера).
Папка `Saved/` внутри StagedBuilds — вывод запусков (трассы, настройки), в раздачу её не включать.

## Ограничения прототипа (видимые игроку)

Два героя (Артур, Медуза), две доски, режимы 1×1 и против ИИ; часть служебных подсказок трассы на английском;
производительность не замерена на целевом ПК (GD-045 / GD-051).

# FINAL-PKG — пакет после финального ревью (2026-10-05)

Финальное ревью ([REVIEW-IMPL-2026-10-04-fable.md](../../../../de-footage/task/runs/REVIEW-IMPL-2026-10-04-fable.md))
исправило шлюз результата DE-019 (`5e950d33`) и пометило упаковку `f4d77d98` устаревшей. Оркестратор после него:

1. Пересобрал бэкенд в контейнере (`docker exec unmatched-backend npm run build`, перезапуск): `dist` был от 15:21, то есть
   без исправления выбора героя ботом. `/health` ok.
2. Перепаковал клиент: `tools/s08/package-client.ps1`, штамп `2420dda7` = HEAD, `skipBuild=false`.
3. Прогнал один живой бой двух клиентов до GAME_OVER на **Marmoreal original** (`-ConceptPaste`, v2-фигуры) —
   `tools/s09/run-combat-demo.ps1` с теми же ключами, что прогон F (CLOSEOUT §6). Аккаунты — засеянные тестовые
   из `backend/prisma/seed.ts` (значения `S09_DEMO_*` в `backend/.env` к основной БД :5433 не подходят).

## Результат

| Проверка | Хост | Соперник |
|---|---|---|
| `cue_contract check-trace --min-ms-cue 1 --min-combat 1 --min-death 1 --min-sound 1` | PASS | PASS |
| бои: 14, длительность | 3933 мс | 3933 мс |
| удар → экран результата (F-09 ≈ 3,1 с) | 3167 мс | 3167 мс |
| `RESULT screen` | `wait=5567`, без `staging=` (шлюз не держал) | то же |
| `ARTLOOK` | `heroes=v2 env=on source=default` | то же |
| CUE-звук | 34 точки, фолбэк без ассетов | 33 точки |

Кадры просмотрены оркестратором: доска — Marmoreal original, нарисованный задник из концепта, шесть v2-фигур;
экран результата «DEFEAT / MEDUSA WINS» с кнопками VIEW BOARD и RETURN TO LOBBY.

PNG клиента пересохранены в JPG (q88), трассы `.log` переименованы в `.trace.txt` (`*.log` в `.gitignore`).
Хэши в `manifest.json` относятся к исходным PNG.

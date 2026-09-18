# S01 scoped review

2026-09-18. Независимое чтение harness, UE source/config, baseline, task statuses и доказательств.

- P2: старый screenshot мог пройти новую smoke-проверку. Исправлено: удаляются только два точных run-output пути, проверяются свежесть/размер/markers/exit code. Новый standalone прогон прошёл в 08:09 UTC.
- P2: optional `combat-defense.json` мог остаться от предыдущей случайной руки. Исправлено: очистка только JSON своего сценария до login; вложенные/чужие файлы не затрагиваются. Offline-проверка изолирована во временном каталоге; после исправления все live-captures повторены.
- Дополнительно: полностью заданные account env-переменные больше не требуют чтения legacy credential fixture. Проверено с mocked fetch, без сети.

Повторное узкое ревью: обе находки устранены; новых существенных замечаний к заявленной приёмке нет. Независимая финальная проверка main: EXE SHA-256/размер, UE runtime markers, geometry projection hash, результаты импорта, schema/JSON, ссылки, 30+30 instance counts, обе WS-проекции, обезличивание и статусы задач — PASS (`verification.txt`).

Это не ревью исправления backend-правил: его код в S01 не менялся. Полные game/network/art/performance gates остаются открыты по README.

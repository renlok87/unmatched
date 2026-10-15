# Отказы транспорта на финальном коде — 2026-10-15 (GD-037 / GD-038)

Повтор пакета `evidence/S10/packaged-fault-runs-2026-09-27.md` на текущем коде (после HUD v2 и фиксов вечера,
коммит `d23ced7c`): dev-клиент `-game -LiveCoding -DevExec`, `-S08Api=http://localhost:3122/graphql`, прокси
`tools/s10/drop-graphql-reply-proxy.cjs` (пропускает мутацию на бэкенд :3000 и выбрасывает только её HTTP-ответ),
тестовый аккаунт `veteran`, VS_AI, Marmoreal. Одна партия, по очереди четыре мутации; перезапуск прокси между ними
заодно оборвал WebSocket.

| Отказ | Клиент (trace-excerpt.txt) | Сервер (server-journal.txt) |
|---|---|---|
| ответ `attack` потерян после коммита | `ATTACK failed: outcome unknown … (no resend)`, `RECOVERY refetch 1/5`, `complete … seq 5` | одна `ATTACK_INITIATED` (seq 4) |
| WebSocket оборван (перезапуск прокси) | `WS closed 1006`, `RECONNECT state=auto attempt=1`, `WS reconnected - refetching gameState`, `state=restoring`, `FX cut reason=reconnect` | — |
| ответ `resolvePendingEffect` (способность Медузы) | `PEND resolve failed: outcome unknown … (no resend)`, `RECOVERY complete … seq 11` | одна `CARD_PLAYED` (seq 11); HP Артура 15 → 14, один урон |
| ответ `maneuver` | `RECOVERY refetch 1/5`, `complete … seq 13`, ход применён | `MANEUVER` seq 12 (begin) + 13 (ходы) — без повтора |
| ответ `playDefense` | `DEFENSE failed: outcome unknown … (no resend)`, `RECOVERY complete … seq 17`, бой закрыт (`COMBAT-RESULT damage=0 role=defended`) | одна `DEFENSE_PLAYED` (seq 17) |

`proxy-events.jsonl`: `reply_dropped_after_commit … forwarded=1` для каждого поля. Кадры: `fault-after-choice.jpg`
(после потерянного ответа выбора — ход продолжается, урон 1 применён один раз), `fault-after-defense.jpg`.

Вывод: на финальном коде обрыв после отправки / в выборе / в манёвре / при защите не повторяет затрат, восстановление
одним авторитетным запросом. Не повторено здесь: refresh-ротация токенов и rate limit (GD-038 — покрыты UE-тестами
`Unmatched.S10.*` и пакетным прогоном 2026-09-27), пакетный клиент двух мест.

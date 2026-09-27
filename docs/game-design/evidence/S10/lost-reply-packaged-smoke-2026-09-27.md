# S10 packaged lost-reply smoke — 2026-09-27

This is a diagnostic run of the **first** S10 client build, before the
adversarial review fixes. It does not close GD-037/GD-038 by itself.

The S10 proxy forwarded GraphQL and WebSocket traffic to the S09 local
backend. It logged `reply_dropped_after_commit` for the first successful
`attack` (`forwarded=1`). In the host packaged-client trace, `ATTACK sent`
was followed by `ATTACK failed: outcome unknown`, `RECOVERY refetch 1/5`, and
`RECOVERY complete: authoritative state at seq 2`. There is no second attack
send in that initial recovery interval; the next attack is at seq 25 in a
later turn. This directly exercised client recovery against a real committed
server mutation and an absent HTTP reply.

The two-client driver completed a full duel: both seats reached sequence 153,
showed opposing VICTORY/DEFEAT outcomes, returned to clean lobbies, and exited.
The authoritative game row remained `FINISHED` after leave, with the winner,
both seats, and end time; winner/loser stats and Elo changed as expected.
An independent read of the S09 Postgres `GameAction` journal for this room
returned exactly one `ATTACK_INITIATED` at sequence 2 (surrounded by
`GAME_STARTED` at 1, `DEFENSE_PLAYED` at 3, and `COMBAT_RESOLVED` at 4).
The driver published
[`run/duel-20260927-141213/manifest.json`](run/duel-20260927-141213/manifest.json);
all 31 listed files passed size and SHA-256 verification.

Remaining gates: the original proxy did not prove that the downstream socket
was still live when it dropped the reply. The client trace independently
shows the transport failure and refetch, but the proxy and client have since
entered adversarial repair. A fresh packaged build and replay are required.
This run did not inject a lost pending-choice reply, expired JWT, or WebSocket
barrier race. The demo's per-process `t.MaxFPS 30` setting is a command, not a
measured effective FPS or GPU-frame-time result.

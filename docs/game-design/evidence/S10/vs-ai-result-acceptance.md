# S10 GD-039/040 — client acceptance gate

This is an implementation checklist, not a completion report. The server-side
VS_AI slice is in `evidence/S10/README.md`; the client must use the same
authoritative GraphQL room and game-state contract.

| Scenario | Required client behavior | Evidence |
| --- | --- | --- |
| Create VS_AI from visible lobby | Send `createGame(mode: VS_AI)`; show one human seat and bot mode from room metadata | UI/controller test and packaged screenshot |
| Hero selected, human ready, one-seat start | Server adds the bot on `startGame`; client attaches live state without waiting for a second human | Packaged one-client flow |
| Bot acts or thinks | Existing combat/pending UI and snapshot remain authoritative; waiting indicator follows actual bot turn/state, not a fixed timer | Bot attack, defense and required choices in fixed live scenarios |
| Terminal `FINISHED` | Render winner/draw from `GAME_OVER` and server winner; disable gameplay, retain leave action | Server row + packaged result + disabled input |
| Live room becomes `ABORTED` | Fetch room status while started; show interruption distinct from victory without inferring a winner from an old snapshot; disable gameplay | Server abort + packaged screen/input check |
| Leave terminal room | Wait for accepted leave, tear down board/stream, return to clean lobby | Packaged lobby and server room row |
| Create next room | New create intent gets a new idempotency key; retries of that same intent keep its key | Two successive room IDs and a lost-reply retry test |

Do not treat `gameEnded` named CUE alone as an authoritative room outcome.
`gameStateUpdated` and a fresh HTTP snapshot establish state; the room row
establishes `ABORTED` versus `FINISHED`. Avoid changing the 60 FPS packaged
default to satisfy the two-client demo's 30 FPS per-process cap.

Observed on the reviewed 2026-09-27 Development package: visible VS_AI
selection, one-human start, real bot seat, authoritative `FINISHED` result,
authoritative `ABORTED` interruption with blocked commands, and clean lobby
return passed. Evidence is in
[`vsai-20260927-190850`](run/vsai-20260927-190850/manifest.json) and
[`vsai-abort-20260927-190951`](run/vsai-abort-20260927-190951/manifest.json).
The idempotency-key retry, rotation, and superseded-CREATE/JOIN race passed
automation (`Unmatched.S10` 50/50); two successive room IDs in one packaged
client process remain an open live check. The bot's waiting indicator is
covered by a controller test and the packaged match trace, not a timed UI
observation across every pending-choice class.

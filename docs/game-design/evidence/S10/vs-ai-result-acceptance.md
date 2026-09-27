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

# S10 verification plan (GD-037..GD-041)

This plan is a gate checklist, not a claim that S10 has passed. The oracle is
`14-sprint-backlog.csv` GD-037..041, `15-rules-and-release-acceptance.md`
ACC-012/019/021, and `16-network-contract.md`.

| Gate | Injection or run | Required result |
| --- | --- | --- |
| Lost response | Commit attack, defense, beginManeuver or pending choice on the server, drop only the HTTP reply, then deliver WS before/after a fresh query. | Exactly one mutation/cost, authoritative phase and sequence restored, no old/duplicate CUE. |
| Subscription window | Move the only mutation before subscribe, during barrier load, and after barrier; include stale and equal-sequence frames. Repeat with more than 100 journal entries and an empty journal. | State converges without relying on journal replay; equal-sequence panels merge; no permanent stale client. |
| Expired auth | Expire access token during defense and while a mutation reply is unknown; inject WS 4403 and successful/failed refresh, 4408/4409, HTTP failure and 429. | Refresh rotates tokens and rebuilds WS; failed refresh returns to login; no blind mutation retry or secrets in logs. |
| VS_AI choices | Bot in both seats and hero orientations, each mandatory pending class and hand-limit discard; optional decline and zero-legal-choice cases. | Queue order, exact card instances, privacy and monotone sequence hold; no stalled mandatory head. |
| VS_AI match | Deterministic full games with bot as Medusa and Arthur; attack/defense deadline and interrupted drain. | Authoritative GAME_OVER without administrative edits; a human defense window is preserved. |
| Abort/finish race | Pause nonterminal publication, commit abort, then release; reverse terminal ordering. | ABORTED cannot reappear playable or as VICTORY; FINISHED keeps winner and once-only statistics. |
| Leave/repeat | Reject then accept leave, deliver late old HTTP/WS frames, enter a new room with lower sequence. | Rejection keeps room; accepted leave resets match; old callbacks cannot rewrite new room; victory/defeat/interruption differ. |

Use the S08 HTTP/WS and S09 combat/pending fixtures as inputs, but inject faults
at the transport boundary with an explicit server commit and final authoritative
query. Fixture-only UI replay does not prove a lost response or subscription
window. Run focused Jest and UE automation, then the packaged two-client and
VS_AI flows; record exact commands, results, logs, manifests and open gaps.

`tools/s10/drop-graphql-reply-proxy.cjs` is the one-response fault injector:
it forwards HTTP and WebSocket locally, waits for a successful mutation reply
from upstream, then destroys only that downstream HTTP response. A preliminary
smoke on 2026-09-27 confirmed `query { __typename }` returned `Query` through
the proxy and a `graphql-transport-ws` upgrade opened. **No mutation was
dropped in this backend smoke**. The independent mock-upstream test
`node --test tools/s10/drop-graphql-reply-proxy.test.cjs` passes (2/2):
the first successful `attack` reply is reset after the mock commit, the
second is delivered normally, and the WS upgrade is tunneled. A drop is now
claimed only when the downstream SOCKET is still alive at commit time - if
the client aborted first, the proxy emits `reply_drop_skipped`, preserves
the one-shot budget, and a later live request still gets its drop. The
packaged commit/drop/reconcile gate remains open.

## Adversarial review P1/P2 - module-level guarantees (2026-09-27)

Adversarial review findings P1(1)-(4) and P2(5)-(8) are implemented and
covered by UE automation tests (offline HTTP/WS harness, no live server):

- P1(1): the GD-037 lock releases only on fresh evidence - an HTTP read
  dispatched while armed, or a WS sequence strictly past the arm baseline;
  a same-seq stale WS snapshot holds the lock (`stale same-seq WS snapshot
  keeps the recovery lock`, `WS seq past the arm baseline releases the
  lock`).
- P1(2): a truncated/malformed HTTP 200 after the server answered is
  outcome-unknown - parse failure arms recovery, no manual resend, and the
  recovery lock owns the error surface (`truncated or malformed mutation
  reply locks recovery`).
- P1(3): HTTP gameState bodies (barrier and recovery refetch) fire no cues
  at any gap size; live WS transitions keep firing them (`barrier body with
  a contiguous move fires no cues`).
- P1(4): a deferred refresh for identity A is dropped after a login as B -
  generation gate on every identity/session change plus a returned-user
  check before token rotation (`deferred refresh from the previous
  identity is dropped`).
- P2(5): a 401 on a gameplay mutation refreshes once and refetches
  authoritative state; the mutation is never replayed (`401 gameplay
  mutation refreshes once and refetches state; no replay`).
- P2(6): gameplay commands are gated until the state stream is acked; the
  reconnect banner's "input locked" promise is enforced
  (`commands are gated until the state stream is ready`).
- P2(8) + 4409: WS close reasons are redacted to the numeric code and a
  fixed client-side description; 4409 reconnects without auth; the
  pending-choice fault path shares the recovery contract (`WS close reason
  is redacted to code and fixed description`, `lost pending-choice
  response locks and converges via WS`).

Exact runs (2026-09-27, Development editor build): `Unmatched.S10` 20/20
pass, `Unmatched.S08` 44/44 pass, `Unmatched.S09` 44/44 pass; node proxy
tests 2/2 pass. These are module gates only.

Post-review client gate (2026-09-27): `Unmatched.S10` 50/50,
`Unmatched.S08` 46/46, and `Unmatched.S09` 44/44 pass. The reviewed
Development package builds with `-MaxParallelActions=4` and
`-NoHotReloadFromIDE`; packaged VS_AI result and abort runs are recorded in
[`vsai-20260927-190850`](run/vsai-20260927-190850/manifest.json) and
[`vsai-abort-20260927-190951`](run/vsai-abort-20260927-190951/manifest.json).
These prove the client-side result/interruption screens and clean lobby, but
do not replace the separate GD-041 human playtest or target-GPU measurement.

## Live packaged proof requirement

The packaged two-client commit/drop/reconcile gate must observe BOTH: (a) a
client-observed reset (the S10 client traces the recovery lock arm and its
fresh release after the dropped reply - the proxy `reply_dropped_after_commit`
event alone does not prove the client saw it, and `reply_drop_skipped` must
be interpreted as "client abort, not a fault injected"), and (b) an
independent state read (server-side query or second seat confirming the
sequence advanced exactly once). Neither observation alone closes the gate.

GD-041 is human observation: three people outside development, six sessions
with swapped sides. Record whether all three find the active player and legal
action unaided, whether at least five of six make a meaningful first move in
three minutes, decision/match time, input errors, and unclear range, boost,
choices or result. Convert blockers into measurable tasks. The six sessions
do not establish game balance.

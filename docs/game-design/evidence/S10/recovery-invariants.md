# S10 recovery invariants and adversarial cases

This is the implementation gate for GD-037/038, following the two read-only
reviews and packaged fault runs. It is a checklist of required behaviour, not
an assertion that every case currently passes.

| State / input | Required transition | Proof |
| --- | --- | --- |
| Login A, then login B; A reply arrives last | Ignore all A callbacks; B owns identity, tokens, room and socket | Deferred HTTP response test in both orders |
| Relogin during A's room/stream or pending `myGames` | Tear down A stream/operation and invalidate all A room callbacks before B can enter a room | Delayed `myGames`, room mutation and WS frame tests |
| WS closes or its operation fails/malformed `next` arrives | Input closes immediately; bounded resubscribe + authoritative read start | Malformed/null operation frame and operation error tests |
| WS acknowledges but subscription/read have not reconciled | Input stays closed until both a live operation and fresh authoritative state are established | Ack/read/order and repeated-subscribe-failure tests |
| Initial WS barrier snapshot after reconnect | Apply state without replaying old CUE, even for exactly one missed sequence | Local seq 10 → barrier seq 11 → live seq 12 test |
| Gameplay mutation reply is lost or unparseable | Do not resend; lock until bounded authoritative reconciliation establishes outcome or reports a recoverable failure | Commit/drop/refetch packaged trace and malformed-200 test |
| Pending-choice reply is lost | Keep the choice locked until a **valid** authoritative pending list explicitly lacks that effect ID; an unrelated seq advance or absent metadata is not proof | Pending-head + unrelated event + missing metadata test |
| Known rejected mutation receives 401 | Refresh once, reconcile state, reset automation draft; any retry is explicit and bounded, never a replay of an unknown outcome | 401 attack automation test |
| Automation command is gate-blocked | Do not count an attempt, change mode, or print `sent`; wait for readiness | Packaged startup and pending-choice disconnect tests |

The playable snapshot is authoritative. `eventsSince` is an action journal, not
state replay; CUEs for sequences already applied must stay suppressed. The
two-client driver must assess stream progress and terminal completion for each
seat separately. A full duel passing under one ordering does not replace the
negative-path tests above.

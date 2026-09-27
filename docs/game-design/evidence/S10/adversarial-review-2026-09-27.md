# S10 client recovery — adversarial review (2026-09-27)

Read-only Sol6 high review of the uncommitted GD-037/038 correction against
`recovery-invariants.md`, after 33/33 S10, 45/45 S08 and 44/44 S09 automation
tests passed. The review found the following failures; the green suites alone
do not close the sprint. A second GLM-5.3 correction pass is in progress.

| Severity | Finding | Required regression |
| --- | --- | --- |
| P1 | A lost `discardToLimit` reply can remain locked forever: a complete settled snapshot legitimately omits `pendingHandDiscard`, while a partial body must not prove settlement. | Distinguish complete authoritative body from partial, exercise both. |
| P1 | HTTP read seq 10 can clear the first WS barrier before opening snapshot seq 11, replaying old CUE. | Read-first, WS-second, one missed sequence, no old CUE. |
| P1 | A locally registered replacement WS operation plus HTTP read can open input before server acceptance; a later operation error arrives too late. | Read-before-WS-error stays gated; valid live frame and read unlock. |
| P2 | `pendingEffects:[null]` passes the metadata shape check though parsing silently skips the invalid entry; a lost-choice lock may release. | Malformed element retains lock, valid empty list may settle. |
| P2 | New budget and 401 tests target helpers/delegates rather than the production `RunS09Auto` transition. | Test exact shared transition or GameMode path for blocked send and known rejection. |

This record is a finding list, not a pass verdict. After correction, rerun the
three UE suites, proxy/watchdog tests, editor/package build and both packaged
commit/drop scenarios. Independent re-review must confirm the P1/P2 cases
before GD-037/038 are marked complete.

## Second read-only review

The five findings above have targeted corrections, and independent runs passed
S10 38/38, S08 45/45 and S09 44/44. A further Sol6 high review found two
remaining issues. The first can still open input after an unverified lost reply;
GD-037/038 remain open until both are corrected and retested.

| Severity | Finding | Required regression |
| --- | --- | --- |
| P1 | A fresh HTTP snapshot with `pendingEffects:null`, `pendingHandDiscard:null`, or a discard object without an ID is treated as if the pending key were absent; the choice lock can release without valid settlement proof. | Keep the lock for each present-but-invalid value, while allowing actual absence on a complete authoritative body to settle. |
| P2 | A malformed subscription `next` removes the local operation but leaves the old server subscription running on the same socket. | Send `complete` before replacing the operation, or replace the socket, and verify it in a focused test. |

GLM-5.3 max corrected both findings and a separate read-only GLM-5.3 max
review found no remaining P1/P2 in these two paths. The absent-key settlement
requires a complete authoritative HTTP body and valid metadata; every
present-but-invalid value holds the lock. Each locally rejected `next` sends
client `complete` before removal and replacement of its operation. Focused
tests cover the malformed fields and the outgoing `complete` frame.

Independent post-fix editor build succeeded; UE automation reports contain
S10 39/39, S08 46/46 and S09 44/44 successes, zero failures. Node proxy
tests passed 3/3 and the per-seat watchdog probe passed 3/3. The packaged
commit/drop runs on this final source remain to be repeated before GD-037/038
are closed.

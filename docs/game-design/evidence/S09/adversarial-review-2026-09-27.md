# S09 adversarial review — 2026-09-27

Scope: GD-032..036 implementation against `14-sprint-backlog.csv`. GLM-5.3
implemented the fixes; Sol 6 high reviewed the Unreal and backend paths in
successive focused passes. The final automated evidence is
[`duel-20260927-132445`](run/duel-20260927-132445/manifest.json).

| Finding | Resolution and focused proof |
| --- | --- |
| A rejected `leaveGame` appeared to return to the lobby | Preserve room/stage and surface a retryable error; `S08LeaveRoomTests` and the packaged driver's required `LEFT room=` replies. |
| Accepted leave retained old WS state and sequence guard | Tear down subscription/socket and match-local UI/state; `S08LeaveLifecycleTests` proves a new match accepts a lower seq. |
| Delayed `startGame` or gameplay echo could rewrite a newer match | Guard room-scoped HTTP and WS callbacks by game id and match generation before effects; nine `S08StaleGuards` tests cover old, same-id and legitimate answers. |
| F10 room entry could strand an active stream; an earlier Room-stage request could arrive after Started | Disable room entry while Started and recheck stage in all four room-entry callback legs; four `S08RoomEntryGuard` tests cover direct calls, deferred success/failure and fresh subscription after leave. Final targeted Sol review found no remaining P0/P1/P2 in this scenario. |
| Timeout victory omitted the named `GAME_ENDED` cue; a failed publication could suppress later cues | Publish the terminal cue after `COMBAT_RESOLVED`, attempt each post-commit cue independently and keep the committed outcome authoritative. Focused timeout regressions cover publication failure after commit. Per `16-network-contract.md` §4, named events are lossy cues; snapshot/query recovery remains the source of truth. |
| A failed Redis eviction or late list write could show stale game status | Validate a live `game(id)` cache entry against status/version; read `myGames` from Postgres rather than a list cache (including empty FINISHED-filter lists). Focused tests cover failed eviction and late writes. |
| Automated duel gates could pass duplicate or unordered result/leave markers or wrong statistics | Require exactly one ordered result, leave request/reply and exit per seat; gate both players' exact counters and K=32 Elo. The final manifest includes 30 independently rehashed files and a post-leave FINISHED row. |

Verification: `run/automation-tests-unmatched-final-guards-20260927.log`
records 88/88; `run/backend-jest-final-20260927.log` records 1278 passed,
14 skipped; `run/backend-terminal-pg-after-review-20260927.log` records 9/9;
`run/backend-build-final-20260927.log` and
`run/package-final-guards-20260927.log` both succeed. The packaged two-client
driver `run/duel-final-guards-driver-20260927.log` exited successfully at
seq 120 on both seats, with VICTORY/DEFEAT, one accepted leave each, a clean
lobby and exact terminal stats.

Open acceptance: the packaged driver chooses gameplay options automatically,
so a visible two-person mouse/keyboard pass remains open; CHOOSE_ONE has a
synthetic client head but no starter-card live producer; adjacent fighter
labels still overlap in some frames. Effective FPS/GPU frame time and the
GTX 1060/1660/RX 580 target benchmark are unmeasured. The current-PC RTX 4090
sample is total-system utilization only. The narrow publish-after-abort race
noted in the S09 README remains a network-recovery follow-up for S10.

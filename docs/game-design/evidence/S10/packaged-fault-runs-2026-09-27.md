# S10 packaged fault runs — 2026-09-27

The local HTTP proxy forwarded exactly one selected GraphQL mutation and then
discarded its reply. Both runs used the packaged two-client build, the live S09
Postgres/Redis backend, and a 30 FPS command cap per process. Effective FPS and
combined GPU usage were not measured.

| Fault | Evidence | Authoritative result |
| --- | --- | --- |
| First `attack` reply lost after commit | `run/duel-20260927-151859/` | Host logged `outcome unknown`, one bounded refetch and recovery at seq 2. The server journal has exactly one `ATTACK_INITIATED` at seq 2, then defense at 3 and combat resolution at 4. Both clients reached seq 98 and a FINISHED result. |
| First `resolvePendingEffect` reply lost after commit | `run/duel-20260927-152136/` | Host sent `TARGET_FIGHTER`, logged `outcome unknown`, then recovered by refetch at seq 3 with pending count 1→0; it did not resend. The server journal has exactly one `CARD_PLAYED` at seq 3, after the scheme at seq 2. Both clients reached seq 158 and a FINISHED result. |

The proxy confirmed `reply_dropped_after_commit ... forwarded=1` for each
selected field. The second run's 32 manifest-listed files were independently
checked for exact byte length and SHA-256 (zero mismatches); the first run's
30 files were checked likewise. These are positive fault demonstrations for
two mutations, not proof of the negative-path invariants in
`recovery-invariants.md` or of all phases. The packaged binary predates the
subsequent adversarial fixes, so repeat the relevant fault gate on the final
binary before closing GD-037/038.

## Final-source repeat after adversarial corrections

The corrected client was built with `tools/s08/package-client.ps1` (UAT
`BUILD SUCCESSFUL`, exit 0). Its staged Development `Unmatched.exe` SHA-256
is `1a1f61bc4442974e09909da7aec28a159800cdff25118f13e310615b42f69024`.
The local proxy forwarded the first selected mutation to the live S09 backend
and discarded only its HTTP reply, leaving the WebSocket live.

| Fault | Evidence | Independent check |
| --- | --- | --- |
| First `attack` reply dropped after commit | `run/duel-20260927-173400/` | Proxy: `reply_dropped_after_commit`, `forwarded=1`. Host: `ATTACK failed: outcome unknown`, no resend, `RECOVERY complete` at seq 2. Server `GameAction` rows through seq 4 contain exactly one `ATTACK_INITIATED` at seq 2, then `DEFENSE_PLAYED` at 3 and `COMBAT_RESOLVED` at 4. Both clients finished at seq 165, with VICTORY/DEFEAT, clean lobby return and server `FINISHED` row. Manifest: 33/33 lengths and SHA-256 matched. |
| First `resolvePendingEffect` reply dropped after commit | `run/duel-20260927-173637/` | Proxy: `reply_dropped_after_commit`, `forwarded=1`. Host: `BOOST_CHOICE` pending resolve outcome unknown, one authoritative refetch, `RECOVERY complete` at seq 5 and no resend. Server `GameAction` rows through seq 7 contain exactly one `CARD_PLAYED` at seq 5 following combat resolution at 4. Both clients finished at seq 145, with VICTORY/DEFEAT, clean lobby return and server `FINISHED` row. Manifest: 28/28 lengths and SHA-256 matched. |

Both runs passed the runner's server-row, result-marker, no-stale-gameplay,
stats, ELO and seat-convergence gates. They used a per-process `t.MaxFPS 30`
command; effective FPS, GPU frame time and combined GPU utilization were not
measured, so no performance improvement is claimed. The negative paths for
malformed pending metadata and malformed WS `next` are covered by the focused
UE automation tests in `adversarial-review-2026-09-27.md`.

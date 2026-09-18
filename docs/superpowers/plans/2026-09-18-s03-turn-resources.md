# S03 turn and resources implementation plan

**Goal:** Complete GD-010…013 / ACC-003…006 on the integrated S02 baseline.

**Architecture:** Keep the production action executor and immutable GameState. Persist maneuver and end-turn discard identities in metadata. Each accepted API mutation advances sequence exactly once; begin maneuver reserves one action and draws, completion only moves/discards boost. Preserve the current combat continuation.

**Spec:** `docs/game-design/15-rules-and-release-acceptance.md`, ACC-003…006; `evidence/S01/rules-oracle.md`, R-01…R-07. S03 does not claim later UE, card, board or full privacy/recovery gates.

## Constraints and oracle

- Two mandatory actions; ordinary pass/raw move/early endTurn cannot bypass them.
- No implicit draw on turn transfer; explicit END_TURN/GAIN_ACTION still work.
- Every missing draw damages each living friendly fighter by two, then checks hero defeat before continuing. No recycling. Seven is an end-turn hand limit.
- Owner selects exactly the excess instance IDs. Reject foreign, repeated, duplicate or malformed choices without modifying state.
- Begin maneuver draws before any movement/boost decision. A fresh card can boost movement; zero/multiple fighters are valid. Reconnect and retries never redraw.
- Hide unrevealed deck order/top cards from both viewers.
- Preserve unrelated original-checkout edits; integrate locally into `fix/admin-panel`, without remote push.

## Work and verification

1. Draw contract: reproduce full-hand draw/exhaustion failures, remove draw cap, test card/hero effect sources and terminal boundaries. Remove RETURN_TO_HAND cap with regression proof.
2. Executor: add failing real-service S03 harness; remove turn-start draw and free pass; persist maneuver/discard stages. Keep seq/action counters distinct and never rerun turn-end hooks after discard.
3. API/persistence: add required sequence/choice identities, generated GraphQL contract tests, compressed DB/cache roundtrips and both-viewer privacy checks.
4. Consumers: adapt AI and active remote/admin flows to begin, inspect, complete; resume pending choices from snapshots.
5. Evidence: real localhost HTTP/graphql-ws fixtures using production gameplay services and isolated storage adapters, plus engine/persistence tests. Clearly name adapter scope.
6. Review: full backend tests/build and frontend checks. Record baseline auth failures separately (3 failed / 835 passed before edits), assess every new failure.
7. Integration: commit verified S03 changes, preserve tracked/untracked user edits, merge to target, rerun focused acceptance and verify ancestry.

Run backend tests with `npx --no-install jest --runInBand --runTestsByPath <files>` from `backend`; avoid path regex matching the worktree directory itself.

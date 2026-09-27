# S10 stream-gate regression found by packaged run

The second S10 Development package built successfully, but its two-client
fault run did **not** reach the injection. At sequence 1 the host trace showed:

```text
S09AUTO attack (attacker=f-0-hero target-set card-set)
ATTACK sent
ATTACK blocked: live stream is reconnecting - commands wait until the state stream is back
SUBSCRIBED gameStateUpdated since=1
S09AUTO drive mode=3 ... phase=ACTION_MANEUVER
```

The controller correctly gated an early command, while the automated driver
advanced as if it had been accepted. Both clients remained at sequence 1. The
two processes belonging to this run were stopped; `run-duel-demo.ps1` then
verified scoped cleanup of room `cmujmrby500otwil8n87b1esk` as `ABORTED` and
exited with a missing-result failure. No success manifest was published.

This is a blocking packaged regression for GD-037. Fix the driver's acceptance
condition or defer its first command until stream subscription/reconciliation
is ready; retain the real input gate. Repackage and repeat the lost-response
run after the fix.

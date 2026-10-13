# 2026-10-13 — Tripo has no spending limit

**Decision (user, 2026-10-13):** «На триппо нет лимита».

ВР-04 capped Tripo at 3000 studio-credits until 2026-10-28
(`docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md`). The user lifted the cap while starting
stage 1b (Tripo drafts) for the whole DB roster («начинай делать все остальные параллельно согласно скиллу»).

Effect:
- `docs/game-design/visual/credits-ledger.json` `limits.tripo.credits` 3000 → 1000000 (the ledger file is the source of
  `ledger.py` limits); the real bound stays the fresh Studio balance, which `ledger.py check --balance` still enforces.
- Every Tripo operation is still written with `ledger.py add` right after it; no purchases are made by the agent.
- providerTerms row for Tripo Studio H3.1 recorded 2026-10-13 (ВР-05).
- Stage-0 cards AN-37…AN-121 added to `docs/game-design/visual/06-tasks/anim.csv` for the 85 figures whose design front
  is accepted (Sol pass or the user's decision `2026-10-13-licensed-concepts-user-accepted.md`).

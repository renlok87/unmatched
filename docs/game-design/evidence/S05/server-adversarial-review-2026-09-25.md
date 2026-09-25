# S05 server/card adversarial review — 2026-09-25

Base: `1ca2231`. Scope: GD-017, GD-019, GD-020. GLM implemented; a separate
GLM reviewer inspected production wiring and tests after each correction.
The orchestrator independently checked the rulebook and frontend type baseline.

## Findings and corrections

1. Hiss and Slither / Clutching Claws originally discarded a random card even
   though the printed text gives the opponent the choice. They now create a
   persisted, owner-bound `DISCARD_CARDS` pending effect. Tests cover the
   opponent's exact choice, empty hand, foreign/stale/replayed answers, combat
   continuation, AI, and privacy.
2. Six Medusa card tests originally checked parser output without executing the
   effects. They now run through the combat/effect executor, including Feint,
   Dash, Regroup, Snipe, Hiss and Clutching Claws.
3. The initial and first correction reviews misapplied Arthur's ability rule
   to card effects: Second Shot and Noble Sacrifice were charging an optional
   boost before the defender chose a card. The [official Battle of Legends
   Vol. 1 rulebook](https://restorationgames.com/wp-content/uploads/2019/07/UM-Battle_of_Legends_vol1_Rules-two-page.pdf)
   (pp. 12–13) places `DURING COMBAT` effects after both cards are revealed.
   Card boost is now an optional `BOOST_CHOICE` at that point; Arthur's separate
   ability boost stays with attack declaration. Feint cancels the card effect
   before its cost is paid. Tests cover ordering, decline, dual boost, invalid
   answers, save/restore, AI, and turn continuation.
4. The first privacy fix hid played card identities for the whole
   `COMBAT_RESOLVE` phase, including after reveal, when the attacker must decide
   whether to boost. The final fix distinguishes pre-reveal states from paused
   post-reveal combat. Query, mutation, subscription, and GameView expose the
   played cards after reveal while keeping hands and unchosen cards private.
   Tests cover both players, committed cards, boost choice, and serialization.
5. Invented ability names were removed from player-facing text; provisional
   internal labels and evidence are marked as such. The parser now distinguishes
   plain random discard text from owner-choice discard.

## Verification and limits

The final independent review ran S05 focused tests (58/58), neighboring
executor/parser/AI/ability tests (326/326), full backend Jest (1048 passed,
three pre-existing `auth.service.spec.ts` failures), backend build, admin
TypeScript build, and frontend Vitest (13/13). The orchestrator repeated a
read-only frontend TypeScript comparison: 255 diagnostics on base and current,
none added; see [comparison](frontend-baseline-comparison.md). Browser UI was
not exercised in this track.

GD-017, GD-019, GD-020 pass their S05 server gates. The registry has 27
records/60 copies; deferred Arthur effects and Skirmish remain explicitly
unsupported or partial for S06, and Excalibur's blank effect is recorded.
This does not close full ACC-013/015/017 or the UE/art gate GD-058.

Follow-ups: a future defense-side card boost needs separate attack/defense
boost totals; current captured decks have no such effect. S07 must address
the pre-existing broader privacy channels, including defense value visibility
and internal Redis event payloads. Target-PC performance and author acceptance
for GD-058 remain open by explicit user decision.

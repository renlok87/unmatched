# S09 screenshot review — 2026-09-27

This is an agent inspection of saved 1280×720 captures, not a human playtest.
The separate [Unreal MCP check](mcp-pointer-review-2026-09-27.md) proves the
Slate pointer path in PIE. I reviewed all six HUD/maneuver/discard shots in
`run/run-20260926-035408/` and both result/lobby pairs in
`run/duel-20260927-093227/`. I also inspected the newer packaged
`run/duel-20260927-113553/` result and discard captures after the
fighter-label adjustment, plus the result/lobby pairs from the current
`run/duel-20260927-132445/` (final callback guards, 88 headless tests).

- The own hand has individually labelled card buttons; the opponent line shows
  counts only. The maneuver and mandatory-discard panels have distinct headings
  and magenta/cyan accents. Both result screens identify victory/defeat, and
  both lobby returns show no board in the gameplay region.
- Fighter labels are a readability problem. On the current five-column duel
  board, adjacent names and HP overlap (for example, Arthur/Medusa/Merlin in
  `duel-20260927-093227/host/s09-discard-open.png`). On the earlier large board
  in `run-20260926-035408`, fighter names are too small to read at 1280×720.
  Color and prototype shapes alone do not reliably identify each fighter.
- In run 113553, names and HP occupy separate lines and individual labels are
  easier to read. Adjacent fighters still overlap at some placements, notably
  Harpies/Merlin in `joiner/s09-discard-open.png`; this remains a grey-prototype
  readability issue for the later art/UI pass.
- In run 132445, the host's VICTORY and joiner's DEFEAT are both clear, and
  the lobby captures show the board and fighters removed. The host result shot
  still has Harpy 1 and Medusa labels touching; this is a visible prototype
  legibility issue to recheck at the S11 camera/scale gate.
- The result is the GD-036 minimum: outcome, turn count, and return action are
  visible. It does not yet display the duration, both players' final HP, or
  updated player stats described by UI-SCR-GAMEOVER in `02-ux-ui-spec.md` §2.9.

The saved captures support the functional marker gates, and Unreal MCP exercised
the discard buttons with Slate pointer events. They do not close the human visual
pass or physical mouse check in a packaged window. Before calling the grey build
playable without assistance, run a visible two-seat pass and verify fighter
identification, card-button hit areas, and result readability at the target
display resolution.

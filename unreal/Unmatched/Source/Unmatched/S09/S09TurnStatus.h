// DE-022 (W-13; docs/game-design/02-ux-ui-spec.md, "Строка «что делать сейчас»" - SD-31; move-selection 03 §7, §9):
// one line "what to do now" in every state of a turn, world-free and automation-tested
// (Unmatched.S09.MoveSel.OpponentStatus). The game mode fills FS09TurnStatusInput from its command UI and the applied
// snapshot; S09TurnStatus::Line picks the key:
//   - my turn, nothing open: choose an action (maneuver, attack, scheme) - or end the turn with no actions left;
//   - the maneuver draft: choose a fighter, then a space; the attack draft: attacker -> target -> card -> attack;
//     the scheme picker: a scheme card;
//   - combat: I defend -> a defense card or No defense; the resolve window -> resolve (or wait for a choice);
//     I attack and the defender has not answered -> waiting for the defender;
//   - my deferred choice -> its own prompt (ms.choice.* / ms.pending.*, given by the caller); the opponent's -> wait;
//   - the hand limit -> "Discard N";
//   - the opponent's turn -> "<name> - <verb>" by ms.opp.phase.* (S09OpponentView::OpponentVerb);
//   - a command in flight / a reconnect -> why.syncing.
// Unlike DE the line never empties while a figure moves or a combat plays: the animation does not block input
// (CUE-007 blocks_input: no). Keys are ms.* / why.* of S08WhyText; DE's strings are not copied.
#pragma once

#include "CoreMinimal.h"
#include "S09ManeuverUi.h"
#include "S09OpponentView.h"

struct UNMATCHED_API FS09TurnStatusInput {
  bool bGameOver = false;
  /** A command in flight, the stream reconnecting or the state being recovered (why.syncing). */
  bool bSyncing = false;
  bool bViewerTurn = false;
  int32 ActionsRemaining = -1;  // -1 unknown
  ES09CommandMode Mode = ES09CommandMode::None;
  // ManeuverDraft
  FString SelectedFighterName;  // '' = no fighter picked yet (MS-S-06)
  // AttackDraft
  bool bAbilityPrompt = false;  // the hero ability BOOST prompt (DE-020)
  FString AttackerName;         // '' = none picked
  FString TargetName;
  bool bAttackCard = false;
  // DiscardDraft (the hand limit)
  int32 DiscardNeed = 0;
  int32 DiscardChosen = 0;
  // PendingChoice: my open head - its prompt (the step / MOVE / PLACE prompt of the panel)
  FS09Reason PendingPrompt;
  /** The head of pendingEffects is the opponent's. */
  bool bOpponentChoice = false;
  /** Combat open and I attack (the defense window is theirs). */
  bool bCombatAttacking = false;
  // the opponent
  ES09OpponentVerb OpponentVerb = ES09OpponentVerb::None;
  FString OpponentName;
};

namespace S09TurnStatus {
/** The line of the state (an unset reason = no line: game over, nobody acting). */
UNMATCHED_API FS09Reason Line(const FS09TurnStatusInput& In);
/** The rendered EN line ('' for none). */
UNMATCHED_API FString Text(const FS09TurnStatusInput& In);
}  // namespace S09TurnStatus

// HB-50 TURN-STRIP (docs/game-design/visual/TURN-STRIP.md; user 2026-10-16: «спроектируй полоску со стадиями хода в
// виде иконок с состоянием. Это позволит игроку быстрее адаптироваться»): the stages of the running turn as icons with
// a state each - action 1, action 2, discard to 7, end of turn - and the sub-steps of the action in progress (maneuver:
// draw -> move; attack: declare -> defense -> reveal -> result; scheme: play -> effect). World-free: the game mode
// fills FS09TurnStripInput from the applied snapshot, the tracker and the command UI; S09TurnStrip::Build gives the
// model UUmHudTurnStrip draws. The strip says WHERE the turn is; the status line (S09TurnStatus) says what to do.
#pragma once

#include "CoreMinimal.h"

enum class ES09StripState : uint8 { Done, Now, Next, Skip };

/** The step of the action in progress (None = between actions). */
enum class ES09StripStep : uint8 {
  None,
  ManeuverMove,   // the card is drawn (pendingManeuver), the fighters move
  AttackDeclare,  // the attack draft: attacker, target, card
  AttackDefense,  // COMBAT: the defender chooses
  AttackReveal,   // the cards flip (COMBAT_RESOLVE before the slam of the staging)
  AttackResult,   // the outcome, the damage, the during / after combat effects
  SchemePlay,     // the scheme picker
  SchemeEffect,   // the scheme is played, its effect / choice runs
};

struct UNMATCHED_API FS09TurnStripInput {
  bool bShow = false;
  bool bOwnTurn = false;
  int32 Slots = 2;
  /** The types of the actions the active side has spent, in order: "maneuver" | "attack" | "scheme" (unknown = None). */
  TArray<FName> Spent;
  /** The action in progress and its step; bStepSpent = the server already counted it in Spent (an attack in combat, a
   *  maneuver after beginManeuver), else it is a local draft that takes the next free slot. */
  FName Current;
  ES09StripStep Step = ES09StripStep::None;
  bool bStepSpent = false;
  /** A deferred choice is open at the current step (mine or the opponent's). */
  bool bChoice = false;
  /** The current step is mine although the turn is not (I defend in the opponent's attack). */
  bool bMyStep = false;
  /** TURN_END with pendingHandDiscard (the discard to the hand limit is the stage now). */
  bool bDiscardNow = false;
  /** The active side holds more than 7 cards now - the discard stage will come (else it is not needed). */
  bool bOverLimit = false;
};

struct UNMATCHED_API FS09StripNode {
  FName Icon;
  ES09StripState State = ES09StripState::Next;
  /** hud.turnstrip.* - the tooltip rule of the node. */
  FName Tip;
  bool bChoice = false;
  bool bMine = false;
  bool operator==(const FS09StripNode& O) const {
    return Icon == O.Icon && State == O.State && Tip == O.Tip && bChoice == O.bChoice && bMine == O.bMine;
  }
};

struct UNMATCHED_API FS09TurnStripModel {
  bool bShow = false;
  bool bOwnTurn = false;
  /** Action 1, action 2, discard, end of turn. */
  TArray<FS09StripNode> Nodes;
  /** The node the sub-steps belong to (-1 = none) and the sub-steps. */
  int32 SubOf = -1;
  TArray<FS09StripNode> Subs;
  /** The icon of the step now (the compact strip shows it as the badge of node SubOf). */
  FName StepIcon;
  bool operator==(const FS09TurnStripModel& O) const {
    return bShow == O.bShow && bOwnTurn == O.bOwnTurn && Nodes == O.Nodes && SubOf == O.SubOf && Subs == O.Subs &&
           StepIcon == O.StepIcon;
  }
  /** 'side=own|opp nodes=now:action-empty,next:... sub=1:done:action-attack,now:action-defense' - the trace. */
  FString Key() const;
};

namespace S09TurnStrip {
UNMATCHED_API const TCHAR* StateName(ES09StripState State);
/** The icon of a spent / running action type ("maneuver" -> action-maneuver ...; unknown -> resource-action-full). */
UNMATCHED_API FName ActionIcon(FName Type);
UNMATCHED_API FS09TurnStripModel Build(const FS09TurnStripInput& In);
}  // namespace S09TurnStrip

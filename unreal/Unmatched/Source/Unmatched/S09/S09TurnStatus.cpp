#include "S09TurnStatus.h"

#include "../S08/S08WhyText.h"

namespace S09TurnStatus {

FS09Reason Line(const FS09TurnStatusInput& In) {
  if (In.bGameOver) return FS09Reason();
  if (In.bSyncing) return FS09Reason::Make(TEXT("why.syncing"));

  // my own choices first: the server waits on them whoever's turn it is
  if (In.Mode == ES09CommandMode::PendingChoice) {
    return In.PendingPrompt.IsSet() ? In.PendingPrompt : FS09Reason::Make(TEXT("ms.choice.object"));
  }
  if (In.Mode == ES09CommandMode::DiscardDraft) {
    const int32 Left = FMath::Max(0, In.DiscardNeed - In.DiscardChosen);
    return Left > 0 ? FS09Reason::Make(TEXT("ms.status.discard")).Arg(TEXT("n"), Left)
                    : FS09Reason::Make(TEXT("ms.status.confirm"));
  }
  if (In.Mode == ES09CommandMode::CombatDefense) return FS09Reason::Make(TEXT("ms.status.defend"));
  if (In.Mode == ES09CommandMode::CombatResolve) {
    return In.bOpponentChoice ? FS09Reason::Make(TEXT("why.wait.opponent.choice"))
                              : FS09Reason::Make(TEXT("ms.status.resolve"));
  }
  if (In.bOpponentChoice) return FS09Reason::Make(TEXT("why.wait.opponent.choice"));
  if (In.bCombatAttacking) return FS09Reason::Make(TEXT("why.wait.defender"));

  switch (In.Mode) {
    case ES09CommandMode::ManeuverDraft:
      return In.SelectedFighterName.IsEmpty()
                 ? FS09Reason::Make(TEXT("ms.status.fighter"))
                 : FS09Reason::Make(TEXT("ms.status.space")).Arg(TEXT("fighterName"), In.SelectedFighterName);
    case ES09CommandMode::AttackDraft:
      if (In.bAbilityPrompt) {
        return FS09Reason::Make(TEXT("ms.ability.boost")).Arg(TEXT("fighterName"), In.AttackerName);
      }
      if (In.AttackerName.IsEmpty()) return FS09Reason::Make(TEXT("ms.status.attacker"));
      if (In.TargetName.IsEmpty()) {
        return FS09Reason::Make(TEXT("ms.status.target")).Arg(TEXT("fighterName"), In.AttackerName);
      }
      return In.bAttackCard ? FS09Reason::Make(TEXT("ms.status.attack.go")).Arg(TEXT("target"), In.TargetName)
                            : FS09Reason::Make(TEXT("ms.status.attack.card")).Arg(TEXT("target"), In.TargetName);
    case ES09CommandMode::SchemeChoice:
      return FS09Reason::Make(TEXT("ms.status.scheme"));
    default:
      break;
  }

  if (In.bViewerTurn) {
    return In.ActionsRemaining == 0 ? FS09Reason::Make(TEXT("ms.status.end"))
                                    : FS09Reason::Make(TEXT("ms.status.action"));
  }
  const FName VerbKey = S09OpponentView::VerbKey(In.OpponentVerb);
  if (VerbKey.IsNone()) return FS09Reason();
  return FS09Reason::Make(TEXT("ms.status.opp"))
      .Arg(TEXT("player"), In.OpponentName.IsEmpty() ? FString(TEXT("Opponent")) : In.OpponentName)
      .Arg(TEXT("verb"), S08WhyText::En(VerbKey));
}

FString Text(const FS09TurnStatusInput& In) { return Line(In).Text(); }

}  // namespace S09TurnStatus

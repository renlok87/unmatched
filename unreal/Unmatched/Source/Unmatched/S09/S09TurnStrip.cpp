// HB-50 TURN-STRIP: the model - see S09TurnStrip.h.
#include "S09TurnStrip.h"

namespace {
const FName ActionEmpty(TEXT("resource-action-empty"));
const FName ActionFull(TEXT("resource-action-full"));
const FName Discard(TEXT("card-drop"));
const FName EndTurn(TEXT("action-end-turn"));

FS09StripNode MakeNode(FName Icon, ES09StripState State, const TCHAR* Tip) {
  FS09StripNode N;
  N.Icon = Icon;
  N.State = State;
  N.Tip = FName(Tip);
  return N;
}

const TCHAR* ActionTip(FName Type) {
  if (Type == TEXT("maneuver")) return TEXT("hud.turnstrip.maneuver");
  if (Type == TEXT("attack")) return TEXT("hud.turnstrip.attack");
  if (Type == TEXT("scheme")) return TEXT("hud.turnstrip.scheme");
  return TEXT("hud.turnstrip.action");
}

/** The sub-steps of an action type and the index of Step among them (-1 = Step is not of this type). */
void SubSteps(FName Type, ES09StripStep Step, TArray<FS09StripNode>& Out, int32& OutAt) {
  struct FDef {
    const TCHAR* Icon;
    const TCHAR* Tip;
    ES09StripStep Step;
  };
  TArray<FDef> Defs;
  if (Type == TEXT("maneuver")) {
    Defs = {{TEXT("resource-card"), TEXT("hud.turnstrip.step.draw"), ES09StripStep::None},
            {TEXT("ui-step"), TEXT("hud.turnstrip.step.move"), ES09StripStep::ManeuverMove}};
  } else if (Type == TEXT("attack")) {
    Defs = {{TEXT("action-attack"), TEXT("hud.turnstrip.step.declare"), ES09StripStep::AttackDeclare},
            {TEXT("action-defense"), TEXT("hud.turnstrip.step.defense"), ES09StripStep::AttackDefense},
            {TEXT("badge-conflict"), TEXT("hud.turnstrip.step.reveal"), ES09StripStep::AttackReveal},
            {TEXT("ui-check"), TEXT("hud.turnstrip.step.result"), ES09StripStep::AttackResult}};
  } else if (Type == TEXT("scheme")) {
    Defs = {{TEXT("action-scheme"), TEXT("hud.turnstrip.step.play"), ES09StripStep::SchemePlay},
            {TEXT("ui-check"), TEXT("hud.turnstrip.step.effect"), ES09StripStep::SchemeEffect}};
  }
  OutAt = -1;
  for (int32 I = 0; I < Defs.Num(); ++I) {
    if (Defs[I].Step == Step && Step != ES09StripStep::None) OutAt = I;
  }
  for (int32 I = 0; I < Defs.Num(); ++I) {
    const ES09StripState State = OutAt < 0 ? ES09StripState::Next
                                 : I < OutAt ? ES09StripState::Done
                                 : I == OutAt ? ES09StripState::Now
                                              : ES09StripState::Next;
    Out.Add(MakeNode(FName(Defs[I].Icon), State, Defs[I].Tip));
  }
}

FString NodeKey(const FS09StripNode& N) {
  FString S = FString::Printf(TEXT("%s:%s"), S09TurnStrip::StateName(N.State), *N.Icon.ToString());
  if (N.bChoice) S += TEXT("+choice");
  if (N.bMine) S += TEXT("+mine");
  return S;
}
}  // namespace

namespace S09TurnStrip {

const TCHAR* StateName(ES09StripState State) {
  switch (State) {
    case ES09StripState::Done: return TEXT("done");
    case ES09StripState::Now: return TEXT("now");
    case ES09StripState::Next: return TEXT("next");
    default: return TEXT("skip");
  }
}

FName ActionIcon(FName Type) {
  if (Type == TEXT("maneuver")) return FName(TEXT("action-maneuver"));
  if (Type == TEXT("attack")) return FName(TEXT("action-attack"));
  if (Type == TEXT("scheme")) return FName(TEXT("action-scheme"));
  return ActionFull;
}

FS09TurnStripModel Build(const FS09TurnStripInput& In) {
  FS09TurnStripModel M;
  M.bShow = In.bShow;
  M.bOwnTurn = In.bOwnTurn;
  if (!In.bShow) return M;
  const int32 Slots = FMath::Max(1, In.Slots);
  const bool bRunning = !In.Current.IsNone();
  // the finished actions: the spent ones minus the running one when the server already counted it
  const int32 Finished = FMath::Clamp(In.Spent.Num() - (bRunning && In.bStepSpent ? 1 : 0), 0, Slots);
  const bool bActionsLeft = Finished < Slots;
  for (int32 I = 0; I < Slots; ++I) {
    if (I < Finished) {
      const FName Type = In.Spent.IsValidIndex(I) ? In.Spent[I] : NAME_None;
      M.Nodes.Add(MakeNode(ActionIcon(Type), ES09StripState::Done, ActionTip(Type)));
    } else if (I == Finished && bRunning) {
      M.Nodes.Add(MakeNode(ActionIcon(In.Current), ES09StripState::Now, ActionTip(In.Current)));
      M.SubOf = I;
    } else if (I == Finished && !In.bDiscardNow) {
      M.Nodes.Add(MakeNode(ActionEmpty, ES09StripState::Now, TEXT("hud.turnstrip.action")));
    } else {
      M.Nodes.Add(MakeNode(ActionEmpty, ES09StripState::Next, TEXT("hud.turnstrip.action")));
    }
  }
  const bool bTurnEnding = !bActionsLeft && !bRunning;
  M.Nodes.Add(MakeNode(Discard,
                       In.bDiscardNow ? ES09StripState::Now
                       : In.bOverLimit ? ES09StripState::Next
                                       : ES09StripState::Skip,
                       TEXT("hud.turnstrip.discard")));
  M.Nodes.Add(MakeNode(EndTurn, bTurnEnding && !In.bDiscardNow ? ES09StripState::Now : ES09StripState::Next,
                       TEXT("hud.turnstrip.end")));
  if (M.SubOf >= 0) {
    int32 At = -1;
    SubSteps(In.Current, In.Step, M.Subs, At);
    if (At >= 0) {
      M.Subs[At].bChoice = In.bChoice;
      M.Subs[At].bMine = In.bMyStep;
      M.StepIcon = M.Subs[At].Icon;
    }
    M.Nodes[M.SubOf].bChoice = In.bChoice;
    M.Nodes[M.SubOf].bMine = In.bMyStep;
  } else if (In.bChoice) {
    for (FS09StripNode& N : M.Nodes) {
      if (N.State == ES09StripState::Now) N.bChoice = true;
    }
  }
  return M;
}

}  // namespace S09TurnStrip

FString FS09TurnStripModel::Key() const {
  if (!bShow) return TEXT("hidden");
  TArray<FString> N;
  for (const FS09StripNode& X : Nodes) N.Add(NodeKey(X));
  TArray<FString> S;
  for (const FS09StripNode& X : Subs) S.Add(NodeKey(X));
  return FString::Printf(TEXT("side=%s nodes=%s sub=%d:%s"), bOwnTurn ? TEXT("own") : TEXT("opp"),
                         *FString::Join(N, TEXT(",")), SubOf, S.Num() ? *FString::Join(S, TEXT(",")) : TEXT("-"));
}

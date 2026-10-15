// HB-50 TURN-STRIP automation: Unmatched.S09.TurnStrip.Model - the stages of one turn as the model gives them (start,
// maneuver draw -> move, attack declare -> defense -> reveal -> result, scheme, a choice, the discard over the limit,
// the end of the turn, the opponent's attack with my defense).
#include "Misc/AutomationTest.h"

#include "S09TurnStrip.h"

namespace {
FString StatesOf(const FS09TurnStripModel& M) {
  TArray<FString> Out;
  for (const FS09StripNode& N : M.Nodes) Out.Add(FString::Printf(TEXT("%s:%s"), S09TurnStrip::StateName(N.State), *N.Icon.ToString()));
  return FString::Join(Out, TEXT(" "));
}
FString SubsOf(const FS09TurnStripModel& M) {
  TArray<FString> Out;
  for (const FS09StripNode& N : M.Subs) Out.Add(FString::Printf(TEXT("%s:%s"), S09TurnStrip::StateName(N.State), *N.Icon.ToString()));
  return FString::Join(Out, TEXT(" "));
}
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09TurnStripModelTest, "Unmatched.S09.TurnStrip.Model",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09TurnStripModelTest::RunTest(const FString&) {
  FS09TurnStripInput In;
  TestFalse(TEXT("hidden without a live match"), S09TurnStrip::Build(In).bShow);
  TestEqual(TEXT("hidden key"), S09TurnStrip::Build(In).Key(), FString(TEXT("hidden")));

  In.bShow = true;
  In.bOwnTurn = true;
  // A: the start of my turn
  FS09TurnStripModel M = S09TurnStrip::Build(In);
  TestEqual(TEXT("A: action 1 now, action 2 next, discard not needed, end next"), StatesOf(M),
            FString(TEXT("now:resource-action-empty next:resource-action-empty skip:card-drop next:action-end-turn")));
  TestEqual(TEXT("A: no sub-steps"), M.SubOf, -1);
  TestEqual(TEXT("A: the tip of the free action"), M.Nodes[0].Tip, FName(TEXT("hud.turnstrip.action")));

  // E: maneuver - the card drawn (beginManeuver spent the action), the fighters move
  In.Spent = {FName(TEXT("maneuver"))};
  In.Current = FName(TEXT("maneuver"));
  In.Step = ES09StripStep::ManeuverMove;
  In.bStepSpent = true;
  M = S09TurnStrip::Build(In);
  TestEqual(TEXT("E: the maneuver now in slot 1"), StatesOf(M),
            FString(TEXT("now:action-maneuver next:resource-action-empty skip:card-drop next:action-end-turn")));
  TestEqual(TEXT("E: draw done, move now"), SubsOf(M), FString(TEXT("done:resource-card now:ui-step")));
  TestEqual(TEXT("E: sub-steps of node 0"), M.SubOf, 0);
  TestEqual(TEXT("E: step icon"), M.StepIcon, FName(TEXT("ui-step")));

  // the attack draft as the second action: a local draft takes the next slot
  In.Current = FName(TEXT("attack"));
  In.Step = ES09StripStep::AttackDeclare;
  In.bStepSpent = false;
  M = S09TurnStrip::Build(In);
  TestEqual(TEXT("draft: maneuver done, attack now"), StatesOf(M),
            FString(TEXT("done:action-maneuver now:action-attack skip:card-drop next:action-end-turn")));
  TestEqual(TEXT("draft: declare now"), SubsOf(M),
            FString(TEXT("now:action-attack next:action-defense next:badge-conflict next:ui-check")));

  // B: the attack sent, the defender chooses
  In.Spent = {FName(TEXT("maneuver")), FName(TEXT("attack"))};
  In.Step = ES09StripStep::AttackDefense;
  In.bStepSpent = true;
  M = S09TurnStrip::Build(In);
  TestEqual(TEXT("B: attack still now"), StatesOf(M),
            FString(TEXT("done:action-maneuver now:action-attack skip:card-drop next:action-end-turn")));
  TestEqual(TEXT("B: declare done, defense now"), SubsOf(M),
            FString(TEXT("done:action-attack now:action-defense next:badge-conflict next:ui-check")));
  In.Step = ES09StripStep::AttackResult;
  In.bChoice = true;
  M = S09TurnStrip::Build(In);
  TestEqual(TEXT("result with a choice"), SubsOf(M),
            FString(TEXT("done:action-attack done:action-defense done:badge-conflict now:ui-check")));
  TestTrue(TEXT("the choice marks the step and its node"), M.Subs[3].bChoice && M.Nodes[1].bChoice);
  In.bChoice = false;

  // both actions done: the end of the turn now; over the limit: the discard comes first
  In.Current = NAME_None;
  In.Step = ES09StripStep::None;
  M = S09TurnStrip::Build(In);
  TestEqual(TEXT("end now"), StatesOf(M),
            FString(TEXT("done:action-maneuver done:action-attack skip:card-drop now:action-end-turn")));
  In.bOverLimit = true;
  In.bDiscardNow = true;
  M = S09TurnStrip::Build(In);
  TestEqual(TEXT("D: discard now"), StatesOf(M),
            FString(TEXT("done:action-maneuver done:action-attack now:card-drop next:action-end-turn")));
  In.bDiscardNow = false;
  In.Spent = {FName(TEXT("scheme"))};
  M = S09TurnStrip::Build(In);
  TestEqual(TEXT("over the limit mid-turn: the discard will come"), StatesOf(M),
            FString(TEXT("done:action-scheme now:resource-action-empty next:card-drop next:action-end-turn")));
  In.bOverLimit = false;

  // the scheme played, its effect runs with a choice
  In.Spent = {FName(TEXT("scheme"))};
  In.Current = FName(TEXT("scheme"));
  In.Step = ES09StripStep::SchemeEffect;
  In.bStepSpent = true;
  In.bChoice = true;
  M = S09TurnStrip::Build(In);
  TestEqual(TEXT("scheme effect"), SubsOf(M), FString(TEXT("done:action-scheme now:ui-check")));
  TestTrue(TEXT("scheme effect choice"), M.Subs[1].bChoice);
  In.bChoice = false;

  // C: the opponent's turn, their scheme done, their attack - my defense
  In.bOwnTurn = false;
  In.Spent = {FName(TEXT("scheme")), FName(TEXT("attack"))};
  In.Current = FName(TEXT("attack"));
  In.Step = ES09StripStep::AttackDefense;
  In.bStepSpent = true;
  In.bMyStep = true;
  M = S09TurnStrip::Build(In);
  TestFalse(TEXT("C: the opponent's side"), M.bOwnTurn);
  TestEqual(TEXT("C: nodes"), StatesOf(M),
            FString(TEXT("done:action-scheme now:action-attack skip:card-drop next:action-end-turn")));
  TestTrue(TEXT("C: my defense is mine"), M.Subs[1].bMine && M.Subs[1].State == ES09StripState::Now);
  TestEqual(TEXT("C: key"), M.Key(),
            FString(TEXT("side=opp nodes=done:action-scheme,now:action-attack+mine,skip:card-drop,next:action-end-turn "
                         "sub=1:done:action-attack,now:action-defense+mine,next:badge-conflict,next:ui-check")));
  return true;
}

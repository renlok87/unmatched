// GD-036 automation tests: the terminal result model and its input gates.
// Base data is the REAL viewer-projected fixture gd035-move-open-host-view
// (players/fighters/hands/metadata of a live duel); the terminal variant
// swaps only phase -> GAME_OVER and metadata.winnerId, exactly the fields the
// server writes at applyTerminalState. Covers: winner/loser/draw parsing for
// BOTH seats, fresh-snapshot (reconnect/late-arrival) derivation, strictly
// phase-driven triggering (an aborted room never renders as a victory),
// idempotent rebuild (same-seq merge cannot double-present), gameplay-input
// death on the terminal snapshot (model + controller gates + seq-guard
// dedupe), and the scheme banner legality mirror that keeps the auto driver
// from re-sending a scheme whose banner fighter fell (10:41 loop).
// DE-019 (W-16): death by stages from the contact frame and the result gate (S09DeathStage.h) -
// Unmatched.S09.DeathStage.Timeline / .ResultGate.
// DE-029 (W-17): the result screen summary and its view (S09ResultScreen.h) - Unmatched.S09.ResultScreen.Summary /
// .Duration / .View.
#if WITH_AUTOMATION_TESTS

#include "S09CombatStage.h"
#include "S09DeathStage.h"
#include "S09HudModel.h"
#include "S09ResultScreen.h"
#include "S09ManeuverUi.h"
#include "../S08/S08BoardModel.h"
#include "../S08/S08Contracts.h"
#include "../S08/S08CueDispatcher.h"
#include "../S08/S08HeroesV2.h"
#include "../S08/S08FlowController.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

namespace {
bool LoadResultBaseSnapshot(FS08Snapshot& OutSnapshot) {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S09Fixtures="), Dir) || Dir.IsEmpty()) {
    Dir = FPaths::Combine(FPaths::ProjectDir(),
                          TEXT("../../docs/game-design/evidence/S09/fixtures"));
  }
  FString Text;
  if (!FFileHelper::LoadFileToString(
          Text, *FPaths::Combine(Dir, TEXT("gd035-move-open-host-view.json")))) {
    return false;
  }
  TSharedPtr<FJsonValue> Value;
  FString Problem;
  if (!FS08Contracts::TryParseJsonValue(Text, Value, Problem)) return false;
  const TSharedPtr<FJsonObject>* Root = nullptr;
  if (!Value->TryGetObject(Root) || !Root->IsValid()) return false;
  FString Body;
  const TSharedPtr<FJsonObject>* RawObject = nullptr;
  if ((*Root)->TryGetStringField(TEXT("raw"), Body)) {
    if (!FS08Contracts::TryParseJsonValue(Body, Value, Problem)) return false;
  } else if ((*Root)->TryGetObjectField(TEXT("raw"), RawObject) && RawObject->IsValid()) {
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Body);
    FJsonSerializer::Serialize(RawObject->ToSharedRef(), Writer);
  }
  FS08GraphQLError Error;
  return FS08Contracts::ParseGameStateQuery(Body, OutSnapshot, Problem, Error);
}

/** Terminal variant of a live snapshot: swaps ONLY phase (+ winnerId), the
 *  exact fields applyTerminalState writes server-side. WinnerId empty string
 *  removes the field (draw / no winner decided). */
FS08Snapshot WithTerminalState(const FS08Snapshot& Snapshot, const FString& WinnerId) {
  FS08Snapshot Out = Snapshot;
  Out.Phase = TEXT("GAME_OVER");
  if (Out.Metadata.IsValid() && Out.Metadata->AsObject().IsValid()) {
    const TSharedRef<FJsonObject> Meta =
        MakeShared<FJsonObject>(*(Out.Metadata->AsObject()));
    if (WinnerId.IsEmpty()) {
      Meta->RemoveField(TEXT("winnerId"));
    } else {
      Meta->SetStringField(TEXT("winnerId"), WinnerId);
    }
    Out.Metadata = MakeShared<FJsonValueObject>(Meta);
  }
  return Out;
}

/** Server draw shape: applyTerminalState with alive == 0 writes GAME_OVER
 *  with NO winnerId and every player isAlive=false (mutual destruction). */
FS08Snapshot WithAllPlayersDead(const FS08Snapshot& Snapshot) {
  FS08Snapshot Out = Snapshot;
  const TArray<TSharedPtr<FJsonValue>>* Players = nullptr;
  if (Out.Players.IsValid() && Out.Players->TryGetArray(Players) && Players) {
    TArray<TSharedPtr<FJsonValue>> Dead;
    for (const TSharedPtr<FJsonValue>& Value : *Players) {
      const TSharedPtr<FJsonObject>* Player = nullptr;
      if (!Value.IsValid() || !Value->TryGetObject(Player) || !Player->IsValid()) continue;
      const TSharedRef<FJsonObject> Copy = MakeShared<FJsonObject>(**Player);
      Copy->SetBoolField(TEXT("isAlive"), false);
      Dead.Add(MakeShared<FJsonValueObject>(Copy));
    }
    Out.Players = MakeShared<FJsonValueArray>(Dead);
  }
  return Out;
}

bool FixtureViewerIds(const FS08Snapshot& Snapshot, FString& OutFirst, FString& OutSecond) {
  if (!Snapshot.Players.IsValid()) return false;
  const TArray<TSharedPtr<FJsonValue>>* Players = nullptr;
  if (!Snapshot.Players->TryGetArray(Players) || !Players || Players->Num() < 2) return false;
  const TSharedPtr<FJsonObject>* P0 = nullptr;
  const TSharedPtr<FJsonObject>* P1 = nullptr;
  if (!(*Players)[0]->TryGetObject(P0) || !(*Players)[1]->TryGetObject(P1)) return false;
  OutFirst = (*P0)->GetStringField(TEXT("userId"));
  OutSecond = (*P1)->GetStringField(TEXT("userId"));
  return !OutFirst.IsEmpty() && !OutSecond.IsEmpty();
}

/** Minimal graphql-transport-ws 'next' frame for the harness-registered
 *  operation (s08-1). Carries ONLY the baseline scalars: the delivered frame
 *  proves the operation live (Sol6 review P1(3) bGameStateOpLive) while the
 *  equal seq collapses in the seq guard as a merge. Projections are
 *  deliberately absent - an event that shipped dummy players/handZones would
 *  overwrite the applied fixture state and fail critical-field validation. */
FString BarrierNextFrame(const FS08Snapshot& Baseline) {
  TSharedRef<FJsonObject> Frame = MakeShared<FJsonObject>();
  Frame->SetStringField(TEXT("type"), TEXT("next"));
  Frame->SetStringField(TEXT("id"), TEXT("s08-1"));
  TSharedRef<FJsonObject> Payload = MakeShared<FJsonObject>();
  TSharedRef<FJsonObject> Data = MakeShared<FJsonObject>();
  TSharedRef<FJsonObject> Event = MakeShared<FJsonObject>();
  Event->SetNumberField(TEXT("sequenceNumber"), Baseline.SequenceNumber);
  Event->SetStringField(TEXT("phase"), Baseline.Phase);
  Event->SetNumberField(TEXT("turnCount"), Baseline.TurnCount);
  Event->SetStringField(TEXT("currentTurnPlayerId"), Baseline.CurrentTurnPlayerId);
  Data->SetObjectField(TEXT("gameStateUpdated"), Event);
  Payload->SetObjectField(TEXT("data"), Data);
  Frame->SetObjectField(TEXT("payload"), Payload);
  FString Out;
  auto Writer = TJsonWriterFactory<>::Create(&Out);
  FJsonSerializer::Serialize(Frame, Writer);
  return Out;
}
} // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09ResultWinnerParseTest,
    "Unmatched.S09.RESULT winner/loser/draw parse for both seats over the live projection",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09ResultWinnerParseTest::RunTest(const FString&) {
  FS08Snapshot Base;
  if (!LoadResultBaseSnapshot(Base)) {
    AddError(TEXT("base fixture gd035-move-open-host-view not loaded"));
    return true;
  }
  FString First, Second;
  if (!FixtureViewerIds(Base, First, Second)) { AddError("players missing"); return true; }

  // Host seat: the opponent won -> DEFEAT, opponent hero name rendered.
  FS09HudModel Lost;
  Lost.Build(WithTerminalState(Base, Second), First, TSet<FString>(), Base.SequenceNumber,
             Base.SequenceNumber);
  TestTrue("game over flagged", Lost.bGameOver);
  TestTrue("winner known", Lost.bWinnerKnown);
  TestFalse("host did not win", Lost.bViewerWon);
  TestEqual("host outcome word", Lost.OutcomeWord(), FString(TEXT("DEFEAT")));
  TestFalse("loser hero name not claimed", Lost.WinnerHeroName.IsEmpty());

  // Guest seat over the SAME terminal body: VICTORY + winner hero name.
  FS09HudModel Won;
  Won.Build(WithTerminalState(Base, Second), Second, TSet<FString>(), Base.SequenceNumber,
            Base.SequenceNumber);
  TestTrue("guest won flag", Won.bViewerWon);
  TestEqual("guest outcome word", Won.OutcomeWord(), FString(TEXT("VICTORY")));
  TestTrue("winner hero name decoded", !Won.WinnerHeroName.IsEmpty());

  // No winnerId while PLAYERS ARE STILL ALIVE (fixture body): the server
  // never writes this shape for a decided duel - it is not a draw, the
  // verdict is simply unavailable and must not be invented (the old model
  // claimed DRAW here).
  FS09HudModel NoVerdict;
  NoVerdict.Build(WithTerminalState(Base, FString()), First, TSet<FString>(),
                  Base.SequenceNumber, Base.SequenceNumber);
  TestTrue("no-verdict body flagged game over", NoVerdict.bGameOver);
  TestFalse("no-verdict has no known winner", NoVerdict.bWinnerKnown);
  TestFalse("living players are not a draw", NoVerdict.bDraw);
  TestTrue("outcome flagged unknown", NoVerdict.bOutcomeUnknown);
  TestEqual("no-verdict outcome word", NoVerdict.OutcomeWord(),
            FString(TEXT("OUTCOME UNAVAILABLE")));

  // Server draw shape (applyTerminalState, alive == 0): GAME_OVER with NO
  // winnerId and every player dead - mutual destruction. Only this is DRAW.
  FS09HudModel Draw;
  Draw.Build(WithAllPlayersDead(WithTerminalState(Base, FString())), First,
             TSet<FString>(), Base.SequenceNumber, Base.SequenceNumber);
  TestTrue("draw flagged game over", Draw.bGameOver);
  TestFalse("draw has no known winner", Draw.bWinnerKnown);
  TestTrue("mutual destruction flagged draw", Draw.bDraw);
  TestFalse("draw is not outcome-unknown", Draw.bOutcomeUnknown);
  TestEqual("draw outcome word", Draw.OutcomeWord(), FString(TEXT("DRAW")));

  // A winnerId that names NO player of the projection is not a claimable win
  // and not a draw - outcome unavailable.
  FS09HudModel Ghost;
  Ghost.Build(WithTerminalState(Base, TEXT("not-a-player")), First, TSet<FString>(),
              Base.SequenceNumber, Base.SequenceNumber);
  TestFalse("unknown winner id stays unknown", Ghost.bWinnerKnown);
  TestFalse("ghost winner is not a draw", Ghost.bDraw);
  TestTrue("ghost winner outcome unknown", Ghost.bOutcomeUnknown);
  TestEqual("unknown winner outcome", Ghost.OutcomeWord(),
            FString(TEXT("OUTCOME UNAVAILABLE")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09ResultStrictlyPhaseDrivenTest,
    "Unmatched.S09.RESULT strictly phase-driven: live phases and abort-shaped bodies never render a result",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09ResultStrictlyPhaseDrivenTest::RunTest(const FString&) {
  FS08Snapshot Base;
  if (!LoadResultBaseSnapshot(Base)) {
    AddError(TEXT("base fixture not loaded"));
    return true;
  }
  FString First, Second;
  FixtureViewerIds(Base, First, Second);

  // The untouched live body (mid-duel, MOVE pending open): no result.
  FS09HudModel Live;
  Live.Build(Base, First, TSet<FString>(), Base.SequenceNumber, Base.SequenceNumber);
  TestFalse("live phase is not game over", Live.bGameOver);
  TestFalse("live outcome word", Live.OutcomeWord() == FString(TEXT("VICTORY")));
  TestFalse("live outcome word 2", Live.OutcomeWord() == FString(TEXT("DEFEAT")));

  // Abort shape: an aborted room keeps the LAST duel phase (the server never
  // writes GAME_OVER for an abort) - only the room row goes ABORTED. Such a
  // body must not flip the result model, so a presented victory can only come
  // from the server outcome, never from a leave/abort.
  FS08Snapshot Aborted = Base;
  Aborted.Phase = TEXT("ACTION_MANEUVER");
  FS09HudModel AbortModel;
  AbortModel.Build(Aborted, First, TSet<FString>(), Base.SequenceNumber,
                   Base.SequenceNumber);
  TestFalse("abort-shaped body has no result", AbortModel.bGameOver);

  // Reconnect/late snapshot: a FRESH model over a terminal body alone (no
  // prior local state, no event replay) derives the full result.
  FS09HudModel Late;
  const FS08Snapshot Terminal = WithTerminalState(Base, Second);
  Late.Build(Terminal, First, TSet<FString>(), 0, 0);
  TestTrue("late terminal snapshot flagged", Late.bGameOver);
  TestEqual("late outcome word", Late.OutcomeWord(), FString(TEXT("DEFEAT")));

  // Idempotency: rebuilding from the same body (WS push + HTTP refetch of one
  // seq) yields identical values - a merge cannot double-present or flip.
  FS09HudModel Again;
  Again.Build(Terminal, First, TSet<FString>(), Base.SequenceNumber,
              Base.SequenceNumber);
  TestEqual("outcome stable across rebuild", Again.OutcomeWord(), Late.OutcomeWord());
  TestEqual("winner stable across rebuild", Again.WinnerHeroName, Late.WinnerHeroName);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09ResultInputGatesTest,
    "Unmatched.S09.RESULT terminal snapshot closes drafts and kills gameplay input (model + controller)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09ResultInputGatesTest::RunTest(const FString&) {
  FS08Snapshot Base;
  if (!LoadResultBaseSnapshot(Base)) {
    AddError(TEXT("base fixture not loaded"));
    return true;
  }
  FString First, Second;
  if (!FixtureViewerIds(Base, First, Second)) { AddError("players missing"); return true; }
  const FS08Snapshot Terminal = WithTerminalState(Base, Second);

  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  TestTrue("board decodes", Board.Decode(Terminal.BoardState));
  TestTrue("fighters decode", FS08BoardModel::DecodeFighters(Terminal.Fighters, Fighters));

  // Pre-open a MOVE pending draft on the LIVE body, then apply the terminal
  // body: the server clears pendingEffects at GAME_OVER and the client must
  // mirror it - Mode collapses to None, not PendingChoice.
  FS09CommandUi Ui;
  Ui.ViewerId = First;
  Ui.OnSnapshot(Base, Board, Fighters);
  TestEqual("live body opens the pending draft",
             static_cast<int32>(Ui.Mode), static_cast<int32>(ES09CommandMode::PendingChoice));
  const bool bModeChanged = Ui.OnSnapshot(Terminal, Board, Fighters);
  TestEqual("terminal body closes every draft",
             static_cast<int32>(Ui.Mode), static_cast<int32>(ES09CommandMode::None));
  TestTrue("mode change reported", bModeChanged);
  // Re-apply of the same terminal body: stays closed (no draft resurrection).
  Ui.OnSnapshot(Terminal, Board, Fighters);
  TestEqual("terminal re-apply stays closed",
             static_cast<int32>(Ui.Mode), static_cast<int32>(ES09CommandMode::None));

  FString Reason;
  TestFalse("beginManeuver dead on result screen", Ui.CanBeginManeuver(Terminal, Reason));
  TestTrue("beginManeuver reason mentions the duel end",
           Reason.Contains(TEXT("duel is over")));
  TestFalse("attack draft dead on result screen", Ui.CanOpenAttackDraft(Terminal, Reason));
  TestTrue("attack draft reason mentions the duel end",
           Reason.Contains(TEXT("duel is over")));

  // Controller-level gate + seq-guard dedupe over the same terminal body.
  FS08FlowController Flow(TEXT("http://127.0.0.1:9"), TEXT("ws://127.0.0.1:9"), First);
  TestEqual("first terminal apply", static_cast<int32>(Flow.ApplySnapshot(Terminal)),
            static_cast<int32>(ES08SeqDecision::Apply));
  TestFalse("controller gameplay gate closed", Flow.CanIssueGameplayCommand(Reason));
  TestTrue("controller gate reason mentions the duel end",
           Reason.Contains(TEXT("duel is over")));
  TestFalse("controller combat gate closed", Flow.CanIssueCombatCommand(Reason));
  TestTrue("combat gate reason mentions the duel end",
           Reason.Contains(TEXT("duel is over")));
  // Equal-seq merge of the same terminal body: no re-apply, gate stays closed.
  TestEqual("same-seq terminal merge",
            static_cast<int32>(Flow.ApplySnapshot(Terminal)),
            static_cast<int32>(ES08SeqDecision::Merge));
  TestFalse("gate still closed after merge", Flow.CanIssueGameplayCommand(Reason));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09EndTurnPhaseGateTest,
    "Unmatched.S09.RESULT endTurn phase gate: no mutation outside ACTION_MANEUVER/ACTION_ATTACK",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09EndTurnPhaseGateTest::RunTest(const FString&) {
  FS08Snapshot Base;
  if (!LoadResultBaseSnapshot(Base)) {
    AddError(TEXT("base fixture not loaded"));
    return true;
  }
  FString First, Second;
  if (!FixtureViewerIds(Base, First, Second)) { AddError("players missing"); return true; }
  // The viewer owns the turn (fixture body) so ONLY the phase gate can block.
  Base.CurrentTurnPlayerId = First;
  Base.Metadata.Reset(); // no pendingManeuver/pendingEffects heads open

  FS08FlowController Flow(TEXT("http://127.0.0.1:9/graphql"),
                          TEXT("ws://127.0.0.1:9/graphql"), First);
  TArray<FString> Traces;
  Flow.OnTrace.AddLambda([&Traces](const FString& Line) { Traces.Add(Line); });
  Flow.AttachStreamHarnessForTest(TEXT("gate-game"));

  // Sol6 review P1(3): the gameplay gate demands a PROVEN-live operation -
  // the harness subscribe alone leaves IsStreamReady closed, so every endTurn
  // below would be blocked as "stream reconnecting" before the phase logic.
  // Baseline the fixture body, then deliver the subscription's first 'next'
  // for op s08-1 at the SAME seq/phase/turn owner (a barrier merge).
  TestFalse("harness alone does not open the endTurn gate", Flow.IsStreamReady());
  Flow.ApplySnapshot(Base);
  Flow.InjectWsFrameForTest(BarrierNextFrame(Flow.GetAppliedSnapshot()));
  TestTrue("first delivered frame proves the stream live", Flow.IsStreamReady());
  TestEqual("no HTTP leg sent yet", Flow.GetTestHttpSendCountForTest(), 0);

  // Server network guard (game-turn.guard ActionEconomy) accepts endTurn ONLY
  // in ACTION_MANEUVER/ACTION_ATTACK. The S09 duel run 2026-09-26 sent 8
  // endTurn mutations from COMBAT/COMBAT_RESOLVE and burned authoritative
  // 'Invalid phase' rejections - the client gate must stop the send BEFORE
  // the network (observable: blocked trace + NO in-flight mutation).
  auto PhaseBlocked = [&](const TCHAR* Phase) {
    Traces.Reset();
    FS08Snapshot Snap = Base;
    Snap.Phase = Phase;
    Snap.SequenceNumber = Flow.GetAppliedSnapshot().SequenceNumber + 1;
    Flow.ApplySnapshot(Snap);
    Flow.EndTurn();
    const bool bBlocked = Traces.ContainsByPredicate([](const FString& Line) {
      return Line.Contains(TEXT("ENDTURN blocked: phase "));
    });
    TestTrue(FString::Printf(TEXT("endTurn blocked in %s"), Phase), bBlocked);
    TestFalse(FString::Printf(TEXT("no mutation left the client in %s"), Phase),
              Flow.IsManeuverInFlight());
    TestEqual(FString::Printf(TEXT("no HTTP leg spent in %s"), Phase),
              Flow.GetTestHttpSendCountForTest(), 0);
  };
  PhaseBlocked(TEXT("COMBAT"));
  PhaseBlocked(TEXT("COMBAT_RESOLVE"));
  PhaseBlocked(TEXT("SETUP"));
  PhaseBlocked(TEXT("PLACEMENT"));
  PhaseBlocked(TEXT("TURN_START"));
  PhaseBlocked(TEXT("TURN_END"));

  // Legal action phases: the gate opens (the send itself is the point). The
  // leg stays in flight on a deferred harness answer that is never delivered:
  // a real POST to the dead test port answers ~2 s later (Windows connect-
  // refused retries) into this destroyed controller (EndTurn captures `this`),
  // a use-after-free once later tests keep the process running.
  {
    FS08Snapshot Snap = Base;
    Snap.Phase = TEXT("ACTION_MANEUVER");
    Snap.SequenceNumber = Flow.GetAppliedSnapshot().SequenceNumber + 1;
    Flow.ApplySnapshot(Snap);
    Traces.Reset();
    Flow.QueueHttpResultForTest(false, {}, /*bDeferDelivery=*/true);
    TestTrue("endTurn dispatched", Flow.EndTurn());
    TestFalse("endTurn not blocked in ACTION_MANEUVER",
              Traces.ContainsByPredicate([](const FString& Line) {
                return Line.Contains(TEXT("ENDTURN blocked"));
              }));
    TestEqual("legal phase: exactly one HTTP leg", Flow.GetTestHttpSendCountForTest(), 1);
    TestTrue("endTurn leg in flight (send allowed)", Flow.IsManeuverInFlight());
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09SchemeBannerLegalityTest,
    "Unmatched.S09.RESULT scheme banner legality mirror: dead-banner schemes are never re-sent",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09SchemeBannerLegalityTest::RunTest(const FString&) {
  // bannerAllows mirror (game-rules.validator semantics)
  TestTrue("banner word in full name",
           FS09CommandUi::BannerAllowsFighter(TEXT("Arthur"), TEXT("King Arthur")));
  TestTrue("singular normalization",
           FS09CommandUi::BannerAllowsFighter(TEXT("Harpy"), TEXT("Harpies")));
  TestTrue("numeric suffix strip",
           FS09CommandUi::BannerAllowsFighter(TEXT("Harpy"), TEXT("Harpy 2")));
  TestTrue("ves plural",
           FS09CommandUi::BannerAllowsFighter(TEXT("Wolves"), TEXT("Wolf")));
  TestTrue("case insensitive",
           FS09CommandUi::BannerAllowsFighter(TEXT("MERLIN"), TEXT("Merlin")));
  TestFalse("different name",
            FS09CommandUi::BannerAllowsFighter(TEXT("Merlin"), TEXT("King Arthur")));

  auto MakeCard = [](const FString& Banner) {
    FS09CardView Card;
    Card.CardType = TEXT("SCHEME");
    Card.BannerName = Banner;
    return Card;
  };
  auto MakeFighter = [](const FString& Name, const FString& Owner, int32 Health) {
    FS08BoardFighter F;
    F.Name = Name;
    F.OwnerId = Owner;
    F.Health = Health;
    F.X = 1;
    F.Y = 1;
    return F;
  };
  const FString Me = TEXT("me"), Opp = TEXT("opp");
  TArray<FS08BoardFighter> Roster = {
      MakeFighter(TEXT("King Arthur"), Me, 12),
      MakeFighter(TEXT("Merlin"), Me, 0),          // defeated sidekick
      MakeFighter(TEXT("Medusa"), Opp, 14),
  };

  // The 10:41 loop: Merlin-banner scheme while only Arthur lives -> the
  // server rejects it; the driver must never pick it.
  TestFalse("dead-banner scheme is not playable",
            FS09CommandUi::SchemePlayableByLivingFighters(MakeCard(TEXT("Merlin")), Roster, Me));
  TestTrue("own hero banner is playable",
           FS09CommandUi::SchemePlayableByLivingFighters(MakeCard(TEXT("Arthur")), Roster, Me));
  TestTrue("generic empty banner is playable",
           FS09CommandUi::SchemePlayableByLivingFighters(MakeCard(FString()), Roster, Me));
  TestTrue("'any' banner is playable",
           FS09CommandUi::SchemePlayableByLivingFighters(MakeCard(TEXT("any")), Roster, Me));
  // A banner of the OPPONENT's fighter: known in the game, no living own
  // match -> the server rejects it for this seat.
  TestFalse("opponent banner scheme is not playable for this seat",
            FS09CommandUi::SchemePlayableByLivingFighters(MakeCard(TEXT("Medusa")), Roster, Me));
  // Dirty data tolerance: a banner of NOBODY in the game plays (server warn +
  // allow); the driver mirrors it instead of stranding a legal card.
  TestTrue("unknown banner stays playable (dirty data)",
           FS09CommandUi::SchemePlayableByLivingFighters(MakeCard(TEXT("Zeppo")), Roster, Me));

  // Revived banner: Merlin back at full health -> playable again.
  TArray<FS08BoardFighter> Revived = Roster;
  Revived[1].Health = 4;
  TestTrue("revived banner fighter makes the scheme playable",
           FS09CommandUi::SchemePlayableByLivingFighters(MakeCard(TEXT("Merlin")), Revived, Me));
  return true;
}

// ---- DE-019 (W-16; 01 F-09, D-DE-09; CUE-DISPATCHER.md §3.1): death by stages and the result gate ----
namespace S09DeathTest {
FS09CombatStageInput LethalInput(const FString& Target) {
  FS09CombatStageInput In;
  In.Seq = 40;
  In.AttackerId = TEXT("arthur");
  In.TargetId = Target;
  In.bHasEffectText = true;
  In.Damage = 2;
  In.HpBefore = 2;
  In.HpAfter = 0;
  In.bLethal = true;
  In.TargetX = 3;
  In.TargetY = 4;
  In.ContactMs = 292;
  In.ContactSource = TEXT("notify");
  In.Reveal.AttackValue = 4;
  In.Reveal.DefenseValue = 0;
  In.Reveal.bNoDefense = true;
  return In;
}

/** The v2 plan of a hero / sidekick with its clip and dissolve MIC (ms). */
FS09DeathInput PlanFor(const FString& Id, bool bHero, int32 Seq, bool bStaged) {
  FS09DeathInput D;
  D.FighterId = Id;
  D.bHero = bHero;
  D.Seq = Seq;
  D.bStaged = bStaged;
  D.SettleMs = FS09DeathTiming::SettleMs;
  D.StillMs = bHero ? FS09DeathTiming::StillHeroMs : FS09DeathTiming::StillSidekickMs;
  D.DissolveMs = bHero ? FS09DeathTiming::DissolveHeroMs : FS09DeathTiming::DissolveSidekickMs;
  D.Style = TEXT("fade");
  return D;
}

/** A staged lethal blow, then the death and the result gate on a 1 ms clock - the game mode's order per frame:
 *  staging Tick + Advance, the Fall event stages the death, death Tick, gate Update. */
struct FRun {
  FS08CueDispatcher Cues;
  FS09CombatStage Stage;
  FS09DeathStage Death;
  FS09ResultGate Gate;
  TArray<FString> Lines;
  int64 ContactMs = -1;
  int64 FallMs = -1;
  int64 ScreenMs = -1;
};
void Run(FRun& R, const FS09CombatStageInput& In, bool bHero, bool bGameOver, int64 EndMs = 20000) {
  TArray<FS09CombatStageEvent> Events;
  R.Stage.Start(In, 1000, R.Cues, R.Lines, Events);
  for (int64 T = 1000; T <= EndMs; ++T) {
    Events.Reset();
    R.Stage.Tick(T, R.Cues, R.Lines, Events);
    R.Cues.Advance(T, R.Lines);
    for (const FS09CombatStageEvent& E : Events) {
      if (E.Type == ES09CombatEvent::HitReact) R.ContactMs = E.AtMs;
      if (E.Type == ES09CombatEvent::Fall) {
        R.FallMs = T;
        R.Death.Begin(PlanFor(In.TargetId, bHero, In.Seq, true), T, R.Cues, R.Lines);
      }
    }
    R.Death.Tick(T, R.Lines);
    const bool bPending = R.Stage.IsActive() && In.bLethal && bHero && R.Stage.GetHold().bAliveHeld;
    FString Line;
    if (R.Gate.Update(T, In.Seq, bGameOver, bPending, R.Death.LatestHeroGoneMs(), Line)) {
      R.ScreenMs = T;
      R.Lines.Add(Line);
    }
  }
  R.Cues.Finish(R.Lines);
}

int64 StageT(const TArray<FString>& Lines, const FString& Needle) {
  for (const FString& L : Lines) {
    if (!L.Contains(Needle)) continue;
    const int32 At = L.Find(TEXT(" t="));
    if (At != INDEX_NONE) return FCString::Atoi64(*L.Mid(At + 3));
  }
  return -1;
}
}  // namespace S09DeathTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09DeathStageTimelineTest, "Unmatched.S09.DeathStage.Timeline",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09DeathStageTimelineTest::RunTest(const FString&) {
  using namespace S09DeathTest;
  // ---- the F-09 table from the contact frame ----
  TestEqual("hero gone 2125 ms after the contact", FS09DeathTiming::GoneAfterContactMs(true), 2125);
  TestEqual("sidekick gone 1725 ms after the contact", FS09DeathTiming::GoneAfterContactMs(false), 1725);
  TestEqual("mark 650 ms after the fall (contact + 1100)", FS09DeathTiming::MarkAfterFallMs, 650);
  {
    FRun R;
    Run(R, LethalInput(TEXT("medusa")), /*bHero=*/true, /*bGameOver=*/false);
    TestTrue("contact frame seen", R.ContactMs > 0);
    TestEqual("hero: fall = contact + 450", R.FallMs - R.ContactMs, static_cast<int64>(450));
    TestEqual("hero: mark = contact + 1100", StageT(R.Lines, TEXT("stage=mark")) - R.ContactMs, static_cast<int64>(1100));
    TestEqual("hero: dissolve = contact + 1625 (settle 875 + still 300)",
              StageT(R.Lines, TEXT("stage=dissolve")) - R.ContactMs, static_cast<int64>(1625));
    TestEqual("hero: gone = contact + 2125", StageT(R.Lines, TEXT("stage=gone")) - R.ContactMs, static_cast<int64>(2125));
    TestEqual("hero: scheduled gone", R.Death.GoneMs(TEXT("medusa")) - R.ContactMs, static_cast<int64>(2125));
    TestTrue("fall line carries the plan",
             R.Lines.ContainsByPredicate([](const FString& L) {
               return L.StartsWith(TEXT("CUE death seq=40 stage=fall")) &&
                      L.Contains(TEXT(" fighter=medusa hero=1 staged=1 settle=875 still=300 dissolve=500 style=fade"));
             }));
    TestTrue("the combat fall and the death fall are one frame",
             StageT(R.Lines, TEXT("CUE combat seq=40 stage=fall")) == StageT(R.Lines, TEXT("CUE death seq=40 stage=fall")));
    // CUE-013 from the fall: DeathSettle, the row's 950 ms (blocks input <= 1 s)
    TestEqual("CUE-013 show from the fall", StageT(R.Lines, TEXT("CUE fx id=CUE-013 subject=medusa")), R.FallMs);
    TestTrue("CUE-013 done after 950 ms", R.Lines.ContainsByPredicate([&R](const FString& L) {
      return L == FString::Printf(TEXT("CUE fx done id=CUE-013 subject=medusa seq=40 t=%lld ms=950 cut=0"), R.FallMs + 950);
    }));
    TestTrue("heart alive before the mark",
             R.Death.HeartState(TEXT("medusa"), R.ContactMs + 1099) == ES09HeartState::Alive);
    TestTrue("heart dark at the mark (no accepted cross glyph)",
             R.Death.HeartState(TEXT("medusa"), R.ContactMs + 1100) == ES09HeartState::Dark);
    TestEqual("no game over, no screen", R.ScreenMs, static_cast<int64>(-1));
  }
  {
    FRun R;
    Run(R, LethalInput(TEXT("harpy2")), /*bHero=*/false, /*bGameOver=*/false);
    TestEqual("sidekick: gone = contact + 1725", StageT(R.Lines, TEXT("stage=gone")) - R.ContactMs, static_cast<int64>(1725));
    TestEqual("sidekick: dissolve right after DeathSettle (still 0)",
              StageT(R.Lines, TEXT("stage=dissolve")) - R.ContactMs, static_cast<int64>(1325));
    TestEqual("sidekick death is not a hero gone time", R.Death.LatestHeroGoneMs(), static_cast<int64>(-1));
  }
  // ---- a figure that hides at once (grey slice / no MIC, no clip): gone in the fall frame, no dissolve line ----
  {
    FS08CueDispatcher Cues;
    FS09DeathStage Death;
    TArray<FString> Lines;
    FS09DeathInput D;
    D.FighterId = TEXT("f-1-hero");
    D.bHero = true;
    D.Seq = 12;
    TestTrue("begins", Death.Begin(D, 500, Cues, Lines));
    TestFalse("one death per fighter", Death.Begin(D, 600, Cues, Lines));
    TestEqual("instant: gone = fall", Death.GoneMs(TEXT("f-1-hero")), static_cast<int64>(500));
    TestEqual("instant: gone line in the fall frame", StageT(Lines, TEXT("stage=gone")), static_cast<int64>(500));
    TestFalse("instant: no dissolve line",
              Lines.ContainsByPredicate([](const FString& L) { return L.Contains(TEXT("stage=dissolve")); }));
    TestTrue("instant: style none", Lines.ContainsByPredicate([](const FString& L) {
      return L.Contains(TEXT("stage=fall")) && L.Contains(TEXT(" style=none gone=500"));
    }));
    Death.Tick(1150, Lines);
    TestEqual("instant: mark still at fall + 650", StageT(Lines, TEXT("stage=mark")), static_cast<int64>(1150));
  }
  // ---- the figure actor's plan (S08HeroesV2) gives the same numbers ----
  {
    using namespace S08HeroesV2;
    const FHeroSpec* Arthur = Find(true, true, TEXT("King Arthur"));
    const FHeroSpec* Merlin = Find(true, true, TEXT("Merlin"));
    if (TestNotNull("Arthur spec", Arthur) && TestNotNull("Merlin spec", Merlin)) {
      const float Settle = ExpectedClipSeconds(*Arthur, EClip::DeathSettle);
      const FDeathPlan H = MakeDeathPlan(*Arthur, Settle, true);
      const FDeathPlan S = MakeDeathPlan(*Merlin, Settle, true);
      TestEqual("hero plan gone from the fall (ms)", FMath::RoundToInt(H.GoneSeconds() * 1000.0f),
                FS09DeathTiming::GoneAfterContactMs(true) - FS09DeathTiming::FallAfterContactMs);
      TestEqual("sidekick plan gone from the fall (ms)", FMath::RoundToInt(S.GoneSeconds() * 1000.0f),
                FS09DeathTiming::GoneAfterContactMs(false) - FS09DeathTiming::FallAfterContactMs);
      TestEqual("settle = DeathSettle clip (ms)", FMath::RoundToInt(Settle * 1000.0f), FS09DeathTiming::SettleMs);
      const FDeathPlan NoMic = MakeDeathPlan(*Arthur, Settle, false);
      TestEqual("no MIC: no dissolve", NoMic.DissolveSeconds, 0.0f);
      TestEqual("progress 0 while still", DissolveProgressAt(H, 1.1f), 0.0f);
      TestTrue("progress half way", FMath::IsNearlyEqual(DissolveProgressAt(H, 1.175f + 0.25f), 0.5f, 1e-3f));
      TestEqual("progress 1 when gone", DissolveProgressAt(H, 1.675f), 1.0f);
      TestEqual("no MIC: progress jumps to 1 at the still end", DissolveProgressAt(NoMic, 1.18f), 1.0f);
    }
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09DeathStageResultGateTest, "Unmatched.S09.DeathStage.ResultGate",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09DeathStageResultGateTest::RunTest(const FString&) {
  using namespace S09DeathTest;
  // ---- the killing blow on a hero: GAME_OVER arrives with the result snapshot, the screen waits ----
  {
    FRun R;
    Run(R, LethalInput(TEXT("medusa")), /*bHero=*/true, /*bGameOver=*/true);
    TestEqual("hit -> screen = 2125 + 1000 = 3125 ms (~3.1 s)", R.ScreenMs - R.ContactMs, static_cast<int64>(3125));
    TestEqual("screen = hero gone + 1000", R.ScreenMs - R.Death.LatestHeroGoneMs(), static_cast<int64>(1000));
    TestTrue("RESULT screen line", R.Lines.ContainsByPredicate([&R](const FString& L) {
      return L == FString::Printf(TEXT("RESULT screen seq=40 t=%lld due=%lld gameOver=1000 heroGone=%lld wait=%lld"),
                                  R.ScreenMs, R.ScreenMs, R.Death.LatestHeroGoneMs(), R.ScreenMs - 1000);
    }));
    int32 Screens = 0;
    for (const FString& L : R.Lines) Screens += L.StartsWith(TEXT("RESULT screen")) ? 1 : 0;
    TestEqual("the outcome is shown once", Screens, 1);
    TestTrue("stays shown", R.Gate.IsShown());
  }
  // ---- a skip in the read hold moves the contact - and the screen with it ----
  {
    FRun R;
    TArray<FS09CombatStageEvent> Events;
    const FS09CombatStageInput In = LethalInput(TEXT("medusa"));
    R.Stage.Start(In, 0, R.Cues, R.Lines, Events);
    for (int64 T = 0; T <= 12000; ++T) {
      Events.Reset();
      R.Stage.Tick(T, R.Cues, R.Lines, Events);
      R.Cues.Advance(T, R.Lines);
      if (T == 800) R.Stage.Skip(T, TEXT("space"), R.Cues, R.Lines, Events);
      for (const FS09CombatStageEvent& E : Events) {
        if (E.Type == ES09CombatEvent::HitReact) R.ContactMs = E.AtMs;
        if (E.Type == ES09CombatEvent::Fall) R.Death.Begin(PlanFor(In.TargetId, true, In.Seq, true), T, R.Cues, R.Lines);
      }
      R.Death.Tick(T, R.Lines);
      FString Line;
      if (R.Gate.Update(T, In.Seq, true, R.Stage.IsActive() && R.Stage.GetHold().bAliveHeld, R.Death.LatestHeroGoneMs(),
                        Line)) {
        R.ScreenMs = T;
      }
    }
    TestEqual("skipped staging: still contact + 3125", R.ScreenMs - R.ContactMs, static_cast<int64>(3125));
  }
  // ---- a sidekick's death never holds the screen (and never ends the game by itself) ----
  {
    FS09ResultGate Gate;
    FString Line;
    TestFalse("no game over: closed", Gate.Update(100, 7, false, false, -1, Line));
    TestTrue("game over without a hero death: at once", Gate.Update(200, 8, true, false, -1, Line));
    TestEqual("at once: due = game over", Gate.GetShownMs(), static_cast<int64>(200));
    TestTrue("line", Line.StartsWith(TEXT("RESULT screen seq=8 t=200 due=200 gameOver=200 heroGone=- wait=0")));
    TestFalse("opens once", Gate.Update(300, 8, true, false, -1, Line));
  }
  // ---- a hero gone long before GAME_OVER (the terminal body came later): at once ----
  {
    FS09ResultGate Gate;
    FString Line;
    Gate.Update(100, 9, false, false, 1200, Line);
    TestTrue("late GAME_OVER after gone + 1000: at once", Gate.Update(5000, 10, true, false, 1200, Line));
  }
  // ---- a hero death at the snapshot (no staging: an ability, a cut staging) ----
  {
    FS08CueDispatcher Cues;
    FS09DeathStage Death;
    FS09ResultGate Gate;
    TArray<FString> Lines;
    Death.Begin(PlanFor(TEXT("arthur"), true, 55, false), 2000, Cues, Lines);
    FString Line;
    int64 Shown = -1;
    for (int64 T = 2000; T <= 8000 && Shown < 0; ++T) {
      if (Gate.Update(T, 55, true, false, Death.LatestHeroGoneMs(), Line)) Shown = T;
    }
    TestEqual("snapshot death: fall + 1675 + 1000", Shown, static_cast<int64>(2000 + 1675 + 1000));
  }
  // ---- review IMPL 2026-10-05 (DE-019 tail): a hero death at the snapshot while an EARLIER combat is still staged
  //      (run F, Marmoreal #1: the screen opened 233 ms before that staging's end). The staging finishes first;
  //      a staging that ends before the due time changes nothing; the cap still wins. ----
  {
    FS08CueDispatcher Cues;
    FS09DeathStage Death;
    TArray<FString> Lines;
    Death.Begin(PlanFor(TEXT("arthur"), true, 56, false), 2000, Cues, Lines);
    const int64 Gone = Death.LatestHeroGoneMs();
    const int64 PlainDue = Gone + FS09DeathTiming::ResultAfterGoneMs;  // 4675
    {
      FS09ResultGate Gate;
      FString Line;
      int64 Shown = -1;
      for (int64 T = 2000; T <= 8000 && Shown < 0; ++T) {
        if (Gate.Update(T, 56, true, false, Death.LatestHeroGoneMs(), Line, /*StagingEndMs=*/PlainDue + 233)) Shown = T;
      }
      TestEqual("staging ends after gone + 1000: the screen waits for its end", Shown, PlainDue + 233);
      TestTrue("the line names the staging hold", Line.EndsWith(FString::Printf(TEXT(" staging=%lld"), PlainDue + 233)));
    }
    {
      FS09ResultGate Gate;
      FString Line;
      int64 Shown = -1;
      for (int64 T = 2000; T <= 8000 && Shown < 0; ++T) {
        if (Gate.Update(T, 56, true, false, Death.LatestHeroGoneMs(), Line, /*StagingEndMs=*/PlainDue - 500)) Shown = T;
      }
      TestEqual("staging ends before gone + 1000: unchanged", Shown, PlainDue);
      TestFalse("no staging token when it did not hold", Line.Contains(TEXT("staging=")));
    }
    {
      FS09ResultGate Gate;
      FString Line;
      TestFalse("staging beyond the cap: closed at GAME_OVER", Gate.Update(2000, 56, true, false, Gone, Line, 2000 + 20000));
      TestFalse("staging beyond the cap: closed before the cap",
                Gate.Update(2000 + FS09ResultGate::MaxWaitMs - 1, 56, true, false, Gone, Line, 2000 + 20000));
      TestTrue("staging beyond the cap: the cap opens it",
               Gate.Update(2000 + FS09ResultGate::MaxWaitMs, 56, true, false, Gone, Line, 2000 + 20000));
    }
  }
  // ---- the pending fall holds it; the safety cap opens it anyway ----
  {
    FS09ResultGate Gate;
    FString Line;
    TestFalse("pending fall: closed", Gate.Update(0, 3, true, true, -1, Line));
    TestEqual("pending: no due", Gate.DueMs(true), static_cast<int64>(-1));
    TestFalse("still pending at 9999", Gate.Update(FS09ResultGate::MaxWaitMs - 1, 3, true, true, -1, Line));
    TestTrue("cap opens at game over + 10 s", Gate.Update(FS09ResultGate::MaxWaitMs, 3, true, true, -1, Line));
    Gate.Reset();
    TestFalse("reset: no game over", Gate.IsGameOver() || Gate.IsShown());
  }
  return true;
}

// ---------------------------------------------------------------------------------------------------- DE-029

namespace {
/** Rewrites one array projection entry by entry (the fixture body stays otherwise untouched). */
TSharedPtr<FJsonValue> MapEntries(const TSharedPtr<FJsonValue>& Array,
                                  TFunctionRef<void(const TSharedRef<FJsonObject>&)> Edit) {
  const TArray<TSharedPtr<FJsonValue>>* Entries = nullptr;
  if (!Array.IsValid() || !Array->TryGetArray(Entries) || !Entries) return Array;
  TArray<TSharedPtr<FJsonValue>> Out;
  for (const TSharedPtr<FJsonValue>& Value : *Entries) {
    const TSharedPtr<FJsonObject>* Object = nullptr;
    if (!Value.IsValid() || !Value->TryGetObject(Object) || !Object->IsValid()) continue;
    const TSharedRef<FJsonObject> Copy = MakeShared<FJsonObject>(**Object);
    Edit(Copy);
    Out.Add(MakeShared<FJsonValueObject>(Copy));
  }
  return MakeShared<FJsonValueArray>(Out);
}

/** The server's terminal body of a hero kill: the loser's hero at HP 0 and the loser player not alive. */
FS08Snapshot WithHeroKilled(const FS08Snapshot& Snapshot, const FString& LoserId) {
  FS08Snapshot Out = Snapshot;
  Out.Fighters = MapEntries(Out.Fighters, [&LoserId](const TSharedRef<FJsonObject>& F) {
    if (F->GetStringField(TEXT("ownerId")) == LoserId && F->GetStringField(TEXT("type")) == TEXT("HERO")) {
      F->SetNumberField(TEXT("health"), 0);
    }
  });
  Out.Players = MapEntries(Out.Players, [&LoserId](const TSharedRef<FJsonObject>& P) {
    if (P->GetStringField(TEXT("userId")) == LoserId) {
      P->SetBoolField(TEXT("isAlive"), false);
      P->SetNumberField(TEXT("health"), 0);
    }
  });
  return Out;
}

/** Sidekicks first: the winner's harpy stands before Medusa in fighters[] (the s04 case - a harpy struck the last
 *  blow); the headline must still name the hero. */
FS08Snapshot WithSidekicksFirst(const FS08Snapshot& Snapshot) {
  FS08Snapshot Out = Snapshot;
  const TArray<TSharedPtr<FJsonValue>>* Entries = nullptr;
  if (!Out.Fighters.IsValid() || !Out.Fighters->TryGetArray(Entries) || !Entries) return Out;
  TArray<TSharedPtr<FJsonValue>> Sidekicks;
  TArray<TSharedPtr<FJsonValue>> Heroes;
  for (const TSharedPtr<FJsonValue>& Value : *Entries) {
    const TSharedPtr<FJsonObject> F = Value.IsValid() ? Value->AsObject() : nullptr;
    (F.IsValid() && F->GetStringField(TEXT("type")) == TEXT("HERO") ? Heroes : Sidekicks).Add(Value);
  }
  Sidekicks.Append(Heroes);
  Out.Fighters = MakeShared<FJsonValueArray>(Sidekicks);
  return Out;
}
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09ResultScreenSummaryTest, "Unmatched.S09.ResultScreen.Summary",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09ResultScreenSummaryTest::RunTest(const FString&) {
  FS08Snapshot Base;
  if (!LoadResultBaseSnapshot(Base)) {
    AddError(TEXT("base fixture gd035-move-open-host-view not loaded"));
    return true;
  }
  FString First, Second;  // First plays Medusa (+ 3 harpies), Second King Arthur (+ Merlin)
  if (!FixtureViewerIds(Base, First, Second)) { AddError("players missing"); return true; }
  const FS08Snapshot Kill = WithSidekicksFirst(WithHeroKilled(WithTerminalState(Base, First), Second));
  const FString Started = TEXT("2026-10-04T12:00:00.000Z");
  const FString Ended = TEXT("2026-10-04T12:12:05.400Z");

  // ---- the winner's seat: VICTORY, the headline by the winning HERO (the harpies stand first in fighters[]) ----
  {
    FS09HudModel Hud;
    Hud.Build(Kill, First, TSet<FString>(), Kill.SequenceNumber, Kill.SequenceNumber);
    const FS09ResultSummary S = FS09ResultSummary::Build(Hud, Kill, Started, Ended);
    TestTrue("valid on GAME_OVER", S.bValid);
    TestEqual("outcome", S.Outcome, FString(TEXT("VICTORY")));
    TestEqual("headline names the hero, not the harpy", S.Headline, FString(TEXT("MEDUSA WINS")));
    TestEqual("reason: the loser hero's HP", S.ReasonText, FString(TEXT("King Arthur's HP reached 0")));
    TestTrue("reason kind", S.Reason == ES09ResultReason::HeroHpZero);
    TestEqual("turn from the snapshot", S.TurnCount, Kill.TurnCount);
    TestEqual("duration endedAt - startedAt", S.DurationSec, 725);
    TestEqual("stats line", S.StatsLine(), FString::Printf(TEXT("Turn %d  ·  12:05"), Kill.TurnCount));
    TestTrue("left = winner = viewer", S.Left.bWinner && S.Left.bViewer && S.Left.PlayerId == First);
    TestEqual("left hero", S.Left.HeroName, FString(TEXT("Medusa")));
    TestTrue("left hp", S.Left.bHpKnown && S.Left.Hp == 16 && S.Left.MaxHp == 16);
    TestFalse("winner is not a silhouette", S.Left.bSilhouette);
    TestTrue("right = loser silhouette", S.Right.bSilhouette && !S.Right.bWinner && S.Right.PlayerId == Second);
    TestEqual("right hero", S.Right.HeroName, FString(TEXT("King Arthur")));
    TestTrue("right hp 0 / 18", S.Right.bHpKnown && S.Right.Hp == 0 && S.Right.MaxHp == 18);
    TestTrue("trace", S.TraceLine().StartsWith(FString::Printf(
                          TEXT("RESULT summary outcome=VICTORY winnerHero=Medusa loserHero=King_Arthur reason=hp0 "
                               "turn=%d duration=725 left=viewer silhouette=1"),
                          Kill.TurnCount)));
  }
  // ---- the loser's seat over the same body: DEFEAT, the winner still left, the viewer is the silhouette ----
  {
    FS09HudModel Hud;
    Hud.Build(Kill, Second, TSet<FString>(), Kill.SequenceNumber, Kill.SequenceNumber);
    const FS09ResultSummary S = FS09ResultSummary::Build(Hud, Kill, Started, FString());
    TestEqual("defeat", S.Outcome, FString(TEXT("DEFEAT")));
    TestEqual("same headline on both seats", S.Headline, FString(TEXT("MEDUSA WINS")));
    TestTrue("left = opponent winner", S.Left.bWinner && !S.Left.bViewer);
    TestTrue("right = viewer silhouette", S.Right.bViewer && S.Right.bSilhouette);
    TestEqual("no endedAt yet: duration unknown", S.DurationSec, -1);
    TestEqual("stats without duration", S.StatsLine(), FString::Printf(TEXT("Turn %d"), Kill.TurnCount));
  }
  // ---- a winner while the loser hero still has HP: the server's verdict, not an invented "HP reached 0" ----
  {
    const FS08Snapshot Verdict = WithTerminalState(Base, Second);
    FS09HudModel Hud;
    Hud.Build(Verdict, First, TSet<FString>(), Verdict.SequenceNumber, Verdict.SequenceNumber);
    const FS09ResultSummary S = FS09ResultSummary::Build(Hud, Verdict, Started, Ended);
    TestEqual("verdict headline", S.Headline, FString(TEXT("KING ARTHUR WINS")));
    TestTrue("verdict reason", S.Reason == ES09ResultReason::Verdict);
    TestTrue("the loser is still the silhouette", S.Right.bSilhouette && S.Right.PlayerId == First);
  }
  // ---- mutual destruction: no winner, nobody is a silhouette, the viewer stays left ----
  {
    const FS08Snapshot Draw = WithAllPlayersDead(WithTerminalState(Base, FString()));
    FS09HudModel Hud;
    Hud.Build(Draw, Second, TSet<FString>(), Draw.SequenceNumber, Draw.SequenceNumber);
    const FS09ResultSummary S = FS09ResultSummary::Build(Hud, Draw, Started, Ended);
    TestEqual("draw outcome", S.Outcome, FString(TEXT("DRAW")));
    TestEqual("draw headline", S.Headline, FString(TEXT("MUTUAL DESTRUCTION")));
    TestTrue("draw reason", S.Reason == ES09ResultReason::Draw);
    TestTrue("viewer left", S.Left.bViewer && S.Left.PlayerId == Second);
    TestFalse("no silhouette", S.Left.bSilhouette || S.Right.bSilhouette || S.Left.bWinner || S.Right.bWinner);
  }
  // ---- no verdict / a live body ----
  {
    const FS08Snapshot NoVerdict = WithTerminalState(Base, FString());
    FS09HudModel Hud;
    Hud.Build(NoVerdict, First, TSet<FString>(), NoVerdict.SequenceNumber, NoVerdict.SequenceNumber);
    const FS09ResultSummary S = FS09ResultSummary::Build(Hud, NoVerdict, Started, Ended);
    TestTrue("unknown reason", S.Reason == ES09ResultReason::Unknown);
    TestEqual("unknown headline", S.Headline, FString(TEXT("NO SERVER VERDICT")));
    FS09HudModel Live;
    Live.Build(Base, First, TSet<FString>(), Base.SequenceNumber, Base.SequenceNumber);
    TestFalse("a live body is no result", FS09ResultSummary::Build(Live, Base, Started, Ended).bValid);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09ResultScreenDurationTest, "Unmatched.S09.ResultScreen.Duration",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09ResultScreenDurationTest::RunTest(const FString&) {
  TestEqual("12:05", FS09ResultSummary::DurationSeconds(TEXT("2026-10-04T12:00:00.000Z"),
                                                        TEXT("2026-10-04T12:12:05.999Z")), 725);
  TestEqual("over an hour", FS09ResultSummary::DurationSeconds(TEXT("2026-10-04T23:30:00Z"),
                                                               TEXT("2026-10-05T00:32:05Z")), 3725);
  TestEqual("not ended", FS09ResultSummary::DurationSeconds(TEXT("2026-10-04T12:00:00Z"), FString()), -1);
  TestEqual("not started", FS09ResultSummary::DurationSeconds(FString(), TEXT("2026-10-04T12:00:00Z")), -1);
  TestEqual("garbage", FS09ResultSummary::DurationSeconds(TEXT("yesterday"), TEXT("2026-10-04T12:00:00Z")), -1);
  // DE-031 live: the backend's Date scalar sends epoch milliseconds (game(id) startedAt / endedAt as JSON numbers)
  TestEqual("epoch ms (live game row)", FS09ResultSummary::DurationSeconds(TEXT("1791197331439"), TEXT("1791197358802")),
            27);
  TestEqual("epoch ms, 12:05", FS09ResultSummary::DurationSeconds(TEXT("1791196800000"), TEXT("1791197525000")), 725);
  TestEqual("epoch ms mixed with ISO", FS09ResultSummary::DurationSeconds(TEXT("1791196800000"),
                                                                          TEXT("2026-10-05T10:52:05Z")), 725);
  TestEqual("zero epoch", FS09ResultSummary::DurationSeconds(TEXT("0"), TEXT("1791197358802")), -1);
  TestEqual("reversed", FS09ResultSummary::DurationSeconds(TEXT("2026-10-04T12:00:10Z"), TEXT("2026-10-04T12:00:00Z")),
            -1);
  TestEqual("m:ss", FS09ResultSummary::FormatDuration(725), FString(TEXT("12:05")));
  TestEqual("0:07", FS09ResultSummary::FormatDuration(7), FString(TEXT("0:07")));
  TestEqual("h:mm:ss", FS09ResultSummary::FormatDuration(3725), FString(TEXT("1:02:05")));
  TestEqual("unknown", FS09ResultSummary::FormatDuration(-1), FString(TEXT("-")));
  {
    // the room poll as the live server answers it: game(id) with the Date scalar as epoch-ms numbers
    FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), TEXT("p-host"));
    Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);
    Flow.QueueHttpResultForTest(
        true, {}, /*bDeferDelivery=*/true,
        TEXT("{\"data\":{\"game\":{\"id\":\"g-1\",\"code\":\"AAA111\",\"status\":\"FINISHED\",")
        TEXT("\"mode\":\"ONE_V_ONE\",\"hostId\":\"p-host\",\"boardId\":\"b-1\",")
        TEXT("\"startedAt\":1791197331439,\"endedAt\":1791197358802,\"players\":[]}}}"));
    Flow.PollRoom();
    Flow.DeliverQueuedHttpForTest();
    TestEqual("room keeps the numeric startedAt", Flow.GetRoom().StartedAt, FString(TEXT("1791197331439")));
    TestEqual("room keeps the numeric endedAt", Flow.GetRoom().EndedAt, FString(TEXT("1791197358802")));
    TestEqual("... and the result screen gets its duration",
              FS09ResultSummary::DurationSeconds(Flow.GetRoom().StartedAt, Flow.GetRoom().EndedAt), 27);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09ResultScreenViewTest, "Unmatched.S09.ResultScreen.View",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09ResultScreenViewTest::RunTest(const FString&) {
  FS09ResultView View;
  TestFalse("hidden before the gate", View.IsOpen());
  TestEqual("hidden: no modal", View.ResultsAlpha(0), 0.0f);
  TestTrue("hidden: keys do nothing", View.OnKey(ES09ResultKey::Enter) == ES09ResultAction::None);
  TestFalse("hidden: no toggle", View.ToggleBoard(10));

  // ---- the intro: 500 ms fade in (SD-45 p. 3), then exactly 1 - and it never closes by itself (F-06) ----
  TestTrue("opens", View.Open(1000));
  TestFalse("second open keeps the mode", View.Open(1100));
  TestEqual("intro start", View.ResultsAlpha(1000), 0.0f);
  TestEqual("intro half", View.ResultsAlpha(1250), 0.5f);
  TestEqual("intro done", View.ResultsAlpha(1000 + FS09ResultView::IntroMs), 1.0f);
  TestEqual("one minute later still up", View.ResultsAlpha(61000), 1.0f);
  TestTrue("still the results", View.Mode() == ES09ResultMode::Results);
  TestEqual("no board bar on the results", View.BoardBarAlpha(61000), 0.0f);
  TestTrue("results take clicks", View.ResultsHitTestable());
  // ---- keys on the results (02 §2.9): Enter / Esc / L = lobby, V = board ----
  TestTrue("Enter lobby", View.OnKey(ES09ResultKey::Enter) == ES09ResultAction::Lobby);
  TestTrue("Esc lobby", View.OnKey(ES09ResultKey::Escape) == ES09ResultAction::Lobby);
  TestTrue("L lobby", View.OnKey(ES09ResultKey::L) == ES09ResultAction::Lobby);
  TestTrue("V board", View.OnKey(ES09ResultKey::V) == ES09ResultAction::ToggleBoard);

  // ---- "view the board": a 250 ms crossfade ----
  TestTrue("to the board", View.ToggleBoard(70000));
  TestTrue("board mode", View.IsBoardView());
  TestFalse("the fading modal takes no clicks", View.ResultsHitTestable());
  TestEqual("crossfade start", View.ResultsAlpha(70000), 1.0f);
  TestEqual("crossfade half", View.ResultsAlpha(70125), 0.5f);
  TestEqual("bar half", View.BoardBarAlpha(70125), 0.5f);
  TestEqual("crossfade done", View.ResultsAlpha(70000 + FS09ResultView::CrossfadeMs), 0.0f);
  TestEqual("bar up", View.BoardBarAlpha(70250), 1.0f);
  TestEqual("the board stays", View.ResultsAlpha(200000), 0.0f);
  // ---- keys on the board: Esc = back to the results, Enter / L = lobby, V toggles ----
  TestTrue("board Esc back", View.OnKey(ES09ResultKey::Escape) == ES09ResultAction::ToggleBoard);
  TestTrue("board Enter lobby", View.OnKey(ES09ResultKey::Enter) == ES09ResultAction::Lobby);
  TestTrue("board L lobby", View.OnKey(ES09ResultKey::L) == ES09ResultAction::Lobby);
  TestTrue("board V back", View.OnKey(ES09ResultKey::V) == ES09ResultAction::ToggleBoard);

  // ---- back to the results: the crossfade only, no second intro ----
  TestTrue("to the results", View.ToggleBoard(300000));
  TestEqual("back start", View.ResultsAlpha(300000), 0.0f);
  TestEqual("back done in 250 ms (no 500 ms intro)", View.ResultsAlpha(300000 + FS09ResultView::CrossfadeMs), 1.0f);
  TestEqual("bar gone", View.BoardBarAlpha(300250), 0.0f);
  // ---- a toggle mid-fade starts from where the modal stands ----
  View.ToggleBoard(400000);
  View.ToggleBoard(400100);  // the modal stood at 0.6
  TestTrue("mid-fade from 0.6", FMath::IsNearlyEqual(View.ResultsAlpha(400100), 0.6f, 1e-4f));
  TestEqual("mid-fade done", View.ResultsAlpha(400350), 1.0f);
  TestEqual("toggles counted", View.Toggles(), 4);

  View.Reset();
  TestFalse("reset hides", View.IsOpen());
  TestEqual("reset alpha", View.ResultsAlpha(400350), 0.0f);
  return true;
}

#endif // WITH_AUTOMATION_TESTS

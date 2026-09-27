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
#if WITH_AUTOMATION_TESTS

#include "S09HudModel.h"
#include "S09ManeuverUi.h"
#include "../S08/S08BoardModel.h"
#include "../S08/S08Contracts.h"
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
  };
  PhaseBlocked(TEXT("COMBAT"));
  PhaseBlocked(TEXT("COMBAT_RESOLVE"));
  PhaseBlocked(TEXT("SETUP"));
  PhaseBlocked(TEXT("PLACEMENT"));
  PhaseBlocked(TEXT("TURN_START"));
  PhaseBlocked(TEXT("TURN_END"));

  // Legal action phases: the gate opens (the leg goes in flight against the
  // dead test port - the send itself is the point).
  {
    FS08Snapshot Snap = Base;
    Snap.Phase = TEXT("ACTION_MANEUVER");
    Snap.SequenceNumber = Flow.GetAppliedSnapshot().SequenceNumber + 1;
    Flow.ApplySnapshot(Snap);
    Traces.Reset();
    Flow.EndTurn();
    TestFalse("endTurn not blocked in ACTION_MANEUVER",
              Traces.ContainsByPredicate([](const FString& Line) {
                return Line.Contains(TEXT("ENDTURN blocked"));
              }));
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

#endif // WITH_AUTOMATION_TESTS

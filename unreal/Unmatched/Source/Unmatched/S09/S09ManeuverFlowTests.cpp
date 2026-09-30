// GD-033 automation tests: command-state machine transitions over the real
// captured board (fixture 04: 20x20 Medusa board, host
// cmugykjjb0000wi9w2nq4qlkj). Covers duplicate-begin gating, zero-move,
// multi-fighter, boost of a hand instance, unreachable rejection, local
// cancel semantics and the exact-count discard draft. Run headless:
//   UnrealEditor-Cmd.exe Unmatched.uproject -ExecCmds="Automation RunTests Unmatched.S09; Quit"
//     -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S09ManeuverUi.h"
#include "S09HudModel.h"
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
const TCHAR* HostId = TEXT("cmugykjjb0000wi9w2nq4qlkj");
const TCHAR* GuestId = TEXT("cmugykjkr0007wi9w2i4f209d");

struct FS09Fixture {
  FS08Snapshot Snapshot;
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  bool bLoaded = false;
};

bool LoadFixture(FS09Fixture& Out) {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S08Fixtures="), Dir) || Dir.IsEmpty()) {
    Dir = FPaths::Combine(FPaths::ProjectDir(),
                          TEXT("../../docs/game-design/evidence/S08/fixtures"));
  }
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *FPaths::Combine(Dir, TEXT("04-game-state-query-host.json")))) {
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
  FString RawState;
  FS08GraphQLError Error;
  if (!FS08Contracts::ParseGameStateQuery(Body, Out.Snapshot, RawState, Error)) return false;
  if (!FS08BoardModel::DecodeFighters(Out.Snapshot.Fighters, Out.Fighters)) return false;
  return Out.Board.Decode(Out.Snapshot.BoardState);
}

// Clones the snapshot metadata with metadata.pendingManeuver set (server form
// after beginManeuver committed the draw).
void WithPendingManeuver(FS08Snapshot& Snapshot, const FString& PlayerId,
                         const FString& ManeuverId) {
  const TSharedRef<FJsonObject> Meta =
      MakeShared<FJsonObject>(*(Snapshot.Metadata->AsObject()));
  const TSharedRef<FJsonObject> Pending = MakeShared<FJsonObject>();
  Pending->SetStringField(TEXT("id"), ManeuverId);
  Pending->SetStringField(TEXT("playerId"), PlayerId);
  Meta->SetObjectField(TEXT("pendingManeuver"), Pending);
  Snapshot.Metadata = MakeShared<FJsonValueObject>(Meta);
}

void WithPendingDiscard(FS08Snapshot& Snapshot, const FString& PlayerId, int32 Count) {
  const TSharedRef<FJsonObject> Meta =
      MakeShared<FJsonObject>(*(Snapshot.Metadata->AsObject()));
  const TSharedRef<FJsonObject> Pending = MakeShared<FJsonObject>();
  Pending->SetStringField(TEXT("id"), TEXT("discard:1:9"));
  Pending->SetStringField(TEXT("playerId"), PlayerId);
  Pending->SetNumberField(TEXT("count"), Count);
  Meta->SetObjectField(TEXT("pendingHandDiscard"), Pending);
  Snapshot.Metadata = MakeShared<FJsonValueObject>(Meta);
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

const FS08BoardFighter* OwnHero(const FS09Fixture& F) {
  for (const FS08BoardFighter& Entry : F.Fighters) {
    if (Entry.OwnerId == HostId && Entry.bIsHero && Entry.IsAlive()) return &Entry;
  }
  return nullptr;
}
const FS08BoardFighter* OwnSidekick(const FS09Fixture& F) {
  for (const FS08BoardFighter& Entry : F.Fighters) {
    if (Entry.OwnerId == HostId && !Entry.bIsHero && Entry.IsAlive()) return &Entry;
  }
  return nullptr;
}
} // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09BeginGateTest,
    "Unmatched.S09.CMD begin gate: legal start, duplicate blocked while pending, not-your-turn rejected",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09BeginGateTest::RunTest(const FString&) {
  FS09Fixture F;
  if (!LoadFixture(F)) { AddError("fixture 04 not loaded"); return true; }
  FS09CommandUi Ui;
  Ui.ViewerId = HostId;
  FString Reason;
  // Clean board state: begin is legal for the host on their ACTION_MANEUVER.
  Ui.OnSnapshot(F.Snapshot, F.Board, F.Fighters);
  TestTrue("begin legal on clean turn", Ui.CanBeginManeuver(F.Snapshot, Reason));

  // begin committed -> draft opens -> a SECOND begin must never be sent.
  FS08Snapshot WithPending = F.Snapshot;
  WithPendingManeuver(WithPending, HostId, TEXT("maneuver:1:5"));
  TestTrue("mode changed to draft", Ui.OnSnapshot(WithPending, F.Board, F.Fighters));
  TestTrue("draft open", Ui.Mode == ES09CommandMode::ManeuverDraft);
  TestFalse("duplicate begin blocked", Ui.CanBeginManeuver(WithPending, Reason));
  TestTrue("reason explains committed draw", Reason.Contains(TEXT("already open")));

  // Opponent seat: never legal on the host's turn.
  FS09CommandUi GuestUi;
  GuestUi.ViewerId = GuestId;
  GuestUi.OnSnapshot(F.Snapshot, F.Board, F.Fighters);
  TestFalse("guest cannot begin on host turn", GuestUi.CanBeginManeuver(F.Snapshot, Reason));
  TestTrue("reason names turn ownership", Reason.Contains(TEXT("not your turn")));

  // In-flight gate.
  FS09CommandUi FlightUi;
  FlightUi.ViewerId = HostId;
  FlightUi.bCommandInFlight = true;
  FlightUi.OnSnapshot(F.Snapshot, F.Board, F.Fighters);
  TestFalse("begin blocked while in flight", FlightUi.CanBeginManeuver(F.Snapshot, Reason));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09ZeroMoveTest,
    "Unmatched.S09.CMD zero-move: confirm with no drafted moves is legal (ACC-006)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09ZeroMoveTest::RunTest(const FString&) {
  FS09Fixture F;
  if (!LoadFixture(F)) { AddError("fixture 04 not loaded"); return true; }
  FS09CommandUi Ui;
  Ui.ViewerId = HostId;
  FS08Snapshot WithPending = F.Snapshot;
  WithPendingManeuver(WithPending, HostId, TEXT("maneuver:1:5"));
  Ui.OnSnapshot(WithPending, F.Board, F.Fighters);

  FS09ManeuverCommand Command;
  FString Reason;
  TestTrue("zero-move confirm legal", Ui.ConfirmManeuver(WithPending, F.Board, F.Fighters,
                                                         Command, Reason));
  TestEqual("command carries the pending id", Command.ManeuverId, TEXT("maneuver:1:5"));
  TestEqual("zero moves", Command.Moves.Num(), 0);
  TestTrue("no boost", Command.BoostCardId.IsEmpty());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09BoostNewCardTest,
    "Unmatched.S09.CMD boost: exact hand instance toggles, hidden/foreign ids rejected",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09BoostNewCardTest::RunTest(const FString&) {
  FS09Fixture F;
  if (!LoadFixture(F)) { AddError("fixture 04 not loaded"); return true; }
  FS09CommandUi Ui;
  Ui.ViewerId = HostId;
  FS08Snapshot WithPending = F.Snapshot;
  WithPendingManeuver(WithPending, HostId, TEXT("maneuver:1:5"));
  Ui.OnSnapshot(WithPending, F.Board, F.Fighters);

  // The freshly drawn card shape: a card NOT in the previous hand is legal -
  // simulate by using the first real hand instance (any hand card is legal
  // per the backend validator, including the begin-drawn one).
  FString FirstOwnId;
  {
    const TSharedPtr<FJsonObject> Hands = WithPending.HandZones->AsObject();
    const TSharedPtr<FJsonValue> HandValue = Hands->TryGetField(HostId);
    const TSharedPtr<FJsonObject> Hand = HandValue.IsValid() ? HandValue->AsObject() : nullptr;
    const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
    if (Hand.IsValid() && Hand->TryGetArrayField(TEXT("cards"), Cards) &&
        Cards && Cards->Num() > 0) {
      FirstOwnId = (*Cards)[0]->AsObject()->GetStringField(TEXT("id"));
    }
  }
  TestTrue("own hand id extracted", !FirstOwnId.IsEmpty());

  FString Reason;
  TestTrue("boost set to exact instance", Ui.ToggleBoostCard(FirstOwnId, WithPending, Reason));
  TestEqual("boost stored", Ui.BoostCardId, FirstOwnId);
  TestTrue("boost toggled off", Ui.ToggleBoostCard(FirstOwnId, WithPending, Reason));
  TestTrue("boost cleared", Ui.BoostCardId.IsEmpty());

  TestFalse("hidden placeholder rejected", Ui.ToggleBoostCard(TEXT("hidden-0"), WithPending, Reason));
  TestTrue("reason demands exact instance", Reason.Contains(TEXT("exact card instance")));
  TestFalse("foreign id rejected", Ui.ToggleBoostCard(TEXT("nope::9"), WithPending, Reason));

  // Boost outside a draft is refused.
  FS09CommandUi Closed;
  Closed.ViewerId = HostId;
  Closed.OnSnapshot(F.Snapshot, F.Board, F.Fighters);
  TestFalse("boost outside draft refused", Closed.ToggleBoostCard(FirstOwnId, F.Snapshot, Reason));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MultiFighterTest,
    "Unmatched.S09.CMD multi-fighter: hero + sidekick drafted, confirm builds both paths",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MultiFighterTest::RunTest(const FString&) {
  FS09Fixture F;
  if (!LoadFixture(F)) { AddError("fixture 04 not loaded"); return true; }
  const FS08BoardFighter* Hero = OwnHero(F);
  const FS08BoardFighter* Sidekick = OwnSidekick(F);
  if (!Hero || !Sidekick) { AddError("host hero/sidekick missing"); return true; }

  FS09CommandUi Ui;
  Ui.ViewerId = HostId;
  FS08Snapshot WithPending = F.Snapshot;
  WithPendingManeuver(WithPending, HostId, TEXT("maneuver:1:5"));
  Ui.OnSnapshot(WithPending, F.Board, F.Fighters);

  FString Reason;
  TestTrue("hero selectable", Ui.SelectFighter(Hero->Id, WithPending, F.Board, F.Fighters));
  TestTrue("hero one step drafted",
           Ui.SetDestination(Hero->Id, Hero->X + 1, Hero->Y, WithPending, F.Board, F.Fighters,
                             Reason));
  TestTrue("sidekick selectable", Ui.SelectFighter(Sidekick->Id, WithPending, F.Board, F.Fighters));
  // f-0-sk0 sits at (1,2); +X is the hero's cell, so draft WEST instead.
  TestTrue("sidekick one step drafted",
           Ui.SetDestination(Sidekick->Id, Sidekick->X - 1, Sidekick->Y, WithPending, F.Board,
                             F.Fighters, Reason));
  TestEqual("two drafted moves", Ui.Moves.Num(), 2);

  FS09ManeuverCommand Command;
  TestTrue("multi-fighter confirm legal",
           Ui.ConfirmManeuver(WithPending, F.Board, F.Fighters, Command, Reason));
  TestEqual("command carries two moves", Command.Moves.Num(), 2);
  bool bHeroPath = false, bSidekickPath = false;
  for (const FS08ManeuverMove& Move : Command.Moves) {
    if (Move.FighterId == Hero->Id) bHeroPath = Move.Path.Num() == 1;
    if (Move.FighterId == Sidekick->Id) bSidekickPath = Move.Path.Num() == 1;
  }
  TestTrue("hero path is exactly one orthogonal step", bHeroPath);
  TestTrue("sidekick path is exactly one orthogonal step", bSidekickPath);

  // Clearing one move keeps the other.
  Ui.ClearMove(Sidekick->Id);
  TestEqual("sidekick move cleared", Ui.Moves.Num(), 1);
  TestEqual("hero move kept", Ui.Moves[0].FighterId, Hero->Id);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09DestinationRulesTest,
    "Unmatched.S09.CMD destinations: unreachable rejected with reason, same-cell conflict caught",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09DestinationRulesTest::RunTest(const FString&) {
  FS09Fixture F;
  if (!LoadFixture(F)) { AddError("fixture 04 not loaded"); return true; }
  const FS08BoardFighter* Hero = OwnHero(F);
  if (!Hero) { AddError("host hero missing"); return true; }
  FS09CommandUi Ui;
  Ui.ViewerId = HostId;
  FS08Snapshot WithPending = F.Snapshot;
  WithPendingManeuver(WithPending, HostId, TEXT("maneuver:1:5"));
  Ui.OnSnapshot(WithPending, F.Board, F.Fighters);

  FString Reason;
  TestFalse("far cell rejected",
            Ui.SetDestination(Hero->Id, 19, 19, WithPending, F.Board, F.Fighters, Reason));
  TestTrue("reason names movement allowance", Reason.Contains(TEXT("exceeds movement")));
  TestFalse("enemy fighter rejected as mover",
            Ui.SetDestination(TEXT("f-1-hero"), 5, 5, WithPending, F.Board, F.Fighters, Reason));

  // Two fighters drafted onto the SAME cell: local catch before the server.
  // Draft each onto its own legal neighbor first, then force the second
  // destination onto the first one's cell (server applies moves sequentially
  // and would reject the occupied cell).
  const FS08BoardFighter* Sidekick = OwnSidekick(F);
  if (!Sidekick) { AddError("sidekick missing"); return true; }
  Ui.Moves.Reset();
  auto DraftNeighbor = [&](const FString& FighterId) -> bool {
    static const int32 Dx[4] = {1, -1, 0, 0};
    static const int32 Dy[4] = {0, 0, 1, -1};
    const FS08BoardFighter* Fighter = nullptr;
    for (const FS08BoardFighter& Entry : F.Fighters) {
      if (Entry.Id == FighterId) Fighter = &Entry;
    }
    if (!Fighter) return false;
    for (int32 Dir = 0; Dir < 4; ++Dir) {
      if (Ui.SetDestination(FighterId, Fighter->X + Dx[Dir], Fighter->Y + Dy[Dir],
                            WithPending, F.Board, F.Fighters, Reason)) {
        return true;
      }
    }
    return false;
  };
  TestTrue("hero drafted onto a legal neighbor", DraftNeighbor(Hero->Id));
  TestTrue("sidekick drafted onto a legal neighbor", DraftNeighbor(Sidekick->Id));
  TestEqual("two moves drafted", Ui.Moves.Num(), 2);
  const int32 ConflictX = Ui.Moves[0].DestX;
  const int32 ConflictY = Ui.Moves[0].DestY;
  Ui.Moves[1].DestX = ConflictX;
  Ui.Moves[1].DestY = ConflictY;
  FS09ManeuverCommand Command;
  TestFalse("confirm catches same-cell conflict",
            Ui.ConfirmManeuver(WithPending, F.Board, F.Fighters, Command, Reason));
  TestTrue("reason names the shared cell", Reason.Contains(TEXT("same cell")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CancelKeepsPendingTest,
    "Unmatched.S09.CMD cancel is local-only: pending survives, begin stays blocked, resume works",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CancelKeepsPendingTest::RunTest(const FString&) {
  FS09Fixture F;
  if (!LoadFixture(F)) { AddError("fixture 04 not loaded"); return true; }
  const FS08BoardFighter* Hero = OwnHero(F);
  if (!Hero) { AddError("host hero missing"); return true; }
  FS09CommandUi Ui;
  Ui.ViewerId = HostId;
  FS08Snapshot WithPending = F.Snapshot;
  WithPendingManeuver(WithPending, HostId, TEXT("maneuver:1:5"));
  Ui.OnSnapshot(WithPending, F.Board, F.Fighters);
  FString Reason;
  Ui.SelectFighter(Hero->Id, WithPending, F.Board, F.Fighters);
  Ui.SetDestination(Hero->Id, Hero->X + 1, Hero->Y, WithPending, F.Board, F.Fighters, Reason);
  TestEqual("move drafted", Ui.Moves.Num(), 1);

  Ui.CancelDraft();
  TestEqual("moves cleared locally", Ui.Moves.Num(), 0);
  TestTrue("boost cleared", Ui.BoostCardId.IsEmpty());
  TestTrue("draft still open (pending lives)",
           Ui.Mode == ES09CommandMode::ManeuverDraft);
  TestTrue("resumable", Ui.CanResumeManeuver(WithPending));
  TestFalse("second begin still blocked", Ui.CanBeginManeuver(WithPending, Reason));

  // Resume: the same pending id accepts a fresh draft.
  TestTrue("resume re-selects fighter",
           Ui.SelectFighter(Hero->Id, WithPending, F.Board, F.Fighters));
  FS09ManeuverCommand Command;
  TestTrue("resume confirms zero-move against same pending",
           Ui.ConfirmManeuver(WithPending, F.Board, F.Fighters, Command, Reason));
  TestEqual("same pending id", Command.ManeuverId, TEXT("maneuver:1:5"));

  // Server clears the pending -> draft closes and state resets.
  Ui.OnSnapshot(F.Snapshot, F.Board, F.Fighters);
  TestTrue("mode closed after resolve", Ui.Mode == ES09CommandMode::None);
  TestTrue("begin legal again", Ui.CanBeginManeuver(F.Snapshot, Reason));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09DiscardExactCountTest,
    "Unmatched.S09.CMD discard: exactly count unique own ids, foreign/hidden rejected, over-select gated",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09DiscardExactCountTest::RunTest(const FString&) {
  FS09Fixture F;
  if (!LoadFixture(F)) { AddError("fixture 04 not loaded"); return true; }
  FS09CommandUi Ui;
  Ui.ViewerId = HostId;
  FS08Snapshot WithDiscard = F.Snapshot;
  WithPendingDiscard(WithDiscard, HostId, 2);
  TestTrue("discard draft opens", Ui.OnSnapshot(WithDiscard, F.Board, F.Fighters));
  TestTrue("mode is discard", Ui.Mode == ES09CommandMode::DiscardDraft);

  TArray<FString> Hand;
  {
    const TSharedPtr<FJsonObject> Hands = WithDiscard.HandZones->AsObject();
    const TSharedPtr<FJsonValue> HandValue = Hands->TryGetField(HostId);
    const TSharedPtr<FJsonObject> HandObject =
        HandValue.IsValid() ? HandValue->AsObject() : nullptr;
    const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
    if (HandObject.IsValid() && HandObject->TryGetArrayField(TEXT("cards"), Cards)) {
      for (const TSharedPtr<FJsonValue>& Card : *Cards) {
        Hand.Add(Card->AsObject()->GetStringField(TEXT("id")));
      }
    }
  }
  TestEqual("host hand loaded", Hand.Num(), 5);

  FString Reason;
  TestFalse("hidden placeholder not discardable",
            Ui.ToggleDiscardCard(TEXT("hidden-0"), WithDiscard, Reason));
  TestFalse("foreign id not discardable",
            Ui.ToggleDiscardCard(TEXT("nope::9"), WithDiscard, Reason));

  FS09DiscardCommand Command;
  TestFalse("confirm under-count rejected",
            Ui.ConfirmDiscard(WithDiscard, Command, Reason));
  TestTrue("under-count reason demands exactly", Reason.Contains(TEXT("exactly 2")));

  TestTrue("first pick", Ui.ToggleDiscardCard(Hand[0], WithDiscard, Reason));
  TestTrue("second pick", Ui.ToggleDiscardCard(Hand[1], WithDiscard, Reason));
  TestFalse("third pick gated at count",
            Ui.ToggleDiscardCard(Hand[2], WithDiscard, Reason));
  TestTrue("gate reason names the excess count", Reason.Contains(TEXT("excess")));
  TestEqual("remaining zero", Ui.DiscardRemaining(), 0);

  TestTrue("confirm at exact count", Ui.ConfirmDiscard(WithDiscard, Command, Reason));
  TestEqual("command count", Command.CardInstanceIds.Num(), 2);
  TestTrue("pending id carried", Command.PendingId == TEXT("discard:1:9"));
  TSet<FString> Unique(Command.CardInstanceIds);
  TestEqual("ids unique", Unique.Num(), 2);
  TestTrue("ids are exact hand members",
           Unique.Contains(Hand[0]) && Unique.Contains(Hand[1]));

  // Deselect one -> confirm is blocked again (exact count is a hard gate).
  Ui.ToggleDiscardCard(Hand[0], WithDiscard, Reason);
  TestFalse("confirm after deselect rejected",
            Ui.ConfirmDiscard(WithDiscard, Command, Reason));

  // In-flight gate.
  Ui.ToggleDiscardCard(Hand[0], WithDiscard, Reason);
  Ui.bCommandInFlight = true;
  TestFalse("confirm blocked while in flight",
            Ui.ConfirmDiscard(WithDiscard, Command, Reason));
  return true;
}
// Pins the packaged-demo regression (GD-033): after beginManeuver the same
// post-begin state arrives again over BOTH channels (WS push + HTTP refetch
// merge). The draft-open guard in S08FlowGameMode keeps the previous-hand
// baseline unchanged while a draft is open, so the freshly drawn instance
// stays *new* on every re-apply and remains the exact boost pick. Without the
// guard the first re-apply absorbed the drawn card into the baseline and the
// boost pick silently lost its target before the confirm.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09SameSeqReapplyBoostTest,
    "Unmatched.S09.CMD regression: same-seq reapply keeps drawn card new and boostable exactly once",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09SameSeqReapplyBoostTest::RunTest(const FString&) {
  FS09Fixture F;
  if (!LoadFixture(F)) { AddError("fixture 04 not loaded"); return true; }

  // Quiet-state baseline: own hand 5, recorded as the previous-hand set.
  FS09HudModel Before;
  Before.Build(F.Snapshot, HostId, TSet<FString>(), F.Snapshot.SequenceNumber,
               F.Snapshot.SequenceNumber);
  const FS09PlayerPanel* BeforeOwn = Before.ViewerPanel();
  if (!BeforeOwn || BeforeOwn->Cards.Num() != 5) {
    AddError("baseline hand is not 5 cards");
    return true;
  }
  TSet<FString> PreviousIds;
  for (const FS09CardView& Card : BeforeOwn->Cards) PreviousIds.Add(Card.InstanceId);

  // beginManeuver committed on the server: hand grows 5 -> 6 with a NEW
  // instance id and metadata.pendingManeuver opens.
  FS08Snapshot AfterBegin = F.Snapshot;
  WithPendingManeuver(AfterBegin, HostId, TEXT("maneuver:1:5"));
  const FString DrawnId(TEXT("drawn-new::9"));
  {
    const TSharedRef<FJsonObject> Hands =
        MakeShared<FJsonObject>(*AfterBegin.HandZones->AsObject());
    const TSharedPtr<FJsonValue> HandValue = Hands->TryGetField(HostId);
    const TSharedPtr<FJsonObject> Hand = HandValue.IsValid() ? HandValue->AsObject() : nullptr;
    if (!Hand.IsValid()) { AddError("host hand missing"); return true; }
    const TSharedRef<FJsonObject> NewHand = MakeShared<FJsonObject>(*Hand);
    const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
    if (!NewHand->TryGetArrayField(TEXT("cards"), Cards) || !Cards || Cards->Num() != 5) {
      AddError("fixture hand is not 5 cards");
      return true;
    }
    TArray<TSharedPtr<FJsonValue>> Grown = *Cards;
    const TSharedRef<FJsonObject> Drawn = MakeShared<FJsonObject>(*Grown[0]->AsObject());
    Drawn->SetStringField(TEXT("id"), DrawnId);
    Grown.Add(MakeShared<FJsonValueObject>(Drawn));
    NewHand->SetArrayField(TEXT("cards"), Grown);
    Hands->SetObjectField(HostId, NewHand);
    AfterBegin.HandZones = MakeShared<FJsonValueObject>(Hands);
  }

  // The SAME state applied three times (first apply + WS push + HTTP refetch
  // merge): the baseline must not absorb the drawn card while the draft is
  // open - exactly one bNew, and it is the drawn instance, every time.
  for (int32 Apply = 1; Apply <= 3; ++Apply) {
    FS09HudModel Hud;
    Hud.Build(AfterBegin, HostId, PreviousIds, AfterBegin.SequenceNumber,
              AfterBegin.SequenceNumber);
    const FS09PlayerPanel* Own = Hud.ViewerPanel();
    if (!Own) { AddError("viewer panel missing"); return true; }
    TestEqual(*FString::Printf(TEXT("apply %d: hand grew to 6"), Apply),
              Own->Cards.Num(), 6);
    int32 NewCount = 0;
    const FS09CardView* NewCard = nullptr;
    for (const FS09CardView& Card : Own->Cards) {
      if (Card.bNew) { ++NewCount; NewCard = &Card; }
    }
    TestEqual(*FString::Printf(TEXT("apply %d: exactly one bNew"), Apply), NewCount, 1);
    if (NewCard) {
      TestEqual(*FString::Printf(TEXT("apply %d: bNew is the drawn instance"), Apply),
                NewCard->InstanceId, DrawnId);
      TestFalse(*FString::Printf(TEXT("apply %d: drawn card is a real face"), Apply),
                NewCard->bHidden);
    }
  }

  // Command machine across the same re-applies: the exact drawn instance is
  // boostable, the boost survives the merged re-apply, and the confirmed
  // zero-move command carries that instance exactly once.
  FS09CommandUi Ui;
  Ui.ViewerId = HostId;
  TestTrue("draft opens on the post-begin state",
           Ui.OnSnapshot(AfterBegin, F.Board, F.Fighters));
  FString Reason;
  TestTrue("drawn instance is boostable", Ui.ToggleBoostCard(DrawnId, AfterBegin, Reason));
  TestEqual("boost set to the exact drawn instance", Ui.BoostCardId, DrawnId);
  TestFalse("merged re-apply is not a mode change",
            Ui.OnSnapshot(AfterBegin, F.Board, F.Fighters));
  TestTrue("draft still open after the re-apply",
           Ui.Mode == ES09CommandMode::ManeuverDraft);
  TestEqual("boost survives the re-apply", Ui.BoostCardId, DrawnId);
  FS09ManeuverCommand Command;
  TestTrue("zero-move boost confirm is legal",
           Ui.ConfirmManeuver(AfterBegin, F.Board, F.Fighters, Command, Reason));
  TestEqual("command carries the drawn instance once", Command.BoostCardId, DrawnId);
  TestEqual("zero moves drafted", Command.Moves.Num(), 0);
  int32 FighterMisuse = 0;
  for (const FS08ManeuverMove& Move : Command.Moves) {
    if (Move.FighterId == DrawnId) ++FighterMisuse;
  }
  TestEqual("drawn id never used as a fighter", FighterMisuse, 0);
  return true;
}

// GD-032 adversarial rework: a double Enter (or double confirm click) before
// the HTTP response used to fire TWO discardToLimit / maneuver mutations
// against the same pending id - the second always fails spuriously. The
// controller gate must reject the duplicate LOCALLY, before any mutation is
// constructed, while the TURN_END discard stays legal after the turn flipped
// (no turn-owner gate on it). Observed through the controller's public
// OnTrace diagnostics; the dead port keeps the first leg in flight for the
// whole synchronous test, exactly like a slow network.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09DoubleFireGateTest,
    "Unmatched.S09.CMD double-fire gate: duplicate discard/submit blocked in flight; TURN_END discard survives turn flip",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09DoubleFireGateTest::RunTest(const FString&) {
  FS09Fixture F;
  if (!LoadFixture(F)) { AddError("fixture 04 not loaded"); return true; }

  // TURN_END discard: the turn already flipped to the guest, the pending
  // discard head belongs to the host (viewer).
  FS08Snapshot DiscardSnap = F.Snapshot;
  DiscardSnap.CurrentTurnPlayerId = GuestId;
  WithPendingDiscard(DiscardSnap, HostId, 2);

  FS08FlowController Flow(TEXT("http://127.0.0.1:9/graphql"),
                          TEXT("ws://127.0.0.1:9/graphql"), HostId);
  TArray<FString> Traces;
  Flow.OnTrace.AddLambda([&Traces](const FString& Line) { Traces.Add(Line); });
  Flow.AttachStreamHarnessForTest(TEXT("gate-game"));
  Flow.ApplySnapshot(DiscardSnap);
  auto Count = [&Traces](const FString& Needle) {
    int32 N = 0;
    for (const FString& Line : Traces) {
      if (Line.Contains(Needle)) ++N;
    }
    return N;
  };

  // Sol6 review P1(3): the gameplay gate demands a PROVEN-live operation -
  // the harness subscribe alone leaves IsStreamReady closed, so the duplicate
  // assertions below could never run. Deliver the subscription's first
  // 'next' for op s08-1 at the SAME seq/phase/turn owner as the applied
  // baseline (a barrier merge: no state change).
  TestFalse("harness alone does not open the command gate", Flow.IsStreamReady());
  Flow.InjectWsFrameForTest(BarrierNextFrame(Flow.GetAppliedSnapshot()));
  TestTrue("first delivered frame proves the stream live", Flow.IsStreamReady());
  TestEqual("no HTTP leg sent yet", Flow.GetTestHttpSendCountForTest(), 0);

  // The leg must stay in flight WITHOUT a real socket: a real POST to the dead
  // port answers ~2 s later (Windows connect-refused retries) into a controller
  // this test already destroyed (DiscardToLimit captures `this`), a use-after-
  // free when later tests keep the process running (S08+S09+S10 in one run).
  // A deferred harness answer is never delivered and dies with the controller.
  Flow.QueueHttpResultForTest(false, {}, /*bDeferDelivery=*/true);
  const TArray<FString> Cards = {TEXT("card::1"), TEXT("card::2")};
  TestTrue("first discard dispatched", Flow.DiscardToLimit(TEXT("discard:1:9"), Cards));
  TestEqual("first discard passes the gate (no block)", Count(TEXT("DISCARD blocked")), 0);
  TestEqual("first discard: exactly one HTTP leg", Flow.GetTestHttpSendCountForTest(), 1);
  TestTrue("discard leg is in flight", Flow.IsManeuverInFlight());
  Flow.DiscardToLimit(TEXT("discard:1:9"), Cards);
  TestEqual("duplicate discard: no extra HTTP leg", Flow.GetTestHttpSendCountForTest(), 1);
  TestEqual("double Enter blocked exactly once",
            Count(TEXT("DISCARD blocked: a command is already in flight")), 1);
  TestEqual("no other block reason invented", Count(TEXT("DISCARD blocked")), 1);

  // Same defect class on the maneuver submit leg (separate controller: the
  // discard leg above stays in flight on its deferred harness answer).
  FS08Snapshot ManeuverSnap = F.Snapshot;
  WithPendingManeuver(ManeuverSnap, HostId, TEXT("maneuver-1"));
  FS08FlowController Flow2(TEXT("http://127.0.0.1:9/graphql"),
                           TEXT("ws://127.0.0.1:9/graphql"), HostId);
  Traces.Reset();
  Flow2.OnTrace.AddLambda([&Traces](const FString& Line) { Traces.Add(Line); });
  Flow2.AttachStreamHarnessForTest(TEXT("gate-game"));
  Flow2.ApplySnapshot(ManeuverSnap);
  TestFalse("harness alone does not open the submit gate", Flow2.IsStreamReady());
  Flow2.InjectWsFrameForTest(BarrierNextFrame(Flow2.GetAppliedSnapshot()));
  TestTrue("first delivered frame proves the submit stream live", Flow2.IsStreamReady());
  TestEqual("no HTTP leg sent yet (submit controller)", Flow2.GetTestHttpSendCountForTest(), 0);
  const TArray<FS08ManeuverMove> NoMoves;
  Flow2.QueueHttpResultForTest(false, {}, /*bDeferDelivery=*/true); // same: no real POST
  TestTrue("first submit dispatched", Flow2.SubmitManeuver(TEXT("maneuver-1"), NoMoves));
  TestEqual("first submit passes the gate", Count(TEXT("MANEUVER submit blocked")), 0);
  TestEqual("first submit: exactly one HTTP leg", Flow2.GetTestHttpSendCountForTest(), 1);
  TestTrue("submit leg is in flight", Flow2.IsManeuverInFlight());
  Flow2.SubmitManeuver(TEXT("maneuver-1"), NoMoves);
  TestEqual("duplicate confirm: no extra HTTP leg", Flow2.GetTestHttpSendCountForTest(), 1);
  TestEqual("double confirm blocked exactly once",
            Count(TEXT("MANEUVER submit blocked: a command is already in flight")), 1);
  return true;
}
#endif

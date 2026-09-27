// S09 UX automation tests: the explicit EXACT-INSTANCE scheme picker
// (ES09CommandMode::SchemeChoice). Regression guard for the review-critical
// bug where G silently spent the FIRST playable scheme - with two legal
// schemes the wrong card/action was spent. Covers: two legal schemes
// (select/switch/confirm returns the EXACT picked id), invalid picks
// (dead banner / non-SCHEME / hidden / foreign), stale-selection confirm
// (rejected - NEVER substituted with another playable scheme), cancel,
// snapshot-driven staleness (turn ended / card left hand) and the open
// gate (turn/phase/pending/in-flight). Run headless:
//   UnrealEditor-Cmd.exe Unmatched.uproject -ExecCmds="Automation RunTests Unmatched.S09.SCHEME; Quit"
//     -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S09ManeuverUi.h"
#include "S09HudModel.h"
#include "../S08/S08BoardModel.h"
#include "../S08/S08Contracts.h"
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

struct FS09SchemeFixture {
  FS08Snapshot Snapshot;
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  bool bLoaded = false;
};

bool LoadSchemeFixture(FS09SchemeFixture& Out) {
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

// Replaces the host hand with synthetic entries (clone of a real card with
// id/name/type/banner overridden). nullptr = keep the card out (omitted).
void SetSchemeHand(FS08Snapshot& Snapshot, const TArray<TTuple<FString, FString, FString, FString>>& Entries) {
  // (id, name, cardType, bannerName)
  const TSharedRef<FJsonObject> Hands =
      MakeShared<FJsonObject>(*(Snapshot.HandZones->AsObject()));
  const TSharedPtr<FJsonValue> HandValue = Hands->TryGetField(HostId);
  const TSharedPtr<FJsonObject> Hand = HandValue.IsValid() ? HandValue->AsObject() : nullptr;
  if (!Hand.IsValid()) return;
  const TSharedRef<FJsonObject> NewHand = MakeShared<FJsonObject>(*Hand);
  const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
  if (!NewHand->TryGetArrayField(TEXT("cards"), Cards) || !Cards || Cards->Num() == 0) return;
  TArray<TSharedPtr<FJsonValue>> Rebuilt;
  for (const TTuple<FString, FString, FString, FString>& Entry : Entries) {
    const TSharedRef<FJsonObject> Card = MakeShared<FJsonObject>(*(*Cards)[0]->AsObject());
    Card->SetStringField(TEXT("id"), Entry.Get<0>());
    Card->SetStringField(TEXT("name"), Entry.Get<1>());
    Card->SetStringField(TEXT("cardType"), Entry.Get<2>());
    Card->SetStringField(TEXT("bannerName"), Entry.Get<3>());
    Rebuilt.Add(MakeShared<FJsonValueObject>(Card));
  }
  NewHand->SetArrayField(TEXT("cards"), Rebuilt);
  Hands->SetObjectField(HostId, NewHand);
  Snapshot.HandZones = MakeShared<FJsonValueObject>(Hands);
}

void WithPendingHead(FS08Snapshot& Snapshot) {
  const TSharedRef<FJsonObject> Meta =
      MakeShared<FJsonObject>(*(Snapshot.Metadata->AsObject()));
  const TSharedRef<FJsonObject> Head = MakeShared<FJsonObject>();
  Head->SetStringField(TEXT("id"), TEXT("pe:scheme-test:1"));
  Head->SetStringField(TEXT("playerId"), HostId);
  Head->SetStringField(TEXT("type"), TEXT("BOOST_CHOICE"));
  Head->SetBoolField(TEXT("optional"), true);
  TArray<TSharedPtr<FJsonValue>> Effects;
  Effects.Add(MakeShared<FJsonValueObject>(Head));
  Meta->SetArrayField(TEXT("pendingEffects"), Effects);
  Snapshot.Metadata = MakeShared<FJsonValueObject>(Meta);
}
} // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09SchemeTwoLegalTest,
    "Unmatched.S09.SCHEME two legal schemes: exact-instance select, switch and confirm",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09SchemeTwoLegalTest::RunTest(const FString&) {
  FS09SchemeFixture F;
  if (!LoadSchemeFixture(F)) { AddError("fixture 04 not loaded"); return true; }
  SetSchemeHand(F.Snapshot, {
      {TEXT("sch-any::1"), TEXT("Restless Spirits"), TEXT("SCHEME"), TEXT("")},
      {TEXT("sch-harpy::2"), TEXT("Winged Frenzy"), TEXT("SCHEME"), TEXT("Harpy")},
  });

  FS09CommandUi Ui;
  Ui.ViewerId = HostId;
  Ui.OnSnapshot(F.Snapshot, F.Board, F.Fighters);
  FString Reason;
  TestTrue("open gate legal on own action phase",
           Ui.CanOpenSchemeChoice(F.Snapshot, Reason));
  TestEqual("two legal schemes counted", Ui.CountPlayableSchemes(F.Snapshot, F.Fighters), 2);

  Ui.OpenSchemeChoice();
  TestTrue("picker open", Ui.Mode == ES09CommandMode::SchemeChoice);
  TestTrue("first scheme selected", Ui.ToggleSchemeCard(TEXT("sch-any::1"), F.Snapshot,
                                                        F.Fighters, Reason));
  TestEqual("selection is the exact instance", Ui.SchemeCardId, TEXT("sch-any::1"));
  TestTrue("switch to the second scheme", Ui.ToggleSchemeCard(TEXT("sch-harpy::2"), F.Snapshot,
                                                              F.Fighters, Reason));
  TestEqual("selection switched to the second instance", Ui.SchemeCardId, TEXT("sch-harpy::2"));
  TestTrue("toggle off clears", Ui.ToggleSchemeCard(TEXT("sch-harpy::2"), F.Snapshot,
                                                    F.Fighters, Reason));
  TestTrue("selection cleared", Ui.SchemeCardId.IsEmpty());
  TestTrue("re-select first", Ui.ToggleSchemeCard(TEXT("sch-any::1"), F.Snapshot,
                                                  F.Fighters, Reason));

  FString OutId;
  TestTrue("confirm legal", Ui.ConfirmScheme(F.Snapshot, F.Fighters, OutId, Reason));
  TestEqual("confirm returns the EXACT picked instance (never another card)",
            OutId, TEXT("sch-any::1"));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09SchemeInvalidPicksTest,
    "Unmatched.S09.SCHEME invalid picks: dead banner, non-SCHEME, hidden, foreign rejected",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09SchemeInvalidPicksTest::RunTest(const FString&) {
  FS09SchemeFixture F;
  if (!LoadSchemeFixture(F)) { AddError("fixture 04 not loaded"); return true; }
  // Merlin lives on the GUEST side: a 'Merlin' banner has no living HOST
  // fighter -> server playScheme gate would reject it (dead banner).
  SetSchemeHand(F.Snapshot, {
      {TEXT("sch-any::1"), TEXT("Restless Spirits"), TEXT("SCHEME"), TEXT("")},
      {TEXT("sch-dead::4"), TEXT("Forbidden Lore"), TEXT("SCHEME"), TEXT("Merlin")},
      {TEXT("atk-plain::3"), TEXT("Clutching Claws"), TEXT("VERSATILE"), TEXT("Any")},
  });

  FS09CommandUi Ui;
  Ui.ViewerId = HostId;
  Ui.OnSnapshot(F.Snapshot, F.Board, F.Fighters);
  Ui.OpenSchemeChoice();
  FString Reason;

  TestFalse("dead-banner scheme rejected",
            Ui.ToggleSchemeCard(TEXT("sch-dead::4"), F.Snapshot, F.Fighters, Reason));
  TestTrue("dead-banner reason names the banner gate",
           Reason.Contains(TEXT("living")) && Reason.Contains(TEXT("Merlin")));
  TestFalse("non-SCHEME card rejected",
            Ui.ToggleSchemeCard(TEXT("atk-plain::3"), F.Snapshot, F.Fighters, Reason));
  TestTrue("non-SCHEME reason names the type",
           Reason.Contains(TEXT("VERSATILE")));
  TestFalse("foreign id rejected",
            Ui.ToggleSchemeCard(TEXT("nope::9"), F.Snapshot, F.Fighters, Reason));
  TestFalse("hidden placeholder rejected",
            Ui.ToggleSchemeCard(TEXT("hidden-0"), F.Snapshot, F.Fighters, Reason));
  TestTrue("no selection survived the rejections", Ui.SchemeCardId.IsEmpty());

  FString OutId;
  TestFalse("confirm without a selection rejected",
             Ui.ConfirmScheme(F.Snapshot, F.Fighters, OutId, Reason));
  TestTrue("reason demands a pick", Reason.Contains(TEXT("pick")));
  TestTrue("no id emitted", OutId.IsEmpty());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09SchemeStaleConfirmTest,
    "Unmatched.S09.SCHEME stale confirm: selection that left the hand is rejected, never substituted",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09SchemeStaleConfirmTest::RunTest(const FString&) {
  FS09SchemeFixture F;
  if (!LoadSchemeFixture(F)) { AddError("fixture 04 not loaded"); return true; }
  SetSchemeHand(F.Snapshot, {
      {TEXT("sch-any::1"), TEXT("Restless Spirits"), TEXT("SCHEME"), TEXT("")},
      {TEXT("sch-harpy::2"), TEXT("Winged Frenzy"), TEXT("SCHEME"), TEXT("Harpy")},
  });
  FS09CommandUi Ui;
  Ui.ViewerId = HostId;
  Ui.OnSnapshot(F.Snapshot, F.Board, F.Fighters);
  Ui.OpenSchemeChoice();
  FString Reason;
  TestTrue("pick the first scheme",
           Ui.ToggleSchemeCard(TEXT("sch-any::1"), F.Snapshot, F.Fighters, Reason));

  // The selected card left the hand (spent by another route / drawn state
  // changed): the fresh hand still holds a DIFFERENT legal scheme.
  FS08Snapshot Shrunk = F.Snapshot;
  SetSchemeHand(Shrunk, {
      {TEXT("sch-harpy::2"), TEXT("Winged Frenzy"), TEXT("SCHEME"), TEXT("Harpy")},
  });
  Ui.OnSnapshot(Shrunk, F.Board, F.Fighters);
  TestTrue("picker survives the same-seq re-apply",
           Ui.Mode == ES09CommandMode::SchemeChoice);
  TestTrue("stale selection dropped by the snapshot",
           Ui.SchemeCardId.IsEmpty());

  // Even with a stale id forced back in, confirm MUST reject - it may never
  // fall through to sch-harpy::2 (the wrong-card spend bug).
  Ui.SchemeCardId = TEXT("sch-any::1");
  FString OutId;
  TestFalse("stale confirm rejected", Ui.ConfirmScheme(Shrunk, F.Fighters, OutId, Reason));
  TestTrue("reason reports the stale pick", Reason.Contains(TEXT("no longer in your hand")));
  TestTrue("no substitute id emitted", OutId.IsEmpty());

  // Dead-banner staleness: banner fighter fell while the picker was open.
  TArray<FS08BoardFighter> DeadFighters = F.Fighters;
  for (FS08BoardFighter& Fighter : DeadFighters) {
    if (Fighter.Name.Contains(TEXT("Harpies"))) Fighter.Health = 0;
  }
  Ui.SchemeCardId = TEXT("sch-harpy::2");
  TestFalse("dead-banner confirm rejected",
             Ui.ConfirmScheme(F.Snapshot, DeadFighters, OutId, Reason));
  TestTrue("reason names the dead banner", Reason.Contains(TEXT("living")));
  TestTrue("still no id emitted", OutId.IsEmpty());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09SchemeCancelTest,
    "Unmatched.S09.SCHEME cancel: local-only close sends nothing and clears the pick",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09SchemeCancelTest::RunTest(const FString&) {
  FS09SchemeFixture F;
  if (!LoadSchemeFixture(F)) { AddError("fixture 04 not loaded"); return true; }
  SetSchemeHand(F.Snapshot, {
      {TEXT("sch-any::1"), TEXT("Restless Spirits"), TEXT("SCHEME"), TEXT("")},
  });
  FS09CommandUi Ui;
  Ui.ViewerId = HostId;
  Ui.OnSnapshot(F.Snapshot, F.Board, F.Fighters);
  Ui.OpenSchemeChoice();
  FString Reason;
  TestTrue("pick set", Ui.ToggleSchemeCard(TEXT("sch-any::1"), F.Snapshot, F.Fighters, Reason));

  Ui.CancelSchemeChoice();
  TestTrue("cancel closes the picker", Ui.Mode == ES09CommandMode::None);
  TestTrue("cancel clears the selection", Ui.SchemeCardId.IsEmpty());
  FString OutId;
  TestFalse("confirm after cancel has no picker",
             Ui.ConfirmScheme(F.Snapshot, F.Fighters, OutId, Reason));

  // Cancel is idempotent and touches nothing else.
  Ui.CancelSchemeChoice();
  TestTrue("mode stays None", Ui.Mode == ES09CommandMode::None);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09SchemeSnapshotStaleTest,
    "Unmatched.S09.SCHEME snapshot staleness: turn end / pending open close the picker",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09SchemeSnapshotStaleTest::RunTest(const FString&) {
  FS09SchemeFixture F;
  if (!LoadSchemeFixture(F)) { AddError("fixture 04 not loaded"); return true; }
  SetSchemeHand(F.Snapshot, {
      {TEXT("sch-any::1"), TEXT("Restless Spirits"), TEXT("SCHEME"), TEXT("")},
  });
  FS09CommandUi Ui;
  Ui.ViewerId = HostId;
  Ui.OnSnapshot(F.Snapshot, F.Board, F.Fighters);
  Ui.OpenSchemeChoice();
  FString Reason;
  TestTrue("pick set", Ui.ToggleSchemeCard(TEXT("sch-any::1"), F.Snapshot, F.Fighters, Reason));

  // Turn passes to the opponent: the local picker must close by itself.
  FS08Snapshot OppTurn = F.Snapshot;
  OppTurn.CurrentTurnPlayerId = GuestId;
  TestTrue("mode changed by the snapshot", Ui.OnSnapshot(OppTurn, F.Board, F.Fighters));
  TestTrue("picker closed on turn loss", Ui.Mode == ES09CommandMode::None);
  TestTrue("selection cleared on turn loss", Ui.SchemeCardId.IsEmpty());

  // A viewer-owned pending head outranks the picker.
  Ui.OnSnapshot(F.Snapshot, F.Board, F.Fighters);
  Ui.OpenSchemeChoice();
  TestTrue("pick set again", Ui.ToggleSchemeCard(TEXT("sch-any::1"), F.Snapshot, F.Fighters, Reason));
  FS08Snapshot WithPending = F.Snapshot;
  WithPendingHead(WithPending);
  Ui.OnSnapshot(WithPending, F.Board, F.Fighters);
  TestTrue("pending head takes over the mode",
           Ui.Mode == ES09CommandMode::PendingChoice);
  TestTrue("scheme selection cleared", Ui.SchemeCardId.IsEmpty());

  // Terminal phase closes everything.
  Ui.OnSnapshot(F.Snapshot, F.Board, F.Fighters);
  Ui.OpenSchemeChoice();
  FS08Snapshot Over = F.Snapshot;
  Over.Phase = TEXT("GAME_OVER");
  Ui.OnSnapshot(Over, F.Board, F.Fighters);
  TestTrue("GAME_OVER closes the picker", Ui.Mode == ES09CommandMode::None);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09SchemeOpenGateTest,
    "Unmatched.S09.SCHEME open gate: turn/phase/pending/in-flight/empty-hand",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09SchemeOpenGateTest::RunTest(const FString&) {
  FS09SchemeFixture F;
  if (!LoadSchemeFixture(F)) { AddError("fixture 04 not loaded"); return true; }
  SetSchemeHand(F.Snapshot, {
      {TEXT("sch-any::1"), TEXT("Restless Spirits"), TEXT("SCHEME"), TEXT("")},
  });
  FS09CommandUi Ui;
  Ui.ViewerId = HostId;
  Ui.OnSnapshot(F.Snapshot, F.Board, F.Fighters);
  FString Reason;
  TestTrue("legal on the own action phase", Ui.CanOpenSchemeChoice(F.Snapshot, Reason));

  FS08Snapshot OppTurn = F.Snapshot;
  OppTurn.CurrentTurnPlayerId = GuestId;
  TestFalse("not-your-turn rejected", Ui.CanOpenSchemeChoice(OppTurn, Reason));
  TestTrue("turn reason", Reason.Contains(TEXT("your action phase")));

  FS08Snapshot BadPhase = F.Snapshot;
  BadPhase.Phase = TEXT("TURN_END");
  TestFalse("non-action phase rejected", Ui.CanOpenSchemeChoice(BadPhase, Reason));

  FS08Snapshot Pending = F.Snapshot;
  WithPendingHead(Pending);
  FS09CommandUi PendingUi;
  PendingUi.ViewerId = HostId;
  PendingUi.OnSnapshot(Pending, F.Board, F.Fighters);
  TestFalse("open pending rejected", PendingUi.CanOpenSchemeChoice(Pending, Reason));

  FS09CommandUi Flight;
  Flight.ViewerId = HostId;
  Flight.bCommandInFlight = true;
  Flight.OnSnapshot(F.Snapshot, F.Board, F.Fighters);
  TestFalse("in-flight rejected", Flight.CanOpenSchemeChoice(F.Snapshot, Reason));

  // A busy other mode is rejected (finish the open command first).
  FS09CommandUi Busy;
  Busy.ViewerId = HostId;
  Busy.OnSnapshot(F.Snapshot, F.Board, F.Fighters);
  Busy.Mode = ES09CommandMode::AttackDraft;
  TestFalse("other open command rejected", Busy.CanOpenSchemeChoice(F.Snapshot, Reason));
  TestTrue("reason names the open command", Reason.Contains(TEXT("open command")));

  // No playable scheme in hand: the picker never opens on an empty draft.
  FS08Snapshot NoSchemes = F.Snapshot;
  SetSchemeHand(NoSchemes, {
      {TEXT("atk-plain::3"), TEXT("Clutching Claws"), TEXT("VERSATILE"), TEXT("Any")},
  });
  TestEqual("zero playable schemes", Ui.CountPlayableSchemes(NoSchemes, F.Fighters), 0);
  return true;
}
#endif

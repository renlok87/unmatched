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
#include "S09CardSlot.h"
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

// ---------------------------------------------------------------------------------------------------- DE-026 (W-18)
// The source-card slot and the hand lowering (S09CardSlot.h; 01 F-10, 02 SD-02, SD-26, SD-28 п. 4, SD-54).
namespace {
FS09CardView SlotCard(const TCHAR* Id, const TCHAR* Name, const TCHAR* Type, int32 Boost = -1) {
  FS09CardView Card;
  Card.InstanceId = Id;
  Card.CardId = Id;
  Card.Name = Name;
  Card.CardType = Type;
  if (Boost >= 0) {
    Card.BoostValue = Boost;
    Card.bHasBoostValue = true;
  }
  return Card;
}

FS09HudModel SlotHud(int32 Seq, const TCHAR* Phase, const TArray<FS09CardView>& OwnPile,
                     const TArray<FS09CardView>& OppPile) {
  FS09HudModel Hud;
  Hud.bValid = true;
  Hud.SequenceNumber = Seq;
  Hud.Phase = Phase;
  FS09PlayerPanel Own;
  Own.PlayerId = HostId;
  Own.bIsViewer = true;
  Own.Discard = OwnPile;
  FS09PlayerPanel Opp;
  Opp.PlayerId = GuestId;
  Opp.Discard = OppPile;
  Hud.Panels = {Own, Opp};
  return Hud;
}

FS09SlotCard MakeSlot(ES09SlotRibbon Ribbon, bool bOpponent, int32 Seq) {
  FS09SlotCard Slot;
  Slot.Card = SlotCard(TEXT("c::1"), TEXT("Some Card"),
                       Ribbon == ES09SlotRibbon::Scheme ? TEXT("SCHEME") : TEXT("ATTACK"));
  Slot.OwnerId = bOpponent ? GuestId : HostId;
  Slot.bOpponent = bOpponent;
  Slot.Ribbon = Ribbon;
  Slot.Seq = Seq;
  return Slot;
}

bool LinesContain(const TArray<FString>& Lines, const TCHAR* Needle) {
  for (const FString& Line : Lines) {
    if (Line.Contains(Needle)) return true;
  }
  return false;
}
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09SlotOpponentSchemeHoldTest,
    "Unmatched.S09.SCHEME.Slot opponent scheme: fly 200, hold 1500 before the effect, then leaves with the effect",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09SlotOpponentSchemeHoldTest::RunTest(const FString&) {
  FS09SourceSlot Slot;
  TArray<FString> Lines;
  bool bReleased = false;
  TestTrue("shown", Slot.Show(MakeSlot(ES09SlotRibbon::Scheme, true, 40), 1000, false, Lines, bReleased));
  TestFalse("nothing to release before", bReleased);
  TestTrue("show line: fly 200, hold 1500",
           LinesContain(Lines, TEXT("HUD-SLOT show seq=40 ribbon=scheme owner=opp")) &&
               LinesContain(Lines, TEXT("fly=200 hold=1500")));
  TestTrue("the effect is held", Slot.HoldsEffect());
  TestEqual("held seq", Slot.HeldSeq(), 40);
  TestEqual("release due at arrival + 1500", Slot.ReleaseAtMs(), static_cast<int64>(1000 + 200 + 1500));
  TestEqual("fly starts at 0", Slot.FlyT(1000), 0.0f);
  TestEqual("arrived", Slot.FlyT(1200), 1.0f);
  Lines.Reset();
  Slot.Tick(1200, false, Lines, bReleased);
  TestTrue("hold after the fly", Slot.GetState() == ES09SlotState::Hold);
  Slot.Tick(2699, false, Lines, bReleased);
  TestFalse("1499 ms after arrival: still held", bReleased);
  TestTrue("still held", Slot.HoldsEffect());
  Slot.Tick(2700, false, Lines, bReleased);
  TestTrue("released at 1500 ms", bReleased);
  TestFalse("no longer held", Slot.HoldsEffect());
  TestTrue("effect line", LinesContain(Lines, TEXT("HUD-SLOT effect seq=40 release=time afterArrive=1500")));
  TestTrue("the card stays the release frame", Slot.IsVisible());
  Lines.Reset();
  Slot.Tick(2716, true, Lines, bReleased);
  TestTrue("stays while the effect runs", Slot.IsVisible());
  Slot.Tick(4000, false, Lines, bReleased);
  TestFalse("leaves when the effect ended", Slot.IsVisible());
  TestTrue("a scheme leaves in one frame",
           LinesContain(Lines, TEXT("HUD-SLOT off seq=40 ribbon=scheme")) && LinesContain(Lines, TEXT("reason=done")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09SlotSkipTest,
    "Unmatched.S09.SCHEME.Slot a click during the hold starts the effect at once; a new seq releases it",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09SlotSkipTest::RunTest(const FString&) {
  FS09SourceSlot Slot;
  TArray<FString> Lines;
  bool bReleased = false;
  Slot.Show(MakeSlot(ES09SlotRibbon::Scheme, true, 7), 0, false, Lines, bReleased);
  Lines.Reset();
  TestTrue("skip during the hold", Slot.Skip(600, TEXT("click"), Lines));
  TestFalse("effect started", Slot.HoldsEffect());
  TestTrue("release line names the click", LinesContain(Lines, TEXT("release=click afterArrive=400")));
  TestFalse("a second skip does nothing", Slot.Skip(650, TEXT("click"), Lines));
  Slot.Tick(700, false, Lines, bReleased);
  TestFalse("the tick does not release twice", bReleased);
  TestFalse("leaves once the effect is over", Slot.IsVisible());

  FS09SourceSlot Newer;
  Newer.Show(MakeSlot(ES09SlotRibbon::Scheme, true, 9), 0, false, Lines, bReleased);
  TestFalse("same seq (a merge) keeps the hold", Newer.ReleaseForSeq(9, 100, Lines));
  TestTrue("a newer seq releases", Newer.ReleaseForSeq(10, 300, Lines));
  TestTrue("release=newseq", LinesContain(Lines, TEXT("release=newseq")));
  TestTrue("the card itself stays", Newer.IsVisible());

  FS09SourceSlot Cut;
  Cut.Show(MakeSlot(ES09SlotRibbon::Scheme, true, 11), 0, false, Lines, bReleased);
  Cut.Cut(100, TEXT("gameover"), Lines, bReleased);
  TestTrue("a cut releases the held effect", bReleased);
  TestFalse("and ends the card", Cut.IsVisible());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09SlotOwnSchemeTest,
    "Unmatched.S09.SCHEME.Slot own scheme: no wait, 500 ms after arrival and while its effect runs",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09SlotOwnSchemeTest::RunTest(const FString&) {
  FS09SourceSlot Slot;
  TArray<FString> Lines;
  bool bReleased = false;
  Slot.Show(MakeSlot(ES09SlotRibbon::Scheme, false, 5), 0, false, Lines, bReleased);
  TestFalse("own scheme holds nothing", Slot.HoldsEffect());
  TestTrue("hold=0 min=700", LinesContain(Lines, TEXT("hold=0 min=700")));
  TestFalse("no skip for an own scheme", Slot.Skip(50, TEXT("click"), Lines));
  Slot.Tick(699, false, Lines, bReleased);
  TestTrue("shown 500 ms after arrival", Slot.IsVisible());
  Slot.Tick(700, true, Lines, bReleased);
  TestTrue("its choice is open: stays", Slot.IsVisible());
  Slot.Tick(5000, true, Lines, bReleased);
  TestTrue("still open: stays", Slot.IsVisible());
  Slot.Tick(5016, false, Lines, bReleased);
  TestFalse("choice answered: leaves", Slot.IsVisible());
  Slot.Show(MakeSlot(ES09SlotRibbon::Scheme, false, 6), 10000, false, Lines, bReleased);
  Slot.Tick(10000 + FS09SourceSlot::MaxShowMs, true, Lines, bReleased);
  TestFalse("a stuck effect is capped", Slot.IsVisible());
  TestTrue("reason=cap", LinesContain(Lines, TEXT("reason=cap")));

  FS09SourceSlot Reduced;
  Reduced.Show(MakeSlot(ES09SlotRibbon::Scheme, true, 8), 0, true, Lines, bReleased);
  TestEqual("reduced motion: no fly", Reduced.FlyT(0), 1.0f);
  TestEqual("reduced motion keeps the read hold", Reduced.ReleaseAtMs(), static_cast<int64>(1500));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09SlotBoostTest,
    "Unmatched.S09.SCHEME.Slot opponent boost: at least 1000 ms and the move, then a 250 ms fade; replace rules",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09SlotBoostTest::RunTest(const FString&) {
  FS09SourceSlot Slot;
  TArray<FString> Lines;
  bool bReleased = false;
  Slot.Show(MakeSlot(ES09SlotRibbon::Boosted, true, 20), 0, false, Lines, bReleased);
  TestFalse("the move never waits for the boost card", Slot.HoldsEffect());
  Slot.Tick(999, false, Lines, bReleased);
  TestTrue("1000 ms minimum", Slot.IsVisible());
  Slot.Tick(1000, true, Lines, bReleased);
  TestTrue("the move still plays: shown", Slot.GetState() == ES09SlotState::Show);
  Slot.Tick(1400, false, Lines, bReleased);
  TestTrue("fade starts", Slot.GetState() == ES09SlotState::Fade);
  TestTrue("half way", FMath::IsNearlyEqual(Slot.Alpha(1525), 0.5f, 0.01f));
  Slot.Tick(1650, false, Lines, bReleased);
  TestFalse("gone after 250 ms", Slot.IsVisible());

  // a held opponent scheme is released before another card replaces it
  FS09SourceSlot Replace;
  Replace.Show(MakeSlot(ES09SlotRibbon::Scheme, true, 30), 0, false, Lines, bReleased);
  Lines.Reset();
  TestTrue("boost replaces", Replace.Show(MakeSlot(ES09SlotRibbon::Boosted, true, 31), 500, false, Lines, bReleased));
  TestTrue("the held effect was released first", bReleased);
  TestTrue("release=replace, off reason=replace",
           LinesContain(Lines, TEXT("release=replace")) && LinesContain(Lines, TEXT("reason=replace")));
  // a discard never replaces a scheme (it is that scheme's effect)
  FS09SourceSlot Keep;
  Keep.Show(MakeSlot(ES09SlotRibbon::Scheme, false, 40), 0, false, Lines, bReleased);
  TestFalse("discard dropped while a scheme shows",
            Keep.Show(MakeSlot(ES09SlotRibbon::Discarded, true, 41), 100, false, Lines, bReleased));
  TestTrue("the scheme stays", Keep.GetCard().Ribbon == ES09SlotRibbon::Scheme);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09SlotWatchTest,
    "Unmatched.S09.SCHEME.Slot played-card watch: scheme, boost and discard from the public piles only",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09SlotWatchTest::RunTest(const FString&) {
  const FS09CardView Old = SlotCard(TEXT("o::1"), TEXT("Old"), TEXT("ATTACK"));
  const FS09CardView OppScheme = SlotCard(TEXT("g::5"), TEXT("Second Sight"), TEXT("SCHEME"));
  const FS09CardView OwnScheme = SlotCard(TEXT("h::5"), TEXT("Restless Spirits"), TEXT("SCHEME"));
  const TArray<FS08PendingEffect> NoQueue;
  FS09LastMovement NoTrail;
  FS09PlayedCardWatch Watch;
  FS09SlotCard Out;
  TestFalse("the first snapshot primes",
            Watch.OnApplied(SlotHud(10, TEXT("ACTION_1"), {Old}, {OppScheme}), NoQueue, NoTrail, HostId, Out));
  TestFalse("a merge of the same piles shows nothing",
            Watch.OnApplied(SlotHud(10, TEXT("ACTION_1"), {Old}, {OppScheme}), NoQueue, NoTrail, HostId, Out));
  // the opponent plays a scheme (its discard pile grows by a SCHEME card)
  const FS09CardView OppScheme2 = SlotCard(TEXT("g::6"), TEXT("Gaze"), TEXT("SCHEME"));
  TestTrue("opponent scheme", Watch.OnApplied(SlotHud(11, TEXT("ACTION_2"), {Old}, {OppScheme, OppScheme2}), NoQueue,
                                              NoTrail, HostId, Out));
  TestTrue("ribbon scheme", Out.Ribbon == ES09SlotRibbon::Scheme);
  TestTrue("opponent's", Out.bOpponent);
  TestEqual("the new card", Out.Card.InstanceId, FString(TEXT("g::6")));
  TestEqual("seq", Out.Seq, 11);
  TestFalse("the same seq again shows nothing",
            Watch.OnApplied(SlotHud(11, TEXT("ACTION_2"), {Old}, {OppScheme, OppScheme2}), NoQueue, NoTrail, HostId,
                            Out));
  // my own scheme
  TestTrue("own scheme", Watch.OnApplied(SlotHud(12, TEXT("ACTION_1"), {Old, OwnScheme}, {OppScheme, OppScheme2}),
                                         NoQueue, NoTrail, HostId, Out));
  TestFalse("mine", Out.bOpponent);
  // combat cards never go to the slot (a SCHEME card used as a combat boost neither)
  const FS09CardView CombatCard = SlotCard(TEXT("g::7"), TEXT("Snipe"), TEXT("SCHEME"));
  TestFalse("in combat", Watch.OnApplied(SlotHud(13, TEXT("COMBAT_RESOLVE"), {Old, OwnScheme},
                                                 {OppScheme, OppScheme2, CombatCard}),
                                         NoQueue, NoTrail, HostId, Out));
  const FS09CardView ClosedCombat = SlotCard(TEXT("g::8"), TEXT("Hiss"), TEXT("SCHEME"));
  TestFalse("the snapshot closing a combat",
            Watch.OnApplied(SlotHud(14, TEXT("ACTION_2"), {Old, OwnScheme}, {OppScheme, OppScheme2, CombatCard, ClosedCombat}),
                            NoQueue, NoTrail, HostId, Out));
  // the opponent's open discard (the hand limit) -> DISCARDED, even for a SCHEME card
  FS09HudModel Limit =
      SlotHud(15, TEXT("TURN_END"), {Old, OwnScheme}, {OppScheme, OppScheme2, CombatCard, ClosedCombat});
  Limit.bHasPendingDiscard = true;
  Limit.PendingDiscard.PlayerId = GuestId;
  Limit.PendingDiscard.Count = 2;
  TestFalse("the discard opens", Watch.OnApplied(Limit, NoQueue, NoTrail, HostId, Out));
  const FS09CardView Drop1 = SlotCard(TEXT("g::9"), TEXT("Drop A"), TEXT("SCHEME"));
  const FS09CardView Drop2 = SlotCard(TEXT("g::10"), TEXT("Drop B"), TEXT("DEFENSE"));
  const TArray<FS09CardView> OppAll = {OppScheme, OppScheme2, CombatCard, ClosedCombat, Drop1, Drop2};
  TestTrue("discarded", Watch.OnApplied(SlotHud(16, TEXT("ACTION_1"), {Old, OwnScheme}, OppAll), NoQueue, NoTrail,
                                        HostId, Out));
  TestTrue("DISCARDED, not a scheme", Out.Ribbon == ES09SlotRibbon::Discarded);
  TestEqual("both counted", Out.Count, 2);
  TestEqual("the newest shown", Out.Card.InstanceId, FString(TEXT("g::10")));
  // my own discard after an effect's DISCARD_CARDS is not shown (I picked it)
  FS08PendingEffect MyDiscard;
  MyDiscard.Id = TEXT("pe:1");
  MyDiscard.PlayerId = HostId;
  MyDiscard.Type = TEXT("DISCARD_CARDS");
  const TArray<FS08PendingEffect> MyQueue = {MyDiscard};
  TestFalse("my choice opens", Watch.OnApplied(SlotHud(17, TEXT("ACTION_1"), {Old, OwnScheme}, OppAll), MyQueue,
                                               NoTrail, HostId, Out));
  const FS09CardView MyDrop = SlotCard(TEXT("h::9"), TEXT("Mine"), TEXT("SCHEME"));
  TestFalse("my discard: nothing", Watch.OnApplied(SlotHud(18, TEXT("ACTION_1"), {Old, OwnScheme, MyDrop}, OppAll),
                                                   NoQueue, NoTrail, HostId, Out));
  // the opponent's maneuver boost (SD-54): a SCHEME card used as the boost is BOOSTED, not a scheme
  FS09LastMovement Trail;
  Trail.bValid = true;
  Trail.Seq = 19;
  Trail.PlayerId = GuestId;
  Trail.Source = TEXT("MANEUVER");
  Trail.bBoost = true;
  Trail.BoostName = TEXT("Feint");
  Trail.BoostValue = 3;
  TArray<FS09CardView> OppBoost = OppAll;
  OppBoost.Add(SlotCard(TEXT("g::11"), TEXT("Feint"), TEXT("SCHEME"), 3));
  TestTrue("boost", Watch.OnApplied(SlotHud(19, TEXT("ACTION_2"), {Old, OwnScheme, MyDrop}, OppBoost), NoQueue, Trail,
                                    HostId, Out));
  TestTrue("BOOSTED", Out.Ribbon == ES09SlotRibbon::Boosted);
  TestEqual("the face from the pile", Out.Card.InstanceId, FString(TEXT("g::11")));
  TestFalse("one boost per seq", Watch.OnApplied(SlotHud(19, TEXT("ACTION_2"), {Old, OwnScheme, MyDrop}, OppBoost),
                                                 NoQueue, Trail, HostId, Out));
  // my own maneuver boost does not go to the slot
  FS09LastMovement Mine = Trail;
  Mine.Seq = 20;
  Mine.PlayerId = HostId;
  const FS09CardView MyBoost = SlotCard(TEXT("h::10"), TEXT("Feint"), TEXT("ATTACK"), 2);
  TestFalse("own boost", Watch.OnApplied(SlotHud(20, TEXT("ACTION_1"), {Old, OwnScheme, MyDrop, MyBoost}, OppBoost),
                                         NoQueue, Mine, HostId, Out));
  // run E G-LIVE: my own boost with a SCHEME card (A Momentary Glance) is a boost, not a played scheme
  FS09LastMovement MineScheme = Mine;
  MineScheme.Seq = 22;
  MineScheme.BoostName = TEXT("A Momentary Glance");
  const FS09CardView MySchemeBoost = SlotCard(TEXT("h::11"), TEXT("A Momentary Glance"), TEXT("SCHEME"), 2);
  TestFalse("own SCHEME-card boost", Watch.OnApplied(SlotHud(22, TEXT("ACTION_1"),
                                                             {Old, OwnScheme, MyDrop, MyBoost, MySchemeBoost}, OppBoost),
                                                     NoQueue, MineScheme, HostId, Out));
  // a boost card not in the pile: the trail's name and value
  FS09LastMovement Bare = Trail;
  Bare.Seq = 21;
  Bare.BoostName = TEXT("Momentous Shift");
  Bare.BoostValue = 2;
  TestTrue("boost from the trail", Watch.OnApplied(SlotHud(21, TEXT("ACTION_1"), {Old, OwnScheme, MyDrop, MyBoost},
                                                           OppBoost),
                                                   NoQueue, Bare, HostId, Out));
  TestEqual("name", Out.Card.Name, FString(TEXT("Momentous Shift")));
  TestEqual("value", Out.Card.BoostValue, 2);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09HandLowerTest,
    "Unmatched.S09.SCHEME.HandLower the hand goes down during a board pick, never over the HUD",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09HandLowerTest::RunTest(const FString&) {
  FS09CommandUi Ui;
  TestTrue("idle: no pick", S09BoardPickOf(Ui, true) == ES09BoardPick::None);
  Ui.Mode = ES09CommandMode::ManeuverDraft;
  TestTrue("draft without a fighter", S09BoardPickOf(Ui, true) == ES09BoardPick::None);
  Ui.SelectedFighterId = TEXT("f1");
  TestTrue("draft destination", S09BoardPickOf(Ui, true) == ES09BoardPick::Cell);
  Ui = FS09CommandUi();
  Ui.Mode = ES09CommandMode::AttackDraft;
  Ui.AttackAttackerId = TEXT("f1");
  TestTrue("attack target", S09BoardPickOf(Ui, true) == ES09BoardPick::Target);
  Ui.AttackTargetId = TEXT("f9");
  TestTrue("target chosen", S09BoardPickOf(Ui, true) == ES09BoardPick::None);
  Ui = FS09CommandUi();
  Ui.Mode = ES09CommandMode::PendingChoice;
  Ui.PendingChoice.Type = TEXT("TARGET_FIGHTER");
  TestTrue("TARGET_FIGHTER", S09BoardPickOf(Ui, false) == ES09BoardPick::Target);
  Ui.PendingChoice.Type = TEXT("MOVE");
  TestTrue("MOVE: the fighter first", S09BoardPickOf(Ui, false) == ES09BoardPick::Target);
  Ui.PendingFighterId = TEXT("f1");
  TestTrue("MOVE: then the space", S09BoardPickOf(Ui, false) == ES09BoardPick::Cell);
  Ui.PendingChoice.Type = TEXT("DISCARD_CARDS");
  TestTrue("a hand pick keeps the hand up", S09BoardPickOf(Ui, false) == ES09BoardPick::None);
  Ui = FS09CommandUi();
  Ui.SelectedFighterId = TEXT("f1");
  Ui.ReachableCells.Add(1);
  TestTrue("MS-S-02 cells in my turn", S09BoardPickOf(Ui, true) == ES09BoardPick::Cell);
  TestTrue("not in the opponent's", S09BoardPickOf(Ui, false) == ES09BoardPick::None);

  FS09HandLower Hand;
  TestTrue("no pick: no line", Hand.Update(ES09BoardPick::None, false, 0.0).IsEmpty());
  const FString Down = Hand.Update(ES09BoardPick::Cell, false, 100.0);
  TestTrue("lowered", Hand.IsLowered() && Down.Contains(TEXT("HUD-HAND lower=1 pick=cell cursor=board preview=hidden")));
  TestTrue("the preview is hidden", Hand.HidesPreview());
  TestEqual("slide starts at 0", Hand.OffsetSu(100.0, false), 0.0f);
  TestTrue("sliding", Hand.IsSliding(150.0, false));
  TestEqual("down by 60 after 120 ms", Hand.OffsetSu(220.0, false), FS09HandLower::LowerSu);
  TestEqual("reduced motion: at once", Hand.OffsetSu(100.0, true), FS09HandLower::LowerSu);
  TestTrue("same state: no line", Hand.Update(ES09BoardPick::Target, false, 300.0).IsEmpty());
  const FString Up = Hand.Update(ES09BoardPick::Cell, true, 400.0);
  TestTrue("cursor on the HUD: up", !Hand.IsLowered() && Up.Contains(TEXT("lower=0")) && Up.Contains(TEXT("cursor=hud")));
  TestEqual("comes up from 60", Hand.OffsetSu(400.0, false), FS09HandLower::LowerSu);
  TestEqual("up after 120 ms", Hand.OffsetSu(520.0, false), 0.0f);
  Hand.Update(ES09BoardPick::Cell, false, 600.0);
  TestTrue("pick ends: up", !Hand.Update(ES09BoardPick::None, false, 650.0).IsEmpty() && !Hand.IsLowered());
  return true;
}
#endif

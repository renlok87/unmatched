// GD-032 automation tests: HUD model parsing, merge behavior, privacy and
// counter freshness over the captured S08 fixtures (host 04 / guest 05 real
// backend bodies). Run headless:
//   UnrealEditor-Cmd.exe Unmatched.uproject -ExecCmds="Automation RunTests Unmatched.S09; Quit"
//     -unattended -nosplash -nullrhi
// Fixture viewer ids (captured 2026-09-25): host cmugykjjb0000wi9w2nq4qlkj,
// guest cmugykjkr0007wi9w2i4f209d. Both perspectives are asserted: the owner
// sees exact instance ids, the opponent ONLY a hidden count.
#if WITH_AUTOMATION_TESTS

#include "S09HudModel.h"
#include "../S08/S08Contracts.h"
#include "../S08/S08FlowGameMode.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

namespace {
const TCHAR* HostId = TEXT("cmugykjjb0000wi9w2nq4qlkj");
const TCHAR* GuestId = TEXT("cmugykjkr0007wi9w2i4f209d");

FString FixturePath(const TCHAR* Name) {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S08Fixtures="), Dir) || Dir.IsEmpty()) {
    Dir = FPaths::Combine(FPaths::ProjectDir(),
                          TEXT("../../docs/game-design/evidence/S08/fixtures"));
  }
  return FPaths::Combine(Dir, Name);
}

// Loads a captured gameState query body into a decoded snapshot.
bool LoadSnapshot(const TCHAR* Name, FS08Snapshot& Out, FString& OutError) {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *FixturePath(Name))) return false;
  TSharedPtr<FJsonValue> Value;
  if (!FS08Contracts::TryParseJsonValue(Text, Value, OutError)) return false;
  const TSharedPtr<FJsonObject>* Root = nullptr;
  if (!Value->TryGetObject(Root) || !Root->IsValid()) return false;
  FString Inner;
  const TSharedPtr<FJsonObject>* RawObject = nullptr;
  if ((*Root)->TryGetStringField(TEXT("raw"), Inner)) {
    if (!FS08Contracts::TryParseJsonValue(Inner, Value, OutError)) return false;
  } else if (!(*Root)->TryGetObjectField(TEXT("raw"), RawObject)) {
    return false;
  }
  FString Serialized;
  if (RawObject && RawObject->IsValid()) {
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Serialized);
    FJsonSerializer::Serialize(RawObject->ToSharedRef(), Writer);
  } else if (!Inner.IsEmpty()) {
    Serialized = Inner;
  }
  FString RawState;
  FS08GraphQLError ParseError;
  if (!FS08Contracts::ParseGameStateQuery(Serialized, Out, RawState, ParseError)) {
    OutError = ParseError.Code + TEXT(": ") + ParseError.Message;
    return false;
  }
  return true;
}
} // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09HudHostPerspectiveTest,
    "Unmatched.S09.HUD host perspective: exact own instance ids, opponent count only (fixture 04)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09HudHostPerspectiveTest::RunTest(const FString&) {
  FS08Snapshot Snapshot;
  FString Error;
  if (!LoadSnapshot(TEXT("04-game-state-query-host.json"), Snapshot, Error)) {
    AddError(TEXT("fixture 04 not loaded: ") + Error);
    return true;
  }
  FS09HudModel Hud;
  Hud.Build(Snapshot, HostId, TSet<FString>(), Snapshot.SequenceNumber,
            Snapshot.SequenceNumber);
  TestTrue("model valid", Hud.bValid);
  TestEqual("two panels", Hud.Panels.Num(), 2);
  TestTrue("viewer panel first", Hud.Panels.Num() > 0 && Hud.Panels[0].bIsViewer);
  const FS09PlayerPanel* Own = Hud.ViewerPanel();
  const FS09PlayerPanel* Opp = Hud.OpponentPanel();
  if (!Own || !Opp) { AddError("panels missing"); return true; }

  // GD-032: owner sees EXACT instance ids (server form "cardId::copyIndex").
  TestEqual("own hand count 5", Own->HandCount, 5);
  TestEqual("own cards decoded", Own->Cards.Num(), 5);
  TestEqual("hand limit 7", Own->HandMaxSize, 7);
  bool bAllExact = true, bAnyHidden = false;
  for (const FS09CardView& Card : Own->Cards) {
    bAllExact &= Card.InstanceId.Contains(TEXT("::")) && !Card.bHidden;
    bAnyHidden |= Card.bHidden;
  }
  TestTrue("every own id is an exact instance id", bAllExact);
  TestFalse("no hidden placeholder in own hand", bAnyHidden);

  // Opponent: COUNT ONLY - entries are never decoded into card views.
  TestEqual("opponent hand count 5", Opp->HandCount, 5);
  TestEqual("opponent cards NOT decoded (privacy by construction)", Opp->Cards.Num(), 0);

  // Deck counters come from the hidden drawPile LENGTH (25 placeholders here).
  TestEqual("own deck count", Own->DeckCount, 25);
  TestEqual("opponent deck count", Opp->DeckCount, 25);
  TestFalse("own deck fresh", Own->bDeckCountStale);
  TestFalse("opponent deck fresh", Opp->bDeckCountStale);

  TestEqual("actions remaining", Hud.ActionsRemaining, 2);
  TestTrue("viewer's turn", Hud.bViewerTurn);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09HudGuestPerspectiveTest,
    "Unmatched.S09.HUD guest perspective: roles flip, hidden host hand stays count-only (fixture 05)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09HudGuestPerspectiveTest::RunTest(const FString&) {
  FS08Snapshot Snapshot;
  FString Error;
  if (!LoadSnapshot(TEXT("05-game-state-query-guest.json"), Snapshot, Error)) {
    AddError(TEXT("fixture 05 not loaded: ") + Error);
    return true;
  }
  FS09HudModel Hud;
  Hud.Build(Snapshot, GuestId, TSet<FString>(), Snapshot.SequenceNumber,
            Snapshot.SequenceNumber);
  TestTrue("model valid", Hud.bValid);
  const FS09PlayerPanel* Own = Hud.ViewerPanel();
  const FS09PlayerPanel* Opp = Hud.OpponentPanel();
  if (!Own || !Opp) { AddError("panels missing"); return true; }
  TestEqual("guest own hand count 5", Own->HandCount, 5);
  TestEqual("guest own cards decoded", Own->Cards.Num(), 5);
  bool bAllExact = true;
  for (const FS09CardView& Card : Own->Cards) {
    bAllExact &= Card.InstanceId.Contains(TEXT("::")) && !Card.bHidden;
  }
  TestTrue("guest sees own exact ids", bAllExact);
  // The HOST hand (opponent from this seat) must be a count only.
  TestEqual("host hand count 5 from guest seat", Opp->HandCount, 5);
  TestEqual("host cards NOT decoded", Opp->Cards.Num(), 0);
  TestFalse("not guest's turn", Hud.bViewerTurn);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09HudPrivacyLeakTest,
    "Unmatched.S09.HUD privacy: hidden entries carry no face, summary never leaks card identity",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09HudPrivacyLeakTest::RunTest(const FString&) {
  // A hidden wire entry (opponent hand / deck placeholder) must decode into a
  // card view with NO identity at all.
  const FString HiddenEntry = TEXT(
      "{\"id\":\"hidden-0\",\"cardId\":\"hidden\",\"name\":\"???\",\"nameEn\":\"Hidden\","
      "\"nameRu\":\"Skryto\",\"cardType\":\"UNIVERSAL\",\"isVisible\":false}");
  TSharedPtr<FJsonValue> Value;
  FString Problem;
  if (!FS08Contracts::TryParseJsonValue(HiddenEntry, Value, Problem)) {
    AddError(Problem);
    return true;
  }
  FS09CardView Card;
  TestTrue("hidden entry decodes", FS09HudFactory::CardFromJson(Value, Card));
  TestTrue("flagged hidden", Card.bHidden);
  TestTrue("no name survives", Card.Name.IsEmpty());
  TestTrue("no cardId survives", Card.CardId.IsEmpty());
  TestTrue("no type survives", Card.CardType.IsEmpty());
  TestEqual("only the placeholder position id", Card.InstanceId, TEXT("hidden-0"));
  TestTrue("chip text never reveals", !Card.ChipText().Contains(TEXT("???")));

  // The evidence-facing summary line: counters and seq only.
  FS08Snapshot Snapshot;
  FString Error;
  if (!LoadSnapshot(TEXT("04-game-state-query-host.json"), Snapshot, Error)) {
    AddError(TEXT("fixture 04 not loaded: ") + Error);
    return true;
  }
  FS09HudModel Hud;
  Hud.Build(Snapshot, HostId, TSet<FString>(), Snapshot.SequenceNumber,
            Snapshot.SequenceNumber);
  const FString Summary = Hud.SummaryLine();
  TestTrue("summary built", !Summary.IsEmpty());
  TestFalse("summary has no own card names (\"Regroup\")", Summary.Contains(TEXT("Regroup")));
  TestFalse("summary has no own card names (\"Zeus\")", Summary.Contains(TEXT("Zeus")));
  TestFalse("summary has no hidden marker", Summary.Contains(TEXT("???")));
  TestTrue("summary carries seq", Summary.Contains(TEXT("seq=")));
  TestTrue("summary carries opponent hand count", Summary.Contains(TEXT("oppHand=5")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09HudFreshnessTest,
    "Unmatched.S09.HUD counter freshness: WS bodies carry no decks, stale counts are marked",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09HudFreshnessTest::RunTest(const FString&) {
  // The WS event body (fixture 07) must NOT carry a decks projection at all -
  // proving the model cannot fabricate deck counts from a stream event.
  FString WsText;
  TestTrue("ws fixture loaded",
           FFileHelper::LoadFileToString(WsText, *FixturePath(TEXT("07-ws-game-state-updated-next.json"))));
  TSharedPtr<FJsonValue> WsValue;
  FString Problem;
  if (FS08Contracts::TryParseJsonValue(WsText, WsValue, Problem)) {
    const TSharedPtr<FJsonObject>* Root = nullptr;
    const TSharedPtr<FJsonObject>* Data = nullptr;
    const TSharedPtr<FJsonObject>* Event = nullptr;
    if (WsValue->TryGetObject(Root) && (*Root)->TryGetObjectField(TEXT("data"), Data) &&
        (*Data)->TryGetObjectField(TEXT("gameStateUpdated"), Event) && Event->IsValid()) {
      FS08Snapshot WsSnap;
      FS08GraphQLError ParseError;
      if (FS08Contracts::ParseGameStateUpdated(Event->ToSharedRef(), WsSnap, ParseError)) {
        TestFalse("WS event has NO decks projection", WsSnap.Decks.IsValid());
        TestTrue("WS event keeps hand zones", WsSnap.HandZones.IsValid());
      } else {
        AddError(ParseError.Message);
      }
    }
  } else {
    AddError(Problem);
  }

  // Stale marking: a count whose last carrier seq is below the applied seq.
  FS08Snapshot Snapshot;
  FString Error;
  if (!LoadSnapshot(TEXT("04-game-state-query-host.json"), Snapshot, Error)) {
    AddError(TEXT("fixture 04 not loaded: ") + Error);
    return true;
  }
  FS09HudModel Hud;
  Hud.Build(Snapshot, HostId, TSet<FString>(), Snapshot.SequenceNumber - 1,
            Snapshot.SequenceNumber - 1);
  const FS09PlayerPanel* Own = Hud.ViewerPanel();
  if (!Own) { AddError("viewer panel missing"); return true; }
  TestTrue("deck count marked stale", Own->bDeckCountStale);
  TestTrue("discard count marked stale", Own->bDiscardStale);
  TestTrue("summary marks staleness", Hud.SummaryLine().Contains(TEXT("~")));

  // Fresh again when the carrier seq catches up.
  FS09HudModel Fresh;
  Fresh.Build(Snapshot, HostId, TSet<FString>(), Snapshot.SequenceNumber,
              Snapshot.SequenceNumber);
  TestFalse("deck fresh at equal seq", Fresh.ViewerPanel()->bDeckCountStale);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09HudNewCardTest,
    "Unmatched.S09.HUD new-card marking: beginManeuver draw is bNew vs previous hand (ACC-006)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09HudNewCardTest::RunTest(const FString&) {
  FS08Snapshot Snapshot;
  FString Error;
  if (!LoadSnapshot(TEXT("04-game-state-query-host.json"), Snapshot, Error)) {
    AddError(TEXT("fixture 04 not loaded: ") + Error);
    return true;
  }
  // Baseline hand.
  FS09HudModel Before;
  Before.Build(Snapshot, HostId, TSet<FString>(), Snapshot.SequenceNumber,
               Snapshot.SequenceNumber);
  const FS09PlayerPanel* BeforeOwn = Before.ViewerPanel();
  if (!BeforeOwn || BeforeOwn->Cards.Num() != 5) { AddError("baseline hand missing"); return true; }
  TSet<FString> PreviousIds;
  for (const FS09CardView& Card : BeforeOwn->Cards) {
    PreviousIds.Add(Card.InstanceId);
  }
  // Simulate the post-begin hand: same 5 ids + a drawn instance.
  const TSharedRef<FJsonObject> Hands = MakeShared<FJsonObject>(*Snapshot.HandZones->AsObject());
  const TSharedPtr<FJsonValue> HandValue = Hands->TryGetField(HostId);
  const TSharedPtr<FJsonObject> Hand = HandValue.IsValid() ? HandValue->AsObject() : nullptr;
  if (!Hand.IsValid()) { AddError("host hand missing"); return true; }
  const TSharedRef<FJsonObject> NewHand = MakeShared<FJsonObject>(*Hand);
  const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
  NewHand->TryGetArrayField(TEXT("cards"), Cards);
  TArray<TSharedPtr<FJsonValue>> Grown;
  if (Cards) Grown = *Cards;
  const TSharedRef<FJsonObject> Drawn = MakeShared<FJsonObject>(*Grown[0]->AsObject());
  Drawn->SetStringField(TEXT("id"), TEXT("drawn-new::9"));
  Grown.Add(MakeShared<FJsonValueObject>(Drawn));
  NewHand->SetArrayField(TEXT("cards"), Grown);
  Hands->SetObjectField(HostId, NewHand);
  Snapshot.HandZones = MakeShared<FJsonValueObject>(Hands);

  FS09HudModel After;
  After.Build(Snapshot, HostId, PreviousIds, Snapshot.SequenceNumber,
              Snapshot.SequenceNumber);
  const FS09PlayerPanel* AfterOwn = After.ViewerPanel();
  if (!AfterOwn) { AddError("panel missing"); return true; }
  TestEqual("hand grew to 6", AfterOwn->Cards.Num(), 6);
  int32 NewCount = 0;
  const FS09CardView* NewCard = nullptr;
  for (const FS09CardView& Card : AfterOwn->Cards) {
    if (Card.bNew) { ++NewCount; NewCard = &Card; }
  }
  TestEqual("exactly one new card", NewCount, 1);
  if (NewCard) {
    TestEqual("new card is the drawn instance", NewCard->InstanceId, TEXT("drawn-new::9"));
  }
  // Empty previous set = first observation: nothing is marked new.
  FS09HudModel First;
  First.Build(Snapshot, HostId, TSet<FString>(), Snapshot.SequenceNumber,
              Snapshot.SequenceNumber);
  TestEqual("no bNew without a baseline", First.ViewerPanel()->Cards.FilterByPredicate(
                [](const FS09CardView& C) { return C.bNew; }).Num(), 0);
  return true;
}
// GD-032 gap fix: the inspector must show the FULL resolved card text plus
// identity/type/values for a public face (own hand AND both public discards),
// while a hidden placeholder renders exactly one faceless line - the pre-reveal
// privacy regression gate for the discard browser.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09InspectorLinesTest,
    "Unmatched.S09.HUD inspector lines: full text + identity for public cards, hidden stays faceless",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09InspectorLinesTest::RunTest(const FString&) {
  FS09CardView Public;
  Public.InstanceId = TEXT("card::7");
  Public.CardId = TEXT("card-regroup");
  Public.Name = TEXT("Regroup");
  Public.NameRu = TEXT("Перегруппировка");
  Public.CardType = TEXT("UNIVERSAL");
  Public.AttackValue = 3;
  Public.DefenseValue = 4;
  Public.BoostValue = 2;
  Public.BannerName = TEXT("Zeus");
  Public.Text = TEXT("Discard this card to draw two cards.");
  TArray<FString> Lines;
  AS08FlowGameMode::BuildInspectorLines(Public, Lines);
  TestEqual("five inspector lines for a public card", Lines.Num(), 5);
  if (Lines.Num() == 5) {
    TestTrue("title carries name, type and banner",
             Lines[0].Contains(TEXT("Regroup")) && Lines[0].Contains(TEXT("UNIVERSAL")) &&
                 Lines[0].Contains(TEXT("Zeus")));
    TestTrue("identity line carries instance and card ids",
             Lines[1].Contains(TEXT("card::7")) && Lines[1].Contains(TEXT("card-regroup")));
    TestTrue("values line carries attack/defense/boost",
             Lines[2].Contains(TEXT("attack 3")) && Lines[2].Contains(TEXT("defense 4")) &&
                 Lines[2].Contains(TEXT("boost 2")));
    TestTrue("ru name present", Lines[3].Contains(TEXT("Перегруппировка")));
    TestTrue("full resolved text present (GD-032 gap)",
             Lines[4].Contains(TEXT("Discard this card to draw two cards.")));
  }

  // Hidden placeholder: exactly one line, no identity anywhere (the wire entry
  // is stripped at decode time; the inspector must not invent a face either).
  const FS09CardView Hidden = FS09HudFactory::HiddenCard(TEXT("hidden-0"));
  TArray<FString> HiddenLines;
  AS08FlowGameMode::BuildInspectorLines(Hidden, HiddenLines);
  TestEqual("hidden inspects to exactly one line", HiddenLines.Num(), 1);
  if (HiddenLines.Num() == 1) {
    TestEqual("hidden line is the faceless placeholder", HiddenLines[0],
              TEXT("hidden card - no face is available to this viewer"));
  }
  return true;
}
#endif

// DE-030 (W-19; 01 F-05; 02 SD-29, SD-41; QA-005) automation tests: the deck side panel model (S09DeckPanel.h).
//   - Unmatched.S09.DeckPanel.Projection: over the REAL viewer-projected fixture gd035-move-open-host-view the client
//     receives no deck order (every drawPile entry is a placeholder, no topCard) and no instance id of the opponent's
//     hand; the opponent panel of the model is built from counts and public discards only.
//   - .Own: composition + "in hand" / "in discard" / "left" + "out of play" against the server's deck count.
//   - .Opponent: discard marks only, card backs by number, no "left"; injected opponent cards are never read.
//   - .Parse: the gameDeckLists answer and its shape errors.
//   - .View: open 80 ms (<= 100), close 150 ms, the auto-close on a new input demand only.
#if WITH_AUTOMATION_TESTS

#include "S09DeckPanel.h"
#include "S09HudModel.h"
#include "../S08/S08Contracts.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace {
bool LoadDeckFixture(FS08Snapshot& OutSnapshot) {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S09Fixtures="), Dir) || Dir.IsEmpty()) {
    Dir = FPaths::Combine(FPaths::ProjectDir(), TEXT("../../docs/game-design/evidence/S09/fixtures"));
  }
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *FPaths::Combine(Dir, TEXT("gd035-move-open-host-view.json")))) return false;
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

/** The host seat of the fixture = the player whose hand is decoded (not placeholders). */
FString HostViewerId(const FS08Snapshot& Snapshot) {
  const TSharedPtr<FJsonObject> Hands = Snapshot.HandZones.IsValid() ? Snapshot.HandZones->AsObject() : nullptr;
  if (!Hands.IsValid()) return FString();
  for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Hands->Values) {
    const TSharedPtr<FJsonObject> Hand = Pair.Value.IsValid() ? Pair.Value->AsObject() : nullptr;
    const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
    if (!Hand.IsValid() || !Hand->TryGetArrayField(TEXT("cards"), Cards) || !Cards || Cards->Num() == 0) continue;
    const TSharedPtr<FJsonObject> First = (*Cards)[0]->AsObject();
    if (First.IsValid() && First->GetStringField(TEXT("cardId")) != TEXT("hidden")) return Pair.Key;
  }
  return FString();
}

FS09DeckListCard ListCard(const FString& CardId, int32 Count, const TCHAR* Type = TEXT("VERSATILE")) {
  FS09DeckListCard Card;
  Card.CardId = CardId;
  Card.Name = TEXT("Card ") + CardId.Right(6);
  Card.CardType = Type;
  Card.AttackValue = 3;
  Card.DefenseValue = 2;
  Card.BoostValue = 1;
  Card.Count = Count;
  return Card;
}

/** A deck list for a panel of the fixture: every card id seen in the panel's own hand / discard gets its seen copies
 *  + Extra, a filler card makes the total Copies. */
FS09DeckList ListFor(const FS09PlayerPanel& Panel, bool bUseHand, int32 Extra, int32 Copies) {
  TMap<FString, int32> Seen;
  TArray<FString> Order;
  auto Note = [&](const FS09CardView& Card) {
    if (Card.bHidden) return;
    if (!Seen.Contains(Card.CardId)) Order.Add(Card.CardId);
    ++Seen.FindOrAdd(Card.CardId);
  };
  if (bUseHand) {
    for (const FS09CardView& Card : Panel.Cards) Note(Card);
  }
  for (const FS09CardView& Card : Panel.Discard) Note(Card);
  FS09DeckList List;
  List.PlayerId = Panel.PlayerId;
  int32 Sum = 0;
  for (const FString& Id : Order) {
    List.Cards.Add(ListCard(Id, Seen[Id] + Extra));
    Sum += Seen[Id] + Extra;
  }
  List.Cards.Add(ListCard(TEXT("cat-filler"), Copies - Sum, TEXT("SCHEME")));
  List.Total = Copies;
  return List;
}

const FS09DeckRow* RowOf(const FS09DeckPanelModel& Model, const FString& CardId) {
  for (const FS09DeckRow& Row : Model.Rows) {
    if (Row.Card.CardId == CardId) return &Row;
  }
  return nullptr;
}
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09DeckPanelProjectionTest, "Unmatched.S09.DeckPanel.Projection",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09DeckPanelProjectionTest::RunTest(const FString&) {
  FS08Snapshot Snap;
  if (!LoadDeckFixture(Snap)) {
    AddError(TEXT("fixture gd035-move-open-host-view not loaded"));
    return true;
  }
  const FString Host = HostViewerId(Snap);
  TestFalse("host seat found", Host.IsEmpty());
  // the wire: no deck order, no topCard - every drawPile entry is a placeholder
  const TSharedPtr<FJsonObject> Decks = Snap.Decks.IsValid() ? Snap.Decks->AsObject() : nullptr;
  TestTrue("decks delivered", Decks.IsValid());
  int32 DeckEntries = 0;
  if (Decks.IsValid()) {
    for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Decks->Values) {
      const TSharedPtr<FJsonObject> Deck = Pair.Value->AsObject();
      TestFalse(TEXT("no topCard ") + Pair.Key, Deck->HasField(TEXT("topCard")));
      const TArray<TSharedPtr<FJsonValue>>* Pile = nullptr;
      if (!Deck->TryGetArrayField(TEXT("drawPile"), Pile) || !Pile) continue;
      for (const TSharedPtr<FJsonValue>& Entry : *Pile) {
        ++DeckEntries;
        TestTrue("drawPile entry is a placeholder", FS08Contracts::IsHiddenCard(Entry));
        TestEqual("drawPile entry has no catalog id", Entry->AsObject()->GetStringField(TEXT("cardId")),
                  FString(TEXT("hidden")));
      }
    }
  }
  TestTrue("both decks have draw piles", DeckEntries > 0);
  // the wire: the opponent hand carries no instance id
  const TSharedPtr<FJsonObject> Hands = Snap.HandZones->AsObject();
  int32 OpponentEntries = 0;
  for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Hands->Values) {
    if (Pair.Key == Host) continue;
    const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
    Pair.Value->AsObject()->TryGetArrayField(TEXT("cards"), Cards);
    for (const TSharedPtr<FJsonValue>& Entry : *Cards) {
      ++OpponentEntries;
      const FString Id = Entry->AsObject()->GetStringField(TEXT("id"));
      TestTrue(TEXT("opponent hand id is positional: ") + Id, Id.StartsWith(TEXT("hidden-")));
      TestFalse("no instance id", Id.Contains(TEXT("::")));
    }
  }
  TestTrue("opponent hand delivered as placeholders", OpponentEntries > 0);

  FS09HudModel Hud;
  Hud.Build(Snap, Host, TSet<FString>(), Snap.SequenceNumber, Snap.SequenceNumber);
  const FS09PlayerPanel* Opp = Hud.OpponentPanel();
  TestNotNull("opponent panel", Opp);
  if (!Opp) return true;
  TestEqual("opponent hand decoded as a count only", Opp->Cards.Num(), 0);
  const FS09DeckList List = ListFor(*Opp, false, 1, 30);
  const FS09DeckPanelModel Model = FS09DeckPanelModel::Build(ES09DeckSide::Opponent, *Opp, &List);
  TestEqual("card backs = opponent hand count", Model.HandCount, OpponentEntries);
  for (const FS09DeckRow& Row : Model.Rows) {
    TestEqual(TEXT("no hand mark on the opponent deck: ") + Row.Card.CardId, Row.InHand, 0);
    TestEqual(TEXT("no 'left' on the opponent deck: ") + Row.Card.CardId, Row.Left, -1);
  }
  TestFalse("trace line names no card", Model.TraceLine().Contains(TEXT("Card ")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09DeckPanelOwnTest, "Unmatched.S09.DeckPanel.Own",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09DeckPanelOwnTest::RunTest(const FString&) {
  FS08Snapshot Snap;
  if (!LoadDeckFixture(Snap)) {
    AddError(TEXT("fixture gd035-move-open-host-view not loaded"));
    return true;
  }
  FS09HudModel Hud;
  Hud.Build(Snap, HostViewerId(Snap), TSet<FString>(), Snap.SequenceNumber, Snap.SequenceNumber);
  const FS09PlayerPanel* Own = Hud.ViewerPanel();
  TestNotNull("own panel", Own);
  if (!Own) return true;
  // composition = hand + discard + deck: 30 copies, one more copy of every seen card stays in the deck
  const int32 Copies = Own->HandCount + Own->Discard.Num() + Own->DeckCount;
  const FS09DeckList List = ListFor(*Own, true, 1, Copies);
  const FS09DeckPanelModel Model = FS09DeckPanelModel::Build(ES09DeckSide::Own, *Own, &List);
  TestTrue("list known", Model.bListKnown);
  TestEqual("copies", Model.Copies, Copies);
  TestEqual("deck count is the server's", Model.DeckCount, Own->DeckCount);
  TestEqual("nothing out of play", Model.OutOfPlay, 0);
  int32 Hand = 0, Discard = 0, Left = 0;
  for (const FS09DeckRow& Row : Model.Rows) {
    Hand += Row.InHand;
    Discard += Row.InDiscard;
    Left += Row.Left;
    TestEqual(TEXT("left = copies - hand - discard: ") + Row.Card.CardId, Row.Left,
              Row.Card.Count - Row.InHand - Row.InDiscard);
  }
  TestEqual("every own hand card is marked", Hand, Own->HandCount);
  TestEqual("every discard face is marked", Discard, Own->Discard.Num());
  TestEqual("the 'left' sum is the deck count", Left, Own->DeckCount);
  // copies side by side: one row per catalog id
  TSet<FString> Ids;
  for (const FS09DeckRow& Row : Model.Rows) {
    TestFalse(TEXT("one row per card: ") + Row.Card.CardId, Ids.Contains(Row.Card.CardId));
    Ids.Add(Row.Card.CardId);
  }
  // a card removed from the game: the deck is one shorter than hand + discard + left -> out of play 1
  FS09PlayerPanel Removed = *Own;
  Removed.DeckCount -= 1;
  TestEqual("one card out of play", FS09DeckPanelModel::Build(ES09DeckSide::Own, Removed, &List).OutOfPlay, 1);
  // stale counters: out of play is not claimed
  Removed.bDeckCountStale = true;
  TestEqual("stale deck count: out of play unknown", FS09DeckPanelModel::Build(ES09DeckSide::Own, Removed, &List).OutOfPlay,
            -1);
  // no list: counts only
  const FS09DeckPanelModel NoList = FS09DeckPanelModel::Build(ES09DeckSide::Own, *Own, nullptr);
  TestFalse("no list", NoList.bListKnown);
  TestEqual("no rows", NoList.Rows.Num(), 0);
  TestEqual("counts stay", NoList.DeckCount, Own->DeckCount);
  // a hand card missing from the list is counted, not invented as a row
  FS09DeckList Short = List;
  const FString Dropped = Own->Cards[0].CardId;
  Short.Cards.RemoveAll([&Dropped](const FS09DeckListCard& C) { return C.CardId == Dropped; });
  const FS09DeckPanelModel Unlisted = FS09DeckPanelModel::Build(ES09DeckSide::Own, *Own, &Short);
  TestTrue("unlisted counted", Unlisted.Unlisted > 0);
  TestNull("no row for the unlisted card", RowOf(Unlisted, Dropped));
  const FString Trace = Model.TraceLine();
  TestTrue("trace side", Trace.Contains(TEXT("side=own")));
  TestFalse("trace names no card id", Trace.Contains(Own->Cards[0].CardId));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09DeckPanelOpponentTest, "Unmatched.S09.DeckPanel.Opponent",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09DeckPanelOpponentTest::RunTest(const FString&) {
  FS09PlayerPanel Opp;
  Opp.PlayerId = TEXT("opp");
  Opp.HandCount = 4;
  Opp.DeckCount = 20;
  FS09CardView Hiss;
  Hiss.CardId = TEXT("cat-hiss");
  Hiss.InstanceId = TEXT("cat-hiss::0");
  Hiss.Name = TEXT("Hiss");
  Opp.Discard.Add(Hiss);
  Opp.Discard.Add(FS09HudFactory::HiddenCard(TEXT("hidden-1")));  // a committed combat card before the reveal
  // never decoded by FS09HudModel - injected here to prove the model does not read it
  FS09CardView Secret = Hiss;
  Secret.InstanceId = TEXT("cat-hiss::1");
  Opp.Cards.Add(Secret);
  FS09DeckList List;
  List.PlayerId = TEXT("opp");
  List.Cards = {ListCard(TEXT("cat-hiss"), 3), ListCard(TEXT("cat-gaze"), 2, TEXT("SCHEME"))};
  const FS09DeckPanelModel Model = FS09DeckPanelModel::Build(ES09DeckSide::Opponent, Opp, &List);
  const FS09DeckRow* Row = RowOf(Model, TEXT("cat-hiss"));
  TestNotNull("hiss row", Row);
  if (Row) {
    TestEqual("discard mark", Row->InDiscard, 1);
    TestEqual("no hand mark", Row->InHand, 0);
    TestEqual("no left", Row->Left, -1);
  }
  TestEqual("card backs", Model.HandCount, 4);
  TestEqual("face-down discard not attributed", Model.HiddenDiscard, 1);
  TestEqual("no out of play for the opponent", Model.OutOfPlay, -1);
  TestTrue("trace: backs", Model.TraceLine().Contains(TEXT("backs=4")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09DeckPanelParseTest, "Unmatched.S09.DeckPanel.Parse",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09DeckPanelParseTest::RunTest(const FString&) {
  const FString Body = TEXT(
      "{\"gameDeckLists\":[{\"playerId\":\"a\",\"total\":4,\"cards\":["
      "{\"cardId\":\"c1\",\"name\":\"Snipe\",\"nameRu\":null,\"cardType\":\"ATTACK\",\"attackValue\":4,"
      "\"defenseValue\":null,\"boostValue\":1,\"bannerName\":\"Medusa\",\"text\":null,\"count\":3},"
      "{\"cardId\":\"c2\",\"name\":\"Gaze\",\"cardType\":\"SCHEME\",\"attackValue\":null,\"defenseValue\":null,"
      "\"boostValue\":null,\"bannerName\":null,\"text\":\"Deal damage.\",\"count\":1}]},"
      "{\"playerId\":\"b\",\"total\":0,\"cards\":[]}]}");
  TSharedPtr<FJsonValue> Value;
  FString Problem;
  TestTrue("json", FS08Contracts::TryParseJsonValue(Body, Value, Problem));
  TArray<FS09DeckList> Lists;
  FString Error;
  TestTrue("parsed", S09DeckPanel::ParseDeckLists(Value->AsObject(), Lists, Error));
  TestEqual("two lists", Lists.Num(), 2);
  const FS09DeckList* A = S09DeckPanel::FindList(Lists, TEXT("a"));
  TestNotNull("list a", A);
  if (A && A->Cards.Num() == 2) {
    TestEqual("total", A->Total, 4);
    TestEqual("count", A->Cards[0].Count, 3);
    TestEqual("attack", A->Cards[0].AttackValue, 4);
    TestEqual("null defense -> -1", A->Cards[0].DefenseValue, -1);
    TestEqual("null name ru -> ''", A->Cards[0].NameRu, FString());
    TestEqual("text", A->Cards[1].Text, FString(TEXT("Deal damage.")));
    TestEqual("no boost -> -1", A->Cards[1].BoostValue, -1);
  }
  TestNull("unknown player", S09DeckPanel::FindList(Lists, TEXT("z")));
  TArray<FS09DeckList> Bad;
  TestFalse("missing field", S09DeckPanel::ParseDeckLists(MakeShared<FJsonObject>(), Bad, Error));
  TestFalse("error set", Error.IsEmpty());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09DeckPanelViewTest, "Unmatched.S09.DeckPanel.View",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09DeckPanelViewTest::RunTest(const FString&) {
  TestTrue("open within 100 ms", FS09DeckPanelView::OpenMs <= 100);
  TestEqual("close 150 ms", FS09DeckPanelView::CloseMs, 150);
  // the demand keys
  FS09DeckDemandInput In;
  TestEqual("nothing asks", S09DeckPanel::InputDemandKey(In), FString());
  In.bViewerTurn = true;
  In.TurnCount = 5;
  TestEqual("my turn", S09DeckPanel::InputDemandKey(In), FString(TEXT("turn:5")));
  In.bViewerDefends = true;
  In.CombatKey = TEXT("f1>f2");
  TestEqual("defense over turn", S09DeckPanel::DemandKind(S09DeckPanel::InputDemandKey(In)), FString(TEXT("defend")));
  In.OwnPendingId = TEXT("pe-1");
  TestEqual("choice over defense", S09DeckPanel::InputDemandKey(In), FString(TEXT("choice:pe-1")));
  In.OwnDiscardId = TEXT("hd-1");
  TestEqual("discard over choice", S09DeckPanel::DemandKind(S09DeckPanel::InputDemandKey(In)), FString(TEXT("discard")));
  In.bGameOver = true;
  TestEqual("game over first", S09DeckPanel::DemandKind(S09DeckPanel::InputDemandKey(In)), FString(TEXT("over")));

  FS09DeckPanelView View;
  TestEqual("closed at rest", View.Opacity(0), 0.0f);
  // the opponent's turn: open, ramp 80 ms
  TestTrue("opened", View.Toggle(ES09DeckSide::Own, 1000, FString()));
  TestEqual("open starts at 0", View.Opacity(1000), 0.0f);
  TestEqual("half way", View.Opacity(1040), 0.5f);
  TestEqual("fully open at 80 ms", View.Opacity(1080), 1.0f);
  // the other deck: content switch, no new fade
  TestTrue("switched", View.Open(ES09DeckSide::Opponent, 1100, FString()));
  TestEqual("still fully open", View.Opacity(1100), 1.0f);
  TestTrue("opponent side", View.Side() == ES09DeckSide::Opponent);
  // the same demand never closes; a new one does
  TestFalse("no demand", View.NoteDemand(FString(), 1200));
  TestTrue("my turn starts -> closes", View.NoteDemand(TEXT("turn:6"), 1300));
  TestFalse("closed", View.IsOpen());
  TestEqual("close ramp half", View.Opacity(1375), 0.5f);
  TestEqual("closed after 150 ms", View.Opacity(1450), 0.0f);
  // opened in my turn: stays while the turn goes on, closes on my deferred choice
  TestTrue("reopened in my turn", View.Toggle(ES09DeckSide::Own, 2000, TEXT("turn:6")));
  TestFalse("same turn keeps it", View.NoteDemand(TEXT("turn:6"), 2100));
  TestTrue("still open", View.IsOpen());
  TestFalse("opponent acting keeps it", View.NoteDemand(FString(), 2200));
  TestTrue("my choice closes it", View.NoteDemand(TEXT("choice:pe-9"), 2300));
  // toggle of the open side closes; a reopen mid-close starts from the current opacity
  View.Toggle(ES09DeckSide::Own, 3000, FString());
  TestFalse("toggle closes", View.Toggle(ES09DeckSide::Own, 3100, FString()));
  const float Mid = View.Opacity(3175);
  TestTrue("mid close", Mid > 0.0f && Mid < 1.0f);
  View.Toggle(ES09DeckSide::Own, 3175, FString());
  TestEqual("reopen from the current opacity", View.Opacity(3175), Mid);
  TestEqual("open again", View.Opacity(3255), 1.0f);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS

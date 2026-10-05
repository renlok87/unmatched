// DE-024 (W-23; 02 SD-42, SD-43; 02-ux-ui-spec §4.2, §7.1 UI-ACC-012): the hand limit models (S09HandLimit.h).
//   Unmatched.S09.HandLimit.Hint       - the rule toast shows once per match when the own hand grows to 7, closes on a
//                                        click or at the end of that turn or GAME_OVER, never again in the match; off
//                                        (UI-ACC-012) = never; the first snapshot (join / reconnect) never shows it;
//   Unmatched.S09.HandLimit.DiscardPick - one picker for the limit discard and an effect's DISCARD_CARDS: the whole hand
//                                        lit, picks marked, the same pick line; the limit discard has no cancel and
//                                        closes by itself when the server passes the turn;
//   Unmatched.S09.HandLimit.Settings   - UI-ACC-012 is saved in US08UserSettings (default on), the flag wins.
#if WITH_AUTOMATION_TESTS

#include "S09HandLimit.h"
#include "../S08/S08UserSettings.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/AutomationTest.h"

namespace S09HandLimitTest {
const TCHAR* const Me = TEXT("me");
const TCHAR* const Opp = TEXT("opp");

/** The viewer's hand of N cards; Discard > 0 adds metadata.pendingHandDiscard {count} in TURN_END. */
FS08Snapshot Snapshot(int32 Cards, int32 Discard, int32 Seq) {
  FS08Snapshot S;
  S.SequenceNumber = Seq;
  S.Phase = Discard > 0 ? TEXT("TURN_END") : TEXT("ACTION_MANEUVER");
  S.TurnCount = 3;
  S.CurrentTurnPlayerId = Me;
  TSharedRef<FJsonObject> Meta = MakeShared<FJsonObject>();
  Meta->SetNumberField(TEXT("actionsRemaining"), Discard > 0 ? 0 : 1);
  if (Discard > 0) {
    TSharedRef<FJsonObject> Pending = MakeShared<FJsonObject>();
    Pending->SetStringField(TEXT("id"), TEXT("discard:3:40"));
    Pending->SetStringField(TEXT("playerId"), Me);
    Pending->SetNumberField(TEXT("count"), Discard);
    Meta->SetObjectField(TEXT("pendingHandDiscard"), Pending);
  }
  S.Metadata = MakeShared<FJsonValueObject>(Meta);
  TArray<TSharedPtr<FJsonValue>> List;
  for (int32 I = 0; I < Cards; ++I) {
    TSharedRef<FJsonObject> C = MakeShared<FJsonObject>();
    C->SetStringField(TEXT("id"), FString::Printf(TEXT("c%d"), I));
    C->SetStringField(TEXT("cardId"), TEXT("cat"));
    C->SetStringField(TEXT("name"), FString::Printf(TEXT("Card %d"), I));
    C->SetStringField(TEXT("cardType"), TEXT("VERSATILE"));
    C->SetBoolField(TEXT("isVisible"), false);
    C->SetNumberField(TEXT("boostValue"), 1);
    List.Add(MakeShared<FJsonValueObject>(C));
  }
  TSharedRef<FJsonObject> Hand = MakeShared<FJsonObject>();
  Hand->SetArrayField(TEXT("cards"), List);
  Hand->SetNumberField(TEXT("maxSize"), 7);
  TSharedRef<FJsonObject> Hands = MakeShared<FJsonObject>();
  Hands->SetObjectField(Me, Hand);
  S.HandZones = MakeShared<FJsonValueObject>(Hands);
  return S;
}
}  // namespace S09HandLimitTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09HandLimitHintTest, "Unmatched.S09.HandLimit.Hint",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS09HandLimitHintTest::RunTest(const FString& Parameters) {
  const FString Own = TEXT("me#3");
  const FString Next = TEXT("opp#3");
  {
    FS09HandLimitHint Hint;
    FS09HandLimitHintEvent E = Hint.OnApplied(TEXT("g1"), Own, false, 5, 7, true);
    TestFalse(TEXT("first snapshot: no toast"), E.bShown || Hint.IsVisible());
    E = Hint.OnApplied(TEXT("g1"), Own, false, 6, 7, true);
    TestFalse(TEXT("6 cards: no toast"), E.bShown);
    E = Hint.OnApplied(TEXT("g1"), Own, false, 7, 7, true);
    TestTrue(TEXT("hand grows to 7: the toast shows"), E.bShown && Hint.IsVisible());
    TestEqual(TEXT("it speaks of the limit 7"), Hint.ShownLimit(), 7);
    // it never blocks: the model has no input gate; a merge of the same turn keeps it, a growing hand does not repeat it
    E = Hint.OnApplied(TEXT("g1"), Own, false, 8, 7, true);
    TestTrue(TEXT("same turn, 8 cards: still visible, no second show"), !E.bShown && Hint.IsVisible() &&
                                                                            E.Closed == ES09HintClose::None);
    // the end of the turn closes it
    E = Hint.OnApplied(TEXT("g1"), Next, false, 7, 7, true);
    TestTrue(TEXT("turn passed: closed by the turn end"), E.Closed == ES09HintClose::TurnEnd && !Hint.IsVisible());
    // once per match: dropping under the limit and growing to it again never shows it again
    Hint.OnApplied(TEXT("g1"), TEXT("me#4"), false, 5, 7, true);
    E = Hint.OnApplied(TEXT("g1"), TEXT("me#4"), false, 7, 7, true);
    TestFalse(TEXT("second time in the match: no toast"), E.bShown || Hint.IsVisible());
    TestTrue(TEXT("was shown in the match"), Hint.WasShown());
    // a new match starts over
    Hint.OnApplied(TEXT("g2"), Own, false, 5, 7, true);
    E = Hint.OnApplied(TEXT("g2"), Own, false, 7, 7, true);
    TestTrue(TEXT("new match: shown again"), E.bShown);
  }
  {
    FS09HandLimitHint Hint;
    Hint.OnApplied(TEXT("g1"), Own, false, 6, 7, true);
    Hint.OnApplied(TEXT("g1"), Own, false, 7, 7, true);
    TestTrue(TEXT("click closes"), Hint.Dismiss() && !Hint.IsVisible());
    TestFalse(TEXT("a second click does nothing"), Hint.Dismiss());
    const FS09HandLimitHintEvent E = Hint.OnApplied(TEXT("g1"), Next, false, 7, 7, true);
    TestTrue(TEXT("closed by the click: the turn end reports nothing"), E.Closed == ES09HintClose::None);
  }
  {
    FS09HandLimitHint Hint;
    Hint.OnApplied(TEXT("g1"), Own, false, 6, 7, true);
    Hint.OnApplied(TEXT("g1"), Own, false, 7, 7, true);
    const FS09HandLimitHintEvent E = Hint.OnApplied(TEXT("g1"), Own, true, 7, 7, true);
    TestTrue(TEXT("GAME_OVER closes it"), E.Closed == ES09HintClose::GameOver && !Hint.IsVisible());
  }
  {
    // the opponent's turn (an effect gives me cards): shown, closed when THAT turn ends
    FS09HandLimitHint Hint;
    Hint.OnApplied(TEXT("g1"), Next, false, 6, 7, true);
    TestTrue(TEXT("grown in the opponent's turn: shown"), Hint.OnApplied(TEXT("g1"), Next, false, 7, 7, true).bShown);
    TestTrue(TEXT("closed at my turn start"),
             Hint.OnApplied(TEXT("g1"), TEXT("me#4"), false, 7, 7, true).Closed == ES09HintClose::TurnEnd);
  }
  {
    // UI-ACC-012 off: never
    FS09HandLimitHint Hint;
    Hint.OnApplied(TEXT("g1"), Own, false, 6, 7, false);
    const FS09HandLimitHintEvent E = Hint.OnApplied(TEXT("g1"), Own, false, 7, 7, false);
    TestFalse(TEXT("hints off: no toast"), E.bShown || Hint.IsVisible() || Hint.WasShown());
  }
  {
    // a jump over the limit (6 -> 8) shows it too; a reconnect that starts with 7 does not
    FS09HandLimitHint Hint;
    Hint.OnApplied(TEXT("g1"), Own, false, 6, 7, true);
    TestTrue(TEXT("6 -> 8: shown"), Hint.OnApplied(TEXT("g1"), Own, false, 8, 7, true).bShown);
    FS09HandLimitHint Rejoin;
    TestFalse(TEXT("first snapshot with 7: not shown"), Rejoin.OnApplied(TEXT("g1"), Own, false, 7, 7, true).bShown);
    TestFalse(TEXT("still 7: not shown"), Rejoin.OnApplied(TEXT("g1"), Own, false, 7, 7, true).bShown);
  }
  TestEqual(TEXT("limit default"), FS09HandLimitHint::LimitOf(0), 7);
  TestEqual(TEXT("limit from maxSize"), FS09HandLimitHint::LimitOf(10), 10);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09HandLimitDiscardPickTest, "Unmatched.S09.HandLimit.DiscardPick",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS09HandLimitDiscardPickTest::RunTest(const FString& Parameters) {
  using namespace S09HandLimitTest;
  const FS08BoardModel Board;
  const TArray<FS08BoardFighter> Fighters;
  FS09CommandUi Ui;
  Ui.ViewerId = Me;
  // no discard: nothing lit
  Ui.OnSnapshot(Snapshot(6, 0, 30), Board, Fighters);
  FS09DiscardPick Pick = FS09DiscardPick::From(Ui);
  TestFalse(TEXT("no discard open"), Pick.IsOpen());
  TestTrue(TEXT("no discard: no mark"), Pick.Mark(TEXT("c0"), false) == ES09HandMark::None);

  // the server keeps the turn in TURN_END with pendingHandDiscard right after the last action: the picker is open at once
  const FS08Snapshot Limit = Snapshot(9, 2, 31);
  TestTrue(TEXT("discard opens on the snapshot"), Ui.OnSnapshot(Limit, Board, Fighters));
  Pick = FS09DiscardPick::From(Ui);
  TestTrue(TEXT("limit discard"), Pick.Source == ES09DiscardSource::HandLimit && Pick.Need == 2);
  TestTrue(TEXT("mandatory"), Pick.IsMandatory());
  TestTrue(TEXT("the whole hand lit"), Pick.Mark(TEXT("c0"), false) == ES09HandMark::Candidate &&
                                           Pick.Mark(TEXT("c8"), false) == ES09HandMark::Candidate);
  TestTrue(TEXT("hidden placeholder never lit"), Pick.Mark(TEXT("c0"), true) == ES09HandMark::None);
  TestEqual(TEXT("pick line"), Pick.PickLine(), FString(TEXT("CHOOSE 2 CARDS: selected 0/2 (2 more)")));
  FString Reason;
  TestTrue(TEXT("click picks"), Ui.ToggleDiscardCard(TEXT("c3"), Limit, Reason));
  Pick = FS09DiscardPick::From(Ui);
  TestTrue(TEXT("picked marked"), Pick.Mark(TEXT("c3"), false) == ES09HandMark::Picked && Pick.Left() == 1);
  // no cancel: the local clear leaves the discard open with its picks; End Turn explains the count
  Ui.CancelDraft();
  TestTrue(TEXT("cancel does not close the discard"), Ui.Mode == ES09CommandMode::DiscardDraft &&
                                                          Ui.DiscardSelection.Contains(TEXT("c3")));
  TestEqual(TEXT("no manual end turn: the count reason"), Ui.EndTurnReason(Limit).Key, FName(TEXT("why.discard.count")));
  // a re-apply of the same seq keeps the picks
  Ui.OnSnapshot(Limit, Board, Fighters);
  TestTrue(TEXT("re-apply keeps the pick"), Ui.DiscardSelection.Contains(TEXT("c3")));
  TestTrue(TEXT("second pick"), Ui.ToggleDiscardCard(TEXT("c5"), Limit, Reason));
  FS09DiscardCommand Command;
  TestTrue(TEXT("confirm at the exact count"), Ui.ConfirmDiscard(Limit, Command, Reason));
  TestTrue(TEXT("complete"), FS09DiscardPick::From(Ui).IsComplete());
  // the server passes the turn by itself: the next snapshot has no pendingHandDiscard and the picker closes
  FS08Snapshot Passed = Snapshot(7, 0, 32);
  Passed.CurrentTurnPlayerId = Opp;
  Ui.OnSnapshot(Passed, Board, Fighters);
  TestFalse(TEXT("turn passed: picker closed"), FS09DiscardPick::From(Ui).IsOpen());

  // an effect's DISCARD_CARDS uses the same picker
  FS09CommandUi Effect;
  Effect.ViewerId = Me;
  Effect.Mode = ES09CommandMode::PendingChoice;
  Effect.bHasPendingChoice = true;
  Effect.PendingChoice.Type = TEXT("DISCARD_CARDS");
  Effect.PendingChoice.PlayerId = Me;
  Effect.PendingChoice.Value = 1;
  Effect.PendingChoice.bHasValue = true;
  Effect.PendingCardIds = {TEXT("c1")};
  Pick = FS09DiscardPick::From(Effect);
  TestTrue(TEXT("effect discard"), Pick.Source == ES09DiscardSource::Effect && Pick.Need == 1 && Pick.IsMandatory());
  TestTrue(TEXT("effect: same marks"), Pick.Mark(TEXT("c1"), false) == ES09HandMark::Picked &&
                                           Pick.Mark(TEXT("c2"), false) == ES09HandMark::Candidate);
  TestEqual(TEXT("effect: same pick line"), Pick.PickLine(), FString(TEXT("CHOOSE 1 CARD: selected 1/1 (0 more)")));
  Effect.PendingChoice.bOptional = true;
  TestFalse(TEXT("an optional effect discard is not mandatory"), FS09DiscardPick::From(Effect).IsMandatory());
  Effect.PendingChoice.Type = TEXT("BOOST_CHOICE");
  TestFalse(TEXT("another pending type is not a discard"), FS09DiscardPick::From(Effect).IsOpen());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09HandLimitSettingsTest, "Unmatched.S09.HandLimit.Settings",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS09HandLimitSettingsTest::RunTest(const FString& Parameters) {
  TestTrue(TEXT("UI-ACC-012 default on"), GetDefault<US08UserSettings>()->bRuleHints);
  TestTrue(TEXT("no flag: saved on"), US08UserSettings::ResolveRuleHints(true, TEXT("-game")));
  TestFalse(TEXT("no flag: saved off"), US08UserSettings::ResolveRuleHints(false, TEXT("-game")));
  TestFalse(TEXT("-S08RuleHints=off"), US08UserSettings::ResolveRuleHints(true, TEXT("-S08RuleHints=off")));
  TestFalse(TEXT("-S08RuleHints=0"), US08UserSettings::ResolveRuleHints(true, TEXT("-S08RuleHints=0")));
  TestTrue(TEXT("-S08RuleHints=On"), US08UserSettings::ResolveRuleHints(false, TEXT("-S08RuleHints=On")));
  TestFalse(TEXT("bogus keeps saved"), US08UserSettings::ResolveRuleHints(false, TEXT("-S08RuleHints=maybe")));
  US08UserSettings* Temp = NewObject<US08UserSettings>(GetTransientPackage());
  Temp->bRuleHints = false;
  Temp->SetToDefaults();
  TestTrue(TEXT("SetToDefaults turns the hints back on"), Temp->bRuleHints);
  Temp->MarkAsGarbage();
  return true;
}

#endif  // WITH_AUTOMATION_TESTS

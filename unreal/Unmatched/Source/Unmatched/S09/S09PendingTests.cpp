// GD-035 automation tests: the pending-effect queue-head choice UI over REAL
// viewer-projected fixtures captured live
// (docs/game-design/evidence/S09/fixtures/gd035-*). Covers every starter-matrix
// type: MOVE (queue semantics), DECK_TOP_PICK PICK/ORDER (owner privacy),
// CHOOSE_SPACE stage 1 (live gap: boards carry no zone data) and stage 2
// (synthesized head per the server model), TARGET_FIGHTER / CHOOSE_ONE /
// DISCARD_CARDS / BOOST_CHOICE (synthesized heads over live snapshots - the
// live duel cannot reach them reliably, see the evidence README), stale-head /
// wrong-owner / mandatory-decline denial, exact-instance validation, malformed
// pendingEffects metadata, and the same-seq echo guard.
// Synthesis rule (GD-035 constraint): a synthesized head keeps the REAL server
// projection (board, hands, fighters, seq) and swaps only the
// metadata.pendingEffects entry to the server-model shape of another type -
// the client logic under test is identical either way; every synthesized case
// is labeled "synthesized" in the test name.
#if WITH_AUTOMATION_TESTS

#include "S09ManeuverUi.h"
#include "S09HudModel.h"
#include "S09PendingPresent.h"
#include "../S08/S08WhyText.h"
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
bool LoadS09PendingFixture(const FString& Name, FS08Snapshot& OutSnapshot) {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S09Fixtures="), Dir) || Dir.IsEmpty()) {
    Dir = FPaths::Combine(FPaths::ProjectDir(),
                          TEXT("../../docs/game-design/evidence/S09/fixtures"));
  }
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *FPaths::Combine(Dir, Name + TEXT(".json")))) {
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

bool PendingViewerIds(const FS08Snapshot& Snapshot, FString& OutFirst, FString& OutSecond) {
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

/** Replaces metadata.pendingEffects with a single given head (deep-copies the
 *  metadata object; everything else of the REAL projection is untouched). */
FS08Snapshot WithPendingHead(const FS08Snapshot& Snapshot,
                             const TSharedRef<FJsonObject>& Effect) {
  FS08Snapshot Out = Snapshot;
  const TSharedRef<FJsonObject> Meta =
      MakeShared<FJsonObject>(*(Snapshot.Metadata->AsObject()));
  TArray<TSharedPtr<FJsonValue>> Effects;
  Effects.Add(MakeShared<FJsonValueObject>(Effect));
  Meta->SetArrayField(TEXT("pendingEffects"), Effects);
  Out.Metadata = MakeShared<FJsonValueObject>(Meta);
  return Out;
}

TSharedRef<FJsonObject> MakeHead(const FString& Id, const FString& PlayerId,
                                 const FString& Type) {
  const TSharedRef<FJsonObject> Head = MakeShared<FJsonObject>();
  Head->SetStringField(TEXT("id"), Id);
  Head->SetStringField(TEXT("playerId"), PlayerId);
  Head->SetStringField(TEXT("type"), Type);
  return Head;
}

/** Adds zones[] to the given cells of the board projection (synthesis for the
 *  stage-1 zone rule: live boards ship NO zone data - see the README gap).
 *  Live shape: boardState.cells is row-major cells[y][x]. */
FS08Snapshot WithBoardZones(const FS08Snapshot& Snapshot,
                            const TArray<TPair<int32, int32>>& Cells,
                            const FString& Zone) {
  FS08Snapshot Out = Snapshot;
  const TSharedRef<FJsonObject> Board =
      MakeShared<FJsonObject>(*(Snapshot.BoardState->AsObject()));
  const TArray<TSharedPtr<FJsonValue>>* Rows = nullptr;
  if (!Board->TryGetArrayField(TEXT("cells"), Rows)) return Out;
  for (const TPair<int32, int32>& Cell : Cells) {
    if (Cell.Value < 0 || Cell.Value >= Rows->Num()) continue;
    const TArray<TSharedPtr<FJsonValue>>* RowCells = nullptr;
    if (!(*Rows)[Cell.Value]->TryGetArray(RowCells)) continue;
    if (Cell.Key < 0 || Cell.Key >= RowCells->Num()) continue;
    const TSharedPtr<FJsonObject> CellObject = (*RowCells)[Cell.Key]->AsObject();
    if (!CellObject.IsValid()) continue;
    TArray<TSharedPtr<FJsonValue>> Zones;
    Zones.Add(MakeShared<FJsonValueString>(Zone));
    CellObject->SetArrayField(TEXT("zones"), Zones);
  }
  Out.BoardState = MakeShared<FJsonValueObject>(Board);
  return Out;
}
} // namespace

// ---- 1. parser matrix: every live fixture head decodes with its real fields
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09PendingParserMatrixTest,
    "Unmatched.S09.PENDING parser matrix (live fixtures: types, stages, privacy fields)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09PendingParserMatrixTest::RunTest(const FString&) {
  struct Expected {
    const TCHAR* Fixture;
    const TCHAR* Type;
    int32 Stage;      // 0 = absent
    const TCHAR* Mode; // "" = absent
  };
  const Expected Cases[] = {
      {TEXT("gd035-move-open-host-view"), TEXT("MOVE"), 0, TEXT("")},
      {TEXT("gd035-move-open-joiner-view"), TEXT("MOVE"), 0, TEXT("")},
      {TEXT("gd035-deckpick-owner-view"), TEXT("DECK_TOP_PICK"), 0, TEXT("PICK")},
      {TEXT("gd035-deckpick-opponent-view"), TEXT("DECK_TOP_PICK"), 0, TEXT("PICK")},
      {TEXT("gd035-deckorder-owner-view"), TEXT("DECK_TOP_PICK"), 0, TEXT("ORDER")},
      {TEXT("gd035-space-stage1-joiner-view"), TEXT("CHOOSE_SPACE"), 1, TEXT("")},
      {TEXT("gd035-space-stage1-host-view"), TEXT("CHOOSE_SPACE"), 1, TEXT("")},
  };
  for (const Expected& Case : Cases) {
    FS08Snapshot Snapshot;
    if (!LoadS09PendingFixture(Case.Fixture, Snapshot)) {
      AddError(FString::Printf(TEXT("fixture %s not loaded"), Case.Fixture));
      continue;
    }
    TArray<FS08PendingEffect> Effects;
    TestTrue(FString(Case.Fixture) + TEXT(" pendingEffects parsed"),
             FS08Contracts::PendingEffects(Snapshot, Effects));
    if (Effects.Num() < 1) continue;
    TestEqual(FString(Case.Fixture) + TEXT(" head type"), Effects[0].Type,
              FString(Case.Type));
    if (Case.Stage > 0) {
      TestEqual(FString(Case.Fixture) + TEXT(" stage"), Effects[0].Stage, Case.Stage);
    }
    if (FCString::Strlen(Case.Mode) > 0) {
      TestEqual(FString(Case.Fixture) + TEXT(" mode"), Effects[0].Mode,
                FString(Case.Mode));
    }
    TestFalse(FString(Case.Fixture) + TEXT(" id present"), Effects[0].Id.IsEmpty());
    TestFalse(FString(Case.Fixture) + TEXT(" playerId present"),
              Effects[0].PlayerId.IsEmpty());
  }

  // DECK_TOP_PICK privacy over the SAME seq pair of views:
  // owner ships revealedCards (exact faces); opponent ships revealedCount.
  FS08Snapshot OwnerView, OpponentView;
  if (LoadS09PendingFixture(TEXT("gd035-deckpick-owner-view"), OwnerView) &&
      LoadS09PendingFixture(TEXT("gd035-deckpick-opponent-view"), OpponentView)) {
    TArray<FS08PendingEffect> OwnerEffects, OpponentEffects;
    FS08Contracts::PendingEffects(OwnerView, OwnerEffects);
    FS08Contracts::PendingEffects(OpponentView, OpponentEffects);
    TestTrue(TEXT("owner revealedCards array"), OwnerEffects[0].RevealedCards.IsValid());
    const TArray<TSharedPtr<FJsonValue>>* Revealed = nullptr;
    TestTrue(TEXT("owner revealedCards decodes"),
             OwnerEffects[0].RevealedCards->TryGetArray(Revealed) && Revealed &&
             Revealed->Num() > 0);
    TestFalse(TEXT("opponent revealedCards stripped"),
              OpponentEffects[0].RevealedCards.IsValid());
    TestTrue(TEXT("opponent revealedCount present"),
             OpponentEffects[0].bHasRevealedCount && OpponentEffects[0].RevealedCount > 0);
    if (Revealed) {
      TestEqual(TEXT("counts agree across seats"),
                OpponentEffects[0].RevealedCount, Revealed->Num());
    }
  }
  return true;
}

// ---- 2. malformed pendingEffects metadata: never dereference blindly
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09PendingMalformedMetadataTest,
    "Unmatched.S09.PENDING malformed pendingEffects metadata (no crash, entries degrade)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09PendingMalformedMetadataTest::RunTest(const FString&) {
  FS08Snapshot Base;
  if (!LoadS09PendingFixture(TEXT("gd035-move-open-host-view"), Base)) {
    AddError(TEXT("base fixture not loaded"));
    return true;
  }
  FString Host;
  {
    FString Second;
    PendingViewerIds(Base, Host, Second);
  }

  auto SetRawPending = [&](const TSharedPtr<FJsonValue>& Raw) {
    FS08Snapshot Out = Base;
    const TSharedRef<FJsonObject> Meta =
        MakeShared<FJsonObject>(*(Base.Metadata->AsObject()));
    Meta->SetField(TEXT("pendingEffects"), Raw);
    Out.Metadata = MakeShared<FJsonValueObject>(Meta);
    return Out;
  };

  // pendingEffects is a plain string / object / null instead of an array.
  {
    TArray<FS08PendingEffect> Effects;
    TestFalse(TEXT("string pendingEffects ignored"),
              FS08Contracts::PendingEffects(
                  SetRawPending(MakeShared<FJsonValueString>(TEXT("oops"))), Effects));
  }
  {
    TArray<FS08PendingEffect> Effects;
    TestFalse(TEXT("object pendingEffects ignored"),
              FS08Contracts::PendingEffects(
                  SetRawPending(
                      MakeShared<FJsonValueObject>(MakeShared<FJsonObject>())),
                  Effects));
  }

  // Array entries: non-object entries and entries without an id are dropped;
  // a valid entry with malformed optional fields (anchor not an object,
  // revealedCards not an array, value as string) still decodes.
  {
    TArray<TSharedPtr<FJsonValue>> Raw;
    Raw.Add(MakeShared<FJsonValueString>(TEXT("garbage")));          // not an object
    Raw.Add(MakeShared<FJsonValueNumber>(42));                      // not an object
    const TSharedRef<FJsonObject> NoId = MakeHead(TEXT(""), Host, TEXT("MOVE"));
    Raw.Add(MakeShared<FJsonValueObject>(NoId));                    // id missing
    const TSharedRef<FJsonObject> BadFields = MakeHead(TEXT("bad-1"), Host, TEXT("CHOOSE_SPACE"));
    BadFields->SetNumberField(TEXT("stage"), 2);
    BadFields->SetStringField(TEXT("anchor"), FString(TEXT("not-an-object"))); // malformed anchor
    BadFields->SetStringField(TEXT("value"), FString(TEXT("2")));             // int-as-string
    Raw.Add(MakeShared<FJsonValueObject>(BadFields));
    FS08Snapshot Snapshot = SetRawPending(MakeShared<FJsonValueArray>(Raw));
    TArray<FS08PendingEffect> Effects;
    TestTrue(TEXT("malformed array parses"), FS08Contracts::PendingEffects(Snapshot, Effects));
    TestEqual(TEXT("only the id-bearing entry survives"), Effects.Num(), 1);
    if (Effects.Num() == 1) {
      TestEqual(TEXT("survivor id"), Effects[0].Id, FString(TEXT("bad-1")));
      TestFalse(TEXT("malformed anchor degrades to absent"), Effects[0].bHasAnchor);
      TestTrue(TEXT("int-as-string value tolerated"),
               Effects[0].bHasValue && Effects[0].Value == 2);
    }
  }

  // The UI itself must not enter PendingChoice from a body whose only entries
  // were dropped (empty queue after filtering).
  {
    TArray<TSharedPtr<FJsonValue>> Raw;
    Raw.Add(MakeShared<FJsonValueString>(TEXT("garbage")));
    FS08Snapshot Snapshot = SetRawPending(MakeShared<FJsonValueArray>(Raw));
    FS08BoardModel Board;
    TArray<FS08BoardFighter> Fighters;
    FS08BoardModel::DecodeFighters(Snapshot.Fighters, Fighters);
    Board.Decode(Snapshot.BoardState);
    FS09CommandUi Ui;
    Ui.ViewerId = Host;
    Ui.OnSnapshot(Snapshot, Board, Fighters);
    TestEqual(TEXT("no mode from dropped entries"),
              static_cast<int32>(Ui.Mode), static_cast<int32>(ES09CommandMode::None));
  }
  return true;
}

// ---- 3. MOVE: owner mode, legal fighters, zero-step cell, wrong owner
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09PendingMoveQueueTest,
    "Unmatched.S09.PENDING MOVE queue: owner gates, legal fighter/cell, zero-step, stale head",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09PendingMoveQueueTest::RunTest(const FString&) {
  FS08Snapshot OwnerView, WaitView;
  if (!LoadS09PendingFixture(TEXT("gd035-move-open-host-view"), OwnerView) ||
      !LoadS09PendingFixture(TEXT("gd035-move-open-joiner-view"), WaitView)) {
    AddError(TEXT("fixtures not loaded"));
    return true;
  }
  FString Host, Joiner;
  PendingViewerIds(OwnerView, Host, Joiner);
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  FS08BoardModel::DecodeFighters(OwnerView.Fighters, Fighters);
  Board.Decode(OwnerView.BoardState);

  FS09CommandUi Ui;
  Ui.ViewerId = Host;
  Ui.bCommandInFlight = false;
  Ui.OnSnapshot(OwnerView, Board, Fighters);
  TestEqual(TEXT("owner enters PendingChoice"), static_cast<int32>(Ui.Mode),
            static_cast<int32>(ES09CommandMode::PendingChoice));
  TestTrue(TEXT("queue parsed"), Ui.PendingQueue.Num() >= 1);
  const FS08PendingEffect Head = Ui.PendingQueue[0];

  // The other seat: no choice mode from the same body, and the queue blocks
  // its maneuver/attack/resolve (server rejects all three while open).
  FS09CommandUi WaitUi;
  WaitUi.ViewerId = Joiner;
  WaitUi.OnSnapshot(WaitView, Board, Fighters);
  TestEqual(TEXT("opponent seat stays in None"),
            static_cast<int32>(WaitUi.Mode), static_cast<int32>(ES09CommandMode::None));
  FString Reason;
  TestFalse(TEXT("queue blocks beginManeuver for BOTH seats"),
            WaitUi.CanBeginManeuver(WaitView, Reason) || Ui.CanBeginManeuver(OwnerView, Reason));
  TestFalse(TEXT("queue blocks the attack draft for BOTH seats"),
            WaitUi.CanOpenAttackDraft(WaitView, Reason) ||
                Ui.CanOpenAttackDraft(OwnerView, Reason));
  TestFalse(TEXT("queue blocks combat resolve for BOTH seats"),
            WaitUi.CanResolveCombat(WaitView, Reason) ||
                Ui.CanResolveCombat(OwnerView, Reason));

  // Legal fighters: exactly the head's fighterIds owned by the viewer.
  TArray<FString> Legal;
  TestTrue(TEXT("legal fighters enumerated"), Ui.PendingLegalFighters(Fighters, Legal));
  TestTrue(TEXT("legal fighters are the head list"),
           Head.FighterIds.Num() == 0 || Legal.Num() == 1);
  const FString LegalId = Legal[0];
  const FS08BoardFighter* Mover =
      FS08BoardModel::FighterAt(Fighters, 0, 0, TEXT("")); // placeholder, refound below
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (Fighter.Id == LegalId) Mover = &Fighter;
  }
  if (!TestNotNull(TEXT("mover found"), Mover)) return true;
  TestTrue(TEXT("legal fighter selectable"),
           Ui.SelectPendingFighter(LegalId, OwnerView, Fighters, Reason));
  // An enemy fighter is never legal for an own-move head.
  FString EnemyId;
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (Fighter.OwnerId != Host && Fighter.IsAlive()) { EnemyId = Fighter.Id; break; }
  }
  if (!EnemyId.IsEmpty()) {
    TestFalse(TEXT("enemy fighter rejected"),
              Ui.SelectPendingFighter(EnemyId, OwnerView, Fighters, Reason));
  }
  // A tail (non-head) queue entry's fighter is stale-head: only the HEAD is
  // actionable, so a fighter in the tail but not the head must be rejected.
  if (Ui.PendingQueue.Num() > 1) {
    const FS08PendingEffect Tail = Ui.PendingQueue[1];
    FString TailOnly;
    for (const FString& Id : Tail.FighterIds) {
      if (!Head.FighterIds.Contains(Id)) { TailOnly = Id; break; }
    }
    if (!TailOnly.IsEmpty()) {
      TestFalse(TEXT("tail entry is not actionable (stale head)"),
                Ui.SelectPendingFighter(TailOnly, OwnerView, Fighters, Reason));
    }
  }

  // Legal cells: the mover's own cell stays legal (zero-step "up to N").
  const TSet<uint64> Cells = Ui.ComputePendingCells(OwnerView, Board, Fighters);
  TestTrue(TEXT("cells enumerated"), Cells.Num() > 0);
  TestTrue(TEXT("zero-step own cell legal"),
           Cells.Contains(FS08BoardModel::CellKey(Mover->X, Mover->Y)));
  TestTrue(TEXT("own cell selectable"),
           Ui.SelectPendingCell(Mover->X, Mover->Y, OwnerView, Board, Fighters, Reason));
  // A distant cell beyond the allowance is illegal.
  int32 FarX = -1, FarY = -1;
  for (int32 Y = 0; Y < Board.Height && FarX < 0; Y++) {
    for (int32 X = 0; X < Board.Width; X++) {
      const FS08Cell* Cell = Board.CellAt(X, Y);
      if (Cell && Cell->IsPassable() &&
          !Cells.Contains(FS08BoardModel::CellKey(X, Y))) {
        FarX = X; FarY = Y; break;
      }
    }
  }
  if (FarX >= 0) {
    TestFalse(TEXT("out-of-reach cell rejected"),
              Ui.SelectPendingCell(FarX, FarY, OwnerView, Board, Fighters, Reason));
  }

  // Confirm builds the exact server payload from the HEAD entry only.
  FS09PendingChoiceCommand Command;
  TestTrue(TEXT("zero-step confirm legal"),
           Ui.ConfirmPendingChoice(OwnerView, false, Command, Reason));
  TestEqual(TEXT("command effect id = HEAD id"), Command.EffectId, Head.Id);
  TestEqual(TEXT("command fighter"), Command.FighterId, LegalId);
  TestTrue(TEXT("command has cell"), Command.bHasCell);
  TestEqual(TEXT("command cell x"), Command.CellX, Mover->X);
  TestEqual(TEXT("command cell y"), Command.CellY, Mover->Y);
  TestFalse(TEXT("mandatory MOVE cannot be declined"),
            Ui.ConfirmPendingChoice(OwnerView, true, Command, Reason));
  return true;
}

// ---- 4. DECK_TOP_PICK: PICK exact revealed ids, ORDER full permutation
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09PendingDeckTopTest,
    "Unmatched.S09.PENDING DECK_TOP_PICK: PICK exact ids, ORDER full order, opponent privacy",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09PendingDeckTopTest::RunTest(const FString&) {
  FS08Snapshot OwnerView, OpponentView, OrderView;
  if (!LoadS09PendingFixture(TEXT("gd035-deckpick-owner-view"), OwnerView) ||
      !LoadS09PendingFixture(TEXT("gd035-deckpick-opponent-view"), OpponentView) ||
      !LoadS09PendingFixture(TEXT("gd035-deckorder-owner-view"), OrderView)) {
    AddError(TEXT("fixtures not loaded"));
    return true;
  }
  FString Host, Joiner;
  PendingViewerIds(OwnerView, Host, Joiner);
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  FS08BoardModel::DecodeFighters(OwnerView.Fighters, Fighters);
  Board.Decode(OwnerView.BoardState);

  // PICK (owner): exact revealed instance ids only.
  FS09CommandUi Ui;
  Ui.ViewerId = Joiner; // the Prophecy player is the joiner seat
  Ui.OnSnapshot(OwnerView, Board, Fighters);
  TestEqual(TEXT("PICK mode opens for the owner"), static_cast<int32>(Ui.Mode),
            static_cast<int32>(ES09CommandMode::PendingChoice));
  TestEqual(TEXT("PICK head type"), Ui.PendingChoice.Type,
            FString(TEXT("DECK_TOP_PICK")));
  TArray<FS09CardView> Revealed;
  TestTrue(TEXT("owner decodes revealed cards"), Ui.PendingRevealedCards(Revealed));
  const int32 Need = Ui.PendingChoice.bHasValue ? Ui.PendingChoice.Value : 2;
  TestTrue(TEXT("fixture carries at least the pick count"), Revealed.Num() >= Need);
  FString Reason;
  // A hand card is NOT a legal pick (exact revealed instances only).
  const TArray<FString> Hand = Ui.PendingOwnHandIds(OwnerView);
  for (const FString& Id : Hand) {
    bool bRevealed = false;
    for (const FS09CardView& Card : Revealed) {
      if (Card.InstanceId == Id) bRevealed = true;
    }
    if (!bRevealed) {
      TestFalse(TEXT("hand card rejected for DECK_TOP_PICK"),
                Ui.TogglePendingCard(Id, OwnerView, Reason));
      break;
    }
  }
  // Pick exactly Need revealed cards (a limit check blocks over-picking).
  for (int32 i = 0; i < Need; i++) {
    TestTrue(FString::Printf(TEXT("revealed pick %d legal"), i),
             Ui.TogglePendingCard(Revealed[i].InstanceId, OwnerView, Reason));
  }
  if (Revealed.Num() > Need) {
    TestFalse(TEXT("over-pick blocked"),
              Ui.TogglePendingCard(Revealed[Need].InstanceId, OwnerView, Reason));
  }
  FS09PendingChoiceCommand Command;
  TestTrue(TEXT("PICK confirm"), Ui.ConfirmPendingChoice(OwnerView, false, Command, Reason));
  TestEqual(TEXT("PICK exact count"), Command.CardIds.Num(), Need);
  for (int32 i = 0; i < Need; i++) {
    TestEqual(FString::Printf(TEXT("PICK id %d"), i), Command.CardIds[i],
              Revealed[i].InstanceId);
  }

  // PICK (opponent): revealedCards never shipped - the seat cannot pick and
  // stays out of the choice mode entirely.
  FS09CommandUi OpponentUi;
  OpponentUi.ViewerId = Host;
  OpponentUi.OnSnapshot(OpponentView, Board, Fighters);
  TestEqual(TEXT("opponent seat stays in None"),
            static_cast<int32>(OpponentUi.Mode), static_cast<int32>(ES09CommandMode::None));
  TArray<FS09CardView> OpponentRevealed;
  TestFalse(TEXT("opponent has no revealed cards"),
            OpponentUi.PendingRevealedCards(OpponentRevealed));

  // ORDER: the FULL permutation of all revealed ids, pick sequence = the
  // top->bottom return order.
  FS09CommandUi OrderUi;
  OrderUi.ViewerId = Joiner;
  OrderUi.OnSnapshot(OrderView, Board, Fighters);
  TestEqual(TEXT("ORDER mode"), OrderUi.PendingChoice.Mode, FString(TEXT("ORDER")));
  TArray<FS09CardView> OrderRevealed;
  TestTrue(TEXT("ORDER revealed decode"), OrderUi.PendingRevealedCards(OrderRevealed));
  TestTrue(TEXT("ORDER carries >= 2 cards"), OrderRevealed.Num() >= 2);
  // Reverse order picks: the return order must follow the pick sequence.
  for (int32 i = OrderRevealed.Num() - 1; i >= 0; i--) {
    TestTrue(FString::Printf(TEXT("ORDER pick %d"), i),
             OrderUi.TogglePendingCard(OrderRevealed[i].InstanceId, OrderView, Reason));
  }
  FS09PendingChoiceCommand OrderCommand;
  TestTrue(TEXT("ORDER confirm"), OrderUi.ConfirmPendingChoice(OrderView, false, OrderCommand, Reason));
  TestEqual(TEXT("ORDER full permutation"), OrderCommand.CardIds.Num(),
            OrderRevealed.Num());
  for (int32 i = 0; i < OrderRevealed.Num(); i++) {
    TestEqual(FString::Printf(TEXT("ORDER position %d"), i), OrderCommand.CardIds[i],
              OrderRevealed[OrderRevealed.Num() - 1 - i].InstanceId);
  }
  return true;
}

// ---- 5. CHOOSE_SPACE: live stage 1 + synthesized zone rule + stage 2
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09PendingChooseSpaceTest,
    "Unmatched.S09.PENDING CHOOSE_SPACE: live stage-1 zones, synthesized zones, stage-2 anchor",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09PendingChooseSpaceTest::RunTest(const FString&) {
  FS08Snapshot OwnerView, WaitView;
  if (!LoadS09PendingFixture(TEXT("gd035-space-stage1-joiner-view"), OwnerView) ||
      !LoadS09PendingFixture(TEXT("gd035-space-stage1-host-view"), WaitView)) {
    AddError(TEXT("fixtures not loaded"));
    return true;
  }
  FString Host, Joiner;
  PendingViewerIds(OwnerView, Host, Joiner);
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  FS08BoardModel::DecodeFighters(OwnerView.Fighters, Fighters);
  Board.Decode(OwnerView.BoardState);

  // The live board contains zones. Stage 1 must offer cells in Merlin's zone.
  FS09CommandUi Ui;
  Ui.ViewerId = Joiner;
  Ui.OnSnapshot(OwnerView, Board, Fighters);
  TestEqual(TEXT("stage-1 mode opens for the owner"), static_cast<int32>(Ui.Mode),
            static_cast<int32>(ES09CommandMode::PendingChoice));
  TestEqual(TEXT("stage-1 stage"), Ui.PendingChoice.Stage, 1);
  TestFalse(TEXT("live zone fighter name parsed"),
            Ui.PendingChoice.ZoneFighterName.IsEmpty());
  const TSet<uint64> LiveCells = Ui.ComputePendingCells(OwnerView, Board, Fighters);
  TestTrue(TEXT("live stage-1 offers legal zone cells"), LiveCells.Num() > 0);
  FS09PendingChoiceCommand Command;
  FString Reason;
  TestFalse(TEXT("stage-1 needs a selected cell"),
            Ui.ConfirmPendingChoice(OwnerView, false, Command, Reason));
  TestFalse(TEXT("mandatory stage 1 cannot be declined"),
            Ui.ConfirmPendingChoice(OwnerView, true, Command, Reason));
  // The opponent seat sees the mandatory head as a wait state, not a choice.
  FS09CommandUi WaitUi;
  WaitUi.ViewerId = Host;
  WaitUi.OnSnapshot(WaitView, Board, Fighters);
  TestEqual(TEXT("wait seat stays in None"),
            static_cast<int32>(WaitUi.Mode), static_cast<int32>(ES09CommandMode::None));

  // SYNTHESIZED zone data (server model shape: cell.zones[]): the zone rule
  // itself is exercised - cells sharing the Merlin zone become legal.
  const FString Zone = TEXT("synthetic-zone");
  const FS08BoardFighter* Merlin = nullptr;
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (Fighter.Name.Contains(TEXT("Merlin"))) Merlin = &Fighter;
  }
  if (!TestNotNull(TEXT("Merlin found"), Merlin)) return true;
  TestTrue(TEXT("Merlin's live cell is legal"),
           LiveCells.Contains(FS08BoardModel::CellKey(Merlin->X, Merlin->Y)));
  TestTrue(TEXT("live stage-1 cell selectable"),
           Ui.SelectPendingCell(Merlin->X, Merlin->Y, OwnerView, Board, Fighters, Reason));
  TestTrue(TEXT("live stage-1 confirms"),
           Ui.ConfirmPendingChoice(OwnerView, false, Command, Reason));
  TArray<TPair<int32, int32>> ZoneCells;
  ZoneCells.Add(TPair<int32, int32>(Merlin->X, Merlin->Y));
  const FS08Snapshot WithZones = WithBoardZones(OwnerView, ZoneCells, Zone);
  FS08BoardModel ZoneBoard;
  ZoneBoard.Decode(WithZones.BoardState);
  FS09CommandUi ZoneUi;
  ZoneUi.ViewerId = Joiner;
  ZoneUi.OnSnapshot(WithZones, ZoneBoard, Fighters);
  const TSet<uint64> ZoneLegal = ZoneUi.ComputePendingCells(WithZones, ZoneBoard, Fighters);
  TestTrue(TEXT("synthesized zone rule yields legal cells"), ZoneLegal.Num() > 0);
  TestTrue(TEXT("Merlin's own cell legal (shares the zone)"),
           ZoneLegal.Contains(FS08BoardModel::CellKey(Merlin->X, Merlin->Y)));
  TestTrue(TEXT("zone cell selectable"),
           ZoneUi.SelectPendingCell(Merlin->X, Merlin->Y, WithZones, ZoneBoard, Fighters, Reason));
  TestTrue(TEXT("stage-1 confirm with zones"),
           ZoneUi.ConfirmPendingChoice(WithZones, false, Command, Reason));
  TestTrue(TEXT("stage-1 payload carries the cell"), Command.bHasCell);
  TestEqual(TEXT("stage-1 payload x"), Command.CellX, Merlin->X);
  TestEqual(TEXT("stage-1 payload y"), Command.CellY, Merlin->Y);

  // SYNTHESIZED stage 2 (server model: stage=2 + anchor from the stage-1
  // pick): legal cells are the passable orthogonal neighbours of the anchor.
  const TSharedRef<FJsonObject> Stage2 = MakeHead(
      Ui.PendingChoice.Id, Joiner, TEXT("CHOOSE_SPACE"));
  Stage2->SetNumberField(TEXT("stage"), 2);
  const TSharedRef<FJsonObject> Anchor = MakeShared<FJsonObject>();
  Anchor->SetNumberField(TEXT("x"), Merlin->X);
  Anchor->SetNumberField(TEXT("y"), Merlin->Y);
  Stage2->SetObjectField(TEXT("anchor"), Anchor);
  Stage2->SetNumberField(TEXT("damage"), 2);
  Stage2->SetNumberField(TEXT("drawIfDefeated"), 1);
  const FS08Snapshot Stage2View = WithPendingHead(OwnerView, Stage2);
  FS09CommandUi Stage2Ui;
  Stage2Ui.ViewerId = Joiner;
  Stage2Ui.OnSnapshot(Stage2View, Board, Fighters);
  TestEqual(TEXT("stage swap detected (new draft)"), Stage2Ui.PendingChoice.Stage, 2);
  TestTrue(TEXT("stage-2 anchor parsed"),
           Stage2Ui.PendingChoice.bHasAnchor &&
               Stage2Ui.PendingChoice.AnchorX == Merlin->X &&
               Stage2Ui.PendingChoice.AnchorY == Merlin->Y);
  const TSet<uint64> Stage2Cells =
      Stage2Ui.ComputePendingCells(Stage2View, Board, Fighters);
  TestTrue(TEXT("stage-2 cells are the anchor neighbours"), Stage2Cells.Num() > 0);
  int32 NeighbourX = -1, NeighbourY = -1;
  const int32 DX[4] = {1, -1, 0, 0};
  const int32 DY[4] = {0, 0, 1, -1};
  for (int32 i = 0; i < 4; i++) {
    const int32 NX = Merlin->X + DX[i], NY = Merlin->Y + DY[i];
    if (Stage2Cells.Contains(FS08BoardModel::CellKey(NX, NY))) {
      NeighbourX = NX; NeighbourY = NY; break;
    }
  }
  TestTrue(TEXT("a passable neighbour exists"), NeighbourX >= 0);
  if (NeighbourX >= 0) {
    TestTrue(TEXT("neighbour selectable"),
             Stage2Ui.SelectPendingCell(NeighbourX, NeighbourY, Stage2View, Board, Fighters, Reason));
    TestTrue(TEXT("stage-2 confirm"),
             Stage2Ui.ConfirmPendingChoice(Stage2View, false, Command, Reason));
    TestEqual(TEXT("stage-2 payload x"), Command.CellX, NeighbourX);
    TestEqual(TEXT("stage-2 payload y"), Command.CellY, NeighbourY);
  }
  return true;
}

// ---- 6. synthesized heads: TARGET_FIGHTER / CHOOSE_ONE multi-step
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09PendingSynthesizedHeadsTest,
    "Unmatched.S09.PENDING synthesized heads: TARGET_FIGHTER list gate, CHOOSE_ONE multi-step (synthesized)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09PendingSynthesizedHeadsTest::RunTest(const FString&) {
  FS08Snapshot Base;
  if (!LoadS09PendingFixture(TEXT("gd035-move-open-host-view"), Base)) {
    AddError(TEXT("base fixture not loaded"));
    return true;
  }
  FString Host;
  {
    FString Second;
    PendingViewerIds(Base, Host, Second);
  }
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  FS08BoardModel::DecodeFighters(Base.Fighters, Fighters);
  Board.Decode(Base.BoardState);

  // TARGET_FIGHTER (server model: targetFighterIds + damage; A Momentary
  // Glance cannot open it live on zone-less boards - see README gap).
  TArray<FString> AliveIds;
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (Fighter.IsAlive()) AliveIds.Add(Fighter.Id);
  }
  TestTrue(TEXT("fixture has living targets"), AliveIds.Num() >= 2);
  const TSharedRef<FJsonObject> TargetHead =
      MakeHead(TEXT("synth-target-1"), Host, TEXT("TARGET_FIGHTER"));
  TArray<TSharedPtr<FJsonValue>> Targets;
  for (const FString& Id : AliveIds) {
    Targets.Add(MakeShared<FJsonValueString>(Id));
  }
  TargetHead->SetArrayField(TEXT("targetFighterIds"), Targets);
  TargetHead->SetNumberField(TEXT("damage"), 2);
  const FS08Snapshot TargetView = WithPendingHead(Base, TargetHead);

  FS09CommandUi Ui;
  Ui.ViewerId = Host;
  Ui.OnSnapshot(TargetView, Board, Fighters);
  TestEqual(TEXT("TARGET mode opens"), static_cast<int32>(Ui.Mode),
            static_cast<int32>(ES09CommandMode::PendingChoice));
  TArray<FString> Legal;
  TestTrue(TEXT("legal targets enumerated"), Ui.PendingLegalFighters(Fighters, Legal));
  TestEqual(TEXT("legal targets = server list"), Legal.Num(), AliveIds.Num());
  FString Reason;
  TestTrue(TEXT("listed target selectable (own OR enemy: any zone list)"),
           Ui.SelectPendingFighter(AliveIds[0], TargetView, Fighters, Reason));
  // A fighter OUTSIDE the server list is illegal even when alive.
  FString Unlisted;
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (Fighter.IsAlive() && !AliveIds.Contains(Fighter.Id)) Unlisted = Fighter.Id;
  }
  // (every living fighter is listed in this synthesis; skip when n/a)
  if (!Unlisted.IsEmpty()) {
    TestFalse(TEXT("unlisted fighter rejected"),
              Ui.SelectPendingFighter(Unlisted, TargetView, Fighters, Reason));
  }
  FS09PendingChoiceCommand Command;
  TestTrue(TEXT("TARGET confirm"),
           Ui.ConfirmPendingChoice(TargetView, false, Command, Reason));
  TestEqual(TEXT("TARGET payload fighter"), Command.FighterId, AliveIds[0]);
  TestFalse(TEXT("TARGET payload carries NO cell"), Command.bHasCell);
  TestFalse(TEXT("mandatory TARGET cannot be declined"),
            Ui.ConfirmPendingChoice(TargetView, true, Command, Reason));

  // CHOOSE_ONE multi-step (no starter card carries it - synthesized from the
  // server model: options[] + chooseCount). Step 1 pick -> confirm index;
  // the server re-queues the SAME id with chooseCount-1 -> the draft resets.
  const TSharedRef<FJsonObject> ChooseHead =
      MakeHead(TEXT("synth-choose-1"), Host, TEXT("CHOOSE_ONE"));
  TArray<TSharedPtr<FJsonValue>> Options;
  for (int32 i = 0; i < 3; i++) {
    const TSharedRef<FJsonObject> Option = MakeShared<FJsonObject>();
    Option->SetNumberField(TEXT("index"), i);
    Option->SetStringField(TEXT("label"), FString::Printf(TEXT("Option %d"), i));
    Options.Add(MakeShared<FJsonValueObject>(Option));
  }
  ChooseHead->SetArrayField(TEXT("options"), Options);
  ChooseHead->SetNumberField(TEXT("chooseCount"), 2);
  const FS08Snapshot ChooseView = WithPendingHead(Base, ChooseHead);
  FS09CommandUi ChooseUi;
  ChooseUi.ViewerId = Host;
  ChooseUi.OnSnapshot(ChooseView, Board, Fighters);
  TestEqual(TEXT("CHOOSE_ONE mode opens"), static_cast<int32>(ChooseUi.Mode),
            static_cast<int32>(ES09CommandMode::PendingChoice));
  TestEqual(TEXT("options parsed"), ChooseUi.PendingChoice.Options.Num(), 3);
  TestFalse(TEXT("confirm without a pick"),
            ChooseUi.ConfirmPendingChoice(ChooseView, false, Command, Reason));
  TestFalse(TEXT("out-of-range option"),
            ChooseUi.SelectPendingOption(3, Reason));
  TestTrue(TEXT("option 2 picked"), ChooseUi.SelectPendingOption(2, Reason));
  TestTrue(TEXT("CHOOSE_ONE step-1 confirm"),
           ChooseUi.ConfirmPendingChoice(ChooseView, false, Command, Reason));
  TestEqual(TEXT("payload carries the picked index"), Command.OptionIndex, 2);

  // Server step 2: same id, chooseCount now 1 -> the draft MUST reset.
  const TSharedRef<FJsonObject> Step2 = MakeHead(TEXT("synth-choose-1"), Host, TEXT("CHOOSE_ONE"));
  Step2->SetArrayField(TEXT("options"), Options);
  Step2->SetNumberField(TEXT("chooseCount"), 1);
  const FS08Snapshot Step2View = WithPendingHead(Base, Step2);
  ChooseUi.OnSnapshot(Step2View, Board, Fighters);
  TestEqual(TEXT("draft reset on chooseCount change"), ChooseUi.PendingOptionIndex, -1);
  TestFalse(TEXT("mandatory CHOOSE_ONE cannot be declined"),
            ChooseUi.ConfirmPendingChoice(Step2View, true, Command, Reason));

  // Optional CHOOSE_ONE declines cleanly.
  const TSharedRef<FJsonObject> OptionalHead = MakeHead(TEXT("synth-choose-2"), Host, TEXT("CHOOSE_ONE"));
  OptionalHead->SetArrayField(TEXT("options"), Options);
  OptionalHead->SetNumberField(TEXT("chooseCount"), 1);
  OptionalHead->SetBoolField(TEXT("optional"), true);
  const FS08Snapshot OptionalView = WithPendingHead(Base, OptionalHead);
  FS09CommandUi OptionalUi;
  OptionalUi.ViewerId = Host;
  OptionalUi.OnSnapshot(OptionalView, Board, Fighters);
  TestTrue(TEXT("optional decline legal"),
           OptionalUi.ConfirmPendingChoice(OptionalView, true, Command, Reason));
  TestTrue(TEXT("decline payload flagged"), Command.bDecline);
  return true;
}

// ---- 7. exact-instance card types: DISCARD_CARDS count, BOOST_CHOICE one
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09PendingCardTypesTest,
    "Unmatched.S09.PENDING card types: DISCARD_CARDS exact own ids, BOOST_CHOICE exactly one (synthesized)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09PendingCardTypesTest::RunTest(const FString&) {
  FS08Snapshot Base;
  if (!LoadS09PendingFixture(TEXT("gd035-move-open-host-view"), Base)) {
    AddError(TEXT("base fixture not loaded"));
    return true;
  }
  FString Host, Joiner;
  PendingViewerIds(Base, Host, Joiner);
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  FS08BoardModel::DecodeFighters(Base.Fighters, Fighters);
  Board.Decode(Base.BoardState);

  // DISCARD_CARDS needs the CHOICE OWNER's own hand faces: use the joiner's
  // own projection (the host's copy ships hidden-N placeholders for it).
  FS08Snapshot JoinerView;
  if (!LoadS09PendingFixture(TEXT("gd035-move-open-joiner-view"), JoinerView)) {
    AddError(TEXT("joiner-view fixture not loaded"));
    return true;
  }
  const TSharedRef<FJsonObject> DiscardHead =
      MakeHead(TEXT("synth-discard-1"), Joiner, TEXT("DISCARD_CARDS"));
  DiscardHead->SetNumberField(TEXT("value"), 2);
  const FS08Snapshot DiscardView = WithPendingHead(JoinerView, DiscardHead);

  FS09CommandUi Ui;
  Ui.ViewerId = Joiner;
  Ui.OnSnapshot(DiscardView, Board, Fighters);
  TestEqual(TEXT("DISCARD mode opens for the owning seat"),
            static_cast<int32>(Ui.Mode), static_cast<int32>(ES09CommandMode::PendingChoice));
  const TArray<FString> Hand = Ui.PendingOwnHandIds(DiscardView);
  TestTrue(TEXT("joiner hand readable (>= 2 cards)"), Hand.Num() >= 2);
  FString Reason;
  // A foreign id (never in the joiner's hand) is not a legal pick. Hands are
  // per-viewer on the server; this projection is the host-view fixture, so
  // the joiner hand below is decoded from the SAME body's handZones by id.
  TestFalse(TEXT("foreign id rejected"),
            Ui.TogglePendingCard(TEXT("definitely-not-a-card"), DiscardView, Reason));
  TestTrue(TEXT("own card 1"), Ui.TogglePendingCard(Hand[0], DiscardView, Reason));
  FS09PendingChoiceCommand Command;
  TestFalse(TEXT("one card is not enough for value=2"),
            Ui.ConfirmPendingChoice(DiscardView, false, Command, Reason));
  TestTrue(TEXT("own card 2"), Ui.TogglePendingCard(Hand[1], DiscardView, Reason));
  if (Hand.Num() > 2) {
    TestFalse(TEXT("third pick blocked at the limit"),
              Ui.TogglePendingCard(Hand[2], DiscardView, Reason));
  }
  TestTrue(TEXT("DISCARD confirm with exactly value cards"),
           Ui.ConfirmPendingChoice(DiscardView, false, Command, Reason));
  TestEqual(TEXT("DISCARD payload count"), Command.CardIds.Num(), 2);
  TestEqual(TEXT("DISCARD payload id 0"), Command.CardIds[0], Hand[0]);
  TestEqual(TEXT("DISCARD payload id 1"), Command.CardIds[1], Hand[1]);
  TestFalse(TEXT("mandatory DISCARD cannot be declined"),
            Ui.ConfirmPendingChoice(DiscardView, true, Command, Reason));

  // BOOST_CHOICE (optional): exactly ONE own-hand id, or decline.
  const TSharedRef<FJsonObject> BoostHead =
      MakeHead(TEXT("synth-boost-1"), Host, TEXT("BOOST_CHOICE"));
  BoostHead->SetBoolField(TEXT("optional"), true);
  const FS08Snapshot BoostView = WithPendingHead(Base, BoostHead);
  FS09CommandUi BoostUi;
  BoostUi.ViewerId = Host;
  BoostUi.OnSnapshot(BoostView, Board, Fighters);
  TestEqual(TEXT("BOOST mode opens"), static_cast<int32>(BoostUi.Mode),
            static_cast<int32>(ES09CommandMode::PendingChoice));
  const TArray<FString> BoostHand = BoostUi.PendingOwnHandIds(BoostView);
  TestTrue(TEXT("host hand readable (>= 2)"), BoostHand.Num() >= 2);
  TestTrue(TEXT("boost card picked"), BoostUi.TogglePendingCard(BoostHand[0], BoostView, Reason));
  TestFalse(TEXT("second boost card blocked (exactly one)"),
            BoostUi.TogglePendingCard(BoostHand[1], BoostView, Reason));
  TestTrue(TEXT("BOOST confirm"),
           BoostUi.ConfirmPendingChoice(BoostView, false, Command, Reason));
  TestEqual(TEXT("BOOST payload is exactly one id"), Command.CardIds.Num(), 1);
  TestEqual(TEXT("BOOST payload id"), Command.CardIds[0], BoostHand[0]);
  TestTrue(TEXT("optional BOOST declines"),
           BoostUi.ConfirmPendingChoice(BoostView, true, Command, Reason));
  return true;
}

// ---- 7b. exact-count pick plan (S09AUTO multi-card driver basis)
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09PendingPickPlanTest,
    "Unmatched.S09.PENDING pick plan: exact pool+count per card head (PICK/ORDER/DISCARD/BOOST)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09PendingPickPlanTest::RunTest(const FString&) {
  // The driver must ACCUMULATE exactly OutCount distinct pool ids before one
  // confirm (the old single-card probe never satisfied value > 1). The plan
  // is the single source of that number for driver + HUD hints.
  FS08Snapshot PickView, OrderView, JoinerView;
  if (!LoadS09PendingFixture(TEXT("gd035-deckpick-owner-view"), PickView) ||
      !LoadS09PendingFixture(TEXT("gd035-deckorder-owner-view"), OrderView) ||
      !LoadS09PendingFixture(TEXT("gd035-move-open-joiner-view"), JoinerView)) {
    AddError(TEXT("fixtures not loaded"));
    return true;
  }
  FString Host, Joiner;
  PendingViewerIds(PickView, Host, Joiner);
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  FS08BoardModel::DecodeFighters(PickView.Fighters, Fighters);
  Board.Decode(PickView.BoardState);

  // DECK_TOP_PICK PICK: pool = ALL revealed ids, count = value (2).
  FS09CommandUi PickUi;
  PickUi.ViewerId = Joiner;
  PickUi.OnSnapshot(PickView, Board, Fighters);
  TArray<FString> Pool;
  int32 Need = 0;
  TestTrue(TEXT("PICK plan available"), PickUi.PendingCardPickPlan(PickView, Pool, Need));
  TestEqual(TEXT("PICK plan count = value"), Need, 2);
  TArray<FS09CardView> PickRevealed;
  TestTrue(TEXT("PICK revealed cards decoded"), PickUi.PendingRevealedCards(PickRevealed));
  TestEqual(TEXT("PICK plan pool = all revealed"), Pool.Num(), PickRevealed.Num());
  TestTrue(TEXT("PICK pool can satisfy requested count"), Pool.Num() >= Need);
  for (const FS09CardView& Card : PickRevealed) {
    TestTrue(TEXT("PICK pool contains revealed card"), Pool.Contains(Card.InstanceId));
  }
  // Driving the plan end-to-end: accumulate Need ids, one confirm, exact payload.
  FString Reason;
  FS09PendingChoiceCommand Command;
  TestFalse(TEXT("partial accumulation cannot confirm"),
            PickUi.ConfirmPendingChoice(PickView, false, Command, Reason));
  for (int32 i = 0; i < Need; i++) {
    TestTrue(FString::Printf(TEXT("plan pick %d legal"), i),
             PickUi.TogglePendingCard(Pool[i], PickView, Reason));
  }
  TestTrue(TEXT("plan-driven confirm"), PickUi.ConfirmPendingChoice(PickView, false, Command, Reason));
  TestEqual(TEXT("plan payload count"), Command.CardIds.Num(), Need);
  for (int32 i = 0; i < Need; i++) {
    TestEqual(FString::Printf(TEXT("plan payload id %d"), i), Command.CardIds[i], Pool[i]);
  }

  // DECK_TOP_PICK ORDER (2 revealed): count = the WHOLE pool in pick order.
  FS09CommandUi OrderUi;
  OrderUi.ViewerId = Joiner;
  OrderUi.OnSnapshot(OrderView, Board, Fighters);
  TestTrue(TEXT("ORDER plan available"), OrderUi.PendingCardPickPlan(OrderView, Pool, Need));
  TestEqual(TEXT("ORDER plan count = whole pool"), Need, Pool.Num());
  TestTrue(TEXT("ORDER pool >= 2"), Pool.Num() >= 2);
  for (int32 i = 0; i < Need; i++) {
    TestTrue(FString::Printf(TEXT("ORDER plan pick %d"), i),
             OrderUi.TogglePendingCard(Pool[i], OrderView, Reason));
  }
  TestTrue(TEXT("ORDER plan confirm"), OrderUi.ConfirmPendingChoice(OrderView, false, Command, Reason));
  TestEqual(TEXT("ORDER payload = full permutation"), Command.CardIds.Num(), Need);

  // DISCARD_CARDS (value=3): pool = exact own-hand ids, count = 3.
  const TSharedRef<FJsonObject> DiscardHead =
      MakeHead(TEXT("synth-discard-plan"), Joiner, TEXT("DISCARD_CARDS"));
  DiscardHead->SetNumberField(TEXT("value"), 3);
  const FS08Snapshot DiscardView = WithPendingHead(JoinerView, DiscardHead);
  FS09CommandUi DiscardUi;
  DiscardUi.ViewerId = Joiner;
  DiscardUi.OnSnapshot(DiscardView, Board, Fighters);
  TestTrue(TEXT("DISCARD plan available"), DiscardUi.PendingCardPickPlan(DiscardView, Pool, Need));
  TestEqual(TEXT("DISCARD plan count = value"), Need, 3);
  TestEqual(TEXT("DISCARD plan pool = own hand"), Pool,
            DiscardUi.PendingOwnHandIds(DiscardView));
  // BOOST_CHOICE: count = exactly 1 (no value field needed).
  const TSharedRef<FJsonObject> BoostHead =
      MakeHead(TEXT("synth-boost-plan"), Joiner, TEXT("BOOST_CHOICE"));
  const FS08Snapshot BoostView = WithPendingHead(JoinerView, BoostHead);
  FS09CommandUi BoostUi;
  BoostUi.ViewerId = Joiner;
  BoostUi.OnSnapshot(BoostView, Board, Fighters);
  TestTrue(TEXT("BOOST plan available"), BoostUi.PendingCardPickPlan(BoostView, Pool, Need));
  TestEqual(TEXT("BOOST plan count = 1"), Need, 1);

  // Non-card heads have no plan (the driver never synthesizes one).
  FS09CommandUi MoveUi;
  MoveUi.ViewerId = Host;
  MoveUi.OnSnapshot(PickView, Board, Fighters); // queue head is the joiner's
  TestFalse(TEXT("no plan for the non-owning seat"), MoveUi.PendingCardPickPlan(PickView, Pool, Need));
  return true;
}

// ---- 8. same-seq echo guard: one pending resolve = one apply, no duplicate
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09PendingSeqGuardTest,
    "Unmatched.S09.PENDING seq guard: pending open + resolved echo, duplicate merges (live seqs)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09PendingSeqGuardTest::RunTest(const FString&) {
  FS08Snapshot Open;
  if (!LoadS09PendingFixture(TEXT("gd035-move-open-host-view"), Open)) {
    AddError(TEXT("fixture not loaded"));
    return true;
  }
  // Synthesize the resolve echo: same state minus the queue, seq + 1.
  FS08Snapshot Resolved = Open;
  {
    const TSharedRef<FJsonObject> Meta =
        MakeShared<FJsonObject>(*(Open.Metadata->AsObject()));
    Meta->RemoveField(TEXT("pendingEffects"));
    Resolved.Metadata = MakeShared<FJsonValueObject>(Meta);
    Resolved.SequenceNumber = Open.SequenceNumber + 1;
  }

  FS08FlowController Flow(TEXT("http://127.0.0.1:9/graphql"),
                          TEXT("ws://127.0.0.1:9/graphql"));
  // OnApplied fires only for Apply/Merge; Ignore is an early return in the
  // controller, so the stale delivery is asserted via the return value below.
  int32 Applied = 0, Merged = 0;
  Flow.OnCues.AddLambda([](const TArray<FS08Cue>&) {});
  Flow.OnApplied.AddLambda([&](const FS08Snapshot&, ES08SeqDecision Decision) {
    if (Decision == ES08SeqDecision::Apply) ++Applied;
    else ++Merged;
  });
  TestEqual(TEXT("pending open applies"),
            static_cast<int32>(Flow.ApplySnapshot(Open)),
            static_cast<int32>(ES08SeqDecision::Apply));
  TestEqual(TEXT("resolve echo applies"),
            static_cast<int32>(Flow.ApplySnapshot(Resolved)),
            static_cast<int32>(ES08SeqDecision::Apply));
  // The WS duplicate of the SAME resolved seq: merge - no second apply, so a
  // duplicate resolvePendingEffect echo cannot double-fire cues.
  TestEqual(TEXT("same-seq duplicate merges"),
            static_cast<int32>(Flow.ApplySnapshot(Resolved)),
            static_cast<int32>(ES08SeqDecision::Merge));
  // A late re-delivery of the OPEN body (older seq) is stale: ignored.
  TestEqual(TEXT("stale open body ignored"),
            static_cast<int32>(Flow.ApplySnapshot(Open)),
            static_cast<int32>(ES08SeqDecision::Ignore));
  TestEqual(TEXT("applied exactly twice"), Applied, 2);
  TestEqual(TEXT("merged exactly once"), Merged, 1);
  return true;
}

namespace {
bool LoadS09PendingMutation(const FString& Name, const FString& Field,
                            FS08Snapshot& OutSnapshot) {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S09Fixtures="), Dir) || Dir.IsEmpty()) {
    Dir = FPaths::Combine(FPaths::ProjectDir(),
                          TEXT("../../docs/game-design/evidence/S09/fixtures"));
  }
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *FPaths::Combine(Dir, Name + TEXT(".json")))) {
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
  return FS08Contracts::ParseMutationResult(Body, Field, OutSnapshot, Error);
}

int32 S09DiscardPileSize(const FS08Snapshot& Snapshot, const FString& PlayerId) {
  const TSharedPtr<FJsonObject>* Piles = nullptr;
  if (!Snapshot.DiscardPiles.IsValid() ||
      !Snapshot.DiscardPiles->TryGetObject(Piles) || !Piles) return -1;
  const TArray<TSharedPtr<FJsonValue>>* Pile = nullptr;
  if (!(*Piles)->TryGetArrayField(PlayerId, Pile) || !Pile) return 0;
  return Pile->Num();
}

/** Every card of PlayerId's hand projection decodes as a hidden placeholder:
 *  the live wait-seat body carries no face of the choice owner's hand
 *  (ACC-018 - hidden ids only, so the count is all that can ever leak). */
bool S09HandFullyHidden(const FS08Snapshot& Snapshot, const FString& PlayerId) {
  const TSharedPtr<FJsonObject>* Hands = nullptr;
  if (!Snapshot.HandZones.IsValid() ||
      !Snapshot.HandZones->TryGetObject(Hands) || !Hands) return false;
  const TSharedPtr<FJsonValue> Hand = (*Hands)->TryGetField(PlayerId);
  const TSharedPtr<FJsonObject>* HandObject = nullptr;
  if (!Hand.IsValid() || !Hand->TryGetObject(HandObject) || !HandObject) return false;
  const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
  if (!(*HandObject)->TryGetArrayField(TEXT("cards"), Cards) || !Cards ||
      Cards->Num() == 0) {
    return false;
  }
  for (const TSharedPtr<FJsonValue>& Card : *Cards) {
    FS09CardView View;
    if (!FS09HudFactory::CardFromJson(Card, View) || !View.bHidden) return false;
  }
  return true;
}
} // namespace

// ---- 9. LIVE DISCARD_CARDS: the real head captured from a live duel
// (Medusa's "Hiss and Slither" OPPONENT_DISCARD opening a DISCARD_CARDS head
// for the discarder seat). Unlike the synthesized heads in tests 7/7b every
// input here is server-authored: queue-head ownership, the exact required
// count, the owner's projected hand faces, the wait seat's blindness, and the
// resolve echo closing the head.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09PendingDiscardLiveTest,
    "Unmatched.S09.PENDING DISCARD_CARDS live: owner gates, exact own ids, wait-seat privacy, echo closes head",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09PendingDiscardLiveTest::RunTest(const FString&) {
  FS08Snapshot OwnerView, WaitView, Echo;
  if (!LoadS09PendingFixture(TEXT("gd035-discard-owner-joiner-view"), OwnerView) ||
      !LoadS09PendingFixture(TEXT("gd035-discard-wait-host-view"), WaitView) ||
      !LoadS09PendingMutation(TEXT("gd035-discard-resolve-echo"),
                              TEXT("resolvePendingEffect"), Echo)) {
    AddError(TEXT("fixtures not loaded"));
    return true;
  }
  FString Host, Joiner;
  PendingViewerIds(OwnerView, Host, Joiner);

  // The REAL queue head: DISCARD_CARDS owned by the discarder seat (joiner,
  // forced there by the host's Medusa producer card).
  TArray<FS08PendingEffect> Effects;
  TestTrue(TEXT("owner view head parses"), FS08Contracts::PendingEffects(OwnerView, Effects));
  if (!TestEqual(TEXT("one live head"), Effects.Num(), 1)) return true;
  const FS08PendingEffect& Head = Effects[0];
  TestEqual(TEXT("live head type"), Head.Type, FString(TEXT("DISCARD_CARDS")));
  TestEqual(TEXT("head owned by the discarder (joiner seat)"), Head.PlayerId, Joiner);
  TestTrue(TEXT("head carries the exact required count"),
           Head.bHasValue && Head.Value >= 1);

  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  FS08BoardModel::DecodeFighters(OwnerView.Fighters, Fighters);
  Board.Decode(OwnerView.BoardState);

  // Owner seat: mode opens over the LIVE projection; the pick plan pool is
  // exactly the own-hand instance ids (never hidden placeholders).
  FS09CommandUi Ui;
  Ui.ViewerId = Joiner;
  Ui.OnSnapshot(OwnerView, Board, Fighters);
  TestEqual(TEXT("discarder enters PendingChoice"), static_cast<int32>(Ui.Mode),
            static_cast<int32>(ES09CommandMode::PendingChoice));
  TestEqual(TEXT("draft head = live head id"), Ui.PendingChoice.Id, Head.Id);
  TArray<FString> Pool;
  int32 Need = 0;
  TestTrue(TEXT("live pick plan available"), Ui.PendingCardPickPlan(OwnerView, Pool, Need));
  TestEqual(TEXT("plan count = server value"), Need, Head.Value);
  TestEqual(TEXT("plan pool = own hand ids"), Pool, Ui.PendingOwnHandIds(OwnerView));
  TestTrue(TEXT("pool can satisfy the count"), Pool.Num() >= Need);
  for (const FString& Id : Pool) {
    TestFalse(TEXT("pool id is exact (no hidden placeholder)"),
              Id.StartsWith(TEXT("hidden-")));
  }

  // Select exactly the required DISTINCT own ids; nothing else is legal.
  FString Reason;
  TestFalse(TEXT("foreign id rejected"),
            Ui.TogglePendingCard(TEXT("definitely-not-a-card"), OwnerView, Reason));
  for (int32 i = 0; i < Need; i++) {
    TestTrue(FString::Printf(TEXT("own pick %d legal"), i),
             Ui.TogglePendingCard(Pool[i], OwnerView, Reason));
  }
  if (Pool.Num() > Need) {
    TestFalse(TEXT("over-pick blocked at the exact count"),
              Ui.TogglePendingCard(Pool[Need], OwnerView, Reason));
  }
  FS09PendingChoiceCommand Command;
  TestTrue(TEXT("confirm with exactly the required ids"),
           Ui.ConfirmPendingChoice(OwnerView, false, Command, Reason));
  TestEqual(TEXT("command effect id = head id"), Command.EffectId, Head.Id);
  TestEqual(TEXT("command count = server value"), Command.CardIds.Num(), Need);
  for (int32 i = 0; i < Need; i++) {
    TestEqual(FString::Printf(TEXT("command id %d"), i), Command.CardIds[i], Pool[i]);
  }
  TestFalse(TEXT("mandatory DISCARD cannot be declined"),
            Ui.ConfirmPendingChoice(OwnerView, true, Command, Reason));

  // Wait seat (the host, who PRODUCED the effect): no choice mode, no plan,
  // and the live projection ships no faces of the discarder's hand.
  FS08BoardModel WaitBoard;
  TArray<FS08BoardFighter> WaitFighters;
  FS08BoardModel::DecodeFighters(WaitView.Fighters, WaitFighters);
  WaitBoard.Decode(WaitView.BoardState);
  FS09CommandUi WaitUi;
  WaitUi.ViewerId = Host;
  WaitUi.OnSnapshot(WaitView, WaitBoard, WaitFighters);
  // The wait seat legitimately sits in CombatResolve (phase COMBAT_RESOLVE,
  // it is the defender) - the point is it NEVER enters PendingChoice, and
  // the open head blocks its combat resolve on either side.
  TestTrue(TEXT("wait seat gets no PendingChoice mode"),
           WaitUi.Mode != ES09CommandMode::PendingChoice);
  TestFalse(TEXT("open head blocks the wait seat's combat resolve"),
            WaitUi.CanResolveCombat(WaitView, Reason));
  TArray<FString> WaitPool;
  int32 WaitNeed = 0;
  TestFalse(TEXT("no pick plan for the wait seat"),
            WaitUi.PendingCardPickPlan(WaitView, WaitPool, WaitNeed));
  TestTrue(TEXT("discarder hand ships hidden placeholders only (no leakage)"),
           S09HandFullyHidden(WaitView, Joiner));
  // The wait seat's own hand IS exact - so the denial below is ownership, not
  // a broken projection.
  const TArray<FString> WaitOwn = WaitUi.PendingOwnHandIds(WaitView);
  TestTrue(TEXT("wait seat own hand exact"), WaitOwn.Num() > 0);
  TestFalse(TEXT("wait seat cannot pick the discarder's card id"),
            WaitUi.TogglePendingCard(Pool[0], WaitView, Reason));

  // Resolve echo (real resolvePendingEffect response): newer seq, empty
  // queue, the closed head drops the draft, and exactly `value` cards moved
  // from the discarder's hand into their public discard pile.
  TestEqual(TEXT("echo seq = open seq + 1"), Echo.SequenceNumber,
            OwnerView.SequenceNumber + 1);
  TArray<FS08PendingEffect> After;
  // PendingEffects returns false for an EMPTY queue (no actionable head) -
  // a closed head is proven by zero decoded entries plus the mode reset below.
  FS08Contracts::PendingEffects(Echo, After);
  TestEqual(TEXT("echo queue closed (zero entries)"), After.Num(), 0);
  FS08BoardModel EchoBoard;
  TArray<FS08BoardFighter> EchoFighters;
  FS08BoardModel::DecodeFighters(Echo.Fighters, EchoFighters);
  EchoBoard.Decode(Echo.BoardState);
  Ui.OnSnapshot(Echo, EchoBoard, EchoFighters);
  TestEqual(TEXT("resolve echo closes the head (mode resets)"), static_cast<int32>(Ui.Mode),
            static_cast<int32>(ES09CommandMode::None));
  TestEqual(TEXT("exactly value cards hit the public discard pile"),
            S09DiscardPileSize(Echo, Head.PlayerId),
            S09DiscardPileSize(OwnerView, Head.PlayerId) + Need);
  return true;
}

// ---- DE-020 (W-11; de-footage/task 02 SD-10, SD-16, SD-19, SD-28, SD-56; 01 F-11): serving the deferred choices
// Headless run: node tools/s08/run-ue-tests.cjs "Unmatched.S09.PENDING DE-020" <abs log>
namespace S09De020Test {
FS08Snapshot WithSkipped(const FS08Snapshot& Snapshot, const TArray<int32>& Ns) {
  FS08Snapshot Out = Snapshot;
  const TSharedRef<FJsonObject> Meta = MakeShared<FJsonObject>(*(Snapshot.Metadata->AsObject()));
  TArray<TSharedPtr<FJsonValue>> Entries;
  for (const int32 N : Ns) {
    const TSharedRef<FJsonObject> Entry = MakeShared<FJsonObject>();
    Entry->SetNumberField(TEXT("n"), N);
    Entry->SetNumberField(TEXT("seq"), 40 + N);
    Entry->SetStringField(TEXT("reason"), TEXT("NO_VALID_TARGETS"));
    Entry->SetStringField(TEXT("playerId"), TEXT("u-host"));
    Entry->SetStringField(TEXT("effectId"), FString::Printf(TEXT("s1-e%d"), N));
    Entry->SetStringField(TEXT("kind"), TEXT("PLACE"));
    Entry->SetStringField(TEXT("text"), TEXT("Place a fighter in any space."));
    Entries.Add(MakeShared<FJsonValueObject>(Entry));
  }
  Entries.Add(MakeShared<FJsonValueString>(TEXT("garbage")));  // malformed entries are skipped
  const TSharedRef<FJsonObject> NoN = MakeShared<FJsonObject>();
  NoN->SetStringField(TEXT("reason"), TEXT("NO_VALID_TARGETS"));
  Entries.Add(MakeShared<FJsonValueObject>(NoN));               // no n: dropped
  Meta->SetArrayField(TEXT("skippedEffects"), Entries);
  Out.Metadata = MakeShared<FJsonValueObject>(Meta);
  return Out;
}

FS08PendingEffect Head(const TCHAR* Id, const TCHAR* Type, bool bOptional, const TCHAR* Text) {
  FS08PendingEffect Out;
  Out.Id = Id;
  Out.Type = Type;
  Out.bOptional = bOptional;
  Out.Text = Text;
  return Out;
}
}  // namespace S09De020Test

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09PendingDe020SkippedTest,
    "Unmatched.S09.PENDING DE-020 skipped effects: first snapshot primes silently, new n explained once (why.effect.no.targets)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09PendingDe020SkippedTest::RunTest(const FString&) {
  FS08Snapshot Base;
  if (!LoadS09PendingFixture(TEXT("gd035-move-open-host-view"), Base)) {
    AddError(TEXT("base fixture not loaded"));
    return true;
  }
  using namespace S09De020Test;
  TArray<FS09SkippedEffectNote> Notes;
  TestFalse(TEXT("no field: Parse false (saves without the field = no skips)"),
            FS09SkippedEffectsFeed::Parse(Base, Notes));
  const FS08Snapshot Two = WithSkipped(Base, {2, 1});
  TestTrue(TEXT("field present: Parse true"), FS09SkippedEffectsFeed::Parse(Two, Notes));
  TestEqual(TEXT("malformed entries / entries without n dropped"), Notes.Num(), 2);
  TestEqual(TEXT("sorted by n"), Notes.Num() == 2 ? Notes[0].N : -1, 1);
  TestEqual(TEXT("kind decoded"), Notes.Num() == 2 ? Notes[1].Kind : FString(), FString(TEXT("PLACE")));
  TestEqual(TEXT("NO_VALID_TARGETS -> why.effect.no.targets"),
            Notes.Num() == 2 ? Notes[0].Why().Key.ToString() : FString(), FString(TEXT("why.effect.no.targets")));
  TestTrue(TEXT("the key is in the EN table"), S08WhyText::Has(FName(TEXT("why.effect.no.targets"))));

  // Entry with two old skips: remembered, nothing shown (04 §4.3.1 `n`).
  FS09SkippedEffectsFeed Feed;
  TestEqual(TEXT("first snapshot: nothing shown"), Feed.Consume(Two).Num(), 0);
  TestEqual(TEXT("primed with the largest n"), Feed.LastShownN, 2);
  TestEqual(TEXT("same body again: nothing"), Feed.Consume(Two).Num(), 0);
  const TArray<FS09SkippedEffectNote> New = Feed.Consume(WithSkipped(Base, {1, 2, 3, 4}));
  TestEqual(TEXT("two new notes"), New.Num(), 2);
  TestEqual(TEXT("oldest first"), New.Num() == 2 ? New[0].N : -1, 3);
  TestEqual(TEXT("explained once"), Feed.Consume(WithSkipped(Base, {3, 4})).Num(), 0);
  TestEqual(TEXT("a body without the field shows nothing"), Feed.Consume(Base).Num(), 0);

  // A fresh game (reconnect): primes again, never replays.
  Feed.Reset();
  TestEqual(TEXT("after reset the first body primes"), Feed.Consume(WithSkipped(Base, {5})).Num(), 0);
  TestEqual(TEXT("then n=6 shows"), Feed.Consume(WithSkipped(Base, {5, 6})).Num(), 1);
  // A first body without skips primes with 0: the first skip of the game is shown.
  FS09SkippedEffectsFeed Fresh;
  TestEqual(TEXT("first body without skips"), Fresh.Consume(Base).Num(), 0);
  TestEqual(TEXT("the first skip of the game is explained"), Fresh.Consume(WithSkipped(Base, {1})).Num(), 1);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09PendingDe020PresentTest,
    "Unmatched.S09.PENDING DE-020 presentation: modal first, toast for a repeating optional trigger, compact every turn, collapse, memory",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09PendingDe020PresentTest::RunTest(const FString&) {
  using namespace S09De020Test;
  FS09PendingPresenter P;
  // Optional trigger (Medusa-like "may deal 1 damage" each turn): first open = modal, then toast.
  const FS08PendingEffect Opt1 = Head(TEXT("o1"), TEXT("TARGET_FIGHTER"), true, TEXT("You may deal 1 damage."));
  TestTrue(TEXT("new open"), P.Observe(Opt1, 3));
  TestEqual(TEXT("first open of an optional trigger: modal"), static_cast<int32>(P.Present),
            static_cast<int32>(ES09PendingPresent::Modal));
  TestFalse(TEXT("the same head again is not a new open"), P.Observe(Opt1, 3));
  TestTrue(TEXT("modal collapses"), P.Collapse());
  TestTrue(TEXT("collapsed"), P.bCollapsed);
  TestFalse(TEXT("collapse twice: no change"), P.Collapse());
  TestTrue(TEXT("toggle expands"), P.Toggle());
  TestFalse(TEXT("expanded"), P.bCollapsed);
  FS09PendingVariant Answer;
  Answer.FighterId = TEXT("f-1-hero");
  P.Remember(Opt1, Answer);
  P.Clear();
  TestFalse(TEXT("cleared: no open"), P.IsOpen());
  const FS08PendingEffect Opt2 = Head(TEXT("o2"), TEXT("TARGET_FIGHTER"), true, TEXT("You may deal 1 damage."));
  TestTrue(TEXT("second open"), P.Observe(Opt2, 5));
  TestEqual(TEXT("repeating optional trigger: toast"), static_cast<int32>(P.Present),
            static_cast<int32>(ES09PendingPresent::Toast));
  TestEqual(TEXT("opens before"), P.OpensBefore, 1);
  TestFalse(TEXT("the toast has no plate"), P.Collapse());
  TestTrue(TEXT("remembered variant of the signature"), P.Remembered() != nullptr &&
                                                            P.Remembered()->FighterId == TEXT("f-1-hero"));
  TestTrue(TEXT("C on the toast opens the full modal"), P.Toggle());
  TestEqual(TEXT("details: modal"), static_cast<int32>(P.Present), static_cast<int32>(ES09PendingPresent::Modal));
  TestTrue(TEXT("trace line"), P.TraceLine().StartsWith(TEXT("MS-PENDING present=modal id=o2 opens=1")));
  // A new open resets the collapse.
  P.Collapse();
  const FS08PendingEffect Opt3 = Head(TEXT("o3"), TEXT("TARGET_FIGHTER"), true, TEXT("You may deal 1 damage."));
  P.Observe(Opt3, 7);
  TestFalse(TEXT("a new open is never collapsed"), P.bCollapsed);

  // Mandatory every turn: modal, the same turn again = modal (EACH effect), the next turn = compact.
  const FS08PendingEffect M1 = Head(TEXT("m1"), TEXT("CHOOSE_ONE"), false, TEXT("Choose one: ..."));
  P.Observe(M1, 3);
  TestEqual(TEXT("first mandatory open: modal"), static_cast<int32>(P.Present),
            static_cast<int32>(ES09PendingPresent::Modal));
  TestTrue(TEXT("no memory yet"), P.Remembered() == nullptr);
  FS09PendingChoiceCommand Sent;
  Sent.EffectId = TEXT("m1");
  Sent.OptionIndex = 7;
  P.Remember(M1, FS09PendingVariant::FromCommand(Sent));
  P.Observe(Head(TEXT("m2"), TEXT("CHOOSE_ONE"), false, TEXT("Choose one: ...")), 3);
  TestEqual(TEXT("same turn again: modal"), static_cast<int32>(P.Present),
            static_cast<int32>(ES09PendingPresent::Modal));
  P.Observe(Head(TEXT("m3"), TEXT("CHOOSE_ONE"), false, TEXT("Choose one: ...")), 4);
  TestEqual(TEXT("next turn: compact"), static_cast<int32>(P.Present),
            static_cast<int32>(ES09PendingPresent::Compact));
  TestEqual(TEXT("compact remembers the stable option index"), P.Remembered() ? P.Remembered()->OptionIndex : -1, 7);
  TestTrue(TEXT("compact collapses too"), P.Collapse());
  TestEqual(TEXT("variant describe"), FS09PendingVariant::FromCommand(Sent).Describe(), FString(TEXT("option=7")));
  // Another text = another trigger: modal again.
  P.Observe(Head(TEXT("x1"), TEXT("CHOOSE_ONE"), false, TEXT("Choose one: other")), 9);
  TestEqual(TEXT("another signature: modal"), static_cast<int32>(P.Present),
            static_cast<int32>(ES09PendingPresent::Modal));
  // A new game forgets.
  P.Reset();
  P.Observe(Head(TEXT("m9"), TEXT("CHOOSE_ONE"), false, TEXT("Choose one: ...")), 12);
  TestEqual(TEXT("reset: modal again"), static_cast<int32>(P.Present), static_cast<int32>(ES09PendingPresent::Modal));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09PendingDe020StepsTest,
    "Unmatched.S09.PENDING DE-020 steps and memory: object -> target (up to N) in the opponent's turn, no-target head, remembered variant (synthesized)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09PendingDe020StepsTest::RunTest(const FString&) {
  FS08Snapshot Base;
  if (!LoadS09PendingFixture(TEXT("gd035-move-open-host-view"), Base)) {
    AddError(TEXT("base fixture not loaded"));
    return true;
  }
  FString Host, Joiner;
  PendingViewerIds(Base, Host, Joiner);
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  FS08BoardModel::DecodeFighters(Base.Fighters, Fighters);
  Board.Decode(Base.BoardState);
  TArray<FString> OwnAlive;
  FString EnemyAlive;
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (!Fighter.IsAlive()) continue;
    if (Fighter.OwnerId == Host) {
      OwnAlive.Add(Fighter.Id);
    } else if (EnemyAlive.IsEmpty()) {
      EnemyAlive = Fighter.Id;
    }
  }
  if (OwnAlive.Num() < 2 || EnemyAlive.IsEmpty()) {
    AddError(TEXT("fixture needs two own living fighters and an enemy"));
    return true;
  }

  // ---- MOVE handed to the viewer during the OPPONENT's turn: two steps ----
  const TSharedRef<FJsonObject> MoveHead = MakeHead(TEXT("de020-move"), Host, TEXT("MOVE"));
  MoveHead->SetNumberField(TEXT("value"), 2);
  TArray<TSharedPtr<FJsonValue>> Ids;
  for (const FString& Id : OwnAlive) Ids.Add(MakeShared<FJsonValueString>(Id));
  MoveHead->SetArrayField(TEXT("fighterIds"), Ids);
  FS08Snapshot MoveView = WithPendingHead(Base, MoveHead);
  MoveView.CurrentTurnPlayerId = Joiner;
  FS09CommandUi Ui;
  Ui.ViewerId = Host;
  Ui.OnSnapshot(MoveView, Board, Fighters);
  TestEqual(TEXT("MOVE opens for the viewer"), static_cast<int32>(Ui.Mode),
            static_cast<int32>(ES09CommandMode::PendingChoice));
  FS09PendingStep Step = S09DescribePendingStep(Ui, MoveView, Board, Fighters);
  TestTrue(TEXT("step valid"), Step.bValid);
  TestTrue(TEXT("opponent's turn flagged (MS-R-77)"), Step.bOpponentTurn);
  TestEqual(TEXT("two steps"), Step.Steps, 2);
  TestEqual(TEXT("step 1: object"), Step.Step, 1);
  TestEqual(TEXT("ms.choice.object"), Step.Prompt.Key.ToString(), FString(TEXT("ms.choice.object")));
  TestEqual(TEXT("step name"), FString(Step.StepName()), FString(TEXT("object")));
  FString Reason;
  FString Picked;
  for (const FString& Id : OwnAlive) {
    if (Ui.SelectPendingFighter(Id, MoveView, Fighters, Reason) &&
        !Ui.DescribePendingMovePlace(Board, Fighters).bNoSpace) {
      Picked = Id;
      break;
    }
  }
  if (TestFalse(TEXT("a movable fighter picked"), Picked.IsEmpty())) {
    Step = S09DescribePendingStep(Ui, MoveView, Board, Fighters);
    TestEqual(TEXT("step 2: target"), Step.Step, 2);
    // VS-5 E4 (ВР-VS5-36): the second step of MOVE / PLACE picks a space - ms.status.space {fighterName}
    TestEqual(TEXT("ms.status.space"), Step.Prompt.Key.ToString(), FString(TEXT("ms.status.space")));
    TestEqual(TEXT("up to N = the allowance"), Step.N, 2);
    TestTrue(TEXT("EN text: «Choose a space for {fighter}»"), Step.Prompt.Text().StartsWith(TEXT("Choose a space for ")));
    TestEqual(TEXT("still the target step"), FString(Step.StepName()), FString(TEXT("target")));
    TestFalse(TEXT("a MOVE with spaces is not a no-target head"), S09PendingHasNoTargets(Ui, MoveView, Board, Fighters));
  }
  FS08Snapshot OwnTurn = MoveView;
  OwnTurn.CurrentTurnPlayerId = Host;
  TestFalse(TEXT("own turn: not flagged"), S09DescribePendingStep(Ui, OwnTurn, Board, Fighters).bOpponentTurn);

  // ---- TARGET_FIGHTER: one step; an empty / dead target list is a no-target head ----
  const TSharedRef<FJsonObject> TargetHead = MakeHead(TEXT("de020-target"), Host, TEXT("TARGET_FIGHTER"));
  TArray<TSharedPtr<FJsonValue>> Targets;
  Targets.Add(MakeShared<FJsonValueString>(EnemyAlive));
  TargetHead->SetArrayField(TEXT("targetFighterIds"), Targets);
  TargetHead->SetBoolField(TEXT("optional"), true);
  TargetHead->SetStringField(TEXT("text"), TEXT("You may deal 1 damage."));
  const FS08Snapshot TargetView = WithPendingHead(Base, TargetHead);
  FS09CommandUi TargetUi;
  TargetUi.ViewerId = Host;
  TargetUi.OnSnapshot(TargetView, Board, Fighters);
  Step = S09DescribePendingStep(TargetUi, TargetView, Board, Fighters);
  TestTrue(TEXT("TARGET: one step"), Step.bValid && Step.Steps == 1 && Step.Step == 1 && Step.N == 1);
  TestFalse(TEXT("TARGET with a living target: not empty"),
            S09PendingHasNoTargets(TargetUi, TargetView, Board, Fighters));
  const TSharedRef<FJsonObject> EmptyHead = MakeHead(TEXT("de020-empty"), Host, TEXT("TARGET_FIGHTER"));
  TArray<TSharedPtr<FJsonValue>> Ghost;
  Ghost.Add(MakeShared<FJsonValueString>(TEXT("no-such-fighter")));
  EmptyHead->SetArrayField(TEXT("targetFighterIds"), Ghost);
  const FS08Snapshot EmptyView = WithPendingHead(Base, EmptyHead);
  FS09CommandUi EmptyUi;
  EmptyUi.ViewerId = Host;
  EmptyUi.OnSnapshot(EmptyView, Board, Fighters);
  TestTrue(TEXT("TARGET without a legal target: named, never a silent wait (D-DE-11)"),
           S09PendingHasNoTargets(EmptyUi, EmptyView, Board, Fighters));
  // CHOOSE_ONE has no step line and is never a no-target head.
  const TSharedRef<FJsonObject> ChooseHead = MakeHead(TEXT("de020-choose"), Host, TEXT("CHOOSE_ONE"));
  TArray<TSharedPtr<FJsonValue>> Options;
  for (const int32 Index : {5, 7, 9}) {
    const TSharedRef<FJsonObject> Option = MakeShared<FJsonObject>();
    Option->SetNumberField(TEXT("index"), Index);
    Option->SetStringField(TEXT("label"), FString::Printf(TEXT("Option %d"), Index));
    Options.Add(MakeShared<FJsonValueObject>(Option));
  }
  ChooseHead->SetArrayField(TEXT("options"), Options);
  const FS08Snapshot ChooseView = WithPendingHead(Base, ChooseHead);
  FS09CommandUi ChooseUi;
  ChooseUi.ViewerId = Host;
  ChooseUi.OnSnapshot(ChooseView, Board, Fighters);
  TestFalse(TEXT("CHOOSE_ONE: no step line"), S09DescribePendingStep(ChooseUi, ChooseView, Board, Fighters).bValid);
  TestFalse(TEXT("CHOOSE_ONE: not a no-target head"), S09PendingHasNoTargets(ChooseUi, ChooseView, Board, Fighters));

  // ---- the remembered variant is pre-selected where it is still legal (nothing sent) ----
  FS09PendingVariant Option7;
  Option7.OptionIndex = 7;
  FString Applied;
  TestTrue(TEXT("CHOOSE_ONE: stable index 7 applied"), S09ApplyPendingVariant(ChooseUi, Option7, ChooseView, Board, Fighters, Applied));
  TestEqual(TEXT("position of index 7"), ChooseUi.PendingOptionIndex, 1);
  FS09PendingChoiceCommand Command;
  TestTrue(TEXT("Enter repeats last time's answer"), ChooseUi.ConfirmPendingChoice(ChooseView, false, Command, Reason));
  TestEqual(TEXT("payload = the stable index"), Command.OptionIndex, 7);
  FS09PendingVariant Gone;
  Gone.OptionIndex = 42;
  FS09CommandUi ChooseUi2;
  ChooseUi2.ViewerId = Host;
  ChooseUi2.OnSnapshot(ChooseView, Board, Fighters);
  TestFalse(TEXT("an option that no longer exists is not applied"),
            S09ApplyPendingVariant(ChooseUi2, Gone, ChooseView, Board, Fighters, Applied));
  TestEqual(TEXT("nothing selected"), ChooseUi2.PendingOptionIndex, -1);
  FS09PendingVariant Target;
  Target.FighterId = EnemyAlive;
  TestTrue(TEXT("TARGET: the remembered fighter applied"),
           S09ApplyPendingVariant(TargetUi, Target, TargetView, Board, Fighters, Applied));
  TestTrue(TEXT("TARGET confirm with the remembered fighter"),
           TargetUi.ConfirmPendingChoice(TargetView, false, Command, Reason) && Command.FighterId == EnemyAlive);
  FS09PendingVariant Illegal;
  Illegal.FighterId = OwnAlive[0];  // not in targetFighterIds
  FS09CommandUi TargetUi2;
  TargetUi2.ViewerId = Host;
  TargetUi2.OnSnapshot(TargetView, Board, Fighters);
  TestFalse(TEXT("an illegal remembered fighter is not applied"),
            S09ApplyPendingVariant(TargetUi2, Illegal, TargetView, Board, Fighters, Applied));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09PendingDe020AbilityTest,
    "Unmatched.S09.PENDING DE-020 attack ability (SD-56): only King Arthur's hero asks, prompt bound to the draft, boost rides on the attack",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09PendingDe020AbilityTest::RunTest(const FString&) {
  // The joiner's projection (own hand faces) of the resolve window, turned into the joiner's action phase:
  // King Arthur (f-1-hero) stands adjacent to Medusa (f-0-hero).
  FS08Snapshot Snapshot;
  if (!LoadS09PendingFixture(TEXT("gd034-resolve-window-defender-view"), Snapshot)) {
    AddError(TEXT("fixture not loaded"));
    return true;
  }
  FString Host, Joiner;
  PendingViewerIds(Snapshot, Host, Joiner);
  {
    const TSharedRef<FJsonObject> Meta = MakeShared<FJsonObject>(*(Snapshot.Metadata->AsObject()));
    Meta->RemoveField(TEXT("combatInfo"));
    Meta->RemoveField(TEXT("pendingEffects"));
    Snapshot.Metadata = MakeShared<FJsonValueObject>(Meta);
    Snapshot.Phase = TEXT("ACTION_MANEUVER");
    Snapshot.CurrentTurnPlayerId = Joiner;
  }
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  FS08BoardModel::DecodeFighters(Snapshot.Fighters, Fighters);
  Board.Decode(Snapshot.BoardState);
  FS08BoardFighter* Arthur = nullptr;
  FS08BoardFighter* Medusa = nullptr;
  FS08BoardFighter* Merlin = nullptr;
  for (FS08BoardFighter& Entry : Fighters) {
    if (Entry.Id == TEXT("f-1-hero")) Arthur = &Entry;
    if (Entry.Id == TEXT("f-0-hero")) Medusa = &Entry;
    if (Entry.Id == TEXT("f-1-sk0")) Merlin = &Entry;
  }
  if (!Arthur || !Medusa) {
    AddError(TEXT("Arthur / Medusa not in the fixture"));
    return true;
  }
  // The S09 fixtures predate heroSlug on the wire (game-state.service `sl`): set it as the live projection does.
  if (Arthur->HeroSlug.IsEmpty()) Arthur->HeroSlug = TEXT("king-arthur");
  if (Medusa->HeroSlug.IsEmpty()) Medusa->HeroSlug = TEXT("medusa");
  TestTrue(TEXT("King Arthur's hero boosts his attack"), FS09CommandUi::AllowsAbilityBoost(*Arthur));
  TestFalse(TEXT("Medusa does not"), FS09CommandUi::AllowsAbilityBoost(*Medusa));
  if (Merlin) {
    FS08BoardFighter Sidekick = *Merlin;
    Sidekick.HeroSlug = TEXT("king-arthur");
    TestFalse(TEXT("Merlin (sidekick, same slug) never"), FS09CommandUi::AllowsAbilityBoost(Sidekick));
  }
  FS08BoardFighter NoSlug = *Arthur;
  NoSlug.HeroSlug.Reset();
  TestFalse(TEXT("no heroSlug on the wire: no prompt (the server could not allow it either)"),
            FS09CommandUi::AllowsAbilityBoost(NoSlug));

  FS09CommandUi Ui;
  Ui.ViewerId = Joiner;
  Ui.OnSnapshot(Snapshot, Board, Fighters);
  Ui.Mode = ES09CommandMode::AttackDraft;  // the player pressed A
  FString Reason;
  TestTrue(TEXT("Arthur attacker"), Ui.SelectAttacker(Arthur->Id, Board, Fighters, Reason));
  TestTrue(TEXT("Medusa target"), Ui.SelectTarget(Medusa->Id, Board, Fighters, Reason));
  TestFalse(TEXT("prompt closed before it is opened"), Ui.IsAttackAbilityPromptOpen());
  TestFalse(TEXT("no boost toggle without the prompt"), Ui.ToggleAttackAbilityBoost(TEXT("x"), Snapshot, Reason));
  FS09PlayerPanel Own;
  {
    FS09HudModel Hud;
    Hud.Build(Snapshot, Joiner, TSet<FString>(), 0, 0);
    if (Hud.ViewerPanel()) Own = *Hud.ViewerPanel();
  }
  for (const FS09CardView& Card : Own.Cards) {
    if (!Card.bHidden && Ui.ToggleAttackCard(Card.InstanceId, Snapshot, Fighters, Reason) &&
        Ui.AttackCardId == Card.InstanceId) {
      break;
    }
  }
  FS09AttackCommand Command;
  if (!TestTrue(TEXT("a legal attack card for Arthur"), Ui.ConfirmAttack(Snapshot, Board, Fighters, Command, Reason))) {
    return true;
  }
  TestTrue(TEXT("plain confirm: no ability boost"), Command.AbilityBoostCardId.IsEmpty());
  const TArray<FS09CardView> BoostCards = Ui.AttackAbilityBoostCards(Snapshot);
  for (const FS09CardView& Card : BoostCards) {
    TestTrue(TEXT("boost candidates carry a printed BOOST"), Card.bHasBoostValue);
    TestNotEqual(TEXT("the attack card is never a candidate"), Card.InstanceId, Ui.AttackCardId);
  }
  if (BoostCards.Num() == 0) {
    TestFalse(TEXT("no boost card: no prompt - the attack goes"), Ui.AttackAbilityAvailable(Snapshot, Fighters));
    return true;
  }
  TestTrue(TEXT("Arthur + a boost card: the prompt is offered"), Ui.AttackAbilityAvailable(Snapshot, Fighters));
  Ui.OpenAttackAbilityPrompt();
  TestTrue(TEXT("prompt open"), Ui.IsAttackAbilityPromptOpen());
  TestFalse(TEXT("the attack card cannot boost itself"), Ui.ToggleAttackAbilityBoost(Ui.AttackCardId, Snapshot, Reason));
  TestTrue(TEXT("boost card picked"), Ui.ToggleAttackAbilityBoost(BoostCards[0].InstanceId, Snapshot, Reason));
  TestTrue(TEXT("confirm with the prompt open"), Ui.ConfirmAttack(Snapshot, Board, Fighters, Command, Reason));
  TestEqual(TEXT("abilityBoostCardId rides on the attack"), Command.AbilityBoostCardId, BoostCards[0].InstanceId);
  TestTrue(TEXT("re-toggle clears"), Ui.ToggleAttackAbilityBoost(BoostCards[0].InstanceId, Snapshot, Reason));
  TestTrue(TEXT("declined: attack without the boost"),
           Ui.ConfirmAttack(Snapshot, Board, Fighters, Command, Reason) && Command.AbilityBoostCardId.IsEmpty());
  // A changed draft closes the prompt: the stale boost never rides on another attack.
  Ui.ToggleAttackAbilityBoost(BoostCards[0].InstanceId, Snapshot, Reason);
  Ui.AttackTargetId = TEXT("someone-else");
  TestFalse(TEXT("another target: the prompt is closed"), Ui.IsAttackAbilityPromptOpen());
  Ui.AttackTargetId = Medusa->Id;
  TestTrue(TEXT("back to the same draft: the prompt key matches again"), Ui.IsAttackAbilityPromptOpen());
  Ui.CloseAttackAbilityPrompt();
  TestTrue(TEXT("closed prompt: plain attack"),
           Ui.ConfirmAttack(Snapshot, Board, Fighters, Command, Reason) && Command.AbilityBoostCardId.IsEmpty());
  TestTrue(TEXT("prompt strings in the EN table"), S08WhyText::Has(FName(TEXT("ms.ability.boost"))) &&
                                                       S08WhyText::Has(FName(TEXT("ms.btn.noboost"))) &&
                                                       S08WhyText::Has(FName(TEXT("ms.choice.target"))));
  return true;
}

#endif // WITH_AUTOMATION_TESTS


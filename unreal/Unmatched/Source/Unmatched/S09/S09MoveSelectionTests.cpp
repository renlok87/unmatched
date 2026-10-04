// Move selection (docs/game-design/move-selection) automation tests of the S09
// draft: 06 MS-AT-11..20.
//   Unmatched.S09.MoveSel.SequentialDraft - MS-AT-13 (MS-T-05): moves in send
//       order on the positions after the previous moves, order changes,
//       overwrite / re-assign numbering, conflict reasons, the command against
//       the golden fixtures of backend/prisma/fixtures/movement.
//   Unmatched.S09.MoveSel.BoostRecompute  - MS-AT-12 (MS-T-05): boost change
//       re-evaluates statuses and tiers in the same call, NeedBoost by the
//       absolute RequiredBoost, card highlight, tiers by MS-E-80, null / +0 /
//       two copies.
//   Unmatched.S09.MoveSel.ZeroLengthNotSent - MS-AT-11 (MS-T-04): the own cell
//       never becomes a move, ConfirmManeuver and SubmitManeuver drop "stay".
//   Unmatched.S09.MoveSel.MovementParity  - MS-AT-14 (MS-T-04): raw movement,
//       immobilized gate, the two "alive" roles, MS-DATA dirtyDefeated.
//   Unmatched.S09.MoveSel.ReasonsAndStrings - MS-AT-18 (MS-T-06): every code of
//       02 §1.1 -> why.* key and class И/С, the wire ruleCode, the EN table =
//       why-reasons.json, CellLabel in toasts, MS-REJECT + refetch, no resend.
//   Unmatched.S09.MoveSel.InFlightGate    - MS-AT-19 (MS-T-06 part): 10 presses ->
//       1 mutation, 3 s why.syncing, 10 s deadline -> recovery, gate released
//       by snapshot, late reply traced only, 429, begin never repeated.
//   Unmatched.S09.MoveSel.InputSemantics  - MS-AT-15 (MS-T-07): Esc / RMB by steps
//       (D / I first), undo stack 32 + barrier, Delete, Tab, Ctrl+Up/Down before
//       the D arrows, MS-S-08 arrows, click on release, MS-R-71, bindings list.
//   Unmatched.S09.MoveSel.PreDraftAndNoQuickMove - MS-AT-16 (MS-T-07): MS-S-02/03
//       without a mutation, the target carried into the draft by the new hand,
//       why.predraft.lost, no quick move, the -S08Maneuver driver (src=auto).
//   Unmatched.S09.MoveSel.ExhaustionConfirm - MS-AT-17 (MS-T-07): MS-S-04.
//   Unmatched.S09.MoveSel.ClickReliability - DE-014 (UI-INP-011): n = 20 clicks
//       per space kind with a 0 / 50 ms hold - 0 lost (target or why.*),
//       MS-S-00 empty space why.not.your.turn, in flight why.syncing.
//   Unmatched.S09.MoveSel.TurnStartInput - DE-015 (SD-44 / SD-47, MS-R-79): the
//       first click of the own turn accepted in the apply frame, END TURN / E
//       answer why.actions.remaining {n}, no pass, the TURN-INPUT trace pair.
//   Unmatched.S09.MoveSel.AutoManeuverPlan - M1 / MS-AT-32 (driver part): the opt-in
//       -S08ManeuverPlan=boost3 on the driver's draft - the best BOOST card, three
//       moves (hero step + two sidekicks), src=auto, confirmable; refusals.
//   Unmatched.S09.MoveSel.ReconnectAndRebuild - MS-AT-20, the MS-T-04 part:
//       the draft cache by maneuverId, re-evaluation on a new seq, a boost card
//       that left the hand, another id / closed maneuver / GAME_OVER. (Deadline,
//       auth refresh and why.syncing: MS-T-06, at the end; undo stack: MS-T-07.)
// Headless run:
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     "-ExecCmds=Automation RunTests Unmatched.S09.MoveSel; Quit"
//     -unattended -nosplash -nullrhi
// Optional: -S08MoveFixtures=<dir> (golden fixtures).
#if WITH_AUTOMATION_TESTS

#include "S09ManeuverUi.h"
#include "S09MoveInput.h"
#include "S09HudPress.h"
#include "../S08/S08BoardModel.h"
#include "../S08/S08Contracts.h"
#include "../S08/S08WhyText.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

// Named namespace (not anonymous): unity builds merge test files.
namespace S09MoveSelTest {

const TCHAR* const Me = TEXT("p1");
const TCHAR* const Opp = TEXT("p2");
const TCHAR* const ManeuverA = TEXT("maneuver:1:5");

/** W x H grid board decoded through the server boardState shape; Walls are
 *  'wall' cells. */
FS08BoardModel MsGrid(int32 W, int32 H, std::initializer_list<FIntPoint> Walls = {}) {
  TArray<TSharedPtr<FJsonValue>> Lines;
  for (int32 Y = 0; Y < H; ++Y) {
    TArray<TSharedPtr<FJsonValue>> Line;
    for (int32 X = 0; X < W; ++X) {
      TSharedRef<FJsonObject> Cell = MakeShared<FJsonObject>();
      Cell->SetNumberField(TEXT("x"), X);
      Cell->SetNumberField(TEXT("y"), Y);
      bool bWall = false;
      for (const FIntPoint& Wall : Walls) bWall |= Wall == FIntPoint(X, Y);
      Cell->SetStringField(TEXT("type"), bWall ? TEXT("wall") : TEXT("normal"));
      Line.Add(MakeShared<FJsonValueObject>(Cell));
    }
    Lines.Add(MakeShared<FJsonValueArray>(Line));
  }
  TSharedRef<FJsonObject> Board = MakeShared<FJsonObject>();
  Board->SetNumberField(TEXT("width"), W);
  Board->SetNumberField(TEXT("height"), H);
  Board->SetArrayField(TEXT("cells"), Lines);
  Board->SetObjectField(TEXT("doors"), MakeShared<FJsonObject>());
  FS08BoardModel Model;
  Model.Decode(MakeShared<FJsonValueObject>(Board));
  return Model;
}

FS08BoardFighter MsFighter(const FString& Id, const FString& Owner, int32 X, int32 Y, double Movement = 3.0,
                           int32 Health = 10) {
  FS08BoardFighter F;
  F.Id = Id;
  F.OwnerId = Owner;
  F.Name = Id;
  F.Label = Id;
  F.Health = Health;
  F.MaxHealth = FMath::Max(Health, 10);
  F.X = X;
  F.Y = Y;
  F.SetRawMovement(Movement);
  F.AttackType = TEXT("melee");
  return F;
}

struct FMsCard {
  FString Id;
  bool bHasBoost = true;
  int32 Boost = 0;
};

/** Viewer's ACTION_MANEUVER snapshot with metadata.pendingManeuver (id) and
 *  the own hand (boostValue null when !bHasBoost). */
FS08Snapshot MsSnapshot(const TArray<FMsCard>& Hand, const FString& ManeuverId = ManeuverA, int32 Seq = 5) {
  FS08Snapshot Snapshot;
  Snapshot.SequenceNumber = Seq;
  Snapshot.Phase = TEXT("ACTION_MANEUVER");
  Snapshot.TurnCount = 1;
  Snapshot.CurrentTurnPlayerId = Me;
  TSharedRef<FJsonObject> Meta = MakeShared<FJsonObject>();
  Meta->SetNumberField(TEXT("actionsRemaining"), 1);
  if (!ManeuverId.IsEmpty()) {
    TSharedRef<FJsonObject> Pending = MakeShared<FJsonObject>();
    Pending->SetStringField(TEXT("id"), ManeuverId);
    Pending->SetStringField(TEXT("playerId"), Me);
    Meta->SetObjectField(TEXT("pendingManeuver"), Pending);
  }
  Snapshot.Metadata = MakeShared<FJsonValueObject>(Meta);
  TArray<TSharedPtr<FJsonValue>> Cards;
  for (const FMsCard& Card : Hand) {
    TSharedRef<FJsonObject> C = MakeShared<FJsonObject>();
    C->SetStringField(TEXT("id"), Card.Id);
    C->SetStringField(TEXT("cardId"), TEXT("cat-") + Card.Id);
    C->SetStringField(TEXT("name"), Card.Id);
    C->SetStringField(TEXT("nameRu"), Card.Id);
    C->SetStringField(TEXT("cardType"), TEXT("VERSATILE"));
    C->SetStringField(TEXT("bannerName"), TEXT("any"));
    C->SetStringField(TEXT("text"), TEXT(""));
    C->SetBoolField(TEXT("isVisible"), false);
    if (Card.bHasBoost) {
      C->SetNumberField(TEXT("boostValue"), Card.Boost);
    } else {
      C->SetField(TEXT("boostValue"), MakeShared<FJsonValueNull>());
    }
    Cards.Add(MakeShared<FJsonValueObject>(C));
  }
  TSharedRef<FJsonObject> OwnHand = MakeShared<FJsonObject>();
  OwnHand->SetArrayField(TEXT("cards"), Cards);
  TSharedRef<FJsonObject> Hands = MakeShared<FJsonObject>();
  Hands->SetObjectField(Me, OwnHand);
  Snapshot.HandZones = MakeShared<FJsonValueObject>(Hands);
  return Snapshot;
}

/** A draft UI opened on Snapshot (viewer p1). */
FS09CommandUi MsOpen(const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                     const TArray<FS08BoardFighter>& Fighters) {
  FS09CommandUi Ui;
  Ui.ViewerId = Me;
  Ui.OnSnapshot(Snapshot, Board, Fighters);
  return Ui;
}

const FS09DraftMove* MsMove(const FS09CommandUi& Ui, const FString& FighterId) {
  const int32 Index = Ui.MoveIndexOf(FighterId);
  return Index == INDEX_NONE ? nullptr : &Ui.Moves[Index];
}

FString MsStatus(const FS09DraftMove* Move) {
  if (!Move) return TEXT("-");
  switch (Move->Status) {
    case ES09DraftMoveStatus::Ok: return TEXT("ok");
    case ES09DraftMoveStatus::NeedBoost: return TEXT("needBoost");
    default: return TEXT("conflict");
  }
}

FString MsKey(const FS09Reason& Reason) { return Reason.Key.ToString(); }

bool MsSameCells(const TArray<FIntPoint>& A, std::initializer_list<FIntPoint> B) {
  return A == TArray<FIntPoint>(B);
}

/** Cells at exactly D steps / within (Lo, Hi] of Start in a list. */
bool MsAllWithin(const FS09ReachTiers& Tiers, const TArray<FIntPoint>& Cells, int32 Lo, int32 Hi) {
  for (const FIntPoint& Cell : Cells) {
    const int32 D = Tiers.Reach.DistanceTo(Cell);
    if (D <= Lo || D > Hi) return false;
  }
  return true;
}

// ---- golden fixtures (backend/prisma/fixtures/movement) -----------------------

FString MsFixtureDir() {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S08MoveFixtures="), Dir) || Dir.IsEmpty()) {
    Dir = FPaths::ConvertRelativePathToFull(
        FPaths::Combine(FPaths::ProjectDir(), TEXT("../.."), TEXT("backend/prisma/fixtures/movement")));
  }
  return Dir;
}

bool MsReadXY(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, FIntPoint& Out) {
  const TSharedPtr<FJsonObject>* XY = nullptr;
  double X = 0.0, Y = 0.0;
  if (!Object->TryGetObjectField(Field, XY) || !XY || !(*XY)->TryGetNumberField(TEXT("x"), X) ||
      !(*XY)->TryGetNumberField(TEXT("y"), Y)) {
    return false;
  }
  Out = FIntPoint(static_cast<int32>(X), static_cast<int32>(Y));
  return true;
}

/** A lattice-grid ("cobble-5x6") fixture: board, fighters, hand, draft. */
struct FMsFixture {
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  TArray<FMsCard> Hand;
  TArray<FS09DraftMove> Draft;
  FString BoostCardId;
  TSharedPtr<FJsonObject> Expect;
};

bool MsLoadGridFixture(const FString& Name, FMsFixture& Out, FString& OutError) {
  const FString Path = FPaths::Combine(MsFixtureDir(), Name + TEXT(".move-fixture.json"));
  FString Text;
  TSharedPtr<FJsonObject> Fx;
  if (!FFileHelper::LoadFileToString(Text, *Path) ||
      !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Fx) || !Fx.IsValid()) {
    OutError = Path + TEXT(" not readable");
    return false;
  }
  const TSharedPtr<FJsonObject>* Board = nullptr;
  const TSharedPtr<FJsonObject>* Lattice = nullptr;
  double W = 0.0, H = 0.0;
  if (!Fx->TryGetObjectField(TEXT("board"), Board) || !(*Board)->TryGetObjectField(TEXT("lattice"), Lattice) ||
      !(*Lattice)->TryGetNumberField(TEXT("width"), W) || !(*Lattice)->TryGetNumberField(TEXT("height"), H) ||
      (*Lattice)->HasField(TEXT("walls")) || (*Lattice)->HasField(TEXT("edges"))) {
    OutError = TEXT("not a plain lattice grid fixture");
    return false;
  }
  Out.Board = MsGrid(static_cast<int32>(W), static_cast<int32>(H));
  const TArray<TSharedPtr<FJsonValue>>* Fighters = nullptr;
  if (!Fx->TryGetArrayField(TEXT("fighters"), Fighters)) {
    OutError = TEXT("no fighters");
    return false;
  }
  for (const TSharedPtr<FJsonValue>& Value : *Fighters) {
    const TSharedPtr<FJsonObject> F = Value->AsObject();
    FIntPoint Pos;
    if (!F.IsValid() || !MsReadXY(F, TEXT("position"), Pos)) {
      OutError = TEXT("a fighter without position");
      return false;
    }
    double Health = 10.0, Movement = 2.0;
    F->TryGetNumberField(TEXT("health"), Health);
    const bool bMovement = F->TryGetNumberField(TEXT("movement"), Movement);
    FS08BoardFighter Fighter =
        MsFighter(F->GetStringField(TEXT("id")), F->GetStringField(TEXT("ownerId")), Pos.X, Pos.Y, Movement,
                  static_cast<int32>(Health));
    if (!bMovement) {
      Fighter.bMovementPresent = false;
      Fighter.Movement = 0;
    }
    Out.Fighters.Add(Fighter);
  }
  const TArray<TSharedPtr<FJsonValue>>* Hand = nullptr;
  if (Fx->TryGetArrayField(TEXT("hand"), Hand)) {
    for (const TSharedPtr<FJsonValue>& Value : *Hand) {
      const TSharedPtr<FJsonObject> C = Value->AsObject();
      FMsCard Card;
      Card.Id = C->GetStringField(TEXT("id"));
      double Boost = 0.0;
      Card.bHasBoost = C->TryGetNumberField(TEXT("boostValue"), Boost);
      Card.Boost = static_cast<int32>(Boost);
      Out.Hand.Add(Card);
    }
  }
  const TSharedPtr<FJsonObject>* Draft = nullptr;
  const TArray<TSharedPtr<FJsonValue>>* Moves = nullptr;
  if (!Fx->TryGetObjectField(TEXT("draft"), Draft) || !(*Draft)->TryGetArrayField(TEXT("moves"), Moves)) {
    OutError = TEXT("no draft.moves");
    return false;
  }
  (*Draft)->TryGetStringField(TEXT("boostCardId"), Out.BoostCardId);
  for (const TSharedPtr<FJsonValue>& Value : *Moves) {
    const TSharedPtr<FJsonObject> M = Value->AsObject();
    FS09DraftMove& Move = Out.Draft.AddDefaulted_GetRef();
    Move.FighterId = M->GetStringField(TEXT("fighterId"));
    // draftInputOf: dest, else the last cell of a forced path.
    FIntPoint Dest;
    const TArray<TSharedPtr<FJsonValue>>* Forced = nullptr;
    if (!MsReadXY(M, TEXT("dest"), Dest)) {
      const TSharedPtr<FJsonObject> Last =
          M->TryGetArrayField(TEXT("path"), Forced) && Forced->Num() > 0 ? Forced->Last()->AsObject() : nullptr;
      double X = 0.0, Y = 0.0;
      if (!Last.IsValid() || !Last->TryGetNumberField(TEXT("x"), X) || !Last->TryGetNumberField(TEXT("y"), Y)) {
        OutError = TEXT("a draft move without dest / path");
        return false;
      }
      Dest = FIntPoint(static_cast<int32>(X), static_cast<int32>(Y));
    }
    Move.DestX = Dest.X;
    Move.DestY = Dest.Y;
  }
  const TSharedPtr<FJsonObject>* Expect = nullptr;
  if (!Fx->TryGetObjectField(TEXT("expect"), Expect)) {
    OutError = TEXT("no expect");
    return false;
  }
  Out.Expect = *Expect;
  return true;
}

} // namespace S09MoveSelTest

using namespace S09MoveSelTest;

// ---------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelSequentialDraftTest, "Unmatched.S09.MoveSel.SequentialDraft",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelSequentialDraftTest::RunTest(const FString&) {
  const FS08BoardModel Board = MsGrid(5, 5);
  const FS08Snapshot Snap = MsSnapshot({});
  FString Reason;

  // ---- MS-E-33 / MS-E-85: A leaves X, B ends on X (order A -> B) ----
  {
    const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 1, 2), MsFighter(TEXT("b"), Me, 0, 2),
                                               MsFighter(TEXT("c"), Me, 4, 4), MsFighter(TEXT("e"), Opp, 4, 0)};
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    TestTrue(TEXT("A drafted to (2,2)"), Ui.SetDestination(TEXT("a"), 2, 2, Snap, Board, Fighters, Reason));
    TestTrue(TEXT("B drafted onto A's cell - A leaves it first (MS-E-85)"),
             Ui.SetDestination(TEXT("b"), 1, 2, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("A then B"), Ui.Moves.Num(), 2);
    TestEqual(TEXT("A order 0"), Ui.MoveIndexOf(TEXT("a")), 0);
    TestEqual(TEXT("B order 1"), MsMove(Ui, TEXT("b")) ? MsMove(Ui, TEXT("b"))->Order : -1, 1);
    TestEqual(TEXT("A ok"), MsStatus(MsMove(Ui, TEXT("a"))), FString(TEXT("ok")));
    TestEqual(TEXT("B ok"), MsStatus(MsMove(Ui, TEXT("b"))), FString(TEXT("ok")));
    TestTrue(TEXT("draft confirmable"), Ui.Eval.IsConfirmable());
    FS09ManeuverCommand Command;
    TestTrue(TEXT("A -> B confirm legal"), Ui.ConfirmManeuver(Snap, Board, Fighters, Command, Reason));
    TestEqual(TEXT("two moves sent"), Command.Moves.Num(), 2);
    if (Command.Moves.Num() == 2) {
      TestEqual(TEXT("A sent first"), Command.Moves[0].FighterId, FString(TEXT("a")));
      TestTrue(TEXT("A path [(2,2)]"), MsSameCells(Command.Moves[0].Path, {FIntPoint(2, 2)}));
      TestTrue(TEXT("B path [(1,2)]"), MsSameCells(Command.Moves[1].Path, {FIntPoint(1, 2)}));
    }

    // ---- MS-E-34: B before A -> B is a Conflict (ally), A stays Ok ----
    const uint32 RevBefore = Ui.DraftRevision;
    TestTrue(TEXT("Ctrl+Up on B"), Ui.MoveOrder(TEXT("b"), -1, Snap, Board, Fighters));
    TestTrue(TEXT("order change re-evaluates (revision)"), Ui.DraftRevision != RevBefore);
    TestEqual(TEXT("B now first"), Ui.MoveIndexOf(TEXT("b")), 0);
    const FS09DraftMove* B = MsMove(Ui, TEXT("b"));
    TestEqual(TEXT("B conflict"), MsStatus(B), FString(TEXT("conflict")));
    if (B) {
      TestEqual(TEXT("B why.cell.ally"), MsKey(B->Reason), FString(TEXT("why.cell.ally")));
      TestTrue(TEXT("B carries the order hint"), B->Reason.Args.Contains(TEXT("orderHint")));
      TestTrue(TEXT("Conflict has no path"), B->Path.IsEmpty());
      TestEqual(TEXT("Conflict needs no boost"), B->RequiredBoost, 0);
    }
    TestEqual(TEXT("A still ok"), MsStatus(MsMove(Ui, TEXT("a"))), FString(TEXT("ok")));
    TestFalse(TEXT("confirm blocked by the Conflict"), Ui.ConfirmManeuver(Snap, Board, Fighters, Command, Reason));
    TestTrue(TEXT("confirm reason names the conflict key"), Reason.Contains(TEXT("why.cell.ally")));
    TestTrue(TEXT("LastReason is the conflict reason"), MsKey(Ui.LastReason) == TEXT("why.cell.ally"));

    // ---- MS-E-96: no-op order changes ----
    const uint32 RevNoOp = Ui.DraftRevision;
    TestFalse(TEXT("Ctrl+Up on the first move"), Ui.MoveOrder(TEXT("b"), -1, Snap, Board, Fighters));
    TestFalse(TEXT("Ctrl+Down on the last move"), Ui.MoveOrder(TEXT("a"), +1, Snap, Board, Fighters));
    TestFalse(TEXT("Ctrl+Up on a fighter without a move"), Ui.MoveOrder(TEXT("c"), -1, Snap, Board, Fighters));
    TestEqual(TEXT("no-op order changes do nothing"), Ui.DraftRevision, RevNoOp);
    TestTrue(TEXT("Ctrl+Down on B restores A -> B"), Ui.MoveOrder(TEXT("b"), +1, Snap, Board, Fighters));
    TestEqual(TEXT("B ok again"), MsStatus(MsMove(Ui, TEXT("b"))), FString(TEXT("ok")));

    // ---- MS-E-38: an overwrite keeps the number ----
    TestTrue(TEXT("A overwritten to (2,1)"), Ui.SetDestination(TEXT("a"), 2, 1, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("A keeps order 0"), Ui.MoveIndexOf(TEXT("a")), 0);
    TestEqual(TEXT("still two moves"), Ui.Moves.Num(), 2);

    // ---- MS-E-114: clear frees the number, a re-assign goes last ----
    Ui.ClearMove(TEXT("a"));
    TestEqual(TEXT("A cleared"), Ui.MoveIndexOf(TEXT("a")), INDEX_NONE);
    TestEqual(TEXT("B moved up to 0"), MsMove(Ui, TEXT("b")) ? MsMove(Ui, TEXT("b"))->Order : -1, 0);
    TestEqual(TEXT("B conflicts once A stays on (1,2)"), MsStatus(MsMove(Ui, TEXT("b"))), FString(TEXT("conflict")));
    TestTrue(TEXT("A re-assigned"), Ui.SetDestination(TEXT("a"), 2, 2, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("A re-assigned goes last"), Ui.MoveIndexOf(TEXT("a")), 1);
    TestEqual(TEXT("B still before A: conflict"), MsStatus(MsMove(Ui, TEXT("b"))), FString(TEXT("conflict")));
    TestTrue(TEXT("Ctrl+Up on A fixes the order"), Ui.MoveOrder(TEXT("a"), -1, Snap, Board, Fighters));
    TestTrue(TEXT("all ok after the reorder"), Ui.Eval.IsConfirmable() && Ui.Eval.NumOk == 2);

    // ---- refusals with reasons (MS-E-21 enemy, MS-E-36 same target) ----
    TestFalse(TEXT("enemy cell refused"), Ui.SetDestination(TEXT("c"), 4, 0, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("why.cell.enemy"), MsKey(Ui.LastReason), FString(TEXT("why.cell.enemy")));
    TestFalse(TEXT("a second fighter on A's target refused"),
              Ui.SetDestination(TEXT("c"), 2, 2, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("why.cell.ally"), MsKey(Ui.LastReason), FString(TEXT("why.cell.ally")));
    TestEqual(TEXT("the refused cells left the draft unchanged"), Ui.Moves.Num(), 2);
  }

  // ---- MS-E-36 on a raw draft: two targets in one cell -> second Conflict ----
  {
    const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 1, 2), MsFighter(TEXT("b"), Me, 0, 2)};
    TArray<FS09DraftMove> Draft;
    Draft.AddDefaulted(2);
    Draft[0].FighterId = TEXT("a");
    Draft[0].DestX = 2;
    Draft[0].DestY = 2;
    Draft[1].FighterId = TEXT("b");
    Draft[1].DestX = 2;
    Draft[1].DestY = 2;
    const FS09DraftEval Eval = FS09DraftEval::Evaluate(Board, Fighters, Draft, {}, FString(), Me);
    TestEqual(TEXT("first target ok"), MsStatus(&Draft[0]), FString(TEXT("ok")));
    TestEqual(TEXT("second target conflict"), MsStatus(&Draft[1]), FString(TEXT("conflict")));
    TestEqual(TEXT("second: why.cell.ally"), MsKey(Draft[1].Reason), FString(TEXT("why.cell.ally")));
    TestTrue(TEXT("not confirmable"), !Eval.IsConfirmable() && Eval.NumConflict == 1);
  }

  // ---- MS-E-35: a swap is impossible in any order ----
  {
    const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 1, 2), MsFighter(TEXT("b"), Me, 0, 2)};
    for (int32 First = 0; First < 2; ++First) {
      TArray<FS09DraftMove> Draft;
      Draft.AddDefaulted(2);
      Draft[First].FighterId = TEXT("a");
      Draft[First].DestX = 0;
      Draft[First].DestY = 2;
      Draft[1 - First].FighterId = TEXT("b");
      Draft[1 - First].DestX = 1;
      Draft[1 - First].DestY = 2;
      FS09DraftEval::Evaluate(Board, Fighters, Draft, {}, FString(), Me);
      for (const FS09DraftMove& Move : Draft) {
        TestEqual(FString::Printf(TEXT("swap (A %s): %s conflict"), First == 0 ? TEXT("first") : TEXT("second"),
                                  *Move.FighterId),
                  MsStatus(&Move), FString(TEXT("conflict")));
        TestEqual(FString::Printf(TEXT("swap: %s why.swap.impossible"), *Move.FighterId), MsKey(Move.Reason),
                  FString(TEXT("why.swap.impossible")));
      }
    }
    // Through the draft operations: B leaves, A takes B's cell, then B tries A's.
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    TestTrue(TEXT("B leaves to (0,1)"), Ui.SetDestination(TEXT("b"), 0, 1, Snap, Board, Fighters, Reason));
    TestTrue(TEXT("A takes B's cell"), Ui.SetDestination(TEXT("a"), 0, 2, Snap, Board, Fighters, Reason));
    TestFalse(TEXT("B onto A's cell refused"), Ui.SetDestination(TEXT("b"), 1, 2, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("why.swap.impossible"), MsKey(Ui.LastReason), FString(TEXT("why.swap.impossible")));
    TestTrue(TEXT("B keeps (0,1)"), MsMove(Ui, TEXT("b")) && MsMove(Ui, TEXT("b"))->DestY == 1);
  }

  // ---- MS-E-37: a later path through the already moved ally ----
  {
    // Corridor y = 1 of a 6 x 3 board.
    const FS08BoardModel Corridor =
        MsGrid(6, 3, {FIntPoint(0, 0), FIntPoint(1, 0), FIntPoint(2, 0), FIntPoint(3, 0), FIntPoint(4, 0),
                      FIntPoint(5, 0), FIntPoint(0, 2), FIntPoint(1, 2), FIntPoint(2, 2), FIntPoint(3, 2),
                      FIntPoint(4, 2), FIntPoint(5, 2)});
    const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 1, 1), MsFighter(TEXT("b"), Me, 0, 1, 4.0)};
    FS09CommandUi Ui = MsOpen(Snap, Corridor, Fighters);
    TestTrue(TEXT("A to (3,1)"), Ui.SetDestination(TEXT("a"), 3, 1, Snap, Corridor, Fighters, Reason));
    TestTrue(TEXT("B through A's new cell to (4,1)"),
             Ui.SetDestination(TEXT("b"), 4, 1, Snap, Corridor, Fighters, Reason));
    const FS09DraftMove* B = MsMove(Ui, TEXT("b"));
    TestEqual(TEXT("B ok"), MsStatus(B), FString(TEXT("ok")));
    TestTrue(TEXT("B path passes the moved ally"),
             B && MsSameCells(B->Path, {FIntPoint(1, 1), FIntPoint(2, 1), FIntPoint(3, 1), FIntPoint(4, 1)}));
    // No path at all (the corridor is walled): why.cell.no.path.
    TestFalse(TEXT("a wall refused"), Ui.SetDestination(TEXT("a"), 3, 0, Snap, Corridor, Fighters, Reason));
    TestEqual(TEXT("why.cell.no.path"), MsKey(Ui.LastReason), FString(TEXT("why.cell.no.path")));
  }

  // ---- MS-E-05: different movements per fighter (Leshen 1 / Wolves 3) ----
  {
    const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("leshen"), Me, 0, 0, 1.0),
                                               MsFighter(TEXT("wolf"), Me, 4, 4, 3.0)};
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    TestTrue(TEXT("Leshen selectable"), Ui.SelectFighter(TEXT("leshen"), Snap, Board, Fighters));
    TestEqual(TEXT("Leshen base 1"), Ui.SelectedTiers.Base, 1);
    TestTrue(TEXT("Leshen base tier = 1 step"), MsAllWithin(Ui.SelectedTiers, Ui.SelectedTiers.BaseTier, 0, 1) &&
                                                    Ui.SelectedTiers.BaseTier.Num() == 2 &&
                                                    Ui.SelectedTiers.BoostTier.Num() == 0);
    TestEqual(TEXT("legacy reach = start + base tier"), Ui.ReachableCells.Num(), 3);
    TestFalse(TEXT("Leshen 2 steps without a boost refused"),
              Ui.SetDestination(TEXT("leshen"), 2, 0, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("why.cell.unreachable"), MsKey(Ui.LastReason), FString(TEXT("why.cell.unreachable")));
    TestEqual(TEXT("need 2"), Ui.LastReason.Args.FindRef(TEXT("need")), FString(TEXT("2")));
    TestEqual(TEXT("have 1"), Ui.LastReason.Args.FindRef(TEXT("have")), FString(TEXT("1")));
    TestTrue(TEXT("Wolf 3 steps ok"), Ui.SetDestination(TEXT("wolf"), 1, 4, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("Wolf base 3, ok"), MsMove(Ui, TEXT("wolf")) ? MsMove(Ui, TEXT("wolf"))->Base : -1, 3);
  }

  // ---- the command matches the golden fixtures (MS-AT-02 drafts) ----
  for (const TCHAR* Name : {TEXT("multi-cobble-free-then-occupy"), TEXT("multi-cobble-occupy-before-free")}) {
    FMsFixture Fx;
    FString Error;
    if (!MsLoadGridFixture(Name, Fx, Error)) {
      AddError(FString::Printf(TEXT("%s: %s"), Name, *Error));
      continue;
    }
    const FS08Snapshot FxSnap = MsSnapshot(Fx.Hand);
    FS09CommandUi Ui = MsOpen(FxSnap, Fx.Board, Fx.Fighters);
    Ui.Moves = Fx.Draft;
    Ui.BoostCardId = Fx.BoostCardId;
    FS09ManeuverCommand Command;
    const bool bConfirmed = Ui.ConfirmManeuver(FxSnap, Fx.Board, Fx.Fighters, Command, Reason);
    FString ServerOutcome;
    Fx.Expect->TryGetStringField(TEXT("server"), ServerOutcome);
    TestEqual(FString::Printf(TEXT("%s: confirm iff the server accepts"), Name), bConfirmed, ServerOutcome == TEXT("ok"));
    const TSharedPtr<FJsonObject>* Status = nullptr;
    const TSharedPtr<FJsonObject>* Paths = nullptr;
    Fx.Expect->TryGetObjectField(TEXT("status"), Status);
    Fx.Expect->TryGetObjectField(TEXT("paths"), Paths);
    for (const FS09DraftMove& Move : Ui.Moves) {
      FString Want;
      if (Status && (*Status)->TryGetStringField(Move.FighterId, Want)) {
        TestEqual(FString::Printf(TEXT("%s: status of %s"), Name, *Move.FighterId), MsStatus(&Move), Want);
      }
    }
    if (bConfirmed && Paths) {
      for (const FS08ManeuverMove& Sent : Command.Moves) {
        const TArray<TSharedPtr<FJsonValue>>* WantPath = nullptr;
        TArray<FIntPoint> Want;
        if ((*Paths)->TryGetArrayField(Sent.FighterId, WantPath)) {
          for (const TSharedPtr<FJsonValue>& Cell : *WantPath) {
            const TArray<TSharedPtr<FJsonValue>>& XY = Cell->AsArray();
            if (XY.Num() == 2) Want.Add(FIntPoint(static_cast<int32>(XY[0]->AsNumber()), static_cast<int32>(XY[1]->AsNumber())));
          }
        }
        TestTrue(FString::Printf(TEXT("%s: sent path of %s equals the fixture"), Name, *Sent.FighterId),
                 Sent.Path == Want);
      }
    }
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelBoostRecomputeTest, "Unmatched.S09.MoveSel.BoostRecompute",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelBoostRecomputeTest::RunTest(const FString&) {
  // Open 10 x 3 grid: distances are manhattan.
  const FS08BoardModel Board = MsGrid(10, 3);
  const TArray<FMsCard> Hand = {{TEXT("c2"), true, 2},  {TEXT("c4"), true, 4},  {TEXT("c0"), true, 0},
                                {TEXT("cn"), false, 0}, {TEXT("c4b"), true, 4}};
  const FS08Snapshot Snap = MsSnapshot(Hand);
  const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 0, 0), MsFighter(TEXT("b"), Me, 0, 2),
                                             MsFighter(TEXT("e"), Opp, 9, 1)};
  FString Reason;

  // ---- MS-E-07 / MS-E-08: offers, null never, +0 labelled ----
  {
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    TArray<FString> Offered;
    for (const FS09BoostCard& Card : Ui.BoostOffers()) Offered.Add(Card.InstanceId + Card.Label());
    TestEqual(TEXT("null BOOST never offered; +0 offered as '+0'"), FString::Join(Offered, TEXT(",")),
              FString(TEXT("c2+2,c4+4,c0+0,c4b+4")));
    TestFalse(TEXT("null BOOST card refused"), Ui.ToggleBoostCard(TEXT("cn"), Snap, Board, Fighters, Reason));
    TestEqual(TEXT("why.boost.no.value"), MsKey(Ui.LastReason), FString(TEXT("why.boost.no.value")));
    TestTrue(TEXT("no boost after the refusal"), Ui.BoostCardId.IsEmpty());
    TestEqual(TEXT("max hand BOOST ignores null"), Ui.Eval.MaxBoost, 4);
  }

  // ---- MS-E-14 / MS-E-13 / MS-E-78: one move, boost swapped and removed ----
  {
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    TestTrue(TEXT("A selected"), Ui.SelectFighter(TEXT("a"), Snap, Board, Fighters));
    // MS-E-80 without a card: base <= 3, boost tier 4..7, chip = dist - movement.
    TestEqual(TEXT("base steps 3"), Ui.SelectedTiers.BaseSteps, 3);
    TestEqual(TEXT("boost steps 3 + 4"), Ui.SelectedTiers.BoostSteps, 7);
    TestTrue(TEXT("base tier within 1..3"), MsAllWithin(Ui.SelectedTiers, Ui.SelectedTiers.BaseTier, 0, 3) &&
                                               Ui.SelectedTiers.BaseTier.Contains(FIntPoint(3, 0)));
    TestTrue(TEXT("boost tier within 4..7"), MsAllWithin(Ui.SelectedTiers, Ui.SelectedTiers.BoostTier, 3, 7) &&
                                                Ui.SelectedTiers.BoostTier.Contains(FIntPoint(4, 0)) &&
                                                Ui.SelectedTiers.BoostTier.Contains(FIntPoint(7, 0)));
    TestEqual(TEXT("chip at 6 steps = +3"), Ui.SelectedTiers.ChipAt(FIntPoint(6, 0)), 3);
    TestEqual(TEXT("no chip on the base tier"), Ui.SelectedTiers.ChipAt(FIntPoint(2, 0)), 0);

    // Beyond the best boost: need 8, have 3 + 4.
    TestFalse(TEXT("8 steps refused"), Ui.SetDestination(TEXT("a"), 8, 0, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("why.cell.unreachable"), MsKey(Ui.LastReason), FString(TEXT("why.cell.unreachable")));
    TestTrue(TEXT("need 8 have 7"), Ui.LastReason.Args.FindRef(TEXT("need")) == TEXT("8") &&
                                        Ui.LastReason.Args.FindRef(TEXT("have")) == TEXT("7"));

    // MS-E-14: boost-tier cell without a card -> NeedBoost(3), cards >= 3 lit.
    TestTrue(TEXT("6 steps accepted as NeedBoost"), Ui.SetDestination(TEXT("a"), 6, 0, Snap, Board, Fighters, Reason));
    const FS09DraftMove* A = MsMove(Ui, TEXT("a"));
    TestEqual(TEXT("NeedBoost"), MsStatus(A), FString(TEXT("needBoost")));
    TestEqual(TEXT("RequiredBoost 3"), A ? A->RequiredBoost : -1, 3);
    TestEqual(TEXT("why.cell.needs.boost"), A ? MsKey(A->Reason) : FString(), FString(TEXT("why.cell.needs.boost")));
    TestEqual(TEXT("badge 6/3 need +3"), A ? A->BadgeText() : FString(), FString(TEXT("6/3 \u00B7 need +3")));
    TestEqual(TEXT("highlight BOOST >= 3"), Ui.Eval.HighlightMinBoost, 3);
    TestEqual(TEXT("lit cards c4, c4b"), FString::Join(Ui.Eval.HighlightCardIds, TEXT(",")),
              FString(TEXT("c4,c4b")));
    FS09ManeuverCommand Command;
    TestFalse(TEXT("NeedBoost blocks the confirm"), Ui.ConfirmManeuver(Snap, Board, Fighters, Command, Reason));
    TestTrue(TEXT("confirm reason: needs boost"), Reason.Contains(TEXT("why.cell.needs.boost")));

    // MS-E-78: +2 selected, movement 3, 6 steps -> NeedBoost(3), badge "6/5 need +3".
    const uint32 Rev = Ui.DraftRevision;
    TestTrue(TEXT("+2 selected"), Ui.ToggleBoostCard(TEXT("c2"), Snap, Board, Fighters, Reason));
    TestTrue(TEXT("re-evaluated in the same call"), Ui.DraftRevision != Rev);
    A = MsMove(Ui, TEXT("a"));
    TestEqual(TEXT("still NeedBoost(3), not 1"), A ? A->RequiredBoost : -1, 3);
    TestEqual(TEXT("badge 6/5 need +3"), A ? A->BadgeText() : FString(), FString(TEXT("6/5 \u00B7 need +3")));
    TestEqual(TEXT("lit cards still c4, c4b"), FString::Join(Ui.Eval.HighlightCardIds, TEXT(",")),
              FString(TEXT("c4,c4b")));
    // MS-E-80 with +2: base <= 5, boost tier 6..7.
    TestEqual(TEXT("base steps 5 with +2"), Ui.SelectedTiers.BaseSteps, 5);
    TestTrue(TEXT("boost tier 6..7 with +2"), MsAllWithin(Ui.SelectedTiers, Ui.SelectedTiers.BoostTier, 5, 7) &&
                                                 Ui.SelectedTiers.BoostTier.Contains(FIntPoint(6, 0)) &&
                                                 Ui.SelectedTiers.BaseTier.Contains(FIntPoint(5, 0)));
    TestTrue(TEXT("legacy reach follows the boost (5 steps)"), Ui.ReachableCells.Contains(FS08BoardModel::CellKey(5, 0)) &&
                                                                  !Ui.ReachableCells.Contains(FS08BoardModel::CellKey(6, 0)));

    // +4 replaces +2: Ok, nothing lit, boost tier empty (s = M).
    TestTrue(TEXT("+4 replaces +2"), Ui.ToggleBoostCard(TEXT("c4"), Snap, Board, Fighters, Reason));
    TestEqual(TEXT("one card per maneuver"), Ui.BoostCardId, FString(TEXT("c4")));
    TestEqual(TEXT("Ok with +4"), MsStatus(MsMove(Ui, TEXT("a"))), FString(TEXT("ok")));
    TestEqual(TEXT("badge 6/7"), MsMove(Ui, TEXT("a")) ? MsMove(Ui, TEXT("a"))->BadgeText() : FString(),
              FString(TEXT("6/7")));
    TestEqual(TEXT("nothing lit"), Ui.Eval.HighlightCardIds.Num(), 0);
    TestEqual(TEXT("boost tier empty at s = M"), Ui.SelectedTiers.BoostTier.Num(), 0);
    TestTrue(TEXT("confirm legal with +4"), Ui.ConfirmManeuver(Snap, Board, Fighters, Command, Reason));
    TestEqual(TEXT("boost card sent"), Command.BoostCardId, FString(TEXT("c4")));

    // MS-E-12: the second copy is a different exact instance.
    TestTrue(TEXT("copy c4b replaces c4"), Ui.ToggleBoostCard(TEXT("c4b"), Snap, Board, Fighters, Reason));
    TestEqual(TEXT("exact copy selected"), Ui.BoostCardId, FString(TEXT("c4b")));

    // MS-E-13: boost removed -> NeedBoost (not Conflict), the move stays.
    TestTrue(TEXT("boost toggled off"), Ui.ToggleBoostCard(TEXT("c4b"), Snap, Reason));
    TestTrue(TEXT("no boost"), Ui.BoostCardId.IsEmpty());
    TestEqual(TEXT("NeedBoost after removal"), MsStatus(MsMove(Ui, TEXT("a"))), FString(TEXT("needBoost")));
    TestEqual(TEXT("the move stays"), Ui.Moves.Num(), 1);

    // MS-E-08: +0 is a legal pick that changes nothing.
    TestTrue(TEXT("+0 selected"), Ui.ToggleBoostCard(TEXT("c0"), Snap, Board, Fighters, Reason));
    TestEqual(TEXT("selected BOOST 0"), Ui.Eval.SelectedBoost, 0);
    TestEqual(TEXT("NeedBoost(3) with +0"), MsMove(Ui, TEXT("a")) ? MsMove(Ui, TEXT("a"))->RequiredBoost : -1, 3);
    TestEqual(TEXT("base steps unchanged by +0"), Ui.SelectedTiers.BaseSteps, 3);

    // Deselect drops the tiers with the id; a local reset keeps the hand data.
    Ui.DeselectFighter();
    TestTrue(TEXT("deselect clears tiers and reach"),
             Ui.SelectedFighterId.IsEmpty() && !Ui.SelectedTiers.bValid && Ui.ReachableCells.Num() == 0);
    Ui.CancelDraft();
    TestTrue(TEXT("reset empties the draft"), Ui.Moves.Num() == 0 && Ui.BoostCardId.IsEmpty());
    TestEqual(TEXT("reset keeps the hand's max BOOST"), Ui.Eval.MaxBoost, 4);
    TestEqual(TEXT("reset keeps the offers"), Ui.BoostOffers().Num(), 4);
  }

  // ---- MS-E-79: two moves needing 2 and 4 ----
  {
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    TestTrue(TEXT("A needs +2"), Ui.SetDestination(TEXT("a"), 5, 0, Snap, Board, Fighters, Reason));
    TestTrue(TEXT("B needs +4"), Ui.SetDestination(TEXT("b"), 7, 2, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("A required 2"), MsMove(Ui, TEXT("a")) ? MsMove(Ui, TEXT("a"))->RequiredBoost : -1, 2);
    TestEqual(TEXT("B required 4"), MsMove(Ui, TEXT("b")) ? MsMove(Ui, TEXT("b"))->RequiredBoost : -1, 4);
    TestEqual(TEXT("highlight BOOST >= 4"), Ui.Eval.HighlightMinBoost, 4);
    TestEqual(TEXT("lit c4, c4b"), FString::Join(Ui.Eval.HighlightCardIds, TEXT(",")), FString(TEXT("c4,c4b")));
    TestTrue(TEXT("+2 selected"), Ui.ToggleBoostCard(TEXT("c2"), Snap, Board, Fighters, Reason));
    TestEqual(TEXT("+2 solves A"), MsStatus(MsMove(Ui, TEXT("a"))), FString(TEXT("ok")));
    TestEqual(TEXT("+2 leaves B NeedBoost(4)"), MsStatus(MsMove(Ui, TEXT("b"))), FString(TEXT("needBoost")));
    TestTrue(TEXT("+4 selected"), Ui.ToggleBoostCard(TEXT("c4"), Snap, Board, Fighters, Reason));
    TestTrue(TEXT("+4 solves both"), Ui.Eval.IsConfirmable() && Ui.Eval.NumOk == 2);
  }

  // ---- a raw move beyond the best boost is a Conflict (no path within
  // base + max hand BOOST), never NeedBoost ----
  {
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    Ui.Moves.AddDefaulted(1);
    Ui.Moves[0].FighterId = TEXT("a");
    Ui.Moves[0].DestX = 9;
    Ui.Moves[0].DestY = 2; // 11 steps: beyond 3 + 4
    FS09ManeuverCommand Command;
    TestFalse(TEXT("a raw move beyond the best boost does not confirm"),
              Ui.ConfirmManeuver(Snap, Board, Fighters, Command, Reason));
    TestEqual(TEXT("it is a Conflict, not NeedBoost"), MsStatus(MsMove(Ui, TEXT("a"))), FString(TEXT("conflict")));
    TestEqual(TEXT("why.cell.unreachable"), MsKey(Ui.Moves[0].Reason), FString(TEXT("why.cell.unreachable")));
  }
  return true;
}

// ---- MS-T-04 ------------------------------------------------------------------

namespace S09MoveSelTest {

/** Fighter projection entry (the shape DecodeFighters reads); Movement is
 *  set raw (number, string, null) unless absent. */
TSharedRef<FJsonObject> MsFighterJson(const FString& Id, const FString& Owner, int32 X, int32 Y, int32 Health,
                                      TSharedPtr<FJsonValue> Movement, bool bDefeated = false,
                                      const FString& Effect = FString()) {
  TSharedRef<FJsonObject> F = MakeShared<FJsonObject>();
  F->SetStringField(TEXT("id"), Id);
  F->SetStringField(TEXT("ownerId"), Owner);
  F->SetStringField(TEXT("heroId"), TEXT("hero-") + Owner);
  F->SetStringField(TEXT("name"), Id);
  F->SetStringField(TEXT("type"), TEXT("MINION"));
  F->SetNumberField(TEXT("health"), Health);
  F->SetNumberField(TEXT("maxHealth"), 10);
  TSharedRef<FJsonObject> Pos = MakeShared<FJsonObject>();
  Pos->SetNumberField(TEXT("x"), X);
  Pos->SetNumberField(TEXT("y"), Y);
  F->SetObjectField(TEXT("position"), Pos);
  F->SetStringField(TEXT("attackType"), TEXT("melee"));
  F->SetBoolField(TEXT("isDefeated"), bDefeated);
  TArray<TSharedPtr<FJsonValue>> Effects;
  if (!Effect.IsEmpty()) {
    TSharedRef<FJsonObject> E = MakeShared<FJsonObject>();
    E->SetStringField(TEXT("type"), Effect);
    Effects.Add(MakeShared<FJsonValueObject>(E));
  }
  F->SetArrayField(TEXT("effects"), Effects);
  if (Movement.IsValid()) F->SetField(TEXT("movement"), Movement);
  return F;
}

TArray<FS08BoardFighter> MsDecode(const TArray<TSharedRef<FJsonObject>>& Entries) {
  TArray<TSharedPtr<FJsonValue>> Values;
  for (const TSharedRef<FJsonObject>& Entry : Entries) Values.Add(MakeShared<FJsonValueObject>(Entry));
  TArray<FS08BoardFighter> Out;
  FS08BoardModel::DecodeFighters(MakeShared<FJsonValueArray>(Values), Out);
  return Out;
}

TSharedPtr<FJsonValue> MsNum(double V) { return MakeShared<FJsonValueNumber>(V); }
TSharedPtr<FJsonValue> MsStr(const TCHAR* V) { return MakeShared<FJsonValueString>(V); }

/** Snapshot with metadata.pendingEffects = [one head of the viewer]: Type
 *  MOVE / PLACE; Value < 0 = no `value` field (MOVE allowance 1). */
FS08Snapshot MsPendingMoveSnapshot(int32 Value, const TCHAR* Type = TEXT("MOVE"), bool bPassThrough = false,
                                   bool bRevive = false) {
  FS08Snapshot Snapshot = MsSnapshot({}, FString());
  const TSharedRef<FJsonObject> Meta = MakeShared<FJsonObject>(*Snapshot.Metadata->AsObject());
  TSharedRef<FJsonObject> Head = MakeShared<FJsonObject>();
  Head->SetStringField(TEXT("id"), TEXT("effect-1"));
  Head->SetStringField(TEXT("playerId"), Me);
  Head->SetStringField(TEXT("type"), Type);
  if (Value >= 0) Head->SetNumberField(TEXT("value"), Value);
  if (bPassThrough) Head->SetBoolField(TEXT("canPassThroughEnemies"), true);
  if (bRevive) Head->SetBoolField(TEXT("restoreFullHealth"), true);
  Head->SetStringField(TEXT("fighterName"), TEXT(""));
  Head->SetStringField(TEXT("zoneFighterName"), TEXT(""));
  Head->SetStringField(TEXT("mode"), TEXT(""));
  Head->SetStringField(TEXT("text"), TEXT("Move up to 2 spaces"));
  TArray<TSharedPtr<FJsonValue>> Effects = {MakeShared<FJsonValueObject>(Head)};
  Meta->SetArrayField(TEXT("pendingEffects"), Effects);
  Snapshot.Metadata = MakeShared<FJsonValueObject>(Meta);
  return Snapshot;
}

/** The viewer's snapshot with metadata.pendingHandDiscard (no pendingManeuver). */
FS08Snapshot MsDiscardSnapshot(const TArray<FMsCard>& Hand, int32 Seq) {
  FS08Snapshot Snapshot = MsSnapshot(Hand, FString(), Seq);
  Snapshot.Phase = TEXT("TURN_END");
  const TSharedRef<FJsonObject> Meta = MakeShared<FJsonObject>(*Snapshot.Metadata->AsObject());
  TSharedRef<FJsonObject> Discard = MakeShared<FJsonObject>();
  Discard->SetStringField(TEXT("id"), TEXT("discard:1:30"));
  Discard->SetStringField(TEXT("playerId"), Me);
  Discard->SetNumberField(TEXT("count"), 1);
  Meta->SetObjectField(TEXT("pendingHandDiscard"), Discard);
  Snapshot.Metadata = MakeShared<FJsonValueObject>(Meta);
  return Snapshot;
}

bool MsTraced(const FS09CommandUi& Ui, const FString& Needle, int32& OutCount) {
  OutCount = 0;
  for (const FString& Line : Ui.DraftTrace) OutCount += Line.Contains(Needle) ? 1 : 0;
  return OutCount > 0;
}

void MsBindCache(FS09CommandUi& Ui, FS08FlowController& Flow) {
  Ui.StoreDraftHook = [&Flow](const FS08ManeuverDraftCache& Draft) { Flow.StoreManeuverDraft(Draft); };
  Ui.RecallDraftHook = [&Flow](const FString& Id, FS08ManeuverDraftCache& Out) {
    return Flow.RecallManeuverDraft(Id, Out);
  };
}

// The live fixture 04 (S08 evidence) - a full snapshot the controller's
// critical-field gate accepts (the SubmitManeuver leg needs one).
const TCHAR* const LiveHost = TEXT("cmugykjjb0000wi9w2nq4qlkj");

bool MsLoadLiveSnapshot(FS08Snapshot& Out) {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S08Fixtures="), Dir) || Dir.IsEmpty()) {
    Dir = FPaths::Combine(FPaths::ProjectDir(), TEXT("../../docs/game-design/evidence/S08/fixtures"));
  }
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *FPaths::Combine(Dir, TEXT("04-game-state-query-host.json")))) return false;
  TSharedPtr<FJsonValue> Value;
  FString Problem;
  if (!FS08Contracts::TryParseJsonValue(Text, Value, Problem)) return false;
  const TSharedPtr<FJsonObject>* Root = nullptr;
  if (!Value->TryGetObject(Root) || !Root->IsValid()) return false;
  FString Body;
  const TSharedPtr<FJsonObject>* RawObject = nullptr;
  if ((*Root)->TryGetStringField(TEXT("raw"), Body)) {
    // raw is the response text
  } else if ((*Root)->TryGetObjectField(TEXT("raw"), RawObject) && RawObject->IsValid()) {
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Body);
    FJsonSerializer::Serialize(RawObject->ToSharedRef(), Writer);
  }
  FString RawState;
  FS08GraphQLError Error;
  if (!FS08Contracts::ParseGameStateQuery(Body, Out, RawState, Error)) return false;
  const TSharedRef<FJsonObject> Meta = MakeShared<FJsonObject>(*(Out.Metadata->AsObject()));
  TSharedRef<FJsonObject> Pending = MakeShared<FJsonObject>();
  Pending->SetStringField(TEXT("id"), TEXT("maneuver:1:5"));
  Pending->SetStringField(TEXT("playerId"), LiveHost);
  Meta->SetObjectField(TEXT("pendingManeuver"), Pending);
  Out.Metadata = MakeShared<FJsonValueObject>(Meta);
  return true;
}

/** graphql-transport-ws 'next' for the harness op s08-1 at the baseline seq
 *  (proves the operation live; the equal seq merges). */
FString MsBarrierFrame(const FS08Snapshot& Baseline) {
  TSharedRef<FJsonObject> Event = MakeShared<FJsonObject>();
  Event->SetNumberField(TEXT("sequenceNumber"), Baseline.SequenceNumber);
  Event->SetStringField(TEXT("phase"), Baseline.Phase);
  Event->SetNumberField(TEXT("turnCount"), Baseline.TurnCount);
  Event->SetStringField(TEXT("currentTurnPlayerId"), Baseline.CurrentTurnPlayerId);
  TSharedRef<FJsonObject> Data = MakeShared<FJsonObject>();
  Data->SetObjectField(TEXT("gameStateUpdated"), Event);
  TSharedRef<FJsonObject> Payload = MakeShared<FJsonObject>();
  Payload->SetObjectField(TEXT("data"), Data);
  TSharedRef<FJsonObject> Frame = MakeShared<FJsonObject>();
  Frame->SetStringField(TEXT("type"), TEXT("next"));
  Frame->SetStringField(TEXT("id"), TEXT("s08-1"));
  Frame->SetObjectField(TEXT("payload"), Payload);
  FString Out;
  FJsonSerializer::Serialize(Frame, TJsonWriterFactory<>::Create(&Out));
  return Out;
}

} // namespace S09MoveSelTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelZeroLengthNotSentTest, "Unmatched.S09.MoveSel.ZeroLengthNotSent",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelZeroLengthNotSentTest::RunTest(const FString&) {
  const FS08BoardModel Board = MsGrid(5, 5);
  const FS08Snapshot Snap = MsSnapshot({{TEXT("c2"), true, 2}});
  const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 1, 1), MsFighter(TEXT("b"), Me, 3, 3)};
  FString Reason;
  FS09ManeuverCommand Command;

  // ---- MS-E-16: the own cell never becomes a move ----
  FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
  TestTrue(TEXT("own cell without a move: accepted"), Ui.SetDestination(TEXT("a"), 1, 1, Snap, Board, Fighters, Reason));
  TestEqual(TEXT("no zero-length move recorded"), Ui.Moves.Num(), 0);
  TestTrue(TEXT("A drafted"), Ui.SetDestination(TEXT("a"), 2, 1, Snap, Board, Fighters, Reason));
  TestTrue(TEXT("B drafted"), Ui.SetDestination(TEXT("b"), 4, 3, Snap, Board, Fighters, Reason));
  TestTrue(TEXT("own cell clears A's move (MS-R-11)"), Ui.SetDestination(TEXT("a"), 1, 1, Snap, Board, Fighters, Reason));
  TestEqual(TEXT("A's move gone, B's kept"), Ui.Moves.Num(), 1);
  TestEqual(TEXT("B moved up to 0"), Ui.MoveIndexOf(TEXT("b")), 0);
  int32 Clears = 0;
  MsTraced(Ui, TEXT("MS-DRAFT op=clear"), Clears);
  TestEqual(TEXT("one MS-DRAFT op=clear"), Clears, 1);

  // ---- a stay entry that slipped into the draft is never sent ----
  Ui.Moves.AddDefaulted_GetRef().FighterId = TEXT("a");
  Ui.Moves.Last().DestX = 1;
  Ui.Moves.Last().DestY = 1;
  TestTrue(TEXT("confirm with a stay entry"), Ui.ConfirmManeuver(Snap, Board, Fighters, Command, Reason));
  TestEqual(TEXT("only B in the command"), Command.Moves.Num(), 1);
  bool bEmptyPath = false;
  for (const FS08ManeuverMove& Move : Command.Moves) bEmptyPath |= Move.Path.IsEmpty();
  TestFalse(TEXT("no empty path in the command (MS-R-44)"), bEmptyPath);

  // ---- MS-E-09: no moves + a boost is a legal maneuver ----
  FS09CommandUi Boosted = MsOpen(Snap, Board, Fighters);
  TestTrue(TEXT("boost selected"), Boosted.ToggleBoostCard(TEXT("c2"), Snap, Board, Fighters, Reason));
  TestTrue(TEXT("boost without moves confirms"), Boosted.ConfirmManeuver(Snap, Board, Fighters, Command, Reason));
  TestEqual(TEXT("zero moves"), Command.Moves.Num(), 0);
  TestEqual(TEXT("boost card sent"), Command.BoostCardId, FString(TEXT("c2")));

  // ---- SubmitManeuver drops an empty path before the wire (MS-R-44) ----
  FS08Snapshot Live;
  if (!MsLoadLiveSnapshot(Live)) {
    AddError(TEXT("fixture 04 not loaded"));
    return true;
  }
  FS08FlowController Flow(TEXT("http://127.0.0.1:9/graphql"), TEXT("ws://127.0.0.1:9/graphql"), LiveHost);
  TArray<FString> Traces;
  Flow.OnTrace.AddLambda([&Traces](const FString& Line) { Traces.Add(Line); });
  Flow.AttachStreamHarnessForTest(TEXT("ms-zero-game"));
  Flow.ApplySnapshot(Live);
  Flow.InjectWsFrameForTest(MsBarrierFrame(Flow.GetAppliedSnapshot()));
  TestTrue(TEXT("stream live"), Flow.IsStreamReady());
  Flow.QueueHttpResultForTest(false, {}, /*bDeferDelivery=*/true); // no real POST
  TArray<FS08ManeuverMove> Moves;
  Moves.AddDefaulted_GetRef().FighterId = TEXT("f-0-hero"); // stay: empty path
  FS08ManeuverMove& Step = Moves.AddDefaulted_GetRef();
  Step.FighterId = TEXT("f-0-sk0");
  Step.Path = {FIntPoint(0, 2)};
  TestTrue(TEXT("submit dispatched"), Flow.SubmitManeuver(TEXT("maneuver:1:5"), Moves));
  TestEqual(TEXT("one HTTP leg"), Flow.GetTestHttpSendCountForTest(), 1);
  bool bDropped = false;
  for (const FString& Line : Traces) bDropped |= Line.Contains(TEXT("MANEUVER zero-length moves dropped=1 sent=1"));
  TestTrue(TEXT("the stay entry is dropped before the wire (trace)"), bDropped);
  const TSharedPtr<FJsonObject> Sent = Flow.GetLastHttpVariablesForTest();
  const TArray<TSharedPtr<FJsonValue>>* WireMoves = nullptr;
  TestTrue(TEXT("maneuver variables captured"), Sent.IsValid() && Sent->TryGetArrayField(TEXT("moves"), WireMoves));
  if (WireMoves) {
    TestEqual(TEXT("one move on the wire"), WireMoves->Num(), 1);
    for (const TSharedPtr<FJsonValue>& Move : *WireMoves) {
      const TArray<TSharedPtr<FJsonValue>>* Path = nullptr;
      TestTrue(TEXT("the wire move has a non-empty path"),
               Move->AsObject()->TryGetArrayField(TEXT("path"), Path) && Path->Num() == 1);
      TestEqual(TEXT("the wire move is the sidekick's"), Move->AsObject()->GetStringField(TEXT("fighterId")),
                FString(TEXT("f-0-sk0")));
    }
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelMovementParityTest, "Unmatched.S09.MoveSel.MovementParity",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelMovementParityTest::RunTest(const FString&) {
  const FS08BoardModel Board = MsGrid(9, 9);
  const FS08Snapshot Snap = MsSnapshot({});
  FString Reason;

  // ---- MS-E-04 / MS-E-107: getFighterMovement on the raw value ----
  {
    struct FCase {
      const TCHAR* Id;
      TSharedPtr<FJsonValue> Raw; // invalid = absent
      int32 Base;
    };
    const TArray<FCase> Cases = {{TEXT("m0"), MsNum(0), 2},        {TEXT("mabsent"), nullptr, 2},
                                 {TEXT("mnull"), MakeShared<FJsonValueNull>(), 2},
                                 {TEXT("m25"), MsNum(2.5), 2},     {TEXT("m35"), MsNum(3.5), 2},
                                 {TEXT("ms3"), MsStr(TEXT("3")), 3}, {TEXT("ms35"), MsStr(TEXT("3.5")), 2},
                                 {TEXT("m4"), MsNum(4), 4}};
    const FS08BoardModel Open = MsGrid(13, 13);
    for (const FCase& Case : Cases) {
      const TArray<FS08BoardFighter> Fighters = MsDecode({MsFighterJson(Case.Id, Me, 6, 6, 5, Case.Raw)});
      FS09CommandUi Ui = MsOpen(Snap, Open, Fighters);
      TestTrue(FString::Printf(TEXT("%s selectable"), Case.Id), Ui.SelectFighter(Case.Id, Snap, Open, Fighters));
      TestEqual(FString::Printf(TEXT("%s base"), Case.Id), Ui.SelectedTiers.Base, Case.Base);
      TestTrue(FString::Printf(TEXT("%s: base steps reachable"), Case.Id),
               Ui.SetDestination(Case.Id, 6 + Case.Base, 6, Snap, Open, Fighters, Reason));
      TestFalse(FString::Printf(TEXT("%s: base + 1 refused without a boost"), Case.Id),
                Ui.SetDestination(Case.Id, 6, 6 + Case.Base + 1, Snap, Open, Fighters, Reason));
      TestEqual(FString::Printf(TEXT("%s: have = base"), Case.Id), Ui.LastReason.Args.FindRef(TEXT("have")),
                FString::FromInt(Case.Base));
    }
  }

  // ---- MS-E-40 / MS-R-05: an immobilized fighter is greyed, others move ----
  {
    const TArray<FS08BoardFighter> Fighters =
        MsDecode({MsFighterJson(TEXT("imm"), Me, 1, 1, 5, MsNum(3), false, TEXT("immobilized")),
                  MsFighterJson(TEXT("free"), Me, 6, 6, 5, MsNum(3))});
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    FS09Reason Why;
    TestFalse(TEXT("CanMoveFighter refuses the immobilized"), Ui.CanMoveFighter(TEXT("imm"), Fighters, Why));
    TestEqual(TEXT("why.immobilized"), MsKey(Why), FString(TEXT("why.immobilized")));
    TestEqual(TEXT("reason names the fighter"), Why.Args.FindRef(TEXT("fighterName")), FString(TEXT("imm")));
    TestFalse(TEXT("immobilized not selectable"), Ui.SelectFighter(TEXT("imm"), Snap, Board, Fighters));
    TestEqual(TEXT("select reason why.immobilized"), MsKey(Ui.LastReason), FString(TEXT("why.immobilized")));
    TestFalse(TEXT("no target for the immobilized"), Ui.SetDestination(TEXT("imm"), 2, 1, Snap, Board, Fighters, Reason));
    TestTrue(TEXT("refusal reason names the key"), Reason.Contains(TEXT("why.immobilized")));
    TestEqual(TEXT("nothing drafted"), Ui.Moves.Num(), 0);
    TestTrue(TEXT("the other fighter moves"), Ui.SetDestination(TEXT("free"), 6, 4, Snap, Board, Fighters, Reason));

    // A drafted move whose fighter becomes immobilized stays as a Conflict.
    const TArray<FS08BoardFighter> Before = MsDecode({MsFighterJson(TEXT("x"), Me, 1, 1, 5, MsNum(3))});
    FS09CommandUi Later = MsOpen(Snap, Board, Before);
    TestTrue(TEXT("x drafted"), Later.SetDestination(TEXT("x"), 3, 1, Snap, Board, Before, Reason));
    const TArray<FS08BoardFighter> After =
        MsDecode({MsFighterJson(TEXT("x"), Me, 1, 1, 5, MsNum(3), false, TEXT("immobilized"))});
    Later.OnSnapshot(MsSnapshot({}, ManeuverA, 6), Board, After);
    TestEqual(TEXT("the move is kept"), Later.Moves.Num(), 1);
    TestEqual(TEXT("as a Conflict"), MsStatus(MsMove(Later, TEXT("x"))), FString(TEXT("conflict")));
    TestEqual(TEXT("why.immobilized"), MsMove(Later, TEXT("x")) ? MsKey(MsMove(Later, TEXT("x"))->Reason) : FString(),
              FString(TEXT("why.immobilized")));
    TestTrue(TEXT("own-cell click still clears it"), Later.SetDestination(TEXT("x"), 1, 1, Snap, Board, After, Reason));
    TestEqual(TEXT("cleared"), Later.Moves.Num(), 0);
  }

  // ---- MS-E-23 / MS-E-24: defeated blockers and occupants ----
  {
    // Corridor y = 1 (rows 0 and 2 walled), 6 wide.
    const FS08BoardModel Corridor =
        MsGrid(6, 3, {FIntPoint(0, 0), FIntPoint(1, 0), FIntPoint(2, 0), FIntPoint(3, 0), FIntPoint(4, 0),
                      FIntPoint(5, 0), FIntPoint(0, 2), FIntPoint(1, 2), FIntPoint(2, 2), FIntPoint(3, 2),
                      FIntPoint(4, 2), FIntPoint(5, 2)});
    const TArray<FS08BoardFighter> Fighters =
        MsDecode({MsFighterJson(TEXT("m"), Me, 0, 1, 5, MsNum(4)),
                  MsFighterJson(TEXT("dirty-enemy"), Opp, 1, 1, 5, MsNum(2), /*bDefeated=*/true),
                  MsFighterJson(TEXT("dead-enemy"), Opp, 2, 1, 0, MsNum(2)),
                  MsFighterJson(TEXT("dirty-ally"), Me, 3, 1, 5, MsNum(2), /*bDefeated=*/true)});
    FS09CommandUi Ui = MsOpen(Snap, Corridor, Fighters);
    TestTrue(TEXT("through a dirty-defeated and a dead enemy onto a dirty-defeated ally's cell"),
             Ui.SetDestination(TEXT("m"), 3, 1, Snap, Corridor, Fighters, Reason));
    const FS09DraftMove* M = MsMove(Ui, TEXT("m"));
    TestTrue(TEXT("path (1,1) (2,1) (3,1)"),
             M && MsSameCells(M->Path, {FIntPoint(1, 1), FIntPoint(2, 1), FIntPoint(3, 1)}));
    TestEqual(TEXT("ok"), MsStatus(M), FString(TEXT("ok")));
  }

  // ---- MS-E-77: a dirty-defeated MOVER moves (as the server), MS-DATA ----
  {
    const TArray<FS08BoardFighter> Fighters =
        MsDecode({MsFighterJson(TEXT("dirty"), Me, 2, 2, 3, MsNum(3), /*bDefeated=*/true),
                  MsFighterJson(TEXT("dead"), Me, 5, 5, 0, MsNum(3))});
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    TestTrue(TEXT("dirty-defeated mover selectable"), Ui.SelectFighter(TEXT("dirty"), Snap, Board, Fighters));
    TestTrue(TEXT("dirty-defeated mover drafted"), Ui.SetDestination(TEXT("dirty"), 4, 2, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("ok"), MsStatus(MsMove(Ui, TEXT("dirty"))), FString(TEXT("ok")));
    int32 Count = 0;
    MsTraced(Ui, TEXT("MS-DATA dirtyDefeated fighter=dirty"), Count);
    TestEqual(TEXT("MS-DATA dirtyDefeated once per maneuver"), Count, 1);
    TestFalse(TEXT("health 0 is not a mover"), Ui.SelectFighter(TEXT("dead"), Snap, Board, Fighters));
    TestEqual(TEXT("why.fighter.defeated"), MsKey(Ui.LastReason), FString(TEXT("why.fighter.defeated")));
    TArray<FS08BoardFighter> WithEnemy = Fighters;
    WithEnemy.Add(MsFighter(TEXT("enemy"), Opp, 7, 7));
    FS09Reason Why;
    TestFalse(TEXT("an enemy fighter is no mover"), Ui.CanMoveFighter(TEXT("enemy"), WithEnemy, Why));
    TestEqual(TEXT("why.fighter.not.yours"), MsKey(Why), FString(TEXT("why.fighter.not.yours")));
    TestFalse(TEXT("an unknown id is no mover"), Ui.CanMoveFighter(TEXT("ghost"), WithEnemy, Why));
    TestEqual(TEXT("why.client.desync"), MsKey(Why), FString(TEXT("why.client.desync")));
  }

  // ---- pending MOVE: the moved fighter and the blockers use isLivingFighter ----
  {
    const TArray<FS08BoardFighter> Fighters =
        MsDecode({MsFighterJson(TEXT("p"), Me, 0, 4, 5, MsNum(3)),
                  MsFighterJson(TEXT("dirty-own"), Me, 8, 8, 5, MsNum(3), /*bDefeated=*/true),
                  MsFighterJson(TEXT("dirty-enemy"), Opp, 1, 4, 5, MsNum(3), /*bDefeated=*/true)});
    const FS08Snapshot Pending = MsPendingMoveSnapshot(2);
    FS09CommandUi Ui = MsOpen(Pending, Board, Fighters);
    TestTrue(TEXT("pending choice open"), Ui.Mode == ES09CommandMode::PendingChoice);
    TArray<FString> Legal;
    Ui.PendingLegalFighters(Fighters, Legal);
    TestTrue(TEXT("living own fighter is a legal MOVE target"), Legal.Contains(TEXT("p")));
    TestFalse(TEXT("dirty-defeated fighter is not (server isLivingFighter)"), Legal.Contains(TEXT("dirty-own")));
    TestTrue(TEXT("pick p"), Ui.SelectPendingFighter(TEXT("p"), Pending, Fighters, Reason));
    const TSet<uint64> Cells = Ui.ComputePendingCells(Pending, Board, Fighters);
    TestTrue(TEXT("stay is legal"), Cells.Contains(FS08BoardModel::CellKey(0, 4)));
    TestTrue(TEXT("a dirty-defeated enemy does not block"), Cells.Contains(FS08BoardModel::CellKey(2, 4)));
    TestTrue(TEXT("its cell is free"), Cells.Contains(FS08BoardModel::CellKey(1, 4)));
    TestFalse(TEXT("3 steps exceed value 2"), Cells.Contains(FS08BoardModel::CellKey(3, 4)));

    // value 0 -> only "stay" (MS-E-76); absent -> 1 step (MS-E-57).
    const FS08Snapshot Zero = MsPendingMoveSnapshot(0);
    FS09CommandUi ZeroUi = MsOpen(Zero, Board, Fighters);
    ZeroUi.SelectPendingFighter(TEXT("p"), Zero, Fighters, Reason);
    const TSet<uint64> ZeroCells = ZeroUi.ComputePendingCells(Zero, Board, Fighters);
    TestTrue(TEXT("value 0: only the own cell"), ZeroCells.Num() == 1 && ZeroCells.Contains(FS08BoardModel::CellKey(0, 4)));
    const FS08Snapshot Absent = MsPendingMoveSnapshot(-1);
    FS09CommandUi AbsentUi = MsOpen(Absent, Board, Fighters);
    AbsentUi.SelectPendingFighter(TEXT("p"), Absent, Fighters, Reason);
    const TSet<uint64> OneCells = AbsentUi.ComputePendingCells(Absent, Board, Fighters);
    TestTrue(TEXT("no value: 1 step"), OneCells.Contains(FS08BoardModel::CellKey(0, 3)) &&
                                          !OneCells.Contains(FS08BoardModel::CellKey(0, 2)));

    // A LIVING enemy blocks unless the effect passes through enemies (MS-E-60).
    TArray<FS08BoardFighter> Walled = Fighters;
    Walled.Add(MsFighter(TEXT("wall-n"), Opp, 0, 3));
    Walled.Add(MsFighter(TEXT("wall-e"), Opp, 1, 3));
    Walled.Add(MsFighter(TEXT("wall-s"), Opp, 0, 5));
    Walled.Add(MsFighter(TEXT("wall-se"), Opp, 1, 5));
    Walled.Add(MsFighter(TEXT("wall-ee"), Opp, 2, 4));
    // p at (0,4): (1,4) is free (the dirty-defeated enemy), (2,4) a living enemy.
    FS09CommandUi Blocked = MsOpen(Pending, Board, Walled);
    Blocked.SelectPendingFighter(TEXT("p"), Pending, Walled, Reason);
    const TSet<uint64> BlockedCells = Blocked.ComputePendingCells(Pending, Board, Walled);
    TestTrue(TEXT("boxed in: own cell and (1,4) only"),
             BlockedCells.Num() == 2 && BlockedCells.Contains(FS08BoardModel::CellKey(1, 4)));
    const FS08Snapshot Through = MsPendingMoveSnapshot(2, TEXT("MOVE"), /*bPassThrough=*/true);
    FS09CommandUi ThroughUi = MsOpen(Through, Board, Walled);
    ThroughUi.SelectPendingFighter(TEXT("p"), Through, Walled, Reason);
    const TSet<uint64> ThroughCells = ThroughUi.ComputePendingCells(Through, Board, Walled);
    TestTrue(TEXT("pass-through: beyond the enemies, never onto them"),
             ThroughCells.Contains(FS08BoardModel::CellKey(0, 2)) && !ThroughCells.Contains(FS08BoardModel::CellKey(0, 3)));

    // Revive PLACE may pick a defeated fighter (restoreFullHealth); a plain PLACE may not.
    TArray<FS08BoardFighter> WithDead = Fighters;
    WithDead.Add(MsFighter(TEXT("fallen"), Me, 5, 5, 3.0, 0));
    const FS08Snapshot Revive = MsPendingMoveSnapshot(-1, TEXT("PLACE"), false, /*bRevive=*/true);
    FS09CommandUi ReviveUi = MsOpen(Revive, Board, WithDead);
    TArray<FString> ReviveLegal;
    ReviveUi.PendingLegalFighters(WithDead, ReviveLegal);
    TestTrue(TEXT("revive PLACE: the fallen fighter is legal"), ReviveLegal.Contains(TEXT("fallen")));
    const FS08Snapshot Place = MsPendingMoveSnapshot(-1, TEXT("PLACE"));
    FS09CommandUi PlaceUi = MsOpen(Place, Board, WithDead);
    TArray<FString> PlaceLegal;
    PlaceUi.PendingLegalFighters(WithDead, PlaceLegal);
    TestFalse(TEXT("plain PLACE: the fallen fighter is not"), PlaceLegal.Contains(TEXT("fallen")));
    TestFalse(TEXT("plain PLACE: nor the dirty-defeated one"), PlaceLegal.Contains(TEXT("dirty-own")));
  }
  return true;
}

// ---- MS-T-06: rule codes, reasons by key, the in-flight gate --------------------

namespace S09MoveSelTest {

/** 02 §1.1, typed here by hand (independent of FS08RuleCodes' own table):
 *  code -> key for the maneuver commands / for a pending MOVE-PLACE resolve,
 *  class И (true) / С (false). PATH_BLOCKED_BY_ENEMY: the off-target form. */
struct FMsRuleRow {
  const TCHAR* Code;
  const TCHAR* ManeuverKey;
  const TCHAR* EffectKey;
  bool bManeuverFixable;
  bool bEffectFixable;
};
const FMsRuleRow MsRuleTable[] = {
    {TEXT("FIGHTER_NOT_FOUND"), TEXT("why.client.desync"), TEXT("why.client.desync"), false, false},
    {TEXT("NOT_YOUR_FIGHTER"), TEXT("why.fighter.not.yours"), TEXT("why.fighter.not.yours"), true, true},
    {TEXT("FIGHTER_DEFEATED"), TEXT("why.fighter.defeated"), TEXT("why.fighter.defeated"), false, false},
    {TEXT("FIGHTER_IMMOBILIZED"), TEXT("why.immobilized"), TEXT("why.immobilized"), true, true},
    {TEXT("INVALID_PHASE"), TEXT("why.maneuver.not.open"), TEXT("why.maneuver.not.open"), false, false},
    {TEXT("HAND_NOT_FOUND"), TEXT("why.client.desync"), TEXT("why.client.desync"), false, false},
    {TEXT("CARD_NOT_IN_HAND"), TEXT("why.boost.card.gone"), TEXT("why.boost.card.gone"), true, true},
    {TEXT("EMPTY_PATH"), TEXT("why.client.desync"), TEXT("why.client.desync"), false, false},
    {TEXT("INVALID_POSITION"), TEXT("why.client.desync"), TEXT("why.cell.not.space"), false, true},
    {TEXT("NOT_ENOUGH_MOVEMENT"), TEXT("why.cell.unreachable"), TEXT("why.cell.unreachable"), true, true},
    {TEXT("INVALID_STEP"), TEXT("why.client.desync"), TEXT("why.client.desync"), false, false},
    {TEXT("PATH_BLOCKED_BY_ENEMY"), TEXT("why.cell.enemy.path"), TEXT("why.cell.enemy.path"), true, true},
    {TEXT("POSITION_OCCUPIED"), TEXT("why.cell.ally"), TEXT("why.cell.occupied"), true, true},
    {TEXT("NOT_YOUR_TURN"), TEXT("why.not.your.turn"), TEXT("why.not.your.turn"), false, false},
    {TEXT("PLAYER_NOT_IN_GAME"), TEXT("why.client.desync"), TEXT("why.client.desync"), false, false},
    {TEXT("BEGIN_NOT_ALLOWED"), TEXT("why.client.desync"), TEXT("why.client.desync"), false, false},
    {TEXT("STATE_CHANGED"), TEXT("why.state.changed"), TEXT("why.state.changed"), false, false},
    {TEXT("PENDING_CHOICE_OPEN"), TEXT("why.state.changed"), TEXT("why.state.changed"), false, false},
    {TEXT("COMBAT_IN_PROGRESS"), TEXT("why.state.changed"), TEXT("why.state.changed"), false, false},
    {TEXT("GAME_OVER"), TEXT("why.state.changed"), TEXT("why.state.changed"), false, false},
    {TEXT("MANEUVER_NOT_OPEN"), TEXT("why.maneuver.not.open"), TEXT("why.maneuver.not.open"), false, false},
    {TEXT("DUPLICATE_FIGHTER"), TEXT("why.client.desync"), TEXT("why.client.desync"), false, false},
    {TEXT("PENDING_WRONG_FIGHTER"), TEXT("why.client.desync"), TEXT("why.client.desync"), false, false},
    {TEXT("PLACE_OUTSIDE_ZONE"), TEXT("why.place.zone"), TEXT("why.place.zone"), true, true},
    {TEXT("BOOST_NO_VALUE"), TEXT("why.boost.no.value"), TEXT("why.boost.no.value"), true, true},
};

FS08GraphQLError MsRuleError(const FString& RuleCode, const FString& Message) {
  FS08GraphQLError Error;
  Error.Code = TEXT("BAD_USER_INPUT");
  Error.Message = Message;
  Error.RuleCode = RuleCode;
  return Error;
}

/** A graph board (original-map style): W spaces "S1".."SW" in a row, y = 0,
 *  each linked to its row neighbours. */
FS08BoardModel MsLine(int32 W) {
  TArray<TSharedPtr<FJsonValue>> Row;
  for (int32 X = 0; X < W; ++X) {
    TSharedRef<FJsonObject> Cell = MakeShared<FJsonObject>();
    Cell->SetNumberField(TEXT("x"), X);
    Cell->SetNumberField(TEXT("y"), 0);
    Cell->SetStringField(TEXT("type"), TEXT("normal"));
    Cell->SetStringField(TEXT("spaceId"), FString::Printf(TEXT("S%d"), X + 1));
    TSharedRef<FJsonObject> Layout = MakeShared<FJsonObject>(); // a map space has a layout point
    Layout->SetNumberField(TEXT("x"), 100 + 200 * X);
    Layout->SetNumberField(TEXT("y"), 100);
    Cell->SetObjectField(TEXT("layout"), Layout);
    TArray<TSharedPtr<FJsonValue>> Links;
    for (const int32 N : {X - 1, X + 1}) {
      if (N < 0 || N >= W) continue;
      TSharedRef<FJsonObject> Link = MakeShared<FJsonObject>();
      Link->SetNumberField(TEXT("x"), N);
      Link->SetNumberField(TEXT("y"), 0);
      Links.Add(MakeShared<FJsonValueObject>(Link));
    }
    Cell->SetArrayField(TEXT("links"), Links);
    Row.Add(MakeShared<FJsonValueObject>(Cell));
  }
  TArray<TSharedPtr<FJsonValue>> Lines = {MakeShared<FJsonValueArray>(Row)};
  TSharedRef<FJsonObject> Board = MakeShared<FJsonObject>();
  Board->SetNumberField(TEXT("width"), W);
  Board->SetNumberField(TEXT("height"), 1);
  Board->SetArrayField(TEXT("cells"), Lines);
  Board->SetObjectField(TEXT("doors"), MakeShared<FJsonObject>());
  FS08BoardModel Model;
  Model.Decode(MakeShared<FJsonValueObject>(Board));
  return Model;
}

/** The live fixture snapshot without metadata.pendingManeuver (a turn before begin). */
FS08Snapshot MsWithoutManeuver(const FS08Snapshot& Live, int32 Seq) {
  FS08Snapshot Out = Live;
  Out.SequenceNumber = Seq;
  const TSharedRef<FJsonObject> Meta = MakeShared<FJsonObject>(*Live.Metadata->AsObject());
  Meta->RemoveField(TEXT("pendingManeuver"));
  Out.Metadata = MakeShared<FJsonValueObject>(Meta);
  return Out;
}

/** graphql-transport-ws 'next' of op s08-1 carrying seq/phase/turn and the
 *  metadata projection (a JSON STRING, as the server sends it). */
FString MsWsMetaFrame(const FS08Snapshot& Base, int32 Seq) {
  TSharedRef<FJsonObject> Event = MakeShared<FJsonObject>();
  Event->SetNumberField(TEXT("sequenceNumber"), Seq);
  Event->SetStringField(TEXT("phase"), Base.Phase);
  Event->SetNumberField(TEXT("turnCount"), Base.TurnCount);
  Event->SetStringField(TEXT("currentTurnPlayerId"), Base.CurrentTurnPlayerId);
  FString MetaText;
  FJsonSerializer::Serialize(Base.Metadata->AsObject().ToSharedRef(), TJsonWriterFactory<>::Create(&MetaText));
  Event->SetStringField(TEXT("metadata"), MetaText);
  TSharedRef<FJsonObject> Data = MakeShared<FJsonObject>();
  Data->SetObjectField(TEXT("gameStateUpdated"), Event);
  TSharedRef<FJsonObject> Payload = MakeShared<FJsonObject>();
  Payload->SetObjectField(TEXT("data"), Data);
  TSharedRef<FJsonObject> Frame = MakeShared<FJsonObject>();
  Frame->SetStringField(TEXT("type"), TEXT("next"));
  Frame->SetStringField(TEXT("id"), TEXT("s08-1"));
  Frame->SetObjectField(TEXT("payload"), Payload);
  FString Out;
  FJsonSerializer::Serialize(Frame, TJsonWriterFactory<>::Create(&Out));
  return Out;
}

/** Captures what the controller tells the UI. */
struct FMsFlowCapture {
  TArray<FString> Traces;
  TArray<FS08Rejection> Rejections;
  int32 FlowErrors = 0;
  void Bind(FS08FlowController& Flow) {
    Flow.OnTrace.AddLambda([this](const FString& Line) { Traces.Add(Line); });
    Flow.OnRejection.AddLambda([this](const FS08Rejection& R) { Rejections.Add(R); });
    Flow.OnFlowError.AddLambda([this](const FS08GraphQLError&) { ++FlowErrors; });
  }
  int32 Count(const FString& Needle) const {
    int32 N = 0;
    for (const FString& Line : Traces) N += Line.Contains(Needle) ? 1 : 0;
    return N;
  }
};

/** Controller on the live fixture (viewer LiveHost, its pendingManeuver
 *  maneuver:1:5 unless bWithoutManeuver) with a proven-live stream. */
bool MsLiveFlow(FS08FlowController& Flow, FS08Snapshot& OutApplied, bool bWithoutManeuver = false) {
  FS08Snapshot Live;
  if (!MsLoadLiveSnapshot(Live)) return false;
  OutApplied = bWithoutManeuver ? MsWithoutManeuver(Live, Live.SequenceNumber) : Live;
  Flow.AttachStreamHarnessForTest(TEXT("ms-net-game"));
  Flow.ApplySnapshot(OutApplied);
  Flow.InjectWsFrameForTest(MsBarrierFrame(Flow.GetAppliedSnapshot()));
  return Flow.IsStreamReady();
}

const TCHAR* const MsManeuverDoc = TEXT("maneuver(input");
const TCHAR* const MsBeginDoc = TEXT("beginManeuver(");
const TCHAR* const MsStateDoc = TEXT("gameState(");

} // namespace S09MoveSelTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelReasonsAndStringsTest, "Unmatched.S09.MoveSel.ReasonsAndStrings",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelReasonsAndStringsTest::RunTest(const FString&) {
  // ---- every code of 02 §1.1 -> key and class, for both command kinds ----
  for (const FMsRuleRow& Row : MsRuleTable) {
    TestTrue(FString::Printf(TEXT("%s is a known code"), Row.Code), FS08RuleCodes::KnownCodes().Contains(Row.Code));
    const FS08Rejection Maneuver =
        FS08RuleCodes::Classify({MsRuleError(Row.Code, TEXT("text"))}, ES08RejectOp::Maneuver, {});
    TestEqual(FString::Printf(TEXT("%s maneuver key"), Row.Code), Maneuver.WhyKey.ToString(), FString(Row.ManeuverKey));
    TestTrue(FString::Printf(TEXT("%s maneuver class"), Row.Code),
             (Maneuver.Class == ES08RejectClass::Fixable) == Row.bManeuverFixable);
    TestTrue(FString::Printf(TEXT("%s re-reads the snapshot"), Row.Code), Maneuver.bRefetch);
    const FS08Rejection Begin = FS08RuleCodes::Classify({MsRuleError(Row.Code, TEXT("text"))}, ES08RejectOp::Begin, {});
    TestEqual(FString::Printf(TEXT("%s begin key"), Row.Code), Begin.WhyKey.ToString(), FString(Row.ManeuverKey));
    const FS08Rejection Effect =
        FS08RuleCodes::Classify({MsRuleError(Row.Code, TEXT("text"))}, ES08RejectOp::PendingEffect, {});
    TestEqual(FString::Printf(TEXT("%s effect key"), Row.Code), Effect.WhyKey.ToString(), FString(Row.EffectKey));
    TestTrue(FString::Printf(TEXT("%s effect class"), Row.Code),
             (Effect.Class == ES08RejectClass::Fixable) == Row.bEffectFixable);
    TestTrue(FString::Printf(TEXT("%s: key in the EN table"), Row.Code), S08WhyText::Has(Maneuver.WhyKey) &&
                                                                          S08WhyText::Has(Effect.WhyKey));
  }
  TestEqual(TEXT("the client maps exactly the 02 §1.1 codes"), FS08RuleCodes::KnownCodes().Num(),
            static_cast<int32>(UE_ARRAY_COUNT(MsRuleTable)));
  TestEqual(TEXT("class letter И"), FString(FS08RuleCodes::Classify({MsRuleError(TEXT("POSITION_OCCUPIED"), TEXT(""))},
                                                                    ES08RejectOp::Maneuver, {}).ClassLetter()),
            FString(TEXT("И")));
  TestEqual(TEXT("class letter С"), FString(FS08RuleCodes::Classify({MsRuleError(TEXT("STATE_CHANGED"), TEXT(""))},
                                                                    ES08RejectOp::Maneuver, {}).ClassLetter()),
            FString(TEXT("С")));

  // ---- PATH_BLOCKED_BY_ENEMY: on the target -> why.cell.enemy, else .path ----
  {
    const FS08GraphQLError Blocked =
        MsRuleError(TEXT("PATH_BLOCKED_BY_ENEMY"), TEXT("Путь проходит через живого противника на клетке (3, 1)"));
    const FS08Rejection OnTarget = FS08RuleCodes::Classify({Blocked}, ES08RejectOp::Maneuver, {FIntPoint(3, 1)});
    TestEqual(TEXT("enemy on the target"), OnTarget.WhyKey.ToString(), FString(TEXT("why.cell.enemy")));
    TestTrue(TEXT("the cell read from the message"), OnTarget.Cell == FIntPoint(3, 1));
    const FS08Rejection OnPath = FS08RuleCodes::Classify({Blocked}, ES08RejectOp::Maneuver, {FIntPoint(4, 1)});
    TestEqual(TEXT("enemy on the way"), OnPath.WhyKey.ToString(), FString(TEXT("why.cell.enemy.path")));
    const FS08Rejection Short = FS08RuleCodes::Classify(
        {MsRuleError(TEXT("NOT_ENOUGH_MOVEMENT"), TEXT("Путь длиной 3 превышает очки движения бойца (2)"))},
        ES08RejectOp::Maneuver, {});
    TestEqual(TEXT("need from the message"), Short.WhyArgs.FindRef(TEXT("need")), FString(TEXT("3")));
    TestEqual(TEXT("have from the message"), Short.WhyArgs.FindRef(TEXT("have")), FString(TEXT("2")));
  }

  // ---- no code / unknown code -> why.command.rejected + refetch (MS-E-93) ----
  {
    FS08GraphQLError Guard;
    Guard.Code = TEXT("BAD_REQUEST");
    Guard.Message = TEXT("Invalid phase. Current: COMBAT");
    const FS08Rejection NoCode = FS08RuleCodes::Classify({Guard}, ES08RejectOp::Maneuver, {});
    TestEqual(TEXT("guard: why.command.rejected"), NoCode.WhyKey.ToString(), FString(TEXT("why.command.rejected")));
    TestTrue(TEXT("guard: class С + refetch"), NoCode.Class == ES08RejectClass::State && NoCode.bRefetch);
    const FS08Rejection Unknown =
        FS08RuleCodes::Classify({MsRuleError(TEXT("SOMETHING_NEW"), TEXT("x"))}, ES08RejectOp::Begin, {});
    TestEqual(TEXT("unknown code: why.command.rejected"), Unknown.WhyKey.ToString(), FString(TEXT("why.command.rejected")));
    FS08GraphQLError Throttled;
    Throttled.Code = TEXT("RATE_LIMIT");
    Throttled.HttpStatus = 429;
    const FS08Rejection Limit = FS08RuleCodes::Classify({Throttled}, ES08RejectOp::Maneuver, {});
    TestEqual(TEXT("429: why.syncing"), Limit.WhyKey.ToString(), FString(TEXT("why.syncing")));
    TestTrue(TEXT("429: class И, no refetch, no retry"), Limit.Class == ES08RejectClass::Fixable && !Limit.bRefetch);
  }

  // ---- the wire: extensions.ruleCode is read (MS-T-06) ----
  {
    TSharedPtr<FJsonObject> Root;
    FString Problem;
    TestTrue(TEXT("errors body parses"),
             FS08Contracts::TryParseJsonObject(
                 TEXT("{\"errors\":[{\"message\":\"Target position is occupied\",\"path\":[\"maneuver\"],")
                 TEXT("\"extensions\":{\"code\":\"BAD_USER_INPUT\",\"ruleCode\":\"POSITION_OCCUPIED\"}}],\"data\":null}"),
                 Root, Problem));
    TArray<FS08GraphQLError> Errors;
    TestTrue(TEXT("errors extracted"), Root.IsValid() && FS08Contracts::ExtractGraphQLErrors(Root.ToSharedRef(), Errors));
    TestTrue(TEXT("extensions.code and extensions.ruleCode"),
             Errors.Num() == 1 && Errors[0].Code == TEXT("BAD_USER_INPUT") && Errors[0].RuleCode == TEXT("POSITION_OCCUPIED"));
  }

  // ---- the EN table == why-reasons.json "en"; every key it carries exists ----
  {
    const FString Path = FPaths::ConvertRelativePathToFull(
        FPaths::Combine(FPaths::ProjectDir(), TEXT("../../docs/unreal/contracts/hud/why-reasons.json")));
    FString Text;
    TSharedPtr<FJsonObject> Doc;
    const TArray<TSharedPtr<FJsonValue>>* Reasons = nullptr;
    if (!FFileHelper::LoadFileToString(Text, *Path) ||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Doc) || !Doc.IsValid() ||
        !Doc->TryGetArrayField(TEXT("reasons"), Reasons)) {
      AddError(Path + TEXT(" not readable"));
    } else {
      TSet<FString> JsonKeys;
      for (const TSharedPtr<FJsonValue>& Value : *Reasons) {
        const TSharedPtr<FJsonObject> Reason = Value->AsObject();
        const FString Key = Reason->GetStringField(TEXT("key"));
        JsonKeys.Add(Key);
        TestEqual(FString::Printf(TEXT("EN text of %s == why-reasons.json"), *Key), S08WhyText::Template(FName(*Key)),
                  Reason->GetStringField(TEXT("en")));
      }
      for (const FName& Key : S08WhyText::Keys()) {
        const FString K = Key.ToString();
        if (K.StartsWith(TEXT("why."))) {
          TestTrue(FString::Printf(TEXT("%s is in why-reasons.json"), *K), JsonKeys.Contains(K));
        }
      }
    }
  }

  // ---- the opponent's choice blocks the begin with why.wait.opponent.choice (MS-E-47) ----
  {
    FS08Snapshot Waiting = MsPendingMoveSnapshot(1);
    const TSharedRef<FJsonObject> Meta = MakeShared<FJsonObject>(*Waiting.Metadata->AsObject());
    const TArray<TSharedPtr<FJsonValue>> Heads = Meta->GetArrayField(TEXT("pendingEffects"));
    const TSharedRef<FJsonObject> Head = MakeShared<FJsonObject>(*Heads[0]->AsObject());
    Head->SetStringField(TEXT("playerId"), Opp);
    TArray<TSharedPtr<FJsonValue>> OpponentHead;
    OpponentHead.Add(MakeShared<FJsonValueObject>(Head));
    Meta->SetArrayField(TEXT("pendingEffects"), OpponentHead);
    Waiting.Metadata = MakeShared<FJsonValueObject>(Meta);
    FS09CommandUi Ui;
    Ui.ViewerId = Me;
    Ui.OnSnapshot(Waiting, MsGrid(4, 4), {MsFighter(TEXT("a"), Me, 0, 0)});
    FString Reason;
    FS09Reason Key;
    TestFalse(TEXT("begin refused"), Ui.CanBeginManeuver(Waiting, Reason, Key));
    TestEqual(TEXT("why.wait.opponent.choice"), MsKey(Key), FString(TEXT("why.wait.opponent.choice")));
    TestEqual(TEXT("its text"), Key.Text(), FString(TEXT("Waiting for the opponent's choice")));
    FS08Snapshot NoActions = MsSnapshot({}, FString());
    const TSharedRef<FJsonObject> Spent = MakeShared<FJsonObject>(*NoActions.Metadata->AsObject());
    Spent->SetNumberField(TEXT("actionsRemaining"), 0);
    NoActions.Metadata = MakeShared<FJsonValueObject>(Spent);
    FS09CommandUi Idle;
    Idle.ViewerId = Me;
    Idle.OnSnapshot(NoActions, MsGrid(4, 4), {MsFighter(TEXT("a"), Me, 0, 0)});
    TestFalse(TEXT("no actions: begin refused"), Idle.CanBeginManeuver(NoActions, Reason, Key));
    TestEqual(TEXT("why.no.actions"), MsKey(Key), FString(TEXT("why.no.actions")));
    FS09CommandUi Draft = MsOpen(MsSnapshot({}), MsGrid(4, 4), {MsFighter(TEXT("a"), Me, 0, 0)});
    TestFalse(TEXT("draft open: begin refused"), Draft.CanBeginManeuver(MsSnapshot({}), Reason, Key));
    TestEqual(TEXT("why.draft.open (the M toast: ms.begin.already)"), MsKey(Key), FString(TEXT("why.draft.open")));
    TestEqual(TEXT("ms.begin.already text"), FS09Reason::Make(TEXT("ms.begin.already")).Text(),
              FString(TEXT("Maneuver already begun — Enter confirms")));
  }

  // ---- graph board: toasts name spaces by CellLabel, never (x,y) (B-04) ----
  {
    const FS08BoardModel Line = MsLine(6);
    TestTrue(TEXT("graph board"), Line.bHasTopology);
    const FS08Snapshot Snap = MsSnapshot({{TEXT("c1"), true, 1}});
    const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 0, 0, 2.0), MsFighter(TEXT("e"), Opp, 4, 0),
                                               MsFighter(TEXT("b"), Me, 2, 0, 2.0)};
    FS09CommandUi Ui = MsOpen(Snap, Line, Fighters);
    FString Reason;
    TArray<FString> Toasts;
    TestFalse(TEXT("ally space refused"), Ui.SetDestination(TEXT("a"), 2, 0, Snap, Line, Fighters, Reason));
    Toasts.Add(Ui.LastReason.Text());
    TestEqual(TEXT("ally: why.cell.ally"), MsKey(Ui.LastReason), FString(TEXT("why.cell.ally")));
    TestFalse(TEXT("enemy space refused"), Ui.SetDestination(TEXT("b"), 4, 0, Snap, Line, Fighters, Reason));
    Toasts.Add(Ui.LastReason.Text());
    TestFalse(TEXT("too far refused"), Ui.SetDestination(TEXT("a"), 5, 0, Snap, Line, Fighters, Reason));
    Toasts.Add(Ui.LastReason.Text());
    FS09Reason Server = FS09Reason::Make(TEXT("why.cell.enemy"));
    Server.Arg(TEXT("cell"), Line.CellLabel(3, 0));
    Toasts.Add(Server.Text());
    TestEqual(TEXT("server reason with the space"), Toasts.Last(), FString(TEXT("S4: An enemy is here")));
    for (const FString& Toast : Toasts) {
      TestFalse(FString::Printf(TEXT("no grid coordinates: \"%s\""), *Toast), Toast.Contains(TEXT("(")));
      TestTrue(FString::Printf(TEXT("a space label: \"%s\""), *Toast), Toast.StartsWith(TEXT("S")));
    }
  }

  // ---- a server rejection's toast has every argument (no "?" placeholder) ----
  {
    const FS08BoardModel Grid = MsGrid(5, 3);
    const FS08Snapshot Snap = MsSnapshot({{TEXT("c1"), true, 1}});
    FS08BoardFighter Stuck = MsFighter(TEXT("s"), Me, 4, 2, 2.0);
    Stuck.Effects.Add(TEXT("immobilized"));
    const TArray<FS08BoardFighter> Team = {MsFighter(TEXT("a"), Me, 0, 1, 2.0), Stuck, MsFighter(TEXT("e"), Opp, 4, 0)};
    FS09CommandUi Ui = MsOpen(Snap, Grid, Team);
    FString Reason;
    TestTrue(TEXT("a drafted to (2,1)"), Ui.SetDestination(TEXT("a"), 2, 1, Snap, Grid, Team, Reason));
    Ui.Moves.AddDefaulted_GetRef().FighterId = TEXT("s"); // what a stale client could have sent
    Ui.Moves.Last().DestX = 3;
    Ui.Moves.Last().DestY = 2;
    Ui.PendingFighterId = TEXT("a");
    Ui.PendingChoice.bHasValue = true;
    Ui.PendingChoice.Value = 1;
    auto MessageOf = [](const FString& Code, bool bEffect) -> FString {
      if (Code == TEXT("NOT_ENOUGH_MOVEMENT")) {
        return bEffect ? FString(TEXT("До клетки (2, 0) не добраться за 1 шаг(ов)"))
                       : FString(TEXT("Путь длиной 3 превышает очки движения бойца (2)"));
      }
      if (Code == TEXT("PATH_BLOCKED_BY_ENEMY")) return TEXT("Путь проходит через живого противника на клетке (2, 1)");
      if (Code == TEXT("PLACE_OUTSIDE_ZONE")) return TEXT("Клетка должна быть в зоне «Medusa»");
      if (Code == TEXT("FIGHTER_IMMOBILIZED")) return TEXT("Боец обездвижен до конца хода (эффект карты)");
      return TEXT("text");
    };
    for (const FMsRuleRow& Row : MsRuleTable) {
      for (const bool bEffect : {false, true}) {
        const FS08Rejection R = FS08RuleCodes::Classify(
            {MsRuleError(Row.Code, MessageOf(Row.Code, bEffect))},
            bEffect ? ES08RejectOp::PendingEffect : ES08RejectOp::Maneuver,
            bEffect ? TArray<FIntPoint>{FIntPoint(1, 1)} : TArray<FIntPoint>{FIntPoint(2, 1), FIntPoint(3, 2)});
        const FString Text = Ui.RejectionReason(R, Grid, Team).Text();
        TestFalse(FString::Printf(TEXT("%s (%s): \"%s\" has no placeholder"), Row.Code, bEffect ? TEXT("effect") : TEXT("maneuver"), *Text),
                  Text.IsEmpty() || Text.Contains(TEXT("?")) || Text.Contains(TEXT("{")));
      }
    }
    const FS08Rejection Zone = FS08RuleCodes::Classify(
        {MsRuleError(TEXT("PLACE_OUTSIDE_ZONE"), TEXT("Клетка должна быть в зоне «Medusa»"))}, ES08RejectOp::PendingEffect,
        {FIntPoint(1, 1)});
    TestEqual(TEXT("the zone fighter from the message"), Ui.RejectionReason(Zone, Grid, Team).Text(),
              FString(TEXT("(1,1): Choose a space in Medusa's zone")));
    const FS08Rejection Stiff = FS08RuleCodes::Classify(
        {MsRuleError(TEXT("FIGHTER_IMMOBILIZED"), TEXT("Боец обездвижен до конца хода (эффект карты)"))},
        ES08RejectOp::Maneuver, {FIntPoint(2, 1), FIntPoint(3, 2)});
    TestEqual(TEXT("the immobilized fighter of the draft"), Ui.RejectionReason(Stiff, Grid, Team).Text(),
              FString(TEXT("s cannot move")));
    const FS08Rejection Short = FS08RuleCodes::Classify(
        {MsRuleError(TEXT("NOT_ENOUGH_MOVEMENT"), TEXT("До клетки (2, 0) не добраться за 1 шаг(ов)"))},
        ES08RejectOp::PendingEffect, {FIntPoint(2, 0)});
    TestEqual(TEXT("effect: need from the board, have from the message"), Ui.RejectionReason(Short, Grid, Team).Text(),
              FString(TEXT("(2,0): Not enough movement: need 3, have 1")));
  }

  // ---- the controller: a rejection is classified, traced, re-read; never resent ----
  {
    FS08FlowController Flow(TEXT("http://127.0.0.1:9/graphql"), TEXT("ws://127.0.0.1:9/graphql"), LiveHost);
    FMsFlowCapture Cap;
    Cap.Bind(Flow);
    FS08Snapshot Live;
    if (!MsLiveFlow(Flow, Live)) {
      AddError(TEXT("fixture 04 / live stream not ready"));
      return true;
    }
    // Class И: the target space is taken (the server's sequential check).
    Flow.QueueHttpResultForTest(false, {MsRuleError(TEXT("POSITION_OCCUPIED"), TEXT("Target position is occupied"))});
    Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true); // the refetch: never delivered, no real POST
    TArray<FS08ManeuverMove> Moves;
    FS08ManeuverMove& Step = Moves.AddDefaulted_GetRef();
    Step.FighterId = TEXT("f-0-sk0");
    Step.Path = {FIntPoint(0, 2)};
    TestTrue(TEXT("maneuver dispatched"), Flow.SubmitManeuver(TEXT("maneuver:1:5"), Moves));
    TestEqual(TEXT("one rejection broadcast"), Cap.Rejections.Num(), 1);
    if (Cap.Rejections.Num() == 1) {
      TestEqual(TEXT("why.cell.ally"), Cap.Rejections[0].WhyKey.ToString(), FString(TEXT("why.cell.ally")));
      TestTrue(TEXT("class И"), Cap.Rejections[0].Class == ES08RejectClass::Fixable);
    }
    TestEqual(TEXT("MS-REJECT traced"), Cap.Count(TEXT("MS-REJECT code=POSITION_OCCUPIED why=why.cell.ally class=И")), 1);
    TestEqual(TEXT("the snapshot is re-read"), Flow.CountHttpSendsForTest(MsStateDoc), 1);
    TestEqual(TEXT("the maneuver is not resent"), Flow.CountHttpSendsForTest(MsManeuverDoc), 1);
    TestFalse(TEXT("an answered rejection is no recovery lock"), Flow.IsMutationRecoveryActiveForTest());

    // Class С with no code at all (a guard): why.command.rejected, re-read.
    FS08FlowController Guarded(TEXT("http://127.0.0.1:9/graphql"), TEXT("ws://127.0.0.1:9/graphql"), LiveHost);
    FMsFlowCapture GuardCap;
    GuardCap.Bind(Guarded);
    if (MsLiveFlow(Guarded, Live)) {
      FS08GraphQLError Guard;
      Guard.Code = TEXT("BAD_REQUEST");
      Guard.Message = TEXT("Not your turn. Current player: x");
      Guarded.QueueHttpResultForTest(false, {Guard});
      Guarded.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true);
      TestTrue(TEXT("guarded maneuver dispatched"), Guarded.SubmitManeuver(TEXT("maneuver:1:5"), Moves));
      TestTrue(TEXT("why.command.rejected, class С"),
               GuardCap.Rejections.Num() == 1 && GuardCap.Rejections[0].WhyKey == FName(TEXT("why.command.rejected")) &&
                   GuardCap.Rejections[0].Class == ES08RejectClass::State);
      TestEqual(TEXT("guard: re-read"), Guarded.CountHttpSendsForTest(MsStateDoc), 1);
    } else {
      AddError(TEXT("second live stream not ready"));
    }
  }

  // ---- the draft after a rejection: И keeps it, С rebuilds or closes it ----
  {
    const FS08BoardModel Board = MsGrid(5, 5);
    const TArray<FMsCard> Hand = {{TEXT("c2"), true, 2}};
    const FS08Snapshot Snap = MsSnapshot(Hand, ManeuverA, 5);
    const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 0, 0), MsFighter(TEXT("b"), Me, 4, 4)};
    FString Reason;
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    TestTrue(TEXT("drafted"), Ui.SetDestination(TEXT("a"), 2, 0, Snap, Board, Fighters, Reason));
    // The refetch of an И rejection returns the same state: the draft is kept and re-checked.
    Ui.OnSnapshot(Snap, Board, Fighters);
    TestEqual(TEXT("И: the move is kept"), Ui.Moves.Num(), 1);
    // С, the same pendingManeuver at a new seq: rebuilt (re-evaluated), not deleted.
    TArray<FS08BoardFighter> Moved = Fighters;
    Moved.Add(MsFighter(TEXT("e"), Opp, 2, 0));
    Ui.OnSnapshot(MsSnapshot(Hand, ManeuverA, 6), Board, Moved);
    TestEqual(TEXT("С, same maneuver: rebuilt, kept"), Ui.Moves.Num(), 1);
    TestEqual(TEXT("С, same maneuver: now a Conflict"), MsStatus(MsMove(Ui, TEXT("a"))), FString(TEXT("conflict")));
    // С, the maneuver is gone: closed.
    Ui.OnSnapshot(MsSnapshot(Hand, FString(), 7), Board, Fighters);
    TestTrue(TEXT("С, maneuver closed: draft closed"), Ui.Mode == ES09CommandMode::None && Ui.Moves.Num() == 0);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelInFlightGateTest, "Unmatched.S09.MoveSel.InFlightGate",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelInFlightGateTest::RunTest(const FString&) {
  TArray<FS08ManeuverMove> Moves;
  FS08ManeuverMove& Step = Moves.AddDefaulted_GetRef();
  Step.FighterId = TEXT("f-0-sk0");
  Step.Path = {FIntPoint(0, 2)};

  // ---- 10 confirms -> 1 mutation; the gate closes in the same call ----
  // ---- 3 s -> why.syncing; a snapshot that closes the maneuver releases the
  //      gate before the HTTP answer; the late answer is only traced ----
  {
    FS08FlowController Flow(TEXT("http://127.0.0.1:9/graphql"), TEXT("ws://127.0.0.1:9/graphql"), LiveHost);
    FMsFlowCapture Cap;
    Cap.Bind(Flow);
    FS08Snapshot Live;
    if (!MsLiveFlow(Flow, Live)) {
      AddError(TEXT("fixture 04 / live stream not ready"));
      return true;
    }
    Flow.QueueHttpResultForTest(false, {MsRuleError(TEXT("MANEUVER_NOT_OPEN"), TEXT("late"))}, /*bDeferDelivery=*/true);
    TestTrue(TEXT("first confirm dispatched"), Flow.SubmitManeuver(TEXT("maneuver:1:5"), Moves));
    TestTrue(TEXT("in flight in the same call (\"Sent...\" within a frame)"), Flow.IsManeuverInFlight());
    for (int32 Press = 1; Press < 10; ++Press) Flow.SubmitManeuver(TEXT("maneuver:1:5"), Moves);
    TestEqual(TEXT("10 presses -> 1 mutation"), Flow.CountHttpSendsForTest(MsManeuverDoc), 1);
    Flow.TickConnectivity(2.9f);
    TestFalse(TEXT("not slow before 3 s"), Flow.IsCommandSlow());
    Flow.TickConnectivity(0.2f);
    TestTrue(TEXT("slow after 3 s (why.syncing)"), Flow.IsCommandSlow());
    TestEqual(TEXT("MS-NET slow traced"), Cap.Count(TEXT("MS-NET slow op=maneuver")), 1);
    // The WS snapshot of the applied maneuver (seq + 1, no pendingManeuver).
    Flow.InjectWsFrameForTest(MsWsMetaFrame(MsWithoutManeuver(Live, Live.SequenceNumber + 1), Live.SequenceNumber + 1));
    TestFalse(TEXT("the snapshot released the gate"), Flow.IsManeuverInFlight());
    TestEqual(TEXT("released by snapshot (traced)"), Cap.Count(TEXT("MS-NET gate released by snapshot op=maneuver")), 1);
    TestFalse(TEXT("no longer slow"), Flow.IsCommandSlow());
    const int32 ErrorsBefore = Cap.FlowErrors;
    Flow.DeliverQueuedHttpForTest(); // the late HTTP answer
    TestEqual(TEXT("late reply traced"), Cap.Count(TEXT("MS-NET late-reply op=maneuver ok=0 settled=snapshot")), 1);
    TestEqual(TEXT("late reply: no error shown"), Cap.FlowErrors, ErrorsBefore);
    TestEqual(TEXT("late reply: no rejection"), Cap.Rejections.Num(), 0);
    TestEqual(TEXT("late reply: no refetch"), Flow.CountHttpSendsForTest(MsStateDoc), 0);
    Flow.TickConnectivity(20.0f);
    TestFalse(TEXT("a settled command has no deadline"), Flow.IsMutationRecoveryActiveForTest());
  }

  // ---- 10 s -> deadline: cancelled, outcome unknown, recovery lock, no resend ----
  {
    FS08FlowController Flow(TEXT("http://127.0.0.1:9/graphql"), TEXT("ws://127.0.0.1:9/graphql"), LiveHost);
    FMsFlowCapture Cap;
    Cap.Bind(Flow);
    FS08Snapshot Live;
    if (!MsLiveFlow(Flow, Live)) {
      AddError(TEXT("live stream not ready (deadline)"));
      return true;
    }
    Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true); // the maneuver: no answer
    Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true); // the recovery read: never delivered
    TestTrue(TEXT("dispatched"), Flow.SubmitManeuver(TEXT("maneuver:1:5"), Moves));
    Flow.TickConnectivity(9.9f);
    TestTrue(TEXT("still waiting at 9.9 s"), Flow.IsManeuverInFlight() && !Flow.IsMutationRecoveryActiveForTest());
    Flow.TickConnectivity(0.2f);
    TestEqual(TEXT("MS-NET deadline traced"), Cap.Count(TEXT("MS-NET deadline op=maneuver")), 1);
    TestTrue(TEXT("outcome unknown: recovery lock (MS-S-10)"), Flow.IsMutationRecoveryActiveForTest());
    TestFalse(TEXT("the command gate is not the in-flight flag any more"), Flow.IsManeuverInFlight());
    TestEqual(TEXT("the recovery reads the state"), Flow.CountHttpSendsForTest(MsStateDoc), 1);
    TestEqual(TEXT("no resend"), Flow.CountHttpSendsForTest(MsManeuverDoc), 1);
    FString Reason;
    TestFalse(TEXT("commands locked while recovering"), Flow.SubmitManeuver(TEXT("maneuver:1:5"), Moves));
    TestEqual(TEXT("why.syncing while locked"), Flow.GameplayGateKey().ToString(), FString(TEXT("why.syncing")));
    Flow.DeliverQueuedHttpForTest(); // the maneuver answer after its deadline
    TestEqual(TEXT("late reply after the deadline"), Cap.Count(TEXT("MS-NET late-reply op=maneuver ok=1 settled=deadline")), 1);
    TestEqual(TEXT("still exactly one maneuver"), Flow.CountHttpSendsForTest(MsManeuverDoc), 1);
  }

  // ---- begin: a snapshot that opens my pendingManeuver releases the gate;
  //      an answered STATE_CHANGED is re-read, never re-sent ----
  {
    FS08FlowController Flow(TEXT("http://127.0.0.1:9/graphql"), TEXT("ws://127.0.0.1:9/graphql"), LiveHost);
    FMsFlowCapture Cap;
    Cap.Bind(Flow);
    FS08Snapshot Before;
    if (!MsLiveFlow(Flow, Before, /*bWithoutManeuver=*/true)) {
      AddError(TEXT("live stream not ready (begin)"));
      return true;
    }
    FS08Snapshot Live;
    MsLoadLiveSnapshot(Live);
    Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true);
    TestTrue(TEXT("begin dispatched"), Flow.BeginManeuver());
    TestTrue(TEXT("begin in flight"), Flow.IsManeuverInFlight());
    FS08Snapshot Opened = Live;
    Opened.SequenceNumber = Before.SequenceNumber + 1;
    Flow.InjectWsFrameForTest(MsWsMetaFrame(Opened, Opened.SequenceNumber));
    TestFalse(TEXT("my pendingManeuver opened by WS: gate released"), Flow.IsManeuverInFlight());
    TestEqual(TEXT("begin released by snapshot"), Cap.Count(TEXT("MS-NET gate released by snapshot op=begin")), 1);
    Flow.DeliverQueuedHttpForTest();
    TestEqual(TEXT("late begin answer traced only"), Cap.Count(TEXT("MS-NET late-reply op=begin")), 1);

    FS08FlowController Stale(TEXT("http://127.0.0.1:9/graphql"), TEXT("ws://127.0.0.1:9/graphql"), LiveHost);
    FMsFlowCapture StaleCap;
    StaleCap.Bind(Stale);
    if (MsLiveFlow(Stale, Before, /*bWithoutManeuver=*/true)) {
      Stale.QueueHttpResultForTest(false, {MsRuleError(TEXT("STATE_CHANGED"), TEXT("State changed; reload before beginning maneuver"))});
      Stale.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true);
      TestTrue(TEXT("stale begin dispatched"), Stale.BeginManeuver());
      TestTrue(TEXT("why.state.changed"), StaleCap.Rejections.Num() == 1 &&
                                              StaleCap.Rejections[0].WhyKey == FName(TEXT("why.state.changed")));
      TestEqual(TEXT("STATE_CHANGED: re-read"), Stale.CountHttpSendsForTest(MsStateDoc), 1);
      TestEqual(TEXT("STATE_CHANGED: begin not repeated (MS-E-50)"), Stale.CountHttpSendsForTest(MsBeginDoc), 1);
    } else {
      AddError(TEXT("live stream not ready (stale begin)"));
    }
  }

  // ---- a late SUCCESS answer is merged (decks ride only in HTTP bodies) ----
  {
    FS08FlowController Flow(TEXT("http://127.0.0.1:9/graphql"), TEXT("ws://127.0.0.1:9/graphql"), LiveHost);
    FMsFlowCapture Cap;
    Cap.Bind(Flow);
    FS08Snapshot Live;
    if (!MsLiveFlow(Flow, Live)) {
      AddError(TEXT("live stream not ready (late success)"));
      return true;
    }
    const int32 Next = Live.SequenceNumber + 1;
    const FString Inner = FString::Printf(
        TEXT("{\\\"players\\\":[{\\\"userId\\\":\\\"%s\\\"},{\\\"userId\\\":\\\"p-x\\\"}],")
        TEXT("\\\"decks\\\":{\\\"%s\\\":{\\\"count\\\":3}}}"),
        LiveHost, LiveHost);
    const FString Body = FString::Printf(
        TEXT("{\"data\":{\"maneuver\":{\"state\":\"%s\",\"sequenceNumber\":%d,\"phase\":\"%s\",")
        TEXT("\"turnCount\":%d,\"currentTurnPlayerId\":\"%s\"}}}"),
        *Inner, Next, *Live.Phase, Live.TurnCount, *Live.CurrentTurnPlayerId);
    Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, Body);
    TestTrue(TEXT("dispatched"), Flow.SubmitManeuver(TEXT("maneuver:1:5"), Moves));
    Flow.InjectWsFrameForTest(MsWsMetaFrame(MsWithoutManeuver(Live, Next), Next));
    TestFalse(TEXT("released by the WS snapshot"), Flow.IsManeuverInFlight());
    const int32 DecksBefore = Flow.GetDecksSeq();
    Flow.DeliverQueuedHttpForTest();
    TestEqual(TEXT("the late success body is merged"), Cap.Count(FString::Printf(TEXT("MS-NET late-reply merged seq=%d (merge)"), Next)), 1);
    TestTrue(TEXT("its decks are fresh"), Flow.GetDecksSeq() == Next && DecksBefore != Next);
    TestFalse(TEXT("no gate change"), Flow.IsManeuverInFlight());
    TestEqual(TEXT("no rejection"), Cap.Rejections.Num(), 0);
  }

  // ---- the match is left with the command in flight: its deadline locks nothing ----
  {
    FS08FlowController Flow(TEXT("http://127.0.0.1:9/graphql"), TEXT("ws://127.0.0.1:9/graphql"), LiveHost);
    FS08Snapshot Live;
    if (!MsLiveFlow(Flow, Live)) {
      AddError(TEXT("live stream not ready (left match)"));
      return true;
    }
    Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true);
    TestTrue(TEXT("dispatched"), Flow.SubmitManeuver(TEXT("maneuver:1:5"), Moves));
    Flow.SetRoomForTest(TEXT("ms-net-game"), ES08Stage::Room); // the stage left Started
    Flow.TickConnectivity(11.0f);
    TestFalse(TEXT("no recovery lock after the match is gone"), Flow.IsMutationRecoveryActiveForTest());
    TestFalse(TEXT("no slow banner either"), Flow.IsCommandSlow());
  }

  // ---- 429: why.syncing, no automatic retry, controls stay usable ----
  {
    FS08FlowController Flow(TEXT("http://127.0.0.1:9/graphql"), TEXT("ws://127.0.0.1:9/graphql"), LiveHost);
    FMsFlowCapture Cap;
    Cap.Bind(Flow);
    FS08Snapshot Live;
    if (!MsLiveFlow(Flow, Live)) {
      AddError(TEXT("live stream not ready (429)"));
      return true;
    }
    FS08GraphQLError Throttled;
    Throttled.Code = TEXT("RATE_LIMIT");
    Throttled.Message = TEXT("HTTP 429 from server");
    Throttled.HttpStatus = 429;
    Flow.QueueHttpResultForTest(false, {Throttled});
    TestTrue(TEXT("dispatched"), Flow.SubmitManeuver(TEXT("maneuver:1:5"), Moves));
    TestTrue(TEXT("why.syncing"), Cap.Rejections.Num() == 1 && Cap.Rejections[0].WhyKey == FName(TEXT("why.syncing")));
    TestEqual(TEXT("no automatic retry"), Flow.CountHttpSendsForTest(MsManeuverDoc), 1);
    TestEqual(TEXT("no refetch"), Flow.CountHttpSendsForTest(MsStateDoc), 0);
    FString Reason;
    TestTrue(TEXT("controls stay usable"), Flow.CanIssueGameplayCommand(Reason));
  }
  return true;
}

// ---- MS-T-07: input semantics, pre-draft, exhaustion --------------------------

namespace S09MoveSelTest {

/** A full click: press and release over the same space / fighter. */
FS09InputResult MsClick(FS09MoveInput& In, FS09CommandUi& Ui, const FS08Snapshot& Snap, const FS08BoardModel& Board,
                        const TArray<FS08BoardFighter>& Fighters, const FIntPoint& Cell,
                        const FString& FighterId = FString()) {
  In.OnPointerPressed(Cell, FighterId);
  return In.OnPointerReleased(Cell, FighterId, Ui, Snap, Board, Fighters);
}

/** The viewer's turn before the begin: no pendingManeuver, actions left. */
FS08Snapshot MsTurnSnapshot(const TArray<FMsCard>& Hand, int32 Seq = 4) {
  return MsSnapshot(Hand, FString(), Seq);
}

int32 MsUndoDepth(const FS09CommandUi& Ui) { return Ui.UndoStack.Num(); }

/** One draft trace line carries every needle. */
bool MsTracedLine(const FS09CommandUi& Ui, std::initializer_list<const TCHAR*> Needles) {
  for (const FString& Line : Ui.DraftTrace) {
    bool bAll = true;
    for (const TCHAR* Needle : Needles) bAll &= Line.Contains(Needle);
    if (bAll) return true;
  }
  return false;
}

} // namespace S09MoveSelTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelInputSemanticsTest, "Unmatched.S09.MoveSel.InputSemantics",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelInputSemanticsTest::RunTest(const FString&) {
  const FS08BoardModel Board = MsGrid(6, 3);
  const TArray<FMsCard> Hand = {{TEXT("c2"), true, 2}, {TEXT("c1"), true, 1}};
  const FS08Snapshot Snap = MsSnapshot(Hand, ManeuverA, 5);
  const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 0, 1, 2.0), MsFighter(TEXT("b"), Me, 5, 1, 2.0),
                                             MsFighter(TEXT("e"), Opp, 5, 0)};
  FString Reason;

  // ---- Esc by steps; D / I close first and leave the draft alone (MS-E-98) ----
  {
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    FS09MoveInput In;
    TestTrue(TEXT("select a"), Ui.SelectFighter(TEXT("a"), Snap, Board, Fighters));
    TestTrue(TEXT("a drafted"), Ui.SetDestination(TEXT("a"), 2, 1, Snap, Board, Fighters, Reason));
    FS09InputView WithD;
    WithD.bDiscardBrowserOpen = true;
    FS09InputResult R = In.OnKey(ES09MoveKey::Escape, Ui, Snap, Board, Fighters, WithD);
    TestTrue(TEXT("Esc closes D first"), R.bHandled && R.bCloseDiscardBrowser && !R.bCloseInspector);
    TestTrue(TEXT("... the draft untouched"), Ui.Moves.Num() == 1 && Ui.SelectedFighterId == TEXT("a"));
    FS09InputView WithI;
    WithI.bInspectorOpen = true;
    R = In.OnKey(ES09MoveKey::Escape, Ui, Snap, Board, Fighters, WithI);
    TestTrue(TEXT("Esc closes I first"), R.bCloseInspector && Ui.Moves.Num() == 1 && Ui.SelectedFighterId == TEXT("a"));
    TestTrue(TEXT("B opens the boost panel"), In.OnKey(ES09MoveKey::B, Ui, Snap, Board, Fighters, {}).bHandled &&
                                                  In.bBoostPanelOpen);
    In.OnKey(ES09MoveKey::Escape, Ui, Snap, Board, Fighters, {});
    TestTrue(TEXT("Esc closes MS-S-08"), !In.bBoostPanelOpen && Ui.SelectedFighterId == TEXT("a"));
    In.OnKey(ES09MoveKey::Escape, Ui, Snap, Board, Fighters, {});
    TestTrue(TEXT("Esc: MS-S-07 -> MS-S-06 (selection dropped, move kept)"),
             Ui.SelectedFighterId.IsEmpty() && Ui.Moves.Num() == 1);
    In.OnKey(ES09MoveKey::Escape, Ui, Snap, Board, Fighters, {});
    TestEqual(TEXT("Esc in MS-S-06 with moves: reset"), Ui.Moves.Num(), 0);
    In.OnKey(ES09MoveKey::Backspace, Ui, Snap, Board, Fighters, {});
    TestEqual(TEXT("the reset is undone by Backspace"), Ui.Moves.Num(), 1);
    In.OnKey(ES09MoveKey::Escape, Ui, Snap, Board, Fighters, {});
    R = In.OnKey(ES09MoveKey::Escape, Ui, Snap, Board, Fighters, {});
    TestEqual(TEXT("Esc in an empty MS-S-06: ms.confirm.zero"), MsKey(R.Toast), FString(TEXT("ms.confirm.zero")));
    // RMB: a step back that never resets the draft.
    TestTrue(TEXT("re-select a"), Ui.SelectFighter(TEXT("a"), Snap, Board, Fighters));
    TestTrue(TEXT("a drafted again"), Ui.SetDestination(TEXT("a"), 2, 1, Snap, Board, Fighters, Reason));
    In.OnRightClick(Ui, Snap, Board, Fighters);
    TestTrue(TEXT("RMB drops the selection"), Ui.SelectedFighterId.IsEmpty() && Ui.Moves.Num() == 1);
    In.OnRightClick(Ui, Snap, Board, Fighters);
    TestEqual(TEXT("RMB never resets the draft"), Ui.Moves.Num(), 1);
  }

  // ---- Esc outside the draft: MS-S-03 -> MS-S-02 -> MS-S-01 -> pause.unavailable ----
  {
    const FS08Snapshot Turn = MsTurnSnapshot(Hand);
    FS09CommandUi Ui = MsOpen(Turn, Board, Fighters);
    FS09MoveInput In;
    TestTrue(TEXT("no draft before the begin"), Ui.Mode == ES09CommandMode::None);
    MsClick(In, Ui, Turn, Board, Fighters, FIntPoint(0, 1), TEXT("a"));
    TestEqual(TEXT("MS-S-02: a inspected"), Ui.SelectedFighterId, FString(TEXT("a")));
    MsClick(In, Ui, Turn, Board, Fighters, FIntPoint(2, 1));
    TestTrue(TEXT("MS-S-03: a pre-draft"), Ui.PreDraft.bSet);
    In.OnKey(ES09MoveKey::Escape, Ui, Turn, Board, Fighters, {});
    TestTrue(TEXT("Esc: MS-S-03 -> MS-S-02"), !Ui.PreDraft.bSet && Ui.SelectedFighterId == TEXT("a"));
    In.OnKey(ES09MoveKey::Escape, Ui, Turn, Board, Fighters, {});
    TestTrue(TEXT("Esc: MS-S-02 -> MS-S-01"), Ui.SelectedFighterId.IsEmpty());
    const FS09InputResult R = In.OnKey(ES09MoveKey::Escape, Ui, Turn, Board, Fighters, {});
    TestTrue(TEXT("Esc without a selection: pause unavailable (MS-E-99)"), R.bHandled && R.bPauseUnavailable);
  }

  // ---- undo stack: 32 records, the 33rd evicts the oldest; barrier; maneuverId ----
  {
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    FS09MoveInput In;
    for (int32 Op = 0; Op < 33; ++Op) Ui.ToggleBoostCard(TEXT("c2"), Snap, Board, Fighters, Reason);
    TestEqual(TEXT("33 ops -> 32 records (MS-E-94)"), MsUndoDepth(Ui), FS09CommandUi::MaxUndo);
    TestEqual(TEXT("after 33 toggles c2 is selected"), Ui.BoostCardId, FString(TEXT("c2")));
    for (int32 Back = 0; Back < 32; ++Back) In.OnKey(ES09MoveKey::CtrlZ, Ui, Snap, Board, Fighters, {});
    // (each undo popped one record; the failed operations below push none)
    TestEqual(TEXT("32 undos reach the state after op 1 (c2), not the start"), Ui.BoostCardId, FString(TEXT("c2")));
    TestFalse(TEXT("an empty stack undoes nothing"), Ui.Undo(Board, Fighters));
    TestFalse(TEXT("a refused target"), Ui.SetDestination(TEXT("a"), 5, 0, Snap, Board, Fighters, Reason));
    TestFalse(TEXT("a refused boost"), Ui.ToggleBoostCard(TEXT("nope"), Snap, Board, Fighters, Reason));
    TestFalse(TEXT("an order no-op"), Ui.MoveOrder(TEXT("a"), -1, Snap, Board, Fighters));
    TestEqual(TEXT("failed operations push no undo record"), MsUndoDepth(Ui), 0);
    TestTrue(TEXT("a drafted"), Ui.SetDestination(TEXT("a"), 2, 1, Snap, Board, Fighters, Reason));
    TestTrue(TEXT("b drafted"), Ui.SetDestination(TEXT("b"), 3, 1, Snap, Board, Fighters, Reason));
    TestTrue(TEXT("order changed"), Ui.MoveOrder(TEXT("b"), -1, Snap, Board, Fighters));
    In.OnKey(ES09MoveKey::Backspace, Ui, Snap, Board, Fighters, {});
    TestTrue(TEXT("undo of the order"), Ui.Moves.Num() == 2 && Ui.Moves[0].FighterId == TEXT("a"));
    // A server rejection re-reads the same seq: the stack stays (MS-E-113).
    const int32 Depth = MsUndoDepth(Ui);
    Ui.OnSnapshot(Snap, Board, Fighters);
    TestEqual(TEXT("same seq (a rejection's refetch): stack kept"), MsUndoDepth(Ui), Depth);
    // A new applied seq is a barrier (MS-E-95).
    Ui.OnSnapshot(MsSnapshot(Hand, ManeuverA, 6), Board, Fighters);
    TestEqual(TEXT("new seq: stack cleared"), MsUndoDepth(Ui), 0);
    TestEqual(TEXT("new seq: the draft itself stays"), Ui.Moves.Num(), 2);
    TestTrue(TEXT("one more op"), Ui.SetDestination(TEXT("a"), 1, 1, MsSnapshot(Hand, ManeuverA, 6), Board, Fighters, Reason));
    TestEqual(TEXT("one record"), MsUndoDepth(Ui), 1);
    Ui.OnSnapshot(MsSnapshot(Hand, TEXT("maneuver:2:9"), 6), Board, Fighters);
    TestEqual(TEXT("another maneuverId: stack cleared"), MsUndoDepth(Ui), 0);
  }

  // ---- Delete, Tab / Shift+Tab, Ctrl+Up/Down before the D arrows, MS-S-08 arrows ----
  {
    TArray<FS08BoardFighter> Team = Fighters;
    Team.Add(MsFighter(TEXT("c"), Me, 2, 2, 2.0));
    Team.Add(MsFighter(TEXT("dead"), Me, 3, 2, 2.0, 0));
    FS08BoardFighter Stuck = MsFighter(TEXT("stuck"), Me, 4, 2, 2.0);
    Stuck.Effects.Add(TEXT("immobilized"));
    Team.Add(Stuck);
    TArray<FMsCard> Big;
    for (int32 Index = 0; Index < 10; ++Index) Big.Add({FString::Printf(TEXT("k%d"), Index), true, Index % 3});
    const FS08Snapshot BigSnap = MsSnapshot(Big, ManeuverA, 5);
    FS09CommandUi Ui = MsOpen(BigSnap, Board, Team);
    FS09MoveInput In;
    In.OnKey(ES09MoveKey::Tab, Ui, BigSnap, Board, Team, {});
    TestEqual(TEXT("Tab: first own fighter"), Ui.SelectedFighterId, FString(TEXT("a")));
    In.OnKey(ES09MoveKey::Tab, Ui, BigSnap, Board, Team, {});
    TestEqual(TEXT("Tab: next"), Ui.SelectedFighterId, FString(TEXT("b")));
    In.OnKey(ES09MoveKey::Tab, Ui, BigSnap, Board, Team, {});
    TestEqual(TEXT("Tab: c"), Ui.SelectedFighterId, FString(TEXT("c")));
    In.OnKey(ES09MoveKey::Tab, Ui, BigSnap, Board, Team, {});
    TestEqual(TEXT("Tab skips the dead and the immobilized, wraps"), Ui.SelectedFighterId, FString(TEXT("a")));
    In.OnKey(ES09MoveKey::ShiftTab, Ui, BigSnap, Board, Team, {});
    TestEqual(TEXT("Shift+Tab: previous"), Ui.SelectedFighterId, FString(TEXT("c")));
    TestTrue(TEXT("c drafted"), Ui.SetDestination(TEXT("c"), 2, 1, BigSnap, Board, Team, Reason));
    In.OnKey(ES09MoveKey::Tab, Ui, BigSnap, Board, Team, {});
    TestTrue(TEXT("a drafted"), Ui.SetDestination(TEXT("a"), 1, 1, BigSnap, Board, Team, Reason));
    FS09InputView WithD;
    WithD.bDiscardBrowserOpen = true;
    const FS09InputResult Up = In.OnKey(ES09MoveKey::CtrlUp, Ui, BigSnap, Board, Team, WithD);
    TestTrue(TEXT("Ctrl+Up with D open: the draft order (MS-E-98)"),
             Up.bHandled && Ui.Moves.Num() == 2 && Ui.Moves[0].FighterId == TEXT("a"));
    const FS09InputResult Top = In.OnKey(ES09MoveKey::CtrlUp, Ui, BigSnap, Board, Team, WithD);
    TestTrue(TEXT("Ctrl+Up on the first move: no action, no toast (MS-E-96)"), Top.bHandled && !Top.Toast.IsSet());
    In.OnKey(ES09MoveKey::Delete, Ui, BigSnap, Board, Team, {});
    TestTrue(TEXT("Delete clears the selected fighter's move"), Ui.MoveIndexOf(TEXT("a")) == INDEX_NONE && Ui.Moves.Num() == 1);
    TestTrue(TEXT("MS-DRAFT op=clear ... src=key (one line)"), MsTracedLine(Ui, {TEXT("op=clear"), TEXT("src=key")}));
    // MS-S-08 with 10 cards: the 10th only by the arrows (MS-E-97).
    In.OnKey(ES09MoveKey::B, Ui, BigSnap, Board, Team, {});
    TestTrue(TEXT("panel open"), In.bBoostPanelOpen);
    TestFalse(TEXT("arrows with D open stay with D"), In.OnKey(ES09MoveKey::Left, Ui, BigSnap, Board, Team, WithD).bHandled);
    In.OnKey(ES09MoveKey::Left, Ui, BigSnap, Board, Team, {});
    TestEqual(TEXT("Left wraps to the 10th card"), In.BoostCursor, 9);
    In.OnKey(ES09MoveKey::Enter, Ui, BigSnap, Board, Team, {});
    TestEqual(TEXT("Enter in MS-S-08 picks the card under the cursor"), Ui.BoostCardId, FString(TEXT("k9")));
    TestFalse(TEXT("the pick closes MS-S-08"), In.bBoostPanelOpen);
  }

  // ---- click on release; a drag or a lost focus cancels (MS-R-34, MS-E-104) ----
  {
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    FS09MoveInput In;
    MsClick(In, Ui, Snap, Board, Fighters, FIntPoint(0, 1), TEXT("a"));
    TestEqual(TEXT("click on a selects it"), Ui.SelectedFighterId, FString(TEXT("a")));
    In.OnPointerPressed(FIntPoint(2, 1), FString());
    TestEqual(TEXT("nothing happens on the press"), Ui.Moves.Num(), 0);
    In.OnPointerReleased(FIntPoint(3, 1), FString(), Ui, Snap, Board, Fighters);
    TestEqual(TEXT("release over another space: no target"), Ui.Moves.Num(), 0);
    In.OnPointerPressed(FIntPoint(2, 1), FString());
    In.SetHover(FIntPoint(2, 1));
    In.OnFocusLost();
    TestTrue(TEXT("focus lost: hover cleared"), In.HoverCell == FIntPoint(-1, -1));
    In.OnPointerReleased(FIntPoint(2, 1), FString(), Ui, Snap, Board, Fighters);
    TestEqual(TEXT("focus lost: the press is gone"), Ui.Moves.Num(), 0);
    MsClick(In, Ui, Snap, Board, Fighters, FIntPoint(2, 1));
    TestEqual(TEXT("press + release over the same space: target set"), Ui.Moves.Num(), 1);
    const uint32 Revision = Ui.DraftRevision;
    MsClick(In, Ui, Snap, Board, Fighters, FIntPoint(2, 1));
    TestEqual(TEXT("the same target again: no action (MS-E-83)"), Ui.DraftRevision, Revision);
    const FS09InputResult Far = MsClick(In, Ui, Snap, Board, Fighters, FIntPoint(4, 0));
    TestTrue(TEXT("unreachable: CUE-004 + reason, target unchanged"),
             Far.IllegalCell == FIntPoint(4, 0) && Far.Toast.IsSet() && Ui.Moves[0].DestX == 2);
    TestTrue(TEXT("MS-DRAFT op=assign ... src=click (one line)"), MsTracedLine(Ui, {TEXT("op=assign"), TEXT("src=click")}));
  }

  // ---- MS-R-71: the plan of MS-E-33 by mouse; the figure that leaves goes to 50 % ----
  {
    const TArray<FS08BoardFighter> Line = {MsFighter(TEXT("a"), Me, 2, 1, 2.0), MsFighter(TEXT("b"), Me, 0, 1, 2.0)};
    FS09CommandUi Ui = MsOpen(Snap, Board, Line);
    FS09MoveInput In;
    MsClick(In, Ui, Snap, Board, Line, FIntPoint(2, 1), TEXT("a"));
    MsClick(In, Ui, Snap, Board, Line, FIntPoint(3, 1));
    TestEqual(TEXT("A leaves first"), Ui.Moves.Num(), 1);
    MsClick(In, Ui, Snap, Board, Line, FIntPoint(0, 1), TEXT("b"));
    TestEqual(TEXT("B selected"), Ui.SelectedFighterId, FString(TEXT("b")));
    // The press/release lands on A's figure, but A's space is in B's tiers (A has left by then).
    MsClick(In, Ui, Snap, Board, Line, FIntPoint(2, 1), TEXT("a"));
    TestEqual(TEXT("the space wins over the figure: B targets A's space"), Ui.Moves.Num(), 2);
    TestTrue(TEXT("B's target is X"), Ui.Moves.Num() == 2 && Ui.Moves[1].FighterId == TEXT("b") && Ui.Moves[1].DestX == 2);
    TestEqual(TEXT("B stays selected"), Ui.SelectedFighterId, FString(TEXT("b")));
    TestTrue(TEXT("A is drawn at 50 %"), Ui.FadedFighters(Line).Contains(TEXT("a")));
    TestFalse(TEXT("B is not"), Ui.FadedFighters(Line).Contains(TEXT("b")));
    MsClick(In, Ui, Snap, Board, Line, FIntPoint(0, 1), TEXT("b"));
    TestEqual(TEXT("a click on the selected fighter's own space clears its move"), Ui.MoveIndexOf(TEXT("b")), INDEX_NONE);
  }

  // ---- routing: no click outside a draft reaches the TASK-022 quick move without the flag (B1) ----
  for (const ES09CommandMode Mode : {ES09CommandMode::None, ES09CommandMode::ManeuverDraft, ES09CommandMode::DiscardDraft,
                                     ES09CommandMode::AttackDraft, ES09CommandMode::CombatDefense,
                                     ES09CommandMode::CombatResolve, ES09CommandMode::PendingChoice,
                                     ES09CommandMode::SchemeChoice}) {
    const int32 M = static_cast<int32>(Mode);
    TestFalse(FString::Printf(TEXT("mode %d: no quick move without the flag"), M),
              FS09MoveInput::LegacyQuickMoveReachable(Mode, false));
    TestTrue(FString::Printf(TEXT("mode %d: quick move with the flag only from None"), M),
             FS09MoveInput::LegacyQuickMoveReachable(Mode, true) == (Mode == ES09CommandMode::None));
    TestTrue(FString::Printf(TEXT("mode %d: move-selection routing"), M),
             FS09MoveInput::RoutesMoveSelection(Mode, false) ==
                 (Mode == ES09CommandMode::None || Mode == ES09CommandMode::ManeuverDraft));
  }
  TestFalse(TEXT("with the flag, None keeps the legacy bindings"),
            FS09MoveInput::RoutesMoveSelection(ES09CommandMode::None, true));

  // ---- MS-S-00: outside the viewer's action time a click only shows the plate ----
  {
    FS08Snapshot Combat = MsTurnSnapshot(Hand);
    Combat.Phase = TEXT("COMBAT");
    FS09CommandUi Ui = MsOpen(Combat, Board, Fighters);
    FS09MoveInput In;
    const FS09InputResult R = MsClick(In, Ui, Combat, Board, Fighters, FIntPoint(0, 1), TEXT("a"));
    TestTrue(TEXT("no inspection in COMBAT"), !R.bHandled && Ui.SelectedFighterId.IsEmpty());
  }

  // ---- no binding needs a held key; every chord has a single-key alternative (MS-R-35) ----
  for (const FS09KeyBinding& Binding : FS09MoveInput::Bindings()) {
    TestFalse(FString::Printf(TEXT("%s: no hold"), Binding.Input), Binding.bHold);
    if (Binding.bChord) {
      TestTrue(FString::Printf(TEXT("%s: has an alternative"), Binding.Input), FCString::Strlen(Binding.Alternative) > 0);
    }
  }
  return true;
}

// DE-014 (W-21, UI-INP-011; MS-D-17 / MS-R-34 for the board): n = 20 synthetic
// clicks on board spaces with a 0 ms hold (press and release in one poll) and a
// 50 ms hold (snapshots applied between them) per space kind - 0 lost: every
// click selects / targets, or answers CUE-004 with a why.* key; a click made
// while a command is in flight is answered why.syncing and edits nothing.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelClickReliabilityTest, "Unmatched.S09.MoveSel.ClickReliability",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelClickReliabilityTest::RunTest(const FString&) {
  const FS08BoardModel Board = MsGrid(6, 3);
  const TArray<FMsCard> Hand = {{TEXT("c2"), true, 2}, {TEXT("c1"), true, 1}};
  const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 0, 1, 2.0), MsFighter(TEXT("b"), Me, 5, 1, 2.0),
                                             MsFighter(TEXT("e"), Opp, 5, 0)};
  constexpr int32 N = 20;
  int32 Clicks = 0;
  int32 Lost = 0;
  // One click: press, (50 ms hold: the snapshots that arrive meanwhile), release.
  auto Click = [&](FS09MoveInput& In, FS09CommandUi& Ui, const FS08Snapshot& Snap, const FIntPoint& Cell,
                   const FString& FighterId, bool bHold) {
    In.OnPointerPressed(Cell, FighterId);
    if (bHold) {
      FS08Snapshot Fresh = Snap;
      Fresh.SequenceNumber += 1;
      Ui.OnSnapshot(Fresh, Board, Fighters);
      In.OnSnapshot(Ui, Fresh);
    }
    return In.OnPointerReleased(Cell, FighterId, Ui, Snap, Board, Fighters);
  };
  auto Answered = [](const FS09InputResult& R) { return R.bHandled && (R.bSelectionChanged || R.Toast.IsSet()); };
  for (const bool bHold : {false, true}) {
    const TCHAR* HoldTag = bHold ? TEXT("50 ms") : TEXT("0 ms");
    // ---- reachable spaces in the draft: each click sets the target ----
    {
      const FS08Snapshot Snap = MsSnapshot(Hand, ManeuverA, 5);
      FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
      FS09MoveInput In;
      int32 Ok = 0;
      for (int32 K = 0; K < N; ++K) {
        const FS09InputResult Pick = Click(In, Ui, Snap, FIntPoint(0, 1), TEXT("a"), bHold);
        const FIntPoint Target = (K % 2) ? FIntPoint(1, 1) : FIntPoint(2, 1);
        const FS09InputResult R = Click(In, Ui, Snap, Target, FString(), bHold);
        const FS09DraftMove* Move = MsMove(Ui, TEXT("a"));
        const bool bSet = Answered(Pick) && Answered(R) && Move && Move->DestX == Target.X && Move->DestY == Target.Y;
        Ok += bSet ? 1 : 0;
        Clicks += 2;
        Lost += bSet ? 0 : 1;
      }
      TestEqual(FString::Printf(TEXT("reachable space, hold %s: every click targets"), HoldTag), Ok, N);
    }
    // ---- an unreachable space: CUE-004 with the reason, the target unchanged ----
    {
      const FS08Snapshot Snap = MsSnapshot(Hand, ManeuverA, 5);
      FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
      FS09MoveInput In;
      Click(In, Ui, Snap, FIntPoint(0, 1), TEXT("a"), false);
      int32 Ok = 0;
      for (int32 K = 0; K < N; ++K) {
        const FS09InputResult R = Click(In, Ui, Snap, FIntPoint(4, 0), FString(), bHold);
        const bool bWhy =
            Answered(R) && R.Toast.Key.ToString().StartsWith(TEXT("why.")) && R.IllegalCell == FIntPoint(4, 0);
        Ok += bWhy ? 1 : 0;
        ++Clicks;
        Lost += bWhy ? 0 : 1;
      }
      TestEqual(FString::Printf(TEXT("unreachable space, hold %s: every click answers why.*"), HoldTag), Ok, N);
      TestEqual(TEXT("... and the draft is unchanged"), Ui.Moves.Num(), 0);
    }
    // ---- MS-S-00 (the opponent's turn): an empty space answers why.not.your.turn ----
    {
      FS08Snapshot Snap = MsTurnSnapshot(Hand);
      Snap.CurrentTurnPlayerId = Opp;
      FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
      FS09MoveInput In;
      int32 Ok = 0;
      for (int32 K = 0; K < N; ++K) {
        const FS09InputResult R = Click(In, Ui, Snap, FIntPoint(1 + K % 3, 2), FString(), bHold);
        const bool bWhy = Answered(R) && R.Toast.Key == FName(TEXT("why.not.your.turn"));
        Ok += bWhy ? 1 : 0;
        ++Clicks;
        Lost += bWhy ? 0 : 1;
      }
      TestEqual(FString::Printf(TEXT("MS-S-00 empty space, hold %s: every click answers why.not.your.turn"), HoldTag),
                Ok, N);
      const FS09InputResult Plate = Click(In, Ui, Snap, FIntPoint(0, 1), TEXT("a"), bHold);
      TestTrue(TEXT("MS-S-00 own fighter: the plate only (no selection, no toast)"),
               !Plate.bHandled && Ui.SelectedFighterId.IsEmpty());
    }
    // ---- a command in flight (MS-S-05 / MS-S-09): why.syncing, nothing edited ----
    {
      const FS08Snapshot Snap = MsSnapshot(Hand, ManeuverA, 5);
      FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
      FS09MoveInput In;
      Click(In, Ui, Snap, FIntPoint(0, 1), TEXT("a"), false);
      const uint32 Revision = Ui.DraftRevision;
      int32 Ok = 0;
      for (int32 K = 0; K < N; ++K) {
        const FIntPoint Cell = (K % 2) ? FIntPoint(1, 1) : FIntPoint(2, 1);
        In.OnPointerPressed(Cell, FString());
        const FS09InputResult R = In.OnPointerReleasedGated(Cell, FString(), FS09Reason::Make(TEXT("why.syncing")));
        const bool bWhy = R.bHandled && R.Toast.Key == FName(TEXT("why.syncing"));
        Ok += bWhy ? 1 : 0;
        ++Clicks;
        Lost += bWhy ? 0 : 1;
      }
      TestEqual(FString::Printf(TEXT("in flight, hold %s: every click answers why.syncing"), HoldTag), Ok, N);
      TestEqual(TEXT("... and edits nothing"), Ui.DraftRevision, Revision);
      In.OnPointerPressed(FIntPoint(1, 1), FString());
      const FS09InputResult Away =
          In.OnPointerReleasedGated(FIntPoint(2, 1), FString(), FS09Reason::Make(TEXT("why.syncing")));
      TestFalse(TEXT("in flight: a drag away cancels silently (MS-R-34)"), Away.Toast.IsSet());
    }
  }
  // ---- the idle reasons by state ----
  {
    FS08Snapshot Snap = MsTurnSnapshot(Hand);
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    Snap.CurrentTurnPlayerId = Opp;
    TestEqual(TEXT("idle reason: not your turn"), FS09MoveInput::IdleClickReason(Ui, Snap).Key.ToString(),
              FString(TEXT("why.not.your.turn")));
    Snap.CurrentTurnPlayerId = Me;
    Snap.Phase = TEXT("TURN_END");
    TestEqual(TEXT("idle reason: no actions"), FS09MoveInput::IdleClickReason(Ui, Snap).Key.ToString(),
              FString(TEXT("why.no.actions")));
    Ui.bHasPendingChoice = true;
    TestEqual(TEXT("idle reason: the opponent's choice"), FS09MoveInput::IdleClickReason(Ui, Snap).Key.ToString(),
              FString(TEXT("why.wait.opponent.choice")));
  }
  TestEqual(TEXT("0 lost board clicks"), Lost, 0);
  AddInfo(FString::Printf(TEXT("DE-014 board clicks: %d synthetic clicks over the 0 and 50 ms holds, lost %d"), Clicks,
                          Lost));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelPreDraftAndNoQuickMoveTest, "Unmatched.S09.MoveSel.PreDraftAndNoQuickMove",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelPreDraftAndNoQuickMoveTest::RunTest(const FString&) {
  const FS08BoardModel Board = MsGrid(7, 3);
  const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 0, 1, 2.0), MsFighter(TEXT("e"), Opp, 6, 0)};
  const TArray<FMsCard> Before = {{TEXT("c1"), true, 1}};
  const FS08Snapshot Turn = MsTurnSnapshot(Before, 4);

  TestFalse(TEXT("TASK-022 quick move is off without -S08LegacyQuickMove"), FS09MoveInput::LegacyQuickMoveEnabled());

  // ---- clicks outside the draft never send: inspect, pre-draft, same target ----
  FS09CommandUi Ui = MsOpen(Turn, Board, Fighters);
  FS09MoveInput In;
  int32 Sends = 0;
  auto Count = [&Sends](const FS09InputResult& R) { Sends += (R.bBeginManeuver || R.bConfirmManeuver) ? 1 : 0; };
  Count(MsClick(In, Ui, Turn, Board, Fighters, FIntPoint(0, 1), TEXT("a")));
  TestEqual(TEXT("MS-S-02: a inspected"), Ui.SelectedFighterId, FString(TEXT("a")));
  TestTrue(TEXT("tiers by the hand before the draw: base 2, boost +1"),
           Ui.SelectedTiers.bValid && Ui.SelectedTiers.BaseTier.Contains(FIntPoint(2, 1)) &&
               Ui.SelectedTiers.BoostTier.Contains(FIntPoint(3, 1)));
  Count(MsClick(In, Ui, Turn, Board, Fighters, FIntPoint(2, 1)));
  TestTrue(TEXT("MS-S-03: pre-draft (Ok)"), Ui.PreDraft.bSet && Ui.PreDraft.X == 2 &&
                                                Ui.PreDraft.Status == ES09DraftMoveStatus::Ok);
  Count(MsClick(In, Ui, Turn, Board, Fighters, FIntPoint(2, 1)));
  TestTrue(TEXT("the same target again: unchanged (MS-E-83)"), Ui.PreDraft.bSet && Ui.PreDraft.X == 2);
  const FS09InputResult Boosted = MsClick(In, Ui, Turn, Board, Fighters, FIntPoint(3, 1));
  Count(Boosted);
  TestTrue(TEXT("boost tier: needs boost +1 (MS-E-82)"), Ui.PreDraft.Status == ES09DraftMoveStatus::NeedBoost &&
                                                             Ui.PreDraft.RequiredBoost == 1);
  TestEqual(TEXT("its toast"), MsKey(Boosted.Toast), FString(TEXT("why.cell.needs.boost")));
  TestEqual(TEXT("0 mutations before Enter (MS-R-01)"), Sends, 0);
  TestTrue(TEXT("MS-DRAFT op=predraft ... src=click (one line)"), MsTracedLine(Ui, {TEXT("op=predraft"), TEXT("src=click")}));

  // ---- Enter begins; the target moves into the draft by the NEW hand ----
  const FS09InputResult Begin = In.OnKey(ES09MoveKey::Enter, Ui, Turn, Board, Fighters, {});
  TestTrue(TEXT("Enter in MS-S-03: beginManeuver"), Begin.bBeginManeuver);
  // A same-seq re-read (e.g. the recovery of an unknown outcome, MS-E-84) keeps the pre-draft.
  Ui.OnSnapshot(Turn, Board, Fighters);
  TestTrue(TEXT("pre-draft survives a re-read"), Ui.PreDraft.bSet);
  const TArray<FMsCard> After = {{TEXT("c1"), true, 1}, {TEXT("c3"), true, 3}};
  Ui.OnSnapshot(MsSnapshot(After, ManeuverA, 5), Board, Fighters);
  TestTrue(TEXT("draft open"), Ui.Mode == ES09CommandMode::ManeuverDraft);
  const FS09DraftMove* Carried = MsMove(Ui, TEXT("a"));
  TestTrue(TEXT("the target is a move of the draft"), Carried && Carried->DestX == 3 && Carried->DestY == 1);
  TestEqual(TEXT("by the new hand: NeedBoost (+1 > no card)"), MsStatus(Carried), FString(TEXT("needBoost")));
  TestFalse(TEXT("the pre-draft is consumed"), Ui.PreDraft.bSet);
  TestTrue(TEXT("carried as a click (op=assign ... src=click, one line)"),
           MsTracedLine(Ui, {TEXT("MS-DRAFT op=assign"), TEXT("src=click")}));
  TestEqual(TEXT("the carried move is one undo record"), MsUndoDepth(Ui), 1);
  In.OnKey(ES09MoveKey::Backspace, Ui, MsSnapshot(After, ManeuverA, 5), Board, Fighters, {});
  TestEqual(TEXT("Backspace removes the carried target"), Ui.Moves.Num(), 0);

  // ---- no path even with the new hand's best BOOST: why.predraft.lost ----
  {
    const TArray<FMsCard> Rich = {{TEXT("c4"), true, 4}};
    FS09CommandUi Lost = MsOpen(MsTurnSnapshot(Rich, 4), Board, Fighters);
    FS09MoveInput In2;
    MsClick(In2, Lost, MsTurnSnapshot(Rich, 4), Board, Fighters, FIntPoint(0, 1), TEXT("a"));
    MsClick(In2, Lost, MsTurnSnapshot(Rich, 4), Board, Fighters, FIntPoint(6, 1));
    TestTrue(TEXT("far pre-draft with +4 in hand"), Lost.PreDraft.bSet);
    // After the draw the hand holds only a +0 card: no path even with its best BOOST.
    Lost.OnSnapshot(MsSnapshot({{TEXT("c0"), true, 0}}, ManeuverA, 5), Board, Fighters);
    TestEqual(TEXT("why.predraft.lost"), MsKey(Lost.LastReason), FString(TEXT("why.predraft.lost")));
    TestEqual(TEXT("the draft opens without a target"), Lost.Moves.Num(), 0);
  }

  // ---- the turn passes: the pre-draft goes (exit to MS-S-00) ----
  {
    FS09CommandUi Gone = MsOpen(Turn, Board, Fighters);
    FS09MoveInput In3;
    MsClick(In3, Gone, Turn, Board, Fighters, FIntPoint(0, 1), TEXT("a"));
    MsClick(In3, Gone, Turn, Board, Fighters, FIntPoint(2, 1));
    FS08Snapshot Theirs = MsTurnSnapshot(Before, 6);
    Theirs.CurrentTurnPlayerId = Opp;
    Gone.OnSnapshot(Theirs, Board, Fighters);
    TestTrue(TEXT("not my turn: pre-draft and selection gone"), !Gone.PreDraft.bSet && Gone.SelectedFighterId.IsEmpty());
  }

  // ---- -S08Maneuver auto driver through the draft (src=auto), demo gate seq + 2 ----
  {
    FS08BoardFighter Hero = MsFighter(TEXT("h"), Me, 0, 1, 2.0);
    Hero.bIsHero = true;
    const TArray<FS08BoardFighter> Team = {Hero, MsFighter(TEXT("e"), Opp, 6, 0)};
    FS09CommandUi Auto = MsOpen(Turn, Board, Team);
    FString HeroId;
    FIntPoint Target;
    TestTrue(TEXT("auto target"), FS09MoveInput::AutoManeuverTarget(Auto, Board, Team, HeroId, Target));
    TestTrue(TEXT("one step of the hero"), HeroId == TEXT("h") && Board.Neighbours(FIntPoint(0, 1)).Contains(Target));
    bool bUnchanged = false;
    TestTrue(TEXT("auto pre-draft"), Auto.InspectFighter(HeroId, Turn, Board, Team) &&
                                         Auto.SetPreDraft(HeroId, Target.X, Target.Y, Turn, Board, Team, bUnchanged));
    FString Reason;
    TestTrue(TEXT("begin legal"), Auto.CanBeginManeuver(Turn, Reason));
    Auto.OnSnapshot(MsSnapshot(Before, ManeuverA, 5), Board, Team);
    TestTrue(TEXT("MS-DRAFT op=assign ... src=auto (one line)"), MsTracedLine(Auto, {TEXT("op=assign"), TEXT("src=auto")}));
    FS09ManeuverCommand Command;
    TestTrue(TEXT("auto confirm"), Auto.ConfirmManeuver(MsSnapshot(Before, ManeuverA, 5), Board, Team, Command, Reason));
    TestEqual(TEXT("one canonical step"), Command.Moves.Num() == 1 ? Command.Moves[0].Path.Num() : 0, 1);
    TestFalse(TEXT("gate: begin applied only (seq + 1)"),
              FS09MoveInput::AutoManeuverSettled(4, MsSnapshot(Before, ManeuverA, 5)));
    TestFalse(TEXT("gate: seq + 2 with the maneuver still open"),
              FS09MoveInput::AutoManeuverSettled(4, MsSnapshot(Before, ManeuverA, 6)));
    TestTrue(TEXT("gate: seq + 2, maneuver closed"), FS09MoveInput::AutoManeuverSettled(4, MsTurnSnapshot(Before, 6)));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelExhaustionConfirmTest, "Unmatched.S09.MoveSel.ExhaustionConfirm",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelExhaustionConfirmTest::RunTest(const FString&) {
  const FS08BoardModel Board = MsGrid(6, 3);
  FS08BoardFighter Hero = MsFighter(TEXT("h"), Me, 0, 1, 2.0);
  Hero.bIsHero = true;
  const TArray<FS08BoardFighter> Team = {Hero, MsFighter(TEXT("s1"), Me, 1, 0, 2.0), MsFighter(TEXT("s2"), Me, 1, 2, 2.0),
                                         MsFighter(TEXT("e"), Opp, 5, 1)};
  const FS08Snapshot Turn = MsTurnSnapshot({{TEXT("c1"), true, 1}}, 4);
  FS09CommandUi Ui = MsOpen(Turn, Board, Team);
  FS09MoveInput In;
  FS09InputView Empty;
  Empty.OwnDeckCount = 0;

  FS09InputResult R = In.OnKey(ES09MoveKey::M, Ui, Turn, Board, Team, Empty);
  TestTrue(TEXT("empty deck: MS-S-04, no begin"), In.bExhaustionOpen && !R.bBeginManeuver);
  TestEqual(TEXT("the prompt names the fighters"), MsKey(R.Toast), FString(TEXT("ms.begin.exhaustion")));
  TestTrue(TEXT("3 own fighters take the damage"), R.Toast.Text().Contains(TEXT("(3)")));
  // MS-S-04 is modal: other keys and board clicks are swallowed.
  TestTrue(TEXT("Tab swallowed"), In.OnKey(ES09MoveKey::Tab, Ui, Turn, Board, Team, Empty).bHandled &&
                                      Ui.SelectedFighterId.IsEmpty());
  TestTrue(TEXT("a click swallowed"), MsClick(In, Ui, Turn, Board, Team, FIntPoint(0, 1), TEXT("h")).bHandled &&
                                          Ui.SelectedFighterId.IsEmpty() && In.bExhaustionOpen);
  R = In.OnKey(ES09MoveKey::Escape, Ui, Turn, Board, Team, Empty);
  TestTrue(TEXT("Cancel: closed, nothing sent"), !In.bExhaustionOpen && !R.bBeginManeuver);
  TestEqual(TEXT("a stale but known 0 still prompts"), FS09MoveInput::DeckCountForPrompt(0, true), 0);
  TestEqual(TEXT("no deck projection yet: no prompt"), FS09MoveInput::DeckCountForPrompt(5, false), -1);
  In.OnKey(ES09MoveKey::M, Ui, Turn, Board, Team, Empty);
  R = In.OnKey(ES09MoveKey::Enter, Ui, Turn, Board, Team, Empty);
  TestTrue(TEXT("Begin anyway: beginManeuver"), R.bBeginManeuver && !In.bExhaustionOpen);
  FS09InputView Full;
  Full.OwnDeckCount = 5;
  TestTrue(TEXT("a deck with cards: M begins at once"), In.OnKey(ES09MoveKey::M, Ui, Turn, Board, Team, Full).bBeginManeuver);

  // After the exhaustion damage: the dead sidekick is out of the draft; an empty hand has no boost panel.
  TArray<FS08BoardFighter> Hurt = Team;
  Hurt[1].Health = 0;
  const FS08Snapshot Draft = MsSnapshot({}, ManeuverA, 5);
  Ui.OnSnapshot(Draft, Board, Hurt);
  In.OnSnapshot(Ui, Draft);
  TestTrue(TEXT("draft open"), Ui.Mode == ES09CommandMode::ManeuverDraft);
  TestFalse(TEXT("the dead sidekick cannot be selected"), Ui.SelectFighter(TEXT("s1"), Draft, Board, Hurt));
  TestEqual(TEXT("why.fighter.defeated"), MsKey(Ui.LastReason), FString(TEXT("why.fighter.defeated")));
  TestEqual(TEXT("Tab skips it"), Ui.CycleFighter(Hurt, 1), FString(TEXT("h")));
  R = In.OnKey(ES09MoveKey::B, Ui, Draft, Board, Hurt, {});
  TestTrue(TEXT("empty hand: no boost panel"), !In.bBoostPanelOpen && MsKey(R.Toast) == TEXT("ms.boost.empty"));
  TestEqual(TEXT("empty hand: no offers"), Ui.BoostOffers().Num(), 0);
  // The hero died of exhaustion: GAME_OVER, no draft.
  FS08Snapshot Over = MsSnapshot({}, ManeuverA, 6);
  Over.Phase = TEXT("GAME_OVER");
  Ui.OnSnapshot(Over, Board, Hurt);
  TestTrue(TEXT("hero dead: no draft"), Ui.Mode == ES09CommandMode::None && Ui.Moves.Num() == 0);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelAutoManeuverPlanTest, "Unmatched.S09.MoveSel.AutoManeuverPlan",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelAutoManeuverPlanTest::RunTest(const FString&) {
  // M1 (MS-AT-32): -S08ManeuverPlan=boost3 on the draft the -S08Maneuver
  // driver opened - the hero step carried in (src=auto), then the best BOOST
  // card and two sidekicks (the first as far as the boost reaches, the next
  // the nearest), all through the draft API with src=auto.
  const FS08BoardModel Board = MsGrid(9, 5);
  FS08BoardFighter Hero = MsFighter(TEXT("h"), Me, 0, 2, 2.0);
  Hero.bIsHero = true;
  const TArray<FS08BoardFighter> Team = {Hero, MsFighter(TEXT("s1"), Me, 0, 1, 2.0), MsFighter(TEXT("s2"), Me, 0, 3, 2.0),
                                         MsFighter(TEXT("s3"), Me, 2, 0, 2.0), MsFighter(TEXT("e"), Opp, 8, 4)};
  const TArray<FMsCard> Before = {{TEXT("c1"), true, 1}};
  // After the draw: +1, a printed-null card, two +3 (the first of equals wins).
  const TArray<FMsCard> After = {{TEXT("c1"), true, 1}, {TEXT("cn"), false, 0}, {TEXT("c3"), true, 3},
                                 {TEXT("c3b"), true, 3}};
  const FS08Snapshot Turn = MsTurnSnapshot(Before, 4);
  const FS08Snapshot Draft = MsSnapshot(After, ManeuverA, 5);

  // ---- the flag: opt-in, one known plan ----
  TestTrue(TEXT("no -S08ManeuverPlan in this run: empty plan (driver unchanged)"),
           FS09MoveInput::AutoManeuverPlanFromCommandLine().IsEmpty());
  TestTrue(TEXT("boost3 is known"), FS09MoveInput::IsKnownManeuverPlan(TEXT("boost3")) &&
                                        FS09MoveInput::IsKnownManeuverPlan(TEXT("BOOST3")));
  TestFalse(TEXT("another plan is not"), FS09MoveInput::IsKnownManeuverPlan(TEXT("boost2")));
  TestFalse(TEXT("an empty plan is not"), FS09MoveInput::IsKnownManeuverPlan(FString()));

  // ---- the driver's pre-draft, begin, the draft opens with the hero step ----
  auto OpenDriverDraft = [&](const TArray<FS08BoardFighter>& Fighters, const FS08Snapshot& Opened) {
    FS09CommandUi Ui = MsOpen(Turn, Board, Fighters);
    FString HeroId;
    FIntPoint Target;
    bool bUnchanged = false;
    const bool bPre = FS09MoveInput::AutoManeuverTarget(Ui, Board, Fighters, HeroId, Target) &&
                      Ui.InspectFighter(HeroId, Turn, Board, Fighters) &&
                      Ui.SetPreDraft(HeroId, Target.X, Target.Y, Turn, Board, Fighters, bUnchanged);
    TestTrue(TEXT("driver pre-draft"), bPre);
    Ui.OnSnapshot(Opened, Board, Fighters);
    return Ui;
  };
  FS09CommandUi Ui = OpenDriverDraft(Team, Draft);
  TestTrue(TEXT("draft open with the hero step"), Ui.Mode == ES09CommandMode::ManeuverDraft && Ui.Moves.Num() == 1 &&
                                                      Ui.Moves[0].FighterId == TEXT("h"));
  Ui.DraftTrace.Reset();

  FString Summary;
  TestTrue(TEXT("boost3: ok"), FS09MoveInput::RunAutoManeuverPlan(TEXT("boost3"), Ui, Draft, Board, Team, Summary));
  TestTrue(TEXT("summary line"), Summary.StartsWith(TEXT("AUTO maneuver plan=boost3 ok=1 moves=3 boost=c3 value=3 maxRequired=3 sidekicks=2 confirmable=1 list=h@")));
  TestEqual(TEXT("the highest printed BOOST, first of equals"), Ui.BoostCardId, FString(TEXT("c3")));
  TestEqual(TEXT("three moves"), Ui.Moves.Num(), 3);
  if (Ui.Moves.Num() == 3) {
    TestEqual(TEXT("1: the carried hero step"), Ui.Moves[0].FighterId, FString(TEXT("h")));
    TestEqual(TEXT("2: the first sidekick"), Ui.Moves[1].FighterId, FString(TEXT("s1")));
    TestEqual(TEXT("3: the next sidekick"), Ui.Moves[2].FighterId, FString(TEXT("s2")));
    TestTrue(TEXT("the first added goes base + boost (spends the boost)"),
             Ui.Moves[1].Path.Num() == 5 && Ui.Moves[1].RequiredBoost == 3 && Ui.Moves[1].Allowance == 5);
    TestTrue(TEXT("the next one the nearest"), Ui.Moves[2].Path.Num() == 1 && Ui.Moves[2].RequiredBoost == 0);
    for (const FS09DraftMove& Move : Ui.Moves) {
      TestEqual(FString::Printf(TEXT("%s is Ok"), *Move.FighterId), MsStatus(&Move), FString(TEXT("ok")));
    }
  }
  TestTrue(TEXT("no selection left"), Ui.SelectedFighterId.IsEmpty());
  TestTrue(TEXT("MS-DRAFT op=boost ... src=auto"), MsTracedLine(Ui, {TEXT("op=boost"), TEXT("src=auto")}));
  TestTrue(TEXT("MS-DRAFT op=assign fighter=s1 ... src=auto"),
           MsTracedLine(Ui, {TEXT("op=assign"), TEXT("src=auto"), TEXT("fighter=s1")}));
  TestTrue(TEXT("MS-DRAFT op=assign fighter=s2 ... src=auto"),
           MsTracedLine(Ui, {TEXT("op=assign"), TEXT("src=auto"), TEXT("fighter=s2")}));
  TestFalse(TEXT("nothing as a click or a key"), MsTracedLine(Ui, {TEXT("src=click")}) || MsTracedLine(Ui, {TEXT("src=key")}));
  TestTrue(TEXT("the source is restored"), Ui.DraftSource == ES09InputSource::Auto);
  FS09ManeuverCommand Command;
  FString Reason;
  TestTrue(TEXT("confirm"), Ui.ConfirmManeuver(Draft, Board, Team, Command, Reason));
  TestTrue(TEXT("the command: 3 moves + the boost card"), Command.Moves.Num() == 3 && Command.BoostCardId == TEXT("c3") &&
                                                              Command.ManeuverId == ManeuverA);

  // ---- a selected card with a printed BOOST is kept ----
  {
    FS09CommandUi Kept = OpenDriverDraft(Team, Draft);
    FString Why;
    TestTrue(TEXT("c1 selected first"), Kept.ToggleBoostCard(TEXT("c1"), Draft, Board, Team, Why));
    FString Line;
    TestTrue(TEXT("kept: ok"), FS09MoveInput::RunAutoManeuverPlan(TEXT("boost3"), Kept, Draft, Board, Team, Line));
    TestTrue(TEXT("kept: c1 stays, the far move uses +1"),
             Kept.BoostCardId == TEXT("c1") && Line.Contains(TEXT(" boost=c1 value=1 maxRequired=1 ")));
  }

  // ---- a hero boxed in by its own sidekicks (the Cobble 5x6 opening, M1 live run
  // 2026-10-04): no hero step, the plan begins without a pre-draft and moves 3 sidekicks ----
  {
    const FS08BoardModel Cobble = MsGrid(5, 6);
    FS08BoardFighter Boxed = MsFighter(TEXT("h"), Me, 2, 2, 3.0);
    Boxed.bIsHero = true;
    FS08BoardFighter Arthur = MsFighter(TEXT("e"), Opp, 2, 3);
    Arthur.bIsHero = true;
    const TArray<FS08BoardFighter> Box = {Boxed, MsFighter(TEXT("s1"), Me, 1, 2, 2.0), MsFighter(TEXT("s2"), Me, 3, 2, 2.0),
                                          MsFighter(TEXT("s3"), Me, 2, 1, 2.0), Arthur, MsFighter(TEXT("m"), Opp, 3, 3)};
    FS09CommandUi BoxUi = MsOpen(Turn, Cobble, Box);
    FString HeroId;
    FIntPoint Target;
    const bool bStep = FS09MoveInput::AutoManeuverTarget(BoxUi, Cobble, Box, HeroId, Target);
    TestFalse(TEXT("boxed: no hero step"), bStep);
    TestFalse(TEXT("boxed without a plan: the one-step driver keeps waiting"),
              FS09MoveInput::AutoManeuverBegins(bStep, FString()));
    TestTrue(TEXT("boxed with boost3: begins"), FS09MoveInput::AutoManeuverBegins(bStep, TEXT("boost3")));
    TestFalse(TEXT("an unknown plan does not begin"), FS09MoveInput::AutoManeuverBegins(bStep, TEXT("boost2")));
    TestTrue(TEXT("a hero step always begins"), FS09MoveInput::AutoManeuverBegins(true, FString()));
    FString Why;
    TestTrue(TEXT("boxed: begin legal"), BoxUi.CanBeginManeuver(Turn, Why));
    BoxUi.OnSnapshot(Draft, Cobble, Box);
    TestTrue(TEXT("boxed: the draft opens empty"), BoxUi.Mode == ES09CommandMode::ManeuverDraft && BoxUi.Moves.Num() == 0);
    FString Line;
    TestTrue(TEXT("boxed: boost3 ok"), FS09MoveInput::RunAutoManeuverPlan(TEXT("boost3"), BoxUi, Draft, Cobble, Box, Line));
    TestTrue(TEXT("boxed: summary"), Line.StartsWith(TEXT("AUTO maneuver plan=boost3 ok=1 moves=3 boost=c3 value=3 maxRequired=3 sidekicks=3 confirmable=1 list=s1@")));
    if (BoxUi.Moves.Num() == 3) {
      TestTrue(TEXT("boxed: s1 goes base + boost"), BoxUi.Moves[0].FighterId == TEXT("s1") &&
                                                       BoxUi.Moves[0].Path.Num() == 5 && BoxUi.Moves[0].RequiredBoost == 3);
      TestTrue(TEXT("boxed: s2, s3 the nearest"), BoxUi.Moves[1].FighterId == TEXT("s2") && BoxUi.Moves[1].Path.Num() == 1 &&
                                                     BoxUi.Moves[2].FighterId == TEXT("s3") && BoxUi.Moves[2].Path.Num() == 1);
    }
    FS09ManeuverCommand BoxCommand;
    TestTrue(TEXT("boxed: confirm"), BoxUi.ConfirmManeuver(Draft, Cobble, Box, BoxCommand, Why) &&
                                         BoxCommand.Moves.Num() == 3 && BoxCommand.BoostCardId == TEXT("c3"));
  }

  // ---- refusals: the summary names them, the draft keeps only Ok moves ----
  {
    FS09CommandUi NoBoost = OpenDriverDraft(Team, MsSnapshot({{TEXT("cn"), false, 0}}, ManeuverA, 5));
    FString Line;
    TestFalse(TEXT("no printed BOOST: refused"),
              FS09MoveInput::RunAutoManeuverPlan(TEXT("boost3"), NoBoost, MsSnapshot({{TEXT("cn"), false, 0}}, ManeuverA, 5),
                                                 Board, Team, Line));
    TestTrue(TEXT("no printed BOOST: ok=0 boost=none reason=boost.none"),
             Line.Contains(TEXT(" ok=0 moves=3 boost=none ")) && Line.Contains(TEXT("reason=boost.none")));
    TestTrue(TEXT("no printed BOOST: the moves are Ok (confirmable)"), NoBoost.Eval.IsConfirmable());
  }
  {
    const TArray<FS08BoardFighter> Small = {Hero, MsFighter(TEXT("s1"), Me, 0, 1, 2.0), MsFighter(TEXT("e"), Opp, 8, 4)};
    FS09CommandUi Short = OpenDriverDraft(Small, Draft);
    FString Line;
    TestFalse(TEXT("two own fighters: refused"),
              FS09MoveInput::RunAutoManeuverPlan(TEXT("boost3"), Short, Draft, Board, Small, Line));
    TestTrue(TEXT("two own fighters: moves.short:2"),
             Line.Contains(TEXT(" ok=0 moves=2 boost=c3 ")) && Line.Contains(TEXT("moves.short:2")));
    TestTrue(TEXT("two own fighters: still confirmable"), Short.Eval.IsConfirmable());
  }
  {
    FS09CommandUi Same = OpenDriverDraft(Team, Draft);
    const int32 Moves = Same.Moves.Num();
    FString Line;
    TestFalse(TEXT("unknown plan: refused"),
              FS09MoveInput::RunAutoManeuverPlan(TEXT("boost2"), Same, Draft, Board, Team, Line));
    TestTrue(TEXT("unknown plan: reason, draft untouched"),
             Line == TEXT("AUTO maneuver plan=boost2 ok=0 reason=plan.unknown") && Same.Moves.Num() == Moves &&
                 Same.BoostCardId.IsEmpty());
    FS09CommandUi Idle = MsOpen(Turn, Board, Team);
    TestFalse(TEXT("no draft: refused"), FS09MoveInput::RunAutoManeuverPlan(TEXT("boost3"), Idle, Turn, Board, Team, Line));
    TestEqual(TEXT("no draft: reason"), Line, FString(TEXT("AUTO maneuver plan=boost3 ok=0 reason=draft.closed")));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelReconnectAndRebuildTest, "Unmatched.S09.MoveSel.ReconnectAndRebuild",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelReconnectAndRebuildTest::RunTest(const FString&) {
  // Open 6 x 3 board: row 1 is the straight line, rows 0 and 2 the detours.
  const FS08BoardModel Board = MsGrid(6, 3);
  const TArray<FMsCard> Hand = {{TEXT("c2"), true, 2}, {TEXT("c1"), true, 1}};
  const FS08Snapshot Snap = MsSnapshot(Hand, ManeuverA, 5);
  const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 0, 1), MsFighter(TEXT("b"), Me, 5, 2)};
  FString Reason;
  FS08FlowController Flow(TEXT("http://127.0.0.1:9/graphql"), TEXT("ws://127.0.0.1:9/graphql"), Me);
  Flow.SetRoomForTest(TEXT("g1"), ES08Stage::Started);

  // ---- MS-R-55: the draft survives a gameplay-HUD reset (same id) ----
  FS09CommandUi First;
  First.ViewerId = Me;
  MsBindCache(First, Flow);
  First.OnSnapshot(Snap, Board, Fighters);
  TestTrue(TEXT("a drafted"), First.SetDestination(TEXT("a"), 3, 1, Snap, Board, Fighters, Reason));
  TestTrue(TEXT("b drafted"), First.SetDestination(TEXT("b"), 5, 0, Snap, Board, Fighters, Reason));
  TestTrue(TEXT("boost c2"), First.ToggleBoostCard(TEXT("c2"), Snap, Board, Fighters, Reason));
  FS08ManeuverDraftCache Cached;
  TestTrue(TEXT("the controller holds the draft"), Flow.RecallManeuverDraft(ManeuverA, Cached));
  TestEqual(TEXT("cached moves in order"), FString::Join(Cached.FighterIds, TEXT(",")), FString(TEXT("a,b")));
  TestEqual(TEXT("cached boost"), Cached.BoostCardId, FString(TEXT("c2")));
  TestFalse(TEXT("another maneuver id never recalls it"), Flow.RecallManeuverDraft(TEXT("maneuver:2:9"), Cached));

  FS09CommandUi Second; // ClearGameplayHud: a fresh command UI, same controller
  Second.ViewerId = Me;
  MsBindCache(Second, Flow);
  Second.OnSnapshot(Snap, Board, Fighters);
  TestEqual(TEXT("restored: two moves"), Second.Moves.Num(), 2);
  TestTrue(TEXT("restored in order with the destinations"),
           Second.Moves.Num() == 2 && Second.Moves[0].FighterId == TEXT("a") && Second.Moves[0].DestX == 3 &&
               Second.Moves[1].FighterId == TEXT("b") && Second.Moves[1].DestY == 0);
  TestEqual(TEXT("restored boost"), Second.BoostCardId, FString(TEXT("c2")));
  TestTrue(TEXT("restored moves re-evaluated"), Second.Eval.IsConfirmable() && Second.Eval.NumOk == 2);
  int32 Restores = 0;
  TestTrue(TEXT("MS-DRAFT op=restore"), MsTraced(Second, TEXT("MS-DRAFT op=restore"), Restores));

  // Another match never restores this draft.
  Flow.SetRoomForTest(TEXT("g2"), ES08Stage::Started);
  TestFalse(TEXT("other match: no recall"), Flow.RecallManeuverDraft(ManeuverA, Cached));
  Flow.SetRoomForTest(TEXT("g1"), ES08Stage::Started);
  TestTrue(TEXT("back in the match: recall"), Flow.RecallManeuverDraft(ManeuverA, Cached));

  // ---- MS-E-53: a new seq with changed positions re-evaluates, never deletes ----
  {
    TestTrue(TEXT("+1 replaces +2"), Second.ToggleBoostCard(TEXT("c1"), Snap, Board, Fighters, Reason));
    // An enemy now stands on a's straight line: the detour is 5 steps -> NeedBoost.
    TArray<FS08BoardFighter> Moved = Fighters;
    Moved.Add(MsFighter(TEXT("e"), Opp, 1, 1));
    Second.OnSnapshot(MsSnapshot(Hand, ManeuverA, 6), Board, Moved);
    TestEqual(TEXT("both moves kept"), Second.Moves.Num(), 2);
    const FS09DraftMove* A = MsMove(Second, TEXT("a"));
    TestEqual(TEXT("longer path: NeedBoost, not Conflict"), MsStatus(A), FString(TEXT("needBoost")));
    TestEqual(TEXT("needs +2 (5 steps, movement 3, +1 selected)"), A ? A->RequiredBoost : -1, 2);
    TestEqual(TEXT("c1 still selected"), Second.BoostCardId, FString(TEXT("c1")));
    // An enemy now stands on a's destination: Conflict, kept.
    TArray<FS08BoardFighter> Blocked = Fighters;
    Blocked.Add(MsFighter(TEXT("e"), Opp, 3, 1));
    Second.OnSnapshot(MsSnapshot(Hand, ManeuverA, 7), Board, Blocked);
    TestEqual(TEXT("still two moves"), Second.Moves.Num(), 2);
    TestEqual(TEXT("enemy on the target: Conflict"), MsStatus(MsMove(Second, TEXT("a"))), FString(TEXT("conflict")));
    TestEqual(TEXT("why.cell.enemy"), MsMove(Second, TEXT("a")) ? MsKey(MsMove(Second, TEXT("a"))->Reason) : FString(),
              FString(TEXT("why.cell.enemy")));
  }

  // ---- MS-E-15: the boost card left the hand ----
  {
    Second.OnSnapshot(MsSnapshot({{TEXT("c2"), true, 2}}, ManeuverA, 8), Board, Fighters);
    TestTrue(TEXT("boost dropped"), Second.BoostCardId.IsEmpty());
    TestEqual(TEXT("why.boost.card.gone"), MsKey(Second.LastReason), FString(TEXT("why.boost.card.gone")));
    TestEqual(TEXT("moves kept"), Second.Moves.Num(), 2);
    TestTrue(TEXT("the cache follows (no boost)"), Flow.RecallManeuverDraft(ManeuverA, Cached) && Cached.BoostCardId.IsEmpty());
  }

  // ---- MS-E-41: a fighter that died leaves the draft ----
  {
    TArray<FS08BoardFighter> Dead = Fighters;
    Dead[1].Health = 0;
    Second.OnSnapshot(MsSnapshot(Hand, ManeuverA, 9), Board, Dead);
    TestEqual(TEXT("b's move dropped"), Second.MoveIndexOf(TEXT("b")), INDEX_NONE);
    TestEqual(TEXT("a's move kept"), Second.Moves.Num(), 1);
  }

  // ---- another maneuver id: the old draft never carries over ----
  {
    Second.OnSnapshot(MsSnapshot(Hand, TEXT("maneuver:2:12"), 12), Board, Fighters);
    TestEqual(TEXT("new id: empty draft"), Second.Moves.Num(), 0);
    TestTrue(TEXT("new id: no boost"), Second.BoostCardId.IsEmpty());
    TestEqual(TEXT("pending id switched"), Second.PendingManeuverId, FString(TEXT("maneuver:2:12")));
    TestFalse(TEXT("the old id is no longer cached"), Flow.RecallManeuverDraft(ManeuverA, Cached));
  }

  // ---- the maneuver closes / GAME_OVER: draft and cache gone ----
  {
    TestTrue(TEXT("draft on the new id"),
             Second.SetDestination(TEXT("a"), 1, 1, MsSnapshot(Hand, TEXT("maneuver:2:12"), 12), Board, Fighters, Reason));
    TestTrue(TEXT("cached"), Flow.RecallManeuverDraft(TEXT("maneuver:2:12"), Cached));
    Second.OnSnapshot(MsSnapshot(Hand, FString(), 13), Board, Fighters);
    TestTrue(TEXT("closed pending: mode none"), Second.Mode == ES09CommandMode::None);
    TestEqual(TEXT("closed pending: no moves"), Second.Moves.Num(), 0);
    TestFalse(TEXT("closed pending: cache cleared"), Flow.RecallManeuverDraft(TEXT("maneuver:2:12"), Cached));

    FS09CommandUi Third;
    Third.ViewerId = Me;
    MsBindCache(Third, Flow);
    Third.OnSnapshot(Snap, Board, Fighters);
    TestTrue(TEXT("third draft"), Third.SetDestination(TEXT("a"), 2, 1, Snap, Board, Fighters, Reason));
    FS08Snapshot Over = MsSnapshot(Hand, ManeuverA, 20);
    Over.Phase = TEXT("GAME_OVER");
    Third.OnSnapshot(Over, Board, Fighters);
    TestTrue(TEXT("GAME_OVER closes the draft"), Third.Mode == ES09CommandMode::None && Third.Moves.Num() == 0);
    TestFalse(TEXT("GAME_OVER clears the cache"), Flow.RecallManeuverDraft(ManeuverA, Cached));
  }

  // ---- MS-E-46: the maneuver ends into a discard (hand > 7) or a pending
  // choice: the draft is gone in that mode too, so is the cache ----
  for (int32 Kind = 0; Kind < 2; ++Kind) {
    FS09CommandUi Ui;
    Ui.ViewerId = Me;
    MsBindCache(Ui, Flow);
    Ui.OnSnapshot(Snap, Board, Fighters);
    TestTrue(TEXT("draft held"), Ui.SetDestination(TEXT("a"), 2, 1, Snap, Board, Fighters, Reason));
    TestTrue(TEXT("draft cached"), Flow.RecallManeuverDraft(ManeuverA, Cached));
    const FS08Snapshot Next = Kind == 0 ? MsDiscardSnapshot(Hand, 31) : MsPendingMoveSnapshot(2);
    Ui.OnSnapshot(Next, Board, Fighters);
    const TCHAR* Name = Kind == 0 ? TEXT("discard") : TEXT("pending choice");
    TestTrue(FString::Printf(TEXT("%s mode opens"), Name),
             Ui.Mode == (Kind == 0 ? ES09CommandMode::DiscardDraft : ES09CommandMode::PendingChoice));
    TestTrue(FString::Printf(TEXT("%s: no maneuver draft left"), Name),
             Ui.Moves.Num() == 0 && Ui.PendingManeuverId.IsEmpty() && Ui.BoostCardId.IsEmpty());
    TestFalse(FString::Printf(TEXT("%s: cache cleared"), Name), Flow.RecallManeuverDraft(ManeuverA, Cached));
  }

  // ---- a fresh UI whose first snapshot has no maneuver clears a stale cache ----
  {
    FS09CommandUi Old;
    Old.ViewerId = Me;
    MsBindCache(Old, Flow);
    Old.OnSnapshot(Snap, Board, Fighters);
    TestTrue(TEXT("old draft"), Old.SetDestination(TEXT("a"), 2, 1, Snap, Board, Fighters, Reason));
    TestTrue(TEXT("old draft cached"), Flow.RecallManeuverDraft(ManeuverA, Cached));
    FS09CommandUi Fresh;
    Fresh.ViewerId = Me;
    MsBindCache(Fresh, Flow);
    Fresh.OnSnapshot(MsSnapshot(Hand, FString(), 40), Board, Fighters);
    TestFalse(TEXT("closed maneuver seen by a fresh UI: cache cleared"), Flow.RecallManeuverDraft(ManeuverA, Cached));
  }

  // ---- MS-T-06 (MS-E-91, MS-E-92, MS-E-51): the stream reconnects, the
  // session is refreshed, the outcome is unknown - the command is never
  // resent and the draft stays ----
  {
    FS09CommandUi Ui;
    Ui.ViewerId = Me;
    Ui.OnSnapshot(Snap, Board, Fighters);
    TestTrue(TEXT("draft for the network cases"), Ui.SetDestination(TEXT("a"), 3, 1, Snap, Board, Fighters, Reason));
    TArray<FS08ManeuverMove> Moves;
    FS08ManeuverMove& Step = Moves.AddDefaulted_GetRef();
    Step.FighterId = TEXT("f-0-sk0");
    Step.Path = {FIntPoint(0, 2)};

    FS08FlowController Down(TEXT("http://127.0.0.1:9/graphql"), TEXT("ws://127.0.0.1:9/graphql"), LiveHost);
    FS08Snapshot LiveSnap;
    if (!MsLiveFlow(Down, LiveSnap)) {
      AddError(TEXT("fixture 04 / live stream not ready"));
      return true;
    }
    Down.DropWsForTest();
    TestFalse(TEXT("stream reconnecting: confirm inactive"), Down.SubmitManeuver(TEXT("maneuver:1:5"), Moves));
    TestEqual(TEXT("stream reconnecting: why.syncing"), Down.GameplayGateKey().ToString(), FString(TEXT("why.syncing")));
    TestEqual(TEXT("stream reconnecting: nothing sent"), Down.CountHttpSendsForTest(MsManeuverDoc), 0);
    TestEqual(TEXT("stream reconnecting: the draft stays"), Ui.Moves.Num(), 1);

    FS08FlowController Auth(TEXT("http://127.0.0.1:9/graphql"), TEXT("ws://127.0.0.1:9/graphql"), LiveHost);
    FMsFlowCapture AuthCap;
    AuthCap.Bind(Auth);
    Auth.SetAuthForTest(TEXT("access-1"), TEXT("refresh-1"));
    if (MsLiveFlow(Auth, LiveSnap)) {
      Auth.QueueHttpResultForTest(false, {FS08GraphQLError{TEXT("AUTH"), TEXT("HTTP 401 from server"), FString(), 401}});
      Auth.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true); // the refresh: never delivered
      TestTrue(TEXT("auth: dispatched"), Auth.SubmitManeuver(TEXT("maneuver:1:5"), Moves));
      TestEqual(TEXT("auth: one refresh"), Auth.CountHttpSendsForTest(TEXT("refreshTokens(")), 1);
      TestEqual(TEXT("auth: the command is not resent"), Auth.CountHttpSendsForTest(MsManeuverDoc), 1);
      TestTrue(TEXT("auth: why.auth.refreshed (class И)"),
               AuthCap.Rejections.Num() == 1 && AuthCap.Rejections[0].WhyKey == FName(TEXT("why.auth.refreshed")) &&
                   AuthCap.Rejections[0].Class == ES08RejectClass::Fixable);
      TestEqual(TEXT("auth: the banner text"), FS09Reason::Make(TEXT("why.auth.refreshed")).Text(),
                FString(TEXT("Session refreshed — confirm again")));
      TestEqual(TEXT("auth: the draft stays"), Ui.Moves.Num(), 1);
    } else {
      AddError(TEXT("live stream not ready (auth)"));
    }

    FS08FlowController Lost(TEXT("http://127.0.0.1:9/graphql"), TEXT("ws://127.0.0.1:9/graphql"), LiveHost);
    if (MsLiveFlow(Lost, LiveSnap)) {
      Lost.QueueHttpResultForTest(false, {FS08GraphQLError{TEXT("TRANSPORT"), TEXT("lost"), FString()}});
      Lost.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true); // the recovery read
      TestTrue(TEXT("lost: dispatched"), Lost.SubmitManeuver(TEXT("maneuver:1:5"), Moves));
      TestTrue(TEXT("lost: recovery lock"), Lost.IsMutationRecoveryActiveForTest());
      TestFalse(TEXT("lost: a second confirm is refused"), Lost.SubmitManeuver(TEXT("maneuver:1:5"), Moves));
      TestEqual(TEXT("lost: 0 resends"), Lost.CountHttpSendsForTest(MsManeuverDoc), 1);
    } else {
      AddError(TEXT("live stream not ready (lost)"));
    }
  }
  return true;
}


// DE-015 (W-22, SD-44 / SD-47; 03 §5 MS-R-79, MS-AT-15 case DE-015): the own
// turn takes input from the applied snapshot that handed it over - the first
// click (pressed before the snapshot or after it, released in that frame) is
// accepted, n = 20 per hold; an earlier click is answered, never lost; the END
// TURN button and the E key answer why.actions.remaining {n} before both
// actions (one function), the other blockers by key; no pass binding; the
// TURN-INPUT trace pair.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelTurnStartInputTest, "Unmatched.S09.MoveSel.TurnStartInput",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelTurnStartInputTest::RunTest(const FString&) {
  const FS08BoardModel Board = MsGrid(6, 3);
  const TArray<FMsCard> Hand = {{TEXT("c2"), true, 2}, {TEXT("c1"), true, 1}};
  const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 0, 1, 2.0), MsFighter(TEXT("b"), Me, 5, 1, 2.0),
                                             MsFighter(TEXT("e"), Opp, 5, 0)};
  // A fresh body (own metadata object) of Player's turn; Actions < 0 = no actionsRemaining field.
  auto Turn = [&](const TCHAR* Player, int32 Actions, int32 Seq, const TCHAR* Phase = TEXT("ACTION_MANEUVER")) {
    FS08Snapshot Snap = MsTurnSnapshot(Hand, Seq);
    Snap.CurrentTurnPlayerId = Player;
    Snap.Phase = Phase;
    TSharedRef<FJsonObject> Meta = MakeShared<FJsonObject>();
    if (Actions >= 0) Meta->SetNumberField(TEXT("actionsRemaining"), Actions);
    Snap.Metadata = MakeShared<FJsonValueObject>(Meta);
    return Snap;
  };
  constexpr int32 N = 20;
  constexpr uint64 ApplyFrame = 100;

  // ---- the first click of the own turn, in the frame of the snapshot ----
  for (const bool bHold : {false, true}) {
    const TCHAR* HoldTag = bHold ? TEXT("pressed before the snapshot") : TEXT("pressed after it");
    int32 Accepted = 0;
    for (int32 K = 0; K < N; ++K) {
      const FS08Snapshot Before = Turn(Opp, 2, 10 + 2 * K);
      FS09CommandUi Ui = MsOpen(Before, Board, Fighters);
      FS09MoveInput In;
      FS09TurnInputWatch Watch;
      FS09HudModel Hud;
      Hud.Build(Before, Me, TSet<FString>(), Before.SequenceNumber, Before.SequenceNumber);
      const bool bNoOpen =
          Watch.OnApplied(Hud.bViewerTurn, Hud.bGameOver, Before.SequenceNumber, ApplyFrame - 5).IsEmpty();
      if (bHold) In.OnPointerPressed(FIntPoint(0, 1), TEXT("a"));
      // The snapshot that hands the turn over - fed exactly as HandleApplied does.
      const FS08Snapshot Mine = Turn(Me, 2, Before.SequenceNumber + 1);
      Ui.OnSnapshot(Mine, Board, Fighters);
      In.OnSnapshot(Ui, Mine);
      Hud.Build(Mine, Me, TSet<FString>(), Mine.SequenceNumber, Mine.SequenceNumber);
      const FString Open = Watch.OnApplied(Hud.bViewerTurn, Hud.bGameOver, Mine.SequenceNumber, ApplyFrame);
      if (!bHold) In.OnPointerPressed(FIntPoint(0, 1), TEXT("a"));
      const FS09InputResult R = In.OnPointerReleased(FIntPoint(0, 1), TEXT("a"), Ui, Mine, Board, Fighters);
      const bool bAct = R.bHandled && !R.Toast.IsSet() && R.bSelectionChanged && Ui.SelectedFighterId == TEXT("a");
      const FString First = Watch.NoteInput(TEXT("board"), TEXT("a"), bAct, R.Toast, ApplyFrame);
      FString BeginWhy;
      FS09Reason BeginKey;
      const bool bBegin = Ui.CanBeginManeuver(Mine, BeginWhy, BeginKey);
      const bool bOk = bNoOpen && bAct && bBegin && Open.StartsWith(TEXT("TURN-INPUT open seq=")) &&
                       Open.EndsWith(TEXT("frame=100 gate=none")) &&
                       First.StartsWith(TEXT("TURN-INPUT first src=board id=a result=act frame=100 open=100")) &&
                       First.EndsWith(TEXT("dframes=0"));
      Accepted += bOk ? 1 : 0;
      if (!bOk && K == 0) {
        AddInfo(FString::Printf(TEXT("%s | %s | begin=%d %s"), *Open, *First, bBegin ? 1 : 0, *BeginWhy));
      }
    }
    TestEqual(FString::Printf(TEXT("first click of the own turn, %s: accepted in the apply frame"), HoldTag), Accepted,
              N);
  }

  // ---- a click before the turn is answered (SD-47 / UI-INP-011), never lost ----
  {
    const FS08Snapshot Before = Turn(Opp, 2, 60);
    FS09CommandUi Ui = MsOpen(Before, Board, Fighters);
    FS09MoveInput In;
    const FS09InputResult Early = MsClick(In, Ui, Before, Board, Fighters, FIntPoint(2, 2));
    TestTrue(TEXT("an empty space before the turn: why.not.your.turn"),
             Early.bHandled && Early.Toast.Key == FName(TEXT("why.not.your.turn")));
    TestEqual(TEXT("END TURN / E before the turn: why.not.your.turn"), MsKey(Ui.EndTurnReason(Before)),
              FString(TEXT("why.not.your.turn")));
  }

  // ---- END TURN and E: one answer by key ----
  {
    const FS08Snapshot Two = Turn(Me, 2, 70);
    FS09CommandUi Ui = MsOpen(Two, Board, Fighters);
    const FS09Reason Remaining = Ui.EndTurnReason(Two);
    TestEqual(TEXT("2 actions left: why.actions.remaining"), MsKey(Remaining), FString(TEXT("why.actions.remaining")));
    TestEqual(TEXT("... {n} = 2"), Remaining.Args.FindRef(TEXT("n")), FString(TEXT("2")));
    const FS08Snapshot One = Turn(Me, 1, 71, TEXT("ACTION_ATTACK"));
    Ui.OnSnapshot(One, Board, Fighters);
    TestEqual(TEXT("1 action left: {n} = 1"), Ui.EndTurnReason(One).Args.FindRef(TEXT("n")), FString(TEXT("1")));
    const FS08Snapshot Zero = Turn(Me, 0, 72, TEXT("ACTION_ATTACK"));
    Ui.OnSnapshot(Zero, Board, Fighters);
    TestFalse(TEXT("both actions spent, action phase: endTurn is sent"), Ui.EndTurnReason(Zero).IsSet());
    const FS08Snapshot Unknown = Turn(Me, -1, 73, TEXT("ACTION_ATTACK"));
    Ui.OnSnapshot(Unknown, Board, Fighters);
    TestEqual(TEXT("actionsRemaining unknown: why.syncing"), MsKey(Ui.EndTurnReason(Unknown)),
              FString(TEXT("why.syncing")));
    const FS08Snapshot TurnEnd = Turn(Me, 0, 74, TEXT("TURN_END"));
    Ui.OnSnapshot(TurnEnd, Board, Fighters);
    TestEqual(TEXT("no action phase (network guard): why.syncing"), MsKey(Ui.EndTurnReason(TurnEnd)),
              FString(TEXT("why.syncing")));
    Ui.OnSnapshot(Zero, Board, Fighters);
    Ui.bCommandInFlight = true;
    TestEqual(TEXT("in flight: why.syncing"), MsKey(Ui.EndTurnReason(Zero)), FString(TEXT("why.syncing")));
    Ui.bCommandInFlight = false;
    Ui.bHasPendingChoice = true;
    Ui.PendingChoice.PlayerId = Opp;
    TestEqual(TEXT("the opponent's pending choice: why.wait.opponent.choice"), MsKey(Ui.EndTurnReason(Zero)),
              FString(TEXT("why.wait.opponent.choice")));
    Ui.PendingChoice.PlayerId = Me;
    TestEqual(TEXT("own pending choice: why.choice.required"), MsKey(Ui.EndTurnReason(Zero)),
              FString(TEXT("why.choice.required")));
    Ui.bHasPendingChoice = false;
    const FS08Snapshot Over = Turn(Me, 0, 75, TEXT("GAME_OVER"));
    TestEqual(TEXT("the duel is over: why.state.changed"), MsKey(Ui.EndTurnReason(Over)),
              FString(TEXT("why.state.changed")));
    // An open pendingManeuver (the draft) answers why.draft.open before the action count.
    const FS08Snapshot Draft = MsSnapshot(Hand, ManeuverA, 76);
    FS09CommandUi DraftUi = MsOpen(Draft, Board, Fighters);
    TestEqual(TEXT("maneuver draft open: why.draft.open"), MsKey(DraftUi.EndTurnReason(Draft)),
              FString(TEXT("why.draft.open")));
    for (const TCHAR* Key : {TEXT("why.actions.remaining"), TEXT("why.not.your.turn"), TEXT("why.draft.open"),
                             TEXT("why.discard.count"), TEXT("why.wait.opponent.choice"), TEXT("why.choice.required"),
                             TEXT("why.wait.defender"), TEXT("why.syncing"), TEXT("why.state.changed")}) {
      TestTrue(FString::Printf(TEXT("%s in the EN table"), Key), S08WhyText::Has(FName(Key)));
    }
  }

  // ---- no pass: E ends the turn, no binding passes (SD-44, PASS_NOT_ALLOWED) ----
  {
    bool bE = false;
    bool bPass = false;
    for (const FS09KeyBinding& Binding : FS09MoveInput::Bindings()) {
      const FString Action = FString(Binding.Action).ToLower();
      bE |= FCString::Strcmp(Binding.Input, TEXT("E")) == 0 && Action.StartsWith(TEXT("end turn"));
      bPass |= Action.Contains(TEXT("pass"));
    }
    TestTrue(TEXT("E is the end-turn key"), bE);
    TestFalse(TEXT("no pass binding"), bPass);
  }

  // ---- the TURN-INPUT watch ----
  {
    FS09TurnInputWatch Watch;
    TestTrue(TEXT("opponent's turn: nothing"), Watch.OnApplied(false, false, 1, 10).IsEmpty());
    TestTrue(TEXT("no watch: no first line"), Watch.NoteInput(TEXT("hud"), TEXT("x"), true, FS09Reason(), 11).IsEmpty());
    TestFalse(TEXT("the turn handed over: open"), Watch.OnApplied(true, false, 2, 12).IsEmpty());
    TestTrue(TEXT("an equal-seq merge of the same turn: no second open"), Watch.OnApplied(true, false, 2, 13).IsEmpty());
    const FString Refused = Watch.NoteInput(TEXT("hud"), TEXT("hud.end.turn"), false,
                                            FS09Reason::Make(TEXT("why.actions.remaining")), 15);
    TestEqual(TEXT("first input refused with its key"), Refused,
              FString(TEXT("TURN-INPUT first src=hud id=hud.end.turn result=refused frame=15 open=12 dframes=3 "
                           "why=why.actions.remaining")));
    TestTrue(TEXT("only the first input is traced"),
             Watch.NoteInput(TEXT("board"), TEXT("a"), true, FS09Reason(), 16).IsEmpty());
    Watch.OnApplied(false, false, 3, 20);
    Watch.OnApplied(true, false, 4, 30);
    TestTrue(TEXT("the next own turn opens again"), Watch.IsOpen());
    Watch.OnApplied(true, true, 5, 31);
    TestFalse(TEXT("the result screen closes it"), Watch.IsOpen());
  }
  return true;
}

#endif // WITH_AUTOMATION_TESTS

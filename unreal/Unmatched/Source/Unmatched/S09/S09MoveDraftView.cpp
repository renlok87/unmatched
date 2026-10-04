#include "S09MoveDraftView.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"

namespace S09MoveDraftView {

FS08MoveDraftInput BuildInput(const FS09CommandUi& Ui, const FS08BoardModel& Board,
                              const TArray<FS08BoardFighter>& Fighters) {
  FS08MoveDraftInput In;
  In.ViewerId = Ui.ViewerId;
  In.Source = Ui.Mode == ES09CommandMode::ManeuverDraft ? TEXT("draft")
              : Ui.Mode == ES09CommandMode::PendingChoice ? TEXT("pending")
                                                          : TEXT("inspect");
  auto PositionOf = [&Fighters](const FString& Id) {
    for (const FS08BoardFighter& F : Fighters) {
      if (F.Id == Id) return FIntPoint(F.X, F.Y);
    }
    return FIntPoint(-1, -1);
  };
  // MS-S-12: the legal spaces of a pending MOVE / PLACE head of this viewer (V-11 / V-12; MS-T-12 adds the rest)
  if (Ui.Mode == ES09CommandMode::PendingChoice) {
    if (Ui.bHasPendingChoice && (Ui.PendingChoice.Type == TEXT("MOVE") || Ui.PendingChoice.Type == TEXT("PLACE"))) {
      In.bPending = true;
      In.bPendingPlace = Ui.PendingChoice.Type == TEXT("PLACE");
      In.PendingCells = Ui.PendingCells;
    }
    return In;
  }
  // V-01 / V-02 of the selected fighter (draft MS-S-06/07, or the MS-S-02 inspection before the draw)
  const FS09ReachTiers& Tiers = Ui.SelectedTiers;
  if (!Ui.SelectedFighterId.IsEmpty() && Tiers.bValid && Tiers.FighterId == Ui.SelectedFighterId) {
    In.SelectedFighterId = Ui.SelectedFighterId;
    In.SelectedStart = Tiers.Start;
    In.BaseTier = Tiers.BaseTier;
    for (const FIntPoint& Cell : Tiers.BoostTier) In.BoostTier.Emplace(Cell, Tiers.ChipAt(Cell));
    In.MarkRange = FMath::Max(Tiers.BaseSteps, Tiers.BoostSteps);
  }
  if (Ui.Mode == ES09CommandMode::ManeuverDraft) {
    for (int32 I = 0; I < Ui.Moves.Num(); ++I) {
      const FS09DraftMove& Move = Ui.Moves[I];
      FS08MoveDraftInput::FMove& Out = In.Moves.AddDefaulted_GetRef();
      Out.FighterId = Move.FighterId;
      Out.Dest = FIntPoint(Move.DestX, Move.DestY);
      Out.Order = Move.Order;
      Out.Status = Move.Status == ES09DraftMoveStatus::Conflict    ? FS08MoveDraftInput::EMoveStatus::Conflict
                   : Move.Status == ES09DraftMoveStatus::NeedBoost ? FS08MoveDraftInput::EMoveStatus::NeedBoost
                                                                   : FS08MoveDraftInput::EMoveStatus::Ok;
      Out.RequiredBoost = Move.RequiredBoost;
      Out.Path = Move.Path;
      // the start on the positions before this move (the sequential evaluation), else the snapshot position
      Out.Start = Ui.Eval.Tiers.IsValidIndex(I) && Ui.Eval.Tiers[I].bValid ? Ui.Eval.Tiers[I].Start
                                                                             : PositionOf(Move.FighterId);
    }
    In.bSent = Ui.bCommandInFlight;
    // V-17 (DE-017, MS-R-75): MS-S-06 - no fighter selected, the draft not sent - rings under every own fighter that
    // may move; they go out in the frame a fighter is selected (and stay out while the maneuver is in flight)
    if (Ui.SelectedFighterId.IsEmpty() && !Ui.bCommandInFlight) In.CandidateFighterIds = Ui.MovableFighterIds(Fighters);
  } else if (Ui.Mode == ES09CommandMode::None && Ui.PreDraft.bSet) {
    // MS-S-03: the pre-draft target is a destination (V-04 / V-04b) before the maneuver began
    FS08MoveDraftInput::FMove& Out = In.Moves.AddDefaulted_GetRef();
    Out.FighterId = Ui.PreDraft.FighterId;
    Out.Start = PositionOf(Ui.PreDraft.FighterId);
    Out.Dest = FIntPoint(Ui.PreDraft.X, Ui.PreDraft.Y);
    Out.Status = Ui.PreDraft.Status == ES09DraftMoveStatus::NeedBoost ? FS08MoveDraftInput::EMoveStatus::NeedBoost
                                                                      : FS08MoveDraftInput::EMoveStatus::Ok;
    Out.RequiredBoost = Ui.PreDraft.RequiredBoost;
  }
  (void)Board;
  return In;
}

}  // namespace S09MoveDraftView

namespace S09MoveDraftBench {

bool FCellRef::Resolve(const FS08BoardModel& Board, FIntPoint& Out) const {
  if (!bSet) return false;
  if (!SpaceId.IsEmpty()) {
    for (const FS08Cell& C : Board.Cells) {
      if (C.SpaceId == SpaceId && Board.IsBoardSpace(C.X, C.Y)) {
        Out = FIntPoint(C.X, C.Y);
        return true;
      }
    }
    return false;
  }
  if (!Board.IsBoardSpace(Cell.X, Cell.Y)) return false;
  Out = Cell;
  return true;
}

FString FCellRef::Describe() const {
  if (!bSet) return TEXT("-");
  return SpaceId.IsEmpty() ? FString::Printf(TEXT("[%d,%d]"), Cell.X, Cell.Y) : SpaceId;
}

namespace {
bool ReadCell(const TSharedPtr<FJsonValue>& Value, FCellRef& Out) {
  if (!Value.IsValid()) return false;
  FString Text;
  if (Value->TryGetString(Text) && !Text.IsEmpty()) {
    Out.SpaceId = Text;
    Out.bSet = true;
    return true;
  }
  const TArray<TSharedPtr<FJsonValue>>* Pair = nullptr;
  double X = 0.0, Y = 0.0;
  if (Value->TryGetArray(Pair) && Pair && Pair->Num() == 2 && (*Pair)[0]->TryGetNumber(X) && (*Pair)[1]->TryGetNumber(Y) &&
      X == FMath::RoundToDouble(X) && Y == FMath::RoundToDouble(Y)) {
    Out.Cell = FIntPoint(static_cast<int32>(X), static_cast<int32>(Y));
    Out.bSet = true;
    return true;
  }
  return false;
}
}  // namespace

bool Parse(const FString& Text, const FString& FileName, FFixture& Out, TArray<FString>& OutErrors) {
  const int32 ErrorsBefore = OutErrors.Num();
  Out = FFixture();
  Out.File = FileName;
  TSharedPtr<FJsonObject> Root;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(Text, Root, Problem) || !Root.IsValid()) {
    OutErrors.Add(TEXT("invalid JSON: ") + Problem);
    return false;
  }
  FString Schema;
  if (!Root->TryGetStringField(TEXT("schema"), Schema) || Schema != TEXT("unmatched.move-draft/1")) {
    OutErrors.Add(FString::Printf(TEXT("schema '%s' is not unmatched.move-draft/1"), *Schema));
    return false;
  }
  static const TSet<FString> Known = {TEXT("schema"), TEXT("board"),   TEXT("benchFixture"), TEXT("scene"),
                                      TEXT("selected"), TEXT("hover"), TEXT("boostCardId"),  TEXT("moves"),
                                      TEXT("moveOrder"), TEXT("lastMovement"), TEXT("pending")};
  for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Root->Values) {
    if (!Known.Contains(Pair.Key) && !Pair.Key.StartsWith(TEXT("note"))) {
      OutErrors.Add(FString::Printf(TEXT("unknown field '%s'"), *Pair.Key));
    }
  }
  Root->TryGetStringField(TEXT("board"), Out.Board);
  Root->TryGetStringField(TEXT("benchFixture"), Out.BenchFixture);
  Root->TryGetStringField(TEXT("scene"), Out.Scene);
  Root->TryGetStringField(TEXT("selected"), Out.Selected);
  Root->TryGetStringField(TEXT("boostCardId"), Out.BoostCardId);
  if (Root->HasField(TEXT("hover")) && !ReadCell(Root->TryGetField(TEXT("hover")), Out.Hover)) {
    OutErrors.Add(TEXT("hover must be a space id or [x, y]"));
  }
  const TArray<TSharedPtr<FJsonValue>>* Moves = nullptr;
  if (Root->HasField(TEXT("moves"))) {
    if (!Root->TryGetArrayField(TEXT("moves"), Moves) || !Moves) {
      OutErrors.Add(TEXT("moves must be an array"));
    } else {
      for (const TSharedPtr<FJsonValue>& V : *Moves) {
        const TSharedPtr<FJsonObject>* Obj = nullptr;
        FFixture::FMove Move;
        if (!V.IsValid() || !V->TryGetObject(Obj) || !Obj || !(*Obj)->TryGetStringField(TEXT("fighterId"), Move.FighterId) ||
            Move.FighterId.IsEmpty() || !ReadCell((*Obj)->TryGetField(TEXT("to")), Move.To)) {
          OutErrors.Add(TEXT("every move needs fighterId and to (space id or [x, y])"));
          continue;
        }
        Out.Moves.Add(Move);
      }
    }
  }
  const TArray<TSharedPtr<FJsonValue>>* Orders = nullptr;
  if (Root->HasField(TEXT("moveOrder"))) {
    if (!Root->TryGetArrayField(TEXT("moveOrder"), Orders) || !Orders) {
      OutErrors.Add(TEXT("moveOrder must be an array"));
    } else {
      for (const TSharedPtr<FJsonValue>& V : *Orders) {
        const TSharedPtr<FJsonObject>* Obj = nullptr;
        FFixture::FOrder Order;
        double Delta = 0.0;
        if (!V.IsValid() || !V->TryGetObject(Obj) || !Obj || !(*Obj)->TryGetStringField(TEXT("fighterId"), Order.FighterId) ||
            !(*Obj)->TryGetNumberField(TEXT("delta"), Delta) || (Delta != 1.0 && Delta != -1.0)) {
          OutErrors.Add(TEXT("every moveOrder entry needs fighterId and delta -1 | 1"));
          continue;
        }
        Order.Delta = static_cast<int32>(Delta);
        Out.MoveOrder.Add(Order);
      }
    }
  }
  for (const TCHAR* Reserved : {TEXT("lastMovement"), TEXT("pending")}) {
    if (Root->HasField(Reserved)) Out.Skipped.Add(Reserved);
  }
  return OutErrors.Num() == ErrorsBefore;
}

FApplyResult Apply(const FFixture& Fixture, const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                   const TArray<FS08BoardFighter>& Fighters, const FString& ViewerId, FS09CommandUi& Ui) {
  FApplyResult R;
  auto HasFighter = [&Fighters](const FString& Id) {
    return Fighters.ContainsByPredicate([&Id](const FS08BoardFighter& F) { return F.Id == Id; });
  };
  // every id must come from the bench fixture (06 §6.2): otherwise no draft, no frame
  TArray<FString> Ids;
  if (!Fixture.Selected.IsEmpty()) Ids.Add(Fixture.Selected);
  for (const FFixture::FMove& Move : Fixture.Moves) Ids.Add(Move.FighterId);
  for (const FFixture::FOrder& Order : Fixture.MoveOrder) Ids.Add(Order.FighterId);
  for (const FString& Id : Ids) {
    if (!HasFighter(Id)) {
      R.MismatchId = Id;
      R.Error = FString::Printf(TEXT("fighter %s is not in the bench fixture"), *Id);
      return R;
    }
  }
  // the synthesised pendingManeuver of the viewer on top of the fixture's metadata
  R.Snapshot = Snapshot;
  const TSharedPtr<FJsonObject> Meta = MakeShared<FJsonObject>();
  if (Snapshot.Metadata.IsValid() && Snapshot.Metadata->Type == EJson::Object && Snapshot.Metadata->AsObject().IsValid()) {
    for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Snapshot.Metadata->AsObject()->Values) {
      Meta->SetField(Pair.Key, Pair.Value);
    }
  }
  const TSharedPtr<FJsonObject> Pending = MakeShared<FJsonObject>();
  Pending->SetStringField(TEXT("id"), TEXT("bench:") + Fixture.File);
  Pending->SetStringField(TEXT("playerId"), ViewerId);
  Meta->SetObjectField(TEXT("pendingManeuver"), Pending);
  R.Snapshot.Metadata = MakeShared<FJsonValueObject>(Meta);
  const FS08Snapshot& Snap = R.Snapshot;
  Ui.ViewerId = ViewerId;
  Ui.bCommandInFlight = false;
  Ui.DraftSource = ES09InputSource::Auto;
  Ui.OnSnapshot(Snap, Board, Fighters);
  if (Ui.Mode != ES09CommandMode::ManeuverDraft) {
    R.Error = TEXT("the synthesised pendingManeuver did not open a draft");
    return R;
  }
  if (!Fixture.BoostCardId.IsEmpty()) {
    const TArray<FS09BoostCard> Hand = FS09DraftEval::BoostHand(Snap, ViewerId);
    if (!Hand.ContainsByPredicate([&](const FS09BoostCard& C) { return C.InstanceId == Fixture.BoostCardId; })) {
      R.MismatchId = Fixture.BoostCardId;
      R.Error = FString::Printf(TEXT("card %s is not in the viewer's hand of the bench fixture"), *Fixture.BoostCardId);
      return R;
    }
    FString Reason;
    if (!Ui.ToggleBoostCard(Fixture.BoostCardId, Snap, Board, Fighters, Reason)) {
      R.Error = FString::Printf(TEXT("boost %s refused: %s"), *Fixture.BoostCardId, *Reason);
      return R;
    }
  }
  for (const FFixture::FMove& Move : Fixture.Moves) {
    FIntPoint To;
    if (!Move.To.Resolve(Board, To)) {
      R.Error = FString::Printf(TEXT("move %s: %s is not a board space"), *Move.FighterId, *Move.To.Describe());
      return R;
    }
    FString Reason;
    if (!Ui.SetDestination(Move.FighterId, To.X, To.Y, Snap, Board, Fighters, Reason)) {
      R.Error = FString::Printf(TEXT("move %s -> %s refused: %s"), *Move.FighterId, *Move.To.Describe(), *Reason);
      return R;
    }
  }
  for (const FFixture::FOrder& Order : Fixture.MoveOrder) {
    if (!Ui.MoveOrder(Order.FighterId, Order.Delta, Snap, Board, Fighters)) {
      R.Error = FString::Printf(TEXT("moveOrder %s %+d refused"), *Order.FighterId, Order.Delta);
      return R;
    }
  }
  if (!Fixture.Selected.IsEmpty()) {
    if (!Ui.SelectFighter(Fixture.Selected, Snap, Board, Fighters)) {
      R.Error = FString::Printf(TEXT("select %s refused: %s"), *Fixture.Selected, *Ui.LastReason.Describe());
      return R;
    }
  } else {
    Ui.DeselectFighter();
  }
  if (Fixture.Hover.bSet && !Fixture.Hover.Resolve(Board, R.Hover)) {
    R.Error = FString::Printf(TEXT("hover %s is not a board space"), *Fixture.Hover.Describe());
    return R;
  }
  R.bOk = true;
  R.Summary = FString::Printf(
      TEXT("MS-BENCH draft file=%s scene=%s board=%s moves=%d ok=%d needBoost=%d conflict=%d boost=%s selected=%s ")
      TEXT("baseTier=%d boostTier=%d hover=%s skipped=%s"),
      *Fixture.File, Fixture.Scene.IsEmpty() ? TEXT("-") : *Fixture.Scene, Fixture.Board.IsEmpty() ? TEXT("-") : *Fixture.Board,
      Ui.Moves.Num(), Ui.Eval.NumOk, Ui.Eval.NumNeedBoost, Ui.Eval.NumConflict,
      Ui.BoostCardId.IsEmpty() ? TEXT("-") : *Ui.BoostCardId,
      Ui.SelectedFighterId.IsEmpty() ? TEXT("-") : *Ui.SelectedFighterId, Ui.SelectedTiers.BaseTier.Num(),
      Ui.SelectedTiers.BoostTier.Num(), R.Hover.X >= 0 ? *Board.CellLabel(R.Hover.X, R.Hover.Y) : TEXT("-"),
      Fixture.Skipped.Num() > 0 ? *FString::Join(Fixture.Skipped, TEXT("+")) : TEXT("-"));
  return R;
}

}  // namespace S09MoveDraftBench

#include "S08BoardModel.h"
#include "Dom/JsonObject.h"

namespace {
ES08CellType ParseCellType(const FString& Type) {
  if (Type == TEXT("normal")) return ES08CellType::Normal;
  if (Type == TEXT("wall")) return ES08CellType::Wall;
  if (Type == TEXT("obstacle")) return ES08CellType::Obstacle;
  if (Type == TEXT("door")) return ES08CellType::Door;
  return ES08CellType::Unknown;
}
} // namespace

bool FS08BoardModel::Decode(const TSharedPtr<FJsonValue>& BoardState) {
  Width = Height = 0;
  Cells.Reset();
  const TSharedPtr<FJsonObject> Board = BoardState.IsValid() ? BoardState->AsObject() : nullptr;
  if (!Board.IsValid()) return false;

  bool Present = false;
  int32 W = 0, H = 0;
  if (!FS08Contracts::ReadIntLike(Board.ToSharedRef(), TEXT("width"), W, Present) || !Present ||
      !FS08Contracts::ReadIntLike(Board.ToSharedRef(), TEXT("height"), H, Present) || !Present) {
    return false;
  }
  if (W <= 0 || H <= 0 || W > 1000 || H > 1000) return false;

  const TSharedPtr<FJsonValue> CellsField = Board->TryGetField(TEXT("cells"));
  const TArray<TSharedPtr<FJsonValue>>* Rows = nullptr;
  if (!CellsField.IsValid() || CellsField->IsNull() ||
      !CellsField->TryGetArray(Rows) || !Rows) {
    return false;
  }

  // Doors: {"x,y": true(open)|false(closed)} or {"x:y": ...}; either key
  // form is accepted, values only ever flip door openness.
  TMap<FString, bool> DoorStates;
  const TSharedPtr<FJsonValue> DoorsField = Board->TryGetField(TEXT("doors"));
  const TSharedPtr<FJsonObject> Doors = DoorsField.IsValid() ? DoorsField->AsObject() : nullptr;
  if (Doors.IsValid()) {
    for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Doors->Values) {
      bool bOpen = true;
      if (Pair.Value.IsValid() && !Pair.Value->IsNull()) {
        Pair.Value->TryGetBool(bOpen);
      }
      DoorStates.Add(Pair.Key.Replace(TEXT(":"), TEXT(",")), bOpen);
    }
  }

  Width = W;
  Height = H;
  Cells.Init(FS08Cell(), W * H);
  for (int32 Y = 0; Y < Rows->Num() && Y < H; ++Y) {
    const TArray<TSharedPtr<FJsonValue>>* Row = nullptr;
    if (!(*Rows)[Y].IsValid() || !(*Rows)[Y]->TryGetArray(Row) || !Row) continue;
    for (int32 X = 0; X < Row->Num() && X < W; ++X) {
      const TSharedPtr<FJsonObject>* CellObject = nullptr;
      if (!(*Row)[X].IsValid() || !(*Row)[X]->TryGetObject(CellObject) || !CellObject->IsValid()) {
        continue; // holes stay Unknown = impassable (backend isInBoardBounds analog)
      }
      FS08Cell& Cell = Cells[Y * W + X];
      Cell.X = X;
      Cell.Y = Y;
      Cell.Type = ParseCellType((*CellObject)->GetStringField(TEXT("type")));
      const TArray<TSharedPtr<FJsonValue>>* Zones = nullptr;
      if ((*CellObject)->TryGetArrayField(TEXT("zones"), Zones) && Zones) {
        for (const TSharedPtr<FJsonValue>& Zone : *Zones) {
          FString Name;
          if (Zone.IsValid() && Zone->TryGetString(Name)) Cell.Zones.Add(Name);
        }
      }
      if (Cell.Type == ES08CellType::Door) {
        bool bOpen = true;
        (*CellObject)->TryGetBoolField(TEXT("isOpen"), bOpen);
        const FString Key = FString::Printf(TEXT("%d,%d"), X, Y);
        if (bool* FromMap = DoorStates.Find(Key)) bOpen = *FromMap;
        Cell.bIsOpen = bOpen;
      }
    }
  }
  return true;
}

const FS08BoardFighter* FS08BoardModel::FighterAt(const TArray<FS08BoardFighter>& Fighters,
                                                  int32 X, int32 Y,
                                                  const FString& IgnoreFighterId) {
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (Fighter.Id == IgnoreFighterId || !Fighter.IsAlive()) continue;
    if (Fighter.X == X && Fighter.Y == Y) return &Fighter;
  }
  return nullptr;
}

bool FS08BoardModel::IsStepTraversable(const FS08BoardModel& Board,
                                       const TArray<FS08BoardFighter>& Fighters,
                                       const FS08BoardFighter& Mover, int32 X, int32 Y) {
  const FS08Cell* Cell = Board.CellAt(X, Y);
  if (!Cell || !Cell->IsPassable()) return false;
  const FS08BoardFighter* Blocker = FighterAt(Fighters, X, Y, Mover.Id);
  if (Blocker && Blocker->OwnerId != Mover.OwnerId) return false; // living enemy blocks
  return true;
}

bool FS08BoardModel::IsEndpointFree(const TArray<FS08BoardFighter>& Fighters,
                                    const FS08BoardFighter& Mover, int32 X, int32 Y) {
  return FighterAt(Fighters, X, Y, Mover.Id) == nullptr;
}

TSet<uint64> FS08BoardModel::ComputeReachableCells(const FS08BoardModel& Board,
                                                   const TArray<FS08BoardFighter>& Fighters,
                                                   const FString& FighterId,
                                                   int32 Allowance) {
  TSet<uint64> Reachable;
  const FS08BoardFighter* Mover = nullptr;
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (Fighter.Id == FighterId) {
      Mover = &Fighter;
      break;
    }
  }
  if (!Mover || !Mover->IsAlive() || Allowance < 0) return Reachable;
  Reachable.Add(CellKey(Mover->X, Mover->Y)); // zero-step legal resolve

  // BFS frontier: (x, y, stepsUsed). Passing through a living ALLY is legal
  // but the ally's cell is not a valid endpoint - endpoint legality is
  // checked when collecting results, not when expanding.
  struct FNode {
    int32 X, Y, Steps;
  };
  TMap<uint64, int32> Best;
  TArray<FNode> Frontier;
  Frontier.Push({Mover->X, Mover->Y, 0});
  Best.Add(CellKey(Mover->X, Mover->Y), 0);
  while (Frontier.Num() > 0) {
    const FNode Node = Frontier.Pop(EAllowShrinking::No);
    if (Node.Steps >= Allowance) continue;
    static const int32 Dx[4] = {1, -1, 0, 0};
    static const int32 Dy[4] = {0, 0, 1, -1};
    for (int32 Dir = 0; Dir < 4; ++Dir) {
      const int32 NX = Node.X + Dx[Dir];
      const int32 NY = Node.Y + Dy[Dir];
      if (!IsStepTraversable(Board, Fighters, *Mover, NX, NY)) continue;
      const uint64 Key = CellKey(NX, NY);
      const int32 NewSteps = Node.Steps + 1;
      if (const int32* Existing = Best.Find(Key)) {
        if (*Existing <= NewSteps) continue;
      }
      Best.Add(Key, NewSteps);
      Frontier.Push({NX, NY, NewSteps});
      if (IsEndpointFree(Fighters, *Mover, NX, NY)) {
        Reachable.Add(Key);
      }
    }
  }
  return Reachable;
}

bool FS08BoardModel::BuildManeuverPath(const FS08BoardModel& Board,
                                       const TArray<FS08BoardFighter>& Fighters,
                                       const FString& FighterId, int32 Allowance,
                                       int32 TargetX, int32 TargetY,
                                       TArray<FIntPoint>& OutPath) {
  OutPath.Reset();
  const FS08BoardFighter* Mover = nullptr;
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (Fighter.Id == FighterId) {
      Mover = &Fighter;
      break;
    }
  }
  if (!Mover || !Mover->IsAlive() || Allowance < 0) return false;
  if (TargetX == Mover->X && TargetY == Mover->Y) return true; // zero-step resolve

  struct FNode {
    int32 X, Y, Steps;
  };
  TMap<uint64, int32> Best;
  TArray<FNode> Frontier;
  Frontier.Push({Mover->X, Mover->Y, 0});
  Best.Add(CellKey(Mover->X, Mover->Y), 0);
  while (Frontier.Num() > 0) {
    const FNode Node = Frontier.Pop(EAllowShrinking::No);
    if (Node.Steps >= Allowance) continue;
    static const int32 Dx[4] = {1, -1, 0, 0};
    static const int32 Dy[4] = {0, 0, 1, -1};
    for (int32 Dir = 0; Dir < 4; ++Dir) {
      const int32 NX = Node.X + Dx[Dir];
      const int32 NY = Node.Y + Dy[Dir];
      if (!IsStepTraversable(Board, Fighters, *Mover, NX, NY)) continue;
      const uint64 Key = CellKey(NX, NY);
      const int32 NewSteps = Node.Steps + 1;
      if (const int32* Existing = Best.Find(Key)) {
        if (*Existing <= NewSteps) continue;
      }
      Best.Add(Key, NewSteps);
      Frontier.Push({NX, NY, NewSteps});
    }
  }

  const uint64 TargetKey = CellKey(TargetX, TargetY);
  const int32* TargetSteps = Best.Find(TargetKey);
  if (!TargetSteps) return false;
  // Walk from the target back to the mover by descending step counts: any
  // adjacent cell with steps-1 is on a shortest legal route.
  TArray<FIntPoint> Reversed;
  int32 CX = TargetX, CY = TargetY;
  int32 Steps = *TargetSteps;
  while (Steps > 0) {
    Reversed.Add(FIntPoint(CX, CY));
    --Steps;
    bool Advanced = false;
    for (int32 Dir = 0; Dir < 4; ++Dir) {
      static const int32 Dx2[4] = {1, -1, 0, 0};
      static const int32 Dy2[4] = {0, 0, 1, -1};
      const int32 PX = CX + Dx2[Dir];
      const int32 PY = CY + Dy2[Dir];
      const int32* PrevSteps = Best.Find(CellKey(PX, PY));
      if (PrevSteps && *PrevSteps == Steps) {
        CX = PX;
        CY = PY;
        Advanced = true;
        break;
      }
    }
    if (!Advanced) return false;
  }
  for (int32 Index = Reversed.Num() - 1; Index >= 0; --Index) {
    OutPath.Add(Reversed[Index]);
  }
  return OutPath.Num() > 0;
}

bool FS08BoardModel::DecodeFighters(const TSharedPtr<FJsonValue>& FightersValue,
                                    TArray<FS08BoardFighter>& OutFighters) {
  OutFighters.Reset();
  const TArray<TSharedPtr<FJsonValue>>* Array = nullptr;
  if (!FightersValue.IsValid() || !FightersValue->TryGetArray(Array) || !Array) return false;

  for (const TSharedPtr<FJsonValue>& Value : *Array) {
    const TSharedPtr<FJsonObject>* Object = nullptr;
    if (!Value.IsValid() || !Value->TryGetObject(Object) || !Object->IsValid()) continue;
    const TSharedRef<FJsonObject> Fighter = Object->ToSharedRef();
    FS08BoardFighter Entry;
    Entry.Id = Fighter->GetStringField(TEXT("id"));
    Entry.OwnerId = Fighter->GetStringField(TEXT("ownerId"));
    Entry.Name = Fighter->GetStringField(TEXT("name"));
    Entry.bIsHero = Fighter->GetStringField(TEXT("type")) == TEXT("HERO");
    bool Present = false;
    FS08Contracts::ReadIntLike(Fighter, TEXT("health"), Entry.Health, Present);
    FS08Contracts::ReadIntLike(Fighter, TEXT("maxHealth"), Entry.MaxHealth, Present);
    FS08Contracts::ReadIntLike(Fighter, TEXT("movement"), Entry.Movement, Present);
    Entry.AttackType = Fighter->GetStringField(TEXT("attackType"));
    const TSharedPtr<FJsonObject>* Position = nullptr;
    if (Fighter->TryGetObjectField(TEXT("position"), Position) && Position->IsValid()) {
      const TSharedRef<FJsonObject> Pos = Position->ToSharedRef();
      bool PosPresent = false;
      if (FS08Contracts::ReadIntLike(Pos, TEXT("x"), Entry.X, PosPresent) && !PosPresent) Entry.X = -1;
      if (FS08Contracts::ReadIntLike(Pos, TEXT("y"), Entry.Y, PosPresent) && !PosPresent) Entry.Y = -1;
    }
    OutFighters.Add(MoveTemp(Entry));
  }

  // Same-name numbering keyed by stable id (TASK-021: three Harpies stay
  // distinguishable even if the server reorders the array between updates).
  TMap<FString, int32> NameCounts;
  TMap<FString, int32> NameTotals;
  for (const FS08BoardFighter& Fighter : OutFighters) {
    const int32* Total = NameTotals.Find(Fighter.Name);
    NameTotals.Add(Fighter.Name, Total ? *Total + 1 : 1);
  }
  for (FS08BoardFighter& Fighter : OutFighters) {
    const int32 Total = NameTotals.FindRef(Fighter.Name);
    if (Total <= 1) {
      Fighter.Label = Fighter.Name;
      continue;
    }
    const int32 Index = NameCounts.FindRef(Fighter.Name) + 1;
    NameCounts.Add(Fighter.Name, Index);
    Fighter.Label = FString::Printf(TEXT("%s %d"), *Fighter.Name, Index);
  }
  return OutFighters.Num() > 0;
}

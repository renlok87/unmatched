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

// ENV-MAPS space fields of one cell (backend buildBoardState copies them only
// when valid: spaceId non-empty string, layout {x,y} numbers, start 1..4,
// links [{x,y}] integer lattice positions). Malformed entries are skipped,
// never fatal - the grid path must keep decoding every old projection.
void DecodeTopologyFields(const TSharedPtr<FJsonObject>& CellObject, FS08Cell& Cell) {
  const TArray<TSharedPtr<FJsonValue>>* LinkValues = nullptr;
  if (CellObject->TryGetArrayField(TEXT("links"), LinkValues) && LinkValues) {
    Cell.bHasLinks = true; // even an empty array marks the board as topological (backend rule)
    for (const TSharedPtr<FJsonValue>& LinkValue : *LinkValues) {
      const TSharedPtr<FJsonObject>* LinkObject = nullptr;
      if (!LinkValue.IsValid() || !LinkValue->TryGetObject(LinkObject) || !LinkObject ||
          !LinkObject->IsValid()) {
        continue;
      }
      int32 LX = 0, LY = 0;
      bool bXPresent = false, bYPresent = false;
      const TSharedRef<FJsonObject> Link = LinkObject->ToSharedRef();
      if (!FS08Contracts::ReadIntLike(Link, TEXT("x"), LX, bXPresent) || !bXPresent ||
          !FS08Contracts::ReadIntLike(Link, TEXT("y"), LY, bYPresent) || !bYPresent) {
        continue;
      }
      Cell.Links.AddUnique(FIntPoint(LX, LY));
    }
  }
  const TSharedPtr<FJsonObject>* LayoutObject = nullptr;
  if (CellObject->TryGetObjectField(TEXT("layout"), LayoutObject) && LayoutObject &&
      LayoutObject->IsValid()) {
    double LX = 0.0, LY = 0.0;
    if ((*LayoutObject)->TryGetNumberField(TEXT("x"), LX) &&
        (*LayoutObject)->TryGetNumberField(TEXT("y"), LY) && FMath::IsFinite(LX) &&
        FMath::IsFinite(LY)) {
      Cell.bHasLayout = true;
      Cell.Layout = FVector2D(LX, LY);
    }
  }
  int32 Start = 0;
  bool bStartPresent = false;
  if (FS08Contracts::ReadIntLike(CellObject.ToSharedRef(), TEXT("start"), Start, bStartPresent) &&
      bStartPresent && Start >= 1 && Start <= 4) {
    Cell.StartSlot = Start;
  }
  FString SpaceId;
  if (CellObject->TryGetStringField(TEXT("spaceId"), SpaceId)) {
    Cell.SpaceId = SpaceId.TrimStartAndEnd();
  }
}
} // namespace

bool FS08BoardModel::Decode(const TSharedPtr<FJsonValue>& BoardState) {
  Width = Height = 0;
  Cells.Reset();
  bHasTopology = false;
  LinkIndex.Reset();
  // LayoutFrame is NOT reset: it belongs to the art profile, not the state.
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
      if (Cell.Zones.Num() == 0) {
        // Backend getCellZones fallback: a legacy cell with only the single
        // `zone` field is in that zone (ranged same-zone parity, GAP-023).
        // buildBoardState always writes zones[] and zone together, so live
        // boards never take this branch.
        FString Legacy;
        if ((*CellObject)->TryGetStringField(TEXT("zone"), Legacy) && !Legacy.IsEmpty()) {
          Cell.Zones.Add(Legacy);
        }
      }
      if (Cell.Type == ES08CellType::Door) {
        bool bOpen = true;
        (*CellObject)->TryGetBoolField(TEXT("isOpen"), bOpen);
        const FString Key = FString::Printf(TEXT("%d,%d"), X, Y);
        if (bool* FromMap = DoorStates.Find(Key)) bOpen = *FromMap;
        Cell.bIsOpen = bOpen;
      }
      DecodeTopologyFields(*CellObject, Cell);
    }
  }
  RebuildTopology();
  return true;
}

// ---- ENV-MAPS topology ------------------------------------------------------

void FS08BoardModel::BuildLinkIndex(const FS08BoardModel& Board,
                                    TArray<TArray<FIntPoint>>& OutIndex) {
  // Mirror of backend board-topology linkIndex: declared links in row-major
  // cell order (bounds-checked, self-links dropped), each cell first gets its
  // OWN links in the order sent, then the reverse of links declared only by
  // the other side (symmetry). Duplicates collapse.
  OutIndex.Reset();
  OutIndex.SetNum(Board.Width * Board.Height);
  TArray<TPair<FIntPoint, FIntPoint>> Declared;
  for (int32 Y = 0; Y < Board.Height; ++Y) {
    for (int32 X = 0; X < Board.Width; ++X) {
      for (const FIntPoint& Link : Board.Cells[Y * Board.Width + X].Links) {
        if (!Board.CellAt(Link.X, Link.Y)) continue;
        if (Link.X == X && Link.Y == Y) continue;
        Declared.Add(TPair<FIntPoint, FIntPoint>(FIntPoint(X, Y), Link));
      }
    }
  }
  for (const TPair<FIntPoint, FIntPoint>& Edge : Declared) {
    OutIndex[Edge.Key.Y * Board.Width + Edge.Key.X].AddUnique(Edge.Value);
  }
  for (const TPair<FIntPoint, FIntPoint>& Edge : Declared) {
    OutIndex[Edge.Value.Y * Board.Width + Edge.Value.X].AddUnique(Edge.Key);
  }
}

void FS08BoardModel::RebuildTopology() {
  LinkIndex.Reset();
  bHasTopology = false;
  if (Width <= 0 || Height <= 0 || Cells.Num() != Width * Height) return;
  for (const FS08Cell& Cell : Cells) {
    if (Cell.bHasLinks || Cell.Links.Num() > 0) {
      bHasTopology = true;
      break;
    }
  }
  if (bHasTopology) BuildLinkIndex(*this, LinkIndex);
}

bool FS08BoardModel::SetLayoutFrame(const FVector2D& SrcSizePx, float UuPerPx,
                                    float SpaceRadiusPx) {
  if (!(SrcSizePx.X > 0.0) || !(SrcSizePx.Y > 0.0) || !(UuPerPx > 0.0f) ||
      !(SpaceRadiusPx > 0.0f)) {
    return false;
  }
  LayoutFrame.SrcSize = SrcSizePx;
  LayoutFrame.UuPerPx = UuPerPx;
  LayoutFrame.SpaceRadiusPx = SpaceRadiusPx;
  LayoutFrame.bSet = true;
  return true;
}

TArray<FIntPoint> FS08BoardModel::Neighbours(const FIntPoint& Cell) const {
  TArray<FIntPoint> Out;
  if (bHasTopology) {
    if (!CellAt(Cell.X, Cell.Y)) return Out;
    const int32 Index = Cell.Y * Width + Cell.X;
    if (LinkIndex.Num() == Width * Height) return LinkIndex[Index];
    // Stale index (cells resized after RebuildTopology): derive on the fly.
    TArray<TArray<FIntPoint>> Fresh;
    BuildLinkIndex(*this, Fresh);
    return Fresh.IsValidIndex(Index) ? Fresh[Index] : Out;
  }
  // Historical client order of every S08/S09 grid BFS: +X, -X, +Y, -Y.
  static const int32 Dx[4] = {1, -1, 0, 0};
  static const int32 Dy[4] = {0, 0, 1, -1};
  for (int32 Dir = 0; Dir < 4; ++Dir) {
    const int32 NX = Cell.X + Dx[Dir];
    const int32 NY = Cell.Y + Dy[Dir];
    if (CellAt(NX, NY)) Out.Add(FIntPoint(NX, NY));
  }
  return Out;
}

bool FS08BoardModel::IsAdjacent(const FIntPoint& A, const FIntPoint& B) const {
  if (bHasTopology) {
    if (A == B) return false;
    return Neighbours(A).Contains(B);
  }
  return FMath::Abs(A.X - B.X) + FMath::Abs(A.Y - B.Y) == 1;
}

int32 FS08BoardModel::GraphDistance(const FIntPoint& A, const FIntPoint& B) const {
  if (A == B) return 0;
  if (!bHasTopology) return FMath::Abs(A.X - B.X) + FMath::Abs(A.Y - B.Y);
  if (!CellAt(A.X, A.Y) || !CellAt(B.X, B.Y)) return MAX_int32;
  TArray<int32> Dist;
  Dist.Init(MAX_int32, Width * Height);
  TArray<FIntPoint> Queue;
  Dist[A.Y * Width + A.X] = 0;
  Queue.Add(A);
  for (int32 Head = 0; Head < Queue.Num(); ++Head) {
    const FIntPoint P = Queue[Head];
    const int32 Next = Dist[P.Y * Width + P.X] + 1;
    for (const FIntPoint& N : Neighbours(P)) {
      int32& D = Dist[N.Y * Width + N.X];
      if (D <= Next) continue;
      D = Next;
      if (N == B) return Next;
      Queue.Add(N);
    }
  }
  return MAX_int32;
}

bool FS08BoardModel::SharesZone(const FIntPoint& A, const FIntPoint& B) const {
  const FS08Cell* CellA = CellAt(A.X, A.Y);
  const FS08Cell* CellB = CellAt(B.X, B.Y);
  if (!CellA || !CellB) return false;
  for (const FString& Zone : CellA->Zones) {
    if (CellB->Zones.Contains(Zone)) return true;
  }
  return false;
}

const FS08Cell* FS08BoardModel::FindSpace(const FString& SpaceId) const {
  if (SpaceId.IsEmpty()) return nullptr;
  for (const FS08Cell& Cell : Cells) {
    if (Cell.SpaceId == SpaceId) return &Cell;
  }
  return nullptr;
}

FString FS08BoardModel::CellLabel(int32 X, int32 Y) const {
  const FS08Cell* Cell = CellAt(X, Y);
  if (Cell && !Cell->SpaceId.IsEmpty()) return Cell->SpaceId;
  return FString::Printf(TEXT("(%d,%d)"), X, Y);
}

bool FS08BoardModel::WorldToSpace(const FVector& World, int32& OutX, int32& OutY) const {
  OutX = OutY = -1;
  const double Radius = LayoutFrame.SpaceRadiusUU();
  const double RadiusSq = Radius * Radius;
  double BestSq = TNumericLimits<double>::Max();
  for (int32 Index = 0; Index < Cells.Num() && Width > 0; ++Index) {
    const FS08Cell& Cell = Cells[Index];
    if (!Cell.bHasLayout) continue;
    const FVector Centre = LayoutFrame.ToWorld(Cell.Layout);
    const double DistSq = FMath::Square(World.X - Centre.X) + FMath::Square(World.Y - Centre.Y);
    if (DistSq > RadiusSq || DistSq >= BestSq) continue; // first (row-major) wins exact ties
    BestSq = DistSq;
    OutX = Index % Width;
    OutY = Index / Width;
  }
  return OutX >= 0;
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
    // Board neighbours: links on a topology board, the in-bounds orthogonal
    // cells (+X, -X, +Y, -Y - the old order) on a grid.
    for (const FIntPoint& Next : Board.Neighbours(FIntPoint(Node.X, Node.Y))) {
      const int32 NX = Next.X;
      const int32 NY = Next.Y;
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
    for (const FIntPoint& Next : Board.Neighbours(FIntPoint(Node.X, Node.Y))) {
      const int32 NX = Next.X;
      const int32 NY = Next.Y;
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
  // neighbour with steps-1 is on a shortest legal route (links are
  // symmetric, so the predecessor is always among the neighbours).
  TArray<FIntPoint> Reversed;
  int32 CX = TargetX, CY = TargetY;
  int32 Steps = *TargetSteps;
  while (Steps > 0) {
    Reversed.Add(FIntPoint(CX, CY));
    --Steps;
    bool Advanced = false;
    for (const FIntPoint& Prev : Board.Neighbours(FIntPoint(CX, CY))) {
      const int32* PrevSteps = Best.Find(CellKey(Prev.X, Prev.Y));
      if (PrevSteps && *PrevSteps == Steps) {
        CX = Prev.X;
        CY = Prev.Y;
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

bool FS08BoardModel::PickApproachDestination(const FS08BoardModel& Board,
                                             const TArray<FS08BoardFighter>& Fighters,
                                             const FString& MoverId, int32 Allowance,
                                             FIntPoint& OutCell, int32& OutFromDistance,
                                             int32& OutToDistance, int32& OutSteps) {
  OutFromDistance = OutToDistance = MAX_int32;
  OutSteps = 0;
  const FS08BoardFighter* Mover = nullptr;
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (Fighter.Id == MoverId) {
      Mover = &Fighter;
      break;
    }
  }
  if (!Mover || !Mover->IsAlive() || Board.Width <= 0 || Board.Height <= 0) return false;

  // Terrain distance field from every living enemy (multi-source BFS). The
  // enemy's own cell is the source even though it is occupied; fighters do
  // not block this field (they move), only terrain does.
  TArray<int32> Dist;
  Dist.Init(MAX_int32, Board.Width * Board.Height);
  TArray<FIntPoint> Queue;
  for (const FS08BoardFighter& Enemy : Fighters) {
    if (Enemy.OwnerId == Mover->OwnerId || !Enemy.IsAlive()) continue;
    if (!Board.CellAt(Enemy.X, Enemy.Y)) continue;
    const int32 Index = Enemy.Y * Board.Width + Enemy.X;
    if (Dist[Index] == 0) continue;
    Dist[Index] = 0;
    Queue.Add(FIntPoint(Enemy.X, Enemy.Y));
  }
  for (int32 Head = 0; Head < Queue.Num(); ++Head) {
    const FIntPoint P = Queue[Head];
    const int32 Next = Dist[P.Y * Board.Width + P.X] + 1;
    for (const FIntPoint& N : Board.Neighbours(P)) {
      const int32 NX = N.X, NY = N.Y;
      const FS08Cell* Cell = Board.CellAt(NX, NY);
      if (!Cell || !Cell->IsPassable()) continue;
      int32& D = Dist[NY * Board.Width + NX];
      if (D <= Next) continue;
      D = Next;
      Queue.Add(FIntPoint(NX, NY));
    }
  }
  auto DistAt = [&](int32 X, int32 Y) -> int32 {
    return Board.CellAt(X, Y) ? Dist[Y * Board.Width + X] : MAX_int32;
  };
  OutFromDistance = DistAt(Mover->X, Mover->Y);

  const TSet<uint64> Reachable = ComputeReachableCells(Board, Fighters, MoverId, Allowance);
  bool bFound = false;
  FIntPoint Best(-1, -1);
  int32 BestDist = MAX_int32, BestSteps = MAX_int32;
  for (const uint64 Key : Reachable) {
    const int32 X = static_cast<int32>(static_cast<uint32>(Key >> 32));
    const int32 Y = static_cast<int32>(static_cast<uint32>(Key & 0xffffffffull));
    if (X == Mover->X && Y == Mover->Y) continue;
    const int32 D = DistAt(X, Y);
    if (D == MAX_int32 || D >= OutFromDistance) continue; // must strictly improve
    TArray<FIntPoint> Path;
    if (!BuildManeuverPath(Board, Fighters, MoverId, Allowance, X, Y, Path)) continue;
    const int32 Steps = Path.Num();
    const bool bBetter = D < BestDist ||
        (D == BestDist && (Steps < BestSteps ||
         (Steps == BestSteps && (Y < Best.Y || (Y == Best.Y && X < Best.X)))));
    if (bBetter) {
      bFound = true;
      Best = FIntPoint(X, Y);
      BestDist = D;
      BestSteps = Steps;
    }
  }
  if (!bFound) return false;
  OutCell = Best;
  OutToDistance = BestDist;
  OutSteps = BestSteps;
  return true;
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
    const TArray<TSharedPtr<FJsonValue>>* EffectValues = nullptr;
    if (Fighter->TryGetArrayField(TEXT("effects"), EffectValues) && EffectValues) {
      for (const TSharedPtr<FJsonValue>& Effect : *EffectValues) {
        if (!Effect.IsValid()) continue;
        FString Name;
        const TSharedPtr<FJsonObject>* EffectObject = nullptr;
        if (Effect->TryGetString(Name)) {
        } else if (Effect->TryGetObject(EffectObject) && EffectObject->IsValid()) {
          if (!(*EffectObject)->TryGetStringField(TEXT("type"), Name) &&
              !(*EffectObject)->TryGetStringField(TEXT("name"), Name)) {
            (*EffectObject)->TryGetStringField(TEXT("id"), Name);
          }
        }
        Name.TrimStartAndEndInline();
        if (!Name.IsEmpty()) Entry.Effects.Add(Name);
      }
    }
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

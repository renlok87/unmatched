#include "S08BoardModel.h"
#include "Dom/JsonObject.h"
#include <limits>

namespace {
constexpr double S08JsNaN = std::numeric_limits<double>::quiet_NaN();

// ECMAScript WhiteSpace + LineTerminator (StringToNumber trims both).
bool IsJsWhitespace(TCHAR C) {
  switch (C) {
    case 0x0009: case 0x000A: case 0x000B: case 0x000C: case 0x000D: case 0x0020: case 0x00A0:
    case 0x1680: case 0x2028: case 0x2029: case 0x202F: case 0x205F: case 0x3000: case 0xFEFF:
      return true;
    default:
      return C >= 0x2000 && C <= 0x200A;
  }
}

bool IsAsciiDigit(TCHAR C) { return C >= TEXT('0') && C <= TEXT('9'); }

// ECMAScript StringToNumber: trimmed; "" -> 0; StrDecimalLiteral (sign,
// digits, '.', exponent, "Infinity"); 0x/0o/0b integers without a sign;
// anything else -> NaN. The validated decimal text goes to Atod (strtod,
// correctly rounded like JS).
double JsStringToNumber(const FString& In) {
  int32 Begin = 0, End = In.Len();
  while (Begin < End && IsJsWhitespace(In[Begin])) ++Begin;
  while (End > Begin && IsJsWhitespace(In[End - 1])) --End;
  if (Begin == End) return 0.0;
  const FString S = In.Mid(Begin, End - Begin);
  const int32 Len = S.Len();
  if (Len > 2 && S[0] == TEXT('0')) {
    const TCHAR Prefix = S[1];
    const int32 Base = (Prefix == TEXT('x') || Prefix == TEXT('X'))   ? 16
                       : (Prefix == TEXT('o') || Prefix == TEXT('O')) ? 8
                       : (Prefix == TEXT('b') || Prefix == TEXT('B')) ? 2
                                                                      : 0;
    if (Base != 0) {
      double Value = 0.0;
      for (int32 I = 2; I < Len; ++I) {
        const TCHAR C = S[I];
        const int32 Digit = IsAsciiDigit(C)                          ? C - TEXT('0')
                            : (C >= TEXT('a') && C <= TEXT('f')) ? C - TEXT('a') + 10
                            : (C >= TEXT('A') && C <= TEXT('F')) ? C - TEXT('A') + 10
                                                                     : -1;
        if (Digit < 0 || Digit >= Base) return S08JsNaN;
        Value = Value * Base + Digit;
      }
      return Value;
    }
  }
  int32 I = 0;
  bool bNegative = false;
  if (S[I] == TEXT('+') || S[I] == TEXT('-')) {
    bNegative = S[I] == TEXT('-');
    ++I;
  }
  if (S.Mid(I).Equals(TEXT("Infinity"), ESearchCase::CaseSensitive)) {
    return bNegative ? -std::numeric_limits<double>::infinity() : std::numeric_limits<double>::infinity();
  }
  int32 Digits = 0;
  while (I < Len && IsAsciiDigit(S[I])) { ++I; ++Digits; }
  if (I < Len && S[I] == TEXT('.')) {
    ++I;
    while (I < Len && IsAsciiDigit(S[I])) { ++I; ++Digits; }
  }
  if (Digits == 0) return S08JsNaN;
  if (I < Len && (S[I] == TEXT('e') || S[I] == TEXT('E'))) {
    ++I;
    if (I < Len && (S[I] == TEXT('+') || S[I] == TEXT('-'))) ++I;
    int32 ExpDigits = 0;
    while (I < Len && IsAsciiDigit(S[I])) { ++I; ++ExpDigits; }
    if (ExpDigits == 0) return S08JsNaN;
  }
  if (I != Len) return S08JsNaN;
  return FCString::Atod(*S);
}

// JS truthiness of a JSON value (`!f.isDefeated`): absent/null/false/0/NaN/""
// are false; any array or object is true.
bool JsTruthy(const TSharedPtr<FJsonValue>& Value) {
  if (!Value.IsValid()) return false;
  switch (Value->Type) {
    case EJson::Boolean: return Value->AsBool();
    case EJson::Number: {
      double D = 0.0;
      Value->TryGetNumber(D);
      return D != 0.0 && !FMath::IsNaN(D);
    }
    case EJson::String: {
      FString S;
      Value->TryGetString(S);
      return !S.IsEmpty();
    }
    case EJson::Array:
    case EJson::Object:
      return true;
    default:
      return false;
  }
}

// Fighter ids compare exactly (server `===`; FString == ignores case).
bool SameId(const FString& A, const FString& B) { return A.Equals(B, ESearchCase::CaseSensitive); }

const FS08BoardFighter* FindFighter(const TArray<FS08BoardFighter>& Fighters, const FString& Id) {
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (SameId(Fighter.Id, Id)) return &Fighter;
  }
  return nullptr;
}

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
  // Occupant role = backend isLivingFighter (MS-E-23/24): a fighter with
  // isDefeated never occupies a cell, whatever its health. A fighter without
  // a position (X < 0) is not on the board.
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (SameId(Fighter.Id, IgnoreFighterId) || !Fighter.IsAliveBlocker() || Fighter.X < 0) continue;
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

// ---- MS-T-03: canonical reach and path (04 §3.1) ----------------------------

int32 FS08ReachMap::DistanceTo(const FIntPoint& Cell) const {
  const int32* Steps = Dist.Find(FS08BoardModel::CellKey(Cell.X, Cell.Y));
  return Steps ? *Steps : INDEX_NONE;
}

double FS08BoardModel::JsNumber(const TSharedPtr<FJsonValue>& Value) {
  if (!Value.IsValid()) return S08JsNaN; // undefined
  switch (Value->Type) {
    case EJson::Null: return 0.0;
    case EJson::Boolean: return Value->AsBool() ? 1.0 : 0.0;
    case EJson::Number: {
      double D = 0.0;
      return Value->TryGetNumber(D) ? D : S08JsNaN;
    }
    case EJson::String: {
      FString S;
      Value->TryGetString(S);
      return JsStringToNumber(S);
    }
    case EJson::Array: {
      // ToPrimitive joins the elements with ',': [] -> "" -> 0, two or more
      // elements always carry a comma -> NaN, one element is its String().
      const TArray<TSharedPtr<FJsonValue>>& Items = Value->AsArray();
      if (Items.Num() == 0) return 0.0;
      if (Items.Num() > 1) return S08JsNaN;
      const TSharedPtr<FJsonValue>& Item = Items[0];
      if (!Item.IsValid() || Item->Type == EJson::Null || Item->Type == EJson::None) return 0.0; // String(null) in join = ""
      if (Item->Type == EJson::Boolean || Item->Type == EJson::Object) return S08JsNaN; // "true" / "[object Object]"
      return JsNumber(Item); // number, string or nested array: Number(String(x)) == Number(x)
    }
    default:
      return S08JsNaN; // object -> "[object Object]"
  }
}

int32 FS08BoardModel::FighterMovement(const FS08BoardFighter& Fighter) {
  if (!Fighter.bMovementPresent) return DefaultFighterMovement; // Number(undefined) = NaN
  const double M = Fighter.MovementRaw;
  if (!FMath::IsFinite(M) || M < 1.0 || FMath::FloorToDouble(M) != M) return DefaultFighterMovement;
  return M >= static_cast<double>(MAX_int32) ? MAX_int32 : static_cast<int32>(M);
}

FS08ReachMap FS08BoardModel::ComputeReachMap(const FS08BoardModel& Board,
                                             const TArray<FS08BoardFighter>& Fighters,
                                             const FString& MoverId, int32 MaxSteps,
                                             const FS08ReachOptions& Options) {
  FS08ReachMap Reach;
  Reach.MoverId = MoverId;
  Reach.MaxSteps = MaxSteps;
  Reach.bPassThroughEnemies = Options.bPassThroughEnemies;
  const FS08BoardFighter* Mover = FindFighter(Fighters, MoverId);
  if (!Mover || Mover->X < 0 || Mover->Y < 0) return Reach;
  Reach.bValid = true;
  Reach.OwnerId = Mover->OwnerId;
  Reach.Start = FIntPoint(Mover->X, Mover->Y);
  Reach.Dist.Add(CellKey(Mover->X, Mover->Y), 0);
  Reach.Order.Add(Reach.Start);

  // Living enemies of the MOVED fighter's owner (an effect may move the
  // opponent's fighter: enemies are relative to it, not to the chooser).
  TSet<uint64> EnemyCells;
  if (!Options.bPassThroughEnemies) {
    for (const FS08BoardFighter& Other : Fighters) {
      if (SameId(Other.Id, MoverId) || !Other.IsAliveBlocker() || Other.X < 0) continue;
      if (!SameId(Other.OwnerId, Mover->OwnerId)) EnemyCells.Add(CellKey(Other.X, Other.Y));
    }
  }

  // FIFO: Order is the queue; Head walks it while new cells are appended.
  for (int32 Head = 0; Head < Reach.Order.Num(); ++Head) {
    const FIntPoint Current = Reach.Order[Head];
    const uint64 CurrentKey = CellKey(Current.X, Current.Y);
    const int32 Steps = Reach.Dist.FindChecked(CurrentKey);
    if (Steps >= MaxSteps) continue; // `>=`: the server rule and the parity contract
    for (const FIntPoint& Next : Board.Neighbours(Current)) {
      const uint64 NextKey = CellKey(Next.X, Next.Y);
      if (Reach.Dist.Contains(NextKey)) continue;
      const FS08Cell* Cell = Board.CellAt(Next.X, Next.Y);
      if (!Cell || !Cell->IsPassable()) continue;
      if (EnemyCells.Contains(NextKey)) continue;
      Reach.Dist.Add(NextKey, Steps + 1);
      Reach.Parent.Add(NextKey, CurrentKey);
      Reach.Order.Add(Next);
    }
  }
  return Reach;
}

bool FS08BoardModel::IsReachEndpoint(const TArray<FS08BoardFighter>& Fighters, const FS08ReachMap& Reach,
                                     const FIntPoint& Cell) {
  if (!Reach.bValid) return false;
  return Cell == Reach.Start || FighterAt(Fighters, Cell.X, Cell.Y, Reach.MoverId) == nullptr;
}

int32 FS08BoardModel::CompareCanonical(const FS08BoardModel& Board, const FIntPoint& A, const FIntPoint& B) {
  if (Board.bHasTopology) {
    const FS08Cell* CellA = Board.CellAt(A.X, A.Y);
    const FS08Cell* CellB = Board.CellAt(B.X, B.Y);
    static const FString None;
    const FString& IdA = CellA ? CellA->SpaceId : None;
    const FString& IdB = CellB ? CellB->SpaceId : None;
    // Ordinal, case sensitive (TCHAR code units) - JS string `<`.
    const int32 ById = IdA.Compare(IdB, ESearchCase::CaseSensitive);
    if (ById != 0) return ById < 0 ? -1 : 1;
  }
  if (A.Y != B.Y) return A.Y < B.Y ? -1 : 1;
  if (A.X != B.X) return A.X < B.X ? -1 : 1;
  return 0;
}

bool FS08BoardModel::BuildCanonicalPath(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                                        const FS08ReachMap& Reach, const FIntPoint& Dest,
                                        TArray<FIntPoint>& OutPath) {
  OutPath.Reset();
  if (!Reach.bValid) return false;
  if (Dest == Reach.Start) return true; // "stay": no entry in moves[]
  const int32 Steps = Reach.DistanceTo(Dest);
  if (Steps == INDEX_NONE || !IsReachEndpoint(Fighters, Reach, Dest)) return false;
  OutPath.SetNum(Steps);
  OutPath[Steps - 1] = Dest;
  FIntPoint Current = Dest;
  for (int32 D = Steps; D > 1; --D) {
    bool bFound = false;
    FIntPoint Best(-1, -1);
    for (const FIntPoint& Candidate : Board.Neighbours(Current)) {
      if (Reach.DistanceTo(Candidate) != D - 1) continue;
      if (!bFound || CompareCanonical(Board, Candidate, Best) < 0) {
        Best = Candidate;
        bFound = true;
      }
    }
    // BFS invariant: a cell at distance d has a neighbour at d - 1.
    if (!bFound) {
      OutPath.Reset();
      return false;
    }
    OutPath[D - 2] = Best;
    Current = Best;
  }
  return true;
}

TArray<FIntPoint> FS08BoardModel::ReachEndpoints(const FS08BoardModel& Board,
                                                 const TArray<FS08BoardFighter>& Fighters,
                                                 const FS08ReachMap& Reach, int32 MaxSteps) {
  TArray<FIntPoint> Out;
  if (!Reach.bValid) return Out;
  for (const FIntPoint& Cell : Reach.Order) {
    const int32 Steps = Reach.Dist.FindChecked(CellKey(Cell.X, Cell.Y));
    if (Steps < 1 || Steps > MaxSteps) continue;
    if (IsReachEndpoint(Fighters, Reach, Cell)) Out.Add(Cell);
  }
  Out.Sort([&Board](const FIntPoint& A, const FIntPoint& B) { return CompareCanonical(Board, A, B) < 0; });
  return Out;
}

// ---- legacy wrappers --------------------------------------------------------

TSet<uint64> FS08BoardModel::ComputeReachableCells(const FS08BoardModel& Board,
                                                   const TArray<FS08BoardFighter>& Fighters,
                                                   const FString& FighterId,
                                                   int32 Allowance) {
  TSet<uint64> Reachable;
  const FS08BoardFighter* Mover = FindFighter(Fighters, FighterId);
  if (!Mover || !Mover->IsAlive() || Allowance < 0) return Reachable;
  // The former stack frontier with relaxation converged to the BFS
  // distances, so "reached within Allowance and endpoint-free" is the same
  // set; the start stays in it (zero-step legal resolve).
  const FS08ReachMap Reach = ComputeReachMap(Board, Fighters, FighterId, Allowance);
  Reachable.Add(CellKey(Mover->X, Mover->Y));
  for (const FIntPoint& Cell : Reach.Order) {
    if (Cell != Reach.Start && IsReachEndpoint(Fighters, Reach, Cell)) Reachable.Add(CellKey(Cell.X, Cell.Y));
  }
  return Reachable;
}

bool FS08BoardModel::BuildManeuverPath(const FS08BoardModel& Board,
                                       const TArray<FS08BoardFighter>& Fighters,
                                       const FString& FighterId, int32 Allowance,
                                       int32 TargetX, int32 TargetY,
                                       TArray<FIntPoint>& OutPath) {
  OutPath.Reset();
  const FS08BoardFighter* Mover = FindFighter(Fighters, FighterId);
  if (!Mover || !Mover->IsAlive() || Allowance < 0) return false;
  if (TargetX == Mover->X && TargetY == Mover->Y) return true; // zero-step resolve

  const FS08ReachMap Reach = ComputeReachMap(Board, Fighters, FighterId, Allowance);
  int32 Steps = Reach.DistanceTo(FIntPoint(TargetX, TargetY));
  if (Steps == INDEX_NONE) return false;
  // The former reverse walk, kept as it was: from the target, the FIRST
  // board neighbour one step closer (Neighbours order) - not the canonical
  // K choice of BuildCanonicalPath.
  TArray<FIntPoint> Reversed;
  FIntPoint Current(TargetX, TargetY);
  while (Steps > 0) {
    Reversed.Add(Current);
    --Steps;
    bool bAdvanced = false;
    for (const FIntPoint& Prev : Board.Neighbours(Current)) {
      if (Reach.DistanceTo(Prev) == Steps) {
        Current = Prev;
        bAdvanced = true;
        break;
      }
    }
    if (!bAdvanced) return false;
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
    // MS-T-03: the raw value for FighterMovement (getFighterMovement parity,
    // MS-E-04/107) and isDefeated for the role predicates (MS-E-24/77).
    const TSharedPtr<FJsonValue> MovementField = Fighter->TryGetField(TEXT("movement"));
    Entry.bMovementPresent = MovementField.IsValid();
    Entry.MovementRaw = Entry.bMovementPresent ? JsNumber(MovementField) : 0.0;
    Entry.bDefeated = JsTruthy(Fighter->TryGetField(TEXT("isDefeated")));
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

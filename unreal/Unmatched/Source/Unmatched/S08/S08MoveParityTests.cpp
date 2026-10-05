// MS-T-03 (move selection) automation tests: the UE half of the reach/path
// parity with the server (docs/game-design/move-selection/04 §3.1, §4.8;
// 06 MS-AT-10 and the board-model part of MS-AT-14).
//   Unmatched.S08.MoveParity.GoldenFixtures  - every golden fixture of
//       backend/prisma/fixtures/movement that applies to the client model,
//       through FS08BoardModel::ComputeReachMap / ReachEndpoints /
//       BuildCanonicalPath / FighterMovement: reach tiers compared as sets,
//       canonical paths exactly, plus status and required BOOST.
//   Unmatched.S08.MoveParity.FighterMovement - getFighterMovement on the raw
//       value (MS-E-04, MS-E-107) and the JS Number() decode.
//   Unmatched.S08.MoveParity.AlivePredicates - the two "alive" roles
//       (MS-E-23, MS-E-24, MS-E-77).
//   Unmatched.S08.MoveParity.ReachAndKey     - FIFO dist, `>=` limit, the K
//       tie-break (ordinal, case-sensitive spaceId), link-order independence.
//   Unmatched.S08.MoveParity.LegacyWrappers  - ComputeReachableCells and
//       BuildManeuverPath equal the pre-MS-T-03 algorithms on both maps.
// Reference reader: backend/src/test/fixtures/move-fixture-state.ts (format
// additions to 04 §4.8, buildMoveFixtureState, computeFixtureExpect). The
// draft walk goes through the client draft evaluator FS09DraftEval (MS-T-05),
// so the fixtures pin it too.
// Headless run:
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     "-ExecCmds=Automation RunTests Unmatched.S08.MoveParity; Quit"
//     -unattended -nosplash -nullrhi
// Optional: -S08MoveFixtures=<dir>, -S08TopologyFixtures=<dir>.
#if WITH_AUTOMATION_TESTS

#include "S08BoardModel.h"
#include "../S09/S09ManeuverUi.h"
#include "Algo/Reverse.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "HAL/FileManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include <limits>

// Named namespace (not anonymous): unity builds merge test files.
namespace S08MoveParityTest {

const TCHAR* const MpSchema = TEXT("unmatched.move-fixture/1");
const TCHAR* const MpSuffix = TEXT(".move-fixture.json");

// ---- files ------------------------------------------------------------------

/** Repo path from the project dir (unreal/Unmatched -> ../..), as the icon
 *  motion and board graph tests read docs/ and backend/. */
FString MpRepoPath(const TCHAR* Relative) {
  return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectDir(), TEXT("../.."), Relative));
}

FString MpMoveFixtureDir() {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S08MoveFixtures="), Dir) || Dir.IsEmpty()) {
    Dir = MpRepoPath(TEXT("backend/prisma/fixtures/movement"));
  }
  return Dir;
}

FString MpTopologyPath(const FString& Key) {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S08TopologyFixtures="), Dir) || Dir.IsEmpty()) {
    Dir = MpRepoPath(TEXT("backend/prisma/fixtures/boards"));
  }
  return FPaths::Combine(Dir, Key + TEXT(".topology.json"));
}

bool MpLoadJson(const FString& Path, TSharedPtr<FJsonObject>& Out) {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *Path)) return false;
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
  return FJsonSerializer::Deserialize(Reader, Out) && Out.IsValid();
}

bool MpSameId(const FString& A, const FString& B) { return A.Equals(B, ESearchCase::CaseSensitive); }

// ---- small JSON readers -----------------------------------------------------

bool MpIsInt(const TSharedPtr<FJsonValue>& Value, int32& Out) {
  double D = 0.0;
  if (!Value.IsValid() || Value->Type != EJson::Number || !Value->TryGetNumber(D)) return false;
  if (!FMath::IsFinite(D) || FMath::FloorToDouble(D) != D) return false;
  Out = static_cast<int32>(FMath::Clamp(D, -2147483648.0, 2147483647.0)); // out of range = an unreachable cell
  return true;
}

/** [x, y] */
bool MpReadCell(const TSharedPtr<FJsonValue>& Value, FIntPoint& Out) {
  const TArray<TSharedPtr<FJsonValue>>* Pair = nullptr;
  if (!Value.IsValid() || !Value->TryGetArray(Pair) || !Pair || Pair->Num() != 2) return false;
  int32 X = 0, Y = 0;
  if (!MpIsInt((*Pair)[0], X) || !MpIsInt((*Pair)[1], Y)) return false;
  Out = FIntPoint(X, Y);
  return true;
}

/** [[x, y], ...] */
bool MpReadCells(const TSharedPtr<FJsonValue>& Value, TArray<FIntPoint>& Out) {
  Out.Reset();
  const TArray<TSharedPtr<FJsonValue>>* Items = nullptr;
  if (!Value.IsValid() || !Value->TryGetArray(Items) || !Items) return false;
  for (const TSharedPtr<FJsonValue>& Item : *Items) {
    FIntPoint Cell(-1, -1);
    if (!MpReadCell(Item, Cell)) return false;
    Out.Add(Cell);
  }
  return true;
}

/** {x, y} object */
bool MpReadXY(const TSharedPtr<FJsonValue>& Value, FIntPoint& Out) {
  const TSharedPtr<FJsonObject>* XY = nullptr;
  if (!Value.IsValid() || !Value->TryGetObject(XY) || !XY || !XY->IsValid()) return false;
  int32 X = 0, Y = 0;
  if (!MpIsInt((*XY)->TryGetField(TEXT("x")), X) || !MpIsInt((*XY)->TryGetField(TEXT("y")), Y)) return false;
  Out = FIntPoint(X, Y);
  return true;
}

FString MpCellsText(const TArray<FIntPoint>& Cells) {
  TArray<FString> Parts;
  for (const FIntPoint& Cell : Cells) Parts.Add(FString::Printf(TEXT("(%d,%d)"), Cell.X, Cell.Y));
  return Parts.Num() ? FString::Join(Parts, TEXT(" ")) : FString(TEXT("-"));
}

TArray<FIntPoint> MpSortedYX(TArray<FIntPoint> Cells) {
  Cells.Sort([](const FIntPoint& A, const FIntPoint& B) { return A.Y != B.Y ? A.Y < B.Y : A.X < B.X; });
  return Cells;
}

// ---- board: the boardState the server ships ---------------------------------

TSharedRef<FJsonObject> MpXYJson(int32 X, int32 Y) {
  TSharedRef<FJsonObject> Object = MakeShared<FJsonObject>();
  Object->SetNumberField(TEXT("x"), X);
  Object->SetNumberField(TEXT("y"), Y);
  return Object;
}

/** backend GameInitializationService.buildBoardState over Board.cells rows:
 *  size = max x / y + 1; holes are 'normal' on a grid and 'obstacle' on a
 *  topology board (any row carries a `links` array); type from isObstacle;
 *  zones + zone; spaceId / layout / start / links copied when valid (links
 *  outside the lattice dropped) - topologyCellFields. */
bool MpBoardStateFromRows(const TArray<TSharedPtr<FJsonObject>>& Rows, TSharedPtr<FJsonValue>& OutState,
                          FString& OutError) {
  int32 MaxX = -1, MaxY = -1;
  bool bTopology = false;
  for (const TSharedPtr<FJsonObject>& Row : Rows) {
    int32 X = -1, Y = -1;
    if (!Row.IsValid() || !MpIsInt(Row->TryGetField(TEXT("x")), X) || !MpIsInt(Row->TryGetField(TEXT("y")), Y) ||
        X < 0 || Y < 0) {
      OutError = TEXT("a board row without integer x/y >= 0");
      return false;
    }
    MaxX = FMath::Max(MaxX, X);
    MaxY = FMath::Max(MaxY, Y);
    const TArray<TSharedPtr<FJsonValue>>* Links = nullptr;
    if (Row->TryGetArrayField(TEXT("links"), Links)) bTopology = true;
  }
  if (MaxX < 0 || MaxY < 0) {
    OutError = TEXT("no board rows");
    return false;
  }
  const int32 W = MaxX + 1;
  const int32 H = MaxY + 1;
  TArray<TSharedPtr<FJsonObject>> Grid;
  Grid.SetNum(W * H);
  for (int32 Y = 0; Y < H; ++Y) {
    for (int32 X = 0; X < W; ++X) {
      TSharedRef<FJsonObject> Hole = MpXYJson(X, Y);
      Hole->SetStringField(TEXT("type"), bTopology ? TEXT("obstacle") : TEXT("normal"));
      Grid[Y * W + X] = Hole;
    }
  }
  for (const TSharedPtr<FJsonObject>& Row : Rows) {
    int32 X = 0, Y = 0;
    MpIsInt(Row->TryGetField(TEXT("x")), X);
    MpIsInt(Row->TryGetField(TEXT("y")), Y);
    bool bObstacle = false;
    Row->TryGetBoolField(TEXT("isObstacle"), bObstacle);
    TSharedRef<FJsonObject> Cell = MpXYJson(X, Y);
    Cell->SetStringField(TEXT("type"), bObstacle ? TEXT("obstacle") : TEXT("normal"));
    const TArray<TSharedPtr<FJsonValue>>* Zones = nullptr;
    if (Row->TryGetArrayField(TEXT("zones"), Zones) && Zones && Zones->Num() > 0) {
      TArray<TSharedPtr<FJsonValue>> Names;
      for (const TSharedPtr<FJsonValue>& Zone : *Zones) {
        FString Name;
        if (Zone.IsValid() && Zone->TryGetString(Name)) Names.Add(MakeShared<FJsonValueString>(Name));
      }
      if (Names.Num() > 0) {
        Cell->SetArrayField(TEXT("zones"), Names);
        Cell->SetStringField(TEXT("zone"), Names[0]->AsString());
      }
    }
    FString SpaceId;
    if (Row->TryGetStringField(TEXT("spaceId"), SpaceId) && !SpaceId.IsEmpty()) {
      Cell->SetStringField(TEXT("spaceId"), SpaceId);
    }
    const TSharedPtr<FJsonObject>* Layout = nullptr;
    double Lx = 0.0, Ly = 0.0;
    if (Row->TryGetObjectField(TEXT("layout"), Layout) && Layout && Layout->IsValid() &&
        (*Layout)->TryGetNumberField(TEXT("x"), Lx) && (*Layout)->TryGetNumberField(TEXT("y"), Ly) &&
        FMath::IsFinite(Lx) && FMath::IsFinite(Ly)) {
      TSharedRef<FJsonObject> L = MakeShared<FJsonObject>();
      L->SetNumberField(TEXT("x"), Lx);
      L->SetNumberField(TEXT("y"), Ly);
      Cell->SetObjectField(TEXT("layout"), L);
    }
    int32 Start = 0;
    if (MpIsInt(Row->TryGetField(TEXT("start")), Start) && Start >= 1 && Start <= 4) {
      Cell->SetNumberField(TEXT("start"), Start);
    }
    const TArray<TSharedPtr<FJsonValue>>* Links = nullptr;
    if (Row->TryGetArrayField(TEXT("links"), Links) && Links) {
      TArray<TSharedPtr<FJsonValue>> Kept;
      for (const TSharedPtr<FJsonValue>& Link : *Links) {
        FIntPoint P(-1, -1);
        if (MpReadXY(Link, P) && P.X >= 0 && P.Y >= 0 && P.X < W && P.Y < H) {
          Kept.Add(MakeShared<FJsonValueObject>(MpXYJson(P.X, P.Y)));
        }
      }
      Cell->SetArrayField(TEXT("links"), Kept);
    }
    Grid[Y * W + X] = Cell;
  }
  TArray<TSharedPtr<FJsonValue>> Lines;
  for (int32 Y = 0; Y < H; ++Y) {
    TArray<TSharedPtr<FJsonValue>> Line;
    for (int32 X = 0; X < W; ++X) Line.Add(MakeShared<FJsonValueObject>(Grid[Y * W + X]));
    Lines.Add(MakeShared<FJsonValueArray>(Line));
  }
  TSharedRef<FJsonObject> Board = MakeShared<FJsonObject>();
  Board->SetNumberField(TEXT("width"), W);
  Board->SetNumberField(TEXT("height"), H);
  Board->SetArrayField(TEXT("cells"), Lines);
  Board->SetObjectField(TEXT("doors"), MakeShared<FJsonObject>());
  OutState = MakeShared<FJsonValueObject>(Board);
  return true;
}

/** move-fixture-state latticeRow: every cell a space, walls = isObstacle,
 *  `edges` (even empty) give every cell a `links` array -> topology board. */
bool MpLatticeRows(const TSharedPtr<FJsonObject>& Lattice, TArray<TSharedPtr<FJsonObject>>& OutRows,
                   FString& OutError) {
  int32 W = 0, H = 0;
  if (!MpIsInt(Lattice->TryGetField(TEXT("width")), W) || !MpIsInt(Lattice->TryGetField(TEXT("height")), H) ||
      W <= 0 || H <= 0) {
    OutError = TEXT("lattice without width/height");
    return false;
  }
  TSet<FIntPoint> Walls;
  const TArray<TSharedPtr<FJsonValue>>* WallValues = nullptr;
  if (Lattice->TryGetArrayField(TEXT("walls"), WallValues) && WallValues) {
    for (const TSharedPtr<FJsonValue>& Value : *WallValues) {
      FIntPoint P(-1, -1);
      if (!MpReadCell(Value, P)) {
        OutError = TEXT("bad lattice wall");
        return false;
      }
      Walls.Add(P);
    }
  }
  const TArray<TSharedPtr<FJsonValue>>* EdgeValues = nullptr;
  const bool bEdges = Lattice->TryGetArrayField(TEXT("edges"), EdgeValues) && EdgeValues;
  TMap<FIntPoint, TArray<FIntPoint>> Links;
  if (bEdges) {
    for (const TSharedPtr<FJsonValue>& Edge : *EdgeValues) {
      const TArray<TSharedPtr<FJsonValue>>* Ends = nullptr;
      FIntPoint A(-1, -1), B(-1, -1);
      if (!Edge.IsValid() || !Edge->TryGetArray(Ends) || !Ends || Ends->Num() != 2 || !MpReadCell((*Ends)[0], A) ||
          !MpReadCell((*Ends)[1], B)) {
        OutError = TEXT("bad lattice edge");
        return false;
      }
      Links.FindOrAdd(A).Add(B);
      Links.FindOrAdd(B).Add(A);
    }
  }
  OutRows.Reset();
  for (int32 Y = 0; Y < H; ++Y) {
    for (int32 X = 0; X < W; ++X) {
      TSharedRef<FJsonObject> Row = MpXYJson(X, Y);
      if (Walls.Contains(FIntPoint(X, Y))) Row->SetBoolField(TEXT("isObstacle"), true);
      if (bEdges) {
        TArray<TSharedPtr<FJsonValue>> L;
        if (const TArray<FIntPoint>* Found = Links.Find(FIntPoint(X, Y))) {
          for (const FIntPoint& P : *Found) L.Add(MakeShared<FJsonValueObject>(MpXYJson(P.X, P.Y)));
        }
        Row->SetArrayField(TEXT("links"), L);
      }
      OutRows.Add(Row);
    }
  }
  return true;
}

/** Board.cells rows of a committed topology fixture (unmatched.board-topology/1). */
bool MpTopologyRows(const FString& Key, TArray<TSharedPtr<FJsonObject>>& OutRows, FString& OutError) {
  const FString Path = MpTopologyPath(Key);
  TSharedPtr<FJsonObject> Topology;
  if (!MpLoadJson(Path, Topology)) {
    OutError = FString::Printf(TEXT("topology fixture %s not readable"), *Path);
    return false;
  }
  const TArray<TSharedPtr<FJsonValue>>* Cells = nullptr;
  if (!Topology->TryGetArrayField(TEXT("cells"), Cells) || !Cells) {
    OutError = FString::Printf(TEXT("%s has no cells"), *Path);
    return false;
  }
  OutRows.Reset();
  for (const TSharedPtr<FJsonValue>& Value : *Cells) {
    const TSharedPtr<FJsonObject>* Row = nullptr;
    if (!Value.IsValid() || !Value->TryGetObject(Row) || !Row || !Row->IsValid()) {
      OutError = FString::Printf(TEXT("%s: a cell is not an object"), *Path);
      return false;
    }
    OutRows.Add(*Row);
  }
  return true;
}

bool MpDecodeRows(const TArray<TSharedPtr<FJsonObject>>& Rows, FS08BoardModel& OutBoard, FString& OutError) {
  TSharedPtr<FJsonValue> State;
  if (!MpBoardStateFromRows(Rows, State, OutError)) return false;
  if (!OutBoard.Decode(State)) {
    OutError = TEXT("FS08BoardModel::Decode rejected the boardState");
    return false;
  }
  return true;
}

/** Fixture `board` -> decoded model; topology maps are cached per key. */
bool MpFixtureBoard(const TSharedPtr<FJsonObject>& BoardSpec, TMap<FString, FS08BoardModel>& Cache,
                    FS08BoardModel& OutBoard, FString& OutKey, FString& OutError) {
  if (!BoardSpec.IsValid() || !BoardSpec->TryGetStringField(TEXT("key"), OutKey) || OutKey.IsEmpty()) {
    OutError = TEXT("board.key missing");
    return false;
  }
  const TSharedPtr<FJsonObject>* Lattice = nullptr;
  TArray<TSharedPtr<FJsonObject>> Rows;
  if (BoardSpec->TryGetObjectField(TEXT("lattice"), Lattice) && Lattice && Lattice->IsValid()) {
    return MpLatticeRows(*Lattice, Rows, OutError) && MpDecodeRows(Rows, OutBoard, OutError);
  }
  if (const FS08BoardModel* Cached = Cache.Find(OutKey)) {
    OutBoard = *Cached;
    return true;
  }
  if (!MpTopologyRows(OutKey, Rows, OutError) || !MpDecodeRows(Rows, OutBoard, OutError)) return false;
  if (!OutBoard.bHasTopology) {
    OutError = FString::Printf(TEXT("%s: decoded without topology"), *OutKey);
    return false;
  }
  Cache.Add(OutKey, OutBoard);
  return true;
}

// ---- fighters: the projection buildMoveFixtureState ships -------------------

/** engineFighter: health ?? 10, maxHealth ?? max(health, 10), type ?? (first
 *  of its owner ? HERO : MINION), effects [{type}], isDefeated ?? false, raw
 *  movement only when the key is present. Decoded by DecodeFighters, so the
 *  raw-movement and isDefeated decode are under test too. */
bool MpFixtureFighters(const TArray<TSharedPtr<FJsonValue>>& Specs, TArray<FS08BoardFighter>& Out,
                       FString& OutError) {
  TArray<TSharedPtr<FJsonValue>> Projection;
  TArray<FString> Owners;
  for (const TSharedPtr<FJsonValue>& Value : Specs) {
    const TSharedPtr<FJsonObject>* SpecPtr = nullptr;
    if (!Value.IsValid() || !Value->TryGetObject(SpecPtr) || !SpecPtr || !SpecPtr->IsValid()) {
      OutError = TEXT("a fighter is not an object");
      return false;
    }
    const TSharedPtr<FJsonObject>& Spec = *SpecPtr;
    FString Id, Owner;
    FIntPoint Pos(-1, -1);
    if (!Spec->TryGetStringField(TEXT("id"), Id) || !Spec->TryGetStringField(TEXT("ownerId"), Owner) ||
        !MpReadXY(Spec->TryGetField(TEXT("position")), Pos)) {
      OutError = TEXT("a fighter without id/ownerId/position");
      return false;
    }
    const bool bFirstOfOwner = !Owners.ContainsByPredicate([&](const FString& O) { return MpSameId(O, Owner); });
    if (bFirstOfOwner) Owners.Add(Owner);
    double Health = 10.0;
    Spec->TryGetNumberField(TEXT("health"), Health);
    double MaxHealth = FMath::Max(Health, 10.0);
    Spec->TryGetNumberField(TEXT("maxHealth"), MaxHealth);
    FString Type;
    if (!Spec->TryGetStringField(TEXT("type"), Type)) Type = bFirstOfOwner ? TEXT("HERO") : TEXT("MINION");
    FString Name;
    if (!Spec->TryGetStringField(TEXT("name"), Name)) Name = Id;

    TSharedRef<FJsonObject> F = MakeShared<FJsonObject>();
    F->SetStringField(TEXT("id"), Id);
    F->SetStringField(TEXT("ownerId"), Owner);
    F->SetStringField(TEXT("heroId"), TEXT("hero-") + Owner);
    F->SetStringField(TEXT("name"), Name);
    F->SetStringField(TEXT("type"), Type == TEXT("HERO") ? TEXT("HERO") : TEXT("MINION"));
    F->SetNumberField(TEXT("health"), Health);
    F->SetNumberField(TEXT("maxHealth"), MaxHealth);
    F->SetObjectField(TEXT("position"), MpXYJson(Pos.X, Pos.Y));
    F->SetStringField(TEXT("attackType"), TEXT("melee"));
    TArray<TSharedPtr<FJsonValue>> Effects;
    const TArray<TSharedPtr<FJsonValue>>* EffectTypes = nullptr;
    if (Spec->TryGetArrayField(TEXT("effects"), EffectTypes) && EffectTypes) {
      for (const TSharedPtr<FJsonValue>& E : *EffectTypes) {
        FString EffectType;
        if (!E.IsValid() || !E->TryGetString(EffectType)) continue;
        TSharedRef<FJsonObject> Effect = MakeShared<FJsonObject>();
        Effect->SetStringField(TEXT("type"), EffectType);
        Effects.Add(MakeShared<FJsonValueObject>(Effect));
      }
    }
    F->SetArrayField(TEXT("effects"), Effects);
    TSharedPtr<FJsonValue> Defeated = Spec->TryGetField(TEXT("isDefeated"));
    if (!Defeated.IsValid()) Defeated = MakeShared<FJsonValueBoolean>(false);
    F->SetField(TEXT("isDefeated"), Defeated);
    F->SetBoolField(TEXT("hasSidekick"), false);
    const TSharedPtr<FJsonValue> Movement = Spec->TryGetField(TEXT("movement"));
    if (Movement.IsValid()) F->SetField(TEXT("movement"), Movement); // raw: number, string or null
    Projection.Add(MakeShared<FJsonValueObject>(F));
  }
  if (!FS08BoardModel::DecodeFighters(MakeShared<FJsonValueArray>(Projection), Out)) {
    OutError = TEXT("DecodeFighters failed");
    return false;
  }
  return true;
}

const FS08BoardFighter* MpFind(const TArray<FS08BoardFighter>& Fighters, const FString& Id) {
  for (const FS08BoardFighter& F : Fighters) {
    if (MpSameId(F.Id, Id)) return &F;
  }
  return nullptr;
}

// ---- the client result of one fixture ---------------------------------------

struct FMpGot {
  FString FighterId;
  TArray<FIntPoint> Base;
  TArray<FIntPoint> Boost;
  bool bPath = false; // false = null (Conflict)
  TArray<FIntPoint> Path;
  FString Status;
  int32 Required = 0;
};

const FMpGot* MpGotFor(const TArray<FMpGot>& Got, const FString& Id) {
  return Got.FindByPredicate([&](const FMpGot& G) { return MpSameId(G.FighterId, Id); });
}

/** Tiers of 04 §3.2 / backend reachTiers: endpoints up to BaseSteps, then up to BoostSteps. */
void MpTiers(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters, const FS08ReachMap& Reach,
             int32 BaseSteps, int32 BoostSteps, FMpGot& Out) {
  for (const FIntPoint& Cell :
       FS08BoardModel::ReachEndpoints(Board, Fighters, Reach, FMath::Max(BaseSteps, BoostSteps))) {
    const int32 D = Reach.DistanceTo(Cell);
    if (D <= BaseSteps) {
      Out.Base.Add(Cell);
    } else if (D <= BoostSteps) {
      Out.Boost.Add(Cell);
    }
  }
}

struct FMpCard {
  FString Id;
  bool bHasBoost = false; // backend cardBoost: a finite number, else null
  int32 Boost = 0;
};

/** The draft of a fixture through the client evaluator FS09DraftEval (MS-T-05,
 *  backend evaluateDraft): moves in the order of draft.moves on the positions
 *  after the previous moves, base = FighterMovement, reach with
 *  base + max(selected, max hand BOOST), tiers, canonical path, required
 *  BOOST. A repeated fighter keeps its first entry (computeFixtureExpect). */
bool MpEvaluateDraft(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Initial,
                     const TSharedPtr<FJsonObject>& Draft, const TArray<FMpCard>& Hand, const FString& Actor,
                     TArray<FMpGot>& Out, FString& OutError) {
  FString BoostCardId;
  Draft->TryGetStringField(TEXT("boostCardId"), BoostCardId);
  const TArray<TSharedPtr<FJsonValue>>* Moves = nullptr;
  if (!Draft->TryGetArrayField(TEXT("moves"), Moves) || !Moves) {
    OutError = TEXT("draft.moves missing");
    return false;
  }
  TArray<FS09DraftMove> DraftMoves;
  for (const TSharedPtr<FJsonValue>& MoveValue : *Moves) {
    const TSharedPtr<FJsonObject>* MovePtr = nullptr;
    FString Id;
    if (!MoveValue.IsValid() || !MoveValue->TryGetObject(MovePtr) || !MovePtr ||
        !(*MovePtr)->TryGetStringField(TEXT("fighterId"), Id)) {
      OutError = TEXT("a draft move without fighterId");
      return false;
    }
    const TSharedPtr<FJsonObject>& Move = *MovePtr;
    // draftInputOf: dest, else the last forced path cell, else the INITIAL position.
    FIntPoint Dest(-1, -1);
    if (!MpReadXY(Move->TryGetField(TEXT("dest")), Dest)) {
      const TArray<TSharedPtr<FJsonValue>>* Forced = nullptr;
      if (Move->TryGetArrayField(TEXT("path"), Forced) && Forced && Forced->Num() > 0) {
        if (!MpReadXY(Forced->Last(), Dest)) {
          OutError = TEXT("bad forced path cell");
          return false;
        }
      } else if (const FS08BoardFighter* AtStart = MpFind(Initial, Id)) {
        Dest = FIntPoint(AtStart->X, AtStart->Y);
      }
    }
    FS09DraftMove& Entry = DraftMoves.AddDefaulted_GetRef();
    Entry.FighterId = Id;
    Entry.DestX = Dest.X;
    Entry.DestY = Dest.Y;
  }
  TArray<FS09BoostCard> BoostHand;
  for (const FMpCard& Card : Hand) {
    FS09BoostCard& Boost = BoostHand.AddDefaulted_GetRef();
    Boost.InstanceId = Card.Id;
    Boost.bHasBoost = Card.bHasBoost;
    Boost.Boost = Card.Boost;
  }
  const FS09DraftEval Eval = FS09DraftEval::Evaluate(Board, Initial, DraftMoves, BoostHand, BoostCardId, Actor);
  for (int32 Index = 0; Index < DraftMoves.Num(); ++Index) {
    const FS09DraftMove& Move = DraftMoves[Index];
    if (MpGotFor(Out, Move.FighterId)) continue; // a repeated fighter keeps its first entry
    FMpGot Got;
    Got.FighterId = Move.FighterId;
    if (Eval.Tiers.IsValidIndex(Index) && Eval.Tiers[Index].bValid) {
      Got.Base = Eval.Tiers[Index].BaseTier; // the early conflicts carry no tiers
      Got.Boost = Eval.Tiers[Index].BoostTier;
    }
    Got.bPath = Move.Status != ES09DraftMoveStatus::Conflict;
    Got.Path = Move.Path;
    Got.Status = Move.Status == ES09DraftMoveStatus::Ok          ? TEXT("ok")
                 : Move.Status == ES09DraftMoveStatus::NeedBoost ? TEXT("needBoost")
                                                                 : TEXT("conflict");
    Got.Required = Move.RequiredBoost;
    Out.Add(Got);
  }
  return true;
}

/** A pending MOVE (computeFixtureExpect): allowance value ?? 1, enemies by
 *  canPassThroughEnemies, base tier only, no mover gate. */
bool MpEvaluatePendingMove(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                           const TSharedPtr<FJsonObject>& Pending, TArray<FMpGot>& Out, FString& OutError) {
  FString Id;
  FIntPoint Target(-1, -1);
  if (!Pending->TryGetStringField(TEXT("fighterId"), Id) || !MpReadXY(Pending->TryGetField(TEXT("target")), Target)) {
    OutError = TEXT("pending without fighterId/target");
    return false;
  }
  int32 Allowance = 1;
  const TSharedPtr<FJsonValue> Value = Pending->TryGetField(TEXT("value"));
  if (Value.IsValid() && Value->Type != EJson::Null && !MpIsInt(Value, Allowance)) {
    OutError = TEXT("pending.value is not an integer");
    return false;
  }
  bool bPass = false;
  Pending->TryGetBoolField(TEXT("canPassThroughEnemies"), bPass);
  FS08ReachOptions Options;
  Options.bPassThroughEnemies = bPass;
  const FS08ReachMap Reach = FS08BoardModel::ComputeReachMap(Board, Fighters, Id, Allowance, Options);
  if (!Reach.bValid) {
    OutError = FString::Printf(TEXT("pending fighter %s is not on the board"), *Id);
    return false;
  }
  FMpGot Got;
  Got.FighterId = Id;
  MpTiers(Board, Fighters, Reach, Allowance, Allowance, Got);
  Got.bPath = FS08BoardModel::BuildCanonicalPath(Board, Fighters, Reach, Target, Got.Path);
  Got.Status = Got.bPath ? TEXT("ok") : TEXT("conflict");
  Got.Required = 0;
  Out.Add(Got);
  return true;
}

/** MS-T-12: a pending PLACE of the fixture through FS09CommandUi (the MS-S-12 spaces): is `target` legal, and the
 *  why.* of a refused one (PendingCellReason). */
bool MpEvaluatePendingPlace(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                            const TSharedPtr<FJsonObject>& Pending, bool& bOutLegal, FString& OutWhy, FString& OutError) {
  FString Id, Owner;
  FIntPoint Target(-1, -1);
  if (!Pending->TryGetStringField(TEXT("fighterId"), Id) || !Pending->TryGetStringField(TEXT("ownerId"), Owner) ||
      !MpReadXY(Pending->TryGetField(TEXT("target")), Target)) {
    OutError = TEXT("pending PLACE without fighterId/ownerId/target");
    return false;
  }
  FS09CommandUi Ui;
  Ui.ViewerId = Owner;
  Ui.Mode = ES09CommandMode::PendingChoice;
  Ui.bHasPendingChoice = true;
  Ui.PendingChoice.Id = TEXT("parity");
  Ui.PendingChoice.PlayerId = Owner;
  Ui.PendingChoice.Type = TEXT("PLACE");
  Pending->TryGetStringField(TEXT("zoneFighterName"), Ui.PendingChoice.ZoneFighterName);
  Pending->TryGetBoolField(TEXT("optional"), Ui.PendingChoice.bOptional);
  Pending->TryGetBoolField(TEXT("restoreFullHealth"), Ui.PendingChoice.bRestoreFullHealth);
  Pending->TryGetBoolField(TEXT("targetsOpponent"), Ui.PendingChoice.bTargetsOpponent);
  Ui.PendingChoice.FighterIds.Add(Id);
  Ui.PendingFighterId = Id;
  TArray<FString> Legal;
  Ui.PendingLegalFighters(Fighters, Legal);
  if (!Legal.Contains(Id)) {
    OutError = FString::Printf(TEXT("PLACE fighter %s is not a legal pick of the client"), *Id);
    return false;
  }
  bOutLegal = Ui.ComputePendingCells(FS08Snapshot(), Board, Fighters).Contains(FS08BoardModel::CellKey(Target.X, Target.Y));
  OutWhy = bOutLegal ? FString() : Ui.PendingCellReason(Target.X, Target.Y, Board, Fighters).Key.ToString();
  return true;
}

// ---- comparison with `expect` -----------------------------------------------

struct FMpCounters {
  int32 Reach = 0;
  int32 Paths = 0;
  int32 Status = 0;
  int32 Required = 0;
};

/** Keys of an expect.<field> object (fighter ids). */
TArray<FString> MpKeys(const TSharedPtr<FJsonObject>& Object) {
  TArray<FString> Keys;
  if (!Object.IsValid()) return Keys;
  for (const auto& Entry : Object->Values) Keys.Add(FString(*Entry.Key)); // FSharedString keys in UE 5.8
  return Keys;
}

void MpCheckKeys(const FString& Field, const TSharedPtr<FJsonObject>& Want, const TArray<FMpGot>& Got,
                 TArray<FString>& Errors) {
  const TArray<FString> Keys = MpKeys(Want);
  for (const FMpGot& G : Got) {
    if (!Keys.ContainsByPredicate([&](const FString& K) { return MpSameId(K, G.FighterId); })) {
      Errors.Add(FString::Printf(TEXT("%s: client has %s, expect does not"), *Field, *G.FighterId));
    }
  }
  for (const FString& K : Keys) {
    if (!MpGotFor(Got, K)) Errors.Add(FString::Printf(TEXT("%s: expect has %s, client does not"), *Field, *K));
  }
}

/** expect.<Field>: absent -> null; present but not an object -> an error (never a silent pass). */
TSharedPtr<FJsonObject> MpExpectObject(const TSharedPtr<FJsonObject>& Expect, const TCHAR* Field,
                                       TArray<FString>& Errors) {
  const TSharedPtr<FJsonValue> Value = Expect->TryGetField(Field);
  if (!Value.IsValid()) return nullptr;
  const TSharedPtr<FJsonObject>* Object = nullptr;
  if (!Value->TryGetObject(Object) || !Object || !Object->IsValid()) {
    Errors.Add(FString::Printf(TEXT("%s: not an object"), Field));
    return nullptr;
  }
  return *Object;
}

void MpCompare(const TSharedPtr<FJsonObject>& Expect, const TArray<FMpGot>& Got, FMpCounters& Count,
               TArray<FString>& Errors) {
  if (const TSharedPtr<FJsonObject> Reach = MpExpectObject(Expect, TEXT("reach"), Errors)) {
    MpCheckKeys(TEXT("reach"), Reach, Got, Errors);
    for (const FString& Key : MpKeys(Reach)) {
      const TSharedPtr<FJsonValue> Value = Reach->TryGetField(Key);
      const FMpGot* G = MpGotFor(Got, Key);
      const TSharedPtr<FJsonObject>* Tiers = nullptr;
      TArray<FIntPoint> WantBase, WantBoost;
      if (!Value.IsValid() || !Value->TryGetObject(Tiers) || !Tiers ||
          !MpReadCells((*Tiers)->TryGetField(TEXT("base")), WantBase) ||
          !MpReadCells((*Tiers)->TryGetField(TEXT("boost")), WantBoost)) {
        Errors.Add(FString::Printf(TEXT("reach.%s: malformed"), *Key));
        continue;
      }
      if (!G) continue; // reported by MpCheckKeys
      ++Count.Reach;
      // Sets: order-free (the fixture lists are not sorted by K).
      if (MpSortedYX(WantBase) != MpSortedYX(G->Base)) {
        Errors.Add(FString::Printf(TEXT("reach.%s.base: want {%s} got {%s}"), *Key,
                                   *MpCellsText(MpSortedYX(WantBase)), *MpCellsText(MpSortedYX(G->Base))));
      }
      if (MpSortedYX(WantBoost) != MpSortedYX(G->Boost)) {
        Errors.Add(FString::Printf(TEXT("reach.%s.boost: want {%s} got {%s}"), *Key,
                                   *MpCellsText(MpSortedYX(WantBoost)), *MpCellsText(MpSortedYX(G->Boost))));
      }
    }
  }
  if (const TSharedPtr<FJsonObject> Paths = MpExpectObject(Expect, TEXT("paths"), Errors)) {
    MpCheckKeys(TEXT("paths"), Paths, Got, Errors);
    for (const FString& Key : MpKeys(Paths)) {
      const TSharedPtr<FJsonValue> Value = Paths->TryGetField(Key);
      const bool bWantNull = !Value.IsValid() || Value->IsNull();
      TArray<FIntPoint> Want;
      if (!bWantNull && !MpReadCells(Value, Want)) {
        Errors.Add(FString::Printf(TEXT("paths.%s: malformed"), *Key));
        continue;
      }
      const FMpGot* G = MpGotFor(Got, Key);
      if (!G) continue; // reported by MpCheckKeys
      ++Count.Paths;
      // Exact: order matters, null (Conflict) differs from [] (stay).
      if (bWantNull != !G->bPath || (!bWantNull && Want != G->Path)) {
        Errors.Add(FString::Printf(TEXT("paths.%s: want %s got %s"), *Key,
                                   bWantNull ? TEXT("null") : *FString::Printf(TEXT("[%s]"), *MpCellsText(Want)),
                                   G->bPath ? *FString::Printf(TEXT("[%s]"), *MpCellsText(G->Path)) : TEXT("null")));
      }
    }
  }
  if (const TSharedPtr<FJsonObject> Status = MpExpectObject(Expect, TEXT("status"), Errors)) {
    MpCheckKeys(TEXT("status"), Status, Got, Errors);
    for (const FString& Key : MpKeys(Status)) {
      const TSharedPtr<FJsonValue> Value = Status->TryGetField(Key);
      FString Want;
      if (!Value.IsValid() || Value->Type != EJson::String || !Value->TryGetString(Want)) {
        Errors.Add(FString::Printf(TEXT("status.%s: malformed"), *Key));
        continue;
      }
      const FMpGot* G = MpGotFor(Got, Key);
      if (!G) continue; // reported by MpCheckKeys
      ++Count.Status;
      if (!Want.Equals(G->Status, ESearchCase::CaseSensitive)) {
        Errors.Add(FString::Printf(TEXT("status.%s: want %s got %s"), *Key, *Want, *G->Status));
      }
    }
  }
  if (const TSharedPtr<FJsonObject> Required = MpExpectObject(Expect, TEXT("requiredBoost"), Errors)) {
    MpCheckKeys(TEXT("requiredBoost"), Required, Got, Errors);
    for (const FString& Key : MpKeys(Required)) {
      int32 Want = 0;
      if (!MpIsInt(Required->TryGetField(Key), Want)) {
        Errors.Add(FString::Printf(TEXT("requiredBoost.%s: malformed"), *Key));
        continue;
      }
      const FMpGot* G = MpGotFor(Got, Key);
      if (!G) continue; // reported by MpCheckKeys
      ++Count.Required;
      if (Want != G->Required) {
        Errors.Add(FString::Printf(TEXT("requiredBoost.%s: want %d got %d"), *Key, Want, G->Required));
      }
    }
  }
}

// ---- synthetic boards for the unit tests ------------------------------------

/** Plain grid W x H (walls = obstacle), decoded through the server shape.
 *  Synthetic boards exercise the model only: the server's MIN/MAX_GRID_SIZE
 *  fallback (2..50, game-initialization.service.ts) is not mirrored, so the
 *  1-row corridors below are boards it would never ship. */
bool MpGrid(int32 W, int32 H, std::initializer_list<FIntPoint> Walls, FS08BoardModel& OutBoard) {
  TArray<TSharedPtr<FJsonObject>> Rows;
  for (int32 Y = 0; Y < H; ++Y) {
    for (int32 X = 0; X < W; ++X) {
      TSharedRef<FJsonObject> Row = MpXYJson(X, Y);
      for (const FIntPoint& Wall : Walls) {
        if (Wall == FIntPoint(X, Y)) Row->SetBoolField(TEXT("isObstacle"), true);
      }
      Rows.Add(Row);
    }
  }
  FString Error;
  return MpDecodeRows(Rows, OutBoard, Error);
}

struct FMpSpace {
  const TCHAR* Id;
  FIntPoint Pos;
};

struct FMpEdge {
  const TCHAR* A;
  const TCHAR* B;
};

/** Topology board from spaces and undirected edges by id; every other
 *  lattice position is an obstacle hole. bReversed reverses every link list
 *  (the result must not depend on it). */
bool MpGraph(int32 W, int32 H, std::initializer_list<FMpSpace> Spaces,
             std::initializer_list<FMpEdge> Edges, bool bReversed, FS08BoardModel& OutBoard) {
  TMap<FString, FIntPoint> Pos;
  for (const FMpSpace& S : Spaces) Pos.Add(S.Id, S.Pos);
  TMap<FString, TArray<FIntPoint>> Links;
  for (const FMpEdge& E : Edges) {
    Links.FindOrAdd(E.A).Add(Pos.FindChecked(E.B));
    Links.FindOrAdd(E.B).Add(Pos.FindChecked(E.A));
  }
  TArray<TSharedPtr<FJsonObject>> Rows;
  for (int32 Y = 0; Y < H; ++Y) {
    for (int32 X = 0; X < W; ++X) {
      TSharedRef<FJsonObject> Row = MpXYJson(X, Y);
      const FMpSpace* Space = nullptr;
      for (const FMpSpace& S : Spaces) {
        if (S.Pos == FIntPoint(X, Y)) Space = &S;
      }
      if (!Space) {
        Row->SetBoolField(TEXT("isObstacle"), true);
      } else {
        Row->SetStringField(TEXT("spaceId"), Space->Id);
        TArray<FIntPoint> L = Links.FindRef(Space->Id);
        if (bReversed) Algo::Reverse(L);
        TArray<TSharedPtr<FJsonValue>> Values;
        for (const FIntPoint& P : L) Values.Add(MakeShared<FJsonValueObject>(MpXYJson(P.X, P.Y)));
        Row->SetArrayField(TEXT("links"), Values);
      }
      Rows.Add(Row);
    }
  }
  FString Error;
  return MpDecodeRows(Rows, OutBoard, Error) && OutBoard.bHasTopology;
}

FS08BoardFighter MpFighter(const TCHAR* Id, const TCHAR* Owner, int32 X, int32 Y, int32 Health = 10,
                           bool bDefeated = false) {
  FS08BoardFighter F;
  F.Id = Id;
  F.OwnerId = Owner;
  F.Name = Id;
  F.Label = Id;
  F.Health = Health;
  F.MaxHealth = 10;
  F.X = X;
  F.Y = Y;
  F.bDefeated = bDefeated;
  F.SetRawMovement(2);
  F.AttackType = TEXT("melee");
  return F;
}

TArray<FIntPoint> MpPath(std::initializer_list<FIntPoint> Cells) { return TArray<FIntPoint>(Cells); }

/** Pre-MS-T-03 ComputeReachableCells (stack frontier with relaxation over
 *  Board.Neighbours) - the oracle of the legacy wrapper. Verbatim except that
 *  IsStepTraversable / IsEndpointFree now go through the new FighterAt, so
 *  this oracle says nothing about the MS-E-24 role split (AlivePredicates
 *  pins that). */
TSet<uint64> MpLegacyReachable(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                               const FString& FighterId, int32 Allowance) {
  TSet<uint64> Reachable;
  const FS08BoardFighter* Mover = MpFind(Fighters, FighterId);
  if (!Mover || !Mover->IsAlive() || Allowance < 0) return Reachable;
  Reachable.Add(FS08BoardModel::CellKey(Mover->X, Mover->Y));
  struct FNode {
    int32 X, Y, Steps;
  };
  TMap<uint64, int32> Best;
  TArray<FNode> Frontier;
  Frontier.Push({Mover->X, Mover->Y, 0});
  Best.Add(FS08BoardModel::CellKey(Mover->X, Mover->Y), 0);
  while (Frontier.Num() > 0) {
    const FNode Node = Frontier.Pop(EAllowShrinking::No);
    if (Node.Steps >= Allowance) continue;
    for (const FIntPoint& Next : Board.Neighbours(FIntPoint(Node.X, Node.Y))) {
      if (!FS08BoardModel::IsStepTraversable(Board, Fighters, *Mover, Next.X, Next.Y)) continue;
      const uint64 Key = FS08BoardModel::CellKey(Next.X, Next.Y);
      const int32 NewSteps = Node.Steps + 1;
      if (const int32* Existing = Best.Find(Key)) {
        if (*Existing <= NewSteps) continue;
      }
      Best.Add(Key, NewSteps);
      Frontier.Push({Next.X, Next.Y, NewSteps});
      if (FS08BoardModel::IsEndpointFree(Fighters, *Mover, Next.X, Next.Y)) Reachable.Add(Key);
    }
  }
  return Reachable;
}

/** Pre-MS-T-03 BuildManeuverPath (same frontier, reverse walk over
 *  Board.Neighbours taking the first neighbour one step closer); verbatim
 *  except the FighterAt note above. */
bool MpLegacyPath(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters, const FString& FighterId,
                  int32 Allowance, int32 TargetX, int32 TargetY, TArray<FIntPoint>& OutPath) {
  OutPath.Reset();
  const FS08BoardFighter* Mover = MpFind(Fighters, FighterId);
  if (!Mover || !Mover->IsAlive() || Allowance < 0) return false;
  if (TargetX == Mover->X && TargetY == Mover->Y) return true;
  struct FNode {
    int32 X, Y, Steps;
  };
  TMap<uint64, int32> Best;
  TArray<FNode> Frontier;
  Frontier.Push({Mover->X, Mover->Y, 0});
  Best.Add(FS08BoardModel::CellKey(Mover->X, Mover->Y), 0);
  while (Frontier.Num() > 0) {
    const FNode Node = Frontier.Pop(EAllowShrinking::No);
    if (Node.Steps >= Allowance) continue;
    for (const FIntPoint& Next : Board.Neighbours(FIntPoint(Node.X, Node.Y))) {
      if (!FS08BoardModel::IsStepTraversable(Board, Fighters, *Mover, Next.X, Next.Y)) continue;
      const uint64 Key = FS08BoardModel::CellKey(Next.X, Next.Y);
      const int32 NewSteps = Node.Steps + 1;
      if (const int32* Existing = Best.Find(Key)) {
        if (*Existing <= NewSteps) continue;
      }
      Best.Add(Key, NewSteps);
      Frontier.Push({Next.X, Next.Y, NewSteps});
    }
  }
  const int32* TargetSteps = Best.Find(FS08BoardModel::CellKey(TargetX, TargetY));
  if (!TargetSteps) return false;
  TArray<FIntPoint> Reversed;
  FIntPoint Current(TargetX, TargetY);
  int32 Steps = *TargetSteps;
  while (Steps > 0) {
    Reversed.Add(Current);
    --Steps;
    bool bAdvanced = false;
    for (const FIntPoint& Prev : Board.Neighbours(Current)) {
      const int32* PrevSteps = Best.Find(FS08BoardModel::CellKey(Prev.X, Prev.Y));
      if (PrevSteps && *PrevSteps == Steps) {
        Current = Prev;
        bAdvanced = true;
        break;
      }
    }
    if (!bAdvanced) return false;
  }
  for (int32 Index = Reversed.Num() - 1; Index >= 0; --Index) OutPath.Add(Reversed[Index]);
  return OutPath.Num() > 0;
}

/** A path WITHOUT the start is a chain of board neighbours from Start. */
bool MpIsStepChain(const FS08BoardModel& Board, const FIntPoint& Start, const TArray<FIntPoint>& Path) {
  FIntPoint Prev = Start;
  for (const FIntPoint& Cell : Path) {
    if (!Board.Neighbours(Prev).Contains(Cell)) return false;
    Prev = Cell;
  }
  return true;
}

} // namespace S08MoveParityTest

using namespace S08MoveParityTest;

// ---------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MoveParityGoldenFixturesTest, "Unmatched.S08.MoveParity.GoldenFixtures",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MoveParityGoldenFixturesTest::RunTest(const FString&) {
  const FString Dir = MpMoveFixtureDir();
  TArray<FString> Files;
  IFileManager::Get().FindFiles(Files, *FPaths::Combine(Dir, FString(TEXT("*")) + MpSuffix), true, false);
  Files.Sort();
  if (!TestTrue(FString::Printf(TEXT("golden fixtures found in %s"), *Dir), Files.Num() > 0)) return false;

  TMap<FString, FS08BoardModel> BoardCache;
  FMpCounters Count;
  int32 Checked = 0, CheckedManual = 0, CheckedGenerated = 0, CheckedDraft = 0, CheckedPending = 0, CheckedPlace = 0;
  int32 Errored = 0, Mismatched = 0, Manual = 0;
  TMap<FString, int32> SkipReasons;
  TArray<FString> Skipped;
  TMap<FString, int32> BoardCounts;
  for (const FString& File : Files) {
    const FString Name = File.LeftChop(FCString::Strlen(MpSuffix));
    TSharedPtr<FJsonObject> Fx;
    if (!MpLoadJson(FPaths::Combine(Dir, File), Fx)) {
      AddError(FString::Printf(TEXT("%s: not readable JSON"), *File));
      ++Errored;
      continue;
    }
    FString Schema, FxName, Source;
    Fx->TryGetStringField(TEXT("schema"), Schema);
    Fx->TryGetStringField(TEXT("name"), FxName);
    Fx->TryGetStringField(TEXT("expectSource"), Source);
    if (!Schema.Equals(MpSchema, ESearchCase::CaseSensitive) || !FxName.Equals(Name, ESearchCase::CaseSensitive)) {
      AddError(FString::Printf(TEXT("%s: schema '%s' / name '%s' do not match %s / the file"), *File, *Schema,
                               *FxName, MpSchema));
      ++Errored;
      continue;
    }
    if (Source == TEXT("manual")) ++Manual;
    const TSharedPtr<FJsonObject>* ExpectPtr = nullptr;
    if (!Fx->TryGetObjectField(TEXT("expect"), ExpectPtr) || !ExpectPtr || !ExpectPtr->IsValid()) {
      AddError(FString::Printf(TEXT("%s: no expect"), *Name));
      ++Errored;
      continue;
    }
    const TSharedPtr<FJsonObject> Expect = *ExpectPtr;
    const TSharedPtr<FJsonObject>* DraftPtr = nullptr;
    const TSharedPtr<FJsonObject>* PendingPtr = nullptr;
    const bool bDraft = Fx->TryGetObjectField(TEXT("draft"), DraftPtr) && DraftPtr && DraftPtr->IsValid();
    const bool bPending = Fx->TryGetObjectField(TEXT("pending"), PendingPtr) && PendingPtr && PendingPtr->IsValid();
    FString PendingType;
    if (bPending) (*PendingPtr)->TryGetStringField(TEXT("type"), PendingType);

    // Which fixtures apply to the client model: a draft with moves or a
    // pending MOVE, both with client-side expectations, and (MS-T-12) a
    // pending PLACE, whose server outcome is compared with the client PLACE
    // legality. Only a draft without moves carries nothing but the server
    // outcome of its layer (MS-AT-02, backend) and is skipped. Anything else
    // without client expectations is an error, never a silent skip.
    const bool bHasClientExpect = Expect->HasField(TEXT("reach")) || Expect->HasField(TEXT("paths")) ||
                                  Expect->HasField(TEXT("status")) || Expect->HasField(TEXT("requiredBoost"));
    const TArray<TSharedPtr<FJsonValue>>* DraftMoves = nullptr;
    const bool bNoMoves = bDraft && (!(*DraftPtr)->TryGetArrayField(TEXT("moves"), DraftMoves) || !DraftMoves ||
                                     DraftMoves->Num() == 0);
    FString SkipReason, Unsupported;
    if (bDraft == bPending) {
      Unsupported = TEXT("needs exactly one of draft / pending");
    } else if (bPending && PendingType == TEXT("PLACE")) {
      // MS-T-12: a PLACE has no reach / path; its server outcome is compared with the client legality below
      if (bHasClientExpect) Unsupported = TEXT("pending PLACE with reach/paths expectations (PLACE has no path)");
    } else if (bPending && PendingType != TEXT("MOVE")) {
      Unsupported = FString::Printf(TEXT("pending type '%s' is not modelled"), *PendingType);
    } else if (!bHasClientExpect) {
      if (bNoMoves) {
        SkipReason = TEXT("draft without moves: server outcome only");
      } else {
        Unsupported = TEXT("a draft with moves / a pending MOVE without client expectations");
      }
    }
    if (!Unsupported.IsEmpty()) {
      AddError(FString::Printf(TEXT("%s: %s"), *Name, *Unsupported));
      ++Errored;
      continue;
    }
    if (!SkipReason.IsEmpty()) {
      SkipReasons.FindOrAdd(SkipReason)++;
      Skipped.Add(Name);
      continue;
    }

    FString Error, Key;
    FS08BoardModel Board;
    const TSharedPtr<FJsonObject>* BoardSpec = nullptr;
    if (!Fx->TryGetObjectField(TEXT("board"), BoardSpec) || !BoardSpec ||
        !MpFixtureBoard(*BoardSpec, BoardCache, Board, Key, Error)) {
      AddError(FString::Printf(TEXT("%s: board: %s"), *Name, *Error));
      ++Errored;
      continue;
    }
    const TArray<TSharedPtr<FJsonValue>>* FighterSpecs = nullptr;
    TArray<FS08BoardFighter> Fighters;
    if (!Fx->TryGetArrayField(TEXT("fighters"), FighterSpecs) || !FighterSpecs ||
        !MpFixtureFighters(*FighterSpecs, Fighters, Error)) {
      AddError(FString::Printf(TEXT("%s: fighters: %s"), *Name, *Error));
      ++Errored;
      continue;
    }
    if (bPending && PendingType == TEXT("PLACE")) {
      // MS-T-12 (MS-E-62, MS-S-12): the client PLACE spaces (FS09CommandUi::ComputePendingCells) agree with the
      // server outcome of the target: legal <=> "ok"; a refused target names the why.* of the server code.
      FString Server, Why;
      bool bLegal = false;
      Expect->TryGetStringField(TEXT("server"), Server);
      if (!MpEvaluatePendingPlace(Board, Fighters, *PendingPtr, bLegal, Why, Error)) {
        AddError(FString::Printf(TEXT("%s: %s"), *Name, *Error));
        ++Errored;
        continue;
      }
      const bool bServerOk = Server == TEXT("ok");
      FString WantWhy;
      if (!bServerOk) {
        FS08GraphQLError Rejected;
        Rejected.RuleCode = Server;
        Rejected.Message = Server;
        WantWhy = FS08RuleCodes::Classify({Rejected}, ES08RejectOp::PendingEffect, {}).WhyKey.ToString();
      }
      if (bLegal != bServerOk || (!bServerOk && Why != WantWhy)) {
        AddError(FString::Printf(TEXT("%s (%s): client PLACE legal=%d why=%s, server %s (why %s)"), *Name, *Source,
                                 bLegal ? 1 : 0, *Why, *Server, *WantWhy));
        ++Mismatched;
      }
      ++Checked;
      ++CheckedPlace;
      (Source == TEXT("manual") ? CheckedManual : CheckedGenerated)++;
      BoardCounts.FindOrAdd(Key)++;
      continue;
    }
    TArray<FMpGot> Got;
    bool bEvaluated = false;
    if (bDraft) {
      TArray<FMpCard> Hand;
      const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
      if (Fx->TryGetArrayField(TEXT("hand"), Cards) && Cards) {
        for (const TSharedPtr<FJsonValue>& CardValue : *Cards) {
          const TSharedPtr<FJsonObject>* CardPtr = nullptr;
          FMpCard Card;
          if (!CardValue.IsValid() || !CardValue->TryGetObject(CardPtr) || !CardPtr ||
              !(*CardPtr)->TryGetStringField(TEXT("id"), Card.Id)) {
            continue;
          }
          const TSharedPtr<FJsonValue> Boost = (*CardPtr)->TryGetField(TEXT("boostValue"));
          if (Boost.IsValid() && Boost->Type == EJson::Number) {
            Card.bHasBoost = MpIsInt(Boost, Card.Boost);
            if (!Card.bHasBoost) Error = TEXT("a non-integer BOOST (not modelled)");
          }
          Hand.Add(Card);
        }
      }
      FString Actor = TEXT("p1");
      Fx->TryGetStringField(TEXT("actor"), Actor);
      bEvaluated = Error.IsEmpty() && MpEvaluateDraft(Board, Fighters, *DraftPtr, Hand, Actor, Got, Error);
    } else {
      bEvaluated = MpEvaluatePendingMove(Board, Fighters, *PendingPtr, Got, Error);
    }
    if (!bEvaluated) {
      AddError(FString::Printf(TEXT("%s: %s"), *Name, *Error));
      ++Errored;
      continue;
    }
    TArray<FString> Mismatches;
    MpCompare(Expect, Got, Count, Mismatches);
    for (const FString& M : Mismatches) AddError(FString::Printf(TEXT("%s (%s): %s"), *Name, *Source, *M));
    if (Mismatches.Num() > 0) ++Mismatched;
    ++Checked;
    (Source == TEXT("manual") ? CheckedManual : CheckedGenerated)++;
    (bDraft ? CheckedDraft : CheckedPending)++;
    BoardCounts.FindOrAdd(Key)++;
  }

  TArray<FString> BoardParts;
  for (const TPair<FString, int32>& B : BoardCounts) BoardParts.Add(FString::Printf(TEXT("%s=%d"), *B.Key, B.Value));
  BoardParts.Sort();
  TArray<FString> SkipParts;
  for (const TPair<FString, int32>& S : SkipReasons) SkipParts.Add(FString::Printf(TEXT("%d x %s"), S.Value, *S.Key));
  const FString Summary = FString::Printf(
      TEXT("MS-PARITY fixtures=%d checked=%d (manual %d, generated %d; draft %d, pendingMove %d, pendingPlace %d) "
           "skipped=%d mismatched=%d errored=%d boards=[%s] compared: reach=%d paths=%d status=%d requiredBoost=%d"),
      Files.Num(), Checked, CheckedManual, CheckedGenerated, CheckedDraft, CheckedPending, CheckedPlace, Skipped.Num(),
      Mismatched,
      Errored,
      *FString::Join(BoardParts, TEXT(" ")), Count.Reach, Count.Paths, Count.Status, Count.Required);
  AddInfo(Summary);
  UE_LOG(LogTemp, Display, TEXT("%s"), *Summary);
  const FString SkipText = FString::Printf(TEXT("MS-PARITY skipped: %s | %s"), *FString::Join(SkipParts, TEXT("; ")),
                                           *FString::Join(Skipped, TEXT(", ")));
  AddInfo(SkipText);
  UE_LOG(LogTemp, Display, TEXT("%s"), *SkipText);

  // 04 §4.8: >= 40 fixtures, >= 15 manual, on Cobble, Marmoreal and Sarpedon.
  TestTrue(FString::Printf(TEXT("at least 40 fixtures (%d)"), Files.Num()), Files.Num() >= 40);
  TestTrue(FString::Printf(TEXT("at least 15 manual fixtures (%d)"), Manual), Manual >= 15);
  // Lower bounds (98 checked and >= 100 comparisons of each kind on 2026-10-03)
  // so that a comparison that silently stops running cannot pass.
  TestTrue(FString::Printf(TEXT("at least 90 checked by the client model (%d)"), Checked), Checked >= 90);
  TestTrue(FString::Printf(TEXT("at least 90 reach / paths / status / requiredBoost comparisons (%d/%d/%d/%d)"),
                           Count.Reach, Count.Paths, Count.Status, Count.Required),
           Count.Reach >= 90 && Count.Paths >= 90 && Count.Status >= 90 && Count.Required >= 90);
  TestEqual(TEXT("every fixture is checked, skipped for a stated reason or reported"), Checked + Skipped.Num() + Errored,
            Files.Num());
  for (const TCHAR* Board : {TEXT("cobble-5x6"), TEXT("marmoreal"), TEXT("sarpedon")}) {
    TestTrue(FString::Printf(TEXT("board %s covered"), Board), BoardCounts.Contains(Board));
  }
  TestEqual(TEXT("fixtures with a mismatch"), Mismatched, 0);
  TestEqual(TEXT("fixtures that could not be evaluated"), Errored, 0);
  TestTrue(FString::Printf(TEXT("MS-T-12: the pending PLACE fixtures are checked (%d)"), CheckedPlace), CheckedPlace >= 2);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MoveParityFighterMovementTest, "Unmatched.S08.MoveParity.FighterMovement",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MoveParityFighterMovementTest::RunTest(const FString&) {
  // backend getFighterMovement: Number(movement), integer >= 1, else 2 - on
  // the value the projection carries, decoded by DecodeFighters.
  struct FCase {
    const TCHAR* Json; // the "movement" member, nullptr = absent
    int32 Want;
  };
  const FCase Cases[] = {
      {nullptr, 2},          {TEXT("null"), 2},      {TEXT("0"), 2},          {TEXT("1"), 1},
      {TEXT("3"), 3},        {TEXT("2.5"), 2},       {TEXT("3.5"), 2},        {TEXT("3.0"), 3},
      {TEXT("-3"), 2},       {TEXT("\"3\""), 3},     {TEXT("\"3.5\""), 2},    {TEXT("\" 4 \""), 4},
      {TEXT("\"\""), 2},     {TEXT("\"abc\""), 2},   {TEXT("\"3abc\""), 2},   {TEXT("\"0x3\""), 3},
      {TEXT("\"0b11\""), 3}, {TEXT("\"0o7\""), 7},   {TEXT("\"-0x3\""), 2},   {TEXT("\"3e0\""), 3},
      {TEXT("\"+5\""), 5},   {TEXT("\"5.\""), 5},    {TEXT("\".5\""), 2},     {TEXT("\"1_0\""), 2},
      {TEXT("\"Infinity\""), 2}, {TEXT("\"infinity\""), 2}, {TEXT("true"), 1}, {TEXT("false"), 2},
      {TEXT("[]"), 2},       {TEXT("[5]"), 5},       {TEXT("[\"4\"]"), 4},    {TEXT("[[4]]"), 4},
      {TEXT("[1,2]"), 2},    {TEXT("[true]"), 2},    {TEXT("{}"), 2},         {TEXT("1e300"), MAX_int32},
  };
  for (const FCase& Case : Cases) {
    const FString Member = Case.Json ? FString::Printf(TEXT(",\"movement\":%s"), Case.Json) : FString();
    const FString Text = FString::Printf(
        TEXT("[{\"id\":\"f\",\"ownerId\":\"p1\",\"name\":\"F\",\"type\":\"HERO\",\"health\":5,\"maxHealth\":5,"
             "\"attackType\":\"melee\",\"position\":{\"x\":0,\"y\":0}%s}]"),
        *Member);
    TSharedPtr<FJsonValue> Value;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
    TArray<FS08BoardFighter> Fighters;
    if (!TestTrue(FString::Printf(TEXT("parse %s"), *Text), FJsonSerializer::Deserialize(Reader, Value) &&
                                                             FS08BoardModel::DecodeFighters(Value, Fighters))) {
      continue;
    }
    TestEqual(FString::Printf(TEXT("movement %s -> %d"), Case.Json ? Case.Json : TEXT("<absent>"), Case.Want),
              FS08BoardModel::FighterMovement(Fighters[0]), Case.Want);
    TestTrue(FString::Printf(TEXT("movement %s: present flag"), Case.Json ? Case.Json : TEXT("<absent>")),
             Fighters[0].bMovementPresent == (Case.Json != nullptr));
  }
  // The legacy int decode is unchanged (MS-T-04 moves its callers).
  {
    FS08BoardFighter F;
    F.SetRawMovement(3.5);
    TestEqual(TEXT("legacy Movement truncates 3.5 -> 3"), F.Movement, 3);
    TestEqual(TEXT("... FighterMovement 3.5 -> 2"), FS08BoardModel::FighterMovement(F), 2);
    FS08BoardFighter Blank;
    TestEqual(TEXT("hand-built fighter without a raw value -> default 2"), FS08BoardModel::FighterMovement(Blank),
              FS08BoardModel::DefaultFighterMovement);
  }
  // JS Number() corner values.
  TestTrue(TEXT("Number(undefined) = NaN"), FMath::IsNaN(FS08BoardModel::JsNumber(nullptr)));
  TestEqual(TEXT("Number(null) = 0"), FS08BoardModel::JsNumber(MakeShared<FJsonValueNull>()), 0.0);
  TestEqual(TEXT("Number(\"\\t 12 \\n\") = 12"),
            FS08BoardModel::JsNumber(MakeShared<FJsonValueString>(TEXT("\t 12 \n"))), 12.0);
  TestEqual(TEXT("Number(\"-1.5e1\") = -15"), FS08BoardModel::JsNumber(MakeShared<FJsonValueString>(TEXT("-1.5e1"))),
            -15.0);
  TestTrue(TEXT("Number(\"-Infinity\") = -Infinity"),
           FS08BoardModel::JsNumber(MakeShared<FJsonValueString>(TEXT("-Infinity"))) ==
               -std::numeric_limits<double>::infinity());
  TestTrue(TEXT("Number(\"1e\") = NaN"), FMath::IsNaN(FS08BoardModel::JsNumber(MakeShared<FJsonValueString>(TEXT("1e")))));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MoveParityAlivePredicatesTest, "Unmatched.S08.MoveParity.AlivePredicates",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MoveParityAlivePredicatesTest::RunTest(const FString&) {
  // Role table: blocker/occupant = isLivingFighter; maneuver mover = health > 0.
  TestTrue(TEXT("healthy: blocks"), MpFighter(TEXT("a"), TEXT("p1"), 0, 0, 5).IsAliveBlocker());
  TestTrue(TEXT("healthy: moves"), MpFighter(TEXT("a"), TEXT("p1"), 0, 0, 5).CanBeMover());
  TestFalse(TEXT("isDefeated + health 5: does not block (MS-E-24)"),
            MpFighter(TEXT("a"), TEXT("p1"), 0, 0, 5, true).IsAliveBlocker());
  TestTrue(TEXT("isDefeated + health 5: still a maneuver mover (MS-E-77)"),
           MpFighter(TEXT("a"), TEXT("p1"), 0, 0, 5, true).CanBeMover());
  TestFalse(TEXT("health 0: does not block (MS-E-23)"), MpFighter(TEXT("a"), TEXT("p1"), 0, 0, 0).IsAliveBlocker());
  TestFalse(TEXT("health 0: cannot move"), MpFighter(TEXT("a"), TEXT("p1"), 0, 0, 0).CanBeMover());

  // isDefeated decode = JS truthiness.
  struct FDefeatedCase {
    const TCHAR* Json;
    bool bWant;
  };
  for (const FDefeatedCase& Case : {FDefeatedCase{nullptr, false}, FDefeatedCase{TEXT("true"), true},
                                    FDefeatedCase{TEXT("false"), false}, FDefeatedCase{TEXT("null"), false},
                                    FDefeatedCase{TEXT("1"), true}, FDefeatedCase{TEXT("0"), false},
                                    FDefeatedCase{TEXT("\"\""), false}, FDefeatedCase{TEXT("\"no\""), true}}) {
    const FString Member = Case.Json ? FString::Printf(TEXT(",\"isDefeated\":%s"), Case.Json) : FString();
    const FString Text = FString::Printf(
        TEXT("[{\"id\":\"f\",\"ownerId\":\"p1\",\"name\":\"F\",\"type\":\"HERO\",\"health\":5,\"maxHealth\":5,"
             "\"movement\":2,\"attackType\":\"melee\",\"position\":{\"x\":0,\"y\":0}%s}]"),
        *Member);
    TSharedPtr<FJsonValue> Value;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
    TArray<FS08BoardFighter> Fighters;
    if (FJsonSerializer::Deserialize(Reader, Value) && FS08BoardModel::DecodeFighters(Value, Fighters)) {
      TestTrue(FString::Printf(TEXT("isDefeated %s -> %d"), Case.Json ? Case.Json : TEXT("<absent>"), Case.bWant ? 1 : 0),
               Fighters[0].bDefeated == Case.bWant);
    } else {
      AddError(FString::Printf(TEXT("parse %s"), *Text));
    }
  }

  // 6x1 corridor: mover p1 at 0; dirty-defeated enemy at 1; truly defeated
  // enemy at 2; living enemy at 4.
  FS08BoardModel Board;
  if (!TestTrue(TEXT("6x1 grid"), MpGrid(6, 1, {}, Board))) return false;
  TArray<FS08BoardFighter> Fighters = {MpFighter(TEXT("m"), TEXT("p1"), 0, 0),
                                       MpFighter(TEXT("dirty"), TEXT("p2"), 1, 0, 3, true),
                                       MpFighter(TEXT("dead"), TEXT("p2"), 2, 0, 0),
                                       MpFighter(TEXT("foe"), TEXT("p2"), 4, 0)};
  const FS08ReachMap Reach = FS08BoardModel::ComputeReachMap(Board, Fighters, TEXT("m"), 9);
  TestEqual(TEXT("through the dirty-defeated and the defeated enemy, stopped by the living one"),
            MpCellsText(Reach.Order), FString(TEXT("(0,0) (1,0) (2,0) (3,0)")));
  TArray<FIntPoint> Path;
  TestTrue(TEXT("the dirty-defeated enemy's cell is a legal end (MS-E-24)"),
           FS08BoardModel::BuildCanonicalPath(Board, Fighters, Reach, FIntPoint(1, 0), Path) &&
               Path == MpPath({FIntPoint(1, 0)}));
  TestTrue(TEXT("the defeated enemy's cell is a legal end (MS-E-23)"),
           FS08BoardModel::BuildCanonicalPath(Board, Fighters, Reach, FIntPoint(2, 0), Path) &&
               Path == MpPath({FIntPoint(1, 0), FIntPoint(2, 0)}));
  TestFalse(TEXT("the living enemy blocks"),
            FS08BoardModel::BuildCanonicalPath(Board, Fighters, Reach, FIntPoint(5, 0), Path));
  TestNull(TEXT("FighterAt ignores the dirty-defeated fighter"), FS08BoardModel::FighterAt(Fighters, 1, 0, TEXT("m")));
  TestNotNull(TEXT("FighterAt sees the living enemy"), FS08BoardModel::FighterAt(Fighters, 4, 0, TEXT("m")));
  const TSet<uint64> Legacy = FS08BoardModel::ComputeReachableCells(Board, Fighters, TEXT("m"), 9);
  TestTrue(TEXT("legacy wrapper: the dirty-defeated cell is reachable and free"),
           Legacy.Contains(FS08BoardModel::CellKey(1, 0)) && Legacy.Contains(FS08BoardModel::CellKey(3, 0)) &&
               !Legacy.Contains(FS08BoardModel::CellKey(4, 0)));

  // The dirty-defeated fighter as the MOVER: a maneuver moves it (server).
  const FS08ReachMap DirtyReach = FS08BoardModel::ComputeReachMap(Board, Fighters, TEXT("dirty"), 2);
  TestTrue(TEXT("a dirty-defeated mover gets a reach (no mover gate in ComputeReachMap)"),
           DirtyReach.bValid && DirtyReach.Reaches(FIntPoint(3, 0)));
  // The real mover m (p1) is the dirty fighter's enemy: (0,0) is blocked for it.
  TestFalse(TEXT("... and its enemy m still blocks it"), DirtyReach.Reaches(FIntPoint(0, 0)));
  TestTrue(TEXT("... the legacy wrapper (IsAlive) moves it too"),
           FS08BoardModel::ComputeReachableCells(Board, Fighters, TEXT("dirty"), 2).Contains(
               FS08BoardModel::CellKey(3, 0)));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MoveParityReachAndKeyTest, "Unmatched.S08.MoveParity.ReachAndKey",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MoveParityReachAndKeyTest::RunTest(const FString&) {
  // 1. FIFO dist with a wall (canonical-path.spec "BFS within maxSteps").
  {
    FS08BoardModel Board;
    if (!TestTrue(TEXT("4x3 grid"), MpGrid(4, 3, {FIntPoint(1, 0)}, Board))) return false;
    const TArray<FS08BoardFighter> Fighters = {MpFighter(TEXT("a"), TEXT("p1"), 0, 0)};
    const FS08ReachMap Reach = FS08BoardModel::ComputeReachMap(Board, Fighters, TEXT("a"), 2);
    TestTrue(TEXT("valid, start (0,0), owner p1"),
             Reach.bValid && Reach.Start == FIntPoint(0, 0) && Reach.OwnerId == TEXT("p1"));
    TestEqual(TEXT("4 cells within 2"), Reach.Dist.Num(), 4);
    TestTrue(TEXT("dist (0,0)=0 (0,1)=1 (1,1)=2 (0,2)=2"),
             Reach.DistanceTo(FIntPoint(0, 0)) == 0 && Reach.DistanceTo(FIntPoint(0, 1)) == 1 &&
                 Reach.DistanceTo(FIntPoint(1, 1)) == 2 && Reach.DistanceTo(FIntPoint(0, 2)) == 2);
    TestFalse(TEXT("the wall is never entered"), Reach.Reaches(FIntPoint(1, 0)));
    bool bFifo = true, bParents = true;
    for (int32 I = 1; I < Reach.Order.Num(); ++I) {
      const FIntPoint Cell = Reach.Order[I];
      bFifo &= Reach.DistanceTo(Reach.Order[I - 1]) <= Reach.DistanceTo(Cell);
      const uint64* Parent = Reach.Parent.Find(FS08BoardModel::CellKey(Cell.X, Cell.Y));
      const FIntPoint P = Parent ? FIntPoint(static_cast<int32>(static_cast<uint32>(*Parent >> 32)),
                                             static_cast<int32>(static_cast<uint32>(*Parent & 0xffffffffull)))
                                 : FIntPoint(-1, -1);
      bParents &= Parent && Reach.DistanceTo(P) == Reach.DistanceTo(Cell) - 1 && Board.IsAdjacent(P, Cell);
    }
    TestTrue(TEXT("Order is FIFO (non-decreasing distance)"), bFifo);
    TestTrue(TEXT("every parent is an adjacent cell one step closer"), bParents);
    TestFalse(TEXT("the start has no parent"), Reach.Parent.Contains(FS08BoardModel::CellKey(0, 0)));
    // Step limit `>=` and its corners.
    TestEqual(TEXT("MaxSteps 0: only the start"),
              FS08BoardModel::ComputeReachMap(Board, Fighters, TEXT("a"), 0).Dist.Num(), 1);
    TestEqual(TEXT("MaxSteps -1: only the start"),
              FS08BoardModel::ComputeReachMap(Board, Fighters, TEXT("a"), -1).Dist.Num(), 1);
    TestEqual(TEXT("MaxSteps MAX_int32: unlimited (11 passable cells)"),
              FS08BoardModel::ComputeReachMap(Board, Fighters, TEXT("a"), MAX_int32).Dist.Num(), 11);
    TestFalse(TEXT("unknown mover -> invalid"),
              FS08BoardModel::ComputeReachMap(Board, Fighters, TEXT("x"), 2).bValid);
    TArray<FS08BoardFighter> Off = {MpFighter(TEXT("a"), TEXT("p1"), -1, -1)};
    TestFalse(TEXT("mover without a position -> invalid"),
              FS08BoardModel::ComputeReachMap(Board, Off, TEXT("a"), 2).bValid);
    FS08BoardModel NoBoard;
    TestEqual(TEXT("no board: only the start"),
              FS08BoardModel::ComputeReachMap(NoBoard, Fighters, TEXT("a"), 5).Dist.Num(), 1);
    // ReachEndpoints: 1..MaxSteps, start excluded, sorted by K = (y, x).
    TestEqual(TEXT("endpoints within 2 sorted by (y, x)"),
              MpCellsText(FS08BoardModel::ReachEndpoints(Board, Fighters, Reach, 2)),
              FString(TEXT("(0,1) (1,1) (0,2)")));
    TestEqual(TEXT("endpoints within 1"), MpCellsText(FS08BoardModel::ReachEndpoints(Board, Fighters, Reach, 1)),
              FString(TEXT("(0,1)")));
  }
  // 2. Grid tie: (0,0) -> (2,2) goes along the lower row first.
  {
    FS08BoardModel Board;
    if (!TestTrue(TEXT("3x3 grid"), MpGrid(3, 3, {}, Board))) return false;
    const TArray<FS08BoardFighter> Fighters = {MpFighter(TEXT("a"), TEXT("p1"), 0, 0)};
    const FS08ReachMap Reach = FS08BoardModel::ComputeReachMap(Board, Fighters, TEXT("a"), 4);
    TArray<FIntPoint> Path;
    TestTrue(TEXT("grid K = (y, x): (1,0) (2,0) (2,1) (2,2)"),
             FS08BoardModel::BuildCanonicalPath(Board, Fighters, Reach, FIntPoint(2, 2), Path) &&
                 Path == MpPath({FIntPoint(1, 0), FIntPoint(2, 0), FIntPoint(2, 1), FIntPoint(2, 2)}));
    TestTrue(TEXT("stay: true with an empty path"),
             FS08BoardModel::BuildCanonicalPath(Board, Fighters, Reach, FIntPoint(0, 0), Path) && Path.Num() == 0);
    TestFalse(TEXT("out of the board: no path"),
              FS08BoardModel::BuildCanonicalPath(Board, Fighters, Reach, FIntPoint(3, 0), Path));
    TestEqual(TEXT("... and the out path is empty"), Path.Num(), 0);
    TArray<FIntPoint> Legacy;
    TestTrue(TEXT("the legacy wrapper keeps its own route (first-neighbour walk): (0,1) (0,2) (1,2) (2,2)"),
             FS08BoardModel::BuildManeuverPath(Board, Fighters, TEXT("a"), 4, 2, 2, Legacy) &&
                 Legacy == MpPath({FIntPoint(0, 1), FIntPoint(0, 2), FIntPoint(1, 2), FIntPoint(2, 2)}));
  }
  // 3. The graph of canonical-path.spec (letters are spaceIds, (2,0) a hole):
  //    y=0  D - E ===== C ;  y=1  A - B - F - G ; plus D-A, E-B, G-C.
  for (const bool bReversed : {false, true}) {
    FS08BoardModel Board;
    const bool bOk = MpGraph(4, 2,
                             {{TEXT("D"), FIntPoint(0, 0)}, {TEXT("E"), FIntPoint(1, 0)}, {TEXT("C"), FIntPoint(3, 0)},
                              {TEXT("A"), FIntPoint(0, 1)}, {TEXT("B"), FIntPoint(1, 1)}, {TEXT("F"), FIntPoint(2, 1)},
                              {TEXT("G"), FIntPoint(3, 1)}},
                             {{TEXT("D"), TEXT("E")}, {TEXT("E"), TEXT("C")}, {TEXT("D"), TEXT("A")},
                              {TEXT("A"), TEXT("B")}, {TEXT("B"), TEXT("F")}, {TEXT("F"), TEXT("G")},
                              {TEXT("G"), TEXT("C")}, {TEXT("E"), TEXT("B")}},
                             bReversed, Board);
    if (!TestTrue(TEXT("graph board"), bOk)) return false;
    const FString Tag = bReversed ? TEXT("reversed links") : TEXT("declared links");
    const TArray<FS08BoardFighter> Fighters = {MpFighter(TEXT("a"), TEXT("p1"), 0, 0)};
    const FS08ReachMap Two = FS08BoardModel::ComputeReachMap(Board, Fighters, TEXT("a"), 2);
    TestTrue(FString::Printf(TEXT("%s: D=0 E=1 A=1 C=2 (long link) B=2"), *Tag),
             Two.Dist.Num() == 5 && Two.DistanceTo(FIntPoint(1, 0)) == 1 && Two.DistanceTo(FIntPoint(0, 1)) == 1 &&
                 Two.DistanceTo(FIntPoint(3, 0)) == 2 && Two.DistanceTo(FIntPoint(1, 1)) == 2);
    const FS08ReachMap Three = FS08BoardModel::ComputeReachMap(Board, Fighters, TEXT("a"), 3);
    TArray<FIntPoint> Path;
    TestTrue(FString::Printf(TEXT("%s: D->F via A (spaceId A < E although E has the smaller y)"), *Tag),
             FS08BoardModel::BuildCanonicalPath(Board, Fighters, Three, FIntPoint(2, 1), Path) &&
                 Path == MpPath({FIntPoint(0, 1), FIntPoint(1, 1), FIntPoint(2, 1)}));
    TestTrue(FString::Printf(TEXT("%s: D->G is D-E-C-G"), *Tag),
             FS08BoardModel::BuildCanonicalPath(Board, Fighters, Three, FIntPoint(3, 1), Path) &&
                 Path == MpPath({FIntPoint(1, 0), FIntPoint(3, 0), FIntPoint(3, 1)}));
    TestEqual(FString::Printf(TEXT("%s: endpoints sorted by spaceId"), *Tag),
              MpCellsText(FS08BoardModel::ReachEndpoints(Board, Fighters, Three, 3)),
              FString(TEXT("(0,1) (1,1) (3,0) (1,0) (2,1) (3,1)"))); // A B C E F G
  }
  // 4. Ordinal, case-sensitive spaceId: "B" (0x42) < "a" (0x61). A
  //    case-insensitive compare or (y, x) alone would take "a" at y = 0.
  {
    FS08BoardModel Board;
    const bool bOk = MpGraph(2, 2,
                             {{TEXT("s"), FIntPoint(0, 0)}, {TEXT("a"), FIntPoint(1, 0)}, {TEXT("B"), FIntPoint(0, 1)},
                              {TEXT("z"), FIntPoint(1, 1)}},
                             {{TEXT("s"), TEXT("a")}, {TEXT("s"), TEXT("B")}, {TEXT("a"), TEXT("z")},
                              {TEXT("B"), TEXT("z")}},
                             false, Board);
    if (!TestTrue(TEXT("diamond board"), bOk)) return false;
    const TArray<FS08BoardFighter> Fighters = {MpFighter(TEXT("m"), TEXT("p1"), 0, 0)};
    const FS08ReachMap Reach = FS08BoardModel::ComputeReachMap(Board, Fighters, TEXT("m"), 2);
    TArray<FIntPoint> Path;
    TestTrue(TEXT("s -> z goes through B (ordinal, case sensitive)"),
             FS08BoardModel::BuildCanonicalPath(Board, Fighters, Reach, FIntPoint(1, 1), Path) &&
                 Path == MpPath({FIntPoint(0, 1), FIntPoint(1, 1)}));
    TestTrue(TEXT("CompareCanonical: B < a"),
             FS08BoardModel::CompareCanonical(Board, FIntPoint(0, 1), FIntPoint(1, 0)) < 0);
  }
  // 5. Enemies, allies, pass-through, enemies relative to the MOVED fighter.
  {
    FS08BoardModel Board;
    if (!TestTrue(TEXT("4x1 grid"), MpGrid(4, 1, {}, Board))) return false;
    TArray<FS08BoardFighter> Fighters = {MpFighter(TEXT("a"), TEXT("p1"), 0, 0), MpFighter(TEXT("ally"), TEXT("p1"), 1, 0),
                                         MpFighter(TEXT("e"), TEXT("p2"), 2, 0)};
    const FS08ReachMap Reach = FS08BoardModel::ComputeReachMap(Board, Fighters, TEXT("a"), 9);
    TArray<FIntPoint> Path;
    TestTrue(TEXT("the ally is passable"), Reach.Reaches(FIntPoint(1, 0)));
    TestFalse(TEXT("... but not an end"), FS08BoardModel::BuildCanonicalPath(Board, Fighters, Reach, FIntPoint(1, 0), Path));
    TestFalse(TEXT("the enemy blocks"), Reach.Reaches(FIntPoint(2, 0)) || Reach.Reaches(FIntPoint(3, 0)));
    FS08ReachOptions Pass;
    Pass.bPassThroughEnemies = true;
    const FS08ReachMap Through = FS08BoardModel::ComputeReachMap(Board, Fighters, TEXT("a"), 9, Pass);
    TestTrue(TEXT("pass-through: (1,0) (2,0) (3,0)"),
             FS08BoardModel::BuildCanonicalPath(Board, Fighters, Through, FIntPoint(3, 0), Path) &&
                 Path == MpPath({FIntPoint(1, 0), FIntPoint(2, 0), FIntPoint(3, 0)}));
    TestFalse(TEXT("pass-through never ends on the enemy"),
              FS08BoardModel::BuildCanonicalPath(Board, Fighters, Through, FIntPoint(2, 0), Path));
    const FS08ReachMap Theirs = FS08BoardModel::ComputeReachMap(Board, Fighters, TEXT("e"), 5);
    TestTrue(TEXT("moving the opponent's fighter: p1 fighters are ITS enemies"),
             Theirs.Dist.Num() == 2 && Theirs.Reaches(FIntPoint(3, 0)));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MoveParityLegacyWrappersTest, "Unmatched.S08.MoveParity.LegacyWrappers",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MoveParityLegacyWrappersTest::RunTest(const FString&) {
  // ComputeReachableCells / BuildManeuverPath are wrappers now: on both
  // original maps, every start space x allowance 0..5, with an ally and an
  // enemy on the board, they equal the pre-MS-T-03 algorithms bit for bit;
  // the canonical path has the same length and is a legal chain of links.
  int32 Sets = 0, Routes = 0;
  for (const TCHAR* Key : {TEXT("marmoreal"), TEXT("sarpedon")}) {
    TArray<TSharedPtr<FJsonObject>> Rows;
    FString Error;
    FS08BoardModel Board;
    const bool bLoaded = MpTopologyRows(Key, Rows, Error) && MpDecodeRows(Rows, Board, Error);
    if (!TestTrue(FString::Printf(TEXT("%s loads: %s"), Key, *Error), bLoaded)) continue;
    TArray<FIntPoint> Spaces;
    for (int32 Y = 0; Y < Board.Height; ++Y) {
      for (int32 X = 0; X < Board.Width; ++X) {
        if (Board.IsBoardSpace(X, Y)) Spaces.Add(FIntPoint(X, Y));
      }
    }
    if (!TestTrue(FString::Printf(TEXT("%s: spaces"), Key), Spaces.Num() > 20)) continue;
    // An ally and an enemy on fixed spaces (a third and two thirds of the list).
    const FIntPoint AllyAt = Spaces[Spaces.Num() / 3];
    const FIntPoint FoeAt = Spaces[(2 * Spaces.Num()) / 3];
    TArray<FS08BoardFighter> Fighters = {MpFighter(TEXT("m"), TEXT("p1"), 0, 0),
                                         MpFighter(TEXT("ally"), TEXT("p1"), AllyAt.X, AllyAt.Y),
                                         MpFighter(TEXT("foe"), TEXT("p2"), FoeAt.X, FoeAt.Y)};
    for (const FIntPoint& Start : Spaces) {
      if (Start == AllyAt || Start == FoeAt) continue;
      Fighters[0].X = Start.X;
      Fighters[0].Y = Start.Y;
      for (int32 Allowance = 0; Allowance <= 5; ++Allowance) {
        const TSet<uint64> Old = MpLegacyReachable(Board, Fighters, TEXT("m"), Allowance);
        const TSet<uint64> New = FS08BoardModel::ComputeReachableCells(Board, Fighters, TEXT("m"), Allowance);
        if (Old.Num() != New.Num() || Old.Difference(New).Num() != 0) {
          AddError(FString::Printf(TEXT("%s: reach differs from %s allowance %d"), Key,
                                   *Board.CellLabel(Start.X, Start.Y), Allowance));
        }
        ++Sets;
        if (Allowance != 5) continue;
        const FS08ReachMap Reach = FS08BoardModel::ComputeReachMap(Board, Fighters, TEXT("m"), Allowance);
        for (const FIntPoint& Target : Spaces) {
          TArray<FIntPoint> OldPath, NewPath, Canonical;
          const bool bOld = MpLegacyPath(Board, Fighters, TEXT("m"), Allowance, Target.X, Target.Y, OldPath);
          const bool bNew = FS08BoardModel::BuildManeuverPath(Board, Fighters, TEXT("m"), Allowance, Target.X,
                                                              Target.Y, NewPath);
          if (bOld != bNew || OldPath != NewPath) {
            AddError(FString::Printf(TEXT("%s: legacy route differs %s -> %s"), Key,
                                     *Board.CellLabel(Start.X, Start.Y), *Board.CellLabel(Target.X, Target.Y)));
          }
          const bool bCanonical = FS08BoardModel::BuildCanonicalPath(Board, Fighters, Reach, Target, Canonical);
          const bool bEnd = FS08BoardModel::IsReachEndpoint(Fighters, Reach, Target);
          // Canonical exists exactly for reached endpoints; same length as the legacy route.
          if (bCanonical != (bNew && bEnd) ||
              (bCanonical && (Canonical.Num() != NewPath.Num() || !MpIsStepChain(Board, Start, Canonical)))) {
            AddError(FString::Printf(TEXT("%s: canonical path inconsistent %s -> %s"), Key,
                                     *Board.CellLabel(Start.X, Start.Y), *Board.CellLabel(Target.X, Target.Y)));
          }
          ++Routes;
        }
      }
    }
  }
  const FString Summary = FString::Printf(TEXT("MS-PARITY legacy wrappers: %d reach sets, %d routes compared"), Sets, Routes);
  AddInfo(Summary);
  UE_LOG(LogTemp, Display, TEXT("%s"), *Summary);
  TestTrue(Summary, Sets > 300 && Routes > 1000);
  return true;
}

#endif // WITH_AUTOMATION_TESTS

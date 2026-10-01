// ENV-MAPS track G automation tests: the UE client plays original maps
// (Marmoreal / Sarpedon) on their space graph, not on the lattice.
//   Unmatched.S08.BoardGraph.*   - topology decode, neighbours = links, graph
//                                  BFS/paths/approach, layout frame and circle
//                                  hit test, the committed topology fixtures,
//                                  and the Cobble-style grid kept bit for bit
//                                  (neighbour order, reach sets, paths).
//   Unmatched.S09.RangedTargets.* - ENV-O6 / GAP-023: the attack draft offers
//                                  exactly the server's legal set (melee =
//                                  linked; ranged = linked OR shared zone).
// Contract: backend game-engine/engine/board-topology.ts (neighbours,
// isAdjacent, boardDistance), adjacency.service isInSameZone,
// game-action-executor executeAttack; data: backend/prisma/fixtures/boards/
// <key>.topology.json and tools/art/map_surface/manifest.<key>.json.
// Headless run (after 21:00 build window):
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     -ExecCmds="Automation RunTests Unmatched.S08.BoardGraph+Unmatched.S09.RangedTargets; Quit"
//     -unattended -nosplash -nullrhi
// Optional: -S08TopologyFixtures=<dir> overrides the fixture directory.
#if WITH_AUTOMATION_TESTS

#include "S08BoardModel.h"
#include "S08Contracts.h"
#include "../S09/S09ManeuverUi.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

// Named namespace (not anonymous): unity builds merge test files, and the
// other suites already define MakeBoard & co. in their anonymous namespaces.
namespace S08BoardGraphTest {

// ---- synthetic topology board ---------------------------------------------

struct FBgSpaceSpec {
  int32 X = 0;
  int32 Y = 0;
  FString Id;
  double Px = 0.0;
  double Py = 0.0;
  TArray<FString> Zones;
  int32 Start = 0;
  TArray<FIntPoint> Links;
};

TSharedRef<FJsonObject> BgLinkJson(const FIntPoint& P) {
  TSharedRef<FJsonObject> Link = MakeShared<FJsonObject>();
  Link->SetNumberField(TEXT("x"), P.X);
  Link->SetNumberField(TEXT("y"), P.Y);
  return Link;
}

/** boardState exactly as backend buildBoardState ships a topology board:
 *  cells[y][x], non-space lattice positions are {type:'obstacle',x,y}, space
 *  cells carry zones/zone/spaceId/layout/start/links. */
TSharedPtr<FJsonValue> BgTopologyBoardState(int32 W, int32 H, const TArray<FBgSpaceSpec>& Spaces) {
  TArray<TArray<TSharedPtr<FJsonObject>>> Grid;
  Grid.SetNum(H);
  for (int32 Y = 0; Y < H; ++Y) {
    for (int32 X = 0; X < W; ++X) {
      TSharedRef<FJsonObject> Hole = MakeShared<FJsonObject>();
      Hole->SetStringField(TEXT("type"), TEXT("obstacle"));
      Hole->SetNumberField(TEXT("x"), X);
      Hole->SetNumberField(TEXT("y"), Y);
      Grid[Y].Add(Hole);
    }
  }
  for (const FBgSpaceSpec& Space : Spaces) {
    TSharedRef<FJsonObject> Cell = MakeShared<FJsonObject>();
    Cell->SetStringField(TEXT("type"), TEXT("normal"));
    Cell->SetNumberField(TEXT("x"), Space.X);
    Cell->SetNumberField(TEXT("y"), Space.Y);
    TArray<TSharedPtr<FJsonValue>> Zones;
    for (const FString& Zone : Space.Zones) Zones.Add(MakeShared<FJsonValueString>(Zone));
    Cell->SetArrayField(TEXT("zones"), Zones);
    if (Space.Zones.Num() > 0) Cell->SetStringField(TEXT("zone"), Space.Zones[0]);
    Cell->SetStringField(TEXT("spaceId"), Space.Id);
    TSharedRef<FJsonObject> Layout = MakeShared<FJsonObject>();
    Layout->SetNumberField(TEXT("x"), Space.Px);
    Layout->SetNumberField(TEXT("y"), Space.Py);
    Cell->SetObjectField(TEXT("layout"), Layout);
    if (Space.Start > 0) Cell->SetNumberField(TEXT("start"), Space.Start);
    TArray<TSharedPtr<FJsonValue>> Links;
    for (const FIntPoint& Link : Space.Links) Links.Add(MakeShared<FJsonValueObject>(BgLinkJson(Link)));
    Cell->SetArrayField(TEXT("links"), Links);
    Grid[Space.Y][Space.X] = Cell;
  }
  TArray<TSharedPtr<FJsonValue>> Rows;
  for (int32 Y = 0; Y < H; ++Y) {
    TArray<TSharedPtr<FJsonValue>> Row;
    for (const TSharedPtr<FJsonObject>& Cell : Grid[Y]) Row.Add(MakeShared<FJsonValueObject>(Cell));
    Rows.Add(MakeShared<FJsonValueArray>(Row));
  }
  TSharedRef<FJsonObject> Board = MakeShared<FJsonObject>();
  Board->SetNumberField(TEXT("width"), W);
  Board->SetNumberField(TEXT("height"), H);
  Board->SetArrayField(TEXT("cells"), Rows);
  Board->SetObjectField(TEXT("doors"), MakeShared<FJsonObject>());
  return MakeShared<FJsonValueObject>(Board);
}

/** 5x2 lattice, 8 spaces, two obstacle holes (2,0) and (3,0):
 *
 *     G01(0,0) - G02(1,0) ============== G05(4,0)      (G02-G05 spans 3 lattice steps)
 *        |          :  (no link)            :  (no link)
 *     G06(0,1) - G07(1,1) - G08(2,1) - G09(3,1) - G10(4,1)
 *
 *  G02-G05 is declared by G02 only (G05 sends links: []), G09-G10 by G10
 *  only: both must come out symmetric. G02|G07 and G05|G10 are LATTICE
 *  neighbours without a link - never adjacent. Zones: G08 is triple
 *  (green, red, yellow); G10 (blue, yellow); G02 (red, blue). */
TArray<FBgSpaceSpec> BgSyntheticSpaces() {
  auto S = [](int32 X, int32 Y, const TCHAR* Id, double Px, double Py,
              TArray<FString> Zones, int32 Start, TArray<FIntPoint> Links) {
    FBgSpaceSpec Spec;
    Spec.X = X;
    Spec.Y = Y;
    Spec.Id = Id;
    Spec.Px = Px;
    Spec.Py = Py;
    Spec.Zones = MoveTemp(Zones);
    Spec.Start = Start;
    Spec.Links = MoveTemp(Links);
    return Spec;
  };
  return {
      S(0, 0, TEXT("G01"), 100, 100, {TEXT("red")}, 1, {FIntPoint(1, 0), FIntPoint(0, 1)}),
      S(1, 0, TEXT("G02"), 300, 100, {TEXT("red"), TEXT("blue")}, 0, {FIntPoint(0, 0), FIntPoint(4, 0)}),
      S(4, 0, TEXT("G05"), 1000, 100, {TEXT("blue")}, 0, {}),
      S(0, 1, TEXT("G06"), 100, 500, {TEXT("red")}, 0, {FIntPoint(0, 0), FIntPoint(1, 1)}),
      S(1, 1, TEXT("G07"), 300, 500, {TEXT("green")}, 0, {FIntPoint(0, 1), FIntPoint(2, 1)}),
      S(2, 1, TEXT("G08"), 500, 500, {TEXT("green"), TEXT("red"), TEXT("yellow")}, 0,
        {FIntPoint(1, 1), FIntPoint(3, 1)}),
      S(3, 1, TEXT("G09"), 700, 500, {TEXT("yellow")}, 0, {FIntPoint(2, 1)}),
      S(4, 1, TEXT("G10"), 1000, 500, {TEXT("blue"), TEXT("yellow")}, 2, {FIntPoint(3, 1)}),
  };
}

bool BgSyntheticBoard(FS08BoardModel& OutBoard) {
  return OutBoard.Decode(BgTopologyBoardState(5, 2, BgSyntheticSpaces()));
}

FS08BoardFighter BgFighter(const TCHAR* Id, const TCHAR* Owner, int32 X, int32 Y,
                         const TCHAR* AttackType = TEXT("melee"), int32 Movement = 2) {
  FS08BoardFighter F;
  F.Id = Id;
  F.OwnerId = Owner;
  F.Name = Id;
  F.Label = Id;
  F.Health = F.MaxHealth = 5;
  F.X = X;
  F.Y = Y;
  F.Movement = Movement;
  F.AttackType = AttackType;
  return F;
}

TSet<uint64> BgKeys(std::initializer_list<FIntPoint> Cells) {
  TSet<uint64> Out;
  for (const FIntPoint& C : Cells) Out.Add(FS08BoardModel::CellKey(C.X, C.Y));
  return Out;
}

FString BgKeysToString(const TSet<uint64>& Set) {
  TArray<FString> Parts;
  for (const uint64 Key : Set) {
    Parts.Add(FString::Printf(TEXT("(%d,%d)"), static_cast<int32>(static_cast<uint32>(Key >> 32)),
                              static_cast<int32>(static_cast<uint32>(Key & 0xffffffffull))));
  }
  Parts.Sort();
  return FString::Join(Parts, TEXT(" "));
}

bool BgSameSet(const TSet<uint64>& A, const TSet<uint64>& B) {
  return A.Num() == B.Num() && A.Difference(B).Num() == 0;
}

// ---- grid board + the pre-topology algorithms (regression oracle) ----------

/** Cobble-like 5x6 grid as the server ships it (no links): zones on every
 *  cell, an obstacle, a wall and a closed door. */
TSharedPtr<FJsonValue> BgGridBoardState() {
  TArray<TSharedPtr<FJsonValue>> Rows;
  for (int32 Y = 0; Y < 6; ++Y) {
    TArray<TSharedPtr<FJsonValue>> Row;
    for (int32 X = 0; X < 5; ++X) {
      TSharedRef<FJsonObject> Cell = MakeShared<FJsonObject>();
      const TCHAR* Type = TEXT("normal");
      if (X == 2 && Y == 2) Type = TEXT("obstacle");
      if (X == 4 && Y == 1) Type = TEXT("wall");
      if (X == 1 && Y == 4) Type = TEXT("door");
      Cell->SetStringField(TEXT("type"), Type);
      Cell->SetNumberField(TEXT("x"), X);
      Cell->SetNumberField(TEXT("y"), Y);
      if (X == 1 && Y == 4) Cell->SetBoolField(TEXT("isOpen"), false);
      if (!(X == 2 && Y == 2) && !(X == 4 && Y == 1)) {
        const TCHAR* Zone = Y < 3 ? TEXT("blue") : TEXT("red");
        TArray<TSharedPtr<FJsonValue>> Zones;
        Zones.Add(MakeShared<FJsonValueString>(Zone));
        if (X == 2 && Y == 3) Zones.Add(MakeShared<FJsonValueString>(TEXT("blue")));
        Cell->SetArrayField(TEXT("zones"), Zones);
        Cell->SetStringField(TEXT("zone"), Zone);
      }
      Row.Add(MakeShared<FJsonValueObject>(Cell));
    }
    Rows.Add(MakeShared<FJsonValueArray>(Row));
  }
  TSharedRef<FJsonObject> Board = MakeShared<FJsonObject>();
  Board->SetNumberField(TEXT("width"), 5);
  Board->SetNumberField(TEXT("height"), 6);
  Board->SetArrayField(TEXT("cells"), Rows);
  Board->SetObjectField(TEXT("doors"), MakeShared<FJsonObject>());
  return MakeShared<FJsonValueObject>(Board);
}

/** Verbatim copy of FS08BoardModel::ComputeReachableCells before ENV-MAPS
 *  (orthogonal Dx/Dy, stack frontier) - the grid oracle. */
TSet<uint64> BgLegacyReachable(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                             const FString& FighterId, int32 Allowance) {
  TSet<uint64> Reachable;
  const FS08BoardFighter* Mover = nullptr;
  for (const FS08BoardFighter& F : Fighters) {
    if (F.Id == FighterId) {
      Mover = &F;
      break;
    }
  }
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
    static const int32 Dx[4] = {1, -1, 0, 0};
    static const int32 Dy[4] = {0, 0, 1, -1};
    for (int32 Dir = 0; Dir < 4; ++Dir) {
      const int32 NX = Node.X + Dx[Dir];
      const int32 NY = Node.Y + Dy[Dir];
      if (!FS08BoardModel::IsStepTraversable(Board, Fighters, *Mover, NX, NY)) continue;
      const uint64 Key = FS08BoardModel::CellKey(NX, NY);
      const int32 NewSteps = Node.Steps + 1;
      if (const int32* Existing = Best.Find(Key)) {
        if (*Existing <= NewSteps) continue;
      }
      Best.Add(Key, NewSteps);
      Frontier.Push({NX, NY, NewSteps});
      if (FS08BoardModel::IsEndpointFree(Fighters, *Mover, NX, NY)) Reachable.Add(Key);
    }
  }
  return Reachable;
}

/** Verbatim copy of the pre-ENV-MAPS BuildManeuverPath (grid oracle; the
 *  reverse walk order decides WHICH shortest route is sent). */
bool BgLegacyPath(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                const FString& FighterId, int32 Allowance, int32 TargetX, int32 TargetY,
                TArray<FIntPoint>& OutPath) {
  OutPath.Reset();
  const FS08BoardFighter* Mover = nullptr;
  for (const FS08BoardFighter& F : Fighters) {
    if (F.Id == FighterId) {
      Mover = &F;
      break;
    }
  }
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
    static const int32 Dx[4] = {1, -1, 0, 0};
    static const int32 Dy[4] = {0, 0, 1, -1};
    for (int32 Dir = 0; Dir < 4; ++Dir) {
      const int32 NX = Node.X + Dx[Dir];
      const int32 NY = Node.Y + Dy[Dir];
      if (!FS08BoardModel::IsStepTraversable(Board, Fighters, *Mover, NX, NY)) continue;
      const uint64 Key = FS08BoardModel::CellKey(NX, NY);
      const int32 NewSteps = Node.Steps + 1;
      if (const int32* Existing = Best.Find(Key)) {
        if (*Existing <= NewSteps) continue;
      }
      Best.Add(Key, NewSteps);
      Frontier.Push({NX, NY, NewSteps});
    }
  }
  const int32* TargetSteps = Best.Find(FS08BoardModel::CellKey(TargetX, TargetY));
  if (!TargetSteps) return false;
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
      const int32* PrevSteps = Best.Find(FS08BoardModel::CellKey(PX, PY));
      if (PrevSteps && *PrevSteps == Steps) {
        CX = PX;
        CY = PY;
        Advanced = true;
        break;
      }
    }
    if (!Advanced) return false;
  }
  for (int32 Index = Reversed.Num() - 1; Index >= 0; --Index) OutPath.Add(Reversed[Index]);
  return OutPath.Num() > 0;
}

// ---- committed topology fixtures (unmatched.board-topology/1) --------------

FString BgRepoPath(const TCHAR* Relative) {
  return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectDir(), TEXT("../.."), Relative));
}

FString BgTopologyFixturePath(const FString& Key) {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S08TopologyFixtures="), Dir) || Dir.IsEmpty()) {
    Dir = BgRepoPath(TEXT("backend/prisma/fixtures/boards"));
  }
  return FPaths::Combine(Dir, Key + TEXT(".topology.json"));
}

bool BgLoadJsonObject(const FString& Path, TSharedPtr<FJsonObject>& OutObject) {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *Path)) return false;
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
  return FJsonSerializer::Deserialize(Reader, OutObject) && OutObject.IsValid();
}

/** Fixture Board.cells (flat {x,y,spaceId,zones,layout,start,links} /
 *  {x,y,isObstacle}) -> the boardState buildBoardState ships: cells[y][x],
 *  zone = zones[0], holes = obstacle (topology rule). */
bool BgFixtureBoardState(const TSharedPtr<FJsonObject>& Fixture, TSharedPtr<FJsonValue>& OutState) {
  const TSharedPtr<FJsonObject>* Lattice = nullptr;
  if (!Fixture->TryGetObjectField(TEXT("lattice"), Lattice) || !Lattice || !Lattice->IsValid()) return false;
  int32 W = 0, H = 0;
  if (!(*Lattice)->TryGetNumberField(TEXT("width"), W) || !(*Lattice)->TryGetNumberField(TEXT("height"), H) ||
      W <= 0 || H <= 0) {
    return false;
  }
  TArray<TArray<TSharedPtr<FJsonObject>>> Grid;
  Grid.SetNum(H);
  for (int32 Y = 0; Y < H; ++Y) {
    for (int32 X = 0; X < W; ++X) {
      TSharedRef<FJsonObject> Hole = MakeShared<FJsonObject>();
      Hole->SetStringField(TEXT("type"), TEXT("obstacle"));
      Hole->SetNumberField(TEXT("x"), X);
      Hole->SetNumberField(TEXT("y"), Y);
      Grid[Y].Add(Hole);
    }
  }
  const TArray<TSharedPtr<FJsonValue>>* Cells = nullptr;
  if (!Fixture->TryGetArrayField(TEXT("cells"), Cells) || !Cells) return false;
  for (const TSharedPtr<FJsonValue>& Value : *Cells) {
    const TSharedPtr<FJsonObject>* Source = nullptr;
    if (!Value.IsValid() || !Value->TryGetObject(Source) || !Source || !Source->IsValid()) return false;
    int32 X = -1, Y = -1;
    if (!(*Source)->TryGetNumberField(TEXT("x"), X) || !(*Source)->TryGetNumberField(TEXT("y"), Y) ||
        X < 0 || Y < 0 || X >= W || Y >= H) {
      return false;
    }
    bool bObstacle = false;
    (*Source)->TryGetBoolField(TEXT("isObstacle"), bObstacle);
    TSharedRef<FJsonObject> Cell = MakeShared<FJsonObject>();
    Cell->SetStringField(TEXT("type"), bObstacle ? TEXT("obstacle") : TEXT("normal"));
    Cell->SetNumberField(TEXT("x"), X);
    Cell->SetNumberField(TEXT("y"), Y);
    if (!bObstacle) {
      const TArray<TSharedPtr<FJsonValue>>* Zones = nullptr;
      if ((*Source)->TryGetArrayField(TEXT("zones"), Zones) && Zones && Zones->Num() > 0) {
        Cell->SetArrayField(TEXT("zones"), *Zones);
        FString First;
        if ((*Zones)[0].IsValid() && (*Zones)[0]->TryGetString(First)) {
          Cell->SetStringField(TEXT("zone"), First);
        }
      }
      for (const TCHAR* Field : {TEXT("spaceId"), TEXT("layout"), TEXT("start"), TEXT("links")}) {
        const TSharedPtr<FJsonValue> Copy = (*Source)->TryGetField(Field);
        if (Copy.IsValid() && !Copy->IsNull()) Cell->SetField(Field, Copy);
      }
    }
    Grid[Y][X] = Cell;
  }
  TArray<TSharedPtr<FJsonValue>> Rows;
  for (int32 Y = 0; Y < H; ++Y) {
    TArray<TSharedPtr<FJsonValue>> Row;
    for (const TSharedPtr<FJsonObject>& Cell : Grid[Y]) Row.Add(MakeShared<FJsonValueObject>(Cell));
    Rows.Add(MakeShared<FJsonValueArray>(Row));
  }
  TSharedRef<FJsonObject> Board = MakeShared<FJsonObject>();
  Board->SetNumberField(TEXT("width"), W);
  Board->SetNumberField(TEXT("height"), H);
  Board->SetArrayField(TEXT("cells"), Rows);
  Board->SetObjectField(TEXT("doors"), MakeShared<FJsonObject>());
  OutState = MakeShared<FJsonValueObject>(Board);
  return true;
}

/** Pairs of space ids from an array of 2-string arrays (edges, lattice pairs). */
TArray<TPair<FString, FString>> BgIdPairs(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field) {
  TArray<TPair<FString, FString>> Out;
  const TArray<TSharedPtr<FJsonValue>>* Pairs = nullptr;
  if (!Object.IsValid() || !Object->TryGetArrayField(Field, Pairs) || !Pairs) return Out;
  for (const TSharedPtr<FJsonValue>& Pair : *Pairs) {
    const TArray<TSharedPtr<FJsonValue>>* Ids = nullptr;
    if (!Pair.IsValid() || !Pair->TryGetArray(Ids) || !Ids || Ids->Num() != 2) continue;
    FString A, B;
    if ((*Ids)[0]->TryGetString(A) && (*Ids)[1]->TryGetString(B)) Out.Add(TPair<FString, FString>(A, B));
  }
  return Out;
}

FIntPoint BgSpacePos(const FS08BoardModel& Board, const FString& Id) {
  const FS08Cell* Cell = Board.FindSpace(Id);
  return Cell ? FIntPoint(Cell->X, Cell->Y) : FIntPoint(-1, -1);
}

} // namespace S08BoardGraphTest

using namespace S08BoardGraphTest;

// ---------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardGraphDecodeTest,
    "Unmatched.S08.BoardGraph.Decode topology cells: links, layout, start, spaceId, obstacles, tolerance",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardGraphDecodeTest::RunTest(const FString&) {
  FS08BoardModel Board;
  if (!TestTrue(TEXT("synthetic topology board decodes"), BgSyntheticBoard(Board))) return false;
  TestTrue(TEXT("links on any cell -> topology board"), Board.bHasTopology);
  TestEqual(TEXT("lattice width"), Board.Width, 5);
  TestEqual(TEXT("lattice height"), Board.Height, 2);

  const FS08Cell* G02 = Board.CellAt(1, 0);
  if (!TestNotNull(TEXT("G02 cell"), G02)) return false;
  TestEqual(TEXT("G02 spaceId"), G02->SpaceId, FString(TEXT("G02")));
  TestTrue(TEXT("G02 has layout"), G02->bHasLayout);
  TestTrue(TEXT("G02 layout = (300,100) px"), G02->Layout.Equals(FVector2D(300.0, 100.0), 1e-6));
  TestEqual(TEXT("G02 zones red+blue"), G02->Zones.Num(), 2);
  TestTrue(TEXT("G02 links as sent: (0,0) then (4,0)"),
           G02->Links.Num() == 2 && G02->Links[0] == FIntPoint(0, 0) && G02->Links[1] == FIntPoint(4, 0));
  TestEqual(TEXT("G02 no start"), G02->StartSlot, 0);
  TestEqual(TEXT("G01 start slot 1"), Board.CellAt(0, 0)->StartSlot, 1);
  TestEqual(TEXT("G10 start slot 2"), Board.CellAt(4, 1)->StartSlot, 2);
  TestEqual(TEXT("G08 keeps all three zones"), Board.CellAt(2, 1)->Zones.Num(), 3);
  const FS08Cell* G05 = Board.CellAt(4, 0);
  TestTrue(TEXT("G05 sent an EMPTY links array (still a topology marker)"), G05->bHasLinks && G05->Links.Num() == 0);

  for (const FIntPoint Hole : {FIntPoint(2, 0), FIntPoint(3, 0)}) {
    const FS08Cell* Cell = Board.CellAt(Hole.X, Hole.Y);
    TestTrue(FString::Printf(TEXT("(%d,%d) is an obstacle"), Hole.X, Hole.Y),
             Cell && Cell->Type == ES08CellType::Obstacle && !Cell->IsPassable());
    TestFalse(TEXT("obstacle has no layout"), Cell && Cell->bHasLayout);
    TestFalse(TEXT("obstacle is not a board space"), Board.IsBoardSpace(Hole.X, Hole.Y));
  }
  TestTrue(TEXT("G02 is a board space"), Board.IsBoardSpace(1, 0));
  TestTrue(TEXT("FindSpace(G08) = (2,1)"), BgSpacePos(Board, TEXT("G08")) == FIntPoint(2, 1));
  TestNull(TEXT("FindSpace(unknown)"), Board.FindSpace(TEXT("G99")));
  TestEqual(TEXT("CellLabel of a space = spaceId"), Board.CellLabel(2, 1), FString(TEXT("G08")));
  TestEqual(TEXT("CellLabel of a hole = (x,y)"), Board.CellLabel(2, 0), FString(TEXT("(2,0)")));

  // Tolerance: malformed link entries / half layouts / out-of-range start
  // are skipped; a board without any links array stays a grid.
  {
    TSharedRef<FJsonObject> A = MakeShared<FJsonObject>();
    A->SetStringField(TEXT("type"), TEXT("normal"));
    A->SetNumberField(TEXT("x"), 0);
    A->SetNumberField(TEXT("y"), 0);
    TArray<TSharedPtr<FJsonValue>> Links;
    Links.Add(MakeShared<FJsonValueString>(TEXT("1,0")));            // not an object
    TSharedRef<FJsonObject> NoY = MakeShared<FJsonObject>();
    NoY->SetNumberField(TEXT("x"), 1);
    Links.Add(MakeShared<FJsonValueObject>(NoY));                     // missing y
    Links.Add(MakeShared<FJsonValueObject>(BgLinkJson(FIntPoint(1, 0)))); // valid
    Links.Add(MakeShared<FJsonValueObject>(BgLinkJson(FIntPoint(1, 0)))); // duplicate
    A->SetArrayField(TEXT("links"), Links);
    TSharedRef<FJsonObject> HalfLayout = MakeShared<FJsonObject>();
    HalfLayout->SetNumberField(TEXT("x"), 5);
    A->SetObjectField(TEXT("layout"), HalfLayout);
    A->SetNumberField(TEXT("start"), 9);
    TSharedRef<FJsonObject> B = MakeShared<FJsonObject>();
    B->SetStringField(TEXT("type"), TEXT("normal"));
    B->SetNumberField(TEXT("x"), 1);
    B->SetNumberField(TEXT("y"), 0);
    B->SetStringField(TEXT("zone"), TEXT("gray")); // legacy single-zone cell
    B->SetStringField(TEXT("start"), TEXT("2"));   // stringified number
    TArray<TSharedPtr<FJsonValue>> Row;
    Row.Add(MakeShared<FJsonValueObject>(A));
    Row.Add(MakeShared<FJsonValueObject>(B));
    TArray<TSharedPtr<FJsonValue>> TolerantRows;
    TolerantRows.Add(MakeShared<FJsonValueArray>(Row));
    TSharedRef<FJsonObject> State = MakeShared<FJsonObject>();
    State->SetNumberField(TEXT("width"), 2);
    State->SetNumberField(TEXT("height"), 1);
    State->SetArrayField(TEXT("cells"), TolerantRows);
    FS08BoardModel Tolerant;
    TestTrue(TEXT("tolerant decode"), Tolerant.Decode(MakeShared<FJsonValueObject>(State)));
    TestTrue(TEXT("tolerant: topology"), Tolerant.bHasTopology);
    TestTrue(TEXT("tolerant: only the valid link kept, once"),
             Tolerant.CellAt(0, 0)->Links.Num() == 1 && Tolerant.CellAt(0, 0)->Links[0] == FIntPoint(1, 0));
    TestFalse(TEXT("tolerant: half layout ignored"), Tolerant.CellAt(0, 0)->bHasLayout);
    TestEqual(TEXT("tolerant: start 9 ignored"), Tolerant.CellAt(0, 0)->StartSlot, 0);
    TestEqual(TEXT("tolerant: stringified start read"), Tolerant.CellAt(1, 0)->StartSlot, 2);
    TestTrue(TEXT("tolerant: legacy `zone` -> zones (backend getCellZones)"),
             Tolerant.CellAt(1, 0)->Zones.Num() == 1 && Tolerant.CellAt(1, 0)->Zones[0] == TEXT("gray"));
    TestTrue(TEXT("tolerant: reverse link symmetrised"),
             Tolerant.IsAdjacent(FIntPoint(1, 0), FIntPoint(0, 0)));
  }
  {
    FS08BoardModel Grid;
    TestTrue(TEXT("grid decodes"), Grid.Decode(BgGridBoardState()));
    TestFalse(TEXT("no links anywhere -> grid board"), Grid.bHasTopology);
    TestTrue(TEXT("re-decode of a topology board into a grid resets topology"),
             Board.Decode(BgGridBoardState()) && !Board.bHasTopology);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardGraphNeighboursTest,
    "Unmatched.S08.BoardGraph.Neighbours links only: lattice neighbour without link is not adjacent, long link is",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardGraphNeighboursTest::RunTest(const FString&) {
  FS08BoardModel Board;
  if (!TestTrue(TEXT("board"), BgSyntheticBoard(Board))) return false;

  const TArray<FIntPoint> N02 = Board.Neighbours(FIntPoint(1, 0));
  TestTrue(TEXT("G02 neighbours = own links in sent order [(0,0),(4,0)]"),
           N02.Num() == 2 && N02[0] == FIntPoint(0, 0) && N02[1] == FIntPoint(4, 0));
  const TArray<FIntPoint> N05 = Board.Neighbours(FIntPoint(4, 0));
  TestTrue(TEXT("G05 (links: []) gets the reverse link to G02"), N05.Num() == 1 && N05[0] == FIntPoint(1, 0));
  const TArray<FIntPoint> N09 = Board.Neighbours(FIntPoint(3, 1));
  TestTrue(TEXT("G09: own link (2,1) first, then the reverse (4,1)"),
           N09.Num() == 2 && N09[0] == FIntPoint(2, 1) && N09[1] == FIntPoint(4, 1));
  TestEqual(TEXT("obstacle hole has no neighbours"), Board.Neighbours(FIntPoint(2, 0)).Num(), 0);
  TestEqual(TEXT("out of bounds has no neighbours"), Board.Neighbours(FIntPoint(9, 9)).Num(), 0);

  TestFalse(TEXT("G02|G07: lattice neighbours WITHOUT a link are not adjacent"),
            Board.IsAdjacent(FIntPoint(1, 0), FIntPoint(1, 1)));
  TestFalse(TEXT("G05|G10: lattice neighbours WITHOUT a link are not adjacent"),
            Board.IsAdjacent(FIntPoint(4, 0), FIntPoint(4, 1)));
  TestTrue(TEXT("G02-G05: one link spanning 3 lattice steps is adjacent"),
           Board.IsAdjacent(FIntPoint(1, 0), FIntPoint(4, 0)));
  TestTrue(TEXT("G05-G02: symmetric"), Board.IsAdjacent(FIntPoint(4, 0), FIntPoint(1, 0)));
  TestTrue(TEXT("G10-G09: declared by G10 only, adjacent both ways"),
           Board.IsAdjacent(FIntPoint(4, 1), FIntPoint(3, 1)) && Board.IsAdjacent(FIntPoint(3, 1), FIntPoint(4, 1)));
  TestFalse(TEXT("a space is not adjacent to itself"), Board.IsAdjacent(FIntPoint(1, 0), FIntPoint(1, 0)));

  TestEqual(TEXT("distance G01 -> G05 = 2 (over the long link)"),
            Board.GraphDistance(FIntPoint(0, 0), FIntPoint(4, 0)), 2);
  TestEqual(TEXT("distance G05 -> G10 = 7 (lattice says 1)"),
            Board.GraphDistance(FIntPoint(4, 0), FIntPoint(4, 1)), 7);
  TestEqual(TEXT("distance to self = 0"), Board.GraphDistance(FIntPoint(2, 1), FIntPoint(2, 1)), 0);
  TestEqual(TEXT("hole unreachable"), Board.GraphDistance(FIntPoint(2, 0), FIntPoint(0, 0)), MAX_int32);

  TestTrue(TEXT("G08 shares its 3rd zone (yellow) with G10"), Board.SharesZone(FIntPoint(2, 1), FIntPoint(4, 1)));
  TestFalse(TEXT("G07 (green) shares nothing with G02 (red, blue)"),
            Board.SharesZone(FIntPoint(1, 1), FIntPoint(1, 0)));
  TestFalse(TEXT("a hole has no zones"), Board.SharesZone(FIntPoint(2, 0), FIntPoint(1, 0)));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardGraphReachTest,
    "Unmatched.S08.BoardGraph.Reachable graph BFS: allies pass, enemies block, occupied end refused, paths and approach",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardGraphReachTest::RunTest(const FString&) {
  FS08BoardModel Board;
  if (!TestTrue(TEXT("board"), BgSyntheticBoard(Board))) return false;

  // 1. Alone, movement 2 from G01: G02, G05 (long link), G06, G07.
  {
    TArray<FS08BoardFighter> Fighters = {BgFighter(TEXT("m"), TEXT("A"), 0, 0)};
    const TSet<uint64> Reach = FS08BoardModel::ComputeReachableCells(Board, Fighters, TEXT("m"), 2);
    const TSet<uint64> Want = BgKeys({FIntPoint(0, 0), FIntPoint(1, 0), FIntPoint(4, 0), FIntPoint(0, 1), FIntPoint(1, 1)});
    TestTrue(FString::Printf(TEXT("reach(2) = {G01,G02,G05,G06,G07}, got %s"), *BgKeysToString(Reach)),
             BgSameSet(Reach, Want));
    TArray<FIntPoint> Path;
    TestTrue(TEXT("path G01 -> G05 over the long link"),
             FS08BoardModel::BuildManeuverPath(Board, Fighters, TEXT("m"), 2, 4, 0, Path) && Path.Num() == 2 &&
                 Path[0] == FIntPoint(1, 0) && Path[1] == FIntPoint(4, 0));
    TestFalse(TEXT("no path to G08 within 2"),
              FS08BoardModel::BuildManeuverPath(Board, Fighters, TEXT("m"), 2, 2, 1, Path));
  }
  // 2. Ally on G02: pass-through, but not an endpoint.
  {
    TArray<FS08BoardFighter> Fighters = {BgFighter(TEXT("m"), TEXT("A"), 0, 0), BgFighter(TEXT("ally"), TEXT("A"), 1, 0)};
    const TSet<uint64> Reach = FS08BoardModel::ComputeReachableCells(Board, Fighters, TEXT("m"), 2);
    TestFalse(TEXT("ally cell is not a legal endpoint"), Reach.Contains(FS08BoardModel::CellKey(1, 0)));
    TestTrue(TEXT("through the ally to G05"), Reach.Contains(FS08BoardModel::CellKey(4, 0)));
    TArray<FIntPoint> Path;
    TestTrue(TEXT("the route crosses the ally"),
             FS08BoardModel::BuildManeuverPath(Board, Fighters, TEXT("m"), 2, 4, 0, Path) && Path.Num() == 2 &&
                 Path[0] == FIntPoint(1, 0));
  }
  // 3. Enemy on G06: blocks G06 and everything behind it - G07 is a LATTICE
  //    neighbour of G02 but not linked, so it stays out of reach.
  {
    TArray<FS08BoardFighter> Fighters = {BgFighter(TEXT("m"), TEXT("A"), 0, 0), BgFighter(TEXT("foe"), TEXT("B"), 0, 1)};
    const TSet<uint64> Reach = FS08BoardModel::ComputeReachableCells(Board, Fighters, TEXT("m"), 3);
    const TSet<uint64> Want = BgKeys({FIntPoint(0, 0), FIntPoint(1, 0), FIntPoint(4, 0)});
    TestTrue(FString::Printf(TEXT("enemy blocks: reach(3) = {G01,G02,G05}, got %s"), *BgKeysToString(Reach)),
             BgSameSet(Reach, Want));
  }
  // 4. Occupied end: an ally standing on G05 - the route through it is fine,
  //    ending there is not; a fighter never ends on a hole either.
  {
    TArray<FS08BoardFighter> Fighters = {BgFighter(TEXT("m"), TEXT("A"), 0, 0), BgFighter(TEXT("ally"), TEXT("A"), 4, 0)};
    const TSet<uint64> Reach = FS08BoardModel::ComputeReachableCells(Board, Fighters, TEXT("m"), 4);
    TestFalse(TEXT("occupied G05 is not an endpoint"), Reach.Contains(FS08BoardModel::CellKey(4, 0)));
    TestFalse(TEXT("hole (2,0) never reachable"), Reach.Contains(FS08BoardModel::CellKey(2, 0)));
    TestFalse(TEXT("hole (3,0) never reachable"), Reach.Contains(FS08BoardModel::CellKey(3, 0)));
  }
  // 5. Approach (S09AUTO): enemy on G10; terrain distance runs over links.
  {
    TArray<FS08BoardFighter> Fighters = {BgFighter(TEXT("m"), TEXT("A"), 0, 0), BgFighter(TEXT("foe"), TEXT("B"), 4, 1)};
    FIntPoint Dest(-1, -1);
    int32 From = 0, To = 0, Steps = 0;
    TestTrue(TEXT("approach picks"),
             FS08BoardModel::PickApproachDestination(Board, Fighters, TEXT("m"), 2, Dest, From, To, Steps));
    TestEqual(TEXT("approach: from G01 = 5 links from G10"), From, 5);
    TestEqual(TEXT("approach: to 3 (G07)"), To, 3);
    TestTrue(FString::Printf(TEXT("approach: G07 (1,1) in 2 steps, got (%d,%d)/%d"), Dest.X, Dest.Y, Steps),
             Dest == FIntPoint(1, 1) && Steps == 2);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardGraphWorldTest,
    "Unmatched.S08.BoardGraph.WorldToCell circle hit, miss between circles, layout frame",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardGraphWorldTest::RunTest(const FString&) {
  FS08BoardModel Board;
  if (!TestTrue(TEXT("board"), BgSyntheticBoard(Board))) return false;
  const FS08LayoutFrame& Frame = Board.LayoutFrame;
  TestFalse(TEXT("default frame (art layer did not set it)"), Frame.bSet);
  TestTrue(TEXT("default src 1337x866"), Frame.SrcSize.Equals(FVector2D(1337.0, 866.0), 1e-6));
  TestTrue(TEXT("default 2/3 uu per px (ENV-O1)"), FMath::IsNearlyEqual(Frame.UuPerPx, 2.0f / 3.0f));
  TestTrue(TEXT("hit radius 63 px = 42 uu"), FMath::IsNearlyEqual(Frame.SpaceRadiusUU(), 42.0f, 1e-3f));
  TestTrue(TEXT("map plane 891.33 x 577.33 uu"),
           Frame.ExtentUU().Equals(FVector2D(891.3333, 577.3333), 1e-2));

  // CellToWorld = ((px/1337 - 0.5) * 891.333, (py/866 - 0.5) * 577.333, 0).
  const FVector G02 = Board.CellToWorld(1, 0);
  TestTrue(FString::Printf(TEXT("G02 world (-245.67,-222.00,0), got (%.3f,%.3f,%.3f)"), G02.X, G02.Y, G02.Z),
           FMath::IsNearlyEqual(G02.X, (300.0 - 668.5) * 2.0 / 3.0, 1e-2) &&
               FMath::IsNearlyEqual(G02.Y, (100.0 - 433.0) * 2.0 / 3.0, 1e-2) && G02.Z == 0.0);

  int32 CX = -7, CY = -7;
  for (int32 Y = 0; Y < Board.Height; ++Y) {
    for (int32 X = 0; X < Board.Width; ++X) {
      if (!Board.IsBoardSpace(X, Y)) continue;
      TestTrue(FString::Printf(TEXT("centre of (%d,%d) round-trips"), X, Y),
               Board.WorldToCell(Board.CellToWorld(X, Y), CX, CY) && CX == X && CY == Y);
    }
  }
  const double UuPerPx = 2.0 / 3.0;
  TestTrue(TEXT("40 px off the G02 centre is inside its circle"),
           Board.WorldToCell(G02 + FVector(40.0 * UuPerPx, 0.0, 0.0), CX, CY) && CX == 1 && CY == 0);
  TestTrue(TEXT("hit on a raised plane (Z ignored)"),
           Board.WorldToCell(G02 + FVector(0.0, 30.0 * UuPerPx, -1.0), CX, CY) && CX == 1 && CY == 0);
  TestFalse(TEXT("70 px off the centre misses (radius 63 px)"),
            Board.WorldToCell(G02 + FVector(70.0 * UuPerPx, 0.0, 0.0), CX, CY));
  TestTrue(TEXT("a miss reports no cell (-1,-1)"), CX == -1 && CY == -1);
  const FVector Between = Frame.ToWorld(FVector2D(300.0, 300.0)); // G02 (300,100) .. G07 (300,500)
  TestFalse(TEXT("between two circles -> no cell"), Board.WorldToCell(Between, CX, CY));
  TestFalse(TEXT("an obstacle hole's fallback position is not clickable"),
            Board.WorldToCell(Board.CellToWorld(2, 0), CX, CY));
  TestFalse(TEXT("far outside the map"), Board.WorldToCell(FVector(0.0, 5000.0, 0.0), CX, CY));

  // Art-layer frame: survives Decode, moves figures and hit circles together.
  TestFalse(TEXT("non-positive frame rejected"), Board.SetLayoutFrame(FVector2D(1337.0, 866.0), 0.0f));
  TestTrue(TEXT("frame set (1 uu per px, radius 50 px)"), Board.SetLayoutFrame(FVector2D(1337.0, 866.0), 1.0f, 50.0f));
  TestTrue(TEXT("re-decode keeps the frame"), BgSyntheticBoard(Board) && Board.LayoutFrame.bSet);
  const FVector G02b = Board.CellToWorld(1, 0);
  TestTrue(TEXT("G02 at 1 uu/px = (-368.5,-333)"),
           FMath::IsNearlyEqual(G02b.X, -368.5, 1e-3) && FMath::IsNearlyEqual(G02b.Y, -333.0, 1e-3));
  TestTrue(TEXT("45 px off hits at radius 50 px"),
           Board.WorldToCell(G02b + FVector(45.0, 0.0, 0.0), CX, CY) && CX == 1 && CY == 0);
  TestFalse(TEXT("55 px off misses at radius 50 px"), Board.WorldToCell(G02b + FVector(55.0, 0.0, 0.0), CX, CY));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardGraphGridRegressionTest,
    "Unmatched.S08.BoardGraph.GridRegression Cobble-style 5x6 grid: neighbour order, reach sets, paths, INT-019 unchanged",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardGraphGridRegressionTest::RunTest(const FString&) {
  FS08BoardModel Board;
  if (!TestTrue(TEXT("grid decodes"), Board.Decode(BgGridBoardState()))) return false;
  TestFalse(TEXT("grid board"), Board.bHasTopology);

  // Neighbour order is the historical +X, -X, +Y, -Y, bounds-filtered.
  const TArray<FIntPoint> Mid = Board.Neighbours(FIntPoint(2, 3));
  TestTrue(TEXT("(2,3): (3,3) (1,3) (2,4) (2,2)"),
           Mid.Num() == 4 && Mid[0] == FIntPoint(3, 3) && Mid[1] == FIntPoint(1, 3) && Mid[2] == FIntPoint(2, 4) &&
               Mid[3] == FIntPoint(2, 2));
  const TArray<FIntPoint> Corner = Board.Neighbours(FIntPoint(0, 0));
  TestTrue(TEXT("(0,0): (1,0) (0,1)"), Corner.Num() == 2 && Corner[0] == FIntPoint(1, 0) && Corner[1] == FIntPoint(0, 1));
  TestTrue(TEXT("grid adjacency = manhattan 1"),
           Board.IsAdjacent(FIntPoint(1, 1), FIntPoint(2, 1)) && !Board.IsAdjacent(FIntPoint(1, 1), FIntPoint(2, 2)) &&
               !Board.IsAdjacent(FIntPoint(1, 1), FIntPoint(1, 1)));
  TestEqual(TEXT("grid distance = manhattan"), Board.GraphDistance(FIntPoint(0, 0), FIntPoint(4, 5)), 9);

  // INT-019 transforms bit for bit.
  int32 CX = 0, CY = 0;
  for (int32 Y = 0; Y < 6; ++Y) {
    for (int32 X = 0; X < 5; ++X) {
      const FVector W = Board.CellToWorld(X, Y);
      TestTrue(FString::Printf(TEXT("INT-019 (%d,%d)"), X, Y),
               W == FVector(X * 100.0f - 200.0f, Y * 100.0f - 250.0f, 0.0f) && Board.WorldToCell(W, CX, CY) &&
                   CX == X && CY == Y);
      TestTrue(TEXT("every grid cell is a board space"), Board.IsBoardSpace(X, Y));
    }
  }
  TestTrue(TEXT("grid hit in the groove still resolves by rounding"),
           Board.WorldToCell(FVector(-200.0f + 49.0f, -250.0f, 0.0f), CX, CY) && CX == 0 && CY == 0);

  // Reach sets and routes identical to the pre-topology algorithms for every
  // mover cell x allowance 0..4, with an ally and an enemy on the board.
  TArray<FS08BoardFighter> Fighters = {BgFighter(TEXT("m"), TEXT("A"), 0, 0), BgFighter(TEXT("ally"), TEXT("A"), 1, 2),
                                       BgFighter(TEXT("foe"), TEXT("B"), 3, 3)};
  int32 Compared = 0, PathsCompared = 0;
  for (int32 Y = 0; Y < 6; ++Y) {
    for (int32 X = 0; X < 5; ++X) {
      const FS08Cell* Cell = Board.CellAt(X, Y);
      if (!Cell || !Cell->IsPassable()) continue;
      if (FS08BoardModel::FighterAt(Fighters, X, Y, TEXT("m"))) continue;
      Fighters[0].X = X;
      Fighters[0].Y = Y;
      for (int32 Allowance = 0; Allowance <= 4; ++Allowance) {
        const TSet<uint64> Old = BgLegacyReachable(Board, Fighters, TEXT("m"), Allowance);
        const TSet<uint64> New = FS08BoardModel::ComputeReachableCells(Board, Fighters, TEXT("m"), Allowance);
        if (!BgSameSet(Old, New)) {
          AddError(FString::Printf(TEXT("reach differs from (%d,%d) allowance %d: old %s new %s"), X, Y, Allowance,
                                   *BgKeysToString(Old), *BgKeysToString(New)));
        }
        ++Compared;
        if (Allowance != 4) continue;
        for (int32 TY = 0; TY < 6; ++TY) {
          for (int32 TX = 0; TX < 5; ++TX) {
            TArray<FIntPoint> OldPath, NewPath;
            const bool bOld = BgLegacyPath(Board, Fighters, TEXT("m"), Allowance, TX, TY, OldPath);
            const bool bNew = FS08BoardModel::BuildManeuverPath(Board, Fighters, TEXT("m"), Allowance, TX, TY, NewPath);
            if (bOld != bNew || OldPath != NewPath) {
              AddError(FString::Printf(TEXT("route differs (%d,%d)->(%d,%d)"), X, Y, TX, TY));
            }
            ++PathsCompared;
          }
        }
      }
    }
  }
  TestTrue(FString::Printf(TEXT("compared %d reach sets and %d routes"), Compared, PathsCompared),
           Compared > 50 && PathsCompared > 300);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardGraphOriginalMapsTest,
    "Unmatched.S08.BoardGraph.OriginalMaps Marmoreal and Sarpedon fixtures: graph, starts, manifest mapping, circles",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardGraphOriginalMapsTest::RunTest(const FString&) {
  for (const TCHAR* Key : {TEXT("marmoreal"), TEXT("sarpedon")}) {
    const FString Path = BgTopologyFixturePath(Key);
    TSharedPtr<FJsonObject> Fixture;
    if (!BgLoadJsonObject(Path, Fixture)) {
      AddInfo(FString::Printf(TEXT("%s: topology fixture absent (%s) - skipped"), Key, *Path));
      continue;
    }
    TSharedPtr<FJsonValue> State;
    if (!TestTrue(FString::Printf(TEXT("%s: fixture -> boardState"), Key), BgFixtureBoardState(Fixture, State))) continue;
    FS08BoardModel Board;
    if (!TestTrue(FString::Printf(TEXT("%s: decodes"), Key), Board.Decode(State))) continue;
    TestTrue(FString::Printf(TEXT("%s: topology board"), Key), Board.bHasTopology);

    const TSharedPtr<FJsonObject>* Summary = nullptr;
    if (!TestTrue(TEXT("summary present"), Fixture->TryGetObjectField(TEXT("summary"), Summary) && Summary)) continue;
    int32 WantSpaces = 0, WantEdges = 0, WantNonLattice = 0;
    (*Summary)->TryGetNumberField(TEXT("spaces"), WantSpaces);
    (*Summary)->TryGetNumberField(TEXT("edges"), WantEdges);
    (*Summary)->TryGetNumberField(TEXT("linksBetweenNonLatticeNeighbours"), WantNonLattice);

    int32 Spaces = 0, LinkEnds = 0;
    for (int32 Y = 0; Y < Board.Height; ++Y) {
      for (int32 X = 0; X < Board.Width; ++X) {
        if (!Board.IsBoardSpace(X, Y)) {
          TestFalse(TEXT("non-space lattice cell is impassable"), Board.CellAt(X, Y)->IsPassable());
          continue;
        }
        ++Spaces;
        LinkEnds += Board.Neighbours(FIntPoint(X, Y)).Num();
      }
    }
    TestEqual(*FString::Printf(TEXT("%s: spaces"), Key), Spaces, WantSpaces);
    TestEqual(*FString::Printf(TEXT("%s: undirected links"), Key), LinkEnds / 2, WantEdges);

    // Every transcribed edge is adjacent both ways; count the long ones.
    int32 NonLattice = 0, LongestSteps = 0;
    for (const TPair<FString, FString>& Edge : BgIdPairs(Fixture, TEXT("edges"))) {
      const FIntPoint A = BgSpacePos(Board, Edge.Key), B = BgSpacePos(Board, Edge.Value);
      TestTrue(FString::Printf(TEXT("%s: edge %s-%s adjacent both ways"), Key, *Edge.Key, *Edge.Value),
               Board.IsAdjacent(A, B) && Board.IsAdjacent(B, A));
      const int32 Lattice = FMath::Abs(A.X - B.X) + FMath::Abs(A.Y - B.Y);
      if (Lattice != 1) ++NonLattice;
      LongestSteps = FMath::Max(LongestSteps, Lattice);
    }
    TestEqual(*FString::Printf(TEXT("%s: links between non-lattice-neighbours"), Key), NonLattice, WantNonLattice);
    // Lattice neighbours the map does NOT connect must never be adjacent.
    const TArray<TPair<FString, FString>> NotLinked = BgIdPairs(*Summary, TEXT("latticeNeighboursNotLinked"));
    TestTrue(FString::Printf(TEXT("%s: has unlinked lattice pairs"), Key), NotLinked.Num() > 0);
    for (const TPair<FString, FString>& Pair : NotLinked) {
      TestFalse(FString::Printf(TEXT("%s: %s|%s lattice neighbours, no link"), Key, *Pair.Key, *Pair.Value),
                Board.IsAdjacent(BgSpacePos(Board, Pair.Key), BgSpacePos(Board, Pair.Value)));
    }
    if (FString(Key) == TEXT("marmoreal")) {
      TestTrue(TEXT("marmoreal: M22-M30 spans 3 lattice steps and is adjacent"),
               Board.IsAdjacent(BgSpacePos(Board, TEXT("M22")), BgSpacePos(Board, TEXT("M30"))) &&
                   FMath::Abs(BgSpacePos(Board, TEXT("M22")).X - BgSpacePos(Board, TEXT("M30")).X) +
                           FMath::Abs(BgSpacePos(Board, TEXT("M22")).Y - BgSpacePos(Board, TEXT("M30")).Y) >= 3);
      TestTrue(TEXT("marmoreal: a long link exists (>= 3 lattice steps)"), LongestSteps >= 3);
    }

    // Start spaces 1..4 exactly as summary.starts.
    const TSharedPtr<FJsonObject>* Starts = nullptr;
    if ((*Summary)->TryGetObjectField(TEXT("starts"), Starts) && Starts) {
      for (const TPair<FString, TSharedPtr<FJsonValue>>& Start : (*Starts)->Values) {
        FString Id;
        Start.Value->TryGetString(Id);
        const FS08Cell* Cell = Board.FindSpace(Id);
        TestTrue(FString::Printf(TEXT("%s: start %s on %s"), Key, *Start.Key, *Id),
                 Cell && Cell->StartSlot == FCString::Atoi(*Start.Key));
      }
    }

    // The default layout frame IS the fixture's recorded frame.
    double FixtureUuPerPx = 0.0, FixtureRadius = 0.0;
    Fixture->TryGetNumberField(TEXT("uuPerPx"), FixtureUuPerPx);
    Fixture->TryGetNumberField(TEXT("spaceRadiusPx"), FixtureRadius);
    TestTrue(FString::Printf(TEXT("%s: default uuPerPx = fixture %.7f"), Key, FixtureUuPerPx),
             FMath::IsNearlyEqual(static_cast<double>(Board.LayoutFrame.UuPerPx), FixtureUuPerPx, 1e-6));
    TestTrue(FString::Printf(TEXT("%s: default radius = fixture %.1f px"), Key, FixtureRadius),
             FMath::IsNearlyEqual(static_cast<double>(Board.LayoutFrame.SpaceRadiusPx), FixtureRadius, 1e-6));

    // CellToWorld of every space = the map-surface manifest mapping
    // "X = (u - 0.5) * board_uu.x, Y = (v - 0.5) * board_uu.y".
    double SrcW = 1337.0, SrcH = 866.0, BoardU = 891.333, BoardV = 577.333;
    TSharedPtr<FJsonObject> Manifest;
    const FString ManifestPath = BgRepoPath(*FString::Printf(TEXT("tools/art/map_surface/manifest.%s.json"), Key));
    if (BgLoadJsonObject(ManifestPath, Manifest)) {
      const TSharedPtr<FJsonObject>* Uv = nullptr;
      const TArray<TSharedPtr<FJsonValue>>* BoardUu = nullptr;
      if (Manifest->TryGetObjectField(TEXT("uv"), Uv) && Uv && (*Uv)->TryGetArrayField(TEXT("board_uu"), BoardUu) &&
          BoardUu && BoardUu->Num() == 2) {
        BoardU = (*BoardUu)[0]->AsNumber();
        BoardV = (*BoardUu)[1]->AsNumber();
      }
      const TSharedPtr<FJsonObject>* Inputs = nullptr;
      const TSharedPtr<FJsonObject>* Image = nullptr;
      const TArray<TSharedPtr<FJsonValue>>* Size = nullptr;
      if (Manifest->TryGetObjectField(TEXT("inputs"), Inputs) && Inputs &&
          (*Inputs)->TryGetObjectField(TEXT("image"), Image) && Image &&
          (*Image)->TryGetArrayField(TEXT("size"), Size) && Size && Size->Num() == 2) {
        SrcW = (*Size)[0]->AsNumber();
        SrcH = (*Size)[1]->AsNumber();
      }
    } else {
      AddInfo(FString::Printf(TEXT("%s: manifest absent (%s) - README constants used"), Key, *ManifestPath));
    }
    TestTrue(FString::Printf(TEXT("%s: frame src = manifest image size"), Key),
             Board.LayoutFrame.SrcSize.Equals(FVector2D(SrcW, SrcH), 1e-6));
    double WorstUu = 0.0;
    int32 Centres = 0;
    int32 CX = 0, CY = 0;
    for (int32 Y = 0; Y < Board.Height; ++Y) {
      for (int32 X = 0; X < Board.Width; ++X) {
        const FS08Cell* Cell = Board.CellAt(X, Y);
        if (!Cell || !Cell->bHasLayout) continue;
        const FVector World = Board.CellToWorld(X, Y);
        const double WantX = (Cell->Layout.X / SrcW - 0.5) * BoardU;
        const double WantY = (Cell->Layout.Y / SrcH - 0.5) * BoardV;
        WorstUu = FMath::Max(WorstUu, FMath::Max(FMath::Abs(World.X - WantX), FMath::Abs(World.Y - WantY)));
        TestTrue(FString::Printf(TEXT("%s: %s centre round-trips"), Key, *Cell->SpaceId),
                 Board.WorldToCell(World, CX, CY) && CX == X && CY == Y);
        ++Centres;
      }
    }
    TestTrue(FString::Printf(TEXT("%s: %d centres on the manifest mapping, worst %.4f uu"), Key, Centres, WorstUu),
             Centres == WantSpaces && WorstUu < 0.01);
    // The midpoint of every link lies between two circles (>= 140 px apart).
    for (const TPair<FString, FString>& Edge : BgIdPairs(Fixture, TEXT("edges"))) {
      const FIntPoint A = BgSpacePos(Board, Edge.Key), B = BgSpacePos(Board, Edge.Value);
      const FVector Mid = (Board.CellToWorld(A.X, A.Y) + Board.CellToWorld(B.X, B.Y)) * 0.5;
      TestFalse(FString::Printf(TEXT("%s: midpoint %s-%s is no cell"), Key, *Edge.Key, *Edge.Value),
                Board.WorldToCell(Mid, CX, CY));
    }
  }
  return true;
}

// ---- ENV-O6 / GAP-023: ranged targets --------------------------------------

namespace S08BoardGraphTest {
/** Viewer 'A': Medusa (ranged) on G08 [green, red, yellow], Harpy A (melee)
 *  on G09 [yellow], Harpy B (melee) on G06 [red]. Enemy 'B': Arthur (melee)
 *  on G10 [blue, yellow], Merlin (ranged) on G02 [red, blue]. */
TArray<FS08BoardFighter> BgRangedRoster() {
  return {BgFighter(TEXT("medusa"), TEXT("A"), 2, 1, TEXT("ranged")), BgFighter(TEXT("harpy-a"), TEXT("A"), 3, 1),
          BgFighter(TEXT("harpy-b"), TEXT("A"), 0, 1), BgFighter(TEXT("arthur"), TEXT("B"), 4, 1),
          BgFighter(TEXT("merlin"), TEXT("B"), 1, 0, TEXT("ranged"))};
}

const FS08BoardFighter& BgRosterFighter(const TArray<FS08BoardFighter>& Fighters, const TCHAR* Id) {
  for (const FS08BoardFighter& F : Fighters) {
    if (F.Id == Id) return F;
  }
  return Fighters[0];
}
} // namespace S08BoardGraphTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09RangedTargetsRuleTest,
    "Unmatched.S09.RangedTargets.Rule ranged = linked or shared 2nd/3rd zone; melee needs a link",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09RangedTargetsRuleTest::RunTest(const FString&) {
  FS08BoardModel Board;
  if (!TestTrue(TEXT("board"), BgSyntheticBoard(Board))) return false;
  const TArray<FS08BoardFighter> Fighters = BgRangedRoster();

  TestTrue(TEXT("'ranged' is ranged"), FS09CommandUi::IsRangedAttacker(BgRosterFighter(Fighters, TEXT("medusa"))));
  TestTrue(TEXT("'range' is ranged (server normalizeAttackType)"),
           FS09CommandUi::IsRangedAttacker(BgFighter(TEXT("x"), TEXT("A"), 0, 0, TEXT("range"))));
  TestFalse(TEXT("'melee' is melee"), FS09CommandUi::IsRangedAttacker(BgRosterFighter(Fighters, TEXT("harpy-a"))));
  TestFalse(TEXT("absent attackType is melee"), FS09CommandUi::IsRangedAttacker(BgFighter(TEXT("x"), TEXT("A"), 0, 0, TEXT(""))));

  const FS08BoardFighter& Medusa = BgRosterFighter(Fighters, TEXT("medusa"));
  const FS08BoardFighter& Arthur = BgRosterFighter(Fighters, TEXT("arthur"));
  const FS08BoardFighter& Merlin = BgRosterFighter(Fighters, TEXT("merlin"));
  TestTrue(TEXT("Medusa -> Arthur: not linked, shared yellow (her 3rd zone, his 2nd)"),
           FS09CommandUi::IsTargetInAttackRange(Board, Medusa, Arthur) &&
               FS09CommandUi::IsZoneOnlyTarget(Board, Medusa, Arthur));
  TestTrue(TEXT("Medusa -> Merlin: shared red (her 2nd zone)"),
           FS09CommandUi::IsTargetInAttackRange(Board, Medusa, Merlin) &&
               FS09CommandUi::IsZoneOnlyTarget(Board, Medusa, Merlin));
  TArray<FString> MedusaTargets = FS09CommandUi::LegalAttackTargets(Board, Fighters, TEXT("medusa"));
  TestTrue(FString::Printf(TEXT("Medusa targets = [arthur, merlin], got [%s]"), *FString::Join(MedusaTargets, TEXT(","))),
           MedusaTargets == TArray<FString>{TEXT("arthur"), TEXT("merlin")});

  const FS08BoardFighter& HarpyA = BgRosterFighter(Fighters, TEXT("harpy-a"));
  TestTrue(TEXT("Harpy A -> Arthur: linked (declared by G10 only)"),
           FS09CommandUi::IsTargetInAttackRange(Board, HarpyA, Arthur) &&
               !FS09CommandUi::IsZoneOnlyTarget(Board, HarpyA, Arthur));
  TestTrue(TEXT("Harpy A targets = [arthur]"),
           FS09CommandUi::LegalAttackTargets(Board, Fighters, TEXT("harpy-a")) == TArray<FString>{TEXT("arthur")});

  const FS08BoardFighter& HarpyB = BgRosterFighter(Fighters, TEXT("harpy-b"));
  TestFalse(TEXT("melee Harpy B cannot hit Merlin: same zone (red) but not linked"),
            FS09CommandUi::IsTargetInAttackRange(Board, HarpyB, Merlin));
  TestEqual(TEXT("Harpy B has no target"), FS09CommandUi::LegalAttackTargets(Board, Fighters, TEXT("harpy-b")).Num(), 0);
  TestTrue(TEXT("ranged Merlin CAN hit Harpy B through the same red zone (rule is seat-independent)"),
           FS09CommandUi::IsTargetInAttackRange(Board, Merlin, HarpyB));

  // Lattice trap: a melee fighter on G07 is a lattice neighbour of Merlin
  // (G02) without a link and shares no zone -> no target.
  const FS08BoardFighter OnG07 = BgFighter(TEXT("harpy-c"), TEXT("A"), 1, 1);
  TestFalse(TEXT("G07|G02 lattice neighbours, no link: melee cannot attack"),
            FS09CommandUi::IsTargetInAttackRange(Board, OnG07, Merlin));
  const FS08BoardFighter RangedOnG07 = BgFighter(TEXT("x"), TEXT("A"), 1, 1, TEXT("ranged"));
  TestFalse(TEXT("... nor ranged (green vs red/blue)"), FS09CommandUi::IsTargetInAttackRange(Board, RangedOnG07, Merlin));

  // Dead / off-board fighters are never offered.
  TArray<FS08BoardFighter> WithDead = Fighters;
  for (FS08BoardFighter& F : WithDead) {
    if (F.Id == TEXT("merlin")) F.Health = 0;
  }
  TestTrue(TEXT("defeated Merlin not offered"),
           FS09CommandUi::LegalAttackTargets(Board, WithDead, TEXT("medusa")) == TArray<FString>{TEXT("arthur")});

  // Grids: the zone rule applies too (server isInSameZone is board-agnostic);
  // a zoneless grid leaves ranged = manhattan 1.
  FS08BoardModel Grid;
  TestTrue(TEXT("grid"), Grid.Decode(BgGridBoardState()));
  const FS08BoardFighter GridArcher = BgFighter(TEXT("archer"), TEXT("A"), 0, 0, TEXT("ranged"));
  const FS08BoardFighter GridBrute = BgFighter(TEXT("brute"), TEXT("A"), 0, 0);
  const FS08BoardFighter FarBlue = BgFighter(TEXT("far"), TEXT("B"), 4, 2);
  const FS08BoardFighter FarRed = BgFighter(TEXT("red"), TEXT("B"), 4, 5);
  TestTrue(TEXT("grid: ranged hits a far same-zone (blue) enemy"), FS09CommandUi::IsTargetInAttackRange(Grid, GridArcher, FarBlue));
  TestFalse(TEXT("grid: melee does not"), FS09CommandUi::IsTargetInAttackRange(Grid, GridBrute, FarBlue));
  TestFalse(TEXT("grid: ranged misses another zone"), FS09CommandUi::IsTargetInAttackRange(Grid, GridArcher, FarRed));
  FS08BoardModel Empty; // no cells, no zones: the pre-ENV rule
  TestTrue(TEXT("zoneless: ranged adjacent ok"),
           FS09CommandUi::IsTargetInAttackRange(Empty, GridArcher, BgFighter(TEXT("n"), TEXT("B"), 1, 0)));
  TestFalse(TEXT("zoneless: ranged at distance 2 refused"),
            FS09CommandUi::IsTargetInAttackRange(Empty, GridArcher, BgFighter(TEXT("n"), TEXT("B"), 2, 0)));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09RangedTargetsDraftTest,
    "Unmatched.S09.RangedTargets.Draft attacker/target/confirm gates accept exactly the legal set",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09RangedTargetsDraftTest::RunTest(const FString&) {
  FS08BoardModel Board;
  if (!TestTrue(TEXT("board"), BgSyntheticBoard(Board))) return false;
  TArray<FS08BoardFighter> Fighters = BgRangedRoster();
  FS09CommandUi Ui;
  Ui.ViewerId = TEXT("A");
  Ui.Mode = ES09CommandMode::AttackDraft;
  FString Reason;

  TestFalse(TEXT("melee Harpy B (only a same-zone enemy) is refused as attacker"),
            Ui.SelectAttacker(TEXT("harpy-b"), Board, Fighters, Reason));
  TestTrue(TEXT("refusal names melee adjacency"), Reason.Contains(TEXT("adjacent")));
  TestTrue(TEXT("ranged Medusa selectable (enemies only in range by zone)"),
           Ui.SelectAttacker(TEXT("medusa"), Board, Fighters, Reason));
  TestTrue(TEXT("Medusa -> Arthur accepted (shared 3rd zone)"), Ui.SelectTarget(TEXT("arthur"), Board, Fighters, Reason));
  TestTrue(TEXT("Medusa -> Merlin accepted (shared 2nd zone)"), Ui.SelectTarget(TEXT("merlin"), Board, Fighters, Reason));
  TestFalse(TEXT("own fighter never a target"), Ui.SelectTarget(TEXT("harpy-a"), Board, Fighters, Reason));

  TestTrue(TEXT("melee Harpy A selectable"), Ui.SelectAttacker(TEXT("harpy-a"), Board, Fighters, Reason));
  TestTrue(TEXT("switching attacker drops the old target"), Ui.AttackTargetId.IsEmpty());
  TestFalse(TEXT("Harpy A -> Merlin refused (not linked, melee)"), Ui.SelectTarget(TEXT("merlin"), Board, Fighters, Reason));
  TestTrue(TEXT("Harpy A -> Arthur accepted (linked)"), Ui.SelectTarget(TEXT("arthur"), Board, Fighters, Reason));

  // Every accepted pair is in LegalAttackTargets and vice versa (GAP-023:
  // highlight == acceptance) for every own attacker x every fighter.
  for (const FS08BoardFighter& Attacker : Fighters) {
    if (Attacker.OwnerId != TEXT("A")) continue;
    const TArray<FString> Offer = FS09CommandUi::LegalAttackTargets(Board, Fighters, Attacker.Id);
    FS09CommandUi Probe;
    Probe.ViewerId = TEXT("A");
    Probe.Mode = ES09CommandMode::AttackDraft;
    const bool bAttacker = Probe.SelectAttacker(Attacker.Id, Board, Fighters, Reason);
    TestTrue(FString::Printf(TEXT("%s selectable iff it has an offer"), *Attacker.Id), bAttacker == (Offer.Num() > 0));
    if (!bAttacker) continue;
    for (const FS08BoardFighter& Target : Fighters) {
      const bool bAccepted = Probe.SelectTarget(Target.Id, Board, Fighters, Reason);
      TestTrue(FString::Printf(TEXT("%s -> %s: accept == offer"), *Attacker.Id, *Target.Id),
               bAccepted == Offer.Contains(Target.Id));
    }
  }

  // Confirm re-derives the range from the fresh board: Arthur stepping to
  // G05 (blue only) leaves Medusa's range; still on G10 the range leg passes
  // and the (empty-hand) card leg is what refuses.
  Ui.AttackAttackerId = TEXT("medusa");
  Ui.AttackTargetId = TEXT("arthur");
  Ui.AttackCardId = TEXT("card::1");
  FS08Snapshot NoHand;
  FS09AttackCommand Command;
  TestFalse(TEXT("confirm without the card in hand refused"), Ui.ConfirmAttack(NoHand, Board, Fighters, Command, Reason));
  TestTrue(FString::Printf(TEXT("range leg passed, card leg refused (%s)"), *Reason), Reason.Contains(TEXT("card")));
  for (FS08BoardFighter& F : Fighters) {
    if (F.Id == TEXT("arthur")) {
      F.X = 4;
      F.Y = 0;
    }
  }
  TestFalse(TEXT("confirm after Arthur left the zone refused"), Ui.ConfirmAttack(NoHand, Board, Fighters, Command, Reason));
  TestTrue(FString::Printf(TEXT("refused on range (%s)"), *Reason), Reason.Contains(TEXT("range")));

  // Board-less overloads follow the last snapshot board; before any
  // snapshot they keep the pre-ENV melee rule (empty board, no zones).
  FS09CommandUi Legacy;
  Legacy.ViewerId = TEXT("A");
  Legacy.Mode = ES09CommandMode::AttackDraft;
  const TArray<FS08BoardFighter> Roster = BgRangedRoster();
  TestFalse(TEXT("no snapshot yet: Medusa has no adjacent enemy"), Legacy.SelectAttacker(TEXT("medusa"), Roster, Reason));
  Legacy.SnapshotBoard = Board; // what OnSnapshot stores
  TestTrue(TEXT("after a snapshot: ranged by zone"), Legacy.SelectAttacker(TEXT("medusa"), Roster, Reason) &&
                                                         Legacy.SelectTarget(TEXT("arthur"), Roster, Reason));
  return true;
}

// ---- ENV-MAPS P5a: S09AUTO auto-attack order (joiner attack plan) --------

namespace S08BoardGraphTest {
FString BgPicksText(const TArray<FS09CommandUi::FAutoAttackPick>& Picks) {
  TArray<FString> Parts;
  for (const FS09CommandUi::FAutoAttackPick& P : Picks) {
    Parts.Add(FString::Printf(TEXT("%s>%s%s"), *P.AttackerId, *P.TargetId, P.bZoneOnly ? TEXT("(zone)") : TEXT("")));
  }
  return FString::Join(Parts, TEXT(","));
}
} // namespace S08BoardGraphTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09AutoAttackPicksTest,
    "Unmatched.S09.RangedTargets.AutoPicks driver order: adjacent first per fighter, zone-only when no link, opt-in ranged preference",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09AutoAttackPicksTest::RunTest(const FString&) {
  FS08BoardModel Board;
  if (!TestTrue(TEXT("board"), BgSyntheticBoard(Board))) return false;
  const TArray<FS08BoardFighter> Fighters = BgRangedRoster();

  // Host side 'A' (default order = the pre-P5a driver loop): Medusa has no
  // linked enemy -> first zone-only enemy (Arthur, shared yellow); Harpy A ->
  // Arthur by link; melee Harpy B has none (Merlin only shares red).
  const FString HostDefault = BgPicksText(FS09CommandUi::AutoAttackPicks(Board, Fighters, TEXT("A"), false));
  TestEqual(TEXT("host default order"), HostDefault, FString(TEXT("medusa>arthur(zone),harpy-a>arthur")));

  // Joiner side 'B' = King Arthur + Merlin. Arthur (melee) hits Harpy A by
  // the G09-G10 link; Merlin (ranged, G02) has NO linked enemy and takes the
  // first enemy of a shared zone: Medusa (red).
  const FString JoinDefault = BgPicksText(FS09CommandUi::AutoAttackPicks(Board, Fighters, TEXT("B"), false));
  TestEqual(TEXT("joiner default order (Fighters order)"), JoinDefault,
            FString(TEXT("arthur>harpy-a,merlin>medusa(zone)")));
  const FString JoinRanged = BgPicksText(FS09CommandUi::AutoAttackPicks(Board, Fighters, TEXT("B"), true));
  TestEqual(TEXT("joiner with the 'ranged' token: Merlin's zone pick first"), JoinRanged,
            FString(TEXT("merlin>medusa(zone),arthur>harpy-a")));

  // The zone pick is a real legal draft pair for the joiner seat.
  FS09CommandUi Ui;
  Ui.ViewerId = TEXT("B");
  Ui.Mode = ES09CommandMode::AttackDraft;
  FString Reason;
  TestTrue(TEXT("Merlin selectable as attacker"), Ui.SelectAttacker(TEXT("merlin"), Board, Fighters, Reason));
  TestTrue(TEXT("Merlin -> Medusa accepted (shared red, not linked)"),
           Ui.SelectTarget(TEXT("medusa"), Board, Fighters, Reason));
  TestTrue(TEXT("... and it is zone-only"),
           FS09CommandUi::IsZoneOnlyTarget(Board, BgRosterFighter(Fighters, TEXT("merlin")),
                                           BgRosterFighter(Fighters, TEXT("medusa"))));

  // A linked enemy wins over the zone for the same fighter: Harpy B moves to
  // G01 (linked to Merlin's G02) -> Merlin attacks it by link, no zone pick.
  TArray<FS08BoardFighter> Linked = Fighters;
  for (FS08BoardFighter& F : Linked) {
    if (F.Id == TEXT("harpy-b")) {
      F.X = 0;
      F.Y = 0;
    }
  }
  TestEqual(TEXT("Merlin with a linked enemy takes the link, even with the ranged token"),
            BgPicksText(FS09CommandUi::AutoAttackPicks(Board, Linked, TEXT("B"), true)),
            FString(TEXT("arthur>harpy-a,merlin>harpy-b")));

  // Dead fighters are neither attackers nor targets.
  TArray<FS08BoardFighter> Dead = Fighters;
  for (FS08BoardFighter& F : Dead) {
    if (F.Id == TEXT("medusa") || F.Id == TEXT("arthur")) F.Health = 0;
  }
  TestEqual(TEXT("defeated Medusa/Arthur: Merlin's only pick is Harpy B by the shared red zone (not linked)"),
            BgPicksText(FS09CommandUi::AutoAttackPicks(Board, Dead, TEXT("B"), true)),
            FString(TEXT("merlin>harpy-b(zone)")));
  TestEqual(TEXT("defeated Medusa: host has only Harpy A (no living linked target) -> none"),
            BgPicksText(FS09CommandUi::AutoAttackPicks(Board, Dead, TEXT("A"), false)), FString());

  // Grids keep the melee-only auto pick (no zone picks without a topology),
  // with or without the token - the recorded Cobble sequence is unchanged.
  FS08BoardModel Grid;
  TestTrue(TEXT("grid"), Grid.Decode(BgGridBoardState()));
  const TArray<FS08BoardFighter> GridRoster = {BgFighter(TEXT("archer"), TEXT("A"), 0, 0, TEXT("ranged")),
                                               BgFighter(TEXT("far"), TEXT("B"), 4, 2),
                                               BgFighter(TEXT("near"), TEXT("B"), 1, 0)};
  TestFalse(TEXT("grid has no topology"), Grid.bHasTopology);
  TestEqual(TEXT("grid: adjacent only"), BgPicksText(FS09CommandUi::AutoAttackPicks(Grid, GridRoster, TEXT("A"), true)),
            FString(TEXT("archer>near")));
  TArray<FS08BoardFighter> GridFar = GridRoster;
  GridFar.RemoveAt(2);
  TestEqual(TEXT("grid: a same-zone far enemy is no auto pick"),
            BgPicksText(FS09CommandUi::AutoAttackPicks(Grid, GridFar, TEXT("A"), true)), FString());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09RangedPositionTest,
    "Unmatched.S09.RangedTargets.RangedPosition 'ranged' plan moves a ranged sidekick by links to a zone-only spot",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09RangedPositionTest::RunTest(const FString&) {
  FS08BoardModel Board;
  if (!TestTrue(TEXT("board"), BgSyntheticBoard(Board))) return false;
  TArray<FS08BoardFighter> Fighters = BgRangedRoster();
  FIntPoint Cell(-1, -1);
  int32 Steps = -1;
  FString Target;
  const TSet<uint64> NoReserved;

  // Merlin on G02 (red, blue): no linked enemy, Medusa shares red -> already in position, stays.
  TestFalse(TEXT("Merlin on G02 already has a zone-only target: stay"),
            FS09CommandUi::PickRangedPosition(Board, Fighters, TEXT("merlin"), 2, NoReserved, Cell, Steps, Target));

  // Merlin on G05 (blue only, linked to G02 only): no enemy in blue -> walk the G05-G02 link back to G02
  // (G01 is 2 steps and linked to Harpy B on G06 - a melee spot, never a ranged pick).
  for (FS08BoardFighter& F : Fighters) {
    if (F.Id == TEXT("merlin")) {
      F.X = 4;
      F.Y = 0;
    }
  }
  TestTrue(TEXT("Merlin on G05 finds a ranged spot"),
           FS09CommandUi::PickRangedPosition(Board, Fighters, TEXT("merlin"), 2, NoReserved, Cell, Steps, Target));
  TestTrue(FString::Printf(TEXT("... G02 (1,0), got (%d,%d)"), Cell.X, Cell.Y), Cell == FIntPoint(1, 0));
  TestEqual(TEXT("... one linked step"), Steps, 1);
  TestEqual(TEXT("... zone target Medusa (shared red)"), Target, FString(TEXT("medusa")));
  TArray<FIntPoint> Path;
  TestTrue(TEXT("the pick is a legal maneuver path over links"),
           FS08BoardModel::BuildManeuverPath(Board, Fighters, TEXT("merlin"), 2, 1, 0, Path) &&
               Path == TArray<FIntPoint>{FIntPoint(1, 0)});

  // G02 reserved by another move of the same draft -> G01 is linked to Harpy B -> no ranged spot.
  TSet<uint64> Reserved;
  Reserved.Add(FS08BoardModel::CellKey(1, 0));
  TestFalse(TEXT("reserved G02 and melee-only G01: no ranged spot"),
            FS09CommandUi::PickRangedPosition(Board, Fighters, TEXT("merlin"), 2, Reserved, Cell, Steps, Target));

  // Melee fighters, dead movers and grids never get a ranged position.
  TestFalse(TEXT("melee Arthur: none"),
            FS09CommandUi::PickRangedPosition(Board, Fighters, TEXT("arthur"), 2, NoReserved, Cell, Steps, Target));
  TArray<FS08BoardFighter> Dead = Fighters;
  for (FS08BoardFighter& F : Dead) {
    if (F.Id == TEXT("merlin")) F.Health = 0;
  }
  TestFalse(TEXT("dead Merlin: none"),
            FS09CommandUi::PickRangedPosition(Board, Dead, TEXT("merlin"), 2, NoReserved, Cell, Steps, Target));
  FS08BoardModel Grid;
  TestTrue(TEXT("grid"), Grid.Decode(BgGridBoardState()));
  const TArray<FS08BoardFighter> GridRoster = {BgFighter(TEXT("archer"), TEXT("B"), 0, 0, TEXT("ranged")),
                                               BgFighter(TEXT("far"), TEXT("A"), 4, 5)};
  TestFalse(TEXT("grid: no ranged positioning (melee-only auto driver on grids)"),
            FS09CommandUi::PickRangedPosition(Grid, GridRoster, TEXT("archer"), 3, NoReserved, Cell, Steps, Target));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09RangedTargetsOriginalMapsTest,
    "Unmatched.S09.RangedTargets.OriginalMaps every space pair: melee = link, ranged = link or shared zone",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09RangedTargetsOriginalMapsTest::RunTest(const FString&) {
  for (const TCHAR* Key : {TEXT("marmoreal"), TEXT("sarpedon")}) {
    TSharedPtr<FJsonObject> Fixture;
    if (!BgLoadJsonObject(BgTopologyFixturePath(Key), Fixture)) {
      AddInfo(FString::Printf(TEXT("%s: topology fixture absent - skipped"), Key));
      continue;
    }
    TSharedPtr<FJsonValue> State;
    FS08BoardModel Board;
    if (!TestTrue(FString::Printf(TEXT("%s: decodes"), Key), BgFixtureBoardState(Fixture, State) && Board.Decode(State))) {
      continue;
    }
    // Oracle straight from the fixture's `spaces` (ids, zones) and `edges`
    // lists - independent of the `cells` the model decoded.
    struct FSpace {
      FString Id;
      TSet<FString> Zones;
    };
    TArray<FSpace> Spaces;
    const TArray<TSharedPtr<FJsonValue>>* SpaceValues = nullptr;
    if (!TestTrue(TEXT("spaces list"), Fixture->TryGetArrayField(TEXT("spaces"), SpaceValues) && SpaceValues)) continue;
    for (const TSharedPtr<FJsonValue>& Value : *SpaceValues) {
      const TSharedPtr<FJsonObject> Object = Value->AsObject();
      if (!Object.IsValid()) continue;
      FSpace Space;
      Space.Id = Object->GetStringField(TEXT("id"));
      const TArray<TSharedPtr<FJsonValue>>* Zones = nullptr;
      if (Object->TryGetArrayField(TEXT("zones"), Zones) && Zones) {
        for (const TSharedPtr<FJsonValue>& Zone : *Zones) Space.Zones.Add(Zone->AsString());
      }
      Spaces.Add(MoveTemp(Space));
    }
    TSet<FString> Edges;
    for (const TPair<FString, FString>& Edge : BgIdPairs(Fixture, TEXT("edges"))) {
      Edges.Add(Edge.Key + TEXT("|") + Edge.Value);
      Edges.Add(Edge.Value + TEXT("|") + Edge.Key);
    }
    int32 Pairs = 0, ZoneOnly = 0, Mismatch = 0;
    for (const FSpace& A : Spaces) {
      for (const FSpace& B : Spaces) {
        if (A.Id == B.Id) continue;
        const FIntPoint PA = BgSpacePos(Board, A.Id), PB = BgSpacePos(Board, B.Id);
        const FS08BoardFighter Archer = BgFighter(TEXT("archer"), TEXT("A"), PA.X, PA.Y, TEXT("ranged"));
        const FS08BoardFighter Brute = BgFighter(TEXT("brute"), TEXT("A"), PA.X, PA.Y);
        const FS08BoardFighter Target = BgFighter(TEXT("target"), TEXT("B"), PB.X, PB.Y);
        const bool bLinked = Edges.Contains(A.Id + TEXT("|") + B.Id);
        const bool bShared = A.Zones.Intersect(B.Zones).Num() > 0;
        const bool bRanged = FS09CommandUi::IsTargetInAttackRange(Board, Archer, Target);
        const bool bMelee = FS09CommandUi::IsTargetInAttackRange(Board, Brute, Target);
        if (bRanged != (bLinked || bShared) || bMelee != bLinked) {
          ++Mismatch;
          AddError(FString::Printf(TEXT("%s: %s -> %s linked=%d shared=%d ranged=%d melee=%d"), Key, *A.Id, *B.Id,
                                   bLinked ? 1 : 0, bShared ? 1 : 0, bRanged ? 1 : 0, bMelee ? 1 : 0));
        }
        if (!bLinked && bShared) ++ZoneOnly;
        ++Pairs;
      }
    }
    TestTrue(FString::Printf(TEXT("%s: %d ordered pairs checked, %d ranged-only-by-zone, %d mismatches"), Key, Pairs,
                             ZoneOnly, Mismatch),
             Pairs > 0 && ZoneOnly > 0 && Mismatch == 0);
  }
  return true;
}

#endif // WITH_AUTOMATION_TESTS

// GD-030 (TASK-020/021): typed board model decoded from the authoritative
// FS08Snapshot projections. Coordinate contract INT-019 (08-integration
// decisions section 4):
//   World(x,y) = ((x - (W-1)/2)*100, (y - (H-1)/2)*100, 0)
//   cell = round(w/100 + (W-1)/2), round(h/100 + (H-1)/2), bounds-checked.
// Row y=0 is the FAR (north) row; camera yaw -90 looks along -Y.
// Movement legality mirrors backend traversal.ts (GD-015): steps go to a
// board NEIGHBOUR, walls/obstacles/closed doors block, living allies are
// pass-through, living enemies block, the destination must hold no living
// fighter.
//
// ENV-MAPS (original maps Marmoreal/Sarpedon, contract
// unmatched.board-topology/1, backend game-engine/engine/board-topology.ts):
// the server still sends a W x H lattice (Position {x,y} unchanged), but a
// space cell carries `links` [{x,y}] (lattice positions of the linked
// spaces), `layout` {x,y} (circle centre in map-image px), `start` (1..4)
// and `spaceId`; every non-space lattice cell is 'obstacle'. The board HAS
// TOPOLOGY iff any cell carries a `links` array; then the neighbours of a
// cell are EXACTLY its links (symmetrised) - a lattice neighbour without a
// link is NOT adjacent and one link may span several lattice steps - and
// CellToWorld/WorldToCell go through the layout (FS08LayoutFrame). Without
// links every rule below is the old orthogonal grid, bit for bit.
#pragma once

#include "CoreMinimal.h"
#include "S08Contracts.h"

enum class ES08CellType : uint8 { Normal, Wall, Obstacle, Door, Unknown };

struct UNMATCHED_API FS08Cell {
  ES08CellType Type = ES08CellType::Unknown;
  int32 X = 0;
  int32 Y = 0;
  TArray<FString> Zones; // multizone cell may list several
  bool bIsOpen = true;   // door state (doors map / cell flag)
  // ENV-MAPS space data (absent on grid boards). Links are the lattice
  // positions as SENT by this cell; FS08BoardModel::Neighbours symmetrises.
  bool bHasLinks = false;       // the cell carried a `links` array (topology marker, may be empty)
  TArray<FIntPoint> Links;
  bool bHasLayout = false;      // `layout` present: this cell is a map space
  FVector2D Layout = FVector2D::ZeroVector; // circle centre, map-image px (x right, y down)
  int32 StartSlot = 0;          // start space number 1..4, 0 = none
  FString SpaceId;              // 'M01'..'M31' / 'S01'..'S38', empty on grids
  bool IsPassable() const {
    if (Type == ES08CellType::Wall || Type == ES08CellType::Obstacle) return false;
    if (Type == ES08CellType::Door && !bIsOpen) return false;
    return true;
  }
};

/** ENV-MAPS layout frame: map-image px -> world uu for topology boards.
 *  World = ((px.x/SrcW - 0.5) * SrcW * UuPerPx, (px.y/SrcH - 0.5) * SrcH * UuPerPx, 0)
 *  - the map-surface manifest mapping "X = (u - 0.5) * 891.333,
 *  Y = (v - 0.5) * 577.333" (u = px.x/1337, v = px.y/866, v down = towards
 *  the K1 camera) with the ENV-O1 defaults, so figures sit on the painted
 *  circles even when the art layer never calls SetLayoutFrame. A click hits
 *  a space within SpaceRadiusPx of its centre (63 px = 42 uu at 2/3). */
struct UNMATCHED_API FS08LayoutFrame {
  static constexpr float DefaultSrcWidthPx = 1337.0f;
  static constexpr float DefaultSrcHeightPx = 866.0f;
  static constexpr float DefaultUuPerPx = 2.0f / 3.0f;
  static constexpr float DefaultSpaceRadiusPx = 63.0f;

  FVector2D SrcSize = FVector2D(DefaultSrcWidthPx, DefaultSrcHeightPx);
  float UuPerPx = DefaultUuPerPx;
  float SpaceRadiusPx = DefaultSpaceRadiusPx;
  bool bSet = false; // true once the art layer set it explicitly

  FVector ToWorld(const FVector2D& Px) const {
    return FVector((Px.X / SrcSize.X - 0.5) * SrcSize.X * UuPerPx,
                   (Px.Y / SrcSize.Y - 0.5) * SrcSize.Y * UuPerPx, 0.0);
  }
  float SpaceRadiusUU() const { return SpaceRadiusPx * UuPerPx; }
  /** Full world size of the map plane (891.33 x 577.33 uu by default). */
  FVector2D ExtentUU() const { return SrcSize * UuPerPx; }
};

/** Fighter as needed by the grey board (TASK-021 mannequin data). */
struct UNMATCHED_API FS08BoardFighter {
  FString Id;
  FString OwnerId;
  FString Name;
  bool bIsHero = false;
  int32 Health = 0;
  int32 MaxHealth = 0;
  int32 X = -1;
  int32 Y = -1;
  int32 Movement = 0;
  FString AttackType;
  FString Label; // display label: 'Medusa', 'Harpies 2', ...
  // Public fighter effects from the projection (`effects[]`: a string, or an
  // object's type/name/id). Plate status chips only (ART-004 T2.2).
  TArray<FString> Effects;
  bool IsAlive() const { return Health > 0 && X >= 0; }
};

class UNMATCHED_API FS08BoardModel {
public:
  static constexpr float CellSizeUU = 100.0f;

  int32 Width = 0;
  int32 Height = 0;
  TArray<FS08Cell> Cells; // flat, index = Y * Width + X (Unknown when absent)

  /** ENV-MAPS: true iff any cell carried a `links` array (set by Decode /
   *  RebuildTopology). Never set it by hand - call RebuildTopology. */
  bool bHasTopology = false;
  /** ENV-MAPS layout frame (map-image px -> uu). Survives Decode: the art
   *  layer sets it once per map-image profile; defaults = ENV-O1 mapping. */
  FS08LayoutFrame LayoutFrame;

  /** Decodes boardState projection (cells[y][x] rows, doors map). Returns
   *  false when the projection is not a usable board object. */
  bool Decode(const TSharedPtr<FJsonValue>& BoardState);

  /** Recomputes bHasTopology and the symmetrised link index from
   *  Cells[].bHasLinks/Links (Decode calls it; hand-built test boards call
   *  it after filling the links). */
  void RebuildTopology();

  /** Art layer hook (map-image profile): source image size in px, uu per px
   *  and hit radius in px. Rejects non-positive values (frame unchanged). */
  bool SetLayoutFrame(const FVector2D& SrcSizePx, float UuPerPx,
                      float SpaceRadiusPx = FS08LayoutFrame::DefaultSpaceRadiusPx);

  const FS08Cell* CellAt(int32 X, int32 Y) const {
    if (X < 0 || Y < 0 || X >= Width || Y >= Height) return nullptr;
    return &Cells[Y * Width + X];
  }

  /** Board neighbours of Cell - the ONE adjacency rule of the client
   *  (mirror of backend board-topology.neighbours):
   *  - topology board: the cell's own links in the order sent, then the
   *    reverse links declared only by the other cell; out-of-bounds links and
   *    self-links dropped; a cell without links has none;
   *  - grid board: the in-bounds orthogonal cells in the client's historical
   *    order (+X, -X, +Y, -Y) - every grid BFS keeps its old result.
   *  Terrain and fighters are NOT checked here. */
  TArray<FIntPoint> Neighbours(const FIntPoint& Cell) const;
  /** Topology: linked; grid: manhattan 1 (no bounds check, the old attack
   *  rule). A cell is never adjacent to itself. */
  bool IsAdjacent(const FIntPoint& A, const FIntPoint& B) const;
  /** "Spaces between" (backend boardDistance): topology = BFS over the links
   *  ignoring terrain and fighters (MAX_int32 when unreachable / out of
   *  bounds); grid = manhattan. 0 for A == B. */
  int32 GraphDistance(const FIntPoint& A, const FIntPoint& B) const;
  /** Backend isInSameZone: A's cell has >= 1 zone and B's cell lists one of
   *  them (multizone spaces are in all their zones). */
  bool SharesZone(const FIntPoint& A, const FIntPoint& B) const;
  /** True when (X,Y) is a position of the board a figure/highlight may use:
   *  every in-bounds cell of a grid; only the map spaces (cells with a
   *  layout) of a topology board. */
  bool IsBoardSpace(int32 X, int32 Y) const {
    const FS08Cell* Cell = CellAt(X, Y);
    return Cell && (!bHasTopology || Cell->bHasLayout);
  }
  /** The map space with this id (nullptr when absent / grid board). */
  const FS08Cell* FindSpace(const FString& SpaceId) const;
  /** Readable position for toasts/traces: 'M13' on a topology space, else
   *  '(x,y)'. */
  FString CellLabel(int32 X, int32 Y) const;

  // INT-019 transforms (board center at world origin, Z=0 play plane).
  // Topology boards: a space maps through LayoutFrame; a non-space lattice
  // cell (obstacle, no layout) keeps the INT-019 grid position as a fallback
  // (never rendered - see IsBoardSpace).
  FVector CellToWorld(int32 X, int32 Y) const {
    if (bHasTopology) {
      const FS08Cell* Cell = CellAt(X, Y);
      if (Cell && Cell->bHasLayout) return LayoutFrame.ToWorld(Cell->Layout);
    }
    const float Ox = (Width - 1) * 0.5f * CellSizeUU;
    const float Oy = (Height - 1) * 0.5f * CellSizeUU;
    return FVector(X * CellSizeUU - Ox, Y * CellSizeUU - Oy, 0.0f);
  }
  /** Grid: nearest cell square (bounds-checked). Topology: the space whose
   *  circle (LayoutFrame.SpaceRadiusUU) contains World.XY, nearest centre
   *  wins; between circles -> false with OutX = OutY = -1 ("no cell"). */
  bool WorldToCell(const FVector& World, int32& OutX, int32& OutY) const {
    if (bHasTopology) return WorldToSpace(World, OutX, OutY);
    const float Ox = (Width - 1) * 0.5f * CellSizeUU;
    const float Oy = (Height - 1) * 0.5f * CellSizeUU;
    OutX = FMath::RoundToInt(World.X / CellSizeUU + Ox / CellSizeUU);
    OutY = FMath::RoundToInt(World.Y / CellSizeUU + Oy / CellSizeUU);
    return OutX >= 0 && OutY >= 0 && OutX < Width && OutY < Height;
  }

  /** True when the cell holds a living fighter other than IgnoreFighterId. */
  static const FS08BoardFighter* FighterAt(const TArray<FS08BoardFighter>& Fighters,
                                           int32 X, int32 Y, const FString& IgnoreFighterId);

  /** Mirrors backend traversal/validateManeuver legality for one step into
   *  (X,Y) by Mover: passable terrain, living enemy blocks, living ally ok. */
  static bool IsStepTraversable(const FS08BoardModel& Board,
                                const TArray<FS08BoardFighter>& Fighters,
                                const FS08BoardFighter& Mover, int32 X, int32 Y);

  /** Destination rule: no OTHER living fighter on (X,Y). */
  static bool IsEndpointFree(const TArray<FS08BoardFighter>& Fighters,
                             const FS08BoardFighter& Mover, int32 X, int32 Y);

  /** BFS over legal movement (TASK-027 grey subset): every cell reachable by
   *  a path of <= Allowance neighbour steps (Neighbours: links / orthogonal)
   *  under the traversal rules; results are cells where the mover may
   *  legally END the move (endpoint free) plus the mover's own cell
   *  (zero-length legal resolve). */
  static TSet<uint64> ComputeReachableCells(const FS08BoardModel& Board,
                                            const TArray<FS08BoardFighter>& Fighters,
                                            const FString& FighterId, int32 Allowance);

  /** Shortest legal route from the fighter's cell to (TargetX,TargetY) under
   *  the same rules as ComputeReachableCells. The backend maneuver validator
   *  expects the path WITHOUT the fighter's starting cell (every entry must
   *  be one neighbour step - a link on topology boards - after the previous
   *  one, starting from the fighter's current position). Empty when no
   *  legal route exists. */
  static bool BuildManeuverPath(const FS08BoardModel& Board,
                                const TArray<FS08BoardFighter>& Fighters,
                                const FString& FighterId, int32 Allowance,
                                int32 TargetX, int32 TargetY,
                                TArray<FIntPoint>& OutPath);

  /** Multi-step approach of the S09AUTO demo driver (stage 3 T5.2). Scores
   *  every cell the mover may legally END a move on (ComputeReachableCells
   *  with Allowance; allies pass-through, enemies block) by the terrain
   *  distance to the NEAREST living enemy: a neighbour BFS over passable
   *  cells that starts at the enemies' cells and ignores fighters, so 1 means
   *  "adjacent (linked / orthogonal) = melee range of the auto attack". Picks the
   *  lowest score; ties go to fewer steps (shortest legal route), then lower
   *  Y, then lower X (deterministic). Returns false when no reachable cell is
   *  strictly closer than the mover's own cell (already adjacent, boxed in,
   *  no living enemy, or no enemy reachable through terrain). The former
   *  one-cell greedy step could not leave a start cell whose four
   *  neighbours are an obstacle and own fighters (T.Rex art fixture). */
  static bool PickApproachDestination(const FS08BoardModel& Board,
                                      const TArray<FS08BoardFighter>& Fighters,
                                      const FString& MoverId, int32 Allowance,
                                      FIntPoint& OutCell, int32& OutFromDistance,
                                      int32& OutToDistance, int32& OutSteps);

  static uint64 CellKey(int32 X, int32 Y) {
    return (static_cast<uint64>(static_cast<uint32>(X)) << 32) |
           static_cast<uint32>(Y);
  }

  /** Decodes the fighters projection into grey-board fighters; same-name
   *  fighters get numbered labels ('Harpies' x3 -> 'Harpies 1/2/3') per
   *  TASK-021, keyed by stable fighter id (never by array order). */
  static bool DecodeFighters(const TSharedPtr<FJsonValue>& FightersValue,
                             TArray<FS08BoardFighter>& OutFighters);

private:
  /** Topology hit test behind WorldToCell. */
  bool WorldToSpace(const FVector& World, int32& OutX, int32& OutY) const;
  /** Symmetrised neighbour lists per flat cell index (backend linkIndex
   *  order), built from Cells[].Links. */
  static void BuildLinkIndex(const FS08BoardModel& Board, TArray<TArray<FIntPoint>>& OutIndex);

  // Per flat cell index; empty on grid boards. Rebuilt by RebuildTopology.
  TArray<TArray<FIntPoint>> LinkIndex;
};

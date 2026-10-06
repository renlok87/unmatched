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
//
// MS-T-03 (move selection, docs/game-design/move-selection/04 §3.1): the
// canonical reach and path - ComputeReachMap (FIFO BFS, dist/parent, step
// limit `>=`) and BuildCanonicalPath (predecessor with the smallest key
// K = (spaceId ordinal, y, x) on a topology board, (y, x) on a grid) - mirror
// backend game-engine/movement/canonical-path.ts. FighterMovement mirrors
// getFighterMovement on the RAW `movement` value; the "alive" predicates are
// split by role exactly as on the server. Parity: the golden fixtures
// backend/prisma/fixtures/movement (S08MoveParityTests.cpp, MS-AT-10).
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
  // Legacy int decode of `movement` (ReadIntLike: 3.5 -> 3, absent/0 -> 0).
  // Kept for the callers MS-T-04 moves to FS08BoardModel::FighterMovement;
  // the movement RULE is FighterMovement on MovementRaw (MS-E-04, MS-E-107).
  int32 Movement = 0;
  // MS-T-03: raw `movement` as the server holds it, converted like JS
  // Number(x) (number; numeric string; true -> 1; null -> 0; unparsable or
  // absent -> NaN). bMovementPresent: the field was sent (null included).
  double MovementRaw = 0.0;
  bool bMovementPresent = false;
  // MS-T-03: the projection's `isDefeated` (JS truthiness). With health > 0
  // it is "dirty" data: the server ignores it for a maneuver mover but treats
  // the fighter as dead for blocking and occupying (MS-E-24, MS-E-77).
  bool bDefeated = false;
  FString AttackType;
  // DE-020 (SD-56): the projection's `heroSlug` (the hero the fighter belongs to - its sidekicks carry the same
  // slug). The hero ability boost of an attack (King Arthur) is offered by it, as the server's
  // abilityBoostAllowed decides (HERO fighter of the handler's hero).
  FString HeroSlug;
  FString Label; // display label: 'Medusa', 'Harpies 2', ...
  // Public fighter effects from the projection (`effects[]`: a string, or an
  // object's type/name/id). Plate status chips only (ART-004 T2.2).
  TArray<FString> Effects;
  /** Display predicate: a figure stands on the board (health > 0 and a
   *  position). Not a movement rule - see the two role predicates below. */
  bool IsAlive() const { return Health > 0 && X >= 0; }
  /** Role "blocks a step / occupies a cell / is moved by an effect": backend
   *  traversal.isLivingFighter (health > 0 && !isDefeated). A living enemy
   *  blocks the step, any such fighter makes the cell an illegal END; the
   *  resolve of a MOVE/PLACE effect also requires it of the moved fighter
   *  (except the revive PLACE). MS-E-23, MS-E-24. */
  bool IsAliveBlocker() const { return Health > 0 && !bDefeated; }
  /** Role "maneuver mover": validateManeuver rejects only health <= 0, so a
   *  fighter with isDefeated and health > 0 still moves (MS-E-77). */
  bool CanBeMover() const { return Health > 0; }
  /** Test/hand-built helper: sets the raw value and the legacy int decode as
   *  DecodeFighters would for a JSON number. */
  void SetRawMovement(double Raw) {
    MovementRaw = Raw;
    bMovementPresent = true;
    Movement = FMath::IsFinite(Raw) ? static_cast<int32>(FMath::Clamp(Raw, -2147483648.0, 2147483647.0)) : 0;
  }
};

/** Options of ComputeReachMap (backend canonical-path ReachOptions). */
struct UNMATCHED_API FS08ReachOptions {
  /** Living enemies do not block steps (Winged Frenzy, pending
   *  canPassThroughEnemies). The END cell rule is unchanged. */
  bool bPassThroughEnemies = false;
};

/** 04 §3.1 computeReach result: BFS distances from the mover's cell. Only
 *  Dist is normative; Parent/Order depend on the neighbour order (the client
 *  grid order is +X, -X, +Y, -Y, the server's N, E, S, W) and are NOT. */
struct UNMATCHED_API FS08ReachMap {
  /** The mover was found and has a board position (X, Y >= 0). An invalid
   *  map reaches nothing, not even the start. */
  bool bValid = false;
  FString MoverId;
  FString OwnerId;
  FIntPoint Start = FIntPoint(-1, -1);
  /** Step limit; MAX_int32 = no limit (cue fallback, 04 §4.6). */
  int32 MaxSteps = 0;
  bool bPassThroughEnemies = false;
  /** CellKey -> steps from the start (start = 0). */
  TMap<uint64, int32> Dist;
  /** CellKey -> CellKey of the BFS discovery parent; the start has none. */
  TMap<uint64, uint64> Parent;
  /** FIFO discovery order (the BFS queue), start first. */
  TArray<FIntPoint> Order;

  /** Steps to Cell, INDEX_NONE when not reached. */
  int32 DistanceTo(const FIntPoint& Cell) const;
  bool Reaches(const FIntPoint& Cell) const { return DistanceTo(Cell) != INDEX_NONE; }
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

  /** The fighter standing on (X,Y) in the "occupies a cell" role
   *  (IsAliveBlocker, with a board position) other than IgnoreFighterId. */
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

  // ---- MS-T-03: canonical reach and path (04 §3.1) -------------------------

  /** backend getFighterMovement on the RAW value: Number(movement) that is an
   *  integer >= 1, otherwise 2 (absent, null, 0, 2.5, 3.5, "3.5", "abc" -> 2;
   *  "3" -> 3). Values above MAX_int32 clamp to it (practically unlimited),
   *  so a caller adding BOOST widens to int64 before clamping the sum. */
  static constexpr int32 DefaultFighterMovement = 2;
  static int32 FighterMovement(const FS08BoardFighter& Fighter);

  /** JS Number(x) of a JSON value (absent -> NaN, null -> 0, bool -> 0/1,
   *  string -> StringToNumber, [] -> 0, [v] -> Number(v), other arrays and
   *  objects -> NaN). The raw-movement decode of DecodeFighters. */
  static double JsNumber(const TSharedPtr<FJsonValue>& Value);

  /** 04 §3.1 computeReach: FIFO BFS from the mover's cell over Neighbours;
   *  a cell at distance d >= MaxSteps is not expanded; a step enters only a
   *  passable cell (in bounds, not wall/obstacle/closed door) without a
   *  living enemy of the mover (IsAliveBlocker, other owner) unless
   *  bPassThroughEnemies. Allies and defeated fighters never block. MaxSteps
   *  < 0 or no board reach only the start. The mover's own state is NOT
   *  checked - that is the caller's role (CanBeMover for a maneuver,
   *  IsAliveBlocker for an effect). Missing mover or no position -> invalid. */
  static FS08ReachMap ComputeReachMap(const FS08BoardModel& Board,
                                      const TArray<FS08BoardFighter>& Fighters,
                                      const FString& MoverId, int32 MaxSteps,
                                      const FS08ReachOptions& Options = FS08ReachOptions());

  /** 04 §3.1 isEndpoint: the start ("stay") or a cell without another fighter
   *  in the occupant role (IsAliveBlocker). Reach distance is not checked. */
  static bool IsReachEndpoint(const TArray<FS08BoardFighter>& Fighters, const FS08ReachMap& Reach,
                              const FIntPoint& Cell);

  /** Total order of cells by K: (SpaceId, Y, X) on a topology board - the
   *  SpaceId compared ordinally, case sensitive (UTF-16 code units, as JS
   *  `<`) - and (Y, X) on a grid. <0, 0, >0. */
  static int32 CompareCanonical(const FS08BoardModel& Board, const FIntPoint& A, const FIntPoint& B);

  /** 04 §3.1 canonicalPath: the path WITHOUT the start cell (wire format of
   *  maneuver.moves[].path). Dest == start -> true with an empty path
   *  ("stay", never sent). Dest not reached or not an endpoint -> false.
   *  Every predecessor is the neighbour one step closer with the smallest
   *  K, so the path does not depend on the order of links or neighbours. */
  static bool BuildCanonicalPath(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                                 const FS08ReachMap& Reach, const FIntPoint& Dest,
                                 TArray<FIntPoint>& OutPath);

  /** backend reachableEndpoints: cells at 1..MaxSteps steps that may END the
   *  move (start excluded), sorted by K. Plate tiers split this list by
   *  distance (04 §3.2, MS-E-80). */
  static TArray<FIntPoint> ReachEndpoints(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                                          const FS08ReachMap& Reach, int32 MaxSteps);

  // ---- legacy wrappers ------------------------------------------------------
  // Behaviour unchanged except the server rules this task brings into the
  // model: a fighter blocks/occupies only in the IsAliveBlocker role (a
  // dirty-defeated fighter no longer does, MS-E-24), ids compare exactly,
  // and a cell holding any living enemy blocks (formerly only the first
  // fighter found on the cell decided - two fighters never share a cell).

  /** Wrapper over ComputeReachMap (TASK-027 contract kept): empty when the
   *  mover is missing, not IsAlive() or Allowance < 0; otherwise the mover's
   *  own cell (zero-length legal resolve) plus every cell at 1..Allowance
   *  steps where the mover may legally END the move (IsReachEndpoint). On
   *  game data the set equals the former DFS-with-relaxation result. */
  static TSet<uint64> ComputeReachableCells(const FS08BoardModel& Board,
                                            const TArray<FS08BoardFighter>& Fighters,
                                            const FString& FighterId, int32 Allowance);

  /** Wrapper over ComputeReachMap: a shortest legal route from the fighter's
   *  cell to (TargetX,TargetY) WITHOUT the starting cell; true with an empty
   *  path for the own cell; false when unreached. Kept as before: the
   *  route among equal shortest ones is the former reverse walk (first
   *  Neighbours entry one step closer), NOT the canonical K choice, and the
   *  end cell is not checked for occupants. New code calls
   *  BuildCanonicalPath; callers move in MS-T-04/05/07. */
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
   *  fighters of one owner get numbered labels ('Harpies' x3 -> 'Harpies
   *  1/2/3') per TASK-021 in the server's seat order (= sidekicks[], fixed for
   *  the game: defeated fighters stay in the array; VS-2 CP-12). Also reads
   *  the raw `movement` (JsNumber) and `isDefeated` (MS-T-03). */
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

// GD-030 (TASK-020/021): typed board model decoded from the authoritative
// FS08Snapshot projections. Coordinate contract INT-019 (08-integration
// decisions section 4):
//   World(x,y) = ((x - (W-1)/2)*100, (y - (H-1)/2)*100, 0)
//   cell = round(w/100 + (W-1)/2), round(h/100 + (H-1)/2), bounds-checked.
// Row y=0 is the FAR (north) row; camera yaw -90 looks along -Y.
// Movement legality mirrors backend traversal.ts (GD-015): orthogonal steps,
// walls/obstacles/closed doors block, living allies are pass-through, living
// enemies block, the destination must hold no living fighter.
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
  bool IsPassable() const {
    if (Type == ES08CellType::Wall || Type == ES08CellType::Obstacle) return false;
    if (Type == ES08CellType::Door && !bIsOpen) return false;
    return true;
  }
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

  /** Decodes boardState projection (cells[y][x] rows, doors map). Returns
   *  false when the projection is not a usable board object. */
  bool Decode(const TSharedPtr<FJsonValue>& BoardState);

  const FS08Cell* CellAt(int32 X, int32 Y) const {
    if (X < 0 || Y < 0 || X >= Width || Y >= Height) return nullptr;
    return &Cells[Y * Width + X];
  }

  // INT-019 transforms (board center at world origin, Z=0 play plane).
  FVector CellToWorld(int32 X, int32 Y) const {
    const float Ox = (Width - 1) * 0.5f * CellSizeUU;
    const float Oy = (Height - 1) * 0.5f * CellSizeUU;
    return FVector(X * CellSizeUU - Ox, Y * CellSizeUU - Oy, 0.0f);
  }
  bool WorldToCell(const FVector& World, int32& OutX, int32& OutY) const {
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
   *  an orthogonal path of <= Allowance steps under the traversal rules;
   *  results are cells where the mover may legally END the move (endpoint
   *  free) plus the mover's own cell (zero-length legal resolve). */
  static TSet<uint64> ComputeReachableCells(const FS08BoardModel& Board,
                                            const TArray<FS08BoardFighter>& Fighters,
                                            const FString& FighterId, int32 Allowance);

  /** Shortest legal route from the fighter's cell to (TargetX,TargetY) under
   *  the same rules as ComputeReachableCells. The backend maneuver validator
   *  expects the path WITHOUT the fighter's starting cell (every entry must
   *  be one orthogonal step after the previous one, starting from the
   *  fighter's current position). Empty when no legal route exists. */
  static bool BuildManeuverPath(const FS08BoardModel& Board,
                                const TArray<FS08BoardFighter>& Fighters,
                                const FString& FighterId, int32 Allowance,
                                int32 TargetX, int32 TargetY,
                                TArray<FIntPoint>& OutPath);

  /** Multi-step approach of the S09AUTO demo driver (stage 3 T5.2). Scores
   *  every cell the mover may legally END a move on (ComputeReachableCells
   *  with Allowance; allies pass-through, enemies block) by the terrain
   *  distance to the NEAREST living enemy: an orthogonal BFS over passable
   *  cells that starts at the enemies' cells and ignores fighters, so 1 means
   *  "orthogonally adjacent = melee range of the auto attack". Picks the
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
};

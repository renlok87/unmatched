// GD-030 (TASK-020/021/022): grey board built ONLY from the decoded
// FS08Snapshot.BoardState + Fighters (never a fabricated arrangement).
// Tiles are instanced cubes (100x100 uu per INT-019); fighters are grey
// mannequins with a team-colored base (own=blue, enemy=red) and a numbered
// text label (same-name sidekicks stay distinguishable, e.g. Harpies 1/2/3).
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "S08BoardModel.h"
#include "S08BoardActor.generated.h"

class UInstancedStaticMeshComponent;
class UStaticMeshComponent;
class UTextRenderComponent;
class AS08FighterActor;
class UMaterialInterface;
class UMaterialInstanceDynamic;

UCLASS()
class UNMATCHED_API AS08BoardActor : public AActor {
  GENERATED_BODY()

public:
  AS08BoardActor();

  /** (Re)builds tiles from the decoded board. Rebuilds only when the board
   *  signature changes (width/height/cell types), so same-seq merges are
   *  cheap. Returns false when the board could not be decoded. */
  bool Rebuild(const FS08BoardModel& Board);

  /** Syncs fighter actors with the latest decoded fighters (spawn/move/
   *  re-label by stable fighter id; dead fighters hide instantly). */
  void SyncFighters(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                    const FString& OwnOwnerId);

  const FS08BoardModel& GetBoard() const { return BoardModel; }
  const TArray<FS08BoardFighter>& GetFighters() const { return Fighters; }
  AS08FighterActor* FindFighterActor(const FString& FighterId) const;

  /** TASK-022 selection ring + reachable-cell highlights. */
  void SetSelectedFighter(const FString& FighterId, const TSet<uint64>& Reachable);
  void ClearSelection();
  /** One-shot illegal-destination feedback (red tile) with a reason. */
  void ShowIllegalCell(int32 X, int32 Y);
  void HideIllegalCell();

  FVector CellToWorld(int32 X, int32 Y) const { return BoardModel.CellToWorld(X, Y); }
  bool WorldToCell(const FVector& World, int32& OutX, int32& OutY) const {
    return BoardModel.WorldToCell(World, OutX, OutY);
  }

  // GD-030 readability: visible tiles are shrunk on XY so adjacent 100-uu
  // cells stay separated by a dark groove instead of merging into a solid
  // slab. Cell centers, the INT-019 100-uu hit-test math and the server
  // board state are untouched: a full-cell dark underlay sits under the
  // tiles and catches visibility traces that land inside a groove.
  static constexpr float TileVisualScaleXY = 0.85f;    // 15 uu groove
  static constexpr float BlockerVisualScaleXY = 0.87f; // 13 uu groove
  static float GrooveUU() {
    return FS08BoardModel::CellSizeUU * (1.0f - TileVisualScaleXY);
  }

protected:
  virtual void BeginPlay() override;
  virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
  void ClearChildren();

  UPROPERTY()
  TObjectPtr<UInstancedStaticMeshComponent> NormalTiles;

  UPROPERTY()
  TObjectPtr<UInstancedStaticMeshComponent> BlockerTiles; // wall/obstacle/closed door

  // One full-board dark slab below the tiles: renders the grooves, hides
  // the old static S01 map underneath and keeps groove clicks on the board.
  UPROPERTY()
  TObjectPtr<UInstancedStaticMeshComponent> UnderlayTiles;

  UPROPERTY()
  TObjectPtr<AActor> IllegalCell;

  UPROPERTY()
  TArray<TObjectPtr<AS08FighterActor>> FighterActors;

  FS08BoardModel BoardModel;
  TArray<FS08BoardFighter> Fighters;
  FString SelectedFighterId;
  TSet<uint64> ReachableCells;
  TArray<TObjectPtr<AActor>> HighlightTiles;
};

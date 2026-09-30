// GD-030 (TASK-020/021/022): grey board built ONLY from the decoded
// FS08Snapshot.BoardState + Fighters (never a fabricated arrangement).
// Tiles are instanced cubes (100x100 uu per INT-019); fighters are grey
// mannequins with a team-colored base (own=blue, enemy=red) and a numbered
// text label (same-name sidekicks stay distinguishable, e.g. Harpies 1/2/3).
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "S08BoardModel.h"
#include "S08BoardArt.h"
#include "S08ArtHud.h"
#include "S08HeroesV2.h"
#include "S08Render.h"
#include "S08Team.h"
#include "S08BoardActor.generated.h"

class UInstancedStaticMeshComponent;
class UStaticMeshComponent;
class UStaticMesh;
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

  /** Board row id of the current room (FS08RoomState::BoardId). Selects the
   *  -ArtPreview board profile before the boardState signature (T3.2); a
   *  change forces the next Rebuild to re-select. */
  void SetRoomBoardId(const FString& BoardId) { RoomBoardId = BoardId; }
  /** Active -ArtPreview board profile id (empty = grey board). */
  const FString& GetArtProfileId() const { return ActiveProfile.Id; }
  /** W4-A: light units / SkyLight / exposure / profile sha actually applied
   *  (input of the RENDER fingerprint line of every SHOT). */
  const FS08AppliedRender& GetAppliedRender() const { return AppliedRender; }
  /** Wave 5c-B -ArtPreviewDiorama tray component (nullptr without the flag). */
  const UStaticMeshComponent* GetDioramaTray() const { return DioramaTray; }
  /** Wave 5c-B: creates the diorama tray component when S08Diorama::Enabled(bArtPreview) (called from BeginPlay;
   *  a no-op without -ArtPreview -ArtPreviewDiorama). Returns true when the tray component exists. */
  bool EnsureDioramaTray(bool bArtPreview);
  /** Wave 5c-B: shows the tray fitted to a board frame of world half extent BoardHalf (S08Diorama::FitTray), or
   *  hides it; writes the 'ARTPREVIEW diorama tray=' line. Public for the automation test. */
  void PlaceDioramaTray(bool bVisible, const FVector2D& BoardHalf, const TCHAR* Surface);

  /** Syncs fighter actors with the latest decoded fighters (spawn/move/
   *  re-label by stable fighter id; dead fighters hide instantly). */
  void SyncFighters(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                    const FString& OwnOwnerId);
  /** W5b-R D-2: the owner id of team P1 (room seat 0 / host; empty = fighter id prefix) and the colour mode of the
   *  art team rings; call before SyncFighters. */
  void SetTeamMapping(const FString& P1OwnerId, ES08TeamColorMode Mode) {
    TeamP1OwnerId = P1OwnerId;
    TeamColorMode = Mode;
  }
  ES08TeamColorMode GetTeamColorMode() const { return TeamColorMode; }
  /** Absolute team (P1/P2) and the drawn look of a fighter (-S08TeamColorMode). */
  ES08TeamSlot TeamOfFighter(const FS08BoardFighter& Fighter) const;
  /** W5b-R D-1: the screen tag layer replaces the world TextRender labels and the
   *  world damage-number text (the damage actor stays: lifetime, dedupe, trace). */
  void SetScreenLabelMode(bool bScreen);
  bool IsScreenLabelMode() const { return bScreenLabelMode; }
  /** Seq of the live damage number of a fighter (-1 when none). */
  int32 GetDamageNumberSeq(const FString& FighterId) const;
  int32 GetDamageNumberAmount(const FString& FighterId) const;

  const FS08BoardModel& GetBoard() const { return BoardModel; }
  bool IsArtActive() const { return bArtActive; }
  const TArray<FS08BoardFighter>& GetFighters() const { return Fighters; }
  AS08FighterActor* FindFighterActor(const FString& FighterId) const;
  void SetFighterLabelZoomRatio(float DistanceRatio, bool bOnlySelected);
  /** ART-004 T2.2: the plate owner hides its world labels, every other
   *  fighter shows one compact line; empty id = the classic full labels. */
  void SetLabelPresentation(const FString& PlateFighterId);
  /** ART-004 T2.2: the exact-size HUD icon replaces the world billboard. */
  void SetScreenIconMode(bool bScreen);
  const FString& GetCombatTargetId() const { return CombatTargetId; }
  /** World box of a live damage number (false when none is showing). */
  bool GetDamageNumberWorldBox(const FString& FighterId, FBox& OutBox) const;
  /** Fighter ids with a damage number currently alive. */
  TArray<FString> GetActiveDamageNumberIds() const;
  /** Apply local attack-draft or authoritative combat focus by fighter ID. */
  void SetCombatFocus(const FString& AttackerId, const FString& TargetId);
  /** CUE-011 fallback: one 900ms damage number at the affected cell,
   *  exactly once per (fighter, authoritative seq) - a repeated cue for the
   *  same seq (reapply, reconnect replay) is traced and ignored (T2.2). */
  void ShowDamageNumber(const FString& FighterId, int32 Damage, int32 SequenceNumber);
  /** Wave 5c-B -ArtPreviewHeroesV2: a combat event (attack / damage) of a fighter drives its v2 clip,
   *  exactly once per (event, fighter, authoritative seq). A no-op without the flag or a v2 figure. */
  void NotifyFighterAnimEvent(const FString& FighterId, S08HeroesV2::EEvent Event, int32 SequenceNumber);

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

  // ART-005 / T3.2 -ArtPreview board art, selected per board from the data in
  // Config/ArtBoards/S08ArtBoardProfiles.json (S08BoardArt.h). Surface
  // 'cobble-5x6-mesh' keeps the ART-005 Cobble slab; 'tiles' dresses the
  // parametric tiles of any W x H board. The instanced tiles always stay the
  // exact click surfaces.
  UPROPERTY()
  TObjectPtr<UStaticMeshComponent> ArtBoard;
  UPROPERTY()
  TObjectPtr<UInstancedStaticMeshComponent> ArtCorners;
  // 'tiles' surface: one lit stone slab per passable cell + four wood frame
  // bars as plain static mesh components. The ART-005 probe materials carry
  // no InstancedStaticMeshes usage, and a cooked build renders them as the
  // default material on an ISM (seen in the first T3.2 packaged smoke).
  UPROPERTY()
  TArray<TObjectPtr<UStaticMeshComponent>> ArtSurfaceParts;
  // One stroke ISM per zone KEY (created on demand; palette from the data).
  UPROPERTY()
  TMap<FString, TObjectPtr<UInstancedStaticMeshComponent>> ArtZoneStrokes;
  UPROPERTY()
  TObjectPtr<UInstancedStaticMeshComponent> ArtZoneGlyphs;
  // T4.2: one glyph-mesh ISM per zone KEY (SM_ART005_ZoneGlyph_<Glyph>, one instance per zone slot).
  UPROPERTY()
  TMap<FString, TObjectPtr<UInstancedStaticMeshComponent>> ArtZoneGlyphMeshes;
  bool bArtAssetsReady = false;   // shared art assets + Medusa candidate + board data
  bool bCobbleMeshReady = false;  // ART-005 Cobble slab and its two material slots
  bool bTileArtReady = false;     // stone/wood probe materials + dark void tint for 'tiles'
  bool bArtActive = false;
  bool bArtTiles = false;
  UPROPERTY()
  TArray<TObjectPtr<AActor>> ArtLights;  // key, points, W4-A SkyLight and exposure volume
  FString ActiveLightProfileId;
  FS08AppliedRender AppliedRender;

  UPROPERTY()
  TObjectPtr<UMaterialInterface> GreyTileMaterial;
  UPROPERTY()
  TObjectPtr<UMaterialInstanceDynamic> GreyBlockerMaterial;
  UPROPERTY()
  TObjectPtr<UMaterialInstanceDynamic> GreyUnderlayMaterial;
  UPROPERTY()
  TObjectPtr<UMaterialInstanceDynamic> ArtVoidMaterial;  // 'tiles': grooves + non-space voids
  UPROPERTY()
  TObjectPtr<UMaterialInterface> ArtStoneTileMaterial;
  UPROPERTY()
  TObjectPtr<UMaterialInterface> ArtWoodMaterial;
  UPROPERTY()
  TObjectPtr<UMaterialInterface> ArtSolidMaterial;  // unlit 'Tint' base for zone colours
  UPROPERTY()
  TMap<FString, TObjectPtr<UMaterialInterface>> ArtZoneMaterials;
  UPROPERTY()
  TMap<FString, TObjectPtr<UMaterialInstanceDynamic>> ArtZoneTints;
  // T4.2 content: zone MI per key ("" = fallback style) and glyph mesh per glyph name, loaded from the data paths.
  UPROPERTY()
  TMap<FString, TObjectPtr<UMaterialInterface>> ArtZoneInstances;
  UPROPERTY()
  TMap<FString, TObjectPtr<UStaticMesh>> ArtGlyphMeshes;
  // W5b-R D-4 keylines: one ISM for the stroke keylines (+ cube-piece glyph keylines of glyphs without a keyline
  // mesh), one ISM per glyph keyline mesh, all with the keyline MI (or a tint MID of the keyline colour).
  UPROPERTY()
  TObjectPtr<UInstancedStaticMeshComponent> ArtZoneKeylines;
  UPROPERTY()
  TMap<FString, TObjectPtr<UInstancedStaticMeshComponent>> ArtZoneGlyphKeylines;
  UPROPERTY()
  TMap<FString, TObjectPtr<UStaticMesh>> ArtGlyphKeylineMeshes;
  UPROPERTY()
  TObjectPtr<UMaterialInterface> ArtKeylineMaterial;
  FString ArtKeylineMaterialName;

  FS08BoardArtData ArtData;
  bool bArtDataLoaded = false;
  FS08BoardArtProfile ActiveProfile;
  FString RoomBoardId;
  FString BuiltForBoardId;

  UInstancedStaticMeshComponent* ZoneStrokeComponent(const FS08ZoneStyle& Style);
  /** Authored material when it supports instancing (or on the legacy Cobble
   *  profile, kept exact), else an unlit tint of the data colour. */
  UMaterialInterface* ZoneMaterialFor(const FS08ZoneStyle& Style, bool& bOutAuthored, bool& bOutIsmUsage);
  /** T4.2: the zone MI of a style (fallback style under ""), nullptr = not in the data or not loaded. */
  UMaterialInterface* ZoneInstanceFor(const FS08ZoneStyle& Style) const;
  /** T4.2: glyph-mesh ISM of a zone key, nullptr when its glyph has no loaded mesh (cube pieces then). */
  UInstancedStaticMeshComponent* ZoneGlyphMeshComponent(const FS08ZoneStyle& Style);
  void ClearArtSurface();
  void AddArtSurfacePart(UMaterialInterface* Material, const FTransform& Transform);
  void ClearArtLights();
  void ApplyArtLights(const FS08LightProfile& Light, bool bLegacyCobbleTrace);
  void ApplySurfaceMaterials();
  /** Wave 5c-B -ArtPreviewDiorama: shows / hides and fits the tray under the active art board (traced). */
  void UpdateDioramaTray(const FS08BoardModel& Board);

  UPROPERTY()
  TObjectPtr<AActor> IllegalCell;

  UPROPERTY()
  TArray<TObjectPtr<AS08FighterActor>> FighterActors;
  TMap<FString, TWeakObjectPtr<AActor>> DamageNumbers;
  TMap<FString, FIntPoint> DamageNumberInfo;  // fighter id -> (amount, seq) of the live number
  FString TeamP1OwnerId;
  ES08TeamColorMode TeamColorMode = ES08TeamColorMode::Absolute;
  bool bScreenLabelMode = false;
  FS08SeqDedupe DamageDedupe;
  FString LabelPlateFighterId;
  bool bScreenIconMode = false;
  bool bAllMedusaSummaryTraced = false;
  FS08SeqDedupe AnimEventDedupe;
  FString HeroesV2SummaryKey;
  // Wave 5c-B -ArtPreviewDiorama (S08Diorama.h): created at runtime only with the flag, nullptr otherwise.
  UPROPERTY()
  TObjectPtr<UStaticMeshComponent> DioramaTray;

  FS08BoardModel BoardModel;
  TArray<FS08BoardFighter> Fighters;
  FString SelectedFighterId;
  FString CombatAttackerId;
  FString CombatTargetId;
  TSet<uint64> ReachableCells;
  TArray<TObjectPtr<AActor>> HighlightTiles;
};

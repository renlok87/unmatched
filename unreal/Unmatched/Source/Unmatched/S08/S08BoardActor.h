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
#include "S08ConceptPaste.h"
#include "S08EnvLayout.h"
#include "S08MapBackdrop.h"
#include "S08ArtHud.h"
#include "S08HeroesV2.h"
#include "S08MoveHighlight.h"
#include "S08MoveAnim.h"
#include "S08Render.h"
#include "S08Team.h"
#include "S08BoardActor.generated.h"

class UInstancedStaticMeshComponent;
class UStaticMeshComponent;
class UStaticMesh;
class UTextRenderComponent;
class UBoxComponent;
class UPointLightComponent;
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
  /** VS-4 V3 (FX-38): the zone icon disc colour of a zone key from the active profile (false: no art profile / no entry). */
  bool GetZoneIconSrgb(FName Key, FColor& Out) const {
    const FColor* C = bArtActive ? ActiveProfile.ZoneIconSrgb.Find(Key) : nullptr;
    if (C) Out = *C;
    return C != nullptr;
  }
  /** W4-A: light units / SkyLight / exposure / profile sha actually applied
   *  (input of the RENDER fingerprint line of every SHOT). */
  const FS08AppliedRender& GetAppliedRender() const { return AppliedRender; }
  /** Wave 5c-B diorama tray component (default since ART-DEFAULT; nullptr with -S08DioramaLegacy / -S08GreyBoard). */
  const UStaticMeshComponent* GetDioramaTray() const { return DioramaTray; }
  /** Wave 5c-B: creates the diorama tray component when S08Diorama::Enabled(bArtLook) (called from BeginPlay on the
   *  art look; a no-op with -S08DioramaLegacy). Returns true when the tray component exists. */
  bool EnsureDioramaTray(bool bArtLook);
  /** Wave 5c-B: shows the tray fitted to a board frame of world half extent BoardHalf (S08Diorama::FitTray), or
   *  hides it; writes the 'ARTPREVIEW diorama tray=' line. Public for the automation test.
   *  ENV-MAPS (ENV-O8 T1): Offset shifts the tray (extra rim on one side), Waiver names the exception the
   *  placeholder stretch runs under ('T1-placeholder' on the map-image surface; nullptr = the old line). */
  void PlaceDioramaTray(bool bVisible, const FVector2D& BoardHalf, const TCHAR* Surface,
                        const FVector2D& Offset = FVector2D::ZeroVector, const TCHAR* Waiver = nullptr);
  /** ENV-U10 track TRAY: shows the shared rocky tray T2 (S08Diorama::T2MeshPath, loaded on first use) at
   *  (0, OffsetY, 0), yaw 0, scale 1 (S08Diorama::FitTrayT2) for a layout tray of outer half LayoutHalf around a board
   *  frame of half FrameHalf; Source names where the tray came from (layout | apron | default). Writes the
   *  'ARTPREVIEW diorama tray=... kind=T2 ...' line (no waiver). False (nothing changed) when T2 is not in the build -
   *  the caller then keeps the T1 placeholder. Public for the automation test. */
  bool PlaceDioramaTrayT2(const FVector2D& FrameHalf, const FVector2D& LayoutHalf, float OffsetY, const TCHAR* Source);
  /** ENV-MAPS track C (S08EnvLayout.h): arms the environment around map-image boards when
   *  S08EnvLayout::Enabled(bArtLook) (the art look with the tray - both default -, no -ArtPreviewNoEnv); creates
   *  nothing by itself (called from BeginPlay; a grid board never gets a component). Returns the gate. */
  bool EnsureEnvLayout(bool bArtLook);
  /** Environment components spawned from Config/ArtBoards/EnvLayouts/<map>.layout.json for the active map-image
   *  board (empty on grids, without the flags, or when the layout is absent / invalid). */
  const TArray<TObjectPtr<UStaticMeshComponent>>& GetEnvProps() const { return EnvProps; }
  const TArray<TObjectPtr<UPointLightComponent>>& GetEnvLights() const { return EnvLights; }
  const FS08EnvLayoutRuntime& GetEnvLayoutRuntime() const { return EnvRuntime; }

  // ---- ENV-MAPS track S (topology boards, 'map-image' surface) ----
  /** True when the last Rebuild got a topology board (FS08BoardModel::bHasTopology). */
  bool IsTopologyBoard() const { return bTopologyBoard; }
  /** True when the active art profile draws the original map illustration. */
  bool IsMapImageActive() const { return bMapImageActive; }
  /** Half extent the K1 camera / lights / tray fit: the active map-image profile's map, else the board's
   *  S08BoardHalfExtentUU (map canvas of a topology board, W x H x 50 of a grid). */
  FVector2D GetBoardHalfExtentUU() const;
  /** ENV-U9: "k1DistanceMul" of the active art profile (1.25 on the two map-image boards), 1 without one (no art,
   *  no match, a refused map-image profile -> the grey topology view keeps the plain fit). */
  float GetK1DistanceMul() const { return bArtActive ? ActiveProfile.K1DistanceMul : 1.0f; }
  /** Map plane (map-image surface, or the dark canvas of the grey topology view); nullptr until a topology board. */
  const UStaticMeshComponent* GetMapPlane() const { return MapPlane; }
  /** Invisible QueryOnly (Visibility) cursor-trace box over the map of a topology board (nullptr on grids). */
  const UBoxComponent* GetMapPickBox() const { return MapPickBox; }
  /** Grey topology view: one disc per space / one bar per link (nullptr until needed). */
  const UInstancedStaticMeshComponent* GetTopologyDiscs() const { return TopologyDiscs; }
  const UInstancedStaticMeshComponent* GetTopologyLinkBars() const { return TopologyLinkBars; }
  /** Instance counts of the lattice ISMs (normal + blocker + underlay): 0 on a topology board. */
  int32 GetLatticeInstanceCount() const;
  /** Art surface parts (wood frame bars / 'tiles' slabs) of the last Rebuild. */
  int32 GetArtSurfacePartCount() const { return ArtSurfaceParts.Num(); }
  int32 GetArtCornerCount() const;
  /** Asset paths the last map-image activation could not load (the fallback reason; empty when none). */
  const TArray<FString>& GetMapImageMissing() const { return MapImageMissing; }
  /** Loads the map material instance + BC / mask of a map-image spec (the SDF / ID packages are only checked
   *  for existence, and only in uncooked runs: they are never cooked); every missing path is traced 'ARTPREVIEW map-image missing <path>'. False when a required
   *  asset (MI, BC, mask) is missing. On success MapPlaneMaterial is a MID of the MI with BaseColor / GameMask
   *  bound to the spec's textures. */
  bool LoadMapImageAssets(const FS08MapImageSpec& Spec);
  /** Automation only: board profile data without BeginPlay / -ArtPreview (art assets treated as ready; the
   *  map-image path loads its own assets and falls back when they are missing). */
  void SetArtDataForTest(const FS08BoardArtData& Data);
  /** Automation only: a 'tiles' profile activates without its probe materials (a test world runs no BeginPlay asset
   *  load), so its lights / fog / hero light spawn as in a real build. */
  void SetTileArtReadyForTest() { bTileArtReady = true; }
  /** ENV-MAPS P4: the "readability" block of the ACTIVE map-image profile (nullptr on grids, without art, on a
   *  refused map-image profile, or when the profile has no block). */
  const FS08BoardReadabilitySpec* GetActiveReadability() const {
    return bArtActive && bMapImageActive && ActiveProfile.Readability.bSet ? &ActiveProfile.Readability : nullptr;
  }
  /** ENV-MAPS P4: screen tags on the readability plate (dark rounded plate + team outline + hard padding). */
  bool UsesLabelPlates() const {
    const FS08BoardReadabilitySpec* R = GetActiveReadability();
    return R && R->bLabelPlates;
  }
  /** Source of the last map frame material: "frame-wood" (M_MapFrameWood MID), "probe" (the ART-005 wood) or
   *  "missing" (frameWood asked for, M_MapFrameWood not imported -> the probe wood). Empty before a map-image board. */
  const FString& GetMapFrameWoodSource() const { return MapFrameWoodSource; }
  /** ENV-MAPS P5 track C (gap 9 full): the frame of the last map-image board - "frame-002" (the 20 modules of
   *  ASSET-MAP-FRAME-002 replaced the cube bars and the ART-005 corners), "bars" (no "mapFrame" block) or "missing" (the
   *  block asks for the kit, a module mesh is not imported -> bars + corners). Empty before a map-image board. */
  const FString& GetMapFrameKitSource() const { return MapFrameKitSource; }
  /** The frame module components of the active map-image board (empty on grids and with the bars). */
  const TArray<TObjectPtr<UStaticMeshComponent>>& GetMapFrameParts() const { return MapFrameParts; }
  /** ENV-MAPS P5 track C (gap 8): the night backdrop parts (mist planes, moon card) of the active map-image board and what
   *  S08MapBackdrop::Update applied (empty / 'off' on grids, the grey view, a refused profile, without the env gate). */
  const TArray<TObjectPtr<UStaticMeshComponent>>& GetBackdropParts() const { return BackdropParts; }
  const FS08BackdropRuntime& GetBackdropRuntime() const { return BackdropRuntime; }
  /** ENV-MAPS P7 (ENV-U15): the concept paste of the active map-image board (S08ConceptPaste.h) - the decision of the
   *  last board (mode, reason), the parts (sheet, sea plane, sky segments, blobs), its point lights, and what it hid. */
  const FS08ConceptPasteRuntime& GetConceptPasteRuntime() const { return ConceptRuntime; }
  const FS08ConceptPasteMode& GetConceptPasteMode() const { return ConceptMode; }
  const TArray<TObjectPtr<UStaticMeshComponent>>& GetConceptPasteParts() const { return ConceptParts; }
  const TArray<TObjectPtr<UPointLightComponent>>& GetConceptPasteLights() const { return ConceptLights; }
  const US08ConceptPasteAnimComponent* GetConceptPasteAnim() const { return ConceptAnim; }
  /** True while the paste is on and its parts exist (the painted surround replaces tray / ground / props). */
  bool IsConceptPasteOn() const { return ConceptMode.bOn && ConceptRuntime.Status == TEXT("ok"); }

  // ---- ENV-MAPS P9 hero light (S08HeroLight.h, docs/art-pipeline/ENV-HERO-LIGHT.md) ----
  /** The "heroLight" block that lights the figures now: the active art profile's light profile block when enabled (grid and
   *  map-image boards alike), nullptr without art, without the block, disabled, or under -NoHeroLight. */
  const FS08HeroLightSpec* GetActiveHeroLight() const;
  /** Hero lights on the board after the last update (sum over the fighters) and the layers per figure. */
  int32 GetHeroLightCount() const { return HeroLightCount; }
  int32 GetHeroLightLayers() const { return HeroLightLayersPerFigure; }
  /** Automation only: a spec used instead of the art profile's (also on a grey board), and the -NoHeroLight decision
   *  (unset = the command line). Call UpdateHeroLights (or SyncFighters) after. */
  void SetHeroLightOverrideForTest(const FS08HeroLightSpec* Spec) {
    bHeroLightOverride = Spec != nullptr;
    HeroLightOverride = Spec ? *Spec : FS08HeroLightSpec();
  }
  void SetHeroLightOptOutForTest(TOptional<bool> bOptOut) {
    HeroLightOptOutOverride = bOptOut;
    HeroLightOptOutReason = TEXT("test-opt-out");
  }
  /** Art Tuner M1 (-ArtView key H): the hero light off for the view only (the profile is untouched); false = back to the
   *  command line decision (-NoHeroLight). Call UpdateHeroLights after. */
  void SetHeroLightViewOff(bool bOff) {
    HeroLightOptOutOverride = bOff ? TOptional<bool>(true) : TOptional<bool>();
    HeroLightOptOutReason = TEXT("art-view");
  }
  /** Applies the active block to every fighter actor within the board budget (S08HeroLight::LayersForBoard); traced. */
  void UpdateHeroLights();

  // ---- ENV-MAPS live tune (S08LiveTune.h, tools/art/render/LIVE-TUNE.md); unused without -ArtLiveTune ----
  /** Loads and validates the board profiles at ProfilesPath (bOverride: not the default path -> profilesSource=override in
   *  the RENDER fingerprint) and every env layout / overlay of EnvDir (empty = S08EnvLayout::ResolveDir) WITHOUT touching
   *  the board: an invalid document returns false with the errors and the board keeps its state. A valid one is swapped
   *  in (traced like BeginPlay), the art runtime goes back to its post-BeginPlay state (lights / fog / exposure, env
   *  layout, concept paste, backdrop) and the next Rebuild is a full one - the caller rebuilds through the normal path
   *  (the game mode's SyncBoardFromApplied: Rebuild + SyncFighters). OutWarnings: changed sections only BeginPlay reads
   *  (zone styles, glyph meshes, zone keyline) - they need a relaunch. */
  bool ReloadArtData(const FString& ProfilesPath, bool bOverride, const FString& EnvDir, TArray<FString>& OutErrors,
                     TArray<FString>& OutWarnings);
  /** Tears the art runtime down like ReloadArtData (same data) and makes the next Rebuild a full one. */
  void RequestFullRebuild();
  // ---- Art Tuner (S08ArtTuner.h, S08BoardActorTuner.cpp); unused without -ArtTuner ----
  /** Swaps in a tuned document (FS08ArtTunerModel::Build: the applied one + the panel's values) and pushes the changed
   *  scopes (ES08TunerScope bits) onto the existing components: hero rigs, the light profile's actors, the map grade MID,
   *  the lit3d lights and their flicker base. A Rebuild scope - or a change the components cannot take (another light
   *  count, a flicker that needs the anim component) - tears the art runtime down like RequestFullRebuild instead: then
   *  it returns true and the caller rebuilds through the normal path (SyncBoardFromApplied). ProfilesSource goes into the
   *  RENDER fingerprint ("tuner" while values differ from the file). */
  bool ApplyTunedArtData(const FS08BoardArtData& Data, uint8 Scopes, const FString& ProfilesSource, FString& OutNote);
  /** Full Rebuilds since spawn (a Rebuild with unchanged geometry keeps the tiles and is not counted). */
  int32 GetBuildCount() const { return BuildCount; }
  const FS08BoardArtData& GetArtData() const { return ArtData; }
  /** Art Tuner M4: env-prop MIDs the lit3d material overrides wrote (0 without the block). */
  int32 GetTunedMaterialCount() const { return TunedMaterialMids.Num(); }
  /** Spawned art light actors of the light profile (key, points, SkyLight, fog, exposure volume). */
  int32 GetArtLightActorCount() const { return ArtLights.Num(); }
  /** Live tune: the fx mode of this board (unset = the command line: -Bench freezes unless -EnvFxLive); applies on the
   *  next full Rebuild. */
  void SetFxOptionsOverride(const TOptional<FS08EnvFxOptions>& Options) { FxOptionsOverride = Options; }
  FS08EnvFxOptions GetFxOptions() const;

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
  void ShowDamageNumber(const FString& FighterId, int32 Damage, int32 SequenceNumber, float LifeSeconds = 0.9f);
  /** DE-018 (01 F-03): contact frame (ms at speed x1) of the fighter's LungeAttack - the "Contact" AnimNotify of the
   *  clip (DE-010), else the build-profile frame; -1 without a v2 figure. OutSource = notify | profile. */
  int32 GetFighterContactMs(const FString& FighterId, FString& OutSource) const;
  /** DE-018 (CUE-011): the red hit tint of a v2 figure (CPD_HitTint) for Seconds from now. */
  void PlayFighterHitTint(const FString& FighterId, float Seconds);
  /** MS-T-16 (CUE-007): starts the moves of one seq at NowMs (the snapshot frame) - one plan per fighter
   *  (FS08MoveAnim::BuildPlans); returns the number of figures that animate (a snapped plan lands at once). */
  int32 PlayFighterMoves(const TArray<FS08MovePlan>& Plans, const FS08MoveAnimParams& Params, int64 NowMs);
  /** Advances every playing move to NowMs (the game mode's tick). */
  void TickFighterMoves(int64 NowMs);
  /** Jumps every playing move to its final pose (skip input, MS-E-70); returns how many were playing. */
  int32 SkipFighterMoves();
  /** Some figure is still travelling or settling. */
  bool AnyFighterMoving() const;
  // ---- AN-23 (ВР-06): the rest facing of the figures (S08Facing.h) ----
  /** The v1 rest facing (world yaw) of Me standing at WorldPos: three-quarter to the view camera with the offset to
   *  the nearest living enemy of Me from there, no dead band (a plan end, a return); the camera axis without an
   *  enemy; the half-field rule with -S08FacingLegacy. PlayFighterMoves sets the plan ends with it. */
  double RestYawFor(const AS08FighterActor* Me, const FVector& WorldPos) const;
  /** (Re)applies the rest facing of one figure: the camera and the nearest living enemy of its owner; Src labels the
   *  FACING trace (snapshot / move - the actor itself upgrades its first apply to spawn). */
  void ApplyFighterRestFacing(AS08FighterActor* Actor, const TCHAR* Src);
  /** ВР-Z1R-04: the one camera helper of the figures (facing, the base digit) - the player's view target (the flow game
   *  mode's BoardCamera camera component), else the camera manager, else the +Y board side (no player: automation). */
  static FVector ViewCameraLocation(const UWorld* World);
  /** ViewCameraLocation of this board's world (the K1 camera of a -Bench run at spawn). */
  FVector LocalCameraLocation() const;
  /** The nearest living enemy (another owner, not dying) of Me by XY distance, or nullptr. */
  AS08FighterActor* NearestEnemyOf(const AS08FighterActor* Me) const;
  /** The nearest living enemy of Me measured from WorldPos (Me's destination), or nullptr. */
  AS08FighterActor* NearestEnemyFrom(const AS08FighterActor* Me, const FVector& WorldPos) const;
  /** AN-25 (ВР-06): the return to the rest angle after a LungeAttack (Src attack-return) / HitReact (hit-return)
   *  ended - RestYawFor on the current positions (a dead target switches to the nearest living enemy), the dead band
   *  never holds it; traced with the game clock. */
  void FighterReturnToRest(const FString& FighterId, const TCHAR* Src);
  /** F4: the game (CUE) clock of the FACING traces - the flow game mode's NowMs; the world time without one. */
  void SetGameClock(TFunction<int64()> Clock) { GameClock = MoveTemp(Clock); }
  int64 GameNowMs() const;
  /** AN-32 (ВР-16): pushes the active light profile's "heroMaterials" Fix to every living v2 figure (their body
   *  slots wrap in MIDs); the Art Tuner scope "heroMaterials" (no rebuild, live tune). Traces one board line. */
  void UpdateHeroMaterials();
  /** DE-019 (01 F-09): the death plan of a dying v2 figure (AS08FighterActor::GetDeathPlan); false when the fighter
   *  plays no death (alive, gone, or a figure that hides at once). */
  bool GetFighterDeathPlan(const FString& FighterId, S08HeroesV2::FDeathPlan& OutPlan, FString& OutStyle) const;
  /** Short asset name of a v2 figure's clip (AM_<Key>_<Clip>), empty without one (CUE trace token). */
  FString GetFighterClipName(const FString& FighterId, S08HeroesV2::EClip Clip) const;
  /** Wave 5c-B heroes v2 (default since ART-DEFAULT): a combat event (attack / damage) of a fighter drives its v2
   *  clip, exactly once per (event, fighter, authoritative seq). A no-op with -S08HeroesLegacy or without a v2 figure. */
  void NotifyFighterAnimEvent(const FString& FighterId, S08HeroesV2::EEvent Event, int32 SequenceNumber,
                              float PlayRate = 1.0f);

  /** TASK-022 selection ring + reachable-cell highlights. MS-T-08: with the move plates (-S08MovePlates) the
   *  highlights are the plates of US08MoveHighlightComponent - the view comes from the provider (the game mode's draft,
   *  SetMoveDraftViewProvider), else from Reachable (S08MoveHighlight::ViewFromReachable); no actor is spawned. */
  void SetSelectedFighter(const FString& FighterId, const TSet<uint64>& Reachable);
  void ClearSelection();
  /** VS-2 HB-12: the cell is lit by the current selection (reachable / move plates) - the pointer cursor over it. */
  bool IsCellHighlighted(const FIntPoint& Cell) const { return ReachableCells.Contains(FS08BoardModel::CellKey(Cell.X, Cell.Y)); }
  // ---- MS-T-08 move plates (S08MoveHighlight.h) ----
  /** True when the plates draw the highlights: -S08MovePlates, M_UM_MovePlate loaded and a board built. */
  bool UsesMovePlates() const;
  /** Draws View on the plates (no-op without them). */
  void SetMoveDraftView(const FS08MoveDraftView& View);
  /** The game mode's view of the current selection (false = the plain reachable set). */
  using FMoveDraftViewProvider = TFunction<bool(const FString& /*FighterId*/, const TSet<uint64>& /*Reachable*/,
                                                FS08MoveDraftView& /*OutView*/)>;
  void SetMoveDraftViewProvider(FMoveDraftViewProvider Provider) { MoveDraftViewProvider = MoveTemp(Provider); }
  /** Rebuilds the view of the current selection (a draft operation without a selection change). */
  void RefreshMoveDraftView();
  /** MS-T-17: the MS-P-03 fade of the last-move outlines V-14 / V-15 (no-op without the plates). */
  void SetLastMoveFade(float Fade) {
    if (MoveHighlight) MoveHighlight->SetLastMoveFade(Fade);
  }
  /** The move-selection style of the active board: the art profile's (root + board override), else the document root,
   *  else the code defaults. */
  FS08MoveSelectionSpec ActiveMoveSelection() const;
  /** The readability leader pips are drawn on this board (the plates cut around them). */
  bool DrawsLeaderPips() const {
    const FS08BoardReadabilitySpec* R = GetActiveReadability();
    return R && R->bLeaderPip;
  }
  const US08MoveHighlightComponent* GetMoveHighlight() const { return MoveHighlight; }
  /** Spawned highlight actors of the old path (0 with the plates, MS-R-49). */
  int32 GetHighlightActorCount() const { return HighlightTiles.Num(); }
  /** Automation: the move plates on a test world (material checked like a game; SetReadyForTest when absent). */
  US08MoveHighlightComponent* EnsureMoveHighlightForTest();
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
  // 'map-image' draws an original map (topology boards); 'tiles' dresses the
  // parametric tiles of any W x H board. The instanced tiles always stay the
  // exact click surfaces of a grid.
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
  // ---- live tune (S08LiveTune.h) ----
  int32 BuildCount = 0;
  bool bForceRebuild = false;          // ReloadArtData / RequestFullRebuild: the next Rebuild ignores the same geometry
  FString EnvDirOverride;              // a reload's "envDir" (empty = S08EnvLayout::ResolveDir)
  TOptional<FS08EnvFxOptions> FxOptionsOverride;
  FString BootSectionsSignature;       // zone styles / glyph meshes / keyline of the BeginPlay document (-ArtLiveTune only)
  void ResetArtRuntimeForReload();
  /** The two 'ARTPREVIEW board profiles' lines of BeginPlay (also written by a reload). */
  void TraceProfilesLoaded(bool bLoaded, bool bOverride, const FString& Path, const TArray<FString>& Errors);
  FS08BoardArtProfile ActiveProfile;
  FString RoomBoardId;
  FString BuiltForBoardId;

  UInstancedStaticMeshComponent* ZoneStrokeComponent(const FS08ZoneStyle& Style);
  /** Authored material when it supports instancing (-S08LegacyRender only), else the zone MI or an unlit tint of
   *  the data colour. */
  UMaterialInterface* ZoneMaterialFor(const FS08ZoneStyle& Style, bool& bOutAuthored, bool& bOutIsmUsage);
  /** T4.2: the zone MI of a style (fallback style under ""), nullptr = not in the data or not loaded. */
  UMaterialInterface* ZoneInstanceFor(const FS08ZoneStyle& Style) const;
  /** T4.2: glyph-mesh ISM of a zone key, nullptr when its glyph has no loaded mesh (cube pieces then). */
  UInstancedStaticMeshComponent* ZoneGlyphMeshComponent(const FS08ZoneStyle& Style);
  void ClearArtSurface();
  void AddArtSurfacePart(UMaterialInterface* Material, const FTransform& Transform);
  void ClearArtLights();
  void ApplyArtLights(const FS08LightProfile& Light);
  /** Art Tuner: the values of Light on the spawned profile actors (no respawn). */
  void ApplyTunedLights(const FS08LightProfile& Light);
  /** Art Tuner: the lit3d light values on ConceptLights (+ the flicker base); false = needs a rebuild. */
  bool ApplyTunedConceptLights();
  /** Art Tuner M4: the lit3d "materialOverrides" on the env props' MIDs (every MID it touched before goes back to its
   *  parent's values first, so a removed look is undone); always true (no rebuild needed). */
  bool ApplyMaterialOverrides();
  /** MIDs the material overrides wrote (owned by the env prop components). */
  TArray<TWeakObjectPtr<UMaterialInstanceDynamic>> TunedMaterialMids;
  FString MaterialOverridesTraceKey;
  /** ENV-MAPS P2: the profile's "mapGrade" on the map MID of a map-image board (traced; no block = the MI values). */
  void ApplyMapGrade(const FS08LightProfile& Light);
  void ApplySurfaceMaterials();
  /** Wave 5c-B diorama tray (default since ART-DEFAULT): shows / hides and fits the tray under the active art board (traced). */
  void UpdateDioramaTray(const FS08BoardModel& Board);
  /** ENV-MAPS track C: spawns / keeps / clears the environment of the active map-image board (S08EnvLayout::Update);
   *  called first thing in UpdateDioramaTray, whose map-image tray then takes the layout's tray (S08EnvLayout::ApplyTrayT2 -> the shared
   *  T2 at scale 1; S08EnvLayout::ApplyTray only for the T1 placeholder fallback). */
  void UpdateEnvLayout();

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
  // Wave 5c-B diorama tray (S08Diorama.h): created at runtime on the art look (default), nullptr with -S08DioramaLegacy /
  // -S08GreyBoard.
  UPROPERTY()
  TObjectPtr<UStaticMeshComponent> DioramaTray;
  // ENV-U10 track TRAY: the tray component swaps between T1 (SM_TableBase, grid boards and the map-image fallback)
  // and T2 (SM_TableBase_T2, map-image boards, loaded on first use; bTrayT2Tried = the load was attempted).
  UPROPERTY()
  TObjectPtr<UStaticMesh> TrayT1Mesh;
  UPROPERTY()
  TObjectPtr<UMaterialInterface> TrayT1Mi;
  UPROPERTY()
  TObjectPtr<UStaticMesh> TrayT2Mesh;
  UPROPERTY()
  TObjectPtr<UMaterialInterface> TrayT2Mi;
  bool bTrayT2Tried = false;
  // ENV-MAPS track C (S08EnvLayout.h): environment props / point lights of the active map-image board, created at
  // runtime only on the art look with the tray (both default; S08ArtLook.h); destroyed on a board change.
  UPROPERTY()
  TArray<TObjectPtr<UStaticMeshComponent>> EnvProps;
  UPROPERTY()
  TArray<TObjectPtr<UPointLightComponent>> EnvLights;
  FS08EnvLayoutRuntime EnvRuntime;
  bool bEnvLayoutEnabled = false;

  // ENV-MAPS track S: created on demand by the first topology board (a grid board creates none of them).
  UPROPERTY()
  TObjectPtr<UStaticMesh> PlaneMesh;     // /Engine/BasicShapes/Plane (constructor finder)
  UPROPERTY()
  TObjectPtr<UStaticMesh> CylinderMesh;  // /Engine/BasicShapes/Cylinder (discs)
  UPROPERTY()
  TObjectPtr<UStaticMeshComponent> MapPlane;  // map-image plane, or the dark canvas of the grey topology view
  UPROPERTY()
  TObjectPtr<UBoxComponent> MapPickBox;       // invisible QueryOnly / Visibility cursor surface over the map
  UPROPERTY()
  TObjectPtr<UInstancedStaticMeshComponent> TopologyDiscs;     // grey view: one disc per space
  UPROPERTY()
  TObjectPtr<UInstancedStaticMeshComponent> TopologyLinkBars;  // grey view: one bar per link
  UPROPERTY()
  TObjectPtr<UMaterialInstanceDynamic> MapPlaneMaterial;  // MID of MI_<Name>_MapBoard (textures bound)
  TArray<FString> MapImageMissing;
  bool bTopologyBoard = false;
  bool bMapImageActive = false;
  void EnsureTopologyComponents();
  /** Grey topology view (no art, or map assets missing): dark canvas + discs + link bars, pick box. */
  void BuildGreyTopology(const FS08BoardModel& Board);
  /** 'map-image' surface: the map plane, frame, corners and pick box (no lattice, no zone marks). */
  void BuildMapImageSurface(const FS08BoardModel& Board, const FS08BoardSummary& Summary);
  void HideTopologyComponents();

  // ---- ENV-MAPS P4 readability (map-image boards with a profile "readability" block only) ----
  /** The map frame material: a MID of M_MapFrameWood with the profile's frameWood values, else the ART-005 probe
   *  wood (MapFrameWoodSource says which). */
  UMaterialInterface* MapFrameMaterial();
  /** Contact-shadow blob and (heroes) leader pip as components of the fighter actor; no-op without the block. */
  void ApplyFighterReadability(AS08FighterActor* Actor, const FS08BoardFighter& Fighter, ES08TeamSlot Look);
  UPROPERTY()
  TObjectPtr<UMaterialInstanceDynamic> MapFrameWoodMid;
  bool bMapFrameWoodTried = false;
  FString MapFrameWoodSource;
  // ---- ENV-MAPS P5 track C: heavy modular frame (profile "mapFrame") and night backdrop (profile "backdrop") ----
  /** Places the 20 ASSET-MAP-FRAME-002 modules (S08MapFrame002Layout) with Wood on their wood slot; false (nothing
   *  placed, traced) when a module mesh is not imported - the caller then keeps the cube bars + ART-005 corners. */
  bool BuildMapFrame002(UMaterialInterface* Wood);
  void ClearMapFrameParts();
  /** S08MapBackdrop::Update for the active board (env gate AND map-image AND the profile block). */
  void UpdateBackdrop();
  UPROPERTY()
  TArray<TObjectPtr<UStaticMeshComponent>> MapFrameParts;
  UPROPERTY()
  TArray<TObjectPtr<UStaticMesh>> Frame002Meshes;  // Corner, SegA, SegB, SegMid (ES08FrameModule order)
  UPROPERTY()
  TObjectPtr<UMaterialInterface> Frame002Iron;
  bool bFrame002Tried = false;
  FString MapFrameKitSource;
  UPROPERTY()
  TArray<TObjectPtr<UStaticMeshComponent>> BackdropParts;
  FS08BackdropRuntime BackdropRuntime;
  // ---- ENV-MAPS P7 (ENV-U15): concept paste (profile "conceptPaste", S08ConceptPaste.h) ----
  /** Decides the mode for the active board (gate, command line, block default) and loads its assets; a missing required
   *  asset falls back to off (P5c look). Called by UpdateEnvLayout before the layout (the mode picks the overlay). */
  void ResolveConceptPasteMode();
  /** The env-layout request of the active board with the current concept mode (UpdateEnvLayout after the decision; the
   *  Apply-failure fallback re-runs it without the concept overlay). */
  void ApplyEnvLayout();
  /** P7c: Apply ended != ok although the assets loaded: off ('apply-failed'), the env layout again without the concept
   *  overlay (the P5c composition) and the backdrop back; remembered per profile (ResolveConceptPasteMode). */
  void FallBackAfterApplyFailure();
  /** profile | mode | reason | env-layout key | calib: the same key = keep the parts. */
  FString ConceptPasteKey() const;
  /** After the env layout: off if the concept overlay did not apply; spawns / keeps / clears the parts, hides what the
   *  block lists (env components, fog), drives the anim component; traced. */
  void UpdateConceptPaste();
  /** The tray part of the hide list (after the tray placement of UpdateDioramaTray). */
  void HideTrayForConceptPaste();
  UPROPERTY()
  TArray<TObjectPtr<UStaticMeshComponent>> ConceptParts;
  UPROPERTY()
  TArray<TObjectPtr<UPointLightComponent>> ConceptLights;
  UPROPERTY()
  TObjectPtr<US08ConceptPasteAnimComponent> ConceptAnim;
  /** Keeps the loaded concept assets alive between ResolveConceptPasteMode and the parts (MIDs / components then own them). */
  UPROPERTY()
  TArray<TObjectPtr<UObject>> ConceptAssetRefs;
  FS08ConceptPasteAssets ConceptAssets;
  FString ConceptAssetsProfileId;
  /** P7c: the profile whose Apply failed (cleared when the assets of another profile load). */
  FString ConceptApplyFailedProfileId;
  FS08ConceptPasteInputs ConceptInputs;
  FS08ConceptPasteMode ConceptMode;
  FS08ConceptPasteRuntime ConceptRuntime;
  UPROPERTY()
  TObjectPtr<UMaterialInstanceDynamic> ContactShadowMid;
  bool bContactShadowTried = false;
  UPROPERTY()
  TObjectPtr<UMaterialInstanceDynamic> LeaderPipMidP1;  // team look slot P1 (gold)
  UPROPERTY()
  TObjectPtr<UMaterialInstanceDynamic> LeaderPipMidP2;  // team look slot P2 (steel blue)
  UPROPERTY()
  TObjectPtr<UMaterialInstanceDynamic> LeaderPipKeylineMid;
  FString ReadabilityFightersTraceKey;

  // ---- ENV-MAPS P9 hero light ----
  bool bHeroLightOverride = false;
  FS08HeroLightSpec HeroLightOverride;
  TOptional<bool> HeroLightOptOutOverride;
  FString HeroLightOptOutReason = TEXT("test-opt-out");
  int32 HeroLightCount = 0;
  int32 HeroLightLayersPerFigure = 0;
  FString HeroLightTraceKey;
  FString HeroMaterialsTraceKey;  // AN-32 (ВР-16): the heroMaterials board trace
  TFunction<int64()> GameClock;   // F4: the FACING trace clock (SetGameClock)

  // ---- MS-T-08 move plates ----
  UPROPERTY()
  TObjectPtr<US08MoveHighlightComponent> MoveHighlight;
  FMoveDraftViewProvider MoveDraftViewProvider;
  /** Creates the component once (-S08MovePlates) and builds its instances for the current board. */
  void BuildMoveHighlight();
  /** The view of (FighterId, Reachable) on the plates. */
  void ApplyMovePlates(const FString& FighterId, const TSet<uint64>& Reachable);

  FS08BoardModel BoardModel;
  TArray<FS08BoardFighter> Fighters;
  FString SelectedFighterId;
  FString CombatAttackerId;
  FString CombatTargetId;
  TSet<uint64> ReachableCells;
  TArray<TObjectPtr<AActor>> HighlightTiles;
};

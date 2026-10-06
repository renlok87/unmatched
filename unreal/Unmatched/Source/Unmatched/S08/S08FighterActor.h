// GD-030 (TASK-021): grey mannequin for one fighter. Body shape separates
// hero (tall box) from minion (short box); base ring color separates own
// (blue) from enemy (red); a text label carries the numbered name.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "S08BoardModel.h"
#include "S08HeroesV2.h"
#include "S08HeroLight.h"
#include "S08MoveAnim.h"
#include "S08Team.h"
#include "TimerManager.h"
#include "S08FighterActor.generated.h"

class UStaticMeshComponent;
class USkeletalMeshComponent;
class UTextRenderComponent;
class UBillboardComponent;
class UCapsuleComponent;
class UMaterialInstanceDynamic;
class UAnimSequenceBase;
class USpotLightComponent;
class UPrimitiveComponent;

/** ART-004 T2.2 world-label presentation: the plate owner hides its world
 *  labels (the screen plate replaces them); neighbours show one compact line. */
enum class ES08FighterLabelMode : uint8 { Full, Compact, Hidden };

UCLASS()
class UNMATCHED_API AS08FighterActor : public AActor {
  GENERATED_BODY()

public:
  AS08FighterActor();

  /** Positions the mannequin at the cell center (Z=0) and applies the
   *  grey-slice visual distinctions. bTopologyBoard (ENV-MAPS original map):
   *  the target icon side follows the world X instead of the lattice column. */
  void ApplyFighter(const FS08BoardFighter& Fighter, const FVector& CellCenter,
                    bool bOwn, bool bArtPreview, bool bTopologyBoard = false);
  /** W5b-R D-2/D-3: absolute team and the drawn look (ring shape/colour, Medusa MI); call before ApplyFighter. */
  void SetTeam(ES08TeamSlot InTeam, ES08TeamSlot InLook, ES08TeamColorMode InMode) {
    Team = InTeam;
    Look = InLook;
    TeamMode = InMode;
  }
  ES08TeamSlot GetTeam() const { return Team; }
  ES08TeamSlot GetLook() const { return Look; }
  /** The authored team ring replaced the grey base disc (art figure + ring assets). */
  bool HasTeamRing() const { return bTeamRingShown; }
  /** Grey ART-003 blockout (Arthur, Merlin, Harpies) - not the art sculpt (D-1: full tag). */
  bool IsBlockout() const { return bBlockoutVisible; }
  /** W5b-R D-1: the screen tag layer hides the world TextRender name/HP lines. */
  void SetWorldLabelsSuppressed(bool bSuppressed);
  /** W5b-R D-3: loads the team ring meshes and MIs (BeginPlay under -ArtPreview; public for the automation test). */
  bool LoadTeamRingAssets();
  bool IsBaseVisible() const;
  bool IsTeamRingVisible() const;
  const UStaticMesh* GetTeamRingMesh() const;
  FVector GetTeamRingScale() const;
  const FS08BoardFighter& GetFighter() const { return Fighter; }
  const FString& GetFighterId() const { return Fighter.Id; }

  void SetSelected(bool bSelected);
  /** Art-preview combat focus. The target marker is a visual child of the
   *  fighter and never participates in the visibility hit test. */
  void SetCombatMarkers(bool bAttacker, bool bTarget);
  /** Keep world-space identity labels legible without letting camera zoom
   *  inflate them across the board. At close range show only the selected
   *  fighter's name/HP; the full roster returns at overview distance. */
  void SetLabelZoomRatio(float DistanceRatio, bool bOnlySelected);
  /** ART-004 T2.2: Full (name + HP), Compact (one short "Label HP" line) or
   *  Hidden (the plate shows this fighter). */
  void SetLabelMode(ES08FighterLabelMode Mode);
  ES08FighterLabelMode GetLabelMode() const { return LabelMode; }
  /** World box of the visible label text (false when no label is visible). */
  bool GetVisibleLabelBox(FBox& OutBox) const;
  /** Height of the visible figure above the cell plane (uu): the art sculpt,
   *  the blockout or the grey mannequin box. */
  float GetFigureHeightUU() const;
  bool HasArtFigure() const { return bArtFigureVisible; }
  bool HasMedusaCandidate() const { return bMedusaVisual; }
  /** A skeletal art sculpt is shown: the isolated Medusa candidate or a -ArtPreviewHeroesV2 figure
   *  (without the flag this equals HasMedusaCandidate()). */
  bool HasArtSculpt() const { return bMedusaVisual || bHeroV2Visual; }
  /** Wave 5c-B: a -ArtPreviewHeroesV2 figure (SK_<Hero>_H2LD / SK_Harpy_H3LD) is shown. */
  bool IsHeroV2() const { return bHeroV2Visual; }
  const S08HeroesV2::FHeroSpec* GetHeroV2Spec() const { return bHeroV2Visual ? HeroV2Spec : nullptr; }
  S08HeroesV2::EClip GetHeroClip() const { return HeroClip; }
  /** Yaw / uniform scale applied to the v2 figure (0 / 0 when none). */
  float GetHeroV2Yaw() const { return bHeroV2Visual ? HeroV2Yaw : 0.0f; }
  float GetHeroV2Scale() const { return bHeroV2Visual ? HeroV2Scale : 0.0f; }
  /** Combat event of this fighter (attack / damage); a no-op unless a v2 figure is shown. DE-025 (SD-49): PlayRate
   *  (> 0) applies to LungeAttack only - the combat animation speed; HitReact / DeathSettle / Idle always play at 1. */
  void NotifyHeroAnimEvent(S08HeroesV2::EEvent Event, int32 Seq, float PlayRate = 1.0f);
  /** DE-018 (01 F-03): contact frame (ms at x1) of this v2 figure's LungeAttack - the "Contact" AnimNotify (DE-010),
   *  else the build-profile frame; -1 without a v2 figure. OutSource = notify | profile. */
  int32 GetLungeContactMs(FString& OutSource) const;
  /** DE-018 (CUE-011): red hit tint (CPD_HitTint, M_UM_Figure_v2.2) for Seconds - full for the first 70 ms, then
   *  fading out; a no-op without a v2 figure. A new hit restarts it. */
  void PlayHitTint(float Seconds);
  /** Current CPD_HitTint value (0 when idle). */
  float GetHitTintValue() const { return HitTintValue; }
  /** Asset name of a loaded v2 clip (AM_<Key>_<Clip>), empty without one. */
  FString GetHeroClipAssetName(S08HeroesV2::EClip Clip) const;
  /** The death (DeathSettle, still, dissolve) is running: the defeated figure is still visible. */
  bool IsInDeathHold() const { return bDeathHold; }
  /** DE-019 (01 F-09): the death plan of a dying v2 figure, from its fall (the start of DeathSettle); false when no
   *  death runs (alive, not a v2 figure - the grey slice hides at once -, or already gone). OutStyle = fade / ash,
   *  "none" when the dissolve MIC is missing. */
  bool GetDeathPlan(S08HeroesV2::FDeathPlan& OutPlan, FString& OutStyle) const;
  /** The dissolve runs (the body carries the dissolve MIC); its current progress 0..1. */
  bool IsDissolving() const { return bDissolving; }
  float GetDissolveProgress() const { return DissolveValue; }
  /** Automation only (no ticking world): plays the death to SecondsSinceFall - the dissolve starts / ends as the
   *  timers would. */
  void AdvanceDeathForTest(float SecondsSinceFall);
  /** Live tune (S08LiveTune.h): position / length of the looping v2 clip that plays (false: no v2 figure, no looping clip). */
  bool GetHeroClipTime(float& OutPosition, float& OutLength) const;
  /** Live tune: moves the looping v2 clip's clock by DeltaSeconds (wrapped into the clip), so a capture shows the pose a
   *  fresh -Bench run shows at the same time since spawn; false when no looping clip plays (nothing changed). */
  bool ShiftHeroClipClock(float DeltaSeconds);
  /** AN-17 (ВР-17): -Bench -BenchClipPose review stand - holds this living v2 figure at the pose of Spec (a frame at
   *  ClipFps or q<pct> of the clip): PlayHeroClip, then SetPosition + SetPlaying(false) (play rate 0), the finish
   *  timer cleared so nothing returns it to Idle. OutT / OutLen = the resolved pose time and the clip length (s),
   *  OutRootDeltaUU = the root-motion translation from frame 0 to the pose (the figure must not slide, GD-058 Р-20).
   *  False without a v2 figure or the clip. */
  bool BenchHoldClipPose(const S08HeroesV2::FBenchClipPoseSpec& Spec, double& OutT, double& OutLen,
                         double& OutRootDeltaUU);
  /** AN-17: the world box of the visible v2 figure with its pedestal (ArtBody + ArtBase bounds; invalid without). */
  FBox GetV2FigureBox() const;
  // ---- AN-31 (ВР-07, ВР-72): the harpy number 1..3 on the base ----
  /** The digit components (never null; visibility is the state - see UpdateBaseDigit). */
  UStaticMeshComponent* GetBaseDigitDisc() const { return BaseDigitDisc; }
  UTextRenderComponent* GetBaseDigitText() const { return BaseDigitText; }
  /** AN-31 (ВР-Z1R-03): the navy disc with the cream number flat on the pedestal's top face, on the camera side
   *  turned 60 deg towards the figure's rest offset (S08HeroesV2::BaseDigitSideTurnDeg - the mirrored side of the
   *  wing rule: the near wing covered the other one; clear of the talons); sizes from the pedestal mesh bounds
   *  (disc 0.5 x the top-face diameter, centre at 0.48 R, digit em 0.9 x the disc, top of the glyph away from the
   *  camera, unlit tokens); the components ride the actor, never the figure's rotation. Shown on living v2 harpies
   *  only - hidden with -S08BaseDigitLegacy, on other figures, for a whole Place transfer and from the death
   *  dissolve on; re-placed by every apply / rest facing / move end. Traced once per figure
   *  'ARTPREVIEW basedigit fighter=.. n=.. discUU=.. capUU=.. side=..'. */
  void UpdateBaseDigit();
  /** AN-31: the base digit's text is in place and drawable (an offline font, the digit material). */
  bool IsBaseDigitDrawable() const { return bBaseDigitDrawable; }
  // ---- AN-32 (ВР-16): the heroMaterials Fix of the map light profile ----
  /** Stores the hero's fix (nullptr / neutral / -S08HeroMatFixLegacy = the plain MI, no MID) and wraps the body
   *  slots in MIDs that carry the Fix values; re-applied whenever a slot's material is swapped (the dissolve MIC,
   *  a Place transfer, the body MI back). Traced once 'ARTPREVIEW heroMat fighter=.. hero=.. look=..'. */
  void ApplyHeroMaterials(const struct FS08HeroMaterialFix* Fix);
  // ---- MS-T-16 move animation (S08MoveAnim.h; move-selection 04 §6.3) ----
  /** Plays a CUE-007 move from NowMs (the seq start, ms on the game clock): the figure stands on the plan's start cell
   *  until its slot, slides along the path (lean, turns, optional hop), settles to Idle; a Place fades out / in. The
   *  logical position stays the snapshot's: the click volume is pinned to the destination cell while the figure travels
   *  (MS-R-53). A move already playing jumps to its final pose first (jump_to_final). */
  void PlayMove(const FS08MovePlan& Plan, const FS08MoveAnimParams& Params, int64 NowMs);
  /** Advances the playing move to NowMs; false when no move plays (the last pose was applied and the move ended). */
  bool TickMove(int64 NowMs);
  /** Jumps the playing move to its final pose at once (skip, jump_to_final, a new snapshot cell); false when none plays. */
  bool FinishMove();
  bool IsMoving() const { return bMoving; }
  const FS08MovePlan& GetMovePlan() const { return MovePlan; }
  /** The pose applied last (the final pose once the move ended). */
  const FS08MovePose& GetMovePose() const { return MovePose; }
  /** World location of the click volume (the logical cell while a move plays). */
  FVector GetClickVolumeLocation() const;
  /** World yaw / lean currently applied to the figure mesh (the v2 body, the Medusa candidate or the blockout). */
  float GetFigureYawDeg() const { return FacingYawDeg; }
  float GetFigureLeanDeg() const { return FacingLeanDeg; }
  /** AN-23 (ВР-06): the rest facing of a standing figure. bLegacy applies the half-field rule at once and traces
   *  nothing; else the wanted angle (S08Facing::RestYaw: three-quarter to CameraPos, offset to the nearest living
   *  enemy) is reached over 150 ms on the shortest arc (instant under reduced motion / speed "none"), traced
   *  'FACING fighter=.. src=.. rest=.. cam=.. off=.. enemy=..' when a turn of at least S08Facing::MinTurnDeg starts.
   *  The first apply of a living figure is its spawn: traced src=spawn always (ВР-Z1R-04), facing the camera axis
   *  when no living enemy is there yet (the card). Skipped while a move plays (the plan owns the facing until it
   *  ends), while an attack holds the target angle (AN-24 / AN-25) and for a dead figure (ВР-06: death never turns). */
  void ApplyRestFacing(const TCHAR* Src, bool bLegacy, const FVector& CameraPos, bool bHasEnemy,
                       const FVector& NearestEnemyPos, const FString& EnemyId);
  /** AN-24 (ВР-06): the attacker turns to face TargetWorldPos over Ms (the remaining face window): the direction to
   *  the target clamped to +-90 deg from the camera axis (S08Facing::AttackYaw, ВР-AN02 - never the back), holding
   *  the angle through the following LungeAttack until the AN-25 return. NowMs = the game (CUE) clock of the event.
   *  bSnapAtLunge (speed "none") or reduced motion: no turn now - the angle snaps in the Lunge frame
   *  (CommitFaceTarget, ВР-Z1R-05). A no-op with -S08FacingLegacy. Traced
   *  'FACING fighter=.. src=attack t=.. from=.. yaw=.. target=.. clamped=0|1 ms=..'. */
  void PlayFaceTarget(const FString& TargetId, const FVector& TargetWorldPos, double Ms, int64 NowMs,
                      bool bSnapAtLunge);
  /** AN-24: the Lunge frame - a face turn deferred by reduced motion / speed "none" snaps now (traced ms=0). */
  void CommitFaceTarget(int64 NowMs);
  /** AN-25 (ВР-06): back to the rest angle after a lunge (src=attack-return) or a HitReact (src=hit-return) - the
   *  wanted angle comes from the caller (the board actor's camera + enemies); the dead band never holds it (the
   *  return always reaches the rest angle). Ends the attack hold. No turn and no trace under S08Facing::MinTurnDeg.
   *  Traced 'FACING fighter=.. src=attack-return|hit-return t=.. from=.. rest=.. ms=150'. */
  void ReturnToRestFacing(const TCHAR* Src, double WantYawDeg, double Ms, int64 NowMs);
  /** AN-24 / AN-25: the attacker holds its target angle (from the Face event until its return). */
  bool IsHoldingAttackFacing() const { return bFaceHold; }
  /** A facing turn (rest, attack or return) is still blending. */
  bool IsFacingTurning() const { return bFacingTurning; }
  /** Automation / frame tick: advances a facing turn by DeltaSeconds (the actor tick calls it while a turn blends). */
  void AdvanceFacingTurn(float DeltaSeconds);
  /** The world yaw of the v2 mesh as shown (ArtBody relative yaw; the figure yaw of the other visuals). */
  float GetShownFigureYawDeg() const;
  virtual void Tick(float DeltaSeconds) override;

  /** Screen-space combat icon mode: the world billboard stays hidden while
   *  the HUD draws the exact-size icon (the trace still reports icon=1). */
  void SetScreenIconMode(bool bScreen);

  // ---- ENV-MAPS P9 hero light (S08HeroLight.h, docs/art-pipeline/ENV-HERO-LIGHT.md) ----
  /** Builds / updates / removes the per-figure rig: Spec = the active light profile's block (nullptr = no rig), Layers =
   *  lights for this figure within the board budget (0 = no rig), bFrozen = no breathing pulse (-Bench frames). Call
   *  after ApplyFighter (the figure height). The figure meshes join lighting channel 1 only while a rig is on. */
  void ApplyHeroLight(const FS08HeroLightSpec* Spec, int32 LayerCount, bool bFrozen);
  /** Number of hero light components currently on (0..2). */
  int32 GetHeroLightCount() const;
  /** Layer 0 = key, 1 = rim (nullptr when that layer is not built). */
  const USpotLightComponent* GetHeroLight(int32 Layer) const;
  ES08HeroLightState GetHeroLightState() const { return HeroLightState; }
  /** The state multiplier applied last (1 idle, ActiveMul (x pulse) active, DefeatedMul defeated, 0 off). */
  float GetHeroLightMultiplier() const { return HeroLightMul; }
  /** The figure primitives that take the hero light (channels 0 + 1 while a rig is on): the body / placeholder / grey box,
   *  and the pedestal only when the block has "litPedestal": true (P9b). */
  TArray<const UPrimitiveComponent*> GetHeroLitPrimitives() const;
  /** The figure pedestal (ArtBase): channel 0 only unless the rig's block has "litPedestal": true. */
  const UPrimitiveComponent* GetHeroPedestal() const;

protected:
  virtual void BeginPlay() override;

private:
  UPROPERTY()
  TObjectPtr<UStaticMeshComponent> Base;

  UPROPERTY()
  TObjectPtr<UStaticMeshComponent> Body;

  UPROPERTY()
  TObjectPtr<UTextRenderComponent> Label;

  UPROPERTY()
  TObjectPtr<UTextRenderComponent> HpLabel;

  UPROPERTY()
  TObjectPtr<UStaticMeshComponent> Ring;

  // W5b-R D-3: the authored team ring (SM_Marker_TeamRing_P1/_P2) of an art figure, z +0.6..+1.2 above the tile.
  UPROPERTY()
  TObjectPtr<UStaticMeshComponent> TeamRing;
  UPROPERTY()
  TObjectPtr<UStaticMesh> TeamRingMeshP1;
  UPROPERTY()
  TObjectPtr<UStaticMesh> TeamRingMeshP2;
  UPROPERTY()
  TObjectPtr<UMaterialInterface> TeamRingKeyline;
  UPROPERTY()
  TObjectPtr<UMaterialInterface> TeamRingFill;
  UPROPERTY()
  TObjectPtr<UMaterialInterface> TeamRingRim;
  UPROPERTY()
  TObjectPtr<UMaterialInstanceDynamic> TeamRingFillMid;

  UPROPERTY()
  TObjectPtr<UStaticMeshComponent> TargetRing;

  UPROPERTY()
  TObjectPtr<UBillboardComponent> TargetIcon;

  UPROPERTY()
  TObjectPtr<USkeletalMeshComponent> ArtBody;

  UPROPERTY()
  TObjectPtr<UStaticMeshComponent> ArtBase;

  UPROPERTY()
  TObjectPtr<UStaticMeshComponent> ArtPlaceholder;

  // AN-31 (ВР-07, ВР-72): the harpy base digit - a flat disc + a text render on the pedestal's camera-side edge.
  UPROPERTY()
  TObjectPtr<UStaticMeshComponent> BaseDigitDisc;
  UPROPERTY()
  TObjectPtr<UTextRenderComponent> BaseDigitText;
  UPROPERTY()
  TObjectPtr<UMaterialInstanceDynamic> BaseDigitMid;
  UPROPERTY()
  TObjectPtr<UMaterialInstanceDynamic> BaseDigitTextMid;
  FString BaseDigitTraceKey;
  bool bBaseDigitDrawable = false;
  // AN-32 (ВР-16): the heroMaterials Fix over per-slot MIDs of the v2 body (neutral = the plain MI).
  int32 HeroMatClassA = -1;
  float HeroMatGainA = 1.0f;
  float HeroMatSpecA = 0.0f;
  int32 HeroMatClassB = -1;
  float HeroMatGainB = 1.0f;
  float HeroMatSpecB = 0.0f;
  bool bHasHeroMaterialFix = false;
  bool bHeroMatTraced = false;
  UPROPERTY()
  TArray<TObjectPtr<UMaterialInstanceDynamic>> HeroMaterialMids;
  void ApplyHeroMaterialMids();

  // ART-004 T2.2: click volume matching the visible art figure. The candidate
  // skeletal meshes carry no physics asset, and the hidden 120-uu grey Body
  // box used to catch clicks far above the 55-uu sculpt.
  UPROPERTY()
  TObjectPtr<UCapsuleComponent> ClickCapsule;

  bool bArtSelectionRingLoaded = false;
  bool bArtTargetRingLoaded = false;
  bool bArtTargetIconLoaded = false;
  bool bIsSelected = false;
  bool bIsCombatAttacker = false;
  bool bIsCombatTarget = false;
  float BaseNameWorldSize = 18.0f;
  float BaseHpWorldSize = 22.0f;
  float BaseNameHeight = 82.0f;
  float BaseHpHeight = 66.0f;
  float LastLabelRatio = -1.0f;
  bool bLastOnlySelected = false;
  ES08FighterLabelMode LabelMode = ES08FighterLabelMode::Full;
  bool bArtFigureVisible = false;
  bool bMedusaVisual = false;
  bool bScreenIconMode = false;
  float FigureHeightUU = 120.0f;
  bool bCapsuleTraced = false;
  bool bAllMedusaTraced = false;
  bool bMedusaMaterialsTraced = false;
  bool bTeamRingReady = false;
  bool bTeamRingShown = false;
  bool bTeamRingTraced = false;
  bool bBlockoutVisible = false;
  bool bWorldLabelsSuppressed = false;
  ES08TeamSlot Team = ES08TeamSlot::P1;
  ES08TeamSlot Look = ES08TeamSlot::P1;
  ES08TeamColorMode TeamMode = ES08TeamColorMode::Absolute;
  void ApplyLabelVisibility();

  // Wave 5c-B -ArtPreviewHeroesV2 figure and its clips (indexed by S08HeroesV2::EClip).
  UPROPERTY()
  TArray<TObjectPtr<UAnimSequenceBase>> HeroClips;
  const S08HeroesV2::FHeroSpec* HeroV2Spec = nullptr;
  bool bHeroV2Visual = false;
  bool bHasApplied = false;
  bool bDeathHold = false;
  bool bDeathDone = false;
  float HeroV2Yaw = 0.0f;
  float HeroV2Scale = 1.0f;
  S08HeroesV2::EClip HeroClip = S08HeroesV2::EClip::None;
  FString HeroV2TraceKey;
  FTimerHandle HeroClipTimer;
  FTimerHandle DeathHideTimer;
  // DE-019: the death plan, its start (world seconds) and the dissolve (MIC swap + CPD progress by a short timer).
  S08HeroesV2::FDeathPlan DeathPlan;
  S08HeroesV2::EDissolveStyle DeathStyle = S08HeroesV2::EDissolveStyle::Fade;
  double DeathFallSeconds = 0.0;
  bool bDissolving = false;
  float DissolveValue = 0.0f;
  bool bBenchDissolveTraced = false;
  UPROPERTY()
  TObjectPtr<UMaterialInterface> DissolveMaterial;
  FTimerHandle DissolveTimer;
  void OnDeathStillFinished();
  void TickDissolve();
  void StepDissolve(float SecondsSinceFall);
  /** -Bench -BenchDissolve=<p> (G-COST): a living v2 figure frozen at that dissolve progress. */
  void ApplyBenchDissolve();
  // DE-018 hit tint (CPD_HitTint) driven by a short timer while it fades.
  FTimerHandle HitTintTimer;
  double HitTintStartSeconds = 0.0;
  float HitTintSeconds = 0.0f;
  float HitTintValue = 0.0f;
  void TickHitTint();
  /** Loads and applies the v2 figure; false (nothing changed) when an asset is missing. */
  bool ApplyHeroV2(const S08HeroesV2::FHeroSpec& Spec, const FVector& CellCenter, USkeletalMesh*& OutMesh);
  void PlayHeroClip(S08HeroesV2::EClip Clip, S08HeroesV2::EEvent Event, int32 Seq, float PlayRate = 1.0f);
  void OnHeroClipFinished();
  void OnDeathHoldFinished();
  void BeginHeroDeath();

  // ENV-MAPS P9 hero light: key (0) + rim (1) spot lights on lighting channel 1, created on first use.
  UPROPERTY()
  TArray<TObjectPtr<USpotLightComponent>> HeroLights;
  FS08HeroLightSpec HeroLightSpec;
  TArray<float> HeroLightBaseCd;  // candelas per layer at multiplier 1
  int32 HeroLightLayers = 0;
  bool bHeroLightFrozen = false;
  bool bHeroLitChannels = false;
  bool bHeroLitPedestal = false;  // P9b: ArtBase on channel 1 only with "litPedestal": true
  float HeroLightMul = 0.0f;
  float HeroLightPhase = 0.0f;
  ES08HeroLightState HeroLightState = ES08HeroLightState::Off;
  FString HeroLightRigKey;
  FString HeroLightTraceKey;
  FTimerHandle HeroLightPulseTimer;
  /** Off / Idle / Active / Defeated from the rig, the fighter and the selection / combat markers. */
  ES08HeroLightState ComputeHeroLightState() const;
  /** Re-evaluates the state (selection, combat focus, death) and the pulse timer; traces a change. */
  void RefreshHeroLightState();
  void ApplyHeroLightIntensity();
  void OnHeroLightPulse();
  /** The figure meshes on channels 0 + 1 while bLit (the pedestal too only when bPedestal), else channel 0 only. */
  void SetHeroLitChannels(bool bLit, bool bPedestal);

  // MS-T-16 move animation state (driven by the game mode's clock through the board actor).
  bool bMoving = false;
  FS08MovePlan MovePlan;
  FS08MoveAnimParams MoveParams;
  FS08MovePose MovePose;
  int64 MoveSeqStartMs = 0;
  FVector LogicalCenter = FVector::ZeroVector;
  bool bMoveFading = false;          // Place: the body carries the dissolve MIC while it fades
  float FacingYawDeg = 0.0f;
  float FacingLeanDeg = 0.0f;
  /** Applies a pose: actor location, figure yaw + lean, the Place fade; the click volume stays on LogicalCenter. */
  void ApplyMovePose(const FS08MovePose& Pose);
  /** Restores the click volume, the collision and the body materials after a move. */
  void EndMove();
  /** Figure mesh rotation for a world facing + lean (v2: forward +X; legacy candidate / blockout: forward +Y). */
  void ApplyFigureFacing(double YawDeg, double LeanDeg);
  // AN-23 (ВР-06): the rest-facing turn (150 ms, shortest arc), driven by the actor's frame tick while it blends
  // (F6: never a fixed-rate timer); AN-24's face turn and AN-25's return reuse it (FacingTurnMs tells which length).
  double FacingTurnFromDeg = 0.0;
  double FacingTurnToDeg = 0.0;
  double FacingTurnMs = 0.0;
  double FacingTurnElapsedMs = 0.0;
  bool bFacingTurning = false;
  bool bRestFacingApplied = false;
  // AN-24: the attacker holds the target angle from the Face event to its return; a snap deferred to the Lunge frame.
  bool bFaceHold = false;
  bool bFacePending = false;
  double FacePendingYawDeg = 0.0;
  FString FacePendingTrace;
  // AN-31: the rest angle the base digit is placed against (the side away from the figure's rest offset).
  double DigitRestYawDeg = 0.0;
  bool bDigitRestYawSet = false;
  /** Starts the blend to WantYawDeg over Ms (instant under reduced motion / speed "none" or Ms <= 0). */
  void StartFacingTurn(double WantYawDeg, double Ms);
  /** Stops a running facing turn where it is. */
  void StopFacingTurn();

  FS08BoardFighter Fighter;
};

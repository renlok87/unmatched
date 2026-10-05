// GD-030 (TASK-021): grey mannequin for one fighter. Body shape separates
// hero (tall box) from minion (short box); base ring color separates own
// (blue) from enemy (red); a text label carries the numbered name.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "S08BoardModel.h"
#include "S08HeroesV2.h"
#include "S08HeroLight.h"
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
  /** Combat event of this fighter (attack / damage); a no-op unless a v2 figure is shown. */
  void NotifyHeroAnimEvent(S08HeroesV2::EEvent Event, int32 Seq);
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
  /** The death hold (DeathSettle final pose) is running: the defeated figure is still visible. */
  bool IsInDeathHold() const { return bDeathHold; }
  /** Live tune (S08LiveTune.h): position / length of the looping v2 clip that plays (false: no v2 figure, no looping clip). */
  bool GetHeroClipTime(float& OutPosition, float& OutLength) const;
  /** Live tune: moves the looping v2 clip's clock by DeltaSeconds (wrapped into the clip), so a capture shows the pose a
   *  fresh -Bench run shows at the same time since spawn; false when no looping clip plays (nothing changed). */
  bool ShiftHeroClipClock(float DeltaSeconds);
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
  // DE-018 hit tint (CPD_HitTint) driven by a short timer while it fades.
  FTimerHandle HitTintTimer;
  double HitTintStartSeconds = 0.0;
  float HitTintSeconds = 0.0f;
  float HitTintValue = 0.0f;
  void TickHitTint();
  /** Loads and applies the v2 figure; false (nothing changed) when an asset is missing. */
  bool ApplyHeroV2(const S08HeroesV2::FHeroSpec& Spec, const FVector& CellCenter, USkeletalMesh*& OutMesh);
  void PlayHeroClip(S08HeroesV2::EClip Clip, S08HeroesV2::EEvent Event, int32 Seq);
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

  FS08BoardFighter Fighter;
};

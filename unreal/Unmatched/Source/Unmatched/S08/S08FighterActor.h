// GD-030 (TASK-021): grey mannequin for one fighter. Body shape separates
// hero (tall box) from minion (short box); base ring color separates own
// (blue) from enemy (red); a text label carries the numbered name.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "S08BoardModel.h"
#include "S08HeroesV2.h"
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

/** ART-004 T2.2 world-label presentation: the plate owner hides its world
 *  labels (the screen plate replaces them); neighbours show one compact line. */
enum class ES08FighterLabelMode : uint8 { Full, Compact, Hidden };

UCLASS()
class UNMATCHED_API AS08FighterActor : public AActor {
  GENERATED_BODY()

public:
  AS08FighterActor();

  /** Positions the mannequin at the cell center (Z=0) and applies the
   *  grey-slice visual distinctions. */
  void ApplyFighter(const FS08BoardFighter& Fighter, const FVector& CellCenter,
                    bool bOwn, bool bArtPreview);
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
  /** The death hold (DeathSettle final pose) is running: the defeated figure is still visible. */
  bool IsInDeathHold() const { return bDeathHold; }
  /** Screen-space combat icon mode: the world billboard stays hidden while
   *  the HUD draws the exact-size icon (the trace still reports icon=1). */
  void SetScreenIconMode(bool bScreen);

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
  /** Loads and applies the v2 figure; false (nothing changed) when an asset is missing. */
  bool ApplyHeroV2(const S08HeroesV2::FHeroSpec& Spec, const FVector& CellCenter, USkeletalMesh*& OutMesh);
  void PlayHeroClip(S08HeroesV2::EClip Clip, S08HeroesV2::EEvent Event, int32 Seq);
  void OnHeroClipFinished();
  void OnDeathHoldFinished();
  void BeginHeroDeath();

  FS08BoardFighter Fighter;
};

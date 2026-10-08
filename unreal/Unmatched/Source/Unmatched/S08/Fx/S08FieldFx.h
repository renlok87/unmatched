// VS-6 F1 (visual chat, 2026-10-08): the field and choice FX of the cards FX-07, FX-08, FX-09, FX-10, FX-13, FX-14,
// FX-15, FX-16 and IC-35 (docs/game-design/visual/06-tasks/vfx.csv, icons.csv; 02-visual-design.md §7.2, §7.3, §7.5,
// §9.2, §9.3; decisions ВР-27, ВР-29, ВР-30, ВР-FX12, ВР-FX14 and the new ВР-VS6-NN of
// docs/game-design/evidence/VISUAL/VS-6-F1/README.md).
//
// What lives here (the hot-file rule: AS08FighterActor / AS08FlowGameMode keep one-line hook points):
//   * the rollbacks of the cards: -S08ChoiceLegacy (V-05 yellow ring on M_S08_Solid, V-17 / V-11 / V-12 in the plate
//     colour), -S08MovePlatesLegacy (no confirm pulse, ВР-28), -S08LastMoveLegacy (the MS-T-17 contour, no hold),
//     -S08TargetArcLegacy (the red arcs and the mvp-v1 world sprite); -S08FxLegacy (Z-2) also turns the dust, the
//     chevrons and the refuse stamp off;
//   * the keyframes of every card as pure, world-free functions (Unmatched.S08.FieldFx.* test them at the card's
//     time stamps); the materials and the Niagara systems read the same numbers (tools/art/fx/ue_fx_field.py);
//   * FS08FieldMarks - the selection ring V-05 and the target arcs of one figure (a member of AS08FighterActor): the
//     MIDs of MI_FX_SelectionRing / MI_FX_TargetArc (M_FX_FieldMark) and their appear / leave curves on a 60 Hz timer;
//   * FS08FieldFxState - the board-side state of the game mode (delayed chevrons, CUE-007 feeds and dust, the cut of
//     the chevrons by an interrupting combat cue); the adapter is S08FlowGameModeFx.cpp.
#pragma once

#include "CoreMinimal.h"
#include "Engine/TimerHandle.h"
#include "UObject/WeakObjectPtr.h"

class AActor;
class UMaterialInstanceDynamic;
class UNiagaraComponent;
class UStaticMeshComponent;

namespace S08FieldFx {

// ---- rollbacks (ARTLOOK fieldFx=) ----
inline const TCHAR* const ChoiceLegacyFlag = TEXT("S08ChoiceLegacy");
inline const TCHAR* const MovePlatesLegacyFlag = TEXT("S08MovePlatesLegacy");
inline const TCHAR* const LastMoveLegacyFlag = TEXT("S08LastMoveLegacy");
inline const TCHAR* const TargetArcLegacyFlag = TEXT("S08TargetArcLegacy");
enum ELegacy : uint32 { Choice = 1, Pulse = 2, LastMove = 4, TargetArc = 8 };
/** FX-07 / FX-08: the V-05 ring and the V-17 / V-11 / V-12 channels take board.choice unless -S08ChoiceLegacy. */
UNMATCHED_API bool ChoiceLegacy();
/** FX-09: the confirm pulse of the plates unless -S08MovePlatesLegacy (ВР-28). */
UNMATCHED_API bool PulseLegacy();
/** FX-14: the dashed path + arrow, held 1500 ms, unless -S08LastMoveLegacy (the MS-T-17 contour). */
UNMATCHED_API bool LastMoveLegacy();
/** FX-15 / IC-35: the cream arcs and the v3 world token unless -S08TargetArcLegacy (-S08IconLegacy keeps the old
 *  sprite too). */
UNMATCHED_API bool TargetArcLegacy();
/** The choice layer of the plate ISM is built without -S08MovePlates (V-17 of DE-017, the FX-14 path, the pulse). */
UNMATCHED_API bool ChoiceLayerWanted();
/** Automation: force the rollback bits (ELegacy); Reset reads the command line again. */
UNMATCHED_API void SetLegacyOverrideForTest(uint32 Mask);
UNMATCHED_API void ResetLegacyOverrideForTest();
/** The ARTLOOK token: on | legacy(<flags>). */
UNMATCHED_API FString ArtLookToken();

// ---- assets (tools/art/fx/ue_fx_field.py) ----
inline const TCHAR* const SelectionRingMi = TEXT("/Game/S08/FX/Materials/MI_FX_SelectionRing.MI_FX_SelectionRing");
inline const TCHAR* const TargetArcMi = TEXT("/Game/S08/FX/Materials/MI_FX_TargetArc.MI_FX_TargetArc");
inline const TCHAR* const PlaneMeshPath = TEXT("/Engine/BasicShapes/Plane.Plane");
/** IC-35 (ВР-IC15): the world fallback of the target token - the v3 master, POT 1024 with mips, TEXTUREGROUP_World. */
inline const TCHAR* const WorldTokenTexture =
    TEXT("/Game/S08/UI/IconsV3/T_IV3_action_attack_token_World.T_IV3_action_attack_token_World");
/** M_FX_FieldMark parameters (unlit translucent game layer, EyeAdaptationInverse like M_UM_MovePlate). */
inline const TCHAR* const ParamColorBody = TEXT("ColorBody");
inline const TCHAR* const ParamColorKeyline = TEXT("ColorKeyline");
inline const TCHAR* const ParamMode = TEXT("Mode");            // 0: SDF ring, 1: mesh + outer keyline, 2: four arcs
inline const TCHAR* const ParamRadiusIn = TEXT("RadiusIn");    // uu (mode 0)
inline const TCHAR* const ParamRadiusOut = TEXT("RadiusOut");  // uu (mode 0)
inline const TCHAR* const ParamOuterUU = TEXT("OuterUU");      // the mesh's outer radius in uu at scale 1 (mode 1)
inline const TCHAR* const ParamKeylineUU = TEXT("KeylineUU");
inline const TCHAR* const ParamOpacity = TEXT("Opacity");
inline const TCHAR* const ParamScale = TEXT("Scale");
inline const TCHAR* const ParamArcSpan = TEXT("ArcSpanDeg");   // mode 2: the angular span of each of the four arcs

// ---- FX-07 V-05 (ВР-FX12): solid ring 2 x V-17 wide (2 x 1.2 uu) on the V-17 radius 18.9, outer keyline 1 uu ----
inline constexpr float SelectionRadiusUU = 18.9f;
inline constexpr float SelectionWidthUU = 2.4f;
inline constexpr float SelectionKeylineUU = 1.0f;
/** Above the candidate ring (CandidateZ 1.6) and the pedestal top; the plane covers the ring with a margin. */
inline constexpr float SelectionZ = 1.75f;
inline constexpr float SelectionPlaneUU = 46.0f;
inline constexpr int32 MarkSortPriority = 12;  // over the plates (10), under the FX (20)
// ---- FX-15 (ВР-30, ВР-VS6-02): four board.target arcs OUTSIDE the team ring (r 30..35 uu, the rim ends at 28.5),
// keyline mark.keyline 1.5 uu around them (the 1.9 uu arcs of SM_Marker_TargetRing left no cream body inside a
// 1.5 uu keyline); centred on the diagonals, 56 deg each; under 1.2 cell radii, never over the pedestal ----
inline constexpr float TargetRadiusIn = 30.0f;
inline constexpr float TargetRadiusOut = 35.0f;
inline constexpr float TargetKeylineUU = 1.5f;
inline constexpr float TargetArcSpanDeg = 56.0f;
inline constexpr float TargetZ = 2.5f;
inline constexpr float TargetPlaneUU = 90.0f;

/** Scale and opacity of a mark at a moment of its curve. */
struct FMarkPose {
  float Scale = 1.0f;
  float Opacity = 1.0f;
  bool bDone = false;  // the curve reached its end (the timer may stop)
};
/** FX-07 keyframes: 0 ms scale 0.85 / opacity 0; 0-120 ms -> 1.0 / 1 (ease-out); 120-250 hold. Reduced motion: no
 *  scale, opacity 0 -> 1 within 100 ms. */
UNMATCHED_API FMarkPose SelectionAppear(double Ms, bool bReduced);
/** FX-07 cancel: opacity 1 -> 0 over 150 ms (07), reduced 100 ms. */
UNMATCHED_API FMarkPose SelectionLeave(double Ms, bool bReduced);
inline constexpr double SelectionAppearMs = 250.0;
inline constexpr double SelectionLeaveMs = 150.0;
/** FX-15 keyframes: 0 ms scale 1.15 / opacity 0; 0-150 ms -> 1.0 / 1; reduced: opacity only within 100 ms. */
UNMATCHED_API FMarkPose TargetAppear(double Ms, bool bReduced);
/** FX-15 leave: 120 ms (reduced 100). */
UNMATCHED_API FMarkPose TargetLeave(double Ms, bool bReduced);
inline constexpr double TargetAppearMs = 150.0;
inline constexpr double TargetLeaveMs = 120.0;

/** FX-09: the confirm pulse of one plate - scale 1.06 -> 1.0 ease-out over 250 ms, the fill 100 % -> the V-10 state
 *  (FillAlpha x 0.7, brightness -30 %). Reduced motion: no scale, the change within 100 ms. */
struct FPulsePose {
  float Scale = 1.0f;
  float Fill = 0.0f;  // 1 = the full plate fill, 0 = the V-10 resting fill
  float Dim = 1.0f;   // brightness factor: 1 at 0 ms, 0.7 at the end
  bool bDone = false;
};
UNMATCHED_API FPulsePose ConfirmPulse(double Ms, bool bReduced);
inline constexpr double ConfirmPulseMs = 250.0;

/** FX-10 stamp: 0 ms scale 1.2 / opacity 0; 0-80 -> 1.0 / 1; 80-230 hold; 230-350 opacity -> 0. Reduced: opacity
 *  only, in 30 / out 30 inside 100 ms. */
UNMATCHED_API FMarkPose RefuseStamp(double Ms, bool bReduced);
inline constexpr double RefuseMs = 350.0;
inline constexpr double RefuseRetriggerMs = 300.0;
/** FX-10: the badge size on screen - clamp(0.3 x the cell diameter on screen, 24, 32) px (02 §5.3 L6 badges, the
 *  card's 24 px floor at 720p, ВР-VS6-04). */
UNMATCHED_API float RefuseBadgePx(float CellDiameterPx);

// ---- FX-08: board.choice timing (V-17 in 100 / out 100 ms in the selection frame; V-11 / V-12 in 150, out 120) ----
inline constexpr double CandidateInMs = 100.0;
inline constexpr double CandidateOutMs = 100.0;
inline constexpr double PendingInMs = 150.0;
inline constexpr double PendingOutMs = 120.0;
/** 0..1 of a fade at Ms of DurMs (reduced motion: 100 ms at most). */
UNMATCHED_API float FadeIn(double Ms, double DurMs, bool bReduced);

// ---- FX-14 (ВР-29): appear 150, hold 1500, fade 300 ----
inline constexpr double LastPathInMs = 150.0;
inline constexpr double LastPathHoldMs = 1500.0;
inline constexpr double LastPathFadeMs = 300.0;
inline constexpr int32 LastPathDashPerEdge = 12;

// ---- FX-13 dust (the material M_FX_BoardPrint mirrors these numbers; tools/art/fx/ue_fx_field.py) ----
inline constexpr double DustMs = 300.0;
inline constexpr float DustQuadUU = 100.0f;  // the plane quad: radius 50 >= 35 + 11
inline constexpr float DustZ = 1.0f;
/** 3..5 discs by the seed (the CRC of the cell, ВР-VS6-07). */
UNMATCHED_API int32 DustCount(uint32 Seed);
/** The disc at Ms (0..300): distance from the centre, radius, opacity (keyframes of the card). */
struct FDustDisc {
  float DistUU = 0.0f;
  float RadiusUU = 0.0f;
  float Opacity = 0.0f;
};
UNMATCHED_API FDustDisc DustAt(double Ms, float SpreadUU);
/** The dust quad at a landing point: the seed = CRC32 of the rounded point (deterministic per space); the quad's size
 *  carries the disc count (100 x (1 + 0.04 (N - 3)) uu), its yaw turns the pattern (M_FX_BoardPrint decodes both). */
UNMATCHED_API FTransform DustTransform(const FVector& At);

// ---- FX-16 chevrons ----
inline constexpr double ChevronDelayMs = 150.0;  // cue-table CUE-008 feedback_delay_ms
inline constexpr double ChevronMs = 600.0;
inline constexpr double ChevronCutMs = 80.0;
inline constexpr float ChevronZ = 1.0f;
/** Chevron I (0..2) at Ms from t0: 0.6 -> 1.0 over 80 ms from 120 x I, all three fade 480 -> 600. */
UNMATCHED_API FMarkPose ChevronAt(int32 Index, double Ms);
/** The chevron's width across the attack (uu): >= 0.35 of the cell radius, for neighbours >= 0.2 (the card). */
UNMATCHED_API float ChevronWidthUU(float LengthUU, float CellRadiusUU);

}  // namespace S08FieldFx

/** FX-07 / FX-15: the selection ring V-05 and the target arcs of one figure. A member of AS08FighterActor; Bind gives
 *  it the two components once (BeginPlay), the actor's SetSelected / SetCombatMarkers call SetSelected / SetTarget. */
struct UNMATCHED_API FS08FieldMarks {
  /** Loads MI_FX_SelectionRing / MI_FX_TargetArc, puts the engine plane on the ring component, makes the MIDs.
   *  False (nothing changes, the actor keeps its old look) with a rollback flag or a missing asset. */
  bool Bind(AActor* InOwner, UStaticMeshComponent* InRing, UStaticMeshComponent* InTargetRing);
  bool IsRingReady() const { return bRingReady; }
  bool IsTargetReady() const { return bTargetReady; }
  /** The figure scale (hero 1, sidekick 0.78) of the ring radius; the arcs keep the actor's scale. */
  void SetFigureScale(float Scale);
  /** Appear (FX-07 keyframes) / leave (150 ms); returns true when the ring component should be visible now. */
  bool SetSelected(bool bOn, bool bInstantOff = false);
  bool SetTarget(bool bOn);
  /** Death / reset: both marks off now (no leave curve). */
  void HideNow();
  /** -BenchFx: the pose at Ms of the appear curve, no timer. */
  void SetStatic(bool bRing, double RingMs, bool bTarget, double TargetMs);
  float GetRingOpacity() const { return RingPose.Opacity; }
  float GetTargetOpacity() const { return TargetPose.Opacity; }

private:
  void Kick();
  void Tick();
  void Apply();
  double Now() const;

  TWeakObjectPtr<AActor> Owner;
  TWeakObjectPtr<UStaticMeshComponent> Ring;
  TWeakObjectPtr<UStaticMeshComponent> TargetRing;
  TWeakObjectPtr<UMaterialInstanceDynamic> RingMid;
  TWeakObjectPtr<UMaterialInstanceDynamic> TargetMid;
  FTimerHandle Timer;
  bool bRingReady = false;
  bool bTargetReady = false;
  float FigureScale = 1.0f;
  FVector TargetBaseScale = FVector::OneVector;
  float TargetOuterUU = 0.0f;
  // curve state: bOn + the start of the current curve (world seconds)
  bool bRingOn = false;
  bool bRingAnim = false;
  double RingStartS = 0.0;
  bool bTargetOn = false;
  bool bTargetAnim = false;
  double TargetStartS = 0.0;
  S08FieldFx::FMarkPose RingPose{1.0f, 0.0f, true};
  S08FieldFx::FMarkPose TargetPose{1.0f, 0.0f, true};
};

/** The board side of the field FX in the game mode (S08FlowGameModeFx.cpp drives it). */
struct UNMATCHED_API FS08FieldFxState {
  struct FPendingMove {
    FString FighterId;
    int32 Seq = 0;
    double StartAtMs = 0.0;   // game clock (NowMs) of the plan's start
    double LandAtMs = 0.0;    // the landing frame (start + travel)
    int32 DurationMs = 0;
    FVector Destination = FVector::ZeroVector;
    bool bSnapped = false;
    bool bFed = false;        // the CUE-007 line was written
  };
  struct FPendingChevrons {
    FString AttackerId;
    FString TargetId;
    int32 Seq = 0;
    double ShowAtMs = 0.0;    // event + 150 (feedback_delay_ms)
  };
  TArray<FPendingMove> Moves;
  TArray<FPendingChevrons> Chevrons;
  TSet<FString> DustDone;     // "<fighter>|<seq>": one dust per landing (a merge re-schedules the same plans)
  TWeakObjectPtr<UNiagaraComponent> LiveChevrons;
  FString LiveChevronsAttacker;
  int32 LiveChevronsSeq = -1;
  void Reset() { *this = FS08FieldFxState(); }
};

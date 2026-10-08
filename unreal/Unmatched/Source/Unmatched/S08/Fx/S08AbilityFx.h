// VS-6 F3 (visual chat; docs/game-design/visual/06-tasks/vfx.csv FX-26, FX-27, FX-28, FX-30, FX-32, anim.csv AN-29;
// 02-visual-design.md §9.2 CUE-013 / CUE-014; ВР-13, ВР-22, ВР-25): the death and ability FX - the world-free numbers
// of the cards and the adapter state of AS08FlowGameMode (S08FlowGameModeAbilityFx.cpp).
//
//   FX-26 embers    NS_FX_AshEmbers, one camera-facing quad over the dissolving figure (M_FX_AbilityPrintDepth mode 2,
//                   ВР-VS6-22): <= 40 rhomb chips (8 per 100 ms of the dissolve - 40 hero / 32 sidekick) born at the
//                   height of the burning front on a cylinder of 0.35 H, rising 40-80 uu/s, +-10 uu drift, 90-180
//                   deg/s spin, 2-4 -> 1 uu, the last 40 % of the life fading; the system lives 600 ms from the dissolve
//                   start (ВР-13). The user parameters FrontHeight (dissolve progress, written every dissolve tick),
//                   TeamScreenColor (team.p1.screen / team.p2.screen of the figure's look) and DissolveMs are bound to
//                   the material (Niagara material parameter bindings, ВР-VS6-23). Not spawned under the fade style
//                   (-S08DissolveFade, reduced motion), without the dissolve MIC, with -S08FxLegacy.
//   FX-28 CUE-014   Medusa: the snapshot that resolved her pending `ability-medusa-target-p<n>` (TARGET_FIGHTER, the
//                   id gone from metadata.pendingEffects, a listed target lost HP) - an AbilityTriggered cue of
//                   FS08FlowController::ComputeCues; Arthur: the FlipAttack of a combat staging whose attacker is King
//                   Arthur with a BOOST on the attack (ВР-FX10, the AU-S5 rule) - FS09CombatStageInput::bAbilityBoost.
//                   The socket and the system are the hero's field of the S08CueFx registry (Weapon / Root).
//   FX-30 vortex    NS_FX_MedusaVortex on Medusa's root: SM_FX_VortexRings - two horizontal quads at 0.45 and 0.7 of
//                   the figure height (1.4 H and 1.12 H across, the upper one mirrored: the rings turn against each
//                   other), the FX-29 flipbook 4 x 4 (16 frames x 37.5 ms by the particle age, depth test on); the
//                   yaw turns the frame-12 flash sector to the camera (ВР-VS2-FX29-08); not scaled by the speed;
//                   staged by FS09AbilityStage (S09/S09AbilityStage.h).
//   FX-32 arc       NS_FX_ArthurArc at the Weapon socket: one camera quad, the FX-31 flipbook 4 x 4 (frames 0-11,
//                   33.3 ms) around the pivot (147.2, 164.0) of the cell on the hand, cell = 1.4457 H (ВР-VS2-FX31-01),
//                   tilted with the blade's screen axis (+-45 deg), no depth test, sort priority 30; 400 ms x speed
//                   (component time dilation 1 / speed), speed "none" and reduced motion: no arc.
#pragma once

#include "CoreMinimal.h"
#include "../S08HeroesV2.h"
#include "../S08Team.h"
#include "UObject/WeakObjectPtr.h"

class UNiagaraComponent;

namespace S08AbilityFx {

// ---- FX-26 / FX-27: the embers of the ash death
inline constexpr double EmbersLifeMs = 600.0;     // ВР-13: the system from the dissolve start
inline constexpr int32 EmbersPer100Ms = 8;
inline constexpr int32 MaxEmbers = 40;
inline constexpr float EmberCylinderRel = 0.35f;  // of the figure height
inline constexpr float EmbersTopMarginUU = 44.0f; // rise 40..80 uu/s x <= 0.4 s above the figure top
inline constexpr float EmbersBaseMarginUU = 6.0f; // below the pedestal
/** The user parameters of NS_FX_AshEmbers bound to MI_FX_Ember (ВР-VS6-23). */
inline const TCHAR* const FrontHeightParam = TEXT("FrontHeight");
inline const TCHAR* const TeamColorParam = TEXT("TeamScreenColor");
inline const TCHAR* const DissolveMsParam = TEXT("DissolveMs");

/** 8 embers per 100 ms of the dissolve, at most 40 (hero 500 ms -> 40, sidekick 400 ms -> 32). */
UNMATCHED_API int32 EmberCount(float DissolveSeconds);
/** The quad side: the figure height + the margins (the quad's bottom edge sits EmbersBaseMarginUU below the base). */
UNMATCHED_API float EmbersQuadSideUU(float FigureHeightUU);
/** A camera quad over the figure (base at Base, height H) moved RadiusUU towards the camera, so the chips draw in
 *  front of the dissolving body with the depth test on. */
UNMATCHED_API FTransform EmbersQuad(const FVector& Base, float FigureHeightUU, float RadiusUU, const FVector& Camera);
enum class EEmbersSkip : uint8 { None, Fade, Reduced, Legacy, NoMaterial };
/** FX-26 states: ash + the dissolve MIC + FX on + no reduced motion spawn; else the reason. */
UNMATCHED_API EEmbersSkip EmbersDecision(S08HeroesV2::EDissolveStyle Style, bool bHasDissolveMic, bool bFxEnabled,
                                         bool bReducedMotion);
UNMATCHED_API const TCHAR* EmbersSkipName(EEmbersSkip Skip);
/** The chip body of the figure's look: team.p1.screen / team.p2.screen (FromSRGBColor, AD-OPEN-39). */
UNMATCHED_API FLinearColor EmberTeamColor(ES08TeamSlot Look);

// ---- FX-28: the hero of an ability
/** The look-dev key of a fighter name (S08HeroesV2::Specs: KingArthur, Merlin, Medusa, Harpy) or "". */
UNMATCHED_API FString HeroKeyOfName(const FString& FighterName);
/** The pending id prefix of Medusa's TARGET_FIGHTER ability (backend generic-hero-ability.handler.ts). */
inline const TCHAR* const MedusaPendingPrefix = TEXT("ability-medusa-target");
/** ВР-FX10: the CUE-014 of King Arthur - his attack carries a boost (the revealed boost cards, AU-S5's rule). */
UNMATCHED_API bool IsArthurAbilityBoost(const FString& AttackerName, int32 BoostCount);

// ---- FX-32: Arthur's arc
inline constexpr double ArcLifeMs = 400.0;
inline constexpr float ArcCellRel = 256.0f * 0.5f / 88.54f;  // ВР-VS2-FX31-01: the cell is 1.4457 x the figure height
inline constexpr float ArcQuadCells = 1.75f;   // the pivot-centred quad covers the whole cell up to a 45 deg tilt
inline constexpr float ArcMaxTiltDeg = 45.0f;
inline constexpr int32 ArcSortPriority = 30;   // S08CueFx::TranslucentSortPriority + 10 (the card's "+10")
inline const TCHAR* const ArcTiltParam = TEXT("ArcTilt");
/** The screen tilt (deg, clockwise from up) of the blade axis at SocketLocation seen from Camera; the axis is folded
 *  to point up (it is an axis, not a direction) and clamped to +-ArcMaxTiltDeg. */
UNMATCHED_API float ArcTiltDeg(const FVector& SocketLocation, const FVector& BladeAxis, const FVector& Camera);
/** The camera quad of the arc centred on the socket (the cell pivot on the hand): side = ArcQuadCells x cell. */
UNMATCHED_API FTransform ArcQuad(const FVector& SocketLocation, float FigureHeightUU, const FVector& Camera);
/** The component time dilation of the arc: 1 / speed (fast 2, slow 0.67); 0 for speed "none" (no arc). */
UNMATCHED_API float ArcTimeDilation(float SpeedMul);

// ---- FX-30: Medusa's vortex
inline constexpr double VortexLifeMs = 600.0;
inline constexpr float VortexMeshHeightUU = 100.0f;  // SM_FX_VortexRings is authored for a 100 uu figure
/** The texture angle of the frame-12 flash sector (FX-29: 300 deg clockwise in the PNG, y down) in the mesh's local
 *  yaw (the mesh maps PNG right to local +Y and PNG down to local -X): +30 deg from +X. */
inline constexpr float VortexFlashLocalYawDeg = 30.0f;
/** The vortex transform: the figure base, uniform scale H / 100, the yaw that turns the flash sector to the camera. */
UNMATCHED_API FTransform VortexTransform(const FVector& Base, float FigureHeightUU, const FVector& Camera);

/** The ARTLOOK field: abilityFx=on|legacy(-S08FxLegacy). */
UNMATCHED_API FString LookField();

}  // namespace S08AbilityFx

/** The adapter state of the death / ability FX (owned by AS08FlowGameMode). */
struct UNMATCHED_API FS08AbilityFxState {
  /** FX-26 / FX-27: the embers of each dissolving figure (FrontHeight is written every frame of its dissolve). */
  TMap<FString, TWeakObjectPtr<UNiagaraComponent>> Embers;
  /** The figures that dissolved in the previous frame (a new dissolve = a rising edge). */
  TSet<FString> WasDissolving;
  /** -BenchFx ability modes (spawned at the end of the warm-up, frozen at their ms; bench only). */
  struct FBenchSpawn {
    FString Mode;       // ash | vortex | arc
    FString FighterId;
    double Ms = 0.0;
  };
  TArray<FBenchSpawn> Bench;
  bool bBenchSpawned = false;
  void Reset() { *this = FS08AbilityFxState(); }
};

// VS-6 F2 (visual chat; docs/game-design/visual/06-tasks/vfx.csv FX-21..FX-25, icons.csv IC-49; 02-visual-design.md §9.2
// CUE-011 / CUE-012, ВР-20, ВР-21, ВР-63, ВР-67): the combat FX of a figure - the world-free numbers of the cards and the
// adapter state of AS08FlowGameMode (S08FlowGameModeCombatFx.cpp).
//
//   FX-21 hit star   NS_FX_HitStar, one camera-facing quad at the contact point (ВР-FX04: the target's centre at 0.6 of
//                    the figure height, 0.4 of its capsule radius towards the attacker; no attacker - no shift), the
//                    star's diameter 0.8 x the figure height (the FX-20 star fills 80 % of its cell, so the quad side is
//                    the figure height), C+70 .. C+340, not scaled by the speed; damage 0 / reduced motion / a cut /
//                    -S08FxLegacy: no star; a cascade of one frame: one star per target.
//   FX-22 numbers    «−N» / «+N» in a card.navy capsule over the figure (UI/UmWorldDamage.h): scale 0.8 -> 1 over 80 ms,
//                    a 24 su ease-out rise over the life, opacity -> 0 over the last 150 ms; «−N» 900 ms x speed (F-04),
//                    «+N» 700 ms; reduced motion: no rise, no scale, 450 ms, the last 100 ms opacity only.
//   FX-23 assembly   one contact frame C: flash 0-70 (FX-19), «−N» +60, star +70, rim 70-370, HP +80; damage 0 (the Block
//                    event of the staging): the cream rim 300 ms only (ВР-FX05, «обод = защита»).
//   FX-24 heal motes NS_FX_HealMotes, one camera-facing quad at the base (side 0.8 H + 16, the base 6 uu above its
//                    bottom edge), the motes drawn by M_FX_FigurePrint mode 1.
//   FX-25 heal       CUE-012 when the applied snapshot raised the HP of a living fighter (ВР-FX13): in a combat - at the
//                    end of its staging (stage=end), otherwise the snapshot frame + 200 ms; N = HP after - HP before.
//
// Rollbacks: -S08FxLegacy (no star, no motes; the numbers stay), -S08HitTintLegacy (the red fill, FX-19),
// -S08SlateHud=damage (the old 18 su #161A28 number, ВР-H15), -S08FigureCueLegacy (ВР-VS6-14: the flash and the fresnel
// rim inside M_UM_Figure_v2 instead of the M_FX_FigureCue overlay).
#pragma once

#include "CoreMinimal.h"
#include "UObject/WeakObjectPtr.h"

class UNiagaraComponent;

namespace S08CombatFx {

// ---- FX-21
inline constexpr double StarDelayMs = 70.0;    // C+70: after the white flash (ВР-20, ВР-FX06)
inline constexpr double StarLifeMs = 270.0;    // 8 frames x 33.3 ms
inline constexpr float StarHeightRel = 0.6f;   // ВР-FX04
inline constexpr float StarTowardRel = 0.4f;
inline constexpr float StarDiameterRel = 0.8f; // of the figure height
inline constexpr float StarCellFill = 0.8f;    // the FX-20 star spans 80 % of its 256 px cell
/** The plane mesh of the quad carriers (100 x 100 uu, ВР-VS6-06). */
inline constexpr float PlaneUU = 100.0f;

/** ВР-FX04: the contact point of a hit - the target's centre (base + up x 0.6 H) moved 0.4 R towards the attacker
 *  (horizontally); without an attacker (an ability, exhaustion) no shift. */
UNMATCHED_API FVector StarPoint(const FVector& TargetBase, float FigureHeightUU, float RadiusUU, const FVector* AttackerBase);
/** The quad side of the star: diameter 0.8 H / the 80 % fill = H (never below 20 uu). */
UNMATCHED_API float StarQuadSideUU(float FigureHeightUU);
/** A quad of the engine plane (normal +Z) at Centre, its normal towards the camera, SideUU on each side. */
UNMATCHED_API FTransform CameraQuad(const FVector& Centre, const FVector& CameraLocation, float SideUU);
/** The in-plane "screen up" of a camera quad (world up without its component along the view). */
UNMATCHED_API FVector CameraQuadUp(const FVector& Centre, const FVector& CameraLocation);

// ---- FX-24
inline constexpr double HealMotesLifeMs = 600.0;
/** The quad side of the motes: 0.8 H of rise + 16 uu of margin. */
UNMATCHED_API float HealQuadSideUU(float FigureHeightUU);
/** The quad centre: the base point sits 6 uu above the quad's bottom edge (M_FX_FigurePrint mode 1). */
UNMATCHED_API FVector HealQuadCentre(const FVector& Base, const FVector& CameraLocation, float SideUU);

// ---- FX-22
inline constexpr float NumberRiseSu = 24.0f;
inline constexpr float NumberStackSu = 28.0f;  // a newer number of the same fighter sits 28 su above the older one
inline constexpr double NumberScaleInMs = 80.0;
inline constexpr float NumberScaleFrom = 0.8f;
inline constexpr double NumberFadeMs = 150.0;
inline constexpr double NumberReducedFadeMs = 100.0;
inline constexpr int32 HealNumberMs = 700;     // CUE-012 (02 §9.2)
inline constexpr int32 ReducedNumberMs = 450;  // 04 §3.5
inline constexpr int32 MaxNumbers = 4;         // the card's budget: <= 4 numbers at once
struct FNumberPose {
  float Scale = 1.0f;
  float RiseSu = 0.0f;
  float Opacity = 0.0f;
};
/** The pose of a number at Ms of its LifeMs (0 opacity outside the life). */
UNMATCHED_API FNumberPose NumberPose(double Ms, double LifeMs, bool bReduced);
/** The life of a «+N» (700, reduced 450) and of a «−N» (the given 900 x speed, reduced 450). */
UNMATCHED_API int32 NumberLifeMs(bool bHeal, int32 DamageLifeMs, bool bReduced);

// ---- FX-25
inline constexpr int32 HealDelayMs = 200;      // CUE-012 feedback_delay_ms (out of a combat)
/** ВР-FX13: the heal of a transition - HP after - HP before of a fighter alive before and after (a revive is no heal). */
UNMATCHED_API int32 HealAmount(int32 HpBefore, int32 HpAfter, bool bAliveBefore, bool bAliveAfter);

// ---- ВР-VS6-14 rollback
inline const TCHAR* const FigureCueLegacyFlagName = TEXT("S08FigureCueLegacy");
UNMATCHED_API bool FigureCueLegacy();
/** The ARTLOOK field: combatFx=on|legacy(-S08FxLegacy) figureCue=overlay|legacy(-S08FigureCueLegacy). */
UNMATCHED_API FString LookField();

}  // namespace S08CombatFx

/** The adapter state of the combat FX (owned by AS08FlowGameMode). */
struct UNMATCHED_API FS08CombatFxState {
  struct FPendingStar {
    FString TargetId;
    FString AttackerId;
    int32 Seq = -1;
    double AtMs = 0.0;
  };
  struct FPendingHeal {
    FString FighterId;
    int32 Amount = 0;
    int32 Seq = -1;
    double AtMs = 0.0;
  };
  TArray<FPendingStar> Stars;
  TArray<FPendingHeal> Heals;
  /** One star per target per frame (a cascade of one frame, CMB-HIT-MULTI). */
  TMap<FString, uint64> StarFrame;
  /** The stars and motes in flight (the capture hook pauses them). */
  TArray<TWeakObjectPtr<UNiagaraComponent>> LiveSystems;
  // ---- the FX capture hook (-S08FxShots or -S08ExitShots with -S09ShotDir): one LIVE frame per effect at its moment
  struct FShot {
    FString Leaf;       // s09-fx19-flash.png ...
    FString FighterId;  // whose channels hold
    double AtMs = 0.0;  // game clock
    // ВР-VC-12: the effect's own clock - the frame waits for this system's age (paused while another frame holds)
    TWeakObjectPtr<UNiagaraComponent> System;
    float AgeS = -1.0f;
    // ВР-VC-12: or the figure's own channel - 1 flash / 2 rim - must reach ChannelMin (the flash / the rim peak)
    uint8 Channel = 0;
    float ChannelMin = -1.0f;
  };
  TArray<FShot> Shots;            // planned
  TSet<FString> ShotsTaken;       // leaves planned or taken (one each)
  int32 StagedHits = 0;           // the n-th staged hit picks its frame (1st flash, 2nd star)
  FShot Holding;                  // the shot in flight (Leaf empty = none)
  uint64 HoldFrame = 0;
  double HoldSinceS = 0.0;
  uint64 TickFrame = 0;           // ВР-VC-12: the game clock of the previous frame's tick (a shot due by then is late)
  double TickMs = -1.0;
  double PrevTickMs = -1.0;
  void Reset() { *this = FS08CombatFxState(); }
};

namespace S08CombatFx {
/** -S08FxShots (or -S08ExitShots): the capture hook of FX-17 / FX-19 / FX-21 / FX-25 (needs -S09ShotDir). */
UNMATCHED_API bool FxShotsRequested();
/** The planned moments (ms after the effect's event): FX-19 flash C+20, FX-21 star C+137, FX-17 rim t0 = event + 150,
 *  peak +120, FX-25 motes show + 200. */
inline constexpr double ShotFlashMs = 20.0;
inline constexpr double ShotStarMs = 137.0;
inline constexpr double ShotDefenseMs = 270.0;
inline constexpr double ShotHealMs = 200.0;
/** ВР-VC-12 (ВР-VS6-56): what the hook does with a planned frame this tick. A frame bound to its system (AgeS >= 0,
 *  the system alive) waits for the system's own age - TargetAgeS - (an earlier held frame pauses every live system, so
 *  the age stops with it) and is skipped when the age overshot it by more than a frame (1.5 x FrameS, 34..100 ms); it
 *  is taken anyway ShotAgeWaitMaxMs after its clock moment. A frame on a figure channel (ChannelMin >= 0: the flash
 *  a = 1, the defence rim at its peak - the channel runs on the actor's world clock, which a screenshot hitch puts
 *  behind the game clock) waits from its clock moment until the channel reaches ChannelMin, and is skipped
 *  ShotAgeWaitMaxMs later. A frame on the game clock alone is skipped when it was due already at the previous frame's
 *  tick (it waited behind another held frame). A skipped leaf is planned again by the next event of its kind. */
enum class EShotDecision : uint8 { Wait, Take, Skip };
inline constexpr double ShotAgeWaitMaxMs = 500.0;
UNMATCHED_API EShotDecision ShotDecision(double NowMs, double AtMs, double PrevTickMs, float AgeS, float TargetAgeS,
                                         float FrameS, float Channel = -1.0f, float ChannelMin = -1.0f);
/** ВР-VC-15: the -BenchFx stager honours reduced motion as the live game does - star, heal motes, vortex, arc and dust
 *  are not spawned (the chevrons run to their end state, S08FieldFx::BenchChevronMs; ash follows DissolveStyle). */
UNMATCHED_API bool BenchSkipsUnderReducedMotion(const FString& Mode);
}  // namespace S08CombatFx

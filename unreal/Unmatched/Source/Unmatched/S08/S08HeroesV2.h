// Wave 5c-B: the look-dev C heroes (rig v2 UM_HUMANOID_17_v2, M_UM_Figure_v2.1 with
// TeamAccent) on the live S08 board. ART-DEFAULT (2026-10-04, S08ArtLook.h): they are the DEFAULT figures of every
// art board; the former opt-in flag -ArtPreviewHeroesV2 is a no-op alias. Rollback: -S08HeroesLegacy (or the
// -ArtPreview -ArtPreviewAllMedusa review) - nothing here is consulted then and the figures are byte-for-byte the
// previous ones (the isolated Medusa candidate, the ART-003 grey blockouts). The grey board (-S08GreyBoard, or a
// board without a registered art profile) never maps a figure.
//
// One place for the whole mapping (world-free, automation-tested in
// S08HeroesV2Tests.cpp):
//   * fighter name -> skeletal mesh, pedestal, body/pedestal MI by the team LOOK
//     (P1 -> *_P1, P2 -> *_P2), four H2Anim clips and the canonical skeleton;
//   * facing: rig v2 looks along +X (UM_FBX_v1, RIG-CONTRACT.md §5), the legacy
//     candidate along +Y; FacingYawOffsetDeg (+90) turns a v2 figure to the same
//     world direction as the legacy figure on the same cell;
//   * scale: visible figure height normalised to the per-hero height budget;
//   * clip selection per combat event (Idle loop with a per-fighter phase,
//     LungeAttack, HitReact, DeathSettle holds its final pose).
// Traces: "ARTPREVIEW heroesV2 fighter=<id> mesh=<path> mi=<path> yaw=<deg> scale=<k> ..."
// and "ARTPREVIEW anim fighter=<id> clip=<name> len=<s> ...".
#pragma once

#include "CoreMinimal.h"
#include "S08Team.h"

class UAnimSequenceBase;
class UPrimitiveComponent;

namespace S08HeroesV2 {

/** Rollback flag (ART-DEFAULT): -S08HeroesLegacy keeps the pre-default figures (Medusa candidate, ART-003 blockouts). */
inline const TCHAR* const LegacyFlagName = TEXT("S08HeroesLegacy");
/** The former opt-in flag -ArtPreviewHeroesV2: still accepted (scripts pass it), a no-op - v2 is the default. */
inline const TCHAR* const FlagName = TEXT("ArtPreviewHeroesV2");

/** World-free rule: v2 figures unless the rollback flag, or the six-Medusa review (-ArtPreview -ArtPreviewAllMedusa)
 *  that asks for the Medusa candidate on every fighter. */
constexpr bool Decide(bool bLegacyFlag, bool bAllMedusaReview) { return !bLegacyFlag && !bAllMedusaReview; }

/** True when the v2 figures are on: by default; false with -S08HeroesLegacy or -ArtPreview -ArtPreviewAllMedusa (or
 *  the automation override). (The name is the opt-in one: it read -ArtPreviewHeroesV2 before ART-DEFAULT.) */
UNMATCHED_API bool FlagEnabled();
/** True when -S08HeroesLegacy is on the command line (the trace names the reason of a legacy run). */
UNMATCHED_API bool LegacyRequested();
/** Automation tests only: force the flag on/off (Reset -> read the command line again). */
UNMATCHED_API void SetFlagOverrideForTest(bool bEnabled);
UNMATCHED_API void ResetFlagOverrideForTest();

/** Rig v2 faces +X at yaw 0; the legacy candidate (and the S08 cell yaw 0/180) faces +Y.
 *  FRotator(0, LegacyYaw + 90, 0) maps +X onto the direction FRotator(0, LegacyYaw, 0) maps +Y to.
 *  (anim-v2-decisions (6) wrote "-90"; the sign is +90 - proven by FS08HeroesV2FacingTest.) */
constexpr float FacingYawOffsetDeg = 90.0f;

// ---- DE-019 (W-16, 01 F-09): death by stages from the contact frame, one scheme for all six v2 figures.
//   HitReact + red tint 0-450 (the combat staging, S09CombatStage.h) -> DeathSettle 450-1325 (the clip, 875 ms) ->
//   still (hero 300, sidekick 0) -> dissolve (hero 500, sidekick 400; DE-011 below) -> gone (hero ~2125, sidekick
//   ~1725 from the contact). The old grey-slice hold (DeathSettle + 2.0 s, then an instant hide) is gone.
/** After DeathSettle ends the final pose stays still this long before the dissolve: hero 0.3 s, sidekick 0. */
constexpr float DeathStillSecondsHero = 0.3f;
constexpr float DeathStillSecondsSidekick = 0.0f;
/** The death plan of one figure from its fall (the start of DeathSettle), in seconds. Settle = the DeathSettle play
 *  length (0 without the clip); Dissolve = 0 when the dissolve MIC is missing (cue-table CUE-013 fallback: the figure
 *  hides at once when the still ends). */
struct FDeathPlan {
  float SettleSeconds = 0.0f;
  float StillSeconds = 0.0f;
  float DissolveSeconds = 0.0f;
  float DissolveStartSeconds() const { return SettleSeconds + StillSeconds; }
  float GoneSeconds() const { return SettleSeconds + StillSeconds + DissolveSeconds; }
};

enum class EClip : uint8 { None, Idle, LungeAttack, HitReact, DeathSettle };
constexpr int32 ClipCount = 5;
enum class EEvent : uint8 { Spawn, Attack, Damaged, Defeated, ClipFinished };

UNMATCHED_API const TCHAR* ClipName(EClip Clip);
UNMATCHED_API const TCHAR* EventName(EEvent Event);
/** Only Idle loops; LungeAttack / HitReact return to Idle; DeathSettle holds its last frame. */
inline bool ClipLoops(EClip Clip) { return Clip == EClip::Idle; }

/** Clip to play after Event while Current plays. bRestart = (re)start the clip now.
 *  A defeated fighter stays in DeathSettle whatever arrives later (a late damage cue of the
 *  killing blow, an attack event of the same snapshot). */
struct FClipChoice {
  EClip Clip = EClip::None;
  bool bRestart = false;
};
UNMATCHED_API FClipChoice NextClip(EClip Current, EEvent Event);

/** Deterministic Idle phase in [0, 1) from the fighter id (FNV-1a 32 over the characters,
 *  mod 10000): three Harpies do not breathe in sync, and a rerun gives the same phase. */
UNMATCHED_API float IdlePhase(const FString& FighterId);

/** Legacy S08 figure yaw on a cell: the board's negative-Y side faces +Y (0), the far side -Y (180). */
inline float LegacyFigureYawDeg(double CellY) { return CellY < 0.0 ? 0.0f : 180.0f; }
/** Yaw of a rig v2 figure on the same cell (same world facing as the legacy figure). */
inline float FigureYawDeg(double CellY) { return LegacyFigureYawDeg(CellY) + FacingYawOffsetDeg; }

struct FHeroSpec {
  const TCHAR* FighterName;  // FS08BoardFighter::Name (server data), case-insensitive
  const TCHAR* Key;          // asset key: KingArthur / Merlin / Medusa / Harpy
  const TCHAR* Stage;        // H2LD / H3LD (look-dev C folder)
  bool bHero;                // hero (true) or sidekick
  // Height budget (uu): the build profile figure_height_m (art/pipeline-candidates/ASSET-*/build-profiles/
  // *-ue-import.json), inside the card range of 17 §4.2 (BudgetMinUU..BudgetMaxUU, proposal until GD-058).
  float BudgetUU;
  float BudgetMinUU;
  float BudgetMaxUU;
  // Measured in UE (look-dev C reports, docs/art-pipeline/<hero>-lookdev-v2.md "UE (look-dev C)"):
  // top of the FIGURE above the pedestal bottom (crown / hood / head, not the weapon)
  float FigureTopUU;
  // and the imported skeletal bounds top (sword tip of Arthur, staff crystal of Merlin).
  float BoundsTopUU;
  float IdleSeconds;  // AM_<Key>_Idle play length (anim-v2 decisions (4))
  // DE-010 (01 F-03): contact frame of AM_<Key>_LungeAttack at ClipFps, from the clip build profile
  // (art/pipeline-candidates/ASSET-*/build-profiles/*-h2anim.json): Arthur's chop k.7, Merlin's staff thrust k.8,
  // Medusa's arrow release k.8, the Harpy's claw strike k.7 (its strike window is k.7-9: contact = first frame).
  int32 LungeContactFrame;
};

/** The four look-dev C heroes (King Arthur, Merlin, Medusa, Harpies). */
UNMATCHED_API const TArray<FHeroSpec>& Specs();
/** Spec for a fighter name, or nullptr (unmapped hero / v2 off / no art board: the grey board or a board without a
 *  registered profile - bArtBoard is the board actor's bArtActive). */
UNMATCHED_API const FHeroSpec* Find(bool bArtBoard, bool bHeroesV2, const FString& FighterName);

/** Scale that brings the measured figure top to the budget: BudgetUU / FigureTopUU, clamped to [0.5, 2]. */
UNMATCHED_API float FigureScale(const FHeroSpec& Spec);

// Asset paths (object paths without the ".Name" suffix, as LoadObject takes them).
UNMATCHED_API FString MeshPath(const FHeroSpec& Spec);
UNMATCHED_API FString PedestalPath(const FHeroSpec& Spec);
UNMATCHED_API FString BodyMaterialPath(const FHeroSpec& Spec, ES08TeamSlot Look);
UNMATCHED_API FString PedestalMaterialPath(const FHeroSpec& Spec, ES08TeamSlot Look);
UNMATCHED_API FString SkeletonPath(const FHeroSpec& Spec);
/** /Game/PipelineCandidates/<Key>/H2Anim/AM_<Key>_<Clip>; empty for EClip::None. */
UNMATCHED_API FString ClipPath(const FHeroSpec& Spec, EClip Clip);
/** Expected play length of a clip (s): Idle per hero, LungeAttack 0.583, HitReact 0.417, DeathSettle 0.875. */
UNMATCHED_API float ExpectedClipSeconds(const FHeroSpec& Spec, EClip Clip);

// ---- DE-010 (W-26, 01 F-03): the contact frame of LungeAttack and the hit tint of the figure material.
/** Frame rate of the H2Anim clips (build profiles "fps"). */
constexpr float ClipFps = 24.0f;
/** Event name of the contact notify in every LungeAttack (US08ContactAnimNotify). */
inline const TCHAR* const ContactNotifyName = TEXT("Contact");
/** Contact time of the build profile (s): LungeContactFrame / ClipFps - the fallback when a clip has no notify. */
UNMATCHED_API float ProfileContactSeconds(const FHeroSpec& Spec);
/** Trigger time (s) of the first "Contact" notify of Anim, or a negative value (no clip, no notify). */
UNMATCHED_API float NotifyContactSeconds(const UAnimSequenceBase* Anim);
/** Contact time of a LungeAttack: the notify when the clip has one, otherwise the profile frame. */
UNMATCHED_API float ContactSeconds(const FHeroSpec& Spec, const UAnimSequenceBase* LungeAttack);

/** Custom Primitive Data slot of the hit tint in M_UM_Figure_v2 (v2.2, DE-010): scalar CPD_HitTint, 0 = off (the
 *  figure renders exactly as without it), 1 = full red fill (HitTintColor x HitTintStrength on the albedo plus
 *  HitTintEmissive). The v1 slots 0-11 (art/um-materials/um-masters.json) are unchanged. Driven by CUE-011 (DE-018):
 *  450 ms from the contact frame, 550 ms when lethal. */
constexpr int32 HitTintCpdIndex = 12;
inline const TCHAR* const HitTintParamName = TEXT("CPD_HitTint");

// ---- DE-011 (W-27, 01 F-09): the death dissolve of the v2 figures (tools/art/de011/de011.py).
// M_UM_Figure_v2 v2.3 has a static switch UseDissolve, off in every hero MI: the accepted figures stay Opaque and
// compile the v2.2 graph unchanged. One dissolve MIC per body MI (/Game/UM/Materials/v2/Dissolve/MI_<Key>_<Stage>_
// <Look>_Dissolve) is a child of that MI (textures, knobs and static switches inherited) with UseDissolve on and the
// blend mode overridden to Masked. A dying figure swaps its body slots to it (DE-019) and drives the progress by CPD.
/** Static switch of M_UM_Figure_v2 that compiles the dissolve (default off). */
inline const TCHAR* const DissolveSwitchName = TEXT("UseDissolve");
/** CPD slots read only by the dissolve permutation: progress 0..1 (0 = the whole figure, exactly its MI look; 1 =
 *  every pixel clipped) and style (EDissolveStyle). 0 is neutral in both. */
constexpr int32 DissolveCpdIndex = 13;
constexpr int32 DissolveStyleCpdIndex = 14;
inline const TCHAR* const DissolveParamName = TEXT("CPD_Dissolve");
inline const TCHAR* const DissolveStyleParamName = TEXT("CPD_DissolveStyle");
/** The pedestal (M_UM_BaseMarker, v1, Opaque) has no dissolve: its v1 slot CPD_Fade greys it out with the same
 *  progress, and the caller hides it with the figure at the end. */
constexpr int32 PedestalFadeCpdIndex = 11;
/** 01 F-09: the dissolve takes 500 ms for a hero (Arthur, Medusa) and 400 ms for a sidekick (Merlin, Harpies). */
constexpr float DissolveSecondsHero = 0.5f;
constexpr float DissolveSecondsSidekick = 0.4f;
inline float DissolveSeconds(const FHeroSpec& Spec) { return Spec.bHero ? DissolveSecondsHero : DissolveSecondsSidekick; }
inline float DeathStillSeconds(const FHeroSpec& Spec) {
  return Spec.bHero ? DeathStillSecondsHero : DeathStillSecondsSidekick;
}
/** DE-019: the plan of a v2 figure (F-09). SettleSeconds = the loaded DeathSettle length (0 without the clip),
 *  bDissolveMaterial = the dissolve MIC loaded. */
inline FDeathPlan MakeDeathPlan(const FHeroSpec& Spec, float SettleSeconds, bool bDissolveMaterial) {
  FDeathPlan Plan;
  Plan.SettleSeconds = FMath::Max(0.0f, SettleSeconds);
  Plan.StillSeconds = DeathStillSeconds(Spec);
  Plan.DissolveSeconds = bDissolveMaterial ? DissolveSeconds(Spec) : 0.0f;
  return Plan;
}
/** Dissolve progress 0..1 at T seconds after the fall (0 before the dissolve, 1 once the figure is gone). */
UNMATCHED_API float DissolveProgressAt(const FDeathPlan& Plan, float SecondsSinceFall);

/** Fade = screen-space dither that TSR resolves into a smooth fade: the default and the reduced-motion style.
 *  Ash = the figure burns away from the feet up with a team-colour (C-11) glowing front: a candidate for the A/B
 *  sheet (DE-028) until the user accepts it, shown only with -S08DissolveAsh. */
enum class EDissolveStyle : uint8 { Fade = 0, Ash = 1 };
inline const TCHAR* const DissolveAshFlagName = TEXT("S08DissolveAsh");
/** World-free rule: the ash candidate only on request and never under reduced motion. */
constexpr EDissolveStyle DecideDissolveStyle(bool bAshFlag, bool bReducedMotion) {
  return bAshFlag && !bReducedMotion ? EDissolveStyle::Ash : EDissolveStyle::Fade;
}
/** DecideDissolveStyle with -S08DissolveAsh from the command line and S08IconMotion::IsReducedMotion(). */
UNMATCHED_API EDissolveStyle DissolveStyle();
UNMATCHED_API const TCHAR* DissolveStyleName(EDissolveStyle Style);
/** /Game/UM/Materials/v2/Dissolve/MI_<Key>_<Stage>_<Look>_Dissolve (the dissolve MIC of BodyMaterialPath). */
UNMATCHED_API FString DissolveMaterialPath(const FHeroSpec& Spec, ES08TeamSlot Look);
/** One dissolve frame: CPD_Dissolve = Progress (clamped to 0..1) and CPD_DissolveStyle on Body, CPD_Fade = Progress on
 *  Pedestal. Either component may be null. Body must already carry the dissolve MIC (on a hero MI the slots are not
 *  compiled and nothing changes). */
UNMATCHED_API void SetDissolve(UPrimitiveComponent* Body, UPrimitiveComponent* Pedestal, float Progress,
                               EDissolveStyle Style);

/** DE-019 G-COST bench (render_bench.py *-dissolve-* variants): -Bench -BenchDissolve=<progress 0..1> freezes every
 *  living v2 figure at that dissolve progress (the dissolve MIC, style by DissolveStyle()) - a worst case of six
 *  dissolving figures for the pass cost. Negative = off (no -Bench, no -BenchDissolve, or an unparsable value). */
inline const TCHAR* const BenchDissolveParamName = TEXT("BenchDissolve=");
UNMATCHED_API float BenchDissolveProgress();

// ---- AN-17 (ВР-17): the clip-pose stand -Bench -BenchClipPose=<Clip>@<f1>,<f2>[;<Clip>@...] ----
// Review tooling only (no game-path effect): the bench walks every pose x every -BenchViews view with every living v2
// figure frozen at that pose (SetPosition + SetPlaying(false)), so any frame of any D-11 clip can be sheeted on the
// real maps. A frame is a plain number (frame at ClipFps) or "q<pct>" - a percent of the clip length, resolved per
// hero (the Idle lengths differ; the q25 frame is 15 on Arthur's 2.5 s and 18 on Merlin's 3.0 s).
inline const TCHAR* const BenchClipPoseParamName = TEXT("BenchClipPose=");
/** -BenchClipPoseFighter=<KingArthur|Merlin|Medusa|Harpy|id> (Harpy = the first harpy): the K2 views focus this
 *  fighter, like -BenchMovePoseFighter; without the parameter the bench's own hero. */
inline const TCHAR* const BenchClipPoseFighterParamName = TEXT("BenchClipPoseFighter=");
/** One pose of the parsed list, still unresolved (q resolves against the hero's clip length). */
struct FBenchClipPoseSpec {
  EClip Clip = EClip::None;
  bool bQuarter = false;  // q<pct> (a percent of the clip) instead of a frame number
  int32 Value = 0;        // frame index at ClipFps, or the percent 0..100
};
/** Parses "<Clip>@<f1>,<f2>[;<Clip>@...]": Clip in Idle | LungeAttack | HitReact | DeathSettle, frames >= 0,
 *  q percents 0..100. False (OutError, Out empty) on any other token - the bench then runs without poses. */
UNMATCHED_API bool ParseBenchClipPoses(const FString& Text, TArray<FBenchClipPoseSpec>& Out, FString& OutError);
/** The pose time (s) of a spec against one figure's clip length: frame / ClipFps, or pct% of the clip. */
UNMATCHED_API double BenchClipPoseSeconds(const FBenchClipPoseSpec& Spec, double ClipSeconds);

}  // namespace S08HeroesV2

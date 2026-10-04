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

/** After DeathSettle ends the final pose is held this long, then the defeated fighter is hidden
 *  like every other defeated fighter (grey slice: instant hide). */
constexpr float DeathHoldSeconds = 2.0f;

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

}  // namespace S08HeroesV2

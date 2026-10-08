// AN-23 / AN-24 / AN-25 (ВР-06, 02-visual-design.md §8.3): the facing of the figures - world-free rules, no engine
// types beyond math, automation-tested in S08FacingTests.cpp.
//   * rest (AN-23): a figure stands three-quarter to the local player camera - its face never further than
//     MaxIdleOffDeg from the camera axis - with the facing offset towards the nearest living enemy, so the player
//     sees who opposes whom; nobody stands back to the camera (the legacy half-field rule did, Р-11 GD-058).
//     ВР-AN01: "наклон к ближайшему врагу" of ВР-06 is this facing offset, not a body lean.
//   * attack (AN-24): before the lunge the attacker turns to the target in AttackTurnMs, clamped to
//     AttackMaxOffDeg from the camera axis (ВР-AN02: even mid-lunge never the back; the target does not turn).
//   * return (AN-25): after the lunge back to the rest angle in ReturnMs.
// The turns are shortest-arc, never scaled by the animation speed (ВР-AN03) and instant under reduced motion /
// speed "none" (the world side applies them). Rollback: -S08FacingLegacy keeps the half-field rule of S08HeroesV2
// (nothing here is consulted then). The draft wip/art012-facing-2026-10-04 is not used (ВР-06).
#pragma once

#include "CoreMinimal.h"

namespace S08Facing {

/** Rest: the largest angle between the figure's face and the direction to the camera. */
constexpr double MaxIdleOffDeg = 45.0;
/** Rest: a new angle within this band of the current one changes nothing (no twitch on repeated snapshots). */
constexpr double DeadBandDeg = 10.0;
/** Attack: the attacker may turn at most this far from the camera axis towards the target. */
constexpr double AttackMaxOffDeg = 90.0;
/** AN-24: the turn to the target inside the "score" pause before the lunge, ms. */
constexpr double AttackTurnMs = 120.0;
/** AN-23 / AN-25: a rest turn (spawn / snapshot / move end / after a lunge), ms. */
constexpr double ReturnMs = 150.0;
/** ВР-Z1R-05 (review F4): a rest / return change under this is no turn and no FACING line (the spawn line is always
 *  written). */
constexpr double MinTurnDeg = 0.5;
/** Rollback of this table: -S08FacingLegacy = the half-field rule of before ВР-06, no FACING traces. */
inline const TCHAR* const LegacyFlagName = TEXT("S08FacingLegacy");

/** True with -S08FacingLegacy on the command line (the ARTLOOK field names the reason of a legacy run). */
UNMATCHED_API bool LegacyRequested();

/** VC C1 (CLOSEOUT 2026-10-09 item 5, AN-33, ВР-VC-01): a per-hero cap of the rest offset. The K2 camera stands
 *  straight in front of the focused figure, so the 45 deg of K1 grow to ~59 there, and under the steep camera
 *  Medusa's snake crown then covers her face. Her rest offset towards the enemy is capped at MedusaRestMaxOffDeg:
 *  still three-quarter, still towards the enemy, never the back (ВР-06). Every other hero keeps MaxIdleOffDeg.
 *  The attack angle (AN-24) and the turn times (AN-23 / AN-25) are unchanged. */
constexpr double MedusaRestMaxOffDeg = 10.0;  // A/B 10 / 20 / 30 on Marmoreal K2: only 10 shows eyes, nose, mouth
/** Rollback of the per-hero cap: -S08FaceCapLegacy = every hero at MaxIdleOffDeg (the AN-23 rest of VS-8). */
inline const TCHAR* const FaceCapLegacyFlagName = TEXT("S08FaceCapLegacy");
/** Review A/B only: -S08FaceCapMedusa=<deg> (0..45) overrides MedusaRestMaxOffDeg. */
inline const TCHAR* const FaceCapMedusaParamName = TEXT("S08FaceCapMedusa=");
/** The rest offset cap of a v2 hero (S08HeroesV2::FHeroSpec::Key; nullptr / unknown -> MaxIdleOffDeg). */
UNMATCHED_API double RestMaxOffDeg(const TCHAR* HeroKey);
/** The ARTLOOK token: "medusa10" (the cap in force) or "legacy(-S08FaceCapLegacy)". */
UNMATCHED_API FString FaceCapLookField();

/** World yaw (deg, XY plane) of the From -> To direction; 0 when the points coincide. */
UNMATCHED_API double YawToward(const FVector& From, const FVector& To);

/** The rest angle (world yaw) of a figure at FigurePos: the camera axis plus the offset towards the nearest living
 *  enemy, clamped to +-MaxIdleOffDeg. Without a living enemy the figure keeps CurrentYawDeg (ВР-06: with one
 *  appearing it faces the camera axis). A wanted angle within DeadBandDeg of the current one keeps the current one -
 *  unless bApplyDeadBand is false (AN-25: the return after a lunge always reaches the rest angle). MaxOffDeg: the
 *  hero's cap (RestMaxOffDeg), clamped to 0..MaxIdleOffDeg. */
UNMATCHED_API double RestYaw(const FVector& FigurePos, const FVector& CameraPos, bool bHasEnemy,
                             const FVector& NearestEnemyPos, double CurrentYawDeg, bool bApplyDeadBand = true,
                             double MaxOffDeg = MaxIdleOffDeg);

/** AN-24: the attack angle (world yaw) of a figure at FigurePos towards TargetPos, clamped to +-AttackMaxOffDeg from
 *  the camera axis. */
UNMATCHED_API double AttackYaw(const FVector& FigurePos, const FVector& TargetPos, const FVector& CameraPos);

/** The yaw of a turn from FromYawDeg to ToYawDeg at blend Alpha (0..1): along the SHORTEST arc, wrapping through
 *  0/360. Every turn of the table (rest, attack, return) blends through this (the actor's timer drives Alpha). */
UNMATCHED_API double TurnYawAt(double FromYawDeg, double ToYawDeg, double Alpha);

}  // namespace S08Facing

// FX-03 (VS-6 Z-2): the world-free CUE->FX registry of the combat VFX base (CUE-DISPATCHER.md §3 rules, ВР-25).
//
// One row per CUE with a vfx block in docs/unreal/contracts/cue-dispatcher/cue-table.json: the planned system
// path, the effect type (NET_UM_Combat / NET_UM_Board), the attachment (world | socket), the sprite budget of
// ВР-25 and the prewarm flag. Unmatched.S08.CueFx.Registry compares this table with cue-table.json; the systems
// themselves are created by FX-13..FX-32 (the visual chat's VS-6), so until then every row's asset is missing
// and the spawner traces vfx=missing (the documented fallback state; the resolver keeps the name honest).
//
// Rollbacks (ВР-FX02): -S08FxLegacy turns every FX of these cards off (systems never spawn, the rim / flash
// writers do not run; vfx=none, the CUE rows stay); FX-19 adds -S08HitTintLegacy - the red fill of before
// instead of the white flash + cream rim. Both are in the ARTLOOK line (fx= / hitFx=).
//
// FX-04: every system of /Game/S08/FX/** runs deterministic on the CPU with RandomSeed = CRC32(asset name) &
// 0x7FFFFFFF (SeedOf below); tools/art/fx/fx_audit.py audits the assets, Unmatched.S08.CueFx.Determinism the
// runtime side.
#pragma once

#include "CoreMinimal.h"

namespace S08CueFx {

/** ВР-FX02: the one rollback of every FX system / channel writer of the FX cards (ARTLOOK fx=). */
inline const TCHAR* const FxLegacyFlagName = TEXT("S08FxLegacy");
/** FX-19 (ВР-20): the red hit fill of before instead of the white flash + cream rim (ARTLOOK hitFx=). */
inline const TCHAR* const HitTintLegacyFlagName = TEXT("S08HitTintLegacy");

/** True unless -S08FxLegacy (or the automation override). */
UNMATCHED_API bool FxEnabled();
/** True with -S08HitTintLegacy (or the automation override). */
UNMATCHED_API bool HitTintLegacy();
/** Automation tests only: force both flags; Reset reads the command line again. */
UNMATCHED_API void SetOverrideForTest(bool bFxEnabled, bool bHitTintLegacy);
UNMATCHED_API void ResetOverrideForTest();

/** The effect types of ВР-25 (one per system; assets under /Game/S08/FX/EffectTypes/). */
inline const TCHAR* const CombatEffectType = TEXT("/Game/S08/FX/EffectTypes/NET_UM_Combat");
inline const TCHAR* const BoardEffectType = TEXT("/Game/S08/FX/EffectTypes/NET_UM_Board");
/** ВР-25: not more than three combat systems alive at once, six board systems. */
constexpr int32 CombatMaxSystemInstances = 3;
constexpr int32 BoardMaxSystemInstances = 6;

/** One CUE's FX binding (the vfx block of its cue-table row). */
struct FEntry {
  FString CueId;        // CUE-008 ...
  FString System;       // the planned /Game/S08/FX/... path ("" = per-hero, FX-28)
  FString HeroKey;      // only CUE-014: KingArthur / Medusa choose their own system (FX-28)
  FString EffectType;   // CombatEffectType / BoardEffectType
  bool bSocket = false; // vfx.attach == "socket"
  FString Socket;       // the socket name when attached
  int32 SpriteBudget = 0;  // the ВР-25 sprite cap of the emitter set (fx_audit checks the allocations)
  bool bPrewarm = true;    // LoadSynchronous + pool prime at the match load (cue-table "prewarm")
};

/** The registry rows (CUE-007/008/011/012/013 + the two CUE-014 hero systems). */
UNMATCHED_API const TArray<FEntry>& Registry();
/** The entry of a CUE (the first match; CUE-014 rows match by hero key). */
UNMATCHED_API const FEntry* Find(const FString& CueId, const FString& HeroKey = FString());
/** The trace token of a system: its asset name (NS_FX_HitStar), or "none" for an empty path. */
UNMATCHED_API FString SystemName(const FString& SystemPath);
/** FX-04: RandomSeed of a system = CRC32 of its asset name & 0x7FFFFFFF. */
UNMATCHED_API uint32 SeedOf(const FString& SystemPath);

}  // namespace S08CueFx

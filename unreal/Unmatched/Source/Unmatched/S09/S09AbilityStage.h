// VS-6 F3 FX-30 (ВР-FX11, by delegation; docs/game-design/visual/06-tasks/vfx.csv FX-30, 02-visual-design.md §9.2
// CUE-014; DE timings docs/game-design/de-footage/live-2026-10-04/timings-live.csv medusa_gaze_*): the staging of Medusa's
// gaze - a world-free timeline in the image of FS09CombatStage (S09CombatStage.h, which stays unchanged) that turns the
// snapshot resolving her pending `ability-medusa-target-p<n>` into one scene:
//   t0 (the apply frame)  CUE-014 on Medusa (socket Root, NS_FX_MedusaVortex 0..600 ms on her model)
//   t0 + 454              contact: CUE-011 of the target, staged (the FX-23 set without a lunge - white flash, hit star,
//                         cream rim, HitReact), the tint 450 (lethal 550)
//   + 60                  «−N»
//   + 80                  the target's HP in the HUD (the old HP is held until then: FS09CombatHold)
//   + 450 (lethal)        the fall (DeathSettle, F-09)
//   end                   max(t0 + 800 (CUE-014), contact + 80, lethal: contact + 450)
// Reduced motion: no vortex, the contact at t0 + 100. The speed setting never scales it (as in DE). A new ability
// staging or a combat cuts a running one (the held HP / fall are released at once). No beam, no line to the target:
// «who -> whom» is the star at the target and the LOG line (ВР-22).
//
// Trace (gated by cue_contract.py check-trace A1):
//   CUE ability seq=<n> stage=start t=<ms> hero=medusa fighter=<id> target=<id> damage=<n> lethal=<0|1> reduced=<0|1>
//   CUE ability seq=<n> stage=contact|minus|hp|fall t=<ms> hero=medusa target=<id> [amount=<n> | from=<a> to=<b>]
//   CUE ability seq=<n> stage=end t=<ms> hero=medusa target=<id> cut=<0|replace|combat>
#pragma once

#include "CoreMinimal.h"
#include "S09CombatStage.h"

class FS08CueDispatcher;

/** FX-30 numbers (ms from t0, the apply frame of the resolving snapshot). */
struct UNMATCHED_API FS09AbilityTiming {
  static constexpr int32 VortexMs = 600;          // NS_FX_MedusaVortex life (FX-29: 16 frames x 37.5 ms)
  static constexpr int32 ContactMs = 454;         // the contact equivalent (DE medusa_gaze_ring_to_hp - 80)
  static constexpr int32 ReducedContactMs = 100;  // reduced motion: no vortex, the hit at t0 + 100
  static constexpr int32 MinusDelayMs = 60;
  static constexpr int32 HpDelayMs = 80;
  static constexpr int32 FallMs = 450;
  static constexpr int32 ShowMs = 800;            // CUE-014 duration
  static constexpr int32 HitTintMs = 450;
  static constexpr int32 HitTintLethalMs = 550;
};

/** What the staging needs (built by the game mode's FX adapter from an AbilityTriggered cue). */
struct UNMATCHED_API FS09AbilityStageInput {
  int32 Seq = -1;
  FString HeroKey = TEXT("Medusa");  // S08HeroesV2 key of the hero whose ability fired
  FString FighterId;                 // the hero's fighter (CUE-014 subject, the vortex's root)
  FString TargetId;                  // the damaged target (CUE-011 subject)
  int32 Damage = 0;
  int32 HpBefore = -1;
  int32 HpAfter = -1;
  bool bLethal = false;
  int32 TargetX = -1;                // the target's cell before the blow (kept standing until the fall)
  int32 TargetY = -1;
  bool bReducedMotion = false;
};

enum class ES09AbilityEvent : uint8 { Vortex, Contact, Minus, Hp, Fall, End };
struct UNMATCHED_API FS09AbilityStageEvent {
  ES09AbilityEvent Type = ES09AbilityEvent::End;
  int64 AtMs = 0;
};
UNMATCHED_API const TCHAR* S09AbilityEventName(ES09AbilityEvent Event);

class UNMATCHED_API FS09AbilityStage {
public:
  /** Starts the staging at NowMs: the start line, CUE-014 on the hero and the Vortex event (not under reduced motion).
   *  A running staging is cut first (cut=replace). False (nothing started) for an input without a seq, a fighter or a
   *  target, and for the seq of the last staging (ACC-012: a repeated seq never shows the gaze twice). */
  bool Start(const FS09AbilityStageInput& InInput, int64 NowMs, FS08CueDispatcher& Cues, TArray<FString>& OutLines,
             TArray<FS09AbilityStageEvent>& OutEvents);
  /** Emits every boundary due at or before NowMs, in time order. */
  void Tick(int64 NowMs, FS08CueDispatcher& Cues, TArray<FString>& OutLines, TArray<FS09AbilityStageEvent>& OutEvents);
  /** Ends a running staging now: the pending HP / fall are released at NowMs (the visual ones are dropped). */
  void Cut(int64 NowMs, const TCHAR* Reason, FS08CueDispatcher& Cues, TArray<FString>& OutLines,
           TArray<FS09AbilityStageEvent>& OutEvents);

  bool IsActive() const { return bActive; }
  int32 GetSeq() const { return Input.Seq; }
  const FS09AbilityStageInput& GetInput() const { return Input; }
  /** The target's presentation hold (HP until contact + 80, the figure until the fall). */
  const FS09CombatHold& GetHold() const { return Hold; }
  /** The staging owns the damage of TargetId at Seq (the game mode does not present it at the snapshot). */
  bool HoldsDamage(const FString& TargetId, int32 Seq) const {
    return bActive && Input.Seq == Seq && Input.TargetId == TargetId;
  }
  int64 GetStartMs() const { return StartMs; }
  int64 GetContactMs() const { return ContactAtMs; }
  int64 GetEndMs() const { return EndMs; }
  int32 GetHitTintMs() const {
    return Input.bLethal ? FS09AbilityTiming::HitTintLethalMs : FS09AbilityTiming::HitTintMs;
  }

private:
  FS09AbilityStageInput Input;
  FS09CombatHold Hold;
  bool bActive = false;
  int32 LastStartedSeq = -1;
  int64 StartMs = 0;
  int64 ContactAtMs = 0;
  int64 EndMs = 0;
  int32 NextBoundary = 0;

  FString Prefix(const TCHAR* Stage, int64 TMs) const;
  void Release(ES09AbilityEvent Type, int64 AtMs, TArray<FS09AbilityStageEvent>& OutEvents);
};

// FX-05 / FX-06 / FX-17 / FX-19 (VS-6 Z-2): the two cue channels of a v2 figure - the white flash (CPD_FxFlash
// 5-8) and the cream rim (CPD_RimIntensity 9 / CPD_RimWidth 10) of M_UM_Figure_v2.
//
// ВР-Z2R-01 (по делегированию, 2026-10-07): the channel state, the 60 Hz timer and the hit / defense / hover
// timing live here, in S08/Fx; AS08FighterActor keeps one-line entry points only (the hot-file rule).
//
// Units (the Z-2 review): every duration is in MILLISECONDS (the *Ms names), every clock value in SECONDS of the
// world clock (the *S names). The timing of the cards is held by the presets below, so a caller never passes a
// bare number: HitFlashMs / HitRim (FX-19), DefenseRim (FX-17, t0 = event + 150 ms), HoverRim / HoverLeaveMs
// (FX-06). The pure part (Start* / Advance) is world-free and tested at the card's time stamps
// (Unmatched.S08.HeroesV2.FxChannelTiming).
#pragma once

#include "CoreMinimal.h"
#include "Engine/TimerHandle.h"
#include "UObject/WeakObjectPtr.h"

class AActor;
class UPrimitiveComponent;

namespace S08FigureFx {

/** A rim pulse: ease-out 0 -> Peak over InMs, the peak until TotalMs - OutMs, down to 0 at TotalMs; bHold stays
 *  at Peak after the ramp until a leave. DelayMs shifts the whole pulse after the call (FX-17 t0 = event + 150). */
struct FRimPulse {
  double TotalMs = 0.0;
  float Peak = 0.0f;
  float Width = 0.0f;
  double InMs = 0.0;
  double OutMs = 0.0;
  bool bHold = false;
  double DelayMs = 0.0;
};

/** FX-19 (ВР-20): the white flash, a = 1 for 70 ms (never scaled by the combat speed). */
inline constexpr double HitFlashMs = 70.0;
/** FX-19: the rim from C+70 - hard start, 1.0 x 0.35, held to C+270, 0 at C+370. */
inline constexpr FRimPulse HitRim{300.0, 1.0f, 0.35f, 0.0, 100.0, false, 70.0};
/** FX-17 (ВР-23): t0 = event + 150 (CUE-009 feedback_delay_ms); 0 -> 1.0 over 60, held to +180, 0 at +300. VC C3
 *  (ВР-VC-16): width 0.6 (was 0.35, the hit rim's) - a ~20 % wider cream contour, the shape reads on dark fields
 *  (ВР-21); 0.75 adds < 1 % more band (the band already spans the thin parts) and floods the figure at K2. */
inline constexpr FRimPulse DefenseRim{300.0, 1.0f, 0.6f, 60.0, 120.0, false, 150.0};
/** FX-06: the hover rim, ease-out 0 -> 0.6 over 150 ms (width 0.2), held while the cursor stays. */
inline constexpr FRimPulse HoverRim{150.0, 0.6f, 0.2f, 150.0, 0.0, true, 0.0};
/** FX-06: the cursor left - the held rim goes to 0 over 120 ms (motion.icon.leave.ms). */
inline constexpr double HoverLeaveMs = 120.0;
/** Reduced motion (FX-17 / FX-19): the rim at 0.6 for 100 ms, no flash; the hover (keep) jumps to 0.6 and to 0. */
inline constexpr float ReducedRimPeak = 0.6f;
inline constexpr double ReducedRimMs = 100.0;
/** VS-6 F2 (ВР-VS6-14): the figure cue overlay and its own custom primitive data (flash a, rim intensity, rim width) -
 *  after the v1 layout 0-11 and the v2 slots 12-14 of M_UM_Figure_v2. */
inline const TCHAR* const CueOverlayPath = TEXT("/Game/S08/FX/Materials/M_FX_FigureCue.M_FX_FigureCue");
inline constexpr int32 CueFlashCpdIndex = 15;
inline constexpr int32 CueRimCpdIndex = 16;
inline constexpr int32 CueRimWidthCpdIndex = 17;

}  // namespace S08FigureFx

/** The flash + rim channel state of one figure. Owned by AS08FighterActor (a member); Bind gives it the body. */
struct UNMATCHED_API FS08FigureFxChannels {
  // ---- the world-free part (the timing tests drive it with explicit clock values) ----
  /** Starts the flash of Ms at NowS; reduced motion: no flash (a = 0). */
  void StartFlash(double NowS, double Ms, bool bReduced);
  /** Starts a rim pulse at NowS (+ Pulse.DelayMs); reduced motion: Peak 0.6 for 100 ms (a held hover: 0.6 at once). */
  void StartRim(double NowS, const S08FigureFx::FRimPulse& Pulse, bool bReduced);
  /** Ends a held rim: the current value -> 0 over OutMs from NowS (reduced motion: 0 at once). */
  void LeaveRim(double NowS, double OutMs, bool bReduced);
  /** FX-19: the hit from one contact moment NowS - flash 70 ms (bDamage), the rim from NowS + 70. */
  void StartHit(double NowS, bool bDamage, bool bReduced);
  /** Writes the bench state straight (no timers): the exact values the -BenchFx shot shows (ВР-Z2-12). */
  void SetStatic(float FlashA, float RimIntensity, float RimWidth);
  /** Evaluates both channels at NowS; true while a channel still changes (the timer keeps running). */
  bool Advance(double NowS);

  float GetFlash() const { return FlashValue; }
  float GetRim() const { return RimValue; }
  float GetRimWidth() const { return RimWidthValue; }
  /** The scheduled pulse of the last start (the honest hit-fx / fig-fx trace values). */
  double GetFlashMs() const { return bFlashOn ? FlashMs : 0.0; }
  const S08FigureFx::FRimPulse& GetRimPulse() const { return Rim; }

  // ---- the world part: CPD writes on the bound body, the 60 Hz timer on the owner, the fig-fx traces ----
  void Bind(AActor* InOwner, UPrimitiveComponent* InBody, const FString& InTraceId);
  /** Start* at the world clock + Kick + the trace with the scheduled values (reduced motion read here). */
  void PlayFlash(double Ms);
  void PlayRim(const S08FigureFx::FRimPulse& Pulse);
  void StopRim(double OutMs);
  void PlayHit(bool bDamage);
  /** Starts the timer (if a channel animates) and writes the current values. */
  void Kick();
  /** The owner's world clock in seconds (0 without a world). */
  double Now() const;
  /** Clears the timer and writes the neutral 0 / 0. */
  void Reset();
  /** VS-6 F2 (the FX capture hook, -S08FxShots): bOn freezes both channels at the world clock of now (the values stay on
   *  screen for the evidence frame); off resumes them where they stopped (the starts move by the held time). */
  void Hold(bool bOn);
  bool IsHeld() const { return HeldAtS >= 0.0; }

private:
  void Tick();
  void Write() const;

  TWeakObjectPtr<AActor> Owner;
  TWeakObjectPtr<UPrimitiveComponent> Body;
  FString TraceId;
  FTimerHandle Timer;
  // flash
  bool bFlashOn = false;
  double FlashStartS = 0.0;
  double FlashMs = 0.0;
  float FlashValue = 0.0f;
  // rim
  bool bRimOn = false;
  double RimStartS = 0.0;  // the pulse's own 0 (after its delay)
  S08FigureFx::FRimPulse Rim;
  float RimValue = 0.0f;
  float RimWidthValue = 0.0f;
  double HeldAtS = -1.0;
};

// FX-05 / FX-06 / FX-17 / FX-19: see S08FigureFxChannels.h (ВР-Z2R-01: the channel code lives in S08/Fx).
#include "S08FigureFxChannels.h"

#include "Components/PrimitiveComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "TimerManager.h"
#include "../S08HeroesV2.h"
#include "../S08IconMotion.h"
#include "../S08TraceLog.h"

void FS08FigureFxChannels::StartFlash(double NowS, double Ms, bool bReduced) {
  // FX-19 (ВР-20): reduced motion plays no flash at all
  if (bReduced || Ms <= 0.0) {
    bFlashOn = false;
    FlashMs = 0.0;
    FlashValue = 0.0f;
    return;
  }
  bFlashOn = true;
  FlashStartS = NowS;
  FlashMs = Ms;
}

void FS08FigureFxChannels::StartRim(double NowS, const S08FigureFx::FRimPulse& Pulse, bool bReduced) {
  if (Pulse.TotalMs <= 0.0 && !Pulse.bHold) return;
  Rim = Pulse;
  // a negative ramp is the auto shape of RimIntensityAt: 20 % in, 40 % out of the total
  if (Rim.InMs < 0.0) Rim.InMs = Rim.TotalMs * 0.2;
  if (Rim.OutMs < 0.0) Rim.OutMs = Rim.TotalMs * 0.4;
  if (bReduced) {
    // FX-06 keep: the hover jumps to 0.6 and stays; FX-17 / FX-19: 0.6 for 100 ms, no ramps (the defense keeps its
    // event delay)
    Rim.Peak = S08FigureFx::ReducedRimPeak;
    Rim.InMs = 0.0;
    Rim.OutMs = 0.0;
    if (!Rim.bHold) Rim.TotalMs = S08FigureFx::ReducedRimMs;
  }
  bRimOn = true;
  RimStartS = NowS + Rim.DelayMs / 1000.0;
  RimWidthValue = Rim.Width;
}

void FS08FigureFxChannels::LeaveRim(double NowS, double OutMs, bool bReduced) {
  if (!bRimOn && RimValue <= 0.0f) return;
  const float From = RimValue;
  bRimOn = false;
  RimValue = 0.0f;
  if (bReduced || OutMs <= 0.0 || From <= 0.0f) return;
  // FX-06: the cursor left - the value of now unwinds linearly to 0 over OutMs
  Rim = S08FigureFx::FRimPulse{OutMs, From, Rim.Width, 0.0, OutMs, false, 0.0};
  bRimOn = true;
  RimStartS = NowS;
  RimValue = From;
}

void FS08FigureFxChannels::StartHit(double NowS, bool bDamage, bool bReduced) {
  // FX-19 (ВР-20): one contact moment C = NowS; the flash C+0..C+70 (damage only - урон 0 is the rim alone, FX-23),
  // the rim C+70..C+370 (hard start, held to C+270)
  StartFlash(NowS, bDamage ? S08FigureFx::HitFlashMs : 0.0, bReduced);
  S08FigureFx::FRimPulse Pulse = S08FigureFx::HitRim;
  if (bReduced) Pulse.DelayMs = 0.0;  // no flash to wait for: the reduced rim starts at C
  StartRim(NowS, Pulse, bReduced);
}

void FS08FigureFxChannels::SetStatic(float FlashA, float RimIntensity, float RimWidth) {
  bFlashOn = false;
  bRimOn = false;
  FlashValue = FlashA;
  RimValue = RimIntensity;
  RimWidthValue = RimWidth;
  if (AActor* O = Owner.Get()) {
    if (UWorld* World = O->GetWorld()) World->GetTimerManager().ClearTimer(Timer);
  }
  Write();
}

bool FS08FigureFxChannels::Advance(double NowS) {
  bool bActive = false;
  // the clock difference in ms, rounded to the microsecond: (C + 0.37) - (C + 0.07) must read 300, not 299.99999
  auto Ms = [](double Seconds) { return FMath::RoundToDouble(Seconds * 1.0e6) / 1000.0; };
  if (bFlashOn) {
    const double T = Ms(NowS - FlashStartS);
    FlashValue = S08HeroesV2::FxFlashValueAt(T, FlashMs);
    if (T >= FlashMs) {
      bFlashOn = false;
      FlashValue = 0.0f;
    } else {
      bActive = true;
    }
  }
  if (bRimOn) {
    const double T = Ms(NowS - RimStartS);
    if (Rim.bHold) {
      // the hover: the ease-out ramp, then the peak held until LeaveRim
      if (T < 0.0) {
        RimValue = 0.0f;
      } else if (T < Rim.InMs) {
        const double X = T / Rim.InMs;
        RimValue = static_cast<float>(Rim.Peak * (1.0 - (1.0 - X) * (1.0 - X)));
      } else {
        RimValue = Rim.Peak;
      }
      bActive = bActive || T < Rim.InMs;
    } else {
      RimValue = S08HeroesV2::RimIntensityAt(T, Rim.TotalMs, Rim.Peak, Rim.InMs, Rim.OutMs);
      if (T >= Rim.TotalMs) {
        bRimOn = false;
        RimValue = 0.0f;
      } else {
        bActive = true;
      }
    }
  }
  return bActive;
}

void FS08FigureFxChannels::Bind(AActor* InOwner, UPrimitiveComponent* InBody, const FString& InTraceId) {
  Owner = InOwner;
  Body = InBody;
  TraceId = InTraceId;
}

void FS08FigureFxChannels::PlayFlash(double Ms) {
  StartFlash(Now(), Ms, S08IconMotion::IsReducedMotion());
  Kick();
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW fig-fx fighter=%s ch=flash ms=%d peak=%.2f"), *TraceId,
                                   FMath::RoundToInt(GetFlashMs()), bFlashOn ? 1.0f : 0.0f));
}

void FS08FigureFxChannels::PlayRim(const S08FigureFx::FRimPulse& Pulse) {
  StartRim(Now(), Pulse, S08IconMotion::IsReducedMotion());
  Kick();
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW fig-fx fighter=%s ch=rim ms=%d delay=%d in=%d out=%d peak=%.2f width=%.2f hold=%d"),
                                   *TraceId, FMath::RoundToInt(Rim.TotalMs), FMath::RoundToInt(Rim.DelayMs),
                                   FMath::RoundToInt(Rim.InMs), FMath::RoundToInt(Rim.OutMs), Rim.Peak, Rim.Width,
                                   Rim.bHold ? 1 : 0));
}

void FS08FigureFxChannels::StopRim(double OutMs) {
  if (!bRimOn && RimValue <= 0.0f) return;
  LeaveRim(Now(), OutMs, S08IconMotion::IsReducedMotion());
  Kick();
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW fig-fx fighter=%s ch=rim ms=%d peak=%.2f leave=1"), *TraceId,
                                   bRimOn ? FMath::RoundToInt(Rim.TotalMs) : 0, bRimOn ? Rim.Peak : 0.0f));
}

void FS08FigureFxChannels::PlayHit(bool bDamage) {
  StartHit(Now(), bDamage, S08IconMotion::IsReducedMotion());
  Kick();
  // the honest values of this hit (the review: no constants): flash window, rim length / start / peak
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW hit-fx fighter=%s flash=%d rim=%d rimAt=%d peak=%.2f legacy=0"),
                                   *TraceId, FMath::RoundToInt(GetFlashMs()), FMath::RoundToInt(Rim.TotalMs),
                                   FMath::RoundToInt(Rim.DelayMs), Rim.Peak));
}

double FS08FigureFxChannels::Now() const {
  const AActor* O = Owner.Get();
  const UWorld* World = O ? O->GetWorld() : nullptr;
  return World ? World->GetTimeSeconds() : 0.0;
}

void FS08FigureFxChannels::Kick() {
  AActor* O = Owner.Get();
  UWorld* World = O ? O->GetWorld() : nullptr;
  const bool bActive = Advance(Now());
  Write();
  if (!World) return;
  FTimerManager& Timers = World->GetTimerManager();
  if (!bActive) {
    Timers.ClearTimer(Timer);
  } else if (!Timers.IsTimerActive(Timer)) {
    // the TickHitTint pattern: 60 Hz, the values come from the clock, not from the tick count
    Timers.SetTimer(Timer, FTimerDelegate::CreateWeakLambda(O, [this] { Tick(); }), 1.0f / 60.0f, true);
  }
}

void FS08FigureFxChannels::Reset() {
  bFlashOn = false;
  bRimOn = false;
  FlashValue = 0.0f;
  RimValue = 0.0f;
  if (AActor* O = Owner.Get()) {
    if (UWorld* World = O->GetWorld()) World->GetTimerManager().ClearTimer(Timer);
  }
  Write();
}

void FS08FigureFxChannels::Tick() {
  const bool bActive = Advance(Now());
  Write();
  if (!bActive) {
    if (AActor* O = Owner.Get()) {
      if (UWorld* World = O->GetWorld()) World->GetTimerManager().ClearTimer(Timer);
    }
  }
}

void FS08FigureFxChannels::Write() const {
  UPrimitiveComponent* B = Body.Get();
  if (!B) return;
  S08HeroesV2::SetFxFlash(B, S08HeroesV2::FxFlashColor(), FlashValue);
  S08HeroesV2::SetRim(B, RimValue, RimWidthValue);
}

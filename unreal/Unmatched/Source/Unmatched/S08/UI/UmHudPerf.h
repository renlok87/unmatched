// VS-3 HUD budget (docs/game-design/visual/05-production-plan.md §3 VS-3; docs/unreal/contracts/hud/HUD-RULES.md П8:
// the HUD <= 0.5 ms GT p95 and <= 0.3 ms GPU at 1080p): the same-process A/B of the UMG HUD cost in a live match,
// opt-in client flag -S08HudPerf (block length -S08HudPerfBlock=<frames>, default 90 = 3 s at 30 FPS).
//
//   method   the UMG HUD root (every VS-2 / VS-3 block) alternates COLLAPSED (no tick, no prepass, no paint) and SHOWN
//            in blocks of N frames, hidden first; the first 6 frames after each switch are skipped (the engine's game
//            thread / GPU times of a frame land one or two frames later). A pair is a hidden block and the shown block
//            right after it: a spike of the rest of the frame (the scene, the network, the other client) falls into both
//            halves, so the median of the paired differences is the HUD's own cost (the W4-C ΔGT method,
//            docs/game-design/evidence/ART-004/hud-umg-w4c-2026-09-29.md §4.4, and the ICONGALLERY perf A/B).
//   pause    while an evidence frame is in flight or queued the HUD stays shown and the current block starts over (a
//            frame of the run never loses its HUD).
//   samples  GGameThreadTime (the game thread's work, the t.MaxFPS wait excluded) and RHIGetGPUFrameCycles (the GPU
//            frame, idle bubbles excluded) - the same engine globals as -S08Perf / the CSV profiler.
// Trace: 'HUDPERF period=<n> shown=0|1 frames=<n> gtP50= gtP95= gpuP50= gpuP95=' per block and
//        'HUDPERF summary why=<..> pairs=<n> dGtP95Med= dGtP95Mean= dGtP50Med= dGpuP95Med= dGpuP50Med= shownGtP95=
//        hiddenGtP95= shownGpuP95= hiddenGpuP95= budgetGt=0.5 budgetGpu=0.3 frames=<shown>/<hidden>' every 10 pairs and
//        at the end of the match.
#pragma once

#include "CoreMinimal.h"

namespace UmHudPerf {
/** The Q-quantile (nearest rank, Q in 0..1) of the samples; 0 for none. */
UNMATCHED_API float Quantile(TArray<float> Samples, float Q);
/** The median (the mean of the two middle samples of an even count); 0 for none. */
UNMATCHED_API float Median(TArray<float> Samples);
}  // namespace UmHudPerf

/** World-free meter: one Step per frame, it says whether the HUD is shown in the next frame. */
class UNMATCHED_API FUmHudPerfMeter {
 public:
  int32 BlockFrames = 90;
  int32 SkipFrames = 6;

  /** One frame's times (of the visibility the meter asked for before). bPause: an evidence frame is in flight - the
   *  HUD shows and the current block starts over. Returns the visibility wanted for the next frame; the finished
   *  block's line (and every 10 pairs the summary) goes to OutLines. */
  bool Step(float GtMs, float GpuMs, bool bPause, TArray<FString>& OutLines);
  FString Summary(const TCHAR* Why) const;
  int32 Pairs() const { return DGt95.Num(); }
  int32 Period() const { return PeriodIndex; }
  bool IsShownPeriod() const { return (PeriodIndex % 2) == 1; }
  float MedianDeltaGtP95() const { return UmHudPerf::Median(DGt95); }
  float MedianDeltaGpuP95() const { return UmHudPerf::Median(DGpu95); }

 private:
  int32 PeriodIndex = 0;  // even = hidden, odd = shown
  int32 Frame = 0;        // frames into the current block
  TArray<float> Gt;
  TArray<float> Gpu;
  bool bHiddenValid = false;
  int32 HiddenPeriod = -1;
  float HiddenGt50 = 0.0f, HiddenGt95 = 0.0f, HiddenGpu50 = 0.0f, HiddenGpu95 = 0.0f;
  TArray<float> DGt50, DGt95, DGpu50, DGpu95;
  TArray<float> AllShownGt, AllHiddenGt, AllShownGpu, AllHiddenGpu;
};

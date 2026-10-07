// VS-3 HUD budget meter (-S08HudPerf): see UmHudPerf.h.
#include "UmHudPerf.h"

namespace UmHudPerf {
float Quantile(TArray<float> Samples, float Q) {
  if (Samples.Num() == 0) return 0.0f;
  Samples.Sort();
  const int32 Rank = FMath::Clamp(FMath::CeilToInt(FMath::Clamp(Q, 0.0f, 1.0f) * Samples.Num()) - 1, 0, Samples.Num() - 1);
  return Samples[Rank];
}

float Median(TArray<float> Samples) {
  if (Samples.Num() == 0) return 0.0f;
  Samples.Sort();
  const int32 N = Samples.Num();
  return (N % 2) == 1 ? Samples[N / 2] : 0.5f * (Samples[N / 2 - 1] + Samples[N / 2]);
}
}  // namespace UmHudPerf

bool FUmHudPerfMeter::Step(float GtMs, float GpuMs, bool bPause, TArray<FString>& OutLines) {
  if (bPause) {
    // an evidence frame keeps its HUD: the block starts over once the frame is written
    Frame = 0;
    Gt.Reset();
    Gpu.Reset();
    return true;
  }
  const bool bShown = IsShownPeriod();
  if (Frame >= SkipFrames) {
    Gt.Add(GtMs);
    Gpu.Add(GpuMs);
  }
  if (++Frame < FMath::Max(BlockFrames, SkipFrames + 1)) return bShown;
  const float Gt50 = UmHudPerf::Quantile(Gt, 0.5f), Gt95 = UmHudPerf::Quantile(Gt, 0.95f);
  const float Gpu50 = UmHudPerf::Quantile(Gpu, 0.5f), Gpu95 = UmHudPerf::Quantile(Gpu, 0.95f);
  OutLines.Add(FString::Printf(TEXT("HUDPERF period=%d shown=%d frames=%d gtP50=%.3f gtP95=%.3f gpuP50=%.3f gpuP95=%.3f"),
                               PeriodIndex, bShown ? 1 : 0, Gt.Num(), Gt50, Gt95, Gpu50, Gpu95));
  if (bShown) {
    AllShownGt.Append(Gt);
    AllShownGpu.Append(Gpu);
    if (bHiddenValid && HiddenPeriod == PeriodIndex - 1) {
      DGt50.Add(Gt50 - HiddenGt50);
      DGt95.Add(Gt95 - HiddenGt95);
      DGpu50.Add(Gpu50 - HiddenGpu50);
      DGpu95.Add(Gpu95 - HiddenGpu95);
      if (DGt95.Num() % 10 == 0) OutLines.Add(Summary(TEXT("every-10")));
    }
    bHiddenValid = false;
  } else {
    AllHiddenGt.Append(Gt);
    AllHiddenGpu.Append(Gpu);
    bHiddenValid = Gt.Num() > 0;
    HiddenPeriod = PeriodIndex;
    HiddenGt50 = Gt50;
    HiddenGt95 = Gt95;
    HiddenGpu50 = Gpu50;
    HiddenGpu95 = Gpu95;
  }
  ++PeriodIndex;
  Frame = 0;
  Gt.Reset();
  Gpu.Reset();
  return IsShownPeriod();
}

FString FUmHudPerfMeter::Summary(const TCHAR* Why) const {
  float MeanGt95 = 0.0f;
  for (const float D : DGt95) MeanGt95 += D;
  MeanGt95 = DGt95.Num() ? MeanGt95 / DGt95.Num() : 0.0f;
  return FString::Printf(
      TEXT("HUDPERF summary why=%s pairs=%d dGtP95Med=%.3f dGtP95Mean=%.3f dGtP50Med=%.3f dGpuP95Med=%.3f dGpuP50Med=%.3f "
           "shownGtP95=%.3f hiddenGtP95=%.3f shownGpuP95=%.3f hiddenGpuP95=%.3f budgetGt=0.5 budgetGpu=0.3 frames=%d/%d"),
      Why, DGt95.Num(), UmHudPerf::Median(DGt95), MeanGt95, UmHudPerf::Median(DGt50), UmHudPerf::Median(DGpu95),
      UmHudPerf::Median(DGpu50), UmHudPerf::Quantile(AllShownGt, 0.95f), UmHudPerf::Quantile(AllHiddenGt, 0.95f),
      UmHudPerf::Quantile(AllShownGpu, 0.95f), UmHudPerf::Quantile(AllHiddenGpu, 0.95f), AllShownGt.Num(),
      AllHiddenGt.Num());
}

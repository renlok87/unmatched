// HUD icon motion v3 (docs/unreal/contracts/hud/ICON-MOTION-PLAN.md, phase E): the game-mode side of
// -S08IconGallery. BeginPlay builds US08IconGalleryWidget (every contract icon looping its demo script on the
// HUD panel colour) and returns before the backend flow; Tick drives only the gallery. With
// -S08IconGalleryShots=<dir> the gallery clock is frozen at each -S08IconGalleryTimes=<ms,...> value, a UI shot
// icon-gallery-<normal|reduced>-<t>.png is taken (TakeEvidenceShot), and the process exits after the last one.
// Optional: -S08IconGallerySize=<px> (texture size and icon side, default 64), -S08ReducedMotion.
#include "S08FlowGameMode.h"

#include "S08AnimatedIconWidget.h"
#include "S08IconMotion.h"
#include "S08TraceLog.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"

namespace {
constexpr int32 GalleryShotSettleFrames = 4;  // frames between freezing the clock and the shot request
constexpr int32 GalleryShotLandFrames = 3;    // frames after the request finished before the next time
}  // namespace

bool AS08FlowGameMode::IconGalleryBegin() {
  const TCHAR* Cmd = FCommandLine::Get();
  if (!FParse::Param(Cmd, TEXT("S08IconGallery"))) return false;
  bIconGallery = true;
  int32 SizePx = 64;
  FParse::Value(Cmd, TEXT("S08IconGallerySize="), SizePx);
  SizePx = FMath::Clamp(SizePx, 16, 128);
  FParse::Value(Cmd, TEXT("S08IconGalleryShots="), IconGalleryShotDir);
  FString Times;
  // The list is comma separated: FParse::Value must not stop at the first comma.
  if (FParse::Value(Cmd, TEXT("S08IconGalleryTimes="), Times, /*bShouldStopOnSeparator=*/false)) {
    TArray<FString> Parts;
    Times.ParseIntoArray(Parts, TEXT(","), true);
    for (const FString& P : Parts) IconGalleryTimes.Add(FCString::Atof(*P));
  }
  if (!IconGalleryShotDir.IsEmpty() && IconGalleryTimes.Num() == 0) {
    IconGalleryTimes = {0.0f, 60.0f, 120.0f, 180.0f, 300.0f, 600.0f, 900.0f, 1200.0f, 1500.0f, 2000.0f};
  }
  const bool bReduced = S08IconMotion::IsReducedMotion();
  const FS08IconMotionLibrary& Lib = FS08IconMotionLibrary::Get();
  IconGallery = CreateWidget<US08IconGalleryWidget>(GetWorld(), US08IconGalleryWidget::StaticClass());
  const int32 Count = IconGallery ? IconGallery->Build(static_cast<float>(SizePx), SizePx, bReduced) : 0;
  if (IconGallery) IconGallery->AddToViewport(1000);
  if (IconGallery && IconGalleryTimes.Num() > 0 && !IconGalleryShotDir.IsEmpty()) {
    IconGallery->SetClockOverrideMs(IconGalleryTimes[0]);
  }
  if (APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr) PC->bShowMouseCursor = true;
  FS08Trace::Write(FString::Printf(
      TEXT("ICONGALLERY start icons=%d size=%d reduced=%d contract=%s loaded=%d shots=%s times=%d"), Count, SizePx,
      bReduced ? 1 : 0, *Lib.Revision, Lib.bLoaded ? 1 : 0,
      IconGalleryShotDir.IsEmpty() ? TEXT("none") : *IconGalleryShotDir, IconGalleryTimes.Num()));
  return true;
}

void AS08FlowGameMode::IconGalleryTick(float DeltaSeconds) {
  if (!IconGallery || IconGalleryShotDir.IsEmpty()) return;
  // -S08IconGalleryPerfFrames=<n>: n free-running frames first (clock advancing, every icon animating) - the cost
  // sample: EvaluateAt of all icons (gallery replays every script each frame - an upper bound of real use) and
  // the game-thread frame time.
  if (IconGalleryPerfLeft < 0) {
    IconGalleryPerfLeft = 0;
    FParse::Value(FCommandLine::Get(), TEXT("S08IconGalleryPerfFrames="), IconGalleryPerfLeft);
    if (IconGalleryPerfLeft > 0) {
      IconGallery->SetClockOverrideMs(-1.0f);
      IconGallery->ResetPerf();
    }
  }
  if (IconGalleryPerfLeft > 0) {
    IconGalleryGtMs.Add(FPlatformTime::ToMilliseconds(GGameThreadTime));
    if (--IconGalleryPerfLeft == 0) {
      TArray<float> S = IconGalleryGtMs;
      S.Sort();
      float Sum = 0.0f;
      for (const float V : S) Sum += V;
      const float P95 = S.Num() ? S[FMath::Clamp(FMath::CeilToInt(0.95f * S.Num()) - 1, 0, S.Num() - 1)] : 0.0f;
      FS08Trace::Write(FString::Printf(TEXT("ICONGALLERY perf %s gtMsAvg=%.3f gtMsP95=%.3f"),
                                       *IconGallery->PerfSummary(), S.Num() ? Sum / S.Num() : 0.0f, P95));
      if (IconGalleryTimes.Num() > 0) IconGallery->SetClockOverrideMs(IconGalleryTimes[0]);
    }
    return;
  }
  if (IconGalleryShot >= IconGalleryTimes.Num()) {
    if (IconGalleryShot == IconGalleryTimes.Num()) {
      ++IconGalleryShot;
      FS08Trace::Write(FString::Printf(TEXT("ICONGALLERY done shots=%d dir=%s"), IconGalleryTimes.Num(),
                                       *IconGalleryShotDir));
      FS08Trace::Close();
      FGenericPlatformMisc::RequestExit(false);
    }
    return;
  }
  const float T = IconGalleryTimes[IconGalleryShot];
  if (bIconGalleryShotPending) {
    if (FScreenshotRequest::IsScreenshotRequested()) return;
    if (++IconGalleryWait < GalleryShotLandFrames) return;
    bIconGalleryShotPending = false;
    IconGalleryWait = 0;
    ++IconGalleryShot;
    if (IconGalleryTimes.IsValidIndex(IconGalleryShot)) IconGallery->SetClockOverrideMs(IconGalleryTimes[IconGalleryShot]);
    return;
  }
  IconGallery->SetClockOverrideMs(T);
  if (++IconGalleryWait < GalleryShotSettleFrames) return;
  IconGalleryWait = 0;
  const FString Name = FString::Printf(TEXT("icon-gallery-%s-%05d.png"),
                                       S08IconMotion::IsReducedMotion() ? TEXT("reduced") : TEXT("normal"),
                                       FMath::RoundToInt(T));
  TakeEvidenceShot(IconGalleryShotDir / Name);
  FS08Trace::Write(FString::Printf(TEXT("ICONGALLERY shot t=%.0f file=%s"), T, *Name));
  bIconGalleryShotPending = true;
}

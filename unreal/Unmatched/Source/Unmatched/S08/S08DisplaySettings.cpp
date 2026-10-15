#include "S08DisplaySettings.h"

#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "GameFramework/GameUserSettings.h"
#include "Kismet/KismetSystemLibrary.h"
#include "UnrealClient.h"
#include "Framework/Application/SlateApplication.h"
#include "Widgets/SWindow.h"
#include "Containers/Ticker.h"
#include "Misc/CommandLine.h"
#include "Misc/DelayedAutoRegister.h"
#include "Misc/Parse.h"

namespace S08Display {
FString ResolutionValue(FIntPoint R) { return FString::Printf(TEXT("%dx%d"), R.X, R.Y); }

TArray<FIntPoint> ResolutionOptions(FIntPoint Desktop, FIntPoint Current) {
  TArray<FIntPoint> Out;
  const FIntPoint Presets[] = {{1280, 720}, {1600, 900}, {1920, 1080}, {2560, 1080},
                              {2560, 1440}, {3440, 1440}, {3840, 2160}, {5120, 1440}};
  for (FIntPoint R : Presets) {
    if (R.X <= Desktop.X && R.Y <= Desktop.Y) Out.Add(R);
  }
  if (Desktop.X > 0 && Desktop.Y > 0) Out.AddUnique(Desktop);
  if (Current.X > 0 && Current.Y > 0) Out.AddUnique(Current);
  Out.Sort([](const FIntPoint& A, const FIntPoint& B) {
    const int64 AreaA = int64(A.X) * A.Y, AreaB = int64(B.X) * B.Y;
    return AreaA == AreaB ? A.X < B.X : AreaA < AreaB;
  });
  return Out;
}

FS08DisplaySettings Read() {
  FS08DisplaySettings S;
  const UGameUserSettings* Gus = GEngine ? GEngine->GetGameUserSettings() : nullptr;
  if (!Gus) return S;
  S.Desktop = Gus->GetDesktopResolution();
  S.WindowMode = static_cast<int32>(Gus->GetFullscreenMode());
  S.Resolution = Gus->GetScreenResolution();
  if (GEngine->GameViewport && GEngine->GameViewport->Viewport) {
    const FIntPoint Actual = GEngine->GameViewport->Viewport->GetSizeXY();
    if (Actual.X > 0 && Actual.Y > 0) S.Resolution = Actual;
  }
  S.Resolutions = ResolutionOptions(S.Desktop, S.Resolution);
  if (S.WindowMode == 1) {
    S.Resolution = S.Desktop;
    S.Resolutions = {S.Desktop};
  } else if (S.WindowMode == 0) {
    // Query the display once, not on every tick of the open settings menu.
    static const TArray<FIntPoint> Supported = [] {
      TArray<FIntPoint> Modes;
      UKismetSystemLibrary::GetSupportedFullscreenResolutions(Modes);
      return Modes;
    }();
    if (!Supported.IsEmpty()) {
      S.Resolutions.RemoveAll([&](FIntPoint R) { return R != S.Resolution && !Supported.Contains(R); });
    }
  }
  return S;
}

bool Resolve(const FS08DisplaySettings& Current, FName Key, const FString& Value,
             FS08DisplaySettings& Out, FString& Error) {
  FS08DisplaySettings Next = Current;
  if (Key == TEXT("windowMode")) {
    if (Value != TEXT("0") && Value != TEXT("1") && Value != TEXT("2")) {
      Error = TEXT("unknown window mode");
      return false;
    }
    Next.WindowMode = FCString::Atoi(*Value);
    if (Next.WindowMode == 1) {
      Next.Resolution = Current.Desktop;
    } else if (Next.WindowMode == 2 && Current.WindowMode != 2) {
      // A desktop-sized borderless surface should become a usable window, including its title bar.
      Next.Resolution = FIntPoint(FMath::Min(1920, Current.Desktop.X - 32),
                                 FMath::Min(1080, Current.Desktop.Y - 80));
    }
  } else if (Key == TEXT("resolution")) {
    const FIntPoint* Choice = Current.Resolutions.FindByPredicate(
        [&](FIntPoint R) { return ResolutionValue(R) == Value; });
    if (!Choice) {
      Error = TEXT("resolution is not available in this window mode");
      return false;
    }
    Next.Resolution = *Choice;
  } else {
    Error = TEXT("unknown display setting");
    return false;
  }
  Out = MoveTemp(Next);
  Error.Reset();
  return true;
}

FIntPoint FitWindowed(FIntPoint Resolution, FIntPoint WorkArea, FIntPoint FramePx) {
  if (Resolution.X <= 0 || Resolution.Y <= 0) return Resolution;
  const int32 MaxW = WorkArea.X - FramePx.X;
  const int32 MaxH = WorkArea.Y - FramePx.Y;
  if (MaxW <= 0 || MaxH <= 0 || (Resolution.X <= MaxW && Resolution.Y <= MaxH)) return Resolution;
  const double Scale = FMath::Min(static_cast<double>(MaxW) / Resolution.X, static_cast<double>(MaxH) / Resolution.Y);
  // even sizes: the swap chain and the HUD's su grid stay on whole pixels
  return FIntPoint(FMath::FloorToInt(Resolution.X * Scale / 2.0) * 2, FMath::FloorToInt(Resolution.Y * Scale / 2.0) * 2);
}

FString FitWindowToWorkArea() {
  UGameUserSettings* Gus = GEngine ? GEngine->GetGameUserSettings() : nullptr;
  UGameViewportClient* GV = GEngine ? GEngine->GameViewport : nullptr;
  const TSharedPtr<SWindow> Window = GV ? GV->GetWindow() : nullptr;
  if (!Gus || !Window.IsValid() || Window->GetWindowMode() != EWindowMode::Windowed || !FSlateApplication::IsInitialized()) {
    return TEXT("DISPLAY fit skipped=not-windowed");
  }
  FDisplayMetrics Metrics;
  FSlateApplication::Get().GetDisplayMetrics(Metrics);
  const FVector2D Pos = Window->GetPositionInScreen();
  const FVector2D Size = Window->GetSizeInScreen();
  const FVector2D Centre = Pos + Size * 0.5;
  FPlatformRect Work = Metrics.PrimaryDisplayWorkAreaRect;
  for (const FMonitorInfo& M : Metrics.MonitorInfo) {
    if (Centre.X >= M.DisplayRect.Left && Centre.X < M.DisplayRect.Right && Centre.Y >= M.DisplayRect.Top &&
        Centre.Y < M.DisplayRect.Bottom) {
      Work = M.WorkArea;
    }
  }
  const FIntPoint WorkSize(Work.Right - Work.Left, Work.Bottom - Work.Top);
  // the client as it is (a -ResX/-ResY start or the saved resolution)
  const FIntPoint Client = GV->Viewport && GV->Viewport->GetSizeXY().X > 0 ? GV->Viewport->GetSizeXY() : Gus->GetScreenResolution();
  // the OS frame: the window's outer size minus its client size, at least a title bar
  const FVector2D ClientNow(Client);
  const FIntPoint Frame(FMath::Max(16, FMath::RoundToInt(Size.X - ClientNow.X)),
                        FMath::Max(40, FMath::RoundToInt(Size.Y - ClientNow.Y)));
  const FIntPoint Fit = FitWindowed(Client, WorkSize, Frame);
  if (Fit == Client) return FString::Printf(TEXT("DISPLAY fit ok client=%dx%d work=%dx%d"), Client.X, Client.Y, WorkSize.X, WorkSize.Y);
  // the window as it is (windowed), only smaller: the saved settings' mode is not applied here and nothing is saved
  FSystemResolution::RequestResolutionChange(Fit.X, Fit.Y, EWindowMode::Windowed);
  // the window's top-left inside the work area, so the title bar stays reachable
  Window->MoveWindowTo(FVector2D(Work.Left + (WorkSize.X - Fit.X - Frame.X) / 2, Work.Top));
  return FString::Printf(TEXT("DISPLAY fit shrunk client=%dx%d -> %dx%d work=%dx%d frame=%dx%d"), Client.X, Client.Y, Fit.X,
                         Fit.Y, WorkSize.X, WorkSize.Y, Frame.X, Frame.Y);
}

namespace {
// Once, a few frames after the game window exists (game only: the editor's PIE windows are the editor's business).
FDelayedAutoRegisterHelper GFitRegister(EDelayedRegisterRunPhase::EndOfEngineInit, [] {
  if (GIsEditor || IsRunningCommandlet() || FParse::Param(FCommandLine::Get(), TEXT("RenderOffScreen"))) return;
  FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([](float) {
    static int32 Frames = 0;
    if (++Frames < 10) return true;
    UE_LOG(LogTemp, Display, TEXT("%s"), *FitWindowToWorkArea());
    return false;
  }));
});
}  // namespace

bool Apply(FName Key, const FString& Value, FString& Error) {
  UGameUserSettings* Gus = GEngine ? GEngine->GetGameUserSettings() : nullptr;
  if (!Gus) { Error = TEXT("video settings unavailable"); return false; }
  FS08DisplaySettings Next;
  if (!Resolve(Read(), Key, Value, Next, Error)) return false;
  Gus->SetScreenResolution(Next.Resolution);
  Gus->SetFullscreenMode(static_cast<EWindowMode::Type>(Next.WindowMode));
  Gus->ApplyResolutionSettings(false);
  Gus->ConfirmVideoMode();
  Gus->SaveSettings();
  return true;
}
}  // namespace S08Display

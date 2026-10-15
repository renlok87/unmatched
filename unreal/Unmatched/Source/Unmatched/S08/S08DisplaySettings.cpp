#include "S08DisplaySettings.h"

#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "GameFramework/GameUserSettings.h"
#include "Kismet/KismetSystemLibrary.h"
#include "UnrealClient.h"

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

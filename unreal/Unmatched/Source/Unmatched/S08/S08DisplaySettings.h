#pragma once

#include "CoreMinimal.h"

/** Engine video settings, separate from render quality and the HUD's UI scale. */
struct UNMATCHED_API FS08DisplaySettings {
  FIntPoint Desktop = FIntPoint(1920, 1080);
  FIntPoint Resolution = FIntPoint(1920, 1080);
  // EWindowMode: 0 fullscreen, 1 borderless (desktop resolution), 2 windowed.
  int32 WindowMode = 1;
  TArray<FIntPoint> Resolutions = {FIntPoint(1920, 1080)};
};

namespace S08Display {
UNMATCHED_API TArray<FIntPoint> ResolutionOptions(FIntPoint Desktop, FIntPoint Current);
UNMATCHED_API FString ResolutionValue(FIntPoint Resolution);
UNMATCHED_API FS08DisplaySettings Read();
/** Validate a menu choice without changing a window or saved settings. */
UNMATCHED_API bool Resolve(const FS08DisplaySettings& Current, FName Key, const FString& Value,
                          FS08DisplaySettings& Out, FString& Error);
/** Apply and save just the video mode; quality, screen percentage and FPS stay as configured. */
UNMATCHED_API bool Apply(FName Key, const FString& Value, FString& Error);
}  // namespace S08Display

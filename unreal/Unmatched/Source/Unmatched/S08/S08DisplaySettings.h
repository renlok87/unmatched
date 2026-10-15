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
/** The windowed client area that fits a monitor's work area (taskbar excluded) with the OS frame (FramePx: width,
 *  height of borders + title bar): the same aspect, never larger than Resolution. User 2026-10-15: a 1920x1080 window
 *  with its title bar on a 1080-1152 px work area lost the bottom of the HUD (hand, action buttons). */
UNMATCHED_API FIntPoint FitWindowed(FIntPoint Resolution, FIntPoint WorkArea, FIntPoint FramePx);
/** Once at start: a windowed client larger than its monitor's work area shrinks to FitWindowed (applied, not saved).
 *  Returns the trace line ('DISPLAY fit ...'). */
UNMATCHED_API FString FitWindowToWorkArea();
}  // namespace S08Display

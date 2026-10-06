// VS-1 HB-09 (docs/game-design/visual/06-tasks/hud.csv HB-09; 02-visual-design.md §3.2, §11.1, ВР-62; 04-hud-spec.md
// §3.6, ВР-H01; UI-ACC-001): the HUD scale of the client.
//
//   DPI       the project curve by the short side of the window (Config/DefaultEngine.ini, [/Script/Engine.
//             UserInterfaceSettings]): 720 -> 0.75, 1080 -> 1.0, 1440 -> 1.333, 2160 -> 2.0 (the engine curve gave
//             720 -> 0.666). type.caption 14 su is 10.5 px at 720p.
//   UI scale  UI-ACC-001, US08UserSettings::UiScalePercent 75..150 % (step 5), at least 100 % while the short side is
//             under 1080 (ВР-62). Applied after the slider is released (the PAUSE screen calls Save) and on a window
//             change - never per slider move, no animation; the layout class L/S follows in the same frame.
//   canvas    window px / (DPI x UI scale) in su; class L >= 1500 su wide, S below (ВР-H01): 1280x720 at 150 % is
//             1138x640 su, class S.
//   -S08DpiLegacy  rollback: the application scale is multiplied by engine curve / project curve at the current short
//             side (720p: 0.666 / 0.75), i.e. the old size. Traced in ARTLOOK (dpi=legacy(-S08DpiLegacy)).
//
// Mechanism (delegated decision ВР-VS1-01, recorded in the VS-1 report): the card names
// FSlateApplication::SetApplicationScale, but the game layer divides that scale out again (UE 5.8
// SGameLayerManager::GetGameViewportDPIScale returns DPI / viewport geometry scale), so every widget added through
// UGameViewportClient::AddViewportWidgetContent - the whole HUD - would keep its size. The engine's game-UI multiplier
// on top of the DPI curve is UUserInterfaceSettings::ApplicationScale (GetDPIScaleBasedOnSize returns curve x
// ApplicationScale; HUD-AND-ICONS.md §1.7 names it for UI-ACC-001), so that is what Apply sets. It scales only the game
// viewport's widgets: the board, the world icons and the 3D view keep their size (04 §3.6), screen tags and "-N" scale.
// r.ScreenPercentage is not touched (pinned to 100, AGENTS.md). The editor process never applies it (the CDO would
// rescale PIE and the editor's own preview of the game layer); the automation test checks the rule without the world.
//
// Trace (once per change, written as soon as the game mode opened the trace):
//   HUD-SCALE dpi=<x> app=<x> canvas=<w>x<h> window=<w>x<h> ui=<percent> uiSet=<percent> class=L|S legacy=0|1
// The HUD-LAYOUT line (field rectangle, overlap) belongs to FUmHudLayout (HB-06); it listens to OnUiScaleChanged.
#pragma once

#include "CoreMinimal.h"

struct UNMATCHED_API FUmHudScaleState {
  FIntPoint Window = FIntPoint::ZeroValue;  // game viewport, px
  float Dpi = 1.0f;                         // DPI curve at the short side (the curve the engine applies)
  int32 UiPercentSet = 100;                 // UI-ACC-001 as stored (clamped 75..150)
  int32 UiPercent = 100;                    // after the "at least 100 % under 1080" rule
  float AppScale = 1.0f;                    // UUserInterfaceSettings::ApplicationScale written by Apply
  bool bLegacy = false;                     // -S08DpiLegacy
  FIntPoint CanvasSu = FIntPoint::ZeroValue;
  bool bClassS = false;                     // ВР-H01: canvas width < 1500 su

  /** Total DPI x application scale: px per su. */
  float PxPerSu() const { return Dpi * AppScale; }
  bool operator==(const FUmHudScaleState& O) const {
    return Window == O.Window && FMath::IsNearlyEqual(Dpi, O.Dpi, 1.0e-4f) && UiPercentSet == O.UiPercentSet &&
           UiPercent == O.UiPercent && FMath::IsNearlyEqual(AppScale, O.AppScale, 1.0e-4f) && bLegacy == O.bLegacy &&
           CanvasSu == O.CanvasSu && bClassS == O.bClassS;
  }
  bool operator!=(const FUmHudScaleState& O) const { return !(*this == O); }
};

DECLARE_MULTICAST_DELEGATE_OneParam(FUmHudScaleChanged, const FUmHudScaleState&);

namespace UmHudScale {

/** -S08DpiLegacy: the engine DPI curve instead of ВР-62 (rollback). */
inline const TCHAR* const LegacyFlagName = TEXT("S08DpiLegacy");
/** ВР-H01: class L from this canvas width in su. */
inline constexpr int32 ClassLMinWidthSu = 1500;

/** The project curve ВР-62 (the keys of DefaultEngine.ini), linear between keys, constant outside. */
UNMATCHED_API float ProjectDpi(int32 ShortSide);
/** The engine default curve (BaseEngine.ini [/Script/Engine.UserInterfaceSettings]: 480 0.444, 720 0.666, 1080 1.0,
 *  8640 8.0) - the size of a client before HB-09. */
UNMATCHED_API float EngineDpi(int32 ShortSide);
/** The curve the engine applies to a window of this size now (UUserInterfaceSettings without ApplicationScale). */
UNMATCHED_API float CurveDpi(FIntPoint Window);
/** UI-ACC-001 after the ВР-62 rule: the stored percent (clamped 75..150, step 5), at least 100 under 1080. */
UNMATCHED_API int32 EffectivePercent(int32 StoredPercent, int32 ShortSide);
/** World-free state of a window: Dpi is the curve value at its short side (CurveDpi in the game). */
UNMATCHED_API FUmHudScaleState Compute(FIntPoint Window, float Dpi, int32 StoredPercent, bool bLegacy);
/** "HUD-SCALE dpi=... app=... canvas=WxH window=WxH ui=.. uiSet=.. class=L|S legacy=0|1". */
UNMATCHED_API FString TraceLine(const FUmHudScaleState& State);
/** True with -S08DpiLegacy on this command line. */
UNMATCHED_API bool LegacyRequested(const TCHAR* CommandLine);
/** The ARTLOOK field: "dpi=project" or "dpi=legacy(-S08DpiLegacy)". */
UNMATCHED_API FString ArtLookField(const TCHAR* CommandLine);

/** The state applied last in this process (zero window before the first apply). */
UNMATCHED_API const FUmHudScaleState& Current();
/** Fired after a changed state was applied: FUmHudLayout (HB-06) recomputes the class and FIELD, the icons (HB-23)
 *  pick their texture size. Same frame as the window change or the settings save. */
UNMATCHED_API FUmHudScaleChanged& OnUiScaleChanged();
/** Recomputes from the game viewport and the saved settings; applies and broadcasts only on a change. Game only
 *  (no-op in the editor process and in commandlets). Called on start, on a viewport resize and on
 *  US08UserSettings::OnChanged; callers may force it after changing the settings object directly. */
UNMATCHED_API void Refresh();

}  // namespace UmHudScale

// Art Tuner M1 (docs/art-pipeline/ART-TUNER-PLAN.md §6): -ArtView=sarpedon|marmoreal - the board, the six figures
// and the camera of a -Bench fixture WITHOUT a backend and without the bench's view walk / exit: a free view for the
// artist. The effects stay live (no -Bench freeze), the camera gets an orbit and a pan on top of the zoom rig, the keys
// 1-5 are the bench views, Tab cycles the "active" figure (hero light state), H / P / F1 switch the hero light, the pause
// and the help. Pure helpers here (tested in S08ArtViewTests.cpp); the game-mode side is S08FlowGameModeArtView.cpp.
// Nothing of this runs without the flag: the normal game and -Bench stay bit for bit.
#pragma once

#include "CoreMinimal.h"
#include "S08BoardModel.h"

class SWidget;
class STextBlock;
class SBorder;

namespace S08ArtViewSpec {
inline const TCHAR* const MapParam = TEXT("ArtView=");
/** The fixed diorama camera of the game (pitch 55 down, yaw -90: looking along -Y, INT-019). */
constexpr float DefaultPitchDeg = 55.0f;
constexpr float DefaultYawDeg = -90.0f;
constexpr float MinPitchDeg = 20.0f;
constexpr float MaxPitchDeg = 85.0f;
/** Orbit speed of a right-button drag (deg per viewport pixel). */
constexpr float YawDegPerPx = 0.25f;
constexpr float PitchDegPerPx = 0.2f;
/** A right click shorter than this (px) keeps the game's meaning (deselect); a longer one is an orbit drag. */
constexpr float DragThresholdPx = 4.0f;
/** The pan offset stays within this distance of the board centre (uu). */
constexpr float MaxPanUU = 3000.0f;
/** The camera's horizontal field of view (AS08FlowGameMode::SetupCameraForBoard). */
constexpr float HfovDeg = 35.0f;
/** The hint line at the top left disappears after this many seconds (F1 brings the full help). */
constexpr float HintSeconds = 12.0f;
}  // namespace S08ArtViewSpec

/** Orbit / pan state of the free view on top of the zoom rig's focus and distance (FS08CameraZoom). The default state
 *  reproduces the game camera exactly (pitch 55, yaw -90, no pan). */
struct UNMATCHED_API FS08ArtViewCamera {
  float YawDeg = S08ArtViewSpec::DefaultYawDeg;
  float PitchDeg = S08ArtViewSpec::DefaultPitchDeg;
  FVector2D PanUU = FVector2D::ZeroVector;

  bool IsDefault() const;
  void Reset();
  /** Right-button drag: x turns the yaw, y the pitch (clamped to MinPitchDeg..MaxPitchDeg). */
  void Orbit(const FVector2D& DeltaPx);
  /** Middle-button drag: the board follows the cursor ("grab"), scaled by the visible width at the focus distance. */
  void Pan(const FVector2D& DeltaPx, float DistanceUU, float ViewportWidthPx);
  /** Camera location / rotation looking at Focus + Pan from DistanceUU. */
  void Pose(const FVector& Focus, float DistanceUU, FVector& OutLocation, FRotator& OutRotation) const;
};

/** Runtime state of one -ArtView session (owned by the game mode; null without the flag). */
struct FS08ArtViewSession {
  FString Map;      // sarpedon | marmoreal
  FString Fixture;  // absolute path of Config/Bench/S08Bench<Map>.json (or -BenchFixture=)
  FString HeroId;   // the fixture viewer's hero (the K2 views focus it when nothing is selected)
  FString View = TEXT("K1");
  FS08ArtViewCamera Cam;
  bool bHelp = false;
  bool bHeroLightOff = false;
  bool bPaused = false;
  bool bRmbDown = false;
  bool bRmbDragging = false;
  bool bMmbDown = false;
  FVector2D RmbStart = FVector2D::ZeroVector;
  FVector2D LastMouse = FVector2D::ZeroVector;
  float HintUntil = 0.0f;
  FString StatusLine;
  TSharedPtr<SWidget> Overlay;
  TSharedPtr<SBorder> HintBox;
  TSharedPtr<SBorder> HelpBox;
  TSharedPtr<STextBlock> HintText;
  TSharedPtr<STextBlock> StatusText;
};

namespace S08ArtView {
/** -ArtView=<map> is on the command line (any value; an unknown map fails the init with a trace line). */
UNMATCHED_API bool Enabled(const TCHAR* CommandLine = nullptr);
/** The lower-case map name of -ArtView= (empty without the flag). */
UNMATCHED_API FString MapFromCommandLine(const TCHAR* CommandLine = nullptr);
/** sarpedon -> S08BenchSarpedon.json, marmoreal -> S08BenchMarmoreal.json (the original maps only, 2026-10-04). */
UNMATCHED_API bool FixtureFileFor(const FString& Map, FString& OutFileName);
UNMATCHED_API const TArray<FString>& Maps();
/** The bench views on the keys 1..5: K1, K1x0.65, K2x1.6, K2x2.5, Fitx1.45. */
UNMATCHED_API const TArray<FString>& Views();
/** Index of the next (Direction +1) / previous (-1) living fighter after Current (wraps; INDEX_NONE without one). An
 *  unknown / empty Current starts at the first (or the last) living fighter. */
UNMATCHED_API int32 NextFighterIndex(const TArray<FS08BoardFighter>& Fighters, const FString& Current, int32 Direction);
/** The help card of F1 (Russian, one key per line). */
UNMATCHED_API FString HelpText(bool bTuner);
/** The short hint line at the top left. */
UNMATCHED_API FString HintText(const FString& Map, bool bTuner);
}  // namespace S08ArtView

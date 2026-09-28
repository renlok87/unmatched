// ART-004 stage 3 T2.2 ("Art 4: HUD/input code"). World-free helpers for the
// live Cobble art preview HUD, split out of AS08FlowGameMode so the automation
// tests exercise the exact production math without a world or a viewport:
//   - FS08CameraZoom: the wheel/Space/flag zoom rig of 03 §2 (D-10) with its
//     parameters in one config (defaults <- [Unmatched.Camera] in the game ini
//     <- -S08Camera*= command-line overrides). Values are PROPOSALS (Q-302).
//   - plate placement: the fighter plate (name/HP/statuses) must not cover the
//     clickable cells of the current selection (03 §3 K-2, str. 107). The
//     overlap rule is the one tools/art/qa010 `plate` applies to the traced
//     bbox: projected full 100x100 uu cell quads, polygon-clipped to the plate
//     rectangle, a cell counts when the clipped area exceeds 0.5 px^2.
//   - QA-010 trace formatting (SHOT reachable/plate/icon lines, format fixed by
//     docs/art-pipeline/qa010/README.md and qa010lib/trace.py).
//   - input plan parsing for the flag-driven input emulation (src=flag),
//     combat icon size parsing (24/32/48 px), exactly-once damage numbers per
//     (fighter, seq), all-Medusa eligibility.
// FS08ArtHudRuntime holds the Slate widgets and per-frame state of the game
// mode; it has no reflection and no UObject references of its own.
#pragma once

#include "CoreMinimal.h"
#include "Styling/SlateBrush.h"
#include "Widgets/Layout/SConstraintCanvas.h"

class SBorder;
class SBox;
class SImage;
class STextBlock;
class SVerticalBox;

// ---------------------------------------------------------------- camera zoom

struct FS08CameraZoomConfig {
  /** Nearest wheel/flag distance in uu. 300 uu = the measured K2 5x probe of
   *  the Cobble 5x6 overview (live-k2-zoom-comparison-2026-09-28); 03 §2 asks
   *  1.6x. Q-302 decides - this is a proposal kept at the measured value. */
  float MinDistanceUU = 300.0f;
  /** Farthest wheel distance = overview / ratio (03 §2: 0.65x). */
  float OverviewOutRatio = 0.65f;
  /** Distance multiplier per wheel notch (one notch = x1.25 / /1.25). */
  float WheelStepFactor = 1.25f;
  /** Wheel/flag zoom animation (03 §2 "~200 ms"); accepted 0.15..0.25 s. */
  float ZoomAnimSeconds = 0.20f;
  /** Space: back to the overview (03 §2 "~300 ms"). */
  float OverviewReturnSeconds = 0.30f;
  /** Follow-selection from this zoom (03 §2: >= 1.2x). */
  float FollowFromZoom = 1.2f;
  FString Source = TEXT("defaults");
  TArray<FString> Issues;

  static constexpr float MinAnimSeconds = 0.15f;
  static constexpr float MaxAnimSeconds = 0.25f;

  /** Clamps every value into its accepted range; each correction is recorded
   *  in Issues (and surfaces in the CAMERA config trace line). */
  void Sanitize();
  /** [Unmatched.Camera] in the given ini file (MinDistanceUU, OverviewOutRatio,
   *  WheelStepFactor, ZoomAnimMs, OverviewReturnMs, FollowFromZoom). */
  void ApplyIni(const FString& IniFile);
  /** -S08CameraMinDist= -S08CameraOutRatio= -S08CameraStep= -S08CameraAnimMs=
   *  -S08CameraReturnMs= -S08CameraFollowFrom= */
  void ApplyCommandLine(const TCHAR* CommandLine);
  FString Describe() const;
};

enum class ES08ZoomLimit : uint8 { None, Near, Far };

inline const TCHAR* S08ZoomLimitName(ES08ZoomLimit Limit) {
  return Limit == ES08ZoomLimit::Near ? TEXT("near") : Limit == ES08ZoomLimit::Far ? TEXT("far") : TEXT("none");
}

/** Result of one distance command (wheel notch, Space, flag focus zoom). */
struct FS08ZoomStep {
  float From = 0.0f;      // target distance before the command
  float Requested = 0.0f; // unclamped request
  float To = 0.0f;        // new target distance (clamped)
  bool bClamped = false;  // the request hit a limit (or was already at it)
  ES08ZoomLimit Limit = ES08ZoomLimit::None;
  float Seconds = 0.0f;   // animation length of this command
};

/** Distance + focus rig of the fixed-angle board camera (pitch/yaw/FOV never
 *  change, D-10). Time-based smoothstep tweens of exactly the configured
 *  length replace the old open-ended FInterpTo, so "settled" is exact. */
class FS08CameraZoom {
public:
  FS08CameraZoomConfig Config;

  void Reset(float OverviewDistance);
  bool IsReady() const { return Overview > 0.0f; }
  float MinDistance() const;
  float MaxDistance() const;
  /** +1 = wheel toward the board (closer), -1 = away. Steps from the target. */
  FS08ZoomStep Wheel(int32 Direction);
  FS08ZoomStep ReturnToOverview();
  /** Flag path (-ArtPreviewFocusZoom): overview / Zoom, clamped to
   *  [MinDistance, Overview] exactly like the historical probe. */
  FS08ZoomStep FocusZoom(float Zoom);
  /** Starts a focus tween (length of the latest distance command) when the
   *  follow target changed. */
  void SetFocusTarget(const FVector& Focus);
  void Tick(float DeltaSeconds);
  /** Follow-selection is active while the TARGET zoom is >= FollowFromZoom. */
  bool WantsFollow() const;
  bool IsSettled() const;
  float ZoomOf(float Distance) const { return Distance > 0.0f ? Overview / Distance : 0.0f; }

  float Overview = 0.0f;
  float Current = 0.0f;
  float Target = 0.0f;
  FVector CurrentFocus = FVector::ZeroVector;
  FVector TargetFocus = FVector::ZeroVector;

private:
  FS08ZoomStep StartDistanceTween(float Requested, float Lo, float Hi, float Seconds);
  float DistStart = 0.0f;
  float DistElapsed = 0.0f;
  float DistDuration = 0.0f;
  FVector FocusStart = FVector::ZeroVector;
  float FocusElapsed = 0.0f;
  float FocusDuration = 0.0f;
  float LastCommandSeconds = 0.2f;
};

// ------------------------------------------------------------ screen geometry

/** Axis-aligned viewport-pixel rectangle, half-open [X0,X1) x [Y0,Y1). */
struct FS08ScreenRect {
  float X0 = 0.0f, Y0 = 0.0f, X1 = 0.0f, Y1 = 0.0f;
  FS08ScreenRect() = default;
  FS08ScreenRect(float InX0, float InY0, float InX1, float InY1)
      : X0(InX0), Y0(InY0), X1(InX1), Y1(InY1) {}
  float Width() const { return FMath::Max(0.0f, X1 - X0); }
  float Height() const { return FMath::Max(0.0f, Y1 - Y0); }
  double Area() const { return static_cast<double>(Width()) * Height(); }
  bool IsEmpty() const { return Width() <= 0.0f || Height() <= 0.0f; }
  FVector2D Center() const { return FVector2D((X0 + X1) * 0.5f, (Y0 + Y1) * 0.5f); }
  FS08ScreenRect Expand(float By) const { return FS08ScreenRect(X0 - By, Y0 - By, X1 + By, Y1 + By); }
  double IntersectionArea(const FS08ScreenRect& Other) const;
  bool Contains(const FS08ScreenRect& Inner) const {
    return Inner.X0 >= X0 && Inner.Y0 >= Y0 && Inner.X1 <= X1 && Inner.Y1 <= Y1;
  }
  /** Bounding rectangle of a point set (empty rect for an empty set). */
  static FS08ScreenRect FromPoints(const TArray<FVector2D>& Points);
};

/** One board cell projected to the viewport (4 corners at z = 0, full
 *  100x100 uu INT-019 cell, like qa010 project_cell). */
struct FS08CellQuad {
  FIntPoint Cell = FIntPoint(-1, -1);
  TArray<FVector2D> Screen;
};

namespace S08ArtHud {
/** qa010 thresholds.proposed.json plate.overlap_epsilon_px2. */
constexpr double OverlapEpsilonPx2 = 0.5;

/** Sutherland-Hodgman clip of a convex/concave polygon to a rectangle. */
TArray<FVector2D> ClipPolygonToRect(const TArray<FVector2D>& Polygon, const FS08ScreenRect& Rect);
/** Absolute shoelace area. */
double PolygonArea(const TArray<FVector2D>& Polygon);
/** Cells whose quad overlaps Rect by more than Epsilon px^2 (qa010 rule). */
int32 CountOverlaps(const FS08ScreenRect& Rect, const TArray<FS08CellQuad>& Cells,
                    double Epsilon, TArray<FIntPoint>* OutCells = nullptr,
                    double* OutArea = nullptr);

struct FPlacementInput {
  FVector2D Viewport = FVector2D::ZeroVector;
  FVector2D PlateSize = FVector2D::ZeroVector;
  FS08ScreenRect Anchor;              // on-screen box of the plate's fighter
  TArray<FS08CellQuad> Forbidden;     // destination cells of the current selection
  TArray<FS08ScreenRect> Soft;        // figures, HUD panels, icon, damage number
  float Gap = 6.0f;                   // nearest distance to the anchor box
  float Step = 8.0f;                  // ring step and slide step (px)
  int32 Rings = 60;                   // search out to Gap + Rings * Step
  float Margin = 4.0f;                // forbidden test uses the rect grown by this
  float EdgeMargin = 6.0f;            // keep the plate this far inside the viewport
};

struct FPlacementResult {
  FS08ScreenRect Rect;
  FString Candidate = TEXT("none");
  int32 Ring = -1;
  int32 ForbiddenOverlaps = 0;        // with the margin-grown rect
  double ForbiddenArea = 0.0;
  double SoftArea = 0.0;
  int32 Tested = 0;
  bool bClean = false;                // no forbidden and no soft overlap
};

/** Nearest plate position around the anchor (ring by ring; each ring slides
 *  the plate along the four sides) that covers no forbidden cell and no soft
 *  obstacle; otherwise the least bad one (forbidden count, area, soft area). */
FPlacementResult ChoosePlateRect(const FPlacementInput& In);

/** "(x,y)(x,y)..." - the qa010 `cells=` list (order as given). */
FString FormatCells(const TArray<FIntPoint>& Cells);
/** "(x0,y0,x1,y1)" rounded to whole pixels - the qa010 `bbox=` value. */
FString FormatRect(const FS08ScreenRect& Rect);
/** Stable cell order for traces: row-major (y, then x). */
void SortCells(TArray<FIntPoint>& Cells);

/** The plate/selection rule: destination cells = legal cells minus the
 *  selected fighter's own cell (the zero-step resolve is not a click target:
 *  a click there lands on the fighter itself). */
TArray<FIntPoint> DestinationCells(const TSet<uint64>& LegalCells, const FIntPoint& OwnCell);
}  // namespace S08ArtHud

/** Pinhole model of the UE board camera (horizontal FOV, FRotationMatrix axes,
 *  top-left screen origin) - identical to tools/art/qa010/qa010lib/projection.py
 *  so the automation tests can replay a traced SHOT ctx camera. The live client
 *  projects with APlayerController::ProjectWorldLocationToScreen instead. */
struct FS08PinholeCamera {
  FVector Position = FVector::ZeroVector;
  FRotator Rotation = FRotator::ZeroRotator;
  float HorizontalFovDeg = 35.0f;
  FVector2D Viewport = FVector2D(1920.0, 1080.0);
  bool Project(const FVector& World, FVector2D& OutScreen) const;
};

// ------------------------------------------------------------- input & flags

enum class ES08InputSource : uint8 { Os, Flag };
inline const TCHAR* S08InputSourceName(ES08InputSource Source) {
  return Source == ES08InputSource::Flag ? TEXT("flag") : TEXT("os");
}

/** Flag-driven input emulation steps (-ArtPreviewInputPlan=). Real OS input
 *  is T4.3; every emulated step is traced src=flag. */
enum class ES08InputStep : uint8 { WheelIn, WheelOut, Space, ClickHero, ClickAbove, ClickCell };
const TCHAR* S08InputStepName(ES08InputStep Step);
/** '+'-separated tokens (',' truncates FParse::Value): wheelin, wheelout,
 *  space, clickhero, clickabove, clickcell; "token*N" repeats (N 1..20).
 *  At most 40 steps. Unknown tokens fail the whole plan. */
bool S08ParseInputPlan(const FString& Text, TArray<ES08InputStep>& OutSteps, FString& OutError);

/** Combat icon size in px: 24, 32 or 48 (02 str. 894). Empty -> Default,
 *  anything else -> 0 (invalid). */
int32 S08ParseIconSize(const FString& Text, int32 Default);

/** Which fighters carry the isolated Medusa candidate: the Medusa hero, or
 *  every fighter with -ArtPreviewAllMedusa (ART-004 six-copies review). */
bool S08IsMedusaCandidateFighter(bool bArtPreview, bool bAllMedusa, bool bIsHero,
                                 const FString& Name);

/** Exactly-once guard keyed by (fighter id, authoritative seq). */
struct FS08SeqDedupe {
  TSet<FString> Seen;
  static FString Key(const FString& FighterId, int32 Seq) {
    return FString::Printf(TEXT("%s@%d"), *FighterId, Seq);
  }
  /** True the first time (FighterId, Seq) is offered. */
  bool Accept(const FString& FighterId, int32 Seq);
};

/** Plate status chips (ASCII: the default Slate font path, no Cyrillic risk). */
TArray<FString> S08PlateStatuses(bool bIsHero, bool bOwn, const FString& AttackType,
                                 bool bAttacker, bool bTarget,
                                 const TArray<FString>& Effects);

// ------------------------------------------------------------------ runtime

/** Slate widgets + per-frame state of the art HUD (owned by the game mode). */
struct FS08ArtHudRuntime {
  // Plate (name / HP / statuses) of the selected or hovered fighter.
  TSharedPtr<SBorder> PlateBorder;
  SConstraintCanvas::FSlot* PlateSlot = nullptr;
  TSharedPtr<STextBlock> PlateName;
  TSharedPtr<STextBlock> PlateHp;
  TSharedPtr<SBox> PlateHpFill;
  TSharedPtr<SBorder> PlateTeamChip;
  TSharedPtr<STextBlock> PlateTeamText;
  TSharedPtr<STextBlock> PlateStatusText;
  FString PlateFighterId;
  FString PlateContentKey;
  FString PlateSignature;             // inputs of the last placement search
  S08ArtHud::FPlacementResult PlateResult;
  TArray<FString> PendingTrace;       // lines built before the trace file opened
  FS08ScreenRect PlatePlanned;
  FS08ScreenRect PlateAnchor;         // on-screen figure box the plate belongs to
  FString PlateCandidate;
  int32 PlateForbiddenPlanned = 0;
  bool bPlateVisible = false;
  int32 PlateStableFrames = 0;
  FString PlateLastTraced;
  float PlateLastTraceAt = -1.0f;

  // Screen-space combat icon (24/32/48 px, exact-size texture, no mips).
  TSharedPtr<SImage> Icon;
  SConstraintCanvas::FSlot* IconSlot = nullptr;
  FSlateBrush IconBrush;
  int32 IconSize = 32;
  bool bIconTextureReady = false;
  bool bIconProbe = false;
  FString IconFighterId;
  FString IconSource;                 // combat | flag
  FS08ScreenRect IconPlanned;
  bool bIconVisible = false;

  // Hover (OS mouse only; offscreen runs never report one).
  FString HoveredFighterId;
  FVector2D FirstMouse = FVector2D(-1.0, -1.0);
  bool bMouseMoved = false;

  // HUD panels as soft obstacles.
  TWeakPtr<SWidget> CommandPanel;
  TWeakPtr<SWidget> SidePanel;
  TWeakPtr<SWidget> HandPanel;

  // Flag input emulation.
  TArray<ES08InputStep> Plan;
  int32 PlanIndex = 0;
  float PlanStartAt = -1.0f;
  float PlanStepSeconds = 0.35f;
  float PlanNextAt = -1.0f;
  bool bPlanDone = false;

  bool bEnabled = true;               // -ArtPreviewNoPlate disables plate + icon
  bool bConfigTraced = false;
};

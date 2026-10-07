// VS-4 HB-40 / HB-41 (docs/game-design/visual/06-tasks/hud.csv HB-40, HB-41; 04-hud-spec.md §2.12, §2.13, ВР-H06; the
// accepted mockup HB-38 art/imagegen/hud-feed-v1-codex, ВР-VS2-HB38-06...08, -18): the world-free rules the toast
// stack (UUmToastStack) and the subtitle capsule (UUmHudSubtitle) share - the toast kind of a string key, the hold
// time, the RU text of a reason, and the ONE placement chain of the group «toasts + subtitle».
//
//   kind       ВР-VS2-HB38-06: a why.* reason (a refusal, CUE-004) is an error (X), an ms.hint.* rule a warning (the
//              «!» triangle, the 2 su state.warning edge, the close cross while it is held), hud.toast.* and the rest
//              an info toast without a sign.
//   hold       04 §2.12: in 180, held 2-4 s (an error 4 s), out 120; a sticky toast (the hand-limit rule) until its
//              close, the end of the turn or GAME_OVER.
//   group      the toasts (at most 2, the newest at the bottom, 8 su apart, centred on the canvas) and under them the
//              subtitle (8 su, centred on the hand corridor) - one group, so the subtitle is always «под стопкой тостов».
//   chain      04 §2.12 (HB-38 delta, ВР-VS2-HB38-07 / -18), the first step that gives 0 px^2 with every obstacle:
//                1 bottom   the subtitle's bottom 4 su over the top of the hand cards, the toasts over it; without a
//                           subtitle the stack's bottom 8 su over the hand caption (or over the lowered hand);
//                2 top      the group's top at the top band (centre, y 216; class S y 162 - HB-38 P6);
//                3 upward   the smallest whole-pixel shift up from the band, never above the STATUS bottom + 8 su;
//                4 newest   only the newest toast (the older one leaves early) with the subtitle, steps 1-3 again;
//                5 fail     the attempt with the least overlap, traced as FAIL (never silent: the text still shows).
//              Obstacles are the caller's: the figure and space masks (the spaces are not one in the defense window,
//              ВР-VS2-HB38-18), every drawn HUD block, the hand caption plate + 8 su.
#pragma once

#include "CoreMinimal.h"
#include "../../S09/S09ManeuverUi.h"

enum class EUmToastKind : uint8 { Info, Warning, Error };
/** Which step of the chain placed the group. */
enum class EUmFeedPlace : uint8 { None, Bottom, Top, Upward, Newest, Fail };

namespace UmHudFeed {
inline constexpr float GapSu = 8.0f;
inline constexpr float TopBandLSu = 216.0f;       // 04 §2.12
inline constexpr float TopBandSSu = 162.0f;       // HB-38 P6 (class S)
inline constexpr float SubOverCardsSu = 4.0f;     // 04 §2.13 delta: the capsule's bottom 4 su over the cards
inline constexpr float CaptionGapSu = 8.0f;       // the stack / capsule keep 8 su from the «Рука n/max» plate
inline constexpr float ToastMinHSu = 48.0f;
inline constexpr float ToastPadSu = 16.0f;        // HB-38 toast_spec pad
inline constexpr float ToastSignSu = 24.0f;       // «!», X, × (ВР-42)
inline constexpr float ToastSignGapSu = 8.0f;
inline constexpr float ToastLinePitchSu = 20.0f;  // HB-38: 48 for one line, 16 + 20 x (n - 1) + 2 x 12 for more
inline constexpr int32 ToastMaxLines = 2;
inline constexpr int32 MaxToasts = 2;
inline constexpr float SubMaxWSu = 720.0f;        // 04 §2.13
inline constexpr float SubPadXSu = 12.0f;
inline constexpr float SubPadYSu = 5.0f;          // the line box + 2 x 5 su (HB-38 P7)
inline constexpr float SubMinHSu = 28.0f;
inline constexpr float SpeakerGapSu = 8.0f;
inline constexpr float BadgeSu = 24.0f;           // badge-refuse (IC-40), 350 ms (refuse.ms)

/** ВР-VS2-HB38-06: the look of a toast by the key of its string. */
UNMATCHED_API EUmToastKind KindOfKey(FName Key);
/** VS-4 HB-49 (the vsai-abort gate, 2026-10-07): «Позиции обновлены (пропущено n)» only when the stream came back
 *  inside the still running match - leaving the room (abort, the result, the lobby) while recovering shows nothing. */
UNMATCHED_API bool ReconnectedToastDue(bool bStillStarted, bool bHudValid, bool bAborted);
UNMATCHED_API const TCHAR* KindName(EUmToastKind Kind);
UNMATCHED_API const TCHAR* PlaceName(EUmFeedPlace Place);
/** 04 §2.12: the cap of a toast's width - 560 (L, 1080p column), 520 (L, 720p column), 440 (class S). */
UNMATCHED_API float ToastCapSu(bool bClassS, bool bTall);
/** 04 §2.12: an error holds 4 s; the others the requested time inside 2...4 s. */
UNMATCHED_API float HoldSec(EUmToastKind Kind, float RequestedSec);
/** The RU / EN text of a reason (ST_Why, else ST_Ms; the space it names first, «M13: …»; MS-E-34's order hint), the
 *  same arguments as FS09Reason::Text - never a literal. */
UNMATCHED_API FText ReasonText(const FS09Reason& Reason);
/** The height of a toast of Lines text lines (48 for one; 16 + 20 x (n - 1) + 2 x 12 for more). */
UNMATCHED_API float ToastHeightSu(int32 Lines);

/** One placement of the group. */
struct UNMATCHED_API FStackInput {
  FVector2D CanvasSu = FVector2D(1920.0, 1080.0);
  float PxPerSu = 1.0f;
  float MarginSu = 24.0f;
  /** The toasts, oldest first (sizes in su); the newest is the last. */
  TArray<FVector2D> Toasts;
  /** The subtitle capsule (zero = none). */
  FVector2D Sub = FVector2D::ZeroVector;
  /** The toasts' centre x (the canvas centre) and the capsule's (the hand corridor's centre); < 0 = the canvas centre. */
  float ToastCentreXSu = -1.0f;
  float SubCentreXSu = -1.0f;
  /** Step 1 without a subtitle: the stack's bottom (the caption top - 8, or the lowered hand's top - 8). */
  float ToastBottomSu = 0.0f;
  /** Step 1 with a subtitle: the capsule's bottom (the top of the hand cards - 4). */
  float SubBottomSu = 0.0f;
  float TopBandSu = TopBandLSu;
  /** Never above this (STATUS bottom + 8 su). */
  float MinTopSu = 80.0f;
  TArray<FBox2D> Obstacles;
};

struct UNMATCHED_API FStackResult {
  EUmFeedPlace Place = EUmFeedPlace::None;
  /** The indices (into FStackInput::Toasts) shown, oldest first, and their rectangles (su). */
  TArray<int32> Shown;
  TArray<FBox2D> ToastRects;
  FBox2D SubRect = FBox2D(ForceInit);
  /** px^2 with the obstacles (0 unless Fail). */
  double OverlapPx2 = 0.0;
  /** Group positions tried (1 + one per jump of the upward search). */
  int32 Attempts = 0;
  /** The older toasts the chain dropped (step 4). */
  int32 Dropped = 0;
  /** «top» for the gate (04 §7.1 state): the top band, the upward shift or a newest-only group placed up there. */
  bool bTop = false;
  FBox2D Bounds() const;
};

/** The chain of 04 §2.12 (see the head of this file). */
UNMATCHED_API FStackResult Place(const FStackInput& In);
/** px^2 of R with every obstacle (each counted). */
UNMATCHED_API double OverlapPx2(const FBox2D& R, const TArray<FBox2D>& Obstacles, float PxPerSu);
}  // namespace UmHudFeed

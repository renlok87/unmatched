// VS-2 HB-06 (docs/game-design/visual/06-tasks/hud.csv HB-06; 04-hud-spec.md §1.6, §2, §4.1-§4.3, §5.2 step H2;
// ВР-H01, ВР-H02, ВР-H06; HUD-RULES П6): the layout of the GAME screen.
//
//   class      ВР-H01: canvas width in su (window / (DPI x UI scale)) >= 1500 -> L, below -> S. 1920x1080 at 100 % is
//              1920x1080 su (L), 1280x720 at 100 % 1706.7x960 su (L, the "720p" column of 04 §1.6), 1920x1080 at 150 %
//              1280x720 su (S), 1280x720 at 150 % 1137.8x640 su (S).
//   rects      04 §1.6: every block at its edge anchor (left / right / top / bottom, margin 24 su in L, 16 in S;
//              OPP-HAND narrows to the room right of FIELD, ВР-VS2-10); the
//              "1080p" and "720p" columns of L differ by the canvas height (bTall = height >= 1000 su: STATUS <= 880 / 720,
//              CENTER <= 720 x 420 / 640 x 380, LOG 6 / 3 lines, DECK PANEL 380 / 340 wide).
//   FIELD      ВР-H02: the rectangle of the board cells on screen. The client projects every cell (centre +- its radius)
//              through the K1 camera after SetupCameraForBoard (UmHudField below) and recomputes it on a window or
//              UI-scale change (UmHudScale::OnUiScaleChanged). The hand corridor runs between PANEL-LOC and ACTIONS
//              (1080p 376..1540, 720p 376..1327, S 268..1040 / 268..898); a resting hand card shows
//              canvas bottom - (FIELD bottom + 8 + caption 22) su of its height, at most 208 (S 166), at least 48 - the
//              lower clamp 120 of 04 §2.6 is dropped (HB-07 delta, ВР-VS2-08): it would push the caption into FIELD.
//   overlap    persistent blocks (TOP, STATUS, SLOT, the combat edges, LOG, both panels, OPP-HAND, HAND + caption,
//              DECKS, ACTIONS) x FIELD in px^2 - 0 is the gate (04 §1.6 "Пересечения"); CENTER, BANNER, TOAST, SUB and
//              the DECK PANEL are the exceptions of 04.
//   stack      ВР-H06 / 04 §2.12-§2.13: toasts over the subtitle, both centred over the hand; when the stack would cross
//              a figure, a plate or a required cell (the caller's Avoid rects) it moves to the top strip (L y 216, S y 144),
//              the subtitle under the toasts there too.
//
// Trace (once per shot frame, AS08FlowGameMode::WriteUmHudShotLines):
//   HUD-LAYOUT class=L|S canvas=<w>x<h> scale=<px per su> field=(x,y,w,h) overlapField=<px2> window=<w>x<h> ...
// field and canvas in su (= px at 1080p 100 %). World-free: the automation tests drive Compute directly.
#pragma once

#include "CoreMinimal.h"

/** The rectangles of the GAME screen (04 §1.6). Defend = the defender's buttons under the own combat card. */
enum class EUmHudBlock : uint8 {
  Top,
  Status,
  Center,
  Banner,
  SourceSlot,
  CombatL,
  CombatR,
  Defend,
  Log,
  PanelLoc,
  PanelOpp,
  OppHand,
  Hand,
  HandCaption,
  Toast,
  Sub,
  Decks,
  DeckPanel,
  Actions,
  Num
};
constexpr int32 UmHudBlockCount = static_cast<int32>(EUmHudBlock::Num);

namespace UmHudLayout {
/** ВР-H01: class L from this canvas width (su). */
inline constexpr float ClassLMinWidthSu = 1500.0f;
/** The "1080p" column of 04 §1.6 from this canvas height (su); below it the "720p" column. */
inline constexpr float TallMinHeightSu = 1000.0f;
/** Short name of a block (trace, tests): top, status, center, banner, slot, combat.l, ... */
UNMATCHED_API const TCHAR* BlockName(EUmHudBlock Block);
/** The -S08SlateHud key of a block (04 §4.2; S08ArtLook::SlateHudKeys). */
UNMATCHED_API FName FlagKey(EUmHudBlock Block);
/** A block of the overlap gate (04 §1.6: CENTER, BANNER, TOAST, SUB, DECK PANEL are the exceptions). */
UNMATCHED_API bool IsPersistent(EUmHudBlock Block);
}  // namespace UmHudLayout

struct UNMATCHED_API FUmHudLayout {
  FVector2D CanvasSu = FVector2D::ZeroVector;
  float PxPerSu = 1.0f;
  bool bClassS = false;
  bool bTall = true;
  float MarginSu = 24.0f;
  bool bHasField = false;
  FBox2D FieldSu = FBox2D(ForceInit);
  FBox2D Rects[UmHudBlockCount];
  float HandLeftSu = 0.0f;
  float HandRightSu = 0.0f;
  /** Visible height of a resting hand card (ВР-H02). */
  float HandVisibleSu = 0.0f;
  /** Persistent blocks x FIELD, px^2. */
  double OverlapFieldPx2 = 0.0;

  /** CanvasSu = window / PxPerSu (fractional: 1137.78 x 640 at 1280x720 150 %); Field in su or null. */
  static FUmHudLayout Compute(const FVector2D& InCanvasSu, float InPxPerSu, const FBox2D* InFieldSu);
  const FBox2D& Rect(EUmHudBlock Block) const { return Rects[static_cast<int32>(Block)]; }
  bool HasRect(EUmHudBlock Block) const { return Rect(Block).bIsValid != 0; }
  /** Where a drawn or discarded card flies (centre of the deck / discard chip, su). */
  FVector2D DeckChipCentreSu() const;
  FVector2D DiscardChipCentreSu() const;
  /** "HUD-LAYOUT class=L canvas=1920x1080 scale=1.000 field=(410,255,1030,595) overlapField=0 ..." */
  FString TraceLine(const FIntPoint& WindowPx = FIntPoint::ZeroValue) const;
  /** ВР-H06: the rect of the toast stack (Which = Toast, its height ToastH) or the subtitle (Which = Sub) for a stack
   *  of ToastH + gap + SubH su (either may be 0); bottom over the hand unless it crosses one of Avoid (su), then the
   *  top strip. bOutTop tells which. HandTopSu >= 0: the top of the hand actually drawn (the Slate hand panel before
   *  H7 is taller than the layout's row) - the stack stays over the higher of the two. */
  FBox2D StackRect(EUmHudBlock Which, float ToastWidthSu, float ToastHeightSu, float SubWidthSu, float SubHeightSu,
                   const TArray<FBox2D>& Avoid, bool& bOutTop, float HandTopSu = -1.0f) const;
  /** Room between the canvas edge and FIELD on one side (su, >= 0): what a left / right edge panel may take without
   *  crossing the cells. Without FIELD: the combat edge width of the class. */
  float EdgeRoomSu(bool bLeft) const;
};

/** ВР-H02: FIELD from the K1 camera - a world-free pinhole model of UE's camera (horizontal FOV kept, AspectRatio
 *  MaintainXFOV, screen y down), the same that PlayerController::ProjectWorldLocationToScreen applies. */
namespace UmHudField {
struct FView {
  FVector Location = FVector::ZeroVector;
  FRotator Rotation = FRotator::ZeroRotator;
  float HFovDeg = 35.0f;
  FVector2D ViewportPx = FVector2D(1920.0, 1080.0);
};
/** World point -> viewport px; false behind the camera. */
UNMATCHED_API bool Project(const FView& View, const FVector& World, FVector2D& OutPx);
/** Envelope (px) of the cell circles: every centre and 8 points of its radius on the play plane. Invalid box when no
 *  point projects. */
UNMATCHED_API FBox2D CellsEnvelopePx(const FView& View, const TArray<FVector>& Centres, float RadiusUU);
}  // namespace UmHudField

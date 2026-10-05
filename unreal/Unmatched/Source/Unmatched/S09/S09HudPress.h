// DE-014 (W-21, UI-INP-011 of docs/game-design/02-ux-ui-spec.md §5; SD-46):
// a press on a HUD button, a hand card or the deck/discard control is never
// lost and never silent.
//
// Why a plain SButton is not enough: AS08FlowGameMode::RefreshHud rebuilds the
// whole Slate HUD (ClearChildren + SNew) on every snapshot, toast and, in the
// combat windows, every 0.25 s for the deadline countdown. An SButton clicks
// only when the press and the release reach the SAME widget instance (it
// captures the mouse on the press); a rebuild between them destroys that
// instance and the release lands on its new twin, which was never pressed -
// the click vanishes without a sound or a reason (the DE defect of R-01 /
// P0-3: 6 of 52 presses). A disabled SButton drops the press as well.
//
// Here the press belongs to a LOGICAL element id, not to a widget instance:
//   - FS09HudPressArbiter (world-free, headless-testable) remembers the id of
//     the press and counts the HUD rebuilds since it; the release over the
//     same id is the click (MS-D-17: no hover, no minimum hold - a press and
//     a release in one tick count); a release over another element after a
//     rebuild moved the layout is a refusal with why.state.changed (never a
//     silent loss); a release over another element without a rebuild is the
//     player's own drag-away cancel (MS-R-34).
//   - SS09HudPress is the Slate element: never disabled, not focusable (the
//     viewport keeps the keyboard focus), hover/press highlight of its own;
//     its content (the old SButton look) is hit-test invisible. The game mode
//     decides on activation: the action with a visible response, or CUE-004
//     with a why.* reason when the element is blocked right now.
#pragma once

#include "CoreMinimal.h"
#include "S09ManeuverUi.h"
#include "Widgets/DeclarativeSyntaxSupport.h"
#include "Widgets/SCompoundWidget.h"

/** What one release resolved to. */
enum class ES09HudPressResult : uint8 {
  None,      // a release without a press (the press began off the HUD)
  Act,       // the click: the element's action runs (or its block reason shows)
  Refused,   // CUE-004 with Reason (the layout moved under the cursor)
  Cancelled, // released over another element / off the HUD, no rebuild: MS-R-34
};

const TCHAR* S09HudPressResultName(ES09HudPressResult Result);

struct UNMATCHED_API FS09HudPressOutcome {
  ES09HudPressResult Result = ES09HudPressResult::None;
  FName PressedId;   // element of the press (NAME_None without one)
  FName ReleasedId;  // element under the release (NAME_None off the HUD)
  FS09Reason Reason; // set for Refused
  int32 Rebuilds = 0; // HUD rebuilds between the press and the release
  uint64 PressFrame = 0;
  uint64 ReleaseFrame = 0;
};

class UNMATCHED_API FS09HudPressArbiter {
public:
  /** Left button down over element Id (any HUD element, blocked or not). */
  void Press(FName Id, uint64 Frame);
  /** Left button up over element OverId (NAME_None: off every HUD element). */
  FS09HudPressOutcome Release(FName OverId, uint64 Frame);
  /** RefreshHud rebuilt the widgets (the pressed instance, if any, is gone). */
  void NoteRebuild() {
    ++RebuildSerial;
    if (bPressed) ++PressRebuilds;
  }
  /** The application lost the mouse (focus loss, window deactivated): the
   *  pending press is dropped like MS-E-104 on the board. */
  void Reset();
  bool IsPressed() const { return bPressed; }
  bool IsPressed(FName Id) const { return bPressed && PressedId == Id; }
  FName GetPressedId() const { return PressedId; }
  int32 GetRebuildSerial() const { return RebuildSerial; }
  /** The frame a press or a release is stamped with: GFrameCounter, or the
   *  clock a test steps through a hold (Unmatched.S09.HudPress.SyntheticClicks). */
  uint64 Now() const;
  void SetFrameClock(TFunction<uint64()> InClock) { FrameClock = MoveTemp(InClock); }

  /** The element's answer to a resolved release: an Act whose element is
   *  blocked right now (BlockedNow set) becomes Refused with that reason
   *  (CUE-004); everything else stays as resolved. */
  static FS09HudPressOutcome Decide(const FS09HudPressOutcome& Outcome, const FS09Reason& BlockedNow);
  /** "HUD-PRESS id=<id> result=act|refused|cancelled over=<id> rebuilds=N
   *  frames=<press>-><release>" (+ " why=<key>" when refused) - the response
   *  trace of UI-INP-011; the game mode adds "action=<...>" or the CUE-004 key. */
  static FString TraceLine(const FS09HudPressOutcome& Outcome);

private:
  bool bPressed = false;
  FName PressedId;
  uint64 PressFrame = 0;
  int32 PressRebuilds = 0;
  int32 RebuildSerial = 0;
  TFunction<uint64()> FrameClock;
};

/** DE-015 (W-22, SD-47; move-selection 03 §5 MS-R-79): input of the own turn is
 *  open from the frame the snapshot that handed the turn over is applied - no
 *  ring, banner or timer gates it. The game mode's handlers read the applied
 *  snapshot synchronously, so the proof is a trace pair:
 *    "TURN-INPUT open seq=<n> frame=<f> gate=none" when an applied snapshot
 *        hands the turn to the viewer,
 *    "TURN-INPUT first src=hud|board id=<element> result=act|refused
 *        frame=<f> open=<f0> dframes=<f-f0> [why=<key>]" for the first
 *        resolved mouse input after it.
 *  World-free (headless-testable); an empty string = nothing to trace. */
class UNMATCHED_API FS09TurnInputWatch {
public:
  /** Every applied snapshot (HandleApplied): opens the watch on the
   *  transition into the viewer's turn; leaving the turn (or the result
   *  screen) closes it without a line. */
  FString OnApplied(bool bViewerTurn, bool bGameOver, int32 Seq, uint64 Frame);
  /** A resolved mouse input (a HUD press or a board release that answered):
   *  the first one after "open" is traced and closes the watch. */
  FString NoteInput(const TCHAR* Src, const FString& Id, bool bAct, const FS09Reason& Why, uint64 Frame);
  bool IsOpen() const { return bOpen; }

private:
  bool bViewerTurn = false;
  bool bOpen = false;
  uint64 OpenFrame = 0;
};

DECLARE_DELEGATE_OneParam(FS09OnHudPressOutcome, const FS09HudPressOutcome&);

/** One pressable HUD element (button, hand card, deck/discard control). */
class UNMATCHED_API SS09HudPress : public SCompoundWidget {
public:
  SLATE_BEGIN_ARGS(SS09HudPress) {}
    /** Logical element id: stable across HUD rebuilds ("hud.end.turn", "hand.2"). */
    SLATE_ARGUMENT(FName, Id)
    SLATE_ARGUMENT(TSharedPtr<FS09HudPressArbiter>, Arbiter)
    /** Every resolved release (Act / Refused; a cancel or a stray release is
     *  not reported). Act runs THIS instance's action - the current widget,
     *  so its captured state is the fresh one after a rebuild. */
    SLATE_EVENT(FS09OnHudPressOutcome, OnOutcome)
    SLATE_DEFAULT_SLOT(FArguments, Content)
  SLATE_END_ARGS()

  void Construct(const FArguments& InArgs);
  FName GetId() const { return Id; }

  /** The HUD element exactly as the game mode builds it (MakeHudPress): the
   *  old SButton look as content, dimmed when the element is blocked now, and
   *  never the target of the press (the content is hit-test invisible). */
  static TSharedRef<SS09HudPress> MakeButton(FName Id, const TSharedPtr<FS09HudPressArbiter>& Arbiter,
                                             const FS09OnHudPressOutcome& OnOutcome, const FMargin& Padding,
                                             const FLinearColor& Tint, bool bDimmed,
                                             const TSharedRef<SWidget>& Label);

  virtual FReply OnMouseButtonDown(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;
  virtual FReply OnMouseButtonDoubleClick(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;
  virtual FReply OnMouseButtonUp(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) override;
  virtual bool SupportsKeyboardFocus() const override { return false; }

private:
  FSlateColor HighlightColor() const;

  FName Id;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FS09OnHudPressOutcome OnOutcome;
};

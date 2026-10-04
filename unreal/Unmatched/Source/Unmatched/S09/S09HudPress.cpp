#include "S09HudPress.h"

#include "Application/SlateApplicationBase.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SOverlay.h"

const TCHAR* S09HudPressResultName(ES09HudPressResult Result) {
  switch (Result) {
    case ES09HudPressResult::Act:
      return TEXT("act");
    case ES09HudPressResult::Refused:
      return TEXT("refused");
    case ES09HudPressResult::Cancelled:
      return TEXT("cancelled");
    default:
      return TEXT("none");
  }
}

// ---- FS09HudPressArbiter ------------------------------------------------------

void FS09HudPressArbiter::Press(FName Id, uint64 Frame) {
  bPressed = !Id.IsNone();
  PressedId = Id;
  PressFrame = Frame;
  PressRebuilds = 0;
}

FS09HudPressOutcome FS09HudPressArbiter::Release(FName OverId, uint64 Frame) {
  FS09HudPressOutcome Out;
  Out.ReleasedId = OverId;
  Out.ReleaseFrame = Frame;
  if (!bPressed) return Out; // the press began off the HUD: not a HUD click
  Out.PressedId = PressedId;
  Out.PressFrame = PressFrame;
  Out.Rebuilds = PressRebuilds;
  if (OverId == PressedId) {
    Out.Result = ES09HudPressResult::Act;
  } else if (PressRebuilds > 0) {
    // The HUD was rebuilt under a held press and another element (or none)
    // is under the cursor now: the player did not move away on purpose, so
    // the press is refused with a reason instead of vanishing.
    Out.Result = ES09HudPressResult::Refused;
    Out.Reason = FS09Reason::Make(TEXT("why.state.changed"));
  } else {
    Out.Result = ES09HudPressResult::Cancelled; // MS-R-34: a drag away cancels
  }
  Reset();
  return Out;
}

void FS09HudPressArbiter::Reset() {
  bPressed = false;
  PressedId = NAME_None;
  PressFrame = 0;
  PressRebuilds = 0;
}

FS09HudPressOutcome FS09HudPressArbiter::Decide(const FS09HudPressOutcome& Outcome, const FS09Reason& BlockedNow) {
  FS09HudPressOutcome Out = Outcome;
  if (Out.Result == ES09HudPressResult::Act && BlockedNow.IsSet()) {
    Out.Result = ES09HudPressResult::Refused;
    Out.Reason = BlockedNow;
  }
  return Out;
}

FString FS09HudPressArbiter::TraceLine(const FS09HudPressOutcome& Outcome) {
  FString Line = FString::Printf(
      TEXT("HUD-PRESS id=%s result=%s over=%s rebuilds=%d frames=%llu->%llu"),
      Outcome.PressedId.IsNone() ? TEXT("none") : *Outcome.PressedId.ToString(),
      S09HudPressResultName(Outcome.Result),
      Outcome.ReleasedId.IsNone() ? TEXT("none") : *Outcome.ReleasedId.ToString(), Outcome.Rebuilds,
      static_cast<unsigned long long>(Outcome.PressFrame), static_cast<unsigned long long>(Outcome.ReleaseFrame));
  if (Outcome.Reason.IsSet()) Line += TEXT(" why=") + Outcome.Reason.Key.ToString();
  return Line;
}

// ---- SS09HudPress --------------------------------------------------------------

void SS09HudPress::Construct(const FArguments& InArgs) {
  Id = InArgs._Id;
  Arbiter = InArgs._Arbiter;
  OnOutcome = InArgs._OnOutcome;
  // The content (the SButton look) never takes the mouse: the press and the
  // release always reach this element, whatever instance of it is alive.
  ChildSlot
      [SNew(SOverlay) +
       SOverlay::Slot()[SNew(SBox).Visibility(EVisibility::HitTestInvisible)[InArgs._Content.Widget]] +
       SOverlay::Slot()
           [SNew(SBorder)
                .Visibility(EVisibility::HitTestInvisible)
                .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
                .BorderBackgroundColor(this, &SS09HudPress::HighlightColor)]];
}

FSlateColor SS09HudPress::HighlightColor() const {
  // Hover rim in the same frame (tl:51); a held press reads stronger.
  const bool bHeld = Arbiter.IsValid() && Arbiter->IsPressed(Id);
  const float Alpha = bHeld ? 0.22f : IsHovered() ? 0.10f : 0.0f;
  return FSlateColor(FLinearColor(1.0f, 1.0f, 1.0f, Alpha));
}

FReply SS09HudPress::OnMouseButtonDown(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) {
  if (MouseEvent.GetEffectingButton() != EKeys::LeftMouseButton || !Arbiter.IsValid()) return FReply::Unhandled();
  Arbiter->Press(Id, GFrameCounter);
  // Capture keeps the release with this instance while it lives; when a
  // rebuild destroys it, Slate routes the release to the element under the
  // cursor - the arbiter, not the capture, decides the click.
  return FReply::Handled().CaptureMouse(AsShared());
}

FReply SS09HudPress::OnMouseButtonDoubleClick(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) {
  // The second press of a fast double click is a press like any other.
  return OnMouseButtonDown(MyGeometry, MouseEvent);
}

FReply SS09HudPress::OnMouseButtonUp(const FGeometry& MyGeometry, const FPointerEvent& MouseEvent) {
  if (MouseEvent.GetEffectingButton() != EKeys::LeftMouseButton || !Arbiter.IsValid()) return FReply::Unhandled();
  // Released over this element (geometry test, no hover state needed) or,
  // while this instance holds the capture, possibly outside it.
  const bool bOver = MyGeometry.IsUnderLocation(MouseEvent.GetScreenSpacePosition());
  const FS09HudPressOutcome Outcome = Arbiter->Release(bOver ? Id : NAME_None, GFrameCounter);
  FReply Reply = FReply::Handled();
  if (FSlateApplicationBase::IsInitialized() && HasMouseCapture()) Reply.ReleaseMouseCapture();
  if (Outcome.Result == ES09HudPressResult::Act || Outcome.Result == ES09HudPressResult::Refused) {
    OnOutcome.ExecuteIfBound(Outcome);
  }
  return Reply;
}

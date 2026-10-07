// VS-3: the Slate portrait column - see UmSlatePortraits.h.
#include "UmSlatePortraits.h"

#include "../S08ArtHudStyle.h"
#include "../S08TurnPortraitWidget.h"
#include "Widgets/Layout/SConstraintCanvas.h"
#include "Widgets/SBoxPanel.h"

namespace UmSlatePortraits {
bool Build(UWorld* World, const TSharedRef<SConstraintCanvas>& Canvas, const FS08TurnHudLook& Look, FColumn& Out) {
  Out = FColumn();
  if (!World) return false;
  US08TurnPortraitWidget* Opp = US08TurnPortraitWidget::Create(World);  // VS-2 CP-08: WBP_UmPortrait when imported
  US08TurnPortraitWidget* Own = US08TurnPortraitWidget::Create(World);
  if (!Opp || !Own) return false;
  const FS08ArtHudPlateStyle Chips;
  Opp->Setup(true, Look, Chips.TeamChipColor(1));
  Own->Setup(false, Look, Chips.TeamChipColor(0));
  for (US08TurnPortraitWidget* Portrait : {Opp, Own}) {
    Portrait->SetVisibility(ESlateVisibility::Collapsed);  // shown with the live match HUD (TickTurnHud)
    Portrait->SetTrackerOpacity(Portrait->IsOpponent() ? 0.0f : 1.0f);
  }
  TSharedPtr<SVerticalBox> Column;
  Canvas->AddSlot()
      .Anchors(FAnchors(0.0f, 1.0f))
      .Alignment(FVector2D(0.0f, 1.0f))
      .Offset(FMargin(EdgeSu, -EdgeSu, 0.0f, 0.0f))
      .AutoSize(true)
      [SAssignNew(Column, SVerticalBox).Visibility(EVisibility::SelfHitTestInvisible) +
       SVerticalBox::Slot().AutoHeight().Padding(0.0f, 0.0f, 0.0f, GapSu)[Opp->TakeWidget()] +
       SVerticalBox::Slot().AutoHeight()[Own->TakeWidget()]];
  Out.Opponent = Opp;
  Out.Own = Own;
  Out.Column = Column;
  return true;
}
}  // namespace UmSlatePortraits

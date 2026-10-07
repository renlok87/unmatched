// VS-3 HB-47: the progress bar - see UmProgressBar.h.
#include "UmProgressBar.h"

#include "../S08IconMotion.h"
#include "UmHudScale.h"
#include "UmHudTheme.h"
#include "Blueprint/WidgetTree.h"
#include "Components/ProgressBar.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Styling/SlateTypes.h"

bool UUmProgressBar::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UVerticalBox* Column = Tree.ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), FName(TEXT("Column")));
  Column->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(Column, nullptr)) return Fail(TEXT("Column"));
  USizeBox* BarBox = Tree.ConstructWidget<USizeBox>(USizeBox::StaticClass(), FName(TEXT("BarBox")));
  BarBox->SetWidthOverride(WidthSu);
  BarBox->SetHeightOverride(HeightSu);
  if (!Attach(BarBox, Column)) return Fail(TEXT("BarBox"));
  UProgressBar* BarW = Tree.ConstructWidget<UProgressBar>(UProgressBar::StaticClass(), FName(TEXT("Bar")));
  if (!Attach(BarW, BarBox)) return Fail(TEXT("Bar"));
  UTextBlock* CaptionW = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("Caption")));
  CaptionW->SetFont(Theme.Font(TEXT("type.caption")));
  CaptionW->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.secondary"))));
  CaptionW->SetShadowOffset(FVector2D::ZeroVector);
  CaptionW->SetJustification(ETextJustify::Center);
  if (!Attach(CaptionW, Column)) return Fail(TEXT("Caption"));
  if (UVerticalBoxSlot* S = Cast<UVerticalBoxSlot>(CaptionW->Slot)) {
    // the caption 8 su under the bar (two tag.padding.x steps)
    S->SetPadding(FMargin(0.0f, 2.0f * Theme.SpaceSu(TEXT("tag.padding.x")), 0.0f, 0.0f));
    S->SetHorizontalAlignment(HAlign_Center);
  }
  return true;
}

bool UUmProgressBar::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  if (!WidgetTree->RootWidget) {
    FString Error;
    UWidgetTree* Tree = WidgetTree;
    const bool bOk = BuildDefaultTree(*Tree, [Tree](UWidget* Child, UPanelWidget* Parent) {
      if (!Parent) {
        Tree->RootWidget = Child;
        return true;
      }
      return Parent->AddChild(Child) != nullptr;
    }, &Error);
    if (!bOk) UE_LOG(LogTemp, Error, TEXT("UMHUD progress default tree: %s"), *Error);
  }
  Bar = Cast<UProgressBar>(WidgetTree->FindWidget(FName(TEXT("Bar"))));
  Caption = Cast<UTextBlock>(WidgetTree->FindWidget(FName(TEXT("Caption"))));
  ApplyStyle();
  SetVisibility(ESlateVisibility::Collapsed);
  return bFirst;
}

bool UUmProgressBar::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Bar) Missing.Add(TEXT("Bar"));
  if (!Caption) Missing.Add(TEXT("Caption"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmProgressBar::ApplyStyle() {
  if (!Bar) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const float PxPerSu = UmHudScale::Current().PxPerSu();
  FProgressBarStyle Style = Bar->GetWidgetStyle();
  if (const FSlateBrush* Track = Theme.SkinFor(TEXT("progress.track"), PxPerSu)) Style.SetBackgroundImage(*Track);
  if (const FSlateBrush* Fill = Theme.SkinFor(TEXT("progress.fill"), PxPerSu)) {
    Style.SetFillImage(*Fill);
    Style.SetMarqueeImage(*Fill);
  }
  Bar->SetWidgetStyle(Style);
  Bar->SetFillColorAndOpacity(FLinearColor::White);  // the skin carries card.cream; no tint over it
  Bar->SetBarFillType(EProgressBarFillType::LeftToRight);
}

void UUmProgressBar::ApplyModel(float InPercent, const FText& Stage, double NowMs) {
  Percent = FMath::Clamp(InPercent, 0.0f, 1.0f);
  if (Bar) Bar->SetPercent(Percent);
  bHasCaption = !Stage.IsEmpty();
  if (Caption) Caption->SetText(Stage);
  if (bHasCaption) {
    NoCaptionSinceMs = -1.0;
  } else if (NoCaptionSinceMs < 0.0) {
    NoCaptionSinceMs = NowMs;
  }
}

FString UUmProgressBar::SetWaiting(bool bWaiting, double NowMs, const TCHAR* Where) {
  if (bWaiting) Delay.Begin(NowMs);
  const double Waited = Delay.WaitedMs(NowMs);
  const bool bWant = bWaiting && Delay.IsShown(NowMs);
  if (!bWaiting) Delay.End();
  if (bWant == bShown) return FString();
  bShown = bWant;
  SetVisibility(bShown ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  return UmLoader::TraceLine(UmLoader::EKind::Progress, bShown, Where, Waited, S08IconMotion::IsReducedMotion()) +
         FString::Printf(TEXT(" caption=%d percent=%.2f"), bHasCaption ? 1 : 0, Percent);
}

bool UUmProgressBar::HasCaptionDefect(double NowMs) const {
  return bShown && !bHasCaption && NoCaptionSinceMs >= 0.0 && NowMs - NoCaptionSinceMs > UmLoader::CaptionGraceMs;
}

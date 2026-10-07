// VS-3 HB-47: the row skeleton - see UmSkeletonRows.h.
#include "UmSkeletonRows.h"


#include "../S08IconMotion.h"
#include "UmHudTheme.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/SizeBox.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "HAL/PlatformTime.h"

bool UUmSkeletonRows::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  UVerticalBox* RowsW = Tree.ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), FName(TEXT("Rows")));
  RowsW->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(RowsW, nullptr)) {
    if (OutError) *OutError = TEXT("attach failed: Rows");
    return false;
  }
  return true;
}

bool UUmSkeletonRows::Initialize() {
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
    if (!bOk) UE_LOG(LogTemp, Error, TEXT("UMHUD skeleton default tree: %s"), *Error);
  }
  Rows = Cast<UVerticalBox>(WidgetTree->FindWidget(FName(TEXT("Rows"))));
  SetVisibility(ESlateVisibility::Collapsed);
  return bFirst;
}

bool UUmSkeletonRows::HasAllParts(FString* OutMissing) const {
  if (OutMissing) *OutMissing = Rows ? FString() : FString(TEXT("Rows"));
  return Rows != nullptr;
}

bool UUmSkeletonRows::IsReduced() const {
  return ReducedOverride >= 0 ? ReducedOverride == 1 : S08IconMotion::IsReducedMotion();
}

double UUmSkeletonRows::NowMs() const { return ClockOverrideMs >= 0.0 ? ClockOverrideMs : FPlatformTime::Seconds() * 1000.0; }

void UUmSkeletonRows::SetRows(int32 N, float InRowSu) {
  if (!Rows || !WidgetTree) return;
  N = FMath::Max(0, N);
  const bool bHeight = !FMath::IsNearlyEqual(InRowSu, RowSu);
  RowSu = InRowSu;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  // the pool grows once; extra rows collapse
  while (Rows->GetChildrenCount() < N) {
    USizeBox* Box = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
    UOverlay* Stack = WidgetTree->ConstructWidget<UOverlay>(UOverlay::StaticClass());
    UImage* Cell = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass());
    Cell->SetColorAndOpacity(Theme.Color(TEXT("panel.bg.inset")));
    UImage* Divider = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass());
    Divider->SetBrush(UmLoader::LineBrush());  // 1 su high (the default image brush is 32 su)
    Divider->SetColorAndOpacity(Theme.Color(TEXT("panel.divider")));
    Box->SetContent(Stack);
    if (UOverlaySlot* S = Stack->AddChildToOverlay(Cell)) {
      S->SetHorizontalAlignment(HAlign_Fill);
      S->SetVerticalAlignment(VAlign_Fill);
    }
    if (UOverlaySlot* S = Stack->AddChildToOverlay(Divider)) {
      S->SetHorizontalAlignment(HAlign_Fill);
      S->SetVerticalAlignment(VAlign_Bottom);
    }
    if (UVerticalBoxSlot* S = Rows->AddChildToVerticalBox(Box)) S->SetHorizontalAlignment(HAlign_Fill);
  }
  for (int32 I = 0; I < Rows->GetChildrenCount(); ++I) {
    USizeBox* Box = Cast<USizeBox>(Rows->GetChildAt(I));
    if (!Box) continue;
    if (bHeight || I >= RowCount) Box->SetHeightOverride(RowSu);
    Box->SetVisibility(I < N ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  }
  RowCount = N;
}

FString UUmSkeletonRows::SetWaiting(bool bWaiting, double InNowMs, const TCHAR* Where) {
  if (bWaiting) Delay.Begin(InNowMs);
  const double Waited = Delay.WaitedMs(InNowMs);
  const bool bWant = bWaiting && Delay.IsShown(InNowMs);
  if (!bWaiting) Delay.End();
  if (bWant == bShown) return FString();
  bShown = bWant;
  // the pulse runs on the widget clock (the tick); it starts at its top (1.0) when the skeleton appears
  ShownAtMs = NowMs();
  PulseNow = -1.0f;
  SetVisibility(bShown ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  if (bShown) StepPulse(ShownAtMs);
  return UmLoader::TraceLine(UmLoader::EKind::Skeleton, bShown, Where, Waited, IsReduced());
}

void UUmSkeletonRows::StepPulse(double InNowMs) {
  const float Want = UmLoader::SkeletonOpacity(InNowMs - ShownAtMs, IsReduced());
  if (FMath::IsNearlyEqual(Want, PulseNow, 1.0e-3f)) return;
  PulseNow = Want;
  SetRenderOpacity(PulseNow);
}

void UUmSkeletonRows::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  ++TickCount;
  if (bShown && !IsReduced()) StepPulse(NowMs());
}

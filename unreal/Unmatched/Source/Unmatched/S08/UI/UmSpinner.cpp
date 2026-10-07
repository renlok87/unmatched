// VS-3 HB-47: the loaders - see UmSpinner.h.
#include "UmSpinner.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08IconMotion.h"
#include "UmGameHud.h"
#include "UmHudScale.h"
#include "Blueprint/WidgetTree.h"
#include "Components/SizeBox.h"

const TCHAR* const UUmSpinner::WidgetBlueprintPath = TEXT("/Game/S08/UI/Common/WBP_UmSpinner");

namespace UmLoader {
const TCHAR* KindName(EKind Kind) {
  switch (Kind) {
    case EKind::Progress: return TEXT("progress");
    case EKind::Skeleton: return TEXT("skeleton");
    default: return TEXT("spinner");
  }
}

FString TraceLine(EKind Kind, bool bShown, const TCHAR* Where, double WaitMs, bool bReduced) {
  return FString::Printf(TEXT("HUD-LOADER kind=%s shown=%d where=%s waitMs=%.0f reduced=%d"), KindName(Kind), bShown ? 1 : 0,
                         Where && *Where ? Where : TEXT("-"), WaitMs, bReduced ? 1 : 0);
}

FSlateBrush LineBrush() {
  FSlateBrush B;
  B.ImageSize = FVector2D(1.0, 1.0);
  B.DrawAs = ESlateBrushDrawType::Image;
  return B;
}

float SkeletonOpacity(double TMs, bool bReduced) {
  if (bReduced) return SkeletonReduced;
  // a cosine from the top: 1.0 at 0, 0.6 at half the period, 1.0 at the period
  const double Phase = FMath::Fmod(FMath::Max(0.0, TMs), static_cast<double>(SkeletonPeriodMs)) / SkeletonPeriodMs;
  const double C = 0.5 + 0.5 * FMath::Cos(2.0 * UE_DOUBLE_PI * Phase);
  return static_cast<float>(SkeletonLow + (SkeletonHigh - SkeletonLow) * C);
}
}  // namespace UmLoader

UClass* UUmSpinner::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmSpinner::StaticClass(), WidgetBlueprintPath); }

bool UUmSpinner::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  USizeBox* BoxW = Tree.ConstructWidget<USizeBox>(USizeBox::StaticClass(), FName(TEXT("Box")));
  BoxW->SetWidthOverride(UmLoader::SpinnerSmallSu);
  BoxW->SetHeightOverride(UmLoader::SpinnerSmallSu);
  BoxW->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(BoxW, nullptr)) return Fail(TEXT("Box"));
  US08AnimatedIconWidget* IconW = Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("Icon")));
  if (!Attach(IconW, BoxW)) return Fail(TEXT("Icon"));
  return true;
}

bool UUmSpinner::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  if (!WidgetTree->RootWidget) {
    FString Error;
    UWidgetTree* Tree = WidgetTree;
    bCodeDefaultTree = BuildDefaultTree(*Tree, [Tree](UWidget* Child, UPanelWidget* Parent) {
      if (!Parent) {
        Tree->RootWidget = Child;
        return true;
      }
      return Parent->AddChild(Child) != nullptr;
    }, &Error);
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD spinner default tree: %s"), *Error);
  }
  Box = Cast<USizeBox>(WidgetTree->FindWidget(FName(TEXT("Box"))));
  Icon = Cast<US08AnimatedIconWidget>(WidgetTree->FindWidget(FName(TEXT("Icon"))));
  ApplyIcon();
  // hidden until a wait passes 300 ms (no tick meanwhile)
  SetVisibility(ESlateVisibility::Collapsed);
  return bFirst;
}

bool UUmSpinner::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Box) Missing.Add(TEXT("Box"));
  if (!Icon) Missing.Add(TEXT("Icon"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

bool UUmSpinner::IsReduced() const {
  return ReducedOverride >= 0 ? ReducedOverride == 1 : S08IconMotion::IsReducedMotion();
}

void UUmSpinner::ApplyIcon() {
  if (Box) {
    Box->SetWidthOverride(SizeSu);
    Box->SetHeightOverride(SizeSu);
  }
  if (!Icon) return;
  bool bClamped = false;
  const int32 Px = S08IconMotion::ExportSizePx(SizeSu, UmHudScale::Current().PxPerSu(), &bClamped);
  if (Icon->SetIcon(TEXT("loader-spinner"), SizeSu, Px)) {
    Icon->SetDisplaySizeSu(SizeSu);
    if (Icon->IsReducedMotion() != IsReduced()) Icon->SetReducedMotion(IsReduced());
    Icon->ShowAtRest();
  }
}

void UUmSpinner::SetSizeSu(float Su) {
  const float Want = Su >= UmLoader::SpinnerLargeSu ? UmLoader::SpinnerLargeSu : UmLoader::SpinnerSmallSu;
  if (FMath::IsNearlyEqual(Want, SizeSu)) return;
  SizeSu = Want;
  ApplyIcon();
}

FString UUmSpinner::SetWaiting(bool bWaiting, double NowMs, const TCHAR* Where) {
  if (bWaiting) {
    Delay.Begin(NowMs);
  }
  const double Waited = Delay.WaitedMs(NowMs);
  const bool bWant = bWaiting && Delay.IsShown(NowMs);
  if (!bWaiting) Delay.End();
  if (bWant == bShown) return FString();
  bShown = bWant;
  SetVisibility(bShown ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  if (bShown && Icon) {
    // the contract loop from its first step (reduced: the contract's 250 ms steps)
    if (Icon->IsReducedMotion() != IsReduced()) {
      Icon->SetReducedMotion(IsReduced());
      Icon->ShowAtRest();
    }
    Icon->PlayAnim(TEXT("cycle"));
  }
  return UmLoader::TraceLine(UmLoader::EKind::Spinner, bShown, Where, Waited, IsReduced());
}

void UUmSpinner::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  ++TickCount;
}

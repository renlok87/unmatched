// VS-3 SC-01: the base of screens and modals - see UmScreenBase.h.
#include "UmScreenBase.h"

#include "../S08ArtHud.h"
#include "../S08IconMotion.h"
#include "UmGameHud.h"
#include "UmHudTheme.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/NamedSlot.h"
#include "HAL/PlatformTime.h"

namespace {
TArray<TWeakObjectPtr<UUmScreenBase>>& UmScreenRegistry() {
  static TArray<TWeakObjectPtr<UUmScreenBase>> Registry;
  return Registry;
}
}  // namespace

namespace UmScreens {
float SafeMarginSu(bool bClassS) { return bClassS ? MarginSSu : MarginLSu; }

float ShowLenMs(bool bReduced) { return bReduced ? ReducedMs : ShowMs; }

float HideLenMs(bool bModal, bool bReduced) {
  if (!bModal) return 0.0f;
  return bReduced ? ReducedMs : ModalHideMs;
}

float AlphaAt(bool bShow, float TMs, float LenMs) {
  const float K = LenMs > 0.0f ? FMath::Clamp(TMs / LenMs, 0.0f, 1.0f) : 1.0f;
  return bShow ? K : 1.0f - K;
}

EEscape RouteEscape(int32 OpenModals, bool bSelection) {
  if (OpenModals > 0) return EEscape::CloseModal;
  return bSelection ? EEscape::ClearSelection : EEscape::OpenPause;
}

const TCHAR* EscapeName(EEscape E) {
  switch (E) {
    case EEscape::CloseModal: return TEXT("close-modal");
    case EEscape::ClearSelection: return TEXT("clear-selection");
    default: return TEXT("open-pause");
  }
}

FString ShotFileName(const FString& UiId, const FString& State) { return FString::Printf(TEXT("%s-%s.png"), *UiId, *State); }

TArray<UUmScreenBase*> LiveScreens() {
  TArray<UUmScreenBase*> Out;
  TArray<TWeakObjectPtr<UUmScreenBase>>& R = UmScreenRegistry();
  for (int32 I = R.Num() - 1; I >= 0; --I) {
    if (UUmScreenBase* S = R[I].Get()) {
      Out.Insert(S, 0);
    } else {
      R.RemoveAt(I);
    }
  }
  return Out;
}
}  // namespace UmScreens

bool UUmScreenBase::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UCanvasPanel* RootW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Root")));
  if (!Attach(RootW, nullptr)) return Fail(TEXT("Root"));
  // the veil over the live scene: panel.veil 0.6, no blur (HUD-RULES П2); it takes the pointer (input outside closed)
  UImage* VeilW = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("Veil")));
  VeilW->SetColorAndOpacity(Theme.Color(TEXT("panel.veil")));
  VeilW->SetVisibility(ESlateVisibility::Visible);
  if (!Attach(VeilW, RootW)) return Fail(TEXT("Veil"));
  if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(VeilW->Slot)) {
    S->SetAnchors(FAnchors(0.0f, 0.0f, 1.0f, 1.0f));
    S->SetOffsets(FMargin(0.0f));
  }
  UBorder* FrameW = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("Frame")));
  if (const FSlateBrush* Skin = Theme.Skin(TEXT("modal"))) FrameW->SetBrush(*Skin);
  FrameW->SetPadding(FMargin(0.0f));
  FrameW->SetVisibility(ESlateVisibility::Visible);
  if (!Attach(FrameW, RootW)) return Fail(TEXT("Frame"));
  UNamedSlot* BodyW = Tree.ConstructWidget<UNamedSlot>(UNamedSlot::StaticClass(), FName(TEXT("Body")));
  if (!Attach(BodyW, FrameW)) return Fail(TEXT("Body"));
  return true;
}

bool UUmScreenBase::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD screen base default tree: %s"), *Error);
  }
  Root = Cast<UCanvasPanel>(WidgetTree->FindWidget(FName(TEXT("Root"))));
  Veil = Cast<UImage>(WidgetTree->FindWidget(FName(TEXT("Veil"))));
  Frame = Cast<UBorder>(WidgetTree->FindWidget(FName(TEXT("Frame"))));
  Body = Cast<UNamedSlot>(WidgetTree->FindWidget(FName(TEXT("Body"))));
  // a WBP keeps neither the theme brush nor the colour of the code tree: set at run time
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (Veil) Veil->SetColorAndOpacity(Theme.Color(TEXT("panel.veil")));
  BuildContent();
  UmScreenRegistry().AddUnique(this);
  SetVisibility(ESlateVisibility::Collapsed);
  SetRenderOpacity(0.0f);
  return bFirst;
}

void UUmScreenBase::BeginDestroy() {
  UmScreenRegistry().RemoveAll([this](const TWeakObjectPtr<UUmScreenBase>& W) { return !W.IsValid() || W.Get() == this; });
  Super::BeginDestroy();
}

bool UUmScreenBase::HasBaseParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Veil) Missing.Add(TEXT("Veil"));
  if (!Frame) Missing.Add(TEXT("Frame"));
  if (!Body) Missing.Add(TEXT("Body"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

FString UUmScreenBase::SourceName() const {
  return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName();
}

double UUmScreenBase::NowMs() const { return ClockOverrideMs >= 0.0 ? ClockOverrideMs : FPlatformTime::Seconds() * 1000.0; }

bool UUmScreenBase::IsReduced() const {
  return ReducedOverride >= 0 ? ReducedOverride != 0 : S08IconMotion::IsReducedMotion();
}

void UUmScreenBase::SetCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu) {
  CanvasSu = InCanvasSu;
  bClassS = bInClassS;
  PxPerSu = InPxPerSu > 0.0f ? InPxPerSu : 1.0f;
  Relayout();
}

void UUmScreenBase::SetFrameSize(const FVector2D& InFrameSu) {
  FrameSu = InFrameSu;
  Relayout();
}

FBox2D UUmScreenBase::FrameRectSu() const {
  const float M = GetSafeMarginSu();
  FVector2D Size = FrameSu;
  if (Size.X <= 0.0 || Size.Y <= 0.0) Size = CanvasSu - FVector2D(2.0f * M);
  // never past the safe margins (720p 150 %: 1138 x 640 su)
  Size.X = FMath::Min(Size.X, CanvasSu.X - 2.0 * M);
  Size.Y = FMath::Min(Size.Y, CanvasSu.Y - 2.0 * M);
  const FVector2D Min = 0.5 * (CanvasSu - Size);
  return FBox2D(Min, Min + Size);
}

void UUmScreenBase::Relayout() {
  if (!Frame) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (const FSlateBrush* Skin = Theme.SkinFor(TEXT("modal"), PxPerSu)) Frame->SetBrush(*Skin);
  if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(Frame->Slot)) {
    const FBox2D R = FrameRectSu();
    S->SetAnchors(FAnchors(0.0f, 0.0f));
    S->SetAlignment(FVector2D::ZeroVector);
    S->SetAutoSize(false);
    S->SetPosition(R.Min);
    S->SetSize(R.GetSize());
  }
}

void UUmScreenBase::PlayShow() {
  if (bShown && (bAnimShow || AlphaNow >= 1.0f)) return;
  bShown = true;
  bAnimShow = true;
  AlphaFrom = AlphaNow;
  AnimLenMs = UmScreens::ShowLenMs(IsReduced()) * (1.0f - AlphaFrom);
  AnimStartMs = NowMs();
  SetVisibility(ESlateVisibility::Visible);
  Step();
}

void UUmScreenBase::PlayHide() {
  if (!bShown) return;
  bShown = false;
  bAnimShow = false;
  AlphaFrom = AlphaNow;
  AnimLenMs = UmScreens::HideLenMs(IsModal(), IsReduced()) * AlphaFrom;
  AnimStartMs = NowMs();
  // a hiding screen takes no more input
  SetVisibility(ESlateVisibility::HitTestInvisible);
  Step();
}

void UUmScreenBase::Step() {
  if (AnimStartMs < 0.0) return;
  const float T = static_cast<float>(NowMs() - AnimStartMs);
  const float K = AnimLenMs > 0.0f ? FMath::Clamp(T / AnimLenMs, 0.0f, 1.0f) : 1.0f;
  AlphaNow = bAnimShow ? FMath::Lerp(AlphaFrom, 1.0f, K) : FMath::Lerp(AlphaFrom, 0.0f, K);
  SetRenderOpacity(AlphaNow);
  if (K >= 1.0f) {
    AnimStartMs = -1.0;
    if (!bAnimShow) SetVisibility(ESlateVisibility::Collapsed);
  }
}

void UUmScreenBase::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  if (AnimStartMs >= 0.0) Step();
}

FReply UUmScreenBase::NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  // nothing under the screen takes the press (04 §1: the input outside a modal is closed); the veil is "outside"
  const FVector2D Local = InGeometry.AbsoluteToLocal(InMouseEvent.GetScreenSpacePosition());
  const FVector2D Size = InGeometry.GetLocalSize();
  const FVector2D Su = Size.X > 0.0 ? Local * (CanvasSu.X / Size.X) : Local;
  if (!FrameRectSu().IsInside(Su)) OnVeilClick();
  return FReply::Handled();
}

void UUmScreenBase::CollectShotLines(TArray<FString>& Out) const {
  if (!bShown || UiId.IsEmpty()) return;
  const bool bVisible = UmGameHudSlots::ShownByProperty(this) || GetVisibility() == ESlateVisibility::Visible;
  const FBox2D R = IsModal() ? FrameRectSu() : FBox2D(FVector2D::ZeroVector, CanvasSu);
  const FS08ScreenRect Rect(R.Min.X * PxPerSu, R.Min.Y * PxPerSu, R.Max.X * PxPerSu, R.Max.Y * PxPerSu);
  Out.Add(S08ArtHud::FormatWidgetLineEx(UiId, TEXT("umg"), *ScreenState.ToString(), FString(), Rect, bVisible && !Rect.IsEmpty(),
                                        bVisible, SourceName(),
                                        FString::Printf(TEXT("modal=%d class=%s alpha=%.2f"), IsModal() ? 1 : 0,
                                                        bClassS ? TEXT("S") : TEXT("L"), AlphaNow)));
}

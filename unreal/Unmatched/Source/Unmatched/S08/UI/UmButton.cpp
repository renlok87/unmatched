// VS-2 HB-11: the HUD button of the UMG HUD - see UmButton.h.
#include "UmButton.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08IconMotion.h"
#include "UmHudScale.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/GridPanel.h"
#include "Components/GridSlot.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "HAL/PlatformTime.h"
#include "Input/Events.h"
#include "InputCoreTypes.h"

const TCHAR* const UUmButton::WidgetBlueprintPath = TEXT("/Game/S08/UI/Common/WBP_UmButton");

const TCHAR* UmButtonVariantName(EUmButtonVariant Variant) {
  switch (Variant) {
    case EUmButtonVariant::Primary: return TEXT("primary");
    case EUmButtonVariant::Disc: return TEXT("disc");
    default: return TEXT("normal");
  }
}

const TCHAR* UmButtonStateName(EUmButtonState State) {
  switch (State) {
    case EUmButtonState::Hover: return TEXT("hover");
    case EUmButtonState::Pressed: return TEXT("pressed");
    case EUmButtonState::Disabled: return TEXT("disabled");
    case EUmButtonState::Focus: return TEXT("focus");
    case EUmButtonState::Selected: return TEXT("selected");
    case EUmButtonState::Busy: return TEXT("busy");
    default: return TEXT("normal");
  }
}

namespace UmButton {
EUmButtonState ResolveState(const FUmButtonModel& Model, bool bHovered, bool bPressed) {
  if (Model.bBusy) return EUmButtonState::Busy;
  if (!Model.bEnabled) return EUmButtonState::Disabled;
  if (bPressed) return EUmButtonState::Pressed;
  if (Model.bSelected && Model.Variant != EUmButtonVariant::Primary) return EUmButtonState::Selected;
  if (bHovered) return EUmButtonState::Hover;
  if (Model.bFocused) return EUmButtonState::Focus;
  return EUmButtonState::Normal;
}

FName SkinKey(EUmButtonVariant Variant, EUmButtonState State) {
  if (Variant == EUmButtonVariant::Disc) return NAME_None;
  const bool bPrimary = Variant == EUmButtonVariant::Primary;
  switch (State) {
    case EUmButtonState::Hover: return bPrimary ? FName(TEXT("btn.primary.hover")) : FName(TEXT("btn.hover"));
    case EUmButtonState::Pressed: return bPrimary ? FName(TEXT("btn.primary.pressed")) : FName(TEXT("btn.pressed"));
    case EUmButtonState::Disabled:
    case EUmButtonState::Busy: return bPrimary ? FName(TEXT("btn.primary.disabled")) : FName(TEXT("btn.disabled"));
    case EUmButtonState::Selected: return bPrimary ? FName(TEXT("btn.primary.normal")) : FName(TEXT("btn.selected"));
    default: return bPrimary ? FName(TEXT("btn.primary.normal")) : FName(TEXT("btn.normal"));
  }
}

FName TextColorToken(EUmButtonVariant Variant, EUmButtonState State) {
  const bool bOff = State == EUmButtonState::Disabled || State == EUmButtonState::Busy;
  if (Variant == EUmButtonVariant::Primary) {
    // ВР-VS2-HB08-01: the disabled primary body is #4E5457 - text.primary there (card.navy would be 2.4 : 1)
    return bOff ? FName(TEXT("text.primary")) : FName(TEXT("card.navy"));
  }
  if (bOff) return FName(TEXT("text.secondary"));  // 02 §4.3: a colour, never the 0.4 opacity (3.4 : 1)
  if (State == EUmButtonState::Selected) return FName(TEXT("card.glyph"));
  return FName(TEXT("text.primary"));
}

FName DiscUnderlayToken(EUmButtonState State) {
  switch (State) {
    case EUmButtonState::Hover: return FName(TEXT("panel.bg.hover"));
    case EUmButtonState::Pressed: return FName(TEXT("panel.bg.pressed"));
    case EUmButtonState::Selected: return FName(TEXT("state.pending"));
    default: return NAME_None;
  }
}

float IconScale(EUmButtonVariant Variant, EUmButtonState State, bool bReduced) {
  if (bReduced || Variant == EUmButtonVariant::Normal) return 1.0f;
  if (State == EUmButtonState::Hover) return 1.06f;   // STYLE-v3 №9, 02 §4.3
  if (State == EUmButtonState::Pressed) return Variant == EUmButtonVariant::Disc ? 0.96f : 1.0f;
  return 1.0f;
}

float BodyScale(EUmButtonVariant Variant, EUmButtonState State, bool bReduced) {
  if (bReduced) return 1.0f;
  return Variant == EUmButtonVariant::Primary && State == EUmButtonState::Pressed ? 0.96f : 1.0f;
}

float DefaultHeightSu(EUmButtonVariant Variant) {
  switch (Variant) {
    case EUmButtonVariant::Primary: return 48.0f;
    case EUmButtonVariant::Disc: return 72.0f;
    default: return 40.0f;
  }
}

float MinWidthSu(EUmButtonVariant Variant) { return Variant == EUmButtonVariant::Disc ? 80.0f : 120.0f; }
}  // namespace UmButton

namespace {
template <typename T>
T* UmBtnMake(UWidgetTree& Tree, const TCHAR* Name) {
  return Tree.ConstructWidget<T>(T::StaticClass(), FName(Name));
}

template <typename T>
T* UmBtnFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

/** Disc variant: the icon 48 su and the caption under it; the others: icon (24) left, label, key chip right. */
constexpr float UmBtnDiscIconSu = 48.0f;
constexpr float UmBtnInlineIconSu = 24.0f;

void UmBtnPlace(UWidget* Widget, int32 Row, int32 Column, const FMargin& Padding,
                EHorizontalAlignment H = HAlign_Center, EVerticalAlignment V = VAlign_Center) {
  if (!Widget) return;
  if (UGridSlot* GridSlot = Cast<UGridSlot>(Widget->Slot)) {
    GridSlot->SetRow(Row);
    GridSlot->SetColumn(Column);
    GridSlot->SetPadding(Padding);
    GridSlot->SetHorizontalAlignment(H);
    GridSlot->SetVerticalAlignment(V);
  }
}

FFormatNamedArguments UmBtnArgs(const FS09Reason& Reason) {
  FFormatNamedArguments Args;
  for (const TPair<FString, FString>& A : Reason.Args) Args.Add(A.Key, FText::FromString(A.Value));
  return Args;
}
}  // namespace

bool UUmButton::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  USizeBox* SizeBox = UmBtnMake<USizeBox>(Tree, TEXT("Box"));
  SizeBox->SetHeightOverride(UmButton::DefaultHeightSu(EUmButtonVariant::Normal));
  SizeBox->SetMinDesiredWidth(UmButton::MinWidthSu(EUmButtonVariant::Normal));
  if (!Attach(SizeBox, nullptr)) return Fail(TEXT("Box"));
  UOverlay* Stack = UmBtnMake<UOverlay>(Tree, TEXT("Stack"));
  if (!Attach(Stack, SizeBox)) return Fail(TEXT("Stack"));
  UBorder* BodyWidget = UmBtnMake<UBorder>(Tree, TEXT("Body"));
  if (const FSlateBrush* Skin = Theme.Skin(TEXT("btn.normal"))) BodyWidget->SetBrush(*Skin);
  BodyWidget->SetPadding(FMargin(Theme.SpaceSu(TEXT("space.m")), 0.0f));
  BodyWidget->SetHorizontalAlignment(HAlign_Center);
  BodyWidget->SetVerticalAlignment(VAlign_Center);
  if (!Attach(BodyWidget, Stack)) return Fail(TEXT("Body"));
  if (UOverlaySlot* BodySlot = Cast<UOverlaySlot>(BodyWidget->Slot)) {
    BodySlot->SetHorizontalAlignment(HAlign_Fill);
    BodySlot->SetVerticalAlignment(VAlign_Fill);
  }
  UGridPanel* Grid = UmBtnMake<UGridPanel>(Tree, TEXT("Content"));
  if (!Attach(Grid, BodyWidget)) return Fail(TEXT("Content"));
  US08AnimatedIconWidget* IconWidget = UmBtnMake<US08AnimatedIconWidget>(Tree, TEXT("Icon"));
  if (!Attach(IconWidget, Grid)) return Fail(TEXT("Icon"));
  UmBtnPlace(IconWidget, 0, 0, FMargin(0.0f));
  UTextBlock* LabelWidget = UmBtnMake<UTextBlock>(Tree, TEXT("Label"));
  LabelWidget->SetFont(Theme.Font(TEXT("type.button")));
  LabelWidget->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
  LabelWidget->SetShadowOffset(FVector2D::ZeroVector);
  LabelWidget->SetJustification(ETextJustify::Center);
  if (!Attach(LabelWidget, Grid)) return Fail(TEXT("Label"));
  UmBtnPlace(LabelWidget, 0, 1, FMargin(0.0f));
  UBorder* Chip = UmBtnMake<UBorder>(Tree, TEXT("KeyChip"));
  if (const FSlateBrush* Skin = Theme.Skin(TEXT("key.chip"))) Chip->SetBrush(*Skin);
  Chip->SetPadding(FMargin(Theme.SpaceSu(TEXT("tag.padding.x")), Theme.SpaceSu(TEXT("tag.padding.y"))));
  Chip->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(Chip, Grid)) return Fail(TEXT("KeyChip"));
  UmBtnPlace(Chip, 0, 2, FMargin(Theme.SpaceSu(TEXT("tag.padding.x")), 0.0f, 0.0f, 0.0f));
  UTextBlock* Key = UmBtnMake<UTextBlock>(Tree, TEXT("KeyText"));
  Key->SetFont(Theme.Font(TEXT("type.tag")));
  Key->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
  Key->SetShadowOffset(FVector2D::ZeroVector);
  if (!Attach(Key, Chip)) return Fail(TEXT("KeyText"));
  UImage* Ring = UmBtnMake<UImage>(Tree, TEXT("FocusRing"));
  if (const FSlateBrush* Skin = Theme.Skin(TEXT("btn.focus"))) Ring->SetBrush(*Skin);
  Ring->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(Ring, Stack)) return Fail(TEXT("FocusRing"));
  if (UOverlaySlot* RingSlot = Cast<UOverlaySlot>(Ring->Slot)) {
    // 02 §4.3: the ring 2 su outside with a 2 su gap - the focus skin carries the gap, it overhangs the body by 4 su
    // (ring 2 su + gap 2 su = two tag.padding.y steps)
    RingSlot->SetHorizontalAlignment(HAlign_Fill);
    RingSlot->SetVerticalAlignment(VAlign_Fill);
    RingSlot->SetPadding(FMargin(-2.0f * Theme.SpaceSu(TEXT("tag.padding.y"))));
  }
  return true;
}

bool UUmButton::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    FString Error;
    UWidgetTree* Tree = WidgetTree;
    bCodeDefaultTree = BuildDefaultTree(*Tree, [Tree](UWidget* Child, UPanelWidget* Parent) {
      if (!Parent) {
        Tree->RootWidget = Child;
        return true;
      }
      return Parent->AddChild(Child) != nullptr;
    }, &Error);
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD button default tree: %s"), *Error);
    Box = UmBtnFind<USizeBox>(Tree, TEXT("Box"));
    Body = UmBtnFind<UBorder>(Tree, TEXT("Body"));
    Content = UmBtnFind<UGridPanel>(Tree, TEXT("Content"));
    Icon = UmBtnFind<US08AnimatedIconWidget>(Tree, TEXT("Icon"));
    Label = UmBtnFind<UTextBlock>(Tree, TEXT("Label"));
    KeyChip = UmBtnFind<UBorder>(Tree, TEXT("KeyChip"));
    KeyText = UmBtnFind<UTextBlock>(Tree, TEXT("KeyText"));
    FocusRing = UmBtnFind<UImage>(Tree, TEXT("FocusRing"));
  }
  if (bFirst) {
    // the press is decided on the button itself (Body / Label never take it)
    SetVisibility(ESlateVisibility::Visible);
    if (Content) Content->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (FocusRing) FocusRing->SetVisibility(ESlateVisibility::Collapsed);
  }
  return bFirst;
}

bool UUmButton::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Box) Missing.Add(TEXT("Box"));
  if (!Body) Missing.Add(TEXT("Body"));
  if (!Content) Missing.Add(TEXT("Content"));
  if (!Icon) Missing.Add(TEXT("Icon"));
  if (!Label) Missing.Add(TEXT("Label"));
  if (!KeyChip) Missing.Add(TEXT("KeyChip"));
  if (!KeyText) Missing.Add(TEXT("KeyText"));
  if (!FocusRing) Missing.Add(TEXT("FocusRing"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

double UUmButton::Now() const { return Clock ? Clock() : FPlatformTime::Seconds(); }

bool UUmButton::IsReduced() const {
  return ReducedOverride >= 0 ? ReducedOverride == 1 : S08IconMotion::IsReducedMotion();
}

void UUmButton::SetPress(FName InId, const TSharedPtr<FS09HudPressArbiter>& InArbiter,
                         const FS09OnHudPressOutcome& InOnOutcome) {
  PressId = InId;
  Arbiter = InArbiter;
  OnOutcome = InOnOutcome;
}

void UUmButton::ApplyModel(const FUmButtonModel& InModel) {
  const bool bSame = bHasModel && Model.Variant == InModel.Variant && Model.Label.EqualTo(InModel.Label) &&
                     Model.IconName == InModel.IconName && Model.bEnabled == InModel.bEnabled &&
                     Model.Reason.Key == InModel.Reason.Key && Model.Reason.Args.OrderIndependentCompareEqual(InModel.Reason.Args) &&
                     Model.bSelected == InModel.bSelected && Model.bBusy == InModel.bBusy &&
                     Model.KeyHint.EqualTo(InModel.KeyHint) && Model.bFocused == InModel.bFocused &&
                     Model.HeightSu == InModel.HeightSu;
  if (bSame) return;
  const bool bWasSelected = bHasModel && Model.bSelected;
  Model = InModel;
  bHasModel = true;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const bool bDisc = Model.Variant == EUmButtonVariant::Disc;
  if (Box) {
    Box->SetHeightOverride(Model.HeightSu > 0.0f ? Model.HeightSu : UmButton::DefaultHeightSu(Model.Variant));
    Box->SetMinDesiredWidth(UmButton::MinWidthSu(Model.Variant));
  }
  if (Body) Body->SetPadding(bDisc ? FMargin(0.0f) : FMargin(Theme.SpaceSu(TEXT("space.m")), 0.0f));
  // the text: type.button caps (disc: type.tag caps under the disc); busy reads "Отправлено…" (V-10)
  if (Label) {
    const FText Text = Model.bBusy ? UmText::Get(EUmTable::Hud, TEXT("hud.btn.sent")) : Model.Label;
    Label->SetText(Model.bBusy ? Text : Text.ToUpper());
    Label->SetFont(Theme.Font(bDisc ? TEXT("type.tag") : TEXT("type.button")));
    Label->SetVisibility(Text.IsEmpty() ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
  }
  if (KeyChip && KeyText) {
    KeyText->SetText(Model.KeyHint);
    KeyChip->SetVisibility(Model.KeyHint.IsEmpty() ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
  }
  // grid: disc = icon over its caption, the chip under; inline = icon, label, chip in a row
  const float Gap = Theme.SpaceSu(TEXT("tag.padding.x"));
  UmBtnPlace(Icon, 0, 0, FMargin(0.0f));
  UmBtnPlace(Label, bDisc ? 1 : 0, bDisc ? 0 : 1, bDisc ? FMargin(0.0f, Gap, 0.0f, 0.0f) : FMargin(Model.IconName.IsNone() ? 0.0f : Gap * 2.0f, 0.0f, 0.0f, 0.0f));
  // the key chip (04 §2.11): right of the label; on a disc in the disc's top-right corner (the same grid cell)
  if (bDisc) {
    UmBtnPlace(KeyChip, 0, 0, FMargin(0.0f), HAlign_Right, VAlign_Top);
  } else {
    UmBtnPlace(KeyChip, 0, 2, FMargin(Gap * 2.0f, 0.0f, 0.0f, 0.0f));
  }
  // the icon (HB-23: the side in su, the texture follows DPI x UI scale)
  if (Icon) {
    const float IconSu = bDisc ? UmBtnDiscIconSu : UmBtnInlineIconSu;
    if (Model.IconName.IsNone()) {
      Icon->SetVisibility(ESlateVisibility::Collapsed);
    } else {
      if (IconShown != Model.IconName || IconSizeShown != IconSu) {
        bool bClamped = false;
        const int32 Px = S08IconMotion::ExportSizePx(IconSu, UmHudScale::Current().PxPerSu(), &bClamped);
        if (Icon->SetIcon(Model.IconName, IconSu, Px)) {
          Icon->SetDisplaySizeSu(IconSu);
          Icon->ShowAtRest();
          IconShown = Model.IconName;
          IconSizeShown = IconSu;
        }
      }
      Icon->SetVisibility(ESlateVisibility::HitTestInvisible);
    }
  }
  if (!bWasSelected && Model.bSelected && bDisc && !IsReduced()) PulseStart = Now();  // glyph 1.1 -> 1.0, 200 ms
  Restyle();
}

void UUmButton::Restyle() {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const EUmButtonState Old = State;
  State = UmButton::ResolveState(Model, bHovered, bPressedVisual);
  const float PxPerSu = UmHudScale::Current().PxPerSu();
  const bool bDisc = Model.Variant == EUmButtonVariant::Disc;
  const bool bOff = State == EUmButtonState::Disabled || State == EUmButtonState::Busy;
  if (Body) {
    if (bDisc) {
      const FName Token = UmButton::DiscUnderlayToken(State);
      const FLinearColor Fill = Token.IsNone() ? FLinearColor::Transparent : Theme.Color(Token);
      Body->SetBrush(FSlateRoundedBoxBrush(Fill, Theme.RadiusSu(TEXT("radius.l"))));
    } else if (const FSlateBrush* Skin = Theme.SkinFor(UmButton::SkinKey(Model.Variant, State), PxPerSu)) {
      Body->SetBrush(*Skin);
    }
  }
  if (Label) Label->SetColorAndOpacity(FSlateColor(Theme.Color(UmButton::TextColorToken(Model.Variant, State))));
  if (KeyText) KeyText->SetColorAndOpacity(FSlateColor(Theme.Color(bOff ? TEXT("text.secondary") : TEXT("text.primary"))));
  if (Icon) Icon->SetRenderOpacity(bOff ? Theme.Alpha(TEXT("state.disabled.opacity")) : 1.0f);
  if (FocusRing) {
    const bool bRing = Model.bFocused;
    if (bRing) {
      const FName RingKey = Model.Variant == EUmButtonVariant::Primary ? FName(TEXT("btn.primary.focus")) : FName(TEXT("btn.focus"));
      if (const FSlateBrush* Skin = Theme.SkinFor(RingKey, PxPerSu)) FocusRing->SetBrush(*Skin);
    }
    FocusRing->SetVisibility(bRing ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  }
  // Normal pressed: the text 1 su down (02 §4.3); reduced motion - colour only
  const bool bReduced = IsReduced();
  LabelOffsetSu = (!bReduced && Model.Variant == EUmButtonVariant::Normal && State == EUmButtonState::Pressed) ? 1.0f : 0.0f;
  if (Label) Label->SetRenderTranslation(FVector2D(0.0f, LabelOffsetSu));
  // scale targets; the move takes icon.press.ms into a press, hover.ms otherwise
  const float IconTo = UmButton::IconScale(Model.Variant, State, bReduced);
  const float BodyTo = UmButton::BodyScale(Model.Variant, State, bReduced);
  if (!FMath::IsNearlyEqual(IconTo, IconScaleTo) || !FMath::IsNearlyEqual(BodyTo, BodyScaleTo)) {
    IconScaleFrom = IconScaleNow;
    BodyScaleFrom = BodyScaleNow;
    IconScaleTo = IconTo;
    BodyScaleTo = BodyTo;
    AnimStart = Now();
    AnimMs = Theme.Ms(State == EUmButtonState::Pressed ? TEXT("icon.press.ms") : TEXT("hover.ms"));
    if (bReduced || AnimMs <= 0.0) {
      IconScaleNow = IconTo;
      BodyScaleNow = BodyTo;
      AnimMs = 0.0;
    }
  }
  // why.*: only while hovered over a disabled / busy button, after 300 ms (Step)
  if (!bOff || !bHovered) {
    if (bWhyShown) SetToolTipText(FText::GetEmpty());
    bWhyShown = false;
  }
  if (Old != State || AnimMs > 0.0) Step();
}

FText UUmButton::GetWhyText() const {
  const FS09Reason Reason = Model.Reason.IsSet() ? Model.Reason : FS09Reason::Make(TEXT("why.syncing"));
  return Reason.Args.Num() ? UmText::Format(EUmTable::Why, Reason.Key.ToString(), UmBtnArgs(Reason))
                           : UmText::Get(EUmTable::Why, Reason.Key.ToString());
}

void UUmButton::Step() {
  const double T = Now();
  if (AnimMs > 0.0) {
    const float A = FMath::Clamp(static_cast<float>((T - AnimStart) * 1000.0 / AnimMs), 0.0f, 1.0f);
    IconScaleNow = FMath::Lerp(IconScaleFrom, IconScaleTo, A);
    BodyScaleNow = FMath::Lerp(BodyScaleFrom, BodyScaleTo, A);
    if (A >= 1.0f) AnimMs = 0.0;
  }
  float Pulse = 1.0f;
  if (PulseStart >= 0.0) {
    const float P = FMath::Clamp(static_cast<float>((T - PulseStart) * 1000.0 / 200.0), 0.0f, 1.0f);
    Pulse = FMath::Lerp(1.1f, 1.0f, P);
    if (P >= 1.0f) PulseStart = -1.0;
  }
  if (Icon) {
    const FVector2D S(IconScaleNow * Pulse, IconScaleNow * Pulse);
    if (!Icon->GetRenderTransform().Scale.Equals(S, 1.0e-4)) Icon->SetRenderScale(S);
  }
  if (Box) {
    const FVector2D S(BodyScaleNow, BodyScaleNow);
    if (!Box->GetRenderTransform().Scale.Equals(S, 1.0e-4)) Box->SetRenderScale(S);
  }
  const bool bOff = State == EUmButtonState::Disabled || State == EUmButtonState::Busy;
  if (bHovered && bOff && !bWhyShown && HoverSince >= 0.0 && T - HoverSince >= 0.3) {
    bWhyShown = true;
    SetToolTipText(GetWhyText());
  }
}

void UUmButton::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  const bool bOff = State == EUmButtonState::Disabled || State == EUmButtonState::Busy;
  if (AnimMs > 0.0 || PulseStart >= 0.0 || (bHovered && bOff && !bWhyShown)) Step();
}

void UUmButton::SetPressedVisual(bool bOn) {
  if (bPressedVisual == bOn) return;
  bPressedVisual = bOn;
  Restyle();
}

void UUmButton::SimulateHover(bool bIn) {
  if (bHovered == bIn) return;
  bHovered = bIn;
  HoverSince = bIn ? Now() : -1.0;
  Restyle();
}

void UUmButton::SetPreviewPointer(bool bHover, bool bPressed) {
  bHovered = bHover;
  bPressedVisual = bPressed;
  HoverSince = bHover ? Now() : -1.0;
  Restyle();
  // the end pose of the state (a still sheet): no tween, no pulse
  IconScaleNow = IconScaleTo;
  BodyScaleNow = BodyScaleTo;
  AnimMs = 0.0;
  PulseStart = -1.0;
  Step();
}

void UUmButton::NativeOnMouseEnter(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  Super::NativeOnMouseEnter(InGeometry, InMouseEvent);
  SimulateHover(true);
}

void UUmButton::NativeOnMouseLeave(const FPointerEvent& InMouseEvent) {
  Super::NativeOnMouseLeave(InMouseEvent);
  SimulateHover(false);
}

FReply UUmButton::NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (InMouseEvent.GetEffectingButton() != EKeys::LeftMouseButton || !Arbiter.IsValid()) return FReply::Unhandled();
  // DE-014: the press belongs to the logical id, the release decides (a disabled button takes it too: its answer is
  // the refusal with why.*, never silence)
  Arbiter->Press(PressId, Arbiter->Now());
  SetPressedVisual(true);
  FReply Reply = FReply::Handled();
  if (const TSharedPtr<SWidget> Cached = GetCachedWidget()) Reply.CaptureMouse(Cached.ToSharedRef());
  return Reply;
}

FReply UUmButton::NativeOnMouseButtonDoubleClick(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  return NativeOnMouseButtonDown(InGeometry, InMouseEvent);  // the second press of a fast double click is a press
}

FReply UUmButton::NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (InMouseEvent.GetEffectingButton() != EKeys::LeftMouseButton || !Arbiter.IsValid()) return FReply::Unhandled();
  const bool bOver = InGeometry.IsUnderLocation(InMouseEvent.GetScreenSpacePosition());
  const FS09HudPressOutcome Outcome = Arbiter->Release(bOver ? PressId : NAME_None, Arbiter->Now());
  SetPressedVisual(false);
  FReply Reply = FReply::Handled().ReleaseMouseCapture();
  if (Outcome.Result == ES09HudPressResult::Act || Outcome.Result == ES09HudPressResult::Refused) {
    // UI-INP-011: the answer in the frame of the release - disabled / busy is a refusal with its reason (CUE-004)
    FS09Reason Blocked;
    if (Model.bBusy || !Model.bEnabled) {
      Blocked = Model.Reason.IsSet() ? Model.Reason : FS09Reason::Make(TEXT("why.syncing"));
    }
    OnOutcome.ExecuteIfBound(FS09HudPressArbiter::Decide(Outcome, Blocked));
  }
  return Reply;
}

void UUmButton::NativeOnMouseCaptureLost(const FCaptureLostEvent& CaptureLostEvent) {
  Super::NativeOnMouseCaptureLost(CaptureLostEvent);
  SetPressedVisual(false);
}

FString UUmButton::DescribeState() const {
  return FString::Printf(TEXT("variant=%s state=%s label=\"%s\" enabled=%d selected=%d busy=%d focus=%d why=%s"),
                         UmButtonVariantName(Model.Variant), UmButtonStateName(State), *Model.Label.ToString(),
                         Model.bEnabled ? 1 : 0, Model.bSelected ? 1 : 0, Model.bBusy ? 1 : 0,
                         Model.bFocused ? 1 : 0, Model.Reason.IsSet() ? *Model.Reason.Key.ToString() : TEXT("-"));
}

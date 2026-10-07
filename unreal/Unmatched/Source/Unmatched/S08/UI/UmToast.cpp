// VS-4 HB-40: one toast - see UmToast.h.
#include "UmToast.h"

#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHudStatusLine.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "../S08AnimatedIconWidget.h"
#include "../S08IconMotion.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "Rendering/SlateRenderer.h"

const TCHAR* const UUmToast::WidgetBlueprintPath = TEXT("/Game/S08/UI/Common/WBP_UmToast");

namespace UmToast {
FName SignIcon(EUmToastKind Kind) {
  switch (Kind) {
    case EUmToastKind::Warning: return FName(TEXT("state-warning"));  // IC-47
    case EUmToastKind::Error: return FName(TEXT("badge-refuse"));     // IC-40
    default: return NAME_None;
  }
}

FName SkinKey(EUmToastKind Kind) {
  return Kind == EUmToastKind::Warning ? FName(TEXT("toast.warning")) : FName(TEXT("toast"));
}

float MeasureBodySu(const FString& Text, float SizeSu, float PxPerSu) {
  if (Text.IsEmpty()) return 0.0f;
  if (!FSlateApplication::IsInitialized() || !FSlateApplication::Get().GetRenderer()) return 0.5f * SizeSu * Text.Len();
  FSlateFontInfo Font = UUmHudTheme::Get().Font(TEXT("type.body"));
  Font.Size = UmHudTheme::PointsFromSu(SizeSu);
  const float Scale = PxPerSu > 0.0f ? PxPerSu : 1.0f;
  const TSharedRef<FSlateFontMeasure> M = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
  return static_cast<float>(M->Measure(Text, Font, Scale).X) / Scale;
}

FUmToastPlan Plan(const FUmToastSpec& Spec, float CapSu, FMeasure Measure) {
  using namespace UmHudFeed;
  FUmToastPlan P;
  P.bSign = Spec.Kind != EUmToastKind::Info;
  P.bClose = Spec.bSticky;
  const float Extra = (P.bSign ? ToastSignSu + ToastSignGapSu : 0.0f) + (P.bClose ? ToastSignGapSu + ToastSignSu : 0.0f);
  const float Room = FMath::Max(40.0f, CapSu - 2.0f * ToastPadSu - Extra);
  const FString S = Spec.Text.ToString();
  const float W = FMath::CeilToFloat(Measure(S, 16.0f)) + TextSlackSu;
  if (W <= Room) {
    P.TextWidthSu = W;
    P.Lines = 1;
  } else {
    // word wrap at the room (never cut, 04 §2.12): the lines are counted TextSlackSu narrower than the text block wraps
    float Widest = 0.0f;
    P.Lines = FMath::Max(1, UmHudStatus::WrapLines(S, FMath::Max(1.0f, Room - TextSlackSu), 16.0f, Measure, &Widest));
    P.TextWidthSu = FMath::Min(Room, FMath::CeilToFloat(Widest) + TextSlackSu);
  }
  P.SizeSu = FVector2D(FMath::CeilToFloat(P.TextWidthSu + 2.0f * ToastPadSu + Extra), ToastHeightSu(P.Lines));
  return P;
}
}  // namespace UmToast

namespace {
template <typename T>
T* UmToastMake(UWidgetTree& Tree, const TCHAR* Name) {
  return Tree.ConstructWidget<T>(T::StaticClass(), FName(Name));
}
}  // namespace

UClass* UUmToast::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmToast::StaticClass(), WidgetBlueprintPath); }

bool UUmToast::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  USizeBox* BoxW = UmToastMake<USizeBox>(Tree, TEXT("Box"));
  BoxW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(BoxW, nullptr)) return Fail(TEXT("Box"));
  UBorder* BodyW = UmToastMake<UBorder>(Tree, TEXT("Body"));
  if (const FSlateBrush* Skin = Theme.Skin(TEXT("toast"))) BodyW->SetBrush(*Skin);
  BodyW->SetPadding(FMargin(UmHudFeed::ToastPadSu, 0.0f));
  BodyW->SetHorizontalAlignment(HAlign_Fill);
  BodyW->SetVerticalAlignment(VAlign_Center);
  BodyW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(BodyW, BoxW)) return Fail(TEXT("Body"));
  UHorizontalBox* RowW = UmToastMake<UHorizontalBox>(Tree, TEXT("Row"));
  RowW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(RowW, BodyW)) return Fail(TEXT("Row"));
  USizeBox* SignW = UmToastMake<USizeBox>(Tree, TEXT("SignBox"));
  SignW->SetWidthOverride(UmHudFeed::ToastSignSu);
  SignW->SetHeightOverride(UmHudFeed::ToastSignSu);
  SignW->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(SignW, RowW)) return Fail(TEXT("SignBox"));
  if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(SignW->Slot)) {
    S->SetVerticalAlignment(VAlign_Center);
    S->SetPadding(FMargin(0.0f, 0.0f, UmHudFeed::ToastSignGapSu, 0.0f));
  }
  US08AnimatedIconWidget* IconW = UmToastMake<US08AnimatedIconWidget>(Tree, TEXT("Icon"));
  IconW->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(IconW, SignW)) return Fail(TEXT("Icon"));
  UTextBlock* TextW = UmToastMake<UTextBlock>(Tree, TEXT("Text"));
  TextW->SetFont(Theme.Font(TEXT("type.body")));
  TextW->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
  TextW->SetShadowOffset(FVector2D::ZeroVector);
  TextW->SetJustification(ETextJustify::Left);
  TextW->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(TextW, RowW)) return Fail(TEXT("Text"));
  if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(TextW->Slot)) {
    S->SetVerticalAlignment(VAlign_Center);
    S->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
  }
  USizeBox* CloseW = UmToastMake<USizeBox>(Tree, TEXT("CloseBox"));
  CloseW->SetWidthOverride(UmHudFeed::ToastSignSu);
  CloseW->SetHeightOverride(UmHudFeed::ToastSignSu);
  CloseW->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(CloseW, RowW)) return Fail(TEXT("CloseBox"));
  if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(CloseW->Slot)) {
    S->SetVerticalAlignment(VAlign_Center);
    S->SetPadding(FMargin(UmHudFeed::ToastSignGapSu, 0.0f, 0.0f, 0.0f));
  }
  UUmButton* Close = Tree.ConstructWidget<UUmButton>(UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath),
                                                     FName(TEXT("CloseButton")));
  if (!Attach(Close, CloseW)) return Fail(TEXT("CloseButton"));
  return true;
}

bool UUmToast::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD toast default tree: %s"), *Error);
  }
  if (bFirst) {
    BindFromTree();
    // the theme font is the default composite font (with its DroidSansFallback): a WBP does not keep it
    if (Text) Text->SetFont(UUmHudTheme::Get().Font(TEXT("type.body")));
    SetVisibility(ESlateVisibility::Collapsed);
  }
  return bFirst;
}

void UUmToast::BindFromTree() {
  UWidgetTree* Tree = WidgetTree;
  if (!Tree) return;
  Box = Cast<USizeBox>(Tree->FindWidget(FName(TEXT("Box"))));
  Body = Cast<UBorder>(Tree->FindWidget(FName(TEXT("Body"))));
  Row = Cast<UHorizontalBox>(Tree->FindWidget(FName(TEXT("Row"))));
  SignBox = Cast<USizeBox>(Tree->FindWidget(FName(TEXT("SignBox"))));
  Icon = Cast<US08AnimatedIconWidget>(Tree->FindWidget(FName(TEXT("Icon"))));
  Text = Cast<UTextBlock>(Tree->FindWidget(FName(TEXT("Text"))));
  CloseBox = Cast<USizeBox>(Tree->FindWidget(FName(TEXT("CloseBox"))));
  CloseButton = Cast<UUmButton>(Tree->FindWidget(FName(TEXT("CloseButton"))));
}

bool UUmToast::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Body) Missing.Add(TEXT("Body"));
  if (!Icon) Missing.Add(TEXT("Icon"));
  if (!Text) Missing.Add(TEXT("Text"));
  if (!CloseButton) Missing.Add(TEXT("CloseButton"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

FString UUmToast::SourceName() const { return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName(); }

FName UUmToast::GetSignIcon() const { return Icon && SignBox && SignBox->GetVisibility() != ESlateVisibility::Collapsed ? Icon->GetIconId() : NAME_None; }

bool UUmToast::IsCloseShown() const { return CloseBox && CloseBox->GetVisibility() != ESlateVisibility::Collapsed; }

void UUmToast::SetClose(FName PressId, const TSharedPtr<FS09HudPressArbiter>& Arbiter, const FS09OnHudPressOutcome& OnClose) {
  if (CloseButton) CloseButton->SetPress(PressId, Arbiter, OnClose);
}

void UUmToast::ApplySpec(const FUmToastSpec& InSpec, const FUmToastPlan& Plan, float InPxPerSu) {
  const bool bSkin = PxPerSu != InPxPerSu || Spec.Kind != InSpec.Kind;
  Spec = InSpec;
  PlanNow = Plan;
  PxPerSu = InPxPerSu;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (Box) {
    Box->SetWidthOverride(static_cast<float>(Plan.SizeSu.X));
    Box->SetHeightOverride(static_cast<float>(Plan.SizeSu.Y));
  }
  if (Body && bSkin) {
    if (const FSlateBrush* Skin = Theme.SkinFor(UmToast::SkinKey(Spec.Kind), PxPerSu)) Body->SetBrush(*Skin);
  }
  if (Text) {
    Text->SetText(Spec.Text);
    Text->SetAutoWrapText(false);
    Text->SetWrapTextAt(Plan.TextWidthSu);
  }
  const FName Sign = UmToast::SignIcon(Spec.Kind);
  if (SignBox) SignBox->SetVisibility(Sign.IsNone() ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
  if (Icon && !Sign.IsNone() && Icon->GetIconId() != Sign) {
    const int32 Px = S08IconMotion::ExportSizePx(UmHudFeed::ToastSignSu, PxPerSu > 0.0f ? PxPerSu : 1.0f);
    if (Icon->SetIcon(Sign, UmHudFeed::ToastSignSu, Px)) {
      Icon->SetDisplaySizeSu(UmHudFeed::ToastSignSu);
      Icon->ShowAtRest();
    }
  }
  if (CloseBox) CloseBox->SetVisibility(Plan.bClose ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Collapsed);
  if (CloseButton && Plan.bClose) {
    FUmButtonModel M;
    M.IconName = FName(TEXT("ui-close"));  // IC-54
    M.HeightSu = UmHudFeed::ToastSignSu;
    M.MinWidthSu = UmHudFeed::ToastSignSu;
    M.bFlat = true;
    CloseButton->ApplyModel(M);
    CloseButton->SetToolTipText(UmText::Get(EUmTable::Ms, TEXT("ms.hint.close")));
  }
}

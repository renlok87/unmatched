// VS-4 HB-35: the number picker of a deferred choice - see UmNumberPicker.h.
#include "UmNumberPicker.h"

#include "../S08AnimatedIconWidget.h"
#include "UmButton.h"
#include "UmDeckRow.h"
#include "UmGameHud.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/TextBlock.h"

namespace UmNumberPicker {
float HeightSu(bool bResult) { return 2.0f * StepSu + RowGapSu + (bResult ? RowGapSu + ResultHSu : 0.0f); }

int32 Stepped(const FUmNumberModel& Model, int32 Delta) {
  const int32 Lo = FMath::Min(Model.Min, Model.Max);
  const int32 Hi = FMath::Max(Model.Min, Model.Max);
  return FMath::Clamp(Model.Value + Delta, Lo, Hi);
}
}  // namespace UmNumberPicker

namespace {
template <typename T>
T* UmNpFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

void UmNpPlace(UWidget* W, const FVector2D& Pos, const FVector2D& Size) {
  if (UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr) {
    S->SetAnchors(FAnchors(0.0f, 0.0f));
    S->SetAlignment(FVector2D::ZeroVector);
    S->SetAutoSize(false);
    S->SetPosition(Pos);
    S->SetSize(Size);
  }
}

/** Width of a 40 su button with this label (caps, type.button 20 su, 2 x 16 su padding, at least 120 su). */
float UmNpButtonSu(const FText& Label) {
  const float Text = UmDeckRow::MeasureSu(Label.ToUpper().ToString(), 20.0f, FName(TEXT("type.button")));
  return FMath::Max(120.0f, FMath::CeilToFloat(Text) + 40.0f);  // + 8 su slack, as UmHudPending::ButtonWidthSu
}
}  // namespace

bool UUmNumberPicker::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  UCanvasPanel* RootW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Root")));
  RootW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(RootW, nullptr)) return Fail(TEXT("Root"));
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  auto Button = [&](const TCHAR* Name) -> bool {
    UUmButton* B = Tree.ConstructWidget<UUmButton>(ButtonClass, FName(Name));
    return Attach(B, RootW);
  };
  if (!Button(TEXT("UpButton"))) return Fail(TEXT("UpButton"));
  UTextBlock* Value = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("ValueText")));
  Value->SetJustification(ETextJustify::Center);
  Value->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(Value, RootW)) return Fail(TEXT("ValueText"));
  if (!Button(TEXT("DownButton"))) return Fail(TEXT("DownButton"));
  if (!Button(TEXT("ConfirmButton"))) return Fail(TEXT("ConfirmButton"));
  if (!Button(TEXT("CancelButton"))) return Fail(TEXT("CancelButton"));
  UBorder* Plate = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("ResultPlate")));
  Plate->SetVisibility(ESlateVisibility::Collapsed);
  Plate->SetVerticalAlignment(VAlign_Center);
  Plate->SetPadding(FMargin(12.0f, 0.0f));
  if (!Attach(Plate, RootW)) return Fail(TEXT("ResultPlate"));
  UTextBlock* Result = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("ResultText")));
  Result->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(Result, Plate)) return Fail(TEXT("ResultText"));
  return true;
}

bool UUmNumberPicker::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  if (!WidgetTree->RootWidget) {
    FString Error;
    UWidgetTree* Tree = WidgetTree;
    if (!BuildDefaultTree(*Tree, [Tree](UWidget* Child, UPanelWidget* Parent) {
          if (!Parent) {
            Tree->RootWidget = Child;
            return true;
          }
          return Parent->AddChild(Child) != nullptr;
        }, &Error)) {
      UE_LOG(LogTemp, Error, TEXT("UMHUD number picker default tree: %s"), *Error);
    }
  }
  Root = UmNpFind<UCanvasPanel>(WidgetTree, TEXT("Root"));
  UpButton = UmNpFind<UUmButton>(WidgetTree, TEXT("UpButton"));
  ValueText = UmNpFind<UTextBlock>(WidgetTree, TEXT("ValueText"));
  DownButton = UmNpFind<UUmButton>(WidgetTree, TEXT("DownButton"));
  ConfirmButton = UmNpFind<UUmButton>(WidgetTree, TEXT("ConfirmButton"));
  CancelButton = UmNpFind<UUmButton>(WidgetTree, TEXT("CancelButton"));
  ResultPlate = UmNpFind<UBorder>(WidgetTree, TEXT("ResultPlate"));
  ResultText = UmNpFind<UTextBlock>(WidgetTree, TEXT("ResultText"));
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (ValueText) {
    // type.title 28 su in the tabular card face (font.card): the digits do not jump while the value steps
    FSlateFontInfo Font = Theme.Font(TEXT("font.card"));
    Font.Size = UmHudTheme::PointsFromSu(28.0f);
    ValueText->SetFont(Font);
    ValueText->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
    ValueText->SetShadowOffset(FVector2D::ZeroVector);
  }
  if (ResultText) {
    ResultText->SetFont(Theme.Font(TEXT("type.body")));
    ResultText->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
    ResultText->SetAutoWrapText(true);
  }
  if (ResultPlate) {
    if (const FSlateBrush* Skin = Theme.Skin(TEXT("panel.inset"))) ResultPlate->SetBrush(*Skin);
  }
  if (Root) Root->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  return bFirst;
}

bool UUmNumberPicker::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Root) Missing.Add(TEXT("Root"));
  if (!UpButton) Missing.Add(TEXT("UpButton"));
  if (!ValueText) Missing.Add(TEXT("ValueText"));
  if (!DownButton) Missing.Add(TEXT("DownButton"));
  if (!ConfirmButton) Missing.Add(TEXT("ConfirmButton"));
  if (!CancelButton) Missing.Add(TEXT("CancelButton"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmNumberPicker::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter,
                               TFunction<void(const FS09HudPressOutcome&, int32)> InOnStep,
                               TFunction<void(const FS09HudPressOutcome&)> InOnConfirm,
                               TFunction<void(const FS09HudPressOutcome&)> InOnCancel) {
  TSharedPtr<TFunction<void(const FS09HudPressOutcome&, int32)>> Step =
      MakeShared<TFunction<void(const FS09HudPressOutcome&, int32)>>(MoveTemp(InOnStep));
  auto BindStep = [&InArbiter, Step](UUmButton* B, const TCHAR* Id, int32 Delta) {
    if (!B) return;
    B->SetPress(FName(Id), InArbiter, FS09OnHudPressOutcome::CreateLambda([Step, Delta](const FS09HudPressOutcome& O) {
      if (*Step) (*Step)(O, Delta);
    }));
  };
  BindStep(UpButton, TEXT("pending.number.up"), 1);
  BindStep(DownButton, TEXT("pending.number.down"), -1);
  auto Bind = [&InArbiter](UUmButton* B, const TCHAR* Id, TFunction<void(const FS09HudPressOutcome&)> Fn) {
    if (!B) return;
    TSharedPtr<TFunction<void(const FS09HudPressOutcome&)>> Shared = MakeShared<TFunction<void(const FS09HudPressOutcome&)>>(MoveTemp(Fn));
    B->SetPress(FName(Id), InArbiter, FS09OnHudPressOutcome::CreateLambda([Shared](const FS09HudPressOutcome& O) {
      if (*Shared) (*Shared)(O);
    }));
  };
  Bind(ConfirmButton, TEXT("pending.number.confirm"), MoveTemp(InOnConfirm));
  Bind(CancelButton, TEXT("pending.number.cancel"), MoveTemp(InOnCancel));
}

void UUmNumberPicker::ApplyModel(const FUmNumberModel& InModel, float WidthSu) {
  if (bHasModel && Model == InModel && FMath::IsNearlyEqual(WidthNow, WidthSu)) return;
  Model = InModel;
  bHasModel = true;
  WidthNow = WidthSu;
  using namespace UmNumberPicker;
  // row 1: ▲ value ▼, centred
  const float RowW = 2.0f * StepSu + ValueWSu + 2.0f * RowGapSu;
  const float X0 = FMath::Max(0.0f, 0.5f * (WidthSu - RowW));
  for (UUmButton* B : {UpButton.Get(), DownButton.Get()}) {
    if (!B) continue;
    FUmButtonModel M;
    M.IconName = FName(TEXT("ui-step"));
    M.HeightSu = StepSu;
    M.MinWidthSu = StepSu;
    B->ApplyModel(M);
  }
  // IC-56: ▼ is the same glyph turned 180° (no second texture)
  if (DownButton && DownButton->Icon) DownButton->Icon->SetRenderTransformAngle(180.0f);
  UmNpPlace(UpButton, FVector2D(X0, 0.0f), FVector2D(StepSu));
  UmNpPlace(ValueText, FVector2D(X0 + StepSu + RowGapSu, 0.0f), FVector2D(ValueWSu, StepSu));
  UmNpPlace(DownButton, FVector2D(X0 + StepSu + ValueWSu + 2.0f * RowGapSu, 0.0f), FVector2D(StepSu));
  if (ValueText) ValueText->SetText(FText::AsNumber(Model.Value));
  // row 2: «Подтвердить» (the window's one primary), «Отмена»
  const FText ConfirmLabel = UmText::Get(EUmTable::Hud, TEXT("hud.number.confirm"));
  const FText CancelLabel = UmText::Get(EUmTable::Ms, TEXT("ms.btn.cancel"));
  const float CW = UmNpButtonSu(ConfirmLabel);
  const float NW = UmNpButtonSu(CancelLabel);
  const float Row2 = CW + RowGapSu + NW;
  const float X2 = FMath::Max(0.0f, 0.5f * (WidthSu - Row2));
  if (ConfirmButton) {
    FUmButtonModel M;
    M.Variant = EUmButtonVariant::Primary;
    M.Label = ConfirmLabel;
    M.Reason = Model.ConfirmWhy;
    M.bEnabled = !Model.ConfirmWhy.IsSet();
    M.HeightSu = StepSu;
    M.MinWidthSu = CW;
    ConfirmButton->ApplyModel(M);
  }
  if (CancelButton) {
    FUmButtonModel M;
    M.Label = CancelLabel;
    M.HeightSu = StepSu;
    M.MinWidthSu = NW;
    CancelButton->ApplyModel(M);
  }
  UmNpPlace(ConfirmButton, FVector2D(X2, StepSu + RowGapSu), FVector2D(CW, StepSu));
  UmNpPlace(CancelButton, FVector2D(X2 + CW + RowGapSu, StepSu + RowGapSu), FVector2D(NW, StepSu));
  // row 3: the result plate
  const bool bResult = !Model.Result.IsEmpty();
  if (ResultPlate) ResultPlate->SetVisibility(bResult ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  if (ResultText) ResultText->SetText(FText::FromString(Model.Result));
  UmNpPlace(ResultPlate, FVector2D(0.0f, 2.0f * StepSu + 2.0f * RowGapSu), FVector2D(WidthSu, ResultHSu));
}

FString UUmNumberPicker::Describe() const {
  return FString::Printf(TEXT("value=%d min=%d max=%d result=%d"), Model.Value, Model.Min, Model.Max, Model.Result.IsEmpty() ? 0 : 1);
}

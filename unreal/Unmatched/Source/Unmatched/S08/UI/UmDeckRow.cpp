// VS-3 HB-28: one row of the deck panel - see UmDeckRow.h.
#include "UmDeckRow.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08IconMotion.h"
#include "UmHudScale.h"
#include "UmHudTheme.h"
#include "UmSpinner.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "InputCoreTypes.h"
#include "Rendering/SlateRenderer.h"

namespace UmDeckRow {
int32 TypeOrder(const FString& CardType) {
  const FString T = CardType.ToUpper();
  if (T == TEXT("ATTACK")) return 0;
  if (T == TEXT("DEFENSE")) return 1;
  if (T == TEXT("VERSATILE") || T == TEXT("UNIVERSAL")) return 2;
  if (T == TEXT("SCHEME")) return 3;
  return 4;
}

FName TypeIcon(const FString& CardType) {
  switch (TypeOrder(CardType)) {
    case 0: return FName(TEXT("action-attack"));
    case 1: return FName(TEXT("action-defense"));
    case 3: return FName(TEXT("action-scheme"));
    default: return FName(TEXT("action-maneuver"));  // versatile: the maneuver disc (ВР-VS2-CX09-05, HB-26 D3)
  }
}

FString Values(const FS09DeckListCard& Card) {
  const int32 Order = TypeOrder(Card.CardType);
  FString Out;
  if (Order == 0 && Card.AttackValue >= 0) Out = FString::Printf(TEXT("A%d"), Card.AttackValue);
  if (Order == 1 && Card.DefenseValue >= 0) Out = FString::Printf(TEXT("D%d"), Card.DefenseValue);
  if (Order == 2) {
    const int32 V = Card.AttackValue >= 0 ? Card.AttackValue : Card.DefenseValue;
    if (V >= 0) Out = FString::Printf(TEXT("V%d"), V);
  }
  if (Card.BoostValue >= 0) Out += FString::Printf(TEXT("%sB%d"), Out.IsEmpty() ? TEXT("") : TEXT(" "), Card.BoostValue);
  return Out;
}

FString ShownName(const FS09DeckListCard& Card, bool bRu) {
  return bRu && !Card.NameRu.IsEmpty() ? Card.NameRu : Card.Name;
}

namespace {
bool UmRowSlate() { return FSlateApplication::IsInitialized() && FSlateApplication::Get().GetRenderer() != nullptr; }

FSlateFontInfo UmRowFont(float SizeSu, FName Token) {
  FSlateFontInfo Font = UUmHudTheme::Get().Font(Token);
  Font.Size = UmHudTheme::PointsFromSu(SizeSu);
  return Font;
}
}  // namespace

float MeasureSu(const FString& Text, float SizeSu, FName Token) {
  if (Text.IsEmpty()) return 0.0f;
  if (UmRowSlate()) {
    return static_cast<float>(FSlateApplication::Get().GetRenderer()->GetFontMeasureService()->Measure(Text, UmRowFont(SizeSu, Token)).X);
  }
  return 0.5f * SizeSu * Text.Len();  // no Slate (a commandlet): a condensed-face estimate
}

float AscentSu(float SizeSu, FName Token) {
  if (UmRowSlate()) {
    // the measure answers whole pixels: at 8x the rounding is 1/8 su
    constexpr float K = 8.0f;
    const TSharedRef<FSlateFontMeasure> M = FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
    const FSlateFontInfo Font = UmRowFont(SizeSu, Token);
    const float Height = static_cast<float>(M->GetMaxCharacterHeight(Font, K));
    const float Baseline = static_cast<float>(M->GetBaseline(Font, K));  // the descent, negative
    if (Height > 0.0f) return (Height + Baseline) / K;
  }
  return AscentEm * SizeSu;
}

float MarkLineSu() {
  if (UmRowSlate()) {
    constexpr float K = 8.0f;  // the measure answers whole pixels: at 8x the rounding is 1/8 su
    const float H = static_cast<float>(FSlateApplication::Get().GetRenderer()->GetFontMeasureService()->GetMaxCharacterHeight(
        UmRowFont(14.0f, FName(TEXT("type.tag"))), K));
    if (H > 0.0f) return H / K;
  }
  return (AscentEm + 500.0f / 2048.0f) * 14.0f;  // Roboto: ascender 1900 + descender 500 of 2048
}

float MarkChipSu() { return FMath::Max(MarkHSu, FMath::CeilToFloat(MarkLineSu()) + 2.0f * MarkPadYSu); }

float MarksTopSu() { return HeightSu - MarkBottomSu - MarkChipSu(); }

FUmNameFit FitName(const FString& Name, float ColumnSu, TFunctionRef<float(const FString&, float)> Measure) {
  FUmNameFit F;
  F.ColumnSu = ColumnSu;
  F.Shown = Name;
  F.SizeSu = TextSu;
  F.WidthSu = Measure(Name, TextSu);
  if (F.WidthSu <= ColumnSu) return F;
  // one step down
  F.SizeSu = NameSmallSu;
  F.WidthSu = Measure(Name, NameSmallSu);
  if (F.WidthSu <= ColumnSu) return F;
  // then «…»: the longest prefix that fits with it
  const FString Ellipsis(TEXT("…"));
  FString Prefix = Name;
  while (Prefix.Len() > 0) {
    Prefix.LeftChopInline(1);
    const FString Try = Prefix.TrimEnd() + Ellipsis;
    const float W = Measure(Try, NameSmallSu);
    if (W <= ColumnSu || Prefix.IsEmpty()) {
      F.Shown = Try;
      F.WidthSu = W;
      break;
    }
  }
  F.bEllipsis = true;
  return F;
}
}  // namespace UmDeckRow

namespace {
template <typename T>
T* UmRowFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

const TCHAR* const UmRowMarkNames[3] = {TEXT("MarkHand"), TEXT("MarkDiscard"), TEXT("MarkLeft")};
}  // namespace

bool UUmDeckRow::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  USizeBox* BoxW = Tree.ConstructWidget<USizeBox>(USizeBox::StaticClass(), FName(TEXT("Box")));
  BoxW->SetHeightOverride(UmDeckRow::HeightSu);
  if (!Attach(BoxW, nullptr)) return Fail(TEXT("Box"));
  UOverlay* Stack = Tree.ConstructWidget<UOverlay>(UOverlay::StaticClass(), FName(TEXT("Stack")));
  if (!Attach(Stack, BoxW)) return Fail(TEXT("Stack"));
  UImage* CellW = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("Cell")));
  CellW->SetColorAndOpacity(Theme.Color(TEXT("panel.bg.inset")));
  if (!Attach(CellW, Stack)) return Fail(TEXT("Cell"));
  UImage* Divider = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("Divider")));
  Divider->SetBrush(UmLoader::LineBrush());  // 1 su high (the default image brush is 32 su)
  Divider->SetColorAndOpacity(Theme.Color(TEXT("panel.divider")));
  Divider->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(Divider, Stack)) return Fail(TEXT("Divider"));
  if (UOverlaySlot* S = Cast<UOverlaySlot>(CellW->Slot)) {
    S->SetHorizontalAlignment(HAlign_Fill);
    S->SetVerticalAlignment(VAlign_Fill);
  }
  if (UOverlaySlot* S = Cast<UOverlaySlot>(Divider->Slot)) {
    S->SetHorizontalAlignment(HAlign_Fill);
    S->SetVerticalAlignment(VAlign_Bottom);
  }
  UCanvasPanel* CanvasW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Canvas")));
  CanvasW->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(CanvasW, Stack)) return Fail(TEXT("Canvas"));
  if (UOverlaySlot* S = Cast<UOverlaySlot>(CanvasW->Slot)) {
    S->SetHorizontalAlignment(HAlign_Fill);
    S->SetVerticalAlignment(VAlign_Fill);
  }
  US08AnimatedIconWidget* Icon = Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("TypeIcon")));
  if (!Attach(Icon, CanvasW)) return Fail(TEXT("TypeIcon"));
  for (const TCHAR* Name : {TEXT("CopiesText"), TEXT("NameText"), TEXT("ValuesText")}) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetFont(Theme.Font(TEXT("type.button")));
    T->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
    T->SetShadowOffset(FVector2D::ZeroVector);
    if (!Attach(T, CanvasW)) return Fail(Name);
  }
  UHorizontalBox* MarksW = Tree.ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), FName(TEXT("Marks")));
  if (!Attach(MarksW, CanvasW)) return Fail(TEXT("Marks"));
  for (const TCHAR* Name : UmRowMarkNames) {
    USizeBox* MarkBox = Tree.ConstructWidget<USizeBox>(USizeBox::StaticClass(), FName(*(FString(Name) + TEXT("Box"))));
    MarkBox->SetHeightOverride(UmDeckRow::MarkHSu);
    if (!Attach(MarkBox, MarksW)) return Fail(Name);
    if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(MarkBox->Slot)) {
      S->SetPadding(FMargin(0.0f, 0.0f, UmDeckRow::MarkGapSu, 0.0f));
      S->SetVerticalAlignment(VAlign_Top);
    }
    UBorder* Chip = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(Name));
    if (const FSlateBrush* Skin = Theme.Skin(TEXT("btn.normal"))) Chip->SetBrush(*Skin);
    Chip->SetPadding(FMargin(UmDeckRow::MarkPadXSu, 0.0f));
    Chip->SetVerticalAlignment(VAlign_Center);
    if (!Attach(Chip, MarkBox)) return Fail(Name);
    UTextBlock* Text = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(*(FString(Name) + TEXT("Text"))));
    Text->SetFont(Theme.Font(TEXT("type.tag")));
    Text->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
    Text->SetShadowOffset(FVector2D::ZeroVector);
    if (!Attach(Text, Chip)) return Fail(Name);
  }
  return true;
}

bool UUmDeckRow::Initialize() {
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
    if (!bOk) UE_LOG(LogTemp, Error, TEXT("UMHUD deck row default tree: %s"), *Error);
  }
  Box = UmRowFind<USizeBox>(WidgetTree, TEXT("Box"));
  Cell = UmRowFind<UImage>(WidgetTree, TEXT("Cell"));
  Canvas = UmRowFind<UCanvasPanel>(WidgetTree, TEXT("Canvas"));
  TypeIcon = UmRowFind<US08AnimatedIconWidget>(WidgetTree, TEXT("TypeIcon"));
  CopiesText = UmRowFind<UTextBlock>(WidgetTree, TEXT("CopiesText"));
  NameText = UmRowFind<UTextBlock>(WidgetTree, TEXT("NameText"));
  ValuesText = UmRowFind<UTextBlock>(WidgetTree, TEXT("ValuesText"));
  Marks = UmRowFind<UHorizontalBox>(WidgetTree, TEXT("Marks"));
  MarkChips.Reset();
  MarkLabels.Reset();
  for (const TCHAR* Name : UmRowMarkNames) {
    MarkChips.Add(UmRowFind<UBorder>(WidgetTree, Name));
    MarkLabels.Add(UmRowFind<UTextBlock>(WidgetTree, *(FString(Name) + TEXT("Text"))));
  }
  // the row takes the press (its cell); the parts never do
  SetVisibility(ESlateVisibility::Visible);
  if (Canvas) Canvas->SetVisibility(ESlateVisibility::HitTestInvisible);
  SetCursor(EMouseCursor::Hand);
  return bFirst;
}

bool UUmDeckRow::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Box) Missing.Add(TEXT("Box"));
  if (!Cell) Missing.Add(TEXT("Cell"));
  if (!Canvas) Missing.Add(TEXT("Canvas"));
  if (!TypeIcon) Missing.Add(TEXT("TypeIcon"));
  if (!CopiesText) Missing.Add(TEXT("CopiesText"));
  if (!NameText) Missing.Add(TEXT("NameText"));
  if (!ValuesText) Missing.Add(TEXT("ValuesText"));
  if (!Marks) Missing.Add(TEXT("Marks"));
  for (int32 I = 0; I < 3; ++I) {
    if (!MarkChips.IsValidIndex(I) || !MarkChips[I] || !MarkLabels.IsValidIndex(I) || !MarkLabels[I]) Missing.Add(UmRowMarkNames[I]);
  }
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmDeckRow::ApplyModel(const FUmDeckRowModel& InModel, float WidthSu) {
  if (bHasModel && Model == InModel && FMath::IsNearlyEqual(WidthNow, WidthSu)) return;
  Model = InModel;
  bHasModel = true;
  WidthNow = WidthSu;
  using namespace UmDeckRow;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (Box) Box->SetWidthOverride(WidthSu);
  // the type disc
  if (TypeIcon) {
    const FName Icon = UmDeckRow::TypeIcon(Model.CardType);
    if (TypeIcon->GetIconId() != Icon) {
      bool bClamped = false;
      if (TypeIcon->SetIcon(Icon, IconSu, S08IconMotion::ExportSizePx(IconSu, UmHudScale::Current().PxPerSu(), &bClamped))) {
        TypeIcon->SetDisplaySizeSu(IconSu);
        TypeIcon->ShowAtRest();
      }
    }
    TypeIcon->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(TypeIcon->Slot)) {
      S->SetAutoSize(false);
      S->SetPosition(FVector2D(IconXSu, IconYSu));
      S->SetSize(FVector2D(IconSu, IconSu));
    }
  }
  // one baseline: the cap top of the 20 su text CapTopSu under the row top
  const float Baseline = CapTopSu + CapEm * TextSu;
  auto Place = [](UTextBlock* T, const FVector2D& Pos, const FVector2D& Align) {
    if (UCanvasPanelSlot* S = T ? Cast<UCanvasPanelSlot>(T->Slot) : nullptr) {
      S->SetAutoSize(true);
      S->SetAlignment(Align);
      S->SetPosition(Pos);
    }
  };
  const float Top20 = Baseline - AscentSu(TextSu);
  if (CopiesText) {
    CopiesText->SetText(FText::FromString(FString::Printf(TEXT("×%d"), Model.Copies)));
    Place(CopiesText, FVector2D(CopiesXSu, Top20), FVector2D::ZeroVector);
  }
  const float ValuesW = MeasureSu(Model.Values, TextSu);
  if (ValuesText) {
    ValuesText->SetText(FText::FromString(Model.Values));
    Place(ValuesText, FVector2D(WidthSu - ValuesRightSu, Top20), FVector2D(1.0f, 0.0f));
  }
  const float Column = FMath::Max(0.0f, WidthSu - ValuesRightSu - ValuesW - NameGapSu - NameXSu);
  NameFit = FitName(Model.Name, Column, [](const FString& Text, float Su) { return MeasureSu(Text, Su); });
  if (NameText) {
    FSlateFontInfo Font = Theme.Font(TEXT("type.button"));
    Font.Size = UmHudTheme::PointsFromSu(NameFit.SizeSu);
    NameText->SetFont(Font);
    NameText->SetText(FText::FromString(NameFit.Shown));
    Place(NameText, FVector2D(NameXSu, Baseline - AscentSu(NameFit.SizeSu)), FVector2D::ZeroVector);
  }
  // the marks (D3 / D7): own - in hand (n > 0), in discard (n > 0), left (always); opponent - in discard (n > 0) only;
  // VS-4 (VS-3 item 11): the chip holds the whole label line, 2 su over the row's bottom
  const float ChipH = MarkChipSu();
  const int32 Counts[3] = {Model.InHand, Model.InDiscard, Model.Left};
  const TCHAR* Keys[3] = {TEXT("hud.deckpanel.mark.hand"), TEXT("hud.deckpanel.mark.discard"), TEXT("hud.deckpanel.mark.left")};
  for (int32 I = 0; I < 3; ++I) {
    const bool bShow = Model.bOwn ? (I == 2 || Counts[I] > 0) : (I == 1 && Counts[I] > 0);
    UBorder* Chip = MarkChips.IsValidIndex(I) ? MarkChips[I].Get() : nullptr;
    UTextBlock* Label = MarkLabels.IsValidIndex(I) ? MarkLabels[I].Get() : nullptr;
    if (Label && bShow) {
      FFormatNamedArguments A;
      A.Add(TEXT("n"), FText::FromString(FString::FromInt(Counts[I])));
      Label->SetText(UmText::Format(EUmTable::Hud, Keys[I], A));
    }
    if (Chip) {
      Chip->SetPadding(FMargin(MarkPadXSu, 0.0f));
      Chip->SetVerticalAlignment(VAlign_Center);
    }
    if (UWidget* MarkBox = Chip ? Chip->GetParent() : nullptr) {
      if (USizeBox* MarkSize = Cast<USizeBox>(MarkBox)) MarkSize->SetHeightOverride(ChipH);
      MarkBox->SetVisibility(bShow ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    }
  }
  if (Marks) {
    Marks->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(Marks->Slot)) {
      S->SetAutoSize(true);
      S->SetPosition(FVector2D(CopiesXSu, MarksTopSu()));
    }
  }
  ApplyCell();
}

TArray<FString> UUmDeckRow::MarkTexts() const {
  TArray<FString> Out;
  for (int32 I = 0; I < 3; ++I) {
    const UBorder* Chip = MarkChips.IsValidIndex(I) ? MarkChips[I].Get() : nullptr;
    const UWidget* MarkBox = Chip ? Chip->GetParent() : nullptr;
    if (MarkBox && MarkBox->GetVisibility() != ESlateVisibility::Collapsed && MarkLabels[I]) {
      Out.Add(MarkLabels[I]->GetText().ToString());
    }
  }
  return Out;
}

void UUmDeckRow::ApplyCell() {
  if (Cell) Cell->SetColorAndOpacity(UUmHudTheme::Get().Color(bHovered ? TEXT("panel.bg.hover") : TEXT("panel.bg.inset")));
}

void UUmDeckRow::SetPress(FName InId, const TSharedPtr<FS09HudPressArbiter>& InArbiter, const FS09OnHudPressOutcome& InOnOutcome) {
  PressId = InId;
  Arbiter = InArbiter;
  OnOutcome = InOnOutcome;
}

FReply UUmDeckRow::NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (InMouseEvent.GetEffectingButton() != EKeys::LeftMouseButton || !Arbiter.IsValid()) return FReply::Handled();
  Arbiter->Press(PressId, Arbiter->Now());
  FReply Reply = FReply::Handled();
  if (const TSharedPtr<SWidget> Cached = GetCachedWidget()) Reply.CaptureMouse(Cached.ToSharedRef());
  return Reply;
}

FReply UUmDeckRow::NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (InMouseEvent.GetEffectingButton() != EKeys::LeftMouseButton || !Arbiter.IsValid()) return FReply::Handled();
  const bool bOver = InGeometry.IsUnderLocation(InMouseEvent.GetScreenSpacePosition());
  const FS09HudPressOutcome Outcome = Arbiter->Release(bOver ? PressId : NAME_None, Arbiter->Now());
  FReply Reply = FReply::Handled().ReleaseMouseCapture();
  if (Outcome.Result == ES09HudPressResult::Act || Outcome.Result == ES09HudPressResult::Refused) {
    OnOutcome.ExecuteIfBound(FS09HudPressArbiter::Decide(Outcome, FS09Reason()));
  }
  return Reply;
}

void UUmDeckRow::NativeOnMouseEnter(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  Super::NativeOnMouseEnter(InGeometry, InMouseEvent);
  bHovered = true;
  ApplyCell();
}

void UUmDeckRow::NativeOnMouseLeave(const FPointerEvent& InMouseEvent) {
  Super::NativeOnMouseLeave(InMouseEvent);
  bHovered = false;
  ApplyCell();
}

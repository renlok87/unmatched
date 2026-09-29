#include "S08ArtHudWidgets.h"

#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/SizeBox.h"
#include "Components/SizeBoxSlot.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Styling/CoreStyle.h"

const TCHAR* const US08ArtPlateWidget::WidgetBlueprintPath = TEXT("/Game/S08/UI/ArtHud/WBP_S08ArtPlate");
const TCHAR* const US08ArtIconWidget::WidgetBlueprintPath = TEXT("/Game/S08/UI/ArtHud/WBP_S08ArtIcon");

namespace {
// FSlateColorBrush(White): no resource, so it serializes into a WBP as is and
// paints a flat quad tinted by the widget color - what SColorBlock / the
// Slate plate's WhiteBrush borders paint.
const FSlateBrush& S08WhiteBrush() { return *FCoreStyle::Get().GetBrush("WhiteBrush"); }

template <typename T>
T* S08Make(UWidgetTree& Tree, const TCHAR* Name) {
  return Tree.ConstructWidget<T>(T::StaticClass(), FName(Name));
}

void S08StyleText(UTextBlock* Text, const FS08ArtHudFontToken& Font, const FColor& Color) {
  if (!Text) return;
  Text->SetFont(Font.Resolve());
  Text->SetColorAndOpacity(FSlateColor(FS08ArtHudPlateStyle::Linear(Color)));
}

UTextBlock* S08MakeText(UWidgetTree& Tree, const TCHAR* Name, const FS08ArtHudFontToken& Font, const FColor& Color) {
  UTextBlock* Text = S08Make<UTextBlock>(Tree, Name);
  S08StyleText(Text, Font, Color);
  // UTextBlock defaults to a (1,1) transparent shadow, and FSlateTextRun
  // measures the shadow offset even when it is invisible: +1 px per text
  // against the Slate plate (NormalText has a zero offset).
  Text->SetShadowOffset(FVector2D::ZeroVector);
  return Text;
}

UImage* S08MakeBlock(UWidgetTree& Tree, const TCHAR* Name, const FColor& Color) {
  UImage* Image = S08Make<UImage>(Tree, Name);
  Image->SetBrush(S08WhiteBrush());
  Image->SetColorAndOpacity(FS08ArtHudPlateStyle::Linear(Color));
  return Image;
}

template <typename T>
T* S08Find(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

void S08AddPart(TArray<FS08WidgetPart>& Out, const TCHAR* Id, const UWidget* Widget) {
  if (Widget) Out.Add({Id, Widget->GetCachedWidget()});
}
}  // namespace

// ------------------------------------------------------------------- plate

bool US08ArtPlateWidget::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  // Mirrors the T2.2 Slate plate widget for widget (S08ArtHudViews.cpp
  // FS08SlatePlateView::Build); the parity automation test compares the
  // arranged geometry of every part.
  const FS08ArtHudPlateStyle Style;
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };

  UBorder* Background = S08Make<UBorder>(Tree, TEXT("PlateBackground"));
  Background->SetBrush(S08WhiteBrush());
  Background->SetBrushColor(FS08ArtHudPlateStyle::Linear(Style.Background));
  Background->SetPadding(FMargin(0.0f));
  Background->SetHorizontalAlignment(HAlign_Fill);
  Background->SetVerticalAlignment(VAlign_Fill);
  if (!Attach(Background, nullptr)) return Fail(TEXT("PlateBackground"));

  UVerticalBox* Column = S08Make<UVerticalBox>(Tree, TEXT("PlateColumn"));
  if (!Attach(Column, Background)) return Fail(TEXT("PlateColumn"));
  Background->SetPadding(FMargin(0.0f));

  auto RowSlot = [](UWidget* Child, const FMargin& RowPadding) {
    if (UVerticalBoxSlot* Slot = Cast<UVerticalBoxSlot>(Child->Slot)) {
      Slot->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
      Slot->SetPadding(RowPadding);
      Slot->SetHorizontalAlignment(HAlign_Fill);
      Slot->SetVerticalAlignment(VAlign_Fill);
    }
  };

  // Marker strip (#C8A0FF, the plate pixel gate).
  USizeBox* MarkerBox = S08Make<USizeBox>(Tree, TEXT("MarkerBox"));
  MarkerBox->SetHeightOverride(S08ArtHudLayout::MarkerHeightSu);
  if (!Attach(MarkerBox, Column)) return Fail(TEXT("MarkerBox"));
  RowSlot(MarkerBox, FMargin(0.0f));
  UImage* MarkerImage = S08MakeBlock(Tree, TEXT("Marker"), Style.Marker);
  if (!Attach(MarkerImage, MarkerBox)) return Fail(TEXT("Marker"));

  // Name + team chip.
  UHorizontalBox* NameRow = S08Make<UHorizontalBox>(Tree, TEXT("NameRow"));
  if (!Attach(NameRow, Column)) return Fail(TEXT("NameRow"));
  RowSlot(NameRow, S08ArtHudLayout::NameRowPadding);
  UTextBlock* Name = S08MakeText(Tree, TEXT("NameText"), Style.NameFont, Style.NameText);
  if (!Attach(Name, NameRow)) return Fail(TEXT("NameText"));
  if (UHorizontalBoxSlot* Slot = Cast<UHorizontalBoxSlot>(Name->Slot)) {
    Slot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
    Slot->SetHorizontalAlignment(HAlign_Fill);
    Slot->SetVerticalAlignment(VAlign_Center);
  }
  UBorder* Chip = S08Make<UBorder>(Tree, TEXT("TeamChip"));
  Chip->SetBrush(S08WhiteBrush());
  Chip->SetBrushColor(Style.ChipColor(true));
  Chip->SetPadding(S08ArtHudLayout::ChipPadding);
  Chip->SetHorizontalAlignment(HAlign_Fill);
  Chip->SetVerticalAlignment(VAlign_Fill);
  if (!Attach(Chip, NameRow)) return Fail(TEXT("TeamChip"));
  if (UHorizontalBoxSlot* Slot = Cast<UHorizontalBoxSlot>(Chip->Slot)) {
    Slot->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
    Slot->SetHorizontalAlignment(HAlign_Fill);
    Slot->SetVerticalAlignment(VAlign_Center);
  }
  UTextBlock* Team = S08MakeText(Tree, TEXT("TeamText"), Style.TeamFont, Style.NameText);
  if (!Attach(Team, Chip)) return Fail(TEXT("TeamText"));
  Chip->SetPadding(S08ArtHudLayout::ChipPadding);

  // HP bar + HP text.
  UHorizontalBox* HpRow = S08Make<UHorizontalBox>(Tree, TEXT("HpRow"));
  if (!Attach(HpRow, Column)) return Fail(TEXT("HpRow"));
  RowSlot(HpRow, S08ArtHudLayout::HpRowPadding);
  USizeBox* Bar = S08Make<USizeBox>(Tree, TEXT("HpBar"));
  Bar->SetWidthOverride(Style.HpBarWidthSu);
  Bar->SetHeightOverride(S08ArtHudLayout::HpBarHeightSu);
  if (!Attach(Bar, HpRow)) return Fail(TEXT("HpBar"));
  if (UHorizontalBoxSlot* Slot = Cast<UHorizontalBoxSlot>(Bar->Slot)) {
    Slot->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
    Slot->SetHorizontalAlignment(HAlign_Fill);
    Slot->SetVerticalAlignment(VAlign_Center);
  }
  UOverlay* BarLayers = S08Make<UOverlay>(Tree, TEXT("HpBarLayers"));
  if (!Attach(BarLayers, Bar)) return Fail(TEXT("HpBarLayers"));
  UImage* Back = S08MakeBlock(Tree, TEXT("HpBack"), Style.HpBack);
  if (!Attach(Back, BarLayers)) return Fail(TEXT("HpBack"));
  if (UOverlaySlot* Slot = Cast<UOverlaySlot>(Back->Slot)) {
    // UOverlaySlot defaults to Left/Top; SOverlay::Slot() fills.
    Slot->SetHorizontalAlignment(HAlign_Fill);
    Slot->SetVerticalAlignment(VAlign_Fill);
  }
  USizeBox* Fill = S08Make<USizeBox>(Tree, TEXT("HpFill"));
  Fill->SetWidthOverride(Style.HpBarWidthSu);
  if (!Attach(Fill, BarLayers)) return Fail(TEXT("HpFill"));
  if (UOverlaySlot* Slot = Cast<UOverlaySlot>(Fill->Slot)) {
    Slot->SetHorizontalAlignment(HAlign_Left);
    Slot->SetVerticalAlignment(VAlign_Fill);
  }
  UImage* FillImage = S08MakeBlock(Tree, TEXT("HpFillImage"), Style.HpFill);
  if (!Attach(FillImage, Fill)) return Fail(TEXT("HpFillImage"));
  UTextBlock* Hp = S08MakeText(Tree, TEXT("HpText"), Style.HpFont, Style.NameText);
  if (!Attach(Hp, HpRow)) return Fail(TEXT("HpText"));
  if (UHorizontalBoxSlot* Slot = Cast<UHorizontalBoxSlot>(Hp->Slot)) {
    Slot->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
    Slot->SetPadding(S08ArtHudLayout::HpTextPadding);
    Slot->SetHorizontalAlignment(HAlign_Fill);
    Slot->SetVerticalAlignment(VAlign_Center);
  }

  // Statuses.
  UTextBlock* Status = S08MakeText(Tree, TEXT("StatusText"), Style.StatusFont, Style.StatusText);
  if (!Attach(Status, Column)) return Fail(TEXT("StatusText"));
  RowSlot(Status, S08ArtHudLayout::StatusPadding);
  return true;
}

bool US08ArtPlateWidget::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("S08 art HUD plate default tree: %s"), *Error);
    PlateBackground = S08Find<UBorder>(Tree, TEXT("PlateBackground"));
    Marker = S08Find<UImage>(Tree, TEXT("Marker"));
    NameText = S08Find<UTextBlock>(Tree, TEXT("NameText"));
    TeamChip = S08Find<UBorder>(Tree, TEXT("TeamChip"));
    TeamText = S08Find<UTextBlock>(Tree, TEXT("TeamText"));
    HpBar = S08Find<USizeBox>(Tree, TEXT("HpBar"));
    HpBack = S08Find<UImage>(Tree, TEXT("HpBack"));
    HpFill = S08Find<USizeBox>(Tree, TEXT("HpFill"));
    HpFillImage = S08Find<UImage>(Tree, TEXT("HpFillImage"));
    HpText = S08Find<UTextBlock>(Tree, TEXT("HpText"));
    StatusText = S08Find<UTextBlock>(Tree, TEXT("StatusText"));
  }
  return bFirst;
}

void US08ArtPlateWidget::NativePreConstruct() {
  Super::NativePreConstruct();
  ApplyStyle();
}

void US08ArtPlateWidget::ApplyStyle() {
  if (PlateBackground) PlateBackground->SetBrushColor(FS08ArtHudPlateStyle::Linear(Style.Background));
  if (Marker) Marker->SetColorAndOpacity(FS08ArtHudPlateStyle::Linear(Style.Marker));
  S08StyleText(NameText, Style.NameFont, Style.NameText);
  S08StyleText(TeamText, Style.TeamFont, Style.NameText);
  S08StyleText(HpText, Style.HpFont, Style.NameText);
  S08StyleText(StatusText, Style.StatusFont, Style.StatusText);
  if (HpBack) HpBack->SetColorAndOpacity(FS08ArtHudPlateStyle::Linear(Style.HpBack));
  if (HpFillImage) HpFillImage->SetColorAndOpacity(FS08ArtHudPlateStyle::Linear(Style.HpFill));
  if (HpBar) HpBar->SetWidthOverride(Style.HpBarWidthSu);
  ApplyDynamic();
}

void US08ArtPlateWidget::ApplyDynamic() {
  if (TeamChip) TeamChip->SetBrushColor(Style.ChipColor(bOwn));
  // Same rule as the Slate plate: at least 1 su of fill.
  if (HpFill) HpFill->SetWidthOverride(FMath::Max(1.0f, Style.HpBarWidthSu * HpFraction));
}

void US08ArtPlateWidget::ApplyTexts(const FS08PlateTexts& Texts) {
  bOwn = Texts.bOwn;
  HpFraction = Texts.HpFraction;
  if (NameText) NameText->SetText(Texts.Name);
  if (TeamText) TeamText->SetText(Texts.Team);
  if (HpText) HpText->SetText(Texts.Hp);
  if (StatusText) StatusText->SetText(Texts.Statuses);
  ApplyDynamic();
}

bool US08ArtPlateWidget::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!PlateBackground) Missing.Add(TEXT("PlateBackground"));
  if (!Marker) Missing.Add(TEXT("Marker"));
  if (!NameText) Missing.Add(TEXT("NameText"));
  if (!TeamChip) Missing.Add(TEXT("TeamChip"));
  if (!TeamText) Missing.Add(TEXT("TeamText"));
  if (!HpBar) Missing.Add(TEXT("HpBar"));
  if (!HpBack) Missing.Add(TEXT("HpBack"));
  if (!HpFill) Missing.Add(TEXT("HpFill"));
  if (!HpFillImage) Missing.Add(TEXT("HpFillImage"));
  if (!HpText) Missing.Add(TEXT("HpText"));
  if (!StatusText) Missing.Add(TEXT("StatusText"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void US08ArtPlateWidget::CollectParts(TArray<FS08WidgetPart>& Out) const {
  Out.Add({S08ArtHudIds::Plate, GetCachedWidget()});
  S08AddPart(Out, S08ArtHudIds::PlateMarker, Marker);
  S08AddPart(Out, S08ArtHudIds::PlateName, NameText);
  S08AddPart(Out, S08ArtHudIds::PlateTeam, TeamChip);
  S08AddPart(Out, S08ArtHudIds::PlateHpBar, HpBar);
  S08AddPart(Out, S08ArtHudIds::PlateHpFill, HpFill);
  S08AddPart(Out, S08ArtHudIds::PlateHp, HpText);
  S08AddPart(Out, S08ArtHudIds::PlateStatus, StatusText);
}

// -------------------------------------------------------------------- icon

bool US08ArtIconWidget::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  UImage* Image = S08Make<UImage>(Tree, TEXT("Icon"));
  if (!Attach(Image, nullptr)) {
    if (OutError) *OutError = TEXT("attach failed: Icon");
    return false;
  }
  return true;
}

bool US08ArtIconWidget::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("S08 art HUD icon default tree: %s"), *Error);
    Icon = S08Find<UImage>(Tree, TEXT("Icon"));
  }
  return bFirst;
}

void US08ArtIconWidget::SetIconBrush(const FSlateBrush& Brush) {
  if (Icon) Icon->SetBrush(Brush);
}

bool US08ArtIconWidget::HasAllParts(FString* OutMissing) const {
  if (OutMissing) *OutMissing = Icon ? FString() : FString(TEXT("Icon"));
  return Icon != nullptr;
}

void US08ArtIconWidget::CollectParts(TArray<FS08WidgetPart>& Out) const {
  Out.Add({S08ArtHudIds::Icon, GetCachedWidget()});
}

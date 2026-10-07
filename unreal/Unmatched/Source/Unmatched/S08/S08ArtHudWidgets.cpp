#include "S08ArtHudWidgets.h"
#include "UI/UmWorldLayer.h"

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
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Styling/CoreStyle.h"

const TCHAR* const US08ArtPlateWidget::WidgetBlueprintPath = TEXT("/Game/S08/UI/ArtHud/WBP_S08ArtPlate");
const TCHAR* const US08ArtIconWidget::WidgetBlueprintPath = TEXT("/Game/S08/UI/ArtHud/WBP_S08ArtIcon");
const TCHAR* const US08ArtTagWidget::WidgetBlueprintPath = TEXT("/Game/S08/UI/ArtHud/WBP_S08ArtTag");
const TCHAR* const US08ArtDamageWidget::WidgetBlueprintPath = TEXT("/Game/S08/UI/ArtHud/WBP_S08ArtDamage");

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
  // W5b-R D-3: the chip is the team shape (on-screen team colour) + YOURS/ENEMY on the plate background.
  UBorder* Chip = S08Make<UBorder>(Tree, TEXT("TeamChip"));
  Chip->SetBrush(S08WhiteBrush());
  Chip->SetBrushColor(FS08ArtHudPlateStyle::Linear(Style.Background));
  Chip->SetPadding(S08ArtHudLayout::ChipPadding);
  Chip->SetHorizontalAlignment(HAlign_Fill);
  Chip->SetVerticalAlignment(VAlign_Fill);
  if (!Attach(Chip, NameRow)) return Fail(TEXT("TeamChip"));
  if (UHorizontalBoxSlot* Slot = Cast<UHorizontalBoxSlot>(Chip->Slot)) {
    Slot->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
    Slot->SetHorizontalAlignment(HAlign_Fill);
    Slot->SetVerticalAlignment(VAlign_Center);
  }
  UHorizontalBox* ChipRow = S08Make<UHorizontalBox>(Tree, TEXT("ChipRow"));
  if (!Attach(ChipRow, Chip)) return Fail(TEXT("ChipRow"));
  USizeBox* ShapeBox = S08Make<USizeBox>(Tree, TEXT("TeamShapeBox"));
  ShapeBox->SetWidthOverride(Style.TeamShapeSu);
  ShapeBox->SetHeightOverride(Style.TeamShapeSu);
  if (!Attach(ShapeBox, ChipRow)) return Fail(TEXT("TeamShapeBox"));
  if (UHorizontalBoxSlot* Slot = Cast<UHorizontalBoxSlot>(ShapeBox->Slot)) {
    Slot->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
    Slot->SetPadding(FMargin(0.0f, 0.0f, 3.0f, 0.0f));
    Slot->SetHorizontalAlignment(HAlign_Fill);
    Slot->SetVerticalAlignment(VAlign_Center);
  }
  UImage* Shape = S08Make<UImage>(Tree, TEXT("TeamShape"));
  Shape->SetBrush(S08WhiteBrush());
  Shape->SetColorAndOpacity(Style.TeamChipColor(0));
  if (!Attach(Shape, ShapeBox)) return Fail(TEXT("TeamShape"));
  UTextBlock* Team = S08MakeText(Tree, TEXT("TeamText"), Style.TeamFont, Style.NameText);
  if (!Attach(Team, ChipRow)) return Fail(TEXT("TeamText"));
  if (UHorizontalBoxSlot* Slot = Cast<UHorizontalBoxSlot>(Team->Slot)) {
    Slot->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
    Slot->SetHorizontalAlignment(HAlign_Fill);
    Slot->SetVerticalAlignment(VAlign_Center);
  }
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
    TeamShape = S08Find<UImage>(Tree, TEXT("TeamShape"));
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
  // VS-4 review (HB-46): with the H12 plate the host border stays transparent - the V2 panel paints and fades its own
  // body. NativePreConstruct runs this after SetV2, and the legacy #161A28 body then showed as an empty panel while the
  // V2 plate faded in / out (HB-49 frames pend-marm-720-150 s09-pending-MOVE, pv-sarp-720-100 s09-exit-banner-combat)
  if (PlateBackground) {
    PlateBackground->SetBrushColor(bV2 ? FLinearColor::Transparent : FS08ArtHudPlateStyle::Linear(Style.Background));
  }
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
  if (TeamChip) TeamChip->SetBrushColor(FS08ArtHudPlateStyle::Linear(Style.Background));
  if (TeamShape) {
    if (bShapeBrushes) TeamShape->SetBrush(ShapeBrushes[TeamSlot ? 1 : 0]);
    TeamShape->SetColorAndOpacity(Style.TeamChipColor(TeamSlot));
  }
  // Same rule as the Slate plate: at least 1 su of fill.
  if (HpFill) HpFill->SetWidthOverride(FMath::Max(1.0f, Style.HpBarWidthSu * HpFraction));
}

void US08ArtPlateWidget::SetTeamShapeBrushes(const FSlateBrush& Circle, const FSlateBrush& Hex) {
  ShapeBrushes[0] = Circle;
  ShapeBrushes[1] = Hex;
  bShapeBrushes = true;
  ApplyDynamic();
}

void US08ArtPlateWidget::SetV2(bool bOn) {
  if (bOn == bV2 || !PlateBackground) return;
  if (bOn) {
    if (!V2Plate) V2Plate = CreateWidget<UUmWorldPlate>(this, UUmWorldPlate::StaticClass());
    if (!V2Plate) return;
    LegacyContent = PlateBackground->GetContent();
    LegacySizeSu = Style.SizeSu;
    PlateBackground->SetContent(V2Plate);
    PlateBackground->SetBrushColor(FLinearColor::Transparent);  // the V2 panel paints its own body
    PlateBackground->SetPadding(FMargin(0.0f));
    Style.SizeSu = FVector2D(UmWorldLayer::PlateWSu, UmWorldLayer::PlateHSu);
  } else {
    bV2 = false;  // before ApplyStyle: the legacy body colour comes back
    PlateBackground->SetContent(LegacyContent);
    Style.SizeSu = LegacySizeSu;
    ApplyStyle();
  }
  bV2 = bOn;
}

void US08ArtPlateWidget::SetShownAnimated(bool bShown) {
  if (bV2 && V2Plate) {
    V2Plate->SetShownAnimated(this, bShown);
  } else {
    SetVisibility(bShown ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  }
}

void US08ArtPlateWidget::FinishFade() {
  if (bV2 && V2Plate) V2Plate->FinishFade();
}

void US08ArtPlateWidget::ApplyTexts(const FS08PlateTexts& Texts) {
  if (bV2 && V2Plate) {
    FUmWorldPlateModel M;
    M.Name = Texts.Name;
    M.Role = Texts.Role;
    M.Side = Texts.Side;
    M.Hp = Texts.Hp;
    M.TeamSlot = Texts.TeamSlot;
    M.bTarget = Texts.bTarget;
    V2Plate->ApplyModel(M);
  }
  bOwn = Texts.bOwn;
  TeamSlot = Texts.TeamSlot;
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
  if (!TeamShape) Missing.Add(TEXT("TeamShape"));
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
  if (bV2 && V2Plate) {
    V2Plate->CollectParts(Out);  // VS-4 HB-46: the same part ids, no marker / bar (the H12 plate has none)
    return;
  }
  S08AddPart(Out, S08ArtHudIds::PlateMarker, Marker);
  S08AddPart(Out, S08ArtHudIds::PlateName, NameText);
  S08AddPart(Out, S08ArtHudIds::PlateTeam, TeamChip);
  S08AddPart(Out, S08ArtHudIds::PlateHpBar, HpBar);
  S08AddPart(Out, S08ArtHudIds::PlateHpFill, HpFill);
  S08AddPart(Out, S08ArtHudIds::PlateHp, HpText);
  S08AddPart(Out, S08ArtHudIds::PlateStatus, StatusText);
  S08AddPart(Out, S08ArtHudIds::PlateTeamShape, TeamShape);
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

FVector2D S08ArtHudPrepassSize(UWidget& Widget) {
  const TSharedRef<SWidget> Slate = Widget.TakeWidget();
  Slate->SlatePrepass(1.0f);
  return Slate->GetDesiredSize();
}

// ------------------------------------------------------------------- tag (W5b-R D-1)

bool US08ArtTagWidget::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  const FS08ArtHudTagStyle Style;
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  auto HSlot = [](UWidget* Child, const FMargin& SlotPadding) {
    if (UHorizontalBoxSlot* Slot = Cast<UHorizontalBoxSlot>(Child->Slot)) {
      Slot->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
      Slot->SetPadding(SlotPadding);
      Slot->SetHorizontalAlignment(HAlign_Left);
      Slot->SetVerticalAlignment(VAlign_Center);
    }
  };
  UBorder* Background = S08Make<UBorder>(Tree, TEXT("TagBackground"));
  Background->SetBrush(S08WhiteBrush());
  Background->SetBrushColor(FS08ArtHudPlateStyle::Linear(Style.Background));
  Background->SetPadding(Style.Padding);
  Background->SetHorizontalAlignment(HAlign_Fill);
  Background->SetVerticalAlignment(VAlign_Fill);
  if (!Attach(Background, nullptr)) return Fail(TEXT("TagBackground"));
  UHorizontalBox* Row = S08Make<UHorizontalBox>(Tree, TEXT("TagRow"));
  if (!Attach(Row, Background)) return Fail(TEXT("TagRow"));
  USizeBox* Chip = S08Make<USizeBox>(Tree, TEXT("ChipBox"));
  Chip->SetWidthOverride(Style.ChipSu);
  Chip->SetHeightOverride(Style.ChipSu);
  if (!Attach(Chip, Row)) return Fail(TEXT("ChipBox"));
  HSlot(Chip, FMargin(0.0f, 0.0f, Style.GapSu, 0.0f));
  UImage* Shape = S08Make<UImage>(Tree, TEXT("TeamShape"));
  Shape->SetBrush(S08WhiteBrush());
  if (!Attach(Shape, Chip)) return Fail(TEXT("TeamShape"));
  UVerticalBox* Column = S08Make<UVerticalBox>(Tree, TEXT("TagColumn"));
  if (!Attach(Column, Row)) return Fail(TEXT("TagColumn"));
  HSlot(Column, FMargin(0.0f));
  UTextBlock* Name = S08MakeText(Tree, TEXT("NameText"), Style.NameFont, Style.Text);
  if (!Attach(Name, Column)) return Fail(TEXT("NameText"));
  if (UVerticalBoxSlot* Slot = Cast<UVerticalBoxSlot>(Name->Slot)) {
    Slot->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
    Slot->SetHorizontalAlignment(HAlign_Left);
  }
  UHorizontalBox* HpRow = S08Make<UHorizontalBox>(Tree, TEXT("HpRow"));
  if (!Attach(HpRow, Column)) return Fail(TEXT("HpRow"));
  if (UVerticalBoxSlot* Slot = Cast<UVerticalBoxSlot>(HpRow->Slot)) {
    Slot->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
    Slot->SetHorizontalAlignment(HAlign_Left);
  }
  USizeBox* Bar = S08Make<USizeBox>(Tree, TEXT("HpBar"));
  Bar->SetWidthOverride(Style.BarWidthSu);
  Bar->SetHeightOverride(Style.BarHeightSu);
  if (!Attach(Bar, HpRow)) return Fail(TEXT("HpBar"));
  HSlot(Bar, FMargin(0.0f, 0.0f, Style.GapSu, 0.0f));
  UOverlay* BarLayers = S08Make<UOverlay>(Tree, TEXT("HpBarLayers"));
  if (!Attach(BarLayers, Bar)) return Fail(TEXT("HpBarLayers"));
  UImage* Back = S08MakeBlock(Tree, TEXT("HpBack"), Style.HpBack);
  if (!Attach(Back, BarLayers)) return Fail(TEXT("HpBack"));
  if (UOverlaySlot* Slot = Cast<UOverlaySlot>(Back->Slot)) {
    Slot->SetHorizontalAlignment(HAlign_Fill);
    Slot->SetVerticalAlignment(VAlign_Fill);
  }
  USizeBox* Fill = S08Make<USizeBox>(Tree, TEXT("HpFill"));
  Fill->SetWidthOverride(Style.BarWidthSu);
  if (!Attach(Fill, BarLayers)) return Fail(TEXT("HpFill"));
  if (UOverlaySlot* Slot = Cast<UOverlaySlot>(Fill->Slot)) {
    Slot->SetHorizontalAlignment(HAlign_Left);
    Slot->SetVerticalAlignment(VAlign_Fill);
  }
  UImage* FillImage = S08MakeBlock(Tree, TEXT("HpFillImage"), Style.HpFill);
  if (!Attach(FillImage, Fill)) return Fail(TEXT("HpFillImage"));
  UTextBlock* Hp = S08MakeText(Tree, TEXT("HpText"), Style.HpFont, Style.Text);
  if (!Attach(Hp, HpRow)) return Fail(TEXT("HpText"));
  HSlot(Hp, FMargin(0.0f));
  return true;
}

bool US08ArtTagWidget::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("S08 art HUD tag default tree: %s"), *Error);
    TagBackground = S08Find<UBorder>(Tree, TEXT("TagBackground"));
    ChipBox = S08Find<USizeBox>(Tree, TEXT("ChipBox"));
    TeamShape = S08Find<UImage>(Tree, TEXT("TeamShape"));
    NameText = S08Find<UTextBlock>(Tree, TEXT("NameText"));
    HpBar = S08Find<USizeBox>(Tree, TEXT("HpBar"));
    HpBack = S08Find<UImage>(Tree, TEXT("HpBack"));
    HpFill = S08Find<USizeBox>(Tree, TEXT("HpFill"));
    HpFillImage = S08Find<UImage>(Tree, TEXT("HpFillImage"));
    HpText = S08Find<UTextBlock>(Tree, TEXT("HpText"));
  }
  return bFirst;
}

void US08ArtTagWidget::NativePreConstruct() {
  Super::NativePreConstruct();
  ApplyStyle();
}

void US08ArtTagWidget::ApplyStyle() {
  if (TagBackground) {
    if (!bBoardPlate) TagBackground->SetBrushColor(FS08ArtHudPlateStyle::Linear(Style.Background));
    TagBackground->SetPadding(Style.Padding);
  }
  if (ChipBox) {
    ChipBox->SetWidthOverride(Style.ChipSu);
    ChipBox->SetHeightOverride(Style.ChipSu);
  }
  S08StyleText(NameText, Style.NameFont, Style.Text);
  S08StyleText(HpText, Style.HpFont, Style.Text);
  if (HpBack) HpBack->SetColorAndOpacity(FS08ArtHudPlateStyle::Linear(Style.HpBack));
  if (HpFillImage) HpFillImage->SetColorAndOpacity(FS08ArtHudPlateStyle::Linear(Style.HpFill));
  if (HpBar) {
    HpBar->SetWidthOverride(Style.BarWidthSu);
    HpBar->SetHeightOverride(Style.BarHeightSu);
  }
  ApplyDynamic();
}

void US08ArtTagWidget::ApplyDynamic() {
  if (TeamShape) {
    if (bShapeBrushes) TeamShape->SetBrush(ShapeBrushes[TeamSlot ? 1 : 0]);
    FS08ArtHudPlateStyle Plate;
    TeamShape->SetColorAndOpacity(Plate.TeamChipColor(TeamSlot));
  }
  if (NameText) {
    NameText->SetVisibility(Mode == ES08TagMode::Full ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  }
  if (HpFill) HpFill->SetWidthOverride(FMath::Max(1.0f, Style.BarWidthSu * HpFraction));
  ApplyBackground();
}

FSlateBrush US08ArtTagWidget::MakeBoardPlateBrush(const FS08ArtHudTagStyle& InStyle, uint8 InTeamSlot) {
  const FS08ArtHudPlateStyle Plate;
  const FColor Accent = InTeamSlot ? Plate.TeamChipP2 : Plate.TeamChipP1;
  return FSlateRoundedBoxBrush(InStyle.BoardPlateFill(), InStyle.BoardPlateCornerSu, InStyle.BoardPlateOutline(Accent),
                               InStyle.BoardPlateOutlineSu);
}

int32 US08ArtTagWidget::HpFontSize() const { return bV2 && V2Tag ? V2Tag->HpFontSize() : Style.HpFont.Size; }

void US08ArtTagWidget::SetV2(bool bOn) {
  if (bOn == bV2 || !TagBackground) return;
  if (bOn) {
    if (!V2Tag) V2Tag = CreateWidget<UUmWorldTag>(this, UUmWorldTag::StaticClass());
    if (!V2Tag) return;
    LegacyContent = TagBackground->GetContent();
    TagBackground->SetContent(V2Tag);
  } else {
    TagBackground->SetContent(LegacyContent);
  }
  bV2 = bOn;
  bBoardPlateBrush = bBoardPlate;  // re-apply below
  ApplyStyle();
}

void US08ArtTagWidget::ApplyBackground() {
  if (!TagBackground) return;
  if (bV2) {
    // VS-4 HB-45: the V2 capsule paints the tag (card.navy, ВР-61) - no flat #161A28 body, no board plate
    TagBackground->SetBrush(FSlateNoResource());
    TagBackground->SetPadding(FMargin(0.0f));
    bBoardPlateBrush = false;
    return;
  }
  if (bBoardPlate) {
    // The fill / outline colours live in the brush; the border tint stays white so nothing multiplies them.
    TagBackground->SetBrush(MakeBoardPlateBrush(Style, TeamSlot));
    TagBackground->SetBrushColor(FLinearColor::White);
    bBoardPlateBrush = true;
  } else if (bBoardPlateBrush) {
    // Back to the flat opaque tag of the grid boards (the code default tree's brush and colour).
    TagBackground->SetBrush(S08WhiteBrush());
    TagBackground->SetBrushColor(FS08ArtHudPlateStyle::Linear(Style.Background));
    bBoardPlateBrush = false;
  }
}

void US08ArtTagWidget::SetBoardPlate(bool bPlate) {
  if (bBoardPlate == bPlate && bBoardPlateBrush == bPlate) return;
  bBoardPlate = bPlate;
  ApplyBackground();
}

void US08ArtTagWidget::SetTeamShapeBrushes(const FSlateBrush& Circle, const FSlateBrush& Hex) {
  ShapeBrushes[0] = Circle;
  ShapeBrushes[1] = Hex;
  bShapeBrushes = true;
  ApplyDynamic();
}

void US08ArtTagWidget::ApplyModel(const FS08TagTexts& Texts) {
  HarpyDigit = Texts.HarpyDigit;
  if (bV2 && V2Tag) {
    FUmWorldTagModel M;
    M.Hp = Texts.HpValue;
    M.MaxHp = Texts.HpMax;
    M.TeamSlot = Texts.TeamSlot;
    M.Digit = Texts.HarpyDigit;
    V2Tag->ApplyModel(M);
  }
  TeamSlot = Texts.TeamSlot;
  HpFraction = FMath::Clamp(Texts.HpFraction, 0.0f, 1.0f);
  Mode = Texts.Mode;
  if (NameText) NameText->SetText(Texts.Name);
  if (HpText) HpText->SetText(Texts.Hp);
  ApplyDynamic();
}

bool US08ArtTagWidget::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!TagBackground) Missing.Add(TEXT("TagBackground"));
  if (!ChipBox) Missing.Add(TEXT("ChipBox"));
  if (!TeamShape) Missing.Add(TEXT("TeamShape"));
  if (!NameText) Missing.Add(TEXT("NameText"));
  if (!HpBar) Missing.Add(TEXT("HpBar"));
  if (!HpBack) Missing.Add(TEXT("HpBack"));
  if (!HpFill) Missing.Add(TEXT("HpFill"));
  if (!HpFillImage) Missing.Add(TEXT("HpFillImage"));
  if (!HpText) Missing.Add(TEXT("HpText"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void US08ArtTagWidget::CollectParts(TArray<FS08WidgetPart>& Out) const {
  Out.Add({S08ArtHudIds::Tag, GetCachedWidget()});
  if (bV2 && V2Tag) {
    V2Tag->CollectParts(Out);  // VS-4 HB-45: hp, bar, chip - never a name (ВР-07)
    return;
  }
  if (Mode == ES08TagMode::Full) S08AddPart(Out, S08ArtHudIds::TagName, NameText);
  S08AddPart(Out, S08ArtHudIds::TagHp, HpText);
  S08AddPart(Out, S08ArtHudIds::TagBar, HpBar);
  S08AddPart(Out, S08ArtHudIds::TagChip, ChipBox);
}

// ------------------------------------------------------------------- damage number (W5b-R D-1)

bool US08ArtDamageWidget::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  const FS08ArtHudDamageStyle Style;
  UBorder* Background = S08Make<UBorder>(Tree, TEXT("DamageBackground"));
  Background->SetBrush(FSlateRoundedBoxBrush(FLinearColor::White, Style.CornerRadiusSu));
  Background->SetBrushColor(FS08ArtHudPlateStyle::Linear(Style.Background));
  Background->SetPadding(Style.Padding);
  Background->SetHorizontalAlignment(HAlign_Center);
  Background->SetVerticalAlignment(VAlign_Center);
  if (!Attach(Background, nullptr)) {
    if (OutError) *OutError = TEXT("attach failed: DamageBackground");
    return false;
  }
  UTextBlock* Text = S08MakeText(Tree, TEXT("DamageText"), Style.Font, Style.Text);
  if (!Attach(Text, Background)) {
    if (OutError) *OutError = TEXT("attach failed: DamageText");
    return false;
  }
  return true;
}

bool US08ArtDamageWidget::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("S08 art HUD damage default tree: %s"), *Error);
    DamageBackground = S08Find<UBorder>(Tree, TEXT("DamageBackground"));
    DamageText = S08Find<UTextBlock>(Tree, TEXT("DamageText"));
  }
  return bFirst;
}

void US08ArtDamageWidget::NativePreConstruct() {
  Super::NativePreConstruct();
  ApplyStyle();
}

void US08ArtDamageWidget::ApplyStyle() {
  if (DamageBackground) {
    DamageBackground->SetBrush(FSlateRoundedBoxBrush(FLinearColor::White, Style.CornerRadiusSu));
    DamageBackground->SetBrushColor(FS08ArtHudPlateStyle::Linear(Style.Background));
    DamageBackground->SetPadding(Style.Padding);
  }
  S08StyleText(DamageText, Style.Font, Style.Text);
}

void US08ArtDamageWidget::ApplyAmount(const FText& Text) {
  if (DamageText) DamageText->SetText(Text);
}

bool US08ArtDamageWidget::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!DamageBackground) Missing.Add(TEXT("DamageBackground"));
  if (!DamageText) Missing.Add(TEXT("DamageText"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void US08ArtDamageWidget::CollectParts(TArray<FS08WidgetPart>& Out) const {
  Out.Add({S08ArtHudIds::Damage, GetCachedWidget()});
  S08AddPart(Out, S08ArtHudIds::DamageText, DamageText);
}

#include "S08ArtHudViews.h"

#include "Misc/PackageName.h"
#include "Styling/CoreStyle.h"
#include "UObject/UObjectGlobals.h"
#include "Widgets/Colors/SColorBlock.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

bool S08ParseArtHudImpl(const FString& Text, ES08ArtHudImpl& Out) {
  const FString T = Text.TrimStartAndEnd().ToLower();
  if (T.IsEmpty() || T == TEXT("umg")) {
    Out = ES08ArtHudImpl::Umg;
    return true;
  }
  if (T == TEXT("slate")) {
    Out = ES08ArtHudImpl::Slate;
    return true;
  }
  if (T == TEXT("compare")) {
    Out = ES08ArtHudImpl::Compare;
    return true;
  }
  if (T == TEXT("alternate")) {
    Out = ES08ArtHudImpl::Alternate;
    return true;
  }
  return false;
}

const TCHAR* S08ArtHudImplName(ES08ArtHudImpl Impl) {
  switch (Impl) {
    case ES08ArtHudImpl::Slate: return TEXT("slate");
    case ES08ArtHudImpl::Compare: return TEXT("compare");
    case ES08ArtHudImpl::Alternate: return TEXT("alternate");
    default: return TEXT("umg");
  }
}

UClass* S08LoadArtHudWidgetClass(const TCHAR* BlueprintPath, UClass* Native) {
  const FString Path(BlueprintPath);
  const FString ClassPath = FString::Printf(TEXT("%s.%s_C"), *Path, *FPackageName::GetShortName(Path));
  UClass* Class = LoadClass<UUserWidget>(nullptr, *ClassPath, nullptr, LOAD_Quiet | LOAD_NoWarn);
  return (Class && Native && Class->IsChildOf(Native)) ? Class : nullptr;
}

namespace {
// ---------------------------------------------------------------- Slate path
// The T2.2 plate exactly as it was built inline in AS08FlowGameMode
// (S08FlowGameMode.cpp BuildArtHudWidgets, 2026-09-28); only the constants
// now come from the Style tokens (same values).
class FS08SlatePlateView final : public IS08ArtPlateView {
public:
  explicit FS08SlatePlateView(const FS08ArtHudPlateStyle& InStyle) : Style(InStyle) {
    const FLinearColor NameColor = FS08ArtHudPlateStyle::Linear(Style.NameText);
    Root = SNew(SBorder)
               .Visibility(EVisibility::Collapsed)
               .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
               .BorderBackgroundColor(FSlateColor(FS08ArtHudPlateStyle::Linear(Style.Background)))
               .Padding(0.0f)
               [SNew(SVerticalBox) +
                SVerticalBox::Slot().AutoHeight()
                    [SNew(SBox).HeightOverride(S08ArtHudLayout::MarkerHeightSu)
                         [SAssignNew(Marker, SColorBlock).Color(FS08ArtHudPlateStyle::Linear(Style.Marker))]] +
                SVerticalBox::Slot().AutoHeight().Padding(S08ArtHudLayout::NameRowPadding)
                    [SNew(SHorizontalBox) +
                     SHorizontalBox::Slot().FillWidth(1.0f).VAlign(VAlign_Center)
                         [SAssignNew(Name, STextBlock)
                              .Font(Style.NameFont.Resolve())
                              .ColorAndOpacity(FSlateColor(NameColor))] +
                     SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
                         [SAssignNew(Chip, SBorder)
                              .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
                              .BorderBackgroundColor(FSlateColor(Style.ChipColor(true)))
                              .Padding(S08ArtHudLayout::ChipPadding)
                              [SAssignNew(Team, STextBlock)
                                   .Font(Style.TeamFont.Resolve())
                                   .ColorAndOpacity(FSlateColor(NameColor))]]] +
                SVerticalBox::Slot().AutoHeight().Padding(S08ArtHudLayout::HpRowPadding)
                    [SNew(SHorizontalBox) +
                     SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
                         [SAssignNew(HpBar, SBox)
                              .WidthOverride(Style.HpBarWidthSu)
                              .HeightOverride(S08ArtHudLayout::HpBarHeightSu)
                              [SNew(SOverlay) +
                               SOverlay::Slot()[SNew(SColorBlock).Color(FS08ArtHudPlateStyle::Linear(Style.HpBack))] +
                               SOverlay::Slot().HAlign(HAlign_Left)
                                   [SAssignNew(HpFill, SBox).WidthOverride(Style.HpBarWidthSu)
                                        [SNew(SColorBlock).Color(FS08ArtHudPlateStyle::Linear(Style.HpFill))]]]] +
                     SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(S08ArtHudLayout::HpTextPadding)
                         [SAssignNew(Hp, STextBlock)
                              .Font(Style.HpFont.Resolve())
                              .ColorAndOpacity(FSlateColor(NameColor))]] +
                SVerticalBox::Slot().AutoHeight().Padding(S08ArtHudLayout::StatusPadding)
                    [SAssignNew(Status, STextBlock)
                         .Font(Style.StatusFont.Resolve())
                         .ColorAndOpacity(FSlateColor(FS08ArtHudPlateStyle::Linear(Style.StatusText)))]];
  }

  const TCHAR* ImplName() const override { return TEXT("slate"); }
  FString Source() const override { return TEXT("slate"); }
  TSharedRef<SWidget> GetRoot() override { return Root.ToSharedRef(); }
  FVector2D SizeSu() const override { return Style.SizeSu; }

  void ApplyTexts(const FS08PlateTexts& Texts) override {
    Name->SetText(Texts.Name);
    Hp->SetText(Texts.Hp);
    HpFill->SetWidthOverride(FOptionalSize(FMath::Max(1.0f, Style.HpBarWidthSu * Texts.HpFraction)));
    Team->SetText(Texts.Team);
    Chip->SetBorderBackgroundColor(FSlateColor(Style.ChipColor(Texts.bOwn)));
    Status->SetText(Texts.Statuses);
  }

  void SetShown(bool bShown) override {
    Root->SetVisibility(bShown ? EVisibility::HitTestInvisible : EVisibility::Collapsed);
  }

  void SetTwin(bool bInTwin) override {
    bTwin = bInTwin;
    Root->SetRenderOpacity(bInTwin ? 0.0f : 1.0f);
  }

  void CollectParts(TArray<FS08WidgetPart>& Out) const override {
    Out.Add({S08ArtHudIds::Plate, Root});
    Out.Add({S08ArtHudIds::PlateMarker, Marker});
    Out.Add({S08ArtHudIds::PlateName, Name});
    Out.Add({S08ArtHudIds::PlateTeam, Chip});
    Out.Add({S08ArtHudIds::PlateHpBar, HpBar});
    Out.Add({S08ArtHudIds::PlateHpFill, HpFill});
    Out.Add({S08ArtHudIds::PlateHp, Hp});
    Out.Add({S08ArtHudIds::PlateStatus, Status});
  }

private:
  FS08ArtHudPlateStyle Style;
  TSharedPtr<SBorder> Root;
  TSharedPtr<SColorBlock> Marker;
  TSharedPtr<STextBlock> Name;
  TSharedPtr<SBorder> Chip;
  TSharedPtr<STextBlock> Team;
  TSharedPtr<SBox> HpBar;
  TSharedPtr<SBox> HpFill;
  TSharedPtr<STextBlock> Hp;
  TSharedPtr<STextBlock> Status;
};

class FS08SlateIconView final : public IS08ArtIconView {
public:
  FS08SlateIconView() {
    Image = SNew(SImage).Visibility(EVisibility::Collapsed).Image(&Brush);
  }
  const TCHAR* ImplName() const override { return TEXT("slate"); }
  FString Source() const override { return TEXT("slate"); }
  TSharedRef<SWidget> GetRoot() override { return Image.ToSharedRef(); }
  void SetIconBrush(const FSlateBrush& InBrush) override {
    Brush = InBrush;
    Image->SetImage(&Brush);
    // Same pointer: SetImage does not invalidate; the brush size changed.
    Image->Invalidate(EInvalidateWidgetReason::Layout);
  }
  void SetShown(bool bShown) override {
    Image->SetVisibility(bShown ? EVisibility::HitTestInvisible : EVisibility::Collapsed);
  }
  void SetTwin(bool bInTwin) override {
    bTwin = bInTwin;
    Image->SetRenderOpacity(bInTwin ? 0.0f : 1.0f);
  }
  void CollectParts(TArray<FS08WidgetPart>& Out) const override { Out.Add({S08ArtHudIds::Icon, Image}); }

private:
  FSlateBrush Brush;
  TSharedPtr<SImage> Image;
};

// ------------------------------------------------------------------ UMG path
class FS08UmgPlateView final : public IS08ArtPlateView {
public:
  FS08UmgPlateView(US08ArtPlateWidget& InWidget, const FString& InSource) : Widget(&InWidget), SourceName(InSource) {
    InWidget.SetVisibility(ESlateVisibility::Collapsed);
  }
  const TCHAR* ImplName() const override { return TEXT("umg"); }
  FString Source() const override { return SourceName; }
  TSharedRef<SWidget> GetRoot() override { return Widget->TakeWidget(); }
  FVector2D SizeSu() const override { return Widget.IsValid() ? Widget->GetPlateSizeSu() : FVector2D::ZeroVector; }
  void ApplyTexts(const FS08PlateTexts& Texts) override {
    if (Widget.IsValid()) Widget->ApplyTexts(Texts);
  }
  void SetShown(bool bShown) override {
    if (Widget.IsValid()) {
      Widget->SetVisibility(bShown ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    }
  }
  void SetTwin(bool bInTwin) override {
    bTwin = bInTwin;
    if (Widget.IsValid()) Widget->SetRenderOpacity(bInTwin ? 0.0f : 1.0f);
  }
  void CollectParts(TArray<FS08WidgetPart>& Out) const override {
    if (Widget.IsValid()) Widget->CollectParts(Out);
  }

private:
  TWeakObjectPtr<US08ArtPlateWidget> Widget;
  FString SourceName;
};

class FS08UmgIconView final : public IS08ArtIconView {
public:
  FS08UmgIconView(US08ArtIconWidget& InWidget, const FString& InSource) : Widget(&InWidget), SourceName(InSource) {
    InWidget.SetVisibility(ESlateVisibility::Collapsed);
  }
  const TCHAR* ImplName() const override { return TEXT("umg"); }
  FString Source() const override { return SourceName; }
  TSharedRef<SWidget> GetRoot() override { return Widget->TakeWidget(); }
  void SetIconBrush(const FSlateBrush& Brush) override {
    if (Widget.IsValid()) Widget->SetIconBrush(Brush);
  }
  void SetShown(bool bShown) override {
    if (Widget.IsValid()) {
      Widget->SetVisibility(bShown ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    }
  }
  void SetTwin(bool bInTwin) override {
    bTwin = bInTwin;
    if (Widget.IsValid()) Widget->SetRenderOpacity(bInTwin ? 0.0f : 1.0f);
  }
  void CollectParts(TArray<FS08WidgetPart>& Out) const override {
    if (Widget.IsValid()) Widget->CollectParts(Out);
  }

private:
  TWeakObjectPtr<US08ArtIconWidget> Widget;
  FString SourceName;
};
}  // namespace

TSharedRef<IS08ArtPlateView> S08MakeSlatePlateView(const FS08ArtHudPlateStyle& Style) {
  return MakeShared<FS08SlatePlateView>(Style);
}

TSharedRef<IS08ArtIconView> S08MakeSlateIconView() { return MakeShared<FS08SlateIconView>(); }

TSharedRef<IS08ArtPlateView> S08MakeUmgPlateView(US08ArtPlateWidget& Widget, const FString& Source) {
  return MakeShared<FS08UmgPlateView>(Widget, Source);
}

TSharedRef<IS08ArtIconView> S08MakeUmgIconView(US08ArtIconWidget& Widget, const FString& Source) {
  return MakeShared<FS08UmgIconView>(Widget, Source);
}

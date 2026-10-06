// VS-2 HB-10 / HB-11 review sheets - see UmHudGallery.h.
#include "UmHudGallery.h"

#include "../S08HudTokens.generated.h"
#include "UmButton.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/GridPanel.h"
#include "Components/GridSlot.h"
#include "Components/Image.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"

namespace {
UTextBlock* UmGalText(UWidgetTree& Tree, const FString& Text, FName ColorToken) {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
  T->SetText(FText::FromString(Text));
  T->SetFont(Theme.Font(TEXT("type.caption")));
  T->SetColorAndOpacity(FSlateColor(Theme.Color(ColorToken)));
  T->SetShadowOffset(FVector2D::ZeroVector);
  return T;
}

void UmGalPut(UGridPanel* Grid, UWidget* W, int32 Row, int32 Col, const FMargin& Pad) {
  if (UGridSlot* Slot = Grid->AddChildToGrid(W, Row, Col)) {
    Slot->SetPadding(Pad);
    Slot->SetHorizontalAlignment(HAlign_Left);
    Slot->SetVerticalAlignment(VAlign_Center);
  }
}

constexpr float UmGalRowSu = 72.0f;
constexpr float UmGalMarginSu = 24.0f;
constexpr float UmGalHeaderSu = 32.0f;
}  // namespace

bool UUmSkinGalleryWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    const UUmHudTheme& Theme = UUmHudTheme::Get();
    Background = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("Background"));
    Background->SetBrushColor(Theme.Color(TEXT("panel.bg.inset")));
    Background->SetPadding(FMargin(UmGalMarginSu));
    Grid = WidgetTree->ConstructWidget<UGridPanel>(UGridPanel::StaticClass(), TEXT("Grid"));
    Background->SetContent(Grid);
    WidgetTree->RootWidget = Background;
  }
  return bFirst;
}

FString UUmSkinGalleryWidget::Build(int32 Page, const FVector2D& CanvasSu, float PxPerSu) {
  if (!Grid) return TEXT("UMGALLERY skins failed: no grid");
  Grid->ClearChildren();
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const int32 Total = S08HudTokens::kNumSkins;
  const int32 Rows = FMath::Max(1, FMath::FloorToInt((CanvasSu.Y - 2.0f * UmGalMarginSu - UmGalHeaderSu) / UmGalRowSu));
  PageCount = FMath::DivideAndRoundUp(Total, Rows);
  Page = FMath::Clamp(Page, 0, PageCount - 1);
  const bool bX2 = PxPerSu >= UUmHudTheme::SkinX2MinPxPerSu;
  const TCHAR* Heads[] = {TEXT("skin"), TEXT("x1 size"), TEXT("button"), TEXT("wide"), TEXT("x1 on cream"), TEXT("wide on cream")};
  for (int32 C = 0; C < UE_ARRAY_COUNT(Heads); ++C) {
    UmGalPut(Grid, UmGalText(*WidgetTree, Heads[C], TEXT("text.secondary")), 0, C, FMargin(0.0f, 0.0f, 16.0f, 8.0f));
  }
  int32 Textures = 0;
  for (int32 I = 0; I < Total; ++I) Textures += Theme.HasTextureSkin(S08HudTokens::kSkins[I].Name) ? 1 : 0;
  int32 Row = 1;
  for (int32 I = Page * Rows; I < FMath::Min(Total, (Page + 1) * Rows); ++I, ++Row) {
    const FName Key(S08HudTokens::kSkins[I].Name);
    const FSlateBrush* Brush = Theme.SkinFor(Key, PxPerSu);
    const bool bTexture = Theme.HasTextureSkin(Key);
    UmGalPut(Grid, UmGalText(*WidgetTree, Key.ToString() + (bTexture ? TEXT("") : TEXT(" (fallback)")), TEXT("text.primary")),
             Row, 0, FMargin(0.0f, 0.0f, 16.0f, 0.0f));
    if (!Brush) continue;
    const FVector2D Native = Brush->ImageSize.X > 0 ? FVector2D(Brush->ImageSize) : FVector2D(34.0, 26.0);
    const bool bStretch = Brush->DrawAs == ESlateBrushDrawType::Box || Brush->DrawAs == ESlateBrushDrawType::RoundedBox;
    const FVector2D Sizes[] = {
        Native,
        bStretch ? FVector2D(FMath::Max(Native.X, 120.0), FMath::Max(Native.Y, 40.0)) : Native,
        bStretch ? FVector2D(FMath::Max(Native.X * 3.0, 200.0), FMath::Max(Native.Y * 1.5, 56.0)) : Native,
    };
    const int32 Cols[] = {1, 2, 3, 4, 5};
    const int32 SizeOf[] = {0, 1, 2, 0, 2};
    for (int32 K = 0; K < 5; ++K) {
      UBorder* Back = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
      Back->SetBrushColor(Theme.Color(K < 3 ? TEXT("card.navy") : TEXT("card.cream")));
      Back->SetPadding(FMargin(8.0f));
      USizeBox* Size = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
      Size->SetWidthOverride(static_cast<float>(Sizes[SizeOf[K]].X));
      Size->SetHeightOverride(static_cast<float>(Sizes[SizeOf[K]].Y));
      UImage* Image = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass());
      Image->SetBrush(*Brush);
      Size->AddChild(Image);
      Back->SetContent(Size);
      UmGalPut(Grid, Back, Row, Cols[K], FMargin(0.0f, 0.0f, 12.0f, 0.0f));
    }
  }
  return FString::Printf(TEXT("UMGALLERY skins page=%d/%d rows=%d pxPerSu=%.3f x2=%d textures=%d/%d"), Page + 1, PageCount,
                         Rows, PxPerSu, bX2 ? 1 : 0, Textures, Total);
}

bool UUmButtonGalleryWidget::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    const UUmHudTheme& Theme = UUmHudTheme::Get();
    Background = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("Background"));
    Background->SetBrushColor(Theme.Color(TEXT("panel.bg.inset")));
    Background->SetPadding(FMargin(UmGalMarginSu));
    Grid = WidgetTree->ConstructWidget<UGridPanel>(UGridPanel::StaticClass(), TEXT("Grid"));
    Background->SetContent(Grid);
    WidgetTree->RootWidget = Background;
  }
  return bFirst;
}

TArray<FString> UUmButtonGalleryWidget::Build(const FVector2D& CanvasSu, int32 OnlyVariant) {
  TArray<FString> Lines;
  if (!Grid) return Lines;
  Grid->ClearChildren();
  Buttons.Reset();
  const EUmButtonState States[] = {EUmButtonState::Normal,  EUmButtonState::Hover, EUmButtonState::Pressed,
                                   EUmButtonState::Disabled, EUmButtonState::Focus, EUmButtonState::Selected,
                                   EUmButtonState::Busy};
  struct FRow {
    EUmButtonVariant Variant;
    const TCHAR* LabelKey;
    FName Icon;
    const TCHAR* KeyHint;
    const TCHAR* Why;
  };
  // real HUD strings (ST_Hud) and reasons (ST_Why) of the blocks that will use each variant
  const FRow Rows[] = {
      {EUmButtonVariant::Normal, TEXT("hud.combat.no.defense"), NAME_None, TEXT("hud.key.no_defense"), TEXT("why.deadline.passed")},
      {EUmButtonVariant::Primary, TEXT("hud.combat.defend"), NAME_None, TEXT("hud.key.confirm"), TEXT("why.defense.none")},
      {EUmButtonVariant::Disc, TEXT("hud.action.maneuver"), FName(TEXT("action-maneuver")), TEXT("hud.key.maneuver"), TEXT("why.not.your.turn")},
  };
  // as many states per line as the canvas holds (7 at 1920 su, 5 at 1137.8 su - 720p 150 %); each cell names its state
  constexpr float CellSu = 260.0f;
  constexpr float LabelColumnSu = 96.0f;
  const int32 States_ = UE_ARRAY_COUNT(States);
  const int32 PerLine = FMath::Clamp(FMath::FloorToInt((CanvasSu.X - 2.0f * UmGalMarginSu - LabelColumnSu) / CellSu), 3, States_);
  const int32 LinesPerRow = FMath::DivideAndRoundUp(States_, PerLine);
  int32 Shown = 0;
  for (int32 Ri = 0; Ri < UE_ARRAY_COUNT(Rows); ++Ri) {
    if (OnlyVariant >= 1 && OnlyVariant != Ri + 1) continue;  // one variant per page (720p 150 %)
    const int32 R = Shown++;
    UmGalPut(Grid, UmGalText(*WidgetTree, UmButtonVariantName(Rows[Ri].Variant), TEXT("text.secondary")), R * LinesPerRow, 0,
             FMargin(0.0f, 0.0f, 16.0f, 0.0f));
    for (int32 C = 0; C < UE_ARRAY_COUNT(States); ++C) {
      UUmButton* Button = CreateWidget<UUmButton>(this, UUmButton::StaticClass());
      if (!Button) continue;
      const EUmButtonState S = States[C];
      FUmButtonModel M;
      M.Variant = Rows[Ri].Variant;
      M.Label = UmText::Get(EUmTable::Hud, Rows[Ri].LabelKey);
      M.IconName = Rows[Ri].Icon;
      M.KeyHint = UmText::Get(EUmTable::Hud, Rows[Ri].KeyHint);
      M.bEnabled = S != EUmButtonState::Disabled;
      M.Reason = S == EUmButtonState::Disabled ? FS09Reason::Make(Rows[Ri].Why) : FS09Reason();
      M.bSelected = S == EUmButtonState::Selected;
      M.bBusy = S == EUmButtonState::Busy;
      M.bFocused = S == EUmButtonState::Focus;
      Button->ApplyModel(M);
      Button->SetPreviewPointer(S == EUmButtonState::Hover, S == EUmButtonState::Pressed);
      UVerticalBox* Cell = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
      Cell->AddChildToVerticalBox(UmGalText(*WidgetTree, UmButtonStateName(S), TEXT("text.secondary")));
      if (UVerticalBoxSlot* ButtonSlot = Cell->AddChildToVerticalBox(Button)) {
        ButtonSlot->SetPadding(FMargin(0.0f, 4.0f, 0.0f, 0.0f));
        ButtonSlot->SetHorizontalAlignment(HAlign_Left);
      }
      UmGalPut(Grid, Cell, R * LinesPerRow + C / PerLine, C % PerLine + 1, FMargin(0.0f, 8.0f, 16.0f, 8.0f));
      Buttons.Add(Button);
      Lines.Add(FString::Printf(TEXT("UMGALLERY button %s.%s: %s"), UmButtonVariantName(M.Variant), UmButtonStateName(S),
                                *Button->DescribeState()));
    }
  }
  Lines.Insert(FString::Printf(TEXT("UMGALLERY buttons variants=%d states=%d perLine=%d canvas=%.0fx%.0f page=%d"),
                               Shown, UE_ARRAY_COUNT(States), PerLine, CanvasSu.X, CanvasSu.Y, OnlyVariant),
               0);
  return Lines;
}

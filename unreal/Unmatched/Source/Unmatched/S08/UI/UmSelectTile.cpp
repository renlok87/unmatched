// SEL select-screen tile - see UmSelectTile.h.
#include "UmSelectTile.h"

#include "UmHeroCard.h"
#include "UmHudScale.h"
#include "UmHudTheme.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Engine/Texture2D.h"

using namespace UmRoomUi;

namespace {
constexpr float TileHoverRiseSu = 6.0f;
constexpr float TileFrameSu = 3.0f;
constexpr float TileBandSu = 30.0f;
constexpr float TileBadgeSu = 30.0f;

FLinearColor TeamColor(ES08TeamSlot Slot, float Alpha = 1.0f) {
  FLinearColor C = FLinearColor(S08TeamPalette::ChipColor(Slot));  // the on-screen team colour (HUD chips)
  C.A = Alpha;
  return C;
}
}  // namespace

bool UUmSelectTile::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  if (!WidgetTree->RootWidget) {
    Canvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Canvas")));
    WidgetTree->RootWidget = Canvas;
    auto Border = [this](const TCHAR* Name) {
      UBorder* B = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), FName(Name));
      B->SetVisibility(ESlateVisibility::HitTestInvisible);
      B->SetPadding(FMargin(0.0f));
      B->SetHorizontalAlignment(HAlign_Center);
      B->SetVerticalAlignment(VAlign_Center);
      B->SetBrush(FSlateNoResource());
      Canvas->AddChild(B);
      return B;
    };
    auto Text = [this](const TCHAR* Name) {
      UTextBlock* T = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
      T->SetVisibility(ESlateVisibility::HitTestInvisible);
      Canvas->AddChild(T);
      return T;
    };
    Plate = Border(TEXT("Plate"));
    Picture = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("Picture")));
    Picture->SetVisibility(ESlateVisibility::HitTestInvisible);
    Canvas->AddChild(Picture);
    Glyph = Text(TEXT("Glyph"));
    Band = Border(TEXT("Band"));
    Caption = Text(TEXT("Caption"));
    Frame = Border(TEXT("Frame"));
    Badge = Border(TEXT("Badge"));
    BadgeText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("BadgeText")));
    BadgeText->SetVisibility(ESlateVisibility::HitTestInvisible);
    Badge->SetContent(BadgeText);
  }
  Style(Caption, TEXT("type.caption"), TEXT("text.primary"));
  Style(Glyph, TEXT("type.display"), TEXT("text.primary"));
  Style(BadgeText, TEXT("type.caption"), TEXT("text.primary"));
  if (Caption) {
    Caption->SetJustification(ETextJustify::Center);
    Caption->SetTextOverflowPolicy(ETextOverflowPolicy::Ellipsis);
    Caption->SetClipping(EWidgetClipping::ClipToBounds);
  }
  if (Glyph) {
    Glyph->SetJustification(ETextJustify::Center);
    Glyph->SetText(FText::FromString(TEXT("?")));
  }
  if (BadgeText) BadgeText->SetJustification(ETextJustify::Center);
  SetVisibility(ESlateVisibility::Visible);
  return bFirst;
}

void UUmSelectTile::Apply(const FUmSelectTileModel& InModel, const FVector2D& InSizeSu, ES08TeamSlot InViewerLook) {
  Model = InModel;
  SizeSu = InSizeSu;
  ViewerLook = InViewerLook;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const float Px = UmHudScale::Current().PxPerSu();
  if (Plate) {
    if (const FSlateBrush* Skin = Theme.SkinFor(TEXT("hud.table.card"), Px)) {
      Plate->SetBrush(*Skin);
    } else {
      Plate->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("card.navy")), 8.0f, Theme.Color(TEXT("panel.edge")), 2.0f));
    }
  }
  if (Picture) {
    if (Model.Image) {
      FSlateBrush B;
      B.SetResourceObject(Model.Image);
      B.ImageSize = FVector2D(Model.Image->GetSizeX(), Model.Image->GetSizeY());
      B.DrawAs = ESlateBrushDrawType::Image;
      B.SetUVRegion(Model.Region);
      Picture->SetBrush(B);
    }
    Picture->SetVisibility(Model.Image ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  }
  if (Glyph) Glyph->SetVisibility(Model.Image ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
  if (Band) {
    FLinearColor Ink = Theme.Color(TEXT("card.navy"));
    Ink.A = 0.86f;
    Band->SetBrush(FSlateRoundedBoxBrush(Ink, FVector4(0.0f, 0.0f, 6.0f, 6.0f)));
  }
  if (Caption) Caption->SetText(FText::FromString(Model.Label));
  if (Badge && BadgeText) {
    Badge->SetBrush(FSlateRoundedBoxBrush(TeamColor(Model.BadgeLook), 0.5f * TileBadgeSu, S08TeamPalette::Keyline(), 2.0f));
    BadgeText->SetText(FText::AsNumber(Model.BadgeDigit));
    BadgeText->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("card.navy"))));
  }
  Layout();
}

void UUmSelectTile::Layout() {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const float Rise = bHover && IsClickable() ? TileHoverRiseSu : 0.0f;
  const float W = SizeSu.X, H = SizeSu.Y;
  const float Y0 = -Rise;
  Place(Plate, FVector2D(0.0f, Y0), FVector2D(W, H));
  // the image inside the plate rim (4 su), above the caption band
  const float Inset = 6.0f;
  Place(Picture, FVector2D(Inset, Y0 + Inset), FVector2D(W - 2.0f * Inset, H - 2.0f * Inset - TileBandSu));
  Place(Glyph, FVector2D(Inset, Y0 + 0.5f * (H - TileBandSu) - 36.0f), FVector2D(W - 2.0f * Inset, 64.0f));
  Place(Band, FVector2D(Inset, Y0 + H - Inset - TileBandSu), FVector2D(W - 2.0f * Inset, TileBandSu));
  Place(Caption, FVector2D(Inset + 4.0f, Y0 + H - Inset - TileBandSu + 5.0f), FVector2D(W - 2.0f * Inset - 8.0f, 20.0f));
  // the frame: the viewer's team colour on hover / selected, the bronze edge otherwise
  if (Frame) {
    const bool bLit = (bHover && IsClickable()) || Model.bSelected;
    const FLinearColor Edge = bLit ? TeamColor(Model.bSelected && !bHover ? Model.BadgeLook : ViewerLook)
                                   : Theme.Color(TEXT("panel.edge"));
    Frame->SetBrush(FSlateRoundedBoxBrush(FLinearColor::Transparent, 8.0f, Edge, bLit ? TileFrameSu : 1.0f));
  }
  Place(Frame, FVector2D(-1.0f, Y0 - 1.0f), FVector2D(W + 2.0f, H + 2.0f));
  Place(Badge, FVector2D(W - TileBadgeSu + 6.0f, Y0 - 6.0f), FVector2D(TileBadgeSu, TileBadgeSu));
  if (Badge) Badge->SetVisibility(Model.bBadge ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  const float Opacity = Model.State == EUmTileState::Taken ? 0.5f : Model.State == EUmTileState::Disabled ? 0.7f : 1.0f;
  // dimmed below the badge: the badge of the other side stays readable on a taken tile
  for (UWidget* Part : {static_cast<UWidget*>(Plate), static_cast<UWidget*>(Picture), static_cast<UWidget*>(Glyph),
                        static_cast<UWidget*>(Band), static_cast<UWidget*>(Caption)}) {
    if (Part) Part->SetRenderOpacity(Opacity);
  }
}

void UUmSelectTile::NativeOnMouseEnter(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  Super::NativeOnMouseEnter(InGeometry, InMouseEvent);
  bHover = true;
  Layout();
  if (OnHover) OnHover(true);
}

void UUmSelectTile::NativeOnMouseLeave(const FPointerEvent& InMouseEvent) {
  Super::NativeOnMouseLeave(InMouseEvent);
  bHover = false;
  bDown = false;
  Layout();
  if (OnHover) OnHover(false);
}

FReply UUmSelectTile::NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (InMouseEvent.GetEffectingButton() != EKeys::LeftMouseButton) return FReply::Unhandled();
  bDown = true;
  return FReply::Handled();
}

FReply UUmSelectTile::NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (InMouseEvent.GetEffectingButton() != EKeys::LeftMouseButton || !bDown) return FReply::Unhandled();
  bDown = false;
  if (IsClickable() && OnClick) OnClick();
  return FReply::Handled();
}

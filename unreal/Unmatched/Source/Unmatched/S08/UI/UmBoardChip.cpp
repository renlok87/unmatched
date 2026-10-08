// VS-7 SC-09: one board tile of the LOBBY - see UmBoardChip.h.
#include "UmBoardChip.h"

#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHudTheme.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Engine/Texture2D.h"

namespace UmBoardChip {
FString ThumbPath(const FString& BoardId) {
  // the two real maps only (AGENTS.md); the thumbnails are the whole map illustrations (scraped-data/images/maps)
  if (BoardId == TEXT("c121b47f8d6eb28daccb76d05")) return TEXT("/Game/S08/UI/Boards/T_BoardThumb_marmoreal.T_BoardThumb_marmoreal");
  if (BoardId == TEXT("c7fa64a26c29a0835f2383e63")) return TEXT("/Game/S08/UI/Boards/T_BoardThumb_sarpedon.T_BoardThumb_sarpedon");
  return FString();
}

FBox2D ImageRect(const FVector2D& TileSu, const FVector2D& SrcPx) {
  const FVector2D Area(FMath::Max(0.0, TileSu.X - 2.0 * InsetSu), FMath::Max(0.0, TileSu.Y - 2.0 * InsetSu - NameRowSu));
  if (SrcPx.X <= 0.0 || SrcPx.Y <= 0.0 || Area.X <= 0.0 || Area.Y <= 0.0) return FBox2D(FVector2D(InsetSu), FVector2D(InsetSu));
  const double S = FMath::Min(Area.X / SrcPx.X, Area.Y / SrcPx.Y);
  const FVector2D Size = SrcPx * S;
  const FVector2D Min = FVector2D(InsetSu) + 0.5 * (Area - Size);
  return FBox2D(Min, Min + Size);
}
}  // namespace UmBoardChip

namespace {
void UmBcPlace(UWidget* W, const FVector2D& Pos, const FVector2D& Size) {
  if (UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr) {
    S->SetAnchors(FAnchors(0.0f, 0.0f));
    S->SetAlignment(FVector2D::ZeroVector);
    S->SetAutoSize(false);
    S->SetPosition(Pos);
    S->SetSize(Size);
  }
}
}  // namespace

bool UUmBoardChip::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  if (!WidgetTree->RootWidget) {
    UCanvasPanel* Canvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Canvas")));
    WidgetTree->RootWidget = Canvas;
    UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
    Button = WidgetTree->ConstructWidget<UUmButton>(ButtonClass, FName(TEXT("Button")));
    Canvas->AddChild(Button);
    Thumb = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("Thumb")));
    Thumb->SetVisibility(ESlateVisibility::HitTestInvisible);
    Canvas->AddChild(Thumb);
    NameText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("NameText")));
    NameText->SetVisibility(ESlateVisibility::HitTestInvisible);
    NameText->SetJustification(ETextJustify::Center);
    Canvas->AddChild(NameText);
  }
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (NameText) {
    NameText->SetFont(Theme.Font(TEXT("type.body")));
    NameText->SetShadowOffset(FVector2D::ZeroVector);
  }
  return bFirst;
}

void UUmBoardChip::Setup(const FString& InBoardId, const FText& InName) {
  BoardId = InBoardId;
  if (NameText) NameText->SetText(InName);
  ThumbTexture = nullptr;
  const FString Path = UmBoardChip::ThumbPath(BoardId);
  if (!Path.IsEmpty()) ThumbTexture = LoadObject<UTexture2D>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
  if (!ThumbTexture) UE_LOG(LogTemp, Log, TEXT("BOARDTHUMB missing=%s board=%s"), Path.IsEmpty() ? TEXT("-") : *Path, *BoardId);
  if (Thumb) {
    if (ThumbTexture) Thumb->SetBrushFromTexture(ThumbTexture, false);
    Thumb->SetVisibility(ThumbTexture ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  }
  Apply(SizeSu, bSelected, false, true);
}

void UUmBoardChip::SetPress(FName Id, const TSharedPtr<FS09HudPressArbiter>& Arbiter, const FS09OnHudPressOutcome& OnOutcome) {
  if (Button) Button->SetPress(Id, Arbiter, OnOutcome);
}

bool UUmBoardChip::HasThumb() const { return ThumbTexture != nullptr; }
FString UUmBoardChip::GetNameText() const { return NameText ? NameText->GetText().ToString() : FString(); }

void UUmBoardChip::Apply(const FVector2D& InSizeSu, bool bInSelected, bool bInFocused, bool bInEnabled) {
  SizeSu = InSizeSu;
  bSelected = bInSelected;
  if (Button) {
    FUmButtonModel B;
    B.Variant = EUmButtonVariant::Normal;
    B.HeightSu = SizeSu.Y;
    B.MinWidthSu = SizeSu.X;
    B.bSelected = bSelected;
    B.bFocused = bInFocused;
    B.bEnabled = bInEnabled;
    if (!bInEnabled) B.Reason.Key = FName(TEXT("why.syncing"));
    Button->ApplyModel(B);
  }
  UmBcPlace(Button, FVector2D::ZeroVector, SizeSu);
  const FVector2D Src = ThumbTexture ? FVector2D(ThumbTexture->GetSizeX(), ThumbTexture->GetSizeY()) : FVector2D(1337.0, 866.0);
  const FBox2D Img = UmBoardChip::ImageRect(SizeSu, Src);
  UmBcPlace(Thumb, Img.Min, Img.GetSize());
  if (Thumb && ThumbTexture) Thumb->SetDesiredSizeOverride(Img.GetSize());
  // the name under the picture (centred in the name row; with no picture it sits in the middle of the tile)
  const float NameY = ThumbTexture ? SizeSu.Y - UmBoardChip::InsetSu - UmBoardChip::NameRowSu + 2.0f : 0.5f * SizeSu.Y - 12.0f;
  UmBcPlace(NameText, FVector2D(UmBoardChip::InsetSu, NameY), FVector2D(SizeSu.X - 2.0f * UmBoardChip::InsetSu, 24.0f));
  if (NameText) {
    const UUmHudTheme& Theme = UUmHudTheme::Get();
    NameText->SetColorAndOpacity(FSlateColor(Theme.Color(bSelected ? TEXT("card.glyph") : TEXT("text.primary"))));
  }
}

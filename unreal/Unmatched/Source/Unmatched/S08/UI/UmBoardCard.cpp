// VS-7 SC-15: one board card of the ROOM - see UmBoardCard.h.
#include "UmBoardCard.h"

#include "../S08AnimatedIconWidget.h"
#include "UmBoardChip.h"
#include "UmHeroCard.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Engine/Texture2D.h"

using namespace UmRoomUi;

namespace {
constexpr float UmBcInset = 8.0f;
constexpr float UmBcNameRow = 26.0f;
constexpr float UmBcCheck = 24.0f;
}  // namespace

bool UUmBoardCard::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  if (!WidgetTree->RootWidget) {
    Canvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Canvas")));
    WidgetTree->RootWidget = Canvas;
    Body = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("Body")));
    Canvas->AddChild(Body);
    Thumb = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("Thumb")));
    Canvas->AddChild(Thumb);
    NameText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("NameText")));
    Canvas->AddChild(NameText);
    Edge = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("Edge")));
    Canvas->AddChild(Edge);
    CheckChip = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("CheckChip")));
    Canvas->AddChild(CheckChip);
    CheckIcon = WidgetTree->ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("CheckIcon")));
    Canvas->AddChild(CheckIcon);
  }
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  for (UWidget* W : {static_cast<UWidget*>(Body.Get()), static_cast<UWidget*>(Thumb.Get()), static_cast<UWidget*>(NameText.Get()),
                     static_cast<UWidget*>(Edge.Get()), static_cast<UWidget*>(CheckChip.Get()), static_cast<UWidget*>(CheckIcon.Get())}) {
    if (W) W->SetVisibility(ESlateVisibility::HitTestInvisible);
  }
  if (Body) {
    if (const FSlateBrush* Chip = Theme.Skin(TEXT("chip"))) Body->SetBrush(*Chip);
  }
  if (Edge) Edge->SetBrush(FSlateRoundedBoxBrush(FLinearColor::Transparent, 4.0f, Theme.Color(TEXT("state.pending")), 3.0f));
  if (CheckChip) {
    if (const FSlateBrush* On = Theme.Skin(TEXT("check.on"))) CheckChip->SetBrush(*On);
  }
  Style(NameText, TEXT("type.body"), TEXT("text.primary"));
  if (NameText) NameText->SetJustification(ETextJustify::Center);
  Icon(CheckIcon, TEXT("ui-check"), UmBcCheck);
  // the whole card answers the pointer with its tooltip (the locked one explains itself, ВР-H11)
  SetVisibility(ESlateVisibility::Visible);
  return bFirst;
}

void UUmBoardCard::Setup(const FString& InBoardId, const FString& InName) {
  BoardId = InBoardId;
  if (NameText) NameText->SetText(FText::FromString(InName));
  ThumbTexture = nullptr;
  const FString Path = UmBoardChip::ThumbPath(BoardId);
  if (!Path.IsEmpty()) ThumbTexture = LoadObject<UTexture2D>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);
  if (!ThumbTexture) UE_LOG(LogTemp, Log, TEXT("BOARDTHUMB missing=%s board=%s show=room"), Path.IsEmpty() ? TEXT("-") : *Path, *BoardId);
  if (Thumb) {
    if (ThumbTexture) Thumb->SetBrushFromTexture(ThumbTexture, false);
    Vis(Thumb, ThumbTexture != nullptr);
  }
  Apply(SizeSu, bRoom);
}

FString UUmBoardCard::GetNameText() const { return NameText ? NameText->GetText().ToString() : FString(); }
bool UUmBoardCard::IsCheckShown() const { return CheckIcon && CheckIcon->GetVisibility() != ESlateVisibility::Collapsed; }

void UUmBoardCard::Apply(const FVector2D& InSizeSu, bool bInRoomBoard) {
  SizeSu = InSizeSu;
  bRoom = bInRoomBoard;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  Place(Body, FVector2D::ZeroVector, SizeSu);
  Place(Edge, FVector2D::ZeroVector, SizeSu);
  // the illustration above the name row, aspect kept, centred (the check chip sits in the free corner beside it)
  const FVector2D Area(SizeSu.X - 2.0f * UmBcInset, SizeSu.Y - 2.0f * UmBcInset - UmBcNameRow);
  const FVector2D Src = ThumbTexture ? FVector2D(ThumbTexture->GetSizeX(), ThumbTexture->GetSizeY()) : FVector2D(1337.0, 866.0);
  const double K = FMath::Min(Area.X / FMath::Max(1.0, Src.X), Area.Y / FMath::Max(1.0, Src.Y));
  const FVector2D ImgSize = Src * K;
  const FVector2D ImgPos = FVector2D(UmBcInset) + 0.5 * (Area - ImgSize);
  Place(Thumb, ImgPos, ImgSize);
  if (Thumb) {
    if (ThumbTexture) Thumb->SetDesiredSizeOverride(ImgSize);
    Thumb->SetRenderOpacity(bRoom ? 1.0f : Theme.Alpha(TEXT("state.disabled.opacity")));
  }
  const float NameY = SizeSu.Y - UmBcInset - UmBcNameRow + 2.0f;
  Place(NameText, FVector2D(UmBcInset, NameY), FVector2D(SizeSu.X - 2.0f * UmBcInset, 24.0f));
  if (NameText) NameText->SetColorAndOpacity(FSlateColor(Theme.Color(bRoom ? TEXT("text.primary") : TEXT("text.secondary"))));
  const FVector2D CheckPos(SizeSu.X - 6.0f - UmBcCheck, 6.0f);
  Place(CheckChip, CheckPos, FVector2D(UmBcCheck));
  Place(CheckIcon, CheckPos, FVector2D(UmBcCheck));
  Vis(Edge, bRoom);
  Vis(CheckChip, bRoom);
  Vis(CheckIcon, bRoom);
  SetToolTipText(bRoom ? FText::GetEmpty() : UmText::Get(EUmTable::Why, TEXT("why.room.board.locked")));
}

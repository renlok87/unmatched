// SEL (docs/game-design/select-screens/02-DESIGN.md §5): the VS look of the match loading - see UmScreenLoading.h «SEL».
#include "UmHeroShowcase.h"
#include "UmButton.h"
#include "UmHeroCard.h"
#include "UmHudTheme.h"
#include "UmScreenLoading.h"
#include "UmSpinner.h"
#include "../S08AnimatedIconWidget.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Engine/TextureRenderTarget2D.h"

using namespace UmRoomUi;

namespace {
FLinearColor VsTeam(bool bHost, float Alpha = 1.0f) {
  FLinearColor C = FLinearColor(S08TeamPalette::ChipColor(bHost ? ES08TeamSlot::P1 : ES08TeamSlot::P2));
  C.A = Alpha;
  return C;
}
}  // namespace

void UUmScreenLoading::VsBuild() {
  bVs = UmShowcase::Enabled();
  if (!bVs || !WidgetTree || !Content || VsMedal) return;
  UWidgetTree& Tree = *WidgetTree;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  auto Border = [&Tree, this](const FString& Name, int32 At) {
    UBorder* B = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(*Name));
    B->SetVisibility(ESlateVisibility::HitTestInvisible);
    B->SetPadding(FMargin(0.0f));
    B->SetBrush(FSlateNoResource());
    B->SetHorizontalAlignment(HAlign_Center);
    B->SetVerticalAlignment(VAlign_Center);
    Content->InsertChildAt(At, B);
    return B;
  };
  // under the texts (index 0..): niches, views, plates, the medallion, the bottom strip
  int32 At = 0;
  VsStrip = Border(TEXT("VsStrip"), At++);
  {
    FLinearColor Ink = Theme.Color(TEXT("card.navy"));
    Ink.A = 0.92f;
    VsStrip->SetBrush(FSlateRoundedBoxBrush(Ink, 8.0f, Theme.Color(TEXT("panel.edge")), 1.5f));
  }
  for (int32 S = 0; S < 2; ++S) {
    VsNiche[S] = Border(FString::Printf(TEXT("VsNiche%d"), S), At++);
    VsView[S] = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(*FString::Printf(TEXT("VsView%d"), S)));
    VsView[S]->SetVisibility(ESlateVisibility::HitTestInvisible);
    Content->InsertChildAt(At++, VsView[S]);
    VsPlate[S] = Border(FString::Printf(TEXT("VsPlate%d"), S), At++);
  }
  for (int32 S = 0; S < 2; ++S) {
    VsSideDisc[S] = Border(FString::Printf(TEXT("VsSideDisc%d"), S), Content->GetChildrenCount());
    VsSideText[S] = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(*FString::Printf(TEXT("VsSideText%d"), S)));
    VsSideText[S]->SetVisibility(ESlateVisibility::HitTestInvisible);
    Style(VsSideText[S], TEXT("type.caption"), TEXT("text.secondary"));
    Content->AddChild(VsSideText[S]);
  }
  VsMedal = Border(TEXT("VsMedal"), At++);
  VsMark = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("VsMark")));
  Style(VsMark, TEXT("type.display"), TEXT("card.cream"));
  VsMark->SetJustification(ETextJustify::Center);
  VsMark->SetText(FText::FromString(TEXT("VS")));
  VsMedal->SetContent(VsMark);
  VsMedal->SetBrush(FSlateRoundedBoxBrush(FLinearColor(FColor::FromHex(TEXT("#8C6B3F"))), 100.0f,
                                          FLinearColor(FColor::FromHex(TEXT("#C9A45C"))), 4.0f));
  if (const FSlateBrush* Marble = Theme.SkinFor(TEXT("hud.table.card"), PxPerSu)) {
    for (int32 S = 0; S < 2; ++S) VsPlate[S]->SetBrush(*Marble);
  }
  Showcase = AUmHeroShowcase::Get(GetWorld());
  for (int32 S = 0; S < 2; ++S) {
    if (UTextureRenderTarget2D* RT = Showcase.IsValid() ? Showcase->GetTarget(S) : nullptr) {
      FSlateBrush B;
      B.SetResourceObject(RT);
      B.ImageSize = FVector2D(UmShowcase::TargetW, UmShowcase::TargetH);
      VsView[S]->SetBrush(B);
    }
  }
  // the SC-19 panel parts this look does not use
  for (UWidget* W : {static_cast<UWidget*>(LoadingPanel), static_cast<UWidget*>(LeftCard), static_cast<UWidget*>(RightCard),
                     static_cast<UWidget*>(LeftPortrait), static_cast<UWidget*>(RightPortrait),
                     static_cast<UWidget*>(VersusText)}) {
    if (W) W->SetVisibility(ESlateVisibility::Collapsed);
  }
  Style(LeftName, TEXT("type.display"), TEXT("text.primary"));
  Style(RightName, TEXT("type.display"), TEXT("text.primary"));
  Style(LeftNick, TEXT("type.body"), TEXT("text.secondary"));
  Style(RightNick, TEXT("type.body"), TEXT("text.secondary"));
  Style(BoardText, TEXT("type.title"), TEXT("text.primary"));
  Style(StageText, TEXT("type.body"), TEXT("text.secondary"));
}

void UUmScreenLoading::VsLayout() {
  if (!bVs || !VsMedal) return;
  const FVector2D O = FrameRectSu().Min;
  auto P = [&O](UWidget* W, float X, float Y, float Wd, float Ht) { Place(W, FVector2D(X, Y) - O, FVector2D(Wd, Ht)); };
  const float W = CanvasSu.X, H = CanvasSu.Y;
  const float Wr = FMath::Min(W, H * 16.0f / 9.0f);
  const float X0 = 0.5f * (W - Wr);
  const float K = FMath::Clamp(H / 1080.0f, 0.45f, 1.0f);
  const float VH = 760.0f * K, VW = VH * 2.0f / 3.0f;
  const float Top = 56.0f * K;
  const float Edge = 72.0f * K;
  const float NX[2] = {X0 + Edge, X0 + Wr - Edge - VW};
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  for (int32 S = 0; S < 2; ++S) {
    const bool bHost = Sides[S].bHost;
    VsNiche[S]->SetBrush(FSlateRoundedBoxBrush(FLinearColor(0.012f, 0.014f, 0.02f, 1.0f), 10.0f, VsTeam(bHost), 3.0f));
    P(VsNiche[S], NX[S] - 3.0f, Top - 3.0f, VW + 6.0f, VH + 6.0f);
    P(VsView[S], NX[S], Top, VW, VH);
    const float PY = Top + VH - 40.0f * K;
    P(VsPlate[S], NX[S] - 24.0f * K, PY, VW + 48.0f * K, 112.0f * K);
    UTextBlock* Name = S == 0 ? LeftName.Get() : RightName.Get();
    UTextBlock* Nick = S == 0 ? LeftNick.Get() : RightNick.Get();
    P(Name, NX[S] - 16.0f, PY + 12.0f * K, VW + 32.0f, 60.0f);
    P(Nick, NX[S] - 16.0f, PY + 70.0f * K, VW + 32.0f, 26.0f);
    // P2 small text: the lighter tint (review fix 7)
    if (Nick) Nick->SetColorAndOpacity(FSlateColor(bHost ? VsTeam(true) : FLinearColor(FColor::FromHex(TEXT("#A4BECE")))));
    // the sidekick: round token + «+ Мерлин · HP 7» under the plate (review fix 2)
    const FUmLoadingSide& Sd = Sides[S];
    const bool bSide = !Sd.SidekickName.IsEmpty() && !Sd.HeroName.IsEmpty();
    if (VsSideText[S]) {
      VsSideText[S]->SetText(bSide ? FText::FromString(TEXT("+ ") + SidekickLine(Sd.SidekickName, Sd.SidekickCount, Sd.SidekickHp, FString(), false))
                                   : FText::GetEmpty());
      VsSideText[S]->SetJustification(ETextJustify::Left);
    }
    if (VsSideDisc[S] && WidgetTree && VsDiscKey[S] != (bSide ? Sd.SidekickKey : FName())) {
      VsDiscKey[S] = bSide ? Sd.SidekickKey : FName();
      if (bSide) {
        FString Line;
        VsSideDisc[S]->SetContent(MakeDisc(*WidgetTree, this, Sd.SidekickKey, Sd.SidekickName, 32.0f, PxPerSu, 0.0f, VsKeepAlive, &Line, TEXT("loading")));
      } else {
        VsSideDisc[S]->ClearChildren();
      }
    }
    const float SideW = bSide ? 40.0f + MeasureW(VsSideText[S]->GetText(), TEXT("type.caption")) + 8.0f : 0.0f;
    const float SideX = NX[S] + 0.5f * (VW - SideW);
    const float SideY = PY + 112.0f * K + 10.0f;
    P(VsSideDisc[S], SideX, SideY, 32.0f, 32.0f);
    P(VsSideText[S], SideX + 40.0f, SideY + 6.0f, SideW, 22.0f);
    Vis(VsSideDisc[S], bSide);
    Vis(VsSideText[S], bSide);
    VsView[S]->SetVisibility(Sides[S].HeroName.IsEmpty() ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
  }
  const float Medal = 200.0f * K;
  P(VsMedal, 0.5f * W - 0.5f * Medal, Top + 0.42f * VH - 0.5f * Medal, Medal, Medal);
  // the bottom strip: the board name, the stage row, the error buttons
  const float StripW = FMath::Min(Wr - 2.0f * Edge, 1100.0f * K);
  const float StripY = H - 124.0f * K;
  P(VsStrip, 0.5f * W - 0.5f * StripW, StripY, StripW, 100.0f * K);
  P(BoardText, 0.5f * W - 0.5f * StripW, StripY + 12.0f * K, StripW, 40.0f);
  float Longest = 0.0f;
  for (EUmLoadingStage S : {EUmLoadingStage::Connect, EUmLoadingStage::State, EUmLoadingStage::Board, EUmLoadingStage::Error}) {
    Longest = FMath::Max(Longest, MeasureW(UmRoomUi::S(UmLoading::StageKey(S)), TEXT("type.body")));
  }
  const float GroupW = 28.0f + 10.0f + Longest + 4.0f;
  const float Gx = 0.5f * W - 0.5f * GroupW;
  const float RowY = StripY + 56.0f * K;
  P(Spinner.Get(), Gx, RowY, 28.0f, 28.0f);
  P(ErrorIcon.Get(), Gx, RowY, 28.0f, 28.0f);
  if (Spinner) Spinner->SetSizeSu(28.0f);
  P(StageText, Gx + 38.0f, RowY + 2.0f, Longest + 4.0f, 26.0f);
  if (StageText) StageText->SetJustification(ETextJustify::Left);
  if (Stage == EUmLoadingStage::Error) {
    const float BtnW = 200.0f;
    P(LobbyButton, 0.5f * W - BtnW - 8.0f, StripY - 64.0f * K, BtnW, 48.0f);
    P(RetryButton, 0.5f * W + 8.0f, StripY - 64.0f * K, BtnW, 48.0f);
  }
  (void)Theme;
}

void UUmScreenLoading::VsTick() {
  if (!bVs) return;
  if (!Showcase.IsValid()) Showcase = AUmHeroShowcase::Get(GetWorld());
  AUmHeroShowcase* SC = Showcase.Get();
  if (!SC || !IsShown() || GetVisibility() == ESlateVisibility::Collapsed) {
    bVsPosed = false;
    return;
  }
  SC->RequestActive();
  for (int32 S = 0; S < 2; ++S) {
    const FString Fighter = Sides[S].HeroName.IsEmpty() ? FString() : UmShowcase::FighterForSlug(Sides[S].HeroKey, Sides[S].HeroName);
    SC->SetHero(S, Fighter, Sides[S].bHost ? ES08TeamSlot::P1 : ES08TeamSlot::P2);
  }
  if (!bVsPosed && SC->HasFigure(0)) {
    // MK / Injustice: both fighters strike their pose as the VS comes up
    bVsPosed = true;
    SC->PlayLockIn(0);
    SC->PlayLockIn(1);
  }
}

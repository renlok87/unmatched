// VS-7 SC-17: one seat of the ROOM - see UmRoomSlot.h.
#include "UmRoomSlot.h"

#include "../S08AnimatedIconWidget.h"
#include "UmHeroCard.h"
#include "UmHudTheme.h"
#include "UmLobbyGameRow.h"
#include "UmScreenLobby.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/TextBlock.h"

using namespace UmRoomUi;

bool UUmRoomSlot::Initialize() {
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
      Canvas->AddChild(B);
      return B;
    };
    auto Text = [this](const TCHAR* Name) {
      UTextBlock* T = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
      T->SetVisibility(ESlateVisibility::HitTestInvisible);
      Canvas->AddChild(T);
      return T;
    };
    Panel = Border(TEXT("Panel"));
    Avatar = Border(TEXT("Avatar"));
    NameText = Text(TEXT("NameText"));
    HostChip = Border(TEXT("HostChip"));
    HostText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("HostText")));
    HostChip->SetContent(HostText);
    ReadyBox = Border(TEXT("ReadyBox"));
    ReadyIcon = WidgetTree->ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("ReadyIcon")));
    Canvas->AddChild(ReadyIcon);
    ReadyText = Text(TEXT("ReadyText"));
    HeroLine = Text(TEXT("HeroLine"));
    SidekickLine = Text(TEXT("SidekickLine"));
  }
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (Avatar) Avatar->SetBrush(FSlateNoResource());  // a UBorder's default brush is a white box
  if (Panel) {
    if (const FSlateBrush* Skin = Theme.Skin(TEXT("modal"))) Panel->SetBrush(*Skin);
  }
  if (HostChip) {
    if (const FSlateBrush* Chip = Theme.Skin(TEXT("chip"))) HostChip->SetBrush(*Chip);
    HostChip->SetPadding(FMargin(8.0f, 2.0f));
  }
  Style(NameText, TEXT("type.heading"), TEXT("text.primary"));
  Style(HostText, TEXT("type.caption"), TEXT("text.primary"));
  Style(HeroLine, TEXT("type.body"), TEXT("text.primary"));
  Style(SidekickLine, TEXT("type.body"), TEXT("text.secondary"));
  // VS-7 Frames: a line longer than the slot (pseudo-locale +30 %, class S) ends in «…» inside the slot (04 §6)
  for (UTextBlock* T : {HeroLine.Get(), SidekickLine.Get(), ReadyText.Get()}) {
    if (T) {
      T->SetTextOverflowPolicy(ETextOverflowPolicy::Ellipsis);
      T->SetClipping(EWidgetClipping::ClipToBounds);  // the ellipsis needs the clip rect (as UmHudLog)
    }
  }
  if (ReadyIcon) ReadyIcon->SetVisibility(ESlateVisibility::HitTestInvisible);
  Icon(ReadyIcon, TEXT("ui-check"), 24.0f);
  return bFirst;
}

FString UUmRoomSlot::GetNameText() const { return NameText ? NameText->GetText().ToString() : FString(); }
FString UUmRoomSlot::GetReadyText() const {
  return ReadyText && ReadyText->GetVisibility() != ESlateVisibility::Collapsed ? ReadyText->GetText().ToString() : FString();
}
FString UUmRoomSlot::GetHeroLine() const { return HeroLine ? HeroLine->GetText().ToString() : FString(); }
FString UUmRoomSlot::GetSidekickLine() const {
  return SidekickLine && SidekickLine->GetVisibility() != ESlateVisibility::Collapsed ? SidekickLine->GetText().ToString() : FString();
}
bool UUmRoomSlot::IsReadyGlyphShown() const { return ReadyIcon && ReadyIcon->GetVisibility() != ESlateVisibility::Collapsed; }

void UUmRoomSlot::Apply(const FUmRoomSlotModel& InModel, const FVector2D& InSizeSu, bool bInClassS, float PxPerSu) {
  const bool bChanged = !bHasModel || InModel != Model || InSizeSu != SizeSu || bInClassS != bClassS;
  Model = InModel;
  bHasModel = true;
  SizeSu = InSizeSu;
  bClassS = bInClassS;
  const float AvSu = bClassS ? 64.0f : 80.0f;
  if (WidgetTree && Avatar && (!bAvatarBuilt || AvatarKey != Model.HeroKey || AvatarPx != PxPerSu || AvatarClassS != bClassS)) {
    bAvatarBuilt = true;
    AvatarKey = Model.HeroKey;
    AvatarPx = PxPerSu;
    AvatarClassS = bClassS;
    KeepAlive.Reset();
    Avatar->SetContent(MakeDisc(*WidgetTree, this, Model.HeroKey, Model.HeroName, AvSu, PxPerSu, 0.0f, KeepAlive, &PortraitLine, TEXT("slot")));
  }
  if (!bChanged) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  // ---- texts
  const bool bAi = Model.Seat == EUmRoomSeat::Ai;
  const bool bWaiting = Model.Seat == EUmRoomSeat::Waiting;
  if (NameText) {
    NameText->SetText(bWaiting ? S(TEXT("screens.room.slot.waiting")) : FText::FromString(bAi ? FString(UmLobby::AiBotName) : Model.Username));
    NameText->SetColorAndOpacity(FSlateColor(Theme.Color(bWaiting ? TEXT("text.secondary") : TEXT("text.primary"))));
  }
  if (HostText) HostText->SetText(S(bAi ? TEXT("screens.room.slot.ai") : TEXT("screens.room.slot.host")));
  const bool bChip = (Model.bHost && Model.Seat == EUmRoomSeat::Player) || bAi;
  Vis(HostChip, bChip);
  if (ReadyText) {
    if (Model.bReady) {
      ReadyText->SetText(S(TEXT("screens.room.ready")).ToUpper());
      Style(ReadyText, TEXT("type.button"), TEXT("text.primary"));
    } else {
      ReadyText->SetText(S(TEXT("screens.room.not.ready")));
      Style(ReadyText, TEXT("type.body"), TEXT("text.secondary"));
    }
  }
  Vis(ReadyText, !bWaiting);
  if (ReadyBox) {
    if (const FSlateBrush* Box = Theme.Skin(Model.bReady ? TEXT("check.on") : TEXT("check.off"))) ReadyBox->SetBrush(*Box);
  }
  Vis(ReadyBox, !bWaiting);
  Vis(ReadyIcon, !bWaiting && Model.bReady);
  FString Hero;
  FString Kick;
  if (bAi) {
    Hero = S(TEXT("screens.room.slot.ai.hero")).ToString();
  } else if (bWaiting) {
    Hero.Reset();
  } else if (Model.HeroName.IsEmpty()) {
    Hero = S(TEXT("screens.room.slot.no.hero")).ToString();
  } else {
    Hero = Model.HeroName;
    if (Model.bDetails) {
      Hero += TEXT(" · ") + Stats(Model.Hp, Model.Move).ToString();
      if (!Model.SidekickName.IsEmpty()) Kick = TEXT("+ ") + UmRoomUi::SidekickLine(Model.SidekickName, Model.SidekickCount, Model.SidekickHp, FString(), false);
    }
  }
  if (HeroLine) {
    HeroLine->SetText(FText::FromString(Hero));
    HeroLine->SetColorAndOpacity(FSlateColor(Theme.Color(Model.HeroName.IsEmpty() || bAi ? TEXT("text.secondary") : TEXT("text.primary"))));
  }
  if (SidekickLine) SidekickLine->SetText(FText::FromString(Kick));
  Vis(SidekickLine, !Kick.IsEmpty());
  // ---- layout (L 560/500 x 200; S 300 x 136)
  const float W = SizeSu.X;
  Place(Panel, FVector2D::ZeroVector, SizeSu);
  const float Pad = bClassS ? 12.0f : 16.0f;
  Place(Avatar, FVector2D(Pad, Pad), FVector2D(AvSu, AvSu));
  const float Tx = Pad + AvSu + (bClassS ? 12.0f : 16.0f);
  const float Tw = W - Tx - Pad;
  const FText ChipLabel = HostText ? HostText->GetText() : FText();
  const float ChipW = bChip ? MeasureW(ChipLabel, TEXT("type.caption")) + 16.0f : 0.0f;
  const float RowStep = bClassS ? 30.0f : 36.0f;
  float Y = bClassS ? 10.0f : 18.0f;
  if (bAi) {
    // «ИИ-соперник» chip first, then «AI Bot» (ВР-VS4-SC14-05)
    Place(HostChip, FVector2D(Tx, Y + 4.0f), FVector2D(ChipW, 24.0f));
    Place(NameText, FVector2D(Tx + ChipW + 8.0f, Y), FVector2D(FMath::Max(40.0f, Tw - ChipW - 8.0f), 30.0f));
  } else {
    const float NameW = MeasureW(NameText ? NameText->GetText() : FText(), TEXT("type.heading")) + 4.0f;
    Place(NameText, FVector2D(Tx, Y), FVector2D(FMath::Max(40.0f, FMath::Min(NameW, Tw)), 30.0f));
    if (Tx + NameW + 8.0f + ChipW <= Tx + Tw) {
      Place(HostChip, FVector2D(Tx + NameW + 8.0f, Y + 4.0f), FVector2D(ChipW, 24.0f));
    } else {
      // the name is never cut (ВР-VS4-SC14-11): the chip goes to the end of the ready row
      const float ReadyW = MeasureW(ReadyText ? ReadyText->GetText() : FText(), Model.bReady ? TEXT("type.button") : TEXT("type.body")) + 4.0f;
      Place(HostChip, FVector2D(Tx + 32.0f + ReadyW + 12.0f, Y + RowStep + 1.0f), FVector2D(ChipW, 24.0f));
    }
  }
  Y += RowStep;
  Place(ReadyBox, FVector2D(Tx, Y), FVector2D(24.0f, 24.0f));
  Place(ReadyIcon, FVector2D(Tx, Y), FVector2D(24.0f, 24.0f));
  Place(ReadyText, FVector2D(Tx + 32.0f, Y), FVector2D(Tw - 32.0f, 26.0f));
  Y += RowStep;
  Place(HeroLine, FVector2D(Tx, Y), FVector2D(Tw, 24.0f));
  Y += bClassS ? 26.0f : 30.0f;
  Place(SidekickLine, FVector2D(Tx, Y), FVector2D(Tw, 24.0f));
}

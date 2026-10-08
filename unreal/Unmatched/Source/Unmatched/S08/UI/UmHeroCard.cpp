// VS-7 SC-14: one hero card of the ROOM grid and the ROOM helpers - see UmHeroCard.h.
#include "UmHeroCard.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08IconMotion.h"
#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHudScale.h"
#include "UmHudTheme.h"
#include "UmPortrait.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "Materials/MaterialInstanceDynamic.h"

// ------------------------------------------------------------------------------------------------ helpers

namespace UmRoomUi {
void Place(UWidget* W, const FVector2D& Pos, const FVector2D& Size) {
  UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr;
  if (!S) return;
  S->SetAnchors(FAnchors(0.0f, 0.0f));
  S->SetAlignment(FVector2D::ZeroVector);
  S->SetAutoSize(false);
  S->SetPosition(Pos);
  S->SetSize(Size);
}

void Style(UTextBlock* T, const TCHAR* Type, const TCHAR* Color) {
  if (!T) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  T->SetFont(Theme.Font(FName(Type)));
  T->SetColorAndOpacity(FSlateColor(Theme.Color(FName(Color))));
  T->SetShadowOffset(FVector2D::ZeroVector);
}

float MeasureW(const FText& Text, const TCHAR* Type) {
  const FSlateFontInfo Font = UUmHudTheme::Get().Font(FName(Type));
  if (FSlateApplication::IsInitialized()) {
    return static_cast<float>(FSlateApplication::Get().GetRenderer()->GetFontMeasureService()->Measure(Text, Font, 1.0f).X);
  }
  return 0.55f * Font.Size * 96.0f / 72.0f * Text.ToString().Len();
}

FString ClampLines(const FString& Text, const TCHAR* Type, float WidthSu, int32 Lines) {
  TArray<FString> Words;
  Text.ParseIntoArrayWS(Words);
  TArray<FString> Out;
  FString Line;
  int32 I = 0;
  for (; I < Words.Num(); ++I) {
    const FString Try = Line.IsEmpty() ? Words[I] : Line + TEXT(" ") + Words[I];
    if (Line.IsEmpty() || MeasureW(FText::FromString(Try), Type) <= WidthSu) {
      Line = Try;
      continue;
    }
    Out.Add(Line);
    Line = Words[I];
    if (Out.Num() == Lines) break;
  }
  if (Out.Num() < Lines && !Line.IsEmpty()) {
    Out.Add(Line);
    Line.Reset();
    I = Words.Num();
  }
  if (I < Words.Num() && Out.Num() > 0) {
    // the text did not fit: the last line ends with «…» (shortened word by word until it fits)
    FString& Last = Out.Last();
    while (!Last.IsEmpty() && MeasureW(FText::FromString(Last + TEXT("…")), Type) > WidthSu) {
      int32 Space = INDEX_NONE;
      if (!Last.FindLastChar(TEXT(' '), Space)) break;
      Last.LeftInline(Space);
    }
    Last += TEXT("…");
  }
  return FString::Join(Out, TEXT("\n"));
}

void Vis(UWidget* W, bool bOn, bool bHit) {
  if (W) W->SetVisibility(bOn ? (bHit ? ESlateVisibility::Visible : ESlateVisibility::HitTestInvisible) : ESlateVisibility::Collapsed);
}

bool Icon(US08AnimatedIconWidget* W, const TCHAR* Id, float Su) {
  if (!W) return false;
  const FName IconId(Id);
  if (W->GetIconId() != IconId && W->SetIcon(IconId, Su, S08IconMotion::ExportSizePx(Su, UmHudScale::Current().PxPerSu()))) {
    W->SetDisplaySizeSu(Su);
    W->ShowAtRest();
  }
  return true;
}

FText S(const TCHAR* Key) { return UmText::Get(EUmTable::Screens, Key); }

FText AttackWord(const FString& AttackType) {
  if (AttackType.Equals(TEXT("melee"), ESearchCase::IgnoreCase)) return S(TEXT("screens.room.hero.melee"));
  if (AttackType.Equals(TEXT("range"), ESearchCase::IgnoreCase) || AttackType.Equals(TEXT("ranged"), ESearchCase::IgnoreCase)) {
    return S(TEXT("screens.room.hero.ranged"));
  }
  return FText::FromString(AttackType);
}

FText Stats(int32 Hp, int32 Move) {
  FFormatNamedArguments Args;
  Args.Add(TEXT("hp"), FText::AsNumber(Hp));
  Args.Add(TEXT("move"), FText::AsNumber(Move));
  return FText::Format(S(TEXT("screens.room.hero.stats")), Args);
}

FString SidekickLine(const FString& Name, int32 Count, int32 Hp, const FString& AttackType, bool bAttack) {
  FString Out = Name;
  if (Count > 1) Out += FString::Printf(TEXT(" ×%d"), Count);
  Out += FString::Printf(TEXT(" · HP %d"), Hp);
  // the attack phrase wraps only whole (ВР-VS4-SC14-14): a no-break space inside it
  if (bAttack && !AttackType.IsEmpty()) Out += TEXT(" · ") + AttackWord(AttackType).ToString().Replace(TEXT(" "), TEXT("\u00A0"));
  return Out;
}

UWidget* MakeDisc(UWidgetTree& Tree, UObject* Outer, FName Key, const FString& Name, float Su, float PxPerSu, float Desaturation,
                  TArray<TObjectPtr<UObject>>& KeepAlive, FString* OutLine, const TCHAR* Show) {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (Key.IsNone()) {
    // an empty seat: portrait underlay + edge, no glyph (ВР-VS4-SC14-05)
    UImage* Disc = Tree.ConstructWidget<UImage>(UImage::StaticClass());
    Disc->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("card.navy")), 0.5f * Su, Theme.Color(TEXT("panel.edge")), 1.0f, FVector2f(Su, Su)));
    if (OutLine) OutLine->Reset();
    return Disc;
  }
  FUmPortraitDiscSpec Spec;
  Spec.Key = Key;
  Spec.Name = Name;
  Spec.ShowSu = Su;
  Spec.PxPerSu = PxPerSu;
  FUmPortraitShown Shown;
  const int32 Before = KeepAlive.Num();
  UWidget* W = UmPortrait::MakeDisc(Tree, Outer, Spec, Shown, KeepAlive);
  if (Desaturation > 0.0f && KeepAlive.Num() > Before) {
    if (UMaterialInstanceDynamic* Mid = Cast<UMaterialInstanceDynamic>(KeepAlive.Last())) {
      Mid->SetScalarParameterValue(UmPortrait::ParamDesaturation, Desaturation);
    }
  }
  if (OutLine) *OutLine = Shown.Line(Show, TEXT("own"));
  return W;
}
}  // namespace UmRoomUi

using namespace UmRoomUi;

namespace {
constexpr float UmHcTakenDesaturation = 0.6f;  // saturation x0.4 (SC-14 taken)
}

// ------------------------------------------------------------------------------------------------ the card

bool UUmHeroCard::Initialize() {
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
    Body = Border(TEXT("Body"));
    PortraitBox = Border(TEXT("PortraitBox"));
    NameText = Text(TEXT("NameText"));
    StatsText = Text(TEXT("StatsText"));
    AttackText = Text(TEXT("AttackText"));
    SidekickBox = Border(TEXT("SidekickBox"));
    SidekickText = Text(TEXT("SidekickText"));
    LangChip = Border(TEXT("LangChip"));
    AbilityText = Text(TEXT("AbilityText"));
    TakenText = Text(TEXT("TakenText"));
    UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
    PickButton = WidgetTree->ConstructWidget<UUmButton>(ButtonClass, FName(TEXT("PickButton")));
    Canvas->AddChild(PickButton);
    Edge = Border(TEXT("Edge"));  // last: the picked edge over everything
  }
  Style(NameText, TEXT("type.heading"), TEXT("text.primary"));
  Style(StatsText, TEXT("type.body"), TEXT("text.primary"));
  Style(AttackText, TEXT("type.body"), TEXT("text.secondary"));
  Style(SidekickText, TEXT("type.body"), TEXT("text.secondary"));
  Style(AbilityText, TEXT("type.caption"), TEXT("text.secondary"));
  Style(TakenText, TEXT("type.body"), TEXT("text.secondary"));
  if (SidekickText) SidekickText->SetAutoWrapText(true);
  if (TakenText) TakenText->SetJustification(ETextJustify::Center);
  for (UBorder* Box : {PortraitBox.Get(), SidekickBox.Get()}) {
    if (Box) Box->SetBrush(FSlateNoResource());  // a UBorder's default brush is a white box
  }
  if (LangChip) {
    const UUmHudTheme& Theme = UUmHudTheme::Get();
    if (const FSlateBrush* Chip = Theme.Skin(TEXT("chip"))) LangChip->SetBrush(*Chip);
    UTextBlock* En = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("LangText")));
    Style(En, TEXT("type.caption"), TEXT("text.primary"));
    En->SetText(S(TEXT("screens.login.lang.en")));
    LangChip->SetContent(En);
  }
  SetVisibility(ESlateVisibility::Visible);
  return bFirst;
}

void UUmHeroCard::SetPress(FName Id, const TSharedPtr<FS09HudPressArbiter>& Arbiter, const FS09OnHudPressOutcome& OnOutcome) {
  if (PickButton) PickButton->SetPress(Id, Arbiter, OnOutcome);
}

FString UUmHeroCard::GetStatsText() const { return StatsText ? StatsText->GetText().ToString() : FString(); }
FString UUmHeroCard::GetAttackText() const { return AttackText ? AttackText->GetText().ToString() : FString(); }
FString UUmHeroCard::GetSidekickText() const { return SidekickText ? SidekickText->GetText().ToString() : FString(); }
FString UUmHeroCard::GetAbilityText() const { return AbilityText ? AbilityText->GetText().ToString() : FString(); }
FString UUmHeroCard::GetTakenText() const {
  return TakenText && TakenText->GetVisibility() != ESlateVisibility::Collapsed ? TakenText->GetText().ToString() : FString();
}
bool UUmHeroCard::IsPickShown() const { return PickButton && PickButton->GetVisibility() != ESlateVisibility::Collapsed; }

void UUmHeroCard::Apply(const FUmHeroCardModel& InModel, const FVector2D& InSizeSu, bool bInClassS, float PxPerSu) {
  const bool bChanged = !bHasModel || InModel != Model || InSizeSu != SizeSu || bInClassS != bClassS;
  Model = InModel;
  bHasModel = true;
  SizeSu = InSizeSu;
  bClassS = bInClassS;
  RebuildDiscs(PxPerSu);
  if (!bChanged) return;
  if (NameText) NameText->SetText(FText::FromString(Model.Name));
  if (StatsText) StatsText->SetText(Model.bDetails ? Stats(Model.Hp, Model.Move) : FText::GetEmpty());
  if (AttackText) AttackText->SetText(Model.bDetails ? AttackWord(Model.AttackType) : FText::GetEmpty());
  if (SidekickText) {
    SidekickText->SetText(Model.bDetails && !Model.SidekickName.IsEmpty()
                              ? FText::FromString(SidekickLine(Model.SidekickName, Model.SidekickCount, Model.SidekickHp, Model.SidekickAttack, true))
                              : FText::GetEmpty());
  }
  if (TakenText) TakenText->SetText(UmText::Get(EUmTable::Why, TEXT("why.hero.taken")));
  Layout();
  Restyle();
}

void UUmHeroCard::RebuildDiscs(float PxPerSu) {
  if (!WidgetTree || !PortraitBox || !SidekickBox) return;
  if (DiscKey == Model.Key && DiscSidekickKey == Model.SidekickKey && DiscState == Model.State && DiscPx == PxPerSu && DiscClassS == bClassS) return;
  DiscKey = Model.Key;
  DiscSidekickKey = Model.SidekickKey;
  DiscState = Model.State;
  DiscPx = PxPerSu;
  DiscClassS = bClassS;
  KeepAlive.Reset();
  PortraitLines.Reset();
  const float Desat = Model.State == EUmHeroCardState::Taken ? UmHcTakenDesaturation : 0.0f;
  FString Line;
  PortraitBox->SetContent(MakeDisc(*WidgetTree, this, Model.Key, Model.Name, bClassS ? 80.0f : 120.0f, PxPerSu, Desat, KeepAlive, &Line, TEXT("room")));
  if (!Line.IsEmpty()) PortraitLines.Add(Line);
  if (!Model.SidekickKey.IsNone()) {
    SidekickBox->SetContent(MakeDisc(*WidgetTree, this, Model.SidekickKey, Model.SidekickName, 40.0f, PxPerSu, Desat, KeepAlive, &Line, TEXT("room")));
    if (!Line.IsEmpty()) PortraitLines.Add(Line);
  } else {
    SidekickBox->ClearChildren();
  }
}

void UUmHeroCard::Layout() {
  const float W = SizeSu.X, H = SizeSu.Y;
  Place(Body, FVector2D::ZeroVector, SizeSu);
  Place(Edge, FVector2D::ZeroVector, SizeSu);
  const float BtnH = 40.0f;
  if (!bClassS) {
    // ВР-VS4-SC14-06: portrait 120 centred, name, stats, attack, the sidekick row, the ability, the button at the bottom
    const float Iw = W - 32.0f;
    Place(PortraitBox, FVector2D(0.5f * (W - 120.0f), 16.0f), FVector2D(120.0f, 120.0f));
    Place(NameText, FVector2D(16.0f, 144.0f), FVector2D(Iw, 30.0f));
    Place(StatsText, FVector2D(16.0f, 176.0f), FVector2D(Iw, 22.0f));
    Place(AttackText, FVector2D(16.0f, 200.0f), FVector2D(Iw, 22.0f));
    Place(SidekickBox, FVector2D(16.0f, 228.0f), FVector2D(40.0f, 40.0f));
    Place(SidekickText, FVector2D(64.0f, 228.0f), FVector2D(Iw - 48.0f, 44.0f));
    if (SidekickText) SidekickText->SetWrapTextAt(Iw - 48.0f);
    const float ChipW = MeasureW(S(TEXT("screens.login.lang.en")), TEXT("type.caption")) + 12.0f;
    Place(LangChip, FVector2D(16.0f, 280.0f), FVector2D(ChipW, 20.0f));
    Place(AbilityText, FVector2D(16.0f + ChipW + 6.0f, 280.0f), FVector2D(Iw - ChipW - 6.0f, 60.0f));
    if (AbilityText) AbilityText->SetText(FText::FromString(Model.bDetails ? ClampLines(Model.Ability, TEXT("type.caption"), Iw - ChipW - 6.0f, 3) : FString()));
    Place(PickButton, FVector2D(16.0f, H - 16.0f - BtnH), FVector2D(Iw, BtnH));
    Place(TakenText, FVector2D(16.0f, H - 16.0f - BtnH + 9.0f), FVector2D(Iw, 22.0f));
  } else {
    // ВР-VS4-SC14-11: portrait 80 left, the text right, the ability 2 lines
    const float Tx = 112.0f, Tw = W - Tx - 16.0f;
    Place(PortraitBox, FVector2D(16.0f, 16.0f), FVector2D(80.0f, 80.0f));
    Place(NameText, FVector2D(Tx, 12.0f), FVector2D(Tw, 30.0f));
    Place(StatsText, FVector2D(Tx, 44.0f), FVector2D(Tw, 22.0f));
    Place(AttackText, FVector2D(Tx, 66.0f), FVector2D(Tw, 22.0f));
    Place(SidekickBox, FVector2D(Tx, 92.0f), FVector2D(40.0f, 40.0f));
    Place(SidekickText, FVector2D(Tx + 48.0f, 92.0f), FVector2D(Tw - 48.0f, 44.0f));
    if (SidekickText) SidekickText->SetWrapTextAt(Tw - 48.0f);
    const float ChipW = MeasureW(S(TEXT("screens.login.lang.en")), TEXT("type.caption")) + 12.0f;
    Place(LangChip, FVector2D(16.0f, 140.0f), FVector2D(ChipW, 20.0f));
    Place(AbilityText, FVector2D(16.0f + ChipW + 6.0f, 140.0f), FVector2D(W - 32.0f - ChipW - 6.0f, 40.0f));
    if (AbilityText) {
      AbilityText->SetText(FText::FromString(Model.bDetails ? ClampLines(Model.Ability, TEXT("type.caption"), W - 32.0f - ChipW - 6.0f, 2) : FString()));
    }
    Place(PickButton, FVector2D(Tx, H - 12.0f - BtnH), FVector2D(Tw, BtnH));
    Place(TakenText, FVector2D(Tx, H - 12.0f - BtnH + 9.0f), FVector2D(Tw, 22.0f));
  }
}

void UUmHeroCard::Restyle() {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const bool bTaken = Model.State == EUmHeroCardState::Taken;
  const bool bPicked = Model.State == EUmHeroCardState::Picked;
  const bool bLoading = Model.State == EUmHeroCardState::Loading || !Model.bDetails;
  if (Body) {
    if (bHover && !bTaken && !bLoading) {
      Body->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("panel.bg.hover")), 4.0f, Theme.Color(TEXT("panel.edge")), 1.0f));
    } else if (const FSlateBrush* Inset = Theme.Skin(TEXT("panel.inset"))) {
      Body->SetBrush(*Inset);
    }
  }
  if (Edge) {
    // picked: the 3 su state.pending edge (never colour alone: the chip «ВЫБРАНО» goes with it)
    Edge->SetBrush(FSlateRoundedBoxBrush(FLinearColor::Transparent, 4.0f, Theme.Color(TEXT("state.pending")), 3.0f));
    Vis(Edge, bPicked);
  }
  const FSlateColor Primary(Theme.Color(TEXT("text.primary")));
  const FSlateColor Secondary(Theme.Color(TEXT("text.secondary")));
  if (NameText) NameText->SetColorAndOpacity(bTaken ? Secondary : Primary);
  if (StatsText) StatsText->SetColorAndOpacity(bTaken ? Secondary : Primary);
  Vis(LangChip, Model.bDetails && !Model.Ability.IsEmpty());
  Vis(SidekickBox, !Model.SidekickKey.IsNone() && Model.bDetails);
  Vis(TakenText, bTaken);
  Vis(PickButton, !bTaken, true);
  if (PickButton) {
    FUmButtonModel B;
    B.Variant = EUmButtonVariant::Normal;  // never primary (ВР-VS4-SC14-06)
    B.Label = S(bPicked ? TEXT("screens.room.hero.picked") : TEXT("screens.room.hero.pick"));
    B.HeightSu = 40.0f;
    B.MinWidthSu = 80.0f;
    B.bSelected = bPicked;
    B.bEnabled = Model.bEnabled && !bLoading;
    if (!B.bEnabled) B.Reason.Key = FName(TEXT("why.syncing"));
    PickButton->ApplyModel(B);
  }
  SetToolTipText(bTaken ? UmText::Get(EUmTable::Why, TEXT("why.hero.taken")) : FText::GetEmpty());
}

void UUmHeroCard::NativeOnMouseEnter(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  Super::NativeOnMouseEnter(InGeometry, InMouseEvent);
  bHover = true;
  Restyle();
}

void UUmHeroCard::NativeOnMouseLeave(const FPointerEvent& InMouseEvent) {
  Super::NativeOnMouseLeave(InMouseEvent);
  bHover = false;
  Restyle();
}

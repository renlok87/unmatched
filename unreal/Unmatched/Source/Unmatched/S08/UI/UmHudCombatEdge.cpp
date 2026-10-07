// VS-3 HB-30 / HB-31 / HB-32: one combat card at a field edge - see UmHudCombatEdge.h.
#include "UmHudCombatEdge.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08ArtHud.h"
#include "../S08IconMotion.h"
#include "UmButton.h"
#include "UmCardWidget.h"
#include "UmDeckRow.h"
#include "UmGameHud.h"
#include "UmHudStatusLine.h"
#include "UmHudTheme.h"
#include "UmTeamChip.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Engine/Texture2D.h"
#include "HAL/PlatformTime.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

const TCHAR* const UUmHudCombatEdge::WidgetBlueprintPath = TEXT("/Game/S08/UI/Hud/WBP_UI_HUD_COMBAT_EDGE");

bool FUmCombatEdgeModel::operator==(const FUmCombatEdgeModel& O) const {
  const bool bSameCard = Card.InstanceId == O.Card.InstanceId && Card.CardId == O.Card.CardId && Card.Name == O.Card.Name &&
                         Card.NameRu == O.Card.NameRu && Card.bHidden == O.Card.bHidden;
  return bShow == O.bShow && Role == O.Role && State == O.State && CombatKey == O.CombatKey && Seq == O.Seq &&
         FighterName == O.FighterName && TeamSlot == O.TeamSlot && HeroSlug == O.HeroSlug && bSameCard && bFace == O.bFace &&
         FlipDelayMs == O.FlipDelayMs && Boost == O.Boost && bButtons == O.bButtons && DefendWhy.Key == O.DefendWhy.Key &&
         NoDefenseWhy.Key == O.NoDefenseWhy.Key && bTimer == O.bTimer && DeadlineSec == O.DeadlineSec &&
         WindowSec == O.WindowSec;
}

namespace UmHudCombatEdge {
const TCHAR* StateName(EUmEdgeState State) {
  switch (State) {
    case EUmEdgeState::Back: return TEXT("back");
    case EUmEdgeState::Shield: return TEXT("shield");
    case EUmEdgeState::Chosen: return TEXT("chosen");
    case EUmEdgeState::Reveal: return TEXT("reveal");
    case EUmEdgeState::NoDefense: return TEXT("nodefense");
    default: return TEXT("");
  }
}

const TCHAR* TimerStateName(EUmTimerState State) {
  switch (State) {
    case EUmTimerState::Normal: return TEXT("normal");
    case EUmTimerState::Warning: return TEXT("warning");
    case EUmTimerState::Expired: return TEXT("expired");
    default: return TEXT("off");
  }
}

EUmTimerState TimerStateFor(bool bTimer, double LeftSec) {
  if (!bTimer) return EUmTimerState::Off;
  if (LeftSec <= 0.0) return EUmTimerState::Expired;
  // ВР-H18 «последние 10 с»: from «10 с» on (HB-31 test: 11 -> 10 s = warning)
  return LeftSec <= WarnFromSec ? EUmTimerState::Warning : EUmTimerState::Normal;
}

int32 ShownSeconds(double LeftSec) { return LeftSec <= 0.0 ? 0 : FMath::CeilToInt(LeftSec - 1.0e-6); }

FVector2D CardSize(bool bClassS) { return bClassS ? FVector2D(CardWSSu, CardHSSu) : FVector2D(CardWLSu, CardHLSu); }

float TagRoomSu(bool bClassS) { return (bClassS ? CardWSSu : CardWLSu) - TagLeftSu - TagRightSu; }

FText RoleText(EUmEdgeRole Role, const FString& Fighter) {
  FFormatNamedArguments A;
  A.Add(TEXT("fighter"), FText::FromString(Fighter));
  return UmText::Format(EUmTable::Hud, Role == EUmEdgeRole::Attack ? TEXT("hud.combat.role.attack") : TEXT("hud.combat.role.defense"), A);
}

float RibbonHeightSu(bool bClassS, int32 TagRows, bool bTimer) {
  const float Row = bClassS ? TagRowSSu : TagRowLSu;
  const float Base = FMath::Max(bClassS ? RibbonSSu : RibbonLSu, FMath::Max(1, TagRows) * Row + 8.0f);
  return Base + (bTimer ? TimerRowSu : 0.0f);
}

float LeaveMs(float SpeedMul, bool bReduced) {
  if (bReduced) return ReducedMs;
  return (LeaveFadeMs + LeaveFlyMs) * FMath::Max(0.0f, SpeedMul);
}

void LeaveAt(float TMs, float SpeedMul, bool bReduced, float& OutDecor, float& OutCard, float& OutFly) {
  OutFly = 0.0f;
  if (bReduced || SpeedMul <= 0.0f) {
    const float A = bReduced ? FMath::Clamp(1.0f - TMs / ReducedMs, 0.0f, 1.0f) : 0.0f;
    OutDecor = A;
    OutCard = A;
    return;
  }
  const float Fade = LeaveFadeMs * SpeedMul;
  const float Fly = LeaveFlyMs * SpeedMul;
  if (TMs < Fade) {
    const float K = TMs / Fade;
    OutDecor = 1.0f - K;
    OutCard = FMath::Lerp(1.0f, LeaveCardAlpha, K);
    return;
  }
  OutDecor = 0.0f;
  const float K = FMath::Clamp((TMs - Fade) / Fly, 0.0f, 1.0f);
  OutFly = 1.0f - FMath::Square(1.0f - K);  // ease out quad
  OutCard = FMath::Lerp(LeaveCardAlpha, 0.0f, K);
}
}  // namespace UmHudCombatEdge

namespace {
template <typename T>
T* UmEdgeFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

void UmEdgePlace(UWidget* W, const FVector2D& Pos, const FVector2D& Size, int32 Z) {
  if (UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr) {
    S->SetAnchors(FAnchors(0.0f, 0.0f));
    S->SetAlignment(FVector2D::ZeroVector);
    S->SetAutoSize(false);
    S->SetPosition(Pos);
    S->SetSize(Size);
    S->SetZOrder(Z);
  }
}

void UmEdgeShow(UWidget* W, bool bOn, ESlateVisibility On = ESlateVisibility::HitTestInvisible) {
  if (!W) return;
  const ESlateVisibility Want = bOn ? On : ESlateVisibility::Collapsed;
  if (W->GetVisibility() != Want) W->SetVisibility(Want);
}

void UmEdgeText(UTextBlock* T, FName Type, FName Color) {
  if (!T) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  T->SetFont(Theme.Font(Type));
  T->SetColorAndOpacity(FSlateColor(Theme.Color(Color)));
  T->SetShadowOffset(FVector2D::ZeroVector);
}

/** The v3 icon at Su (the display texture of the current DPI x UI scale). */
void UmEdgeIcon(US08AnimatedIconWidget* W, const TCHAR* Id, float Su) {
  if (!W) return;
  if (W->GetIconId() != FName(Id) || !FMath::IsNearlyEqual(W->GetDisplaySizeSu(), Su)) {
    if (W->SetIcon(FName(Id), Su, FMath::RoundToInt(Su))) {
      W->SetDisplaySizeSu(Su);
      W->ShowAtRest();
    }
  }
}

/** Team chip brushes per px (UmTeamChip, IC-44 / IC-45); kept referenced by the root set of the textures' owners. */
struct FUmEdgeChips {
  int32 Px = -1;
  UmTeamChip::FUmTeamChipBrushes Brushes;
};
FUmEdgeChips& UmEdgeChips() {
  static FUmEdgeChips Chips;
  return Chips;
}
const FSlateBrush* UmEdgeChip(int32 Slot, float PxPerSu) {
  FUmEdgeChips& C = UmEdgeChips();
  const int32 Px = UmTeamChip::TexturePx(UmTeamChip::HudSu, PxPerSu);
  if (C.Px != Px || !C.Brushes.bReady) {
    C.Brushes = UmTeamChip::Load(UmTeamChip::HudSu, PxPerSu, FCommandLine::Get());
    C.Px = Px;
    for (UTexture2D* T : C.Brushes.Textures) {
      if (T) T->AddToRoot();  // a handful of 24-48 px icons for the session (the HUD rebuilds never unload them)
    }
  }
  return C.Brushes.bReady ? &C.Brushes.Brushes[FMath::Clamp(Slot, 0, 1)] : nullptr;
}
}  // namespace

UClass* UUmHudCombatEdge::WidgetClass() {
  return UmGameHudSlots::WbpOrNative(UUmHudCombatEdge::StaticClass(), WidgetBlueprintPath);
}

bool UUmHudCombatEdge::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  UCanvasPanel* RootW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Root")));
  RootW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(RootW, nullptr)) return Fail(TEXT("Root"));
  auto Image = [&Tree](const TCHAR* Name) {
    UImage* I = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(Name));
    I->SetVisibility(ESlateVisibility::Collapsed);
    return I;
  };
  auto Icon = [&Tree](const TCHAR* Name) {
    US08AnimatedIconWidget* I = Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(Name));
    I->SetVisibility(ESlateVisibility::Collapsed);
    return I;
  };
  auto Text = [&Tree](const TCHAR* Name) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetVisibility(ESlateVisibility::Collapsed);
    return T;
  };
  // the empty slot (shield / nodefense) under the card's place
  if (!Attach(Image(TEXT("SlotUnderlay")), RootW)) return Fail(TEXT("SlotUnderlay"));
  if (!Attach(Image(TEXT("SlotFrame")), RootW)) return Fail(TEXT("SlotFrame"));
  if (!Attach(Icon(TEXT("SlotGlyph")), RootW)) return Fail(TEXT("SlotGlyph"));
  if (!Attach(Text(TEXT("SlotText")), RootW)) return Fail(TEXT("SlotText"));
  UUmCardWidget* CardW = Tree.ConstructWidget<UUmCardWidget>(UUmCardWidget::WidgetClass(), FName(TEXT("Card")));
  CardW->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(CardW, RootW)) return Fail(TEXT("Card"));
  if (!Attach(Icon(TEXT("Stamp")), RootW)) return Fail(TEXT("Stamp"));
  if (!Attach(Text(TEXT("StampText")), RootW)) return Fail(TEXT("StampText"));
  UBorder* Plate = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("CaptionPlate")));
  Plate->SetVisibility(ESlateVisibility::Collapsed);
  Plate->SetHorizontalAlignment(HAlign_Center);
  Plate->SetVerticalAlignment(VAlign_Center);
  Plate->SetPadding(FMargin(4.0f, 0.0f));
  if (!Attach(Plate, RootW)) return Fail(TEXT("CaptionPlate"));
  UTextBlock* Caption = Text(TEXT("CaptionText"));
  Caption->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(Caption, Plate)) return Fail(TEXT("CaptionText"));
  // the ribbon: the panel, then its parts over it on the root canvas
  UBorder* RibbonW = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("Ribbon")));
  RibbonW->SetVisibility(ESlateVisibility::Collapsed);
  RibbonW->SetPadding(FMargin(0.0f));
  if (!Attach(RibbonW, RootW)) return Fail(TEXT("Ribbon"));
  if (!Attach(Image(TEXT("WarnEdge")), RootW)) return Fail(TEXT("WarnEdge"));
  if (!Attach(Icon(TEXT("RoleIcon")), RootW)) return Fail(TEXT("RoleIcon"));
  UTextBlock* Role = Text(TEXT("RoleText"));
  Role->SetAutoWrapText(true);
  if (!Attach(Role, RootW)) return Fail(TEXT("RoleText"));
  if (!Attach(Image(TEXT("TeamChip")), RootW)) return Fail(TEXT("TeamChip"));
  if (!Attach(Text(TEXT("TimerText")), RootW)) return Fail(TEXT("TimerText"));
  if (!Attach(Image(TEXT("TimerTrack")), RootW)) return Fail(TEXT("TimerTrack"));
  if (!Attach(Image(TEXT("TimerBar")), RootW)) return Fail(TEXT("TimerBar"));
  if (!Attach(Icon(TEXT("WarnIcon")), RootW)) return Fail(TEXT("WarnIcon"));
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  for (const TCHAR* Name : {TEXT("DefendButton"), TEXT("NoDefenseButton")}) {
    UUmButton* B = Tree.ConstructWidget<UUmButton>(ButtonClass, FName(Name));
    B->SetVisibility(ESlateVisibility::Collapsed);
    if (!Attach(B, RootW)) return Fail(Name);
  }
  return true;
}

bool UUmHudCombatEdge::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  if (!WidgetTree->RootWidget) {
    FString Error;
    UWidgetTree* Tree = WidgetTree;
    bCodeDefaultTree = BuildDefaultTree(*Tree, [Tree](UWidget* Child, UPanelWidget* Parent) {
      if (!Parent) {
        Tree->RootWidget = Child;
        return true;
      }
      return Parent->AddChild(Child) != nullptr;
    }, &Error);
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD combat edge default tree: %s"), *Error);
  }
  Root = UmEdgeFind<UCanvasPanel>(WidgetTree, TEXT("Root"));
  Card = UmEdgeFind<UUmCardWidget>(WidgetTree, TEXT("Card"));
  Ribbon = UmEdgeFind<UBorder>(WidgetTree, TEXT("Ribbon"));
  RoleIcon = UmEdgeFind<US08AnimatedIconWidget>(WidgetTree, TEXT("RoleIcon"));
  RoleText = UmEdgeFind<UTextBlock>(WidgetTree, TEXT("RoleText"));
  TimerText = UmEdgeFind<UTextBlock>(WidgetTree, TEXT("TimerText"));
  TimerBar = UmEdgeFind<UImage>(WidgetTree, TEXT("TimerBar"));
  DefendButton = UmEdgeFind<UUmButton>(WidgetTree, TEXT("DefendButton"));
  NoDefenseButton = UmEdgeFind<UUmButton>(WidgetTree, TEXT("NoDefenseButton"));
  Stamp = UmEdgeFind<US08AnimatedIconWidget>(WidgetTree, TEXT("Stamp"));
  SlotUnderlay = UmEdgeFind<UImage>(WidgetTree, TEXT("SlotUnderlay"));
  SlotFrame = UmEdgeFind<UImage>(WidgetTree, TEXT("SlotFrame"));
  SlotGlyph = UmEdgeFind<US08AnimatedIconWidget>(WidgetTree, TEXT("SlotGlyph"));
  SlotText = UmEdgeFind<UTextBlock>(WidgetTree, TEXT("SlotText"));
  StampText = UmEdgeFind<UTextBlock>(WidgetTree, TEXT("StampText"));
  CaptionPlate = UmEdgeFind<UBorder>(WidgetTree, TEXT("CaptionPlate"));
  CaptionText = UmEdgeFind<UTextBlock>(WidgetTree, TEXT("CaptionText"));
  WarnEdge = UmEdgeFind<UImage>(WidgetTree, TEXT("WarnEdge"));
  TeamChip = UmEdgeFind<UImage>(WidgetTree, TEXT("TeamChip"));
  TimerTrack = UmEdgeFind<UImage>(WidgetTree, TEXT("TimerTrack"));
  WarnIcon = UmEdgeFind<US08AnimatedIconWidget>(WidgetTree, TEXT("WarnIcon"));
  // a WBP keeps neither the theme fonts nor the colours of the code tree: set at run time
  UmEdgeText(RoleText, TEXT("type.tag"), TEXT("text.primary"));
  UmEdgeText(TimerText, TEXT("type.tag"), TEXT("text.primary"));
  UmEdgeText(SlotText, TEXT("type.body"), TEXT("text.secondary"));
  UmEdgeText(CaptionText, TEXT("type.body"), TEXT("text.primary"));
  UmEdgeText(StampText, TEXT("type.display"), TEXT("state.error"));
  if (RoleText) RoleText->SetAutoWrapText(true);
  if (SlotText) {
    SlotText->SetAutoWrapText(true);
    SlotText->SetJustification(ETextJustify::Center);
  }
  if (CaptionText) CaptionText->SetJustification(ETextJustify::Center);
  if (StampText) StampText->SetText(FText::FromString(TEXT("X")));  // -S08CrossLegacy only (the AB-8 rollback)
  if (Card) {
    TWeakObjectPtr<UUmHudCombatEdge> WeakThis(this);
    Card->SetOnInspect([WeakThis]() {
      UUmHudCombatEdge* Self = WeakThis.Get();
      if (!Self || !Self->OnInspect) return;
      if (!(Self->Model.bFace && Self->bFaceShown) && Self->Side != EUmEdgeSide::Opp) return;  // the own back: nothing
      if (Self->Model.bFace && Self->bFaceShown) {
        Self->OnInspect(Self->Model.Card);
        return;
      }
      // VS-4 SC-22 (QA-005): the back (the defense slot before the reveal, a hidden boost) opens the hidden card - a
      // fresh placeholder, never the model's card: no name, no value leaves the edge before the reveal
      FS09CardView Hidden;
      Hidden.bHidden = true;
      Hidden.CardId = TEXT("hidden");
      Self->OnInspect(Hidden);
    });
  }
  if (Root) Root->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  SetVisibility(ESlateVisibility::Collapsed);
  return bFirst;
}

void UUmHudCombatEdge::BeginDestroy() {
  StopTicker();
  Super::BeginDestroy();
}

bool UUmHudCombatEdge::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Root) Missing.Add(TEXT("Root"));
  if (!Card) Missing.Add(TEXT("Card"));
  if (!Ribbon) Missing.Add(TEXT("Ribbon"));
  if (!RoleIcon) Missing.Add(TEXT("RoleIcon"));
  if (!RoleText) Missing.Add(TEXT("RoleText"));
  if (!TimerText) Missing.Add(TEXT("TimerText"));
  if (!TimerBar) Missing.Add(TEXT("TimerBar"));
  if (!DefendButton) Missing.Add(TEXT("DefendButton"));
  if (!NoDefenseButton) Missing.Add(TEXT("NoDefenseButton"));
  if (!Stamp) Missing.Add(TEXT("Stamp"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

FString UUmHudCombatEdge::SourceName() const {
  return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName();
}

void UUmHudCombatEdge::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter,
                                TFunction<void(const FS09HudPressOutcome&)> InOnDefend,
                                TFunction<void(const FS09HudPressOutcome&)> InOnNoDefense,
                                TFunction<void(const FS09CardView&)> InOnInspect) {
  Arbiter = InArbiter;
  OnInspect = MoveTemp(InOnInspect);
  auto Bind = [&InArbiter](UUmButton* B, const TCHAR* Id, TFunction<void(const FS09HudPressOutcome&)> Fn) {
    if (!B) return;
    TSharedPtr<TFunction<void(const FS09HudPressOutcome&)>> Shared = MakeShared<TFunction<void(const FS09HudPressOutcome&)>>(MoveTemp(Fn));
    B->SetPress(FName(Id), InArbiter, FS09OnHudPressOutcome::CreateLambda([Shared](const FS09HudPressOutcome& O) {
      if (*Shared) (*Shared)(O);
    }));
  };
  Bind(DefendButton, TEXT("hud.combat.defend"), MoveTemp(InOnDefend));
  Bind(NoDefenseButton, TEXT("hud.combat.no.defense"), MoveTemp(InOnNoDefense));
}

void UUmHudCombatEdge::SetSyncLoad(bool bOn) {
  if (Card) Card->SetSyncLoad(bOn);
}

void UUmHudCombatEdge::SetClockOverrideMs(double Ms) {
  ClockOverrideMs = Ms;
  if (Card) Card->SetClockOverrideMs(Ms);
  for (US08AnimatedIconWidget* I : {Stamp.Get(), SlotGlyph.Get(), WarnIcon.Get(), RoleIcon.Get()}) {
    if (I) I->SetClockOverrideMs(Ms >= 0.0 ? static_cast<float>(Ms) : -1.0f);
  }
}

double UUmHudCombatEdge::NowMs() const { return ClockOverrideMs >= 0.0 ? ClockOverrideMs : FPlatformTime::Seconds() * 1000.0; }

bool UUmHudCombatEdge::IsReduced() const {
  return ReducedOverride >= 0 ? ReducedOverride != 0 : S08IconMotion::IsReducedMotion();
}

bool UUmHudCombatEdge::IsCrossLegacy() const { return FParse::Param(FCommandLine::Get(), TEXT("S08CrossLegacy")); }

void UUmHudCombatEdge::SetFrame(const FUmCombatEdgeFrame& InFrame) {
  if (bHasFrame && Frame == InFrame) return;
  const bool bClassChanged = !bHasFrame || Frame.bClassS != InFrame.bClassS || Frame.PxPerSu != InFrame.PxPerSu;
  Frame = InFrame;
  bHasFrame = true;
  if (bClassChanged) CardShownId.Reset();  // the card takes its new show size (230 x 319 / 150 x 208) from the model
  if (bHasModel) ApplyContent(nullptr);
}

FBox2D UUmHudCombatEdge::RibbonRectSu() const {
  using namespace UmHudCombatEdge;
  if (!Frame.CardSu.bIsValid) return FBox2D(ForceInit);
  const float W = static_cast<float>(Frame.CardSu.Max.X - Frame.CardSu.Min.X);
  const float Top = static_cast<float>(Frame.CardSu.Max.Y) + RibbonGapSu;
  const float H = RibbonHeightSu(Frame.bClassS, TagRows, Model.bTimer);
  return FBox2D(FVector2D(Frame.CardSu.Min.X, Top), FVector2D(Frame.CardSu.Min.X + W, Top + H));
}

FBox2D UUmHudCombatEdge::DrawnRectSu() const {
  if (!bHasModel || !Model.bShow || !Frame.CardSu.bIsValid) return FBox2D(ForceInit);
  FBox2D R = Frame.CardSu;
  R += RibbonRectSu();
  if (Model.State == EUmEdgeState::Chosen) {
    R += FBox2D(Frame.CardSu.Min - FVector2D(0.0, UmHudCombatEdge::CaptionHSu + UmHudCombatEdge::CaptionGapSu), Frame.CardSu.Min);
  }
  if (Model.bButtons) {
    if (Frame.DefendSu.bIsValid) R += Frame.DefendSu;
    if (Frame.NoDefenseSu.bIsValid) R += Frame.NoDefenseSu;
  }
  return R;
}

FBox2D UUmHudCombatEdge::PaintedRectSu() const {
  // ВР-VS3-72: the edge as painted now - during the HB-32 leave the card flies (and shrinks) outside its rect
  FBox2D Out = DrawnRectSu();
  if (IsLeaving() && Frame.CardSu.bIsValid) {
    Out += Frame.CardSu;
    Out += RibbonRectSu();
    const double K = Card ? FMath::Max(static_cast<double>(Card->GetRenderTransform().Scale.X), 0.0) : 1.0;
    const FVector2D C = Frame.CardSu.GetCenter() + LeaveOffsetNow;
    const FVector2D H = 0.5 * Frame.CardSu.GetSize() * K;
    Out += FBox2D(C - H, C + H);
  }
  return Out;
}

void UUmHudCombatEdge::ApplyModel(const FUmCombatEdgeModel& InModel) {
  if (bHasModel && Model == InModel) return;
  const FUmCombatEdgeModel Old = Model;
  const bool bHadModel = bHasModel;
  Model = InModel;
  bHasModel = true;
  // a new combat: a leave in flight of the old one ends now (HB-32 p. 3)
  if (bHadModel && Model.bShow && Old.CombatKey != Model.CombatKey) CutLeave();
  ApplyContent(bHadModel ? &Old : nullptr);
}

void UUmHudCombatEdge::ApplyContent(const FUmCombatEdgeModel* Old) {
  using namespace UmHudCombatEdge;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (!Model.bShow || Model.State == EUmEdgeState::Hidden) {
    // the leave keeps drawing the last state until it ends
    if (!IsLeaving()) {
      SetVisibility(ESlateVisibility::Collapsed);
      StopTicker();
      TimerNow = EUmTimerState::Off;
      CardShownId.Reset();
      bFaceShown = false;
      PendingFlipAtMs = -1.0;
    }
    return;
  }
  if (!IsLeaving()) {
    // the root's opacity belongs to the owner (the deck panel fades the right edge under it)
    SetVisibility(ESlateVisibility::SelfHitTestInvisible);
    SetDecorOpacity(1.0f);
  }
  const bool bS = Frame.bClassS;
  const float Px = Frame.PxPerSu > 0.0f ? Frame.PxPerSu : 1.0f;
  const FVector2D Origin = Frame.OriginSu;
  const FVector2D CardPos = Frame.CardSu.bIsValid ? FVector2D(Frame.CardSu.Min) - Origin : FVector2D::ZeroVector;
  const FVector2D CardWH = CardSize(bS);
  CardCentreSu = Frame.CardSu.bIsValid ? FVector2D(Frame.CardSu.GetCenter()) : FVector2D::ZeroVector;
  // ---- the ribbon text: wrapped, never cut (the ribbon grows) ----
  const FText Role = UmHudCombatEdge::RoleText(Model.Role, Model.FighterName);
  {
    const float Size = 14.0f;
    TagRows = UmHudStatus::WrapLines(Role.ToString(), TagRoomSu(bS), Size,
                                     [](const FString& T, float S) { return UmDeckRow::MeasureSu(T, S, FName(TEXT("type.tag"))); });
  }
  // ---- the card or the empty slot ----
  const bool bEmptySlot = Model.State == EUmEdgeState::Shield || Model.State == EUmEdgeState::NoDefense;
  UmEdgeShow(SlotUnderlay, bEmptySlot);
  UmEdgeShow(SlotFrame, bEmptySlot);
  if (bEmptySlot) {
    const float R = Theme.RadiusSu(TEXT("radius.l"));
    if (SlotUnderlay) {
      SlotUnderlay->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("card.navy")), FMath::Max(0.0f, R - 1.0f)));
      UmEdgePlace(SlotUnderlay, CardPos + FVector2D(1.0), CardWH - FVector2D(2.0), 0);
    }
    if (SlotFrame) {
      const FSlateBrush* B = Theme.CardFrameFor(TEXT("card.frame.idle"), Px);
      SlotFrame->SetBrush(B ? *B : FSlateRoundedBoxBrush(FLinearColor::Transparent, R, Theme.Color(TEXT("panel.edge")), 1.0f));
      UmEdgePlace(SlotFrame, CardPos, CardWH, 1);
    }
  }
  const bool bShield = Model.State == EUmEdgeState::Shield;
  // VS-4 (VS-3 item 13, 04 §3.8 «штамп X + текст «Нет защиты»»): the no-defense slot names itself under the stamp
  const bool bNoDefenseText = Model.State == EUmEdgeState::NoDefense;
  UmEdgeShow(SlotGlyph, bShield);
  UmEdgeShow(SlotText, bShield || bNoDefenseText);
  if (bShield) {
    UmEdgeIcon(SlotGlyph, TEXT("action-defense"), SlotGlyphSu);
    UmEdgePlace(SlotGlyph, CardPos + FVector2D(0.5f * (CardWH.X - SlotGlyphSu), FMath::RoundToFloat(0.27f * CardWH.Y)),
                FVector2D(SlotGlyphSu), 2);
    if (SlotText) {
      SlotText->SetText(UmText::Get(EUmTable::Hud, TEXT("hud.combat.slot.empty")));
      SlotText->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.secondary"))));
      UmEdgePlace(SlotText, CardPos + FVector2D(12.0f, FMath::RoundToFloat(0.65f * CardWH.Y)), FVector2D(CardWH.X - 24.0f, 44.0f), 2);
    }
  } else if (bNoDefenseText && SlotText) {
    SlotText->SetText(UmText::Get(EUmTable::Hud, TEXT("hud.combat.nodefense")));
    SlotText->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
    UmEdgePlace(SlotText, CardPos + FVector2D(12.0f, FMath::RoundToFloat(0.5f * (CardWH.Y + SlotGlyphSu)) + 8.0f),
                FVector2D(CardWH.X - 24.0f, 44.0f), 3);
  }
  // the stamp (AB-8): once per combat, appear 200 ms; -S08CrossLegacy: the text X
  const bool bNoDefense = Model.State == EUmEdgeState::NoDefense;
  const bool bLegacyX = bNoDefense && IsCrossLegacy();
  UmEdgeShow(Stamp, bNoDefense && !bLegacyX);
  UmEdgeShow(StampText, bLegacyX);
  if (bNoDefense) {
    UmEdgeIcon(Stamp, TEXT("marker-x-stamp"), SlotGlyphSu);
    UmEdgePlace(Stamp, CardPos + 0.5f * (CardWH - FVector2D(SlotGlyphSu)), FVector2D(SlotGlyphSu), 3);
    UmEdgePlace(StampText, CardPos + 0.5f * (CardWH - FVector2D(SlotGlyphSu)), FVector2D(SlotGlyphSu), 3);
    if (StampKey != Model.CombatKey) {
      StampKey = Model.CombatKey;
      if (Stamp && !bLegacyX) {
        Stamp->SetReducedMotion(IsReduced());
        Stamp->PlayAnim(TEXT("appear"));
      }
      PendingTrace.Add(FString::Printf(TEXT("HUD-STAMP no-defense seq=%d side=%s icon=%s"), Model.Seq,
                                       Side == EUmEdgeSide::Own ? TEXT("own") : TEXT("opp"),
                                       bLegacyX ? TEXT("legacy-text") : TEXT("marker-x-stamp")));
    }
  }
  // the card (back / chosen / reveal): the face turns on the spot when it becomes public (HB-32)
  const bool bCard = Model.State == EUmEdgeState::Back || Model.State == EUmEdgeState::Chosen || Model.State == EUmEdgeState::Reveal;
  if (Card) {
    if (!bCard) {
      UmEdgeShow(Card, false);
      CardShownId.Reset();
      bFaceShown = false;
      PendingFlipAtMs = -1.0;
    } else {
      UmEdgeShow(Card, true, ESlateVisibility::Visible);
      UmEdgePlace(Card, CardPos, CardWH, 1);
      FUmCardState S;
      S.Show = bS ? EUmCardShow::ClassSCombat : EUmCardShow::Combat;
      S.HeroSlug = Model.HeroSlug;
      S.PxPerSu = Px;
      const bool bSameCard = !CardShownId.IsEmpty() && CardShownId == Model.Card.InstanceId;
      if (!bSameCard) {
        S.bFaceDown = !Model.bFace;
        Card->ApplyModel(Model.Card, S);
        CardShownId = Model.Card.InstanceId;
        bFaceShown = Model.bFace;
        PendingFlipAtMs = -1.0;
      } else if (Model.bFace && !bFaceShown && PendingFlipAtMs < 0.0) {
        // the reveal: the attack card at once, the defense card +120 ms (x speed) - Step starts the flip
        PendingFlipAtMs = NowMs() + FMath::Max(0.0f, Model.FlipDelayMs);
      } else if (!Model.bFace && bFaceShown) {
        S.bFaceDown = true;
        Card->ApplyModel(Model.Card, S);
        bFaceShown = false;
        PendingFlipAtMs = -1.0;
      }
      Card->SetBoostChip(Model.bFace ? Model.Boost : UmCardWidget::NoBoostChip);
    }
  }
  // «Карта выбрана» on its own plate above the card (never over the back)
  const bool bCaption = Model.State == EUmEdgeState::Chosen;
  UmEdgeShow(CaptionPlate, bCaption);
  if (bCaption && CaptionPlate) {
    if (const FSlateBrush* Skin = Theme.SkinFor(TEXT("panel"), Px)) CaptionPlate->SetBrush(*Skin);
    if (CaptionText) CaptionText->SetText(UmText::Get(EUmTable::Hud, TEXT("hud.combat.slot.chosen")));
    UmEdgePlace(CaptionPlate, CardPos - FVector2D(0.0f, CaptionHSu + CaptionGapSu), FVector2D(CardWH.X, CaptionHSu), 4);
  }
  // ---- the ribbon ----
  const FBox2D RibbonSu = RibbonRectSu();
  const FVector2D RibbonPos = FVector2D(RibbonSu.Min) - Origin;
  const FVector2D RibbonWH = RibbonSu.GetSize();
  const float BaseH = RibbonHeightSu(bS, TagRows, false);
  UmEdgeShow(Ribbon, true);
  if (Ribbon) {
    if (const FSlateBrush* Skin = Theme.SkinFor(TEXT("panel"), Px)) Ribbon->SetBrush(*Skin);
    UmEdgePlace(Ribbon, RibbonPos, RibbonWH, 2);
  }
  UmEdgeShow(RoleIcon, true);
  UmEdgeIcon(RoleIcon, Model.Role == EUmEdgeRole::Attack ? TEXT("action-attack") : TEXT("action-defense"), DiscSu);
  UmEdgePlace(RoleIcon, RibbonPos + FVector2D(3.0f, 0.5f * (BaseH - DiscSu)), FVector2D(DiscSu), 3);
  if (RoleText) {
    UmEdgeShow(RoleText, true);
    RoleText->SetText(Role);
    RoleText->SetWrapTextAt(TagRoomSu(bS));
    const float Row = bS ? TagRowSSu : TagRowLSu;
    const float TextH = TagRows * Row;
    UmEdgePlace(RoleText, RibbonPos + FVector2D(TagLeftSu, 0.5f * (BaseH - TextH)), FVector2D(TagRoomSu(bS) + 2.0f, TextH), 3);
  }
  if (TeamChip) {
    const FSlateBrush* B = UmEdgeChip(Model.TeamSlot, Px);
    UmEdgeShow(TeamChip, B != nullptr);
    if (B) {
      TeamChip->SetBrush(*B);
      TeamChip->SetColorAndOpacity(Theme.Color(Model.TeamSlot == 0 ? TEXT("team.p1.screen") : TEXT("team.p2.screen")));
      UmEdgePlace(TeamChip, RibbonPos + FVector2D(RibbonWH.X - 4.0f - UmTeamChip::HudSu, 0.5f * (BaseH - UmTeamChip::HudSu)),
                  FVector2D(UmTeamChip::HudSu), 3);
    }
  }
  // the timer row (HB-31): the text, the warning sign, the bar at the ribbon bottom
  UmEdgeShow(TimerText, Model.bTimer);
  UmEdgeShow(TimerTrack, Model.bTimer);
  UmEdgeShow(TimerBar, Model.bTimer);
  if (Model.bTimer) {
    UmEdgePlace(TimerText, RibbonPos + FVector2D(6.0f, BaseH + 1.0f), FVector2D(RibbonWH.X - 44.0f, TimerRowSu - 6.0f), 3);
    if (TimerTrack) {
      TimerTrack->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("panel.bg.inset")), 0.0f));
      UmEdgePlace(TimerTrack, RibbonPos + FVector2D(0.0f, RibbonWH.Y - TimerBarSu), FVector2D(RibbonWH.X, TimerBarSu), 3);
    }
    if (TimerBar) TimerBar->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("card.cream")), 0.0f));
    if (WarnIcon) UmEdgeIcon(WarnIcon, TEXT("state-warning"), WarnSu);
    UmEdgePlace(WarnIcon, RibbonPos + FVector2D(RibbonWH.X - 8.0f - WarnSu, BaseH), FVector2D(WarnSu), 4);
    if (WarnEdge) {
      WarnEdge->SetBrush(FSlateRoundedBoxBrush(FLinearColor::Transparent, Theme.RadiusSu(TEXT("radius.s")),
                                               Theme.Color(TEXT("state.warning")), 2.0f));
      UmEdgePlace(WarnEdge, RibbonPos, RibbonWH, 5);
    }
    StartTicker();
  } else {
    StopTicker();
    UmEdgeShow(WarnIcon, false);
    UmEdgeShow(WarnEdge, false);
    if (TimerNow != EUmTimerState::Off) TimerNow = EUmTimerState::Off;
    TimerSecondsNow = -1;
  }
  ApplyTimer(true);
  ApplyButtons();
  Step();
}

void UUmHudCombatEdge::ApplyButtons() {
  const bool bOn = Model.bShow && Model.bButtons;
  UmEdgeShow(DefendButton, bOn, ESlateVisibility::Visible);
  UmEdgeShow(NoDefenseButton, bOn, ESlateVisibility::Visible);
  if (!bOn) return;
  const bool bS = Frame.bClassS;
  const float H = bS ? 40.0f : 48.0f;
  // HB-31: after the deadline both refuse with why.deadline.passed
  const bool bExpired = TimerNow == EUmTimerState::Expired;
  const FS09Reason Deadline = FS09Reason::Make(TEXT("why.deadline.passed"));
  if (DefendButton) {
    FUmButtonModel B;
    B.Variant = EUmButtonVariant::Primary;
    B.Label = UmText::Get(EUmTable::Hud, TEXT("hud.combat.defend"));
    B.Reason = bExpired ? Deadline : Model.DefendWhy;
    B.bEnabled = !B.Reason.IsSet();
    B.HeightSu = H;
    B.MinWidthSu = static_cast<float>(Frame.DefendSu.Max.X - Frame.DefendSu.Min.X);
    DefendButton->ApplyModel(B);
    UmEdgePlace(DefendButton, FVector2D(Frame.DefendSu.Min) - Frame.OriginSu, FVector2D(B.MinWidthSu, H), 6);
  }
  if (NoDefenseButton) {
    FUmButtonModel B;
    B.Variant = EUmButtonVariant::Normal;
    B.Label = UmText::Get(EUmTable::Hud, TEXT("hud.combat.no.defense"));
    B.Reason = bExpired ? Deadline : Model.NoDefenseWhy;
    B.bEnabled = !B.Reason.IsSet();
    B.HeightSu = H;
    B.MinWidthSu = static_cast<float>(Frame.NoDefenseSu.Max.X - Frame.NoDefenseSu.Min.X);
    NoDefenseButton->ApplyModel(B);
    UmEdgePlace(NoDefenseButton, FVector2D(Frame.NoDefenseSu.Min) - Frame.OriginSu, FVector2D(B.MinWidthSu, H), 6);
  }
}

void UUmHudCombatEdge::ApplyTimer(bool bForce) {
  using namespace UmHudCombatEdge;
  if (!Model.bTimer || !Model.bShow) return;
  const double Left = Model.DeadlineSec - NowMs() / 1000.0;
  const EUmTimerState State = TimerStateFor(true, Left);
  const int32 Seconds = ShownSeconds(Left);
  const bool bStateChanged = State != TimerNow;
  // between whole seconds only the bar moves
  if (TimerText && (bForce || Seconds != TimerSecondsNow)) {
    FFormatNamedArguments A;
    A.Add(TEXT("n"), FText::FromString(FString::FromInt(Seconds)));
    TimerText->SetText(UmText::Format(EUmTable::Hud, TEXT("hud.combat.timer"), A));
  }
  TimerSecondsNow = Seconds;
  if (TimerBar && Frame.CardSu.bIsValid) {
    const FBox2D R = RibbonRectSu();
    const float Frac = Model.WindowSec > 0.0f ? FMath::Clamp(static_cast<float>(Left) / Model.WindowSec, 0.0f, 1.0f) : 0.0f;
    UmEdgePlace(TimerBar, FVector2D(R.Min.X, R.Max.Y - TimerBarSu) - Frame.OriginSu,
                FVector2D(Frac * static_cast<float>(R.Max.X - R.Min.X), TimerBarSu), 4);
  }
  const bool bWarn = State == EUmTimerState::Warning || State == EUmTimerState::Expired;
  UmEdgeShow(WarnEdge, bWarn);
  UmEdgeShow(WarnIcon, bWarn);
  if (bStateChanged) {
    const EUmTimerState Was = TimerNow;
    TimerNow = State;
    if (bWarn && WarnIcon && Was != EUmTimerState::Warning) {
      WarnIcon->SetReducedMotion(IsReduced());
      WarnIcon->PlayAnim(TEXT("appear"));
    }
    PendingTrace.Add(FString::Printf(TEXT("HUD-TIMER left=%d state=%s side=%s seq=%d"), Seconds, TimerStateName(State),
                                     Side == EUmEdgeSide::Own ? TEXT("own") : TEXT("opp"), Model.Seq));
    if (State == EUmTimerState::Expired || Was == EUmTimerState::Expired) ApplyButtons();
  }
}

void UUmHudCombatEdge::SetDecorOpacity(float Alpha) {
  for (UWidget* W : {static_cast<UWidget*>(Ribbon.Get()), static_cast<UWidget*>(RoleIcon.Get()), static_cast<UWidget*>(RoleText.Get()),
                     static_cast<UWidget*>(TeamChip.Get()), static_cast<UWidget*>(TimerText.Get()), static_cast<UWidget*>(TimerTrack.Get()),
                     static_cast<UWidget*>(TimerBar.Get()), static_cast<UWidget*>(WarnIcon.Get()), static_cast<UWidget*>(WarnEdge.Get()),
                     static_cast<UWidget*>(CaptionPlate.Get()), static_cast<UWidget*>(Stamp.Get()), static_cast<UWidget*>(StampText.Get()),
                     static_cast<UWidget*>(SlotUnderlay.Get()), static_cast<UWidget*>(SlotFrame.Get()), static_cast<UWidget*>(SlotGlyph.Get()),
                     static_cast<UWidget*>(SlotText.Get()), static_cast<UWidget*>(DefendButton.Get()),
                     static_cast<UWidget*>(NoDefenseButton.Get())}) {
    if (W && !FMath::IsNearlyEqual(W->GetRenderOpacity(), Alpha, 1.0e-3f)) W->SetRenderOpacity(Alpha);
  }
}

void UUmHudCombatEdge::StartLeave() {
  if (!bHasModel || IsLeaving() || GetVisibility() == ESlateVisibility::Collapsed) return;
  LeaveStartMs = NowMs();
  // nothing of the edge takes the pointer while it leaves
  SetVisibility(ESlateVisibility::HitTestInvisible);
  StopTicker();
  ApplyLeave();
}

void UUmHudCombatEdge::CutLeave() {
  if (!IsLeaving()) return;
  LeaveStartMs = -1.0;
  LeaveDecorNow = 1.0f;
  LeaveCardNow = 1.0f;
  LeaveOffsetNow = FVector2D::ZeroVector;
  if (Card) {
    Card->SetRenderTranslation(FVector2D::ZeroVector);
    Card->SetRenderScale(FVector2D(1.0f));
    Card->SetRenderOpacity(1.0f);
  }
  SetDecorOpacity(1.0f);
  SetVisibility(ESlateVisibility::Collapsed);
  CardShownId.Reset();
  bFaceShown = false;
}

void UUmHudCombatEdge::ApplyLeave() {
  using namespace UmHudCombatEdge;
  if (!IsLeaving()) return;
  const bool bReduced = IsReduced();
  const float T = static_cast<float>(NowMs() - LeaveStartMs);
  float Decor = 1.0f, CardA = 1.0f, Fly = 0.0f;
  LeaveAt(T, Frame.SpeedMul, bReduced, Decor, CardA, Fly);
  LeaveDecorNow = Decor;
  LeaveCardNow = CardA;
  SetDecorOpacity(Decor);
  const FVector2D Delta = Frame.LeaveToSu.IsZero() ? FVector2D::ZeroVector : Frame.LeaveToSu - CardCentreSu;
  LeaveOffsetNow = Delta * Fly;
  if (Card) {
    Card->SetRenderOpacity(CardA);
    Card->SetRenderTranslation(LeaveOffsetNow);
    // the card shrinks towards the chip's mini card (32 su wide) on the way
    const float Mini = 32.0f / UmHudCombatEdge::CardSize(Frame.bClassS).X;
    Card->SetRenderScale(FVector2D(FMath::Lerp(1.0f, Mini, Fly)));
  }
  if (T >= LeaveMs(Frame.SpeedMul, bReduced)) {
    LeaveStartMs = -1.0;
    if (Card) {
      Card->SetRenderTranslation(FVector2D::ZeroVector);
      Card->SetRenderScale(FVector2D(1.0f));
      Card->SetRenderOpacity(1.0f);
    }
    SetDecorOpacity(1.0f);
    LeaveDecorNow = 0.0f;
    LeaveCardNow = 0.0f;
    SetVisibility(ESlateVisibility::Collapsed);
    CardShownId.Reset();
    bFaceShown = false;
    PendingFlipAtMs = -1.0;
  }
}

void UUmHudCombatEdge::Step() {
  if (PendingFlipAtMs >= 0.0 && NowMs() >= PendingFlipAtMs && Card) {
    PendingFlipAtMs = -1.0;
    bFaceShown = true;
    Card->Flip(true, Frame.SpeedMul, &Model.Card);
  }
  if (IsLeaving()) ApplyLeave();
  if (Model.bTimer) ApplyTimer(false);  // the 4 Hz ticker between steps; tests and frozen sheets step it here
}

void UUmHudCombatEdge::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  if (PendingFlipAtMs >= 0.0 || IsLeaving()) Step();
}

void UUmHudCombatEdge::StartTicker() {
  if (TickerHandle.IsValid() || ClockOverrideMs >= 0.0) return;
  TWeakObjectPtr<UUmHudCombatEdge> WeakThis(this);
  TickerHandle = FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([WeakThis](float Dt) {
    UUmHudCombatEdge* Self = WeakThis.Get();
    return Self ? Self->OnTicker(Dt) : false;
  }), UmHudCombatEdge::TickSec);
}

void UUmHudCombatEdge::StopTicker() {
  if (!TickerHandle.IsValid()) return;
  FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
  TickerHandle.Reset();
}

bool UUmHudCombatEdge::OnTicker(float /*DeltaTime*/) {
  if (!Model.bTimer || !Model.bShow) {
    TickerHandle.Reset();
    return false;  // the ticker removes itself outside the defense window
  }
  ApplyTimer(false);
  return true;
}

TArray<FString> UUmHudCombatEdge::TakeTrace() {
  TArray<FString> Out = MoveTemp(PendingTrace);
  PendingTrace.Reset();
  return Out;
}

bool UUmHudCombatEdge::IsStampShown() const {
  return (Stamp && Stamp->GetVisibility() != ESlateVisibility::Collapsed) ||
         (StampText && StampText->GetVisibility() != ESlateVisibility::Collapsed);
}

void UUmHudCombatEdge::CollectShotLines(TArray<FString>& Out) const {
  using namespace UmHudCombatEdge;
  const float Px = Frame.PxPerSu > 0.0f ? Frame.PxPerSu : 1.0f;
  // ВР-VS3-72: a leaving card is painted outside the edge's rect (and the SHOT line says visible=0): its painted rect
  if (IsLeaving()) {
    const FBox2D P = PaintedRectSu();
    if (P.bIsValid) {
      Out.Add(FString::Printf(TEXT("HUD-EDGE-PAINT side=%s painted=(%.0f,%.0f,%.0f,%.0f) leave=1"),
                              Side == EUmEdgeSide::Own ? TEXT("own") : TEXT("opp"), P.Min.X * Px, P.Min.Y * Px, P.Max.X * Px,
                              P.Max.Y * Px));
    }
  }
  if (!bHasModel || !Model.bShow || Model.State == EUmEdgeState::Hidden) return;
  const bool bVisible = UmGameHudSlots::ShownByProperty(this) && !IsLeaving();
  FS08ScreenRect Rect;
  const FBox2D R = DrawnRectSu();
  if (R.bIsValid) Rect = FS08ScreenRect(R.Min.X * Px, R.Min.Y * Px, R.Max.X * Px, R.Max.Y * Px);
  const FVector2D CardWH = CardSize(Frame.bClassS);
  const FBox2D Rib = RibbonRectSu();
  FString Defend = TEXT("-");
  if (Model.bButtons) {
    const FS09Reason Why = TimerNow == EUmTimerState::Expired ? FS09Reason::Make(TEXT("why.deadline.passed")) : Model.DefendWhy;
    Defend = Why.IsSet() ? FString::Printf(TEXT("off:%s"), *Why.Key.ToString()) : FString(TEXT("on"));
  }
  const FString Extra = FString::Printf(
      TEXT("role=%s face=%d class=%s card=%.0fx%.0f ribbon=%.0fx%.0f rows=%d timer=%s timerState=%s buttons=%d defend=%s stamp=%d "
           "stampText=%d leave=%d seq=%d"),
      Model.Role == EUmEdgeRole::Attack ? TEXT("attack") : TEXT("defense"), Model.bFace && bFaceShown ? 1 : 0,
      Frame.bClassS ? TEXT("S") : TEXT("L"), CardWH.X, CardWH.Y, Rib.Max.X - Rib.Min.X, Rib.Max.Y - Rib.Min.Y, TagRows,
      Model.bTimer ? *FString::FromInt(TimerSecondsNow) : TEXT("-"), TimerStateName(TimerNow), Model.bButtons ? 1 : 0, *Defend,
      IsStampShown() ? 1 : 0,
      Model.State == EUmEdgeState::NoDefense && SlotText && SlotText->GetVisibility() != ESlateVisibility::Collapsed ? 1 : 0,
      IsLeaving() ? 1 : 0, Model.Seq);
  Out.Add(S08ArtHud::FormatWidgetLineEx(TEXT("UI-HUD-COMBAT-EDGE"), TEXT("umg"), StateName(Model.State),
                                        Side == EUmEdgeSide::Own ? FString(TEXT("own")) : FString(TEXT("opp")), Rect,
                                        bVisible && !Rect.IsEmpty(), bVisible, SourceName(), Extra));
}

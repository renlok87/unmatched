// VS-4 HB-37: the source card at the top left - see UmHudSourceSlot.h.
#include "UmHudSourceSlot.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08ArtHud.h"
#include "../S08IconMotion.h"
#include "UmCardWidget.h"
#include "UmDeckRow.h"
#include "UmGameHud.h"
#include "UmHudPending.h"
#include "UmHudStatusLine.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/TextBlock.h"
#include "HAL/PlatformTime.h"

const TCHAR* const UUmHudSourceSlot::WidgetBlueprintPath = TEXT("/Game/S08/UI/Hud/WBP_UI_HUD_SLOT");

namespace UmHudSourceSlot {
FName RibbonIcon(ES09SlotRibbon Ribbon) {
  switch (Ribbon) {
    case ES09SlotRibbon::Boosted: return FName(TEXT("marker-slot-boost"));
    case ES09SlotRibbon::Discarded: return FName(TEXT("marker-slot-discard"));
    default: return FName(TEXT("marker-slot-scheme"));
  }
}

const TCHAR* RibbonKey(ES09SlotRibbon Ribbon) {
  switch (Ribbon) {
    case ES09SlotRibbon::Boosted: return TEXT("hud.slot.boost");
    case ES09SlotRibbon::Discarded: return TEXT("hud.slot.discard");
    default: return TEXT("hud.slot.scheme");
  }
}

FName RibbonFill(ES09SlotRibbon Ribbon) {
  return Ribbon == ES09SlotRibbon::Scheme ? FName(TEXT("card.type.scheme")) : FName(TEXT("card.navy"));
}

FName RibbonInk(ES09SlotRibbon Ribbon) {
  switch (Ribbon) {
    case ES09SlotRibbon::Boosted: return FName(TEXT("card.glyph"));
    case ES09SlotRibbon::Discarded: return FName(TEXT("text.secondary"));
    default: return FName(TEXT("card.navy"));
  }
}

float GlyphSu(float PxPerSu) { return UmCardWidget::ChipSuFor(PxPerSu); }

const TCHAR* PhaseName(EUmSlotPhase Phase) {
  switch (Phase) {
    case EUmSlotPhase::Fly: return TEXT("fly");
    case EUmSlotPhase::Hold: return TEXT("hold");
    case EUmSlotPhase::Show: return TEXT("show");
    case EUmSlotPhase::Fade: return TEXT("fade");
    default: return TEXT("hidden");
  }
}

EUmSlotPhase PhaseOf(ES09SlotState State) {
  switch (State) {
    case ES09SlotState::Fly: return EUmSlotPhase::Fly;
    case ES09SlotState::Hold: return EUmSlotPhase::Hold;
    case ES09SlotState::Show: return EUmSlotPhase::Show;
    case ES09SlotState::Fade: return EUmSlotPhase::Fade;
    default: return EUmSlotPhase::Hidden;
  }
}

float RibbonWidthSu(bool bClassS, float CardWidthSu, ES09SlotRibbon Ribbon) {
  return bClassS && Ribbon == ES09SlotRibbon::Boosted ? FMath::Max(CardWidthSu, BoostRibbonSSu) : CardWidthSu;
}

float RibbonHeightSu(int32 Rows, float GlyphSize) {
  // HB-34 fix1: one row 28 su (type.tag 14 + 2 x 7), every further row + 18 su; the glyph keeps 2 su above and below
  const float Text = 14.0f + 18.0f * FMath::Max(0, Rows - 1) + 14.0f;
  return FMath::Max(RibbonMinSu, FMath::Max(GlyphSize + 4.0f, Text));
}

float LeaveAlpha(float TMs, bool bReduced) {
  const float Dur = bReduced ? ReducedMs : LeaveMs;
  return FMath::Clamp(1.0f - TMs / Dur, 0.0f, 1.0f);
}
}  // namespace UmHudSourceSlot

namespace {
template <typename T>
T* UmSlFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

void UmSlPlace(UWidget* W, const FVector2D& Pos, const FVector2D& Size, int32 Z) {
  if (UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr) {
    S->SetAnchors(FAnchors(0.0f, 0.0f));
    S->SetAlignment(FVector2D::ZeroVector);
    S->SetAutoSize(false);
    S->SetPosition(Pos);
    S->SetSize(Size);
    S->SetZOrder(Z);
  }
}

void UmSlShow(UWidget* W, bool bOn) {
  if (!W) return;
  const ESlateVisibility Want = bOn ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed;
  if (W->GetVisibility() != Want) W->SetVisibility(Want);
}

void UmSlIcon(US08AnimatedIconWidget* W, FName Id, float Su) {
  if (!W) return;
  if (W->GetIconId() != Id || !FMath::IsNearlyEqual(W->GetDisplaySizeSu(), Su)) {
    if (W->SetIcon(Id, Su, FMath::RoundToInt(Su))) {
      W->SetDisplaySizeSu(Su);
      W->ShowAtRest();
    }
  }
}

FText UmSlLabel(const FUmSlotModel& M) {
  const FText Slot = UmText::Get(EUmTable::Hud, UmHudSourceSlot::RibbonKey(M.Ribbon));
  if (M.OwnerName.IsEmpty()) return Slot;
  FFormatNamedArguments A;
  A.Add(TEXT("slot"), Slot);
  A.Add(TEXT("hero"), FText::FromString(M.OwnerName));
  return UmText::Format(EUmTable::Hud, TEXT("hud.slot.owner"), A);
}
}  // namespace

UClass* UUmHudSourceSlot::WidgetClass() {
  return UmGameHudSlots::WbpOrNative(UUmHudSourceSlot::StaticClass(), WidgetBlueprintPath);
}

bool UUmHudSourceSlot::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  UCanvasPanel* RootW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Root")));
  RootW->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(RootW, nullptr)) return Fail(TEXT("Root"));
  UUmCardWidget* CardW = Tree.ConstructWidget<UUmCardWidget>(UUmCardWidget::WidgetClass(), FName(TEXT("Card")));
  CardW->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(CardW, RootW)) return Fail(TEXT("Card"));
  UBorder* RibbonW = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("Ribbon")));
  RibbonW->SetVisibility(ESlateVisibility::Collapsed);
  RibbonW->SetPadding(FMargin(0.0f));
  if (!Attach(RibbonW, RootW)) return Fail(TEXT("Ribbon"));
  UImage* EdgeW = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("RibbonEdge")));
  EdgeW->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(EdgeW, RootW)) return Fail(TEXT("RibbonEdge"));
  US08AnimatedIconWidget* IconW = Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("RibbonIcon")));
  IconW->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(IconW, RootW)) return Fail(TEXT("RibbonIcon"));
  UTextBlock* TextW = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("RibbonText")));
  TextW->SetVisibility(ESlateVisibility::Collapsed);
  TextW->SetAutoWrapText(true);
  if (!Attach(TextW, RootW)) return Fail(TEXT("RibbonText"));
  UOverlay* Chip = Tree.ConstructWidget<UOverlay>(UOverlay::StaticClass(), FName(TEXT("BoostChip")));
  Chip->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(Chip, RootW)) return Fail(TEXT("BoostChip"));
  US08AnimatedIconWidget* ChipIcon = Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("BoostIcon")));
  if (!Attach(ChipIcon, Chip)) return Fail(TEXT("BoostIcon"));
  UTextBlock* ChipText = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("BoostText")));
  ChipText->SetJustification(ETextJustify::Center);
  if (!Attach(ChipText, Chip)) return Fail(TEXT("BoostText"));
  if (UOverlaySlot* S = Cast<UOverlaySlot>(ChipText->Slot)) {
    S->SetHorizontalAlignment(HAlign_Center);
    S->SetVerticalAlignment(VAlign_Center);
  }
  for (const TCHAR* Name : {TEXT("HoldTrack"), TEXT("HoldFill")}) {
    UImage* I = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(Name));
    I->SetVisibility(ESlateVisibility::Collapsed);
    if (!Attach(I, RootW)) return Fail(Name);
  }
  return true;
}

bool UUmHudSourceSlot::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD source slot default tree: %s"), *Error);
  }
  UWidgetTree* T = WidgetTree;
  Root = UmSlFind<UCanvasPanel>(T, TEXT("Root"));
  Card = UmSlFind<UUmCardWidget>(T, TEXT("Card"));
  Ribbon = UmSlFind<UBorder>(T, TEXT("Ribbon"));
  RibbonEdge = UmSlFind<UImage>(T, TEXT("RibbonEdge"));
  RibbonIcon = UmSlFind<US08AnimatedIconWidget>(T, TEXT("RibbonIcon"));
  RibbonText = UmSlFind<UTextBlock>(T, TEXT("RibbonText"));
  BoostChip = UmSlFind<UOverlay>(T, TEXT("BoostChip"));
  BoostIcon = UmSlFind<US08AnimatedIconWidget>(T, TEXT("BoostIcon"));
  BoostText = UmSlFind<UTextBlock>(T, TEXT("BoostText"));
  HoldTrack = UmSlFind<UImage>(T, TEXT("HoldTrack"));
  HoldFill = UmSlFind<UImage>(T, TEXT("HoldFill"));
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (RibbonText) {
    RibbonText->SetFont(Theme.Font(TEXT("type.tag")));
    RibbonText->SetShadowOffset(FVector2D::ZeroVector);
    RibbonText->SetAutoWrapText(true);
  }
  if (BoostText) {
    BoostText->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("card.glyph"))));
    BoostText->SetShadowOffset(FVector2D::ZeroVector);
  }
  // the slot never takes the pointer: a click on it is a click on the field (the hold's skip, F-10)
  if (Root) Root->SetVisibility(ESlateVisibility::HitTestInvisible);
  SetVisibility(ESlateVisibility::Collapsed);
  return bFirst;
}

bool UUmHudSourceSlot::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Card) Missing.Add(TEXT("Card"));
  if (!Ribbon) Missing.Add(TEXT("Ribbon"));
  if (!RibbonIcon) Missing.Add(TEXT("RibbonIcon"));
  if (!RibbonText) Missing.Add(TEXT("RibbonText"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

FString UUmHudSourceSlot::SourceName() const {
  return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName();
}

void UUmHudSourceSlot::SetClockOverrideMs(double Ms) {
  ClockOverrideMs = Ms;
  if (Card) Card->SetClockOverrideMs(Ms);
  for (US08AnimatedIconWidget* I : {RibbonIcon.Get(), BoostIcon.Get()}) {
    if (I) I->SetClockOverrideMs(Ms >= 0.0 ? static_cast<float>(Ms) : -1.0f);
  }
}

void UUmHudSourceSlot::SetSyncLoad(bool bOn) {
  if (Card) Card->SetSyncLoad(bOn);
}

double UUmHudSourceSlot::NowMs() const { return ClockOverrideMs >= 0.0 ? ClockOverrideMs : FPlatformTime::Seconds() * 1000.0; }

bool UUmHudSourceSlot::IsReduced() const {
  return ReducedOverride >= 0 ? ReducedOverride != 0 : S08IconMotion::IsReducedMotion();
}

void UUmHudSourceSlot::SetFrame(const FUmSlotFrame& InFrame) {
  if (bHasFrame && Frame == InFrame) return;
  Frame = InFrame;
  bHasFrame = true;
  if (bDrawn) {
    LaidRevision = 0;  // lay out again at the new size
    Layout();
    ApplyMotion();
  }
}

void UUmHudSourceSlot::ApplyModel(const FUmSlotModel& InModel) {
  Model = InModel;
  bHasModel = true;
  const bool bLive = InModel.bShow && InModel.Phase != EUmSlotPhase::Hidden;
  // the same card: the model's revision (a new card or the old one gone) and the card itself
  const bool bSameCard = bDrawn && InModel.Revision == Drawn.Revision && InModel.Seq == Drawn.Seq &&
                         InModel.Ribbon == Drawn.Ribbon && InModel.Card.InstanceId == Drawn.Card.InstanceId;
  // a new card (CUE-006 replace): a leave in flight ends now, the new one lays out
  if (bLive && InModel.Phase != EUmSlotPhase::Fade && !bSameCard) {
    LeaveStartMs = -1.0;
    LeaveAlphaNow = 1.0f;
    Drawn = InModel;
    bDrawn = true;
    SetVisibility(ESlateVisibility::HitTestInvisible);
    Layout();
    if (InModel.Phase != EUmSlotPhase::Fly) FlashLanded();  // no flight (reduced motion, a join): it lands now
  } else if (bSameCard && bLive && InModel.Phase != EUmSlotPhase::Fade) {
    // the same card moves on: fly -> hold -> show
    const bool bLanded = Drawn.Phase == EUmSlotPhase::Fly && InModel.Phase != EUmSlotPhase::Fly;
    Drawn.Phase = InModel.Phase;
    if (bLanded) FlashLanded();
    Drawn.FlyT = InModel.FlyT;
    Drawn.HoldFrac = InModel.HoldFrac;
  }
  // the card leaves (the model's fade, or it is gone): the widget's own 150 ms fade (04 §2.8)
  const bool bStillSame = bDrawn && InModel.Revision == Drawn.Revision && InModel.Seq == Drawn.Seq &&
                          InModel.Ribbon == Drawn.Ribbon && InModel.Card.InstanceId == Drawn.Card.InstanceId;
  if (bDrawn && LeaveStartMs < 0.0 && (!bLive || InModel.Phase == EUmSlotPhase::Fade || !bStillSame)) {
    LeaveStartMs = NowMs();
    Drawn.Phase = EUmSlotPhase::Show;
    Drawn.FlyT = 1.0f;
    Drawn.HoldFrac = -1.0f;
  }
  ApplyMotion();
}

void UUmHudSourceSlot::FlashLanded() {
  // VS-4 CP-21 (CUE-006): a played scheme lands in the slot - own (hand -> slot) and the opponent's (in the slot);
  // a boost or a discard is not a play
  if (!Card || Drawn.Ribbon != ES09SlotRibbon::Scheme || !Drawn.bFace) return;
  Card->PlayPlayedFlash(Drawn.SpeedMul);
  if (Card->GetFlashMs() > 0.0f) PlayedFlashes.Add(Card->GetFlashMs());
}

FBox2D UUmHudSourceSlot::CardRectSu() const {
  if (!bDrawn || IsLeaving() || !Frame.CardSu.bIsValid || GetPhase() == EUmSlotPhase::Fly) return FBox2D(ForceInit);
  return Frame.CardSu;
}

EUmSlotPhase UUmHudSourceSlot::GetPhase() const {
  if (!bDrawn) return EUmSlotPhase::Hidden;
  return IsLeaving() ? EUmSlotPhase::Fade : Drawn.Phase;
}

FBox2D UUmHudSourceSlot::RibbonRectSu() const {
  using namespace UmHudSourceSlot;
  if (!bDrawn || !Frame.CardSu.bIsValid) return FBox2D(ForceInit);
  const float W = RibbonWidthSu(Frame.bClassS, static_cast<float>(Frame.CardSu.GetSize().X), Drawn.Ribbon);
  const float Top = static_cast<float>(Frame.CardSu.Max.Y) + RibbonGapSu;
  const float H = RibbonHeightSu(RibbonRows, GlyphNow);
  return FBox2D(FVector2D(Frame.CardSu.Min.X, Top), FVector2D(Frame.CardSu.Min.X + W, Top + H));
}

FBox2D UUmHudSourceSlot::DrawnRectSu() const {
  if (!bDrawn || !Frame.CardSu.bIsValid) return FBox2D(ForceInit);
  FBox2D R = Frame.CardSu;
  if (GetPhase() != EUmSlotPhase::Fly) {
    const FBox2D Rib = RibbonRectSu();
    R += Rib;
    if (Drawn.HoldFrac >= 0.0f && GetPhase() == EUmSlotPhase::Hold) {
      R += FVector2D(Rib.Min.X, Rib.Max.Y + UmHudSourceSlot::HoldGapSu + UmHudSourceSlot::HoldBarSu);
    }
  }
  return R;
}

FBox2D UUmHudSourceSlot::PaintedRectSu() const {
  FBox2D R = DrawnRectSu();
  if (!R.bIsValid || !Card) return R;
  const FVector2D Off = Card->GetRenderTransform().Translation;
  if (!Off.IsNearlyZero()) R += FBox2D(Frame.CardSu.Min + Off, Frame.CardSu.Max + Off);
  return R;
}

void UUmHudSourceSlot::Layout() {
  using namespace UmHudSourceSlot;
  if (!bDrawn || !bHasFrame || !Frame.CardSu.bIsValid) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const float Px = Frame.PxPerSu > 0.0f ? Frame.PxPerSu : 1.0f;
  const FVector2D CardPos = FVector2D(Frame.CardSu.Min) - Frame.OriginSu;
  const FVector2D CardWH = Frame.CardSu.GetSize();
  // ---- the card: the scan face up (public), the owner's back otherwise; the show size of the class ----
  if (Card) {
    FUmCardState S;
    S.Show = Frame.bClassS ? EUmCardShow::ClassSHand : EUmCardShow::Slot;
    S.HeroSlug = Drawn.HeroSlug;
    S.bFaceDown = !Drawn.bFace;
    S.PxPerSu = Px;
    Card->ApplyModel(Drawn.Card, S);
    Card->SetBoostChip(UmCardWidget::NoBoostChip);  // the slot's «+N» is in its ribbon (ВР-VS2-HB34-16)
    Card->SetVisibility(ESlateVisibility::HitTestInvisible);
    UmSlPlace(Card, CardPos, CardWH, 1);
  }
  // ---- the ribbon ----
  GlyphNow = GlyphSu(Px);
  const bool bChip = Drawn.Ribbon == ES09SlotRibbon::Boosted && Drawn.Boost >= 0;
  const float W = RibbonWidthSu(Frame.bClassS, static_cast<float>(CardWH.X), Drawn.Ribbon);
  const float TextLeft = 2.0f + GlyphNow + 6.0f;
  const float TextRoom = W - TextLeft - (bChip ? GlyphNow + 8.0f : 4.0f);
  const FText Label = UmSlLabel(Drawn);
  RibbonRows = FMath::Max(1, UmHudStatus::WrapLines(Label.ToString(), FMath::Max(1.0f, TextRoom), 14.0f, [Px](const FString& T, float S) {
                                return UmHudPending::MeasureAtSu(T, S, FName(TEXT("type.tag")), Px) + 2.0f;
                              }));
  const FBox2D Rib = RibbonRectSu();
  const FVector2D RibPos = FVector2D(Rib.Min) - Frame.OriginSu;
  const FVector2D RibWH = Rib.GetSize();
  if (Ribbon) {
    // СХЕМА filled (card.type.scheme, navy 1 su edge), BOOST card.navy 0.92, СБРОС outline (text.secondary 2 su)
    FLinearColor Fill = Theme.Color(RibbonFill(Drawn.Ribbon));
    if (Drawn.Ribbon != ES09SlotRibbon::Scheme) Fill.A *= 0.92f;
    const float R = 6.0f;
    if (Drawn.Ribbon == ES09SlotRibbon::Scheme) {
      Ribbon->SetBrush(FSlateRoundedBoxBrush(Fill, R, Theme.Color(TEXT("card.navy")), 1.0f));
    } else if (Drawn.Ribbon == ES09SlotRibbon::Discarded) {
      Ribbon->SetBrush(FSlateRoundedBoxBrush(Fill, R, Theme.Color(TEXT("text.secondary")), 2.0f));
    } else {
      Ribbon->SetBrush(FSlateRoundedBoxBrush(Fill, R));
    }
    UmSlPlace(Ribbon, RibPos, RibWH, 2);
  }
  UmSlIcon(RibbonIcon, UmHudSourceSlot::RibbonIcon(Drawn.Ribbon), GlyphNow);
  UmSlPlace(RibbonIcon, RibPos + FVector2D(2.0f, 0.5f * (RibWH.Y - GlyphNow)), FVector2D(GlyphNow), 3);
  if (RibbonText) {
    RibbonText->SetText(Label);
    RibbonText->SetColorAndOpacity(FSlateColor(Theme.Color(RibbonInk(Drawn.Ribbon))));
    RibbonText->SetWrapTextAt(TextRoom);
    const float TextH = 14.0f + 18.0f * (RibbonRows - 1) + 4.0f;
    UmSlPlace(RibbonText, RibPos + FVector2D(TextLeft, 0.5f * (RibWH.Y - TextH)), FVector2D(TextRoom + 2.0f, TextH), 3);
  }
  if (BoostChip) {
    if (bChip) {
      UmSlIcon(BoostIcon, FName(TEXT("state-boost")), GlyphNow);
      if (BoostText) {
        FFormatNamedArguments A;
        A.Add(TEXT("n"), FText::AsNumber(Drawn.Boost));
        BoostText->SetText(UmText::Format(EUmTable::Hud, TEXT("hud.card.boost"), A));
        FSlateFontInfo Font = Theme.Font(TEXT("font.card"));
        Font.Size = UmHudTheme::PointsFromSu(12.0f * GlyphNow / 24.0f);
        BoostText->SetFont(Font);
      }
      UmSlPlace(BoostChip, RibPos + FVector2D(RibWH.X - 4.0f - GlyphNow, 0.5f * (RibWH.Y - GlyphNow)), FVector2D(GlyphNow), 4);
    }
  }
  if (HoldTrack) {
    FLinearColor Track = Theme.Color(TEXT("card.navy"));
    Track.A *= 0.92f;
    HoldTrack->SetBrush(FSlateRoundedBoxBrush(Track, 0.0f));
    UmSlPlace(HoldTrack, RibPos + FVector2D(0.0f, RibWH.Y + HoldGapSu), FVector2D(RibWH.X, HoldBarSu), 2);
  }
  if (HoldFill) HoldFill->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("card.glyph")), 0.0f));
  LaidRevision = Drawn.Revision;
  bLaidClassS = Frame.bClassS;
  LaidPx = Px;
}

void UUmHudSourceSlot::SetDecorShown(bool bOn) {
  UmSlShow(Ribbon, bOn);
  UmSlShow(RibbonIcon, bOn);
  UmSlShow(RibbonText, bOn);
  UmSlShow(BoostChip, bOn && Drawn.Ribbon == ES09SlotRibbon::Boosted && Drawn.Boost >= 0);
}

void UUmHudSourceSlot::ApplyMotion() {
  using namespace UmHudSourceSlot;
  if (!bDrawn) {
    if (GetVisibility() != ESlateVisibility::Collapsed) SetVisibility(ESlateVisibility::Collapsed);
    return;
  }
  // the leave: opacity 1 -> 0 over 150 ms (reduced 100), then nothing
  if (IsLeaving()) {
    LeaveAlphaNow = LeaveAlpha(static_cast<float>(NowMs() - LeaveStartMs), IsReduced());
    SetRenderOpacity(LeaveAlphaNow);
    if (LeaveAlphaNow <= 0.0f) {
      LeaveStartMs = -1.0;
      LeaveAlphaNow = 1.0f;
      bDrawn = false;
      SetRenderOpacity(1.0f);
      SetVisibility(ESlateVisibility::Collapsed);
      if (Card) Card->SetRenderTranslation(FVector2D::ZeroVector);
    }
  } else if (!FMath::IsNearlyEqual(GetRenderOpacity(), 1.0f)) {
    SetRenderOpacity(1.0f);
  }
  const EUmSlotPhase Phase = GetPhase();
  // the fly (ease-out, FS09SourceSlot::FlyT): from the hand / OPP-HAND to SLOT; the ribbon on arrival
  if (Card && bDrawn) {
    FVector2D Off = FVector2D::ZeroVector;
    if (Phase == EUmSlotPhase::Fly && !Drawn.FlyFromSu.IsZero() && Frame.CardSu.bIsValid) {
      Off = (Drawn.FlyFromSu - FVector2D(Frame.CardSu.GetCenter())) * (1.0f - FMath::Clamp(Drawn.FlyT, 0.0f, 1.0f));
    }
    if (!Card->GetRenderTransform().Translation.Equals(Off, 0.01)) Card->SetRenderTranslation(Off);
  }
  SetDecorShown(bDrawn && Phase != EUmSlotPhase::Fly);
  // the hold bar: 0 -> 1 over the 1500 ms before the opponent's scheme acts (ВР-VS2-HB34-17)
  const bool bHold = bDrawn && Phase == EUmSlotPhase::Hold && Drawn.HoldFrac >= 0.0f;
  UmSlShow(HoldTrack, bHold);
  UmSlShow(HoldFill, bHold);
  if (bHold && HoldFill) {
    const FBox2D Rib = RibbonRectSu();
    const FVector2D Pos = FVector2D(Rib.Min.X, Rib.Max.Y + HoldGapSu) - Frame.OriginSu;
    UmSlPlace(HoldFill, Pos, FVector2D(FMath::Clamp(Drawn.HoldFrac, 0.0f, 1.0f) * static_cast<float>(Rib.GetSize().X), HoldBarSu), 3);
  }
  const FString Name = PhaseName(Phase);
  if (Name != LastPhase) {
    LastPhase = Name;
    bPhaseChanged = true;
  }
}

FString UUmHudSourceSlot::TakeChangeLine() {
  if (!bPhaseChanged) return FString();
  bPhaseChanged = false;
  return FString::Printf(TEXT("HUD-SLOT-UMG phase=%s ribbon=%s owner=%s face=%d seq=%d"), *LastPhase,
                         bDrawn ? S09SlotRibbonName(Drawn.Ribbon) : TEXT("-"), bDrawn ? (Drawn.bOpponent ? TEXT("opp") : TEXT("own")) : TEXT("-"),
                         bDrawn && Drawn.bFace ? 1 : 0, bDrawn ? Drawn.Seq : -1);
}

void UUmHudSourceSlot::CollectShotLines(TArray<FString>& Out) const {
  if (!bDrawn) return;
  const float Px = Frame.PxPerSu > 0.0f ? Frame.PxPerSu : 1.0f;
  const FBox2D R = PaintedRectSu();
  FS08ScreenRect Rect;
  if (R.bIsValid) Rect = FS08ScreenRect(R.Min.X * Px, R.Min.Y * Px, R.Max.X * Px, R.Max.Y * Px);
  const bool bVisible = UmGameHudSlots::ShownByProperty(this) && R.bIsValid;
  const FBox2D Rib = RibbonRectSu();
  const EUmSlotPhase Phase = GetPhase();
  const FString Extra = FString::Printf(
      TEXT("ribbon=%s face=%d class=%s card=%.0fx%.0f ribbonSu=%.0fx%.0f rows=%d icon=%.0f chip=%d hold=%s alpha=%.2f seq=%d"),
      S09SlotRibbonName(Drawn.Ribbon), Drawn.bFace ? 1 : 0, Frame.bClassS ? TEXT("S") : TEXT("L"), Frame.CardSu.GetSize().X,
      Frame.CardSu.GetSize().Y, Rib.bIsValid ? Rib.GetSize().X : 0.0, Rib.bIsValid ? Rib.GetSize().Y : 0.0, RibbonRows, GlyphNow,
      Drawn.Ribbon == ES09SlotRibbon::Boosted && Drawn.Boost >= 0 ? 1 : 0,
      Phase == EUmSlotPhase::Hold && Drawn.HoldFrac >= 0.0f ? *FString::Printf(TEXT("%.2f"), Drawn.HoldFrac) : TEXT("-"), LeaveAlphaNow,
      Drawn.Seq);
  Out.Add(S08ArtHud::FormatWidgetLineEx(TEXT("UI-HUD-SLOT"), TEXT("umg"), UmHudSourceSlot::PhaseName(Phase),
                                        Drawn.bOpponent ? FString(TEXT("opp")) : FString(TEXT("own")), Rect, bVisible && !Rect.IsEmpty(),
                                        bVisible, SourceName(), Extra));
}

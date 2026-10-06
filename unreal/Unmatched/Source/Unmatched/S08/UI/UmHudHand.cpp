// VS-3 HB-24 / HB-25: HAND - see UmHudHand.h.
#include "UmHudHand.h"

#include "../../S09/S09HandLimit.h"
#include "../../S09/S09ManeuverUi.h"
#include "../S08AnimatedIconWidget.h"
#include "../S08BoardModel.h"
#include "../S08IconMotion.h"
#include "UmGameHud.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/SizeBox.h"
#include "Components/SizeBoxSlot.h"
#include "Components/TextBlock.h"
#include "HAL/PlatformTime.h"

const TCHAR* const UUmHudHand::WidgetBlueprintPath = TEXT("/Game/S08/UI/Hud/WBP_UI_HUD_HAND");

// ------------------------------------------------------------------------------------------------ models

bool FUmHandCardModel::operator==(const FUmHandCardModel& O) const {
  const FS09CardView& A = Card;
  const FS09CardView& B = O.Card;
  return A.InstanceId == B.InstanceId && A.CardId == B.CardId && A.Name == B.Name && A.NameRu == B.NameRu &&
         A.CardType == B.CardType && A.BoostValue == B.BoostValue && A.bHasBoostValue == B.bHasBoostValue &&
         A.BannerName == B.BannerName && A.bNew == B.bNew && A.bHidden == B.bHidden && bPlayable == O.bPlayable &&
         Reason.Key == O.Reason.Key && Reason.Args.OrderIndependentCompareEqual(O.Reason.Args) && bSelected == O.bSelected &&
         bCandidate == O.bCandidate && bMarked == O.bMarked && bBoostPlaced == O.bBoostPlaced;
}

bool FUmHandModel::operator==(const FUmHandModel& O) const {
  return Cards == O.Cards && HandMaxSize == O.HandMaxSize && HeroSlug == O.HeroSlug && Mode == O.Mode &&
         BoostSlot == O.BoostSlot && PlayTo == O.PlayTo && bLowered == O.bLowered && bStartHand == O.bStartHand &&
         bShow == O.bShow;
}

int32 FUmHandModel::RowCount() const {
  int32 N = 0;
  for (const FUmHandCardModel& C : Cards) N += C.bBoostPlaced ? 0 : 1;
  return N;
}

FUmHandFrame FUmHandFrame::FromLayout(const FUmHudLayout& L, float InSpeedMul) {
  FUmHandFrame F;
  F.CanvasSu = L.CanvasSu;
  F.PxPerSu = L.PxPerSu > 0.0f ? L.PxPerSu : 1.0f;
  F.bClassS = L.bClassS;
  F.CorridorLeftSu = L.HandLeftSu;
  F.CorridorRightSu = L.HandRightSu;
  F.VisibleSu = L.HandVisibleSu;
  F.bHasField = L.bHasField;
  F.FieldBottomSu = L.bHasField ? static_cast<float>(L.FieldSu.Max.Y) : 0.0f;
  FBox2D Slot = L.Rect(EUmHudBlock::Hand);
  if (Slot.bIsValid && L.Rect(EUmHudBlock::HandCaption).bIsValid) Slot += L.Rect(EUmHudBlock::HandCaption);
  F.SlotSu = Slot;
  F.SourceSlotSu = L.Rect(EUmHudBlock::SourceSlot);
  // COMBAT-L without its role ribbon: the card 230 x 319 (S 150 x 208) at the top of the block
  const FBox2D Combat = L.Rect(EUmHudBlock::CombatL);
  if (Combat.bIsValid) {
    const FVector2D Card = L.bClassS ? FVector2D(150.0, 208.0) : FVector2D(230.0, 319.0);
    F.CombatLSu = FBox2D(Combat.Min, Combat.Min + Card);
  }
  F.DeckChipSu = L.DeckChipCentreSu();
  F.DiscardChipSu = L.DiscardChipCentreSu();
  F.SpeedMul = FMath::Max(0.0f, InSpeedMul);
  return F;
}

bool FUmHandFrame::operator==(const FUmHandFrame& O) const {
  return CanvasSu.Equals(O.CanvasSu, 0.01) && PxPerSu == O.PxPerSu && bClassS == O.bClassS &&
         CorridorLeftSu == O.CorridorLeftSu && CorridorRightSu == O.CorridorRightSu && VisibleSu == O.VisibleSu &&
         bHasField == O.bHasField && FieldBottomSu == O.FieldBottomSu && SlotSu == O.SlotSu &&
         SourceSlotSu == O.SourceSlotSu && CombatLSu == O.CombatLSu && DeckChipSu.Equals(O.DeckChipSu, 0.01) &&
         DiscardChipSu.Equals(O.DiscardChipSu, 0.01) && SpeedMul == O.SpeedMul;
}

// ------------------------------------------------------------------------------------------------ the rules

namespace UmHudHand {
FRow Row(int32 N, const FUmHandFrame& F) {
  FRow R;
  R.CardSize = F.bClassS ? FVector2D(CardWS, CardHS) : FVector2D(CardWL, CardHL);
  const float W = static_cast<float>(R.CardSize.X);
  const float Nominal = F.bClassS ? StepS : StepL;
  const float CorrL = F.CorridorLeftSu;
  const float CorrR = FMath::Max(F.CorridorLeftSu, F.CorridorRightSu);
  const float Corridor = CorrR - CorrL;
  R.CardTopSu = static_cast<float>(F.CanvasSu.Y) - F.VisibleSu;
  R.StepSu = Nominal;
  if (N <= 0) {
    R.LeftSu = R.RightSu = 0.5f * (CorrL + CorrR);
    return R;
  }
  const float Full = W + Nominal * static_cast<float>(N - 1);
  float Left = CorrL;
  if (Full <= Corridor + 1.0e-3f) {
    // 04 §2.6 / HB-22 H3: centred in the corridor
    Left = CorrL + 0.5f * (Corridor - Full);
  } else {
    // a fan over the whole corridor; under 72 su only when the corridor cannot hold it (ВР-VS2-HB22-09)
    R.bFan = true;
    R.StepSu = N > 1 ? (Corridor - W) / static_cast<float>(N - 1) : Nominal;
    R.bBelowMin = R.StepSu < MinStepSu - 1.0e-3f;
  }
  for (int32 I = 0; I < N; ++I) R.CardPos.Add(FVector2D(Left + R.StepSu * static_cast<float>(I), R.CardTopSu));
  R.LeftSu = Left;
  R.RightSu = Left + W + R.StepSu * static_cast<float>(N - 1);
  return R;
}

EUmCardShow RowShow(const FUmHandFrame& F) { return F.bClassS ? EUmCardShow::ClassSHand : EUmCardShow::Hand; }

FBox2D HoverRect(const FVector2D& RestPos, const FUmHandFrame& F) {
  const FVector2D Rest = F.bClassS ? FVector2D(CardWS, CardHS) : FVector2D(CardWL, CardHL);
  const FVector2D Size = Rest * UmCardWidget::HoverScaleOf(RowShow(F));
  const double MaxX = FMath::Max(0.0, F.CanvasSu.X - Size.X);
  const double X = FMath::Clamp(RestPos.X + 0.5 * Rest.X - 0.5 * Size.X, 0.0, MaxX);
  const double Bottom = F.CanvasSu.Y - HoverBottomGapSu;
  return FBox2D(FVector2D(X, Bottom - Size.Y), FVector2D(X + Size.X, Bottom));
}

float SelectedRaiseFor(const FUmHandFrame& F) {
  if (!F.bHasField) return SelectedRaiseSu;
  // ВР-VS2-HB22-12: 32 su, never above the first protected pixel (FIELD)
  const float CardTop = static_cast<float>(F.CanvasSu.Y) - F.VisibleSu;
  return FMath::Clamp(CardTop - F.FieldBottomSu, 0.0f, SelectedRaiseSu);
}

float LowerDropSu(const FUmHandFrame& F) { return FMath::Max(0.0f, F.VisibleSu - LoweredVisibleSu); }

FBox2D BoostRect(EUmHandBoostSlot Slot, const FUmHandFrame& F) {
  if (Slot == EUmHandBoostSlot::Combat) {
    // ВР-VS2-HB22-11: the size of the attack card, 40 su (S 32) right of COMBAT-L, behind it
    FBox2D C = F.CombatLSu;
    if (!C.bIsValid) C = F.bClassS ? FBox2D(FVector2D(16.0, 240.0), FVector2D(166.0, 448.0))
                                   : FBox2D(FVector2D(24.0, 360.0), FVector2D(254.0, 679.0));
    const FVector2D Shift(F.bClassS ? BoostCombatShiftS : BoostCombatShiftL, 0.0);
    return FBox2D(C.Min + Shift, C.Max + Shift);
  }
  if (F.SourceSlotSu.bIsValid) return F.SourceSlotSu;
  return F.bClassS ? FBox2D(FVector2D(16.0, 64.0), FVector2D(136.0, 230.0)) : FBox2D(FVector2D(24.0, 84.0), FVector2D(214.0, 348.0));
}

EUmCardShow BoostShow(EUmHandBoostSlot Slot, const FUmHandFrame& F) {
  if (Slot == EUmHandBoostSlot::Combat) return F.bClassS ? EUmCardShow::ClassSCombat : EUmCardShow::Combat;
  return F.bClassS ? EUmCardShow::ClassSHand : EUmCardShow::Slot;
}

FBox2D RibbonRect(const FUmHandFrame& F) {
  const FBox2D S = BoostRect(EUmHandBoostSlot::Slot, F);
  return FBox2D(FVector2D(S.Min.X, S.Max.Y + RibbonGapSu), FVector2D(S.Max.X, S.Max.Y + RibbonGapSu + RibbonHSu));
}

float CascadeDelayMs(int32 Count) {
  if (Count <= 1) return 0.0f;
  return FMath::Min(CascadeMs, (CascadeMaxMs - DrawMs) / static_cast<float>(Count - 1));
}

FText Caption(int32 N, int32 Max) {
  FFormatNamedArguments A;
  A.Add(TEXT("n"), FText::AsNumber(N));
  A.Add(TEXT("max"), FText::AsNumber(Max));
  return UmText::Format(EUmTable::Hud, TEXT("hud.hand.count"), A);
}

const TCHAR* ModeName(EUmHandMode Mode) {
  switch (Mode) {
    case EUmHandMode::Discard: return TEXT("discard");
    case EUmHandMode::Boost: return TEXT("boost");
    default: return TEXT("rest");
  }
}

bool BannerAllows(const FString& Banner, const FString& FighterName) {
  const FString B = Banner.TrimStartAndEnd().ToLower();
  if (B.IsEmpty() || B == TEXT("any")) return true;
  const FString N = FighterName.ToLower();
  return N.Contains(B) || B.Contains(N);
}

FUmHandModel Gather(const FGatherIn& In) {
  FUmHandModel M;
  M.HeroSlug = In.HeroSlug;
  M.bLowered = In.bLowered;
  M.bStartHand = In.bStartHand;
  if (!In.Own || !In.Ui) {
    M.bShow = false;
    return M;
  }
  M.HandMaxSize = FS09HandLimitHint::LimitOf(In.Own->HandMaxSize);
  const FS09CommandUi& Ui = *In.Ui;
  const FS09DiscardPick Pick = FS09DiscardPick::From(Ui);
  const bool bBoostChoice = Ui.Mode == ES09CommandMode::PendingChoice && Ui.PendingChoice.Type == TEXT("BOOST_CHOICE");
  const bool bAbility = Ui.Mode == ES09CommandMode::AttackDraft && Ui.IsAttackAbilityPromptOpen();
  const bool bCombat = Ui.Combat.bPresent;
  if (Pick.IsOpen()) {
    M.Mode = EUmHandMode::Discard;
    M.PlayTo = EUmHandPlayTo::Discard;
  } else if (Ui.Mode == ES09CommandMode::ManeuverDraft) {
    M.Mode = EUmHandMode::Boost;
    M.BoostSlot = EUmHandBoostSlot::Slot;
  } else if (bAbility) {
    M.Mode = EUmHandMode::Boost;
    M.BoostSlot = EUmHandBoostSlot::Combat;
    M.PlayTo = EUmHandPlayTo::Combat;
  } else if (bBoostChoice) {
    M.Mode = EUmHandMode::Boost;
    M.BoostSlot = bCombat ? EUmHandBoostSlot::Combat : EUmHandBoostSlot::Slot;
    M.PlayTo = bCombat ? EUmHandPlayTo::Combat : EUmHandPlayTo::Slot;
  } else if (Ui.Mode == ES09CommandMode::AttackDraft || Ui.Mode == ES09CommandMode::CombatDefense || bCombat) {
    M.PlayTo = EUmHandPlayTo::Combat;
  }
  auto FighterName = [&In](const FString& Id) -> FString {
    if (Id.IsEmpty() || !In.Fighters) return FString();
    for (const FS08BoardFighter& F : *In.Fighters) {
      if (F.Id == Id) return F.Name;
    }
    return FString();
  };
  const FString Attacker = Ui.Mode == ES09CommandMode::AttackDraft && !bAbility ? FighterName(Ui.AttackAttackerId) : FString();
  const FString Defender = Ui.Mode == ES09CommandMode::CombatDefense ? FighterName(Ui.Combat.TargetFighterId) : FString();
  auto TypeIn = [](const FString& Type, std::initializer_list<const TCHAR*> Set) {
    for (const TCHAR* T : Set) {
      if (Type == T) return true;
    }
    return false;
  };
  auto Banner = [](const FS09CardView& Card) {
    return FS09Reason::Make(TEXT("why.banner.mismatch")).Arg(TEXT("bannerName"), Card.BannerName);
  };
  int32 Index = -1;
  for (const FS09CardView& Card : In.Own->Cards) {
    ++Index;
    if (Card.bHidden) continue;  // the own hand carries faces only; a placeholder is never drawn
    FUmHandCardModel C;
    C.Card = Card;
    const FString Type = Card.CardType.ToUpper();
    if (M.Mode == EUmHandMode::Discard) {
      // HB-25 (SD-43): every card a candidate, the picked ones marked
      const ES09HandMark Mark = Pick.Mark(Card.InstanceId, Card.bHidden);
      C.bCandidate = Mark != ES09HandMark::None;
      C.bMarked = Mark == ES09HandMark::Picked;
    } else if (M.Mode == EUmHandMode::Boost) {
      // HB-25: candidates carry a printed BOOST > 0; the attack card of King Arthur's prompt stays selected
      const bool bAttackCard = bAbility && Card.InstanceId == Ui.AttackCardId;
      const bool bHasBoost = Card.bHasBoostValue && Card.BoostValue > 0;
      if (bAttackCard) {
        C.bSelected = true;
      } else if (!bHasBoost) {
        C.bPlayable = false;
        C.Reason = FS09Reason::Make(TEXT("why.boost.no.value"));
      }
      const FString& Placed = Ui.Mode == ES09CommandMode::ManeuverDraft ? Ui.BoostCardId
                              : bAbility                                 ? Ui.AttackAbilityBoostCardId
                                                                         : FString();
      C.bBoostPlaced = !bAttackCard && bHasBoost &&
                       ((!Placed.IsEmpty() && Placed == Card.InstanceId) ||
                        (bBoostChoice && Ui.PendingCardIds.Contains(Card.InstanceId)));
    } else {
      switch (Ui.Mode) {
        case ES09CommandMode::AttackDraft: C.bSelected = !Ui.AttackCardId.IsEmpty() && Card.InstanceId == Ui.AttackCardId; break;
        case ES09CommandMode::CombatDefense: C.bSelected = !Ui.DefenseCardId.IsEmpty() && Card.InstanceId == Ui.DefenseCardId; break;
        case ES09CommandMode::SchemeChoice: C.bSelected = !Ui.SchemeCardId.IsEmpty() && Card.InstanceId == Ui.SchemeCardId; break;
        case ES09CommandMode::PendingChoice: C.bSelected = Ui.PendingCardIds.Contains(Card.InstanceId); break;
        default: C.bSelected = Index == In.InspectedIndex; break;
      }
      // the card step of a choice: what this card cannot be (type: no exact why key - dimmed only, ВР-VS3-19)
      if (!Attacker.IsEmpty()) {
        if (!TypeIn(Type, {TEXT("ATTACK"), TEXT("VERSATILE"), TEXT("UNIVERSAL")})) {
          C.bPlayable = false;
        } else if (!BannerAllows(Card.BannerName, Attacker)) {
          C.bPlayable = false;
          C.Reason = Banner(Card);
        }
      } else if (!Defender.IsEmpty()) {
        if (!TypeIn(Type, {TEXT("DEFENSE"), TEXT("VERSATILE"), TEXT("UNIVERSAL")})) {
          C.bPlayable = false;
        } else if (!BannerAllows(Card.BannerName, Defender)) {
          C.bPlayable = false;
          C.Reason = Banner(Card);
        }
      } else if (Ui.Mode == ES09CommandMode::SchemeChoice && In.Fighters) {
        if (Type != TEXT("SCHEME")) {
          C.bPlayable = false;
        } else if (!FS09CommandUi::SchemePlayableByLivingFighters(Card, *In.Fighters, In.ViewerId)) {
          C.bPlayable = false;
          C.Reason = Banner(Card);
        }
      }
    }
    M.Cards.Add(C);
  }
  return M;
}

FString KeyTarget(const FUmHandModel& Model, int32 Key) {
  return Key >= 1 && Model.Cards.IsValidIndex(Key - 1) ? Model.Cards[Key - 1].Card.InstanceId : FString();
}
}  // namespace UmHudHand

// ------------------------------------------------------------------------------------------------ tree

namespace {
template <typename T>
T* UmHandFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

/** The plate of the caption, the tooltip and the ribbon: panel.bg + panel.edge 1 su, radius.s (HB-22 caption). */
FSlateBrush UmHandPlate() {
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  return FSlateRoundedBoxBrush(Theme.Color(TEXT("panel.bg")), Theme.RadiusSu(TEXT("radius.s")), Theme.Color(TEXT("panel.edge")), 1.0f);
}

constexpr int32 ZRow = 10;
constexpr int32 ZPlaced = 60;
constexpr int32 ZRibbon = 70;
constexpr int32 ZCaption = 100;
constexpr int32 ZLeaving = 150;
constexpr int32 ZHover = 200;
constexpr int32 ZTooltip = 300;
}  // namespace

bool UUmHudHand::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  using namespace UmHudHand;
  UCanvasPanel* RowW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Row")));
  RowW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(RowW, nullptr)) return Fail(TEXT("Row"));
  // a plate (Border) > SizeBox of a fixed height > text, auto-sized in the canvas
  auto Plate = [&](const TCHAR* PlateName, const TCHAR* BoxName, const TCHAR* TextName, float HeightSu, bool bShown) -> bool {
    UBorder* P = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(PlateName));
    P->SetBrush(UmHandPlate());
    P->SetPadding(FMargin(CaptionPadSu, 0.0f));
    P->SetHorizontalAlignment(HAlign_Left);
    P->SetVerticalAlignment(VAlign_Center);
    P->SetVisibility(bShown ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    if (!Attach(P, RowW)) return Fail(PlateName);
    if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(P->Slot)) {
      S->SetAutoSize(true);
      S->SetAnchors(FAnchors(0.0f, 0.0f));
    }
    USizeBox* Box = Tree.ConstructWidget<USizeBox>(USizeBox::StaticClass(), FName(BoxName));
    Box->SetHeightOverride(HeightSu);
    if (!Attach(Box, P)) return Fail(BoxName);
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TextName));
    if (!Attach(T, Box)) return Fail(TextName);
    if (USizeBoxSlot* S = Cast<USizeBoxSlot>(T->Slot)) S->SetVerticalAlignment(VAlign_Center);
    return true;
  };
  if (!Plate(TEXT("CountPlate"), TEXT("CountBox"), TEXT("CountText"), CaptionSu, true)) return false;
  if (!Plate(TEXT("WhyPlate"), TEXT("WhyBox"), TEXT("WhyText"), TooltipHSu, false)) return false;
  // the BOOST ribbon under the own boost card in SLOT (HB-22: marker-status 24 su + «BOOST» type.tag)
  UBorder* Ribbon = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("BoostRibbon")));
  Ribbon->SetBrush(UmHandPlate());
  Ribbon->SetPadding(FMargin(2.0f, 2.0f, 8.0f, 2.0f));
  Ribbon->SetHorizontalAlignment(HAlign_Left);
  Ribbon->SetVerticalAlignment(VAlign_Center);
  Ribbon->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(Ribbon, RowW)) return Fail(TEXT("BoostRibbon"));
  UHorizontalBox* RibbonRow = Tree.ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), FName(TEXT("RibbonRow")));
  if (!Attach(RibbonRow, Ribbon)) return Fail(TEXT("RibbonRow"));
  US08AnimatedIconWidget* Icon = Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("RibbonIcon")));
  if (!Attach(Icon, RibbonRow)) return Fail(TEXT("RibbonIcon"));
  if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(Icon->Slot)) S->SetVerticalAlignment(VAlign_Center);
  UTextBlock* RibbonT = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("RibbonText")));
  if (!Attach(RibbonT, RibbonRow)) return Fail(TEXT("RibbonText"));
  if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(RibbonT->Slot)) {
    S->SetVerticalAlignment(VAlign_Center);
    S->SetPadding(FMargin(6.0f, 0.0f, 0.0f, 0.0f));
  }
  return true;
}

UClass* UUmHudHand::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmHudHand::StaticClass(), WidgetBlueprintPath); }

bool UUmHudHand::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD hand default tree: %s"), *Error);
  }
  Row = UmHandFind<UCanvasPanel>(WidgetTree, TEXT("Row"));
  CountText = UmHandFind<UTextBlock>(WidgetTree, TEXT("CountText"));
  CountPlate = UmHandFind<UBorder>(WidgetTree, TEXT("CountPlate"));
  WhyPlate = UmHandFind<UBorder>(WidgetTree, TEXT("WhyPlate"));
  WhyText = UmHandFind<UTextBlock>(WidgetTree, TEXT("WhyText"));
  BoostRibbon = UmHandFind<UBorder>(WidgetTree, TEXT("BoostRibbon"));
  RibbonIcon = UmHandFind<US08AnimatedIconWidget>(WidgetTree, TEXT("RibbonIcon"));
  RibbonText = UmHandFind<UTextBlock>(WidgetTree, TEXT("RibbonText"));
  // a WBP keeps neither the theme font (the default composite font) nor the code brush: set at run time
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const FSlateColor Primary(Theme.Color(TEXT("text.primary")));
  if (CountText) {
    CountText->SetFont(Theme.Font(TEXT("type.caption")));
    CountText->SetColorAndOpacity(Primary);
  }
  if (WhyText) {
    WhyText->SetFont(Theme.Font(TEXT("type.body")));
    WhyText->SetColorAndOpacity(Primary);
  }
  if (RibbonText) {
    RibbonText->SetFont(Theme.Font(TEXT("type.tag")));
    RibbonText->SetColorAndOpacity(Primary);
    RibbonText->SetText(UmText::Get(EUmTable::Hud, TEXT("hud.slot.boost")));
  }
  if (RibbonIcon && RibbonIcon->SetIcon(TEXT("marker-status"), 24.0f, 24)) {
    RibbonIcon->SetDisplaySizeSu(24.0f);
    RibbonIcon->ShowAtRest();
  }
  for (UBorder* P : {CountPlate.Get(), WhyPlate.Get(), BoostRibbon.Get()}) {
    if (P) P->SetBrush(UmHandPlate());
  }
  if (Row) Row->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  // the cards take the pointer, the hand only hears it (moves and the wheel bubble up from them)
  SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  return bFirst;
}

bool UUmHudHand::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Row) Missing.Add(TEXT("Row"));
  if (!CountText) Missing.Add(TEXT("CountText"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

FString UUmHudHand::SourceName() const { return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName(); }

// ------------------------------------------------------------------------------------------------ pool

bool UUmHudHand::IsReduced() const {
  return ReducedOverride >= 0 ? ReducedOverride == 1 : S08IconMotion::IsReducedMotion();
}

double UUmHudHand::NowMs() const {
  return ClockOverrideMs >= 0.0 ? ClockOverrideMs : FPlatformTime::Seconds() * 1000.0;
}

void UUmHudHand::EnsurePool(int32 Count) {
  if (!Row) return;
  while (Pool.Num() < Count) {
    UUmCardWidget* W = CreateWidget<UUmCardWidget>(this, UUmCardWidget::WidgetClass());
    if (!W) return;
    ++Created;
    if (ClockOverrideMs >= 0.0) W->SetClockOverrideMs(ClockOverrideMs);
    if (ReducedOverride >= 0) W->SetReducedForTest(ReducedOverride);
    if (LegacyOverride >= 0) W->SetLegacyForTest(LegacyOverride);
    W->SetSyncLoad(bSyncLoad);
    W->SetVisualHitTest(true);
    if (UCanvasPanelSlot* S = Row->AddChildToCanvas(W)) {
      S->SetAnchors(FAnchors(0.0f, 0.0f));
      S->SetAlignment(FVector2D::ZeroVector);
      S->SetAutoSize(false);
    }
    W->SetVisibility(ESlateVisibility::Collapsed);
    Pool.Add(W);
    Free.Add(W);
  }
}

void UUmHudHand::WireCard(UUmCardWidget* W, const FString& InstanceId) {
  if (!W) return;
  TWeakObjectPtr<UUmHudHand> WeakThis(this);
  W->SetPress(FName(*(TEXT("hand.") + InstanceId)), Arbiter,
              FS09OnHudPressOutcome::CreateWeakLambda(this, [this, InstanceId](const FS09HudPressOutcome& O) {
                if (OnPress) OnPress(O, InstanceId);
              }));
  W->SetOnInspect([WeakThis, InstanceId]() {
    if (UUmHudHand* Self = WeakThis.Get()) {
      if (Self->OnInspect) Self->OnInspect(InstanceId);
    }
  });
  W->SetOnDoubleClick([WeakThis, InstanceId]() {
    if (UUmHudHand* Self = WeakThis.Get()) {
      if (Self->OnPlay) Self->OnPlay(InstanceId);
    }
  });
}

UUmCardWidget* UUmHudHand::Acquire(const FString& InstanceId) {
  if (Free.Num() == 0) EnsurePool(Pool.Num() + 1);
  if (Free.Num() == 0) return nullptr;
  UUmCardWidget* W = Free.Pop();
  WireCard(W, InstanceId);
  W->SetVisibility(ESlateVisibility::Visible);
  W->SetRenderOpacity(1.0f);
  W->SetRenderTransform(FWidgetTransform());
  return W;
}

void UUmHudHand::Release(UUmCardWidget* W) {
  if (!W) return;
  W->SetVisibility(ESlateVisibility::Collapsed);
  W->SetHover(false);
  W->SetSelected(false);
  W->SetLowered(false);
  W->SetDiscardCandidate(false);
  W->SetMarkedForDiscard(false);
  W->SetBoostChip(UmCardWidget::NoBoostChip);
  W->SetChipRightAbove(false);
  W->SetNew(false);
  W->SetPlayable(true);
  if (W->IsFaceDown()) W->SetFaceDown(false, 0.0f);
  W->StartOwnerOffset(FVector2D::ZeroVector, FVector2D::ZeroVector, 0.0f);
  W->SetRenderOpacity(1.0f);
  W->SetRenderTransform(FWidgetTransform());
  Free.Add(W);
}

void UUmHudHand::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter,
                          TFunction<void(const FS09HudPressOutcome&, const FString&)> InOnPress,
                          TFunction<void(const FString&)> InOnInspect, TFunction<void(const FString&)> InOnPlay) {
  Arbiter = InArbiter;
  OnPress = MoveTemp(InOnPress);
  OnInspect = MoveTemp(InOnInspect);
  OnPlay = MoveTemp(InOnPlay);
  for (const TPair<FString, TObjectPtr<UUmCardWidget>>& L : Live) WireCard(L.Value, L.Key);
}

// ------------------------------------------------------------------------------------------------ model and layout

FUmCardState UUmHudHand::CardState(EUmCardShow Show) const {
  FUmCardState S;
  S.Show = Show;
  S.HeroSlug = Model.HeroSlug;
  S.PxPerSu = Frame.PxPerSu;
  return S;
}

FVector2D UUmHudHand::LocalOf(const FVector2D& CanvasSu) const {
  return Frame.SlotSu.bIsValid ? CanvasSu - Frame.SlotSu.Min : CanvasSu;
}

FVector2D UUmHudHand::ShowSizeOf(EUmCardShow Show) const { return UmCardWidget::ShowSize(Show); }

void UUmHudHand::PlaceCard(UUmCardWidget* W, const FVector2D& PosSu, const FVector2D& SizeSu, int32 Z) {
  if (!W) return;
  if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(W->Slot)) {
    const FVector2D Local = LocalOf(PosSu);
    if (!S->GetPosition().Equals(Local, 0.01)) S->SetPosition(Local);
    if (!S->GetSize().Equals(SizeSu, 0.01)) S->SetSize(SizeSu);
    if (S->GetZOrder() != Z) S->SetZOrder(Z);
  }
}

void UUmHudHand::SetFrame(const FUmHandFrame& InFrame) {
  if (bHasFrame && InFrame == Frame) return;
  Frame = InFrame;
  bHasFrame = true;
  // a new canvas: the lowering restarts from its end value, nothing flies
  LowerTo = Model.bLowered ? UmHudHand::LowerDropSu(Frame) : 0.0f;
  LowerNow = LowerFrom = LowerTo;
  LowerStartMs = -1.0;
  if (bHasModel) {
    Relayout(false);
    ApplyCardStates();
    ApplyOffsets(0.0f);
    Step();
  }
}

void UUmHudHand::ApplyModel(const FUmHandModel& InModel) {
  if (bHasModel && InModel == Model) return;
  const bool bFirst = !bHasModel;
  const FUmHandModel Old = Model;
  Model = InModel;
  bHasModel = true;
  EnsurePool(UmHudHand::PoolWarm);
  SetVisibility(Model.bShow ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Collapsed);
  const double Now = NowMs();
  const bool bReduced = IsReduced();
  // ---- the cards that left: CUE-006 flash, flight to where they went, fade (the placed boost fades in its slot)
  TSet<FString> Ids;
  for (const FUmHandCardModel& C : Model.Cards) Ids.Add(C.Card.InstanceId);
  for (auto It = Live.CreateIterator(); It; ++It) {
    if (Ids.Contains(It.Key())) continue;
    UUmCardWidget* W = It.Value();
    if (W) {
      W->SetVisibility(ESlateVisibility::HitTestInvisible);
      W->SetHover(false);
      W->PlayFlash();
      if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(W->Slot)) S->SetZOrder(ZLeaving);
      const bool bPlaced = PlacedNow.Contains(It.Key());
      if (!bPlaced && !bReduced && Frame.SpeedMul > 0.0f) {
        FVector2D To = Frame.SourceSlotSu.bIsValid ? Frame.SourceSlotSu.GetCenter() : FVector2D::ZeroVector;
        if (Old.PlayTo == EUmHandPlayTo::Combat && Frame.CombatLSu.bIsValid) To = Frame.CombatLSu.GetCenter();
        if (Old.PlayTo == EUmHandPlayTo::Discard) To = Frame.DiscardChipSu;
        FVector2D Centre = FVector2D::ZeroVector;
        if (const UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(W->Slot)) {
          Centre = S->GetPosition() + (Frame.SlotSu.bIsValid ? Frame.SlotSu.Min : FVector2D::ZeroVector) + 0.5 * S->GetSize();
        }
        W->SetOwnerOffset(To - Centre, UmHudHand::PlayMs * Frame.SpeedMul);
      }
      FLeaving L;
      L.W = W;
      L.StartMs = Now;
      L.DurMs = bReduced ? UmCardWidget::ReducedMs : FMath::Max(UmCardWidget::ReducedMs, UmHudHand::PlayMs * FMath::Max(Frame.SpeedMul, 0.2f));
      Leaving.Add(L);
    }
    PlacedNow.Remove(It.Key());
    It.RemoveCurrent();
  }
  // ---- the cards that came: one widget per instance id (UI-INP-007)
  TArray<FString> Arrived;
  for (const FUmHandCardModel& C : Model.Cards) {
    if (Live.Contains(C.Card.InstanceId)) continue;
    if (UUmCardWidget* W = Acquire(C.Card.InstanceId)) {
      Live.Add(C.Card.InstanceId, W);
      Arrived.Add(C.Card.InstanceId);
    }
  }
  // ---- the old canvas positions (the reflow and the boost flight start from them)
  TMap<FString, FVector2D> OldPos;
  for (const TPair<FString, TObjectPtr<UUmCardWidget>>& L : Live) {
    if (Arrived.Contains(L.Key)) continue;
    if (const UCanvasPanelSlot* S = L.Value ? Cast<UCanvasPanelSlot>(L.Value->Slot) : nullptr) OldPos.Add(L.Key, S->GetPosition());
  }
  Relayout(true);
  ApplyCardStates();
  // ---- the lowering (SD-26)
  const float Want = Model.bLowered ? UmHudHand::LowerDropSu(Frame) : 0.0f;
  if (!FMath::IsNearlyEqual(Want, LowerTo, 0.01f)) {
    LowerFrom = LowerNow;
    LowerTo = Want;
    LowerStartMs = bReduced ? -1.0 : Now;
    if (bReduced) LowerNow = LowerTo;
  }
  // ---- the targets (hover lift / selected raise) and the flights
  ApplyOffsets(UUmHudTheme::Get().Ms(TEXT("hover.ms")));
  const float Speed = Frame.SpeedMul;
  const float Cascade = UmHudHand::CascadeDelayMs(Arrived.Num()) * Speed;
  int32 K = 0;
  for (const FString& Id : Arrived) {
    UUmCardWidget* W = Live.FindRef(Id);
    const int32 I = IndexOf(Id);
    if (!W || I < 0) continue;
    // CUE-005: from the deck chip of DECKS (not on the first model: a join shows the hand at rest; the starting hand
    // of the match cascades in, SD-01)
    if (bFirst && !Model.bStartHand) continue;
    if (Model.Cards[I].bBoostPlaced || Speed <= 0.0f || bReduced) continue;
    const FBox2D Rest = RestRectSu(I);
    if (!Rest.bIsValid || Frame.DeckChipSu.IsZero()) continue;
    const FVector2D From = Frame.DeckChipSu - Rest.GetCenter();
    W->StartOwnerOffset(From, W->GetOwnerOffsetTarget(), UmHudHand::DrawMs * Speed, bFirst ? Cascade * K : 0.0);
    ++K;
  }
  // ---- the reflow: a card that moved (a card left before it, a boost went into / out of its slot) slides
  for (const TPair<FString, FVector2D>& P : OldPos) {
    UUmCardWidget* W = Live.FindRef(P.Key);
    const UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr;
    if (!S || S->GetPosition().Equals(P.Value, 0.01)) continue;
    const int32 I = IndexOf(P.Key);
    const bool bPlacedChange = I >= 0 && (Model.Cards[I].bBoostPlaced != (Old.Cards.ContainsByPredicate([&P](const FUmHandCardModel& C) {
                                            return C.Card.InstanceId == P.Key && C.bBoostPlaced;
                                          })));
    const float Ms = bPlacedChange ? UmHudHand::BoostMs : UUmHudTheme::Get().Ms(TEXT("hover.ms"));
    W->StartOwnerOffset(P.Value - S->GetPosition() + W->GetOwnerOffset(), W->GetOwnerOffsetTarget(), Ms * FMath::Max(Speed, 0.0f));
  }
  ApplyCaption();
  ApplyTooltip();
  ApplyRibbon();
  Step();
}

int32 UUmHudHand::IndexOf(const FString& InstanceId) const {
  for (int32 I = 0; I < Model.Cards.Num(); ++I) {
    if (Model.Cards[I].Card.InstanceId == InstanceId) return I;
  }
  return INDEX_NONE;
}

UUmCardWidget* UUmHudHand::FindCard(const FString& InstanceId) const { return Live.FindRef(InstanceId); }

FBox2D UUmHudHand::RestRectSu(int32 I) const {
  if (!RowIndex.IsValidIndex(I) || RowIndex[I] < 0 || !RowNow.CardPos.IsValidIndex(RowIndex[I])) return FBox2D(ForceInit);
  const FVector2D P = RowNow.CardPos[RowIndex[I]];
  return FBox2D(P, P + RowNow.CardSize);
}

void UUmHudHand::Relayout(bool bAnimate) {
  (void)bAnimate;
  TArray<int32> Members;
  for (int32 I = 0; I < Model.Cards.Num(); ++I) {
    if (!Model.Cards[I].bBoostPlaced) Members.Add(I);
  }
  RowNow = UmHudHand::Row(Members.Num(), Frame);
  RowIndex.Init(INDEX_NONE, Model.Cards.Num());
  for (int32 K = 0; K < Members.Num(); ++K) RowIndex[Members[K]] = K;
  if (HoverIndex != INDEX_NONE && (!RowIndex.IsValidIndex(HoverIndex) || RowIndex[HoverIndex] < 0)) HoverIndex = INDEX_NONE;
  const EUmCardShow RowShowNow = UmHudHand::RowShow(Frame);
  const EUmCardShow BoostShowNow = UmHudHand::BoostShow(Model.BoostSlot, Frame);
  const FBox2D Boost = UmHudHand::BoostRect(Model.BoostSlot, Frame);
  TSet<FString> Placed;
  for (int32 I = 0; I < Model.Cards.Num(); ++I) {
    const FUmHandCardModel& C = Model.Cards[I];
    UUmCardWidget* W = Live.FindRef(C.Card.InstanceId);
    if (!W) continue;
    if (C.bBoostPlaced) {
      Placed.Add(C.Card.InstanceId);
      W->ApplyModel(C.Card, CardState(BoostShowNow));
      PlaceCard(W, Boost.Min, ShowSizeOf(BoostShowNow), ZPlaced);
      W->SetRenderTransform(FWidgetTransform());  // the slot does not go down with the row
    } else {
      W->ApplyModel(C.Card, CardState(RowShowNow));
      PlaceCard(W, RowNow.CardPos[RowIndex[I]], RowNow.CardSize, I == HoverIndex ? ZHover : ZRow + RowIndex[I]);
    }
  }
  PlacedNow = MoveTemp(Placed);
}

void UUmHudHand::ApplyCardStates() {
  const double Now = NowMs();
  for (int32 I = 0; I < Model.Cards.Num(); ++I) {
    const FUmHandCardModel& C = Model.Cards[I];
    UUmCardWidget* W = Live.FindRef(C.Card.InstanceId);
    if (!W) continue;
    const FString& Id = C.Card.InstanceId;
    W->SetPlayable(C.bPlayable, C.Reason);
    // the new dot: until the first hover or 10 s (04 §2.6)
    bool bNewDot = false;
    if (C.Card.bNew && !NewDone.Contains(Id)) {
      const double Since = NewSinceMs.FindOrAdd(Id, Now);
      bNewDot = Now - Since < UmHudHand::NewDotMs;
      if (!bNewDot) NewDone.Add(Id);
    }
    W->SetNew(bNewDot);
    W->SetSelected(C.bSelected);
    W->SetDiscardCandidate(C.bCandidate);
    W->SetMarkedForDiscard(C.bMarked);
    W->SetLowered(Model.bLowered && !C.bBoostPlaced);
    W->SetHover(I == HoverIndex && !C.bBoostPlaced);
    // HB-25 / CP-18: the boost card turns face down (the face stays in the own widget) and carries "+N"
    if (C.bBoostPlaced) {
      W->SetChipRightAbove(Model.BoostSlot == EUmHandBoostSlot::Combat);
      if (!W->IsFaceDown()) W->SetFaceDown(true);
      W->SetBoostChip(C.Card.BoostValue);
    } else {
      if (W->IsFaceDown()) W->SetFaceDown(false);
      W->SetBoostChip(UmCardWidget::NoBoostChip);
      W->SetChipRightAbove(false);
    }
    if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(W->Slot)) {
      const int32 Z = C.bBoostPlaced ? ZPlaced : (I == HoverIndex ? ZHover : ZRow + (RowIndex.IsValidIndex(I) ? RowIndex[I] : 0));
      if (S->GetZOrder() != Z) S->SetZOrder(Z);
    }
  }
}

void UUmHudHand::ApplyOffsets(float DurMs) {
  const float Raise = UmHudHand::SelectedRaiseFor(Frame);
  for (int32 I = 0; I < Model.Cards.Num(); ++I) {
    const FUmHandCardModel& C = Model.Cards[I];
    UUmCardWidget* W = Live.FindRef(C.Card.InstanceId);
    if (!W || C.bBoostPlaced) continue;
    FVector2D Target = FVector2D::ZeroVector;
    const FBox2D Rest = RestRectSu(I);
    if (I == HoverIndex && !Model.bLowered && Rest.bIsValid) {
      // CP-17 scales the drawn card about its bottom centre; the hand moves that bottom to 24 su over the canvas bottom
      const FBox2D Hover = UmHudHand::HoverRect(Rest.Min, Frame);
      Target = FVector2D(Hover.GetCenter().X - Rest.GetCenter().X, Hover.Max.Y - Rest.Max.Y);
    } else if (C.bSelected && !Model.bLowered) {
      Target = FVector2D(0.0, -Raise);
    }
    W->SetOwnerOffset(Target, DurMs);
  }
}

bool UUmHudHand::IsCaptionShown() const {
  return CountPlate ? CountPlate->GetVisibility() != ESlateVisibility::Collapsed : CountText && CountText->GetVisibility() != ESlateVisibility::Collapsed;
}

FBox2D UUmHudHand::CaptionRectSu() const {
  const float Top = RowNow.CardTopSu - UmHudHand::CaptionSu;
  float W = 0.0f;
  if (CountPlate) W = static_cast<float>(CountPlate->GetDesiredSize().X);
  if (W <= 0.0f) W = 2.0f * UmHudHand::CaptionPadSu + 60.0f;  // before the first prepass: the plate of «Рука n/7»
  const float Left = Model.RowCount() > 0 ? RowNow.LeftSu : RowNow.LeftSu - 0.5f * W;
  return FBox2D(FVector2D(Left, Top), FVector2D(Left + W, Top + UmHudHand::CaptionSu));
}

void UUmHudHand::ApplyCaption() {
  const int32 N = Model.RowCount();
  if (CountText) CountText->SetText(UmHudHand::Caption(N, Model.HandMaxSize));
  UWidget* PlateW = CountPlate ? static_cast<UWidget*>(CountPlate) : static_cast<UWidget*>(CountText);
  if (!PlateW) return;
  // ВР-VS2-HB22-10: one plate at the left edge of the first card in every state, hidden while the hand is lowered
  const bool bShown = Model.bShow && !Model.bLowered;
  PlateW->SetVisibility(bShown ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(PlateW->Slot)) {
    const bool bEmpty = N == 0;
    S->SetAutoSize(true);
    S->SetAlignment(FVector2D(bEmpty ? 0.5 : 0.0, 0.0));
    S->SetPosition(LocalOf(FVector2D(RowNow.LeftSu, RowNow.CardTopSu - UmHudHand::CaptionSu)));
    S->SetZOrder(ZCaption);
  }
}

bool UUmHudHand::IsTooltipShown() const { return WhyPlate && WhyPlate->GetVisibility() != ESlateVisibility::Collapsed; }

FText UUmHudHand::GetTooltipText() const { return WhyText ? WhyText->GetText() : FText::GetEmpty(); }

void UUmHudHand::ApplyTooltip() {
  if (!WhyPlate || !WhyText) return;
  // 04 §2.6: the why.* of an unplayable card while it is hovered, on its own plate over the drawn card
  FText Why;
  FBox2D Over(ForceInit);
  if (Model.Cards.IsValidIndex(HoverIndex)) {
    if (const UUmCardWidget* W = Live.FindRef(Model.Cards[HoverIndex].Card.InstanceId)) Why = W->GetWhyText();
    const FBox2D Rest = RestRectSu(HoverIndex);
    if (Rest.bIsValid) {
      Over = Model.bLowered ? FBox2D(Rest.Min + FVector2D(0.0, LowerTo), Rest.Max + FVector2D(0.0, LowerTo))
                            : UmHudHand::HoverRect(Rest.Min, Frame);
    }
  }
  const bool bShow = !Why.IsEmpty() && Over.bIsValid && Model.bShow;
  WhyPlate->SetVisibility(bShow ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  if (!bShow) return;
  WhyText->SetText(Why);
  if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(WhyPlate->Slot)) {
    S->SetAutoSize(true);
    S->SetAlignment(FVector2D(0.5, 1.0));
    S->SetPosition(LocalOf(FVector2D(Over.GetCenter().X, Over.Min.Y - UmHudHand::TooltipGapSu)));
    S->SetZOrder(ZTooltip);
  }
}

void UUmHudHand::ApplyRibbon() {
  if (!BoostRibbon) return;
  // HB-22: the BOOST ribbon under the own boost card in SLOT (the source slot block, H10, owns it later)
  bool bSlotBoost = false;
  for (const FUmHandCardModel& C : Model.Cards) bSlotBoost |= C.bBoostPlaced && Model.BoostSlot == EUmHandBoostSlot::Slot;
  BoostRibbon->SetVisibility(bSlotBoost && Model.bShow ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  if (!bSlotBoost) return;
  const FBox2D R = UmHudHand::RibbonRect(Frame);
  if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(BoostRibbon->Slot)) {
    S->SetAutoSize(false);
    S->SetPosition(LocalOf(R.Min));
    S->SetSize(R.GetSize());
    S->SetZOrder(ZRibbon);
  }
}

// ------------------------------------------------------------------------------------------------ hover and input

void UUmHudHand::SetHoverIndex(int32 Index) {
  if (Index != INDEX_NONE && (!RowIndex.IsValidIndex(Index) || RowIndex[Index] < 0)) Index = INDEX_NONE;
  if (Index == HoverIndex) return;
  HoverIndex = Index;
  if (Model.Cards.IsValidIndex(Index)) NewDone.Add(Model.Cards[Index].Card.InstanceId);  // the dot leaves on the first hover
  ApplyCardStates();
  ApplyOffsets(UUmHudTheme::Get().Ms(TEXT("hover.ms")));
  ApplyTooltip();
  Step();
}

void UUmHudHand::ClearHover() {
  WheelIndex = INDEX_NONE;
  SetHoverIndex(INDEX_NONE);
}

void UUmHudHand::HoverAtSu(const FVector2D& P) {
  WheelIndex = INDEX_NONE;
  int32 Hit = INDEX_NONE;
  const int32 N = RowNow.CardPos.Num();
  // the strips of the resting row (and the raise of a selected card over it): the card under the pointer by x, so
  // the hovered card that rises never takes its neighbour's strip and never flickers away from its own
  const float Top = RowNow.CardTopSu + LowerNow - UmHudHand::SelectedRaiseFor(Frame);
  if (N > 0 && P.Y >= Top && P.Y <= Frame.CanvasSu.Y + 1.0) {
    for (int32 K = 0; K < N; ++K) {
      const float X0 = static_cast<float>(RowNow.CardPos[K].X);
      const float X1 = K + 1 < N ? static_cast<float>(RowNow.CardPos[K + 1].X) : X0 + static_cast<float>(RowNow.CardSize.X);
      if (P.X >= X0 && P.X < X1) {
        Hit = RowIndex.IndexOfByKey(K);
        break;
      }
    }
  }
  if (Hit == INDEX_NONE && Model.Cards.IsValidIndex(HoverIndex) && !Model.bLowered) {
    // over the raised preview of the hovered card: it stays
    const FBox2D Rest = RestRectSu(HoverIndex);
    if (Rest.bIsValid && UmHudHand::HoverRect(Rest.Min, Frame).IsInside(P)) Hit = HoverIndex;
  }
  SetHoverIndex(Hit);
}

FReply UUmHudHand::NativeOnMouseMove(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  const FVector2D Local = InGeometry.AbsoluteToLocal(InMouseEvent.GetScreenSpacePosition());
  HoverAtSu(Local + (Frame.SlotSu.bIsValid ? Frame.SlotSu.Min : FVector2D::ZeroVector));
  return FReply::Unhandled();
}

void UUmHudHand::NativeOnMouseEnter(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  Super::NativeOnMouseEnter(InGeometry, InMouseEvent);
  const FVector2D Local = InGeometry.AbsoluteToLocal(InMouseEvent.GetScreenSpacePosition());
  HoverAtSu(Local + (Frame.SlotSu.bIsValid ? Frame.SlotSu.Min : FVector2D::ZeroVector));
}

void UUmHudHand::NativeOnMouseLeave(const FPointerEvent& InMouseEvent) {
  Super::NativeOnMouseLeave(InMouseEvent);
  ClearHover();
}

FReply UUmHudHand::NativeOnMouseWheel(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  return WheelStep(InMouseEvent.GetWheelDelta() < 0.0f) ? FReply::Handled() : FReply::Unhandled();
}

bool UUmHudHand::WheelStep(bool bForward) {
  // 04 §2.6 / ВР-VS2-HB22-09: the wheel over the hand browses the fan (the preview walks along the row)
  TArray<int32> Order;
  for (int32 I = 0; I < RowIndex.Num(); ++I) {
    if (RowIndex[I] >= 0) Order.Add(I);
  }
  if (Order.Num() == 0 || Model.bLowered) return false;
  Order.Sort([this](int32 A, int32 B) { return RowIndex[A] < RowIndex[B]; });
  const int32 Base = WheelIndex != INDEX_NONE ? WheelIndex : HoverIndex;
  int32 Pos = Order.IndexOfByKey(Base);
  Pos = Pos == INDEX_NONE ? (bForward ? 0 : Order.Num() - 1) : FMath::Clamp(Pos + (bForward ? 1 : -1), 0, Order.Num() - 1);
  SetHoverIndex(Order[Pos]);
  WheelIndex = Order[Pos];
  return true;
}

// ------------------------------------------------------------------------------------------------ the step

void UUmHudHand::StepHand(double Now) {
  // the lowering of the row (150 ms ease out quad): the row cards move with their hit rectangles; the boost slot stays
  if (LowerStartMs >= 0.0) {
    const float A = FMath::Clamp(static_cast<float>((Now - LowerStartMs) / UmHudHand::LowerMs), 0.0f, 1.0f);
    LowerNow = FMath::Lerp(LowerFrom, LowerTo, S08IconMotion::Ease(ES08IconEase::EaseOutQuad, A));
    if (A >= 1.0f) LowerStartMs = -1.0;
  } else {
    LowerNow = LowerTo;
  }
  for (const FUmHandCardModel& C : Model.Cards) {
    UUmCardWidget* W = Live.FindRef(C.Card.InstanceId);
    if (!W || C.bBoostPlaced) continue;
    const FVector2D Want(0.0, LowerNow);
    if (!W->GetRenderTransform().Translation.Equals(Want, 1.0e-3)) {
      W->SetRenderTransform(FWidgetTransform(Want, FVector2D(1.0, 1.0), FVector2D::ZeroVector, 0.0f));
    }
  }
  // the new dots time out (10 s)
  for (const FUmHandCardModel& C : Model.Cards) {
    if (!C.Card.bNew || NewDone.Contains(C.Card.InstanceId)) continue;
    const double* Since = NewSinceMs.Find(C.Card.InstanceId);
    if (Since && Now - *Since >= UmHudHand::NewDotMs) {
      NewDone.Add(C.Card.InstanceId);
      if (UUmCardWidget* W = Live.FindRef(C.Card.InstanceId)) W->SetNew(false);
    }
  }
  // the cards that left fade out, then go back to the pool
  for (int32 I = Leaving.Num() - 1; I >= 0; --I) {
    UUmCardWidget* W = Leaving[I].W.Get();
    const float T = static_cast<float>(Now - Leaving[I].StartMs);
    if (!W || T >= Leaving[I].DurMs) {
      if (W) Release(W);
      Leaving.RemoveAt(I);
      continue;
    }
    W->SetRenderOpacity(1.0f - T / Leaving[I].DurMs);
  }
}

bool UUmHudHand::NeedsHandStep() const {
  if (LowerStartMs >= 0.0 || Leaving.Num() > 0) return true;
  for (const FUmHandCardModel& C : Model.Cards) {
    if (C.Card.bNew && !NewDone.Contains(C.Card.InstanceId)) return true;
  }
  return false;
}

void UUmHudHand::Step() {
  StepHand(NowMs());
  for (const TObjectPtr<UUmCardWidget>& W : Pool) {
    if (W && W->GetVisibility() != ESlateVisibility::Collapsed) {
      if (ClockOverrideMs >= 0.0) W->SetClockOverrideMs(ClockOverrideMs);
      W->Step();
    }
  }
}

void UUmHudHand::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  // the hand's own tweens only; the cards step themselves (UUmCardWidget::NativeTick)
  if (NeedsHandStep()) StepHand(NowMs());
}

// ------------------------------------------------------------------------------------------------ tests / sheet hooks

void UUmHudHand::SetClockOverrideMs(double Ms) {
  ClockOverrideMs = Ms;
  for (const TObjectPtr<UUmCardWidget>& W : Pool) {
    if (W) W->SetClockOverrideMs(Ms);
  }
}

void UUmHudHand::SetReducedForTest(int32 InReduced) {
  ReducedOverride = InReduced;
  for (const TObjectPtr<UUmCardWidget>& W : Pool) {
    if (W) W->SetReducedForTest(InReduced);
  }
}

void UUmHudHand::SetLegacyForTest(int32 InLegacy) {
  LegacyOverride = InLegacy;
  for (const TObjectPtr<UUmCardWidget>& W : Pool) {
    if (W) W->SetLegacyForTest(InLegacy);
  }
}

void UUmHudHand::SetSyncLoad(bool bOn) {
  bSyncLoad = bOn;
  for (const TObjectPtr<UUmCardWidget>& W : Pool) {
    if (W) W->SetSyncLoad(bOn);
  }
}

// ------------------------------------------------------------------------------------------------ trace

FString UUmHudHand::StateName() const {
  bool bSelected = false;
  for (const FUmHandCardModel& C : Model.Cards) bSelected |= C.bSelected && !C.bBoostPlaced;
  if (Model.Cards.Num() == 0) return TEXT("empty");
  if (Model.bLowered) return TEXT("lowered");
  if (Model.Mode == EUmHandMode::Discard) return TEXT("discard");
  if (HoverIndex != INDEX_NONE) return TEXT("hover");
  if (bSelected) return TEXT("selected");
  return TEXT("rest");
}

FBox2D UUmHudHand::DrawnRectSu() const {
  FBox2D Out(ForceInit);
  const double Bottom = Frame.CanvasSu.Y;
  for (const FVector2D& P : RowNow.CardPos) {
    const FVector2D Min(P.X, P.Y + LowerNow);
    const FVector2D Max(P.X + RowNow.CardSize.X, FMath::Min(Bottom, P.Y + LowerNow + RowNow.CardSize.Y));
    if (Max.Y > Min.Y) Out += FBox2D(Min, Max);
  }
  if (IsCaptionShown()) Out += CaptionRectSu();
  return Out;
}

void UUmHudHand::CollectShotLines(TArray<FString>& Out) const {
  const bool bVisible = bHasModel && UmGameHudSlots::ShownByProperty(this);
  const FBox2D Su = DrawnRectSu();
  const float Px = Frame.PxPerSu > 0.0f ? Frame.PxPerSu : 1.0f;
  FS08ScreenRect Rect;
  if (Su.bIsValid) Rect = FS08ScreenRect(Su.Min.X * Px, Su.Min.Y * Px, Su.Max.X * Px, Su.Max.Y * Px);
  float ScaleMax = 0.0f;
  int32 Fallback = 0, Marked = 0, Selected = 0;
  bool bPlaced = false;
  for (const FUmHandCardModel& C : Model.Cards) {
    Marked += C.bMarked ? 1 : 0;
    Selected += C.bSelected ? 1 : 0;
    bPlaced |= C.bBoostPlaced;
    if (const UUmCardWidget* W = Live.FindRef(C.Card.InstanceId)) {
      ScaleMax = FMath::Max(ScaleMax, W->GetFit().Scale * W->GetScale());
      Fallback += W->GetFace() == EUmCardFace::Fallback ? 1 : 0;
    }
  }
  const FString Extra = FString::Printf(
      TEXT("n=%d max=%d mode=%s step=%.1f fan=%d below72=%d rowVisible=%.0f placed=%d selected=%d marked=%d hoverIdx=%d "
           "scaleMax=%.3f fallback=%d pool=%d created=%d"),
      Model.RowCount(), Model.HandMaxSize, UmHudHand::ModeName(Model.Mode), RowNow.StepSu, RowNow.bFan ? 1 : 0,
      RowNow.bBelowMin ? 1 : 0, FMath::Max(0.0f, Frame.VisibleSu - LowerNow), bPlaced ? 1 : 0, Selected, Marked, HoverIndex,
      ScaleMax, Fallback, Pool.Num(), Created);
  Out.Add(S08ArtHud::FormatWidgetLineEx(TEXT("UI-HUD-HAND"), TEXT("umg"), *StateName(), FString(), Rect,
                                        bVisible && !Rect.IsEmpty(), bVisible, SourceName(), Extra));
  if (!bVisible) return;
  // per card: what the scan draws - no key, no name, no value (ВР-VS3-21)
  for (int32 I = 0; I < Model.Cards.Num(); ++I) {
    const UUmCardWidget* W = Live.FindRef(Model.Cards[I].Card.InstanceId);
    if (!W) continue;
    const FUmCardFit& F = W->GetFit();
    const float CardPx = W->GetPxPerSu();
    Out.Add(FString::Printf(TEXT("HUD-HAND card=%d lang=%s show=%s su=%.0fx%.0f px=%.0fx%.0f scale=%.3f capped=%d state=%s"), I,
                            UmCardWidget::FaceName(W->GetFace()), UmCardWidget::ShowName(W->GetState().Show), F.CardSu.X,
                            F.CardSu.Y, F.ScanSu.X * CardPx * W->GetScale(), F.ScanSu.Y * CardPx * W->GetScale(),
                            F.Scale * W->GetScale(), F.bCapped ? 1 : 0, *W->StateText()));
  }
}

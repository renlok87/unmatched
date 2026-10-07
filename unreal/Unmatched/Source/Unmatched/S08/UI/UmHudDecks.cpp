// VS-3 HB-27: DECKS - see UmHudDecks.h.
#include "UmHudDecks.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08ArtHud.h"
#include "../S08IconMotion.h"
#include "UmButton.h"
#include "UmCardWidget.h"
#include "UmGameHud.h"
#include "UmHudLayout.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/ScaleBox.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"

const TCHAR* const UUmHudDecks::WidgetBlueprintPath = TEXT("/Game/S08/UI/Hud/WBP_UI_HUD_DECKS");

namespace UmHudDecks {
FUmDecksModel Gather(const FS09PlayerPanel* Own, const FString& HeroSlug) {
  FUmDecksModel M;
  if (!Own) return M;
  M.bShow = true;
  M.DeckCount = Own->DeckCount;
  M.bDeckStale = Own->bDeckCountStale;
  M.DiscardCount = Own->Discard.Num();
  M.bDiscardStale = Own->bDiscardStale;
  M.HeroSlug = HeroSlug;
  // the public pile is delivered oldest first: the top is the last entry
  if (Own->Discard.Num() > 0) {
    M.bHasTop = true;
    M.Top = Own->Discard.Last();
  }
  return M;
}

namespace {
FText Count(int32 N, bool bStale) {
  const FText Num = FText::FromString(FString::FromInt(N));  // tabular digits, no grouping
  if (!bStale) return Num;
  FFormatNamedArguments A;
  A.Add(TEXT("n"), Num);
  return UmText::Format(EUmTable::Hud, TEXT("hud.decks.stale"), A);
}

FText Label(const TCHAR* Key, int32 N, bool bStale, bool bClassS) {
  const FText Num = Count(N, bStale);
  if (bClassS) return Num;  // class S: the number only (04 §2.9)
  FFormatNamedArguments A;
  A.Add(TEXT("n"), Num);
  return UmText::Format(EUmTable::Hud, Key, A);
}
}  // namespace

FText DeckLabel(const FUmDecksModel& M, bool bClassS) {
  return Label(TEXT("hud.decks.deck"), M.DeckCount, M.bDeckStale, bClassS);
}

FText DiscardLabel(const FUmDecksModel& M, bool bClassS) {
  return Label(TEXT("hud.decks.discard"), M.DiscardCount, M.bDiscardStale, bClassS);
}

float IconSuFor(float PxPerSu) { return PxPerSu > 0.0f && PxPerSu < 1.0f ? 32.0f : 24.0f; }

const TCHAR* StateName(const FUmDecksModel& M) { return M.bDeckStale || M.bDiscardStale ? TEXT("stale") : TEXT("idle"); }
}  // namespace UmHudDecks

namespace {
template <typename T>
T* UmDecksFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

UCanvasPanelSlot* UmDecksSlot(UWidget* W) { return W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr; }

void UmDecksPlace(UWidget* W, const FVector2D& Pos, const FVector2D& Size, int32 Z) {
  if (UCanvasPanelSlot* S = UmDecksSlot(W)) {
    S->SetAnchors(FAnchors(0.0f, 0.0f));
    S->SetAlignment(FVector2D::ZeroVector);
    S->SetAutoSize(false);
    S->SetPosition(Pos);
    S->SetSize(Size);
    S->SetZOrder(Z);
  }
}
}  // namespace

UClass* UUmHudDecks::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmHudDecks::StaticClass(), WidgetBlueprintPath); }

bool UUmHudDecks::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UCanvasPanel* RowW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Row")));
  RowW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(RowW, nullptr)) return Fail(TEXT("Row"));
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  for (const TCHAR* Side : {TEXT("Deck"), TEXT("Discard")}) {
    const FString S(Side);
    UUmButton* Chip = Tree.ConstructWidget<UUmButton>(ButtonClass, FName(*(S + TEXT("Chip"))));
    if (!Attach(Chip, RowW)) return Fail(TEXT("Chip"));
    // the mini card: 32 x 45 su in L, scaled to 18 x 25.3 su in S (one widget, ScaleToFit)
    USizeBox* MiniBox = Tree.ConstructWidget<USizeBox>(USizeBox::StaticClass(), FName(*(S + TEXT("MiniBox"))));
    MiniBox->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (!Attach(MiniBox, RowW)) return Fail(TEXT("MiniBox"));
    UScaleBox* MiniScale = Tree.ConstructWidget<UScaleBox>(UScaleBox::StaticClass(), FName(*(S + TEXT("MiniScale"))));
    MiniScale->SetStretch(EStretch::ScaleToFit);
    if (!Attach(MiniScale, MiniBox)) return Fail(TEXT("MiniScale"));
    UUmCardWidget* Mini = Tree.ConstructWidget<UUmCardWidget>(UUmCardWidget::WidgetClass(), FName(*(S + TEXT("Mini"))));
    if (!Attach(Mini, MiniScale)) return Fail(TEXT("Mini"));
    US08AnimatedIconWidget* IconW = Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(),
                                                                                  FName(*(S + TEXT("Icon"))));
    IconW->SetVisibility(ESlateVisibility::Collapsed);
    if (!Attach(IconW, RowW)) return Fail(TEXT("Icon"));
    UTextBlock* CountW = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(*(S + TEXT("Count"))));
    CountW->SetFont(Theme.Font(TEXT("type.button")));
    CountW->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
    CountW->SetShadowOffset(FVector2D::ZeroVector);
    CountW->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (!Attach(CountW, RowW)) return Fail(TEXT("Count"));
  }
  return true;
}

bool UUmHudDecks::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD decks default tree: %s"), *Error);
  }
  Row = UmDecksFind<UCanvasPanel>(WidgetTree, TEXT("Row"));
  DeckChip = UmDecksFind<UUmButton>(WidgetTree, TEXT("DeckChip"));
  DiscardChip = UmDecksFind<UUmButton>(WidgetTree, TEXT("DiscardChip"));
  DeckCount = UmDecksFind<UTextBlock>(WidgetTree, TEXT("DeckCount"));
  DiscardCount = UmDecksFind<UTextBlock>(WidgetTree, TEXT("DiscardCount"));
  DeckMiniBox = UmDecksFind<USizeBox>(WidgetTree, TEXT("DeckMiniBox"));
  DeckMiniScale = UmDecksFind<UScaleBox>(WidgetTree, TEXT("DeckMiniScale"));
  DeckMini = UmDecksFind<UUmCardWidget>(WidgetTree, TEXT("DeckMini"));
  DeckIcon = UmDecksFind<US08AnimatedIconWidget>(WidgetTree, TEXT("DeckIcon"));
  DiscardMiniBox = UmDecksFind<USizeBox>(WidgetTree, TEXT("DiscardMiniBox"));
  DiscardMiniScale = UmDecksFind<UScaleBox>(WidgetTree, TEXT("DiscardMiniScale"));
  DiscardMini = UmDecksFind<UUmCardWidget>(WidgetTree, TEXT("DiscardMini"));
  DiscardIcon = UmDecksFind<US08AnimatedIconWidget>(WidgetTree, TEXT("DiscardIcon"));
  // a WBP keeps neither the theme font nor the colour of the code tree: set at run time
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  for (UTextBlock* T : {DeckCount.Get(), DiscardCount.Get()}) {
    if (!T) continue;
    T->SetFont(Theme.Font(TEXT("type.button")));
    T->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
    T->SetShadowOffset(FVector2D::ZeroVector);
    T->SetVisibility(ESlateVisibility::HitTestInvisible);
  }
  for (UWidget* W : {static_cast<UWidget*>(DeckMiniBox.Get()), static_cast<UWidget*>(DiscardMiniBox.Get()),
                     static_cast<UWidget*>(DeckIcon.Get()), static_cast<UWidget*>(DiscardIcon.Get())}) {
    if (W) W->SetVisibility(ESlateVisibility::HitTestInvisible);
  }
  if (DeckIcon) DeckIcon->SetVisibility(ESlateVisibility::Collapsed);  // the deck chip always shows the back
  if (Row) Row->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  return bFirst;
}

bool UUmHudDecks::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Row) Missing.Add(TEXT("Row"));
  if (!DeckChip) Missing.Add(TEXT("DeckChip"));
  if (!DiscardChip) Missing.Add(TEXT("DiscardChip"));
  if (!DeckCount) Missing.Add(TEXT("DeckCount"));
  if (!DiscardCount) Missing.Add(TEXT("DiscardCount"));
  if (!DeckMini) Missing.Add(TEXT("DeckMini"));
  if (!DiscardMini) Missing.Add(TEXT("DiscardMini"));
  if (!DiscardIcon) Missing.Add(TEXT("DiscardIcon"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

FString UUmHudDecks::SourceName() const {
  return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName();
}

void UUmHudDecks::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter,
                           TFunction<void(const FS09HudPressOutcome&, bool)> InOnPress) {
  TSharedPtr<TFunction<void(const FS09HudPressOutcome&, bool)>> Press =
      MakeShared<TFunction<void(const FS09HudPressOutcome&, bool)>>(MoveTemp(InOnPress));
  if (DeckChip) {
    DeckChip->SetPress(FName(TEXT("hud.decks.deck")), InArbiter, FS09OnHudPressOutcome::CreateLambda([Press](const FS09HudPressOutcome& O) {
      if (*Press) (*Press)(O, false);
    }));
  }
  if (DiscardChip) {
    DiscardChip->SetPress(FName(TEXT("hud.decks.discard")), InArbiter, FS09OnHudPressOutcome::CreateLambda([Press](const FS09HudPressOutcome& O) {
      if (*Press) (*Press)(O, true);
    }));
  }
}

void UUmHudDecks::SetSyncLoad(bool bOn) {
  if (DeckMini) DeckMini->SetSyncLoad(bOn);
  if (DiscardMini) DiscardMini->SetSyncLoad(bOn);
}

void UUmHudDecks::SetLegacyForTest(int32 InLegacy) {
  if (DeckMini) DeckMini->SetLegacyForTest(InLegacy);
  if (DiscardMini) DiscardMini->SetLegacyForTest(InLegacy);
}

FBox2D UUmHudDecks::ChipRectSu(int32 Index) const {
  return UmHudLayout::DeckChipRect(Frame.RectSu, Frame.bClassS, Frame.bEnglish, Index);
}

void UUmHudDecks::SetFrame(const FUmDecksFrame& InFrame) {
  if (bHasFrame && Frame == InFrame) return;
  Frame = InFrame;
  bHasFrame = true;
  Relayout();
  if (bHasModel) ApplyContent();
}

void UUmHudDecks::Relayout() {
  if (!Frame.RectSu.bIsValid) return;
  using namespace UmHudDecks;
  const bool bS = Frame.bClassS;
  const float ChipH = bS ? ChipHeightSSu : ChipHeightLSu;
  const FVector2D Origin = Frame.RectSu.Min;
  const float MiniW = bS ? MiniSWSu : MiniWSu;
  const float MiniH = bS ? MiniSWSu * MiniHSu / MiniWSu : MiniHSu;
  const float MiniLeft = bS ? MiniLeftSSu : MiniLeftLSu;
  const float TextLeft = bS ? TextLeftSSu : TextLeftLSu;
  IconSuNow = IconSuFor(Frame.PxPerSu);
  for (int32 I = 0; I < 2; ++I) {
    const FBox2D Chip = ChipRectSu(I);
    const FVector2D P = Chip.Min - Origin;
    const float W = static_cast<float>(Chip.Max.X - Chip.Min.X);
    UUmButton* Button = I == 0 ? DeckChip.Get() : DiscardChip.Get();
    if (Button) {
      // the Btn_Normal body of HB-08, no label of its own: the mini card and the count lie over it
      FUmButtonModel B;
      B.Variant = EUmButtonVariant::Normal;
      B.HeightSu = ChipH;
      B.MinWidthSu = W;
      Button->ApplyModel(B);
      UmDecksPlace(Button, P, FVector2D(W, ChipH), 0);
    }
    USizeBox* MiniBox = I == 0 ? DeckMiniBox.Get() : DiscardMiniBox.Get();
    if (MiniBox) {
      MiniBox->SetWidthOverride(MiniW);
      MiniBox->SetHeightOverride(MiniH);
      UmDecksPlace(MiniBox, P + FVector2D(MiniLeft, 0.5f * (ChipH - MiniH)), FVector2D(MiniW, MiniH), 1);
    }
    US08AnimatedIconWidget* IconW = I == 0 ? DeckIcon.Get() : DiscardIcon.Get();
    if (IconW && IconW->SetIcon(TEXT("resource-card"), IconSuNow, FMath::RoundToInt(IconSuNow))) {
      IconW->SetDisplaySizeSu(IconSuNow);
      IconW->ShowAtRest();
      // centred on the mini card's place (it stands in for the top card of an empty pile)
      const FVector2D C = P + FVector2D(MiniLeft + 0.5f * MiniW, 0.5f * ChipH);
      UmDecksPlace(IconW, C - FVector2D(0.5f * IconSuNow), FVector2D(IconSuNow), 1);
    }
    UTextBlock* Text = I == 0 ? DeckCount.Get() : DiscardCount.Get();
    if (UCanvasPanelSlot* S = UmDecksSlot(Text)) {
      S->SetAnchors(FAnchors(0.0f, 0.0f));
      S->SetAlignment(FVector2D(0.0f, 0.5f));
      S->SetAutoSize(true);
      S->SetPosition(P + FVector2D(TextLeft, 0.5f * ChipH));
      S->SetZOrder(2);
    }
  }
}

void UUmHudDecks::ApplyModel(const FUmDecksModel& InModel) {
  if (bHasModel && Model == InModel) return;
  Model = InModel;
  bHasModel = true;
  ++ApplyCount;
  ApplyContent();
}

void UUmHudDecks::ApplyContent() {
  SetVisibility(Model.bShow ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Collapsed);
  if (!Model.bShow) return;
  const bool bS = Frame.bClassS;
  if (DeckCount) DeckCount->SetText(UmHudDecks::DeckLabel(Model, bS));
  if (DiscardCount) DiscardCount->SetText(UmHudDecks::DiscardLabel(Model, bS));
  // the mini cards: S draws the 32 x 45 widget at 18 / 32 of its size (ScaleToFit) - its fit takes that px per su
  FUmCardState State;
  State.Show = EUmCardShow::MiniChip;
  State.HeroSlug = Model.HeroSlug;
  State.PxPerSu = Frame.PxPerSu * (bS ? UmHudDecks::MiniSWSu / UmHudDecks::MiniWSu : 1.0f);
  if (DeckMini) {
    FS09CardView Back;
    Back.InstanceId = TEXT("decks.deck.back");
    FUmCardState Down = State;
    Down.bFaceDown = true;
    DeckMini->ApplyModel(Back, Down);
  }
  if (DiscardMini) {
    FUmCardState Top = State;
    Top.bFaceDown = Model.Top.bHidden;  // a face-down entry (a combat card before its reveal) shows its back
    if (Model.bHasTop) DiscardMini->ApplyModel(Model.Top, Top);
  }
  if (DiscardMiniBox) DiscardMiniBox->SetVisibility(Model.bHasTop ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  if (DiscardIcon) DiscardIcon->SetVisibility(Model.bHasTop ? ESlateVisibility::Collapsed : ESlateVisibility::HitTestInvisible);
}

void UUmHudDecks::CollectShotLines(TArray<FString>& Out) const {
  const bool bVisible = bHasModel && Model.bShow && UmGameHudSlots::ShownByProperty(this);
  const float Px = Frame.PxPerSu > 0.0f ? Frame.PxPerSu : 1.0f;
  FS08ScreenRect Rect;
  if (Frame.RectSu.bIsValid) {
    const FBox2D A = ChipRectSu(0);
    const FBox2D B = ChipRectSu(1);
    Rect = FS08ScreenRect(A.Min.X * Px, A.Min.Y * Px, B.Max.X * Px, B.Max.Y * Px);
  }
  const FBox2D A = ChipRectSu(0);
  const FBox2D B = ChipRectSu(1);
  const TCHAR* Top = !Model.bHasTop ? TEXT("none") : Model.Top.bHidden ? TEXT("back") : TEXT("face");
  const FString Extra = FString::Printf(
      TEXT("class=%s deck=%d discard=%d deckStale=%d discardStale=%d top=%s chips=%.0fx%.0f,%.0fx%.0f lang=%s icon=%.0f"),
      Frame.bClassS ? TEXT("S") : TEXT("L"), Model.DeckCount, Model.DiscardCount, Model.bDeckStale ? 1 : 0,
      Model.bDiscardStale ? 1 : 0, Top, A.Max.X - A.Min.X, A.Max.Y - A.Min.Y, B.Max.X - B.Min.X, B.Max.Y - B.Min.Y,
      Frame.bEnglish ? TEXT("en") : TEXT("ru"), IconSuNow);
  Out.Add(S08ArtHud::FormatWidgetLineEx(TEXT("UI-HUD-DECKS"), TEXT("umg"), UmHudDecks::StateName(Model), FString(), Rect,
                                        bVisible && !Rect.IsEmpty(), bVisible, SourceName(), Extra));
}

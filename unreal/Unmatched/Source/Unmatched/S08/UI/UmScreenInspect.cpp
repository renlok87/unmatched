// VS-4 V4 (H13): INSPECT - see UmScreenInspect.h.
#include "UmScreenInspect.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08ArtHud.h"
#include "../S08IconMotion.h"
#include "UmButton.h"
#include "UmCardMedia.h"
#include "UmDeckRow.h"
#include "UmGameHud.h"
#include "UmHudScale.h"
#include "UmHudTheme.h"
#include "UmSpinner.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/BorderSlot.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Image.h"
#include "Components/NamedSlot.h"
#include "Components/ScrollBox.h"
#include "Components/ScrollBoxSlot.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/UniformGridPanel.h"
#include "Components/UniformGridSlot.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "InputCoreTypes.h"

const TCHAR* const UUmScreenInspect::WidgetBlueprintPath = TEXT("/Game/S08/UI/Screens/WBP_UI_SCR_INSPECT");

UClass* UUmScreenInspect::WidgetClass() {
  return UmGameHudSlots::WbpOrNative(UUmScreenInspect::StaticClass(), WidgetBlueprintPath);
}

// ------------------------------------------------------------------------------------------------ the model

namespace UmInspect {
const TCHAR* ModeName(EUmInspectMode Mode) {
  switch (Mode) {
    case EUmInspectMode::Hidden: return TEXT("hidden");
    case EUmInspectMode::Deck: return TEXT("deck");
    case EUmInspectMode::DeckCard: return TEXT("deckcard");
    default: return TEXT("own");
  }
}

const TCHAR* SourceName(EUmInspectSource Source) {
  switch (Source) {
    case EUmInspectSource::Hand: return TEXT("hand");
    case EUmInspectSource::Discard: return TEXT("discard");
    case EUmInspectSource::Log: return TEXT("log");
    case EUmInspectSource::DeckRow: return TEXT("deckrow");
    case EUmInspectSource::Combat: return TEXT("combat");
    case EUmInspectSource::Slot: return TEXT("slot");
    case EUmInspectSource::Key: return TEXT("key");
    case EUmInspectSource::OppHand: return TEXT("opphand");
    case EUmInspectSource::Pending: return TEXT("pending");
    case EUmInspectSource::DeckAll: return TEXT("deckall");
    case EUmInspectSource::Room: return TEXT("room");
    default: return TEXT("sheet");
  }
}

const TCHAR* StateName(EUmInspectMode Mode, bool bLoading) {
  if (Mode == EUmInspectMode::Hidden) return TEXT("hidden");
  if (Mode == EUmInspectMode::Deck) return TEXT("deck");
  return bLoading ? TEXT("loading") : TEXT("own");
}

FVector2D ModalSize(bool bClassS) { return bClassS ? FVector2D(ModalSW, ModalSH) : FVector2D(ModalLW, ModalLH); }

FBox2D SlotRect(bool bClassS) {
  const FVector2D Size = bClassS ? FVector2D(SlotSW, SlotSH) : FVector2D(SlotLW, SlotLH);
  return FBox2D(FVector2D(PadSu, PadSu), FVector2D(PadSu, PadSu) + Size);
}

FBox2D ColumnRect(bool bClassS) {
  const FVector2D Modal = ModalSize(bClassS);
  const float X = bClassS ? ColSX : ColLX;
  const float W = bClassS ? ColSW : ColLW;
  return FBox2D(FVector2D(X, PadSu), FVector2D(X + W, Modal.Y - PadSu));
}

EUmCardShow CardShow(bool bClassS) { return bClassS ? EUmCardShow::ClassSInspector : EUmCardShow::Inspector; }

FBox2D GridRect(bool bClassS) {
  const FVector2D Modal = ModalSize(bClassS);
  // two whole rows centred between the title band and the bottom margin (the CX-23 SC-23 geometry: L y 150, S y 106);
  // the scroll room for the track at the right
  const float Top = GridTitleBandSu + FMath::Max(0.0f, (Modal.Y - PadSu - GridTitleBandSu - GridViewSu) * 0.5f);
  const float W = Modal.X - 2.0f * PadSu - GridScrollRoomSu;
  return FBox2D(FVector2D(PadSu, Top), FVector2D(PadSu + W, Top + GridViewSu));
}

int32 GridRows(int32 Cards) { return Cards <= 0 ? 0 : (Cards + GridColumns - 1) / GridColumns; }

int32 MaxFirstRow(int32 Cards) {
  const int32 Visible = FMath::Max(1, FMath::FloorToInt((GridViewSu + GridRowGapSu + 0.5f) / GridRowStepSu));
  return FMath::Max(0, GridRows(Cards) - Visible);
}

FString TypeKey(const FString& CardType) {
  switch (UmDeckRow::TypeOrder(CardType)) {
    case 0: return TEXT("hud.inspect.type.attack");
    case 1: return TEXT("hud.inspect.type.defense");
    case 2: return TEXT("hud.inspect.type.versatile");
    case 3: return TEXT("hud.inspect.type.scheme");
    default: return FString();
  }
}

int32 ValueOf(const FS09CardView& Card) {
  switch (UmDeckRow::TypeOrder(Card.CardType)) {
    case 0: return Card.AttackValue;
    case 1: return Card.DefenseValue;
    case 2: return Card.AttackValue > 0 ? Card.AttackValue : Card.DefenseValue;
    default: return INDEX_NONE;
  }
}

FS09CardView DeckCardView(const FS09DeckListCard& C) {
  FS09CardView V;
  V.CardId = C.CardId;
  V.Name = C.Name;
  V.NameRu = C.NameRu;
  V.CardType = C.CardType;
  V.BannerName = C.BannerName;
  V.Text = C.Text;
  V.AttackValue = FMath::Max(0, C.AttackValue);
  V.DefenseValue = FMath::Max(0, C.DefenseValue);
  V.BoostValue = FMath::Max(0, C.BoostValue);
  V.bHasBoostValue = C.BoostValue >= 0;
  V.bVisible = true;
  return V;
}

const FS09DeckList* FindList(const FUmInspectContext& C, const FString& PlayerId) {
  if (!C.Lists || PlayerId.IsEmpty()) return nullptr;
  return C.Lists->FindByPredicate([&PlayerId](const FS09DeckList& L) { return L.PlayerId == PlayerId; });
}

namespace {
bool PanelHas(const FS09PlayerPanel* P, const FS09CardView& Card) {
  if (!P) return false;
  auto Same = [&Card](const FS09CardView& X) {
    return !Card.InstanceId.IsEmpty() ? X.InstanceId == Card.InstanceId : (!Card.CardId.IsEmpty() && X.CardId == Card.CardId);
  };
  return P->Cards.ContainsByPredicate(Same) || P->Discard.ContainsByPredicate(Same);
}

/** gameDeckLists has no text for a card with parsed effects (`text` empty): the printed effect text of a known
 *  instance of the same card (the snapshot's EffectText) stands in (ВР-VS4-64). */
FString KnownText(const FUmInspectContext& C, const FString& CardId) {
  if (CardId.IsEmpty()) return FString();
  for (const FS09PlayerPanel* P : {C.Own, C.Opp}) {
    if (!P) continue;
    for (const TArray<FS09CardView>* Pile : {&P->Cards, &P->Discard}) {
      for (const FS09CardView& X : *Pile) {
        if (X.CardId != CardId) continue;
        if (!X.Text.IsEmpty()) return X.Text;
        if (!X.EffectText.IsEmpty()) return X.EffectText;
      }
    }
  }
  return FString();
}

bool ListHas(const FS09DeckList* L, const FString& CardId) {
  return L && !CardId.IsEmpty() && L->Cards.ContainsByPredicate([&CardId](const FS09DeckListCard& X) { return X.CardId == CardId; });
}
}  // namespace

FUmInspectModel Hidden(const FString& OwnerSlug, const FString& OwnerHero, EUmInspectSource Source) {
  FUmInspectModel M;
  M.Mode = EUmInspectMode::Hidden;
  M.Source = Source;
  M.Card.bHidden = true;
  M.Card.CardId = TEXT("hidden");
  M.HeroSlug = OwnerSlug;
  M.HeroName = OwnerHero;
  return M;
}

FUmInspectModel FromCard(const FS09CardView& Card, EUmInspectSource Source, const FUmInspectContext& C) {
  if (Card.bHidden) return Hidden(C.OppSlug, C.OppHero, Source);
  FUmInspectModel M;
  M.Mode = EUmInspectMode::Own;
  M.Source = Source;
  M.Card = Card;
  if (M.Card.Text.IsEmpty() && M.Card.EffectText.IsEmpty()) M.Card.EffectText = KnownText(C, Card.CardId);
  // the owner: the own hand / discard or the own list -> own; else the opponent's (his discard, his revealed card)
  const FS09DeckList* OwnList = C.Own ? FindList(C, C.Own->PlayerId) : nullptr;
  const bool bOppPile = PanelHas(C.Opp, Card);
  const bool bOwn = PanelHas(C.Own, Card) || (!bOppPile && ListHas(OwnList, Card.CardId));
  M.HeroSlug = bOwn ? C.OwnSlug : C.OppSlug;
  M.HeroName = bOwn ? C.OwnHero : C.OppHero;
  // «В колоде: n · в руке: h · в сбросе: d» - the own deck only (ВР-VS3-SC21-03: n = copies - hand - discard)
  if (bOwn && OwnList && !Card.CardId.IsEmpty()) {
    const FS09DeckListCard* Row = OwnList->Cards.FindByPredicate([&Card](const FS09DeckListCard& X) { return X.CardId == Card.CardId; });
    if (Row) {
      M.Copies.bKnown = true;
      M.Copies.Copies = Row->Count;
      for (const FS09CardView& X : C.Own->Cards) M.Copies.Hand += X.CardId == Card.CardId ? 1 : 0;
      for (const FS09CardView& X : C.Own->Discard) M.Copies.Discard += X.CardId == Card.CardId ? 1 : 0;
      M.Copies.Deck = FMath::Max(0, Row->Count - M.Copies.Hand - M.Copies.Discard);
    }
  }
  return M;
}

FUmInspectModel FromList(const FS09DeckList& List, const FString& HeroSlug, const FString& HeroName, EUmInspectSource Source) {
  FUmInspectModel M;
  M.Mode = EUmInspectMode::Deck;
  M.Source = Source;
  M.HeroSlug = HeroSlug;
  M.HeroName = HeroName;
  M.Deck = List.Cards;  // the catalogue order of gameDeckLists (F-05: never the draw order)
  return M;
}

FUmInspectModel FromDeck(bool bOwnSide, EUmInspectSource Source, const FUmInspectContext& C) {
  const FS09PlayerPanel* Side = bOwnSide ? C.Own : C.Opp;
  const FS09DeckList* List = Side ? FindList(C, Side->PlayerId) : nullptr;
  if (!List) {
    FUmInspectModel None;
    None.Source = Source;
    return None;
  }
  FUmInspectModel M = FromList(*List, bOwnSide ? C.OwnSlug : C.OppSlug, bOwnSide ? C.OwnHero : C.OppHero, Source);
  for (FS09DeckListCard& Card : M.Deck) {
    if (Card.Text.IsEmpty()) Card.Text = KnownText(C, Card.CardId);
  }
  return M;
}

int32 CopiesSum(const TArray<FS09DeckListCard>& Deck) {
  int32 N = 0;
  for (const FS09DeckListCard& C : Deck) N += C.Count;
  return N;
}

FString OpenLine(const FUmInspectModel& M) {
  return FString::Printf(TEXT("INSPECT open source=%s mode=%s grid=%d copies=%d known=%d"), SourceName(M.Source), ModeName(M.Mode),
                         M.Deck.Num(), CopiesSum(M.Deck), M.Copies.bKnown ? 1 : 0);
}
}  // namespace UmInspect

// ------------------------------------------------------------------------------------------------ the tree

namespace {
template <typename T>
T* UmInFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

void UmInPlace(UWidget* W, const FVector2D& Pos, const FVector2D& Size) {
  if (UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr) {
    S->SetAnchors(FAnchors(0.0f, 0.0f));
    S->SetAlignment(FVector2D::ZeroVector);
    S->SetAutoSize(false);
    S->SetPosition(Pos);
    S->SetSize(Size);
  }
}

void UmInText(UTextBlock* T, FName Type, FName Color) {
  if (!T) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  T->SetFont(Theme.Font(Type));
  T->SetColorAndOpacity(FSlateColor(Theme.Color(Color)));
  T->SetShadowOffset(FVector2D::ZeroVector);
}

void UmInShow(UWidget* W, bool bOn, ESlateVisibility On = ESlateVisibility::HitTestInvisible) {
  if (!W) return;
  const ESlateVisibility Want = bOn ? On : ESlateVisibility::Collapsed;
  if (W->GetVisibility() != Want) W->SetVisibility(Want);
}

/** The content alignment of a border lives in its slot (UBorderSlot): set there once the content exists. */
void UmInCentre(UWidget* Content, bool bHCentre) {
  if (UBorderSlot* S = Content ? Cast<UBorderSlot>(Content->Slot) : nullptr) {
    S->SetHorizontalAlignment(bHCentre ? HAlign_Center : HAlign_Left);
    S->SetVerticalAlignment(VAlign_Center);
  }
}

/** No shadow at the scroll box's edges (the grid and the text end on the panel, nothing is dimmed). */
void UmInNoShadow(UScrollBox* Box) {
  if (!Box) return;
  FScrollBoxStyle Style = Box->GetWidgetStyle();
  Style.SetTopShadowBrush(FSlateNoResource());
  Style.SetBottomShadowBrush(FSlateNoResource());
  Style.SetLeftShadowBrush(FSlateNoResource());
  Style.SetRightShadowBrush(FSlateNoResource());
  Box->SetWidgetStyle(Style);
}

void UmInPad(UWidget* W, float Top) {
  if (UVerticalBoxSlot* S = W ? Cast<UVerticalBoxSlot>(W->Slot) : nullptr) {
    S->SetPadding(FMargin(0.0f, Top, 0.0f, 0.0f));
    S->SetHorizontalAlignment(HAlign_Fill);
  }
}

}  // namespace

bool UUmScreenInspect::AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  UCanvasPanel* ContentW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Content")));
  ContentW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(ContentW, Parent)) return Fail(TEXT("Content"));
  // the card (the nested WBP_UmCard when it exists)
  UClass* CardClass = UmGameHudSlots::WbpOrNative(UUmCardWidget::StaticClass(), UUmCardWidget::WidgetBlueprintPath);
  if (!Attach(Tree.ConstructWidget<UUmCardWidget>(CardClass, FName(TEXT("Card"))), ContentW)) return Fail(TEXT("Card"));
  // the text column
  UVerticalBox* ColumnW = Tree.ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), FName(TEXT("Column")));
  ColumnW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(ColumnW, ContentW)) return Fail(TEXT("Column"));
  UTextBlock* TitleW = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("TitleText")));
  TitleW->SetAutoWrapText(true);
  if (!Attach(TitleW, ColumnW)) return Fail(TEXT("TitleText"));
  UHorizontalBox* TypeRowW = Tree.ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), FName(TEXT("TypeRow")));
  if (!Attach(TypeRowW, ColumnW)) return Fail(TEXT("TypeRow"));
  if (!Attach(Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("TypeIcon"))), TypeRowW)) {
    return Fail(TEXT("TypeIcon"));
  }
  if (!Attach(Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("TypeText"))), TypeRowW)) return Fail(TEXT("TypeText"));
  for (const TCHAR* Name : {TEXT("ValueText"), TEXT("BoostText")}) {
    if (!Attach(Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name)), ColumnW)) return Fail(Name);
  }
  USizeBox* ChipBox = Tree.ConstructWidget<USizeBox>(USizeBox::StaticClass(), FName(TEXT("CopiesChipBox")));
  ChipBox->SetWidthOverride(UmInspect::GridChipWSu);
  ChipBox->SetHeightOverride(UmInspect::GridChipHSu);
  if (!Attach(ChipBox, ColumnW)) return Fail(TEXT("CopiesChipBox"));
  UBorder* ChipW = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("CopiesChip")));
  if (!Attach(ChipW, ChipBox)) return Fail(TEXT("CopiesChip"));
  if (!Attach(Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("CopiesChipText"))), ChipW)) {
    return Fail(TEXT("CopiesChipText"));
  }
  UScrollBox* BodyW = Tree.ConstructWidget<UScrollBox>(UScrollBox::StaticClass(), FName(TEXT("BodyText")));
  if (!Attach(BodyW, ColumnW)) return Fail(TEXT("BodyText"));
  for (const TCHAR* Name : {TEXT("BodyLine"), TEXT("CopiesText"), TEXT("ArtMissingText")}) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetAutoWrapText(true);
    if (!Attach(T, BodyW)) return Fail(Name);
  }
  // the language row: the key chip «Tab» + «Язык карты»
  UHorizontalBox* LangW = Tree.ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), FName(TEXT("LangToggle")));
  if (!Attach(LangW, ContentW)) return Fail(TEXT("LangToggle"));
  UBorder* KeyW = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("LangKey")));
  if (!Attach(KeyW, LangW)) return Fail(TEXT("LangKey"));
  if (!Attach(Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("LangKeyText"))), KeyW)) return Fail(TEXT("LangKeyText"));
  if (!Attach(Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("LangText"))), LangW)) return Fail(TEXT("LangText"));
  // the buttons
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  for (const TCHAR* Name : {TEXT("CloseButton"), TEXT("BackButton")}) {
    if (!Attach(Tree.ConstructWidget<UUmButton>(ButtonClass, FName(Name)), ContentW)) return Fail(Name);
  }
  // the deck grid
  UScrollBox* ScrollW = Tree.ConstructWidget<UScrollBox>(UScrollBox::StaticClass(), FName(TEXT("DeckScroll")));
  if (!Attach(ScrollW, ContentW)) return Fail(TEXT("DeckScroll"));
  if (!Attach(Tree.ConstructWidget<UUniformGridPanel>(UUniformGridPanel::StaticClass(), FName(TEXT("DeckGrid"))), ScrollW)) {
    return Fail(TEXT("DeckGrid"));
  }
  for (const TCHAR* Name : {TEXT("Track"), TEXT("Thumb")}) {
    UImage* I = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(Name));
    I->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (!Attach(I, ContentW)) return Fail(Name);
  }
  return true;
}

bool UUmScreenInspect::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  if (!UUmScreenBase::BuildDefaultTree(Tree, Attach, OutError)) return false;
  UNamedSlot* BodyW = Cast<UNamedSlot>(Tree.FindWidget(FName(TEXT("Body"))));
  if (!BodyW) {
    if (OutError) *OutError = TEXT("no Body");
    return false;
  }
  return AttachContent(Tree, BodyW, Attach, OutError);
}

void UUmScreenInspect::BuildContent() {
  if (!WidgetTree || !Body || Body->GetContent()) return;
  UWidgetTree* Tree = WidgetTree;
  FString Error;
  if (!AttachContent(*Tree, Body, [](UWidget* Child, UPanelWidget* Parent) { return Parent && Parent->AddChild(Child) != nullptr; }, &Error)) {
    UE_LOG(LogTemp, Error, TEXT("UMHUD inspect content: %s"), *Error);
  }
}

void UUmScreenInspect::BindParts() {
  Content = UmInFind<UCanvasPanel>(WidgetTree, TEXT("Content"));
  Card = UmInFind<UUmCardWidget>(WidgetTree, TEXT("Card"));
  Column = UmInFind<UVerticalBox>(WidgetTree, TEXT("Column"));
  TitleText = UmInFind<UTextBlock>(WidgetTree, TEXT("TitleText"));
  TypeRow = UmInFind<UHorizontalBox>(WidgetTree, TEXT("TypeRow"));
  TypeIcon = UmInFind<US08AnimatedIconWidget>(WidgetTree, TEXT("TypeIcon"));
  TypeText = UmInFind<UTextBlock>(WidgetTree, TEXT("TypeText"));
  ValueText = UmInFind<UTextBlock>(WidgetTree, TEXT("ValueText"));
  BoostText = UmInFind<UTextBlock>(WidgetTree, TEXT("BoostText"));
  CopiesChip = UmInFind<UBorder>(WidgetTree, TEXT("CopiesChip"));
  CopiesChipText = UmInFind<UTextBlock>(WidgetTree, TEXT("CopiesChipText"));
  BodyText = UmInFind<UScrollBox>(WidgetTree, TEXT("BodyText"));
  BodyLine = UmInFind<UTextBlock>(WidgetTree, TEXT("BodyLine"));
  CopiesText = UmInFind<UTextBlock>(WidgetTree, TEXT("CopiesText"));
  ArtMissingText = UmInFind<UTextBlock>(WidgetTree, TEXT("ArtMissingText"));
  LangToggle = UmInFind<UHorizontalBox>(WidgetTree, TEXT("LangToggle"));
  LangKey = UmInFind<UBorder>(WidgetTree, TEXT("LangKey"));
  LangKeyText = UmInFind<UTextBlock>(WidgetTree, TEXT("LangKeyText"));
  LangText = UmInFind<UTextBlock>(WidgetTree, TEXT("LangText"));
  CloseButton = UmInFind<UUmButton>(WidgetTree, TEXT("CloseButton"));
  BackButton = UmInFind<UUmButton>(WidgetTree, TEXT("BackButton"));
  DeckScroll = UmInFind<UScrollBox>(WidgetTree, TEXT("DeckScroll"));
  DeckGrid = UmInFind<UUniformGridPanel>(WidgetTree, TEXT("DeckGrid"));
  Track = UmInFind<UImage>(WidgetTree, TEXT("Track"));
  Thumb = UmInFind<UImage>(WidgetTree, TEXT("Thumb"));
}

bool UUmScreenInspect::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  SetUiId(TEXT("UI-SCR-INSPECT"));
  BindParts();
  // a WBP keeps neither the theme fonts nor the code brushes: set at run time (П3: tokens only)
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UmInText(TitleText, TEXT("type.title"), TEXT("text.primary"));
  UmInText(TypeText, TEXT("type.body"), TEXT("text.primary"));
  UmInText(ValueText, TEXT("type.heading"), TEXT("text.primary"));  // font.card: Roboto Bold Condensed runtime numerals
  UmInText(BoostText, TEXT("type.heading"), TEXT("text.primary"));
  UmInText(CopiesChipText, TEXT("type.caption"), TEXT("text.primary"));
  UmInText(BodyLine, TEXT("type.body"), TEXT("text.primary"));
  UmInText(CopiesText, TEXT("type.caption"), TEXT("text.secondary"));
  UmInText(ArtMissingText, TEXT("type.caption"), TEXT("text.secondary"));
  UmInText(LangKeyText, TEXT("type.caption"), TEXT("text.primary"));
  UmInText(LangText, TEXT("type.caption"), TEXT("text.secondary"));
  for (UTextBlock* T : {TitleText.Get(), BodyLine.Get(), CopiesText.Get(), ArtMissingText.Get()}) {
    if (T) T->SetAutoWrapText(true);
  }
  if (CopiesChip) {
    if (const FSlateBrush* Skin = Theme.Skin(TEXT("chip"))) CopiesChip->SetBrush(*Skin);
    CopiesChip->SetPadding(FMargin(0.0f));
    CopiesChip->SetHorizontalAlignment(HAlign_Center);
    CopiesChip->SetVerticalAlignment(VAlign_Center);
    UmInCentre(CopiesChipText, true);
  }
  if (LangKey) {
    if (const FSlateBrush* Skin = Theme.Skin(TEXT("key.chip"))) LangKey->SetBrush(*Skin);
    LangKey->SetPadding(FMargin(6.0f, 2.0f));
    LangKey->SetVerticalAlignment(VAlign_Center);
    UmInCentre(LangKeyText, true);
    if (UBorderSlot* S = LangKeyText ? Cast<UBorderSlot>(LangKeyText->Slot) : nullptr) S->SetPadding(FMargin(6.0f, 2.0f));
    if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(LangKey->Slot)) S->SetVerticalAlignment(VAlign_Center);
  }
  if (LangText) {
    if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(LangText->Slot)) {
      S->SetPadding(FMargin(8.0f, 0.0f, 0.0f, 0.0f));
      S->SetVerticalAlignment(VAlign_Center);
    }
  }
  if (LangKeyText) LangKeyText->SetText(FText::FromString(TEXT("Tab")));  // the key's name (ВР-H09: keys are chips)
  if (LangText) LangText->SetText(UmText::Get(EUmTable::Hud, TEXT("hud.inspect.lang.toggle")));
  if (ArtMissingText) ArtMissingText->SetText(UmText::Get(EUmTable::Hud, TEXT("hud.inspect.art.missing")));
  if (TypeText) {
    if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(TypeText->Slot)) S->SetVerticalAlignment(VAlign_Center);
  }
  if (TypeIcon) {
    if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(TypeIcon->Slot)) {
      S->SetPadding(FMargin(0.0f, 0.0f, UmInspect::DiscGapSu, 0.0f));
      S->SetVerticalAlignment(VAlign_Center);
    }
  }
  UmInNoShadow(BodyText);
  UmInNoShadow(DeckScroll);
  if (BodyText) {
    BodyText->SetScrollBarVisibility(ESlateVisibility::Collapsed);
    BodyText->SetAnimateWheelScrolling(false);
    if (UVerticalBoxSlot* S = Cast<UVerticalBoxSlot>(BodyText->Slot)) S->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
  }
  if (DeckScroll) {
    // the grid scrolls by whole rows (WheelStep); the box draws no bar of its own, the track does
    DeckScroll->SetScrollBarVisibility(ESlateVisibility::Collapsed);
    DeckScroll->SetConsumeMouseWheel(EConsumeMouseWheel::Never);
    DeckScroll->SetAllowOverscroll(false);
    DeckScroll->SetAnimateWheelScrolling(false);
    if (UScrollBoxSlot* S = Cast<UScrollBoxSlot>(DeckGrid ? DeckGrid->Slot : nullptr)) S->SetHorizontalAlignment(HAlign_Center);
  }
  if (DeckGrid) {
    DeckGrid->SetSlotPadding(FMargin(0.5f * UmInspect::GridColGapSu, 0.0f, 0.5f * UmInspect::GridColGapSu, UmInspect::GridRowGapSu));
  }
  if (Track) Track->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("panel.divider")), 0.5f * UmInspect::TrackWSu));
  if (Thumb) Thumb->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("panel.edge")), 0.5f * UmInspect::TrackWSu));
  if (CloseButton) {
    FUmButtonModel C;
    C.IconName = TEXT("ui-close");  // IC-54; «Закрыть» is its tooltip and accessible name (ВР-VS3-SC21-06)
    C.HeightSu = UmInspect::CloseSu;
    C.MinWidthSu = UmInspect::CloseSu;
    CloseButton->ApplyModel(C);
    CloseButton->SetToolTipText(UmText::Get(EUmTable::Hud, TEXT("hud.inspect.close")));
  }
  if (BackButton) {
    FUmButtonModel B;
    B.Variant = EUmButtonVariant::Normal;  // INSPECT has no primary button (ВР-VS3-SC21-06)
    B.Label = UmText::Get(EUmTable::Hud, TEXT("hud.inspect.back"));
    B.HeightSu = UmInspect::BackHSu;
    B.MinWidthSu = UmInspect::BackWSu;
    BackButton->ApplyModel(B);
  }
  if (Card) {
    // the inspector's card is no hand card: no press of its own, the right click goes to the modal (it closes)
    Card->SetVisibility(ESlateVisibility::HitTestInvisible);
  }
  SetFrameSize(UmInspect::ModalSize(false));
  return bFirst;
}

bool UUmScreenInspect::HasAllParts(FString* OutMissing) const {
  FString Base;
  HasBaseParts(&Base);
  TArray<FString> Missing;
  if (!Base.IsEmpty()) Missing.Add(Base);
  if (!Card) Missing.Add(TEXT("Card"));
  if (!TitleText) Missing.Add(TEXT("TitleText"));
  if (!TypeIcon) Missing.Add(TEXT("TypeIcon"));
  if (!TypeText) Missing.Add(TEXT("TypeText"));
  if (!ValueText) Missing.Add(TEXT("ValueText"));
  if (!BoostText) Missing.Add(TEXT("BoostText"));
  if (!BodyText) Missing.Add(TEXT("BodyText"));
  if (!CopiesText) Missing.Add(TEXT("CopiesText"));
  if (!LangToggle) Missing.Add(TEXT("LangToggle"));
  if (!CloseButton) Missing.Add(TEXT("CloseButton"));
  if (!DeckGrid) Missing.Add(TEXT("DeckGrid"));
  if (!BackButton) Missing.Add(TEXT("BackButton"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

// ------------------------------------------------------------------------------------------------ the model in

void UUmScreenInspect::ApplyModel(const FUmInspectModel& InModel) {
  FUmInspectModel Next = InModel;
  if (Next.Mode == EUmInspectMode::Hidden) {
    // QA-005 / SC-22: nothing of a hidden card is kept - no name, type, value, text, copies or deck
    Next.Card = FS09CardView();
    Next.Card.bHidden = true;
    Next.Card.CardId = TEXT("hidden");
    Next.Copies = FUmInspectCopies();
    Next.Deck.Reset();
    Next.DeckIndex = INDEX_NONE;
  }
  auto SameCard = [](const FS09CardView& A, const FS09CardView& B) {
    return A.InstanceId == B.InstanceId && A.CardId == B.CardId && A.Name == B.Name && A.NameRu == B.NameRu &&
           A.CardType == B.CardType && A.AttackValue == B.AttackValue && A.DefenseValue == B.DefenseValue &&
           A.BoostValue == B.BoostValue && A.bHasBoostValue == B.bHasBoostValue && A.Text == B.Text && A.bHidden == B.bHidden;
  };
  const bool bSame = bHasModel && Next.Mode == Model.Mode && Next.Source == Model.Source && SameCard(Next.Card, Model.Card) &&
                     Next.HeroSlug == Model.HeroSlug && Next.HeroName == Model.HeroName && Next.Copies == Model.Copies &&
                     Next.Deck.Num() == Model.Deck.Num() && Next.DeckIndex == Model.DeckIndex;
  if (bSame) return;
  const bool bModeChange = bHasModel && Next.Mode != Model.Mode;
  Model = MoveTemp(Next);
  bHasModel = true;
  if (bModeChange) StartSwitch();
  if (Model.Mode != EUmInspectMode::Deck) {
    FirstRow = FMath::Clamp(FirstRow, 0, UmInspect::MaxFirstRow(Model.Deck.Num()));
  }
  LayoutContent();
}

void UUmScreenInspect::ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu) {
  const bool bChanged = !CanvasSu.Equals(InCanvasSu) || bClassS != bInClassS || !FMath::IsNearlyEqual(PxPerSu, InPxPerSu);
  SetCanvas(InCanvasSu, bInClassS, InPxPerSu);
  if (bChanged) LayoutContent();
}

bool UUmScreenInspect::IsEnglish() const {
  // the build language (ВР-51: RU unless the culture is English), or the other one after Tab
  const bool bBuildEn = UmCardMedia::PreferredLang() == TEXT("en");
  return bAltLang ? !bBuildEn : bBuildEn;
}

void UUmScreenInspect::Open(const FUmInspectModel& InModel) {
  bClosing = false;
  const bool bWasShown = IsShown();
  if (!bWasShown) {
    bAltLang = false;  // a fresh inspector shows the build language (ВР-51)
    FirstRow = 0;
    bHasModel = false;
  }
  ApplyModel(InModel);
  UpdateShotState();
  if (!bWasShown) PlayShow();
}

void UUmScreenInspect::Close(const TCHAR* Why) {
  if (!IsShown() || bClosing) return;
  bClosing = true;
  PlayHide();
  if (Input.OnClose) Input.OnClose(Why);
}

FS09CardView UUmScreenInspect::ShownCard() const {
  if (Model.Mode == EUmInspectMode::DeckCard && Model.Deck.IsValidIndex(Model.DeckIndex)) {
    return UmInspect::DeckCardView(Model.Deck[Model.DeckIndex]);
  }
  return Model.Card;
}

// ------------------------------------------------------------------------------------------------ layout

FBox2D UUmScreenInspect::CardBoxSu() const {
  const FBox2D SlotR = UmInspect::SlotRect(bClassS);
  const EUmCardShow Show = UmInspect::CardShow(bClassS);
  const FVector2D Size = UmCardWidget::ShowSize(Show, IsEnglish() && Show == EUmCardShow::Inspector);
  const FVector2D Min = SlotR.Min + 0.5 * (SlotR.GetSize() - Size);
  return FBox2D(Min, Min + Size);
}

void UUmScreenInspect::LayoutContent() {
  if (!bHasModel) return;
  using namespace UmInspect;
  const bool bS = bClassS;
  const FVector2D Modal = ModalSize(bS);
  SetFrameSize(Modal);
  const bool bDeck = Model.Mode == EUmInspectMode::Deck;
  const bool bHidden = Model.Mode == EUmInspectMode::Hidden;
  const bool bDeckCard = Model.Mode == EUmInspectMode::DeckCard;
  const FBox2D Col = ColumnRect(bS);
  const float LangY = Modal.Y - PadSu - LangRowSu;
  const float BackY = LangY - BackGapSu - BackHSu;
  // ---- the close glyph: the top right of the frame ----
  UmInPlace(CloseButton, FVector2D(Modal.X - PadSu - CloseSu, PadSu), FVector2D(CloseSu, CloseSu));
  UmInShow(CloseButton, true, ESlateVisibility::Visible);
  // ---- the card ----
  UmInShow(Card, !bDeck);
  if (!bDeck) ApplyCardView();
  // ---- the column: the title, the type, the values, the chip, the text ----
  const FS09CardView Shown = ShownCard();
  if (Column) {
    if (bDeck) {
      UmInPlace(Column, FVector2D(PadSu, PadSu), FVector2D(Modal.X - 2.0f * PadSu - CloseSu - 16.0f, GridTitleBandSu - PadSu));
    } else {
      const float Bottom = (bDeckCard ? BackY : LangY) - 16.0f;
      UmInPlace(Column, FVector2D(Col.Min.X, TitleY), FVector2D(Col.GetSize().X, Bottom - TitleY));
    }
    UmInShow(Column, true, ESlateVisibility::SelfHitTestInvisible);
  }
  if (TitleText) {
    FText Title;
    if (bDeck) {
      FFormatNamedArguments A;
      A.Add(TEXT("hero"), FText::FromString(Model.HeroName));
      Title = UmText::Format(EUmTable::Hud, TEXT("hud.inspect.deck.title"), A);
    } else if (bHidden) {
      Title = UmText::Get(EUmTable::Hud, TEXT("hud.inspect.hidden"));
    } else {
      // the name of the shown language: RU - nameRu when the data has it (ВР-VS2-02), EN - name
      Title = FText::FromString(!IsEnglish() && !Shown.NameRu.IsEmpty() ? Shown.NameRu : Shown.Name);
    }
    TitleText->SetText(Title);
    TitleText->SetWrapTextAt(bDeck ? 0.0f : Col.GetSize().X);
    UmInPad(TitleText, 0.0f);
  }
  const FString Type = bHidden || bDeck ? FString() : TypeKey(Shown.CardType);
  if (TypeRow) {
    UmInShow(TypeRow, bHidden || !Type.IsEmpty());
    UmInPad(TypeRow, 31.0f);  // the CX-23 rhythm: a one-line title (64) -> the type row at 128
  }
  if (TypeIcon) {
    const bool bIcon = !Type.IsEmpty();
    UmInShow(TypeIcon, bIcon);
    if (bIcon) {
      const FName Icon = UmDeckRow::TypeIcon(Shown.CardType);
      const float Px = PxPerSu > 0.0f ? PxPerSu : 1.0f;
      if (TypeIcon->GetIconId() != Icon && TypeIcon->SetIcon(Icon, DiscSu, S08IconMotion::ExportSizePx(DiscSu, Px))) {
        TypeIcon->SetDisplaySizeSu(DiscSu);
        TypeIcon->ShowAtRest();
      }
    }
  }
  if (TypeText) {
    // hidden: the owner's hero (SC-22); else the type word next to its disc (never colour alone, 02 §11.4)
    TypeText->SetText(bHidden ? FText::FromString(Model.HeroName) : (Type.IsEmpty() ? FText::GetEmpty() : UmText::Get(EUmTable::Hud, Type)));
  }
  const int32 Value = bHidden || bDeck ? INDEX_NONE : ValueOf(Shown);
  if (ValueText) {
    UmInShow(ValueText, Value != INDEX_NONE);
    if (Value != INDEX_NONE) {
      FFormatNamedArguments A;
      A.Add(TEXT("n"), FText::AsNumber(Value));
      ValueText->SetText(UmText::Format(EUmTable::Hud, TEXT("hud.inspect.value"), A));
    }
    UmInPad(ValueText, 20.0f);
  }
  const bool bBoost = !bHidden && !bDeck && Shown.bHasBoostValue;
  if (BoostText) {
    UmInShow(BoostText, bBoost);
    if (bBoost) {
      FFormatNamedArguments A;
      A.Add(TEXT("n"), FText::AsNumber(Shown.BoostValue));
      BoostText->SetText(UmText::Format(EUmTable::Hud, TEXT("hud.inspect.boost"), A));
    }
    UmInPad(BoostText, Value != INDEX_NONE ? 8.0f : 20.0f);
  }
  // the deck card's «×N» after BOOST (ВР-VS3-SC21-08)
  const bool bChip = bDeckCard && Model.Deck.IsValidIndex(Model.DeckIndex);
  if (UWidget* ChipBox = CopiesChip ? CopiesChip->GetParent() : nullptr) {
    UmInShow(ChipBox, bChip);
    if (UVerticalBoxSlot* S = Cast<UVerticalBoxSlot>(ChipBox->Slot)) {
      S->SetPadding(FMargin(0.0f, 12.0f, 0.0f, 0.0f));
      S->SetHorizontalAlignment(HAlign_Left);
    }
  }
  if (CopiesChipText && bChip) {
    FFormatNamedArguments A;
    A.Add(TEXT("n"), FText::AsNumber(Model.Deck[Model.DeckIndex].Count));
    CopiesChipText->SetText(UmText::Format(EUmTable::Hud, TEXT("hud.inspect.copies.short"), A));
  }
  // the effect text (scrolls), the copies line, the missing scan
  const FString BodyStr = bHidden || bDeck ? FString() : (Shown.Text.IsEmpty() ? Shown.EffectText : Shown.Text);
  if (BodyText) {
    UmInShow(BodyText, !bHidden && !bDeck, ESlateVisibility::Visible);
    if (UVerticalBoxSlot* S = Cast<UVerticalBoxSlot>(BodyText->Slot)) {
      S->SetPadding(FMargin(0.0f, 28.0f, 0.0f, 0.0f));
      S->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
    }
  }
  if (BodyLine) {
    BodyLine->SetText(FText::FromString(BodyStr));
    BodyLine->SetWrapTextAt(Col.GetSize().X);
    UmInShow(BodyLine, !BodyStr.IsEmpty());
  }
  const bool bCopies = Model.Mode == EUmInspectMode::Own && Model.Copies.bKnown;
  if (CopiesText) {
    UmInShow(CopiesText, bCopies);
    if (bCopies) {
      FFormatNamedArguments A;
      A.Add(TEXT("n"), FText::AsNumber(Model.Copies.Deck));
      A.Add(TEXT("h"), FText::AsNumber(Model.Copies.Hand));
      A.Add(TEXT("d"), FText::AsNumber(Model.Copies.Discard));
      CopiesText->SetText(UmText::Format(EUmTable::Hud, TEXT("hud.inspect.copies"), A));
    }
    if (UScrollBoxSlot* S = Cast<UScrollBoxSlot>(CopiesText->Slot)) S->SetPadding(FMargin(0.0f, BodyStr.IsEmpty() ? 0.0f : CopiesGapSu, 0.0f, 0.0f));
  }
  if (ArtMissingText) {
    UmInShow(ArtMissingText, IsArtMissing());
    if (UScrollBoxSlot* S = Cast<UScrollBoxSlot>(ArtMissingText->Slot)) S->SetPadding(FMargin(0.0f, 8.0f, 0.0f, 0.0f));
  }
  // ---- the language row, the back button ----
  if (LangToggle) {
    UmInPlace(LangToggle, FVector2D(Col.Min.X, LangY), FVector2D(Col.GetSize().X, LangRowSu));
    UmInShow(LangToggle, !bDeck && !bHidden && CanToggleLang());
  }
  if (BackButton) {
    UmInPlace(BackButton, FVector2D(Col.Min.X, BackY), FVector2D(BackWSu, BackHSu));
    UmInShow(BackButton, bDeckCard, ESlateVisibility::Visible);
  }
  // ---- the deck grid ----
  ApplyDeckGrid();
  UpdateShotState();
}

void UUmScreenInspect::ApplyCardView() {
  if (!Card) return;
  const bool bHidden = Model.Mode == EUmInspectMode::Hidden;
  FUmCardState S;
  S.Show = UmInspect::CardShow(bClassS);
  S.HeroSlug = Model.HeroSlug;
  S.bFaceDown = bHidden;  // the owner's back (ВР-50); the widget keeps no face then (QA-005)
  S.Lang = bHidden ? FString() : (IsEnglish() ? TEXT("en") : TEXT("ru"));
  S.PxPerSu = PxPerSu;
  Card->ApplyModel(ShownCard(), S);
  const FBox2D Box = CardBoxSu();
  UmInPlace(Card, Box.Min, Box.GetSize());
}

void UUmScreenInspect::EnsureGridCells(int32 N) {
  if (!DeckGrid || !WidgetTree) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UClass* CardClass = UmGameHudSlots::WbpOrNative(UUmCardWidget::StaticClass(), UUmCardWidget::WidgetBlueprintPath);
  while (GridCells.Num() < N) {
    const int32 I = GridCells.Num();
    FGridCell C;
    UHorizontalBox* Row = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());
    C.Cell = Row;
    C.Card = CreateWidget<UUmCardWidget>(this, CardClass);
    if (!C.Card) break;
    C.Card->SetSyncLoad(bSheetSync);
    if (SheetClockMs >= 0.0) C.Card->SetClockOverrideMs(SheetClockMs);
    Row->AddChildToHorizontalBox(C.Card);
    USizeBox* ChipBox = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
    ChipBox->SetWidthOverride(UmInspect::GridChipWSu);
    ChipBox->SetHeightOverride(UmInspect::GridChipHSu);
    if (UHorizontalBoxSlot* S = Row->AddChildToHorizontalBox(ChipBox)) {
      S->SetPadding(FMargin(UmInspect::GridChipGapSu, 0.0f, 0.0f, 0.0f));
      S->SetVerticalAlignment(VAlign_Center);
    }
    C.Chip = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
    if (const FSlateBrush* Skin = Theme.Skin(TEXT("chip"))) C.Chip->SetBrush(*Skin);
    C.Chip->SetHorizontalAlignment(HAlign_Center);
    C.Chip->SetVerticalAlignment(VAlign_Center);
    C.Chip->SetPadding(FMargin(0.0f));
    ChipBox->SetContent(C.Chip);
    C.ChipText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
    UmInText(C.ChipText, TEXT("type.caption"), TEXT("text.primary"));  // Roboto Regular: equal-width digits
    C.Chip->SetContent(C.ChipText);
    C.Chip->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (UUniformGridSlot* G = DeckGrid->AddChildToUniformGrid(Row, I / UmInspect::GridColumns, I % UmInspect::GridColumns)) {
      G->SetHorizontalAlignment(HAlign_Left);
      G->SetVerticalAlignment(VAlign_Top);
    }
    Row->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
    // a click opens the card in the same modal (the press on the release, DE-014)
    const FName Id(*FString::Printf(TEXT("hud.inspect.grid.%d"), I));
    TWeakObjectPtr<UUmScreenInspect> WeakThis(this);
    C.Card->SetPress(Id, Arbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, Id](const FS09HudPressOutcome& O) {
      if (UUmScreenInspect* Self = WeakThis.Get()) Self->OnPressOutcome(Id, O);
    }));
    GridKeep.Add(Row);
    GridKeep.Add(C.Card);
    GridCells.Add(C);
  }
}

void UUmScreenInspect::ApplyDeckGrid() {
  using namespace UmInspect;
  const bool bDeck = Model.Mode == EUmInspectMode::Deck;
  UmInShow(DeckScroll, bDeck, ESlateVisibility::Visible);
  UmInShow(Track, bDeck && MaxFirstRow(Model.Deck.Num()) > 0);
  UmInShow(Thumb, bDeck && MaxFirstRow(Model.Deck.Num()) > 0);
  if (!bDeck) return;
  const FBox2D Grid = GridRect(bClassS);
  UmInPlace(DeckScroll, Grid.Min, Grid.GetSize());
  const FVector2D Modal = ModalSize(bClassS);
  UmInPlace(Track, FVector2D(Modal.X - PadSu - TrackWSu, Grid.Min.Y), FVector2D(TrackWSu, GridViewSu));
  const int32 N = Model.Deck.Num();
  EnsureGridCells(N);
  for (int32 I = 0; I < GridCells.Num(); ++I) {
    FGridCell& C = GridCells[I];
    const bool bOn = I < N;
    UmInShow(C.Cell, bOn, ESlateVisibility::SelfHitTestInvisible);
    if (!bOn || !C.Card) continue;
    FUmCardState S;
    S.Show = EUmCardShow::DeckGrid;
    S.HeroSlug = Model.HeroSlug;
    S.Lang = IsEnglish() ? TEXT("en") : TEXT("ru");
    S.PxPerSu = PxPerSu;
    C.Card->ApplyModel(DeckCardView(Model.Deck[I]), S);
    C.Card->SetPress(FName(*FString::Printf(TEXT("hud.inspect.grid.%d"), I)), Arbiter, FS09OnHudPressOutcome::CreateLambda(
                         [WeakThis = TWeakObjectPtr<UUmScreenInspect>(this), I](const FS09HudPressOutcome& O) {
                           if (UUmScreenInspect* Self = WeakThis.Get()) Self->OnPressOutcome(FName(*FString::Printf(TEXT("hud.inspect.grid.%d"), I)), O);
                         }));
    C.Card->SetVisibility(ESlateVisibility::Visible);
    if (C.ChipText) {
      FFormatNamedArguments A;
      A.Add(TEXT("n"), FText::AsNumber(Model.Deck[I].Count));
      C.ChipText->SetText(UmText::Format(EUmTable::Hud, TEXT("hud.inspect.copies.short"), A));
    }
  }
  FirstRow = FMath::Clamp(FirstRow, 0, MaxFirstRow(N));
  if (DeckScroll) DeckScroll->SetScrollOffset(FirstRow * GridRowStepSu);
  ApplyScrollbar();
}

void UUmScreenInspect::ApplyScrollbar() {
  using namespace UmInspect;
  const int32 Max = MaxFirstRow(Model.Deck.Num());
  if (!Thumb || Max <= 0) return;
  const FBox2D Grid = GridRect(bClassS);
  const int32 Rows = GridRows(Model.Deck.Num());
  const float Visible = static_cast<float>(Rows - Max);
  const float H = GridViewSu * Visible / static_cast<float>(Rows);
  const float Y = Grid.Min.Y + (GridViewSu - H) * static_cast<float>(FirstRow) / static_cast<float>(Max);
  const FVector2D Modal = ModalSize(bClassS);
  UmInPlace(Thumb, FVector2D(Modal.X - PadSu - TrackWSu, Y), FVector2D(TrackWSu, H));
}

// ------------------------------------------------------------------------------------------------ the grid and the language

void UUmScreenInspect::OpenDeckCard(int32 Index) {
  if ((Model.Mode != EUmInspectMode::Deck && Model.Mode != EUmInspectMode::DeckCard) || !Model.Deck.IsValidIndex(Index)) return;
  FUmInspectModel Next = Model;
  Next.Mode = EUmInspectMode::DeckCard;
  Next.DeckIndex = Index;
  ApplyModel(Next);
  if (Input.OnPage) Input.OnPage(Index);
}

void UUmScreenInspect::BackToGrid() {
  if (Model.Mode != EUmInspectMode::DeckCard) return;
  FUmInspectModel Next = Model;
  Next.Mode = EUmInspectMode::Deck;
  Next.DeckIndex = INDEX_NONE;
  ApplyModel(Next);
  if (Input.OnPage) Input.OnPage(INDEX_NONE);
}

bool UUmScreenInspect::WheelStep(bool bUp) {
  if (Model.Mode != EUmInspectMode::Deck) return false;
  const int32 Next = FMath::Clamp(FirstRow + (bUp ? -1 : 1), 0, UmInspect::MaxFirstRow(Model.Deck.Num()));
  if (Next == FirstRow) return false;
  FirstRow = Next;
  if (DeckScroll) DeckScroll->SetScrollOffset(FirstRow * UmInspect::GridRowStepSu);
  ApplyScrollbar();
  return true;
}

UUmCardWidget* UUmScreenInspect::GetGridCard(int32 I) const { return GridCells.IsValidIndex(I) ? GridCells[I].Card.Get() : nullptr; }

FString UUmScreenInspect::GetGridChipText(int32 I) const {
  return GridCells.IsValidIndex(I) && GridCells[I].ChipText ? GridCells[I].ChipText->GetText().ToString() : FString();
}

bool UUmScreenInspect::CanToggleLang() const {
  if (Model.Mode != EUmInspectMode::Own && Model.Mode != EUmInspectMode::DeckCard) return false;
  const FS09CardView Shown = ShownCard();
  const FString Slug = UmCardWidget::Slug(Shown.Name);
  return !Model.HeroSlug.IsEmpty() && !Slug.IsEmpty() && UmCardMedia::FindCard(Model.HeroSlug, Slug, TEXT("ru")) &&
         UmCardMedia::FindCard(Model.HeroSlug, Slug, TEXT("en"));
}

void UUmScreenInspect::ToggleLang() {
  if (!CanToggleLang()) return;
  bAltLang = !bAltLang;
  LayoutContent();
}

// ------------------------------------------------------------------------------------------------ input

void UUmScreenInspect::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput) {
  Arbiter = InArbiter;
  Input = MoveTemp(InInput);
  TWeakObjectPtr<UUmScreenInspect> WeakThis(this);
  auto Bind = [&WeakThis, this](UUmButton* B, const TCHAR* Id) {
    if (!B) return;
    const FName Name(Id);
    B->SetPress(Name, Arbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, Name](const FS09HudPressOutcome& O) {
      if (UUmScreenInspect* Self = WeakThis.Get()) Self->OnPressOutcome(Name, O);
    }));
  };
  Bind(CloseButton, TEXT("hud.inspect.close"));
  Bind(BackButton, TEXT("hud.inspect.back"));
  for (int32 I = 0; I < GridCells.Num(); ++I) {
    const FName Id(*FString::Printf(TEXT("hud.inspect.grid.%d"), I));
    if (GridCells[I].Card) {
      GridCells[I].Card->SetPress(Id, Arbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, Id](const FS09HudPressOutcome& O) {
        if (UUmScreenInspect* Self = WeakThis.Get()) Self->OnPressOutcome(Id, O);
      }));
    }
  }
}

void UUmScreenInspect::OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome) {
  if (Outcome.Result != ES09HudPressResult::Act) return;
  const FString S = Id.ToString();
  if (S == TEXT("hud.inspect.close")) {
    Close(TEXT("button"));
  } else if (S == TEXT("hud.inspect.back")) {
    BackToGrid();
  } else if (S.StartsWith(TEXT("hud.inspect.grid."))) {
    OpenDeckCard(FCString::Atoi(*S.RightChop(17)));
  }
}

void UUmScreenInspect::SetSyncLoadForSheet(bool bOn) {
  bSheetSync = bOn;
  if (Card) Card->SetSyncLoad(bOn);
  for (FGridCell& C : GridCells) {
    if (C.Card) C.Card->SetSyncLoad(bOn);
  }
}

void UUmScreenInspect::SetSheetClockMs(double Ms) {
  SheetClockMs = Ms;
  SetClockOverrideMs(Ms);
  if (Card) Card->SetClockOverrideMs(Ms);
  for (FGridCell& C : GridCells) {
    if (C.Card) C.Card->SetClockOverrideMs(Ms);
  }
}

void UUmScreenInspect::SimulatePressForTest(FName Id) {
  if (!Arbiter.IsValid()) Arbiter = MakeShared<FS09HudPressArbiter>();
  Arbiter->Press(Id, Arbiter->Now());
  OnPressOutcome(Id, FS09HudPressArbiter::Decide(Arbiter->Release(Id, Arbiter->Now()), FS09Reason()));
}

bool UUmScreenInspect::HandleKey(const FKey& Key) {
  if (!IsShown() || bClosing) return false;
  if (Key == EKeys::Escape) {
    Close(TEXT("esc"));
  } else if (Key == EKeys::I) {
    Close(TEXT("key-i"));
  } else if (Key == EKeys::Tab) {
    ToggleLang();
  } else if (Key == EKeys::BackSpace) {
    BackToGrid();
  }
  return true;  // the modal owns the keyboard (04 §1: the input outside a modal is closed)
}

FReply UUmScreenInspect::NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (InMouseEvent.GetEffectingButton() == EKeys::RightMouseButton) return FReply::Handled();  // closes on the release
  return Super::NativeOnMouseButtonDown(InGeometry, InMouseEvent);
}

FReply UUmScreenInspect::NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  if (InMouseEvent.GetEffectingButton() == EKeys::RightMouseButton) Close(TEXT("rmb"));
  return FReply::Handled();
}

FReply UUmScreenInspect::NativeOnMouseWheel(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  WheelStep(InMouseEvent.GetWheelDelta() > 0.0f);
  return FReply::Handled();  // the board never zooms under a modal
}

// ------------------------------------------------------------------------------------------------ the clock, the trace

void UUmScreenInspect::StartSwitch() {
  SwitchStartMs = NowMs();
  ContentAlphaNow = 0.0f;
  if (Content) Content->SetRenderOpacity(0.0f);
}

void UUmScreenInspect::StepInspect() {
  if (SwitchStartMs >= 0.0) {
    const float Len = IsReduced() ? UmInspect::SwitchReducedMs : UmInspect::SwitchMs;
    const float T = static_cast<float>(NowMs() - SwitchStartMs);
    ContentAlphaNow = FMath::Clamp(T / Len, 0.0f, 1.0f);
    if (ContentAlphaNow >= 1.0f) SwitchStartMs = -1.0;
    if (Content) Content->SetRenderOpacity(ContentAlphaNow);
  }
  UpdateShotState();
  if (ArtMissingText && bHasModel) UmInShow(ArtMissingText, IsArtMissing());
}

void UUmScreenInspect::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  StepInspect();
}

FString UUmScreenInspect::GetTitle() const { return TitleText ? TitleText->GetText().ToString() : FString(); }

FString UUmScreenInspect::GetTypeText() const {
  return TypeText && TypeRow && TypeRow->GetVisibility() != ESlateVisibility::Collapsed ? TypeText->GetText().ToString() : FString();
}

FString UUmScreenInspect::GetValueText() const {
  return ValueText && ValueText->GetVisibility() != ESlateVisibility::Collapsed ? ValueText->GetText().ToString() : FString();
}

FString UUmScreenInspect::GetBoostText() const {
  return BoostText && BoostText->GetVisibility() != ESlateVisibility::Collapsed ? BoostText->GetText().ToString() : FString();
}

FString UUmScreenInspect::GetBodyText() const {
  return BodyLine && BodyText && BodyText->GetVisibility() != ESlateVisibility::Collapsed &&
                 BodyLine->GetVisibility() != ESlateVisibility::Collapsed
             ? BodyLine->GetText().ToString()
             : FString();
}

FString UUmScreenInspect::GetCopiesText() const {
  return CopiesText && CopiesText->GetVisibility() != ESlateVisibility::Collapsed ? CopiesText->GetText().ToString() : FString();
}

bool UUmScreenInspect::IsLoadingScan() const {
  if (Model.Mode != EUmInspectMode::Deck) return Card && Card->IsLoading();
  // the grid: any shown scan still streaming in
  for (int32 I = 0; I < GridCells.Num() && I < Model.Deck.Num(); ++I) {
    if (GridCells[I].Card && GridCells[I].Card->IsLoading()) return true;
  }
  return false;
}

void UUmScreenInspect::UpdateShotState() {
  // the gate state (04 §7.1) follows the content: while the 150 ms switch fades the content in, the previous state
  // stands (a -S08ScreenShots frame never catches a half-faded content); a grid with scans still loading is «loading»
  if (!bHasModel || (SwitchStartMs >= 0.0 && !GetScreenState().IsNone())) return;
  const bool bLoading = IsLoadingScan();
  SetScreenState(FName(Model.Mode == EUmInspectMode::Deck && bLoading ? TEXT("loading") : UmInspect::StateName(Model.Mode, bLoading)));
}

bool UUmScreenInspect::IsArtMissing() const {
  return Card && (Model.Mode == EUmInspectMode::Own || Model.Mode == EUmInspectMode::DeckCard) && !Card->IsLoading() &&
         Card->GetFace() == EUmCardFace::Fallback && !Card->IsLegacy();
}

void UUmScreenInspect::CollectShotLines(TArray<FString>& Out) const {
  if (!IsShown() || !bHasModel) return;
  const bool bVisible = UmGameHudSlots::ShownByProperty(this) || GetVisibility() == ESlateVisibility::Visible;
  const FBox2D R = FrameRectSu();
  const FS08ScreenRect Rect(R.Min.X * PxPerSu, R.Min.Y * PxPerSu, R.Max.X * PxPerSu, R.Max.Y * PxPerSu);
  const bool bDeck = Model.Mode == EUmInspectMode::Deck;
  const FString Face = bDeck || !Card ? FString(TEXT("-")) : FString(UmCardWidget::FaceName(Card->GetFace()));
  const float Cap = bDeck || !Card ? 0.0f : Card->GetFit().Scale;
  Out.Add(S08ArtHud::FormatWidgetLineEx(
      GetUiId(), TEXT("umg"), UmInspect::StateName(Model.Mode, IsLoadingScan()), FString(), Rect, bVisible && !Rect.IsEmpty(), bVisible,
      SourceName(),
      FString::Printf(TEXT("modal=1 class=%s alpha=%.2f mode=%s source=%s face=%s cap=%.3f grid=%d first=%d copies=%d lang=%d primary=0"),
                      bClassS ? TEXT("S") : TEXT("L"), GetAlpha(), UmInspect::ModeName(Model.Mode),
                      UmInspect::SourceName(Model.Source), *Face, Cap, bDeck ? Model.Deck.Num() : 0, FirstRow,
                      UmInspect::CopiesSum(Model.Deck), CanToggleLang() ? 1 : 0)));
  if (!bDeck && Card) {
    Card->CollectShotLines(Out);
  } else if (bDeck) {
    for (int32 I = 0; I < GridCells.Num() && I < Model.Deck.Num(); ++I) {
      if (GridCells[I].Card) GridCells[I].Card->CollectShotLines(Out);
    }
  }
}

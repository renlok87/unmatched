// VS-7 SC-14...SC-18: ROOM - see UmScreenRoom.h.
#include "UmScreenRoom.h"

#include "../S08ArtHud.h"
#include "UmBoardCard.h"
#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHudScale.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Image.h"
#include "Components/NamedSlot.h"
#include "Components/ScrollBox.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/UniformGridPanel.h"
#include "Components/UniformGridSlot.h"

using namespace UmRoomUi;

const TCHAR* const UUmScreenRoom::WidgetBlueprintPath = TEXT("/Game/S08/UI/Screens/WBP_UI_SCR_ROOM");

UClass* UUmScreenRoom::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmScreenRoom::StaticClass(), WidgetBlueprintPath); }

// ------------------------------------------------------------------------------------------------ the model

namespace UmRoom {
FUmRoomLayout Layout(const FVector2D& CanvasSu, bool bClassS) {
  FUmRoomLayout L;
  L.bClassS = bClassS;
  const float W = CanvasSu.X, H = CanvasSu.Y;
  if (!bClassS) {
    // 04 §1.4 table: the 1080p column, the 720p column at 1707 x 960 su
    const bool bWide = W >= 1800.0f;
    const float SlotW = bWide ? 560.0f : 500.0f;
    const float Rx = 24.0f + SlotW + 24.0f;
    const float Rw = W - 24.0f - Rx;
    L.Header = {24.0f, 24.0f, W - 48.0f, 64.0f};
    L.Slot0 = {24.0f, 112.0f, SlotW, 200.0f};
    L.Slot1 = {24.0f, 328.0f, SlotW, 200.0f};
    L.Grid = {Rx, 112.0f, Rw, bWide ? 560.0f : 480.0f};
    L.Board = {Rx, bWide ? 688.0f : 608.0f, Rw, bWide ? 160.0f : 140.0f};
    L.Deck = {Rx, bWide ? 864.0f : 764.0f, Rw, bWide ? 80.0f : 68.0f};
    L.Bottom = {24.0f, H - 112.0f, W - 48.0f, 88.0f};
    L.CardSu = FVector2D(300.0, 420.0);
  } else {
    // ВР-VS4-SC14-11: margins 16; the left column 300 su; two compact 360x240 cards and the board block at the right
    const float Rx = 332.0f;
    const float Rw = W - 16.0f - Rx;
    L.Header = {16.0f, 16.0f, W - 32.0f, 64.0f};
    L.Slot0 = {16.0f, 96.0f, 300.0f, 136.0f};
    L.Slot1 = {16.0f, 248.0f, 300.0f, 136.0f};
    L.Deck = {16.0f, 400.0f, 300.0f, FMath::Max(112.0f, H - 96.0f - 16.0f - 400.0f)};
    L.Grid = {Rx, 96.0f, Rw, 240.0f};
    L.Board = {Rx, 352.0f, Rw, FMath::Max(176.0f, H - 96.0f - 16.0f - 352.0f)};
    L.Bottom = {16.0f, H - 96.0f, W - 32.0f, 80.0f};
    L.CardSu = FVector2D(360.0, 240.0);
  }
  L.Columns = FMath::Clamp(FMath::FloorToInt((L.Grid.W + 16.0f) / (L.CardSu.X + 16.0f)), 1, 4);
  return L;
}

const TCHAR* StateName(EUmRoomPhase Phase, const FUmRoomModel& M) {
  if (Phase != EUmRoomPhase::Room) return TEXT("countdown");
  const bool bOwnHero = !M.OwnHeroId.IsEmpty();
  if (bOwnHero && M.bOwnReady && (M.bVsAi || (M.bOppPresent && M.bOppReady))) return TEXT("ready");
  if (bOwnHero) return TEXT("picked");
  return TEXT("waiting");
}

FName StartWhy(const FUmRoomModel& M) {
  if (M.OwnHeroId.IsEmpty()) return FName(TEXT("why.room.no.hero"));
  if (M.bVsAi) return M.bOwnReady ? NAME_None : FName(TEXT("why.room.not.ready"));
  if (!M.bOwnReady || !M.bOppPresent || !M.bOppHero || !M.bOppReady) return FName(TEXT("why.room.not.ready"));
  return NAME_None;
}

FName ReadyWhy(const FUmRoomModel& M) { return M.OwnHeroId.IsEmpty() ? FName(TEXT("why.room.no.hero")) : NAME_None; }

int32 CountDigit(double ElapsedMs) {
  if (ElapsedMs < 0.0) return 3;
  const int32 Step = FMath::FloorToInt(ElapsedMs / CountStepMs);
  return Step >= 3 ? 0 : 3 - Step;
}
}  // namespace UmRoom

// ------------------------------------------------------------------------------------------------ the tree

namespace {
const TCHAR* const UmRmPanels[] = {TEXT("Header"), TEXT("BoardBlock"), TEXT("DeckRow"), TEXT("BottomStrip")};
const TCHAR* const UmRmTexts[] = {TEXT("TitleText"), TEXT("ModeLabel"), TEXT("ModeText"), TEXT("BoardTitle"), TEXT("BoardWhy"),
                                  TEXT("DeckCount"), TEXT("DeckWhy"), TEXT("StatusText"), TEXT("WhyText")};
const TCHAR* const UmRmButtons[] = {TEXT("CopyButton"), TEXT("MenuButton"), TEXT("DeckButton"), TEXT("LeaveButton"),
                                    TEXT("ReadyButton"), TEXT("StartButton")};

template <typename T>
T* UmRmFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

FString UmRmUpper(const TCHAR* Key) { return S(Key).ToUpper().ToString(); }
}  // namespace

bool UUmScreenRoom::AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  UCanvasPanel* ContentW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Content")));
  ContentW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(ContentW, Parent)) return Fail(TEXT("Content"));
  for (const TCHAR* Name : UmRmPanels) {
    UBorder* B = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(Name));
    B->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (!Attach(B, ContentW)) return Fail(Name);
  }
  for (const TCHAR* Name : UmRmTexts) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (!Attach(T, ContentW)) return Fail(Name);
  }
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  for (const TCHAR* Name : UmRmButtons) {
    if (!Attach(Tree.ConstructWidget<UUmButton>(ButtonClass, FName(Name)), ContentW)) return Fail(Name);
  }
  for (const TCHAR* Name : {TEXT("Slot0"), TEXT("Slot1")}) {
    if (!Attach(Tree.ConstructWidget<UUmRoomSlot>(UUmRoomSlot::StaticClass(), FName(Name)), ContentW)) return Fail(Name);
  }
  UScrollBox* Scroll = Tree.ConstructWidget<UScrollBox>(UScrollBox::StaticClass(), FName(TEXT("HeroScroll")));
  if (!Attach(Scroll, ContentW)) return Fail(TEXT("HeroScroll"));
  if (!Attach(Tree.ConstructWidget<UUniformGridPanel>(UUniformGridPanel::StaticClass(), FName(TEXT("HeroGrid"))), Scroll)) return Fail(TEXT("HeroGrid"));
  UCanvasPanel* Cards = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("BoardCards")));
  Cards->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(Cards, ContentW)) return Fail(TEXT("BoardCards"));
  // the countdown layer last (over everything; the veil takes the pointer)
  UImage* CountVeilW = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("CountVeil")));
  if (!Attach(CountVeilW, ContentW)) return Fail(TEXT("CountVeil"));
  UBorder* CountPanelW = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("CountPanel")));
  CountPanelW->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(CountPanelW, ContentW)) return Fail(TEXT("CountPanel"));
  if (!Attach(Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("CountText"))), CountPanelW)) return Fail(TEXT("CountText"));
  return true;
}

bool UUmScreenRoom::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  if (!UUmScreenBase::BuildDefaultTree(Tree, Attach, OutError)) return false;
  UNamedSlot* BodyW = Cast<UNamedSlot>(Tree.FindWidget(FName(TEXT("Body"))));
  if (!BodyW) {
    if (OutError) *OutError = TEXT("no Body");
    return false;
  }
  return AttachContent(Tree, BodyW, Attach, OutError);
}

void UUmScreenRoom::BuildContent() {
  if (!WidgetTree || !Body || Body->GetContent()) return;
  FString Problem;
  auto AddTo = [](UWidget* Child, UPanelWidget* Parent) { return Parent && Parent->AddChild(Child) != nullptr; };
  if (!AttachContent(*WidgetTree, Body, AddTo, &Problem)) UE_LOG(LogTemp, Error, TEXT("UMHUD room content: %s"), *Problem);
}

void UUmScreenRoom::BindParts() {
  Content = UmRmFind<UCanvasPanel>(WidgetTree, TEXT("Content"));
  Header = UmRmFind<UBorder>(WidgetTree, TEXT("Header"));
  BoardBlock = UmRmFind<UBorder>(WidgetTree, TEXT("BoardBlock"));
  DeckRow = UmRmFind<UBorder>(WidgetTree, TEXT("DeckRow"));
  BottomStrip = UmRmFind<UBorder>(WidgetTree, TEXT("BottomStrip"));
  TitleText = UmRmFind<UTextBlock>(WidgetTree, TEXT("TitleText"));
  ModeLabel = UmRmFind<UTextBlock>(WidgetTree, TEXT("ModeLabel"));
  ModeText = UmRmFind<UTextBlock>(WidgetTree, TEXT("ModeText"));
  BoardTitle = UmRmFind<UTextBlock>(WidgetTree, TEXT("BoardTitle"));
  BoardWhy = UmRmFind<UTextBlock>(WidgetTree, TEXT("BoardWhy"));
  DeckCount = UmRmFind<UTextBlock>(WidgetTree, TEXT("DeckCount"));
  DeckWhy = UmRmFind<UTextBlock>(WidgetTree, TEXT("DeckWhy"));
  StatusText = UmRmFind<UTextBlock>(WidgetTree, TEXT("StatusText"));
  WhyText = UmRmFind<UTextBlock>(WidgetTree, TEXT("WhyText"));
  CopyButton = UmRmFind<UUmButton>(WidgetTree, TEXT("CopyButton"));
  MenuButton = UmRmFind<UUmButton>(WidgetTree, TEXT("MenuButton"));
  DeckButton = UmRmFind<UUmButton>(WidgetTree, TEXT("DeckButton"));
  LeaveButton = UmRmFind<UUmButton>(WidgetTree, TEXT("LeaveButton"));
  ReadyButton = UmRmFind<UUmButton>(WidgetTree, TEXT("ReadyButton"));
  StartButton = UmRmFind<UUmButton>(WidgetTree, TEXT("StartButton"));
  Slot0 = UmRmFind<UUmRoomSlot>(WidgetTree, TEXT("Slot0"));
  Slot1 = UmRmFind<UUmRoomSlot>(WidgetTree, TEXT("Slot1"));
  HeroScroll = UmRmFind<UScrollBox>(WidgetTree, TEXT("HeroScroll"));
  HeroGrid = UmRmFind<UUniformGridPanel>(WidgetTree, TEXT("HeroGrid"));
  BoardCards = UmRmFind<UCanvasPanel>(WidgetTree, TEXT("BoardCards"));
  CountVeil = UmRmFind<UImage>(WidgetTree, TEXT("CountVeil"));
  CountPanel = UmRmFind<UBorder>(WidgetTree, TEXT("CountPanel"));
  CountText = UmRmFind<UTextBlock>(WidgetTree, TEXT("CountText"));
}

void UUmScreenRoom::BuildBoards() {
  if (!BoardCards || !WidgetTree || Boards.Num() == 2) return;
  for (int32 I = 0; I < 2; ++I) {
    UUmBoardCard* Card = WidgetTree->ConstructWidget<UUmBoardCard>(UUmBoardCard::StaticClass(), FName(*FString::Printf(TEXT("BoardCard%d"), I)));
    BoardCards->AddChild(Card);
    Boards.Add(Card);
  }
  Boards[0]->Setup(UmLobby::MarmorealId, UmLobby::MarmorealName);
  Boards[1]->Setup(UmLobby::SarpedonId, UmLobby::SarpedonName);
}

bool UUmScreenRoom::Initialize() {
  SetIsFocusable(true);
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  SetUiId(TEXT("UI-SCR-ROOM"));
  SetScreenState(FName(TEXT("waiting")));
  BindParts();
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const float ScalePx = UmHudScale::Current().PxPerSu();
  if (Header) {
    if (const FSlateBrush* Panel = Theme.SkinFor(TEXT("panel"), ScalePx)) Header->SetBrush(*Panel);
  }
  for (UBorder* B : {BoardBlock.Get(), DeckRow.Get(), BottomStrip.Get()}) {
    if (const FSlateBrush* Screen = Theme.SkinFor(TEXT("modal"), ScalePx)) {
      if (B) B->SetBrush(*Screen);
    }
  }
  if (CountPanel) {
    if (const FSlateBrush* Screen = Theme.SkinFor(TEXT("modal"), ScalePx)) CountPanel->SetBrush(*Screen);
    CountPanel->SetHorizontalAlignment(HAlign_Center);
    CountPanel->SetVerticalAlignment(VAlign_Center);
  }
  if (CountVeil) {
    FLinearColor VeilColor = Theme.Color(TEXT("card.navy"));
    VeilColor.A = UmRoom::CountVeilAlpha;
    CountVeil->SetColorAndOpacity(VeilColor);
    CountVeil->SetVisibility(ESlateVisibility::Collapsed);
  }
  Style(TitleText, TEXT("type.title"), TEXT("text.primary"));
  Style(ModeLabel, TEXT("type.body"), TEXT("text.secondary"));
  Style(ModeText, TEXT("type.body"), TEXT("text.primary"));
  Style(BoardTitle, TEXT("type.heading"), TEXT("text.primary"));
  Style(BoardWhy, TEXT("type.caption"), TEXT("text.secondary"));
  Style(DeckCount, TEXT("type.body"), TEXT("text.primary"));
  Style(DeckWhy, TEXT("type.caption"), TEXT("text.secondary"));
  Style(StatusText, TEXT("type.body"), TEXT("text.primary"));
  Style(WhyText, TEXT("type.caption"), TEXT("text.secondary"));
  Style(CountText, TEXT("type.display"), TEXT("text.primary"));
  if (StatusText) StatusText->SetJustification(ETextJustify::Center);
  if (WhyText) WhyText->SetJustification(ETextJustify::Right);
  if (BoardWhy) BoardWhy->SetAutoWrapText(true);
  if (CountText) CountText->SetJustification(ETextJustify::Center);
  if (HeroGrid) HeroGrid->SetSlotPadding(FMargin(0.0f, 0.0f, 16.0f, 16.0f));
  BuildBoards();
  if (Frame) Frame->SetBrush(FSlateNoResource());
  Refresh();
  return bFirst;
}

bool UUmScreenRoom::HasAllParts(FString* OutMissing) const {
  FString Base;
  HasBaseParts(&Base);
  TArray<FString> Missing;
  if (!Base.IsEmpty()) Missing.Add(Base);
  auto Need = [&Missing](const UObject* P, const TCHAR* Name) {
    if (!P) Missing.Add(Name);
  };
  Need(Header, TEXT("Header"));
  Need(TitleText, TEXT("TitleText"));
  Need(CopyButton, TEXT("CopyButton"));
  Need(ModeLabel, TEXT("ModeLabel"));
  Need(ModeText, TEXT("ModeText"));
  Need(MenuButton, TEXT("MenuButton"));
  Need(Slot0, TEXT("Slot0"));
  Need(Slot1, TEXT("Slot1"));
  Need(HeroScroll, TEXT("HeroScroll"));
  Need(HeroGrid, TEXT("HeroGrid"));
  Need(BoardBlock, TEXT("BoardBlock"));
  Need(BoardTitle, TEXT("BoardTitle"));
  Need(BoardCards, TEXT("BoardCards"));
  Need(BoardWhy, TEXT("BoardWhy"));
  Need(DeckRow, TEXT("DeckRow"));
  Need(DeckCount, TEXT("DeckCount"));
  Need(DeckButton, TEXT("DeckButton"));
  Need(DeckWhy, TEXT("DeckWhy"));
  Need(BottomStrip, TEXT("BottomStrip"));
  Need(LeaveButton, TEXT("LeaveButton"));
  Need(StatusText, TEXT("StatusText"));
  Need(ReadyButton, TEXT("ReadyButton"));
  Need(StartButton, TEXT("StartButton"));
  Need(WhyText, TEXT("WhyText"));
  Need(CountVeil, TEXT("CountVeil"));
  Need(CountPanel, TEXT("CountPanel"));
  Need(CountText, TEXT("CountText"));
  if (Boards.Num() != 2) Missing.Add(TEXT("BoardCards[2]"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmScreenRoom::ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu) {
  SetCanvas(InCanvasSu, bInClassS, InPxPerSu);
  if (Frame) Frame->SetBrush(FSlateNoResource());
  Layout();
}

// ------------------------------------------------------------------------------------------------ model in

void UUmScreenRoom::ApplyModel(const FUmRoomModel& InModel) {
  Model = InModel;
  if (Boards.Num() == 2) {
    for (int32 I = 0; I < 2; ++I) {
      const FString Name = Model.BoardNames[I].IsEmpty() ? FString(I == 0 ? UmLobby::MarmorealName : UmLobby::SarpedonName) : Model.BoardNames[I];
      if (Boards[I]->GetNameText() != Name) Boards[I]->Setup(Boards[I]->GetBoardId(), Name);
    }
  }
  SyncCards();
  Refresh();  // the texts first: the layout measures them
  Layout();
}

void UUmScreenRoom::SetPhase(EUmRoomPhase InPhase, int32 InDigit) {
  if (Phase == InPhase && Digit == InDigit) return;
  Phase = InPhase;
  Digit = InDigit;
  Refresh();
  Layout();
}

void UUmScreenRoom::SyncCards() {
  if (!HeroGrid || !WidgetTree) return;
  while (CardPool.Num() < Model.Heroes.Num()) {
    UUmHeroCard* Card = CreateWidget<UUmHeroCard>(this, UUmHeroCard::StaticClass());
    USizeBox* Box = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
    if (!Card || !Box) break;
    Box->AddChild(Card);
    CardBoxes.Add(Box);
    BindCardPress(Card, CardPool.Num());
    CardPool.Add(Card);
  }
}

// ------------------------------------------------------------------------------------------------ layout

void UUmScreenRoom::Layout() {
  const FUmRoomLayout L = UmRoom::Layout(CanvasSu, bClassS);
  const FVector2D O = FrameRectSu().Min;
  auto P = [&O](UWidget* W, float X, float Y, float Wd, float Ht) { Place(W, FVector2D(X, Y) - O, FVector2D(Wd, Ht)); };
  auto PR = [&P](UWidget* W, const FUmRectSu& R) { P(W, R.X, R.Y, R.W, R.H); };
  PR(Header, L.Header);
  PR(BoardBlock, L.Board);
  PR(DeckRow, L.Deck);
  PR(BottomStrip, L.Bottom);
  const float PxPerSuNow = PxPerSu;
  // ---- header: the title, «Копировать», the mode; «≡» at the right (ВР-VS4-SC14-03)
  const FUmRectSu& Hd = L.Header;
  const float TitleW = MeasureW(TitleText ? TitleText->GetText() : FText(), TEXT("type.title")) + 4.0f;
  P(TitleText, Hd.X + 16.0f, Hd.Y + 14.0f, TitleW, 36.0f);
  const float CopyW = FMath::Max(120.0f, MeasureW(FText::FromString(UmRmUpper(TEXT("screens.room.code.copy"))), TEXT("type.button")) + 32.0f);
  float X = Hd.X + 16.0f + TitleW + 16.0f;
  P(CopyButton, X, Hd.Y + 12.0f, CopyW, 40.0f);
  X += CopyW + 24.0f;
  const float ModeLabelW = MeasureW(ModeLabel ? ModeLabel->GetText() : FText(), TEXT("type.body")) + 4.0f;
  P(ModeLabel, X, Hd.Y + 21.0f, ModeLabelW, 22.0f);
  P(ModeText, X + ModeLabelW + 8.0f, Hd.Y + 21.0f, 200.0f, 22.0f);
  P(MenuButton, Hd.X + Hd.W - 16.0f - 40.0f, Hd.Y + 12.0f, 40.0f, 40.0f);
  // ---- slots
  PR(Slot0, L.Slot0);
  PR(Slot1, L.Slot1);
  if (Slot0) Slot0->Apply(Model.Slots[0], L.Slot0.Size(), bClassS, PxPerSuNow);
  if (Slot1) Slot1->Apply(Model.Slots[1], L.Slot1.Size(), bClassS, PxPerSuNow);
  // ---- the hero grid (as many columns as fit, at most 4; it scrolls)
  // the uniform grid spreads its columns over the box: the box is exactly the used columns wide (cards 16 su apart),
  // plus the slot padding of the last row / column
  const int32 UsedCols = FMath::Clamp(Model.Heroes.Num(), 1, L.Columns);
  P(HeroScroll, L.Grid.X, L.Grid.Y, UsedCols * (L.CardSu.X + 16.0f), L.Grid.H + 16.0f);
  if (HeroScroll) {
    // the bar only when the rows do not fit (the template scrolls for ~84 heroes, ВР-H12; two cards are one row)
    const int32 RowsNeeded = FMath::DivideAndRoundUp(FMath::Max(1, Model.Heroes.Num()), L.Columns);
    const bool bScroll = RowsNeeded * (L.CardSu.Y + 16.0f) > L.Grid.H + 16.0f;
    HeroScroll->SetScrollBarVisibility(bScroll ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
  }
  if (HeroGrid) {
    HeroGrid->SetMinDesiredSlotWidth(L.CardSu.X);
    HeroGrid->SetMinDesiredSlotHeight(L.CardSu.Y);
    for (int32 I = 0; I < CardPool.Num(); ++I) {
      USizeBox* Box = CardBoxes.IsValidIndex(I) ? CardBoxes[I].Get() : nullptr;
      if (!Box) continue;
      Box->SetWidthOverride(L.CardSu.X);
      Box->SetHeightOverride(L.CardSu.Y);
      if (I < Model.Heroes.Num()) {
        if (!Box->GetParent()) HeroGrid->AddChildToUniformGrid(Box, I / L.Columns, I % L.Columns);
        if (UUniformGridSlot* S = Cast<UUniformGridSlot>(Box->Slot)) {
          S->SetRow(I / L.Columns);
          S->SetColumn(I % L.Columns);
        }
        Box->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
        CardPool[I]->Apply(Model.Heroes[I], L.CardSu, bClassS, PxPerSuNow);
      } else {
        Box->SetVisibility(ESlateVisibility::Collapsed);
      }
    }
  }
  // ---- the board block: «Доска», the two cards, the locked reason (ВР-VS4-SC14-10)
  const FUmRectSu& Bd = L.Board;
  const float BoardTitleW = MeasureW(BoardTitle ? BoardTitle->GetText() : FText(), TEXT("type.heading")) + 4.0f;
  float CardsX, CardsY;
  const float CardW = 240.0f;
  float CardH;
  if (!bClassS) {
    CardH = FMath::Min(136.0f, Bd.H - 16.0f);
    P(BoardTitle, Bd.X + 16.0f, Bd.Y + 0.5f * Bd.H - 15.0f, BoardTitleW, 30.0f);
    CardsX = Bd.X + 16.0f + BoardTitleW + 24.0f;
    CardsY = Bd.Y + 0.5f * (Bd.H - CardH);
  } else {
    CardH = FMath::Min(136.0f, Bd.H - 56.0f);
    P(BoardTitle, Bd.X + 16.0f, Bd.Y + 12.0f, BoardTitleW, 30.0f);
    CardsX = Bd.X + 16.0f;
    CardsY = Bd.Y + 44.0f;
  }
  P(BoardCards, CardsX, CardsY, 2.0f * CardW + 16.0f, CardH);
  for (int32 I = 0; I < Boards.Num(); ++I) {
    Place(Boards[I], FVector2D(I * (CardW + 16.0f), 0.0f), FVector2D(CardW, CardH));
    Boards[I]->Apply(FVector2D(CardW, CardH), Boards[I]->GetBoardId() == Model.BoardId);
  }
  const float WhyX = CardsX + 2.0f * CardW + 16.0f + 24.0f;
  const float WhyW = FMath::Max(120.0f, Bd.X + Bd.W - 16.0f - WhyX);
  P(BoardWhy, WhyX, CardsY + 0.5f * CardH - 20.0f, WhyW, 40.0f);
  if (BoardWhy) BoardWhy->SetWrapTextAt(WhyW);
  // ---- the deck row: the count, «Просмотр колоды», its why (ВР-VS4-SC14-04)
  const FUmRectSu& Dk = L.Deck;
  const bool bCount = Model.DeckCount >= 0 && !Model.OwnHeroId.IsEmpty();
  const float CountW = bCount ? MeasureW(DeckCount ? DeckCount->GetText() : FText(), TEXT("type.body")) + 4.0f : 0.0f;
  const float DeckBtnW = FMath::Max(160.0f, MeasureW(FText::FromString(UmRmUpper(TEXT("screens.room.deck.view"))), TEXT("type.button")) + 32.0f);
  if (!bClassS) {
    P(DeckCount, Dk.X + 16.0f, Dk.Y + 0.5f * Dk.H - 11.0f, CountW, 22.0f);
    const float Bx = Dk.X + 16.0f + (bCount ? CountW + 24.0f : 0.0f);
    P(DeckButton, Bx, Dk.Y + 0.5f * Dk.H - 20.0f, DeckBtnW, 40.0f);
    P(DeckWhy, Bx + DeckBtnW + 16.0f, Dk.Y + 0.5f * Dk.H - 9.0f, FMath::Max(80.0f, Dk.X + Dk.W - 16.0f - (Bx + DeckBtnW + 16.0f)), 20.0f);
  } else {
    P(DeckCount, Dk.X + 16.0f, Dk.Y + 12.0f, Dk.W - 32.0f, 22.0f);
    P(DeckButton, Dk.X + 16.0f, Dk.Y + 40.0f, Dk.W - 32.0f, 40.0f);
    P(DeckWhy, Dk.X + 16.0f, Dk.Y + 86.0f, Dk.W - 32.0f, 20.0f);
  }
  // ---- the bottom strip: «Выйти» left, the status centred, «Готов» / «Начать» right, the why under them
  const FUmRectSu& Bt = L.Bottom;
  const float BtnY = Bt.Y + 8.0f;
  const float LeaveW = FMath::Max(160.0f, MeasureW(FText::FromString(UmRmUpper(TEXT("screens.room.leave"))), TEXT("type.button")) + 32.0f);
  P(LeaveButton, Bt.X + 16.0f, BtnY + 4.0f, LeaveW, 40.0f);
  P(StatusText, Bt.X + 16.0f + LeaveW + 16.0f, BtnY + 13.0f, FMath::Max(100.0f, Bt.W - 2.0f * (16.0f + LeaveW + 16.0f)), 22.0f);
  const float StartW = FMath::Max(200.0f, MeasureW(FText::FromString(UmRmUpper(TEXT("screens.room.start"))), TEXT("type.button")) + 48.0f);
  const float ReadyW = FMath::Max(140.0f, MeasureW(FText::FromString(UmRmUpper(TEXT("screens.room.ready"))), TEXT("type.button")) + 64.0f);
  const float StartH = bClassS ? 40.0f : 48.0f;
  const float Right = Bt.X + Bt.W - 16.0f;
  if (Model.bHost) {
    P(StartButton, Right - StartW, BtnY, StartW, StartH);
    P(ReadyButton, Right - StartW - 16.0f - ReadyW, BtnY + (StartH - 40.0f) * 0.5f, ReadyW, 40.0f);
  } else {
    P(ReadyButton, Right - ReadyW, BtnY, ReadyW, StartH);
  }
  P(WhyText, Bt.X + 0.5f * Bt.W, BtnY + StartH + 2.0f, 0.5f * Bt.W - 16.0f, 20.0f);
  // ---- the countdown: the 0.8 veil over the whole canvas, the panel hugging its text
  P(CountVeil, 0.0f, 0.0f, CanvasSu.X, CanvasSu.Y);
  const bool bDigit = Phase == EUmRoomPhase::Countdown;
  const FText CountLabel = CountText ? CountText->GetText() : FText();
  const float Tw = MeasureW(CountLabel, bDigit ? TEXT("type.display") : TEXT("type.title"));
  const float Pw = FMath::Max(bDigit ? 120.0f : 240.0f, Tw + 64.0f);
  const float Ph = bDigit ? 104.0f : 72.0f;
  P(CountPanel, 0.5f * (CanvasSu.X - Pw), 0.5f * (CanvasSu.Y - Ph), Pw, Ph);
  if (CountPanel) {
    // the text line centred in the panel (type.display 48 su / type.title 28 su, Slate line height ~1.3 em)
    const float LineH = bDigit ? 62.0f : 36.0f;
    CountPanel->SetPadding(FMargin(0.0f, FMath::Max(0.0f, 0.5f * (Ph - LineH)), 0.0f, 0.0f));
    CountPanel->SetVerticalAlignment(VAlign_Top);
    CountPanel->SetHorizontalAlignment(HAlign_Fill);
  }
}

// ------------------------------------------------------------------------------------------------ refresh

void UUmScreenRoom::Refresh() {
  auto Btn = [](UUmButton* B, const FText& Label, EUmButtonVariant V, float H, float MinW, bool bEnabled, FName Why,
                bool bSelected = false, FName Icon = NAME_None) {
    if (!B) return;
    FUmButtonModel M;
    M.Variant = V;
    M.Label = Label;
    M.HeightSu = H;
    M.MinWidthSu = MinW;
    M.bEnabled = bEnabled;
    if (!bEnabled && !Why.IsNone()) M.Reason.Key = Why;
    M.bSelected = bSelected;
    M.IconName = Icon;
    B->ApplyModel(M);
  };
  const FName Syncing(TEXT("why.syncing"));
  // header
  if (TitleText) {
    FFormatNamedArguments Args;
    Args.Add(TEXT("code"), FText::FromString(Model.Code));
    TitleText->SetText(FText::Format(S(TEXT("screens.room.title")), Args));
  }
  if (ModeLabel) ModeLabel->SetText(S(TEXT("screens.lobby.create.mode")));
  if (ModeText) ModeText->SetText(S(Model.bVsAi ? TEXT("screens.lobby.create.mode.ai") : TEXT("screens.lobby.create.mode.1v1")));
  Btn(CopyButton, S(TEXT("screens.room.code.copy")), EUmButtonVariant::Normal, 40.0f, 120.0f, !Model.Code.IsEmpty(), Syncing);
  Btn(MenuButton, FText::GetEmpty(), EUmButtonVariant::Normal, 40.0f, 40.0f, true, NAME_None, false, FName(TEXT("ui-menu")));
  // board block
  if (BoardTitle) BoardTitle->SetText(S(TEXT("screens.room.board.title")));
  if (BoardWhy) BoardWhy->SetText(UmText::Get(EUmTable::Why, TEXT("why.room.board.locked")));
  // deck row (ВР-VS4-SC14-13: without a hero no count, only the disabled button with its why)
  const bool bHero = !Model.OwnHeroId.IsEmpty();
  if (DeckCount) {
    FFormatNamedArguments Args;
    Args.Add(TEXT("n"), FText::AsNumber(FMath::Max(0, Model.DeckCount)));
    DeckCount->SetText(FText::Format(S(TEXT("screens.room.deck.count")), Args));
  }
  Vis(DeckCount, bHero && Model.DeckCount >= 0);
  const bool bDeckOn = bHero && Model.DeckCount > 0;
  Btn(DeckButton, S(TEXT("screens.room.deck.view")), EUmButtonVariant::Normal, 40.0f, 160.0f, bDeckOn,
      bHero ? Syncing : FName(TEXT("why.room.no.hero")));
  if (DeckWhy) DeckWhy->SetText(UmText::Get(EUmTable::Why, TEXT("why.room.no.hero")));
  Vis(DeckWhy, !bHero);
  // bottom strip (ВР-VS4-SC14-07: the host's Start is the one primary; the guest's Ready; a toggle that is on - none)
  Btn(LeaveButton, S(TEXT("screens.room.leave")), EUmButtonVariant::Normal, 40.0f, 160.0f, true, NAME_None);
  const bool bAllReady = FCString::Strcmp(UmRoom::StateName(EUmRoomPhase::Room, Model), TEXT("ready")) == 0;
  if (StatusText) StatusText->SetText(S(bAllReady ? TEXT("screens.room.status.all.ready") : TEXT("screens.room.status.waiting")));
  const FName ReadyNo = UmRoom::ReadyWhy(Model);
  const bool bReadyEnabled = ReadyNo.IsNone() && !Model.bBusy;
  const EUmButtonVariant ReadyVariant = (!Model.bHost && !Model.bOwnReady) ? EUmButtonVariant::Primary : EUmButtonVariant::Normal;
  Btn(ReadyButton, S(TEXT("screens.room.ready")), ReadyVariant, (!Model.bHost && !bClassS) ? 48.0f : 40.0f, 140.0f, bReadyEnabled,
      ReadyNo.IsNone() ? Syncing : ReadyNo, Model.bOwnReady, Model.bOwnReady ? FName(TEXT("ui-check")) : NAME_None);
  const FName StartNo = UmRoom::StartWhy(Model);
  Btn(StartButton, S(TEXT("screens.room.start")), EUmButtonVariant::Primary, bClassS ? 40.0f : 48.0f, 200.0f, StartNo.IsNone() && !Model.bBusy,
      StartNo.IsNone() ? Syncing : StartNo);
  Vis(StartButton, Model.bHost, true);
  // the why of the disabled pair, once under the buttons
  FName Why = NAME_None;
  if (Model.bHost) {
    Why = StartNo;
  } else if (!ReadyNo.IsNone()) {
    Why = ReadyNo;
  }
  if (WhyText) WhyText->SetText(Why.IsNone() ? FText::GetEmpty() : UmText::Get(EUmTable::Why, Why.ToString()));
  Vis(WhyText, !Why.IsNone() && Phase == EUmRoomPhase::Room);
  // countdown
  const bool bCount = Phase != EUmRoomPhase::Room;
  if (CountText) {
    if (Phase == EUmRoomPhase::Countdown) {
      CountText->SetText(FText::AsNumber(FMath::Max(1, Digit)));  // the digit is a number, not a string (ВР-VS4-SC18-01)
      Style(CountText, TEXT("type.display"), TEXT("text.primary"));
    } else {
      CountText->SetText(S(TEXT("screens.room.countdown")));
      Style(CountText, TEXT("type.title"), TEXT("text.primary"));
    }
  }
  if (CountVeil) CountVeil->SetVisibility(bCount ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
  Vis(CountPanel, bCount);
  SetScreenState(FName(UmRoom::StateName(Phase, Model)));
}

// ------------------------------------------------------------------------------------------------ what it shows

UUmHeroCard* UUmScreenRoom::GetHeroCard(int32 Index) const {
  return CardPool.IsValidIndex(Index) && Index < Model.Heroes.Num() ? CardPool[Index].Get() : nullptr;
}
UUmRoomSlot* UUmScreenRoom::GetSlot(int32 Index) const { return Index == 0 ? Slot0.Get() : Index == 1 ? Slot1.Get() : nullptr; }
UUmBoardCard* UUmScreenRoom::GetBoardCard(int32 Index) const { return Boards.IsValidIndex(Index) ? Boards[Index].Get() : nullptr; }
bool UUmScreenRoom::IsStartShown() const { return StartButton && StartButton->GetVisibility() != ESlateVisibility::Collapsed; }
bool UUmScreenRoom::IsStartEnabled() const { return IsStartShown() && StartButton->GetModel().bEnabled; }
bool UUmScreenRoom::IsStartPrimary() const { return IsStartShown() && StartButton->GetModel().Variant == EUmButtonVariant::Primary; }
bool UUmScreenRoom::IsReadyEnabled() const { return ReadyButton && ReadyButton->GetModel().bEnabled; }
bool UUmScreenRoom::IsReadyPrimary() const { return ReadyButton && ReadyButton->GetModel().Variant == EUmButtonVariant::Primary; }
bool UUmScreenRoom::IsReadyOn() const { return ReadyButton && ReadyButton->GetModel().bSelected; }
bool UUmScreenRoom::IsDeckEnabled() const { return DeckButton && DeckButton->GetModel().bEnabled; }
int32 UUmScreenRoom::PrimaryCount() const { return (IsStartPrimary() ? 1 : 0) + (IsReadyPrimary() ? 1 : 0); }
FString UUmScreenRoom::GetTitleText() const { return TitleText ? TitleText->GetText().ToString() : FString(); }
FString UUmScreenRoom::GetStatusText() const { return StatusText ? StatusText->GetText().ToString() : FString(); }
FString UUmScreenRoom::GetWhyText() const {
  return WhyText && WhyText->GetVisibility() != ESlateVisibility::Collapsed ? WhyText->GetText().ToString() : FString();
}
FString UUmScreenRoom::GetDeckText() const {
  return DeckCount && DeckCount->GetVisibility() != ESlateVisibility::Collapsed ? DeckCount->GetText().ToString() : FString();
}
FString UUmScreenRoom::GetDeckWhyText() const {
  return DeckWhy && DeckWhy->GetVisibility() != ESlateVisibility::Collapsed ? DeckWhy->GetText().ToString() : FString();
}
FString UUmScreenRoom::GetBoardWhyText() const { return BoardWhy ? BoardWhy->GetText().ToString() : FString(); }
FString UUmScreenRoom::GetCountText() const { return IsCountShown() && CountText ? CountText->GetText().ToString() : FString(); }
bool UUmScreenRoom::IsCountShown() const { return CountPanel && CountPanel->GetVisibility() != ESlateVisibility::Collapsed; }

void UUmScreenRoom::CollectPortraitLines(TArray<FString>& Out) const {
  for (int32 I = 0; I < Model.Heroes.Num() && I < CardPool.Num(); ++I) {
    if (CardPool[I]) Out.Append(CardPool[I]->GetPortraitLines());
  }
  for (const UUmRoomSlot* Seat : {Slot0.Get(), Slot1.Get()}) {
    if (Seat && !Seat->GetPortraitLine().IsEmpty()) Out.Add(Seat->GetPortraitLine());
  }
}

FBox2D UUmScreenRoom::BlockRectPx(const FUmRectSu& R) const {
  return FBox2D(FVector2D(R.X, R.Y) * PxPerSu, FVector2D(R.X + R.W, R.Y + R.H) * PxPerSu);
}

FString UUmScreenRoom::ShotExtra() const {
  const TCHAR* Opp = !Model.bOppPresent ? TEXT("none") : Model.bOppReady ? TEXT("ready") : Model.bOppHero ? TEXT("hero") : TEXT("joined");
  return FString::Printf(TEXT(" host=%d mode=%s hero=%d ready=%d opp=%s primary=%s busy=%d heroes=%d phase=%s digit=%d"), Model.bHost ? 1 : 0,
                         Model.bVsAi ? TEXT("ai") : TEXT("1v1"), Model.OwnHeroId.IsEmpty() ? 0 : 1, Model.bOwnReady ? 1 : 0, Opp,
                         IsStartPrimary() ? TEXT("start") : IsReadyPrimary() ? TEXT("ready") : TEXT("none"), Model.bBusy ? 1 : 0,
                         Model.Heroes.Num(), Phase == EUmRoomPhase::Countdown ? TEXT("countdown") : Phase == EUmRoomPhase::Starting ? TEXT("starting") : TEXT("room"),
                         Digit);
}

void UUmScreenRoom::CollectShotLines(TArray<FString>& Out) const {
  Super::CollectShotLines(Out);
  if (!IsShown()) return;
  // the two blocks of SC-15 / SC-16 as their own lines (ВР-SC11): state=board, state=deck
  const FUmRoomLayout L = UmRoom::Layout(CanvasSu, bClassS);
  auto Line = [this, &Out](const FUmRectSu& R, const TCHAR* State, const FString& Extra) {
    const FBox2D B = BlockRectPx(R);
    Out.Add(S08ArtHud::FormatWidgetLineEx(GetUiId(), TEXT("umg"), State, FString(), FS08ScreenRect(B.Min.X, B.Min.Y, B.Max.X, B.Max.Y),
                                          true, true, SourceName(),
                                          FString::Printf(TEXT("modal=0 class=%s alpha=%.2f block=1%s"), bClassS ? TEXT("S") : TEXT("L"), GetAlpha(), *Extra)));
  };
  const FString BoardKey = Model.BoardId == UmLobby::SarpedonId ? TEXT("sarpedon") : Model.BoardId == UmLobby::MarmorealId ? TEXT("marmoreal") : TEXT("other");
  int32 Locked = 0;
  for (const UUmBoardCard* B : Boards) Locked += B && !B->IsRoomBoard() ? 1 : 0;
  Line(L.Board, TEXT("board"), FString::Printf(TEXT(" board=%s locked=%d thumbs=%d"), *BoardKey, Locked,
                                               (Boards.Num() == 2 && Boards[0]->HasThumb() ? 1 : 0) + (Boards.Num() == 2 && Boards[1]->HasThumb() ? 1 : 0)));
  Line(L.Deck, TEXT("deck"), FString::Printf(TEXT(" deck=%d deckButton=%d"), Model.OwnHeroId.IsEmpty() ? -1 : Model.DeckCount, IsDeckEnabled() ? 1 : 0));
}

// ------------------------------------------------------------------------------------------------ input

void UUmScreenRoom::Sound(const TCHAR* Bank) const {
  if (Input.OnSound) Input.OnSound(FName(Bank));
}

void UUmScreenRoom::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput) {
  Arbiter = InArbiter;
  Input = MoveTemp(InInput);
  TWeakObjectPtr<UUmScreenRoom> WeakThis(this);
  auto Bind = [&WeakThis, this](UUmButton* B, const TCHAR* Id) {
    if (!B) return;
    const FName Name(Id);
    B->SetPress(Name, Arbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, Name](const FS09HudPressOutcome& O) {
      if (UUmScreenRoom* Self = WeakThis.Get()) Self->OnPressOutcome(Name, O);
    }));
  };
  Bind(CopyButton, TEXT("screens.room.code.copy"));
  Bind(MenuButton, TEXT("screens.room.menu"));
  Bind(DeckButton, TEXT("screens.room.deck.view"));
  Bind(LeaveButton, TEXT("screens.room.leave"));
  Bind(ReadyButton, TEXT("screens.room.ready"));
  Bind(StartButton, TEXT("screens.room.start"));
  for (int32 I = 0; I < CardPool.Num(); ++I) BindCardPress(CardPool[I], I);
}

void UUmScreenRoom::BindCardPress(UUmHeroCard* Card, int32 Index) {
  if (!Card) return;
  TWeakObjectPtr<UUmScreenRoom> WeakThis(this);
  const FName Name(*FString::Printf(TEXT("screens.room.hero.pick.%d"), Index));
  Card->SetPress(Name, Arbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, Name](const FS09HudPressOutcome& O) {
    if (UUmScreenRoom* Self = WeakThis.Get()) Self->OnPressOutcome(Name, O);
  }));
}

void UUmScreenRoom::OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome) {
  if (Outcome.Result != ES09HudPressResult::Act || Phase != EUmRoomPhase::Room) return;
  const FString S = Id.ToString();
  if (S == TEXT("screens.room.code.copy")) {
    Sound(TEXT("UI-BTN-CLICK"));
    if (Input.OnCopy) Input.OnCopy();
  } else if (S == TEXT("screens.room.menu")) {
    Sound(TEXT("UI-BTN-CLICK"));
    if (Input.OnMenu) Input.OnMenu();
  } else if (S == TEXT("screens.room.deck.view")) {
    if (IsDeckEnabled() && Input.OnDeck) Input.OnDeck();  // UI-PANEL-OPEN with the modal (08-screen-audio-hooks)
  } else if (S == TEXT("screens.room.leave")) {
    if (Input.OnLeave) Input.OnLeave();
  } else if (S == TEXT("screens.room.ready")) {
    // the ready / start / leave sounds play by themselves on the room answers (08: SC-17 «—»)
    if (IsReadyEnabled() && Input.OnReady) Input.OnReady();
  } else if (S == TEXT("screens.room.start")) {
    if (IsStartEnabled() && Input.OnStart) Input.OnStart();
  } else if (S.StartsWith(TEXT("screens.room.hero.pick."))) {
    const int32 I = FCString::Atoi(*S.RightChop(23));
    if (Model.Heroes.IsValidIndex(I)) {
      const FUmHeroCardModel& H = Model.Heroes[I];
      if (H.State == EUmHeroCardState::Normal && H.bEnabled && H.bDetails) {
        Sound(TEXT("UI-SELECT"));  // the pick; the hero sting plays on the server's confirmation (PlayHeroSelectSting)
        if (Input.OnPick) Input.OnPick(H.HeroId);
      }
    }
  }
  Refresh();
}

void UUmScreenRoom::SimulatePress(FName Id) {
  if (!Arbiter.IsValid()) Arbiter = MakeShared<FS09HudPressArbiter>();
  Arbiter->Press(Id, Arbiter->Now());
  OnPressOutcome(Id, FS09HudPressArbiter::Decide(Arbiter->Release(Id, Arbiter->Now()), FS09Reason()));
}

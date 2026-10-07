// VS-3 HB-28: the deck panel - see UmHudDeckPanel.h.
#include "UmHudDeckPanel.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08ArtHud.h"
#include "../S08ArtLook.h"
#include "UmButton.h"
#include "UmCardMedia.h"
#include "UmGameHud.h"
#include "UmHudScale.h"
#include "UmHudTheme.h"
#include "UmSkeletonRows.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Image.h"
#include "Components/ScrollBox.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Engine/Texture2D.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "InputCoreTypes.h"
#include "Rendering/SlateRenderer.h"

const TCHAR* const UUmHudDeckPanel::WidgetBlueprintPath = TEXT("/Game/S08/UI/Hud/WBP_UI_HUD_DECKPANEL");

TArray<int32> FUmDeckPanelModel::ShownRows() const {
  TArray<int32> Out;
  for (int32 I = 0; I < Rows.Num(); ++I) {
    if (!bFilterDiscard || Rows[I].InDiscard > 0) Out.Add(I);
  }
  return Out;
}

namespace UmHudDeckPanel {
FUmDeckPanelModel Gather(const FS09DeckPanelModel& M, const FString& HeroName, const FString& HeroSlug,
                         EUmDeckListState List, bool bFilterDiscard, bool bRu) {
  FUmDeckPanelModel Out;
  Out.bShow = true;
  Out.Side = M.Side;
  Out.HeroName = HeroName;
  Out.HeroSlug = HeroSlug;
  Out.DeckCount = M.DeckCount;
  Out.bDeckStale = M.bDeckStale;
  Out.DiscardCount = M.DiscardCount;
  Out.bDiscardStale = M.bDiscardStale;
  Out.HandCount = M.HandCount;
  Out.Copies = M.Copies;
  Out.List = M.bListKnown ? EUmDeckListState::Loaded : (List == EUmDeckListState::Loaded ? EUmDeckListState::Loading : List);
  Out.bFilterDiscard = bFilterDiscard;
  const bool bOwn = M.Side == ES09DeckSide::Own;
  for (const FS09DeckRow& Row : M.Rows) {
    FUmDeckRowModel R;
    R.CardId = Row.Card.CardId;
    R.Name = UmDeckRow::ShownName(Row.Card, bRu);
    R.CardType = Row.Card.CardType;
    R.Copies = Row.Card.Count;
    R.Values = UmDeckRow::Values(Row.Card);
    R.bOwn = bOwn;
    // the opponent's rows never carry the hand or what is left (F-05): the model has them 0 / -1 anyway
    R.InHand = bOwn ? Row.InHand : 0;
    R.InDiscard = Row.InDiscard;
    R.Left = bOwn ? FMath::Max(0, Row.Left) : 0;
    Out.Rows.Add(MoveTemp(R));
  }
  // ВР-VS2-HB26-04: the type (attack, defense, versatile, scheme), then the shown name in code-point order of its lower
  // case - never the deck or draw order
  Out.Rows.StableSort([](const FUmDeckRowModel& A, const FUmDeckRowModel& B) {
    const int32 TA = UmDeckRow::TypeOrder(A.CardType);
    const int32 TB = UmDeckRow::TypeOrder(B.CardType);
    if (TA != TB) return TA < TB;
    return A.Name.ToLower().Compare(B.Name.ToLower(), ESearchCase::CaseSensitive) < 0;
  });
  return Out;
}

FString TitleText(const FUmDeckPanelModel& M) {
  FFormatNamedArguments A;
  A.Add(TEXT("hero"), FText::FromString(M.HeroName));
  return UmText::Format(EUmTable::Hud,
                        M.Side == ES09DeckSide::Own ? TEXT("hud.deckpanel.title.own") : TEXT("hud.deckpanel.title.opp"), A)
      .ToString();
}

void FitTitle(const FString& Title, float WidthSu, TFunctionRef<float(const FString&, float)> Measure, float& OutSizeSu,
              TArray<FString>& OutLines) {
  OutLines.Reset();
  if (Measure(Title, TitleSu) <= WidthSu) {
    OutSizeSu = TitleSu;
    OutLines.Add(Title);
    return;
  }
  // the only legal break: after « · » (the hero's name stays whole, ВР-VS2-HB26-10)
  const FString Sep(TEXT(" · "));
  const int32 At = Title.Find(Sep, ESearchCase::CaseSensitive, ESearchDir::FromEnd);
  if (At == INDEX_NONE) {
    OutSizeSu = TitleSmallSu;
    OutLines.Add(Title);
    return;
  }
  OutLines.Add(Title.Left(At) + TEXT(" ·"));
  OutLines.Add(Title.Mid(At + Sep.Len()));
  bool bFit = true;
  for (const FString& L : OutLines) bFit &= Measure(L, TitleSu) <= WidthSu;
  OutSizeSu = bFit ? TitleSu : TitleSmallSu;
}

namespace {
FText Count(int32 N, bool bStale) {
  const FText Num = FText::FromString(FString::FromInt(N));
  if (!bStale) return Num;
  FFormatNamedArguments A;
  A.Add(TEXT("n"), Num);
  return UmText::Format(EUmTable::Hud, TEXT("hud.decks.stale"), A);
}
}  // namespace

FText SummaryText(const FUmDeckPanelModel& M) {
  FFormatNamedArguments A;
  A.Add(TEXT("deck"), Count(M.DeckCount, M.bDeckStale));
  A.Add(TEXT("discard"), Count(M.DiscardCount, M.bDiscardStale));
  A.Add(TEXT("hand"), FText::FromString(FString::FromInt(M.HandCount)));
  return UmText::Format(EUmTable::Hud, TEXT("hud.deckpanel.summary"), A);
}

float HeaderSu(float TitleSizeSu, int32 TitleLines, int32 SummaryLines, bool bBacks) {
  return PadSu + TitleLines * TitleSizeSu * LineK + GapSu + TabHSu + GapSu + SummaryLines * SummaryLineSu +
         (bBacks ? BacksPadSu + BackHSu + BacksPadSu : 0.0f) + FilterGapSu + FilterHSu + GapSu;
}

int32 Capacity(float PanelHeightSu, float HeaderHeightSu) {
  return FMath::Max(0, FMath::FloorToInt((PanelHeightSu - PadSu - HeaderHeightSu + 1.0e-3f) / RowSu));
}

float ReducedAlpha(float ViewAlpha, bool bOpen) {
  if (bOpen) return ViewAlpha;
  // the view closes 1 -> 0 linearly in 150 ms: after t ms it reads 1 - t / 150; reduced reaches 0 at t = 100
  return FMath::Clamp(1.0f - (1.0f - ViewAlpha) * 150.0f / CloseReducedMs, 0.0f, 1.0f);
}

const TCHAR* StateName(const FUmDeckPanelModel& M) { return M.Side == ES09DeckSide::Own ? TEXT("own") : TEXT("opp"); }

float BottomOver(const FBox2D& SlotSu, const FBox2D& HandSu) {
  const float Bottom = static_cast<float>(SlotSu.Max.Y);
  if (!SlotSu.bIsValid || !HandSu.bIsValid) return Bottom;
  const bool bUnder = HandSu.Max.X > SlotSu.Min.X && HandSu.Min.X < SlotSu.Max.X && HandSu.Min.Y < Bottom;
  return bUnder ? FMath::Max(static_cast<float>(SlotSu.Min.Y), static_cast<float>(HandSu.Min.Y) - GapSu) : Bottom;
}
}  // namespace UmHudDeckPanel

namespace {
template <typename T>
T* UmDpFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

void UmDpPlace(UWidget* W, const FVector2D& Pos, const FVector2D& Size, bool bAuto = false) {
  if (UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr) {
    S->SetAnchors(FAnchors(0.0f, 0.0f));
    S->SetAlignment(FVector2D::ZeroVector);
    S->SetAutoSize(bAuto);
    S->SetPosition(Pos);
    if (!bAuto) S->SetSize(Size);
  }
}

float UmDpMeasure(const FString& Text, float SizeSu, const TCHAR* Token) {
  return UmDeckRow::MeasureSu(Text, SizeSu, FName(Token));
}

/** The line pitch K x size for a text block of SizeSu of Token (Slate's natural pitch is ascender - descender). */
float UmDpLinePercent(float SizeSu, const TCHAR* Token, float PitchSu) {
  if (FSlateApplication::IsInitialized() && FSlateApplication::Get().GetRenderer()) {
    constexpr float K = 8.0f;
    FSlateFontInfo Font = UUmHudTheme::Get().Font(FName(Token));
    Font.Size = UmHudTheme::PointsFromSu(SizeSu);
    const float Natural = FSlateApplication::Get().GetRenderer()->GetFontMeasureService()->GetMaxCharacterHeight(Font, K) / K;
    if (Natural > 0.0f) return PitchSu / Natural;
  }
  return 1.0f;
}
}  // namespace

UClass* UUmHudDeckPanel::WidgetClass() {
  return UmGameHudSlots::WbpOrNative(UUmHudDeckPanel::StaticClass(), WidgetBlueprintPath);
}

bool UUmHudDeckPanel::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UCanvasPanel* RootW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Root")));
  RootW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(RootW, nullptr)) return Fail(TEXT("Root"));
  UBorder* PanelW = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(TEXT("Panel")));
  if (const FSlateBrush* Skin = Theme.Skin(TEXT("panel"))) PanelW->SetBrush(*Skin);
  PanelW->SetPadding(FMargin(UmHudDeckPanel::PadSu));
  PanelW->SetHorizontalAlignment(HAlign_Fill);
  PanelW->SetVerticalAlignment(VAlign_Fill);
  if (!Attach(PanelW, RootW)) return Fail(TEXT("Panel"));
  UCanvasPanel* BodyW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Body")));
  BodyW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(BodyW, PanelW)) return Fail(TEXT("Body"));
  auto Text = [&Tree, &Theme](const TCHAR* Name, const TCHAR* Token, const TCHAR* Color) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetFont(Theme.Font(FName(Token)));
    T->SetColorAndOpacity(FSlateColor(Theme.Color(FName(Color))));
    T->SetShadowOffset(FVector2D::ZeroVector);
    T->SetVisibility(ESlateVisibility::HitTestInvisible);
    return T;
  };
  if (!Attach(Text(TEXT("Title"), TEXT("type.title"), TEXT("text.primary")), BodyW)) return Fail(TEXT("Title"));
  UHorizontalBox* TabsW = Tree.ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), FName(TEXT("Tabs")));
  TabsW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(TabsW, BodyW)) return Fail(TEXT("Tabs"));
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  for (const TCHAR* Name : {TEXT("TabOwn"), TEXT("TabOpp")}) {
    UUmButton* Tab = Tree.ConstructWidget<UUmButton>(ButtonClass, FName(Name));
    if (!Attach(Tab, TabsW)) return Fail(Name);
  }
  if (!Attach(Tree.ConstructWidget<UUmButton>(ButtonClass, FName(TEXT("CloseButton"))), BodyW)) return Fail(TEXT("CloseButton"));
  UTextBlock* SummaryW = Text(TEXT("Summary"), TEXT("type.caption"), TEXT("text.secondary"));
  if (!Attach(SummaryW, BodyW)) return Fail(TEXT("Summary"));
  UHorizontalBox* BacksW = Tree.ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), FName(TEXT("Backs")));
  BacksW->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(BacksW, BodyW)) return Fail(TEXT("Backs"));
  if (!Attach(Tree.ConstructWidget<UUmButton>(ButtonClass, FName(TEXT("FilterButton"))), BodyW)) return Fail(TEXT("FilterButton"));
  // VS-4 SC-23: «Весь состав» on the filter row
  if (!Attach(Tree.ConstructWidget<UUmButton>(ButtonClass, FName(TEXT("AllButton"))), BodyW)) return Fail(TEXT("AllButton"));
  UScrollBox* RowsW = Tree.ConstructWidget<UScrollBox>(UScrollBox::StaticClass(), FName(TEXT("Rows")));
  if (!Attach(RowsW, BodyW)) return Fail(TEXT("Rows"));
  UImage* TrackW = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("Track")));
  TrackW->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(TrackW, BodyW)) return Fail(TEXT("Track"));
  UImage* ThumbW = Tree.ConstructWidget<UImage>(UImage::StaticClass(), FName(TEXT("Thumb")));
  ThumbW->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(ThumbW, BodyW)) return Fail(TEXT("Thumb"));
  if (!Attach(Tree.ConstructWidget<UUmSkeletonRows>(UUmSkeletonRows::StaticClass(), FName(TEXT("Skeleton"))), BodyW)) {
    return Fail(TEXT("Skeleton"));
  }
  UTextBlock* ErrorW = Text(TEXT("ErrorText"), TEXT("type.caption"), TEXT("text.secondary"));
  ErrorW->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(ErrorW, BodyW)) return Fail(TEXT("ErrorText"));
  UUmButton* Retry = Tree.ConstructWidget<UUmButton>(ButtonClass, FName(TEXT("RetryButton")));
  Retry->SetVisibility(ESlateVisibility::Collapsed);
  if (!Attach(Retry, BodyW)) return Fail(TEXT("RetryButton"));
  return true;
}

bool UUmHudDeckPanel::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD deck panel default tree: %s"), *Error);
  }
  Root = UmDpFind<UCanvasPanel>(WidgetTree, TEXT("Root"));
  Panel = UmDpFind<UBorder>(WidgetTree, TEXT("Panel"));
  Body = UmDpFind<UCanvasPanel>(WidgetTree, TEXT("Body"));
  Title = UmDpFind<UTextBlock>(WidgetTree, TEXT("Title"));
  Tabs = UmDpFind<UHorizontalBox>(WidgetTree, TEXT("Tabs"));
  TabOwn = UmDpFind<UUmButton>(WidgetTree, TEXT("TabOwn"));
  TabOpp = UmDpFind<UUmButton>(WidgetTree, TEXT("TabOpp"));
  CloseButton = UmDpFind<UUmButton>(WidgetTree, TEXT("CloseButton"));
  Summary = UmDpFind<UTextBlock>(WidgetTree, TEXT("Summary"));
  Backs = UmDpFind<UHorizontalBox>(WidgetTree, TEXT("Backs"));
  FilterButton = UmDpFind<UUmButton>(WidgetTree, TEXT("FilterButton"));
  Rows = UmDpFind<UScrollBox>(WidgetTree, TEXT("Rows"));
  Track = UmDpFind<UImage>(WidgetTree, TEXT("Track"));
  Thumb = UmDpFind<UImage>(WidgetTree, TEXT("Thumb"));
  Skeleton = UmDpFind<UUmSkeletonRows>(WidgetTree, TEXT("Skeleton"));
  ErrorText = UmDpFind<UTextBlock>(WidgetTree, TEXT("ErrorText"));
  RetryButton = UmDpFind<UUmButton>(WidgetTree, TEXT("RetryButton"));
  AllButton = UmDpFind<UUmButton>(WidgetTree, TEXT("AllButton"));
  if (!AllButton && Body) {
    // VS-4 SC-23: a WBP authored before the step has no «Весь состав» - it is made here, like the pooled rows
    AllButton = WidgetTree->ConstructWidget<UUmButton>(UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath),
                                                       FName(TEXT("AllButton")));
    if (AllButton) Body->AddChild(AllButton);
  }
  // a WBP keeps neither the theme fonts nor the code brushes: set at run time
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (Panel) {
    if (const FSlateBrush* Skin = Theme.SkinFor(TEXT("panel"), UmHudScale::Current().PxPerSu())) Panel->SetBrush(*Skin);
    Panel->SetPadding(FMargin(UmHudDeckPanel::PadSu));
    Panel->SetVisibility(ESlateVisibility::Visible);  // the body takes a click (it never reaches the board)
  }
  if (Title) {
    Title->SetFont(Theme.Font(TEXT("type.title")));
    Title->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.primary"))));
  }
  for (UTextBlock* T : {Summary.Get(), ErrorText.Get()}) {
    if (!T) continue;
    T->SetFont(Theme.Font(TEXT("type.caption")));
    T->SetColorAndOpacity(FSlateColor(Theme.Color(TEXT("text.secondary"))));
  }
  if (Track) Track->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("panel.divider")), 0.5f * UmHudDeckPanel::ScrollWSu));
  if (Thumb) Thumb->SetBrush(FSlateRoundedBoxBrush(Theme.Color(TEXT("panel.edge")), 0.5f * UmHudDeckPanel::ScrollWSu));
  if (Rows) {
    // the list scrolls by whole rows (the panel's wheel, ScrollToRow); the box draws no bar of its own
    Rows->SetScrollBarVisibility(ESlateVisibility::Collapsed);
    Rows->SetConsumeMouseWheel(EConsumeMouseWheel::Never);
    Rows->SetAllowOverscroll(false);
    Rows->SetAnimateWheelScrolling(false);
    Rows->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  }
  if (CloseButton) {
    FUmButtonModel C;
    C.IconName = TEXT("ui-close");
    C.HeightSu = UmHudDeckPanel::CloseSu;
    C.MinWidthSu = UmHudDeckPanel::CloseSu;
    CloseButton->ApplyModel(C);
    CloseButton->SetToolTipText(UmText::Get(EUmTable::Hud, TEXT("hud.deckpanel.close")));
  }
  if (RetryButton) {
    FUmButtonModel R;
    R.Label = UmText::Get(EUmTable::Screens, TEXT("common.btn.retry"));
    R.HeightSu = UmHudDeckPanel::TabHSu;
    RetryButton->ApplyModel(R);
  }
  if (ErrorText) ErrorText->SetText(UmText::Get(EUmTable::Screens, TEXT("screens.boot.error.server")));
  if (Skeleton) Skeleton->SetRows(UmHudDeckPanel::SkeletonRows, UmHudDeckPanel::RowSu);
  if (Root) Root->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  SetVisibility(ESlateVisibility::Collapsed);  // the owner's view opens it
  return bFirst;
}

bool UUmHudDeckPanel::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Root) Missing.Add(TEXT("Root"));
  if (!Panel) Missing.Add(TEXT("Panel"));
  if (!Body) Missing.Add(TEXT("Body"));
  if (!Title) Missing.Add(TEXT("Title"));
  if (!Tabs) Missing.Add(TEXT("Tabs"));
  if (!TabOwn) Missing.Add(TEXT("TabOwn"));
  if (!TabOpp) Missing.Add(TEXT("TabOpp"));
  if (!CloseButton) Missing.Add(TEXT("CloseButton"));
  if (!Summary) Missing.Add(TEXT("Summary"));
  if (!Backs) Missing.Add(TEXT("Backs"));
  if (!FilterButton) Missing.Add(TEXT("FilterButton"));
  if (!Rows) Missing.Add(TEXT("Rows"));
  if (!Skeleton) Missing.Add(TEXT("Skeleton"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

FString UUmHudDeckPanel::SourceName() const {
  return bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName();
}

void UUmHudDeckPanel::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput) {
  Arbiter = InArbiter;
  Input = MoveTemp(InInput);
  TWeakObjectPtr<UUmHudDeckPanel> WeakThis(this);
  auto Wire = [WeakThis](TFunction<void(UUmHudDeckPanel&, const FS09HudPressOutcome&)> Fn) {
    return FS09OnHudPressOutcome::CreateLambda([WeakThis, Fn](const FS09HudPressOutcome& O) {
      if (UUmHudDeckPanel* Self = WeakThis.Get()) Fn(*Self, O);
    });
  };
  if (TabOwn) TabOwn->SetPress(FName(TEXT("hud.deck.tab.own")), Arbiter, Wire([](UUmHudDeckPanel& S, const FS09HudPressOutcome& O) {
    if (S.Input.OnTab) S.Input.OnTab(O, ES09DeckSide::Own);
  }));
  if (TabOpp) TabOpp->SetPress(FName(TEXT("hud.deck.tab.opp")), Arbiter, Wire([](UUmHudDeckPanel& S, const FS09HudPressOutcome& O) {
    if (S.Input.OnTab) S.Input.OnTab(O, ES09DeckSide::Opponent);
  }));
  if (CloseButton) CloseButton->SetPress(FName(TEXT("hud.deck.close")), Arbiter, Wire([](UUmHudDeckPanel& S, const FS09HudPressOutcome& O) {
    if (S.Input.OnClose) S.Input.OnClose(O);
  }));
  if (FilterButton) FilterButton->SetPress(FName(TEXT("hud.deck.filter.discard")), Arbiter, Wire([](UUmHudDeckPanel& S, const FS09HudPressOutcome& O) {
    if (S.Input.OnFilter) S.Input.OnFilter(O);
  }));
  if (RetryButton) RetryButton->SetPress(FName(TEXT("hud.deck.retry")), Arbiter, Wire([](UUmHudDeckPanel& S, const FS09HudPressOutcome& O) {
    if (S.Input.OnRetry) S.Input.OnRetry(O);
  }));
  if (AllButton) AllButton->SetPress(FName(TEXT("hud.deck.all")), Arbiter, Wire([](UUmHudDeckPanel& S, const FS09HudPressOutcome& O) {
    if (S.Input.OnAll) S.Input.OnAll(O, S.Model.Side);
  }));
}

void UUmHudDeckPanel::SetFrame(const FUmDeckPanelFrame& InFrame) {
  if (bHasFrame && Frame == InFrame) return;
  Frame = InFrame;
  bHasFrame = true;
  if (bHasModel) Relayout();
}

void UUmHudDeckPanel::ApplyModel(const FUmDeckPanelModel& InModel) {
  if (bHasModel && Model == InModel) return;
  const bool bNewList = !bHasModel || Model.Side != InModel.Side || Model.bFilterDiscard != InModel.bFilterDiscard;
  Model = InModel;
  bHasModel = true;
  if (bNewList) FirstRow = 0;  // a new side or filter shows its list from the top
  Relayout();
}

FBox2D UUmHudDeckPanel::PanelRectSu() const {
  if (!Frame.SlotSu.bIsValid) return FBox2D(ForceInit);
  const float Bottom = Frame.BottomSu > Frame.SlotSu.Min.Y ? FMath::Min(Frame.BottomSu, static_cast<float>(Frame.SlotSu.Max.Y))
                                                           : static_cast<float>(Frame.SlotSu.Max.Y);
  return FBox2D(Frame.SlotSu.Min, FVector2D(Frame.SlotSu.Max.X, Bottom));
}

void UUmHudDeckPanel::Relayout() {
  using namespace UmHudDeckPanel;
  const FBox2D Rect = PanelRectSu();
  if (!Rect.bIsValid || !Model.bShow) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const float W = static_cast<float>(Rect.Max.X - Rect.Min.X);
  const float H = static_cast<float>(Rect.Max.Y - Rect.Min.Y);
  const float Iw = FMath::Max(0.0f, W - 2.0f * PadSu);
  UmDpPlace(Panel, FVector2D::ZeroVector, FVector2D(W, H));
  // ---- the title: one line at 28 su, else broken after « · », then 24 su ----
  FitTitle(TitleText(Model), Iw, [](const FString& T, float Su) { return UmDpMeasure(T, Su, TEXT("type.title")); },
           TitleSizeNow, TitleLinesNow);
  const float TitleH = TitleLinesNow.Num() * TitleSizeNow * LineK;
  if (Title) {
    FSlateFontInfo Font = Theme.Font(TEXT("type.title"));
    Font.Size = UmHudTheme::PointsFromSu(TitleSizeNow);
    Title->SetFont(Font);
    Title->SetText(FText::FromString(FString::Join(TitleLinesNow, TEXT("\n"))));
    Title->SetLineHeightPercentage(UmDpLinePercent(TitleSizeNow, TEXT("type.title"), TitleSizeNow * LineK));
    UmDpPlace(Title, FVector2D::ZeroVector, FVector2D(Iw, TitleH));
  }
  // ---- the tabs and the close glyph ----
  const float TabsY = TitleH + GapSu;
  const float TabGap = Frame.bClassS ? TabGapSSu : TabGapLSu;
  auto TabModel = [](const TCHAR* Key, bool bSelected) {
    FUmButtonModel B;
    B.Label = UmText::Get(EUmTable::Hud, Key);
    B.HeightSu = TabHSu;
    B.MinWidthSu = 1.0f;
    B.PadXSu = TabPadXSu;
    B.bSelected = bSelected;
    return B;
  };
  if (TabOwn) TabOwn->ApplyModel(TabModel(TEXT("hud.deckpanel.tab.own"), Model.Side == ES09DeckSide::Own));
  if (TabOpp) {
    TabOpp->ApplyModel(TabModel(TEXT("hud.deckpanel.tab.opp"), Model.Side == ES09DeckSide::Opponent));
    if (UHorizontalBoxSlot* S = Cast<UHorizontalBoxSlot>(TabOpp->Slot)) S->SetPadding(FMargin(TabGap, 0.0f, 0.0f, 0.0f));
  }
  UmDpPlace(Tabs, FVector2D(0.0f, TabsY), FVector2D::ZeroVector, true);
  UmDpPlace(CloseButton, FVector2D(Iw - CloseSu, TabsY), FVector2D(CloseSu, CloseSu));
  // ---- the summary (and the opponent's hand as backs) ----
  const FText SummaryValue = SummaryText(Model);
  const float SummaryY = TabsY + TabHSu + GapSu;
  SummaryLinesNow = UmDpMeasure(SummaryValue.ToString(), 14.0f, TEXT("type.caption")) <= Iw ? 1 : 2;
  if (Summary) {
    Summary->SetText(SummaryValue);
    Summary->SetAutoWrapText(true);
    Summary->SetWrapTextAt(Iw);
    Summary->SetLineHeightPercentage(UmDpLinePercent(14.0f, TEXT("type.caption"), SummaryLineSu));
    UmDpPlace(Summary, FVector2D(0.0f, SummaryY), FVector2D(Iw, SummaryLinesNow * SummaryLineSu));
  }
  const bool bBacks = Model.Side == ES09DeckSide::Opponent;
  float Y = SummaryY + SummaryLinesNow * SummaryLineSu;
  if (bBacks) {
    UmDpPlace(Backs, FVector2D(0.0f, Y + BacksPadSu), FVector2D::ZeroVector, true);
    Y += BacksPadSu + BackHSu + BacksPadSu;
  }
  ApplyBacks();
  // ---- the filter «Только сброс» ----
  const float FilterY = Y + FilterGapSu;
  if (FilterButton) {
    FUmButtonModel F;
    F.Label = UmText::Get(EUmTable::Hud, TEXT("hud.deckpanel.filter.discard"));
    F.HeightSu = FilterHSu;
    F.MinWidthSu = 1.0f;
    F.PadXSu = FilterPadXSu;
    F.bSelected = Model.bFilterDiscard;
    FilterButton->ApplyModel(F);
    UmDpPlace(FilterButton, FVector2D(0.0f, FilterY), FVector2D::ZeroVector, true);
  }
  // ---- VS-4 SC-23: «Весь состав» at the right of the filter row (the grid of the side; a loaded list only) ----
  if (AllButton) {
    FUmButtonModel A;
    A.Label = UmText::Get(EUmTable::Hud, TEXT("hud.deckpanel.all"));
    A.HeightSu = FilterHSu;
    A.MinWidthSu = 1.0f;
    A.PadXSu = FilterPadXSu;
    AllButton->ApplyModel(A);
    // right-aligned by its own desired size (the button sizes itself to its label, like the filter)
    if (UCanvasPanelSlot* S = Cast<UCanvasPanelSlot>(AllButton->Slot)) {
      S->SetAnchors(FAnchors(0.0f, 0.0f));
      S->SetAlignment(FVector2D(1.0f, 0.0f));
      S->SetAutoSize(true);
      S->SetPosition(FVector2D(Iw, FilterY));
    }
    AllButton->SetVisibility(Model.List == EUmDeckListState::Loaded ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
  }
  // ---- the list viewport: whole rows only ----
  ViewportTopSu = FilterY + FilterHSu + GapSu;
  HeaderNow = PadSu + ViewportTopSu;
  CapacityNow = Capacity(H, HeaderNow);
  const float ListW = FMath::Max(0.0f, Iw - ScrollGapSu);
  const float ViewH = CapacityNow * RowSu;
  UmDpPlace(Rows, FVector2D(0.0f, ViewportTopSu), FVector2D(ListW, ViewH));
  UmDpPlace(Track, FVector2D(Iw - ScrollWSu, ViewportTopSu), FVector2D(ScrollWSu, ViewH));
  if (Skeleton) {
    UmDpPlace(Skeleton, FVector2D(0.0f, ViewportTopSu), FVector2D(ListW, FMath::Min(SkeletonRows, CapacityNow) * RowSu));
    Skeleton->SetRows(FMath::Min(SkeletonRows, CapacityNow), RowSu);
  }
  const bool bFailed = Model.List == EUmDeckListState::Failed;
  if (ErrorText) {
    ErrorText->SetVisibility(bFailed ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    UmDpPlace(ErrorText, FVector2D(0.0f, ViewportTopSu + FilterGapSu), FVector2D::ZeroVector, true);
  }
  if (RetryButton) {
    RetryButton->SetVisibility(bFailed ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
    UmDpPlace(RetryButton, FVector2D(0.0f, ViewportTopSu + FilterGapSu + SummaryLineSu + GapSu), FVector2D::ZeroVector, true);
  }
  ApplyRows();
}

void UUmHudDeckPanel::ApplyBacks() {
  if (!Backs || !WidgetTree) return;
  const bool bShowBacks = Model.Side == ES09DeckSide::Opponent;
  Backs->SetVisibility(bShowBacks ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  if (!bShowBacks) return;
  // the opponent's hero back (CP-05 / CP-06), one texture per hero; never a face (F-05)
  if (BacksSlug != Model.HeroSlug) {
    BacksSlug = Model.HeroSlug;
    // -S08CardArtLegacy (ВР-CP08): the flat plate instead of the original back
    const FUmCardMediaEntry* Entry = BacksSlug.IsEmpty() || !S08ArtLook::CardArt() ? nullptr : UmCardMedia::FindBack(BacksSlug);
    BackTexture = Entry ? UmCardMedia::LoadTexture(*Entry) : nullptr;
    Backs->ClearChildren();
    BacksShown = 0;
  }
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const int32 N = FMath::Max(0, Model.HandCount);
  while (Backs->GetChildrenCount() < N) {
    USizeBox* Box = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
    Box->SetWidthOverride(UmHudDeckPanel::BackWSu);
    Box->SetHeightOverride(UmHudDeckPanel::BackHSu);
    if (BackTexture) {
      const FUmCardMediaEntry* Entry = UmCardMedia::FindBack(BacksSlug);
      UImage* Image = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass());
      FSlateBrush Brush;
      Brush.SetResourceObject(BackTexture);
      Brush.ImageSize = FVector2D(UmHudDeckPanel::BackWSu, UmHudDeckPanel::BackHSu);
      const FVector2D Uv = Entry ? Entry->Uv : FVector2D(1.0, 1.0);
      Brush.SetUVRegion(FBox2f(FVector2f(0.0f, 0.0f), FVector2f(static_cast<float>(Uv.X), static_cast<float>(Uv.Y))));
      Image->SetBrush(Brush);
      Box->SetContent(Image);
    } else {
      // 02 §6.4: the flat back until the hero's back is in the pak
      UBorder* Flat = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
      if (const FSlateBrush* Skin = Theme.Skin(TEXT("btn.normal"))) Flat->SetBrush(*Skin);
      Box->SetContent(Flat);
    }
    if (UHorizontalBoxSlot* S = Backs->AddChildToHorizontalBox(Box)) {
      S->SetPadding(FMargin(0.0f, 0.0f, UmHudDeckPanel::BackStepSu - UmHudDeckPanel::BackWSu, 0.0f));
    }
  }
  for (int32 I = 0; I < Backs->GetChildrenCount(); ++I) {
    if (UWidget* C = Backs->GetChildAt(I)) C->SetVisibility(I < N ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  }
  BacksShown = N;
}

UUmDeckRow* UUmHudDeckPanel::AcquireRow(int32 Index) {
  while (Pool.Num() <= Index) {
    UUmDeckRow* Row = CreateWidget<UUmDeckRow>(this, UUmDeckRow::StaticClass());
    if (!Row) return nullptr;
    Pool.Add(Row);
    if (Rows) Rows->AddChild(Row);
  }
  return Pool[Index];
}

void UUmHudDeckPanel::ApplyRows() {
  using namespace UmHudDeckPanel;
  const bool bLoaded = Model.List == EUmDeckListState::Loaded;
  Shown = bLoaded ? Model.ShownRows() : TArray<int32>();
  const float ListW = FMath::Max(0.0f, PanelRectSu().GetSize().X - 2.0f * PadSu - ScrollGapSu);
  for (int32 I = 0; I < Shown.Num(); ++I) {
    UUmDeckRow* Row = AcquireRow(I);
    if (!Row) continue;
    const FUmDeckRowModel& M = Model.Rows[Shown[I]];
    Row->ApplyModel(M, ListW);
    const FString CardId = M.CardId;
    TWeakObjectPtr<UUmHudDeckPanel> WeakThis(this);
    Row->SetPress(FName(*(TEXT("hud.deck.row.") + CardId)), Arbiter,
                  FS09OnHudPressOutcome::CreateLambda([WeakThis, CardId](const FS09HudPressOutcome& O) {
                    UUmHudDeckPanel* Self = WeakThis.Get();
                    if (Self && Self->Input.OnRow) Self->Input.OnRow(O, CardId);
                  }));
    Row->SetVisibility(ESlateVisibility::Visible);
  }
  for (int32 I = Shown.Num(); I < Pool.Num(); ++I) {
    if (Pool[I]) Pool[I]->SetVisibility(ESlateVisibility::Collapsed);
  }
  ScrollToRow(FirstRow);
}

int32 UUmHudDeckPanel::GetVisibleRows() const { return FMath::Min(CapacityNow, FMath::Max(0, Shown.Num() - FirstRow)); }

void UUmHudDeckPanel::ScrollToRow(int32 First) {
  const int32 MaxFirst = FMath::Max(0, Shown.Num() - CapacityNow);
  FirstRow = FMath::Clamp(First, 0, MaxFirst);
  if (Rows) Rows->SetScrollOffset(FirstRow * UmHudDeckPanel::RowSu);
  ApplyScrollbar();
}

bool UUmHudDeckPanel::WheelStep(bool bUp) {
  const int32 Before = FirstRow;
  ScrollToRow(FirstRow + (bUp ? -1 : 1));
  return FirstRow != Before;
}

bool UUmHudDeckPanel::IsScrollbarShown() const { return Shown.Num() > CapacityNow && CapacityNow > 0; }

bool UUmHudDeckPanel::IsSkeletonShown() const { return Skeleton && Skeleton->IsShown(); }

void UUmHudDeckPanel::ApplyScrollbar() {
  using namespace UmHudDeckPanel;
  const bool bBar = IsScrollbarShown();
  if (Track) Track->SetVisibility(bBar ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  if (!Thumb) return;
  Thumb->SetVisibility(bBar ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  if (!bBar) return;
  const float ViewH = CapacityNow * RowSu;
  const float ThumbH = ViewH * CapacityNow / static_cast<float>(Shown.Num());
  const int32 MaxFirst = FMath::Max(1, Shown.Num() - CapacityNow);
  const float ThumbY = ViewportTopSu + (ViewH - ThumbH) * FirstRow / static_cast<float>(MaxFirst);
  const float Iw = FMath::Max(0.0f, PanelRectSu().GetSize().X - 2.0f * PadSu);
  UmDpPlace(Thumb, FVector2D(Iw - ScrollWSu, ThumbY), FVector2D(ScrollWSu, ThumbH));
}

UUmDeckRow* UUmHudDeckPanel::GetRowWidget(int32 I) const { return Pool.IsValidIndex(I) ? Pool[I].Get() : nullptr; }

FString UUmHudDeckPanel::ApplyView(float Alpha, bool bOpen, double NowMs) {
  AlphaNow = FMath::Clamp(Alpha, 0.0f, 1.0f);
  bOpenNow = bOpen;
  const bool bDrawn = AlphaNow > 0.0f && Model.bShow;
  // clicks only while open; the close fade lets them through to the field
  const ESlateVisibility Want = !bDrawn ? ESlateVisibility::Collapsed
                                : bOpen ? ESlateVisibility::SelfHitTestInvisible
                                        : ESlateVisibility::HitTestInvisible;
  if (GetVisibility() != Want) SetVisibility(Want);
  if (!FMath::IsNearlyEqual(GetRenderOpacity(), AlphaNow, 1.0e-3f)) SetRenderOpacity(AlphaNow);
  // HB-47: the skeleton while gameDeckLists has not answered (after 300 ms of waiting)
  const bool bWaiting = bDrawn && Model.List == EUmDeckListState::Loading;
  return Skeleton ? Skeleton->SetWaiting(bWaiting, NowMs, TEXT("deckpanel")) : FString();
}

bool UUmHudDeckPanel::ContainsSu(const FVector2D& CanvasSu) const {
  if (!bOpenNow || AlphaNow <= 0.0f || !Model.bShow) return false;
  return PanelRectSu().IsInsideOrOn(CanvasSu);
}

FReply UUmHudDeckPanel::NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  // the read-only body: a click on it never reaches the board under it
  Super::NativeOnMouseButtonDown(InGeometry, InMouseEvent);
  return FReply::Handled();
}

FReply UUmHudDeckPanel::NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  Super::NativeOnMouseButtonUp(InGeometry, InMouseEvent);
  return FReply::Handled();
}

FReply UUmHudDeckPanel::NativeOnMouseWheel(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) {
  WheelStep(InMouseEvent.GetWheelDelta() > 0.0f);
  return FReply::Handled();
}

void UUmHudDeckPanel::CollectShotLines(TArray<FString>& Out) const {
  const bool bVisible = bHasModel && Model.bShow && AlphaNow > 0.0f && UmGameHudSlots::ShownByProperty(this);
  const FBox2D Su = PanelRectSu();
  const float Px = Frame.PxPerSu > 0.0f ? Frame.PxPerSu : 1.0f;
  FS08ScreenRect Rect;
  if (Su.bIsValid) Rect = FS08ScreenRect(Su.Min.X * Px, Su.Min.Y * Px, Su.Max.X * Px, Su.Max.Y * Px);
  int32 SumHand = 0, SumDiscard = 0, SumLeft = 0;
  for (const FUmDeckRowModel& R : Model.Rows) {
    SumHand += R.InHand;
    SumDiscard += R.InDiscard;
    SumLeft += R.Left;
  }
  const TCHAR* List = Model.List == EUmDeckListState::Loaded ? TEXT("loaded")
                      : Model.List == EUmDeckListState::Failed ? TEXT("failed")
                                                               : TEXT("loading");
  // counts only - no card name, no card id (the opponent's composition is public; the order never is)
  const FString Extra = FString::Printf(
      TEXT("class=%s filter=%d list=%s rows=%d shown=%d rowsVisible=%d first=%d capacity=%d copies=%d deck=%d%s discard=%d%s "
           "hand=%d sumHand=%d sumDiscard=%d sumLeft=%d titleSu=%.0f titleLines=%d header=%.1f viewport=%.0f scroll=%d "
           "skeleton=%d alpha=%.2f open=%d bottom=%.0f pool=%d"),
      Frame.bClassS ? TEXT("S") : TEXT("L"), Model.bFilterDiscard ? 1 : 0, List, Model.Rows.Num(), Shown.Num(),
      GetVisibleRows(), FirstRow, CapacityNow, Model.Copies, Model.DeckCount, Model.bDeckStale ? TEXT("~") : TEXT(""),
      Model.DiscardCount, Model.bDiscardStale ? TEXT("~") : TEXT(""), Model.HandCount,
      Model.Side == ES09DeckSide::Own ? SumHand : 0, SumDiscard, Model.Side == ES09DeckSide::Own ? SumLeft : 0, TitleSizeNow,
      TitleLinesNow.Num(), HeaderNow, CapacityNow * UmHudDeckPanel::RowSu, IsScrollbarShown() ? 1 : 0,
      IsSkeletonShown() ? 1 : 0, AlphaNow, bOpenNow ? 1 : 0, Su.bIsValid ? Su.Max.Y : 0.0, Pool.Num());
  Out.Add(S08ArtHud::FormatWidgetLineEx(TEXT("UI-HUD-DECKPANEL"), TEXT("umg"), UmHudDeckPanel::StateName(Model), FString(), Rect,
                                        bVisible && !Rect.IsEmpty(), bVisible, SourceName(), Extra));
}

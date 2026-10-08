// VS-7 SC-19, SC-20: the match loading - see UmScreenLoading.h.
#include "UmScreenLoading.h"

#include "../S08AnimatedIconWidget.h"
#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHeroCard.h"
#include "UmHudScale.h"
#include "UmHudTheme.h"
#include "UmScreenLobby.h"
#include "UmSpinner.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/Image.h"
#include "Components/CanvasPanel.h"
#include "Components/NamedSlot.h"
#include "Components/TextBlock.h"
#include "HAL/PlatformTime.h"

using namespace UmRoomUi;

const TCHAR* const UUmScreenLoading::WidgetBlueprintPath = TEXT("/Game/S08/UI/Screens/WBP_UI_SCR_LOADING");

UClass* UUmScreenLoading::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmScreenLoading::StaticClass(), WidgetBlueprintPath); }

namespace UmLoading {
const TCHAR* StageName(EUmLoadingStage S) {
  switch (S) {
    case EUmLoadingStage::State: return TEXT("state");
    case EUmLoadingStage::Board: return TEXT("board");
    case EUmLoadingStage::Error: return TEXT("error");
    default: return TEXT("connect");
  }
}

const TCHAR* StageKey(EUmLoadingStage S) {
  switch (S) {
    case EUmLoadingStage::State: return TEXT("screens.loading.state");
    case EUmLoadingStage::Board: return TEXT("screens.loading.board");
    case EUmLoadingStage::Error: return TEXT("screens.loading.error");
    default: return TEXT("screens.loading.connect");
  }
}
}  // namespace UmLoading

namespace {
const TCHAR* const UmLdTexts[] = {TEXT("StageText"), TEXT("LeftName"), TEXT("RightName"), TEXT("LeftNick"), TEXT("RightNick"),
                                  TEXT("VersusText"), TEXT("BoardText")};

template <typename T>
T* UmLdFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}
}  // namespace

bool UUmScreenLoading::AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  UCanvasPanel* ContentW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Content")));
  ContentW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(ContentW, Parent)) return Fail(TEXT("Content"));
  for (const TCHAR* Name : {TEXT("LoadingPanel"), TEXT("LeftCard"), TEXT("RightCard"), TEXT("LeftPortrait"), TEXT("RightPortrait")}) {
    UBorder* B = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(Name));
    B->SetVisibility(ESlateVisibility::HitTestInvisible);
    B->SetPadding(FMargin(0.0f));
    B->SetHorizontalAlignment(HAlign_Center);
    B->SetVerticalAlignment(VAlign_Center);
    if (!Attach(B, ContentW)) return Fail(Name);
  }
  for (const TCHAR* Name : UmLdTexts) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (!Attach(T, ContentW)) return Fail(Name);
  }
  if (!Attach(Tree.ConstructWidget<UUmSpinner>(UUmSpinner::WidgetClass(), FName(TEXT("Spinner"))), ContentW)) return Fail(TEXT("Spinner"));
  if (!Attach(Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("ErrorIcon"))), ContentW)) {
    return Fail(TEXT("ErrorIcon"));
  }
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  for (const TCHAR* Name : {TEXT("LobbyButton"), TEXT("RetryButton")}) {
    if (!Attach(Tree.ConstructWidget<UUmButton>(ButtonClass, FName(Name)), ContentW)) return Fail(Name);
  }
  return true;
}

bool UUmScreenLoading::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  if (!UUmScreenBase::BuildDefaultTree(Tree, Attach, OutError)) return false;
  UNamedSlot* BodyW = Cast<UNamedSlot>(Tree.FindWidget(FName(TEXT("Body"))));
  if (!BodyW) {
    if (OutError) *OutError = TEXT("no Body");
    return false;
  }
  return AttachContent(Tree, BodyW, Attach, OutError);
}

void UUmScreenLoading::BuildContent() {
  if (!WidgetTree || !Body || Body->GetContent()) return;
  FString Problem;
  auto AddTo = [](UWidget* Child, UPanelWidget* Parent) { return Parent && Parent->AddChild(Child) != nullptr; };
  if (!AttachContent(*WidgetTree, Body, AddTo, &Problem)) UE_LOG(LogTemp, Error, TEXT("UMHUD loading content: %s"), *Problem);
}

void UUmScreenLoading::BindParts() {
  Content = UmLdFind<UCanvasPanel>(WidgetTree, TEXT("Content"));
  LoadingPanel = UmLdFind<UBorder>(WidgetTree, TEXT("LoadingPanel"));
  LeftCard = UmLdFind<UBorder>(WidgetTree, TEXT("LeftCard"));
  RightCard = UmLdFind<UBorder>(WidgetTree, TEXT("RightCard"));
  LeftPortrait = UmLdFind<UBorder>(WidgetTree, TEXT("LeftPortrait"));
  RightPortrait = UmLdFind<UBorder>(WidgetTree, TEXT("RightPortrait"));
  StageText = UmLdFind<UTextBlock>(WidgetTree, TEXT("StageText"));
  LeftName = UmLdFind<UTextBlock>(WidgetTree, TEXT("LeftName"));
  RightName = UmLdFind<UTextBlock>(WidgetTree, TEXT("RightName"));
  LeftNick = UmLdFind<UTextBlock>(WidgetTree, TEXT("LeftNick"));
  RightNick = UmLdFind<UTextBlock>(WidgetTree, TEXT("RightNick"));
  VersusText = UmLdFind<UTextBlock>(WidgetTree, TEXT("VersusText"));
  BoardText = UmLdFind<UTextBlock>(WidgetTree, TEXT("BoardText"));
  Spinner = UmLdFind<UUmSpinner>(WidgetTree, TEXT("Spinner"));
  ErrorIcon = UmLdFind<US08AnimatedIconWidget>(WidgetTree, TEXT("ErrorIcon"));
  LobbyButton = UmLdFind<UUmButton>(WidgetTree, TEXT("LobbyButton"));
  RetryButton = UmLdFind<UUmButton>(WidgetTree, TEXT("RetryButton"));
}

bool UUmScreenLoading::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  SetUiId(TEXT("UI-SCR-LOADING"));
  SetScreenState(FName(TEXT("connect")));
  BindParts();
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const float ScalePx = UmHudScale::Current().PxPerSu();
  if (LoadingPanel) {
    if (const FSlateBrush* Screen = Theme.SkinFor(TEXT("modal"), ScalePx)) LoadingPanel->SetBrush(*Screen);
  }
  for (UBorder* B : {LeftPortrait.Get(), RightPortrait.Get()}) {
    if (B) B->SetBrush(FSlateNoResource());  // a UBorder's default brush is a white box
  }
  for (UBorder* B : {LeftCard.Get(), RightCard.Get()}) {
    if (const FSlateBrush* Inset = Theme.Skin(TEXT("panel.inset"))) {
      if (B) B->SetBrush(*Inset);
    }
  }
  Style(StageText, TEXT("type.title"), TEXT("text.primary"));
  Style(LeftName, TEXT("type.heading"), TEXT("text.primary"));
  Style(RightName, TEXT("type.heading"), TEXT("text.primary"));
  Style(LeftNick, TEXT("type.caption"), TEXT("text.secondary"));
  Style(RightNick, TEXT("type.caption"), TEXT("text.secondary"));
  Style(VersusText, TEXT("type.heading"), TEXT("text.secondary"));
  Style(BoardText, TEXT("type.heading"), TEXT("text.primary"));
  for (UTextBlock* T : {LeftName.Get(), RightName.Get(), LeftNick.Get(), RightNick.Get(), VersusText.Get(), BoardText.Get()}) {
    if (T) {
      T->SetJustification(ETextJustify::Center);
      T->SetTextOverflowPolicy(ETextOverflowPolicy::Ellipsis);  // VS-7 Frames: «против» +30 % ran over the cards
      T->SetClipping(EWidgetClipping::ClipToBounds);             // the ellipsis needs the clip rect (as UmHudLog)
    }
  }
  if (Spinner) Spinner->SetSizeSu(48.0f);
  Icon(ErrorIcon, TEXT("resource-connection-lost"), 48.0f);
  if (Frame) Frame->SetBrush(FSlateNoResource());
  Refresh();
  return bFirst;
}

bool UUmScreenLoading::HasAllParts(FString* OutMissing) const {
  FString Base;
  HasBaseParts(&Base);
  TArray<FString> Missing;
  if (!Base.IsEmpty()) Missing.Add(Base);
  auto Need = [&Missing](const UObject* P, const TCHAR* Name) {
    if (!P) Missing.Add(Name);
  };
  Need(LoadingPanel, TEXT("LoadingPanel"));
  Need(Spinner, TEXT("Spinner"));
  Need(ErrorIcon, TEXT("ErrorIcon"));
  Need(StageText, TEXT("StageText"));
  Need(LeftCard, TEXT("LeftCard"));
  Need(RightCard, TEXT("RightCard"));
  Need(LeftPortrait, TEXT("LeftPortrait"));
  Need(RightPortrait, TEXT("RightPortrait"));
  Need(LeftName, TEXT("LeftName"));
  Need(RightName, TEXT("RightName"));
  Need(LeftNick, TEXT("LeftNick"));
  Need(RightNick, TEXT("RightNick"));
  Need(VersusText, TEXT("VersusText"));
  Need(BoardText, TEXT("BoardText"));
  Need(LobbyButton, TEXT("LobbyButton"));
  Need(RetryButton, TEXT("RetryButton"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmScreenLoading::ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu) {
  SetCanvas(InCanvasSu, bInClassS, InPxPerSu);
  if (Frame) Frame->SetBrush(FSlateNoResource());
  RebuildDiscs();
  Layout();
}

void UUmScreenLoading::SetSides(const FUmLoadingSide& Own, const FUmLoadingSide& Opp, const FString& InBoardId, const FString& BoardName) {
  Sides[0] = Own;
  Sides[1] = Opp;
  BoardId = InBoardId;
  if (LeftName) LeftName->SetText(FText::FromString(Own.HeroName));
  if (RightName) RightName->SetText(FText::FromString(Opp.HeroName));
  if (LeftNick) LeftNick->SetText(FText::FromString(Own.Nick));
  if (RightNick) RightNick->SetText(FText::FromString(Opp.Nick));
  if (BoardText) BoardText->SetText(FText::FromString(BoardName));
  RebuildDiscs();
  Refresh();
}

void UUmScreenLoading::SetStage(EUmLoadingStage InStage) {
  if (Stage == InStage) return;
  Stage = InStage;
  Refresh();
}

void UUmScreenLoading::SetVeilOpaque(bool bOpaque) {
  if (bVeilOpaque == bOpaque) return;
  bVeilOpaque = bOpaque;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (Veil) Veil->SetColorAndOpacity(bOpaque ? Theme.Color(TEXT("card.navy")) : Theme.Color(TEXT("panel.veil")));
}

void UUmScreenLoading::RebuildDiscs() {
  if (!WidgetTree || !LeftPortrait || !RightPortrait) return;
  if (DiscKeys[0] == Sides[0].HeroKey.ToString() && DiscKeys[1] == Sides[1].HeroKey.ToString() && DiscPx == PxPerSu) return;
  DiscKeys[0] = Sides[0].HeroKey.ToString();
  DiscKeys[1] = Sides[1].HeroKey.ToString();
  DiscPx = PxPerSu;
  KeepAlive.Reset();
  PortraitLines.Reset();
  FString Line;
  LeftPortrait->SetContent(MakeDisc(*WidgetTree, this, Sides[0].HeroKey, Sides[0].HeroName, 160.0f, PxPerSu, 0.0f, KeepAlive, &Line, TEXT("loading")));
  if (!Line.IsEmpty()) PortraitLines.Add(Line);
  RightPortrait->SetContent(MakeDisc(*WidgetTree, this, Sides[1].HeroKey, Sides[1].HeroName, 160.0f, PxPerSu, 0.0f, KeepAlive, &Line, TEXT("loading")));
  if (!Line.IsEmpty()) PortraitLines.Add(Line.Replace(TEXT("side=own"), TEXT("side=opp")));
}

FBox2D UUmScreenLoading::PanelRectSu() const {
  const float H = UmLoading::PanelHSu + (Stage == EUmLoadingStage::Error ? UmLoading::ErrorGrowSu : 0.0f);
  const FVector2D Size(UmLoading::PanelWSu, H);
  const FVector2D Min = 0.5 * (CanvasSu - Size);
  return FBox2D(Min, Min + Size);
}

void UUmScreenLoading::Layout() {
  const FVector2D O = FrameRectSu().Min;
  auto P = [&O](UWidget* W, float X, float Y, float Wd, float Ht) { Place(W, FVector2D(X, Y) - O, FVector2D(Wd, Ht)); };
  const FBox2D R = PanelRectSu();
  const float X0 = R.Min.X, Y0 = R.Min.Y;
  P(LoadingPanel, X0, Y0, R.GetSize().X, R.GetSize().Y);
  // ВР-VS5-SC19-04: the stage row keeps the width of the longest caption, the spinner does not jump
  float Longest = 0.0f;
  for (EUmLoadingStage S : {EUmLoadingStage::Connect, EUmLoadingStage::State, EUmLoadingStage::Board, EUmLoadingStage::Error}) {
    Longest = FMath::Max(Longest, MeasureW(UmRoomUi::S(UmLoading::StageKey(S)), TEXT("type.title")));
  }
  const float GroupW = 48.0f + 12.0f + Longest + 4.0f;
  const float Gx = X0 + 0.5f * (UmLoading::PanelWSu - GroupW);
  const float RowY = Y0 + 24.0f;
  P(Spinner, Gx, RowY, 48.0f, 48.0f);
  P(ErrorIcon, Gx, RowY, 48.0f, 48.0f);
  P(StageText, Gx + 60.0f, RowY + 6.0f, Longest + 4.0f, 36.0f);
  const float CardsY = RowY + 48.0f + 24.0f;
  const float Lx = X0 + 24.0f, Rx = X0 + 24.0f + 240.0f + 96.0f;
  P(LeftCard, Lx, CardsY, 240.0f, 320.0f);
  P(RightCard, Rx, CardsY, 240.0f, 320.0f);
  // ВР-VS5-SC19-03: portrait 160, 16, name, 4, nick - centred in the card
  const float Block = 160.0f + 16.0f + 30.0f + 4.0f + 18.0f;
  const float Py = CardsY + 0.5f * (320.0f - Block);
  for (int32 I = 0; I < 2; ++I) {
    const float Cx = I == 0 ? Lx : Rx;
    P(I == 0 ? LeftPortrait.Get() : RightPortrait.Get(), Cx + 40.0f, Py, 160.0f, 160.0f);
    P(I == 0 ? LeftName.Get() : RightName.Get(), Cx + 8.0f, Py + 176.0f, 224.0f, 30.0f);
    P(I == 0 ? LeftNick.Get() : RightNick.Get(), Cx + 8.0f, Py + 210.0f, 224.0f, 20.0f);
  }
  P(VersusText, Lx + 240.0f, CardsY + 160.0f - 15.0f, 96.0f, 30.0f);
  const float BoardY = CardsY + 320.0f + 24.0f;
  P(BoardText, X0 + 24.0f, BoardY, UmLoading::PanelWSu - 48.0f, 30.0f);
  // SC-20 (ВР-VS5-SC20-02): «В ЛОББИ» normal left, «ПОВТОРИТЬ» primary right, 16 su apart, the same width
  const float BtnW = FMath::Max(168.0f, FMath::Max(MeasureW(FText::FromString(UmRoomUi::S(TEXT("common.btn.lobby")).ToUpper().ToString()), TEXT("type.button")),
                                                   MeasureW(FText::FromString(UmRoomUi::S(TEXT("common.btn.retry")).ToUpper().ToString()), TEXT("type.button"))) + 48.0f);
  const float BtnY = BoardY + 30.0f + 24.0f;
  const float Bx = X0 + 0.5f * (UmLoading::PanelWSu - (2.0f * BtnW + 16.0f));
  P(LobbyButton, Bx, BtnY, BtnW, 48.0f);
  P(RetryButton, Bx + BtnW + 16.0f, BtnY, BtnW, 48.0f);
}

void UUmScreenLoading::Refresh() {
  const bool bError = Stage == EUmLoadingStage::Error;
  if (StageText) StageText->SetText(UmRoomUi::S(UmLoading::StageKey(Stage)));
  if (VersusText) VersusText->SetText(UmRoomUi::S(TEXT("screens.loading.versus")));
  Vis(Spinner, !bError);
  Vis(ErrorIcon, bError);
  if (Spinner) Spinner->SetWaiting(!bError && IsShown(), FPlatformTime::Seconds() * 1000.0, TEXT("loading"));
  auto Btn = [](UUmButton* B, const FText& Label, EUmButtonVariant V) {
    if (!B) return;
    FUmButtonModel M;
    M.Variant = V;
    M.Label = Label;
    M.HeightSu = 48.0f;
    M.MinWidthSu = 168.0f;
    B->ApplyModel(M);
  };
  Btn(LobbyButton, UmRoomUi::S(TEXT("common.btn.lobby")), EUmButtonVariant::Normal);
  Btn(RetryButton, UmRoomUi::S(TEXT("common.btn.retry")), EUmButtonVariant::Primary);
  Vis(LobbyButton, bError, true);
  Vis(RetryButton, bError, true);
  SetScreenState(FName(UmLoading::StageName(Stage)));
  Layout();
}

FString UUmScreenLoading::GetStageText() const { return StageText ? StageText->GetText().ToString() : FString(); }
FString UUmScreenLoading::GetLeftName() const { return LeftName ? LeftName->GetText().ToString() : FString(); }
FString UUmScreenLoading::GetRightName() const { return RightName ? RightName->GetText().ToString() : FString(); }
FString UUmScreenLoading::GetBoardText() const { return BoardText ? BoardText->GetText().ToString() : FString(); }
bool UUmScreenLoading::IsSpinnerSlotSpinner() const { return Spinner && Spinner->GetVisibility() != ESlateVisibility::Collapsed; }
bool UUmScreenLoading::IsErrorIconShown() const { return ErrorIcon && ErrorIcon->GetVisibility() != ESlateVisibility::Collapsed; }
bool UUmScreenLoading::AreButtonsShown() const { return RetryButton && RetryButton->GetVisibility() != ESlateVisibility::Collapsed; }
bool UUmScreenLoading::IsRetryPrimary() const {
  return AreButtonsShown() && RetryButton->GetModel().Variant == EUmButtonVariant::Primary;
}
bool UUmScreenLoading::IsLobbyPrimary() const {
  return LobbyButton && LobbyButton->GetVisibility() != ESlateVisibility::Collapsed && LobbyButton->GetModel().Variant == EUmButtonVariant::Primary;
}

FString UUmScreenLoading::ShotExtra() const {
  const TCHAR* Board = BoardId == UmLobby::SarpedonId ? TEXT("sarpedon") : BoardId == UmLobby::MarmorealId ? TEXT("marmoreal") : TEXT("other");
  const int32 Heroes = (Sides[0].HeroName.IsEmpty() ? 0 : 1) + (Sides[1].HeroName.IsEmpty() ? 0 : 1);
  return FString::Printf(TEXT(" board=%s heroes=%d primary=%s veil=%s"), Board, Heroes, IsRetryPrimary() ? TEXT("retry") : TEXT("none"),
                         bVeilOpaque ? TEXT("opaque") : TEXT("0.60"));
}

void UUmScreenLoading::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput) {
  Arbiter = InArbiter;
  Input = MoveTemp(InInput);
  TWeakObjectPtr<UUmScreenLoading> WeakThis(this);
  for (const TPair<UUmButton*, const TCHAR*>& B : {TPair<UUmButton*, const TCHAR*>(LobbyButton.Get(), TEXT("common.btn.lobby")),
                                                   TPair<UUmButton*, const TCHAR*>(RetryButton.Get(), TEXT("common.btn.retry"))}) {
    if (!B.Key) continue;
    const FName Name(B.Value);
    B.Key->SetPress(Name, Arbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, Name](const FS09HudPressOutcome& O) {
      if (UUmScreenLoading* Self = WeakThis.Get()) Self->OnPressOutcome(Name, O);
    }));
  }
}

void UUmScreenLoading::OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome) {
  if (Outcome.Result != ES09HudPressResult::Act || Stage != EUmLoadingStage::Error) return;
  if (Input.OnSound) Input.OnSound(FName(TEXT("UI-BTN-CLICK")));
  if (Id == FName(TEXT("common.btn.retry"))) {
    if (Input.OnRetry) Input.OnRetry();
  } else if (Input.OnLobby) {
    Input.OnLobby();
  }
}

void UUmScreenLoading::SimulatePress(FName Id) {
  if (!Arbiter.IsValid()) Arbiter = MakeShared<FS09HudPressArbiter>();
  Arbiter->Press(Id, Arbiter->Now());
  OnPressOutcome(Id, FS09HudPressArbiter::Decide(Arbiter->Release(Id, Arbiter->Now()), FS09Reason()));
}

void UUmScreenLoading::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  if (Spinner && IsShown()) Spinner->SetWaiting(Stage != EUmLoadingStage::Error, FPlatformTime::Seconds() * 1000.0, TEXT("loading"));
}

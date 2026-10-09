// VS-7 S5 SC-34...SC-37: the result screen - see UmScreenGameOver.h.
#include "UmScreenGameOver.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08ArtHud.h"
#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHeroCard.h"
#include "UmHudScale.h"
#include "UmHudTheme.h"
#include "UmPortrait.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/Image.h"
#include "Components/NamedSlot.h"
#include "Components/TextBlock.h"

using namespace UmRoomUi;

const TCHAR* const UUmScreenGameOver::WidgetBlueprintPath = TEXT("/Game/S08/UI/Screens/WBP_UI_SCR_GAMEOVER");

UClass* UUmScreenGameOver::WidgetClass() {
  return UmGameHudSlots::WbpOrNative(UUmScreenGameOver::StaticClass(), WidgetBlueprintPath);
}

namespace UmGameOver {
const TCHAR* OutcomeName(EUmGameOverOutcome O) {
  switch (O) {
    case EUmGameOverOutcome::Victory: return TEXT("victory");
    case EUmGameOverOutcome::Defeat: return TEXT("defeat");
    case EUmGameOverOutcome::Draw: return TEXT("draw");
    default: return TEXT("unknown");
  }
}

const TCHAR* StateName(const FUmGameOverModel& M) {
  if (M.bAgainBusy) return TEXT("again");
  if (M.bBoard) return TEXT("board");
  return OutcomeName(M.Outcome);
}

FVector2D ModalSize(bool bClassS, bool bVsAi) {
  if (!bClassS) return FVector2D(ModalWSu, ModalHSu);
  return FVector2D(bVsAi ? ModalWSu : ModalSWSu, ModalSHSu);
}

FText OutcomeText(EUmGameOverOutcome O) {
  switch (O) {
    case EUmGameOverOutcome::Victory: return S(TEXT("screens.result.victory"));
    case EUmGameOverOutcome::Defeat: return S(TEXT("screens.result.defeat"));
    case EUmGameOverOutcome::Draw: return S(TEXT("screens.result.draw"));
    default: return S(TEXT("screens.result.unknown"));
  }
}

FText HeadlineText(const FUmGameOverModel& M) {
  if (M.WinnerHero.IsEmpty() || M.Outcome == EUmGameOverOutcome::Draw || M.Outcome == EUmGameOverOutcome::Unknown) return FText::GetEmpty();
  FFormatNamedArguments A;
  A.Add(TEXT("hero"), FText::FromString(M.WinnerHero));
  return UmText::Format(EUmTable::Screens, TEXT("screens.result.wins"), A).ToUpper();
}

FText ReasonText(const FUmGameOverModel& M) {
  if (M.LoserHero.IsEmpty() || M.Outcome == EUmGameOverOutcome::Draw || M.Outcome == EUmGameOverOutcome::Unknown) return FText::GetEmpty();
  FFormatNamedArguments A;
  A.Add(TEXT("hero"), FText::FromString(M.LoserHero));
  return UmText::Format(EUmTable::Screens, TEXT("screens.result.reason.hp"), A);
}

FString Duration(int32 Seconds) {
  if (Seconds < 0) return FString();
  if (Seconds >= 3600) return FString::Printf(TEXT("%d:%02d:%02d"), Seconds / 3600, (Seconds / 60) % 60, Seconds % 60);
  return FString::Printf(TEXT("%d:%02d"), Seconds / 60, Seconds % 60);
}

FText TurnText(const FUmGameOverModel& M) {
  if (M.Outcome == EUmGameOverOutcome::Draw || M.Outcome == EUmGameOverOutcome::Unknown || M.Turn <= 0) return FText::GetEmpty();
  FFormatNamedArguments A;
  A.Add(TEXT("n"), FText::AsNumber(M.Turn));
  if (M.DurationSec < 0) return UmText::Format(EUmTable::Screens, TEXT("screens.aborted.turn"), A);  // «Ход {n}»
  A.Add(TEXT("time"), FText::FromString(Duration(M.DurationSec)));
  return UmText::Format(EUmTable::Screens, TEXT("screens.result.turn.time"), A);
}

FString CaptionLead(const FUmGameOverSide& Side) {
  FString Out = Side.Role;
  if (Side.Hp >= 0 && Side.MaxHp > 0) {
    FFormatNamedArguments A;
    A.Add(TEXT("hp"), FText::AsNumber(Side.Hp));
    A.Add(TEXT("max"), FText::AsNumber(Side.MaxHp));
    Out += TEXT(" · HP ") + UmText::Format(EUmTable::Hud, TEXT("hud.panel.hp"), A).ToString();
  }
  if (Side.bWinner || Side.bFallen) Out += TEXT(" · ");
  return Out;
}

FText CaptionVerdict(const FUmGameOverSide& Side) {
  if (Side.bWinner) return S(TEXT("screens.result.winner"));
  if (Side.bFallen) return S(TEXT("screens.result.defeated"));
  return FText::GetEmpty();
}

FText StripText(const FUmGameOverModel& M) {
  FFormatNamedArguments A;
  A.Add(TEXT("n"), FText::AsNumber(M.Turn));
  A.Add(TEXT("outcome"), OutcomeText(M.Outcome));
  return UmText::Format(EUmTable::Screens, TEXT("screens.result.board.turn"), A).ToUpper();
}

EUmAgainStep NextAgainStep(EUmAgainStep Step, const FUmAgainInput& In) {
  if (Step == EUmAgainStep::Idle || Step == EUmAgainStep::Done || Step == EUmAgainStep::Failed) return Step;
  if (In.bError || In.bTimedOut) return EUmAgainStep::Failed;
  switch (Step) {
    case EUmAgainStep::Leave: return In.bLobby ? EUmAgainStep::Create : Step;
    case EUmAgainStep::Create: return In.bRoom ? EUmAgainStep::Select : Step;
    case EUmAgainStep::Select: return In.bRoom && In.bHeroPicked ? EUmAgainStep::Ready : Step;
    case EUmAgainStep::Ready: return In.bRoom && In.bReady ? EUmAgainStep::Start : Step;
    case EUmAgainStep::Start: return In.bNewMatch ? EUmAgainStep::Done : Step;
    default: return Step;
  }
}

const TCHAR* AgainStepName(EUmAgainStep Step) {
  switch (Step) {
    case EUmAgainStep::Leave: return TEXT("leave");
    case EUmAgainStep::Create: return TEXT("create");
    case EUmAgainStep::Select: return TEXT("select");
    case EUmAgainStep::Ready: return TEXT("ready");
    case EUmAgainStep::Start: return TEXT("start");
    case EUmAgainStep::Done: return TEXT("done");
    case EUmAgainStep::Failed: return TEXT("failed");
    default: return TEXT("idle");
  }
}

double OverlapPx2(const FBox2D& A, const FBox2D& B, float PxPerSu) {
  if (!A.bIsValid || !B.bIsValid) return 0.0;
  const double W = FMath::Min(A.Max.X, B.Max.X) - FMath::Max(A.Min.X, B.Min.X);
  const double H = FMath::Min(A.Max.Y, B.Max.Y) - FMath::Max(A.Min.Y, B.Min.Y);
  if (W <= 0.0 || H <= 0.0) return 0.0;
  return W * H * PxPerSu * PxPerSu;
}
}  // namespace UmGameOver

namespace {
template <typename T>
T* UmGoFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

const TCHAR* const UmGoBorders[] = {TEXT("ResultModal"), TEXT("LeftPortrait"), TEXT("RightPortrait"), TEXT("BoardStrip")};
const TCHAR* const UmGoTexts[] = {TEXT("OutcomeText"), TEXT("HeadlineText"), TEXT("ReasonText"), TEXT("TurnText"), TEXT("VersusText"),
                                  TEXT("LeftName"), TEXT("RightName"), TEXT("LeftCaption"), TEXT("RightCaption"), TEXT("LeftVerdict"),
                                  TEXT("RightVerdict"), TEXT("StripText")};
const TCHAR* const UmGoIcons[] = {TEXT("LeftHeart"), TEXT("RightHeart")};
const TCHAR* const UmGoButtons[] = {TEXT("ViewBoardButton"), TEXT("AgainButton"), TEXT("LobbyButton"), TEXT("ResultsButton"),
                                    TEXT("StripLobbyButton")};
constexpr float UmGoHeartSu = 24.0f;

/** The key chip width of a button (ВР-VS5-SC34-05): 20 su, wider for «Enter» (text + 2 x 4 su), 8 su after the label. */
float UmGoChipW(const FText& Key) {
  if (Key.IsEmpty()) return 0.0f;
  return 8.0f + FMath::Max(20.0f, MeasureW(Key, TEXT("type.tag")) + 8.0f);
}

float UmGoLabelW(const FText& Label) { return MeasureW(Label.ToUpper(), TEXT("type.button")); }
}  // namespace

bool UUmScreenGameOver::AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  UCanvasPanel* ContentW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Content")));
  ContentW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(ContentW, Parent)) return Fail(TEXT("Content"));
  for (const TCHAR* Name : UmGoBorders) {
    UBorder* B = Tree.ConstructWidget<UBorder>(UBorder::StaticClass(), FName(Name));
    B->SetVisibility(ESlateVisibility::HitTestInvisible);
    B->SetPadding(FMargin(0.0f));
    B->SetHorizontalAlignment(HAlign_Center);
    B->SetVerticalAlignment(VAlign_Center);
    if (!Attach(B, ContentW)) return Fail(Name);
  }
  for (const TCHAR* Name : UmGoTexts) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (!Attach(T, ContentW)) return Fail(Name);
  }
  for (const TCHAR* Name : UmGoIcons) {
    if (!Attach(Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(Name)), ContentW)) return Fail(Name);
  }
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  for (const TCHAR* Name : UmGoButtons) {
    if (!Attach(Tree.ConstructWidget<UUmButton>(ButtonClass, FName(Name)), ContentW)) return Fail(Name);
  }
  return true;
}

bool UUmScreenGameOver::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  if (!UUmScreenBase::BuildDefaultTree(Tree, Attach, OutError)) return false;
  UNamedSlot* BodyW = Cast<UNamedSlot>(Tree.FindWidget(FName(TEXT("Body"))));
  if (!BodyW) {
    if (OutError) *OutError = TEXT("no Body");
    return false;
  }
  return AttachContent(Tree, BodyW, Attach, OutError);
}

void UUmScreenGameOver::BuildContent() {
  if (!WidgetTree || !Body || Body->GetContent()) return;
  FString Problem;
  auto AddTo = [](UWidget* Child, UPanelWidget* Parent) { return Parent && Parent->AddChild(Child) != nullptr; };
  if (!AttachContent(*WidgetTree, Body, AddTo, &Problem)) UE_LOG(LogTemp, Error, TEXT("UMHUD gameover content: %s"), *Problem);
}

void UUmScreenGameOver::BindParts() {
  Content = UmGoFind<UCanvasPanel>(WidgetTree, TEXT("Content"));
  ResultModal = UmGoFind<UBorder>(WidgetTree, TEXT("ResultModal"));
  LeftPortrait = UmGoFind<UBorder>(WidgetTree, TEXT("LeftPortrait"));
  RightPortrait = UmGoFind<UBorder>(WidgetTree, TEXT("RightPortrait"));
  BoardStrip = UmGoFind<UBorder>(WidgetTree, TEXT("BoardStrip"));
  OutcomeText = UmGoFind<UTextBlock>(WidgetTree, TEXT("OutcomeText"));
  HeadlineText = UmGoFind<UTextBlock>(WidgetTree, TEXT("HeadlineText"));
  ReasonText = UmGoFind<UTextBlock>(WidgetTree, TEXT("ReasonText"));
  TurnText = UmGoFind<UTextBlock>(WidgetTree, TEXT("TurnText"));
  VersusText = UmGoFind<UTextBlock>(WidgetTree, TEXT("VersusText"));
  LeftName = UmGoFind<UTextBlock>(WidgetTree, TEXT("LeftName"));
  RightName = UmGoFind<UTextBlock>(WidgetTree, TEXT("RightName"));
  LeftCaption = UmGoFind<UTextBlock>(WidgetTree, TEXT("LeftCaption"));
  RightCaption = UmGoFind<UTextBlock>(WidgetTree, TEXT("RightCaption"));
  LeftVerdict = UmGoFind<UTextBlock>(WidgetTree, TEXT("LeftVerdict"));
  RightVerdict = UmGoFind<UTextBlock>(WidgetTree, TEXT("RightVerdict"));
  StripText = UmGoFind<UTextBlock>(WidgetTree, TEXT("StripText"));
  LeftHeart = UmGoFind<US08AnimatedIconWidget>(WidgetTree, TEXT("LeftHeart"));
  RightHeart = UmGoFind<US08AnimatedIconWidget>(WidgetTree, TEXT("RightHeart"));
  ViewBoardButton = UmGoFind<UUmButton>(WidgetTree, TEXT("ViewBoardButton"));
  AgainButton = UmGoFind<UUmButton>(WidgetTree, TEXT("AgainButton"));
  LobbyButton = UmGoFind<UUmButton>(WidgetTree, TEXT("LobbyButton"));
  ResultsButton = UmGoFind<UUmButton>(WidgetTree, TEXT("ResultsButton"));
  StripLobbyButton = UmGoFind<UUmButton>(WidgetTree, TEXT("StripLobbyButton"));
}

bool UUmScreenGameOver::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  SetUiId(TEXT("UI-SCR-GAMEOVER"));
  SetScreenState(FName(TEXT("unknown")));
  BindParts();
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const float ScalePx = UmHudScale::Current().PxPerSu();
  if (ResultModal) {
    if (const FSlateBrush* Skin = Theme.SkinFor(TEXT("modal"), ScalePx)) ResultModal->SetBrush(*Skin);
  }
  if (BoardStrip) {
    if (const FSlateBrush* Skin = Theme.SkinFor(TEXT("panel"), ScalePx)) BoardStrip->SetBrush(*Skin);  // panel.bg 0.92
  }
  for (UBorder* B : {LeftPortrait.Get(), RightPortrait.Get()}) {
    if (B) B->SetBrush(FSlateNoResource());
  }
  Style(OutcomeText, TEXT("type.display"), TEXT("turn.flash.yellow"));
  Style(HeadlineText, TEXT("type.title"), TEXT("card.cream"));
  Style(ReasonText, TEXT("type.body"), TEXT("text.primary"));
  Style(TurnText, TEXT("type.caption"), TEXT("text.secondary"));
  Style(VersusText, TEXT("type.heading"), TEXT("text.secondary"));
  Style(LeftName, TEXT("type.heading"), TEXT("text.primary"));
  Style(RightName, TEXT("type.heading"), TEXT("text.primary"));
  Style(LeftCaption, TEXT("type.caption"), TEXT("text.secondary"));
  Style(RightCaption, TEXT("type.caption"), TEXT("text.secondary"));
  Style(LeftVerdict, TEXT("type.caption"), TEXT("turn.flash.yellow"));
  Style(RightVerdict, TEXT("type.caption"), TEXT("turn.flash.yellow"));
  Style(StripText, TEXT("type.button"), TEXT("text.primary"));
  if (StripText) {  // VC C4 (ВР-VC-23): the strip text stops before the buttons with «…» (pseudo-locale +30 %)
    StripText->SetTextOverflowPolicy(ETextOverflowPolicy::Ellipsis);
    StripText->SetClipping(EWidgetClipping::ClipToBounds);
  }
  for (UTextBlock* T : {OutcomeText.Get(), HeadlineText.Get(), ReasonText.Get(), TurnText.Get(), VersusText.Get(), LeftName.Get(),
                        RightName.Get()}) {
    if (T) T->SetJustification(ETextJustify::Center);
  }
  Icon(LeftHeart, TEXT("resource-hp-fallen"), UmGoHeartSu);
  Icon(RightHeart, TEXT("resource-hp-fallen"), UmGoHeartSu);
  // the frame is the whole canvas, clear: the modal and the strip are its parts
  if (Frame) Frame->SetBrush(FSlateNoResource());
  Refresh();
  return bFirst;
}

bool UUmScreenGameOver::HasAllParts(FString* OutMissing) const {
  FString Base;
  HasBaseParts(&Base);
  TArray<FString> Missing;
  if (!Base.IsEmpty()) Missing.Add(Base);
  auto Need = [&Missing](const UObject* P, const TCHAR* Name) {
    if (!P) Missing.Add(Name);
  };
  Need(ResultModal, TEXT("ResultModal"));
  Need(OutcomeText, TEXT("OutcomeText"));
  Need(HeadlineText, TEXT("HeadlineText"));
  Need(ReasonText, TEXT("ReasonText"));
  Need(TurnText, TEXT("TurnText"));
  Need(LeftPortrait, TEXT("LeftPortrait"));
  Need(RightPortrait, TEXT("RightPortrait"));
  Need(VersusText, TEXT("VersusText"));
  Need(LeftName, TEXT("LeftName"));
  Need(RightName, TEXT("RightName"));
  Need(LeftCaption, TEXT("LeftCaption"));
  Need(RightCaption, TEXT("RightCaption"));
  Need(LeftVerdict, TEXT("LeftVerdict"));
  Need(RightVerdict, TEXT("RightVerdict"));
  Need(LeftHeart, TEXT("LeftHeart"));
  Need(RightHeart, TEXT("RightHeart"));
  Need(ViewBoardButton, TEXT("ViewBoardButton"));
  Need(AgainButton, TEXT("AgainButton"));
  Need(LobbyButton, TEXT("LobbyButton"));
  Need(BoardStrip, TEXT("BoardStrip"));
  Need(StripText, TEXT("StripText"));
  Need(ResultsButton, TEXT("ResultsButton"));
  Need(StripLobbyButton, TEXT("StripLobbyButton"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmScreenGameOver::ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu) {
  SetCanvas(InCanvasSu, bInClassS, InPxPerSu);
  if (Frame) Frame->SetBrush(FSlateNoResource());
  RebuildDiscs();
  Refresh();
}

void UUmScreenGameOver::SetFieldSu(const FBox2D* InFieldSu) {
  bHasField = InFieldSu && InFieldSu->bIsValid;
  FieldSu = bHasField ? *InFieldSu : FBox2D(ForceInit);
}

void UUmScreenGameOver::ApplyModel(const FUmGameOverModel& InModel) {
  if (bHasModel && InModel == Model) return;
  bHasModel = true;
  Model = InModel;
  RebuildDiscs();
  Refresh();
}

void UUmScreenGameOver::RebuildDiscs() {
  if (!WidgetTree || !LeftPortrait || !RightPortrait) return;
  const FUmGameOverSide* Sides[2] = {&Model.Left, &Model.Right};
  bool bSame = DiscPx == PxPerSu;
  for (int32 I = 0; I < 2; ++I) bSame &= DiscKeys[I] == Sides[I]->HeroKey.ToString() && DiscLoser[I] == Sides[I]->bFallen;
  if (bSame) return;
  KeepAlive.Reset();
  PortraitLines.Reset();
  DiscPx = PxPerSu;
  for (int32 I = 0; I < 2; ++I) {
    DiscKeys[I] = Sides[I]->HeroKey.ToString();
    DiscLoser[I] = Sides[I]->bFallen;
    UBorder* Holder = I == 0 ? LeftPortrait.Get() : RightPortrait.Get();
    if (Sides[I]->HeroKey.IsNone()) {
      Holder->SetContent(MakeDisc(*WidgetTree, this, NAME_None, FString(), UmGameOver::DiscSu, PxPerSu, 0.0f, KeepAlive, nullptr, TEXT("result")));
      continue;
    }
    // ВР-VS5-SC34-04: the loser's whole disc at saturation 0 and opacity 0.6 (the CP-08 loser state), no red
    FUmPortraitDiscSpec Spec;
    Spec.Key = Sides[I]->HeroKey;
    Spec.Name = Sides[I]->HeroName;
    Spec.ShowSu = UmGameOver::DiscSu;
    Spec.PxPerSu = PxPerSu;
    Spec.State = Sides[I]->bFallen ? EUmPortraitState::Loser : EUmPortraitState::Avatar;
    FUmPortraitShown Shown;
    UWidget* Disc = UmPortrait::MakeDisc(*WidgetTree, this, Spec, Shown, KeepAlive);
    if (Sides[I]->bFallen && Disc) Disc->SetRenderOpacity(UmPortrait::LoserOpacity);
    Holder->SetContent(Disc);
    PortraitLines.Add(Shown.Line(TEXT("result"), I == 0 ? TEXT("own") : TEXT("opp")));
  }
}

FBox2D UUmScreenGameOver::ModalRectSu() const {
  const FVector2D Size = UmGameOver::ModalSize(bClassS, Model.bVsAi);
  const FVector2D Min = 0.5 * (CanvasSu - Size);
  return FBox2D(Min, Min + Size);
}

FBox2D UUmScreenGameOver::StripRectSu() const {
  const float M = GetSafeMarginSu();
  const FVector2D Min(0.5f * (CanvasSu.X - UmGameOver::StripWSu), CanvasSu.Y - M - UmGameOver::StripHSu);
  return FBox2D(Min, Min + FVector2D(UmGameOver::StripWSu, UmGameOver::StripHSu));
}

double UUmScreenGameOver::StripOverlapFieldPx2() const {
  return bHasField ? UmGameOver::OverlapPx2(StripRectSu(), FieldSu, PxPerSu) : 0.0;
}

void UUmScreenGameOver::Refresh() {
  using namespace UmGameOver;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const bool bDecided = Model.Outcome == EUmGameOverOutcome::Victory || Model.Outcome == EUmGameOverOutcome::Defeat;
  // ---- texts
  if (OutcomeText) {
    OutcomeText->SetText(UmGameOver::OutcomeText(Model.Outcome));
    // ВР-VS5-SC34-07: draw / unknown one step down (type.banner), text.primary; victory yellow, defeat state.error (>= 24 su)
    Style(OutcomeText, bDecided ? TEXT("type.display") : TEXT("type.banner"),
          Model.Outcome == EUmGameOverOutcome::Victory ? TEXT("turn.flash.yellow")
          : Model.Outcome == EUmGameOverOutcome::Defeat ? TEXT("state.error")
                                                        : TEXT("text.primary"));
  }
  if (HeadlineText) HeadlineText->SetText(UmGameOver::HeadlineText(Model));
  if (ReasonText) ReasonText->SetText(UmGameOver::ReasonText(Model));
  if (TurnText) TurnText->SetText(UmGameOver::TurnText(Model));
  if (VersusText) VersusText->SetText(S(TEXT("screens.loading.versus")));
  const FUmGameOverSide* Sides[2] = {&Model.Left, &Model.Right};
  UTextBlock* Names[2] = {LeftName.Get(), RightName.Get()};
  UTextBlock* Leads[2] = {LeftCaption.Get(), RightCaption.Get()};
  UTextBlock* Verdicts[2] = {LeftVerdict.Get(), RightVerdict.Get()};
  US08AnimatedIconWidget* Hearts[2] = {LeftHeart.Get(), RightHeart.Get()};
  for (int32 I = 0; I < 2; ++I) {
    if (Names[I]) Names[I]->SetText(FText::FromString(Sides[I]->HeroName));
    if (Leads[I]) Leads[I]->SetText(FText::FromString(UmGameOver::CaptionLead(*Sides[I])));
    if (Verdicts[I]) {
      Verdicts[I]->SetText(UmGameOver::CaptionVerdict(*Sides[I]));
      Style(Verdicts[I], TEXT("type.caption"), Sides[I]->bWinner ? TEXT("turn.flash.yellow") : TEXT("text.secondary"));
    }
  }
  // ---- the modal
  const FBox2D MR = ModalRectSu();
  const FVector2D MS = MR.GetSize();
  const float Ax = MR.Min.X + 0.5f * MS.X;
  const float Y0 = MR.Min.Y;
  Place(ResultModal, MR.Min, MS);
  const float InnerW = MS.X - 48.0f;
  Place(OutcomeText, FVector2D(MR.Min.X + 24.0f, Y0 + 32.0f), FVector2D(InnerW, bDecided ? 58.0f : 44.0f));
  Place(HeadlineText, FVector2D(MR.Min.X + 24.0f, Y0 + 96.0f), FVector2D(InnerW, 34.0f));
  Place(ReasonText, FVector2D(MR.Min.X + 24.0f, Y0 + 140.0f), FVector2D(InnerW, 20.0f));
  Place(TurnText, FVector2D(MR.Min.X + 24.0f, Y0 + 168.0f), FVector2D(InnerW, 18.0f));
  Vis(HeadlineText, !HeadlineText || !HeadlineText->GetText().IsEmpty());
  Vis(ReasonText, !ReasonText || !ReasonText->GetText().IsEmpty());
  Vis(TurnText, !TurnText || !TurnText->GetText().IsEmpty());
  const float Off = bClassS ? 160.0f : 180.0f;
  const float DiscY = Y0 + 210.0f;
  const float NameY = DiscY + DiscSu + (bClassS ? 8.0f : 12.0f);
  const float CapY = NameY + 30.0f + 4.0f;
  const float ColW = 2.0f * Off - 32.0f;  // a side column never reaches the other's
  for (int32 I = 0; I < 2; ++I) {
    const float Cx = Ax + (I == 0 ? -Off : Off);
    Place(I == 0 ? LeftPortrait.Get() : RightPortrait.Get(), FVector2D(Cx - 0.5f * DiscSu, DiscY), FVector2D(DiscSu));
    Place(Names[I], FVector2D(Cx - 0.5f * ColW, NameY), FVector2D(ColW, 30.0f));
    // the caption: lead (text.secondary) + verdict (yellow / secondary) + the fallen heart, centred under the disc
    const float LeadW = Leads[I] ? MeasureW(Leads[I]->GetText(), TEXT("type.caption")) * 1.04f + 4.0f : 0.0f;
    const float VerdW = Verdicts[I] ? MeasureW(Verdicts[I]->GetText(), TEXT("type.caption")) * 1.04f + 2.0f : 0.0f;
    const bool bHeart = Sides[I]->bFallen && !Sides[I]->bWinner;
    const float Total = LeadW + VerdW + (bHeart ? 6.0f + UmGoHeartSu : 0.0f);
    float X = Cx - 0.5f * Total;
    // the boxes get 16 su of slack (the DPI-scaled glyphs run wider than the 1.0 measure at 720p); the next part
    // starts at the measured width
    Place(Leads[I], FVector2D(X, CapY + 4.0f), FVector2D(LeadW + 16.0f, 18.0f));
    X += LeadW;
    Place(Verdicts[I], FVector2D(X, CapY + 4.0f), FVector2D(VerdW + 16.0f, 18.0f));
    X += VerdW + 6.0f;
    Place(Hearts[I], FVector2D(X, CapY), FVector2D(UmGoHeartSu));
    Vis(Hearts[I], bHeart);
  }
  Place(VersusText, FVector2D(Ax - 0.5f * (2.0f * Off - DiscSu), DiscY + 0.5f * DiscSu - 15.0f), FVector2D(2.0f * Off - DiscSu, 30.0f));
  // ---- the button row (ВР-VS5-SC34-05, ВР-VS5-SC37-03): chips V / Enter, gaps 16 -> 8 -> no chips when it does not fit
  const FText KeyV = FText::FromString(TEXT("V"));
  const FText KeyEnter = FText::FromString(TEXT("Enter"));
  const FText LView = S(TEXT("screens.result.view.board"));
  const FText LAgain = S(TEXT("screens.result.again"));
  const FText LAgainBusy = S(TEXT("screens.result.again.busy"));
  const FText LLobby = S(TEXT("screens.result.lobby"));
  bool bChips = Model.bKeyChips;
  float Gap = 16.0f;
  float WView = 0.0f, WAgain = 0.0f, WLobby = 0.0f, Row = 0.0f;
  for (int32 Pass = 0; Pass < 3; ++Pass) {
    WView = FMath::Max(168.0f, UmGoLabelW(LView) + (bChips ? UmGoChipW(KeyV) : 0.0f) + 48.0f);
    WAgain = Model.bVsAi ? FMath::Max(168.0f, FMath::Max(UmGoLabelW(LAgain), UmGoLabelW(LAgainBusy) + 24.0f + 8.0f) + 48.0f) : 0.0f;
    WLobby = FMath::Max(168.0f, UmGoLabelW(LLobby) + (bChips ? UmGoChipW(KeyEnter) : 0.0f) + 48.0f);
    Row = WView + WLobby + Gap + (Model.bVsAi ? WAgain + Gap : 0.0f);
    if (Row <= MS.X - 48.0f) break;
    if (Gap > 8.0f) {
      Gap = 8.0f;
    } else {
      bChips = false;
    }
  }
  if (Row > MS.X - 48.0f) {
    // VS-7 Frames: no chips and 8 su gaps still too wide (pseudo-locale +30 %) - the buttons share the modal's inner width;
    // UUmButton steps its label down to fit (FitLabel)
    const float Gaps = Gap * (Model.bVsAi ? 2.0f : 1.0f);
    const float F = FMath::Max(0.1f, (MS.X - 48.0f - Gaps) / FMath::Max(1.0f, Row - Gaps));
    WView *= F;
    WAgain *= F;
    WLobby *= F;
    Row = MS.X - 48.0f;
  }
  const float By = Y0 + (bClassS ? 480.0f : 500.0f);
  float Bx = Ax - 0.5f * Row;
  auto Btn = [](UUmButton* B, const FText& Label, EUmButtonVariant V, const FText& Key, bool bBusy, bool bEnabled, float H) {
    if (!B) return;
    FUmButtonModel M;
    M.Variant = V;
    M.Label = Label;
    M.KeyHint = Key;
    M.HeightSu = H;
    M.MinWidthSu = 168.0f;
    M.bBusy = bBusy;
    M.bEnabled = bEnabled && !bBusy;
    if (bBusy) M.Reason = FS09Reason::Make(TEXT("why.syncing"));
    B->ApplyModel(M);
  };
  // ВР-VS5-SC37-04: «Создаём партию…» keeps the normal body with the spinner 24 su (not the generic «Отправлено…» busy);
  // the other buttons stay as they are (their presses wait while the chain runs)
  Btn(ViewBoardButton, LView, EUmButtonVariant::Normal, bChips ? KeyV : FText::GetEmpty(), false, !Model.bLobbyBusy, 48.0f);
  Btn(AgainButton, Model.bAgainBusy ? LAgainBusy : LAgain, EUmButtonVariant::Normal, FText::GetEmpty(), false, !Model.bLobbyBusy, 48.0f);
  if (AgainButton && Model.bAgainBusy) {
    FUmButtonModel AM = AgainButton->GetModel();
    AM.IconName = FName(TEXT("loader-spinner"));
    AgainButton->ApplyModel(AM);
  }
  Btn(LobbyButton, LLobby, EUmButtonVariant::Primary, bChips ? KeyEnter : FText::GetEmpty(), Model.bLobbyBusy, true, 48.0f);
  Place(ViewBoardButton, FVector2D(Bx, By), FVector2D(WView, 48.0f));
  Bx += WView + Gap;
  if (Model.bVsAi) {
    Place(AgainButton, FVector2D(Bx, By), FVector2D(WAgain, 48.0f));
    Bx += WAgain + Gap;
  }
  Place(LobbyButton, FVector2D(Bx, By), FVector2D(WLobby, 48.0f));
  // ---- the board strip (ВР-VS5-SC36-01): padding 8, StripText left, the two 40 su buttons right, 8 apart
  const FBox2D SR = StripRectSu();
  Place(BoardStrip, SR.Min, SR.GetSize());
  if (StripText) StripText->SetText(UmGameOver::StripText(Model));
  const FText LResults = S(TEXT("screens.result.view.results"));
  const float TextW = StripText ? MeasureW(StripText->GetText(), TEXT("type.button")) + 4.0f : 0.0f;
  bStripChips = Model.bKeyChips;
  float WRes = 0.0f, WSLobby = 0.0f;
  for (int32 Pass = 0; Pass < 2; ++Pass) {
    WRes = FMath::Max(120.0f, UmGoLabelW(LResults) + (bStripChips ? UmGoChipW(KeyV) : 0.0f) + 32.0f);
    WSLobby = FMath::Max(120.0f, UmGoLabelW(LLobby) + (bStripChips ? UmGoChipW(KeyEnter) : 0.0f) + 32.0f);
    if (8.0f + TextW + 8.0f + WRes + 8.0f + WSLobby + 8.0f <= StripWSu || !bStripChips) break;
    bStripChips = false;  // the chips go first, never the type
  }
  // VC C4 (ВР-VC-23): never under «К ИТОГАМ» - the text gets what the two buttons leave, the rest is «…»
  const float TextRoom = FMath::Max(40.0f, StripWSu - 8.0f - 8.0f - WRes - 8.0f - WSLobby - 8.0f);
  Place(StripText, FVector2D(SR.Min.X + 8.0f, SR.Min.Y + 0.5f * (StripHSu - 26.0f)), FVector2D(FMath::Min(TextW, TextRoom), 26.0f));
  Btn(ResultsButton, LResults, EUmButtonVariant::Normal, bStripChips ? KeyV : FText::GetEmpty(), false, !Model.bLobbyBusy, 40.0f);
  Btn(StripLobbyButton, LLobby, EUmButtonVariant::Primary, bStripChips ? KeyEnter : FText::GetEmpty(), Model.bLobbyBusy, true, 40.0f);
  Place(StripLobbyButton, FVector2D(SR.Max.X - 8.0f - WSLobby, SR.Min.Y + 8.0f), FVector2D(WSLobby, 40.0f));
  Place(ResultsButton, FVector2D(SR.Max.X - 8.0f - WSLobby - 8.0f - WRes, SR.Min.Y + 8.0f), FVector2D(WRes, 40.0f));
  SetScreenState(FName(StateName(Model)));
  SetViewAlphas(ResultsA, StripA);
  (void)Theme;
}

void UUmScreenGameOver::SetViewAlphas(float ResultsAlpha, float StripAlpha) {
  ResultsA = FMath::Clamp(ResultsAlpha, 0.0f, 1.0f);
  StripA = FMath::Clamp(StripAlpha, 0.0f, 1.0f);
  const bool bResults = ResultsA > 0.0f;
  const bool bStrip = StripA > 0.0f;
  // the results take clicks only while they are (becoming) the results; the strip only on the board (FS09ResultView)
  const ESlateVisibility ResultsVis = !bResults ? ESlateVisibility::Collapsed
                                      : !Model.bBoard ? ESlateVisibility::SelfHitTestInvisible
                                                      : ESlateVisibility::HitTestInvisible;
  for (UWidget* W : {static_cast<UWidget*>(Veil.Get()), static_cast<UWidget*>(ResultModal.Get())}) {
    if (!W) continue;
    W->SetRenderOpacity(ResultsA);
    if (W == Veil.Get()) {
      W->SetVisibility(!bResults ? ESlateVisibility::Collapsed : Model.bBoard ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Visible);
    } else {
      W->SetVisibility(bResults ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
    }
  }
  for (UWidget* W : {static_cast<UWidget*>(OutcomeText.Get()), static_cast<UWidget*>(HeadlineText.Get()), static_cast<UWidget*>(ReasonText.Get()),
                     static_cast<UWidget*>(TurnText.Get()), static_cast<UWidget*>(LeftPortrait.Get()), static_cast<UWidget*>(RightPortrait.Get()),
                     static_cast<UWidget*>(VersusText.Get()), static_cast<UWidget*>(LeftName.Get()), static_cast<UWidget*>(RightName.Get()),
                     static_cast<UWidget*>(LeftCaption.Get()), static_cast<UWidget*>(RightCaption.Get()),
                     static_cast<UWidget*>(LeftVerdict.Get()), static_cast<UWidget*>(RightVerdict.Get()), static_cast<UWidget*>(LeftHeart.Get()),
                     static_cast<UWidget*>(RightHeart.Get())}) {
    if (W) W->SetRenderOpacity(ResultsA);
  }
  for (UUmButton* B : {ViewBoardButton.Get(), AgainButton.Get(), LobbyButton.Get()}) {
    if (!B) continue;
    B->SetRenderOpacity(ResultsA);
    const bool bOn = bResults && (B != AgainButton.Get() || Model.bVsAi);
    B->SetVisibility(!bOn ? ESlateVisibility::Collapsed : ResultsVis == ESlateVisibility::SelfHitTestInvisible ? ESlateVisibility::Visible
                                                                                                                : ESlateVisibility::HitTestInvisible);
  }
  for (UWidget* W : {static_cast<UWidget*>(BoardStrip.Get()), static_cast<UWidget*>(StripText.Get())}) {
    if (!W) continue;
    W->SetRenderOpacity(StripA);
    W->SetVisibility(bStrip ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  }
  for (UUmButton* B : {ResultsButton.Get(), StripLobbyButton.Get()}) {
    if (!B) continue;
    B->SetRenderOpacity(StripA);
    B->SetVisibility(!bStrip ? ESlateVisibility::Collapsed : Model.bBoard ? ESlateVisibility::Visible : ESlateVisibility::HitTestInvisible);
  }
  // the hearts and the verdicts follow their own rules inside the results
  if (bResults) {
    Vis(LeftHeart, Model.Left.bFallen && !Model.Left.bWinner);
    Vis(RightHeart, Model.Right.bFallen && !Model.Right.bWinner);
    Vis(HeadlineText, HeadlineText && !HeadlineText->GetText().IsEmpty());
    Vis(ReasonText, ReasonText && !ReasonText->GetText().IsEmpty());
    Vis(TurnText, TurnText && !TurnText->GetText().IsEmpty());
  }
  // the screen itself: shown while either part is; on the board the clicks pass to the scene but the strip
  SetAlphaDirect(FMath::Max(ResultsA, StripA), Model.bBoard ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::Visible);
}

FString UUmScreenGameOver::GetOutcomeText() const { return OutcomeText ? OutcomeText->GetText().ToString() : FString(); }
FString UUmScreenGameOver::GetHeadlineText() const { return HeadlineText ? HeadlineText->GetText().ToString() : FString(); }
FString UUmScreenGameOver::GetReasonText() const { return ReasonText ? ReasonText->GetText().ToString() : FString(); }
FString UUmScreenGameOver::GetTurnText() const { return TurnText ? TurnText->GetText().ToString() : FString(); }
FString UUmScreenGameOver::GetStripText() const { return StripText ? StripText->GetText().ToString() : FString(); }
FString UUmScreenGameOver::GetCaption(bool bLeft) const {
  const UTextBlock* L = bLeft ? LeftCaption.Get() : RightCaption.Get();
  const UTextBlock* V = bLeft ? LeftVerdict.Get() : RightVerdict.Get();
  return (L ? L->GetText().ToString() : FString()) + (V ? V->GetText().ToString() : FString());
}
bool UUmScreenGameOver::IsShownPart(const UWidget* W) const { return W && W->GetVisibility() != ESlateVisibility::Collapsed; }

int32 UUmScreenGameOver::PrimaryCount() const {
  int32 N = 0;
  for (const UUmButton* B : {ViewBoardButton.Get(), AgainButton.Get(), LobbyButton.Get(), ResultsButton.Get(), StripLobbyButton.Get()}) {
    if (IsShownPart(B) && B->GetModel().Variant == EUmButtonVariant::Primary) ++N;
  }
  return N;
}

void UUmScreenGameOver::CollectShotLines(TArray<FString>& Out) const {
  if (!IsShown() || UiId.IsEmpty()) return;
  const bool bVisible = UmGameHudSlots::ShownByProperty(this) || GetVisibility() != ESlateVisibility::Collapsed;
  // the bbox of what shows: the strip on the board, the modal otherwise (04 §4.5)
  const FBox2D R = Model.bBoard ? StripRectSu() : ModalRectSu();
  const FS08ScreenRect Rect(R.Min.X * PxPerSu, R.Min.Y * PxPerSu, R.Max.X * PxPerSu, R.Max.Y * PxPerSu);
  Out.Add(S08ArtHud::FormatWidgetLineEx(UiId, TEXT("umg"), *ShotStateName(), FString(), Rect, bVisible && !Rect.IsEmpty(),
                                        bVisible, SourceName(),
                                        FString::Printf(TEXT("modal=%d class=%s alpha=%.2f%s"), Model.bBoard ? 0 : 1, bClassS ? TEXT("S") : TEXT("L"),
                                                        GetAlpha(), *ShotExtra())));
}

FString UUmScreenGameOver::ShotExtra() const {
  return FString::Printf(TEXT(" mode=%s chips=%d primary=%d overlapField=%.0f"), Model.bVsAi ? TEXT("vs_ai") : TEXT("1v1"),
                         Model.bKeyChips ? 1 : 0, PrimaryCount(), Model.bBoard ? StripOverlapFieldPx2() : 0.0);
}

void UUmScreenGameOver::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput) {
  Arbiter = InArbiter;
  Input = MoveTemp(InInput);
  TWeakObjectPtr<UUmScreenGameOver> WeakThis(this);
  for (const TPair<UUmButton*, const TCHAR*>& B :
       {TPair<UUmButton*, const TCHAR*>(ViewBoardButton.Get(), TEXT("screens.result.view.board")),
        TPair<UUmButton*, const TCHAR*>(AgainButton.Get(), TEXT("screens.result.again")),
        TPair<UUmButton*, const TCHAR*>(LobbyButton.Get(), TEXT("screens.result.lobby")),
        TPair<UUmButton*, const TCHAR*>(ResultsButton.Get(), TEXT("screens.result.view.results")),
        TPair<UUmButton*, const TCHAR*>(StripLobbyButton.Get(), TEXT("screens.result.board.lobby"))}) {
    if (!B.Key) continue;
    const FName Name(B.Value);
    B.Key->SetPress(Name, Arbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, Name](const FS09HudPressOutcome& O) {
      if (UUmScreenGameOver* Self = WeakThis.Get()) Self->OnPressOutcome(Name, O);
    }));
  }
}

void UUmScreenGameOver::OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome) {
  if (Outcome.Result != ES09HudPressResult::Act || Model.bAgainBusy) return;
  if (Id == FName(TEXT("screens.result.view.board")) || Id == FName(TEXT("screens.result.view.results"))) {
    if (Input.OnSound) Input.OnSound(FName(TEXT("UI-PANEL-CLOSE")));  // 08-screen-audio-hooks SC-36
    if (Input.OnViewBoard) Input.OnViewBoard();
  } else if (Id == FName(TEXT("screens.result.again"))) {
    if (!Model.bVsAi || Model.bLobbyBusy) return;
    if (Input.OnSound) Input.OnSound(FName(TEXT("UI-CONFIRM")));  // SC-37
    if (Input.OnAgain) Input.OnAgain();
  } else if (!Model.bLobbyBusy) {
    if (Input.OnSound) Input.OnSound(FName(TEXT("UI-BTN-CLICK")));
    if (Input.OnLobby) Input.OnLobby();
  }
}

void UUmScreenGameOver::SimulatePress(FName Id) {
  if (!Arbiter.IsValid()) Arbiter = MakeShared<FS09HudPressArbiter>();
  Arbiter->Press(Id, Arbiter->Now());
  OnPressOutcome(Id, FS09HudPressArbiter::Decide(Arbiter->Release(Id, Arbiter->Now()), FS09Reason()));
}

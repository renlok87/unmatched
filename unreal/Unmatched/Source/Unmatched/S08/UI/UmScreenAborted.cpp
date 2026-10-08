// VS-7 S5 SC-38: the interrupted match - see UmScreenAborted.h.
#include "UmScreenAborted.h"

#include "../S08AnimatedIconWidget.h"
#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHeroCard.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/NamedSlot.h"
#include "Components/TextBlock.h"

using namespace UmRoomUi;

const TCHAR* const UUmScreenAborted::WidgetBlueprintPath = TEXT("/Game/S08/UI/Screens/WBP_UI_SCR_ABORTED");

UClass* UUmScreenAborted::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmScreenAborted::StaticClass(), WidgetBlueprintPath); }

namespace UmAborted {
FText WhoText(const FUmAbortedModel& M) {
  if (M.Leaver.IsEmpty()) return S(TEXT("screens.aborted.who.unknown"));
  FFormatNamedArguments A;
  A.Add(TEXT("player"), FText::FromString(M.Leaver));
  return UmText::Format(EUmTable::Screens, TEXT("screens.aborted.who"), A);
}

FText TurnText(const FUmAbortedModel& M) {
  if (M.Turn <= 0) return FText::GetEmpty();
  FFormatNamedArguments A;
  A.Add(TEXT("n"), FText::AsNumber(M.Turn));
  return UmText::Format(EUmTable::Screens, TEXT("screens.aborted.turn"), A);
}
}  // namespace UmAborted

namespace {
template <typename T>
T* UmAbFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}
}  // namespace

bool UUmScreenAborted::AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  UCanvasPanel* ContentW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Content")));
  ContentW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(ContentW, Parent)) return Fail(TEXT("Content"));
  if (!Attach(Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("Icon"))), ContentW)) {
    return Fail(TEXT("Icon"));
  }
  for (const TCHAR* Name : {TEXT("TitleText"), TEXT("WhoText"), TEXT("TurnText")}) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (!Attach(T, ContentW)) return Fail(Name);
  }
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  if (!Attach(Tree.ConstructWidget<UUmButton>(ButtonClass, FName(TEXT("LobbyButton"))), ContentW)) return Fail(TEXT("LobbyButton"));
  return true;
}

bool UUmScreenAborted::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  if (!UUmScreenBase::BuildDefaultTree(Tree, Attach, OutError)) return false;
  UNamedSlot* BodyW = Cast<UNamedSlot>(Tree.FindWidget(FName(TEXT("Body"))));
  if (!BodyW) {
    if (OutError) *OutError = TEXT("no Body");
    return false;
  }
  return AttachContent(Tree, BodyW, Attach, OutError);
}

void UUmScreenAborted::BuildContent() {
  if (!WidgetTree || !Body || Body->GetContent()) return;
  FString Problem;
  auto AddTo = [](UWidget* Child, UPanelWidget* Parent) { return Parent && Parent->AddChild(Child) != nullptr; };
  if (!AttachContent(*WidgetTree, Body, AddTo, &Problem)) UE_LOG(LogTemp, Error, TEXT("UMHUD aborted content: %s"), *Problem);
}

void UUmScreenAborted::BindParts() {
  Content = UmAbFind<UCanvasPanel>(WidgetTree, TEXT("Content"));
  Icon = UmAbFind<US08AnimatedIconWidget>(WidgetTree, TEXT("Icon"));
  TitleText = UmAbFind<UTextBlock>(WidgetTree, TEXT("TitleText"));
  WhoText = UmAbFind<UTextBlock>(WidgetTree, TEXT("WhoText"));
  TurnText = UmAbFind<UTextBlock>(WidgetTree, TEXT("TurnText"));
  LobbyButton = UmAbFind<UUmButton>(WidgetTree, TEXT("LobbyButton"));
}

bool UUmScreenAborted::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  SetUiId(TEXT("UI-SCR-ABORTED"));
  SetScreenState(FName(TEXT("shown")));
  BindParts();
  Style(TitleText, TEXT("type.title"), TEXT("text.primary"));
  Style(WhoText, TEXT("type.body"), TEXT("text.primary"));
  Style(TurnText, TEXT("type.caption"), TEXT("text.secondary"));
  for (UTextBlock* T : {TitleText.Get(), WhoText.Get(), TurnText.Get()}) {
    if (T) T->SetJustification(ETextJustify::Center);
  }
  UmRoomUi::Icon(Icon, TEXT("resource-connection-lost"), 48.0f);
  SetFrameSize(FVector2D(UmAborted::ModalWSu, UmAborted::ModalHSu));
  Refresh();
  return bFirst;
}

bool UUmScreenAborted::HasAllParts(FString* OutMissing) const {
  FString Base;
  HasBaseParts(&Base);
  TArray<FString> Missing;
  if (!Base.IsEmpty()) Missing.Add(Base);
  if (!Icon) Missing.Add(TEXT("Icon"));
  if (!TitleText) Missing.Add(TEXT("TitleText"));
  if (!WhoText) Missing.Add(TEXT("WhoText"));
  if (!TurnText) Missing.Add(TEXT("TurnText"));
  if (!LobbyButton) Missing.Add(TEXT("LobbyButton"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmScreenAborted::ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu) {
  SetCanvas(InCanvasSu, bInClassS, InPxPerSu);
  Refresh();
}

void UUmScreenAborted::ApplyModel(const FUmAbortedModel& InModel) {
  if (bHasModel && InModel == Model) return;
  bHasModel = true;
  Model = InModel;
  Refresh();
}

void UUmScreenAborted::Refresh() {
  if (TitleText) TitleText->SetText(S(TEXT("screens.aborted.title")));
  if (WhoText) WhoText->SetText(UmAborted::WhoText(Model));
  if (TurnText) TurnText->SetText(UmAborted::TurnText(Model));
  const bool bTurn = Model.Turn > 0;
  const FText Label = S(TEXT("screens.aborted.lobby"));
  const FText Key = Model.bKeyChips ? FText::FromString(TEXT("Enter")) : FText::GetEmpty();
  const float ChipW = Key.IsEmpty() ? 0.0f : 8.0f + FMath::Max(20.0f, MeasureW(Key, TEXT("type.tag")) + 8.0f);
  const float BtnW = FMath::Max(168.0f, MeasureW(Label.ToUpper(), TEXT("type.button")) + ChipW + 48.0f);
  // ВР-VS5-SC38-02: icon 48; 16; title 34; 12; who 20; 8; turn 18; 24; button 48 - centred in the 360 su modal
  const float W = UmAborted::ModalWSu;
  const float ColH = 48.0f + 16.0f + 34.0f + 12.0f + 20.0f + (bTurn ? 8.0f + 18.0f : 0.0f) + 24.0f + 48.0f;
  float Y = 0.5f * (UmAborted::ModalHSu - ColH);
  Place(Icon, FVector2D(0.5f * (W - 48.0f), Y), FVector2D(48.0f));
  Y += 48.0f + 16.0f;
  Place(TitleText, FVector2D(24.0f, Y), FVector2D(W - 48.0f, 34.0f));
  Y += 34.0f + 12.0f;
  Place(WhoText, FVector2D(24.0f, Y), FVector2D(W - 48.0f, 20.0f));
  Y += 20.0f;
  Vis(TurnText, bTurn);
  if (bTurn) {
    Y += 8.0f;
    Place(TurnText, FVector2D(24.0f, Y), FVector2D(W - 48.0f, 18.0f));
    Y += 18.0f;
  }
  Y += 24.0f;
  if (LobbyButton) {
    FUmButtonModel M;
    M.Variant = EUmButtonVariant::Primary;  // the one primary of the window
    M.Label = Label;
    M.KeyHint = Key;
    M.HeightSu = 48.0f;
    M.MinWidthSu = 168.0f;
    M.bBusy = Model.bLobbyBusy;
    M.bEnabled = !Model.bLobbyBusy;
    if (Model.bLobbyBusy) M.Reason = FS09Reason::Make(TEXT("why.syncing"));
    LobbyButton->ApplyModel(M);
  }
  Place(LobbyButton, FVector2D(0.5f * (W - BtnW), Y), FVector2D(BtnW, 48.0f));
  SetScreenState(FName(TEXT("shown")));
}

FString UUmScreenAborted::GetTitleText() const { return TitleText ? TitleText->GetText().ToString() : FString(); }
FString UUmScreenAborted::GetWhoText() const { return WhoText ? WhoText->GetText().ToString() : FString(); }
FString UUmScreenAborted::GetTurnText() const { return TurnText ? TurnText->GetText().ToString() : FString(); }
bool UUmScreenAborted::IsLobbyPrimary() const {
  return LobbyButton && LobbyButton->GetVisibility() != ESlateVisibility::Collapsed && LobbyButton->GetModel().Variant == EUmButtonVariant::Primary;
}

FString UUmScreenAborted::ShotExtra() const {
  return FString::Printf(TEXT(" who=%s turn=%d primary=%s"), Model.Leaver.IsEmpty() ? TEXT("unknown") : TEXT("named"), Model.Turn,
                         IsLobbyPrimary() ? TEXT("lobby") : TEXT("none"));
}

void UUmScreenAborted::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput) {
  Arbiter = InArbiter;
  Input = MoveTemp(InInput);
  if (!LobbyButton) return;
  TWeakObjectPtr<UUmScreenAborted> WeakThis(this);
  const FName Name(TEXT("screens.aborted.lobby"));
  LobbyButton->SetPress(Name, Arbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, Name](const FS09HudPressOutcome& O) {
    if (UUmScreenAborted* Self = WeakThis.Get()) Self->OnPressOutcome(Name, O);
  }));
}

void UUmScreenAborted::OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome) {
  if (Outcome.Result != ES09HudPressResult::Act || Model.bLobbyBusy) return;
  if (Input.OnSound) Input.OnSound(FName(TEXT("UI-BTN-CLICK")));
  if (Input.OnLobby) Input.OnLobby();
}

void UUmScreenAborted::SimulatePress(FName Id) {
  if (!Arbiter.IsValid()) Arbiter = MakeShared<FS09HudPressArbiter>();
  Arbiter->Press(Id, Arbiter->Now());
  OnPressOutcome(Id, FS09HudPressArbiter::Decide(Arbiter->Release(Id, Arbiter->Now()), FS09Reason()));
}

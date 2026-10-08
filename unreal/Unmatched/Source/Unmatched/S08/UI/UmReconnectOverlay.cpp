// VS-7 S5 SC-31...SC-33: the RECONNECT overlay - see UmReconnectOverlay.h.
#include "UmReconnectOverlay.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08IconMotion.h"
#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHeroCard.h"
#include "UmHudTheme.h"
#include "UmSpinner.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/Image.h"
#include "Components/NamedSlot.h"
#include "Components/TextBlock.h"
#include "HAL/PlatformTime.h"

using namespace UmRoomUi;

const TCHAR* const UUmReconnectOverlay::WidgetBlueprintPath = TEXT("/Game/S08/UI/Screens/WBP_UI_SCR_RECONNECT");

UClass* UUmReconnectOverlay::WidgetClass() {
  return UmGameHudSlots::WbpOrNative(UUmReconnectOverlay::StaticClass(), WidgetBlueprintPath);
}

namespace UmReconnect {
const TCHAR* StateName(EUmReconnectState S) {
  switch (S) {
    case EUmReconnectState::Auto: return TEXT("auto");
    case EUmReconnectState::Manual: return TEXT("manual");
    case EUmReconnectState::Restoring: return TEXT("restoring");
    case EUmReconnectState::Expired: return TEXT("expired");
    default: return TEXT("hidden");
  }
}

int32 AttemptAt(double LostForMs) {
  const int32 N = 1 + static_cast<int32>(FMath::Max(0.0, LostForMs) / AttemptMs);
  return FMath::Clamp(N, 1, MaxAttempts);
}

EUmReconnectState Decide(const FUmReconnectInput& In) {
  if (In.bExpiredInMatch) return EUmReconnectState::Expired;
  if (!In.bStarted) return EUmReconnectState::Hidden;
  if (In.bLost) {
    if (In.bAcked) return EUmReconnectState::Restoring;
    return In.LostForMs >= AttemptMs * MaxAttempts ? EUmReconnectState::Manual : EUmReconnectState::Auto;
  }
  if (In.bAwaitingRecovery && In.RecoveryForMs >= RestoreDelayMs) return EUmReconnectState::Restoring;
  return EUmReconnectState::Hidden;
}

float CardHeightSu(EUmReconnectState S, bool bRunningTwoLines) {
  // ВР-VS5-SC31-02: padding 24, icon 48, 16, title; the lines a state shows with their gaps; 24, buttons 48, 24
  float H = PadSu + IconSu + 16.0f + TitleSu;
  const float Run = bRunningTwoLines ? 2.0f * LineSu : LineSu;
  switch (S) {
    case EUmReconnectState::Auto: H += 12.0f + LineSu + 8.0f + LineSu + 12.0f + Run + 24.0f + ButtonHSu; break;
    case EUmReconnectState::Manual: H += 12.0f + LineSu + 12.0f + Run + 24.0f + ButtonHSu; break;
    case EUmReconnectState::Expired: H += 24.0f + ButtonHSu; break;
    default: break;  // restoring: the title closes the card
  }
  return H + PadSu;
}

float ExitAlpha(double TMs, bool bReduced) {
  const double Len = bReduced ? 100.0 : ExitMs;
  return 1.0f - static_cast<float>(FMath::Clamp(TMs / Len, 0.0, 1.0));
}
}  // namespace UmReconnect

namespace {
template <typename T>
T* UmRcFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

const TCHAR* const UmRcTexts[] = {TEXT("Title"), TEXT("Attempt"), TEXT("Missed"), TEXT("Running")};
const TCHAR* const UmRcButtons[] = {TEXT("Leave"), TEXT("Retry"), TEXT("ToLogin")};

FText UmRcUpper(const TCHAR* Key) { return S(Key).ToUpper(); }
}  // namespace

bool UUmReconnectOverlay::AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError) {
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
  if (!Attach(Tree.ConstructWidget<UUmSpinner>(UUmSpinner::WidgetClass(), FName(TEXT("Spinner"))), ContentW)) return Fail(TEXT("Spinner"));
  for (const TCHAR* Name : UmRcTexts) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (!Attach(T, ContentW)) return Fail(Name);
  }
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  for (const TCHAR* Name : UmRcButtons) {
    if (!Attach(Tree.ConstructWidget<UUmButton>(ButtonClass, FName(Name)), ContentW)) return Fail(Name);
  }
  return true;
}

bool UUmReconnectOverlay::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  if (!UUmScreenBase::BuildDefaultTree(Tree, Attach, OutError)) return false;
  UNamedSlot* BodyW = Cast<UNamedSlot>(Tree.FindWidget(FName(TEXT("Body"))));
  if (!BodyW) {
    if (OutError) *OutError = TEXT("no Body");
    return false;
  }
  return AttachContent(Tree, BodyW, Attach, OutError);
}

void UUmReconnectOverlay::BuildContent() {
  if (!WidgetTree || !Body || Body->GetContent()) return;
  FString Problem;
  auto AddTo = [](UWidget* Child, UPanelWidget* Parent) { return Parent && Parent->AddChild(Child) != nullptr; };
  if (!AttachContent(*WidgetTree, Body, AddTo, &Problem)) UE_LOG(LogTemp, Error, TEXT("UMHUD reconnect content: %s"), *Problem);
}

void UUmReconnectOverlay::BindParts() {
  Content = UmRcFind<UCanvasPanel>(WidgetTree, TEXT("Content"));
  Icon = UmRcFind<US08AnimatedIconWidget>(WidgetTree, TEXT("Icon"));
  Spinner = UmRcFind<UUmSpinner>(WidgetTree, TEXT("Spinner"));
  Title = UmRcFind<UTextBlock>(WidgetTree, TEXT("Title"));
  Attempt = UmRcFind<UTextBlock>(WidgetTree, TEXT("Attempt"));
  Missed = UmRcFind<UTextBlock>(WidgetTree, TEXT("Missed"));
  Running = UmRcFind<UTextBlock>(WidgetTree, TEXT("Running"));
  Leave = UmRcFind<UUmButton>(WidgetTree, TEXT("Leave"));
  Retry = UmRcFind<UUmButton>(WidgetTree, TEXT("Retry"));
  ToLogin = UmRcFind<UUmButton>(WidgetTree, TEXT("ToLogin"));
}

bool UUmReconnectOverlay::Initialize() {
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  SetUiId(TEXT("UI-SCR-RECONNECT"));
  SetScreenState(FName(TEXT("auto")));
  BindParts();
  // ВР-VS5-SC31-03: the veil at 0.8 over the scene (its -30 % saturation is CUE-017's)
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  if (Veil) {
    FLinearColor V = Theme.Color(TEXT("card.navy"));
    V.A = 0.8f;
    Veil->SetColorAndOpacity(V);
  }
  Style(Title, TEXT("type.title"), TEXT("text.primary"));
  Style(Attempt, TEXT("type.body"), TEXT("text.primary"));
  Style(Missed, TEXT("type.body"), TEXT("text.secondary"));
  Style(Running, TEXT("type.body"), TEXT("text.secondary"));
  for (UTextBlock* T : {Title.Get(), Attempt.Get(), Missed.Get(), Running.Get()}) {
    if (T) T->SetJustification(ETextJustify::Center);
  }
  if (Spinner) Spinner->SetSizeSu(UmReconnect::SpinnerSu);
  Refresh();
  return bFirst;
}

bool UUmReconnectOverlay::HasAllParts(FString* OutMissing) const {
  FString Base;
  HasBaseParts(&Base);
  TArray<FString> Missing;
  if (!Base.IsEmpty()) Missing.Add(Base);
  auto Need = [&Missing](const UObject* P, const TCHAR* Name) {
    if (!P) Missing.Add(Name);
  };
  Need(Icon, TEXT("Icon"));
  Need(Spinner, TEXT("Spinner"));
  Need(Title, TEXT("Title"));
  Need(Attempt, TEXT("Attempt"));
  Need(Missed, TEXT("Missed"));
  Need(Running, TEXT("Running"));
  Need(Retry, TEXT("Retry"));
  Need(Leave, TEXT("Leave"));
  Need(ToLogin, TEXT("ToLogin"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmReconnectOverlay::ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu) {
  SetCanvas(InCanvasSu, bInClassS, InPxPerSu);
  Refresh();
}

void UUmReconnectOverlay::ApplyModel(const FUmReconnectModel& InModel) {
  if (bHasModel && InModel == Model) return;
  bHasModel = true;
  Model = InModel;
  Refresh();
}

void UUmReconnectOverlay::Refresh() {
  using namespace UmReconnect;
  const EUmReconnectState St = Model.State == EUmReconnectState::Hidden ? EUmReconnectState::Auto : Model.State;
  const bool bAuto = St == EUmReconnectState::Auto;
  const bool bManual = St == EUmReconnectState::Manual;
  const bool bExpired = St == EUmReconnectState::Expired;
  const bool bRestoring = St == EUmReconnectState::Restoring;
  const float InnerW = CardWSu - 2.0f * PadSu;
  // texts
  if (Title) {
    Title->SetText(bExpired ? S(TEXT("screens.reconnect.session.expired"))
                   : bRestoring ? S(TEXT("screens.reconnect.restoring"))
                                : S(TEXT("screens.reconnect.title")));
  }
  {
    FFormatNamedArguments A;
    A.Add(TEXT("n"), FText::AsNumber(Model.Attempt));
    A.Add(TEXT("max"), FText::AsNumber(Model.MaxAttempts));
    if (Attempt) Attempt->SetText(UmText::Format(EUmTable::Screens, TEXT("screens.reconnect.attempt"), A));
    FFormatNamedArguments M;
    M.Add(TEXT("n"), FText::AsNumber(Model.Missed));
    if (Missed) Missed->SetText(UmText::Format(EUmTable::Screens, TEXT("screens.reconnect.missed"), M));
  }
  // Running: one line if it fits 472 su, else broken only between its two sentences (ВР-VS5-SC31-02)
  FString Run = S(TEXT("screens.reconnect.running")).ToString();
  bool bTwo = false;
  if (MeasureW(FText::FromString(Run), TEXT("type.body")) > InnerW) {
    int32 Dot = INDEX_NONE;
    for (int32 I = 0; I + 1 < Run.Len(); ++I) {
      if ((Run[I] == TEXT('.') || Run[I] == TEXT('!')) && Run[I + 1] == TEXT(' ')) {
        Dot = I;
        break;
      }
    }
    if (Dot != INDEX_NONE) {
      Run = Run.Left(Dot + 1) + TEXT("\n") + Run.Mid(Dot + 2);
      bTwo = true;
    } else {
      Run = ClampLines(Run, TEXT("type.body"), InnerW, 2);
      bTwo = Run.Contains(TEXT("\n"));
    }
  }
  if (Running) Running->SetText(FText::FromString(Run));
  CardHSu = CardHeightSu(St, bTwo);
  SetFrameSize(FVector2D(CardWSu, CardHSu));
  // the icon slot: ↻ (auto), X (manual / expired) - a change of shape; the spinner 32 su (restoring)
  const TCHAR* IconId = bAuto ? TEXT("resource-connection-reconnecting") : TEXT("resource-connection-lost");
  if (Icon && !bRestoring) {
    // the reduced flag first: SetReducedMotion re-inits the animator (the icon would sit at its pre-appear pose)
    const bool bRed = S08IconMotion::IsReducedMotion();
    const bool bReset = Icon->IsReducedMotion() != bRed;
    if (bReset) Icon->SetReducedMotion(bRed);
    const FName Before = Icon->GetIconId();
    UmRoomUi::Icon(Icon, IconId, IconSu);
    if (Before != FName(IconId) || bReset) {
      Icon->ShowAtRest();
      if (bAuto) Icon->PlayAnim(FName(TEXT("cycle")));  // icon.reconnect.ms 1200; reduced - the contract's static branch
    }
  }
  Vis(Icon, !bRestoring);
  Vis(Spinner, bRestoring);
  // lines
  float Y = PadSu;
  Place(Icon, FVector2D(0.5f * (CardWSu - IconSu), Y), FVector2D(IconSu));
  Place(Spinner, FVector2D(0.5f * (CardWSu - SpinnerSu), Y + 0.5f * (IconSu - SpinnerSu)), FVector2D(SpinnerSu));
  Y += IconSu + 16.0f;
  Place(Title, FVector2D(PadSu, Y), FVector2D(InnerW, TitleSu));
  Y += TitleSu;
  Vis(Attempt, bAuto);
  Vis(Missed, bAuto || bManual);
  Vis(Running, bAuto || bManual);
  if (bAuto) {
    Y += 12.0f;
    Place(Attempt, FVector2D(PadSu, Y), FVector2D(InnerW, LineSu));
    Y += LineSu + 8.0f;
  } else if (bManual) {
    Y += 12.0f;
  }
  if (bAuto || bManual) {
    Place(Missed, FVector2D(PadSu, Y), FVector2D(InnerW, LineSu));
    Y += LineSu + 12.0f;
    const float RunH = bTwo ? 2.0f * LineSu : LineSu;
    Place(Running, FVector2D(PadSu, Y), FVector2D(InnerW, RunH));
    Y += RunH;
  }
  // buttons: width max(168, label + 48); manual - the pair of one width, 16 apart, centred
  auto Btn = [](UUmButton* B, const TCHAR* Key, EUmButtonVariant V, bool bEnabled, const TCHAR* Why) {
    if (!B) return;
    FUmButtonModel M;
    M.Variant = V;
    M.Label = S(Key);
    M.HeightSu = ButtonHSu;
    M.MinWidthSu = 168.0f;
    M.bEnabled = bEnabled;
    if (!bEnabled && Why) M.Reason = FS09Reason::Make(Why);
    B->ApplyModel(M);
  };
  const float WLeave = FMath::Max(168.0f, MeasureW(UmRcUpper(TEXT("screens.reconnect.leave")), TEXT("type.button")) + 48.0f);
  const float WRetry = FMath::Max(168.0f, MeasureW(UmRcUpper(TEXT("screens.reconnect.retry")), TEXT("type.button")) + 48.0f);
  const float WLogin = FMath::Max(168.0f, MeasureW(UmRcUpper(TEXT("screens.reconnect.to.login")), TEXT("type.button")) + 48.0f);
  const float By = Y + 24.0f;
  Btn(Leave, TEXT("screens.reconnect.leave"), EUmButtonVariant::Normal, !Model.bLeaveBusy, TEXT("why.syncing"));
  Btn(Retry, TEXT("screens.reconnect.retry"), EUmButtonVariant::Primary, true, nullptr);
  Btn(ToLogin, TEXT("screens.reconnect.to.login"), EUmButtonVariant::Primary, true, nullptr);
  Vis(Leave, bAuto || bManual, true);
  Vis(Retry, bManual, true);  // hidden until the fifth attempt is over (ВР-VS5-SC31-04)
  Vis(ToLogin, bExpired, true);
  if (bAuto) {
    Place(Leave, FVector2D(0.5f * (CardWSu - WLeave), By), FVector2D(WLeave, ButtonHSu));
  } else if (bManual) {
    const float W = FMath::Max(WLeave, WRetry);
    const float X = 0.5f * (CardWSu - (2.0f * W + 16.0f));
    Place(Leave, FVector2D(X, By), FVector2D(W, ButtonHSu));
    Place(Retry, FVector2D(X + W + 16.0f, By), FVector2D(W, ButtonHSu));
  } else if (bExpired) {
    Place(ToLogin, FVector2D(0.5f * (CardWSu - WLogin), By), FVector2D(WLogin, ButtonHSu));
  }
  if (Spinner) Spinner->SetWaiting(bRestoring && IsShown(), FPlatformTime::Seconds() * 1000.0, TEXT("reconnect"));
  SetScreenState(FName(StateName(St)));
}

FString UUmReconnectOverlay::GetTitleText() const { return Title ? Title->GetText().ToString() : FString(); }
FString UUmReconnectOverlay::GetAttemptText() const { return Attempt ? Attempt->GetText().ToString() : FString(); }
FString UUmReconnectOverlay::GetMissedText() const { return Missed ? Missed->GetText().ToString() : FString(); }
FString UUmReconnectOverlay::GetRunningText() const { return Running ? Running->GetText().ToString() : FString(); }
bool UUmReconnectOverlay::IsShownPart(const UWidget* W) const { return W && W->GetVisibility() != ESlateVisibility::Collapsed; }
FName UUmReconnectOverlay::GetIconId() const { return Icon ? Icon->GetIconId() : NAME_None; }

FString UUmReconnectOverlay::PrimaryName() const {
  if (IsShownPart(Retry) && Retry->GetModel().Variant == EUmButtonVariant::Primary) return TEXT("retry");
  if (IsShownPart(ToLogin) && ToLogin->GetModel().Variant == EUmButtonVariant::Primary) return TEXT("login");
  return TEXT("none");
}

FString UUmReconnectOverlay::ShotExtra() const {
  return FString::Printf(TEXT(" attempt=%d missed=%d primary=%s card=%.0f"), Model.State == EUmReconnectState::Auto ? Model.Attempt : 0,
                         Model.Missed, *PrimaryName(), CardHSu);
}

void UUmReconnectOverlay::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput) {
  Arbiter = InArbiter;
  Input = MoveTemp(InInput);
  TWeakObjectPtr<UUmReconnectOverlay> WeakThis(this);
  for (const TPair<UUmButton*, const TCHAR*>& B : {TPair<UUmButton*, const TCHAR*>(Leave.Get(), TEXT("screens.reconnect.leave")),
                                                   TPair<UUmButton*, const TCHAR*>(Retry.Get(), TEXT("screens.reconnect.retry")),
                                                   TPair<UUmButton*, const TCHAR*>(ToLogin.Get(), TEXT("screens.reconnect.to.login"))}) {
    if (!B.Key) continue;
    const FName Name(B.Value);
    B.Key->SetPress(Name, Arbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, Name](const FS09HudPressOutcome& O) {
      if (UUmReconnectOverlay* Self = WeakThis.Get()) Self->OnPressOutcome(Name, O);
    }));
  }
}

void UUmReconnectOverlay::OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome) {
  if (Outcome.Result != ES09HudPressResult::Act) return;
  const EUmReconnectState St = Model.State;
  if (Id == FName(TEXT("screens.reconnect.leave")) && (St == EUmReconnectState::Auto || St == EUmReconnectState::Manual)) {
    if (Input.OnSound) Input.OnSound(FName(TEXT("UI-BTN-CLICK")));
    if (Input.OnLeave) Input.OnLeave();
  } else if (Id == FName(TEXT("screens.reconnect.retry")) && St == EUmReconnectState::Manual) {
    if (Input.OnSound) Input.OnSound(FName(TEXT("UI-CONFIRM")));
    if (Input.OnRetry) Input.OnRetry();
  } else if (Id == FName(TEXT("screens.reconnect.to.login")) && St == EUmReconnectState::Expired) {
    if (Input.OnSound) Input.OnSound(FName(TEXT("UI-CONFIRM")));
    if (Input.OnToLogin) Input.OnToLogin();
  }
}

void UUmReconnectOverlay::SimulatePress(FName Id) {
  if (!Arbiter.IsValid()) Arbiter = MakeShared<FS09HudPressArbiter>();
  Arbiter->Press(Id, Arbiter->Now());
  OnPressOutcome(Id, FS09HudPressArbiter::Decide(Arbiter->Release(Id, Arbiter->Now()), FS09Reason()));
}

void UUmReconnectOverlay::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  if (Spinner && IsShown()) {
    Spinner->SetWaiting(Model.State == EUmReconnectState::Restoring, FPlatformTime::Seconds() * 1000.0, TEXT("reconnect"));
  }
}

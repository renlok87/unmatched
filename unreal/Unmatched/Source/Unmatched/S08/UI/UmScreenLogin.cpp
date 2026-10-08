// VS-7 SC-06, SC-07: LOGIN - see UmScreenLogin.h.
#include "UmScreenLogin.h"

#include "../S08AnimatedIconWidget.h"
#include "../S08IconMotion.h"
#include "../S08UserSettings.h"
#include "UmButton.h"
#include "UmGameHud.h"
#include "UmHudScale.h"
#include "UmHudTheme.h"
#include "UmSpinner.h"
#include "UmText.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/EditableTextBox.h"
#include "Components/NamedSlot.h"
#include "Components/TextBlock.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "HAL/PlatformTime.h"
#include "InputCoreTypes.h"
#include "Internationalization/Culture.h"
#include "Internationalization/Internationalization.h"

const TCHAR* const UUmScreenLogin::WidgetBlueprintPath = TEXT("/Game/S08/UI/Screens/WBP_UI_SCR_LOGIN");

UClass* UUmScreenLogin::WidgetClass() { return UmGameHudSlots::WbpOrNative(UUmScreenLogin::StaticClass(), WidgetBlueprintPath); }

// ------------------------------------------------------------------------------------------------ the model

namespace UmLogin {
EUmLoginError ClassifyError(const FString& Code) {
  // the backend answers a wrong pair with UNAUTHENTICATED («Неверный email или пароль», AuthService.login); a
  // malformed email is a validation error. No answer at all (PARSE of an empty body), 5xx and rate limits are the server.
  static const TCHAR* const Credentials[] = {TEXT("UNAUTHENTICATED"), TEXT("BAD_USER_INPUT"), TEXT("BAD_REQUEST"), TEXT("FORBIDDEN")};
  for (const TCHAR* C : Credentials) {
    if (Code.Equals(C, ESearchCase::IgnoreCase)) return EUmLoginError::Credentials;
  }
  return EUmLoginError::Server;
}

const TCHAR* ErrorName(EUmLoginError E) {
  switch (E) {
    case EUmLoginError::Credentials: return TEXT("credentials");
    case EUmLoginError::Server: return TEXT("server");
    default: return TEXT("-");
  }
}

const TCHAR* FocusName(EUmLoginFocus F) {
  switch (F) {
    case EUmLoginFocus::Password: return TEXT("password");
    case EUmLoginFocus::Submit: return TEXT("submit");
    case EUmLoginFocus::LangRu: return TEXT("ru");
    case EUmLoginFocus::LangEn: return TEXT("en");
    default: return TEXT("email");
  }
}

const TCHAR* StateName(bool bBusy, EUmLoginError Error, bool bEmail, bool bPassword) {
  if (bBusy) return TEXT("busy");
  if (Error != EUmLoginError::None) return TEXT("error");
  return bEmail && bPassword ? TEXT("input") : TEXT("empty");
}

EUmLoginFocus NextFocus(EUmLoginFocus F, bool bBack) {
  const int32 N = 5;
  const int32 I = (static_cast<int32>(F) + (bBack ? N - 1 : 1)) % N;
  return static_cast<EUmLoginFocus>(I);
}

FString Mask(bool bFilled) { return bFilled ? FString::ChrN(MaskDots, TCHAR(0x2022)) : FString(); }
}  // namespace UmLogin

// ------------------------------------------------------------------------------------------------ helpers

namespace {
template <typename T>
T* UmLgFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

void UmLgText(UTextBlock* T, const TCHAR* Type, const TCHAR* Color) {
  if (!T) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  T->SetFont(Theme.Font(FName(Type)));
  T->SetColorAndOpacity(FSlateColor(Theme.Color(FName(Color))));
  T->SetShadowOffset(FVector2D::ZeroVector);
}

void UmLgPlace(UWidget* W, const FVector2D& Pos, const FVector2D& Size, bool bAutoSize = false) {
  UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr;
  if (!S) return;
  S->SetAnchors(FAnchors(0.0f, 0.0f));
  S->SetAlignment(FVector2D::ZeroVector);
  S->SetAutoSize(bAutoSize);
  S->SetPosition(Pos);
  if (!bAutoSize) S->SetSize(Size);
}

float UmLgMeasureW(const FText& Text, const TCHAR* Type) {
  const FSlateFontInfo Font = UUmHudTheme::Get().Font(FName(Type));
  if (FSlateApplication::IsInitialized()) {
    return static_cast<float>(FSlateApplication::Get().GetRenderer()->GetFontMeasureService()->Measure(Text, Font, 1.0f).X);
  }
  return 0.55f * Font.Size * 96.0f / 72.0f * Text.ToString().Len();
}

void UmLgField(UEditableTextBox* Box, bool bHiddenText) {
  if (!Box) return;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  const float PxPerSu = UmHudScale::Current().PxPerSu();
  FEditableTextBoxStyle Style = Box->GetWidgetStyle();
  if (const FSlateBrush* N = Theme.SkinFor(TEXT("input.normal"), PxPerSu)) {
    Style.SetBackgroundImageNormal(*N);
    Style.SetBackgroundImageHovered(*N);
    Style.SetBackgroundImageReadOnly(*N);
  }
  if (const FSlateBrush* F = Theme.SkinFor(TEXT("input.focus"), PxPerSu)) Style.SetBackgroundImageFocused(*F);
  Style.SetPadding(FMargin(16.0f, 12.0f));
  Style.SetFont(Theme.Font(TEXT("type.body")));
  Style.SetBackgroundColor(FSlateColor(FLinearColor::White));  // the skin carries its colours
  FLinearColor Ink = Theme.Color(TEXT("text.primary"));
  if (bHiddenText) Ink.A = 0.0f;  // ВР-SC09: the password's own glyphs never draw; the 8-dot mask does
  Style.SetForegroundColor(FSlateColor(Ink));
  Style.SetFocusedForegroundColor(FSlateColor(Ink));
  FLinearColor Locked = Theme.Color(TEXT("text.secondary"));  // busy: the values kept, locked (ВР-VS4-SC07-02)
  if (bHiddenText) Locked.A = 0.0f;
  Style.SetReadOnlyForegroundColor(FSlateColor(Locked));
  Box->SetWidgetStyle(Style);
}
}  // namespace

// ------------------------------------------------------------------------------------------------ the tree

bool UUmScreenLogin::AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  UCanvasPanel* ContentW = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Content")));
  ContentW->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(ContentW, Parent)) return Fail(TEXT("Content"));
  for (const TCHAR* Name : {TEXT("Title"), TEXT("EmailLabel"), TEXT("PasswordLabel")}) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (!Attach(T, ContentW)) return Fail(Name);
  }
  for (const TCHAR* Name : {TEXT("EmailBox"), TEXT("PasswordBox")}) {
    if (!Attach(Tree.ConstructWidget<UEditableTextBox>(UEditableTextBox::StaticClass(), FName(Name)), ContentW)) return Fail(Name);
  }
  UTextBlock* MaskW = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(TEXT("PasswordMask")));
  MaskW->SetVisibility(ESlateVisibility::HitTestInvisible);
  if (!Attach(MaskW, ContentW)) return Fail(TEXT("PasswordMask"));
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  for (const TCHAR* Name : {TEXT("RevealButton"), TEXT("SubmitButton")}) {
    if (!Attach(Tree.ConstructWidget<UUmButton>(ButtonClass, FName(Name)), ContentW)) return Fail(Name);
  }
  if (!Attach(Tree.ConstructWidget<UUmSpinner>(UUmSpinner::WidgetClass(), FName(TEXT("SubmitSpinner"))), ContentW)) {
    return Fail(TEXT("SubmitSpinner"));
  }
  if (!Attach(Tree.ConstructWidget<US08AnimatedIconWidget>(US08AnimatedIconWidget::StaticClass(), FName(TEXT("ErrorIcon"))), ContentW)) {
    return Fail(TEXT("ErrorIcon"));
  }
  for (const TCHAR* Name : {TEXT("ErrorText"), TEXT("WhyText")}) {
    UTextBlock* T = Tree.ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName(Name));
    T->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (!Attach(T, ContentW)) return Fail(Name);
  }
  return true;
}

bool UUmScreenLogin::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  if (!UUmScreenBase::BuildDefaultTree(Tree, Attach, OutError)) return false;
  UNamedSlot* BodyW = Cast<UNamedSlot>(Tree.FindWidget(FName(TEXT("Body"))));
  if (!BodyW) {
    if (OutError) *OutError = TEXT("no Body");
    return false;
  }
  if (!AttachContent(Tree, BodyW, Attach, OutError)) return false;
  // the language chips sit at the screen's bottom right, outside the card (in Root)
  UCanvasPanel* RootW = Cast<UCanvasPanel>(Tree.FindWidget(FName(TEXT("Root"))));
  UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
  for (const TCHAR* Name : {TEXT("LangRu"), TEXT("LangEn")}) {
    if (!RootW || !Attach(Tree.ConstructWidget<UUmButton>(ButtonClass, FName(Name)), RootW)) {
      if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), Name);
      return false;
    }
  }
  return true;
}

void UUmScreenLogin::BuildContent() {
  if (!WidgetTree || !Body || Body->GetContent()) return;
  FString Problem;
  auto AddTo = [](UWidget* Child, UPanelWidget* Parent) { return Parent && Parent->AddChild(Child) != nullptr; };
  if (!AttachContent(*WidgetTree, Body, AddTo, &Problem)) UE_LOG(LogTemp, Error, TEXT("UMHUD login content: %s"), *Problem);
  if (Root) {
    UClass* ButtonClass = UmGameHudSlots::WbpOrNative(UUmButton::StaticClass(), UUmButton::WidgetBlueprintPath);
    for (const TCHAR* Name : {TEXT("LangRu"), TEXT("LangEn")}) {
      if (!WidgetTree->FindWidget(FName(Name))) Root->AddChild(WidgetTree->ConstructWidget<UUmButton>(ButtonClass, FName(Name)));
    }
  }
}

void UUmScreenLogin::BindParts() {
  Content = UmLgFind<UCanvasPanel>(WidgetTree, TEXT("Content"));
  Title = UmLgFind<UTextBlock>(WidgetTree, TEXT("Title"));
  EmailLabel = UmLgFind<UTextBlock>(WidgetTree, TEXT("EmailLabel"));
  PasswordLabel = UmLgFind<UTextBlock>(WidgetTree, TEXT("PasswordLabel"));
  EmailBox = UmLgFind<UEditableTextBox>(WidgetTree, TEXT("EmailBox"));
  PasswordBox = UmLgFind<UEditableTextBox>(WidgetTree, TEXT("PasswordBox"));
  PasswordMask = UmLgFind<UTextBlock>(WidgetTree, TEXT("PasswordMask"));
  RevealButton = UmLgFind<UUmButton>(WidgetTree, TEXT("RevealButton"));
  SubmitButton = UmLgFind<UUmButton>(WidgetTree, TEXT("SubmitButton"));
  SubmitSpinner = UmLgFind<UUmSpinner>(WidgetTree, TEXT("SubmitSpinner"));
  ErrorIcon = UmLgFind<US08AnimatedIconWidget>(WidgetTree, TEXT("ErrorIcon"));
  ErrorText = UmLgFind<UTextBlock>(WidgetTree, TEXT("ErrorText"));
  WhyText = UmLgFind<UTextBlock>(WidgetTree, TEXT("WhyText"));
  LangRu = UmLgFind<UUmButton>(WidgetTree, TEXT("LangRu"));
  LangEn = UmLgFind<UUmButton>(WidgetTree, TEXT("LangEn"));
}

bool UUmScreenLogin::Initialize() {
  SetIsFocusable(true);  // a button's keyboard focus is the screen's (the ring is drawn on the button, 04 §3.4)
  const bool bFirst = Super::Initialize();
  if (!bFirst || !WidgetTree) return bFirst;
  SetUiId(TEXT("UI-SCR-LOGIN"));
  SetScreenState(FName(TEXT("empty")));
  BindParts();
  UmLgText(Title, TEXT("type.title"), TEXT("text.primary"));
  UmLgText(EmailLabel, TEXT("type.body"), TEXT("text.primary"));
  UmLgText(PasswordLabel, TEXT("type.body"), TEXT("text.primary"));
  UmLgText(PasswordMask, TEXT("type.body"), TEXT("text.primary"));
  UmLgText(ErrorText, TEXT("type.body"), TEXT("text.primary"));
  UmLgText(WhyText, TEXT("type.caption"), TEXT("text.secondary"));
  if (Title) Title->SetText(UmText::Get(EUmTable::Screens, TEXT("screens.login.title")));
  if (EmailLabel) EmailLabel->SetText(UmText::Get(EUmTable::Screens, TEXT("screens.login.email")));
  if (PasswordLabel) PasswordLabel->SetText(UmText::Get(EUmTable::Screens, TEXT("screens.login.password")));
  if (ErrorText) ErrorText->SetAutoWrapText(true);
  UmLgField(EmailBox, false);
  UmLgField(PasswordBox, true);
  if (PasswordBox) {
    PasswordBox->SetIsPassword(true);
    PasswordBox->SetRevertTextOnEscape(false);
  }
  if (EmailBox) EmailBox->SetRevertTextOnEscape(false);
  for (UEditableTextBox* B : {EmailBox.Get(), PasswordBox.Get()}) {
    if (!B) continue;
    B->SetClearKeyboardFocusOnCommit(false);
    B->OnTextChanged.AddUniqueDynamic(this, &UUmScreenLogin::HandleFieldChanged);
    B->OnTextCommitted.AddUniqueDynamic(this, &UUmScreenLogin::HandleFieldCommitted);
  }
  if (RevealButton) RevealButton->SetVisibility(ESlateVisibility::Collapsed);  // ВР-VS4-SC06-03: no v3 glyph yet
  if (SubmitSpinner) SubmitSpinner->SetSizeSu(UmLoader::SpinnerSmallSu);
  SetFrameSize(FVector2D(UmLogin::CardWSu, UmLogin::CardHSu));
  Refresh();
  return bFirst;
}

bool UUmScreenLogin::HasAllParts(FString* OutMissing) const {
  FString Base;
  HasBaseParts(&Base);
  TArray<FString> Missing;
  if (!Base.IsEmpty()) Missing.Add(Base);
  if (!Title) Missing.Add(TEXT("Title"));
  if (!EmailBox) Missing.Add(TEXT("EmailBox"));
  if (!PasswordBox) Missing.Add(TEXT("PasswordBox"));
  if (!RevealButton) Missing.Add(TEXT("RevealButton"));
  if (!SubmitButton) Missing.Add(TEXT("SubmitButton"));
  if (!ErrorText) Missing.Add(TEXT("ErrorText"));
  if (!LangRu) Missing.Add(TEXT("LangRu"));
  if (!LangEn) Missing.Add(TEXT("LangEn"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmScreenLogin::ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu) {
  SetCanvas(InCanvasSu, bInClassS, InPxPerSu);
  Layout();
}

void UUmScreenLogin::Layout() {
  const float P = UmLogin::PadSu;
  const float W = UmLogin::FieldWSu;
  UmLgPlace(Title, FVector2D(P, P), FVector2D(W, 34.0f));
  UmLgPlace(EmailLabel, FVector2D(P, UmLogin::LabelYSu), FVector2D(W, 22.0f));
  UmLgPlace(EmailBox, FVector2D(P, UmLogin::LabelYSu + 24.0f), FVector2D(W, UmLogin::FieldHSu));
  const float PwY = UmLogin::LabelYSu + UmLogin::FieldStepSu;
  UmLgPlace(PasswordLabel, FVector2D(P, PwY), FVector2D(W, 22.0f));
  UmLgPlace(PasswordBox, FVector2D(P, PwY + 24.0f), FVector2D(W, UmLogin::FieldHSu));
  // the mask over the value area (16 su in, up to the reveal slot)
  UmLgPlace(PasswordMask, FVector2D(P + 16.0f, PwY + 24.0f + 0.5f * UmLogin::FieldHSu - 11.0f), FVector2D(W - 60.0f, 22.0f));
  UmLgPlace(RevealButton, FVector2D(P + W - 12.0f - UmLogin::RevealSu, PwY + 24.0f + 12.0f), FVector2D(UmLogin::RevealSu, UmLogin::RevealSu));
  UmLgPlace(SubmitButton, FVector2D(P, UmLogin::SubmitYSu), FVector2D(W, UmLogin::FieldHSu));
  // the busy spinner 32 su left of the centred label, 8 su apart (ВР-VS4-SC07-02)
  const float LabelW = UmLgMeasureW(FText::FromString(GetSubmitLabel().ToUpper()), TEXT("type.button"));
  UmLgPlace(SubmitSpinner, FVector2D(P + 0.5f * (W - LabelW) - 8.0f - 32.0f, UmLogin::SubmitYSu + 8.0f), FVector2D(32.0f, 32.0f));
  const bool bIcon = Error != EUmLoginError::None;
  UmLgPlace(ErrorIcon, FVector2D(P, UmLogin::ErrorYSu), FVector2D(UmLogin::ErrorIconSu, UmLogin::ErrorIconSu));
  const float TextX = P + (bIcon ? UmLogin::ErrorIconSu + 8.0f : 0.0f);
  UmLgPlace(ErrorText, FVector2D(TextX, UmLogin::ErrorYSu + 2.0f), FVector2D(W - (TextX - P), 22.0f));
  // why.login.fields: the first line of the zone when there is no error, the second under an error
  UmLgPlace(WhyText, FVector2D(P, UmLogin::ErrorYSu + (bIcon ? 26.0f : 4.0f)), FVector2D(W, 18.0f));
  // the chips: bottom right of the screen, the safe margin (canvas su in Root)
  const float M = GetSafeMarginSu();
  // VS-7 Frames: each chip as wide as its label (+6 % for the glyph run at 1.125 px/su, padding 8 + 8), 48 su at least
  auto ChipW = [](const TCHAR* Key) {
    return FMath::Max(UmLogin::ChipWSu, FMath::CeilToFloat(1.06f * UmLgMeasureW(UmText::Get(EUmTable::Screens, Key).ToUpper(), TEXT("type.button")) + 18.0f));
  };
  const float EnW = ChipW(TEXT("screens.login.lang.en"));
  const float RuW = ChipW(TEXT("screens.login.lang.ru"));
  const FVector2D EnPos(CanvasSu.X - M - EnW, CanvasSu.Y - M - UmLogin::ChipHSu);
  UmLgPlace(LangEn, EnPos, FVector2D(EnW, UmLogin::ChipHSu));
  UmLgPlace(LangRu, EnPos - FVector2D(RuW + UmLogin::ChipGapSu, 0.0f), FVector2D(RuW, UmLogin::ChipHSu));
}

bool UUmScreenLogin::HasEmail() const { return EmailBox && !EmailBox->GetText().ToString().TrimStartAndEnd().IsEmpty(); }
bool UUmScreenLogin::HasPassword() const { return PasswordBox && !PasswordBox->GetText().IsEmpty(); }
FString UUmScreenLogin::GetMaskText() const { return PasswordMask ? PasswordMask->GetText().ToString() : FString(); }
FString UUmScreenLogin::GetErrorText() const {
  return ErrorText && ErrorText->GetVisibility() != ESlateVisibility::Collapsed ? ErrorText->GetText().ToString() : FString();
}
FString UUmScreenLogin::GetSubmitLabel() const { return SubmitButton ? SubmitButton->GetModel().Label.ToString() : FString(); }
bool UUmScreenLogin::IsSpinnerShown() const { return SubmitSpinner && SubmitSpinner->IsShown(); }
bool UUmScreenLogin::IsSubmitEnabled() const { return SubmitButton && SubmitButton->GetModel().bEnabled; }

bool UUmScreenLogin::IsEnglish() const {
  return FInternationalization::Get().GetCurrentLanguage()->GetTwoLetterISOLanguageName() == TEXT("en");
}

void UUmScreenLogin::Refresh() {
  const bool bEmail = HasEmail();
  const bool bPassword = HasPassword();
  const bool bFilled = bEmail && bPassword;
  if (PasswordMask) PasswordMask->SetText(FText::FromString(UmLogin::Mask(bPassword)));
  if (PasswordMask) {  // busy: the kept values in text.secondary (ВР-VS4-SC07-02)
    PasswordMask->SetColorAndOpacity(FSlateColor(UUmHudTheme::Get().Color(bBusy ? TEXT("text.secondary") : TEXT("text.primary"))));
  }
  for (UEditableTextBox* B : {EmailBox.Get(), PasswordBox.Get()}) {
    if (B) B->SetIsReadOnly(bBusy);  // busy: locked, the values kept
  }
  if (SubmitButton) {
    FUmButtonModel B;
    B.Variant = EUmButtonVariant::Primary;  // the one primary of the screen
    B.HeightSu = UmLogin::FieldHSu;
    B.MinWidthSu = UmLogin::FieldWSu;
    if (bBusy) {
      B.Label = UmText::Get(EUmTable::Screens, TEXT("screens.login.busy"));  // the label is its visible reason
      B.bEnabled = false;
      B.Reason.Key = FName(TEXT("why.syncing"));
    } else if (Error == EUmLoginError::Server) {
      B.Label = UmText::Get(EUmTable::Screens, TEXT("common.btn.retry"));  // ВР-VS4-SC07-04
      B.bEnabled = bFilled;
      if (!bFilled) B.Reason.Key = FName(TEXT("why.login.fields"));
    } else {
      B.Label = UmText::Get(EUmTable::Screens, TEXT("screens.login.submit"));
      B.bEnabled = bFilled;
      if (!bFilled) B.Reason.Key = FName(TEXT("why.login.fields"));
    }
    B.bFocused = bFocusRing && Focus == EUmLoginFocus::Submit && !bBusy;
    SubmitButton->ApplyModel(B);
  }
  auto Chip = [this](UUmButton* Btn, const TCHAR* Key, bool bSelected, EUmLoginFocus F) {
    if (!Btn) return;
    FUmButtonModel B;
    B.Variant = EUmButtonVariant::Normal;
    B.Label = UmText::Get(EUmTable::Screens, Key);
    B.HeightSu = UmLogin::ChipHSu;
    B.MinWidthSu = UmLogin::ChipWSu;
    B.PadXSu = 8.0f;
    B.bSelected = bSelected;
    B.bFocused = bFocusRing && Focus == F;
    Btn->ApplyModel(B);
  };
  const bool bEn = IsEnglish();
  Chip(LangRu, TEXT("screens.login.lang.ru"), !bEn, EUmLoginFocus::LangRu);
  Chip(LangEn, TEXT("screens.login.lang.en"), bEn, EUmLoginFocus::LangEn);
  // the error zone: the X sign + the message (only the X is red), then why.login.fields while «Войти» waits for both
  const bool bErr = Error != EUmLoginError::None && !bBusy;
  if (ErrorIcon) {
    const FName Icon(Error == EUmLoginError::Server ? TEXT("resource-connection-lost") : TEXT("badge-refuse"));
    if (bErr && ErrorIcon->GetIconId() != Icon &&
        ErrorIcon->SetIcon(Icon, UmLogin::ErrorIconSu, S08IconMotion::ExportSizePx(UmLogin::ErrorIconSu, UmHudScale::Current().PxPerSu()))) {
      ErrorIcon->SetDisplaySizeSu(UmLogin::ErrorIconSu);
      ErrorIcon->ShowAtRest();
    }
    ErrorIcon->SetVisibility(bErr ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  }
  if (ErrorText) {
    ErrorText->SetText(UmText::Get(EUmTable::Screens, Error == EUmLoginError::Server ? TEXT("screens.login.error.server")
                                                                                     : TEXT("screens.login.error.credentials")));
    ErrorText->SetVisibility(bErr ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  }
  if (WhyText) {
    WhyText->SetText(UmText::Get(EUmTable::Why, TEXT("why.login.fields")));
    WhyText->SetVisibility(!bFilled && !bBusy ? ESlateVisibility::HitTestInvisible : ESlateVisibility::Collapsed);
  }
  if (SubmitSpinner) SubmitSpinner->SetWaiting(bBusy, FPlatformTime::Seconds() * 1000.0, TEXT("login"));
  SetScreenState(FName(UmLogin::StateName(bBusy, Error, bEmail, bPassword)));
  Layout();
}

void UUmScreenLogin::SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput) {
  Arbiter = InArbiter;
  Input = MoveTemp(InInput);
  TWeakObjectPtr<UUmScreenLogin> WeakThis(this);
  auto Bind = [&WeakThis, this](UUmButton* B, const TCHAR* Id) {
    if (!B) return;
    const FName Name(Id);
    B->SetPress(Name, Arbiter, FS09OnHudPressOutcome::CreateLambda([WeakThis, Name](const FS09HudPressOutcome& O) {
      if (UUmScreenLogin* Self = WeakThis.Get()) Self->OnPressOutcome(Name, O);
    }));
  };
  Bind(SubmitButton, TEXT("screens.login.submit"));
  Bind(LangRu, TEXT("screens.login.lang.ru"));
  Bind(LangEn, TEXT("screens.login.lang.en"));
}

void UUmScreenLogin::OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome) {
  if (Outcome.Result != ES09HudPressResult::Act) return;
  bFocusRing = false;  // a mouse press: no ring (04 §3.4)
  const FString S = Id.ToString();
  if (S == TEXT("screens.login.submit")) {
    Submit(TEXT("button"));
  } else if (S == TEXT("screens.login.lang.ru")) {
    SetLanguage(TEXT("ru"));
  } else if (S == TEXT("screens.login.lang.en")) {
    SetLanguage(TEXT("en"));
  }
}

void UUmScreenLogin::SimulatePress(FName Id) {
  if (!Arbiter.IsValid()) Arbiter = MakeShared<FS09HudPressArbiter>();
  Arbiter->Press(Id, Arbiter->Now());
  OnPressOutcome(Id, FS09HudPressArbiter::Decide(Arbiter->Release(Id, Arbiter->Now()), FS09Reason()));
}

void UUmScreenLogin::SetLanguage(const TCHAR* Culture) {
  if (Input.OnSound) Input.OnSound(FName(TEXT("UI-TOGGLE")));
  UmText::SetUiLanguage(Culture);
  if (US08UserSettings* Settings = US08UserSettings::Get()) {  // VS-7 SC-26 (UI-ACC-010): the choice is kept
    Settings->Language = US08UserSettings::NormalizeLanguage(Culture);
    Settings->SaveConfig();
  }
  // the table texts re-resolve; the fixed ones are set again in the new language
  if (Title) Title->SetText(UmText::Get(EUmTable::Screens, TEXT("screens.login.title")));
  if (EmailLabel) EmailLabel->SetText(UmText::Get(EUmTable::Screens, TEXT("screens.login.email")));
  if (PasswordLabel) PasswordLabel->SetText(UmText::Get(EUmTable::Screens, TEXT("screens.login.password")));
  Refresh();
}

bool UUmScreenLogin::Submit(const TCHAR* Source) {
  if (bBusy) return false;  // a repeat waits for the answer (SC-07)
  if (!HasEmail() || !HasPassword()) {
    Refresh();
    return false;  // «Войти» explains itself (why.login.fields)
  }
  bBusy = true;
  Error = EUmLoginError::None;
  BusySinceMs = FPlatformTime::Seconds() * 1000.0;
  ++SubmitCount;
  if (Input.OnSound) Input.OnSound(FName(TEXT("UI-BTN-CLICK")));
  Refresh();
  if (Input.OnSubmit) Input.OnSubmit(EmailBox->GetText().ToString().TrimStartAndEnd(), PasswordBox->GetText().ToString());
  return true;
}

void UUmScreenLogin::ShowError(EUmLoginError InError) {
  bBusy = false;
  Error = InError;
  if (Error == EUmLoginError::Credentials) {
    // never which field: the email stays, the password goes and takes the focus (ВР-VS4-SC07-03)
    if (PasswordBox) PasswordBox->SetText(FText::GetEmpty());
    SetFocusTo(EUmLoginFocus::Password);
  } else if (Error == EUmLoginError::Server) {
    bFocusRing = true;  // «Повторить» carries the keyboard ring (ВР-VS4-SC07-04)
    SetFocusTo(EUmLoginFocus::Submit);
  }
  Refresh();
}

void UUmScreenLogin::ResetAfterLogin() {
  bBusy = false;
  Error = EUmLoginError::None;
  if (PasswordBox) PasswordBox->SetText(FText::GetEmpty());
  Refresh();
}

void UUmScreenLogin::OnShown() {
  SetFocusTo(Error == EUmLoginError::Credentials ? EUmLoginFocus::Password : EUmLoginFocus::Email);
  Refresh();
}

void UUmScreenLogin::SetFocusTo(EUmLoginFocus F) {
  Focus = F;
  if (F == EUmLoginFocus::Email && EmailBox) {
    EmailBox->SetKeyboardFocus();
  } else if (F == EUmLoginFocus::Password && PasswordBox) {
    PasswordBox->SetKeyboardFocus();
  } else if (IsFocusable()) {
    SetKeyboardFocus();  // the screen holds the keys; the ring marks the button
  }
  Refresh();
}

bool UUmScreenLogin::HandleKey(const FKey& Key, bool bShift, bool bRepeat) {
  if (!IsShown()) return false;
  if (Key == EKeys::Tab) {
    bFocusRing = true;
    SetFocusTo(UmLogin::NextFocus(Focus, bShift));
    return true;
  }
  if (Key == EKeys::Enter) {
    if (bRepeat) return true;  // Enter sends exactly once
    if (Focus == EUmLoginFocus::Email) {
      SetFocusTo(EUmLoginFocus::Password);
    } else if (Focus == EUmLoginFocus::LangRu) {
      SetLanguage(TEXT("ru"));
    } else if (Focus == EUmLoginFocus::LangEn) {
      SetLanguage(TEXT("en"));
    } else {
      Submit(TEXT("enter"));
    }
    return true;
  }
  return false;
}

FReply UUmScreenLogin::NativeOnPreviewKeyDown(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent) {
  if (HandleKey(InKeyEvent.GetKey(), InKeyEvent.IsShiftDown(), InKeyEvent.IsRepeat())) return FReply::Handled();
  return Super::NativeOnPreviewKeyDown(InGeometry, InKeyEvent);
}

void UUmScreenLogin::HandleFieldChanged(const FText& /*Text*/) {
  // typing clears a shown error (the next submit gives a fresh answer)
  if (!bBusy && Error != EUmLoginError::None) Error = EUmLoginError::None;
  Refresh();
}

void UUmScreenLogin::HandleFieldCommitted(const FText& /*Text*/, ETextCommit::Type /*Method*/) {
  // Enter is taken by the preview (HandleKey) - a commit by focus loss changes nothing
}

void UUmScreenLogin::SetFieldsForTest(const FString& Email, const FString& Password) {
  if (EmailBox) EmailBox->SetText(FText::FromString(Email));
  if (PasswordBox) PasswordBox->SetText(FText::FromString(Password));
  if (!bBusy) Error = EUmLoginError::None;
  Refresh();
}

void UUmScreenLogin::StepLogin() {
  // a click into a field moves the focus there (no ring: the mouse)
  if (EmailBox && EmailBox->HasKeyboardFocus() && Focus != EUmLoginFocus::Email) {
    Focus = EUmLoginFocus::Email;
    bFocusRing = false;
    Refresh();
  } else if (PasswordBox && PasswordBox->HasKeyboardFocus() && Focus != EUmLoginFocus::Password) {
    Focus = EUmLoginFocus::Password;
    bFocusRing = false;
    Refresh();
  }
  if (SubmitSpinner) SubmitSpinner->SetWaiting(bBusy, FPlatformTime::Seconds() * 1000.0, TEXT("login"));
}

void UUmScreenLogin::NativeTick(const FGeometry& MyGeometry, float InDeltaTime) {
  Super::NativeTick(MyGeometry, InDeltaTime);
  if (IsShown()) StepLogin();
}

FString UUmScreenLogin::ShotExtra() const {
  return FString::Printf(TEXT(" error=%s focus=%s filled=%d%d lang=%s primary=1"), UmLogin::ErrorName(Error), UmLogin::FocusName(Focus),
                         HasEmail() ? 1 : 0, HasPassword() ? 1 : 0, IsEnglish() ? TEXT("en") : TEXT("ru"));
}

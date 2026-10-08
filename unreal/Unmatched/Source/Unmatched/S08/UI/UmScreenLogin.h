// VS-7 SC-06, SC-07 (docs/game-design/visual/06-tasks/screens.csv SC-06, SC-07; 04-hud-spec.md §1.2, §3.1, §3.3, §3.4,
// §3.7; 02 §4.2, §4.3, §5.5, §11.4; Q-005, ВР-38, ВР-SC09; the accepted CX-28 mockups art/imagegen/sc06-login-form-codex,
// sc07-login-errors-codex and their decisions ВР-VS4-SC06-01...09, ВР-VS4-SC07-01...05): LOGIN - UUmScreenLogin
// (/Game/S08/UI/Screens/WBP_UI_SCR_LOGIN) in the root's Screens over the menu backdrop (SC-02).
//
//   card     the frame 480 x 420 su centred (the modal skin: panel.bg 1.0, radius.l), 24 su inside: «Вход» type.title;
//            the labels «Email» / «Пароль» above their fields in every state (ВР-VS4-SC06-02; step 88 = 64 + the label
//            row); the fields 432 x 48 (input.normal / input.focus skins, type.body); «Войти» 432 x 48 primary; the error
//            zone 432 x <= 44 (two lines). No sign-up link (Q-005). RU / EN chips 48 x 32 bottom right of the screen
//            (the selected one state.pending, ВР-VS4-SC06-04): the UI language (UmText::SetUiLanguage).
//   password never in a trace or a log; the field draws a fixed 8-dot mask while it holds anything, so no frame shows
//            its length (ВР-SC09, ВР-VS7-05); the RevealButton slot 24 su stays empty (no v3 glyph, ВР-VS4-SC06-03).
//   states   empty: «Войти» disabled with why.login.fields under it (focus in Email on show); input: both filled,
//            «Войти» primary; busy (SC-07): «Вход…» in the disabled primary with a 32 su spinner, the fields locked, the
//            cursor busy, a repeat refused until the answer (ВР-VS4-SC07-02); error.credentials: badge-refuse 24 su +
//            «Неверный email или пароль», the password cleared and focused, no field marked (ВР-VS4-SC07-03);
//            error.server: resource-connection-lost 24 su + «Сервер недоступен», «Повторить» in the submit slot
//            (ВР-VS4-SC07-04). Only the two X signs are red.
//   errors   the backend's codes (FS08FlowController::Login -> OnFlowError): UNAUTHENTICATED / BAD_USER_INPUT /
//            BAD_REQUEST / FORBIDDEN -> credentials; anything else (no answer = PARSE, 5xx, rate limit) -> server.
//   keys     Tab / Shift+Tab: Email -> Пароль -> «Войти» -> RU -> EN (the ring on a button, 04 §3.4); Enter: Email ->
//            Пароль, else submit exactly once; repeats ignored.
//   gate     'SHOT widget id=UI-SCR-LOGIN impl=umg state=empty|input|busy|error ... error=-|credentials|server
//            focus=<email|password|submit|ru|en> filled=<email 0|1><password 0|1> lang=ru|en' - no value of a field.
//   sound    PlayScreenSound UI-BTN-CLICK (submit, retry), UI-TOGGLE (the language); UI-LOGIN-OK / -ERR play by themselves.
//   rollback -S08SlateHud=login: the legacy grey form (GD-028...031), this is not built.
#pragma once

#include "CoreMinimal.h"
#include "../../S09/S09HudPress.h"
#include "UmScreenBase.h"
#include "UmScreenLogin.generated.h"

class UBorder;
class UCanvasPanel;
class UEditableTextBox;
class UTextBlock;
class UUmButton;
class UUmSpinner;
class US08AnimatedIconWidget;
struct FKey;

enum class EUmLoginError : uint8 { None, Credentials, Server };
enum class EUmLoginFocus : uint8 { Email, Password, Submit, LangRu, LangEn };

namespace UmLogin {
inline constexpr float CardWSu = 480.0f;
inline constexpr float CardHSu = 420.0f;
inline constexpr float PadSu = 24.0f;
inline constexpr float FieldWSu = 432.0f;
inline constexpr float FieldHSu = 48.0f;
inline constexpr float LabelYSu = 80.0f;      // «Email» label (card-local); the field 24 su lower
inline constexpr float FieldStepSu = 88.0f;   // 64 + the label row (ВР-VS4-SC06-02)
inline constexpr float SubmitYSu = 288.0f;
inline constexpr float ErrorYSu = 342.0f;
inline constexpr float ErrorIconSu = 24.0f;
inline constexpr float RevealSu = 24.0f;
inline constexpr float ChipWSu = 48.0f;
inline constexpr float ChipHSu = 32.0f;
inline constexpr float ChipGapSu = 8.0f;
inline constexpr int32 MaskDots = 8;  // ВР-SC09

/** The backend code of a failed login -> what the screen says (never which field was wrong). */
UNMATCHED_API EUmLoginError ClassifyError(const FString& Code);
UNMATCHED_API const TCHAR* ErrorName(EUmLoginError E);
UNMATCHED_API const TCHAR* FocusName(EUmLoginFocus F);
/** The gate state: busy > error > input (both fields filled) > empty. */
UNMATCHED_API const TCHAR* StateName(bool bBusy, EUmLoginError Error, bool bEmail, bool bPassword);
/** Tab order (04 §1.2): Email -> Пароль -> «Войти» -> RU -> EN, wrapping; bBack = Shift+Tab. */
UNMATCHED_API EUmLoginFocus NextFocus(EUmLoginFocus F, bool bBack);
/** The fixed mask of a non-empty password (ВР-SC09). */
UNMATCHED_API FString Mask(bool bFilled);
}  // namespace UmLogin

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmScreenLogin : public UUmScreenBase {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Screens/WBP_UI_SCR_LOGIN
  static UClass* WidgetClass();

  virtual bool Initialize() override;
  /** The base tree (Root > Veil, Frame > Body) + Content (Canvas) > Title, EmailLabel, EmailBox, PasswordLabel,
   *  PasswordBox, PasswordMask, RevealButton, SubmitButton, SubmitSpinner, ErrorIcon, ErrorText, WhyText; LangRu, LangEn
   *  (UUmButton) in Root at the bottom right of the screen. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  void ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu);

  struct FInput {
    /** One submit (Enter or the button): the owner calls FS08FlowController::Login. The password lives only here. */
    TFunction<void(const FString& Email, const FString& Password)> OnSubmit;
    /** A screen sound (UI-BTN-CLICK, UI-TOGGLE) through AS08FlowGameMode::PlayScreenSound. */
    TFunction<void(FName BankId)> OnSound;
  };
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput);

  /** Shown: the fields keep their text; the focus goes to Email (or the password after a credentials error). */
  void OnShown();
  /** The answer of the login: an error (busy ends) - credentials clear the password and focus it. */
  void ShowError(EUmLoginError Error);
  /** The login went through (or the screen leaves): busy ends, the password is forgotten. */
  void ResetAfterLogin();
  /** Submit as Enter / the button do: refused when a field is empty or a request is in flight; true = sent. */
  bool Submit(const TCHAR* Source);
  bool IsBusy() const { return bBusy; }
  /** The busy spinner shows (after 300 ms of the request, HB-47). */
  bool IsSpinnerShown() const;
  EUmLoginError GetError() const { return Error; }
  EUmLoginFocus GetFocus() const { return Focus; }
  int32 GetSubmitCount() const { return SubmitCount; }
  /** Moves the focus (Tab / the drive): text boxes take the keyboard, buttons draw the ring. */
  void SetFocusTo(EUmLoginFocus F);
  /** A key (the screen's preview or the tests): Tab, Enter; true = taken. */
  bool HandleKey(const FKey& Key, bool bShift, bool bRepeat);
  /** Tests / the evidence drive: the field contents (as typed). */
  void SetFieldsForTest(const FString& Email, const FString& Password);
  void SimulatePress(FName Id);
  bool HasEmail() const;
  bool HasPassword() const;
  FString GetMaskText() const;
  FString GetErrorText() const;
  FString GetSubmitLabel() const;
  bool IsSubmitEnabled() const;
  /** Per frame: the focus follows a mouse click into a field; the busy spinner. */
  void StepLogin();
  virtual FString ShotExtra() const override;

  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> Title;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UEditableTextBox> EmailBox;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UEditableTextBox> PasswordBox;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> RevealButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> SubmitButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> ErrorText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> LangRu;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> LangEn;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> EmailLabel;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> PasswordLabel;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> PasswordMask;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UUmSpinner> SubmitSpinner;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> ErrorIcon;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> WhyText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UCanvasPanel> Content;

 protected:
  virtual void BuildContent() override;
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;
  virtual FReply NativeOnPreviewKeyDown(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent) override;

 private:
  static bool AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError);
  void BindParts();
  void Layout();
  void Refresh();
  void OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome);
  void SetLanguage(const TCHAR* Culture);
  bool IsEnglish() const;
  UFUNCTION()
  void HandleFieldChanged(const FText& Text);
  UFUNCTION()
  void HandleFieldCommitted(const FText& Text, ETextCommit::Type Method);

  bool bBusy = false;
  EUmLoginError Error = EUmLoginError::None;
  EUmLoginFocus Focus = EUmLoginFocus::Email;
  bool bFocusRing = false;  // the ring only with the keyboard (04 §3.4)
  int32 SubmitCount = 0;
  double BusySinceMs = -1.0;
  FString LastRefreshKey;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FInput Input;
};

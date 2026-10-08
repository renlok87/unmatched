// VS-7 S5 SC-31...SC-33 (docs/game-design/visual/06-tasks/screens.csv SC-31, SC-32, SC-33; 04-hud-spec.md §1.9, H14; the
// accepted CX-33 mockups art/imagegen/sc31-reconnect-auto-codex, sc32-reconnect-manual-codex, sc33-reconnect-restore-codex
// and their decisions ВР-VS5-SC31-01...06, ВР-VS5-SC32-01...03, ВР-VS5-SC33-01...04): the RECONNECT overlay -
// UUmReconnectOverlay (/Game/S08/UI/Screens/WBP_UI_SCR_RECONNECT) in the root's Reconnect slot, over every modal.
//
//   states   auto     the link is lost (the HB-14 chip's X, the same edge as CUE-017): «Соединение потеряно»,
//                     «Переподключение… попытка {n} из 5» (n = 1 + the lost time / 10 s), «Пропущено событий: {n}» (the
//                     seqs applied since the loss), «Партия продолжается на сервере. Не закрывайте приложение.», «Выйти в
//                     лобби» (normal) - no primary (ВР-VS5-SC31-04); the icon resource-connection-reconnecting 48 su cycles.
//            manual   50 s of loss (5 x 10 s): the icon resource-connection-lost (a change of shape), no attempt line,
//                     «Выйти в лобби» (normal) + «Переподключить» (the one primary): the attempt cycle starts again.
//            restoring the transport is back (acked) and the state loads, or a lost command answer is being recovered
//                     (GD-037, after 300 ms): loader-spinner 32 su in the 48 su slot + «Загрузка состояния…», no buttons.
//            expired  the session died in a match (GD-038): «Сессия истекла — войдите снова» + «Ко входу» (the one primary,
//                     -> LOGIN); no retry with the old token, no lobby (ВР-VS5-SC32-02/03).
//   card     520 su wide, centred, the modal skin, padding 24, one centred column (ВР-VS5-SC31-02): Icon 48; 16; Title
//            (type.title); 12; Attempt (type.body); 8; Missed (type.body, text.secondary); 12; Running (type.body,
//            text.secondary, two lines between its sentences when it does not fit 472 su); 24; the button row 48; 24. A
//            line a state does not show goes with its gap; the height is the content's (<= 340 su).
//   exit     the link back: the card fades in 200 ms (the scene's saturation returns by CUE-018 / FX-36 itself; the CONN
//            chip and the «Позиции обновлены» toast are HB-14 / HB-40's); the veil goes with the card.
//   input    the veil and the card take every click; Esc is swallowed (the owner); no board command passes.
//   gate     'SHOT widget id=UI-SCR-RECONNECT impl=umg state=<auto|manual|restoring|expired> ... attempt=<n> missed=<n>
//            primary=<retry|login|none>'.
//   rollback -S08SlateHud=reconnect: no overlay (the CONN chip alone says it, as before).
#pragma once

#include "CoreMinimal.h"
#include "../../S09/S09HudPress.h"
#include "UmScreenBase.h"
#include "UmReconnectOverlay.generated.h"

class UCanvasPanel;
class UTextBlock;
class UUmButton;
class UUmSpinner;
class US08AnimatedIconWidget;

enum class EUmReconnectState : uint8 { Hidden, Auto, Manual, Restoring, Expired };

/** One frame's inputs (the flow controller and the HB-14 / CUE-017 net watch). */
struct UNMATCHED_API FUmReconnectInput {
  bool bStarted = false;           // the match runs
  bool bLost = false;              // FS08NetWatch::bLost (the chip's X, CUE-017)
  bool bAcked = false;             // the transport is back (connection_ack), the state not reconciled yet
  bool bAwaitingRecovery = false;  // GD-037: a lost command answer is being recovered
  bool bExpiredInMatch = false;    // GD-038: the session died while a match ran
  double LostForMs = 0.0;          // since the loss (or the last «Переподключить»)
  double RecoveryForMs = 0.0;      // since the GD-037 recovery began
};

struct UNMATCHED_API FUmReconnectModel {
  EUmReconnectState State = EUmReconnectState::Hidden;
  int32 Attempt = 1;
  int32 MaxAttempts = 5;
  int32 Missed = 0;
  bool bLeaveBusy = false;  // a leave is on its way (why.syncing)
  bool operator==(const FUmReconnectModel& O) const {
    return State == O.State && Attempt == O.Attempt && MaxAttempts == O.MaxAttempts && Missed == O.Missed && bLeaveBusy == O.bLeaveBusy;
  }
  bool operator!=(const FUmReconnectModel& O) const { return !(*this == O); }
};

namespace UmReconnect {
inline constexpr double AttemptMs = 10000.0;       // 04 §1.9: attempts 1-5, 10 s each
inline constexpr int32 MaxAttempts = 5;
inline constexpr double RestoreDelayMs = 300.0;    // 04 §3.3: a wait shows after 300 ms (a GD-037 recovery alone)
inline constexpr double ExitMs = 200.0;            // SC-33: the card fades in 200 ms
inline constexpr float CardWSu = 520.0f;
inline constexpr float PadSu = 24.0f;
inline constexpr float IconSu = 48.0f;
inline constexpr float SpinnerSu = 32.0f;
inline constexpr float TitleSu = 34.0f;            // the type.title slot (ВР-VS5-SC31-02: the Roboto metrics)
inline constexpr float LineSu = 20.0f;             // a type.body line
inline constexpr float ButtonHSu = 48.0f;
UNMATCHED_API const TCHAR* StateName(EUmReconnectState S);
/** «попытка n»: 1 + LostForMs / 10 s, at most 5. */
UNMATCHED_API int32 AttemptAt(double LostForMs);
/** The state of a frame (pure): expired > restoring (the transport back) > manual (>= 50 s) > auto; a GD-037 recovery
 *  alone shows restoring after 300 ms; nothing otherwise. */
UNMATCHED_API EUmReconnectState Decide(const FUmReconnectInput& In);
/** The card height (su) of a state; bRunningTwoLines = the Running text is broken between its sentences. */
UNMATCHED_API float CardHeightSu(EUmReconnectState S, bool bRunningTwoLines);
/** The card opacity of the exit at TMs after the link came back (1 -> 0 in 200 ms; reduced motion 100 ms). */
UNMATCHED_API float ExitAlpha(double TMs, bool bReduced);
}  // namespace UmReconnect

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmReconnectOverlay : public UUmModalBase {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Screens/WBP_UI_SCR_RECONNECT
  static UClass* WidgetClass();

  virtual bool Initialize() override;
  /** The base tree + Content (Canvas) > Icon (US08AnimatedIconWidget), Spinner (WBP_UmSpinner), Title, Attempt, Missed,
   *  Running (UTextBlock), Leave, Retry, ToLogin (WBP_UmButton) in Body. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  void ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu);

  struct FInput {
    TFunction<void()> OnLeave;    // «Выйти в лобби» (the owner asks to confirm)
    TFunction<void()> OnRetry;    // «Переподключить»
    TFunction<void()> OnToLogin;  // «Ко входу»
    TFunction<void(FName BankId)> OnSound;
  };
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput);
  /** The one data input; the same model = no work. Hidden goes at once (the owner runs the exit with SetAlphaDirect). */
  void ApplyModel(const FUmReconnectModel& InModel);
  const FUmReconnectModel& GetModel() const { return Model; }
  /** Tests / the evidence drive: a press of Id (screens.reconnect.leave | .retry | .to.login) through the arbiter. */
  void SimulatePress(FName Id);

  FString GetTitleText() const;
  FString GetAttemptText() const;
  FString GetMissedText() const;
  FString GetRunningText() const;
  bool IsShownPart(const UWidget* W) const;
  /** The one primary button of the card ("retry" | "login" | "none"). */
  FString PrimaryName() const;
  FName GetIconId() const;
  float CardHeight() const { return CardHSu; }
  virtual FString ShotExtra() const override;

  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<US08AnimatedIconWidget> Icon;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> Title;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> Attempt;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> Missed;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> Running;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> Retry;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> Leave;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UUmButton> ToLogin;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UUmSpinner> Spinner;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UCanvasPanel> Content;

 protected:
  virtual void BuildContent() override;
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

 private:
  static bool AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError);
  void BindParts();
  void Refresh();
  void OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome);

  FUmReconnectModel Model;
  bool bHasModel = false;
  float CardHSu = 0.0f;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FInput Input;
};

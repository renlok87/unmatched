// VS-3 SC-01 UE part (docs/game-design/visual/06-tasks/screens.csv SC-01; 04-hud-spec.md §1 (common), §3.1-§3.6,
// §4.1-§4.5, §5.1; ВР-H14, ВР-SC04, ВР-SC05, ВР-SC14; the accepted mockup art/imagegen/sc01-screen-base-codex,
// ВР-VS3-SC01-01...10): the base of every screen and modal of the UMG HUD.
//
//   UUmScreenBase  abstract UUserWidget: BindWidget Veil (UImage, panel.veil - the live scene dimmed, never blurred:
//                  HUD-RULES П2), Frame (UBorder, the modal skin: panel.bg 1.0, radius.l), Body (UNamedSlot, the
//                  screen's content); UiId (UI-SCR-*), ScreenState (the gate state of 04 §7.1). PlayShow / PlayHide:
//                  a screen appears in 250 ms and goes at once (the next screen appears over it), reduced motion 100 ms
//                  (04 §1); the safe margins 24 su (class S 16), the buttons 32 su from the edge. The veil takes the
//                  pointer: the input outside a modal is closed (a click on it is the modal's OnVeilClick).
//   UUmModalBase   abstract, over UUmScreenBase: appears in 250 ms, goes in 120 ms, reduced 100 ms (ВР-SC05).
//   Esc            UmScreens::RouteEscape: the top modal closes -> the selection clears -> PAUSE opens (04 §1).
//   SHOT           'SHOT widget id=<UI-ID> impl=umg state=<state> fighter=none bbox=(x,y,w,h) geom=painted visible=1
//                  twin=0 source=<WBP path>' (04 §4.5) - one line per shown screen / modal.
//   capture        -S08ScreenShots (ВР-SC14, evidence queue I-03): the first appearance of every UI-SCR-* id + state
//                  queues one frame <UI-ID>-<state>.png (AS08FlowGameMode::TickUmScreenShots).
//   rollback       -S08SlateHud=<boot|login|lobby|room|loading|menubg|inspect|pause|reconnect|gameover|aborted> (ВР-SC04):
//                  each screen keeps its Slate look until its own step builds it on this base.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../S08ArtHudWidgets.h"
#include "UmScreenBase.generated.h"

class UBorder;
class UCanvasPanel;
class UImage;
class UNamedSlot;
class UUmScreenBase;

namespace UmScreens {
inline constexpr float ShowMs = 250.0f;        // a screen / a modal appears (04 §1, ВР-SC05)
inline constexpr float ModalHideMs = 120.0f;   // a modal goes
inline constexpr float ReducedMs = 100.0f;     // reduced motion (UI-ACC-006)
inline constexpr float MarginLSu = 24.0f;      // the safe margin of the content (04 §1)
inline constexpr float MarginSSu = 16.0f;
inline constexpr float ButtonMarginSu = 32.0f; // the buttons keep 32 su from the edge
/** The safe margin of a layout class. */
UNMATCHED_API float SafeMarginSu(bool bClassS);
/** The opacity of an appearing (bShow) or going screen at TMs from the start (linear; Len from ShowLenMs/HideLenMs). */
UNMATCHED_API float AlphaAt(bool bShow, float TMs, float LenMs);
UNMATCHED_API float ShowLenMs(bool bReduced);
/** A modal goes in 120 ms (reduced 100); a screen goes at once (the next one appears over it). */
UNMATCHED_API float HideLenMs(bool bModal, bool bReduced);
/** 04 §1 Esc: what one press does - the top open modal closes, else the board selection clears, else PAUSE opens. */
enum class EEscape : uint8 { CloseModal, ClearSelection, OpenPause };
UNMATCHED_API EEscape RouteEscape(int32 OpenModals, bool bSelection);
UNMATCHED_API const TCHAR* EscapeName(EEscape E);
/** -S08ScreenShots (ВР-SC14): the file of one screen state, "<UI-ID>-<state>.png". */
UNMATCHED_API FString ShotFileName(const FString& UiId, const FString& State);
/** Every live screen / modal built on the base (the capture queue and the gate walk them). */
UNMATCHED_API TArray<UUmScreenBase*> LiveScreens();
}  // namespace UmScreens

UCLASS(Abstract, Blueprintable, BlueprintType)
class UNMATCHED_API UUmScreenBase : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  virtual void BeginDestroy() override;
  /** Canvas "Root" > Veil (full canvas), Frame (Border, the modal skin) > Body (NamedSlot). FrameSu = the frame size
   *  (0 = the whole canvas inside the safe margins). */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasBaseParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  FString SourceName() const;

  /** The UI-ID of the gate (UI-SCR-*); a screen sets it at construction. */
  void SetUiId(const FString& InId) { UiId = InId; }
  const FString& GetUiId() const { return UiId; }
  void SetScreenState(FName InState) { ScreenState = InState; }
  FName GetScreenState() const { return ScreenState; }
  /** ВР-VS7-76: the state as the gate lines and evidence file names spell it - lower case (a packaged build names an
   *  FName by its first spelling in the name table, "Board", "Connect"; the editor by ours). */
  FString ShotStateName() const { return ScreenState.ToString().ToLower(); }
  virtual bool IsModal() const { return false; }

  /** The canvas (su), the class and px per su of the window: the frame centres, the margins follow the class. */
  void SetCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu);
  /** The frame size (su); 0 = the whole canvas inside the safe margins. */
  void SetFrameSize(const FVector2D& InFrameSu);
  FBox2D FrameRectSu() const;
  float GetSafeMarginSu() const { return UmScreens::SafeMarginSu(bClassS); }
  bool IsClassS() const { return bClassS; }

  void PlayShow();
  void PlayHide();
  /** VS-7 S5: the owner drives the opacity itself (GAMEOVER: the FS09ResultView intro / crossfade; RECONNECT: the 200 ms
   *  exit) - no animation of its own; shown while A > 0 with ShownVis, collapsed at 0. */
  void SetAlphaDirect(float A, ESlateVisibility ShownVis = ESlateVisibility::Visible);
  /** Shown (or appearing); false once hidden (or while it goes). */
  bool IsShown() const { return bShown; }
  float GetAlpha() const { return AlphaNow; }
  /** Steps the opacity at the widget clock; collapses at the end of a hide. */
  void Step();
  /** The SHOT line of the gate (04 §4.5) while shown. */
  virtual void CollectShotLines(TArray<FString>& Out) const;
  /** VS-7: the screen's own fields after the base ones (" key=value ..."; never a secret, a name or a code). */
  virtual FString ShotExtra() const { return FString(); }

  // ---- tests ----
  void SetClockOverrideMs(double Ms) { ClockOverrideMs = Ms; }
  void SetReducedForTest(int32 InReduced) { ReducedOverride = InReduced; }

  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UImage> Veil;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> Frame;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UNamedSlot> Body;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UCanvasPanel> Root;

 protected:
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;
  virtual FReply NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  /** A click on the veil (outside the frame): the input outside is closed; a modal may answer it (the dialog: Cancel). */
  virtual void OnVeilClick() {}
  /** Builds the content into Body (once, after the tree exists). */
  virtual void BuildContent() {}
  void Relayout();
  bool IsReduced() const;
  double NowMs() const;

  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Um Screen") FString UiId;
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Um Screen") FName ScreenState = FName(TEXT("shown"));
  bool bCodeDefaultTree = false;
  FVector2D CanvasSu = FVector2D(1920.0, 1080.0);
  bool bClassS = false;
  float PxPerSu = 1.0f;
  FVector2D FrameSu = FVector2D::ZeroVector;

 private:
  bool bShown = false;
  bool bAnimShow = false;
  double AnimStartMs = -1.0;
  float AnimLenMs = 0.0f;
  float AlphaFrom = 0.0f;
  float AlphaNow = 0.0f;
  double ClockOverrideMs = -1.0;
  int32 ReducedOverride = -1;
};

UCLASS(Abstract, Blueprintable, BlueprintType)
class UNMATCHED_API UUmModalBase : public UUmScreenBase {
  GENERATED_BODY()

 public:
  virtual bool IsModal() const override { return true; }
};

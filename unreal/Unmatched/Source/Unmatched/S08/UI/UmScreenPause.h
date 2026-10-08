// VS-7 S4 SC-24...SC-30 (docs/game-design/visual/06-tasks/screens.csv SC-24...SC-30; 04-hud-spec.md §1.8 H16; the accepted
// CX-32 mockups art/imagegen/sc24-pause-codex ... sc30-settings-graphics-codex and their decisions ВР-VS5-SC24-01...12,
// ВР-VS5-SC25-01...02, ВР-VS5-SC26-01...03, ВР-VS5-SC27-01...02, ВР-VS5-SC28-01, ВР-VS5-SC29-01...02, ВР-VS5-SC30-01): the
// PAUSE modal and the settings - UUmScreenPause (/Game/S08/UI/Screens/WBP_UI_SCR_PAUSE) in the root's Modals.
//
//   modal    720 su wide (the base Frame, modal skin), padding 16, height = content, at most 800 su (720p: 864) and the
//            canvas minus the safe margins (ВР-VS5-SC24-01 / -03). Header: TitleText «Пауза» (type.title); in GAME
//            RunningText «Партия продолжается» (type.body, text.secondary) and, while a combat's defense window is open,
//            DefenseText «До конца окна защиты {n} с» (combatInfo.timeoutAt; the match never stops on the server). A
//            panel.divider 16 su under the header and 16 su over the footer.
//   body     Tabs 160 su (TabSound, TabInterface, TabGame, TabGraphics: 160 x 48, 8 apart; the open tab btn.selected),
//            8 su, Rows 520 su - the pool of UUmSettingRow of the open tab, a divider between rows. When the modal would
//            not fit, Rows scrolls (the mouse wheel; ScrollTrack / ScrollThumb 4 su, 4 su inside the right edge, thumb =
//            visible / total), the header and the footer stay.
//   footer   48 su: LeaveButton (normal; the badge-refuse X 24 su + «Покинуть партию» in GAME, «Выйти из комнаты» in ROOM,
//            none in LOBBY) left, ContinueButton «Продолжить» (the one primary) right; widths max(168, content + 48).
//            While a command is in flight the leave button is disabled with why.syncing, the reason under it (LeaveWhy).
//   tabs     Звук (SC-25), Интерфейс (SC-26 language, SC-27 UI scale, SC-29 rule and key hints + the END TURN sample),
//            Игра (SC-28 animation speed, reduced motion - no shake row, ВР-SC06), Графика (SC-30 quality + the note).
//   input    Esc and «Продолжить» close (the owner: UI-PANEL-CLOSE, SetAudioPaused(false)); a row commit goes to the owner
//            (s08.Settings name + value) which applies, saves and gives the new model back.
//   gate     'SHOT widget id=UI-SCR-PAUSE impl=umg state=<sound|interface|game|graphics> ... context=<game|lobby|room>
//            rows=<n> scroll=<0|1> visible=<su> total=<su> leave=<enabled|disabled|none> defense=<n|-> primary=continue
//            lang=<ru|en|pseudo>' (ВР-SC11: the state is the open tab; the leave dialog writes state=confirm itself).
//   rollback -S08SlateHud=pause: no PAUSE (Esc writes 'INPUT esc pause.unavailable', the menu buttons only trace).
#pragma once

#include "CoreMinimal.h"
#include "../../S09/S09HudPress.h"
#include "UmScreenBase.h"
#include "UmSettingRow.h"
#include "UmScreenPause.generated.h"

class UBorder;
class UCanvasPanel;
class UTextBlock;
class UUmButton;

enum class EUmPauseContext : uint8 { Game, Lobby, Room };
enum class EUmPauseTab : uint8 { Sound, Interface, Game, Graphics };

/** Everything the modal shows: the context and the current values (the owner reads them from US08UserSettings and the
 *  GameUserSettings; the screen never reads the settings itself). */
struct UNMATCHED_API FUmPauseModel {
  EUmPauseContext Context = EUmPauseContext::Game;
  /** >= 0: the defense window is open, n seconds left. */
  int32 DefenseSeconds = -1;
  /** A command in flight: the leave button is disabled with why.syncing. */
  bool bSyncing = false;
  // Звук (SC-25)
  int32 Master = 100;
  bool bMasterMuted = false;
  int32 Music = 60;
  int32 Sfx = 80;
  int32 Ui = 80;
  int32 Vo = 80;
  int32 Ambience = 60;
  bool bAmbienceMuted = false;
  bool bSubtitles = true;
  bool bDescribeSounds = false;
  // Интерфейс (SC-26, SC-27, SC-29)
  FString Language = TEXT("ru");
  int32 UiScale = 100;
  /** 75, or 100 while the window's short side is under 1080 (ВР-62, ВР-VS5-SC27-01). */
  int32 UiScaleMin = 75;
  bool bRuleHints = true;
  FString KeyHints = TEXT("auto");
  /** The key chips show now (auto: no completed match yet) - the sample carries its chip then. */
  bool bKeyChips = true;
  // Игра (SC-28)
  FString AnimSpeed = TEXT("normal");
  bool bReducedMotion = false;
  // Графика (SC-30): 2 high, 1 medium, 0 low, -1 none of them (custom / epic)
  int32 Graphics = 2;
  bool bClassS = false;
  bool operator==(const FUmPauseModel& O) const {
    return Context == O.Context && DefenseSeconds == O.DefenseSeconds && bSyncing == O.bSyncing && Master == O.Master &&
           bMasterMuted == O.bMasterMuted && Music == O.Music && Sfx == O.Sfx && Ui == O.Ui && Vo == O.Vo && Ambience == O.Ambience &&
           bAmbienceMuted == O.bAmbienceMuted && bSubtitles == O.bSubtitles && bDescribeSounds == O.bDescribeSounds &&
           Language == O.Language && UiScale == O.UiScale && UiScaleMin == O.UiScaleMin && bRuleHints == O.bRuleHints &&
           KeyHints == O.KeyHints && bKeyChips == O.bKeyChips && AnimSpeed == O.AnimSpeed && bReducedMotion == O.bReducedMotion &&
           Graphics == O.Graphics && bClassS == O.bClassS;
  }
};

namespace UmPause {
inline constexpr float ModalWSu = 720.0f;
inline constexpr float PadSu = 16.0f;
inline constexpr float TabWSu = 160.0f;
inline constexpr float TabHSu = 48.0f;
inline constexpr float GapSu = 8.0f;
inline constexpr float RowsWSu = 520.0f;
inline constexpr float FooterHSu = 48.0f;
inline constexpr float TitleHSu = 34.0f;
inline constexpr float LineHSu = 20.0f;
inline constexpr float WhyHSu = 18.0f;
inline constexpr float WheelStepSu = 64.0f;
UNMATCHED_API const TCHAR* TabName(EUmPauseTab Tab);
UNMATCHED_API const TCHAR* TabKey(EUmPauseTab Tab);
UNMATCHED_API const TCHAR* ContextName(EUmPauseContext C);
/** The rows of a tab with their current values (ВР-VS5-SC25-01, -SC26-01, -SC27-01, -SC28-01, -SC29-01, -SC30-01). */
UNMATCHED_API TArray<FUmSettingRowModel> Rows(const FUmPauseModel& M, EUmPauseTab Tab);
/** The tallest modal of a canvas: 800 su (720p: 864) and the canvas minus the safe margins. */
UNMATCHED_API float MaxModalHSu(const FVector2D& CanvasSu, bool bClassS);
}  // namespace UmPause

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmScreenPause : public UUmModalBase {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Screens/WBP_UI_SCR_PAUSE
  static UClass* WidgetClass();

  virtual bool Initialize() override;
  /** The base tree + Content (Canvas) > TitleText, RunningText, DefenseText, HeaderDivider, Tabs (Canvas) > TabSound,
   *  TabInterface, TabGame, TabGraphics, Rows (Canvas, clipped), ScrollTrack, ScrollThumb, FooterDivider, LeaveButton,
   *  LeaveWhy, ContinueButton (WBP_UmButton). The rows are made at run time. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  void ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu);

  struct FInput {
    TFunction<void()> OnContinue;
    TFunction<void()> OnLeave;
    TFunction<void(FName Key, const FString& Value)> OnCommit;
    TFunction<void(FName BankId)> OnSound;
    TFunction<void(EUmPauseTab Tab)> OnTab;
  };
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput);

  void ApplyModel(const FUmPauseModel& InModel);
  const FUmPauseModel& GetModel() const { return Model; }
  void SetTab(EUmPauseTab InTab);
  EUmPauseTab GetTab() const { return Tab; }
  /** Esc: «Продолжить» (true when open). */
  bool HandleEscape();
  /** The modal scrolls the rows (su, clamped). */
  void ScrollBy(float DeltaSu);
  void ScrollTo(float OffsetSu);
  float GetScrollSu() const { return ScrollSu; }
  bool IsScrolling() const { return TotalRowsSu > VisibleRowsSu + 0.5f; }
  float GetVisibleRowsSu() const { return VisibleRowsSu; }
  float GetTotalRowsSu() const { return TotalRowsSu; }
  float GetModalHeightSu() const { return ModalHSu; }
  float GetModalWidthSu() const { return ModalW; }
  float GetTabWidthSu() const { return TabW; }
  /** Texts and states as drawn (tests, the SHOT line). */
  FString GetTitleText() const;
  FString GetRunningText() const;
  FString GetDefenseText() const;
  bool IsRunningShown() const;
  bool IsDefenseShown() const;
  bool IsLeaveShown() const;
  bool IsLeaveEnabled() const;
  FString GetLeaveText() const;
  FString GetLeaveWhy() const;
  int32 PrimaryCount() const;
  int32 RowCount() const { return RowCountNow; }
  UUmSettingRow* GetRow(int32 Index) const { return Pool.IsValidIndex(Index) && Index < RowCountNow ? Pool[Index].Get() : nullptr; }
  UUmSettingRow* FindRow(FName Key) const;
  UUmButton* GetTabButton(EUmPauseTab InTab) const;
  /** The footer buttons stay inside the frame and the frame inside the canvas (tests: 720p 150 %). */
  bool FooterVisible() const;
  FBox2D ContinueRectSu() const;
  void SimulatePress(FName Id);
  virtual FString ShotExtra() const override;

  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> TitleText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> RunningText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> DefenseText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> HeaderDivider;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UCanvasPanel> Tabs;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> TabSound;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> TabInterface;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> TabGame;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> TabGraphics;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UCanvasPanel> Rows;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> ScrollTrack;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> ScrollThumb;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> FooterDivider;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> LeaveButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> LeaveWhy;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> ContinueButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UCanvasPanel> Content;

 protected:
  virtual void BuildContent() override;
  virtual FReply NativeOnMouseWheel(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;

 private:
  static bool AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError);
  void BindParts();
  void Refresh();
  void Layout();
  void PlaceRows();
  void OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome);

  UPROPERTY() TArray<TObjectPtr<UUmSettingRow>> Pool;
  UPROPERTY() TArray<TObjectPtr<UBorder>> RowDividers;
  FUmPauseModel Model;
  EUmPauseTab Tab = EUmPauseTab::Sound;
  int32 RowCountNow = 0;
  TArray<float> RowY;
  float ScrollSu = 0.0f;
  float VisibleRowsSu = 0.0f;
  float TotalRowsSu = 0.0f;
  float ModalHSu = 0.0f;
  float BodyTopSu = 0.0f;
  float FooterTopSu = 0.0f;
  float LeaveWSu = 168.0f;
  /** ВР-VS7-47: 160 su, wider only when a tab label needs it (the pseudo-locale) - the modal grows with it. */
  float TabW = UmPause::TabWSu;
  float ModalW = UmPause::ModalWSu;
  bool bHasModel = false;
  float ContinueWSu = 168.0f;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FInput Input;
};

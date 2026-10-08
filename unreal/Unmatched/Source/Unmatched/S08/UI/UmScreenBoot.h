// VS-7 SC-03...SC-05 (docs/game-design/visual/06-tasks/screens.csv SC-03, SC-04, SC-05; 04-hud-spec.md §1.1, §3.1, §3.3;
// 02 §3.3, §4.3, §4.5, §10.5, §11.4; ВР-H19, ВР-75, ВР-SC05, ВР-SC11, ВР-SC15; the accepted CX-27 mockups
// art/imagegen/sc03-boot-loading-codex, sc04-boot-error-codex, sc05-boot-resume-codex and their decisions
// ВР-VS4-SC03-01...11, ВР-VS4-SC04-01...03): BOOT - UUmScreenBoot (/Game/S08/UI/Screens/WBP_UI_SCR_BOOT), a full screen
// in the root's Screens over the menu backdrop (SC-02) under panel.veil 0.6; no frame (the elements stand on the veil).
//
//   loading  the wordmark screens.boot.title (plain text, ВР-H19, type.display, centre, y 400 / 720p y 356), the stage
//            bar 480 x 8 (UUmProgressBar HB-47: done / 3, no percentages, ВР-SC15) at y 500 / 448, the stage caption on a
//            capsule (ВР-VS4-SC03-02: type.body text.secondary, 12 / 4 su padding) 16 su under the bar, the build
//            «сборка {commit}» bottom right 24 su (S 16) from the edges (type.caption text.secondary; the commit of
//            BuildStamp.json of the staged build, else the repository HEAD). 150 % canvases keep the 1080p offsets from
//            the centre (-140 / -40 / -24, ВР-VS4-SC03-03).
//   stages   session 0/3 «Проверка сессии…» -> heroes 1/3 «Загрузка героев…» (waiting, ВР-VS4-SC03-05) -> 2/3 «Загрузка
//            героев… {n}/{total}» (heroList answered) -> boards 2/3 «Загрузка досок…» -> 3/3; each stage has its caption
//            (a bar without one for > 2 s is a defect - never here).
//   error    SC-04: a stage without an answer for 10 s or with a failed answer -> the error capsule 480 x 104 16 su under
//            the caption capsule: resource-connection-lost 48 su (its X the only red), «Сервер недоступен» (type.body,
//            text.primary), «Повторить» primary 168 x 48; retrying: «Повторить» disabled with why.syncing «Синхронизация…»
//            6 su under it, the stage caption stays (ВР-VS4-SC04-01). Retry restarts the current stage.
//   resume   SC-05: the own IN_PROGRESS match (myGames) - the modal UUmBootResume (UUmModalBase, 640 x 300, the modal
//            skin, no second veil, ВР-VS4-SC03-06) over the boards frame: «Партия идёт», «Ваш герой: {hero} · соперник:
//            {opponent} · {board}» (database names, nominative), «В лобби» (normal) and «Вернуться в партию» (primary);
//            resuming: the primary disabled with a 32 su spinner and why.syncing (ВР-VS4-SC03-07). Enter = return,
//            Esc = lobby. 250 / 120 ms (ВР-SC05).
//   gate     'SHOT widget id=UI-SCR-BOOT impl=umg state=loading|error|resume ... stage=<session|heroes|boards|done>
//            done=<n>/3 retrying=0|1 resuming=0|1 build=<commit|->'.
//   sound    PlayScreenSound: UI-BOOT-LOGO when the wordmark first shows, UI-NET-LOST on the error, UI-BTN-CLICK on
//            Retry, UI-PANEL-OPEN / UI-CONFIRM for the modal (docs/game-design/audio/08-screen-audio-hooks.md); the menu
//            music plays by itself.
//   rollback -S08SlateHud=boot: the legacy Slate flow panel, this is not built.
#pragma once

#include "CoreMinimal.h"
#include "../../S09/S09HudPress.h"
#include "UmScreenBase.h"
#include "UmScreenBoot.generated.h"

class UBorder;
class UCanvasPanel;
class UTextBlock;
class UUmButton;
class UUmProgressBar;
class UUmSpinner;
class US08AnimatedIconWidget;
struct FKey;

enum class EUmBootStage : uint8 { Session, Heroes, Boards, Done };

/** The one data input of the BOOT screen (П1). */
struct UNMATCHED_API FUmBootModel {
  EUmBootStage Stage = EUmBootStage::Session;
  /** heroList answered: the counter of the heroes caption ({n}/{total}); before the answer the wait caption. */
  bool bHeroesLoaded = false;
  int32 Heroes = 0;
  int32 HeroesTotal = 0;
  /** SC-04: the current stage failed or timed out; bRetrying = its retry is in flight. */
  bool bError = false;
  bool bRetrying = false;
  /** SC-05: the own live match was found; bResuming = «Вернуться в партию» pressed. */
  bool bResume = false;
  bool bResuming = false;
  FString ResumeHero;
  FString ResumeOpponent;
  FString ResumeBoard;
  /** 8 characters of the build commit ('' = no stamp: the label is hidden). */
  FString BuildCommit;
  bool operator==(const FUmBootModel& O) const {
    return Stage == O.Stage && bHeroesLoaded == O.bHeroesLoaded && Heroes == O.Heroes && HeroesTotal == O.HeroesTotal &&
           bError == O.bError && bRetrying == O.bRetrying && bResume == O.bResume && bResuming == O.bResuming &&
           ResumeHero == O.ResumeHero && ResumeOpponent == O.ResumeOpponent && ResumeBoard == O.ResumeBoard &&
           BuildCommit == O.BuildCommit;
  }
};

namespace UmBoot {
inline constexpr float WordmarkFromCentreSu = -140.0f;  // 1080p: y 400 of 540
inline constexpr float BarFromCentreSu = -40.0f;        // y 500
inline constexpr float CaptionGapSu = 8.0f;             // the capsule 8 su under the bar's bottom (y 516)
inline constexpr float CaptionHSu = 28.0f;
inline constexpr float CaptionPadXSu = 12.0f;
inline constexpr float CaptionPadYSu = 4.0f;
inline constexpr float ErrorWSu = 480.0f;
inline constexpr float ErrorHSu = 104.0f;
inline constexpr float ErrorGapSu = 16.0f;
inline constexpr float ErrorPadSu = 16.0f;
inline constexpr float ErrorIconSu = 48.0f;
inline constexpr float RetryWSu = 168.0f;
inline constexpr float RetryHSu = 48.0f;
inline constexpr float WhyGapSu = 6.0f;
inline constexpr float ResumeWSu = 640.0f;
inline constexpr float ResumeHSu = 300.0f;
inline constexpr float ResumePadSu = 16.0f;
inline constexpr float ResumeLineYSu = 64.0f;  // the mockup line y 454 of the modal at 390
inline constexpr float ResumeLobbyWSu = 168.0f;
inline constexpr float ResumeReturnWSu = 312.0f;
inline constexpr float ResumeButtonsYSu = 212.0f;  // 300 - 40 - 48
/** 04 §1.1: a stage without an answer for 10 s shows the error (SC-04). */
inline constexpr double StageTimeoutMs = 10000.0;
/** ВР-VS7-03: a passed stage keeps its caption at least this long (the player reads it; the frames see it). */
inline constexpr double MinStageMs = 400.0;

/** Stages done of 3 (session, heroes, boards): the bar fill (ВР-SC15, ВР-VS4-SC03-04). */
UNMATCHED_API int32 DoneOf(const FUmBootModel& M);
/** The caption key of the stage (never empty, 04 §1.1: a bar always has its caption). */
UNMATCHED_API FString CaptionKey(const FUmBootModel& M);
/** The caption text (the heroes counter after the answer). */
UNMATCHED_API FText Caption(const FUmBootModel& M);
UNMATCHED_API const TCHAR* StageName(EUmBootStage Stage);
/** The gate state: resume | error | loading. */
UNMATCHED_API const TCHAR* StateName(const FUmBootModel& M);
/** A stage started at StartMs is late at NowMs (10 s, 04 §1.1). */
UNMATCHED_API bool TimedOut(double StartMs, double NowMs);
/** The 8-character commit of a BuildStamp.json text ('' when it has none). */
UNMATCHED_API FString CommitFromStamp(const FString& StampJson);
/** The build commit of this run: <root>/BuildStamp.json of a staged build, else the git HEAD of the project's
 *  repository (editor builds); '' when neither is readable. */
UNMATCHED_API FString BuildCommit();
/** The y (su, canvas) of the wordmark top, the bar and the caption capsule: the 04 columns at 1080p / 720p 100 %, the
 *  1080p offsets from the centre elsewhere (ВР-VS4-SC03-03). */
UNMATCHED_API FVector2D WordmarkBar(const FVector2D& CanvasSu, bool bClassS);
}  // namespace UmBoot

/** SC-05: the resume modal (code tree; it lives inside WBP_UI_SCR_BOOT). Its veil is clear - the screen's veil is the
 *  only one (ВР-VS4-SC03-06); it writes no SHOT line of its own (BOOT state=resume). */
UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmBootResume : public UUmModalBase {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  /** The base tree + Content (Canvas) > ResumeTitle, ResumeLine, LobbyButton, ResumeButton (UUmButton), ResumeSpinner
   *  (UUmSpinner), ResumeWhy. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  void ApplyModel(const FUmBootModel& M);
  void ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu);

  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> ResumeTitle;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> ResumeLine;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> LobbyButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> ResumeButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UUmSpinner> ResumeSpinner;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> ResumeWhy;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UCanvasPanel> Content;

 protected:
  virtual void BuildContent() override;

 private:
  static bool AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError);
  void BindParts();
  void Layout();
};

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmScreenBoot : public UUmScreenBase {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Screens/WBP_UI_SCR_BOOT
  static UClass* WidgetClass();

  virtual bool Initialize() override;
  /** The base tree (Root > Veil, Frame > Body) + Content (Canvas) > Wordmark, Progress (UUmProgressBar), StageCapsule >
   *  StageText, BuildText, ErrorBanner (capsule) > ErrorIcon, ErrorText, RetryButton (UUmButton), WhyText; and
   *  ResumeModal (UUmBootResume) in Root over the frame. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;

  /** The one data input; same model = no work. NowMs = the owner's clock (the bar's 300 ms delay). */
  void ApplyModel(const FUmBootModel& InModel, double NowMs);
  const FUmBootModel& GetModel() const { return Model; }
  /** The canvas of the window (su), the class and px per su. */
  void ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu);

  struct FInput {
    TFunction<void()> OnRetry;
    TFunction<void()> OnResume;
    TFunction<void()> OnLobby;
  };
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput);
  /** Enter / Esc while the modal is open (true = taken). */
  bool HandleKey(const FKey& Key);
  /** Tests / the evidence drive: a press of Id (screens.boot.retry | .resume | .lobby) through the arbiter. */
  void SimulatePress(FName Id);

  FString GetStageText() const;
  FString GetBuildText() const;
  FString GetResumeLineText() const;
  float GetBarPercent() const;
  bool IsErrorShown() const;
  bool IsResumeShown() const;
  UUmBootResume* GetResume() const { return ResumeModal; }
  virtual FString ShotExtra() const override;

  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> Wordmark;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmProgressBar> Progress;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> StageText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> BuildText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> ErrorBanner;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<US08AnimatedIconWidget> ErrorIcon;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> ErrorText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> RetryButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> WhyText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UBorder> StageCapsule;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UCanvasPanel> Content;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UUmBootResume> ResumeModal;

 protected:
  virtual void BuildContent() override;

 private:
  static bool AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError);
  void BindParts();
  void Layout();
  void OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome);
  FUmBootModel Model;
  bool bHasModel = false;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FInput Input;
};

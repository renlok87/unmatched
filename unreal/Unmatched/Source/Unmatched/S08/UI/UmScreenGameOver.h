// VS-7 S5 SC-34...SC-37 (docs/game-design/visual/06-tasks/screens.csv SC-34, SC-35, SC-36, SC-37; 04-hud-spec.md §1.10,
// H14; the accepted CX-34 mockups art/imagegen/sc34-gameover-victory-codex, sc35-gameover-defeat-codex,
// sc36-gameover-board-codex, sc37-gameover-again-codex and their decisions ВР-VS5-SC34-01...09, ВР-VS5-SC35-01/02,
// ВР-VS5-SC36-01...03, ВР-VS5-SC37-01...06): the result screen - UUmScreenGameOver (/Game/S08/UI/Screens/
// WBP_UI_SCR_GAMEOVER) in the root's Modals; it replaces the Slate modal of DE-029 (S08FlowGameModeResult.cpp), whose
// summary (FS09ResultSummary), gate (FS09ResultGate) and modes (FS09ResultView) it shows.
//
//   results  ResultModal 760 x 580 su (class S 680 x 560; VS_AI with three buttons 760 x 560, ВР-VS5-SC37-06), the modal
//            skin, centred over the veil 0.6, one vertical axis (ВР-VS5-SC34-03): OutcomeText y 32 (type.display; victory
//            turn.flash.yellow, defeat state.error, draw / unknown type.banner text.primary), HeadlineText y 96
//            («MEDUSA ПОБЕЖДАЕТ» - by the winning hero, SD-45; type.title card.cream), ReasonText y 140 («King Arthur: HP
//            достигли 0»), TurnText y 168 («Ход 11 · 0:27», type.caption text.secondary); LeftPortrait / RightPortrait 120
//            su at the axis +- 180 (S +- 160), VersusText «против» between, LeftName / RightName (type.heading), the
//            captions «Вы · HP 11/16 · » + «Победитель» (turn.flash.yellow) or «Повержен» (text.secondary) + the fallen
//            heart 24 su; the loser's disc at saturation 0 and opacity 0.6, no red (ВР-VS5-SC34-04); the button row y 500
//            (S 480): «Посмотреть доску» + V chip (normal), [VS_AI: «Сыграть ещё» (normal)], «В лобби» + Enter chip (the one
//            primary). Draw: no headline, reason or turn; both discs in the loser look, «Повержен» both (ВР-VS5-SC34-07).
//   board    SC-36: the modal and the veil crossfade out in 250 ms (FS09ResultView), BoardStrip 520 x 56 su at the bottom
//            centre (panel 0.92): StripText «ХОД 11 · ПОБЕДА», ResultsButton «К итогам» + V (normal), StripLobbyButton «В
//            лобби» + Enter (primary); the chips go first when the three do not fit. Back to the results - no entry anim.
//   again    SC-37 (VS_AI only, F-06 / DE-027): «Сыграть ещё» -> «Создаём партию…» (busy, the width of the wider label)
//            while the owner runs leaveGame -> createGame(VS_AI, the same board) -> selectHero(the same hero) -> toggleReady
//            -> startGame -> UI-SCR-LOADING (no ROOM); a refused step: the toast why.command.rejected, the screen stays.
//   opacity  the owner drives it every frame (SetResultsAlpha: the FS09ResultView intro 500 ms / crossfade 250 ms).
//   gate     'SHOT widget id=UI-SCR-GAMEOVER impl=umg state=<victory|defeat|draw|unknown|board|again> bbox=<the modal or the
//            strip> ... mode=<1v1|vs_ai> chips=0|1 primary=lobby overlapField=<px2 of the strip>' - never a name.
//   rollback -S08SlateHud=gameover: the Slate modal of DE-029 as before.
#pragma once

#include "CoreMinimal.h"
#include "../../S09/S09HudPress.h"
#include "UmScreenBase.h"
#include "UmScreenGameOver.generated.h"

class UBorder;
class UCanvasPanel;
class UTextBlock;
class UUmButton;
class US08AnimatedIconWidget;

enum class EUmGameOverOutcome : uint8 { Victory, Defeat, Draw, Unknown };

struct UNMATCHED_API FUmGameOverSide {
  FString HeroName;   // as the projection names it (nominative, ВР-SC10); '' = unknown
  FName HeroKey;      // the portrait slug
  FString Role;       // «Вы» / «Соперник» / the bot's nickname (VS_AI, ВР-VS5-SC37-01)
  int32 Hp = -1;
  int32 MaxHp = -1;
  bool bWinner = false;
  bool bFallen = false;  // the loser of a decided match, both on a draw (the loser look + «Повержен» + the heart)
  bool operator==(const FUmGameOverSide& O) const {
    return HeroName == O.HeroName && HeroKey == O.HeroKey && Role == O.Role && Hp == O.Hp && MaxHp == O.MaxHp &&
           bWinner == O.bWinner && bFallen == O.bFallen;
  }
};

struct UNMATCHED_API FUmGameOverModel {
  EUmGameOverOutcome Outcome = EUmGameOverOutcome::Unknown;
  FString WinnerHero;  // the headline (by the winning hero)
  FString LoserHero;   // the reason «{hero}: HP достигли 0» ('' = no HP reason)
  int32 Turn = 0;
  int32 DurationSec = -1;
  FUmGameOverSide Left;   // the winner (the viewer without a winner)
  FUmGameOverSide Right;
  bool bVsAi = false;
  bool bKeyChips = true;
  bool bBoard = false;       // SC-36: the board view
  bool bAgainBusy = false;   // SC-37: «Создаём партию…»
  bool bLobbyBusy = false;   // the lobby return was sent
  bool operator==(const FUmGameOverModel& O) const {
    return Outcome == O.Outcome && WinnerHero == O.WinnerHero && LoserHero == O.LoserHero && Turn == O.Turn &&
           DurationSec == O.DurationSec && Left == O.Left && Right == O.Right && bVsAi == O.bVsAi && bKeyChips == O.bKeyChips &&
           bBoard == O.bBoard && bAgainBusy == O.bAgainBusy && bLobbyBusy == O.bLobbyBusy;
  }
  bool operator!=(const FUmGameOverModel& O) const { return !(*this == O); }
};

/** SC-37: the «Сыграть ещё» chain of VS_AI (pure: the owner sends the command of the step it enters). */
enum class EUmAgainStep : uint8 { Idle, Leave, Create, Select, Ready, Start, Done, Failed };
struct UNMATCHED_API FUmAgainInput {
  bool bStarted = false;       // the stage Started
  bool bLobby = false;         // the stage Lobby
  bool bRoom = false;          // the stage Room with a room other than the finished match's
  bool bHeroPicked = false;    // the own seat holds the hero
  bool bReady = false;         // the own seat is ready
  bool bNewMatch = false;      // Started with a game other than the finished one
  bool bError = false;         // the flow reported an error since the step began
  bool bTimedOut = false;      // the step waited longer than StepTimeoutMs
};

namespace UmGameOver {
inline constexpr float ModalWSu = 760.0f;
inline constexpr float ModalHSu = 580.0f;
inline constexpr float ModalSWSu = 680.0f;
inline constexpr float ModalSHSu = 560.0f;
inline constexpr float DiscSu = 120.0f;
inline constexpr float StripWSu = 520.0f;
inline constexpr float StripHSu = 56.0f;
inline constexpr double StepTimeoutMs = 10000.0;
UNMATCHED_API const TCHAR* OutcomeName(EUmGameOverOutcome O);
/** The gate state: victory | defeat | draw | unknown, board on the board view, again while «Сыграть ещё» runs. */
UNMATCHED_API const TCHAR* StateName(const FUmGameOverModel& M);
/** The modal size (su): L 760 x 580, S 680 x 560; VS_AI in class S 760 x 560 (ВР-VS5-SC37-06). */
UNMATCHED_API FVector2D ModalSize(bool bClassS, bool bVsAi);
UNMATCHED_API FText OutcomeText(EUmGameOverOutcome O);
/** «MEDUSA ПОБЕЖДАЕТ» (screens.result.wins in upper case, 04 §6.2). */
UNMATCHED_API FText HeadlineText(const FUmGameOverModel& M);
/** «King Arthur: HP достигли 0» (screens.result.reason.hp); empty without a loser hero. */
UNMATCHED_API FText ReasonText(const FUmGameOverModel& M);
/** «Ход 11 · 0:27» (screens.result.turn.time), «Ход 11» without a known duration. */
UNMATCHED_API FText TurnText(const FUmGameOverModel& M);
/** «m:ss» under an hour, «h:mm:ss» from an hour. */
UNMATCHED_API FString Duration(int32 Seconds);
/** «Вы · HP 11/16 · » (the part before the verdict word, text.secondary). */
UNMATCHED_API FString CaptionLead(const FUmGameOverSide& S);
/** «Победитель» / «Повержен» / '' (unknown). */
UNMATCHED_API FText CaptionVerdict(const FUmGameOverSide& S);
/** «ХОД 11 · ПОБЕДА» (screens.result.board.turn in upper case). */
UNMATCHED_API FText StripText(const FUmGameOverModel& M);
/** SC-37: the next step of the chain from the current one and this frame's inputs. */
UNMATCHED_API EUmAgainStep NextAgainStep(EUmAgainStep Step, const FUmAgainInput& In);
UNMATCHED_API const TCHAR* AgainStepName(EUmAgainStep Step);
/** Rect A x rect B in px^2 (su rects, PxPerSu). */
UNMATCHED_API double OverlapPx2(const FBox2D& A, const FBox2D& B, float PxPerSu);
}  // namespace UmGameOver

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmScreenGameOver : public UUmModalBase {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Screens/WBP_UI_SCR_GAMEOVER
  static UClass* WidgetClass();

  virtual bool Initialize() override;
  /** The base tree + Content (Canvas) > ResultModal (UBorder), OutcomeText, HeadlineText, ReasonText, TurnText,
   *  LeftPortrait / RightPortrait (UBorder), VersusText, LeftName / RightName, LeftCaption / RightCaption, LeftVerdict /
   *  RightVerdict (UTextBlock), LeftHeart / RightHeart (US08AnimatedIconWidget), ViewBoardButton, AgainButton,
   *  LobbyButton (WBP_UmButton), BoardStrip (UBorder), StripText, ResultsButton, StripLobbyButton. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  void ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu);
  /** FIELD of the live layout (su; null = none): the strip's overlap gate (04 §1.6). */
  void SetFieldSu(const FBox2D* InFieldSu);

  struct FInput {
    TFunction<void()> OnViewBoard;  // «Посмотреть доску» / «К итогам» (the owner toggles FS09ResultView)
    TFunction<void()> OnLobby;      // «В лобби»
    TFunction<void()> OnAgain;      // «Сыграть ещё» (VS_AI)
    TFunction<void(FName BankId)> OnSound;
  };
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput);
  /** The one data input; the same model = no work. */
  void ApplyModel(const FUmGameOverModel& InModel);
  const FUmGameOverModel& GetModel() const { return Model; }
  /** The owner's opacities at this frame: the results (modal + veil) and the board strip (FS09ResultView). */
  void SetViewAlphas(float ResultsAlpha, float StripAlpha);
  void SimulatePress(FName Id);

  FString GetOutcomeText() const;
  FString GetHeadlineText() const;
  FString GetReasonText() const;
  FString GetTurnText() const;
  FString GetCaption(bool bLeft) const;  // lead + verdict
  FString GetStripText() const;
  bool IsShownPart(const UWidget* W) const;
  /** The primary buttons shown (the gate: exactly one). */
  int32 PrimaryCount() const;
  FBox2D ModalRectSu() const;
  FBox2D StripRectSu() const;
  /** The strip x FIELD (px^2); 0 without FIELD. */
  double StripOverlapFieldPx2() const;
  const TArray<FString>& GetPortraitLines() const { return PortraitLines; }
  virtual void CollectShotLines(TArray<FString>& Out) const override;
  virtual FString ShotExtra() const override;

  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> ResultModal;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> OutcomeText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> HeadlineText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> ReasonText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> TurnText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> LeftPortrait;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> RightPortrait;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> VersusText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> LeftName;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> RightName;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> LeftCaption;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> RightCaption;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> LeftVerdict;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> RightVerdict;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> LeftHeart;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> RightHeart;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> ViewBoardButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> LobbyButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> AgainButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> BoardStrip;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> StripText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> ResultsButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> StripLobbyButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UCanvasPanel> Content;
  UPROPERTY() TArray<TObjectPtr<UObject>> KeepAlive;

 protected:
  virtual void BuildContent() override;

 private:
  static bool AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError);
  void BindParts();
  void Refresh();
  void RebuildDiscs();
  void OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome);

  FUmGameOverModel Model;
  bool bHasModel = false;
  bool bHasField = false;
  FBox2D FieldSu = FBox2D(ForceInit);
  float ResultsA = 0.0f;
  float StripA = 0.0f;
  bool bStripChips = true;
  FString DiscKeys[2];
  bool DiscLoser[2] = {false, false};
  float DiscPx = 0.0f;
  TArray<FString> PortraitLines;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FInput Input;
};

// VS-7 SC-19, SC-20 (docs/game-design/visual/06-tasks/screens.csv SC-19, SC-20; 04-hud-spec.md §1.5 (new id
// UI-SCR-LOADING), H15; the accepted CX-31 mockups art/imagegen/sc19-loading-codex, sc20-loading-error-codex and their
// decisions ВР-VS5-SC19-01...08, ВР-VS5-SC20-01...03): the match loading - UUmScreenLoading
// (/Game/S08/UI/Screens/WBP_UI_SCR_LOADING) in the root's Screens between the start and the first applied snapshot.
//
//   panel    one centred LoadingPanel (panel.bg 1.0, ВР-VS5-SC19-02), the same su on every canvas: padding 24; StageRow 48 su
//            (Spinner 48 su - loader-spinner, HB-47 - or ErrorIcon resource-connection-lost 48 su in the same slot, then
//            StageText type.title; the group keeps the width of the longest caption, ВР-VS5-SC19-04); LeftCard 240x320,
//            VersusText «против» (type.heading, text.secondary) in a 96 su column, RightCard 240x320 (panel.inset: Portrait
//            160 su - CP-07 disc, show=loading - NameText type.heading, NickText type.caption; the viewer's side left,
//            names as the DB has them, never declined); BoardText «Marmoreal · original map» (boardList); 624 x 494 su.
//   stages   connect «Подключение к партии…» (gameSequence), state «Загрузка состояния…» (gameState), board «Подготовка
//            поля…» (the scene and the v2 figures) - the owner sets them.
//   error    SC-20: «Не удаётся подключиться», the icon instead of the spinner (a change of shape); the button row under
//            BoardText: LobbyButton «В лобби» (normal), RetryButton «Повторить» (the one primary); the panel grows 72 su.
//   gate     'SHOT widget id=UI-SCR-LOADING impl=umg state=<connect|state|board|error> ... board=<marmoreal|sarpedon|other>
//            heroes=<n> primary=<retry|none>' - never a name.
//   rollback -S08SlateHud=loading: no loading screen (the match shows as before).
#pragma once

#include "CoreMinimal.h"
#include "../../S09/S09HudPress.h"
#include "UmScreenBase.h"
#include "UmScreenLoading.generated.h"

class UBorder;
class UCanvasPanel;
class UTextBlock;
class UUmButton;
class UUmSpinner;
class US08AnimatedIconWidget;

enum class EUmLoadingStage : uint8 { Connect, State, Board, Error };

struct UNMATCHED_API FUmLoadingSide {
  FString HeroName;  // '' = not known (the disc stays empty)
  FName HeroKey;
  FString Nick;
};

namespace UmLoading {
inline constexpr float PanelWSu = 624.0f;
inline constexpr float PanelHSu = 494.0f;
inline constexpr float ErrorGrowSu = 72.0f;
inline constexpr double ErrorAfterMs = 10000.0;  // SC-20: 10 s without the first snapshot
inline constexpr double MinStageMs = 600.0;      // ВР-VS7-31: every stage reads (BOOT holds 400) and its frame is taken
UNMATCHED_API const TCHAR* StageName(EUmLoadingStage S);
UNMATCHED_API const TCHAR* StageKey(EUmLoadingStage S);
}  // namespace UmLoading

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmScreenLoading : public UUmScreenBase {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Screens/WBP_UI_SCR_LOADING
  static UClass* WidgetClass();

  virtual bool Initialize() override;
  /** The base tree + Content (Canvas) > LoadingPanel, Spinner (WBP_UmSpinner), ErrorIcon, StageText, LeftCard / RightCard
   *  (UBorder) with LeftPortrait / RightPortrait (UBorder), LeftName / RightName, LeftNick / RightNick, VersusText,
   *  BoardText, LobbyButton, RetryButton (WBP_UmButton). */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  void ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu);

  struct FInput {
    TFunction<void()> OnRetry;
    TFunction<void()> OnLobby;
    TFunction<void(FName BankId)> OnSound;
  };
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput);

  void SetSides(const FUmLoadingSide& Own, const FUmLoadingSide& Opp, const FString& BoardId, const FString& BoardName);
  void SetStage(EUmLoadingStage InStage);
  /** ВР-VS7-32: while the scene under the screen is not the room's board yet (the Marmoreal menu before the Sarpedon swap
   *  at the first snapshot) the veil is opaque card.navy - no other map shows through; panel.veil 0.6 otherwise. */
  void SetVeilOpaque(bool bOpaque);
  bool IsVeilOpaque() const { return bVeilOpaque; }
  EUmLoadingStage GetStage() const { return Stage; }
  FString GetStageText() const;
  FString GetLeftName() const;
  FString GetRightName() const;
  FString GetBoardText() const;
  bool IsSpinnerSlotSpinner() const;
  bool IsErrorIconShown() const;
  bool AreButtonsShown() const;
  bool IsRetryPrimary() const;
  bool IsLobbyPrimary() const;
  FBox2D PanelRectSu() const;
  void SimulatePress(FName Id);
  virtual FString ShotExtra() const override;
  const TArray<FString>& GetPortraitLines() const { return PortraitLines; }

  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> LoadingPanel;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmSpinner> Spinner;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<US08AnimatedIconWidget> ErrorIcon;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> StageText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> LeftCard;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> RightCard;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> LeftPortrait;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UBorder> RightPortrait;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> LeftName;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> RightName;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> LeftNick;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> RightNick;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> VersusText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> BoardText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> LobbyButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> RetryButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UCanvasPanel> Content;
  UPROPERTY() TArray<TObjectPtr<UObject>> KeepAlive;

 protected:
  virtual void BuildContent() override;
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

 private:
  static bool AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError);
  void BindParts();
  void Layout();
  void Refresh();
  void RebuildDiscs();
  void OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome);

  EUmLoadingStage Stage = EUmLoadingStage::Connect;
  bool bVeilOpaque = false;
  FUmLoadingSide Sides[2];
  FString BoardId;
  FString DiscKeys[2];
  float DiscPx = 0.0f;
  TArray<FString> PortraitLines;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FInput Input;
};

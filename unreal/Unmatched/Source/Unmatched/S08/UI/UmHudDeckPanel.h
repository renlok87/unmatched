// VS-3 HB-28 (docs/game-design/visual/06-tasks/hud.csv HB-28; 04-hud-spec.md §2.9, §1.6, §3.3, §6.2, §7.1; accepted
// mockup HB-26 art/imagegen/hud-decks-v1-codex D3-D8, ВР-VS2-HB26-04 / -05 / -10 / -11 / -13; F-05): the deck panel -
// UUmHudDeckPanel (/Game/S08/UI/Hud/WBP_UI_HUD_DECKPANEL), the composition of the own or the opponent's deck without
// any order; the discard browser of the Slate HUD lives inside it as the filter «Только сброс».
//
//   rect     the DECK PANEL slot of FUmHudLayout (HB-26 delta 04): L 1080p (1516, 268, 380, 644), L 720p
//            (1346.67, 268, 336, 524), S (964, 120, 300, 472) / (821.78, 120, 300, 392); the bottom rises over a drawn
//            hand that reaches under it (a fan of 8+ cards at 1080p, ВР-VS3-37) - the panel covers no block shown with it
//            in class L; in class S it is read-only over OPP-HAND and the field edge (04 §1.6, ВР-VS2-HB26-13).
//   inside   Panel (T_Skin_Panel: card.navy 0.92, card.cream edge 0.45, radius 6), padding 12 su; from the top:
//            Title type.title 28 su («Ваша колода · {hero}» / «Колода соперника · {hero}»; too wide - two lines broken
//            only after « · », then 24 su, never cut; lines 1.2 em apart, ВР-VS2-HB26-10); 8 su; the tabs «Ваша» /
//            «Соперник» (UUmButton, 32 su, the selected one Btn_Selected, 8 su apart in L, 4 in S, ВР-VS2-HB26-11) and
//            CloseButton - the ui-close glyph 24 su in a 32 su square at the right (IC-54, «Закрыть» its tooltip,
//            ВР-VS3-38); 8 su; Summary type.caption 14 su text.secondary «В колоде {deck} · Сброс {discard} · Рука
//            {hand}» (20 su a line; «≈» before a stale count); the opponent: his hand as n backs 17 x 24 su, 21 su apart,
//            4 su above and under; 4 su; FilterButton «Только сброс» (30 su; Btn_Selected while on) and, right-aligned
//            on the same row, AllButton «Весь состав» (VS-4 SC-23: the INSPECT deck grid of the side, catalogue order;
//            only with a loaded list; created at run time when an older WBP lacks it); 8 su; the list.
//   list     Rows (UScrollBox, pooled UUmDeckRow, 48 su each, width - 10 su): a whole number of rows (no row is cut by
//            the viewport), a wheel notch scrolls one row; the scrollbar - a 4 su track panel.divider at the right, the
//            thumb card.cream 0.45, radius 2 su, only when the list is longer. Rows sorted by type (attack, defense,
//            versatile, scheme), then by the shown name (casefold) - never the deck or draw order (ВР-VS2-HB26-04).
//   loading  before gameDeckLists answers: 6 skeleton rows (UUmSkeletonRows, after 300 ms - HB-47); a failed fetch:
//            «Сервер недоступен» + «Повторить» (ВР-VS3-39).
//   privacy  the opponent tab: only «В сбросе n» on the rows, the summary and his hand as backs (F-05, D7).
//   input    tabs switch the side (the selected tab stays), CloseButton / Esc close, the filter toggles, a row opens the
//            inspector; a click on the body never reaches the board; a wheel notch moves the list by a row.
//   motion   open 80 ms, close 150 ms (FS09DeckPanelView) - reduced motion: the close in 100 ms (ВР-VS3-40); the alpha
//            comes from the owner's view each frame.
//   rollback -S08SlateHud=deckpanel: the Slate panel of S08FlowGameModeDeckPanel.cpp and the Slate discard browser.
// SHOT: 'SHOT widget id=UI-HUD-DECKPANEL impl=umg state=own|opp ... filter=0|1 list=loaded|loading|failed rows=<n>
//        rowsVisible=<n> first=<i> copies=<n> deck=<n> discard=<n> hand=<n> sumHand=<n> sumDiscard=<n> sumLeft=<n>
//        titleSu=<su> titleLines=<n> header=<su> viewport=<su> scroll=0|1 skeleton=0|1 alpha=<a> bottom=<su>' (counts
//        only, no card name or id).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09DeckPanel.h"
#include "../../S09/S09HudPress.h"
#include "../S08ArtHudWidgets.h"
#include "UmDeckRow.h"
#include "UmHudDeckPanel.generated.h"

class UBorder;
class UCanvasPanel;
class UHorizontalBox;
class UImage;
class UScrollBox;
class USizeBox;
class UTextBlock;
class UTexture2D;
class UUmButton;
class UUmSkeletonRows;

enum class EUmDeckListState : uint8 { Loaded, Loading, Failed };

/** What the panel shows. */
struct UNMATCHED_API FUmDeckPanelModel {
  bool bShow = false;
  ES09DeckSide Side = ES09DeckSide::Own;
  FString HeroName;  // the database name ("Medusa", "King Arthur", ВР-VS2-02)
  FString HeroSlug;  // the backs of the opponent's hand
  int32 DeckCount = 0;
  bool bDeckStale = false;
  int32 DiscardCount = 0;
  bool bDiscardStale = false;
  int32 HandCount = 0;
  int32 Copies = 0;
  EUmDeckListState List = EUmDeckListState::Loading;
  bool bFilterDiscard = false;
  /** Every row of the deck, sorted (type, then name); the filter hides rows, it never drops them from the model. */
  TArray<FUmDeckRowModel> Rows;
  bool operator==(const FUmDeckPanelModel& O) const {
    return bShow == O.bShow && Side == O.Side && HeroName == O.HeroName && HeroSlug == O.HeroSlug &&
           DeckCount == O.DeckCount && bDeckStale == O.bDeckStale && DiscardCount == O.DiscardCount &&
           bDiscardStale == O.bDiscardStale && HandCount == O.HandCount && Copies == O.Copies && List == O.List &&
           bFilterDiscard == O.bFilterDiscard && Rows == O.Rows;
  }
  bool operator!=(const FUmDeckPanelModel& O) const { return !(*this == O); }
  /** The rows the list shows now (the filter applied). */
  TArray<int32> ShownRows() const;
};

/** The layout event of the panel: the DECK PANEL rect of the layout, the bottom over a drawn hand. */
struct UNMATCHED_API FUmDeckPanelFrame {
  bool bClassS = false;
  float PxPerSu = 1.0f;
  FBox2D SlotSu = FBox2D(ForceInit);
  /** The panel's bottom (canvas su): the slot's bottom, or higher over a drawn hand (ВР-VS3-37). */
  float BottomSu = 0.0f;
  bool operator==(const FUmDeckPanelFrame& O) const {
    return bClassS == O.bClassS && PxPerSu == O.PxPerSu && SlotSu == O.SlotSu && BottomSu == O.BottomSu;
  }
};

namespace UmHudDeckPanel {
inline constexpr float PadSu = 12.0f;
inline constexpr float TitleSu = 28.0f;
inline constexpr float TitleSmallSu = 24.0f;
inline constexpr float LineK = 1.2f;          // the title lines 1.2 em apart (HB-26)
inline constexpr float GapSu = 8.0f;
inline constexpr float TabHSu = 32.0f;
inline constexpr float TabPadXSu = 6.0f;      // the tab label 6 su from its edges (text + 12)
inline constexpr float TabGapLSu = 8.0f;
inline constexpr float TabGapSSu = 4.0f;
inline constexpr float CloseSu = 32.0f;
inline constexpr float SummaryLineSu = 20.0f;
inline constexpr float BackWSu = 17.0f;
inline constexpr float BackHSu = 24.0f;
inline constexpr float BackStepSu = 21.0f;
inline constexpr float BacksPadSu = 4.0f;
inline constexpr float FilterGapSu = 4.0f;
inline constexpr float FilterHSu = 30.0f;
inline constexpr float FilterPadXSu = 8.0f;   // the filter label 8 su from its edges (text + 16)
inline constexpr float RowSu = 48.0f;
inline constexpr float ScrollGapSu = 10.0f;   // the rows end 10 su before the inner right edge (the 4 su bar there)
inline constexpr float ScrollWSu = 4.0f;
inline constexpr int32 SkeletonRows = 6;      // HB-47 / HB-28: 6 rows of skeleton
inline constexpr float CloseReducedMs = 100.0f;  // ВР-VS3-40: reduced motion closes in <= 100 ms

/** The model of one side: the S09 model (rows with marks) sorted, the names of the build language, the filter. */
UNMATCHED_API FUmDeckPanelModel Gather(const FS09DeckPanelModel& M, const FString& HeroName, const FString& HeroSlug,
                                       EUmDeckListState List, bool bFilterDiscard, bool bRu);
/** «Ваша колода · Medusa» / «Колода соперника · King Arthur». */
UNMATCHED_API FString TitleText(const FUmDeckPanelModel& M);
/** The title fit: one line at 28 su, else two lines broken after « · », then 24 su (ВР-VS2-HB26-10). */
UNMATCHED_API void FitTitle(const FString& Title, float WidthSu, TFunctionRef<float(const FString&, float)> Measure,
                            float& OutSizeSu, TArray<FString>& OutLines);
/** «В колоде 23 · Сброс 2 · Рука 5» (stale counts with «≈»). */
UNMATCHED_API FText SummaryText(const FUmDeckPanelModel& M);
/** The header height (su, from the panel top: padding, title, tabs, summary, backs, filter and their gaps). */
UNMATCHED_API float HeaderSu(float TitleSizeSu, int32 TitleLines, int32 SummaryLines, bool bBacks);
/** Whole rows that fit under the header (the bottom padding kept). */
UNMATCHED_API int32 Capacity(float PanelHeightSu, float HeaderHeightSu);
/** The reduced-motion opacity of the view's: the close in 100 ms instead of 150 (the open 80 ms stays). */
UNMATCHED_API float ReducedAlpha(float ViewAlpha, bool bOpen);
/** own | opp (04 §7.1). */
UNMATCHED_API const TCHAR* StateName(const FUmDeckPanelModel& M);
/** ВР-VS3-37: the panel's bottom (canvas su) over a drawn hand (its cards and caption, HandSu; invalid = none) that
 *  reaches under the slot - 8 su above it, never above the slot's top; the slot's bottom otherwise. */
UNMATCHED_API float BottomOver(const FBox2D& SlotSu, const FBox2D& HandSu);
}  // namespace UmHudDeckPanel

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmHudDeckPanel : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Hud/WBP_UI_HUD_DECKPANEL
  static UClass* WidgetClass();

  virtual bool Initialize() override;
  /** CanvasPanel "Root" > Border "Panel" > CanvasPanel "Body" > Title; Tabs (HorizontalBox) > TabOwn, TabOpp (UUmButton);
   *  CloseButton (UUmButton); Summary; Backs (HorizontalBox); FilterButton (UUmButton); Rows (ScrollBox); Track, Thumb
   *  (Image); Skeleton (UUmSkeletonRows); ErrorText; RetryButton (UUmButton). */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  FString SourceName() const;

  void SetFrame(const FUmDeckPanelFrame& InFrame);
  const FUmDeckPanelFrame& GetFrame() const { return Frame; }
  /** The one data input (П1): the open side, the applied snapshot, the list, the filter. Same model = no work. */
  void ApplyModel(const FUmDeckPanelModel& InModel);
  const FUmDeckPanelModel& GetModel() const { return Model; }
  /** The view of the owner at NowMs: the opacity (open 80 / close 150 ms), clicks only while open; the skeleton timer.
   *  Returns the HUD-LOADER line of a skeleton change ('' else). */
  FString ApplyView(float Alpha, bool bOpen, double NowMs);
  float GetAlpha() const { return AlphaNow; }
  bool IsOpenNow() const { return bOpenNow; }

  /** Presses: OnTab(outcome, side), OnClose, OnFilter, OnRow(outcome, cardId), OnRetry. */
  struct FInput {
    TFunction<void(const FS09HudPressOutcome&, ES09DeckSide)> OnTab;
    TFunction<void(const FS09HudPressOutcome&)> OnClose;
    TFunction<void(const FS09HudPressOutcome&)> OnFilter;
    TFunction<void(const FS09HudPressOutcome&, const FString&)> OnRow;
    TFunction<void(const FS09HudPressOutcome&)> OnRetry;
    /** VS-4 SC-23: «Весь состав» - the INSPECT deck grid of the shown side. */
    TFunction<void(const FS09HudPressOutcome&, ES09DeckSide)> OnAll;
  };
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput);

  // ---- the list ----
  /** Scrolls to the first shown row First (clamped: the last row ends the viewport). */
  void ScrollToRow(int32 First);
  /** One wheel notch: a row up (bUp) or down. */
  bool WheelStep(bool bUp);
  int32 GetFirstRow() const { return FirstRow; }
  int32 GetCapacity() const { return CapacityNow; }
  int32 GetVisibleRows() const;
  int32 GetShownRowCount() const { return Shown.Num(); }
  float GetHeaderSu() const { return HeaderNow; }
  float GetTitleSizeSu() const { return TitleSizeNow; }
  int32 GetTitleLines() const { return TitleLinesNow.Num(); }
  bool IsScrollbarShown() const;
  bool IsSkeletonShown() const;
  /** The row widget of the shown row I (tests). */
  UUmDeckRow* GetRowWidget(int32 I) const;
  /** The panel body as drawn (canvas su). */
  FBox2D PanelRectSu() const;
  /** The pointer (canvas su) is over the open panel's body. */
  bool ContainsSu(const FVector2D& CanvasSu) const;
  void CollectShotLines(TArray<FString>& Out) const;
  int32 RowPoolSize() const { return Pool.Num(); }

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UCanvasPanel> Root;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UBorder> Panel;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UCanvasPanel> Body;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> Title;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UHorizontalBox> Tabs;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> TabOwn;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> TabOpp;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> CloseButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> Summary;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UHorizontalBox> Backs;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> FilterButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UScrollBox> Rows;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UImage> Track;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UImage> Thumb;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UUmSkeletonRows> Skeleton;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> ErrorText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UUmButton> RetryButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UUmButton> AllButton;

 protected:
  virtual FReply NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual FReply NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual FReply NativeOnMouseWheel(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;

 private:
  void Relayout();
  void ApplyRows();
  void ApplyScrollbar();
  void ApplyBacks();
  UUmDeckRow* AcquireRow(int32 Index);
  FUmDeckPanelFrame Frame;
  bool bHasFrame = false;
  FUmDeckPanelModel Model;
  bool bHasModel = false;
  bool bCodeDefaultTree = false;
  TArray<int32> Shown;
  int32 FirstRow = 0;
  int32 CapacityNow = 0;
  float HeaderNow = 0.0f;
  float ViewportTopSu = 0.0f;
  float TitleSizeNow = UmHudDeckPanel::TitleSu;
  TArray<FString> TitleLinesNow;
  int32 SummaryLinesNow = 1;
  float AlphaNow = 0.0f;
  bool bOpenNow = false;
  bool bSkeletonWaiting = false;
  FString BacksSlug;
  int32 BacksShown = 0;
  UPROPERTY(Transient) TObjectPtr<UTexture2D> BackTexture;
  UPROPERTY(Transient) TArray<TObjectPtr<UUmDeckRow>> Pool;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FInput Input;
};

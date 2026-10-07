// VS-4 HB-39 (docs/game-design/visual/06-tasks/hud.csv HB-39; 04-hud-spec.md §2.10, §4.3, §5.2 step H11, §7.1; ВР-H07;
// the accepted mockup HB-38 art/imagegen/hud-feed-v1-codex, ВР-VS2-HB38-05 / -16 / -20, ВР-78): the event log -
// UUmHudLog (/Game/S08/UI/Hud/WBP_UI_HUD_LOG). It replaces the three Slate feed lines over the hand
// (AddEventFeedLines, S08FlowGameModeOpponent.cpp; rollback -S08SlateHud=log).
//
//   data     one entry per line of FS09EventFeed (a maneuver or an effect trail, ms.log.*), rendered here in the UI
//            language from the trail itself (DescribeTrail: the player, the fighters, the spaces, the card); up to 50
//            lines, the oldest leaves; never an instance id or the EN trace text.
//   row      22 su: a 4 su stripe of the acting player's team (team.p1.screen / team.p2.screen) at the left edge, the
//            turn «Х{n}» (hud.log.turn; the turn the event happened in, not the HUD's current one) type.caption
//            text.secondary at 12 su, the text type.body on one line with «…» at 48 su (the full text is the tooltip);
//            the last row text.primary, the others text.secondary. No chip (ВР-78). The font is the theme's default
//            composite font: its DroidSansFallback draws U+2192 «→» (ВР-VS2-HB38-20).
//   class L  the LOG rect of the layout - (24, 712, 300, 200) at 1080p: the header hud.log.title type.tag at (12, 8),
//            6 rows from y + 40; 720p (24, 688, 300, 104): 3 rows from y + 38 (ВР-VS4-24); the rest scrolls (wheel).
//   class S  no column: «Журнал» in TOP opens the list 360 x 320 su under TOP (left = TOP left, top = TOP bottom + 8), 12
//            rows from y + 40, the 4 su scroll track only when there are more; it may lie over the field while open
//            (04 §2.10) and closes on a click outside it, Esc or the combat.
//   empty    hud.log.empty «Событий пока нет».
//   time     a new line fades in over icon.appear.ms 180; the combat (FS09CombatStage, the defense window) hides the
//            block and the end of it shows it again over 150 ms (hover.ms); reduced motion - no fade. The newest line
//            scrolls into view unless the player scrolled up (autoscroll waits while they read).
//   input    the wheel scrolls, a hover shows the full line, a click on a line with a known card opens the inspector.
// SHOT: 'SHOT widget id=UI-HUD-LOG impl=umg state=lines=<n>|hidden fighter=none bbox=... total=<k> class=L|S open=0|1
//        scroll=<su> atEnd=0|1' - no text.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09OpponentView.h"
#include "../S08ArtHud.h"
#include "../S08ArtHudWidgets.h"
#include "UmHudLog.generated.h"

class UBorder;
class UCanvasPanel;
class UImage;
class UScrollBox;
class USizeBox;
class UTextBlock;
class UVerticalBox;

/** One line of the log. */
struct UNMATCHED_API FUmLogEntry {
  int32 Seq = 0;
  /** The turn the event happened in (turnCount of the acting player's turn); 0 = unknown (no «Х»). */
  int32 Turn = 0;
  /** 0 = team.p1.screen, 1 = team.p2.screen (the acting player's team as the board draws it). */
  int32 TeamSlot = 0;
  FText Text;  // the inline moves (MS-E-106: the first two + «и ещё N»)
  FText Full;  // every move (the tooltip)
  /** VS-5 E4 (VS-4 «Открыто» п. 4, HB-39): shorter forms of Text, tried in order when Text does not fit the row - the
   *  moves without the player (the stripe names the side), then the first move + «и ещё N»; the row never ends before the
   *  first «→». */
  TArray<FText> Shorter;
  /** The card of an effect / a boost when the public piles name it (the click opens the inspector). */
  FString CardId;
};

/** The block's canvas. */
struct UNMATCHED_API FUmLogFrame {
  bool bClassS = false;
  bool bTall = true;
  float PxPerSu = 1.0f;
  /** The panel's size (L: the LOG rect; S: the list 360 x 320). */
  FVector2D SizeSu = FVector2D(300.0, 200.0);
  bool bReduced = false;
  bool operator==(const FUmLogFrame& O) const {
    return bClassS == O.bClassS && bTall == O.bTall && PxPerSu == O.PxPerSu && SizeSu == O.SizeSu && bReduced == O.bReduced;
  }
};

namespace UmHudLog {
inline constexpr int32 MaxLines = 50;
inline constexpr float RowSu = 22.0f;
inline constexpr float StripeSu = 4.0f;
inline constexpr float TurnXSu = 12.0f;
inline constexpr float TextXSu = 48.0f;
inline constexpr float HeaderYSu = 8.0f;
inline constexpr float ListWSu = 360.0f;
inline constexpr float ListHSu = 320.0f;
inline FVector2D ListSizeSu() { return FVector2D(ListWSu, ListHSu); }
/** Rows a canvas shows at once: 6 (1080p column), 3 (720p column), 12 (the class S list). */
UNMATCHED_API int32 VisibleRows(const FUmLogFrame& Frame);
/** The first row's y in the panel: 40 su; the short canvas 38 (3 x 22 inside the 104 su rect, ВР-VS4-24). */
UNMATCHED_API float FirstRowSu(const FUmLogFrame& Frame);
/** The class S list under TOP (left = TOP left, top = TOP bottom + 8). */
UNMATCHED_API FBox2D ListRectSu(const FBox2D& TopRectSu);
/** «Х{n}» / «T{n}» (hud.log.turn). */
UNMATCHED_API FText TurnText(int32 Turn);
/** The line of a trail in the UI language (ms.log.maneuver / ms.log.effect / ms.opp.moves.yours, ms.log.move,
 *  ms.log.stay, ms.log.more, ms.log.boost.part) - the structure of FS09EventFeed::Describe / DescribeEffect. */
UNMATCHED_API void DescribeTrail(const FS09LastMovement& Trail, const FString& CardName, const TArray<FString>& YourFighters,
                                 const FS09EventFeed::FNameOf& PlayerName, const FS09EventFeed::FNameOf& FighterName,
                                 const FS09EventFeed::FCellName& CellName, FText& OutText, FText& OutFull,
                                 TArray<FText>* OutShorter = nullptr);
/** VS-5 E4: the first of Text, Shorter... whose width (Measure, su) fits WidthSu; else the last (shortest) one. */
UNMATCHED_API FText PickRowText(const FUmLogEntry& Entry, float WidthSu, TFunctionRef<float(const FText&)> Measure);
}  // namespace UmHudLog

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmHudLog : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Hud/WBP_UI_HUD_LOG

  virtual bool Initialize() override;
  /** Border "Panel" > CanvasPanel "Root" > TextBlock "Title", TextBlock "Empty", ScrollBox "Scroll" > VerticalBox
   *  "Lines" (the rows are pooled at run time). */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  static UClass* WidgetClass();
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  FString SourceName() const;

  void SetFrame(const FUmLogFrame& InFrame);
  const FUmLogFrame& GetFrame() const { return Frame; }
  /** The data input (П1): every entry of the match so far (the widget keeps the last 50; only the new ones are added). */
  void ApplyModel(const TArray<FUmLogEntry>& Entries, double NowMs);
  /** One new entry. */
  void Push(const FUmLogEntry& Entry, double NowMs);
  /** The combat hides the block (150 ms). */
  void SetHidden(bool bHidden, double NowMs);
  bool IsHiddenByCombat() const { return bHiddenWanted; }
  /** Class S: the list from TOP is open. */
  void SetOpen(bool bOpen);
  bool IsOpen() const { return bOpen; }
  /** The fades; true while something animates. */
  bool Tick(double NowMs);
  void SetOnInspect(TFunction<void(const FString& CardId)> In) { OnInspect = MoveTemp(In); }
  int32 Num() const { return Rows.Num(); }
  /** Rows on screen now (min(total, VisibleRows)); 0 when hidden / closed. */
  int32 ShownRows() const;
  bool IsAtEnd() const;
  /** Scrolls by Rows rows (tests: the player reading; < 0 = up). */
  void ScrollRowsForTest(float RowsBy);
  FText GetRowText(int32 I) const;
  /** VS-5 E4: the text the row draws (Text or a shorter form that fits). */
  FText GetRowShownText(int32 I) const;
  /** The width of the row text (su). */
  float RowTextWidthSu() const;
  FText GetRowTooltip(int32 I) const;
  FName GetRowColorToken(int32 I) const;
  FLinearColor GetStripeColor(int32 I) const;
  void CollectShotLines(TArray<FString>& Out, const FS08ScreenRect& Rect) const;

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UVerticalBox> Lines;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UScrollBox> Scroll;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<UBorder> Panel;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<UCanvasPanel> Root;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<UTextBlock> Title;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<UTextBlock> Empty;

 protected:
  virtual FReply NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;

 private:
  struct FRow {
    FUmLogEntry Entry;
    double AddedMs = 0.0;
  };
  void BindFromTree();
  void Relayout();
  void RestyleRows();
  void AddRowWidget();
  void ApplyVisibility();

  UPROPERTY() TArray<TObjectPtr<USizeBox>> RowBoxes;
  UPROPERTY() TArray<TObjectPtr<UImage>> RowStripes;
  UPROPERTY() TArray<TObjectPtr<UTextBlock>> RowTurns;
  UPROPERTY() TArray<TObjectPtr<UTextBlock>> RowTexts;
  TArray<FRow> Rows;
  FUmLogFrame Frame;
  bool bHasFrame = false;
  bool bHiddenWanted = false;
  bool bOpen = false;
  double HideStartMs = -1.0;
  double ShowStartMs = -1.0;
  float BlockAlpha = 1.0f;
  TFunction<void(const FString&)> OnInspect;
  bool bCodeDefaultTree = false;
};

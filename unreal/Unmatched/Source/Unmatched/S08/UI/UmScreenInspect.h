// VS-4 step V4 (H13) - INSPECT, the read-only card inspector (docs/game-design/visual/06-tasks/screens.csv SC-21, SC-22,
// SC-23; cards-portraits.csv CP-22; 04-hud-spec.md §1.7, §2.9, §3.3, §4.2, §5.2 H13, §7.1; 02 §6.1-§6.4; ВР-47...ВР-51;
// QA-005; F-05; UI-INP-006; the accepted CX-23 mockups art/imagegen/sc21-inspect-own-codex, sc22-inspect-hidden-codex,
// sc23-inspect-deck-codex and their decisions ВР-VS3-SC21-01...08): UUmScreenInspect (/Game/S08/UI/Screens/
// WBP_UI_SCR_INSPECT), a UUmModalBase in the root's Modals.
//
//   modal    852 x 688 su (class S 784 x 600) centred over panel.veil 0.6, the modal skin (panel.bg 1.0, radius.l);
//            appears 250 ms, goes 120 ms, reduced 100 (ВР-SC05). Read-only: it never sends a command (UI-INP-006) and
//            has no primary button (ВР-VS3-SC21-06). Closes with «×» (CloseButton, ui-close IC-54 32 su, «Закрыть» its
//            tooltip), Esc, I, a right click anywhere, a click outside the frame (the veil).
//   own      the card at (24, 24) in the slot 460 x 640 (S 400 x 555): UUmCardWidget show=inspector (S classS-inspector)
//            - RU 452 x 627 su in the 452 x 632 window at 1080p 100 %, EN 400 x 558 in 408 x 566; the ВР-48 / ВР-CP04 cap
//            1.6 x the source pixels shrinks the frame to hug the scan, centred in the slot (ВР-VS3-SC21-07: 1080p 150 %
//            306 x 425 su = 459 x 637 px); the scan loads with the frame and the 32 su spinner after 300 ms (HB-47);
//            no scan key - the 02 §6.1 plate + «Скан карты недоступен». The text column (508, 24, 320, 640) (S 448, 312):
//            the name type.title (two lines at most), the type disc 32 su + the word (hud.inspect.type.*), the value and
//            BOOST runtime text font.card 24 su (hud.inspect.value / .boost - never printed over the scan, ВР-49), the
//            effect text type.body scrolling, «В колоде: n · в руке: h · в сбросе: d» type.caption (own deck only:
//            n = copies - hand - discard, ВР-VS3-SC21-03), at the bottom the key chip «Tab» + «Язык карты» when the
//            registry has both scans (ВР-VS3-SC21-04); Tab switches RU / EN (the scan and the name).
//   hidden   SC-22 (QA-005): the owner hero's back in the same slot (ВР-50, CP-05 / CP-06), «Скрытая информация»
//            type.title and the owner's hero name; the model keeps no name, type, value, text or copies of the card -
//            ApplyModel strips them, so neither the view nor the trace can show them.
//   deck     SC-23 (F-05, ВР-VS3-SC21-05): «Колода · {hero}», the deck grid - a pool of UUmCardWidget show=deckgrid
//            150 x 208 with the «×N» chip 40 x 32 (type.caption, Roboto's equal-width digits) 8 su right of each card,
//            three columns 32 su apart, rows 24 su apart, centred; the viewport shows two whole rows (440 su) between the
//            title band and the bottom margin, a wheel notch scrolls one row (232 su), the 4 su track at the right; the
//            catalogue order of the deck list, never the draw order. A click opens the card in the same modal (deck card:
//            the own view + the «×N» chip after BOOST, ВР-VS3-SC21-08, and «Назад» 120 x 40 over the language row);
//            «Назад» / Backspace return to the grid; the switch fades the content in 150 ms (reduced 100).
//   input    the presses go through the arbiter (DE-014): hud.inspect.close, hud.inspect.back, hud.inspect.grid.<i>;
//            the owner routes the keys while the modal is open (HandleKey: Esc, I, Tab, Backspace; every other key is
//            the modal's - nothing reaches the board, 04 §1).
//   gate     'SHOT widget id=UI-SCR-INSPECT impl=umg state=own|hidden|deck|loading ... modal=1 class=L|S mode=<m>
//            source=<s> face=<ru|en|back|fallback> cap=<scale> grid=<n> first=<row> copies=<n> primary=0' + the
//            CARD-ART line of every shown card (show=inspector|classS-inspector|deckgrid, scale <= 1.6). No card name,
//            no value, no text in any line.
//   rollback -S08SlateHud=inspect: the Slate text inspector of the side panel (BuildInspectorLines), this is not built.
#pragma once

#include "CoreMinimal.h"
#include "../../S09/S09DeckPanel.h"
#include "../../S09/S09HudModel.h"
#include "../../S09/S09HudPress.h"
#include "UmCardWidget.h"
#include "UmScreenBase.h"
#include "UmScreenInspect.generated.h"

class UBorder;
class UCanvasPanel;
class UHorizontalBox;
class UImage;
class UScrollBox;
class USizeBox;
class UTextBlock;
class UUniformGridPanel;
class UVerticalBox;
class UUmButton;
class US08AnimatedIconWidget;
struct FKey;

enum class EUmInspectMode : uint8 { Own, Hidden, Deck, DeckCard };

/** Where the inspector was opened (04 §1.7: the hand, the discard, a log line, a deck panel row, a combat card, the slot
 *  card, the key I; the opponent's backs; a card of the PENDING choice; «Весь состав»; ROOM «Просмотр колоды»; the
 *  review sheet). */
enum class EUmInspectSource : uint8 { Hand, Discard, Log, DeckRow, Combat, Slot, Key, OppHand, Pending, DeckAll, Room, Sheet };

/** «В колоде: n · в руке: h · в сбросе: d» of the own deck (bKnown = the own deck list has the card). */
struct UNMATCHED_API FUmInspectCopies {
  bool bKnown = false;
  int32 Deck = 0;
  int32 Hand = 0;
  int32 Discard = 0;
  int32 Copies = 0;
  bool operator==(const FUmInspectCopies& O) const {
    return bKnown == O.bKnown && Deck == O.Deck && Hand == O.Hand && Discard == O.Discard && Copies == O.Copies;
  }
};

/** What the inspector shows (the one data input, П1). */
struct UNMATCHED_API FUmInspectModel {
  EUmInspectMode Mode = EUmInspectMode::Own;
  EUmInspectSource Source = EUmInspectSource::Hand;
  /** Own / DeckCard: the public face. Hidden: nothing but bHidden (QA-005: ApplyModel strips the rest). */
  FS09CardView Card;
  /** The deck owner's hero slug: the scan key heroSlug:cardSlug (INT-014) and the back (ВР-50). */
  FString HeroSlug;
  /** Hidden: the owner's hero; Deck / DeckCard: the hero of «Колода · {hero}» (the database name, ВР-VS2-02). */
  FString HeroName;
  FUmInspectCopies Copies;
  /** Deck / DeckCard: the deck list in catalogue order (gameDeckLists; ROOM: the hero's catalogue) - never the draw order. */
  TArray<FS09DeckListCard> Deck;
  /** DeckCard: the opened card (index into Deck). */
  int32 DeckIndex = INDEX_NONE;
};

/** What the game mode knows when it opens the inspector (world-free: the tests build it by hand). */
struct UNMATCHED_API FUmInspectContext {
  const FS09PlayerPanel* Own = nullptr;
  const FS09PlayerPanel* Opp = nullptr;
  FString OwnHero;
  FString OwnSlug;
  FString OppHero;
  FString OppSlug;
  const TArray<FS09DeckList>* Lists = nullptr;
};

namespace UmInspect {
// ---- 04 §1.7 and the CX-23 mockups (modal-relative su) ----
inline constexpr float ModalLW = 852.0f;
inline constexpr float ModalLH = 688.0f;
inline constexpr float ModalSW = 784.0f;
inline constexpr float ModalSH = 600.0f;
inline constexpr float PadSu = 24.0f;
inline constexpr float SlotLW = 460.0f;
inline constexpr float SlotLH = 640.0f;
inline constexpr float SlotSW = 400.0f;
inline constexpr float SlotSH = 555.0f;
inline constexpr float ColLX = 508.0f;
inline constexpr float ColLW = 320.0f;
inline constexpr float ColSX = 448.0f;
inline constexpr float ColSW = 312.0f;
inline constexpr float CloseSu = 32.0f;
inline constexpr float TitleY = 64.0f;
inline constexpr float TitleLines = 2.0f;
inline constexpr float TypeY = 128.0f;
inline constexpr float DiscSu = 32.0f;
inline constexpr float DiscGapSu = 12.0f;
inline constexpr float ValueY = 180.0f;
inline constexpr float BoostY = 216.0f;
inline constexpr float ChipY = 278.0f;      // the deck card's «×N» after BOOST (ВР-VS3-SC21-08)
inline constexpr float BodyY = 272.0f;
inline constexpr float BodyDeckCardY = 326.0f;
inline constexpr float CopiesGapSu = 24.0f;
inline constexpr float LangRowSu = 28.0f;
inline constexpr float BackWSu = 120.0f;
inline constexpr float BackHSu = 40.0f;
inline constexpr float BackGapSu = 32.0f;
// the deck grid
inline constexpr int32 GridColumns = 3;
inline constexpr float CellWSu = 150.0f;
inline constexpr float CellHSu = 208.0f;
inline constexpr float GridChipWSu = 40.0f;
inline constexpr float GridChipHSu = 32.0f;
inline constexpr float GridChipGapSu = 8.0f;
inline constexpr float GridColGapSu = 32.0f;
inline constexpr float GridRowGapSu = 24.0f;
inline constexpr float GridViewSu = 440.0f;     // two whole rows
inline constexpr float GridRowStepSu = 232.0f;  // 208 + 24
inline constexpr float GridTitleBandSu = 76.0f;
inline constexpr float GridScrollRoomSu = 24.0f;
inline constexpr float TrackWSu = 4.0f;
inline constexpr float SwitchMs = 150.0f;       // grid <-> card (SC-23 timing)
inline constexpr float SwitchReducedMs = 100.0f;

UNMATCHED_API const TCHAR* ModeName(EUmInspectMode Mode);
UNMATCHED_API const TCHAR* SourceName(EUmInspectSource Source);
/** The SHOT state (04 §7.1): hidden | deck | loading (the scan is loading) | own. */
UNMATCHED_API const TCHAR* StateName(EUmInspectMode Mode, bool bLoading);
/** The modal size, the scan slot and the text column (modal-relative su) of a layout class. */
UNMATCHED_API FVector2D ModalSize(bool bClassS);
UNMATCHED_API FBox2D SlotRect(bool bClassS);
UNMATCHED_API FBox2D ColumnRect(bool bClassS);
/** The card show of the inspector: inspector (L) / classS-inspector (S). */
UNMATCHED_API EUmCardShow CardShow(bool bClassS);
/** The grid viewport (modal-relative su): centred between the title band and the bottom margin. */
UNMATCHED_API FBox2D GridRect(bool bClassS);
/** The grid's rows for N cards and the first row a scroll may show (the last whole rows end the viewport). */
UNMATCHED_API int32 GridRows(int32 Cards);
UNMATCHED_API int32 MaxFirstRow(int32 Cards);
/** hud.inspect.type.attack|defense|versatile|scheme ('' for an unknown type). */
UNMATCHED_API FString TypeKey(const FString& CardType);
/** The printed value of a card: attack (ATTACK, VERSATILE), defense (DEFENSE, else VERSATILE's), INDEX_NONE for a
 *  scheme or none printed. */
UNMATCHED_API int32 ValueOf(const FS09CardView& Card);
/** A catalogue card as a card view (no instance id: a catalogue card is not an instance). */
UNMATCHED_API FS09CardView DeckCardView(const FS09DeckListCard& Card);
/** The deck list of a player (nullptr when not loaded). */
UNMATCHED_API const FS09DeckList* FindList(const FUmInspectContext& C, const FString& PlayerId);
/** The model of one face card opened from Source: the owner (own hand / own discard / own list -> own; else the
 *  opponent), the copies of the own deck, the hero slug. A hidden card goes to Hidden (always the opponent's). */
UNMATCHED_API FUmInspectModel FromCard(const FS09CardView& Card, EUmInspectSource Source, const FUmInspectContext& C);
/** QA-005: the hidden card of the opponent - nothing of the card, only its owner's back and name. */
UNMATCHED_API FUmInspectModel Hidden(const FString& OwnerSlug, const FString& OwnerHero, EUmInspectSource Source);
/** SC-23: the deck grid of a side from its deck list (catalogue order). Mode Deck, or Own with an empty Deck when the
 *  list is not loaded (the caller refuses then). */
UNMATCHED_API FUmInspectModel FromDeck(bool bOwnSide, EUmInspectSource Source, const FUmInspectContext& C);
/** The same from a list in hand (ROOM: the hero's catalogue; the review sheet). */
UNMATCHED_API FUmInspectModel FromList(const FS09DeckList& List, const FString& HeroSlug, const FString& HeroName,
                                       EUmInspectSource Source);
/** The card count of a deck list (the grid's ×N sum). */
UNMATCHED_API int32 CopiesSum(const TArray<FS09DeckListCard>& Deck);
/** 'INSPECT open source=<s> mode=<m> grid=<n> copies=<sum> known=0|1' - counts only, never a name or a value. */
UNMATCHED_API FString OpenLine(const FUmInspectModel& M);
}  // namespace UmInspect

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmScreenInspect : public UUmModalBase {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Screens/WBP_UI_SCR_INSPECT
  static UClass* WidgetClass();

  virtual bool Initialize() override;
  /** The base tree (Root > Veil, Frame > Body) + Content (Canvas) > Card (UUmCardWidget); Column (VerticalBox) >
   *  TitleText, TypeRow (TypeIcon, TypeText), ValueText, BoostText, CopiesChipBox > CopiesChip > CopiesChipText,
   *  BodyText (ScrollBox, fills the rest) > BodyLine, CopiesText, ArtMissingText; LangToggle (LangKey > LangKeyText,
   *  LangText); CloseButton, BackButton (UUmButton); DeckScroll (ScrollBox) > DeckGrid (UniformGridPanel); Track,
   *  Thumb (Image). */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;

  /** The one data input: shows the model (QA-005: a hidden card's fields are dropped here). Same model = no work. */
  void ApplyModel(const FUmInspectModel& InModel);
  const FUmInspectModel& GetModel() const { return Model; }
  /** Opens (250 ms) with the model, or swaps the content of an open inspector. */
  void Open(const FUmInspectModel& InModel);
  /** Closes (120 ms) and calls OnClose(Why) once: "button", "esc", "key-i", "rmb", "outside", "owner". */
  void Close(const TCHAR* Why);
  /** The canvas of the window (su), the class and px per su: the frame and the content follow (L 852 x 688 / S 784 x 600). */
  void ApplyCanvas(const FVector2D& InCanvasSu, bool bInClassS, float InPxPerSu);
  bool IsOpen() const { return IsShown(); }

  struct FInput {
    /** The modal closed (the owner clears its inspect state). */
    TFunction<void(const TCHAR* Why)> OnClose;
    /** A grid card opened / the grid came back (CRD-INSPECT-PAGE; the trace). DeckIndex INDEX_NONE = the grid. */
    TFunction<void(int32 DeckIndex)> OnPage;
  };
  /** The presses go through the arbiter (DE-014); nothing here can send a command (UI-INP-006). */
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FInput InInput);
  /** A key while open: Esc / I close, Tab switches the language (both scans), Backspace returns to the grid. Returns
   *  true for every key while open (the modal owns the keyboard). */
  bool HandleKey(const FKey& Key);

  // ---- the deck grid ----
  /** Opens the grid card Index in the same modal (deck card) / back to the grid. */
  void OpenDeckCard(int32 Index);
  void BackToGrid();
  /** One wheel notch: a row up (bUp) or down; false at the end. */
  bool WheelStep(bool bUp);
  int32 GetFirstRow() const { return FirstRow; }
  int32 GetGridCellCount() const { return GridCells.Num(); }
  /** The grid card / chip of cell I (tests). */
  UUmCardWidget* GetGridCard(int32 I) const;
  FString GetGridChipText(int32 I) const;

  // ---- the language ----
  /** Both scans of the card in the registry (the toggle is shown). */
  bool CanToggleLang() const;
  void ToggleLang();
  /** The face and the name shown in English (the EN build, or Tab in the RU build). */
  bool IsEnglish() const;

  // ---- what is shown (tests, the sheet) ----
  FString GetTitle() const;
  FString GetTypeText() const;
  FString GetValueText() const;
  FString GetBoostText() const;
  FString GetBodyText() const;
  FString GetCopiesText() const;
  bool IsLoadingScan() const;
  bool IsArtMissing() const;
  float GetContentAlpha() const { return ContentAlphaNow; }
  /** The card rect (modal-relative su) the slot gives the card widget. */
  FBox2D CardBoxSu() const;
  virtual void CollectShotLines(TArray<FString>& Out) const override;
  /** Tests / the review sheet: every card of the inspector (the main one and the grid pool) loads synchronously, and
   *  the widget clocks are frozen at Ms (< 0 = the platform clock). */
  void SetSyncLoadForSheet(bool bOn);
  void SetSheetClockMs(double Ms);
  /** Tests / the sheet: a press of Id (hud.inspect.close | .back | .grid.<i>) through the arbiter, as the mouse does. */
  void SimulatePressForTest(FName Id);
  /** Steps the content switch and the screen state at the widget clock (the tick does it while shown). */
  void StepInspect();

  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmCardWidget> Card;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> TitleText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<US08AnimatedIconWidget> TypeIcon;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> TypeText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> ValueText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> BoostText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UScrollBox> BodyText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UTextBlock> CopiesText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UHorizontalBox> LangToggle;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> CloseButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUniformGridPanel> DeckGrid;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidget)) TObjectPtr<UUmButton> BackButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UCanvasPanel> Content;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UHorizontalBox> TypeRow;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UBorder> CopiesChip;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> CopiesChipText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UVerticalBox> Column;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> BodyLine;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> ArtMissingText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UBorder> LangKey;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> LangKeyText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> LangText;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UScrollBox> DeckScroll;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UImage> Track;
  UPROPERTY(BlueprintReadOnly, Category = "Um Screen", meta = (BindWidgetOptional)) TObjectPtr<UImage> Thumb;

 protected:
  virtual void BuildContent() override;
  virtual void OnVeilClick() override { Close(TEXT("outside")); }
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;
  virtual FReply NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual FReply NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual FReply NativeOnMouseWheel(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;

 private:
  static bool AttachContent(UWidgetTree& Tree, UPanelWidget* Parent, FS08AttachWidget Attach, FString* OutError);
  void BindParts();
  void LayoutContent();
  void ApplyCardView();
  void ApplyDeckGrid();
  void ApplyScrollbar();
  void StartSwitch();
  void UpdateShotState();
  void OnPressOutcome(FName Id, const FS09HudPressOutcome& Outcome);
  FS09CardView ShownCard() const;
  struct FGridCell {
    TObjectPtr<UUmCardWidget> Card;
    TObjectPtr<UBorder> Chip;
    TObjectPtr<UTextBlock> ChipText;
    TObjectPtr<UWidget> Cell;
  };
  void EnsureGridCells(int32 N);
  FUmInspectModel Model;
  bool bHasModel = false;
  bool bAltLang = false;
  bool bSheetSync = false;
  double SheetClockMs = -1.0;
  bool bClosing = false;
  int32 FirstRow = 0;
  double SwitchStartMs = -1.0;
  float ContentAlphaNow = 1.0f;
  TArray<FGridCell> GridCells;
  UPROPERTY(Transient) TArray<TObjectPtr<UWidget>> GridKeep;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FInput Input;
};

// VS-4 HB-35 (docs/game-design/visual/06-tasks/hud.csv HB-35; 04-hud-spec.md §2.8, §3.1, §3.4, §4.3, §5.2 step H10,
// §7.1; the accepted mockup HB-34 art/imagegen/hud-pending-v1-codex, ВР-VS2-HB34-01...19, ВР-HB11, ВР-HB12) with the
// forms of HB-36 the step needs (the Slate command panel leaves the default view, so every deferred choice is drawn
// here): UUmHudPending (/Game/S08/UI/Hud/WBP_UI_HUD_PENDING) - the deferred choice at CENTER (centre, y 80 su, S 64;
// never above the STATUS bottom + 8 su, under a shown combat centre + 8 su).
//
//   modal      the first open of a choice that is not made on the board - DECK_TOP_PICK, CHOOSE_ONE, the number ▲▼, an
//              unknown type: 640 su (720p 640, class S 560) x <= 420 (720p 380, S 360) su, panel.bg 1.0 (skin modal),
//              edge state.pending 2 su, radius 8, padding 16. Header: the source card's name (type.title 28, data) and
//              the queue chip «ещё {k}»; the body scrolls (4 su bar) - the effect text (type.body) and the variants:
//                DECK_TOP_PICK PICK  the revealed cards as scans 150 x 208 (S 120 x 166) in CP-13 hand frames, a click
//                                    marks (CP-17 selected, raised 16 su, ВР-VS2-HB34-19), the counter «Выбрано {k}/{n}»;
//                DECK_TOP_PICK ORDER only the cards to order, centred, a click puts the next number on a 24 su chip
//                                    (card.glyph, keyline 1 su, font.card 20 su card.navy) 28 su over the card;
//                CHOOSE_ONE          the options as full-width buttons 40 su (selected = the button's selected state);
//                number              UUmNumberPicker (no MVP card has it, ВР-HB11: tests and the review sheet only).
//              Footer (always visible, 16 su under the body): «Назад» (a CHOOSE_ONE option or a number is picked), «Отказаться
//              (X)» (optional only), «Подтвердить» (the one primary; refuses with why.pick.count until the pick is
//              complete) and «Свернуть (C)».
//   compact    a choice made on the board (MOVE, PLACE, TARGET_FIGHTER, CHOOSE_SPACE), a hand pick (BOOST_CHOICE), a
//              discard (DISCARD_CARDS and the hand limit), King Arthur's «Добавить BOOST?» (SD-56): class L 720 x 56..60 su
//              in two rows (the glyph state-pending-move / -place 24 su, the card name type.heading 24, the queue chip;
//              the hint type.body 16) with the buttons right; class S one row up to 720 su in the free band SLOT + 8 ...
//              PANEL-OPP / OPP-HAND - 8, the hint stays in STATUS (ВР-VS2-HB34-13); BOOST - only its two buttons
//              (ВР-VS2-HB34-14). panel.bg 0.92 + edge state.pending 2 su. A text that does not fit wraps to another row,
//              the plate grows - never cut.
//   collapsed  after «Свернуть»: the plate 320 x 44 su «{card}: выбор ждёт» + key chip C at the compact's place (the
//              width grows with the text); a click or C expands. Collapsing never cancels the choice.
//   toast      a repeating optional trigger (FS09PendingPresenter::Toast): 560 x 48 su (720p 520, S 440) at the toast
//              place of the stack rule (over the hand caption, or the top band when it would cross a figure - the owner
//              computes it, ВР-H06): the source (bold) and «В прошлый раз: {choice}», key chips Enter, X, C; a click
//              opens the full choice (as C). HB-40 moves it into UUmToastStack.
//   opp        the opponent's choice: grey compact (panel.bg 0.92 + panel.edge 1 su, text.secondary, no buttons) - the
//              source card's name and «Соперник делает выбор» (why.wait.opponent.choice) unless STATUS already says it
//              (one text once, ВР-VS2-HB34-12); width = text + 2 x 16, at least 320 su.
//   after-combat my choice waits for the combat staging: grey compact «{card}» / «Выполните после боя».
// No form opens over a choice on the board: a board type is never a modal (the modal of 04 §2.8 «сворачивается»). While
// the opponent's scheme holds its effect (F-10, FS09SourceSlot) my choice it opened waits hidden.
// Input: every button through the HUD arbiter (DE-014: the answer in the frame of the release, CUE-004 with the why.* of
// a refused one); a card of the modal: left click = mark / order, right click = the inspector; keys stay the game
// mode's (C, X, N, Enter, Esc - Esc = «Назад» or why.choice.required for a mandatory choice).
// Rollback: -S08SlateHud=pending - the Slate command panel blocks of RefreshHud, nothing of this widget is built.
// SHOT: 'SHOT widget id=UI-HUD-PENDING impl=umg state=modal|compact|collapsed|toast|opp fighter=none bbox=... kind=<type>
//        body=text|options|pick|order|number|- tone=own|grey wait=-|combat queue=<k> pick=<have>/<need> buttons=<list>
//        scroll=<su> class=L|S' - no card name, no text, no card id (the published traces stay reveal-free).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudModel.h"
#include "../../S09/S09HudPress.h"
#include "../S08ArtHudWidgets.h"
#include "UmNumberPicker.h"
#include "UmHudPending.generated.h"

class UBorder;
class UCanvasPanel;
class UImage;
class UScrollBox;
class USizeBox;
class UTextBlock;
class UUmButton;
class UVerticalBox;
class UUmCardWidget;
class US08AnimatedIconWidget;
class FS09CommandUi;
class FS09PendingPresenter;
struct FS08PendingEffect;

enum class EUmPendingView : uint8 { Hidden, Modal, Compact, Collapsed, Toast, Opp, AfterCombat };
enum class EUmPendingBody : uint8 { Text, Options, Pick, Order, Number };
enum class EUmPendingCompact : uint8 { Board, HandPick, Discard, Boost };

/** One revealed card of DECK_TOP_PICK. */
struct UNMATCHED_API FUmPendingCard {
  FS09CardView Card;
  bool bMarked = false;  // PICK: taken into the hand
  int32 Order = 0;       // ORDER: 1.. in the pick sequence, 0 = not ordered yet
  bool operator==(const FUmPendingCard& O) const {
    return Card.InstanceId == O.Card.InstanceId && Card.Name == O.Card.Name && bMarked == O.bMarked && Order == O.Order;
  }
};

/** What the block shows (UmHudPending::Gather builds it; the texts are resolved already - data or string tables). */
struct UNMATCHED_API FUmPendingModel {
  EUmPendingView View = EUmPendingView::Hidden;
  EUmPendingBody Body = EUmPendingBody::Text;
  EUmPendingCompact Compact = EUmPendingCompact::Board;
  /** The trace kind: the pending type, LIMIT (the hand limit) or ABILITY (King Arthur's BOOST, SD-56). */
  FString Kind;
  FString HeadId;
  /** The source card's / hero's name (data; '' = unknown - the header is left out). */
  FString Title;
  /** modal: the effect text; compact: the hint; toast: the remembered line; grey: its line; collapsed: the plate text. */
  FString Text;
  /** The compact glyph (state-pending-move / -place) or none. */
  FName Icon;
  int32 QueueMore = 0;
  TArray<FString> Options;
  int32 Selected = -1;
  TArray<FUmPendingCard> Cards;
  /** The deck owner's hero slug (the scans of the revealed cards). */
  FString HeroSlug;
  int32 PickNeed = 0;
  int32 PickHave = 0;
  FUmNumberModel Number;
  // ---- buttons (an unset reason = enabled; BusyWhy refuses every one while a command is in flight) ----
  bool bConfirm = false;
  FString ConfirmKey;   // hud.number.confirm / ms.btn.boost.attack
  FS09Reason ConfirmWhy;
  bool bSecondary = false;
  FString SecondaryKey;  // ms.btn.noboost
  bool bStay = false;
  bool bDecline = false;
  bool bBack = false;
  bool bCollapse = false;
  FS09Reason BusyWhy;
  bool operator==(const FUmPendingModel& O) const;
  bool operator!=(const FUmPendingModel& O) const { return !(*this == O); }
};

/** The layout event of the block (canvas su, FUmHudLayout + the live tops). */
struct UNMATCHED_API FUmPendingFrame {
  bool bClassS = false;
  float PxPerSu = 1.0f;
  FVector2D CanvasSu = FVector2D(1920.0, 1080.0);
  /** CENTER y (80 / S 64), pushed under a shown STATUS (+ 8) and a shown combat centre (+ 8). */
  float TopSu = 80.0f;
  float ModalWidthSu = 640.0f;
  float ModalCapSu = 420.0f;
  /** Class S: the free band of the one-row compact (SLOT right + 8 ... PANEL-OPP / OPP-HAND left - 8). */
  float BandLeftSu = 0.0f;
  float BandRightSu = 0.0f;
  /** The toast plate (the stack rule of the owner, ВР-H06); invalid = over the hand caption. */
  FBox2D ToastSu = FBox2D(ForceInit);
  bool operator==(const FUmPendingFrame& O) const {
    return bClassS == O.bClassS && PxPerSu == O.PxPerSu && CanvasSu == O.CanvasSu && TopSu == O.TopSu &&
           ModalWidthSu == O.ModalWidthSu && ModalCapSu == O.ModalCapSu && BandLeftSu == O.BandLeftSu &&
           BandRightSu == O.BandRightSu && ToastSu == O.ToastSu;
  }
  bool operator!=(const FUmPendingFrame& O) const { return !(*this == O); }
};

/** Where every part of a form goes (canvas su) - world-free, the tests check the numbers. */
struct UNMATCHED_API FUmPendingPlan {
  FBox2D Panel = FBox2D(ForceInit);
  FBox2D Icon = FBox2D(ForceInit);
  FBox2D Title = FBox2D(ForceInit);
  int32 TitleRows = 0;
  FBox2D Queue = FBox2D(ForceInit);
  FBox2D Hint = FBox2D(ForceInit);
  int32 HintRows = 0;
  /** modal: the body viewport, the height of its content and how much of it scrolls. */
  FBox2D BodyView = FBox2D(ForceInit);
  float BodyTextSu = 0.0f;
  float ContentSu = 0.0f;
  float ScrollSu = 0.0f;
  FBox2D Counter = FBox2D(ForceInit);
  /** The buttons by name (Back, Decline, Stay, Confirm, Secondary, Collapse, Expand), in drawing order. */
  TArray<TPair<FName, FBox2D>> Buttons;
  /** toast / collapsed key chips (Enter, X, C). */
  TArray<TPair<FString, FBox2D>> Keys;
  /** modal cards (content su of the body: x from the body's left, y from its top). */
  TArray<FBox2D> Cards;
  TArray<FBox2D> Chips;
  FBox2D Find(FName Button) const;
};

namespace UmHudPending {
inline constexpr float ModalPadSu = 16.0f;
inline constexpr float ModalTitleSu = 28.0f;
inline constexpr float BodyTopSu = 48.0f;
inline constexpr float FooterSu = 56.0f;
inline constexpr float FooterGapSu = 16.0f;
inline constexpr float ButtonHSu = 40.0f;
inline constexpr float ButtonGapSu = 8.0f;
inline constexpr float BodyLineSu = 20.0f;   // type.body 16 su in rows of 20
inline constexpr float TitleLineSu = 28.0f;  // type.heading 24 su in rows of 28
inline constexpr float CardRaiseSu = 16.0f;  // ВР-VS2-HB34-19
inline constexpr float OrderChipSu = 24.0f;
inline constexpr float CompactLSu = 720.0f;
inline constexpr float CompactSMinSu = 560.0f;
inline constexpr float CompactMinHSu = 56.0f;
inline constexpr float GreyMinSu = 320.0f;   // ВР-VS2-HB34-15
inline constexpr float CollapsedWSu = 320.0f;
inline constexpr float CollapsedHSu = 44.0f;
inline constexpr float ToastHSu = 48.0f;
inline constexpr float ScrollBarSu = 4.0f;
/** Measured text + this before it may wrap (the drawn glyphs round per pixel; never cut, HB-34 P11). */
inline constexpr float TextSlackSu = 6.0f;
inline constexpr int32 MaxCards = 4;
inline constexpr int32 MaxOptions = 6;

UNMATCHED_API const TCHAR* ViewName(EUmPendingView View);
UNMATCHED_API const TCHAR* BodyName(EUmPendingBody Body);
/** The toast plate width of a canvas: 560 (L, height >= 1000), 520 (L short), 440 (S). */
UNMATCHED_API float ToastWidthSu(bool bClassS, bool bTall);

/** Text width (su) of one line at the em SizeSu of a theme type token. */
using FMeasure = TFunctionRef<float(const FString& Text, float SizeSu, FName Token)>;
/** One line of Text at the em SizeSu of a theme type token, as drawn at PxPerSu (DPI x UI scale) - su. */
UNMATCHED_API float MeasureAtSu(const FString& Text, float SizeSu, FName Token, float PxPerSu);
/** The width of a 40 su button with this label (caps, 2 x 16 su padding, at least 120 su). */
UNMATCHED_API float ButtonWidthSu(const FString& Label, FMeasure Measure);
/** The plan of a model on a frame; Labels: the button labels by name (as drawn). */
UNMATCHED_API FUmPendingPlan Plan(const FUmPendingModel& Model, const FUmPendingFrame& Frame,
                                  const TMap<FName, FString>& Labels, FMeasure Measure);

/** The source of a deferred choice from its effect id: "<catalog card id>-<field>-<i>-p<n>", "discard-choice-<effect
 *  id>-<seq>", "<effect id>-boost-<seq>" -> the catalog card (Known: the deck lists' cards, the hand and the piles,
 *  the longest id that prefixes it); "ability-<hero>-..." -> the owner's hero (HeroNames: player id -> name). Without
 *  a match the owner's newest discard card whose text holds the head's text (S09OpponentView::EffectCardName); ''
 *  when nothing is known. The name of the UI language (nameRu when bRu and the data has it). */
UNMATCHED_API FString SourceName(const FS08PendingEffect& Head, const TArray<FS09CardView>& Known,
                                 const TMap<FString, FString>& HeroNames, const TArray<FS09CardView>& OwnerDiscard, bool bRu,
                                 FString* OutText = nullptr);
/** The first sentence of a printed text, verbatim (CHOOSE_SPACE hint, ВР-VS2-HB34-12). */
UNMATCHED_API FString FirstSentence(const FString& Text);

/** One gather (the game mode fills it from the applied snapshot, the command state and the board). */
struct UNMATCHED_API FUmPendingInput {
  bool bLive = false;
  FString ViewerId;
  const FS09CommandUi* Ui = nullptr;
  const FS09PendingPresenter* Presenter = nullptr;
  /** The combat staging runs: my choice waits «после боя». */
  bool bCombatStaging = false;
  /** The opponent's scheme holds its effect (F-10): my choice it opened waits hidden. */
  bool bHeldBySlot = false;
  /** The STATUS line already reads why.wait.opponent.choice (the UMG STATUS is shown). */
  bool bStatusSaysOpp = true;
  FS09Reason BusyWhy;
  bool bRu = true;
  TArray<FS09CardView> Known;
  TMap<FString, FString> HeroNames;
  /** The discard pile of the head's owner (oldest first) - the text fallback of SourceName. */
  TArray<FS09CardView> OwnerDiscard;
  FString OwnHeroSlug;
  // ---- board / snapshot bits of the game mode ----
  FS09Reason MovePrompt;       // ms.pending.move / .place (DescribePendingMovePlace)
  bool bCanStay = false;       // «Оставить на месте» (MOVE)
  FString RememberedChoice;    // the toast's {choice}: a fighter, a space, an option
  int32 PickNeed = 0;          // PendingCardPickPlan
  TArray<FS09CardView> Revealed;  // DECK_TOP_PICK (the owner's projection)
};
UNMATCHED_API FUmPendingModel Gather(const FUmPendingInput& In);
}  // namespace UmHudPending

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmHudPending : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Hud/WBP_UI_HUD_PENDING
  static UClass* WidgetClass();

  struct FCallbacks {
    TFunction<void(const FS09HudPressOutcome&)> OnConfirm;
    TFunction<void(const FS09HudPressOutcome&)> OnSecondary;
    TFunction<void(const FS09HudPressOutcome&)> OnStay;
    TFunction<void(const FS09HudPressOutcome&)> OnDecline;
    TFunction<void(const FS09HudPressOutcome&)> OnBack;
    /** «Свернуть», the collapsed plate and the toast: the presenter's C. */
    TFunction<void(const FS09HudPressOutcome&)> OnToggle;
    TFunction<void(const FS09HudPressOutcome&, int32)> OnOption;
    TFunction<void(const FS09HudPressOutcome&, const FString&)> OnCard;
    TFunction<void(const FS09HudPressOutcome&, int32)> OnStep;
    TFunction<void(const FS09CardView&)> OnInspect;
  };

  virtual bool Initialize() override;
  /** Canvas "Root" > Panel, Edge, ExpandButton, Header (HeaderIcon, SourceName, QueueChip > QueueText), Hint, Body
   *  (scroll) > BodyBox > BodyCanvas (BodyText, Options (vertical) > Option0..5, Picker, Card0..3, OrderChip0..3 > OrderText0..3),
   *  ScrollTrack, Counter, BackButton, DeclineButton, StayButton, ConfirmButton, SecondaryButton, CollapseButton,
   *  KeyChip0..2 > KeyText0..2. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  FString WidgetSourceName() const;

  void SetFrame(const FUmPendingFrame& InFrame);
  const FUmPendingFrame& GetFrame() const { return Frame; }
  /** The one data input (П1). Same model and frame = no work; a new step rebuilds the parts (pools, no new widget). */
  void ApplyModel(const FUmPendingModel& InModel);
  const FUmPendingModel& GetModel() const { return Model; }
  const FUmPendingPlan& GetPlan() const { return PlanNow; }
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, FCallbacks InCallbacks);
  /** The drawn panel (canvas su); invalid when hidden. */
  FBox2D PanelRectSu() const;
  bool IsShown() const { return Model.View != EUmPendingView::Hidden; }
  void CollectShotLines(TArray<FString>& Out) const;
  /** 'HUD-PENDING view=.. kind=.. head=.. ...' when the form changed since the last call ('' otherwise). */
  FString TakeChangeLine();
  /** Tests / the review sheet: load the card scans synchronously, freeze the clock of the cards. */
  void SetSyncLoad(bool bOn);
  void SetClockOverrideMs(double Ms);
  /** The labels drawn now by button name (tests). */
  const TMap<FName, FString>& GetLabels() const { return LabelsNow; }
  UUmCardWidget* GetCard(int32 Index) const;
  UUmButton* GetOption(int32 Index) const;

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UCanvasPanel> Header;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> SourceName;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UScrollBox> Body;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UVerticalBox> Options;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmNumberPicker> Picker;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> CollapseButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> BackButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> DeclineButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UBorder> QueueChip;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UCanvasPanel> Root;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UBorder> Panel;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UImage> Edge;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UUmButton> ExpandButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<US08AnimatedIconWidget> HeaderIcon;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> QueueText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> Hint;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<USizeBox> BodyBox;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UCanvasPanel> BodyCanvas;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> BodyText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> Counter;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UUmButton> StayButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UUmButton> ConfirmButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UUmButton> SecondaryButton;

 private:
  void Relayout();
  void ApplyCards();
  void ApplyButtons();
  FName PanelSkin() const;

  FUmPendingFrame Frame;
  bool bHasFrame = false;
  FUmPendingModel Model;
  bool bHasModel = false;
  bool bCodeDefaultTree = false;
  FUmPendingPlan PlanNow;
  TMap<FName, FString> LabelsNow;
  UPROPERTY() TArray<TObjectPtr<UUmButton>> OptionPool;
  UPROPERTY() TArray<TObjectPtr<UUmCardWidget>> CardPool;
  UPROPERTY() TArray<TObjectPtr<UBorder>> ChipPool;
  UPROPERTY() TArray<TObjectPtr<UTextBlock>> ChipText;
  UPROPERTY() TArray<TObjectPtr<UBorder>> KeyPool;
  UPROPERTY() TArray<TObjectPtr<UTextBlock>> KeyText;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FCallbacks Callbacks;
  FString LastChangeKey;
  bool bChangePending = false;
};

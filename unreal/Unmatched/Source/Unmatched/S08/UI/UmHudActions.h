// VS-4 HB-43 (docs/game-design/visual/06-tasks/hud.csv HB-43; 04-hud-spec.md §2.14, §2.11, §3.1, §3.4, §4.3, §5.2 step H6,
// §7.1; ВР-39, ВР-H08, ВР-H09; accepted mockup HB-42 art/imagegen/hud-actions-v1-codex, ВР-VS2-HB42-01...20): ACTIONS -
// UUmHudActions (/Game/S08/UI/Hud/WBP_UI_HUD_ACTIONS), the maneuver, attack, scheme and end-of-turn buttons.
//
//   cells    four UUmButton (Disc variant, the HB-08 skins of HB-42) in the ACTIONS rect, no common panel - the 8 su gaps
//            show the scene: class L МАНЁВР, АТАКА, СХЕМА 78 x 72 su and КОНЕЦ ХОДА 86 x 72 su (ВР-VS2-HB42-12), the disc
//            48 su at y + 4, the captions (hud.action.*, type.tag caps) on one baseline y + 67 su (ВР-VS2-HB42-13);
//            class S four 48 x 48 su cells, the disc 40 su at (+4, +4), no caption (the tooltip carries it, A9).
//   discs    the v3 action-maneuver, action-attack, action-scheme and action-end-turn (IC-46) icons; disabled at
//            state.disabled.opacity 0.4 with the caption text.secondary (02 §4.3, never a lowered text alpha).
//   rules    UmHudActions::Decide (world-free, ВР-VS2-HB42-05 and the client guards of FS09CommandUi): the opponent's
//            turn - all four disabled with why.not.your.turn; a command in flight - all four with its reason; an open
//            maneuver draft - МАНЁВР selected, the other three why.draft.open; the end-of-turn discard - the actions
//            why.no.actions, КОНЕЦ ХОДА why.discard.count; 0 actions - the actions why.no.actions; КОНЕЦ ХОДА is the
//            primary cell (BtnPrimary_*, caption card.navy) only while CommandUi.EndTurnReason() is empty, otherwise an
//            ordinary Btn_Disabled cell with that reason (SD-44) - never two primaries; an attack / scheme draft selects
//            its button and keeps the other two actions available (the mode switch, ВР-VS4-41).
//   tooltip  the HB-22 plate of HB-42 A7 (panel.bg, panel.edge 1 su, radius.s, 16 su side padding, 44 su for one line + 24
//            su per further line, max 360 su in L / 300 su in S, word wrap, never cut): bottom = the row top - 8 su, the
//            right edge = the pointed cell's, kept inside the canvas side margin. Class L: the why.* of a disabled
//            button after 300 ms of hover (04 §3.1). Class S: the caption (type.tag caps) on hover or focus, the why.*
//            under it for a disabled button, the key chip 8 su right of the caption while key hints show (A8 / A9).
//   keys     UI-ACC-017 (04 §2.11, ВР-H09): the chips M, A, G, E (hud.key.*) 20 x 20 su in the cells' top-right corner in
//            class L (2 su in), in the tooltip in class S; the owner decides the mode (US08UserSettings::KeyHintsNow).
//   input    a click is the key's command (DE-015): the owner maps EUmActionKey to M / A / G / E. The press is the
//            arbiter's (DE-014): a disabled cell answers Refused with its why.* (CUE-004), never silence.
//   rollback -S08SlateHud=actions: the Slate buttons «BEGIN MANEUVER (M)» / «END TURN (E)» of the command panel.
// SHOT: 'SHOT widget id=UI-HUD-ACTIONS impl=umg state=own|opp|mode=maneuver|attack|scheme ... class=L|S actions=<n>
//        primary=end|none keys=0|1 cells=<w>x<h>,.. buttons=<key>:<state>[:<why>],.. tip=<key|none> tipRect=(..)'.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudPress.h"
#include "../../S09/S09ManeuverUi.h"
#include "../S08ArtHudWidgets.h"
#include "UmButton.h"
#include "UmHudActions.generated.h"

class UBorder;
class UCanvasPanel;
class UHorizontalBox;
class USizeBox;
class UTextBlock;
class UVerticalBox;

/** The four buttons, left to right (04 §2.14). */
enum class EUmActionKey : uint8 { Maneuver, Attack, Scheme, EndTurn, Num };
constexpr int32 UmActionCount = static_cast<int32>(EUmActionKey::Num);

/** What decides the row (the applied snapshot and the command state of the owner). */
struct UNMATCHED_API FUmActionsInput {
  /** The live match HUD (not the result screen, not an aborted room). */
  bool bShow = false;
  bool bViewerTurn = false;
  /** metadata.actionsRemaining of the snapshot; -1 = unknown. */
  int32 ActionsRemaining = -1;
  ES09CommandMode Mode = ES09CommandMode::None;
  /** The server holds a maneuver of the viewer (the draft is open on the server). */
  bool bManeuverPending = false;
  /** HudBusyReason: a command in flight (why.syncing). */
  FS09Reason Busy;
  /** CanBeginManeuver's refusal (none = a maneuver may begin): the pending choice, the phase, the game over. */
  FS09Reason BeginRefusal;
  /** CommandUi.EndTurnReason(): none = the end of turn is open. */
  FS09Reason EndTurn;
  /** A combat window is open (the attacker waits for the defender). */
  bool bCombat = false;
  /** No scheme of the hand is playable by a living fighter (PlaySchemeCommand refuses): СХЕМА why.scheme.none. */
  bool bNoScheme = false;
  /** UI-ACC-017 shows the key chips. */
  bool bKeyHints = false;
  /** Keyboard navigation focus (04 §3.4): the focused button, INDEX_NONE = none. */
  int32 FocusIndex = INDEX_NONE;
};

/** The decided row: one button model per key, the SHOT state. */
struct UNMATCHED_API FUmActionsModel {
  bool bShow = false;
  FString State;  // own | opp | mode=maneuver | mode=attack | mode=scheme
  FUmButtonModel Buttons[UmActionCount];
  bool bKeyHints = false;
  int32 ActionsRemaining = -1;
  bool operator==(const FUmActionsModel& O) const;
  bool operator!=(const FUmActionsModel& O) const { return !(*this == O); }
};

/** The layout event: the class, px per su, the ACTIONS rect and the canvas (su). */
struct UNMATCHED_API FUmActionsFrame {
  bool bClassS = false;
  float PxPerSu = 1.0f;
  FBox2D RectSu = FBox2D(ForceInit);
  FVector2D CanvasSu = FVector2D::ZeroVector;
  float MarginSu = 24.0f;
  bool operator==(const FUmActionsFrame& O) const {
    return bClassS == O.bClassS && PxPerSu == O.PxPerSu && RectSu == O.RectSu && CanvasSu == O.CanvasSu && MarginSu == O.MarginSu;
  }
};

namespace UmHudActions {
inline constexpr float CellHSu = 72.0f;      // class L
inline constexpr float CellSSu = 48.0f;      // class S (square)
inline constexpr float GapSu = 8.0f;
inline constexpr float DiscLSu = 48.0f;
inline constexpr float DiscSSu = 40.0f;
inline constexpr float TipGapSu = 8.0f;      // the tooltip's bottom = the row top - 8 su (A7)
inline constexpr float TipPadSu = 16.0f;     // side padding
inline constexpr float TipLineSu = 44.0f;    // one line; + TipMoreSu per further line
inline constexpr float TipMoreSu = 24.0f;
inline constexpr float TipMaxLSu = 360.0f;
inline constexpr float TipMaxSSu = 300.0f;
inline constexpr float TipChipGapSu = 8.0f;  // the class S chip right of the caption
inline constexpr float TipSlackSu = 2.0f;    // the measured line + 2 su: never a wrap at the last glyph
inline constexpr double TipDelaySec = 0.3;   // 04 §3.1
/** "maneuver" / "attack" / "scheme" / "end" (trace, ids). */
UNMATCHED_API const TCHAR* KeyName(EUmActionKey Key);
/** The press id of the arbiter (hud.begin.maneuver, hud.begin.attack, hud.begin.scheme, hud.end.turn - the Slate ids). */
UNMATCHED_API FName PressId(EUmActionKey Key);
/** The v3 icon of the disc. */
UNMATCHED_API FName IconName(EUmActionKey Key);
/** hud.action.* (the caption) and hud.key.* (the chip letter). */
UNMATCHED_API FText Caption(EUmActionKey Key);
UNMATCHED_API FText KeyLetter(EUmActionKey Key);
/** The cell width (su): class L 78 / 78 / 78 / 86 (ВР-VS2-HB42-12), class S 48. */
UNMATCHED_API float CellWidthSu(EUmActionKey Key, bool bClassS);
/** The cell rect relative to the block's top-left (su). */
UNMATCHED_API FBox2D CellLocalSu(EUmActionKey Key, bool bClassS);
/** The row (ВР-VS2-HB42-05, see the file comment). */
UNMATCHED_API FUmActionsModel Decide(const FUmActionsInput& In);
/** The why text of a disabled button (ST_Why, formatted with its arguments). */
UNMATCHED_API FText WhyText(const FS09Reason& Reason);
}  // namespace UmHudActions

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmHudActions : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Hud/WBP_UI_HUD_ACTIONS
  static UClass* WidgetClass();

  virtual bool Initialize() override;
  /** CanvasPanel "Row" > Maneuver, Attack, Scheme, EndTurn (UUmButton) + Tip (UBorder) > TipBox (UVerticalBox) >
   *  TipHead (UHorizontalBox: TipCaption, TipKey > TipKeyText) + TipText. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  FString SourceName() const;

  /** The layout event (window / UI scale). */
  void SetFrame(const FUmActionsFrame& InFrame);
  const FUmActionsFrame& GetFrame() const { return Frame; }
  /** The one data input (П1). Same model = no work. */
  void ApplyModel(const FUmActionsModel& InModel);
  const FUmActionsModel& GetModel() const { return Model; }
  /** OnPress(outcome, key) answers a resolved press of a cell (the owner runs the key's command or CUE-004). */
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, TFunction<void(const FS09HudPressOutcome&, EUmActionKey)> InOnPress);
  void CollectShotLines(TArray<FString>& Out) const;
  UUmButton* GetButton(EUmActionKey Key) const;
  /** The cell rect in canvas su (the ACTIONS rect + the cell's offset). */
  FBox2D CellRectSu(EUmActionKey Key) const;
  /** The tooltip shown now: its key (Num = none) and rect (canvas su). */
  EUmActionKey GetTipKey() const { return TipFor; }
  FBox2D TipRectSu() const { return TipRect; }
  FText GetTipText() const;
  /** Applies since the first model (tests: same model = no work). */
  int32 GetApplyCount() const { return ApplyCount; }

  // ---- tests, the review sheet and the flag step (the same paths as the mouse) ----
  void SetClockForTest(TFunction<double()> InClock);
  /** Hover a cell (INDEX_NONE: none) through UUmButton::SimulateHover. */
  void SimulatePointer(int32 Index);
  /** The sheet: the tooltip at once (no 300 ms) for a still frame. */
  void SetTipImmediateForTest(bool bOn) { bTipImmediate = bOn; }
  /** Runs the tooltip step without Slate. */
  void TickForTest() { StepTip(); }

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UCanvasPanel> Row;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> Maneuver;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> Attack;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> Scheme;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> EndTurn;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UBorder> Tip;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UVerticalBox> TipBox;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UHorizontalBox> TipHead;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> TipCaption;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UBorder> TipKey;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> TipKeyText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> TipText;

 protected:
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

 private:
  void Relayout();
  void ApplyButtons();
  void StepTip();
  void ShowTip(int32 Index);
  double Now() const;
  FUmActionsFrame Frame;
  bool bHasFrame = false;
  FUmActionsModel Model;
  bool bHasModel = false;
  bool bCodeDefaultTree = false;
  int32 ApplyCount = 0;
  TFunction<double()> Clock;
  int32 HoverIndex = INDEX_NONE;
  double HoverSince = -1.0;
  bool bTipImmediate = false;
  EUmActionKey TipFor = EUmActionKey::Num;
  FBox2D TipRect = FBox2D(ForceInit);
  FString TipSignature;
};

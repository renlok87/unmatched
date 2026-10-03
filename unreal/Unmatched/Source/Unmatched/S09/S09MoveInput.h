// MS-T-07 (move-selection 03 §3, 04 §6.2): the input semantics of move
// selection as pure logic over FS09CommandUi - headless-testable, no world.
// AS08FlowGameMode polls the keys and the mouse, picks the space under the
// cursor (a ray to the board plane) and the fighter actor hit, and feeds them
// here; the result says what to send and what to show. It owns only the input
// state the draft does not: the boost panel (MS-S-08) with its arrow cursor,
// the exhaustion prompt (MS-S-04) and the click-on-release pair (MS-R-34).
#pragma once

#include "CoreMinimal.h"
#include "S09ManeuverUi.h"

/** The keys of 03 §3.2 the move selection consumes (Ctrl / Shift folded in). */
enum class ES09MoveKey : uint8 {
  M,
  Enter,
  Escape,
  Backspace,
  CtrlZ,
  Delete,
  Tab,
  ShiftTab,
  B,
  Left,
  Right,
  CtrlUp,
  CtrlDown,
  E,
};

/** What the game mode knows that the draft does not. */
struct UNMATCHED_API FS09InputView {
  bool bDiscardBrowserOpen = false; // D: public discard browser
  bool bInspectorOpen = false;      // I: card inspector
  int32 OwnDeckCount = -1;          // own draw pile; < 0 unknown (no MS-S-04 prompt)
};

/** What the game mode does with one input. */
struct UNMATCHED_API FS09InputResult {
  bool bHandled = false;          // false: the caller's older bindings may take the input
  bool bBeginManeuver = false;    // send beginManeuver (draft-side gates passed)
  bool bConfirmManeuver = false;  // send Command (ConfirmManeuver passed)
  FS09ManeuverCommand Command;
  bool bCloseDiscardBrowser = false;
  bool bCloseInspector = false;
  bool bPauseUnavailable = false; // MS-E-99: Esc with nothing to close; no pause screen yet
  bool bSelectionChanged = false; // refresh the board highlight
  FS09Reason Toast;               // why.* / ms.* by key (CUE-004 for a refused space)
  FString ToastText;              // plain text when no key applies (shown only without Toast)
  float ToastSeconds = 3.0f;
  FIntPoint IllegalCell = FIntPoint(-1, -1); // V-08 ring on a refused space
};

/** One row of the bindings review list (MS-R-35, MS-AT-15): no binding needs a
 *  held key; every chord has a single-key alternative. */
struct UNMATCHED_API FS09KeyBinding {
  const TCHAR* Input;
  const TCHAR* Action;
  const TCHAR* Alternative; // empty for a single key
  bool bChord = false;
  bool bHold = false;
};

class UNMATCHED_API FS09MoveInput {
public:
  // ---- MS-S-08: the boost panel ----
  bool bBoostPanelOpen = false;
  int32 BoostCursor = 0; // index into FS09CommandUi::BoostOffers()
  // ---- MS-S-04: the exhaustion prompt ----
  bool bExhaustionOpen = false;
  int32 ExhaustionFighters = 0;
  // ---- MS-R-34: click on release ----
  bool bPressed = false;
  FIntPoint PressedCell = FIntPoint(-1, -1);
  FString PressedFighterId;
  FIntPoint HoverCell = FIntPoint(-1, -1);

  FS09InputResult OnKey(ES09MoveKey Key, FS09CommandUi& Ui, const FS08Snapshot& Snapshot,
                        const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                        const FS09InputView& View);
  /** Left button down over Cell (the board plane under the cursor, (-1,-1)
   *  off the board) with FighterId the fighter actor hit (empty: none). */
  void OnPointerPressed(const FIntPoint& Cell, const FString& FighterId);
  /** Left button up: a click only over the same space (or the same fighter)
   *  as the press; anything else cancels it (MS-R-34). */
  FS09InputResult OnPointerReleased(const FIntPoint& Cell, const FString& FighterId, FS09CommandUi& Ui,
                                    const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                                    const TArray<FS08BoardFighter>& Fighters);
  /** Right button: one step back like Esc, never the draft reset (03 §3.1). */
  FS09InputResult OnRightClick(FS09CommandUi& Ui, const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                               const TArray<FS08BoardFighter>& Fighters);
  /** Focus lost / cursor left the viewport: the press and the hover drop (MS-E-104). */
  void OnFocusLost();
  void SetHover(const FIntPoint& Cell) { HoverCell = Cell; }
  /** A completed click (MS-R-71 priority): (1) a space of the selected
   *  fighter's tiers (base or boost; its own space clears its move) gets the
   *  target even with a figure on it; (2) an own fighter (actor hit or
   *  standing on the space) is selected; (3) otherwise the space is judged. */
  FS09InputResult Click(const FIntPoint& Cell, const FString& FighterId, FS09CommandUi& Ui,
                        const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                        const TArray<FS08BoardFighter>& Fighters);
  /** Closes the prompts the fresh state made stale (a draft opened, the turn
   *  passed, the boost panel outside a draft). */
  void OnSnapshot(const FS09CommandUi& Ui, const FS08Snapshot& Snapshot);

  /** 03 §3.2 bindings of the move selection (the review list). */
  static const TArray<FS09KeyBinding>& Bindings();

  // ---- -S08Maneuver auto driver (MS-R-62, RK-13) ----
  /** One step for the viewer's hero (own, CanBeMover, not immobilized): the
   *  first board neighbour (Neighbours order) its move can end on. */
  static bool AutoManeuverTarget(const FS09CommandUi& Ui, const FS08BoardModel& Board,
                                 const TArray<FS08BoardFighter>& Fighters, FString& OutFighterId,
                                 FIntPoint& OutCell);
  /** The demo gate (S08FlowGameMode): begin (+1) and maneuver (+1) applied and
   *  the pendingManeuver closed. */
  static bool AutoManeuverSettled(int32 StartSeq, const FS08Snapshot& Snapshot);
  /** MS-R-32: the TASK-022 two-click quick move only with -S08LegacyQuickMove. */
  static bool LegacyQuickMoveEnabled();
  /** Board clicks and the move-selection keys of this mode go through
   *  FS09MoveInput (the draft; outside a draft unless the legacy flag is on). */
  static bool RoutesMoveSelection(ES09CommandMode Mode, bool bLegacyQuickMove);
  /** The TASK-022 tail of HandleClick (TryManeuverTo) may run: only with the
   *  flag and no command mode open - never from the scheme picker, a pending
   *  choice or any draft (MS-R-01, MS-R-32). */
  static bool LegacyQuickMoveReachable(ES09CommandMode Mode, bool bLegacyQuickMove);
  /** MS-S-04 needs the own draw pile: the last count ever received is good
   *  even when stale (WS events carry no decks and the pile never grows);
   *  -1 (no prompt) before any deck projection arrived. */
  static int32 DeckCountForPrompt(int32 DeckCount, bool bEverSeen) { return bEverSeen ? DeckCount : -1; }

private:
  FS09InputResult BeginRequest(FS09CommandUi& Ui, const FS08Snapshot& Snapshot,
                               const TArray<FS08BoardFighter>& Fighters, const FS09InputView& View);
  FS09InputResult StepBack(bool bRightMouse, FS09CommandUi& Ui, const FS08Snapshot& Snapshot,
                           const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                           const FS09InputView& View);
};

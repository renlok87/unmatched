// DE-023 (W-15 HUD; 01 F-07, F-12, D-DE-07, D-DE-12 and the review resolution pp. 6, 9; 02 SD-08, SD-25, SD-34, SD-35;
// 02-ux-ui-spec §4.3 "Ход и действия"; ICON-MOTION.md "Трекер действий: поведение игры"): the world-free models of the
// turn HUD that the persistent UMG portraits (S08/S08TurnPortraitWidget.h) play. Automation-tested
// (Unmatched.S09.TurnHud.*):
//   - FS09TurnCue: the turn ring and the "Your turn" banner (CUE-015). A new turn key (currentTurnPlayerId#turnCount)
//     starts the ring on the active player's portrait at BOTH sides - the flash of the whole rim 1000 ms, then the
//     smouldering rim to the end of the turn (the contract record plays it; reduced motion: a static rim). The banner
//     is shown on the own turn only, 600 ms, never blocks input (reduced motion: 100 ms, CUE-015 reduced shorten). The
//     first snapshot seen (join, reconnect) shows the ring at rest and no banner; GAME_OVER ends both.
//   - FS09TrackerMarks: the own tracker marks a slot spent in the frame the action is CHOSEN, before the server
//     answers (a local attack / scheme draft is open, or the choice was just sent - the latch), and gives it back on
//     cancel; the server marks (FS09ActionTracker, DE-022) take over when they arrive; a new turn resets in one frame.
//   - FS09HeartWatch: the shown hero HP of a portrait (the HUD fighters - the combat staging holds the HP until the
//     contact + 80 ms) -> the heart events damage / deplete / heal.
#pragma once

#include "CoreMinimal.h"

/** What the portraits play this frame for a turn change. */
struct UNMATCHED_API FS09TurnCueEvent {
  bool bChanged = false;    // a new turn key (or the first one seen)
  bool bInitial = false;    // the first turn seen in this match: the ring at rest, no flash, no banner
  bool bOwn = false;        // the viewer's turn
  bool bGameOver = false;   // the match ended: the ring leaves, no banner
  FString TurnPlayerId;
};

class UNMATCHED_API FS09TurnCue {
public:
  /** CUE-015 duration_ms (cue-table.json) - our decision (01 F-07): DE 2.2.1 has no banner. */
  static constexpr double BannerMs = 600.0;
  /** CUE-015 reduced_motion shorten max_ms. */
  static constexpr double BannerReducedMs = 100.0;
  /** Fade in / out of the banner inside its 600 ms (no scale, nothing moves the board). */
  static constexpr double BannerFadeInMs = 100.0;
  static constexpr double BannerFadeOutMs = 150.0;
  /** 01 F-07: the flash of the whole rim, then the smouldering rim (marker-turn-ring appear 1000 ms). */
  static constexpr double RingFlashMs = 1000.0;

  /** An applied snapshot. Returns the event of a turn change (bChanged false otherwise). */
  FS09TurnCueEvent OnApplied(const FString& TurnPlayerId, int32 TurnCount, const FString& ViewerId, bool bGameOver,
                             double NowMs, bool bReducedMotion);
  /** Banner opacity at NowMs (0 = hidden). */
  float BannerAlpha(double NowMs) const;
  bool IsBannerVisible(double NowMs) const { return BannerAlpha(NowMs) > 0.0f; }
  /** The banner length of the latest own turn start (0 = none: opponent's turn, initial, game over). */
  double BannerLengthMs() const { return bBanner ? BannerLength : 0.0; }
  bool IsOwnTurn() const { return bOwnTurn; }
  bool IsOpponentTurn() const { return bOpponentTurn; }
  bool IsGameOver() const { return bOver; }
  void Reset() { *this = FS09TurnCue(); }

private:
  FString TurnKey;
  bool bSeen = false;
  bool bOver = false;
  bool bOwnTurn = false;
  bool bOpponentTurn = false;
  bool bBanner = false;
  double BannerSinceMs = 0.0;
  double BannerLength = BannerMs;
};

/** The own tracker of the portrait: the server marks plus the action being chosen now (01 F-12 "в момент выбора"). */
class UNMATCHED_API FS09TrackerMarks {
public:
  /** Command deadline of the flow (FS08FlowController::CommandDeadlineSeconds): a choice the server never answered
   *  stops counting after this long. */
  static constexpr double LatchTimeoutMs = 10000.0;

  /** The choice was sent (beginManeuver / attack / scheme): the slot stays marked until the server's answer -
   *  ServerSpent grows, or a newer seq than AppliedSeq arrives (accepted or not), or the timeout, or a new turn. */
  void Choose(int32 ServerSpent, int32 AppliedSeq, double NowMs);
  /** An applied snapshot of the turn (TurnKey = currentTurnPlayerId#turnCount): a new key drops every local mark. */
  void OnApplied(const FString& TurnKey, int32 Seq, int32 ServerSpent);
  /** The slots shown spent: the server marks + 1 while a local draft is open (bDraftOpen: an attack draft or the
   *  scheme picker of the own turn) or the latch holds; never more than Slots. */
  int32 Shown(int32 ServerSpent, int32 Slots, bool bDraftOpen, double NowMs) const;
  bool IsLatched(double NowMs) const { return bLatched && NowMs - LatchSinceMs < LatchTimeoutMs; }
  void Reset() { *this = FS09TrackerMarks(); }

private:
  FString TurnKey;
  bool bLatched = false;
  int32 LatchBase = 0;
  int32 LatchSeq = 0;
  double LatchSinceMs = 0.0;
};

enum class ES09HeartEvent : uint8 { None, Damage, Deplete, Heal };

/** The hero heart of a portrait: HP changes of the SHOWN fighter (first sample: no event). */
class UNMATCHED_API FS09HeartWatch {
public:
  /** HP of the hero now (-1 = no hero on the board: nothing changes). */
  ES09HeartEvent Sample(const FString& HeroId, int32 Health);
  int32 GetHealth() const { return Health; }
  /** The hero last sampled (run I: the fallen heart of a hero no longer among the HUD fighters). */
  const FString& GetHeroId() const { return HeroId; }
  void Reset() { *this = FS09HeartWatch(); }

private:
  FString HeroId;
  int32 Health = -1;
};

namespace S09TurnHud {
UNMATCHED_API const TCHAR* HeartEventName(ES09HeartEvent Event);
/** The contract animation of a heart event on resource-hp-full (none for None). */
UNMATCHED_API FName HeartAnim(ES09HeartEvent Event);
/** "Ab Cd" -> "AC", "Medusa" -> "M": the monogram of the portrait disc (no portrait art yet, ICON-MOTION.md). */
UNMATCHED_API FString Monogram(const FString& Name);

/** Run E review (acceptance defect 2): the hand panel (the event feed, the status line, "YOUR HAND n/7" and the card
 *  chips) never slides under the portrait column at the bottom left. Slate units of the HUD canvas. */
constexpr float HandGutterSu = 12.0f;  // between the portrait column and the hand panel
constexpr float HandEdgeSu = 16.0f;    // the hand panel's gap to the right screen edge (and the left one, no column)
/** The hand panel's left edge: centred on the screen while that clears the column (ObstacleRightSu + gutter), else
 *  pushed right to the column's edge plus the gutter. ObstacleRightSu <= 0 (no portraits): centred, as before. */
UNMATCHED_API float HandPanelLeft(float CanvasWidthSu, float PanelWidthSu, float ObstacleRightSu);
/** The width the card chips may take before they wrap to a second row: from the column (or the left edge) to the
 *  right edge, minus the panel's own horizontal padding. */
UNMATCHED_API float HandStripWrap(float CanvasWidthSu, float ObstacleRightSu, float PanelPaddingSu);
}  // namespace S09TurnHud

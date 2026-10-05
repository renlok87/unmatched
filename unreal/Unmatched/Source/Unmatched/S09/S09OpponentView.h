// MS-T-17 (docs/game-design/move-selection 03 §2.2 MS-P-03, §4.2 V-14 / V-15, §7; 02 MS-E-73, MS-E-102, MS-E-103,
// MS-E-106; 04 §4.3, §9): what a player sees of the other side's turn, world-free and automation-tested
// (Unmatched.S09.MoveSel.OpponentView, MS-AT-26):
//   - the planning indicator "Opponent is planning a maneuver" (MS-S-11): metadata.pendingManeuver.playerId is the
//     opponent; the opponent's draft never reaches this client (the server keeps it), only the indicator does;
//   - the last-move highlight V-14 / V-15 of metadata.lastMovement (FS09LastMoveTracker): shown at the end of the move
//     animation (MS-P-01 / MS-P-02), or at once without an animation when the snapshot is the trail's own seq and no
//     move played (reconnect, seq gap - MS-E-102); it goes out by the ONE exit rule of MS-P-03 - the first applied
//     seq > lastMovement.seq in which fighter positions, the HP of any fighter or currentTurnPlayerId changed - with a
//     300 ms fade (instant with reduced motion); an opponent's beginManeuver (seq + 1, the hand only) keeps it
//     (MS-E-103);
//   - the event feed (FS09EventFeed): the three latest maneuver lines over the hand, by the ms.log.* templates; more
//     than three moves -> the first two + "and N more", the full list as the tooltip (MS-E-106);
//   - the edge arrow (MS-E-73, MS-R-31): the camera never moves for the opponent's move; an end of the path outside the
//     viewport gets an arrow at the screen edge pointing at it.
// The game mode (S08FlowGameMode) feeds it from the applied snapshots and draws it: the plates (S08MoveHighlight
// FS08MoveDraftInput::LastMove), the HUD lines and the arrow. Phase verb, action tracker, the opponent's effect on my
// fighter and the BOOSTED card are DE-022 (W-13).
#pragma once

#include "CoreMinimal.h"
#include "../S08/S08BoardModel.h"
#include "../S08/S08Contracts.h"
#include "../S08/S08MoveHighlight.h"

/** metadata.lastMovement (04 §4.3): every public field the opponent view uses. */
struct UNMATCHED_API FS09LastMovement {
  struct FMove {
    FString FighterId;
    bool bPlace = false;
    FIntPoint From = FIntPoint(-1, -1);
    TArray<FIntPoint> Path;  // without the start; PLACE: [target]
    FIntPoint Dest() const { return Path.Num() > 0 ? Path.Last() : From; }
  };
  bool bValid = false;
  int32 Seq = 0;
  FString PlayerId;
  FString Source;  // MANEUVER | EFFECT
  bool bBoost = false;
  FString BoostName;
  int32 BoostValue = 0;  // a null printed BOOST counts +0 until MS-T-20 (04 §4.3)
  TArray<FMove> Moves;   // in the order applied; a maneuver without movement: []

  /** False when the field is absent, null or has no seq / playerId (a save before MS-T-14, MS-E-108). An unreadable
   *  move entry (no fighter, no from, no path, PLACE with more than one cell) is dropped. */
  static bool Read(const TSharedPtr<FJsonValue>& Metadata, FS09LastMovement& Out);
};

/** What the MS-P-03 exit rule compares between two applied snapshots. */
struct UNMATCHED_API FS09BoardStamp {
  TMap<FString, FIntVector> Fighters;  // id -> (x, y, health)
  FString TurnPlayerId;
  bool bSet = false;
  static FS09BoardStamp Make(const TArray<FS08BoardFighter>& Fighters, const FString& TurnPlayerId);
  /** Fighter positions, the HP of any fighter or the active player differ (a fighter that appears / disappears too). */
  bool Differs(const FS09BoardStamp& Other) const;
};

enum class ES09LastMoveState : uint8 { None, Waiting, Shown, Fading };

/** The MS-P-03 state machine of the last-move highlight. Times are game-clock milliseconds. */
class UNMATCHED_API FS09LastMoveTracker {
public:
  /** 03 §6 "Затухание подсветки последнего хода". */
  static constexpr double FadeMs = 300.0;

  /** An applied snapshot (Apply or a same-seq Merge): the exit rule against the previous one, then a trail of exactly
   *  this seq enters (Waiting). Returns the 'MS-LAST ...' trace lines. */
  TArray<FString> OnApplied(int32 Seq, const FS09LastMovement& Trail, const FS09BoardStamp& Stamp, double NowMs,
                            bool bReducedMotion);
  /** The move animation of Seq ends at EndMs: the highlight waits for it (MS-P-01 / MS-P-02 -> MS-P-03). */
  void OnMoveAnimation(int32 Seq, double EndMs);
  /** Reveals a waiting highlight (no animation for its seq, the figures arrived - a skip too - or EndMs passed) and
   *  ends a fade. Returns trace lines. */
  TArray<FString> Tick(double NowMs, bool bAnyFigureMoving);
  /** 1 shown, 1 -> 0 over FadeMs while fading, 0 otherwise. */
  float Alpha(double NowMs) const;
  /** The outlines are on the board (shown or fading). */
  bool IsDrawn() const { return State == ES09LastMoveState::Shown || State == ES09LastMoveState::Fading; }
  ES09LastMoveState GetState() const { return State; }
  const FS09LastMovement& GetTrail() const { return Trail; }
  /** Changes with every state change (the plates' redraw key). */
  uint32 GetRevision() const { return Revision; }
  /** The last reveal came without an animation (MS-E-102 restore, seq gap). */
  bool WasRestored() const { return bRestored; }
  /** True once per reveal: the trail just shown (the event-feed line). */
  bool ConsumeRevealed(FS09LastMovement& Out);
  void Reset();
  static const TCHAR* StateName(ES09LastMoveState State);

private:
  ES09LastMoveState State = ES09LastMoveState::None;
  FS09LastMovement Trail;
  int32 EnteredSeq = -1;
  FS09BoardStamp PrevStamp;
  bool bAwaitAnimation = false;
  double RevealAtMs = 0.0;
  double FadeStartMs = 0.0;
  bool bRestored = false;
  bool bRevealedUnconsumed = false;
  uint32 Revision = 0;
};

/** One line of the event feed. */
struct UNMATCHED_API FS09FeedEntry {
  int32 Seq = 0;
  FString Text;  // at most MaxInlineMoves moves, then "and N more"
  FString Full;  // every move (the tooltip)
  int32 Moves = 0;
  bool bTruncated = false;
};

/** The minimal event feed of 03 §7: the three latest maneuver lines (not the UI-HUD-LOG journal). */
class UNMATCHED_API FS09EventFeed {
public:
  static constexpr int32 MaxLines = 3;
  static constexpr int32 MaxInlineMoves = 3;
  using FNameOf = TFunction<FString(const FString& /*Id*/)>;
  using FCellName = TFunction<FString(const FIntPoint& /*Cell*/)>;

  /** ms.log.maneuver of a MANEUVER trail: "{player}: maneuver{boostPart}: {moves}"; no movement -> ms.log.stay. */
  static FS09FeedEntry Describe(const FS09LastMovement& Trail, const FNameOf& PlayerName, const FNameOf& FighterName,
                                const FCellName& CellName);
  /** Adds the line of a MANEUVER trail once per seq (EFFECT moves are DE-022 lines); false when skipped. */
  bool Add(const FS09LastMovement& Trail, const FNameOf& PlayerName, const FNameOf& FighterName,
           const FCellName& CellName);
  /** Oldest first, at most MaxLines. */
  const TArray<FS09FeedEntry>& GetLines() const { return Lines; }
  uint32 GetRevision() const { return Revision; }
  void Reset();

private:
  TArray<FS09FeedEntry> Lines;
  TSet<int32> Seen;
  uint32 Revision = 0;
};

namespace S09OpponentView {
/** metadata.pendingManeuver.playerId ('' without an open maneuver). */
UNMATCHED_API FString PendingManeuverPlayer(const FS08Snapshot& Snapshot);
/** MS-S-11: the open maneuver is the opponent's. */
UNMATCHED_API bool OpponentPlanning(const FS08Snapshot& Snapshot, const FString& ViewerId);
/** Opacity of the indicator: a 1 Hz pulse 0.45 .. 1 (03 §6); reduced motion: no pulse (1). */
UNMATCHED_API float PlanningPulse(double Seconds, bool bReducedMotion);

/** The plate input V-14 / V-15 of a trail: starts, path points, ends, in the mover's team colour. */
UNMATCHED_API FS08MoveDraftInput::FLastMove LastMoveInput(const FS09LastMovement& Trail, ES08PlateColor Color);

/** MS-E-73 edge arrow: where (viewport pixels) and towards which angle (deg, screen x right / y down) an arrow at the
 *  edge points at Target. bShow false when Target is inside the viewport inset by Margin or not projectable. */
struct UNMATCHED_API FEdgeArrow {
  bool bShow = false;
  FVector2D Pos = FVector2D::ZeroVector;
  float AngleDeg = 0.0f;
};
UNMATCHED_API FEdgeArrow EdgeArrow(const FVector2D& Target, bool bProjected, const FVector2D& Viewport, float Margin);
}  // namespace S09OpponentView

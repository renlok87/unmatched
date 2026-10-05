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
// FS08MoveDraftInput::LastMove), the HUD lines and the arrow.
// DE-022 (W-13; 03 §7 "Дополнение по живым данным DE" п. 1-3, MS-R-77; 01 F-12; 02-ux-ui-spec SD-31) adds:
//   - the opponent's phase verb from the server state (S09OpponentView::OpponentVerb: the head of pendingEffects,
//     combatInfo, pendingManeuver, pendingHandDiscard, currentTurnPlayerId - never a client guess);
//   - the action tracker of both players by the snapshot (FS09ActionTracker): own always, the opponent's only in
//     the opponent's turn - appearing over 150 ms, hidden in one frame at the start of mine;
//   - the opponent's effect moving MY fighter (an EFFECT trail): the source card (FS09EffectSources: the resolved
//     pending effect's text matched against the mover's public discard pile) and the line ms.opp.moves.yours while
//     the move plays along the trail (MS-T-16); the effect lines of the feed.
// The BOOSTED card of the opponent's maneuver (MS-R-78) is DE-026 (the source-card slot of W-18).
#pragma once

#include "CoreMinimal.h"
#include "../S08/S08BoardModel.h"
#include "../S08/S08Contracts.h"
#include "../S08/S08MoveHighlight.h"
#include "S09HudModel.h"

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
  FString SourceRef;  // MANEUVER: the maneuverId; EFFECT: the id of the resolved pending effect (DE-022)
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
  /** Adds the line of a MANEUVER trail once per seq (EFFECT trails: AddEffect); false when skipped. */
  bool Add(const FS09LastMovement& Trail, const FNameOf& PlayerName, const FNameOf& FighterName,
           const FCellName& CellName);
  /** DE-022: the line of an EFFECT trail. YourFighters (the viewer's fighters an opponent's effect moved, in trail
   *  order) not empty -> ms.opp.moves.yours per fighter ("Your fighter Merlin: Feint effect"); otherwise
   *  ms.log.effect "{player}: {cardName} effect: {moves}" (no movement -> ms.log.stay). An unknown card -> "?". */
  static FS09FeedEntry DescribeEffect(const FS09LastMovement& Trail, const FString& CardName,
                                      const TArray<FString>& YourFighters, const FNameOf& PlayerName,
                                      const FNameOf& FighterName, const FCellName& CellName);
  /** Adds the line of an EFFECT trail once per seq; false when skipped (not an EFFECT trail, seq seen). */
  bool AddEffect(const FS09LastMovement& Trail, const FString& CardName, const TArray<FString>& YourFighters,
                 const FNameOf& PlayerName, const FNameOf& FighterName, const FCellName& CellName);
  /** Oldest first, at most MaxLines. */
  const TArray<FS09FeedEntry>& GetLines() const { return Lines; }
  uint32 GetRevision() const { return Revision; }
  void Reset();

private:
  TArray<FS09FeedEntry> Lines;
  TSet<int32> Seen;
  uint32 Revision = 0;
};

// ---------------------------------------------------------------------------------------------------- DE-022

/** What the opponent is doing now, read from the server state (03 §7 п. 1; ms.opp.phase.*). None: nothing of the
 *  opponent's is open - my turn, my own choice, the game is over. Turn: the opponent's turn with nothing open yet
 *  (ms.opp.phase.turn - DE-022's key by the 02 SD-31 convention). */
enum class ES09OpponentVerb : uint8 { None, Turn, Maneuver, Attack, Defend, Card, Ability };

/** The action tracker of both players (01 F-12; 03 §7 п. 2): slots and spent actions of the turn from
 *  metadata.actionsRemaining of the applied snapshots - the server spends the action at beginManeuver / attack /
 *  scheme, so a slot is marked when the action is chosen. Own: always visible (its turn's marks, otherwise every
 *  slot free - the reset comes in the frame the turn passes); the opponent's: only in the opponent's turn,
 *  appearing over AppearMs, hidden in the frame my turn starts. */
class UNMATCHED_API FS09ActionTracker {
public:
  /** 01 F-12 "появление 150 мс". */
  static constexpr double AppearMs = 150.0;
  /** ACTIONS_PER_TURN of the backend (game-state.model.ts). */
  static constexpr int32 PerTurn = 2;
  struct FSlots {
    int32 Slots = PerTurn;
    int32 Spent = 0;
    bool operator==(const FSlots& O) const { return Slots == O.Slots && Spent == O.Spent; }
  };
  /** An applied snapshot. ActionsRemaining -1 = unknown (a merge without metadata): the marks stay. SpentAs = the
   *  action type of the slots this snapshot spends (S09OpponentView::SpentActionType; run I, AB-7: the DE tracker
   *  fills a spent slot with the icon of its type). Returns the 'MS-TRACK ...' trace line when anything visible
   *  changed ('' otherwise). */
  FString OnApplied(int32 Seq, const FString& TurnPlayerId, int32 TurnCount, int32 ActionsRemaining,
                    const FString& ViewerId, double NowMs, FName SpentAs = NAME_None);
  /** The type of spent slot Index of the active turn ('attack' / 'maneuver' / 'scheme'; NAME_None unknown). */
  FName SpentType(int32 Index) const { return SpentTypes.IsValidIndex(Index) ? SpentTypes[Index] : NAME_None; }
  FSlots Own() const { return bOwnTurn ? TurnSlots : FSlots(); }
  FSlots Opponent() const { return bOpponentTurn ? TurnSlots : FSlots(); }
  bool OpponentVisible() const { return bOpponentTurn; }
  /** 0 -> 1 over AppearMs from the start of the opponent's turn (1 at once with reduced motion); 0 when hidden. */
  float OpponentAlpha(double NowMs, bool bReducedMotion) const;
  void Reset() { *this = FS09ActionTracker(); }

private:
  FString TurnKey;
  int32 LastRemaining = -1;
  bool bOwnTurn = false;
  bool bOpponentTurn = false;
  FSlots TurnSlots;  // the active player's marks of this turn
  TArray<FName> SpentTypes;  // the type of each spent slot of this turn (index = slot)
  double OpponentSinceMs = 0.0;
  FString TraceKey;
};

/** The texts of the pending effects seen so far (id -> text): the EFFECT trail names only the id of the resolved
 *  choice (lastMovement.sourceRef); the card itself is in its owner's public discard pile by then. */
class UNMATCHED_API FS09EffectSources {
public:
  static constexpr int32 MaxKept = 32;
  void Note(const TArray<FS08PendingEffect>& Queue);
  /** The text of a pending effect seen before ('' when it was never seen - a seq gap, a reconnect). */
  FString TextOf(const FString& PendingId) const;
  void Reset() {
    Ids.Reset();
    Texts.Reset();
  }

private:
  TArray<FString> Ids;  // oldest first
  TMap<FString, FString> Texts;
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

/** DE-022 (03 §7 п. 1): the opponent's verb, in this order - the head of pendingEffects (owned by the opponent:
 *  DISCARD_CARDS / BOOST_CHOICE / DECK_TOP_PICK -> Card, every other choice -> Ability; owned by me -> None, they
 *  wait on me), the open combat (I defend -> Attack, they defend -> Defend), the opponent's pendingManeuver ->
 *  Maneuver, the opponent's pendingHandDiscard -> Card, the opponent's turn -> Turn; None otherwise and at
 *  GAME_OVER. */
UNMATCHED_API ES09OpponentVerb OpponentVerb(const FS08Snapshot& Snapshot, const FString& ViewerId);
/** Run I (AB-7, the DE tracker): the action type a snapshot that spends an action shows - 'maneuver' (an open
 *  pendingManeuver, or a MANEUVER lastMovement of this very seq), 'attack' (the open combat: combatInfo or a COMBAT
 *  phase), else 'scheme' (the third action of the turn - a scheme card leaves neither). The snapshot carries no
 *  type of its own; a seq gap that skipped the maneuver / combat snapshot reads as 'scheme'. */
UNMATCHED_API FName SpentActionType(const FS08Snapshot& Snapshot);
/** metadata.pendingEffects with only id / playerId / type / text read (server order; [0] is the head). */
UNMATCHED_API TArray<FS08PendingEffect> PendingQueue(const FS08Snapshot& Snapshot);
/** ms.opp.planning / ms.opp.phase.* of a verb (NAME_None for None). */
UNMATCHED_API FName VerbKey(ES09OpponentVerb Verb);
UNMATCHED_API const TCHAR* VerbName(ES09OpponentVerb Verb);

/** DE-022 (03 §7 п. 3): the viewer's fighters that an opponent's EFFECT trail moved, in trail order (empty for a
 *  maneuver, for the viewer's own choice or when only the opponent's fighters moved). OwnerOf: fighter id -> owner. */
UNMATCHED_API TArray<FString> YourFightersMoved(const FS09LastMovement& Trail, const FString& ViewerId,
                                                const TFunction<FString(const FString&)>& OwnerOf);
/** The source card of an EFFECT trail, from public data only: in the mover's discard pile (oldest first, as the
 *  HUD model delivers it) the newest face-up card whose text contains the resolved pending effect's text; else the
 *  newest face-up card with effect text; '' when the pile has none. */
UNMATCHED_API FString EffectCardName(const FString& PendingText, const TArray<FS09CardView>& MoverDiscard);
}  // namespace S09OpponentView

// DE-024 (W-23; 02 SD-42, SD-43; 01 "Резолюция ревью" п. 4; 02-ux-ui-spec §4.2 "Лимит руки", §7.1 UI-ACC-012): the
// world-free models of the hand limit. Automation-tested (Unmatched.S09.HandLimit.*):
//   - FS09HandLimitHint: the one-shot rule toast. The first time in a match the own hand GROWS to the limit (7 =
//     handZones[me].maxSize; the server's MAX_HAND_SIZE) the toast shows the rule once. It never blocks input (the
//     model has no input gate at all; the widget is a hit-test target only over itself), closes on a click or when the
//     turn it appeared in ends (or GAME_OVER), and never comes back in the same match. UI-ACC-012 off: no toast. The
//     first snapshot seen (join, reconnect) only records the hand - a client that rejoins with 7 cards does not
//     re-teach the rule it showed before the reconnect.
//   - FS09DiscardPick: ONE view of both hand discards - the end-of-turn discard to the limit (metadata.
//     pendingHandDiscard, SD-43) and an effect's DISCARD_CARDS choice (pendingEffects head, SD-43 п. 3). The HUD
//     draws both with the same pending widget lines and the same hand highlight (every own card a candidate, the picked
//     ones marked). The limit discard has no cancel (the server keeps the turn until the exact count arrives, then
//     passes it by itself); picks are a click and a confirm, never a drag (D-05).
#pragma once

#include "CoreMinimal.h"
#include "S09ManeuverUi.h"

/** Why the rule toast closed in this apply (None = still open, or it was never open). */
enum class ES09HintClose : uint8 { None, Click, TurnEnd, GameOver, Off };

struct UNMATCHED_API FS09HandLimitHintEvent {
  bool bShown = false;                     // the toast appeared in this apply
  ES09HintClose Closed = ES09HintClose::None;
};

class UNMATCHED_API FS09HandLimitHint {
public:
  /** The server's end-of-turn limit (backend MAX_HAND_SIZE = 7) when the hand projection has no maxSize. */
  static constexpr int32 DefaultLimit = 7;
  static int32 LimitOf(int32 HandMaxSize) { return HandMaxSize > 0 ? HandMaxSize : DefaultLimit; }

  /** An applied snapshot. GameId keys "once per match" (a new match starts over); TurnKey is
   *  currentTurnPlayerId#turnCount; OwnHandCount is the viewer's hand size (count of the own hand projection);
   *  bEnabled is UI-ACC-012 for this run. */
  FS09HandLimitHintEvent OnApplied(const FString& GameId, const FString& TurnKey, bool bGameOver, int32 OwnHandCount,
                                   int32 HandLimit, bool bEnabled);
  /** A click on the toast. True when it was open (it closes; it never comes back in this match). */
  bool Dismiss();
  bool IsVisible() const { return bVisible; }
  /** The toast was shown in this match (visible now or closed). */
  bool WasShown() const { return bShown; }
  /** The limit the toast spoke of (its {n}). */
  int32 ShownLimit() const { return Limit; }
  void Reset() { *this = FS09HandLimitHint(); }
  static const TCHAR* CloseName(ES09HintClose Close);

private:
  FString GameKey;
  bool bSeen = false;
  int32 LastCount = 0;
  bool bShown = false;
  bool bVisible = false;
  FString ShownTurnKey;
  int32 Limit = DefaultLimit;
};

/** Where an own hand discard comes from. */
enum class ES09DiscardSource : uint8 { None, HandLimit, Effect };

/** How the hand strip marks a card while a discard is open. */
enum class ES09HandMark : uint8 { None, Candidate, Picked };

struct UNMATCHED_API FS09DiscardPick {
  ES09DiscardSource Source = ES09DiscardSource::None;
  int32 Need = 0;
  TArray<FString> Picked;
  /** The effect's choice was sent with optional:true (the pending widget then offers its decline). */
  bool bOptional = false;

  /** The discard open on the command state now: the limit discard (DiscardDraft) or the own DISCARD_CARDS head. */
  static FS09DiscardPick From(const FS09CommandUi& Ui);

  bool IsOpen() const { return Source != ES09DiscardSource::None; }
  /** A mandatory discard has no cancel: the limit discard always, an effect's unless optional. */
  bool IsMandatory() const { return IsOpen() && (Source == ES09DiscardSource::HandLimit || !bOptional); }
  int32 Left() const { return FMath::Max(0, Need - Picked.Num()); }
  bool IsComplete() const { return IsOpen() && Picked.Num() == Need; }
  /** Every own visible card is a candidate while the discard is open; the picked ones are Picked. */
  ES09HandMark Mark(const FString& InstanceId, bool bHidden) const;
  /** The pick line of the pending widget (both sources): "CHOOSE n CARD(S): selected h/n (k more)". */
  FString PickLine() const;
  static const TCHAR* SourceName(ES09DiscardSource Source);
};

// DE-020 (W-11; de-footage/task 02 SD-10, SD-16, SD-19, SD-28, SD-56; 01 F-11, D-DE-11; 02-ux-ui-spec §4.6
// п. 1, 5, 6; move-selection 03 §7 п. 4, MS-R-77; 04 §4.3.1): how the client SERVES the deferred choices.
// World-free (headless-testable); the game mode feeds snapshots and renders the result.
//   - FS09SkippedEffectsFeed: the server skips an effect without legal targets and leaves a note in
//     metadata.skippedEffects (DE-016); the client explains every note with n above the last one shown -
//     toast why.effect.no.targets + CUE-004 - and on the first snapshot (entry, reconnect) only remembers the
//     largest n without showing anything.
//   - FS09PendingPresenter: one presentation per open of an own head - the modal (first time), a toast for a
//     REPEATING OPTIONAL trigger (its signature was opened before), a compact panel for a MANDATORY choice that
//     comes back every turn (seen in an earlier turn) with the variant answered last time pre-selected. The
//     modal collapses into a plate (the board stays visible); collapsing never cancels the choice.
//   - S09DescribePendingStep: a choice in two steps "object -> target (up to N)" (ms.choice.object,
//     ms.choice.target), also and especially in the opponent's turn (the opponent's scheme hands the choice over).
//   - S09PendingHasNoTargets: the client never waits for input without a highlighted target - an own head with
//     nothing to pick reads why.effect.no.targets (after DE-016 the server does not open such heads; the line is
//     the signal of a server gap).
#pragma once

#include "CoreMinimal.h"
#include "S09ManeuverUi.h"

/** One metadata.skippedEffects entry (move-selection 04 §4.3.1). */
struct UNMATCHED_API FS09SkippedEffectNote {
  int32 N = 0;        // running number in the game (1, 2, ...)
  int32 Seq = 0;      // sequenceNumber of the skip (diagnostics only)
  FString Reason;     // NO_VALID_TARGETS (the only one so far)
  FString PlayerId;   // whose choice / effect it was
  FString EffectId;
  FString Kind;       // PendingEffect.type or EffectType
  FString Text;       // printed text when present
  /** why.effect.no.targets for NO_VALID_TARGETS (and for an unknown reason - the toast still explains). */
  FS09Reason Why() const;
};

class UNMATCHED_API FS09SkippedEffectsFeed {
public:
  /** Decodes metadata.skippedEffects (entries without a positive n are dropped). False when the field is
   *  absent or not an array ("no skips" - saves without the field). */
  static bool Parse(const FS08Snapshot& Snapshot, TArray<FS09SkippedEffectNote>& OutNotes);
  /** Notes to explain now, oldest first: n > the last shown. The first snapshot with metadata primes the feed
   *  with the largest n and returns nothing (entry / reconnect never replays old skips). */
  TArray<FS09SkippedEffectNote> Consume(const FS08Snapshot& Snapshot);
  /** A new game / room: the next snapshot primes again. */
  void Reset();
  int32 LastShownN = 0;
  bool bPrimed = false;
};

enum class ES09PendingPresent : uint8 { Modal, Compact, Toast };

UNMATCHED_API const TCHAR* S09PendingPresentName(ES09PendingPresent Present);

/** The answer given to a head - what the compact / toast form pre-selects next time. */
struct UNMATCHED_API FS09PendingVariant {
  int32 OptionIndex = -1;  // CHOOSE_ONE: the server's stable option index
  FString FighterId;       // MOVE / PLACE / TARGET_FIGHTER
  bool bHasCell = false;   // MOVE / PLACE / CHOOSE_SPACE
  int32 CellX = -1;
  int32 CellY = -1;
  bool IsSet() const { return OptionIndex >= 0 || !FighterId.IsEmpty() || bHasCell; }
  static FS09PendingVariant FromCommand(const FS09PendingChoiceCommand& Command);
  /** Trace-safe: option index, fighter id, cell - no card identity. */
  FString Describe() const;
};

class UNMATCHED_API FS09PendingPresenter {
public:
  /** What makes two opens "the same trigger": type, printed text, fighter restriction and optional flag. */
  static FString Signature(const FS08PendingEffect& Head);
  /** Feed the viewer-owned head (call with every applied snapshot while one is open). A new head id is a new
   *  open: the presentation is decided once, from the history of the signature, and the history is updated.
   *  Returns true for a new open. */
  bool Observe(const FS08PendingEffect& Head, int32 TurnCount);
  /** No own head any more: the open ends (history stays). */
  void Clear();
  /** A new game: history too. */
  void Reset();
  bool IsOpen() const { return !HeadId.IsEmpty(); }

  /** Modal / compact -> the plate; true when the state changed. The toast has no plate. */
  bool Collapse();
  /** The plate -> back; the toast -> the full modal ("details"). True when the state changed. */
  bool Expand();
  /** C key / the plate click: collapse an expanded form, expand a collapsed one (or the toast). */
  bool Toggle();

  /** The answer just sent for the current head (the next compact / toast open pre-selects it). */
  void Remember(const FS08PendingEffect& Head, const FS09PendingVariant& Variant);
  /** The variant remembered for the CURRENT head's signature (nullptr when none). */
  const FS09PendingVariant* Remembered() const;

  /** "MS-PENDING present=<modal|compact|toast> id=<id> type=<type> opens=<n> collapsed=<0|1>". */
  FString TraceLine() const;

  ES09PendingPresent Present = ES09PendingPresent::Modal;
  bool bCollapsed = false;
  FString HeadId;
  FString HeadSignature;
  int32 OpensBefore = 0;  // earlier opens of this signature (this game)

private:
  struct FHistory {
    int32 Opens = 0;
    int32 LastTurn = INDEX_NONE;
    FS09PendingVariant Last;
  };
  TMap<FString, FHistory> History;
};

/** One step of a choice "object -> target (up to N)". Step 1 of 2: ms.choice.object (MOVE / PLACE before the
 *  fighter is picked); step 2 of 2: ms.choice.target {n} (n = the MOVE allowance, 1 for a PLACE space); a
 *  one-step target choice (TARGET_FIGHTER, CHOOSE_SPACE) is step 1 of 1. Other types have no step line. */
struct UNMATCHED_API FS09PendingStep {
  bool bValid = false;
  int32 Step = 0;
  int32 Steps = 0;
  int32 N = 0;
  bool bOpponentTurn = false;  // the choice is ours, the turn is the opponent's (MS-R-77)
  FS09Reason Prompt;
  /** "object" / "target" for the trace. */
  const TCHAR* StepName() const;
};

UNMATCHED_API FS09PendingStep S09DescribePendingStep(const FS09CommandUi& Ui, const FS08Snapshot& Snapshot,
                                                     const FS08BoardModel& Board,
                                                     const TArray<FS08BoardFighter>& Fighters);

/** An own head with nothing to pick: TARGET_FIGHTER without a living legal target, MOVE / PLACE without a
 *  legal fighter or space (MS-T-12 bNoSpace), CHOOSE_SPACE without a legal space. */
UNMATCHED_API bool S09PendingHasNoTargets(const FS09CommandUi& Ui, const FS08Snapshot& Snapshot,
                                          const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters);

/** Pre-selects a remembered variant on the open head where it is still legal (CHOOSE_ONE by the stable index,
 *  the fighter of MOVE / PLACE / TARGET_FIGHTER, then the remembered space). OutApplied describes what was
 *  set; false when nothing applied. Never sends anything. */
UNMATCHED_API bool S09ApplyPendingVariant(FS09CommandUi& Ui, const FS09PendingVariant& Variant,
                                          const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                                          const TArray<FS08BoardFighter>& Fighters, FString& OutApplied);

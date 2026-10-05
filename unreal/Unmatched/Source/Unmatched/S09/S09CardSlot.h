// DE-026 (W-18; de-footage/task 02 SD-02, SD-26, SD-28 п. 4, SD-54; 01 F-10, D-DE-10; 07-animation-vfx-audio CUE-006;
// APPROXIMATION §9): the hand and the played cards, world-free and automation-tested (Unmatched.S09.SCHEME.Slot.*,
// Unmatched.S09.SCHEME.HandLower.*). The game mode (S08FlowGameModeCardSlot.cpp) feeds snapshots and draws them.
//   - FS09HandLower (SD-26): while a cell or a target is being picked on the board and the cursor is not over a HUD
//     panel, the hand strip goes down by LowerSu (DE LOWER HAND: 815 -> 875 at 1080p) and the hand-card preview (the
//     inspector) is not drawn - the preview never covers the field. The hand comes back up when the pick ends or the
//     cursor goes onto the HUD (the cards stay reachable for a boost or a pick).
//   - FS09PlayedCardWatch: which card goes into the source-card slot, from public data only (the discard piles and
//     metadata.lastMovement of the applied snapshots): a SCHEME card that entered a pile outside combat and outside an
//     open discard of its owner (SCHEME ribbon); the BOOST card of the opponent's maneuver (BOOSTED, SD-54); cards the
//     opponent discarded to an open discard (DISCARDED). The first snapshot (entry, reconnect) only primes.
//   - FS09SourceSlot (F-10, SD-02, SD-28 п. 4, SD-54): the slot at the top left. Every card flies in over FlyMs.
//       opponent's scheme: fly 200 -> hold 1500 BEFORE its effect -> the effect (the board and the HP of the snapshot,
//         its cues, my own choice it opened); a click / Space / Enter during the hold starts the effect at once;
//       own scheme: the effect starts on arrival (no wait), the card shows OwnSchemeMs;
//       opponent's boost: from the start of the move, at least MinShowMs; the move never waits for it;
//       discarded: at least MinShowMs.
//     The card stays while its effect runs (moves playing, a choice open) and leaves: a scheme in one frame, the
//     others with a FadeMs fade (DE: the boost card fades ~250 ms). A new card replaces the shown one (CUE-006
//     on_new_event replace) - except a DISCARDED card never replaces a scheme (it is that scheme's effect). A held
//     effect is released before anything replaces it (a new seq, a reconnect, the end of the game).
// Trace lines (the game mode writes them): 'HUD-SLOT show|effect|skip|off ...', 'HUD-HAND lower=<0|1> ...'.
#pragma once

#include "CoreMinimal.h"
#include "S09HudModel.h"
#include "S09ManeuverUi.h"
#include "S09OpponentView.h"

// ---------------------------------------------------------------------------------------------------- hand (SD-26)

/** The board pick in progress: a cell (a maneuver destination, a MOVE / PLACE / CHOOSE_SPACE space, the MS-S-02 cell
 *  of a selected own fighter) or a target (an attack target, TARGET_FIGHTER, the fighter of a MOVE / PLACE). */
enum class ES09BoardPick : uint8 { None, Cell, Target };

UNMATCHED_API const TCHAR* S09BoardPickName(ES09BoardPick Pick);

/** The pick of the command state. bViewerTurn gates the no-draft cell pick of a selected own fighter. */
UNMATCHED_API ES09BoardPick S09BoardPickOf(const FS09CommandUi& Ui, bool bViewerTurn);

class UNMATCHED_API FS09HandLower {
public:
  /** SD-26 / R-15: DE lowers the top of the hand by ~60 px at 1080p (WF1 HUD-M17). Slate units. */
  static constexpr float LowerSu = 60.0f;
  /** The slide down / up (ours; DE has no measured value). Reduced motion: no slide. */
  static constexpr double SlideMs = 120.0;

  /** Every frame. Lowered = a board pick is in progress and the cursor is not over a HUD panel. Returns the
   *  'HUD-HAND lower=<0|1> pick=<cell|target|none> cursor=<board|hud>' line when the state flips ('' otherwise). */
  FString Update(ES09BoardPick Pick, bool bCursorOverHud, double NowMs);
  bool IsLowered() const { return bLowered; }
  /** The hand-card preview (inspector) is not drawn while lowered. */
  bool HidesPreview() const { return bLowered; }
  /** 0 .. LowerSu: how far down the hand panel is now (ease out; the end value at once with reduced motion). */
  float OffsetSu(double NowMs, bool bReducedMotion) const;
  /** True while the slide still runs (the widget needs a per-frame transform). */
  bool IsSliding(double NowMs, bool bReducedMotion) const;
  void Reset() { *this = FS09HandLower(); }

private:
  bool bLowered = false;
  double ChangedMs = -1.0e9;
  float FromSu = 0.0f;
};

// ---------------------------------------------------------------------------------------------------- slot (F-10)

enum class ES09SlotRibbon : uint8 { Scheme, Boosted, Discarded };

UNMATCHED_API const TCHAR* S09SlotRibbonName(ES09SlotRibbon Ribbon);
/** The ribbon text (SCHEME / BOOSTED / DISCARDED; the marker-status art is not in UE yet - a Slate band). */
UNMATCHED_API const TCHAR* S09SlotRibbonLabel(ES09SlotRibbon Ribbon);

struct UNMATCHED_API FS09SlotCard {
  FS09CardView Card;   // the public face (a boost card not found in the pile: name and value from lastMovement)
  FString OwnerId;
  bool bOpponent = false;
  ES09SlotRibbon Ribbon = ES09SlotRibbon::Scheme;
  int32 Count = 1;     // DISCARDED: cards discarded together (the newest is shown)
  int32 Seq = 0;
};

class UNMATCHED_API FS09PlayedCardWatch {
public:
  /** An applied snapshot (a same-seq merge too). Hud is built from it; Queue = its pendingEffects; Trail = its
   *  metadata.lastMovement. True with Out set when a card goes to the slot: scheme > boosted > discarded (one per
   *  call). The first call primes the piles and returns false. */
  bool OnApplied(const FS09HudModel& Hud, const TArray<FS08PendingEffect>& Queue, const FS09LastMovement& Trail,
                 const FString& ViewerId, FS09SlotCard& Out);
  void Reset() { *this = FS09PlayedCardWatch(); }

  static bool IsCombatPhase(const FString& Phase) {
    return Phase == TEXT("COMBAT") || Phase == TEXT("COMBAT_RESOLVE");
  }

private:
  bool bPrimed = false;
  TMap<FString, TSet<FString>> PileIds;  // player -> discard instance ids seen
  TSet<FString> DiscardOpen;             // players with an open discard (limit, DISCARD_CARDS, BOOST_CHOICE) before
  bool bCombatBefore = false;
  int32 BoostSeqSeen = -1;
};

enum class ES09SlotState : uint8 { Idle, Fly, Hold, Show, Fade };

class UNMATCHED_API FS09SourceSlot {
public:
  /** 01 F-10: the card flies in over 200 ms. */
  static constexpr int32 FlyMs = 200;
  /** 01 F-10: the opponent's scheme waits 1500 ms after its arrival before the effect. */
  static constexpr int32 OppSchemeHoldMs = 1500;
  /** 01 F-10 / CUE-006 duration_ms: the own scheme shows 500 ms after its arrival (its effect starts on arrival). */
  static constexpr int32 OwnSchemeMs = 500;
  /** 02 SD-54: the opponent's boost card at least 1000 ms from the start of the move (discarded cards alike). */
  static constexpr int32 MinShowMs = 1000;
  /** DE: the BOOST card fades out ~250 ms (APPROXIMATION §9, tl:54); a scheme leaves in one frame. */
  static constexpr int32 FadeMs = 250;
  /** A card whose effect never ends (a stuck choice) leaves after this long. */
  static constexpr int32 MaxShowMs = 30000;

  /** A card enters at NowMs. A shown card is replaced ('HUD-SLOT off ... reason=replace'); a held effect is released
   *  first (bOutReleased). A DISCARDED card while a scheme shows is dropped (false). */
  bool Show(const FS09SlotCard& InCard, int64 NowMs, bool bReducedMotion, TArray<FString>& OutLines,
            bool& bOutReleased);
  /** Every frame. bEffectBusy: the card's effect still runs (a move plays, a choice is open). Releases a held
   *  effect at its time (bOutReleased, once) and ends the card. */
  void Tick(int64 NowMs, bool bEffectBusy, TArray<FString>& OutLines, bool& bOutReleased);
  /** A click / Space / Enter during the hold of the opponent's scheme: its effect starts now. False otherwise. */
  bool Skip(int64 NowMs, const TCHAR* Source, TArray<FString>& OutLines);
  /** Ends the card now (a reconnect, the end of the game, a reset), releasing a held effect (bOutReleased). */
  void Cut(int64 NowMs, const TCHAR* Reason, TArray<FString>& OutLines, bool& bOutReleased);
  /** A new seq arrives while the effect is held: the held effect starts now; the card itself stays (its show goes
   *  on). True when something was released. */
  bool ReleaseForSeq(int32 Seq, int64 NowMs, TArray<FString>& OutLines);

  /** The opponent's scheme waits: the snapshot's effect is not presented yet. */
  bool HoldsEffect() const { return bHolding; }
  int32 HeldSeq() const { return bHolding ? Card.Seq : -1; }
  bool IsVisible() const { return State != ES09SlotState::Idle; }
  ES09SlotState GetState() const { return State; }
  const FS09SlotCard& GetCard() const { return Card; }
  /** 0 -> 1 over the fly (ease out); 1 with reduced motion. */
  float FlyT(int64 NowMs) const;
  /** 1, then 1 -> 0 over the fade. */
  float Alpha(int64 NowMs) const;
  /** Changes when a card shows or leaves (the widget's rebuild key). */
  uint32 GetRevision() const { return Revision; }
  /** When the held effect is due (-1 when nothing is held). */
  int64 ReleaseAtMs() const { return bHolding ? ReleaseMs : -1; }
  void Reset() { *this = FS09SourceSlot(); }
  static const TCHAR* StateName(ES09SlotState State);

private:
  void Release(int64 NowMs, const TCHAR* How, TArray<FString>& OutLines);
  void Off(int64 NowMs, const TCHAR* Reason, TArray<FString>& OutLines);

  ES09SlotState State = ES09SlotState::Idle;
  FS09SlotCard Card;
  bool bReduced = false;
  bool bHolding = false;
  int64 StartMs = 0;
  int64 ArriveMs = 0;
  int64 ReleaseMs = 0;  // the held effect is due (opponent's scheme), else the arrival
  int64 MinEndMs = 0;
  int64 FadeStartMs = 0;
  uint32 Revision = 0;
};

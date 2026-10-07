// GD-032: typed, privacy-safe HUD view model for hands, public discards and
// deck counters, derived ONLY from the authoritative FS08Snapshot store.
//
// Privacy contract (ACC-009/ACC-018, GameStateService.filterPrivateData):
//   - own hand: exact card instances (id = instance id like "card::0");
//   - opponent hand: COUNT ONLY - entries are server placeholders and are
//     never decoded into names/values (by construction this model cannot
//     leak a face it never read);
//   - decks: hidden placeholders on the wire - only array lengths survive
//     here; neither catalog order nor topCard is ever exposed as "draw
//     order" (the server hides both; the HUD shows a counter);
//   - discard piles: public faces; a face-down placeholder entry stays a
//     bHidden card with no identity (combat-committed cards before reveal).
// Freshness (unmatched-net/1 section 2): the WS event omits `decks`, so
// counters carry the seq they were last seen at; the HUD marks counts of a
// body older than the applied seq as stale ("~") instead of lying.
#pragma once

#include "CoreMinimal.h"
#include "../S08/S08Contracts.h"

struct UNMATCHED_API FS09CardView {
  FString InstanceId; // hand/discard instance id ("hidden-N" for placeholders)
  FString CardId;     // catalog key ("hidden" for placeholders)
  FString Name;
  FString NameRu;
  FString CardType;
  int32 AttackValue = 0;
  int32 DefenseValue = 0;
  int32 BoostValue = 0;
  // MS-T-05: boostValue was a JSON number (backend cardBoost); null / absent /
  // a string = no printed BOOST - such a card is never offered as a boost.
  bool bHasBoostValue = false;
  FString BannerName;
  FString Text;
  // DE-018 (01 F-01): number of entries of the card's `effects` array - with Text the "has effect text" test of the
  // combat read hold (combat.readHoldMs 1000 only when a revealed card carries an effect).
  int32 EffectCount = 0;
  // VS-3 HB-33: the printed text of the card's effects (effects[].text joined) - the centre's line of a cancelled card
  FString EffectText;
  bool bHidden = false;  // server placeholder: no face anywhere (count only)
  bool bNew = false;     // drawn since the previous own-hand set (ACC-006)
  bool bVisible = false; // isVisible flag as delivered (own hand: false)

  /** One-line chip for the hand strip (never called for hidden cards). */
  FString ChipText() const;
};

/** Per-player panel data: one viewer entry + one opponent entry. */
struct UNMATCHED_API FS09PlayerPanel {
  FString PlayerId;
  bool bIsViewer = false;
  bool bIsAlive = true; // players projection isAlive (absent = alive)
  // Own hand: exact instances. Opponent hand: count only (Cards stays empty
  // for the opponent - reading those entries is forbidden by design).
  TArray<FS09CardView> Cards;
  int32 HandCount = 0;
  int32 HandMaxSize = 0;
  TArray<FS09CardView> Discard; // public pile, oldest first as delivered
  int32 DeckCount = 0;
  bool bDeckCountStale = false;  // decks last seen at a seq < applied seq
  bool bDiscardStale = false;    // discardPiles last seen at a seq < applied seq
};

struct UNMATCHED_API FS09HudModel {
  TArray<FS09PlayerPanel> Panels; // [0] = viewer, [1] = opponent
  int32 SequenceNumber = 0;
  FString Phase;
  int32 TurnCount = 0;
  bool bViewerTurn = false;
  int32 ActionsRemaining = -1; // -1 = unknown (metadata absent in a merge)
  FS08PendingHandDiscard PendingDiscard;
  bool bHasPendingDiscard = false;

  // ---- GD-036 terminal result (strictly server-outcome driven) ----
  // phase GAME_OVER + metadata.winnerId are the ONLY trigger; an aborted
  // room (status ABORTED, phase unchanged) never renders as a victory.
  bool bGameOver = false;      // applied snapshot phase == GAME_OVER
  FString WinnerPlayerId;      // metadata.winnerId ('' = absent on the wire)
  bool bWinnerKnown = false;   // winnerId present and names a player
  bool bViewerWon = false;     // winner == viewer (false on a draw)
  bool bAnyPlayerAlive = true; // players projection has a living player
  // Server contract (applyTerminalState/checkGameEnd): GAME_OVER with NO
  // winnerId means mutual destruction (alive == 0) - the only DRAW. A
  // missing winnerId while someone lives (or a winnerId naming no player)
  // is NOT a draw: the verdict is unavailable and must not be invented.
  bool bDraw = false;          // GAME_OVER + no winnerId + nobody alive
  bool bOutcomeUnknown = false; // GAME_OVER with no derivable verdict
  FString WinnerHeroName;      // winner's living/last hero fighter name (public
                               // fighters projection; '' when undecodable)
  /** VICTORY/DEFEAT when the server named a winner; DRAW only for the
   *  server's mutual-destruction terminal (no winnerId, nobody alive);
   *  OUTCOME UNAVAILABLE otherwise - never an invented verdict. */
  FString OutcomeWord() const;

  /** True when Build saw projections it needs (own hand resolved). */
  bool bValid = false;

  /**
   * Derives the whole model from the applied snapshot.
   * @param PreviousOwnHandIds  instance ids of the previous own hand (may be
   *        empty); entries not present there are marked bNew (the card drawn
   *        by beginManeuver - ACC-006 "new card visible before boost").
   * @param DecksSeq / DiscardPilesSeq  seq of the last body that carried the
   *        projection (store-side freshness tracking).
   */
  void Build(const FS08Snapshot& Snapshot, const FString& ViewerId,
             const TSet<FString>& PreviousOwnHandIds, int32 DecksSeq,
             int32 DiscardPilesSeq);

  const FS09PlayerPanel* ViewerPanel() const {
    return Panels.Num() > 0 && Panels[0].bIsViewer ? &Panels[0] : nullptr;
  }
  const FS09PlayerPanel* OpponentPanel() const {
    return Panels.Num() > 1 && !Panels[1].bIsViewer ? &Panels[1] : nullptr;
  }

  /** Trace-safe one-line summary: counts and seq only - no hidden identity,
   *  no own card names (published evidence must stay reveal-free). */
  FString SummaryLine() const;
};

// ---- DE-018 (W-14; 02 SD-04, SD-05, SD-27): combat panel model ----

/** The defense slot of the combat panel in three states (SD-04): Shield = nothing chosen yet, CardBack = a defense
 *  card is chosen / committed face down, NoDefense = the red cross stamp (the defender committed no card - shown
 *  with the reveal). */
enum class ES09DefenseSlot : uint8 { Shield, CardBack, NoDefense };

/** World-free slot rule. COMBAT (defense window): the defender's own pick shows the card back, otherwise the
 *  shield (the attacker never sees the pick). COMBAT_RESOLVE exists only after playDefense (the "no defense"
 *  resolve goes from COMBAT straight to the result), so the slot holds a face-down card there. The reveal of a
 *  combat without a defense card stamps the cross. */
UNMATCHED_API ES09DefenseSlot S09DefenseSlotState(const FString& Phase, bool bViewerDefender, bool bDraftPicked,
                                                  bool bRevealedNoDefense);
UNMATCHED_API const TCHAR* S09DefenseSlotName(ES09DefenseSlot Slot);

/** The revealed cards of a finished combat, derived from public data only: the last open-combat snapshot (its
 *  combatInfo and discard piles, where the opponent's committed cards are "hidden-<index>" placeholders) and the
 *  closing snapshot (the same piles face up). The server clears combatInfo with the result, so this is the only
 *  source of the opponent's card for the reveal; nothing hidden is ever read (a placeholder index points at the
 *  card that the closing body already shows publicly). */
struct UNMATCHED_API FS09CombatReveal {
  bool bAttackKnown = false;
  FS09CardView Attack;
  TArray<FS09CardView> Boosts;    // ability boost (committed with the attack) and the BOOST_CHOICE card
  bool bDefenseKnown = false;
  FS09CardView Defense;
  bool bNoDefense = false;        // the defender committed no card (the slot gets the cross)
  int32 AttackValue = -1;         // printed attack + boost (-1 unknown)
  int32 DefenseValue = -1;        // printed defense, 0 without a card (-1 unknown)
  /** A revealed attack or defense card carries effect text (Text or effects[]) - the read hold applies. */
  bool HasEffectText() const;
  /** Baseline = the last applied open-combat snapshot (combatInfo present), Closing = the snapshot that closed the
   *  combat. AttackerOwnerId = owner of Combat.AttackerId. Hidden placeholders of the attacker's pile in the baseline:
   *  the first is the attack card (executeAttack discards it before the ability boost card), the rest are boosts. */
  static FS09CombatReveal Derive(const FS08CombatInfo& Combat, const FString& AttackerOwnerId,
                                 const TSharedPtr<FJsonValue>& BaselinePiles,
                                 const TSharedPtr<FJsonValue>& ClosingPiles);
};

class UNMATCHED_API FS09HudFactory {
public:
  /** Decodes one hand/discard entry into a card view. Hidden placeholders
   *  become bHidden cards with NO identity (privacy by construction). */
  static bool CardFromJson(const TSharedPtr<FJsonValue>& Value, FS09CardView& OutCard);
  /** Card view with identity stripped (used for placeholders). */
  static FS09CardView HiddenCard(const FString& PlaceholderId);
};

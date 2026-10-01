// GD-033: local command-state machine for the maneuver stages and the
// end-of-turn discard-to-limit choice. Pure logic (headless-testable):
// legal choices are derived ONLY from the authoritative applied snapshot
// (pending ids, own hand, own living fighters, board reachability); the
// caller owns transport (FS08FlowController) and passes its in-flight flag.
//
// Maneuver contract (ACC-006 / GD-013):
//   beginManeuver  -> server draws ONE card, opens metadata.pendingManeuver;
//   local draft    -> zero or more own fighters, one destination each
//                     (neighbour path built from the board model: links on
//                     an original-map board, orthogonal on a grid), optional
//                     boost = any exact own-hand instance id (the card drawn
//                     by begin is legal - it is already in the hand);
//   confirm        -> maneuver(maneuverId, moves, boostCardId?). Zero moves
//                     is a legal completion (draw + no movement).
// CANCEL is local-only: the committed server draw is never reversed and
// beginManeuver is never re-sent while a pendingManeuver exists - resuming
// re-enters the draft against the same pending id.
//
// Discard contract (ACC-005 / GD-012): TURN_END + pendingHandDiscard
// (playerId = viewer) -> select EXACTLY pending.count own hand instance ids
// -> discardToLimit(pendingId, ids). Duplicate ids are impossible (a set);
// a wrong count never leaves the local state.
#pragma once

#include "CoreMinimal.h"
#include "../S08/S08BoardModel.h"
#include "../S08/S08Contracts.h"
#include "../S08/S08FlowController.h"
#include "S09HudModel.h"

enum class ES09CommandMode : uint8 {
  None,
  ManeuverDraft,
  DiscardDraft,
  AttackDraft,    // GD-034: local draft of attack(attacker, card, adjacent target)
  CombatDefense,  // GD-034: COMBAT, viewer IS the defender (opponent's turn)
  CombatResolve,  // GD-034: COMBAT_RESOLVE, any participant may resolve
  PendingChoice,  // GD-035: pendingEffects head owned by THIS viewer (any type)
  SchemeChoice,   // S09 UX: explicit EXACT-INSTANCE scheme pick (G opens,
                  // 1-9/click selects, Enter sends THAT card, G/Esc cancels).
                  // Fixes the silent first-playable auto-send: with two legal
                  // schemes G used to spend the wrong card/action.
};

struct UNMATCHED_API FS09DraftMove {
  FString FighterId;
  int32 DestX = -1;
  int32 DestY = -1;
};

/** Result intent produced by Confirm() - executed by the flow controller. */
struct UNMATCHED_API FS09ManeuverCommand {
  FString ManeuverId;
  TArray<FS08ManeuverMove> Moves;
  FString BoostCardId; // empty = no boost
};

struct UNMATCHED_API FS09DiscardCommand {
  FString PendingId;
  TArray<FString> CardInstanceIds; // EXACTLY pending.count unique own ids
};

/** GD-034 attack intent: attacker + target are living fighters in attack
 *  range (melee: adjacent; ranged: adjacent or sharing a zone - ENV-O6),
 *  attacker owned by the viewer, card is a viewer-hand instance of type
 *  ATTACK/VERSATILE/UNIVERSAL whose banner the attacker satisfies. */
struct UNMATCHED_API FS09AttackCommand {
  FString AttackerFighterId;
  FString CardInstanceId;
  FString TargetFighterId;
};

/** GD-034 defense intent: card is a viewer-hand DEFENSE/VERSATILE/UNIVERSAL
 *  instance whose banner the DEFENDING fighter satisfies. Empty card =
 *  explicit "no defense" (defender-side resolveCombat). */
struct UNMATCHED_API FS09DefenseCommand {
  bool bNoDefense = false;
  FString CardInstanceId;
};

/** GD-035 pending choice intent for the queue head. Payload per type
 *  (server ResolvePendingEffectDto):
 *  - MOVE/PLACE: FighterId + CellX/CellY (bHasCell);
 *  - CHOOSE_SPACE: CellX/CellY only (bHasCell);
 *  - TARGET_FIGHTER: FighterId only;
 *  - CHOOSE_ONE: OptionIndex only;
 *  - DISCARD_CARDS: CardIds = exactly `value` unique own-hand ids;
 *  - BOOST_CHOICE: CardIds = exactly ONE own-hand id;
 *  - DECK_TOP_PICK: CardIds = exactly `value` revealed ids (PICK) or the
 *    full top->bottom return order of ALL revealed ids (ORDER).
 *  DECLINE (bDecline) is only legal for optional effects. */
struct UNMATCHED_API FS09PendingChoiceCommand {
  FString EffectId;
  bool bDecline = false;
  FString FighterId;
  bool bHasCell = false;
  int32 CellX = -1;
  int32 CellY = -1;
  int32 OptionIndex = -1;
  TArray<FString> CardIds;
};

class UNMATCHED_API FS09CommandUi {
public:
  /** Server bannerAllows mirror (game-rules.validator): 'Harpy' matches
   *  'Harpies' / 'Harpy 2' (singular normalization + numeric suffix strip),
   *  'Arthur' matches 'King Arthur' (banner as a word of the full name). */
  static bool BannerAllowsFighter(const FString& Banner, const FString& FighterName);
  /** Server playScheme banner gate mirror: empty/'any' banner is universal;
   *  a named banner needs a LIVING fighter it matches; a banner that matches
   *  NO fighter of the game at all is allowed (server dirty-data tolerance).
   *  Keeps the auto driver from re-sending a scheme the server rejects
   *  (10:41 loop: Merlin-banner scheme after Merlin fell). */
  static bool SchemePlayableByLivingFighters(const FS09CardView& Card,
                                             const TArray<FS08BoardFighter>& Fighters,
                                             const FString& ViewerId);

  // ---- ENV-O6 / GAP-023: attack range = the server's legal set ----------
  /** Server normalizeAttackType: 'ranged' / 'range' is ranged, anything else
   *  (absent, 'melee', unknown) is melee. The fighter projection carries
   *  attackType for heroes and sidekicks (Hero.properties / sidekick data). */
  static bool IsRangedAttacker(const FS08BoardFighter& Attacker);
  /** Mirror of game-action-executor executeAttack range: the target is
   *  ADJACENT (board neighbour - a link on original-map boards, manhattan 1
   *  on grids), or the attacker is ranged and the two cells share at least
   *  one zone (multizone spaces are in all their zones; a zoneless cell
   *  shares none). Hero range abilities of the server registry
   *  (canAttackAtRange, e.g. Ms. Marvel / Muhammad Ali) are NOT mirrored -
   *  none of the Medusa/Harpy/Arthur/Merlin roster has one. Positions only:
   *  aliveness/ownership are the caller's gates. */
  static bool IsTargetInAttackRange(const FS08BoardModel& Board,
                                    const FS08BoardFighter& Attacker,
                                    const FS08BoardFighter& Target);
  /** True when the pair is legal only through a shared zone (not adjacent):
   *  the ranged-through-zone case the HUD/trace calls out. */
  static bool IsZoneOnlyTarget(const FS08BoardModel& Board, const FS08BoardFighter& Attacker,
                               const FS08BoardFighter& Target);
  /** Living fighters of the OTHER owner that AttackerId may legally attack,
   *  in Fighters order - the offer/highlight set of the draft, equal to what
   *  the server accepts. Empty for an unknown/dead attacker. */
  static TArray<FString> LegalAttackTargets(const FS08BoardModel& Board,
                                            const TArray<FS08BoardFighter>& Fighters,
                                            const FString& AttackerId);
  /** One S09AUTO auto-attack candidate: an own attacker and the ONE target
   *  the driver offers it (positions only - the draft gates re-check). */
  struct FAutoAttackPick {
    FString AttackerId;
    FString TargetId;
    bool bZoneOnly = false; // legal only through a shared zone (ranged, not linked)
  };
  /** S09AUTO auto-attack order (pure; the driver tries the picks in order
   *  with SelectAttacker/SelectTarget and takes the first that passes).
   *  For every living fighter of ViewerId in Fighters order: the first
   *  living enemy on an ADJACENT cell (a link on an original-map board,
   *  manhattan 1 on a grid); when it has none and the board carries a space
   *  topology, the first living enemy it may hit only through a shared zone
   *  (ranged attackers, ENV-O6). Grids keep the melee-only auto pick.
   *  bPreferRanged (opt-in '-S09Combat=...+ranged' plan token, ENV-MAPS
   *  P5a: the joiner's Merlin proof) moves the zone-only picks ahead of the
   *  adjacent ones, keeping the relative order inside both groups; without
   *  it the order is exactly the pre-P5a driver loop. */
  static TArray<FAutoAttackPick> AutoAttackPicks(const FS08BoardModel& Board,
                                                 const TArray<FS08BoardFighter>& Fighters,
                                                 const FString& ViewerId, bool bPreferRanged);
  /** S09AUTO 'ranged' plan maneuver (ENV-MAPS P5a, original-map boards
   *  only): a destination from where the RANGED mover has a zone-only
   *  target - no living enemy on a linked space, at least one living enemy
   *  sharing a zone. False (stay) when the mover is not ranged / dead, the
   *  board has no topology, its own cell already is such a position, or no
   *  legal destination qualifies. Candidates are ComputeReachableCells
   *  (Allowance; the same traversal/endpoint rules as every draft move)
   *  minus Reserved (endpoints of the other moves of the same draft); the
   *  pick is the fewest steps (BuildManeuverPath), then lower Y, lower X.
   *  OutTargetId = the first such enemy in Fighters order. */
  static bool PickRangedPosition(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                                 const FString& MoverId, int32 Allowance, const TSet<uint64>& Reserved,
                                 FIntPoint& OutCell, int32& OutSteps, FString& OutTargetId);

  ES09CommandMode Mode = ES09CommandMode::None;

  // Maneuver draft state
  FString PendingManeuverId;
  TArray<FS09DraftMove> Moves;
  FString BoostCardId;
  FString SelectedFighterId; // fighter whose destination the next cell click sets
  TSet<uint64> ReachableCells;

  // Discard draft state
  FS08PendingHandDiscard PendingDiscard;
  TSet<FString> DiscardSelection;

  // ---- GD-034 combat state (rebuilt from every snapshot) ----
  FS08CombatInfo Combat;        // parsed metadata.combatInfo of the window
  FS08PendingEffect PendingChoice; // pendingEffects head when owned by viewer
  bool bHasPendingChoice = false;
  TArray<FS08PendingEffect> PendingQueue; // whole server queue (HUD display)
  // AttackDraft selections (explicit A-opened local draft)
  FString AttackAttackerId;
  FString AttackTargetId;
  FString AttackCardId;
  // CombatDefense selection
  FString DefenseCardId;
  // ---- GD-035 pending-choice draft (rebuilt from every snapshot) ----
  FString PendingFighterId;   // MOVE/PLACE/TARGET_FIGHTER picked fighter
  // S09 UX: the EXACT own-hand SCHEME instance the viewer picked. Confirm
  // sends THIS id or nothing - a stale/invalid selection is rejected with a
  // reason and never substitutes a different playable scheme.
  FString SchemeCardId;
  bool bPendingCellSet = false;
  int32 PendingCellX = -1;    // MOVE/PLACE/CHOOSE_SPACE picked cell
  int32 PendingCellY = -1;
  int32 PendingOptionIndex = -1; // CHOOSE_ONE picked option
  TArray<FString> PendingCardIds; // DISCARD/BOOST/DECK_TOP_PICK picked ids
  TSet<uint64> PendingCells;   // legal cell hints for the CURRENT head type
  // Identity of the head the draft was built for: any change (id, stage,
  // mode or remaining chooseCount) resets the carried selection.
  FString PendingDraftKey;

  // Live inputs (pushed by the owner every applied snapshot)
  FString ViewerId;
  bool bCommandInFlight = false;
  /** Board of the last OnSnapshot (attack-range basis of the board-less
   *  overloads). Callers holding the live model pass it explicitly. */
  FS08BoardModel SnapshotBoard;

  /** Feed one authoritative applied snapshot. Clears/resumes drafts strictly
   *  from the server state (pending appeared -> draft open; pending gone ->
   *  draft reset). Returns true when the mode changed. */
  bool OnSnapshot(const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                  const TArray<FS08BoardFighter>& Fighters);

  /** True when beginManeuver may be sent: viewer's turn, action phase, no
   *  open pending, no command in flight (duplicate-begin gate). */
  bool CanBeginManeuver(const FS08Snapshot& Snapshot, FString& OutReason) const;

  /** Maneuver draft ops (no server calls; every one is reversible). */
  bool SelectFighter(const FString& FighterId, const FS08Snapshot& Snapshot,
                     const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters);
  /** Sets/overwrites the drafted destination for FighterId. Fails with
   *  OutReason when the cell is not reachable (movement + boost allowance). */
  bool SetDestination(const FString& FighterId, int32 X, int32 Y,
                      const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                      const TArray<FS08BoardFighter>& Fighters, FString& OutReason);
  void ClearMove(const FString& FighterId);
  /** Boost toggle: only an exact own-hand instance id is accepted. */
  bool ToggleBoostCard(const FString& InstanceId, const FS08Snapshot& Snapshot,
                       FString& OutReason);
  /** Local-only cancel: drops the draft; the server pendingManeuver stays
   *  (the committed draw is NOT reversed) - Resume re-enters the draft. */
  void CancelDraft();
  /** True while a pendingManeuver exists for the viewer (draft resumable). */
  bool CanResumeManeuver(const FS08Snapshot& Snapshot) const;

  /** Confirm gate: always legal while the draft is open (zero moves is a
   *  legal maneuver - ACC-006). Destination conflicts are rejected. */
  bool ConfirmManeuver(const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                       const TArray<FS08BoardFighter>& Fighters,
                       FS09ManeuverCommand& OutCommand, FString& OutReason);

  /** Discard draft ops. */
  bool ToggleDiscardCard(const FString& InstanceId, const FS08Snapshot& Snapshot,
                         FString& OutReason);
  bool ConfirmDiscard(const FS08Snapshot& Snapshot, FS09DiscardCommand& OutCommand,
                      FString& OutReason) const;

  /** Count still to select in the open discard draft. */
  int32 DiscardRemaining() const {
    return PendingDiscard.Count - DiscardSelection.Num();
  }

  // ---- GD-034: attack draft ----
  /** True when the viewer may OPEN an attack draft: own turn, action phase,
   *  no open server pending, nothing in flight. (The draft itself also needs
   *  an enemy in range + legal card - see LegalAttackTargets.) */
  bool CanOpenAttackDraft(const FS08Snapshot& Snapshot, FString& OutReason) const;
  /** Attack draft ops. SelectAttacker/SelectTarget validate attack range
   *  (IsTargetInAttackRange over Board) and ownership against the
   *  authoritative snapshot. */
  bool SelectAttacker(const FString& FighterId, const FS08BoardModel& Board,
                      const TArray<FS08BoardFighter>& Fighters, FString& OutReason);
  bool SelectTarget(const FString& FighterId, const FS08BoardModel& Board,
                    const TArray<FS08BoardFighter>& Fighters, FString& OutReason);
  /** Pre-ENV overloads: use the board of the last OnSnapshot (an empty grid
   *  before the first snapshot = the old manhattan-1 melee rule). */
  bool SelectAttacker(const FString& FighterId, const TArray<FS08BoardFighter>& Fighters,
                      FString& OutReason) {
    return SelectAttacker(FighterId, SnapshotBoard, Fighters, OutReason);
  }
  bool SelectTarget(const FString& FighterId, const TArray<FS08BoardFighter>& Fighters,
                    FString& OutReason) {
    return SelectTarget(FighterId, SnapshotBoard, Fighters, OutReason);
  }
  /** Attack card toggle: hand instance of type ATTACK/VERSATILE/UNIVERSAL
   *  whose banner the drafted attacker satisfies. */
  bool ToggleAttackCard(const FString& InstanceId, const FS08Snapshot& Snapshot,
                        const TArray<FS08BoardFighter>& Fighters, FString& OutReason);
  bool ConfirmAttack(const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                     const TArray<FS08BoardFighter>& Fighters,
                     FS09AttackCommand& OutCommand, FString& OutReason) const;
  bool ConfirmAttack(const FS08Snapshot& Snapshot, const TArray<FS08BoardFighter>& Fighters,
                     FS09AttackCommand& OutCommand, FString& OutReason) const {
    return ConfirmAttack(Snapshot, SnapshotBoard, Fighters, OutCommand, OutReason);
  }

  // ---- GD-034: defense window (COMBAT, viewer is defender) ----
  /** Defense card toggle: DEFENSE/VERSATILE/UNIVERSAL hand instance whose
   *  banner the ATTACKED fighter (combatInfo.targetFighterId) satisfies. */
  bool ToggleDefenseCard(const FString& InstanceId, const FS08Snapshot& Snapshot,
                         const TArray<FS08BoardFighter>& Fighters, FString& OutReason);
  /** bNoDefense=true validates the explicit defender resolve ("no defense");
   *  otherwise the selected card must still be legal. */
  bool ConfirmDefense(const FS08Snapshot& Snapshot, const TArray<FS08BoardFighter>& Fighters,
                      FS09DefenseCommand& OutCommand, FString& OutReason) const;
  /** Attacker-side resolve attempt in COMBAT: NEVER legal (server: 'Defender
   *  has not responded yet'). Kept explicit for the gate test. A non-empty
   *  pending queue blocks resolve on EITHER side (server gate: 'Resolve the
   *  pending choice first'). */
  bool CanResolveCombat(const FS08Snapshot& Snapshot, FString& OutReason) const;

  // ---- GD-035: viewer-owned pending queue head (any type) ----
  /** Legal fighter ids for the head type (ownership/banner/list rules of the
   *  server resolver, incl. revive-PLACE and Skirmish anyOwner). */
  bool PendingLegalFighters(const TArray<FS08BoardFighter>& Fighters,
                            TArray<FString>& OutIds) const;
  /** Legal destination cells for MOVE/PLACE/CHOOSE_SPACE (server reachability
   *  + zone/anchor rules). Empty set for fighter/card/option types. */
  TSet<uint64> ComputePendingCells(const FS08Snapshot& Snapshot,
                                   const FS08BoardModel& Board,
                                   const TArray<FS08BoardFighter>& Fighters) const;
  /** Fighter pick for MOVE/PLACE/TARGET_FIGHTER (revalidated per snapshot). */
  bool SelectPendingFighter(const FString& FighterId, const FS08Snapshot& Snapshot,
                            const TArray<FS08BoardFighter>& Fighters, FString& OutReason);
  /** Cell pick for MOVE/PLACE/CHOOSE_SPACE (must be in ComputePendingCells). */
  bool SelectPendingCell(int32 X, int32 Y, const FS08Snapshot& Snapshot,
                         const FS08BoardModel& Board,
                         const TArray<FS08BoardFighter>& Fighters, FString& OutReason);
  /** Option pick for CHOOSE_ONE (index into PendingChoice.Options). */
  bool SelectPendingOption(int32 OptionIndex, FString& OutReason);
  /** Card toggle: DISCARD_CARDS/BOOST_CHOICE take exact OWN-HAND ids,
   *  DECK_TOP_PICK takes exact revealedCards ids (owner-only projection);
   *  ORDER builds the return order by pick sequence. */
  bool TogglePendingCard(const FString& InstanceId, const FS08Snapshot& Snapshot,
                         FString& OutReason);
  /** Exact own-hand ids (DISCARD_CARDS/BOOST_CHOICE legality basis). */
  TArray<FString> PendingOwnHandIds(const FS08Snapshot& Snapshot) const {
    return OwnHandIds(Snapshot);
  }
  /** Exact-count pick plan for the open card head: the candidate pool
   *  (revealed ids for DECK_TOP_PICK in board order; exact own-hand ids
   *  otherwise) and how many DISTINCT ids the answer requires (ORDER = the
   *  whole pool, BOOST = 1, else the server `value`, default 2/1). The
   *  S09AUTO driver and the HUD hint derive the SAME number from here;
   *  legality of each id and of the final count stays in
   *  TogglePendingCard/ConfirmPendingChoice. */
  bool PendingCardPickPlan(const FS08Snapshot& Snapshot, TArray<FString>& OutPool,
                           int32& OutCount) const;
  /** Reveal entries of a DECK_TOP_PICK head decoded for the OWNER only;
   *  empty for the opponent's projection (revealedCards never ships). */
  bool PendingRevealedCards(TArray<FS09CardView>& OutCards) const;
  bool ConfirmPendingChoice(const FS08Snapshot& Snapshot,
                            bool bDecline, FS09PendingChoiceCommand& OutCommand,
                            FString& OutReason) const;

  // ---- S09 UX: explicit exact-instance scheme choice ----
  /** True when G may OPEN the scheme picker: viewer's turn, action phase,
   *  no open server pending, nothing in flight (mirror of the server
   *  playScheme gate). Mode must be None. */
  bool CanOpenSchemeChoice(const FS08Snapshot& Snapshot, FString& OutReason) const;
  /** Count of own-hand SCHEME cards the living roster may play (banner gate).
   *  The picker opens only when >= 1 - an empty draft is noise. */
  int32 CountPlayableSchemes(const FS08Snapshot& Snapshot,
                             const TArray<FS08BoardFighter>& Fighters) const;
  void OpenSchemeChoice();
  /** Select/switch the EXACT scheme instance. Rejects non-own, hidden,
   *  non-SCHEME and dead-banner cards with a reason (server gate mirror). */
  bool ToggleSchemeCard(const FString& InstanceId, const FS08Snapshot& Snapshot,
                        const TArray<FS08BoardFighter>& Fighters, FString& OutReason);
  /** Confirm gate: revalidates turn/phase/hand/banner against the FRESH
   *  snapshot and returns the EXACT selected instance id. A stale selection
   *  is rejected - NEVER substituted with another playable scheme. */
  bool ConfirmScheme(const FS08Snapshot& Snapshot,
                     const TArray<FS08BoardFighter>& Fighters,
                     FString& OutInstanceId, FString& OutReason) const;
  /** Local-only cancel: nothing was sent to the server. */
  void CancelSchemeChoice();

private:
  TArray<FString> OwnHandIds(const FS08Snapshot& Snapshot) const;
  /** boostValue of the currently selected boost card (0 = none/unknown). */
  int32 BoostValueFromHand(const FS08Snapshot& Snapshot) const;
  const FS08BoardFighter* FindOwnFighter(const TArray<FS08BoardFighter>& Fighters,
                                         const FString& FighterId) const;
  /** GD-034 helpers. */
  const FS08BoardFighter* FindFighter(const TArray<FS08BoardFighter>& Fighters,
                                      const FString& FighterId) const;
  /** GD-035: resets the pending draft (head changed / closed). */
  void ResetPendingDraft();
  /** Head identity the draft belongs to (id + stage + mode + chooseCount). */
  FString PendingHeadKey() const;
  /** Server MOVE reachability: BFS with `allowance` steps; enemies block the
   *  path unless bCanPassThroughEnemies; destination must be endpoint-free
   *  (own current cell included = zero-step legal resolve). */
  TSet<uint64> PendingMoveCells(const FS08BoardModel& Board,
                                const TArray<FS08BoardFighter>& Fighters,
                                const FS08BoardFighter& Mover, int32 Allowance,
                                bool bPassThroughEnemies) const;
  /** True when (X,Y) shares a board zone with the cell of the living fighter
   *  named ZoneFighterName (PLACE/CHOOSE_SPACE stage 1 rule). */
  bool CellSharesZoneWith(const FS08BoardModel& Board,
                          const TArray<FS08BoardFighter>& Fighters,
                          const FString& ZoneFighterName, int32 X, int32 Y) const;
};

// GD-033: local command-state machine for the maneuver stages and the
// end-of-turn discard-to-limit choice. Pure logic (headless-testable):
// legal choices are derived ONLY from the authoritative applied snapshot
// (pending ids, own hand, own living fighters, board reachability); the
// caller owns transport (FS08FlowController) and passes its in-flight flag.
//
// Maneuver contract (ACC-006 / GD-013):
//   beginManeuver  -> server draws ONE card, opens metadata.pendingManeuver;
//   local draft    -> zero or more own fighters, one destination each, in
//                     send order (MS-T-05: evaluated sequentially - each move
//                     on the positions after the previous ones - with the
//                     canonical path of the board model: links on an
//                     original-map board, orthogonal on a grid; status
//                     Ok / NeedBoost / Conflict by the absolute RequiredBoost),
//                     optional boost = an exact own-hand instance id with a
//                     printed BOOST (the card drawn by begin is legal - it is
//                     already in the hand);
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

// ---- MS-T-05: sequential draft evaluation (docs/game-design/move-selection
// 04 §3.2, §4.4; reference: backend game-engine/movement/canonical-path.ts
// evaluateDraft). The moves are evaluated in send order on the positions after
// the previous moves; reach uses base + max(selected BOOST, max hand BOOST);
// the absolute RequiredBoost = max(0, len(path) - base) decides Ok/NeedBoost.

enum class ES09DraftMoveStatus : uint8 { Ok, NeedBoost, Conflict };

/** Why a drafted move is a Conflict (backend DraftConflict). */
enum class ES09DraftConflict : uint8 { None, Missing, NotYours, Defeated, Immobilized, Duplicate, NoPath };

/** A why.* reason key (03 §8.2) with its arguments ({cell}, {need}, {have},
 *  {n}, {fighterName}). The RU/EN texts come with MS-T-06 / MS-T-28. */
struct UNMATCHED_API FS09Reason {
  FName Key;
  TMap<FString, FString> Args;

  bool IsSet() const { return !Key.IsNone(); }
  void Reset() {
    Key = NAME_None;
    Args.Reset();
  }
  static FS09Reason Make(const TCHAR* InKey) {
    FS09Reason Reason;
    Reason.Key = FName(InKey);
    return Reason;
  }
  FS09Reason& Arg(const TCHAR* Name, const FString& Value) {
    Args.Add(Name, Value);
    return *this;
  }
  FS09Reason& Arg(const TCHAR* Name, int32 Value) { return Arg(Name, FString::FromInt(Value)); }
  /** English placeholder text followed by " [key]" - the trace / OutReason
   *  form (tests match on it). */
  FString Describe() const;
  /** MS-T-06: the toast text BY KEY - the EN text of S08WhyText (the "en"
   *  column of why-reasons.json; RU with MS-T-28) with the arguments, prefixed
   *  by the space it names ("M13: An enemy is here") - a CellLabel, never grid
   *  coordinates (B-04). */
  FString Text() const;
};

struct UNMATCHED_API FS09DraftMove {
  FString FighterId;
  int32 DestX = -1;
  int32 DestY = -1;
  // ---- MS-T-05 evaluation (FS09DraftEval::Evaluate rewrites these on every
  // draft operation; DestX/DestY and the array order are the input) ----
  int32 Order = 0;                 // index in moves[] (send order)
  TArray<FIntPoint> Path;          // canonical path WITHOUT the start; empty = stay or Conflict
  ES09DraftMoveStatus Status = ES09DraftMoveStatus::Ok;
  ES09DraftConflict Conflict = ES09DraftConflict::None;
  int32 RequiredBoost = 0;         // absolute BOOST: max(0, len - Base); 0 for Conflict
  int32 Base = 0;                  // FighterMovement of the fighter
  int32 Allowance = 0;             // Base + selected BOOST (the badge "steps/allowance")
  FS09Reason Reason;               // why.* of a NeedBoost / Conflict move

  /** Badge data of 03 §4.3: "{steps}/{allowance}" and, when the move needs a
   *  bigger boost, " · need +{RequiredBoost}" ("6/5 · need +3"). Empty for a
   *  Conflict. English until MS-T-28. */
  FString BadgeText() const;
};

/** One own-hand card as the boost model sees it (backend DraftHandCard). */
struct UNMATCHED_API FS09BoostCard {
  FString InstanceId;
  bool bHasBoost = false; // a printed BOOST (JSON number); null is never offered (MS-D-20)
  int32 Boost = 0;
  /** "+N" ("+0" for a zero BOOST); empty without a printed BOOST. */
  FString Label() const { return bHasBoost ? FString::Printf(TEXT("+%d"), Boost) : FString(); }
};

/** MS-T-07: where a draft operation came from - the src= of MS-DRAFT (04 §9). */
enum class ES09InputSource : uint8 { Click, Key, Auto, Snapshot };

/** MS-T-07 (04 §4.4, MS-R-18): one undo record - the draft before an
 *  operation (destinations and order; the evaluation is recomputed). */
struct UNMATCHED_API FS09DraftOp {
  TArray<FS09DraftMove> Moves;
  FString BoostCardId;
};

/** MS-T-07 (04 §4.4, MS-S-03): the target picked before the maneuver began. */
struct UNMATCHED_API FS09PreDraft {
  FString FighterId;
  int32 X = -1;
  int32 Y = -1;
  bool bSet = false;
  /** By the hand BEFORE the draw - information only (MS-E-82). */
  ES09DraftMoveStatus Status = ES09DraftMoveStatus::Ok;
  int32 RequiredBoost = 0;
  /** src= of the move it becomes when the draft opens. */
  ES09InputSource Source = ES09InputSource::Click;
};

/** Plate tiers of one fighter on one work state (04 §3.2, MS-E-80): base =
 *  endpoints at 1..Base+s steps, boost = Base+s+1..Base+M (empty when s >= M);
 *  Reach is the BFS with Base + max(s, M) steps (the hover preview reuses it). */
struct UNMATCHED_API FS09ReachTiers {
  bool bValid = false;
  FString FighterId;
  FIntPoint Start = FIntPoint(-1, -1);
  int32 Base = 0;
  int32 BaseSteps = 0;
  int32 BoostSteps = 0;
  TArray<FIntPoint> BaseTier;  // sorted by K
  TArray<FIntPoint> BoostTier; // sorted by K
  FS08ReachMap Reach;

  /** The "+N" chip of a boost-tier cell: dist - Base (absolute BOOST); 0 for
   *  any other cell. */
  int32 ChipAt(const FIntPoint& Cell) const;
};

/** Result of FS09DraftEval::Evaluate (the per-move fields live in the
 *  evaluated FS09DraftMove array). */
struct UNMATCHED_API FS09DraftEval {
  int32 SelectedBoost = 0; // BOOST of the selected card (no card / no BOOST -> 0)
  int32 MaxBoost = 0;      // max BOOST of the hand cards that have one, 0 if none
  /** Tiers of each move's fighter on the positions before its move (same
   *  index as the moves); invalid for the early Conflicts (missing,
   *  not-yours, defeated, immobilized, duplicate). */
  TArray<FS09ReachTiers> Tiers;
  /** work_n: the fighters after every Ok / NeedBoost move. */
  TArray<FS08BoardFighter> Work;
  int32 NumOk = 0;
  int32 NumNeedBoost = 0;
  int32 NumConflict = 0;
  /** MS-E-14 / MS-E-79: max RequiredBoost over the NeedBoost moves (0 = no
   *  highlight) and the hand cards with BOOST >= it, except the selected one. */
  int32 HighlightMinBoost = 0;
  TArray<FString> HighlightCardIds;

  bool IsConfirmable() const { return NumNeedBoost == 0 && NumConflict == 0; }

  /** The viewer's own hand as boost cards (snapshot order). */
  static TArray<FS09BoostCard> BoostHand(const FS08Snapshot& Snapshot, const FString& ViewerId);
  static int32 SelectedBoostOf(const TArray<FS09BoostCard>& Hand, const FString& BoostCardId);
  static int32 MaxBoostOf(const TArray<FS09BoostCard>& Hand);
  /** backend isImmobilized: an effect of type 'immobilized' (exact). */
  static bool IsImmobilized(const FS08BoardFighter& Fighter);
  /** Tiers of FighterId on Work with BOOST s (selected) and M (max hand). */
  static FS09ReachTiers ComputeTiers(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Work,
                                     const FString& FighterId, int32 SelectedBoost, int32 MaxBoost);
  /** Why Dest cannot end Mover's move on Work (the BFS with Base + max(s, M)
   *  found no path): not a board space, an enemy / an ally on it (an ally
   *  whose own drafted move ends on Mover's cell = a swap, MS-E-35; an ally
   *  that leaves it later in the order gets the "orderHint" argument,
   *  MS-E-34), a path longer than the best boost (need / have) or no path. */
  static FS09Reason DestinationReason(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Work,
                                      const FS08BoardFighter& Mover, const FIntPoint& Dest, int32 Base,
                                      int32 SelectedBoost, int32 MaxBoost, const TArray<FS09DraftMove>& Draft);
  /** backend evaluateDraft over Moves (in place: Order, Path, Status,
   *  Conflict, RequiredBoost, Base, Allowance, Reason). ActorId (empty = no
   *  check) rejects fighters of another owner; the mover needs only
   *  health > 0 (MS-E-77), blockers use IsAliveBlocker (MS-E-24). */
  static FS09DraftEval Evaluate(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                                TArray<FS09DraftMove>& Moves, const TArray<FS09BoostCard>& Hand,
                                const FString& BoostCardId, const FString& ActorId);
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
  /** The draft in send order (moves[] of the command). Every draft operation
   *  re-evaluates all moves (FS09DraftEval): status, path, RequiredBoost. */
  TArray<FS09DraftMove> Moves;
  FString BoostCardId;
  FString SelectedFighterId; // fighter whose destination the next cell click sets
  /** Legacy reach set of the selected fighter (the TASK-022 ring): its own
   *  cell plus the base tier of SelectedTiers. */
  TSet<uint64> ReachableCells;
  // ---- MS-T-05 ----
  /** Evaluation of Moves after the last draft operation. */
  FS09DraftEval Eval;
  /** Tiers of the selected fighter: on the positions before its move when it
   *  has one, else after every move (a new move goes last) - 04 §3.2. */
  FS09ReachTiers SelectedTiers;
  /** The viewer's hand as boost cards (refreshed by every snapshot / op that
   *  passes one). */
  TArray<FS09BoostCard> DraftHand;
  /** +1 on every draft operation (assign, clear, boost, order, snapshot). */
  uint32 DraftRevision = 0;
  /** Reason of the last refused draft operation (why.* key + args). */
  FS09Reason LastReason;
  /** Draft trace lines (MS-DRAFT, MS-PATH, MS-DATA) also written to FS08Trace;
   *  the last 64 are kept for tests. */
  TArray<FString> DraftTrace;
  // ---- MS-T-04: draft cache by maneuverId (MS-R-55, 04 §5) ----
  /** Write-through of the draft (ExportDraft) whenever it changes; the owner
   *  binds it to FS08FlowController::StoreManeuverDraft. Unbound = no cache
   *  (pure tests). */
  TFunction<void(const FS08ManeuverDraftCache&)> StoreDraftHook;
  /** Read-back when a snapshot opens a pendingManeuver id this UI holds no
   *  draft for (FS08FlowController::RecallManeuverDraft): true with the
   *  cached draft of exactly that id. Another id never restores anything. */
  TFunction<bool(const FString& /*ManeuverId*/, FS08ManeuverDraftCache&)> RecallDraftHook;
  // ---- MS-T-07: input (03 §3, 04 §4.4) ----
  /** src= of the next draft operations (the input layer sets click / key;
   *  drivers keep auto; snapshot re-evaluations write snapshot). */
  ES09InputSource DraftSource = ES09InputSource::Auto;
  /** MS-R-18: undo records, at most MaxUndo (the 33rd evicts the oldest,
   *  MS-E-94). An applied snapshot with a new seq is a barrier (MS-E-95) and
   *  another maneuverId clears it; a server rejection leaves it (MS-E-113). */
  static constexpr int32 MaxUndo = 32;
  TArray<FS09DraftOp> UndoStack;
  /** MS-S-03: the pre-draft target (moves into the draft when it opens). */
  FS09PreDraft PreDraft;

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
  /** Fighters of the last OnSnapshot: the re-evaluation basis of the draft
   *  operations that take no model (ClearMove, the 3-argument boost toggle). */
  TArray<FS08BoardFighter> SnapshotFighters;

  /** Feed one authoritative applied snapshot. Clears/resumes drafts strictly
   *  from the server state (pending appeared -> draft open; pending gone ->
   *  draft reset). Returns true when the mode changed. */
  bool OnSnapshot(const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                  const TArray<FS08BoardFighter>& Fighters);

  /** True when beginManeuver may be sent: viewer's turn, action phase, no
   *  open pending, no command in flight (duplicate-begin gate). */
  bool CanBeginManeuver(const FS08Snapshot& Snapshot, FString& OutReason) const;
  /** MS-T-06: the same gate with the why.* key of the refusal (03 §8.2):
   *  why.state.changed (over), why.draft.open (a draft is open - the M toast
   *  is ms.begin.already), why.wait.opponent.choice (the pending head belongs
   *  to the opponent, MS-E-47), why.state.changed (own pending choice /
   *  discard open), why.syncing (in flight), why.not.your.turn,
   *  why.no.actions (metadata.actionsRemaining 0), why.maneuver.not.open
   *  (phase). */
  bool CanBeginManeuver(const FS08Snapshot& Snapshot, FString& OutReason, FS09Reason& OutKey) const;
  /** DE-015 (W-22, SD-44; 02 §4.10): why endTurn may not be sent now - the
   *  one answer of the END TURN button AND the E key (CUE-004 by key); an
   *  unset reason = send. In order: why.state.changed (over), why.syncing (in
   *  flight), why.not.your.turn, why.draft.open (a maneuver draft or an open
   *  pendingManeuver), why.discard.count {need} {have} (discard to the limit),
   *  why.wait.opponent.choice / why.choice.required (a pending choice),
   *  why.wait.defender (combat window), why.actions.remaining {n} (server
   *  ACTIONS_REMAINING: before both actions), why.syncing (no action phase or
   *  actionsRemaining unknown). After the second action the server ends the
   *  turn itself - there is no "pass" (PASS_NOT_ALLOWED). */
  FS09Reason EndTurnReason(const FS08Snapshot& Snapshot) const;

  /** Maneuver draft ops (no server calls; every one is reversible).
   *  SelectFighter refuses a fighter CanMoveFighter refuses (LastReason,
   *  e.g. why.immobilized - MS-R-05) and keeps the previous selection. */
  bool SelectFighter(const FString& FighterId, const FS08Snapshot& Snapshot,
                     const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters);
  /** MS-T-05: what (X, Y) would be as FighterId's destination - evaluated on
   *  the positions before its move (it keeps its place in the order) or, for
   *  a fighter without a move, after every move (a new move goes last).
   *  True with OutMove (Path, Status Ok / NeedBoost, RequiredBoost, Base,
   *  Allowance) when a path exists within Base + max(selected, max hand
   *  BOOST); false with OutReason (why.*) otherwise. Own cell = an empty
   *  path ("stay"). Does not change the draft. */
  bool EvaluateDestination(const FString& FighterId, int32 X, int32 Y, const FS08BoardModel& Board,
                           const TArray<FS08BoardFighter>& Fighters, FS09DraftMove& OutMove,
                           FS09Reason& OutReason) const;
  /** Sets/overwrites the drafted destination for FighterId (EvaluateDestination
   *  decides): an overwrite keeps the move's place in the order (MS-E-38), a
   *  new move goes last (MS-E-114). A cell in the boost tier is accepted with
   *  the NeedBoost status (MS-E-14). The fighter's own cell is "stay": its
   *  move (if any) is cleared and nothing is recorded (MS-E-16, B-01). Fails
   *  with OutReason (and LastReason) when CanMoveFighter refuses or no path
   *  exists within the best boost. */
  bool SetDestination(const FString& FighterId, int32 X, int32 Y,
                      const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                      const TArray<FS08BoardFighter>& Fighters, FString& OutReason);
  /** Drops FighterId's move (the later moves move up one place) and
   *  re-evaluates the draft on the last snapshot's model. */
  void ClearMove(const FString& FighterId);
  /** MS-R-17 (Ctrl+Up = -1, Ctrl+Down = +1): moves FighterId's move Delta
   *  places in the send order and re-evaluates every move. No action (false)
   *  for a fighter without a move, the first move up and the last move down
   *  (MS-E-96). */
  bool MoveOrder(const FString& FighterId, int32 Delta, const FS08Snapshot& Snapshot,
                 const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters);
  /** Index of FighterId's move in Moves, INDEX_NONE without one. */
  int32 MoveIndexOf(const FString& FighterId) const;
  /** Drops the selection (the draft stays): SelectedFighterId, SelectedTiers
   *  and ReachableCells together. */
  void DeselectFighter();
  // ---- MS-T-07 ----
  /** MS-S-02 (no draft open): inspect an own fighter - its tiers by the hand
   *  BEFORE the draw (information only). Refused like SelectFighter. */
  bool InspectFighter(const FString& FighterId, const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                      const TArray<FS08BoardFighter>& Fighters);
  /** MS-S-03 (no draft open): the pre-draft target of FighterId - a space its
   *  move can end on with the best BOOST of the current hand (Ok in the base
   *  tier, NeedBoost "needs boost +k" in the boost tier, MS-E-82). The same
   *  target again sets bOutUnchanged and changes nothing (MS-E-83); the own
   *  space clears the target. False with LastReason. */
  bool SetPreDraft(const FString& FighterId, int32 X, int32 Y, const FS08Snapshot& Snapshot,
                   const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters, bool& bOutUnchanged);
  void ClearPreDraft() { PreDraft = FS09PreDraft(); }
  /** MS-R-18 (Backspace / Ctrl+Z): the draft before its last operation,
   *  re-evaluated. False on an empty stack. */
  bool Undo(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters);
  /** Delete: ClearMove on the live model. */
  void ClearMove(const FString& FighterId, const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters);
  /** Tab / Shift+Tab (MS-R-04): the next / previous own fighter after the
   *  selected one in fighters[] order that CanMoveFighter accepts (the dead
   *  and the immobilized are skipped); empty without one. */
  FString CycleFighter(const TArray<FS08BoardFighter>& Fighters, int32 Direction) const;
  /** DE-017 (MS-R-75, V-17): the own fighters CanMoveFighter accepts, in
   *  fighters[] order - the candidate rings of MS-S-06 and the Tab ring. The
   *  dead and the immobilized are not candidates. */
  TArray<FString> MovableFighterIds(const TArray<FS08BoardFighter>& Fighters) const;
  /** DE-017 (MS-R-75): the draft of THIS pendingManeuver.id auto-selected its
   *  only movable fighter when it opened (MS-S-07 at once). Once per id: Esc
   *  back to MS-S-06 does not repeat it, a later snapshot does not either. */
  bool bAutoSelected = false;
  /** MS-R-71: fighters that leave a space another drafted move ends on - drawn
   *  at 50 % under that move's ghost (the drawing comes with the ghosts, MS-T-10). */
  TArray<FString> FadedFighters(const TArray<FS08BoardFighter>& Fighters) const;
  /** Own fighters with health > 0 on the board (MS-S-04: who takes the
   *  exhaustion damage). */
  int32 OwnLivingFighters(const TArray<FS08BoardFighter>& Fighters) const;
  /** MS-S-01/02/03 input may act now: the viewer's action phase with actions
   *  left (CanKeepPreDraft), no pending choice and no combat window. */
  bool CanPreDraftNow(const FS08Snapshot& Snapshot) const {
    return CanKeepPreDraft(Snapshot) && !bHasPendingChoice && !Combat.bPresent;
  }
  /** MS-S-02/03 survive a snapshot while the viewer may still begin. */
  bool CanKeepPreDraft(const FS08Snapshot& Snapshot) const;
  /** MS-T-04 (MS-R-05, MS-E-40/77): may the viewer move FighterId in this
   *  maneuver? Own fighter on the board with health > 0 (the mover role:
   *  isDefeated with health > 0 still moves, as the server), not
   *  immobilized. False with why.client.desync / why.fighter.not.yours /
   *  why.fighter.defeated / why.immobilized {fighterName} - the panel greys
   *  the fighter with that reason. */
  bool CanMoveFighter(const FString& FighterId, const TArray<FS08BoardFighter>& Fighters,
                      FS09Reason& OutReason) const;
  /** MS-T-06: the toast reason of a classified server rejection - its why.*
   *  key with every argument the text needs: the space by CellLabel, the
   *  fighter (the move ending on the space, a drafted immobilized one, the
   *  selected / pending fighter), need / have from the draft model; a missing
   *  need with no path at all becomes why.cell.no.path. No "?" placeholder. */
  FS09Reason RejectionReason(const FS08Rejection& Rejection, const FS08BoardModel& Board,
                             const TArray<FS08BoardFighter>& Fighters) const;
  /** The current draft in the cache format (empty outside a maneuver draft). */
  FS08ManeuverDraftCache ExportDraft() const;
  /** Boost toggle: only an exact own-hand instance id with a printed BOOST is
   *  accepted (null -> why.boost.no.value, MS-D-20); another card replaces
   *  the selected one; the draft is re-evaluated in the same call (MS-R-15).
   *  The 3-argument form re-evaluates on the last snapshot's model. */
  bool ToggleBoostCard(const FString& InstanceId, const FS08Snapshot& Snapshot,
                       FString& OutReason);
  bool ToggleBoostCard(const FString& InstanceId, const FS08Snapshot& Snapshot,
                       const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                       FString& OutReason);
  /** The hand cards offered as a boost (a printed BOOST, "+0" included). */
  TArray<FS09BoostCard> BoostOffers() const;
  /** Local-only cancel: drops the draft; the server pendingManeuver stays
   *  (the committed draw is NOT reversed) - Resume re-enters the draft. */
  void CancelDraft();
  /** True while a pendingManeuver exists for the viewer (draft resumable). */
  bool CanResumeManeuver(const FS08Snapshot& Snapshot) const;

  /** Confirm gate: legal while the draft is open (zero moves is a legal
   *  maneuver - ACC-006) and every move is Ok after a fresh evaluation; a
   *  NeedBoost or Conflict move blocks it with its reason (MS-R-16). The
   *  command carries the canonical paths; a zero-length move is never in it
   *  (MS-R-44). */
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
  /** DE-018 (SD-04/SD-16): the defender holds at least one hand card the attacked fighter may defend with -
   *  otherwise the defense slot reads why.defense.none ("Nothing to defend with"). */
  bool HasLegalDefenseCard(const FS08Snapshot& Snapshot, const TArray<FS08BoardFighter>& Fighters) const;
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
   *  + zone/anchor rules). Empty set for fighter/card/option types. MOVE:
   *  FS08BoardModel::ComputeReachMap with `value` steps (absent -> 1, 0 -> 0)
   *  - the mover's cell plus every endpoint (04 §3.3). */
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
  const FS08BoardFighter* FindOwnFighter(const TArray<FS08BoardFighter>& Fighters,
                                         const FString& FighterId) const;
  /** MS-T-05: Eval + the evaluated Moves, then SelectedTiers / ReachableCells;
   *  +1 DraftRevision. */
  void ReevaluateDraft(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters);
  /** Tiers of the selected fighter on its work state (see SelectedTiers). */
  void RefreshSelectedTiers(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters);
  /** The fighters before FighterId's move (it keeps its place) or after every
   *  move (no move yet). */
  TArray<FS08BoardFighter> WorkStateFor(const FString& FighterId, const FS08BoardModel& Board,
                                        const TArray<FS08BoardFighter>& Fighters) const;
  /** Resets the evaluation, the selected tiers and the reach set. */
  void ResetDraftEval();
  /** MS-T-04: drops the whole maneuver draft (id, moves, boost, selection,
   *  evaluation) - no pendingManeuver of the viewer, or another id. */
  void ResetManeuverDraft();
  /** MS-T-04: StoreDraftHook(ExportDraft()) when the draft changed since the
   *  last store. */
  void SyncDraftCache();
  /** MS-T-07: the draft before an operation goes on the undo stack. */
  void PushUndo(const TArray<FS09DraftMove>& BeforeMoves, const FString& BeforeBoost);
  /** MS-R-02: the pre-draft target becomes the first move of the freshly
   *  opened draft (Ok / NeedBoost by the new hand) or why.predraft.lost. */
  void CarryPreDraft(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters);
  int32 LastSnapshotSeq = INDEX_NONE;
  /** MS-T-04: "MS-DATA dirtyDefeated fighter=<id>" once per maneuver for a
   *  mover with isDefeated and health > 0 (04 §9). */
  void TraceDirtyDefeated(const TArray<FS08BoardFighter>& Fighters, const FString& FighterId);
  FS08ManeuverDraftCache LastStoredDraft;
  /** False until the first store: a fresh UI always reports its (possibly
   *  empty) draft once, so a stale cache of a closed maneuver is cleared. */
  bool bDraftCacheSynced = false;
  TSet<FString> DirtyDefeatedTraced;
  /** FS08Trace + DraftTrace (last 64). */
  void DraftTraceLine(const FString& Line);
  /** "MS-DRAFT op=<Op> rev=<n> ..." (04 §9) for FighterId's move (or the
   *  summary); an assign also writes MS-PATH. */
  void TraceDraftOp(const TCHAR* Op, const FString& FighterId, const FS08BoardModel& Board);
  /** GD-034 helpers. */
  const FS08BoardFighter* FindFighter(const TArray<FS08BoardFighter>& Fighters,
                                      const FString& FighterId) const;
  /** GD-035: resets the pending draft (head changed / closed). */
  void ResetPendingDraft();
  /** Head identity the draft belongs to (id + stage + mode + chooseCount). */
  FString PendingHeadKey() const;
  /** Server MOVE reachability (ComputeReachMap): `allowance` steps; living
   *  enemies of the mover's owner (IsAliveBlocker) block unless
   *  bCanPassThroughEnemies; destination endpoint-free (own current cell
   *  included = zero-step legal resolve). */
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

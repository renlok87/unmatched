#include "S09ManeuverUi.h"
#include "Dom/JsonObject.h"
#include "S09HudModel.h"

namespace {
bool OwnHandCards(const FS08Snapshot& Snapshot, const FString& ViewerId,
                  TArray<FS09CardView>& OutCards) {
  OutCards.Reset();
  if (!Snapshot.HandZones.IsValid()) return false;
  const TSharedPtr<FJsonObject> Hands = Snapshot.HandZones->AsObject();
  if (!Hands.IsValid()) return false;
  const TSharedPtr<FJsonValue> Hand = Hands->TryGetField(ViewerId);
  if (!Hand.IsValid()) return false;
  const TSharedPtr<FJsonObject> HandObject = Hand->AsObject();
  if (!HandObject.IsValid()) return false;
  const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
  if (!HandObject->TryGetArrayField(TEXT("cards"), Cards) || !Cards) return false;
  for (const TSharedPtr<FJsonValue>& Value : *Cards) {
    FS09CardView Card;
    if (FS09HudFactory::CardFromJson(Value, Card)) OutCards.Add(MoveTemp(Card));
  }
  return true;
}

bool PendingManeuverFor(const FS08Snapshot& Snapshot, const FString& ViewerId,
                        FString& OutId) {
  if (!Snapshot.Metadata.IsValid()) return false;
  const TSharedPtr<FJsonObject> Meta = Snapshot.Metadata->AsObject();
  if (!Meta.IsValid()) return false;
  const TSharedPtr<FJsonObject>* Pending = nullptr;
  if (!Meta->TryGetObjectField(TEXT("pendingManeuver"), Pending) || !Pending->IsValid()) {
    return false;
  }
  if ((*Pending)->GetStringField(TEXT("playerId")) != ViewerId) return false;
  OutId = (*Pending)->GetStringField(TEXT("id"));
  return !OutId.IsEmpty();
}
// Mirrors the server validateBanner: empty/'any' banner is universal;
// otherwise the fighter name must match the banner in either direction
// ('Harpy' banner is satisfied by the 'Harpies' minion, exact for heroes).
bool PlayableByBanner(const FS09CardView& Card, const FString& FighterName) {
  const FString Banner = Card.BannerName.TrimStartAndEnd().ToLower();
  if (Banner.IsEmpty() || Banner == TEXT("any")) return true;
  const FString Name = FighterName.ToLower();
  return Name.Contains(Banner) || Banner.Contains(Name);
}

// Own-hand cards of the given types whose banner FighterName satisfies.
TArray<FS09CardView> LegalCardsFor(const FS08Snapshot& Snapshot, const FString& ViewerId,
                                   const TArray<const TCHAR*>& Types,
                                   const FString& FighterName) {
  TArray<FS09CardView> Out;
  TArray<FS09CardView> Cards;
  if (!OwnHandCards(Snapshot, ViewerId, Cards)) return Out;
  for (const FS09CardView& Card : Cards) {
    if (Card.bHidden) continue;
    bool bTypeOk = false;
    for (const TCHAR* Type : Types) {
      if (Card.CardType == Type) { bTypeOk = true; break; }
    }
    if (bTypeOk && PlayableByBanner(Card, FighterName)) Out.Add(Card);
  }
  return Out;
}
} // namespace

// Server bannerAllows singular normalization: harpies→harpy, wolves→wolf,
// dogs→dog (mirrors game-rules.validator.ts).
static FString SingularLower(FString Word) {
  Word = Word.TrimStartAndEnd().ToLower();
  if (Word.EndsWith(TEXT("ies"))) {
    Word = Word.LeftChop(3) + TEXT("y");
  } else if (Word.EndsWith(TEXT("ves"))) {
    Word = Word.LeftChop(3) + TEXT("f");
  } else if (Word.EndsWith(TEXT("s")) && Word.Len() > 1) {
    Word = Word.LeftChop(1);
  }
  return Word;
}

bool FS09CommandUi::BannerAllowsFighter(const FString& Banner, const FString& FighterName) {
  const FString B = SingularLower(Banner);
  FString Full = FighterName.TrimStartAndEnd().ToLower();
  // numeric suffix: 'harpy 2' -> 'harpy'
  int32 SpaceIdx = INDEX_NONE;
  if (Full.FindLastChar(' ', SpaceIdx)) {
    const FString Tail = Full.RightChop(SpaceIdx + 1);
    bool bNumeric = !Tail.IsEmpty();
    for (const TCHAR C : Tail) {
      if (C < '0' || C > '9') { bNumeric = false; break; }
    }
    if (bNumeric) Full = Full.Left(SpaceIdx);
  }
  if (B == SingularLower(Full)) return true;
  // banner as a whole word of the full name: 'arthur' in 'king arthur'
  FString Rest = Full;
  while (!Rest.IsEmpty()) {
    int32 Idx = INDEX_NONE;
    if (!Rest.FindChar(' ', Idx)) {
      return SingularLower(Rest) == B;
    }
    if (SingularLower(Rest.Left(Idx)) == B) return true;
    Rest = Rest.RightChop(Idx + 1);
  }
  return false;
}

bool FS09CommandUi::SchemePlayableByLivingFighters(
    const FS09CardView& Card, const TArray<FS08BoardFighter>& Fighters,
    const FString& ViewerId) {
  const FString Banner = Card.BannerName.TrimStartAndEnd();
  if (Banner.IsEmpty() || Banner.ToLower() == TEXT("any")) return true;
  bool bKnownInGame = false;
  bool bHasLivingOwn = false;
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (BannerAllowsFighter(Banner, Fighter.Name)) {
      bKnownInGame = true; // matches a fighter of the game (dead or alive)
    }
    if (Fighter.OwnerId == ViewerId && Fighter.Health > 0) {
      bHasLivingOwn = true;
    }
  }
  // Server gate: SOME living OWN fighter must pass validateBanner - i.e. the
  // banner matches it, or the banner is known to no fighter of the game.
  // (No living own fighter at all -> the server skips the check entirely.)
  if (!bHasLivingOwn) return true;
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (Fighter.OwnerId == ViewerId && Fighter.Health > 0 &&
        BannerAllowsFighter(Banner, Fighter.Name)) {
      return true;
    }
  }
  return !bKnownInGame;
}

bool FS09CommandUi::IsRangedAttacker(const FS08BoardFighter& Attacker) {
  const FString Type = Attacker.AttackType.TrimStartAndEnd();
  return Type == TEXT("ranged") || Type == TEXT("range");
}

bool FS09CommandUi::IsTargetInAttackRange(const FS08BoardModel& Board,
                                          const FS08BoardFighter& Attacker,
                                          const FS08BoardFighter& Target) {
  if (Attacker.X < 0 || Attacker.Y < 0 || Target.X < 0 || Target.Y < 0) return false;
  const FIntPoint From(Attacker.X, Attacker.Y);
  const FIntPoint To(Target.X, Target.Y);
  if (From == To) return false;
  if (Board.IsAdjacent(From, To)) return true;
  return IsRangedAttacker(Attacker) && Board.SharesZone(From, To);
}

bool FS09CommandUi::IsZoneOnlyTarget(const FS08BoardModel& Board,
                                     const FS08BoardFighter& Attacker,
                                     const FS08BoardFighter& Target) {
  return IsTargetInAttackRange(Board, Attacker, Target) &&
         !Board.IsAdjacent(FIntPoint(Attacker.X, Attacker.Y), FIntPoint(Target.X, Target.Y));
}

TArray<FString> FS09CommandUi::LegalAttackTargets(const FS08BoardModel& Board,
                                                  const TArray<FS08BoardFighter>& Fighters,
                                                  const FString& AttackerId) {
  TArray<FString> Out;
  const FS08BoardFighter* Attacker = nullptr;
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (Fighter.Id == AttackerId) {
      Attacker = &Fighter;
      break;
    }
  }
  if (!Attacker || !Attacker->IsAlive()) return Out;
  for (const FS08BoardFighter& Other : Fighters) {
    if (Other.OwnerId == Attacker->OwnerId || !Other.IsAlive()) continue;
    if (IsTargetInAttackRange(Board, *Attacker, Other)) Out.Add(Other.Id);
  }
  return Out;
}

bool FS09CommandUi::OnSnapshot(const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                               const TArray<FS08BoardFighter>& Fighters) {
  const ES09CommandMode OldMode = Mode;
  // ENV-O6: attack range of the board-less draft overloads follows the
  // latest authoritative board (links + zones).
  SnapshotBoard = Board;

  // GD-036: terminal state closes every local draft - gameplay input is
  // dead on the result screen (the server would reject it anyway: executor
  // early-returns, GameInProgressGuard blocks after the row goes FINISHED).
  if (Snapshot.Phase == TEXT("GAME_OVER")) {
    Mode = ES09CommandMode::None;
    PendingManeuverId.Reset();
    Moves.Reset();
    BoostCardId.Reset();
    SelectedFighterId.Reset();
    ReachableCells.Reset();
    PendingDiscard = FS08PendingHandDiscard();
    DiscardSelection.Reset();
    AttackAttackerId.Reset();
    AttackTargetId.Reset();
    AttackCardId.Reset();
    DefenseCardId.Reset();
    SchemeCardId.Reset();
    ResetPendingDraft();
    return Mode != OldMode;
  }

  FString ManeuverId;
  FS08PendingHandDiscard Discard;
  const bool bHasDiscard = FS08Contracts::PendingHandDiscard(Snapshot, Discard);

  // GD-034: combat projections are re-derived on EVERY snapshot - no local
  // combat state survives a server body (the server is the only authority on
  // phase/deadline/committed cards).
  FS08CombatInfo Info;
  const bool bHasCombat = FS08Contracts::CombatInfo(Snapshot, Info);
  bHasPendingChoice = FS08Contracts::PendingEffects(Snapshot, PendingQueue);
  PendingChoice = FS08PendingEffect();
  if (bHasPendingChoice) PendingChoice = PendingQueue[0];
  Combat = bHasCombat ? Info : FS08CombatInfo();

  // Drop a stale local attack draft the moment it can no longer be legal
  // (phase left ACTION_*, turn ended, combat opened). Selections that depend
  // on cards still in hand survive re-applies of the same seq. The scheme
  // picker follows the same rule: a playScheme is only legal in the owner's
  // action phase with an empty pending queue.
  if ((Mode == ES09CommandMode::AttackDraft || Mode == ES09CommandMode::SchemeChoice) &&
      (bHasCombat || bHasPendingChoice ||
       (Snapshot.Phase != TEXT("ACTION_MANEUVER") && Snapshot.Phase != TEXT("ACTION_ATTACK")) ||
       Snapshot.CurrentTurnPlayerId != ViewerId)) {
    Mode = ES09CommandMode::None;
    AttackAttackerId.Reset();
    AttackTargetId.Reset();
    AttackCardId.Reset();
    SchemeCardId.Reset();
  }

  if (PendingManeuverFor(Snapshot, ViewerId, ManeuverId)) {
    Mode = ES09CommandMode::ManeuverDraft;
    PendingManeuverId = ManeuverId;
    // Revalidate the carried draft against the FRESH authoritative state:
    // moves of fighters no longer selectable are dropped, a boost card that
    // left the hand is cleared (the server would reject both).
    Moves.RemoveAll([&](const FS09DraftMove& Move) {
      return FindOwnFighter(Fighters, Move.FighterId) == nullptr;
    });
    if (!BoostCardId.IsEmpty() && !OwnHandIds(Snapshot).Contains(BoostCardId)) {
      BoostCardId.Reset();
    }
    if (!SelectedFighterId.IsEmpty() && FindOwnFighter(Fighters, SelectedFighterId) == nullptr) {
      SelectedFighterId.Reset();
      ReachableCells.Reset();
    } else if (!SelectedFighterId.IsEmpty()) {
      // Allowance may have changed (boost cleared above) - refresh hints.
      const FS08BoardFighter* Fighter = FindOwnFighter(Fighters, SelectedFighterId);
      if (Fighter) {
        ReachableCells = FS08BoardModel::ComputeReachableCells(
            Board, Fighters, Fighter->Id, Fighter->Movement + BoostValueFromHand(Snapshot));
      }
    }
  } else if (bHasDiscard && Discard.PlayerId == ViewerId) {
    Mode = ES09CommandMode::DiscardDraft;
    PendingDiscard = Discard;
    // Keep still-valid selections; ids that left the hand cannot resolve.
    TArray<FString> Hand = OwnHandIds(Snapshot);
    DiscardSelection = DiscardSelection.Intersect(TSet<FString>(Hand));
  } else if (bHasPendingChoice && PendingChoice.PlayerId == ViewerId) {
    // GD-035: the server is waiting on THIS viewer's queue head - ANY type.
    // Highest-priority mode (combat stays open behind it; the deadline keeps
    // ticking server-side). A changed head (id/stage/mode/chooseCount, e.g.
    // the CHOOSE_SPACE stage swap or a DECK_TOP_PICK PICK->ORDER swap)
    // restarts the draft from scratch.
    Mode = ES09CommandMode::PendingChoice;
    const FString HeadKey = PendingHeadKey();
    if (PendingDraftKey != HeadKey) {
      ResetPendingDraft();
      PendingDraftKey = HeadKey;
    }
    // Revalidate the carried selection against the fresh head.
    if (!PendingFighterId.IsEmpty()) {
      TArray<FString> Legal;
      PendingLegalFighters(Fighters, Legal);
      if (!Legal.Contains(PendingFighterId)) PendingFighterId.Reset();
    }
    if (bPendingCellSet) {
      PendingCells = ComputePendingCells(Snapshot, Board, Fighters);
      if (!PendingCells.Contains(FS08BoardModel::CellKey(PendingCellX, PendingCellY))) {
        bPendingCellSet = false;
      }
    } else {
      PendingCells.Reset();
    }
    if (PendingOptionIndex >= PendingChoice.Options.Num()) PendingOptionIndex = -1;
    if (PendingCardIds.Num() > 0) {
      TSet<FString> Allowed;
      if (PendingChoice.Type == TEXT("DECK_TOP_PICK")) {
        TArray<FS09CardView> Revealed;
        if (PendingRevealedCards(Revealed)) {
          for (const FS09CardView& Card : Revealed) Allowed.Add(Card.InstanceId);
        }
      } else {
        Allowed = TSet<FString>(OwnHandIds(Snapshot));
      }
      PendingCardIds.RemoveAll([&](const FString& Id) { return !Allowed.Contains(Id); });
    }
  } else if (bHasCombat && Snapshot.Phase == TEXT("COMBAT") &&
             Combat.DefenderId == ViewerId) {
    // Role gate: the DEFENDER acts on the ATTACKER's turn - no turn-owner
    // check may close this window.
    Mode = ES09CommandMode::CombatDefense;
    if (!DefenseCardId.IsEmpty() && !OwnHandIds(Snapshot).Contains(DefenseCardId)) {
      DefenseCardId.Reset();
    }
  } else if (bHasCombat && Snapshot.Phase == TEXT("COMBAT_RESOLVE") &&
             (!bHasPendingChoice || PendingChoice.PlayerId != ViewerId)) {
    // Resolve is open to ANY participant (unmatched-net/1 section 7); the
    // deadline is server-authoritative (combatInfo.timeoutAt). A non-empty
    // pending queue blocks resolve on both seats (server: 'Resolve the
    // pending choice first') - the owner sits in PendingChoice instead, and
    // the OTHER seat still opens the resolve window: during the post-reveal
    // boost pause the revealed cards/values must stay rendered (GD-033),
    // while any premature R is rejected by the server anyway.
    Mode = ES09CommandMode::CombatResolve;
  } else if (Mode == ES09CommandMode::AttackDraft || Mode == ES09CommandMode::SchemeChoice) {
    // A live attack draft survives same-seq re-applies; legality was checked
    // by the stale-drop above. Cards that left the hand are dropped so an
    // illegal confirm is unrepresentable. The scheme picker survives the
    // same way; a selected scheme that left the hand is cleared (the confirm
    // then demands a fresh explicit pick - it NEVER auto-picks another).
    if (Mode == ES09CommandMode::AttackDraft) {
      if (!AttackCardId.IsEmpty() && !OwnHandIds(Snapshot).Contains(AttackCardId)) {
        AttackCardId.Reset();
      }
    } else if (!SchemeCardId.IsEmpty() && !OwnHandIds(Snapshot).Contains(SchemeCardId)) {
      SchemeCardId.Reset();
    }
  } else {
    Mode = ES09CommandMode::None;
    PendingManeuverId.Reset();
    Moves.Reset();
    BoostCardId.Reset();
    SelectedFighterId.Reset();
    ReachableCells.Reset();
    PendingDiscard = FS08PendingHandDiscard();
    DiscardSelection.Reset();
    AttackAttackerId.Reset();
    AttackTargetId.Reset();
    AttackCardId.Reset();
    DefenseCardId.Reset();
    SchemeCardId.Reset();
    ResetPendingDraft();
  }
  return Mode != OldMode;
}

bool FS09CommandUi::CanBeginManeuver(const FS08Snapshot& Snapshot,
                                     FString& OutReason) const {
  OutReason.Reset();
  if (Snapshot.Phase == TEXT("GAME_OVER")) {
    OutReason = TEXT("the duel is over - no gameplay input on the result screen");
    return false;
  }
  if (Mode == ES09CommandMode::ManeuverDraft) {
    OutReason = TEXT("a maneuver draft is already open (server draw committed)");
    return false;
  }
  if (Mode == ES09CommandMode::DiscardDraft) {
    OutReason = TEXT("finish the discard choice first");
    return false;
  }
  if (bHasPendingChoice) {
    OutReason = TEXT("a pending choice is open (resolve the queue head first)");
    return false;
  }
  if (bCommandInFlight) {
    OutReason = TEXT("a command is already in flight");
    return false;
  }
  if (Snapshot.CurrentTurnPlayerId != ViewerId) {
    OutReason = TEXT("not your turn");
    return false;
  }
  if (Snapshot.Phase != TEXT("ACTION_MANEUVER") && Snapshot.Phase != TEXT("ACTION_ATTACK")) {
    OutReason = TEXT("maneuver is not legal in phase ") + Snapshot.Phase;
    return false;
  }
  return true;
}

TArray<FString> FS09CommandUi::OwnHandIds(const FS08Snapshot& Snapshot) const {
  TArray<FS09CardView> Cards;
  TArray<FString> Ids;
  if (OwnHandCards(Snapshot, ViewerId, Cards)) {
    for (const FS09CardView& Card : Cards) Ids.Add(Card.InstanceId);
  }
  return Ids;
}

int32 FS09CommandUi::BoostValueFromHand(const FS08Snapshot& Snapshot) const {
  if (BoostCardId.IsEmpty()) return 0;
  TArray<FS09CardView> Cards;
  if (!OwnHandCards(Snapshot, ViewerId, Cards)) return 0;
  for (const FS09CardView& Card : Cards) {
    if (Card.InstanceId == BoostCardId) return Card.BoostValue;
  }
  return 0;
}

const FS08BoardFighter* FS09CommandUi::FindOwnFighter(
    const TArray<FS08BoardFighter>& Fighters, const FString& FighterId) const {
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (Fighter.Id == FighterId && Fighter.OwnerId == ViewerId && Fighter.IsAlive()) {
      return &Fighter;
    }
  }
  return nullptr;
}

bool FS09CommandUi::SelectFighter(const FString& FighterId, const FS08Snapshot& Snapshot,
                                  const FS08BoardModel& Board,
                                  const TArray<FS08BoardFighter>& Fighters) {
  if (Mode != ES09CommandMode::ManeuverDraft) return false;
  if (FindOwnFighter(Fighters, FighterId) == nullptr) return false;
  SelectedFighterId = FighterId;
  const FS08BoardFighter* Fighter = FindOwnFighter(Fighters, FighterId);
  ReachableCells = FS08BoardModel::ComputeReachableCells(
      Board, Fighters, FighterId, Fighter->Movement + BoostValueFromHand(Snapshot));
  return true;
}

bool FS09CommandUi::SetDestination(const FString& FighterId, int32 X, int32 Y,
                                   const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                                   const TArray<FS08BoardFighter>& Fighters,
                                   FString& OutReason) {
  OutReason.Reset();
  if (Mode != ES09CommandMode::ManeuverDraft) {
    OutReason = TEXT("no open maneuver draft");
    return false;
  }
  const FS08BoardFighter* Fighter = FindOwnFighter(Fighters, FighterId);
  if (!Fighter) {
    OutReason = TEXT("not one of your living fighters");
    return false;
  }
  const int32 Allowance = Fighter->Movement + BoostValueFromHand(Snapshot);
  const TSet<uint64> Reach = FS08BoardModel::ComputeReachableCells(Board, Fighters,
                                                                   FighterId, Allowance);
  if (!Reach.Contains(FS08BoardModel::CellKey(X, Y))) {
    OutReason = FString::Printf(TEXT("cell (%d,%d) exceeds movement %d or is blocked"),
                                X, Y, Allowance);
    return false;
  }
  for (FS09DraftMove& Move : Moves) {
    if (Move.FighterId == FighterId) {
      Move.DestX = X;
      Move.DestY = Y;
      return true;
    }
  }
  FS09DraftMove Move;
  Move.FighterId = FighterId;
  Move.DestX = X;
  Move.DestY = Y;
  Moves.Add(Move);
  return true;
}

void FS09CommandUi::ClearMove(const FString& FighterId) {
  Moves.RemoveAll([&](const FS09DraftMove& Move) { return Move.FighterId == FighterId; });
}

bool FS09CommandUi::ToggleBoostCard(const FString& InstanceId, const FS08Snapshot& Snapshot,
                                    FString& OutReason) {
  OutReason.Reset();
  if (Mode != ES09CommandMode::ManeuverDraft) {
    OutReason = TEXT("boost is chosen inside an open maneuver draft");
    return false;
  }
  if (BoostCardId == InstanceId) {
    BoostCardId.Reset();
    return true;
  }
  const TArray<FString> Hand = OwnHandIds(Snapshot);
  if (!Hand.Contains(InstanceId)) {
    OutReason = TEXT("boost must be an exact card instance in your hand");
    return false;
  }
  BoostCardId = InstanceId;
  return true;
}

void FS09CommandUi::CancelDraft() {
  // LOCAL-ONLY: the server pendingManeuver stays exactly as it is - the
  // committed draw is not reversed and beginManeuver must not be re-sent
  // (CanBeginManeuver keeps refusing while the pending exists).
  Moves.Reset();
  BoostCardId.Reset();
  SelectedFighterId.Reset();
  ReachableCells.Reset();
}

bool FS09CommandUi::CanResumeManeuver(const FS08Snapshot& Snapshot) const {
  FString Id;
  return PendingManeuverFor(Snapshot, ViewerId, Id);
}

bool FS09CommandUi::ConfirmManeuver(const FS08Snapshot& Snapshot,
                                    const FS08BoardModel& Board,
                                    const TArray<FS08BoardFighter>& Fighters,
                                    FS09ManeuverCommand& OutCommand, FString& OutReason) {
  OutReason.Reset();
  OutCommand = FS09ManeuverCommand();
  if (Mode != ES09CommandMode::ManeuverDraft) {
    OutReason = TEXT("no open maneuver draft");
    return false;
  }
  if (bCommandInFlight) {
    OutReason = TEXT("a command is already in flight");
    return false;
  }
  if (PendingManeuverId.IsEmpty()) {
    OutReason = TEXT("draft has no pending maneuver id");
    return false;
  }
  // Destination conflicts between drafted moves: the server applies moves
  // sequentially and rejects a second fighter on an occupied cell - catch it
  // locally with an actionable reason.
  TSet<uint64> Used;
  for (const FS09DraftMove& Move : Moves) {
    const uint64 Key = FS08BoardModel::CellKey(Move.DestX, Move.DestY);
    if (Used.Contains(Key)) {
      OutReason = FString::Printf(
          TEXT("two drafted moves end on the same cell (%d,%d)"), Move.DestX, Move.DestY);
      return false;
    }
    Used.Add(Key);
  }
  OutCommand.ManeuverId = PendingManeuverId;
  OutCommand.BoostCardId = BoostCardId;
  for (const FS09DraftMove& Move : Moves) {
    const FS08BoardFighter* Fighter = FindOwnFighter(Fighters, Move.FighterId);
    if (!Fighter) {
      OutReason = TEXT("drafted fighter is no longer selectable");
      return false;
    }
    FS08ManeuverMove Out;
    if (Move.DestX == Fighter->X && Move.DestY == Fighter->Y) {
      // Zero-length legal resolve: stay in place.
      Out.FighterId = Move.FighterId;
    } else if (!FS08BoardModel::BuildManeuverPath(Board, Fighters, Move.FighterId,
                                                  Fighter->Movement + BoostValueFromHand(Snapshot),
                                                  Move.DestX, Move.DestY, Out.Path) ||
               Out.Path.IsEmpty()) {
      OutReason = FString::Printf(TEXT("no legal path to (%d,%d) for %s"), Move.DestX,
                                  Move.DestY, *Move.FighterId);
      return false;
    } else {
      Out.FighterId = Move.FighterId;
    }
    OutCommand.Moves.Add(MoveTemp(Out));
  }
  // Zero moves + optional boost/no-boost is a legal completion (ACC-006).
  return true;
}

bool FS09CommandUi::ToggleDiscardCard(const FString& InstanceId, const FS08Snapshot& Snapshot,
                                      FString& OutReason) {
  OutReason.Reset();
  if (Mode != ES09CommandMode::DiscardDraft) {
    OutReason = TEXT("no open discard choice");
    return false;
  }
  const TArray<FString> Hand = OwnHandIds(Snapshot);
  if (!Hand.Contains(InstanceId)) {
    OutReason = TEXT("discard picks must be exact card instances in your hand");
    return false;
  }
  if (DiscardSelection.Contains(InstanceId)) {
    DiscardSelection.Remove(InstanceId);
    return true;
  }
  if (DiscardSelection.Num() >= PendingDiscard.Count) {
    OutReason = FString::Printf(TEXT("already selected the excess count (%d)"),
                                PendingDiscard.Count);
    return false;
  }
  DiscardSelection.Add(InstanceId);
  return true;
}

bool FS09CommandUi::ConfirmDiscard(const FS08Snapshot& Snapshot,
                                   FS09DiscardCommand& OutCommand,
                                   FString& OutReason) const {
  OutReason.Reset();
  OutCommand = FS09DiscardCommand();
  if (Mode != ES09CommandMode::DiscardDraft) {
    OutReason = TEXT("no open discard choice");
    return false;
  }
  if (bCommandInFlight) {
    OutReason = TEXT("a command is already in flight");
    return false;
  }
  // EXACT count of unique own-hand instances (backend rejects any other
  // shape; the local gate makes the illegal click states unrepresentable).
  if (DiscardSelection.Num() != PendingDiscard.Count) {
    OutReason = FString::Printf(TEXT("select exactly %d cards (%d chosen)"),
                                PendingDiscard.Count, DiscardSelection.Num());
    return false;
  }
  OutCommand.PendingId = PendingDiscard.Id;
  for (const FString& Id : DiscardSelection) {
    OutCommand.CardInstanceIds.Add(Id);
  }
  return true;
}

// ---- GD-034 combat ----------------------------------------------------------

const FS08BoardFighter* FS09CommandUi::FindFighter(const TArray<FS08BoardFighter>& Fighters,
                                                   const FString& FighterId) const {
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (Fighter.Id == FighterId) return &Fighter;
  }
  return nullptr;
}

bool FS09CommandUi::CanOpenAttackDraft(const FS08Snapshot& Snapshot,
                                       FString& OutReason) const {
  OutReason.Reset();
  if (Snapshot.Phase == TEXT("GAME_OVER")) {
    OutReason = TEXT("the duel is over - no gameplay input on the result screen");
    return false;
  }
  if (Mode == ES09CommandMode::ManeuverDraft || Mode == ES09CommandMode::DiscardDraft ||
      Mode == ES09CommandMode::CombatDefense || Mode == ES09CommandMode::CombatResolve ||
      Mode == ES09CommandMode::PendingChoice) {
    OutReason = TEXT("another command mode is open");
    return false;
  }
  if (bHasPendingChoice) {
    OutReason = TEXT("a pending choice is open (resolve the queue head first)");
    return false;
  }
  if (bCommandInFlight) {
    OutReason = TEXT("a command is already in flight");
    return false;
  }
  if (Snapshot.CurrentTurnPlayerId != ViewerId) {
    OutReason = TEXT("not your turn");
    return false;
  }
  if (Snapshot.Phase != TEXT("ACTION_MANEUVER") && Snapshot.Phase != TEXT("ACTION_ATTACK")) {
    OutReason = TEXT("attack is not legal in phase ") + Snapshot.Phase;
    return false;
  }
  FS08CombatInfo Open;
  if (FS08Contracts::CombatInfo(Snapshot, Open)) {
    OutReason = TEXT("a combat window is open");
    return false;
  }
  return true;
}

bool FS09CommandUi::SelectAttacker(const FString& FighterId, const FS08BoardModel& Board,
                                   const TArray<FS08BoardFighter>& Fighters,
                                   FString& OutReason) {
  OutReason.Reset();
  if (Mode != ES09CommandMode::AttackDraft) {
    OutReason = TEXT("no open attack draft");
    return false;
  }
  const FS08BoardFighter* Fighter = FindOwnFighter(Fighters, FighterId);
  if (!Fighter) {
    OutReason = TEXT("attacker must be one of your living fighters");
    return false;
  }
  // An attacker without a living enemy in range can never confirm (melee:
  // adjacent; ranged: adjacent or same zone - the server's legal set).
  bool bHasEnemyInRange = false;
  for (const FS08BoardFighter& Other : Fighters) {
    if (Other.OwnerId == ViewerId || !Other.IsAlive()) continue;
    if (IsTargetInAttackRange(Board, *Fighter, Other)) {
      bHasEnemyInRange = true;
      break;
    }
  }
  if (!bHasEnemyInRange) {
    OutReason = IsRangedAttacker(*Fighter)
                    ? TEXT("attacker has no enemy in range (ranged: adjacent or same zone)")
                    : TEXT("attacker has no adjacent enemy (melee adjacency)");
    return false;
  }
  if (AttackAttackerId != FighterId) {
    // Different attacker invalidates the old card (banner) and target.
    AttackCardId.Reset();
    AttackTargetId.Reset();
  }
  AttackAttackerId = FighterId;
  return true;
}

bool FS09CommandUi::SelectTarget(const FString& FighterId, const FS08BoardModel& Board,
                                 const TArray<FS08BoardFighter>& Fighters,
                                 FString& OutReason) {
  OutReason.Reset();
  if (Mode != ES09CommandMode::AttackDraft) {
    OutReason = TEXT("no open attack draft");
    return false;
  }
  const FS08BoardFighter* Attacker = FindFighter(Fighters, AttackAttackerId);
  if (!Attacker) {
    OutReason = TEXT("select an attacker first");
    return false;
  }
  const FS08BoardFighter* Target = FindFighter(Fighters, FighterId);
  if (!Target || !Target->IsAlive() || Target->OwnerId == ViewerId) {
    OutReason = TEXT("target must be a living enemy fighter");
    return false;
  }
  if (!IsTargetInAttackRange(Board, *Attacker, *Target)) {
    OutReason = IsRangedAttacker(*Attacker)
                    ? TEXT("target must be adjacent to the attacker or share a zone with it (ranged)")
                    : TEXT("target must be adjacent to the attacker");
    return false;
  }
  AttackTargetId = FighterId;
  return true;
}

bool FS09CommandUi::ToggleAttackCard(const FString& InstanceId, const FS08Snapshot& Snapshot,
                                     const TArray<FS08BoardFighter>& Fighters,
                                     FString& OutReason) {
  OutReason.Reset();
  if (Mode != ES09CommandMode::AttackDraft) {
    OutReason = TEXT("no open attack draft");
    return false;
  }
  const FS08BoardFighter* Attacker = FindFighter(Fighters, AttackAttackerId);
  if (!Attacker) {
    OutReason = TEXT("select an attacker first");
    return false;
  }
  if (AttackCardId == InstanceId) {
    AttackCardId.Reset();
    return true;
  }
  const TArray<const TCHAR*> Types = {TEXT("ATTACK"), TEXT("VERSATILE"), TEXT("UNIVERSAL")};
  const TArray<FS09CardView> Legal = LegalCardsFor(Snapshot, ViewerId, Types, Attacker->Name);
  for (const FS09CardView& Card : Legal) {
    if (Card.InstanceId == InstanceId) {
      AttackCardId = InstanceId;
      return true;
    }
  }
  OutReason = TEXT("attack card must be an ATTACK/VERSATILE/UNIVERSAL hand card this attacker may play");
  return false;
}

bool FS09CommandUi::ConfirmAttack(const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                                  const TArray<FS08BoardFighter>& Fighters,
                                  FS09AttackCommand& OutCommand,
                                  FString& OutReason) const {
  OutReason.Reset();
  OutCommand = FS09AttackCommand();
  if (Mode != ES09CommandMode::AttackDraft) {
    OutReason = TEXT("no open attack draft");
    return false;
  }
  if (bCommandInFlight) {
    OutReason = TEXT("a command is already in flight");
    return false;
  }
  if (AttackAttackerId.IsEmpty() || AttackTargetId.IsEmpty() || AttackCardId.IsEmpty()) {
    OutReason = TEXT("attack needs attacker + target in range + legal card");
    return false;
  }
  // Re-derive every leg from the AUTHORITATIVE snapshot (no draft-stale
  // confirm): attack range, ownership, banner legality.
  const FS08BoardFighter* Attacker = FindFighter(Fighters, AttackAttackerId);
  if (!Attacker || Attacker->OwnerId != ViewerId || !Attacker->IsAlive()) {
    OutReason = TEXT("drafted attacker is no longer legal");
    return false;
  }
  const FS08BoardFighter* Target = FindFighter(Fighters, AttackTargetId);
  if (!Target || !Target->IsAlive() || Target->OwnerId == ViewerId ||
      !IsTargetInAttackRange(Board, *Attacker, *Target)) {
    OutReason = TEXT("drafted target is no longer in range/alive");
    return false;
  }
  const TArray<const TCHAR*> Types = {TEXT("ATTACK"), TEXT("VERSATILE"), TEXT("UNIVERSAL")};
  bool bCardLegal = false;
  const TArray<FS09CardView> Legal = LegalCardsFor(Snapshot, ViewerId, Types, Attacker->Name);
  for (const FS09CardView& Card : Legal) {
    if (Card.InstanceId == AttackCardId) { bCardLegal = true; break; }
  }
  if (!bCardLegal) {
    OutReason = TEXT("drafted card is no longer legal for this attacker");
    return false;
  }
  OutCommand.AttackerFighterId = AttackAttackerId;
  OutCommand.CardInstanceId = AttackCardId;
  OutCommand.TargetFighterId = AttackTargetId;
  return true;
}

bool FS09CommandUi::ToggleDefenseCard(const FString& InstanceId, const FS08Snapshot& Snapshot,
                                      const TArray<FS08BoardFighter>& Fighters,
                                      FString& OutReason) {
  OutReason.Reset();
  if (Mode != ES09CommandMode::CombatDefense) {
    OutReason = TEXT("no open defense window");
    return false;
  }
  if (DefenseCardId == InstanceId) {
    DefenseCardId.Reset();
    return true;
  }
  // Banner legality is per the ATTACKED fighter (server: combatInfo.targetFighterId).
  const FS08BoardFighter* Defender =
      FindFighter(Fighters, Combat.TargetFighterId);
  const FString FighterName = Defender ? Defender->Name : FString();
  const TArray<const TCHAR*> Types = {TEXT("DEFENSE"), TEXT("VERSATILE"), TEXT("UNIVERSAL")};
  const TArray<FS09CardView> Legal = LegalCardsFor(Snapshot, ViewerId, Types, FighterName);
  for (const FS09CardView& Card : Legal) {
    if (Card.InstanceId == InstanceId) {
      DefenseCardId = InstanceId;
      return true;
    }
  }
  OutReason = TEXT("defense card must be a DEFENSE/VERSATILE/UNIVERSAL hand card the attacked fighter may play");
  return false;
}

bool FS09CommandUi::ConfirmDefense(const FS08Snapshot& Snapshot,
                                   const TArray<FS08BoardFighter>& Fighters,
                                   FS09DefenseCommand& OutCommand,
                                   FString& OutReason) const {
  OutReason.Reset();
  OutCommand = FS09DefenseCommand();
  if (Mode != ES09CommandMode::CombatDefense) {
    OutReason = TEXT("no open defense window");
    return false;
  }
  if (bCommandInFlight) {
    OutReason = TEXT("a command is already in flight");
    return false;
  }
  // The server deadline is authoritative: an expired window must not send
  // (the auto-resolve job owns the outcome from here).
  if (Combat.bHasTimeoutAt && Combat.SecondsUntilDeadline() <= 0.0) {
    OutReason = TEXT("the defense window has expired (server deadline)");
    return false;
  }
  if (DefenseCardId.IsEmpty()) {
    OutReason = TEXT("pick a defense card or choose 'no defense'");
    return false;
  }
  const FS08BoardFighter* Defender = FindFighter(Fighters, Combat.TargetFighterId);
  const FString FighterName = Defender ? Defender->Name : FString();
  const TArray<const TCHAR*> Types = {TEXT("DEFENSE"), TEXT("VERSATILE"), TEXT("UNIVERSAL")};
  bool bLegal = false;
  const TArray<FS09CardView> Legal = LegalCardsFor(Snapshot, ViewerId, Types, FighterName);
  for (const FS09CardView& Card : Legal) {
    if (Card.InstanceId == DefenseCardId) { bLegal = true; break; }
  }
  if (!bLegal) {
    OutReason = TEXT("selected defense card is no longer legal");
    return false;
  }
  OutCommand.bNoDefense = false;
  OutCommand.CardInstanceId = DefenseCardId;
  return true;
}

bool FS09CommandUi::CanResolveCombat(const FS08Snapshot& Snapshot,
                                     FString& OutReason) const {
  OutReason.Reset();
  // A non-empty pending queue blocks resolve on BOTH seats (server:
  // 'Resolve the pending choice first') - the queue head's OWNER must answer
  // first; the other seat only waits. The old local gate checked just the
  // own head, so the non-owner's button sent a command the server rejected.
  if (bHasPendingChoice || PendingQueue.Num() > 0) {
    OutReason = TEXT("a pending choice must be resolved first");
    return false;
  }
  if (Snapshot.Phase == TEXT("COMBAT")) {
    // Only the defender may close the window early ("no defense"); the
    // attacker NEVER can ('Defender has not responded yet').
    if (Mode == ES09CommandMode::CombatDefense) return true;
    OutReason = TEXT("the defender has not responded yet");
    return false;
  }
  if (Snapshot.Phase == TEXT("COMBAT_RESOLVE")) {
    if (Mode == ES09CommandMode::CombatResolve) {
      return true;
    }
    OutReason = TEXT("resolve is open in the COMBAT_RESOLVE window");
    return false;
  }
  OutReason = TEXT("no combat to resolve in phase ") + Snapshot.Phase;
  return false;
}

// ---- GD-035 pending queue head (all types) ---------------------------------

void FS09CommandUi::ResetPendingDraft() {
  PendingFighterId.Reset();
  bPendingCellSet = false;
  PendingCellX = -1;
  PendingCellY = -1;
  PendingOptionIndex = -1;
  PendingCardIds.Reset();
  PendingCells.Reset();
  PendingDraftKey.Reset();
}

FString FS09CommandUi::PendingHeadKey() const {
  return PendingChoice.Id + TEXT("|") + PendingChoice.Type + TEXT("|") +
         FString::FromInt(PendingChoice.Stage) + TEXT("|") + PendingChoice.Mode +
         TEXT("|") + FString::FromInt(PendingChoice.ChooseCount);
}

bool FS09CommandUi::PendingLegalFighters(const TArray<FS08BoardFighter>& Fighters,
                                         TArray<FString>& OutIds) const {
  OutIds.Reset();
  const FString& Type = PendingChoice.Type;
  if (Type != TEXT("MOVE") && Type != TEXT("PLACE") && Type != TEXT("TARGET_FIGHTER")) {
    return false;
  }
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (Type == TEXT("TARGET_FIGHTER")) {
      // Server revalidates aliveness at resolve; the list (when present)
      // bounds the legal targets.
      if (!Fighter.IsAlive()) continue;
      if (PendingChoice.TargetFighterIds.Num() > 0 &&
          !PendingChoice.TargetFighterIds.Contains(Fighter.Id)) {
        continue;
      }
      OutIds.Add(Fighter.Id);
      continue;
    }
    // MOVE/PLACE ownership: own fighter, opponent's fighter
    // (targetsOpponent) or ANY of the effect list (anyOwner, Skirmish).
    const bool bOwn = Fighter.OwnerId == ViewerId;
    if (!PendingChoice.bAnyOwner) {
      if (PendingChoice.bTargetsOpponent ? bOwn : !bOwn) continue;
    }
    if (PendingChoice.FighterIds.Num() > 0 &&
        !PendingChoice.FighterIds.Contains(Fighter.Id)) {
      continue;
    }
    // Revive-PLACE may pick a DEFEATED fighter; every other MOVE/PLACE
    // needs a living one (server: 'Боец не найден или повержен').
    if (!Fighter.IsAlive() && !(Type == TEXT("PLACE") && PendingChoice.bRestoreFullHealth)) {
      continue;
    }
    // Banner restriction from the card text ('Move Daredevil…'):
    // both-direction substring like the server bannerAllows.
    if (!PendingChoice.FighterName.IsEmpty()) {
      const FString Restriction = PendingChoice.FighterName.ToLower();
      const FString Name = Fighter.Name.ToLower();
      if (!Name.Contains(Restriction) && !Restriction.Contains(Name)) continue;
    }
    OutIds.Add(Fighter.Id);
  }
  return OutIds.Num() > 0;
}

bool FS09CommandUi::CellSharesZoneWith(const FS08BoardModel& Board,
                                       const TArray<FS08BoardFighter>& Fighters,
                                       const FString& ZoneFighterName,
                                       int32 X, int32 Y) const {
  const FS08BoardFighter* Anchor = nullptr;
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (Fighter.Name.ToLower().Contains(ZoneFighterName.ToLower()) ||
        ZoneFighterName.ToLower().Contains(Fighter.Name.ToLower())) {
      Anchor = &Fighter;
      break;
    }
  }
  if (!Anchor) return false;
  const FS08Cell* AnchorCell = Board.CellAt(Anchor->X, Anchor->Y);
  const FS08Cell* TargetCell = Board.CellAt(X, Y);
  if (!AnchorCell || !TargetCell) return false;
  for (const FString& Zone : AnchorCell->Zones) {
    if (TargetCell->Zones.Contains(Zone)) return true;
  }
  return false;
}

TSet<uint64> FS09CommandUi::PendingMoveCells(const FS08BoardModel& Board,
                                             const TArray<FS08BoardFighter>& Fighters,
                                             const FS08BoardFighter& Mover,
                                             int32 Allowance,
                                             bool bPassThroughEnemies) const {
  TSet<uint64> Out;
  // Living enemy cells block the path unless the effect passes through them.
  TSet<uint64> Blocked;
  if (!bPassThroughEnemies) {
    for (const FS08BoardFighter& Other : Fighters) {
      if (Other.Id != Mover.Id && Other.IsAlive() && Other.OwnerId != Mover.OwnerId) {
        Blocked.Add(FS08BoardModel::CellKey(Other.X, Other.Y));
      }
    }
  }
  // BFS from the mover's cell; allies are pass-through (server semantics).
  TSet<uint64> Visited;
  TArray<TPair<int32, int32>> Frontier;
  Frontier.Add(TPair<int32, int32>(Mover.X, Mover.Y));
  Visited.Add(FS08BoardModel::CellKey(Mover.X, Mover.Y));
  for (int32 Step = 0; Step < Allowance && Frontier.Num() > 0; Step++) {
    TArray<TPair<int32, int32>> Next;
    for (const TPair<int32, int32>& Cell : Frontier) {
      // Board neighbours (links on an original-map board, orthogonal on a
      // grid) - the server getReachableCells graph.
      for (const FIntPoint& Neighbour : Board.Neighbours(FIntPoint(Cell.Key, Cell.Value))) {
        const int32 NX = Neighbour.X;
        const int32 NY = Neighbour.Y;
        const uint64 Key = FS08BoardModel::CellKey(NX, NY);
        if (Visited.Contains(Key)) continue;
        const FS08Cell* BoardCell = Board.CellAt(NX, NY);
        if (!BoardCell || !BoardCell->IsPassable() || Blocked.Contains(Key)) continue;
        Visited.Add(Key);
        Next.Add(TPair<int32, int32>(NX, NY));
      }
    }
    Frontier = MoveTemp(Next);
  }
  for (const uint64 Key : Visited) {
    // Destination rule: no OTHER living fighter on the cell; the mover's own
    // cell stays legal (zero-step resolve of an "up to N" move).
    const int32 X = static_cast<int32>(Key >> 32);
    const int32 Y = static_cast<int32>(Key & 0xFFFFFFFF);
    if (FS08BoardModel::FighterAt(Fighters, X, Y, Mover.Id) == nullptr) {
      Out.Add(Key);
    }
  }
  return Out;
}

TSet<uint64> FS09CommandUi::ComputePendingCells(const FS08Snapshot& Snapshot,
                                                const FS08BoardModel& Board,
                                                const TArray<FS08BoardFighter>& Fighters) const {
  TSet<uint64> Out;
  const FString& Type = PendingChoice.Type;
  if (Type == TEXT("MOVE") || Type == TEXT("PLACE")) {
    for (const FS08BoardFighter& Fighter : Fighters) {
      if (Fighter.Id != PendingFighterId) continue;
      if (Type == TEXT("MOVE")) {
        return PendingMoveCells(Board, Fighters, Fighter,
                                PendingChoice.bHasValue ? PendingChoice.Value : 1,
                                PendingChoice.bCanPassThroughEnemies);
      }
      // PLACE: any passable free cell (revive may target a defeated fighter,
      // whose own cell counts as free); optional zone restriction.
      for (int32 Y = 0; Y < Board.Height; Y++) {
        for (int32 X = 0; X < Board.Width; X++) {
          const FS08Cell* Cell = Board.CellAt(X, Y);
          if (!Cell || !Cell->IsPassable()) continue;
          if (FS08BoardModel::FighterAt(Fighters, X, Y, Fighter.Id) != nullptr) continue;
          if (!PendingChoice.ZoneFighterName.IsEmpty() &&
              !CellSharesZoneWith(Board, Fighters, PendingChoice.ZoneFighterName, X, Y)) {
            continue;
          }
          Out.Add(FS08BoardModel::CellKey(X, Y));
        }
      }
      return Out;
    }
    return Out;
  }
  if (Type == TEXT("CHOOSE_SPACE")) {
    if (PendingChoice.Stage != 2) {
      // Stage 1: any passable cell sharing the named fighter's zone.
      for (int32 Y = 0; Y < Board.Height; Y++) {
        for (int32 X = 0; X < Board.Width; X++) {
          const FS08Cell* Cell = Board.CellAt(X, Y);
          if (!Cell || !Cell->IsPassable()) continue;
          if (!CellSharesZoneWith(Board, Fighters, PendingChoice.ZoneFighterName, X, Y)) {
            continue;
          }
          Out.Add(FS08BoardModel::CellKey(X, Y));
        }
      }
      return Out;
    }
    // Stage 2: the board neighbours of the stage-1 anchor (server isAdjacent:
    // linked spaces on an original map, the 4 orthogonal cells on a grid).
    if (PendingChoice.bHasAnchor) {
      for (const FIntPoint& Neighbour :
           Board.Neighbours(FIntPoint(PendingChoice.AnchorX, PendingChoice.AnchorY))) {
        const FS08Cell* Cell = Board.CellAt(Neighbour.X, Neighbour.Y);
        if (Cell && Cell->IsPassable()) {
          Out.Add(FS08BoardModel::CellKey(Neighbour.X, Neighbour.Y));
        }
      }
    }
    return Out;
  }
  return Out;
}

bool FS09CommandUi::SelectPendingFighter(const FString& FighterId,
                                          const FS08Snapshot& Snapshot,
                                          const TArray<FS08BoardFighter>& Fighters,
                                          FString& OutReason) {
  OutReason.Reset();
  if (Mode != ES09CommandMode::PendingChoice) {
    OutReason = TEXT("no open pending choice");
    return false;
  }
  TArray<FString> Legal;
  PendingLegalFighters(Fighters, Legal);
  if (!Legal.Contains(FighterId)) {
    OutReason = TEXT("this fighter is not a legal target of the pending choice");
    return false;
  }
  if (PendingFighterId != FighterId) {
    PendingFighterId = FighterId;
    bPendingCellSet = false; // cell legality depends on the fighter
  }
  return true;
}

bool FS09CommandUi::SelectPendingCell(int32 X, int32 Y,
                                       const FS08Snapshot& Snapshot,
                                       const FS08BoardModel& Board,
                                       const TArray<FS08BoardFighter>& Fighters,
                                       FString& OutReason) {
  OutReason.Reset();
  if (Mode != ES09CommandMode::PendingChoice) {
    OutReason = TEXT("no open pending choice");
    return false;
  }
  const FString& Type = PendingChoice.Type;
  if (Type != TEXT("MOVE") && Type != TEXT("PLACE") && Type != TEXT("CHOOSE_SPACE")) {
    OutReason = TEXT("this choice does not take a cell");
    return false;
  }
  if ((Type == TEXT("MOVE") || Type == TEXT("PLACE")) && PendingFighterId.IsEmpty()) {
    OutReason = TEXT("select the fighter to move first");
    return false;
  }
  const TSet<uint64> Legal = ComputePendingCells(Snapshot, Board, Fighters);
  if (!Legal.Contains(FS08BoardModel::CellKey(X, Y))) {
    OutReason = FString::Printf(TEXT("cell (%d,%d) is not legal for this choice"), X, Y);
    return false;
  }
  PendingCellX = X;
  PendingCellY = Y;
  bPendingCellSet = true;
  return true;
}

bool FS09CommandUi::SelectPendingOption(int32 OptionIndex, FString& OutReason) {
  OutReason.Reset();
  if (Mode != ES09CommandMode::PendingChoice) {
    OutReason = TEXT("no open pending choice");
    return false;
  }
  if (PendingChoice.Type != TEXT("CHOOSE_ONE")) {
    OutReason = TEXT("this choice does not take an option");
    return false;
  }
  if (!PendingChoice.Options.IsValidIndex(OptionIndex)) {
    OutReason = TEXT("option index out of range");
    return false;
  }
  PendingOptionIndex = OptionIndex;
  return true;
}

bool FS09CommandUi::PendingRevealedCards(TArray<FS09CardView>& OutCards) const {
  OutCards.Reset();
  if (!PendingChoice.RevealedCards.IsValid()) return false;
  const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
  if (!PendingChoice.RevealedCards->TryGetArray(Cards) || !Cards) return false;
  for (const TSharedPtr<FJsonValue>& Value : *Cards) {
    FS09CardView Card;
    if (FS09HudFactory::CardFromJson(Value, Card)) OutCards.Add(MoveTemp(Card));
  }
  return true;
}

bool FS09CommandUi::PendingCardPickPlan(const FS08Snapshot& Snapshot,
                                        TArray<FString>& OutPool,
                                        int32& OutCount) const {
  OutPool.Reset();
  OutCount = 0;
  // Only the head OWNER gets a plan (bHasPendingChoice is true for ANY queue,
  // Mode is PendingChoice only for this viewer's own head).
  if (Mode != ES09CommandMode::PendingChoice) return false;
  const FString& Type = PendingChoice.Type;
  if (Type != TEXT("DECK_TOP_PICK") && Type != TEXT("DISCARD_CARDS") &&
      Type != TEXT("BOOST_CHOICE")) {
    return false;
  }
  if (Type == TEXT("DECK_TOP_PICK")) {
    TArray<FS09CardView> Revealed;
    if (!PendingRevealedCards(Revealed)) return false; // owner-only projection
    for (const FS09CardView& Card : Revealed) OutPool.Add(Card.InstanceId);
    OutCount = PendingChoice.Mode == TEXT("ORDER")
                   ? Revealed.Num()
                   : (PendingChoice.bHasValue ? PendingChoice.Value : 2);
  } else {
    OutPool = OwnHandIds(Snapshot); // exact instance ids, legality basis
    OutCount = Type == TEXT("BOOST_CHOICE")
                   ? 1
                   : (PendingChoice.bHasValue ? PendingChoice.Value : 1);
  }
  return true;
}

bool FS09CommandUi::TogglePendingCard(const FString& InstanceId,
                                      const FS08Snapshot& Snapshot,
                                      FString& OutReason) {
  OutReason.Reset();
  if (Mode != ES09CommandMode::PendingChoice) {
    OutReason = TEXT("no open pending choice");
    return false;
  }
  const FString& Type = PendingChoice.Type;
  if (PendingCardIds.Contains(InstanceId)) {
    PendingCardIds.RemoveAll([&InstanceId](const FString& Id) { return Id == InstanceId; });
    return true;
  }
  if (Type == TEXT("DECK_TOP_PICK")) {
    // Owner-only exact revealed instances (the opponent's copy has none).
    TArray<FS09CardView> Revealed;
    if (!PendingRevealedCards(Revealed)) {
      OutReason = TEXT("revealed cards are not available to this seat");
      return false;
    }
    bool bKnown = false;
    for (const FS09CardView& Card : Revealed) {
      if (Card.InstanceId == InstanceId) { bKnown = true; break; }
    }
    if (!bKnown) {
      OutReason = TEXT("pick must be one of the revealed card instances");
      return false;
    }
    const int32 Limit = PendingChoice.Mode == TEXT("ORDER")
                            ? Revealed.Num()
                            : (PendingChoice.bHasValue ? PendingChoice.Value : 2);
    if (PendingCardIds.Num() >= Limit) {
      OutReason = FString::Printf(TEXT("already picked the limit (%d)"), Limit);
      return false;
    }
    PendingCardIds.Add(InstanceId); // ORDER: pick sequence = return order
    return true;
  }
  if (Type != TEXT("DISCARD_CARDS") && Type != TEXT("BOOST_CHOICE")) {
    OutReason = TEXT("this choice does not take cards");
    return false;
  }
  if (!OwnHandIds(Snapshot).Contains(InstanceId)) {
    OutReason = TEXT("pick must be an exact card instance in your hand");
    return false;
  }
  const int32 Limit = Type == TEXT("BOOST_CHOICE")
                          ? 1
                          : (PendingChoice.bHasValue ? PendingChoice.Value : 1);
  if (PendingCardIds.Num() >= Limit) {
    OutReason = FString::Printf(TEXT("already picked the limit (%d)"), Limit);
    return false;
  }
  PendingCardIds.Add(InstanceId);
  return true;
}

bool FS09CommandUi::ConfirmPendingChoice(const FS08Snapshot& Snapshot, bool bDecline,
                                         FS09PendingChoiceCommand& OutCommand,
                                         FString& OutReason) const {
  OutReason.Reset();
  OutCommand = FS09PendingChoiceCommand();
  if (Mode != ES09CommandMode::PendingChoice) {
    OutReason = TEXT("no open pending choice");
    return false;
  }
  if (bCommandInFlight) {
    OutReason = TEXT("a command is already in flight");
    return false;
  }
  OutCommand.EffectId = PendingChoice.Id;
  if (bDecline) {
    if (!PendingChoice.bOptional) {
      OutReason = TEXT("this choice is mandatory - declining is not legal");
      return false;
    }
    OutCommand.bDecline = true;
    return true;
  }
  const FString& Type = PendingChoice.Type;
  if (Type == TEXT("MOVE") || Type == TEXT("PLACE")) {
    if (PendingFighterId.IsEmpty() || !bPendingCellSet) {
      OutReason = TEXT("pick the fighter and its destination cell");
      return false;
    }
    OutCommand.FighterId = PendingFighterId;
    OutCommand.bHasCell = true;
    OutCommand.CellX = PendingCellX;
    OutCommand.CellY = PendingCellY;
    return true;
  }
  if (Type == TEXT("CHOOSE_SPACE")) {
    if (!bPendingCellSet) {
      OutReason = TEXT("pick a cell for this effect");
      return false;
    }
    OutCommand.bHasCell = true;
    OutCommand.CellX = PendingCellX;
    OutCommand.CellY = PendingCellY;
    return true;
  }
  if (Type == TEXT("TARGET_FIGHTER")) {
    if (PendingFighterId.IsEmpty()) {
      OutReason = TEXT("pick the target fighter");
      return false;
    }
    OutCommand.FighterId = PendingFighterId;
    return true;
  }
  if (Type == TEXT("CHOOSE_ONE")) {
    if (!PendingChoice.Options.IsValidIndex(PendingOptionIndex)) {
      OutReason = TEXT("pick one of the options");
      return false;
    }
    OutCommand.OptionIndex = PendingChoice.Options[PendingOptionIndex].Index;
    return true;
  }
  if (Type == TEXT("BOOST_CHOICE")) {
    if (PendingCardIds.Num() != 1) {
      OutReason = TEXT("pick exactly one boost card or decline");
      return false;
    }
    if (!OwnHandIds(Snapshot).Contains(PendingCardIds[0])) {
      OutReason = TEXT("selected boost card is no longer in your hand");
      return false;
    }
    OutCommand.CardIds = PendingCardIds;
    return true;
  }
  if (Type == TEXT("DISCARD_CARDS")) {
    const int32 Need = PendingChoice.bHasValue ? PendingChoice.Value : 1;
    if (PendingCardIds.Num() != Need) {
      OutReason = FString::Printf(TEXT("select exactly %d cards (%d chosen)"),
                                  Need, PendingCardIds.Num());
      return false;
    }
    const TSet<FString> Hand = TSet<FString>(OwnHandIds(Snapshot));
    for (const FString& Id : PendingCardIds) {
      if (!Hand.Contains(Id)) {
        OutReason = TEXT("a selected card is no longer in your hand");
        return false;
      }
    }
    OutCommand.CardIds = PendingCardIds;
    return true;
  }
  if (Type == TEXT("DECK_TOP_PICK")) {
    TArray<FS09CardView> Revealed;
    if (!PendingRevealedCards(Revealed) || Revealed.Num() == 0) {
      OutReason = TEXT("revealed cards are not available to this seat");
      return false;
    }
    const bool bOrder = PendingChoice.Mode == TEXT("ORDER");
    const int32 Need = bOrder ? Revealed.Num()
                              : (PendingChoice.bHasValue ? PendingChoice.Value : 2);
    if (PendingCardIds.Num() != Need) {
      OutReason = bOrder
          ? FString::Printf(TEXT("order ALL %d revealed cards (%d picked)"),
                            Need, PendingCardIds.Num())
          : FString::Printf(TEXT("pick exactly %d revealed cards (%d chosen)"),
                            Need, PendingCardIds.Num());
      return false;
    }
    TSet<FString> Allowed;
    for (const FS09CardView& Card : Revealed) Allowed.Add(Card.InstanceId);
    TSet<FString> Seen;
    for (const FString& Id : PendingCardIds) {
      if (!Allowed.Contains(Id) || Seen.Contains(Id)) {
        OutReason = TEXT("every pick must be a distinct revealed card instance");
        return false;
      }
      Seen.Add(Id);
    }
    OutCommand.CardIds = PendingCardIds; // ORDER: pick sequence = top->bottom
    return true;
  }
  // Unknown type: NEVER invent a payload - surface the gap instead.
  OutReason = FString::Printf(TEXT("unsupported pending type '%s' - no legal client command"),
                              *PendingChoice.Type);
  return false;
}

// ---- S09 UX: explicit exact-instance scheme choice -------------------------

bool FS09CommandUi::CanOpenSchemeChoice(const FS08Snapshot& Snapshot,
                                        FString& OutReason) const {
  OutReason.Reset();
  if (Snapshot.Phase == TEXT("GAME_OVER")) {
    OutReason = TEXT("the duel is over - no gameplay input on the result screen");
    return false;
  }
  if (Mode != ES09CommandMode::None && Mode != ES09CommandMode::SchemeChoice) {
    OutReason = TEXT("finish the open command first");
    return false;
  }
  if (bHasPendingChoice) {
    OutReason = TEXT("a pending choice is open (resolve the queue head first)");
    return false;
  }
  if (bCommandInFlight) {
    OutReason = TEXT("a command is already in flight");
    return false;
  }
  if (Snapshot.CurrentTurnPlayerId != ViewerId) {
    OutReason = TEXT("scheme needs your action phase");
    return false;
  }
  if (Snapshot.Phase != TEXT("ACTION_MANEUVER") && Snapshot.Phase != TEXT("ACTION_ATTACK")) {
    OutReason = TEXT("scheme is not legal in phase ") + Snapshot.Phase;
    return false;
  }
  return true;
}

int32 FS09CommandUi::CountPlayableSchemes(const FS08Snapshot& Snapshot,
                                          const TArray<FS08BoardFighter>& Fighters) const {
  TArray<FS09CardView> Cards;
  if (!OwnHandCards(Snapshot, ViewerId, Cards)) return 0;
  int32 Count = 0;
  for (const FS09CardView& Card : Cards) {
    if (Card.bHidden || Card.CardType != TEXT("SCHEME")) continue;
    if (SchemePlayableByLivingFighters(Card, Fighters, ViewerId)) ++Count;
  }
  return Count;
}

void FS09CommandUi::OpenSchemeChoice() {
  Mode = ES09CommandMode::SchemeChoice;
  SchemeCardId.Reset();
}

void FS09CommandUi::CancelSchemeChoice() {
  if (Mode != ES09CommandMode::SchemeChoice) return;
  Mode = ES09CommandMode::None;
  SchemeCardId.Reset();
}

bool FS09CommandUi::ToggleSchemeCard(const FString& InstanceId,
                                     const FS08Snapshot& Snapshot,
                                     const TArray<FS08BoardFighter>& Fighters,
                                     FString& OutReason) {
  OutReason.Reset();
  if (Mode != ES09CommandMode::SchemeChoice) {
    OutReason = TEXT("no open scheme choice (press G first)");
    return false;
  }
  if (InstanceId == SchemeCardId) {
    SchemeCardId.Reset();
    return true;
  }
  TArray<FS09CardView> Cards;
  if (!OwnHandCards(Snapshot, ViewerId, Cards)) {
    OutReason = TEXT("your hand is not visible to this seat");
    return false;
  }
  const FS09CardView* Card = nullptr;
  for (const FS09CardView& Entry : Cards) {
    if (Entry.InstanceId == InstanceId) { Card = &Entry; break; }
  }
  if (!Card) {
    OutReason = TEXT("pick must be an exact card instance in your hand");
    return false;
  }
  if (Card->bHidden) {
    OutReason = TEXT("hidden card - no face is available to this viewer");
    return false;
  }
  if (Card->CardType != TEXT("SCHEME")) {
    OutReason = FString::Printf(TEXT("%s is a %s card - only SCHEME cards are playable here"),
                                *Card->Name, *Card->CardType);
    return false;
  }
  if (!SchemePlayableByLivingFighters(*Card, Fighters, ViewerId)) {
    OutReason = FString::Printf(
        TEXT("%s needs a living '%s' fighter - that banner is dead on your side"),
        *Card->Name, *Card->BannerName);
    return false;
  }
  SchemeCardId = InstanceId;
  return true;
}

bool FS09CommandUi::ConfirmScheme(const FS08Snapshot& Snapshot,
                                  const TArray<FS08BoardFighter>& Fighters,
                                  FString& OutInstanceId, FString& OutReason) const {
  OutReason.Reset();
  OutInstanceId.Reset();
  if (Mode != ES09CommandMode::SchemeChoice) {
    OutReason = TEXT("no open scheme choice");
    return false;
  }
  if (!CanOpenSchemeChoice(Snapshot, OutReason)) return false;
  if (SchemeCardId.IsEmpty()) {
    OutReason = TEXT("pick a scheme card first (click or 1-9)");
    return false;
  }
  // Revalidate the EXACT selection against the fresh snapshot. A stale pick
  // is rejected - a different playable scheme is NEVER substituted.
  FString ToggleReason;
  TArray<FS09CardView> Cards;
  if (!OwnHandCards(Snapshot, ViewerId, Cards)) {
    OutReason = TEXT("your hand is not visible to this seat");
    return false;
  }
  const FS09CardView* Card = nullptr;
  for (const FS09CardView& Entry : Cards) {
    if (Entry.InstanceId == SchemeCardId) { Card = &Entry; break; }
  }
  if (!Card) {
    OutReason = TEXT("the selected scheme is no longer in your hand - pick again");
    return false;
  }
  if (Card->bHidden || Card->CardType != TEXT("SCHEME")) {
    OutReason = TEXT("the selected card is no longer a visible scheme - pick again");
    return false;
  }
  if (!SchemePlayableByLivingFighters(*Card, Fighters, ViewerId)) {
    OutReason = FString::Printf(
        TEXT("the selected scheme's banner '%s' has no living fighter anymore - pick again or cancel"),
        *Card->BannerName);
    return false;
  }
  OutInstanceId = SchemeCardId;
  return true;
}

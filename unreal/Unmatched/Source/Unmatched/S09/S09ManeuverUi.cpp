#include "S09ManeuverUi.h"
#include "Dom/JsonObject.h"
#include "S09HudModel.h"
#include "../S08/S08TraceLog.h"
#include "../S08/S08WhyText.h"

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

TArray<FS09CommandUi::FAutoAttackPick> FS09CommandUi::AutoAttackPicks(
    const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters, const FString& ViewerId,
    bool bPreferRanged) {
  TArray<FAutoAttackPick> Adjacent;
  TArray<FAutoAttackPick> ZoneOnly;
  TArray<FAutoAttackPick> Ordered; // default: per attacker, Fighters order
  for (const FS08BoardFighter& Attacker : Fighters) {
    if (Attacker.OwnerId != ViewerId || !Attacker.IsAlive()) continue;
    const FS08BoardFighter* Target = nullptr;
    bool bZone = false;
    for (const FS08BoardFighter& Enemy : Fighters) {
      if (Enemy.OwnerId == ViewerId || !Enemy.IsAlive()) continue;
      if (Board.IsAdjacent(FIntPoint(Attacker.X, Attacker.Y), FIntPoint(Enemy.X, Enemy.Y))) {
        Target = &Enemy;
        break;
      }
    }
    if (!Target && Board.bHasTopology) {
      for (const FS08BoardFighter& Enemy : Fighters) {
        if (Enemy.OwnerId == ViewerId || !Enemy.IsAlive()) continue;
        if (IsZoneOnlyTarget(Board, Attacker, Enemy)) {
          Target = &Enemy;
          bZone = true;
          break;
        }
      }
    }
    if (!Target) continue;
    FAutoAttackPick Pick;
    Pick.AttackerId = Attacker.Id;
    Pick.TargetId = Target->Id;
    Pick.bZoneOnly = bZone;
    Ordered.Add(Pick);
    (bZone ? ZoneOnly : Adjacent).Add(Pick);
  }
  if (!bPreferRanged) return Ordered;
  ZoneOnly.Append(Adjacent);
  return ZoneOnly;
}

bool FS09CommandUi::PickRangedPosition(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                                       const FString& MoverId, int32 Allowance, const TSet<uint64>& Reserved,
                                       FIntPoint& OutCell, int32& OutSteps, FString& OutTargetId) {
  OutSteps = 0;
  OutTargetId.Reset();
  const FS08BoardFighter* Mover =
      Fighters.FindByPredicate([&MoverId](const FS08BoardFighter& F) { return F.Id == MoverId; });
  if (!Mover || !Mover->IsAlive() || !IsRangedAttacker(*Mover) || !Board.bHasTopology) return false;
  // From (X,Y): no linked living enemy, and the first living enemy sharing a zone.
  auto ZoneOnlyFrom = [&](int32 X, int32 Y, FString& OutTarget) {
    FS08BoardFighter Probe = *Mover;
    Probe.X = X;
    Probe.Y = Y;
    for (const FS08BoardFighter& Enemy : Fighters) {
      if (Enemy.OwnerId == Mover->OwnerId || !Enemy.IsAlive()) continue;
      if (Board.IsAdjacent(FIntPoint(X, Y), FIntPoint(Enemy.X, Enemy.Y))) return false;
    }
    for (const FS08BoardFighter& Enemy : Fighters) {
      if (Enemy.OwnerId == Mover->OwnerId || !Enemy.IsAlive()) continue;
      if (IsZoneOnlyTarget(Board, Probe, Enemy)) {
        OutTarget = Enemy.Id;
        return true;
      }
    }
    return false;
  };
  FString Here;
  if (ZoneOnlyFrom(Mover->X, Mover->Y, Here)) return false; // already in a ranged position: stay
  const TSet<uint64> Reach = FS08BoardModel::ComputeReachableCells(Board, Fighters, MoverId, Allowance);
  bool bFound = false;
  for (const uint64 Key : Reach) {
    const int32 X = static_cast<int32>(Key >> 32);
    const int32 Y = static_cast<int32>(Key & 0xFFFFFFFF);
    if ((X == Mover->X && Y == Mover->Y) || Reserved.Contains(Key)) continue;
    FString Target;
    if (!ZoneOnlyFrom(X, Y, Target)) continue;
    TArray<FIntPoint> Path;
    if (!FS08BoardModel::BuildManeuverPath(Board, Fighters, MoverId, Allowance, X, Y, Path) || Path.Num() == 0) {
      continue;
    }
    const int32 Steps = Path.Num();
    const bool bBetter = !bFound || Steps < OutSteps ||
                         (Steps == OutSteps && (Y < OutCell.Y || (Y == OutCell.Y && X < OutCell.X)));
    if (!bBetter) continue;
    bFound = true;
    OutCell = FIntPoint(X, Y);
    OutSteps = Steps;
    OutTargetId = Target;
  }
  return bFound;
}

// ---- MS-T-05: sequential draft evaluation (04 §3.2) ------------------------

namespace {
bool SameDraftId(const FString& A, const FString& B) { return A.Equals(B, ESearchCase::CaseSensitive); }

int32 ClampSteps(int64 Steps) { return static_cast<int32>(FMath::Clamp<int64>(Steps, MIN_int32, MAX_int32)); }

FS08BoardFighter* FindWorkFighter(TArray<FS08BoardFighter>& Work, const FString& Id) {
  return Work.FindByPredicate([&Id](const FS08BoardFighter& F) { return SameDraftId(F.Id, Id); });
}

const FS08BoardFighter* FindWorkFighter(const TArray<FS08BoardFighter>& Work, const FString& Id) {
  return Work.FindByPredicate([&Id](const FS08BoardFighter& F) { return SameDraftId(F.Id, Id); });
}

FString FighterDisplayName(const FS08BoardFighter& Fighter) {
  return Fighter.Label.IsEmpty() ? (Fighter.Name.IsEmpty() ? Fighter.Id : Fighter.Name) : Fighter.Label;
}

const TCHAR* S09DraftSourceName(ES09InputSource Source) {
  switch (Source) {
    case ES09InputSource::Click: return TEXT("click");
    case ES09InputSource::Key: return TEXT("key");
    case ES09InputSource::Snapshot: return TEXT("snapshot");
    default: return TEXT("auto");
  }
}

const TCHAR* DraftStatusName(ES09DraftMoveStatus Status) {
  switch (Status) {
    case ES09DraftMoveStatus::Ok: return TEXT("ok");
    case ES09DraftMoveStatus::NeedBoost: return TEXT("needBoost");
    default: return TEXT("conflict");
  }
}
} // namespace

FString FS09Reason::Describe() const {
  if (!IsSet()) return FString();
  auto ArgOf = [this](const TCHAR* Name) {
    const FString* Value = Args.Find(Name);
    return Value ? *Value : FString(TEXT("?"));
  };
  const FString* Cell = Args.Find(TEXT("cell"));
  const FString Where = Cell ? FString::Printf(TEXT("cell %s"), **Cell) : FString(TEXT("cell"));
  const FString K = Key.ToString();
  FString Text;
  if (K == TEXT("why.cell.unreachable")) {
    Text = FString::Printf(TEXT("%s exceeds movement: need %s, have %s"), *Where, *ArgOf(TEXT("need")),
                           *ArgOf(TEXT("have")));
  } else if (K == TEXT("why.cell.no.path")) {
    Text = Where + TEXT(": no way to get there");
  } else if (K == TEXT("why.cell.needs.boost")) {
    Text = FString::Printf(TEXT("needs boost +%s"), *ArgOf(TEXT("n")));
  } else if (K == TEXT("why.cell.enemy")) {
    Text = Where + TEXT(": an enemy is here");
  } else if (K == TEXT("why.cell.ally")) {
    Text = Where + TEXT(": occupied by an ally");
    if (Args.Contains(TEXT("orderHint"))) Text += TEXT(" (it leaves later - change the order)");
  } else if (K == TEXT("why.cell.not.space")) {
    Text = Where + TEXT(": not a board space");
  } else if (K == TEXT("why.cell.occupied")) {
    Text = Where + TEXT(": the space is occupied");
  } else if (K == TEXT("why.cell.enemy.path")) {
    Text = Where + TEXT(": the path is blocked by an enemy");
  } else if (K == TEXT("why.place.zone")) {
    Text = Where + TEXT(": not in ") + ArgOf(TEXT("fighterName")) + TEXT("'s zone");
  } else if (K == TEXT("why.swap.impossible")) {
    Text = TEXT("fighters cannot swap spaces");
  } else if (K == TEXT("why.immobilized")) {
    Text = ArgOf(TEXT("fighterName")) + TEXT(" cannot move");
  } else if (K == TEXT("why.fighter.not.yours")) {
    Text = TEXT("that is an opponent's fighter");
  } else if (K == TEXT("why.fighter.defeated")) {
    Text = TEXT("fighter is defeated");
  } else if (K == TEXT("why.boost.no.value")) {
    Text = TEXT("this card has no BOOST");
  } else if (K == TEXT("why.boost.card.gone")) {
    Text = TEXT("the boost card is no longer in hand");
  } else if (K == TEXT("why.client.desync")) {
    Text = TEXT("out of sync with the server");
  } else {
    Text = K;
  }
  return Text + TEXT(" [") + K + TEXT("]");
}

FString FS09Reason::Text() const {
  if (!IsSet()) return FString();
  FString Out = S08WhyText::En(Key, Args);
  if (Args.Contains(TEXT("orderHint"))) {
    // MS-E-34: the ally leaves later in the order - say how to fix it.
    Out += TEXT(". ") + S08WhyText::En(FName(TEXT("ms.order.swap.hint")));
  }
  const FString* Cell = Args.Find(TEXT("cell"));
  return Cell && !Cell->IsEmpty() ? *Cell + TEXT(": ") + Out : Out;
}

FString FS09DraftMove::BadgeText() const {
  if (Status == ES09DraftMoveStatus::Conflict) return FString();
  FString Text = FString::Printf(TEXT("%d/%d"), Path.Num(), Allowance);
  if (Status == ES09DraftMoveStatus::NeedBoost) Text += FString::Printf(TEXT(" \u00B7 need +%d"), RequiredBoost);
  return Text;
}

int32 FS09ReachTiers::ChipAt(const FIntPoint& Cell) const {
  if (!bValid || !BoostTier.Contains(Cell)) return 0;
  const int32 Steps = Reach.DistanceTo(Cell);
  return Steps == INDEX_NONE ? 0 : Steps - Base;
}

TArray<FS09BoostCard> FS09DraftEval::BoostHand(const FS08Snapshot& Snapshot, const FString& ViewerId) {
  TArray<FS09BoostCard> Out;
  TArray<FS09CardView> Cards;
  if (!OwnHandCards(Snapshot, ViewerId, Cards)) return Out;
  for (const FS09CardView& Card : Cards) {
    if (Card.bHidden) continue;
    FS09BoostCard Boost;
    Boost.InstanceId = Card.InstanceId;
    Boost.bHasBoost = Card.bHasBoostValue;
    Boost.Boost = Card.bHasBoostValue ? Card.BoostValue : 0;
    Out.Add(MoveTemp(Boost));
  }
  return Out;
}

int32 FS09DraftEval::SelectedBoostOf(const TArray<FS09BoostCard>& Hand, const FString& BoostCardId) {
  if (BoostCardId.IsEmpty()) return 0;
  const FS09BoostCard* Card =
      Hand.FindByPredicate([&BoostCardId](const FS09BoostCard& C) { return SameDraftId(C.InstanceId, BoostCardId); });
  return Card && Card->bHasBoost ? Card->Boost : 0; // cardBoost(selected) ?? 0
}

int32 FS09DraftEval::MaxBoostOf(const TArray<FS09BoostCard>& Hand) {
  int32 Max = 0; // hand.reduce((m, c) => Math.max(m, cardBoost(c) ?? 0), 0)
  for (const FS09BoostCard& Card : Hand) {
    if (Card.bHasBoost) Max = FMath::Max(Max, Card.Boost);
  }
  return Max;
}

bool FS09DraftEval::IsImmobilized(const FS08BoardFighter& Fighter) {
  return Fighter.Effects.ContainsByPredicate(
      [](const FString& Effect) { return Effect.Equals(TEXT("immobilized"), ESearchCase::CaseSensitive); });
}

FS09ReachTiers FS09DraftEval::ComputeTiers(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Work,
                                           const FString& FighterId, int32 SelectedBoost, int32 MaxBoost) {
  FS09ReachTiers Tiers;
  Tiers.FighterId = FighterId;
  const FS08BoardFighter* Fighter = FindWorkFighter(Work, FighterId);
  if (!Fighter) return Tiers;
  Tiers.Base = FS08BoardModel::FighterMovement(*Fighter);
  Tiers.BaseSteps = ClampSteps(int64(Tiers.Base) + SelectedBoost);
  Tiers.BoostSteps = ClampSteps(int64(Tiers.Base) + MaxBoost);
  const int32 MaxSteps = FMath::Max(Tiers.BaseSteps, Tiers.BoostSteps);
  Tiers.Reach = FS08BoardModel::ComputeReachMap(Board, Work, FighterId, MaxSteps);
  if (!Tiers.Reach.bValid) return Tiers;
  Tiers.bValid = true;
  Tiers.Start = Tiers.Reach.Start;
  // backend reachTiers: endpoints by K, split by distance.
  for (const FIntPoint& Cell : FS08BoardModel::ReachEndpoints(Board, Work, Tiers.Reach, MaxSteps)) {
    const int32 Steps = Tiers.Reach.DistanceTo(Cell);
    if (Steps <= Tiers.BaseSteps) {
      Tiers.BaseTier.Add(Cell);
    } else if (Steps <= Tiers.BoostSteps) {
      Tiers.BoostTier.Add(Cell);
    }
  }
  return Tiers;
}

FS09Reason FS09DraftEval::DestinationReason(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Work,
                                            const FS08BoardFighter& Mover, const FIntPoint& Dest, int32 Base,
                                            int32 SelectedBoost, int32 MaxBoost,
                                            const TArray<FS09DraftMove>& Draft) {
  const FString Cell = Board.CellLabel(Dest.X, Dest.Y);
  if (!Board.IsBoardSpace(Dest.X, Dest.Y)) return FS09Reason::Make(TEXT("why.cell.not.space")).Arg(TEXT("cell"), Cell);
  if (const FS08BoardFighter* Occupant = FS08BoardModel::FighterAt(Work, Dest.X, Dest.Y, Mover.Id)) {
    if (!SameDraftId(Occupant->OwnerId, Mover.OwnerId)) {
      return FS09Reason::Make(TEXT("why.cell.enemy")).Arg(TEXT("cell"), Cell);
    }
    // An ally still on Dest: its own move (not applied yet - later in the
    // order, or itself in conflict) either ends on the mover's cell (a swap,
    // impossible in any order - MS-E-35) or, when it comes LATER in the
    // order, leaves Dest after the mover (MS-E-34: the order hint). A mover
    // without a move counts as last (a new move goes to the end).
    int32 MoverIndex = Draft.IndexOfByPredicate(
        [&Mover](const FS09DraftMove& Move) { return SameDraftId(Move.FighterId, Mover.Id); });
    if (MoverIndex == INDEX_NONE) MoverIndex = Draft.Num();
    for (int32 Index = 0; Index < Draft.Num(); ++Index) {
      const FS09DraftMove& Other = Draft[Index];
      if (!SameDraftId(Other.FighterId, Occupant->Id)) continue;
      if (Other.DestX == Mover.X && Other.DestY == Mover.Y) {
        return FS09Reason::Make(TEXT("why.swap.impossible")).Arg(TEXT("cell"), Cell);
      }
      if (Index > MoverIndex && (Other.DestX != Dest.X || Other.DestY != Dest.Y)) {
        return FS09Reason::Make(TEXT("why.cell.ally")).Arg(TEXT("cell"), Cell).Arg(TEXT("orderHint"), 1);
      }
      break;
    }
    return FS09Reason::Make(TEXT("why.cell.ally")).Arg(TEXT("cell"), Cell);
  }
  const FS08Cell* Terrain = Board.CellAt(Dest.X, Dest.Y);
  if (!Terrain || !Terrain->IsPassable()) return FS09Reason::Make(TEXT("why.cell.no.path")).Arg(TEXT("cell"), Cell);
  // MS-E-19: a path that exists but is longer than the best boost names the
  // numbers; no path at all (blocked, no links) does not.
  const FS08ReachMap Unlimited = FS08BoardModel::ComputeReachMap(Board, Work, Mover.Id, MAX_int32);
  const int32 Need = Unlimited.DistanceTo(Dest);
  if (Need != INDEX_NONE) {
    return FS09Reason::Make(TEXT("why.cell.unreachable"))
        .Arg(TEXT("cell"), Cell)
        .Arg(TEXT("need"), Need)
        .Arg(TEXT("have"), ClampSteps(int64(Base) + FMath::Max(SelectedBoost, MaxBoost)));
  }
  return FS09Reason::Make(TEXT("why.cell.no.path")).Arg(TEXT("cell"), Cell);
}

FS09DraftEval FS09DraftEval::Evaluate(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                                      TArray<FS09DraftMove>& Moves, const TArray<FS09BoostCard>& Hand,
                                      const FString& BoostCardId, const FString& ActorId) {
  FS09DraftEval Eval;
  Eval.SelectedBoost = SelectedBoostOf(Hand, BoostCardId);
  Eval.MaxBoost = MaxBoostOf(Hand);
  Eval.Work = Fighters;
  Eval.Tiers.SetNum(Moves.Num());
  TArray<FString> Seen;
  for (int32 Index = 0; Index < Moves.Num(); ++Index) {
    FS09DraftMove& Move = Moves[Index];
    Move.Order = Index;
    Move.Path.Reset();
    Move.Status = ES09DraftMoveStatus::Ok;
    Move.Conflict = ES09DraftConflict::None;
    Move.RequiredBoost = 0;
    Move.Reason.Reset();
    FS08BoardFighter* Fighter = FindWorkFighter(Eval.Work, Move.FighterId);
    Move.Base = Fighter ? FS08BoardModel::FighterMovement(*Fighter) : 0;
    Move.Allowance = ClampSteps(int64(Move.Base) + Eval.SelectedBoost);
    auto SetConflict = [&Move](ES09DraftConflict Why, FS09Reason Reason) {
      Move.Status = ES09DraftMoveStatus::Conflict;
      Move.Conflict = Why;
      Move.Reason = MoveTemp(Reason);
      Move.Path.Reset();
      Move.RequiredBoost = 0;
    };
    // backend evaluateDraft gate order: duplicate, missing, not-yours,
    // defeated (health <= 0 only - MS-E-77), immobilized.
    if (Seen.ContainsByPredicate([&Move](const FString& Id) { return SameDraftId(Id, Move.FighterId); })) {
      SetConflict(ES09DraftConflict::Duplicate, FS09Reason::Make(TEXT("why.client.desync")));
      continue;
    }
    Seen.Add(Move.FighterId);
    if (!Fighter) {
      SetConflict(ES09DraftConflict::Missing, FS09Reason::Make(TEXT("why.client.desync")));
      continue;
    }
    if (!ActorId.IsEmpty() && !SameDraftId(Fighter->OwnerId, ActorId)) {
      SetConflict(ES09DraftConflict::NotYours, FS09Reason::Make(TEXT("why.fighter.not.yours")));
      continue;
    }
    if (!Fighter->CanBeMover()) {
      SetConflict(ES09DraftConflict::Defeated, FS09Reason::Make(TEXT("why.fighter.defeated")));
      continue;
    }
    if (IsImmobilized(*Fighter)) {
      SetConflict(ES09DraftConflict::Immobilized,
                  FS09Reason::Make(TEXT("why.immobilized")).Arg(TEXT("fighterName"), FighterDisplayName(*Fighter)));
      continue;
    }
    FS09ReachTiers& Tiers = Eval.Tiers[Index];
    Tiers = ComputeTiers(Board, Eval.Work, Move.FighterId, Eval.SelectedBoost, Eval.MaxBoost);
    const FIntPoint Dest(Move.DestX, Move.DestY);
    if (!FS08BoardModel::BuildCanonicalPath(Board, Eval.Work, Tiers.Reach, Dest, Move.Path)) {
      // no-path: the tiers stay (backend conflict('no-path', tiers)).
      SetConflict(ES09DraftConflict::NoPath, DestinationReason(Board, Eval.Work, *Fighter, Dest, Move.Base,
                                                               Eval.SelectedBoost, Eval.MaxBoost, Moves));
      continue;
    }
    Move.RequiredBoost = FMath::Max(0, Move.Path.Num() - Move.Base);
    if (Move.RequiredBoost > Eval.SelectedBoost) {
      Move.Status = ES09DraftMoveStatus::NeedBoost;
      Move.Reason = FS09Reason::Make(TEXT("why.cell.needs.boost"))
                        .Arg(TEXT("cell"), Board.CellLabel(Dest.X, Dest.Y))
                        .Arg(TEXT("n"), Move.RequiredBoost);
    }
    Fighter->X = Dest.X;
    Fighter->Y = Dest.Y;
  }
  for (const FS09DraftMove& Move : Moves) {
    switch (Move.Status) {
      case ES09DraftMoveStatus::Ok: ++Eval.NumOk; break;
      case ES09DraftMoveStatus::NeedBoost:
        ++Eval.NumNeedBoost;
        Eval.HighlightMinBoost = FMath::Max(Eval.HighlightMinBoost, Move.RequiredBoost);
        break;
      default: ++Eval.NumConflict; break;
    }
  }
  if (Eval.HighlightMinBoost > 0) {
    for (const FS09BoostCard& Card : Hand) {
      if (Card.bHasBoost && Card.Boost >= Eval.HighlightMinBoost && !SameDraftId(Card.InstanceId, BoostCardId)) {
        Eval.HighlightCardIds.Add(Card.InstanceId);
      }
    }
  }
  return Eval;
}

bool FS09CommandUi::OnSnapshot(const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                               const TArray<FS08BoardFighter>& Fighters) {
  const ES09CommandMode OldMode = Mode;
  // ENV-O6: attack range of the board-less draft overloads follows the
  // latest authoritative board (links + zones).
  SnapshotBoard = Board;
  SnapshotFighters = Fighters;
  // MS-E-95: an applied snapshot with a new seq is the undo barrier (a
  // same-seq re-read - e.g. the refetch after a rejection - is not).
  if (Snapshot.SequenceNumber != LastSnapshotSeq) UndoStack.Reset();
  LastSnapshotSeq = Snapshot.SequenceNumber;
  // MS-S-02/03: the fighter inspected outside a draft (kept below while the
  // viewer may still begin).
  const FString Inspected = OldMode == ES09CommandMode::None ? SelectedFighterId : FString();

  // GD-036: terminal state closes every local draft - gameplay input is
  // dead on the result screen (the server would reject it anyway: executor
  // early-returns, GameInProgressGuard blocks after the row goes FINISHED).
  if (Snapshot.Phase == TEXT("GAME_OVER")) {
    Mode = ES09CommandMode::None;
    ResetManeuverDraft();
    ClearPreDraft();
    PendingDiscard = FS08PendingHandDiscard();
    DiscardSelection.Reset();
    AttackAttackerId.Reset();
    AttackTargetId.Reset();
    AttackCardId.Reset();
    DefenseCardId.Reset();
    SchemeCardId.Reset();
    ResetPendingDraft();
    SyncDraftCache();
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

  const bool bOwnManeuver = PendingManeuverFor(Snapshot, ViewerId, ManeuverId);
  // MS-T-04: without the viewer's pendingManeuver no maneuver draft survives
  // in ANY mode (it would otherwise leak into the next maneuver).
  if (!bOwnManeuver) ResetManeuverDraft();

  if (bOwnManeuver) {
    Mode = ES09CommandMode::ManeuverDraft;
    bool bRestored = false;
    bool bOpened = false;
    if (!PendingManeuverId.Equals(ManeuverId, ESearchCase::CaseSensitive)) {
      bOpened = true;
      // MS-R-55: a draft belongs to ONE pendingManeuver.id. Another id starts
      // empty; the same id after a gameplay-HUD reset (re-entry into the
      // match inside this process) comes back from the controller's cache.
      ResetManeuverDraft();
      PendingManeuverId = ManeuverId;
      FS08ManeuverDraftCache Cached;
      if (RecallDraftHook && RecallDraftHook(ManeuverId, Cached)) {
        for (int32 Index = 0; Index < Cached.FighterIds.Num() && Index < Cached.Dests.Num(); ++Index) {
          FS09DraftMove& Move = Moves.AddDefaulted_GetRef();
          Move.FighterId = Cached.FighterIds[Index];
          Move.DestX = Cached.Dests[Index].X;
          Move.DestY = Cached.Dests[Index].Y;
        }
        BoostCardId = Cached.BoostCardId;
        bRestored = true;
      }
    }
    // Revalidate the carried draft against the FRESH authoritative state:
    // moves of fighters that can no longer move at all (defeated, gone, not
    // own - MS-E-41) are dropped; every other move stays and is re-evaluated
    // below - a lost path is a Conflict, a longer one NeedBoost (MS-E-53).
    Moves.RemoveAll([&](const FS09DraftMove& Move) {
      const FS08BoardFighter* Own = FindOwnFighter(Fighters, Move.FighterId);
      // MS-E-16: a carried move that now ends on the fighter's own cell (an
      // effect put it there) is a "stay" - never an entry of the draft.
      return Own == nullptr || (Own->X == Move.DestX && Own->Y == Move.DestY);
    });
    if (!BoostCardId.IsEmpty() && !OwnHandIds(Snapshot).Contains(BoostCardId)) {
      // MS-E-15: the card left the hand - the boost is dropped, the moves
      // re-evaluate (NeedBoost), the reason stays for the toast.
      BoostCardId.Reset();
      LastReason = FS09Reason::Make(TEXT("why.boost.card.gone"));
    }
    FS09Reason SelectionGate;
    if (!SelectedFighterId.IsEmpty() && !CanMoveFighter(SelectedFighterId, Fighters, SelectionGate)) {
      SelectedFighterId.Reset(); // e.g. immobilized since the last snapshot (MS-R-05)
    }
    // MS-T-05: every snapshot re-evaluates the whole draft on the fresh
    // positions and hand (statuses, paths, the selected fighter's tiers).
    DraftHand = FS09DraftEval::BoostHand(Snapshot, ViewerId);
    ReevaluateDraft(Board, Fighters);
    if (bRestored) {
      TraceDraftOp(TEXT("restore"), FString(), Board);
    } else if (Moves.Num() > 0 || !BoostCardId.IsEmpty()) {
      TraceDraftOp(TEXT("snapshot"), FString(), Board);
    }
    // MS-R-02 / MS-E-84: a freshly opened draft takes the pre-draft target
    // (also after MS-S-10); a restored draft (same id) keeps its own.
    if (bOpened && !bRestored && PreDraft.bSet) {
      CarryPreDraft(Board, Fighters);
    } else if (bOpened) {
      ClearPreDraft();
    }
    // DE-017 (MS-R-75; 01 F-08): the candidate rings (V-17) of MS-S-06 are
    // drawn in the frame the draft opens; with exactly one movable fighter
    // the draft opens in MS-S-07 on it. Only on opening: after Esc back to
    // MS-S-06 nothing re-selects, and there is never an advance to the next
    // fighter after a move is assigned.
    if (bOpened) {
      const TArray<FString> Movers = MovableFighterIds(Fighters);
      if (SelectedFighterId.IsEmpty() && Movers.Num() == 1) {
        SelectedFighterId = Movers[0];
        bAutoSelected = true;
        RefreshSelectedTiers(Board, Fighters);
        ++DraftRevision;
      }
      DraftTraceLine(FString::Printf(TEXT("MS-DRAFT op=candidates rev=%u src=snapshot n=%d ids=%s autoselect=%s"),
                                     DraftRevision, Movers.Num(),
                                     Movers.Num() > 0 ? *FString::Join(Movers, TEXT(",")) : TEXT("-"),
                                     bAutoSelected ? *SelectedFighterId : TEXT("-")));
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
    // MS-T-12 (MS-S-12): the only legal fighter of a MOVE / PLACE head is
    // picked at once (its spaces light up without a click - with `value` 0
    // the panel offers just "Stay in place"), and the picked fighter's legal
    // spaces follow every snapshot, not only while a target is set.
    const bool bMovePlace = IsPendingMovePlace();
    if (bMovePlace && PendingFighterId.IsEmpty()) {
      TArray<FString> Legal;
      if (PendingLegalFighters(Fighters, Legal) && Legal.Num() == 1) PendingFighterId = Legal[0];
    }
    if (bPendingCellSet || (bMovePlace && !PendingFighterId.IsEmpty())) {
      PendingCells = ComputePendingCells(Snapshot, Board, Fighters);
      if (bPendingCellSet && !PendingCells.Contains(FS08BoardModel::CellKey(PendingCellX, PendingCellY))) {
        bPendingCellSet = false;
      }
    } else {
      PendingCells.Reset();
    }
    if (bMovePlace) TracePendingMovePlace(Board, Fighters);
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
    PendingDiscard = FS08PendingHandDiscard();
    DiscardSelection.Reset();
    AttackAttackerId.Reset();
    AttackTargetId.Reset();
    AttackCardId.Reset();
    DefenseCardId.Reset();
    SchemeCardId.Reset();
    ResetPendingDraft();
  }
  // MS-S-02/03 live on while the viewer may still begin (the pre-draft
  // survives MS-S-10 re-reads, MS-R-02); any other state drops them.
  if (Mode == ES09CommandMode::None && !Inspected.IsEmpty() && CanKeepPreDraft(Snapshot)) {
    FS09Reason Gate;
    if (CanMoveFighter(Inspected, Fighters, Gate)) {
      SelectedFighterId = Inspected;
      DraftHand = FS09DraftEval::BoostHand(Snapshot, ViewerId);
      ReevaluateDraft(Board, Fighters);
      if (PreDraft.bSet) {
        FS09DraftMove Probe;
        FS09Reason Why;
        if (EvaluateDestination(PreDraft.FighterId, PreDraft.X, PreDraft.Y, Board, Fighters, Probe, Why)) {
          PreDraft.Status = Probe.Status;
          PreDraft.RequiredBoost = Probe.RequiredBoost;
        } else {
          LastReason = FS09Reason::Make(TEXT("why.predraft.lost")).Arg(TEXT("cell"), Board.CellLabel(PreDraft.X, PreDraft.Y));
          ClearPreDraft();
        }
      }
    } else {
      ClearPreDraft();
    }
  } else if (Mode != ES09CommandMode::ManeuverDraft) {
    ClearPreDraft();
  }
  SyncDraftCache();
  return Mode != OldMode;
}

bool FS09CommandUi::CanBeginManeuver(const FS08Snapshot& Snapshot,
                                     FString& OutReason) const {
  FS09Reason Key;
  return CanBeginManeuver(Snapshot, OutReason, Key);
}

bool FS09CommandUi::CanBeginManeuver(const FS08Snapshot& Snapshot, FString& OutReason,
                                     FS09Reason& OutKey) const {
  OutReason.Reset();
  OutKey.Reset();
  auto Refuse = [&](const TCHAR* Key, const FString& Reason) {
    OutKey = FS09Reason::Make(Key);
    OutReason = Reason;
    return false;
  };
  if (Snapshot.Phase == TEXT("GAME_OVER")) {
    return Refuse(TEXT("why.state.changed"), TEXT("the duel is over - no gameplay input on the result screen"));
  }
  if (Mode == ES09CommandMode::ManeuverDraft) {
    return Refuse(TEXT("why.draft.open"), TEXT("a maneuver draft is already open (server draw committed)"));
  }
  if (Mode == ES09CommandMode::DiscardDraft) {
    return Refuse(TEXT("why.state.changed"), TEXT("finish the discard choice first"));
  }
  if (bHasPendingChoice) {
    // MS-E-47: the opponent's choice blocks the begin on the server.
    return Refuse(PendingChoice.PlayerId != ViewerId ? TEXT("why.wait.opponent.choice") : TEXT("why.state.changed"),
                  TEXT("a pending choice is open (resolve the queue head first)"));
  }
  if (bCommandInFlight) {
    return Refuse(TEXT("why.syncing"), TEXT("a command is already in flight"));
  }
  if (Snapshot.CurrentTurnPlayerId != ViewerId) {
    return Refuse(TEXT("why.not.your.turn"), TEXT("not your turn"));
  }
  if (Snapshot.Phase != TEXT("ACTION_MANEUVER") && Snapshot.Phase != TEXT("ACTION_ATTACK")) {
    return Refuse(TEXT("why.maneuver.not.open"), TEXT("maneuver is not legal in phase ") + Snapshot.Phase);
  }
  const TSharedPtr<FJsonObject> Meta = Snapshot.Metadata.IsValid() ? Snapshot.Metadata->AsObject() : nullptr;
  double Actions = 1.0;
  if (Meta.IsValid() && Meta->TryGetNumberField(TEXT("actionsRemaining"), Actions) && Actions <= 0.0) {
    return Refuse(TEXT("why.no.actions"), TEXT("no actions left"));
  }
  return true;
}

FS09Reason FS09CommandUi::EndTurnReason(const FS08Snapshot& Snapshot) const {
  // DE-015 (SD-44): the server rule - endTurn only after both actions
  // (ACTIONS_REMAINING), never a pass (PASS_NOT_ALLOWED) - explained before
  // the send, by key; the button and the E key share this one answer.
  if (Snapshot.Phase == TEXT("GAME_OVER")) return FS09Reason::Make(TEXT("why.state.changed"));
  if (bCommandInFlight) return FS09Reason::Make(TEXT("why.syncing"));
  if (Snapshot.CurrentTurnPlayerId != ViewerId) return FS09Reason::Make(TEXT("why.not.your.turn"));
  if (Mode == ES09CommandMode::ManeuverDraft || !FS08Contracts::PendingManeuverId(Snapshot).IsEmpty()) {
    return FS09Reason::Make(TEXT("why.draft.open"));
  }
  if (Mode == ES09CommandMode::DiscardDraft) {
    return FS09Reason::Make(TEXT("why.discard.count"))
        .Arg(TEXT("need"), PendingDiscard.Count)
        .Arg(TEXT("have"), DiscardSelection.Num());
  }
  if (bHasPendingChoice) {
    return FS09Reason::Make(PendingChoice.PlayerId != ViewerId ? TEXT("why.wait.opponent.choice")
                                                               : TEXT("why.choice.required"));
  }
  if (Combat.bPresent) return FS09Reason::Make(TEXT("why.wait.defender"));
  int32 Actions = 0;
  bool bPresent = false;
  const TSharedPtr<FJsonObject> Meta = Snapshot.Metadata.IsValid() ? Snapshot.Metadata->AsObject() : nullptr;
  if (Meta.IsValid()) FS08Contracts::ReadIntLike(Meta.ToSharedRef(), TEXT("actionsRemaining"), Actions, bPresent);
  if (bPresent && Actions > 0) {
    return FS09Reason::Make(TEXT("why.actions.remaining")).Arg(TEXT("n"), Actions);
  }
  // The network guard accepts endTurn only in ACTION_MANEUVER / ACTION_ATTACK;
  // an unknown count (a merge without metadata) waits for the next body.
  if (!FS08FlowController::IsEndTurnPhase(Snapshot.Phase) || !bPresent) return FS09Reason::Make(TEXT("why.syncing"));
  return FS09Reason();
}

TArray<FString> FS09CommandUi::OwnHandIds(const FS08Snapshot& Snapshot) const {
  TArray<FS09CardView> Cards;
  TArray<FString> Ids;
  if (OwnHandCards(Snapshot, ViewerId, Cards)) {
    for (const FS09CardView& Card : Cards) Ids.Add(Card.InstanceId);
  }
  return Ids;
}

const FS08BoardFighter* FS09CommandUi::FindOwnFighter(
    const TArray<FS08BoardFighter>& Fighters, const FString& FighterId) const {
  // MS-T-04 (F10): the maneuver MOVER role - validateManeuver rejects only
  // health <= 0, so isDefeated with health > 0 still moves (MS-E-77); ids
  // compare exactly. Immobilized is CanMoveFighter's gate, not this one.
  // SelectAttacker shares the lookup (unchanged: health > 0 with a position).
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (SameDraftId(Fighter.Id, FighterId) && SameDraftId(Fighter.OwnerId, ViewerId) && Fighter.CanBeMover() &&
        Fighter.X >= 0 && Fighter.Y >= 0) {
      return &Fighter;
    }
  }
  return nullptr;
}

bool FS09CommandUi::CanMoveFighter(const FString& FighterId, const TArray<FS08BoardFighter>& Fighters,
                                   FS09Reason& OutReason) const {
  OutReason.Reset();
  const FS08BoardFighter* Fighter = FindWorkFighter(Fighters, FighterId);
  if (!Fighter) {
    OutReason = FS09Reason::Make(TEXT("why.client.desync"));
  } else if (!SameDraftId(Fighter->OwnerId, ViewerId)) {
    OutReason = FS09Reason::Make(TEXT("why.fighter.not.yours"));
  } else if (!Fighter->CanBeMover()) {
    OutReason = FS09Reason::Make(TEXT("why.fighter.defeated"));
  } else if (!FindOwnFighter(Fighters, FighterId)) {
    OutReason = FS09Reason::Make(TEXT("why.client.desync")); // living, but no board position
  } else if (FS09DraftEval::IsImmobilized(*Fighter)) {
    // MS-R-05 / B-06: greyed with the reason, no target may be assigned.
    OutReason = FS09Reason::Make(TEXT("why.immobilized")).Arg(TEXT("fighterName"), FighterDisplayName(*Fighter));
  }
  return !OutReason.IsSet();
}

FS09Reason FS09CommandUi::RejectionReason(const FS08Rejection& Rejection, const FS08BoardModel& Board,
                                          const TArray<FS08BoardFighter>& Fighters) const {
  FS09Reason Out = FS09Reason::Make(*Rejection.WhyKey.ToString());
  for (const TPair<FString, FString>& Arg : Rejection.WhyArgs) Out.Arg(*Arg.Key, Arg.Value);
  const bool bCell = Rejection.Cell.X >= 0 && Rejection.Cell.Y >= 0;
  if (bCell) Out.Arg(TEXT("cell"), Board.CellLabel(Rejection.Cell.X, Rejection.Cell.Y));
  const bool bEffect = Rejection.Op == ES08RejectOp::PendingEffect;
  // Who the rejection is about.
  FString Who;
  if (!bEffect) {
    for (const FS09DraftMove& Move : Moves) {
      if (bCell && Move.DestX == Rejection.Cell.X && Move.DestY == Rejection.Cell.Y) Who = Move.FighterId;
    }
    if (Who.IsEmpty() && Rejection.WhyKey == FName(TEXT("why.immobilized"))) {
      for (const FS09DraftMove& Move : Moves) {
        const FS08BoardFighter* Fighter = FindWorkFighter(Fighters, Move.FighterId);
        if (Fighter && FS09DraftEval::IsImmobilized(*Fighter)) {
          Who = Move.FighterId;
          break;
        }
      }
    }
    if (Who.IsEmpty()) Who = SelectedFighterId;
    if (Who.IsEmpty() && Moves.Num() > 0) Who = Moves[0].FighterId;
  } else {
    Who = PendingFighterId;
  }
  const FS08BoardFighter* Mover = FindWorkFighter(Fighters, Who);
  const FString Template = S08WhyText::Template(Out.Key);
  if (Template.Contains(TEXT("{fighterName}")) && !Out.Args.Contains(TEXT("fighterName"))) {
    Out.Arg(TEXT("fighterName"), Mover ? FighterDisplayName(*Mover) : (Who.IsEmpty() ? FString(TEXT("-")) : Who));
  }
  if (Template.Contains(TEXT("{have}")) && !Out.Args.Contains(TEXT("have"))) {
    const int32 Have = bEffect ? (PendingChoice.bHasValue ? PendingChoice.Value : 1)
                               : (Mover ? FS08BoardModel::FighterMovement(*Mover) : 0) +
                                     FS09DraftEval::SelectedBoostOf(DraftHand, BoostCardId);
    Out.Arg(TEXT("have"), Have);
  }
  if (Template.Contains(TEXT("{need}")) && !Out.Args.Contains(TEXT("need"))) {
    // The steps of the shortest path on the snapshot (unlimited allowance).
    const int32 Need = Mover && bCell
                           ? FS08BoardModel::ComputeReachMap(Board, Fighters, Mover->Id, MAX_int32)
                                 .DistanceTo(Rejection.Cell)
                           : INDEX_NONE;
    if (Need == INDEX_NONE) {
      FS09Reason NoPath = FS09Reason::Make(TEXT("why.cell.no.path"));
      if (bCell) NoPath.Arg(TEXT("cell"), Board.CellLabel(Rejection.Cell.X, Rejection.Cell.Y));
      return NoPath;
    }
    Out.Arg(TEXT("need"), Need);
  }
  return Out;
}

FS08ManeuverDraftCache FS09CommandUi::ExportDraft() const {
  FS08ManeuverDraftCache Out;
  if (Mode != ES09CommandMode::ManeuverDraft || PendingManeuverId.IsEmpty()) return Out;
  Out.ManeuverId = PendingManeuverId;
  for (const FS09DraftMove& Move : Moves) {
    Out.FighterIds.Add(Move.FighterId);
    Out.Dests.Add(FIntPoint(Move.DestX, Move.DestY));
  }
  Out.BoostCardId = BoostCardId;
  return Out;
}

void FS09CommandUi::SyncDraftCache() {
  if (!StoreDraftHook) return;
  const FS08ManeuverDraftCache Draft = ExportDraft();
  auto SameIds = [](const TArray<FString>& A, const TArray<FString>& B) {
    if (A.Num() != B.Num()) return false;
    for (int32 Index = 0; Index < A.Num(); ++Index) {
      if (!SameDraftId(A[Index], B[Index])) return false;
    }
    return true;
  };
  if (bDraftCacheSynced && SameDraftId(Draft.ManeuverId, LastStoredDraft.ManeuverId) &&
      SameIds(Draft.FighterIds, LastStoredDraft.FighterIds) && Draft.Dests == LastStoredDraft.Dests &&
      SameDraftId(Draft.BoostCardId, LastStoredDraft.BoostCardId)) {
    return;
  }
  bDraftCacheSynced = true;
  LastStoredDraft = Draft;
  StoreDraftHook(Draft);
}

void FS09CommandUi::ResetManeuverDraft() {
  UndoStack.Reset(); // another maneuverId / no maneuver: the stack goes (MS-E-113)
  PendingManeuverId.Reset();
  Moves.Reset();
  BoostCardId.Reset();
  SelectedFighterId.Reset();
  bAutoSelected = false;
  ResetDraftEval();
  DirtyDefeatedTraced.Reset();
}

void FS09CommandUi::TraceDirtyDefeated(const TArray<FS08BoardFighter>& Fighters, const FString& FighterId) {
  const FS08BoardFighter* Fighter = FindWorkFighter(Fighters, FighterId);
  if (!Fighter || !Fighter->bDefeated || Fighter->Health <= 0 || DirtyDefeatedTraced.Contains(FighterId)) return;
  DirtyDefeatedTraced.Add(FighterId);
  DraftTraceLine(FString::Printf(TEXT("MS-DATA dirtyDefeated fighter=%s"), *FighterId));
}

// ---- MS-T-05 draft bookkeeping ----------------------------------------------

int32 FS09CommandUi::MoveIndexOf(const FString& FighterId) const {
  return Moves.IndexOfByPredicate(
      [&FighterId](const FS09DraftMove& Move) { return SameDraftId(Move.FighterId, FighterId); });
}

void FS09CommandUi::ResetDraftEval() {
  Eval = FS09DraftEval();
  SelectedTiers = FS09ReachTiers();
  ReachableCells.Reset();
  DraftHand.Reset();
  LastReason.Reset();
}

void FS09CommandUi::DeselectFighter() {
  SelectedFighterId.Reset();
  SelectedTiers = FS09ReachTiers();
  ReachableCells.Reset();
}

void FS09CommandUi::ReevaluateDraft(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters) {
  Eval = FS09DraftEval::Evaluate(Board, Fighters, Moves, DraftHand, BoostCardId, ViewerId);
  RefreshSelectedTiers(Board, Fighters);
  ++DraftRevision;
  SyncDraftCache();
}

void FS09CommandUi::RefreshSelectedTiers(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters) {
  SelectedTiers = FS09ReachTiers();
  ReachableCells.Reset();
  if (SelectedFighterId.IsEmpty()) return;
  const FS08BoardFighter* Own = FindOwnFighter(Fighters, SelectedFighterId);
  if (!Own) return;
  const int32 Index = MoveIndexOf(SelectedFighterId);
  if (Index != INDEX_NONE) {
    // Its move keeps its place: the tiers on the positions before it.
    if (Eval.Tiers.IsValidIndex(Index)) SelectedTiers = Eval.Tiers[Index];
  } else if (!FS09DraftEval::IsImmobilized(*Own)) {
    // A new move goes last: the tiers after every drafted move (work_n).
    SelectedTiers =
        FS09DraftEval::ComputeTiers(Board, Eval.Work, SelectedFighterId, Eval.SelectedBoost, Eval.MaxBoost);
  }
  if (!SelectedTiers.bValid) return;
  ReachableCells.Add(FS08BoardModel::CellKey(SelectedTiers.Start.X, SelectedTiers.Start.Y));
  for (const FIntPoint& Cell : SelectedTiers.BaseTier) ReachableCells.Add(FS08BoardModel::CellKey(Cell.X, Cell.Y));
}

TArray<FS08BoardFighter> FS09CommandUi::WorkStateFor(const FString& FighterId, const FS08BoardModel& Board,
                                                     const TArray<FS08BoardFighter>& Fighters) const {
  const int32 Index = MoveIndexOf(FighterId);
  TArray<FS09DraftMove> Prefix;
  Prefix.Append(Moves.GetData(), Index == INDEX_NONE ? Moves.Num() : Index);
  return FS09DraftEval::Evaluate(Board, Fighters, Prefix, DraftHand, BoostCardId, ViewerId).Work;
}

void FS09CommandUi::DraftTraceLine(const FString& Line) {
  FS08Trace::Write(Line);
  DraftTrace.Add(Line);
  if (DraftTrace.Num() > 64) DraftTrace.RemoveAt(0, DraftTrace.Num() - 64);
}

void FS09CommandUi::TraceDraftOp(const TCHAR* Op, const FString& FighterId, const FS08BoardModel& Board) {
  // 04 §9: src= click | key | auto; a re-evaluation by the server state is snapshot.
  const bool bServerOp = FCString::Strcmp(Op, TEXT("snapshot")) == 0 || FCString::Strcmp(Op, TEXT("restore")) == 0;
  FString Line = FString::Printf(TEXT("MS-DRAFT op=%s rev=%u src=%s"), Op, DraftRevision,
                                 bServerOp ? TEXT("snapshot") : S09DraftSourceName(DraftSource));
  const int32 Index = FighterId.IsEmpty() ? INDEX_NONE : MoveIndexOf(FighterId);
  if (Index != INDEX_NONE) {
    const FS09DraftMove& Move = Moves[Index];
    Line += FString::Printf(TEXT(" fighter=%s dest=%s order=%d status=%s required=%d"), *Move.FighterId,
                            *Board.CellLabel(Move.DestX, Move.DestY), Move.Order + 1, DraftStatusName(Move.Status),
                            Move.RequiredBoost);
  } else if (!FighterId.IsEmpty()) {
    Line += FString::Printf(TEXT(" fighter=%s"), *FighterId);
  }
  Line += FString::Printf(TEXT(" boost=%d moves=%d ok=%d needboost=%d conflict=%d"), Eval.SelectedBoost, Moves.Num(),
                          Eval.NumOk, Eval.NumNeedBoost, Eval.NumConflict);
  DraftTraceLine(Line);
  if (Index == INDEX_NONE || FCString::Strcmp(Op, TEXT("assign")) != 0) return;
  const FS09DraftMove& Move = Moves[Index];
  if (Move.Status == ES09DraftMoveStatus::Conflict || !Eval.Tiers.IsValidIndex(Index)) return;
  const FIntPoint Start = Eval.Tiers[Index].Start;
  TArray<FString> Cells = {Board.CellLabel(Start.X, Start.Y)};
  for (const FIntPoint& Cell : Move.Path) Cells.Add(Board.CellLabel(Cell.X, Cell.Y));
  DraftTraceLine(FString::Printf(TEXT("MS-PATH fighter=%s steps=%d allowance=%d key=canonical cells=%s"),
                                 *Move.FighterId, Move.Path.Num(), Move.Allowance, *FString::Join(Cells, TEXT(">"))));
}

bool FS09CommandUi::SelectFighter(const FString& FighterId, const FS08Snapshot& Snapshot,
                                  const FS08BoardModel& Board,
                                  const TArray<FS08BoardFighter>& Fighters) {
  if (Mode != ES09CommandMode::ManeuverDraft) return false;
  if (!CanMoveFighter(FighterId, Fighters, LastReason)) return false; // MS-R-05: e.g. why.immobilized
  TraceDirtyDefeated(Fighters, FighterId);
  SelectedFighterId = FighterId;
  DraftHand = FS09DraftEval::BoostHand(Snapshot, ViewerId);
  ReevaluateDraft(Board, Fighters);
  return true;
}

bool FS09CommandUi::EvaluateDestination(const FString& FighterId, int32 X, int32 Y, const FS08BoardModel& Board,
                                        const TArray<FS08BoardFighter>& Fighters, FS09DraftMove& OutMove,
                                        FS09Reason& OutReason) const {
  OutMove = FS09DraftMove();
  OutMove.FighterId = FighterId;
  OutMove.DestX = X;
  OutMove.DestY = Y;
  OutReason.Reset();
  if (!CanMoveFighter(FighterId, Fighters, OutReason)) return false;
  const int32 Selected = FS09DraftEval::SelectedBoostOf(DraftHand, BoostCardId);
  const int32 MaxBoost = FS09DraftEval::MaxBoostOf(DraftHand);
  const TArray<FS08BoardFighter> Work = WorkStateFor(FighterId, Board, Fighters);
  const FS08BoardFighter* Mover = FindWorkFighter(Work, FighterId);
  if (!Mover) {
    OutReason = FS09Reason::Make(TEXT("why.client.desync"));
    return false;
  }
  const FS09ReachTiers Tiers = FS09DraftEval::ComputeTiers(Board, Work, FighterId, Selected, MaxBoost);
  OutMove.Base = Tiers.Base;
  OutMove.Allowance = ClampSteps(int64(Tiers.Base) + Selected);
  const FIntPoint Dest(X, Y);
  if (!FS08BoardModel::BuildCanonicalPath(Board, Work, Tiers.Reach, Dest, OutMove.Path)) {
    OutReason =
        FS09DraftEval::DestinationReason(Board, Work, *Mover, Dest, Tiers.Base, Selected, MaxBoost, Moves);
    OutMove.Status = ES09DraftMoveStatus::Conflict;
    OutMove.Conflict = ES09DraftConflict::NoPath;
    OutMove.Reason = OutReason;
    return false;
  }
  OutMove.RequiredBoost = FMath::Max(0, OutMove.Path.Num() - OutMove.Base);
  if (OutMove.RequiredBoost > Selected) {
    OutMove.Status = ES09DraftMoveStatus::NeedBoost;
    OutMove.Reason = FS09Reason::Make(TEXT("why.cell.needs.boost"))
                         .Arg(TEXT("cell"), Board.CellLabel(X, Y))
                         .Arg(TEXT("n"), OutMove.RequiredBoost);
  }
  return true;
}

bool FS09CommandUi::SetDestination(const FString& FighterId, int32 X, int32 Y,
                                   const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                                   const TArray<FS08BoardFighter>& Fighters,
                                   FString& OutReason) {
  OutReason.Reset();
  LastReason.Reset();
  if (Mode != ES09CommandMode::ManeuverDraft) {
    OutReason = TEXT("no open maneuver draft");
    return false;
  }
  DraftHand = FS09DraftEval::BoostHand(Snapshot, ViewerId);
  const FS08BoardFighter* Own = FindOwnFighter(Fighters, FighterId);
  if (Own && Own->X == X && Own->Y == Y) {
    // MS-E-16 / B-01: the own cell is "stay" - never a move of the draft;
    // a drafted move of this fighter is cleared (MS-R-11).
    const int32 Index = MoveIndexOf(FighterId);
    if (Index != INDEX_NONE) {
      PushUndo(Moves, BoostCardId);
      Moves.RemoveAt(Index);
      ReevaluateDraft(Board, Fighters);
      TraceDraftOp(TEXT("clear"), FighterId, Board);
    }
    return true;
  }
  if (!CanMoveFighter(FighterId, Fighters, LastReason)) {
    OutReason = LastReason.Describe();
    return false;
  }
  TraceDirtyDefeated(Fighters, FighterId);
  FS09DraftMove Candidate;
  if (!EvaluateDestination(FighterId, X, Y, Board, Fighters, Candidate, LastReason)) {
    OutReason = LastReason.Describe();
    return false;
  }
  PushUndo(Moves, BoostCardId);
  const int32 Index = MoveIndexOf(FighterId);
  if (Index != INDEX_NONE) {
    // MS-E-38: an overwrite keeps the move's place in the order.
    Moves[Index].DestX = X;
    Moves[Index].DestY = Y;
  } else {
    // MS-E-114: a new (or re-assigned) move goes last.
    FS09DraftMove Move;
    Move.FighterId = FighterId;
    Move.DestX = X;
    Move.DestY = Y;
    Moves.Add(MoveTemp(Move));
  }
  ReevaluateDraft(Board, Fighters);
  TraceDraftOp(TEXT("assign"), FighterId, Board);
  return true;
}

void FS09CommandUi::ClearMove(const FString& FighterId) { ClearMove(FighterId, SnapshotBoard, SnapshotFighters); }

void FS09CommandUi::ClearMove(const FString& FighterId, const FS08BoardModel& Board,
                              const TArray<FS08BoardFighter>& Fighters) {
  LastReason.Reset();
  const TArray<FS09DraftMove> Before = Moves;
  if (Moves.RemoveAll([&FighterId](const FS09DraftMove& Move) { return SameDraftId(Move.FighterId, FighterId); }) ==
      0) {
    return;
  }
  PushUndo(Before, BoostCardId);
  ReevaluateDraft(Board, Fighters);
  TraceDraftOp(TEXT("clear"), FighterId, Board);
}

bool FS09CommandUi::MoveOrder(const FString& FighterId, int32 Delta, const FS08Snapshot& Snapshot,
                              const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters) {
  LastReason.Reset();
  if (Mode != ES09CommandMode::ManeuverDraft || Delta == 0) return false;
  const int32 From = MoveIndexOf(FighterId);
  if (From == INDEX_NONE) return false;
  const int32 To = FMath::Clamp(From + Delta, 0, Moves.Num() - 1);
  if (To == From) return false;
  PushUndo(Moves, BoostCardId);
  FS09DraftMove Move = Moves[From];
  Moves.RemoveAt(From);
  Moves.Insert(MoveTemp(Move), To);
  DraftHand = FS09DraftEval::BoostHand(Snapshot, ViewerId);
  ReevaluateDraft(Board, Fighters);
  TraceDraftOp(TEXT("order"), FighterId, Board);
  return true;
}

bool FS09CommandUi::ToggleBoostCard(const FString& InstanceId, const FS08Snapshot& Snapshot,
                                    FString& OutReason) {
  return ToggleBoostCard(InstanceId, Snapshot, SnapshotBoard, SnapshotFighters, OutReason);
}

bool FS09CommandUi::ToggleBoostCard(const FString& InstanceId, const FS08Snapshot& Snapshot,
                                    const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                                    FString& OutReason) {
  OutReason.Reset();
  LastReason.Reset();
  if (Mode != ES09CommandMode::ManeuverDraft) {
    OutReason = TEXT("boost is chosen inside an open maneuver draft");
    return false;
  }
  DraftHand = FS09DraftEval::BoostHand(Snapshot, ViewerId);
  const FString BoostBefore = BoostCardId;
  if (!BoostCardId.IsEmpty() && SameDraftId(BoostCardId, InstanceId)) {
    BoostCardId.Reset();
  } else {
    const FS09BoostCard* Card = DraftHand.FindByPredicate(
        [&InstanceId](const FS09BoostCard& C) { return SameDraftId(C.InstanceId, InstanceId); });
    if (!Card) {
      LastReason = FS09Reason::Make(TEXT("why.boost.card.gone"));
      OutReason = TEXT("boost must be an exact card instance in your hand");
      return false;
    }
    if (!Card->bHasBoost) {
      LastReason = FS09Reason::Make(TEXT("why.boost.no.value"));
      OutReason = LastReason.Describe();
      return false;
    }
    // One card per maneuver: another card REPLACES the selected one.
    BoostCardId = InstanceId;
  }
  PushUndo(Moves, BoostBefore);
  // MS-R-15: plates and statuses follow the boost in the same call.
  ReevaluateDraft(Board, Fighters);
  TraceDraftOp(TEXT("boost"), FString(), Board);
  return true;
}

TArray<FS09BoostCard> FS09CommandUi::BoostOffers() const {
  return DraftHand.FilterByPredicate([](const FS09BoostCard& Card) { return Card.bHasBoost; });
}

void FS09CommandUi::CancelDraft() {
  // LOCAL-ONLY: the server pendingManeuver stays exactly as it is - the
  // committed draw is not reversed and beginManeuver must not be re-sent
  // (CanBeginManeuver keeps refusing while the pending exists).
  // Esc's reset is undoable with Backspace (03 §3.2).
  if (Moves.Num() > 0 || !BoostCardId.IsEmpty()) PushUndo(Moves, BoostCardId);
  Moves.Reset();
  BoostCardId.Reset();
  SelectedFighterId.Reset();
  LastReason.Reset();
  // The draft stays open (same pending id): an empty draft evaluated on the
  // last snapshot keeps the hand data (max BOOST, offers) current.
  ReevaluateDraft(SnapshotBoard, SnapshotFighters);
  TraceDraftOp(TEXT("reset"), FString(), SnapshotBoard);
}

// ---- MS-T-07: input (03 §3, 04 §4.4) -------------------------------------------

void FS09CommandUi::PushUndo(const TArray<FS09DraftMove>& BeforeMoves, const FString& BeforeBoost) {
  FS09DraftOp Op;
  Op.Moves = BeforeMoves;
  Op.BoostCardId = BeforeBoost;
  UndoStack.Add(MoveTemp(Op));
  if (UndoStack.Num() > MaxUndo) UndoStack.RemoveAt(0, UndoStack.Num() - MaxUndo); // MS-E-94
}

bool FS09CommandUi::Undo(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters) {
  LastReason.Reset();
  if (Mode != ES09CommandMode::ManeuverDraft || UndoStack.Num() == 0) return false;
  const FS09DraftOp Op = UndoStack.Pop();
  Moves.Reset();
  for (const FS09DraftMove& Saved : Op.Moves) {
    FS09DraftMove& Move = Moves.AddDefaulted_GetRef();
    Move.FighterId = Saved.FighterId;
    Move.DestX = Saved.DestX;
    Move.DestY = Saved.DestY;
  }
  BoostCardId = Op.BoostCardId;
  ReevaluateDraft(Board, Fighters);
  TraceDraftOp(TEXT("undo"), FString(), Board);
  return true;
}

bool FS09CommandUi::InspectFighter(const FString& FighterId, const FS08Snapshot& Snapshot,
                                   const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters) {
  LastReason.Reset();
  if (Mode != ES09CommandMode::None) return false;
  if (!CanMoveFighter(FighterId, Fighters, LastReason)) return false;
  if (PreDraft.bSet && !SameDraftId(PreDraft.FighterId, FighterId)) ClearPreDraft();
  SelectedFighterId = FighterId;
  DraftHand = FS09DraftEval::BoostHand(Snapshot, ViewerId);
  ReevaluateDraft(Board, Fighters); // no moves: the tiers on the snapshot positions
  return true;
}

bool FS09CommandUi::SetPreDraft(const FString& FighterId, int32 X, int32 Y, const FS08Snapshot& Snapshot,
                                const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                                bool& bOutUnchanged) {
  bOutUnchanged = false;
  LastReason.Reset();
  if (Mode != ES09CommandMode::None) return false;
  if (!CanMoveFighter(FighterId, Fighters, LastReason)) return false;
  const FS08BoardFighter* Own = FindOwnFighter(Fighters, FighterId);
  if (Own && Own->X == X && Own->Y == Y) {
    ClearPreDraft(); // the own space: no target
    return true;
  }
  if (PreDraft.bSet && SameDraftId(PreDraft.FighterId, FighterId) && PreDraft.X == X && PreDraft.Y == Y) {
    bOutUnchanged = true; // MS-E-83
    return true;
  }
  DraftHand = FS09DraftEval::BoostHand(Snapshot, ViewerId);
  FS09DraftMove Candidate;
  if (!EvaluateDestination(FighterId, X, Y, Board, Fighters, Candidate, LastReason)) return false;
  if (!SameDraftId(SelectedFighterId, FighterId)) {
    SelectedFighterId = FighterId;
    ReevaluateDraft(Board, Fighters);
  }
  PreDraft.FighterId = FighterId;
  PreDraft.X = X;
  PreDraft.Y = Y;
  PreDraft.bSet = true;
  PreDraft.Status = Candidate.Status;
  PreDraft.RequiredBoost = Candidate.RequiredBoost;
  PreDraft.Source = DraftSource;
  DraftTraceLine(FString::Printf(TEXT("MS-DRAFT op=predraft rev=%u src=%s fighter=%s dest=%s status=%s required=%d"),
                                 DraftRevision, S09DraftSourceName(DraftSource), *FighterId, *Board.CellLabel(X, Y),
                                 DraftStatusName(Candidate.Status), Candidate.RequiredBoost));
  return true;
}

void FS09CommandUi::CarryPreDraft(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters) {
  const FS09PreDraft Carried = PreDraft;
  ClearPreDraft();
  const ES09InputSource Previous = DraftSource;
  DraftSource = Carried.Source;
  FS09Reason Gate;
  if (CanMoveFighter(Carried.FighterId, Fighters, Gate)) SelectedFighterId = Carried.FighterId;
  FS09DraftMove Candidate;
  FS09Reason Why;
  if (!SelectedFighterId.IsEmpty() &&
      EvaluateDestination(Carried.FighterId, Carried.X, Carried.Y, Board, Fighters, Candidate, Why) &&
      Candidate.Path.Num() > 0) {
    // By the NEW hand: Ok or NeedBoost (MS-R-02).
    PushUndo(Moves, BoostCardId);
    FS09DraftMove& Move = Moves.AddDefaulted_GetRef();
    Move.FighterId = Carried.FighterId;
    Move.DestX = Carried.X;
    Move.DestY = Carried.Y;
    ReevaluateDraft(Board, Fighters);
    TraceDraftOp(TEXT("assign"), Carried.FighterId, Board);
  } else {
    // No path even with the best BOOST of the new hand.
    LastReason = FS09Reason::Make(TEXT("why.predraft.lost")).Arg(TEXT("cell"), Board.CellLabel(Carried.X, Carried.Y));
    RefreshSelectedTiers(Board, Fighters);
    DraftTraceLine(FString::Printf(TEXT("MS-DRAFT op=predraft.lost rev=%u src=%s fighter=%s dest=%s"), DraftRevision,
                                   S09DraftSourceName(DraftSource), *Carried.FighterId,
                                   *Board.CellLabel(Carried.X, Carried.Y)));
  }
  DraftSource = Previous;
}

bool FS09CommandUi::CanKeepPreDraft(const FS08Snapshot& Snapshot) const {
  if (Snapshot.CurrentTurnPlayerId != ViewerId) return false;
  if (Snapshot.Phase != TEXT("ACTION_MANEUVER") && Snapshot.Phase != TEXT("ACTION_ATTACK")) return false;
  const TSharedPtr<FJsonObject> Meta = Snapshot.Metadata.IsValid() ? Snapshot.Metadata->AsObject() : nullptr;
  double Actions = 1.0;
  return !(Meta.IsValid() && Meta->TryGetNumberField(TEXT("actionsRemaining"), Actions) && Actions <= 0.0);
}

TArray<FString> FS09CommandUi::MovableFighterIds(const TArray<FS08BoardFighter>& Fighters) const {
  TArray<FString> Ids;
  for (const FS08BoardFighter& Fighter : Fighters) {
    FS09Reason Why;
    if (SameDraftId(Fighter.OwnerId, ViewerId) && CanMoveFighter(Fighter.Id, Fighters, Why)) Ids.Add(Fighter.Id);
  }
  return Ids;
}

FString FS09CommandUi::CycleFighter(const TArray<FS08BoardFighter>& Fighters, int32 Direction) const {
  const TArray<FString> Ids = MovableFighterIds(Fighters);
  if (Ids.Num() == 0) return FString();
  const int32 Current = Ids.IndexOfByPredicate([this](const FString& Id) { return SameDraftId(Id, SelectedFighterId); });
  if (Current == INDEX_NONE) return Direction >= 0 ? Ids[0] : Ids.Last();
  return Ids[(Current + (Direction >= 0 ? 1 : -1) + Ids.Num()) % Ids.Num()];
}

TArray<FString> FS09CommandUi::FadedFighters(const TArray<FS08BoardFighter>& Fighters) const {
  TArray<FString> Out;
  for (const FS09DraftMove& Leaving : Moves) {
    const FS08BoardFighter* Fighter = FindWorkFighter(Fighters, Leaving.FighterId);
    if (!Fighter) continue;
    for (const FS09DraftMove& Other : Moves) {
      if (!SameDraftId(Other.FighterId, Leaving.FighterId) && Other.DestX == Fighter->X && Other.DestY == Fighter->Y) {
        Out.AddUnique(Fighter->Id);
        break;
      }
    }
  }
  return Out;
}

int32 FS09CommandUi::OwnLivingFighters(const TArray<FS08BoardFighter>& Fighters) const {
  int32 Count = 0;
  for (const FS08BoardFighter& Fighter : Fighters) {
    Count += SameDraftId(Fighter.OwnerId, ViewerId) && Fighter.Health > 0 && Fighter.X >= 0 ? 1 : 0;
  }
  return Count;
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
  LastReason.Reset();
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
  // locally with an actionable reason (MS-E-36).
  TSet<uint64> Used;
  for (const FS09DraftMove& Move : Moves) {
    const uint64 Key = FS08BoardModel::CellKey(Move.DestX, Move.DestY);
    if (Used.Contains(Key)) {
      LastReason = FS09Reason::Make(TEXT("why.cell.ally")).Arg(TEXT("cell"), Board.CellLabel(Move.DestX, Move.DestY));
      OutReason = FString::Printf(
          TEXT("two drafted moves end on the same cell (%d,%d)"), Move.DestX, Move.DestY);
      return false;
    }
    Used.Add(Key);
  }
  for (const FS09DraftMove& Move : Moves) {
    if (!FindOwnFighter(Fighters, Move.FighterId)) {
      OutReason = TEXT("drafted fighter is no longer selectable");
      return false;
    }
  }
  // MS-T-05: a fresh sequential evaluation on the confirm-time state; every
  // move must be Ok (MS-R-16) - NeedBoost and Conflict block with a reason.
  DraftHand = FS09DraftEval::BoostHand(Snapshot, ViewerId);
  ReevaluateDraft(Board, Fighters);
  for (const FS09DraftMove& Move : Moves) {
    if (Move.Status == ES09DraftMoveStatus::Ok) continue;
    LastReason = Move.Reason;
    OutReason = FString::Printf(TEXT("move %d (%s) %s: %s"), Move.Order + 1, *Move.FighterId,
                                Move.Status == ES09DraftMoveStatus::NeedBoost ? TEXT("needs a bigger boost")
                                                                               : TEXT("is in conflict"),
                                *Move.Reason.Describe());
    return false;
  }
  OutCommand.ManeuverId = PendingManeuverId;
  OutCommand.BoostCardId = BoostCardId;
  for (const FS09DraftMove& Move : Moves) {
    // MS-R-44 (B-01): "stay" is no entry in moves[] (the server would reject
    // the whole maneuver with EMPTY_PATH).
    if (Move.Path.IsEmpty()) continue;
    FS08ManeuverMove Out;
    Out.FighterId = Move.FighterId;
    Out.Path = Move.Path; // canonical path (04 §3.1)
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

bool FS09CommandUi::HasLegalDefenseCard(const FS08Snapshot& Snapshot,
                                        const TArray<FS08BoardFighter>& Fighters) const {
  const FS08BoardFighter* Defender = FindFighter(Fighters, Combat.TargetFighterId);
  const FString FighterName = Defender ? Defender->Name : FString();
  const TArray<const TCHAR*> Types = {TEXT("DEFENSE"), TEXT("VERSATILE"), TEXT("UNIVERSAL")};
  return LegalCardsFor(Snapshot, ViewerId, Types, FighterName).Num() > 0;
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
    // needs a living one (server: 'Боец не найден или повержен' -
    // isLivingFighter, so isDefeated with health > 0 is NOT movable by an
    // effect: MS-T-04, the IsAliveBlocker role).
    const bool bLiving = Fighter.IsAliveBlocker() && Fighter.X >= 0 && Fighter.Y >= 0;
    if (!bLiving && !(Type == TEXT("PLACE") && PendingChoice.bRestoreFullHealth)) {
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
  // 04 §3.3 (MS-T-04): the canonical reach of the model - living enemies of
  // the moved fighter's owner (IsAliveBlocker) block unless the effect passes
  // through them; allies and defeated fighters never block.
  TSet<uint64> Out;
  FS08ReachOptions Options;
  Options.bPassThroughEnemies = bPassThroughEnemies;
  const FS08ReachMap Reach = FS08BoardModel::ComputeReachMap(Board, Fighters, Mover.Id, Allowance, Options);
  if (!Reach.bValid) return Out;
  // The mover's own cell stays legal (zero-step resolve of an "up to N" move);
  // every other cell must be free of another living fighter.
  Out.Add(FS08BoardModel::CellKey(Reach.Start.X, Reach.Start.Y));
  for (const FIntPoint& Cell : FS08BoardModel::ReachEndpoints(Board, Fighters, Reach, Allowance)) {
    Out.Add(FS08BoardModel::CellKey(Cell.X, Cell.Y));
  }
  return Out;
}

TSet<uint64> FS09CommandUi::ComputePendingCells(const FS08Snapshot& Snapshot,
                                                const FS08BoardModel& Board,
                                                const TArray<FS08BoardFighter>& Fighters) const {
  (void)Snapshot;
  const FString& Type = PendingChoice.Type;
  if (Type == TEXT("MOVE") || Type == TEXT("PLACE")) return PendingCellsFor(PendingFighterId, Board, Fighters);
  TSet<uint64> Out;
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

bool FS09CommandUi::IsPendingMovePlace() const {
  return Mode == ES09CommandMode::PendingChoice && bHasPendingChoice && PendingChoice.PlayerId == ViewerId &&
         (PendingChoice.Type == TEXT("MOVE") || PendingChoice.Type == TEXT("PLACE"));
}

FS09PendingMovePrompt FS09CommandUi::DescribePendingMovePlace(const FS08BoardModel& Board,
                                                              const TArray<FS08BoardFighter>& Fighters) const {
  FS09PendingMovePrompt Out;
  if (!IsPendingMovePlace()) return Out;
  Out.bValid = true;
  Out.bPlace = PendingChoice.Type == TEXT("PLACE");
  Out.bCanDecline = PendingChoice.bOptional;
  Out.Allowance = PendingChoice.bHasValue ? PendingChoice.Value : 1; // MS-E-57 / MS-E-76
  TArray<FString> Legal;
  PendingLegalFighters(Fighters, Legal);
  Out.LegalFighters = Legal.Num();
  Out.FighterId = !PendingFighterId.IsEmpty() ? PendingFighterId : (Legal.Num() == 1 ? Legal[0] : FString());
  auto LabelOf = [](const FS08BoardFighter& F) { return F.Label.IsEmpty() ? F.Name : F.Label; };
  // MS-E-61: no legal fighter, or (PLACE) no legal fighter has a free space.
  bool bAnySpace = false;
  for (const FString& Id : Legal) {
    if (PendingCellsFor(Id, Board, Fighters).Num() > 0) {
      bAnySpace = true;
      break;
    }
  }
  Out.bNoSpace = !bAnySpace;
  if (const FS08BoardFighter* Fighter = FindFighter(Fighters, Out.FighterId)) {
    Out.FighterLabel = LabelOf(*Fighter);
    Out.bEnemyFighter = Fighter->OwnerId != ViewerId;
    Out.bImmobilized = !Out.bPlace && FS09DraftEval::IsImmobilized(*Fighter);
    const TSet<uint64> Cells = PendingCellsFor(Fighter->Id, Board, Fighters);
    const bool bOwnSpace = Fighter->X >= 0 && Fighter->Y >= 0 &&
                           Cells.Contains(FS08BoardModel::CellKey(Fighter->X, Fighter->Y));
    Out.Targets = Cells.Num() - (bOwnSpace ? 1 : 0);
    Out.bCanStay = !Out.bPlace && bOwnSpace;
  } else {
    // several legal fighters, none picked yet: name them all (max 3)
    TArray<FString> Names;
    for (const FString& Id : Legal) {
      if (const FS08BoardFighter* F = FindFighter(Fighters, Id)) Names.Add(LabelOf(*F));
      if (Names.Num() == 3) break;
    }
    Out.FighterLabel = FString::Join(Names, TEXT(" / "));
  }
  if (Out.bNoSpace) {
    Out.Prompt = FS09Reason::Make(TEXT("ms.place.no.space"));
  } else if (Out.bPlace) {
    Out.Prompt = FS09Reason::Make(TEXT("ms.pending.place")).Arg(TEXT("fighterName"), Out.FighterLabel);
  } else if (Out.bEnemyFighter) {
    Out.Prompt = FS09Reason::Make(TEXT("ms.pending.move.enemy")).Arg(TEXT("fighterName"), Out.FighterLabel);
  } else {
    Out.Prompt = FS09Reason::Make(TEXT("ms.pending.move"))
                     .Arg(TEXT("fighterName"), Out.FighterLabel)
                     .Arg(TEXT("n"), Out.Allowance);
  }
  return Out;
}

bool FS09CommandUi::StayPendingInPlace(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters,
                                       FS09Reason& OutWhy) {
  OutWhy.Reset();
  if (!IsPendingMovePlace() || PendingChoice.Type != TEXT("MOVE")) {
    OutWhy = FS09Reason::Make(TEXT("why.state.changed"));
    return false;
  }
  if (bCommandInFlight) {
    OutWhy = FS09Reason::Make(TEXT("why.syncing"));
    return false;
  }
  if (PendingFighterId.IsEmpty()) {
    TArray<FString> Legal;
    if (!PendingLegalFighters(Fighters, Legal) || Legal.Num() != 1) {
      OutWhy = FS09Reason::Make(TEXT("ms.choice.object"));
      return false;
    }
    PendingFighterId = Legal[0];
  }
  const FS08BoardFighter* Mover = FindFighter(Fighters, PendingFighterId);
  const TSet<uint64> Cells = PendingCellsFor(PendingFighterId, Board, Fighters);
  if (!Mover || Mover->X < 0 || Mover->Y < 0 || !Cells.Contains(FS08BoardModel::CellKey(Mover->X, Mover->Y))) {
    OutWhy = FS09Reason::Make(TEXT("why.state.changed"));
    return false;
  }
  PendingCells = Cells;
  PendingCellX = Mover->X;
  PendingCellY = Mover->Y;
  bPendingCellSet = true;
  return true;
}

FS09Reason FS09CommandUi::PendingCellReason(int32 X, int32 Y, const FS08BoardModel& Board,
                                            const TArray<FS08BoardFighter>& Fighters) const {
  if (!IsPendingMovePlace() || PendingFighterId.IsEmpty()) return FS09Reason();
  if (PendingCellsFor(PendingFighterId, Board, Fighters).Contains(FS08BoardModel::CellKey(X, Y))) return FS09Reason();
  const FString Cell = Board.CellLabel(X, Y);
  auto Make = [&Cell](const TCHAR* Key) { return FS09Reason::Make(Key).Arg(TEXT("cell"), Cell); };
  const FS08Cell* Terrain = Board.CellAt(X, Y);
  if (!Board.IsBoardSpace(X, Y) || !Terrain || !Terrain->IsPassable()) return Make(TEXT("why.cell.not.space"));
  const FS08BoardFighter* Mover = FindFighter(Fighters, PendingFighterId);
  if (!Mover) return FS09Reason::Make(TEXT("why.client.desync"));
  const FS08BoardFighter* Occupant = FS08BoardModel::FighterAt(Fighters, X, Y, Mover->Id);
  if (PendingChoice.Type == TEXT("PLACE")) {
    if (Occupant) return Make(TEXT("why.cell.occupied"));
    if (!PendingChoice.ZoneFighterName.IsEmpty() &&
        !CellSharesZoneWith(Board, Fighters, PendingChoice.ZoneFighterName, X, Y)) {
      return Make(TEXT("why.place.zone")).Arg(TEXT("fighterName"), PendingChoice.ZoneFighterName);
    }
    return Make(TEXT("why.cell.not.space"));
  }
  // MOVE: the occupant first (an endpoint is never taken), then the path.
  if (Occupant) return Make(Occupant->OwnerId != Mover->OwnerId ? TEXT("why.cell.enemy") : TEXT("why.cell.ally"));
  FS08ReachOptions Options;
  Options.bPassThroughEnemies = PendingChoice.bCanPassThroughEnemies;
  const FS08ReachMap Unlimited = FS08BoardModel::ComputeReachMap(Board, Fighters, Mover->Id, MAX_int32, Options);
  const int32 Need = Unlimited.DistanceTo(FIntPoint(X, Y));
  const int32 Have = PendingChoice.bHasValue ? PendingChoice.Value : 1;
  if (Need != INDEX_NONE && Need > Have) {
    return Make(TEXT("why.cell.unreachable")).Arg(TEXT("need"), Need).Arg(TEXT("have"), Have);
  }
  if (Need == INDEX_NONE && !Options.bPassThroughEnemies) {
    FS08ReachOptions Through;
    Through.bPassThroughEnemies = true;
    if (FS08BoardModel::ComputeReachMap(Board, Fighters, Mover->Id, MAX_int32, Through).Reaches(FIntPoint(X, Y))) {
      return Make(TEXT("why.cell.enemy.path"));
    }
  }
  return Make(TEXT("why.cell.no.path"));
}

void FS09CommandUi::TracePendingMovePlace(const FS08BoardModel& Board, const TArray<FS08BoardFighter>& Fighters) {
  const FS09PendingMovePrompt Prompt = DescribePendingMovePlace(Board, Fighters);
  if (!Prompt.bValid) return;
  const FString Key = PendingHeadKey() + TEXT("|") + Prompt.FighterId;
  if (Key == PendingTracedKey) return;
  PendingTracedKey = Key;
  DraftTraceLine(FString::Printf(
      TEXT("MS-PENDING open id=%s type=%s value=%s optional=%d fighter=%s owner=%s legal=%d targets=%d stay=%d ")
      TEXT("decline=%d"),
      *PendingChoice.Id, *PendingChoice.Type,
      PendingChoice.bHasValue ? *FString::FromInt(PendingChoice.Value) : TEXT("absent(1)"),
      PendingChoice.bOptional ? 1 : 0, Prompt.FighterId.IsEmpty() ? TEXT("-") : *Prompt.FighterId,
      Prompt.FighterId.IsEmpty() ? TEXT("-") : (Prompt.bEnemyFighter ? TEXT("opponent") : TEXT("own")),
      Prompt.LegalFighters, Prompt.Targets, Prompt.bCanStay ? 1 : 0, Prompt.bCanDecline ? 1 : 0));
  if (Prompt.bNoSpace) {
    // MS-E-61: the server neither resolves nor refuses (R1-D07); since DE-016
    // it should not open such a head at all - a line here is a server gap.
    DraftTraceLine(FString::Printf(TEXT("MS-REJECT place.no.space id=%s type=%s legal=%d"), *PendingChoice.Id,
                                   *PendingChoice.Type, Prompt.LegalFighters));
  }
  if (Prompt.bImmobilized) {
    // MS-E-63: allowed as the server allows it (R1-D02); the rule is open until MS-T-19.
    DraftTraceLine(FString::Printf(TEXT("MS-DATA pending.move.immobilized fighter=%s id=%s (allowed; rule open, MS-T-19)"),
                                   *Prompt.FighterId, *PendingChoice.Id));
  }
}

TSet<uint64> FS09CommandUi::PendingCellsFor(const FString& FighterId, const FS08BoardModel& Board,
                                            const TArray<FS08BoardFighter>& Fighters) const {
  TSet<uint64> Out;
  const FString& Type = PendingChoice.Type;
  if (Type == TEXT("MOVE") || Type == TEXT("PLACE")) {
    for (const FS08BoardFighter& Fighter : Fighters) {
      if (FighterId.IsEmpty() || Fighter.Id != FighterId) continue;
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
    // B-04: the space by CellLabel; MOVE / PLACE name the exact why.* (MS-T-12).
    const FS09Reason Why = PendingCellReason(X, Y, Board, Fighters);
    OutReason = Why.IsSet() ? Why.Describe()
                            : FString::Printf(TEXT("space %s is not legal for this choice"), *Board.CellLabel(X, Y));
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

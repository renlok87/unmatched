#include "S09OpponentView.h"

#include "../S08/S08WhyText.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"

namespace {
bool ReadXY(const TSharedPtr<FJsonValue>& Value, FIntPoint& Out) {
  const TSharedPtr<FJsonObject>* Object = nullptr;
  if (!Value.IsValid() || !Value->TryGetObject(Object) || !Object || !Object->IsValid()) return false;
  bool bX = false, bY = false;
  int32 X = -1, Y = -1;
  if (!FS08Contracts::ReadIntLike(Object->ToSharedRef(), TEXT("x"), X, bX) || !bX) return false;
  if (!FS08Contracts::ReadIntLike(Object->ToSharedRef(), TEXT("y"), Y, bY) || !bY) return false;
  Out = FIntPoint(X, Y);
  return true;
}

/** Template of Key with {name} replaced by Args (an empty value stays empty - the boost part of a maneuver without
 *  a boost; S08WhyText::En renders an empty argument as "?"). */
FString Fill(const TCHAR* Key, const TMap<FString, FString>& Args) {
  FString Out = S08WhyText::Template(FName(Key));
  if (Out.IsEmpty()) return FString(Key);
  for (const TPair<FString, FString>& Arg : Args) {
    Out.ReplaceInline(*FString::Printf(TEXT("{%s}"), *Arg.Key), *Arg.Value, ESearchCase::CaseSensitive);
  }
  return Out;
}
}  // namespace

// ---------------------------------------------------------------------------------------------------- trail

bool FS09LastMovement::Read(const TSharedPtr<FJsonValue>& Metadata, FS09LastMovement& Out) {
  Out = FS09LastMovement();
  const TSharedPtr<FJsonObject> Meta = Metadata.IsValid() && Metadata->Type == EJson::Object ? Metadata->AsObject() : nullptr;
  if (!Meta.IsValid()) return false;
  const TSharedPtr<FJsonValue> Value = Meta->TryGetField(TEXT("lastMovement"));
  const TSharedPtr<FJsonObject>* Trail = nullptr;
  if (!Value.IsValid() || !Value->TryGetObject(Trail) || !Trail || !Trail->IsValid()) return false;
  bool bSeq = false;
  if (!FS08Contracts::ReadIntLike(Trail->ToSharedRef(), TEXT("seq"), Out.Seq, bSeq) || !bSeq) return false;
  if (!(*Trail)->TryGetStringField(TEXT("playerId"), Out.PlayerId) || Out.PlayerId.IsEmpty()) return false;
  (*Trail)->TryGetStringField(TEXT("source"), Out.Source);
  (*Trail)->TryGetStringField(TEXT("sourceRef"), Out.SourceRef);
  const TSharedPtr<FJsonObject>* Boost = nullptr;
  if ((*Trail)->TryGetObjectField(TEXT("boost"), Boost) && Boost && Boost->IsValid()) {
    Out.bBoost = true;
    (*Boost)->TryGetStringField(TEXT("name"), Out.BoostName);
    bool bValue = false;
    FS08Contracts::ReadIntLike(Boost->ToSharedRef(), TEXT("value"), Out.BoostValue, bValue);
    if (!bValue) Out.BoostValue = 0;
  }
  const TArray<TSharedPtr<FJsonValue>>* Moves = nullptr;
  if ((*Trail)->TryGetArrayField(TEXT("moves"), Moves) && Moves) {
    for (const TSharedPtr<FJsonValue>& MoveValue : *Moves) {
      const TSharedPtr<FJsonObject>* Move = nullptr;
      if (!MoveValue.IsValid() || !MoveValue->TryGetObject(Move) || !Move || !Move->IsValid()) continue;
      FMove Entry;
      if (!(*Move)->TryGetStringField(TEXT("fighterId"), Entry.FighterId) || Entry.FighterId.IsEmpty()) continue;
      FString Kind;
      Entry.bPlace = (*Move)->TryGetStringField(TEXT("kind"), Kind) && Kind == TEXT("PLACE");
      if (!ReadXY((*Move)->TryGetField(TEXT("from")), Entry.From)) continue;
      const TArray<TSharedPtr<FJsonValue>>* Path = nullptr;
      if (!(*Move)->TryGetArrayField(TEXT("path"), Path) || !Path || Path->Num() == 0) continue;
      bool bPath = true;
      for (const TSharedPtr<FJsonValue>& Step : *Path) {
        FIntPoint Cell;
        if (!ReadXY(Step, Cell)) {
          bPath = false;
          break;
        }
        Entry.Path.Add(Cell);
      }
      if (!bPath || (Entry.bPlace && Entry.Path.Num() != 1)) continue;
      Out.Moves.Add(MoveTemp(Entry));
    }
  }
  Out.bValid = true;
  return true;
}

// ---------------------------------------------------------------------------------------------------- stamp

FS09BoardStamp FS09BoardStamp::Make(const TArray<FS08BoardFighter>& Fighters, const FString& TurnPlayerId) {
  FS09BoardStamp Stamp;
  Stamp.bSet = true;
  Stamp.TurnPlayerId = TurnPlayerId;
  for (const FS08BoardFighter& F : Fighters) Stamp.Fighters.Add(F.Id, FIntVector(F.X, F.Y, F.Health));
  return Stamp;
}

bool FS09BoardStamp::Differs(const FS09BoardStamp& Other) const {
  if (TurnPlayerId != Other.TurnPlayerId || Fighters.Num() != Other.Fighters.Num()) return true;
  for (const TPair<FString, FIntVector>& Pair : Fighters) {
    const FIntVector* Was = Other.Fighters.Find(Pair.Key);
    if (!Was || *Was != Pair.Value) return true;
  }
  return false;
}

// ---------------------------------------------------------------------------------------------------- tracker

const TCHAR* FS09LastMoveTracker::StateName(ES09LastMoveState InState) {
  switch (InState) {
    case ES09LastMoveState::Waiting: return TEXT("waiting");
    case ES09LastMoveState::Shown: return TEXT("shown");
    case ES09LastMoveState::Fading: return TEXT("fading");
    default: return TEXT("none");
  }
}

TArray<FString> FS09LastMoveTracker::OnApplied(int32 Seq, const FS09LastMovement& InTrail, const FS09BoardStamp& Stamp,
                                               double NowMs, bool bReducedMotion) {
  TArray<FString> Lines;
  bReduced = bReducedMotion;  // VS-6 FX-14: the hold fade of Tick follows the same setting
  // MS-P-03 - the one exit rule: the first applied seq > lastMovement.seq in which positions, the HP of any fighter or
  // currentTurnPlayerId changed. A beginManeuver (seq + 1, a card drawn) changes none of them (MS-E-103).
  const bool bActive = State == ES09LastMoveState::Waiting || State == ES09LastMoveState::Shown;
  if (bActive && Seq > Trail.Seq && PrevStamp.bSet && Stamp.Differs(PrevStamp)) {
    if (bReducedMotion || State == ES09LastMoveState::Waiting) {
      State = ES09LastMoveState::None;
      Lines.Add(FString::Printf(TEXT("MS-LAST off seq=%d at=%d fade=0"), Trail.Seq, Seq));
    } else {
      State = ES09LastMoveState::Fading;
      FadeStartMs = NowMs;
      Lines.Add(FString::Printf(TEXT("MS-LAST fade seq=%d at=%d ms=%d"), Trail.Seq, Seq, FMath::RoundToInt(FadeMs)));
    }
    ++Revision;
  }
  // a trail of exactly this seq enters once (a same-seq merge does not restart it); it replaces a fading one - the
  // alpha is one value for every last-move outline, and the board is changing under the new move anyway
  if (InTrail.bValid && InTrail.Seq == Seq && InTrail.Seq != EnteredSeq) {
    if (State == ES09LastMoveState::Fading || State == ES09LastMoveState::Shown) {
      Lines.Add(FString::Printf(TEXT("MS-LAST replace seq=%d by=%d"), Trail.Seq, InTrail.Seq));
    }
    Trail = InTrail;
    EnteredSeq = InTrail.Seq;
    State = ES09LastMoveState::Waiting;
    bAwaitAnimation = false;
    RevealAtMs = NowMs;
    bRestored = false;
    ++Revision;
    Lines.Add(FString::Printf(TEXT("MS-LAST enter seq=%d player=%s source=%s moves=%d boost=%d"), InTrail.Seq,
                              *InTrail.PlayerId, InTrail.Source.IsEmpty() ? TEXT("-") : *InTrail.Source,
                              InTrail.Moves.Num(), InTrail.bBoost ? InTrail.BoostValue : -1));
  }
  PrevStamp = Stamp;
  return Lines;
}

void FS09LastMoveTracker::OnMoveAnimation(int32 Seq, double EndMs) {
  if (State != ES09LastMoveState::Waiting || Seq != Trail.Seq) return;
  bAwaitAnimation = true;
  RevealAtMs = FMath::Max(RevealAtMs, EndMs);
}

TArray<FString> FS09LastMoveTracker::Tick(double NowMs, bool bAnyFigureMoving) {
  TArray<FString> Lines;
  if (State == ES09LastMoveState::Waiting &&
      (!bAwaitAnimation || !bAnyFigureMoving || NowMs >= RevealAtMs)) {
    State = ES09LastMoveState::Shown;
    ShownAtMs = NowMs;  // VS-6 FX-14: the appear and the hold count from the reveal
    bRestored = !bAwaitAnimation;
    bRevealedUnconsumed = true;
    ++Revision;
    TArray<FString> From, To;
    for (const FS09LastMovement::FMove& Move : Trail.Moves) {
      From.Add(FString::Printf(TEXT("%d,%d"), Move.From.X, Move.From.Y));
      To.Add(FString::Printf(TEXT("%d,%d"), Move.Dest().X, Move.Dest().Y));
    }
    Lines.Add(FString::Printf(TEXT("MS-LAST show seq=%d mode=%s player=%s from=%s to=%s"), Trail.Seq,
                              bRestored ? TEXT("restore") : TEXT("anim"), *Trail.PlayerId,
                              From.Num() ? *FString::Join(From, TEXT(">")) : TEXT("-"),
                              To.Num() ? *FString::Join(To, TEXT(">")) : TEXT("-")));
  }
  // VS-6 FX-14 (ВР-29): the path holds HoldMs after its reveal, then fades (reduced motion: off at once)
  if (State == ES09LastMoveState::Shown && HoldMs > 0.0 && NowMs - ShownAtMs >= InMs + HoldMs) {
    ++Revision;
    if (bReduced) {
      State = ES09LastMoveState::None;
      Lines.Add(FString::Printf(TEXT("MS-LAST off seq=%d at=hold fade=0"), Trail.Seq));
    } else {
      State = ES09LastMoveState::Fading;
      FadeStartMs = NowMs;
      Lines.Add(FString::Printf(TEXT("MS-LAST fade seq=%d at=hold ms=%d"), Trail.Seq, FMath::RoundToInt(FadeMs)));
    }
  }
  if (State == ES09LastMoveState::Fading && NowMs - FadeStartMs >= FadeMs) {
    State = ES09LastMoveState::None;
    ++Revision;
    Lines.Add(FString::Printf(TEXT("MS-LAST off seq=%d fade=%d"), Trail.Seq, FMath::RoundToInt(FadeMs)));
  }
  return Lines;
}

float FS09LastMoveTracker::Alpha(double NowMs) const {
  switch (State) {
    case ES09LastMoveState::Shown:
      // VS-6 FX-14: the appear over InMs (0 = at once; reduced motion: at once)
      return InMs > 0.0 && !bReduced ? FMath::Clamp(static_cast<float>((NowMs - ShownAtMs) / InMs), 0.0f, 1.0f) : 1.0f;
    case ES09LastMoveState::Fading:
      return FMath::Clamp(1.0f - static_cast<float>((NowMs - FadeStartMs) / FadeMs), 0.0f, 1.0f);
    default: return 0.0f;
  }
}

bool FS09LastMoveTracker::ConsumeRevealed(FS09LastMovement& Out) {
  if (!bRevealedUnconsumed) return false;
  bRevealedUnconsumed = false;
  Out = Trail;
  return true;
}

void FS09LastMoveTracker::Reset() {
  const uint32 Rev = Revision + 1;
  const double Hold = HoldMs, In = InMs;  // VS-6 FX-14: the settings survive a reset
  *this = FS09LastMoveTracker();
  Revision = Rev;
  HoldMs = Hold;
  InMs = In;
}

// ---------------------------------------------------------------------------------------------------- feed

namespace {
/** The ms.log.move list of a trail: Full = every move, Inline = at most MaxInline moves (the first MaxInline - 1 +
 *  "and N more" beyond it, MS-E-106); no movement -> ms.log.stay. Returns true when Inline is cut. */
bool MoveLists(const FS09LastMovement& Trail, const FS09EventFeed::FNameOf& FighterName,
               const FS09EventFeed::FCellName& CellName, int32 MaxInline, FString& Inline, FString& Full) {
  TArray<FString> Moves;
  for (const FS09LastMovement::FMove& Move : Trail.Moves) {
    Moves.Add(Fill(TEXT("ms.log.move"), {{TEXT("fighterName"), FighterName(Move.FighterId)},
                                        {TEXT("from"), CellName(Move.From)},
                                        {TEXT("to"), CellName(Move.Dest())}}));
  }
  if (Moves.Num() == 0) {
    Inline = Full = S08WhyText::En(FName(TEXT("ms.log.stay")));
    return false;
  }
  Full = FString::Join(Moves, TEXT(", "));
  if (Moves.Num() <= MaxInline) {
    Inline = Full;
    return false;
  }
  // MS-E-106: the first two moves + "and N more" keep the line within two visual lines at 150 %
  const int32 Shown = MaxInline - 1;
  TArray<FString> Head(Moves.GetData(), Shown);
  Head.Add(S08WhyText::En(FName(TEXT("ms.log.more")), {{TEXT("n"), FString::FromInt(Moves.Num() - Shown)}}));
  Inline = FString::Join(Head, TEXT(", "));
  return true;
}
}  // namespace

FS09FeedEntry FS09EventFeed::Describe(const FS09LastMovement& Trail, const FNameOf& PlayerName,
                                      const FNameOf& FighterName, const FCellName& CellName) {
  FS09FeedEntry Entry;
  Entry.Seq = Trail.Seq;
  Entry.Moves = Trail.Moves.Num();
  FString Inline;
  FString Full;
  Entry.bTruncated = MoveLists(Trail, FighterName, CellName, MaxInlineMoves, Inline, Full);
  const FString BoostPart =
      Trail.bBoost ? Fill(TEXT("ms.log.boost.part"),
                          {{TEXT("n"), FString::FromInt(Trail.BoostValue)},
                           {TEXT("cardName"), Trail.BoostName.IsEmpty() ? FString(TEXT("?")) : Trail.BoostName}})
                   : FString();
  const FString Player = PlayerName(Trail.PlayerId);
  Entry.Text = Fill(TEXT("ms.log.maneuver"), {{TEXT("player"), Player}, {TEXT("boostPart"), BoostPart}, {TEXT("moves"), Inline}});
  Entry.Full = Fill(TEXT("ms.log.maneuver"), {{TEXT("player"), Player}, {TEXT("boostPart"), BoostPart}, {TEXT("moves"), Full}});
  return Entry;
}

bool FS09EventFeed::Add(const FS09LastMovement& Trail, const FNameOf& PlayerName, const FNameOf& FighterName,
                        const FCellName& CellName) {
  if (!Trail.bValid || Trail.Source != TEXT("MANEUVER") || Seen.Contains(Trail.Seq)) return false;
  Seen.Add(Trail.Seq);
  Lines.Add(Describe(Trail, PlayerName, FighterName, CellName));
  while (Lines.Num() > MaxLines) Lines.RemoveAt(0);
  ++Revision;
  return true;
}

FS09FeedEntry FS09EventFeed::DescribeEffect(const FS09LastMovement& Trail, const FString& CardName,
                                            const TArray<FString>& YourFighters, const FNameOf& PlayerName,
                                            const FNameOf& FighterName, const FCellName& CellName) {
  FS09FeedEntry Entry;
  Entry.Seq = Trail.Seq;
  Entry.Moves = Trail.Moves.Num();
  const FString Card = CardName.IsEmpty() ? FString(TEXT("?")) : CardName;
  if (YourFighters.Num() > 0) {
    // 03 §7 п. 3: the opponent's effect moved MY fighter - "Your fighter Merlin: Feint effect" (one per fighter)
    TArray<FString> Parts;
    for (const FString& Id : YourFighters) {
      Parts.Add(Fill(TEXT("ms.opp.moves.yours"), {{TEXT("fighterName"), FighterName(Id)}, {TEXT("cardName"), Card}}));
    }
    Entry.Text = Entry.Full = FString::Join(Parts, TEXT("; "));
    return Entry;
  }
  FString Inline;
  FString Full;
  Entry.bTruncated = MoveLists(Trail, FighterName, CellName, MaxInlineMoves, Inline, Full);
  const FString Player = PlayerName(Trail.PlayerId);
  Entry.Text = Fill(TEXT("ms.log.effect"), {{TEXT("player"), Player}, {TEXT("cardName"), Card}, {TEXT("moves"), Inline}});
  Entry.Full = Fill(TEXT("ms.log.effect"), {{TEXT("player"), Player}, {TEXT("cardName"), Card}, {TEXT("moves"), Full}});
  return Entry;
}

bool FS09EventFeed::AddEffect(const FS09LastMovement& Trail, const FString& CardName,
                              const TArray<FString>& YourFighters, const FNameOf& PlayerName,
                              const FNameOf& FighterName, const FCellName& CellName) {
  if (!Trail.bValid || Trail.Source != TEXT("EFFECT") || Seen.Contains(Trail.Seq)) return false;
  Seen.Add(Trail.Seq);
  Lines.Add(DescribeEffect(Trail, CardName, YourFighters, PlayerName, FighterName, CellName));
  while (Lines.Num() > MaxLines) Lines.RemoveAt(0);
  ++Revision;
  return true;
}

void FS09EventFeed::Reset() {
  Lines.Reset();
  Seen.Reset();
  ++Revision;
}

// ---------------------------------------------------------------------------------------------------- DE-022

FString FS09ActionTracker::OnApplied(int32 Seq, const FString& TurnPlayerId, int32 TurnCount, int32 ActionsRemaining,
                                     const FString& ViewerId, double NowMs, FName SpentAs) {
  const bool bWasOpponentTurn = bOpponentTurn;
  const FString Key = FString::Printf(TEXT("%s#%d"), *TurnPlayerId, TurnCount);
  if (Key != TurnKey) {
    // a new turn (or the first snapshot seen): every slot free, then the marks this snapshot already carries (a
    // reconnect mid-turn sees 2 - actionsRemaining spent)
    TurnKey = Key;
    TurnSlots = FSlots();
    SpentTypes.Reset();
    LastRemaining = -1;
    if (ActionsRemaining >= 0) {
      TurnSlots.Spent = FMath::Clamp(PerTurn - ActionsRemaining, 0, PerTurn);
      TurnSlots.Slots = FMath::Max(PerTurn, TurnSlots.Spent + ActionsRemaining);
      // a reconnect mid-turn: the earlier actions' types are not in the snapshot - the one it shows stands for them
      SpentTypes.Init(SpentAs, TurnSlots.Spent);
    }
  } else if (ActionsRemaining >= 0 && LastRemaining >= 0 && ActionsRemaining != LastRemaining) {
    if (ActionsRemaining < LastRemaining) {
      TurnSlots.Spent += LastRemaining - ActionsRemaining;  // an action chosen (beginManeuver / attack / scheme)
      while (SpentTypes.Num() < TurnSlots.Spent) SpentTypes.Add(SpentAs);
    }
    // a gained action (GAIN_ACTION, a hero ability) adds a slot; spent ones stay marked
    TurnSlots.Slots = FMath::Max(PerTurn, TurnSlots.Spent + ActionsRemaining);
  }
  if (ActionsRemaining >= 0) LastRemaining = ActionsRemaining;
  bOwnTurn = !ViewerId.IsEmpty() && TurnPlayerId == ViewerId;
  bOpponentTurn = !ViewerId.IsEmpty() && !TurnPlayerId.IsEmpty() && TurnPlayerId != ViewerId;
  if (bOpponentTurn && !bWasOpponentTurn) OpponentSinceMs = NowMs;

  const FSlots O = Own();
  const FSlots P = Opponent();
  const FString Trace = FString::Printf(TEXT("own=%d/%d opp=%d/%d oppVisible=%d"), O.Spent, O.Slots, P.Spent, P.Slots,
                                        bOpponentTurn ? 1 : 0);
  if (Trace == TraceKey) return FString();
  TraceKey = Trace;
  return FString::Printf(TEXT("MS-TRACK %s seq=%d"), *Trace, Seq);
}

float FS09ActionTracker::OpponentAlpha(double NowMs, bool bReducedMotion) const {
  if (!bOpponentTurn) return 0.0f;
  if (bReducedMotion) return 1.0f;
  return FMath::Clamp(static_cast<float>((NowMs - OpponentSinceMs) / AppearMs), 0.0f, 1.0f);
}

void FS09EffectSources::Note(const TArray<FS08PendingEffect>& Queue) {
  for (const FS08PendingEffect& Pending : Queue) {
    if (Pending.Id.IsEmpty() || Texts.Contains(Pending.Id)) continue;
    Texts.Add(Pending.Id, Pending.Text);
    Ids.Add(Pending.Id);
  }
  while (Ids.Num() > MaxKept) {
    Texts.Remove(Ids[0]);
    Ids.RemoveAt(0);
  }
}

FString FS09EffectSources::TextOf(const FString& PendingId) const {
  const FString* Text = Texts.Find(PendingId);
  return Text ? *Text : FString();
}

// ---------------------------------------------------------------------------------------------------- helpers

namespace S09OpponentView {

FString PendingManeuverPlayer(const FS08Snapshot& Snapshot) {
  const TSharedPtr<FJsonObject> Meta =
      Snapshot.Metadata.IsValid() && Snapshot.Metadata->Type == EJson::Object ? Snapshot.Metadata->AsObject() : nullptr;
  const TSharedPtr<FJsonObject>* Pending = nullptr;
  if (!Meta.IsValid() || !Meta->TryGetObjectField(TEXT("pendingManeuver"), Pending) || !Pending || !Pending->IsValid()) {
    return FString();
  }
  FString PlayerId;
  (*Pending)->TryGetStringField(TEXT("playerId"), PlayerId);
  return PlayerId;
}

FName SpentActionType(const FS08Snapshot& Snapshot) {
  if (!PendingManeuverPlayer(Snapshot).IsEmpty()) return FName(TEXT("maneuver"));
  FS09LastMovement Trail;
  if (FS09LastMovement::Read(Snapshot.Metadata, Trail) && Trail.Source == TEXT("MANEUVER") &&
      Trail.Seq == Snapshot.SequenceNumber) {
    return FName(TEXT("maneuver"));
  }
  const TSharedPtr<FJsonObject> Meta =
      Snapshot.Metadata.IsValid() && Snapshot.Metadata->Type == EJson::Object ? Snapshot.Metadata->AsObject() : nullptr;
  const TSharedPtr<FJsonObject>* Combat = nullptr;
  if (Snapshot.Phase.StartsWith(TEXT("COMBAT")) ||
      (Meta.IsValid() && Meta->TryGetObjectField(TEXT("combatInfo"), Combat) && Combat && Combat->IsValid())) {
    return FName(TEXT("attack"));
  }
  return FName(TEXT("scheme"));
}

bool OpponentPlanning(const FS08Snapshot& Snapshot, const FString& ViewerId) {
  const FString Player = PendingManeuverPlayer(Snapshot);
  return !Player.IsEmpty() && !ViewerId.IsEmpty() && Player != ViewerId;
}

float PlanningPulse(double Seconds, bool bReducedMotion) {
  if (bReducedMotion) return 1.0f;
  const double Wave = 0.5 + 0.5 * FMath::Cos(2.0 * UE_DOUBLE_PI * Seconds);  // 1 Hz, 1 at t = 0
  return static_cast<float>(0.45 + 0.55 * Wave);
}

FS08MoveDraftInput::FLastMove LastMoveInput(const FS09LastMovement& Trail, ES08PlateColor Color) {
  FS08MoveDraftInput::FLastMove Out;
  Out.Color = Color;
  for (const FS09LastMovement::FMove& Move : Trail.Moves) {
    Out.From.AddUnique(Move.From);
    Out.To.AddUnique(Move.Dest());
    // VS-6 FX-14: every move's cells with the start (PLACE: from -> to) for the dashed path
    TArray<FIntPoint> Cells;
    Cells.Add(Move.From);
    Cells.Append(Move.bPlace ? TArray<FIntPoint>{Move.Dest()} : Move.Path);
    Out.Paths.Add(MoveTemp(Cells));
    Out.Places.Add(Move.bPlace);
    if (Move.bPlace) continue;  // PLACE: a transfer without a path
    for (int32 I = 0; I + 1 < Move.Path.Num(); ++I) Out.Dots.AddUnique(Move.Path[I]);
  }
  return Out;
}

FEdgeArrow EdgeArrow(const FVector2D& Target, bool bProjected, const FVector2D& Viewport, float Margin) {
  FEdgeArrow Out;
  if (!bProjected || Viewport.X <= 2.0f * Margin || Viewport.Y <= 2.0f * Margin) return Out;
  if (Target.X >= Margin && Target.X <= Viewport.X - Margin && Target.Y >= Margin && Target.Y <= Viewport.Y - Margin) {
    return Out;
  }
  const FVector2D Centre = Viewport * 0.5f;
  const FVector2D D = Target - Centre;
  const double HalfW = Centre.X - Margin;
  const double HalfH = Centre.Y - Margin;
  const double Tx = FMath::Abs(D.X) > UE_KINDA_SMALL_NUMBER ? HalfW / FMath::Abs(D.X) : TNumericLimits<double>::Max();
  const double Ty = FMath::Abs(D.Y) > UE_KINDA_SMALL_NUMBER ? HalfH / FMath::Abs(D.Y) : TNumericLimits<double>::Max();
  const double T = FMath::Min(Tx, Ty);
  Out.bShow = true;
  Out.Pos = Centre + D * T;
  Out.AngleDeg = static_cast<float>(FMath::RadiansToDegrees(FMath::Atan2(D.Y, D.X)));
  return Out;
}

TArray<FS08PendingEffect> PendingQueue(const FS08Snapshot& Snapshot) {
  TArray<FS08PendingEffect> Out;
  const TSharedPtr<FJsonObject> Meta =
      Snapshot.Metadata.IsValid() && Snapshot.Metadata->Type == EJson::Object ? Snapshot.Metadata->AsObject() : nullptr;
  const TArray<TSharedPtr<FJsonValue>>* Queue = nullptr;
  if (!Meta.IsValid() || !Meta->TryGetArrayField(TEXT("pendingEffects"), Queue) || !Queue) return Out;
  for (const TSharedPtr<FJsonValue>& Value : *Queue) {
    const TSharedPtr<FJsonObject>* Entry = nullptr;
    if (!Value.IsValid() || !Value->TryGetObject(Entry) || !Entry || !Entry->IsValid()) continue;
    FS08PendingEffect Pending;
    (*Entry)->TryGetStringField(TEXT("id"), Pending.Id);
    (*Entry)->TryGetStringField(TEXT("playerId"), Pending.PlayerId);
    (*Entry)->TryGetStringField(TEXT("type"), Pending.Type);
    (*Entry)->TryGetStringField(TEXT("text"), Pending.Text);
    Out.Add(MoveTemp(Pending));
  }
  return Out;
}

ES09OpponentVerb OpponentVerb(const FS08Snapshot& Snapshot, const FString& ViewerId) {
  if (ViewerId.IsEmpty() || Snapshot.Phase == TEXT("GAME_OVER")) return ES09OpponentVerb::None;
  const TSharedPtr<FJsonObject> Meta =
      Snapshot.Metadata.IsValid() && Snapshot.Metadata->Type == EJson::Object ? Snapshot.Metadata->AsObject() : nullptr;
  // the head of the queue is the choice the server waits on - whoever owns it is the one acting now
  const TArray<FS08PendingEffect> Queue = PendingQueue(Snapshot);
  if (Queue.Num() > 0 && !Queue[0].PlayerId.IsEmpty()) {
    if (Queue[0].PlayerId == ViewerId) return ES09OpponentVerb::None;
    const FString& Type = Queue[0].Type;
    return Type == TEXT("DISCARD_CARDS") || Type == TEXT("BOOST_CHOICE") || Type == TEXT("DECK_TOP_PICK")
               ? ES09OpponentVerb::Card
               : ES09OpponentVerb::Ability;
  }
  // only the public player ids are read here (TryGet: no parser warnings for the optional combat fields)
  auto PlayerOf = [&Meta](const TCHAR* Field, const TCHAR* IdField) {
    const TSharedPtr<FJsonObject>* Object = nullptr;
    FString Id;
    if (Meta.IsValid() && Meta->TryGetObjectField(Field, Object) && Object && Object->IsValid()) {
      if (!(*Object)->TryGetStringField(IdField, Id) || Id.IsEmpty()) Id = TEXT("?");
    }
    return Id;
  };
  const FString Defender = PlayerOf(TEXT("combatInfo"), TEXT("defenderId"));
  if (!Defender.IsEmpty() && Defender != TEXT("?")) {
    return Defender == ViewerId ? ES09OpponentVerb::Attack : ES09OpponentVerb::Defend;
  }
  const FString Maneuver = PendingManeuverPlayer(Snapshot);
  if (!Maneuver.IsEmpty()) return Maneuver != ViewerId ? ES09OpponentVerb::Maneuver : ES09OpponentVerb::None;
  const FString Discard = PlayerOf(TEXT("pendingHandDiscard"), TEXT("playerId"));
  if (!Discard.IsEmpty() && Discard != TEXT("?")) {
    return Discard != ViewerId ? ES09OpponentVerb::Card : ES09OpponentVerb::None;
  }
  if (!Snapshot.CurrentTurnPlayerId.IsEmpty() && Snapshot.CurrentTurnPlayerId != ViewerId) return ES09OpponentVerb::Turn;
  return ES09OpponentVerb::None;
}

FName VerbKey(ES09OpponentVerb Verb) {
  switch (Verb) {
    case ES09OpponentVerb::Turn: return FName(TEXT("ms.opp.phase.turn"));
    case ES09OpponentVerb::Maneuver: return FName(TEXT("ms.opp.planning"));
    case ES09OpponentVerb::Attack: return FName(TEXT("ms.opp.phase.attack"));
    case ES09OpponentVerb::Defend: return FName(TEXT("ms.opp.phase.defend"));
    case ES09OpponentVerb::Card: return FName(TEXT("ms.opp.phase.card"));
    case ES09OpponentVerb::Ability: return FName(TEXT("ms.opp.phase.ability"));
    default: return NAME_None;
  }
}

const TCHAR* VerbName(ES09OpponentVerb Verb) {
  switch (Verb) {
    case ES09OpponentVerb::Turn: return TEXT("turn");
    case ES09OpponentVerb::Maneuver: return TEXT("maneuver");
    case ES09OpponentVerb::Attack: return TEXT("attack");
    case ES09OpponentVerb::Defend: return TEXT("defend");
    case ES09OpponentVerb::Card: return TEXT("card");
    case ES09OpponentVerb::Ability: return TEXT("ability");
    default: return TEXT("none");
  }
}

TArray<FString> YourFightersMoved(const FS09LastMovement& Trail, const FString& ViewerId,
                                  const TFunction<FString(const FString&)>& OwnerOf) {
  TArray<FString> Out;
  if (!Trail.bValid || Trail.Source != TEXT("EFFECT") || ViewerId.IsEmpty() || Trail.PlayerId == ViewerId) return Out;
  for (const FS09LastMovement::FMove& Move : Trail.Moves) {
    if (OwnerOf(Move.FighterId) == ViewerId) Out.AddUnique(Move.FighterId);
  }
  return Out;
}

FString EffectCardName(const FString& PendingText, const TArray<FS09CardView>& MoverDiscard) {
  const FString Needle = PendingText.TrimStartAndEnd();
  if (!Needle.IsEmpty()) {
    for (int32 I = MoverDiscard.Num() - 1; I >= 0; --I) {
      const FS09CardView& Card = MoverDiscard[I];
      if (!Card.bHidden && !Card.Name.IsEmpty() && Card.Text.Contains(Needle, ESearchCase::IgnoreCase)) return Card.Name;
    }
  }
  for (int32 I = MoverDiscard.Num() - 1; I >= 0; --I) {
    const FS09CardView& Card = MoverDiscard[I];
    if (!Card.bHidden && !Card.Name.IsEmpty() && (!Card.Text.IsEmpty() || Card.EffectCount > 0)) return Card.Name;
  }
  return FString();
}

}  // namespace S09OpponentView

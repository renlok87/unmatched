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
  if (State == ES09LastMoveState::Fading && NowMs - FadeStartMs >= FadeMs) {
    State = ES09LastMoveState::None;
    ++Revision;
    Lines.Add(FString::Printf(TEXT("MS-LAST off seq=%d fade=%d"), Trail.Seq, FMath::RoundToInt(FadeMs)));
  }
  return Lines;
}

float FS09LastMoveTracker::Alpha(double NowMs) const {
  switch (State) {
    case ES09LastMoveState::Shown: return 1.0f;
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
  *this = FS09LastMoveTracker();
  Revision = Rev;
}

// ---------------------------------------------------------------------------------------------------- feed

FS09FeedEntry FS09EventFeed::Describe(const FS09LastMovement& Trail, const FNameOf& PlayerName,
                                      const FNameOf& FighterName, const FCellName& CellName) {
  FS09FeedEntry Entry;
  Entry.Seq = Trail.Seq;
  Entry.Moves = Trail.Moves.Num();
  TArray<FString> Moves;
  for (const FS09LastMovement::FMove& Move : Trail.Moves) {
    Moves.Add(Fill(TEXT("ms.log.move"), {{TEXT("fighterName"), FighterName(Move.FighterId)},
                                        {TEXT("from"), CellName(Move.From)},
                                        {TEXT("to"), CellName(Move.Dest())}}));
  }
  FString Inline;
  FString Full;
  if (Moves.Num() == 0) {
    Inline = Full = S08WhyText::En(FName(TEXT("ms.log.stay")));
  } else {
    Full = FString::Join(Moves, TEXT(", "));
    if (Moves.Num() > MaxInlineMoves) {
      // MS-E-106: the first two moves + "and N more" keep the line within two visual lines at 150 %
      const int32 Shown = MaxInlineMoves - 1;
      TArray<FString> Head(Moves.GetData(), Shown);
      Head.Add(S08WhyText::En(FName(TEXT("ms.log.more")), {{TEXT("n"), FString::FromInt(Moves.Num() - Shown)}}));
      Inline = FString::Join(Head, TEXT(", "));
      Entry.bTruncated = true;
    } else {
      Inline = Full;
    }
  }
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

void FS09EventFeed::Reset() {
  Lines.Reset();
  Seen.Reset();
  ++Revision;
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

}  // namespace S09OpponentView

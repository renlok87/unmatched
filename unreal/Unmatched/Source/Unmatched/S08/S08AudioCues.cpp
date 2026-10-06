#include "S08AudioCues.h"

#include "../S09/S09OpponentView.h"

bool S08AudioCues::IsMedusaGazeHead(const FString& HeadId) {
  return HeadId.StartsWith(TEXT("ability-medusa-target"), ESearchCase::IgnoreCase);
}

TArray<FString> S08AudioCues::PushedFighters(const FS09LastMovement& Trail,
                                             TFunctionRef<FString(const FString&)> OwnerOf) {
  TArray<FString> Out;
  if (!Trail.bValid || Trail.Source != TEXT("EFFECT") || Trail.PlayerId.IsEmpty()) return Out;
  for (const FS09LastMovement::FMove& Move : Trail.Moves) {
    const FString Owner = OwnerOf(Move.FighterId);
    if (!Owner.IsEmpty() && Owner != Trail.PlayerId) Out.AddUnique(Move.FighterId);
  }
  return Out;
}

TArray<int32> S08AudioCues::SetupDelays(int32 Figures, int32 FirstMs) {
  TArray<int32> Out;
  for (int32 I = 0; I < FMath::Min(Figures, 6); ++I) Out.Add(FirstMs + I * 140);
  return Out;
}

FString FS08DeadlineBeeper::Feed(const FString& DeadlineKey, double SecondsLeft) {
  if (DeadlineKey != Key) {
    Key = DeadlineKey;
    bWarned = false;
    LastTick = 0;
  }
  if (SecondsLeft <= 0.0) return FString();
  const int32 Whole = FMath::CeilToInt(SecondsLeft);
  if (Whole <= 5 && (LastTick == 0 || Whole < LastTick)) {
    LastTick = Whole;
    bWarned = true;  // the ticks carry the last seconds; a late join never warns after them
    return TEXT("UI-TIMER-TICK");
  }
  if (!bWarned && SecondsLeft <= 10.0) {
    bWarned = true;
    return TEXT("UI-TIMER-WARN");
  }
  return FString();
}

void FS08DeadlineBeeper::Reset() {
  Key.Reset();
  bWarned = false;
  LastTick = 0;
}

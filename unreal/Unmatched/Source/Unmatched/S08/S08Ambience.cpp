// AU-S4: the map ambience - see S08Ambience.h.
#include "S08Ambience.h"

FS08AmbPlan S08Ambience::PlanFor(const FString& MapKey) {
  FS08AmbPlan Plan;
  Plan.MapKey = MapKey;
  auto Spot = [](const TCHAR* Id, float MinS, float MaxS, const TCHAR* Follows = TEXT("")) {
    FS08AmbSpot S;
    S.BankId = Id;
    S.MinS = MinS;
    S.MaxS = MaxS;
    S.Follows = Follows;
    return S;
  };
  if (MapKey == TEXT("MARMOREAL")) {
    // 02 §4.8: night insects + leaves + cliff wind; gusts with sakura, petals after a gust, lantern crackle, an owl.
    Plan.Beds = {TEXT("AMB-MARMOREAL-BED")};
    Plan.Spots = {Spot(TEXT("AMB-MARMOREAL-GUST"), 15, 40), Spot(TEXT("AMB-MARMOREAL-PETALS"), 0, 0, TEXT("AMB-MARMOREAL-GUST")),
                  Spot(TEXT("AMB-MARMOREAL-LANTERN"), 20, 60), Spot(TEXT("AMB-MARMOREAL-BIRD"), 90, 180)};
  } else if (MapKey == TEXT("SARPEDON")) {
    // sea, the waterfall (left), two fires, the banner at the wind 0.35 Hz; rigging, distant gulls, a cannon chain.
    // No cannon shots: the cannons are static, a boom would be mistaken for combat.
    Plan.Beds = {TEXT("AMB-SARPEDON-BED"), TEXT("AMB-SARPEDON-FALLS"), TEXT("AMB-SARPEDON-FIRE-FORT"),
                 TEXT("AMB-SARPEDON-FIRE-BRAZIER"), TEXT("AMB-SARPEDON-BANNER")};
    Plan.Spots = {Spot(TEXT("AMB-SARPEDON-RIGGING"), 20, 50), Spot(TEXT("AMB-SARPEDON-GULLS"), 60, 150),
                  Spot(TEXT("AMB-SARPEDON-CHAIN"), 90, 200)};
  }
  return Plan;
}

FString S08Ambience::MapKeyOf(const FString& Board) {
  if (Board.Contains(TEXT("marmoreal"), ESearchCase::IgnoreCase) || Board.Contains(TEXT("c121b47f8d6eb28daccb76d05"))) {
    return TEXT("MARMOREAL");
  }
  if (Board.Contains(TEXT("sarpedon"), ESearchCase::IgnoreCase) || Board.Contains(TEXT("c7fa64a26c29a0835f2383e63"))) {
    return TEXT("SARPEDON");
  }
  return FString();
}

int64 FS08AmbienceScheduler::Interval(const FS08AmbSpot& Spot) {
  return static_cast<int64>(Rng.FRandRange(Spot.MinS, FMath::Max(Spot.MinS, Spot.MaxS)) * 1000.0f);
}

void FS08AmbienceScheduler::Start(const FS08AmbPlan& InPlan, int64 TMs, TArray<FString>& OutLines) {
  Plan = InPlan;
  Next.Reset();
  Followers.Reset();
  for (const FS08AmbSpot& S : Plan.Spots) Next.Add(S.Follows.IsEmpty() ? TMs + Interval(S) : MAX_int64);
  OutLines.Add(FString::Printf(TEXT("AMB map=%s beds=%d spots=%d t=%lld"), Plan.MapKey.IsEmpty() ? TEXT("-") : *Plan.MapKey,
                               Plan.Beds.Num(), Plan.Spots.Num(), static_cast<long long>(TMs)));
}

TArray<FString> FS08AmbienceScheduler::TakeDue(int64 TMs, TArray<FString>& OutLines) {
  TArray<FString> Due;
  for (int32 I = 0; I < Plan.Spots.Num(); ++I) {
    if (Next[I] > TMs) continue;
    const FS08AmbSpot& S = Plan.Spots[I];
    Due.Add(S.BankId);
    Next[I] = TMs + Interval(S);
    for (const FS08AmbSpot& F : Plan.Spots) {
      if (F.Follows == S.BankId && Rng.FRand() < F.FollowChance) {
        Followers.Emplace(TMs + static_cast<int64>(F.FollowDelayS * 1000.0f), F.BankId);
      }
    }
  }
  for (int32 I = 0; I < Followers.Num();) {
    if (Followers[I].Key <= TMs) {
      Due.Add(Followers[I].Value);
      Followers.RemoveAt(I);
    } else {
      ++I;
    }
  }
  for (const FString& Id : Due) {
    OutLines.Add(FString::Printf(TEXT("AMB spot=%s t=%lld"), *Id, static_cast<long long>(TMs)));
  }
  return Due;
}

// AU-S4 (docs/game-design/audio/02-audio-design.md §4.8, card AUC-U05): the map ambience, world-free.
// A map has looping beds (stereo, pan baked into the assets - the camera never moves, D-10) and spot one-shots at
// random intervals. The spots are scheduled with a seeded stream (a trace repeats). In -Bench (env FX frozen) the
// ambience is silent, like the animated backdrop; in combat the Ambience bus ducks -4 dB (02 §5.2).
//
// Trace: AMB map=<KEY> beds=<n> t=<ms> | AMB spot=<bank id> t=<ms>
#pragma once

#include "CoreMinimal.h"
#include "Math/RandomStream.h"

struct UNMATCHED_API FS08AmbSpot {
  FString BankId;
  float MinS = 20.0f;
  float MaxS = 60.0f;
  FString Follows;      // a spot that follows another one (petals after a gust)
  float FollowDelayS = 0.8f;
  float FollowChance = 0.7f;
};

struct UNMATCHED_API FS08AmbPlan {
  FString MapKey;
  TArray<FString> Beds;
  TArray<FS08AmbSpot> Spots;
};

namespace S08Ambience {
/** The plan of a map key (MARMOREAL / SARPEDON); an empty plan for a map without ambience. */
UNMATCHED_API FS08AmbPlan PlanFor(const FString& MapKey);
/** The map key of a board: the profile / board name or id (marmoreal-original, Board c121b..., Sarpedon ...). */
UNMATCHED_API FString MapKeyOf(const FString& BoardNameOrId);
}  // namespace S08Ambience

class UNMATCHED_API FS08AmbienceScheduler {
public:
  explicit FS08AmbienceScheduler(int32 Seed = 0xA4B1) : Rng(Seed) {}
  /** Starts a map at TMs (beds now, each spot after its first interval). */
  void Start(const FS08AmbPlan& Plan, int64 TMs, TArray<FString>& OutLines);
  void Stop() { Plan = FS08AmbPlan(); Next.Reset(); Followers.Reset(); }
  /** The spots due at TMs (bank ids), oldest first. */
  TArray<FString> TakeDue(int64 TMs, TArray<FString>& OutLines);
  const FS08AmbPlan& GetPlan() const { return Plan; }

private:
  FRandomStream Rng;
  FS08AmbPlan Plan;
  TArray<int64> Next;                       // per spot
  TArray<TPair<int64, FString>> Followers;  // pending follower spots
  int64 Interval(const FS08AmbSpot& Spot);
};

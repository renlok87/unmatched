// AU-S5 (docs/game-design/audio/07-production-log.md §9): world-free decisions of the sounds wired after AU-S4 - the
// defense deadline beeps, the forced move of an enemy figure, Medusa's start-of-turn gaze head, the placement cascade
// at the match start. The game mode (S08FlowGameModeAudio.cpp) feeds them and plays the banks.
#pragma once

#include "CoreMinimal.h"

struct FS09LastMovement;

namespace S08AudioCues {
/** Medusa's start-of-turn ability head: the server opens it as `ability-medusa-target-p<N>` (TARGET_FIGHTER,
 *  optional, 1 damage to an enemy in Medusa's zone; generic-hero-ability.handler.ts). */
UNMATCHED_API bool IsMedusaGazeHead(const FString& HeadId);

/** BRD-PUSH: the figures an EFFECT trail moved that do not belong to the player whose effect moved them. A maneuver
 *  trail, an invalid trail or an unknown owner gives none (the plain BRD-STEP plays). */
UNMATCHED_API TArray<FString> PushedFighters(const FS09LastMovement& Trail,
                                             TFunctionRef<FString(const FString&)> OwnerOf);

/** BRD-SETUP: the delays of the placement sounds at the match start, one per figure, at most 6, 140 ms apart. */
UNMATCHED_API TArray<int32> SetupDelays(int32 Figures, int32 FirstMs = 300);
}  // namespace S08AudioCues

/** UI-TIMER-WARN / UI-TIMER-TICK of a server deadline: WARN once when 10 s or less are left, TICK on each whole second
 *  5..1. A new deadline (another key) starts over; the HUD refreshes 4 times a second and a re-applied snapshot keeps
 *  the key, so no sound repeats. An expired deadline is silent. */
struct UNMATCHED_API FS08DeadlineBeeper {
  /** The bank to play now ("" for none). */
  FString Feed(const FString& DeadlineKey, double SecondsLeft);
  void Reset();

private:
  FString Key;
  bool bWarned = false;
  int32 LastTick = 0;  // the last whole second that ticked (0: none yet)
};

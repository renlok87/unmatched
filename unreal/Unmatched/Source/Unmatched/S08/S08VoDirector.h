// AU-S4 (docs/game-design/audio/02-audio-design.md §3, 04-vo-script.md, card AUC-U04): hero lines, world-free.
// An event of the match is OFFERED to the director; it decides whether a line plays and which one:
//   - per event: probability, cooldown per speaker and event, priority (1 = most important), once-per-match events;
//   - one voice at a time: a higher priority (lower number) interrupts, an equal or lower one is dropped (no queue);
//   - a global gap of 3 s between lines, except priority 1 and the opponent's answer at the match start;
//   - budget: more than 3 lines in the last 60 s halves the chance of priority >= 3;
//   - animation speed "fast" / "none" halves attack, defend and hurt;
//   - the line: a bag without repeats over the lines of (speaker, event); harpies by their pitch version (H1-H3).
// Lines exist only for PUBLIC events (02 §3.2, §5.8): the caller never offers a hidden one (a defense card before the
// reveal, a face-down boost, the cards of Prophecy).
//
// Trace: VO event=<EVENT> speaker=<KEY> t=<ms> result=<played|skipped> line=<id|-> prio=<p> [reason=<...>]
#pragma once

#include "CoreMinimal.h"
#include "Math/RandomStream.h"
#include "S08AudioBank.h"

struct UNMATCHED_API FS08VoOffer {
  FString Event;        // the script event: ATTACK, HURT, CARD-EXCALIBUR, MATCHUP-MEDUSA, ...
  FString Speaker;      // ARTHUR / MERLIN / MEDUSA / HARPY
  int32 HarpyIndex = 1; // 1..3: the harpy's pitch version
  int64 TMs = 0;
  float SpeedMul = 1.0f;  // the combat animation speed (0 = none, 0.5 = fast)
  bool bAnswer = false;   // the opponent's answer to the match-start line (no gap, 60 %)
};

struct UNMATCHED_API FS08VoDecision {
  bool bPlay = false;
  bool bInterrupt = false;  // stop the current line first (80 ms fade)
  FString LineId;           // ARTHUR-ATTACK-02 / HARPY-ATTACK-01-H2
  FString Path;             // soft path of the SoundWave
  FString En;               // subtitles (empty: no subtitle - an effort or a cry)
  FString Ru;
  int32 Priority = 5;
  FString Reason;           // why it was skipped
};

class UNMATCHED_API FS08VoDirector {
public:
  static constexpr int32 GapMs = 3000;
  static constexpr int32 BudgetWindowMs = 60000;
  static constexpr int32 BudgetLines = 3;

  explicit FS08VoDirector(int32 Seed = 0x0E0E) : Rng(Seed) {}

  /** A new match: once-per-match flags, cooldowns and the budget start over. */
  void NewMatch(int32 Seed);
  FS08VoDecision Offer(const FS08VoOffer& Offer, TArray<FString>& OutLines);
  /** The adapter: the line started (its length) / ended. */
  void Started(int64 TMs, int32 LengthMs);
  void Finished(int64 TMs);
  bool IsSpeaking(int64 TMs) const { return bSpeaking && TMs < SpeakingUntilMs; }
  int32 CurrentPriority() const { return CurrentPrio; }

  struct FRule {
    float Chance = 1.0f;
    int32 CooldownMs = 0;
    int32 Priority = 3;
    bool bOnce = false;
    bool bCombat = false;  // halved at fast / none animation speed
  };
  /** The rule of a script event (CARD-* share one). */
  static FRule RuleFor(const FString& Speaker, const FString& Event);

private:
  FRandomStream Rng;
  FS08SoundBag Bag;
  TMap<FString, int64> Cooldowns;  // speaker|event -> last
  TSet<FString> OnceDone;
  TArray<int64> Recent;            // line starts within the budget window
  int64 LastLineMs = MIN_int64;
  bool bSpeaking = false;
  int64 SpeakingUntilMs = 0;
  int32 CurrentPrio = 99;

  void Trace(const FS08VoOffer& Offer, const FS08VoDecision& D, TArray<FString>& OutLines) const;
};

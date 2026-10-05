// R-03 (run H 2026-10-05; REVIEW-IMPL-2026-10-04-fable §2 "observation", RESEARCH-2026-10-05 finding 7): the catch-up
// policy of the presentation queue. The game state never waits for a presentation (DE-018: the snapshot is applied at
// once, DE-015: the input opens on the apply, S09TurnStatus: the status line is "what to do now"), so the status line,
// the move feed and the command panel always speak about the newest applied seq. What may lag is the presentation: a
// combat staging of seq N runs its F-01 scale (2.9-5+ s) while seq N+1.. are applied - with a fast opponent (the VS_AI
// bot, an auto client) the edge cards of combat N were still on screen while the panel printed the cards of seq N+4.
//
// Policy (shipped games cut or skip the show in favour of the server timing instead of delaying the state - Hearthstone
// Battlegrounds skipped animations of a lagging client, RESEARCH finding 7): the lag of a staging is bounded.
//   - hurry ("short version"): the remaining holds (read, effect lines, the pause "score") are dropped exactly like a
//     player's skip (F-01) - the blow itself (lunge, contact, HitReact, "-N", HP) still plays, <= ~2 s. When:
//       * the staging has been behind a newer applied snapshot for longer than T (MaxLagMs), or
//       * a newer combat is open (the next staging is queued: its declare / defense must not run under the old cards);
//   - cut (instant result, `cut=catchup`, the same Cut as `replace`): more than K (MaxQueued) newer snapshots are
//     queued behind the staging (seq distance - merged snapshots count by seq). The held HP / fall are released now.
//   A newer combat RESULT keeps replacing the staging (cut=replace, unchanged): only the newest staging plays.
//   GAME_OVER suspends the policy: the result gate (DE-019, FS09ResultGate) waits for the staging, insurance 10 s.
// Hence the text never leads the screen by more than MaxLeadMs = T + the short version's tail (the rest of CUE-010 +
// the contact frame + CUE-011 <= 1 s) or K snapshots, whichever comes first.
//
// Config: CVars s09.Catchup.MaxQueued (K, default 3) and s09.Catchup.MaxLagMs (T, default 1500 ms), 0 = that rule off;
// the command line -S09CatchupQueued=<n> / -S09CatchupLagMs=<ms> overrides them (review runs).
// Trace (cue_contract.py check-trace C10, CUE-DISPATCHER.md §5-§6):
//   CATCHUP config queued=<K> lagMs=<T>
//   CATCHUP seq=<staged> latest=<applied> queued=<n> lag=<ms> t=<ms> action=<hurry|cut> reason=<lag|combat|queue>
//           applied=<0|1>
// next to the staging's own `CUE combat seq=<staged> stage=skip t=<t> src=catchup` (hurry, applied=1) or
// `CUE combat seq=<staged> stage=end t=<t> … cut=catchup` (cut).
#pragma once

#include "CoreMinimal.h"

struct UNMATCHED_API FS09CatchupConfig {
  static constexpr int32 DefaultMaxQueued = 3;
  static constexpr int32 DefaultMaxLagMs = 1500;
  int32 MaxQueued = DefaultMaxQueued;  // K: newer snapshots a staging may lag behind (0 = no queue cut)
  int32 MaxLagMs = DefaultMaxLagMs;    // T: ms a staging may lag behind a newer snapshot before it hurries (0 = off)
  /** The CVar values with the command-line overrides (-S09CatchupQueued=<n>, -S09CatchupLagMs=<ms>); negatives = 0. */
  static FS09CatchupConfig Resolve(int32 CVarQueued, int32 CVarLagMs, const TCHAR* CommandLine);
  /** The config in force now: CVars s09.Catchup.MaxQueued / s09.Catchup.MaxLagMs + FCommandLine. */
  static FS09CatchupConfig Current();
  FString TraceLine() const;
};

enum class ES09CatchupAction : uint8 { None, Hurry, Cut };
enum class ES09CatchupReason : uint8 { None, Lag, Combat, Queue };
UNMATCHED_API const TCHAR* S09CatchupActionName(ES09CatchupAction Action);
UNMATCHED_API const TCHAR* S09CatchupReasonName(ES09CatchupReason Reason);

struct UNMATCHED_API FS09CatchupDecision {
  ES09CatchupAction Action = ES09CatchupAction::None;
  ES09CatchupReason Reason = ES09CatchupReason::None;
  int32 StagedSeq = -1;
  int32 LatestSeq = -1;
  int32 Queued = 0;
  int64 LagMs = 0;
  bool IsSet() const { return Action != ES09CatchupAction::None; }
  /** The CATCHUP line; bApplied = the staging really changed (a hurry after the last hold is a no-op: applied=0). */
  FString TraceLine(int64 NowMs, bool bApplied) const;
};

class UNMATCHED_API FS09PresentationCatchup {
public:
  void Configure(const FS09CatchupConfig& InConfig) { Config = InConfig; }
  const FS09CatchupConfig& GetConfig() const { return Config; }
  /** Binds the policy to the running staging: a different seq starts a fresh queue, -1 = no staging (idle). */
  void Track(int32 StagedSeq, int64 NowMs);
  /** One APPLIED snapshot. bGameOver = its phase is GAME_OVER (the policy stops: the result gate owns the end);
   *  bCombatOpen = a combat is open in it (newer than the staging by construction - the staged one is closed). */
  FS09CatchupDecision OnApplied(int32 Seq, int64 NowMs, bool bGameOver, bool bCombatOpen);
  /** The lag rule on the game clock (every frame). */
  FS09CatchupDecision Tick(int64 NowMs);

  int32 GetStagedSeq() const { return StagedSeq; }
  int32 GetLatestSeq() const { return LatestSeq; }
  /** Newer snapshots behind the staging (seq distance). */
  int32 Queued() const { return StagedSeq >= 0 && LatestSeq > StagedSeq ? LatestSeq - StagedSeq : 0; }
  /** How long the staging has been behind a newer snapshot (0 when it is not). */
  int64 LagMs(int64 NowMs) const { return FirstNewerMs >= 0 ? FMath::Max<int64>(0, NowMs - FirstNewerMs) : 0; }
  bool IsSuspended() const { return bSuspended; }
  bool HasHurried() const { return bHurried; }
  bool HasCut() const { return bCut; }

  /** Upper bound of the text lead (ms from the first newer snapshot to the end of the staging) under the lag rule: T +
   *  the short version's tail = the rest of CUE-010 (<= 800 x speed) + the contact frame (x speed) + CUE-011 / the fall
   *  (<= 1000, 08 §6.1 P3). -1 when the lag rule is off. */
  static int64 MaxLeadMs(const FS09CatchupConfig& Config, float SpeedMul, int32 ContactMs);

private:
  FS09CatchupConfig Config;
  int32 StagedSeq = -1;
  int32 LatestSeq = -1;
  int64 FirstNewerMs = -1;
  bool bHurried = false;
  bool bCut = false;
  bool bSuspended = false;
  FS09CatchupDecision Make(ES09CatchupAction Action, ES09CatchupReason Reason, int64 NowMs) const;
  FS09CatchupDecision Decide(int64 NowMs, bool bCombatOpen);
};

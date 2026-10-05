// R-03 automation tests: the catch-up policy of the presentation queue (S09PresentationCatchup.h) driving the combat
// staging (S09CombatStage.h) the way AS08FlowGameMode::RunPresentationCatchup does.
//   Unmatched.S09.Catchup.Config  - defaults K = 3 / T = 1500, CVar values, command-line overrides, the trace lines;
//   Unmatched.S09.Catchup.Single  - a single combat is never cut: no newer snapshot, a same-seq merge, a newer snapshot
//                                   that comes when the staging is (almost) over - the full F-01 scale plays;
//   Unmatched.S09.Catchup.Queue   - a stream of N combats from a fast client catches up: every older staging ends in
//                                   bounded time (replace / short version / cut), only the newest plays in full, and
//                                   it ends a single staging after the last snapshot; K newer moves cut a staging;
//   Unmatched.S09.Catchup.Lead    - the status line (= the newest applied seq) never leads the screen by more than
//                                   MaxLeadMs: one newer snapshot early in a long staging -> short version at T, at
//                                   speed x1 and "slow"; the blow (lunge, contact, -N, HP) still plays;
//   Unmatched.S09.Catchup.GameOver - GAME_OVER suspends the policy: the staging plays out and the DE-019 result gate
//                                   still waits for its end.
#if WITH_AUTOMATION_TESTS

#include "S09CombatStage.h"
#include "S09DeathStage.h"
#include "S09PresentationCatchup.h"
#include "../S08/S08CueDispatcher.h"
#include "Misc/AutomationTest.h"

namespace S09CatchupTest {
FS09CombatStageInput Combat(int32 Seq, bool bText, int32 Lines, float Speed = 1.0f) {
  FS09CombatStageInput In;
  In.Seq = Seq;
  In.AttackerId = TEXT("arthur");
  In.TargetId = TEXT("medusa");
  In.bHasEffectText = bText;
  In.EffectLines = Lines;
  for (int32 I = 0; I < Lines; ++I) {
    FS09CombatEffectLine Line;
    Line.Text = FString::Printf(TEXT("line %d"), I + 1);
    In.Effects.Add(Line);
  }
  In.Damage = 2;
  In.HpBefore = 7;
  In.HpAfter = 5;
  In.TargetX = 3;
  In.TargetY = 4;
  In.ContactMs = 292;
  In.ContactSource = TEXT("notify");
  In.SpeedMul = Speed;
  In.Reveal.AttackValue = 4;
  In.Reveal.bNoDefense = true;
  return In;
}

/** One applied snapshot of the scripted stream. */
struct FApply {
  int64 AtMs = 0;
  int32 Seq = 0;
  bool bCombatOpen = false;
  bool bGameOver = false;
  bool bClosesCombat = false;  // the snapshot closes a combat: its staging starts (replacing a running one)
  FS09CombatStageInput Closing;
};

/** The adapter of AS08FlowGameMode on a 1 ms clock: per apply - the result staging, then OnApplied; per tick - the
 *  staging, then the lag rule. Records the trace, the catch-up decisions and the visible seq per ms. */
struct FHarness {
  FS09CombatStage Stage;
  FS08CueDispatcher Cues;
  FS09PresentationCatchup Policy;
  TArray<FString> Lines;
  TArray<FS09CombatStageEvent> Events;
  TArray<FS09CatchupDecision> Decisions;
  int64 MaxLeadMs = 0;         // the largest (now - first newer snapshot) while an older staging was on screen
  int32 LatestSeq = -1;        // what the status line speaks about (the newest applied seq)
  int64 FirstNewerMs = -1;     // the first apply newer than the visible staging
  int32 FirstNewerFor = -1;    // ... for this staging seq
  TFunction<void(int64)> AfterTick;  // per-ms probe (the result gate)

  explicit FHarness(const FS09CatchupConfig& Config) { Policy.Configure(Config); }

  void Act(const FS09CatchupDecision& D, int64 Now) {
    if (!D.IsSet()) return;
    Decisions.Add(D);
    bool bApplied = false;
    if (D.Action == ES09CatchupAction::Cut) {
      bApplied = Stage.IsActive();
      Stage.Cut(Now, TEXT("catchup"), Cues, Lines, Events);
    } else {
      bApplied = Stage.Skip(Now, TEXT("catchup"), Cues, Lines, Events);
    }
    Lines.Add(D.TraceLine(Now, bApplied));
  }
  void Apply(const FApply& A) {
    if (A.Seq > LatestSeq) LatestSeq = A.Seq;
    if (A.bClosesCombat) Stage.Start(A.Closing, A.AtMs, Cues, Lines, Events);
    Policy.Track(Stage.IsActive() ? Stage.GetSeq() : -1, A.AtMs);
    Act(Policy.OnApplied(A.Seq, A.AtMs, A.bGameOver, A.bCombatOpen), A.AtMs);
  }
  void Tick(int64 Now) {
    Stage.Tick(Now, Cues, Lines, Events);
    Cues.Advance(Now, Lines);
    Policy.Track(Stage.IsActive() ? Stage.GetSeq() : -1, Now);
    Act(Policy.Tick(Now), Now);
    // The lead of the text: the status already speaks about a newer seq than the staging on screen.
    if (Stage.IsActive() && LatestSeq > Stage.GetSeq()) {
      if (FirstNewerFor != Stage.GetSeq()) {
        FirstNewerFor = Stage.GetSeq();
        FirstNewerMs = Now;
      }
      MaxLeadMs = FMath::Max(MaxLeadMs, Now - FirstNewerMs);
    }
    if (AfterTick) AfterTick(Now);
  }
  /** Runs the stream on a 1 ms clock until EndMs (applies first in their frame, like HandleApplied before Tick). */
  void Run(const TArray<FApply>& Stream, int64 FromMs, int64 EndMs) {
    int32 Next = 0;
    for (int64 T = FromMs; T <= EndMs; ++T) {
      while (Next < Stream.Num() && Stream[Next].AtMs <= T) Apply(Stream[Next++]);
      Tick(T);
    }
  }
  int32 Count(const TCHAR* Needle, const TCHAR* Also = nullptr) const {
    int32 N = 0;
    for (const FString& L : Lines) N += L.Contains(Needle) && (!Also || L.Contains(Also)) ? 1 : 0;
    return N;
  }
  /** The `stage=end` line of a staging seq ('' when none). */
  FString EndLine(int32 Seq) const {
    const FString Prefix = FString::Printf(TEXT("CUE combat seq=%d stage=end "), Seq);
    for (const FString& L : Lines) {
      if (L.StartsWith(Prefix)) return L;
    }
    return FString();
  }
  int64 EndT(int32 Seq) const {
    const FString L = EndLine(Seq);
    int64 T = -1;
    const int32 At = L.Find(TEXT(" t="));
    if (At >= 0) T = FCString::Atoi64(*L.Mid(At + 3));
    return T;
  }
};

FApply Close(int64 At, const FS09CombatStageInput& In) {
  FApply A;
  A.AtMs = At;
  A.Seq = In.Seq;
  A.bClosesCombat = true;
  A.Closing = In;
  return A;
}
FApply Step(int64 At, int32 Seq, bool bCombatOpen = false, bool bGameOver = false) {
  FApply A;
  A.AtMs = At;
  A.Seq = Seq;
  A.bCombatOpen = bCombatOpen;
  A.bGameOver = bGameOver;
  return A;
}
}  // namespace S09CatchupTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CatchupConfigTest, "Unmatched.S09.Catchup.Config",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CatchupConfigTest::RunTest(const FString&) {
  const FS09CatchupConfig Default;
  TestEqual("K default 3", Default.MaxQueued, 3);
  TestEqual("T default 1500", Default.MaxLagMs, 1500);
  const FS09CatchupConfig FromCVar = FS09CatchupConfig::Resolve(5, 2000, TEXT("-game"));
  TestEqual("CVar K", FromCVar.MaxQueued, 5);
  TestEqual("CVar T", FromCVar.MaxLagMs, 2000);
  const FS09CatchupConfig Cli = FS09CatchupConfig::Resolve(3, 1500, TEXT("-S09CatchupQueued=1 -S09CatchupLagMs=800"));
  TestEqual("command line K", Cli.MaxQueued, 1);
  TestEqual("command line T", Cli.MaxLagMs, 800);
  const FS09CatchupConfig Off = FS09CatchupConfig::Resolve(-2, -1, nullptr);
  TestEqual("negative K = off (0)", Off.MaxQueued, 0);
  TestEqual("negative T = off (0)", Off.MaxLagMs, 0);
  TestEqual("config line", Default.TraceLine(), FString(TEXT("CATCHUP config queued=3 lagMs=1500")));
  FS09CatchupDecision D;
  D.Action = ES09CatchupAction::Hurry;
  D.Reason = ES09CatchupReason::Lag;
  D.StagedSeq = 11;
  D.LatestSeq = 12;
  D.Queued = 1;
  D.LagMs = 1501;
  TestEqual("decision line", D.TraceLine(4000, true),
            FString(TEXT("CATCHUP seq=11 latest=12 queued=1 lag=1501 t=4000 action=hurry reason=lag applied=1")));
  TestEqual("lead bound x1 = 1500 + 800 + 292 + 1000", FS09PresentationCatchup::MaxLeadMs(Default, 1.0f, 292),
            static_cast<int64>(3592));
  TestEqual("lead bound slow = 1500 + 1200 + 438 + 1000", FS09PresentationCatchup::MaxLeadMs(Default, 1.5f, 292),
            static_cast<int64>(4138));
  TestEqual("no lag rule, no bound", FS09PresentationCatchup::MaxLeadMs(Off, 1.0f, 292), static_cast<int64>(-1));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CatchupSingleTest, "Unmatched.S09.Catchup.Single",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CatchupSingleTest::RunTest(const FString&) {
  using namespace S09CatchupTest;
  const FS09CatchupConfig Config;
  // ---- no newer snapshot (the turn passes inside the same seq, consumeAction): the full F-01 scale ----
  {
    FHarness H(Config);
    H.Run({Close(1000, Combat(11, true, 2))}, 1000, 9000);
    TestEqual("no decision", H.Decisions.Num(), 0);
    TestEqual("full scale with 2 lines: 5092", H.Stage.TotalMs(), static_cast<int64>(5092));
    TestTrue("end cut=0 skipped=0", H.EndLine(11).EndsWith(TEXT("skipped=0 cut=0")));
    TestEqual("no catch-up skip", H.Count(TEXT("src=catchup")), 0);
  }
  // ---- a same-seq merge (WS push + HTTP refetch) is not a newer snapshot ----
  {
    FHarness H(Config);
    H.Run({Close(1000, Combat(11, true, 1)), Step(1100, 11), Step(1200, 11)}, 1000, 9000);
    TestEqual("merge: no decision", H.Decisions.Num(), 0);
    TestEqual("merge: full 4492", H.Stage.TotalMs(), static_cast<int64>(4492));
  }
  // ---- a newer move late in the staging: the staging ends before T runs out ----
  {
    FHarness H(Config);
    H.Run({Close(1000, Combat(11, true, 0)), Step(3000, 12)}, 1000, 9000);
    TestEqual("late newer snapshot: no decision", H.Decisions.Num(), 0);
    TestEqual("late newer snapshot: full 3892", H.Stage.TotalMs(), static_cast<int64>(3892));
  }
  // ---- a newer move after the holds: the lag rule fires, but the short version changes nothing (applied=0) ----
  {
    FHarness H(Config);
    H.Run({Close(1000, Combat(11, false, 0)), Step(1150, 12)}, 1000, 9000);
    TestEqual("one decision (lag)", H.Decisions.Num(), 1);
    TestTrue("applied=0 (the holds were over)", H.Count(TEXT("action=hurry reason=lag applied=0")) == 1);
    TestEqual("no-text combat plays in full: 2892", H.Stage.TotalMs(), static_cast<int64>(2892));
    TestTrue("end cut=0", H.EndLine(11).EndsWith(TEXT("skipped=0 cut=0")));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CatchupQueueTest, "Unmatched.S09.Catchup.Queue",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CatchupQueueTest::RunTest(const FString&) {
  using namespace S09CatchupTest;
  const FS09CatchupConfig Config;
  // ---- N combats from an auto client: per combat attack (COMBAT), defense (COMBAT_RESOLVE), result, 150 ms apart.
  //      Run H review case: the cards of seq N were still on screen while the panel printed seq N+4. ----
  for (const int32 N : {2, 5, 8}) {
    FHarness H(Config);
    TArray<FApply> Stream;
    int32 Seq = 10;
    int64 T = 1000;
    TArray<int32> Results;
    for (int32 C = 0; C < N; ++C) {
      if (C > 0) {
        Stream.Add(Step(T, ++Seq, /*bCombatOpen=*/true));
        T += 150;
        Stream.Add(Step(T, ++Seq, /*bCombatOpen=*/true));
        T += 150;
      }
      Stream.Add(Close(T, Combat(++Seq, true, 2)));
      Results.Add(Seq);
      T += 150;
    }
    const int64 LastMs = Stream.Last().AtMs;
    H.Run(Stream, 1000, LastMs + 12000);
    const int32 Newest = Results.Last();
    // every older staging ended - by its short version, a replace or a cut - never after the newest started
    for (int32 I = 0; I + 1 < Results.Num(); ++I) {
      const int64 End = H.EndT(Results[I]);
      TestTrue(FString::Printf(TEXT("N=%d: staging %d ended"), N, Results[I]), End >= 0);
      TestTrue(FString::Printf(TEXT("N=%d: staging %d ended before the newest result"), N, Results[I]),
               End <= Stream.Last().AtMs);
    }
    // only the newest plays in full: no catch-up decision for it, its end comes one single staging after the stream
    TestTrue(FString::Printf(TEXT("N=%d: newest end cut=0 skipped=0"), N),
             H.EndLine(Newest).EndsWith(TEXT("skipped=0 cut=0")));
    TestEqual(FString::Printf(TEXT("N=%d: caught up = last snapshot + one staging (5092 - declare 600)"), N),
              H.EndT(Newest) - LastMs, static_cast<int64>(5092 - 600));
    // the older stagings were hurried by the newer combat (reason=combat) and replaced by the next result
    if (N > 1) {
      TestEqual(FString::Printf(TEXT("N=%d: one short version per older staging"), N),
                H.Count(TEXT("action=hurry reason=combat applied=1")), N - 1);
      TestEqual(FString::Printf(TEXT("N=%d: skip src=catchup per older staging"), N),
                H.Count(TEXT("stage=skip")), N - 1);
      TestEqual(FString::Printf(TEXT("N=%d: replaced by the next result"), N),
                H.Count(TEXT(" stage=end "), TEXT("cut=replace")), N - 1);
    }
    // the text never led the screen by more than the bound
    TestTrue(FString::Printf(TEXT("N=%d: lead %lld <= bound"), N, H.MaxLeadMs),
             H.MaxLeadMs <= FS09PresentationCatchup::MaxLeadMs(Config, 1.0f, 292));
  }
  // ---- K: moves of the opponent pile up behind a staging (seq distance) - the 4th newer one cuts it ----
  {
    FHarness H(Config);
    H.Run({Close(1000, Combat(20, true, 2)), Step(1100, 21), Step(1200, 22), Step(1300, 23), Step(1400, 24)}, 1000,
          9000);
    TestEqual("hurry? no - 3 newer snapshots are within K", H.Count(TEXT("action=hurry")), 0);
    TestEqual("cut on the 4th", H.Count(TEXT("CATCHUP seq=20 latest=24 queued=4 lag=300 t=1400 action=cut reason=queue "
                                             "applied=1")),
              1);
    TestTrue("instant result: end cut=catchup at 1400", H.EndLine(20).Contains(TEXT(" t=1400 ")) &&
                                                            H.EndLine(20).EndsWith(TEXT("cut=catchup")));
    TestEqual("the held HP is released at the cut", FString(S09CombatEventName(H.Events.Last(1).Type)),
              FString(TEXT("hp")));
    TestFalse("the hold is gone", H.Stage.GetHold().IsSet());
  }
  // ---- a merged jump (seq 30 -> 35 in one snapshot) counts by seq ----
  {
    FHarness H(Config);
    H.Run({Close(1000, Combat(30, false, 0)), Step(1050, 35)}, 1000, 9000);
    TestEqual("merged jump of 5 > K: cut", H.Count(TEXT("action=cut reason=queue")), 1);
  }
  // ---- K = 0 turns the queue rule off; T = 0 turns the lag rule off ----
  {
    FS09CatchupConfig Off;
    Off.MaxQueued = 0;
    Off.MaxLagMs = 0;
    FHarness H(Off);
    H.Run({Close(1000, Combat(40, true, 2)), Step(1100, 41), Step(1200, 42), Step(1300, 43), Step(1400, 44),
           Step(1500, 45)},
          1000, 9000);
    TestEqual("rules off: no decision", H.Decisions.Num(), 0);
    TestEqual("rules off: full scale", H.Stage.TotalMs(), static_cast<int64>(5092));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CatchupLeadTest, "Unmatched.S09.Catchup.Lead",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CatchupLeadTest::RunTest(const FString&) {
  using namespace S09CatchupTest;
  const FS09CatchupConfig Config;
  for (const float Speed : {1.0f, 1.5f, 0.5f}) {
    FHarness Full(Config);
    Full.Run({Close(1000, Combat(11, true, 3, Speed))}, 1000, 12000);
    FHarness H(Config);
    // the VS_AI bot answers 100 ms after the result: one newer snapshot, a long staging (text + 3 lines)
    H.Run({Close(1000, Combat(11, true, 3, Speed)), Step(1100, 12)}, 1000, 12000);
    const int64 Bound = FS09PresentationCatchup::MaxLeadMs(Config, Speed, 292);
    TestTrue(FString::Printf(TEXT("speed %.1f: lead %lld <= bound %lld"), Speed, H.MaxLeadMs, Bound),
             H.MaxLeadMs <= Bound);
    TestEqual(FString::Printf(TEXT("speed %.1f: short version at T + 1 ms"), Speed),
              H.Count(TEXT("CATCHUP seq=11 latest=12 queued=1 lag=1501 t=2601 action=hurry reason=lag applied=1")), 1);
    TestEqual(FString::Printf(TEXT("speed %.1f: skip src=catchup at 2601"), Speed),
              H.Count(TEXT("CUE combat seq=11 stage=skip t=2601 src=catchup")), 1);
    TestTrue(FString::Printf(TEXT("speed %.1f: not cut, skipped"), Speed),
             H.EndLine(11).EndsWith(TEXT("skipped=1 cut=0")));
    // the blow still plays in the short version
    for (const TCHAR* Stage : {TEXT(" stage=lunge "), TEXT(" stage=contact "), TEXT(" stage=hit "),
                               TEXT(" stage=minus "), TEXT(" stage=hp ")}) {
      TestEqual(FString::Printf(TEXT("speed %.1f: %s plays"), Speed, Stage), H.Count(Stage), 1);
    }
    TestTrue(FString::Printf(TEXT("speed %.1f: shorter than the full scale"), Speed),
             H.Stage.TotalMs() < Full.Stage.TotalMs());
    TestTrue(FString::Printf(TEXT("speed %.1f: the full one was longer than the bound"), Speed),
             Full.Stage.GetEndMs() - 1100 > Bound || Speed < 1.0f);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09CatchupGameOverTest, "Unmatched.S09.Catchup.GameOver",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09CatchupGameOverTest::RunTest(const FString&) {
  using namespace S09CatchupTest;
  const FS09CatchupConfig Config;
  // A sidekick's combat is staged (seq 55, long), then the hero falls at the snapshot (an ability, seq 56 GAME_OVER):
  // the policy stops, the staging plays out in full and the result gate (DE-019) waits for it.
  FHarness H(Config);
  FS09ResultGate Gate;
  int64 Shown = -1;
  bool bSuspendedSeen = false;
  FString Line;
  H.AfterTick = [&](int64 T) {
    bSuspendedSeen |= H.Policy.IsSuspended();
    const int64 StagingEnd = H.Stage.IsActive() ? H.Stage.GetEndMs() : -1;
    if (T >= 1100 && Shown < 0 && Gate.Update(T, 56, true, false, -1, Line, StagingEnd)) Shown = T;
  };
  H.Run({Close(1000, Combat(55, true, 2)), Step(1100, 56, false, /*bGameOver=*/true), Step(1200, 57), Step(1300, 58),
         Step(1400, 59), Step(1500, 60)},
        1000, 12000);
  TestTrue("suspended at GAME_OVER", bSuspendedSeen);
  TestEqual("no catch-up after GAME_OVER (lag and queue past K and T)", H.Decisions.Num(), 0);
  TestTrue("the staging plays out: cut=0", H.EndLine(55).EndsWith(TEXT("skipped=0 cut=0")));
  TestEqual("the staging is the full 5092", H.Stage.TotalMs(), static_cast<int64>(5092));
  TestEqual("the screen opens at the staging's end", Shown, H.EndT(55));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS

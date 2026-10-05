// R-03: catch-up policy of the presentation queue - see S09PresentationCatchup.h.
#include "S09PresentationCatchup.h"

#include "S09CombatStage.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace {
TAutoConsoleVariable<int32> CVarS09CatchupMaxQueued(
    TEXT("s09.Catchup.MaxQueued"), FS09CatchupConfig::DefaultMaxQueued,
    TEXT("R-03 presentation catch-up, K: a combat staging more than K newer applied snapshots behind is cut (the "
         "result is shown at once, cut=catchup). 0 = no queue cut. -S09CatchupQueued=<n> overrides it."),
    ECVF_Default);
TAutoConsoleVariable<int32> CVarS09CatchupMaxLagMs(
    TEXT("s09.Catchup.MaxLagMs"), FS09CatchupConfig::DefaultMaxLagMs,
    TEXT("R-03 presentation catch-up, T: a combat staging behind a newer applied snapshot for longer than T ms drops "
         "its remaining holds (the short version, skip src=catchup). 0 = off. -S09CatchupLagMs=<ms> overrides it."),
    ECVF_Default);
}  // namespace

const TCHAR* S09CatchupActionName(ES09CatchupAction Action) {
  switch (Action) {
    case ES09CatchupAction::Hurry: return TEXT("hurry");
    case ES09CatchupAction::Cut: return TEXT("cut");
    default: return TEXT("none");
  }
}

const TCHAR* S09CatchupReasonName(ES09CatchupReason Reason) {
  switch (Reason) {
    case ES09CatchupReason::Lag: return TEXT("lag");
    case ES09CatchupReason::Combat: return TEXT("combat");
    case ES09CatchupReason::Queue: return TEXT("queue");
    default: return TEXT("none");
  }
}

FS09CatchupConfig FS09CatchupConfig::Resolve(int32 CVarQueued, int32 CVarLagMs, const TCHAR* CommandLine) {
  FS09CatchupConfig Out;
  Out.MaxQueued = CVarQueued;
  Out.MaxLagMs = CVarLagMs;
  if (CommandLine) {
    int32 Value = 0;
    if (FParse::Value(CommandLine, TEXT("S09CatchupQueued="), Value)) Out.MaxQueued = Value;
    if (FParse::Value(CommandLine, TEXT("S09CatchupLagMs="), Value)) Out.MaxLagMs = Value;
  }
  Out.MaxQueued = FMath::Max(0, Out.MaxQueued);
  Out.MaxLagMs = FMath::Max(0, Out.MaxLagMs);
  return Out;
}

FS09CatchupConfig FS09CatchupConfig::Current() {
  return Resolve(CVarS09CatchupMaxQueued.GetValueOnGameThread(), CVarS09CatchupMaxLagMs.GetValueOnGameThread(),
                 FCommandLine::Get());
}

FString FS09CatchupConfig::TraceLine() const {
  return FString::Printf(TEXT("CATCHUP config queued=%d lagMs=%d"), MaxQueued, MaxLagMs);
}

FString FS09CatchupDecision::TraceLine(int64 NowMs, bool bApplied) const {
  return FString::Printf(TEXT("CATCHUP seq=%d latest=%d queued=%d lag=%lld t=%lld action=%s reason=%s applied=%d"),
                         StagedSeq, LatestSeq, Queued, static_cast<long long>(LagMs), static_cast<long long>(NowMs),
                         S09CatchupActionName(Action), S09CatchupReasonName(Reason), bApplied ? 1 : 0);
}

void FS09PresentationCatchup::Track(int32 InStagedSeq, int64 NowMs) {
  if (InStagedSeq == StagedSeq) return;
  StagedSeq = InStagedSeq;
  LatestSeq = InStagedSeq;
  FirstNewerMs = -1;
  bHurried = false;
  bCut = false;
  bSuspended = false;
}

FS09CatchupDecision FS09PresentationCatchup::Make(ES09CatchupAction Action, ES09CatchupReason Reason,
                                                  int64 NowMs) const {
  FS09CatchupDecision D;
  D.Action = Action;
  D.Reason = Reason;
  D.StagedSeq = StagedSeq;
  D.LatestSeq = LatestSeq;
  D.Queued = Queued();
  D.LagMs = LagMs(NowMs);
  return D;
}

FS09CatchupDecision FS09PresentationCatchup::Decide(int64 NowMs, bool bCombatOpen) {
  if (StagedSeq < 0 || bSuspended || bCut || FirstNewerMs < 0) return FS09CatchupDecision();
  // K: the queue behind the staging is too long - the result is shown at once (only the newest presentation plays).
  if (Config.MaxQueued > 0 && Queued() > Config.MaxQueued) {
    bCut = true;
    return Make(ES09CatchupAction::Cut, ES09CatchupReason::Queue, NowMs);
  }
  if (bHurried) return FS09CatchupDecision();
  // A newer combat is open: its staging is next in the queue - the old one plays its short version.
  if (bCombatOpen) {
    bHurried = true;
    return Make(ES09CatchupAction::Hurry, ES09CatchupReason::Combat, NowMs);
  }
  // T: the screen has shown an older seq than the applied one for too long.
  if (Config.MaxLagMs > 0 && LagMs(NowMs) > Config.MaxLagMs) {
    bHurried = true;
    return Make(ES09CatchupAction::Hurry, ES09CatchupReason::Lag, NowMs);
  }
  return FS09CatchupDecision();
}

FS09CatchupDecision FS09PresentationCatchup::OnApplied(int32 Seq, int64 NowMs, bool bGameOver, bool bCombatOpen) {
  if (StagedSeq < 0) return FS09CatchupDecision();
  // DE-019: from GAME_OVER on the result gate waits for the staging (insurance 10 s) - it is never cut or hurried.
  if (bGameOver) bSuspended = true;
  if (Seq > LatestSeq) {
    LatestSeq = Seq;
    if (FirstNewerMs < 0 && Seq > StagedSeq) FirstNewerMs = NowMs;
  }
  return Decide(NowMs, bCombatOpen && Seq > StagedSeq);
}

FS09CatchupDecision FS09PresentationCatchup::Tick(int64 NowMs) { return Decide(NowMs, /*bCombatOpen=*/false); }

int64 FS09PresentationCatchup::MaxLeadMs(const FS09CatchupConfig& InConfig, float SpeedMul, int32 ContactMs) {
  if (InConfig.MaxLagMs <= 0) return -1;
  auto Scaled = [SpeedMul](int32 Ms) { return SpeedMul <= 0.0f ? 0 : FMath::RoundToInt(Ms * SpeedMul); };
  return static_cast<int64>(InConfig.MaxLagMs) + Scaled(FS09CombatTiming::RevealMs) + Scaled(FMath::Max(0, ContactMs)) +
         FS09CombatTiming::MaxBlockingMs;
}

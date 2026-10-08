// VS-6 F4 (FX-34 / FX-35 / FX-36): the outcome and link post-process adapter of AS08FlowGameMode - see
// S08CuePostProcess.h. The game mode calls S08FxNetOnApplied (first line of HandleApplied) and S08FxStale (the combat
// staging of a recovered snapshot); everything else runs from S08FxTick.
//
//   grade   starts at the scheduled `CUE death stage=gone` time of the fallen hero (FS09DeathStage::LatestHeroGoneMs)
//           once the applied phase is GAME_OVER with a named winner, or at the RESULT screen frame without a hero death;
//           the viewer's own verdict (FS09HudModel::bViewerWon); held while the applied phase stays GAME_OVER.
//   link    FS08NetWatch on the HB-14 chip's inputs: lost -> desat on (CUE-017); recovered -> the reconnect (D4, when no
//           applied snapshot ran it during the loss) and the 300 ms return (CUE-018).
#include "../S08FlowGameMode.h"

#include "Misc/Parse.h"
#include "NiagaraComponent.h"
#include "../S08CueDispatcher.h"
#include "../S08IconMotion.h"
#include "../S08TraceLog.h"
#include "S08CueFx.h"
#include "S08CueFxSpawner.h"
#include "S08CuePostProcess.h"

void AS08FlowGameMode::S08FxOutcomeTick() {
  const int64 Now = NowMs();
  if (!CuePostFx) {
    if (!GetWorld()) return;
    CuePostFx = S08CuePostProcess::CreateVolume(*GetWorld());
    if (!CuePostFx) return;
    FS08Trace::Write(TEXT("FX postprocess volume=spawned priority=200 unbound=1"));
  }
  FS08CuePostProcessState& St = CuePostState;
  const bool bFx = S08CueFx::FxEnabled();
  // ---- FX-34: the outcome grade (the viewer's own verdict; ABORTED never reaches GAME_OVER)
  if (!Hud.bGameOver) {
    if (St.HasOutcome()) {
      FS08Trace::Write(FString::Printf(TEXT("FX postprocess off t=%lld reason=match-left"), static_cast<long long>(Now)));
      St.Outcome = ES08Outcome::None;
      St.OutcomeStartMs = -1;
    }
    bS08FxOutcomeNoneTraced = false;
  } else if (!St.HasOutcome()) {
    const ES08Outcome Outcome = !Hud.bWinnerKnown || Hud.bDraw || Hud.bOutcomeUnknown ? ES08Outcome::None
                                : Hud.bViewerWon                                      ? ES08Outcome::Victory
                                                                                      : ES08Outcome::Defeat;
    // the start: the fallen hero's gone frame (the DE-019 schedule) - else the result screen
    const int64 GoneMs = DeathStage.LatestHeroGoneMs();
    int64 StartMs = -1;
    const TCHAR* Src = TEXT("result");
    FString FighterId;
    if (GoneMs >= 0 && Now >= GoneMs) {
      StartMs = GoneMs;
      Src = TEXT("gone");
      for (const FS08BoardFighter& F : Fighters) {
        if (F.bIsHero && DeathStage.GoneMs(F.Id) == GoneMs) FighterId = F.Id;
      }
    } else if (GoneMs < 0 && ResultGate.IsShown()) {
      StartMs = ResultGate.GetShownMs();
    }
    if (StartMs >= 0) {
      if (Outcome == ES08Outcome::None || !bFx) {
        if (!bS08FxOutcomeNoneTraced) {
          bS08FxOutcomeNoneTraced = true;
          FS08Trace::Write(FString::Printf(TEXT("FX grade outcome=none t=%lld reason=%s"), static_cast<long long>(StartMs),
                                           !bFx ? TEXT("legacy") : Hud.bDraw ? TEXT("draw") : TEXT("unknown")));
        }
      } else {
        FString Line;
        if (St.StartOutcome(Outcome, StartMs, S08IconMotion::IsReducedMotion(), Src, FighterId, Line)) {
          FS08Trace::Write(Line);
        }
      }
    }
  }
  // ---- FX-35 / FX-36: the link (the bench has no flow: frozen weights only)
  if (Flow.IsValid() && !bBench) {
    FS08NetWatchInput In;
    In.bStarted = Flow->GetStage() == ES08Stage::Started;
    In.bStreamReady = Flow->IsStreamReady();
    In.bAwaitingRecovery = Flow->IsAwaitingStateRecovery();
    const bool bFedBefore = NetWatch.bReconnectFed;
    const ES08NetEvent Ev = NetWatch.Tick(In);
    if (!In.bStarted && S08FxStaleSeq != MIN_int32) {
      S08FxStaleSeq = MIN_int32;  // a new match numbers its seqs again
      if (CueFxSpawner) CueFxSpawner->ClearReconnect();
    }
    if (!In.bStarted && St.bDisconnected) {
      St.bDisconnected = false;
      St.RestoreStartMs = -1;
      FS08Trace::Write(FString::Printf(TEXT("FX desat off t=%lld ms=0 reason=match-left"), static_cast<long long>(Now)));
    }
    if (Ev == ES08NetEvent::Lost && bFx) {
      FString Line;
      St.Disconnect(Now, Line);
      FS08Trace::Write(Line);
    } else if (Ev == ES08NetEvent::Recovered) {
      const int32 R = Flow->GetAppliedSnapshot().SequenceNumber;
      if (!bFedBefore) S08FxReconnect(R, TEXT("stream"));
      FString Line;
      if (St.Reconnect(Now, S08IconMotion::IsReducedMotion(), CueFxSpawner ? CueFxSpawner->GetRecoveredSeq() : R, Line)) {
        FS08Trace::Write(Line);
      }
    }
  }
  if (!bFx && St.BenchOutcomeW < 0.0f && St.BenchDisconnectW < 0.0f) {
    St.bDisconnected = false;  // -S08FxLegacy: no post process at all
    St.Outcome = ES08Outcome::None;
  }
  const bool bWasOn = CuePostFx->bEnabled;
  const S08CuePostProcess::FSettings Set = St.Evaluate(Now);
  S08CuePostProcess::Apply(*CuePostFx, Set);
  if (bWasOn != static_cast<bool>(CuePostFx->bEnabled)) {
    FS08Trace::Write(FString::Printf(TEXT("FX postprocess on=%d t=%lld temp=%.0f sat=%.3f vignette=%.3f"),
                                     CuePostFx->bEnabled ? 1 : 0, static_cast<long long>(Now), Set.WhiteTemp,
                                     Set.Saturation, Set.Vignette));
  }
}

void AS08FlowGameMode::S08FxNetOnApplied(int32 Seq, bool bApply) {
  if (NetWatch.OnApplied(bApply)) S08FxReconnect(Seq, TEXT("snapshot"));
}

void AS08FlowGameMode::S08FxReconnect(int32 RecoveredSeq, const TCHAR* Src) {
  const int64 Now = NowMs();
  TArray<FString> Lines;
  // D4: the dispatcher first - every active show ends (cut=reconnect), later server cues of seq <= R are stale
  CueDispatcher.OnReconnect(RecoveredSeq, Now, Lines);
  TArray<FS09CombatStageEvent> CombatEvents;
  if (CombatStage.IsActive()) CombatStage.Cut(Now, TEXT("reconnect"), CueDispatcher, Lines, CombatEvents);
  TArray<FS09AbilityStageEvent> AbilityEvents;
  if (AbilityStage.IsActive()) AbilityStage.Cut(Now, TEXT("reconnect"), CueDispatcher, Lines, AbilityEvents);
  WriteCueLines(Lines);
  // the final state at once: the stagings' held HP / falls are released (their visual events are dropped by Cut)
  RunCombatEvents(CombatEvents);
  RunAbilityEvents(AbilityEvents);
  // FX-36: the live systems fade out; the queued FX of the missed seqs never spawn
  const int32 Moves = FieldFx.Moves.Num(), Chevrons = FieldFx.Chevrons.Num();
  const int32 Stars = CombatFx.Stars.Num(), Heals = CombatFx.Heals.Num();
  FieldFx.Moves.Reset();
  FieldFx.Chevrons.Reset();
  if (FieldFx.LiveChevrons.IsValid()) FieldFx.LiveChevrons->Deactivate();
  CombatFx.Stars.Reset();
  CombatFx.Heals.Reset();
  const int32 Systems = CueFxSpawner ? CueFxSpawner->CutAllForReconnect(RecoveredSeq) : 0;
  FS08Trace::Write(FString::Printf(TEXT("FX reconnect recovered_seq=%d t=%lld src=%s systems=%d dropped=moves:%d,chevrons:%d,stars:%d,heals:%d"),
                                   RecoveredSeq, static_cast<long long>(Now), Src, Systems, Moves, Chevrons, Stars, Heals));
  S08FxStaleSeq = FMath::Max(S08FxStaleSeq, RecoveredSeq);
}

bool AS08FlowGameMode::S08FxStale(int32 Seq, const TCHAR* What) const {
  if (Seq < 0 || Seq > S08FxStaleSeq) return false;
  FS08Trace::Write(FString::Printf(TEXT("FX skip what=%s seq=%d reason=stale recovered_seq=%d"), What, Seq, S08FxStaleSeq));
  return true;
}

bool AS08FlowGameMode::S08FxBenchOutcome(const FString& Mode, const TArray<FString>& Parts) {
  // -BenchFx=outcome,<w>[,victory|defeat]  the FX-34 grade frozen at weight w (the outcome: the bench result's verdict,
  //                                         -BenchResult=board [-BenchResultLoser]; or named here)
  // -BenchFx=desat,<w>                      the FX-35 / FX-36 disconnect weight frozen at w (1 = lost, 1/3 = R0+200)
  if (Mode != TEXT("outcome") && Mode != TEXT("desat")) return false;
  if (!CuePostFx) S08FxOutcomeTick();
  if (!CuePostFx) return true;
  FS08CuePostProcessState& St = CuePostState;
  const float W = Parts.IsValidIndex(1) && Parts[1].IsNumeric() ? FMath::Clamp(FCString::Atof(*Parts[1]), 0.0f, 1.0f) : 1.0f;
  if (Mode == TEXT("outcome")) {
    St.BenchOutcomeW = W;
    if (Parts.IsValidIndex(2)) {
      St.Outcome = Parts[2] == TEXT("defeat") ? ES08Outcome::Defeat : ES08Outcome::Victory;
      St.OutcomeStartMs = NowMs();
    }
  } else {
    St.BenchDisconnectW = W;
  }
  const S08CuePostProcess::FSettings Set = St.Evaluate(NowMs());
  S08CuePostProcess::Apply(*CuePostFx, Set);
  FS08Trace::Write(FString::Printf(TEXT("FX bench %s w=%.3f outcome=%s sat=%.3f temp=%.0f vignette=%.3f"), *Mode, W,
                                   S08CuePostProcess::OutcomeName(St.Outcome), Set.Saturation, Set.WhiteTemp, Set.Vignette));
  return true;
}

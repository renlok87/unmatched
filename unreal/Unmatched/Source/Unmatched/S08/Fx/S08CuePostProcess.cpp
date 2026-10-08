// VS-6 F4 FX-34 / FX-35 / FX-36: see S08CuePostProcess.h.
#include "S08CuePostProcess.h"

#include "Engine/World.h"

namespace S08CuePostProcess {

const TCHAR* OutcomeName(ES08Outcome Outcome) {
  switch (Outcome) {
    case ES08Outcome::Victory: return TEXT("victory");
    case ES08Outcome::Defeat: return TEXT("defeat");
    default: return TEXT("none");
  }
}

float EaseInOut(float X) {
  const float T = FMath::Clamp(X, 0.0f, 1.0f);
  return T * T * (3.0f - 2.0f * T);
}

float OutcomeWeight(int64 NowMs, int64 StartMs, int32 BlendMs) {
  if (StartMs < 0 || NowMs < StartMs) return 0.0f;
  if (BlendMs <= 0) return 1.0f;
  return EaseInOut(static_cast<float>(NowMs - StartMs) / static_cast<float>(BlendMs));
}

float RestoreWeight(int64 NowMs, int64 StartMs, int32 Ms) {
  if (StartMs < 0 || NowMs <= StartMs) return 1.0f;
  if (Ms <= 0) return 0.0f;
  return FMath::Clamp(1.0f - static_cast<float>(NowMs - StartMs) / static_cast<float>(Ms), 0.0f, 1.0f);
}

FSettings Compose(ES08Outcome Outcome, float OutcomeW, float DisconnectW) {
  FSettings S;
  const float WO = Outcome == ES08Outcome::None ? 0.0f : FMath::Clamp(OutcomeW, 0.0f, 1.0f);
  const float WD = FMath::Clamp(DisconnectW, 0.0f, 1.0f);
  const float Target = Outcome == ES08Outcome::Victory ? VictoryWhiteTemp
                       : Outcome == ES08Outcome::Defeat ? DefeatWhiteTemp
                                                        : BaseWhiteTemp;
  S.WhiteTemp = BaseWhiteTemp + (Target - BaseWhiteTemp) * WO;
  const float OutcomeSat = Outcome == ES08Outcome::Defeat ? 1.0f - (1.0f - DefeatSaturation) * WO : 1.0f;
  S.Saturation = OutcomeSat * (1.0f - (1.0f - DisconnectSaturation) * WD);
  S.Vignette = BaseVignette + VignetteAdd * WO;
  S.bActive = WO > 0.0f || WD > 0.0f;
  return S;
}

}  // namespace S08CuePostProcess

bool FS08CuePostProcessState::StartOutcome(ES08Outcome InOutcome, int64 TMs, bool bReduced, const TCHAR* Src,
                                           const FString& FighterId, FString& OutLine) {
  OutLine.Reset();
  if (InOutcome == ES08Outcome::None || HasOutcome()) return false;
  Outcome = InOutcome;
  OutcomeStartMs = TMs;
  OutcomeBlendMs = bReduced ? S08CuePostProcess::ReducedMaxMs : S08CuePostProcess::OutcomeBlendMs;
  OutLine = FString::Printf(TEXT("FX grade outcome=%s t=%lld ms=%d reduced=%d src=%s fighter=%s"),
                            S08CuePostProcess::OutcomeName(Outcome), static_cast<long long>(TMs), OutcomeBlendMs,
                            bReduced ? 1 : 0, Src, FighterId.IsEmpty() ? TEXT("-") : *FighterId);
  return true;
}

bool FS08CuePostProcessState::Disconnect(int64 TMs, FString& OutLine) {
  if (bDisconnected && RestoreStartMs < 0) {
    OutLine = FString::Printf(TEXT("FX desat duplicate t=%lld"), static_cast<long long>(TMs));
    return false;
  }
  bDisconnected = true;
  RestoreStartMs = -1;  // a loss during the return: full weight again in this frame
  OutLine = FString::Printf(TEXT("FX desat on t=%lld sat=%.2f grade=%s"), static_cast<long long>(TMs),
                            S08CuePostProcess::DisconnectSaturation,
                            S08CuePostProcess::OutcomeName(HasOutcome() ? Outcome : ES08Outcome::None));
  return true;
}

bool FS08CuePostProcessState::Reconnect(int64 TMs, bool bReduced, int32 RecoveredSeq, FString& OutLine) {
  OutLine.Reset();
  if (!bDisconnected || RestoreStartMs >= 0) return false;
  RestoreStartMs = TMs;
  RestoreMsLen = bReduced ? S08CuePostProcess::ReducedMaxMs : S08CuePostProcess::RestoreMs;
  OutLine = FString::Printf(TEXT("FX desat off t=%lld ms=%d recovered_seq=%d"), static_cast<long long>(TMs),
                            RestoreMsLen, RecoveredSeq);
  return true;
}

float FS08CuePostProcessState::DisconnectWeight(int64 NowMs) const {
  if (BenchDisconnectW >= 0.0f) return BenchDisconnectW;
  if (!bDisconnected) return 0.0f;
  return RestoreStartMs < 0 ? 1.0f : S08CuePostProcess::RestoreWeight(NowMs, RestoreStartMs, RestoreMsLen);
}

float FS08CuePostProcessState::OutcomeWeightAt(int64 NowMs) const {
  if (BenchOutcomeW >= 0.0f) return Outcome == ES08Outcome::None ? 0.0f : BenchOutcomeW;
  return HasOutcome() ? S08CuePostProcess::OutcomeWeight(NowMs, OutcomeStartMs, OutcomeBlendMs) : 0.0f;
}

S08CuePostProcess::FSettings FS08CuePostProcessState::Evaluate(int64 NowMs) const {
  return S08CuePostProcess::Compose(Outcome, OutcomeWeightAt(NowMs), DisconnectWeight(NowMs));
}

ES08NetEvent FS08NetWatch::Tick(const FS08NetWatchInput& In) {
  if (!In.bStarted) {
    Reset();
    return ES08NetEvent::None;
  }
  if (!bLost) {
    if (In.bStreamReady) {
      bSeenReady = true;
      return ES08NetEvent::None;
    }
    if (!bSeenReady) return ES08NetEvent::None;  // the match start subscribes (HB-14: syncing, not lost)
    bLost = true;
    bReconnectFed = false;
    return ES08NetEvent::Lost;
  }
  if (In.bStreamReady && !In.bAwaitingRecovery) {
    bLost = false;
    return ES08NetEvent::Recovered;
  }
  return ES08NetEvent::None;
}

bool FS08NetWatch::OnApplied(bool bApply) {
  if (!bLost || !bApply) return false;
  bReconnectFed = true;
  return true;
}

namespace S08CuePostProcess {

APostProcessVolume* CreateVolume(UWorld& World) {
  FActorSpawnParameters Params;
  Params.ObjectFlags |= RF_Transient;
  APostProcessVolume* C = World.SpawnActor<APostProcessVolume>(FVector::ZeroVector, FRotator::ZeroRotator, Params);
  if (!C) return nullptr;
  C->bUnbound = true;
  C->Priority = Priority;
  C->BlendWeight = 1.0f;
  C->bEnabled = false;
  FPostProcessSettings& P = C->Settings;
  P.bOverride_WhiteTemp = true;
  P.WhiteTemp = BaseWhiteTemp;
  P.bOverride_ColorSaturation = true;
  P.ColorSaturation = FVector4(1.0f, 1.0f, 1.0f, 1.0f);
  P.bOverride_VignetteIntensity = true;
  P.VignetteIntensity = BaseVignette;
  return C;
}

void Apply(APostProcessVolume& Component, const FSettings& S) {
  if (!S.bActive) {
    Component.bEnabled = false;
    return;
  }
  Component.Settings.WhiteTemp = S.WhiteTemp;
  Component.Settings.ColorSaturation = FVector4(S.Saturation, S.Saturation, S.Saturation, 1.0f);
  Component.Settings.VignetteIntensity = S.Vignette;
  Component.bEnabled = true;
}

}  // namespace S08CuePostProcess

// VS-6 F2 (FX-21..FX-25, IC-49, the Z-2 leftovers): the combat FX adapter of AS08FlowGameMode - the hit star, the
// damage-0 rim, the heal (CUE-012 + motes + «+N»), the numbers of the art HUD damage widget, the FX capture hook and
// the -BenchFx combat modes. The game mode only calls the S08Fx* entry points (one line each, S08CombatFx.h).
#include "../S08FlowGameMode.h"

#include "Camera/CameraActor.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/PlayerController.h"
#include "NiagaraComponent.h"
#include "../S08ArtHudWidgets.h"
#include "../S08BoardActor.h"
#include "../S08FighterActor.h"
#include "../S08IconMotion.h"
#include "../S08TraceLog.h"
#include "S08CombatFx.h"
#include "S08CueFx.h"
#include "S08CueFxSpawner.h"
#include "S08FigureFxChannels.h"

namespace {
/** The viewpoint the camera quads face (the player camera; the board camera before the controller has one). */
FVector FxCameraLocation(UWorld* World, const AActor* BoardCamera) {
  if (World) {
    if (const APlayerController* PC = World->GetFirstPlayerController()) {
      if (PC->PlayerCameraManager) return PC->PlayerCameraManager->GetCameraLocation();
    }
  }
  return BoardCamera ? BoardCamera->GetActorLocation() : FVector(0.0f, 600.0f, 900.0f);
}

/** -BenchFx combat steps (spawned at the end of the warm-up, frozen at their ms; bench only). */
struct FCombatBench {
  struct FSpawn {
    FString Cue;
    FString FighterId;
    FString AttackerId;
    double Ms = 0.0;
  };
  TArray<FSpawn> Spawns;
  bool bSpawned = false;
};
FCombatBench GCombatBench;
}  // namespace

void AS08FlowGameMode::S08FxHit(const FString& TargetId, int32 Seq, bool bStaged) {
  // FX-21 / FX-23 (ВР-21, ВР-FX05): every damage shows the star at C+70 - staged (the contact frame) or not (an ability,
  // exhaustion, a cascade); reduced motion and -S08FxLegacy show none; one star per target in a frame (CMB-HIT-MULTI)
  if (TargetId.IsEmpty() || !BoardActor) return;
  const bool bReduced = S08IconMotion::IsReducedMotion();
  const uint64* Frame = CombatFx.StarFrame.Find(TargetId);
  const bool bRepeat = Frame && *Frame == GFrameCounter;
  // the attacker of the staging (the shift towards it); none out of a combat (ВР-FX04)
  const FS09CombatStageInput& In = CombatStage.GetInput();
  const FString Attacker = bStaged && In.TargetId == TargetId ? In.AttackerId : FString();
  const TCHAR* Skip = !S08CueFx::FxEnabled() ? TEXT("legacy") : bReduced ? TEXT("reduced") : bRepeat ? TEXT("same-frame")
                                                                                                  : nullptr;
  FS08Trace::Write(FString::Printf(TEXT("FX star plan fighter=%s seq=%d staged=%d attacker=%s at=+%d%s%s"), *TargetId,
                                   Seq, bStaged ? 1 : 0, Attacker.IsEmpty() ? TEXT("-") : *Attacker,
                                   FMath::RoundToInt(S08CombatFx::StarDelayMs), Skip ? TEXT(" skip=") : TEXT(""),
                                   Skip ? Skip : TEXT("")));
  if (bStaged && S08CombatFx::FxShotsRequested() && !S09ShotDir.IsEmpty()) {
    // the capture hook: the 1st staged hit holds its flash (C+20), the 2nd its star frame 4 (C+137, the rim on)
    ++CombatFx.StagedHits;
    const TCHAR* Leaf = CombatFx.StagedHits == 1 ? TEXT("s09-fx19-flash-c20.png")
                        : CombatFx.StagedHits == 2 && !Skip ? TEXT("s09-fx21-star-c137.png")
                                                            : nullptr;
    if (Leaf && !CombatFx.ShotsTaken.Contains(Leaf)) {
      CombatFx.ShotsTaken.Add(Leaf);
      const double Dt = CombatFx.StagedHits == 1 ? S08CombatFx::ShotFlashMs : S08CombatFx::ShotStarMs;
      CombatFx.Shots.Add({Leaf, TargetId, static_cast<double>(NowMs()) + Dt});
    }
  }
  if (Skip) return;
  CombatFx.StarFrame.Add(TargetId, GFrameCounter);
  CombatFx.Stars.Add({TargetId, Attacker, Seq, static_cast<double>(NowMs()) + S08CombatFx::StarDelayMs});
}

void AS08FlowGameMode::S08FxBlock(const FString& TargetId, int32 Seq) {
  // FX-23 (ВР-FX05): damage 0 - the cream rim 300 ms of the target (FX-17's pulse without its event delay), no flash,
  // no star: «обод = защита»
  if (TargetId.IsEmpty() || !BoardActor || !S08CueFx::FxEnabled()) return;
  AS08FighterActor* Actor = BoardActor->FindFighterActor(TargetId);
  if (!Actor || Actor->IsInDeathHold()) return;
  S08FigureFx::FRimPulse Pulse = S08FigureFx::DefenseRim;
  Pulse.DelayMs = 0.0;
  Actor->PlayRimPulse(Pulse);
  FS08Trace::Write(FString::Printf(TEXT("FX block-rim fighter=%s seq=%d ms=%d"), *TargetId, Seq,
                                   FMath::RoundToInt(Pulse.TotalMs)));
}

void AS08FlowGameMode::S08FxHealCue(const FString& FighterId, int32 Amount, int32 Seq) {
  // FX-25 (ВР-FX13): the snapshot frame + 200 ms; a staging of the same seq holds it to its end (S08FxCombatEnd)
  if (FighterId.IsEmpty() || Amount <= 0) return;
  CombatFx.Heals.Add({FighterId, Amount, Seq, static_cast<double>(NowMs()) + S08CombatFx::HealDelayMs});
  FS08Trace::Write(FString::Printf(TEXT("FX heal plan fighter=%s amount=%d seq=%d staged=%d"), *FighterId, Amount, Seq,
                                   CombatStage.IsActive() && CombatStage.GetSeq() == Seq ? 1 : 0));
}

void AS08FlowGameMode::S08FxCombatEnd(int32 Seq) {
  const double Now = static_cast<double>(NowMs());
  for (FS08CombatFxState::FPendingHeal& H : CombatFx.Heals) {
    if (H.Seq == Seq) H.AtMs = FMath::Min(H.AtMs, Now);  // stage=end: due now
  }
  S08FxCombatTick();
}

void AS08FlowGameMode::S08FxShowNumber(US08ArtDamageWidget& Widget, const FString& FighterId, int32 Amount, int32 Seq) {
  // FX-22: the life of the board's number (900 x speed / 700 / reduced 450); the widget animates itself
  const int32 Life = BoardActor ? BoardActor->GetDamageNumberLifeMs(FighterId) : 0;
  const bool bReduced = S08IconMotion::IsReducedMotion();
  Widget.ShowNumber(FighterId, Amount, Seq,
                    Life > 0 ? Life : S08CombatFx::NumberLifeMs(Amount < 0, 900, bReduced), bReduced);
}

void AS08FlowGameMode::S08FxCombatTick() {
  if (!BoardActor) return;
  UWorld* World = GetWorld();
  const double Now = static_cast<double>(NowMs());
  const bool bReduced = S08IconMotion::IsReducedMotion();
  // ---- FX-21: the due stars
  for (int32 I = 0; I < CombatFx.Stars.Num();) {
    const FS08CombatFxState::FPendingStar S = CombatFx.Stars[I];
    if (Now < S.AtMs) {
      ++I;
      continue;
    }
    CombatFx.Stars.RemoveAt(I);
    const AS08FighterActor* T = BoardActor->FindFighterActor(S.TargetId);
    const AS08FighterActor* A = S.AttackerId.IsEmpty() ? nullptr : BoardActor->FindFighterActor(S.AttackerId);
    if (!T || !CueFxSpawner) continue;
    const FVector Base = T->GetActorLocation();
    const FVector ABase = A ? A->GetActorLocation() : FVector::ZeroVector;
    const float H = T->GetFigureHeightUU();
    const FVector P = S08CombatFx::StarPoint(Base, H, T->GetClickRadiusUU(), A ? &ABase : nullptr);
    const float Side = S08CombatFx::StarQuadSideUU(H);
    UNiagaraComponent* C =
        CueFxSpawner->Spawn(TEXT("CUE-011"), S08CombatFx::CameraQuad(P, FxCameraLocation(World, BoardCamera), Side));
    if (C) CombatFx.LiveSystems.Add(C);
    FS08Trace::Write(FString::Printf(TEXT("FX star fighter=%s seq=%d at=(%.0f,%.0f,%.0f) side=%.0f diameter=%.0f result=%s"),
                                     *S.TargetId, S.Seq, P.X, P.Y, P.Z, Side, S08CombatFx::StarDiameterRel * H,
                                     C ? TEXT("spawned") : TEXT("missing")));
  }
  // ---- FX-25: the due heals (not before the end of a staging of their seq)
  for (int32 I = 0; I < CombatFx.Heals.Num();) {
    const FS08CombatFxState::FPendingHeal Heal = CombatFx.Heals[I];
    const bool bStaged = CombatStage.IsActive() && CombatStage.GetSeq() == Heal.Seq;
    if (Now < Heal.AtMs || bStaged) {
      ++I;
      continue;
    }
    CombatFx.Heals.RemoveAt(I);
    TArray<FString> Lines;
    const bool bAfterCombat = CombatStage.GetSeq() == Heal.Seq;
    CueDispatcher.Feed(TEXT("CUE-012"), Heal.FighterId, Heal.Seq, NowMs(), Lines, 0, -1, /*bStaged=*/bAfterCombat);
    WriteCueLines(Lines);
    BoardActor->ShowDamageNumber(Heal.FighterId, -Heal.Amount, Heal.Seq,
                                 S08CombatFx::NumberLifeMs(true, 0, bReduced) / 1000.0f);  // FX-22 «+N»
    AS08FighterActor* F = BoardActor->FindFighterActor(Heal.FighterId);
    UNiagaraComponent* Motes = nullptr;
    if (F && CueFxSpawner && S08CueFx::FxEnabled() && !bReduced) {
      const float H = F->GetFigureHeightUU();
      const float Side = S08CombatFx::HealQuadSideUU(H);
      const FVector Cam = FxCameraLocation(World, BoardCamera);
      const FTransform Xf =
          S08CombatFx::CameraQuad(S08CombatFx::HealQuadCentre(F->GetActorLocation(), Cam, Side), Cam, Side);
      Motes = CueFxSpawner->Spawn(TEXT("CUE-012"), Xf, F->GetRootComponent());
      if (Motes) {
        // attached to the figure (cue-table: socket Base) but facing the camera: the world rotation and size stay
        Motes->SetUsingAbsoluteRotation(true);
        Motes->SetUsingAbsoluteScale(true);
        Motes->SetWorldRotation(Xf.GetRotation());
        Motes->SetWorldScale3D(Xf.GetScale3D());
        CombatFx.LiveSystems.Add(Motes);
      }
    }
    FS08Trace::Write(FString::Printf(TEXT("FX heal fighter=%s amount=%d seq=%d afterCombat=%d motes=%s"), *Heal.FighterId,
                                     Heal.Amount, Heal.Seq, bAfterCombat ? 1 : 0,
                                     Motes ? TEXT("spawned") : (bReduced ? TEXT("reduced") : TEXT("none"))));
    if (S08CombatFx::FxShotsRequested() && !S09ShotDir.IsEmpty() && !CombatFx.ShotsTaken.Contains(TEXT("s09-fx25-heal.png"))) {
      CombatFx.ShotsTaken.Add(TEXT("s09-fx25-heal.png"));
      CombatFx.Shots.Add({TEXT("s09-fx25-heal.png"), Heal.FighterId, Now + S08CombatFx::ShotHealMs});
    }
  }
  CombatFx.LiveSystems.RemoveAll([](const TWeakObjectPtr<UNiagaraComponent>& C) { return !C.IsValid() || !C->IsActive(); });
  // ---- the FX capture hook: hold the channels (and pause the systems) until the evidence frame is written
  auto Pause = [this](bool bOn) {
    for (const TWeakObjectPtr<UNiagaraComponent>& C : CombatFx.LiveSystems) {
      if (C.IsValid()) C->SetPaused(bOn);
    }
  };
  if (!CombatFx.Holding.Leaf.IsEmpty()) {
    const bool bDone = GFrameCounter >= CombatFx.HoldFrame + 3 && !IsEvidenceCaptureBusy() && EvidenceShotQueue.Num() == 0;
    const bool bTimeout = FPlatformTime::Seconds() - CombatFx.HoldSinceS > 3.0;
    if (bDone || bTimeout) {
      if (AS08FighterActor* F = BoardActor->FindFighterActor(CombatFx.Holding.FighterId)) F->HoldFx(false);
      Pause(false);
      FS08Trace::Write(FString::Printf(TEXT("FXSHOT release %s frames=%llu timeout=%d"), *CombatFx.Holding.Leaf,
                                       static_cast<unsigned long long>(GFrameCounter - CombatFx.HoldFrame),
                                       bTimeout ? 1 : 0));
      CombatFx.Holding = FS08CombatFxState::FShot();
    }
    return;
  }
  for (int32 I = 0; I < CombatFx.Shots.Num(); ++I) {
    if (Now < CombatFx.Shots[I].AtMs) continue;
    CombatFx.Holding = CombatFx.Shots[I];
    CombatFx.Shots.RemoveAt(I);
    AS08FighterActor* F = BoardActor->FindFighterActor(CombatFx.Holding.FighterId);
    if (F) F->HoldFx(true);
    Pause(true);
    CombatFx.HoldFrame = GFrameCounter;
    CombatFx.HoldSinceS = FPlatformTime::Seconds();
    FS08Trace::Write(FString::Printf(TEXT("FXSHOT hold %s fighter=%s systems=%d"), *CombatFx.Holding.Leaf,
                                     *CombatFx.Holding.FighterId, CombatFx.LiveSystems.Num()));
    TakeEvidenceShot(S09ShotDir / CombatFx.Holding.Leaf);
    break;
  }
}

void AS08FlowGameMode::S08FxDefenseShot(const FString& DefenderId) {
  // the capture hook of FX-17: the defense rim at its peak (t0 = event + 150, +120)
  if (!S08CombatFx::FxShotsRequested() || S09ShotDir.IsEmpty() || DefenderId.IsEmpty()) return;
  const TCHAR* Leaf = TEXT("s09-fx17-defense-rim.png");
  if (CombatFx.ShotsTaken.Contains(Leaf)) return;
  CombatFx.ShotsTaken.Add(Leaf);
  CombatFx.Shots.Add({Leaf, DefenderId, static_cast<double>(NowMs()) + S08CombatFx::ShotDefenseMs});
}

bool AS08FlowGameMode::S08FxBenchCombat(const FString& Mode, const TArray<FString>& Parts) {
  // -BenchFx (VS-6 F2) combat modes, ';' between steps:
  //   star,<target>,<ms>[,<attacker>]   FX-21 NS_FX_HitStar frozen at <ms> after its spawn (C+70 + ms)
  //   heal,<fighter>,<ms>               FX-24 NS_FX_HealMotes frozen at <ms>
  if (Mode != TEXT("star") && Mode != TEXT("heal")) return false;
  if (Parts.Num() < 3 || !BoardActor || !BoardActor->FindFighterActor(Parts[1])) return false;
  FCombatBench::FSpawn S;
  S.Cue = Mode == TEXT("star") ? TEXT("CUE-011") : TEXT("CUE-012");
  S.FighterId = Parts[1];
  S.Ms = FCString::Atod(*Parts[2]);
  S.AttackerId = Parts.IsValidIndex(3) ? Parts[3] : FString();
  GCombatBench.Spawns.Add(S);
  FS08Trace::Write(FString::Printf(TEXT("FX bench %s fighter=%s ms=%.0f queued"), *Mode, *S.FighterId, S.Ms));
  return true;
}

void AS08FlowGameMode::S08FxBenchCombatFinish() {
  if (GCombatBench.bSpawned || !BoardActor || !CueFxSpawner) return;
  GCombatBench.bSpawned = true;
  const FVector Cam = FxCameraLocation(GetWorld(), BoardCamera);
  for (const FCombatBench::FSpawn& S : GCombatBench.Spawns) {
    const AS08FighterActor* F = BoardActor->FindFighterActor(S.FighterId);
    if (!F) continue;
    const float H = F->GetFigureHeightUU();
    FTransform Xf;
    if (S.Cue == TEXT("CUE-011")) {
      const AS08FighterActor* A = S.AttackerId.IsEmpty() ? nullptr : BoardActor->FindFighterActor(S.AttackerId);
      const FVector ABase = A ? A->GetActorLocation() : FVector::ZeroVector;
      const FVector P = S08CombatFx::StarPoint(F->GetActorLocation(), H, F->GetClickRadiusUU(), A ? &ABase : nullptr);
      Xf = S08CombatFx::CameraQuad(P, Cam, S08CombatFx::StarQuadSideUU(H));
    } else {
      const float Side = S08CombatFx::HealQuadSideUU(H);
      Xf = S08CombatFx::CameraQuad(S08CombatFx::HealQuadCentre(F->GetActorLocation(), Cam, Side), Cam, Side);
    }
    UNiagaraComponent* C = CueFxSpawner->Spawn(S.Cue, Xf);
    if (C) {
      // frozen at <ms>: the CPU simulation advanced in 1/60 s ticks, then paused (deterministic, FX-04)
      const int32 Ticks = FMath::Max(1, FMath::RoundToInt(S.Ms / (1000.0 / 60.0)));
      C->AdvanceSimulation(Ticks, 1.0f / 60.0f);
      C->SetPaused(true);
    }
    FS08Trace::Write(FString::Printf(TEXT("FX bench spawn cue=%s fighter=%s ms=%.0f side=%.0f result=%s"), *S.Cue,
                                     *S.FighterId, S.Ms, Xf.GetScale3D().X * S08CombatFx::PlaneUU,
                                     C ? TEXT("spawned") : TEXT("missing")));
  }
}

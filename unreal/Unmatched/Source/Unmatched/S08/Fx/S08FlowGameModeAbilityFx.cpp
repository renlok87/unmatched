// VS-6 F3 (FX-26, FX-27, FX-28, FX-30, FX-32): the death and ability FX adapter of AS08FlowGameMode - the embers of
// the ash death, the staging of Medusa's gaze (FS09AbilityStage) with her vortex, Arthur's arc at the flip of his
// boosted attack, the capture hook leaves and the -BenchFx ash / vortex / arc modes. The game mode only calls the
// S08FxAbility* entry points (one line each; S08AbilityFx.h).
#include "../S08FlowGameMode.h"

#include "Camera/CameraActor.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/PlayerController.h"
#include "Misc/Parse.h"
#include "NiagaraComponent.h"
#include "../S08BoardActor.h"
#include "../S08FighterActor.h"
#include "../S08HeroesV2.h"
#include "../S08IconMotion.h"
#include "../S08TraceLog.h"
#include "S08AbilityFx.h"
#include "S08CombatFx.h"
#include "S08CueFx.h"
#include "S08CueFxSpawner.h"

namespace {
/** The viewpoint the camera quads face (the player camera; the board camera before the controller has one). */
FVector AbilityCameraLocation(UWorld* World, const AActor* BoardCamera) {
  if (World) {
    if (const APlayerController* PC = World->GetFirstPlayerController()) {
      if (PC->PlayerCameraManager) return PC->PlayerCameraManager->GetCameraLocation();
    }
  }
  return BoardCamera ? BoardCamera->GetActorLocation() : FVector(0.0f, 600.0f, 900.0f);
}

/** The world location and the blade axis of the Weapon socket of a v2 figure (the actor's centre at 0.6 H without
 *  one). ВР-VS6-27: the blade axis is the socket axis closest to the world vertical (the rig's weapon bones do not share
 *  one convention - on Arthur's v2 rig the socket X lies across the raised blade and tilted every arc to the 45 deg
 *  clamp); the arc then leans with the blade's lean only. */
bool WeaponSocket(const AS08FighterActor& F, FVector& OutLocation, FVector& OutAxis) {
  const USkeletalMeshComponent* Body = F.GetArtBodyComponent();
  if (Body && Body->DoesSocketExist(TEXT("Weapon"))) {
    const FTransform X = Body->GetSocketTransform(TEXT("Weapon"), RTS_World);
    OutLocation = X.GetLocation();
    OutAxis = X.GetUnitAxis(EAxis::X);
    for (const EAxis::Type A : {EAxis::Y, EAxis::Z}) {
      const FVector V = X.GetUnitAxis(A);
      if (FMath::Abs(V.Z) > FMath::Abs(OutAxis.Z)) OutAxis = V;
    }
    return true;
  }
  OutLocation = F.GetActorLocation() + FVector(0.0f, 0.0f, 0.6f * F.GetFigureHeightUU());
  OutAxis = FVector::UpVector;
  return false;
}
}  // namespace

// ---------------------------------------------------------------- FX-28 / FX-30: Medusa's gaze

void AS08FlowGameMode::S08FxAbilityCues(const TArray<FS08Cue>& Cues) {
  for (const FS08Cue& Cue : Cues) {
    if (Cue.Type != ES08CueType::AbilityTriggered) continue;
    if (S08FxStale(Cue.SequenceNumber, TEXT("ability"))) continue;  // VS-6 FX-36: a missed gaze is not staged
    FS09AbilityStageInput In;
    In.Seq = Cue.SequenceNumber;
    In.HeroKey = Cue.HeroKey;
    In.FighterId = Cue.FighterId;
    In.TargetId = Cue.TargetId;
    In.Damage = Cue.Damage;
    In.HpBefore = Cue.TargetHpBefore;
    In.HpAfter = Cue.TargetHpBefore >= 0 ? FMath::Max(0, Cue.TargetHpBefore - Cue.Damage) : -1;
    In.bLethal = Cue.Damage > 0 && In.HpAfter == 0;
    In.TargetX = Cue.FromX;
    In.TargetY = Cue.FromY;
    In.bReducedMotion = S08IconMotion::IsReducedMotion();
    TArray<FString> Lines;
    TArray<FS09AbilityStageEvent> Events;
    if (In.bReducedMotion != CueDispatcher.IsReducedMotion()) CueDispatcher.SetReducedMotion(In.bReducedMotion, NowMs(), Lines);
    const bool bStarted = AbilityStage.Start(In, NowMs(), CueDispatcher, Lines, Events);
    FS08Trace::Write(FString::Printf(TEXT("FX ability plan hero=%s fighter=%s target=%s seq=%d damage=%d lethal=%d "
                                          "reduced=%d started=%d"),
                                     *In.HeroKey, *In.FighterId, *In.TargetId, In.Seq, In.Damage, In.bLethal ? 1 : 0,
                                     In.bReducedMotion ? 1 : 0, bStarted ? 1 : 0));
    WriteCueLines(Lines);
    RunAbilityEvents(Events);
  }
}

bool AS08FlowGameMode::S08FxAbilityHoldsDamage(const FS08Cue& Cue) const {
  return Cue.Type == ES08CueType::FighterDamaged && AbilityStage.HoldsDamage(Cue.FighterId, Cue.SequenceNumber);
}

void AS08FlowGameMode::RunAbilityEvents(const TArray<FS09AbilityStageEvent>& Events) {
  const FS09AbilityStageInput& In = AbilityStage.GetInput();
  for (const FS09AbilityStageEvent& Event : Events) {
    switch (Event.Type) {
      case ES09AbilityEvent::Vortex: {
        // FX-30: NS_FX_MedusaVortex on the hero's root (cue-table socket Root), 600 ms, not scaled by the speed
        AS08FighterActor* Hero = BoardActor ? BoardActor->FindFighterActor(In.FighterId) : nullptr;
        UNiagaraComponent* C = nullptr;
        if (Hero && CueFxSpawner && S08CueFx::FxEnabled()) {
          const FTransform Xf = S08AbilityFx::VortexTransform(Hero->GetActorLocation(), Hero->GetFigureHeightUU(),
                                                              AbilityCameraLocation(GetWorld(), BoardCamera.Get()));
          C = CueFxSpawner->Spawn(TEXT("CUE-014"), Xf, Hero->GetRootComponent(), In.HeroKey);
          if (C) {
            C->SetUsingAbsoluteRotation(true);
            C->SetUsingAbsoluteScale(true);
            C->SetWorldRotation(Xf.GetRotation());
            C->SetWorldScale3D(Xf.GetScale3D());
            CombatFx.LiveSystems.Add(C);
          }
        }
        FS08Trace::Write(FString::Printf(TEXT("FX vortex fighter=%s seq=%d t=%lld result=%s"), *In.FighterId, In.Seq,
                                         static_cast<long long>(Event.AtMs),
                                         C ? TEXT("spawned") : (S08CueFx::FxEnabled() ? TEXT("missing") : TEXT("legacy"))));
        if (S08CombatFx::FxShotsRequested() && !S09ShotDir.IsEmpty() && !CombatFx.ShotsTaken.Contains(TEXT("s09-fx30-vortex-t300.png"))) {
          CombatFx.ShotsTaken.Add(TEXT("s09-fx30-vortex-t300.png"));
          CombatFx.Shots.Add({TEXT("s09-fx30-vortex-t300.png"), In.FighterId, static_cast<double>(Event.AtMs) + 300.0});
        }
        break;
      }
      case ES09AbilityEvent::Contact:
        // the FX-23 set without a lunge: white flash + cream rim, the hit star at C+70, HitReact, the hit sound
        if (In.Damage > 0) PresentHit(In.TargetId, In.Seq, AbilityStage.GetHitTintMs(), Event.AtMs);
        break;
      case ES09AbilityEvent::Minus:
        if (In.Damage > 0) {
          PresentDamageNumber(In.TargetId, In.Damage, In.Seq, FS09CombatStage::MinusLifeMsAt(1.0f) / 1000.0f);
        }
        break;
      case ES09AbilityEvent::Hp:
      case ES09AbilityEvent::Fall:
        RefreshShownFighters(true);
        break;
      case ES09AbilityEvent::End:
        RefreshShownFighters(true);
        RefreshHud();
        break;
    }
  }
}

// ---------------------------------------------------------------- FX-28 / FX-32: Arthur's arc

void AS08FlowGameMode::S08FxAbilityOnCombatEvent(const FS09CombatStageEvent& Event) {
  const FS09CombatStageInput& In = CombatStage.GetInput();
  if (Event.Type != ES09CombatEvent::FlipAttack || !In.bAbilityBoost) return;
  // ВР-FX10: Arthur's ability is the boost of his attack - CUE-014 in the frame the attack card turns
  TArray<FString> Lines;
  CueDispatcher.Feed(TEXT("CUE-014"), In.AttackerId, In.Seq, Event.AtMs, Lines);
  WriteCueLines(Lines);
  AS08FighterActor* Arthur = BoardActor ? BoardActor->FindFighterActor(In.AttackerId) : nullptr;
  const bool bReduced = S08IconMotion::IsReducedMotion();
  const float Dilation = S08AbilityFx::ArcTimeDilation(In.SpeedMul);
  const TCHAR* Skip = !S08CueFx::FxEnabled() ? TEXT("legacy") : bReduced ? TEXT("reduced")
                      : Dilation <= 0.0f    ? TEXT("speed-none") : !Arthur ? TEXT("no-figure") : nullptr;
  UNiagaraComponent* C = nullptr;
  float Tilt = 0.0f;
  bool bSocket = false;
  if (!Skip && CueFxSpawner) {
    FVector Loc, Axis;
    bSocket = WeaponSocket(*Arthur, Loc, Axis);
    const FVector Cam = AbilityCameraLocation(GetWorld(), BoardCamera.Get());
    Tilt = S08AbilityFx::ArcTiltDeg(Loc, Axis, Cam);
    const FTransform Xf = S08AbilityFx::ArcQuad(Loc, Arthur->GetFigureHeightUU(), Cam);
    USceneComponent* Parent = Arthur->GetArtBodyComponent();
    C = CueFxSpawner->Spawn(TEXT("CUE-014"), Xf, Parent ? Parent : Arthur->GetRootComponent(), TEXT("KingArthur"));
    if (C) {
      // on the hand (SpawnSystemAttached at Weapon), but facing the camera at the card's size
      C->SetUsingAbsoluteRotation(true);
      C->SetUsingAbsoluteScale(true);
      C->SetWorldRotation(Xf.GetRotation());
      C->SetWorldScale3D(Xf.GetScale3D());
      C->SetTranslucentSortPriority(S08AbilityFx::ArcSortPriority);
      C->SetCustomTimeDilation(Dilation);  // 400 ms x speed
      C->SetVariableFloat(S08AbilityFx::ArcTiltParam, Tilt);
      CombatFx.LiveSystems.Add(C);
    }
  }
  FS08Trace::Write(FString::Printf(TEXT("FX arc fighter=%s seq=%d t=%lld socket=%s tilt=%.1f dilation=%.2f result=%s"),
                                   *In.AttackerId, In.Seq, static_cast<long long>(Event.AtMs),
                                   bSocket ? TEXT("Weapon") : TEXT("-"), Tilt, Dilation,
                                   C ? TEXT("spawned") : Skip ? Skip : TEXT("missing")));
  if (C && S08CombatFx::FxShotsRequested() && !S09ShotDir.IsEmpty() &&
      !CombatFx.ShotsTaken.Contains(TEXT("s09-fx32-arc-f133.png"))) {
    CombatFx.ShotsTaken.Add(TEXT("s09-fx32-arc-f133.png"));
    CombatFx.Shots.Add({TEXT("s09-fx32-arc-f133.png"), In.AttackerId,
                        static_cast<double>(Event.AtMs) + 133.0 * FMath::Max(In.SpeedMul, 0.01f)});
  }
}

// ---------------------------------------------------------------- the frame tick: the gaze staging, the embers

void AS08FlowGameMode::S08FxAbilityTick() {
  {
    TArray<FString> Lines;
    TArray<FS09AbilityStageEvent> Events;
    AbilityStage.Tick(NowMs(), CueDispatcher, Lines, Events);
    WriteCueLines(Lines);
    RunAbilityEvents(Events);
  }
  if (!BoardActor) return;
  // FX-26 / FX-27: the embers spawn in the first frame a figure dissolves and follow its front every frame
  const bool bReduced = S08IconMotion::IsReducedMotion();
  TSet<FString> Dissolving;
  for (const FS08BoardFighter& F : Fighters) {
    AS08FighterActor* A = BoardActor->FindFighterActor(F.Id);
    if (!A || !A->IsDissolving()) continue;
    Dissolving.Add(F.Id);
    if (!AbilityFx.WasDissolving.Contains(F.Id)) {
      S08HeroesV2::FDeathPlan Plan;
      FString Style;
      A->GetDeathPlan(Plan, Style);
      const S08AbilityFx::EEmbersSkip Skip = S08AbilityFx::EmbersDecision(
          Style == TEXT("ash") ? S08HeroesV2::EDissolveStyle::Ash : S08HeroesV2::EDissolveStyle::Fade,
          Style != TEXT("none"), S08CueFx::FxEnabled(), bReduced);
      UNiagaraComponent* C = nullptr;
      if (Skip == S08AbilityFx::EEmbersSkip::None && CueFxSpawner) {
        const FTransform Xf = S08AbilityFx::EmbersQuad(A->GetActorLocation(), A->GetFigureHeightUU(),
                                                       A->GetClickRadiusUU(), AbilityCameraLocation(GetWorld(), BoardCamera.Get()));
        C = CueFxSpawner->Spawn(TEXT("CUE-013"), Xf);
        if (C) {
          C->SetVariableLinearColor(S08AbilityFx::TeamColorParam, S08AbilityFx::EmberTeamColor(A->GetLook()));
          C->SetVariableFloat(S08AbilityFx::DissolveMsParam, Plan.DissolveSeconds * 1000.0f);
          C->SetVariableFloat(S08AbilityFx::FrontHeightParam, A->GetDissolveProgress());
          AbilityFx.Embers.Add(F.Id, C);
          CombatFx.LiveSystems.Add(C);
        }
      }
      FS08Trace::Write(FString::Printf(TEXT("FX embers fighter=%s t=%lld dissolve=%d count=%d look=%s result=%s%s"),
                                       *F.Id, static_cast<long long>(NowMs()),
                                       FMath::RoundToInt(Plan.DissolveSeconds * 1000.0f),
                                       C ? S08AbilityFx::EmberCount(Plan.DissolveSeconds) : 0,
                                       S08TeamSlotName(A->GetLook()),
                                       C ? TEXT("spawned") : Skip == S08AbilityFx::EEmbersSkip::None ? TEXT("missing") : TEXT("skip"),
                                       Skip == S08AbilityFx::EEmbersSkip::None
                                           ? TEXT("")
                                           : *(FString(TEXT(" reason=")) + S08AbilityFx::EmbersSkipName(Skip))));
      if (C && S08CombatFx::FxShotsRequested() && !S09ShotDir.IsEmpty() &&
          !CombatFx.ShotsTaken.Contains(TEXT("s09-fx26-embers-d300.png"))) {
        CombatFx.ShotsTaken.Add(TEXT("s09-fx26-embers-d300.png"));
        CombatFx.Shots.Add({TEXT("s09-fx26-embers-d300.png"), F.Id, static_cast<double>(NowMs()) + 300.0});
      }
    }
    if (const TWeakObjectPtr<UNiagaraComponent>* C = AbilityFx.Embers.Find(F.Id)) {
      if (C->IsValid()) (*C)->SetVariableFloat(S08AbilityFx::FrontHeightParam, A->GetDissolveProgress());
    }
  }
  // a figure gone: its embers live out their 600 ms (the front stays at the top - FrontHeight 1)
  for (auto It = AbilityFx.Embers.CreateIterator(); It; ++It) {
    if (!Dissolving.Contains(It.Key())) {
      if (It.Value().IsValid()) It.Value()->SetVariableFloat(S08AbilityFx::FrontHeightParam, 1.0f);
      It.RemoveCurrent();
    }
  }
  AbilityFx.WasDissolving = MoveTemp(Dissolving);
}

// ---------------------------------------------------------------- -BenchFx ash / vortex / arc, -BenchFocusFighter

bool AS08FlowGameMode::S08FxBenchAbility(const FString& Mode, const TArray<FString>& Parts) {
  //   ash,<fighter>,<ms>     FX-26 the figure's dissolve frozen at ms / its dissolve length + NS_FX_AshEmbers at ms
  //   vortex,<fighter>,<ms>  FX-30 NS_FX_MedusaVortex on the fighter's root frozen at ms
  //   arc,<fighter>,<ms>     FX-32 NS_FX_ArthurArc at the fighter's Weapon socket frozen at ms
  if (Mode != TEXT("ash") && Mode != TEXT("vortex") && Mode != TEXT("arc")) return false;
  if (Parts.Num() < 3 || !BoardActor || !BoardActor->FindFighterActor(Parts[1])) return false;
  FS08AbilityFxState::FBenchSpawn S;
  S.Mode = Mode;
  S.FighterId = Parts[1];
  S.Ms = FCString::Atod(*Parts[2]);
  AbilityFx.Bench.Add(S);
  FS08Trace::Write(FString::Printf(TEXT("FX bench %s fighter=%s ms=%.0f queued"), *Mode, *S.FighterId, S.Ms));
  return true;
}

void AS08FlowGameMode::S08FxBenchAbilityFinish() {
  if (AbilityFx.bBenchSpawned || !BoardActor || !CueFxSpawner) return;
  AbilityFx.bBenchSpawned = true;
  const FVector Cam = AbilityCameraLocation(GetWorld(), BoardCamera.Get());
  for (const FS08AbilityFxState::FBenchSpawn& S : AbilityFx.Bench) {
    AS08FighterActor* F = BoardActor->FindFighterActor(S.FighterId);
    if (!F) continue;
    const float H = F->GetFigureHeightUU();
    UNiagaraComponent* C = nullptr;
    FString Extra;
    if (S.Mode == TEXT("ash")) {
      const S08HeroesV2::FHeroSpec* Spec = F->GetHeroV2Spec();
      const float DissolveS = Spec ? S08HeroesV2::DissolveSeconds(*Spec) : 0.5f;
      const float Progress = FMath::Clamp(static_cast<float>(S.Ms / (DissolveS * 1000.0f)), 0.0f, 1.0f);
      const bool bMic = F->BenchDissolveAt(Progress);
      Extra = FString::Printf(TEXT(" progress=%.2f mic=%d style=%s"), Progress, bMic ? 1 : 0,
                              S08HeroesV2::DissolveStyleName(S08HeroesV2::DissolveStyle()));
      if (S08HeroesV2::DissolveStyle() == S08HeroesV2::EDissolveStyle::Ash) {
        C = CueFxSpawner->Spawn(TEXT("CUE-013"), S08AbilityFx::EmbersQuad(F->GetActorLocation(), H,
                                                                          F->GetClickRadiusUU(), Cam));
        if (C) {
          C->SetVariableLinearColor(S08AbilityFx::TeamColorParam, S08AbilityFx::EmberTeamColor(F->GetLook()));
          C->SetVariableFloat(S08AbilityFx::DissolveMsParam, DissolveS * 1000.0f);
          C->SetVariableFloat(S08AbilityFx::FrontHeightParam, Progress);
        }
      }
    } else if (S.Mode == TEXT("vortex")) {
      const FTransform Xf = S08AbilityFx::VortexTransform(F->GetActorLocation(), H, Cam);
      C = CueFxSpawner->Spawn(TEXT("CUE-014"), Xf, nullptr, TEXT("Medusa"));
    } else {
      FVector Loc, Axis;
      const bool bSocket = WeaponSocket(*F, Loc, Axis);
      const float Tilt = S08AbilityFx::ArcTiltDeg(Loc, Axis, Cam);
      C = CueFxSpawner->Spawn(TEXT("CUE-014"), S08AbilityFx::ArcQuad(Loc, H, Cam), nullptr, TEXT("KingArthur"));
      if (C) {
        C->SetTranslucentSortPriority(S08AbilityFx::ArcSortPriority);
        C->SetVariableFloat(S08AbilityFx::ArcTiltParam, Tilt);
      }
      Extra = FString::Printf(TEXT(" socket=%s tilt=%.1f"), bSocket ? TEXT("Weapon") : TEXT("-"), Tilt);
    }
    if (C) {
      // frozen at <ms>: the CPU simulation advanced in 1/60 s ticks, then paused (deterministic, FX-04)
      const int32 Ticks = FMath::Max(1, FMath::RoundToInt(S.Ms / (1000.0 / 60.0)));
      C->AdvanceSimulation(Ticks, 1.0f / 60.0f);
      C->SetPaused(true);
    }
    const bool bFadeSkip = S.Mode == TEXT("ash") && S08HeroesV2::DissolveStyle() != S08HeroesV2::EDissolveStyle::Ash;
    FS08Trace::Write(FString::Printf(TEXT("FX bench spawn mode=%s fighter=%s ms=%.0f H=%.0f%s result=%s"), *S.Mode,
                                     *S.FighterId, S.Ms, H, *Extra,
                                     C ? TEXT("spawned") : bFadeSkip ? TEXT("skip reason=fade") : TEXT("missing")));
  }
}

FString AS08FlowGameMode::S08FxBenchFocus(const TCHAR* Cmd, const FString& HeroId) const {
  FString Wanted;
  if (!FParse::Value(Cmd, TEXT("BenchFocusFighter="), Wanted) || Wanted.IsEmpty()) return HeroId;
  for (const FS08BoardFighter& F : Fighters) {
    if (F.Id.Equals(Wanted, ESearchCase::IgnoreCase)) return F.Id;
  }
  for (const S08HeroesV2::FHeroSpec& Spec : S08HeroesV2::Specs()) {
    if (!Wanted.Equals(Spec.Key, ESearchCase::IgnoreCase)) continue;
    for (const FS08BoardFighter& F : Fighters) {
      if (F.Name.Equals(Spec.FighterName, ESearchCase::IgnoreCase)) {
        FS08Trace::Write(FString::Printf(TEXT("BENCH focus fighter=%s (%s)"), *F.Id, Spec.Key));
        return F.Id;
      }
    }
  }
  FS08Trace::Write(FString::Printf(TEXT("BENCH focus error=fighter '%s' not on this board"), *Wanted));
  return HeroId;
}

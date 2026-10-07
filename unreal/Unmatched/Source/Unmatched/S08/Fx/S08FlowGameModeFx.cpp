// FX-03 / FX-06 / FX-17 / FX-19 (VS-6 Z-2): the FX adapter of AS08FlowGameMode - the prewarm + asset resolver +
// grade of the spawner, the hover rim of CUE-001, the defense rim pulse of CUE-009. The game mode itself only
// calls the three S08Fx* entry points (one line each); everything else lives here and in S08/Fx/*.
//
// ВР-FX16: the dispatcher's AssetResolver names the REAL channel state - vfx=<NS_FX_*> when the registry system
// loads (none with -S08FxLegacy, missing while FX-13..FX-32 have not created it), clip=<AM_<Hero>_<Role>> when
// the v2 fighter carries the clip (no more clip=missing on a playing clip), sfx=<the sound token> when the
// sound row's asset loads.
#include "../S08FlowGameMode.h"

#include "NiagaraComponent.h"
#include "NiagaraSystem.h"
#include "Sound/SoundBase.h"
#include "../S08BoardActor.h"
#include "../S08FighterActor.h"
#include "../S08CueDispatcher.h"
#include "S08CueFx.h"
#include "S08CueFxSpawner.h"
#include "../S08CueSound.h"
#include "../S08HeroesV2.h"
#include "../S08TraceLog.h"

namespace {

S08HeroesV2::EClip ClipOfRole(const FString& Role) {
  if (Role == TEXT("LungeAttack")) return S08HeroesV2::EClip::LungeAttack;
  if (Role == TEXT("HitReact")) return S08HeroesV2::EClip::HitReact;
  if (Role == TEXT("DeathSettle")) return S08HeroesV2::EClip::DeathSettle;
  return S08HeroesV2::EClip::None;
}

}  // namespace

void AS08FlowGameMode::S08FxBoardReady() {
  if (!BoardActor || !GetWorld()) return;
  if (!CueFxSpawner) CueFxSpawner = NewObject<US08CueFxSpawnerComponent>(this);
  if (!CueFxSpawner->IsRegistered()) CueFxSpawner->RegisterComponent();
  // the prewarm (load + pool prime + one invisible spawn) once per process: before the first show, so the
  // first frame of a system never pays the compile / pool price
  static bool bPrewarmed = false;
  if (!bPrewarmed) {
    bPrewarmed = true;
    CueFxSpawner->Prewarm();
  }
  // the grade of the profile's paste spec: the measured fit of the engine tone curve (the paste may be off -
  // the fit still holds); the placard / every FX material runs the same inverse curve as M_ConceptPaste
  const FS08ConceptPasteSpec& Paste = BoardActor->GetConceptPasteSpec();
  if (Paste.Grade == ES08ConceptGrade::AcesInverse) {
    const FVector& K = Paste.FitScale;
    const FVector& P = Paste.FitPower;
    CueFxSpawner->SetGrade(FLinearColor(K.X, K.Y, K.Z, 0.0f),
                           FLinearColor(1.0f / P.X, 1.0f / P.Y, 1.0f / P.Z, 0.0f), TEXT("profile"));
  } else {
    CueFxSpawner->SetGrade(FLinearColor(1.0f, 1.0f, 1.0f, 0.0f), FLinearColor(1.0f, 1.0f, 1.0f, 0.0f),
                           TEXT("neutral"));
  }
  // ВР-FX16: the honest channel tokens of every `CUE fx` line
  CueDispatcher.AssetResolver = [this](const FString& CueId, const FString& Channel, const FString& Subject) {
    if (Channel == TEXT("vfx")) {
      if (!S08CueFx::FxEnabled()) return FString(TEXT("none"));
      const FString HeroKey;  // CUE-014 is per hero (FX-28); until then the first entry answers
      const S08CueFx::FEntry* E = S08CueFx::Find(CueId, HeroKey);
      if (!E) return FString();
      if (E->System.IsEmpty()) return FString();  // missing until FX-28 names the hero's system
      return LoadObject<UNiagaraSystem>(nullptr, *E->System) ? S08CueFx::SystemName(E->System) : FString();
    }
    if (Channel == TEXT("clip")) {
      const FS08CueRow* Row = S08CueRows::Find(S08CueRows::Combat(), CueId);
      if (!Row || Row->ClipRole.IsEmpty() || !BoardActor) return FString(TEXT("none"));
      const AS08FighterActor* Actor = BoardActor->FindFighterActor(Subject);
      const FString Asset = Actor ? Actor->GetHeroClipAssetName(ClipOfRole(Row->ClipRole)) : FString();
      return Asset.IsEmpty() ? FString() : Asset;  // missing when this figure carries no such v2 clip
    }
    if (Channel == TEXT("sfx")) {
      const FS08SoundRow* Row = S08SoundRows::Find(CueId);
      if (!Row || Row->SoundPath.IsEmpty()) return FString(TEXT("none"));
      return LoadObject<USoundBase>(nullptr, *Row->SoundPath) ? S08SoundRows::ShortName(Row->SoundPath)
                                                              : FString();
    }
    return FString();
  };
}

void AS08FlowGameMode::S08FxHoverChanged(const FString& NewId, const FString& OldId) {
  // FX-06: the rim follows the cursor's figure - in over 150 ms (ease-out to 0.6, width 0.2, held), out 120 ms;
  // a fallen figure shows no rim; -S08FxLegacy writes nothing (the CUE row still traces).
  auto Rim = [&](const FString& Id, bool bOn) {
    if (Id.IsEmpty() || !BoardActor || !S08CueFx::FxEnabled()) return;
    AS08FighterActor* Actor = BoardActor->FindFighterActor(Id);
    if (!Actor || Actor->IsInDeathHold()) return;
    if (bOn) {
      Actor->PlayRim(0.15f, 0.6f, 0.2f, 0.15f, 0.12f, /*bHold=*/true);
    } else {
      Actor->StopRim(0.12f);
    }
  };
  Rim(OldId, false);
  Rim(NewId, true);
  TArray<FString> Lines;
  CueDispatcher.Feed(TEXT("CUE-001"), NewId, -1, NowMs(), Lines);
  WriteCueLines(Lines);
}

void AS08FlowGameMode::S08FxDefensePlayed(const FString& DefenderId) {
  // FX-17 (ВР-23): the cream rim pulse of the defender - 0 -> 1 over 60 ms, held to 180, out by 300; the CUE
  // row (mat=Rim, no vfx) has already traced above the call.
  if (DefenderId.IsEmpty() || !BoardActor || !S08CueFx::FxEnabled()) return;
  if (AS08FighterActor* Actor = BoardActor->FindFighterActor(DefenderId)) {
    if (!Actor->IsInDeathHold()) Actor->PlayRim(0.3f, 1.0f, 0.35f, 0.06f, 0.12f);
  }
}

void AS08FlowGameMode::S08FxBenchStep(const FString& Spec) {
  // -BenchFx=<mode>[,<id>][,<value>]: placard | hover | rim | rimout | flash | hit | star | off
  //   placard      the FX-02 test placard: NS_FX_PlacardStar (the flipbook print) + the three SDF quads
  //                (disk / diamond / chevron) in a row over the board centre
  //   hover[,<id>] the FX-06 hold state: rim 0.6 x width 0.2 + the CUE-001 line (src=flag, like INPUT select)
  //   rim[,<id>]   the FX-17 / FX-19 peak state: rim 1.0 x width 0.35 (t0+60..C+270)
  //   rimout[,<id>] the way out (C+300): rim 0.5 x width 0.35
  //   flash[,<id>] the FX-19 flash frame (C+0..C+35): FxFlash a = 1, no rim
  //   hit[,<id>]   flash 1 + rim 1 (the composite frame for the grey / deuteranopia rows)
  // The channel values are written straight to CPD (deterministic, no timers in the bench); the curves run in
  // the unit tests and in the live demo.
  TArray<FString> Parts;
  Spec.ParseIntoArray(Parts, TEXT(","), true);
  const FString& Mode = Parts[0];
  const FString Id = Parts.IsValidIndex(1) ? Parts[1] : FString();
  UWorld* World = GetWorld();
  if (!World || !BoardActor) {
    FS08Trace::Write(FString::Printf(TEXT("FX bench mode=%s error=no board"), *Mode));
    return;
  }
  auto Rim = [&](const FString& FighterId, float Intensity, float Width) {
    if (AS08FighterActor* Actor = BoardActor->FindFighterActor(FighterId)) {
      Actor->SetFxBenchChannels(0.0f, Intensity, Width);
    }
  };
  auto Flash = [&](const FString& FighterId, float A) {
    if (AS08FighterActor* Actor = BoardActor->FindFighterActor(FighterId)) {
      Actor->SetFxBenchChannels(A, 0.0f, 0.35f);
    }
  };
  if (Mode == TEXT("placard")) {
    // the FX-02 placard: the Niagara star (frame 0 of the print flipbook) + three SDF quads, a row over the
    // board centre; every component lives on this game mode, the bench tears down with it
    const FVector Centre = BoardActor->GetActorLocation();
    const float Spacing = 46.0f;
    if (CueFxSpawner) {
      UNiagaraComponent* Star = CueFxSpawner->SpawnSystem(
          TEXT("/Game/S08/FX/Systems/NS_FX_PlacardStar"),
          FTransform(FRotator(0.0f, 90.0f, 0.0f), Centre + FVector(1.5f * Spacing, 0.0f, 22.0f)));
      const bool bStarOk = Star && Star->IsRegistered();
      FS08Trace::Write(FString::Printf(TEXT("FX bench placard star=%s"), bStarOk ? TEXT("registered") : TEXT("failed")));
    }
    static const TCHAR* const QuadMis[] = {TEXT("MI_FX_PlacardDisk"), TEXT("MI_FX_PlacardDiamond"),
                                          TEXT("MI_FX_PlacardChevron")};
    int32 Quads = 0;
    for (int32 I = 0; I < 3; ++I) {
      const FString MiPath = FString::Printf(TEXT("/Game/S08/FX/Materials/%s.%s"), QuadMis[I], QuadMis[I]);
      UMaterialInterface* Mi = LoadObject<UMaterialInterface>(nullptr, *MiPath);
      if (!Mi) continue;
      UStaticMesh* Plane = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Plane.Plane"));
      if (!Plane) continue;
      UStaticMeshComponent* Quad = NewObject<UStaticMeshComponent>(BoardActor);
      Quad->SetStaticMesh(Plane);
      Quad->SetMaterial(0, Mi);
      Quad->SetWorldLocation(Centre + FVector((I - 1) * Spacing, 0.0f, 22.0f));
      // the engine plane faces -Z (its normal down): flip it up and face the board camera (yaw 90)
      Quad->SetWorldRotation(FRotator(90.0f, 90.0f, 0.0f));
      Quad->SetWorldScale3D(FVector(0.32f));  // 100 uu plane x 0.32 = 32 uu quad
      Quad->SetCollisionEnabled(ECollisionEnabled::NoCollision);
      Quad->RegisterComponentWithWorld(World);
      ++Quads;
    }
    FS08Trace::Write(FString::Printf(TEXT("FX bench placard sdf=%d"), Quads));
    return;
  }
  if (Mode == TEXT("hover")) {
    Rim(Id, 0.6f, 0.2f);
    TArray<FString> Lines;
    CueDispatcher.Feed(TEXT("CUE-001"), Id, -1, NowMs(), Lines);
    WriteCueLines(Lines);
    FS08Trace::Write(FString::Printf(TEXT("INPUT hover src=flag fighter=%s"), *Id));
    return;
  }
  if (Mode == TEXT("rim")) { Rim(Id, 1.0f, 0.35f); return; }
  if (Mode == TEXT("rimout")) { Rim(Id, 0.5f, 0.35f); return; }
  if (Mode == TEXT("flash")) { Flash(Id, 1.0f); return; }
  if (Mode == TEXT("hit")) {
    if (AS08FighterActor* Actor = BoardActor->FindFighterActor(Id)) {
      Actor->SetFxBenchChannels(1.0f, 1.0f, 0.35f);
    }
    return;
  }
  FS08Trace::Write(FString::Printf(TEXT("FX bench mode=%s error=unknown"), *Mode));
}

// FX-03 / FX-04 (VS-6 Z-2): the registry against cue-table.json and the runtime determinism of the FX systems.
#include "Misc/App.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "NiagaraComponent.h"
#include "NiagaraDataSet.h"
#include "NiagaraDataSetAccessor.h"
#include "NiagaraEffectType.h"
#include "NiagaraEmitter.h"
#include "NiagaraEmitterHandle.h"
#include "NiagaraEmitterInstance.h"
#include "NiagaraSystemInstance.h"
#include "NiagaraSystemInstanceController.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"
#include "../S08CueDispatcher.h"
#include "S08CueFx.h"
#include "Serialization/JsonSerializer.h"

#if WITH_AUTOMATION_TESTS

#include "Engine/World.h"
#include "Misc/AutomationTest.h"

namespace {

TSharedPtr<FJsonObject> LoadJson(const FString& Path) {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *Path)) return nullptr;
  TSharedPtr<FJsonObject> Out;
  TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
  FJsonSerializer::Deserialize(Reader, Out);
  return Out;
}

FString ContractDir() {
  return FPaths::ConvertRelativePathToFull(
      FPaths::Combine(FPaths::ProjectDir(), TEXT("../../docs/unreal/contracts/cue-dispatcher")));
}

}  // namespace

// FX-03: the registry mirrors the vfx blocks of cue-table.json (paths, attach / socket, prewarm), every row has
// one of the two effect types of ВР-25 and a sprite budget; the seed rule of FX-04 is a pure name function.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CueFxRegistryTest,
    "Unmatched.S08.CueFx.Registry the CUE->system rows mirror cue-table.json, ВР-25 types and budgets (FX-03)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CueFxRegistryTest::RunTest(const FString&) {
  using namespace S08CueFx;
  const TSharedPtr<FJsonObject> Table = LoadJson(ContractDir() / TEXT("cue-table.json"));
  TestTrue("cue-table.json read", Table.IsValid());
  if (!Table.IsValid()) return false;
  int32 TableVfx = 0, TableSocket = 0;
  for (const TSharedPtr<FJsonValue>& Value : Table->GetArrayField(TEXT("cues"))) {
    const TSharedPtr<FJsonObject> Row = Value->AsObject();
    const TSharedPtr<FJsonObject>* Vfx = nullptr;
    if (!Row->TryGetObjectField(TEXT("vfx"), Vfx) || !Vfx) continue;
    ++TableVfx;
    const FString Id = Row->GetStringField(TEXT("id"));
    const bool bSocket = (*Vfx)->GetStringField(TEXT("attach")) == TEXT("socket");
    if (bSocket) ++TableSocket;
    const bool bPrewarm = (*Vfx)->GetBoolField(TEXT("prewarm"));
    const FString System = (*Vfx)->HasField(TEXT("system")) ? (*Vfx)->GetStringField(TEXT("system")) : FString();
    if (System.IsEmpty()) continue;  // CUE-014: the hero's own system (FX-28) - checked by hero key below
    const FEntry* E = Find(Id);
    TestNotNull(FString::Printf(TEXT("%s has a registry entry"), *Id), E);
    if (!E) continue;
    // the table carries the object path (/Game/.../NS_X.NS_X); the registry stores the package path
    int32 Dot = INDEX_NONE;
    const FString Package = System.FindChar(TEXT('.'), Dot) ? System.Left(Dot) : System;
    TestEqual(FString::Printf(TEXT("%s system path"), *Id), E->System, Package);
    TestEqual(FString::Printf(TEXT("%s socket attach"), *Id), E->bSocket, bSocket);
    TestEqual(FString::Printf(TEXT("%s prewarm"), *Id), E->bPrewarm, bPrewarm);
    if (bSocket) {
      TestEqual(FString::Printf(TEXT("%s socket name"), *Id), E->Socket, (*Vfx)->GetStringField(TEXT("socket")));
    }
  }
  TestTrue("every vfx row of the table is registered", Registry().Num() >= TableVfx);
  TestEqual("CUE-014 has both hero systems (FX-28 paths)", Find(TEXT("CUE-014"), TEXT("KingArthur")) != nullptr &&
                                                       Find(TEXT("CUE-014"), TEXT("Medusa")) != nullptr, true);
  for (const FEntry& E : Registry()) {
    const FString P = E.CueId + (E.HeroKey.IsEmpty() ? FString() : TEXT("/") + E.HeroKey) + TEXT(" ");
    TestTrue(P + TEXT("effect type is one of ВР-25's two"),
             E.EffectType == CombatEffectType || E.EffectType == BoardEffectType);
    TestTrue(P + TEXT("sprite budget > 0"), E.SpriteBudget > 0);
    TestTrue(P + TEXT("combat type capped at 3 systems (ВР-25)"),
             E.EffectType != CombatEffectType || CombatMaxSystemInstances == 3);
  }
  // FX-04: the seed is a pure function of the asset name - stable, positive, different per system
  TestEqual("NS_FX_HitStar seed is stable", SeedOf(TEXT("/Game/S08/FX/Combat/NS_FX_HitStar")),
            SeedOf(TEXT("/Game/S08/FX/Combat/NS_FX_HitStar")));
  TestTrue("the seed is positive", SeedOf(TEXT("/Game/S08/FX/Combat/NS_FX_HitStar")) > 0);
  TestTrue("two systems never share a seed",
           SeedOf(TEXT("/Game/S08/FX/Combat/NS_FX_HitStar")) != SeedOf(TEXT("/Game/S08/FX/Board/NS_FX_Dust")));
  TestEqual("SystemName is the asset name", SystemName(TEXT("/Game/S08/FX/Combat/NS_FX_HitStar")),
            FString(TEXT("NS_FX_HitStar")));
  TestEqual("SystemName of an empty path is none", SystemName(FString()), FString(TEXT("none")));
  // the rollback flags read the command line (the ARTLOOK fields test them end to end)
  TestTrue("FX enabled by default in this test process", FxEnabled() || FParse::Param(FCommandLine::Get(), FxLegacyFlagName));
  return true;
}

// FX-03 (ВР-25, the Z-2 review fix 8): the two effect types carry their caps - at most 3 combat / 6 board systems
// alive (effect-type and per-system instance count), cull reaction Deactivate (tools/art/fx/ue_fx_systems.py through
// US08FxAuthoringLibrary::SetEffectTypeCaps).
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CueFxEffectTypesTest,
    "Unmatched.S08.CueFx.EffectTypes NET_UM_Combat 3 / NET_UM_Board 6 instance caps, cull reaction Deactivate (FX-03)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CueFxEffectTypesTest::RunTest(const FString&) {
  using namespace S08CueFx;
  const TPair<const TCHAR*, int32> Types[] = {{CombatEffectType, CombatMaxSystemInstances},
                                              {BoardEffectType, BoardMaxSystemInstances}};
  for (const TPair<const TCHAR*, int32>& T : Types) {
    const FString Path = FString(T.Key) + TEXT(".") + FPaths::GetBaseFilename(T.Key);
    const UNiagaraEffectType* Type = LoadObject<UNiagaraEffectType>(nullptr, *Path);
    TestNotNull(FString::Printf(TEXT("%s loads"), T.Key), Type);
    if (!Type) continue;
    TestTrue(FString::Printf(TEXT("%s cull reaction Deactivate"), T.Key),
             Type->CullReaction == ENiagaraCullReaction::Deactivate);
    const TArray<FNiagaraSystemScalabilitySettings>& Settings = Type->GetSystemScalabilitySettings().Settings;
    TestTrue(FString::Printf(TEXT("%s has scalability entries"), T.Key), Settings.Num() > 0);
    for (const FNiagaraSystemScalabilitySettings& S : Settings) {
      TestTrue(FString::Printf(TEXT("%s culls by the effect-type instance count"), T.Key), S.bCullMaxInstanceCount != 0);
      TestEqual(FString::Printf(TEXT("%s MaxInstances"), T.Key), S.MaxInstances, T.Value);
      TestTrue(FString::Printf(TEXT("%s culls by the per-system instance count"), T.Key),
               S.bCullPerSystemMaxInstanceCount != 0);
      TestEqual(FString::Printf(TEXT("%s MaxSystemInstances"), T.Key), S.MaxSystemInstances, T.Value);
    }
  }
  return true;
}

// FX-04: every system under /Game/S08/FX/Systems runs deterministic on the CPU with RandomSeed = CRC32 of its
// name; two components of the same system spawned at the same place hold the same particles at the same positions
// at three time stamps (the card: "позиции частиц в трёх отметках времени"); the pixel-level proof is the -BenchFx
// A/B of the packaged bench. The world carries a world context (the Z-2 review: a context-free world asserted in
// DestroyWorldContext and stopped the whole S08 run).
// ВР-Z2R-05 (по делегированию): Niagara never activates a component in a process that cannot render
// (FApp::CanEverRender() is false with -nullrhi - the S08 suite's runner), so there the test checks the asset half
// (determinism, CPU, the emitter seeds, fixed bounds) and says so; the particle replay runs in a rendering process:
//   UnrealEditor-Cmd <uproject> -ExecCmds="Automation RunTests Unmatched.S08.CueFx.Determinism; Quit" -RenderOffScreen
namespace S08CueFxTest {

struct FParticleSample {
  int32 Count = 0;
  FString State;
  TArray<FVector> Positions;
  TArray<float> Sizes;
};

FParticleSample Sample(UNiagaraComponent* Component) {
  FParticleSample Out;
  FNiagaraSystemInstanceControllerPtr Controller = Component ? Component->GetSystemInstanceController() : nullptr;
  FNiagaraSystemInstance* Instance = Controller.IsValid() ? Controller->GetSystemInstance_Unsafe() : nullptr;
  if (!Instance) {
    Out.State = TEXT("no system instance");
    return Out;
  }
  Out.State = FString::Printf(TEXT("active=%d complete=%d age=%.2f"), Component->IsActive() ? 1 : 0,
                              Instance->IsComplete() ? 1 : 0, Instance->GetAge());
  for (const FNiagaraEmitterInstanceRef& Emitter : Instance->GetEmitters()) {
    Out.State += FString::Printf(TEXT(" [emitter state=%d spawned=%d]"), static_cast<int32>(Emitter->GetExecutionState()),
                                 Emitter->GetTotalSpawnedParticles());
    if (Emitter->IsDisabled()) continue;
    const FNiagaraDataSet& Data = Emitter->GetParticleData();
    const FNiagaraDataBuffer* Buffer = Data.GetCurrentData();
    if (!Buffer) continue;
    const int32 N = static_cast<int32>(Buffer->GetNumInstances());
    const auto Position = FNiagaraDataSetAccessor<FNiagaraPosition>::CreateReader(Data, FName(TEXT("Position")));
    const auto Size = FNiagaraDataSetAccessor<FVector2f>::CreateReader(Data, FName(TEXT("SpriteSize")));
    Out.Count += N;
    for (int32 I = 0; I < N; ++I) {
      Out.Positions.Add(FVector(Position.GetSafe(I, FNiagaraPosition(FVector3f::ZeroVector))));
      Out.Sizes.Add(Size.GetSafe(I, FVector2f::ZeroVector).X);
    }
  }
  return Out;
}

}  // namespace S08CueFxTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CueFxDeterminismTest,
    "Unmatched.S08.CueFx.Determinism bDeterminism + the CRC32 seed; two spawns hold the same particle positions at three times (FX-04)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CueFxDeterminismTest::RunTest(const FString&) {
  using namespace S08CueFxTest;
  UNiagaraSystem* System =
      LoadObject<UNiagaraSystem>(nullptr, TEXT("/Game/S08/FX/Systems/NS_FX_PlacardStar.NS_FX_PlacardStar"));
  TestNotNull("NS_FX_PlacardStar loads (the FX-02 placard system)", System);
  if (!System) return false;
  // RandomSeed itself is protected from the runtime (the editor audit fx_audit.py reads and enforces the CRC32
  // rule); the runtime half is the determinism flag plus the replay check below
  TestTrue("system NeedsDeterminism", System->NeedsDeterminism());
  TestTrue("system fixed bounds", System->bFixedBounds != 0);
  for (const FNiagaraEmitterHandle& Handle : System->GetEmitterHandles()) {
    const FVersionedNiagaraEmitterData* Data = Handle.GetEmitterData();
    if (!Handle.GetIsEnabled() || !Data) continue;
    TestTrue(FString::Printf(TEXT("%s: CPU simulation (no GPU emitters)"), *Handle.GetName().ToString()),
             Data->SimTarget == ENiagaraSimTarget::CPUSim);
    TestTrue(FString::Printf(TEXT("%s: emitter determinism"), *Handle.GetName().ToString()), Data->bDeterminism != 0);
  }
  if (!FApp::CanEverRender()) {
    AddInfo(TEXT("particle replay not run: this process cannot render (-nullrhi), Niagara never activates here - "
                 "run Unmatched.S08.CueFx.Determinism in a rendering process (ВР-Z2R-05)"));
    return true;
  }
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("S08CueFxDeterminismWorld"));
  if (!World) {
    AddError(TEXT("could not create a test world"));
    return true;
  }
  FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
  Context.SetCurrentWorld(World);
  // the component / world-manager tick functions run only in a world that has begun play
  World->InitializeActorsForPlay(FURL());
  World->BeginPlay();
  UNiagaraComponent* A = UNiagaraFunctionLibrary::SpawnSystemAtLocation(World, System, FVector::ZeroVector,
      FRotator::ZeroRotator, FVector::OneVector, /*bAutoDestroy=*/false, /*bAutoActivate=*/true, ENCPoolMethod::None,
      /*bPreCullCheck=*/false);
  UNiagaraComponent* B = UNiagaraFunctionLibrary::SpawnSystemAtLocation(World, System, FVector::ZeroVector,
      FRotator::ZeroRotator, FVector::OneVector, /*bAutoDestroy=*/false, /*bAutoActivate=*/true, ENCPoolMethod::None,
      /*bPreCullCheck=*/false);
  TestTrue("two components of the system spawned", A != nullptr && B != nullptr);
  if (A && B) {
    // three time stamps: 0.1 s (the first frames), 1.0 s and 6.0 s (the still print, FX-02)
    const double Stamps[] = {0.1, 1.0, 6.0};
    const double Dt = 1.0 / 30.0;
    double T = 0.0;
    int32 FirstCount = -1;
    for (const double Stamp : Stamps) {
      // the simulation advances synchronously (the warm-up path of the component), the same steps on both
      const int32 Steps = FMath::RoundToInt((Stamp - T) / Dt);
      if (Steps > 0) {
        A->AdvanceSimulation(Steps, static_cast<float>(Dt));
        B->AdvanceSimulation(Steps, static_cast<float>(Dt));
        T += Steps * Dt;
      }
      const FParticleSample SA = Sample(A);
      const FParticleSample SB = Sample(B);
      AddInfo(FString::Printf(TEXT("t=%.2f s: particles %d / %d, size %.1f, %s"), Stamp, SA.Count, SB.Count,
                              SA.Sizes.Num() ? SA.Sizes[0] : -1.0f, *SA.State));
      TestEqual(FString::Printf(TEXT("t=%.2f s: the same particle count"), Stamp), SA.Count, SB.Count);
      if (FirstCount < 0) FirstCount = SA.Count;
      if (SA.Count == SB.Count) {
        double MaxDelta = 0.0;
        for (int32 I = 0; I < SA.Count; ++I) {
          MaxDelta = FMath::Max(MaxDelta, (SA.Positions[I] - SB.Positions[I]).Size());
        }
        TestTrue(FString::Printf(TEXT("t=%.2f s: the same positions (max delta %.4f uu)"), Stamp, MaxDelta),
                 MaxDelta < 0.01);
      }
    }
    TestEqual("the placard star is one print sprite from the first 0.1 s (FX-02: shown at once)", FirstCount, 1);
    const FParticleSample Last = Sample(A);
    TestTrue("the star sprite has a visible size", Last.Sizes.Num() == 1 && Last.Sizes[0] > 1.0f);
    A->DestroyComponent();
    B->DestroyComponent();
  }
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS

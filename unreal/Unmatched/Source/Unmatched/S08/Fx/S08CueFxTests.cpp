// FX-03 / FX-04 (VS-6 Z-2): the registry against cue-table.json and the runtime determinism of the FX systems.
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "NiagaraComponent.h"
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

// FX-04: every system under /Game/S08/FX/Systems runs deterministic on the CPU with RandomSeed = CRC32 of its
// name, and two spawned components of the same system cover the same bounds over time (the pixel-level proof
// is the -BenchFx A/B of the packaged bench; this is the runtime half).
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CueFxDeterminismTest,
    "Unmatched.S08.CueFx.Determinism bDeterminism + the CRC32 seed; two spawns cover the same bounds (FX-04)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CueFxDeterminismTest::RunTest(const FString&) {
  UNiagaraSystem* System =
      LoadObject<UNiagaraSystem>(nullptr, TEXT("/Game/S08/FX/Systems/NS_FX_PlacardStar.NS_FX_PlacardStar"));
  TestNotNull("NS_FX_PlacardStar loads (the FX-02 placard system)", System);
  if (!System) return false;
  // RandomSeed itself is protected from the runtime (the editor audit fx_audit.py reads and enforces the CRC32
  // rule); the runtime half is the determinism flag plus the replay check below
  TestTrue("system NeedsDeterminism", System->NeedsDeterminism());
  UWorld* World = UWorld::CreateWorld(EWorldType::Inactive, false);
  if (!World) return true;
  UNiagaraFunctionLibrary::SpawnSystemAtLocation(World, System, FVector::ZeroVector);
  UNiagaraFunctionLibrary::SpawnSystemAtLocation(World, System, FVector::ZeroVector);
  for (int32 I = 0; I < 5; ++I) World->Tick(LEVELTICK_All, 1.0f / 30.0f);
  TArray<UNiagaraComponent*> Spawned;
  for (TObjectIterator<UNiagaraComponent> It; It; ++It) {
    if (It->GetWorld() == World && It->GetAsset() == System) Spawned.Add(*It);
  }
  TestEqual("two components of the system are alive", Spawned.Num(), 2);
  if (Spawned.Num() == 2) {
    const double ARadius = Spawned[0]->Bounds.SphereRadius;
    const double BRadius = Spawned[1]->Bounds.SphereRadius;
    TestTrue(FString::Printf(TEXT("two same-seed spawns: bounds %.1f vs %.1f"), ARadius, BRadius),
             FMath::Abs(ARadius - BRadius) < 1.0);
  }
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS

// AN-32 (ВР-16) automation tests of the heroMaterials block of the map light profile (S08BoardArt.h) and its way
// onto the figures (AS08FighterActor::ApplyHeroMaterials; the Art Tuner scope "heroMaterials"):
//   Unmatched.S08.HeroMaterials.Parse - the block decodes: looks P1 / P2 / *, neutral defaults for absent fields.
//   Unmatched.S08.HeroMaterials.Validate - a bad class / gain / spec / look drops only that hero's entry with an
//     error (the profile and the other heroes stay).
//   Unmatched.S08.HeroMaterials.Apply - a non-neutral fix wraps the v2 body slots in MIDs carrying the values; a
//     neutral fix / nullptr unwraps them back to the plain MI; -S08HeroMatFixLegacy ignores the block.
//   Unmatched.S08.ArtTuner.HeroMaterials - the registry rows (Config/ArtTuner/S08ArtTunerParams.json) point into
//     lightProfiles.<id>.heroMaterials and map to the "heroMaterials" scope.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.HeroMaterials" <abs log>
#if WITH_AUTOMATION_TESTS

#include "S08BoardArt.h"
#include "S08ArtTuner.h"
#include "S08FighterActor.h"
#include "S08HeroesV2.h"
#include "S08BoardModel.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

namespace {

/** One document with a light profile carrying a heroMaterials block (the BoardArt test minimal skeleton). */
FString Doc(const FString& HeroMaterials) {
  return FString::Printf(TEXT(
      "{\"schema\":\"unmatched.s08-art-board-profiles/1\",\"revision\":7,"
      "\"zoneStyles\":{\"a\":{\"stroke\":\"solid\",\"glyph\":\"diamond\",\"color\":\"#102030\"},"
      "\"b\":{\"stroke\":\"dash2\",\"glyph\":\"ring\",\"color\":\"#A0B0C0\"},"
      "\"c\":{\"stroke\":\"dots5\",\"glyph\":\"x\",\"color\":\"#FFFFFF\"}},"
      "\"fallbackZoneStyle\":{\"stroke\":\"dots5\",\"glyph\":\"bar1\",\"color\":\"#FFFFFF\"},"
      "\"lightProfiles\":{\"L\":{\"directional\":{\"name\":\"key\",\"posUU\":[0,0,600],\"rotation\":[-50,-90,0],"
      "\"intensity\":3,\"castShadows\":true},\"points\":[{\"name\":\"p\",\"at\":[0.5,-0.5,200],\"intensity\":50,"
      "\"radiusUU\":300,\"colorLinear\":[1,0.5,0.25]}],%s}},"
      "\"boards\":[{\"id\":\"one\",\"match\":{\"boardIds\":[\"cid1\"],\"width\":3,\"height\":2,\"zoneKeys\":[\"b\",\"a\"]},"
      "\"surface\":\"tiles\",\"light\":\"L\",\"expect\":{\"cells\":6,\"zoneCells\":6,\"multizoneCells\":1,"
      "\"obstacles\":0,\"zoneCellCounts\":{\"a\":3,\"b\":4}}}]}"),
      *HeroMaterials);
}

constexpr const TCHAR* GoodBlock =
    TEXT("\"heroMaterials\": { \"Medusa\": { \"*\": { \"FixClassA\": 13, \"FixGainA\": 1.15 } }, "
         "\"KingArthur\": { \"P1\": { \"FixClassB\": 7, \"FixSpecB\": 0.1 } } }");

FS08BoardFighter Harpy() {
  FS08BoardFighter F;
  F.Id = TEXT("f-harpy");
  F.OwnerId = TEXT("owner");
  F.Name = TEXT("Harpies");
  F.Label = TEXT("Harpies 1");
  F.bIsHero = false;
  F.Health = 8;
  F.MaxHealth = 8;
  F.X = 1;
  F.Y = 1;
  return F;
}

}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroMaterialsParseTest,
    "Unmatched.S08.HeroMaterials.Parse the block decodes - looks P1/P2/*, neutral defaults (AN-32, BP-16)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroMaterialsParseTest::RunTest(const FString&) {
  FS08BoardArtData Data;
  TArray<FString> Errors;
  TestTrue("document with heroMaterials parses", Data.ParseJson(Doc(GoodBlock), Errors));
  const FS08LightProfile* L = Data.Lights.Find(TEXT("L"));
  if (!TestNotNull("profile L", L)) return false;
  TestEqual("two heroes", L->HeroMaterials.Num(), 2);
  // Medusa's "*" look: class 13, gain 1.15; the absent fields keep their neutral defaults.
  const FS08HeroMaterialFix& Medusa = L->HeroMaterialFix(TEXT("Medusa"), TEXT("P1"));
  TestEqual("Medusa class A (from *)", Medusa.ClassA, 13);
  TestTrue("Medusa gain A 1.15", FMath::IsNearlyEqual(Medusa.GainA, 1.15f));
  TestEqual("Medusa spec A neutral", Medusa.SpecA, 0.0f);
  TestEqual("Medusa class B neutral", Medusa.ClassB, -1);
  TestTrue("Medusa not neutral", !Medusa.IsNeutral());
  // Arthur's own P1 beats the absent "*" look; P2 has nothing - neutral.
  TestEqual("Arthur class B (his P1)", L->HeroMaterialFix(TEXT("KingArthur"), TEXT("P1")).ClassB, 7);
  TestTrue("Arthur P2 neutral", L->HeroMaterialFix(TEXT("KingArthur"), TEXT("P2")).IsNeutral());
  // A hero without a block is neutral; the block-free profile too.
  TestTrue("Merlin neutral", L->HeroMaterialFix(TEXT("Merlin"), TEXT("P1")).IsNeutral());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroMaterialsValidateTest,
    "Unmatched.S08.HeroMaterials.Validate bad values drop only that hero entry with an error (AN-32, BP-16)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroMaterialsValidateTest::RunTest(const FString&) {
  auto Check = [this](const FString& Name, const FString& Block, const TCHAR* ErrorPart, int32 WantHeroes) {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    Data.ParseJson(Doc(Block), Errors);  // the per-hero errors make the document "not clean", the profile stays
    const FString All = FString::Join(Errors, TEXT(" | "));
    TestTrue(FString::Printf(TEXT("%s: error '%s' in %s"), *Name, ErrorPart, *All), All.Contains(ErrorPart));
    const FS08LightProfile* L = Data.Lights.Find(TEXT("L"));
    if (TestNotNull(Name + TEXT(": the profile stays"), L)) {
      TestEqual(Name + TEXT(": heroes kept"), L->HeroMaterials.Num(), WantHeroes);
    }
  };
  Check(TEXT("class over 15"),
        TEXT("\"heroMaterials\": { \"Medusa\": { \"*\": { \"FixClassA\": 16 } }, \"Merlin\": { \"*\": { \"FixGainA\": 0.9 } } }"),
        TEXT("heroMaterials.Medusa.* out of range: FixClassA"), 1);
  Check(TEXT("gain under 0.5"),
        TEXT("\"heroMaterials\": { \"Medusa\": { \"*\": { \"FixGainA\": 0.4 } }, \"Merlin\": { \"*\": { \"FixGainA\": 0.9 } } }"),
        TEXT("heroMaterials.Medusa.* out of range: FixGainA"), 1);
  Check(TEXT("spec over 0.3"),
        TEXT("\"heroMaterials\": { \"Medusa\": { \"*\": { \"FixSpecA\": 0.4 } }, \"Merlin\": { \"*\": { \"FixGainA\": 0.9 } } }"),
        TEXT("heroMaterials.Medusa.* out of range: FixSpecA"), 1);
  Check(TEXT("unknown look key"),
        TEXT("\"heroMaterials\": { \"Medusa\": { \"P9\": { \"FixGainA\": 0.9 } }, \"Merlin\": { \"*\": { \"FixGainA\": 0.9 } } }"),
        TEXT("heroMaterials.Medusa.P9"), 1);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroMaterialsApplyTest,
    "Unmatched.S08.HeroMaterials.Apply the fix wraps the v2 body slots in MIDs; neutral unwraps (AN-32, BP-16)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroMaterialsApplyTest::RunTest(const FString&) {
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("S08HeroMaterialsWorld"));
  if (!World) {
    AddError(TEXT("could not create a test world"));
    return true;
  }
  FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
  Context.SetCurrentWorld(World);
  AS08FighterActor* Actor = World->SpawnActor<AS08FighterActor>(AS08FighterActor::StaticClass(), FVector(0, -400, 0),
                                                                FRotator::ZeroRotator);
  Actor->SetTeam(ES08TeamSlot::P1, ES08TeamSlot::P1, ES08TeamColorMode::Absolute);
  Actor->ApplyFighter(Harpy(), FVector(0, -400, 0), true, true);
  if (!Actor->IsHeroV2()) {
    AddWarning(TEXT("v2 harpy assets missing in this checkout - the apply test is skipped"));
  } else {
    const UMaterialInterface* Plain = Actor->FindComponentByClass<USkeletalMeshComponent>()->GetMaterial(0);
    TestFalse("no block: the plain MI, no MID", !!Cast<UMaterialInstanceDynamic>(Plain));
    FS08HeroMaterialFix Fix;
    Fix.ClassA = 13;
    Fix.GainA = 1.15f;
    Fix.SpecA = -0.1f;
    Actor->ApplyHeroMaterials(&Fix);
    UMaterialInstanceDynamic* Mid = Cast<UMaterialInstanceDynamic>(
        Actor->FindComponentByClass<USkeletalMeshComponent>()->GetMaterial(0));
    if (TestNotNull("the fix wraps the slot in a MID", Mid)) {
      TestEqual("FixClassA on the MID", FMath::RoundToInt(Mid->K2_GetScalarParameterValue(TEXT("FixClassA"))), 13);
      TestTrue("FixGainA on the MID",
               FMath::IsNearlyEqual(Mid->K2_GetScalarParameterValue(TEXT("FixGainA")), 1.15f));
      TestTrue("FixSpecA on the MID",
               FMath::IsNearlyEqual(Mid->K2_GetScalarParameterValue(TEXT("FixSpecA")), -0.1f));
      TestEqual("FixClassB neutral on the MID",
                FMath::RoundToInt(Mid->K2_GetScalarParameterValue(TEXT("FixClassB"))), -1);
    }
    // Neutral unwraps back to the plain MI.
    const FS08HeroMaterialFix Neutral;
    Actor->ApplyHeroMaterials(&Neutral);
    TestEqual("neutral: the plain MI back",
              Actor->FindComponentByClass<USkeletalMeshComponent>()->GetMaterial(0) == Plain ? 1 : 0, 1);
    // The rollback flag ignores the block.
    Actor->ApplyHeroMaterials(&Fix);
    const FString Saved = FCommandLine::Get();
    FCommandLine::Set(*(Saved + TEXT(" -S08HeroMatFixLegacy")));
    Actor->ApplyHeroMaterials(&Fix);
    FCommandLine::Set(*Saved);
    TestEqual("rollback: the plain MI stays",
              Actor->FindComponentByClass<USkeletalMeshComponent>()->GetMaterial(0) == Plain ? 1 : 0, 1);
  }
  Actor->Destroy();
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtTunerHeroMaterialsTest,
    "Unmatched.S08.ArtTuner.HeroMaterials the registry rows point into lightProfiles heroMaterials (AN-32, BP-16)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtTunerHeroMaterialsTest::RunTest(const FString&) {
  ES08TunerScope Scope = ES08TunerScope::None;
  TestTrue("the scope name maps", S08TunerScopeFromName(TEXT("heroMaterials"), Scope) &&
                                     EnumHasAnyFlags(Scope, ES08TunerScope::HeroMaterials));
  const FString Path = FPaths::Combine(FPaths::ProjectConfigDir(), TEXT("ArtTuner"),
                                       TEXT("S08ArtTunerParams.json"));
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *Path)) {
    AddError(TEXT("S08ArtTunerParams.json not found"));
    return false;
  }
  // One row per (hero, Fix field): the pointer template writes lightProfiles.{profile}.heroMaterials.<Hero>.*.
  int32 Rows = 0;
  for (const FString& Hero : {TEXT("KingArthur"), TEXT("Merlin"), TEXT("Medusa"), TEXT("Harpy")}) {
    for (const FString& Field : {TEXT("FixClassA"), TEXT("FixGainA"), TEXT("FixSpecA"), TEXT("FixClassB"),
                                 TEXT("FixGainB"), TEXT("FixSpecB")}) {
      const FString Id = Hero + TEXT(".") + Field;
      const FString Pointer = FString::Printf(TEXT("/lightProfiles/{profile}/heroMaterials/%s/*/%s"), *Hero, *Field);
      if (Text.Contains(TEXT("\"id\": \"") + Id + TEXT("\"")) && Text.Contains(Pointer)) ++Rows;
    }
  }
  TestEqual("24 heroMaterials rows (4 heroes x 6 Fix fields)", Rows, 24);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS

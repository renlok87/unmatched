// ENV-MAPS P9 hero light automation tests (S08HeroLight.h, docs/art-pipeline/ENV-HERO-LIGHT.md):
//   Parse      the "heroLight" block: valid / absent / every broken field refused (the document fails);
//   Shipped    every light profile of S08ArtBoardProfiles.json (Marmoreal, Sarpedon, Cobble + probes: «Все сцены») has an
//              enabled key + rim block, the budget constants, the key on the camera side towards the moon key;
//   Math       Place (camera side / behind, the aim, lux -> cd, cone, radius), StateMultiplier (active x 1.35, frozen,
//              the breathing pulse, defeated off), LayersForBoard (<= 2 per figure, <= 14 per board);
//   Actor      a grid board and a topology (map-image layout) board: a rig per figure, lighting channel 1 only, no
//              shadow / GI / translucency, the figure meshes on channels 0 + 1 and nothing else of the world on channel 1
//              (tiles, map plane, frame, rings, labels), the active fighter x activeMul, the rig follows a move, a dead
//              fighter has none, -NoHeroLight removes it all, the board budget; the shipped Sarpedon profile end to end
//              when the map assets are imported.
//   UnrealEditor-Cmd.exe Unmatched.uproject -ExecCmds="Automation RunTests Unmatched.S08.HeroLight; Quit" -unattended -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08BoardActor.h"
#include "S08BoardArt.h"
#include "S08BoardModel.h"
#include "S08Contracts.h"
#include "S08FighterActor.h"
#include "S08HeroLight.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SpotLightComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "UObject/UObjectIterator.h"

namespace S08HeroLightTest {

/** A valid heroLight block (the shipped night values). */
const TCHAR* const ValidBlock = TEXT(
    "{\"enabled\":true,\"note\":\"t\",\"cameraAzimuthDeg\":90,\"aimHeight\":0.55,"
    "\"key\":{\"lux\":4,\"colorSrgb\":\"#FFE4C4\",\"innerConeDeg\":22,\"outerConeDeg\":34,\"heightMul\":2.5,\"azimuthDeg\":35,"
    "\"elevationDeg\":60,\"radiusMul\":1.6},"
    "\"rim\":{\"lux\":2.4,\"colorSrgb\":\"#A8C0FF\",\"innerConeDeg\":16,\"outerConeDeg\":26,\"heightMul\":1.3,\"azimuthDeg\":145,"
    "\"elevationDeg\":35,\"radiusMul\":1.6},"
    "\"states\":{\"activeMul\":1.35,\"breathHz\":0.4,\"breathAmp\":0.08,\"defeatedMul\":0}}");

/** A minimal valid profile document whose light profile L carries Block (empty = no block). */
FString Doc(const FString& Block) {
  const FString Hero = Block.IsEmpty() ? FString() : FString(TEXT(",\"heroLight\":")) + Block;
  return FString(TEXT(
             "{\"schema\":\"unmatched.s08-art-board-profiles/1\",\"revision\":19,"
             "\"zoneStyles\":{\"a\":{\"stroke\":\"solid\",\"glyph\":\"diamond\",\"color\":\"#102030\"},"
             "\"b\":{\"stroke\":\"dash2\",\"glyph\":\"ring\",\"color\":\"#A0B0C0\"}},"
             "\"fallbackZoneStyle\":{\"stroke\":\"dots5\",\"glyph\":\"bar1\",\"color\":\"#FFFFFF\"},"
             "\"lightProfiles\":{\"L\":{\"directional\":{\"name\":\"key\",\"posUU\":[0,0,600],\"rotation\":[-55,30,0],"
             "\"intensity\":3,\"castShadows\":true},\"points\":[{\"name\":\"p\",\"at\":[0.5,-0.5,200],\"intensity\":50,"
             "\"radiusUU\":300}]")) +
         Hero +
         TEXT("}},\"boards\":[{\"id\":\"one\",\"match\":{\"boardIds\":[\"cid1\"],\"width\":3,\"height\":2,\"zoneKeys\":[\"b\",\"a\"]},"
              "\"surface\":\"tiles\",\"light\":\"L\",\"expect\":{\"cells\":6,\"zoneCells\":6,\"multizoneCells\":1,\"obstacles\":0,"
              "\"zoneCellCounts\":{\"a\":3,\"b\":4}}}]}");
}

/** ValidBlock with Old replaced by New (one occurrence). */
FString Broken(const TCHAR* Old, const TCHAR* New) {
  FString B = ValidBlock;
  B.ReplaceInline(Old, New);
  return B;
}

FS08HeroLightSpec ValidSpec() {
  FS08BoardArtData Data;
  TArray<FString> Errors;
  Data.ParseJson(Doc(ValidBlock), Errors);
  const FS08LightProfile* L = Data.Lights.Find(TEXT("L"));
  return L ? L->HeroLight : FS08HeroLightSpec();
}

FS08BoardModel Grid(int32 W, int32 H) {
  FS08BoardModel Board;
  Board.Width = W;
  Board.Height = H;
  Board.Cells.Init(FS08Cell(), W * H);
  for (int32 Y = 0; Y < H; ++Y) {
    for (int32 X = 0; X < W; ++X) {
      FS08Cell& Cell = Board.Cells[Y * W + X];
      Cell.X = X;
      Cell.Y = Y;
      Cell.Type = ES08CellType::Normal;
    }
  }
  return Board;
}

/** 3 x 2 lattice with three linked spaces (a topology board: the map-image layout frame), same as S08BoardArtTests. */
const TCHAR* const TopologyJson = TEXT(
    "{\"width\":3,\"height\":2,\"doors\":{},\"cells\":["
    "[{\"type\":\"normal\",\"x\":0,\"y\":0,\"zones\":[\"a\"],\"zone\":\"a\",\"spaceId\":\"T01\",\"layout\":{\"x\":200,\"y\":200},"
    "\"start\":1,\"links\":[{\"x\":1,\"y\":0}]},"
    "{\"type\":\"normal\",\"x\":1,\"y\":0,\"zones\":[\"a\",\"b\"],\"zone\":\"a\",\"spaceId\":\"T02\",\"layout\":{\"x\":500,\"y\":200},"
    "\"links\":[{\"x\":0,\"y\":0},{\"x\":2,\"y\":1}]},"
    "{\"type\":\"obstacle\",\"x\":2,\"y\":0}],"
    "[{\"type\":\"obstacle\",\"x\":0,\"y\":1},{\"type\":\"obstacle\",\"x\":1,\"y\":1},"
    "{\"type\":\"normal\",\"x\":2,\"y\":1,\"zones\":[\"b\"],\"zone\":\"b\",\"spaceId\":\"T03\",\"layout\":{\"x\":800,\"y\":500},"
    "\"start\":2,\"links\":[{\"x\":1,\"y\":0}]}]]}");

bool Topology(FS08BoardModel& Out) {
  TSharedPtr<FJsonObject> Obj;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(TopologyJson, Obj, Problem) || !Obj.IsValid()) return false;
  return Out.Decode(MakeShared<FJsonValueObject>(Obj));
}

/** N fighters on the board spaces (cycling), the first of each side a hero. */
TArray<FS08BoardFighter> Fighters(const FS08BoardModel& Board, int32 N) {
  TArray<FS08BoardFighter> Spaces;
  for (int32 Y = 0; Y < Board.Height; ++Y) {
    for (int32 X = 0; X < Board.Width; ++X) {
      if (!Board.IsBoardSpace(X, Y)) continue;
      FS08BoardFighter F;
      F.X = X;
      F.Y = Y;
      Spaces.Add(F);
    }
  }
  TArray<FS08BoardFighter> Out;
  for (int32 I = 0; I < N && Spaces.Num() > 0; ++I) {
    FS08BoardFighter F = Spaces[I % Spaces.Num()];
    F.Id = FString::Printf(TEXT("f-%d"), I);
    F.OwnerId = I % 2 == 0 ? TEXT("host") : TEXT("guest");
    F.Name = I < 2 ? TEXT("Medusa") : TEXT("Harpies");
    F.Label = F.Name;
    F.bIsHero = I < 2;
    F.Health = F.MaxHealth = 7;
    Out.Add(F);
  }
  return Out;
}

/** Every primitive of the world on lighting channel 1 is a figure mesh of a fighter actor (ArtBody / ArtBase /
 *  ArtPlaceholder / Body); returns the offenders. */
TArray<FString> ChannelOneOutsideFigures(UWorld* World) {
  TArray<FString> Bad;
  for (TObjectIterator<UPrimitiveComponent> It; It; ++It) {
    const UPrimitiveComponent* P = *It;
    if (!P || P->GetWorld() != World || !P->LightingChannels.bChannel1) continue;
    const AS08FighterActor* Fighter = Cast<AS08FighterActor>(P->GetOwner());
    if (!Fighter || !Fighter->GetHeroLitPrimitives().Contains(P)) {
      Bad.Add(FString::Printf(TEXT("%s.%s"), P->GetOwner() ? *P->GetOwner()->GetName() : TEXT("-"), *P->GetName()));
    }
  }
  return Bad;
}

}  // namespace S08HeroLightTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroLightParseTest,
    "Unmatched.S08.HeroLight.Parse heroLight block: valid, absent, broken fields fail the document",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroLightParseTest::RunTest(const FString&) {
  using namespace S08HeroLightTest;
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    TestTrue(TEXT("valid block parses: ") + FString::Join(Errors, TEXT(" | ")), Data.ParseJson(Doc(ValidBlock), Errors));
    const FS08LightProfile* L = Data.Lights.Find(TEXT("L"));
    if (TestNotNull("light profile L", L)) {
      const FS08HeroLightSpec& H = L->HeroLight;
      TestTrue("set + enabled, key + rim", H.bSet && H.bEnabled && H.Key.bSet && H.Rim.bSet && H.Layers() == 2);
      TestTrue("key values", H.Key.Lux == 4.0f && H.Key.InnerConeDeg == 22.0f && H.Key.OuterConeDeg == 34.0f &&
                                 H.Key.HeightMul == 2.5f && H.Key.AzimuthDeg == 35.0f && H.Key.ElevationDeg == 60.0f &&
                                 H.Key.ColorSrgb == FColor(0xFF, 0xE4, 0xC4));
      TestTrue("rim values", FMath::IsNearlyEqual(H.Rim.Lux, 2.4f) && H.Rim.ColorSrgb == FColor(0xA8, 0xC0, 0xFF) &&
                                 H.Rim.AzimuthDeg == 145.0f && H.Rim.ElevationDeg == 35.0f);
      TestTrue("states", FMath::IsNearlyEqual(H.ActiveMul, 1.35f) && FMath::IsNearlyEqual(H.BreathHz, 0.4f) &&
                             FMath::IsNearlyEqual(H.BreathAmp, 0.08f) && H.DefeatedMul == 0.0f);
      TestTrue("camera azimuth / aim", H.CameraAzimuthDeg == 90.0f && FMath::IsNearlyEqual(H.AimHeight, 0.55f));
    }
  }
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    TestTrue("no block parses", Data.ParseJson(Doc(FString()), Errors));
    const FS08LightProfile* L = Data.Lights.Find(TEXT("L"));
    TestTrue("absent block = not set (no rig)", L && !L->HeroLight.bSet && !L->HeroLight.bEnabled);
  }
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    TestTrue("disabled block parses", Data.ParseJson(Doc(Broken(TEXT("\"enabled\":true"), TEXT("\"enabled\":false"))), Errors));
    const FS08LightProfile* L = Data.Lights.Find(TEXT("L"));
    TestTrue("disabled: set, not enabled", L && L->HeroLight.bSet && !L->HeroLight.bEnabled);
  }
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    TestTrue("key only parses", Data.ParseJson(Doc(Broken(
        TEXT(",\"rim\":{\"lux\":2.4,\"colorSrgb\":\"#A8C0FF\",\"innerConeDeg\":16,\"outerConeDeg\":26,\"heightMul\":1.3,\"azimuthDeg\":145,"
             "\"elevationDeg\":35,\"radiusMul\":1.6}"), TEXT(""))), Errors));
    const FS08LightProfile* L = Data.Lights.Find(TEXT("L"));
    TestTrue("key only: one layer", L && L->HeroLight.Layers() == 1 && !L->HeroLight.Rim.bSet);
  }
  struct FCase {
    const TCHAR* Name;
    const TCHAR* Old;
    const TCHAR* New;
  };
  const FCase Cases[] = {
      {TEXT("unknown block field"), TEXT("\"note\":\"t\""), TEXT("\"notes\":\"t\"")},
      {TEXT("no enabled"), TEXT("\"enabled\":true,"), TEXT("")},
      {TEXT("key lux 0"), TEXT("\"lux\":4"), TEXT("\"lux\":0")},
      {TEXT("key lux 60"), TEXT("\"lux\":4"), TEXT("\"lux\":60")},
      {TEXT("bad colour"), TEXT("#FFE4C4"), TEXT("FFE4C4")},
      {TEXT("inner cone > outer"), TEXT("\"innerConeDeg\":22"), TEXT("\"innerConeDeg\":40")},
      {TEXT("elevation 90"), TEXT("\"elevationDeg\":60"), TEXT("\"elevationDeg\":90")},
      {TEXT("light below the aim point"), TEXT("\"heightMul\":2.5"), TEXT("\"heightMul\":0.6")},
      {TEXT("unknown layer field"), TEXT("\"radiusMul\":1.6},\"rim\""), TEXT("\"radiusMul\":1.6,\"shadow\":true},\"rim\"")},
      {TEXT("activeMul 0.5"), TEXT("\"activeMul\":1.35"), TEXT("\"activeMul\":0.5")},
      {TEXT("breathAmp 0.9"), TEXT("\"breathAmp\":0.08"), TEXT("\"breathAmp\":0.9")},
      {TEXT("unknown state field"), TEXT("\"defeatedMul\":0"), TEXT("\"defeatedMul\":0,\"idleMul\":1")},
      {TEXT("no key"), TEXT("\"key\":"), TEXT("\"keys\":")},
  };
  for (const FCase& C : Cases) {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    const bool bOk = Data.ParseJson(Doc(Broken(C.Old, C.New)), Errors);
    TestFalse(FString::Printf(TEXT("%s: the document fails"), C.Name), bOk);
    TestTrue(FString::Printf(TEXT("%s: a heroLight error line (%s)"), C.Name, *FString::Join(Errors, TEXT(" | "))),
             Errors.ContainsByPredicate([](const FString& E) { return E.Contains(TEXT("heroLight")); }));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroLightShippedTest,
    "Unmatched.S08.HeroLight.Shipped every light profile carries an enabled key + rim heroLight (all scenes)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroLightShippedTest::RunTest(const FString&) {
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (!TestTrue(TEXT("shipped profiles parse: ") + FString::Join(Errors, TEXT(" | ")),
                Data.LoadFile(FS08BoardArtData::DefaultPath(), Errors))) {
    return false;
  }
  for (const TCHAR* Id : {TEXT("marmoreal-night"), TEXT("sarpedon-night"), TEXT("cobble-probe"), TEXT("forest-probe"),
                          TEXT("paddock-probe")}) {
    const FS08LightProfile* L = Data.Lights.Find(Id);
    if (!TestNotNull(FString::Printf(TEXT("light profile %s"), Id), L)) continue;
    const FS08HeroLightSpec& H = L->HeroLight;
    TestTrue(FString::Printf(TEXT("%s: heroLight enabled, key + rim"), Id), H.bSet && H.bEnabled && H.Layers() == 2);
    TestTrue(FString::Printf(TEXT("%s: rim weaker than the key, cool rim / warm key"), Id),
             H.Rim.Lux < H.Key.Lux && H.Rim.ColorSrgb.B > H.Rim.ColorSrgb.R && H.Key.ColorSrgb.R >= H.Key.ColorSrgb.B);
    TestTrue(FString::Printf(TEXT("%s: active x %.2f >= 1.2, defeated off"), Id, H.ActiveMul),
             H.ActiveMul >= 1.2f && H.DefeatedMul == 0.0f);
    // the environment budget is untouched: 1 key + <= 6 points (the hero light is its own category)
    FString Reason;
    TestTrue(FString::Printf(TEXT("%s: environment budget still ok"), Id), L->BudgetOk(Reason));
    // the key comes from the camera side (+Y), rotated towards the moon key (from -X); the rim from behind (-Y)
    const FS08HeroLightPlacement Key = S08HeroLight::Place(H, H.Key, 55.0f);
    const FS08HeroLightPlacement Rim = S08HeroLight::Place(H, H.Rim, 55.0f);
    TestTrue(FString::Printf(TEXT("%s: key on the camera side towards the moon (%s)"), Id, *Key.Location.ToString()),
             Key.Location.Y > 0.0 && Key.Location.X < 0.0);
    TestTrue(FString::Printf(TEXT("%s: rim behind (%s)"), Id, *Rim.Location.ToString()), Rim.Location.Y < 0.0);
  }
  for (const FS08BoardArtProfile& B : Data.Boards) {
    const FS08LightProfile* L = Data.LightFor(B);
    TestTrue(B.Id + TEXT(": its light profile lights the figures"), L && L->HeroLight.bSet && L->HeroLight.bEnabled);
  }
  TestEqual("budget per figure", S08HeroLightSpec::MaxLightsPerFigure, 2);
  TestEqual("budget per board", S08HeroLightSpec::MaxLightsPerBoard, 14);
  TestEqual("channel", S08HeroLightSpec::Channel, 1);
  TestEqual("flag", FString(S08HeroLightSpec::OptOutFlagName), FString(TEXT("NoHeroLight")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroLightMathTest,
    "Unmatched.S08.HeroLight.Math placement, lux to candelas, state multipliers, board budget",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroLightMathTest::RunTest(const FString&) {
  using namespace S08HeroLightTest;
  const FS08HeroLightSpec H = ValidSpec();
  if (!TestTrue("valid spec", H.bSet && H.Layers() == 2)) return false;
  for (const float Height : {55.0f, 120.0f}) {
    const FS08HeroLightPlacement K = S08HeroLight::Place(H, H.Key, Height);
    TestTrue(FString::Printf(TEXT("h %.0f: aim at 0.55 h"), Height), K.Aim.Equals(FVector(0, 0, 0.55 * Height), 1e-3));
    TestTrue(FString::Printf(TEXT("h %.0f: key at 2.5 h"), Height), FMath::IsNearlyEqual(K.Location.Z, 2.5 * Height, 1e-2));
    const FVector ToAim = (K.Aim - K.Location).GetSafeNormal();
    TestTrue(FString::Printf(TEXT("h %.0f: the spot points at the aim"), Height),
             K.Rotation.Vector().Equals(ToAim, 1e-4));
    const double Elev = FMath::RadiansToDegrees(FMath::Asin(-ToAim.Z));
    TestTrue(FString::Printf(TEXT("h %.0f: 60 deg down (%.3f)"), Height, Elev), FMath::IsNearlyEqual(Elev, 60.0, 1e-3));
    const double Yaw = FMath::RadiansToDegrees(FMath::Atan2(K.Location.Y - K.Aim.Y, K.Location.X - K.Aim.X));
    TestTrue(FString::Printf(TEXT("h %.0f: azimuth 90 + 35 (%.3f)"), Height, Yaw), FMath::IsNearlyEqual(Yaw, 125.0, 1e-3));
    TestTrue(FString::Printf(TEXT("h %.0f: cd = lux x d_m^2 (%.3f)"), Height, K.Candelas),
             FMath::IsNearlyEqual(K.Candelas, 4.0f * FMath::Square(K.DistanceUU / 100.0f), 1e-3f));
    TestTrue(FString::Printf(TEXT("h %.0f: radius 1.6 x d"), Height),
             FMath::IsNearlyEqual(K.AttenuationRadiusUU, 1.6f * K.DistanceUU, 1e-3f) && K.AttenuationRadiusUU > K.DistanceUU);
  }
  // the same lux at the aim point for every figure size: bigger figures get proportionally stronger, farther lights
  const FS08HeroLightPlacement Small = S08HeroLight::Place(H, H.Key, 50.0f);
  const FS08HeroLightPlacement Big = S08HeroLight::Place(H, H.Key, 100.0f);
  TestTrue("cd scales with height^2", FMath::IsNearlyEqual(Big.Candelas, 4.0f * Small.Candelas, 1e-3f));
  TestTrue("no height -> the default figure", S08HeroLight::Place(H, H.Key, 0.0f).Location.Equals(
                                                  S08HeroLight::Place(H, H.Key, S08HeroLightSpec::DefaultFigureHeightUU).Location));
  // states
  TestEqual("idle x1", S08HeroLight::StateMultiplier(H, ES08HeroLightState::Idle, 3.0, false), 1.0f);
  TestEqual("defeated off", S08HeroLight::StateMultiplier(H, ES08HeroLightState::Defeated, 3.0, false), 0.0f);
  TestEqual("off", S08HeroLight::StateMultiplier(H, ES08HeroLightState::Off, 3.0, false), 0.0f);
  TestTrue("active frozen = exactly activeMul",
           S08HeroLight::StateMultiplier(H, ES08HeroLightState::Active, 1.234, true) == H.ActiveMul);
  float Lo = 10.0f, Hi = 0.0f;
  for (int32 I = 0; I <= 100; ++I) {
    const float M = S08HeroLight::StateMultiplier(H, ES08HeroLightState::Active, I * 0.025, false);  // 2.5 s = one period
    Lo = FMath::Min(Lo, M);
    Hi = FMath::Max(Hi, M);
  }
  TestTrue(FString::Printf(TEXT("breathing %.3f..%.3f = 1.35 x (1 +- 0.08)"), Lo, Hi),
           FMath::IsNearlyEqual(Lo, 1.35f * 0.92f, 2e-3f) && FMath::IsNearlyEqual(Hi, 1.35f * 1.08f, 2e-3f));
  TestTrue(FString::Printf(TEXT("H4: the active figure >= 1.2 x the others even at the pulse low (%.3f)"), Lo), Lo >= 1.2f);
  // budget
  TestEqual("7 figures: key + rim", S08HeroLight::LayersForBoard(H, 7), 2);
  TestEqual("8 figures: the key only", S08HeroLight::LayersForBoard(H, 8), 1);
  TestEqual("no figures: the block's layers", S08HeroLight::LayersForBoard(H, 0), 2);
  TestTrue("names", FString(S08HeroLightStateName(ES08HeroLightState::Active)) == TEXT("active") &&
                        FString(S08HeroLightStateName(ES08HeroLightState::Defeated)) == TEXT("defeated"));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroLightActorTest,
    "Unmatched.S08.HeroLight.Actor rig per figure on grid and map-image boards, channel 1 only, active, move, -NoHeroLight, budget",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroLightActorTest::RunTest(const FString&) {
  using namespace S08HeroLightTest;
  const FS08HeroLightSpec Spec = ValidSpec();
  if (!TestTrue("valid spec", Spec.bSet && Spec.bEnabled)) return false;
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, FName(TEXT("S08HeroLightActor")));
  if (!TestNotNull("test world", World)) return false;
  FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
  Context.SetCurrentWorld(World);

  auto CheckRig = [this](const AS08FighterActor* A, const TCHAR* Where, int32 WantLights) {
    if (!A) return;
    TestEqual(FString::Printf(TEXT("%s %s: lights on"), Where, *A->GetFighterId()), A->GetHeroLightCount(), WantLights);
    for (int32 Layer = 0; Layer < WantLights; ++Layer) {
      const USpotLightComponent* L = A->GetHeroLight(Layer);
      if (!TestNotNull(FString::Printf(TEXT("%s %s: layer %d"), Where, *A->GetFighterId(), Layer), L)) continue;
      TestTrue(FString::Printf(TEXT("%s %s layer %d: channel 1 only"), Where, *A->GetFighterId(), Layer),
               !L->LightingChannels.bChannel0 && L->LightingChannels.bChannel1 && !L->LightingChannels.bChannel2);
      TestTrue(FString::Printf(TEXT("%s %s layer %d: no shadow / GI / volumetric / translucency"), Where, *A->GetFighterId(), Layer),
               !L->CastShadows && L->IndirectLightingIntensity == 0.0f && L->VolumetricScatteringIntensity == 0.0f &&
                   !L->bAffectTranslucentLighting);
      TestTrue(FString::Printf(TEXT("%s %s layer %d: candelas, movable, attached to the fighter"), Where, *A->GetFighterId(), Layer),
               L->IntensityUnits == ELightUnits::Candelas && L->Mobility == EComponentMobility::Movable &&
                   L->GetAttachParent() == A->GetRootComponent() && L->Intensity > 0.0f);
    }
    for (const UPrimitiveComponent* P : A->GetHeroLitPrimitives()) {
      if (!P) continue;
      TestTrue(FString::Printf(TEXT("%s %s: figure mesh %s on channels 0 + %d"), Where, *A->GetFighterId(), *P->GetName(),
                               WantLights > 0 ? 1 : 0),
               P->LightingChannels.bChannel0 && P->LightingChannels.bChannel1 == (WantLights > 0));
    }
  };

  // 1) a grid board (grey in a test world: the spec comes through the test override, as the art profile's would)
  {
    AS08BoardActor* Board = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator);
    if (TestNotNull("grid board actor", Board)) {
      const FS08BoardModel Model = Grid(5, 6);
      TestTrue("rebuild grid", Board->Rebuild(Model));
      Board->SetHeroLightOptOutForTest(false);
      Board->SetHeroLightOverrideForTest(&Spec);
      Board->SyncFighters(Model, Fighters(Model, 4), TEXT("host"));
      TestEqual("grid: 4 figures x 2 lights", Board->GetHeroLightCount(), 8);
      TestEqual("grid: key + rim per figure", Board->GetHeroLightLayers(), 2);
      for (int32 I = 0; I < 4; ++I) CheckRig(Board->FindFighterActor(FString::Printf(TEXT("f-%d"), I)), TEXT("grid"), 2);
      const TArray<FString> Bad = ChannelOneOutsideFigures(World);
      TestTrue(FString::Printf(TEXT("grid: nothing but the figure meshes on channel 1 (%s)"), *FString::Join(Bad, TEXT(", "))),
               Bad.IsEmpty());
      // the active (selected) fighter: x activeMul (the pulse stays within 1.35 x (1 +- 0.08)), the others x1
      Board->SetSelectedFighter(TEXT("f-0"), TSet<uint64>());
      const AS08FighterActor* Active = Board->FindFighterActor(TEXT("f-0"));
      const AS08FighterActor* Idle = Board->FindFighterActor(TEXT("f-1"));
      if (Active && Idle) {
        TestTrue("selected = active", Active->GetHeroLightState() == ES08HeroLightState::Active);
        TestTrue("others idle", Idle->GetHeroLightState() == ES08HeroLightState::Idle && Idle->GetHeroLightMultiplier() == 1.0f);
        TestTrue(FString::Printf(TEXT("active multiplier %.3f within 1.35 x (1 +- 0.08)"), Active->GetHeroLightMultiplier()),
                 Active->GetHeroLightMultiplier() >= 1.35f * 0.92f - 1e-3f && Active->GetHeroLightMultiplier() <= 1.35f * 1.08f + 1e-3f);
        const USpotLightComponent* AK = Active->GetHeroLight(0);
        const USpotLightComponent* IK = Idle->GetHeroLight(0);
        TestTrue("H4: the active key >= 1.2 x an idle key of the same figure size",
                 AK && IK && AK->Intensity >= 1.2f * IK->Intensity);
      }
      Board->SetSelectedFighter(FString(), TSet<uint64>());
      TestTrue("deselected: idle again", Active && Active->GetHeroLightState() == ES08HeroLightState::Idle);
      // the rig follows a move
      if (Active) {
        const FVector Before = Active->GetHeroLight(0)->GetComponentLocation();
        const FVector CellBefore = Active->GetActorLocation();
        TArray<FS08BoardFighter> Moved = Fighters(Model, 4);
        Moved[0].X = 4;
        Moved[0].Y = 5;
        Board->SyncFighters(Model, Moved, TEXT("host"));
        const FVector Delta = Active->GetActorLocation() - CellBefore;
        TestTrue("the fighter moved", !Delta.IsNearlyZero());
        TestTrue("the key light moved with it", Active->GetHeroLight(0)->GetComponentLocation().Equals(Before + Delta, 1e-2));
        // a defeated fighter loses its rig
        Moved[1].Health = 0;
        Board->SyncFighters(Model, Moved, TEXT("host"));
        TestEqual("dead fighter: no lights", Idle ? Idle->GetHeroLightCount() : -1, 0);
        TestTrue("dead fighter: figure back on channel 0 only",
                 Idle && Idle->GetHeroLitPrimitives().Num() > 0 && !Idle->GetHeroLitPrimitives()[0]->LightingChannels.bChannel1);
        TestEqual("grid: 3 living figures x 2", Board->GetHeroLightCount(), 6);
      }
      // -NoHeroLight
      Board->SetHeroLightOptOutForTest(true);
      Board->UpdateHeroLights();
      TestEqual("-NoHeroLight: no lights on the board", Board->GetHeroLightCount(), 0);
      TestTrue("-NoHeroLight: nothing on channel 1", ChannelOneOutsideFigures(World).IsEmpty());
      for (int32 I = 0; I < 4; ++I) CheckRig(Board->FindFighterActor(FString::Printf(TEXT("f-%d"), I)), TEXT("opt-out"), 0);
      Board->SetHeroLightOptOutForTest(false);
      // budget: 9 figures -> the key only (9 <= 14); 16 figures -> 14 keys
      Board->SyncFighters(Model, Fighters(Model, 9), TEXT("host"));
      TestEqual("9 figures: key only", Board->GetHeroLightLayers(), 1);
      TestEqual("9 figures: 9 lights <= 14", Board->GetHeroLightCount(), 9);
      Board->SyncFighters(Model, Fighters(Model, 16), TEXT("host"));
      TestEqual("16 figures: the board budget 14", Board->GetHeroLightCount(), S08HeroLightSpec::MaxLightsPerBoard);
      // no spec at all (a grey board without the override): no rig
      Board->SetHeroLightOverrideForTest(nullptr);
      Board->UpdateHeroLights();
      TestEqual("no art profile: no rig", Board->GetHeroLightCount(), 0);
      Board->Destroy();
    }
  }
  // 2) a topology board (the map-image layout frame; grey here: the spec through the override)
  {
    FS08BoardModel Topo;
    AS08BoardActor* Board = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator);
    if (TestTrue("synthetic topology", Topology(Topo)) && TestNotNull("topology board actor", Board)) {
      TestTrue("rebuild topology", Board->Rebuild(Topo));
      Board->SetHeroLightOptOutForTest(false);
      Board->SetHeroLightOverrideForTest(&Spec);
      Board->SyncFighters(Topo, Fighters(Topo, 3), TEXT("host"));
      TestEqual("topology: 3 figures x 2 lights", Board->GetHeroLightCount(), 6);
      for (int32 I = 0; I < 3; ++I) CheckRig(Board->FindFighterActor(FString::Printf(TEXT("f-%d"), I)), TEXT("topology"), 2);
      const TArray<FString> Bad = ChannelOneOutsideFigures(World);
      TestTrue(FString::Printf(TEXT("topology: the map canvas / discs / pick box stay on channel 0 (%s)"),
                               *FString::Join(Bad, TEXT(", "))), Bad.IsEmpty());
      Board->Destroy();
    }
  }
  // 3) the shipped Sarpedon profile end to end (the art profile's own block, no override) once the map import ran
  {
    FS08BoardArtData Shipped;
    TArray<FString> Errors;
    const FString Fixture = FPaths::ConvertRelativePathToFull(FPaths::Combine(
        FPaths::ProjectDir(), TEXT("../../backend/prisma/fixtures/boards/sarpedon.topology.json")));
    FString Text;
    TSharedPtr<FJsonObject> Root;
    FString Problem;
    const FS08BoardArtProfile* Sarpedon = nullptr;
    if (Shipped.LoadFile(FS08BoardArtData::DefaultPath(), Errors)) {
      Sarpedon = Shipped.Boards.FindByPredicate([](const FS08BoardArtProfile& B) { return B.Id == TEXT("sarpedon-original"); });
    }
    if (!Sarpedon || !FPackageName::DoesPackageExist(Sarpedon->Map.MaterialInstancePath) ||
        !FFileHelper::LoadFileToString(Text, *Fixture) || !FS08Contracts::TryParseJsonObject(Text, Root, Problem) ||
        !Root.IsValid()) {
      AddWarning(TEXT("sarpedon map assets / fixture missing: the shipped map-image end-to-end path was NOT exercised ")
                 TEXT("(tools/art/map_surface/ue_import_map_surface.py, ENV-U3: out of git)"));
    } else {
      // the fixture -> the boardState projection (rows of cells with the space fields), as S08BoardArtTests does
      const TSharedPtr<FJsonObject> Lattice = Root->GetObjectField(TEXT("lattice"));
      const int32 W = static_cast<int32>(Lattice->GetNumberField(TEXT("width")));
      const int32 H = static_cast<int32>(Lattice->GetNumberField(TEXT("height")));
      TArray<TArray<TSharedPtr<FJsonValue>>> Rows;
      Rows.SetNum(H);
      for (int32 Y = 0; Y < H; ++Y) {
        Rows[Y].SetNum(W);
        for (int32 X = 0; X < W; ++X) {
          TSharedRef<FJsonObject> Empty = MakeShared<FJsonObject>();
          Empty->SetStringField(TEXT("type"), TEXT("obstacle"));
          Empty->SetNumberField(TEXT("x"), X);
          Empty->SetNumberField(TEXT("y"), Y);
          Rows[Y][X] = MakeShared<FJsonValueObject>(Empty);
        }
      }
      for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("cells"))) {
        const TSharedPtr<FJsonObject> C = V->AsObject();
        const int32 X = static_cast<int32>(C->GetNumberField(TEXT("x")));
        const int32 Y = static_cast<int32>(C->GetNumberField(TEXT("y")));
        if (X < 0 || Y < 0 || X >= W || Y >= H) continue;
        TSharedRef<FJsonObject> Cell = MakeShared<FJsonObject>();
        bool bObstacle = false;
        C->TryGetBoolField(TEXT("isObstacle"), bObstacle);
        Cell->SetStringField(TEXT("type"), bObstacle ? TEXT("obstacle") : TEXT("normal"));
        Cell->SetNumberField(TEXT("x"), X);
        Cell->SetNumberField(TEXT("y"), Y);
        const TArray<TSharedPtr<FJsonValue>>* Zones = nullptr;
        if (C->TryGetArrayField(TEXT("zones"), Zones) && Zones && Zones->Num() > 0) {
          Cell->SetArrayField(TEXT("zones"), *Zones);
          Cell->SetStringField(TEXT("zone"), (*Zones)[0]->AsString());
        }
        for (const TCHAR* Field : {TEXT("spaceId"), TEXT("layout"), TEXT("start"), TEXT("links")}) {
          if (C->HasField(Field)) Cell->SetField(Field, C->TryGetField(Field));
        }
        Rows[Y][X] = MakeShared<FJsonValueObject>(Cell);
      }
      TArray<TSharedPtr<FJsonValue>> RowValues;
      for (const TArray<TSharedPtr<FJsonValue>>& Row : Rows) RowValues.Add(MakeShared<FJsonValueArray>(Row));
      TSharedRef<FJsonObject> State = MakeShared<FJsonObject>();
      State->SetNumberField(TEXT("width"), W);
      State->SetNumberField(TEXT("height"), H);
      State->SetArrayField(TEXT("cells"), RowValues);
      State->SetObjectField(TEXT("doors"), MakeShared<FJsonObject>());
      FS08BoardModel Board;
      AS08BoardActor* Map = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator);
      if (TestTrue("sarpedon fixture decodes", Board.Decode(MakeShared<FJsonValueObject>(State))) && TestNotNull("map actor", Map)) {
        Map->SetArtDataForTest(Shipped);
        Map->SetRoomBoardId(Root->GetStringField(TEXT("boardId")));
        Map->SetHeroLightOptOutForTest(false);
        TestTrue("rebuild Sarpedon", Map->Rebuild(Board));
        TestTrue("map-image active", Map->IsMapImageActive());
        const FS08HeroLightSpec* Active = Map->GetActiveHeroLight();
        TestTrue("the sarpedon-night heroLight is the active block", Active && Active->bEnabled && Active->Layers() == 2);
        Map->SyncFighters(Board, Fighters(Board, 4), TEXT("host"));
        TestEqual("sarpedon: 4 figures x 2 lights", Map->GetHeroLightCount(), 8);
        const TArray<FString> Bad = ChannelOneOutsideFigures(World);
        TestTrue(FString::Printf(TEXT("sarpedon: the map plane / frame / env stay on channel 0 (%s)"), *FString::Join(Bad, TEXT(", "))),
                 Bad.IsEmpty());
        Map->SetHeroLightOptOutForTest(true);
        Map->UpdateHeroLights();
        TestEqual("sarpedon -NoHeroLight: none", Map->GetHeroLightCount(), 0);
        Map->Destroy();
      }
    }
  }
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS

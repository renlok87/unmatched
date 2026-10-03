// ENV-MAPS P9 hero light automation tests (S08HeroLight.h, docs/art-pipeline/ENV-HERO-LIGHT.md):
//   Parse      the "heroLight" block: valid / absent / every broken field refused (the document fails);
//   Shipped    every light profile of S08ArtBoardProfiles.json (Marmoreal, Sarpedon, Cobble + probes: «Все сцены») has an
//              enabled key + rim block, the budget constants, and the P9b accent logic (review 2026-10-02 «сильно
//              пересвечены»): the key from the moon side 60-90 deg off the camera, 40-50 deg down, 1-2 x the moon key's lux,
//              reduced specular, contact shadows; the rim low (12-22 deg) behind the figure, <= 0.5 x the key; active
//              x 1.08..1.2, breathing <= 5 %, the pedestal unlit;
//   Math       Place (moon side / behind, the aim, lux -> cd, cone, radius), StateMultiplier (active x activeMul, frozen,
//              the breathing pulse, defeated off), LayersForBoard (<= 2 per figure, <= 14 per board);
//   Actor      a grid board and a topology (map-image layout) board: a rig per figure, lighting channel 1 only, never a
//              shadow map (contact shadows only where the layer asks), no GI / translucency, the layer specular scale,
//              the figure body on channels 0 + 1, the pedestal on channel 0 unless litPedestal, nothing else of the world
//              on channel 1 (tiles, map plane, frame, rings, labels), the active fighter x activeMul, the rig follows a
//              move, a dead fighter has none, -NoHeroLight removes it all, the board budget; the shipped Sarpedon profile
//              end to end when the map assets are imported.
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

/** A valid heroLight block (P9b-style accent values: the key from the moon side, a low rim behind, contact shadows). */
const TCHAR* const ValidBlock = TEXT(
    "{\"enabled\":true,\"note\":\"t\",\"cameraAzimuthDeg\":90,\"aimHeight\":0.55,\"litPedestal\":false,"
    "\"key\":{\"lux\":6,\"colorSrgb\":\"#FFE4C4\",\"innerConeDeg\":18,\"outerConeDeg\":28,\"heightMul\":2.5,\"azimuthDeg\":75,"
    "\"elevationDeg\":45,\"radiusMul\":1.6,\"specularScale\":0.4,\"contactShadowLength\":0.08},"
    "\"rim\":{\"lux\":2.4,\"colorSrgb\":\"#A8C0FF\",\"innerConeDeg\":12,\"outerConeDeg\":20,\"heightMul\":1.0,\"azimuthDeg\":160,"
    "\"elevationDeg\":18,\"radiusMul\":1.6,\"specularScale\":0.7},"
    "\"states\":{\"activeMul\":1.15,\"breathHz\":0.4,\"breathAmp\":0.04,\"defeatedMul\":0}}");

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

/** ValidBlock with Old replaced by New (every occurrence; the cases use unique substrings). */
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
      TestTrue("key values", H.Key.Lux == 6.0f && H.Key.InnerConeDeg == 18.0f && H.Key.OuterConeDeg == 28.0f &&
                                 H.Key.HeightMul == 2.5f && H.Key.AzimuthDeg == 75.0f && H.Key.ElevationDeg == 45.0f &&
                                 H.Key.ColorSrgb == FColor(0xFF, 0xE4, 0xC4));
      TestTrue("key specular / contact shadow", FMath::IsNearlyEqual(H.Key.SpecularScale, 0.4f) &&
                                                    FMath::IsNearlyEqual(H.Key.ContactShadowLength, 0.08f) && H.Key.HasContactShadow());
      TestTrue("rim values", FMath::IsNearlyEqual(H.Rim.Lux, 2.4f) && H.Rim.ColorSrgb == FColor(0xA8, 0xC0, 0xFF) &&
                                 H.Rim.AzimuthDeg == 160.0f && H.Rim.ElevationDeg == 18.0f && H.Rim.HeightMul == 1.0f);
      TestTrue("rim specular, no contact shadow (absent = 0)", FMath::IsNearlyEqual(H.Rim.SpecularScale, 0.7f) &&
                                                                    H.Rim.ContactShadowLength == 0.0f && !H.Rim.HasContactShadow());
      TestTrue("states", FMath::IsNearlyEqual(H.ActiveMul, 1.15f) && FMath::IsNearlyEqual(H.BreathHz, 0.4f) &&
                             FMath::IsNearlyEqual(H.BreathAmp, 0.04f) && H.DefeatedMul == 0.0f);
      TestTrue("camera azimuth / aim / pedestal unlit", H.CameraAzimuthDeg == 90.0f && FMath::IsNearlyEqual(H.AimHeight, 0.55f) &&
                                                            !H.bLitPedestal);
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
    // P9b defaults: no specularScale / contactShadowLength / litPedestal = 1 / 0 / false (the P9 behaviour of the layers)
    FS08BoardArtData Data;
    TArray<FString> Errors;
    FString Plain = Broken(TEXT(",\"specularScale\":0.4,\"contactShadowLength\":0.08"), TEXT(""));
    Plain.ReplaceInline(TEXT(",\"specularScale\":0.7"), TEXT(""));
    Plain.ReplaceInline(TEXT("\"litPedestal\":false,"), TEXT(""));
    TestTrue("block without the P9b fields parses", Data.ParseJson(Doc(Plain), Errors));
    const FS08LightProfile* L = Data.Lights.Find(TEXT("L"));
    TestTrue("defaults: specular 1, no contact shadow, pedestal unlit",
             L && L->HeroLight.Key.SpecularScale == 1.0f && L->HeroLight.Rim.SpecularScale == 1.0f &&
                 L->HeroLight.Key.ContactShadowLength == 0.0f && !L->HeroLight.bLitPedestal);
  }
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    TestTrue("litPedestal true parses",
             Data.ParseJson(Doc(Broken(TEXT("\"litPedestal\":false"), TEXT("\"litPedestal\":true"))), Errors));
    const FS08LightProfile* L = Data.Lights.Find(TEXT("L"));
    TestTrue("litPedestal true", L && L->HeroLight.bLitPedestal);
    const FS08HeroLightSpec Unlit = ValidSpec();
    TestTrue("the pedestal flag changes the rig signature", L && L->HeroLight.Signature() != Unlit.Signature());
  }
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    TestTrue("key only parses", Data.ParseJson(Doc(Broken(
        TEXT(",\"rim\":{\"lux\":2.4,\"colorSrgb\":\"#A8C0FF\",\"innerConeDeg\":12,\"outerConeDeg\":20,\"heightMul\":1.0,\"azimuthDeg\":160,"
             "\"elevationDeg\":18,\"radiusMul\":1.6,\"specularScale\":0.7}"), TEXT(""))), Errors));
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
      {TEXT("key lux 0"), TEXT("\"lux\":6"), TEXT("\"lux\":0")},
      {TEXT("key lux 60"), TEXT("\"lux\":6"), TEXT("\"lux\":60")},
      {TEXT("bad colour"), TEXT("#FFE4C4"), TEXT("FFE4C4")},
      {TEXT("inner cone > outer"), TEXT("\"innerConeDeg\":18"), TEXT("\"innerConeDeg\":40")},
      {TEXT("elevation 90"), TEXT("\"elevationDeg\":45"), TEXT("\"elevationDeg\":90")},
      {TEXT("light below the aim point"), TEXT("\"heightMul\":2.5"), TEXT("\"heightMul\":0.6")},
      {TEXT("unknown layer field"), TEXT("\"contactShadowLength\":0.08},\"rim\""),
       TEXT("\"contactShadowLength\":0.08,\"shadow\":true},\"rim\"")},
      {TEXT("specularScale 1.5"), TEXT("\"specularScale\":0.4"), TEXT("\"specularScale\":1.5")},
      {TEXT("specularScale -0.1"), TEXT("\"specularScale\":0.7"), TEXT("\"specularScale\":-0.1")},
      {TEXT("contactShadowLength 0.6"), TEXT("\"contactShadowLength\":0.08"), TEXT("\"contactShadowLength\":0.6")},
      {TEXT("contactShadowLength -0.01"), TEXT("\"contactShadowLength\":0.08"), TEXT("\"contactShadowLength\":-0.01")},
      {TEXT("litPedestal not a bool"), TEXT("\"litPedestal\":false"), TEXT("\"litPedestal\":\"no\"")},
      {TEXT("activeMul 0.5"), TEXT("\"activeMul\":1.15"), TEXT("\"activeMul\":0.5")},
      {TEXT("breathAmp 0.9"), TEXT("\"breathAmp\":0.04"), TEXT("\"breathAmp\":0.9")},
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
  // 2026-10-04 (real boards only): the probe profiles of the synthetic boards are gone; the two map profiles remain
  TestEqual("two light profiles", Data.Lights.Num(), 2);
  for (const TCHAR* Id : {TEXT("marmoreal-night"), TEXT("sarpedon-night")}) {
    const FS08LightProfile* L = Data.Lights.Find(Id);
    if (!TestNotNull(FString::Printf(TEXT("light profile %s"), Id), L)) continue;
    const FS08HeroLightSpec& H = L->HeroLight;
    TestTrue(FString::Printf(TEXT("%s: heroLight enabled, key + rim"), Id), H.bSet && H.bEnabled && H.Layers() == 2);
    // the key colour: a light tint against the board's colour cast on the figures (near-neutral, the cool moon white on
    // Marmoreal); the rim cool
    const int32 KeyMin = FMath::Min3<int32>(H.Key.ColorSrgb.R, H.Key.ColorSrgb.G, H.Key.ColorSrgb.B);
    const int32 KeyMax = FMath::Max3<int32>(H.Key.ColorSrgb.R, H.Key.ColorSrgb.G, H.Key.ColorSrgb.B);
    TestTrue(FString::Printf(TEXT("%s: rim <= 0.5 x the key, cool rim, light key tint (%s)"), Id, *H.Key.ColorSrgb.ToHex()),
             H.Rim.Lux <= 0.5f * H.Key.Lux + 1e-4f && H.Rim.ColorSrgb.B > H.Rim.ColorSrgb.R && KeyMax == 255 && KeyMin >= 0xC8);
    // P9b: an accent, not a main light - the active figure x 1.08..1.2 (P9 x 1.35 made it 2.77 x the others), a gentle
    // breathing pulse, a defeated figure dark
    TestTrue(FString::Printf(TEXT("%s: active x %.2f in 1.08..1.2, breathing %.2f <= 0.05, defeated off"), Id, H.ActiveMul, H.BreathAmp),
             H.ActiveMul >= 1.08f && H.ActiveMul <= 1.2f && H.BreathAmp <= 0.05f && H.DefeatedMul == 0.0f);
    // the environment budget is untouched: 1 key + <= 6 points (the hero light is its own category)
    FString Reason;
    TestTrue(FString::Printf(TEXT("%s: environment budget still ok"), Id), L->BudgetOk(Reason));
    // P9b key: 1-2 x the profile's moon key (lux), from the moon side 60-90 deg off the camera azimuth, 40-50 deg down,
    // less specular, contact shadows on; the pedestal stays unlit
    const float MoonLux = L->Directional.Intensity;
    TestTrue(FString::Printf(TEXT("%s: key %.2f lux within 1..2 x the moon key %.2f lux"), Id, H.Key.Lux, MoonLux),
             H.Key.Lux >= 1.0f * MoonLux - 1e-3f && H.Key.Lux <= 2.0f * MoonLux + 1e-3f);
    TestTrue(FString::Printf(TEXT("%s: key azimuth +%.0f (moon side, 60..90 off the camera), elevation %.0f in 40..50"), Id,
                             H.Key.AzimuthDeg, H.Key.ElevationDeg),
             H.Key.AzimuthDeg >= 60.0f && H.Key.AzimuthDeg <= 90.0f && H.Key.ElevationDeg >= 40.0f && H.Key.ElevationDeg <= 50.0f);
    TestTrue(FString::Printf(TEXT("%s: key specular %.2f in 0.3..0.5, contact shadow %.3f in 0.03..0.12"), Id, H.Key.SpecularScale,
                             H.Key.ContactShadowLength),
             H.Key.SpecularScale >= 0.3f && H.Key.SpecularScale <= 0.5f && H.Key.ContactShadowLength >= 0.03f &&
                 H.Key.ContactShadowLength <= 0.12f);
    TestTrue(FString::Printf(TEXT("%s: rim low (%.0f deg in 12..22) behind the figure (azimuth %.0f), specular %.2f in 0.6..0.8"), Id,
                             H.Rim.ElevationDeg, H.Rim.AzimuthDeg, H.Rim.SpecularScale),
             H.Rim.ElevationDeg >= 12.0f && H.Rim.ElevationDeg <= 22.0f && FMath::Abs(H.Rim.AzimuthDeg) >= 135.0f &&
                 FMath::Abs(H.Rim.AzimuthDeg) <= 225.0f && H.Rim.SpecularScale >= 0.6f && H.Rim.SpecularScale <= 0.8f);
    TestTrue(FString::Printf(TEXT("%s: pedestal unlit"), Id), !H.bLitPedestal);
    // world placement: the camera sits at +Y (cameraAzimuthDeg 90), the moon key (-55, 30, 0) comes from yaw 210 (-X -Y):
    // the key stands on the -X (moon) side, at least as close to the moon's azimuth as to the camera's; the rim behind (-Y)
    const FS08HeroLightPlacement Key = S08HeroLight::Place(H, H.Key, 55.0f);
    const FS08HeroLightPlacement Rim = S08HeroLight::Place(H, H.Rim, 55.0f);
    const double KeyYaw = FMath::RadiansToDegrees(FMath::Atan2(Key.Location.Y, Key.Location.X));
    const double MoonYaw = static_cast<double>(L->Directional.Rotation.Yaw) + 180.0;
    TestTrue(FString::Printf(TEXT("%s: key on the moon side (%s, yaw %.0f, moon from %.0f)"), Id, *Key.Location.ToString(), KeyYaw, MoonYaw),
             Key.Location.X < 0.0 && FMath::Abs(FMath::FindDeltaAngleDegrees(KeyYaw, MoonYaw)) <=
                                         FMath::Abs(FMath::FindDeltaAngleDegrees(KeyYaw, static_cast<double>(H.CameraAzimuthDeg))) + 1e-3);
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
    const FS08HeroLightPlacement R = S08HeroLight::Place(H, H.Rim, Height);
    const double RimElev = FMath::RadiansToDegrees(FMath::Asin(-(R.Aim - R.Location).GetSafeNormal().Z));
    TestTrue(FString::Printf(TEXT("h %.0f: low rim 18 deg down at 1.0 h (%.3f)"), Height, RimElev),
             FMath::IsNearlyEqual(RimElev, 18.0, 1e-3) && FMath::IsNearlyEqual(R.Location.Z, 1.0 * Height, 1e-2));
    const FVector ToAim = (K.Aim - K.Location).GetSafeNormal();
    TestTrue(FString::Printf(TEXT("h %.0f: the spot points at the aim"), Height),
             K.Rotation.Vector().Equals(ToAim, 1e-4));
    const double Elev = FMath::RadiansToDegrees(FMath::Asin(-ToAim.Z));
    TestTrue(FString::Printf(TEXT("h %.0f: 45 deg down (%.3f)"), Height, Elev), FMath::IsNearlyEqual(Elev, 45.0, 1e-3));
    const double Yaw = FMath::RadiansToDegrees(FMath::Atan2(K.Location.Y - K.Aim.Y, K.Location.X - K.Aim.X));
    TestTrue(FString::Printf(TEXT("h %.0f: azimuth 90 + 75 (%.3f)"), Height, Yaw), FMath::IsNearlyEqual(Yaw, 165.0, 1e-3));
    TestTrue(FString::Printf(TEXT("h %.0f: cd = lux x d_m^2 (%.3f)"), Height, K.Candelas),
             FMath::IsNearlyEqual(K.Candelas, 6.0f * FMath::Square(K.DistanceUU / 100.0f), 1e-3f));
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
  TestTrue(FString::Printf(TEXT("breathing %.3f..%.3f = 1.15 x (1 +- 0.04)"), Lo, Hi),
           FMath::IsNearlyEqual(Lo, 1.15f * 0.96f, 2e-3f) && FMath::IsNearlyEqual(Hi, 1.15f * 1.04f, 2e-3f));
  TestTrue(FString::Printf(TEXT("P9b: the active figure stays above the idle ones at the pulse low (%.3f), no flare at the high (%.3f)"),
                           Lo, Hi),
           Lo > 1.05f && Hi <= 1.25f);
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

  auto CheckRig = [this, &Spec](const AS08FighterActor* A, const TCHAR* Where, int32 WantLights) {
    if (!A) return;
    TestEqual(FString::Printf(TEXT("%s %s: lights on"), Where, *A->GetFighterId()), A->GetHeroLightCount(), WantLights);
    for (int32 Layer = 0; Layer < WantLights; ++Layer) {
      const USpotLightComponent* L = A->GetHeroLight(Layer);
      if (!TestNotNull(FString::Printf(TEXT("%s %s: layer %d"), Where, *A->GetFighterId(), Layer), L)) continue;
      TestTrue(FString::Printf(TEXT("%s %s layer %d: channel 1 only"), Where, *A->GetFighterId(), Layer),
               !L->LightingChannels.bChannel0 && L->LightingChannels.bChannel1 && !L->LightingChannels.bChannel2);
      TestTrue(FString::Printf(TEXT("%s %s layer %d: no GI / volumetric / translucency"), Where, *A->GetFighterId(), Layer),
               L->IndirectLightingIntensity == 0.0f && L->VolumetricScatteringIntensity == 0.0f && !L->bAffectTranslucentLighting &&
                   !L->bAffectGlobalIllumination);
      // P9b: never a shadow map; a layer with contactShadowLength > 0 casts screen-space contact shadows only
      const FS08HeroLightLayer& Want = Layer == 0 ? Spec.Key : Spec.Rim;
      TestTrue(FString::Printf(TEXT("%s %s layer %d: shadow maps off (resolution scale %.2f), contact %.3f = %.3f, cast %d = %d"), Where,
                               *A->GetFighterId(), Layer, L->ShadowResolutionScale, L->ContactShadowLength, Want.ContactShadowLength,
                               L->CastShadows ? 1 : 0, Want.HasContactShadow() ? 1 : 0),
               L->ShadowResolutionScale == 0.0f && FMath::IsNearlyEqual(L->ContactShadowLength, Want.ContactShadowLength) &&
                   !L->ContactShadowLengthInWS && static_cast<bool>(L->CastShadows) == Want.HasContactShadow());
      TestTrue(FString::Printf(TEXT("%s %s layer %d: specular scale %.2f = %.2f"), Where, *A->GetFighterId(), Layer, L->SpecularScale,
                               Want.SpecularScale),
               FMath::IsNearlyEqual(L->SpecularScale, Want.SpecularScale));
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
    // P9b: the pedestal (ArtBase) stays on channel 0 only (litPedestal false in the spec): no more cream disks
    if (const UPrimitiveComponent* Pedestal = A->GetHeroPedestal()) {
      TestTrue(FString::Printf(TEXT("%s %s: pedestal on channel 0 only"), Where, *A->GetFighterId()),
               Pedestal->LightingChannels.bChannel0 && !Pedestal->LightingChannels.bChannel1 &&
                   !A->GetHeroLitPrimitives().Contains(Pedestal));
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
        TestTrue(FString::Printf(TEXT("active multiplier %.3f within 1.15 x (1 +- 0.04)"), Active->GetHeroLightMultiplier()),
                 Active->GetHeroLightMultiplier() >= 1.15f * 0.96f - 1e-3f && Active->GetHeroLightMultiplier() <= 1.15f * 1.04f + 1e-3f);
        const USpotLightComponent* AK = Active->GetHeroLight(0);
        const USpotLightComponent* IK = Idle->GetHeroLight(0);
        TestTrue("P9b: the active key 1.08..1.25 x an idle key of the same figure size (an accent, not a flare)",
                 AK && IK && AK->Intensity >= 1.08f * IK->Intensity && AK->Intensity <= 1.25f * IK->Intensity);
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
      // litPedestal true: the pedestal joins channel 1 (and the lit list); false again: back on channel 0 only
      {
        FS08HeroLightSpec Lit = Spec;
        Lit.bLitPedestal = true;
        Board->SetHeroLightOverrideForTest(&Lit);
        Board->UpdateHeroLights();
        const AS08FighterActor* F0 = Board->FindFighterActor(TEXT("f-0"));
        const UPrimitiveComponent* Pedestal = F0 ? F0->GetHeroPedestal() : nullptr;
        TestTrue("litPedestal: the pedestal on channels 0 + 1 and in the lit list",
                 Pedestal && Pedestal->LightingChannels.bChannel0 && Pedestal->LightingChannels.bChannel1 &&
                     F0->GetHeroLitPrimitives().Contains(Pedestal));
        TestTrue("litPedestal: still nothing but figure meshes on channel 1", ChannelOneOutsideFigures(World).IsEmpty());
        Board->SetHeroLightOverrideForTest(&Spec);
        Board->UpdateHeroLights();
        TestTrue("litPedestal false again: the pedestal back on channel 0 only",
                 Pedestal && !Pedestal->LightingChannels.bChannel1 && !F0->GetHeroLitPrimitives().Contains(Pedestal));
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

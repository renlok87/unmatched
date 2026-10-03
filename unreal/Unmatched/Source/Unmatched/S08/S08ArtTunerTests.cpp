// Art Tuner M2 automation tests (S08ArtTuner.h, docs/art-pipeline/ART-TUNER-PLAN.md §9):
//   Pointer      RFC 6901 split / escape / get / set (objects in place, arrays rebuilt, a new leaf only when allowed);
//   Values       saved number text, #RRGGBB, the writes of every row type (snap, hard bounds, ev100 -> min = max);
//   Registry     the shipped Config/ArtTuner/S08ArtTunerParams.json parses; the rows of Sarpedon / Cobble expand from the
//                shipped profile; every row points into the document;
//   Ranges       the registry's hard bounds ARE the C++ parser's: on every shipped board each number row passes at its
//                min / max and the document is refused one step outside a hard bound (rows checked together skipped);
//   Model        entries: equal to the base -> gone, type / pointer checks, build = the parser's data;
//   Overrides    S08ArtTuner.overrides.json round trip, other boards kept, value text kept, broken entries skipped;
//   Apply        AS08BoardActor::ApplyTunedArtData on a built board: the key / point / fog / hero rig values reach the
//                spawned components without a rebuild, and a full rebuild of the same document gives the same values;
//   OffByDefault no -ArtTuner / -ArtTunerFile in this process.
//   UnrealEditor-Cmd.exe Unmatched.uproject -ExecCmds="Automation RunTests Unmatched.S08.ArtTuner; Quit" -unattended -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08ArtTuner.h"
#include "S08BoardActor.h"
#include "S08BoardArt.h"
#include "S08BoardModel.h"
#include "S08FighterActor.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SpotLightComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/DirectionalLight.h"
#include "Engine/Engine.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/PointLight.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace S08ArtTunerTest {
TSharedPtr<FJsonObject> Obj(const FString& Text) {
  TSharedPtr<FJsonObject> O;
  const TSharedRef<TJsonReader<>> R = TJsonReaderFactory<>::Create(Text);
  FJsonSerializer::Deserialize(R, O);
  return O;
}

TSharedPtr<FJsonValue> Num(double V) { return MakeShared<FJsonValueNumber>(V); }
TSharedPtr<FJsonValue> NumText(const FString& S) { return MakeShared<FJsonValueNumberString>(S); }

/** A minimal valid profile document: light profile L (key, one point, fog, hero light), one tiles board. */
FString Doc(float KeyLux = 6.0f) {
  return FString::Printf(TEXT(
      "{\"schema\":\"unmatched.s08-art-board-profiles/1\",\"revision\":7,"
      "\"zoneStyles\":{\"a\":{\"stroke\":\"solid\",\"glyph\":\"diamond\",\"color\":\"#102030\"},"
      "\"b\":{\"stroke\":\"dash2\",\"glyph\":\"ring\",\"color\":\"#A0B0C0\"}},"
      "\"fallbackZoneStyle\":{\"stroke\":\"dots5\",\"glyph\":\"bar1\",\"color\":\"#FFFFFF\"},"
      "\"lightProfiles\":{\"L\":{\"directional\":{\"name\":\"key\",\"posUU\":[0,0,600],\"rotation\":[-55,30,0],"
      "\"intensity\":3,\"castShadows\":true},\"points\":[{\"name\":\"p\",\"at\":[0.5,-0.5,200],\"intensity\":50,"
      "\"radiusUU\":300}],"
      "\"fog\":{\"colorLinear\":[0.2,0.25,0.46],\"density\":0.3,\"heightFalloff\":0.2,\"heightZ\":-400,"
      "\"startDistanceUU\":2900,\"endDistanceUU\":6000,\"maxOpacity\":1.0},"
      "\"heroLight\":{\"enabled\":true,\"cameraAzimuthDeg\":90,\"aimHeight\":0.55,\"litPedestal\":false,"
      "\"key\":{\"lux\":%g,\"colorSrgb\":\"#FFE4C4\",\"innerConeDeg\":18,\"outerConeDeg\":28,\"heightMul\":2.5,\"azimuthDeg\":75,"
      "\"elevationDeg\":45,\"radiusMul\":1.6,\"specularScale\":0.4},"
      "\"states\":{\"activeMul\":1.15,\"breathHz\":0.4,\"breathAmp\":0.04,\"defeatedMul\":0}}}},"
      "\"boards\":[{\"id\":\"one\",\"match\":{\"boardIds\":[\"cid1\"],\"width\":3,\"height\":2,\"zoneKeys\":[\"b\",\"a\"]},"
      "\"surface\":\"tiles\",\"light\":\"L\",\"expect\":{\"cells\":6,\"zoneCells\":6,\"multizoneCells\":1,\"obstacles\":0,"
      "\"zoneCellCounts\":{\"a\":3,\"b\":4}}}]}"),
      KeyLux);
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

TArray<FS08BoardFighter> TwoFighters() {
  TArray<FS08BoardFighter> Out;
  for (int32 I = 0; I < 2; ++I) {
    FS08BoardFighter F;
    F.Id = FString::Printf(TEXT("f-%d"), I);
    F.OwnerId = I == 0 ? TEXT("host") : TEXT("guest");
    F.Name = TEXT("Medusa");
    F.Label = F.Name;
    F.bIsHero = true;
    F.Health = F.MaxHealth = 7;
    F.X = I;
    F.Y = 0;
    Out.Add(F);
  }
  return Out;
}

bool LoadShipped(FString& OutProfiles, FS08ArtTunerRegistry& OutRegistry, TArray<FString>& OutErrors) {
  return FFileHelper::LoadFileToString(OutProfiles, *FS08BoardArtData::DefaultPath()) &&
         OutRegistry.LoadFile(S08ArtTunerSpec::DefaultParamsPath(), OutErrors);
}
}  // namespace S08ArtTunerTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtTunerPointerTest, "Unmatched.S08.ArtTuner.Pointer RFC 6901 split / get / set",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtTunerPointerTest::RunTest(const FString&) {
  using namespace S08ArtTunerTest;
  TArray<FString> Seg;
  TestTrue("root", S08JsonPointer::Split(TEXT(""), Seg) && Seg.IsEmpty());
  TestTrue("escapes", S08JsonPointer::Split(TEXT("/a~1b/c~0d/0"), Seg) && Seg.Num() == 3 && Seg[0] == TEXT("a/b") &&
                          Seg[1] == TEXT("c~d") && Seg[2] == TEXT("0"));
  TestFalse("no leading slash", S08JsonPointer::Split(TEXT("a/b"), Seg));
  TestEqual("escape", S08JsonPointer::Escape(TEXT("x/y~z")), FString(TEXT("x~1y~0z")));
  const TSharedPtr<FJsonObject> O = Obj(TEXT("{\"a\":{\"b\":[1,{\"c\":2},[3,4]]},\"s\":\"t\"}"));
  TestEqual("object leaf", S08JsonPointer::Get(O, TEXT("/a/b/1/c"))->AsNumber(), 2.0);
  TestEqual("array in array", S08JsonPointer::Get(O, TEXT("/a/b/2/1"))->AsNumber(), 4.0);
  TestFalse("out of range", S08JsonPointer::Get(O, TEXT("/a/b/9")).IsValid());
  TestFalse("not an index", S08JsonPointer::Get(O, TEXT("/a/b/x")).IsValid());
  TestFalse("negative index", S08JsonPointer::Get(O, TEXT("/a/b/-1")).IsValid());
  TestFalse("missing key", S08JsonPointer::Get(O, TEXT("/a/z")).IsValid());
  FString Error;
  TestTrue("set object leaf", S08JsonPointer::Set(O, TEXT("/a/b/1/c"), Num(5), false, Error));
  TestEqual("set in place", S08JsonPointer::Get(O, TEXT("/a/b/1/c"))->AsNumber(), 5.0);
  TestTrue("set array element", S08JsonPointer::Set(O, TEXT("/a/b/2/0"), Num(30), false, Error));
  TestEqual("array element", S08JsonPointer::Get(O, TEXT("/a/b/2/0"))->AsNumber(), 30.0);
  TestEqual("array sibling kept", S08JsonPointer::Get(O, TEXT("/a/b/2/1"))->AsNumber(), 4.0);
  TestFalse("new key refused", S08JsonPointer::Set(O, TEXT("/a/new"), Num(1), false, Error));
  TestTrue("new key allowed", S08JsonPointer::Set(O, TEXT("/a/new"), Num(1), true, Error));
  TestFalse("new key needs its parent", S08JsonPointer::Set(O, TEXT("/q/new"), Num(1), true, Error));
  TestFalse("below a value", S08JsonPointer::Set(O, TEXT("/s/x"), Num(1), true, Error));
  TestFalse("the root is not a value", S08JsonPointer::Set(O, TEXT(""), Num(1), true, Error));
  TestEqual("text of a NumberString", S08JsonPointer::ToText(NumText(TEXT("7.50"))), FString(TEXT("7.50")));
  TestEqual("text of 0.1+0.2", S08JsonPointer::ToText(Num(0.30000000000000004)), FString(TEXT("0.30000000000000004")));
  TestEqual("text of 7.5", S08JsonPointer::ToText(Num(7.5)), FString(TEXT("7.5")));
  TestEqual("text of a string", S08JsonPointer::ToText(MakeShared<FJsonValueString>(TEXT("a\"b"))), FString(TEXT("\"a\\\"b\"")));
  TestTrue("equal numbers", S08JsonPointer::Equal(Num(7.5), NumText(TEXT("7.50"))));
  TestFalse("number != string", S08JsonPointer::Equal(Num(1), MakeShared<FJsonValueString>(TEXT("1"))));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtTunerValuesTest, "Unmatched.S08.ArtTuner.Values saved text, colours, row writes",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtTunerValuesTest::RunTest(const FString&) {
  using namespace S08ArtTunerTest;
  TestEqual("7.50 -> 7.5", S08ArtTuner::FormatNumber(7.5, 2), FString(TEXT("7.5")));
  TestEqual("3 -> 3", S08ArtTuner::FormatNumber(3.0, 1), FString(TEXT("3")));
  TestEqual("-0", S08ArtTuner::FormatNumber(-0.0001, 2), FString(TEXT("0")));
  TestEqual("4.14106", S08ArtTuner::FormatNumber(FMath::Pow(2.0, 2.05), 5), FString(TEXT("4.14106")));
  FString Hex;
  TestTrue("hex", S08ArtTuner::NormalizeHex(TEXT(" ffe4c4 "), Hex) && Hex == TEXT("#FFE4C4"));
  TestFalse("short hex", S08ArtTuner::NormalizeHex(TEXT("#FFF"), Hex));
  TestFalse("not hex", S08ArtTuner::NormalizeHex(TEXT("#GG0000"), Hex));

  FS08TunerParam P;
  P.Label = TEXT("t");
  P.Pointer = TEXT("/x");
  P.Type = ES08TunerType::Number;
  P.Step = 0.05;
  P.bHasMin = P.bHasMax = P.bMinHard = P.bMaxHard = true;
  P.Min = 0.0;
  P.Max = 1.0;
  TestEqual("decimals 0.05", P.Decimals(), 2);
  TestEqual("snap", P.Snap(0.333), 0.35, 1e-12);
  TArray<TPair<FString, TSharedPtr<FJsonValue>>> W;
  FString Error;
  TestTrue("number", S08ArtTuner::ValueWrites(P, Num(0.333), W, Error) && W.Num() == 1 && W[0].Value->AsString() == TEXT("0.35"));
  TestFalse("above the hard max", S08ArtTuner::ValueWrites(P, Num(1.2), W, Error));
  TestFalse("a string is not a number", S08ArtTuner::ValueWrites(P, MakeShared<FJsonValueString>(TEXT("1")), W, Error));
  P.Type = ES08TunerType::Bool;
  TestTrue("bool", S08ArtTuner::ValueWrites(P, MakeShared<FJsonValueBoolean>(true), W, Error) && W[0].Value->AsBool());
  TestFalse("number is not a bool", S08ArtTuner::ValueWrites(P, Num(1), W, Error));
  P.Type = ES08TunerType::ColorSrgb;
  TestTrue("colour", S08ArtTuner::ValueWrites(P, MakeShared<FJsonValueString>(TEXT("a8c0ff")), W, Error) &&
                         W[0].Value->AsString() == TEXT("#A8C0FF"));
  P.Type = ES08TunerType::ColorLinear;
  P.Step = 0.01;
  TArray<TSharedPtr<FJsonValue>> C = {Num(0.123), Num(0.5), Num(1.0)};
  TestTrue("linear", S08ArtTuner::ValueWrites(P, MakeShared<FJsonValueArray>(C), W, Error) &&
                         S08JsonPointer::ToText(W[0].Value) == TEXT("[0.12, 0.5, 1]"));
  C[2] = Num(1.5);
  TestFalse("linear above the hard max", S08ArtTuner::ValueWrites(P, MakeShared<FJsonValueArray>(C), W, Error));
  C.Pop();
  TestFalse("two channels", S08ArtTuner::ValueWrites(P, MakeShared<FJsonValueArray>(C), W, Error));
  P.Type = ES08TunerType::Ev100;
  P.Pointer = TEXT("/lightProfiles/L/exposure");
  P.bHasMin = P.bHasMax = false;
  TestTrue("ev100", S08ArtTuner::ValueWrites(P, Num(2.05), W, Error) && W.Num() == 3);
  if (W.Num() == 3) {
    TestEqual("ev100 pointer", W[0].Key, FString(TEXT("/lightProfiles/L/exposure/ev100")));
    TestEqual("min == max", W[1].Value->AsString(), W[2].Value->AsString());
    TestEqual("2^2.05", W[1].Value->AsString(), FString(TEXT("4.14106")));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtTunerRegistryTest,
    "Unmatched.S08.ArtTuner.Registry shipped params parse; Sarpedon / Cobble rows expand from the shipped profile",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtTunerRegistryTest::RunTest(const FString&) {
  using namespace S08ArtTunerTest;
  FString Profiles;
  FS08ArtTunerRegistry Registry;
  TArray<FString> Errors;
  if (!TestTrue(FString::Printf(TEXT("shipped files load (%s)"), *FString::Join(Errors, TEXT("; "))),
                LoadShipped(Profiles, Registry, Errors))) {
    return false;
  }
  TestTrue("templates", Registry.NumTemplates() > 40);
  FS08ArtTunerModel Model;
  TestTrue("base", Model.SetBase(Profiles, TEXT("sha"), Errors));
  // board index by id
  auto BoardIndex = [&](const FString& Id) {
    for (int32 I = 0; I < 16; ++I) {
      const TSharedPtr<FJsonValue> V = Model.BaseValue(FString::Printf(TEXT("/boards/%d/id"), I));
      if (V.IsValid() && V->AsString() == Id) return I;
    }
    return int32(INDEX_NONE);
  };
  auto Groups = [&](const FString& BoardId, const FString& Light) { return Registry.Expand(Model.GetBase(), Light, BoardIndex(BoardId)); };
  auto Has = [](const TArray<FS08TunerGroup>& G, const TCHAR* Id) { return G.ContainsByPredicate([&](const FS08TunerGroup& X) { return X.Id == Id; }); };
  const TArray<FS08TunerGroup> Sarpedon = Groups(TEXT("sarpedon-original"), TEXT("sarpedon-night"));
  for (const TCHAR* Id : {TEXT("heroKey"), TEXT("heroRim"), TEXT("heroCommon"), TEXT("scene"), TEXT("points"), TEXT("fog"),
                          TEXT("mapGrade"), TEXT("conceptLights"), TEXT("sceneGeometry")}) {
    TestTrue(FString::Printf(TEXT("sarpedon has %s"), Id), Has(Sarpedon, Id));
  }
  for (const FS08TunerGroup& G : Sarpedon) {
    if (G.Id == TEXT("fog")) TestTrue("fog is inert on Sarpedon (lit3d.hide fog)", G.bInert && !G.Note.IsEmpty());
    if (G.Id == TEXT("conceptLights")) {
      TestEqual("5 lit3d lights x 5 rows", G.Params.Num(), 25);
      TestTrue("label from the id", G.Params[0].Label.StartsWith(TEXT("fire-fort")));
    }
    if (G.Id == TEXT("heroRim")) {
      TestTrue("rim contact shadow is a new optional key",
               G.Params.ContainsByPredicate([](const FS08TunerParam& P) { return P.Id == TEXT("heroRim.rim.contact") && P.bCreate; }));
    }
    for (const FS08TunerParam& P : G.Params) {
      const FString Ptr = P.Type == ES08TunerType::Ev100 ? P.Pointer + TEXT("/ev100") : P.Pointer;
      TestTrue(FString::Printf(TEXT("%s points into the document (%s)"), *P.Id, *Ptr), Model.BaseValue(Ptr).IsValid() || P.bCreate);
      TestFalse(FString::Printf(TEXT("%s: template resolved"), *P.Id), P.Pointer.Contains(TEXT("{")));
    }
  }
  const TArray<FS08TunerGroup> Cobble = Groups(TEXT("cobble-city"), TEXT("cobble-probe"));
  TestTrue("cobble hero key", Has(Cobble, TEXT("heroKey")));
  TestFalse("cobble has no fog", Has(Cobble, TEXT("fog")));
  TestFalse("cobble has no map grade", Has(Cobble, TEXT("mapGrade")));
  TestFalse("cobble has no lit3d lights", Has(Cobble, TEXT("conceptLights")));
  // broken registries
  FS08ArtTunerRegistry Bad;
  Errors.Reset();
  TestFalse("schema", Bad.Parse(TEXT("{\"schema\":\"x\",\"groups\":[]}"), Errors));
  Errors.Reset();
  TestFalse("unknown scope / type", Bad.Parse(TEXT("{\"schema\":\"unmatched.art-tuner-params/1\",\"groups\":[{\"id\":\"g\",\"scope\":\"q\","
                                                   "\"params\":[{\"id\":\"a\",\"pointer\":\"/x\",\"type\":\"z\"}]}]}"),
                                              Errors));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtTunerRangesTest,
    "Unmatched.S08.ArtTuner.Ranges the registry's hard bounds are the profile parser's on every shipped board",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtTunerRangesTest::RunTest(const FString&) {
  using namespace S08ArtTunerTest;
  FString Profiles;
  FS08ArtTunerRegistry Registry;
  TArray<FString> Errors;
  if (!TestTrue("shipped files load", LoadShipped(Profiles, Registry, Errors))) return false;
  FS08ArtTunerModel Base;
  if (!TestTrue("base", Base.SetBase(Profiles, TEXT("sha"), Errors))) return false;
  TSet<FString> Seen;
  int32 Checked = 0;
  for (int32 B = 0; B < 16; ++B) {
    const TSharedPtr<FJsonValue> Light = Base.BaseValue(FString::Printf(TEXT("/boards/%d/light"), B));
    if (!Light.IsValid()) break;
    for (const FS08TunerGroup& G : Registry.Expand(Base.GetBase(), Light->AsString(), B)) {
      for (const FS08TunerParam& P : G.Params) {
        if (P.bCross || Seen.Contains(P.Pointer)) continue;
        if (P.Type != ES08TunerType::Number && P.Type != ES08TunerType::ColorLinear) continue;
        Seen.Add(P.Pointer);
        auto Try = [&](double V) {
          FS08ArtTunerModel M;
          TArray<FString> E;
          M.SetBase(Profiles, TEXT("sha"), E);
          TSharedPtr<FJsonValue> Value = MakeShared<FJsonValueNumberString>(S08ArtTuner::FormatNumber(V, 6));
          if (P.Type == ES08TunerType::ColorLinear) Value = MakeShared<FJsonValueArray>(TArray<TSharedPtr<FJsonValue>>{Value, Value, Value});
          FString SetError;
          if (!M.SetValue(P.Pointer, Value, P.bCreate, SetError)) return false;
          FS08BoardArtData Data;
          return M.Build(Data, E);
        };
        const double Lo = P.bHasMin ? P.Min : P.SliderMin;
        TestTrue(FString::Printf(TEXT("%s accepts its min %g"), *P.Pointer, Lo), Try(Lo));
        if (P.bHasMax) TestTrue(FString::Printf(TEXT("%s accepts its max %g"), *P.Pointer, P.Max), Try(P.Max));
        else TestTrue(FString::Printf(TEXT("%s accepts its slider max %g"), *P.Pointer, P.SliderMax), Try(P.SliderMax));
        if (P.bHasMin && P.bMinHard) {
          TestFalse(FString::Printf(TEXT("%s: the parser refuses min - step (%g)"), *P.Pointer, P.Min - P.Step), Try(P.Min - P.Step));
        }
        if (P.bHasMax && P.bMaxHard) {
          TestFalse(FString::Printf(TEXT("%s: the parser refuses max + step (%g)"), *P.Pointer, P.Max + P.Step), Try(P.Max + P.Step));
        }
        ++Checked;
      }
    }
  }
  TestTrue(FString::Printf(TEXT("rows checked: %d"), Checked), Checked > 40);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtTunerModelTest, "Unmatched.S08.ArtTuner.Model entries, checks, build",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtTunerModelTest::RunTest(const FString&) {
  using namespace S08ArtTunerTest;
  FS08ArtTunerModel M;
  TArray<FString> Errors;
  if (!TestTrue("base", M.SetBase(Doc(), TEXT("abc"), Errors))) return false;
  TestEqual("revision", M.GetBaseRevision(), 7);
  const FString Lux = TEXT("/lightProfiles/L/heroLight/key/lux");
  FString Error;
  TestTrue("set", M.SetValue(Lux, NumText(TEXT("7.5")), false, Error));
  TestTrue("changed", M.IsChanged(Lux) && M.GetEntries().Num() == 1);
  TestEqual("value", M.Value(Lux)->AsNumber(), 7.5);
  TestEqual("base kept", M.BaseValue(Lux)->AsNumber(), 6.0);
  TestTrue("back to the base removes the entry", M.SetValue(Lux, Num(6.0), false, Error) && M.GetEntries().IsEmpty());
  TestFalse("type mismatch", M.SetValue(Lux, MakeShared<FJsonValueString>(TEXT("7")), false, Error));
  TestFalse("unknown pointer", M.SetValue(TEXT("/lightProfiles/L/nope"), Num(1), false, Error));
  TestTrue("new optional key", M.SetValue(TEXT("/lightProfiles/L/heroLight/key/contactShadowLength"), Num(0.1), true, Error));
  TestFalse("an object is not a value", M.SetValue(TEXT("/lightProfiles/L/heroLight/key"), Num(1), false, Error));
  TestTrue("set again", M.SetValue(Lux, NumText(TEXT("9")), false, Error));
  FS08BoardArtData Data;
  TestTrue(FString::Printf(TEXT("build (%s)"), *FString::Join(Errors, TEXT("; "))), M.Build(Data, Errors));
  const FS08LightProfile* L = Data.Lights.Find(TEXT("L"));
  TestTrue("the parser saw the lux", L && FMath::IsNearlyEqual(L->HeroLight.Key.Lux, 9.0f));
  TestTrue("the parser saw the contact shadow", L && FMath::IsNearlyEqual(L->HeroLight.Key.ContactShadowLength, 0.1f));
  TestEqual("sha of the base", Data.SourceSha256, FString(TEXT("abc")));
  // a value the parser refuses (inner cone > outer cone) fails the build
  TestTrue("set inner 40", M.SetValue(TEXT("/lightProfiles/L/heroLight/key/innerConeDeg"), Num(40), false, Error));
  Errors.Reset();
  TestFalse("inner > outer refused by the parser", M.Build(Data, Errors));
  M.Reset(TEXT("/lightProfiles/L/heroLight/key/innerConeDeg"));
  Errors.Reset();
  TestTrue("valid again", M.Build(Data, Errors));
  M.ResetAll();
  TestTrue("reset all", M.GetEntries().IsEmpty());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtTunerOverridesTest, "Unmatched.S08.ArtTuner.Overrides file round trip",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtTunerOverridesTest::RunTest(const FString&) {
  using namespace S08ArtTunerTest;
  FS08TunerOverridesFile F;
  F.SavedAt = TEXT("2026-10-03T12:00:00Z");
  F.BaseSha256 = TEXT("abc");
  F.BaseRevision = 20;
  FS08TunerOverridesFile::FBoard A;
  A.Board = TEXT("sarpedon-original");
  A.Profile = TEXT("sarpedon-night");
  A.Anchors.Add({TEXT("/boards/4/id"), TEXT("sarpedon-original")});
  A.Entries.Add({TEXT("/lightProfiles/sarpedon-night/heroLight/key/lux"), NumText(TEXT("7.5")), NumText(TEXT("7.0"))});
  A.Entries.Add({TEXT("/lightProfiles/sarpedon-night/heroLight/key/colorSrgb"), MakeShared<FJsonValueString>(TEXT("#FFE0C0")),
                 MakeShared<FJsonValueString>(TEXT("#FFF0E0"))});
  A.Entries.Add({TEXT("/lightProfiles/sarpedon-night/heroLight/rim/contactShadowLength"), NumText(TEXT("0.1")), nullptr});
  F.PutBoard(A);
  FS08TunerOverridesFile::FBoard Bo;
  Bo.Board = TEXT("cobble-city");
  Bo.Entries.Add({TEXT("/lightProfiles/cobble-probe/sky/intensity"), NumText(TEXT("12")), NumText(TEXT("11.2"))});
  F.PutBoard(Bo);
  const FString Text = F.ToJson();
  TestTrue("value text kept", Text.Contains(TEXT("\"value\": 7.5, \"was\": 7.0")));
  TestTrue("new key -> was null", Text.Contains(TEXT("\"was\": null")));
  FS08TunerOverridesFile G;
  TArray<FString> Errors;
  if (!TestTrue(FString::Printf(TEXT("parse (%s)"), *FString::Join(Errors, TEXT("; "))), G.Parse(Text, Errors))) return false;
  TestEqual("boards", G.Boards.Num(), 2);
  const FS08TunerOverridesFile::FBoard* S = G.FindBoard(TEXT("sarpedon-original"));
  if (TestNotNull("sarpedon block", S)) {
    TestEqual("entries", S->Entries.Num(), 3);
    TestEqual("anchor", S->Anchors.Num(), 1);
    TestEqual("number text", S08JsonPointer::ToText(S->Entries[0].Value), FString(TEXT("7.5")));
    TestFalse("was null -> unset", S->Entries[2].Was.IsValid());
  }
  // saving one board replaces only its block
  FS08TunerOverridesFile::FBoard A2 = A;
  A2.Entries.SetNum(1);
  G.PutBoard(A2);
  TestEqual("still two boards", G.Boards.Num(), 2);
  TestEqual("replaced", G.FindBoard(TEXT("sarpedon-original"))->Entries.Num(), 1);
  TestEqual("the other kept", G.FindBoard(TEXT("cobble-city"))->Entries.Num(), 1);
  // broken files / entries
  Errors.Reset();
  TestFalse("wrong schema", G.Parse(TEXT("{\"schema\":\"x\",\"boards\":[]}"), Errors));
  Errors.Reset();
  TestTrue("a broken entry is skipped, the file still loads",
           G.Parse(TEXT("{\"schema\":\"unmatched.art-tuner-overrides/1\",\"boards\":[{\"board\":\"b\",\"entries\":[{\"value\":1},"
                        "{\"pointer\":\"/x\",\"value\":2}]}]}"),
                   Errors) &&
               Errors.Num() == 1 && G.Boards.Num() == 1 && G.Boards[0].Entries.Num() == 1);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtTunerApplyTest,
    "Unmatched.S08.ArtTuner.Apply tuned values reach the spawned components without a rebuild; a rebuild agrees",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtTunerApplyTest::RunTest(const FString&) {
  using namespace S08ArtTunerTest;
  FS08BoardArtData Start;
  TArray<FString> Errors;
  if (!TestTrue(FString::Printf(TEXT("start document (%s)"), *FString::Join(Errors, TEXT("; "))), Start.ParseJson(Doc(), Errors))) {
    return false;
  }
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, FName(TEXT("S08ArtTunerApply")));
  if (!TestNotNull("test world", World)) return false;
  FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
  Context.SetCurrentWorld(World);
  AS08BoardActor* Board = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator);
  if (TestNotNull("board actor", Board)) {
    const FS08BoardModel Model = Grid(3, 2);
    Board->SetArtDataForTest(Start);
    Board->SetTileArtReadyForTest();
    Board->SetRoomBoardId(TEXT("cid1"));
    Board->SetHeroLightOptOutForTest(TOptional<bool>(false));
    TestTrue("art active", (Board->Rebuild(Grid(3, 2)), Board->IsArtActive()));
    TestTrue("first build", Board->Rebuild(Model));
    Board->SyncFighters(Model, TwoFighters(), TEXT("host"));
    const int32 Builds = Board->GetBuildCount();
    auto Components = [&](float& OutKey, float& OutPoint, float& OutFogDensity, float& OutHeroCd) {
      OutKey = OutPoint = OutFogDensity = OutHeroCd = -1.0f;
      for (TActorIterator<ADirectionalLight> It(World); It; ++It) OutKey = It->GetLightComponent()->Intensity;
      for (TActorIterator<APointLight> It(World); It; ++It) OutPoint = It->GetLightComponent()->Intensity;
      for (TActorIterator<AExponentialHeightFog> It(World); It; ++It) OutFogDensity = It->GetComponent()->FogDensity;
      const AS08FighterActor* F = Board->FindFighterActor(TEXT("f-0"));
      const USpotLightComponent* Spot = F ? F->GetHeroLight(0) : nullptr;
      if (Spot) OutHeroCd = Spot->Intensity;
    };
    float Key0, Point0, Fog0, Hero0;
    Components(Key0, Point0, Fog0, Hero0);
    TestEqual("key at start", Key0, 3.0f, 1e-4f);
    TestEqual("fog at start", Fog0, 0.3f, 1e-4f);
    TestTrue("a hero rig", Hero0 > 0.0f);
    const AS08FighterActor* FighterBefore = Board->FindFighterActor(TEXT("f-0"));

    FS08ArtTunerModel M;
    TestTrue("model", M.SetBase(Doc(), TEXT("sha"), Errors));
    FString Error;
    TestTrue("key", M.SetValue(TEXT("/lightProfiles/L/directional/intensity"), NumText(TEXT("4.5")), false, Error));
    TestTrue("point", M.SetValue(TEXT("/lightProfiles/L/points/0/intensity"), NumText(TEXT("80")), false, Error));
    TestTrue("fog", M.SetValue(TEXT("/lightProfiles/L/fog/density"), NumText(TEXT("0.5")), false, Error));
    TestTrue("hero lux x2", M.SetValue(TEXT("/lightProfiles/L/heroLight/key/lux"), NumText(TEXT("12")), false, Error));
    FS08BoardArtData Tuned;
    if (TestTrue("tuned build", M.Build(Tuned, Errors))) {
      FString Note;
      const uint8 Scopes = static_cast<uint8>(ES08TunerScope::ProfileLights | ES08TunerScope::HeroLight);
      TestFalse("no rebuild needed", Board->ApplyTunedArtData(Tuned, Scopes, TEXT("tuner"), Note));
      TestEqual("no build", Board->GetBuildCount(), Builds);
      TestTrue("the same fighter actor (no respawn)", Board->FindFighterActor(TEXT("f-0")) == FighterBefore);
      float Key1, Point1, Fog1, Hero1;
      Components(Key1, Point1, Fog1, Hero1);
      TestEqual("key on the component", Key1, 4.5f, 1e-4f);
      TestEqual("point on the component", Point1, 80.0f, 1e-4f);
      TestEqual("fog on the component", Fog1, 0.5f, 1e-4f);
      TestEqual("hero candelas x2", Hero1, 2.0f * Hero0, 0.01f * Hero0);
      TestEqual("fingerprint source", Board->GetAppliedRender().ProfilesSource, FString(TEXT("tuner")));
      // a full rebuild of the same document (the reference path) puts the same values on the new components
      Board->RequestFullRebuild();
      TestTrue("rebuild", Board->Rebuild(Model));
      Board->SyncFighters(Model, TwoFighters(), TEXT("host"));
      float Key2, Point2, Fog2, Hero2;
      Components(Key2, Point2, Fog2, Hero2);
      TestEqual("rebuild: key", Key2, Key1, 1e-4f);
      TestEqual("rebuild: point", Point2, Point1, 1e-4f);
      TestEqual("rebuild: fog", Fog2, Fog1, 1e-4f);
      TestEqual("rebuild: hero", Hero2, Hero1, 0.001f * Hero1);
      // the rebuild scope asks the caller for the normal build
      TestTrue("rebuild scope", Board->ApplyTunedArtData(Tuned, static_cast<uint8>(ES08TunerScope::Rebuild), TEXT("tuner"), Note));
    }
  }
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtTunerOffByDefaultTest, "Unmatched.S08.ArtTuner.OffByDefault no -ArtTuner in this process",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtTunerOffByDefaultTest::RunTest(const FString&) {
  TestFalse("no -ArtTuner", S08ArtTunerSpec::Enabled());
  TestTrue("no -ArtTunerFile", S08ArtTunerSpec::FileFromCommandLine().IsEmpty());
  TestTrue("explicit flag", S08ArtTunerSpec::Enabled(TEXT("-ArtView=sarpedon -ArtTuner")));
  TestEqual("file", S08ArtTunerSpec::FileFromCommandLine(TEXT("-ArtTunerFile=\"C:/a b/x.json\"")), FString(TEXT("C:/a b/x.json")));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS

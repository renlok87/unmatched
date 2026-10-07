// VS-5 EN-06 automation: the animation channels of the concept paste (S08ConceptPasteAnim.h).
//   Unmatched.S08.ConceptPaste.Anim  the lantern flicker in sync with the linked point light (FlickerScale, same T), the
//   own pair of an unlinked slot, frozen values in -Bench / -EnvFxFreeze / reduced motion (AnimTime 0, flicker 1, wind 0,
//   the mist kept still), the freeze reason (s08.ReducedMotion), no mask / no anim material -> UseAnim 0, the trace line,
//   the shipped Marmoreal block once it carries "anim" and - when imported - MI_ConceptPaste_Anim's static switch.
//   UnrealEditor-Cmd.exe Unmatched.uproject -ExecCmds="Automation RunTests Unmatched.S08.ConceptPaste.Anim; Quit"
//     -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08BoardArt.h"
#include "S08ConceptPaste.h"
#include "S08ConceptPasteAnim.h"
#include "S08Contracts.h"
#include "S08EnvLayout.h"
#include "S08IconMotion.h"
#include "Dom/JsonObject.h"
#include "HAL/IConsoleManager.h"
#include "Materials/MaterialInstance.h"
#include "Materials/MaterialInterface.h"
#include "Misc/AutomationTest.h"
#include "Misc/PackageName.h"

namespace S08ConceptPasteAnimTest {
const TCHAR* const Block = TEXT(
    "{\"default\":\"off\",\"sheetMesh\":\"/Game/EnvMaps/X/SM_S\",\"plateB\":\"/Game/EnvMaps/X/T_B\","
    "\"hide\":[\"layoutLights\"],"
    "\"lights\":[{\"id\":\"lantern-nw\",\"loc\":[-400,-500,100],\"colorSrgb\":\"#FF9A45\",\"intensityCd\":80,\"radius\":480,"
    "\"flicker\":{\"amp\":0.08,\"hz\":4.0}},{\"id\":\"portal-glow\",\"loc\":[0,-600,60],\"colorSrgb\":\"#FFB066\","
    "\"intensityCd\":65,\"radius\":380}],"
    "\"anim\":{\"mask\":\"/Game/EnvMaps/NoSuchAnim/T_NoSuchAnim_ConceptAnim\","
    "\"lanterns\":[{\"id\":\"lantern-nw\",\"c0Px\":[486.6,105.2],\"radiusPx\":262,\"light\":\"lantern-nw\"},"
    "{\"id\":\"sconce-door-w\",\"c0Px\":[904.9,31.4],\"radiusPx\":70,\"flicker\":{\"amp\":0.06,\"hz\":6.0}}],"
    "\"wind\":{\"ampPx\":1.2,\"hz\":0.25,\"gustHz\":0.6,\"gustAmp\":0.35,\"wavePx\":400},"
    "\"mist\":{\"opacity\":0.18,\"panPxPerS\":[6,0],\"noisePx\":220,\"colorSrgb\":\"#0F1523\"}}}");

bool Parse(const TCHAR* Text, FS08ConceptPasteSpec& Out, TArray<FString>& Errors) {
  TSharedPtr<FJsonObject> Obj;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(Text, Obj, Problem) || !Obj.IsValid()) {
    Errors.Add(Problem);
    return false;
  }
  return S08ConceptPaste::ParseJson(TEXT("animtest"), Obj, Out, Errors);
}

/** s08.ReducedMotion for the scope (restored after). */
struct FReducedScope {
  IConsoleVariable* Var = nullptr;
  int32 Before = 0;
  explicit FReducedScope(int32 Value) {
    Var = IConsoleManager::Get().FindConsoleVariable(TEXT("s08.ReducedMotion"));
    if (Var) {
      Before = Var->GetInt();
      Var->Set(Value, ECVF_SetByCode);
    }
  }
  ~FReducedScope() {
    if (Var) Var->Set(Before, ECVF_SetByCode);
  }
};
}  // namespace S08ConceptPasteAnimTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ConceptPasteAnimTest,
    "Unmatched.S08.ConceptPaste.Anim lantern flicker synced with its light, frozen in -Bench and reduced motion, no mask -> UseAnim 0",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ConceptPasteAnimTest::RunTest(const FString&) {
  using namespace S08ConceptPasteAnimTest;
  FS08ConceptPasteSpec Spec;
  TArray<FString> Errors;
  if (!TestTrue(TEXT("block with anim parses: ") + FString::Join(Errors, TEXT(" | ")), Parse(Block, Spec, Errors))) return false;
  const FS08ConceptPasteAnimSpec& A = Spec.Anim;
  if (!TestTrue("anim set, 2 slots", A.bSet && A.Lanterns.Num() == 2)) return false;
  TestEqual("one synced slot", S08ConceptPasteAnim::SyncedCount(A, Spec.Lights), 1);
  TestTrue("slot 0 linked to lantern-nw", S08ConceptPasteAnim::LinkedLight(A.Lanterns[0], Spec.Lights) == &Spec.Lights[0]);
  TestNull("slot 1 own pair", S08ConceptPasteAnim::LinkedLight(A.Lanterns[1], Spec.Lights));

  // sync: the same function and the same T as the point light (one value per frame for the paint and the light)
  bool bSynced = true, bMoves = false, bOwn = true;
  float Lo = 2.0f, Hi = 0.0f;
  for (const double T : {0.0, 0.13, 0.5, 1.7, 2.25, 5.25, 61.0, 3600.4}) {
    const float Light = S08ConceptPaste::FlickerScale(Spec.Lights[0], T);
    const FS08ConceptAnimParams P = S08ConceptPasteAnim::Params(A, Spec.Lights, false, T);
    bSynced &= P.LanternFlicker[0] == Light && S08ConceptPasteAnim::LanternFlicker(A.Lanterns[0], Spec.Lights, T) == Light;
    bMoves |= !FMath::IsNearlyEqual(P.LanternFlicker[0], 1.0f, 1e-4f);
    FS08ConceptLight Own;
    Own.Id = TEXT("sconce-door-w");
    Own.FlickerAmp = 0.06f;
    Own.FlickerHz = 6.0f;
    bOwn &= P.LanternFlicker[1] == S08ConceptPaste::FlickerScale(Own, T);
    Lo = FMath::Min(Lo, P.LanternFlicker[0]);
    Hi = FMath::Max(Hi, P.LanternFlicker[0]);
    TestTrue(FString::Printf(TEXT("T %.2f: AnimTime = T, unused slots steady"), T),
             FMath::IsNearlyEqual(P.AnimTime, static_cast<float>(T), 1e-3f) && P.LanternFlicker[2] == 1.0f &&
                 P.LanternC0[2].B == 0.0f);
  }
  TestTrue("slot 0 = FlickerScale(lantern-nw, T) at every T", bSynced);
  TestTrue("slot 0 flickers", bMoves);
  TestTrue(FString::Printf(TEXT("slot 0 within 1 +- amp 0.08 (%.3f..%.3f)"), Lo, Hi), Lo >= 0.92f - 1e-4f && Hi <= 1.08f + 1e-4f);
  TestTrue("slot 1 = FlickerScale of its own pair (phases from the slot id)", bOwn);

  // the static values: circles, wind, mist (linear colour)
  const FS08ConceptAnimParams Live = S08ConceptPasteAnim::Params(A, Spec.Lights, false, 2.0);
  TestTrue("circle 0 (x, y, radius)", Live.LanternC0[0].Equals(FLinearColor(486.6f, 105.2f, 262.0f, 0.0f), 1e-3f));
  TestTrue("wind live (amp, hz, gustHz, gustAmp) + wave", Live.Wind.Equals(FLinearColor(1.2f, 0.25f, 0.6f, 0.35f), 1e-5f) &&
                                                              Live.WindWavePx == 400.0f);
  const FLinearColor MistLinear = FLinearColor::FromSRGBColor(FColor(0x0F, 0x15, 0x23));
  TestTrue("mist colour linear + (opacity, pan, noisePx)", Live.MistColor.Equals(FLinearColor(MistLinear.R, MistLinear.G, MistLinear.B, 0.0f), 1e-6f) &&
                                                             Live.MistParams.Equals(FLinearColor(0.18f, 6.0f, 0.0f, 220.0f), 1e-5f));
  // frozen (-Bench / -EnvFxFreeze / reduced motion): AnimTime 0, flicker 1, wind 0, the mist kept (still at t 0)
  const FS08ConceptAnimParams Frozen = S08ConceptPasteAnim::Params(A, Spec.Lights, true, 5.25);
  TestTrue("frozen: AnimTime 0, every flicker 1", Frozen.AnimTime == 0.0f && Frozen.LanternFlicker[0] == 1.0f && Frozen.LanternFlicker[1] == 1.0f);
  TestTrue("frozen: wind amplitude 0 (no UV offset), the wave kept", Frozen.Wind.R == 0.0f && Frozen.Wind.G == 0.25f);
  TestTrue("frozen: the mist stays (still)", Frozen.MistParams.Equals(Live.MistParams) && Frozen.MistColor.Equals(Live.MistColor));
  TestTrue("frozen twice = the same values (reproducible -Bench)",
           S08ConceptPasteAnim::Params(A, Spec.Lights, true, 99.0).LanternFlicker[0] == Frozen.LanternFlicker[0] &&
               S08ConceptPasteAnim::Params(A, Spec.Lights, true, 99.0).AnimTime == 0.0f);

  // the freeze reason
  {
    FS08EnvFxOptions O;
    TestEqual("live run", S08ConceptPasteAnim::FreezeReason(O), FString(TEXT("live")));
    O.bBench = O.bFreeze = true;
    TestEqual("-Bench", S08ConceptPasteAnim::FreezeReason(O), FString(TEXT("bench")));
    O.bBench = false;
    O.bFreezeFlag = true;
    TestEqual("-EnvFxFreeze", S08ConceptPasteAnim::FreezeReason(O), FString(TEXT("flag")));
    O.bReduced = true;
    TestEqual("reduced motion", S08ConceptPasteAnim::FreezeReason(O), FString(TEXT("reduced")));
    O.bSpawn = false;  // -ArtPreviewNoFx: the paste animation still follows the freeze
    TestEqual("reduced motion with -ArtPreviewNoFx", S08ConceptPasteAnim::FreezeReason(O), FString(TEXT("reduced")));
  }
  {
    const FReducedScope Reduced(1);
    if (Reduced.Var) {
      TestTrue("s08.ReducedMotion 1 -> reduced", S08IconMotion::IsReducedMotion());
      const FS08EnvFxOptions O = FS08EnvFxOptions::FromCommandLine();
      TestTrue("FromCommandLine under reduced motion: frozen, reason reduced",
               O.bReduced && O.bFreeze && O.Reason() == TEXT("reduced") && S08ConceptPasteAnim::FreezeReason(O) == TEXT("reduced"));
    } else {
      AddWarning(TEXT("s08.ReducedMotion not registered: the CVar path was not checked"));
    }
  }

  // no mask / no anim material -> UseAnim 0
  TestEqual("status ok", S08ConceptPasteAnim::Status(A, true, true), FString(TEXT("ok")));
  TestEqual("no mask", S08ConceptPasteAnim::Status(A, false, true), FString(TEXT("mask-missing")));
  TestEqual("no anim material", S08ConceptPasteAnim::Status(A, true, false), FString(TEXT("material-missing")));
  TestEqual("no block", S08ConceptPasteAnim::Status(FS08ConceptPasteAnimSpec(), true, true), FString(TEXT("no-block")));
  {
    const FS08ConceptPasteAssets Assets = S08ConceptPaste::LoadAssets(Spec);
    TestNull("a mask that is not imported does not load", Assets.AnimMask);
    TestTrue("it is listed as missing (traced, not fatal)", Assets.Missing.Contains(A.MaskPath));
    TestFalse("the static paste then: UseAnim 0", S08ConceptPasteAnim::Status(A, Assets.AnimMask != nullptr,
                                                                             Assets.AnimMaterial != nullptr) == TEXT("ok"));
  }
  // the trace line (the EN-06 acceptance reads it)
  TestEqual("trace line", S08ConceptPasteAnim::TraceLine(TEXT("marmoreal-original"), A, Spec.Lights, TEXT("T_X_ConceptAnim"), true,
                                                         TEXT("ok"), true, TEXT("reduced")),
            FString(TEXT("ARTPREVIEW concept-paste anim profile=marmoreal-original mask=T_X_ConceptAnim lanterns=2 synced=1 wind=1.20@0.25 mist=0.18 frozen=1 reason=reduced use=1 status=ok")));
  TestEqual("parameter names", S08ConceptPasteAnim::LanternC0Name(7).ToString() + TEXT(" ") +
                                   S08ConceptPasteAnim::LanternFlickerName(0).ToString(),
            FString(TEXT("LanternC0_7 LanternFlicker_0")));

  // the shipped Marmoreal block (VS-5 E1: EN-06 + EN-07 set it up; EN-08 / EN-10 / EN-12 tune it)
  {
    FS08BoardArtData Data;
    TArray<FString> E;
    if (TestTrue(TEXT("shipped profiles parse: ") + FString::Join(E, TEXT(" | ")), Data.LoadFile(FS08BoardArtData::DefaultPath(), E))) {
      const FS08BoardArtProfile* M = Data.Boards.FindByPredicate([](const FS08BoardArtProfile& B) { return B.Id == TEXT("marmoreal-original"); });
      const FS08BoardArtProfile* S = Data.Boards.FindByPredicate([](const FS08BoardArtProfile& B) { return B.Id == TEXT("sarpedon-original"); });
      if (TestNotNull("marmoreal-original", M) && TestNotNull("sarpedon-original", S)) {
        const FS08ConceptPasteAnimSpec& MA = M->ConceptPaste.Anim;
        TestTrue("marmoreal: anim block with T_Marmoreal_ConceptAnim", MA.bSet && MA.MaskPath == TEXT("/Game/EnvMaps/Marmoreal/ConceptPaste/T_Marmoreal_ConceptAnim"));
        TestEqual("marmoreal: 6 slots (4 lanterns + 2 sconces)", MA.Lanterns.Num(), 6);
        TestEqual("marmoreal: synced=4 (the lanterns follow their point lights)", S08ConceptPasteAnim::SyncedCount(MA, M->ConceptPaste.Lights), 4);
        TestTrue("marmoreal: wind and mist", MA.Wind.bSet && MA.Mist.bSet);
        TestFalse("sarpedon: no paste animation (lit3d unchanged)", S->ConceptPaste.Anim.bSet);
      }
    }
  }
#if WITH_EDITOR
  // MI_ConceptPaste_Anim (ue_concept_material.py) once imported: the static switch on, the anim parameters there
  if (FPackageName::DoesPackageExist(S08ConceptPasteSpec::AnimMaterialPath)) {
    UMaterialInterface* Mi = LoadObject<UMaterialInterface>(nullptr, S08ConceptPasteSpec::AnimMaterialPath);
    if (TestNotNull("MI_ConceptPaste_Anim loads", Mi)) {
      bool bOn = false;
      FGuid Guid;
      TestTrue("static switch UseAnim found and on",
               Mi->GetStaticSwitchParameterValue(FHashedMaterialParameterInfo(S08ConceptPasteSpec::UseAnimSwitchName), bOn, Guid) && bOn);
      float V = -1.0f;
      TestTrue("AnimTime default 0", Mi->GetScalarParameterValue(FHashedMaterialParameterInfo(S08ConceptPasteSpec::ParamAnimTime), V) && V == 0.0f);
      TestTrue("LanternFlicker_7 default 1", Mi->GetScalarParameterValue(FHashedMaterialParameterInfo(S08ConceptPasteAnim::LanternFlickerName(7)), V) && V == 1.0f);
    }
    UMaterialInterface* Base = LoadObject<UMaterialInterface>(nullptr, S08ConceptPasteSpec::DefaultMaterialPath);
    bool bOn = true;
    FGuid Guid;
    TestTrue("M_ConceptPaste: UseAnim off by default (Sarpedon's sky unchanged)",
             Base && Base->GetStaticSwitchParameterValue(FHashedMaterialParameterInfo(S08ConceptPasteSpec::UseAnimSwitchName), bOn, Guid) && !bOn);
  } else {
    AddWarning(TEXT("MI_ConceptPaste_Anim not imported (tools/art/concept_paste/ue_concept_material.py): the material side was not checked"));
  }
#endif
  return true;
}

#endif  // WITH_AUTOMATION_TESTS

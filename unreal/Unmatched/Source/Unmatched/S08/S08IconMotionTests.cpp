// HUD icon motion v3 automation tests (docs/unreal/contracts/hud/ICON-MOTION-PLAN.md, phase C):
//   Load    - Config/S08IconMotion.json parses: 23 v3 icons + 5 DE-012 records (4 accepted 2026-10-05, the team ring
//             a candidate) + 13 accepted VR44 records (VS-2 A2, IC-38...IC-56), appear/leave each, the fallen heart on
//             its own blackened layer, the conflict badge on the order badge's body and team layers, revision = the
//             golden file's;
//   Golden  - FS08IconAnimator replays every icon's demo script (normal and reduced) and matches the Python
//             reference poses docs/unreal/contracts/hud/icon-motion-golden.json (8 props + pivot, 1e-3);
//   Reduced - s08.ReducedMotion drives S08IconMotion::IsReducedMotion;
//   Textures- every layer and variant texture of the contract exists at its `ue_sizes` (18/24/32/36/48/64; the L6
//             badges also 16/21) with the exact size (2:1 plates by canvas) and no mips;
//   Widget  - US08AnimatedIconWidget builds one image per layer and applies the evaluator's pose;
//   Semantics - events over the base (review 2026-10-03): leave after hold fades, tap after hover returns to it,
//             a future appear is invisible, equal start time -> the later command wins;
//   CombatView - the combat token view: show = appear + pulse, hide = leave, then hidden.
//   DefaultToken - RD-1: the animated v3 token is the default, -S08IconLegacy is the rollback.
//   TurnPortrait - DE-023 + run I (AB-5..AB-8 accepted 2026-10-05): the persistent HUD portrait in the default look -
//             the warm ring (flash 1000 ms -> rim 0.35, at rest, leave), the heart damage with its glow halo, the DE
//             tracker (a spent slot filled with its action type, unfill on cancel, reset in one frame), the fallen
//             heart's cross stamped in at the heart mark;
//   TurnHudRollbacks - run I: each rollback flag restores its old part (-S08TurnRingLegacy no ring, -S08HeartGlowLegacy
//             no halo, -S08TrackerLegacy the v3 slots spend / gain, -S08CrossLegacy no fallen glyph), the ring choice
//             of -S08TurnRingIcon, the trace fields (HUD-TURN config, ARTLOOK hud=...).
//   GalleryIds - VS-2 IC-70: the -S08IconGallery grid = contract order, its rows fit the 1080 su canvas, and its
//             `ICONGALLERY ids` list names every id of accepted_vr44, accepted_de012 and candidates.
// Headless:
//   UnrealEditor-Cmd.exe Unmatched.uproject -ExecCmds="Automation RunTests Unmatched.S08.IconMotion; Quit"
//     -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08AnimatedIconWidget.h"
#include "S08ArtHudViews.h"
#include "S08IconMotion.h"
#include "S08TurnPortraitWidget.h"
#include "Components/TextBlock.h"
#include "Blueprint/UserWidget.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace {
FString S08GoldenPath() {
  return FPaths::ConvertRelativePathToFull(FPaths::Combine(
      FPaths::ProjectDir(), TEXT("../../docs/unreal/contracts/hud/icon-motion-golden.json")));
}

struct FS08IconTestWorld {
  UWorld* World = nullptr;
  explicit FS08IconTestWorld(const TCHAR* Name) {
    World = UWorld::CreateWorld(EWorldType::Game, false, FName(Name));
    if (World) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
  }
  ~FS08IconTestWorld() {
    if (!World) return;
    GEngine->DestroyWorldContext(World);
    World->DestroyWorld(false);
  }
};

TArray<FString> S08LayerTextureNames(const FS08IconMotionDef& Def) {
  TArray<FString> Out;
  for (const FS08IconLayer& L : Def.Layers) {
    if (L.Src.EndsWith(TEXT("#"))) {
      for (int32 F = 0; F < L.Frames; ++F) Out.Add(FString::Printf(TEXT("%s#%d"), *L.Src, F));
    } else {
      Out.Add(L.Src);
    }
  }
  return Out;
}
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08IconMotionLoadTest, "Unmatched.S08.IconMotion.Load",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS08IconMotionLoadTest::RunTest(const FString& Parameters) {
  FS08IconMotionLibrary Lib;
  FString Err;
  if (!TestTrue(TEXT("contract loads: ") + Err, Lib.LoadFile(FS08IconMotionLibrary::DefaultPath(), &Err))) return false;
  // 23 accepted v3 icons + 5 DE-012 records: the warm turn ring, the fallen heart, the X stamp and the DE tracker slot
  // accepted by the user on 2026-10-05 (contract `accepted_de012`, Codex forms), the team-tint ring still a candidate
  // (gallery only; contract `candidates`).
  // VS-2 A2 (2026-10-06): 13 VR44 records accepted by delegation (contract `accepted_vr44`, IC-38...IC-56; the cursors
  // IC-58...IC-61 are not in the motion contract - HB-12 imports them).
  // VS-2 A3: 4 more VR44 records with the Codex IC-36 forms (IC-46 end turn, IC-48 card drop, IC-52 slot discard ribbon,
  // IC-55 log glyph).
  // VS-4 V3: 8 zone icons (IC-62...IC-69, Codex IC-37 forms): body / disc / glyph, the disc tint "zone", the glyph "ink".
  // VS-6 F2: + state-heal (IC-49, the «+» of a heal under reduced motion; appear / leave opacity 100 ms).
  TestEqual(TEXT("54 icons in order"), Lib.Order.Num(), 54);
  TestEqual(TEXT("54 icon definitions"), Lib.Icons.Num(), 54);
  for (const TCHAR* Zone : {TEXT("zone-gray"), TEXT("zone-green"), TEXT("zone-blue"), TEXT("zone-violet"), TEXT("zone-purple"),
                            TEXT("zone-red"), TEXT("zone-brown"), TEXT("zone-yellow")}) {
    const FS08IconMotionDef* Z = Lib.Find(FName(Zone));
    if (!TestNotNull(FString::Printf(TEXT("%s defined"), Zone), Z)) continue;
    TestEqual(FString::Printf(TEXT("%s: 3 layers"), Zone), Z->Layers.Num(), 3);
    if (Z->Layers.Num() == 3) {
      TestTrue(FString::Printf(TEXT("%s: shared plate and disc, own glyph, tints zone / ink"), Zone),
               Z->Layers[0].Src == TEXT("zone-gray_body") && Z->Layers[1].Src == TEXT("zone-gray_disc") &&
                   Z->Layers[1].TintKey == FName(TEXT("zone")) && Z->Layers[2].TintKey == FName(TEXT("ink")) &&
                   Z->Layers[2].Src == FString(Zone) + TEXT("_glyph"));
    }
  }
  for (const TCHAR* Vr44 : {TEXT("badge-order"), TEXT("badge-refuse"), TEXT("badge-conflict"), TEXT("badge-ally"),
                            TEXT("badge-attack-from"), TEXT("team-chip-p1"), TEXT("team-chip-p2"), TEXT("state-warning"),
                            TEXT("marker-slot-scheme"), TEXT("marker-slot-boost"), TEXT("ui-menu"), TEXT("ui-close"),
                            TEXT("ui-step"), TEXT("action-end-turn"), TEXT("card-drop"), TEXT("marker-slot-discard"),
                            TEXT("ui-log")}) {
    TestNotNull(*FString::Printf(TEXT("VR44 %s defined"), Vr44), Lib.Find(Vr44));
  }
  if (const FS08IconMotionDef* EndTurn = Lib.Find(TEXT("action-end-turn"))) {
    // IC-46: the action disc events without spend / restore (a turn has no "pass" action, SD-44).
    TestNotNull(TEXT("end turn select"), EndTurn->FindAnim(TEXT("select")));
    TestNull(TEXT("end turn has no spend"), EndTurn->FindAnim(TEXT("spend")));
    TestEqual(TEXT("end turn layers"), EndTurn->Layers.Num(), 2);
  }
  if (const FS08IconMotionDef* Conflict = Lib.Find(TEXT("badge-conflict"))) {
    // ВР-IC05: the conflict badge shares the order badge's body and team block; only the "!" is its own layer.
    TestEqual(TEXT("conflict layers"), Conflict->Layers.Num(), 3);
    if (Conflict->Layers.Num() == 3) {
      TestEqual(TEXT("conflict body src"), Conflict->Layers[0].Src, FString(TEXT("badge-order_body")));
      TestTrue(TEXT("conflict team tinted"), Conflict->Layers[1].bTintTeam);
      TestEqual(TEXT("conflict glyph src"), Conflict->Layers[2].Src, FString(TEXT("badge-conflict_glyph")));
    }
  }
  if (const FS08IconMotionDef* From = Lib.Find(TEXT("badge-attack-from"))) {
    TestEqual(TEXT("attack-from is a 2:1 plate"), From->CanvasU.X, 64.0);
  }
  TestNotNull(TEXT("variant badge-order-p2 resolves"), Lib.Find(TEXT("badge-order-p2")));
  for (const TCHAR* De012 : {TEXT("marker-turn-ring"), TEXT("marker-turn-ring-team"), TEXT("resource-hp-fallen"),
                             TEXT("marker-x-stamp"), TEXT("marker-action-slot-de")}) {
    TestNotNull(*FString::Printf(TEXT("DE-012 %s defined"), De012), Lib.Find(De012));
  }
  if (const FS08IconMotionDef* Fallen = Lib.Find(TEXT("resource-hp-fallen"))) {
    // Codex form: a blackened heart under the small X, not the empty-heart texture.
    TestEqual(TEXT("fallen heart layers"), Fallen->Layers.Num(), 2);
    if (Fallen->Layers.Num() == 2) {
      TestEqual(TEXT("fallen heart layer src"), Fallen->Layers[0].Src, FString(TEXT("resource-hp-fallen_heart")));
      TestEqual(TEXT("fallen cross layer src"), Fallen->Layers[1].Src, FString(TEXT("resource-hp-fallen_cross")));
    }
  }
  for (const FName Id : Lib.Order) {
    const FS08IconMotionDef* Def = Lib.Find(Id);
    if (!TestNotNull(*FString::Printf(TEXT("%s defined"), *Id.ToString()), Def)) continue;
    TestNotNull(*FString::Printf(TEXT("%s appear"), *Id.ToString()), Def->FindAnim(TEXT("appear")));
    TestNotNull(*FString::Printf(TEXT("%s leave"), *Id.ToString()), Def->FindAnim(TEXT("leave")));
  }
  TestNotNull(TEXT("variant resource-hp-full-enemy resolves"), Lib.Find(TEXT("resource-hp-full-enemy")));
  FString GoldenText;
  if (FFileHelper::LoadFileToString(GoldenText, *S08GoldenPath())) {
    TSharedPtr<FJsonObject> G;
    const TSharedRef<TJsonReader<>> R = TJsonReaderFactory<>::Create(GoldenText);
    if (FJsonSerializer::Deserialize(R, G) && G.IsValid()) {
      TestEqual(TEXT("golden matches the contract revision"), G->GetStringField(TEXT("contract_revision")), Lib.Revision);
    }
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08IconMotionGoldenTest, "Unmatched.S08.IconMotion.Golden",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS08IconMotionGoldenTest::RunTest(const FString& Parameters) {
  FS08IconMotionLibrary Lib;
  FString Err;
  if (!TestTrue(TEXT("contract loads"), Lib.LoadFile(FS08IconMotionLibrary::DefaultPath(), &Err))) return false;
  FString Text;
  if (!TestTrue(TEXT("golden file readable: ") + S08GoldenPath(), FFileHelper::LoadFileToString(Text, *S08GoldenPath()))) {
    return false;
  }
  TSharedPtr<FJsonObject> G;
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
  if (!TestTrue(TEXT("golden parses"), FJsonSerializer::Deserialize(Reader, G) && G.IsValid())) return false;
  const float Tol = 1.0e-3f;
  int32 Samples = 0;
  int32 Mismatches = 0;
  for (const auto& IconPair : G->GetObjectField(TEXT("icons"))->Values) {
    const FS08IconMotionDef* Def = Lib.Find(FName(*IconPair.Key));
    if (!TestNotNull(*FString::Printf(TEXT("%s in contract"), *IconPair.Key), Def)) continue;
    for (const bool bReduced : {false, true}) {
      const TSharedPtr<FJsonObject> Mode = IconPair.Value->AsObject()->GetObjectField(bReduced ? TEXT("reduced") : TEXT("normal"));
      TArray<TPair<float, FName>> Script;
      float Total = 0.0f;
      S08IconMotion::DemoSchedule(*Def, bReduced, Script, Total);
      TestTrue(*FString::Printf(TEXT("%s %s demo length"), *IconPair.Key, bReduced ? TEXT("reduced") : TEXT("normal")),
               FMath::IsNearlyEqual(Total, static_cast<float>(Mode->GetNumberField(TEXT("total_ms"))), 0.01f));
      FS08IconAnimator Anim;
      Anim.Init(Def, bReduced);
      int32 Next = 0;
      for (const TSharedPtr<FJsonValue>& SV : Mode->GetArrayField(TEXT("samples"))) {
        const TSharedPtr<FJsonObject> S = SV->AsObject();
        const float T = static_cast<float>(S->GetNumberField(TEXT("t")));
        while (Next < Script.Num() && Script[Next].Key <= T) {
          Anim.Play(Script[Next].Value, Script[Next].Key);
          ++Next;
        }
        const FS08IconPose Pose = Anim.Pose(T);
        ++Samples;
        bool bOk = Pose.bVisible == (S->GetIntegerField(TEXT("v")) != 0);
        FString Where;
        const TSharedPtr<FJsonObject> P = S->GetObjectField(TEXT("pose"));
        for (int32 Target = 0; Target < Def->TargetCount() && bOk; ++Target) {
          const FString Name = Target == 0 ? FString(TEXT("all")) : Def->Layers[Target - 1].Id.ToString();
          const TArray<TSharedPtr<FJsonValue>>& Want = P->GetArrayField(Name);
          for (int32 Prop = 0; Prop < S08IconPropCount && bOk; ++Prop) {
            if (!FMath::IsNearlyEqual(Pose.Targets[Target].V[Prop], static_cast<float>(Want[Prop]->AsNumber()), Tol)) {
              bOk = false;
              Where = FString::Printf(TEXT("%s prop %d got %.5f want %.5f"), *Name, Prop, Pose.Targets[Target].V[Prop],
                                      Want[Prop]->AsNumber());
            }
          }
          const FVector2D Pv(Want[S08IconPropCount]->AsNumber(), Want[S08IconPropCount + 1]->AsNumber());
          if (bOk && !Pose.Targets[Target].PivotU.Equals(Pv, 1.0e-3)) {
            bOk = false;
            Where = FString::Printf(TEXT("%s pivot got %s want %s"), *Name, *Pose.Targets[Target].PivotU.ToString(), *Pv.ToString());
          }
        }
        if (!bOk) {
          ++Mismatches;
          if (Mismatches <= 10) {
            AddError(FString::Printf(TEXT("%s %s t=%.0f: %s"), *IconPair.Key, bReduced ? TEXT("reduced") : TEXT("normal"), T,
                                     Where.IsEmpty() ? TEXT("visibility") : *Where));
          }
        }
      }
    }
  }
  AddInfo(FString::Printf(TEXT("ICONMOTION golden samples=%d mismatches=%d"), Samples, Mismatches));
  TestTrue(TEXT("golden samples present"), Samples > 3000);
  return Mismatches == 0;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08IconMotionReducedTest, "Unmatched.S08.IconMotion.Reduced",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS08IconMotionReducedTest::RunTest(const FString& Parameters) {
  IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(TEXT("s08.ReducedMotion"));
  if (!TestNotNull(TEXT("s08.ReducedMotion exists"), CVar)) return false;
  const int32 Was = CVar->GetInt();
  CVar->Set(1, ECVF_SetByCode);
  TestTrue(TEXT("CVar 1 -> reduced"), S08IconMotion::IsReducedMotion());
  CVar->Set(0, ECVF_SetByCode);
  TestFalse(TEXT("CVar 0 -> normal (no -S08ReducedMotion flag in tests)"), S08IconMotion::IsReducedMotion());
  CVar->Set(Was, ECVF_SetByCode);
  // Reduced branch: appear is opacity-only (scale stays 1 at t = 0).
  FS08IconMotionLibrary Lib;
  Lib.LoadFile(FS08IconMotionLibrary::DefaultPath());
  const FS08IconMotionDef* Def = Lib.Find(TEXT("action-attack"));
  if (!TestNotNull(TEXT("action-attack"), Def)) return false;
  FS08IconAnimator A;
  A.Init(Def, true);
  A.Play(TEXT("appear"), 0.0f);
  const FS08IconPose P0 = A.Pose(0.0f);
  TestEqual(TEXT("reduced appear keeps scale 1"), P0.Targets[0].Get(ES08IconProp::Scale), 1.0f);
  TestEqual(TEXT("reduced appear starts transparent"), P0.Targets[0].Get(ES08IconProp::Opacity), 0.0f);
  TestTrue(TEXT("reduced appear done by 100 ms"), !A.IsMoving(101.0f));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08IconMotionTexturesTest, "Unmatched.S08.IconMotion.Textures",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS08IconMotionTexturesTest::RunTest(const FString& Parameters) {
  FS08IconMotionLibrary Lib;
  if (!TestTrue(TEXT("contract loads"), Lib.LoadFile(FS08IconMotionLibrary::DefaultPath()))) return false;
  // name -> 2:1 plate (canvas 64 u); variants take their base icon's canvas (VS-2 A2: by the contract, not by name)
  TMap<FString, bool> Names;
  for (const auto& Pair : Lib.Icons) {
    for (const FString& N : S08LayerTextureNames(Pair.Value)) Names.Add(N, Pair.Value.CanvasU.X > 32.0);
  }
  for (const auto& Pair : Lib.Variants) {
    const FS08IconMotionDef* Base = Lib.Find(Pair.Value);
    Names.Add(Pair.Key.ToString(), Base && Base->CanvasU.X > 32.0);
  }
  int32 Checked = 0;
  for (const auto& NameWide : Names) {
    const FString& N = NameWide.Key;
    FString Src = N;
    int32 Frame = 0;
    int32 Hash = INDEX_NONE;
    if (N.FindChar(TEXT('#'), Hash)) {
      Src = N.Left(Hash + 1);
      Frame = FCString::Atoi(*N.Mid(Hash + 1));
    }
    // IC-33: 18 / 36 for every record; VS-2 A2: the L6 badges at the cell also 16 / 21 (contract ue_sizes)
    TArray<int32> Sizes = {18, 24, 32, 36, 48, 64};
    if (N.StartsWith(TEXT("badge-order")) || N.StartsWith(TEXT("badge-refuse")) || N.StartsWith(TEXT("badge-conflict"))) {
      Sizes.Append({16, 21});
    }
    // VS-4 V3: the zone icons only from 24 px (IC-62...IC-69 ue_sizes 24 / 32 / 36 / 48 / 64)
    if (N.StartsWith(TEXT("zone-"))) Sizes = {24, 32, 36, 48, 64};
    for (const int32 Px : Sizes) {
      const FString Path = S08IconMotion::TextureObjectPath(Src, Frame, Px);
      UTexture2D* Tex = LoadObject<UTexture2D>(nullptr, *Path);
      if (!TestNotNull(*FString::Printf(TEXT("texture %s"), *Path), Tex)) continue;
      ++Checked;
      const bool bWide = NameWide.Value;
      // Source (imported) size: -nullrhi has no built platform data, so GetSizeX() would be 0.
      const FIntPoint Imported = Tex->GetImportedSize();
      TestEqual(*FString::Printf(TEXT("%s width"), *Path), Imported.X, bWide ? 2 * Px : Px);
      TestEqual(*FString::Printf(TEXT("%s height"), *Path), Imported.Y, Px);
#if WITH_EDITORONLY_DATA  // MipGenSettings is editor-only data: the packaged game target has no such member
      TestEqual(*FString::Printf(TEXT("%s no mips"), *Path), static_cast<int32>(Tex->MipGenSettings),
                static_cast<int32>(TMGS_NoMipmaps));
#endif
    }
  }
  AddInfo(FString::Printf(TEXT("ICONMOTION textures checked=%d names=%d"), Checked, Names.Num()));
  return Checked > 0;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08IconMotionWidgetTest, "Unmatched.S08.IconMotion.Widget",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS08IconMotionWidgetTest::RunTest(const FString& Parameters) {
  FS08IconTestWorld W(TEXT("S08IconMotionWidgetTest"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  US08AnimatedIconWidget* Icon = CreateWidget<US08AnimatedIconWidget>(W.World, US08AnimatedIconWidget::StaticClass());
  if (!TestNotNull(TEXT("widget"), Icon)) return false;
  Icon->SetReducedMotion(false);
  if (!TestTrue(TEXT("SetIcon action-attack"), Icon->SetIcon(TEXT("action-attack"), 48.0f, 48))) return false;
  TestEqual(TEXT("two layers (body, glyph)"), Icon->GetLayerCount(), 2);
  TestNotNull(TEXT("body texture loaded"), Icon->GetLayerTexture(0, 0));
  TestEqual(TEXT("canvas 48 su"), Icon->GetCanvasSizeSu(), FVector2D(48.0, 48.0));
  Icon->PlayAnimAt(TEXT("appear"), 0.0f);
  Icon->ApplyPose(36.0f);
  const FS08IconPose& Pose = Icon->GetLastPose();
  TestTrue(TEXT("visible during appear"), Pose.bVisible);
  const FWidgetTransform Applied = Icon->GetStage()->GetRenderTransform();
  TestTrue(TEXT("stage scale = root pose scale"),
           FMath::IsNearlyEqual(Applied.Scale.X, Pose.Targets[0].Get(ES08IconProp::Scale), 1.0e-4f));
  TestTrue(TEXT("stage opacity = root pose opacity"),
           FMath::IsNearlyEqual(Icon->GetStage()->GetRenderOpacity(), Pose.Targets[0].Get(ES08IconProp::Opacity), 1.0e-4f));
  Icon->PlayAnimAt(TEXT("select"), 400.0f);
  Icon->ApplyPose(470.0f);
  const float GlyphScale = Icon->GetLayerImage(1)->GetRenderTransform().Scale.X;
  TestTrue(TEXT("select pulses the glyph layer (1.12 at the beat)"), FMath::IsNearlyEqual(GlyphScale, 1.12f, 1.0e-3f));
  Icon->PlayAnimAt(TEXT("leave"), 1000.0f);
  Icon->ApplyPose(1200.0f);
  TestFalse(TEXT("hidden after leave"), Icon->GetLastPose().bVisible);
  // Flipbook: the hourglass swaps its glyph texture with the sand frame.
  US08AnimatedIconWidget* Sent = CreateWidget<US08AnimatedIconWidget>(W.World, US08AnimatedIconWidget::StaticClass());
  Sent->SetReducedMotion(false);
  if (TestTrue(TEXT("SetIcon state-sent"), Sent->SetIcon(TEXT("state-sent"), 48.0f, 48))) {
    Sent->PlayAnimAt(TEXT("appear"), 0.0f);
    Sent->ApplyPose(180.0f + 300.0f);  // cycle frame 3 (275 ms)
    const UObject* Res = Sent->GetLayerImage(1)->GetBrush().GetResourceObject();
    TestEqual(TEXT("sand frame 3 texture"), Res, static_cast<const UObject*>(Sent->GetLayerTexture(1, 3)));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08IconMotionSemanticsTest, "Unmatched.S08.IconMotion.Semantics",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS08IconMotionSemanticsTest::RunTest(const FString& Parameters) {
  // Review 2026-10-03 (same cases as tools/s08/hud_contract/test_icon_motion.py IconMotionSemanticsTests).
  FS08IconMotionLibrary Lib;
  if (!TestTrue(TEXT("contract loads"), Lib.LoadFile(FS08IconMotionLibrary::DefaultPath()))) return false;
  const FS08IconMotionDef* Attack = Lib.Find(TEXT("action-attack"));
  const FS08IconMotionDef* Hint = Lib.Find(TEXT("state-hint"));
  if (!TestNotNull(TEXT("action-attack"), Attack) || !TestNotNull(TEXT("state-hint"), Hint)) return false;
  auto Root = [](const FS08IconAnimator& A, float T, ES08IconProp P) { return A.Pose(T).Targets[0].Get(P); };
  {
    FS08IconAnimator A;
    A.Init(Attack, false);
    A.Play(TEXT("appear"), 0.0f);
    A.Play(TEXT("hover_in"), 300.0f);
    A.Play(TEXT("spend"), 500.0f);
    A.Play(TEXT("leave"), 1000.0f);
    TestTrue(TEXT("leave after hold: visible while fading"), A.Pose(1060.0f).bVisible);
    TestTrue(TEXT("leave after hold: opacity fades below the held 0.4"), Root(A, 1060.0f, ES08IconProp::Opacity) < 0.4f);
    TestTrue(TEXT("leave after hold: scale leaves the held 1.06"), Root(A, 1060.0f, ES08IconProp::Scale) < 1.06f);
    TestFalse(TEXT("leave after hold: hidden at the end"), A.Pose(1121.0f).bVisible);
  }
  {
    FS08IconAnimator A;
    A.Init(Attack, false);
    A.Play(TEXT("appear"), 0.0f);
    A.Play(TEXT("hover_in"), 300.0f);
    A.Play(TEXT("tap"), 600.0f);
    TestTrue(TEXT("tap starts from the hover scale (no jump)"), FMath::IsNearlyEqual(Root(A, 600.0f, ES08IconProp::Scale), 1.06f, 1.0e-4f));
    TestTrue(TEXT("tap dips to 0.94"), FMath::IsNearlyEqual(Root(A, 650.0f, ES08IconProp::Scale), 0.94f, 1.0e-4f));
    TestTrue(TEXT("after the tap the hover holds again"), FMath::IsNearlyEqual(Root(A, 800.0f, ES08IconProp::Scale), 1.06f, 1.0e-4f));
  }
  {
    FS08IconAnimator A;
    A.Init(Hint, false);
    A.Play(TEXT("appear"), 120.0f);
    TestFalse(TEXT("appear scheduled in the future is invisible before it starts"), A.Pose(60.0f).bVisible);
    TestTrue(TEXT("visible from its start"), A.Pose(120.0f).bVisible);
  }
  {
    FS08IconAnimator A;
    A.Init(Attack, false);
    A.Play(TEXT("appear"), 0.0f);
    A.Play(TEXT("release"), 500.0f);
    A.Play(TEXT("hover_out"), 500.0f);
    TestTrue(TEXT("equal start time: the later command wins"), FMath::IsNearlyEqual(Root(A, 700.0f, ES08IconProp::Scale), 1.0f, 1.0e-4f));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08IconMotionCombatViewTest, "Unmatched.S08.IconMotion.CombatView",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS08IconMotionCombatViewTest::RunTest(const FString& Parameters) {
  FS08IconTestWorld W(TEXT("S08IconMotionCombatViewTest"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  US08AnimatedIconWidget* Icon = CreateWidget<US08AnimatedIconWidget>(W.World, US08AnimatedIconWidget::StaticClass());
  if (!TestNotNull(TEXT("widget"), Icon)) return false;
  Icon->SetReducedMotion(false);
  Icon->SetClockOverrideMs(0.0f);
  const TSharedRef<IS08ArtIconView> View = S08MakeAnimatedIconView(*Icon, 48);
  TestEqual(TEXT("impl name"), FString(View->ImplName()), FString(TEXT("umg-motion")));
  FSlateBrush Brush;
  Brush.ImageSize = FVector2D(48.0, 48.0);
  View->SetIconBrush(Brush);
  TestEqual(TEXT("token icon set"), Icon->GetIconId(), FName(TEXT("action-attack-token")));
  View->SetShown(true);
  Icon->ApplyPose(0.0f);
  TestTrue(TEXT("visible at once (appear frame 0 is not empty)"), Icon->GetLastPose().bVisible);
  TestTrue(TEXT("appear starts at 1.25 (laid on from above)"),
           FMath::IsNearlyEqual(Icon->GetLastPose().Targets[0].Get(ES08IconProp::Scale), 1.25f, 1.0e-3f));
  Icon->ApplyPose(220.0f + 500.0f);
  TestTrue(TEXT("pulse peak 1.05 at 500 ms of the cycle"),
           FMath::IsNearlyEqual(Icon->GetLastPose().Targets[0].Get(ES08IconProp::Scale), 1.05f, 1.0e-3f));
  Icon->SetClockOverrideMs(1000.0f);
  View->SetShown(false);
  Icon->ApplyPose(1060.0f);
  TestTrue(TEXT("still visible while leaving"), Icon->GetLastPose().bVisible);
  Icon->ApplyPose(1121.0f);
  TestFalse(TEXT("hidden after the 120 ms leave"), Icon->GetLastPose().bVisible);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08IconMotionDefaultTokenTest, "Unmatched.S08.IconMotion.DefaultToken",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS08IconMotionDefaultTokenTest::RunTest(const FString& Parameters) {
  TestTrue(TEXT("no flag: animated v3 token"), S08IconMotion::UseAnimatedCombatToken(TEXT("")));
  TestTrue(TEXT("former opt-in flag: still v3"), S08IconMotion::UseAnimatedCombatToken(TEXT("-S08IconMotion")));
  TestFalse(TEXT("-S08IconLegacy: rollback to the W5b-R token"),
            S08IconMotion::UseAnimatedCombatToken(TEXT("-ArtPreview -S08IconLegacy")));
  return true;
}

namespace {
int32 S08LayerIndex(const FS08IconMotionDef* Def, const TCHAR* Id) {
  for (int32 L = 0; Def && L < Def->Layers.Num(); ++L) {
    if (Def->Layers[L].Id == FName(Id)) return L;
  }
  return INDEX_NONE;
}
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08IconMotionTurnPortraitTest, "Unmatched.S08.IconMotion.TurnPortrait",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS08IconMotionTurnPortraitTest::RunTest(const FString& Parameters) {
  FS08IconTestWorld W(TEXT("S08IconMotionTurnPortraitTest"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  const FLinearColor Gold = FLinearColor::FromSRGBColor(FColor(0xDA, 0xC5, 0x76));
  const FS08IconMotionLibrary& Lib = FS08IconMotionLibrary::Get();

  // the default look = the user's answers AB-5..AB-8 (2026-10-05): accepted art by default, no flag needed
  const FS08TurnHudLook Default = FS08TurnHudLook::FromCommandLine(TEXT("-ArtPreview"));
  TestEqual(TEXT("default: the warm ring"), Default.RingIcon, FName(TEXT("marker-turn-ring")));
  TestTrue(TEXT("default: heart glow"), Default.bHeartGlow);
  TestTrue(TEXT("default: DE tracker"), Default.bTrackerDe);
  TestTrue(TEXT("default: fallen cross and stamp"), Default.bCrossGlyphs);
  TestTrue(TEXT("default: nothing refused"), Default.Issues.IsEmpty());
  TestEqual(TEXT("default traced"), Default.Describe(),
            FString(TEXT("ring=marker-turn-ring heartGlow=1 tracker=de cross=1")));
  TestEqual(TEXT("no flags at all = the same look"), FS08TurnHudLook::FromCommandLine(TEXT("")).Describe(),
            Default.Describe());
  US08TurnPortraitWidget* Own = CreateWidget<US08TurnPortraitWidget>(W.World, US08TurnPortraitWidget::StaticClass());
  if (!TestNotNull(TEXT("portrait"), Own)) return false;
  Own->Setup(false, Default, Gold);
  TestTrue(TEXT("default: ring widget present"), Own->HasRingIcon());
  if (Own->GetRingIcon()) {
    TestEqual(TEXT("ring icon"), Own->GetRingIcon()->GetIconId(), FName(TEXT("marker-turn-ring")));
  }
  Own->SetActive(true);
  TestEqual(TEXT("own active status"), Own->GetStatusText()->GetText().ToString(), FString(TEXT("YOUR TURN")));
  Own->SetActive(false);
  TestEqual(TEXT("idle status"), Own->GetStatusText()->GetText().ToString(), FString(TEXT("waiting")));

  // heart (AB-6): damage plays with its glow halo drawn (200-1000 ms, peak at 320)
  US08AnimatedIconWidget* Heart = Own->GetHeartIcon();
  if (TestNotNull(TEXT("heart icon"), Heart)) {
    const int32 Glow = S08LayerIndex(Lib.Find(TEXT("resource-hp-full")), TEXT("glow"));
    if (TestTrue(TEXT("resource-hp-full has a glow layer"), Glow != INDEX_NONE)) {
      TestFalse(TEXT("glow drawn by default"), Heart->IsLayerHidden(TEXT("glow")));
      Heart->SetReducedMotion(false);
      Heart->ShowAtRest();
      const float T0 = Heart->GetClockMs();
      TestTrue(TEXT("damage plays"), Heart->PlayAnimAt(TEXT("damage"), T0));
      Heart->ApplyPose(T0 + 320.0f);
      TestTrue(TEXT("drawn: glow at 1.0 at 320 ms"),
               FMath::IsNearlyEqual(Heart->GetLayerImage(Glow)->GetRenderOpacity(), 1.0f, 1.0e-3f));
      Heart->ApplyPose(T0 + 1001.0f);
      TestTrue(TEXT("drawn: glow gone after 1000 ms"),
               FMath::IsNearlyEqual(Heart->GetLayerImage(Glow)->GetRenderOpacity(), 0.0f, 1.0e-3f));
    }
  }

  // tracker (AB-7): marker-action-slot-de slots - ring (ghost in the orange rim) 0.6 at rest; a spent slot fills with
  // its action type (body / glyph of action-<type>, 300 ms, held), a cancel unfills it, a new turn snaps
  const FS08IconMotionDef* SlotDef = Lib.Find(TEXT("marker-action-slot-de"));
  const int32 RingL = S08LayerIndex(SlotDef, TEXT("ring"));
  const int32 BodyL = S08LayerIndex(SlotDef, TEXT("body"));
  const int32 GlyphL = S08LayerIndex(SlotDef, TEXT("glyph"));
  if (!TestTrue(TEXT("slot layers ring / body / glyph"),
                RingL != INDEX_NONE && BodyL != INDEX_NONE && GlyphL != INDEX_NONE)) {
    return false;
  }
  auto Opacity = [](US08AnimatedIconWidget* Icon, int32 L) { return Icon->GetLayerImage(L)->GetRenderOpacity(); };
  TestEqual(TEXT("first apply resets"), Own->ApplyTracker(2, 0, true), FString(TEXT("reset")));
  TestEqual(TEXT("two slots"), Own->GetTrackerSlots(), 2);
  TestEqual(TEXT("slot icon: DE"), Own->GetTrackerIcon(0)->GetIconId(), FName(TEXT("marker-action-slot-de")));
  TestTrue(TEXT("empty slot: ring 0.6, no fill"),
           FMath::IsNearlyEqual(Opacity(Own->GetTrackerIcon(0), RingL), 0.6f, 1.0e-3f) &&
               FMath::IsNearlyEqual(Opacity(Own->GetTrackerIcon(0), BodyL), 0.0f, 1.0e-3f));
  TestEqual(TEXT("unchanged: nothing"), Own->ApplyTracker(2, 0, false), FString());
  for (int32 I = 0; I < Own->GetTrackerSlots(); ++I) Own->GetTrackerIcon(I)->SetReducedMotion(false);
  Own->ApplyTracker(2, 0, true);  // back at rest after the motion switch
  TestEqual(TEXT("chosen attack: spend"), Own->ApplyTracker(2, 1, false, {FName(TEXT("attack"))}),
            FString(TEXT("spend")));
  US08AnimatedIconWidget* Slot0 = Own->GetTrackerIcon(0);
  if (TestNotNull(TEXT("slot 0"), Slot0)) {
    TestEqual(TEXT("slot 0 filled with the attack"), Own->GetTrackerFill(0), FString(TEXT("attack")));
    TestEqual(TEXT("body from action-attack"), Slot0->GetLayerSource(TEXT("body")), FString(TEXT("action-attack_body")));
    Slot0->ApplyPose(Slot0->GetClockMs() + 300.0f);
    TestTrue(TEXT("filled: body and glyph at 1, ring gone"),
             FMath::IsNearlyEqual(Opacity(Slot0, BodyL), 1.0f, 1.0e-3f) &&
                 FMath::IsNearlyEqual(Opacity(Slot0, GlyphL), 1.0f, 1.0e-3f) &&
                 FMath::IsNearlyEqual(Opacity(Slot0, RingL), 0.0f, 1.0e-3f));
  }
  TestEqual(TEXT("second action, a maneuver: spend"),
            Own->ApplyTracker(2, 2, false, {FName(TEXT("attack")), FName(TEXT("maneuver"))}), FString(TEXT("spend")));
  if (US08AnimatedIconWidget* Slot1 = Own->GetTrackerIcon(1)) {
    TestEqual(TEXT("slot 1 filled with the maneuver"), Slot1->GetLayerSource(TEXT("glyph")),
              FString(TEXT("action-maneuver_glyph")));
    TestEqual(TEXT("slot 0 keeps the attack"), Own->GetTrackerFill(0), FString(TEXT("attack")));
    TestEqual(TEXT("cancelled: gain"), Own->ApplyTracker(2, 1, false, {FName(TEXT("attack"))}), FString(TEXT("gain")));
    Slot1->ApplyPose(Slot1->GetClockMs() + 150.0f);
    TestTrue(TEXT("unfilled: the empty slot again (ring 0.6, no body)"),
             FMath::IsNearlyEqual(Opacity(Slot1, RingL), 0.6f, 1.0e-3f) &&
                 FMath::IsNearlyEqual(Opacity(Slot1, BodyL), 0.0f, 1.0e-3f));
  }
  TestEqual(TEXT("gained action: a third slot"), Own->ApplyTracker(3, 1, false), FString(TEXT("slots")));
  TestEqual(TEXT("three slots"), Own->GetTrackerSlots(), 3);
  TestEqual(TEXT("new turn: reset"), Own->ApplyTracker(2, 1, true, {FName(TEXT("scheme"))}), FString(TEXT("reset")));
  TestEqual(TEXT("back to two slots"), Own->GetTrackerSlots(), 2);
  if (Own->GetTrackerIcon(0) && Own->GetTrackerIcon(1)) {
    TestEqual(TEXT("reset refills slot 0 with the scheme"), Own->GetTrackerFill(0), FString(TEXT("scheme")));
    TestTrue(TEXT("reset with a spent slot: slot 0 filled at once"),
             FMath::IsNearlyEqual(Opacity(Own->GetTrackerIcon(0), BodyL), 1.0f, 1.0e-3f) &&
                 FMath::IsNearlyEqual(Opacity(Own->GetTrackerIcon(0), RingL), 0.0f, 1.0e-3f));
    TestTrue(TEXT("reset: slot 1 empty at once"),
             FMath::IsNearlyEqual(Opacity(Own->GetTrackerIcon(1), RingL), 0.6f, 1.0e-3f) &&
                 FMath::IsNearlyEqual(Opacity(Own->GetTrackerIcon(1), BodyL), 0.0f, 1.0e-3f));
  }

  // fallen (AB-8): at the heart mark the heart becomes resource-hp-fallen, the cross stamps in (scale 0 -> 1.08 -> 1)
  TestTrue(TEXT("fallen: the heart changes"), Own->SetHeartFallen(true));
  TestFalse(TEXT("fallen twice: no-op"), Own->SetHeartFallen(true));
  if (US08AnimatedIconWidget* Fallen = Own->GetHeartIcon()) {
    TestEqual(TEXT("fallen icon"), Fallen->GetIconId(), FName(TEXT("resource-hp-fallen")));
    const int32 Cross = S08LayerIndex(Lib.Find(TEXT("resource-hp-fallen")), TEXT("cross"));
    if (TestTrue(TEXT("fallen cross layer"), Cross != INDEX_NONE) && !Fallen->IsReducedMotion()) {
      const float T0 = Fallen->GetClockMs();
      Fallen->ApplyPose(T0);
      TestTrue(TEXT("frame 0: the blackened heart without the cross"),
               FMath::IsNearlyEqual(Fallen->GetLastPose().Targets[Cross + 1].Get(ES08IconProp::Scale), 0.0f, 1.0e-3f));
      Fallen->ApplyPose(T0 + 200.0f);
      TestTrue(TEXT("200 ms: the cross stands"),
               Fallen->GetLastPose().bVisible &&
                   FMath::IsNearlyEqual(Fallen->GetLastPose().Targets[Cross + 1].Get(ES08IconProp::Scale), 1.0f,
                                        1.0e-3f));
    }
  }
  TestTrue(TEXT("a new game: the full heart back"), Own->SetHeartFallen(false));
  if (Own->GetHeartIcon()) {
    TestEqual(TEXT("full heart icon"), Own->GetHeartIcon()->GetIconId(), FName(TEXT("resource-hp-full")));
    TestTrue(TEXT("full heart at rest is visible"), Own->GetHeartIcon()->GetLastPose().bVisible);
  }

  // ring (AB-5) on the opponent's portrait: flash 1000 ms -> rim 0.35, at rest, leave
  US08TurnPortraitWidget* Opp = CreateWidget<US08TurnPortraitWidget>(W.World, US08TurnPortraitWidget::StaticClass());
  Opp->Setup(true, Default, Gold);
  Opp->SetActive(true);
  TestEqual(TEXT("opponent active status"), Opp->GetStatusText()->GetText().ToString(), FString(TEXT("THEIR TURN")));
  if (TestTrue(TEXT("ring widget present"), Opp->HasRingIcon())) {
    US08AnimatedIconWidget* RingIcon = Opp->GetRingIcon();
    RingIcon->SetReducedMotion(false);
    Opp->PlayRing(false);
    TestTrue(TEXT("ring shown"), Opp->IsRingShown());
    const float T0 = RingIcon->GetClockMs();
    RingIcon->ApplyPose(T0 + 120.0f);
    TestTrue(TEXT("flash at full at 120 ms"),
             FMath::IsNearlyEqual(RingIcon->GetLayerImage(1)->GetRenderOpacity(), 1.0f, 1.0e-3f));
    RingIcon->ApplyPose(T0 + 1000.0f);
    TestTrue(TEXT("rim smoulders at 0.35 after 1000 ms"),
             FMath::IsNearlyEqual(RingIcon->GetLayerImage(0)->GetRenderOpacity(), 0.35f, 1.0e-3f));
    TestTrue(TEXT("flash gone after 1000 ms"),
             FMath::IsNearlyEqual(RingIcon->GetLayerImage(1)->GetRenderOpacity(), 0.0f, 1.0e-3f));
    RingIcon->ApplyPose(T0 + 60000.0f);
    TestTrue(TEXT("still smouldering a minute later (no cycle)"), RingIcon->GetLastPose().bVisible);
    Opp->StopRing();
    RingIcon->ApplyPose(RingIcon->GetClockMs() + 200.0f);
    TestFalse(TEXT("leave hides it"), RingIcon->GetLastPose().bVisible);
    Opp->PlayRing(true);
    TestTrue(TEXT("at rest: rim 0.35 at once"),
             FMath::IsNearlyEqual(RingIcon->GetLayerImage(0)->GetRenderOpacity(), 0.35f, 1.0e-3f));
    TestTrue(TEXT("at rest: no flash"),
             FMath::IsNearlyEqual(RingIcon->GetLayerImage(1)->GetRenderOpacity(), 0.0f, 1.0e-3f));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08IconMotionTurnHudRollbacksTest, "Unmatched.S08.IconMotion.TurnHudRollbacks",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS08IconMotionTurnHudRollbacksTest::RunTest(const FString& Parameters) {
  FS08IconTestWorld W(TEXT("S08IconMotionTurnHudRollbacksTest"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  const FLinearColor Gold = FLinearColor::FromSRGBColor(FColor(0xDA, 0xC5, 0x76));
  auto Portrait = [&](const TCHAR* Cmd) {
    US08TurnPortraitWidget* P = CreateWidget<US08TurnPortraitWidget>(W.World, US08TurnPortraitWidget::StaticClass());
    if (P) P->Setup(false, FS08TurnHudLook::FromCommandLine(Cmd), Gold);
    return P;
  };
  TestEqual(TEXT("flag names"),
            FString::Printf(TEXT("%s %s %s %s"), FS08TurnHudLook::RingLegacyFlag, FS08TurnHudLook::HeartGlowLegacyFlag,
                            FS08TurnHudLook::TrackerLegacyFlag, FS08TurnHudLook::CrossLegacyFlag),
            FString(TEXT("S08TurnRingLegacy S08HeartGlowLegacy S08TrackerLegacy S08CrossLegacy")));

  // AB-5 rollback: no ring; -S08TurnRingIcon picks another record (=none: no ring), an unknown id is refused
  {
    const FS08TurnHudLook L = FS08TurnHudLook::FromCommandLine(TEXT("-S08TurnRingLegacy"));
    TestTrue(TEXT("-S08TurnRingLegacy: no ring"), L.RingIcon.IsNone() && L.Issues.IsEmpty());
    TestTrue(TEXT("-S08TurnRingLegacy: the rest stays"), L.bHeartGlow && L.bTrackerDe && L.bCrossGlyphs);
    US08TurnPortraitWidget* P = Portrait(TEXT("-S08TurnRingLegacy"));
    if (TestNotNull(TEXT("portrait"), P)) {
      TestFalse(TEXT("-S08TurnRingLegacy: ring widget absent"), P->HasRingIcon());
      P->PlayRing(false);
      TestFalse(TEXT("-S08TurnRingLegacy: PlayRing is a no-op"), P->IsRingShown());
    }
    TestTrue(TEXT("-S08TurnRingIcon=none: no ring"),
             FS08TurnHudLook::FromCommandLine(TEXT("-S08TurnRingIcon=none")).RingIcon.IsNone());
    const FS08TurnHudLook Bad = FS08TurnHudLook::FromCommandLine(TEXT("-S08TurnRingIcon=no-such-icon"));
    TestTrue(TEXT("unknown ring refused"), Bad.RingIcon.IsNone() && !Bad.Issues.IsEmpty());
    TestTrue(TEXT("refusal traced"), Bad.Describe().Contains(TEXT(" issues=ring_'no-such-icon'_refused")));
    TestEqual(TEXT("the team candidate by the A/B option"),
              FS08TurnHudLook::FromCommandLine(TEXT("-S08TurnRingIcon=marker-turn-ring-team")).RingIcon,
              FName(TEXT("marker-turn-ring-team")));
  }
  // AB-6 rollback: the glow layer hidden (drawn 0 at the 320 ms peak); the former -S08HeartGlow changes nothing
  {
    US08TurnPortraitWidget* P = Portrait(TEXT("-S08HeartGlowLegacy"));
    US08AnimatedIconWidget* Heart = P ? P->GetHeartIcon() : nullptr;
    if (TestNotNull(TEXT("heart"), Heart)) {
      TestTrue(TEXT("-S08HeartGlowLegacy: glow hidden"), Heart->IsLayerHidden(TEXT("glow")));
      const int32 Glow = S08LayerIndex(FS08IconMotionLibrary::Get().Find(TEXT("resource-hp-full")), TEXT("glow"));
      Heart->SetReducedMotion(false);
      Heart->ShowAtRest();
      const float T0 = Heart->GetClockMs();
      Heart->PlayAnimAt(TEXT("damage"), T0);
      Heart->ApplyPose(T0 + 320.0f);
      TestTrue(TEXT("-S08HeartGlowLegacy: pose glow 1.0, drawn 0"),
               Glow != INDEX_NONE &&
                   FMath::IsNearlyEqual(Heart->GetLastPose().Targets[Glow + 1].Get(ES08IconProp::Opacity), 1.0f,
                                        1.0e-3f) &&
                   FMath::IsNearlyEqual(Heart->GetLayerImage(Glow)->GetRenderOpacity(), 0.0f));
    }
    TestTrue(TEXT("-S08HeartGlow alias: glow stays on"),
             FS08TurnHudLook::FromCommandLine(TEXT("-S08HeartGlow")).bHeartGlow);
  }
  // AB-7 rollback: the v3 slots - resource-action-full, spend fades the icon over the empty token, gain, reset
  {
    US08TurnPortraitWidget* P = Portrait(TEXT("-S08TrackerLegacy"));
    if (TestNotNull(TEXT("portrait"), P)) {
      P->ApplyTracker(2, 0, true);
      TestEqual(TEXT("-S08TrackerLegacy: v3 slot"), P->GetTrackerIcon(0)->GetIconId(),
                FName(TEXT("resource-action-full")));
      for (int32 I = 0; I < P->GetTrackerSlots(); ++I) P->GetTrackerIcon(I)->SetReducedMotion(false);
      P->ApplyTracker(2, 0, true);
      TestEqual(TEXT("chosen: spend"), P->ApplyTracker(2, 1, false, {FName(TEXT("attack"))}), FString(TEXT("spend")));
      US08AnimatedIconWidget* Slot0 = P->GetTrackerIcon(0);
      Slot0->ApplyPose(Slot0->GetClockMs() + 150.0f);
      TestTrue(TEXT("v3 spent: icon layer at 0"),
               FMath::IsNearlyEqual(Slot0->GetLayerImage(1)->GetRenderOpacity(), 0.0f, 1.0e-3f));
      TestTrue(TEXT("v3 spent: empty token shown"),
               FMath::IsNearlyEqual(Slot0->GetLayerImage(0)->GetRenderOpacity(), 1.0f, 1.0e-3f));
      TestEqual(TEXT("v3: no type fill"), P->GetTrackerFill(0), FString());
      TestEqual(TEXT("cancelled: gain"), P->ApplyTracker(2, 0, false), FString(TEXT("gain")));
      TestEqual(TEXT("new turn: reset"), P->ApplyTracker(2, 1, true), FString(TEXT("reset")));
      TestTrue(TEXT("v3 reset: slot 0 faded at once, slot 1 full"),
               FMath::IsNearlyEqual(P->GetTrackerIcon(0)->GetLayerImage(1)->GetRenderOpacity(), 0.0f, 1.0e-3f) &&
                   FMath::IsNearlyEqual(P->GetTrackerIcon(1)->GetLayerImage(1)->GetRenderOpacity(), 1.0f, 1.0e-3f));
    }
  }
  // AB-8 rollback: no fallen glyph - the emptied heart stays
  {
    US08TurnPortraitWidget* P = Portrait(TEXT("-S08CrossLegacy"));
    if (TestNotNull(TEXT("portrait"), P)) {
      TestFalse(TEXT("-S08CrossLegacy: SetHeartFallen is a no-op"), P->SetHeartFallen(true));
      TestEqual(TEXT("-S08CrossLegacy: the full heart icon stays"), P->GetHeartIcon()->GetIconId(),
                FName(TEXT("resource-hp-full")));
    }
  }
  // the trace fields: HUD-TURN config and the ARTLOOK hud field name every rolled back part by its flag
  TestEqual(TEXT("ARTLOOK hud default"), FS08TurnHudLook::ArtLookField(TEXT("")),
            FString(TEXT("hud=ring:marker-turn-ring,glow:on,tracker:de,cross:on")));
  TestEqual(TEXT("ARTLOOK hud rollbacks"),
            FS08TurnHudLook::ArtLookField(
                TEXT("-S08TurnRingLegacy -S08HeartGlowLegacy -S08TrackerLegacy -S08CrossLegacy")),
            FString(TEXT("hud=ring:legacy(-S08TurnRingLegacy),glow:legacy(-S08HeartGlowLegacy),")
                        TEXT("tracker:legacy(-S08TrackerLegacy),cross:legacy(-S08CrossLegacy)")));
  TestEqual(TEXT("ARTLOOK hud ring choice"),
            FS08TurnHudLook::ArtLookField(TEXT("-S08TurnRingIcon=marker-turn-ring-team")),
            FString(TEXT("hud=ring:marker-turn-ring-team,glow:on,tracker:de,cross:on")));
  TestEqual(TEXT("HUD-TURN config rollbacks"),
            FS08TurnHudLook::FromCommandLine(
                TEXT("-S08TurnRingLegacy -S08HeartGlowLegacy -S08TrackerLegacy -S08CrossLegacy"))
                .Describe(),
            FString(TEXT("ring=none heartGlow=0 tracker=v3 cross=0")));
  return true;
}

// VS-2 IC-70: the -S08IconGallery grid holds every contract icon in `order`, and the trace line `ICONGALLERY ids`
// (US08IconGalleryWidget::IdList) names each id of the contract lists accepted_vr44, accepted_de012 and candidates.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08IconMotionGalleryIdsTest, "Unmatched.S08.IconMotion.GalleryIds",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS08IconMotionGalleryIdsTest::RunTest(const FString& Parameters) {
  FString Text;
  if (!TestTrue(TEXT("contract file"), FFileHelper::LoadFileToString(Text, *FS08IconMotionLibrary::DefaultPath()))) {
    return false;
  }
  TSharedPtr<FJsonObject> Root;
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
  if (!TestTrue(TEXT("contract parses"), FJsonSerializer::Deserialize(Reader, Root) && Root.IsValid())) return false;
  FS08IconTestWorld W(TEXT("S08IconMotionGalleryIdsTest"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  US08IconGalleryWidget* Gallery = CreateWidget<US08IconGalleryWidget>(W.World, US08IconGalleryWidget::StaticClass());
  if (!TestNotNull(TEXT("gallery widget"), Gallery)) return false;
  const FS08IconMotionLibrary& Lib = FS08IconMotionLibrary::Get();
  // Rows fit the 1080 su canvas: 45 icons at 64 su -> 7 columns x 7 rows (6 columns would squeeze 8 rows into 1080 su
  // and centre each 130 su cell half a pixel off); 28 icons (run I) keep the 6 columns.
  const int32 Columns = US08IconGalleryWidget::ColumnsToFit(Lib.Order.Num(), 64.0f, 1080.0f);
  TestEqual(TEXT("cell 64 su"), US08IconGalleryWidget::CellSizeSu(64.0f), FVector2D(168.0, 130.0));
  TestEqual(TEXT("45 icons -> 7 columns"), US08IconGalleryWidget::ColumnsToFit(45, 64.0f, 1080.0f), 7);
  TestEqual(TEXT("28 icons -> 6 columns"), US08IconGalleryWidget::ColumnsToFit(28, 64.0f, 1080.0f), 6);
  const int32 Rows = FMath::DivideAndRoundUp(Lib.Order.Num(), Columns);
  TestTrue(TEXT("rows fit 1080 su"),
           Rows * (US08IconGalleryWidget::CellSizeSu(64.0f).Y + 2.0f * US08IconGalleryWidget::SlotPaddingSu) <= 1080.0f);
  const int32 Count = Gallery->Build(64.0f, 64, /*bInReduced=*/false, Columns, /*bLabels=*/true);
  TestEqual(TEXT("gallery = contract order"), Count, Lib.Order.Num());
  TArray<FString> Ids;
  Gallery->IdList().ParseIntoArray(Ids, TEXT(","), true);
  TestEqual(TEXT("IdList count"), Ids.Num(), Count);
  for (int32 I = 0; I < FMath::Min(Ids.Num(), Lib.Order.Num()); ++I) {
    TestEqual(*FString::Printf(TEXT("grid %d in contract order"), I), Ids[I], Lib.Order[I].ToString());
  }
  int32 Listed = 0;
  for (const TCHAR* List : {TEXT("accepted_vr44"), TEXT("accepted_de012"), TEXT("candidates")}) {
    const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
    if (!TestTrue(*FString::Printf(TEXT("%s present"), List), Root->TryGetArrayField(List, Values) && Values)) continue;
    for (const TSharedPtr<FJsonValue>& V : *Values) {
      TestTrue(*FString::Printf(TEXT("%s %s in the gallery trace"), List, *V->AsString()), Ids.Contains(V->AsString()));
      ++Listed;
    }
  }
  TestEqual(TEXT("26 VR44 (VS-4 V3: + 8 zone icons; VS-6 F2: + state-heal) + 4 DE-012 + 1 candidate"), Listed, 31);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS

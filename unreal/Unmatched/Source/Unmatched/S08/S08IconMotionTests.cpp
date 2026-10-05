// HUD icon motion v3 automation tests (docs/unreal/contracts/hud/ICON-MOTION-PLAN.md, phase C):
//   Load    - Config/S08IconMotion.json parses: 23 v3 icons + 5 DE-012 records (4 accepted 2026-10-05, the team ring
//             a candidate), appear/leave each, the fallen heart on its own blackened layer, revision = the golden file's;
//   Golden  - FS08IconAnimator replays every icon's demo script (normal and reduced) and matches the Python
//             reference poses docs/unreal/contracts/hud/icon-motion-golden.json (8 props + pivot, 1e-3);
//   Reduced - s08.ReducedMotion drives S08IconMotion::IsReducedMotion;
//   Textures- every layer texture of the contract exists at 24/32/48/64 px with the exact size and no mips;
//   Widget  - US08AnimatedIconWidget builds one image per layer and applies the evaluator's pose;
//   Semantics - events over the base (review 2026-10-03): leave after hold fades, tap after hover returns to it,
//             a future appear is invisible, equal start time -> the later command wins;
//   CombatView - the combat token view: show = appear + pulse, hide = leave, then hidden.
//   DefaultToken - RD-1: the animated v3 token is the default, -S08IconLegacy is the rollback.
//   TurnPortrait - DE-023: the persistent HUD portrait - no ring by default (the DE-012 ring is a candidate until the
//             art acceptance, -S08TurnRingIcon=<id> draws it: flash 1000 ms -> rim 0.35, at rest, leave), the heart
//             damage without its glow layer (-S08HeartGlow keeps it), the tracker spend / gain / reset in one frame.
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
  TestEqual(TEXT("28 icons in order"), Lib.Order.Num(), 28);
  TestEqual(TEXT("28 icon definitions"), Lib.Icons.Num(), 28);
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
  TSet<FString> Names;
  for (const auto& Pair : Lib.Icons) Names.Append(S08LayerTextureNames(Pair.Value));
  Names.Add(TEXT("resource-hp-full-enemy"));
  int32 Checked = 0;
  for (const FString& N : Names) {
    FString Src = N;
    int32 Frame = 0;
    int32 Hash = INDEX_NONE;
    if (N.FindChar(TEXT('#'), Hash)) {
      Src = N.Left(Hash + 1);
      Frame = FCString::Atoi(*N.Mid(Hash + 1));
    }
    for (const int32 Px : {24, 32, 48, 64}) {
      const FString Path = S08IconMotion::TextureObjectPath(Src, Frame, Px);
      UTexture2D* Tex = LoadObject<UTexture2D>(nullptr, *Path);
      if (!TestNotNull(*FString::Printf(TEXT("texture %s"), *Path), Tex)) continue;
      ++Checked;
      const bool bWide = Src.StartsWith(TEXT("state-hint")) || Src.StartsWith(TEXT("state-threat"));
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08IconMotionTurnPortraitTest, "Unmatched.S08.IconMotion.TurnPortrait",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FS08IconMotionTurnPortraitTest::RunTest(const FString& Parameters) {
  FS08IconTestWorld W(TEXT("S08IconMotionTurnPortraitTest"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  const FLinearColor Gold = FLinearColor::FromSRGBColor(FColor(0xDA, 0xC5, 0x76));

  // the default look: no ring drawn (accepted art by default - the ring glyph waits for the art acceptance)
  const FS08TurnHudLook Default = FS08TurnHudLook::FromCommandLine(TEXT("-ArtPreview"));
  TestTrue(TEXT("default: no ring icon"), Default.RingIcon.IsNone());
  TestFalse(TEXT("default: no heart glow"), Default.bHeartGlow);
  US08TurnPortraitWidget* Own = CreateWidget<US08TurnPortraitWidget>(W.World, US08TurnPortraitWidget::StaticClass());
  if (!TestNotNull(TEXT("portrait"), Own)) return false;
  Own->Setup(false, Default, Gold);
  TestFalse(TEXT("default: ring widget absent"), Own->HasRingIcon());
  Own->PlayRing(false);
  TestFalse(TEXT("default: PlayRing is a no-op"), Own->IsRingShown());
  Own->SetActive(true);
  TestEqual(TEXT("own active status"), Own->GetStatusText()->GetText().ToString(), FString(TEXT("YOUR TURN")));
  Own->SetActive(false);
  TestEqual(TEXT("idle status"), Own->GetStatusText()->GetText().ToString(), FString(TEXT("waiting")));

  // heart: damage plays (1000 ms, the shake 0-200) but the glow layer stays at 0 by default
  US08AnimatedIconWidget* Heart = Own->GetHeartIcon();
  if (TestNotNull(TEXT("heart icon"), Heart)) {
    const FS08IconMotionDef* Def = FS08IconMotionLibrary::Get().Find(TEXT("resource-hp-full"));
    int32 Glow = INDEX_NONE;
    for (int32 L = 0; Def && L < Def->Layers.Num(); ++L) {
      if (Def->Layers[L].Id == FName(TEXT("glow"))) Glow = L;
    }
    if (TestTrue(TEXT("resource-hp-full has a glow layer"), Glow != INDEX_NONE)) {
      TestTrue(TEXT("glow hidden by default"), Heart->IsLayerHidden(TEXT("glow")));
      Heart->SetReducedMotion(false);
      Heart->ShowAtRest();
      TestTrue(TEXT("damage plays"), Heart->PlayAnimAt(TEXT("damage"), Heart->GetClockMs()));
      Heart->ApplyPose(Heart->GetClockMs() + 320.0f);
      TestTrue(TEXT("pose: glow at 1.0 at 320 ms"),
               FMath::IsNearlyEqual(Heart->GetLastPose().Targets[Glow + 1].Get(ES08IconProp::Opacity), 1.0f, 1.0e-3f));
      TestTrue(TEXT("drawn: glow at 0"), FMath::IsNearlyEqual(Heart->GetLayerImage(Glow)->GetRenderOpacity(), 0.0f));
    }
    US08TurnPortraitWidget* WithGlow =
        CreateWidget<US08TurnPortraitWidget>(W.World, US08TurnPortraitWidget::StaticClass());
    WithGlow->Setup(false, FS08TurnHudLook::FromCommandLine(TEXT("-S08HeartGlow")), Gold);
    TestFalse(TEXT("-S08HeartGlow: glow drawn"), WithGlow->GetHeartIcon()->IsLayerHidden(TEXT("glow")));
  }

  // tracker: resource-action-full slots; spend at the choice, gain on cancel, reset in one frame
  TestEqual(TEXT("first apply resets"), Own->ApplyTracker(2, 0, true), FString(TEXT("reset")));
  TestEqual(TEXT("two slots"), Own->GetTrackerSlots(), 2);
  TestEqual(TEXT("unchanged: nothing"), Own->ApplyTracker(2, 0, false), FString());
  for (int32 I = 0; I < Own->GetTrackerSlots(); ++I) Own->GetTrackerIcon(I)->SetReducedMotion(false);
  Own->ApplyTracker(2, 0, true);  // back at rest after the motion switch
  TestEqual(TEXT("chosen: spend"), Own->ApplyTracker(2, 1, false), FString(TEXT("spend")));
  US08AnimatedIconWidget* Slot0 = Own->GetTrackerIcon(0);
  if (TestNotNull(TEXT("slot 0"), Slot0)) {
    Slot0->ApplyPose(Slot0->GetClockMs() + 150.0f);
    // resource-action-full layers: under (resource-action-empty), icon - spend fades the icon out (held)
    TestTrue(TEXT("spent: icon layer at 0"),
             FMath::IsNearlyEqual(Slot0->GetLayerImage(1)->GetRenderOpacity(), 0.0f, 1.0e-3f));
    TestTrue(TEXT("spent: empty token shown"),
             FMath::IsNearlyEqual(Slot0->GetLayerImage(0)->GetRenderOpacity(), 1.0f, 1.0e-3f));
  }
  TestEqual(TEXT("cancelled: gain"), Own->ApplyTracker(2, 0, false), FString(TEXT("gain")));
  TestEqual(TEXT("gained action: a third slot"), Own->ApplyTracker(3, 0, false), FString(TEXT("slots")));
  TestEqual(TEXT("three slots"), Own->GetTrackerSlots(), 3);
  TestEqual(TEXT("new turn: reset"), Own->ApplyTracker(2, 1, true), FString(TEXT("reset")));
  TestEqual(TEXT("back to two slots"), Own->GetTrackerSlots(), 2);
  if (Own->GetTrackerIcon(0) && Own->GetTrackerIcon(1)) {
    TestTrue(TEXT("reset with a spent slot: slot 0 faded at once"),
             FMath::IsNearlyEqual(Own->GetTrackerIcon(0)->GetLayerImage(1)->GetRenderOpacity(), 0.0f, 1.0e-3f));
    TestTrue(TEXT("reset: slot 1 full at once"),
             FMath::IsNearlyEqual(Own->GetTrackerIcon(1)->GetLayerImage(1)->GetRenderOpacity(), 1.0f, 1.0e-3f));
  }

  // the ring candidate only through the command line (the A/B option): flash 1000 ms -> rim 0.35, at rest, leave
  const FS08TurnHudLook Bad = FS08TurnHudLook::FromCommandLine(TEXT("-S08TurnRingIcon=no-such-icon"));
  TestTrue(TEXT("unknown ring refused"), Bad.RingIcon.IsNone() && !Bad.Issues.IsEmpty());
  const FS08TurnHudLook Ring = FS08TurnHudLook::FromCommandLine(TEXT("-S08TurnRingIcon=marker-turn-ring"));
  TestEqual(TEXT("ring id from the flag"), Ring.RingIcon, FName(TEXT("marker-turn-ring")));
  US08TurnPortraitWidget* Opp = CreateWidget<US08TurnPortraitWidget>(W.World, US08TurnPortraitWidget::StaticClass());
  Opp->Setup(true, Ring, Gold);
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

#endif  // WITH_AUTOMATION_TESTS

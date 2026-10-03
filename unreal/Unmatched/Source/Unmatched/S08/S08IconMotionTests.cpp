// HUD icon motion v3 automation tests (docs/unreal/contracts/hud/ICON-MOTION-PLAN.md, phase C):
//   Load    - Config/S08IconMotion.json parses: 23 icons, appear/leave each, revision = the golden file's;
//   Golden  - FS08IconAnimator replays every icon's demo script (normal and reduced) and matches the Python
//             reference poses docs/unreal/contracts/hud/icon-motion-golden.json (8 props + pivot, 1e-3);
//   Reduced - s08.ReducedMotion drives S08IconMotion::IsReducedMotion;
//   Textures- every layer texture of the contract exists at 24/32/48/64 px with the exact size and no mips;
//   Widget  - US08AnimatedIconWidget builds one image per layer and applies the evaluator's pose;
//   CombatView - the -S08IconMotion combat token view: show = appear + pulse, hide = leave, then hidden.
// Headless:
//   UnrealEditor-Cmd.exe Unmatched.uproject -ExecCmds="Automation RunTests Unmatched.S08.IconMotion; Quit"
//     -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08AnimatedIconWidget.h"
#include "S08ArtHudViews.h"
#include "S08IconMotion.h"
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
  TestEqual(TEXT("23 icons in order"), Lib.Order.Num(), 23);
  TestEqual(TEXT("23 icon definitions"), Lib.Icons.Num(), 23);
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
      TestEqual(*FString::Printf(TEXT("%s no mips"), *Path), static_cast<int32>(Tex->MipGenSettings),
                static_cast<int32>(TMGS_NoMipmaps));
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

#endif  // WITH_AUTOMATION_TESTS

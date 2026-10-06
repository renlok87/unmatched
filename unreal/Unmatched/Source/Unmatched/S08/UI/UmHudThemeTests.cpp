// VS-1 HB-04 automation tests of UI/UmHudTheme.h:
//   Theme.Load      /Game/S08/UI/Theme/DA_UmHudTheme loads, was imported from the same JSON as the header (sha256), every
//                   token of hud-style-tokens.json is in its maps with the header values, 29 skins are rounded boxes;
//   Theme.Fallback  without the asset the theme is built from S08HudTokens.generated.h (one Warning) with the same values.
//   node tools/s08/run-ue-tests.cjs Unmatched.S08.Hud.Theme <log>
#if WITH_AUTOMATION_TESTS

#include "UmHudTheme.h"
#include "../S08HudTokens.generated.h"
#include "Dom/JsonObject.h"
#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace {
TSharedPtr<FJsonObject> LoadThemeTokensJson(FString& OutPath) {
  OutPath = FPaths::ConvertRelativePathToFull(
      FPaths::Combine(FPaths::ProjectDir(), TEXT("../../docs/unreal/contracts/hud/hud-style-tokens.json")));
  FString Text;
  TSharedPtr<FJsonObject> Doc;
  if (!FFileHelper::LoadFileToString(Text, *OutPath) ||
      !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Doc)) {
    return nullptr;
  }
  return Doc;
}

/** The theme has exactly the header values (both paths go through FLinearColor::FromSRGBColor). */
void CheckHeaderValues(FAutomationTestBase& Test, const UUmHudTheme& Theme, const TCHAR* What) {
  for (const S08HudTokens::FColorToken& C : S08HudTokens::kColors) {
    FLinearColor Want = FLinearColor::FromSRGBColor(C.Srgb);
    Want.A = C.Alpha;
    const FLinearColor* Have = Theme.Colors.Find(C.Name);
    Test.TestTrue(FString::Printf(TEXT("%s: color %s present"), What, C.Name), Have != nullptr);
    if (Have) Test.TestTrue(FString::Printf(TEXT("%s: color %s value"), What, C.Name), Have->Equals(Want, 1e-5f));
  }
  for (const S08HudTokens::FTypeToken& T : S08HudTokens::kTypes) {
    const FSlateFontInfo* Have = Theme.Type.Find(T.Name);
    Test.TestTrue(FString::Printf(TEXT("%s: type %s present"), What, T.Name), Have != nullptr);
    if (Have) {
      Test.TestEqual(FString::Printf(TEXT("%s: type %s size"), What, T.Name), Have->Size, static_cast<float>(T.Su));
      Test.TestEqual(FString::Printf(TEXT("%s: type %s face"), What, T.Name), Have->TypefaceFontName, FName(T.Face));
    }
  }
  auto Scalars = [&](const TMap<FName, float>& Map, const S08HudTokens::FScalarToken* Begin, int32 Num, const TCHAR* Kind) {
    for (int32 I = 0; I < Num; ++I) {
      const float* Have = Map.Find(Begin[I].Name);
      Test.TestTrue(FString::Printf(TEXT("%s: %s %s present"), What, Kind, Begin[I].Name), Have != nullptr);
      if (Have) Test.TestEqual(FString::Printf(TEXT("%s: %s %s"), What, Kind, Begin[I].Name), *Have, Begin[I].Value);
    }
  };
  Scalars(Theme.Alphas, S08HudTokens::kAlphas, UE_ARRAY_COUNT(S08HudTokens::kAlphas), TEXT("alpha"));
  Scalars(Theme.Space, S08HudTokens::kSpace, UE_ARRAY_COUNT(S08HudTokens::kSpace), TEXT("space"));
  Scalars(Theme.Radius, S08HudTokens::kRadius, UE_ARRAY_COUNT(S08HudTokens::kRadius), TEXT("radius"));
  Scalars(Theme.MotionMs, S08HudTokens::kMotionMs, UE_ARRAY_COUNT(S08HudTokens::kMotionMs), TEXT("motion"));
  Test.TestEqual(FString::Printf(TEXT("%s: 29 skins"), What), Theme.Skins.Num(), S08HudTokens::kNumSkins);
  for (int32 I = 0; I < S08HudTokens::kNumSkins; ++I) {
    const S08HudTokens::FSkinToken& S = S08HudTokens::kSkins[I];
    const FSlateBrush* Brush = Theme.Skins.Find(S.Name);
    Test.TestTrue(FString::Printf(TEXT("%s: skin %s present"), What, S.Name), Brush != nullptr);
    if (!Brush) continue;
    Test.TestTrue(FString::Printf(TEXT("%s: skin %s is a rounded box"), What, S.Name),
                  Brush->DrawAs == ESlateBrushDrawType::RoundedBox);
    FLinearColor Fill = FLinearColor::FromSRGBColor(S.Fill);
    Fill.A = S.FillAlpha;
    Test.TestTrue(FString::Printf(TEXT("%s: skin %s fill"), What, S.Name), Brush->TintColor.GetSpecifiedColor().Equals(Fill, 1e-5f));
    Test.TestEqual(FString::Printf(TEXT("%s: skin %s edge"), What, S.Name), static_cast<float>(Brush->OutlineSettings.Width), S.EdgeSu);
    Test.TestTrue(FString::Printf(TEXT("%s: skin %s rounding"), What, S.Name),
                  Brush->OutlineSettings.RoundingType ==
                      (S.bHalfHeight ? ESlateBrushRoundingType::HalfHeightRadius : ESlateBrushRoundingType::FixedRadius));
  }
  Test.TestEqual(FString::Printf(TEXT("%s: tokens sha"), What), Theme.TokensJsonSha256, FString(S08HudTokens::kTokensJsonSha256));
  const FSlateFontInfo Tag = Theme.Font(TEXT("type.tag"));
  Test.TestTrue(FString::Printf(TEXT("%s: type.tag resolves to a font"), What), Tag.HasValidFont());
  Test.TestEqual(FString::Printf(TEXT("%s: type.tag Bold Condensed 14"), What), Tag.TypefaceFontName, FName(TEXT("BoldCondensed")));
}
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudThemeLoadTest,
    "Unmatched.S08.Hud.Theme.Load the theme asset loads and carries every token of the JSON with the header values",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudThemeLoadTest::RunTest(const FString&) {
  const double Start = FPlatformTime::Seconds();
  bool bFallback = true;
  const UUmHudTheme* Theme = UUmHudTheme::LoadOrFallback(UUmHudTheme::AssetPath, bFallback);
  AddInfo(FString::Printf(TEXT("DA_UmHudTheme load %.2f ms (budget 5 ms once)"), (FPlatformTime::Seconds() - Start) * 1000.0));
  TestFalse(TEXT("the asset exists (no header fallback)"), bFallback);
  if (!Theme || bFallback) return false;
  TestFalse(TEXT("not flagged as fallback"), Theme->IsHeaderFallback());

  FString Path;
  const TSharedPtr<FJsonObject> Doc = LoadThemeTokensJson(Path);
  if (!Doc.IsValid()) {
    AddError(Path + TEXT(" not readable"));
    return false;
  }
  // every token of the JSON is in the asset maps
  for (const TPair<FString, TSharedPtr<FJsonValue>>& P : Doc->GetObjectField(TEXT("colors"))->Values) {
    TestTrue(FString::Printf(TEXT("JSON color %s in Colors"), *P.Key), Theme->Colors.Contains(FName(*P.Key)));
  }
  for (const TPair<FString, TSharedPtr<FJsonValue>>& P : Doc->GetObjectField(TEXT("typography"))->Values) {
    if (P.Key.StartsWith(TEXT("type."))) {
      TestTrue(FString::Printf(TEXT("JSON type %s in Type"), *P.Key), Theme->Type.Contains(FName(*P.Key)));
    }
  }
  const TPair<const TCHAR*, const TMap<FName, float>*> Groups[] = {
      {TEXT("spacing"), &Theme->Space}, {TEXT("radii"), &Theme->Radius}, {TEXT("motion"), &Theme->MotionMs},
      {TEXT("opacity"), &Theme->Alphas}};
  for (const auto& G : Groups) {
    for (const TPair<FString, TSharedPtr<FJsonValue>>& P : Doc->GetObjectField(G.Key)->Values) {
      TestTrue(FString::Printf(TEXT("JSON %s %s in the theme"), G.Key, *P.Key), G.Value->Contains(FName(*P.Key)));
    }
  }
  for (const TPair<FString, TSharedPtr<FJsonValue>>& P : Doc->GetObjectField(TEXT("skins"))->Values) {
    TestTrue(FString::Printf(TEXT("JSON skin %s in Skins"), *P.Key), Theme->Skins.Contains(FName(*P.Key)));
  }
  CheckHeaderValues(*this, *Theme, TEXT("asset"));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudThemeFallbackTest,
    "Unmatched.S08.Hud.Theme.Fallback without the asset the theme takes the header values and warns once",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudThemeFallbackTest::RunTest(const FString&) {
  AddExpectedMessagePlain(TEXT("UMHUDTHEME asset /Game/S08/UI/Theme/DA_UmHudThemeMissing.DA_UmHudThemeMissing not found"),
                          ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 1);
  bool bFallback = false;
  const UUmHudTheme* Theme =
      UUmHudTheme::LoadOrFallback(TEXT("/Game/S08/UI/Theme/DA_UmHudThemeMissing.DA_UmHudThemeMissing"), bFallback);
  TestTrue(TEXT("fallback used"), bFallback);
  if (!Theme) return false;
  TestTrue(TEXT("flagged as fallback"), Theme->IsHeaderFallback());
  CheckHeaderValues(*this, *Theme, TEXT("fallback"));
  // the accessors (what BuildDefaultTree of the UUm* bases calls)
  FLinearColor PanelBg = FLinearColor::FromSRGBColor(S08HudTokens::Color_CardNavy);
  PanelBg.A = S08HudTokens::Alpha_PanelBg;
  TestTrue(TEXT("panel.bg = card.navy at 0.92"), Theme->Color(TEXT("panel.bg")).Equals(PanelBg, 1e-5f));
  TestEqual(TEXT("radius.m"), Theme->RadiusSu(TEXT("radius.m")), S08HudTokens::Radius_M);
  TestEqual(TEXT("hover.ms"), Theme->Ms(TEXT("hover.ms")), S08HudTokens::MotionMs_Hover);
  TestEqual(TEXT("state.disabled.opacity"), Theme->Alpha(TEXT("state.disabled.opacity")), S08HudTokens::Alpha_StateDisabledOpacity);
  TestNotNull(TEXT("skin btn.primary.normal"), Theme->Skin(TEXT("btn.primary.normal")));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS

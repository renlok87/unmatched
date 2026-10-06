// VS-1 HB-03 automation test of S08HudTokens.generated.h (tools/s08/hud_contract/hud_tokens_codegen.py, ВР-77):
// three sample tokens read straight from docs/unreal/contracts/hud/hud-style-tokens.json (a direct colour, an alias
// with its own alpha, a type size) equal the generated constants, and every colour token of the JSON is in kColors.
//   node tools/s08/run-ue-tests.cjs Unmatched.S08.Hud.Tokens <log>
#if WITH_AUTOMATION_TESTS

#include "../S08HudTokens.generated.h"
#include "Dom/JsonObject.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace {
TSharedPtr<FJsonObject> LoadTokensJson(FString& OutPath) {
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

/** Hex of a colour token, following "alias" (the test's own resolution, independent of the generator). */
FString ResolveHex(const TSharedPtr<FJsonObject>& Colors, const FString& Name, int32 Depth = 0) {
  const TSharedPtr<FJsonObject>* Tok = nullptr;
  if (Depth > 8 || !Colors->TryGetObjectField(Name, Tok)) return FString();
  FString Alias;
  if ((*Tok)->TryGetStringField(TEXT("alias"), Alias)) return ResolveHex(Colors, Alias, Depth + 1);
  return (*Tok)->GetStringField(TEXT("hex"));
}
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudTokensHeaderTest,
    "Unmatched.S08.Hud.Tokens.Header three sample tokens of the generated header equal the tokens JSON",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudTokensHeaderTest::RunTest(const FString&) {
  FString Path;
  const TSharedPtr<FJsonObject> Doc = LoadTokensJson(Path);
  if (!Doc.IsValid()) {
    AddError(Path + TEXT(" not readable"));
    return false;
  }
  const TSharedPtr<FJsonObject> Colors = Doc->GetObjectField(TEXT("colors"));
  const TSharedPtr<FJsonObject> Typography = Doc->GetObjectField(TEXT("typography"));

  // 1) a direct colour: turn.flash.yellow (accepted by the user, AB-5)
  TestEqual(TEXT("turn.flash.yellow bytes"), S08HudTokens::Color_TurnFlashYellow,
            FColor::FromHex(ResolveHex(Colors, TEXT("turn.flash.yellow"))));

  // 2) an alias with its own alpha: panel.edge = card.cream at 0.45 (ВР-64)
  const TSharedPtr<FJsonObject> Edge = Colors->GetObjectField(TEXT("panel.edge"));
  TestEqual(TEXT("panel.edge is an alias of card.cream"), Edge->GetStringField(TEXT("alias")), FString(TEXT("card.cream")));
  TestEqual(TEXT("panel.edge bytes = card.cream"), S08HudTokens::Color_PanelEdge,
            FColor::FromHex(ResolveHex(Colors, TEXT("panel.edge"))));
  TestEqual(TEXT("panel.edge alpha"), S08HudTokens::Alpha_PanelEdge, static_cast<float>(Edge->GetNumberField(TEXT("alpha"))));
  // ВР-61: tag.background -> card.navy (the Slate rollback keeps #161A28 in S08ArtHudStyle.h, not here)
  TestEqual(TEXT("tag.background = card.navy"), S08HudTokens::Color_TagBackground, S08HudTokens::Color_CardNavy);

  // 3) a type size: type.damage 24 su (ВР-63)
  TestEqual(TEXT("type.damage su"), S08HudTokens::TypeSu_Damage,
            static_cast<int32>(Typography->GetObjectField(TEXT("type.damage"))->GetNumberField(TEXT("su"))));

  // every colour token of the JSON is in the generated table, with the resolved bytes
  TMap<FString, FColor> Table;
  for (const S08HudTokens::FColorToken& T : S08HudTokens::kColors) Table.Add(T.Name, T.Srgb);
  TestEqual(TEXT("kColors has every colour token"), Table.Num(), Colors->Values.Num());
  for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Colors->Values) {
    const FColor* Bytes = Table.Find(Pair.Key);
    TestTrue(FString::Printf(TEXT("%s in kColors"), *Pair.Key), Bytes != nullptr);
    if (Bytes) TestEqual(FString::Printf(TEXT("%s bytes"), *Pair.Key), *Bytes, FColor::FromHex(ResolveHex(Colors, Pair.Key)));
  }
  TestEqual(TEXT("sha256 field is 64 hex"), FCString::Strlen(S08HudTokens::kTokensJsonSha256), 64);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS

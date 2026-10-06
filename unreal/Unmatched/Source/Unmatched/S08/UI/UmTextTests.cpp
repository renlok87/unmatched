// VS-1 HB-05 automation test of UI/UmText.h: every key of the four HUD string tables (the sources in
// docs/unreal/contracts/hud: st-hud.csv, st-screens.csv, st-ms.csv, why-reasons.json) resolves in RU and in EN to the
// source text; "Рука 5/7" / "Hand 5/7" through FText::Format; RU plural one/few/many on 1, 2, 5, 21; a held FText
// follows the language switch without being fetched again; a missing key shows "?<key>".
// In the editor the game localization is shown through the game-localization preview (the packaged game reads
// [Internationalization] Culture=ru of DefaultGame.ini); the test restores the editor culture state at the end.
//   node tools/s08/run-ue-tests.cjs Unmatched.S08.Hud.Strings <log>
#if WITH_AUTOMATION_TESTS

#include "UmText.h"
#include "Dom/JsonObject.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/TextLocalizationManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/Csv/CsvParser.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace {
struct FExpectedString {
  EUmTable Table;
  FString Key;
  FString En;
  FString Ru;
};

FString ContractPath(const TCHAR* File) {
  return FPaths::ConvertRelativePathToFull(
      FPaths::Combine(FPaths::ProjectDir(), TEXT("../../docs/unreal/contracts/hud"), File));
}

bool LoadCsv(FAutomationTestBase& Test, EUmTable Table, const TCHAR* File, TArray<FExpectedString>& Out) {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *ContractPath(File))) {
    Test.AddError(FString::Printf(TEXT("%s not readable"), *ContractPath(File)));
    return false;
  }
  const FCsvParser Parser(Text);
  const FCsvParser::FRows& Rows = Parser.GetRows();
  if (Rows.Num() < 2 || Rows[0].Num() < 3) {
    Test.AddError(FString::Printf(TEXT("%s: no rows"), File));
    return false;
  }
  for (int32 R = 1; R < Rows.Num(); ++R) {
    if (Rows[R].Num() < 3 || FCString::Strlen(Rows[R][0]) == 0) continue;
    Out.Add({Table, Rows[R][0], Rows[R][1], Rows[R][2]});
  }
  return true;
}

bool LoadWhy(FAutomationTestBase& Test, TArray<FExpectedString>& Out) {
  FString Text;
  TSharedPtr<FJsonObject> Doc;
  const TArray<TSharedPtr<FJsonValue>>* Reasons = nullptr;
  if (!FFileHelper::LoadFileToString(Text, *ContractPath(TEXT("why-reasons.json"))) ||
      !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Doc) || !Doc.IsValid() ||
      !Doc->TryGetArrayField(TEXT("reasons"), Reasons)) {
    Test.AddError(TEXT("why-reasons.json not readable"));
    return false;
  }
  for (const TSharedPtr<FJsonValue>& V : *Reasons) {
    const TSharedPtr<FJsonObject> R = V->AsObject();
    Out.Add({EUmTable::Why, R->GetStringField(TEXT("key")), R->GetStringField(TEXT("en")), R->GetStringField(TEXT("ru"))});
  }
  return true;
}

/** UI language + game text in Culture (editor: the game localization preview), loaded synchronously. */
void UseCulture(const FString& Culture) {
  FInternationalization::Get().SetCurrentLanguageAndLocale(Culture);
  FTextLocalizationManager::Get().EnableGameLocalizationPreview(Culture);
  FTextLocalizationManager::Get().WaitForAsyncTasks();
}
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmTextKeysTest,
    "Unmatched.S08.Hud.Strings.Keys every key of the four HUD string tables resolves in RU and EN",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmTextKeysTest::RunTest(const FString&) {
  TestTrue(TEXT("the four string table assets load"), UmText::Preload());
  TArray<FExpectedString> Expected;
  if (!LoadCsv(*this, EUmTable::Hud, TEXT("st-hud.csv"), Expected) ||
      !LoadCsv(*this, EUmTable::Screens, TEXT("st-screens.csv"), Expected) ||
      !LoadCsv(*this, EUmTable::Ms, TEXT("st-ms.csv"), Expected) || !LoadWhy(*this, Expected)) {
    return false;
  }
  // every source key is in its table, and the tables hold nothing else
  int32 NumTableKeys = 0;
  for (int32 T = 0; T < 4; ++T) NumTableKeys += UmText::Keys(static_cast<EUmTable>(T)).Num();
  TestEqual(TEXT("table keys = source keys"), NumTableKeys, Expected.Num());
  for (const FExpectedString& E : Expected) {
    TestTrue(FString::Printf(TEXT("%s in %s"), *E.Key, *UmText::TableId(E.Table).ToString()), UmText::Has(E.Table, E.Key));
  }

  FInternationalization::FCultureStateSnapshot Snapshot;
  FInternationalization::Get().BackupCultureState(Snapshot);

  UseCulture(TEXT("en"));
  const FText Held = UmText::Get(EUmTable::Hud, TEXT("hud.banner.own_turn"));  // kept across the switch
  TestEqual(TEXT("EN held text"), Held.ToString(), FString(TEXT("YOUR TURN")));
  int32 EnOk = 0;
  for (const FExpectedString& E : Expected) {
    const FString Have = UmText::Get(E.Table, E.Key).ToString();
    if (Have == E.En) {
      ++EnOk;
    } else {
      AddError(FString::Printf(TEXT("EN %s: '%s' != '%s'"), *E.Key, *Have, *E.En));
    }
  }
  FFormatNamedArguments Hand;
  Hand.Add(TEXT("n"), 5);
  Hand.Add(TEXT("max"), 7);
  TestEqual(TEXT("EN Hand 5/7"), UmText::Format(EUmTable::Hud, TEXT("hud.hand.count"), Hand).ToString(), FString(TEXT("Hand 5/7")));
  const TPair<int32, const TCHAR*> EnDeck[] = {{1, TEXT("Deck: 1 card")}, {2, TEXT("Deck: 2 cards")}, {21, TEXT("Deck: 21 cards")}};
  for (const auto& P : EnDeck) {
    FFormatNamedArguments A;
    A.Add(TEXT("n"), P.Key);
    TestEqual(FString::Printf(TEXT("EN plural %d"), P.Key), UmText::Format(EUmTable::Screens, TEXT("screens.room.deck.count"), A).ToString(),
              FString(P.Value));
  }

  UseCulture(TEXT("ru"));
  TestEqual(TEXT("the held FText follows the switch to RU (same object, no new Get)"), Held.ToString(), FString(TEXT("ВАШ ХОД")));
  int32 RuOk = 0;
  for (const FExpectedString& E : Expected) {
    const FString Have = UmText::Get(E.Table, E.Key).ToString();
    if (Have == E.Ru) {
      ++RuOk;
    } else {
      AddError(FString::Printf(TEXT("RU %s: '%s' != '%s'"), *E.Key, *Have, *E.Ru));
    }
  }
  TestEqual(TEXT("RU Рука 5/7"), UmText::Format(EUmTable::Hud, TEXT("hud.hand.count"), Hand).ToString(), FString(TEXT("Рука 5/7")));
  const TPair<int32, const TCHAR*> RuDeck[] = {
      {1, TEXT("Колода: 1 карта")}, {2, TEXT("Колода: 2 карты")}, {5, TEXT("Колода: 5 карт")}, {21, TEXT("Колода: 21 карта")}};
  for (const auto& P : RuDeck) {
    FFormatNamedArguments A;
    A.Add(TEXT("n"), P.Key);
    TestEqual(FString::Printf(TEXT("RU plural %d"), P.Key), UmText::Format(EUmTable::Screens, TEXT("screens.room.deck.count"), A).ToString(),
              FString(P.Value));
  }
  const TPair<int32, const TCHAR*> RuFighters[] = {{1, TEXT("Подтвердить: 1 боец (Enter)")}, {2, TEXT("Подтвердить: 2 бойца (Enter)")},
                                                   {5, TEXT("Подтвердить: 5 бойцов (Enter)")}, {21, TEXT("Подтвердить: 21 боец (Enter)")}};
  for (const auto& P : RuFighters) {
    FFormatNamedArguments A;
    A.Add(TEXT("n"), P.Key);
    TestEqual(FString::Printf(TEXT("RU fighters plural %d"), P.Key),
              UmText::Format(EUmTable::Ms, TEXT("ms.btn.confirm.noboost"), A).ToString(), FString(P.Value));
  }

  AddExpectedMessagePlain(TEXT("UMTEXT missing key 'hud.no.such.key'"), ELogVerbosity::Warning,
                          EAutomationExpectedMessageFlags::Contains, 1);
  TestEqual(TEXT("missing key is visible"), UmText::Get(EUmTable::Hud, TEXT("hud.no.such.key")).ToString(),
            FString(TEXT("?hud.no.such.key")));

  FTextLocalizationManager::Get().DisableGameLocalizationPreview();
  FTextLocalizationManager::Get().WaitForAsyncTasks();
  FInternationalization::Get().RestoreCultureState(Snapshot);
  FTextLocalizationManager::Get().WaitForAsyncTasks();

  AddInfo(FString::Printf(TEXT("keys %d: EN %d ok, RU %d ok"), Expected.Num(), EnOk, RuOk));
  TestEqual(TEXT("every key in EN"), EnOk, Expected.Num());
  TestEqual(TEXT("every key in RU"), RuOk, Expected.Num());
  return true;
}

#endif  // WITH_AUTOMATION_TESTS

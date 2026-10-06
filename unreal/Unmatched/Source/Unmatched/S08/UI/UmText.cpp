#include "UmText.h"

#include "Internationalization/Internationalization.h"
#include "Internationalization/StringTable.h"
#include "Internationalization/StringTableCore.h"
#include "Internationalization/StringTableRegistry.h"

DEFINE_LOG_CATEGORY_STATIC(LogUmText, Log, All);

namespace UmText {
namespace {
constexpr int32 NumTables = 4;
const TCHAR* const GPaths[NumTables] = {
    TEXT("/Game/UI/Localization/ST_Hud.ST_Hud"),
    TEXT("/Game/UI/Localization/ST_Screens.ST_Screens"),
    TEXT("/Game/UI/Localization/ST_Why.ST_Why"),
    TEXT("/Game/UI/Localization/ST_Ms.ST_Ms"),
};

int32 Index(EUmTable Table) { return FMath::Clamp(static_cast<int32>(Table), 0, NumTables - 1); }

/** The registered table; loads the asset once (UStringTable registers itself on load) and keeps it rooted. */
FStringTableConstPtr FindTable(EUmTable Table) {
  const FName Id = TableId(Table);
  FStringTableConstPtr Found = FStringTableRegistry::Get().FindStringTable(Id);
  if (!Found.IsValid()) {
    if (UStringTable* Asset = LoadObject<UStringTable>(nullptr, GPaths[Index(Table)], nullptr, LOAD_NoWarn | LOAD_Quiet)) {
      Asset->AddToRoot();
      Found = FStringTableRegistry::Get().FindStringTable(Id);
    }
  }
  return Found;
}

/** Per-table text cache: a widget asking again for the same key gets the same FText (no allocation); the FText of a
 *  string table entry re-resolves its display string itself after a language switch. */
TMap<FString, FText>& Cache(EUmTable Table) {
  static TMap<FString, FText> Caches[NumTables];
  return Caches[Index(Table)];
}
}  // namespace

FName TableId(EUmTable Table) { return FName(GPaths[Index(Table)]); }

bool Preload() {
  bool bAll = true;
  for (int32 I = 0; I < NumTables; ++I) {
    if (!FindTable(static_cast<EUmTable>(I)).IsValid()) {
      UE_LOG(LogUmText, Warning, TEXT("UMTEXT table %s not found"), GPaths[I]);
      bAll = false;
    }
  }
  return bAll;
}

bool Has(EUmTable Table, const FString& Key) {
  const FStringTableConstPtr Found = FindTable(Table);
  return Found.IsValid() && Found->FindEntry(Key).IsValid();
}

FText Get(EUmTable Table, const FString& Key) {
  TMap<FString, FText>& Texts = Cache(Table);
  if (const FText* Hit = Texts.Find(Key)) return *Hit;
  if (!Has(Table, Key)) {
    UE_LOG(LogUmText, Warning, TEXT("UMTEXT missing key '%s' in %s"), *Key, *TableId(Table).ToString());
    const FText Missing = FText::AsCultureInvariant(TEXT("?") + Key);  // visible defect, never silent English
    Texts.Add(Key, Missing);
    return Missing;
  }
  const FText Text = FText::FromStringTable(TableId(Table), Key);
  Texts.Add(Key, Text);
  return Text;
}

FText Format(EUmTable Table, const FString& Key, const FFormatNamedArguments& Args) {
  return FText::Format(FTextFormat(Get(Table, Key)), Args);
}

bool SetUiLanguage(const FString& Culture) { return FInternationalization::Get().SetCurrentCulture(Culture); }

TArray<FString> Keys(EUmTable Table) {
  TArray<FString> Out;
  if (const FStringTableConstPtr Found = FindTable(Table)) {
    Found->EnumerateSourceStrings([&Out](const FString& Key, const FString&) {
      Out.Add(Key);
      return true;
    });
  }
  return Out;
}
}  // namespace UmText

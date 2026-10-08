#include "UmText.h"

#include "Internationalization/Internationalization.h"
#include "Internationalization/StringTable.h"
#include "Internationalization/StringTableCore.h"
#include "Internationalization/StringTableRegistry.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

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

/** -1 not read yet, 0 off, 1 on (VS-7 SC-26: -S08Lang=pseudo). */
int32& PseudoState() {
  static int32 State = -1;
  return State;
}

void ClearCaches() {
  for (int32 I = 0; I < NumTables; ++I) Cache(static_cast<EUmTable>(I)).Reset();
}
}  // namespace

bool IsPseudo() {
  int32& State = PseudoState();
  if (State < 0) {
    FString Lang;
    State = FParse::Value(FCommandLine::Get(), TEXT("S08Lang="), Lang) && Lang.TrimStartAndEnd().Equals(TEXT("pseudo"), ESearchCase::IgnoreCase) ? 1 : 0;
  }
  return State == 1;
}

FString Pseudo(const FString& Text) {
  // ВР-VS5-SC26-03 in the engine (ВР-VS7-45): "~" is about as wide as an average letter of Roboto, the brackets add the rest
  const int32 K = FMath::Max(1, FMath::CeilToInt(0.3f * Text.Len()));
  return TEXT("[") + Text + FString::ChrN(K, TEXT('~')) + TEXT("]");
}

void SetPseudoForTest(bool bOn) {
  PseudoState() = bOn ? 1 : 0;
  ClearCaches();
}

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
  FText Text = FText::FromStringTable(TableId(Table), Key);
  if (IsPseudo()) Text = FText::AsCultureInvariant(Pseudo(Text.ToString()));  // a check flag: frozen at the start culture
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

#include "S08ArtHudText.h"

#include "Internationalization/StringTable.h"
#include "Internationalization/StringTableCore.h"
#include "Internationalization/StringTableRegistry.h"
#include "Misc/Paths.h"

namespace S08ArtHudText {

const FName TableId(TEXT("S08ArtHud"));
const TCHAR* const CsvPath = TEXT("Localization/StringTables/S08ArtHud.csv");

namespace {
FStringTableConstPtr FindTable() { return FStringTableRegistry::Get().FindStringTable(TableId); }

FNumberFormattingOptions NoGrouping() {
  FNumberFormattingOptions Options;
  Options.UseGrouping = false;
  return Options;
}

FText Number(int32 Value) {
  static const FNumberFormattingOptions Options = NoGrouping();
  return FText::AsNumber(Value, &Options);
}

FText FormatKey(const FString& Key, const FFormatNamedArguments& Args) {
  return FText::Format(FTextFormat(Get(Key)), Args);
}
}  // namespace

bool EnsureTable() {
  static bool bRequested = false;
  if (!bRequested) {
    bRequested = true;
    if (!FindTable().IsValid()) {
      // LOCTABLE_FROMFILE_GAME: the gatherer reads this macro and the CSV.
      LOCTABLE_FROMFILE_GAME("S08ArtHud", "S08ArtHud", "Localization/StringTables/S08ArtHud.csv");
    }
  }
  return NumEntries() > 0;
}

int32 NumEntries() {
  const FStringTableConstPtr Table = FindTable();
  if (!Table.IsValid()) return 0;
  int32 Count = 0;
  Table->EnumerateSourceStrings([&Count](const FString&, const FString&) {
    ++Count;
    return true;
  });
  return Count;
}

const TArray<FString>& RequiredKeys() {
  static const TArray<FString> Keys = {
      TEXT("plate.team.own"),         TEXT("plate.team.enemy"),      TEXT("plate.hp"),
      TEXT("plate.status.separator"), TEXT("plate.status.hero"),     TEXT("plate.status.sidekick"),
      TEXT("plate.status.melee"),     TEXT("plate.status.ranged"),   TEXT("plate.status.attacker"),
      TEXT("plate.status.target"),    TEXT("label.compact"),         TEXT("label.hp"),
      TEXT("damage.number"),
  };
  return Keys;
}

TArray<FString> MissingKeys() {
  EnsureTable();
  TArray<FString> Out;
  for (const FString& Key : RequiredKeys()) {
    if (!Has(Key)) Out.Add(Key);
  }
  return Out;
}

bool Has(const FString& Key) {
  EnsureTable();
  const FStringTableConstPtr Table = FindTable();
  FString Source;
  return Table.IsValid() && Table->GetSourceString(Key, Source);
}

FText Get(const FString& Key) {
  if (!Has(Key)) return FText::FromString(Key);
  return FText::FromStringTable(TableId, Key);
}

FText PlateHp(int32 Health, int32 MaxHealth) {
  FFormatNamedArguments Args;
  Args.Add(TEXT("Hp"), Number(Health));
  Args.Add(TEXT("Max"), Number(MaxHealth));
  return FormatKey(TEXT("plate.hp"), Args);
}

FText PlateTeam(bool bOwn) { return Get(bOwn ? TEXT("plate.team.own") : TEXT("plate.team.enemy")); }

FText PlateStatuses(const TArray<FString>& Codes) {
  TArray<FText> Parts;
  for (const FString& Code : Codes) {
    const FString Key = TEXT("plate.status.") + Code.ToLower();
    Parts.Add(Has(Key) ? Get(Key) : FText::FromString(Code));
  }
  return FText::Join(Get(TEXT("plate.status.separator")), Parts);
}

FS08PlateTexts PlateTexts(const FString& Name, int32 Health, int32 MaxHealth, bool bOwn,
                          const TArray<FString>& StatusCodes) {
  FS08PlateTexts Out;
  Out.Name = FText::FromString(Name);  // fighter label: server data, not UI text
  Out.Team = PlateTeam(bOwn);
  Out.Hp = PlateHp(Health, MaxHealth);
  Out.Statuses = PlateStatuses(StatusCodes);
  Out.HpFraction = MaxHealth > 0 ? FMath::Clamp(static_cast<float>(Health) / MaxHealth, 0.0f, 1.0f) : 0.0f;
  Out.bOwn = bOwn;
  return Out;
}

FText CompactLabel(const FString& Name, int32 Health, int32 MaxHealth) {
  FFormatNamedArguments Args;
  Args.Add(TEXT("Name"), FText::FromString(Name));
  Args.Add(TEXT("Hp"), Number(Health));
  Args.Add(TEXT("Max"), Number(MaxHealth));
  return FormatKey(TEXT("label.compact"), Args);
}

FText HpLabel(int32 Health, int32 MaxHealth) {
  FFormatNamedArguments Args;
  Args.Add(TEXT("Hp"), Number(Health));
  Args.Add(TEXT("Max"), Number(MaxHealth));
  return FormatKey(TEXT("label.hp"), Args);
}

FText DamageNumber(int32 Amount) {
  FFormatNamedArguments Args;
  Args.Add(TEXT("Amount"), Number(Amount));
  return FormatKey(TEXT("damage.number"), Args);
}

}  // namespace S08ArtHudText

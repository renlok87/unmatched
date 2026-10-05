// AU-S4: the game's sound bank - see S08AudioBank.h.
#include "S08AudioBank.h"

namespace {
struct FBankRow {
  const TCHAR* Id;
  const TCHAR* Paths;
};

const TArray<FBankRow>& Rows() {
#define S08_AUDIO_BANK(Id, Paths) {Id, Paths},
  static const TArray<FBankRow> Table = {
#include "S08AudioBankData.inl"
  };
#undef S08_AUDIO_BANK
  return Table;
}

const TMap<FString, TArray<FString>>& Bank() {
  static const TMap<FString, TArray<FString>> Map = [] {
    TMap<FString, TArray<FString>> Out;
    for (const FBankRow& Row : Rows()) {
      TArray<FString> Paths;
      FString(Row.Paths).ParseIntoArray(Paths, TEXT("|"));
      Out.Add(Row.Id, MoveTemp(Paths));
    }
    return Out;
  }();
  return Map;
}
}  // namespace

const TArray<FString>* S08AudioBank::Find(const FString& Id) { return Bank().Find(Id); }

int32 S08AudioBank::Num() { return Bank().Num(); }

const TArray<FS08VoLine>& S08AudioBank::VoLines() {
#define S08_VO_LINE(Id, Fighter, Event, En, Ru, Path) {Id, Fighter, Event, En, Ru, Path},
  static const TArray<FS08VoLine> Lines = {
#include "S08VoLinesData.inl"
  };
#undef S08_VO_LINE
  return Lines;
}

const FS08VoLine* S08AudioBank::FindVoLine(const FString& LineId) {
  return VoLines().FindByPredicate([&LineId](const FS08VoLine& L) { return L.Id == LineId; });
}

const FS08VoLine* S08AudioBank::FindVoLineByPath(const FString& SoftPath) {
  return VoLines().FindByPredicate([&SoftPath](const FS08VoLine& L) { return L.Path == SoftPath; });
}

FString S08AudioBank::CharacterKey(const FString& Name) {
  if (Name.Contains(TEXT("arthur"), ESearchCase::IgnoreCase)) return TEXT("ARTHUR");
  if (Name.Contains(TEXT("merlin"), ESearchCase::IgnoreCase)) return TEXT("MERLIN");
  if (Name.Contains(TEXT("medusa"), ESearchCase::IgnoreCase)) return TEXT("MEDUSA");
  if (Name.Contains(TEXT("harp"), ESearchCase::IgnoreCase)) return TEXT("HARPY");
  return FString();
}

FString S08AudioBank::HitType(const FString& Key) {
  if (Key == TEXT("ARTHUR")) return TEXT("BLADE");
  if (Key == TEXT("HARPY")) return TEXT("CLAW");
  if (Key == TEXT("MEDUSA")) return TEXT("ARROW");
  if (Key == TEXT("MERLIN")) return TEXT("MAGIC");
  return TEXT("BLUNT");
}

FString FS08SoundBag::Pick(const FString& Key, const TArray<FString>& Variants, FRandomStream& Rng) {
  const int32 N = Variants.Num();
  if (N == 0) return FString();
  if (N == 1) return Variants[0];
  FBag& Bag = Bags.FindOrAdd(Key);
  if (Bag.Size != N || Bag.Next >= Bag.Order.Num()) {
    const int32 Last = Bag.Size == N ? Bag.Last : INDEX_NONE;
    Bag.Size = N;
    Bag.Order.SetNum(N);
    for (int32 I = 0; I < N; ++I) Bag.Order[I] = I;
    for (int32 I = N - 1; I > 0; --I) Bag.Order.Swap(I, Rng.RandRange(0, I));
    if (Bag.Order[0] == Last) Bag.Order.Swap(0, Rng.RandRange(1, N - 1));  // no repeat across the reshuffle
    Bag.Next = 0;
  }
  Bag.Last = Bag.Order[Bag.Next++];
  return Variants[Bag.Last];
}

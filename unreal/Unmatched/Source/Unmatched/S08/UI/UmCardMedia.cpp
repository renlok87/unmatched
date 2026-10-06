#include "UmCardMedia.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/Texture2D.h"
#include "Internationalization/Culture.h"
#include "Internationalization/Internationalization.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

DEFINE_LOG_CATEGORY_STATIC(LogUmCardMedia, Log, All);

namespace UmCardMedia {
namespace {
TArray<FUmCardMediaEntry> GRegistry;
bool GLoaded = false;

bool ReadPair(const TSharedPtr<FJsonObject>& O, const TCHAR* Field, double& OutA, double& OutB) {
  const TArray<TSharedPtr<FJsonValue>>* Arr = nullptr;
  if (!O->TryGetArrayField(Field, Arr) || !Arr || Arr->Num() != 2) return false;
  return (*Arr)[0]->TryGetNumber(OutA) && (*Arr)[1]->TryGetNumber(OutB);
}

bool IsPowerOfTwo(int32 V) { return V > 0 && (V & (V - 1)) == 0; }

FString Underscored(const FString& Slug) { return Slug.Replace(TEXT("-"), TEXT("_")); }
}  // namespace

FString RegistryPath() { return FPaths::Combine(FPaths::ProjectConfigDir(), ConfigSubdir, FileName); }

bool Parse(const FString& Json, TArray<FUmCardMediaEntry>& Out, TArray<FString>& Errors) {
  Out.Reset();
  TSharedPtr<FJsonObject> Root;
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
  if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid()) {
    Errors.Add(TEXT("not a JSON object"));
    return false;
  }
  FString SchemaValue;
  if (!Root->TryGetStringField(TEXT("schema"), SchemaValue) || SchemaValue != Schema) {
    Errors.Add(FString::Printf(TEXT("schema '%s', expected '%s'"), *SchemaValue, Schema));
    return false;
  }
  const TArray<TSharedPtr<FJsonValue>>* Entries = nullptr;
  if (!Root->TryGetArrayField(TEXT("entries"), Entries) || !Entries) {
    Errors.Add(TEXT("no entries array"));
    return false;
  }
  TSet<FString> Seen;
  for (const TSharedPtr<FJsonValue>& V : *Entries) {
    const TSharedPtr<FJsonObject>* OPtr = nullptr;
    if (!V.IsValid() || !V->TryGetObject(OPtr) || !OPtr) {
      Errors.Add(TEXT("entry is not an object"));
      continue;
    }
    const TSharedPtr<FJsonObject>& O = *OPtr;
    FUmCardMediaEntry E;
    O->TryGetStringField(TEXT("key"), E.Key);
    O->TryGetStringField(TEXT("kind"), E.Kind);
    O->TryGetStringField(TEXT("lang"), E.Lang);
    O->TryGetStringField(TEXT("object"), E.ObjectPath);
    O->TryGetStringField(TEXT("sha256"), E.Sha256);
    double Sx = 0, Sy = 0, Px = 0, Py = 0, Ux = 0, Uy = 0;
    const bool bSizes = ReadPair(O, TEXT("src"), Sx, Sy) && ReadPair(O, TEXT("pad"), Px, Py) && ReadPair(O, TEXT("uv"), Ux, Uy);
    E.Src = FIntPoint(FMath::RoundToInt(Sx), FMath::RoundToInt(Sy));
    E.Pad = FIntPoint(FMath::RoundToInt(Px), FMath::RoundToInt(Py));
    E.Uv = FVector2D(Ux, Uy);
    const FString Id = E.Key + (E.Lang.IsEmpty() ? FString() : TEXT(".") + E.Lang);
    if (E.Key.IsEmpty() || !(E.Kind == TEXT("card") || E.Kind == TEXT("back") || E.Kind == TEXT("portrait"))) {
      Errors.Add(FString::Printf(TEXT("%s: key / kind '%s' invalid"), *Id, *E.Kind));
      continue;
    }
    if ((E.Kind == TEXT("card")) != (E.Lang == TEXT("ru") || E.Lang == TEXT("en"))) {
      Errors.Add(FString::Printf(TEXT("%s: lang '%s' (cards ru|en, others none)"), *Id, *E.Lang));
      continue;
    }
    if (!E.ObjectPath.StartsWith(TEXT("/Game/S08/UI/")) || !E.ObjectPath.Contains(TEXT("."))) {
      Errors.Add(FString::Printf(TEXT("%s: object path '%s' is not a cooked /Game/S08/UI object path"), *Id, *E.ObjectPath));
      continue;
    }
    if (!bSizes || E.Src.X <= 0 || E.Src.Y <= 0 || !IsPowerOfTwo(E.Pad.X) || !IsPowerOfTwo(E.Pad.Y) ||
        E.Pad.X < E.Src.X || E.Pad.Y < E.Src.Y ||
        !FMath::IsNearlyEqual(E.Uv.X, static_cast<double>(E.Src.X) / E.Pad.X, 1.0e-5) ||
        !FMath::IsNearlyEqual(E.Uv.Y, static_cast<double>(E.Src.Y) / E.Pad.Y, 1.0e-5)) {
      Errors.Add(FString::Printf(TEXT("%s: src / pad / uv inconsistent"), *Id));
      continue;
    }
    if (E.Kind == TEXT("portrait")) {
      const TArray<TSharedPtr<FJsonValue>>* Disc = nullptr;
      double Cx = 0, Cy = 0, D = 0;
      if (!O->TryGetArrayField(TEXT("disc"), Disc) || !Disc || Disc->Num() != 3 || !(*Disc)[0]->TryGetNumber(Cx) ||
          !(*Disc)[1]->TryGetNumber(Cy) || !(*Disc)[2]->TryGetNumber(D) || D <= 0.0 || D > 1.0 || Cx <= 0.0 ||
          Cx >= 1.0 || Cy <= 0.0 || Cy >= 1.0) {
        Errors.Add(FString::Printf(TEXT("%s: portrait disc [cx, cy, d] missing or out of (0, 1]"), *Id));
        continue;
      }
      E.bHasDisc = true;
      E.Disc = FVector(Cx, Cy, D);
    }
    if (Seen.Contains(Id)) {
      Errors.Add(FString::Printf(TEXT("%s: duplicate"), *Id));
      continue;
    }
    Seen.Add(Id);
    Out.Add(MoveTemp(E));
  }
  if (Errors.Num()) {
    Out.Reset();
    return false;
  }
  return true;
}

const TArray<FUmCardMediaEntry>& Registry() {
  if (GLoaded) return GRegistry;
  GLoaded = true;
  FString Text;
  TArray<FString> Errors;
  if (!FFileHelper::LoadFileToString(Text, *RegistryPath())) {
    UE_LOG(LogUmCardMedia, Warning, TEXT("CARDMEDIA registry missing: %s (card faces / backs / portraits fall back, INT-018)"),
           *RegistryPath());
  } else if (!Parse(Text, GRegistry, Errors)) {
    UE_LOG(LogUmCardMedia, Warning, TEXT("CARDMEDIA registry invalid (%s): %s"), *RegistryPath(),
           *FString::Join(Errors, TEXT("; ")));
  }
  return GRegistry;
}

void ResetForTest() {
  GRegistry.Reset();
  GLoaded = false;
}

const FUmCardMediaEntry* FindCard(const FString& HeroSlug, const FString& CardSlug, const FString& Lang) {
  const FString Key = HeroSlug + TEXT(":") + CardSlug;
  return Registry().FindByPredicate(
      [&](const FUmCardMediaEntry& E) { return E.Kind == TEXT("card") && E.Key == Key && E.Lang == Lang; });
}

const FUmCardMediaEntry* FindBack(const FString& HeroSlug) {
  const FString Key = TEXT("back:") + HeroSlug;
  return Registry().FindByPredicate([&](const FUmCardMediaEntry& E) { return E.Kind == TEXT("back") && E.Key == Key; });
}

const FUmCardMediaEntry* FindPortrait(const FString& HeroSlug, const FString& SidekickSlug) {
  const FString Key = TEXT("portrait:") + HeroSlug + (SidekickSlug.IsEmpty() ? FString() : TEXT(":") + SidekickSlug);
  return Registry().FindByPredicate(
      [&](const FUmCardMediaEntry& E) { return E.Kind == TEXT("portrait") && E.Key == Key; });
}

FString PreferredLang() {
  const FCultureRef Lang = FInternationalization::Get().GetCurrentLanguage();
  return Lang->GetTwoLetterISOLanguageName() == TEXT("en") ? FString(TEXT("en")) : FString(TEXT("ru"));
}

UTexture2D* LoadTexture(const FUmCardMediaEntry& Entry) {
  UTexture2D* T = LoadObject<UTexture2D>(nullptr, *Entry.ObjectPath);
  if (!T) {
    UE_LOG(LogUmCardMedia, Warning, TEXT("CARDMEDIA texture missing key=%s%s path=%s (fallback, INT-018)"), *Entry.Key,
           Entry.Lang.IsEmpty() ? TEXT("") : *(TEXT(".") + Entry.Lang), *Entry.ObjectPath);
  }
  return T;
}

FString CardAssetName(const FString& HeroSlug, const FString& CardSlug, const FString& Lang) {
  return FString::Printf(TEXT("T_Card_%s_%s_%s"), *Underscored(HeroSlug), *Underscored(CardSlug), *Lang.ToUpper());
}

bool ProbeRequested(const TCHAR* CommandLine) { return CommandLine && FParse::Param(CommandLine, ProbeFlagName); }

FString ProbeLine() {
  const TArray<FUmCardMediaEntry>& R = Registry();
  int32 Loaded = 0;
  FString FirstMissing;
  for (const FUmCardMediaEntry& E : R) {
    if (LoadTexture(E)) {
      ++Loaded;
    } else if (FirstMissing.IsEmpty()) {
      FirstMissing = E.ObjectPath;
    }
  }
  return FString::Printf(TEXT("CARDMEDIA probe entries=%d loaded=%d missing=%d%s"), R.Num(), Loaded, R.Num() - Loaded,
                         FirstMissing.IsEmpty() ? TEXT("") : *(TEXT(" first=") + FirstMissing));
}

}  // namespace UmCardMedia

#include "S08BaseDigitAuthoring.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/Font.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

#if WITH_EDITOR
#include "AssetRegistry/AssetRegistryModule.h"
#include "Engine/FontImportOptions.h"
#include "Engine/Texture2D.h"
#include "Factories/TrueTypeFontFactory.h"
#include "Misc/FeedbackContext.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#endif

namespace {
FString S08DigitJsonString(const TSharedRef<FJsonObject>& Object) {
  FString Out;
  const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Out);
  FJsonSerializer::Serialize(Object, Writer);
  return Out;
}
}  // namespace

FString US08BaseDigitAuthoringLibrary::AuthorOfflineDigitFont(const FString& PackagePath, const FString& AssetName,
                                                              const FString& FontName, float Height, bool bBold,
                                                              bool bDistanceField, const FString& Chars,
                                                              bool bOverwrite) {
  TSharedRef<FJsonObject> R = MakeShared<FJsonObject>();
  R->SetStringField(TEXT("schema"), TEXT("unmatched.an31-offline-digit-font/1"));
#if WITH_EDITOR
  const FString PackageName = PackagePath / AssetName;
  R->SetStringField(TEXT("asset"), PackageName);
  R->SetStringField(TEXT("fontName"), FontName);
  UTrueTypeFontFactory* Factory = NewObject<UTrueTypeFontFactory>();
  Factory->SetupFontImportOptions();
  FFontImportOptionsData& D = Factory->ImportOptions->Data;
  D.FontName = FontName;
  D.Height = Height;
  D.bEnableBold = bBold;
  D.bEnableItalic = false;
  D.bEnableUnderline = false;
  D.bEnableAntialiasing = true;
  D.bAlphaOnly = false;
  D.bUseDistanceFieldAlpha = bDistanceField;
  D.DistanceFieldScaleFactor = 16;
  D.DistanceFieldScanRadiusScale = 1.0f;
  D.Chars = Chars;
  D.UnicodeRange = FString();
  D.CharsFilePath = FString();
  D.bCreatePrintableOnly = true;
  D.bIncludeASCIIRange = false;
  D.bEnableDropShadow = false;
  D.ForegroundColor = FLinearColor::White;
  D.TexturePageWidth = 256;
  D.TexturePageMaxHeight = 256;
  D.XPadding = 4;
  D.YPadding = 4;
  D.ExtendBoxTop = 0;
  D.ExtendBoxBottom = 0;
  D.ExtendBoxRight = 0;
  D.ExtendBoxLeft = 0;
  D.Kerning = 0;
  UFont* Font = nullptr;
  if (FPackageName::DoesPackageExist(PackageName)) {
    UFont* Existing = LoadObject<UFont>(nullptr, *(PackageName + TEXT(".") + AssetName));
    if (!Existing) {
      R->SetStringField(TEXT("error"), TEXT("the package exists but is not a UFont"));
      return S08DigitJsonString(R);
    }
    if (!bOverwrite) {
      R->SetStringField(TEXT("result"), TEXT("exists-unchanged"));
      Font = Existing;
    } else {
      Existing->ImportOptions = D;
      Existing->FontCacheType = EFontCacheType::Offline;
      R->SetBoolField(TEXT("reimported"), Factory->Reimport(Existing) == EReimportResult::Succeeded);
      Font = LoadObject<UFont>(nullptr, *(PackageName + TEXT(".") + AssetName));
    }
  } else {
    UPackage* Package = CreatePackage(*PackageName);
    Font = Cast<UFont>(Factory->FactoryCreateNew(UFont::StaticClass(), Package, FName(*AssetName),
                                                 RF_Public | RF_Standalone, nullptr, GWarn));
    if (Font) FAssetRegistryModule::AssetCreated(Font);
  }
  if (!Font) {
    R->SetStringField(TEXT("error"), TEXT("UTrueTypeFontFactory created no font (is the GDI face available?)"));
    return S08DigitJsonString(R);
  }
  Font->FontCacheType = EFontCacheType::Offline;
  R->SetStringField(TEXT("cacheType"), Font->FontCacheType == EFontCacheType::Offline ? TEXT("offline") : TEXT("runtime"));
  R->SetNumberField(TEXT("pages"), Font->Textures.Num());
  R->SetNumberField(TEXT("maxCharHeight"), Font->GetMaxCharHeight());
  R->SetBoolField(TEXT("distanceField"), Font->ImportOptions.bUseDistanceFieldAlpha);
  TArray<TSharedPtr<FJsonValue>> Cells;
  for (const TCHAR Ch : Chars) {
    const int32 Index = Font->RemapChar(Ch);
    if (!Font->Characters.IsValidIndex(Index)) continue;
    const FFontCharacter& C = Font->Characters[Index];
    TSharedRef<FJsonObject> Cell = MakeShared<FJsonObject>();
    Cell->SetStringField(TEXT("char"), FString(1, &Ch));
    Cell->SetNumberField(TEXT("u"), C.StartU);
    Cell->SetNumberField(TEXT("v"), C.StartV);
    Cell->SetNumberField(TEXT("w"), C.USize);
    Cell->SetNumberField(TEXT("h"), C.VSize);
    Cell->SetNumberField(TEXT("page"), C.TextureIndex);
    Cells.Add(MakeShared<FJsonValueObject>(Cell));
  }
  R->SetArrayField(TEXT("cells"), Cells);
  if (Font->Textures.Num() > 0 && Font->Textures[0]) {
    R->SetNumberField(TEXT("pageWidth"), Font->Textures[0]->Source.GetSizeX());
    R->SetNumberField(TEXT("pageHeight"), Font->Textures[0]->Source.GetSizeY());
  }
  UPackage* Package = Font->GetOutermost();
  Package->MarkPackageDirty();
  const FString File = FPackageName::LongPackageNameToFilename(PackageName, FPackageName::GetAssetPackageExtension());
  FSavePackageArgs Args;
  Args.TopLevelFlags = RF_Public | RF_Standalone;
  Args.SaveFlags = SAVE_NoError;
  const bool bSaved = UPackage::SavePackage(Package, Font, *File, Args);
  R->SetStringField(TEXT("file"), FPaths::ConvertRelativePathToFull(File));
  R->SetBoolField(TEXT("saved"), bSaved);
  if (!R->HasField(TEXT("result"))) R->SetStringField(TEXT("result"), bSaved ? TEXT("saved") : TEXT("save-failed"));
#else
  R->SetStringField(TEXT("error"), TEXT("editor only"));
#endif
  return S08DigitJsonString(R);
}

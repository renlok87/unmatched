// AN-31 (ВР-72, ВР-Z1R-03): authoring of the harpy base digit's OFFLINE font, called from a UE Python script under
// UnrealEditor-Cmd (tools/art/hero/base_digit_import_ue.py via tools/art/hero/base_digit_import.py).
// Why C++: UTextRenderComponent draws only offline (texture-page) fonts - a runtime-cached font never reaches its
// scene proxy - and the offline importer (UTrueTypeFontFactory, Windows GDI) takes its options in
// FFontImportOptionsData, a struct with no Blueprint-visible field, so Python cannot fill it. The caller makes the
// TTF visible to GDI first (AddFontResourceExW FR_PRIVATE in the editor process - nothing is installed). Editor only;
// the game build has the function but it returns an error report.
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "S08BaseDigitAuthoring.generated.h"

UCLASS()
class UNMATCHED_API US08BaseDigitAuthoringLibrary : public UBlueprintFunctionLibrary {
  GENERATED_BODY()

public:
  /** Imports (bOverwrite: re-imports) the offline UFont PackagePath/AssetName from the GDI face FontName (bold) at
   *  Height px with a distance-field alpha (bDistanceField) for the characters Chars only, and saves it. Returns a
   *  JSON report: the asset, the cache type, the texture pages, MaxCharHeight and the cell of every character. */
  UFUNCTION(BlueprintCallable, Category = "S08|Heroes")
  static FString AuthorOfflineDigitFont(const FString& PackagePath, const FString& AssetName, const FString& FontName,
                                        float Height, bool bBold, bool bDistanceField, const FString& Chars,
                                        bool bOverwrite);
};

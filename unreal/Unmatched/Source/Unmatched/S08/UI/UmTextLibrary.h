// VS-1 HB-05: authoring call for tools/s08/hud_contract/hud_strings_build.py (UE Python, -run=pythonscript). The
// engine's Python API imports a string table CSV but cannot set the table namespace; this call does both, so the four
// tables ST_Hud / ST_Screens / ST_Why / ST_Ms get the namespaces of 04 §6.1 (hud, screens, why, ms).
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "UmTextLibrary.generated.h"

class UStringTable;

UCLASS()
class UNMATCHED_API UUmTextLibrary : public UBlueprintFunctionLibrary {
  GENERATED_BODY()

 public:
  /** Sets the namespace, replaces all entries with the CSV (Key, SourceString[, metadata…]) and marks the asset dirty. */
  UFUNCTION(BlueprintCallable, Category = "Um HUD|Strings")
  static bool AuthorStringTable(UStringTable* Table, const FString& Namespace, const FString& Csv);
};

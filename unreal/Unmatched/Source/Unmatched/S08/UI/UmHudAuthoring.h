// VS-2 HB-06 / HB-11 (04-hud-spec.md §4.1 "WBP, тема и StringTable — git add -f или генерация скриптом", HUD-RULES П9):
// the widget blueprints of the UMG HUD are generated, never hand-edited - each from the BuildDefaultTree of its C++ base
// (the same tree the class builds in code without a WBP):
//   /Game/S08/UI/Root/WBP_UmHudRoot      UUmHudRoot
//   /Game/S08/UI/Hud/WBP_UI_SCR_GAME     UUmGameHud
//   /Game/S08/UI/Common/WBP_UmButton     UUmButton
// Called from UE Python: tools/s08/hud_contract/ue_author_um_hud.py (UnrealEditor-Cmd -run=pythonscript).
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "UmHudAuthoring.generated.h"

UCLASS()
class UNMATCHED_API UUmHudAuthoringLibrary : public UBlueprintFunctionLibrary {
  GENERATED_BODY()

 public:
  /** Creates (bOverwrite: rebuilds the tree of) the three WBPs, compiles and saves them; a JSON report. Editor only. */
  UFUNCTION(BlueprintCallable, Category = "Um HUD|Authoring")
  static FString AuthorUmHudWidgetBlueprints(bool bOverwrite);
};

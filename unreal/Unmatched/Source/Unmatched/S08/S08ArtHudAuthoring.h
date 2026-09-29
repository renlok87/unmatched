// W4-C: authoring of the art HUD widget blueprints, called from a UE Python
// script under UnrealEditor-Cmd of the ART worktree
// (tools/art/umg/ue_author_art_hud.py via tools/art/art_hud_umg.py author).
// Why C++ and not pure Python/MCP: UWidgetBlueprint::WidgetTree is not
// exposed to reflection (Python cannot build a widget tree), the UMGToolSet
// functions are AICallable only (not BlueprintCallable, so not in Python) and
// its MCP server needs a running GUI editor of the art project. The tree is
// built by the SAME function the widget classes use for their code default
// tree (US08ArtPlateWidget::BuildDefaultTree), attached through
// FWidgetBlueprintOperationUtils::AddWidget (variable GUIDs, like the
// designer), compiled and saved. Editor only; the game build has the
// function but it returns an error report.
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "S08ArtHudAuthoring.generated.h"

UCLASS()
class UNMATCHED_API US08ArtHudAuthoringLibrary : public UBlueprintFunctionLibrary {
  GENERATED_BODY()

public:
  /** Creates (or with bOverwrite rebuilds the tree of) WBP_S08ArtPlate and
   *  WBP_S08ArtIcon under Folder (default /Game/S08/UI/ArtHud - cooked via
   *  DirectoriesToAlwaysCook /Game/S08), compiles and saves them. Returns a
   *  JSON report (assets, parent class, widget names, compile status, files). */
  UFUNCTION(BlueprintCallable, Category = "S08|Art HUD")
  static FString AuthorArtHudWidgetBlueprints(const FString& Folder, bool bOverwrite);
};

#include "S08ArtHudAuthoring.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "S08ArtHudWidgets.h"

#if WITH_EDITOR
#include "AssetRegistry/AssetRegistryModule.h"
#include "Blueprint/WidgetTree.h"
#include "Components/PanelWidget.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "WidgetBlueprint.h"
#include "WidgetBlueprintOperationUtils.h"
#endif

namespace {
FString S08JsonString(const TSharedRef<FJsonObject>& Object) {
  FString Out;
  const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Out);
  FJsonSerializer::Serialize(Object, Writer);
  return Out;
}

#if WITH_EDITOR
using FS08TreeBuilder = TFunctionRef<bool(UWidgetTree&, FS08AttachWidget, FString*)>;

TSharedRef<FJsonObject> S08AuthorOne(const FString& Folder, const FString& Name, UClass* Parent,
                                     FS08TreeBuilder Build, bool bOverwrite) {
  TSharedRef<FJsonObject> R = MakeShared<FJsonObject>();
  const FString PackageName = Folder / Name;
  R->SetStringField(TEXT("asset"), PackageName);
  R->SetStringField(TEXT("parentClass"), Parent->GetPathName());
  UWidgetBlueprint* BP = nullptr;
  UPackage* Package = nullptr;
  bool bCreated = false;
  if (FPackageName::DoesPackageExist(PackageName)) {
    BP = LoadObject<UWidgetBlueprint>(nullptr, *(PackageName + TEXT(".") + Name));
    if (!BP) {
      R->SetStringField(TEXT("error"), TEXT("package exists but is not a widget blueprint"));
      return R;
    }
    if (!bOverwrite) {
      R->SetStringField(TEXT("result"), TEXT("exists-unchanged"));
      return R;
    }
    Package = BP->GetOutermost();
    if (UWidget* OldRoot = BP->WidgetTree->RootWidget) {
      FText Error;
      FWidgetBlueprintOperationUtils::RemoveWidget(BP, OldRoot, Error);
    }
  } else {
    Package = CreatePackage(*PackageName);
    BP = FWidgetBlueprintOperationUtils::CreateWidgetBlueprint(Package, FName(*Name), BPTYPE_Normal, Parent,
                                                               /*RootWidgetClass=*/nullptr, NAME_None,
                                                               /*bRegisterAndCompile=*/false);
    bCreated = BP != nullptr;
  }
  if (!BP) {
    R->SetStringField(TEXT("error"), TEXT("CreateWidgetBlueprint failed"));
    return R;
  }
  TArray<FString> AttachErrors;
  FString BuildError;
  const bool bBuilt = Build(*BP->WidgetTree, [BP, &AttachErrors](UWidget* Child, UPanelWidget* ParentWidget) {
    FText Error;
    if (!FWidgetBlueprintOperationUtils::AddWidget(BP, Child, ParentWidget, -1, Error)) {
      AttachErrors.Add(FString::Printf(TEXT("%s: %s"), *Child->GetName(), *Error.ToString()));
      return false;
    }
    Child->bIsVariable = true;  // BindWidget parts are variables, like the designer's
    return true;
  }, &BuildError);
  TArray<TSharedPtr<FJsonValue>> Widgets;
  BP->WidgetTree->ForEachWidget([&Widgets](UWidget* W) {
    Widgets.Add(MakeShared<FJsonValueString>(FString::Printf(TEXT("%s:%s"), *W->GetName(), *W->GetClass()->GetName())));
  });
  R->SetArrayField(TEXT("widgets"), Widgets);
  if (!bBuilt) {
    R->SetStringField(TEXT("error"), BuildError + TEXT(" ") + FString::Join(AttachErrors, TEXT("; ")));
    return R;
  }
  FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
  FKismetEditorUtilities::CompileBlueprint(BP);
  const bool bCompiled = BP->Status == BS_UpToDate || BP->Status == BS_UpToDateWithWarnings;
  R->SetStringField(TEXT("compileStatus"), BP->Status == BS_UpToDate ? TEXT("up-to-date")
                                           : BP->Status == BS_UpToDateWithWarnings ? TEXT("warnings")
                                           : BP->Status == BS_Error ? TEXT("error") : TEXT("dirty"));
  if (bCreated) FAssetRegistryModule::AssetCreated(BP);
  Package->MarkPackageDirty();
  const FString File = FPackageName::LongPackageNameToFilename(PackageName, FPackageName::GetAssetPackageExtension());
  FSavePackageArgs Args;
  Args.TopLevelFlags = RF_Public | RF_Standalone;
  Args.SaveFlags = SAVE_NoError;
  const bool bSaved = bCompiled && UPackage::SavePackage(Package, BP, *File, Args);
  R->SetStringField(TEXT("file"), FPaths::ConvertRelativePathToFull(File));
  R->SetBoolField(TEXT("saved"), bSaved);
  R->SetStringField(TEXT("result"), !bCompiled ? TEXT("compile-failed") : bSaved ? (bCreated ? TEXT("created") : TEXT("rebuilt"))
                                                                          : TEXT("save-failed"));
  UClass* Generated = BP->GeneratedClass;
  R->SetStringField(TEXT("generatedClass"), Generated ? Generated->GetPathName() : FString());
  return R;
}
#endif
}  // namespace

TSharedRef<FJsonObject> S08AuthorWidgetBlueprint(const FString& Folder, const FString& Name, UClass* Parent,
                                                 TFunctionRef<bool(UWidgetTree&, FS08AttachWidget, FString*)> Build,
                                                 bool bOverwrite) {
#if WITH_EDITOR
  return S08AuthorOne(Folder, Name, Parent, Build, bOverwrite);
#else
  TSharedRef<FJsonObject> R = MakeShared<FJsonObject>();
  R->SetStringField(TEXT("error"), TEXT("editor only"));
  return R;
#endif
}

FString US08ArtHudAuthoringLibrary::AuthorArtHudWidgetBlueprints(const FString& Folder, bool bOverwrite) {
  TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
  Report->SetStringField(TEXT("schema"), TEXT("unmatched.w4c-art-hud-wbp/1"));
#if WITH_EDITOR
  const FString Root = Folder.IsEmpty() ? FString(TEXT("/Game/S08/UI/ArtHud")) : Folder;
  Report->SetStringField(TEXT("folder"), Root);
  Report->SetBoolField(TEXT("overwrite"), bOverwrite);
  TArray<TSharedPtr<FJsonValue>> Assets;
  Assets.Add(MakeShared<FJsonValueObject>(S08AuthorOne(
      Root, FPackageName::GetShortName(US08ArtPlateWidget::WidgetBlueprintPath), US08ArtPlateWidget::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) {
        return US08ArtPlateWidget::BuildDefaultTree(Tree, Attach, Error);
      },
      bOverwrite)));
  Assets.Add(MakeShared<FJsonValueObject>(S08AuthorOne(
      Root, FPackageName::GetShortName(US08ArtIconWidget::WidgetBlueprintPath), US08ArtIconWidget::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) {
        return US08ArtIconWidget::BuildDefaultTree(Tree, Attach, Error);
      },
      bOverwrite)));
  // W5b-R D-1: the screen tag and the damage number (proposals UI-HUD-TAG / UI-HUD-DAMAGE).
  Assets.Add(MakeShared<FJsonValueObject>(S08AuthorOne(
      Root, FPackageName::GetShortName(US08ArtTagWidget::WidgetBlueprintPath), US08ArtTagWidget::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) {
        return US08ArtTagWidget::BuildDefaultTree(Tree, Attach, Error);
      },
      bOverwrite)));
  Assets.Add(MakeShared<FJsonValueObject>(S08AuthorOne(
      Root, FPackageName::GetShortName(US08ArtDamageWidget::WidgetBlueprintPath), US08ArtDamageWidget::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) {
        return US08ArtDamageWidget::BuildDefaultTree(Tree, Attach, Error);
      },
      bOverwrite)));
  Report->SetArrayField(TEXT("assets"), Assets);
#else
  Report->SetStringField(TEXT("error"), TEXT("editor only"));
#endif
  return S08JsonString(Report);
}

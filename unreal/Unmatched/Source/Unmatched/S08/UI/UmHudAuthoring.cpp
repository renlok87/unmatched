// VS-2 HB-06 / HB-11: authoring of the UMG HUD widget blueprints - see UmHudAuthoring.h.
#include "UmHudAuthoring.h"

#include "../S08ArtHudAuthoring.h"
#include "UmButton.h"
#include "UmConnectionBadge.h"
#include "UmHudBanner.h"
#include "UmHudStatusLine.h"
#include "UmHudTop.h"
#include "UmCursor.h"
#include "UmPortrait.h"
#include "../S08TurnPortraitWidget.h"
#include "UmGameHud.h"
#include "UmHudRoot.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/PackageName.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

FString UUmHudAuthoringLibrary::AuthorUmHudWidgetBlueprints(bool bOverwrite) {
  TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
  Report->SetStringField(TEXT("schema"), TEXT("unmatched.vs2-um-hud-wbp/1"));
  Report->SetBoolField(TEXT("overwrite"), bOverwrite);
  TArray<TSharedPtr<FJsonValue>> Assets;
  auto One = [&Assets, bOverwrite](const TCHAR* Path, UClass* Parent,
                                    TFunctionRef<bool(UWidgetTree&, FS08AttachWidget, FString*)> Build) {
    const FString Package(Path);
    Assets.Add(MakeShared<FJsonValueObject>(S08AuthorWidgetBlueprint(
        FPackageName::GetLongPackagePath(Package), FPackageName::GetShortName(Package), Parent, Build, bOverwrite)));
  };
  One(UUmHudRoot::WidgetBlueprintPath, UUmHudRoot::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmHudRoot::BuildDefaultTree(Tree, Attach, Error); });
  One(UUmGameHud::WidgetBlueprintPath, UUmGameHud::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmGameHud::BuildDefaultTree(Tree, Attach, Error); });
  One(UUmButton::WidgetBlueprintPath, UUmButton::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmButton::BuildDefaultTree(Tree, Attach, Error); });
  One(UUmCursor::WidgetBlueprintPath, UUmCursor::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmCursor::BuildDefaultTree(Tree, Attach, Error); });
  One(UmPortrait::WidgetBlueprintPath, US08TurnPortraitWidget::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) {
        return US08TurnPortraitWidget::BuildDefaultTree(Tree, Attach, Error);
      });
  // VS-2 HB-14...HB-16: the chip before TOP (TOP nests WBP_UmButton and WBP_UmConnectionBadge when they exist)
  One(UUmConnectionBadge::WidgetBlueprintPath, UUmConnectionBadge::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmConnectionBadge::BuildDefaultTree(Tree, Attach, Error); });
  One(UUmHudTop::WidgetBlueprintPath, UUmHudTop::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmHudTop::BuildDefaultTree(Tree, Attach, Error); });
  One(UUmHudStatusLine::WidgetBlueprintPath, UUmHudStatusLine::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmHudStatusLine::BuildDefaultTree(Tree, Attach, Error); });
  One(UUmHudBanner::WidgetBlueprintPath, UUmHudBanner::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmHudBanner::BuildDefaultTree(Tree, Attach, Error); });
  Report->SetArrayField(TEXT("assets"), Assets);
  FString Out;
  const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Out);
  FJsonSerializer::Serialize(Report, Writer);
  return Out;
}

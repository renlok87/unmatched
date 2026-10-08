// VS-2 HB-06 / HB-11: authoring of the UMG HUD widget blueprints - see UmHudAuthoring.h.
#include "UmHudAuthoring.h"

#include "../S08ArtHudAuthoring.h"
#include "UmButton.h"
#include "UmCardWidget.h"
#include "UmConnectionBadge.h"
#include "UmConfirmDialog.h"
#include "UmHudActions.h"
#include "UmHudBanner.h"
#include "UmHudCombatCenter.h"
#include "UmHudCombatEdge.h"
#include "UmHudDeckPanel.h"
#include "UmHudDecks.h"
#include "UmHudHand.h"
#include "UmHudLog.h"
#include "UmHudOppHand.h"
#include "UmHudPending.h"
#include "UmHudPlayerPanel.h"
#include "UmHudSourceSlot.h"
#include "UmHudStatusLine.h"
#include "UmHudSubtitle.h"
#include "UmHudTop.h"
#include "UmScreenBoot.h"
#include "UmScreenInspect.h"
#include "UmScreenLobby.h"
#include "UmScreenLogin.h"
#include "UmToast.h"
#include "UmToastStack.h"
#include "UmCursor.h"
#include "UmPortrait.h"
#include "UmSpinner.h"
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
  // VS-2 HB-18...HB-21: after WBP_UmPortrait (the panels nest it); one class, two mirrored trees
  One(UUmHudPlayerPanel::LocBlueprintPath, UUmHudPlayerPanel::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) {
        return UUmHudPlayerPanel::BuildDefaultTree(Tree, Attach, EUmPanelSide::Own, Error);
      });
  One(UUmHudPlayerPanel::OppBlueprintPath, UUmHudPlayerPanel::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) {
        return UUmHudPlayerPanel::BuildDefaultTree(Tree, Attach, EUmPanelSide::Opp, Error);
      });
  One(UUmHudOppHand::WidgetBlueprintPath, UUmHudOppHand::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmHudOppHand::BuildDefaultTree(Tree, Attach, Error); });
  // VS-3 CP-15: the card of every display (hand, combat, slot, inspector, decks, OPP-HAND)
  One(UUmCardWidget::WidgetBlueprintPath, UUmCardWidget::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmCardWidget::BuildDefaultTree(Tree, Attach, Error); });
  // VS-3 HB-24 / HB-25: the hand (its cards are pooled WBP_UmCard instances made at run time)
  One(UUmHudHand::WidgetBlueprintPath, UUmHudHand::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmHudHand::BuildDefaultTree(Tree, Attach, Error); });
  // VS-3 HB-47: the spinner (screens and the HUD take it); HB-27 / HB-28: the chips (nest WBP_UmButton, WBP_UmCard) and
  // the deck panel (WBP_UmButton; its rows and skeleton are made at run time)
  One(UUmSpinner::WidgetBlueprintPath, UUmSpinner::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmSpinner::BuildDefaultTree(Tree, Attach, Error); });
  One(UUmHudDecks::WidgetBlueprintPath, UUmHudDecks::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmHudDecks::BuildDefaultTree(Tree, Attach, Error); });
  One(UUmHudDeckPanel::WidgetBlueprintPath, UUmHudDeckPanel::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmHudDeckPanel::BuildDefaultTree(Tree, Attach, Error); });
  // VS-3 HB-30...HB-33: the combat edge (nests WBP_UmCard and WBP_UmButton) and the combat centre
  One(UUmHudCombatEdge::WidgetBlueprintPath, UUmHudCombatEdge::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmHudCombatEdge::BuildDefaultTree(Tree, Attach, Error); });
  One(UUmHudCombatCenter::WidgetBlueprintPath, UUmHudCombatCenter::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmHudCombatCenter::BuildDefaultTree(Tree, Attach, Error); });
  // VS-3 SC-01: the confirm dialog (nests WBP_UmButton); UUmScreenBase / UUmModalBase are abstract, without a WBP
  One(UUmConfirmDialog::WidgetBlueprintPath, UUmConfirmDialog::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmConfirmDialog::BuildDefaultTree(Tree, Attach, Error); });
  // VS-4 HB-35 / HB-37: the choice (nests WBP_UmButton, WBP_UmCard; its number picker is code-built) and the source
  // card (nests WBP_UmCard)
  One(UUmHudPending::WidgetBlueprintPath, UUmHudPending::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmHudPending::BuildDefaultTree(Tree, Attach, Error); });
  One(UUmHudSourceSlot::WidgetBlueprintPath, UUmHudSourceSlot::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmHudSourceSlot::BuildDefaultTree(Tree, Attach, Error); });
  // VS-4 HB-39...HB-41: the log, one toast (nests WBP_UmButton for its cross), the stack (its toasts are pooled
  // WBP_UmToast made at run time) and the subtitle capsule
  One(UUmHudLog::WidgetBlueprintPath, UUmHudLog::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmHudLog::BuildDefaultTree(Tree, Attach, Error); });
  One(UUmToast::WidgetBlueprintPath, UUmToast::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmToast::BuildDefaultTree(Tree, Attach, Error); });
  One(UUmToastStack::WidgetBlueprintPath, UUmToastStack::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmToastStack::BuildDefaultTree(Tree, Attach, Error); });
  One(UUmHudSubtitle::WidgetBlueprintPath, UUmHudSubtitle::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmHudSubtitle::BuildDefaultTree(Tree, Attach, Error); });
  // VS-4 HB-43: ACTIONS (nests WBP_UmButton four times; the tooltip plate is part of its tree)
  One(UUmHudActions::WidgetBlueprintPath, UUmHudActions::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmHudActions::BuildDefaultTree(Tree, Attach, Error); });
  // VS-4 SC-21...SC-23 / CP-22: INSPECT (nests WBP_UmCard and WBP_UmButton; the grid cards are pooled at run time)
  One(UUmScreenInspect::WidgetBlueprintPath, UUmScreenInspect::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmScreenInspect::BuildDefaultTree(Tree, Attach, Error); });
  // VS-7 SC-03...SC-07: BOOT (nests WBP_UmButton, WBP_UmSpinner, the progress bar and the code-built resume modal) and
  // LOGIN (nests WBP_UmButton, WBP_UmSpinner; its fields are UEditableTextBox)
  One(UUmScreenBoot::WidgetBlueprintPath, UUmScreenBoot::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmScreenBoot::BuildDefaultTree(Tree, Attach, Error); });
  One(UUmScreenLogin::WidgetBlueprintPath, UUmScreenLogin::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmScreenLogin::BuildDefaultTree(Tree, Attach, Error); });
  // VS-7 SC-08...SC-13: LOBBY (nests WBP_UmButton, WBP_UmSpinner, the skeleton; the board tiles, the code cells and the
  // rows are code-built at run time)
  One(UUmScreenLobby::WidgetBlueprintPath, UUmScreenLobby::StaticClass(),
      [](UWidgetTree& Tree, FS08AttachWidget Attach, FString* Error) { return UUmScreenLobby::BuildDefaultTree(Tree, Attach, Error); });
  Report->SetArrayField(TEXT("assets"), Assets);
  FString Out;
  const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Out);
  FJsonSerializer::Serialize(Report, Writer);
  return Out;
}

// VS-2 HB-06: the root of the UMG HUD - see UmHudRoot.h.
#include "UmHudRoot.h"

#include "UmGameHud.h"
#include "Blueprint/WidgetTree.h"
#include "Components/NamedSlot.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/WidgetSwitcher.h"
#include "Components/WidgetSwitcherSlot.h"
#include "Engine/World.h"
#include "Misc/PackageName.h"

const TCHAR* const UUmHudRoot::WidgetBlueprintPath = TEXT("/Game/S08/UI/Root/WBP_UmHudRoot");

namespace {
template <typename T>
T* UmRootMake(UWidgetTree& Tree, const TCHAR* Name) {
  return Tree.ConstructWidget<T>(T::StaticClass(), FName(Name));
}

template <typename T>
T* UmRootFind(UWidgetTree* Tree, const TCHAR* Name) {
  return Tree ? Cast<T>(Tree->FindWidget(FName(Name))) : nullptr;
}

void UmRootFill(UWidget* Child) {
  if (UOverlaySlot* Slot = Cast<UOverlaySlot>(Child->Slot)) {
    Slot->SetHorizontalAlignment(HAlign_Fill);
    Slot->SetVerticalAlignment(VAlign_Fill);
  }
}
}  // namespace

bool UUmHudRoot::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  auto Fail = [OutError](const TCHAR* What) {
    if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), What);
    return false;
  };
  UOverlay* Root = UmRootMake<UOverlay>(Tree, TEXT("RootOverlay"));
  Root->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(Root, nullptr)) return Fail(TEXT("RootOverlay"));
  // 04 §1: scene -> HUD of the match (Screens: GAME) -> screen veil -> modal -> reconnect overlay (cursor: HB-12)
  UWidgetSwitcher* ScreensWidget = UmRootMake<UWidgetSwitcher>(Tree, TEXT("Screens"));
  ScreensWidget->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(ScreensWidget, Root)) return Fail(TEXT("Screens"));
  UmRootFill(ScreensWidget);
  UOverlay* ModalsWidget = UmRootMake<UOverlay>(Tree, TEXT("Modals"));
  ModalsWidget->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(ModalsWidget, Root)) return Fail(TEXT("Modals"));
  UmRootFill(ModalsWidget);
  UNamedSlot* ReconnectWidget = UmRootMake<UNamedSlot>(Tree, TEXT("Reconnect"));
  ReconnectWidget->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(ReconnectWidget, Root)) return Fail(TEXT("Reconnect"));
  UmRootFill(ReconnectWidget);
  return true;
}

bool UUmHudRoot::Initialize() {
  const bool bFirst = Super::Initialize();
  if (bFirst && WidgetTree && !WidgetTree->RootWidget) {
    FString Error;
    UWidgetTree* Tree = WidgetTree;
    bCodeDefaultTree = BuildDefaultTree(*Tree, [Tree](UWidget* Child, UPanelWidget* Parent) {
      if (!Parent) {
        Tree->RootWidget = Child;
        return true;
      }
      return Parent->AddChild(Child) != nullptr;
    }, &Error);
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD root default tree: %s"), *Error);
    Screens = UmRootFind<UWidgetSwitcher>(Tree, TEXT("Screens"));
    Modals = UmRootFind<UOverlay>(Tree, TEXT("Modals"));
    Reconnect = UmRootFind<UNamedSlot>(Tree, TEXT("Reconnect"));
  }
  if (bFirst) SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  return bFirst;
}

UUmHudRoot* UUmHudRoot::Create(UWorld* World, FString* OutSource) {
  if (!World) return nullptr;
  UClass* Class = UUmHudRoot::StaticClass();
  FString Source = TEXT("code-default");
  const FString Package = WidgetBlueprintPath;
  if (FPackageName::DoesPackageExist(Package)) {
    const FString ClassPath = Package + TEXT(".") + FPackageName::GetShortName(Package) + TEXT("_C");
    if (UClass* Wbp = LoadClass<UUmHudRoot>(nullptr, *ClassPath, nullptr, LOAD_NoWarn | LOAD_Quiet)) {
      Class = Wbp;
      Source = Package;
    }
  }
  UUmHudRoot* Root = CreateWidget<UUmHudRoot>(World, Class);
  if (OutSource) *OutSource = Source;
  return Root;
}

UUmGameHud* UUmHudRoot::EnsureGameHud() {
  if (GameHud || !Screens) return GameHud;
  UClass* Class = UUmGameHud::StaticClass();
  const FString Package = UUmGameHud::WidgetBlueprintPath;
  if (FPackageName::DoesPackageExist(Package)) {
    const FString ClassPath = Package + TEXT(".") + FPackageName::GetShortName(Package) + TEXT("_C");
    if (UClass* Wbp = LoadClass<UUmGameHud>(nullptr, *ClassPath, nullptr, LOAD_NoWarn | LOAD_Quiet)) Class = Wbp;
  }
  GameHud = CreateWidget<UUmGameHud>(this, Class);
  if (!GameHud) return nullptr;
  Screens->AddChild(GameHud);
  if (UWidgetSwitcherSlot* SwitcherSlot = Cast<UWidgetSwitcherSlot>(GameHud->Slot)) {
    SwitcherSlot->SetHorizontalAlignment(HAlign_Fill);
    SwitcherSlot->SetVerticalAlignment(VAlign_Fill);
  }
  Screens->SetActiveWidget(GameHud);
  return GameHud;
}

bool UUmHudRoot::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Screens) Missing.Add(TEXT("Screens"));
  if (!Modals) Missing.Add(TEXT("Modals"));
  if (!Reconnect) Missing.Add(TEXT("Reconnect"));
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

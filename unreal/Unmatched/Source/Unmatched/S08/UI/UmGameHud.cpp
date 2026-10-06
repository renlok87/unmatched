// VS-2 HB-06: the GAME screen of the UMG HUD - see UmGameHud.h.
#include "UmGameHud.h"

#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/SizeBox.h"
#include "Misc/PackageName.h"

const TCHAR* const UUmGameHud::WidgetBlueprintPath = TEXT("/Game/S08/UI/Hud/WBP_UI_SCR_GAME");

namespace UmGameHudSlots {
const TCHAR* SlotName(EUmGameSlot Slot) {
  switch (Slot) {
    case EUmGameSlot::Top: return TEXT("Top");
    case EUmGameSlot::Status: return TEXT("Status");
    case EUmGameSlot::PanelLoc: return TEXT("PanelLoc");
    case EUmGameSlot::PanelOpp: return TEXT("PanelOpp");
    case EUmGameSlot::OppHand: return TEXT("OppHand");
    case EUmGameSlot::Hand: return TEXT("Hand");
    case EUmGameSlot::Decks: return TEXT("Decks");
    case EUmGameSlot::DeckPanel: return TEXT("DeckPanel");
    case EUmGameSlot::Actions: return TEXT("Actions");
    case EUmGameSlot::CombatCenter: return TEXT("CombatCenter");
    case EUmGameSlot::CombatEdgeL: return TEXT("CombatEdgeL");
    case EUmGameSlot::CombatEdgeR: return TEXT("CombatEdgeR");
    case EUmGameSlot::Pending: return TEXT("Pending");
    case EUmGameSlot::SourceSlot: return TEXT("SourceSlot");
    case EUmGameSlot::Log: return TEXT("Log");
    case EUmGameSlot::Banner: return TEXT("Banner");
    case EUmGameSlot::Toast: return TEXT("Toast");
    case EUmGameSlot::Sub: return TEXT("Sub");
    default: return TEXT("?");
  }
}

FBox2D SlotRect(const FUmHudLayout& Layout, EUmGameSlot Slot) {
  switch (Slot) {
    case EUmGameSlot::Top: return Layout.Rect(EUmHudBlock::Top);
    case EUmGameSlot::Status: return Layout.Rect(EUmHudBlock::Status);
    case EUmGameSlot::PanelLoc: return Layout.Rect(EUmHudBlock::PanelLoc);
    case EUmGameSlot::PanelOpp: return Layout.Rect(EUmHudBlock::PanelOpp);
    case EUmGameSlot::OppHand: return Layout.Rect(EUmHudBlock::OppHand);
    case EUmGameSlot::Hand: {
      FBox2D Row = Layout.Rect(EUmHudBlock::Hand);
      const FBox2D& Caption = Layout.Rect(EUmHudBlock::HandCaption);
      if (Row.bIsValid && Caption.bIsValid) Row += Caption;
      return Row;
    }
    case EUmGameSlot::Decks: return Layout.Rect(EUmHudBlock::Decks);
    case EUmGameSlot::DeckPanel: return Layout.Rect(EUmHudBlock::DeckPanel);
    case EUmGameSlot::Actions: return Layout.Rect(EUmHudBlock::Actions);
    case EUmGameSlot::CombatCenter:
    case EUmGameSlot::Pending: return Layout.Rect(EUmHudBlock::Center);
    case EUmGameSlot::CombatEdgeL: return Layout.Rect(EUmHudBlock::CombatL);
    case EUmGameSlot::CombatEdgeR: return Layout.Rect(EUmHudBlock::CombatR);
    case EUmGameSlot::SourceSlot: return Layout.Rect(EUmHudBlock::SourceSlot);
    case EUmGameSlot::Log: return Layout.Rect(EUmHudBlock::Log);
    case EUmGameSlot::Banner: return Layout.Rect(EUmHudBlock::Banner);
    case EUmGameSlot::Toast: return Layout.Rect(EUmHudBlock::Toast);
    case EUmGameSlot::Sub: return Layout.Rect(EUmHudBlock::Sub);
    default: return FBox2D(ForceInit);
  }
}

FName SlotKey(EUmGameSlot Slot) {
  switch (Slot) {
    case EUmGameSlot::Top: return FName(TEXT("top"));
    case EUmGameSlot::Status: return FName(TEXT("status"));
    case EUmGameSlot::PanelLoc:
    case EUmGameSlot::PanelOpp: return FName(TEXT("panels"));
    case EUmGameSlot::OppHand: return FName(TEXT("opphand"));
    case EUmGameSlot::Hand: return FName(TEXT("hand"));
    case EUmGameSlot::Decks: return FName(TEXT("decks"));
    case EUmGameSlot::DeckPanel: return FName(TEXT("deckpanel"));
    case EUmGameSlot::Actions: return FName(TEXT("actions"));
    case EUmGameSlot::CombatCenter:
    case EUmGameSlot::CombatEdgeL:
    case EUmGameSlot::CombatEdgeR: return FName(TEXT("combat"));
    case EUmGameSlot::Pending: return FName(TEXT("pending"));
    case EUmGameSlot::SourceSlot: return FName(TEXT("slot"));
    case EUmGameSlot::Log: return FName(TEXT("log"));
    case EUmGameSlot::Banner: return FName(TEXT("banner"));
    case EUmGameSlot::Toast: return FName(TEXT("toast"));
    case EUmGameSlot::Sub: return FName(TEXT("sub"));
    default: return NAME_None;
  }
}

UClass* WbpOrNative(UClass* Native, const TCHAR* Package) {
  const FString Path(Package);
  if (Native && FPackageName::DoesPackageExist(Path)) {
    const FString ClassPath = Path + TEXT(".") + FPackageName::GetShortName(Path) + TEXT("_C");
    if (UClass* Wbp = LoadClass<UObject>(nullptr, *ClassPath, nullptr, LOAD_NoWarn | LOAD_Quiet)) {
      if (Wbp->IsChildOf(Native)) return Wbp;
    }
  }
  return Native;
}

bool HeightFollowsBlock(EUmGameSlot Slot) { return Slot == EUmGameSlot::Status; }

bool ShownByProperty(const UWidget* Widget) {
  if (!Widget || Widget->GetRenderOpacity() <= 0.0f) return false;
  const ESlateVisibility V = Widget->GetVisibility();
  return V == ESlateVisibility::Visible || V == ESlateVisibility::HitTestInvisible ||
         V == ESlateVisibility::SelfHitTestInvisible;
}
}  // namespace UmGameHudSlots

bool UUmGameHud::BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError) {
  UCanvasPanel* Root = Tree.ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName(TEXT("Canvas")));
  Root->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  if (!Attach(Root, nullptr)) {
    if (OutError) *OutError = TEXT("attach failed: Canvas");
    return false;
  }
  for (int32 I = 0; I < UmGameSlotCount; ++I) {
    const TCHAR* Name = UmGameHudSlots::SlotName(static_cast<EUmGameSlot>(I));
    USizeBox* Box = Tree.ConstructWidget<USizeBox>(USizeBox::StaticClass(), FName(Name));
    // empty until its block moves in: no hit test, no paint
    Box->SetVisibility(ESlateVisibility::HitTestInvisible);
    if (!Attach(Box, Root)) {
      if (OutError) *OutError = FString::Printf(TEXT("attach failed: %s"), Name);
      return false;
    }
    if (UCanvasPanelSlot* CanvasSlot = Cast<UCanvasPanelSlot>(Box->Slot)) {
      CanvasSlot->SetAnchors(FAnchors(0.0f, 0.0f));
      CanvasSlot->SetAlignment(FVector2D::ZeroVector);
      CanvasSlot->SetAutoSize(false);
    }
  }
  return true;
}

bool UUmGameHud::Initialize() {
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
    if (!bCodeDefaultTree) UE_LOG(LogTemp, Error, TEXT("UMHUD game default tree: %s"), *Error);
    BindSlotsFromTree();
  }
  if (bFirst) SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  return bFirst;
}

void UUmGameHud::BindSlotsFromTree() {
  UWidgetTree* Tree = WidgetTree;
  if (!Tree) return;
  Canvas = Cast<UCanvasPanel>(Tree->FindWidget(FName(TEXT("Canvas"))));
  TObjectPtr<USizeBox>* Slots[UmGameSlotCount] = {&Top,          &Status,      &PanelLoc,    &PanelOpp,   &OppHand,
                                                  &Hand,         &Decks,       &DeckPanel,   &Actions,    &CombatCenter,
                                                  &CombatEdgeL,  &CombatEdgeR, &Pending,     &SourceSlot, &Log,
                                                  &Banner,       &Toast,       &Sub};
  for (int32 I = 0; I < UmGameSlotCount; ++I) {
    *Slots[I] = Cast<USizeBox>(Tree->FindWidget(FName(UmGameHudSlots::SlotName(static_cast<EUmGameSlot>(I)))));
  }
}

USizeBox* UUmGameHud::GetSlot(EUmGameSlot Which) const {
  const TObjectPtr<USizeBox> Slots[UmGameSlotCount] = {Top,         Status,      PanelLoc, PanelOpp,   OppHand, Hand,
                                                       Decks,       DeckPanel,   Actions,  CombatCenter, CombatEdgeL,
                                                       CombatEdgeR, Pending,     SourceSlot, Log,      Banner,  Toast,
                                                       Sub};
  const int32 I = static_cast<int32>(Which);
  return I >= 0 && I < UmGameSlotCount ? Slots[I].Get() : nullptr;
}

bool UUmGameHud::SetBlock(EUmGameSlot Which, UWidget* Block) {
  USizeBox* Box = GetSlot(Which);
  if (!Box || !Block) return false;
  if (Box->GetContent() == Block) return true;
  Box->SetContent(Block);
  return Box->GetContent() == Block;
}

bool UUmGameHud::HasAllParts(FString* OutMissing) const {
  TArray<FString> Missing;
  if (!Canvas) Missing.Add(TEXT("Canvas"));
  for (int32 I = 0; I < UmGameSlotCount; ++I) {
    if (!GetSlot(static_cast<EUmGameSlot>(I))) Missing.Add(UmGameHudSlots::SlotName(static_cast<EUmGameSlot>(I)));
  }
  if (OutMissing) *OutMissing = FString::Join(Missing, TEXT(","));
  return Missing.Num() == 0;
}

void UUmGameHud::ApplyLayout(const FUmHudLayout& InLayout, const TArray<FName>& SlateKeys, bool bAllSlate) {
  Layout = InLayout;
  for (int32 I = 0; I < UmGameSlotCount; ++I) {
    const EUmGameSlot Which = static_cast<EUmGameSlot>(I);
    USizeBox* Box = GetSlot(Which);
    if (!Box) continue;
    const FBox2D Rect = UmGameHudSlots::SlotRect(InLayout, Which);
    const bool bSlate = bAllSlate || SlateKeys.Contains(UmGameHudSlots::SlotKey(Which));
    if (!Rect.bIsValid || bSlate) {
      Box->SetVisibility(ESlateVisibility::Collapsed);
      continue;
    }
    const FVector2D Size = Rect.Max - Rect.Min;
    // VS-2 HB-15: STATUS keeps the rect's width (it centres its capsule) and takes the capsule's height (48 / 78 su)
    const bool bAutoHeight = Box->GetContent() && UmGameHudSlots::HeightFollowsBlock(Which);
    Box->SetWidthOverride(static_cast<float>(Size.X));
    if (bAutoHeight) {
      Box->ClearHeightOverride();
    } else {
      Box->SetHeightOverride(static_cast<float>(Size.Y));
    }
    // an empty slot never takes the mouse; a block that moves in sets its own visibility on its content
    Box->SetVisibility(Box->GetContent() ? ESlateVisibility::SelfHitTestInvisible : ESlateVisibility::HitTestInvisible);
    if (UCanvasPanelSlot* CanvasSlot = Cast<UCanvasPanelSlot>(Box->Slot)) {
      CanvasSlot->SetAnchors(FAnchors(0.0f, 0.0f));
      CanvasSlot->SetAlignment(FVector2D::ZeroVector);
      CanvasSlot->SetAutoSize(bAutoHeight);
      CanvasSlot->SetPosition(Rect.Min);
      CanvasSlot->SetSize(Size);
    }
  }
}

void UUmGameHud::CollectShotLines(TArray<FString>& Out, const FIntPoint& WindowPx) const {
  const FString Source = bCodeDefaultTree ? FString(TEXT("code-default")) : GetClass()->GetPathName();
  const bool bVisible = IsVisible() && WindowPx.X > 0 && WindowPx.Y > 0;
  Out.Add(FString::Printf(
      TEXT("SHOT widget id=UI-SCR-GAME impl=umg state=%s fighter=none bbox=0,0,%d,%d geom=painted visible=%d twin=0 "
           "source=%s slots=%d"),
      *ScreenState, WindowPx.X, WindowPx.Y, bVisible ? 1 : 0, *Source, UmGameSlotCount));
}

// VS-2 HB-06 (docs/game-design/visual/06-tasks/hud.csv HB-06; 04-hud-spec.md §1.6, §4.2, §4.3, §5.2 step H2): the GAME
// screen of the UMG HUD - UUmGameHud (/Game/S08/UI/Hud/WBP_UI_SCR_GAME), a canvas with one sized slot per block of
// 04 §4.2. The slots take their rects from FUmHudLayout (UmHudLayout.h); the blocks move in step by step (H4-H12) -
// until then a slot is empty, HitTestInvisible and paints nothing. See UmHudRoot.h for the root around it.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../S08ArtHudWidgets.h"
#include "UmHudLayout.h"
#include "UmGameHud.generated.h"

class UCanvasPanel;
class USizeBox;

/** The blocks of the GAME screen as UUmGameHud slots (04 §4.2 order). */
enum class EUmGameSlot : uint8 {
  Top,
  Status,
  PanelLoc,
  PanelOpp,
  OppHand,
  Hand,
  Decks,
  DeckPanel,
  Actions,
  CombatCenter,
  CombatEdgeL,
  CombatEdgeR,
  Pending,
  SourceSlot,
  Log,
  Banner,
  Toast,
  Sub,
  Num
};
constexpr int32 UmGameSlotCount = static_cast<int32>(EUmGameSlot::Num);

namespace UmGameHudSlots {
/** BindWidget name of a slot: "Top", "Status", ... */
UNMATCHED_API const TCHAR* SlotName(EUmGameSlot Slot);
/** The layout rect that places a slot (Hand = the row with its caption; the combat edges with the ribbon). */
UNMATCHED_API FBox2D SlotRect(const FUmHudLayout& Layout, EUmGameSlot Slot);
/** The -S08SlateHud key of a slot (S08ArtLook::SlateHudKeys). */
UNMATCHED_API FName SlotKey(EUmGameSlot Slot);
/** VS-2 HB-14...HB-16: the generated class of the WBP at Package (/Game/.../WBP_X) when the asset exists, else Native
 *  (the code default tree) - the blocks and their nested widgets are created through it. */
UNMATCHED_API UClass* WbpOrNative(UClass* Native, const TCHAR* Package);
/** VS-2 HB-15: a slot whose height follows its block (STATUS: one line 48 su, two lines 78 su); the width stays the
 *  layout rect's (the block centres itself in it). */
UNMATCHED_API bool HeightFollowsBlock(EUmGameSlot Slot);
/** The widget's own visibility property shows it (Visible / HitTestInvisible / SelfHitTestInvisible) and it is not
 *  transparent - UWidget::IsVisible needs a constructed Slate widget, a SHOT line also comes from tests. */
UNMATCHED_API bool ShownByProperty(const UWidget* Widget);
}  // namespace UmGameHudSlots

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmGameHud : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Hud/WBP_UI_SCR_GAME

  virtual bool Initialize() override;
  /** Canvas "Canvas" > one USizeBox per slot (names = UmGameHudSlots::SlotName). */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  /** Places every slot at its layout rect (su); a slot whose block is still on the Slate path (SlateKeys) or has no
   *  rect in this class (LOG in S) is collapsed. Event only: a window / scale change or a new FIELD. */
  void ApplyLayout(const FUmHudLayout& InLayout, const TArray<FName>& SlateKeys, bool bAllSlate = false);
  const FUmHudLayout& GetLayout() const { return Layout; }
  USizeBox* GetSlot(EUmGameSlot Which) const;
  /** VS-2 HB-14...HB-16: puts a block into its slot (once; the slot is placed by the next ApplyLayout). */
  bool SetBlock(EUmGameSlot Which, UWidget* Block);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  /** UI-SCR-GAME state of the gate (own | opp | combat | pending | over). */
  void SetScreenState(const FString& InState) { ScreenState = InState; }
  /** "SHOT widget id=UI-SCR-GAME impl=umg state=.. fighter=none bbox=0,0,W,H geom=painted visible=1 twin=0 source=..":
   *  the screen line of the gate (04 §1.6); an empty slot writes nothing (its block is still Slate or not built yet). */
  void CollectShotLines(TArray<FString>& Out, const FIntPoint& WindowPx) const;

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UCanvasPanel> Canvas;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> Top;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> Status;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> PanelLoc;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> PanelOpp;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> OppHand;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> Hand;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> Decks;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> DeckPanel;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> Actions;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> CombatCenter;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> CombatEdgeL;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> CombatEdgeR;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> Pending;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> SourceSlot;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> Log;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> Banner;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> Toast;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> Sub;

 private:
  void BindSlotsFromTree();
  FUmHudLayout Layout;
  FString ScreenState = TEXT("own");
  bool bCodeDefaultTree = false;
};

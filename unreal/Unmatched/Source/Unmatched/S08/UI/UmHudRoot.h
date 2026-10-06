// VS-2 HB-06 (docs/game-design/visual/06-tasks/hud.csv HB-06; 04-hud-spec.md §4.1-§4.3, §5.2 step H2; ВР-36, ВР-H14,
// ВР-H15; HUD-RULES П1, П2, П7): the root of the UMG HUD and the GAME screen.
//
//   UUmHudRoot  (/Game/S08/UI/Root/WBP_UmHudRoot)  one per viewport, layer 1 (the HUD layer of 04 §1)
//   ├─ Screens  UWidgetSwitcher   - the route screens; step H2 holds the GAME screen only (UUmGameHud)
//   ├─ Modals   UOverlay          - INSPECT, PAUSE, GAMEOVER, ABORTED, confirm (H13-H16)
//   └─ Reconnect UNamedSlot       - RECONNECT (H14)
//   UUmGameHud  (/Game/S08/UI/Hud/WBP_UI_SCR_GAME) a canvas with one sized slot per block of 04 §4.2 (BindWidgetOptional):
//               the blocks move in step by step (H4-H12); until then a slot is empty and costs nothing.
//
// Both classes build their tree in code when used without a WBP (BuildDefaultTree: fresh worktree, tests); the WBPs
// are authored from the same function (tools/s08/hud_contract/ue_author_um_hud.py). Nothing here takes the mouse:
// every container is SelfHitTestInvisible, the empty slots HitTestInvisible - the Slate HUD and the board keep their
// input. Data comes in only by call (ApplyLayout, SetScreenState) - no property binding, no tick (П2).
// The -S08SlateHud rollback (S08ArtLook::SlateHudBlocks) does not create the root at all.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../S08ArtHudWidgets.h"
#include "UmHudLayout.h"
#include "UmHudRoot.generated.h"

class UCanvasPanel;
class UNamedSlot;
class UOverlay;
class USizeBox;
class UWidgetSwitcher;
class UUmGameHud;

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmHudRoot : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Root/WBP_UmHudRoot

  virtual bool Initialize() override;
  /** Overlay "RootOverlay" > Screens, Modals, Reconnect (names = BindWidget names). */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  /** The WBP's generated class when the asset exists, else the native class (code default tree). OutSource: the WBP
   *  path or "code-default". */
  static UUmHudRoot* Create(UWorld* World, FString* OutSource = nullptr);
  /** The GAME screen inside Screens (created on the first call from WBP_UI_SCR_GAME or the native class). */
  UUmGameHud* EnsureGameHud();
  UUmGameHud* GetGameHud() const { return GameHud; }
  /** Every BindWidget part bound (false = broken tree; OutMissing lists them). */
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UWidgetSwitcher> Screens;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UOverlay> Modals;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UNamedSlot> Reconnect;

 private:
  UPROPERTY()
  TObjectPtr<UUmGameHud> GameHud;
  bool bCodeDefaultTree = false;
};

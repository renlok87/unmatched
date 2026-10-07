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
#include "GenericPlatform/ICursor.h"
#include "../S08ArtHudWidgets.h"
#include "UmHudLayout.h"
#include "UmHudRoot.generated.h"

class UCanvasPanel;
class UInvalidationBox;
class UNamedSlot;
class UOverlay;
class USizeBox;
class UWidgetSwitcher;
class UUmCursor;
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
  /** The GAME screen inside Screens (created on the first call from WBP_UI_SCR_GAME or the native class). VS-5 E4 (HUD-RULES
   *  П8, VS-4 «Открыто» п. 2): the screen sits in an invalidation box (UInvalidationBox, the Slate fast path) - its paint,
   *  prepass and hit-test entries are cached and only the widgets that changed repaint; rollback -S08HudNoCache. */
  UUmGameHud* EnsureGameHud();
  /** The cache box around GAME (null with -S08HudNoCache or before EnsureGameHud). */
  UInvalidationBox* GetGameCache() const { return GameCache; }
  /** False with -S08HudNoCache (the GAME screen straight in Screens, as before VS-5). */
  static bool CacheWanted();
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

  // ---- VS-2 HB-12: software cursors (04 §3.2; §4.2 UUmCursor under the root; UmCursor.h) ----
  /** One UUmCursor (WBP_UmCursor or the code tree) per UmCursor::RegisteredTypes(), registered on the game viewport
   *  (UGameViewportClient::SetSoftwareCursorWidget). The caller skips it with -S08SlateHud=cursor (system cursor). */
  bool InstallCursors(FString* OutSource = nullptr);
  /** Unregisters the cursor widgets (end of play). */
  void UninstallCursors();
  bool HasCursors() const { return Cursors.Num() > 0; }
  /** Per frame: Busy (a command in flight) overrides the three shapes; the texture size follows DPI x UI scale; the
   *  busy loop frame comes from NowSeconds (frame 0 with reduced motion). */
  void TickCursors(bool bBusy, double NowSeconds);
  /** 'HUD-CURSOR state=default|pointer|denied|busy|none ...' - the shape Slate drew in the last frames. */
  FString CursorShotLine(EMouseCursor::Type GameCursor) const;
  const TArray<TObjectPtr<UUmCursor>>& GetCursors() const { return Cursors; }

 private:
  UPROPERTY()
  TObjectPtr<UUmGameHud> GameHud;
  UPROPERTY()
  TObjectPtr<UInvalidationBox> GameCache;
  UPROPERTY()
  TArray<TObjectPtr<UUmCursor>> Cursors;
  FString CursorSource;
  double BusySince = -1.0;
  bool bCodeDefaultTree = false;
};

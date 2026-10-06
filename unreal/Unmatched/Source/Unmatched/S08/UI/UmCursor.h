// VS-2 HB-12 (docs/game-design/visual/06-tasks/hud.csv HB-12; 04-hud-spec.md §3.2, §4.2; 02-visual-design.md §4.4,
// ВР-46; cursor cards IC-58...IC-61 of icons.csv): the software cursors of the UMG HUD - UUmCursor
// (/Game/S08/UI/Common/WBP_UmCursor), four shapes drawn by the v3 engine (art/imagegen/hud-icons-v3, accepted by
// delegation in VS-2 A2 / A3).
//
//   shapes    Default (the arrow, IC-58), Pointer (the hand, IC-59: buttons, cards, own figures, lit cells), Denied (the
//             arrow with the small X, IC-60: a disabled element, with its why.*), Busy (the hourglass, IC-61: a command
//             in flight, V-10 - an 8-frame loop of 1500 ms, frame 0 with reduced motion).
//   mapping   one UUmCursor per registered EMouseCursor (UGameViewportClient::SetSoftwareCursorWidget):
//             Default -> Default, Hand -> Pointer, SlashedCircle -> Denied. Busy overrides the form: while a command is in
//             flight (AS08FlowGameMode::HudBusyReason = why.syncing) all three show the hourglass.
//   who sets  UUmButton: Hand, SlashedCircle when disabled; the Slate HUD presses (MakeHudPress: buttons, hand cards,
//             deck controls) the same; the board: Hand over an own figure and a lit (reachable) cell, else Default
//             (the player controller's CurrentMouseCursor, UmCursor::BoardCursor). UUmCardWidget sets it when CP-15 lands.
//   size      the texture of the screen px (HB-23): the smallest of 24 / 32 / 48 / 64 >= 32 su x DPI x UI scale - 32 px
//             at 100 %, 24 at 720p, 48 at 150 %, 64 at 4K; drawn 1 : 1 (Slate paints a cursor widget unscaled).
//   hot spot  Slate centres a cursor widget on the pointer (FSlateUser::DrawCursor), so the widget is 2 px x 2 px and
//             the image sits at (px - hx, px - hy): the hot-spot pixel of cursor-hotspots.json covers the pointer
//             pixel. Hot spots: Config/Cursors/S08CursorHotspots.json (tools/art/hud_skins_import.py --cursors).
//   textures  /Game/S08/UI/Cursors/T_Cursor_<Default|Pointer|Denied|Busy_NN><""|_24|_48|_x2> (ВР-VS2-27).
//   trace     at every evidence shot 'HUD-CURSOR state=default|pointer|denied|busy|none ...' (UUmHudRoot::CursorShotLine).
//   rollback  -S08SlateHud=cursor (or the whole -S08SlateHud): nothing is registered - the system cursor as before.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "GenericPlatform/ICursor.h"
#include "../S08ArtHudWidgets.h"
#include "UmCursor.generated.h"

class UImage;
class USizeBox;
class UTexture2D;

enum class EUmCursor : uint8 { Default, Pointer, Denied, Busy };

namespace UmCursor {
/** 'default' / 'pointer' / 'denied' / 'busy'. */
UNMATCHED_API const TCHAR* Name(EUmCursor Shape);
/** The asset state name: Default, Pointer, Denied, Busy. */
UNMATCHED_API const TCHAR* StateName(EUmCursor Shape);
/** The three EMouseCursor types the HUD registers (Default, Hand, SlashedCircle). */
UNMATCHED_API const TArray<EMouseCursor::Type>& RegisteredTypes();
/** The base shape of an EMouseCursor (anything not registered draws the arrow). */
UNMATCHED_API EUmCursor BaseShape(EMouseCursor::Type Type);
/** The drawn shape: Busy overrides every base while a command is in flight. */
UNMATCHED_API EUmCursor Resolve(EMouseCursor::Type Type, bool bBusy);
/** The board cursor of the player controller: Hand over an own figure or a lit cell, else Default. */
UNMATCHED_API EMouseCursor::Type BoardCursor(bool bOwnFighter, bool bLitCell);
/** Texture px for DPI x UI scale (px per su): the smallest of 24 / 32 / 48 / 64 >= 32 x PxPerSu, at most 64. */
UNMATCHED_API int32 SizePx(float PxPerSu);
/** Texture object path, e.g. /Game/S08/UI/Cursors/T_Cursor_Busy_03_48.T_Cursor_Busy_03_48 (Frame only for Busy). */
UNMATCHED_API FString TexturePath(EUmCursor Shape, int32 Px, int32 Frame = 0);
/** Busy loop: 8 frames over 1500 ms (the hourglass of state-sent: f04 is the 90° turn), frame 0 with reduced motion. */
inline constexpr int32 BusyFrames = 8;
inline constexpr double BusyCycleMs = 1500.0;
UNMATCHED_API int32 BusyFrame(double MsSinceBusy, bool bReduced);
/** Hot spot (px from the top left) of a shape at a size from Config/Cursors/S08CursorHotspots.json; false when the file
 *  or the entry is missing (the caller then uses the top left). */
UNMATCHED_API bool Hotspot(EUmCursor Shape, int32 Px, FIntPoint& Out);
/** The hot-spot file (project Config) and a test override; Reload clears the cache. */
UNMATCHED_API FString HotspotsPath();
UNMATCHED_API void ReloadHotspots();
/** The offset of the image inside the 2 px x 2 px widget so the hot spot lands on the centre (the pointer). */
UNMATCHED_API FVector2D ImageOffset(int32 Px, const FIntPoint& Hotspot);
}  // namespace UmCursor

/** The board half of the cursor (the player controller's CurrentMouseCursor, 04 §3.2): the board is picked again only
 *  when the pointer moved or RepickFrames passed (a selection or a move changes what is under a still pointer). */
struct UNMATCHED_API FUmBoardCursor {
  static constexpr uint64 RepickFrames = 10;
  FVector2D Mouse = FVector2D(-1.0, -1.0);
  uint64 Frame = 0;
  EMouseCursor::Type Cursor = EMouseCursor::Default;
  bool NeedsPick(const FVector2D& InMouse, uint64 InFrame) const {
    return Frame == 0 || !InMouse.Equals(Mouse, 0.5) || InFrame >= Frame + RepickFrames;
  }
  EMouseCursor::Type Store(const FVector2D& InMouse, uint64 InFrame, bool bOwnFighter, bool bLitCell) {
    Mouse = InMouse;
    Frame = InFrame;
    Cursor = UmCursor::BoardCursor(bOwnFighter, bLitCell);
    return Cursor;
  }
};

namespace UmCursor {
/** The shot line of the rollback: 'HUD-CURSOR state=system impl=system reason=<flag>'. */
UNMATCHED_API FString SystemShotLine(const TCHAR* Reason);
}  // namespace UmCursor

/** What one cursor widget draws now. */
struct UNMATCHED_API FUmCursorModel {
  bool bBusy = false;
  int32 Px = 32;
  int32 BusyFrame = 0;
};

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmCursor : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Common/WBP_UmCursor

  virtual bool Initialize() override;
  /** SizeBox "Box" (2 px x 2 px) > Image "Image" (px x px, top left at the hot-spot offset). */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  /** The WBP's generated class when the asset exists, else the native class; OutSource: the WBP path or "code-default". */
  static UUmCursor* Create(UObject* Outer, FString* OutSource = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }

  /** The EMouseCursor this widget is registered for (its base shape). */
  void SetCursorType(EMouseCursor::Type InType);
  EMouseCursor::Type GetCursorType() const { return CursorType; }
  /** The one data input (П1): same model again = no work. */
  void ApplyModel(const FUmCursorModel& InModel);
  const FUmCursorModel& GetModel() const { return Model; }

  EUmCursor GetShown() const { return Shown; }
  FIntPoint GetHotspot() const { return HotspotPx; }
  /** The drawn texture (null when the asset is missing - nothing is drawn then, the error is logged once). */
  const UTexture2D* GetTexture() const { return Texture; }
  /** GFrameCounter of the last paint (0 = never drawn): Slate paints only the cursor widget of the current shape. */
  uint64 GetLastPaintFrame() const { return LastPaintFrame; }

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<USizeBox> Box;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UImage> Image;

 protected:
  virtual int32 NativePaint(const FPaintArgs& Args, const FGeometry& AllottedGeometry, const FSlateRect& MyCullingRect,
                            FSlateWindowElementList& OutDrawElements, int32 LayerId, const FWidgetStyle& InWidgetStyle,
                            bool bParentEnabled) const override;

 private:
  void Restyle();

  EMouseCursor::Type CursorType = EMouseCursor::Default;
  FUmCursorModel Model;
  bool bHasModel = false;
  EUmCursor Shown = EUmCursor::Default;
  FIntPoint HotspotPx = FIntPoint::ZeroValue;
  UPROPERTY(Transient)
  TObjectPtr<UTexture2D> Texture;
  mutable uint64 LastPaintFrame = 0;
  bool bCodeDefaultTree = false;
};

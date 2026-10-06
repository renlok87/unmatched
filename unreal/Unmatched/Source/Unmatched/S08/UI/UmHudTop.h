// VS-2 HB-14 (docs/game-design/visual/06-tasks/hud.csv HB-14; 04-hud-spec.md §2.1, §4.2, §4.3, §5.2 step H6, §7.1;
// ВР-H07, ВР-H17; CX-08 mockup art/imagegen/hud-topstrip-v1-codex, accepted by delegation): TOP - UUmHudTop
// (/Game/S08/UI/Hud/WBP_UI_HUD_TOP), the small block in the top-left corner: menu, connection, turn number.
//
//   layout   one panel plate (T_Skin_Panel) at the TOP slot: L (24, 24, 252, 44), S (16, 16, 236, 40) - no strip over
//            the whole width (ВР-H17). Inside, left to right: MenuButton (44 / 40 square), Conn (UUmConnectionBadge,
//            the same square, icon 24 su), TurnText «Ход {n}» (type.button, not caps), LogButton (class S only, 40).
//   buttons  ВР-VS2-42: the glyphs ui-menu (IC-53) and ui-log (IC-55) on flat UUmButtons (no body at rest, CX-08), the
//            words hud.top.menu / hud.top.log as their tooltips; a glyph that does not load falls back to the word
//            (ВР-HB08, trace 'ICON missing=<id> block=UI-HUD-TOP'). The owner wires the presses (SetPress): the menu is
//            Esc without a selection -> PAUSE, the log button opens the LOG list of class S (ВР-H07).
//   data     ApplyModel(FUmTopModel): FS09HudModel::TurnCount and the connection state - an applied snapshot or a
//            change of the link, no tick for data (П2); same model = no work.
// The phase text and the RECONNECT overlay are not here (dont of HB-14).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../S08ArtHud.h"
#include "../S08ArtHudWidgets.h"
#include "UmConnectionBadge.h"
#include "UmHudTop.generated.h"

class UBorder;
class UHorizontalBox;
class UTextBlock;
class UUmButton;

struct UNMATCHED_API FUmTopModel {
  /** FS09HudModel::TurnCount; <= 0 = no turn yet (the text is hidden). */
  int32 TurnCount = 0;
  EUmConnState Conn = EUmConnState::Online;
  /** Layout class S (ВР-H01): 40 su squares and the «Журнал» button. */
  bool bClassS = false;
  /** DPI x UI scale (the x2 plate skin from 1.5, HB-10). */
  float PxPerSu = 1.0f;

  bool operator==(const FUmTopModel& O) const {
    return TurnCount == O.TurnCount && Conn == O.Conn && bClassS == O.bClassS && PxPerSu == O.PxPerSu;
  }
};

namespace UmHudTop {
/** 04 §2.1: the squares of the menu, the chip and the log button. */
inline constexpr float SquareLSu = 44.0f;
inline constexpr float SquareSSu = 40.0f;
inline float SquareSu(bool bClassS) { return bClassS ? SquareSSu : SquareLSu; }
/** hud.top.turn «Ход {n}» (no caps). */
UNMATCHED_API FText TurnText(int32 TurnCount);
/** The glyphs of the two buttons (v3, IC-53 / IC-55). */
inline const TCHAR* const MenuIcon = TEXT("ui-menu");
inline const TCHAR* const LogIcon = TEXT("ui-log");
}  // namespace UmHudTop

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmHudTop : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Hud/WBP_UI_HUD_TOP

  virtual bool Initialize() override;
  /** Border "Plate" > HorizontalBox "Row" > MenuButton (UUmButton), Conn (UUmConnectionBadge), TurnText, LogButton. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  /** The WBP's generated class when the asset exists, else the native class. */
  static UClass* WidgetClass();
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }

  /** The one data input (П1). */
  void ApplyModel(const FUmTopModel& InModel);
  const FUmTopModel& GetModel() const { return Model; }
  bool HasModel() const { return bHasModel; }
  /** The menu / log glyphs loaded (false = the word fallback of ВР-HB08). */
  bool HasMenuGlyph() const { return bMenuGlyph; }
  bool HasLogGlyph() const { return bLogGlyph; }
  /** "code-default" or the WBP path. */
  FString SourceName() const;
  /** 'SHOT widget id=UI-HUD-TOP state=idle ... turn=<n> class=L|S menu=<glyph|word> log=0|1' (Rect = the plate in
   *  viewport px) and the line of the connection chip (ConnRect). */
  void CollectShotLines(TArray<FString>& Out, const FS08ScreenRect& Rect, const FS08ScreenRect& ConnRect) const;

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UBorder> Plate;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UHorizontalBox> Row;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UUmButton> MenuButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UUmConnectionBadge> Conn;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UTextBlock> TurnText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UUmButton> LogButton;

 private:
  void ApplyButton(UUmButton* Button, const TCHAR* IconId, const TCHAR* LabelKey, float Square, bool& bOutGlyph);

  FUmTopModel Model;
  bool bHasModel = false;
  bool bMenuGlyph = false;
  bool bLogGlyph = false;
  bool bMissingTraced = false;
  bool bCodeDefaultTree = false;
};

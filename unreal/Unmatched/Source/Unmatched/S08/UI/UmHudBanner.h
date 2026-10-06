// VS-2 HB-16 (docs/game-design/visual/06-tasks/hud.csv HB-16; 04-hud-spec.md §2.4, §4.3, §5.2 step H5, §7.1; 02 §4.5;
// ВР-09, ВР-40, ВР-61; CUE-015; CX-08 mockup art/imagegen/hud-topstrip-v1-codex, accepted by delegation): the
// "ВАШ ХОД" banner - UUmHudBanner (/Game/S08/UI/Hud/WBP_UI_HUD_BANNER). It replaces the Slate TurnBanner
// (S08FlowGameModeTurnHud.cpp, #161A28, 30 pt; rollback -S08SlateHud=banner).
//
//   look     a plate (T_Skin_Panel: panel.bg 0.92, panel.edge) 420 x 64 su, «ВАШ ХОД» (hud.banner.own_turn) type.banner
//            36 su turn.flash.yellow, centred; no blot, stroke or splash (ВР-09).
//   place    the BANNER slot: centred, y 144 in L; y 72 in S - right under the one-line STATUS (ВР-VS2-45: at 112 / 144
//            the S plate covers the top row of cells).
//   time     the alpha IS FS09TurnCue::BannerAlpha (CUE-015: in 100 -> hold -> out 150, 600 ms; reduced 100 ms static;
//            the UI-ACC-013 speed does not scale it); the block has no animation of its own and is collapsed (no tick,
//            no paint) at alpha 0. Own turn only - FS09TurnCue never starts it in the opponent's turn.
//   input    HitTestInvisible: the board and the HUD take every click through it (SD-47).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09TurnHud.h"
#include "../S08ArtHud.h"
#include "../S08ArtHudWidgets.h"
#include "UmHudBanner.generated.h"

class UBorder;
class UTextBlock;

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmHudBanner : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Hud/WBP_UI_HUD_BANNER

  virtual bool Initialize() override;
  /** Border "Plate" > TextBlock "Text". */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  static UClass* WidgetClass();
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }

  /** The data input (П1): the opacity = Cue.BannerAlpha(NowMs); bShow false (the result screen) hides it. */
  void ApplyModel(const FS09TurnCue& Cue, double NowMs, bool bShow = true);
  /** The opacity applied (0 = collapsed). */
  float GetAlpha() const { return Alpha; }
  /** The x2 plate from 150 % (HB-10). */
  void SetPxPerSu(float InPxPerSu);
  FString SourceName() const;
  /** 'SHOT widget id=UI-HUD-BANNER state=shown ... alpha=<a>' while alpha > 0 (Rect = the plate, viewport px). */
  void CollectShotLines(TArray<FString>& Out, const FS08ScreenRect& Rect) const;

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UBorder> Plate;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UTextBlock> Text;

 private:
  float Alpha = 0.0f;
  float PxPerSu = 0.0f;
  bool bCodeDefaultTree = false;
};

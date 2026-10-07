// VS-3 HB-47 (hud.csv HB-47; 04-hud-spec.md §3.3, §1.1 the BOOT bar, §1.5 the match loading): the progress bar of the
// UMG HUD and the screens - UUmProgressBar, a UProgressBar 480 x 8 su with the theme skins (track progress.track:
// panel.bg.inset + panel.edge; fill progress.fill: card.cream - HB-08 / HB-10 9-slice, before the import the ВР-HB06
// brushes) and the stage caption under it (type.caption, text.secondary). A bar always has its stage caption: a bar
// shown without one for longer than 2 s is a defect (HasCaptionDefect, traced 'caption=0').
// Shown only after 300 ms of waiting (FUmDelayedShow); collapsed otherwise. The screens take it in VS-7 (BOOT, LOADING).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../S08ArtHudWidgets.h"
#include "UmSpinner.h"
#include "UmProgressBar.generated.h"

class UProgressBar;
class USizeBox;
class UTextBlock;

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmProgressBar : public UUserWidget {
  GENERATED_BODY()

 public:
  static constexpr float WidthSu = 480.0f;
  static constexpr float HeightSu = 8.0f;

  virtual bool Initialize() override;
  /** VerticalBox "Column" > SizeBox "BarBox" > UProgressBar "Bar"; TextBlock "Caption". */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;

  /** The value 0..1 and the stage caption (screens.boot.stage.*, screens.loading.*). */
  void ApplyModel(float Percent, const FText& Stage, double NowMs);
  /** The wait at NowMs: shown after 300 ms, hidden at once. The HUD-LOADER line on a change. */
  FString SetWaiting(bool bWaiting, double NowMs, const TCHAR* Where);
  bool IsShown() const { return bShown; }
  float GetPercent() const { return Percent; }
  /** Shown without a stage caption for longer than 2 s at NowMs. */
  bool HasCaptionDefect(double NowMs) const;

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UProgressBar> Bar;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> Caption;

 private:
  void ApplyStyle();
  FUmDelayedShow Delay;
  bool bShown = false;
  float Percent = 0.0f;
  bool bHasCaption = false;
  double NoCaptionSinceMs = -1.0;
};

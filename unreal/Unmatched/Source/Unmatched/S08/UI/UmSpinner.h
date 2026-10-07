// VS-3 HB-47 (docs/game-design/visual/06-tasks/hud.csv HB-47; 04-hud-spec.md §3.3, §1.1, §1.3; 02 §11.2; icon IC-16
// loader-spinner): the loaders of the UMG HUD and the screens.
//
//   FUmDelayedShow  04 §3.3: a wait shows its indicator only after 300 ms; ready hides it at once. World-free, the
//                   owner polls it with its clock (a hidden loader has no tick of its own).
//   UUmSpinner      /Game/S08/UI/Common/WBP_UmSpinner: the v3 loader-spinner (US08AnimatedIconWidget, contract
//                   icon-motion.json `cycle`: 8 steps of icon.spinner.step.ms 125, reduced 250 - the contract's reduced
//                   branch) at 32 or 48 su. Collapsed while hidden (Slate does not tick a collapsed widget: 0 ticks).
//   UUmProgressBar  UmProgressBar.h - UProgressBar 480 x 8 with the theme skins progress.track / progress.fill and the
//                   stage caption (a progress without its caption longer than 2 s is a defect).
//   UUmSkeletonRows UmSkeletonRows.h - N rows panel.bg.inset with the opacity pulse 0.6 <-> 1.0 in 900 ms (reduced:
//                   static), the deck panel before gameDeckLists answers (HB-28: 6 rows).
// Trace (by the owner, on a change): 'HUD-LOADER kind=spinner|progress|skeleton shown=0|1 where=<owner> waitMs=<ms>
// reduced=0|1'.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Styling/SlateBrush.h"
#include "../S08ArtHudWidgets.h"
#include "UmSpinner.generated.h"

class USizeBox;
class US08AnimatedIconWidget;

/** 04 §3.3: the indicator of a wait shows after 300 ms of waiting and hides as soon as it is ready. */
struct UNMATCHED_API FUmDelayedShow {
  static constexpr double DelayMs = 300.0;
  /** The wait starts at NowMs (a running wait keeps its start). */
  void Begin(double NowMs) {
    if (StartMs < 0.0) StartMs = NowMs;
  }
  /** Ready (or cancelled): hidden at once, the next Begin starts a new wait. */
  void End() { StartMs = -1.0; }
  bool IsWaiting() const { return StartMs >= 0.0; }
  double WaitedMs(double NowMs) const { return StartMs >= 0.0 ? FMath::Max(0.0, NowMs - StartMs) : 0.0; }
  /** Shown at NowMs: waiting for at least DelayMs. */
  bool IsShown(double NowMs) const { return StartMs >= 0.0 && NowMs - StartMs >= DelayMs; }
  double StartMs = -1.0;
};

namespace UmLoader {
enum class EKind : uint8 { Spinner, Progress, Skeleton };
UNMATCHED_API const TCHAR* KindName(EKind Kind);
/** 'HUD-LOADER kind=<k> shown=0|1 where=<owner> waitMs=<ms> reduced=0|1' */
UNMATCHED_API FString TraceLine(EKind Kind, bool bShown, const TCHAR* Where, double WaitMs, bool bReduced);
/** The spinner sizes of 04 §3.3 (su). */
inline constexpr float SpinnerSmallSu = 32.0f;
inline constexpr float SpinnerLargeSu = 48.0f;
/** The skeleton pulse (04 §3.3): opacity 0.6 <-> 1.0, one period 900 ms (a cosine from 1.0); reduced - static. */
inline constexpr float SkeletonPeriodMs = 900.0f;
inline constexpr float SkeletonLow = 0.6f;
inline constexpr float SkeletonHigh = 1.0f;
/** ВР-VS3-34: the static reduced-motion skeleton stands at the middle of the pulse. */
inline constexpr float SkeletonReduced = 0.8f;
UNMATCHED_API float SkeletonOpacity(double TMs, bool bReduced);
/** A plain 1 x 1 su image brush: the divider line of a skeleton or a list row (the default UImage brush is 32 su). */
UNMATCHED_API FSlateBrush LineBrush();
/** The progress bar's stage caption may be missing for at most this long (HB-47 readability: 2 s). */
inline constexpr double CaptionGraceMs = 2000.0;
}  // namespace UmLoader

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmSpinner : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Common/WBP_UmSpinner
  static UClass* WidgetClass();

  virtual bool Initialize() override;
  /** SizeBox "Box" > US08AnimatedIconWidget "Icon" (loader-spinner). */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }

  /** 32 or 48 su (04 §3.3); the texture follows DPI x UI scale (HB-23). */
  void SetSizeSu(float Su);
  float GetSizeSu() const { return SizeSu; }
  /** The wait at NowMs (ms, the owner's clock): shown after 300 ms, hidden at once when !bWaiting. Returns the
   *  HUD-LOADER line when the shown state changed, '' otherwise. */
  FString SetWaiting(bool bWaiting, double NowMs, const TCHAR* Where);
  bool IsShown() const { return bShown; }
  const FUmDelayedShow& GetDelay() const { return Delay; }
  /** NativeTick calls (HB-47 budget: 0 while hidden - a collapsed widget is not ticked). */
  int32 GetTickCount() const { return TickCount; }
  void SetReducedForTest(int32 InReduced) { ReducedOverride = InReduced; }
  bool IsReduced() const;

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<USizeBox> Box;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<US08AnimatedIconWidget> Icon;

 protected:
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

 private:
  void ApplyIcon();
  FUmDelayedShow Delay;
  bool bShown = false;
  float SizeSu = UmLoader::SpinnerSmallSu;
  int32 TickCount = 0;
  int32 ReducedOverride = -1;
  bool bCodeDefaultTree = false;
};

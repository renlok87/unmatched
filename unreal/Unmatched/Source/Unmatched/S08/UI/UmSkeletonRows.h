// VS-3 HB-47 (hud.csv HB-47; 04-hud-spec.md §3.3, §1.3): the row skeleton - N rows of panel.bg.inset with the
// panel.divider line under each, the whole block pulsing its opacity 0.6 <-> 1.0 in 900 ms (reduced motion: static at
// 0.8, ВР-VS3-34). Shown only after 300 ms of waiting (FUmDelayedShow, UmSpinner.h); collapsed (no tick) otherwise.
// Users: the deck panel before gameDeckLists answers (HB-28: 6 rows), the LOBBY list (04 §1.3, screens).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../S08ArtHudWidgets.h"
#include "UmSpinner.h"
#include "UmSkeletonRows.generated.h"

class UImage;
class UVerticalBox;

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmSkeletonRows : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  /** VerticalBox "Rows" (the rows are pooled children: a SizeBox with the inset cell and its divider). */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;

  /** N rows of RowSu (48 su in the deck panel). */
  void SetRows(int32 N, float RowSu);
  int32 GetRowCount() const { return RowCount; }
  /** The wait at NowMs (ms): shown after 300 ms, hidden at once when !bWaiting. The HUD-LOADER line on a change. */
  FString SetWaiting(bool bWaiting, double NowMs, const TCHAR* Where);
  bool IsShown() const { return bShown; }
  /** The pulse at NowMs of the widget clock (FPlatformTime or the override; the tick drives it while shown). */
  void StepPulse(double NowMs);
  float GetPulseOpacity() const { return PulseNow; }
  void SetClockOverrideMs(double Ms) { ClockOverrideMs = Ms; }
  void SetReducedForTest(int32 InReduced) { ReducedOverride = InReduced; }
  bool IsReduced() const;
  int32 GetTickCount() const { return TickCount; }

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UVerticalBox> Rows;

 protected:
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

 private:
  double NowMs() const;
  FUmDelayedShow Delay;
  bool bShown = false;
  int32 RowCount = 0;
  float RowSu = 48.0f;
  float PulseNow = 1.0f;
  double ShownAtMs = 0.0;
  double ClockOverrideMs = -1.0;
  int32 ReducedOverride = -1;
  int32 TickCount = 0;
};

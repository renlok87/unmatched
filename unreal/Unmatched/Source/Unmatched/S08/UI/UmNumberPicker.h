// VS-4 HB-35 (docs/game-design/visual/06-tasks/hud.csv HB-35 p. 2; 04-hud-spec.md §2.8 «Число ▲▼», §4.2; IC-56 ui-step;
// the accepted mockup HB-34 art/imagegen/hud-pending-v1-codex - the number picker is geometry only on its overlay sheets,
// ВР-VS2-HB34-03): the number choice of a deferred effect - UUmNumberPicker, one widget inside UUmHudPending's body:
//
//   row 1    «▲» (UUmButton, icon-only, the v3 glyph ui-step 24 su, IC-56), the value (type.title 28 su, tabular
//            font.card digits), «▼» (the same glyph turned 180° in UMG - IC-56 has no second texture);
//   row 2    «Подтвердить» (primary, hud.number.confirm) and «Отмена» (ms.btn.cancel);
//   row 3    the result plate (panel.inset, type.body): what the chosen number does (the owner's text).
//
// The MVP decks have no number choice (ВР-HB11, s05-registry.spec.ts): the picker is driven by the tests and the review
// sheet only, the live game never opens it today. The value is clamped to [Min, Max]: ▲ at Max / ▼ at Min still take the
// press (the value stays; no silently disabled button, 04 §3.1).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudPress.h"
#include "../S08ArtHudWidgets.h"
#include "UmNumberPicker.generated.h"

class UBorder;
class UCanvasPanel;
class UTextBlock;
class UUmButton;

struct UNMATCHED_API FUmNumberModel {
  int32 Min = 0;
  int32 Max = 0;
  int32 Value = 0;
  /** The result plate (the owner's text; '' = no plate). */
  FString Result;
  /** Why «Подтвердить» refuses (unset = enabled); a command in flight. */
  FS09Reason ConfirmWhy;
  bool operator==(const FUmNumberModel& O) const {
    return Min == O.Min && Max == O.Max && Value == O.Value && Result == O.Result && ConfirmWhy.Key == O.ConfirmWhy.Key;
  }
  bool operator!=(const FUmNumberModel& O) const { return !(*this == O); }
};

namespace UmNumberPicker {
inline constexpr float StepSu = 40.0f;      // the ▲ / ▼ buttons (40 su, 04 §3.1 panel buttons)
inline constexpr float GlyphSu = 24.0f;     // ui-step (IC-56)
inline constexpr float ValueWSu = 96.0f;    // the value cell
inline constexpr float RowGapSu = 8.0f;
inline constexpr float ResultHSu = 32.0f;
/** The picker's height (su): two rows of 40 + the result plate. */
UNMATCHED_API float HeightSu(bool bResult);
/** The value after a step (clamped to [Min, Max]). */
UNMATCHED_API int32 Stepped(const FUmNumberModel& Model, int32 Delta);
}  // namespace UmNumberPicker

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmNumberPicker : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  /** Canvas "Root" > UpButton, ValueText, DownButton, ConfirmButton, CancelButton, ResultPlate > ResultText. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;

  /** The one data input (П1); the same model = no work. Width = the room of the owner's body (su). */
  void ApplyModel(const FUmNumberModel& InModel, float WidthSu);
  const FUmNumberModel& GetModel() const { return Model; }
  /** OnStep(+1 / -1), OnConfirm, OnCancel answer a resolved press (the arbiter, DE-014). */
  void SetInput(const TSharedPtr<FS09HudPressArbiter>& InArbiter, TFunction<void(const FS09HudPressOutcome&, int32)> InOnStep,
                TFunction<void(const FS09HudPressOutcome&)> InOnConfirm, TFunction<void(const FS09HudPressOutcome&)> InOnCancel);
  /** "value=3 min=1 max=5 result=1" for the owner's SHOT line (no text). */
  FString Describe() const;

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UCanvasPanel> Root;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> UpButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> ValueText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> DownButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> ConfirmButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UUmButton> CancelButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UBorder> ResultPlate;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional)) TObjectPtr<UTextBlock> ResultText;

 private:
  FUmNumberModel Model;
  bool bHasModel = false;
  float WidthNow = 0.0f;
};

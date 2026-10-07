// VS-4 HB-40 (docs/game-design/visual/06-tasks/hud.csv HB-40; 04-hud-spec.md §2.12, §4.3, ВР-H06; 02 §4.5, ВР-66; the
// accepted mockup HB-38 art/imagegen/hud-feed-v1-codex, ВР-VS2-HB38-06 / -12): one toast - UUmToast
// (/Game/S08/UI/Common/WBP_UmToast), pooled by UUmToastStack.
//
//   look   info     T_Skin_Toast (panel.bg 0.92, panel.edge 1 su), no sign;
//          warning  T_Skin_ToastWarning (the 2 su state.warning edge), the «!» triangle state-warning (IC-47) 24 su left
//                   and, while it is held, the close cross ui-close (IC-54) 24 su right - the only part that takes the
//                   mouse (its tooltip ms.hint.close);
//          error    T_Skin_Toast with the X sign badge-refuse (IC-40) 24 su left.
//          Text type.body text.primary, padding 16 su, up to 2 lines (word wrap at the cap - never cut); the width is
//          the measured content (at the drawn scale) + the padding, at most 560 su (720p 520, class S 440); 48 su for
//          one line, 16 + 20 x (n - 1) + 2 x 12 for more (HB-38 toast_spec). The three kinds differ by shape in grey.
//   input  never focusable; the body is HitTestInvisible, only the cross is a button (through the HUD press arbiter).
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudPress.h"
#include "../S08ArtHudWidgets.h"
#include "UmHudFeed.h"
#include "UmToast.generated.h"

class UBorder;
class UHorizontalBox;
class USizeBox;
class UTextBlock;
class UUmButton;
class US08AnimatedIconWidget;

/** What a toast shows (FUmToastSpec of the card: Kind, Text, Hold, bSticky). */
struct UNMATCHED_API FUmToastSpec {
  EUmToastKind Kind = EUmToastKind::Info;
  FText Text;
  /** Requested hold (s); the stack applies UmHudFeed::HoldSec. */
  float HoldSec = 3.0f;
  /** Held until its close / the owner's dismiss (the hand-limit rule, DE-024). */
  bool bSticky = false;
  /** The string key (trace, de-duplication; never the text in a trace). */
  FName Key;
  bool SameAs(const FUmToastSpec& O) const { return Kind == O.Kind && Key == O.Key && Text.EqualTo(O.Text) && bSticky == O.bSticky; }
};

/** The size of a toast and its text box (su). */
struct UNMATCHED_API FUmToastPlan {
  FVector2D SizeSu = FVector2D(0.0, UmHudFeed::ToastMinHSu);
  float TextWidthSu = 0.0f;
  int32 Lines = 1;
  bool bSign = false;
  bool bClose = false;
};

namespace UmToast {
using FMeasure = TFunctionRef<float(const FString& Text, float SizeSu)>;
/** The plan of a spec under CapSu (the text wraps at the cap minus padding, sign and cross). */
UNMATCHED_API FUmToastPlan Plan(const FUmToastSpec& Spec, float CapSu, FMeasure Measure);
/** The v3 icon of the sign (NAME_None for info). */
UNMATCHED_API FName SignIcon(EUmToastKind Kind);
/** The theme skin key of the body. */
UNMATCHED_API FName SkinKey(EUmToastKind Kind);
/** type.body measured at the drawn scale (DPI x UI scale), su; an estimate without a Slate renderer. */
UNMATCHED_API float MeasureBodySu(const FString& Text, float SizeSu, float PxPerSu);
inline constexpr float TextSlackSu = 6.0f;  // ВР-VS4-20: a measured line + 6 su never wraps by rounding
}  // namespace UmToast

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmToast : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Common/WBP_UmToast

  virtual bool Initialize() override;
  /** SizeBox "Box" > Border "Body" > HorizontalBox "Row" > SizeBox "SignBox" > Icon, TextBlock "Text", SizeBox
   *  "CloseBox" > UUmButton "CloseButton". */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  static UClass* WidgetClass();
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  FString SourceName() const;

  /** Shows Spec at Plan's size (the x2 skins from 150 %). */
  void ApplySpec(const FUmToastSpec& Spec, const FUmToastPlan& Plan, float PxPerSu);
  /** The close cross through the HUD press arbiter (DE-014); OnClose answers the release. */
  void SetClose(FName PressId, const TSharedPtr<FS09HudPressArbiter>& Arbiter, const FS09OnHudPressOutcome& OnClose);
  const FUmToastSpec& GetSpec() const { return Spec; }
  const FUmToastPlan& GetPlan() const { return PlanNow; }
  FName GetSignIcon() const;
  bool IsCloseShown() const;

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UBorder> Body;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<US08AnimatedIconWidget> Icon;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UTextBlock> Text;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UUmButton> CloseButton;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> Box;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<UHorizontalBox> Row;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> SignBox;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<USizeBox> CloseBox;

 private:
  void BindFromTree();
  FUmToastSpec Spec;
  FUmToastPlan PlanNow;
  float PxPerSu = 0.0f;
  bool bCodeDefaultTree = false;
};

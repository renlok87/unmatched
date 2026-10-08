// VS-2 HB-11 (docs/game-design/visual/06-tasks/hud.csv HB-11; 02-visual-design.md §4.3, ВР-65; 04-hud-spec.md §3.1,
// §2.14, §4.3; STYLE-v3 rule 9; UI-INP-011, DE-014, SD-46): the HUD button of the UMG HUD - UUmButton
// (/Game/S08/UI/Common/WBP_UmButton).
//
//   variants  Normal  - body btn.* skins, text text.primary (02 §4.3);
//             Primary - body btn.primary.* (turn.flash.yellow), text card.navy; never selected; one per window;
//             Disc    - the v3 pip 48 su (an action disc of ACTIONS, ВР-39) with its caption under it; the underlay is
//                       panel.bg.hover / panel.bg.pressed / state.pending, the disc itself scales (STYLE-v3 №9).
//                       VS-4 HB-43 (accepted mockup HB-42, ВР-VS2-HB42-03 / -12 / -13): the disc is a cell of its own with
//                       the HB-08 skin of its state (Btn_Normal / _Hover / _Pressed / _Disabled / _Selected; bDiscPrimary:
//                       BtnPrimary_* while enabled), the disc DiscSu (48 / 40) centred at y + 4, the caption on the row
//                       baseline y + 67, the key chip 20 x 20 su 2 su from the cell's top-right corner.
//   states    normal, hover, pressed, disabled (+ why.*), focus, selected; busy ("Отправлено…", hud.btn.sent).
//             Skins come from DA_UmHudTheme.Skins (HB-10: the 9-slice PNG, before the import the ВР-HB06 brushes);
//             disabled text is text.secondary, never an opacity (0.4 gives 3.4 : 1); selected text card.glyph.
//   motion    hover.ms 150 (disc / primary icon 1.06), icon.press.ms 80 (0.96; Normal: the text 1 su down), focus ring
//             100, selected glyph pulse 1.1 -> 1.0 in 200 ms; reduced motion - colour only. The body brush swaps in the
//             frame of the state change; only the scale / offset animate, and only while they move (no idle tick work).
//   press     on the release over the same element through FS09HudPressArbiter (S09HudPress.h) - unchanged rules: a
//             hold of 0 or 50 ms counts, a rebuild between press and release never loses the click (the arbiter is
//             keyed by the logical Id). A disabled or busy button still takes the press: the release answers Refused
//             with its why.* (the owner plays CUE-004 in that frame, UI-INP-011) - no silently disabled button.
//   why.*     after 300 ms of hover over a disabled / busy button its reason becomes the tooltip (ST_Why, RU default).
//   focus     drawn when the owner's keyboard navigation puts it there (model bFocused); the widget never takes the
//             keyboard (GameAndUI, HUD-RULES П7).
// The button writes no SHOT line of its own: DescribeState() goes into its owner block's line.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudPress.h"
#include "../S08ArtHudWidgets.h"
#include "UmButton.generated.h"

class UBorder;
class UGridPanel;
class UImage;
class USizeBox;
class UTextBlock;
class US08AnimatedIconWidget;

enum class EUmButtonVariant : uint8 { Normal, Primary, Disc };
/** The drawn state (one at a time; Focus = the ring over a normal body). */
enum class EUmButtonState : uint8 { Normal, Hover, Pressed, Disabled, Focus, Selected, Busy };

UNMATCHED_API const TCHAR* UmButtonVariantName(EUmButtonVariant Variant);
UNMATCHED_API const TCHAR* UmButtonStateName(EUmButtonState State);

struct UNMATCHED_API FUmButtonModel {
  EUmButtonVariant Variant = EUmButtonVariant::Normal;
  FText Label;
  /** v3 icon id (S08IconMotion), NAME_None = no icon (a disc needs one). */
  FName IconName;
  bool bEnabled = true;
  /** Why the button is disabled (or busy): the tooltip after 300 ms and the reason of the refused press. */
  FS09Reason Reason;
  bool bSelected = false;
  bool bBusy = false;
  /** Key chip text (UI-ACC-017, ВР-H09), empty = no chip. */
  FText KeyHint;
  /** Keyboard navigation focus (04 §3.4), set by the owner. */
  bool bFocused = false;
  /** 48 (primary, modal) / 40 (panels) / 32 (chips); 0 = the variant default (Normal 40, Primary 48, Disc 72). */
  float HeightSu = 0.0f;
  /** VS-2 HB-14: minimum width (su); 0 = the variant default (120, disc 80). The TOP buttons are squares 44 / 40. */
  float MinWidthSu = 0.0f;
  /** VS-2 HB-14 (CX-08): no body at rest - the button sits inside its block's plate (TOP «≡», «Журнал»); hover,
   *  pressed, disabled, selected and busy still draw their skin, focus its ring. Normal variant only. */
  bool bFlat = false;
  /** VS-3 HB-28 (HB-26 delta: the deck panel tabs text + 12 su, the filter text + 16 su): the label's side padding (su);
   *  0 = the variant default (space.m 16). */
  float PadXSu = 0.0f;
  /** VS-4 HB-43 (HB-42 ВР-VS2-HB42-03): a disc on the primary cell (BtnPrimary_* skins, caption card.navy) - only while
   *  enabled; a disabled one is an ordinary Btn_Disabled cell, never BtnPrimary_Disabled. Disc variant only. */
  bool bDiscPrimary = false;
  /** VS-4 HB-43: the disc side (su); 0 = 48 (class L), 40 in class S (HB-42 A2). Disc variant only. */
  float DiscSu = 0.0f;
  /** VS-4 HB-43: the owner block draws the why tooltip (the HB-22 plate of HB-42 A7), the button sets none. */
  bool bOwnerTooltip = false;
};

namespace UmButton {
/** The state drawn for a model and the pointer (busy > disabled > pressed > selected > hover > focus > normal;
 *  a primary is never selected). */
UNMATCHED_API EUmButtonState ResolveState(const FUmButtonModel& Model, bool bHovered, bool bPressed);
/** Theme skin key of the body (btn.normal, btn.primary.hover, ...). VS-4 HB-43 (HB-42 ВР-VS2-HB42-03): a disc is its
 *  own cell with the HB-08 skin of its state (Btn_Normal / _Hover / _Pressed / _Disabled / _Selected). */
UNMATCHED_API FName SkinKey(EUmButtonVariant Variant, EUmButtonState State);
/** The skin of a model in a state: a primary disc (bDiscPrimary) takes the BtnPrimary_* skins while enabled. */
UNMATCHED_API FName SkinKeyFor(const FUmButtonModel& Model, EUmButtonState State);
/** Theme colour token of the label. */
UNMATCHED_API FName TextColorToken(EUmButtonVariant Variant, EUmButtonState State);
/** The label colour of a model in a state: the caption of an enabled primary disc is card.navy. */
UNMATCHED_API FName TextColorTokenFor(const FUmButtonModel& Model, EUmButtonState State);
/** VS-4 HB-43 (04 §2.14, ВР-VS2-HB42-13): the disc caption's baseline from the cell top (su), every caption of the row
 *  on one line; the caption box top = this - the type.tag ascent. */
inline constexpr float DiscCaptionBaselineSu = 67.0f;
/** The disc's top inset in its cell (su): y + 4 in both classes (HB-42 A2). */
inline constexpr float DiscTopSu = 4.0f;
/** The key chip of a disc cell: 20 x 20 su, 2 su from the cell's top and right edges (ВР-VS2-HB42-08). */
inline constexpr float DiscChipSu = 20.0f;
inline constexpr float DiscChipInsetSu = 2.0f;
/** The type.tag ascent (su) at PxPerSu: the font measure when Slate runs, else Roboto's 1900 / 2048 of 14 su. */
UNMATCHED_API float TagAscentSu(float PxPerSu);
/** Theme colour token of a disc underlay (NAME_None = none). */
UNMATCHED_API FName DiscUnderlayToken(EUmButtonState State);
/** Target scale of the icon (disc / primary) and the body (primary pressed) - 1 with reduced motion. */
UNMATCHED_API float IconScale(EUmButtonVariant Variant, EUmButtonState State, bool bReduced);
UNMATCHED_API float BodyScale(EUmButtonVariant Variant, EUmButtonState State, bool bReduced);
/** Default height (su) of a variant. */
UNMATCHED_API float DefaultHeightSu(EUmButtonVariant Variant);
/** Minimum width (su): 120, disc 80 (04 §3.1). */
UNMATCHED_API float MinWidthSu(EUmButtonVariant Variant);
}  // namespace UmButton

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmButton : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Common/WBP_UmButton

  virtual bool Initialize() override;
  /** SizeBox "Box" > Overlay "Stack" > [Border "Body" > Grid "Content" > Icon, Label, KeyChip > KeyText] + FocusRing. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }

  /** The one data input (П1). Same model again = no work. */
  void ApplyModel(const FUmButtonModel& InModel);
  const FUmButtonModel& GetModel() const { return Model; }
  /** The logical element of the press arbiter (stable across rebuilds) and the owner's answer to a resolved release
   *  (Act, or Refused with the reason). */
  void SetPress(FName InId, const TSharedPtr<FS09HudPressArbiter>& InArbiter, const FS09OnHudPressOutcome& InOnOutcome);
  FName GetPressId() const { return PressId; }

  EUmButtonState GetState() const { return State; }
  bool IsPointerOver() const { return bHovered; }
  bool IsWhyShown() const { return bWhyShown; }
  FText GetWhyText() const;
  /** "variant=disc state=hover label=… enabled=1 why=-" - goes into the owner block's SHOT line. */
  FString DescribeState() const;
  /** Current animated scales (tests, the owner's SHOT line). */
  float GetIconScale() const { return IconScaleNow; }
  float GetBodyScale() const { return BodyScaleNow; }

  // ---- tests and synthetic input (the same paths as the mouse) ----
  /** Seconds clock of the widget (hover timer, animations): FPlatformTime by default. */
  void SetClockForTest(TFunction<double()> InClock) { Clock = MoveTemp(InClock); }
  void SetReducedMotionForTest(bool bOn) { ReducedOverride = bOn ? 1 : 0; }
  /** Runs the per-frame step without Slate (the tests step the clock). */
  void TickForTest() { Step(); }
  void SimulateHover(bool bIn);
  /** Review sheet (-S08IconGalleryButtons): draw the hover / pressed look without a pointer, animations at their end. */
  void SetPreviewPointer(bool bHover, bool bPressed);

  virtual FReply NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual FReply NativeOnMouseButtonDoubleClick(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual FReply NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual void NativeOnMouseEnter(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual void NativeOnMouseLeave(const FPointerEvent& InMouseEvent) override;
  virtual void NativeOnMouseCaptureLost(const FCaptureLostEvent& CaptureLostEvent) override;
  virtual bool NativeSupportsKeyboardFocus() const override { return false; }

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<USizeBox> Box;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UBorder> Body;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UGridPanel> Content;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<US08AnimatedIconWidget> Icon;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UTextBlock> Label;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<UBorder> KeyChip;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidgetOptional))
  TObjectPtr<UTextBlock> KeyText;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget))
  TObjectPtr<UImage> FocusRing;

 protected:
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

 private:
  void Restyle();
  void Step();
  /** VS-7 Frames: a label wider than the button (a long locale, the pseudo-locale +30 %, class S) steps its font down to
   *  fit the width it got (to 70 % at most) - the text never runs past the body. */
  void FitLabel(float WidthSu);
  void SetPressedVisual(bool bOn);
  bool IsReduced() const;
  double Now() const;

  FUmButtonModel Model;
  bool bHasModel = false;
  EUmButtonState State = EUmButtonState::Normal;
  FName PressId;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FS09OnHudPressOutcome OnOutcome;
  bool bHovered = false;
  bool bPressedVisual = false;
  double HoverSince = -1.0;
  bool bWhyShown = false;
  // animation: the scale moves linearly to its target over the state's duration
  float IconScaleNow = 1.0f;
  float IconScaleFrom = 1.0f;
  float IconScaleTo = 1.0f;
  float BodyScaleNow = 1.0f;
  float BodyScaleFrom = 1.0f;
  float BodyScaleTo = 1.0f;
  double AnimStart = 0.0;
  double AnimMs = 0.0;
  double PulseStart = -1.0;  // selected glyph pulse 1.1 -> 1.0
  float LabelOffsetSu = 0.0f;
  float FitWidthSu = -1.0f;  // FitLabel: the width and the text it last fitted (-1: refit)
  FString FitText;
  int32 ReducedOverride = -1;
  TFunction<double()> Clock;
  FName IconShown;
  float IconSizeShown = 0.0f;
  bool bCodeDefaultTree = false;
};

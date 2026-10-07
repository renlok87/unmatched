// VS-2 HB-21 (docs/game-design/visual/06-tasks/hud.csv HB-21; 04-hud-spec.md §2.3, §4.3, §7.1; 02 §6.2, §6.4; ВР-50;
// CX-09 mockup art/imagegen/hud-panels-v1-codex, accepted by delegation): OPP-HAND - UUmHudOppHand
// (/Game/S08/UI/Hud/WBP_UI_HUD_OPP_HAND), the opponent's hand as card backs of THEIR hero under PANEL-OPP; the deck
// and the discard as a caption. No face ever (GD-032): the model is the count only.
//
//   layout   the OPP-HAND slot (04 §1.6: right edge 1896, y 168; L 300 x 92, S 220 x 104 - the CX-09 delta; narrowed to the
//            room right of FIELD, ВР-VS2-10) on a T_Skin_Panel plate: Backs - 48 x 67 su backs from x 12, y 4, 28 su
//            apart; more than fit (10 in L) - the step shrinks so the last back ends inside (L 10 -> 25.3 su); Caption
//            «Рука {n} · колода {d} · сброс {s}» type.caption under them; a stale deck count «≈{d}» (bDeckCountStale).
//   texture  the back of the opponent's hero from the registry (back:<hero>, CP-05 King Arthur, CP-06 Medusa; one texture
//            per hero, the UV of its padded source); no back - the flat fallback (T_Skin_Panel 48 x 67 with resource-card
//            24 su) and one Warning (02 §6.4).
//   motion   a new back slides in from the left over 180 ms (icon.appear.ms: opacity 0.15 -> 1, x -12 -> 0 su); one that
//            leaves fades over 120 ms (icon.leave.ms); reduced motion - opacity only, <= 100 ms.
//   input    a click on the backs or the caption - the deck panel of the opponent (the arbiter, DE-014); the right button
//            - the inspector with "Скрытая информация" (the owner wires both). No CRD-DRAW for the opponent's draw.
// SHOT: 'SHOT widget id=UI-HUD-OPP-HAND state=count=<n> ... deck=<d> discard=<s> stale=0|1 step=<su> width=<su>'.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../../S09/S09HudPress.h"
#include "../S08ArtHud.h"
#include "../S08ArtHudWidgets.h"
#include "UmHudOppHand.generated.h"

class UBorder;
class UHorizontalBox;
class UTextBlock;
class UTexture2D;
class UVerticalBox;

struct UNMATCHED_API FUmOppHandModel {
  int32 HandCount = 0;
  int32 DeckCount = 0;
  int32 DiscardCount = 0;
  bool bDeckStale = false;
  /** The opponent's hero slug: the back texture (back:<slug>). */
  FString HeroSlug;
  /** The width of the OPP-HAND slot (su): the step of the backs follows it. */
  float WidthSu = 300.0f;
  float PxPerSu = 1.0f;
  bool operator==(const FUmOppHandModel& O) const {
    return HandCount == O.HandCount && DeckCount == O.DeckCount && DiscardCount == O.DiscardCount &&
           bDeckStale == O.bDeckStale && HeroSlug == O.HeroSlug && WidthSu == O.WidthSu && PxPerSu == O.PxPerSu;
  }
};

namespace UmHudOppHand {
inline constexpr float BackWSu = 48.0f;   // 02 §6.2 (ВР-50): the back 48 x 67 su
inline constexpr float BackHSu = 67.0f;
inline constexpr float StepSu = 28.0f;    // 04 §2.3
inline constexpr float PadSu = 12.0f;     // CX-09: the backs from x 12, the caption too
inline constexpr float TopSu = 4.0f;
inline constexpr float SlideSu = 12.0f;   // the new back comes in from 12 su to the left
/** The step of Count backs in a slot of WidthSu: 28 su while they fit, then shrinking so the last ends inside. */
UNMATCHED_API float Step(int32 Count, float WidthSu);
/** The width the backs take (su): 0 for none, 48 + (n - 1) x step otherwise. */
UNMATCHED_API float FanWidth(int32 Count, float WidthSu);
/** «Рука {n} · колода {d} · сброс {s}» (hud.opp.hand / .deck / .discard, the deck «≈{d}» when stale). */
UNMATCHED_API FText Caption(const FUmOppHandModel& M);
}  // namespace UmHudOppHand

UCLASS(Blueprintable, BlueprintType)
class UNMATCHED_API UUmHudOppHand : public UUserWidget {
  GENERATED_BODY()

 public:
  static const TCHAR* const WidgetBlueprintPath;  // /Game/S08/UI/Hud/WBP_UI_HUD_OPP_HAND

  virtual bool Initialize() override;
  /** Border "Panel" > VerticalBox "Column" > Backs (HorizontalBox, the pool of backs), Caption. */
  static bool BuildDefaultTree(UWidgetTree& Tree, FS08AttachWidget Attach, FString* OutError = nullptr);
  static UClass* WidgetClass();
  bool HasAllParts(FString* OutMissing = nullptr) const;
  bool UsesCodeDefaultTree() const { return bCodeDefaultTree; }
  FString SourceName() const;

  /** The one data input (П1); same model = no work. */
  void ApplyModel(const FUmOppHandModel& InModel);
  const FUmOppHandModel& GetModel() const { return Model; }
  bool HasModel() const { return bHasModel; }
  /** A left click (the deck panel of the opponent, through the arbiter) and a right click (the inspector). */
  void SetPress(FName InId, const TSharedPtr<FS09HudPressArbiter>& InArbiter, const FS09OnHudPressOutcome& InOnOutcome,
                TFunction<void()> InOnInspect);
  void CollectShotLines(TArray<FString>& Out, const FS08ScreenRect& Rect) const;
  /** The backs shown now (the leaving ones while they fade included) and the step (su). */
  int32 GetBacksShown() const { return Shown; }
  float GetStepSu() const { return StepNow; }
  /** The back texture loaded (false = the flat fallback). */
  bool HasBackTexture() const { return BackTexture != nullptr; }
  /** Tests: the clock (seconds) and reduced motion (-1 = the setting). */
  void SetClockForTest(TFunction<double()> InClock) { Clock = MoveTemp(InClock); }
  void SetReducedForTest(int32 InReduced) { ReducedOverride = InReduced; }
  /** Steps the slide / fade now (the tick does it per frame). */
  void Step();
  float GetBackOpacity(int32 Index) const;
  /** VS-5 E4 (LEET class S): the caption's type - type.caption, type.tag when that line is wider than the row. */
  FName GetCaptionToken() const { return CaptionToken; }

  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UBorder> Panel;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UHorizontalBox> Backs;
  UPROPERTY(BlueprintReadOnly, Category = "Um HUD", meta = (BindWidget)) TObjectPtr<UTextBlock> Caption;

 protected:
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;
  virtual FReply NativeOnMouseButtonDown(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;
  virtual FReply NativeOnMouseButtonUp(const FGeometry& InGeometry, const FPointerEvent& InMouseEvent) override;

 private:
  UWidget* MakeBack();
  void LayoutBacks();
  bool IsReduced() const;
  double Now() const;

  FUmOppHandModel Model;
  bool bHasModel = false;
  bool bCodeDefaultTree = false;
  int32 Shown = 0;      // widgets visible (entering, resting, leaving)
  int32 Target = 0;     // the hand count
  float StepNow = UmHudOppHand::StepSu;
  TArray<double> EnterStart;  // per back: the slide-in start (< 0 = at rest)
  TArray<double> LeaveStart;  // per back: the fade-out start (< 0 = not leaving)
  int32 ReducedOverride = -1;
  TFunction<double()> Clock;
  FName PressId;
  TSharedPtr<FS09HudPressArbiter> Arbiter;
  FS09OnHudPressOutcome OnOutcome;
  TFunction<void()> OnInspect;
  FString BackSlugLoaded;
  bool bWarned = false;
  FName CaptionToken = FName(TEXT("type.caption"));
  UPROPERTY(Transient) TObjectPtr<UTexture2D> BackTexture;
  UPROPERTY(Transient) TArray<TObjectPtr<UWidget>> Pool;
};

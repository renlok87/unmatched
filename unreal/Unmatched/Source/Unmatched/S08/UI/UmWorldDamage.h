// VS-6 F2 FX-22 (docs/game-design/visual/06-tasks/vfx.csv FX-22, icons.csv IC-49; 04-hud-spec.md §2.15, §3.5; 02 §3.3,
// §9.2; ВР-21, ВР-37, ВР-63, ВР-67): the «−N» / «+N» numbers over a figure - the content the art HUD damage widget
// (US08ArtDamageWidget, WBP_S08ArtDamage) shows by default since VS-6 F2; its old tree (18 su, #161A28) lives only in the
// rollback -S08SlateHud=damage (ВР-H15, ВР-61).
//
//   capsule  card.navy, panel.edge hairline 1 su, radius.s 4 su, padding 8 x 4 su; the text type.damage 24 su, «−N»
//            damage.text (hud.damage.minus «−{n}», U+2212), «+N» fx.heal (hud.damage.plus «+{n}»); under reduced motion
//            a «+N» carries the IC-49 state-heal «+» (24 su, the export for DPI x UI scale) - the heal motes are off then.
//   motion   S08CombatFx::NumberPose: scale 0.8 -> 1 over 80 ms, a 24 su ease-out rise over the life, the last 150 ms
//            opacity -> 0; «−N» 900 ms x speed, «+N» 700 ms; reduced motion: no rise / scale, 450 ms (04 §3.5).
//   stack    up to four numbers of the fighter at once; a newer one sits above the highest one still shown - 28 su, at
//            least the capsule height + 4 su (ВР-VS6-17: the 36 su capsule would overlap at 28), measured where the
//            older one is at the push.
//   anchor   above the figure's screen rect (FigureScreenRect), centred, not on a seam of the spaces (HD-07); when that
//            rect leaves the viewport or covers a placed tag / the icon / a panel, the W5b-R chooser places it.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../S08ArtHud.h"
#include "../S08ArtHudWidgets.h"
#include "UmWorldDamage.generated.h"

class UBorder;
class UOverlay;
class UImage;
class UTextBlock;
class UTexture2D;

namespace UmWorldDamage {
inline constexpr float CapsuleRadiusSu = 4.0f;
inline constexpr float PadXSu = 8.0f;
inline constexpr float PadYSu = 4.0f;
inline constexpr float HealIconSu = 24.0f;
inline constexpr float GapPx = 4.0f;
/** -S08SlateHud=damage is the rollback; anything else draws the FX-22 look. */
UNMATCHED_API bool DamageV2();
/** «−{n}» (hud.damage.minus) for a damage (Amount > 0), «+{n}» (hud.damage.plus) for a heal (Amount < 0). */
UNMATCHED_API FText NumberText(int32 Amount);
/** The anchor of FX-22: Size px centred above Figure (GapPx), inside the viewport and off every Hard rect; false when
 *  no such rect exists (the caller falls back to the W5b-R chooser). */
UNMATCHED_API bool AboveFigure(const FS08ScreenRect& Figure, const FVector2D& SizePx, const FVector2D& ViewportPx,
                               const TArray<FS08ScreenRect>& Hard, FS08ScreenRect& Out);
/** The ARTLOOK field 'damage=v2|legacy(-S08SlateHud=damage)'. */
UNMATCHED_API FString LookField();
}  // namespace UmWorldDamage

UCLASS()
class UNMATCHED_API UUmWorldDamage : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  /** A new number of FighterId (Amount > 0 damage, < 0 heal) for LifeMs: an older fighter's numbers are dropped, the
   *  same fighter's stay (stacked 28 su below the new one), never more than MaxNumbers. The same (fighter, seq, sign)
   *  again is ignored. */
  void Push(const FString& FighterId, int32 Amount, int32 Seq, int32 LifeMs, bool bReduced);
  /** Drops every number (review sheets switch their state). */
  void Clear();
  /** Applies the poses of NowS (seconds, FPlatformTime by default); collapses the finished entries. */
  void Step();
  int32 NumShown() const;
  int32 FontSize() const;
  /** The traced parts: board.damage.text of the newest number (its capsule is the widget itself). */
  void CollectParts(TArray<FS08WidgetPart>& Out) const;
  void SetClockForTest(TFunction<double()> InClock) { Clock = MoveTemp(InClock); }
  /** The newest entry's text / opacity / rise (tests, the gallery). */
  FText NewestText() const;
  float NewestOpacity() const;
  float NewestRiseSu() const;
  bool NewestHasHealIcon() const;

 protected:
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

 private:
  struct FEntry {
    int32 Amount = 0;
    int32 Seq = -1;
    float BaseSu = 0.0f;  // the stack offset above the anchor (ВР-VS6-17)
    double StartS = 0.0;
    int32 LifeMs = 0;
    bool bReduced = false;
    bool bShown = false;
  };
  double Now() const;
  void BuildSlot(int32 Index);
  void ApplyEntry(int32 Index, const FEntry& E);
  void EnsureHealBrush();

  FString FighterId;
  TArray<FEntry> Entries;  // index = widget slot
  UPROPERTY() TObjectPtr<UOverlay> Root;
  UPROPERTY() TArray<TObjectPtr<UBorder>> Capsules;
  UPROPERTY() TArray<TObjectPtr<UTextBlock>> Texts;
  UPROPERTY() TArray<TObjectPtr<UImage>> Icons;
  UPROPERTY() TObjectPtr<UTexture2D> HealTexture;
  FSlateBrush HealBrush;
  bool bHealBrush = false;
  int32 Newest = INDEX_NONE;
  TFunction<double()> Clock;
};

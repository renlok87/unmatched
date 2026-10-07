// VS-4 H12 (docs/game-design/visual/06-tasks/hud.csv HB-45, HB-46; 04-hud-spec.md §2.15, §5.2 H12; 02 §6.5; ВР-07,
// ВР-61, ВР-63, ВР-72, ВР-78; accepted mockup HB-44 art/imagegen/hud-world-v1-codex, ВР-VS2-HB44-01...07): the world
// layer on the HUD tokens - the content the art HUD tag (US08ArtTagWidget, WBP_S08ArtTag) and plate (US08ArtPlateWidget,
// WBP_S08ArtPlate) show by default since H12. The old trees stay inside those widgets for the rollbacks.
//
//   tag    UUmWorldTag (HB-45): a card.navy capsule 40 su high, radius 8, panel.edge hairline (ВР-61, not #161A28);
//          the team chip 24 su (team-chip-p1 circle / -p2 hexagon, IC-44 / IC-45, ВР-78; -S08IconLegacy: mvp-v1), the
//          harpy digit 1-3 on a 16 su card.navy disc with a card.cream ring (font.card card.cream, cap 10 su, ВР-72; the
//          order of sidekicks[], the same number the Z-1 base digit prints - S08HeroesV2::HarpyNumber), the HP bar 40 x 4
//          hp.fill / hp.back, «{hp}/{max}» type.tag 14 text.primary (ВР-63, not 12 / 11). No name (ВР-07). The row of
//          HB-44: 12 | chip 24 | 6 | digit 16 | 6 | bar 40 | 8 | text | 12, every part centred on the 20 su line.
//   plate  UUmWorldPlate (HB-46): panel.bg 268 x 144 su (radius.m, panel.edge), the name type.heading text.primary
//          (RU «Медуза», «Король Артур», «Мерлин» from Config/Cards/S08FighterNames.json = 05-content-matrix; harpies
//          hud.plate.harpy_name «Гарпия {number}»), the role type.tag text.secondary (hud.plate.role.hero_ranged ...: hero /
//          sidekick x ranged / melee of the fighter, FS09CommandUi::IsRangedAttacker), the HP «{hp}/{max}», the team chip
//          24 su and «ВАШ» / «СОПЕРНИК» (hud.plate.side.*), «ЦЕЛЬ» on a state.pending chip with card.glyph text in the
//          attack mode (hud.plate.target). Shown only on hover or selection (ВР-07, the controller's rule): appear 150 ms
//          (hover.ms), leave 120 ms (icon.leave.ms), reduced motion - opacity within 100 ms.
//   rollback -S08SlateHud=tag / -S08SlateHud=plate: the trees of before H12 (12 / 11 su, #161A28, «H1» names);
//            -ArtHudImpl=slate is a separate switch and does not change.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../S08ArtHudWidgets.h"
#include "UmWorldLayer.generated.h"

class UBorder;
class UHorizontalBox;
class UImage;
class USizeBox;
class UTextBlock;
class UTexture2D;
class UVerticalBox;
struct FS08BoardFighter;

/** What the V2 tag shows. */
struct UNMATCHED_API FUmWorldTagModel {
  int32 Hp = 0;
  int32 MaxHp = 0;
  uint8 TeamSlot = 0;  // 0 = P1 circle, 1 = P2 hexagon (the look slot)
  int32 Digit = 0;     // 1..3 for a harpy, 0 = none
  bool operator==(const FUmWorldTagModel& O) const {
    return Hp == O.Hp && MaxHp == O.MaxHp && TeamSlot == O.TeamSlot && Digit == O.Digit;
  }
};

/** What the V2 plate shows. */
struct UNMATCHED_API FUmWorldPlateModel {
  FText Name;
  FText Role;
  FText Side;
  FText Hp;
  uint8 TeamSlot = 0;
  bool bTarget = false;
};

namespace UmWorldLayer {
inline constexpr float TagHeightSu = 40.0f;
inline constexpr float TagRadiusSu = 8.0f;
inline constexpr float TagPadSu = 12.0f;
inline constexpr float ChipSu = 24.0f;
inline constexpr float DigitSu = 16.0f;
inline constexpr float BarWSu = 40.0f;
inline constexpr float BarHSu = 4.0f;
inline constexpr float GapSu = 6.0f;
inline constexpr float BarGapSu = 8.0f;
inline constexpr float PlateWSu = 268.0f;
inline constexpr float PlateHSu = 144.0f;
inline constexpr float PlatePadSu = 16.0f;
/** -S08SlateHud=tag / =plate are the rollbacks; anything else draws the H12 look. */
UNMATCHED_API bool TagV2();
UNMATCHED_API bool PlateV2();
/** The plate name of a fighter on the UI language (Config/Cards/S08FighterNames.json; harpies hud.plate.harpy_name with
 *  their sidekicks[] number); the server label when the file has no entry. */
UNMATCHED_API FText DisplayName(const FS08BoardFighter& Fighter);
/** hud.plate.role.hero_ranged | hero_melee | sidekick_ranged | sidekick_melee. */
UNMATCHED_API FText RoleText(bool bHero, bool bRanged);
/** hud.plate.side.own | .opponent. */
UNMATCHED_API FText SideText(bool bOwn);
/** hud.plate.target «ЦЕЛЬ». */
UNMATCHED_API FText TargetText();
/** «{hp}/{max}». */
UNMATCHED_API FText HpText(int32 Hp, int32 MaxHp);
/** The ARTLOOK / trace field 'worldTag=v2|legacy(-S08SlateHud=tag) worldPlate=v2|legacy(..)'. */
UNMATCHED_API FString LookField();
/** The harpy digit of a tag: the sidekicks[] number of a numbered sidekick (S08FighterNames.json), else 0. */
UNMATCHED_API int32 TagDigit(const FS08BoardFighter& Fighter);
/** The controller's hooks (S08FlowGameMode.cpp): the H12 look on the art HUD widgets unless rolled back (the 24 su
 *  team chips of IC-44 / IC-45 loaded for it), and the V2 fields of the texts. */
UNMATCHED_API void SetupTag(US08ArtTagWidget& Tag);
UNMATCHED_API void SetupPlate(US08ArtPlateWidget& Plate);
UNMATCHED_API void FillTagTexts(FS08TagTexts& Texts, const FS08BoardFighter& Fighter);
UNMATCHED_API void FillPlateTexts(struct FS08PlateTexts& Texts, const FS08BoardFighter& Fighter, bool bOwn, bool bTarget);
}  // namespace UmWorldLayer

UCLASS()
class UNMATCHED_API UUmWorldTag : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  void ApplyModel(const FUmWorldTagModel& InModel);
  const FUmWorldTagModel& GetModel() const { return Model; }
  /** The 24 su chips (v3 team-chip at the carrier's DPI x UI scale; -S08IconLegacy mvp-v1), loaded once. */
  void SetChipBrushes(const FSlateBrush& P1, const FSlateBrush& P2, const TArray<UTexture2D*>& Keep);
  /** The traced parts with the ids of the tag (board.tag, .hp, .bar, .chip; the name is never drawn). */
  void CollectParts(TArray<FS08WidgetPart>& Out) const;
  int32 HpFontSize() const;

  UPROPERTY() TObjectPtr<UBorder> Capsule;
  UPROPERTY() TObjectPtr<USizeBox> ChipBox;
  UPROPERTY() TObjectPtr<UImage> Chip;
  UPROPERTY() TObjectPtr<USizeBox> DigitBox;
  UPROPERTY() TObjectPtr<UBorder> DigitDisc;
  UPROPERTY() TObjectPtr<UTextBlock> DigitText;
  UPROPERTY() TObjectPtr<USizeBox> BarBox;
  UPROPERTY() TObjectPtr<USizeBox> BarFill;
  UPROPERTY() TObjectPtr<UImage> BarBack;
  UPROPERTY() TObjectPtr<UImage> BarFillImage;
  UPROPERTY() TObjectPtr<UTextBlock> HpLabel;

 private:
  void Restyle();
  FUmWorldTagModel Model;
  bool bHasModel = false;
  FSlateBrush ChipBrushes[2];
  bool bChips = false;
  UPROPERTY() TArray<TObjectPtr<UTexture2D>> ChipTextures;
};

UCLASS()
class UNMATCHED_API UUmWorldPlate : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  void ApplyModel(const FUmWorldPlateModel& InModel);
  void SetChipBrushes(const FSlateBrush& P1, const FSlateBrush& P2, const TArray<UTexture2D*>& Keep);
  /** The hover fade (04 §2.15): in over hover.ms, out over icon.leave.ms, reduced motion <= reduced.max_ms. Collapses the
   *  owner (Host) at the end of the leave. */
  void SetShownAnimated(UWidget* Host, bool bShown);
  /** Ends a running fade at its target now (review sheets: a state is shot a few frames after it is applied). */
  void FinishFade();
  float GetOpacityNow() const { return OpacityNow; }
  bool IsTargetShown() const;
  void CollectParts(TArray<FS08WidgetPart>& Out) const;
  void SetClockForTest(TFunction<double()> InClock) { Clock = MoveTemp(InClock); }
  void SetReducedForTest(int32 InReduced) { ReducedOverride = InReduced; }
  void TickForTest() { StepFade(); }

  UPROPERTY() TObjectPtr<UBorder> Panel;
  UPROPERTY() TObjectPtr<UTextBlock> NameLabel;
  UPROPERTY() TObjectPtr<UTextBlock> RoleLabel;
  UPROPERTY() TObjectPtr<UTextBlock> HpLabel;
  UPROPERTY() TObjectPtr<USizeBox> ChipBox;
  UPROPERTY() TObjectPtr<UImage> Chip;
  UPROPERTY() TObjectPtr<UTextBlock> SideLabel;
  UPROPERTY() TObjectPtr<UBorder> TargetChip;
  UPROPERTY() TObjectPtr<UTextBlock> TargetLabel;

 protected:
  virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

 private:
  void StepFade();
  double Now() const;
  FUmWorldPlateModel Model;
  FSlateBrush ChipBrushes[2];
  bool bChips = false;
  UPROPERTY() TArray<TObjectPtr<UTexture2D>> ChipTextures;
  TWeakObjectPtr<UWidget> FadeHost;
  bool bWantShown = false;
  float OpacityNow = 0.0f;
  float OpacityFrom = 0.0f;
  double FadeStart = -1.0;
  double FadeMs = 0.0;
  int32 ReducedOverride = -1;
  TFunction<double()> Clock;
};

// W4-C (user decision 2026-09-28 "HUD: hybrid UMG now"): style tokens of the
// ART-004 art HUD layer - ONE table for the combat plate and the combat icon,
// read by both views (the UMG widget classes and the transitional Slate
// path) and by the controller (plate size and HP bar width feed the
// placement geometry). Rules (engine gate memo, HUD row):
//   - colors are sRGB bytes (FColor) and reach Slate/UMG ONLY through
//     FLinearColor(FColor): the painted back-buffer bytes then equal these
//     bytes, which is what every pixel gate matches (memory trap 9: a raw
//     FLinearColor(1, .25, .25) paints #FF8989, not #FF4040);
//   - fonts are tokens (typeface + size, optional UFont), never literals in
//     view code; an empty FontObject is the core Slate default font (Roboto),
//     i.e. exactly the pre-UMG Slate plate;
//   - layout metrics that only the layout needs (paddings, the marker strip
//     height, the HP bar height) live in the widget tree (WBP) and default to
//     S08ArtHudLayout below, shared by the code default tree and the Slate path.
// The values are the T2.2 plate (hud-input-t22-2026-09-28.md); a designer
// changes them in the WBP class defaults (Style) without a C++ rebuild.
#pragma once

#include "CoreMinimal.h"
#include "Fonts/SlateFontInfo.h"
#include "Layout/Margin.h"
#include "S08ArtHudStyle.generated.h"

/** Font token: typeface of the default composite font (or of FontObject) + size. */
USTRUCT(BlueprintType)
struct UNMATCHED_API FS08ArtHudFontToken {
  GENERATED_BODY()

  FS08ArtHudFontToken() = default;
  FS08ArtHudFontToken(const TCHAR* InTypeface, int32 InSize) : Typeface(InTypeface), Size(InSize) {}

  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD")
  FName Typeface = TEXT("Regular");

  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD", meta = (ClampMin = "4", ClampMax = "96"))
  int32 Size = 10;

  /** Optional UFont asset; empty = FCoreStyle::GetDefaultFontStyle (the Slate
   *  plate font, Roboto with the engine's Cyrillic coverage). */
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD", meta = (AllowedClasses = "/Script/Engine.Font"))
  TObjectPtr<const UObject> FontObject = nullptr;

  FSlateFontInfo Resolve() const;
};

/** HI-07 (HUD-AND-ICONS.md; hud-style-tokens font.card, decided 2026-10-03): numbers and short labels of icons
 *  (+N BOOST, turn order, threat count, hint rank), the step badge, the maneuver panel title use Roboto Bold
 *  Condensed = the "BoldCondensed" typeface of the core Slate default font (Engine/Content/Slate/Fonts, staged in
 *  the client pak; Apache 2.0, Licenses/THIRD_PARTY_NOTICES.txt). No project UFont: the engine UFont
 *  /Engine/EngineFonts/Roboto lacks this face, the Slate default font (FCoreStyle) has it. */
namespace S08ArtHudFonts {
inline const TCHAR* const CardTypeface = TEXT("BoldCondensed");
inline FS08ArtHudFontToken Card(int32 Size) { return FS08ArtHudFontToken(CardTypeface, Size); }
}  // namespace S08ArtHudFonts

/** Plate (name / HP / statuses) tokens. */
USTRUCT(BlueprintType)
struct UNMATCHED_API FS08ArtHudPlateStyle {
  GENERATED_BODY()

  /** Top strip. #C8A0FF differs from every S09/S10 HUD marker by > 32 in at
   *  least one channel (nearest #A020FF: dR = 40) - the T2.2 plate pixel gate. */
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Colors")
  FColor Marker = FColor(200, 160, 255, 255);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Colors")
  FColor Background = FColor(22, 26, 40, 255);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Colors")
  FColor NameText = FColor(242, 236, 222, 255);
  /** W5b-R D-2/D-3: the team chip = the team shape (circle P1 / hexagon P2) in the ON-SCREEN colour of the team
   *  ring fill (hud-style-tokens team.p1.screen / team.p2.screen), drawn on the plate background; YOURS/ENEMY text
   *  carries own/enemy. Replaces the T2.2 own/enemy chip box (OwnChip / EnemyChip). */
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Colors")
  FColor TeamChipP1 = FColor(218, 197, 118, 255);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Colors")
  FColor TeamChipP2 = FColor(87, 134, 168, 255);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Colors")
  FColor HpBack = FColor(70, 30, 30, 255);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Colors")
  FColor HpFill = FColor(80, 190, 100, 255);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Colors")
  FColor StatusText = FColor(200, 204, 220, 255);

  /** Plate size in HUD slate units (1 su = 1 px at 1920x1080). The placement
   *  search (S08ArtHud::ChoosePlateRect) uses this size. */
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Size")
  FVector2D SizeSu = FVector2D(172.0, 54.0);
  /** Full HP bar width in su; the fill is width * health / maxHealth (>= 1 su). */
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Size", meta = (ClampMin = "8"))
  float HpBarWidthSu = 96.0f;
  /** Team shape chip (exact-size 12 px texture, hud-style-tokens icon.team_shape). */
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Size", meta = (ClampMin = "4"))
  float TeamShapeSu = 12.0f;

  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Fonts")
  FS08ArtHudFontToken NameFont = FS08ArtHudFontToken(TEXT("Bold"), 12);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Fonts")
  FS08ArtHudFontToken TeamFont = FS08ArtHudFontToken(TEXT("Bold"), 8);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Fonts")
  FS08ArtHudFontToken HpFont = FS08ArtHudFontToken(TEXT("Bold"), 10);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Fonts")
  FS08ArtHudFontToken StatusFont = FS08ArtHudFontToken(TEXT("Regular"), 8);

  /** The pixel-gate conversion (sRGB bytes -> linear). */
  static FLinearColor Linear(const FColor& Srgb) { return FLinearColor(Srgb); }
  /** Team chip colour by the team LOOK slot (0 = P1, 1 = P2). */
  FLinearColor TeamChipColor(uint8 Slot) const { return Linear(Slot == 0 ? TeamChipP1 : TeamChipP2); }
};

/** W5b-R D-1: screen tag of a fighter (UI-HUD-TAG proposal): team chip, name (full mode), HP mini bar + "7/7". */
USTRUCT(BlueprintType)
struct UNMATCHED_API FS08ArtHudTagStyle {
  GENERATED_BODY()

  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Colors")
  FColor Background = FColor(22, 26, 40, 255);  // tag.background #161A28
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Colors")
  FColor Text = FColor(242, 236, 222, 255);  // tag.text #F2ECDE (14.7:1 on the background)
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Colors")
  FColor HpBack = FColor(70, 30, 30, 255);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Colors")
  FColor HpFill = FColor(80, 190, 100, 255);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Fonts")
  FS08ArtHudFontToken NameFont = FS08ArtHudFontToken(TEXT("Bold"), 12);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Fonts")
  FS08ArtHudFontToken HpFont = FS08ArtHudFontToken(TEXT("Bold"), 11);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Size")
  FMargin Padding = FMargin(4.0f, 2.0f);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Size")
  float ChipSu = 12.0f;
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Size")
  float GapSu = 3.0f;
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Size")
  float BarWidthSu = 34.0f;
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Size")
  float BarHeightSu = 5.0f;
  /** ENV-MAPS P4 (concept review readability, map-image boards with "labelPlates" only): the tag sits on a dark
   *  SEMI-opaque rounded plate with a 1 su outline in the team's on-screen colour (the team accent), so light circles
   *  under it no longer swallow the text. Grid boards keep the flat opaque Background above. */
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Board plate")
  // #10131E at 84 %: over a white circle the plate reads ~#363944 (gamma-space UI blend), text #F2ECDE ~10:1
  FColor BoardPlateBackground = FColor(16, 19, 30, 214);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Board plate", meta = (ClampMin = "0"))
  float BoardPlateCornerSu = 4.0f;
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Board plate", meta = (ClampMin = "0"))
  float BoardPlateOutlineSu = 1.0f;
  /** Outline (team accent) opacity over the team chip colour (FS08ArtHudPlateStyle::TeamChipP1 / P2). */
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Board plate", meta = (ClampMin = "0", ClampMax = "1"))
  float BoardPlateOutlineAlpha = 0.9f;
  /** Linear colours of the board plate (sRGB bytes through FLinearColor(FColor), alpha kept). */
  FLinearColor BoardPlateFill() const { return FLinearColor(BoardPlateBackground); }
  FLinearColor BoardPlateOutline(const FColor& TeamChip) const {
    FLinearColor C(TeamChip);
    C.A = FMath::Clamp(BoardPlateOutlineAlpha, 0.0f, 1.0f);
    return C;
  }
};

/** ENV-MAPS P4: stacked board-plate tags keep at least this gap (px) between each other and to the plate / icon /
 *  damage number (S08ArtHud::FLabelPlacementInput::HardPadPx; 0 on grids). */
namespace S08ArtHudBoardPlate {
constexpr float TagHardPadPx = 3.0f;
}  // namespace S08ArtHudBoardPlate

/** W5b-R D-1: the damage number capsule (UI-HUD-DAMAGE proposal). */
USTRUCT(BlueprintType)
struct UNMATCHED_API FS08ArtHudDamageStyle {
  GENERATED_BODY()

  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Colors")
  FColor Background = FColor(22, 26, 40, 255);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Colors")
  FColor Text = FColor(255, 224, 175, 255);  // damage.text #FFE0AF (13.6:1 on the capsule)
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Fonts")
  FS08ArtHudFontToken Font = FS08ArtHudFontToken(TEXT("Bold"), 18);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Size")
  FMargin Padding = FMargin(8.0f, 0.0f);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Size")
  float CornerRadiusSu = 12.0f;
};

/** Layout defaults of the code default tree (UMG) and of the Slate path. In a
 *  WBP these are ordinary slot/size-box properties the designer edits. */
namespace S08ArtHudLayout {
inline const FMargin NameRowPadding(6.0f, 2.0f, 6.0f, 0.0f);
inline const FMargin HpRowPadding(6.0f, 2.0f, 6.0f, 0.0f);
inline const FMargin StatusPadding(6.0f, 2.0f, 6.0f, 2.0f);
inline const FMargin ChipPadding(4.0f, 0.0f);
inline const FMargin HpTextPadding(6.0f, 0.0f, 0.0f, 0.0f);
constexpr float MarkerHeightSu = 3.0f;
constexpr float HpBarHeightSu = 7.0f;
}  // namespace S08ArtHudLayout

/** UI ids of the plate parts in `SHOT widget id=` trace lines (stable names:
 *  they are the gate vocabulary, not the widget names). */
namespace S08ArtHudIds {
inline const TCHAR* const Plate = TEXT("plate");
inline const TCHAR* const PlateMarker = TEXT("plate.marker");
inline const TCHAR* const PlateName = TEXT("plate.name");
inline const TCHAR* const PlateTeam = TEXT("plate.team");
inline const TCHAR* const PlateHpBar = TEXT("plate.hpbar");
inline const TCHAR* const PlateHpFill = TEXT("plate.hpfill");
inline const TCHAR* const PlateHp = TEXT("plate.hp");
inline const TCHAR* const PlateStatus = TEXT("plate.status");
inline const TCHAR* const PlateTeamShape = TEXT("plate.teamshape");
inline const TCHAR* const Icon = TEXT("icon");
// W5b-R D-1 (proposed UI-HUD-TAG / UI-HUD-DAMAGE, docs/art-pipeline/proposals/w5br-hud-tag-damage-02.diff.md)
inline const TCHAR* const Tag = TEXT("board.tag");
inline const TCHAR* const TagName = TEXT("board.tag.name");
inline const TCHAR* const TagHp = TEXT("board.tag.hp");
inline const TCHAR* const TagBar = TEXT("board.tag.bar");
inline const TCHAR* const TagChip = TEXT("board.tag.chip");
inline const TCHAR* const Damage = TEXT("board.damage");
inline const TCHAR* const DamageText = TEXT("board.damage.text");
}  // namespace S08ArtHudIds

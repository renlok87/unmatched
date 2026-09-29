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
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Colors")
  FColor OwnChip = FColor(70, 120, 200, 255);
  UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "S08 Art HUD|Colors")
  FColor EnemyChip = FColor(200, 70, 60, 255);
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
  FLinearColor ChipColor(bool bOwn) const { return Linear(bOwn ? OwnChip : EnemyChip); }
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
inline const TCHAR* const Icon = TEXT("icon");
}  // namespace S08ArtHudIds

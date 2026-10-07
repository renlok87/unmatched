// VS-4 FX-38 (docs/game-design/visual/06-tasks/vfx.csv FX-38; ВР-PL12, ВР-32, ВР-68, ВР-VS3-FX38-01 / -02; 02 §7.1
// (L6), §7.4; HUD-AND-ICONS HI-06, HI-12; move-selection 03-ux-spec §4.1, §4.2a): the zone icons at a hovered space -
// UUmZoneBadges, the screen L6 layer bound to the projection of the space centre.
//
//   what     the zone keys of the space under the cursor (the board model's Zones of the cell = topology
//            spaces[].zones): up to three zone icons (IC-62...IC-69, US08AnimatedIconWidget, layers body / disc / glyph of
//            T_IV3_zone_<key>), more than three - two icons and «+N» (type.tag card.cream on a card.navy plate). No hover -
//            no icons (ВР-32); the zone colour never reads alone: the glyph carries the key (UI-ACC-004).
//   size     L6 = clamp(0.3 x the space circle's screen diameter; 16; 32) px (HI-12; UI-ACC-001 does not apply to the
//            board layer); the zone icons only from 24 px (below that the L6 channel stays without them, IC-62...IC-69;
//            no 16 px icon, ВР-42); the texture is the nearest export of 24 / 32 / 36 / 48 / 64 drawn 1 : 1.
//   colours  the disc - boards[].zoneIconSrgb of the board profile (live tune; never the topology hex); the glyph -
//            card.navy or card.glyph, whichever contrasts more with the disc (02 §7.4, ВР-68).
//   anchor   the right anchor of the space (03-ux-spec §4.2a: + 38 uu right of the centre), the icons in a column centred
//            on it; a column that would cover a figure or its tag (HB-45) moves right of them (MS-R-72: the leader's
//            ±15° sector and the left / top / bottom anchors belong to MS-T-10).
//   motion   appear 180 / leave 120 ms (the contract's standard); a new space - the old icons leave and the new ones
//            appear in one frame; reduced motion - opacity 100 ms (the contract's reduced branch).
//   rollback -S08SlateHud=zone: no zone icons at a space (as before FX-38).
// SHOT: 'SHOT widget id=zone impl=umg state=shown|hidden fighter=none bbox=(..) ... space=<id> keys=<k,..> shown=<n>
//        more=<n> px=<size> tex=<px> moved=0|1 overlap=<px2>' - one line, the format of plate / tag / damage / icon unchanged.
#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "../S08ArtHud.h"
#include "UmZoneBadges.generated.h"

class UBorder;
class UCanvasPanel;
class UTextBlock;
class US08AnimatedIconWidget;

/** What the layer shows this frame (the owner fills it from the hovered space). */
struct UNMATCHED_API FUmZoneBadgeInput {
  /** A space is hovered and nothing hides the layer (combat on screen, a modal, the result screen). */
  bool bShow = false;
  FString SpaceId;
  /** The space's zone keys in topology order. */
  TArray<FName> Keys;
  /** The projected space centre and its circle radius (viewport px). */
  FVector2D CentrePx = FVector2D::ZeroVector;
  float RadiusPx = 0.0f;
  /** The right anchor's distance from the centre (viewport px: 38 uu projected). */
  float AnchorPx = 0.0f;
  /** What the column never covers: the figures and their tags (viewport px). */
  TArray<FS08ScreenRect> Avoid;
  /** The viewport (px): the column stays inside. */
  FVector2D ViewportPx = FVector2D(1920.0, 1080.0);
  /** The disc colour of a key from the board profile; false = no entry (the key shows no icon). */
  TFunction<bool(FName, FColor&)> DiscColor;
};

/** The planned column (viewport px). */
struct UNMATCHED_API FUmZonePlan {
  int32 L6Px = 0;          // clamp(0.3 d; 16; 32)
  int32 TexturePx = 0;     // 0 = no icon (L6 < 20 px, ВР-VS4-56)
  TArray<FName> Shown;     // <= 3 keys with an icon
  int32 More = 0;          // keys beyond the two shown when more than three
  TArray<FS08ScreenRect> IconRects;
  FS08ScreenRect MoreRect;
  FS08ScreenRect Column;
  bool bMoved = false;
  double Overlap = 0.0;    // the column x the avoided rects after the move (px2)
  FString Hidden;          // why nothing is shown ('' = shown): off | nokeys | small | nocolor
};

namespace UmZoneBadges {
inline constexpr float L6Ratio = 0.3f;
inline constexpr int32 L6MinPx = 16;
inline constexpr int32 L6MaxPx = 32;
inline constexpr int32 MinIconPx = 24;
/** ВР-VS4-56: the hovered space's zone icons are its only L6 channel today (the MS-T-10 badges are not drawn), so an L6 of
 *  20...23 px - K1 at 720p on both real boards (circle 66-70 px) - still shows them at 24 px (FX-38 «на 720p >= 24 px»,
 *  the exports start at 24); below 20 px (the minimum zoom) they stay hidden, as HI-12 collapses L6 below 24 px. */
inline constexpr int32 MinShowL6Px = 20;
inline constexpr int32 MaxIcons = 3;
inline constexpr float GapPx = 2.0f;
inline constexpr float AnchorUU = 38.0f;  // 03-ux-spec §4.2a / HI-12: the anchors ±38 uu from the centre
/** clamp(0.3 x 2 r; 16; 32), rounded. */
UNMATCHED_API int32 L6SizePx(float RadiusPx);
/** The export drawn for an L6 size: 0 below 20 (ВР-VS4-56), else the nearest of 24 / 32 / 36 / 48 / 64 to max(L6, 24)
 *  (a tie - the larger). */
UNMATCHED_API int32 TexturePxFor(int32 L6Px);
/** The contrast rule of the glyph: card.navy or card.glyph (theme colours), whichever contrasts more with Disc. */
UNMATCHED_API FLinearColor InkFor(const FColor& Disc, bool* bOutNavy = nullptr);
UNMATCHED_API double Contrast(const FLinearColor& A, const FLinearColor& B);
/** The column: icons <= 3 or two + «+N», centred on the right anchor, moved right of a covered figure / tag. */
UNMATCHED_API FUmZonePlan Plan(const FUmZoneBadgeInput& In);
}  // namespace UmZoneBadges

UCLASS()
class UNMATCHED_API UUmZoneBadges : public UUserWidget {
  GENERATED_BODY()

 public:
  virtual bool Initialize() override;
  /** px per slate unit of the board layer (the art HUD's HudPixelsPerUnit). */
  void SetPxPerUnit(float InPpu) { Ppu = InPpu > 0.0f ? InPpu : 1.0f; }
  /** The one input (per frame from the owner; no work while the plan and the space stay the same). */
  void ApplyInput(const FUmZoneBadgeInput& In);
  const FUmZonePlan& GetPlan() const { return PlanNow; }
  const FString& GetSpaceId() const { return SpaceNow; }
  /** The disc / ink colours of a shown key (tests). */
  bool GetShownColors(FName Key, FLinearColor& OutDisc, FLinearColor& OutInk) const;
  int32 GetApplyCount() const { return ApplyCount; }
  void CollectShotLines(TArray<FString>& Out) const;
  void SetReducedForTest(int32 InReduced) { ReducedOverride = InReduced; }

 private:
  US08AnimatedIconWidget* IconAt(int32 Set, int32 Index);
  void Place(UWidget* W, const FS08ScreenRect& RectPx, int32 Z);
  UPROPERTY() TObjectPtr<UCanvasPanel> Root;
  UPROPERTY() TArray<TObjectPtr<US08AnimatedIconWidget>> Icons;  // two sets of MaxIcons (current / leaving)
  UPROPERTY() TObjectPtr<UBorder> MorePlate;
  UPROPERTY() TObjectPtr<UTextBlock> MoreText;
  FUmZonePlan PlanNow;
  FString SpaceNow;
  FString Signature;
  int32 SetNow = 0;
  int32 ApplyCount = 0;
  int32 ReducedOverride = -1;
  float Ppu = 1.0f;
  TMap<FName, FLinearColor> DiscNow;
  TMap<FName, FLinearColor> InkNow;
};

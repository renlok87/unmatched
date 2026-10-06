// VS-2 CP-08 (docs/game-design/visual/06-tasks/cards-portraits.csv CP-08; 02-visual-design.md §6.4, §6.5; 04-hud-spec.md
// §4.2, §4.3 WBP_UmPortrait, §2.2, §2.3, §1.10; HUD-AND-ICONS.md HI-05): the portrait circle of a player - the avatar
// PNG of the registry (Config/Cards/S08CardMedia.json portraits.*, CP-02) in the material M_UmPortraitDisc, our rim
// (mark.keyline outside, panel.edge inside), the turn ring outside the circle; the monogram only when the PNG is missing.
//
//   keys      the hero slug of the projection ("king-arthur", "medusa"), a sidekick "<hero>/<sidekick>" ("king-arthur/
//             merlin", "medusa/harpies") -> registry portrait:<hero>[:<sidekick>].
//   fallback  no key or no PNG: the monogram (S09TurnHud::Monogram) text.primary type.heading on a card.navy disc and a
//             Warning in the log; a harpy gets its number 1-3, never "H" (ВР-CP09, ВР-07, ВР-72).
//   rollback  -S08PortraitLegacy (ВР-CP08): the team-colour disc + monogram as before (ARTLOOK portraits=legacy(..)).
//   cap       ВР-CP04: the circle shown is at most 1.6 x the source circle in physical px - su = min(show su, 1.6 x src
//             circle px / (DPI x UI scale)); the rest is padding (the circle stays centred).
//   states    avatar; fallen (saturation 0); loser (saturation 0, opacity 0.6 over 400 ms; reduced motion - at once).
//   trace     PORTRAIT id=<key> tex=<path|monogram> su=<n> px=<n> scale=<x> show=<panel|room|slot|loading|result|lobby>
//             side=<own|opp> state=<..> capped=0|1 [n=<harpy 1..3>] (ВР-CP10); tools/s08/hud_contract/hud_contract.py
//             check-trace fails at scale > 1.6, at tex=monogram for a key the registry has and at a harpy without n 1..3.
//
// VS-2 CP-09...CP-12 (cards-portraits.csv): the four avatars in the circles of the accepted CP-07 crops (registry discs,
// variant B of art/imagegen/portrait-crop-v1-codex/portrait-crops.json); MakeDisc builds one circle of any show size
// (the panel's sidekick mini portraits 32 su, the review sheet 32...160 su) and MakeNumberBadge the harpy's number badge
// (02 §6.5, ВР-72): a card.navy disc 14 su with the mark.keyline 1 su, the digit card.cream in type.tag - Roboto Bold
// Condensed, em 14 su = cap 10 su, the font.card cap of 02 §6.5 - as runtime text (И-7: digits are never baked).
#pragma once

#include "CoreMinimal.h"
#include "UObject/ObjectPtr.h"

struct FUmCardMediaEntry;
class UMaterialInstanceDynamic;
class UTexture2D;
class UWidget;
class UWidgetTree;

enum class EUmPortraitState : uint8 { Avatar, Fallen, Loser };

/** One circle as shown - what its PORTRAIT line says (CP-09...CP-12). */
struct UNMATCHED_API FUmPortraitShown {
  FName Key;
  FString Tex;          // the texture's object path, "monogram" (no key / no PNG) or "legacy" (-S08PortraitLegacy)
  float ShowSu = 0.0f;  // the show size asked for
  float Su = 0.0f;      // the circle drawn (ВР-CP04: <= ShowSu)
  float SrcPx = 0.0f;   // the source circle (registry disc x source width)
  float PxPerSu = 1.0f;
  EUmPortraitState State = EUmPortraitState::Avatar;
  int32 Number = 0;     // a harpy 1..3 (the badge / the fallback digit), 0 = none
  bool IsAvatar() const { return Tex.StartsWith(TEXT("/")); }
  FString Line(const TCHAR* Show, const TCHAR* Side) const;
};

/** What MakeDisc draws. */
struct UNMATCHED_API FUmPortraitDiscSpec {
  FName Key;
  FString Name;          // the fallback monogram (S09TurnHud::Monogram)
  int32 Number = 0;      // a harpy 1..3: the fallback is the digit (ВР-CP09)
  float ShowSu = 32.0f;
  float PxPerSu = 1.0f;  // DPI x UI scale (the ВР-CP04 cap)
  EUmPortraitState State = EUmPortraitState::Avatar;
  bool bLegacy = false;  // -S08PortraitLegacy: the fallback without a warning (tex=legacy)
};

namespace UmPortrait {
inline const TCHAR* const MaterialPath = TEXT("/Game/S08/UI/Common/M_UmPortraitDisc.M_UmPortraitDisc");
inline const TCHAR* const WidgetBlueprintPath = TEXT("/Game/S08/UI/Common/WBP_UmPortrait");
// M_UmPortraitDisc parameters (tools/art/cards/ue_portrait_disc_material.py builds them; its --check reads these)
inline const TCHAR* const ParamAvatar = TEXT("Avatar");
inline const TCHAR* const ParamUvRect = TEXT("UVRect");
inline const TCHAR* const ParamDesaturation = TEXT("Desaturation");
inline const TCHAR* const ParamOpacity = TEXT("Opacity");
inline const TCHAR* const ParamEdgeColor = TEXT("EdgeColor");
inline const TCHAR* const ParamKeylineColor = TEXT("KeylineColor");
inline const TCHAR* const ParamFillColor = TEXT("FillColor");
inline const TCHAR* const ParamEdgeFrac = TEXT("EdgeFrac");
inline const TCHAR* const ParamKeylineFrac = TEXT("KeylineFrac");
/** The rim (02 §6.4): mark.keyline outside, panel.edge (card.cream at 0.45) inside it - 1 su + 1 su, the accepted CP-07
 *  frame (portrait-crop-v1 README; replaces the 1.5 su of ВР-VS2-31, ВР-VS2-63). */
inline constexpr float KeylineSu = 1.0f;
inline constexpr float EdgeSu = 1.0f;
/** 02 §6.5 / ВР-72: the harpy's number badge. */
inline constexpr float BadgeSu = 14.0f;
inline constexpr float BadgeKeylineSu = 1.0f;
/** ВР-CP04: px shown <= 1.6 x px of the source circle. */
inline constexpr float CapScale = 1.6f;
/** 04 §1.10: the loser fades to 0.6 with saturation 0 over 400 ms. */
inline constexpr float LoserOpacity = 0.6f;
inline constexpr float LoserMs = 400.0f;

/** "King Arthur" -> "king-arthur" (lower case, spaces -> '-', anything but a-z 0-9 '-' dropped). */
UNMATCHED_API FString SlugOf(const FString& Name);
/** "king-arthur" -> portrait:king-arthur, "medusa/harpies" -> portrait:medusa:harpies (nullptr: not in the registry). */
UNMATCHED_API const FUmCardMediaEntry* Find(FName Key);
/** "<hero>/<sidekick>". */
UNMATCHED_API bool IsSidekickKey(FName Key);
/** The fallback text: a harpy (medusa/harpies) with a number 1..3 -> the digit; otherwise the monogram of Name. */
UNMATCHED_API FString FallbackText(FName Key, const FString& Name, int32 SidekickNumber = 0);
/** The source circle in px: disc diameter x source width (the registry's numbers). */
UNMATCHED_API float SourceCirclePx(const FUmCardMediaEntry& Entry);
/** The UV rectangle of the disc in the padded texture: (minU, minV, maxU, maxV). */
UNMATCHED_API FVector4 UvRect(const FUmCardMediaEntry& Entry);
/** ВР-CP04: the circle su shown for a show size (su) at DPI x UI scale (px per su). */
UNMATCHED_API float CappedSu(float ShowSu, float SrcCirclePx, float PxPerSu);
/** The M_UmPortraitDisc parameters of a circle of CircleSu: the avatar, its UV rectangle, our rim (panel.edge at the
 *  token alpha, mark.keyline), the card.navy fill (VS-2 HB-18: the panel's sidekick mini portraits share it). */
UNMATCHED_API void SetupDiscMid(UMaterialInstanceDynamic& Mid, const FUmCardMediaEntry& Entry, UTexture2D* Tex, float CircleSu);
UNMATCHED_API float Desaturation(EUmPortraitState State);
UNMATCHED_API float Opacity(EUmPortraitState State);
UNMATCHED_API const TCHAR* StateName(EUmPortraitState State);
/** 'PORTRAIT id=.. tex=.. su=.. px=.. scale=.. show=.. side=.. state=.. capped=0|1 [n=..]' (scale = px shown / source
 *  circle px, 0 for a monogram; capped = the ВР-CP04 cap made the circle smaller than ShowSu; n = a harpy's number). */
UNMATCHED_API FString TraceLine(FName Key, const FString& Texture, float Su, float PxPerSu, float SrcCirclePx,
                                const TCHAR* Show, const TCHAR* Side, EUmPortraitState State, float ShowSu = 0.0f,
                                int32 Number = 0);
/** One circle of Spec.ShowSu x Spec.ShowSu: the avatar in M_UmPortraitDisc (the ВР-CP04 cap, centred; the rim; the state)
 *  or the fallback - a card.navy disc with the monogram / a harpy's digit in text.primary and a Warning in the log.
 *  The MID goes to KeepAlive (the owner's UPROPERTY). */
UNMATCHED_API UWidget* MakeDisc(UWidgetTree& Tree, UObject* Outer, const FUmPortraitDiscSpec& Spec, FUmPortraitShown& Out,
                                TArray<TObjectPtr<UObject>>& KeepAlive);
/** The harpy's number badge BadgeSu (02 §6.5, ВР-72): card.navy disc + mark.keyline, the digit card.cream type.tag. */
UNMATCHED_API UWidget* MakeNumberBadge(UWidgetTree& Tree, int32 Number);
}  // namespace UmPortrait

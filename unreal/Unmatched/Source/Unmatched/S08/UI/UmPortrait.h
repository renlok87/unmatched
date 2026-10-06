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
//             side=<own|opp> (ВР-CP10); tools/s08/hud_contract/hud_contract.py check-trace fails at scale > 1.6 or
//             tex=monogram for a key the registry has.
#pragma once

#include "CoreMinimal.h"

struct FUmCardMediaEntry;

enum class EUmPortraitState : uint8 { Avatar, Fallen, Loser };

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
/** The rim (02 §6.4): mark.keyline outside, panel.edge inside it (ВР-VS2-31: 1 su + 1.5 su). */
inline constexpr float KeylineSu = 1.0f;
inline constexpr float EdgeSu = 1.5f;
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
UNMATCHED_API float Desaturation(EUmPortraitState State);
UNMATCHED_API float Opacity(EUmPortraitState State);
UNMATCHED_API const TCHAR* StateName(EUmPortraitState State);
/** 'PORTRAIT id=.. tex=.. su=.. px=.. scale=.. show=.. side=..' (scale = px shown / source circle px; 0 for a monogram). */
UNMATCHED_API FString TraceLine(FName Key, const FString& Texture, float Su, float PxPerSu, float SrcCirclePx,
                                const TCHAR* Show, const TCHAR* Side, EUmPortraitState State);
}  // namespace UmPortrait

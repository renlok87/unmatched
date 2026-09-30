// W5b-R (ART-005 board readability, advisor decisions D-2/D-3,
// docs/game-design/decisions/2026-09-29-board-readability-decisions.md):
// the ABSOLUTE team of a fighter (P1 = the room seat 0 / host, P2 = the other
// seat), its palette (hud-style-tokens.json team.p1 / team.p2, one source with
// art/um-materials/um-masters.json team_palette) and the team ring geometry of
// the art figures. World-free: automation-tested in S08BoardArtTests.cpp.
// Colours are sRGB hex in the data and reach UE only through
// FLinearColor::FromSRGBColor(FColor::FromHex(hex)) (HUD-RULES P3, AD-OPEN-39).
#pragma once

#include "CoreMinimal.h"

struct FS08RoomPlayer;

enum class ES08TeamSlot : uint8 { P1, P2 };

/** -S08TeamColorMode=: absolute (default, D-2) = the seat team; relative = the
 *  viewer's team looks like P1 (A/B for the user, step 9). */
enum class ES08TeamColorMode : uint8 { Absolute, Relative };

inline const TCHAR* S08TeamSlotName(ES08TeamSlot Slot) { return Slot == ES08TeamSlot::P1 ? TEXT("P1") : TEXT("P2"); }
inline const TCHAR* S08TeamShapeName(ES08TeamSlot Slot) {
  return Slot == ES08TeamSlot::P1 ? TEXT("circle") : TEXT("hexagon");
}
inline const TCHAR* S08TeamColorModeName(ES08TeamColorMode Mode) {
  return Mode == ES08TeamColorMode::Relative ? TEXT("relative") : TEXT("absolute");
}
/** "" / "absolute" -> Absolute, "relative" -> Relative; anything else false. */
UNMATCHED_API bool S08ParseTeamColorMode(const FString& Text, ES08TeamColorMode& Out);

/** The owner id of team P1: the player with the lowest seatOrder of the room
 *  (Players are sorted by seat, FS08FlowController); without room players the
 *  host id; empty when neither is known (bench: the caller falls back to the
 *  fighter id prefix "f-0-", the seat-0 roster of the backend projection). */
UNMATCHED_API FString S08TeamP1OwnerId(const TArray<FS08RoomPlayer>& PlayersBySeat, const FString& HostId);

/** Absolute team of a fighter: P1 when its owner is the P1 owner; with an empty
 *  P1 owner, by the fighter id prefix ("f-0-" = P1). */
UNMATCHED_API ES08TeamSlot S08TeamOf(const FString& FighterId, const FString& OwnerId, const FString& P1OwnerId);

/** The slot whose LOOK (ring shape + colour) a fighter gets: its absolute team,
 *  or with Relative the viewer's team drawn as P1 and the opponent as P2. */
UNMATCHED_API ES08TeamSlot S08TeamLook(ES08TeamSlot Team, bool bOwn, ES08TeamColorMode Mode);

namespace S08TeamPalette {
/** hud-style-tokens.json colors (tools/art/tests/test_t53_readability.py PaletteConsistency checks this header against the JSON). */
inline const TCHAR* const P1Hex = TEXT("#E8C06A");        // team.p1 (Gold)
inline const TCHAR* const P2Hex = TEXT("#5A7F9F");        // team.p2 (Silver, W4-B value split)
inline const TCHAR* const P1ScreenHex = TEXT("#DAC576");  // team.p1.screen (measured on-screen ring fill)
inline const TCHAR* const P2ScreenHex = TEXT("#5786A8");  // team.p2.screen
inline const TCHAR* const KeylineHex = TEXT("#111317");   // mark.keyline
inline const TCHAR* const RimHex = TEXT("#FFFFFF");       // team.rim (5c-B1: light rim of the two-tone ring edge;
                                                          // #F2ECDE -> the plan fallback #FFFFFF in B1-2)
/** Ring fill as the game-layer LayerColor: FromSRGBColor(FromHex(team hex)). */
UNMATCHED_API FLinearColor RingFill(ES08TeamSlot Slot);
UNMATCHED_API FLinearColor Keyline();
UNMATCHED_API FLinearColor Rim();
/** UI chip colour (sRGB bytes, drawn through FLinearColor(FColor) = FromSRGBColor):
 *  the measured ON-SCREEN colour of the ring fill, so the chip equals the ring
 *  for the viewer (the ring passes the tonemapper, the UI does not). */
UNMATCHED_API FColor ChipColor(ES08TeamSlot Slot);
}  // namespace S08TeamPalette

/** Team ring of an art figure (tools/art/t53_team_ring.py RING_SPEC; the meshes
 *  /Game/ArtTests/ARTMarkers/Meshes/SM_Marker_TeamRing_P1/_P2). Hero size; the
 *  client scales XY by the figure scale (sidekicks 0.78). */
namespace S08TeamRingSpec {
constexpr float ZMin = 0.6f;
constexpr float ZMax = 1.2f;
constexpr float SidekickScale = 0.78f;
// 5c-B1 B1-3 (plan rev 2): two-tone edge - the outer keyline keeps its r3 width, a light rim (team.rim) sits
// outside it, paid for by the fill (r3: P1 fill 23.5-26.5, keyline out 26.5-28.0; P2 fill 23.0-26.0, 26.0-27.0).
// P1 circle (radius, uu)
constexpr float P1KeylineIn0 = 22.0f, P1Fill0 = 23.5f, P1Fill1 = 26.0f, P1KeylineOut1 = 27.5f, P1RimOut1 = 28.5f;
// P2 hexagon (apothem, uu; corners at 0/60/.../300 deg from +X) + a gap across each corner through every band
constexpr float P2KeylineIn0 = 21.5f, P2Fill0 = 23.0f, P2Fill1 = 25.25f, P2KeylineOut1 = 26.25f, P2RimOut1 = 27.25f;
constexpr float P2CornerGapUU = 2.0f;
/** SM_Marker_TargetRing arcs: outer radius (blender/ASSET-MARKERS-001/build_markers.py: inner 20.9, outer 23). */
constexpr float TargetArcOuterUU = 23.0f;
/** SM_Marker_SelectionRing: inner 17.8, outer 20. */
constexpr float SelectionRingOuterUU = 20.0f;
/** FigureScreenRect half-size with the ring (hero / sidekick): the outer ring edge (5c-B1: the rim, was 28.0). */
constexpr float HeroRectRadiusUU = P1RimOut1;
constexpr float SidekickRectRadiusUU = P1RimOut1 * SidekickScale;  // 22.23
inline const TCHAR* MeshPath(ES08TeamSlot Slot) {
  return Slot == ES08TeamSlot::P1 ? TEXT("/Game/ArtTests/ARTMarkers/Meshes/SM_Marker_TeamRing_P1")
                                  : TEXT("/Game/ArtTests/ARTMarkers/Meshes/SM_Marker_TeamRing_P2");
}
inline const TCHAR* const KeylineMaterialPath = TEXT("/Game/ArtTests/ARTMarkers/Materials/MI_Marker_TeamRing_Keyline");
inline const TCHAR* const FillMaterialPath = TEXT("/Game/ArtTests/ARTMarkers/Materials/MI_Marker_TeamRing_Fill");
/** 5c-B1: material slot 2 of both ring meshes (slots: 0 Keyline, 1 Fill, 2 Rim). */
inline const TCHAR* const RimMaterialPath = TEXT("/Game/ArtTests/ARTMarkers/Materials/MI_Marker_TeamRing_Rim");
/** Outer boundary of the ring's top face in the cell plane (hero size, uu): P1 a
 *  96-gon at radius 28.5 (the rim), P2 the six trimmed outer hexagon edges of the
 *  rim (each side two points; the corner gaps open the polygon, so it is
 *  returned side by side). */
UNMATCHED_API void OuterEdges(ES08TeamSlot Slot, TArray<TPair<FVector2D, FVector2D>>& OutSegments);
/** Top-face polygons (quads) of the fill band (hero size, uu). */
UNMATCHED_API void FillQuads(ES08TeamSlot Slot, TArray<TArray<FVector2D>>& OutQuads);
}  // namespace S08TeamRingSpec

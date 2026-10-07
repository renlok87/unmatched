// ART-005 / stage 3 T3.2: data-driven -ArtPreview board art, world-free.
//
// The board art of AS08BoardActor used to be a Cobble-only special case
// (SupportsCobbleArt: 5x6, every cell exactly one of blue/red). This module
// generalises it to any boardState grid - W x H, N zone keys, multizone cells,
// obstacles - driven by data in Config/ArtBoards/S08ArtBoardProfiles.json:
//   * zoneStyles: per zone KEY (never per board) a stroke pattern along a cell
//     side, a glyph shape and a colour (sRGB) or a material;
//   * lightProfiles: exactly 1 directional light with shadow + <= 6 point
//     lights without shadows; point spots are board-relative and authored
//     apart from the gameplay zones (light sections != zones);
//   * boards: profile selection by Board row id, else by the boardState
//     signature (W x H + exact zone-key set), surface kind, light profile and
//     the expected cell/zone counts that the live trace is checked against.
// A multizone cell keeps every zone: zone i draws its stroke on side i (0 near
// +Y, 1 left -X, 2 far -Y, 3 right +X) and its glyph in slot i, so the zones
// stay distinct by shape even without colour (03 §4.5/§6). Everything here is
// a pure function of the data and the decoded board (automation-tested in
// S08BoardArtTests.cpp); AS08BoardActor only turns the layouts into ISM
// instances and light actors.
//
// ENV-MAPS track S (docs/art-pipeline/ENV-MAPS-PLAN.md, user decisions ENV-U1/U3/U7): a topology board
// (FS08BoardModel::bHasTopology - Marmoreal / Sarpedon on their original space graph) gets the surface
// 'map-image': the WHOLE original illustration (1337 x 866 px) as one flat plane at 2/3 uu per px
// (891.333 x 577.333 uu, ENV-O1) on the stone tray, a wooden frame and the ART-005 iron corners around it,
// no lattice tiles, no slab, no zone marks (the zones are the painted ones). Such a profile is selected by
// the Board row id only (no W x H signature) and its expect block counts spaces / links / zones instead of
// W x H cells. The map textures stay OUT of git: tools/art/map_surface/ue_import_map_surface.py imports
// them into /Game/EnvMaps/<Name>/ (Content/ is gitignored); without the import the board falls back to the
// grey topology view (traced 'ARTPREVIEW map-image missing <path>').
#pragma once

#include "CoreMinimal.h"
#include "S08BoardModel.h"
#include "S08HeroLight.h"
#include "S08ConceptPaste.h"

/** Zone mark geometry (uu, z above the tile top z = 0). W5b-R D-4: strokes moved inside the slab (nominal centre
 *  line 42, clamped so that fill + keyline <= 45), dark keylines under every stroke and glyph, glyphs above strokes:
 *  top faces - stroke keyline 0.33 < stroke fill 0.48 < glyph keyline 0.53 < glyph fill 0.58 < team ring 1.2. */
namespace S08ZoneMarkSpec {
constexpr float EdgeUU = 42.0f;          // nominal stroke centre line (was 46 = the slab edge, T5.2)
constexpr float MaxOuterUU = 45.0f;      // any stroke fill + keyline stays within this distance of the cell centre
constexpr float SlabHalfUU = 46.0f;      // 'tiles' slab half size (ArtTileScaleXY 0.92 x 50)
constexpr float KeylineGrowUU = 1.5f;    // keyline width on each side of a stroke / glyph piece
constexpr float StrokeZ = 0.28f;         // stroke fill centre (depth 0.4 -> 0.08..0.48)
constexpr float StrokeDepth = 0.004f;
constexpr float StrokeKeylineZ = 0.18f;  // stroke keyline centre (depth 0.3 -> 0.03..0.33)
constexpr float KeylineDepth = 0.003f;
constexpr float GlyphZ = 0.38f;          // glyph anchor / fill centre (depth 0.4 -> 0.18..0.58); keyline 0.23..0.53
constexpr float GlyphDepth = 0.004f;
}  // namespace S08ZoneMarkSpec

/** ENV-MAPS track S: the map-image surface and the topology game layer (uu; z relative to the play plane z = 0
 *  where the figures stand). The tray top is S08Diorama::TopZ = -3. */
namespace S08MapSurfaceSpec {
constexpr float PlaneZ = -0.5f;            // map plane: above the tray top (-3), under the figures (no z-fight)
constexpr float DefaultFrameUU = 24.0f;    // wooden frame around the map (the 'tiles' ArtFrameUU look)
constexpr float FrameCentreZ = -3.0f;      // frame bars: same height / depth as the 'tiles' frame (top +4)
// Reachable ring of a topology board (art): 12 cube pieces on a circle INSIDE the painted rim (rim centre line
// 62.4 px = 41.6 uu), clear of the team ring (outer 28.5 uu), at the L-corner height of the grid boards.
constexpr float RingRadiusUU = 36.0f;
constexpr float RingWidthUU = 3.0f;
constexpr int32 RingSegments = 12;
constexpr float RingZ = 1.8f;
constexpr float RingDepth = 0.005f;        // cube z scale (0.5 uu)
// Grey topology view (no art profile or map assets missing): one disc per space (the painted circle size
// 2 x 63 px = 84 uu), thin link bars between the linked spaces, all on a dark canvas plane of the map size.
constexpr float GreyDiscDiameterUU = 84.0f;
constexpr float GreyDiscDepth = 0.02f;     // cylinder z scale (2 uu: -2..0, top on the play plane)
constexpr float GreyLinkWidthUU = 5.0f;
constexpr float GreyLinkZ = -0.3f;         // bar centre (depth 0.2 uu: -0.4..-0.2, above the canvas -0.5)
constexpr float GreyLinkDepth = 0.002f;
// Reachable (grey) and illegal (grey and art) marks of a topology board: a flat disc instead of a square.
constexpr float MarkDiscDiameterUU = 70.0f;
constexpr float MarkDiscZ = 1.5f;
constexpr float MarkDiscDepth = 0.02f;
// Invisible cursor-trace box over the map (QueryOnly, Visibility): top face on the play plane.
constexpr float PickBoxHalfZ = 1.0f;
inline const TCHAR* const AssetRoot = TEXT("/Game/EnvMaps/");
/** The SDF and space-ID textures (not sampled by M_MapBoard yet) live under <DataRoot><Name>/, which
 *  DefaultGame.ini never cooks (DirectoriesToNeverCook /Game/EnvMaps/Data): ~0.4 GB of 4K float data stays out of
 *  the pak. Move them out (and drop that line) once M_MapBoard samples them - the cooker drops a never-cook
 *  package even when a cooked asset references it. */
inline const TCHAR* const DataRoot = TEXT("/Game/EnvMaps/Data/");
inline const TCHAR* const PlaneMeshPath = TEXT("/Engine/BasicShapes/Plane.Plane");
inline const TCHAR* const CylinderMeshPath = TEXT("/Engine/BasicShapes/Cylinder.Cylinder");
/** M_MapBoard texture parameters (tools/art/map_surface/ue_import_map_surface.py builds the material). */
inline const TCHAR* const ParamBaseColor = TEXT("BaseColor");
inline const TCHAR* const ParamGameMask = TEXT("GameMask");
/** M_MapBoard night-grade parameters (ENV-MAPS P2: a light profile's "mapGrade" sets them on the map MID). */
inline const TCHAR* const ParamNightEV = TEXT("NightEV");
inline const TCHAR* const ParamNightSaturation = TEXT("NightSaturation");
inline const TCHAR* const ParamLift = TEXT("Lift");
inline const TCHAR* const ParamNightTint = TEXT("NightTint");
/** ENV-MAPS P4 (M_MapBoard graph v2, zone separation inside the game mask): a mask-only saturation of the lit share,
 *  a mask-only inverse tint (cancels the cool lit gain inside the circles) and the saturation of the emissive lift.
 *  Identity defaults (1, 1, (1,1,1)) keep the graph-v1 look; a graph-v1 material simply lacks them (traced). */
inline const TCHAR* const ParamMaskSaturation = TEXT("MaskSaturation");
inline const TCHAR* const ParamLiftSaturation = TEXT("LiftSaturation");
inline const TCHAR* const ParamMaskInverseTint = TEXT("MaskInverseTint");
/** ENV-MAPS P4 readability materials (map-image boards only; built out of git by ue_import_map_surface.py, cooked
 *  through DirectoriesToAlwaysCook /Game/EnvMaps). A missing one keeps the old look (traced). */
inline const TCHAR* const FrameWoodMaterialPath = TEXT("/Game/EnvMaps/M_MapFrameWood.M_MapFrameWood");
inline const TCHAR* const ParamFrameValueScale = TEXT("FrameValueScale");  // linear albedo multiplier
inline const TCHAR* const ParamFrameSaturation = TEXT("FrameSaturation");
inline const TCHAR* const ContactShadowMaterialPath = TEXT("/Game/EnvMaps/M_MapContactShadow.M_MapContactShadow");
inline const TCHAR* const ParamShadowStrength = TEXT("Strength");
inline const TCHAR* const ParamShadowSoftness = TEXT("Softness");
// Readability geometry (uu, z relative to the play plane): the contact-shadow blob lies between the map plane
// (-0.5) and the team ring (+0.6); the leader pip sits on the near side (+Y, towards the K1 camera) just outside the
// team ring, at the team-ring height band; its dark keyline under it.
constexpr float ContactShadowZ = -0.25f;
constexpr float ContactShadowOffsetX = 4.0f;  // along the key light (-55, 30, 0): the shadow falls to +X / +Y
constexpr float ContactShadowOffsetY = 3.0f;
// pip centre = team ring outer radius x ring scale + gap; the keyline diamond (half diagonal 5.6) clears the team
// ring (28.5) on the inside and stays inside the painted rim (41.6): 28.5 + 6 = 34.5, 28.9 .. 40.1
constexpr float LeaderPipGapUU = 6.0f;
constexpr float LeaderPipSizeUU = 5.5f;       // diamond side (cube rotated 45 deg)
constexpr float LeaderPipZ = 1.1f;            // fill 0.5 .. 1.7
constexpr float LeaderPipDepth = 0.012f;
constexpr float LeaderPipKeylineUU = 1.2f;    // keyline grows the diamond by this much per side
constexpr float LeaderPipKeylineZ = 0.9f;     // keyline 0.5 .. 1.3 (under the fill top)
constexpr float LeaderPipKeylineDepth = 0.008f;
// Reachable ring stroke (map-image readability): the dark outer stroke sits under the fill (top 1.8 < fill top 2.05)
// and above the team ring (bottom 1.4 > 1.2).
constexpr float ReachStrokeZ = 1.6f;
constexpr float ReachStrokeDepth = 0.004f;
/** ENV-O8 T1: the placeholder tray is stretched non-uniformly under a map (see S08Diorama.h). */
inline const TCHAR* const TrayWaiver = TEXT("T1-placeholder");
/** ENV-MAPS P5 track C (concept review gap 9, full): the heavy modular frame ASSET-MAP-FRAME-002 (Blender lane K,
 *  art/pipeline-candidates/ASSET-MAP-FRAME-002/20261001-frame-v1), imported out of git by
 *  tools/art/env_kit/ue_import_map_frame.py into /Game/EnvMaps/Frame (cooked with /Game/EnvMaps). A profile "mapFrame"
 *  block {"kit": "frame-002"} replaces the 4 cube bars AND the ART-005 corner brackets of a map-image board with the
 *  20 module instances of S08MapFrame002Layout; a missing mesh keeps the bars + brackets (traced). Slot
 *  M_MapFrame002_Wood takes the frame-wood material of the profile (MapFrameMaterial), slot M_MapFrame002_Iron keeps
 *  its MI (child of M_EnvProp). */
inline const TCHAR* const Frame002Kit = TEXT("frame-002");
inline const TCHAR* const Frame002CornerPath = TEXT("/Game/EnvMaps/Frame/SM_MapFrame002_Corner.SM_MapFrame002_Corner");
inline const TCHAR* const Frame002SegAPath = TEXT("/Game/EnvMaps/Frame/SM_MapFrame002_SegA.SM_MapFrame002_SegA");
inline const TCHAR* const Frame002SegBPath = TEXT("/Game/EnvMaps/Frame/SM_MapFrame002_SegB.SM_MapFrame002_SegB");
inline const TCHAR* const Frame002SegMidPath = TEXT("/Game/EnvMaps/Frame/SM_MapFrame002_SegMid.SM_MapFrame002_SegMid");
inline const TCHAR* const Frame002IronMaterialPath = TEXT("/Game/EnvMaps/Frame/MI_MapFrame002_Iron.MI_MapFrame002_Iron");
inline const TCHAR* const Frame002WoodSlot = TEXT("M_MapFrame002_Wood");
inline const TCHAR* const Frame002IronSlot = TEXT("M_MapFrame002_Iron");
constexpr double Frame002SegmentUU = 157.0;         // straight module length (frame-params.json modules.segment_uu)
constexpr double Frame002CornerLegUU = 53.1666667;  // corner leg along each side from the inner map corner
constexpr float Frame002FrameUU = 24.0f;            // the modules' wood width = the profile frameUU they need
constexpr float Frame002IronProudUU = 2.0f;         // iron straps / rivets beyond FrameHalf (onto the ground strips)
/** ENV-MAPS P5 track C (concept review gap 8): the procedural night backdrop of a map-image board (profile "backdrop"
 *  block): <= 2 large unlit translucent mist planes far under the tray and one soft moon-glow card in the upper-left of
 *  the far zoom view (K1 x 0.65). Materials built out of git by tools/art/map_surface/ue_import_map_surface.py; both
 *  have Apply Fogging off (the night fog starts at 2900 uu and would wash them out) and light nothing (unlit, no
 *  shadow, no GI / distance field / reflection-capture contribution). */
inline const TCHAR* const BackdropMistMaterialPath = TEXT("/Game/EnvMaps/M_MapBackdropMist.M_MapBackdropMist");
inline const TCHAR* const BackdropMoonMaterialPath = TEXT("/Game/EnvMaps/M_MapBackdropMoon.M_MapBackdropMoon");
inline const TCHAR* const ParamBackdropTint = TEXT("Tint");            // vector (linear)
inline const TCHAR* const ParamBackdropOpacity = TEXT("Opacity");      // mist: peak opacity
inline const TCHAR* const ParamBackdropSize = TEXT("SizeUU");          // mist: plane size (x, y) uu
inline const TCHAR* const ParamBackdropPan = TEXT("PanUU");            // mist: pan (x, y) uu per second
inline const TCHAR* const ParamBackdropNoiseScale = TEXT("NoiseScaleUU");
inline const TCHAR* const ParamBackdropEdgeFade = TEXT("EdgeFade");    // mist: elliptic edge fade (fraction of the radius)
inline const TCHAR* const ParamBackdropCoverage = TEXT("Coverage");    // mist: 0 = clear .. 1 = solid
inline const TCHAR* const ParamBackdropSeed = TEXT("Seed");
inline const TCHAR* const ParamBackdropIntensity = TEXT("Intensity");  // moon: glow intensity
inline const TCHAR* const ParamBackdropSoftness = TEXT("Softness");    // moon: gaussian width (fraction of the radius)
inline const TCHAR* const ParamBackdropDiscRadius = TEXT("DiscRadius");
inline const TCHAR* const ParamBackdropDiscIntensity = TEXT("DiscIntensity");
/** ENV-MAPS P5c (P5b review: the Marmoreal moon read as a hard flat disc): the disc edge falloff as a fraction of the disc
 *  radius (0.15 = the P5 edge) and a limb shading 0..1 (0 = flat, the P5 look) of M_MapBackdropMoon graph 2. */
inline const TCHAR* const ParamBackdropDiscSoftness = TEXT("DiscSoftness");
inline const TCHAR* const ParamBackdropDiscLimb = TEXT("DiscLimb");
constexpr int32 BackdropMaxMist = 2;
/** Every backdrop part stays below this Z (the T2b rocky tray bottom is at about -216): the opaque tray, frame and props
 *  are always in front of it, so the backdrop can never draw over the board. */
constexpr float BackdropMaxZ = -250.0f;
constexpr float BackdropMinZ = -4000.0f;
/** Two mist layers at least this far apart in Z (no translucency sort flicker between them). */
constexpr float BackdropMinLayerGapUU = 100.0f;
/** The far zoom view the moon is anchored in: K1 fit / FarViewRatio (= FS08CameraZoom::OverviewOutRatio, S08ArtHud.h;
 *  2880.2 uu on the maps), the camera of AS08FlowGameMode::SetupCameraForBoard (pitch -55, yaw -90, hfov 35, 16:9). */
constexpr float BackdropFarViewRatio = 0.65f;
constexpr int32 BackdropTranslucencySortPriority = -10;  // drawn before the game-layer translucents
}  // namespace S08MapSurfaceSpec

enum class ES08ZoneStroke : uint8 { Solid, Dash2, Dash3, Dash4, Dots5, Double, DashDot };
enum class ES08ZoneGlyph : uint8 { Diamond, Bar1, Bars2, Bars3, HBars2, Square, Cross, X, Tee, Chevron, Ring };
enum class ES08BoardSurface : uint8 { Tiles, MapImage };
enum class ES08ProfileMatch : uint8 { None, BoardId, Signature };

UNMATCHED_API const TCHAR* S08ZoneStrokeName(ES08ZoneStroke Stroke);
UNMATCHED_API const TCHAR* S08ZoneGlyphName(ES08ZoneGlyph Glyph);
UNMATCHED_API const TCHAR* S08BoardSurfaceName(ES08BoardSurface Surface);
UNMATCHED_API const TCHAR* S08ProfileMatchName(ES08ProfileMatch Match);
UNMATCHED_API bool S08ParseZoneStroke(const FString& Name, ES08ZoneStroke& Out);
UNMATCHED_API bool S08ParseZoneGlyph(const FString& Name, ES08ZoneGlyph& Out);

struct UNMATCHED_API FS08ZoneStyle {
  FString Key;
  ES08ZoneStroke Stroke = ES08ZoneStroke::Dots5;
  ES08ZoneGlyph Glyph = ES08ZoneGlyph::Bar1;
  FColor Color = FColor::White;  // sRGB bytes: use FLinearColor(Color) for a Tint
  FString MaterialPath;          // optional authored material (Cobble blue/red, -S08LegacyRender only)
  /** T4.2: MI_ART005_Zone_<Key> (child of the game-layer master M_UM_GameLayer, LayerColor = this colour) under
   *  /Game/ArtTests/ART005/Zones; empty = a runtime tint MID of the game-layer material (pre-T4.2 behaviour). */
  FString MaterialInstancePath;
  bool bFallback = false;
  FString ColorHex() const;
};

/** W5b-R D-4: the dark keyline under zone strokes and glyphs ("zoneKeyline" of the profile data, rev 4). */
struct UNMATCHED_API FS08ZoneKeyline {
  bool bSet = false;
  FColor Color = FColor(17, 19, 23, 255);  // #111317 = hud-style-tokens mark.keyline
  float GrowUU = S08ZoneMarkSpec::KeylineGrowUU;
  FString MaterialInstancePath;              // MI_ART005_Zone_Keyline (game-layer master)
  TMap<FString, FString> GlyphMeshPaths;     // glyph name -> SM_ART005_ZoneGlyphKey_<Glyph>
};

struct UNMATCHED_API FS08LightSpec {
  FString Name;
  FString Role;  // fill | warm | cool | key
  bool bDirectional = false;
  bool bHasPosUU = false;
  FVector PosUU = FVector::ZeroVector;  // absolute world position
  FVector2D At = FVector2D::ZeroVector; // board-relative: world XY = At * (W, H) * 100 (map-image: At * map size uu)
  float AtZ = 0.0f;
  FRotator Rotation = FRotator::ZeroRotator;  // directional: FRotator(Pitch, Yaw, Roll)
  float Intensity = 0.0f;
  float RadiusUU = 0.0f;
  bool bHasColor = false;
  FLinearColor Color = FLinearColor::White;  // linear
  bool bCastShadows = false;
};

/** W4-A: Movable SkyLight of a profile (replaces the point "ambient", memo §1
 *  item 3). The cubemap is a long-lat TextureCube; intensity scales it. */
struct UNMATCHED_API FS08SkySpec {
  bool bSet = false;
  FString CubemapPath;
  float Intensity = 1.0f;
  FLinearColor Color = FLinearColor::White;  // linear
  bool bLowerHemisphereIsBlack = false;
  FLinearColor LowerHemisphereColor = FLinearColor::Black;
};

/** W4-A: fixed exposure of a profile (unbound post-process volume, histogram
 *  with min == max brightness + bias; the range is never widened). */
struct UNMATCHED_API FS08ExposureSpec {
  bool bSet = false;
  float MinBrightness = 1.0f;
  float MaxBrightness = 1.0f;
  float Bias = 0.0f;
  float Ev100 = 0.0f;  // informational: 2^Ev100 == brightness (ExtendDefaultLuminanceRange off)
};

/** W4-A: key-light CSM fitted to the diorama camera (optional). */
struct UNMATCHED_API FS08KeyShadowSpec {
  bool bSet = false;
  float DistanceUU = 0.0f;       // DynamicShadowDistanceMovableLight
  int32 Cascades = 0;            // DynamicShadowCascades
  float ContactShadowLength = 0.0f;
};

/** ENV-MAPS P2 night calibration (optional "fog" block): one ExponentialHeightFog actor, so the void around the
 *  diorama reads as a dark night haze instead of the black clear colour. A scene actor, not a renderer setting:
 *  no volumetric fog, Lumen and the scalability untouched. StartDistanceUU keeps the board itself out of it. */
struct UNMATCHED_API FS08FogSpec {
  bool bSet = false;
  FLinearColor Color = FLinearColor::Black;  // FogInscatteringLuminance (linear)
  float Density = 0.02f;                     // FogDensity
  float HeightFalloff = 0.2f;                // FogHeightFalloff
  float HeightZ = 0.0f;                      // actor Z = the fog height
  float StartDistanceUU = 0.0f;              // StartDistance
  float EndDistanceUU = 0.0f;                // EndDistance (0 = none)
  float MaxOpacity = 1.0f;                   // FogMaxOpacity
};

/** ENV-MAPS P2 (optional "mapGrade" block): the night grade of the M_MapBoard MID on a map-image board
 *  (NightEV, NightSaturation, Lift, NightTint); overrides the MI values of ue_import_map_surface.py at runtime,
 *  because the grade belongs to the night light it is calibrated with. Ignored on grid boards. */
struct UNMATCHED_API FS08MapGradeSpec {
  bool bSet = false;
  float NightEV = -0.7f;
  float NightSaturation = 0.7f;
  float Lift = 0.35f;
  bool bHasTint = false;
  FLinearColor NightTint = FLinearColor::White;  // linear
  /** ENV-MAPS P4 (optional, M_MapBoard graph v2): zone separation inside the game mask under the night light.
   *  maskSaturation scales the chroma of the lit share inside the mask (luma kept), maskInverseTintLinear multiplies
   *  the lit share inside the mask (cancels the cool lit gain), liftSaturation scales the chroma of the emissive lift.
   *  Identity (1, (1,1,1), 1) = the graph-v1 look. Ranges: saturations 0..3, inverse tint 0..4. */
  float MaskSaturation = 1.0f;
  float LiftSaturation = 1.0f;
  FLinearColor MaskInverseTint = FLinearColor::White;  // linear
  bool HasMaskTerms() const {
    return MaskSaturation != 1.0f || LiftSaturation != 1.0f || MaskInverseTint != FLinearColor::White;  // exact: Equals(.., 0) is always false (strict <)
  }
};

/** AN-32 (ВР-16): one hero's Fix values of a light profile's "heroMaterials" block - the Fix group of
 *  M_UM_Figure_v2 v2.4 driven over a MID (S08ArtBoardProfiles.json lightProfiles.<id>.heroMaterials). Neutral
 *  defaults change nothing: the figure keeps its MI exactly (no MID is created). */
struct UNMATCHED_API FS08HeroMaterialFix {
  int32 ClassA = -1;     // MatID class 0..15, -1 = off
  float GainA = 1.0f;    // BaseColor gain of the class
  float SpecA = 0.0f;    // specular delta
  int32 ClassB = -1;
  float GainB = 1.0f;
  float SpecB = 0.0f;
  bool IsNeutral() const {
    return ClassA < 0 && ClassB < 0 && GainA == 1.0f && GainB == 1.0f && SpecA == 0.0f && SpecB == 0.0f;
  }
};

struct UNMATCHED_API FS08LightProfile {
  FString Id;
  bool bHasDirectional = false;
  FS08LightSpec Directional;
  TArray<FS08LightSpec> Points;
  /** W4-A G01 units: "candelas" for points, "lux" for the directional. Both
   *  empty = a pre-W4 profile: points spawn Unitless as the old packaged
   *  builds did (x1/625 against the editor probes) - legacy, never reference. */
  FString PointUnits;
  FString DirectionalUnits;
  bool HasPhysicalUnits() const { return PointUnits == TEXT("candelas") && DirectionalUnits == TEXT("lux"); }
  FS08SkySpec Sky;
  FS08ExposureSpec Exposure;
  FS08KeyShadowSpec KeyShadow;
  FS08FogSpec Fog;
  FS08MapGradeSpec MapGrade;
  /** ENV-MAPS P9 (docs/art-pipeline/ENV-HERO-LIGHT.md, S08HeroLight.h): the optional per-figure "heroLight" rig (lighting
   *  channel 1, figures only); a separate category outside the 1 key + <= 6 points budget below. */
  FS08HeroLightSpec HeroLight;
  /** AN-32 (ВР-16): the "heroMaterials" block - hero key -> look ("P1" / "P2" / "*") -> the Fix values. */
  TMap<FString, TMap<FString, FS08HeroMaterialFix>> HeroMaterials;
  /** The fix of a hero for a look: the look's own entry, else "*", else the neutral default. */
  const FS08HeroMaterialFix& HeroMaterialFix(const FString& HeroKey, const FString& Look) const;
  /** 1 directional with shadow + <= 6 points without shadows. */
  bool BudgetOk(FString& OutReason) const;
};

struct UNMATCHED_API FS08BoardExpect {
  int32 Cells = -1;
  int32 ZoneCells = -1;
  int32 MultizoneCells = -1;
  int32 Obstacles = -1;
  TMap<FString, int32> ZoneCellCounts;
  /** ENV-MAPS (map-image profiles): spaces (cells with a layout), undirected links and the exact zone-key set
   *  (sorted); -1 / empty = not checked. A map-image expect never states W x H cells (the lattice is a server
   *  detail of the topology contract). */
  int32 Spaces = -1;
  int32 Links = -1;
  TArray<FString> Zones;
};

/** ENV-MAPS track S: the 'map-image' surface data of a board profile ("mapImage" block). Every asset path is a
 *  /Game/EnvMaps/<Name>/ package (SDF / space ID: /Game/EnvMaps/Data/<Name>/, never cooked) imported by
 *  tools/art/map_surface/ue_import_map_surface.py (out of git, ENV-U3/U7); the source size and the scale MUST equal the FS08LayoutFrame defaults the game mode's board model
 *  uses for CellToWorld (the Shipped test pins it), so the figures stand on the painted circles. */
struct UNMATCHED_API FS08MapImageSpec {
  bool bSet = false;
  FString Name;                  // 'Marmoreal' | 'Sarpedon' (asset folder and trace)
  FString BaseColorPath;         // "bc": T_<Name>_Map_BC_4K (sRGB)
  FString MaskPath;              // "mask": T_<Name>_Map_GameMask_4K (linear)
  FString SdfPath;               // "sdf": Data/<Name>/T_<Name>_Map_GameSDF_4K (RGBA16F, not sampled by M_MapBoard yet; never cooked)
  FString SpaceIdPath;           // "id": Data/<Name>/T_<Name>_Map_SpaceID_4K (R16F, nearest, no mips; not sampled yet; never cooked)
  FString MaterialInstancePath;  // "materialInstance": MI_<Name>_MapBoard (parent /Game/EnvMaps/M_MapBoard)
  FString ManifestPath;          // "manifest": tools/art/map_surface/manifest.<key>.json (sha256 of the sources)
  FIntPoint SrcSizePx = FIntPoint(1337, 866);
  float UuPerPx = FS08LayoutFrame::DefaultUuPerPx;
  float FrameUU = S08MapSurfaceSpec::DefaultFrameUU;
  /** ENV-O8 T1: optional XY shift of the tray under the map (extra rim on one side, S08Diorama::FitTray). */
  FVector2D TrayOffsetUU = FVector2D::ZeroVector;

  FVector2D SizeUU() const { return FVector2D(SrcSizePx.X * UuPerPx, SrcSizePx.Y * UuPerPx); }
  FVector2D HalfUU() const { return SizeUU() * 0.5; }
  /** Half extent of the map plus its wooden frame (the tray fits around this). */
  FVector2D FrameHalfUU() const { return HalfUU() + FVector2D(FrameUU, FrameUU); }
  /** Map px (continuous, x right / y down as the topology layout) -> world (map centre at the origin, Z = 0):
   *  X = (px.x / W - 0.5) * W * UuPerPx, Y = (px.y / H - 0.5) * H * UuPerPx (= FS08LayoutFrame::ToWorld). */
  FVector PxToWorld(const FVector2D& Px) const;
  /** bc, mask, sdf, id, materialInstance (in this order). */
  TArray<FString> AssetPaths() const;
  /** True when SrcSizePx / UuPerPx equal the given layout frame (the board model's CellToWorld frame). */
  bool MatchesLayoutFrame(const FS08LayoutFrame& Frame) const;
  /** True when SrcSizePx / UuPerPx equal the FS08LayoutFrame defaults (the game mode's CellToWorld frame). */
  bool MatchesDefaultLayoutFrame() const;
};

/** ENV-MAPS P4 (concept review 2026-10-01 'readability'): the optional "readability" block of a board profile. Only a
 *  'map-image' board may carry it (the parser rejects it on grids, so Cobble and the art fixtures stay bit for bit);
 *  every sub-block is optional and off when absent. Status: предложено (proposed, not artistically accepted). */
struct UNMATCHED_API FS08BoardReadabilitySpec {
  bool bSet = false;
  /** "labelPlates": screen tags on a dark semi-opaque rounded plate with a 1 px team-colour outline, placed with a
   *  hard padding so stacked tags keep a gap (S08ArtHud::FLabelPlacementInput::HardPadPx). */
  bool bLabelPlates = false;
  /** "reach": the reachable-space ring in a colour outside the zone palette with a thin dark outer stroke and more
   *  segments (the default map ring is 12 mint-green pieces). */
  bool bReach = false;
  FColor ReachColor = FColor(255, 200, 87, 255);  // sRGB bytes ("colorSrgb")
  FColor ReachStroke = FColor(20, 17, 12, 255);   // sRGB bytes ("strokeSrgb")
  int32 ReachSegments = 48;                       // 12..96
  float ReachWidthUU = 3.5f;                      // fill width (radial), 1..6
  float ReachStrokeUU = 1.0f;                     // stroke per side, 0.25..3
  /** "contactShadow": a soft dark blob (M_MapContactShadow, modulate) under every fighter base. */
  bool bContactShadow = false;
  float ShadowDiameterUU = 64.0f;  // at ring scale 1 (a sidekick's blob scales with its team ring), 20..160
  float ShadowStrength = 0.5f;     // 0..1 darkening at the centre
  float ShadowSoftness = 0.55f;    // gaussian width as a fraction of the radius, 0.1..1
  /** "leaderPip": a small team-colour diamond on the near side of every hero's base (Medusa vs the Harpies). */
  bool bLeaderPip = false;
  /** "frameWood": the map frame on M_MapFrameWood (the ART-005 wood, darker and less saturated). */
  bool bFrameWood = false;
  float FrameValueScaleSrgb = 0.7f;  // display value (V) multiplier 0.2..1; the material gets its linear power 2.2
  float FrameSaturation = 0.75f;     // 0..1
  /** Linear albedo multiplier of FrameValueScaleSrgb (V^2.2). */
  float FrameValueScaleLinear() const { return FMath::Pow(FMath::Clamp(FrameValueScaleSrgb, 0.0f, 1.0f), 2.2f); }
};

/** ENV-MAPS P5 track C (gap 9 full): the optional "mapFrame" block of a map-image board ({"kit": "frame-002"}, the
 *  only kit; the profile's mapImage.frameUU must be the modules' 24 uu). Absent = the cube bars + ART-005 brackets. */
struct UNMATCHED_API FS08MapFrameSpec {
  bool bSet = false;
  FString Kit;
};

/** One mist plane of the backdrop: the engine plane (100 uu, normal +Z) scaled to 2 x HalfUU at (CenterUU, ZUU). */
struct UNMATCHED_API FS08BackdropMistSpec {
  float ZUU = -400.0f;                                      // BackdropMinZ .. BackdropMaxZ
  FVector2D CenterUU = FVector2D::ZeroVector;               // |x|, |y| <= 4000
  FVector2D HalfUU = FVector2D(1900.0, 1350.0);             // 500 .. 8000 each
  FLinearColor Color = FLinearColor(0.3f, 0.38f, 0.62f);    // linear, 0..4 ("colorLinear")
  float Opacity = 0.3f;                                     // peak opacity (0, 0.8]
  float NoiseScaleUU = 700.0f;                              // 50 .. 5000 (the largest noise octave)
  FVector2D PanUUPerSec = FVector2D(6.0, -3.0);             // |x|, |y| <= 100 (a slow drift)
  float EdgeFade = 0.3f;                                    // 0.05 .. 0.5 of the elliptic radius
  float Coverage = 0.5f;                                    // 0 .. 1
  float Seed = 0.0f;                                        // 0 .. 1000
};

/** The moon-glow card: the engine plane facing the camera (parallel to the screen) at DepthUU along the ray of
 *  ScreenAnchor (NDC of the far zoom view: x right, y up, -1..1). */
struct UNMATCHED_API FS08BackdropMoonSpec {
  bool bSet = false;
  FVector2D ScreenAnchor = FVector2D(-0.9, 0.82);
  float DepthUU = 5200.0f;                                  // 500 .. 20000 from the far camera
  float DiameterUU = 1800.0f;                               // 50 .. 5000
  FLinearColor Color = FLinearColor(0.72f, 0.8f, 1.0f);     // linear, 0..4
  float Intensity = 1.0f;                                   // (0, 50]
  float Softness = 0.4f;                                    // 0.05 .. 1
  float DiscRadius = 0.06f;                                 // 0 .. 0.5 of the card radius (0 = glow only)
  float DiscIntensity = 2.0f;                               // 0 .. 50
  float DiscSoftness = 0.15f;                               // 0.02 .. 0.95 of the disc radius (P5c; 0.15 = the P5 edge)
  float DiscLimb = 0.0f;                                    // 0 .. 1 limb shading (P5c; 0 = flat, the P5 disc)
};

/** ENV-MAPS P5 track C (gap 8): the optional "backdrop" block of a map-image board (grids reject it). Status:
 *  предложено. Mist: 0..BackdropMaxMist layers, each below BackdropMaxZ, layers >= BackdropMinLayerGapUU apart in Z;
 *  the moon card is optional and must also stay below BackdropMaxZ; at least one part. */
struct UNMATCHED_API FS08BackdropSpec {
  bool bSet = false;
  TArray<FS08BackdropMistSpec> Mist;
  FS08BackdropMoonSpec Moon;
};

/** MS-T-08 (docs/game-design/move-selection/04 §4.7, MS-D-24, MS-R-50): the move-selection style - the root
 *  "moveSelection" block of the document (defaults of every board) and boards[i].moveSelection (an override of any
 *  field for one board, allowed on EVERY surface: it is not part of "readability", which grids reject). The code
 *  defaults below are the 04 §4.7 numbers, so a document without both blocks draws the same. Status: предложено
 *  until the user's art acceptance (MS-Q-04); live tune (MS-T-13) edits the values without a relaunch. Parsed by
 *  S08ParseMoveSelection; S08ValidateMoveSelection keeps the plate inside the space (03 §4.1, MS-R-72). */
struct UNMATCHED_API FS08MoveSelectionSpec {
  // "plate" (V-01..V-12, 03 §4.1 / §4.2): radii in uu from the space centre, z above the play plane
  FColor PlateColor = FColor(0xF2, 0xE9, 0xD8, 255);  // "colorSrgb" (a map board overrides it, 03 §4.2b)
  FColor KeylineColor = FColor(0x11, 0x13, 0x17, 255); // "keylineSrgb" (mark.keyline)
  float FillAlpha = 0.18f;
  float RingCenterUU = 36.0f;
  float RingWidthUU = 3.5f;
  float KeylineUU = 1.5f;
  float OutlineInnerUU = 39.6f;
  float OutlineOuterUU = 41.0f;
  float OccupiedClearUU = 30.0f;  // nothing of the plate at r <= this on a space with a living fighter
  float PipCutDeg = 15.0f;        // half angle of the cut around the leader pip (+Y) on a hero's space
  float ZFill = 0.3f;
  float ZRing = 0.9f;
  // "boostTier" (V-02 / V-04b)
  int32 DashCount = 12;
  float DashDuty = 0.6f;
  FColor ChipBgColor = FColor(0x16, 0x1A, 0x28, 255);
  FColor ChipTextColor = FColor(0xF2, 0xEC, 0xDE, 255);
  // "path" (V-03, MS-T-09)
  FColor PathColor = FColor(0xFF, 0xF4, 0xDC, 255);
  float PathWidthUU = 6.0f;
  float PathKeylineUU = 1.5f;
  float StepDotUU = 8.0f;
  float PathZ = 1.5f;
  // "ghost" (V-04 / MS-R-71, MS-T-10)
  float GhostAlpha = 0.45f;
  float GhostAlphaSent = 0.30f;
  float LeavingFighterAlpha = 0.5f;
  // "invalid" (V-08)
  FColor InvalidColor = FColor(0xD9, 0x48, 0x3F, 255);
  int32 InvalidMs = 350;
  // "lastMove" (V-14 / V-15, MS-T-17)
  float LastMoveAlpha = 0.6f;
  int32 LastMoveFadeMs = 300;
  // "candidate" (V-17, MS-R-75 - DE-017): a thin ring under an own fighter that may move, in the band of the
  // selection ring V-05 (SM_Marker_SelectionRing 17.8..20 uu), thinner than it and without the team ring; the radius
  // scales with the figure (sidekicks 0.78); z above the figure's pedestal top.
  float CandidateRadiusUU = 18.9f;
  float CandidateWidthUU = 1.2f;
  float CandidateAlpha = 0.7f;
  float CandidateZ = 1.6f;
  // "anim" (04 §6.3, MS-T-16): numbers only here; hopHeightRel 0 = glide without a hop (D-DE-02)
  int32 StepMs = 280;
  int32 CapFighterMs = 1400;
  int32 CapManeuverMs = 2400;
  int32 MinStepMs = 90;
  float Overlap = 0.3f;
  int32 PlaceMs = 240;
  float HopHeightRel = 0.0f;
  int32 TurnMs = 120;
  int32 StartTurnMs = 50;
  float TravelLeanDeg = 10.0f;
  int32 LeanInMs = 60;
  int32 SettleMs = 150;
  bool bEaseEnds = false;
  /** Where the values came from: "code" (no block), "root" (the root block only), "board" (a board override). */
  FString Source = TEXT("code");

  float RingInnerUU() const { return RingCenterUU - RingWidthUU * 0.5f; }
  float RingOuterUU() const { return RingCenterUU + RingWidthUU * 0.5f; }
  /** The ring with its keyline on both sides: [RingInnerUU - KeylineUU, RingOuterUU + KeylineUU]. */
  float RingBandInnerUU() const { return RingInnerUU() - KeylineUU; }
  float RingBandOuterUU() const { return RingOuterUU() + KeylineUU; }
};

/** Applies a "moveSelection" object onto InOut (absent fields keep InOut's value: the root block starts from the code
 *  defaults, a board block from the root). Context names the block in the errors ("root", "board <id>"). Unknown
 *  sub-blocks / fields and out-of-range values are errors (a broken block rejects the document - never a silent
 *  default, like the other profile blocks). Validates the result with S08ValidateMoveSelection. */
UNMATCHED_API bool S08ParseMoveSelection(const FString& Context, const TSharedPtr<FJsonObject>& Object,
                                         FS08MoveSelectionSpec& InOut, TArray<FString>& OutErrors);
/** 03 §4.1 / 04 §4.7 geometry: the ring with its keyline inside [30, 40] uu, the outline inside [39.6, 41.6] (the
 *  painted rim) and outside the ring band, the occupied clear radius <= the ring band, the pip cut 0..45 deg. */
UNMATCHED_API bool S08ValidateMoveSelection(const FString& Context, const FS08MoveSelectionSpec& Spec,
                                            TArray<FString>& OutErrors);

struct UNMATCHED_API FS08BoardArtProfile {
  FString Id;
  TArray<FString> MatchBoardIds;
  int32 MatchWidth = 0;
  int32 MatchHeight = 0;
  TArray<FString> MatchZoneKeys;  // sorted
  ES08BoardSurface Surface = ES08BoardSurface::Tiles;
  FString LightId;
  bool bArtFixture = false;
  /** "glyphs": "zone" (default) = glyph in the zone colour (unlit tint),
   *  "review" = the ART-005 review glyph material (Cobble, kept exact). */
  bool bZoneColorGlyphs = true;
  FS08BoardExpect Expect;
  /** ENV-MAPS: the "mapImage" block (bSet only on surface 'map-image'). */
  FS08MapImageSpec Map;
  /** ENV-U9 (user decision 2026-09-30, "Отъехать до ≈×1,25"): optional "k1DistanceMul" in [MinK1DistanceMul,
   *  MaxK1DistanceMul], default 1. The K1 overview = the board fit (S08K1FitDistanceUU) x this, see
   *  S08K1OverviewDistanceUU. The two map-image profiles set 1.25 (1872.156 -> 2340.195 uu: the env layout around
   *  the frame is in the overview); every grid profile keeps 1, so Cobble stays at 1931 uu bit for bit.
   *  AS08BoardActor::GetK1DistanceMul returns it only while the profile is active (1 on a refused profile). */
  float K1DistanceMul = 1.0f;
  static constexpr float MinK1DistanceMul = 1.0f;  // never nearer than the fit (the whole board stays in K1)
  static constexpr float MaxK1DistanceMul = 2.0f;
  /** ENV-MAPS P4: optional "readability" block (map-image boards only, see FS08BoardReadabilitySpec). */
  FS08BoardReadabilitySpec Readability;
  /** ENV-MAPS P5 track C: optional "mapFrame" / "backdrop" blocks (map-image boards only). */
  FS08MapFrameSpec MapFrame;
  FS08BackdropSpec Backdrop;
  /** ENV-MAPS P7 (ENV-U15): optional "conceptPaste" block (map-image boards only; S08ConceptPaste.h). Its lights count
   *  against the light profile's points (profile points + block lights <= 6, the block hides the layout lights). */
  FS08ConceptPasteSpec ConceptPaste;
  /** MS-T-08: the move-selection style of this board - the root "moveSelection" with this board's override applied
   *  (Source "board" when the profile has its own block). */
  FS08MoveSelectionSpec MoveSelection;
  /** VS-4 V3 (IC-62...IC-69, FX-38; 02 §7.4, ВР-32, ВР-68): optional "zoneIconSrgb" {zone key: "#RRGGBB"} - the disc
   *  colour of the zone icon at a hovered space, the measured colours of the run I frames (never the pale topology hex);
   *  a key without an entry shows no icon. Live tune reloads it with the profile. */
  TMap<FName, FColor> ZoneIconSrgb;
};

/** Counts of one decoded board (what the art and the trace describe). */
struct UNMATCHED_API FS08BoardSummary {
  int32 Width = 0;
  int32 Height = 0;
  int32 Cells = 0;
  int32 ZoneCells = 0;       // passable-or-not cells with >= 1 zone
  int32 MultizoneCells = 0;  // cells with >= 2 zones
  int32 TripleZoneCells = 0; // cells with >= 3 zones
  int32 Obstacles = 0;       // wall/obstacle/closed door/unknown
  TArray<FString> ZoneKeys;  // sorted, unique
  TMap<FString, int32> ZoneCellCounts;
  /** ENV-MAPS: FS08BoardModel::bHasTopology; Spaces = cells with a layout, Links = undirected pairs of the
   *  symmetrised neighbour lists, Starts = spaces with a start number (all 0 on a grid). */
  bool bTopology = false;
  int32 Spaces = 0;
  int32 Links = 0;
  int32 Starts = 0;
};

UNMATCHED_API FS08BoardSummary S08SummarizeBoard(const FS08BoardModel& Board);

class UNMATCHED_API FS08BoardArtData {
public:
  int32 Revision = 0;
  FString Status;
  /** sha256 of the loaded file bytes (RENDER fingerprint), empty for ParseJson. */
  FString SourceSha256;
  TMap<FString, FS08ZoneStyle> ZoneStyles;
  FS08ZoneStyle FallbackStyle;
  TMap<FString, FS08LightProfile> Lights;
  TArray<FS08BoardArtProfile> Boards;
  /** T4.2 "glyphMeshes": glyph name (S08ZoneGlyphName) -> SM_ART005_ZoneGlyph_<Glyph> package. A glyph mesh is
   *  exactly the S08GlyphPieces cubes merged, pivot on the slot centre at the mark height (S08GlyphAnchor); a glyph
   *  without a mesh keeps the cube pieces. */
  TMap<FString, FString> GlyphMeshPaths;
  /** W5b-R D-4 zone keylines (bSet = the profile has a valid "zoneKeyline" block). */
  FS08ZoneKeyline Keyline;
  /** MS-T-08: the root "moveSelection" block (code defaults without one) - the style of a board without a profile. */
  FS08MoveSelectionSpec MoveSelection;

  /** <ProjectConfigDir>/ArtBoards/S08ArtBoardProfiles.json (staged as a UFS
   *  runtime dependency of the Unmatched module, see Unmatched.Build.cs). */
  static FString DefaultPath();
  /** DefaultPath(), or -ArtBoardProfiles=<abs path> (diagnostic override:
   *  calibration and the pre-W4 bench leg; the fingerprint marks it, and
   *  the evidence tools never accept such frames as reference). */
  static FString ResolvePath(bool& bOutOverride);
  /** Parses and validates the whole document. Invalid entries are reported;
   *  a light profile over budget or a board pointing at a missing light
   *  profile makes the document invalid (false). */
  bool ParseJson(const FString& Text, TArray<FString>& OutErrors);
  bool LoadFile(const FString& Path, TArray<FString>& OutErrors);

  /** Style of a zone key; unknown keys get the fallback style (bFallback). */
  FS08ZoneStyle StyleFor(const FString& Key) const;
  const FS08LightProfile* LightFor(const FS08BoardArtProfile& Profile) const;
  /** Board row id first, then W x H + exact zone-key set (grids only: a topology board matches by id or not at
   *  all); nullptr = no art. */
  const FS08BoardArtProfile* Select(const FS08BoardModel& Board, const FString& BoardId,
                                    ES08ProfileMatch& OutMatch) const;
};

/** Empty when the summary matches the profile's expect block. */
UNMATCHED_API FString S08ExpectMismatch(const FS08BoardArtProfile& Profile, const FS08BoardSummary& Summary);

/** One cube instance of a zone mark, in board-actor space (the actor sits at
 *  the world origin, so this is also world space). */
struct UNMATCHED_API FS08ZoneMarkPiece {
  FString Key;
  FIntPoint Cell = FIntPoint::ZeroValue;
  int32 Slot = 0;  // zone index within the cell (side / glyph slot)
  FTransform Transform;
};

struct UNMATCHED_API FS08ZoneMarkLayout {
  TArray<FS08ZoneMarkPiece> Strokes;
  TArray<FS08ZoneMarkPiece> Glyphs;
  /** T4.2: one entry per zone of a cell - the glyph slot centre at the mark height (translation only), where one
   *  instance of the zone's glyph mesh replaces that zone's cube pieces in Glyphs. */
  TArray<FS08ZoneMarkPiece> GlyphAnchors;
  /** W5b-R D-4: keyline cube pieces under every stroke / glyph (NOT in the *ByKey counts). */
  TArray<FS08ZoneMarkPiece> StrokeKeylines;
  TArray<FS08ZoneMarkPiece> GlyphKeylines;
  TMap<FString, int32> StrokePiecesByKey;
  TMap<FString, int32> GlyphPiecesByKey;
  TMap<FString, int32> CellsByKey;
  TArray<FString> FallbackKeys;
  int32 MultizoneCells = 0;
  int32 MultizoneZonesListed = 0;  // sum of zones over multizone cells
  int32 MultizoneZonesMarked = 0;  // of those, zones with >= 1 stroke AND >= 1 glyph piece
  TArray<FString> MultizoneLines;  // "(x,y) a+b strokeSides=0+1 glyphSlots=0+1 marked=2/2"
};

/** Zone strokes along cell sides (height 0.28 uu above the play plane) and
 *  glyphs in the cell slots, for every zone of every cell. Zones beyond the
 *  fourth of a cell reuse side/slot (i % 4) - never dropped. */
UNMATCHED_API FS08ZoneMarkLayout S08BuildZoneMarks(const FS08BoardModel& Board, const FS08BoardArtData& Data);
/** Stroke / glyph cube pieces relative to the cell centre (for tests too). */
UNMATCHED_API void S08StrokePieces(ES08ZoneStroke Stroke, int32 Side, TArray<FTransform>& Out);
UNMATCHED_API void S08GlyphPieces(ES08ZoneGlyph Glyph, int32 Slot, TArray<FTransform>& Out);
/** W5b-R D-4: the keyline pieces - every piece grown by KeylineGrowUU per side, under the fill (S08ZoneMarkSpec). */
UNMATCHED_API void S08StrokeKeylinePieces(ES08ZoneStroke Stroke, int32 Side, TArray<FTransform>& Out);
UNMATCHED_API void S08GlyphKeylinePieces(ES08ZoneGlyph Glyph, int32 Slot, TArray<FTransform>& Out);
/** Largest |across offset| + half thickness of a stroke's segments (fill only, uu). */
UNMATCHED_API float S08ZoneStrokeHalfExtentUU(ES08ZoneStroke Stroke);
/** Stroke centre line from the cell centre: min(EdgeUU, MaxOuterUU - KeylineGrowUU - half extent). */
UNMATCHED_API float S08ZoneStrokeCenterUU(ES08ZoneStroke Stroke);
/** Outermost distance of a stroke's fill (or fill + keyline) from the cell centre. */
UNMATCHED_API float S08ZoneStrokeOuterUU(ES08ZoneStroke Stroke, bool bKeyline);
/** T4.2: glyph slot centre relative to the cell centre, at the glyph height (W5b-R: z = 0.38 uu, above the strokes):
 *  the pivot of the glyph and glyph-keyline meshes, so S08GlyphPieces(Glyph, Slot) == pieces of
 *  S08GlyphPieces(Glyph, 0) moved by the anchor difference. */
UNMATCHED_API FVector S08GlyphAnchor(int32 Slot);

struct UNMATCHED_API FS08PlacedLight {
  FS08LightSpec Spec;
  FVector Position = FVector::ZeroVector;
};

/** World placement of a light profile on a board (directional first). */
UNMATCHED_API TArray<FS08PlacedLight> S08PlaceLights(const FS08LightProfile& Profile, const FS08BoardModel& Board);
/** ENV-MAPS: the same with the board-relative spots scaled by an explicit board size in uu (a map-image profile
 *  passes its map size 891.333 x 577.333, never the W x H lattice); posUU spots stay absolute. */
UNMATCHED_API TArray<FS08PlacedLight> S08PlaceLights(const FS08LightProfile& Profile, const FVector2D& BoardSizeUU);

// ---- ENV-MAPS track S: world-free helpers of the map-image surface and the topology game layer -------------

/** Half extent (uu) the K1 camera, the light spots and the tray are fitted to: a topology board -> its map
 *  canvas (FS08LayoutFrame::ExtentUU / 2 = 445.667 x 288.667 by default), a grid -> W x H x 50 (the old value,
 *  bit for bit). */
UNMATCHED_API FVector2D S08BoardHalfExtentUU(const FS08BoardModel& Board);
/** K1 overview distance of AS08FlowGameMode::SetupCameraForBoard for a board half extent: horizontal FOV 35,
 *  16:9, pitch -55, 60 uu margin, x1.12 (Cobble 5x6 -> 1931 uu, the map canvas 891.333 x 577.333 -> 1872 uu). */
UNMATCHED_API float S08K1FitDistanceUU(const FVector2D& HalfExtentUU);
/** ENV-U9: the K1 overview distance (the camera's home view: the first frame, Space, and the reference of every zoom
 *  ratio of FS08CameraZoom) = the fit (S08K1FitDistanceUU) x K1DistanceMul (the active board profile's
 *  "k1DistanceMul"). K1DistanceMul == 1 returns FitDistanceUU itself, bit for bit (every grid: Cobble 5x6 -> 1931
 *  uu); the map-image boards (1.25) -> 1872.156 x 1.25 = 2340.195 uu. */
UNMATCHED_API float S08K1OverviewDistanceUU(float FitDistanceUU, float K1DistanceMul);
/** Undirected links of a topology board (FS08BoardModel::Neighbours, symmetrised), each pair once with the
 *  row-major smaller cell first, sorted; empty on a grid. */
UNMATCHED_API TArray<TPair<FIntPoint, FIntPoint>> S08BoardLinkPairs(const FS08BoardModel& Board);
/** Relative transform of /Engine/BasicShapes/Plane (100 x 100 uu, pivot centre, normal +Z) that lays a map of
 *  SizeUU at height Z with UV (0,0) on the far-left corner (-X, -Y), u along +X and v along +Y (manifest
 *  "X = (u - 0.5) * W, Y = (v - 0.5) * H"). The engine plane's UV orientation is pinned by the editor test
 *  Unmatched.S08.BoardArt.MapPlaneUV (it reports the observed mapping if this ever disagrees). */
UNMATCHED_API FTransform S08MapPlaneTransform(const FVector2D& SizeUU, float Z);
/** The fallback trace line: 'ARTPREVIEW map-image missing <path>'. */
UNMATCHED_API FString S08MapImageMissingLine(const FString& Path);
/** A ring of Segments cube pieces (engine cube, 100 uu) around the origin: centre line RadiusUU, width WidthUU,
 *  each piece tangent (outer edge = the circumscribed polygon, no gaps), top face at Z + DepthScale * 50. */
UNMATCHED_API void S08RingPieces(float RadiusUU, float WidthUU, int32 Segments, float Z, float DepthScale,
                                 TArray<FTransform>& Out);
/** A cube bar from A to B (XY), shortened by TrimUU at both ends (the disc radius), width WidthUU at height Z;
 *  false when nothing is left between the discs. */
UNMATCHED_API bool S08LinkBarTransform(const FVector& A, const FVector& B, float TrimUU, float WidthUU, float Z,
                                       float DepthScale, FTransform& Out);

// ---- ENV-MAPS P4 readability (map-image boards; world-free, automation-tested) ------------------------------

/** Reachable ring of a map-image board with a "reach" block: Fill = Segments tangent pieces of width ReachWidthUU on
 *  RingRadiusUU at RingZ; Stroke = the same circle, width ReachWidthUU + 2 x ReachStrokeUU, at ReachStrokeZ (under the
 *  fill, above the team ring). Without the block (bReach false): Fill = the default 12-piece ring, Stroke empty. */
UNMATCHED_API void S08ReachRingPieces(const FS08BoardReadabilitySpec& Spec, TArray<FTransform>& OutFill,
                                      TArray<FTransform>& OutStroke);
/** Leader pip of a hero on a map-image board, relative to the fighter actor (actor yaw 0 on the board): a diamond
 *  (engine cube, yaw 45) on the near side (+Y) at radius RingOuterUU x RingScale + LeaderPipGapUU, and its keyline
 *  diamond under it. */
UNMATCHED_API void S08LeaderPipTransforms(float RingOuterUU, float RingScale, FTransform& OutFill, FTransform& OutKeyline);
/** Contact-shadow blob relative to the fighter actor: /Engine/BasicShapes/Plane (100 uu) scaled to
 *  ShadowDiameterUU x RingScale, shifted along the key light, at ContactShadowZ. */
UNMATCHED_API FTransform S08ContactShadowTransform(const FS08BoardReadabilitySpec& Spec, float RingScale);
/** "#RRGGBB" of a colour (trace lines). */
UNMATCHED_API FString S08ColorHex(const FColor& Color);

// ---- ENV-MAPS P5 track C: heavy modular map frame + night backdrop (world-free, automation-tested) -------------

enum class ES08FrameModule : uint8 { Corner, SegA, SegB, SegMid };
UNMATCHED_API const TCHAR* S08FrameModuleName(ES08FrameModule Module);  // Corner | A | B | Mid (frame-layout.json)
/** Asset path of a module (S08MapSurfaceSpec::Frame002*Path). */
UNMATCHED_API const TCHAR* S08FrameModulePath(ES08FrameModule Module);

struct UNMATCHED_API FS08FramePiece {
  FString Id;            // corner-near-east, near-0 .. (frame-layout.json ids)
  ES08FrameModule Module = ES08FrameModule::SegA;
  FVector Location = FVector::ZeroVector;  // board-actor space, z 0 (the module meshes carry their own heights)
  float YawDeg = 0.0f;
  float ScaleX = 1.0f;   // segment stretch along the side (1 on both shipped maps)
};

struct UNMATCHED_API FS08FrameLayout {
  TArray<FS08FramePiece> Pieces;
  int32 SegmentsX = 0;   // per long side (near / far)
  int32 SegmentsY = 0;   // per short side (east / west)
  double StretchX = 1.0;
  double StretchY = 1.0;
  /** Every side fits whole modules (|stretch - 1| < 1e-5). */
  bool bExactFit = false;
};

/** The 20 (on the shipped maps) module instances of ASSET-MAP-FRAME-002 around a map of half extent MapHalf - the C++
 *  mirror of art/pipeline-candidates/ASSET-MAP-FRAME-002/scripts/frame_layout.py placements(): 4 corners (pivot = the
 *  inner map corner; yaw 0 near-east, 90 near-west, 180 far-west, -90 far-east), then per side (near yaw 0 from -X,
 *  far yaw 180 from +X, east yaw -90 from +Y, west yaw 90 from -Y) round(fill / SegmentUU) segments from the corner leg
 *  on (fill = side - 2 x CornerLegUU), the middle one of an odd count 'Mid', the others alternating A / B (A first on
 *  near / far, B first on east / west). Another map size gets the nearest count and ScaleX = the stretch. */
UNMATCHED_API FS08FrameLayout S08MapFrame002Layout(const FVector2D& MapHalf,
                                                   double SegmentUU = S08MapSurfaceSpec::Frame002SegmentUU,
                                                   double CornerLegUU = S08MapSurfaceSpec::Frame002CornerLegUU);

/** The K1 camera of AS08FlowGameMode::SetupCameraForBoard at a distance: location (0, D cos 55, D sin 55), pitch -55,
 *  yaw -90 (looks along -Y; screen right = +X, screen up = far = -Y), horizontal fov 35, 16:9. */
struct UNMATCHED_API FS08BoardView {
  FVector Location = FVector::ZeroVector;
  FVector Forward = FVector::ForwardVector;
  FVector Right = FVector::RightVector;
  FVector Up = FVector::UpVector;
  double HalfTanH = 0.0;
  double HalfTanV = 0.0;
  static FS08BoardView AtDistance(double DistanceUU);
  /** World point -> NDC (x right, y up); false behind the camera. */
  bool Project(const FVector& World, FVector2D& OutNdc) const;
  /** Unit ray through an NDC point. */
  FVector Ray(const FVector2D& Ndc) const;
};

/** Far zoom distance of a map: S08K1FitDistanceUU(MapHalf) / BackdropFarViewRatio (2880.2 uu on the shipped maps). */
UNMATCHED_API double S08BackdropFarViewDistanceUU(const FVector2D& MapHalf);
/** Mist plane transform (engine plane, 100 uu, normal +Z, UV 0..1 over the plane). */
UNMATCHED_API FTransform S08BackdropMistTransform(const FS08BackdropMistSpec& Mist);
/** Moon card transform: centre on the far view's ray through ScreenAnchor at DepthUU, normal towards the camera
 *  (-Forward: parallel to the screen), scale DiameterUU / 100. OutTopZ = the highest Z of the card (its corners). */
UNMATCHED_API FTransform S08BackdropMoonTransform(const FS08BackdropMoonSpec& Moon, const FVector2D& MapHalf,
                                                  double* OutTopZ = nullptr);
/** Empty when every part of the backdrop stays below S08MapSurfaceSpec::BackdropMaxZ (the board is always in front of
 *  it) and the mist layers are BackdropMinLayerGapUU apart; else the reason (the parser rejects the board). */
UNMATCHED_API FString S08BackdropPlacementProblem(const FS08BackdropSpec& Spec, const FVector2D& MapHalf);

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
/** ENV-O8 T1: the placeholder tray is stretched non-uniformly under a map (see S08Diorama.h). */
inline const TCHAR* const TrayWaiver = TEXT("T1-placeholder");
}  // namespace S08MapSurfaceSpec

enum class ES08ZoneStroke : uint8 { Solid, Dash2, Dash3, Dash4, Dots5, Double, DashDot };
enum class ES08ZoneGlyph : uint8 { Diamond, Bar1, Bars2, Bars3, HBars2, Square, Cross, X, Tee, Chevron, Ring };
enum class ES08BoardSurface : uint8 { Tiles, Cobble5x6Mesh, MapImage };
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

struct UNMATCHED_API FS08BoardArtProfile {
  FString Id;
  TArray<FString> MatchBoardIds;
  int32 MatchWidth = 0;
  int32 MatchHeight = 0;
  TArray<FString> MatchZoneKeys;  // sorted
  ES08BoardSurface Surface = ES08BoardSurface::Tiles;
  FString LightId;
  bool bLegacyCobbleTrace = false;
  bool bArtFixture = false;
  /** "glyphs": "zone" (default) = glyph in the zone colour (unlit tint),
   *  "review" = the ART-005 review glyph material (Cobble, kept exact). */
  bool bZoneColorGlyphs = true;
  FS08BoardExpect Expect;
  /** ENV-MAPS: the "mapImage" block (bSet only on surface 'map-image'). */
  FS08MapImageSpec Map;
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

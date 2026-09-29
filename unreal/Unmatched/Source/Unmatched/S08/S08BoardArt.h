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
#pragma once

#include "CoreMinimal.h"
#include "S08BoardModel.h"

enum class ES08ZoneStroke : uint8 { Solid, Dash2, Dash3, Dash4, Dots5, Double, DashDot };
enum class ES08ZoneGlyph : uint8 { Diamond, Bar1, Bars2, Bars3, HBars2, Square, Cross, X, Tee, Chevron, Ring };
enum class ES08BoardSurface : uint8 { Tiles, Cobble5x6Mesh };
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

struct UNMATCHED_API FS08LightSpec {
  FString Name;
  FString Role;  // fill | warm | cool | key
  bool bDirectional = false;
  bool bHasPosUU = false;
  FVector PosUU = FVector::ZeroVector;  // absolute world position
  FVector2D At = FVector2D::ZeroVector; // board-relative: world XY = At * (W, H) * 100
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
  /** Board row id first, then W x H + exact zone-key set; nullptr = no art. */
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
/** T4.2: glyph slot centre relative to the cell centre, at the mark height (z = 0.28 uu): the pivot of the glyph
 *  meshes, so S08GlyphPieces(Glyph, Slot) == pieces of S08GlyphPieces(Glyph, 0) moved by the anchor difference. */
UNMATCHED_API FVector S08GlyphAnchor(int32 Slot);

struct UNMATCHED_API FS08PlacedLight {
  FS08LightSpec Spec;
  FVector Position = FVector::ZeroVector;
};

/** World placement of a light profile on a board (directional first). */
UNMATCHED_API TArray<FS08PlacedLight> S08PlaceLights(const FS08LightProfile& Profile, const FS08BoardModel& Board);

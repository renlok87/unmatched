// Wave 5c-B: the diorama tray ASSET-TABLE-BASE-001 (SM_TableBase, Tripo c2e5e3bf -> Blender -> UE,
// docs/art-pipeline/table-base-report.md) under the live S08 art board, behind the opt-in flag
// -ArtPreviewDiorama (only together with -ArtPreview). Without the flag the board actor creates no
// component and loads nothing from here: the board is byte-for-byte the previous one.
//
// Placement (report "Исправление по ревью"): the tray pivot is the board centre, its flat top lies on
// Z = -3 (the nearest board horizontal is the tile top at -1.2: no z-fight), the mesh is 756 x 656 x 150 uu
// (half 378 x 328 in mesh space) = the ART-005 Cobble board (world +-278 x +-328 at yaw -90) plus a 50 uu
// rim. The actor stays at (0,0,0) with NoCollision (the instanced tiles remain the only click surfaces).
//
// FitTray is world-free and automation-tested (S08DioramaTests.cpp): the long axis of the tray (mesh X)
// follows the long axis of the board frame, the XY scale keeps the 50 uu rim around the frame. On the
// Cobble 5x6 mesh this is exactly yaw -90 / scale 1 (the report placement); the 'tiles' art-fixture boards
// (8x5, 7x5) get yaw 0 and a traced XY scale (a measured technical fit, no art acceptance).
// Trace: "ARTPREVIEW diorama tray=<mesh path> mi=<name> surface=<s> yaw=<deg> scale=<x>x<y>x<z> bounds=(..)..(..) ..."
//
// ENV-MAPS (ENV-O8 T1, explicit waiver): under the 'map-image' surface (map 891.333 x 577.333 uu + 24 uu wooden
// frame, aspect 1.50) the Cobble-sized tray (aspect 1.15) is stretched NON-UNIFORMLY, ~1.375 x 1.106 (anisotropy
// ~1.24): the rock skirt and the rim texels stretch along X. The Blender stage limits the non-uniformity of the
// tray body to 5 %; the map-image surface runs under an explicit, traced waiver of that rule (field
// 'waiver=T1-placeholder' of the tray line) as the plan's T1 placeholder, until the T2 modular skirt (corners +
// segments, Blender) replaces it. (The 5c-B2 'tiles' art fixtures carry their own measured technical fit.) An
// optional XY offset of the profile shifts the tray: the rim stays RimUU on the side the offset points away from
// and grows by 2 |offset| on the other.
//
// ENV-U10 (track TRAY, 2026-10-01) - T2 replaces that stretch on the map-image boards: SM_TableBase_T2 is the ONE shared
// rocky tray of both maps ("единая каменная подложка"; art/pipeline-candidates/ASSET-TABLE-BASE-001/20261001-tray-t2:
// a modular rock kit - convex chunk library -> side / corner modules -> instanced around the perimeter with rigid
// transforms and uniform scale only - built in headless Blender, imported by tools/art/env_kit/ue_import_tray_t2.py).
// Its flat top at TopZ is exactly 2 T2TopHalfX x 2 T2TopHalfY (= the env layouts' shared "tray"), its pivot is the
// centre of that top (Z = play plane); the rocky lip rises to Z +2 only within T2RimUU of the edge and overhangs it by
// <= 30 uu, the cliff hangs <= 180 uu below the top. The board actor places it at (0, tray offsetY, 0), yaw 0, SCALE 1
// (FitTrayT2): no stretch and no waiver; its trace line carries 'kind=T2'. T1 (MeshPath + FitTray) stays the tray of
// every grid board, and the map-image fallback with 'waiver=T1-placeholder' only when T2 is not in the build.
#pragma once

#include "CoreMinimal.h"

namespace S08Diorama {

/** Command-line flag (with -ArtPreview): -ArtPreviewDiorama. */
inline const TCHAR* const FlagName = TEXT("ArtPreviewDiorama");
inline const TCHAR* const MeshPath =
    TEXT("/Game/PipelineCandidates/TableBase/20260928-table-base-tripo-h31/Meshes/SM_TableBase");
inline const TCHAR* const MaterialPath =
    TEXT("/Game/PipelineCandidates/TableBase/20260928-table-base-tripo-h31/Materials/MI_TableBase_Candidate");

/** Mesh-space half extent of SM_TableBase (UE bounds (-378,-328,-153)..(378,328,-3)). */
constexpr float MeshHalfX = 378.0f;
constexpr float MeshHalfY = 328.0f;
constexpr float TopZ = -3.0f;
constexpr float BottomZ = -153.0f;
/** Flat rim from the board frame to the outer tray edge (report: 46.5..47 uu flat + 3 uu chamfer). */
constexpr float RimUU = 50.0f;

/** ENV-U10 T2: the shared rocky tray of the map-image boards (see the file comment). */
inline const TCHAR* const T2MeshPath = TEXT("/Game/PipelineCandidates/TableBase/T2/SM_TableBase_T2");
inline const TCHAR* const T2MaterialPath = TEXT("/Game/PipelineCandidates/TableBase/T2/MI_TableBase_T2");
/** Mesh-space half extent of the flat top of SM_TableBase_T2 (= the layouts' shared tray halfX / halfY, uu). */
constexpr float T2TopHalfX = 780.0f;
constexpr float T2TopHalfY = 470.0f;
/** Tray centre Y of the shared layouts (far side): T2 goes there when no layout tray applies (-ArtPreviewNoEnv). */
constexpr float T2DefaultOffsetY = -45.0f;
/** Band inside the tray edge where the T2 lip rocks may rise above TopZ (up to Z +2); props stay out of it. */
constexpr float T2RimUU = 20.0f;
/** Envelope of the built mesh beyond its flat top (Assets test): overhang, lip height, depth below the top. */
constexpr float T2MaxOverhangUU = 30.0f;
constexpr float T2LipTopZMax = 2.0f;
constexpr float T2MinDepthUU = 120.0f;
constexpr float T2MaxDepthUU = 180.0f;
/** A layout tray within this of the T2 top matches; a larger difference is traced (mismatchUU), never stretched. */
constexpr float T2MatchToleranceUU = 1.0f;

/** True when -ArtPreviewDiorama is on the command line (or the automation override is set). */
UNMATCHED_API bool FlagEnabled();
/** The tray is spawned only with -ArtPreview AND -ArtPreviewDiorama. */
inline bool Enabled(bool bArtPreview) { return bArtPreview && FlagEnabled(); }
/** Automation tests only: force the flag on/off (Reset -> read the command line again). */
UNMATCHED_API void SetFlagOverrideForTest(bool bEnabled);
UNMATCHED_API void ResetFlagOverrideForTest();

struct FTrayFit {
  float YawDeg = 0.0f;
  FVector Scale = FVector::OneVector;
  /** World half extent of the tray top after yaw and scale (board frame half + rim [+ |offset|]). */
  FVector2D WorldHalf = FVector2D::ZeroVector;
  /** ENV-MAPS: world XY of the tray pivot (the profile offset; zero for every grid board). */
  FVector2D Location = FVector2D::ZeroVector;
  /** max(scale X, scale Y) / min(...): 1 = uniform; > 1.05 breaks the Blender-stage rule (T1 waiver only). */
  double Anisotropy() const {
    const double Lo = FMath::Min(Scale.X, Scale.Y);
    return Lo > 0.0 ? FMath::Max(Scale.X, Scale.Y) / Lo : 0.0;
  }
};

/** Yaw / scale for a board frame of world half extent BoardHalf (X, Y): mesh X (the long side) goes along
 *  the longer board axis (yaw -90 when Y >= X, else 0), the XY scale keeps RimUU around the frame, Z = 1. */
UNMATCHED_API FTrayFit FitTray(const FVector2D& BoardHalf);
/** ENV-MAPS: the same with the tray shifted by Offset (world XY): the half extent grows by |Offset| per axis so
 *  the rim is RimUU on one side and RimUU + 2 |Offset| on the other; Location = Offset. */
UNMATCHED_API FTrayFit FitTray(const FVector2D& BoardHalf, const FVector2D& Offset);
/** ENV-U10 T2 placement for a layout tray of outer half extent LayoutHalf centred at (0, OffsetY): yaw 0, scale 1
 *  (never stretched: anisotropy 1), Location = (0, OffsetY), WorldHalf = the T2 top (T2TopHalfX x T2TopHalfY).
 *  OutMismatchUU = max |LayoutHalf - T2 top half| per axis (0 on the shipped layouts; > T2MatchToleranceUU = the layout
 *  asks for a tray T2 is not - the caller traces it). */
UNMATCHED_API FTrayFit FitTrayT2(const FVector2D& LayoutHalf, float OffsetY, float& OutMismatchUU);
/** ENV-U10 T2: the shortest distance from a board frame (half extent FrameHalf, centred at the origin) to the edge of the
 *  T2 top at (0, OffsetY) - the narrowest apron (negative = the frame sticks out of the tray). */
UNMATCHED_API float T2MinApronUU(const FVector2D& FrameHalf, float OffsetY);

/** World half extent of the 'tiles' art surface frame of a W x H board (cells 100 uu + wood frame FrameUU). */
inline FVector2D TilesFrameHalf(int32 Width, int32 Height, float CellUU, float FrameUU) {
  return FVector2D(Width * CellUU * 0.5f + FrameUU, Height * CellUU * 0.5f + FrameUU);
}

}  // namespace S08Diorama

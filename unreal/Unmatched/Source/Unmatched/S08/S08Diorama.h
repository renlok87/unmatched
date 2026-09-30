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
  /** World half extent of the tray top after yaw and scale (board frame half + rim). */
  FVector2D WorldHalf = FVector2D::ZeroVector;
};

/** Yaw / scale for a board frame of world half extent BoardHalf (X, Y): mesh X (the long side) goes along
 *  the longer board axis (yaw -90 when Y >= X, else 0), the XY scale keeps RimUU around the frame, Z = 1. */
UNMATCHED_API FTrayFit FitTray(const FVector2D& BoardHalf);

/** World half extent of the 'tiles' art surface frame of a W x H board (cells 100 uu + wood frame FrameUU). */
inline FVector2D TilesFrameHalf(int32 Width, int32 Height, float CellUU, float FrameUU) {
  return FVector2D(Width * CellUU * 0.5f + FrameUU, Height * CellUU * 0.5f + FrameUU);
}

}  // namespace S08Diorama

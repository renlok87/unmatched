// Wave 5c-B: the diorama tray ASSET-TABLE-BASE-001 (SM_TableBase, Tripo c2e5e3bf -> Blender -> UE,
// docs/art-pipeline/table-base-report.md) under the live S08 art board. ART-DEFAULT (2026-10-04, S08ArtLook.h): the
// tray - and with it the environment of the map boards (S08EnvLayout::Enabled) - is ON by default on every art board;
// the former opt-in flag -ArtPreviewDiorama is a no-op alias. Rollback: -S08DioramaLegacy - the board actor then creates
// no component and loads nothing from here: the board is byte-for-byte the one before -ArtPreviewDiorama.
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
//
// ENV-MAPS P5 track B (2026-10-01) - T2b: the chunky lane K rebuild of the same shared tray (art/pipeline-candidates/
// ASSET-TABLE-BASE-001/20261001-tray-t2b, imported by tools/art/env_kit/ue_import_tray_t2.py --variant t2b): the SAME flat
// top (T2TopHalfX x T2TopHalfY at TopZ, pivot = its centre, placed by FitTrayT2 at scale 1), a heavier rock skirt (depth
// <= T2bMaxDepthUU, overhang <= T2bMaxOverhangUU) and the vertex-colour moss of M_TableBase_T2b. LoadTrayT2 prefers T2b and
// falls back to T2 (then the caller's T1 placeholder) when it is not in the build; its material is the map's MI
// (MI_TableBase_T2b_<Map>: Marmoreal moss + petals, Sarpedon damp dark rock) when imported, else the shared
// MI_TableBase_T2b (LoadTrayT2Material). One mesh for both maps (ENV-U10); the grid boards never reach any of this.
#pragma once

#include "CoreMinimal.h"

class UMaterialInterface;
class UStaticMesh;

namespace S08Diorama {

/** Rollback flag (ART-DEFAULT): -S08DioramaLegacy - no tray and no environment (the board before -ArtPreviewDiorama). */
inline const TCHAR* const LegacyFlagName = TEXT("S08DioramaLegacy");
/** The former opt-in flag -ArtPreviewDiorama: still accepted (scripts pass it), a no-op - the tray is the default. */
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

/** P5 track B: the T2b rebuild of the shared tray (same flat top / pivot / placement as T2, see the file comment). */
inline const TCHAR* const T2bMeshPath = TEXT("/Game/PipelineCandidates/TableBase/T2b/SM_TableBase_T2b");
/** The shared MI (the mesh slot; maps without their own MI). */
inline const TCHAR* const T2bMaterialPath = TEXT("/Game/PipelineCandidates/TableBase/T2b/MI_TableBase_T2b");
/** Per-map MI: <prefix><Map> (MI_TableBase_T2b_Marmoreal, MI_TableBase_T2b_Sarpedon). */
inline const TCHAR* const T2bMapMaterialPrefix = TEXT("/Game/PipelineCandidates/TableBase/T2b/MI_TableBase_T2b_");
inline const TCHAR* const T2bMasterPath = TEXT("/Game/PipelineCandidates/TableBase/T2b/M_TableBase_T2b");
/** Envelope of the T2b build (Assets test; lane K: overhang 23.0 sides / 35.7 corners, depth 212.7, lip top 1.71). The
 *  lip band (T2RimUU) and the lip top (T2LipTopZMax) are the T2 ones. */
constexpr float T2bMaxOverhangUU = 40.0f;
constexpr float T2bMinDepthUU = 180.0f;
constexpr float T2bMaxDepthUU = 230.0f;

/** Which shared tray mesh a map-image board shows (None: neither is in the build -> the T1 placeholder). */
enum class ETrayT2Kind : uint8 { None, T2, T2b };
/** "none" / "T2" / "T2b" (the 'kind=' field of the tray trace line). */
UNMATCHED_API const TCHAR* TrayT2KindName(ETrayT2Kind Kind);
/** World-free choice: T2b when its mesh is in the build, else T2, else None. */
UNMATCHED_API ETrayT2Kind PickTrayT2(bool bT2bInBuild, bool bT2InBuild);
/** Mesh / shared material package path of a kind (nullptr for None). */
UNMATCHED_API const TCHAR* TrayT2MeshPath(ETrayT2Kind Kind);
UNMATCHED_API const TCHAR* TrayT2MaterialPath(ETrayT2Kind Kind);
/** The per-map T2b MI path of a map name or key ("Sarpedon" / "sarpedon" -> .../MI_TableBase_T2b_Sarpedon); empty for an
 *  empty name or one that is not [A-Za-z0-9_]. */
UNMATCHED_API FString T2bMapMaterialPath(const FString& MapName);
/** The kind of a loaded tray mesh by its path (None for any other mesh, e.g. T1). */
UNMATCHED_API ETrayT2Kind TrayT2KindOf(const UStaticMesh* Mesh);

/** What LoadTrayT2 found. */
struct FTrayT2Assets {
  ETrayT2Kind Kind = ETrayT2Kind::None;
  UStaticMesh* Mesh = nullptr;
  /** The map's MI, else the kind's shared MI; nullptr = the mesh's own slot material. */
  UMaterialInterface* Material = nullptr;
  FString MaterialPath;
  /** T2b was in the build but did not load (T2 used instead) - traced. */
  bool bT2bFailed = false;
};
/** Loads the map-image tray: T2b if its package is in the build (cooked runs: if it loads), else T2; Material =
 *  LoadTrayT2Material(Kind, MapName). Uncooked runs never touch a package that does not exist (no loader warning). */
UNMATCHED_API FTrayT2Assets LoadTrayT2(const FString& MapName);
/** The tray material of a kind on a map: T2b -> MI_TableBase_T2b_<Map> when in the build, else MI_TableBase_T2b;
 *  T2 -> MI_TableBase_T2; None -> nullptr. OutPath (optional) = the path that loaded (empty when none did). */
UNMATCHED_API UMaterialInterface* LoadTrayT2Material(ETrayT2Kind Kind, const FString& MapName,
                                                     FString* OutPath = nullptr);
/** 'ARTPREVIEW diorama tray-t2 loaded|absent mesh=<path> mi=<name>[ (import: ...) -> T1 placeholder] kind=<k>
 *  [t2b=failed]' (the first map-image board; the leading fields are those of the T2-only line before P5). */
UNMATCHED_API FString TrayT2LoadTraceLine(const FTrayT2Assets& Assets);

/** World-free rule: the tray unless the rollback flag is on the command line. */
constexpr bool Decide(bool bLegacyFlag) { return !bLegacyFlag; }
/** True when the tray is on: by default; false with -S08DioramaLegacy (or the automation override). (The name is the
 *  opt-in one: it read -ArtPreviewDiorama before ART-DEFAULT.) */
UNMATCHED_API bool FlagEnabled();
/** True when -S08DioramaLegacy is on the command line. */
UNMATCHED_API bool LegacyRequested();
/** The tray is spawned only on the art look (bArtLook: S08ArtLook::Enabled() in BeginPlay) AND without the rollback. */
inline bool Enabled(bool bArtLook) { return bArtLook && FlagEnabled(); }
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

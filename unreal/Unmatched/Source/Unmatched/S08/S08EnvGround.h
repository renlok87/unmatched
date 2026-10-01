// ENV-MAPS P2 track GROUND (user decision ENV-U10, "Тематическая земля + скалистый край"): the themed ground between
// the wooden map frame and the tray edge of the original-map boards, spawned with the environment layout
// (S08EnvLayout.h) of the active 'map-image' board.
//
// Data: the optional "ground" object of Config/ArtBoards/EnvLayouts/<map>.layout.json (tools/art/env_kit/
// ground_splat.py --write-layouts writes it; other fields such as "splat" / "splatSha256" / "notes" are ignored):
//   "ground": {"mode":"runtime", "material":"/Game/EnvKit/Ground/MI_EnvGround_Marmoreal", "z":-1.0,
//              "frameOverlapUU":2.0, "insetUU":0.0, "splatRect":[minX, minY, maxX, maxY]}
//
// Mesh = "runtime" (the only mode; chosen over a Blender plane-with-hole FBX): the ground is the tray top rectangle the
// diorama tray is placed with (S08EnvLayout::TrayTopRect) shrunk by insetUU, minus the frame outer rectangle shrunk by
// frameOverlapUU (the strips reach under the 14 uu deep frame bars: no seam, the T-junction corners stay hidden),
// cut into <= 4 axis-aligned strips (N and S full width, W and E between them). Each strip is one
// /Engine/BasicShapes/Plane (100 x 100 uu, always cooked by DefaultGame.ini) scaled to the strip at Z = z, strictly
// between the tray top (-3) and the map plane (-0.5): no z-fight with either. NoCollision, no navigation, no shadow
// casting (a flat layer; it receives shadows and decals). Why runtime rather than an FBX: the ground follows whatever
// tray the layout sets (track TRAY) with no Blender re-export and no re-import, it needs no new mesh asset and no
// plugin, and the board-space UVs come from the material instead of the mesh. Each strip gets a MID of the layout's
// material with
//   GroundStrip = (min.x, min.y, size.x, size.y) of the strip  -> M_EnvGround: P = GroundStrip.xy + UV0 * GroundStrip.zw
//   SplatRect   = (minX, minY, maxX - minX, maxY - minY)         (only when "splatRect" is set; else the MI's value)
// (the engine plane maps local (-50,-50) -> UV (0,0), u along +X, v along +Y), so the strips sample ONE continuous
// board-space texture: tools/art/env_kit/ue_import_env_ground.py builds M_EnvGround and MI_EnvGround_<Map>.
// A missing material spawns no strip (traced; the props and lights of the layout still spawn).
// (The ground parser accepts only mode "runtime"; the P5 lane K meshes below are extra pieces of the same section.)
//
// Waterfalls (ENV-MAPS P4, review gap 1; optional "waterfalls" array of the same section, written by ground_splat.py from
// ground-params.json 'water.falls'; Sarpedon only):
//   "waterfalls": [{"id":"fall-s", "material":"/Game/EnvKit/Ground/MI_EnvWaterfall_Sarpedon", "x0":-241, "x1":-47,
//                   "y":457, "topZ":2.5, "dropUU":230, "spillUU":60}]
// Each entry spawns (with the strips, only when the ground status is 'ok') one more /Engine/BasicShapes/Plane: the
// vertical card x0..x1 at Y = y facing +Y (the K1 camera) from Z = topZ down to topZ - dropUU (local +Z -> +Y, local +Y ->
// -Z, so UV v runs down the card), plus, when spillUU > 0, a flat spill x0..x1, y - spillUU..y at Z = topZ (above the T2
// rocky lip, which rises to Z +2 within 20 uu of the tray edge; v runs towards the lip). Both are NoCollision, no shadow,
// MID of the entry's material with FallCard = (width, height, kind 0 card / 1 spill, 0) (M_EnvWaterfall scrolls its
// streaks along +v). The ground water itself is not a component: M_EnvGround draws it from the aux mask of the MI. A
// missing waterfall material skips that entry (counted in the trace). Grid boards never reach this code (no layout).
//
// P5 track B (lane K meshes, art/pipeline-candidates/ASSET-ENV-S-WATERFALL-001; Sarpedon only, written by ground_splat.py):
//   waterfalls[i].mesh = {"sheet":"/Game/EnvKit/Ground/Sarpedon/SM_Env_S_Waterfall", "foam":".../SM_Env_S_WaterfallFoam",
//                         "lip":".../SM_Env_S_WaterfallLip", "lipMaterial":"/Game/PipelineCandidates/TableBase/T2b/
//                         MI_TableBase_T2b_Sarpedon", "loc":[-144.1,425,0], "yawDeg":90, "sheetCard":[193.8,185.231],
//                         "foamCards":[[261.34,70],[243.97,76]]}
//     When the sheet mesh loads, the entry spawns the sheet (MID of the entry's material, FallCard = (sheetCard, kind 0, flip 1)),
//     the foam / mist (one MID per slot, FallCard = (foamCards[slot] or the last one, kind 1, flip 1)) and the optional rock lip
//     (lipMaterial, else the mesh's own slot material; it casts a shadow like the tray) at loc / yawDeg, scale 1, INSTEAD
//     of the vertical plane card; the flat spill plane stays. A sheet mesh that is not in the build falls back to the
//     plane card (traced as fallMeshes=0); a missing foam / lip mesh is skipped.
//   sea = {"mesh":"/Game/EnvKit/Ground/Sarpedon/SM_Env_S_SeaRing", "material":"/Game/EnvKit/Ground/MI_EnvSea_Sarpedon",
//          "loc":[0,-45,-172], "yawDeg":0}: the dark sea ring under the tray (z strictly below the tray top), NoCollision,
//          no shadow, the MI as is; spawned with the strips (status ok), sea=ok|missing-mesh|missing-material.
// Trace: 'ARTPREVIEW envlayout ground map=<m> mode=runtime strips=N material=<name> z=.. outer=(..)..(..) hole=(..)..(..)
//         splatRect=(..)..(..)|- splatCovers=0|1 areaUU2=.. falls=<spawned>/<declared> fallCards=K
//         status=ok|off|no-tray|no-strips|missing-plane|missing-material[ fallMeshes=M fallMeshParts=P sea=<s>]' (the
//         bracketed P5 tail only for a ground with a waterfall mesh or a sea: every other line is unchanged)
#pragma once

#include "CoreMinimal.h"
#include "UObject/WeakObjectPtrTemplates.h"

class AActor;
class FJsonObject;
class USceneComponent;
class UStaticMeshComponent;

namespace S08EnvGroundSpec {
inline const TCHAR* const RuntimeMode = TEXT("runtime");
inline const TCHAR* const PlaneMeshPath = TEXT("/Engine/BasicShapes/Plane.Plane");
/** Where ue_import_env_ground.py puts M_EnvGround / MI_EnvGround_<Map> (under the always-cooked /Game/EnvKit). */
inline const TCHAR* const MaterialRoot = TEXT("/Game/EnvKit/Ground/");
inline const TCHAR* const ParamGroundStrip = TEXT("GroundStrip");
inline const TCHAR* const ParamSplatRect = TEXT("SplatRect");
/** Exclusive Z range: above the tray top (S08Diorama::TopZ), below the map plane (S08MapSurfaceSpec::PlaneZ). */
constexpr float MinZ = -3.0f;
constexpr float MaxZ = -0.5f;
constexpr float DefaultZ = -1.0f;
constexpr float DefaultFrameOverlapUU = 2.0f;
/** The frame is 24 uu wide: the hole never shrinks past the painted map. */
constexpr float MaxFrameOverlapUU = 20.0f;
constexpr float MaxInsetUU = 200.0f;
/** /Engine/BasicShapes/Plane spans 100 x 100 uu at scale 1. */
constexpr float PlaneSizeUU = 100.0f;
/** Strips thinner than this are dropped. */
constexpr float MinStripUU = 0.5f;
/** P4 waterfalls (the "waterfalls" array; tools/art/env_kit/ground_splat.py validate_waterfalls mirrors the limits). */
inline const TCHAR* const ParamFallCard = TEXT("FallCard");
constexpr int32 MaxWaterfalls = 4;
constexpr float FallMinTopZ = -3.0f;
constexpr float FallMaxTopZ = 20.0f;
constexpr float DefaultFallTopZ = 2.5f;
constexpr float MaxFallDropUU = 1000.0f;
constexpr float MaxFallSpillUU = 200.0f;
constexpr float MaxFallWidthUU = 2000.0f;
/** |x0|, |x1|, |y| bound (board space; the trays are ~800 uu). */
constexpr float MaxFallAbsXYUU = 5000.0f;
/** FallCard.z of the two parts. */
constexpr float FallKindCard = 0.0f;
constexpr float FallKindSpill = 1.0f;
/** FallCard.w: 0 = the engine-plane card / spill (v runs down the card), 1 = a lane K mesh (sheet / foam / mist): their v
 *  was authored top -> bottom in Blender and the FBX import flips V, so M_EnvWaterfall (graph 2) uses 1 - v (P5b tune). */
constexpr float FallFlipPlane = 0.0f;
constexpr float FallFlipMesh = 1.0f;
/** P5 track B mesh pieces (waterfalls[].mesh, sea; tools/art/env_kit/ground_splat.py mirrors the limits). */
constexpr float MeshMaxAbsXYUU = 5000.0f;
constexpr float FallMeshMinZ = -50.0f;
constexpr float FallMeshMaxZ = 50.0f;
constexpr float MaxMeshYawDeg = 360.0f;
constexpr float MaxMeshCardUU = 2000.0f;
constexpr int32 MaxFoamCards = 2;
/** The sea ring lies in [SeaMinZ, SeaMaxZ): strictly below the tray top (S08Diorama::TopZ). */
constexpr float SeaMinZ = -1000.0f;
constexpr float SeaMaxZ = -3.0f;
}  // namespace S08EnvGroundSpec

/** P5 track B: the optional lane K meshes of a waterfall (they replace its vertical plane card). */
struct UNMATCHED_API FS08EnvWaterfallMesh {
  bool bSet = false;
  FString Sheet;        // required (package path)
  FString Foam;         // optional
  FString Lip;          // optional
  FString LipMaterial;  // required with a lip
  FVector Loc = FVector::ZeroVector;
  float YawDeg = 0.0f;
  FVector2D SheetCard = FVector2D::ZeroVector;  // FallCard.xy of the sheet
  TArray<FVector2D> FoamCards;                  // FallCard.xy per foam slot (the last one repeats)
};

/** One "waterfalls" entry: a vertical card (and an optional flat spill) at the near tray edge (board space). */
struct UNMATCHED_API FS08EnvWaterfall {
  FString Id;
  FString Material;  // MI package path (/Game/... or /Engine/...), optionally "Pkg.Obj"
  float X0 = 0.0f;
  float X1 = 0.0f;
  float Y = 0.0f;
  float TopZ = S08EnvGroundSpec::DefaultFallTopZ;
  float DropUU = 0.0f;
  float SpillUU = 0.0f;
  /** P5 track B: the optional "mesh" object (bSet false = the plane card only). */
  FS08EnvWaterfallMesh Mesh;
};

/** P5 track B: the optional "sea" object of the ground section (the sea ring under the tray). */
struct UNMATCHED_API FS08EnvSea {
  bool bSet = false;
  FString Mesh;
  FString Material;
  FVector Loc = FVector::ZeroVector;
  float YawDeg = 0.0f;
};

/** The parsed "ground" section of a layout (bSet false = the layout has none: no ground). */
struct UNMATCHED_API FS08EnvGround {
  bool bSet = false;
  FString Mode;
  FString Material;  // MI package path (/Game/... or /Engine/...), optionally "Pkg.Obj"
  float Z = S08EnvGroundSpec::DefaultZ;
  float FrameOverlapUU = S08EnvGroundSpec::DefaultFrameOverlapUU;
  float InsetUU = 0.0f;
  bool bSplatRect = false;
  FBox2D SplatRect = FBox2D(ForceInit);  // board XY covered by the splat texture
  /** P4: the optional "waterfalls" (empty = none). */
  TArray<FS08EnvWaterfall> Waterfalls;
  /** P5 track B: the optional "sea". */
  FS08EnvSea Sea;
  /** True when the trace line carries the P5 tail (a waterfall with a mesh, or a sea). */
  bool HasMeshPieces() const;
};

/** What one ground spawn did (also the trace numbers). */
struct UNMATCHED_API FS08EnvGroundStats {
  FString Status = TEXT("off");
  int32 Strips = 0;
  FBox2D Outer = FBox2D(ForceInit);  // tray top - inset
  FBox2D Hole = FBox2D(ForceInit);   // frame outer - overlap
  double AreaUU2 = 0.0;
  /** The splat rectangle contains the outer rectangle (true without a "splatRect": the MI's value is used). */
  bool bSplatCoversOuter = false;
  FString MaterialName;
  /** P4 waterfalls: entries spawned / entries whose material is missing / plane components (card + spill). */
  int32 Falls = 0;
  int32 FallsMissing = 0;
  int32 FallCards = 0;
  /** P5 track B: falls shown with their sheet mesh (not the plane card) / mesh components (sheet + foam + lip) / the sea
   *  ring ('off' without a "sea", else ok | missing-mesh | missing-material). */
  int32 FallMeshes = 0;
  int32 FallMeshParts = 0;
  FString SeaStatus = TEXT("off");
};

namespace S08EnvGround {
/** Parses a "ground" object into Out (Out.bSet = true only when it is valid); appends 'ground: ...' errors. */
UNMATCHED_API bool ParseJson(const TSharedPtr<FJsonObject>& Obj, FS08EnvGround& Out, TArray<FString>& OutErrors);
/** Tray top shrunk by InsetUU on every side. */
UNMATCHED_API FBox2D OuterRect(const FBox2D& TrayTop, float InsetUU);
/** Frame outer rectangle (+-FrameHalf) shrunk by FrameOverlapUU on every side. */
UNMATCHED_API FBox2D HoleRect(const FVector2D& FrameHalf, float FrameOverlapUU);
/** Outer minus Hole as <= 4 disjoint axis-aligned strips, in the order N (far, full width), S (near, full width), W,
 *  E (between N and S); the hole is clipped to Outer first, strips thinner than MinStripUU are dropped. No hole inside
 *  Outer -> Outer itself; an invalid or degenerate Outer -> none. */
UNMATCHED_API TArray<FBox2D> Strips(const FBox2D& Outer, const FBox2D& Hole);
/** Relative transform of the engine plane that covers Strip at height Z (no rotation, scale size / 100, Z scale 1). */
UNMATCHED_API FTransform StripTransform(const FBox2D& Strip, float Z);
/** (min.x, min.y, size.x, size.y): the GroundStrip / SplatRect parameter value of a rectangle. */
UNMATCHED_API FLinearColor RectParam(const FBox2D& Rect);
/** Relative transform of the engine plane that is the vertical card of a waterfall: centre ((x0+x1)/2, y, topZ - drop/2),
 *  local +X -> +X, local +Z (the plane normal) -> +Y (towards the K1 camera), local +Y -> -Z (UV v runs down), scale
 *  (width / 100, drop / 100, 1). */
UNMATCHED_API FTransform FallCardTransform(const FS08EnvWaterfall& Fall);
/** Relative transform of the flat spill of a waterfall: x0..x1, y - spillUU..y at Z = topZ, no rotation (v runs +Y). */
UNMATCHED_API FTransform FallSpillTransform(const FS08EnvWaterfall& Fall);
/** FallCard = (width, height, kind, 0): height = dropUU (card) or spillUU (spill), kind = FallKindCard | FallKindSpill. */
UNMATCHED_API FLinearColor FallCardParam(const FS08EnvWaterfall& Fall, bool bSpill);
/** P5 track B: relative transform of a lane K piece: Loc, yaw YawDeg about +Z (90: local +X -> board +Y), scale 1. */
UNMATCHED_API FTransform MeshPieceTransform(const FVector& Loc, float YawDeg);
/** FallCard of the sheet mesh: (sheetCard.x, sheetCard.y, FallKindCard, FallFlipMesh). */
UNMATCHED_API FLinearColor SheetCardParam(const FS08EnvWaterfallMesh& Mesh);
/** FallCard of foam slot Slot: (foamCards[Slot] or the last one, FallKindSpill, FallFlipMesh); no foamCards -> (sheet width, 70). */
UNMATCHED_API FLinearColor FoamCardParam(const FS08EnvWaterfallMesh& Mesh, int32 Slot);
/** Creates one plane component per strip of (OuterRect(TrayTop), HoleRect(FrameHalf)) under Parent (owned by Owner),
 *  each with a MID of Ground.Material carrying GroundStrip / SplatRect, then the waterfall cards / spills of
 *  Ground.Waterfalls (MID of their material with FallCard; P5: the sheet / foam / lip meshes instead of the card when the
 *  sheet mesh loads) and the P5 sea ring; appends them to Out (weak: the actor owns them). Nothing is created unless the
 *  status is 'ok'. */
UNMATCHED_API FS08EnvGroundStats Spawn(const FS08EnvGround& Ground, AActor& Owner, USceneComponent* Parent,
                                       const FBox2D& TrayTop, const FVector2D& FrameHalf,
                                       TArray<TWeakObjectPtr<UStaticMeshComponent>>& Out);
/** Destroys every live ground component; returns how many there were. */
UNMATCHED_API int32 Clear(TArray<TWeakObjectPtr<UStaticMeshComponent>>& Components);
/** 'ARTPREVIEW envlayout ground map=<m> mode=.. strips=N ... status=<s>'. */
UNMATCHED_API FString TraceLine(const FString& MapKey, const FS08EnvGround& Ground, const FS08EnvGroundStats& Stats);
}  // namespace S08EnvGround

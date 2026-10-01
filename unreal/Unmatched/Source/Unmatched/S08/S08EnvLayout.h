// ENV-MAPS track C (docs/art-pipeline/ENV-MAPS-PLAN.md, user decisions ENV-U1 / ENV-U2 / ENV-U8): the 3D environment
// around the original-map boards (Marmoreal v1, Sarpedon v2), placed from data under the live S08 board actor.
//
// Data: <ProjectConfigDir>/ArtBoards/EnvLayouts/<map>.layout.json (staged as UFS files by Unmatched.Build.cs, like
// S08ArtBoardProfiles.json), schema "unmatched.env-layout/1":
//   { "schema":"unmatched.env-layout/1", "map":"marmoreal", "boardId":"c121b47f8d6eb28daccb76d05",
//     "tray":  {"halfX":<uu>, "halfY":<uu>, "offsetY":<uu>},  // outer tray half extents incl. apron; offsetY < 0 = far
//     "apron": {"n":<uu>, "s":<uu>, "w":<uu>, "e":<uu>},       // decor band outside the frame (n = far -Y, s = near +Y)
//     "props": [ {"id":"cherry-nw", "mesh":"/Game/EnvKit/Marmoreal/SM_Env_Cherry", "loc":[x,y,z], "yawDeg":0,
//                 "scale":1.0, "castShadow":true} ],
//     "lights": [ {"id":"lamp-nw", "type":"point", "loc":[x,y,z], "colorSrgb":"#FFB870", "intensityCd":<cd>,
//                  "radius":<uu>, "castShadow":false} ],
//     "ground": {"mode":"runtime", "material":"/Game/EnvKit/Ground/MI_EnvGround_<Map>", "z":-1, ...},  // optional,
//                                                              // ENV-U10 themed ground: S08EnvGround.h
//     "notes": "..." }
// Coordinates are board-actor space (uu): origin = map centre, +X right on screen, +Y towards the K1 camera (near
// side), Z up (map plane ~ 0, tray top -3). A prop's pivot is its base centre; scale multiplies the processed mesh,
// whose size already equals the target size (tools/art/env_kit/ue_import_env_kit.py imports it into
// /Game/EnvKit/<Map>/, cooked through DirectoriesToAlwaysCook /Game/EnvKit). At most 6 point lights per layout,
// never shadowed (budget: the key light stays in the art light profile).
//
// Gate: the board actor spawns the environment only with -ArtPreview AND -ArtPreviewDiorama (S08Diorama::Enabled),
// without -ArtPreviewNoEnv (A/B and perf opt-out), and only while a 'map-image' art profile is active. A grid board
// (Cobble, the 'tiles' fixtures) never loads a layout nor creates a component; a board change destroys what was
// spawned. A missing mesh skips its props (traced), never the whole layout. Invalid documents spawn nothing.
// Trace (evidence contract):
//   ARTPREVIEW envlayout map=<m> props=N lights=M missingMeshes=K ... status=ok|invalid|absent
//   ARTPREVIEW envlayout prop id=.. / light id=.. / missing mesh=.. / skipped id=.. / tray ... / off ...
// Everything except Spawn / Update / Clear is world-free and automation-tested (S08EnvLayoutTests.cpp,
// Unmatched.S08.EnvLayout.*).
#pragma once

#include "CoreMinimal.h"
#include "S08EnvGround.h"
#include "UObject/ObjectPtr.h"

class AActor;
class USceneComponent;
class UStaticMeshComponent;
class UPointLightComponent;

namespace S08EnvLayoutSpec {
inline const TCHAR* const Schema = TEXT("unmatched.env-layout/1");
/** Folder of the layouts under the project Config dir (and the UFS staging rule in Unmatched.Build.cs). */
inline const TCHAR* const ConfigSubdir = TEXT("ArtBoards/EnvLayouts");
inline const TCHAR* const FileSuffix = TEXT(".layout.json");
/** Where ue_import_env_kit.py puts the kit (always cooked); a mesh elsewhere is allowed but traced (cook risk). */
inline const TCHAR* const KitRoot = TEXT("/Game/EnvKit/");
/** -ArtPreviewNoEnv: keep the diorama tray but spawn no environment (A/B frames, perf gate). */
inline const TCHAR* const NoEnvFlagName = TEXT("ArtPreviewNoEnv");
/** -ArtEnvLayouts=<abs dir>: diagnostic override of the layout folder (the trace says source=override). */
inline const TCHAR* const DirOverrideParam = TEXT("ArtEnvLayouts=");
constexpr int32 MaxPointLights = 6;
constexpr int32 MaxProps = 256;
constexpr float MaxPropScale = 20.0f;
/** Shared budget of AGENTS/W4-A: 1 directional key + <= 6 point lights on screen (art profile + layout). */
constexpr int32 CombinedPointBudget = 6;
/** Tolerance of the tray-vs-apron consistency note (uu). */
constexpr float TrayApronToleranceUU = 1.0f;
}  // namespace S08EnvLayoutSpec

/** "tray": outer half extents of the diorama tray top (incl. the apron) and its Y shift (board space). */
struct UNMATCHED_API FS08EnvTray {
  bool bSet = false;
  float HalfX = 0.0f;
  float HalfY = 0.0f;
  /** Signed world Y of the tray centre: < 0 = shifted to the far side (-Y, away from the K1 camera). */
  float OffsetY = 0.0f;
};

/** "apron": width of the decor band outside the wooden frame per side (n = far -Y, s = near +Y, w = -X, e = +X). */
struct UNMATCHED_API FS08EnvApron {
  bool bSet = false;
  float N = 0.0f;
  float S = 0.0f;
  float W = 0.0f;
  float E = 0.0f;
  /** The tray these bands imply around a frame of half extent FrameHalf: X symmetric (max(w, e)), Y from n / s. */
  FS08EnvTray ImpliedTray(const FVector2D& FrameHalf) const;
};

struct UNMATCHED_API FS08EnvProp {
  FString Id;
  FString Mesh;  // package path (/Game/... or /Engine/...), optionally "Pkg.Obj"
  FVector Loc = FVector::ZeroVector;
  float YawDeg = 0.0f;
  float Scale = 1.0f;
  bool bCastShadow = true;
  /** Relative transform under the board actor root (pivot = base centre). */
  FTransform Transform() const;
};

struct UNMATCHED_API FS08EnvLight {
  FString Id;
  FVector Loc = FVector::ZeroVector;
  FColor Color = FColor::White;  // sRGB bytes of "colorSrgb" (SetLightFColor keeps them exactly)
  float IntensityCd = 0.0f;
  float RadiusUU = 0.0f;
  FString ColorHex() const;
};

/** One parsed layout document (world-free). */
struct UNMATCHED_API FS08EnvLayout {
  FString Map;      // "marmoreal" | "sarpedon" (lower-case map key)
  FString BoardId;  // Board row id the layout belongs to
  FS08EnvTray Tray;
  FS08EnvApron Apron;
  TArray<FS08EnvProp> Props;
  TArray<FS08EnvLight> Lights;
  /** ENV-U10: the optional themed ground (S08EnvGround.h); an invalid "ground" makes the whole layout invalid. */
  FS08EnvGround Ground;
  FString Notes;
  /** LoadFile only: the file and the sha256 of its bytes (evidence). */
  FString SourcePath;
  FString SourceSha256;

  /** Parses and validates the whole document; any structural error makes it invalid (false, nothing spawns). */
  bool ParseJson(const FString& Text, TArray<FString>& OutErrors);
  bool LoadFile(const FString& Path, TArray<FString>& OutErrors);
  /** Unique mesh package paths of the props (first-use order). */
  TArray<FString> UniqueMeshPaths() const;
};

/** What one Spawn did (also the trace numbers). */
struct UNMATCHED_API FS08EnvSpawnStats {
  int32 LayoutProps = 0;
  int32 LayoutLights = 0;
  int32 Props = 0;             // prop components created
  int32 Lights = 0;            // point light components created
  int32 MissingMeshes = 0;     // unique mesh paths that did not load
  int32 SkippedMissing = 0;    // props skipped because their mesh is missing
  int32 SkippedInsideMap = 0;  // props whose pivot lies on the painted map (ENV-U1: environment only around it)
  int32 Intrusions = 0;        // spawned props whose bounds overlap the painted map (traced, not refused)
  int32 OutsideTray = 0;       // spawned props whose pivot lies outside the tray top (floating over the void)
  int32 OutsideKit = 0;        // props whose mesh is not under /Game/EnvKit (cooked only by another rule)
  int32 ShadowCasters = 0;
  TArray<FString> MissingPaths;
};

/** Inputs of one board-actor update (the actor fills it from its active art profile). */
struct UNMATCHED_API FS08EnvLayoutRequest {
  bool bEnabled = false;         // S08EnvLayout::Enabled(-ArtPreview)
  bool bMapImageActive = false;  // the active art profile draws the 'map-image' surface
  FString ProfileId;
  FString MapKey;                // lower-case FS08MapImageSpec::Name
  FString RoomBoardId;
  TArray<FString> ProfileBoardIds;
  FVector2D MapHalf = FVector2D::ZeroVector;    // painted map half extent (445.667 x 288.667)
  FVector2D FrameHalf = FVector2D::ZeroVector;  // map + wooden frame half extent
  FVector2D ProfileTrayOffset = FVector2D::ZeroVector;  // FS08MapImageSpec::TrayOffsetUU (placeholder fit)
  int32 ProfilePointLights = 0;  // point lights of the art light profile (combined budget trace)
  FString Dir;                   // empty = S08EnvLayout::ResolveDir()
};

/** The environment state of one board actor (the components themselves are UPROPERTY arrays of the actor). */
struct UNMATCHED_API FS08EnvLayoutRuntime {
  bool bApplied = false;      // an update ran for a map-image board (valid or not)
  bool bLayoutValid = false;  // Layout holds a validated document
  FString Key;                // map | boardId | sha256 of what is applied (same key -> no respawn)
  FString MapKey;
  FString Status;             // ok | invalid | absent
  FS08EnvLayout Layout;
  FS08EnvSpawnStats Stats;
  /** ENV-U10: the ground strips of Layout.Ground (S08EnvGround::Spawn). Weak: the board actor owns the components
   *  (OwnedComponents); Update clears them together with the props and lights. */
  TArray<TWeakObjectPtr<UStaticMeshComponent>> Ground;
  FS08EnvGroundStats GroundStats;
};

namespace S08EnvLayout {
/** -ArtPreview AND -ArtPreviewDiorama AND NOT -ArtPreviewNoEnv. */
UNMATCHED_API bool Enabled(bool bArtPreview);
UNMATCHED_API bool OptOut();
/** Enabled(bArtPreview) plus its trace: 'ARTPREVIEW envlayout enabled dir=.. source=pak|override files=N', or
 *  'ARTPREVIEW envlayout disabled (-ArtPreviewNoEnv)' when the diorama is on but the environment opted out; nothing
 *  without the diorama flag (the previous board, byte for byte). */
UNMATCHED_API bool Arm(bool bArtPreview);
/** Automation only: force -ArtPreviewNoEnv on/off (Reset -> command line). The diorama flag has its own override. */
UNMATCHED_API void SetOptOutOverrideForTest(bool bOptOut);
UNMATCHED_API void ResetOptOutOverrideForTest();

/** <ProjectConfigDir>/ArtBoards/EnvLayouts. */
UNMATCHED_API FString DefaultDir();
/** DefaultDir(), or -ArtEnvLayouts=<dir>. */
UNMATCHED_API FString ResolveDir(bool& bOutOverride);
/** <Dir>/<MapKey>.layout.json */
UNMATCHED_API FString FileFor(const FString& Dir, const FString& MapKey);
/** "Marmoreal" -> "marmoreal". */
UNMATCHED_API FString MapKeyOf(const FString& MapName);
/** Loads the layout of a map-image board: <Dir>/<MapKey>.layout.json whose "map" is MapKey and whose "boardId" is one
 *  of BoardIds (empty = any); when that file does not exist, the first *.layout.json of Dir (by name) with such a
 *  boardId. False with errors when none is found or the document is invalid; bOutAbsent = no file at all. */
UNMATCHED_API bool Resolve(const FString& Dir, const FString& MapKey, const TArray<FString>& BoardIds,
                           FS08EnvLayout& Out, TArray<FString>& OutErrors, bool& bOutAbsent);

/** Tray of a valid layout for S08Diorama::FitTray(BoardHalf, Offset): "tray" (else the tray the "apron" implies)
 *  as the equivalent board half (outer half - |offset| - RimUU) and offset (0, offsetY). False (with the reason) when
 *  the layout has neither or its tray would not cover the map frame; the caller keeps the profile placeholder fit. */
UNMATCHED_API bool TrayFit(const FS08EnvLayout& Layout, const FVector2D& FrameHalf, FVector2D& OutBoardHalf,
                           FVector2D& OutOffset, FString& OutSource, FString& OutReason);
/** World XY rectangle of the tray top: the layout tray when TrayFit accepts it, else the placeholder fit of the
 *  profile (S08Diorama::FitTray(FrameHalf, ProfileTrayOffset)). */
UNMATCHED_API FBox2D TrayTopRect(const FS08EnvLayout* Layout, const FVector2D& FrameHalf,
                                 const FVector2D& ProfileTrayOffset);
/** True when the pivot (XY) lies strictly inside the painted map rectangle. */
UNMATCHED_API bool PivotInsideMap(const FVector& Loc, const FVector2D& MapHalf);
/** True when a board-space box overlaps the painted map rectangle (XY). */
UNMATCHED_API bool BoxOverlapsMap(const FBox& Box, const FVector2D& MapHalf);
/** The summary line: 'ARTPREVIEW envlayout map=<m> props=N lights=M missingMeshes=K ...'. */
UNMATCHED_API FString SummaryLine(const FString& MapKey, const FS08EnvSpawnStats& Stats, const FString& Tail);

/** Creates one UStaticMeshComponent per prop (NoCollision, no navigation, CastShadow per entry) and one Movable
 *  UPointLightComponent per light (candelas, attenuation radius, sRGB colour, no shadows) under Parent, owned by
 *  Owner; appends them to OutProps / OutLights and traces each. Props on the painted map or with a missing mesh are
 *  skipped (traced). TrayTop (world XY, invalid = unknown) only feeds the outside-tray count. */
UNMATCHED_API FS08EnvSpawnStats Spawn(const FS08EnvLayout& Layout, AActor& Owner, USceneComponent* Parent,
                                      const FVector2D& MapHalf, const FBox2D& TrayTop,
                                      TArray<TObjectPtr<UStaticMeshComponent>>& OutProps,
                                      TArray<TObjectPtr<UPointLightComponent>>& OutLights);
/** Destroys every spawned component; returns how many there were. */
UNMATCHED_API int32 Clear(TArray<TObjectPtr<UStaticMeshComponent>>& Props,
                          TArray<TObjectPtr<UPointLightComponent>>& Lights);
/** The board-actor hook: clears on a board change / gate off, (re)loads and spawns the layout of the active map-image
 *  profile, keeps the components when the same layout applies again; writes the summary trace. ENV-U10: a layout with
 *  a "ground" section also gets its ground strips (S08EnvGround::Spawn on the same tray top rectangle, kept in
 *  Runtime.Ground, traced 'ARTPREVIEW envlayout ground ...') and loses them with the props. */
UNMATCHED_API void Update(const FS08EnvLayoutRequest& Request, AActor& Owner, USceneComponent* Parent,
                          FS08EnvLayoutRuntime& Runtime, TArray<TObjectPtr<UStaticMeshComponent>>& Props,
                          TArray<TObjectPtr<UPointLightComponent>>& Lights);
/** The board actor's tray hook (map-image branch of UpdateDioramaTray): when the applied layout has a tray (or an
 *  apron) that covers the frame, replaces the placeholder fit inputs by the layout's (TrayFit) and traces
 *  'ARTPREVIEW envlayout tray ... source=layout|apron'; a refused layout tray is traced and the inputs stay. The tray
 *  line itself (PlaceDioramaTray) keeps its 'waiver=T1-placeholder' field. Since ENV-U10 only the T1 fallback of a
 *  map-image board uses it (SM_TableBase_T2 not in the build); ApplyTrayT2 is the regular hook. */
UNMATCHED_API bool ApplyTray(const FS08EnvLayoutRuntime& Runtime, const FVector2D& FrameHalf,
                             FVector2D& InOutBoardHalf, FVector2D& InOutOffset);
/** ENV-U10 track TRAY: the map-image tray hook of the shared rocky tray T2 (S08Diorama::FitTrayT2: scale 1, never
 *  stretched). When the applied valid layout has a tray (or an apron) that covers the frame (TrayFit), its OUTER half
 *  extent (halfX, halfY) and offsetY replace InOutHalf / InOutOffsetY and OutSource = layout | apron, traced
 *  'ARTPREVIEW envlayout tray map=.. source=.. outerHalf=.. offsetY=.. frameHalf=.. mesh=T2 t2Top=.. mismatchUU=..';
 *  otherwise the inputs (the T2 default) stay, OutSource is untouched and a refused layout tray is traced. */
UNMATCHED_API bool ApplyTrayT2(const FS08EnvLayoutRuntime& Runtime, const FVector2D& FrameHalf, FVector2D& InOutHalf,
                               float& InOutOffsetY, FString& OutSource);
}  // namespace S08EnvLayout

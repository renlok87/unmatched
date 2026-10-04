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
// Gate: the board actor spawns the environment only on the art look with the tray (S08Diorama::Enabled; both the
// default since ART-DEFAULT 2026-10-04 - rollbacks -S08GreyBoard / -S08DioramaLegacy, S08ArtLook.h), without
// -ArtPreviewNoEnv (A/B and perf opt-out), and only while a 'map-image' art profile is active. A grid board
// (Cobble, the 'tiles' fixtures) never loads a layout nor creates a component; a board change destroys what was
// spawned. A missing mesh skips its props (traced), never the whole layout. Invalid documents spawn nothing.
// Trace (evidence contract):
//   ARTPREVIEW envlayout map=<m> props=N lights=M missingMeshes=K ... status=ok|invalid|absent
//   ARTPREVIEW envlayout prop id=.. / light id=.. / missing mesh=.. / skipped id=.. / tray ... / off ...
// Everything except Spawn / Update / Clear is world-free and automation-tested (S08EnvLayoutTests.cpp,
// Unmatched.S08.EnvLayout.*).
//
// ENV-MAPS P5c track V:
//  * optional "fx" section - Niagara systems (derived copies under /Game/EnvKit/, never a pack folder in place):
//      "fx": [ {"id":"fire-campfire-nw", "system":"/Game/EnvKit/FX/NS_Env_Campfire", "anchor":"campfire-nw",
//               "loc":[0,0,6], "yawDeg":0, "scale":1, "seed":1234, "warmupS":1.5, "enabled":true,
//               "user":{"SpawnRate":8, "Color":[1.6,0.8,1.0,1]}} ]
//    "anchor" (optional) = a prop id: loc is then an offset from that prop's pivot (rotated by its yaw, not scaled) and
//    the fx spawns only when the prop spawned. Spawned only on map-image boards (Update), never with -ArtPreviewNoFx;
//    a system with an enabled Light / Component renderer is refused (light budget: no dynamic lights from VFX); an fx
//    whose pivot lies on the painted map is skipped. Deterministic frames: a fixed random seed per fx (seed, else the
//    CRC of the id), warmup = warmupS of simulation in fixed 1/30 s ticks at spawn (AdvanceSimulation), and in -Bench
//    (or with -EnvFxFreeze) the systems are paused after the warmup (-EnvFxLive keeps them running in -Bench).
//    Trace: 'ARTPREVIEW envlayout fx id=.. system=.. ...' per fx and 'ARTPREVIEW envlayout fx map=.. fx=N ...'.
//  * layout variants: -EnvLayoutVariant=<name> overlays <Dir>/<map>.<name>.layout.json (schema
//    "unmatched.env-layout-overlay/1": props / fx {remove:[ids], replace:[{id, fields..}], add:[entries]}) on the base
//    layout; the merged document is validated like a base layout. No flag = no overlay (the base, byte for byte); a
//    missing or invalid overlay falls back to the base (traced 'ARTPREVIEW envlayout variant=<name> ... status=absent|
//    invalid fallback=base'). Removing a prop also removes the fx anchored on it.
//
// ENV-MAPS P8 (lit3d scene, docs/art-pipeline/ENV-P8-3D-UNDER-PAINT-TASK.md): a prop may carry an optional "material"
// override (also replaceable / addable by an overlay): a package path string = EVERY slot of the mesh gets that material
// interface; an array = per slot (index = material slot, null or "" = keep the mesh's own; at most 16 entries, extra
// entries past the mesh's slots are ignored). A material that does not load keeps the mesh's own (traced 'ARTPREVIEW
// envlayout missing material=..'); the prop line gets ' material=<name|per-slot>x<slots set>' only when the field is
// present (every other line stays byte-identical).
#pragma once

#include "CoreMinimal.h"
#include "S08EnvGround.h"
#include "UObject/ObjectPtr.h"

class AActor;
class USceneComponent;
class UStaticMeshComponent;
class UPointLightComponent;
class UNiagaraComponent;
class UNiagaraSystem;

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
/** P8: the per-slot form of a prop's "material" override has at most this many entries. */
constexpr int32 MaxMaterialSlots = 16;
constexpr float MaxPropScale = 20.0f;
/** Shared budget of AGENTS/W4-A: 1 directional key + <= 6 point lights on screen (art profile + layout). */
constexpr int32 CombinedPointBudget = 6;
/** Tolerance of the tray-vs-apron consistency note (uu). */
constexpr float TrayApronToleranceUU = 1.0f;
/** P5c "fx" section (Niagara). Budget per board: a few hundred particles (the trace sums them after the warmup). */
constexpr int32 MaxFx = 48;
constexpr int32 MaxFxUserParams = 16;
constexpr float MaxFxScale = 10.0f;
constexpr float DefaultFxWarmupS = 2.0f;
constexpr float MaxFxWarmupS = 10.0f;
/** Fixed warmup tick (AdvanceSimulation): the same ticks on every run = reproducible -Bench frames. */
constexpr float FxWarmupTickS = 1.0f / 30.0f;
/** Fx systems are derived copies under the kit root (cooked by DirectoriesToAlwaysCook /Game/EnvKit). */
inline const TCHAR* const FxRoot = TEXT("/Game/EnvKit/");
/** -ArtPreviewNoFx: keep the environment but spawn no fx (A/B frames, perf gate). */
inline const TCHAR* const NoFxFlagName = TEXT("ArtPreviewNoFx");
/** -EnvFxFreeze: pause every fx after its warmup (also outside -Bench); -EnvFxLive: keep them running in -Bench. */
inline const TCHAR* const FxFreezeFlagName = TEXT("EnvFxFreeze");
inline const TCHAR* const FxLiveFlagName = TEXT("EnvFxLive");
inline const TCHAR* const BenchFlagName = TEXT("Bench");
/** -EnvLayoutVariant=<name>: overlay <Dir>/<map>.<name>.layout.json on the base layout. */
inline const TCHAR* const VariantParam = TEXT("EnvLayoutVariant=");
inline const TCHAR* const OverlaySchema = TEXT("unmatched.env-layout-overlay/1");
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
  /** P8: the optional "material" override (see the file comment): bMaterialAllSlots = one path for every slot,
   *  else Materials[slot] ("" = the mesh's own). Empty = no override. */
  TArray<FString> Materials;
  bool bMaterialAllSlots = false;
  /** The override for one slot ("" = none). */
  FString MaterialForSlot(int32 Slot) const;
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

/** One Niagara user parameter override of an fx entry: 1..4 numbers (the type comes from the system's exposed
 *  parameter at spawn: float / int / bool / vec2 / vec3 / position / vec4 / colour). */
struct UNMATCHED_API FS08EnvFxParam {
  FString Name;  // without the "User." prefix
  int32 Num = 1;
  FVector4 Value = FVector4(0.0, 0.0, 0.0, 0.0);
  FString ValueString() const;
};

/** One entry of the optional "fx" section. */
struct UNMATCHED_API FS08EnvFx {
  FString Id;
  FString System;  // /Game/EnvKit/... package path of a UNiagaraSystem, optionally "Pkg.Obj"
  FString Anchor;  // optional prop id: Loc is then relative to that prop's pivot (rotated by its yaw)
  FVector Loc = FVector::ZeroVector;
  float YawDeg = 0.0f;
  float Scale = 1.0f;
  bool bSeedSet = false;
  int32 Seed = 0;
  float WarmupS = S08EnvLayoutSpec::DefaultFxWarmupS;
  bool bEnabled = true;
  TArray<FS08EnvFxParam> User;
  /** Seed, or a stable CRC of the id (the same on every run). */
  int32 EffectiveSeed() const;
  /** Fixed warmup ticks of FxWarmupTickS. */
  int32 WarmupTicks() const;
  /** Relative transform under the board actor root; AnchorProp = the prop named by Anchor (nullptr = board space). */
  FTransform Transform(const FS08EnvProp* AnchorProp) const;
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
  /** P5c: the optional Niagara fx (an invalid entry makes the whole layout invalid, like a prop). */
  TArray<FS08EnvFx> Fx;
  FString Notes;
  /** LoadFile only: the file and the sha256 of its bytes (evidence). */
  FString SourcePath;
  FString SourceSha256;
  /** S08EnvLayout::ApplyVariant only: the overlay applied on top of the base (empty = none). */
  FString Variant;
  FString OverlayPath;
  FString OverlaySha256;
  /** ENV-MAPS P7 (concept paste): ids of the props / fx the applied overlay added or replaced (MergeOverlay); every other
   *  entry is a 'base' one (FS08ConceptHide::bBaseProps / bBaseFx hide those). Empty without an overlay. */
  TSet<FString> OverlayPropIds;
  TSet<FString> OverlayFxIds;

  /** Parses and validates the whole document; any structural error makes it invalid (false, nothing spawns). */
  bool ParseJson(const FString& Text, TArray<FString>& OutErrors);
  bool LoadFile(const FString& Path, TArray<FString>& OutErrors);
  /** Unique mesh package paths of the props (first-use order). */
  TArray<FString> UniqueMeshPaths() const;
  /** Unique Niagara system paths of the fx (first-use order). */
  TArray<FString> UniqueFxSystemPaths() const;
  const FS08EnvProp* FindProp(const FString& Id) const;
};

/** What -EnvLayoutVariant did (also its trace line). */
struct UNMATCHED_API FS08EnvVariantResult {
  FString Name;           // empty = no variant requested
  FString Status;         // none | ok | absent | invalid
  FString Path;           // overlay file
  FString Sha256;         // of the overlay bytes (ok / invalid)
  int32 PropsRemoved = 0;
  int32 PropsReplaced = 0;
  int32 PropsAdded = 0;
  int32 FxRemoved = 0;
  int32 FxRemovedWithAnchor = 0;  // fx dropped because the overlay removed their anchor prop
  int32 FxReplaced = 0;
  int32 FxAdded = 0;
  TArray<FString> Errors;
  /** 'ARTPREVIEW envlayout variant=<name|none> map=<m> status=.. ...' */
  FString TraceLine(const FString& MapKey) const;
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
  int32 MaterialOverrides = 0;    // P8: slots that got a "material" override
  int32 MissingMaterials = 0;     // P8: unique override paths that did not load (the mesh's own stays)
  TArray<FString> MissingPaths;
  /** Ids of the props that got a component (fx anchors need a spawned prop). */
  TSet<FString> SpawnedPropIds;
  /** ENV-MAPS P7: the id of every component Spawn appended, in the order of OutProps / OutLights. */
  TArray<FString> PropComponentIds;
  TArray<FString> LightComponentIds;
};

/** How fx spawn (FromCommandLine for the board actor; tests build their own). */
struct UNMATCHED_API FS08EnvFxOptions {
  bool bSpawn = true;     // false = -ArtPreviewNoFx
  bool bActivate = true;  // false: components are created and configured but never simulated (automation)
  bool bFreeze = false;   // still after the warmup (-Bench unless -EnvFxLive, or -EnvFxFreeze): time dilation 0 (P7c)
  bool bBench = false;
  /** Automation only: systems by layout path instead of loading packages. */
  TMap<FString, UNiagaraSystem*> Preloaded;
  static FS08EnvFxOptions FromCommandLine();
  /** off | frozen | live | inactive */
  FString Mode() const;
};

/** What one SpawnFx did (also the fx summary trace). */
struct UNMATCHED_API FS08EnvFxStats {
  int32 LayoutFx = 0;
  int32 Fx = 0;                    // Niagara components created
  int32 MissingSystems = 0;        // unique system paths that did not load
  int32 SkippedMissing = 0;
  int32 SkippedDisabled = 0;       // "enabled": false
  int32 SkippedAnchor = 0;         // anchor prop not spawned (missing mesh / removed / inside the map)
  int32 SkippedInsideMap = 0;      // pivot on the painted map (circles stay readable)
  int32 SkippedLightRenderer = 0;  // the system has an enabled Light / Component renderer (light budget)
  int32 NearBand = 0;              // spawned between the map and the K1 camera (traced, not refused)
  int32 GpuEmitters = 0;           // enabled GPU-sim emitters of the spawned systems (not deterministic)
  int32 NonDeterministic = 0;      // spawned fx whose system lacks bDeterminism or simulates on the GPU
  int32 Particles = 0;             // live particles after the warmup (0 when not activated)
  int32 UserSet = 0;               // user parameters applied
  int32 UserMissing = 0;           // user parameters the system does not expose (or with the wrong arity)
  int32 Frozen = 0;                // ENV-MAPS P7c: fx frozen by time dilation 0 after the warmup (trace 'still=')
  FString Mode;
  TArray<FString> MissingPaths;
  /** ENV-MAPS P7: the id of every component SpawnFx appended, in the order of OutFx. */
  TArray<FString> FxComponentIds;
};

/** Inputs of one board-actor update (the actor fills it from its active art profile). */
struct UNMATCHED_API FS08EnvLayoutRequest {
  bool bEnabled = false;         // S08EnvLayout::Enabled(art look)
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
  /** P5c: unset = the command line (-EnvLayoutVariant=, -ArtPreviewNoFx, -Bench, -EnvFxFreeze / -EnvFxLive). */
  TOptional<FString> Variant;
  TOptional<FS08EnvFxOptions> FxOptions;
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
  /** P5c: the Niagara fx of Layout.Fx (SpawnFx). Weak like Ground: the board actor owns the components. */
  TArray<TWeakObjectPtr<UNiagaraComponent>> Fx;
  FS08EnvFxStats FxStats;
  FS08EnvVariantResult Variant;
};

namespace S08EnvLayout {
/** The art look AND the tray (S08Diorama::Enabled: default, -S08DioramaLegacy off) AND NOT -ArtPreviewNoEnv. */
UNMATCHED_API bool Enabled(bool bArtLook);
UNMATCHED_API bool OptOut();
/** Enabled(bArtPreview) plus its trace: 'ARTPREVIEW envlayout enabled dir=.. source=pak|override files=N', or
 *  'ARTPREVIEW envlayout disabled (-ArtPreviewNoEnv)' when the diorama is on but the environment opted out; nothing
 *  without the diorama flag (the previous board, byte for byte). */
UNMATCHED_API bool Arm(bool bArtLook);
/** Automation only: force -ArtPreviewNoEnv on/off (Reset -> command line). The diorama flag has its own override. */
UNMATCHED_API void SetOptOutOverrideForTest(bool bOptOut);
UNMATCHED_API void ResetOptOutOverrideForTest();
/** -ArtPreviewNoFx. */
UNMATCHED_API bool FxOptOut();
/** -EnvLayoutVariant=<name> (empty = none; an invalid name is traced by Update and ignored). */
UNMATCHED_API FString VariantFromCommandLine();
/** Variant names: [a-z0-9-], 1..32 characters. */
UNMATCHED_API bool IsVariantName(const FString& Name);
/** <Dir>/<MapKey>.<Variant>.layout.json */
UNMATCHED_API FString OverlayFileFor(const FString& Dir, const FString& MapKey, const FString& Variant);
/** True for an overlay file name ("<map>.<variant>.layout.json"): never a base layout (Resolve / Arm skip it). */
UNMATCHED_API bool IsOverlayFileName(const FString& FileName);
/** World-free merge: applies the overlay document OverlayText on the base document BaseText (props / fx remove ->
 *  replace -> add) and validates the merged document as a layout (Out). False with errors (Out untouched) when the
 *  overlay or the merged document is invalid. Counts go to InOutResult. */
UNMATCHED_API bool MergeOverlay(const FString& BaseText, const FString& OverlayText, const FString& MapKey,
                                const FString& Variant, FS08EnvLayout& Out, FS08EnvVariantResult& InOutResult);
/** Applies -EnvLayoutVariant (Variant) to a valid base layout loaded from InOutLayout.SourcePath: none (empty name) /
 *  absent (no overlay file) / invalid (bad name or document: the base stays) / ok (InOutLayout = the merged layout,
 *  Variant / OverlayPath / OverlaySha256 set; SourcePath / SourceSha256 stay the base's). */
UNMATCHED_API FS08EnvVariantResult ApplyVariant(const FString& Dir, const FString& MapKey, const FString& Variant,
                                                FS08EnvLayout& InOutLayout);

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
/** P5c: one UNiagaraComponent per enabled fx entry under Parent, owned by Owner (no collision, no shadow, no
 *  scalability culling, the fixed seed, the user parameters typed by the system's exposed parameters), activated,
 *  warmed up in WarmupTicks() fixed ticks and held still (time dilation 0, P7c) when Options.bFreeze; traced per fx. Skips (traced): disabled,
 *  anchor prop not in SpawnedPropIds, pivot on the painted map, missing system, a system with an enabled Light /
 *  Component renderer. FrameHalf feeds the near-band count. Nothing when !Options.bSpawn. */
UNMATCHED_API FS08EnvFxStats SpawnFx(const FS08EnvLayout& Layout, AActor& Owner, USceneComponent* Parent,
                                     const FVector2D& MapHalf, const FVector2D& FrameHalf,
                                     const TSet<FString>& SpawnedPropIds, const FS08EnvFxOptions& Options,
                                     TArray<TWeakObjectPtr<UNiagaraComponent>>& OutFx);
UNMATCHED_API int32 ClearFx(TArray<TWeakObjectPtr<UNiagaraComponent>>& Fx);
/** 'ARTPREVIEW envlayout fx map=<m> fx=N layoutFx=M ...' */
UNMATCHED_API FString FxSummaryLine(const FString& MapKey, const FS08EnvFxStats& Stats);
/** The board-actor hook: clears on a board change / gate off, (re)loads and spawns the layout of the active map-image
 *  profile, keeps the components when the same layout applies again; writes the summary trace. ENV-U10: a layout with
 *  a "ground" section also gets its ground strips (S08EnvGround::Spawn on the same tray top rectangle, kept in
 *  Runtime.Ground, traced 'ARTPREVIEW envlayout ground ...') and loses them with the props. P5c: the -EnvLayoutVariant
 *  overlay is applied before anything spawns (part of the same-layout key), and the "fx" section spawns after the
 *  ground (Runtime.Fx, cleared with the props). */
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

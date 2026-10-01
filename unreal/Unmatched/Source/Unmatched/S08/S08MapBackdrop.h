// ENV-MAPS P5 track C (concept review 2026-10-01 gap 8): the procedural night backdrop of a map-image board.
//
// The profile "backdrop" block (S08BoardArt.h FS08BackdropSpec, parsed and validated with the board profiles) asks for
// <= 2 large unlit translucent mist planes far under the tray (/Engine/BasicShapes/Plane with a MID of
// /Game/EnvMaps/M_MapBackdropMist: value noise panning slowly, elliptic edge fade) and one soft moon-glow card in the
// upper-left of the far zoom view (MID of /Game/EnvMaps/M_MapBackdropMoon, additive). Both materials are built out of git
// by tools/art/map_surface/ue_import_map_surface.py with Apply Fogging off (the night fog starts at 2900 uu and would wash
// them out; the fog actor and its start distance are not touched). The parts light nothing: unlit, no shadow, no
// dynamic indirect / distance-field lighting, invisible to ray tracing and reflection / sky captures; every part is
// below S08MapSurfaceSpec::BackdropMaxZ, so the opaque tray, frame and props are always in front of it (the parser
// rejects a block that would reach higher). Nothing is created on grid boards, the grey topology view, a refused
// map-image profile, or without the environment gate (-ArtPreview -ArtPreviewDiorama, no -ArtPreviewNoEnv); a missing
// material spawns nothing (traced). Status: предложено (the look is calibrated in UE frames, not here).
#pragma once

#include "CoreMinimal.h"
#include "S08BoardArt.h"

class AActor;
class USceneComponent;
class UStaticMesh;
class UStaticMeshComponent;

/** What the last Update applied (AS08BoardActor::GetBackdropRuntime; the components live in its UPROPERTY array). */
struct UNMATCHED_API FS08BackdropRuntime {
  FString ProfileId;     // the profile the parts belong to ("" = none)
  int32 MistPlanes = 0;
  bool bMoon = false;
  /** ok | off (no block / not a map-image board / env gate closed) | missing-plane | missing-material */
  FString Status = TEXT("off");
  bool bTraced = false;  // a backdrop line was ever written (a grid-only run writes none)
};

namespace S08MapBackdrop {
/** Component names of the parts (tests and traces). */
UNMATCHED_API FName MistComponentName(int32 Index);
UNMATCHED_API FName MoonComponentName();
/** Spawns the backdrop of the active map-image profile, keeps it when the same profile is applied again, or clears it
 *  (bActive false / no block). A grid-only run (nothing ever applied) writes no trace line and creates nothing. */
UNMATCHED_API void Update(bool bActive, const FString& ProfileId, const FS08BackdropSpec& Spec, const FVector2D& MapHalf,
                          AActor& Owner, USceneComponent* Root, UStaticMesh* Plane,
                          TArray<TObjectPtr<UStaticMeshComponent>>& Parts, FS08BackdropRuntime& Runtime);
/** Destroys every part (Runtime back to 'off'; bTraced kept). */
UNMATCHED_API void Clear(TArray<TObjectPtr<UStaticMeshComponent>>& Parts, FS08BackdropRuntime& Runtime);
}  // namespace S08MapBackdrop

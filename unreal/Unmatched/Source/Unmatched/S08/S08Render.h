// W4-A render policy (user decision 2026-09-28: DX12/SM6 + Lumen now, High as
// the acceptance reference for K1-K3 and ACC-022; engine gate memo §1 items
// 1, 2 and 7, C:/tmp/p0-review/engine-gate-memo.md).
//
//  * RENDER fingerprint: one trace line per SHOT with the effective RHI,
//    feature level / shader platform, GI and reflection method (requested and
//    what the platform can run), shadow method, every sg.* group, screen
//    percentage, AA, the exposure and light units of the applied profile,
//    t.MaxFPS / VSync / FrameRateLimit and the sha256 of the board profile
//    data. tools/art/classify_evidence.py and tools/art/qa010 reject frames
//    without it or off the reference (docs/art-pipeline/render-reference.json).
//  * Game layer: zone strokes and glyphs, selection/target rings, reachable /
//    illegal cell marks and the team bases of grey fighters render unlit with
//    EyeAdaptationInverse (/Game/S08/Render/M_S08_GameLayerUnlit), cast no
//    shadow and stay out of Lumen / distance-field lighting, so their
//    readability depends on neither the light profile nor the exposure.
//  * -S08LegacyRender reproduces the pre-W4 look in the same binary (Unitless
//    points, no SkyLight / exposure volume, M_S08_Solid game layer) for the
//    DX11-old leg of the bench; its fingerprint says legacyRender=1.
#pragma once

#include "CoreMinimal.h"

class UMaterialInterface;
class UPrimitiveComponent;
class UWorld;

/** Hex sha256 of a byte buffer (UE 5.8 has no Windows FPlatformMisc SHA256). */
UNMATCHED_API FString S08Sha256Hex(const uint8* Data, int64 Size);

/** -S08LegacyRender: pre-W4 lights/exposure/game-layer (bench comparison only). */
UNMATCHED_API bool S08LegacyRender();

/** Unlit EyeAdaptationInverse game-layer material; falls back to
 *  /Game/S08/M_S08_Solid (legacy flag or asset missing). Both carry "Tint". */
UNMATCHED_API UMaterialInterface* S08GameLayerMaterial();
/** True when S08GameLayerMaterial() is the W4-A unlit material. */
UNMATCHED_API bool S08GameLayerIsUnlit();
/** Game-layer primitive: no shadow, no Lumen / distance-field contribution. */
UNMATCHED_API void S08ApplyGameLayerPrimitive(UPrimitiveComponent* Component);

/** What the board actor applied from the active light profile (fingerprint). */
struct UNMATCHED_API FS08AppliedRender {
  bool bArt = false;
  FString ProfileId;          // light profile id, "-" when none
  FString PointUnits;         // candelas | unitless-legacy | -
  bool bSky = false;
  float SkyIntensity = 0.0f;
  bool bExposure = false;     // unbound exposure volume spawned
  float ExposureMin = 1.0f;
  float ExposureMax = 1.0f;
  float ExposureBias = 1.0f;  // engine default when no volume (r.DefaultFeature.AutoExposure=0)
  float Ev100 = 0.0f;
  FString ProfilesSha256;     // sha256 of the loaded S08ArtBoardProfiles.json bytes
  FString ProfilesSource;     // pak | override
  int32 ShadowCasters = 0;    // lights with CastShadows (C-8: 1 = the key)
  FString KeyShadow;          // csm distance/cascades as applied
};

/** One "RENDER ..." trace line (no trailing newline). Tag = SHOT/BENCH/... */
UNMATCHED_API FString S08RenderFingerprint(const UWorld* World, const FS08AppliedRender& Applied,
                                           const TCHAR* Tag);
/** reference=1 when the effective state equals the W4-A reference
 *  (D3D12 + SM6 + Lumen GI and reflections + sg.* = 2 + SP 100 + fixed
 *  profile exposure + candela units + packaged profile data). */
UNMATCHED_API bool S08RenderIsReference(const FS08AppliedRender& Applied, FString& OutWhyNot);

/** -S08RenderPreset=Low|Medium|High|Epic applies sg.* (0..3) before the first
 *  frame (the bench and evidence scripts pass High; players keep their saved
 *  settings). Returns the preset name applied or empty. */
UNMATCHED_API FString S08ApplyRenderPresetFromCommandLine();

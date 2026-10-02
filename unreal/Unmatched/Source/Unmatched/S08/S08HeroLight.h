// ENV-MAPS P9 (docs/art-pipeline/ENV-HERO-LIGHT.md): the hero light - a small "stage" rig per figure that lights ONLY the
// figure, so the figures read against the dark board without brightening the environment (the user keeps the dark
// night look: «общее освещение темное, и оно мне нравится. Все сцены»).
//
// The ready-made engine function is the Lighting Channels of UE 5.8 (no free Fab asset does character lighting, see the doc):
//   * per figure <= 2 SpotLights on lighting channel 1 ONLY. P9b (2026-10-02 review «сильно пересвечены»: an ACCENT, not a
//     main light): H-key from the moon side, 60-90 deg off the camera azimuth and ~45 deg down (form shading agrees with
//     the board's moon key; no coaxial "flash"), at 1-2 x the moon key's lux, reduced specular; H-rim low (12-22 deg) from
//     behind the figure relative to the camera, <= 0.5 x the key, narrow cone: a thin cool edge, not a wash;
//   * per layer "specularScale" (0..1, default 1: ULightComponent::SpecularScale - less sheen on the PBR figures) and
//     "contactShadowLength" (0..0.5 screen-space units, default 0 = off): the layer's screen-space contact shadows so
//     wings / arms / folds occlude it. A layer with contact shadows has CastShadows on but ShadowResolutionScale 0 (no
//     shadow map is ever rendered for it; the deferred light pass traces the contact ray only); 0 = CastShadows off;
//   * the figure meshes (ArtBody, ArtPlaceholder, the grey Body box) on channels 0 AND 1; the pedestal (ArtBase) only when
//     the block says "litPedestal": true (default false: the dark bronze base stays as the scene lights it); everything
//     else (map, frame, island, props, team rings, labels) stays on channel 0 only: the hero light never reaches them;
//   * no Lumen GI / volumetric / translucency contribution (IndirectLightingIntensity 0, VolumetricScatteringIntensity 0,
//     AffectTranslucentLighting off, ray-traced GI off): the translucency lighting volume and the Lumen surface cache
//     ignore lighting channels, so these are the only leaks and they are closed;
//   * the components are children of the fighter actor (they follow every move) and are rebuilt only when the profile
//     block, the figure height or the budget changes;
//   * states: the active fighter (selected or the combat attacker) x activeMul with a slow breathing pulse
//     (breathHz, +-breathAmp; frozen runs = -Bench without -EnvFxLive or -EnvFxFreeze: exactly activeMul, no pulse),
//     others x 1, a defeated fighter x defeatedMul (0 = off);
//   * profile block "heroLight" in every light profile of S08ArtBoardProfiles.json (FS08LightProfile::HeroLight); a light
//     profile without the block = no rig; -NoHeroLight removes the rig (A/B frames), and so does -ArtPreviewLightsOff (gate
//     G1: no engine light at all) and -S08LegacyRender (the pre-W4 bench emulation); works on SM5 (deferred lighting
//     channels, screen-space contact shadows).
// Budget (a separate figure-only category, not the environment's 1 key + <= 6 points): <= 2 lights per figure, <= 14 per
// board (LayersForBoard: more than 7 lit figures keep the key only, more than 14 light the first 14). Intensities are given as the illuminance (lux) at the
// figure's aim point and converted to candelas per figure (lux x distance_m^2), so every figure height reads the same.
// Trace: 'ARTPREVIEW hero-light board ...' (per board / budget change), 'ARTPREVIEW hero-light rig ...' (per rig build:
// placement, cd, specular, contact shadow, pedestal) and 'ARTPREVIEW hero-light fighter=... state=...' (per fighter state
// change). Status: предложено; "художественно принято" is the user's decision only.
#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

namespace S08HeroLightSpec {
/** -NoHeroLight: no rig on any board (A/B frames for gates H1 / H2). */
inline const TCHAR* const OptOutFlagName = TEXT("NoHeroLight");
/** The lighting channel of the rig (channel 0 = the scene). */
constexpr int32 Channel = 1;
constexpr int32 MaxLightsPerFigure = 2;
constexpr int32 MaxLightsPerBoard = 14;
/** Fallback figure height (uu) when the actor reports none. */
constexpr float DefaultFigureHeightUU = 55.0f;
/** Breathing pulse update (timer) in live runs. */
constexpr float PulseTickS = 1.0f / 30.0f;
}  // namespace S08HeroLightSpec

/** Fighter state as the rig sees it. */
enum class ES08HeroLightState : uint8 { Off, Idle, Active, Defeated };

UNMATCHED_API const TCHAR* S08HeroLightStateName(ES08HeroLightState State);

/** One spot layer of the rig ("key" / "rim"). Angles in degrees; azimuth relative to the camera azimuth, counter-clockwise
 *  (world yaw); elevation = the pitch down from the light to the aim point. */
struct UNMATCHED_API FS08HeroLightLayer {
  bool bSet = false;
  float Lux = 0.0f;                      // illuminance at the aim point (lux) -> candelas per figure
  FColor ColorSrgb = FColor::White;      // "colorSrgb" #RRGGBB
  float InnerConeDeg = 22.0f;
  float OuterConeDeg = 34.0f;
  float HeightMul = 2.5f;                // light Z above the play plane = HeightMul x figure height
  float AzimuthDeg = 35.0f;              // + camera azimuth = the world yaw from the figure to the light
  float ElevationDeg = 60.0f;            // pitch down to the aim point (5..89)
  float RadiusMul = 1.6f;                // attenuation radius = RadiusMul x the light-to-aim distance
  float SpecularScale = 1.0f;            // "specularScale" 0..1: ULightComponent::SpecularScale (P9b: less sheen)
  float ContactShadowLength = 0.0f;      // "contactShadowLength" 0..0.5 (screen-space units), 0 = no contact shadow
  /** The layer traces screen-space contact shadows (CastShadows on, ShadowResolutionScale 0: never a shadow map). */
  bool HasContactShadow() const { return ContactShadowLength > 0.0f; }
  FLinearColor Linear() const { return FLinearColor::FromSRGBColor(ColorSrgb); }
};

/** "heroLight" block of a light profile. */
struct UNMATCHED_API FS08HeroLightSpec {
  bool bSet = false;      // the profile has the block
  bool bEnabled = false;  // "enabled": true
  float CameraAzimuthDeg = 90.0f;  // world yaw from the board towards the K1 camera (the camera looks along -Y)
  float AimHeight = 0.55f;         // aim point = AimHeight x figure height
  /** "litPedestal" (P9b, default false): the pedestal (ArtBase) joins channel 1 too; false = only the body / placeholder. */
  bool bLitPedestal = false;
  FS08HeroLightLayer Key;
  FS08HeroLightLayer Rim;
  float ActiveMul = 1.35f;
  float BreathHz = 0.4f;
  float BreathAmp = 0.08f;
  float DefeatedMul = 0.0f;
  /** Layers this block lights per figure (key, + rim when set): 0..2. */
  int32 Layers() const { return (Key.bSet ? 1 : 0) + (Rim.bSet ? 1 : 0); }
  /** Stable text of every value (the fighter rebuilds its rig only when it changes). */
  FString Signature() const;
};

/** Where one layer stands for one figure (fighter-actor space: the root is the cell centre on the play plane). */
struct UNMATCHED_API FS08HeroLightPlacement {
  FVector Location = FVector::ZeroVector;
  FRotator Rotation = FRotator::ZeroRotator;  // points at the aim point
  FVector Aim = FVector::ZeroVector;
  float DistanceUU = 0.0f;
  float Candelas = 0.0f;
  float AttenuationRadiusUU = 0.0f;
};

namespace S08HeroLight {
/** Parses the optional "heroLight" object of light profile ProfileId (every field validated, unknown fields refused;
 *  layer fields lux 0..50, specularScale 0..1, contactShadowLength 0..0.5; block field litPedestal bool);
 *  false (+ an error line) on a broken block. Absent block = true and Out.bSet false. */
UNMATCHED_API bool Parse(const FString& ProfileId, const TSharedPtr<FJsonObject>& LightProfile, FS08HeroLightSpec& Out,
                         TArray<FString>& Errors);
/** The placement of Layer for a figure of height FigureHeightUU (<= 0 -> DefaultFigureHeightUU). */
UNMATCHED_API FS08HeroLightPlacement Place(const FS08HeroLightSpec& Spec, const FS08HeroLightLayer& Layer,
                                           float FigureHeightUU);
/** Intensity multiplier of a state at TimeS (Active: ActiveMul x (1 + BreathAmp sin(2 pi BreathHz t + Phase)),
 *  exactly ActiveMul when bFrozen; Idle 1; Defeated DefeatedMul; Off 0). */
UNMATCHED_API float StateMultiplier(const FS08HeroLightSpec& Spec, ES08HeroLightState State, double TimeS, bool bFrozen,
                                    float Phase = 0.0f);
/** Layers per figure for LitFigures figures on one board within MaxLightsPerBoard: Spec.Layers() while it fits, else 1
 *  (the key only; with more than MaxLightsPerBoard figures the caller lights the first MaxLightsPerBoard of them). */
UNMATCHED_API int32 LayersForBoard(const FS08HeroLightSpec& Spec, int32 LitFigures);
/** -NoHeroLight on the command line. */
UNMATCHED_API bool OptOut();
}  // namespace S08HeroLight

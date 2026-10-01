// ENV-MAPS P7 (ENV-U15, docs/art-pipeline/ENV-CONCEPT-PASTE.md): the approved concept pasted around the real map field.
//
// The map field (the original map with its circles and links, the 3D frame-002, the figures and the game layer) stays
// real (layer A). Everything around it comes from the concept (layer B): the registered concept plates are projected
// from the concept camera C0 (k1_mock pinhole: HFOV 35, pitch -55, yaw -90, 2714.6 uu from the map centre) onto
//   * the depth sheet: a static mesh in board space whose vertices lie on C0 rays at the depth of a simple relief
//     (ground Z -3, forest canopy, bay ramp, front cliff, vertical flats at the painted base lines; built out of git by
//     tools/art/concept_paste/, imported by ue_import_concept_paste.py),
//   * the sea layer: a sea plane (engine plane) and a sky cylinder of engine-plane segments around it,
// with one unlit masked material (M_ConceptPaste, tools/art/concept_paste/ue_concept_material.py). The material projects
// per pixel: world position -> C0 pixel (the camera of this block) -> concept pixel (the registration homography) ->
// plate UV (the plate rectangles), so the mesh UVs are irrelevant and the sea layer needs no mesh asset. The painted
// light is in the plates: the layer is emissive (P7 tune: grade "aces-inverse" with the measured per-channel fit of the
// engine tone curve - fitScale / fitPower, selfcal at C0 - and "devignette" undoing the engine vignette on this layer; the
// LUT route stays supported but unused: a 256 x 1 .hdr imports as a TextureCube in 5.8), unlit, casts / receives nothing,
// adds nothing to Lumen GI. The cut lies under the 3D frame's outer
// foot (frame half - underFrameUU), so the seam is hidden in every view. The small 3D details (lanterns, fires,
// cannons, banner) are props / fx of the concept env-layout overlay (EnvLayouts/<map>.<variant>.layout.json); this
// block adds the true point lights of the main fires / lanterns (they light the figures and the frame, the painted
// pools are in the plates), their flicker, a sway of named props and contact-shadow blobs under the 3D details.
//
// Profile block "conceptPaste" (S08ArtBoardProfiles.json, map-image boards only; grids reject it, so Cobble and the art
// fixtures stay bit for bit). Mode per run (ResolveMode):
//   -NoConceptPaste / -ConceptPaste=0|off|false -> off; -ConceptPaste / -ConceptPaste=1|on|true -> on;
//   -EnvLayoutVariant=<variant> (the block's concept overlay, 'concept') -> on;
//   -EnvLayoutVariant=<offVariant> (Sarpedon: 'p5c') -> off and the BASE layout (no overlay: the P5c composition);
//   any other -EnvLayoutVariant -> off (that overlay applies as before); else the block's "default" (on | off).
// On = the env layout gets the concept overlay, the parts spawn and the block's "hide" list hides the painted-over
// parts (tray, ground strips, sea ring, waterfalls, backdrop, fog, base props / fx, layout lights). A missing required
// asset (material, sheet mesh, plate B) or a missing / invalid concept overlay turns it off (traced 'ARTPREVIEW
// concept-paste missing ...' / 'mode=off reason=overlay-...'): the P5c look stays. Status: предложено.
// Everything except Apply / ApplyHides / RestoreHides / the anim component is world-free (S08ConceptPasteTests.cpp,
// Unmatched.S08.ConceptPaste.*).
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "UObject/ObjectPtr.h"
#include "S08ConceptPaste.generated.h"

class AActor;
class FJsonObject;
class UExponentialHeightFogComponent;
class UMaterialInterface;
class UPointLightComponent;
class USceneComponent;
class UStaticMesh;
class UStaticMeshComponent;
class UTexture;
struct FS08EnvLayoutRuntime;

namespace S08ConceptPasteSpec {
/** Every asset of the block is a /Game/EnvMaps package (cooked with DirectoriesToAlwaysCook /Game/EnvMaps), never under
 *  the never-cooked data root. */
inline const TCHAR* const AssetRoot = TEXT("/Game/EnvMaps/");
inline const TCHAR* const NeverCookRoot = TEXT("/Game/EnvMaps/Data/");
inline const TCHAR* const DefaultMaterialPath = TEXT("/Game/EnvMaps/ConceptPaste/M_ConceptPaste");
inline const TCHAR* const PlaneMeshPath = TEXT("/Engine/BasicShapes/Plane.Plane");
inline const TCHAR* const ContactShadowMaterialPath = TEXT("/Game/EnvMaps/M_MapContactShadow.M_MapContactShadow");
/** Command line: -ConceptPaste[=0|1|on|off|true|false], -NoConceptPaste, -ConceptPasteCalib (the ramp card). */
inline const TCHAR* const FlagName = TEXT("ConceptPaste");
inline const TCHAR* const FlagValueParam = TEXT("ConceptPaste=");
inline const TCHAR* const NoFlagName = TEXT("NoConceptPaste");
inline const TCHAR* const CalibFlagName = TEXT("ConceptPasteCalib");
inline const TCHAR* const DefaultConceptVariant = TEXT("concept");
/** M_ConceptPaste parameters (ue_concept_material.py builds exactly these; the names are the contract). */
inline const TCHAR* const ParamPlateA = TEXT("PlateA");          // texture: centre plate (x2 detail), sRGB
inline const TCHAR* const ParamPlateB = TEXT("PlateB");          // texture: outskirts plate RGBA (A = matte x cut), sRGB
inline const TCHAR* const ParamMask = TEXT("Mask");              // texture: R = extra opacity, G = plate-A weight (B space)
inline const TCHAR* const ParamLut = TEXT("Lut");                // texture: 256 x 1 inverse-tonemap LUT (linear HDR)
inline const TCHAR* const ParamWater = TEXT("Water");            // texture: water masks (B space) R waterfall, G surf, B sea
inline const TCHAR* const ParamCamPos = TEXT("CamPos");          // vector: C0 location (board space = world)
inline const TCHAR* const ParamCamRight = TEXT("CamRight");      // vector: C0 screen right
inline const TCHAR* const ParamCamUp = TEXT("CamUp");            // vector: C0 screen up
inline const TCHAR* const ParamCamForward = TEXT("CamForward");  // vector: C0 view direction
inline const TCHAR* const ParamCamTan = TEXT("CamTan");          // vector: (tan half HFOV, tan half VFOV, W px, H px)
inline const TCHAR* const ParamHRow0 = TEXT("HRow0");            // vectors: registration homography rows (C0 px ->
inline const TCHAR* const ParamHRow1 = TEXT("HRow1");            //   concept px, both in the W x H frame of CamTan)
inline const TCHAR* const ParamHRow2 = TEXT("HRow2");
inline const TCHAR* const ParamRectA = TEXT("RectA");            // vector: plate A rectangle in concept px (x0, y0, w, h)
inline const TCHAR* const ParamRectB = TEXT("RectB");            // vector: plate B / mask rectangle in concept px
inline const TCHAR* const ParamCut = TEXT("Cut");                // vector: (half X, half Y, min Z, enabled 0|1)
inline const TCHAR* const ParamUseA = TEXT("UseA");              // scalar 0|1
inline const TCHAR* const ParamFeatherPx = TEXT("FeatherPx");    // scalar: plate A edge feather (concept px)
inline const TCHAR* const ParamAlphaWeight = TEXT("AlphaWeight");// scalar: 1 = opacity from plate B alpha x mask R
inline const TCHAR* const ParamOutsideKeep = TEXT("OutsideKeep");// scalar: 0 = clip outside plate B, 1 = edge clamp
inline const TCHAR* const ParamGradeMode = TEXT("GradeMode");    // scalar: 0 linear, 1 LUT, 2 inverse ACES (approx)
inline const TCHAR* const ParamGainLinear = TEXT("GainLinear");  // scalar: paint gain (linear display)
inline const TCHAR* const ParamEmissiveScale = TEXT("EmissiveScale");  // scalar: 1 / exposure scale (modes 0, 2)
inline const TCHAR* const ParamCalib = TEXT("Calib");            // scalar 0|1: the ramp card (-ConceptPasteCalib)
inline const TCHAR* const ParamCalibMax = TEXT("CalibMax");      // scalar: the ramp's top emissive value
inline const TCHAR* const ParamFlowRect0 = TEXT("FlowRect0");    // vectors: painted-water flow regions (concept px
inline const TCHAR* const ParamFlowRect1 = TEXT("FlowRect1");    //   x0, y0, w, h; w 0 = off)
inline const TCHAR* const ParamFlowVel0 = TEXT("FlowVel0");      // vectors: (pan px / s x, y, amplitude px, 0)
inline const TCHAR* const ParamFlowVel1 = TEXT("FlowVel1");
inline const TCHAR* const ParamFlowMaxZ = TEXT("FlowMaxZ");      // scalar: flow only below this world Z (the sea plane)
inline const TCHAR* const ParamUseWater = TEXT("UseWater");      // scalar 0|1: the flow regions x the water masks
inline const TCHAR* const ParamFlowSea = TEXT("FlowSea");        // scalar 0|1: region 0 reads mask B (sea) instead of R
inline const TCHAR* const ParamDevignette = TEXT("Devignette");  // scalar: the view's vignette intensity to undo (0 = off)
inline const TCHAR* const ParamGradeScale = TEXT("GradeScale");  // vector: grade 2 per-channel emissive scale (1 / k)
inline const TCHAR* const ParamGradePow = TEXT("GradePow");      // vector: grade 2 per-channel display power (1 / p)
constexpr int32 MaxFlows = 2;
constexpr float FlowFeatherPx = 8.0f;  // the region edge feather of the shader
constexpr int32 MaxLights = 6;
constexpr int32 MaxAnims = 32;
constexpr int32 MaxShadowBlobs = 16;
constexpr int32 MinSkySegments = 8;
constexpr int32 MaxSkySegments = 128;
constexpr float DefaultCalibMax = 16.0f;
/** The shared point-light budget (AGENTS / W4-A): 1 key + <= 6 points (profile + layout + this block). */
constexpr int32 CombinedPointBudget = 6;
/** Contact-shadow blobs sit this far above the surface they darken (no z-fight with the sheet). */
constexpr float BlobLiftUU = 0.4f;
}  // namespace S08ConceptPasteSpec

/** The concept camera C0 (k1_mock / cp_common.Cam): looks at Focus from DistanceUU along FRotator(Pitch, Yaw, 0);
 *  pixels x right / y down, continuous (pixel centres at i + 0.5), the VFOV from the aspect of SizePx. */
struct UNMATCHED_API FS08ConceptCamera {
  double DistanceUU = 2714.626;
  FVector Focus = FVector::ZeroVector;
  double PitchDeg = -55.0;
  double YawDeg = -90.0;
  double HFovDeg = 35.0;
  FIntPoint SizePx = FIntPoint(1920, 1080);
  FVector Forward() const;
  FVector Right() const;
  FVector Up() const;
  FVector Location() const;
  double TanHalfH() const;
  double TanHalfV() const;
  /** World -> continuous C0 pixel; false behind the camera. OutDepth = distance along Forward. */
  bool Project(const FVector& World, FVector2D& OutPx, double* OutDepth = nullptr) const;
  /** Unit ray through a C0 pixel. */
  FVector Ray(const FVector2D& Px) const;
};

/** Registration homography: C0 px -> concept px (rows, row-major). Identity = the plates are already rectified. */
struct UNMATCHED_API FS08ConceptHomography {
  double M[3][3] = {{1.0, 0.0, 0.0}, {0.0, 1.0, 0.0}, {0.0, 0.0, 1.0}};
  FVector2D Apply(const FVector2D& Px) const;
  bool IsIdentity(double Tolerance = 1e-9) const;
};

enum class ES08ConceptGrade : uint8 { Linear, Lut, AcesInverse };
UNMATCHED_API const TCHAR* S08ConceptGradeName(ES08ConceptGrade Grade);

/** "hide": what the painted surround replaces (names in the JSON list). */
struct UNMATCHED_API FS08ConceptHide {
  bool bTray = false;          // "tray": the diorama tray (T2 / T2b with its lip, or the T1 fallback)
  bool bGround = false;        // "ground": the env ground strips (EnvGround_*)
  bool bSea = false;           // "sea": the sea ring (EnvSea)
  bool bWaterfalls = false;    // "waterfalls": sheet / foam / lip / card / spill (EnvWaterfall_*)
  bool bBackdrop = false;      // "backdrop": the profile backdrop (mist planes, moon card)
  bool bFog = false;           // "fog": the light profile's height fog
  bool bBaseProps = false;     // "baseProps": layout props the concept overlay did not add or replace
  bool bBaseFx = false;        // "baseFx": base layout fx anchored on a base prop this list hid (free fx: the overlay)
  bool bLayoutLights = false;  // "layoutLights": every env-layout point light (this block's lights replace them)
  /** Names in the order above (trace). */
  FString Names() const;
};

/** A true point light of a painted fire / lantern (board space, candelas, no shadow). */
struct UNMATCHED_API FS08ConceptLight {
  FString Id;
  FVector Loc = FVector::ZeroVector;
  FColor Color = FColor::White;  // sRGB bytes ("colorSrgb")
  float IntensityCd = 0.0f;
  float RadiusUU = 0.0f;
  float FlickerAmp = 0.0f;       // 0 = steady; intensity x (1 + amp x noise), amp 0..0.5
  float FlickerHz = 0.0f;        // base frequency 0..20
};

/** A sway of one env-layout prop (by id): roll about the prop's local X (or Y) axis, deg x sin. */
struct UNMATCHED_API FS08ConceptAnim {
  FString Prop;
  float SwayDeg = 0.0f;          // 0..15
  float SwayHz = 0.0f;           // 0..5
  bool bAxisY = false;           // "axis": "x" (default) | "y"
};

/** A contact-shadow blob (M_MapContactShadow, modulate) under a 3D detail on the unlit sheet. */
struct UNMATCHED_API FS08ConceptShadowBlob {
  FString Id;
  FVector Loc = FVector::ZeroVector;  // centre on the surface (the blob lifts by BlobLiftUU)
  float DiameterUU = 60.0f;           // 10..300
  float Strength = 0.35f;             // 0..1
  float Softness = 0.55f;             // 0.1..1
};

/** One painted-water flow region of the sheet ("flow.regions", concept px): the plates are sampled with a slow,
 *  time-panned value-noise offset of AmpPx (the waterfall, the bay surf). With a "waterMask" the region weight is also
 *  multiplied by the painted-water mask: regions[0] by its R (waterfall), regions[1] by its G (bay surf). */
struct UNMATCHED_API FS08ConceptFlow {
  FString Id;
  FVector4 RectPx = FVector4(0.0, 0.0, 0.0, 0.0);  // x0, y0, w, h
  FVector2D VelocityPx = FVector2D::ZeroVector;    // pan of the noise, px / s (|..| <= 200)
  float AmpPx = 0.0f;                              // 0..6
};

/** "flow.sea": the same on the sea plane of the sea layer (the whole plate below the sea level + 1; never the sky). */
struct UNMATCHED_API FS08ConceptSeaFlow {
  bool bSet = false;
  FVector2D VelocityPx = FVector2D::ZeroVector;
  float AmpPx = 0.0f;
};

/** "sea": the sea plane + sky cylinder layer under / behind the sheet. */
struct UNMATCHED_API FS08ConceptSeaSpec {
  bool bSet = false;
  float ZUU = -300.0f;
  FVector2D CentreUU = FVector2D(0.0, -45.0);
  float RadiusUU = 1900.0f;
  float SkyTopZUU = 900.0f;
  int32 SkySegments = 48;
};

struct UNMATCHED_API FS08ConceptPasteSpec {
  bool bSet = false;
  bool bDefaultOn = false;                                         // "default": "on" | "off"
  FString Variant = S08ConceptPasteSpec::DefaultConceptVariant;    // the concept env-layout overlay
  FString OffVariant;                                              // optional: variant = off + the base layout
  FString SpecPath;                                                // informational (tools/art/concept_paste/<map>.paste.json)
  FString ManifestPath;                                            // informational (sha256 of the out-of-git sources)
  FString MaterialPath = S08ConceptPasteSpec::DefaultMaterialPath;
  FString SheetMeshPath;                                           // required
  FString PlateAPath;                                              // optional (centre detail plate)
  FString PlateBPath;                                              // required (outskirts plate, alpha = matte x cut)
  FString SeaPlatePath;                                            // optional (the sea layer; else plate B)
  FString MaskPath;                                                // optional (B space)
  FString LutPath;                                                 // optional (grade "lut")
  FString WaterMaskPath;                                           // optional (B space: R waterfall, G surf, B sea)
  FS08ConceptCamera Camera;
  FS08ConceptHomography Homography;
  FVector4 RectA = FVector4(0.0, 0.0, 1920.0, 1080.0);
  FVector4 RectB = FVector4(0.0, 0.0, 1920.0, 1080.0);
  float FeatherPx = 24.0f;
  bool bClampOutside = false;                                      // "outside": "clip" (default) | "clamp" (the sheet)
  float CutUnderFrameUU = 2.0f;
  float CutMinZ = -60.0f;
  ES08ConceptGrade Grade = ES08ConceptGrade::Lut;
  float GainLinear = 1.0f;
  bool bHasEmissiveScale = false;
  float EmissiveScale = 1.0f;
  /** "grade.devignette" 0..1: the engine vignette intensity (FPostProcessSettings::VignetteIntensity, default 0.4) the
   *  material undoes on the painted layer (P7 tune: measured at C0, the corners displayed 19-31 % under the plate). */
  float Devignette = 0.0f;
  /** "grade.fitScale" / "grade.fitPower" (aces-inverse): the measured per-channel fit of the engine's tone curve on an
   *  unlit emissive, display = sRGB(ACES(k x E)^p): fitScale = 1 / k, fitPower = p (P7 tune: concept-pose selfcal). */
  FVector FitScale = FVector::OneVector;
  FVector FitPower = FVector::OneVector;
  FS08ConceptSeaSpec Sea;
  FS08ConceptHide Hide;
  TArray<FS08ConceptLight> Lights;
  TArray<FS08ConceptAnim> Anims;
  TArray<FS08ConceptShadowBlob> ShadowBlobs;
  TArray<FS08ConceptFlow> Flows;  // <= MaxFlows
  FS08ConceptSeaFlow SeaFlow;
  /** Half extent of the cut: the frame's outer foot minus CutUnderFrameUU (467.67 x 310.67 on the shipped maps). */
  FVector2D CutHalf(const FVector2D& FrameHalf) const;
  /** Asset packages in a stable order (material, sheet, plates, sea, mask, LUT, water; empty optional ones skipped). */
  TArray<FString> AssetPaths() const;
};

/** What the command line asks for (ResolveMode input; FromCommandLine or a test override). */
struct UNMATCHED_API FS08ConceptPasteInputs {
  bool bFlagOn = false;
  bool bFlagOff = false;
  bool bCalib = false;
  FString Variant;  // -EnvLayoutVariant=
  FString FlagText; // the flag as given (trace), empty = none
  static FS08ConceptPasteInputs FromCommandLine();
};

/** The decision for one board. bOverrideVariant: the env layout gets Variant ("" = the base, no overlay) instead of
 *  the command line's -EnvLayoutVariant. */
struct UNMATCHED_API FS08ConceptPasteMode {
  bool bOn = false;
  FString Reason = TEXT("no-block");  // no-block | gate | flag-on | flag-off | variant | variant-off | variant-other |
                                      // default | missing-assets | overlay-absent | overlay-invalid
  bool bOverrideVariant = false;
  FString Variant;
};

/** Parameter values of one M_ConceptPaste MID (the C++ mirror of the shader is ShaderSample). */
struct UNMATCHED_API FS08ConceptMaterialParams {
  FLinearColor CamPos, CamRight, CamUp, CamForward, CamTan;
  FLinearColor HRow0, HRow1, HRow2;
  FLinearColor RectA, RectB, Cut;
  float UseA = 1.0f;
  float FeatherPx = 24.0f;
  float AlphaWeight = 1.0f;
  float OutsideKeep = 0.0f;
  float GradeMode = 1.0f;
  float GainLinear = 1.0f;
  float EmissiveScale = 1.0f;
  float Calib = 0.0f;
  float CalibMax = S08ConceptPasteSpec::DefaultCalibMax;
  FLinearColor FlowRect0 = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);
  FLinearColor FlowRect1 = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);
  FLinearColor FlowVel0 = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);
  FLinearColor FlowVel1 = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);
  float FlowMaxZ = 1.0e6f;
  float UseWater = 0.0f;  // set by Apply when the water mask is loaded
  float FlowSea = 0.0f;   // 1 on the sea layer (region 0 = the open-sea mask B)
  float Devignette = 0.0f;
  FLinearColor GradeScale = FLinearColor(1.0f, 1.0f, 1.0f, 0.0f);
  FLinearColor GradePow = FLinearColor(1.0f, 1.0f, 1.0f, 0.0f);
};

/** What the shader computes for one world point (ShaderSample, tests). */
struct UNMATCHED_API FS08ConceptShaderSample {
  bool bInFront = false;
  FVector2D C0Px = FVector2D::ZeroVector;
  FVector2D ConceptPx = FVector2D::ZeroVector;
  FVector2D UvA = FVector2D::ZeroVector;
  FVector2D UvB = FVector2D::ZeroVector;
  float WeightA = 0.0f;   // plate A over plate B
  bool bInsideB = false;
  bool bCut = false;      // under the 3D frame / map: never drawn
  float FlowWeight0 = 0.0f;  // flow region weights (feathered box x the Z gate; the noise itself is not mirrored)
  float FlowWeight1 = 0.0f;
};

/** The loaded assets of a block (nullptr = missing / not asked). */
struct UNMATCHED_API FS08ConceptPasteAssets {
  UMaterialInterface* Material = nullptr;
  UStaticMesh* Sheet = nullptr;
  UStaticMesh* Plane = nullptr;
  UTexture* PlateA = nullptr;
  UTexture* PlateB = nullptr;
  UTexture* Sea = nullptr;
  UTexture* Mask = nullptr;
  UTexture* Lut = nullptr;
  UTexture* Water = nullptr;
  UMaterialInterface* ShadowMaterial = nullptr;
  TArray<FString> Missing;    // every missing package (required or optional)
  bool RequiredOk() const { return Material && Sheet && PlateB && Plane; }
};

/** What the last Apply did (AS08BoardActor::GetConceptPasteRuntime; the components live in its UPROPERTY arrays). */
struct UNMATCHED_API FS08ConceptPasteRuntime {
  FString ProfileId;
  FString Key;                 // profile | mode | variant status: the same key = keep the parts
  FS08ConceptPasteMode Mode;
  /** off | ok | missing (status of the parts; 'off' also when the mode is off) */
  FString Status = TEXT("off");
  bool bTraced = false;        // a concept-paste line was ever written (a grid-only run writes none)
  int32 SheetParts = 0;
  int32 SeaParts = 0;          // sea plane + sky segments
  int32 Lights = 0;
  int32 Blobs = 0;
  int32 Anims = 0;
  FString Grade = TEXT("-");   // effective grade
  float EmissiveScale = 1.0f;
  FString EmissiveScaleSource = TEXT("-");
  bool bCalib = false;
  bool bAnimFrozen = false;
  int32 HiddenProps = 0, HiddenFx = 0, HiddenLights = 0, HiddenGround = 0, HiddenSea = 0, HiddenWaterfalls = 0;
  bool bHidTray = false, bHidFog = false, bHidBackdrop = false;
  /** Env / scene components this mode hid (made visible again by RestoreHides). */
  TArray<TWeakObjectPtr<USceneComponent>> Hidden;
};

namespace S08ConceptPaste {
/** Parses the "conceptPaste" object of board BoardId; appends 'board <id>: conceptPaste.<field> ...' errors. */
UNMATCHED_API bool ParseJson(const FString& BoardId, const TSharedPtr<FJsonObject>& Object, FS08ConceptPasteSpec& Out,
                             TArray<FString>& OutErrors);
/** The decision table of the file comment. bGate = env gate AND map-image AND the block (false -> off 'gate'). */
UNMATCHED_API FS08ConceptPasteMode ResolveMode(const FS08ConceptPasteSpec& Spec, const FS08ConceptPasteInputs& In,
                                               bool bGate);
/** The mode turned off after the decision (missing assets, the overlay did not apply): off with Reason; when the command
 *  line asked for the concept overlay itself, the env layout gets the base instead (the overlay alone leaves holes). */
UNMATCHED_API FS08ConceptPasteMode FallbackOff(const FS08ConceptPasteSpec& Spec, const FS08ConceptPasteInputs& In,
                                               const TCHAR* Reason);
/** Automation only: inputs from this fake command line instead of FCommandLine (Reset -> the real one). */
UNMATCHED_API void SetCommandLineOverrideForTest(const FString& FakeCommandLine);
UNMATCHED_API void ResetCommandLineOverrideForTest();
UNMATCHED_API FS08ConceptPasteInputs InputsFromCommandLine(const TCHAR* CommandLine);

/** Engine plane (100 uu, normal +Z) as the sea plane: 2 R x 2 R around the centre at Z. */
UNMATCHED_API FTransform SeaPlaneTransform(const FS08ConceptSeaSpec& Sea);
/** The sky cylinder as SkySegments engine planes: chords of the circle (vertices on the radius), Z .. SkyTopZ, the
 *  plane normal towards the axis (local X along the chord, local Y up). */
UNMATCHED_API TArray<FTransform> SkySegmentTransforms(const FS08ConceptSeaSpec& Sea);
/** MID values of the sheet (bSea false) or the sea layer (bSea true). bFreezeFlow: amplitude 0 (reproducible -Bench). */
UNMATCHED_API FS08ConceptMaterialParams MaterialParams(const FS08ConceptPasteSpec& Spec, const FVector2D& FrameHalf,
                                                       bool bSea, bool bHasPlateA, ES08ConceptGrade Grade,
                                                       float EmissiveScale, bool bCalib, bool bFreezeFlow = false);
/** The shader's projection of one world point (exactly the HLSL of ue_concept_material.py). */
UNMATCHED_API FS08ConceptShaderSample ShaderSample(const FS08ConceptMaterialParams& P, const FVector& World);
/** Approximate inverse of the ACES fit (Narkowicz 2015, input x 0.6) used by grade mode 2: display-linear -> scene. */
UNMATCHED_API float InverseAcesApprox(float DisplayLinear);
UNMATCHED_API float AcesApprox(float SceneLinear);
/** Flicker multiplier at TimeS (1 +- FlickerAmp; Seed = CRC of the id). */
UNMATCHED_API float FlickerScale(const FS08ConceptLight& Light, double TimeS);
/** Sway angle (deg) at TimeS. */
UNMATCHED_API float SwayAngleDeg(const FS08ConceptAnim& Anim, double TimeS);
/** Effective grade for the loaded assets ("lut" without a LUT -> inverse ACES) and the emissive scale (the block's,
 *  else the light profile's fixed exposure brightness, else 1). */
UNMATCHED_API ES08ConceptGrade EffectiveGrade(const FS08ConceptPasteSpec& Spec, bool bHasLut);
UNMATCHED_API float EffectiveEmissiveScale(const FS08ConceptPasteSpec& Spec, bool bExposureSet, float ExposureMaxBrightness,
                                           FString& OutSource);
/** 'ARTPREVIEW concept-paste missing <path>' */
UNMATCHED_API FString MissingLine(const FString& Path);

/** Loads the block's assets (uncooked runs ask the package registry first: no loader warning in automation). */
UNMATCHED_API FS08ConceptPasteAssets LoadAssets(const FS08ConceptPasteSpec& Spec);

/** Spawns the sheet, the sea layer, the lights and the blobs under Root (owned by Owner), clears the previous ones;
 *  writes the trace. Status ok / missing (Assets.RequiredOk false: nothing spawned). */
UNMATCHED_API void Apply(const FS08ConceptPasteSpec& Spec, const FS08ConceptPasteAssets& Assets, const FVector2D& FrameHalf,
                         ES08ConceptGrade Grade, float EmissiveScale, bool bCalib, bool bFreezeFlow, AActor& Owner,
                         USceneComponent* Root,
                         TArray<TObjectPtr<UStaticMeshComponent>>& Parts,
                         TArray<TObjectPtr<UPointLightComponent>>& Lights, FS08ConceptPasteRuntime& Runtime);
/** Destroys the parts and lights (Runtime counts back to 0; Hidden untouched). */
UNMATCHED_API void Clear(TArray<TObjectPtr<UStaticMeshComponent>>& Parts, TArray<TObjectPtr<UPointLightComponent>>& Lights,
                         FS08ConceptPasteRuntime& Runtime);
/** Hides the env components of the hide list (props / fx by the overlay ids, layout lights, ground / sea / waterfalls by
 *  component name) and the fog component; records them in Runtime.Hidden (idempotent). */
UNMATCHED_API void ApplyHides(const FS08ConceptHide& Hide, const FS08EnvLayoutRuntime& Env,
                              const TArray<TObjectPtr<UStaticMeshComponent>>& EnvProps,
                              const TArray<TObjectPtr<UPointLightComponent>>& EnvLights,
                              UExponentialHeightFogComponent* Fog, FS08ConceptPasteRuntime& Runtime);
/** Shows again whatever ApplyHides hid (the mode went off for the same components). */
UNMATCHED_API int32 RestoreHides(FS08ConceptPasteRuntime& Runtime);
/** Ground component kind by its S08EnvGround name: ground | sea | waterfalls | "" (not a ground part). */
UNMATCHED_API FString GroundKindOf(const FString& ComponentName);
}  // namespace S08ConceptPaste

/** Drives the flicker of the concept lights and the sway of named props (world time). Created by the board actor only
 *  when the block has an animation and the run is not frozen (-Bench without -EnvFxLive, or -EnvFxFreeze): frozen runs
 *  keep the base intensity / rotation, so evidence frames stay reproducible. */
UCLASS()
class UNMATCHED_API US08ConceptPasteAnimComponent : public UActorComponent {
  GENERATED_BODY()

public:
  US08ConceptPasteAnimComponent();
  void AddFlicker(UPointLightComponent* Light, const FS08ConceptLight& Spec);
  void AddSway(USceneComponent* Prop, const FS08ConceptAnim& Spec);
  int32 Num() const { return Flickers.Num() + Sways.Num(); }
  /** Back to the base intensity / rotation (before the component goes away). */
  void RestoreBase();
  virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
  struct FFlicker {
    TWeakObjectPtr<UPointLightComponent> Light;
    FS08ConceptLight Spec;
    float BaseIntensity = 0.0f;
  };
  struct FSway {
    TWeakObjectPtr<USceneComponent> Prop;
    FS08ConceptAnim Spec;
    FRotator BaseRotation = FRotator::ZeroRotator;
  };
  TArray<FFlicker> Flickers;
  TArray<FSway> Sways;
};

// SEL 3D hero showcases - see UmHeroShowcase.h.
#include "UmHeroShowcase.h"

#include "../S08TraceLog.h"
#include "Animation/AnimSequenceBase.h"
#include "Components/PointLightComponent.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace {
int32 GShowcaseOverride = -1;  // -1 = the command line

// The side origins (local to the actor): far enough apart that a side's lights never reach the other figure.
const FVector SideOrigin[2] = {FVector(0.0, -2000.0, 0.0), FVector(0.0, 2000.0, 0.0)};
// The look of the stage (tuned live; the figure is ~55 uu tall on its pedestal).
constexpr float CaptureFovDeg = 24.0f;      // horizontal; a long lens flatters the miniature
constexpr float FrameMargin = 1.22f;        // vertical room around pedestal bottom .. bounds top
constexpr float CameraHeightK = 0.42f;      // camera height as a part of the figure height (slightly low: heroic)
constexpr float KeyCandela = 7.0f;
constexpr float RimCandela = 3.0f;
constexpr float FillCandela = 1.6f;
constexpr float LightReachUU = 600.0f;
constexpr float ExposureBias = 0.0f;     // manual exposure of the captures (EV)
constexpr int32 StageChannel = 2;           // lighting channel 2: no board light reaches the figures
constexpr float HiPolyYawSide0Deg = 45.0f;    // the imported Tripo source (glTF axes after Interchange), left niche
constexpr float HiPolyYawSide1Deg = 135.0f;  // right niche
// King Arthur's regenerated source holds the sword upright before his right shoulder: at the shared three-quarter turn
// the blade crosses his face (blind round 3) - his own yaw per side (tuned live: um.Showcase.ArthurYaw0 / 1, -1 = table)
constexpr float ArthurYawSide0Deg = 85.0f;   // live frames 2026-10-16: 25-65 the blade crosses the face, 85 clear
constexpr float ArthurYawSide1Deg = 95.0f;   // the mirror of side 0 (45/135 -> 85/95)
TAutoConsoleVariable<float> CVarArthurYaw0(TEXT("um.Showcase.ArthurYaw0"), -1.0f, TEXT("SEL: Arthur high-poly yaw, left niche (-1 = code)"));
TAutoConsoleVariable<float> CVarArthurYaw1(TEXT("um.Showcase.ArthurYaw1"), -1.0f, TEXT("SEL: Arthur high-poly yaw, right niche (-1 = code)"));
}  // namespace

namespace UmShowcase {
bool Enabled() {
  if (GShowcaseOverride >= 0) return GShowcaseOverride == 1;
  return !FParse::Param(FCommandLine::Get(), LegacyFlagName);
}
void SetEnabledOverrideForTest(bool bEnabled) { GShowcaseOverride = bEnabled ? 1 : 0; }
void ResetEnabledOverrideForTest() { GShowcaseOverride = -1; }
FString FighterForSlug(FName Slug, const FString& Fallback) {
  const FString Want = Slug.ToString().ToLower();
  if (!Want.IsEmpty()) {
    for (const S08HeroesV2::FHeroSpec& Spec : S08HeroesV2::Specs()) {
      if (FString(Spec.FighterName).ToLower().Replace(TEXT(" "), TEXT("-")) == Want) return Spec.FighterName;
    }
  }
  return Fallback;
}
float PushFov(float BaseFov, double Seconds) {
  // in 0.25 s to 20/24 of the FOV, back in 0.40 s (02-DESIGN.md §3 «Фиксация»)
  constexpr double In = 0.25, Out = 0.40;
  const float Near = BaseFov * (20.0f / 24.0f);
  if (Seconds < 0.0 || Seconds >= In + Out) return BaseFov;
  if (Seconds < In) return FMath::InterpEaseOut(BaseFov, Near, static_cast<float>(Seconds / In), 2.0f);
  return FMath::InterpEaseInOut(Near, BaseFov, static_cast<float>((Seconds - In) / Out), 2.0f);
}
bool HiPolyRequested() { return !FParse::Param(FCommandLine::Get(), V2FlagName); }
FString HiPolyPath(const TCHAR* Key) {
  // the H2 Tripo sources of the in-game H2LD figures, repaired and baked with the game look (06-HIPOLY-LOOKDEV.md,
  // tools/art/showcase/hp_lookdev_bake.py + import_hipoly_lookdev.py)
  // King Arthur: the regenerated H2 4f059621 (side in the LEFT slot, no phantoms; 2026-10-16) with its own Tripo 8K
  // materials - no game low-poly shares its frame, so the game maps are not baked onto it (06-HIPOLY-LOOKDEV.md)
  const FString K(Key);
  if (K == TEXT("KingArthur")) {
    return TEXT("/Game/PipelineCandidates/KingArthur/HP2/king-arthur-h2-tripo-4f059621-tex8k-pbr-clean.king-arthur-h2-tripo-4f059621-tex8k-pbr-clean");
  }
  // Bruce Lee (wave A 2026-10-21, stage 7b): the cleaned H2 Tripo 14235c8d source with its own Tripo 8K materials (HP2)
  if (K == TEXT("BruceLee")) {
    return TEXT("/Game/PipelineCandidates/BruceLee/HP2/bruce-lee-h2-tripo-14235c8d-tex8k-pbr-clean.bruce-lee-h2-tripo-14235c8d-tex8k-pbr-clean");
  }
  if (K != TEXT("Medusa")) return FString();
  return FString::Printf(TEXT("/Game/PipelineCandidates/%s/HPLD/SM_%s_HP_Showcase.SM_%s_HP_Showcase"), Key, Key, Key);
}
FString HiPolyMaterialPath(const TCHAR* Key, const FString& Part, ES08TeamSlot Look) {
  return FString::Printf(TEXT("/Game/PipelineCandidates/%s/HPLD/Materials/MI_%s_HP_%s_%s.MI_%s_HP_%s_%s"), Key, Key, *Part,
                         S08TeamSlotName(Look), Key, *Part, S08TeamSlotName(Look));
}
float FigureYawDeg(int32 Side) {
  // The camera looks along +X (its right is +Y). Rig v2 faces +X at yaw 0: 180 faces the camera; side 0 turns towards
  // the image right (+Y, yaw 90) -> 135, side 1 towards the image left (-Y, yaw 270) -> 225 (checked on the live
  // frames of 2026-10-16: 135 looks right, 225 looks left).
  return Side == 0 ? 135.0f : 225.0f;
}
}  // namespace UmShowcase

AUmHeroShowcase::AUmHeroShowcase() {
  PrimaryActorTick.bCanEverTick = true;
  PrimaryActorTick.bStartWithTickEnabled = true;
  Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
  SetRootComponent(Root);
  for (int32 S = 0; S < 2; ++S) {
    const FString Sfx = FString::Printf(TEXT("%d"), S);
    Base[S] = CreateDefaultSubobject<UStaticMeshComponent>(*(TEXT("Base") + Sfx));
    Base[S]->SetupAttachment(Root);
    Backdrop[S] = CreateDefaultSubobject<UStaticMeshComponent>(*(TEXT("Backdrop") + Sfx));
    Backdrop[S]->SetupAttachment(Root);
    Backdrop[S]->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Backdrop[S]->SetCastShadow(false);
    Backdrop[S]->LightingChannels.bChannel0 = false;
    Backdrop[S]->LightingChannels.bChannel2 = true;
    HiPoly[S] = CreateDefaultSubobject<UStaticMeshComponent>(*(TEXT("HiPoly") + Sfx));
    HiPoly[S]->SetupAttachment(Root);
    HiPoly[S]->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    HiPoly[S]->LightingChannels.bChannel0 = false;
    HiPoly[S]->LightingChannels.bChannel2 = true;
    HiPoly[S]->bForceMipStreaming = true;
    HiPoly[S]->SetVisibility(false);
    Body[S] = CreateDefaultSubobject<USkeletalMeshComponent>(*(TEXT("Body") + Sfx));
    Body[S]->SetupAttachment(Root);
    // never rendered by the main view: the pose must tick anyway (the capture sees it)
    Body[S]->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    // the close-up shows every texel: the top LOD and all mips resident (streaming only sees the main view)
    Body[S]->SetForcedLOD(1);
    Body[S]->bForceMipStreaming = true;
    Base[S]->bForceMipStreaming = true;
    for (UPrimitiveComponent* P : {static_cast<UPrimitiveComponent*>(Base[S]), static_cast<UPrimitiveComponent*>(Body[S])}) {
      P->SetCollisionEnabled(ECollisionEnabled::NoCollision);
      P->SetCastShadow(true);
      P->LightingChannels.bChannel0 = false;
      P->LightingChannels.bChannel2 = true;
    }
    auto MakeLight = [this, &Sfx](const TCHAR* Name, float Cd, const FLinearColor& Color) {
      UPointLightComponent* L = CreateDefaultSubobject<UPointLightComponent>(*(FString(Name) + Sfx));
      L->SetupAttachment(Root);
      L->SetIntensityUnits(ELightUnits::Candelas);
      L->SetIntensity(Cd);
      L->SetLightColor(Color);
      L->SetAttenuationRadius(LightReachUU);
      L->LightingChannels.bChannel0 = false;
      L->LightingChannels.bChannel2 = true;
      L->SetCastShadows(true);
      return L;
    };
    Key[S] = MakeLight(TEXT("Key"), KeyCandela, FLinearColor(1.0f, 0.92f, 0.80f));
    Key[S]->SetSourceRadius(6.0f);  // soft key shadows on the miniature (~55 uu)
    RimLight[S] = MakeLight(TEXT("Rim"), RimCandela, S08TeamPalette::RingFill(S == 0 ? ES08TeamSlot::P1 : ES08TeamSlot::P2));
    Fill[S] = MakeLight(TEXT("Fill"), FillCandela, FLinearColor(0.70f, 0.78f, 1.0f));
    Fill[S]->SetCastShadows(false);
    Capture[S] = CreateDefaultSubobject<USceneCaptureComponent2D>(*(TEXT("Capture") + Sfx));
    Capture[S]->SetupAttachment(Root);
    USceneCaptureComponent2D* C = Capture[S];
    C->FOVAngle = CaptureFovDeg;
    C->CaptureSource = ESceneCaptureSource::SCS_FinalColorLDR;
    C->PrimitiveRenderMode = ESceneCapturePrimitiveRenderMode::PRM_UseShowOnlyList;
    C->bCaptureEveryFrame = false;
    C->bCaptureOnMovement = false;
    C->bAlwaysPersistRenderingState = true;
    C->ShowOnlyComponents.Add(Backdrop[S]);
    C->ShowOnlyComponents.Add(Base[S]);
    C->ShowOnlyComponents.Add(HiPoly[S]);
    C->ShowOnlyComponents.Add(Body[S]);
    C->ShowFlags.SetAtmosphere(false);
    C->ShowFlags.SetFog(false);
    C->ShowFlags.SetVolumetricFog(false);
    C->ShowFlags.SetSkyLighting(false);
    C->ShowFlags.SetMotionBlur(false);
    C->ShowFlags.SetDirectionalLights(false);
    C->ShowFlags.SetTemporalAA(true);  // with bAlwaysPersistRenderingState the capture keeps its TAA history
    C->ShowFlags.SetAntiAliasing(true);
    FPostProcessSettings& PP = C->PostProcessSettings;
    PP.bOverride_DynamicGlobalIlluminationMethod = true;
    PP.DynamicGlobalIlluminationMethod = EDynamicGlobalIlluminationMethod::None;
    PP.bOverride_ReflectionMethod = true;
    PP.ReflectionMethod = EReflectionMethod::None;
    PP.bOverride_AutoExposureMethod = true;
    PP.AutoExposureMethod = EAutoExposureMethod::AEM_Manual;
    PP.bOverride_AutoExposureBias = true;
    PP.AutoExposureBias = ExposureBias;
    PP.bOverride_AutoExposureApplyPhysicalCameraExposure = true;
    PP.AutoExposureApplyPhysicalCameraExposure = false;
    PP.bOverride_VignetteIntensity = true;
    PP.VignetteIntensity = 0.0f;
    PP.bOverride_BloomIntensity = true;
    PP.BloomIntensity = 0.2f;
  }
  Clips0.SetNum(S08HeroesV2::ClipCount);
  Clips1.SetNum(S08HeroesV2::ClipCount);
}

AUmHeroShowcase* AUmHeroShowcase::Get(UWorld* World) {
  if (!World || !UmShowcase::Enabled()) return nullptr;
  for (TActorIterator<AUmHeroShowcase> It(World); It; ++It) return *It;
  FActorSpawnParameters P;
  P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
  P.ObjectFlags |= RF_Transient;
  AUmHeroShowcase* A = World->SpawnActor<AUmHeroShowcase>(AUmHeroShowcase::StaticClass(),
                                                         FTransform(FVector(UmShowcase::ShowcaseOffsetUU, 0.0, 0.0)), P);
  if (A) {
    A->EnsureTargets();
    for (int32 S = 0; S < 2; ++S) A->TraceSide(S);
  }
  return A;
}

void AUmHeroShowcase::EnsureTargets() {
  UStaticMesh* PlaneMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Plane.Plane"));
  UMaterialInterface* PlaneMat = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
  for (int32 S = 0; S < 2; ++S) {
    if (PlaneMesh && !Backdrop[S]->GetStaticMesh()) {
      Backdrop[S]->SetStaticMesh(PlaneMesh);
      if (PlaneMat) {
        UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(PlaneMat, this);
        Mid->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.035f, 0.04f, 0.055f));
        Backdrop[S]->SetMaterial(0, Mid);
      }
    }
    if (Target[S]) continue;
    UTextureRenderTarget2D* RT = NewObject<UTextureRenderTarget2D>(this, *FString::Printf(TEXT("RT_Showcase%d"), S));
    RT->ClearColor = FLinearColor::Black;
    RT->bAutoGenerateMips = true;
    RT->MipsSamplerFilter = TF_Trilinear;
    // FinalColorLDR is already display-encoded: a linear (non-sRGB) target keeps it as is - an sRGB target encoded it
    // twice (the live frame of 2026-10-16: a pale, washed-out Medusa)
    RT->InitCustomFormat(UmShowcase::TargetW, UmShowcase::TargetH, PF_B8G8R8A8, /*bForceLinearGamma*/ true);
    RT->UpdateResourceImmediate(true);
    Target[S] = RT;
    Capture[S]->TextureTarget = RT;
  }
}

void AUmHeroShowcase::SetActive(bool bInActive) {
  if (bActive == bInActive) return;
  bActive = bInActive;
  EnsureTargets();
  for (int32 S = 0; S < 2; ++S) {
    Capture[S]->bCaptureEveryFrame = bActive;
    TraceSide(S);
  }
}

void AUmHeroShowcase::RequestActive() {
  LastRequestFrame = GFrameCounter;
  if (!bActive) SetActive(true);
}

void AUmHeroShowcase::SetHero(int32 Side, const FString& FighterName, ES08TeamSlot Look) {
  if (Side < 0 || Side > 1) return;
  using namespace S08HeroesV2;
  const FHeroSpec* NewSpec = FighterName.IsEmpty() ? nullptr : Find(true, FlagEnabled(), FighterName);
  if (NewSpec == Spec[Side] && Look == SideLook[Side]) return;
  EnsureTargets();
  Spec[Side] = nullptr;
  SideLook[Side] = Look;
  Body[Side]->SetSkeletalMeshAsset(nullptr);
  Base[Side]->SetStaticMesh(nullptr);
  Clip[Side] = EClip::None;
  if (NewSpec) {
    USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr, *MeshPath(*NewSpec));
    UStaticMesh* Pedestal = LoadObject<UStaticMesh>(nullptr, *PedestalPath(*NewSpec));
    UMaterialInterface* BodyMi = LoadObject<UMaterialInterface>(nullptr, *BodyMaterialPath(*NewSpec, Look));
    UMaterialInterface* BaseMi = LoadObject<UMaterialInterface>(nullptr, *PedestalMaterialPath(*NewSpec, Look));
    TArray<TObjectPtr<UAnimSequenceBase>>& Clips = ClipsOf(Side);
    for (TObjectPtr<UAnimSequenceBase>& C : Clips) C = nullptr;
    if (Mesh && Mesh->GetSkeleton()) {
      for (const EClip C : {EClip::Idle, EClip::LungeAttack}) {
        UAnimSequenceBase* A = LoadObject<UAnimSequenceBase>(nullptr, *ClipPath(*NewSpec, C));
        Clips[static_cast<int32>(C)] = A && A->GetSkeleton() == Mesh->GetSkeleton() ? A : nullptr;
      }
      Spec[Side] = NewSpec;
      Body[Side]->SetSkeletalMeshAsset(Mesh);
      if (BodyMi) {
        for (int32 I = 0; I < Body[Side]->GetNumMaterials(); ++I) Body[Side]->SetMaterial(I, BodyMi);
      }
      Base[Side]->SetStaticMesh(Pedestal);
      if (BaseMi) {
        for (int32 I = 0; I < Base[Side]->GetNumMaterials(); ++I) Base[Side]->SetMaterial(I, BaseMi);
      }
      PlayClip(Side, EClip::Idle);
    } else {
      FS08Trace::Write(FString::Printf(TEXT("SHOWCASE side=%d hero=%s missing=%s"), Side, *FighterName, *MeshPath(*NewSpec)));
    }
  }
  // default: the static high-poly source in place of the skeletal figure (rollback -S08ShowcaseV2; no source = v2)
  UStaticMesh* Hi = nullptr;
  if (Spec[Side] && UmShowcase::HiPolyRequested()) {
    const FString HiPath = UmShowcase::HiPolyPath(Spec[Side]->Key);
    Hi = HiPath.IsEmpty() ? nullptr : LoadObject<UStaticMesh>(nullptr, *HiPath, nullptr, LOAD_NoWarn | LOAD_Quiet);
    FS08Trace::Write(FString::Printf(TEXT("SHOWCASE side=%d hipoly=%s path=%s"), Side, Hi ? TEXT("1") : TEXT("missing"), *HiPath));
  }
  HiPoly[Side]->SetStaticMesh(Hi);
  HiPoly[Side]->EmptyOverrideMaterials();  // overrides survive SetStaticMesh: a previous hero's instances would stay
  if (Hi && Hi->GetPathName().Contains(TEXT("/HPLD/"))) {
    // the game material per Tripo part, in the side's team look (slot names MAT_tripo_part_N) - only for the HPLD bake;
    // a source with its own Tripo materials (Arthur HP2) keeps them (the old HPLD instances belong to another mesh)
    int32 Set = 0;
    for (int32 I = 0; I < Hi->GetStaticMaterials().Num(); ++I) {
      const FString Slot = Hi->GetStaticMaterials()[I].MaterialSlotName.ToString();
      int32 At = Slot.Find(TEXT("tripo_part_"));
      if (At == INDEX_NONE) continue;
      FString Part = Slot.Mid(At);
      int32 End = 11;
      while (End < Part.Len() && FChar::IsDigit(Part[End])) ++End;
      Part = Part.Left(End);
      if (UMaterialInterface* Mi = LoadObject<UMaterialInterface>(nullptr, *UmShowcase::HiPolyMaterialPath(Spec[Side]->Key, Part, Look),
                                                                  nullptr, LOAD_NoWarn | LOAD_Quiet)) {
        HiPoly[Side]->SetMaterial(I, Mi);
        ++Set;
      }
    }
    FS08Trace::Write(FString::Printf(TEXT("SHOWCASE side=%d hipolyMaterials=%d/%d look=%s"), Side, Set,
                                     Hi->GetStaticMaterials().Num(), S08TeamSlotName(Look)));
  }
  HiPoly[Side]->SetVisibility(Hi != nullptr);
  Body[Side]->SetVisibility(Hi == nullptr);
  // the game pedestal with the team ring stays (blind round 1: the Tripo base had no team colour; it is cut off by
  // tools/art/showcase/clean_hipoly.py)
  Base[Side]->SetVisibility(true);
  RimLight[Side]->SetLightColor(S08TeamPalette::RingFill(Look));
  Frame(Side);
  TraceSide(Side);
}

void AUmHeroShowcase::Frame(int32 Side) {
  const FVector O = SideOrigin[Side];
  const float Scale = Spec[Side] ? S08HeroesV2::FigureScale(*Spec[Side]) : 1.0f;
  const float TopUU = (Spec[Side] ? Spec[Side]->BoundsTopUU : 55.0f) * Scale;
  const FRotator Yaw(0.0f, UmShowcase::FigureYawDeg(Side), 0.0f);
  for (USceneComponent* C : {static_cast<USceneComponent*>(Body[Side]), static_cast<USceneComponent*>(Base[Side])}) {
    C->SetRelativeLocation(O);
    C->SetRelativeRotation(Yaw);
    C->SetRelativeScale3D(FVector(Scale));
  }
  // the high-poly source: the same top height as the v2 figure (its bounds top incl. the weapon), the same facing
  // plus the glTF axis offset of the import (tuned on the live frame)
  if (UStaticMesh* Hi = HiPoly[Side]->GetStaticMesh()) {
    // seat the feet on the pedestal top; the figure keeps the v2 height from the pedestal top to the weapon tip
    const FBox HiBox = Hi->GetBoundingBox();
    const float PedTop = Base[Side]->GetStaticMesh() ? static_cast<float>(Base[Side]->GetStaticMesh()->GetBoundingBox().Max.Z) * Scale : 0.0f;
    const float HiH = FMath::Max(1.0f, static_cast<float>(HiBox.Max.Z - HiBox.Min.Z));
    const float S = FMath::Max(0.05f, (TopUU - PedTop) / HiH);
    HiPoly[Side]->SetRelativeLocation(O + FVector(0.0, 0.0, PedTop - HiBox.Min.Z * S));
    // measured on the live frames 2026-10-16: the imported source faces the camera at yaw 90 (180 = left profile,
    // 315 = back), so three quarters to the image right is 45 (side 0) and to the image left 135 (side 1)
    float HiYaw = Side == 0 ? HiPolyYawSide0Deg : HiPolyYawSide1Deg;
    if (Spec[Side] && FCString::Strcmp(Spec[Side]->Key, TEXT("KingArthur")) == 0) {
      const float Live = (Side == 0 ? CVarArthurYaw0 : CVarArthurYaw1).GetValueOnGameThread();
      HiYaw = Live >= 0.0f ? Live : (Side == 0 ? ArthurYawSide0Deg : ArthurYawSide1Deg);
    }
    HiPoly[Side]->SetRelativeRotation(FRotator(0.0f, HiYaw, 0.0f));
    HiPoly[Side]->SetRelativeScale3D(FVector(S));
  }
  // the wall: a plane (100 uu) stood up behind the figure, square to the camera axis, big enough to fill the frame
  Backdrop[Side]->SetRelativeLocation(O + FVector(TopUU * 2.2, 0.0, TopUU * 0.5));
  Backdrop[Side]->SetRelativeRotation(FRotator(90.0f, 0.0f, 0.0f));
  Backdrop[Side]->SetRelativeScale3D(FVector(TopUU * 0.09f, TopUU * 0.09f, 1.0f));
  // vertical FOV of the 2:3 target from the horizontal FOV
  const double HalfH = FMath::DegreesToRadians(CaptureFovDeg * 0.5);
  const double HalfV = FMath::Atan(FMath::Tan(HalfH) * double(UmShowcase::TargetH) / double(UmShowcase::TargetW));
  const double Dist = (TopUU * FrameMargin * 0.5) / FMath::Tan(HalfV);
  const double CamZ = TopUU * CameraHeightK;
  const double AimZ = TopUU * 0.5;
  const FVector Cam = O + FVector(-Dist, 0.0, CamZ);
  const FVector Aim = O + FVector(0.0, 0.0, AimZ);
  Capture[Side]->PostProcessSettings.AutoExposureBias = ExposureBias;  // here too: a Live Coding patch re-tunes it
  Key[Side]->SetIntensity(KeyCandela);
  RimLight[Side]->SetIntensity(RimCandela);
  Fill[Side]->SetIntensity(FillCandela);
  Capture[Side]->SetRelativeLocation(Cam);
  Capture[Side]->SetRelativeRotation((Aim - Cam).Rotation());
  // key: front, high, from the outer side; rim: behind, high, from the inner side; fill: front low
  const double Sgn = Side == 0 ? -1.0 : 1.0;
  Key[Side]->SetRelativeLocation(O + FVector(-TopUU * 1.6, Sgn * TopUU * 1.2, TopUU * 1.7));
  RimLight[Side]->SetRelativeLocation(O + FVector(TopUU * 1.4, -Sgn * TopUU * 1.0, TopUU * 1.5));
  Fill[Side]->SetRelativeLocation(O + FVector(-TopUU * 2.0, -Sgn * TopUU * 0.6, TopUU * 0.3));
}

void AUmHeroShowcase::PlayClip(int32 Side, S08HeroesV2::EClip InClip) {
  using namespace S08HeroesV2;
  UAnimSequenceBase* Anim = ClipsOf(Side)[static_cast<int32>(InClip)].Get();
  if (!Anim) {
    if (InClip != EClip::Idle) PlayClip(Side, EClip::Idle);
    return;
  }
  Body[Side]->SetAnimationMode(EAnimationMode::AnimationSingleNode);
  Body[Side]->PlayAnimation(Anim, ClipLoops(InClip));
  Body[Side]->SetPlayRate(1.0f);
  Clip[Side] = InClip;
  const UWorld* W = GetWorld();
  ClipEndsAt[Side] = (W ? W->GetTimeSeconds() : 0.0) + Anim->GetPlayLength();
}

void AUmHeroShowcase::PlayLockIn(int32 Side) {
  if (Side < 0 || Side > 1 || !Spec[Side]) return;
  PlayClip(Side, S08HeroesV2::EClip::LungeAttack);
  const UWorld* W = GetWorld();
  PushStartedAt[Side] = W ? W->GetTimeSeconds() : 0.0;
  TraceSide(Side);
}

void AUmHeroShowcase::Tick(float DeltaSeconds) {
  Super::Tick(DeltaSeconds);
  const UWorld* W = GetWorld();
  if (!W) return;
  if (bActive && GFrameCounter > LastRequestFrame + 2) SetActive(false);  // no screen asked: the captures sleep
  for (int32 S = 0; S < 2; ++S) {  // live yaw tuning (um.Showcase.ArthurYaw*): re-frame when the value changes
    const float Live = (S == 0 ? CVarArthurYaw0 : CVarArthurYaw1).GetValueOnGameThread();
    if (Live != LastArthurYaw[S]) {
      LastArthurYaw[S] = Live;
      if (HiPoly[S]->GetStaticMesh()) Frame(S);
    }
  }
  for (int32 S = 0; S < 2; ++S) {
    Capture[S]->FOVAngle = UmShowcase::PushFov(CaptureFovDeg, W->GetTimeSeconds() - PushStartedAt[S]);
    if (Clip[S] == S08HeroesV2::EClip::LungeAttack && W->GetTimeSeconds() >= ClipEndsAt[S]) {
      PlayClip(S, S08HeroesV2::EClip::Idle);
      TraceSide(S);
    }
  }
}

UTextureRenderTarget2D* AUmHeroShowcase::GetTarget(int32 Side) const { return Side >= 0 && Side < 2 ? Target[Side].Get() : nullptr; }
FString AUmHeroShowcase::GetHeroKey(int32 Side) const { return Side >= 0 && Side < 2 && Spec[Side] ? FString(Spec[Side]->Key) : FString(); }
bool AUmHeroShowcase::HasFigure(int32 Side) const { return Side >= 0 && Side < 2 && Spec[Side] != nullptr; }
const TCHAR* AUmHeroShowcase::GetClipName(int32 Side) const {
  return Side >= 0 && Side < 2 ? S08HeroesV2::ClipName(Clip[Side]) : TEXT("None");
}

void AUmHeroShowcase::TraceSide(int32 Side) const {
  FS08Trace::Write(FString::Printf(TEXT("SHOWCASE side=%d hero=%s look=%s clip=%s rt=%dx%d active=%d"), Side,
                                   Spec[Side] ? Spec[Side]->Key : TEXT("none"), S08TeamSlotName(SideLook[Side]),
                                   S08HeroesV2::ClipName(Clip[Side]), UmShowcase::TargetW, UmShowcase::TargetH, bActive ? 1 : 0));
}

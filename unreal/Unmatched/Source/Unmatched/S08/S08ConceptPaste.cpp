#include "S08ConceptPaste.h"
#include "S08EnvLayout.h"
#include "S08Render.h"
#include "S08TraceLog.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/Crc.h"
#include "Misc/PackageName.h"
#include "Misc/Parse.h"
#include "NiagaraComponent.h"
#include "StaticMeshResources.h"

namespace S08ConceptPastePrivate {
TOptional<FString> GFakeCommandLine;
bool GForceApplyFailure = false;  // automation only (SetForceApplyFailureForTest)

FString CpPackageOf(const FString& Path) {
  int32 Dot = INDEX_NONE;
  return Path.FindLastChar(TEXT('.'), Dot) ? Path.Left(Dot) : Path;
}

FString CpVec(const FVector& V) { return FString::Printf(TEXT("(%.1f,%.1f,%.1f)"), V.X, V.Y, V.Z); }

bool CpIsId(const FString& S) {
  if (S.IsEmpty() || S.Len() > 64) return false;
  for (const TCHAR C : S) {
    if (!FChar::IsAlnum(C) && C != TEXT('-') && C != TEXT('_')) return false;
  }
  return true;
}

bool CpHexColor(const FString& Hex, FColor& Out) {
  FString H = Hex;
  if (!H.RemoveFromStart(TEXT("#")) || H.Len() != 6) return false;
  for (const TCHAR C : H) {
    if (!FChar::IsHexDigit(C)) return false;
  }
  Out = FColor::FromHex(H);
  Out.A = 255;
  return true;
}

FString CpColorHex(const FColor& C) { return FString::Printf(TEXT("#%02X%02X%02X"), C.R, C.G, C.B); }

/** JSON number (finite) of a value. */
bool CpNumber(const TSharedPtr<FJsonValue>& V, double& Out) {
  return V.IsValid() && V->Type == EJson::Number && V->TryGetNumber(Out) && FMath::IsFinite(Out);
}

/** Exactly Count finite numbers. */
bool CpNumbers(const TSharedPtr<FJsonObject>& O, const TCHAR* Field, int32 Count, TArray<double>& Out) {
  Out.Reset();
  const TArray<TSharedPtr<FJsonValue>>* A = nullptr;
  if (!O->TryGetArrayField(Field, A) || !A || A->Num() != Count) return false;
  for (const TSharedPtr<FJsonValue>& V : *A) {
    double N = 0.0;
    if (!CpNumber(V, N)) return false;
    Out.Add(N);
  }
  return true;
}

/** Optional 3 numbers in [Min, Max] (absent = keep InOut). */
bool CpOptFit(const TSharedPtr<FJsonObject>& O, const TCHAR* Field, double Min, double Max, FVector& InOut) {
  if (!O->HasField(Field)) return true;
  TArray<double> N;
  if (!CpNumbers(O, Field, 3, N)) return false;
  for (const double V : N) {
    if (V < Min || V > Max) return false;
  }
  InOut = FVector(N[0], N[1], N[2]);
  return true;
}

/** Optional number in [Min, Max] (absent = keep InOut). */
bool CpOptNumber(const TSharedPtr<FJsonObject>& O, const TCHAR* Field, double Min, double Max, float& InOut) {
  if (!O->HasField(Field)) return true;
  double V = 0.0;
  if (!CpNumber(O->TryGetField(Field), V) || V < Min || V > Max) return false;
  InOut = static_cast<float>(V);
  return true;
}

bool CpOptNumberD(const TSharedPtr<FJsonObject>& O, const TCHAR* Field, double Min, double Max, double& InOut) {
  if (!O->HasField(Field)) return true;
  double V = 0.0;
  if (!CpNumber(O->TryGetField(Field), V) || V < Min || V > Max) return false;
  InOut = V;
  return true;
}

bool CpVec3(const TSharedPtr<FJsonObject>& O, const TCHAR* Field, double Limit, FVector& Out) {
  TArray<double> N;
  if (!CpNumbers(O, Field, 3, N)) return false;
  for (const double V : N) {
    if (FMath::Abs(V) > Limit) return false;
  }
  Out = FVector(N[0], N[1], N[2]);
  return true;
}

/** Only the listed fields (and any "note*") on an object. */
bool CpKnownFields(const TSharedPtr<FJsonObject>& O, const TArray<const TCHAR*>& Allowed, FString& OutUnknown) {
  for (const TPair<FString, TSharedPtr<FJsonValue>>& F : O->Values) {
    if (F.Key.StartsWith(TEXT("note"))) continue;
    bool bKnown = false;
    for (const TCHAR* A : Allowed) bKnown |= F.Key == A;
    if (!bKnown) {
      OutUnknown = F.Key;
      return false;
    }
  }
  return true;
}

/** A /Game/EnvMaps package path (cooked), never under the never-cooked data root; no spaces / object suffix. */
bool CpAssetPath(const FString& Path) {
  return Path.StartsWith(S08ConceptPasteSpec::AssetRoot) && !Path.StartsWith(S08ConceptPasteSpec::NeverCookRoot) &&
         !Path.Contains(TEXT(" ")) && !Path.Contains(TEXT(".")) && Path.Len() > FCString::Strlen(S08ConceptPasteSpec::AssetRoot);
}

UStaticMeshComponent* CpNewPart(AActor& Owner, USceneComponent* Root, const TCHAR* BaseName, UStaticMesh* Mesh,
                              UMaterialInterface* Material, const FTransform& Relative) {
  UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(
      &Owner, MakeUniqueObjectName(&Owner, UStaticMeshComponent::StaticClass(), FName(BaseName)));
  C->SetupAttachment(Root ? Root : Owner.GetRootComponent());
  C->SetStaticMesh(Mesh);
  C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  C->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
  C->SetGenerateOverlapEvents(false);
  C->SetCanEverAffectNavigation(false);
  // The painted light is in the plates: the layer lights nothing, casts / receives no shadow and stays out of Lumen
  // GI (the bright painted fires / sand would shift the calibrated map luma), distance fields, ray tracing, captures.
  C->SetCastShadow(false);
  C->SetAffectDynamicIndirectLighting(false);
  C->SetAffectIndirectLightingWhileHidden(false);
  C->SetAffectDistanceFieldLighting(false);
  C->SetVisibleInRayTracing(false);
  C->bVisibleInReflectionCaptures = false;
  C->bVisibleInRealTimeSkyCaptures = false;
  C->SetReceivesDecals(false);
  C->SetRelativeTransform(Relative);
  for (int32 I = 0; I < FMath::Max(1, C->GetNumMaterials()); ++I) C->SetMaterial(I, Material);
  C->RegisterComponent();
  return C;
}

void CpSetParams(UMaterialInstanceDynamic& Mid, const FS08ConceptMaterialParams& P) {
  using namespace S08ConceptPasteSpec;
  Mid.SetVectorParameterValue(FName(ParamCamPos), P.CamPos);
  Mid.SetVectorParameterValue(FName(ParamCamRight), P.CamRight);
  Mid.SetVectorParameterValue(FName(ParamCamUp), P.CamUp);
  Mid.SetVectorParameterValue(FName(ParamCamForward), P.CamForward);
  Mid.SetVectorParameterValue(FName(ParamCamTan), P.CamTan);
  Mid.SetVectorParameterValue(FName(ParamHRow0), P.HRow0);
  Mid.SetVectorParameterValue(FName(ParamHRow1), P.HRow1);
  Mid.SetVectorParameterValue(FName(ParamHRow2), P.HRow2);
  Mid.SetVectorParameterValue(FName(ParamRectA), P.RectA);
  Mid.SetVectorParameterValue(FName(ParamRectB), P.RectB);
  Mid.SetVectorParameterValue(FName(ParamCut), P.Cut);
  Mid.SetScalarParameterValue(FName(ParamUseA), P.UseA);
  Mid.SetScalarParameterValue(FName(ParamFeatherPx), P.FeatherPx);
  Mid.SetScalarParameterValue(FName(ParamAlphaWeight), P.AlphaWeight);
  Mid.SetScalarParameterValue(FName(ParamOutsideKeep), P.OutsideKeep);
  Mid.SetScalarParameterValue(FName(ParamGradeMode), P.GradeMode);
  Mid.SetScalarParameterValue(FName(ParamGainLinear), P.GainLinear);
  Mid.SetScalarParameterValue(FName(ParamEmissiveScale), P.EmissiveScale);
  Mid.SetScalarParameterValue(FName(ParamCalib), P.Calib);
  Mid.SetScalarParameterValue(FName(ParamCalibMax), P.CalibMax);
  Mid.SetVectorParameterValue(FName(ParamFlowRect0), P.FlowRect0);
  Mid.SetVectorParameterValue(FName(ParamFlowRect1), P.FlowRect1);
  Mid.SetVectorParameterValue(FName(ParamFlowVel0), P.FlowVel0);
  Mid.SetVectorParameterValue(FName(ParamFlowVel1), P.FlowVel1);
  Mid.SetScalarParameterValue(FName(ParamFlowMaxZ), P.FlowMaxZ);
  Mid.SetScalarParameterValue(FName(ParamUseWater), P.UseWater);
  Mid.SetScalarParameterValue(FName(ParamFlowSea), P.FlowSea);
  Mid.SetScalarParameterValue(FName(ParamDevignette), P.Devignette);
  Mid.SetVectorParameterValue(FName(ParamGradeScale), P.GradeScale);
  Mid.SetVectorParameterValue(FName(ParamGradePow), P.GradePow);
}

uint32 CpSeedOf(const FString& Id) { return FCrc::StrCrc32(*Id); }

double CpPhase(uint32 Seed, int32 Shift) {
  return static_cast<double>((Seed >> Shift) & 0xFFFFu) / 65535.0 * 2.0 * UE_DOUBLE_PI;
}
}  // namespace S08ConceptPastePrivate

// ---- camera / homography -----------------------------------------------------------------------------------------

FVector FS08ConceptCamera::Forward() const { return FRotationMatrix(FRotator(PitchDeg, YawDeg, 0.0)).GetScaledAxis(EAxis::X); }

FVector FS08ConceptCamera::Right() const { return FRotationMatrix(FRotator(PitchDeg, YawDeg, 0.0)).GetScaledAxis(EAxis::Y); }

FVector FS08ConceptCamera::Up() const { return FRotationMatrix(FRotator(PitchDeg, YawDeg, 0.0)).GetScaledAxis(EAxis::Z); }

FVector FS08ConceptCamera::Location() const { return Focus - Forward() * DistanceUU; }

double FS08ConceptCamera::TanHalfH() const { return FMath::Tan(FMath::DegreesToRadians(HFovDeg * 0.5)); }

double FS08ConceptCamera::TanHalfV() const {
  return TanHalfH() * static_cast<double>(SizePx.Y) / static_cast<double>(FMath::Max(1, SizePx.X));
}

bool FS08ConceptCamera::Project(const FVector& World, FVector2D& OutPx, double* OutDepth) const {
  const FVector D = World - Location();
  const double Z = FVector::DotProduct(D, Forward());
  if (OutDepth) *OutDepth = Z;
  if (Z <= 1e-6) return false;
  const double Sx = FVector::DotProduct(D, Right()) / Z / TanHalfH();
  const double Sy = FVector::DotProduct(D, Up()) / Z / TanHalfV();
  OutPx = FVector2D((Sx + 1.0) * 0.5 * SizePx.X, (1.0 - Sy) * 0.5 * SizePx.Y);
  return true;
}

FVector FS08ConceptCamera::Ray(const FVector2D& Px) const {
  const double Sx = (Px.X / SizePx.X * 2.0 - 1.0) * TanHalfH();
  const double Sy = (1.0 - Px.Y / SizePx.Y * 2.0) * TanHalfV();
  return (Forward() + Right() * Sx + Up() * Sy).GetSafeNormal();
}

FVector2D FS08ConceptHomography::Apply(const FVector2D& P) const {
  const double W = M[2][0] * P.X + M[2][1] * P.Y + M[2][2];
  const double Safe = FMath::Abs(W) < 1e-12 ? 1e-12 : W;
  return FVector2D((M[0][0] * P.X + M[0][1] * P.Y + M[0][2]) / Safe, (M[1][0] * P.X + M[1][1] * P.Y + M[1][2]) / Safe);
}

bool FS08ConceptHomography::IsIdentity(double Tolerance) const {
  for (int32 R = 0; R < 3; ++R) {
    for (int32 C = 0; C < 3; ++C) {
      if (FMath::Abs(M[R][C] - (R == C ? 1.0 : 0.0)) > Tolerance) return false;
    }
  }
  return true;
}

const TCHAR* S08ConceptGradeName(ES08ConceptGrade Grade) {
  switch (Grade) {
    case ES08ConceptGrade::Linear: return TEXT("linear");
    case ES08ConceptGrade::Lut: return TEXT("lut");
    case ES08ConceptGrade::AcesInverse: return TEXT("aces-inverse");
  }
  return TEXT("?");
}

FString FS08ConceptHide::Names() const {
  TArray<FString> N;
  if (bTray) N.Add(TEXT("tray"));
  if (bGround) N.Add(TEXT("ground"));
  if (bSea) N.Add(TEXT("sea"));
  if (bWaterfalls) N.Add(TEXT("waterfalls"));
  if (bBackdrop) N.Add(TEXT("backdrop"));
  if (bFog) N.Add(TEXT("fog"));
  if (bBaseProps) N.Add(TEXT("baseProps"));
  if (bBaseFx) N.Add(TEXT("baseFx"));
  if (bLayoutLights) N.Add(TEXT("layoutLights"));
  return N.Num() ? FString::Join(N, TEXT("+")) : FString(TEXT("-"));
}

FVector2D FS08ConceptPasteSpec::CutHalf(const FVector2D& FrameHalf) const {
  return FVector2D(FrameHalf.X - CutUnderFrameUU, FrameHalf.Y - CutUnderFrameUU);
}

TArray<FString> FS08ConceptPasteSpec::AssetPaths() const {
  TArray<FString> Out;
  for (const FString* P : {&MaterialPath, &SheetMeshPath, &PlateAPath, &PlateBPath, &SeaPlatePath, &MaskPath, &LutPath,
                           &WaterMaskPath}) {
    if (!P->IsEmpty()) Out.Add(*P);
  }
  return Out;
}

FS08ConceptPasteInputs FS08ConceptPasteInputs::FromCommandLine() {
  using namespace S08ConceptPastePrivate;
  return S08ConceptPaste::InputsFromCommandLine(GFakeCommandLine.IsSet() ? *GFakeCommandLine.GetValue()
                                                                         : FCommandLine::Get());
}

// ---- world-free -------------------------------------------------------------------------------------------------

namespace S08ConceptPaste {

bool ParseJson(const FString& BoardId, const TSharedPtr<FJsonObject>& O, FS08ConceptPasteSpec& Out,
               TArray<FString>& Errors) {
  using namespace S08ConceptPastePrivate;
  Out = FS08ConceptPasteSpec();
  const int32 Before = Errors.Num();
  auto Fail = [&](const FString& What) { Errors.Add(FString::Printf(TEXT("board %s: conceptPaste.%s"), *BoardId, *What)); };
  FString Unknown;
  if (!CpKnownFields(O, {TEXT("default"), TEXT("variant"), TEXT("offVariant"), TEXT("spec"), TEXT("manifest"),
                       TEXT("material"), TEXT("sheetMesh"), TEXT("plateA"), TEXT("plateB"), TEXT("seaPlate"),
                       TEXT("mask"), TEXT("lut"), TEXT("waterMask"), TEXT("camera"), TEXT("homography"), TEXT("rectA"), TEXT("rectB"),
                       TEXT("featherPx"), TEXT("outside"), TEXT("cut"), TEXT("grade"), TEXT("sea"), TEXT("hide"),
                       TEXT("lights"), TEXT("anims"), TEXT("winds"), TEXT("shadowBlobs"), TEXT("flow")},
                   Unknown)) {
    Fail(FString::Printf(TEXT("%s is not a field"), *Unknown));
  }
  // mode
  FString Default;
  if (!O->TryGetStringField(TEXT("default"), Default) || (Default != TEXT("on") && Default != TEXT("off"))) {
    Fail(TEXT("default must be \"on\" | \"off\""));
  }
  Out.bDefaultOn = Default == TEXT("on");
  if (O->HasField(TEXT("variant")) &&
      (!O->TryGetStringField(TEXT("variant"), Out.Variant) || !S08EnvLayout::IsVariantName(Out.Variant))) {
    Fail(TEXT("variant must be an env-layout variant name [a-z0-9-]{1,32}"));
  }
  if (O->HasField(TEXT("offVariant")) &&
      (!O->TryGetStringField(TEXT("offVariant"), Out.OffVariant) || !S08EnvLayout::IsVariantName(Out.OffVariant) ||
       Out.OffVariant == Out.Variant)) {
    Fail(TEXT("offVariant must be a variant name other than variant"));
  }
  O->TryGetStringField(TEXT("spec"), Out.SpecPath);
  O->TryGetStringField(TEXT("manifest"), Out.ManifestPath);
  // assets
  auto ReadAsset = [&](const TCHAR* Field, FString& Path, bool bRequired) {
    if (!O->HasField(Field)) {
      if (bRequired) Fail(FString::Printf(TEXT("%s is required"), Field));
      return;
    }
    if (!O->TryGetStringField(Field, Path) || !CpAssetPath(Path)) {
      Fail(FString::Printf(TEXT("%s '%s' is not a %s package path (not under %s)"), Field, *Path,
                           S08ConceptPasteSpec::AssetRoot, S08ConceptPasteSpec::NeverCookRoot));
      Path.Reset();
    }
  };
  ReadAsset(TEXT("material"), Out.MaterialPath, false);
  ReadAsset(TEXT("sheetMesh"), Out.SheetMeshPath, true);
  ReadAsset(TEXT("plateA"), Out.PlateAPath, false);
  ReadAsset(TEXT("plateB"), Out.PlateBPath, true);
  ReadAsset(TEXT("seaPlate"), Out.SeaPlatePath, false);
  ReadAsset(TEXT("mask"), Out.MaskPath, false);
  ReadAsset(TEXT("lut"), Out.LutPath, false);
  ReadAsset(TEXT("waterMask"), Out.WaterMaskPath, false);
  // camera C0
  const TSharedPtr<FJsonObject>* Cam = nullptr;
  if (O->HasField(TEXT("camera"))) {
    TArray<double> Size;
    FS08ConceptCamera& C = Out.Camera;
    FString CamUnknown;
    if (!O->TryGetObjectField(TEXT("camera"), Cam) || !Cam || !Cam->IsValid() ||
        !CpKnownFields(*Cam, {TEXT("distanceUU"), TEXT("focus"), TEXT("pitch"), TEXT("yaw"), TEXT("hfov"), TEXT("sizePx")},
                     CamUnknown) ||
        !CpOptNumberD(*Cam, TEXT("distanceUU"), 100.0, 20000.0, C.DistanceUU) ||
        ((*Cam)->HasField(TEXT("focus")) && !CpVec3(*Cam, TEXT("focus"), 5000.0, C.Focus)) ||
        !CpOptNumberD(*Cam, TEXT("pitch"), -89.0, -1.0, C.PitchDeg) ||
        !CpOptNumberD(*Cam, TEXT("yaw"), -180.0, 180.0, C.YawDeg) ||
        !CpOptNumberD(*Cam, TEXT("hfov"), 5.0, 120.0, C.HFovDeg) ||
        ((*Cam)->HasField(TEXT("sizePx")) &&
         (!CpNumbers(*Cam, TEXT("sizePx"), 2, Size) || Size[0] < 16.0 || Size[1] < 16.0 || Size[0] > 16384.0 ||
          Size[1] > 16384.0 || Size[0] != FMath::RoundToDouble(Size[0]) || Size[1] != FMath::RoundToDouble(Size[1])))) {
      Fail(TEXT("camera needs optional distanceUU 100..20000, focus [x,y,z] |..| <= 5000, pitch -89..-1, yaw -180..180, hfov 5..120, sizePx [w,h] whole 16..16384"));
    } else if (Size.Num() == 2) {
      C.SizePx = FIntPoint(static_cast<int32>(Size[0]), static_cast<int32>(Size[1]));
    }
  }
  // registration homography (C0 px -> concept px)
  if (O->HasField(TEXT("homography"))) {
    const TArray<TSharedPtr<FJsonValue>>* Rows = nullptr;
    bool bOk = O->TryGetArrayField(TEXT("homography"), Rows) && Rows && Rows->Num() == 3;
    for (int32 R = 0; bOk && R < 3; ++R) {
      const TArray<TSharedPtr<FJsonValue>>* Row = nullptr;
      bOk = (*Rows)[R].IsValid() && (*Rows)[R]->TryGetArray(Row) && Row && Row->Num() == 3;
      for (int32 C = 0; bOk && C < 3; ++C) bOk = CpNumber((*Row)[C], Out.Homography.M[R][C]);
    }
    // sanity: the registration moved the concept by pixels, never by a frame - the C0 centre stays within 64 px
    const FVector2D Centre(Out.Camera.SizePx.X * 0.5, Out.Camera.SizePx.Y * 0.5);
    if (bOk) bOk = FMath::Abs(Out.Homography.M[2][2]) > 1e-9 && FVector2D::Distance(Out.Homography.Apply(Centre), Centre) <= 64.0;
    if (!bOk) {
      Fail(TEXT("homography needs [[3],[3],[3]] finite numbers that keep the C0 centre within 64 px"));
      Out.Homography = FS08ConceptHomography();
    }
  }
  auto ReadRect = [&](const TCHAR* Field, FVector4& Rect) {
    if (!O->HasField(Field)) return;
    TArray<double> N;
    if (!CpNumbers(O, Field, 4, N) || N[2] <= 0.0 || N[3] <= 0.0 || FMath::Abs(N[0]) > 10000.0 ||
        FMath::Abs(N[1]) > 10000.0 || N[2] > 40000.0 || N[3] > 40000.0) {
      Fail(FString::Printf(TEXT("%s needs [x0, y0, w, h] in concept px (w, h > 0)"), Field));
      return;
    }
    Rect = FVector4(N[0], N[1], N[2], N[3]);
  };
  ReadRect(TEXT("rectA"), Out.RectA);
  ReadRect(TEXT("rectB"), Out.RectB);
  if (!CpOptNumber(O, TEXT("featherPx"), 0.0, 200.0, Out.FeatherPx)) Fail(TEXT("featherPx must be 0..200"));
  if (O->HasField(TEXT("outside"))) {
    FString Outside;
    if (!O->TryGetStringField(TEXT("outside"), Outside) || (Outside != TEXT("clip") && Outside != TEXT("clamp"))) {
      Fail(TEXT("outside must be \"clip\" | \"clamp\""));
    }
    Out.bClampOutside = Outside == TEXT("clamp");
  }
  const TSharedPtr<FJsonObject>* Cut = nullptr;
  if (O->HasField(TEXT("cut"))) {
    FString CutUnknown;
    if (!O->TryGetObjectField(TEXT("cut"), Cut) || !Cut || !Cut->IsValid() ||
        !CpKnownFields(*Cut, {TEXT("underFrameUU"), TEXT("minZ")}, CutUnknown) ||
        !CpOptNumber(*Cut, TEXT("underFrameUU"), 0.0, 20.0, Out.CutUnderFrameUU) ||
        !CpOptNumber(*Cut, TEXT("minZ"), -500.0, 0.0, Out.CutMinZ)) {
      Fail(TEXT("cut needs optional underFrameUU 0..20 and minZ -500..0"));
    }
  }
  const TSharedPtr<FJsonObject>* Grade = nullptr;
  if (O->HasField(TEXT("grade"))) {
    FString Mode = TEXT("lut"), GradeUnknown;
    if (!O->TryGetObjectField(TEXT("grade"), Grade) || !Grade || !Grade->IsValid() ||
        !CpKnownFields(*Grade, {TEXT("mode"), TEXT("gainLinear"), TEXT("emissiveScale"), TEXT("devignette"),
                                  TEXT("fitScale"), TEXT("fitPower")}, GradeUnknown) ||
        ((*Grade)->HasField(TEXT("mode")) && !(*Grade)->TryGetStringField(TEXT("mode"), Mode)) ||
        (Mode != TEXT("lut") && Mode != TEXT("linear") && Mode != TEXT("aces-inverse")) ||
        !CpOptNumber(*Grade, TEXT("gainLinear"), 0.1, 4.0, Out.GainLinear) ||
        !CpOptNumber(*Grade, TEXT("emissiveScale"), 0.001, 1000.0, Out.EmissiveScale) ||
        !CpOptNumber(*Grade, TEXT("devignette"), 0.0, 1.0, Out.Devignette) ||
        !CpOptFit(*Grade, TEXT("fitScale"), 0.01, 100.0, Out.FitScale) ||
        !CpOptFit(*Grade, TEXT("fitPower"), 0.5, 2.0, Out.FitPower)) {
      Fail(TEXT("grade needs optional mode lut | linear | aces-inverse, gainLinear 0.1..4, emissiveScale 0.001..1000, devignette 0..1, fitScale [3 x 0.01..100], fitPower [3 x 0.5..2]"));
    } else {
      Out.Grade = Mode == TEXT("linear") ? ES08ConceptGrade::Linear
                                         : (Mode == TEXT("aces-inverse") ? ES08ConceptGrade::AcesInverse : ES08ConceptGrade::Lut);
      Out.bHasEmissiveScale = (*Grade)->HasField(TEXT("emissiveScale"));
    }
  }
  const TSharedPtr<FJsonObject>* Sea = nullptr;
  if (O->HasField(TEXT("sea"))) {
    FS08ConceptSeaSpec& S = Out.Sea;
    float Segments = static_cast<float>(S.SkySegments);
    FString SeaUnknown;
    if (!O->TryGetObjectField(TEXT("sea"), Sea) || !Sea || !Sea->IsValid() ||
        !CpKnownFields(*Sea, {TEXT("zUU"), TEXT("centreUU"), TEXT("radiusUU"), TEXT("skyTopZUU"), TEXT("skySegments")},
                     SeaUnknown) ||
        !CpOptNumber(*Sea, TEXT("zUU"), -2000.0, -10.0, S.ZUU) ||
        !CpOptNumber(*Sea, TEXT("radiusUU"), 200.0, 10000.0, S.RadiusUU) ||
        !CpOptNumber(*Sea, TEXT("skyTopZUU"), -1990.0, 5000.0, S.SkyTopZUU) ||
        !CpOptNumber(*Sea, TEXT("skySegments"), S08ConceptPasteSpec::MinSkySegments, S08ConceptPasteSpec::MaxSkySegments,
                   Segments) ||
        Segments != FMath::RoundToFloat(Segments) || S.SkyTopZUU <= S.ZUU + 10.0f) {
      Fail(TEXT("sea needs optional zUU -2000..-10, centreUU [x,y], radiusUU 200..10000, skyTopZUU > zUU + 10 (<= 5000), skySegments 8..128 (whole)"));
    } else {
      TArray<double> C;
      if ((*Sea)->HasField(TEXT("centreUU"))) {
        if (!CpNumbers(*Sea, TEXT("centreUU"), 2, C) || FMath::Abs(C[0]) > 4000.0 || FMath::Abs(C[1]) > 4000.0) {
          Fail(TEXT("sea.centreUU needs [x, y] |..| <= 4000"));
        } else {
          S.CentreUU = FVector2D(C[0], C[1]);
        }
      }
      S.SkySegments = static_cast<int32>(Segments);
      S.bSet = true;
    }
  }
  if (O->HasField(TEXT("hide"))) {
    const TArray<TSharedPtr<FJsonValue>>* Hide = nullptr;
    if (!O->TryGetArrayField(TEXT("hide"), Hide) || !Hide) {
      Fail(TEXT("hide must be an array of names"));
    } else {
      for (const TSharedPtr<FJsonValue>& V : *Hide) {
        FString N;
        if (!V.IsValid() || !V->TryGetString(N)) N = TEXT("?");
        FS08ConceptHide& H = Out.Hide;
        bool* Flag = N == TEXT("tray")         ? &H.bTray
                     : N == TEXT("ground")     ? &H.bGround
                     : N == TEXT("sea")        ? &H.bSea
                     : N == TEXT("waterfalls") ? &H.bWaterfalls
                     : N == TEXT("backdrop")   ? &H.bBackdrop
                     : N == TEXT("fog")        ? &H.bFog
                     : N == TEXT("baseProps")  ? &H.bBaseProps
                     : N == TEXT("baseFx")     ? &H.bBaseFx
                     : N == TEXT("layoutLights") ? &H.bLayoutLights
                                                 : nullptr;
        if (!Flag) {
          Fail(FString::Printf(TEXT("hide '%s' is not tray | ground | sea | waterfalls | backdrop | fog | baseProps | baseFx | layoutLights"), *N));
          continue;
        }
        *Flag = true;
      }
    }
  }
  // lights (<= 6 here; the board parser checks them against the light profile's points)
  TSet<FString> Ids;
  if (O->HasField(TEXT("lights"))) {
    const TArray<TSharedPtr<FJsonValue>>* Lights = nullptr;
    if (!O->TryGetArrayField(TEXT("lights"), Lights) || !Lights || Lights->Num() > S08ConceptPasteSpec::MaxLights) {
      Fail(FString::Printf(TEXT("lights must be an array of at most %d points"), S08ConceptPasteSpec::MaxLights));
    } else {
      for (int32 I = 0; I < Lights->Num(); ++I) {
        const TSharedPtr<FJsonObject>* L = nullptr;
        FS08ConceptLight Light;
        FString Hex, LightUnknown;
        const TSharedPtr<FJsonObject>* Flicker = nullptr;
        bool bOk = (*Lights)[I].IsValid() && (*Lights)[I]->TryGetObject(L) && L && L->IsValid() &&
                   CpKnownFields(*L, {TEXT("id"), TEXT("loc"), TEXT("colorSrgb"), TEXT("intensityCd"), TEXT("radius"),
                                    TEXT("flicker")},
                               LightUnknown) &&
                   (*L)->TryGetStringField(TEXT("id"), Light.Id) && CpIsId(Light.Id) && !Ids.Contains(Light.Id) &&
                   CpVec3(*L, TEXT("loc"), 5000.0, Light.Loc) && (*L)->TryGetStringField(TEXT("colorSrgb"), Hex) &&
                   CpHexColor(Hex, Light.Color) && (*L)->HasField(TEXT("intensityCd")) &&
                   CpOptNumber(*L, TEXT("intensityCd"), 0.0, 10000.0, Light.IntensityCd) && (*L)->HasField(TEXT("radius")) &&
                   CpOptNumber(*L, TEXT("radius"), 1.0, 5000.0, Light.RadiusUU);
        if (bOk && (*L)->HasField(TEXT("flicker"))) {
          FString FlickerUnknown;
          bOk = (*L)->TryGetObjectField(TEXT("flicker"), Flicker) && Flicker && Flicker->IsValid() &&
                CpKnownFields(*Flicker, {TEXT("amp"), TEXT("hz")}, FlickerUnknown) &&
                CpOptNumber(*Flicker, TEXT("amp"), 0.0, 0.5, Light.FlickerAmp) &&
                CpOptNumber(*Flicker, TEXT("hz"), 0.0, 20.0, Light.FlickerHz);
        }
        if (!bOk) {
          Fail(FString::Printf(TEXT("lights[%d] needs a unique id, loc [x,y,z] |..| <= 5000, colorSrgb #RRGGBB, intensityCd 0..10000, radius 1..5000, optional flicker {amp 0..0.5, hz 0..20}"), I));
          continue;
        }
        Ids.Add(Light.Id);
        Out.Lights.Add(Light);
      }
    }
    if (Out.Lights.Num() > 0 && !Out.Hide.bLayoutLights) {
      Fail(TEXT("lights replace the env-layout lights: hide needs \"layoutLights\" (light budget)"));
    }
  }
  if (O->HasField(TEXT("anims"))) {
    const TArray<TSharedPtr<FJsonValue>>* Anims = nullptr;
    if (!O->TryGetArrayField(TEXT("anims"), Anims) || !Anims || Anims->Num() > S08ConceptPasteSpec::MaxAnims) {
      Fail(FString::Printf(TEXT("anims must be an array of at most %d entries"), S08ConceptPasteSpec::MaxAnims));
    } else {
      for (int32 I = 0; I < Anims->Num(); ++I) {
        const TSharedPtr<FJsonObject>* A = nullptr;
        FS08ConceptAnim Anim;
        FString Axis = TEXT("x"), AnimUnknown;
        const bool bOk = (*Anims)[I].IsValid() && (*Anims)[I]->TryGetObject(A) && A && A->IsValid() &&
                         CpKnownFields(*A, {TEXT("prop"), TEXT("swayDeg"), TEXT("swayHz"), TEXT("axis")}, AnimUnknown) &&
                         (*A)->TryGetStringField(TEXT("prop"), Anim.Prop) && CpIsId(Anim.Prop) &&
                         (*A)->HasField(TEXT("swayDeg")) && CpOptNumber(*A, TEXT("swayDeg"), 0.0, 15.0, Anim.SwayDeg) &&
                         (*A)->HasField(TEXT("swayHz")) && CpOptNumber(*A, TEXT("swayHz"), 0.0, 5.0, Anim.SwayHz) &&
                         (!(*A)->HasField(TEXT("axis")) ||
                          ((*A)->TryGetStringField(TEXT("axis"), Axis) && (Axis == TEXT("x") || Axis == TEXT("y"))));
        if (!bOk) {
          Fail(FString::Printf(TEXT("anims[%d] needs prop (an env-layout prop id), swayDeg 0..15, swayHz 0..5, optional axis x | y"), I));
          continue;
        }
        Anim.bAxisY = Axis == TEXT("y");
        Out.Anims.Add(Anim);
      }
    }
  }
  if (O->HasField(TEXT("winds"))) {
    const TArray<TSharedPtr<FJsonValue>>* Winds = nullptr;
    if (!O->TryGetArrayField(TEXT("winds"), Winds) || !Winds || Winds->Num() > S08ConceptPasteSpec::MaxWinds) {
      Fail(FString::Printf(TEXT("winds must be an array of at most %d prop ids"), S08ConceptPasteSpec::MaxWinds));
    } else {
      for (int32 I = 0; I < Winds->Num(); ++I) {
        FString Prop;
        if (!(*Winds)[I].IsValid() || !(*Winds)[I]->TryGetString(Prop) || !CpIsId(Prop) || Out.WindProps.Contains(Prop)) {
          Fail(FString::Printf(TEXT("winds[%d] must be a unique env-layout prop id"), I));
          continue;
        }
        Out.WindProps.Add(Prop);
      }
    }
  }
  if (O->HasField(TEXT("shadowBlobs"))) {
    const TArray<TSharedPtr<FJsonValue>>* Blobs = nullptr;
    TSet<FString> BlobIds;
    if (!O->TryGetArrayField(TEXT("shadowBlobs"), Blobs) || !Blobs || Blobs->Num() > S08ConceptPasteSpec::MaxShadowBlobs) {
      Fail(FString::Printf(TEXT("shadowBlobs must be an array of at most %d blobs"), S08ConceptPasteSpec::MaxShadowBlobs));
    } else {
      for (int32 I = 0; I < Blobs->Num(); ++I) {
        const TSharedPtr<FJsonObject>* B = nullptr;
        FS08ConceptShadowBlob Blob;
        FString BlobUnknown;
        const bool bOk = (*Blobs)[I].IsValid() && (*Blobs)[I]->TryGetObject(B) && B && B->IsValid() &&
                         CpKnownFields(*B, {TEXT("id"), TEXT("loc"), TEXT("diameterUU"), TEXT("strength"), TEXT("softness")},
                                     BlobUnknown) &&
                         (*B)->TryGetStringField(TEXT("id"), Blob.Id) && CpIsId(Blob.Id) && !BlobIds.Contains(Blob.Id) &&
                         CpVec3(*B, TEXT("loc"), 5000.0, Blob.Loc) &&
                         CpOptNumber(*B, TEXT("diameterUU"), 10.0, 300.0, Blob.DiameterUU) &&
                         CpOptNumber(*B, TEXT("strength"), 0.0, 1.0, Blob.Strength) &&
                         CpOptNumber(*B, TEXT("softness"), 0.1, 1.0, Blob.Softness);
        if (!bOk) {
          Fail(FString::Printf(TEXT("shadowBlobs[%d] needs a unique id, loc [x,y,z], optional diameterUU 10..300, strength 0..1, softness 0.1..1"), I));
          continue;
        }
        BlobIds.Add(Blob.Id);
        Out.ShadowBlobs.Add(Blob);
      }
    }
  }
  if (O->HasField(TEXT("flow"))) {
    const TSharedPtr<FJsonObject>* Flow = nullptr;
    FString FlowUnknown;
    if (!O->TryGetObjectField(TEXT("flow"), Flow) || !Flow || !Flow->IsValid() ||
        !CpKnownFields(*Flow, {TEXT("regions"), TEXT("sea")}, FlowUnknown)) {
      Fail(TEXT("flow must be an object {regions, sea}"));
    } else {
      // velocity [x, y] px / s |..| <= 200 and amplitude 0..6 px
      auto ReadMotion = [](const TSharedPtr<FJsonObject>& M, FVector2D& OutVel, float& OutAmp) {
        TArray<double> V;
        if (!CpNumbers(M, TEXT("velocityPx"), 2, V) || FMath::Abs(V[0]) > 200.0 || FMath::Abs(V[1]) > 200.0 ||
            !M->HasField(TEXT("ampPx")) || !CpOptNumber(M, TEXT("ampPx"), 0.0, 6.0, OutAmp)) {
          return false;
        }
        OutVel = FVector2D(V[0], V[1]);
        return true;
      };
      const TArray<TSharedPtr<FJsonValue>>* Regions = nullptr;
      if ((*Flow)->HasField(TEXT("regions"))) {
        if (!(*Flow)->TryGetArrayField(TEXT("regions"), Regions) || !Regions ||
            Regions->Num() > S08ConceptPasteSpec::MaxFlows) {
          Fail(FString::Printf(TEXT("flow.regions must be an array of at most %d regions"), S08ConceptPasteSpec::MaxFlows));
        } else {
          for (int32 I = 0; I < Regions->Num(); ++I) {
            const TSharedPtr<FJsonObject>* R = nullptr;
            FS08ConceptFlow F;
            TArray<double> Rect;
            FString RegionUnknown;
            const bool bOk = (*Regions)[I].IsValid() && (*Regions)[I]->TryGetObject(R) && R && R->IsValid() &&
                             CpKnownFields(*R, {TEXT("id"), TEXT("rectPx"), TEXT("velocityPx"), TEXT("ampPx")}, RegionUnknown) &&
                             (*R)->TryGetStringField(TEXT("id"), F.Id) && CpIsId(F.Id) &&
                             CpNumbers(*R, TEXT("rectPx"), 4, Rect) && Rect[2] > 0.0 && Rect[3] > 0.0 &&
                             FMath::Abs(Rect[0]) <= 10000.0 && FMath::Abs(Rect[1]) <= 10000.0 &&
                             ReadMotion(*R, F.VelocityPx, F.AmpPx);
            if (!bOk) {
              Fail(FString::Printf(TEXT("flow.regions[%d] needs id, rectPx [x0, y0, w, h] (w, h > 0), velocityPx [x, y] |..| <= 200, ampPx 0..6"), I));
              continue;
            }
            F.RectPx = FVector4(Rect[0], Rect[1], Rect[2], Rect[3]);
            Out.Flows.Add(F);
          }
        }
      }
      const TSharedPtr<FJsonObject>* SeaFlow = nullptr;
      if ((*Flow)->HasField(TEXT("sea"))) {
        FString SeaUnknown;
        if (!(*Flow)->TryGetObjectField(TEXT("sea"), SeaFlow) || !SeaFlow || !SeaFlow->IsValid() ||
            !CpKnownFields(*SeaFlow, {TEXT("velocityPx"), TEXT("ampPx")}, SeaUnknown) ||
            !ReadMotion(*SeaFlow, Out.SeaFlow.VelocityPx, Out.SeaFlow.AmpPx)) {
          Fail(TEXT("flow.sea needs velocityPx [x, y] |..| <= 200 and ampPx 0..6"));
        } else if (!Out.Sea.bSet) {
          Fail(TEXT("flow.sea needs the sea layer (\"sea\")"));
        } else {
          Out.SeaFlow.bSet = true;
        }
      }
    }
  }
  Out.bSet = Errors.Num() == Before;
  return Out.bSet;
}

FS08ConceptPasteInputs InputsFromCommandLine(const TCHAR* CommandLine) {
  FS08ConceptPasteInputs In;
  TArray<FString> Tokens, Switches;
  FCommandLine::Parse(CommandLine ? CommandLine : TEXT(""), Tokens, Switches);
  for (const FString& Switch : Switches) {
    FString Key = Switch, Value;
    const bool bHasValue = Switch.Split(TEXT("="), &Key, &Value);
    Value = Value.TrimQuotes().TrimStartAndEnd();
    if (Key.Equals(S08ConceptPasteSpec::FlagName, ESearchCase::IgnoreCase)) {
      const FString V = Value.ToLower();
      In.FlagText = bHasValue ? V : FString(TEXT("1"));
      if (!bHasValue || V == TEXT("1") || V == TEXT("on") || V == TEXT("true")) {
        In.bFlagOn = true;
        In.bFlagOff = false;
      } else if (V == TEXT("0") || V == TEXT("off") || V == TEXT("false")) {
        In.bFlagOff = true;
        In.bFlagOn = false;
      }
    } else if (Key.Equals(S08ConceptPasteSpec::NoFlagName, ESearchCase::IgnoreCase) && !bHasValue) {
      In.bFlagOff = true;
      In.bFlagOn = false;
      In.FlagText = TEXT("no");
    } else if (Key.Equals(S08ConceptPasteSpec::CalibFlagName, ESearchCase::IgnoreCase) && !bHasValue) {
      In.bCalib = true;
    } else if (bHasValue && Key.Equals(TEXT("EnvLayoutVariant"), ESearchCase::IgnoreCase)) {
      In.Variant = Value;
    }
  }
  return In;
}

void SetCommandLineOverrideForTest(const FString& FakeCommandLine) {
  S08ConceptPastePrivate::GFakeCommandLine = FakeCommandLine;
}

void ResetCommandLineOverrideForTest() { S08ConceptPastePrivate::GFakeCommandLine.Reset(); }

void SetForceApplyFailureForTest(bool bFail) { S08ConceptPastePrivate::GForceApplyFailure = bFail; }

FS08ConceptPasteMode ResolveMode(const FS08ConceptPasteSpec& Spec, const FS08ConceptPasteInputs& In, bool bGate) {
  FS08ConceptPasteMode M;
  if (!Spec.bSet) return M;  // no-block: the env layout reads the command line as before
  if (!bGate) {
    M.Reason = TEXT("gate");
    return M;
  }
  const bool bConceptVariant = In.Variant == Spec.Variant;
  const bool bOffVariant = !Spec.OffVariant.IsEmpty() && In.Variant == Spec.OffVariant;
  if (In.bFlagOff) {
    M.Reason = TEXT("flag-off");
    if (bConceptVariant || bOffVariant) {
      // the concept overlay without the paste would leave holes; the off variant means the base layout
      M.bOverrideVariant = true;
      M.Variant.Reset();
    }
    return M;
  }
  if (In.bFlagOn) {
    M.Reason = TEXT("flag-on");
  } else if (bConceptVariant) {
    M.Reason = TEXT("variant");
  } else if (bOffVariant) {
    M.Reason = TEXT("variant-off");
    M.bOverrideVariant = true;  // the base layout, byte for byte (no '<map>.<offVariant>.layout.json' is needed)
    M.Variant.Reset();
    return M;
  } else if (!In.Variant.IsEmpty()) {
    M.Reason = TEXT("variant-other");  // e.g. the NoAI 'user' variant: that overlay applies, no paste
    return M;
  } else {
    M.Reason = TEXT("default");
    if (!Spec.bDefaultOn) return M;
  }
  M.bOn = true;
  M.bOverrideVariant = true;
  M.Variant = Spec.Variant;
  return M;
}

FS08ConceptPasteMode FallbackOff(const FS08ConceptPasteSpec& Spec, const FS08ConceptPasteInputs& In, const TCHAR* Reason) {
  FS08ConceptPasteMode M;
  M.Reason = Reason;
  if (Spec.bSet && In.Variant == Spec.Variant) {
    M.bOverrideVariant = true;
    M.Variant.Reset();
  }
  return M;
}

FTransform SeaPlaneTransform(const FS08ConceptSeaSpec& Sea) {
  return FTransform(FQuat::Identity, FVector(Sea.CentreUU.X, Sea.CentreUU.Y, Sea.ZUU),
                    FVector(Sea.RadiusUU * 2.0 / 100.0, Sea.RadiusUU * 2.0 / 100.0, 1.0));
}

TArray<FTransform> SkySegmentTransforms(const FS08ConceptSeaSpec& Sea) {
  TArray<FTransform> Out;
  const int32 N = FMath::Clamp(Sea.SkySegments, S08ConceptPasteSpec::MinSkySegments, S08ConceptPasteSpec::MaxSkySegments);
  const double Half = UE_DOUBLE_PI / N;
  const double Width = 2.0 * Sea.RadiusUU * FMath::Sin(Half);
  const double Apothem = Sea.RadiusUU * FMath::Cos(Half);
  const double Height = Sea.SkyTopZUU - Sea.ZUU;
  for (int32 I = 0; I < N; ++I) {
    const double Mid = (2.0 * I + 1.0) * Half;
    const FVector Outward(FMath::Cos(Mid), FMath::Sin(Mid), 0.0);
    const FVector Inward = -Outward;
    const FVector Tangent = FVector::CrossProduct(FVector::UpVector, Inward);  // local X along the chord
    const FQuat Rotation = FRotationMatrix::MakeFromXZ(Tangent, Inward).ToQuat();  // local Y = up, local Z = inward
    const FVector Centre(Sea.CentreUU.X + Outward.X * Apothem, Sea.CentreUU.Y + Outward.Y * Apothem,
                         Sea.ZUU + Height * 0.5);
    Out.Add(FTransform(Rotation, Centre, FVector(Width / 100.0, Height / 100.0, 1.0)));
  }
  return Out;
}

FS08ConceptMaterialParams MaterialParams(const FS08ConceptPasteSpec& Spec, const FVector2D& FrameHalf, bool bSea,
                                         bool bHasPlateA, ES08ConceptGrade Grade, float EmissiveScale, bool bCalib,
                                         bool bFreezeFlow) {
  FS08ConceptMaterialParams P;
  const FS08ConceptCamera& C = Spec.Camera;
  auto V3 = [](const FVector& V) { return FLinearColor(static_cast<float>(V.X), static_cast<float>(V.Y), static_cast<float>(V.Z), 0.0f); };
  P.CamPos = V3(C.Location());
  P.CamRight = V3(C.Right());
  P.CamUp = V3(C.Up());
  P.CamForward = V3(C.Forward());
  P.CamTan = FLinearColor(static_cast<float>(C.TanHalfH()), static_cast<float>(C.TanHalfV()),
                          static_cast<float>(C.SizePx.X), static_cast<float>(C.SizePx.Y));
  const auto& M = Spec.Homography.M;
  P.HRow0 = FLinearColor(static_cast<float>(M[0][0]), static_cast<float>(M[0][1]), static_cast<float>(M[0][2]), 0.0f);
  P.HRow1 = FLinearColor(static_cast<float>(M[1][0]), static_cast<float>(M[1][1]), static_cast<float>(M[1][2]), 0.0f);
  P.HRow2 = FLinearColor(static_cast<float>(M[2][0]), static_cast<float>(M[2][1]), static_cast<float>(M[2][2]), 0.0f);
  auto R4 = [](const FVector4& R) {
    return FLinearColor(static_cast<float>(R.X), static_cast<float>(R.Y), static_cast<float>(R.Z), static_cast<float>(R.W));
  };
  P.RectA = R4(Spec.RectA);
  P.RectB = R4(Spec.RectB);
  const FVector2D Cut = Spec.CutHalf(FrameHalf);
  P.Cut = bSea ? FLinearColor(0.0f, 0.0f, 0.0f, 0.0f)
               : FLinearColor(static_cast<float>(Cut.X), static_cast<float>(Cut.Y), Spec.CutMinZ, 1.0f);
  P.UseA = !bSea && bHasPlateA ? 1.0f : 0.0f;
  P.FeatherPx = Spec.FeatherPx;
  P.AlphaWeight = bSea ? 0.0f : 1.0f;
  P.OutsideKeep = bSea || Spec.bClampOutside ? 1.0f : 0.0f;
  P.GradeMode = Grade == ES08ConceptGrade::Linear ? 0.0f : (Grade == ES08ConceptGrade::Lut ? 1.0f : 2.0f);
  P.GainLinear = Spec.GainLinear;
  P.EmissiveScale = EmissiveScale;
  P.Devignette = Spec.Devignette;
  P.GradeScale = FLinearColor(static_cast<float>(Spec.FitScale.X), static_cast<float>(Spec.FitScale.Y),
                              static_cast<float>(Spec.FitScale.Z), 0.0f);
  P.GradePow = FLinearColor(static_cast<float>(1.0 / Spec.FitPower.X), static_cast<float>(1.0 / Spec.FitPower.Y),
                            static_cast<float>(1.0 / Spec.FitPower.Z), 0.0f);
  P.Calib = bCalib ? 1.0f : 0.0f;
  P.CalibMax = S08ConceptPasteSpec::DefaultCalibMax;
  // painted-water flow: the sheet's regions, or the sea layer's whole plate below the sea level (never the sky)
  const float Freeze = bFreezeFlow ? 0.0f : 1.0f;
  P.FlowSea = bSea ? 1.0f : 0.0f;
  if (bSea) {
    if (Spec.SeaFlow.bSet) {
      P.FlowRect0 = P.RectB;
      P.FlowVel0 = FLinearColor(static_cast<float>(Spec.SeaFlow.VelocityPx.X), static_cast<float>(Spec.SeaFlow.VelocityPx.Y),
                                Spec.SeaFlow.AmpPx * Freeze, 0.0f);
      P.FlowMaxZ = Spec.Sea.ZUU + 1.0f;
    }
  } else {
    for (int32 I = 0; I < Spec.Flows.Num() && I < S08ConceptPasteSpec::MaxFlows; ++I) {
      const FS08ConceptFlow& F = Spec.Flows[I];
      (I == 0 ? P.FlowRect0 : P.FlowRect1) = R4(F.RectPx);
      (I == 0 ? P.FlowVel0 : P.FlowVel1) = FLinearColor(static_cast<float>(F.VelocityPx.X), static_cast<float>(F.VelocityPx.Y),
                                                        F.AmpPx * Freeze, 0.0f);
    }
  }
  return P;
}

FS08ConceptShaderSample ShaderSample(const FS08ConceptMaterialParams& P, const FVector& W) {
  // Mirror of the HLSL in tools/art/concept_paste/ue_concept_material.py (keep both in step).
  FS08ConceptShaderSample S;
  const FVector Pos(P.CamPos.R, P.CamPos.G, P.CamPos.B);
  const FVector R(P.CamRight.R, P.CamRight.G, P.CamRight.B);
  const FVector U(P.CamUp.R, P.CamUp.G, P.CamUp.B);
  const FVector F(P.CamForward.R, P.CamForward.G, P.CamForward.B);
  const FVector D = W - Pos;
  const double Z = FVector::DotProduct(D, F);
  S.bInFront = Z > 1e-3;
  const double Zs = FMath::Max(Z, 1e-3);
  const double Sx = FVector::DotProduct(D, R) / Zs / P.CamTan.R;
  const double Sy = FVector::DotProduct(D, U) / Zs / P.CamTan.G;
  S.C0Px = FVector2D((Sx + 1.0) * 0.5 * P.CamTan.B, (1.0 - Sy) * 0.5 * P.CamTan.A);
  const double Hw = P.HRow2.R * S.C0Px.X + P.HRow2.G * S.C0Px.Y + P.HRow2.B;
  S.ConceptPx = FVector2D((P.HRow0.R * S.C0Px.X + P.HRow0.G * S.C0Px.Y + P.HRow0.B) / Hw,
                          (P.HRow1.R * S.C0Px.X + P.HRow1.G * S.C0Px.Y + P.HRow1.B) / Hw);
  const FVector2D A0(P.RectA.R, P.RectA.G), AS(P.RectA.B, P.RectA.A), B0(P.RectB.R, P.RectB.G), BS(P.RectB.B, P.RectB.A);
  S.UvA = (S.ConceptPx - A0) / AS;
  S.UvB = (S.ConceptPx - B0) / BS;
  const FVector2D InA(FMath::Min(S.ConceptPx.X - A0.X, A0.X + AS.X - S.ConceptPx.X),
                      FMath::Min(S.ConceptPx.Y - A0.Y, A0.Y + AS.Y - S.ConceptPx.Y));
  S.WeightA = P.UseA * FMath::Clamp(static_cast<float>(FMath::Min(InA.X, InA.Y) / FMath::Max(P.FeatherPx, 1e-3f)), 0.0f, 1.0f);
  S.bInsideB = S.UvB.X >= 0.0 && S.UvB.Y >= 0.0 && S.UvB.X <= 1.0 && S.UvB.Y <= 1.0;
  S.bCut = P.Cut.A > 0.5f && FMath::Abs(W.X) < P.Cut.R && FMath::Abs(W.Y) < P.Cut.G && W.Z > P.Cut.B;
  auto FlowWeight = [&S, &P, &W](const FLinearColor& Rect) {
    if (Rect.B < 0.5f || W.Z > P.FlowMaxZ) return 0.0f;
    const double In = FMath::Min(FMath::Min(S.ConceptPx.X - Rect.R, Rect.R + Rect.B - S.ConceptPx.X),
                                 FMath::Min(S.ConceptPx.Y - Rect.G, Rect.G + Rect.A - S.ConceptPx.Y));
    return FMath::Clamp(static_cast<float>(In / S08ConceptPasteSpec::FlowFeatherPx), 0.0f, 1.0f);
  };
  S.FlowWeight0 = FlowWeight(P.FlowRect0);
  S.FlowWeight1 = FlowWeight(P.FlowRect1);
  return S;
}

float AcesApprox(float X) {
  const float L = X * 0.6f;
  return FMath::Clamp((L * (2.51f * L + 0.03f)) / (L * (2.43f * L + 0.59f) + 0.14f), 0.0f, 1.0f);
}

float InverseAcesApprox(float Y) {
  const float Yc = FMath::Clamp(Y, 0.0f, 0.98f);
  const float A = 2.51f - Yc * 2.43f;
  const float B = 0.03f - Yc * 0.59f;
  const float C = -Yc * 0.14f;
  const float X = (-B + FMath::Sqrt(FMath::Max(B * B - 4.0f * A * C, 0.0f))) / (2.0f * A);
  return X / 0.6f;
}

float FlickerScale(const FS08ConceptLight& Light, double TimeS) {
  if (Light.FlickerAmp <= 0.0f || Light.FlickerHz <= 0.0f) return 1.0f;
  const uint32 Seed = S08ConceptPastePrivate::CpSeedOf(Light.Id);
  const double W = 2.0 * UE_DOUBLE_PI * Light.FlickerHz * TimeS;
  const double N = 0.6 * FMath::Sin(W + S08ConceptPastePrivate::CpPhase(Seed, 0)) +
                   0.4 * FMath::Sin(W * 2.37 + S08ConceptPastePrivate::CpPhase(Seed, 16));
  return static_cast<float>(1.0 + Light.FlickerAmp * N);
}

float SwayAngleDeg(const FS08ConceptAnim& Anim, double TimeS) {
  if (Anim.SwayDeg <= 0.0f || Anim.SwayHz <= 0.0f) return 0.0f;
  const uint32 Seed = S08ConceptPastePrivate::CpSeedOf(Anim.Prop);
  return static_cast<float>(Anim.SwayDeg *
                            FMath::Sin(2.0 * UE_DOUBLE_PI * Anim.SwayHz * TimeS + S08ConceptPastePrivate::CpPhase(Seed, 0)));
}

ES08ConceptGrade EffectiveGrade(const FS08ConceptPasteSpec& Spec, bool bHasLut) {
  return Spec.Grade == ES08ConceptGrade::Lut && !bHasLut ? ES08ConceptGrade::AcesInverse : Spec.Grade;
}

float EffectiveEmissiveScale(const FS08ConceptPasteSpec& Spec, bool bExposureSet, float ExposureMaxBrightness,
                             FString& OutSource) {
  if (Spec.bHasEmissiveScale) {
    OutSource = TEXT("block");
    return Spec.EmissiveScale;
  }
  if (bExposureSet && ExposureMaxBrightness > 0.0f) {
    // fixed exposure (min == max brightness): the scene is scaled by ~1 / brightness before the tonemapper
    OutSource = TEXT("exposure");
    return ExposureMaxBrightness;
  }
  OutSource = TEXT("default");
  return 1.0f;
}

FString MissingLine(const FString& Path) { return TEXT("ARTPREVIEW concept-paste missing ") + Path; }

FString GroundKindOf(const FString& Name) {
  if (Name.StartsWith(TEXT("EnvWaterfall"))) return TEXT("waterfalls");
  if (Name.StartsWith(TEXT("EnvSea"))) return TEXT("sea");
  if (Name.StartsWith(TEXT("EnvGround"))) return TEXT("ground");
  return FString();
}

// ---- world -------------------------------------------------------------------------------------------------------

FS08ConceptPasteAssets LoadAssets(const FS08ConceptPasteSpec& Spec) {
  using namespace S08ConceptPastePrivate;
  FS08ConceptPasteAssets A;
  auto Load = [&A](const FString& Path, UClass* Class) -> UObject* {
    if (Path.IsEmpty()) return nullptr;
    // uncooked runs (editor, automation) ask the package first: a missing import never reaches the loader
    const bool bMayExist = FPlatformProperties::RequiresCookedData() || FPackageName::DoesPackageExist(CpPackageOf(Path));
    UObject* Obj = bMayExist ? StaticLoadObject(Class, nullptr, *Path, nullptr, LOAD_NoWarn) : nullptr;
    if (!Obj) A.Missing.Add(Path);
    return Obj;
  };
  A.Material = Cast<UMaterialInterface>(Load(Spec.MaterialPath, UMaterialInterface::StaticClass()));
  A.Sheet = Cast<UStaticMesh>(Load(Spec.SheetMeshPath, UStaticMesh::StaticClass()));
  A.PlateA = Cast<UTexture>(Load(Spec.PlateAPath, UTexture::StaticClass()));
  A.PlateB = Cast<UTexture>(Load(Spec.PlateBPath, UTexture::StaticClass()));
  A.Sea = Cast<UTexture>(Load(Spec.SeaPlatePath, UTexture::StaticClass()));
  A.Mask = Cast<UTexture>(Load(Spec.MaskPath, UTexture::StaticClass()));
  A.Lut = Cast<UTexture>(Load(Spec.LutPath, UTexture::StaticClass()));
  A.Water = Cast<UTexture>(Load(Spec.WaterMaskPath, UTexture::StaticClass()));
  A.Plane = Cast<UStaticMesh>(Load(S08ConceptPasteSpec::PlaneMeshPath, UStaticMesh::StaticClass()));
  if (Spec.ShadowBlobs.Num() > 0) {
    A.ShadowMaterial =
        Cast<UMaterialInterface>(Load(S08ConceptPasteSpec::ContactShadowMaterialPath, UMaterialInterface::StaticClass()));
  }
  return A;
}

void Clear(TArray<TObjectPtr<UStaticMeshComponent>>& Parts, TArray<TObjectPtr<UPointLightComponent>>& Lights,
           FS08ConceptPasteRuntime& Runtime) {
  for (UStaticMeshComponent* C : Parts) {
    if (C) C->DestroyComponent();
  }
  for (UPointLightComponent* C : Lights) {
    if (C) C->DestroyComponent();
  }
  Parts.Reset();
  Lights.Reset();
  Runtime.SheetParts = 0;
  Runtime.SeaParts = 0;
  Runtime.Lights = 0;
  Runtime.Blobs = 0;
  Runtime.Status = TEXT("off");
}

void Apply(const FS08ConceptPasteSpec& Spec, const FS08ConceptPasteAssets& Assets, const FVector2D& FrameHalf,
           ES08ConceptGrade Grade, float EmissiveScale, bool bCalib, bool bFreezeFlow, AActor& Owner, USceneComponent* Root,
           TArray<TObjectPtr<UStaticMeshComponent>>& Parts, TArray<TObjectPtr<UPointLightComponent>>& Lights,
           FS08ConceptPasteRuntime& Runtime) {
  using namespace S08ConceptPastePrivate;
  using namespace S08ConceptPasteSpec;
  Clear(Parts, Lights, Runtime);
  Runtime.bTraced = true;
  Runtime.Grade = S08ConceptGradeName(Grade);
  Runtime.EmissiveScale = EmissiveScale;
  Runtime.bCalib = bCalib;
  if (!Assets.RequiredOk()) {
    Runtime.Status = TEXT("missing");
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW concept-paste status=missing profile=%s (run tools/art/concept_paste/ue_import_concept_paste.py and ue_concept_material.py) -> no paste"),
                                     *Runtime.ProfileId));
    return;
  }
  if (GForceApplyFailure) {
    // automation only (P7c): the assets are there, Apply fails anyway -> the board actor's full P5c fallback
    Runtime.Status = TEXT("failed");
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW concept-paste status=failed profile=%s (forced by the automation hook) -> no paste"),
                                     *Runtime.ProfileId));
    return;
  }
  // the sheet: the depth mesh in board space (identity under the actor root, which sits at the world origin)
  UMaterialInstanceDynamic* SheetMid = UMaterialInstanceDynamic::Create(Assets.Material, &Owner);
  FS08ConceptMaterialParams SheetParams =
      MaterialParams(Spec, FrameHalf, false, Assets.PlateA != nullptr, Grade, EmissiveScale, bCalib, bFreezeFlow);
  SheetParams.UseWater = Assets.Water ? 1.0f : 0.0f;
  CpSetParams(*SheetMid, SheetParams);
  if (Assets.Water) SheetMid->SetTextureParameterValue(FName(ParamWater), Assets.Water);
  SheetMid->SetTextureParameterValue(FName(ParamPlateA), Assets.PlateA ? Assets.PlateA : Assets.PlateB);
  SheetMid->SetTextureParameterValue(FName(ParamPlateB), Assets.PlateB);
  if (Assets.Mask) SheetMid->SetTextureParameterValue(FName(ParamMask), Assets.Mask);
  if (Assets.Lut) SheetMid->SetTextureParameterValue(FName(ParamLut), Assets.Lut);
  UStaticMeshComponent* Sheet = CpNewPart(Owner, Root, TEXT("ConceptPasteSheet"), Assets.Sheet, SheetMid, FTransform::Identity);
  Parts.Add(Sheet);
  Runtime.SheetParts = 1;
  const FBox SheetBox = Assets.Sheet->GetBoundingBox();
  int32 Triangles = -1;
  if (const FStaticMeshRenderData* Render = Assets.Sheet->GetRenderData()) {
    if (Render->LODResources.Num() > 0) Triangles = Render->LODResources[0].GetNumTriangles();
  }
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW concept-paste sheet profile=%s mesh=%s triangles=%d bounds=%s..%s slots=%d plateA=%s plateB=%s mask=%s cut=(%.2f,%.2f) minZ=%.1f outside=%s"),
      *Runtime.ProfileId, *Assets.Sheet->GetName(), Triangles, *CpVec(SheetBox.Min), *CpVec(SheetBox.Max),
      Sheet->GetNumMaterials(), Assets.PlateA ? *Assets.PlateA->GetName() : TEXT("-(plateB)"), *Assets.PlateB->GetName(),
      Assets.Mask ? *Assets.Mask->GetName() : TEXT("-"), Spec.CutHalf(FrameHalf).X, Spec.CutHalf(FrameHalf).Y,
      Spec.CutMinZ, Spec.bClampOutside ? TEXT("clamp") : TEXT("clip")));
  // the sea layer: sea plane + sky cylinder, the same projection (no alpha, no cut, edge clamp)
  if (Spec.Sea.bSet) {
    UMaterialInstanceDynamic* SeaMid = UMaterialInstanceDynamic::Create(Assets.Material, &Owner);
    FS08ConceptMaterialParams SeaParams = MaterialParams(Spec, FrameHalf, true, false, Grade, EmissiveScale, bCalib, bFreezeFlow);
    SeaParams.UseWater = Assets.Water ? 1.0f : 0.0f;
    CpSetParams(*SeaMid, SeaParams);
    if (Assets.Water) SeaMid->SetTextureParameterValue(FName(ParamWater), Assets.Water);
    UTexture* SeaTex = Assets.Sea ? Assets.Sea : Assets.PlateB;
    SeaMid->SetTextureParameterValue(FName(ParamPlateA), SeaTex);
    SeaMid->SetTextureParameterValue(FName(ParamPlateB), SeaTex);
    if (Assets.Lut) SeaMid->SetTextureParameterValue(FName(ParamLut), Assets.Lut);
    Parts.Add(CpNewPart(Owner, Root, TEXT("ConceptPasteSea"), Assets.Plane, SeaMid, SeaPlaneTransform(Spec.Sea)));
    const TArray<FTransform> Sky = SkySegmentTransforms(Spec.Sea);
    for (const FTransform& T : Sky) Parts.Add(CpNewPart(Owner, Root, TEXT("ConceptPasteSky"), Assets.Plane, SeaMid, T));
    Runtime.SeaParts = 1 + Sky.Num();
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW concept-paste sea profile=%s plate=%s z=%.0f centre=(%.0f,%.0f) radius=%.0f skyTopZ=%.0f skySegments=%d"),
        *Runtime.ProfileId, *SeaTex->GetName(), Spec.Sea.ZUU, Spec.Sea.CentreUU.X, Spec.Sea.CentreUU.Y, Spec.Sea.RadiusUU,
        Spec.Sea.SkyTopZUU, Sky.Num()));
  }
  // the true lights of the main fires / lanterns (the painted pools are in the plates; these light the real layer)
  const bool bCandelas = !S08LegacyRender();
  for (const FS08ConceptLight& L : Spec.Lights) {
    UPointLightComponent* C = NewObject<UPointLightComponent>(
        &Owner, MakeUniqueObjectName(&Owner, UPointLightComponent::StaticClass(), FName(*(TEXT("ConceptLight_") + L.Id))));
    C->SetupAttachment(Root ? Root : Owner.GetRootComponent());
    C->SetMobility(EComponentMobility::Movable);
    if (bCandelas) C->SetIntensityUnits(ELightUnits::Candelas);
    C->SetIntensity(L.IntensityCd);
    C->SetAttenuationRadius(L.RadiusUU);
    C->SetCastShadows(false);
    C->SetLightFColor(L.Color);
    C->SetRelativeLocation(L.Loc);
    C->RegisterComponent();
    Lights.Add(C);
    ++Runtime.Lights;
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW concept-paste light id=%s kind=point at=%s intensity=%g units=%s radius=%g color=%s shadow=0 flicker=%.2f@%.1fHz"),
        *L.Id, *CpVec(L.Loc), L.IntensityCd, bCandelas ? TEXT("candelas") : TEXT("unitless-legacy"), L.RadiusUU,
        *CpColorHex(L.Color), L.FlickerAmp, L.FlickerHz));
  }
  // contact-shadow blobs under the 3D details (the unlit sheet receives no shadow)
  if (Spec.ShadowBlobs.Num() > 0 && !Assets.ShadowMaterial) {
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW concept-paste blobs skipped=%d (missing %s)"), Spec.ShadowBlobs.Num(),
                                     ContactShadowMaterialPath));
  }
  for (const FS08ConceptShadowBlob& B : Spec.ShadowBlobs) {
    if (!Assets.ShadowMaterial) break;
    UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(Assets.ShadowMaterial, &Owner);
    Mid->SetScalarParameterValue(TEXT("Strength"), B.Strength);
    Mid->SetScalarParameterValue(TEXT("Softness"), B.Softness);
    const FTransform T(FQuat::Identity, B.Loc + FVector(0.0, 0.0, BlobLiftUU),
                       FVector(B.DiameterUU / 100.0, B.DiameterUU / 100.0, 1.0));
    Parts.Add(CpNewPart(Owner, Root, TEXT("ConceptPasteBlob"), Assets.Plane, Mid, T));
    ++Runtime.Blobs;
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW concept-paste blob id=%s at=%s diameterUU=%.0f strength=%.2f softness=%.2f"),
                                     *B.Id, *CpVec(B.Loc), B.DiameterUU, B.Strength, B.Softness));
  }
  Runtime.Status = TEXT("ok");
  const FVector2D Cut = Spec.CutHalf(FrameHalf);
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW concept-paste status=ok profile=%s sheet=%d sea=%d lights=%d blobs=%d flows=%d seaFlow=%d flowFrozen=%d water=%d grade=%s gainLinear=%.4f emissiveScale=%.4f(%s) devignette=%.3f fit=(%.4f,%.4f,%.4f)^(%.4f,%.4f,%.4f) calib=%d camera=(%.1f,%.1f,%.1f) pitch=%.0f yaw=%.0f hfov=%.0f size=%dx%d homography=%s rectA=(%.1f,%.1f,%.1f,%.1f) rectB=(%.1f,%.1f,%.1f,%.1f) cut=(%.2f,%.2f) lit=0 lumenGI=0 shadow=0"),
      *Runtime.ProfileId, Runtime.SheetParts, Runtime.SeaParts, Runtime.Lights, Runtime.Blobs, Spec.Flows.Num(),
      Spec.SeaFlow.bSet ? 1 : 0, bFreezeFlow ? 1 : 0, Assets.Water ? 1 : 0, *Runtime.Grade,
      Spec.GainLinear, EmissiveScale, *Runtime.EmissiveScaleSource, Spec.Devignette, Spec.FitScale.X, Spec.FitScale.Y, Spec.FitScale.Z,
      Spec.FitPower.X, Spec.FitPower.Y, Spec.FitPower.Z, bCalib ? 1 : 0, Spec.Camera.Location().X,
      Spec.Camera.Location().Y, Spec.Camera.Location().Z, Spec.Camera.PitchDeg, Spec.Camera.YawDeg, Spec.Camera.HFovDeg,
      Spec.Camera.SizePx.X, Spec.Camera.SizePx.Y, Spec.Homography.IsIdentity() ? TEXT("identity") : TEXT("registered"),
      Spec.RectA.X, Spec.RectA.Y, Spec.RectA.Z, Spec.RectA.W, Spec.RectB.X, Spec.RectB.Y, Spec.RectB.Z, Spec.RectB.W, Cut.X,
      Cut.Y));
}

void ApplyHides(const FS08ConceptHide& Hide, const FS08EnvLayoutRuntime& Env,
                const TArray<TObjectPtr<UStaticMeshComponent>>& EnvProps,
                const TArray<TObjectPtr<UPointLightComponent>>& EnvLights, UExponentialHeightFogComponent* Fog,
                FS08ConceptPasteRuntime& Runtime) {
  Runtime.HiddenProps = Runtime.HiddenFx = Runtime.HiddenLights = 0;
  Runtime.HiddenGround = Runtime.HiddenSea = Runtime.HiddenWaterfalls = 0;
  Runtime.bHidFog = false;
  auto HideOne = [&Runtime](USceneComponent* C) {
    if (!C) return false;
    if (C->IsVisible()) C->SetVisibility(false);
    Runtime.Hidden.AddUnique(C);
    return true;
  };
  TSet<FString> HiddenPropIds;
  if (Hide.bBaseProps) {
    for (int32 I = 0; I < EnvProps.Num(); ++I) {
      const FString Id = Env.Stats.PropComponentIds.IsValidIndex(I) ? Env.Stats.PropComponentIds[I] : FString();
      if (Env.Layout.OverlayPropIds.Contains(Id)) continue;  // a concept detail (added / replaced by the overlay)
      if (HideOne(EnvProps[I])) {
        ++Runtime.HiddenProps;
        HiddenPropIds.Add(Id);
      }
    }
  }
  if (Hide.bBaseFx) {
    // an fx anchored on a hidden base prop goes with it (a fire over a painted-over campfire); free fx (fireflies) are
    // the overlay's call (remove / replace), as are the fx the overlay added or replaced
    for (int32 I = 0; I < Env.Fx.Num(); ++I) {
      const FString Id = Env.FxStats.FxComponentIds.IsValidIndex(I) ? Env.FxStats.FxComponentIds[I] : FString();
      if (Env.Layout.OverlayFxIds.Contains(Id)) continue;
      const FS08EnvFx* Fx = Env.Layout.Fx.FindByPredicate([&Id](const FS08EnvFx& F) { return F.Id == Id; });
      if (!Fx || Fx->Anchor.IsEmpty() || !HiddenPropIds.Contains(Fx->Anchor)) continue;
      Runtime.HiddenFx += HideOne(Env.Fx[I].Get()) ? 1 : 0;
    }
  }
  if (Hide.bLayoutLights) {
    for (UPointLightComponent* L : EnvLights) Runtime.HiddenLights += HideOne(L) ? 1 : 0;
  }
  for (const TWeakObjectPtr<UStaticMeshComponent>& G : Env.Ground) {
    UStaticMeshComponent* C = G.Get();
    if (!C) continue;
    const FString Kind = GroundKindOf(C->GetName());
    if (Kind == TEXT("ground") && Hide.bGround) Runtime.HiddenGround += HideOne(C) ? 1 : 0;
    if (Kind == TEXT("sea") && Hide.bSea) Runtime.HiddenSea += HideOne(C) ? 1 : 0;
    if (Kind == TEXT("waterfalls") && Hide.bWaterfalls) Runtime.HiddenWaterfalls += HideOne(C) ? 1 : 0;
  }
  if (Hide.bFog && Fog) Runtime.bHidFog = HideOne(Fog);
  Runtime.Hidden.RemoveAll([](const TWeakObjectPtr<USceneComponent>& W) { return !W.IsValid(); });
}

int32 RestoreHides(FS08ConceptPasteRuntime& Runtime) {
  int32 Count = 0;
  for (const TWeakObjectPtr<USceneComponent>& W : Runtime.Hidden) {
    if (USceneComponent* C = W.Get()) {
      C->SetVisibility(true);
      ++Count;
    }
  }
  Runtime.Hidden.Reset();
  Runtime.HiddenProps = Runtime.HiddenFx = Runtime.HiddenLights = 0;
  Runtime.HiddenGround = Runtime.HiddenSea = Runtime.HiddenWaterfalls = 0;
  Runtime.bHidFog = Runtime.bHidTray = Runtime.bHidBackdrop = false;
  return Count;
}
}  // namespace S08ConceptPaste

// ---- animation ---------------------------------------------------------------------------------------------------

US08ConceptPasteAnimComponent::US08ConceptPasteAnimComponent() {
  PrimaryComponentTick.bCanEverTick = true;
  PrimaryComponentTick.bStartWithTickEnabled = true;
}

void US08ConceptPasteAnimComponent::AddFlicker(UPointLightComponent* Light, const FS08ConceptLight& Spec) {
  if (!Light || Spec.FlickerAmp <= 0.0f || Spec.FlickerHz <= 0.0f) return;
  FFlicker& F = Flickers.AddDefaulted_GetRef();
  F.Light = Light;
  F.Spec = Spec;
  F.BaseIntensity = Light->Intensity;
}

void US08ConceptPasteAnimComponent::AddSway(USceneComponent* Prop, const FS08ConceptAnim& Spec) {
  if (!Prop || Spec.SwayDeg <= 0.0f || Spec.SwayHz <= 0.0f) return;
  FSway& S = Sways.AddDefaulted_GetRef();
  S.Prop = Prop;
  S.Spec = Spec;
  S.BaseRotation = Prop->GetRelativeRotation();
}

void US08ConceptPasteAnimComponent::AddWind(UStaticMeshComponent* Prop) {
  if (!Prop) return;
  for (int32 Slot = 0; Slot < Prop->GetNumMaterials(); ++Slot) {
    UMaterialInterface* Mat = Prop->GetMaterial(Slot);
    if (!Mat) continue;
    UMaterialInstanceDynamic* Mid = Cast<UMaterialInstanceDynamic>(Mat);
    if (!Mid) Mid = Prop->CreateDynamicMaterialInstance(Slot, Mat);
    if (Mid) Mid->SetScalarParameterValue(S08ConceptPasteSpec::WindLiveParamName, 1.0f);
  }
  Winds.Add(Prop);
}

void US08ConceptPasteAnimComponent::RestoreBase() {
  for (const TWeakObjectPtr<UStaticMeshComponent>& W : Winds) {
    UStaticMeshComponent* P = W.Get();
    if (!P) continue;
    for (int32 Slot = 0; Slot < P->GetNumMaterials(); ++Slot) {
      if (UMaterialInstanceDynamic* Mid = Cast<UMaterialInstanceDynamic>(P->GetMaterial(Slot))) {
        Mid->SetScalarParameterValue(S08ConceptPasteSpec::WindLiveParamName, 0.0f);
      }
    }
  }
  for (const FFlicker& F : Flickers) {
    if (UPointLightComponent* L = F.Light.Get()) L->SetIntensity(F.BaseIntensity);
  }
  for (const FSway& S : Sways) {
    if (USceneComponent* P = S.Prop.Get()) P->SetRelativeRotation(S.BaseRotation);
  }
}

void US08ConceptPasteAnimComponent::TickComponent(float DeltaTime, ELevelTick TickType,
                                                  FActorComponentTickFunction* ThisTickFunction) {
  Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
  const UWorld* World = GetWorld();
  const double T = World ? World->GetTimeSeconds() : 0.0;
  for (const FFlicker& F : Flickers) {
    if (UPointLightComponent* L = F.Light.Get()) L->SetIntensity(F.BaseIntensity * S08ConceptPaste::FlickerScale(F.Spec, T));
  }
  for (const FSway& S : Sways) {
    USceneComponent* P = S.Prop.Get();
    if (!P) continue;
    const float Angle = FMath::DegreesToRadians(S08ConceptPaste::SwayAngleDeg(S.Spec, T));
    const FQuat Delta(S.Spec.bAxisY ? FVector::YAxisVector : FVector::XAxisVector, Angle);
    P->SetRelativeRotation(S.BaseRotation.Quaternion() * Delta);
  }
}

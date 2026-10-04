#include "S08Diorama.h"

#include "Engine/StaticMesh.h"
#include "HAL/PlatformProperties.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/PackageName.h"
#include "Misc/Parse.h"
#include "UObject/UObjectGlobals.h"

namespace S08Diorama {
namespace {
// -1 = read the command line, 0/1 = automation override.
int32 GFlagOverride = -1;
}  // namespace

bool FlagEnabled() {
  if (GFlagOverride >= 0) return GFlagOverride == 1;
  // ART-DEFAULT: on unless rolled back; -ArtPreviewDiorama (FlagName) is not read any more (no-op alias).
  return Decide(LegacyRequested());
}

bool LegacyRequested() { return FParse::Param(FCommandLine::Get(), LegacyFlagName); }

void SetFlagOverrideForTest(bool bEnabled) { GFlagOverride = bEnabled ? 1 : 0; }

void ResetFlagOverrideForTest() { GFlagOverride = -1; }

FTrayFit FitTray(const FVector2D& BoardHalf) {
  FTrayFit Fit;
  const FVector2D Want(BoardHalf.X + RimUU, BoardHalf.Y + RimUU);
  if (BoardHalf.Y >= BoardHalf.X) {
    // yaw -90: mesh X -> world -Y, mesh Y -> world +X.
    Fit.YawDeg = -90.0f;
    Fit.Scale = FVector(Want.Y / MeshHalfX, Want.X / MeshHalfY, 1.0f);
  } else {
    Fit.YawDeg = 0.0f;
    Fit.Scale = FVector(Want.X / MeshHalfX, Want.Y / MeshHalfY, 1.0f);
  }
  Fit.WorldHalf = Want;
  return Fit;
}

FTrayFit FitTray(const FVector2D& BoardHalf, const FVector2D& Offset) {
  // Grow the fitted half extent by |offset| per axis, then move the pivot by the offset: the board frame stays
  // inside the tray with at least RimUU on every side (ENV-O8 T1 placeholder; a zero offset = FitTray(BoardHalf)).
  FTrayFit Fit = FitTray(FVector2D(BoardHalf.X + FMath::Abs(Offset.X), BoardHalf.Y + FMath::Abs(Offset.Y)));
  Fit.Location = Offset;
  return Fit;
}

FTrayFit FitTrayT2(const FVector2D& LayoutHalf, float OffsetY, float& OutMismatchUU) {
  // ENV-U10 T2: the mesh already IS the tray (built to the shared extents in Blender): it only moves, never scales.
  FTrayFit Fit;
  Fit.YawDeg = 0.0f;
  Fit.Scale = FVector::OneVector;
  Fit.WorldHalf = FVector2D(T2TopHalfX, T2TopHalfY);
  Fit.Location = FVector2D(0.0, OffsetY);
  OutMismatchUU = static_cast<float>(
      FMath::Max(FMath::Abs(LayoutHalf.X - T2TopHalfX), FMath::Abs(LayoutHalf.Y - T2TopHalfY)));
  return Fit;
}

float T2MinApronUU(const FVector2D& FrameHalf, float OffsetY) {
  const double Side = T2TopHalfX - FrameHalf.X;
  const double Far = (T2TopHalfY - OffsetY) - FrameHalf.Y;   // far edge at OffsetY - halfY (-Y)
  const double Near = (T2TopHalfY + OffsetY) - FrameHalf.Y;  // near edge at OffsetY + halfY (+Y)
  return static_cast<float>(FMath::Min(Side, FMath::Min(Far, Near)));
}

// ---------------------------------------------------------------------------------------------- P5 track B: T2b
namespace {
/** Uncooked runs (editor, automation) ask the package first: a tray that was never imported reaches no loader warning.
 *  Cooked runs load directly (the folders are always cooked; an absent asset just returns null). */
bool TrayPackageMayExist(const TCHAR* PackagePath) {
  return FPlatformProperties::RequiresCookedData() || FPackageName::DoesPackageExist(FString(PackagePath));
}

template <typename T>
T* TrayLoad(const FString& PackagePath) {
  return TrayPackageMayExist(*PackagePath) ? LoadObject<T>(nullptr, *PackagePath, nullptr, LOAD_NoWarn) : nullptr;
}
}  // namespace

const TCHAR* TrayT2KindName(ETrayT2Kind Kind) {
  switch (Kind) {
    case ETrayT2Kind::T2:
      return TEXT("T2");
    case ETrayT2Kind::T2b:
      return TEXT("T2b");
    default:
      return TEXT("none");
  }
}

ETrayT2Kind PickTrayT2(bool bT2bInBuild, bool bT2InBuild) {
  if (bT2bInBuild) return ETrayT2Kind::T2b;
  return bT2InBuild ? ETrayT2Kind::T2 : ETrayT2Kind::None;
}

const TCHAR* TrayT2MeshPath(ETrayT2Kind Kind) {
  switch (Kind) {
    case ETrayT2Kind::T2:
      return T2MeshPath;
    case ETrayT2Kind::T2b:
      return T2bMeshPath;
    default:
      return nullptr;
  }
}

const TCHAR* TrayT2MaterialPath(ETrayT2Kind Kind) {
  switch (Kind) {
    case ETrayT2Kind::T2:
      return T2MaterialPath;
    case ETrayT2Kind::T2b:
      return T2bMaterialPath;
    default:
      return nullptr;
  }
}

FString T2bMapMaterialPath(const FString& MapName) {
  if (MapName.IsEmpty()) return FString();
  for (const TCHAR C : MapName) {
    if (!(FChar::IsAlnum(C) || C == TEXT('_'))) return FString();
  }
  // "sarpedon" (S08EnvLayout::MapKeyOf) and "Sarpedon" (FS08MapImageSpec::Name) name the same MI
  FString Leaf = MapName.ToLower();
  Leaf[0] = FChar::ToUpper(Leaf[0]);
  return FString(T2bMapMaterialPrefix) + Leaf;
}

ETrayT2Kind TrayT2KindOf(const UStaticMesh* Mesh) {
  if (!Mesh) return ETrayT2Kind::None;
  const FString Path = Mesh->GetPathName();
  // package paths followed by '.' + object name: ".../T2b/SM_TableBase_T2b.SM_TableBase_T2b"
  if (Path.StartsWith(FString(T2bMeshPath) + TEXT("."))) return ETrayT2Kind::T2b;
  if (Path.StartsWith(FString(T2MeshPath) + TEXT("."))) return ETrayT2Kind::T2;
  return ETrayT2Kind::None;
}

UMaterialInterface* LoadTrayT2Material(ETrayT2Kind Kind, const FString& MapName, FString* OutPath) {
  if (OutPath) OutPath->Reset();
  TArray<FString> Candidates;
  if (Kind == ETrayT2Kind::T2b) {
    const FString MapMi = T2bMapMaterialPath(MapName);
    if (!MapMi.IsEmpty()) Candidates.Add(MapMi);
  }
  if (const TCHAR* Shared = TrayT2MaterialPath(Kind)) Candidates.Add(Shared);
  for (const FString& Path : Candidates) {
    if (UMaterialInterface* Mi = TrayLoad<UMaterialInterface>(Path)) {
      if (OutPath) *OutPath = Path;
      return Mi;
    }
  }
  return nullptr;
}

FTrayT2Assets LoadTrayT2(const FString& MapName) {
  FTrayT2Assets Out;
  for (const ETrayT2Kind Kind : {ETrayT2Kind::T2b, ETrayT2Kind::T2}) {
    UStaticMesh* Mesh = TrayLoad<UStaticMesh>(TrayT2MeshPath(Kind));
    if (!Mesh) {
      // in the build but not loadable (uncooked: the package exists) -> traced, T2 is tried next
      if (Kind == ETrayT2Kind::T2b && !FPlatformProperties::RequiresCookedData() &&
          FPackageName::DoesPackageExist(FString(T2bMeshPath))) {
        Out.bT2bFailed = true;
      }
      continue;
    }
    Out.Kind = Kind;
    Out.Mesh = Mesh;
    Out.Material = LoadTrayT2Material(Kind, MapName, &Out.MaterialPath);
    break;
  }
  return Out;
}

FString TrayT2LoadTraceLine(const FTrayT2Assets& Assets) {
  const TCHAR* Path = Assets.Mesh ? TrayT2MeshPath(Assets.Kind) : T2bMeshPath;
  return FString::Printf(TEXT("ARTPREVIEW diorama tray-t2 %s mesh=%s mi=%s%s kind=%s%s"),
                         Assets.Mesh ? TEXT("loaded") : TEXT("absent"), Path,
                         Assets.Material ? *Assets.Material->GetName() : TEXT("missing(mesh default)"),
                         Assets.Mesh ? TEXT("") : TEXT(" (import: tools/art/env_kit/ue_import_tray_t2.py) -> T1 placeholder"),
                         TrayT2KindName(Assets.Kind), Assets.bT2bFailed ? TEXT(" t2b=failed") : TEXT(""));
}

}  // namespace S08Diorama

#include "S08EnvGround.h"

#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Actor.h"
#include "HAL/PlatformProperties.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/PackageName.h"
#include "UObject/UObjectGlobals.h"

// Helpers live in a NAMED namespace (unity builds merge this file with S08EnvLayout.cpp / S08BoardArt.cpp, whose
// helper names overlap).
namespace S08EnvGroundPrivate {
/** A JSON number (never a numeric string). */
bool GroundNumber(const TSharedPtr<FJsonValue>& Value, double& Out) {
  if (!Value.IsValid() || Value->Type != EJson::Number) return false;
  Out = Value->AsNumber();
  return FMath::IsFinite(Out);
}

/** Optional number field: absent / null -> true (Out unchanged); present but not a number -> false. */
bool GroundOptionalNumber(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, double& Out) {
  const TSharedPtr<FJsonValue> Value = Obj->TryGetField(Field);
  if (!Value.IsValid() || Value->Type == EJson::Null) return true;
  return GroundNumber(Value, Out);
}

/** Package path "/Game/..." or "/Engine/..." ([A-Za-z0-9_/-]), optionally ".<ObjectName>" (the S08EnvLayout rule). */
bool GroundIsPackagePath(const FString& Path) {
  if (!(Path.StartsWith(TEXT("/Game/")) || Path.StartsWith(TEXT("/Engine/")))) return false;
  if (Path.Contains(TEXT("//")) || Path.EndsWith(TEXT("/"))) return false;
  int32 Dots = 0;
  for (const TCHAR C : Path) {
    if (C == TEXT('.')) {
      ++Dots;
      continue;
    }
    if (!(FChar::IsAlnum(C) || C == TEXT('_') || C == TEXT('/') || C == TEXT('-'))) return false;
  }
  return Dots == 0 || (Dots == 1 && !Path.EndsWith(TEXT(".")));
}

FString GroundPackageOf(const FString& Path) {
  int32 Dot = INDEX_NONE;
  return Path.FindChar(TEXT('.'), Dot) ? Path.Left(Dot) : Path;
}

FString GroundBox(const FBox2D& B) {
  return B.bIsValid ? FString::Printf(TEXT("(%.1f,%.1f)..(%.1f,%.1f)"), B.Min.X, B.Min.Y, B.Max.X, B.Max.Y)
                    : FString(TEXT("-"));
}
}  // namespace S08EnvGroundPrivate

namespace S08EnvGround {

bool ParseJson(const TSharedPtr<FJsonObject>& Obj, FS08EnvGround& Out, TArray<FString>& OutErrors) {
  using namespace S08EnvGroundPrivate;
  Out = FS08EnvGround();
  if (!Obj.IsValid()) {
    OutErrors.Add(TEXT("ground is not an object"));
    return false;
  }
  const int32 Before = OutErrors.Num();
  FS08EnvGround G;
  if (!Obj->TryGetStringField(TEXT("mode"), G.Mode) || G.Mode != S08EnvGroundSpec::RuntimeMode) {
    OutErrors.Add(FString::Printf(TEXT("ground: mode '%s' is not '%s' (four engine-plane strips; a mesh mode is not "
                                       "supported, see S08EnvGround.h)"),
                                  *G.Mode, S08EnvGroundSpec::RuntimeMode));
  }
  if (!Obj->TryGetStringField(TEXT("material"), G.Material) || !GroundIsPackagePath(G.Material)) {
    OutErrors.Add(FString::Printf(TEXT("ground: material '%s' is not a /Game/ or /Engine/ package path"), *G.Material));
  }
  double Z = S08EnvGroundSpec::DefaultZ, Overlap = S08EnvGroundSpec::DefaultFrameOverlapUU, Inset = 0.0;
  if (!GroundOptionalNumber(Obj, TEXT("z"), Z) || Z <= S08EnvGroundSpec::MinZ || Z >= S08EnvGroundSpec::MaxZ) {
    OutErrors.Add(FString::Printf(TEXT("ground: z must be a number in (%.1f, %.1f) - above the tray top, below the map"),
                                  S08EnvGroundSpec::MinZ, S08EnvGroundSpec::MaxZ));
  }
  if (!GroundOptionalNumber(Obj, TEXT("frameOverlapUU"), Overlap) || Overlap < 0.0 ||
      Overlap > S08EnvGroundSpec::MaxFrameOverlapUU) {
    OutErrors.Add(FString::Printf(TEXT("ground: frameOverlapUU must be a number in [0, %.0f]"),
                                  S08EnvGroundSpec::MaxFrameOverlapUU));
  }
  if (!GroundOptionalNumber(Obj, TEXT("insetUU"), Inset) || Inset < 0.0 || Inset > S08EnvGroundSpec::MaxInsetUU) {
    OutErrors.Add(FString::Printf(TEXT("ground: insetUU must be a number in [0, %.0f]"), S08EnvGroundSpec::MaxInsetUU));
  }
  G.Z = static_cast<float>(Z);
  G.FrameOverlapUU = static_cast<float>(Overlap);
  G.InsetUU = static_cast<float>(Inset);
  const TSharedPtr<FJsonValue> RectValue = Obj->TryGetField(TEXT("splatRect"));
  if (RectValue.IsValid() && RectValue->Type != EJson::Null) {
    const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
    double N[4] = {0.0, 0.0, 0.0, 0.0};
    bool bOk = RectValue->TryGetArray(Values) && Values && Values->Num() == 4;
    for (int32 I = 0; bOk && I < 4; ++I) bOk = GroundNumber((*Values)[I], N[I]);
    if (!bOk || N[2] <= N[0] || N[3] <= N[1]) {
      OutErrors.Add(TEXT("ground: splatRect must be [minX, minY, maxX, maxY] numbers with max > min"));
    } else {
      G.bSplatRect = true;
      G.SplatRect = FBox2D(FVector2D(N[0], N[1]), FVector2D(N[2], N[3]));
    }
  }
  if (OutErrors.Num() != Before) return false;
  G.bSet = true;
  Out = G;
  return true;
}

FBox2D OuterRect(const FBox2D& TrayTop, float InsetUU) {
  if (!TrayTop.bIsValid) return FBox2D(ForceInit);
  return FBox2D(TrayTop.Min + FVector2D(InsetUU, InsetUU), TrayTop.Max - FVector2D(InsetUU, InsetUU));
}

FBox2D HoleRect(const FVector2D& FrameHalf, float FrameOverlapUU) {
  const FVector2D Half(FMath::Max(FrameHalf.X - FrameOverlapUU, 0.0), FMath::Max(FrameHalf.Y - FrameOverlapUU, 0.0));
  return FBox2D(-Half, Half);
}

TArray<FBox2D> Strips(const FBox2D& Outer, const FBox2D& Hole) {
  TArray<FBox2D> Out;
  const double Min = S08EnvGroundSpec::MinStripUU;
  if (!Outer.bIsValid || Outer.Max.X - Outer.Min.X <= Min || Outer.Max.Y - Outer.Min.Y <= Min) return Out;
  if (!Hole.bIsValid || Hole.Max.X <= Outer.Min.X || Hole.Min.X >= Outer.Max.X || Hole.Max.Y <= Outer.Min.Y ||
      Hole.Min.Y >= Outer.Max.Y) {
    Out.Add(Outer);  // the hole does not cut the outer rectangle
    return Out;
  }
  const double HX0 = FMath::Max(Hole.Min.X, Outer.Min.X), HX1 = FMath::Min(Hole.Max.X, Outer.Max.X);
  const double HY0 = FMath::Max(Hole.Min.Y, Outer.Min.Y), HY1 = FMath::Min(Hole.Max.Y, Outer.Max.Y);
  auto Add = [&Out, Min](double X0, double Y0, double X1, double Y1) {
    if (X1 - X0 > Min && Y1 - Y0 > Min) Out.Add(FBox2D(FVector2D(X0, Y0), FVector2D(X1, Y1)));
  };
  Add(Outer.Min.X, Outer.Min.Y, Outer.Max.X, HY0);  // N: the far side, full width
  Add(Outer.Min.X, HY1, Outer.Max.X, Outer.Max.Y);  // S: the near side, full width
  Add(Outer.Min.X, HY0, HX0, HY1);                  // W: between N and S
  Add(HX1, HY0, Outer.Max.X, HY1);                  // E
  return Out;
}

FTransform StripTransform(const FBox2D& Strip, float Z) {
  const FVector2D C = Strip.GetCenter();
  const FVector2D Size = Strip.GetSize();
  return FTransform(FRotator::ZeroRotator, FVector(C.X, C.Y, Z),
                    FVector(Size.X / S08EnvGroundSpec::PlaneSizeUU, Size.Y / S08EnvGroundSpec::PlaneSizeUU, 1.0));
}

FLinearColor RectParam(const FBox2D& Rect) {
  const FVector2D Size = Rect.GetSize();
  return FLinearColor(static_cast<float>(Rect.Min.X), static_cast<float>(Rect.Min.Y), static_cast<float>(Size.X),
                      static_cast<float>(Size.Y));
}

FS08EnvGroundStats Spawn(const FS08EnvGround& Ground, AActor& Owner, USceneComponent* Parent, const FBox2D& TrayTop,
                         const FVector2D& FrameHalf, TArray<TWeakObjectPtr<UStaticMeshComponent>>& Out) {
  using namespace S08EnvGroundPrivate;
  FS08EnvGroundStats S;
  if (!Ground.bSet) return S;  // status 'off'
  if (!TrayTop.bIsValid) {
    S.Status = TEXT("no-tray");
    return S;
  }
  S.Outer = OuterRect(TrayTop, Ground.InsetUU);
  S.Hole = HoleRect(FrameHalf, Ground.FrameOverlapUU);
  S.bSplatCoversOuter = !Ground.bSplatRect || (Ground.SplatRect.IsInsideOrOn(S.Outer.Min) &&
                                               Ground.SplatRect.IsInsideOrOn(S.Outer.Max));
  const TArray<FBox2D> Rects = Strips(S.Outer, S.Hole);
  if (Rects.Num() == 0) {
    S.Status = TEXT("no-strips");
    return S;
  }
  UStaticMesh* Plane = LoadObject<UStaticMesh>(nullptr, S08EnvGroundSpec::PlaneMeshPath, nullptr, LOAD_NoWarn);
  if (!Plane) {
    S.Status = TEXT("missing-plane");
    return S;
  }
  // Uncooked runs (editor, automation) ask the package first: a ground that was never imported reaches no loader
  // warning (the automation log collects them). Cooked runs load directly, as the props of S08EnvLayout do.
  const bool bMayExist =
      FPlatformProperties::RequiresCookedData() || FPackageName::DoesPackageExist(GroundPackageOf(Ground.Material));
  UMaterialInterface* Material =
      bMayExist ? LoadObject<UMaterialInterface>(nullptr, *Ground.Material, nullptr, LOAD_NoWarn) : nullptr;
  if (!Material) {
    S.Status = TEXT("missing-material");
    return S;
  }
  S.MaterialName = Material->GetName();
  USceneComponent* Attach = Parent ? Parent : Owner.GetRootComponent();
  for (int32 I = 0; I < Rects.Num(); ++I) {
    const FBox2D& R = Rects[I];
    const FName Name = MakeUniqueObjectName(&Owner, UStaticMeshComponent::StaticClass(),
                                            FName(*FString::Printf(TEXT("EnvGround_%d"), I)));
    UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(&Owner, Name);
    C->SetupAttachment(Attach);
    C->SetStaticMesh(Plane);
    // A flat decor layer: never a click / cursor surface (the map pick box is), never navigation, no shadow of its own.
    C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    C->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
    C->SetGenerateOverlapEvents(false);
    C->SetCanEverAffectNavigation(false);
    C->SetCastShadow(false);
    C->SetRelativeTransform(StripTransform(R, Ground.Z));
    UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(Material, C);
    if (Mid) {
      Mid->SetVectorParameterValue(FName(S08EnvGroundSpec::ParamGroundStrip), RectParam(R));
      if (Ground.bSplatRect) {
        Mid->SetVectorParameterValue(FName(S08EnvGroundSpec::ParamSplatRect), RectParam(Ground.SplatRect));
      }
      C->SetMaterial(0, Mid);
    } else {
      C->SetMaterial(0, Material);
    }
    C->RegisterComponent();
    Out.Emplace(C);
    ++S.Strips;
    S.AreaUU2 += R.GetArea();
  }
  S.Status = TEXT("ok");
  return S;
}

int32 Clear(TArray<TWeakObjectPtr<UStaticMeshComponent>>& Components) {
  int32 Count = 0;
  for (const TWeakObjectPtr<UStaticMeshComponent>& Weak : Components) {
    if (UStaticMeshComponent* C = Weak.Get()) {
      C->DestroyComponent();
      ++Count;
    }
  }
  Components.Reset();
  return Count;
}

FString TraceLine(const FString& MapKey, const FS08EnvGround& Ground, const FS08EnvGroundStats& Stats) {
  using namespace S08EnvGroundPrivate;
  return FString::Printf(
      TEXT("ARTPREVIEW envlayout ground map=%s mode=%s strips=%d material=%s z=%.1f outer=%s hole=%s splatRect=%s splatCovers=%d areaUU2=%.0f status=%s"),
      MapKey.IsEmpty() ? TEXT("-") : *MapKey, Ground.Mode.IsEmpty() ? TEXT("-") : *Ground.Mode, Stats.Strips,
      Stats.MaterialName.IsEmpty() ? *Ground.Material : *Stats.MaterialName, Ground.Z, *GroundBox(Stats.Outer),
      *GroundBox(Stats.Hole), Ground.bSplatRect ? *GroundBox(Ground.SplatRect) : TEXT("-"),
      Stats.bSplatCoversOuter ? 1 : 0, Stats.AreaUU2, *Stats.Status);
}

}  // namespace S08EnvGround

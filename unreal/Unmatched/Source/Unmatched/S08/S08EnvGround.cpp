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
#include "Math/RotationMatrix.h"
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

/** Required number field: present and a JSON number. */
bool GroundRequiredNumber(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, double& Out) {
  return GroundNumber(Obj->TryGetField(Field), Out);
}

/** An id as a component-name fragment ([A-Za-z0-9_]). */
FString GroundSafeName(const FString& Id) {
  FString S = Id;
  for (int32 I = 0; I < S.Len(); ++I) {
    if (!FChar::IsAlnum(S[I])) S[I] = TEXT('_');
  }
  return S;
}

/** N JSON numbers in an array (never numeric strings). */
bool GroundNumbers(const TSharedPtr<FJsonValue>& Value, int32 N, double* Out) {
  const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
  if (!Value.IsValid() || !Value->TryGetArray(Values) || !Values || Values->Num() != N) return false;
  for (int32 I = 0; I < N; ++I) {
    if (!GroundNumber((*Values)[I], Out[I])) return false;
  }
  return true;
}

/** Optional package-path string: absent / null -> true (Out empty); present -> a valid package path. */
bool GroundOptionalPackage(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, FString& Out) {
  Out.Reset();
  const TSharedPtr<FJsonValue> Value = Obj->TryGetField(Field);
  if (!Value.IsValid() || Value->Type == EJson::Null) return true;
  return Value->TryGetString(Out) && GroundIsPackagePath(Out);
}

/** "loc" [x, y, z] with |x|, |y| <= MeshMaxAbsXYUU and MinZ <= z <= MaxZ (bMaxExclusive: z < MaxZ) + "yawDeg". */
bool GroundParsePlacement(const TSharedPtr<FJsonObject>& Obj, const FString& Where, double MinZ, double MaxZ,
                          bool bMaxExclusive, FVector& OutLoc, float& OutYaw, TArray<FString>& OutErrors) {
  const int32 Before = OutErrors.Num();
  double L[3] = {0.0, 0.0, 0.0};
  const double MaxXY = S08EnvGroundSpec::MeshMaxAbsXYUU;
  if (!GroundNumbers(Obj->TryGetField(TEXT("loc")), 3, L) || FMath::Abs(L[0]) > MaxXY || FMath::Abs(L[1]) > MaxXY ||
      L[2] < MinZ || (bMaxExclusive ? L[2] >= MaxZ : L[2] > MaxZ)) {
    OutErrors.Add(FString::Printf(TEXT("%s.loc must be [x, y, z] numbers with |x|, |y| <= %.0f and z in [%.0f, %.0f%s"),
                                  *Where, MaxXY, MinZ, MaxZ, bMaxExclusive ? TEXT(")") : TEXT("]")));
  }
  double Yaw = 0.0;
  if (!GroundOptionalNumber(Obj, TEXT("yawDeg"), Yaw) || FMath::Abs(Yaw) > S08EnvGroundSpec::MaxMeshYawDeg) {
    OutErrors.Add(FString::Printf(TEXT("%s.yawDeg must be a number in [-%.0f, %.0f]"), *Where,
                                  S08EnvGroundSpec::MaxMeshYawDeg, S08EnvGroundSpec::MaxMeshYawDeg));
  }
  OutLoc = FVector(L[0], L[1], L[2]);
  OutYaw = static_cast<float>(Yaw);
  return OutErrors.Num() == Before;
}

/** A card size [w, h] in (0, MaxMeshCardUU]. */
bool GroundCard(const TSharedPtr<FJsonValue>& Value, FVector2D& Out) {
  double C[2] = {0.0, 0.0};
  if (!GroundNumbers(Value, 2, C)) return false;
  const double Max = S08EnvGroundSpec::MaxMeshCardUU;
  if (C[0] <= 0.0 || C[0] > Max || C[1] <= 0.0 || C[1] > Max) return false;
  Out = FVector2D(C[0], C[1]);
  return true;
}

/** P5 track B: the optional "mesh" object of a waterfall entry (absent / null -> bSet false). */
void GroundParseFallMesh(const TSharedPtr<FJsonValue>& Value, const FString& Where, FS08EnvWaterfallMesh& Out,
                         TArray<FString>& OutErrors) {
  Out = FS08EnvWaterfallMesh();
  if (!Value.IsValid() || Value->Type == EJson::Null) return;
  const FString W = Where + TEXT(": mesh");
  const TSharedPtr<FJsonObject>* ObjPtr = nullptr;
  if (!Value->TryGetObject(ObjPtr) || !ObjPtr || !ObjPtr->IsValid()) {
    OutErrors.Add(W + TEXT(" is not an object"));
    return;
  }
  const TSharedPtr<FJsonObject>& Obj = *ObjPtr;
  const int32 Before = OutErrors.Num();
  FS08EnvWaterfallMesh M;
  if (!Obj->TryGetStringField(TEXT("sheet"), M.Sheet) || !GroundIsPackagePath(M.Sheet)) {
    OutErrors.Add(FString::Printf(TEXT("%s.sheet '%s' is not a /Game/ or /Engine/ package path"), *W, *M.Sheet));
  }
  for (const TPair<const TCHAR*, FString*>& Field :
       {TPair<const TCHAR*, FString*>(TEXT("foam"), &M.Foam), TPair<const TCHAR*, FString*>(TEXT("lip"), &M.Lip),
        TPair<const TCHAR*, FString*>(TEXT("lipMaterial"), &M.LipMaterial)}) {
    if (!GroundOptionalPackage(Obj, Field.Key, *Field.Value)) {
      OutErrors.Add(FString::Printf(TEXT("%s.%s is not a /Game/ or /Engine/ package path"), *W, Field.Key));
    }
  }
  if (!M.Lip.IsEmpty() && M.LipMaterial.IsEmpty()) OutErrors.Add(W + TEXT(": a lip needs its lipMaterial"));
  GroundParsePlacement(Obj, W, S08EnvGroundSpec::FallMeshMinZ, S08EnvGroundSpec::FallMeshMaxZ, false, M.Loc, M.YawDeg,
                       OutErrors);
  if (!GroundCard(Obj->TryGetField(TEXT("sheetCard")), M.SheetCard)) {
    OutErrors.Add(FString::Printf(TEXT("%s.sheetCard must be [w, h] numbers in (0, %.0f]"), *W,
                                  S08EnvGroundSpec::MaxMeshCardUU));
  }
  const TSharedPtr<FJsonValue> Foam = Obj->TryGetField(TEXT("foamCards"));
  if (Foam.IsValid() && Foam->Type != EJson::Null) {
    const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
    bool bOk = Foam->TryGetArray(Cards) && Cards && Cards->Num() <= S08EnvGroundSpec::MaxFoamCards;
    for (int32 I = 0; bOk && I < Cards->Num(); ++I) {
      FVector2D Card;
      bOk = GroundCard((*Cards)[I], Card);
      if (bOk) M.FoamCards.Add(Card);
    }
    if (!bOk) {
      OutErrors.Add(FString::Printf(TEXT("%s.foamCards must be <= %d pairs [w, h] in (0, %.0f]"), *W,
                                    S08EnvGroundSpec::MaxFoamCards, S08EnvGroundSpec::MaxMeshCardUU));
    }
  }
  if (OutErrors.Num() != Before) return;
  M.bSet = true;
  Out = M;
}

/** P5 track B: the optional "sea" object of the ground section (absent / null -> bSet false). */
void GroundParseSea(const TSharedPtr<FJsonValue>& Value, FS08EnvSea& Out, TArray<FString>& OutErrors) {
  Out = FS08EnvSea();
  if (!Value.IsValid() || Value->Type == EJson::Null) return;
  const TSharedPtr<FJsonObject>* ObjPtr = nullptr;
  if (!Value->TryGetObject(ObjPtr) || !ObjPtr || !ObjPtr->IsValid()) {
    OutErrors.Add(TEXT("ground: sea is not an object"));
    return;
  }
  const TSharedPtr<FJsonObject>& Obj = *ObjPtr;
  const int32 Before = OutErrors.Num();
  FS08EnvSea Sea;
  if (!Obj->TryGetStringField(TEXT("mesh"), Sea.Mesh) || !GroundIsPackagePath(Sea.Mesh)) {
    OutErrors.Add(FString::Printf(TEXT("ground: sea.mesh '%s' is not a /Game/ or /Engine/ package path"), *Sea.Mesh));
  }
  if (!Obj->TryGetStringField(TEXT("material"), Sea.Material) || !GroundIsPackagePath(Sea.Material)) {
    OutErrors.Add(FString::Printf(TEXT("ground: sea.material '%s' is not a /Game/ or /Engine/ package path"),
                                  *Sea.Material));
  }
  GroundParsePlacement(Obj, TEXT("ground: sea"), S08EnvGroundSpec::SeaMinZ, S08EnvGroundSpec::SeaMaxZ, true, Sea.Loc,
                       Sea.YawDeg, OutErrors);
  if (OutErrors.Num() != Before) return;
  Sea.bSet = true;
  Out = Sea;
}

/** The optional "waterfalls" array (P4): absent / null -> none; anything invalid adds 'ground: waterfalls...' errors. */
void GroundParseWaterfalls(const TSharedPtr<FJsonValue>& Value, TArray<FS08EnvWaterfall>& Out,
                           TArray<FString>& OutErrors) {
  if (!Value.IsValid() || Value->Type == EJson::Null) return;
  const TArray<TSharedPtr<FJsonValue>>* Items = nullptr;
  if (!Value->TryGetArray(Items) || !Items) {
    OutErrors.Add(TEXT("ground: waterfalls is not an array"));
    return;
  }
  if (Items->Num() > S08EnvGroundSpec::MaxWaterfalls) {
    OutErrors.Add(FString::Printf(TEXT("ground: waterfalls has %d entries (max %d)"), Items->Num(),
                                  S08EnvGroundSpec::MaxWaterfalls));
    return;
  }
  TSet<FString> Ids;
  for (int32 I = 0; I < Items->Num(); ++I) {
    const FString Where = FString::Printf(TEXT("ground: waterfalls[%d]"), I);
    const TSharedPtr<FJsonObject>* ObjPtr = nullptr;
    if (!(*Items)[I].IsValid() || !(*Items)[I]->TryGetObject(ObjPtr) || !ObjPtr || !ObjPtr->IsValid()) {
      OutErrors.Add(Where + TEXT(" is not an object"));
      continue;
    }
    const TSharedPtr<FJsonObject>& Obj = *ObjPtr;
    const int32 Before = OutErrors.Num();
    FS08EnvWaterfall F;
    if (!Obj->TryGetStringField(TEXT("id"), F.Id) || F.Id.IsEmpty() || Ids.Contains(F.Id)) {
      OutErrors.Add(FString::Printf(TEXT("%s: id '%s' is empty or a duplicate"), *Where, *F.Id));
    }
    Ids.Add(F.Id);
    if (!Obj->TryGetStringField(TEXT("material"), F.Material) || !GroundIsPackagePath(F.Material)) {
      OutErrors.Add(FString::Printf(TEXT("%s: material '%s' is not a /Game/ or /Engine/ package path"), *Where,
                                    *F.Material));
    }
    double X0 = 0.0, X1 = 0.0, Y = 0.0, Drop = 0.0;
    double TopZ = S08EnvGroundSpec::DefaultFallTopZ, Spill = 0.0;
    const double MaxXY = S08EnvGroundSpec::MaxFallAbsXYUU;
    if (!GroundRequiredNumber(Obj, TEXT("x0"), X0) || !GroundRequiredNumber(Obj, TEXT("x1"), X1) ||
        !GroundRequiredNumber(Obj, TEXT("y"), Y)) {
      OutErrors.Add(Where + TEXT(": x0 / x1 / y must be numbers"));
    } else if (X1 - X0 <= 0.0 || X1 - X0 > S08EnvGroundSpec::MaxFallWidthUU || FMath::Abs(X0) > MaxXY ||
               FMath::Abs(X1) > MaxXY || FMath::Abs(Y) > MaxXY) {
      OutErrors.Add(FString::Printf(TEXT("%s: x1 - x0 must be in (0, %.0f] and |x0|, |x1|, |y| <= %.0f"), *Where,
                                    S08EnvGroundSpec::MaxFallWidthUU, MaxXY));
    }
    if (!GroundRequiredNumber(Obj, TEXT("dropUU"), Drop) || Drop <= 0.0 || Drop > S08EnvGroundSpec::MaxFallDropUU) {
      OutErrors.Add(FString::Printf(TEXT("%s: dropUU must be a number in (0, %.0f]"), *Where,
                                    S08EnvGroundSpec::MaxFallDropUU));
    }
    if (!GroundOptionalNumber(Obj, TEXT("topZ"), TopZ) || TopZ < S08EnvGroundSpec::FallMinTopZ ||
        TopZ > S08EnvGroundSpec::FallMaxTopZ) {
      OutErrors.Add(FString::Printf(TEXT("%s: topZ must be a number in [%.0f, %.0f]"), *Where,
                                    S08EnvGroundSpec::FallMinTopZ, S08EnvGroundSpec::FallMaxTopZ));
    }
    if (!GroundOptionalNumber(Obj, TEXT("spillUU"), Spill) || Spill < 0.0 || Spill > S08EnvGroundSpec::MaxFallSpillUU) {
      OutErrors.Add(FString::Printf(TEXT("%s: spillUU must be a number in [0, %.0f]"), *Where,
                                    S08EnvGroundSpec::MaxFallSpillUU));
    }
    GroundParseFallMesh(Obj->TryGetField(TEXT("mesh")), Where, F.Mesh, OutErrors);
    if (OutErrors.Num() != Before) continue;
    F.X0 = static_cast<float>(X0);
    F.X1 = static_cast<float>(X1);
    F.Y = static_cast<float>(Y);
    F.TopZ = static_cast<float>(TopZ);
    F.DropUU = static_cast<float>(Drop);
    F.SpillUU = static_cast<float>(Spill);
    Out.Add(F);
  }
}

/** One decor component under the board actor (not registered yet): Mesh, NoCollision, no navigation, CastShadow as
 *  asked, the relative transform. */
UStaticMeshComponent* GroundNewComponent(AActor& Owner, USceneComponent* Attach, UStaticMesh* Mesh,
                                         const FString& BaseName, const FTransform& Relative, bool bCastShadow) {
  const FName Name = MakeUniqueObjectName(&Owner, UStaticMeshComponent::StaticClass(), FName(*BaseName));
  UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(&Owner, Name);
  C->SetupAttachment(Attach);
  C->SetStaticMesh(Mesh);
  // Decor: never a click / cursor surface (the map pick box is), never navigation.
  C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  C->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
  C->SetGenerateOverlapEvents(false);
  C->SetCanEverAffectNavigation(false);
  C->SetCastShadow(bCastShadow);
  C->SetRelativeTransform(Relative);
  return C;
}

/** Slot Slot of C <- a MID of Material filled by Params (the material itself when no MID can be made). */
template <typename FParams>
void GroundSetMid(UStaticMeshComponent* C, int32 Slot, UMaterialInterface* Material, const FParams& Params) {
  UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(Material, C);
  if (Mid) {
    Params(*Mid);
    C->SetMaterial(Slot, Mid);
  } else {
    C->SetMaterial(Slot, Material);
  }
}

void GroundRegister(UStaticMeshComponent* C, TArray<TWeakObjectPtr<UStaticMeshComponent>>& Out) {
  C->RegisterComponent();
  Out.Emplace(C);
}

/** Material slots of a mesh (at least 1). */
int32 GroundSlots(const UStaticMesh* Mesh) { return FMath::Max(Mesh ? Mesh->GetStaticMaterials().Num() : 0, 1); }

/** One decor plane under the board actor: the engine plane, NoCollision, no navigation, no shadow, a MID of Material
 *  (Params fills it). Registered and appended to Out. */
template <typename FParams>
UStaticMeshComponent* GroundAddPlane(AActor& Owner, USceneComponent* Attach, UStaticMesh* Plane,
                                     const FString& BaseName, const FTransform& Relative,
                                     UMaterialInterface* Material, const FParams& Params,
                                     TArray<TWeakObjectPtr<UStaticMeshComponent>>& Out) {
  // A flat decor layer: no shadow of its own.
  UStaticMeshComponent* C = GroundNewComponent(Owner, Attach, Plane, BaseName, Relative, false);
  GroundSetMid(C, 0, Material, Params);
  GroundRegister(C, Out);
  return C;
}

/** Uncooked runs (editor, automation) ask the package first: an asset that was never imported reaches no loader
 *  warning (the automation log collects them). Cooked runs load directly, as the props of S08EnvLayout do. */
UMaterialInterface* GroundLoadMaterial(const FString& Path) {
  const bool bMayExist =
      FPlatformProperties::RequiresCookedData() || FPackageName::DoesPackageExist(GroundPackageOf(Path));
  return bMayExist ? LoadObject<UMaterialInterface>(nullptr, *Path, nullptr, LOAD_NoWarn) : nullptr;
}

/** The same for the P5 lane K meshes (an empty path -> nullptr). */
UStaticMesh* GroundLoadMesh(const FString& Path) {
  if (Path.IsEmpty()) return nullptr;
  const bool bMayExist =
      FPlatformProperties::RequiresCookedData() || FPackageName::DoesPackageExist(GroundPackageOf(Path));
  return bMayExist ? LoadObject<UStaticMesh>(nullptr, *Path, nullptr, LOAD_NoWarn) : nullptr;
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
  GroundParseWaterfalls(Obj->TryGetField(TEXT("waterfalls")), G.Waterfalls, OutErrors);
  GroundParseSea(Obj->TryGetField(TEXT("sea")), G.Sea, OutErrors);
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

FTransform FallCardTransform(const FS08EnvWaterfall& Fall) {
  // plane normal (local +Z) -> +Y, local +X stays +X, local +Y -> -Z (MakeFromXZ: Y = Z ^ X)
  const FQuat Rotation = FRotationMatrix::MakeFromXZ(FVector(1.0, 0.0, 0.0), FVector(0.0, 1.0, 0.0)).ToQuat();
  const double Width = static_cast<double>(Fall.X1) - static_cast<double>(Fall.X0);
  return FTransform(Rotation,
                    FVector((static_cast<double>(Fall.X0) + Fall.X1) * 0.5, Fall.Y,
                            static_cast<double>(Fall.TopZ) - Fall.DropUU * 0.5),
                    FVector(Width / S08EnvGroundSpec::PlaneSizeUU, Fall.DropUU / S08EnvGroundSpec::PlaneSizeUU, 1.0));
}

FTransform FallSpillTransform(const FS08EnvWaterfall& Fall) {
  const double Width = static_cast<double>(Fall.X1) - static_cast<double>(Fall.X0);
  return FTransform(FQuat::Identity,
                    FVector((static_cast<double>(Fall.X0) + Fall.X1) * 0.5,
                            static_cast<double>(Fall.Y) - Fall.SpillUU * 0.5, Fall.TopZ),
                    FVector(Width / S08EnvGroundSpec::PlaneSizeUU, Fall.SpillUU / S08EnvGroundSpec::PlaneSizeUU, 1.0));
}

FLinearColor FallCardParam(const FS08EnvWaterfall& Fall, bool bSpill) {
  return FLinearColor(Fall.X1 - Fall.X0, bSpill ? Fall.SpillUU : Fall.DropUU,
                      bSpill ? S08EnvGroundSpec::FallKindSpill : S08EnvGroundSpec::FallKindCard, 0.0f);
}

FTransform MeshPieceTransform(const FVector& Loc, float YawDeg) {
  return FTransform(FRotator(0.0f, YawDeg, 0.0f), Loc, FVector::OneVector);
}

FLinearColor SheetCardParam(const FS08EnvWaterfallMesh& Mesh) {
  return FLinearColor(static_cast<float>(Mesh.SheetCard.X), static_cast<float>(Mesh.SheetCard.Y),
                      S08EnvGroundSpec::FallKindCard, S08EnvGroundSpec::FallFlipMesh);
}

FLinearColor FoamCardParam(const FS08EnvWaterfallMesh& Mesh, int32 Slot) {
  const FVector2D Card = Mesh.FoamCards.Num() > 0 ? Mesh.FoamCards[FMath::Clamp(Slot, 0, Mesh.FoamCards.Num() - 1)]
                                                  : FVector2D(Mesh.SheetCard.X, 70.0);
  return FLinearColor(static_cast<float>(Card.X), static_cast<float>(Card.Y), S08EnvGroundSpec::FallKindSpill,
                      S08EnvGroundSpec::FallFlipMesh);
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
  UMaterialInterface* Material = GroundLoadMaterial(Ground.Material);
  if (!Material) {
    S.Status = TEXT("missing-material");
    return S;
  }
  S.MaterialName = Material->GetName();
  USceneComponent* Attach = Parent ? Parent : Owner.GetRootComponent();
  for (int32 I = 0; I < Rects.Num(); ++I) {
    const FBox2D& R = Rects[I];
    GroundAddPlane(Owner, Attach, Plane, FString::Printf(TEXT("EnvGround_%d"), I), StripTransform(R, Ground.Z),
                   Material,
                   [&Ground, &R](UMaterialInstanceDynamic& Mid) {
                     Mid.SetVectorParameterValue(FName(S08EnvGroundSpec::ParamGroundStrip), RectParam(R));
                     if (Ground.bSplatRect) {
                       Mid.SetVectorParameterValue(FName(S08EnvGroundSpec::ParamSplatRect),
                                                   RectParam(Ground.SplatRect));
                     }
                   },
                   Out);
    ++S.Strips;
    S.AreaUU2 += R.GetArea();
  }
  // P4 waterfalls: the vertical card and the optional flat spill of every entry (the same engine plane, own material);
  // P5 track B: the lane K sheet / foam / lip meshes instead of the card when the sheet mesh is in the build
  const FName FallCardName(S08EnvGroundSpec::ParamFallCard);
  for (const FS08EnvWaterfall& Fall : Ground.Waterfalls) {
    UMaterialInterface* FallMaterial = GroundLoadMaterial(Fall.Material);
    if (!FallMaterial) {
      ++S.FallsMissing;
      continue;
    }
    const FString Base = FString::Printf(TEXT("EnvWaterfall_%s"), *GroundSafeName(Fall.Id));
    UStaticMesh* Sheet = Fall.Mesh.bSet ? GroundLoadMesh(Fall.Mesh.Sheet) : nullptr;
    if (Sheet) {
      const FTransform Piece = MeshPieceTransform(Fall.Mesh.Loc, Fall.Mesh.YawDeg);
      UStaticMeshComponent* C = GroundNewComponent(Owner, Attach, Sheet, Base + TEXT("_Sheet"), Piece, false);
      for (int32 Slot = 0; Slot < GroundSlots(Sheet); ++Slot) {
        GroundSetMid(C, Slot, FallMaterial, [&Fall, &FallCardName](UMaterialInstanceDynamic& Mid) {
          Mid.SetVectorParameterValue(FallCardName, SheetCardParam(Fall.Mesh));
        });
      }
      GroundRegister(C, Out);
      ++S.FallMeshParts;
      if (UStaticMesh* Foam = GroundLoadMesh(Fall.Mesh.Foam)) {
        C = GroundNewComponent(Owner, Attach, Foam, Base + TEXT("_Foam"), Piece, false);
        for (int32 Slot = 0; Slot < GroundSlots(Foam); ++Slot) {  // slot 0 foam, slot 1 mist (kind 1 = spill fades)
          GroundSetMid(C, Slot, FallMaterial, [&Fall, &FallCardName, Slot](UMaterialInstanceDynamic& Mid) {
            Mid.SetVectorParameterValue(FallCardName, FoamCardParam(Fall.Mesh, Slot));
          });
        }
        GroundRegister(C, Out);
        ++S.FallMeshParts;
      }
      // the rock lip: only with its tray material (a lip in the importer's default material would read as a hole)
      UStaticMesh* Lip = GroundLoadMesh(Fall.Mesh.Lip);
      UMaterialInterface* LipMaterial = Lip ? GroundLoadMaterial(Fall.Mesh.LipMaterial) : nullptr;
      if (Lip && LipMaterial) {
        C = GroundNewComponent(Owner, Attach, Lip, Base + TEXT("_Lip"), Piece, true);  // rock: casts like the tray
        for (int32 Slot = 0; Slot < GroundSlots(Lip); ++Slot) C->SetMaterial(Slot, LipMaterial);
        GroundRegister(C, Out);
        ++S.FallMeshParts;
      }
      ++S.FallMeshes;
    } else {
      GroundAddPlane(Owner, Attach, Plane, Base + TEXT("_Card"), FallCardTransform(Fall), FallMaterial,
                     [&Fall, &FallCardName](UMaterialInstanceDynamic& Mid) {
                       Mid.SetVectorParameterValue(FallCardName, FallCardParam(Fall, false));
                     },
                     Out);
      ++S.FallCards;
    }
    if (Fall.SpillUU > 0.0f) {
      GroundAddPlane(Owner, Attach, Plane, Base + TEXT("_Spill"), FallSpillTransform(Fall), FallMaterial,
                     [&Fall, &FallCardName](UMaterialInstanceDynamic& Mid) {
                       Mid.SetVectorParameterValue(FallCardName, FallCardParam(Fall, true));
                     },
                     Out);
      ++S.FallCards;
    }
    ++S.Falls;
  }
  // P5 track B: the sea ring under the tray (the MI as is: one look per map, nothing per component)
  if (Ground.Sea.bSet) {
    UStaticMesh* SeaMesh = GroundLoadMesh(Ground.Sea.Mesh);
    UMaterialInterface* SeaMaterial = SeaMesh ? GroundLoadMaterial(Ground.Sea.Material) : nullptr;
    if (!SeaMesh) {
      S.SeaStatus = TEXT("missing-mesh");
    } else if (!SeaMaterial) {
      S.SeaStatus = TEXT("missing-material");
    } else {
      UStaticMeshComponent* C = GroundNewComponent(Owner, Attach, SeaMesh, TEXT("EnvSea"),
                                                   MeshPieceTransform(Ground.Sea.Loc, Ground.Sea.YawDeg), false);
      for (int32 Slot = 0; Slot < GroundSlots(SeaMesh); ++Slot) C->SetMaterial(Slot, SeaMaterial);
      GroundRegister(C, Out);
      S.SeaStatus = TEXT("ok");
    }
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
      TEXT("ARTPREVIEW envlayout ground map=%s mode=%s strips=%d material=%s z=%.1f outer=%s hole=%s splatRect=%s splatCovers=%d areaUU2=%.0f falls=%d/%d fallCards=%d status=%s"),
      MapKey.IsEmpty() ? TEXT("-") : *MapKey, Ground.Mode.IsEmpty() ? TEXT("-") : *Ground.Mode, Stats.Strips,
      Stats.MaterialName.IsEmpty() ? *Ground.Material : *Stats.MaterialName, Ground.Z, *GroundBox(Stats.Outer),
      *GroundBox(Stats.Hole), Ground.bSplatRect ? *GroundBox(Ground.SplatRect) : TEXT("-"),
      Stats.bSplatCoversOuter ? 1 : 0, Stats.AreaUU2, Stats.Falls, Ground.Waterfalls.Num(), Stats.FallCards,
      *Stats.Status) +
         (Ground.HasMeshPieces() ? FString::Printf(TEXT(" fallMeshes=%d fallMeshParts=%d sea=%s"), Stats.FallMeshes,
                                                   Stats.FallMeshParts, *Stats.SeaStatus)
                                 : FString());
}

}  // namespace S08EnvGround

bool FS08EnvGround::HasMeshPieces() const {
  if (Sea.bSet) return true;
  for (const FS08EnvWaterfall& Fall : Waterfalls) {
    if (Fall.Mesh.bSet) return true;
  }
  return false;
}

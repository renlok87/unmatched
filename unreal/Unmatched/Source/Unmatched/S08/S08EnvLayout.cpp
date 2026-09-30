#include "S08EnvLayout.h"

#include "S08Contracts.h"
#include "S08Diorama.h"
#include "S08Render.h"
#include "S08TraceLog.h"
#include "Components/PointLightComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/CollisionProfile.h"
#include "Engine/Scene.h"  // ELightUnits (LightComponent.h only forward-declares it)
#include "Engine/StaticMesh.h"
#include "GameFramework/Actor.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformProperties.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UObject/UObjectGlobals.h"

// Helpers live in a NAMED namespace: unity builds merge this file with S08BoardArt.cpp, whose anonymous namespace
// already has ParseHexColor / ReadNumberArray / MaxPointLights.
namespace S08EnvLayoutPrivate {
int32 GOptOutOverride = -1;  // -1 = read the command line, 0/1 = automation override

/** A JSON number (never a numeric string: FJsonValueString::TryGetNumber would accept "12"). */
bool EnvNumber(const TSharedPtr<FJsonValue>& Value, double& Out) {
  if (!Value.IsValid() || Value->Type != EJson::Number) return false;
  Out = Value->AsNumber();
  return FMath::IsFinite(Out);
}

/** Optional number field: absent -> true (Out unchanged); present but not a number -> false. */
bool EnvOptionalNumber(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, double& Out) {
  const TSharedPtr<FJsonValue> Value = Obj->TryGetField(Field);
  if (!Value.IsValid() || Value->Type == EJson::Null) return true;
  return EnvNumber(Value, Out);
}

bool EnvRequiredNumber(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, double& Out) {
  return EnvNumber(Obj->TryGetField(Field), Out);
}

/** Optional bool field: absent -> true (Out unchanged); present but not a bool -> false. */
bool EnvOptionalBool(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, bool& Out) {
  const TSharedPtr<FJsonValue> Value = Obj->TryGetField(Field);
  if (!Value.IsValid() || Value->Type == EJson::Null) return true;
  if (Value->Type != EJson::Boolean) return false;
  Out = Value->AsBool();
  return true;
}

bool EnvVec3(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, FVector& Out) {
  const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
  if (!Obj->TryGetArrayField(Field, Values) || !Values || Values->Num() != 3) return false;
  double N[3] = {0.0, 0.0, 0.0};
  for (int32 I = 0; I < 3; ++I) {
    if (!EnvNumber((*Values)[I], N[I])) return false;
  }
  Out = FVector(N[0], N[1], N[2]);
  return true;
}

bool EnvHexColor(const FString& Hex, FColor& Out) {
  if (Hex.Len() != 7 || Hex[0] != TEXT('#')) return false;
  for (int32 I = 1; I < 7; ++I) {
    if (!FChar::IsHexDigit(Hex[I])) return false;
  }
  Out = FColor::FromHex(Hex);
  Out.A = 255;
  return true;
}

/** Map key / board id: [a-z0-9-] resp. [A-Za-z0-9_-], non-empty. */
bool EnvIsKey(const FString& S, bool bLowerOnly) {
  if (S.IsEmpty()) return false;
  for (const TCHAR C : S) {
    const bool bOk = FChar::IsDigit(C) || C == TEXT('-') || (bLowerOnly ? FChar::IsLower(C) : (FChar::IsAlpha(C) || C == TEXT('_')));
    if (!bOk) return false;
  }
  return true;
}

/** Package path "/Game/..." or "/Engine/..." ([A-Za-z0-9_/-]), optionally ".<ObjectName>". */
bool EnvIsPackagePath(const FString& Path) {
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

FString EnvPackageOf(const FString& Path) {
  int32 Dot = INDEX_NONE;
  return Path.FindChar(TEXT('.'), Dot) ? Path.Left(Dot) : Path;
}

FString EnvSafeName(const FString& Id) {
  FString Safe;
  for (const TCHAR C : Id) Safe.AppendChar(FChar::IsAlnum(C) ? C : TEXT('_'));
  return Safe;
}

bool EnvParseProp(const TSharedPtr<FJsonObject>& Obj, int32 Index, TSet<FString>& Ids, FS08EnvProp& Out,
                  TArray<FString>& Errors) {
  const int32 Before = Errors.Num();
  Out = FS08EnvProp();
  if (!Obj->TryGetStringField(TEXT("id"), Out.Id) || Out.Id.IsEmpty()) {
    Errors.Add(FString::Printf(TEXT("props[%d]: id missing"), Index));
    return false;
  }
  const FString Ctx = TEXT("prop ") + Out.Id;
  if (Ids.Contains(Out.Id)) Errors.Add(Ctx + TEXT(": duplicate id"));
  Ids.Add(Out.Id);
  if (!Obj->TryGetStringField(TEXT("mesh"), Out.Mesh) || !EnvIsPackagePath(Out.Mesh)) {
    Errors.Add(FString::Printf(TEXT("%s: mesh '%s' is not a /Game/ or /Engine/ package path"), *Ctx, *Out.Mesh));
  }
  if (!EnvVec3(Obj, TEXT("loc"), Out.Loc)) Errors.Add(Ctx + TEXT(": loc needs [x, y, z] numbers"));
  double Yaw = 0.0, Scale = 1.0;
  if (!EnvOptionalNumber(Obj, TEXT("yawDeg"), Yaw)) Errors.Add(Ctx + TEXT(": yawDeg is not a number"));
  if (!EnvOptionalNumber(Obj, TEXT("scale"), Scale) || Scale <= 0.0 || Scale > S08EnvLayoutSpec::MaxPropScale) {
    Errors.Add(FString::Printf(TEXT("%s: scale must be a number in (0, %.0f]"), *Ctx, S08EnvLayoutSpec::MaxPropScale));
  }
  Out.YawDeg = static_cast<float>(Yaw);
  Out.Scale = static_cast<float>(Scale);
  if (!EnvOptionalBool(Obj, TEXT("castShadow"), Out.bCastShadow)) Errors.Add(Ctx + TEXT(": castShadow is not a bool"));
  return Errors.Num() == Before;
}

bool EnvParseLight(const TSharedPtr<FJsonObject>& Obj, int32 Index, TSet<FString>& Ids, FS08EnvLight& Out,
                   TArray<FString>& Errors) {
  const int32 Before = Errors.Num();
  Out = FS08EnvLight();
  if (!Obj->TryGetStringField(TEXT("id"), Out.Id) || Out.Id.IsEmpty()) {
    Errors.Add(FString::Printf(TEXT("lights[%d]: id missing"), Index));
    return false;
  }
  const FString Ctx = TEXT("light ") + Out.Id;
  if (Ids.Contains(Out.Id)) Errors.Add(Ctx + TEXT(": duplicate id"));
  Ids.Add(Out.Id);
  FString Type = TEXT("point");
  if (Obj->HasField(TEXT("type")) && (!Obj->TryGetStringField(TEXT("type"), Type) || Type != TEXT("point"))) {
    Errors.Add(FString::Printf(TEXT("%s: type '%s' is not 'point' (the directional key stays in the art profile)"), *Ctx,
                               *Type));
  }
  if (!EnvVec3(Obj, TEXT("loc"), Out.Loc)) Errors.Add(Ctx + TEXT(": loc needs [x, y, z] numbers"));
  FString Hex;
  if (!Obj->TryGetStringField(TEXT("colorSrgb"), Hex) || !EnvHexColor(Hex, Out.Color)) {
    Errors.Add(FString::Printf(TEXT("%s: colorSrgb '%s' is not #RRGGBB"), *Ctx, *Hex));
  }
  double Cd = 0.0, Radius = 0.0;
  if (!EnvRequiredNumber(Obj, TEXT("intensityCd"), Cd) || Cd <= 0.0) Errors.Add(Ctx + TEXT(": intensityCd must be > 0"));
  if (!EnvRequiredNumber(Obj, TEXT("radius"), Radius) || Radius <= 0.0) Errors.Add(Ctx + TEXT(": radius must be > 0 uu"));
  Out.IntensityCd = static_cast<float>(Cd);
  Out.RadiusUU = static_cast<float>(Radius);
  bool bShadow = false;
  if (!EnvOptionalBool(Obj, TEXT("castShadow"), bShadow)) {
    Errors.Add(Ctx + TEXT(": castShadow is not a bool"));
  } else if (bShadow) {
    Errors.Add(Ctx + TEXT(": castShadow true - point lights never cast shadows (budget: 1 shadowed directional)"));
  }
  return Errors.Num() == Before;
}

FString EnvVec(const FVector& V) { return FString::Printf(TEXT("(%.1f,%.1f,%.1f)"), V.X, V.Y, V.Z); }

FString EnvDisplayPath(const FString& Path) {
  // the pak / Config-relative form of the default folder (as the profiles line), the full path of an override
  FString Rel = Path;
  FPaths::NormalizeFilename(Rel);
  FString Config = FPaths::ProjectConfigDir();
  FPaths::NormalizeFilename(Config);
  return Rel.StartsWith(Config) ? TEXT("Config/") + Rel.RightChop(Config.Len()) : Rel;
}
}  // namespace S08EnvLayoutPrivate

// ---- data --------------------------------------------------------------------------------------------------------

FS08EnvTray FS08EnvApron::ImpliedTray(const FVector2D& FrameHalf) const {
  FS08EnvTray T;
  T.bSet = bSet;
  T.HalfX = static_cast<float>(FrameHalf.X) + FMath::Max(W, E);
  // far edge -(FrameHalf.Y + N), near edge +(FrameHalf.Y + S)
  T.HalfY = static_cast<float>(FrameHalf.Y) + 0.5f * (N + S);
  T.OffsetY = 0.5f * (S - N);
  return T;
}

FTransform FS08EnvProp::Transform() const {
  return FTransform(FRotator(0.0f, YawDeg, 0.0f), Loc, FVector(Scale));
}

FString FS08EnvLight::ColorHex() const {
  return FString::Printf(TEXT("#%02X%02X%02X"), Color.R, Color.G, Color.B);
}

bool FS08EnvLayout::ParseJson(const FString& Text, TArray<FString>& OutErrors) {
  using namespace S08EnvLayoutPrivate;
  *this = FS08EnvLayout();
  const int32 Before = OutErrors.Num();
  TSharedPtr<FJsonObject> Root;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(Text, Root, Problem) || !Root.IsValid()) {
    OutErrors.Add(TEXT("invalid JSON: ") + Problem);
    return false;
  }
  FString Schema;
  if (!Root->TryGetStringField(TEXT("schema"), Schema) || Schema != S08EnvLayoutSpec::Schema) {
    OutErrors.Add(FString::Printf(TEXT("schema '%s' is not %s"), *Schema, S08EnvLayoutSpec::Schema));
    return false;
  }
  if (!Root->TryGetStringField(TEXT("map"), Map) || !EnvIsKey(Map, true)) {
    OutErrors.Add(FString::Printf(TEXT("map '%s' is not a lower-case map key"), *Map));
  }
  if (!Root->TryGetStringField(TEXT("boardId"), BoardId) || !EnvIsKey(BoardId, false)) {
    OutErrors.Add(FString::Printf(TEXT("boardId '%s' is not a Board row id"), *BoardId));
  }
  if (Root->HasField(TEXT("tray"))) {
    const TSharedPtr<FJsonObject>* TrayObj = nullptr;
    double HalfX = 0.0, HalfY = 0.0, OffsetY = 0.0;
    if (!Root->TryGetObjectField(TEXT("tray"), TrayObj) || !TrayObj || !TrayObj->IsValid() ||
        !EnvRequiredNumber(*TrayObj, TEXT("halfX"), HalfX) || !EnvRequiredNumber(*TrayObj, TEXT("halfY"), HalfY) ||
        !EnvOptionalNumber(*TrayObj, TEXT("offsetY"), OffsetY) || HalfX <= 0.0 || HalfY <= 0.0) {
      OutErrors.Add(TEXT("tray needs {halfX > 0, halfY > 0, offsetY (number, optional)}"));
    } else {
      Tray.bSet = true;
      Tray.HalfX = static_cast<float>(HalfX);
      Tray.HalfY = static_cast<float>(HalfY);
      Tray.OffsetY = static_cast<float>(OffsetY);
    }
  }
  if (Root->HasField(TEXT("apron"))) {
    const TSharedPtr<FJsonObject>* ApronObj = nullptr;
    double N = 0.0, S = 0.0, W = 0.0, E = 0.0;
    if (!Root->TryGetObjectField(TEXT("apron"), ApronObj) || !ApronObj || !ApronObj->IsValid() ||
        !EnvRequiredNumber(*ApronObj, TEXT("n"), N) || !EnvRequiredNumber(*ApronObj, TEXT("s"), S) ||
        !EnvRequiredNumber(*ApronObj, TEXT("w"), W) || !EnvRequiredNumber(*ApronObj, TEXT("e"), E) || N < 0.0 ||
        S < 0.0 || W < 0.0 || E < 0.0) {
      OutErrors.Add(TEXT("apron needs {n, s, w, e} numbers >= 0"));
    } else {
      Apron.bSet = true;
      Apron.N = static_cast<float>(N);
      Apron.S = static_cast<float>(S);
      Apron.W = static_cast<float>(W);
      Apron.E = static_cast<float>(E);
    }
  }
  const TArray<TSharedPtr<FJsonValue>>* PropValues = nullptr;
  if (!Root->TryGetArrayField(TEXT("props"), PropValues) || !PropValues) {
    OutErrors.Add(TEXT("props array missing"));
  } else if (PropValues->Num() > S08EnvLayoutSpec::MaxProps) {
    OutErrors.Add(FString::Printf(TEXT("%d props > %d"), PropValues->Num(), S08EnvLayoutSpec::MaxProps));
  } else {
    TSet<FString> Ids;
    for (int32 I = 0; I < PropValues->Num(); ++I) {
      const TSharedPtr<FJsonObject>* Obj = nullptr;
      if (!(*PropValues)[I].IsValid() || !(*PropValues)[I]->TryGetObject(Obj) || !Obj || !Obj->IsValid()) {
        OutErrors.Add(FString::Printf(TEXT("props[%d] is not an object"), I));
        continue;
      }
      FS08EnvProp Prop;
      if (EnvParseProp(*Obj, I, Ids, Prop, OutErrors)) Props.Add(Prop);
    }
  }
  if (Root->HasField(TEXT("lights"))) {
    const TArray<TSharedPtr<FJsonValue>>* LightValues = nullptr;
    if (!Root->TryGetArrayField(TEXT("lights"), LightValues) || !LightValues) {
      OutErrors.Add(TEXT("lights is not an array"));
    } else if (LightValues->Num() > S08EnvLayoutSpec::MaxPointLights) {
      OutErrors.Add(FString::Printf(TEXT("%d point lights > %d (budget: 1 directional key in the art profile + <= %d points)"),
                                    LightValues->Num(), S08EnvLayoutSpec::MaxPointLights,
                                    S08EnvLayoutSpec::MaxPointLights));
    } else {
      TSet<FString> Ids;
      for (int32 I = 0; I < LightValues->Num(); ++I) {
        const TSharedPtr<FJsonObject>* Obj = nullptr;
        if (!(*LightValues)[I].IsValid() || !(*LightValues)[I]->TryGetObject(Obj) || !Obj || !Obj->IsValid()) {
          OutErrors.Add(FString::Printf(TEXT("lights[%d] is not an object"), I));
          continue;
        }
        FS08EnvLight Light;
        if (EnvParseLight(*Obj, I, Ids, Light, OutErrors)) Lights.Add(Light);
      }
    }
  }
  Root->TryGetStringField(TEXT("notes"), Notes);
  return OutErrors.Num() == Before;
}

bool FS08EnvLayout::LoadFile(const FString& Path, TArray<FString>& OutErrors) {
  TArray<uint8> Bytes;
  if (!FFileHelper::LoadFileToArray(Bytes, *Path)) {
    OutErrors.Add(FString::Printf(TEXT("cannot read %s"), *Path));
    return false;
  }
  FString Text;
  FFileHelper::BufferToString(Text, Bytes.GetData(), Bytes.Num());
  const bool bOk = ParseJson(Text, OutErrors);
  SourcePath = Path;
  SourceSha256 = S08Sha256Hex(Bytes.GetData(), Bytes.Num());
  return bOk;
}

TArray<FString> FS08EnvLayout::UniqueMeshPaths() const {
  TArray<FString> Out;
  for (const FS08EnvProp& P : Props) Out.AddUnique(P.Mesh);
  return Out;
}

// ---- world-free helpers -----------------------------------------------------------------------------------------

namespace S08EnvLayout {

bool OptOut() {
  if (S08EnvLayoutPrivate::GOptOutOverride >= 0) return S08EnvLayoutPrivate::GOptOutOverride == 1;
  return FParse::Param(FCommandLine::Get(), S08EnvLayoutSpec::NoEnvFlagName);
}

bool Enabled(bool bArtPreview) { return S08Diorama::Enabled(bArtPreview) && !OptOut(); }

bool Arm(bool bArtPreview) {
  if (!S08Diorama::Enabled(bArtPreview)) return false;
  if (OptOut()) {
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW envlayout disabled (-%s)"), S08EnvLayoutSpec::NoEnvFlagName));
    return false;
  }
  bool bOverride = false;
  const FString Dir = ResolveDir(bOverride);
  TArray<FString> Files;
  IFileManager::Get().FindFiles(Files, *FPaths::Combine(Dir, FString(TEXT("*")) + S08EnvLayoutSpec::FileSuffix), true,
                                false);
  Files.Sort();
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW envlayout enabled dir=%s source=%s files=%d%s%s"),
                                   *S08EnvLayoutPrivate::EnvDisplayPath(Dir), bOverride ? TEXT("override") : TEXT("pak"),
                                   Files.Num(), Files.Num() ? TEXT(" names=") : TEXT(""),
                                   *FString::Join(Files, TEXT("+"))));
  return true;
}

void SetOptOutOverrideForTest(bool bOptOut) { S08EnvLayoutPrivate::GOptOutOverride = bOptOut ? 1 : 0; }

void ResetOptOutOverrideForTest() { S08EnvLayoutPrivate::GOptOutOverride = -1; }

FString DefaultDir() { return FPaths::Combine(FPaths::ProjectConfigDir(), S08EnvLayoutSpec::ConfigSubdir); }

FString ResolveDir(bool& bOutOverride) {
  FString Override;
  bOutOverride = FParse::Value(FCommandLine::Get(), S08EnvLayoutSpec::DirOverrideParam, Override) && !Override.IsEmpty();
  return bOutOverride ? Override : DefaultDir();
}

FString FileFor(const FString& Dir, const FString& MapKey) {
  return FPaths::Combine(Dir, MapKey + S08EnvLayoutSpec::FileSuffix);
}

FString MapKeyOf(const FString& MapName) { return MapName.ToLower(); }

bool Resolve(const FString& Dir, const FString& MapKey, const TArray<FString>& BoardIds, FS08EnvLayout& Out,
             TArray<FString>& OutErrors, bool& bOutAbsent) {
  bOutAbsent = false;
  auto Accept = [&](const FS08EnvLayout& Layout, TArray<FString>& Errors) {
    bool bOk = true;
    if (Layout.Map != MapKey) {
      Errors.Add(FString::Printf(TEXT("%s: map '%s' != '%s'"), *FPaths::GetCleanFilename(Layout.SourcePath),
                                 *Layout.Map, *MapKey));
      bOk = false;
    }
    if (BoardIds.Num() > 0 && !BoardIds.Contains(Layout.BoardId)) {
      Errors.Add(FString::Printf(TEXT("%s: boardId '%s' is not the board of this profile (%s)"),
                                 *FPaths::GetCleanFilename(Layout.SourcePath), *Layout.BoardId,
                                 *FString::Join(BoardIds, TEXT("+"))));
      bOk = false;
    }
    return bOk;
  };
  const FString Primary = FileFor(Dir, MapKey);
  if (FPaths::FileExists(Primary)) {
    FS08EnvLayout Layout;
    if (!Layout.LoadFile(Primary, OutErrors) || !Accept(Layout, OutErrors)) return false;
    Out = MoveTemp(Layout);
    return true;
  }
  // No <map>.layout.json: any layout of the folder that names this map and board (e.g. a file named by board id).
  TArray<FString> Names;
  IFileManager::Get().FindFiles(Names, *FPaths::Combine(Dir, FString(TEXT("*")) + S08EnvLayoutSpec::FileSuffix), true,
                                false);
  Names.Sort();
  for (const FString& Name : Names) {
    FS08EnvLayout Layout;
    TArray<FString> Ignored;
    if (!Layout.LoadFile(FPaths::Combine(Dir, Name), Ignored)) continue;
    if (Layout.Map == MapKey && (BoardIds.Num() == 0 || BoardIds.Contains(Layout.BoardId))) {
      Out = MoveTemp(Layout);
      return true;
    }
  }
  bOutAbsent = true;
  OutErrors.Add(FString::Printf(TEXT("no layout for map=%s boardIds=%s (expected %s; %d other layout file(s) in the folder)"),
                                *MapKey, BoardIds.Num() ? *FString::Join(BoardIds, TEXT("+")) : TEXT("-"),
                                *S08EnvLayoutPrivate::EnvDisplayPath(Primary), Names.Num()));
  return false;
}

bool TrayFit(const FS08EnvLayout& Layout, const FVector2D& FrameHalf, FVector2D& OutBoardHalf, FVector2D& OutOffset,
             FString& OutSource, FString& OutReason) {
  OutReason.Reset();
  FS08EnvTray T;
  if (Layout.Tray.bSet) {
    T = Layout.Tray;
    OutSource = TEXT("layout");
  } else if (Layout.Apron.bSet) {
    T = Layout.Apron.ImpliedTray(FrameHalf);
    OutSource = TEXT("apron");
  } else {
    OutSource = TEXT("profile");
    OutReason = TEXT("layout has neither tray nor apron");
    return false;
  }
  // The tray top must cover the map + frame: X symmetric, Y from OffsetY - HalfY (far) to OffsetY + HalfY (near).
  if (T.HalfX < FrameHalf.X || T.OffsetY - T.HalfY > -FrameHalf.Y || T.OffsetY + T.HalfY < FrameHalf.Y) {
    OutReason = FString::Printf(TEXT("tray %.1fx%.1f offsetY %.1f does not cover the frame half %.1fx%.1f"), T.HalfX,
                                T.HalfY, T.OffsetY, FrameHalf.X, FrameHalf.Y);
    OutSource = TEXT("profile");
    return false;
  }
  // S08Diorama::FitTray(BoardHalf, Offset) = outer half BoardHalf + |Offset| + RimUU at Offset: invert it.
  OutOffset = FVector2D(0.0, T.OffsetY);
  OutBoardHalf = FVector2D(T.HalfX - S08Diorama::RimUU, T.HalfY - FMath::Abs(T.OffsetY) - S08Diorama::RimUU);
  if (OutBoardHalf.X <= 0.0 || OutBoardHalf.Y <= 0.0) {
    OutReason = FString::Printf(TEXT("tray %.1fx%.1f is smaller than the %.0f uu rim"), T.HalfX, T.HalfY,
                                S08Diorama::RimUU);
    OutSource = TEXT("profile");
    return false;
  }
  return true;
}

FBox2D TrayTopRect(const FS08EnvLayout* Layout, const FVector2D& FrameHalf, const FVector2D& ProfileTrayOffset) {
  FVector2D BoardHalf = FrameHalf, Offset = ProfileTrayOffset;
  FString Source, Reason;
  if (Layout) {
    FVector2D LayoutHalf, LayoutOffset;
    if (TrayFit(*Layout, FrameHalf, LayoutHalf, LayoutOffset, Source, Reason)) {
      BoardHalf = LayoutHalf;
      Offset = LayoutOffset;
    }
  }
  const S08Diorama::FTrayFit Fit = S08Diorama::FitTray(BoardHalf, Offset);
  return FBox2D(Fit.Location - Fit.WorldHalf, Fit.Location + Fit.WorldHalf);
}

bool PivotInsideMap(const FVector& Loc, const FVector2D& MapHalf) {
  return FMath::Abs(Loc.X) < MapHalf.X && FMath::Abs(Loc.Y) < MapHalf.Y;
}

bool BoxOverlapsMap(const FBox& Box, const FVector2D& MapHalf) {
  return Box.IsValid && Box.Min.X < MapHalf.X && Box.Max.X > -MapHalf.X && Box.Min.Y < MapHalf.Y &&
         Box.Max.Y > -MapHalf.Y;
}

FString SummaryLine(const FString& MapKey, const FS08EnvSpawnStats& Stats, const FString& Tail) {
  return FString::Printf(TEXT("ARTPREVIEW envlayout map=%s props=%d lights=%d missingMeshes=%d%s"),
                         MapKey.IsEmpty() ? TEXT("-") : *MapKey, Stats.Props, Stats.Lights, Stats.MissingMeshes, *Tail);
}

// ---- world side -------------------------------------------------------------------------------------------------

FS08EnvSpawnStats Spawn(const FS08EnvLayout& Layout, AActor& Owner, USceneComponent* Parent, const FVector2D& MapHalf,
                        const FBox2D& TrayTop, TArray<TObjectPtr<UStaticMeshComponent>>& OutProps,
                        TArray<TObjectPtr<UPointLightComponent>>& OutLights) {
  using namespace S08EnvLayoutPrivate;
  FS08EnvSpawnStats S;
  S.LayoutProps = Layout.Props.Num();
  S.LayoutLights = Layout.Lights.Num();
  USceneComponent* Attach = Parent ? Parent : Owner.GetRootComponent();
  TMap<FString, UStaticMesh*> Loaded;  // nullptr = tried, missing (one load per unique path)
  TMap<FString, TArray<FString>> MissingIds;
  for (const FS08EnvProp& P : Layout.Props) {
    if (PivotInsideMap(P.Loc, MapHalf)) {
      // ENV-U1: the 3D environment stands only around the map; a pivot on the painted map would cover spaces.
      ++S.SkippedInsideMap;
      FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW envlayout skipped id=%s reason=inside-map loc=%s mapHalf=%.1fx%.1f"),
                                       *P.Id, *EnvVec(P.Loc), MapHalf.X, MapHalf.Y));
      continue;
    }
    if (!P.Mesh.StartsWith(S08EnvLayoutSpec::KitRoot)) ++S.OutsideKit;
    UStaticMesh* Mesh = nullptr;
    if (UStaticMesh** Found = Loaded.Find(P.Mesh)) {
      Mesh = *Found;
    } else {
      // Uncooked runs (editor, automation) ask the package first: a missing kit never reaches the loader (no loader
      // warning in the automation log). Cooked runs load directly (LOAD_NoWarn), as the map-image assets do.
      const bool bMayExist =
          FPlatformProperties::RequiresCookedData() || FPackageName::DoesPackageExist(EnvPackageOf(P.Mesh));
      Mesh = bMayExist ? LoadObject<UStaticMesh>(nullptr, *P.Mesh, nullptr, LOAD_NoWarn) : nullptr;
      Loaded.Add(P.Mesh, Mesh);
    }
    if (!Mesh) {
      MissingIds.FindOrAdd(P.Mesh).Add(P.Id);
      ++S.SkippedMissing;
      continue;
    }
    const FName Name = MakeUniqueObjectName(&Owner, UStaticMeshComponent::StaticClass(),
                                            FName(*(TEXT("EnvProp_") + EnvSafeName(P.Id))));
    UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(&Owner, Name);
    C->SetupAttachment(Attach);
    C->SetStaticMesh(Mesh);
    // Decor only: never a click / cursor surface (the map pick box is), never navigation.
    C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    C->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
    C->SetGenerateOverlapEvents(false);
    C->SetCanEverAffectNavigation(false);
    C->SetCastShadow(P.bCastShadow);
    // Default mobility (Movable, as the tray and the frame bars): a registered Static component would refuse the
    // transform (USceneComponent::MoveComponentImpl), and nothing here is baked.
    C->SetRelativeTransform(P.Transform());
    C->RegisterComponent();
    OutProps.Add(C);
    ++S.Props;
    S.ShadowCasters += P.bCastShadow ? 1 : 0;
    const FBox Box = Mesh->GetBoundingBox().TransformBy(P.Transform());  // board space
    const bool bOverMap = BoxOverlapsMap(Box, MapHalf);
    const bool bOnTray = !TrayTop.bIsValid || TrayTop.IsInside(FVector2D(P.Loc.X, P.Loc.Y));
    S.Intrusions += bOverMap ? 1 : 0;
    S.OutsideTray += bOnTray ? 0 : 1;
    const FVector Size = Box.GetSize();
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW envlayout prop id=%s mesh=%s loc=%s yaw=%.1f scale=%.3f shadow=%d size=%.1fx%.1fx%.1f bounds=%s..%s overMap=%d onTray=%d"),
        *P.Id, *FPackageName::GetShortName(EnvPackageOf(P.Mesh)), *EnvVec(P.Loc), P.YawDeg, P.Scale,
        P.bCastShadow ? 1 : 0, Size.X, Size.Y, Size.Z, *EnvVec(Box.Min), *EnvVec(Box.Max), bOverMap ? 1 : 0,
        bOnTray ? 1 : 0));
  }
  for (const TPair<FString, TArray<FString>>& Missing : MissingIds) {
    ++S.MissingMeshes;
    S.MissingPaths.Add(Missing.Key);
    const FString Line = FString::Printf(TEXT("ARTPREVIEW envlayout missing mesh=%s props=%s (skipped; run tools/art/env_kit/ue_import_env_kit.py)"),
                                         *Missing.Key, *FString::Join(Missing.Value, TEXT("+")));
    UE_LOG(LogTemp, Display, TEXT("%s"), *Line);  // Display: the trace line is the contract (tests collect warnings)
    FS08Trace::Write(Line);
  }
  for (const FS08EnvLight& L : Layout.Lights) {
    const FName Name = MakeUniqueObjectName(&Owner, UPointLightComponent::StaticClass(),
                                            FName(*(TEXT("EnvLight_") + EnvSafeName(L.Id))));
    UPointLightComponent* C = NewObject<UPointLightComponent>(&Owner, Name);
    C->SetupAttachment(Attach);
    C->SetMobility(EComponentMobility::Movable);
    // W4-A G01: a runtime point light starts Unitless (1 = 16 internal); the layout is in candelas -> units first.
    // -S08LegacyRender keeps Unitless, as the profile points (S08BoardActor ApplyArtLights), for consistent A/B frames.
    const bool bCandelas = !S08LegacyRender();
    if (bCandelas) C->SetIntensityUnits(ELightUnits::Candelas);
    C->SetIntensity(L.IntensityCd);
    C->SetAttenuationRadius(L.RadiusUU);
    C->SetCastShadows(false);
    C->SetLightFColor(L.Color);  // the sRGB bytes of the data, exactly
    C->SetRelativeLocation(L.Loc);
    C->RegisterComponent();
    OutLights.Add(C);
    ++S.Lights;
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW envlayout light id=%s kind=point at=%s intensity=%g units=%s radius=%g color=%s shadow=0"),
        *L.Id, *EnvVec(L.Loc), L.IntensityCd, bCandelas ? TEXT("candelas") : TEXT("unitless-legacy"), L.RadiusUU,
        *L.ColorHex()));
  }
  return S;
}

int32 Clear(TArray<TObjectPtr<UStaticMeshComponent>>& Props, TArray<TObjectPtr<UPointLightComponent>>& Lights) {
  int32 Count = 0;
  for (UStaticMeshComponent* C : Props) {
    if (C) {
      C->DestroyComponent();
      ++Count;
    }
  }
  for (UPointLightComponent* C : Lights) {
    if (C) {
      C->DestroyComponent();
      ++Count;
    }
  }
  Props.Reset();
  Lights.Reset();
  return Count;
}

void Update(const FS08EnvLayoutRequest& Request, AActor& Owner, USceneComponent* Parent, FS08EnvLayoutRuntime& Runtime,
            TArray<TObjectPtr<UStaticMeshComponent>>& Props, TArray<TObjectPtr<UPointLightComponent>>& Lights) {
  using namespace S08EnvLayoutPrivate;
  if (!Request.bEnabled || !Request.bMapImageActive) {
    // A board change away from a map-image board (or the gate went off): nothing of the environment stays. A grid
    // board that never had one writes nothing at all.
    if (Runtime.bApplied || Props.Num() > 0 || Lights.Num() > 0) {
      const int32 P = Props.Num(), L = Lights.Num();
      Clear(Props, Lights);
      FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW envlayout off map=%s reason=%s clearedProps=%d clearedLights=%d"),
                                       Runtime.MapKey.IsEmpty() ? TEXT("-") : *Runtime.MapKey,
                                       !Request.bEnabled ? TEXT("gate-off") : TEXT("no-map-image-board"), P, L));
    }
    Runtime = FS08EnvLayoutRuntime();
    return;
  }
  bool bOverride = false;
  const FString Dir = Request.Dir.IsEmpty() ? ResolveDir(bOverride) : Request.Dir;
  TArray<FString> BoardIds;
  if (!Request.RoomBoardId.IsEmpty()) BoardIds.AddUnique(Request.RoomBoardId);
  for (const FString& Id : Request.ProfileBoardIds) BoardIds.AddUnique(Id);
  FS08EnvLayout Layout;
  TArray<FString> Errors;
  bool bAbsent = false;
  const bool bOk = Resolve(Dir, Request.MapKey, BoardIds, Layout, Errors, bAbsent);
  const FString Key = FString::Printf(TEXT("%s|%s|%s|%s"), *Request.MapKey, *Request.RoomBoardId,
                                      bOk ? *Layout.SourceSha256 : (bAbsent ? TEXT("absent") : TEXT("invalid")), *Dir);
  if (Runtime.bApplied && Runtime.Key == Key) {
    return;  // the same layout bytes on the same board again: the components (or the traced failure) stay as they are
  }
  Clear(Props, Lights);
  Runtime = FS08EnvLayoutRuntime();
  Runtime.bApplied = true;
  Runtime.Key = Key;
  Runtime.MapKey = Request.MapKey;
  const FString Source = Request.Dir.IsEmpty() ? (bOverride ? TEXT("override") : TEXT("pak")) : TEXT("explicit");
  if (!bOk) {
    Runtime.Status = bAbsent ? TEXT("absent") : TEXT("invalid");
    const FString Line = SummaryLine(Request.MapKey, Runtime.Stats,
                                     FString::Printf(TEXT(" layoutProps=0 layoutLights=0 profile=%s boardId=%s dir=%s source=%s status=%s errors=%d"),
                                                     *Request.ProfileId,
                                                     Request.RoomBoardId.IsEmpty() ? TEXT("-") : *Request.RoomBoardId,
                                                     *EnvDisplayPath(Dir), *Source, *Runtime.Status, Errors.Num()));
    UE_LOG(LogTemp, Display, TEXT("%s"), *Line);
    FS08Trace::Write(Line);
    for (int32 I = 0; I < Errors.Num() && I < 8; ++I) FS08Trace::Write(TEXT("ARTPREVIEW envlayout error: ") + Errors[I]);
    return;
  }
  Runtime.bLayoutValid = true;
  Runtime.Status = TEXT("ok");
  Runtime.Layout = Layout;
  FVector2D TrayHalf, TrayOffset;
  FString TraySource, TrayReason;
  TrayFit(Layout, Request.FrameHalf, TrayHalf, TrayOffset, TraySource, TrayReason);
  const FBox2D TrayTop = TrayTopRect(&Layout, Request.FrameHalf, Request.ProfileTrayOffset);
  // "tray" and "apron" describe the same band twice: note when they disagree (the tray wins).
  int32 TrayApronMismatch = 0;
  if (Layout.Tray.bSet && Layout.Apron.bSet) {
    const FS08EnvTray Implied = Layout.Apron.ImpliedTray(Request.FrameHalf);
    const float Tol = S08EnvLayoutSpec::TrayApronToleranceUU;
    TrayApronMismatch = !FMath::IsNearlyEqual(Implied.HalfX, Layout.Tray.HalfX, Tol) ||
                                !FMath::IsNearlyEqual(Implied.HalfY, Layout.Tray.HalfY, Tol) ||
                                !FMath::IsNearlyEqual(Implied.OffsetY, Layout.Tray.OffsetY, Tol)
                            ? 1
                            : 0;
    if (TrayApronMismatch) {
      FS08Trace::Write(FString::Printf(
          TEXT("ARTPREVIEW envlayout note map=%s tray %.1fx%.1f offsetY %.1f != apron-implied %.1fx%.1f offsetY %.1f (tray wins)"),
          *Request.MapKey, Layout.Tray.HalfX, Layout.Tray.HalfY, Layout.Tray.OffsetY, Implied.HalfX, Implied.HalfY,
          Implied.OffsetY));
    }
  }
  Runtime.Stats = Spawn(Layout, Owner, Parent, Request.MapHalf, TrayTop, Props, Lights);
  const FS08EnvSpawnStats& S = Runtime.Stats;
  const int32 Combined = Request.ProfilePointLights + S.Lights;
  const FString Tail = FString::Printf(
      TEXT(" layoutProps=%d layoutLights=%d skippedMissing=%d skippedInsideMap=%d intrusions=%d outsideTray=%d outsideKit=%d shadowCasters=%d profilePoints=%d combinedPoints=%d combinedBudgetOk=%d tray=%s trayApronMismatch=%d profile=%s boardId=%s file=%s sha256=%s source=%s status=ok"),
      S.LayoutProps, S.LayoutLights, S.SkippedMissing, S.SkippedInsideMap, S.Intrusions, S.OutsideTray, S.OutsideKit,
      S.ShadowCasters, Request.ProfilePointLights, Combined, Combined <= S08EnvLayoutSpec::CombinedPointBudget ? 1 : 0,
      *TraySource, TrayApronMismatch, *Request.ProfileId, *Layout.BoardId, *EnvDisplayPath(Layout.SourcePath),
      *Layout.SourceSha256, *Source);
  const FString Line = SummaryLine(Request.MapKey, S, Tail);
  UE_LOG(LogTemp, Display, TEXT("%s"), *Line);
  FS08Trace::Write(Line);
}

bool ApplyTray(const FS08EnvLayoutRuntime& Runtime, const FVector2D& FrameHalf, FVector2D& InOutBoardHalf,
               FVector2D& InOutOffset) {
  if (!Runtime.bApplied || !Runtime.bLayoutValid) return false;
  FVector2D Half, Offset;
  FString Source, Reason;
  const bool bOk = TrayFit(Runtime.Layout, FrameHalf, Half, Offset, Source, Reason);
  if (bOk) {
    InOutBoardHalf = Half;
    InOutOffset = Offset;
    const S08Diorama::FTrayFit Fit = S08Diorama::FitTray(Half, Offset);
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW envlayout tray map=%s source=%s outerHalf=%.1fx%.1f offsetY=%.1f frameHalf=%.1fx%.1f fitBoardHalf=%.1fx%.1f anisotropy=%.3f"),
        *Runtime.MapKey, *Source, Fit.WorldHalf.X, Fit.WorldHalf.Y, Offset.Y, FrameHalf.X, FrameHalf.Y, Half.X, Half.Y,
        Fit.Anisotropy()));
  } else if (Runtime.Layout.Tray.bSet || Runtime.Layout.Apron.bSet) {
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW envlayout tray map=%s source=profile refused=%s"),
                                     *Runtime.MapKey, *Reason));
  }
  return bOk;
}

}  // namespace S08EnvLayout

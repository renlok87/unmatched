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
#include "Misc/Crc.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UObject/UObjectGlobals.h"
// P5c fx (Unmatched.Build.cs: private dependency "Niagara")
#include "NiagaraComponent.h"
#include "NiagaraComponentRendererProperties.h"
#include "NiagaraEmitter.h"
#include "NiagaraEmitterHandle.h"
#include "NiagaraEmitterInstance.h"
#include "NiagaraLightRendererProperties.h"
#include "NiagaraParameterStore.h"
#include "NiagaraRendererProperties.h"
#include "NiagaraSystem.h"
#include "NiagaraSystemInstance.h"
#include "NiagaraSystemInstanceController.h"
#include "NiagaraTypes.h"

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

/** User parameter names: [A-Za-z0-9 _.-], no "User." prefix after normalisation. */
bool EnvIsUserParamName(const FString& Name) {
  if (Name.IsEmpty() || Name.Len() > 64) return false;
  for (const TCHAR C : Name) {
    if (!(FChar::IsAlnum(C) || C == TEXT(' ') || C == TEXT('_') || C == TEXT('-') || C == TEXT('.'))) return false;
  }
  return true;
}

/** "user" value: a number, a bool (1 number) or an array of 2..4 numbers. */
bool EnvUserValue(const TSharedPtr<FJsonValue>& Value, FS08EnvFxParam& Out) {
  if (!Value.IsValid()) return false;
  if (Value->Type == EJson::Boolean) {
    Out.Num = 1;
    Out.Value = FVector4(Value->AsBool() ? 1.0 : 0.0, 0.0, 0.0, 0.0);
    return true;
  }
  double N = 0.0;
  if (EnvNumber(Value, N)) {
    Out.Num = 1;
    Out.Value = FVector4(N, 0.0, 0.0, 0.0);
    return true;
  }
  if (Value->Type != EJson::Array) return false;
  const TArray<TSharedPtr<FJsonValue>>& Items = Value->AsArray();
  if (Items.Num() < 2 || Items.Num() > 4) return false;
  double V[4] = {0.0, 0.0, 0.0, 0.0};
  for (int32 I = 0; I < Items.Num(); ++I) {
    if (!EnvNumber(Items[I], V[I])) return false;
  }
  Out.Num = Items.Num();
  Out.Value = FVector4(V[0], V[1], V[2], V[3]);
  return true;
}

bool EnvParseFx(const TSharedPtr<FJsonObject>& Obj, int32 Index, TSet<FString>& Ids, FS08EnvFx& Out,
                TArray<FString>& Errors) {
  const int32 Before = Errors.Num();
  Out = FS08EnvFx();
  if (!Obj->TryGetStringField(TEXT("id"), Out.Id) || Out.Id.IsEmpty()) {
    Errors.Add(FString::Printf(TEXT("fx[%d]: id missing"), Index));
    return false;
  }
  const FString Ctx = TEXT("fx ") + Out.Id;
  if (Ids.Contains(Out.Id)) Errors.Add(Ctx + TEXT(": duplicate id"));
  Ids.Add(Out.Id);
  if (!Obj->TryGetStringField(TEXT("system"), Out.System) || !EnvIsPackagePath(Out.System)) {
    Errors.Add(FString::Printf(TEXT("%s: system '%s' is not a /Game/ package path"), *Ctx, *Out.System));
  } else if (!Out.System.StartsWith(S08EnvLayoutSpec::FxRoot)) {
    Errors.Add(FString::Printf(TEXT("%s: system '%s' is not under %s (cooked derived copies only, never a pack folder in place)"),
                               *Ctx, *Out.System, S08EnvLayoutSpec::FxRoot));
  }
  if (Obj->HasField(TEXT("anchor")) && (!Obj->TryGetStringField(TEXT("anchor"), Out.Anchor) || Out.Anchor.IsEmpty())) {
    Errors.Add(Ctx + TEXT(": anchor is not a prop id string"));
  }
  if (!EnvVec3(Obj, TEXT("loc"), Out.Loc)) Errors.Add(Ctx + TEXT(": loc needs [x, y, z] numbers"));
  double Yaw = 0.0, Scale = 1.0, Warmup = S08EnvLayoutSpec::DefaultFxWarmupS;
  if (!EnvOptionalNumber(Obj, TEXT("yawDeg"), Yaw)) Errors.Add(Ctx + TEXT(": yawDeg is not a number"));
  if (!EnvOptionalNumber(Obj, TEXT("scale"), Scale) || Scale <= 0.0 || Scale > S08EnvLayoutSpec::MaxFxScale) {
    Errors.Add(FString::Printf(TEXT("%s: scale must be a number in (0, %.0f]"), *Ctx, S08EnvLayoutSpec::MaxFxScale));
  }
  if (!EnvOptionalNumber(Obj, TEXT("warmupS"), Warmup) || Warmup < 0.0 || Warmup > S08EnvLayoutSpec::MaxFxWarmupS) {
    Errors.Add(FString::Printf(TEXT("%s: warmupS must be a number in [0, %.0f]"), *Ctx, S08EnvLayoutSpec::MaxFxWarmupS));
  }
  Out.YawDeg = static_cast<float>(Yaw);
  Out.Scale = static_cast<float>(Scale);
  Out.WarmupS = static_cast<float>(Warmup);
  if (Obj->HasField(TEXT("seed"))) {
    double Seed = -1.0;
    if (!EnvRequiredNumber(Obj, TEXT("seed"), Seed) || Seed < 0.0 || Seed > 2147483647.0 || FMath::Frac(Seed) != 0.0) {
      Errors.Add(Ctx + TEXT(": seed must be an integer in [0, 2147483647]"));
    } else {
      Out.bSeedSet = true;
      Out.Seed = static_cast<int32>(Seed);
    }
  }
  if (!EnvOptionalBool(Obj, TEXT("enabled"), Out.bEnabled)) Errors.Add(Ctx + TEXT(": enabled is not a bool"));
  if (Obj->HasField(TEXT("user"))) {
    const TSharedPtr<FJsonObject>* UserObj = nullptr;
    if (!Obj->TryGetObjectField(TEXT("user"), UserObj) || !UserObj || !UserObj->IsValid()) {
      Errors.Add(Ctx + TEXT(": user is not an object"));
    } else if ((*UserObj)->Values.Num() > S08EnvLayoutSpec::MaxFxUserParams) {
      Errors.Add(FString::Printf(TEXT("%s: %d user parameters > %d"), *Ctx, (*UserObj)->Values.Num(),
                                 S08EnvLayoutSpec::MaxFxUserParams));
    } else {
      // UE 5.8: FJsonObject keys are UE::FSharedString; copy into FString-keyed storage (same pattern as BoardArt)
      TMap<FString, TSharedPtr<FJsonValue>> UserValues;
      for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*UserObj)->Values) UserValues.Add(Pair.Key, Pair.Value);
      TArray<FString> Names;
      UserValues.GetKeys(Names);
      Names.Sort();  // deterministic order (the trace and the setter calls)
      TSet<FString> Seen;
      for (const FString& Raw : Names) {
        FS08EnvFxParam P;
        P.Name = Raw.StartsWith(TEXT("User.")) ? Raw.RightChop(5) : Raw;
        if (!EnvIsUserParamName(P.Name) || Seen.Contains(P.Name)) {
          Errors.Add(FString::Printf(TEXT("%s: user parameter name '%s' is invalid or duplicated"), *Ctx, *Raw));
          continue;
        }
        Seen.Add(P.Name);
        if (!EnvUserValue(UserValues[Raw], P)) {
          Errors.Add(FString::Printf(TEXT("%s: user '%s' needs a number, a bool or 2..4 numbers"), *Ctx, *Raw));
          continue;
        }
        Out.User.Add(P);
      }
    }
  }
  return Errors.Num() == Before;
}

// ---- overlay (-EnvLayoutVariant) ----------------------------------------------------------------------------------

/** Entries of a base section array by id (objects with a string id; anything else was rejected by the base parse). */
int32 EnvFindById(const TArray<TSharedPtr<FJsonValue>>& Items, const FString& Id) {
  for (int32 I = 0; I < Items.Num(); ++I) {
    const TSharedPtr<FJsonObject>* Obj = nullptr;
    FString ItemId;
    if (Items[I].IsValid() && Items[I]->TryGetObject(Obj) && Obj && Obj->IsValid() &&
        (*Obj)->TryGetStringField(TEXT("id"), ItemId) && ItemId == Id) {
      return I;
    }
  }
  return INDEX_NONE;
}

/** Applies one overlay section ("props" / "fx": {remove, replace, add}) to the base array of the same name.
 *  Tolerated: removing an id listed in AlreadyDropped (an fx that went with its anchor prop). */
void EnvOverlaySection(const TSharedPtr<FJsonObject>& Base, const TSharedPtr<FJsonObject>& Overlay, const TCHAR* Section,
                       const TArray<FString>& ReplaceFields, const TArray<FString>& AlreadyDropped, int32& Removed,
                       int32& Replaced, int32& Added, TArray<FString>& RemovedIds, TArray<FString>& TouchedIds,
                       TArray<FString>& Errors) {
  if (!Overlay->HasField(Section)) return;
  const TSharedPtr<FJsonObject>* Ops = nullptr;
  if (!Overlay->TryGetObjectField(Section, Ops) || !Ops || !Ops->IsValid()) {
    Errors.Add(FString::Printf(TEXT("overlay %s is not an object {remove, replace, add}"), Section));
    return;
  }
  for (const TPair<FString, TSharedPtr<FJsonValue>>& Op : (*Ops)->Values) {
    if (Op.Key != TEXT("remove") && Op.Key != TEXT("replace") && Op.Key != TEXT("add")) {
      Errors.Add(FString::Printf(TEXT("overlay %s.%s: unknown operation (remove | replace | add)"), Section, *Op.Key));
    }
  }
  TArray<TSharedPtr<FJsonValue>> Items;
  const TArray<TSharedPtr<FJsonValue>>* BaseItems = nullptr;
  if (Base->TryGetArrayField(Section, BaseItems) && BaseItems) Items = *BaseItems;
  // remove
  if ((*Ops)->HasField(TEXT("remove"))) {
    const TArray<TSharedPtr<FJsonValue>>* Ids = nullptr;
    if (!(*Ops)->TryGetArrayField(TEXT("remove"), Ids) || !Ids) {
      Errors.Add(FString::Printf(TEXT("overlay %s.remove is not an array of ids"), Section));
    } else {
      for (const TSharedPtr<FJsonValue>& V : *Ids) {
        FString Id;
        if (!V.IsValid() || !V->TryGetString(Id) || Id.IsEmpty()) {
          Errors.Add(FString::Printf(TEXT("overlay %s.remove: entry is not an id string"), Section));
          continue;
        }
        const int32 At = EnvFindById(Items, Id);
        if (At == INDEX_NONE) {
          if (!AlreadyDropped.Contains(Id)) {
            Errors.Add(FString::Printf(TEXT("overlay %s.remove: '%s' is not in the base layout"), Section, *Id));
          }
          continue;
        }
        Items.RemoveAt(At);
        RemovedIds.Add(Id);
        ++Removed;
      }
    }
  }
  // replace (field by field on the base entry)
  if ((*Ops)->HasField(TEXT("replace"))) {
    const TArray<TSharedPtr<FJsonValue>>* Entries = nullptr;
    if (!(*Ops)->TryGetArrayField(TEXT("replace"), Entries) || !Entries) {
      Errors.Add(FString::Printf(TEXT("overlay %s.replace is not an array"), Section));
    } else {
      for (const TSharedPtr<FJsonValue>& V : *Entries) {
        const TSharedPtr<FJsonObject>* Obj = nullptr;
        FString Id;
        if (!V.IsValid() || !V->TryGetObject(Obj) || !Obj || !Obj->IsValid() ||
            !(*Obj)->TryGetStringField(TEXT("id"), Id) || Id.IsEmpty()) {
          Errors.Add(FString::Printf(TEXT("overlay %s.replace: entry is not an object with an id"), Section));
          continue;
        }
        const int32 At = EnvFindById(Items, Id);
        if (At == INDEX_NONE) {
          Errors.Add(FString::Printf(TEXT("overlay %s.replace: '%s' is not in the base layout (use add)"), Section, *Id));
          continue;
        }
        // a copy of the base entry: the base document object itself stays untouched for the error paths
        TSharedRef<FJsonObject> Merged = MakeShared<FJsonObject>();
        Merged->Values = Items[At]->AsObject()->Values;
        bool bEntryOk = true;
        for (const TPair<FString, TSharedPtr<FJsonValue>>& Field : (*Obj)->Values) {
          if (Field.Key == TEXT("id")) continue;
          if (!ReplaceFields.Contains(Field.Key)) {
            Errors.Add(FString::Printf(TEXT("overlay %s.replace '%s': field '%s' cannot be replaced (%s)"), Section, *Id,
                                       *Field.Key, *FString::Join(ReplaceFields, TEXT(", "))));
            bEntryOk = false;
            continue;
          }
          Merged->SetField(Field.Key, Field.Value);
        }
        if (bEntryOk) {
          Items[At] = MakeShared<FJsonValueObject>(Merged);
          ++Replaced;
          TouchedIds.AddUnique(Id);
        }
      }
    }
  }
  // add
  if ((*Ops)->HasField(TEXT("add"))) {
    const TArray<TSharedPtr<FJsonValue>>* Entries = nullptr;
    if (!(*Ops)->TryGetArrayField(TEXT("add"), Entries) || !Entries) {
      Errors.Add(FString::Printf(TEXT("overlay %s.add is not an array"), Section));
    } else {
      for (const TSharedPtr<FJsonValue>& V : *Entries) {
        const TSharedPtr<FJsonObject>* Obj = nullptr;
        FString Id;
        if (!V.IsValid() || !V->TryGetObject(Obj) || !Obj || !Obj->IsValid() ||
            !(*Obj)->TryGetStringField(TEXT("id"), Id) || Id.IsEmpty()) {
          Errors.Add(FString::Printf(TEXT("overlay %s.add: entry is not an object with an id"), Section));
          continue;
        }
        if (EnvFindById(Items, Id) != INDEX_NONE) {
          Errors.Add(FString::Printf(TEXT("overlay %s.add: '%s' already exists (use replace)"), Section, *Id));
          continue;
        }
        Items.Add(V);
        ++Added;
        TouchedIds.AddUnique(Id);
      }
    }
  }
  if (Items.Num() > 0 || Base->HasField(Section)) Base->SetArrayField(Section, Items);
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
  if (Root->HasField(TEXT("ground"))) {
    // ENV-U10 themed ground (S08EnvGround.h): optional; when present it must be valid like every other section.
    const TSharedPtr<FJsonObject>* GroundObj = nullptr;
    if (!Root->TryGetObjectField(TEXT("ground"), GroundObj) || !GroundObj || !GroundObj->IsValid()) {
      OutErrors.Add(TEXT("ground is not an object"));
    } else {
      S08EnvGround::ParseJson(*GroundObj, Ground, OutErrors);
    }
  }
  if (Root->HasField(TEXT("fx"))) {
    // P5c: optional Niagara fx; anchors must name a prop of this document.
    const TArray<TSharedPtr<FJsonValue>>* FxValues = nullptr;
    if (!Root->TryGetArrayField(TEXT("fx"), FxValues) || !FxValues) {
      OutErrors.Add(TEXT("fx is not an array"));
    } else if (FxValues->Num() > S08EnvLayoutSpec::MaxFx) {
      OutErrors.Add(FString::Printf(TEXT("%d fx > %d"), FxValues->Num(), S08EnvLayoutSpec::MaxFx));
    } else {
      TSet<FString> Ids;
      for (int32 I = 0; I < FxValues->Num(); ++I) {
        const TSharedPtr<FJsonObject>* Obj = nullptr;
        if (!(*FxValues)[I].IsValid() || !(*FxValues)[I]->TryGetObject(Obj) || !Obj || !Obj->IsValid()) {
          OutErrors.Add(FString::Printf(TEXT("fx[%d] is not an object"), I));
          continue;
        }
        FS08EnvFx Entry;
        if (!EnvParseFx(*Obj, I, Ids, Entry, OutErrors)) continue;
        if (!Entry.Anchor.IsEmpty() && !FindProp(Entry.Anchor)) {
          OutErrors.Add(FString::Printf(TEXT("fx %s: anchor '%s' is not a prop id of this layout"), *Entry.Id, *Entry.Anchor));
          continue;
        }
        Fx.Add(Entry);
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

TArray<FString> FS08EnvLayout::UniqueFxSystemPaths() const {
  TArray<FString> Out;
  for (const FS08EnvFx& F : Fx) Out.AddUnique(F.System);
  return Out;
}

const FS08EnvProp* FS08EnvLayout::FindProp(const FString& Id) const {
  return Props.FindByPredicate([&Id](const FS08EnvProp& P) { return P.Id == Id; });
}

FString FS08EnvFxParam::ValueString() const {
  if (Num <= 1) return FString::Printf(TEXT("%g"), Value.X);
  FString Out = TEXT("(");
  for (int32 I = 0; I < Num && I < 4; ++I) Out += FString::Printf(TEXT("%s%g"), I ? TEXT(",") : TEXT(""), Value[I]);
  return Out + TEXT(")");
}

int32 FS08EnvFx::EffectiveSeed() const {
  return bSeedSet ? Seed : static_cast<int32>(FCrc::StrCrc32(*Id) & 0x7FFFFFFFu);
}

int32 FS08EnvFx::WarmupTicks() const {
  return FMath::Max(0, FMath::RoundToInt(WarmupS / S08EnvLayoutSpec::FxWarmupTickS));
}

FTransform FS08EnvFx::Transform(const FS08EnvProp* AnchorProp) const {
  if (!AnchorProp) return FTransform(FRotator(0.0f, YawDeg, 0.0f), Loc, FVector(Scale));
  // an offset from the anchor's pivot, turned with the anchor (not scaled: the offset is authored in uu)
  const FRotator AnchorYaw(0.0f, AnchorProp->YawDeg, 0.0f);
  return FTransform(FRotator(0.0f, AnchorProp->YawDeg + YawDeg, 0.0f), AnchorProp->Loc + AnchorYaw.RotateVector(Loc),
                    FVector(Scale));
}

FString FS08EnvVariantResult::TraceLine(const FString& MapKey) const {
  const TCHAR* Map = MapKey.IsEmpty() ? TEXT("-") : *MapKey;
  if (Name.IsEmpty()) return FString::Printf(TEXT("ARTPREVIEW envlayout variant=none map=%s"), Map);
  return FString::Printf(
      TEXT("ARTPREVIEW envlayout variant=%s map=%s status=%s file=%s sha256=%s propsRemoved=%d propsReplaced=%d propsAdded=%d fxRemoved=%d fxRemovedWithAnchor=%d fxReplaced=%d fxAdded=%d errors=%d%s"),
      *Name, Map, *Status, Path.IsEmpty() ? TEXT("-") : *FPaths::GetCleanFilename(Path),
      Sha256.IsEmpty() ? TEXT("-") : *Sha256, PropsRemoved, PropsReplaced, PropsAdded, FxRemoved, FxRemovedWithAnchor,
      FxReplaced, FxAdded, Errors.Num(), Status == TEXT("ok") ? TEXT("") : TEXT(" fallback=base"));
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
  TArray<FString> All, Files, Overlays;
  IFileManager::Get().FindFiles(All, *FPaths::Combine(Dir, FString(TEXT("*")) + S08EnvLayoutSpec::FileSuffix), true,
                                false);
  All.Sort();
  for (const FString& Name : All) (IsOverlayFileName(Name) ? Overlays : Files).Add(Name);
  // P5c: overlays / the variant / -ArtPreviewNoFx only add fields when present (the line stays byte-identical otherwise)
  FString Extra;
  if (Overlays.Num() > 0) Extra += TEXT(" overlays=") + FString::Join(Overlays, TEXT("+"));
  const FString Variant = VariantFromCommandLine();
  if (!Variant.IsEmpty()) Extra += TEXT(" variant=") + Variant;
  if (FxOptOut()) Extra += FString::Printf(TEXT(" fx=off(-%s)"), S08EnvLayoutSpec::NoFxFlagName);
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW envlayout enabled dir=%s source=%s files=%d%s%s%s"),
                                   *S08EnvLayoutPrivate::EnvDisplayPath(Dir), bOverride ? TEXT("override") : TEXT("pak"),
                                   Files.Num(), Files.Num() ? TEXT(" names=") : TEXT(""),
                                   *FString::Join(Files, TEXT("+")), *Extra));
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

bool FxOptOut() { return FParse::Param(FCommandLine::Get(), S08EnvLayoutSpec::NoFxFlagName); }

FString VariantFromCommandLine() {
  FString Name;
  FParse::Value(FCommandLine::Get(), S08EnvLayoutSpec::VariantParam, Name);
  return Name.TrimStartAndEnd();
}

bool IsVariantName(const FString& Name) {
  return Name.Len() <= 32 && S08EnvLayoutPrivate::EnvIsKey(Name, true);
}

FString OverlayFileFor(const FString& Dir, const FString& MapKey, const FString& Variant) {
  return FPaths::Combine(Dir, MapKey + TEXT(".") + Variant + S08EnvLayoutSpec::FileSuffix);
}

bool IsOverlayFileName(const FString& FileName) {
  const FString Name = FPaths::GetCleanFilename(FileName);
  if (!Name.EndsWith(S08EnvLayoutSpec::FileSuffix)) return false;
  const FString Stem = Name.LeftChop(FCString::Strlen(S08EnvLayoutSpec::FileSuffix));
  return Stem.Contains(TEXT("."));
}

bool MergeOverlay(const FString& BaseText, const FString& OverlayText, const FString& MapKey, const FString& Variant,
                  FS08EnvLayout& Out, FS08EnvVariantResult& R) {
  using namespace S08EnvLayoutPrivate;
  const int32 Before = R.Errors.Num();
  TSharedPtr<FJsonObject> Base, Overlay;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(BaseText, Base, Problem) || !Base.IsValid()) {
    R.Errors.Add(TEXT("base layout: invalid JSON: ") + Problem);
    return false;
  }
  if (!FS08Contracts::TryParseJsonObject(OverlayText, Overlay, Problem) || !Overlay.IsValid()) {
    R.Errors.Add(TEXT("overlay: invalid JSON: ") + Problem);
    return false;
  }
  FString Schema, Map, Name, BoardId, BaseBoardId;
  if (!Overlay->TryGetStringField(TEXT("schema"), Schema) || Schema != S08EnvLayoutSpec::OverlaySchema) {
    R.Errors.Add(FString::Printf(TEXT("overlay schema '%s' is not %s"), *Schema, S08EnvLayoutSpec::OverlaySchema));
    return false;
  }
  if (!Overlay->TryGetStringField(TEXT("map"), Map) || Map != MapKey) {
    R.Errors.Add(FString::Printf(TEXT("overlay map '%s' != '%s'"), *Map, *MapKey));
  }
  if (!Overlay->TryGetStringField(TEXT("variant"), Name) || Name != Variant) {
    R.Errors.Add(FString::Printf(TEXT("overlay variant '%s' != '%s'"), *Name, *Variant));
  }
  if (Overlay->HasField(TEXT("boardId")) &&
      (!Overlay->TryGetStringField(TEXT("boardId"), BoardId) || !Base->TryGetStringField(TEXT("boardId"), BaseBoardId) ||
       BoardId != BaseBoardId)) {
    R.Errors.Add(FString::Printf(TEXT("overlay boardId '%s' is not the base layout's '%s'"), *BoardId, *BaseBoardId));
  }
  for (const TCHAR* Fixed : {TEXT("lights"), TEXT("ground"), TEXT("tray"), TEXT("apron")}) {
    if (Overlay->HasField(Fixed)) {
      R.Errors.Add(FString::Printf(TEXT("overlay cannot change '%s' (props and fx only; the light budget, the ground "
                                        "and the tray stay the base layout's)"),
                                   Fixed));
    }
  }
  if (R.Errors.Num() != Before) return false;
  // props: remove -> replace -> add; the fx anchored on a removed prop go with it
  TArray<FString> RemovedProps, RemovedFx, NoneDropped, TouchedProps, TouchedFx;
  EnvOverlaySection(Base, Overlay, TEXT("props"),
                    {TEXT("mesh"), TEXT("loc"), TEXT("yawDeg"), TEXT("scale"), TEXT("castShadow")}, NoneDropped,
                    R.PropsRemoved, R.PropsReplaced, R.PropsAdded, RemovedProps, TouchedProps, R.Errors);
  TArray<FString> DroppedWithAnchor;
  const TArray<TSharedPtr<FJsonValue>>* BaseFx = nullptr;
  if (RemovedProps.Num() > 0 && Base->TryGetArrayField(TEXT("fx"), BaseFx) && BaseFx) {
    TArray<TSharedPtr<FJsonValue>> Kept;
    for (const TSharedPtr<FJsonValue>& V : *BaseFx) {
      const TSharedPtr<FJsonObject>* Obj = nullptr;
      FString Anchor, Id;
      if (V.IsValid() && V->TryGetObject(Obj) && Obj && Obj->IsValid() &&
          (*Obj)->TryGetStringField(TEXT("anchor"), Anchor) && RemovedProps.Contains(Anchor)) {
        (*Obj)->TryGetStringField(TEXT("id"), Id);
        DroppedWithAnchor.Add(Id);
        ++R.FxRemovedWithAnchor;
        continue;
      }
      Kept.Add(V);
    }
    Base->SetArrayField(TEXT("fx"), Kept);
  }
  EnvOverlaySection(Base, Overlay, TEXT("fx"),
                    {TEXT("system"), TEXT("anchor"), TEXT("loc"), TEXT("yawDeg"), TEXT("scale"), TEXT("seed"),
                     TEXT("warmupS"), TEXT("enabled"), TEXT("user")},
                    DroppedWithAnchor, R.FxRemoved, R.FxReplaced, R.FxAdded, RemovedFx, TouchedFx, R.Errors);
  if (R.Errors.Num() != Before) return false;
  FString MergedText;
  const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&MergedText);
  if (!FJsonSerializer::Serialize(Base.ToSharedRef(), Writer)) {
    R.Errors.Add(TEXT("merged layout: JSON serialisation failed"));
    return false;
  }
  FS08EnvLayout Merged;
  TArray<FString> ParseErrors;
  if (!Merged.ParseJson(MergedText, ParseErrors)) {
    for (const FString& E : ParseErrors) R.Errors.Add(TEXT("merged layout: ") + E);
    return false;
  }
  Out = MoveTemp(Merged);
  for (const FString& Id : TouchedProps) Out.OverlayPropIds.Add(Id);
  for (const FString& Id : TouchedFx) Out.OverlayFxIds.Add(Id);
  return true;
}

FS08EnvVariantResult ApplyVariant(const FString& Dir, const FString& MapKey, const FString& Variant,
                                  FS08EnvLayout& InOutLayout) {
  FS08EnvVariantResult R;
  R.Name = Variant;
  if (Variant.IsEmpty()) {
    R.Status = TEXT("none");
    return R;
  }
  if (!IsVariantName(Variant)) {
    R.Status = TEXT("invalid");
    R.Errors.Add(FString::Printf(TEXT("variant name '%s' is not [a-z0-9-]{1,32}"), *Variant));
    return R;
  }
  R.Path = OverlayFileFor(Dir, MapKey, Variant);
  if (!FPaths::FileExists(R.Path)) {
    R.Status = TEXT("absent");
    return R;
  }
  TArray<uint8> OverlayBytes, BaseBytes;
  if (!FFileHelper::LoadFileToArray(OverlayBytes, *R.Path)) {
    R.Status = TEXT("invalid");
    R.Errors.Add(FString::Printf(TEXT("cannot read %s"), *R.Path));
    return R;
  }
  R.Sha256 = S08Sha256Hex(OverlayBytes.GetData(), OverlayBytes.Num());
  if (InOutLayout.SourcePath.IsEmpty() || !FFileHelper::LoadFileToArray(BaseBytes, *InOutLayout.SourcePath)) {
    R.Status = TEXT("invalid");
    R.Errors.Add(TEXT("the base layout file cannot be re-read for the merge"));
    return R;
  }
  FString OverlayText, BaseText;
  FFileHelper::BufferToString(OverlayText, OverlayBytes.GetData(), OverlayBytes.Num());
  FFileHelper::BufferToString(BaseText, BaseBytes.GetData(), BaseBytes.Num());
  FS08EnvLayout Merged;
  if (!MergeOverlay(BaseText, OverlayText, MapKey, Variant, Merged, R)) {
    R.Status = TEXT("invalid");
    return R;
  }
  Merged.SourcePath = InOutLayout.SourcePath;
  Merged.SourceSha256 = InOutLayout.SourceSha256;
  Merged.Variant = Variant;
  Merged.OverlayPath = R.Path;
  Merged.OverlaySha256 = R.Sha256;
  InOutLayout = MoveTemp(Merged);
  R.Status = TEXT("ok");
  return R;
}

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
  Names.RemoveAll([](const FString& Name) { return IsOverlayFileName(Name); });  // P5c: overlays are never a base
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
    S.PropComponentIds.Add(P.Id);
    ++S.Props;
    S.SpawnedPropIds.Add(P.Id);
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
    S.LightComponentIds.Add(L.Id);
    ++S.Lights;
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW envlayout light id=%s kind=point at=%s intensity=%g units=%s radius=%g color=%s shadow=0"),
        *L.Id, *EnvVec(L.Loc), L.IntensityCd, bCandelas ? TEXT("candelas") : TEXT("unitless-legacy"), L.RadiusUU,
        *L.ColorHex()));
  }
  return S;
}

}  // namespace S08EnvLayout

// ---- P5c fx (Niagara) -------------------------------------------------------------------------------------------

FS08EnvFxOptions FS08EnvFxOptions::FromCommandLine() {
  FS08EnvFxOptions O;
  const TCHAR* Cmd = FCommandLine::Get();
  O.bSpawn = !S08EnvLayout::FxOptOut();
  O.bBench = FParse::Param(Cmd, S08EnvLayoutSpec::BenchFlagName);
  // -Bench frames must be reproducible: freeze after the warmup unless -EnvFxLive; -EnvFxFreeze anywhere.
  O.bFreeze = (O.bBench && !FParse::Param(Cmd, S08EnvLayoutSpec::FxLiveFlagName)) ||
              FParse::Param(Cmd, S08EnvLayoutSpec::FxFreezeFlagName);
  return O;
}

FString FS08EnvFxOptions::Mode() const {
  if (!bSpawn) return TEXT("off");
  if (!bActivate) return TEXT("inactive");
  return bFreeze ? TEXT("frozen") : TEXT("live");
}

namespace S08EnvLayoutPrivate {
struct FEnvFxSystemInfo {
  int32 Emitters = 0;
  int32 Gpu = 0;
  int32 LightRenderers = 0;
  int32 ComponentRenderers = 0;
  bool bDeterminism = false;
};

/** Enabled emitters, GPU sims and the renderers that would add dynamic lights (Light; Component = may spawn lights). */
FEnvFxSystemInfo EnvInspectSystem(const UNiagaraSystem& System) {
  FEnvFxSystemInfo I;
  for (const FNiagaraEmitterHandle& H : System.GetEmitterHandles()) {
    if (!H.GetIsEnabled()) continue;
    ++I.Emitters;
    const FVersionedNiagaraEmitterData* D = H.GetEmitterData();
    if (!D) continue;  // a stateless emitter: no data-driven renderers to check here
    if (D->SimTarget == ENiagaraSimTarget::GPUComputeSim) ++I.Gpu;
    for (const UNiagaraRendererProperties* R : D->GetRenderers()) {
      if (!R || !R->GetIsEnabled()) continue;
      if (R->IsA<UNiagaraLightRendererProperties>()) {
        ++I.LightRenderers;
      } else if (R->IsA<UNiagaraComponentRendererProperties>()) {
        ++I.ComponentRenderers;
      }
    }
  }
  I.bDeterminism = System.NeedsDeterminism();
  return I;
}

/** Sets the user parameters with the setter of the exposed parameter's type; unknown names / wrong arity are counted. */
void EnvApplyUser(UNiagaraComponent& C, const UNiagaraSystem& System, const TArray<FS08EnvFxParam>& User, int32& OutSet,
                  int32& OutMissing, TArray<FString>& OutTrace) {
  const FNiagaraUserRedirectionParameterStore& Exposed = System.GetExposedParameters();
  for (const FS08EnvFxParam& P : User) {
    const FName Full(*(TEXT("User.") + P.Name));
    const FNiagaraVariableBase* Var = nullptr;
    for (const FNiagaraVariableWithOffset& V : Exposed.ReadParameterVariables()) {
      if (V.GetName() == Full) {
        Var = &V;
        break;
      }
    }
    bool bOk = Var != nullptr;
    if (bOk) {
      const FNiagaraTypeDefinition& Type = Var->GetType();
      const FVector4& X = P.Value;
      if (Type == FNiagaraTypeDefinition::GetFloatDef() && P.Num == 1) {
        C.SetVariableFloat(Full, static_cast<float>(X.X));
      } else if (Type == FNiagaraTypeDefinition::GetIntDef() && P.Num == 1) {
        C.SetVariableInt(Full, FMath::RoundToInt(X.X));
      } else if (Type == FNiagaraTypeDefinition::GetBoolDef() && P.Num == 1) {
        C.SetVariableBool(Full, X.X != 0.0);
      } else if (Type == FNiagaraTypeDefinition::GetVec2Def() && P.Num == 2) {
        C.SetVariableVec2(Full, FVector2D(X.X, X.Y));
      } else if (Type == FNiagaraTypeDefinition::GetVec3Def() && P.Num == 3) {
        C.SetVariableVec3(Full, FVector(X.X, X.Y, X.Z));
      } else if (Type == FNiagaraTypeDefinition::GetPositionDef() && P.Num == 3) {
        C.SetVariablePosition(Full, FVector(X.X, X.Y, X.Z));
      } else if (Type == FNiagaraTypeDefinition::GetVec4Def() && P.Num == 4) {
        C.SetVariableVec4(Full, X);
      } else if (Type == FNiagaraTypeDefinition::GetColorDef() && (P.Num == 3 || P.Num == 4)) {
        C.SetVariableLinearColor(Full, FLinearColor(static_cast<float>(X.X), static_cast<float>(X.Y),
                                                    static_cast<float>(X.Z), P.Num == 4 ? static_cast<float>(X.W) : 1.0f));
      } else {
        bOk = false;
      }
    }
    OutSet += bOk ? 1 : 0;
    OutMissing += bOk ? 0 : 1;
    OutTrace.Add(FString::Printf(TEXT("%s:%s%s"), *P.Name, *P.ValueString(),
                                 bOk ? TEXT("") : (Var ? TEXT(":type-mismatch") : TEXT(":missing"))));
  }
}

/** Live particles of an activated component (0 without a system instance). */
int32 EnvLiveParticles(UNiagaraComponent& C) {
  int32 Count = 0;
  FNiagaraSystemInstanceControllerPtr Controller = C.GetSystemInstanceController();
  if (!Controller.IsValid()) return 0;
  if (FNiagaraSystemInstance* Instance = Controller->GetSystemInstance_Unsafe()) {
    for (const FNiagaraEmitterInstanceRef& Emitter : Instance->GetEmitters()) Count += Emitter->GetNumParticles();
  }
  return Count;
}
}  // namespace S08EnvLayoutPrivate

namespace S08EnvLayout {

FS08EnvFxStats SpawnFx(const FS08EnvLayout& Layout, AActor& Owner, USceneComponent* Parent, const FVector2D& MapHalf,
                       const FVector2D& FrameHalf, const TSet<FString>& SpawnedPropIds,
                       const FS08EnvFxOptions& Options, TArray<TWeakObjectPtr<UNiagaraComponent>>& OutFx) {
  using namespace S08EnvLayoutPrivate;
  FS08EnvFxStats S;
  S.LayoutFx = Layout.Fx.Num();
  S.Mode = Options.Mode();
  if (!Options.bSpawn) return S;
  USceneComponent* Attach = Parent ? Parent : Owner.GetRootComponent();
  TMap<FString, UNiagaraSystem*> Loaded;  // nullptr = tried, missing
  TMap<FString, TArray<FString>> MissingIds;
  for (const FS08EnvFx& F : Layout.Fx) {
    if (!F.bEnabled) {
      ++S.SkippedDisabled;
      FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW envlayout fx skipped id=%s reason=disabled"), *F.Id));
      continue;
    }
    const FS08EnvProp* AnchorProp = nullptr;
    if (!F.Anchor.IsEmpty()) {
      AnchorProp = Layout.FindProp(F.Anchor);
      if (!AnchorProp || !SpawnedPropIds.Contains(F.Anchor)) {
        ++S.SkippedAnchor;
        FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW envlayout fx skipped id=%s reason=anchor-not-spawned anchor=%s"),
                                         *F.Id, *F.Anchor));
        continue;
      }
    }
    const FTransform T = F.Transform(AnchorProp);
    const FVector At = T.GetTranslation();
    if (PivotInsideMap(At, MapHalf)) {
      // the circles / labels of the painted map stay readable: no fx emitter on the map
      ++S.SkippedInsideMap;
      FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW envlayout fx skipped id=%s reason=inside-map at=%s mapHalf=%.1fx%.1f"),
                                       *F.Id, *EnvVec(At), MapHalf.X, MapHalf.Y));
      continue;
    }
    UNiagaraSystem* System = nullptr;
    if (UNiagaraSystem* const* Pre = Options.Preloaded.Find(F.System)) {
      System = *Pre;
    } else if (UNiagaraSystem** Found = Loaded.Find(F.System)) {
      System = *Found;
    } else {
      // as the props: uncooked runs ask the package first (no loader warning in the automation log)
      const bool bMayExist =
          FPlatformProperties::RequiresCookedData() || FPackageName::DoesPackageExist(EnvPackageOf(F.System));
      System = bMayExist ? LoadObject<UNiagaraSystem>(nullptr, *F.System, nullptr, LOAD_NoWarn) : nullptr;
      Loaded.Add(F.System, System);
    }
    if (!System) {
      MissingIds.FindOrAdd(F.System).Add(F.Id);
      ++S.SkippedMissing;
      continue;
    }
    const FEnvFxSystemInfo Info = EnvInspectSystem(*System);
    if (Info.LightRenderers > 0 || Info.ComponentRenderers > 0) {
      // budget: 1 key + <= 6 layout / profile points; VFX never add dynamic lights
      ++S.SkippedLightRenderer;
      const FString Line = FString::Printf(
          TEXT("ARTPREVIEW envlayout fx skipped id=%s reason=light-renderer system=%s lightRenderers=%d componentRenderers=%d (disable them in tools/art/env_kit/ue_import_fab_fx.py)"),
          *F.Id, *FPackageName::GetShortName(EnvPackageOf(F.System)), Info.LightRenderers, Info.ComponentRenderers);
      UE_LOG(LogTemp, Display, TEXT("%s"), *Line);
      FS08Trace::Write(Line);
      continue;
    }
    const bool bNearBand = At.Y > FrameHalf.Y && FMath::Abs(At.X) < FrameHalf.X;
    S.NearBand += bNearBand ? 1 : 0;
    const FName Name = MakeUniqueObjectName(&Owner, UNiagaraComponent::StaticClass(),
                                            FName(*(TEXT("EnvFx_") + EnvSafeName(F.Id))));
    UNiagaraComponent* C = NewObject<UNiagaraComponent>(&Owner, Name);
    C->SetAutoActivate(false);
    C->SetAsset(System);
    C->SetupAttachment(Attach);
    C->SetRelativeTransform(T);
    // decor only: no collision / navigation / shadow; never culled by the effect type (reproducible frames)
    C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    C->SetCanEverAffectNavigation(false);
    C->SetCastShadow(false);
    C->SetAllowScalability(false);
    const int32 Seed = F.EffectiveSeed();
    C->SetRandomSeedOffset(Seed);
    int32 UserSet = 0, UserMissing = 0;
    TArray<FString> UserTrace;
    EnvApplyUser(*C, *System, F.User, UserSet, UserMissing, UserTrace);
    C->RegisterComponent();
    const int32 Ticks = F.WarmupTicks();
    int32 Particles = 0;
    if (Options.bActivate) {
      C->Activate(true);
      if (Ticks > 0) C->AdvanceSimulation(Ticks, S08EnvLayoutSpec::FxWarmupTickS);
      if (Options.bFreeze) {
        // ENV-MAPS P7c: frozen = time dilation 0 (the component ticks with dt 0: no emitter update, the warmed particles
        // stay as they are, but every tick re-sends the render data), NOT SetPaused. Root cause, measured in the cooked
        // client (P6 / P7b packaged -Bench, P7c experiments): with PSO precaching (on in cooked builds, off in the
        // editor) UNiagaraComponent::CreateSceneProxy is skipped while the system's PSOs are still compiling (the first
        // component of a system usually gets its proxy before the precache request is in flight, every later one does
        // not); the proxy is created a few frames later, but a PAUSED instance never ticks again, so the late proxy never
        // receives dynamic data: the brazier / P6 campfire-w / every lantern flame after the first drew nothing although
        // the trace counted their particles. -dpcvars=r.PSOPrecaching=0 showed them; SetForceSolo did not.
        C->SetCustomTimeDilation(0.0f);
        ++S.Frozen;
      }
      Particles = EnvLiveParticles(*C);
    }
    OutFx.Add(C);
    S.FxComponentIds.Add(F.Id);
    ++S.Fx;
    S.Particles += Particles;
    S.UserSet += UserSet;
    S.UserMissing += UserMissing;
    S.GpuEmitters += Info.Gpu;
    const bool bDeterministic = Info.bDeterminism && Info.Gpu == 0;
    S.NonDeterministic += bDeterministic ? 0 : 1;
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW envlayout fx id=%s system=%s anchor=%s at=%s yaw=%.1f scale=%.3f seed=%d warmup=%.2fs ticks=%d mode=%s particles=%d emitters=%d gpuEmitters=%d deterministic=%d nearBand=%d user=%s"),
        *F.Id, *FPackageName::GetShortName(EnvPackageOf(F.System)), F.Anchor.IsEmpty() ? TEXT("-") : *F.Anchor,
        *EnvVec(At), T.Rotator().Yaw, F.Scale, Seed, F.WarmupS, Ticks, *S.Mode, Particles, Info.Emitters, Info.Gpu,
        bDeterministic ? 1 : 0, bNearBand ? 1 : 0, UserTrace.Num() ? *FString::Join(UserTrace, TEXT("+")) : TEXT("-")));
  }
  for (const TPair<FString, TArray<FString>>& Missing : MissingIds) {
    ++S.MissingSystems;
    S.MissingPaths.Add(Missing.Key);
    const FString Line = FString::Printf(
        TEXT("ARTPREVIEW envlayout fx missing system=%s fx=%s (skipped; run tools/art/env_kit/ue_import_fab_fx.py)"),
        *Missing.Key, *FString::Join(Missing.Value, TEXT("+")));
    UE_LOG(LogTemp, Display, TEXT("%s"), *Line);
    FS08Trace::Write(Line);
  }
  return S;
}

int32 ClearFx(TArray<TWeakObjectPtr<UNiagaraComponent>>& Fx) {
  int32 Count = 0;
  for (const TWeakObjectPtr<UNiagaraComponent>& C : Fx) {
    if (UNiagaraComponent* Live = C.Get()) {
      Live->DestroyComponent();
      ++Count;
    }
  }
  Fx.Reset();
  return Count;
}

FString FxSummaryLine(const FString& MapKey, const FS08EnvFxStats& S) {
  return FString::Printf(
      TEXT("ARTPREVIEW envlayout fx map=%s fx=%d layoutFx=%d missingSystems=%d skippedMissing=%d skippedDisabled=%d skippedAnchor=%d skippedInsideMap=%d skippedLightRenderer=%d nearBand=%d gpuEmitters=%d nonDeterministic=%d particles=%d userSet=%d userMissing=%d mode=%s still=%d"),
      MapKey.IsEmpty() ? TEXT("-") : *MapKey, S.Fx, S.LayoutFx, S.MissingSystems, S.SkippedMissing, S.SkippedDisabled,
      S.SkippedAnchor, S.SkippedInsideMap, S.SkippedLightRenderer, S.NearBand, S.GpuEmitters, S.NonDeterministic,
      S.Particles, S.UserSet, S.UserMissing, S.Mode.IsEmpty() ? TEXT("-") : *S.Mode, S.Frozen);
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
    if (Runtime.bApplied || Props.Num() > 0 || Lights.Num() > 0 || Runtime.Ground.Num() > 0 || Runtime.Fx.Num() > 0) {
      const int32 P = Props.Num(), L = Lights.Num();
      Clear(Props, Lights);
      const int32 G = S08EnvGround::Clear(Runtime.Ground);
      const int32 Fx = ClearFx(Runtime.Fx);
      FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW envlayout off map=%s reason=%s clearedProps=%d clearedLights=%d clearedGround=%d%s"),
                                       Runtime.MapKey.IsEmpty() ? TEXT("-") : *Runtime.MapKey,
                                       !Request.bEnabled ? TEXT("gate-off") : TEXT("no-map-image-board"), P, L, G,
                                       Fx > 0 ? *FString::Printf(TEXT(" clearedFx=%d"), Fx) : TEXT("")));
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
  // P5c: the -EnvLayoutVariant overlay (a missing / invalid one falls back to the base) and the fx mode are part of
  // the same-layout key; without a variant and fx the key is the previous one plus constant suffixes.
  const FString VariantName = Request.Variant.IsSet() ? Request.Variant.GetValue() : VariantFromCommandLine();
  const FS08EnvFxOptions FxOptions =
      Request.FxOptions.IsSet() ? Request.FxOptions.GetValue() : FS08EnvFxOptions::FromCommandLine();
  FS08EnvVariantResult Variant;
  if (bOk) {
    Variant = ApplyVariant(Dir, Request.MapKey, VariantName, Layout);
  } else {
    Variant.Name = VariantName;
    Variant.Status = TEXT("none");
  }
  const FString Key = FString::Printf(TEXT("%s|%s|%s|%s|variant=%s:%s:%s|fx=%s"), *Request.MapKey, *Request.RoomBoardId,
                                      bOk ? *Layout.SourceSha256 : (bAbsent ? TEXT("absent") : TEXT("invalid")), *Dir,
                                      *Variant.Name, *Variant.Status, *Variant.Sha256, *FxOptions.Mode());
  if (Runtime.bApplied && Runtime.Key == Key) {
    return;  // the same layout bytes on the same board again: the components (or the traced failure) stay as they are
  }
  Clear(Props, Lights);
  S08EnvGround::Clear(Runtime.Ground);  // before the reset below forgets them
  ClearFx(Runtime.Fx);
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
  Runtime.Variant = Variant;
  FS08Trace::Write(Variant.TraceLine(Request.MapKey));
  for (int32 I = 0; I < Variant.Errors.Num() && I < 8; ++I) {
    FS08Trace::Write(TEXT("ARTPREVIEW envlayout variant error: ") + Variant.Errors[I]);
  }
  if (Variant.Status == TEXT("invalid")) {
    UE_LOG(LogTemp, Display, TEXT("%s"), *Variant.TraceLine(Request.MapKey));
  }
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
  if (Layout.Ground.bSet) {
    // ENV-U10: the themed ground on the same tray top rectangle the diorama tray is placed with (ApplyTray / TrayFit).
    Runtime.GroundStats =
        S08EnvGround::Spawn(Layout.Ground, Owner, Parent, TrayTop, Request.FrameHalf, Runtime.Ground);
    const FString GroundLine = S08EnvGround::TraceLine(Request.MapKey, Layout.Ground, Runtime.GroundStats);
    if (Runtime.GroundStats.Status != TEXT("ok")) {
      UE_LOG(LogTemp, Display, TEXT("%s (import: tools/art/env_kit/ue_import_env_ground.py)"), *GroundLine);
    }
    FS08Trace::Write(GroundLine);
  }
  if (Layout.Fx.Num() > 0) {
    // P5c: the Niagara fx after the props (anchors) and the ground; a layout without "fx" writes nothing here.
    Runtime.FxStats = SpawnFx(Layout, Owner, Parent, Request.MapHalf, Request.FrameHalf, Runtime.Stats.SpawnedPropIds,
                              FxOptions, Runtime.Fx);
    const FString FxLine = FxSummaryLine(Request.MapKey, Runtime.FxStats);
    UE_LOG(LogTemp, Display, TEXT("%s"), *FxLine);
    FS08Trace::Write(FxLine);
  }
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

bool ApplyTrayT2(const FS08EnvLayoutRuntime& Runtime, const FVector2D& FrameHalf, FVector2D& InOutHalf,
                 float& InOutOffsetY, FString& OutSource) {
  if (!Runtime.bApplied || !Runtime.bLayoutValid) return false;
  FVector2D Half, Offset;
  FString Source, Reason;
  if (!TrayFit(Runtime.Layout, FrameHalf, Half, Offset, Source, Reason)) {
    if (Runtime.Layout.Tray.bSet || Runtime.Layout.Apron.bSet) {
      FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW envlayout tray map=%s mesh=T2 source=default refused=%s"),
                                       *Runtime.MapKey, *Reason));
    }
    return false;
  }
  // TrayFit inverted S08Diorama::FitTray; the forward fit is the layout's outer tray (halfX x halfY at (0, offsetY)).
  const S08Diorama::FTrayFit Outer = S08Diorama::FitTray(Half, Offset);
  float MismatchUU = 0.0f;
  S08Diorama::FitTrayT2(Outer.WorldHalf, static_cast<float>(Offset.Y), MismatchUU);
  InOutHalf = Outer.WorldHalf;
  InOutOffsetY = static_cast<float>(Offset.Y);
  OutSource = Source;
  FS08Trace::Write(FString::Printf(
      TEXT("ARTPREVIEW envlayout tray map=%s source=%s outerHalf=%.1fx%.1f offsetY=%.1f frameHalf=%.1fx%.1f mesh=T2 t2Top=%.1fx%.1f mismatchUU=%.1f"),
      *Runtime.MapKey, *Source, Outer.WorldHalf.X, Outer.WorldHalf.Y, Offset.Y, FrameHalf.X, FrameHalf.Y,
      S08Diorama::T2TopHalfX, S08Diorama::T2TopHalfY, MismatchUU));
  return true;
}

}  // namespace S08EnvLayout

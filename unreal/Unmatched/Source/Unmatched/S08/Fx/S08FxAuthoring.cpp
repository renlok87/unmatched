// FX-03 (Z-2 review fix 8): see S08FxAuthoring.h.
#include "S08FxAuthoring.h"

#include "Dom/JsonObject.h"
#include "Misc/PackageName.h"
#include "NiagaraEffectType.h"
#include "NiagaraSystem.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

FString US08FxAuthoringLibrary::SetEffectTypeCaps(const FString& EffectTypePath, int32 MaxInstances) {
  TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
  Report->SetStringField(TEXT("effectType"), EffectTypePath);
  bool bOk = false;
#if WITH_EDITOR
  if (!EffectTypePath.StartsWith(TEXT("/Game/S08/FX/"))) {
    Report->SetStringField(TEXT("error"), TEXT("refused: only /Game/S08/FX/ effect types"));
  } else {
    int32 Dot = INDEX_NONE;
    const FString ObjectPath = EffectTypePath.FindChar(TEXT('.'), Dot)
        ? EffectTypePath : EffectTypePath + TEXT(".") + FPackageName::GetShortName(EffectTypePath);
    UNiagaraEffectType* Type = LoadObject<UNiagaraEffectType>(nullptr, *ObjectPath);
    if (!Type) {
      Report->SetStringField(TEXT("error"), TEXT("not a Niagara effect type"));
    } else {
      Type->Modify();
      Type->CullReaction = ENiagaraCullReaction::Deactivate;
      TArray<FNiagaraSystemScalabilitySettings>& Settings = Type->SystemScalabilitySettings.Settings;
      if (Settings.Num() == 0) Settings.AddDefaulted();
      for (FNiagaraSystemScalabilitySettings& S : Settings) {
        S.bCullMaxInstanceCount = true;
        S.MaxInstances = MaxInstances;
        S.bCullPerSystemMaxInstanceCount = true;
        S.MaxSystemInstances = MaxInstances;
      }
      FProperty* Prop = UNiagaraEffectType::StaticClass()->FindPropertyByName(TEXT("SystemScalabilitySettings"));
      FPropertyChangedEvent Event(Prop);
      Type->PostEditChangeProperty(Event);
      Type->MarkPackageDirty();
      Report->SetNumberField(TEXT("entries"), Settings.Num());
      Report->SetNumberField(TEXT("maxInstances"), Settings[0].MaxInstances);
      Report->SetNumberField(TEXT("maxSystemInstances"), Settings[0].MaxSystemInstances);
      Report->SetStringField(TEXT("cullReaction"), TEXT("Deactivate"));
      bOk = true;
    }
  }
#else
  Report->SetStringField(TEXT("error"), TEXT("editor only"));
#endif
  Report->SetBoolField(TEXT("ok"), bOk);
  FString Out;
  const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Out);
  FJsonSerializer::Serialize(Report, Writer);
  return Out;
}

FString US08FxAuthoringLibrary::SetSystemFixedBounds(const FString& SystemPath, float HalfExtent) {
  TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
  Report->SetStringField(TEXT("system"), SystemPath);
  bool bOk = false;
#if WITH_EDITOR
  int32 Dot = INDEX_NONE;
  const FString ObjectPath = SystemPath.FindChar(TEXT('.'), Dot)
      ? SystemPath : SystemPath + TEXT(".") + FPackageName::GetShortName(SystemPath);
  UNiagaraSystem* System = SystemPath.StartsWith(TEXT("/Game/S08/FX/"))
      ? LoadObject<UNiagaraSystem>(nullptr, *ObjectPath) : nullptr;
  if (!System) {
    Report->SetStringField(TEXT("error"), TEXT("not a /Game/S08/FX/ Niagara system"));
  } else {
    System->Modify();
    System->bFixedBounds = 1;
    System->SetFixedBounds(FBox(FVector(-HalfExtent), FVector(HalfExtent)));
    System->MarkPackageDirty();
    Report->SetBoolField(TEXT("fixedBounds"), System->bFixedBounds != 0);
    Report->SetNumberField(TEXT("halfExtent"), HalfExtent);
    bOk = true;
  }
#else
  Report->SetStringField(TEXT("error"), TEXT("editor only"));
#endif
  Report->SetBoolField(TEXT("ok"), bOk);
  FString Out;
  const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Out);
  FJsonSerializer::Serialize(Report, Writer);
  return Out;
}

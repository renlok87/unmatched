// FX-03 (Z-2 review fix 8): see S08FxAuthoring.h.
#include "S08FxAuthoring.h"

#include "Dom/JsonObject.h"
#include "Misc/PackageName.h"
#include "NiagaraEffectType.h"
#include "NiagaraEmitter.h"
#include "NiagaraEmitterHandle.h"
#include "NiagaraMeshRendererProperties.h"
#include "NiagaraRibbonRendererProperties.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "NiagaraSpriteRendererProperties.h"
#include "NiagaraSystem.h"
#include "NiagaraCommon.h"
#include "NiagaraTypes.h"
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

FString US08FxAuthoringLibrary::SetSpriteSubImage(const FString& SystemPath, const FString& EmitterName, int32 X,
                                                 int32 Y) {
  TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
  Report->SetStringField(TEXT("system"), SystemPath);
  Report->SetStringField(TEXT("emitter"), EmitterName);
  int32 Renderers = 0;
#if WITH_EDITOR
  int32 Dot = INDEX_NONE;
  const FString ObjectPath = SystemPath.FindChar(TEXT('.'), Dot)
      ? SystemPath : SystemPath + TEXT(".") + FPackageName::GetShortName(SystemPath);
  UNiagaraSystem* System = SystemPath.StartsWith(TEXT("/Game/S08/FX/"))
      ? LoadObject<UNiagaraSystem>(nullptr, *ObjectPath) : nullptr;
  if (System) {
    for (FNiagaraEmitterHandle& Handle : System->GetEmitterHandles()) {
      if (Handle.GetName().ToString() != EmitterName) continue;
      FVersionedNiagaraEmitterData* Data = Handle.GetEmitterData();
      if (!Data) continue;
      for (UNiagaraRendererProperties* R : Data->GetRenderers()) {
        UNiagaraSpriteRendererProperties* Sprite = Cast<UNiagaraSpriteRendererProperties>(R);
        if (!Sprite) continue;
        Sprite->Modify();
        Sprite->SubImageSize = FVector2D(X, Y);
        FProperty* Prop = UNiagaraSpriteRendererProperties::StaticClass()->FindPropertyByName(TEXT("SubImageSize"));
        FPropertyChangedEvent Event(Prop);
        Sprite->PostEditChangeProperty(Event);
        ++Renderers;
      }
    }
    System->MarkPackageDirty();
  } else {
    Report->SetStringField(TEXT("error"), TEXT("not a /Game/S08/FX/ Niagara system"));
  }
#else
  Report->SetStringField(TEXT("error"), TEXT("editor only"));
#endif
  Report->SetNumberField(TEXT("renderers"), Renderers);
  Report->SetBoolField(TEXT("ok"), Renderers > 0);
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

FString US08FxAuthoringLibrary::MakeBoardQuadCarrier(const FString& SystemPath, const FString& EmitterName,
                                                     const FString& MeshPath, const FString& MaterialPath) {
  TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
  Report->SetStringField(TEXT("system"), SystemPath);
  Report->SetStringField(TEXT("emitter"), EmitterName);
  bool bOk = false;
#if WITH_EDITOR
  auto Obj = [](const FString& Path) {
    int32 Dot = INDEX_NONE;
    return Path.FindChar(TEXT('.'), Dot) ? Path : Path + TEXT(".") + FPackageName::GetShortName(Path);
  };
  UNiagaraSystem* System = SystemPath.StartsWith(TEXT("/Game/S08/FX/"))
      ? LoadObject<UNiagaraSystem>(nullptr, *Obj(SystemPath)) : nullptr;
  UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *Obj(MeshPath));
  UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr, *Obj(MaterialPath));
  if (!System || !Mesh || !Material) {
    Report->SetStringField(TEXT("error"), FString::Printf(TEXT("load failed system=%d mesh=%d material=%d"),
                                                          System ? 1 : 0, Mesh ? 1 : 0, Material ? 1 : 0));
  } else {
    int32 Disabled = 0;
    bool bFound = false;
    for (FNiagaraEmitterHandle& Handle : System->GetEmitterHandles()) {
      if (Handle.GetName().ToString() != EmitterName) continue;
      FVersionedNiagaraEmitter Versioned = Handle.GetInstance();
      FVersionedNiagaraEmitterData* Data = Handle.GetEmitterData();
      if (!Versioned.Emitter || !Data) continue;
      bFound = true;
      Versioned.Emitter->Modify();
      Data->bLocalSpace = true;
      UNiagaraMeshRendererProperties* MeshRenderer = nullptr;
      for (UNiagaraRendererProperties* R : Data->GetRenderers()) {
        if (UNiagaraMeshRendererProperties* M = Cast<UNiagaraMeshRendererProperties>(R)) {
          MeshRenderer = M;
        } else if (R && R->GetIsEnabled()) {
          R->Modify();
          R->SetIsEnabled(false);
          ++Disabled;
        }
      }
      if (!MeshRenderer) {
        MeshRenderer = NewObject<UNiagaraMeshRendererProperties>(Versioned.Emitter, NAME_None, RF_Transactional);
        Versioned.Emitter->AddRenderer(MeshRenderer, Versioned.Version);
      }
      MeshRenderer->Modify();
      if (MeshRenderer->Meshes.Num() == 0) MeshRenderer->Meshes.AddDefaulted();
      MeshRenderer->Meshes.SetNum(1);
      MeshRenderer->Meshes[0].Mesh = Mesh;
      MeshRenderer->bOverrideMaterials = true;
      MeshRenderer->OverrideMaterials.SetNum(1);
      MeshRenderer->OverrideMaterials[0].ExplicitMat = Material;
      MeshRenderer->SortMode = ENiagaraSortMode::None;
      MeshRenderer->SetIsEnabled(true);
      FPropertyChangedEvent MeshEvent(UNiagaraMeshRendererProperties::StaticClass()->FindPropertyByName(TEXT("Meshes")));
      MeshRenderer->PostEditChangeProperty(MeshEvent);
      FPropertyChangedEvent MatEvent(
          UNiagaraMeshRendererProperties::StaticClass()->FindPropertyByName(TEXT("OverrideMaterials")));
      MeshRenderer->PostEditChangeProperty(MatEvent);
      FPropertyChangedEvent SpaceEvent(FVersionedNiagaraEmitterData::StaticStruct()->FindPropertyByName(TEXT("bLocalSpace")));
      Versioned.Emitter->PostEditChangeVersionedProperty(SpaceEvent, Versioned.Version);
    }
    if (bFound) {
      System->RequestCompile(false);
      System->WaitForCompilationComplete();
      System->MarkPackageDirty();
      bOk = true;
    } else {
      Report->SetStringField(TEXT("error"), TEXT("emitter not found"));
    }
    Report->SetNumberField(TEXT("renderersDisabled"), Disabled);
    Report->SetStringField(TEXT("mesh"), Mesh->GetPathName());
    Report->SetStringField(TEXT("material"), Material->GetPathName());
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

FString US08FxAuthoringLibrary::BindUserMaterialParameters(const FString& SystemPath, const FString& EmitterName,
                                                           const FString& SpecJson) {
  TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
  Report->SetStringField(TEXT("system"), SystemPath);
  Report->SetStringField(TEXT("emitter"), EmitterName);
  bool bOk = false;
#if WITH_EDITOR
  int32 Dot = INDEX_NONE;
  const FString ObjectPath = SystemPath.FindChar(TEXT('.'), Dot)
      ? SystemPath : SystemPath + TEXT(".") + FPackageName::GetShortName(SystemPath);
  UNiagaraSystem* System = SystemPath.StartsWith(TEXT("/Game/S08/FX/"))
      ? LoadObject<UNiagaraSystem>(nullptr, *ObjectPath) : nullptr;
  TArray<TSharedPtr<FJsonValue>> Spec;
  {
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(SpecJson);
    FJsonSerializer::Deserialize(Reader, Spec);
  }
  if (!System) {
    Report->SetStringField(TEXT("error"), TEXT("not a /Game/S08/FX/ Niagara system"));
  } else if (Spec.Num() == 0) {
    Report->SetStringField(TEXT("error"), TEXT("empty spec"));
  } else {
    System->Modify();
    FNiagaraUserRedirectionParameterStore& Store = System->GetExposedParameters();
    TArray<TSharedPtr<FJsonValue>> Added;
    TArray<FNiagaraMaterialAttributeBinding> Bindings;
    for (const TSharedPtr<FJsonValue>& Value : Spec) {
      const TSharedPtr<FJsonObject> P = Value.IsValid() ? Value->AsObject() : nullptr;
      if (!P.IsValid()) continue;
      const FString Name = P->GetStringField(TEXT("name"));
      const bool bColor = P->GetStringField(TEXT("type")) == TEXT("color");
      const FNiagaraTypeDefinition Type = bColor ? FNiagaraTypeDefinition::GetColorDef() : FNiagaraTypeDefinition::GetFloatDef();
      const FName UserName(*(FString(TEXT("User.")) + Name));
      FNiagaraVariable Var(Type, UserName);
      // replace a parameter of the same name but another type; keep an existing one of the right type
      for (const FNiagaraVariableWithOffset& Existing : Store.ReadParameterVariables()) {
        if (Existing.GetName() == UserName && Existing.GetType() != Type) {
          Store.RemoveParameter(Existing);
          break;
        }
      }
      if (Store.IndexOf(Var) == INDEX_NONE) Store.AddParameter(Var, true, true);
      if (bColor) {
        const TArray<TSharedPtr<FJsonValue>>* D = nullptr;
        FLinearColor C(1.0f, 1.0f, 1.0f, 1.0f);
        if (P->TryGetArrayField(TEXT("default"), D) && D->Num() >= 3) {
          C = FLinearColor((*D)[0]->AsNumber(), (*D)[1]->AsNumber(), (*D)[2]->AsNumber(),
                           D->Num() > 3 ? (*D)[3]->AsNumber() : 1.0f);
        }
        Store.SetParameterValue(C, Var, true);
      } else {
        double D = 0.0;
        P->TryGetNumberField(TEXT("default"), D);
        Store.SetParameterValue(static_cast<float>(D), Var, true);
      }
      FNiagaraMaterialAttributeBinding B;
      B.MaterialParameterName = FName(*Name);
      B.NiagaraVariable = FNiagaraVariableBase(Type, UserName);
      Bindings.Add(B);
      Added.Add(MakeShared<FJsonValueString>(UserName.ToString()));
    }
    int32 Renderers = 0;
    for (FNiagaraEmitterHandle& Handle : System->GetEmitterHandles()) {
      if (Handle.GetName().ToString() != EmitterName) continue;
      FVersionedNiagaraEmitter Versioned = Handle.GetInstance();
      FVersionedNiagaraEmitterData* Data = Handle.GetEmitterData();
      if (!Versioned.Emitter || !Data) continue;
      for (UNiagaraRendererProperties* R : Data->GetRenderers()) {
        UNiagaraMeshRendererProperties* Mesh = Cast<UNiagaraMeshRendererProperties>(R);
        if (!Mesh) continue;
        Mesh->Modify();
        for (const FNiagaraMaterialAttributeBinding& B : Bindings) {
          Mesh->MaterialParameters.AttributeBindings.RemoveAll([&B](const FNiagaraMaterialAttributeBinding& E) {
            return E.MaterialParameterName == B.MaterialParameterName;
          });
          FNiagaraMaterialAttributeBinding& NewB = Mesh->MaterialParameters.AttributeBindings.Add_GetRef(B);
          NewB.CacheValues(Versioned.Emitter);
        }
        FPropertyChangedEvent Event(
            UNiagaraMeshRendererProperties::StaticClass()->FindPropertyByName(TEXT("MaterialParameters")));
        Mesh->PostEditChangeProperty(Event);
        ++Renderers;
      }
    }
    if (Renderers > 0) {
      System->RequestCompile(false);
      System->WaitForCompilationComplete();
      System->MarkPackageDirty();
      bOk = true;
    } else {
      Report->SetStringField(TEXT("error"), TEXT("no mesh renderer on the emitter"));
    }
    Report->SetNumberField(TEXT("renderers"), Renderers);
    Report->SetArrayField(TEXT("userParameters"), Added);
    Report->SetNumberField(TEXT("exposedParameters"), Store.Num());
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

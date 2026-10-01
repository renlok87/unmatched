#include "S08EnvFxAuthoring.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/PackageName.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

#if WITH_EDITOR
#include "NiagaraComponentRendererProperties.h"
#include "NiagaraEmitter.h"
#include "NiagaraEmitterHandle.h"
#include "NiagaraLightRendererProperties.h"
#include "NiagaraParameterStore.h"
#include "NiagaraRendererProperties.h"
#include "NiagaraScript.h"
#include "NiagaraSystem.h"
#include "NiagaraTypes.h"
#include "UObject/UnrealType.h"
#endif

namespace S08EnvFxAuthoringPrivate {
FString FxJsonString(const TSharedRef<FJsonObject>& Object) {
  FString Out;
  const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Out);
  FJsonSerializer::Serialize(Object, Writer);
  return Out;
}

#if WITH_EDITOR
/** "/Game/X/NS_A" -> "/Game/X/NS_A.NS_A" (LoadObject of the asset, not the package). */
FString FxObjectPath(const FString& Path) {
  int32 Dot = INDEX_NONE;
  return Path.FindChar(TEXT('.'), Dot) ? Path : Path + TEXT(".") + FPackageName::GetShortName(Path);
}

/** Float components of a constant / parameter type (0 = not a float vector). */
int32 FxFloatComponents(const FNiagaraTypeDefinition& T) {
  if (T == FNiagaraTypeDefinition::GetFloatDef()) return 1;
  if (T == FNiagaraTypeDefinition::GetVec2Def()) return 2;
  if (T == FNiagaraTypeDefinition::GetVec3Def() || T == FNiagaraTypeDefinition::GetPositionDef()) return 3;
  if (T == FNiagaraTypeDefinition::GetVec4Def() || T == FNiagaraTypeDefinition::GetColorDef()) return 4;
  return 0;
}

bool FxIsInt(const FNiagaraTypeDefinition& T) {
  return T == FNiagaraTypeDefinition::GetIntDef() || T == FNiagaraTypeDefinition::GetBoolDef();
}

/** The value of a store variable as JSON (number or array), null for other types (data interfaces, objects ...). */
TSharedPtr<FJsonValue> FxValueJson(const FNiagaraParameterStore& Store, const FNiagaraVariableWithOffset& V) {
  const uint8* Data = Store.GetParameterData(V);
  if (!Data) return MakeShared<FJsonValueNull>();
  const int32 N = FxFloatComponents(V.GetType());
  if (N > 0) {
    float F[4] = {0.f, 0.f, 0.f, 0.f};
    FMemory::Memcpy(F, Data, N * sizeof(float));
    if (N == 1) return MakeShared<FJsonValueNumber>(F[0]);
    TArray<TSharedPtr<FJsonValue>> Items;
    for (int32 I = 0; I < N; ++I) Items.Add(MakeShared<FJsonValueNumber>(F[I]));
    return MakeShared<FJsonValueArray>(Items);
  }
  if (FxIsInt(V.GetType())) {
    int32 I = 0;
    FMemory::Memcpy(&I, Data, sizeof(int32));
    return MakeShared<FJsonValueNumber>(I);
  }
  return MakeShared<FJsonValueNull>();
}

/** Every script whose rapid-iteration constants may hold module inputs: system spawn / update (emitter-stage modules
 *  are compiled into them) and all scripts of every emitter copy. */
TArray<UNiagaraScript*> FxScripts(UNiagaraSystem& System) {
  TArray<UNiagaraScript*> Out;
  if (UNiagaraScript* S = System.GetSystemSpawnScript()) Out.AddUnique(S);
  if (UNiagaraScript* S = System.GetSystemUpdateScript()) Out.AddUnique(S);
  for (const FNiagaraEmitterHandle& H : System.GetEmitterHandles()) {
    if (const FVersionedNiagaraEmitterData* D = H.GetEmitterData()) {
      TArray<UNiagaraScript*> Scripts;
      D->GetScripts(Scripts, false, false);
      for (UNiagaraScript* S : Scripts) {
        if (S) Out.AddUnique(S);
      }
    }
  }
  return Out;
}

FString FxScriptLabel(const UNiagaraScript* S) { return S ? S->GetPathName() : FString(TEXT("-")); }

/** "Constants.Fire.InitializeParticle.Lifetime" -> "Fire.InitializeParticle.Lifetime". */
FString FxConstantName(const FName& Name) {
  FString S = Name.ToString();
  if (S.StartsWith(TEXT("Constants."))) S.RightChopInline(10);
  return S;
}

/** Reads a number / array of numbers from a JSON value into F (1..4). */
bool FxReadNumbers(const TSharedPtr<FJsonValue>& V, float F[4], int32& N) {
  if (!V.IsValid()) return false;
  double D = 0.0;
  if (V->Type == EJson::Number) {
    F[0] = static_cast<float>(V->AsNumber());
    N = 1;
    return true;
  }
  if (V->Type == EJson::Boolean) {
    F[0] = V->AsBool() ? 1.f : 0.f;
    N = 1;
    return true;
  }
  if (V->Type != EJson::Array) return false;
  const TArray<TSharedPtr<FJsonValue>>& A = V->AsArray();
  if (A.Num() < 1 || A.Num() > 4) return false;
  for (int32 I = 0; I < A.Num(); ++I) {
    if (!A[I].IsValid() || !A[I]->TryGetNumber(D)) return false;
    F[I] = static_cast<float>(D);
  }
  N = A.Num();
  return true;
}

/** Writes 1..4 floats (or an int) into the store variable; false on an arity / type mismatch. */
bool FxWrite(FNiagaraParameterStore& Store, const FNiagaraVariableWithOffset& V, const float F[4], int32 N) {
  const FNiagaraVariable Var(V.GetType(), V.GetName());
  const int32 Want = FxFloatComponents(V.GetType());
  if (Want > 0) {
    float Out[4] = {F[0], F[1], F[2], F[3]};
    if (N == 1 && Want > 1) {
      for (int32 I = 1; I < Want; ++I) Out[I] = F[0];  // a scalar "set" fills every component
    } else if (N != Want && !(Want == 4 && N == 3 && V.GetType() == FNiagaraTypeDefinition::GetColorDef())) {
      return false;
    }
    if (Want == 4 && N == 3) Out[3] = 1.f;  // colour without alpha
    return Store.SetParameterData(reinterpret_cast<const uint8*>(Out), Var, false);
  }
  if (FxIsInt(V.GetType()) && N == 1) {
    const int32 I = FMath::RoundToInt(F[0]);
    return Store.SetParameterData(reinterpret_cast<const uint8*>(&I), Var, false);
  }
  return false;
}

TSharedRef<FJsonObject> FxDescribe(UNiagaraSystem& System) {
  TSharedRef<FJsonObject> R = MakeShared<FJsonObject>();
  R->SetBoolField(TEXT("determinism"), System.NeedsDeterminism());
  R->SetNumberField(TEXT("randomSeed"), System.GetRandomSeed());
  R->SetNumberField(TEXT("warmupTime"), System.GetWarmupTime());
  R->SetNumberField(TEXT("warmupTickCount"), System.GetWarmupTickCount());
  R->SetNumberField(TEXT("warmupTickDelta"), System.GetWarmupTickDelta());
  TArray<TSharedPtr<FJsonValue>> Emitters;
  for (const FNiagaraEmitterHandle& H : System.GetEmitterHandles()) {
    TSharedRef<FJsonObject> E = MakeShared<FJsonObject>();
    E->SetStringField(TEXT("name"), H.GetName().ToString());
    E->SetBoolField(TEXT("enabled"), H.GetIsEnabled());
    if (const FVersionedNiagaraEmitterData* D = H.GetEmitterData()) {
      E->SetStringField(TEXT("simTarget"), D->SimTarget == ENiagaraSimTarget::GPUComputeSim ? TEXT("gpu") : TEXT("cpu"));
      E->SetBoolField(TEXT("determinism"), D->bDeterminism);
      E->SetNumberField(TEXT("randomSeed"), D->RandomSeed);
      E->SetBoolField(TEXT("localSpace"), D->bLocalSpace);
      TArray<TSharedPtr<FJsonValue>> Renderers;
      for (const UNiagaraRendererProperties* Rp : D->GetRenderers()) {
        if (!Rp) continue;
        TSharedRef<FJsonObject> RO = MakeShared<FJsonObject>();
        RO->SetStringField(TEXT("class"), Rp->GetClass()->GetName());
        RO->SetBoolField(TEXT("enabled"), Rp->GetIsEnabled());
        RO->SetBoolField(TEXT("light"), Rp->IsA<UNiagaraLightRendererProperties>());
        RO->SetBoolField(TEXT("component"), Rp->IsA<UNiagaraComponentRendererProperties>());
        Renderers.Add(MakeShared<FJsonValueObject>(RO));
      }
      E->SetArrayField(TEXT("renderers"), Renderers);
    } else {
      E->SetStringField(TEXT("simTarget"), TEXT("stateless"));
    }
    Emitters.Add(MakeShared<FJsonValueObject>(E));
  }
  R->SetArrayField(TEXT("emitters"), Emitters);
  TSharedRef<FJsonObject> User = MakeShared<FJsonObject>();
  const FNiagaraUserRedirectionParameterStore& Exposed = System.GetExposedParameters();
  for (const FNiagaraVariableWithOffset& V : Exposed.ReadParameterVariables()) {
    TSharedRef<FJsonObject> U = MakeShared<FJsonObject>();
    U->SetStringField(TEXT("type"), V.GetType().GetName());
    U->SetField(TEXT("value"), FxValueJson(Exposed, V));
    User->SetObjectField(V.GetName().ToString(), U);
  }
  R->SetObjectField(TEXT("user"), User);
  TSharedRef<FJsonObject> Constants = MakeShared<FJsonObject>();
  for (UNiagaraScript* S : FxScripts(System)) {
    TSharedRef<FJsonObject> PerScript = MakeShared<FJsonObject>();
    for (const FNiagaraVariableWithOffset& V : S->RapidIterationParameters.ReadParameterVariables()) {
      TSharedRef<FJsonObject> C = MakeShared<FJsonObject>();
      C->SetStringField(TEXT("type"), V.GetType().GetName());
      C->SetField(TEXT("value"), FxValueJson(S->RapidIterationParameters, V));
      PerScript->SetObjectField(FxConstantName(V.GetName()), C);
    }
    Constants->SetObjectField(FxScriptLabel(S), PerScript);
  }
  R->SetObjectField(TEXT("constants"), Constants);
  return R;
}

/** PostEditChange of one FVersionedNiagaraEmitterData property (marks the graph source unsynchronised so the
 *  recompile picks the new sim target / determinism up). The struct is looked up by name: it is not exported. */
void FxPostEditEmitter(const FNiagaraEmitterHandle& H, const TCHAR* PropertyName) {
  const FVersionedNiagaraEmitter VE = H.GetInstance();
  if (!VE.Emitter) return;
  const UScriptStruct* Struct = FindObject<UScriptStruct>(nullptr, TEXT("/Script/Niagara.VersionedNiagaraEmitterData"));
  FProperty* Prop = Struct ? Struct->FindPropertyByName(FName(PropertyName)) : nullptr;
  FPropertyChangedEvent Event(Prop);
  VE.Emitter->PostEditChangeVersionedProperty(Event, VE.Version);
}
#endif
}  // namespace S08EnvFxAuthoringPrivate

FString US08EnvFxAuthoringLibrary::DescribeNiagaraSystem(const FString& SystemPath) {
  using namespace S08EnvFxAuthoringPrivate;
  TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
  Report->SetStringField(TEXT("schema"), TEXT("unmatched.env-fx-describe/1"));
  Report->SetStringField(TEXT("system"), SystemPath);
#if WITH_EDITOR
  UNiagaraSystem* System = LoadObject<UNiagaraSystem>(nullptr, *FxObjectPath(SystemPath));
  if (!System) {
    Report->SetStringField(TEXT("error"), TEXT("not a Niagara system"));
    return FxJsonString(Report);
  }
  Report->SetObjectField(TEXT("describe"), FxDescribe(*System));
#else
  Report->SetStringField(TEXT("error"), TEXT("editor only"));
#endif
  return FxJsonString(Report);
}

FString US08EnvFxAuthoringLibrary::TuneNiagaraSystem(const FString& SystemPath, const FString& SpecJson) {
  using namespace S08EnvFxAuthoringPrivate;
  TSharedRef<FJsonObject> Report = MakeShared<FJsonObject>();
  Report->SetStringField(TEXT("schema"), TEXT("unmatched.env-fx-tune/1"));
  Report->SetStringField(TEXT("system"), SystemPath);
#if WITH_EDITOR
  TArray<TSharedPtr<FJsonValue>> Errors;
  auto Fail = [&](const FString& Message) {
    Errors.Add(MakeShared<FJsonValueString>(Message));
    Report->SetArrayField(TEXT("errors"), Errors);
    Report->SetBoolField(TEXT("ok"), false);
    return FxJsonString(Report);
  };
  if (!SystemPath.StartsWith(TEXT("/Game/EnvKit/"))) {
    return Fail(TEXT("refused: only derived copies under /Game/EnvKit/ are tuned (the Fab pack folders stay pristine)"));
  }
  TSharedPtr<FJsonObject> Spec;
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(SpecJson);
  if (!FJsonSerializer::Deserialize(Reader, Spec) || !Spec.IsValid()) return Fail(TEXT("spec is not a JSON object"));
  UNiagaraSystem* System = LoadObject<UNiagaraSystem>(nullptr, *FxObjectPath(SystemPath));
  if (!System) return Fail(TEXT("not a Niagara system"));
  System->Modify();

  // emitters: sim target, determinism / seed, renderers, enabled
  FString SimTarget;
  Spec->TryGetStringField(TEXT("simTarget"), SimTarget);
  bool bDeterminism = false, bNoLights = true, bNoComponents = true;
  const bool bSetDeterminism = Spec->TryGetBoolField(TEXT("emitterDeterminism"), bDeterminism);
  double SeedBase = 0.0;
  const bool bSeed = Spec->TryGetNumberField(TEXT("emitterSeedBase"), SeedBase);
  Spec->TryGetBoolField(TEXT("disableLightRenderers"), bNoLights);
  Spec->TryGetBoolField(TEXT("disableComponentRenderers"), bNoComponents);
  const TSharedPtr<FJsonObject>* EmitterOps = nullptr;
  Spec->TryGetObjectField(TEXT("emitters"), EmitterOps);
  TArray<TSharedPtr<FJsonValue>> EmitterChanges;
  int32 LightsOff = 0, ComponentsOff = 0;
  TArray<FNiagaraEmitterHandle>& Handles = System->GetEmitterHandles();
  for (int32 Index = 0; Index < Handles.Num(); ++Index) {
    FNiagaraEmitterHandle& H = Handles[Index];
    const FString Name = H.GetName().ToString();
    TSharedRef<FJsonObject> Change = MakeShared<FJsonObject>();
    Change->SetStringField(TEXT("emitter"), Name);
    if (EmitterOps && EmitterOps->IsValid()) {
      const TSharedPtr<FJsonObject>* Op = nullptr;
      bool bEnabled = true;
      if ((*EmitterOps)->TryGetObjectField(Name, Op) && Op && Op->IsValid() && (*Op)->TryGetBoolField(TEXT("enabled"), bEnabled)) {
        if (H.SetIsEnabled(bEnabled, *System, false)) Change->SetBoolField(TEXT("enabled"), bEnabled);
      }
    }
    FVersionedNiagaraEmitterData* D = H.GetEmitterData();
    if (!D) {
      Change->SetStringField(TEXT("note"), TEXT("stateless emitter: untouched"));
      EmitterChanges.Add(MakeShared<FJsonValueObject>(Change));
      continue;
    }
    const FVersionedNiagaraEmitter VE = H.GetInstance();
    if (VE.Emitter) VE.Emitter->Modify();
    if (SimTarget == TEXT("cpu") && D->SimTarget != ENiagaraSimTarget::CPUSim) {
      D->SimTarget = ENiagaraSimTarget::CPUSim;
      FxPostEditEmitter(H, TEXT("SimTarget"));
      Change->SetStringField(TEXT("simTarget"), TEXT("gpu->cpu"));
    }
    if (bSetDeterminism && D->bDeterminism != bDeterminism) {
      D->bDeterminism = bDeterminism;
      FxPostEditEmitter(H, TEXT("bDeterminism"));
      Change->SetBoolField(TEXT("determinism"), bDeterminism);
    }
    if (bSeed) {
      const int32 Seed = static_cast<int32>(SeedBase) + Index;
      if (D->RandomSeed != Seed) {
        D->RandomSeed = Seed;
        Change->SetNumberField(TEXT("randomSeed"), Seed);
      }
    }
    for (UNiagaraRendererProperties* Rp : D->GetRenderers()) {
      if (!Rp || !Rp->GetIsEnabled()) continue;
      if (bNoLights && Rp->IsA<UNiagaraLightRendererProperties>()) {
        Rp->Modify();
        Rp->SetIsEnabled(false);
        ++LightsOff;
      } else if (bNoComponents && Rp->IsA<UNiagaraComponentRendererProperties>()) {
        Rp->Modify();
        Rp->SetIsEnabled(false);
        ++ComponentsOff;
      }
    }
    EmitterChanges.Add(MakeShared<FJsonValueObject>(Change));
  }
  Report->SetArrayField(TEXT("emitters"), EmitterChanges);
  Report->SetNumberField(TEXT("lightRenderersDisabled"), LightsOff);
  Report->SetNumberField(TEXT("componentRenderersDisabled"), ComponentsOff);

  // rapid-iteration constants (module inputs): every store of every script holding a matching name
  TArray<TSharedPtr<FJsonValue>> ConstantChanges, Unmatched;
  const TArray<TSharedPtr<FJsonValue>>* Rules = nullptr;
  if (Spec->TryGetArrayField(TEXT("constants"), Rules) && Rules) {
    const TArray<UNiagaraScript*> Scripts = FxScripts(*System);
    for (const TSharedPtr<FJsonValue>& RuleValue : *Rules) {
      const TSharedPtr<FJsonObject>* Rule = nullptr;
      FString Match, Emitter;
      if (!RuleValue.IsValid() || !RuleValue->TryGetObject(Rule) || !Rule || !(*Rule)->TryGetStringField(TEXT("match"), Match)) {
        Errors.Add(MakeShared<FJsonValueString>(TEXT("constants: a rule without 'match'")));
        continue;
      }
      (*Rule)->TryGetStringField(TEXT("emitter"), Emitter);
      double Mul = 1.0;
      const bool bMul = (*Rule)->TryGetNumberField(TEXT("mul"), Mul);
      float SetValue[4] = {0.f, 0.f, 0.f, 0.f};
      int32 SetN = 0;
      const bool bSet = (*Rule)->HasField(TEXT("set")) && FxReadNumbers((*Rule)->TryGetField(TEXT("set")), SetValue, SetN);
      if (bMul == bSet) {
        Errors.Add(MakeShared<FJsonValueString>(FString::Printf(TEXT("constants '%s': exactly one of mul / set"), *Match)));
        continue;
      }
      int32 Hits = 0;
      for (UNiagaraScript* S : Scripts) {
        FNiagaraParameterStore& Store = S->RapidIterationParameters;
        // copy: writing may re-sort the store's variable table
        TArray<FNiagaraVariableWithOffset> Vars(Store.ReadParameterVariables());
        for (const FNiagaraVariableWithOffset& V : Vars) {
          const FString Name = FxConstantName(V.GetName());
          if (!Name.MatchesWildcard(Match, ESearchCase::IgnoreCase)) continue;
          if (!Emitter.IsEmpty() && !Name.StartsWith(Emitter + TEXT("."))) continue;
          const TSharedPtr<FJsonValue> Old = FxValueJson(Store, V);
          bool bWritten = false;
          if (bSet) {
            bWritten = FxWrite(Store, V, SetValue, SetN);
          } else {
            const int32 N = FxFloatComponents(V.GetType());
            const uint8* Data = Store.GetParameterData(V);
            if (N > 0 && Data) {
              float F[4] = {0.f, 0.f, 0.f, 0.f};
              FMemory::Memcpy(F, Data, N * sizeof(float));
              for (int32 I = 0; I < N; ++I) F[I] *= static_cast<float>(Mul);
              bWritten = FxWrite(Store, V, F, N);
            }
          }
          if (!bWritten) continue;
          ++Hits;
          S->Modify();
          TSharedRef<FJsonObject> C = MakeShared<FJsonObject>();
          C->SetStringField(TEXT("script"), FxScriptLabel(S));
          C->SetStringField(TEXT("name"), Name);
          C->SetStringField(TEXT("rule"), Match);
          C->SetField(TEXT("old"), Old);
          C->SetField(TEXT("new"), FxValueJson(Store, V));
          ConstantChanges.Add(MakeShared<FJsonValueObject>(C));
        }
      }
      if (Hits == 0) Unmatched.Add(MakeShared<FJsonValueString>(Match));
    }
  }
  Report->SetArrayField(TEXT("constants"), ConstantChanges);
  Report->SetArrayField(TEXT("unmatchedRules"), Unmatched);

  // exposed user parameter defaults
  TArray<TSharedPtr<FJsonValue>> UserChanges;
  const TSharedPtr<FJsonObject>* User = nullptr;
  if (Spec->TryGetObjectField(TEXT("user"), User) && User && User->IsValid()) {
    FNiagaraUserRedirectionParameterStore& Exposed = System->GetExposedParameters();
    TArray<FNiagaraVariableWithOffset> Vars(Exposed.ReadParameterVariables());
    for (const TPair<FString, TSharedPtr<FJsonValue>>& Entry : (*User)->Values) {
      const FString Key = Entry.Key.StartsWith(TEXT("User.")) ? Entry.Key : TEXT("User.") + Entry.Key;
      const FNiagaraVariableWithOffset* Var = Vars.FindByPredicate(
          [&Key](const FNiagaraVariableWithOffset& V) { return V.GetName().ToString() == Key; });
      float F[4] = {0.f, 0.f, 0.f, 0.f};
      int32 N = 0;
      if (!Var || !FxReadNumbers(Entry.Value, F, N)) {
        Errors.Add(MakeShared<FJsonValueString>(FString::Printf(TEXT("user '%s': not exposed or not numbers"), *Key)));
        continue;
      }
      const TSharedPtr<FJsonValue> Old = FxValueJson(Exposed, *Var);
      if (!FxWrite(Exposed, *Var, F, N)) {
        Errors.Add(MakeShared<FJsonValueString>(FString::Printf(TEXT("user '%s': type %s does not take %d numbers"), *Key,
                                                                *Var->GetType().GetName(), N)));
        continue;
      }
      TSharedRef<FJsonObject> C = MakeShared<FJsonObject>();
      C->SetStringField(TEXT("name"), Key);
      C->SetField(TEXT("old"), Old);
      C->SetField(TEXT("new"), FxValueJson(Exposed, *Var));
      UserChanges.Add(MakeShared<FJsonValueObject>(C));
    }
  }
  Report->SetArrayField(TEXT("user"), UserChanges);

  // recompile everything (sim target / determinism / baked constants), then the caller saves the package
  System->RequestCompile(true);
  System->WaitForCompilationComplete(true, false);
  System->MarkPackageDirty();
  Report->SetBoolField(TEXT("compiled"), !System->HasOutstandingCompilationRequests());
  Report->SetObjectField(TEXT("after"), FxDescribe(*System));
  Report->SetArrayField(TEXT("errors"), Errors);
  Report->SetBoolField(TEXT("ok"), Errors.Num() == 0);
#else
  Report->SetStringField(TEXT("error"), TEXT("editor only"));
  Report->SetBoolField(TEXT("ok"), false);
#endif
  return FxJsonString(Report);
}

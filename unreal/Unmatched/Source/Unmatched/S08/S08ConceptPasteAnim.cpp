#include "S08ConceptPasteAnim.h"
#include "S08EnvLayout.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Materials/MaterialInstanceDynamic.h"

namespace S08ConceptPasteAnimPrivate {
bool Number(const TSharedPtr<FJsonValue>& V, double& Out) {
  return V.IsValid() && V->Type == EJson::Number && V->TryGetNumber(Out) && FMath::IsFinite(Out);
}

/** Required number in [Min, Max]. */
bool Req(const TSharedPtr<FJsonObject>& O, const TCHAR* Field, double Min, double Max, float& Out) {
  double V = 0.0;
  if (!O->HasField(Field) || !Number(O->TryGetField(Field), V) || V < Min || V > Max) return false;
  Out = static_cast<float>(V);
  return true;
}

/** Exactly two finite numbers. */
bool Pair(const TSharedPtr<FJsonObject>& O, const TCHAR* Field, FVector2D& Out) {
  const TArray<TSharedPtr<FJsonValue>>* A = nullptr;
  double X = 0.0, Y = 0.0;
  if (!O->TryGetArrayField(Field, A) || !A || A->Num() != 2 || !Number((*A)[0], X) || !Number((*A)[1], Y)) return false;
  Out = FVector2D(X, Y);
  return true;
}

/** Only the listed fields (and any "note*"). */
bool Known(const TSharedPtr<FJsonObject>& O, std::initializer_list<const TCHAR*> Allowed, FString& OutUnknown) {
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

bool IsId(const FString& S) {
  if (S.IsEmpty() || S.Len() > 64) return false;
  for (const TCHAR C : S) {
    if (!FChar::IsAlnum(C) && C != TEXT('-') && C != TEXT('_')) return false;
  }
  return true;
}

bool Hex(const FString& Text, FColor& Out) {
  FString H = Text;
  if (!H.RemoveFromStart(TEXT("#")) || H.Len() != 6) return false;
  for (const TCHAR C : H) {
    if (!FChar::IsHexDigit(C)) return false;
  }
  Out = FColor::FromHex(H);
  Out.A = 255;
  return true;
}

bool IsAssetPath(const FString& Path) {
  return Path.StartsWith(S08ConceptPasteSpec::AssetRoot) && !Path.StartsWith(S08ConceptPasteSpec::NeverCookRoot) &&
         !Path.Contains(TEXT(" ")) && !Path.Contains(TEXT(".")) && Path.Len() > FCString::Strlen(S08ConceptPasteSpec::AssetRoot);
}

const TArray<FName>& Names(const TCHAR* Prefix) {
  static TArray<FName> C0, Flicker;
  TArray<FName>& Out = FCString::Strcmp(Prefix, S08ConceptPasteSpec::LanternC0Prefix) == 0 ? C0 : Flicker;
  if (Out.IsEmpty()) {
    for (int32 I = 0; I < S08ConceptPasteSpec::MaxAnimLanterns; ++I) Out.Add(FName(*FString::Printf(TEXT("%s%d"), Prefix, I)));
  }
  return Out;
}
}  // namespace S08ConceptPasteAnimPrivate

FS08ConceptAnimParams::FS08ConceptAnimParams() {
  for (int32 I = 0; I < S08ConceptPasteSpec::MaxAnimLanterns; ++I) {
    LanternC0[I] = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);
    LanternFlicker[I] = 1.0f;
  }
}

namespace S08ConceptPasteAnim {

void ParseJson(const TSharedPtr<FJsonObject>& O, const TArray<FS08ConceptLight>& Lights, FS08ConceptPasteAnimSpec& Out,
               TFunctionRef<void(const FString&)> Fail) {
  using namespace S08ConceptPasteAnimPrivate;
  Out = FS08ConceptPasteAnimSpec();
  if (!O.IsValid()) {
    Fail(TEXT("anim must be an object"));
    return;
  }
  bool bOk = true;
  auto Bad = [&](const FString& What) {
    bOk = false;
    Fail(What);
  };
  FString Unknown;
  if (!Known(O, {TEXT("mask"), TEXT("lanterns"), TEXT("wind"), TEXT("mist")}, Unknown)) {
    Bad(FString::Printf(TEXT("anim.%s is not a field"), *Unknown));
  }
  if (!O->TryGetStringField(TEXT("mask"), Out.MaskPath) || !IsAssetPath(Out.MaskPath)) {
    Bad(FString::Printf(TEXT("anim.mask '%s' is not a %s package path (not under %s)"), *Out.MaskPath,
                        S08ConceptPasteSpec::AssetRoot, S08ConceptPasteSpec::NeverCookRoot));
  }
  if (O->HasField(TEXT("lanterns"))) {
    const TArray<TSharedPtr<FJsonValue>>* Slots = nullptr;
    if (!O->TryGetArrayField(TEXT("lanterns"), Slots) || !Slots || Slots->Num() > S08ConceptPasteSpec::MaxAnimLanterns) {
      Bad(FString::Printf(TEXT("anim.lanterns must be an array of at most %d slots"), S08ConceptPasteSpec::MaxAnimLanterns));
    } else {
      TSet<FString> Ids;
      for (int32 I = 0; I < Slots->Num(); ++I) {
        const TSharedPtr<FJsonObject>* S = nullptr;
        FS08ConceptAnimLantern L;
        FString SlotUnknown;
        bool bSlot = (*Slots)[I].IsValid() && (*Slots)[I]->TryGetObject(S) && S && S->IsValid() &&
                     Known(*S, {TEXT("id"), TEXT("c0Px"), TEXT("radiusPx"), TEXT("light"), TEXT("flicker")}, SlotUnknown) &&
                     (*S)->TryGetStringField(TEXT("id"), L.Id) && IsId(L.Id) && !Ids.Contains(L.Id) &&
                     Pair(*S, TEXT("c0Px"), L.C0Px) && FMath::Abs(L.C0Px.X) <= 4000.0 && FMath::Abs(L.C0Px.Y) <= 4000.0 &&
                     Req(*S, TEXT("radiusPx"), 4.0, 320.0, L.RadiusPx);
        const bool bLight = bSlot && (*S)->HasField(TEXT("light"));
        const bool bFlicker = bSlot && (*S)->HasField(TEXT("flicker"));
        if (bSlot && bLight == bFlicker) bSlot = false;  // exactly one of light / flicker
        if (bSlot && bLight) {
          bSlot = (*S)->TryGetStringField(TEXT("light"), L.LightId) &&
                  Lights.ContainsByPredicate([&L](const FS08ConceptLight& Light) { return Light.Id == L.LightId; });
        }
        if (bSlot && bFlicker) {
          const TSharedPtr<FJsonObject>* F = nullptr;
          FString FlickerUnknown;
          bSlot = (*S)->TryGetObjectField(TEXT("flicker"), F) && F && F->IsValid() &&
                  Known(*F, {TEXT("amp"), TEXT("hz")}, FlickerUnknown) && Req(*F, TEXT("amp"), 0.0, 0.5, L.FlickerAmp) &&
                  Req(*F, TEXT("hz"), 0.0, 20.0, L.FlickerHz);
        }
        if (!bSlot) {
          Bad(FString::Printf(TEXT("anim.lanterns[%d] needs a unique id, c0Px [x, y] |..| <= 4000, radiusPx 4..320 and exactly one of light (an id of conceptPaste.lights) | flicker {amp 0..0.5, hz 0..20}"),
                              I));
          continue;
        }
        Ids.Add(L.Id);
        Out.Lanterns.Add(L);
      }
    }
  }
  if (O->HasField(TEXT("wind"))) {
    const TSharedPtr<FJsonObject>* W = nullptr;
    FS08ConceptAnimWind& Wind = Out.Wind;
    FString WindUnknown;
    const bool bWind = O->TryGetObjectField(TEXT("wind"), W) && W && W->IsValid() &&
                       Known(*W, {TEXT("ampPx"), TEXT("hz"), TEXT("gustHz"), TEXT("gustAmp"), TEXT("wavePx")}, WindUnknown) &&
                       Req(*W, TEXT("ampPx"), 0.0, S08ConceptPasteSpec::MaxWindOffsetPx, Wind.AmpPx) &&
                       Req(*W, TEXT("hz"), 0.0, 2.0, Wind.Hz) && Req(*W, TEXT("gustHz"), 0.0, 3.0, Wind.GustHz) &&
                       Req(*W, TEXT("gustAmp"), 0.0, 1.0, Wind.GustAmp) && Req(*W, TEXT("wavePx"), 50.0, 2000.0, Wind.WavePx);
    if (!bWind) {
      Bad(TEXT("anim.wind needs ampPx 0..4, hz 0..2, gustHz 0..3, gustAmp 0..1, wavePx 50..2000"));
    } else if (Wind.AmpPx * (1.0f + Wind.GustAmp) > S08ConceptPasteSpec::MaxWindOffsetPx + 1e-4f) {
      Bad(FString::Printf(TEXT("anim.wind ampPx x (1 + gustAmp) = %.2f > %.0f C0 px (the hard limit of the UV offset)"),
                          Wind.AmpPx * (1.0f + Wind.GustAmp), S08ConceptPasteSpec::MaxWindOffsetPx));
    } else {
      Wind.bSet = true;
    }
  }
  if (O->HasField(TEXT("mist"))) {
    const TSharedPtr<FJsonObject>* M = nullptr;
    FS08ConceptAnimMist& Mist = Out.Mist;
    FString MistUnknown, ColorText;
    const bool bMist = O->TryGetObjectField(TEXT("mist"), M) && M && M->IsValid() &&
                       Known(*M, {TEXT("opacity"), TEXT("panPxPerS"), TEXT("noisePx"), TEXT("colorSrgb")}, MistUnknown) &&
                       Req(*M, TEXT("opacity"), 0.0, 0.4, Mist.Opacity) && Pair(*M, TEXT("panPxPerS"), Mist.PanPxPerS) &&
                       Mist.PanPxPerS.Size() <= 30.0 && Req(*M, TEXT("noisePx"), 32.0, 1024.0, Mist.NoisePx) &&
                       (*M)->TryGetStringField(TEXT("colorSrgb"), ColorText) && Hex(ColorText, Mist.Color);
    if (!bMist) {
      Bad(TEXT("anim.mist needs opacity 0..0.4, panPxPerS [x, y] |..| <= 30, noisePx 32..1024, colorSrgb #RRGGBB"));
    } else {
      Mist.bSet = true;
    }
  }
  Out.bSet = bOk;
}

FName LanternC0Name(int32 Index) {
  return S08ConceptPasteAnimPrivate::Names(S08ConceptPasteSpec::LanternC0Prefix)[Index];
}

FName LanternFlickerName(int32 Index) {
  return S08ConceptPasteAnimPrivate::Names(S08ConceptPasteSpec::LanternFlickerPrefix)[Index];
}

const FS08ConceptLight* LinkedLight(const FS08ConceptAnimLantern& Slot, const TArray<FS08ConceptLight>& Lights) {
  if (Slot.LightId.IsEmpty()) return nullptr;
  return Lights.FindByPredicate([&Slot](const FS08ConceptLight& L) { return L.Id == Slot.LightId; });
}

float LanternFlicker(const FS08ConceptAnimLantern& Slot, const TArray<FS08ConceptLight>& Lights, double TimeS) {
  if (const FS08ConceptLight* Light = LinkedLight(Slot, Lights)) return S08ConceptPaste::FlickerScale(*Light, TimeS);
  FS08ConceptLight Own;
  Own.Id = Slot.Id;  // the phases come from the slot id (CpSeedOf), like a light of that id
  Own.FlickerAmp = Slot.FlickerAmp;
  Own.FlickerHz = Slot.FlickerHz;
  return S08ConceptPaste::FlickerScale(Own, TimeS);
}

int32 SyncedCount(const FS08ConceptPasteAnimSpec& Anim, const TArray<FS08ConceptLight>& Lights) {
  int32 N = 0;
  for (const FS08ConceptAnimLantern& Slot : Anim.Lanterns) N += LinkedLight(Slot, Lights) ? 1 : 0;
  return N;
}

FS08ConceptAnimParams Params(const FS08ConceptPasteAnimSpec& Anim, const TArray<FS08ConceptLight>& Lights, bool bFrozen,
                             double TimeS) {
  FS08ConceptAnimParams P;
  const double T = bFrozen ? 0.0 : TimeS;
  P.AnimTime = static_cast<float>(T);
  for (int32 I = 0; I < Anim.Lanterns.Num() && I < S08ConceptPasteSpec::MaxAnimLanterns; ++I) {
    const FS08ConceptAnimLantern& L = Anim.Lanterns[I];
    P.LanternC0[I] = FLinearColor(static_cast<float>(L.C0Px.X), static_cast<float>(L.C0Px.Y), L.RadiusPx, 0.0f);
    P.LanternFlicker[I] = bFrozen ? 1.0f : LanternFlicker(L, Lights, T);
  }
  if (Anim.Wind.bSet) {
    P.Wind = FLinearColor(bFrozen ? 0.0f : Anim.Wind.AmpPx, Anim.Wind.Hz, Anim.Wind.GustHz, Anim.Wind.GustAmp);
    P.WindWavePx = Anim.Wind.WavePx;
  }
  if (Anim.Mist.bSet) {
    const FLinearColor C = FLinearColor::FromSRGBColor(Anim.Mist.Color);
    P.MistColor = FLinearColor(C.R, C.G, C.B, 0.0f);
    P.MistParams = FLinearColor(Anim.Mist.Opacity, static_cast<float>(Anim.Mist.PanPxPerS.X),
                                static_cast<float>(Anim.Mist.PanPxPerS.Y), Anim.Mist.NoisePx);
  }
  return P;
}

FString Status(const FS08ConceptPasteAnimSpec& Anim, bool bMaskLoaded, bool bMaterialLoaded) {
  if (!Anim.bSet) return TEXT("no-block");
  if (!bMaskLoaded) return TEXT("mask-missing");
  if (!bMaterialLoaded) return TEXT("material-missing");
  return TEXT("ok");
}

FString FreezeReason(const FS08EnvFxOptions& O) {
  if (!O.bFreeze) return TEXT("live");
  if (O.bReduced) return TEXT("reduced");
  return O.bFreezeFlag && !O.bBench ? TEXT("flag") : TEXT("bench");
}

FString TraceLine(const FString& ProfileId, const FS08ConceptPasteAnimSpec& Anim, const TArray<FS08ConceptLight>& Lights,
                  const FString& MaskName, bool bUseAnim, const FString& InStatus, bool bFrozen, const FString& Reason) {
  const FString Wind = Anim.Wind.bSet ? FString::Printf(TEXT("%.2f@%.2f"), Anim.Wind.AmpPx, Anim.Wind.Hz) : FString(TEXT("-"));
  const FString Mist = Anim.Mist.bSet ? FString::Printf(TEXT("%.2f"), Anim.Mist.Opacity) : FString(TEXT("-"));
  return FString::Printf(
      TEXT("ARTPREVIEW concept-paste anim profile=%s mask=%s lanterns=%d synced=%d wind=%s mist=%s frozen=%d reason=%s use=%d status=%s"),
      ProfileId.IsEmpty() ? TEXT("-") : *ProfileId, MaskName.IsEmpty() ? TEXT("-") : *MaskName, Anim.Lanterns.Num(),
      SyncedCount(Anim, Lights), *Wind, *Mist, bFrozen ? 1 : 0, *Reason, bUseAnim ? 1 : 0, *InStatus);
}

void SetParams(UMaterialInstanceDynamic& Mid, const FS08ConceptAnimParams& P, bool bStatic) {
  using namespace S08ConceptPasteSpec;
  Mid.SetScalarParameterValue(FName(ParamAnimTime), P.AnimTime);
  for (int32 I = 0; I < MaxAnimLanterns; ++I) Mid.SetScalarParameterValue(LanternFlickerName(I), P.LanternFlicker[I]);
  if (!bStatic) return;
  for (int32 I = 0; I < MaxAnimLanterns; ++I) Mid.SetVectorParameterValue(LanternC0Name(I), P.LanternC0[I]);
  Mid.SetVectorParameterValue(FName(ParamWindParams), P.Wind);
  Mid.SetScalarParameterValue(FName(ParamWindWavePx), P.WindWavePx);
  Mid.SetVectorParameterValue(FName(ParamMistColor), P.MistColor);
  Mid.SetVectorParameterValue(FName(ParamMistParams), P.MistParams);
}

int32 AttachMids(US08ConceptPasteAnimComponent& Component, const FS08ConceptPasteSpec& Spec,
                 const FS08ConceptPasteRuntime& Runtime) {
  int32 N = 0;
  if (UMaterialInstanceDynamic* Sheet = Runtime.SheetMid.Get()) {
    if (Runtime.bUseAnim || Spec.Flows.Num() > 0) {
      Component.AddPasteMid(Sheet, Runtime.bUseAnim, Spec.Anim, Spec.Lights);
      ++N;
    }
  }
  if (UMaterialInstanceDynamic* Sea = Runtime.SeaMid.Get()) {
    if (Spec.SeaFlow.bSet) {
      Component.AddPasteMid(Sea, false, Spec.Anim, Spec.Lights);
      ++N;
    }
  }
  return N;
}

}  // namespace S08ConceptPasteAnim

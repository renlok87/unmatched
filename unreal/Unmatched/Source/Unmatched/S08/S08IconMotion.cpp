#include "S08IconMotion.h"
#include "S08MoveAnim.h"

#include "Algo/Sort.h"
#include "Dom/JsonObject.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace {
TAutoConsoleVariable<int32> CVarS08ReducedMotion(
    TEXT("s08.ReducedMotion"), 0,
    TEXT("HUD icon motion: 1 = reduced motion (UI-ACC-005/006): only opacity <= 100 ms, loops stand still. "
         "The -S08ReducedMotion flag forces it on."),
    ECVF_Default);

const FName NameCycle(TEXT("cycle"));
const FName NameAppear(TEXT("appear"));
const FName NameLeave(TEXT("leave"));
const FName NameWait(TEXT("wait"));

bool ParseProp(const FString& S, ES08IconProp& Out) {
  static const TMap<FString, ES08IconProp> Map = {
      {TEXT("scale"), ES08IconProp::Scale}, {TEXT("scale_x"), ES08IconProp::ScaleX},
      {TEXT("scale_y"), ES08IconProp::ScaleY}, {TEXT("tx"), ES08IconProp::Tx},
      {TEXT("ty"), ES08IconProp::Ty},       {TEXT("rotate"), ES08IconProp::Rotate},
      {TEXT("opacity"), ES08IconProp::Opacity}, {TEXT("frame"), ES08IconProp::Frame}};
  const ES08IconProp* Found = Map.Find(S);
  if (!Found) return false;
  Out = *Found;
  return true;
}

bool ParseEase(const FString& S, ES08IconEase& Out) {
  static const TMap<FString, ES08IconEase> Map = {
      {TEXT("linear"), ES08IconEase::Linear},           {TEXT("constant"), ES08IconEase::Constant},
      {TEXT("ease_in_quad"), ES08IconEase::EaseInQuad}, {TEXT("ease_out_quad"), ES08IconEase::EaseOutQuad},
      {TEXT("ease_out_cubic"), ES08IconEase::EaseOutCubic},
      {TEXT("ease_in_out_cubic"), ES08IconEase::EaseInOutCubic}};
  const ES08IconEase* Found = Map.Find(S);
  if (!Found) return false;
  Out = *Found;
  return true;
}

bool ParseKind(const FString& S, ES08IconAnimKind& Out) {
  if (S == TEXT("enter")) Out = ES08IconAnimKind::Enter;
  else if (S == TEXT("loop")) Out = ES08IconAnimKind::Loop;
  else if (S == TEXT("exit")) Out = ES08IconAnimKind::Exit;
  else if (S == TEXT("event")) Out = ES08IconAnimKind::Event;
  else return false;
  return true;
}

bool ReadVec2(const TSharedPtr<FJsonValue>& V, FVector2D& Out) {
  const TArray<TSharedPtr<FJsonValue>>* A = nullptr;
  if (!V.IsValid() || !V->TryGetArray(A) || A->Num() != 2) return false;
  Out = FVector2D((*A)[0]->AsNumber(), (*A)[1]->AsNumber());
  return true;
}

int32 TargetIndex(const FS08IconMotionDef& Def, const FString& Name) {
  if (Name == TEXT("all")) return 0;
  for (int32 I = 0; I < Def.Layers.Num(); ++I) {
    if (Def.Layers[I].Id.ToString() == Name) return I + 1;
  }
  return INDEX_NONE;
}

bool ParseBranch(const FS08IconMotionDef& Def, const TSharedPtr<FJsonObject>& Obj, FS08IconBranch& Out,
                 FString& Err) {
  Out.DurationMs = static_cast<float>(Obj->GetNumberField(TEXT("duration_ms")));
  const TArray<TSharedPtr<FJsonValue>>* Tracks = nullptr;
  if (!Obj->TryGetArrayField(TEXT("tracks"), Tracks)) {
    Err = TEXT("no tracks");
    return false;
  }
  for (const TSharedPtr<FJsonValue>& TV : *Tracks) {
    const TSharedPtr<FJsonObject> T = TV->AsObject();
    FS08IconTrack Track;
    Track.Target = TargetIndex(Def, T->GetStringField(TEXT("target")));
    if (Track.Target == INDEX_NONE) {
      Err = FString::Printf(TEXT("unknown target %s"), *T->GetStringField(TEXT("target")));
      return false;
    }
    if (!ParseProp(T->GetStringField(TEXT("prop")), Track.Prop)) {
      Err = FString::Printf(TEXT("unknown prop %s"), *T->GetStringField(TEXT("prop")));
      return false;
    }
    for (const TSharedPtr<FJsonValue>& KV : T->GetArrayField(TEXT("keys"))) {
      const TArray<TSharedPtr<FJsonValue>>& K = KV->AsArray();
      if (K.Num() != 3) {
        Err = TEXT("key is not [t, v, ease]");
        return false;
      }
      FS08IconKey Key;
      Key.T = static_cast<float>(K[0]->AsNumber());
      Key.bFromStart = K[1]->IsNull();
      Key.V = Key.bFromStart ? 0.0f : static_cast<float>(K[1]->AsNumber());
      if (!ParseEase(K[2]->AsString(), Key.Ease)) {
        Err = FString::Printf(TEXT("unknown ease %s"), *K[2]->AsString());
        return false;
      }
      Track.Keys.Add(Key);
    }
    if (Track.Keys.Num() == 0) {
      Err = TEXT("empty track");
      return false;
    }
    Out.Tracks.Add(MoveTemp(Track));
  }
  return true;
}

bool ParseIcon(FName Icon, const TSharedPtr<FJsonObject>& Obj, FS08IconMotionDef& Def, FString& Err) {
  Def.Icon = Icon;
  ReadVec2(Obj->TryGetField(TEXT("canvas_u")), Def.CanvasU);
  for (const TSharedPtr<FJsonValue>& LV : Obj->GetArrayField(TEXT("layers"))) {
    const TSharedPtr<FJsonObject> L = LV->AsObject();
    FS08IconLayer Layer;
    Layer.Id = FName(*L->GetStringField(TEXT("id")));
    Layer.Src = L->GetStringField(TEXT("src"));
    L->TryGetNumberField(TEXT("frames"), Layer.Frames);
    Layer.bHasPivot = ReadVec2(L->TryGetField(TEXT("pivot_u")), Layer.PivotU);
    FString Tint;
    Layer.bTintTeam = L->TryGetStringField(TEXT("tint"), Tint) && Tint == TEXT("team");
    const TSharedPtr<FJsonObject>* Rest = nullptr;
    if (L->TryGetObjectField(TEXT("rest"), Rest)) {
      for (const auto& Pair : (*Rest)->Values) {
        ES08IconProp P;
        if (!ParseProp(FString(*Pair.Key), P)) {
          Err = FString::Printf(TEXT("%s: unknown rest prop %s"), *Icon.ToString(), *Pair.Key);
          return false;
        }
        Layer.Rest[static_cast<int32>(P)] = static_cast<float>(Pair.Value->AsNumber());
      }
    }
    Def.Layers.Add(MoveTemp(Layer));
  }
  const TSharedPtr<FJsonObject>* AnimsObj = nullptr;
  if (!Obj->TryGetObjectField(TEXT("anims"), AnimsObj)) {
    Err = FString::Printf(TEXT("%s: no anims"), *Icon.ToString());
    return false;
  }
  for (const auto& Pair : (*AnimsObj)->Values) {
    const TSharedPtr<FJsonObject> A = Pair.Value.IsValid() ? Pair.Value->AsObject() : nullptr;
    if (!A.IsValid()) {
      Err = FString::Printf(TEXT("%s.%s: not an object"), *Icon.ToString(), *Pair.Key);
      return false;
    }
    FS08IconAnim Anim;
    Anim.Name = FName(*Pair.Key);
    if (!ParseKind(A->GetStringField(TEXT("kind")), Anim.Kind)) {
      Err = FString::Printf(TEXT("%s.%s: unknown kind"), *Icon.ToString(), *Pair.Key);
      return false;
    }
    A->TryGetBoolField(TEXT("hold"), Anim.bHold);
    double Beat = -1.0;
    if (A->TryGetNumberField(TEXT("beat_ms"), Beat)) Anim.BeatMs = static_cast<float>(Beat);
    double Stagger = 0.0;
    if (A->TryGetNumberField(TEXT("stagger_ms"), Stagger)) Anim.StaggerMs = static_cast<float>(Stagger);
    FString BranchErr;
    if (!ParseBranch(Def, A, Anim.Normal, BranchErr)) {
      Err = FString::Printf(TEXT("%s.%s: %s"), *Icon.ToString(), *Pair.Key, *BranchErr);
      return false;
    }
    const TSharedPtr<FJsonObject>* Red = nullptr;
    if (A->TryGetObjectField(TEXT("reduced"), Red)) {
      Anim.bHasReduced = true;
      if (!ParseBranch(Def, *Red, Anim.Reduced, BranchErr)) {
        Err = FString::Printf(TEXT("%s.%s reduced: %s"), *Icon.ToString(), *Pair.Key, *BranchErr);
        return false;
      }
    }
    const TSharedPtr<FJsonObject>* Pivots = nullptr;
    if (A->TryGetObjectField(TEXT("pivot_u"), Pivots)) {
      for (const auto& PV : (*Pivots)->Values) {
        const int32 Target = TargetIndex(Def, FString(*PV.Key));
        FVector2D P;
        if (Target == INDEX_NONE || !ReadVec2(PV.Value, P)) {
          Err = FString::Printf(TEXT("%s.%s: bad pivot %s"), *Icon.ToString(), *Pair.Key, *PV.Key);
          return false;
        }
        Anim.Pivots.Add(Target, P);
      }
    }
    Def.Anims.Add(Anim.Name, MoveTemp(Anim));
  }
  const TArray<TSharedPtr<FJsonValue>>* Demo = nullptr;
  if (Obj->TryGetArrayField(TEXT("demo"), Demo)) {
    for (const TSharedPtr<FJsonValue>& SV : *Demo) {
      const TArray<TSharedPtr<FJsonValue>>* SA = nullptr;
      if (!SV.IsValid() || !SV->TryGetArray(SA) || SA->Num() == 0) {
        Err = FString::Printf(TEXT("%s: bad demo step"), *Icon.ToString());
        return false;
      }
      const TArray<TSharedPtr<FJsonValue>>& S = *SA;
      FS08IconDemoStep Step;
      Step.Op = FName(*S[0]->AsString());
      if (S.Num() > 1) Step.Value = static_cast<float>(S[1]->AsNumber());
      Def.Demo.Add(Step);
    }
  }
  if (!Def.Anims.Contains(NameAppear) || !Def.Anims.Contains(NameLeave)) {
    Err = FString::Printf(TEXT("%s: appear/leave missing"), *Icon.ToString());
    return false;
  }
  return true;
}
}  // namespace

// ------------------------------------------------------------------------------------------- helpers

bool FS08IconTrack::HasFromStart() const {
  for (const FS08IconKey& K : Keys) {
    if (K.bFromStart) return true;
  }
  return false;
}

FVector2D FS08IconMotionDef::PivotOf(int32 Target, const TMap<int32, FVector2D>& Active) const {
  if (const FVector2D* P = Active.Find(Target)) return *P;
  if (Target > 0 && Layers.IsValidIndex(Target - 1) && Layers[Target - 1].bHasPivot) return Layers[Target - 1].PivotU;
  return CanvasU * 0.5;
}

float S08IconMotion::Ease(ES08IconEase E, float X) {
  X = FMath::Clamp(X, 0.0f, 1.0f);
  switch (E) {
    case ES08IconEase::Linear: return X;
    case ES08IconEase::Constant: return 0.0f;
    case ES08IconEase::EaseInQuad: return X * X;
    case ES08IconEase::EaseOutQuad: return 1.0f - (1.0f - X) * (1.0f - X);
    case ES08IconEase::EaseOutCubic: return 1.0f - FMath::Pow(1.0f - X, 3.0f);
    case ES08IconEase::EaseInOutCubic:
      return X < 0.5f ? 4.0f * X * X * X : 1.0f - FMath::Pow(-2.0f * X + 2.0f, 3.0f) / 2.0f;
  }
  return X;
}

float S08IconMotion::EvalKeys(const TArray<FS08IconKey>& Keys, float T, float Start) {
  auto Val = [Start](const FS08IconKey& K) { return K.bFromStart ? Start : K.V; };
  if (T <= Keys[0].T) return Val(Keys[0]);
  int32 I = 0;
  for (int32 J = 0; J < Keys.Num(); ++J) {
    if (Keys[J].T <= T) I = J;
    else break;
  }
  if (I == Keys.Num() - 1) return Val(Keys[I]);
  const FS08IconKey& K0 = Keys[I];
  const FS08IconKey& K1 = Keys[I + 1];
  if (K0.Ease == ES08IconEase::Constant || K1.T <= K0.T) return Val(K0);
  const float X = (T - K0.T) / (K1.T - K0.T);
  const float A = Val(K0);
  const float B = Val(K1);
  return A + (B - A) * Ease(K0.Ease, X);
}

bool S08IconMotion::IsReducedMotion() {
  // MS-T-16: the saved US08UserSettings::bReducedMotion joins the CVar and the flag (S08Motion::Current).
  return CVarS08ReducedMotion.GetValueOnGameThread() > 0 || S08Motion::Current().bReducedMotion;
}

bool S08IconMotion::UseAnimatedCombatToken(const TCHAR* CommandLine) {
  return !FParse::Param(CommandLine, TEXT("S08IconLegacy"));
}

FString S08IconMotion::TextureObjectPath(const FString& Src, int32 Frame, int32 SizePx) {
  FString Name = Src;
  if (Name.EndsWith(TEXT("#"))) Name = Name.LeftChop(1) + FString::Printf(TEXT("_f%02d"), Frame);
  const FString Asset = FString::Printf(TEXT("T_IV3_%s_%d"), *Name.Replace(TEXT("-"), TEXT("_")), SizePx);
  return FString::Printf(TEXT("/Game/S08/UI/IconsV3/%s.%s"), *Asset, *Asset);
}

int32 S08IconMotion::ExportSizePx(float Su, float PxPerSu, bool* bOutClamped) {
  const float Px = Su * (PxPerSu > 0.0f ? PxPerSu : 1.0f);
  if (bOutClamped) *bOutClamped = false;
  for (const int32 Size : UeExportSizes) {
    if (static_cast<float>(Size) + 0.05f >= Px) return Size;
  }
  if (bOutClamped) *bOutClamped = true;
  return UeExportSizes[UE_ARRAY_COUNT(UeExportSizes) - 1];
}

bool S08IconMotion::IconSizeLegacy(const TCHAR* CommandLine) {
  return CommandLine && FParse::Param(CommandLine, TEXT("S08IconLegacy"));
}

void S08IconMotion::DemoSchedule(const FS08IconMotionDef& Def, bool bReduced, TArray<TPair<float, FName>>& Out,
                                 float& OutTotalMs) {
  Out.Reset();
  float T = 0.0f;
  for (const FS08IconDemoStep& Step : Def.Demo) {
    if (Step.Op == NameWait) {
      T += Step.Value;
    } else if (Step.Op == NameCycle) {
      const FS08IconAnim* Cycle = Def.FindAnim(NameCycle);
      if (!Cycle) continue;
      float Period = Cycle->Normal.DurationMs;
      if (bReduced && Cycle->bHasReduced && Cycle->Reduced.Tracks.Num() > 0) Period = Cycle->Reduced.DurationMs;
      T += Period * Step.Value;
    } else {
      Out.Emplace(T, Step.Op);
      if (Step.Op == NameAppear || Step.Op == NameLeave) {
        if (const FS08IconAnim* A = Def.FindAnim(Step.Op)) T += A->Branch(bReduced).DurationMs;
      }
    }
  }
  OutTotalMs = T;
}

// ------------------------------------------------------------------------------------------- library

FString FS08IconMotionLibrary::DefaultPath() {
  return FPaths::Combine(FPaths::ProjectConfigDir(), TEXT("S08IconMotion.json"));
}

bool FS08IconMotionLibrary::LoadFile(const FString& Path, FString* OutError) {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *Path)) {
    if (OutError) *OutError = FString::Printf(TEXT("cannot read %s"), *Path);
    return false;
  }
  return LoadFromString(Text, OutError);
}

bool FS08IconMotionLibrary::LoadFromString(const FString& Json, FString* OutError) {
  Icons.Reset();
  Order.Reset();
  Variants.Reset();
  bLoaded = false;
  TSharedPtr<FJsonObject> Root;
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
  if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid()) {
    if (OutError) *OutError = TEXT("invalid JSON");
    return false;
  }
  if (Root->GetStringField(TEXT("schema")) != TEXT("unmatched.icon-motion/1")) {
    if (OutError) *OutError = TEXT("schema is not unmatched.icon-motion/1");
    return false;
  }
  Revision = Root->GetStringField(TEXT("revision"));
  for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("order"))) Order.Add(FName(*V->AsString()));
  const TSharedPtr<FJsonObject>* VarObj = nullptr;
  if (Root->TryGetObjectField(TEXT("variants"), VarObj)) {
    for (const auto& Pair : (*VarObj)->Values) Variants.Add(FName(*Pair.Key), FName(*Pair.Value->AsString()));
  }
  const TSharedPtr<FJsonObject>* IconsObj = nullptr;
  if (!Root->TryGetObjectField(TEXT("icons"), IconsObj)) {
    if (OutError) *OutError = TEXT("no icons");
    return false;
  }
  for (const auto& Pair : (*IconsObj)->Values) {
    FS08IconMotionDef Def;
    FString Err;
    const TSharedPtr<FJsonObject> IconObj = Pair.Value.IsValid() ? Pair.Value->AsObject() : nullptr;
    if (!IconObj.IsValid() || !ParseIcon(FName(*Pair.Key), IconObj, Def, Err)) {
      if (Err.IsEmpty()) Err = FString::Printf(TEXT("%s: not an object"), *Pair.Key);
      if (OutError) *OutError = Err;
      Icons.Reset();
      return false;
    }
    Icons.Add(Def.Icon, MoveTemp(Def));
  }
  bLoaded = true;
  return true;
}

const FS08IconMotionLibrary& FS08IconMotionLibrary::Get() {
  static FS08IconMotionLibrary Lib;  // game thread only (widgets, gallery, tests)
  if (!Lib.bLoadAttempted) {
    Lib.bLoadAttempted = true;
    FString Err;
    if (!Lib.LoadFile(DefaultPath(), &Err)) UE_LOG(LogTemp, Error, TEXT("S08 icon motion: %s"), *Err);
  }
  return Lib;
}

const FS08IconMotionDef* FS08IconMotionLibrary::Find(FName Icon) const {
  if (const FName* Base = Variants.Find(Icon)) Icon = *Base;
  return Icons.Find(Icon);
}

// ------------------------------------------------------------------------------------------- animator

void FS08IconAnimator::Init(const FS08IconMotionDef* InDef, bool bInReduced) {
  Def = InDef;
  bReduced = bInReduced;
  bHasBase = false;
  Base = FPlay();
  Events.Reset();
  bShown = false;
  bHasHiddenFrom = false;
  HiddenFrom = 0.0f;
}

bool FS08IconAnimator::Play(FName AnimName, float TMs) {
  if (!Def) return false;
  const FS08IconAnim* Anim = Def->FindAnim(AnimName);
  if (!Anim) return false;
  FPlay P;
  P.Anim = Anim;
  P.T0 = TMs;
  P.Seq = ++SeqCounter;
  P.Branch = &Anim->Branch(bReduced);
  P.Dur = P.Branch->DurationMs;
  bool bNeeds = false;
  for (const FS08IconTrack& Tr : P.Branch->Tracks) bNeeds |= Tr.HasFromStart();
  if (bNeeds) {
    const FS08IconPose Cur = Pose(TMs);
    for (const FS08IconTrack& Tr : P.Branch->Tracks) {
      if (Tr.HasFromStart()) P.Start.Add(Key(Tr.Target, Tr.Prop), Cur.Targets[Tr.Target].Get(Tr.Prop));
    }
  }
  if (Anim->Kind == ES08IconAnimKind::Event) {
    TSet<uint32> Covered;
    for (const FS08IconTrack& Tr : P.Branch->Tracks) Covered.Add(Key(Tr.Target, Tr.Prop));
    TArray<FPlay> Keep;
    for (FPlay& E : Events) {
      const bool bDone = TMs - E.T0 >= E.Dur;
      bool bSubset = true;
      for (const FS08IconTrack& Tr : E.Branch->Tracks) bSubset &= Covered.Contains(Key(Tr.Target, Tr.Prop));
      // A finished event is dropped when the new one covers all its tracks; a held one only by a new held one
      // (a short tap plays over a hover and hands the hover's value back).
      if (bDone && bSubset && (!E.Anim->bHold || Anim->bHold)) continue;
      Keep.Add(MoveTemp(E));
    }
    Keep.Add(MoveTemp(P));
    Events = MoveTemp(Keep);
  } else {
    Base = MoveTemp(P);
    bHasBase = true;
    if (Anim->Kind == ES08IconAnimKind::Enter) {
      bShown = true;
      bHasHiddenFrom = false;
      Events.Reset();
    } else if (Anim->Kind == ES08IconAnimKind::Exit) {
      // The exit owns everything: held events (hover, spend) no longer cover the fade; their values are already
      // in the exit's from-start keys.
      bHasHiddenFrom = true;
      HiddenFrom = TMs + Base.Dur;
      Events.Reset();
    }
  }
  return true;
}

bool FS08IconAnimator::BaseAt(float TMs, FPlay& OutPlay, float& OutLocal) const {
  if (!bHasBase || !Base.Anim) return false;
  const float Lt = TMs - Base.T0;
  if (Base.Anim->Kind == ES08IconAnimKind::Enter && Lt >= Base.Dur) {
    const FS08IconAnim* Cycle = Def->FindAnim(NameCycle);
    if (!Cycle) return false;
    const FS08IconBranch& Br = Cycle->Branch(bReduced);
    if (Br.DurationMs <= 0.0f || Br.Tracks.Num() == 0) return false;
    OutPlay = FPlay();
    OutPlay.Anim = Cycle;
    OutPlay.Branch = &Br;
    OutPlay.T0 = Base.T0 + Base.Dur;
    OutPlay.Dur = Br.DurationMs;
    OutLocal = FMath::Fmod(TMs - OutPlay.T0, OutPlay.Dur);
    if (OutLocal < 0.0f) OutLocal += OutPlay.Dur;  // Python % semantics
    return true;
  }
  if (Base.Anim->Kind == ES08IconAnimKind::Loop) {
    if (Base.Dur <= 0.0f || Base.Branch->Tracks.Num() == 0) return false;
    OutPlay = Base;
    OutLocal = FMath::Fmod(Lt, Base.Dur);
    if (OutLocal < 0.0f) OutLocal += Base.Dur;
    return true;
  }
  OutPlay = Base;
  OutLocal = FMath::Min(Lt, Base.Dur);
  return true;
}

FS08IconPose FS08IconAnimator::Pose(float TMs) const {
  FS08IconPose Out;
  if (!Def) return Out;
  Out.Targets.SetNum(Def->TargetCount());
  for (int32 I = 0; I < Def->Layers.Num(); ++I) {
    FMemory::Memcpy(Out.Targets[I + 1].V, Def->Layers[I].Rest, sizeof(Def->Layers[I].Rest));
  }
  Out.bVisible = bShown && (!bHasHiddenFrom || TMs < HiddenFrom);
  // An appear scheduled in the future (hint cascade, stagger_ms) has not started yet.
  if (bHasBase && Base.Anim && Base.Anim->Kind == ES08IconAnimKind::Enter && TMs < Base.T0) Out.bVisible = false;
  TMap<int32, FVector2D> Pivots;
  FPlay B;
  float Lt = 0.0f;
  if (BaseAt(TMs, B, Lt)) {
    for (const FS08IconTrack& Tr : B.Branch->Tracks) {
      float& Slot = Out.Targets[Tr.Target].V[static_cast<int32>(Tr.Prop)];
      const float* S = B.Start.Find(Key(Tr.Target, Tr.Prop));
      Slot = S08IconMotion::EvalKeys(Tr.Keys, Lt, S ? *S : Slot);
    }
    for (const auto& P : B.Anim->Pivots) Pivots.Add(P.Key, P.Value);
  }
  // An event in effect (running, or held) owns its (target, prop) until a later event in effect takes the same
  // track; a finished event without hold owns nothing, so an earlier hold (hover 1.06 after a tap) or the
  // base/rest shows again. Order (T0, Seq): at equal T0 the later command wins.
  TArray<const FPlay*, TInlineAllocator<8>> Started;
  for (const FPlay& E : Events) {
    if (TMs >= E.T0 && (TMs - E.T0 < E.Dur || E.Anim->bHold)) Started.Add(&E);
  }
  Algo::Sort(Started, [](const FPlay* A, const FPlay* B2) { return A->T0 != B2->T0 ? A->T0 > B2->T0 : A->Seq > B2->Seq; });
  TSet<uint32, DefaultKeyFuncs<uint32>, TInlineSetAllocator<16>> Claimed;
  for (const FPlay* E : Started) {
    const float Local = TMs - E->T0;
    for (const FS08IconTrack& Tr : E->Branch->Tracks) {
      const uint32 K = Key(Tr.Target, Tr.Prop);
      if (Claimed.Contains(K)) continue;
      Claimed.Add(K);
      float& Slot = Out.Targets[Tr.Target].V[static_cast<int32>(Tr.Prop)];
      const float* S = E->Start.Find(K);
      Slot = S08IconMotion::EvalKeys(Tr.Keys, FMath::Min(Local, E->Dur), S ? *S : Slot);
    }
    for (const auto& P : E->Anim->Pivots) {
      if (!Pivots.Contains(P.Key)) Pivots.Add(P.Key, P.Value);
    }
  }
  for (int32 T = 0; T < Out.Targets.Num(); ++T) Out.Targets[T].PivotU = Def->PivotOf(T, Pivots);
  return Out;
}

bool FS08IconAnimator::IsCycling(float TMs) const {
  FPlay B;
  float Lt = 0.0f;
  return BaseAt(TMs, B, Lt) && B.Anim && B.Anim->Kind == ES08IconAnimKind::Loop;
}

bool FS08IconAnimator::IsMoving(float TMs) const {
  if (!Def) return false;
  if (bHasBase && Base.Anim) {
    const float Lt = TMs - Base.T0;
    switch (Base.Anim->Kind) {
      case ES08IconAnimKind::Enter: {
        if (Lt < Base.Dur) return true;
        const FS08IconAnim* Cycle = Def->FindAnim(NameCycle);
        if (Cycle && Cycle->Branch(bReduced).DurationMs > 0.0f && Cycle->Branch(bReduced).Tracks.Num() > 0) return true;
        break;
      }
      case ES08IconAnimKind::Loop:
        if (Base.Dur > 0.0f && Base.Branch->Tracks.Num() > 0) return true;
        break;
      case ES08IconAnimKind::Exit:
        if (Lt < Base.Dur) return true;
        break;
      default:
        break;
    }
  }
  for (const FPlay& E : Events) {
    if (TMs >= E.T0 && TMs - E.T0 < E.Dur && E.Branch->Tracks.Num() > 0) return true;
  }
  return false;
}

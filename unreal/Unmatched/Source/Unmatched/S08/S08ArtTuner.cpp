// Art Tuner M2: the data model (S08ArtTuner.h).
#include "S08ArtTuner.h"

#include "S08BoardArt.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Policies/CondensedJsonPrintPolicy.h"

namespace S08ArtTunerSpec {
FString DefaultParamsPath() {
  return FPaths::Combine(FPaths::ProjectConfigDir(), TEXT("ArtTuner"), TEXT("S08ArtTunerParams.json"));
}

bool Enabled(const TCHAR* CommandLine) {
  return FParse::Param(CommandLine ? CommandLine : FCommandLine::Get(), FlagName);
}

FString FileFromCommandLine(const TCHAR* CommandLine) {
  FString File;
  FParse::Value(CommandLine ? CommandLine : FCommandLine::Get(), FileParam, File);
  return File.TrimQuotes();
}
}  // namespace S08ArtTunerSpec

namespace {
struct FScopeName {
  ES08TunerScope Scope;
  const TCHAR* Name;
};
const FScopeName GScopeNames[] = {
    {ES08TunerScope::HeroLight, TEXT("heroLight")},       {ES08TunerScope::ProfileLights, TEXT("profileLights")},
    {ES08TunerScope::MapGrade, TEXT("mapGrade")},         {ES08TunerScope::ConceptLights, TEXT("conceptLights")},
    {ES08TunerScope::Materials, TEXT("materials")},       {ES08TunerScope::Rebuild, TEXT("rebuild")},
};

bool TunerReadObject(const FString& Text, TSharedPtr<FJsonObject>& Out, bool bNumbersAsText) {
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
  TSharedPtr<FJsonValue> Root;
  if (!FJsonSerializer::Deserialize(Reader, Root, bNumbersAsText ? FJsonSerializer::EFlags::StoreNumbersAsStrings
                                                                 : FJsonSerializer::EFlags::None) ||
      !Root.IsValid() || Root->Type != EJson::Object) {
    return false;
  }
  Out = Root->AsObject();
  return Out.IsValid();
}

FString TunerObjectText(const TSharedRef<FJsonObject>& Obj, bool bPretty) {
  FString Text;
  if (bPretty) {
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Text);
    FJsonSerializer::Serialize(Obj, Writer);
  } else {
    const TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
        TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Text);
    FJsonSerializer::Serialize(Obj, Writer);
  }
  return Text;
}

FString TunerQuote(const FString& S) {
  FString Out = TEXT("\"");
  for (const TCHAR C : S) {
    switch (C) {
      case TCHAR('"'): Out += TEXT("\\\""); break;
      case TCHAR('\\'): Out += TEXT("\\\\"); break;
      case TCHAR('\n'): Out += TEXT("\\n"); break;
      case TCHAR('\r'): Out += TEXT("\\r"); break;
      case TCHAR('\t'): Out += TEXT("\\t"); break;
      default:
        if (C < 0x20) Out += FString::Printf(TEXT("\\u%04x"), static_cast<int32>(C));
        else Out.AppendChar(C);
    }
  }
  return Out + TEXT("\"");
}

/** Shortest text that parses back to the same double. */
FString TunerNumberText(double V) {
  if (FMath::IsNearlyEqual(V, FMath::RoundToDouble(V), 1e-12) && FMath::Abs(V) < 1e15) {
    return FString::Printf(TEXT("%lld"), static_cast<long long>(FMath::RoundToDouble(V)));
  }
  for (int32 P = 1; P <= 17; ++P) {
    const FString S = FString::Printf(TEXT("%.*g"), P, V);
    if (FCString::Atod(*S) == V) return S;
  }
  return FString::Printf(TEXT("%.17g"), V);
}

TSharedPtr<FJsonValue> TunerChild(const TSharedPtr<FJsonValue>& Node, const FString& Segment) {
  if (!Node.IsValid()) return nullptr;
  if (Node->Type == EJson::Object) {
    const TSharedPtr<FJsonObject> Obj = Node->AsObject();
    return Obj.IsValid() ? Obj->TryGetField(Segment) : nullptr;
  }
  if (Node->Type == EJson::Array) {
    if (Segment.IsEmpty() || !Segment.IsNumeric() || Segment.Contains(TEXT(".")) || Segment.Contains(TEXT("-"))) return nullptr;
    const int32 Index = FCString::Atoi(*Segment);
    const TArray<TSharedPtr<FJsonValue>>& Arr = Node->AsArray();
    return Arr.IsValidIndex(Index) ? Arr[Index] : nullptr;
  }
  return nullptr;
}

/** Functional set: returns the node with Segments[I..] replaced (objects are changed in place, arrays rebuilt). */
TSharedPtr<FJsonValue> TunerWith(const TSharedPtr<FJsonValue>& Node, const TArray<FString>& Segments, int32 I,
                                 const TSharedPtr<FJsonValue>& Value, bool bCreateLeaf, FString& OutError) {
  if (I == Segments.Num()) return Value;
  if (!Node.IsValid()) {
    OutError = FString::Printf(TEXT("missing parent of '%s'"), *Segments[I]);
    return nullptr;
  }
  const FString& Seg = Segments[I];
  const bool bLeaf = I == Segments.Num() - 1;
  if (Node->Type == EJson::Object) {
    const TSharedPtr<FJsonObject> Obj = Node->AsObject();
    TSharedPtr<FJsonValue> Child = Obj->TryGetField(Seg);
    if (!Child.IsValid() && !bCreateLeaf) {
      OutError = FString::Printf(TEXT("no key '%s'"), *Seg);
      return nullptr;
    }
    // a missing object on the way to a new leaf (Art Tuner M4: lit3d.materialOverrides.<Look>.<key>)
    if (!Child.IsValid() && !bLeaf) Child = MakeShared<FJsonValueObject>(MakeShared<FJsonObject>());
    const TSharedPtr<FJsonValue> NewChild = TunerWith(Child, Segments, I + 1, Value, bCreateLeaf, OutError);
    if (!NewChild.IsValid()) return nullptr;
    Obj->SetField(Seg, NewChild);
    return Node;
  }
  if (Node->Type == EJson::Array) {
    TArray<TSharedPtr<FJsonValue>> Arr = Node->AsArray();
    if (Seg.IsEmpty() || !Seg.IsNumeric() || Seg.Contains(TEXT(".")) || Seg.Contains(TEXT("-"))) {
      OutError = FString::Printf(TEXT("'%s' is not an array index"), *Seg);
      return nullptr;
    }
    const int32 Index = FCString::Atoi(*Seg);
    if (!Arr.IsValidIndex(Index)) {
      OutError = FString::Printf(TEXT("index %d out of range (%d)"), Index, Arr.Num());
      return nullptr;
    }
    const TSharedPtr<FJsonValue> NewChild = TunerWith(Arr[Index], Segments, I + 1, Value, bCreateLeaf, OutError);
    if (!NewChild.IsValid()) return nullptr;
    Arr[Index] = NewChild;
    return MakeShared<FJsonValueArray>(Arr);
  }
  OutError = FString::Printf(TEXT("'%s' is below a value"), *Seg);
  return nullptr;
}

FString TunerTemplate(const FString& In, const FString& Profile, int32 Board) {
  return In.Replace(TEXT("{profile}"), *S08JsonPointer::Escape(Profile)).Replace(TEXT("{board}"), *FString::FromInt(Board));
}

double TunerNumber(const TSharedPtr<FJsonObject>& O, const TCHAR* Field, double Default) {
  double V = Default;
  O->TryGetNumberField(Field, V);
  return V;
}

bool TunerBool(const TSharedPtr<FJsonObject>& O, const TCHAR* Field, bool Default) {
  bool V = Default;
  O->TryGetBoolField(Field, V);
  return V;
}
}  // namespace

bool S08TunerScopeFromName(const FString& Name, ES08TunerScope& Out) {
  for (const FScopeName& S : GScopeNames) {
    if (Name == S.Name) {
      Out = S.Scope;
      return true;
    }
  }
  return false;
}

FString S08TunerScopeNames(ES08TunerScope Scopes) {
  TArray<FString> Names;
  for (const FScopeName& S : GScopeNames) {
    if (EnumHasAnyFlags(Scopes, S.Scope)) Names.Add(S.Name);
  }
  return Names.IsEmpty() ? FString(TEXT("-")) : FString::Join(Names, TEXT("+"));
}

const TCHAR* S08TunerTypeName(ES08TunerType Type) {
  switch (Type) {
    case ES08TunerType::Number: return TEXT("number");
    case ES08TunerType::Bool: return TEXT("bool");
    case ES08TunerType::ColorSrgb: return TEXT("colorSrgb");
    case ES08TunerType::ColorLinear: return TEXT("colorLinear");
    case ES08TunerType::Ev100: return TEXT("ev100");
  }
  return TEXT("?");
}

// ---- JSON pointer ----------------------------------------------------------------------------------------------------

namespace S08JsonPointer {
bool Split(const FString& Pointer, TArray<FString>& OutSegments) {
  OutSegments.Reset();
  if (Pointer.IsEmpty()) return true;
  if (!Pointer.StartsWith(TEXT("/"))) return false;
  TArray<FString> Raw;
  Pointer.Mid(1).ParseIntoArray(Raw, TEXT("/"), false);
  if (Pointer.EndsWith(TEXT("/"))) Raw.Add(FString());
  for (const FString& R : Raw) OutSegments.Add(R.Replace(TEXT("~1"), TEXT("/")).Replace(TEXT("~0"), TEXT("~")));
  return true;
}

FString Escape(const FString& Segment) { return Segment.Replace(TEXT("~"), TEXT("~0")).Replace(TEXT("/"), TEXT("~1")); }

TSharedPtr<FJsonValue> Get(const TSharedPtr<FJsonObject>& Root, const FString& Pointer) {
  TArray<FString> Segments;
  if (!Root.IsValid() || !Split(Pointer, Segments)) return nullptr;
  TSharedPtr<FJsonValue> Node = MakeShared<FJsonValueObject>(Root);
  for (const FString& Seg : Segments) {
    Node = TunerChild(Node, Seg);
    if (!Node.IsValid()) return nullptr;
  }
  return Node;
}

bool Set(const TSharedPtr<FJsonObject>& Root, const FString& Pointer, const TSharedPtr<FJsonValue>& Value, bool bCreateLeaf,
         FString& OutError) {
  TArray<FString> Segments;
  if (!Root.IsValid() || !Value.IsValid()) {
    OutError = TEXT("no document / value");
    return false;
  }
  if (!Split(Pointer, Segments) || Segments.IsEmpty()) {
    OutError = FString::Printf(TEXT("'%s' is not a pointer below the root"), *Pointer);
    return false;
  }
  const TSharedPtr<FJsonValue> RootValue = MakeShared<FJsonValueObject>(Root);
  return TunerWith(RootValue, Segments, 0, Value, bCreateLeaf, OutError).IsValid();
}

FString ToText(const TSharedPtr<FJsonValue>& Value) {
  if (!Value.IsValid()) return TEXT("null");
  switch (Value->Type) {
    case EJson::Null: return TEXT("null");
    case EJson::Boolean: return Value->AsBool() ? TEXT("true") : TEXT("false");
    case EJson::String: return TunerQuote(Value->AsString());
    case EJson::Number:
      // a NumberString keeps its own text (the profile's / the saved file's), a plain number gets the shortest one
      return Value->PreferStringRepresentation() ? Value->AsString() : TunerNumberText(Value->AsNumber());
    case EJson::Array: {
      TArray<FString> Items;
      for (const TSharedPtr<FJsonValue>& V : Value->AsArray()) Items.Add(ToText(V));
      return TEXT("[") + FString::Join(Items, TEXT(", ")) + TEXT("]");
    }
    case EJson::Object: return TunerObjectText(Value->AsObject().ToSharedRef(), false);
    default: return TEXT("null");
  }
}

bool Equal(const TSharedPtr<FJsonValue>& A, const TSharedPtr<FJsonValue>& B) {
  if (!A.IsValid() || !B.IsValid()) return A.IsValid() == B.IsValid();
  if (A->Type != B->Type) return false;
  switch (A->Type) {
    case EJson::Number: return FMath::Abs(A->AsNumber() - B->AsNumber()) <= 1e-9;
    case EJson::Boolean: return A->AsBool() == B->AsBool();
    case EJson::String: return A->AsString().Equals(B->AsString(), ESearchCase::CaseSensitive);
    case EJson::Null: return true;
    case EJson::Array: {
      const TArray<TSharedPtr<FJsonValue>>& X = A->AsArray();
      const TArray<TSharedPtr<FJsonValue>>& Y = B->AsArray();
      if (X.Num() != Y.Num()) return false;
      for (int32 I = 0; I < X.Num(); ++I) {
        if (!Equal(X[I], Y[I])) return false;
      }
      return true;
    }
    default: return ToText(A) == ToText(B);
  }
}
}  // namespace S08JsonPointer

// ---- registry --------------------------------------------------------------------------------------------------------

int32 FS08TunerParam::Decimals() const {
  if (Step <= 0.0) return 3;
  int32 D = 0;
  double S = Step;
  while (D < 6 && FMath::Abs(S - FMath::RoundToDouble(S)) > 1e-9) {
    S *= 10.0;
    ++D;
  }
  return D;
}

TSharedPtr<FJsonValue> FS08TunerParam::DefaultValue() const {
  if (!bHasDefault) return nullptr;
  if (Type != ES08TunerType::ColorLinear) return MakeShared<FJsonValueNumber>(DefaultNumber);
  TArray<TSharedPtr<FJsonValue>> Channels;
  for (const double C : DefaultColor) Channels.Add(MakeShared<FJsonValueNumber>(C));
  return MakeShared<FJsonValueArray>(Channels);
}

double FS08TunerParam::Snap(double Value) const {
  double V = Step > 0.0 ? FMath::RoundToDouble(Value / Step) * Step : Value;
  // the decimals of the step (0.1 * 3 = 0.30000000000000004 -> 0.3)
  const double Scale = FMath::Pow(10.0, static_cast<double>(Decimals()));
  V = FMath::RoundToDouble(V * Scale) / Scale;
  if (bHasMin && bMinHard) V = FMath::Max(V, Min);
  if (bHasMax && bMaxHard) V = FMath::Min(V, Max);
  return V;
}

bool FS08ArtTunerRegistry::Parse(const FString& Text, TArray<FString>& OutErrors) {
  Groups.Reset();
  const int32 Before = OutErrors.Num();
  TSharedPtr<FJsonObject> Root;
  if (!TunerReadObject(Text, Root, false)) {
    OutErrors.Add(TEXT("params: not a JSON object"));
    return false;
  }
  FString Schema;
  if (!Root->TryGetStringField(TEXT("schema"), Schema) || Schema != S08ArtTunerSpec::ParamsSchema) {
    OutErrors.Add(FString::Printf(TEXT("params: schema must be %s"), S08ArtTunerSpec::ParamsSchema));
  }
  const TArray<TSharedPtr<FJsonValue>>* GroupValues = nullptr;
  if (!Root->TryGetArrayField(TEXT("groups"), GroupValues) || !GroupValues) {
    OutErrors.Add(TEXT("params: groups must be an array"));
    return false;
  }
  TSet<FString> GroupIds;
  for (int32 G = 0; G < GroupValues->Num(); ++G) {
    const TSharedPtr<FJsonObject> O = (*GroupValues)[G].IsValid() ? (*GroupValues)[G]->AsObject() : nullptr;
    if (!O.IsValid()) {
      OutErrors.Add(FString::Printf(TEXT("params: groups[%d] is not an object"), G));
      continue;
    }
    FTemplateGroup& T = Groups.AddDefaulted_GetRef();
    FString ScopeName;
    if (!O->TryGetStringField(TEXT("id"), T.Id) || T.Id.IsEmpty() || GroupIds.Contains(T.Id)) {
      OutErrors.Add(FString::Printf(TEXT("params: groups[%d] needs a unique id"), G));
    }
    GroupIds.Add(T.Id);
    O->TryGetStringField(TEXT("label"), T.Label);
    O->TryGetStringField(TEXT("when"), T.When);
    O->TryGetStringField(TEXT("each"), T.Each);
    if (!O->TryGetStringField(TEXT("scope"), ScopeName) || !S08TunerScopeFromName(ScopeName, T.Scope)) {
      OutErrors.Add(FString::Printf(TEXT("params: group %s scope '%s' unknown"), *T.Id, *ScopeName));
    }
    const TSharedPtr<FJsonObject>* Hidden = nullptr;
    if (O->TryGetObjectField(TEXT("hiddenIf"), Hidden) && Hidden && Hidden->IsValid()) {
      (*Hidden)->TryGetStringField(TEXT("pointer"), T.HiddenIfPointer);
      (*Hidden)->TryGetStringField(TEXT("contains"), T.HiddenIfContains);
      (*Hidden)->TryGetStringField(TEXT("note"), T.HiddenNote);
    }
    const TArray<TSharedPtr<FJsonValue>>* ParamValues = nullptr;
    if (!O->TryGetArrayField(TEXT("params"), ParamValues) || !ParamValues || ParamValues->IsEmpty()) {
      OutErrors.Add(FString::Printf(TEXT("params: group %s needs params"), *T.Id));
      continue;
    }
    TSet<FString> ParamIds;
    for (int32 I = 0; I < ParamValues->Num(); ++I) {
      const TSharedPtr<FJsonObject> PO = (*ParamValues)[I].IsValid() ? (*ParamValues)[I]->AsObject() : nullptr;
      if (!PO.IsValid()) {
        OutErrors.Add(FString::Printf(TEXT("params: %s.params[%d] is not an object"), *T.Id, I));
        continue;
      }
      FS08TunerParam P;
      FString TypeName;
      PO->TryGetStringField(TEXT("id"), P.Id);
      PO->TryGetStringField(TEXT("label"), P.Label);
      PO->TryGetStringField(TEXT("unit"), P.Unit);
      PO->TryGetStringField(TEXT("note"), P.Note);
      PO->TryGetStringField(TEXT("pointer"), P.Pointer);
      PO->TryGetStringField(TEXT("type"), TypeName);
      if (P.Id.IsEmpty() || ParamIds.Contains(P.Id)) {
        OutErrors.Add(FString::Printf(TEXT("params: %s.params[%d] needs a unique id"), *T.Id, I));
      }
      ParamIds.Add(P.Id);
      if (!P.Pointer.StartsWith(TEXT("/")) && !P.Pointer.StartsWith(TEXT("{each}"))) {
        OutErrors.Add(FString::Printf(TEXT("params: %s.%s pointer '%s' must start with / or {each}"), *T.Id, *P.Id, *P.Pointer));
      }
      if (P.Pointer.StartsWith(TEXT("{each}")) && T.Each.IsEmpty()) {
        OutErrors.Add(FString::Printf(TEXT("params: %s.%s uses {each} in a group without \"each\""), *T.Id, *P.Id));
      }
      if (TypeName == TEXT("number")) P.Type = ES08TunerType::Number;
      else if (TypeName == TEXT("bool")) P.Type = ES08TunerType::Bool;
      else if (TypeName == TEXT("colorSrgb")) P.Type = ES08TunerType::ColorSrgb;
      else if (TypeName == TEXT("colorLinear")) P.Type = ES08TunerType::ColorLinear;
      else if (TypeName == TEXT("ev100")) P.Type = ES08TunerType::Ev100;
      else OutErrors.Add(FString::Printf(TEXT("params: %s.%s type '%s' unknown"), *T.Id, *P.Id, *TypeName));
      P.Scope = T.Scope;
      P.bHasMin = PO->HasField(TEXT("min"));
      P.bHasMax = PO->HasField(TEXT("max"));
      P.Min = TunerNumber(PO, TEXT("min"), 0.0);
      P.Max = TunerNumber(PO, TEXT("max"), 0.0);
      P.bMinHard = TunerBool(PO, TEXT("minHard"), false);
      P.bMaxHard = TunerBool(PO, TEXT("maxHard"), false);
      P.Step = TunerNumber(PO, TEXT("step"), 0.01);
      P.SliderMin = TunerNumber(PO, TEXT("sliderMin"), P.bHasMin ? P.Min : 0.0);
      P.SliderMax = TunerNumber(PO, TEXT("sliderMax"), P.bHasMax ? P.Max : 1.0);
      P.bCross = TunerBool(PO, TEXT("cross"), false);
      P.bCreate = TunerBool(PO, TEXT("create"), false);
      P.bHasDefault = PO->HasField(TEXT("default"));
      P.DefaultNumber = TunerNumber(PO, TEXT("default"), 0.0);
      if (P.bHasDefault) {
        // a number row means a number; a colorLinear row [r, g, b] (a tint absent from the profile = [1, 1, 1])
        const TSharedPtr<FJsonValue> D = PO->TryGetField(TEXT("default"));
        bool bOk = D.IsValid() && (P.Type == ES08TunerType::ColorLinear ? D->Type == EJson::Array && D->AsArray().Num() == 3
                                                                         : D->Type == EJson::Number);
        if (bOk && P.Type == ES08TunerType::ColorLinear) {
          for (const TSharedPtr<FJsonValue>& C : D->AsArray()) {
            double V = 0.0;
            bOk = bOk && C.IsValid() && C->Type == EJson::Number && C->TryGetNumber(V) && FMath::IsFinite(V);
            P.DefaultColor.Add(V);
          }
        }
        if (!bOk || (P.Type != ES08TunerType::Number && P.Type != ES08TunerType::ColorLinear)) {
          OutErrors.Add(FString::Printf(TEXT("params: %s.%s default must be a number (number rows) or [r, g, b] (colorLinear rows)"),
                                        *T.Id, *P.Id));
        }
      }
      if (P.Step <= 0.0) OutErrors.Add(FString::Printf(TEXT("params: %s.%s step must be > 0"), *T.Id, *P.Id));
      if (P.SliderMax <= P.SliderMin) {
        OutErrors.Add(FString::Printf(TEXT("params: %s.%s slider range %g..%g is empty"), *T.Id, *P.Id, P.SliderMin, P.SliderMax));
      }
      if (P.bHasMin && P.bHasMax && P.Max < P.Min) {
        OutErrors.Add(FString::Printf(TEXT("params: %s.%s min > max"), *T.Id, *P.Id));
      }
      T.Params.Add(P);
    }
  }
  return OutErrors.Num() == Before;
}

bool FS08ArtTunerRegistry::LoadFile(const FString& Path, TArray<FString>& OutErrors) {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *Path)) {
    OutErrors.Add(FString::Printf(TEXT("params: cannot read %s"), *Path));
    return false;
  }
  return Parse(Text, OutErrors);
}

int32 FS08ArtTunerRegistry::NumTemplates() const {
  int32 N = 0;
  for (const FTemplateGroup& G : Groups) N += G.Params.Num();
  return N;
}

TArray<FS08TunerGroup> FS08ArtTunerRegistry::Expand(const TSharedPtr<FJsonObject>& Doc, const FString& ProfileId,
                                                     int32 BoardIndex) const {
  TArray<FS08TunerGroup> Out;
  if (!Doc.IsValid()) return Out;
  for (const FTemplateGroup& T : Groups) {
    const FString When = TunerTemplate(T.When, ProfileId, BoardIndex);
    if (!When.IsEmpty() && !S08JsonPointer::Get(Doc, When).IsValid()) continue;
    FS08TunerGroup G;
    G.Id = T.Id;
    G.Label = T.Label;
    G.Scope = T.Scope;
    if (!T.HiddenIfPointer.IsEmpty()) {
      const TSharedPtr<FJsonValue> List = S08JsonPointer::Get(Doc, TunerTemplate(T.HiddenIfPointer, ProfileId, BoardIndex));
      if (List.IsValid() && List->Type == EJson::Array) {
        for (const TSharedPtr<FJsonValue>& V : List->AsArray()) {
          if (V.IsValid() && V->Type == EJson::String && V->AsString() == T.HiddenIfContains) {
            G.Note = T.HiddenNote;
            G.bInert = true;
          }
        }
      }
    }
    // one block per element of "each" (or one block without it)
    TArray<TPair<FString, FString>> Blocks;  // element pointer, element label
    if (T.Each.IsEmpty()) {
      Blocks.Add({FString(), FString()});
    } else {
      const FString Each = TunerTemplate(T.Each, ProfileId, BoardIndex);
      const TSharedPtr<FJsonValue> Arr = S08JsonPointer::Get(Doc, Each);
      if (!Arr.IsValid() || Arr->Type != EJson::Array) continue;
      for (int32 I = 0; I < Arr->AsArray().Num(); ++I) {
        const TSharedPtr<FJsonObject> E = Arr->AsArray()[I].IsValid() ? Arr->AsArray()[I]->AsObject() : nullptr;
        FString Name = FString::Printf(TEXT("#%d"), I);
        if (E.IsValid() && !E->TryGetStringField(TEXT("id"), Name)) E->TryGetStringField(TEXT("name"), Name);
        Blocks.Add({FString::Printf(TEXT("%s/%d"), *Each, I), Name});
      }
    }
    for (int32 B = 0; B < Blocks.Num(); ++B) {
      for (const FS08TunerParam& PT : T.Params) {
        FS08TunerParam P = PT;
        P.GroupId = T.Id;
        P.Pointer = TunerTemplate(PT.Pointer, ProfileId, BoardIndex).Replace(TEXT("{each}"), *Blocks[B].Key);
        P.Label = PT.Label.Replace(TEXT("{id}"), *Blocks[B].Value).Replace(TEXT("{name}"), *Blocks[B].Value);
        P.Id = T.Each.IsEmpty() ? FString::Printf(TEXT("%s.%s"), *T.Id, *PT.Id)
                                : FString::Printf(TEXT("%s.%s#%d"), *T.Id, *PT.Id, B);
        const bool bExists = S08JsonPointer::Get(Doc, P.Pointer).IsValid();
        if (!bExists) {
          if (!P.bCreate) continue;
          // a new optional key: the nearest existing ancestor must be an object
          FString Ancestor = P.Pointer;
          TSharedPtr<FJsonValue> AncestorValue;
          while (!AncestorValue.IsValid()) {
            FString Parent, Leaf;
            if (!Ancestor.Split(TEXT("/"), &Parent, &Leaf, ESearchCase::CaseSensitive, ESearchDir::FromEnd)) break;
            Ancestor = Parent;
            AncestorValue = Ancestor.IsEmpty() ? MakeShared<FJsonValueObject>(Doc) : S08JsonPointer::Get(Doc, Ancestor);
          }
          if (!AncestorValue.IsValid() || AncestorValue->Type != EJson::Object) continue;
        }
        if (P.Type == ES08TunerType::Ev100) {
          const TSharedPtr<FJsonValue> Ev = S08JsonPointer::Get(Doc, P.Pointer + TEXT("/ev100"));
          if (!Ev.IsValid()) continue;
        }
        G.Params.Add(P);
      }
    }
    if (!G.Params.IsEmpty()) Out.Add(MoveTemp(G));
  }
  return Out;
}

// ---- model -----------------------------------------------------------------------------------------------------------

bool FS08ArtTunerModel::SetBase(const FString& Text, const FString& Sha256, TArray<FString>& OutErrors) {
  TSharedPtr<FJsonObject> Root;
  if (!TunerReadObject(Text, Root, true)) {
    OutErrors.Add(TEXT("profiles: not a JSON object"));
    return false;
  }
  BaseText = Text;
  BaseSha256 = Sha256;
  Base = Root;
  return true;
}

int32 FS08ArtTunerModel::GetBaseRevision() const {
  int32 Revision = 0;
  if (Base.IsValid()) Base->TryGetNumberField(TEXT("revision"), Revision);
  return Revision;
}

TSharedPtr<FJsonValue> FS08ArtTunerModel::BaseValue(const FString& Pointer) const { return S08JsonPointer::Get(Base, Pointer); }

TSharedPtr<FJsonValue> FS08ArtTunerModel::Value(const FString& Pointer) const {
  const int32 I = IndexOf(Pointer);
  return I != INDEX_NONE ? Entries[I].Value : BaseValue(Pointer);
}

int32 FS08ArtTunerModel::IndexOf(const FString& Pointer) const {
  for (int32 I = 0; I < Entries.Num(); ++I) {
    if (Entries[I].Pointer.Equals(Pointer, ESearchCase::CaseSensitive)) return I;
  }
  return INDEX_NONE;
}

bool FS08ArtTunerModel::SetValue(const FString& Pointer, const TSharedPtr<FJsonValue>& NewValue, bool bCreate,
                                 FString& OutError) {
  if (!Base.IsValid() || !NewValue.IsValid()) {
    OutError = TEXT("no base document / value");
    return false;
  }
  TArray<FString> Segments;
  if (!S08JsonPointer::Split(Pointer, Segments) || Segments.IsEmpty()) {
    OutError = FString::Printf(TEXT("'%s' is not a JSON pointer"), *Pointer);
    return false;
  }
  const TSharedPtr<FJsonValue> Old = BaseValue(Pointer);
  if (Old.IsValid()) {
    if (Old->Type != NewValue->Type) {
      OutError = FString::Printf(TEXT("%s: the base value is a %d, not a %d (EJson)"), *Pointer, static_cast<int32>(Old->Type),
                                 static_cast<int32>(NewValue->Type));
      return false;
    }
    if (Old->Type == EJson::Array && Old->AsArray().Num() != NewValue->AsArray().Num()) {
      OutError = FString::Printf(TEXT("%s: %d elements expected"), *Pointer, Old->AsArray().Num());
      return false;
    }
    if (Old->Type == EJson::Object) {
      OutError = FString::Printf(TEXT("%s: an object is not a tuner value"), *Pointer);
      return false;
    }
  } else {
    // a new key: the nearest existing ancestor must be an object (missing objects below it are created)
    FString Ancestor = Pointer;
    TSharedPtr<FJsonValue> AncestorValue;
    while (!AncestorValue.IsValid()) {
      FString Parent, Leaf;
      if (!Ancestor.Split(TEXT("/"), &Parent, &Leaf, ESearchCase::CaseSensitive, ESearchDir::FromEnd)) break;
      Ancestor = Parent;
      AncestorValue = Ancestor.IsEmpty() ? MakeShared<FJsonValueObject>(Base) : BaseValue(Ancestor);
    }
    if (!bCreate || !AncestorValue.IsValid() || AncestorValue->Type != EJson::Object) {
      OutError = FString::Printf(TEXT("%s: not in the profiles document"), *Pointer);
      return false;
    }
  }
  const int32 I = IndexOf(Pointer);
  if (Old.IsValid() && S08JsonPointer::Equal(Old, NewValue)) {
    if (I != INDEX_NONE) Entries.RemoveAt(I);  // back to the base: no entry
    return true;
  }
  if (I != INDEX_NONE) {
    Entries[I].Value = NewValue;
  } else {
    Entries.Add({Pointer, NewValue});
  }
  return true;
}

void FS08ArtTunerModel::Reset(const FString& Pointer) {
  const int32 I = IndexOf(Pointer);
  if (I != INDEX_NONE) Entries.RemoveAt(I);
}

bool FS08ArtTunerModel::BuildText(FString& OutText, TArray<FString>& OutErrors) const {
  TSharedPtr<FJsonObject> Doc;
  if (!TunerReadObject(BaseText, Doc, true)) {
    OutErrors.Add(TEXT("profiles: the base is not a JSON object"));
    return false;
  }
  bool bOk = true;
  for (const FS08TunerEntry& E : Entries) {
    FString Error;
    if (!S08JsonPointer::Set(Doc, E.Pointer, E.Value, true, Error)) {
      OutErrors.Add(FString::Printf(TEXT("%s: %s"), *E.Pointer, *Error));
      bOk = false;
    }
  }
  OutText = TunerObjectText(Doc.ToSharedRef(), false);
  return bOk;
}

bool FS08ArtTunerModel::Build(FS08BoardArtData& OutData, TArray<FString>& OutErrors) const {
  FString Text;
  if (!BuildText(Text, OutErrors)) return false;
  OutData = FS08BoardArtData();
  if (!OutData.ParseJson(Text, OutErrors)) return false;
  OutData.SourceSha256 = BaseSha256;
  return true;
}

// ---- overrides file --------------------------------------------------------------------------------------------------

bool FS08TunerOverridesFile::Parse(const FString& Text, TArray<FString>& OutErrors) {
  *this = FS08TunerOverridesFile();
  TSharedPtr<FJsonObject> Root;
  if (!TunerReadObject(Text, Root, true)) {
    OutErrors.Add(TEXT("overrides: not a JSON object"));
    return false;
  }
  FString Schema;
  if (!Root->TryGetStringField(TEXT("schema"), Schema) || Schema != S08ArtTunerSpec::OverridesSchema) {
    OutErrors.Add(FString::Printf(TEXT("overrides: schema must be %s"), S08ArtTunerSpec::OverridesSchema));
    return false;
  }
  Root->TryGetStringField(TEXT("savedAt"), SavedAt);
  Root->TryGetStringField(TEXT("baseProfilesSha256"), BaseSha256);
  Root->TryGetNumberField(TEXT("baseRevision"), BaseRevision);
  const TArray<TSharedPtr<FJsonValue>>* BoardValues = nullptr;
  if (!Root->TryGetArrayField(TEXT("boards"), BoardValues) || !BoardValues) {
    OutErrors.Add(TEXT("overrides: boards must be an array"));
    return false;
  }
  for (int32 B = 0; B < BoardValues->Num(); ++B) {
    const TSharedPtr<FJsonObject> BO = (*BoardValues)[B].IsValid() ? (*BoardValues)[B]->AsObject() : nullptr;
    if (!BO.IsValid()) {
      OutErrors.Add(FString::Printf(TEXT("overrides: boards[%d] is not an object (skipped)"), B));
      continue;
    }
    FBoard Board;
    BO->TryGetStringField(TEXT("board"), Board.Board);
    BO->TryGetStringField(TEXT("profile"), Board.Profile);
    const TSharedPtr<FJsonObject>* Anchors = nullptr;
    if (BO->TryGetObjectField(TEXT("anchors"), Anchors) && Anchors && Anchors->IsValid()) {
      for (const TPair<FString, TSharedPtr<FJsonValue>>& A : (*Anchors)->Values) {
        FString V;
        if (A.Value.IsValid() && A.Value->TryGetString(V)) Board.Anchors.Add({A.Key, V});
      }
    }
    const TArray<TSharedPtr<FJsonValue>>* EntryValues = nullptr;
    if (BO->TryGetArrayField(TEXT("entries"), EntryValues) && EntryValues) {
      for (int32 I = 0; I < EntryValues->Num(); ++I) {
        const TSharedPtr<FJsonObject> EO = (*EntryValues)[I].IsValid() ? (*EntryValues)[I]->AsObject() : nullptr;
        FEntry E;
        if (!EO.IsValid() || !EO->TryGetStringField(TEXT("pointer"), E.Pointer) || !EO->HasField(TEXT("value"))) {
          OutErrors.Add(FString::Printf(TEXT("overrides: %s entries[%d] needs pointer + value (skipped)"), *Board.Board, I));
          continue;
        }
        E.Value = EO->TryGetField(TEXT("value"));
        E.Was = EO->TryGetField(TEXT("was"));
        if (E.Was.IsValid() && E.Was->Type == EJson::Null) E.Was.Reset();
        Board.Entries.Add(E);
      }
    }
    if (Board.Board.IsEmpty()) {
      OutErrors.Add(FString::Printf(TEXT("overrides: boards[%d] has no board id (skipped)"), B));
      continue;
    }
    Boards.Add(MoveTemp(Board));
  }
  return true;
}

bool FS08TunerOverridesFile::LoadFile(const FString& Path, TArray<FString>& OutErrors) {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *Path)) {
    OutErrors.Add(FString::Printf(TEXT("overrides: cannot read %s"), *Path));
    return false;
  }
  return Parse(Text, OutErrors);
}

FString FS08TunerOverridesFile::ToJson() const {
  // hand-written: one entry per line (the fold tool and git diffs read it), numbers as their saved text
  using S08JsonPointer::ToText;
  TArray<FString> L;
  L.Add(TEXT("{"));
  L.Add(FString::Printf(TEXT(" \"schema\": %s,"), *TunerQuote(S08ArtTunerSpec::OverridesSchema)));
  L.Add(FString::Printf(TEXT(" \"savedAt\": %s,"), *TunerQuote(SavedAt)));
  L.Add(FString::Printf(TEXT(" \"baseProfilesSha256\": %s,"), *TunerQuote(BaseSha256)));
  L.Add(FString::Printf(TEXT(" \"baseRevision\": %d,"), BaseRevision));
  L.Add(TEXT(" \"boards\": ["));
  for (int32 B = 0; B < Boards.Num(); ++B) {
    const FBoard& Board = Boards[B];
    L.Add(TEXT("  {"));
    L.Add(FString::Printf(TEXT("   \"board\": %s,"), *TunerQuote(Board.Board)));
    L.Add(FString::Printf(TEXT("   \"profile\": %s,"), *TunerQuote(Board.Profile)));
    TArray<FString> Anchors;
    for (const TPair<FString, FString>& A : Board.Anchors) Anchors.Add(TunerQuote(A.Key) + TEXT(": ") + TunerQuote(A.Value));
    L.Add(FString::Printf(TEXT("   \"anchors\": {%s},"), *FString::Join(Anchors, TEXT(", "))));
    L.Add(TEXT("   \"entries\": ["));
    for (int32 I = 0; I < Board.Entries.Num(); ++I) {
      const FEntry& E = Board.Entries[I];
      L.Add(FString::Printf(TEXT("    {\"pointer\": %s, \"value\": %s, \"was\": %s}%s"), *TunerQuote(E.Pointer), *ToText(E.Value),
                            *ToText(E.Was), I + 1 < Board.Entries.Num() ? TEXT(",") : TEXT("")));
    }
    L.Add(TEXT("   ]"));
    L.Add(FString::Printf(TEXT("  }%s"), B + 1 < Boards.Num() ? TEXT(",") : TEXT("")));
  }
  L.Add(TEXT(" ]"));
  L.Add(TEXT("}"));
  return FString::Join(L, TEXT("\n")) + TEXT("\n");
}

FS08TunerOverridesFile::FBoard* FS08TunerOverridesFile::FindBoard(const FString& Board) {
  return Boards.FindByPredicate([&](const FBoard& B) { return B.Board == Board; });
}

void FS08TunerOverridesFile::PutBoard(const FBoard& Board) {
  if (FBoard* Existing = FindBoard(Board.Board)) {
    *Existing = Board;
  } else {
    Boards.Add(Board);
  }
}

// ---- values ----------------------------------------------------------------------------------------------------------

namespace S08ArtTuner {
FString FormatNumber(double Value, int32 Decimals) {
  FString S = FString::Printf(TEXT("%.*f"), FMath::Clamp(Decimals, 0, 9), Value);
  if (S.Contains(TEXT("."))) {
    while (S.EndsWith(TEXT("0"))) S.LeftChopInline(1);
    if (S.EndsWith(TEXT("."))) S.LeftChopInline(1);
  }
  if (S == TEXT("-0")) S = TEXT("0");
  return S;
}

bool NormalizeHex(const FString& In, FString& Out) {
  FString H = In.TrimStartAndEnd();
  if (H.StartsWith(TEXT("#"))) H.RightChopInline(1);
  if (H.Len() != 6) return false;
  for (const TCHAR C : H) {
    if (!FChar::IsHexDigit(C)) return false;
  }
  Out = TEXT("#") + H.ToUpper();
  return true;
}

namespace {
bool CheckBounds(const FS08TunerParam& P, double V, FString& OutError) {
  if (P.bHasMin && P.bMinHard && V < P.Min - 1e-9) {
    OutError = FString::Printf(TEXT("%s: %g is below %g"), *P.Label, V, P.Min);
    return false;
  }
  if (P.bHasMax && P.bMaxHard && V > P.Max + 1e-9) {
    OutError = FString::Printf(TEXT("%s: %g is above %g"), *P.Label, V, P.Max);
    return false;
  }
  return true;
}

TSharedPtr<FJsonValue> NumberValue(double V, int32 Decimals) {
  return MakeShared<FJsonValueNumberString>(FormatNumber(V, Decimals));
}
}  // namespace

bool ValueWrites(const FS08TunerParam& P, const TSharedPtr<FJsonValue>& Value,
                 TArray<TPair<FString, TSharedPtr<FJsonValue>>>& OutWrites, FString& OutError) {
  OutWrites.Reset();
  if (!Value.IsValid()) {
    OutError = TEXT("no value");
    return false;
  }
  switch (P.Type) {
    case ES08TunerType::Number: {
      double V = 0.0;
      if (Value->Type != EJson::Number || !Value->TryGetNumber(V) || !FMath::IsFinite(V)) {
        OutError = FString::Printf(TEXT("%s: a number expected"), *P.Label);
        return false;
      }
      if (!CheckBounds(P, V, OutError)) return false;
      OutWrites.Add({P.Pointer, NumberValue(P.Snap(V), P.Decimals())});
      return true;
    }
    case ES08TunerType::Bool:
      if (Value->Type != EJson::Boolean) {
        OutError = FString::Printf(TEXT("%s: true or false expected"), *P.Label);
        return false;
      }
      OutWrites.Add({P.Pointer, MakeShared<FJsonValueBoolean>(Value->AsBool())});
      return true;
    case ES08TunerType::ColorSrgb: {
      FString Hex;
      if (Value->Type != EJson::String || !NormalizeHex(Value->AsString(), Hex)) {
        OutError = FString::Printf(TEXT("%s: #RRGGBB expected"), *P.Label);
        return false;
      }
      OutWrites.Add({P.Pointer, MakeShared<FJsonValueString>(Hex)});
      return true;
    }
    case ES08TunerType::ColorLinear: {
      if (Value->Type != EJson::Array || Value->AsArray().Num() != 3) {
        OutError = FString::Printf(TEXT("%s: [r, g, b] expected"), *P.Label);
        return false;
      }
      TArray<TSharedPtr<FJsonValue>> Channels;
      for (const TSharedPtr<FJsonValue>& C : Value->AsArray()) {
        double V = 0.0;
        if (!C.IsValid() || C->Type != EJson::Number || !C->TryGetNumber(V) || !FMath::IsFinite(V)) {
          OutError = FString::Printf(TEXT("%s: three numbers expected"), *P.Label);
          return false;
        }
        if (!CheckBounds(P, V, OutError)) return false;
        Channels.Add(NumberValue(P.Snap(V), P.Decimals()));
      }
      OutWrites.Add({P.Pointer, MakeShared<FJsonValueArray>(Channels)});
      return true;
    }
    case ES08TunerType::Ev100: {
      double V = 0.0;
      if (Value->Type != EJson::Number || !Value->TryGetNumber(V) || !FMath::IsFinite(V) || V < -10.0 || V > 20.0) {
        OutError = FString::Printf(TEXT("%s: EV100 -10..20 expected"), *P.Label);
        return false;
      }
      const double Ev = P.Snap(V);
      // the parser wants min == max brightness (a fixed histogram exposure); ev100 is informational: 2^ev100 == brightness
      const FString Brightness = FormatNumber(FMath::Pow(2.0, Ev), 5);
      OutWrites.Add({P.Pointer + TEXT("/ev100"), NumberValue(Ev, P.Decimals())});
      OutWrites.Add({P.Pointer + TEXT("/minBrightness"), MakeShared<FJsonValueNumberString>(Brightness)});
      OutWrites.Add({P.Pointer + TEXT("/maxBrightness"), MakeShared<FJsonValueNumberString>(Brightness)});
      return true;
    }
  }
  OutError = TEXT("unknown row type");
  return false;
}

int32 ReanchorBoard(FS08TunerOverridesFile::FBoard& Board, int32 CurrentIndex) {
  if (CurrentIndex == INDEX_NONE || Board.Board.IsEmpty()) return 0;
  const FString Prefix = TEXT("/boards/");
  const FString Suffix = TEXT("/id");
  TSet<FString> OldIndices;
  for (const TPair<FString, FString>& A : Board.Anchors) {
    if (A.Value != Board.Board || !A.Key.StartsWith(Prefix, ESearchCase::CaseSensitive) ||
        !A.Key.EndsWith(Suffix, ESearchCase::CaseSensitive)) {
      continue;
    }
    const FString Index = A.Key.Mid(Prefix.Len(), A.Key.Len() - Prefix.Len() - Suffix.Len());
    bool bDigits = !Index.IsEmpty();
    for (const TCHAR C : Index) bDigits = bDigits && FChar::IsDigit(C);
    if (bDigits && FCString::Atoi(*Index) != CurrentIndex) OldIndices.Add(Index);
  }
  if (OldIndices.IsEmpty()) return 0;
  const FString NewPrefix = FString::Printf(TEXT("/boards/%d/"), CurrentIndex);
  auto Move = [&](FString& Pointer) {
    for (const FString& Old : OldIndices) {
      const FString OldPrefix = Prefix + Old + TEXT("/");
      if (Pointer.StartsWith(OldPrefix, ESearchCase::CaseSensitive)) {
        Pointer = NewPrefix + Pointer.Mid(OldPrefix.Len());
        return 1;
      }
    }
    return 0;
  };
  int32 Moved = 0;
  for (TPair<FString, FString>& A : Board.Anchors) Moved += Move(A.Key);
  for (FS08TunerOverridesFile::FEntry& E : Board.Entries) Moved += Move(E.Pointer);
  return Moved;
}
}  // namespace S08ArtTuner

const FS08TunerParam* FS08ArtTunerSession::FindParam(const FString& PointerOrId) const {
  for (const FS08TunerGroup& G : Groups) {
    for (const FS08TunerParam& P : G.Params) {
      if (P.Id == PointerOrId || P.Pointer.Equals(PointerOrId, ESearchCase::CaseSensitive)) return &P;
      if (P.Type == ES08TunerType::Ev100 && PointerOrId.Equals(P.Pointer + TEXT("/ev100"), ESearchCase::CaseSensitive)) return &P;
    }
  }
  return nullptr;
}

const FS08TunerGroup* FS08ArtTunerSession::FindGroup(const FString& Id) const {
  return Groups.FindByPredicate([&](const FS08TunerGroup& G) { return G.Id == Id; });
}

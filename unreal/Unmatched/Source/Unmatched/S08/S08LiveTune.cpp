#include "S08LiveTune.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "HAL/FileManager.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "S08Contracts.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

const TCHAR* S08LiveActionName(ES08LiveAction Action) {
  switch (Action) {
    case ES08LiveAction::Reload: return TEXT("reload");
    case ES08LiveAction::Shot: return TEXT("shot");
    case ES08LiveAction::State: return TEXT("state");
    case ES08LiveAction::Quit: return TEXT("quit");
    case ES08LiveAction::Tune: return TEXT("tune");
    case ES08LiveAction::TunerState: return TEXT("tunerState");
    case ES08LiveAction::TunerSave: return TEXT("tunerSave");
    case ES08LiveAction::TunerReset: return TEXT("tunerReset");
    case ES08LiveAction::TunerPanel: return TEXT("tunerPanel");
    case ES08LiveAction::ArtView: return TEXT("artView");
    default: return TEXT("none");
  }
}

namespace {
bool LiveNumber(const TSharedPtr<FJsonObject>& Root, const TCHAR* Field, float Min, float Max, float& Out,
                TArray<FString>& Errors) {
  if (!Root->HasField(Field)) return true;
  double V = 0.0;
  const TSharedPtr<FJsonValue> Value = Root->TryGetField(Field);
  if (!Value.IsValid() || Value->Type != EJson::Number || !Value->TryGetNumber(V) || V < Min || V > Max) {
    Errors.Add(FString::Printf(TEXT("'%s' must be a number in %g..%g"), Field, Min, Max));
    return false;
  }
  Out = static_cast<float>(V);
  return true;
}

bool LiveInt(const TSharedPtr<FJsonObject>& Root, const TCHAR* Field, int32 Min, int32 Max, int32& Out,
             TArray<FString>& Errors) {
  float V = 0.0f;
  if (!Root->HasField(Field)) return true;
  if (!LiveNumber(Root, Field, static_cast<float>(Min), static_cast<float>(Max), V, Errors)) return false;
  if (FMath::RoundToInt(V) != V) {
    Errors.Add(FString::Printf(TEXT("'%s' must be an integer"), Field));
    return false;
  }
  Out = FMath::RoundToInt(V);
  return true;
}

bool LiveString(const TSharedPtr<FJsonObject>& Root, const TCHAR* Field, FString& Out, TArray<FString>& Errors) {
  if (!Root->HasField(Field)) return true;
  const TSharedPtr<FJsonValue> Value = Root->TryGetField(Field);
  if (!Value.IsValid() || Value->Type != EJson::String) {
    Errors.Add(FString::Printf(TEXT("'%s' must be a string"), Field));
    return false;
  }
  Out = Value->AsString();
  return true;
}

bool LiveBool(const TSharedPtr<FJsonObject>& Root, const TCHAR* Field, bool& Out, TArray<FString>& Errors) {
  if (!Root->HasField(Field)) return true;
  const TSharedPtr<FJsonValue> Value = Root->TryGetField(Field);
  // strictly a JSON boolean (FJsonValueString::TryGetBool takes any string, the P9b litPedestal trap)
  if (!Value.IsValid() || Value->Type != EJson::Boolean) {
    Errors.Add(FString::Printf(TEXT("'%s' must be true or false"), Field));
    return false;
  }
  Out = Value->AsBool();
  return true;
}

FString LiveNormalizeDir(const FString& In) {
  FString Dir = In.TrimStartAndEnd().TrimQuotes();
  FPaths::NormalizeDirectoryName(Dir);
  if (!Dir.IsEmpty() && FPaths::IsRelative(Dir)) Dir = FPaths::ConvertRelativePathToFull(Dir);
  return Dir;
}
}  // namespace

bool FS08LiveCommand::Parse(const FString& Text, int32 FileSeq, FS08LiveCommand& Out, TArray<FString>& OutErrors) {
  Out = FS08LiveCommand();
  Out.Seq = FileSeq;
  const int32 Before = OutErrors.Num();
  TSharedPtr<FJsonObject> Root;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(Text, Root, Problem) || !Root.IsValid()) {
    OutErrors.Add(TEXT("invalid JSON: ") + Problem);
    return false;
  }
  int32 Seq = FileSeq;
  LiveInt(Root, TEXT("seq"), 1, MAX_int32, Seq, OutErrors);
  if (Seq != FileSeq) OutErrors.Add(FString::Printf(TEXT("seq %d != the file's %d"), Seq, FileSeq));
  FString Action;
  if (!Root->TryGetStringField(TEXT("action"), Action)) {
    OutErrors.Add(FString::Printf(TEXT("'action' missing (%s)"), S08LiveTuneSpec::ActionList));
    return false;
  }
  for (ES08LiveAction A : {ES08LiveAction::Reload, ES08LiveAction::Shot, ES08LiveAction::State, ES08LiveAction::Quit,
                           ES08LiveAction::Tune, ES08LiveAction::TunerState, ES08LiveAction::TunerSave,
                           ES08LiveAction::TunerReset, ES08LiveAction::TunerPanel, ES08LiveAction::ArtView}) {
    if (Action == S08LiveActionName(A)) Out.Action = A;
  }
  if (Out.Action == ES08LiveAction::None) {
    OutErrors.Add(FString::Printf(TEXT("unknown action '%s' (%s)"), *Action, S08LiveTuneSpec::ActionList));
    return false;
  }
  if (Out.Action == ES08LiveAction::Tune) {
    auto AddEntry = [&](const TSharedPtr<FJsonObject>& E, const FString& Where) {
      FString Pointer;
      const TSharedPtr<FJsonValue> Value = E->TryGetField(TEXT("value"));
      if (!E->TryGetStringField(TEXT("pointer"), Pointer) || Pointer.IsEmpty() || !Value.IsValid()) {
        OutErrors.Add(FString::Printf(TEXT("tune: %s needs 'pointer' (a panel row pointer or id) and 'value'"), *Where));
        return;
      }
      Out.TuneEntries.Add({Pointer, Value});
    };
    const TArray<TSharedPtr<FJsonValue>>* Entries = nullptr;
    if (Root->TryGetArrayField(TEXT("entries"), Entries) && Entries) {
      for (int32 I = 0; I < Entries->Num(); ++I) {
        const TSharedPtr<FJsonValue>& V = (*Entries)[I];
        const TSharedPtr<FJsonObject> E = V.IsValid() && V->Type == EJson::Object ? V->AsObject() : nullptr;
        if (!E.IsValid()) {
          OutErrors.Add(FString::Printf(TEXT("tune: entries[%d] must be an object"), I));
          continue;
        }
        AddEntry(E, FString::Printf(TEXT("entries[%d]"), I));
      }
    } else {
      AddEntry(Root, TEXT("the command"));
    }
    if (Out.TuneEntries.IsEmpty() && OutErrors.Num() == Before) OutErrors.Add(TEXT("tune: no entries"));
  }
  if (Out.Action == ES08LiveAction::TunerSave) {
    LiveString(Root, TEXT("file"), Out.TunerFile, OutErrors);
    Out.TunerFile = Out.TunerFile.TrimStartAndEnd();
    if (!Out.TunerFile.IsEmpty() && FPaths::IsRelative(Out.TunerFile)) {
      OutErrors.Add(TEXT("tunerSave: 'file' must be an absolute path"));
    }
  }
  if (Out.Action == ES08LiveAction::TunerReset) LiveString(Root, TEXT("group"), Out.TunerGroup, OutErrors);
  if (Out.Action == ES08LiveAction::TunerPanel) {
    if (!Root->HasField(TEXT("open"))) OutErrors.Add(TEXT("tunerPanel: 'open' (true | false) missing"));
    LiveBool(Root, TEXT("open"), Out.bPanelOpen, OutErrors);
  }
  if (Out.Action == ES08LiveAction::ArtView) {
    LiveString(Root, TEXT("view"), Out.ArtViewView, OutErrors);
    if (!Out.ArtViewView.IsEmpty()) {
      TArray<FString> Views;
      S08LiveTune::ParseViews(Out.ArtViewView, Views, OutErrors);
      if (Views.Num() != 1) OutErrors.Add(TEXT("artView: 'view' must be one view (K1, K2x1.6, ...)"));
    }
    LiveNumber(Root, TEXT("yaw"), -720.0f, 720.0f, Out.ArtViewYaw, OutErrors);
    LiveNumber(Root, TEXT("pitch"), 0.0f, 90.0f, Out.ArtViewPitch, OutErrors);
    if (Root->HasField(TEXT("pan"))) {
      const TArray<TSharedPtr<FJsonValue>>* Pan = nullptr;
      double X = 0.0, Y = 0.0;
      if (!Root->TryGetArrayField(TEXT("pan"), Pan) || !Pan || Pan->Num() != 2 || !(*Pan)[0].IsValid() ||
          !(*Pan)[1].IsValid() || !(*Pan)[0]->TryGetNumber(X) || !(*Pan)[1]->TryGetNumber(Y)) {
        OutErrors.Add(TEXT("artView: 'pan' must be [x, y] (uu)"));
      } else {
        Out.bArtViewPan = true;
        Out.ArtViewPan = FVector2D(X, Y);
      }
    }
    if (Root->HasField(TEXT("select"))) Out.bArtViewSelect = LiveString(Root, TEXT("select"), Out.ArtViewSelect, OutErrors);
    const TCHAR* Names[] = {TEXT("heroLight"), TEXT("pause"), TEXT("help")};
    int32* Slots[] = {&Out.ArtViewHeroLight, &Out.ArtViewPause, &Out.ArtViewHelp};
    for (int32 I = 0; I < 3; ++I) {
      bool B = false;
      if (Root->HasField(Names[I]) && LiveBool(Root, Names[I], B, OutErrors)) *Slots[I] = B ? 1 : 0;
    }
  }
  if (Out.Action == ES08LiveAction::Reload) {
    LiveString(Root, TEXT("profiles"), Out.ProfilesPath, OutErrors);
    LiveString(Root, TEXT("envDir"), Out.EnvDir, OutErrors);
    Out.ProfilesPath = Out.ProfilesPath.TrimStartAndEnd();
    if (!Out.ProfilesPath.IsEmpty() && FPaths::IsRelative(Out.ProfilesPath)) {
      OutErrors.Add(TEXT("'profiles' must be an absolute path"));
    }
    if (!Out.EnvDir.IsEmpty()) {
      if (FPaths::IsRelative(Out.EnvDir.TrimStartAndEnd())) OutErrors.Add(TEXT("'envDir' must be an absolute path"));
      Out.EnvDir = LiveNormalizeDir(Out.EnvDir);
    }
  }
  if (Out.Action == ES08LiveAction::Shot) {
    FString Views;
    if (!Root->TryGetStringField(TEXT("views"), Views)) {
      OutErrors.Add(TEXT("shot: 'views' missing (e.g. \"K1+K2x1.6\")"));
    } else {
      S08LiveTune::ParseViews(Views, Out.Views, OutErrors);
    }
    if (!Root->TryGetStringField(TEXT("out"), Out.OutDir) || Out.OutDir.TrimStartAndEnd().IsEmpty()) {
      OutErrors.Add(TEXT("shot: 'out' missing (absolute directory)"));
    } else if (FPaths::IsRelative(Out.OutDir.TrimStartAndEnd())) {
      OutErrors.Add(TEXT("shot: 'out' must be an absolute directory"));
    } else {
      Out.OutDir = LiveNormalizeDir(Out.OutDir);
    }
    LiveString(Root, TEXT("tag"), Out.Tag, OutErrors);
    LiveNumber(Root, TEXT("warmup"), 0.0f, 600.0f, Out.Warmup, OutErrors);
    LiveNumber(Root, TEXT("settle"), 0.0f, 120.0f, Out.Settle, OutErrors);
    LiveNumber(Root, TEXT("measure"), 0.0f, 120.0f, Out.Measure, OutErrors);
    LiveNumber(Root, TEXT("post"), 0.0f, 60.0f, Out.Post, OutErrors);
    LiveInt(Root, TEXT("warmupFrames"), 0, 100000, Out.WarmupFrames, OutErrors);
    LiveInt(Root, TEXT("settleFrames"), 0, 100000, Out.SettleFrames, OutErrors);
    LiveBool(Root, TEXT("live"), Out.bLive, OutErrors);
    LiveBool(Root, TEXT("append"), Out.bAppendTrace, OutErrors);
    LiveBool(Root, TEXT("fresh"), Out.bFresh, OutErrors);
    FString Clock = TEXT("bench");
    LiveString(Root, TEXT("clock"), Clock, OutErrors);
    if (Clock != TEXT("bench") && Clock != TEXT("free")) {
      OutErrors.Add(FString::Printf(TEXT("shot: 'clock' '%s' is not bench | free"), *Clock));
    }
    Out.bBenchClock = Clock == TEXT("bench") && !Out.bLive;
    const TSharedPtr<FJsonObject>* Bench = nullptr;
    if (Root->HasField(TEXT("bench"))) {
      if (!Root->TryGetObjectField(TEXT("bench"), Bench) || !Bench || !Bench->IsValid()) {
        OutErrors.Add(TEXT("shot: 'bench' must be an object {warmup, settle, measure}"));
      } else {
        LiveNumber(*Bench, TEXT("warmup"), 0.0f, 600.0f, Out.BenchWarmup, OutErrors);
        LiveNumber(*Bench, TEXT("settle"), 0.0f, 120.0f, Out.BenchSettle, OutErrors);
        LiveNumber(*Bench, TEXT("measure"), 0.0f, 120.0f, Out.BenchMeasure, OutErrors);
        LiveNumber(*Bench, TEXT("gap"), -1.0f, 5.0f, Out.BenchGap, OutErrors);
        LiveNumber(*Bench, TEXT("gapLater"), -1.0f, 5.0f, Out.BenchGapLater, OutErrors);
      }
    }
  }
  return OutErrors.Num() == Before;
}

FString FS08LiveResult::ToJson() const {
  TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
  Root->SetNumberField(TEXT("seq"), Seq);
  Root->SetStringField(TEXT("action"), Action);
  Root->SetBoolField(TEXT("ok"), bOk);
  Root->SetNumberField(TEXT("ms"), FMath::RoundToDouble(Ms * 10.0) / 10.0);
  auto Strings = [](const TArray<FString>& In) {
    TArray<TSharedPtr<FJsonValue>> Out;
    for (const FString& S : In) Out.Add(MakeShared<FJsonValueString>(S));
    return Out;
  };
  Root->SetArrayField(TEXT("errors"), Strings(Errors));
  Root->SetArrayField(TEXT("warnings"), Strings(Warnings));
  Root->SetArrayField(TEXT("files"), Strings(Files));
  if (Extra.IsValid()) {
    for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Extra->Values) {
      if (!Root->HasField(Pair.Key)) Root->SetField(Pair.Key, Pair.Value);
    }
  }
  FString Text;
  const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Text);
  FJsonSerializer::Serialize(Root, Writer);
  return Text;
}

namespace S08LiveTune {

FString DirFromCommandLine() {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), S08LiveTuneSpec::DirParam, Dir)) return FString();
  return LiveNormalizeDir(Dir);
}

bool Enabled() { return !DirFromCommandLine().IsEmpty(); }

FString CommandFile(const FString& Dir, int32 Seq) {
  return FPaths::Combine(Dir, FString::Printf(TEXT("cmd-%d.json"), Seq));
}

FString DoneFile(const FString& Dir, int32 Seq) {
  return FPaths::Combine(Dir, FString::Printf(TEXT("done-%d.json"), Seq));
}

int32 SeqOfFileName(const FString& FileName, const TCHAR* Prefix) {
  const FString Name = FPaths::GetCleanFilename(FileName);
  if (!Name.StartsWith(Prefix) || !Name.EndsWith(TEXT(".json"))) return INDEX_NONE;
  const FString Digits = Name.Mid(FCString::Strlen(Prefix), Name.Len() - FCString::Strlen(Prefix) - 5);
  if (Digits.IsEmpty() || Digits.Len() > 9) return INDEX_NONE;
  for (const TCHAR C : Digits) {
    if (!FChar::IsDigit(C)) return INDEX_NONE;
  }
  return FCString::Atoi(*Digits);
}

bool NextCommand(const FString& Dir, int32 LastSeq, int32& OutSeq, FString& OutPath) {
  TArray<FString> Names;
  IFileManager::Get().FindFiles(Names, *FPaths::Combine(Dir, TEXT("cmd-*.json")), true, false);
  int32 Best = INDEX_NONE;
  for (const FString& Name : Names) {
    const int32 Seq = SeqOfFileName(Name, TEXT("cmd-"));
    if (Seq > LastSeq && (Best == INDEX_NONE || Seq < Best)) Best = Seq;
  }
  if (Best == INDEX_NONE) return false;
  OutSeq = Best;
  OutPath = CommandFile(Dir, Best);
  return true;
}

FString ShotFileName(const FString& View) {
  return FString::Printf(TEXT("bench-%s-1920x1080.png"), *View.Replace(TEXT("."), TEXT("p")));
}

bool WriteFileAtomic(const FString& Path, const FString& Text) {
  const FString Tmp = Path + TEXT(".tmp");
  IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path), true);
  if (!FFileHelper::SaveStringToFile(Text, *Tmp, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM)) return false;
  return IFileManager::Get().Move(*Path, *Tmp, /*Replace=*/true, /*EvenIfReadOnly=*/true);
}

bool ParseViews(const FString& Text, TArray<FString>& OutViews, TArray<FString>& OutErrors) {
  OutViews.Reset();
  Text.ParseIntoArray(OutViews, TEXT("+"), true);
  bool bOk = OutViews.Num() > 0 && OutViews.Num() <= 16;
  if (!bOk) OutErrors.Add(TEXT("views: 1..16 names joined by '+' (K1, K2x1.6, K1x0.65, Fitx1.45, ...)"));
  for (const FString& View : OutViews) {
    bool bName = View.Len() <= 16 && (View.StartsWith(TEXT("K1")) || View.StartsWith(TEXT("K2")) ||
                                      View.StartsWith(TEXT("Fitx")));
    for (const TCHAR C : View) bName = bName && (FChar::IsAlnum(C) || C == TEXT('.'));
    if (!bName) {
      OutErrors.Add(FString::Printf(TEXT("view '%s' is not a -Bench view (K1, K2x<zoom>, K1x<zoom>, Fitx<mul>)"), *View));
      bOk = false;
    }
  }
  return bOk;
}

}  // namespace S08LiveTune

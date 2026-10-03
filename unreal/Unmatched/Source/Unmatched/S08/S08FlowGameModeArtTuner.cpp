// Art Tuner M2: the game-mode side of -ArtTuner (S08ArtTuner.h). One code path for the panel's sliders and the live-tune
// "tune" action: ArtTunerSetValue (registry row -> validated writes -> the model -> FS08BoardArtData::ParseJson) ->
// ArtTunerApplyPending (AS08BoardActor::ApplyTunedArtData on the components, a rebuild only for the rebuild scope),
// ArtTunerSave (S08ArtTuner.overrides.json). Nothing here runs without the flag.
#include "S08FlowGameMode.h"

#include "S08ArtTuner.h"
#include "S08ArtTunerPanel.h"
#include "S08ArtView.h"
#include "S08BoardActor.h"
#include "S08BoardArt.h"
#include "S08LiveTune.h"
#include "S08TraceLog.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/PlayerController.h"
#include "Widgets/Layout/SBox.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "InputCoreTypes.h"
#include "Misc/DateTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"

namespace {
FString S08TunerSha256(const FString& Path) {
  TArray<uint8> Bytes;
  if (!FFileHelper::LoadFileToArray(Bytes, *Path)) return FString();
  FSHA256Signature Signature;
  if (!FPlatformMisc::GetSHA256Signature(Bytes.GetData(), Bytes.Num(), Signature)) return FString();
  return Signature.ToString().ToLower();
}
}  // namespace

bool AS08FlowGameMode::ArtTunerEnabled() const { return bArtTunerFlag; }

bool AS08FlowGameMode::ArtTunerBegin() {
  if (!BoardActor || !BoardActor->IsArtActive()) return false;
  ArtTuner = MakeShared<FS08ArtTunerSession>();
  FS08ArtTunerSession& S = *ArtTuner;
  S.File = S08ArtTunerSpec::FileFromCommandLine();
  bool bOverride = false;
  S.ProfilesPath = !ArtTunerProfilesPath.IsEmpty() ? ArtTunerProfilesPath : FS08BoardArtData::ResolvePath(bOverride);
  S.ProfilesSource = BoardActor->GetAppliedRender().ProfilesSource;
  S.BoardId = BoardActor->GetArtProfileId();
  S.LightId = BoardActor->GetAppliedRender().ProfileId;
  TArray<FString> Errors;
  if (!S.Registry.LoadFile(S08ArtTunerSpec::DefaultParamsPath(), Errors)) {
    for (const FString& E : Errors) S.Warnings.Add(TEXT("реестр: ") + E);
  }
  ArtTunerRebase(FString(), S.Warnings);
  // the saved values of this board (-ArtTunerFile): the same path as a slider move, so a broken entry is skipped with a
  // warning and the rest still applies
  int32 Loaded = 0, Skipped = 0;
  if (!S.File.IsEmpty() && FPaths::FileExists(S.File)) {
    FS08TunerOverridesFile File;
    TArray<FString> FileErrors;
    File.LoadFile(S.File, FileErrors);
    for (const FString& E : FileErrors) S.Warnings.Add(TEXT("файл: ") + E);
    if (const FS08TunerOverridesFile::FBoard* Board = File.FindBoard(S.BoardId)) {
      bool bAnchors = true;
      for (const TPair<FString, FString>& A : Board->Anchors) {
        const TSharedPtr<FJsonValue> V = S.Model.BaseValue(A.Key);
        FString Got;
        if (!V.IsValid() || !V->TryGetString(Got) || Got != A.Value) {
          bAnchors = false;
          S.Warnings.Add(FString::Printf(TEXT("файл: якорь %s = %s, а в профиле %s - записи доски пропущены"), *A.Key, *A.Value,
                                         V.IsValid() ? *S08JsonPointer::ToText(V) : TEXT("нет")));
        }
      }
      for (const FS08TunerOverridesFile::FEntry& E : bAnchors ? Board->Entries : TArray<FS08TunerOverridesFile::FEntry>()) {
        // the ev100 row writes its min / max brightness itself
        if (E.Pointer.EndsWith(TEXT("/minBrightness")) || E.Pointer.EndsWith(TEXT("/maxBrightness"))) {
          const FS08TunerParam* P = S.FindParam(E.Pointer.Left(E.Pointer.Find(TEXT("/"), ESearchCase::CaseSensitive,
                                                                                ESearchDir::FromEnd)));
          if (P && P->Type == ES08TunerType::Ev100) continue;
        }
        const TSharedPtr<FJsonValue> Base = S.Model.BaseValue(E.Pointer);
        if (E.Was.IsValid() && Base.IsValid() && !S08JsonPointer::Equal(E.Was, Base)) {
          S.Warnings.Add(FString::Printf(TEXT("файл: %s - база изменилась (было %s, стало %s), значение %s применено"), *E.Pointer,
                                         *S08JsonPointer::ToText(E.Was), *S08JsonPointer::ToText(Base),
                                         *S08JsonPointer::ToText(E.Value)));
        }
        FString Error;
        if (ArtTunerSetValue(E.Pointer, E.Value, Error)) {
          ++Loaded;
        } else {
          ++Skipped;
          S.Warnings.Add(TEXT("файл: пропущено ") + E.Pointer + TEXT(" - ") + Error);
        }
      }
    }
  }
  ArtTunerApplyPending(true);
  int32 Rows = 0;
  for (const FS08TunerGroup& G : S.Groups) Rows += G.Params.Num();
  FS08Trace::Write(FString::Printf(
      TEXT("ARTTUNER ready board=%s light=%s index=%d groups=%d rows=%d file=%s loaded=%d skipped=%d warnings=%d profiles=%s"),
      *S.BoardId, *S.LightId, S.BoardIndex, S.Groups.Num(), Rows, S.File.IsEmpty() ? TEXT("-") : *S.File, Loaded, Skipped,
      S.Warnings.Num(), *S.ProfilesPath));
  for (int32 I = 0; I < S.Warnings.Num() && I < 12; ++I) FS08Trace::Write(TEXT("ARTTUNER warning: ") + S.Warnings[I]);
  return true;
}

bool AS08FlowGameMode::ArtTunerRebase(const FString& ProfilesPath, TArray<FString>& OutWarnings) {
  FS08ArtTunerSession& S = *ArtTuner;
  if (!ProfilesPath.IsEmpty()) {
    // a live-tune reload swapped the document: the tuner continues on the file it read
    S.ProfilesPath = ProfilesPath;
    S.ProfilesSource = BoardActor ? BoardActor->GetAppliedRender().ProfilesSource : S.ProfilesSource;
  }
  FString Text;
  TArray<FString> Errors;
  if (!FFileHelper::LoadFileToString(Text, *S.ProfilesPath) ||
      !S.Model.SetBase(Text, BoardActor ? BoardActor->GetArtData().SourceSha256 : S08TunerSha256(S.ProfilesPath), Errors)) {
    OutWarnings.Add(FString::Printf(TEXT("профиль: не прочитан %s"), *S.ProfilesPath));
    return false;
  }
  S.BoardIndex = INDEX_NONE;
  const TSharedPtr<FJsonValue> Boards = S.Model.BaseValue(TEXT("/boards"));
  if (Boards.IsValid() && Boards->Type == EJson::Array) {
    for (int32 I = 0; I < Boards->AsArray().Num(); ++I) {
      const TSharedPtr<FJsonValue> Id = S.Model.BaseValue(FString::Printf(TEXT("/boards/%d/id"), I));
      FString V;
      if (Id.IsValid() && Id->TryGetString(V) && V == S.BoardId) S.BoardIndex = I;
    }
  }
  if (S.BoardIndex == INDEX_NONE) OutWarnings.Add(FString::Printf(TEXT("профиль: доски %s нет в документе"), *S.BoardId));
  S.Groups = S.Registry.Expand(S.Model.GetBase(), S.LightId, S.BoardIndex);
  // the values survive a rebase: rebuild the pending document on the new base (an entry the new base refuses is dropped)
  TArray<FS08TunerEntry> Keep = S.Model.GetEntries();
  S.Model.ResetAll();
  for (const FS08TunerEntry& E : Keep) {
    FString Error;
    const FS08TunerParam* P = S.FindParam(E.Pointer);
    if (!S.Model.SetValue(E.Pointer, E.Value, P && P->bCreate, Error)) OutWarnings.Add(TEXT("значение снято: ") + Error);
  }
  FS08BoardArtData Data;
  if (S.Model.Build(Data, Errors)) {
    S.PendingData = MoveTemp(Data);
    S.bPending = true;
    for (const FS08TunerGroup& G : S.Groups) S.PendingScopes |= static_cast<uint8>(G.Scope);
    S.PendingScopes &= ~static_cast<uint8>(ES08TunerScope::Rebuild);  // the document was just built
  }
  ++S.Version;
  return true;
}

void AS08FlowGameMode::ArtTunerEnd() {
  if (!ArtTuner.IsValid()) return;
  ArtTunerSetPanelOpen(false);
  if (ArtTuner->PanelRoot.IsValid() && GEngine && GEngine->GameViewport) {
    GEngine->GameViewport->RemoveViewportWidgetContent(ArtTuner->PanelRoot.ToSharedRef());
  }
  ArtTuner.Reset();
}

bool AS08FlowGameMode::ArtTunerSetValue(const FString& PointerOrId, const TSharedPtr<FJsonValue>& Value, FString& OutError) {
  if (!ArtTuner.IsValid()) {
    OutError = TEXT("тюнер не запущен (нет -ArtTuner или доска без арта)");
    return false;
  }
  FS08ArtTunerSession& S = *ArtTuner;
  const FS08TunerParam* P = S.FindParam(PointerOrId);
  if (!P) {
    OutError = FString::Printf(TEXT("%s - не строка тюнера на этой доске (Config/ArtTuner/S08ArtTunerParams.json)"), *PointerOrId);
    return false;
  }
  TArray<TPair<FString, TSharedPtr<FJsonValue>>> Writes;
  if (!S08ArtTuner::ValueWrites(*P, Value, Writes, OutError)) return false;
  // the previous state of every written pointer (a refused document puts it back)
  TArray<TPair<FString, TSharedPtr<FJsonValue>>> Previous;
  for (const TPair<FString, TSharedPtr<FJsonValue>>& W : Writes) {
    Previous.Add({W.Key, S.Model.IsChanged(W.Key) ? S.Model.Value(W.Key) : nullptr});
  }
  auto Revert = [&]() {
    for (const TPair<FString, TSharedPtr<FJsonValue>>& Prev : Previous) {
      FString Ignored;
      if (Prev.Value.IsValid()) S.Model.SetValue(Prev.Key, Prev.Value, true, Ignored);
      else S.Model.Reset(Prev.Key);
    }
  };
  for (const TPair<FString, TSharedPtr<FJsonValue>>& W : Writes) {
    // an absent optional key set to the value it means anyway: no entry (the file stays minimal)
    if (P->bHasDefault && !S.Model.BaseValue(W.Key).IsValid() && S08JsonPointer::Equal(W.Value, P->DefaultValue())) {
      S.Model.Reset(W.Key);
      continue;
    }
    if (!S.Model.SetValue(W.Key, W.Value, P->bCreate, OutError)) {
      Revert();
      return false;
    }
  }
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (!S.Model.Build(Data, Errors)) {
    Revert();
    OutError = Errors.IsEmpty() ? FString(TEXT("документ не прошёл проверку")) : Errors[0];
    S.LastError = OutError;
    ++S.Version;
    return false;
  }
  S.PendingData = MoveTemp(Data);
  S.bPending = true;
  S.PendingScopes |= static_cast<uint8>(P->Scope);
  S.LastError.Reset();
  ++S.Version;
  return true;
}

void AS08FlowGameMode::ArtTunerApplyPending(bool bForce) {
  if (!ArtTuner.IsValid() || !BoardActor) return;
  FS08ArtTunerSession& S = *ArtTuner;
  if (!S.bPending) return;
  const double Now = FPlatformTime::Seconds();
  const bool bRebuildScope = (S.PendingScopes & static_cast<uint8>(ES08TunerScope::Rebuild)) != 0;
  if (!bForce && (Now < S.NextApplyAt || (bRebuildScope && Now < S.NextRebuildAt))) return;
  const FString Source = S.Model.GetEntries().IsEmpty() ? S.ProfilesSource : FString(TEXT("tuner"));
  FString Note;
  const bool bRebuild = BoardActor->ApplyTunedArtData(S.PendingData, S.PendingScopes, Source, Note);
  if (bRebuild) {
    // the normal build path (as a live-tune reload), the camera and the selection stay
    SyncBoardFromApplied();
    ++S.Rebuilds;
    S.NextRebuildAt = Now + 1.0 / S08ArtTunerSpec::RebuildHz;
  }
  ++S.Applies;
  S.LastApplyMs = (FPlatformTime::Seconds() - Now) * 1000.0;
  S.LastApplyNote = Note;
  S.NextApplyAt = Now + 1.0 / S08ArtTunerSpec::ApplyHz;
  S.bPending = false;
  S.PendingScopes = 0;
  ++S.Version;
}

bool AS08FlowGameMode::ArtTunerSave(const FString& PathOverride, FString& OutPath, FString& OutError) {
  if (!ArtTuner.IsValid()) {
    OutError = TEXT("тюнер не запущен");
    return false;
  }
  FS08ArtTunerSession& S = *ArtTuner;
  OutPath = !PathOverride.IsEmpty() ? PathOverride : S.File;
  if (OutPath.IsEmpty()) {
    OutError = TEXT("файл не задан: запустите с -ArtTunerFile=<путь> (лаунчер Unmatched-ArtTuner.cmd делает это сам)");
    return false;
  }
  // the other boards of the file stay (one block per board); a corrupt file is kept aside as .bak, never lost
  FS08TunerOverridesFile File;
  if (FPaths::FileExists(OutPath)) {
    TArray<FString> Errors;
    if (!File.LoadFile(OutPath, Errors)) {
      IFileManager::Get().Copy(*(OutPath + TEXT(".bak")), *OutPath);
      File = FS08TunerOverridesFile();
      S.Warnings.Add(FString::Printf(TEXT("файл был повреждён, копия: %s.bak"), *OutPath));
    }
  }
  FS08TunerOverridesFile::FBoard Board;
  Board.Board = S.BoardId;
  Board.Profile = S.LightId;
  if (S.BoardIndex != INDEX_NONE) Board.Anchors.Add({FString::Printf(TEXT("/boards/%d/id"), S.BoardIndex), S.BoardId});
  for (const FS08TunerEntry& E : S.Model.GetEntries()) {
    Board.Entries.Add({E.Pointer, E.Value, S.Model.BaseValue(E.Pointer)});
  }
  if (Board.Entries.IsEmpty()) {
    File.Boards.RemoveAll([&](const FS08TunerOverridesFile::FBoard& B) { return B.Board == S.BoardId; });
  } else {
    File.PutBoard(Board);
  }
  File.SavedAt = FDateTime::UtcNow().ToIso8601();
  File.BaseSha256 = S.Model.GetBaseSha256();
  File.BaseRevision = S.Model.GetBaseRevision();
  IFileManager::Get().MakeDirectory(*FPaths::GetPath(OutPath), true);
  if (!S08LiveTune::WriteFileAtomic(OutPath, File.ToJson())) {
    OutError = FString::Printf(TEXT("не удалось записать %s"), *OutPath);
    return false;
  }
  S.LastSavedAt = FDateTime::Now().ToString(TEXT("%H:%M:%S"));
  ++S.Version;
  FS08Trace::Write(FString::Printf(TEXT("ARTTUNER saved file=%s board=%s entries=%d boards=%d"), *OutPath, *S.BoardId,
                                   Board.Entries.Num(), File.Boards.Num()));
  return true;
}

void AS08FlowGameMode::ArtTunerReset(const FString& GroupId) {
  if (!ArtTuner.IsValid()) return;
  FS08ArtTunerSession& S = *ArtTuner;
  uint8 Scopes = 0;
  for (const FS08TunerGroup& G : S.Groups) {
    if (!GroupId.IsEmpty() && G.Id != GroupId) continue;
    for (const FS08TunerParam& P : G.Params) {
      const bool bChanged = S.Model.IsChanged(P.Pointer) || S.Model.IsChanged(P.Pointer + TEXT("/ev100"));
      if (!bChanged) continue;
      S.Model.Reset(P.Pointer);
      for (const TCHAR* Leaf : {TEXT("/ev100"), TEXT("/minBrightness"), TEXT("/maxBrightness")}) {
        if (P.Type == ES08TunerType::Ev100) S.Model.Reset(P.Pointer + Leaf);
      }
      Scopes |= static_cast<uint8>(G.Scope);
    }
  }
  if (GroupId.IsEmpty()) S.Model.ResetAll();
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (S.Model.Build(Data, Errors)) {
    S.PendingData = MoveTemp(Data);
    S.bPending = true;
    S.PendingScopes |= Scopes;
  }
  ++S.Version;
  FS08Trace::Write(FString::Printf(TEXT("ARTTUNER reset group=%s scopes=%s entries=%d"), GroupId.IsEmpty() ? TEXT("*") : *GroupId,
                                   *S08TunerScopeNames(static_cast<ES08TunerScope>(Scopes)), S.Model.GetEntries().Num()));
}

TSharedPtr<FJsonObject> AS08FlowGameMode::ArtTunerState() const {
  TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
  Root->SetBoolField(TEXT("enabled"), bArtTunerFlag);
  Root->SetBoolField(TEXT("active"), ArtTuner.IsValid());
  if (!ArtTuner.IsValid()) return Root;
  const FS08ArtTunerSession& S = *ArtTuner;
  Root->SetStringField(TEXT("board"), S.BoardId);
  Root->SetStringField(TEXT("light"), S.LightId);
  Root->SetNumberField(TEXT("boardIndex"), S.BoardIndex);
  Root->SetStringField(TEXT("file"), S.File);
  Root->SetStringField(TEXT("profiles"), S.ProfilesPath);
  Root->SetStringField(TEXT("source"), BoardActor ? BoardActor->GetAppliedRender().ProfilesSource : FString());
  Root->SetNumberField(TEXT("applies"), S.Applies);
  Root->SetNumberField(TEXT("rebuilds"), S.Rebuilds);
  Root->SetNumberField(TEXT("lastApplyMs"), S.LastApplyMs);
  Root->SetStringField(TEXT("lastApply"), S.LastApplyNote);
  Root->SetBoolField(TEXT("pending"), S.bPending);
  Root->SetBoolField(TEXT("panelOpen"), S.bPanelOpen);
  Root->SetStringField(TEXT("lastError"), S.LastError);
  Root->SetStringField(TEXT("savedAt"), S.LastSavedAt);
  TArray<TSharedPtr<FJsonValue>> Warnings;
  for (const FString& W : S.Warnings) Warnings.Add(MakeShared<FJsonValueString>(W));
  Root->SetArrayField(TEXT("warnings"), Warnings);
  TArray<TSharedPtr<FJsonValue>> Entries;
  for (const FS08TunerEntry& E : S.Model.GetEntries()) {
    TSharedRef<FJsonObject> O = MakeShared<FJsonObject>();
    O->SetStringField(TEXT("pointer"), E.Pointer);
    O->SetField(TEXT("value"), E.Value);
    const TSharedPtr<FJsonValue> Base = S.Model.BaseValue(E.Pointer);
    O->SetField(TEXT("base"), Base.IsValid() ? Base : MakeShared<FJsonValueNull>());
    Entries.Add(MakeShared<FJsonValueObject>(O));
  }
  Root->SetArrayField(TEXT("entries"), Entries);
  TArray<TSharedPtr<FJsonValue>> Groups;
  for (const FS08TunerGroup& G : S.Groups) {
    TSharedRef<FJsonObject> GO = MakeShared<FJsonObject>();
    GO->SetStringField(TEXT("id"), G.Id);
    GO->SetStringField(TEXT("label"), G.Label);
    GO->SetStringField(TEXT("scope"), S08TunerScopeNames(G.Scope));
    GO->SetStringField(TEXT("note"), G.Note);
    GO->SetBoolField(TEXT("inert"), G.bInert);
    TArray<TSharedPtr<FJsonValue>> Rows;
    for (const FS08TunerParam& P : G.Params) {
      TSharedRef<FJsonObject> PO = MakeShared<FJsonObject>();
      PO->SetStringField(TEXT("id"), P.Id);
      PO->SetStringField(TEXT("label"), P.Label);
      PO->SetStringField(TEXT("pointer"), P.Pointer);
      PO->SetStringField(TEXT("type"), S08TunerTypeName(P.Type));
      PO->SetStringField(TEXT("unit"), P.Unit);
      const FString ValuePointer = P.Type == ES08TunerType::Ev100 ? P.Pointer + TEXT("/ev100") : P.Pointer;
      const TSharedPtr<FJsonValue> V = S.Model.Value(ValuePointer);
      const TSharedPtr<FJsonValue> B = S.Model.BaseValue(ValuePointer);
      PO->SetField(TEXT("value"), V.IsValid() ? V : MakeShared<FJsonValueNull>());
      PO->SetField(TEXT("base"), B.IsValid() ? B : MakeShared<FJsonValueNull>());
      PO->SetBoolField(TEXT("changed"), S.Model.IsChanged(ValuePointer));
      if (P.bHasMin) PO->SetNumberField(TEXT("min"), P.Min);
      if (P.bHasMax) PO->SetNumberField(TEXT("max"), P.Max);
      PO->SetNumberField(TEXT("sliderMin"), P.SliderMin);
      PO->SetNumberField(TEXT("sliderMax"), P.SliderMax);
      PO->SetNumberField(TEXT("step"), P.Step);
      if (P.bHasDefault) PO->SetField(TEXT("default"), P.DefaultValue());
      Rows.Add(MakeShared<FJsonValueObject>(PO));
    }
    GO->SetArrayField(TEXT("rows"), Rows);
    Groups.Add(MakeShared<FJsonValueObject>(GO));
  }
  Root->SetArrayField(TEXT("groups"), Groups);
  return Root;
}

void AS08FlowGameMode::ArtTunerTick() {
  if (!bArtTunerFlag) return;
  if (!ArtTuner.IsValid()) {
    if (BoardActor && BoardActor->IsArtActive() && CameraZoom.IsReady()) ArtTunerBegin();
    if (!ArtTuner.IsValid()) return;
  } else if (BoardActor && BoardActor->IsArtActive() && BoardActor->GetArtProfileId() != ArtTuner->BoardId) {
    // another board (a new game in the same client): a fresh session on its rows
    ArtTunerEnd();
    if (!ArtTunerBegin()) return;
  }
  APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
  if (PC) {
    const bool bShift = PC->IsInputKeyDown(EKeys::LeftShift) || PC->IsInputKeyDown(EKeys::RightShift);
    const bool bCtrl = PC->IsInputKeyDown(EKeys::LeftControl) || PC->IsInputKeyDown(EKeys::RightControl);
    // F10 in the free view; Shift+F10 in a live game (F10 alone stays the operator debug panel there)
    if (PC->WasInputKeyJustPressed(EKeys::F10) && (ArtView.IsValid() || bShift)) ArtTunerSetPanelOpen(!ArtTuner->bPanelOpen);
    if (bCtrl && PC->WasInputKeyJustPressed(EKeys::S)) {
      FString Path, Error;
      if (!ArtTunerSave(FString(), Path, Error)) {
        ArtTuner->LastError = Error;
        ++ArtTuner->Version;
      }
    }
  }
  ArtTunerApplyPending(false);
}

void AS08FlowGameMode::LiveTuneTuner(const FS08LiveCommand& Cmd, FS08LiveResult& Result) {
  Result.Extra = MakeShared<FJsonObject>();
  if (!ArtTuner.IsValid() && Cmd.Action != ES08LiveAction::TunerState) {
    Result.Errors.Add(bArtTunerFlag ? TEXT("the tuner has no art board yet") : TEXT("no -ArtTuner on the command line"));
    return;
  }
  switch (Cmd.Action) {
    case ES08LiveAction::Tune: {
      const int32 AppliesBefore = ArtTuner->Applies;
      const int32 RebuildsBefore = ArtTuner->Rebuilds;
      TArray<TSharedPtr<FJsonValue>> Done;
      for (const TPair<FString, TSharedPtr<FJsonValue>>& E : Cmd.TuneEntries) {
        FString Error;
        if (!ArtTunerSetValue(E.Key, E.Value, Error)) {
          Result.Errors.Add(Error);
          continue;
        }
        const FS08TunerParam* P = ArtTuner->FindParam(E.Key);
        TSharedRef<FJsonObject> O = MakeShared<FJsonObject>();
        O->SetStringField(TEXT("pointer"), P ? P->Pointer : E.Key);
        O->SetStringField(TEXT("scope"), P ? S08TunerScopeNames(P->Scope) : FString());
        const FString ValuePointer = P && P->Type == ES08TunerType::Ev100 ? P->Pointer + TEXT("/ev100") : (P ? P->Pointer : E.Key);
        const TSharedPtr<FJsonValue> V = ArtTuner->Model.Value(ValuePointer);
        O->SetField(TEXT("value"), V.IsValid() ? V : MakeShared<FJsonValueNull>());
        Done.Add(MakeShared<FJsonValueObject>(O));
      }
      const double T0 = FPlatformTime::Seconds();
      ArtTunerApplyPending(true);
      Result.Extra->SetArrayField(TEXT("applied"), Done);
      Result.Extra->SetNumberField(TEXT("applyMs"), (FPlatformTime::Seconds() - T0) * 1000.0);
      Result.Extra->SetNumberField(TEXT("applies"), ArtTuner->Applies - AppliesBefore);
      Result.Extra->SetNumberField(TEXT("rebuilds"), ArtTuner->Rebuilds - RebuildsBefore);
      Result.Extra->SetStringField(TEXT("scopes"), ArtTuner->LastApplyNote);
      Result.Extra->SetNumberField(TEXT("entries"), ArtTuner->Model.GetEntries().Num());
      Result.Extra->SetStringField(TEXT("source"), BoardActor ? BoardActor->GetAppliedRender().ProfilesSource : FString());
      return;
    }
    case ES08LiveAction::TunerState:
      Result.Extra->SetObjectField(TEXT("tuner"), ArtTunerState());
      return;
    case ES08LiveAction::TunerSave: {
      FString Path, Error;
      if (!ArtTunerSave(Cmd.TunerFile, Path, Error)) Result.Errors.Add(Error);
      else Result.Files.Add(Path);
      Result.Extra->SetNumberField(TEXT("entries"), ArtTuner->Model.GetEntries().Num());
      return;
    }
    case ES08LiveAction::TunerReset:
      if (!Cmd.TunerGroup.IsEmpty() && !ArtTuner->FindGroup(Cmd.TunerGroup)) {
        Result.Errors.Add(FString::Printf(TEXT("tunerReset: no group '%s' on this board"), *Cmd.TunerGroup));
        return;
      }
      ArtTunerReset(Cmd.TunerGroup);
      ArtTunerApplyPending(true);
      Result.Extra->SetNumberField(TEXT("entries"), ArtTuner->Model.GetEntries().Num());
      return;
    case ES08LiveAction::TunerPanel:
      ArtTunerSetPanelOpen(Cmd.bPanelOpen);
      Result.Extra->SetBoolField(TEXT("panelOpen"), ArtTuner->bPanelOpen);
      return;
    default:
      Result.Errors.Add(TEXT("not a tuner action"));
  }
}

void AS08FlowGameMode::LiveTuneArtView(const FS08LiveCommand& Cmd, FS08LiveResult& Result) {
  Result.Extra = MakeShared<FJsonObject>();
  if (!ArtView.IsValid()) {
    Result.Errors.Add(TEXT("artView needs -ArtView=<map>"));
    return;
  }
  FS08ArtViewSession& V = *ArtView;
  if (!Cmd.ArtViewView.IsEmpty()) ArtViewSetView(Cmd.ArtViewView);
  if (Cmd.bArtViewSelect) {
    SelectFighter(Cmd.ArtViewSelect);
    if (!Cmd.ArtViewSelect.IsEmpty() && SelectedFighterId != Cmd.ArtViewSelect) {
      Result.Errors.Add(FString::Printf(TEXT("artView: no fighter '%s'"), *Cmd.ArtViewSelect));
    }
  }
  if (FMath::IsFinite(Cmd.ArtViewYaw)) V.Cam.YawDeg = FRotator::NormalizeAxis(Cmd.ArtViewYaw);
  if (FMath::IsFinite(Cmd.ArtViewPitch)) {
    V.Cam.PitchDeg = FMath::Clamp(Cmd.ArtViewPitch, S08ArtViewSpec::MinPitchDeg, S08ArtViewSpec::MaxPitchDeg);
  }
  if (Cmd.bArtViewPan) V.Cam.PanUU = Cmd.ArtViewPan.GetClampedToMaxSize(S08ArtViewSpec::MaxPanUU);
  if (Cmd.ArtViewHeroLight >= 0 && BoardActor) {
    V.bHeroLightOff = Cmd.ArtViewHeroLight == 0;
    BoardActor->SetHeroLightViewOff(V.bHeroLightOff);
    BoardActor->UpdateHeroLights();
  }
  if (Cmd.ArtViewPause >= 0) {
    V.bPaused = Cmd.ArtViewPause == 1;
    if (APlayerController* PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr) PC->SetPause(V.bPaused);
  }
  if (Cmd.ArtViewHelp >= 0) {
    V.bHelp = Cmd.ArtViewHelp == 1;
    V.HintUntil = 0.0f;
  }
  ArtViewRefreshOverlay();
  Result.Extra->SetStringField(TEXT("view"), V.View);
  Result.Extra->SetNumberField(TEXT("yaw"), V.Cam.YawDeg);
  Result.Extra->SetNumberField(TEXT("pitch"), V.Cam.PitchDeg);
  Result.Extra->SetStringField(TEXT("pan"), V.Cam.PanUU.ToString());
  Result.Extra->SetStringField(TEXT("selected"), SelectedFighterId);
  Result.Extra->SetBoolField(TEXT("heroLightOff"), V.bHeroLightOff);
  Result.Extra->SetBoolField(TEXT("paused"), V.bPaused);
  Result.Extra->SetNumberField(TEXT("heroLights"), BoardActor ? BoardActor->GetHeroLightCount() : 0);
}

void AS08FlowGameMode::ArtTunerResetRow(const FString& RowId) {
  if (!ArtTuner.IsValid()) return;
  FS08ArtTunerSession& S = *ArtTuner;
  const FS08TunerParam* P = S.FindParam(RowId);
  if (!P) return;
  S.Model.Reset(P->Pointer);
  if (P->Type == ES08TunerType::Ev100) {
    for (const TCHAR* Leaf : {TEXT("/ev100"), TEXT("/minBrightness"), TEXT("/maxBrightness")}) S.Model.Reset(P->Pointer + Leaf);
  }
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (S.Model.Build(Data, Errors)) {
    S.PendingData = MoveTemp(Data);
    S.bPending = true;
    S.PendingScopes |= static_cast<uint8>(P->Scope);
  }
  ++S.Version;
}

void AS08FlowGameMode::ArtTunerSetPanelOpen(bool bOpen) {
  if (!ArtTuner.IsValid()) return;
  FS08ArtTunerSession& S = *ArtTuner;
  if (bOpen && !S.Panel.IsValid() && GEngine && GEngine->GameViewport) {
    TWeakObjectPtr<AS08FlowGameMode> Self(this);
    FS08ArtTunerPanelActions Actions;
    Actions.Set = [Self](const FString& RowId, const TSharedPtr<FJsonValue>& Value, FString& OutError) {
      return Self.IsValid() && Self->ArtTunerSetValue(RowId, Value, OutError);
    };
    Actions.ResetRow = [Self](const FString& RowId) {
      if (Self.IsValid()) Self->ArtTunerResetRow(RowId);
    };
    Actions.ResetGroup = [Self](const FString& GroupId) {
      if (Self.IsValid()) Self->ArtTunerReset(GroupId);
    };
    Actions.Save = [Self]() {
      if (!Self.IsValid() || !Self->ArtTuner.IsValid()) return;
      FString Path, Error;
      if (!Self->ArtTunerSave(FString(), Path, Error)) Self->ArtTuner->LastError = Error;
      else Self->ArtTuner->LastError.Reset();
    };
    Actions.Close = [Self]() {
      if (Self.IsValid()) Self->ArtTunerSetPanelOpen(false);
    };
    // F10 alone stays the operator debug panel in a live game (ArtTunerTick)
    Actions.CloseKey = ArtView.IsValid() ? TEXT("F10") : TEXT("Shift+F10");
    S.Panel = SNew(SS08ArtTunerPanel, ArtTuner, MoveTemp(Actions));
    S.PanelRoot = SNew(SBox)
                      .HAlign(HAlign_Right)
                      .VAlign(VAlign_Fill)
                      .Padding(FMargin(0.0f, 12.0f, 12.0f, 12.0f))[SNew(SBox).WidthOverride(480.0f)[S.Panel.ToSharedRef()]];
    GEngine->GameViewport->AddViewportWidgetContent(S.PanelRoot.ToSharedRef(), 40);
  }
  if (!bOpen && S.Panel.IsValid()) S.Panel->Flush();
  if (S.PanelRoot.IsValid()) S.PanelRoot->SetVisibility(bOpen ? EVisibility::SelfHitTestInvisible : EVisibility::Collapsed);
  if (!bOpen && FSlateApplication::IsInitialized()) FSlateApplication::Get().SetAllUserFocusToGameViewport();
  S.bPanelOpen = bOpen && S.Panel.IsValid();
  FS08Trace::Write(FString::Printf(TEXT("ARTTUNER panel open=%d"), S.bPanelOpen ? 1 : 0));
}

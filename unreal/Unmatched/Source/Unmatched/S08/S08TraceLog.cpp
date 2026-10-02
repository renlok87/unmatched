#include "S08TraceLog.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/CommandLine.h"
#include "Misc/DateTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

FString FS08Trace::Path;
bool FS08Trace::bOpen = false;
bool FS08Trace::bJournal = false;
TArray<FString> FS08Trace::Journal;
FString FS08Trace::TeePath;

void FS08Trace::Open() {
  if (bOpen) return;
  FString Override;
  if (FParse::Value(FCommandLine::Get(), TEXT("S08Trace="), Override) && !Override.IsEmpty()) {
    Path = Override;
  } else {
    Path = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("S08"),
                           FString::Printf(TEXT("trace-%s.log"),
                                           *FDateTime::Now().ToString()));
  }
  IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path), true);
  bOpen = true;
  Write(TEXT("--- S08 trace open ") + FDateTime::UtcNow().ToString() + TEXT(" ---"));
}

FString FS08Trace::Stamp(const FString& Line) { return FDateTime::UtcNow().ToString() + TEXT(" ") + Line; }

void FS08Trace::Write(const FString& Line) {
  if (!bOpen) return;
  // Defense in depth: never persist anything that smells like credentials.
  static const TArray<FString> SecretMarkers = {TEXT("Bearer "), TEXT("accessToken"),
                                                TEXT("refreshToken"), TEXT("password=")};
  for (const FString& Marker : SecretMarkers) {
    if (Line.Contains(Marker)) return;
  }
  const FString Stamped = Stamp(Line);
  FFileHelper::SaveStringToFile(
      Stamped + LINE_TERMINATOR, *Path,
      FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
      &IFileManager::Get(), FILEWRITE_Append);
  if (bJournal) Journal.Add(Stamped);
  if (!TeePath.IsEmpty()) {
    FFileHelper::SaveStringToFile(Stamped + LINE_TERMINATOR, *TeePath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
                                  &IFileManager::Get(), FILEWRITE_Append);
  }
}

void FS08Trace::Close() {
  if (!bOpen) return;
  Write(TEXT("--- S08 trace close ---"));
  bOpen = false;
}

void FS08Trace::SetJournal(bool bOn) {
  bJournal = bOn;
  if (!bOn) Journal.Empty();
}

TArray<FString> FS08Trace::JournalSlice(int32 From, int32 To) {
  TArray<FString> Out;
  From = FMath::Clamp(From, 0, Journal.Num());
  To = FMath::Clamp(To, From, Journal.Num());
  for (int32 I = From; I < To; ++I) Out.Add(Journal[I]);
  return Out;
}

void FS08Trace::TruncateJournal(int32 Num) {
  if (Num >= 0 && Num < Journal.Num()) Journal.SetNum(Num);
}

void FS08Trace::SetTee(const FString& InPath) {
  TeePath = InPath;
  if (!TeePath.IsEmpty()) IFileManager::Get().MakeDirectory(*FPaths::GetPath(TeePath), true);
}

void FS08Trace::ClearTee() { TeePath.Reset(); }

void FS08Trace::WriteTeeRaw(const TArray<FString>& Lines) {
  if (TeePath.IsEmpty() || Lines.IsEmpty()) return;
  FString Text;
  for (const FString& Line : Lines) Text += Line + LINE_TERMINATOR;
  FFileHelper::SaveStringToFile(Text, *TeePath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM, &IFileManager::Get(),
                                FILEWRITE_Append);
}

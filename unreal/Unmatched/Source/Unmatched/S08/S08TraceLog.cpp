#include "S08TraceLog.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/CommandLine.h"
#include "Misc/DateTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

FString FS08Trace::Path;
bool FS08Trace::bOpen = false;

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

void FS08Trace::Write(const FString& Line) {
  if (!bOpen) return;
  // Defense in depth: never persist anything that smells like credentials.
  static const TArray<FString> SecretMarkers = {TEXT("Bearer "), TEXT("accessToken"),
                                                TEXT("refreshToken"), TEXT("password=")};
  for (const FString& Marker : SecretMarkers) {
    if (Line.Contains(Marker)) return;
  }
  FFileHelper::SaveStringToFile(
      FDateTime::UtcNow().ToString() + TEXT(" ") + Line + LINE_TERMINATOR, *Path,
      FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
      &IFileManager::Get(), FILEWRITE_Append);
}

void FS08Trace::Close() {
  if (!bOpen) return;
  Write(TEXT("--- S08 trace close ---"));
  bOpen = false;
}

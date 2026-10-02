// GD-028/029: evidence trace file for packaged runs. Only flow events are
// written; tokens/passwords never enter trace lines (GD-028: no sensitive
// logging). Path override: -S08Trace=<absolute path>.
#pragma once

#include "CoreMinimal.h"

class UNMATCHED_API FS08Trace {
public:
  static void Open();
  static void Write(const FString& Line);
  static void Close();

  // ---- ENV-MAPS live tune (S08LiveTune.h): off unless -ArtLiveTune armed it; a run without the flag never touches
  // the journal or a tee (no memory, no extra file, the trace bytes unchanged) ----
  /** Keeps every written line (with its timestamp) in memory, so a live-tune shot can copy the lines of the current
   *  board build into its own bench.trace.log. */
  static void SetJournal(bool bOn);
  static bool IsJournalOn() { return bJournal; }
  static int32 JournalNum() { return Journal.Num(); }
  /** Lines [From, To) of the journal (clamped). */
  static TArray<FString> JournalSlice(int32 From, int32 To);
  /** Drops the journal lines from Num on (the lines of a finished shot, a superseded build). */
  static void TruncateJournal(int32 Num);
  /** Every written line also goes to Path (appended; the live-tune shot's bench.trace.log) until ClearTee. */
  static void SetTee(const FString& InPath);
  static void ClearTee();
  /** Appends already timestamped lines (journal copies) to the tee only. */
  static void WriteTeeRaw(const TArray<FString>& Lines);
  /** "<utc timestamp> <Line>" as Write stores it. */
  static FString Stamp(const FString& Line);

private:
  static FString Path;
  static bool bOpen;
  static bool bJournal;
  static TArray<FString> Journal;
  static FString TeePath;
};

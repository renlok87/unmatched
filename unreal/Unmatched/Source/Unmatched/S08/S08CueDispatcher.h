// DE-018 (W-14; GD-044 "Cue subsystem", first slice): the world-free CUE dispatcher of
// docs/unreal/contracts/cue-dispatcher/CUE-DISPATCHER.md §4 (rules D1-D12) for the combat rows CUE-008..011, 013
// and 014. It owns no game state: it decides show / duplicate / stale, interrupts and replacements, the reduced
// motion length, the fallback for missing assets and the `CUE fx …` trace lines (§5) that
// tools/s08/cue_contract/cue_contract.py check-trace gates. The UE adapter (AS08FlowGameMode + the combat staging,
// S09CombatStage.h) executes the shows; it never decides a repeat.
//
// Rows are built in (the JSON lives in docs/, outside the pak) and Unmatched.S08.CueDispatcher.Table compares them
// field by field with cue-table.json; Unmatched.S08.CueDispatcher.Fixtures runs the contract fixtures through this
// class and compares the trace byte for byte with their expect_trace (the C++ port of §7).
//
// DE-018 extension (CUE-DISPATCHER.md §3.1, §4 D12): a show may carry a HOLD - the skippable read / effect time the
// combat staging inserts inside CUE-010 between the flip and the slam. The hold lengthens the show, the done line
// carries `hold=<ms>` and the input-blocking part is `ms - hold` (gate G5).
#pragma once

#include "CoreMinimal.h"

enum class ES08CueOnNew : uint8 { Replace, Cascade, JumpToFinal, Interrupt, None };
enum class ES08CueReduced : uint8 { Keep, Shorten, Snap };
enum class ES08CueResult : uint8 { Spawned, Fallback, Duplicate, Stale };

/** One cue-table.json row, reduced to what the dispatcher decides on. */
struct UNMATCHED_API FS08CueRow {
  FString Id;                    // CUE-NNN
  bool bServer = true;           // source "server": a seq is required and deduplicated (D2/D3)
  FString Subject;               // default subject: fighter / target / scene / hud / cursor
  int32 DurationMs = 0;
  bool bBlocksInput = false;
  ES08CueOnNew OnNew = ES08CueOnNew::Replace;
  bool bReplaceScopeCue = false; // replace_scope "cue" (any subject) vs "subject"
  TArray<FString> InterruptedBy;
  ES08CueReduced Reduced = ES08CueReduced::Keep;
  int32 ReducedMaxMs = 0;
  bool bHasVfx = false;          // the row has a vfx block (system null = missing until ART-010)
  bool bVfxSocket = false;       // vfx.attach == "socket"
  FString Socket;                // vfx.socket when attached to a socket
  bool bHasSfx = false;
  int32 SfxMaxCount = 0;         // 0 = unlimited (max_count null)
  bool bSfxPreventNew = false;   // resolution PreventNew (else StopOldest)
  int32 SfxRetriggerMs = 0;
  FString ClipRole;              // LungeAttack / HitReact / DeathSettle; empty = no clip channel
  FString Mat = TEXT("none");    // material.cpd_param or "none"
};

namespace S08CueRows {
/** CUE-008, 009, 010, 011, 013, 014 as cue-table.json revision de-003-2026-10-04 writes them. */
UNMATCHED_API const TArray<FS08CueRow>& Combat();
UNMATCHED_API const FS08CueRow* Find(const TArray<FS08CueRow>& Rows, const FString& Id);
}  // namespace S08CueRows

class UNMATCHED_API FS08CueDispatcher {
public:
  explicit FS08CueDispatcher(const TArray<FS08CueRow>& InRows = S08CueRows::Combat());

  /** Channel token of a show: the short asset name, "missing" or "none". Channel is vfx / sfx / clip. Unset: the
   *  rows carry no asset path (ART-010 open), so every channel the row has is "missing" and the others "none". */
  TFunction<FString(const FString& CueId, const FString& Channel, const FString& Subject)> AssetResolver;
  /** VS-6 F3 FX-28: the socket of a socket-attached show for this subject (CUE-014: the hero's field of the S08CueFx
   *  registry - Weapon for King Arthur, Root for Medusa); "" or unset = the row's socket. */
  TFunction<FString(const FString& CueId, const FString& Subject)> SocketResolver;

  /** D11: UI-ACC-006 on/off (`CUE settings reduced_motion=…`). */
  void SetReducedMotion(bool bReduced, int64 TMs, TArray<FString>& OutLines);
  bool IsReducedMotion() const { return bReducedMotion; }
  /** D4: cuts every active show (cut=reconnect); later server cues with seq <= RecoveredSeq are stale. */
  void OnReconnect(int32 RecoveredSeq, int64 TMs, TArray<FString>& OutLines);
  /** D1-D11: one cue event at TMs (non-decreasing). Seq < 0 = no seq (local cues; a server cue needs one).
   *  DurationMs < 0 = the row's duration; HoldMs > 0 lengthens the show by a skippable hold (DE-018). An unknown
   *  cue id writes nothing and returns Stale. bStaged: a cue a staging plays later at its own combat's seq (CUE-011
   *  from the contact frame, CUE-013 from a staged fall) - newer snapshots applied meanwhile do not make it stale
   *  (no D3); D2 and D4 still apply. */
  ES08CueResult Feed(const FString& CueId, const FString& Subject, int32 Seq, int64 TMs, TArray<FString>& OutLines,
                     int32 HoldMs = 0, int32 DurationMs = -1, bool bStaged = false);
  /** DE-018: the staging skipped (part of) the hold of an active show; its done moves to start + duration + hold.
   *  False when no such show is active. */
  bool SetHold(const FString& CueId, const FString& Subject, int32 Seq, int32 HoldMs);
  /** D6 `jump`: ends an active show now (staging cut). False when none. */
  bool Cut(const FString& CueId, const FString& Subject, int32 Seq, int64 TMs, const TCHAR* CutName,
           TArray<FString>& OutLines);
  /** D1: done lines of every show that ended at or before TMs. */
  void Advance(int64 TMs, TArray<FString>& OutLines);
  /** Done lines of every remaining show (end of a fixture). */
  void Finish(TArray<FString>& OutLines);
  bool IsActive(const FString& CueId, const FString& Subject, int32 Seq) const;
  /** Shown length of a cue right now (row or override, reduced motion applied), without the hold. */
  int32 ShowDurationMs(const FString& CueId, int32 DurationMs = -1) const;
  int64 GetNowMs() const { return NowMs; }

  static FString SeqToken(int32 Seq) { return Seq < 0 ? FString(TEXT("-")) : FString::FromInt(Seq); }

private:
  struct FInstance {
    FString Id;
    FString Subject;
    FString SeqTok;
    int64 StartMs = 0;
    int64 EndMs = 0;
    int32 DurationMs = 0;
    int32 HoldMs = 0;
    int64 Order = 0;
  };
  struct FSound {
    FString Subject;
    FString SeqTok;
    int64 EndMs = 0;
  };
  TArray<FS08CueRow> Rows;
  TSet<FString> Seen;            // "<id>|<subject>|<seq>"
  int32 HighWater = MIN_int32;
  int32 RecoveredSeq = MIN_int32;
  bool bReducedMotion = false;
  TArray<FInstance> Active;
  TMap<FString, TArray<FSound>> SoundsActive;
  TMap<FString, int64> SoundLast;
  int64 NowMs = 0;
  int64 OrderCounter = 0;

  FString Channel(const FS08CueRow& Row, const TCHAR* Name, const FString& Subject) const;
  void Done(const FInstance& Inst, int64 TMs, const TCHAR* CutName, TArray<FString>& OutLines) const;
  void Flush(int64 TMs, TArray<FString>& OutLines);
  void CutWhere(TFunctionRef<bool(const FInstance&)> Pred, int64 TMs, const TCHAR* CutName, TArray<FString>& OutLines);
};

// DE-018: world-free CUE dispatcher (CUE-DISPATCHER.md §4 D1-D12) - see S08CueDispatcher.h.
#include "S08CueDispatcher.h"

namespace {
FS08CueRow MakeRow(const TCHAR* Id, int32 DurationMs, bool bBlocks, ES08CueOnNew OnNew, bool bScopeCue,
                   TArray<FString> InterruptedBy, bool bHasVfx, bool bVfxSocket, const TCHAR* Socket,
                   int32 SfxMaxCount, const TCHAR* ClipRole, const TCHAR* Mat) {
  FS08CueRow Row;
  Row.Id = Id;
  Row.bServer = true;
  Row.Subject = TEXT("fighter");
  Row.DurationMs = DurationMs;
  Row.bBlocksInput = bBlocks;
  Row.OnNew = OnNew;
  Row.bReplaceScopeCue = bScopeCue;
  Row.InterruptedBy = MoveTemp(InterruptedBy);
  // Every combat row: reduced_motion shorten <= 100 ms (UI-ACC-006), a sound slot (missing until GD-049).
  Row.Reduced = ES08CueReduced::Shorten;
  Row.ReducedMaxMs = 100;
  Row.bHasVfx = bHasVfx;
  Row.bVfxSocket = bVfxSocket;
  Row.Socket = Socket;
  Row.bHasSfx = true;
  Row.SfxMaxCount = SfxMaxCount;
  Row.bSfxPreventNew = false;
  Row.SfxRetriggerMs = 0;
  Row.ClipRole = ClipRole;
  Row.Mat = Mat;
  return Row;
}
}  // namespace

const TArray<FS08CueRow>& S08CueRows::Combat() {
  static const TArray<FS08CueRow> Rows = [] {
    TArray<FS08CueRow> Out;
    // CUE-008 attack declared: aim ring + direction flash, NO clip (01 F-03); cut by the next combat cue.
    Out.Add(MakeRow(TEXT("CUE-008"), 600, true, ES08CueOnNew::Interrupt, false,
                    {TEXT("CUE-009"), TEXT("CUE-010"), TEXT("CUE-011"), TEXT("CUE-013")}, true, true, TEXT("Weapon"), 0,
                    TEXT(""), TEXT("none")));
    // CUE-009 defense played: shield flicker on the defender (FxFlash).
    Out.Add(MakeRow(TEXT("CUE-009"), 500, false, ES08CueOnNew::Replace, false, {}, true, true, TEXT("Head"), 0,
                    TEXT(""), TEXT("FxFlash")));
    // CUE-010 reveal and score: a HUD scene cue (no vfx, no clip); holds of the staging live inside it (§3.1).
    FS08CueRow Reveal = MakeRow(TEXT("CUE-010"), 800, true, ES08CueOnNew::Replace, true, {}, false, false, TEXT(""), 0,
                                TEXT(""), TEXT("none"));
    Reveal.Subject = TEXT("scene");
    Out.Add(Reveal);
    // CUE-011 damage: HitReact + hit tint from the contact frame; 900 ms from contact; two hit sounds at most.
    Out.Add(MakeRow(TEXT("CUE-011"), 900, true, ES08CueOnNew::Replace, false, {}, true, true, TEXT("Head"), 2,
                    TEXT("HitReact"), TEXT("FxFlash")));
    // CUE-013 death: DeathSettle + fade; a new death of the same figure jumps to the final pose.
    Out.Add(MakeRow(TEXT("CUE-013"), 950, true, ES08CueOnNew::JumpToFinal, false, {}, true, false, TEXT(""), 0,
                    TEXT("DeathSettle"), TEXT("Fade")));
    // CUE-014 hero ability (AFTER COMBAT steps): Weapon socket by default (GD-044 per-hero socket open).
    Out.Add(MakeRow(TEXT("CUE-014"), 800, true, ES08CueOnNew::Replace, false, {}, true, true, TEXT("Weapon"), 0,
                    TEXT(""), TEXT("none")));
    return Out;
  }();
  return Rows;
}

const FS08CueRow* S08CueRows::Find(const TArray<FS08CueRow>& Rows, const FString& Id) {
  return Rows.FindByPredicate([&Id](const FS08CueRow& Row) { return Row.Id == Id; });
}

FS08CueDispatcher::FS08CueDispatcher(const TArray<FS08CueRow>& InRows) : Rows(InRows) {}

FString FS08CueDispatcher::Channel(const FS08CueRow& Row, const TCHAR* Name, const FString& Subject) const {
  const FString ChannelName(Name);
  const bool bHas = ChannelName == TEXT("vfx") ? Row.bHasVfx
                    : ChannelName == TEXT("sfx") ? Row.bHasSfx
                                                 : !Row.ClipRole.IsEmpty();
  if (!bHas) return TEXT("none");
  if (AssetResolver) {
    const FString Token = AssetResolver(Row.Id, ChannelName, Subject);
    return Token.IsEmpty() ? FString(TEXT("missing")) : Token;
  }
  return TEXT("missing");
}

void FS08CueDispatcher::Done(const FInstance& Inst, int64 TMs, const TCHAR* CutName, TArray<FString>& OutLines) const {
  const int64 Ms = TMs - Inst.StartMs;
  FString Line = FString::Printf(TEXT("CUE fx done id=%s subject=%s seq=%s t=%lld ms=%lld cut=%s"), *Inst.Id,
                                 *Inst.Subject, *Inst.SeqTok, static_cast<long long>(TMs), static_cast<long long>(Ms),
                                 CutName);
  if (Inst.HoldMs > 0) {
    // DE-018 (§4 D12): the skippable part of the show; G5 measures the input block as ms - hold.
    Line += FString::Printf(TEXT(" hold=%lld"), static_cast<long long>(FMath::Min<int64>(Inst.HoldMs, Ms)));
  }
  OutLines.Add(MoveTemp(Line));
}

void FS08CueDispatcher::Flush(int64 TMs, TArray<FString>& OutLines) {
  TArray<FInstance> Due;
  for (int32 I = Active.Num() - 1; I >= 0; --I) {
    if (Active[I].EndMs <= TMs) {
      Due.Add(Active[I]);
      Active.RemoveAt(I);
    }
  }
  Due.Sort([](const FInstance& A, const FInstance& B) {
    return A.EndMs != B.EndMs ? A.EndMs < B.EndMs : A.Order < B.Order;
  });
  for (const FInstance& Inst : Due) Done(Inst, Inst.EndMs, TEXT("0"), OutLines);
  for (TPair<FString, TArray<FSound>>& Entry : SoundsActive) {
    Entry.Value.RemoveAll([TMs](const FSound& Sound) { return Sound.EndMs <= TMs; });
  }
}

void FS08CueDispatcher::CutWhere(TFunctionRef<bool(const FInstance&)> Pred, int64 TMs, const TCHAR* CutName,
                                 TArray<FString>& OutLines) {
  TArray<FInstance> Hit;
  for (int32 I = Active.Num() - 1; I >= 0; --I) {
    if (Pred(Active[I])) {
      Hit.Add(Active[I]);
      Active.RemoveAt(I);
    }
  }
  Hit.Sort([](const FInstance& A, const FInstance& B) { return A.Order < B.Order; });
  for (const FInstance& Inst : Hit) Done(Inst, TMs, CutName, OutLines);
}

void FS08CueDispatcher::SetReducedMotion(bool bReduced, int64 TMs, TArray<FString>& OutLines) {
  TMs = FMath::Max(TMs, NowMs);
  NowMs = TMs;
  Flush(TMs, OutLines);
  bReducedMotion = bReduced;
  OutLines.Add(FString::Printf(TEXT("CUE settings reduced_motion=%d t=%lld"), bReduced ? 1 : 0,
                               static_cast<long long>(TMs)));
}

void FS08CueDispatcher::OnReconnect(int32 InRecoveredSeq, int64 TMs, TArray<FString>& OutLines) {
  TMs = FMath::Max(TMs, NowMs);
  NowMs = TMs;
  Flush(TMs, OutLines);
  OutLines.Add(FString::Printf(TEXT("CUE reconnect recovered_seq=%d t=%lld"), InRecoveredSeq,
                               static_cast<long long>(TMs)));
  CutWhere([](const FInstance&) { return true; }, TMs, TEXT("reconnect"), OutLines);
  SoundsActive.Reset();
  RecoveredSeq = InRecoveredSeq;
  HighWater = FMath::Max(HighWater, InRecoveredSeq);
}

int32 FS08CueDispatcher::ShowDurationMs(const FString& CueId, int32 DurationMs) const {
  const FS08CueRow* Row = S08CueRows::Find(Rows, CueId);
  if (!Row) return 0;
  int32 Dur = DurationMs >= 0 ? DurationMs : Row->DurationMs;
  if (bReducedMotion && Row->Reduced != ES08CueReduced::Keep) {
    Dur = Row->Reduced == ES08CueReduced::Snap ? 0 : FMath::Min(Dur, Row->ReducedMaxMs);
  }
  return Dur;
}

ES08CueResult FS08CueDispatcher::Feed(const FString& CueId, const FString& InSubject, int32 Seq, int64 TMs,
                                      TArray<FString>& OutLines, int32 HoldMs, int32 DurationMs, bool bStaged) {
  const FS08CueRow* RowPtr = S08CueRows::Find(Rows, CueId);
  if (!RowPtr) return ES08CueResult::Stale;
  const FS08CueRow Row = *RowPtr;
  // D1: time never runs backwards; shows that ended before this event write their done first.
  TMs = FMath::Max(TMs, NowMs);
  NowMs = TMs;
  Flush(TMs, OutLines);
  const FString Subject = InSubject.IsEmpty() ? Row.Subject : InSubject;
  const FString SeqTok = SeqToken(Seq);
  const FString Head = FString::Printf(TEXT("CUE fx id=%s subject=%s seq=%s t=%lld"), *Row.Id, *Subject, *SeqTok,
                                       static_cast<long long>(TMs));
  if (Row.bServer) {
    if (Seq < 0) return ES08CueResult::Stale;  // a server cue without seq is a caller bug: nothing is shown
    // D2: one show per (cue, subject, seq) - the same seq over HTTP and WS is a duplicate.
    const FString Key = FString::Printf(TEXT("%s|%s|%d"), *Row.Id, *Subject, Seq);
    if (Seen.Contains(Key)) {
      OutLines.Add(Head + TEXT(" result=duplicate"));
      return ES08CueResult::Duplicate;
    }
    Seen.Add(Key);
    // D3/D4: older than what was shown, or covered by a reconnect. A staged cue (DE-018 contact, DE-019 fall) keeps its
    // combat's seq on purpose and plays after newer snapshots: D3 does not apply to it (run C G-LIVE, 2026-10-05).
    if ((RecoveredSeq != MIN_int32 && Seq <= RecoveredSeq) ||
        (!bStaged && HighWater != MIN_int32 && Seq < HighWater)) {
      OutLines.Add(Head + TEXT(" result=stale"));
      return ES08CueResult::Stale;
    }
    HighWater = FMath::Max(HighWater, Seq);
  }
  // D7: this cue interrupts the shows that list it; D6: it replaces its own show (per cue or per subject).
  CutWhere(
      [this, &Row](const FInstance& Inst) {
        const FS08CueRow* Other = S08CueRows::Find(Rows, Inst.Id);
        return Other && Other->InterruptedBy.Contains(Row.Id);
      },
      TMs, TEXT("interrupt"), OutLines);
  if (Row.OnNew != ES08CueOnNew::Cascade) {
    const TCHAR* CutName = Row.OnNew == ES08CueOnNew::JumpToFinal ? TEXT("jump") : TEXT("replace");
    CutWhere(
        [&Row, &Subject](const FInstance& Inst) {
          return Inst.Id == Row.Id && (Row.bReplaceScopeCue || Inst.Subject == Subject);
        },
        TMs, CutName, OutLines);
  }
  // D11 / D12: the shown length (reduced motion shortens the animation, never the hold).
  const int32 Dur = ShowDurationMs(Row.Id, DurationMs);
  const bool bReduced = bReducedMotion && Row.Reduced != ES08CueReduced::Keep;
  const FString Vfx = Channel(Row, TEXT("vfx"), Subject);
  const FString Clip = Channel(Row, TEXT("clip"), Subject);
  FString Sfx = Channel(Row, TEXT("sfx"), Subject);
  const int32 Hold = FMath::Max(0, HoldMs);
  if (Sfx != TEXT("none") && Sfx != TEXT("missing")) {
    // D8: retrigger throttle; D9: concurrency (StopOldest / PreventNew).
    const int64* Last = SoundLast.Find(Row.Id);
    if (Last && Row.SfxRetriggerMs > 0 && TMs - *Last < Row.SfxRetriggerMs) {
      Sfx = TEXT("throttled");
    } else {
      TArray<FSound>& Playing = SoundsActive.FindOrAdd(Row.Id);
      if (Row.SfxMaxCount > 0 && Playing.Num() >= Row.SfxMaxCount) {
        if (Row.bSfxPreventNew) {
          Sfx = TEXT("limited");
        } else {
          const FSound Oldest = Playing[0];
          Playing.RemoveAt(0);
          OutLines.Add(FString::Printf(TEXT("CUE sfx stop id=%s subject=%s seq=%s t=%lld reason=concurrency"), *Row.Id,
                                       *Oldest.Subject, *Oldest.SeqTok, static_cast<long long>(TMs)));
        }
      }
      if (Sfx != TEXT("limited")) {
        Playing.Add({Subject, SeqTok, TMs + Dur + Hold});
        SoundLast.Add(Row.Id, TMs);
      }
    }
  }
  const FString Socket = Row.bHasVfx && Row.bVfxSocket ? Row.Socket : FString(TEXT("-"));
  // D10: a missing asset is a fallback show - the length and the done line stay.
  const bool bFallback = Vfx == TEXT("missing") || Sfx == TEXT("missing") || Clip == TEXT("missing");
  OutLines.Add(Head + FString::Printf(TEXT(" vfx=%s sfx=%s clip=%s mat=%s socket=%s reduced=%d result=%s"), *Vfx, *Sfx,
                                      *Clip, *Row.Mat, *Socket, bReduced ? 1 : 0,
                                      bFallback ? TEXT("fallback") : TEXT("spawned")));
  FInstance Inst;
  Inst.Id = Row.Id;
  Inst.Subject = Subject;
  Inst.SeqTok = SeqTok;
  Inst.StartMs = TMs;
  Inst.DurationMs = Dur;
  Inst.HoldMs = Hold;
  Inst.EndMs = TMs + Dur + Hold;
  Inst.Order = ++OrderCounter;
  if (Dur + Hold == 0) {
    Done(Inst, TMs, TEXT("0"), OutLines);
  } else {
    Active.Add(Inst);
  }
  return bFallback ? ES08CueResult::Fallback : ES08CueResult::Spawned;
}

bool FS08CueDispatcher::SetHold(const FString& CueId, const FString& Subject, int32 Seq, int32 HoldMs) {
  const FString SeqTok = SeqToken(Seq);
  for (FInstance& Inst : Active) {
    if (Inst.Id == CueId && Inst.Subject == Subject && Inst.SeqTok == SeqTok) {
      Inst.HoldMs = FMath::Max(0, HoldMs);
      Inst.EndMs = Inst.StartMs + Inst.DurationMs + Inst.HoldMs;
      return true;
    }
  }
  return false;
}

bool FS08CueDispatcher::Cut(const FString& CueId, const FString& Subject, int32 Seq, int64 TMs, const TCHAR* CutName,
                            TArray<FString>& OutLines) {
  TMs = FMath::Max(TMs, NowMs);
  NowMs = TMs;
  Flush(TMs, OutLines);
  const FString SeqTok = SeqToken(Seq);
  bool bAny = false;
  CutWhere(
      [&](const FInstance& Inst) {
        const bool bMatch = Inst.Id == CueId && Inst.Subject == Subject && Inst.SeqTok == SeqTok;
        bAny |= bMatch;
        return bMatch;
      },
      TMs, CutName, OutLines);
  return bAny;
}

void FS08CueDispatcher::Advance(int64 TMs, TArray<FString>& OutLines) {
  TMs = FMath::Max(TMs, NowMs);
  NowMs = TMs;
  Flush(TMs, OutLines);
}

void FS08CueDispatcher::Finish(TArray<FString>& OutLines) { Flush(MAX_int64, OutLines); }

bool FS08CueDispatcher::IsActive(const FString& CueId, const FString& Subject, int32 Seq) const {
  const FString SeqTok = SeqToken(Seq);
  return Active.ContainsByPredicate([&](const FInstance& Inst) {
    return Inst.Id == CueId && Inst.Subject == Subject && Inst.SeqTok == SeqTok;
  });
}

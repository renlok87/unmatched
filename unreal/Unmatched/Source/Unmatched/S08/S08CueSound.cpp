// DE-032: the sound of the CUE sync points (CUE-DISPATCHER.md §3.2) - see S08CueSound.h.
#include "S08CueSound.h"

namespace {
FS08SoundRow MakeRow(const TCHAR* CueId, const TCHAR* SoundClass, int32 Priority, int32 RetriggerMs) {
  FS08SoundRow Row;
  Row.CueId = CueId;
  Row.SoundClass = SoundClass;
  Row.Priority = Priority;
  Row.RetriggerMs = RetriggerMs;
  return Row;  // SoundPath stays empty: cue-table sfx.sound is null until ART-010 / DE-013
}

const TCHAR* ResultName(ES08SoundResult Result) {
  switch (Result) {
    case ES08SoundResult::Played:
      return TEXT("played");
    case ES08SoundResult::Fallback:
      return TEXT("fallback");
    case ES08SoundResult::Throttled:
      return TEXT("throttled");
    default:
      return TEXT("silent");
  }
}

FString GainToken(float Gain) { return FString::Printf(TEXT("%.2f"), Gain); }
}  // namespace

FString S08SoundRows::ShortName(const FString& SoftPath) {
  // /Game/Audio/SW_Hit.SW_Hit -> SW_Hit (the CUE trace token, like the fx dispatcher's asset names)
  FString Name = SoftPath;
  int32 Slash = INDEX_NONE;
  if (Name.FindLastChar(TEXT('/'), Slash)) Name.RightChopInline(Slash + 1);
  int32 Dot = INDEX_NONE;
  if (Name.FindChar(TEXT('.'), Dot)) Name.LeftInline(Dot);
  return Name;
}

const TArray<FS08SoundRow>& S08SoundRows::All() {
  static const TArray<FS08SoundRow> Rows = {
      MakeRow(TEXT("CUE-002"), TEXT("UI"), 2, 0),     // ui: own figure picked
      MakeRow(TEXT("CUE-003"), TEXT("UI"), 1, 0),     // ui: a choice accepted / a HUD press acted
      MakeRow(TEXT("CUE-004"), TEXT("UI"), 1, 300),   // ui: refused, at most once in 300 ms
      MakeRow(TEXT("CUE-007"), TEXT("SFX"), 3, 0),    // step: one per edge
      MakeRow(TEXT("CUE-011"), TEXT("SFX"), 1, 0),    // hit: the contact frame
      MakeRow(TEXT("CUE-015"), TEXT("UI"), 2, 0),     // turn: own turn only
      MakeRow(TEXT("CUE-016"), TEXT("Music"), 1, 0),  // result sting: with the screen
  };
  return Rows;
}

const FS08SoundRow* S08SoundRows::Find(const FString& CueId) {
  return All().FindByPredicate([&CueId](const FS08SoundRow& Row) { return Row.CueId == CueId; });
}

const TCHAR* S08SoundRows::PointName(ES08SoundPoint Point) {
  switch (Point) {
    case ES08SoundPoint::Hit:
      return TEXT("hit");
    case ES08SoundPoint::Step:
      return TEXT("step");
    case ES08SoundPoint::Turn:
      return TEXT("turn");
    case ES08SoundPoint::Result:
      return TEXT("result");
    default:
      return TEXT("ui");
  }
}

const TCHAR* S08SoundRows::BoardUiCue(bool bRefused, bool bCommand, bool bPickedOwn, bool bSelectionChanged) {
  if (bRefused) return TEXT("CUE-004");
  if (bCommand) return TEXT("CUE-003");
  if (bPickedOwn) return TEXT("CUE-002");
  return bSelectionChanged ? TEXT("CUE-003") : nullptr;
}

bool FS08CueSound::SetAudio(const FS08AudioSettings& InAudio, int64 TMs, bool bStart, TArray<FString>& OutLines) {
  if (bAudioSet && InAudio == Audio) return false;
  Audio = InAudio;
  bAudioSet = true;
  OutLines.Add(FString::Printf(
      TEXT("CUE audio master=%d master_mute=%d ambience=%d ambience_mute=%d gain_master=%s gain_ambience=%s t=%lld "
           "applied=%s"),
      FMath::Clamp(Audio.MasterPercent, 0, 100), Audio.bMasterMuted ? 1 : 0, FMath::Clamp(Audio.AmbiencePercent, 0, 100),
      Audio.bAmbienceMuted ? 1 : 0, *GainToken(Audio.MasterGain()), *GainToken(Audio.AmbienceGain()),
      static_cast<long long>(TMs), bStart ? TEXT("start") : TEXT("change")));
  return true;
}

float FS08CueSound::ClassGain(const FString& SoundClass) const {
  if (SoundClass == TEXT("Ambience")) {
    return Audio.bAmbienceMuted ? 0.0f : static_cast<float>(FMath::Clamp(Audio.AmbiencePercent, 0, 100)) / 100.0f;
  }
  return 1.0f;
}

float FS08CueSound::EffectiveGain(const FString& SoundClass) const {
  return SoundClass == TEXT("Ambience") ? Audio.AmbienceGain() : Audio.MasterGain();
}

FS08SoundDecision FS08CueSound::Play(const FS08SoundRequest& Request, int64 NowMs, TArray<FString>& OutLines) {
  FS08SoundDecision Out;
  const FS08SoundRow* Row = S08SoundRows::Find(Request.CueId);
  if (!Row) {
    Out.Result = ES08SoundResult::Silent;
    return Out;
  }
  Out.ClassGain = ClassGain(Row->SoundClass);
  Out.Gain = EffectiveGain(Row->SoundClass);
  Out.bUiSound = Row->SoundClass == TEXT("UI");
  FString Sound = TEXT("none");
  const TCHAR* Reason = nullptr;
  if (Request.Point == ES08SoundPoint::Turn && !Request.bOwnTurn) {
    // SD-51 p. 4: the opponent's turn start is silent (DE: the AI turn starts without a sound, WF1 AV-05)
    Out.Result = ES08SoundResult::Silent;
    Reason = TEXT("opponent");
  } else if (const int64* Last = LastPlayed.Find(Row->CueId);
             Last && Row->RetriggerMs > 0 && NowMs - *Last < Row->RetriggerMs) {
    Out.Result = ES08SoundResult::Throttled;  // D8
  } else if (Out.Gain <= 0.0f) {
    Out.Result = ES08SoundResult::Silent;
    Reason = TEXT("muted");
  } else {
    FString Name;
    if (AssetResolver) {
      Name = AssetResolver(*Row);
    } else if (!Row->SoundPath.IsEmpty()) {
      Name = S08SoundRows::ShortName(Row->SoundPath);
    }
    // D10: no asset - a fallback show, the line stays and nothing plays (no error)
    Sound = Name.IsEmpty() ? FString(TEXT("missing")) : Name;
    Out.Result = Name.IsEmpty() ? ES08SoundResult::Fallback : ES08SoundResult::Played;
    Out.SoundPath = Name.IsEmpty() ? FString() : Row->SoundPath;
    LastPlayed.Add(Row->CueId, NowMs);
  }
  FString Line = FString::Printf(
      TEXT("CUE sound id=%s point=%s subject=%s seq=%s t=%lld event_t=%lld dt=%lld class=%s sound=%s gain=%s result=%s"),
      *Row->CueId, S08SoundRows::PointName(Request.Point), Request.Subject.IsEmpty() ? TEXT("-") : *Request.Subject,
      Request.Seq < 0 ? TEXT("-") : *FString::FromInt(Request.Seq), static_cast<long long>(NowMs),
      static_cast<long long>(Request.EventMs), static_cast<long long>(NowMs - Request.EventMs), *Row->SoundClass, *Sound,
      *GainToken(Out.Gain), ResultName(Out.Result));
  if (Request.Point == ES08SoundPoint::Turn) Line += Request.bOwnTurn ? TEXT(" turn=own") : TEXT(" turn=opp");
  if (Request.Point == ES08SoundPoint::Step) {
    Line += Request.Edge < 0 ? FString(TEXT(" edge=snap"))
                             : FString::Printf(TEXT(" edge=%d/%d"), Request.Edge + 1, Request.Edges);
  }
  if (Request.DueMs >= 0) Line += FString::Printf(TEXT(" due=%lld"), static_cast<long long>(Request.DueMs));
  if (Reason) Line += FString::Printf(TEXT(" reason=%s"), Reason);
  OutLines.Add(MoveTemp(Line));
  return Out;
}

void FS08CueSound::ScheduleSteps(const FString& FighterId, int32 Seq, int64 StartMs, double StepMs, int32 InSteps,
                                 bool bSnapped) {
  auto Add = [this](FS08StepSound&& Step) {
    // stable insert by due time: a later seq never jumps ahead of an earlier step due at the same moment
    int32 At = Steps.Num();
    while (At > 0 && Steps[At - 1].DueMs > Step.DueMs) --At;
    Steps.Insert(MoveTemp(Step), At);
  };
  if (bSnapped || StepMs <= 0.0 || InSteps < 1) {
    Add({FighterId, Seq, StartMs, -1, FMath::Max(InSteps, 1)});
    return;
  }
  for (int32 Edge = 0; Edge < InSteps; ++Edge) {
    Add({FighterId, Seq, StartMs + static_cast<int64>(FMath::RoundToDouble(StepMs * Edge)), Edge, InSteps});
  }
}

void FS08CueSound::TakeDueSteps(int64 NowMs, TArray<FS08StepSound>& OutDue) {
  int32 Count = 0;
  while (Count < Steps.Num() && Steps[Count].DueMs <= NowMs) ++Count;
  if (Count == 0) return;
  OutDue.Append(Steps.GetData(), Count);
  Steps.RemoveAt(0, Count);
}

int32 FS08CueSound::DropSteps(int64 NowMs, const TCHAR* Reason, TArray<FString>& OutLines, const FString& FighterId) {
  TMap<int32, int32> BySeq;
  TArray<int32> Order;
  int32 Dropped = 0;
  for (int32 I = 0; I < Steps.Num();) {
    if (!FighterId.IsEmpty() && Steps[I].FighterId != FighterId) {
      ++I;
      continue;
    }
    if (!BySeq.Contains(Steps[I].Seq)) Order.Add(Steps[I].Seq);
    ++BySeq.FindOrAdd(Steps[I].Seq);
    Steps.RemoveAt(I);
    ++Dropped;
  }
  for (const int32 Seq : Order) {
    OutLines.Add(FString::Printf(TEXT("CUE sound drop point=step seq=%d fighter=%s t=%lld count=%d reason=%s"), Seq,
                                 FighterId.IsEmpty() ? TEXT("*") : *FighterId, static_cast<long long>(NowMs),
                                 BySeq[Seq], Reason));
  }
  return Dropped;
}

// DE-032 + AU-S4: the sound of the CUE sync points (CUE-DISPATCHER.md §3.2) - see S08CueSound.h.
#include "S08CueSound.h"

namespace {
FS08SoundRow MakeRow(const TCHAR* CueId, const TCHAR* SoundClass, int32 Priority, int32 RetriggerMs,
                     const TCHAR* BankId) {
  FS08SoundRow Row;
  Row.CueId = CueId;
  Row.SoundClass = SoundClass;
  Row.Priority = Priority;
  Row.RetriggerMs = RetriggerMs;
  Row.BankId = BankId;
  const TArray<FString>* Variants = S08AudioBank::Find(Row.BankId);
  Row.SoundPath = Variants && Variants->Num() ? (*Variants)[0] : FString();  // cue-table sfx.sound
  return Row;
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
  // class / priority / retrigger: cue-table.json sfx; bank: the default sound of the cue (02 §4, registry 03).
  static const TArray<FS08SoundRow> Rows = {
      MakeRow(TEXT("CUE-002"), TEXT("UI"), 2, 0, TEXT("UI-SELECT")),             // ui: own figure picked
      MakeRow(TEXT("CUE-003"), TEXT("UI"), 1, 0, TEXT("UI-CONFIRM")),            // ui: a choice accepted / HUD press
      MakeRow(TEXT("CUE-004"), TEXT("UI"), 1, 300, TEXT("UI-REJECT")),           // ui: refused, at most once in 300 ms
      MakeRow(TEXT("CUE-005"), TEXT("SFX"), 2, 0, TEXT("CRD-DRAW")),             // cue: card drawn
      MakeRow(TEXT("CUE-006"), TEXT("SFX"), 1, 0, TEXT("CRD-PLAY")),             // cue: card played (schemes: CRD-SCHEME)
      MakeRow(TEXT("CUE-007"), TEXT("SFX"), 3, 0, TEXT("BRD-STEP")),             // step: one per edge
      MakeRow(TEXT("CUE-008"), TEXT("SFX"), 1, 0, TEXT("CMB-ATTACK-DECLARE")),   // cue: attack declared
      MakeRow(TEXT("CUE-009"), TEXT("SFX"), 2, 0, TEXT("CMB-DEFENSE-PLAYED")),   // cue: defense played / no defense
      MakeRow(TEXT("CUE-010"), TEXT("SFX"), 1, 0, TEXT("CRD-FLIP")),             // cue: reveal flips, slam, effect lines
      MakeRow(TEXT("CUE-011"), TEXT("SFX"), 1, 0, TEXT("CMB-HIT-BLADE")),        // hit: the contact frame (hit type)
      MakeRow(TEXT("CUE-012"), TEXT("SFX"), 2, 0, TEXT("CMB-HEAL")),             // cue: healed
      MakeRow(TEXT("CUE-013"), TEXT("SFX"), 1, 0, TEXT("DTH-TEMPLATE")),         // cue: death (per character)
      MakeRow(TEXT("CUE-014"), TEXT("SFX"), 1, 0, TEXT("FX-ARTHUR-BOOST")),      // cue: hero ability
      MakeRow(TEXT("CUE-015"), TEXT("UI"), 2, 0, TEXT("UI-TURN-CHIME")),         // turn: own turn only
      MakeRow(TEXT("CUE-016"), TEXT("Music"), 1, 0, TEXT("STG-WIN")),            // result sting (per hero, outcome)
      MakeRow(TEXT("CUE-017"), TEXT("UI"), 1, 5000, TEXT("UI-NET-LOST")),        // cue: connection lost
      MakeRow(TEXT("CUE-018"), TEXT("UI"), 2, 0, TEXT("UI-NET-BACK")),           // cue: connection back
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
    case ES08SoundPoint::Cue:
      return TEXT("cue");
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
      TEXT("CUE audio master=%d master_mute=%d ambience=%d ambience_mute=%d gain_master=%s gain_ambience=%s music=%d "
           "sfx=%d ui=%d vo=%d subtitles=%d t=%lld applied=%s"),
      FMath::Clamp(Audio.MasterPercent, 0, 100), Audio.bMasterMuted ? 1 : 0, FMath::Clamp(Audio.AmbiencePercent, 0, 100),
      Audio.bAmbienceMuted ? 1 : 0, *GainToken(Audio.MasterGain()), *GainToken(Audio.AmbienceGain()),
      FMath::Clamp(Audio.MusicPercent, 0, 100), FMath::Clamp(Audio.SfxPercent, 0, 100),
      FMath::Clamp(Audio.UiPercent, 0, 100), FMath::Clamp(Audio.VoPercent, 0, 100), Audio.bSubtitles ? 1 : 0,
      static_cast<long long>(TMs), bStart ? TEXT("start") : TEXT("change")));
  return true;
}

float FS08CueSound::ClassGain(const FString& SoundClass) const { return Audio.BusGain(SoundClass); }

float FS08CueSound::EffectiveGain(const FString& SoundClass) const {
  return Audio.MasterGain() * Audio.BusGain(SoundClass);
}

FString FS08CueSound::PickVariant(const FString& BankId) {
  const TArray<FString>* Variants = S08AudioBank::Find(BankId);
  return Variants ? Bag.Pick(BankId, *Variants, Rng) : FString();
}

FString FS08CueSound::Line(const FS08SoundRequest& Request, const FS08SoundRow& Row, int64 NowMs, const FString& Sound,
                           float Gain, ES08SoundResult Result, const FString& BankId, const TCHAR* Reason) const {
  FString Out = FString::Printf(
      TEXT("CUE sound id=%s point=%s subject=%s seq=%s t=%lld event_t=%lld dt=%lld class=%s sound=%s gain=%s result=%s"),
      *Row.CueId, S08SoundRows::PointName(Request.Point), Request.Subject.IsEmpty() ? TEXT("-") : *Request.Subject,
      Request.Seq < 0 ? TEXT("-") : *FString::FromInt(Request.Seq), static_cast<long long>(NowMs),
      static_cast<long long>(Request.EventMs), static_cast<long long>(NowMs - Request.EventMs), *Row.SoundClass,
      *Sound, *GainToken(Gain), ResultName(Result));
  if (!BankId.IsEmpty() && BankId != Row.BankId) Out += FString::Printf(TEXT(" bank=%s"), *BankId);
  if (Request.Point == ES08SoundPoint::Turn) Out += Request.bOwnTurn ? TEXT(" turn=own") : TEXT(" turn=opp");
  if (Request.Point == ES08SoundPoint::Step) {
    Out += Request.Edge < 0 ? FString(TEXT(" edge=snap")) : FString::Printf(TEXT(" edge=%d/%d"), Request.Edge + 1,
                                                                          Request.Edges);
  }
  if (Request.DueMs >= 0) Out += FString::Printf(TEXT(" due=%lld"), static_cast<long long>(Request.DueMs));
  if (Reason) Out += FString::Printf(TEXT(" reason=%s"), Reason);
  return Out;
}

FS08SoundDecision FS08CueSound::Play(const FS08SoundRequest& Request, int64 NowMs, TArray<FString>& OutLines) {
  FS08SoundDecision Out;
  const FS08SoundRow* Row = S08SoundRows::Find(Request.CueId);
  if (!Row) {
    Out.Result = ES08SoundResult::Silent;
    return Out;
  }
  const FString BankId = Request.BankId.IsEmpty() ? Row->BankId : Request.BankId;
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
    const FString Path = PickVariant(BankId);
    FString Name;
    if (!Path.IsEmpty()) Name = AssetResolver ? AssetResolver(Path) : S08SoundRows::ShortName(Path);
    // D10: no asset - a fallback show, the line stays and nothing plays (no error)
    Sound = Name.IsEmpty() ? FString(TEXT("missing")) : Name;
    Out.Result = Name.IsEmpty() ? ES08SoundResult::Fallback : ES08SoundResult::Played;
    Out.SoundPath = Name.IsEmpty() ? FString() : Path;
    LastPlayed.Add(Row->CueId, NowMs);
  }
  OutLines.Add(Line(Request, *Row, NowMs, Sound, Out.Gain, Out.Result, BankId, Reason));
  return Out;
}

void FS08CueSound::Grouped(const FS08SoundRequest& Request, int64 NowMs, TArray<FString>& OutLines) {
  const FS08SoundRow* Row = S08SoundRows::Find(Request.CueId);
  if (!Row) return;
  OutLines.Add(Line(Request, *Row, NowMs, TEXT("none"), EffectiveGain(Row->SoundClass), ES08SoundResult::Silent,
                    Request.BankId, TEXT("grouped")));
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

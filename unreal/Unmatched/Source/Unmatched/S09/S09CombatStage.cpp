// DE-018: combat staging timeline - see S09CombatStage.h.
#include "S09CombatStage.h"

#include "../S08/S08CueDispatcher.h"

namespace {
const TCHAR* const RevealCue = TEXT("CUE-010");
const TCHAR* const DamageCue = TEXT("CUE-011");
const TCHAR* const SceneSubject = TEXT("scene");

/** The fixed boundary order of one staging (derived from the input). */
enum class EBoundary : uint8 { Read, Effect, Slam, SlamEnd, Pause, Contact, Minus, Hp, Fall, End };
struct FBoundary {
  EBoundary Kind;
  int32 Index;
};
TArray<FBoundary> BoundaryOrder(const FS09CombatStageInput& In) {
  TArray<FBoundary> Out;
  if (In.bHasEffectText) Out.Add({EBoundary::Read, 0});
  for (int32 I = 0; I < In.EffectLines; ++I) Out.Add({EBoundary::Effect, I});
  Out.Add({EBoundary::Slam, 0});
  Out.Add({EBoundary::SlamEnd, 0});
  Out.Add({EBoundary::Pause, 0});
  Out.Add({EBoundary::Contact, 0});
  if (In.Damage > 0 && !In.bDamageShown) {
    Out.Add({EBoundary::Minus, 0});
    Out.Add({EBoundary::Hp, 0});
    if (In.bLethal) Out.Add({EBoundary::Fall, 0});
  }
  Out.Add({EBoundary::End, 0});
  return Out;
}
}  // namespace

const TCHAR* S09CombatEventName(ES09CombatEvent Event) {
  switch (Event) {
    case ES09CombatEvent::Lunge: return TEXT("lunge");
    case ES09CombatEvent::HitReact: return TEXT("hit");
    case ES09CombatEvent::Minus: return TEXT("minus");
    case ES09CombatEvent::Hp: return TEXT("hp");
    case ES09CombatEvent::Fall: return TEXT("fall");
    default: return TEXT("end");
  }
}

void FS09CombatHold::Apply(TArray<FS08BoardFighter>& Fighters, bool bBoardView) const {
  if (!IsSet()) return;
  for (FS08BoardFighter& Fighter : Fighters) {
    if (Fighter.Id != FighterId) continue;
    // The fighter as it stood before the blow: HP, cell and defeat flag (a lethal snapshot clears the cell).
    if (!(bHpHeld || (bBoardView && bAliveHeld))) return;
    Fighter.Health = FMath::Max(HeldHealth, Fighter.Health);
    if (HeldX >= 0 && !Fighter.IsAlive()) {
      Fighter.X = HeldX;
      Fighter.Y = HeldY;
    }
    if (Fighter.Health > 0) Fighter.bDefeated = false;
    return;
  }
}

int32 FS09CombatStage::Scaled(int32 Ms) const {
  return Input.SpeedMul <= 0.0f ? 0 : FMath::RoundToInt(Ms * Input.SpeedMul);
}

int32 FS09CombatStage::MinusLifeMs() const {
  // 01 F-04: 900 x speed; "none" (instant animations) keeps the number readable at the fast 450.
  const float Mul = Input.SpeedMul <= 0.0f ? 0.5f : Input.SpeedMul;
  return FMath::RoundToInt(FS09CombatTiming::MinusLifeMs * Mul);
}

int32 FS09CombatStage::HoldTotalMs() const {
  int32 Total = ReadMs;
  for (const int32 Ms : EffectMs) Total += Ms;
  return Total;
}

void FS09CombatStage::Reschedule() {
  FlipEndMs = StartMs + FlipLenMs;
  SlamStartMs = FlipEndMs + HoldTotalMs();
  SlamEndMs = SlamStartMs + SlamLenMs;
  PauseEndMs = SlamEndMs + PauseMs;
  ContactAtMs = PauseEndMs + ContactOffsetMs;
  int32 Tail = HitWindowMs;
  if (Input.Damage > 0 && !Input.bDamageShown) {
    Tail = FMath::Max(Tail, FS09CombatTiming::HpDelayMs);
    if (Input.bLethal) Tail = FMath::Max(Tail, FS09CombatTiming::FallMs);
  }
  EndMs = ContactAtMs + Tail;
}

int64 FS09CombatStage::BoundaryTime(uint8 KindByte, int32 Index) const {
  switch (static_cast<EBoundary>(KindByte)) {
    case EBoundary::Read: return FlipEndMs + ReadMs;
    case EBoundary::Effect: {
      int64 T = FlipEndMs + ReadMs;
      for (int32 I = 0; I <= Index && I < EffectMs.Num(); ++I) T += EffectMs[I];
      return T;
    }
    case EBoundary::Slam: return SlamStartMs;
    case EBoundary::SlamEnd: return SlamEndMs;
    case EBoundary::Pause: return PauseEndMs;
    case EBoundary::Contact: return ContactAtMs;
    case EBoundary::Minus: return ContactAtMs + FS09CombatTiming::MinusDelayMs;
    case EBoundary::Hp: return ContactAtMs + FS09CombatTiming::HpDelayMs;
    case EBoundary::Fall: return ContactAtMs + FS09CombatTiming::FallMs;
    default: return EndMs;
  }
}

FString FS09CombatStage::Prefix(const TCHAR* Stage, int64 TMs) const {
  return FString::Printf(TEXT("CUE combat seq=%d stage=%s t=%lld"), Input.Seq, Stage, static_cast<long long>(TMs));
}

void FS09CombatStage::Release(ES09CombatEvent Type, int64 AtMs, TArray<FS09CombatStageEvent>& OutEvents) {
  if (Type == ES09CombatEvent::Hp) Hold.bHpHeld = false;
  if (Type == ES09CombatEvent::Fall) Hold.bAliveHeld = false;
  if (Type == ES09CombatEvent::End) Hold.Reset();
  FS09CombatStageEvent Event;
  Event.Type = Type;
  Event.AtMs = AtMs;
  OutEvents.Add(Event);
}

namespace {
/** CUE-011 from the contact frame: 900 x speed, never shorter than the hit tint, never an input block over 1 s. */
int32 HitWindowAt(float SpeedMul, int32 TintMs) {
  const float Mul = SpeedMul <= 0.0f ? 0.5f : SpeedMul;
  return FMath::Clamp(FMath::Max(FMath::RoundToInt(FS09CombatTiming::HitWindowMs * Mul), TintMs), 0,
                      FS09CombatTiming::MaxBlockingMs);
}
}  // namespace

bool FS09CombatStage::Start(const FS09CombatStageInput& InInput, int64 NowMs, FS08CueDispatcher& Cues,
                            TArray<FString>& OutLines, TArray<FS09CombatStageEvent>& OutEvents) {
  if (InInput.Seq < 0 || InInput.AttackerId.IsEmpty() || InInput.TargetId.IsEmpty()) return false;
  if (InInput.Seq == LastStartedSeq) return false;
  if (IsActive()) Cut(NowMs, TEXT("replace"), Cues, OutLines, OutEvents);
  LastStartedSeq = InInput.Seq;
  Input = InInput;
  Input.Damage = FMath::Max(0, Input.Damage);
  Input.EffectLines = FMath::Max(0, Input.EffectLines);
  Phase = ES09CombatStagePhase::Flip;
  bAllHoldsSkipped = false;
  bSkipped = false;
  NextBoundary = 0;
  // CUE-010: flip + slam at the animation speed (reduced motion shortens the shown length, D11).
  const int32 RevealShown = Cues.ShowDurationMs(RevealCue, Scaled(FS09CombatTiming::RevealMs));
  FlipLenMs = FMath::RoundToInt(static_cast<float>(RevealShown) * FS09CombatTiming::FlipMs /
                                FS09CombatTiming::RevealMs);
  SlamLenMs = RevealShown - FlipLenMs;
  DefenseFlipMs = FMath::Min(Scaled(FS09CombatTiming::DefenseFlipDelayMs), FlipLenMs);
  ContactOffsetMs = Scaled(FMath::Max(0, Input.ContactMs));
  HitWindowMs = Cues.ShowDurationMs(DamageCue, HitWindowAt(Input.SpeedMul, GetHitTintMs()));
  // Holds (never scaled, 01 F-01): read only with effect text, one step per fired line, the pause "score".
  ReadMs = Input.bHasEffectText ? FS09CombatTiming::ReadHoldMs : 0;
  bReadSkipped = false;
  EffectMs.Init(Scaled(FS09CombatTiming::EffectHighlightMs) +
                    (FS09CombatTiming::EffectStepMs - FS09CombatTiming::EffectHighlightMs),
                Input.EffectLines);
  EffectSkipped.Init(false, Input.EffectLines);
  PauseMs = FS09CombatTiming::SlamToLungeMs;
  bPauseSkipped = false;
  StartMs = NowMs;
  Reschedule();
  // The target's presentation waits for the contact frame (the snapshot already applied the result).
  Hold.Reset();
  if (Input.Damage > 0 && !Input.bDamageShown && Input.HpBefore >= 0) {
    Hold.FighterId = Input.TargetId;
    Hold.HeldHealth = Input.HpBefore;
    Hold.HeldX = Input.TargetX;
    Hold.HeldY = Input.TargetY;
    Hold.bHpHeld = true;
    Hold.bAliveHeld = Input.bLethal;
  }
  Cues.Advance(StartMs, OutLines);  // shows that ended before the reveal write their done first (D1)
  const FS09CombatReveal& R = Input.Reveal;
  OutLines.Add(Prefix(TEXT("start"), StartMs) +
               FString::Printf(TEXT(" attacker=%s target=%s text=%d lines=%d damage=%d lethal=%d shown=%d speed=%.2f "
                                    "flip=%d contact=%d src=%s a=%d d=%d outcome=%s"),
                               *Input.AttackerId, *Input.TargetId, Input.bHasEffectText ? 1 : 0, Input.EffectLines,
                               Input.Damage, Input.bLethal ? 1 : 0, Input.bDamageShown ? 1 : 0, Input.SpeedMul,
                               FlipLenMs, ContactOffsetMs, *Input.ContactSource, R.AttackValue, R.DefenseValue,
                               AttackerWins() ? TEXT("win") : TEXT("hold")));
  Cues.Feed(RevealCue, SceneSubject, Input.Seq, StartMs, OutLines, HoldTotalMs(), Scaled(FS09CombatTiming::RevealMs));
  Tick(NowMs, Cues, OutLines, OutEvents);
  return true;
}

void FS09CombatStage::Tick(int64 NowMs, FS08CueDispatcher& Cues, TArray<FString>& OutLines,
                           TArray<FS09CombatStageEvent>& OutEvents) {
  if (!IsActive()) return;
  const TArray<FBoundary> Order = BoundaryOrder(Input);
  const bool bPresentDamage = Input.Damage > 0 && !Input.bDamageShown;
  while (NextBoundary < Order.Num()) {
    const FBoundary B = Order[NextBoundary];
    const int64 T = BoundaryTime(static_cast<uint8>(B.Kind), B.Index);
    if (T > NowMs) break;
    ++NextBoundary;
    Cues.Advance(T, OutLines);
    switch (B.Kind) {
      case EBoundary::Read:
        Phase = ES09CombatStagePhase::Read;
        OutLines.Add(Prefix(TEXT("read"), T) +
                     FString::Printf(TEXT(" ms=%d skipped=%d"), ReadMs, bReadSkipped ? 1 : 0));
        break;
      case EBoundary::Effect:
        Phase = ES09CombatStagePhase::Effects;
        OutLines.Add(Prefix(TEXT("effect"), T) + FString::Printf(TEXT(" i=%d ms=%d skipped=%d"), B.Index + 1,
                                                                 EffectMs[B.Index], EffectSkipped[B.Index] ? 1 : 0));
        break;
      case EBoundary::Slam: {
        Phase = ES09CombatStagePhase::Slam;
        const FS09CombatReveal& R = Input.Reveal;
        OutLines.Add(Prefix(TEXT("slam"), T) + FString::Printf(TEXT(" a=%d d=%d outcome=%s"), R.AttackValue,
                                                               R.DefenseValue,
                                                               AttackerWins() ? TEXT("win") : TEXT("hold")));
        break;
      }
      case EBoundary::SlamEnd:
        // The CUE-010 done line came out of Advance above (its end = slam end, the holds included).
        Phase = ES09CombatStagePhase::Pause;
        break;
      case EBoundary::Pause:
        Phase = ES09CombatStagePhase::Lunge;
        OutLines.Add(Prefix(TEXT("pause"), T) +
                     FString::Printf(TEXT(" ms=%d skipped=%d"), PauseMs, bPauseSkipped ? 1 : 0));
        OutLines.Add(Prefix(TEXT("lunge"), T) + FString::Printf(TEXT(" attacker=%s"), *Input.AttackerId));
        Release(ES09CombatEvent::Lunge, T, OutEvents);
        break;
      case EBoundary::Contact:
        Phase = ES09CombatStagePhase::Hit;
        OutLines.Add(Prefix(TEXT("contact"), T) + FString::Printf(TEXT(" offset=%d window=%d src=%s"),
                                                                  ContactOffsetMs, HitWindowMs, *Input.ContactSource));
        if (bPresentDamage) {
          // CUE-011 runs from the contact frame (01 "Резолюция" п. 4); LungeAttack was its intro.
          Cues.Feed(DamageCue, Input.TargetId, Input.Seq, T, OutLines, 0,
                    HitWindowAt(Input.SpeedMul, GetHitTintMs()));
          OutLines.Add(Prefix(TEXT("hit"), T) +
                       FString::Printf(TEXT(" target=%s tint=%d"), *Input.TargetId, GetHitTintMs()));
          Release(ES09CombatEvent::HitReact, T, OutEvents);
        }
        break;
      case EBoundary::Minus:
        OutLines.Add(Prefix(TEXT("minus"), T) +
                     FString::Printf(TEXT(" amount=%d life=%d"), Input.Damage, MinusLifeMs()));
        Release(ES09CombatEvent::Minus, T, OutEvents);
        break;
      case EBoundary::Hp:
        OutLines.Add(Prefix(TEXT("hp"), T) + FString::Printf(TEXT(" from=%d to=%d"), Input.HpBefore, Input.HpAfter));
        Release(ES09CombatEvent::Hp, T, OutEvents);
        break;
      case EBoundary::Fall:
        OutLines.Add(Prefix(TEXT("fall"), T) + FString::Printf(TEXT(" target=%s"), *Input.TargetId));
        Release(ES09CombatEvent::Fall, T, OutEvents);
        break;
      case EBoundary::End:
        OutLines.Add(Prefix(TEXT("end"), T) + FString::Printf(TEXT(" total=%lld skipped=%d cut=0"),
                                                              static_cast<long long>(TotalMs()), bSkipped ? 1 : 0));
        Phase = ES09CombatStagePhase::Done;
        Release(ES09CombatEvent::End, T, OutEvents);
        break;
    }
  }
}

bool FS09CombatStage::Skip(int64 NowMs, const TCHAR* Source, FS08CueDispatcher& Cues, TArray<FString>& OutLines,
                           TArray<FS09CombatStageEvent>& OutEvents) {
  Tick(NowMs, Cues, OutLines, OutEvents);
  if (!IsSkippable(NowMs)) return false;
  const bool bRevealActive = NowMs < SlamEndMs;
  const int64 ReadEnd = FlipEndMs + ReadMs;
  if (NowMs < ReadEnd || NowMs < FlipEndMs) {
    // In the flip (its animation plays on) or in the read hold: the read ends now, no effect line plays.
    if (Input.bHasEffectText) {
      ReadMs = NowMs < FlipEndMs ? 0 : static_cast<int32>(NowMs - FlipEndMs);
      bReadSkipped = true;
    }
    for (int32 I = 0; I < EffectMs.Num(); ++I) {
      EffectMs[I] = 0;
      EffectSkipped[I] = true;
    }
  } else if (NowMs < SlamStartMs) {
    // In the effect lines: the finished lines stay, the current one ends now, the rest are dropped.
    int64 Cursor = ReadEnd;
    for (int32 I = 0; I < EffectMs.Num(); ++I) {
      const int64 LineEnd = Cursor + EffectMs[I];
      if (NowMs >= LineEnd) {
        Cursor = LineEnd;
        continue;
      }
      EffectMs[I] = static_cast<int32>(FMath::Max<int64>(0, NowMs - Cursor));
      EffectSkipped[I] = true;
      Cursor = NowMs;
    }
  }
  // The pause "score": dropped when it has not started, cut now when it runs.
  PauseMs = NowMs < SlamEndMs ? 0 : static_cast<int32>(NowMs - SlamEndMs);
  bPauseSkipped = true;
  bAllHoldsSkipped = true;
  bSkipped = true;
  Reschedule();
  if (bRevealActive) Cues.SetHold(RevealCue, SceneSubject, Input.Seq, HoldTotalMs());
  OutLines.Add(Prefix(TEXT("skip"), NowMs) + FString::Printf(TEXT(" src=%s"), Source));
  Tick(NowMs, Cues, OutLines, OutEvents);
  return true;
}

void FS09CombatStage::Cut(int64 NowMs, const TCHAR* Reason, FS08CueDispatcher& Cues, TArray<FString>& OutLines,
                          TArray<FS09CombatStageEvent>& OutEvents) {
  if (!IsActive()) return;
  Tick(NowMs, Cues, OutLines, OutEvents);
  if (!IsActive()) return;
  // The presentation catches up with the applied snapshot: the held HP and figure are released now; the lunge, the
  // hit and the number of a cut staging are not played any more.
  const TArray<FBoundary> Order = BoundaryOrder(Input);
  for (int32 I = NextBoundary; I < Order.Num(); ++I) {
    if (Order[I].Kind == EBoundary::Hp) Release(ES09CombatEvent::Hp, NowMs, OutEvents);
    if (Order[I].Kind == EBoundary::Fall) Release(ES09CombatEvent::Fall, NowMs, OutEvents);
  }
  NextBoundary = Order.Num();
  const FString CutName(Reason);
  const TCHAR* DispatcherCut = CutName == TEXT("replace") || CutName == TEXT("reconnect") ? Reason : TEXT("jump");
  Cues.Cut(RevealCue, SceneSubject, Input.Seq, NowMs, DispatcherCut, OutLines);
  Cues.Cut(DamageCue, Input.TargetId, Input.Seq, NowMs, DispatcherCut, OutLines);
  EndMs = NowMs;
  OutLines.Add(Prefix(TEXT("end"), NowMs) + FString::Printf(TEXT(" total=%lld skipped=%d cut=%s"),
                                                            static_cast<long long>(TotalMs()), bSkipped ? 1 : 0,
                                                            Reason));
  Phase = ES09CombatStagePhase::Done;
  Release(ES09CombatEvent::End, NowMs, OutEvents);
}

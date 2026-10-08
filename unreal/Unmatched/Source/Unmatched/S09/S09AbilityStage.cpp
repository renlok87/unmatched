// VS-6 F3 FX-30: the world-free staging of Medusa's gaze - see S09AbilityStage.h.
#include "S09AbilityStage.h"

#include "../S08/S08CueDispatcher.h"

namespace {
const TCHAR* const AbilityCue = TEXT("CUE-014");
const TCHAR* const DamageCue = TEXT("CUE-011");

enum class EBoundary : uint8 { Contact, Minus, Hp, Fall, End };
}  // namespace

const TCHAR* S09AbilityEventName(ES09AbilityEvent Event) {
  switch (Event) {
    case ES09AbilityEvent::Vortex: return TEXT("vortex");
    case ES09AbilityEvent::Contact: return TEXT("contact");
    case ES09AbilityEvent::Minus: return TEXT("minus");
    case ES09AbilityEvent::Hp: return TEXT("hp");
    case ES09AbilityEvent::Fall: return TEXT("fall");
    default: return TEXT("end");
  }
}

FString FS09AbilityStage::Prefix(const TCHAR* Stage, int64 TMs) const {
  return FString::Printf(TEXT("CUE ability seq=%d stage=%s t=%lld hero=%s target=%s"), Input.Seq, Stage,
                         static_cast<long long>(TMs), *Input.HeroKey.ToLower(), *Input.TargetId);
}

void FS09AbilityStage::Release(ES09AbilityEvent Type, int64 AtMs, TArray<FS09AbilityStageEvent>& OutEvents) {
  if (Type == ES09AbilityEvent::Hp) Hold.bHpHeld = false;
  if (Type == ES09AbilityEvent::Fall) Hold.bAliveHeld = false;
  if (Type == ES09AbilityEvent::End) Hold.Reset();
  FS09AbilityStageEvent Event;
  Event.Type = Type;
  Event.AtMs = AtMs;
  OutEvents.Add(Event);
}

bool FS09AbilityStage::Start(const FS09AbilityStageInput& InInput, int64 NowMs, FS08CueDispatcher& Cues,
                             TArray<FString>& OutLines, TArray<FS09AbilityStageEvent>& OutEvents) {
  if (InInput.Seq < 0 || InInput.FighterId.IsEmpty() || InInput.TargetId.IsEmpty()) return false;
  if (InInput.Seq == LastStartedSeq) return false;
  if (bActive) Cut(NowMs, TEXT("replace"), Cues, OutLines, OutEvents);
  LastStartedSeq = InInput.Seq;
  Input = InInput;
  Input.Damage = FMath::Max(0, Input.Damage);
  bActive = true;
  NextBoundary = 0;
  StartMs = NowMs;
  ContactAtMs = StartMs + (Input.bReducedMotion ? FS09AbilityTiming::ReducedContactMs : FS09AbilityTiming::ContactMs);
  const int32 Show = Cues.ShowDurationMs(AbilityCue);
  int64 Tail = ContactAtMs + FS09AbilityTiming::HpDelayMs;
  if (Input.bLethal && Input.Damage > 0) Tail = FMath::Max<int64>(Tail, ContactAtMs + FS09AbilityTiming::FallMs);
  EndMs = FMath::Max<int64>(StartMs + Show, Tail);
  Hold.Reset();
  if (Input.Damage > 0 && Input.HpBefore >= 0) {
    Hold.FighterId = Input.TargetId;
    Hold.HeldHealth = Input.HpBefore;
    Hold.HeldX = Input.TargetX;
    Hold.HeldY = Input.TargetY;
    Hold.bHpHeld = true;
    Hold.bAliveHeld = Input.bLethal;
  }
  Cues.Advance(StartMs, OutLines);
  OutLines.Add(FString::Printf(TEXT("CUE ability seq=%d stage=start t=%lld hero=%s fighter=%s target=%s damage=%d "
                                    "lethal=%d reduced=%d"),
                               Input.Seq, static_cast<long long>(StartMs), *Input.HeroKey.ToLower(), *Input.FighterId,
                               *Input.TargetId, Input.Damage, Input.bLethal ? 1 : 0, Input.bReducedMotion ? 1 : 0));
  Cues.Feed(AbilityCue, Input.FighterId, Input.Seq, StartMs, OutLines);
  if (!Input.bReducedMotion) Release(ES09AbilityEvent::Vortex, StartMs, OutEvents);
  Tick(NowMs, Cues, OutLines, OutEvents);
  return true;
}

void FS09AbilityStage::Tick(int64 NowMs, FS08CueDispatcher& Cues, TArray<FString>& OutLines,
                            TArray<FS09AbilityStageEvent>& OutEvents) {
  if (!bActive) return;
  TArray<TPair<EBoundary, int64>> Order = {
      {EBoundary::Contact, ContactAtMs},
      {EBoundary::Minus, ContactAtMs + FS09AbilityTiming::MinusDelayMs},
      {EBoundary::Hp, ContactAtMs + FS09AbilityTiming::HpDelayMs}};
  if (Input.bLethal && Input.Damage > 0) Order.Add({EBoundary::Fall, ContactAtMs + FS09AbilityTiming::FallMs});
  Order.Add({EBoundary::End, EndMs});
  while (NextBoundary < Order.Num()) {
    const EBoundary B = Order[NextBoundary].Key;
    const int64 T = Order[NextBoundary].Value;
    if (T > NowMs) break;
    ++NextBoundary;
    Cues.Advance(T, OutLines);
    switch (B) {
      case EBoundary::Contact:
        OutLines.Add(Prefix(TEXT("contact"), T) + FString::Printf(TEXT(" tint=%d"), GetHitTintMs()));
        if (Input.Damage > 0) {
          // CUE-011 of the target from the contact equivalent, staged at the ability's seq (no D3)
          Cues.Feed(DamageCue, Input.TargetId, Input.Seq, T, OutLines, 0, -1, /*bStaged=*/true);
        }
        Release(ES09AbilityEvent::Contact, T, OutEvents);
        break;
      case EBoundary::Minus:
        OutLines.Add(Prefix(TEXT("minus"), T) + FString::Printf(TEXT(" amount=%d"), Input.Damage));
        Release(ES09AbilityEvent::Minus, T, OutEvents);
        break;
      case EBoundary::Hp:
        OutLines.Add(Prefix(TEXT("hp"), T) + FString::Printf(TEXT(" from=%d to=%d"), Input.HpBefore, Input.HpAfter));
        Release(ES09AbilityEvent::Hp, T, OutEvents);
        break;
      case EBoundary::Fall:
        OutLines.Add(Prefix(TEXT("fall"), T));
        Release(ES09AbilityEvent::Fall, T, OutEvents);
        break;
      case EBoundary::End:
        OutLines.Add(Prefix(TEXT("end"), T) + TEXT(" cut=0"));
        bActive = false;
        Release(ES09AbilityEvent::End, T, OutEvents);
        break;
    }
  }
}

void FS09AbilityStage::Cut(int64 NowMs, const TCHAR* Reason, FS08CueDispatcher& Cues, TArray<FString>& OutLines,
                           TArray<FS09AbilityStageEvent>& OutEvents) {
  if (!bActive) return;
  Tick(NowMs, Cues, OutLines, OutEvents);
  if (!bActive) return;
  // The presentation catches up with the applied snapshot: the held HP and figure go now, the hit is not played.
  if (Hold.bHpHeld) Release(ES09AbilityEvent::Hp, NowMs, OutEvents);
  if (Hold.bAliveHeld) Release(ES09AbilityEvent::Fall, NowMs, OutEvents);
  Cues.Cut(AbilityCue, Input.FighterId, Input.Seq, NowMs, TEXT("jump"), OutLines);
  Cues.Cut(DamageCue, Input.TargetId, Input.Seq, NowMs, TEXT("jump"), OutLines);
  EndMs = NowMs;
  OutLines.Add(Prefix(TEXT("end"), NowMs) + FString::Printf(TEXT(" cut=%s"), Reason));
  bActive = false;
  Release(ES09AbilityEvent::End, NowMs, OutEvents);
}

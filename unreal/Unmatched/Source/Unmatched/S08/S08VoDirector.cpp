// AU-S4: hero lines - see S08VoDirector.h.
#include "S08VoDirector.h"

FS08VoDirector::FRule FS08VoDirector::RuleFor(const FString& Speaker, const FString& Event) {
  // 02-audio-design §3.2 (chance, cooldown, priority); the harpies' cries per 04 §5.
  FRule R;
  auto Set = [&R](float Chance, int32 CooldownMs, int32 Priority, bool bOnce = false, bool bCombat = false) {
    R.Chance = Chance;
    R.CooldownMs = CooldownMs;
    R.Priority = Priority;
    R.bOnce = bOnce;
    R.bCombat = bCombat;
  };
  if (Speaker == TEXT("HARPY")) {
    if (Event == TEXT("ATTACK")) Set(0.6f, 10000, 3, false, true);
    else if (Event == TEXT("HURT")) Set(0.6f, 0, 3, false, true);
    else if (Event == TEXT("DEATH")) Set(1.0f, 0, 1);
    else if (Event == TEXT("FRENZY")) Set(0.8f, 0, 2);
    else if (Event == TEXT("ENEMY-DOWN")) Set(0.6f, 0, 2);
    else if (Event == TEXT("RETURN")) Set(1.0f, 0, 2);
    else Set(0.0f, 0, 5);
    return R;
  }
  if (Event == TEXT("SELECT")) Set(1.0f, 0, 2);
  else if (Event == TEXT("MATCH-START")) Set(1.0f, 0, 2);
  else if (Event.StartsWith(TEXT("MATCHUP-"))) Set(1.0f, 0, 2);
  else if (Event == TEXT("TURN-START")) Set(0.25f, 0, 4);
  else if (Event == TEXT("ATTACK")) Set(0.5f, 15000, 3, false, true);
  else if (Event == TEXT("DEFEND")) Set(0.3f, 15000, 4, false, true);
  else if (Event == TEXT("HURT")) Set(0.6f, 6000, 3, false, true);
  else if (Event == TEXT("HURT-BIG")) Set(1.0f, 10000, 2);
  else if (Event == TEXT("LOW-HP")) Set(1.0f, 0, 1, true);
  else if (Event == TEXT("ALLY-DOWN")) Set(1.0f, 10000, 1);
  else if (Event == TEXT("ALLY-LOW")) Set(1.0f, 0, 2, true);
  else if (Event == TEXT("ENEMY-DOWN")) Set(0.6f, 10000, 2);
  else if (Event == TEXT("ABILITY")) Set(Speaker == TEXT("MEDUSA") ? 0.7f : 0.5f, 20000, 3);
  else if (Event.StartsWith(TEXT("CARD-"))) Set(0.8f, 30000, 2);
  else if (Event == TEXT("SCHEME")) Set(0.4f, 30000, 3);
  else if (Event == TEXT("IDLE")) Set(1.0f, 45000, 5);
  else if (Event == TEXT("DEATH")) Set(1.0f, 0, 1);
  else if (Event == TEXT("VICTORY") || Event == TEXT("DEFEAT")) Set(1.0f, 0, 1);
  else Set(0.0f, 0, 5);
  return R;
}

void FS08VoDirector::NewMatch(int32 Seed) {
  Rng.Initialize(Seed);
  Bag.Reset();
  Cooldowns.Reset();
  OnceDone.Reset();
  Recent.Reset();
  LastLineMs = MIN_int64;
  bSpeaking = false;
  CurrentPrio = 99;
}

void FS08VoDirector::Trace(const FS08VoOffer& Offer, const FS08VoDecision& D, TArray<FString>& OutLines) const {
  FString Line = FString::Printf(TEXT("VO event=%s speaker=%s t=%lld result=%s line=%s prio=%d"), *Offer.Event,
                                 *Offer.Speaker, static_cast<long long>(Offer.TMs), D.bPlay ? TEXT("played") : TEXT("skipped"),
                                 D.LineId.IsEmpty() ? TEXT("-") : *D.LineId, D.Priority);
  if (D.bInterrupt) Line += TEXT(" interrupt=1");
  if (!D.Reason.IsEmpty()) Line += FString::Printf(TEXT(" reason=%s"), *D.Reason);
  OutLines.Add(MoveTemp(Line));
}

FS08VoDecision FS08VoDirector::Offer(const FS08VoOffer& In, TArray<FString>& OutLines) {
  FS08VoDecision D;
  const FRule Rule = RuleFor(In.Speaker, In.Event);
  D.Priority = Rule.Priority;
  const FString Key = In.Speaker + TEXT("|") + In.Event;
  auto Skip = [&](const TCHAR* Why) {
    D.bPlay = false;
    D.Reason = Why;
    Trace(In, D, OutLines);
    return D;
  };
  if (Rule.Chance <= 0.0f) return Skip(TEXT("noevent"));
  if (Rule.bOnce && OnceDone.Contains(Key)) return Skip(TEXT("once"));
  if (const int64* Last = Cooldowns.Find(Key); Last && Rule.CooldownMs > 0 && In.TMs - *Last < Rule.CooldownMs) {
    return Skip(TEXT("cooldown"));
  }
  const bool bBusy = IsSpeaking(In.TMs);
  if (bBusy && Rule.Priority >= CurrentPrio) return Skip(TEXT("busy"));
  if (!In.bAnswer && Rule.Priority > 1 && LastLineMs != MIN_int64 && In.TMs - LastLineMs < GapMs) {
    return Skip(TEXT("gap"));
  }
  // the chance: answer 60 %; budget and animation speed halve it
  float Chance = In.bAnswer ? 0.6f : Rule.Chance;
  Recent.RemoveAll([&In](int64 T) { return In.TMs - T > BudgetWindowMs; });
  if (Rule.Priority >= 3 && Recent.Num() > BudgetLines) Chance *= 0.5f;
  if (Rule.bCombat && In.SpeedMul < 0.75f) Chance *= 0.5f;
  if (Chance < 1.0f && Rng.FRand() >= Chance) return Skip(TEXT("chance"));
  // the line
  if (In.Speaker == TEXT("HARPY")) {
    const FString BankId = FString::Printf(TEXT("VO-HARPY-%s-H%d"), *In.Event, FMath::Clamp(In.HarpyIndex, 1, 3));
    const TArray<FString>* Variants = S08AudioBank::Find(BankId);
    if (!Variants || !Variants->Num()) return Skip(TEXT("nolines"));
    D.Path = Bag.Pick(BankId, *Variants, Rng);
    int32 Slash = INDEX_NONE;
    D.LineId = D.Path;
    if (D.LineId.FindLastChar(TEXT('.'), Slash)) D.LineId.RightChopInline(Slash + 1);
  } else {
    TArray<FString> Ids;
    for (const FS08VoLine& L : S08AudioBank::VoLines()) {
      if (L.Fighter == In.Speaker && L.Event == In.Event) Ids.Add(L.Id);
    }
    if (!Ids.Num()) return Skip(TEXT("nolines"));
    D.LineId = Bag.Pick(Key, Ids, Rng);
    if (const FS08VoLine* L = S08AudioBank::FindVoLine(D.LineId)) {
      D.Path = L->Path;
      D.En = L->En;
      D.Ru = L->Ru;
    }
  }
  D.bPlay = true;
  D.bInterrupt = bBusy;
  Cooldowns.Add(Key, In.TMs);
  if (Rule.bOnce) OnceDone.Add(Key);
  Recent.Add(In.TMs);
  LastLineMs = In.TMs;
  bSpeaking = true;
  SpeakingUntilMs = In.TMs + 3000;  // until Started tells the real length
  CurrentPrio = Rule.Priority;
  Trace(In, D, OutLines);
  return D;
}

void FS08VoDirector::Started(int64 TMs, int32 LengthMs) {
  bSpeaking = true;
  SpeakingUntilMs = TMs + FMath::Max(LengthMs, 100);
}

void FS08VoDirector::Finished(int64 TMs) {
  bSpeaking = false;
  CurrentPrio = 99;
}

// DE-019: death by stages and the result gate - see S09DeathStage.h.
#include "S09DeathStage.h"

#include "../S08/S08CueDispatcher.h"

namespace {
const TCHAR* const DeathCue = TEXT("CUE-013");

enum : uint8 { MarkBit = 1, DissolveBit = 2, GoneBit = 4 };

FString Prefix(int32 Seq, const TCHAR* Stage, int64 TMs) {
  return FString::Printf(TEXT("CUE death seq=%d stage=%s t=%lld"), Seq, Stage, static_cast<long long>(TMs));
}
}  // namespace

const TCHAR* S09HeartStateName(ES09HeartState State) {
  switch (State) {
    case ES09HeartState::Dark: return TEXT("dark");
    case ES09HeartState::Crossed: return TEXT("crossed");
    default: return TEXT("alive");
  }
}

const FS09DeathStage::FEntry* FS09DeathStage::Find(const FString& FighterId) const {
  return Entries.FindByPredicate([&FighterId](const FEntry& E) { return E.In.FighterId == FighterId; });
}

bool FS09DeathStage::Begin(const FS09DeathInput& In, int64 NowMs, FS08CueDispatcher& Cues, TArray<FString>& OutLines,
                           bool bCrossGlyph) {
  if (In.FighterId.IsEmpty() || Find(In.FighterId)) return false;
  FEntry E;
  E.In = In;
  E.In.SettleMs = FMath::Max(0, In.SettleMs);
  E.In.StillMs = FMath::Max(0, In.StillMs);
  E.In.DissolveMs = FMath::Max(0, In.DissolveMs);
  if (E.In.DissolveMs == 0) E.In.Style = TEXT("none");
  E.bCross = bCrossGlyph;
  E.FallMs = NowMs;
  E.MarkMs = NowMs + FS09DeathTiming::MarkAfterFallMs;
  E.DissolveMs = NowMs + E.In.SettleMs + E.In.StillMs;
  E.GoneMs = E.DissolveMs + E.In.DissolveMs;
  Cues.Advance(NowMs, OutLines);
  OutLines.Add(Prefix(In.Seq, TEXT("fall"), NowMs) +
               FString::Printf(TEXT(" fighter=%s hero=%d staged=%d settle=%d still=%d dissolve=%d style=%s gone=%lld"),
                               *In.FighterId, In.bHero ? 1 : 0, In.bStaged ? 1 : 0, E.In.SettleMs, E.In.StillMs,
                               E.In.DissolveMs, *E.In.Style, static_cast<long long>(E.GoneMs)));
  // CUE-013 from the fall: DeathSettle (the row's 950 = clip 875 + start), subject = the fallen fighter.
  Cues.Feed(DeathCue, In.FighterId, In.Seq, NowMs, OutLines, 0, -1, In.bStaged);
  Entries.Add(E);
  Tick(NowMs, OutLines);
  return true;
}

void FS09DeathStage::Tick(int64 NowMs, TArray<FString>& OutLines) {
  struct FDue {
    int64 T;
    int32 Entry;
    uint8 Bit;
  };
  TArray<FDue> Due;
  for (int32 I = 0; I < Entries.Num(); ++I) {
    const FEntry& E = Entries[I];
    if (!(E.Emitted & MarkBit) && E.MarkMs <= NowMs) Due.Add({E.MarkMs, I, MarkBit});
    if (!(E.Emitted & DissolveBit) && E.In.DissolveMs > 0 && E.DissolveMs <= NowMs) {
      Due.Add({E.DissolveMs, I, DissolveBit});
    }
    if (!(E.Emitted & GoneBit) && E.GoneMs <= NowMs) Due.Add({E.GoneMs, I, GoneBit});
  }
  // Time order; at one time the dissolve start comes before the gone (a 0 ms dissolve never happens: no line).
  Due.StableSort([](const FDue& A, const FDue& B) { return A.T != B.T ? A.T < B.T : A.Bit < B.Bit; });
  for (const FDue& D : Due) {
    FEntry& E = Entries[D.Entry];
    E.Emitted |= D.Bit;
    if (D.Bit == MarkBit) {
      OutLines.Add(Prefix(E.In.Seq, TEXT("mark"), D.T) +
                   FString::Printf(TEXT(" fighter=%s heart=%s"), *E.In.FighterId,
                                   S09HeartStateName(E.bCross ? ES09HeartState::Crossed : ES09HeartState::Dark)));
    } else if (D.Bit == DissolveBit) {
      OutLines.Add(Prefix(E.In.Seq, TEXT("dissolve"), D.T) +
                   FString::Printf(TEXT(" fighter=%s ms=%d style=%s"), *E.In.FighterId, E.In.DissolveMs, *E.In.Style));
    } else {
      OutLines.Add(Prefix(E.In.Seq, TEXT("gone"), D.T) + FString::Printf(TEXT(" fighter=%s"), *E.In.FighterId));
    }
  }
}

int64 FS09DeathStage::LatestHeroGoneMs() const {
  int64 Latest = -1;
  for (const FEntry& E : Entries) {
    if (E.In.bHero) Latest = FMath::Max(Latest, E.GoneMs);
  }
  return Latest;
}

int64 FS09DeathStage::GoneMs(const FString& FighterId) const {
  const FEntry* E = Find(FighterId);
  return E ? E->GoneMs : -1;
}

ES09HeartState FS09DeathStage::HeartState(const FString& FighterId, int64 NowMs) const {
  const FEntry* E = Find(FighterId);
  if (!E || NowMs < E->MarkMs) return ES09HeartState::Alive;
  return E->bCross ? ES09HeartState::Crossed : ES09HeartState::Dark;
}

int64 FS09ResultGate::DueMs(bool bHeroFallPending) const {
  if (GameOverMs < 0 || bHeroFallPending) return -1;
  if (HeroGoneMs < 0) return GameOverMs;
  return FMath::Max(GameOverMs, HeroGoneMs + FS09DeathTiming::ResultAfterGoneMs);
}

bool FS09ResultGate::Update(int64 NowMs, int32 Seq, bool bGameOver, bool bHeroFallPending, int64 InHeroGoneMs,
                            FString& OutLine, int64 StagingEndMs) {
  OutLine.Reset();
  if (InHeroGoneMs >= 0) HeroGoneMs = InHeroGoneMs;
  if (!bGameOver) return false;
  if (GameOverMs < 0) GameOverMs = NowMs;
  if (bShown) return false;
  const int64 Cap = GameOverMs + MaxWaitMs;
  int64 Due = DueMs(bHeroFallPending);
  // A combat staging still on screen (an earlier seq than the death) finishes first; the cap still wins. The end is
  // remembered: on the tick the staging ends it is no longer active and the caller passes -1.
  if (StagingEndMs >= 0) HeldStagingEndMs = FMath::Max(HeldStagingEndMs, StagingEndMs);
  const bool bHeldByStaging = Due >= 0 && HeldStagingEndMs > Due;
  if (bHeldByStaging) Due = HeldStagingEndMs;
  if (Due < 0 || Due > Cap) Due = Cap;
  if (NowMs < Due) return false;
  bShown = true;
  ShownMs = NowMs;
  OutLine = FString::Printf(TEXT("RESULT screen seq=%d t=%lld due=%lld gameOver=%lld heroGone=%s wait=%lld%s"), Seq,
                            static_cast<long long>(NowMs), static_cast<long long>(Due),
                            static_cast<long long>(GameOverMs),
                            HeroGoneMs >= 0 ? *FString::Printf(TEXT("%lld"), static_cast<long long>(HeroGoneMs))
                                            : TEXT("-"),
                            static_cast<long long>(NowMs - GameOverMs),
                            bHeldByStaging ? *FString::Printf(TEXT(" staging=%lld"), static_cast<long long>(HeldStagingEndMs))
                                           : TEXT(""));
  return true;
}

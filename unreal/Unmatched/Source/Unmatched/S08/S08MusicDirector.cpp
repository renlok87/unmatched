// AU-S4: the music of a match - see S08MusicDirector.h.
#include "S08MusicDirector.h"

float FS08MusicDirector::FRamp::At(int64 TMs) const {
  if (LenMs <= 0 || TMs >= StartMs + LenMs) return To;
  if (TMs <= StartMs) return From;
  return From + (To - From) * static_cast<float>(TMs - StartMs) / static_cast<float>(LenMs);
}

void FS08MusicDirector::FRamp::Go(float Target, int64 TMs, int32 Ms, float Current) {
  From = Current;
  To = Target;
  StartMs = TMs;
  LenMs = Ms;
}

void FS08MusicDirector::Trace(const TCHAR* StateName, int64 TMs, TArray<FString>& OutLines, const FString& Sting,
                              const TCHAR* Reason) const {
  FString Line = FString::Printf(TEXT("MUSIC state=%s theme=%s t=%lld"), StateName,
                                 Theme.IsEmpty() ? TEXT("-") : *Theme, static_cast<long long>(TMs));
  if (!Sting.IsEmpty()) Line += FString::Printf(TEXT(" sting=%s"), *Sting);
  if (Reason) Line += FString::Printf(TEXT(" reason=%s"), Reason);
  OutLines.Add(MoveTemp(Line));
}

void FS08MusicDirector::SetTheme(const FString& NewTheme, int64 TMs) {
  if (NewTheme != Theme) {
    Theme = NewTheme;
    bThemeChanged = true;
  }
  PendingTheme.Reset();
  ThemeAtMs = -1;
}

void FS08MusicDirector::Menu(int64 TMs, bool bQuiet, TArray<FString>& OutLines) {
  const bool bSame = Theme == TEXT("MUS-MENU");
  SetTheme(TEXT("MUS-MENU"), TMs);
  State = bQuiet ? ES08MusicState::Lobby : ES08MusicState::Menu;
  bFinalStand = false;
  bInCombat = false;
  L1.Go(1.0f, TMs, bSame ? 1000 : 1500, bSame ? L1.At(TMs) : 0.0f);
  L2.Go(bQuiet ? 0.0f : 1.0f, TMs, 1000, bSame ? L2.At(TMs) : 0.0f);
  Trace(bQuiet ? TEXT("lobby") : TEXT("menu"), TMs, OutLines);
}

void FS08MusicDirector::StartMatch(const FString& MapKey, int64 TMs, TArray<FString>& OutLines) {
  SetTheme(FString::Printf(TEXT("MUS-MAP-%s"), *MapKey), TMs);
  State = ES08MusicState::Intro;
  bFinalStand = false;
  bInCombat = false;
  CombatEndAtMs = -1;
  // STG-MATCH-START now (duck), L1 rises over 2 s; L2 off
  L1.Go(1.0f, TMs, IntroMs, 0.0f);
  L2.Go(0.0f, TMs, 0, 0.0f);
  Stings.Add(TEXT("STG-MATCH-START"));
  DuckUntilMs = TMs + 3000;
  Trace(TEXT("intro"), TMs, OutLines, TEXT("STG-MATCH-START"));
}

void FS08MusicDirector::CombatBegin(int64 TMs, TArray<FString>& OutLines) {
  if (State == ES08MusicState::Result || State == ES08MusicState::HeroFallen || Theme.IsEmpty()) return;
  CombatEndAtMs = -1;  // cascaded combats keep L2 (02 §2.4)
  if (!bInCombat) {
    bInCombat = true;
    L2.Go(Db(CombatBoostDb), TMs, CombatInMs, L2.At(TMs));
    State = ES08MusicState::Combat;
    Trace(TEXT("combat"), TMs, OutLines);
  }
}

void FS08MusicDirector::CombatEnd(int64 TMs, TArray<FString>& OutLines) {
  if (!bInCombat) return;
  CombatEndAtMs = TMs + CombatTailMs;
}

void FS08MusicDirector::HeroHp(int32 Hp, int32 MaxHp, int64 TMs, TArray<FString>& OutLines) {
  if (bFinalStand || MaxHp <= 0 || Hp <= 0 || State == ES08MusicState::Result) return;
  if (Hp * 4 > MaxHp) return;
  bFinalStand = true;
  if (!bInCombat) L2.Go(L2Rest(), TMs, 3000, L2.At(TMs));
  Trace(TEXT("final_stand"), TMs, OutLines);
}

void FS08MusicDirector::HeroFallen(int64 TMs, TArray<FString>& OutLines) {
  if (State == ES08MusicState::Result) return;
  State = ES08MusicState::HeroFallen;
  bInCombat = false;
  CombatEndAtMs = -1;
  L1.Go(0.0f, TMs, FallenMs, L1.At(TMs));
  L2.Go(0.0f, TMs, FallenMs, L2.At(TMs));
  Trace(TEXT("hero_fallen"), TMs, OutLines);
}

FString FS08MusicDirector::Result(ES08MatchOutcome Outcome, const FString& OwnHeroKey, int64 TMs,
                                  TArray<FString>& OutLines) {
  FString StingId;
  if (Outcome == ES08MatchOutcome::Aborted) {
    StingId = TEXT("STG-ABORTED");
  } else {
    const TCHAR* Kind = Outcome == ES08MatchOutcome::Win ? TEXT("WIN") : TEXT("LOSE");
    const bool bMotif = OwnHeroKey == TEXT("ARTHUR") || OwnHeroKey == TEXT("MEDUSA");
    StingId = bMotif ? FString::Printf(TEXT("STG-%s-%s"), Kind, *OwnHeroKey) : FString::Printf(TEXT("STG-%s"), Kind);
  }
  State = ES08MusicState::Result;
  bInCombat = false;
  bFinalStand = false;
  CombatEndAtMs = -1;
  L1.Go(0.0f, TMs, 1000, L1.At(TMs));  // the theme crossfades out in 1 s (07 CUE-016)
  L2.Go(0.0f, TMs, 1000, L2.At(TMs));
  Stings.Add(StingId);
  // the sting is 2-4 s; then 2 s of silence; then the quiet menu theme (02 §2.5)
  PendingTheme = TEXT("MUS-MENU");
  ThemeAtMs = TMs + 4000 + ResultGapMs;
  Trace(TEXT("result"), TMs, OutLines, StingId);
  return StingId;
}

void FS08MusicDirector::Sting(const FString& BankId, int32 StingMs, int64 TMs, TArray<FString>& OutLines) {
  Stings.Add(BankId);
  DuckUntilMs = FMath::Max(DuckUntilMs, TMs + StingMs + 1000);
  Trace(TEXT("sting"), TMs, OutLines, BankId);
}

void FS08MusicDirector::SetVoActive(bool bActive, int64 TMs) { bVo = bActive; }

void FS08MusicDirector::SetPaused(bool bInPaused, int64 TMs) { bPaused = bInPaused; }

void FS08MusicDirector::SetDisconnected(bool bInDisconnected, int64 TMs, TArray<FString>& OutLines) {
  if (bDisconnected == bInDisconnected) return;
  bDisconnected = bInDisconnected;
  Trace(bDisconnected ? TEXT("disconnected") : TEXT("reconnected"), TMs, OutLines);
}

float FS08MusicDirector::DuckGain(int64 TMs) const {
  float Db = 0.0f;
  if (TMs < DuckUntilMs) Db -= 6.0f;    // sting
  if (bVo) Db -= 6.0f;                  // VO
  if (bPaused) Db -= 10.0f;             // pause
  if (bDisconnected) Db -= 6.0f;        // 07 CUE-017 "music -50 %"
  return FS08MusicDirector::Db(FMath::Max(Db, -18.0f));
}

FS08MusicMix FS08MusicDirector::Mix(int64 TMs) {
  if (ThemeAtMs >= 0 && TMs >= ThemeAtMs && !PendingTheme.IsEmpty()) {
    SetTheme(PendingTheme, TMs);
    State = ES08MusicState::Lobby;
    L1.Go(1.0f, TMs, MenuFadeInMs, 0.0f);
    L2.Go(0.0f, TMs, 0, 0.0f);
  }
  if (CombatEndAtMs >= 0 && TMs >= CombatEndAtMs) {
    CombatEndAtMs = -1;
    bInCombat = false;
    if (State == ES08MusicState::Combat) State = ES08MusicState::Maneuver;
    L2.Go(L2Rest(), TMs, CombatOutMs, L2.At(TMs));
  }
  if (State == ES08MusicState::Intro && TMs >= L1.StartMs + IntroMs) State = ES08MusicState::Maneuver;
  FS08MusicMix Out;
  Out.Theme = Theme;
  const float Duck = DuckGain(TMs);
  Out.L1 = L1.At(TMs) * Duck;
  Out.L2 = L2.At(TMs) * Duck;
  Out.bThemeChanged = bThemeChanged;
  bThemeChanged = false;
  return Out;
}

TArray<FString> FS08MusicDirector::TakeStings() {
  TArray<FString> Out = MoveTemp(Stings);
  Stings.Reset();
  return Out;
}

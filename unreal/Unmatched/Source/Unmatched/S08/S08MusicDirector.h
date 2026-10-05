// AU-S4 (docs/game-design/audio/02-audio-design.md §2.4-§2.6, card AUC-U03): the music of a match, world-free.
// Vertical adaptivity: both layers of the map theme play all the time (L1 maneuver, L2 combat = drums + bass, the
// same loop length, sample-aligned), the director only moves their gains; stings play on top with a duck.
//
//   state          when                                         L1            L2
//   intro          match start (after STG-MATCH-START)          0 -> 1, 2 s   off
//   maneuver       default                                      1             off
//   combat         CUE-008 attack declared                      1             on in 400 ms (+4 dB boost)
//   (combat end)   end of the combat + 4 s                      1             off in 2.5 s (final stand: -8 dB)
//   final_stand    a hero at <= 25 % HP, once, to the end       1             -8 dB, combat 0 dB
//   hero_fallen    lethal contact on a hero                     off in 1.2 s  off in 1.2 s
//   result         CUE-016 result screen                        sting, then 2 s silence, then the menu theme
//   ducks          sting -6 dB, VO -6 dB, pause -10 dB, disconnected -6 dB (02 §5.2)
//
// Trace: MUSIC state=<s> theme=<bank id> t=<ms> [sting=<bank id>] [reason=<...>]
#pragma once

#include "CoreMinimal.h"

enum class ES08MusicState : uint8 { Silent, Menu, Lobby, Intro, Maneuver, Combat, HeroFallen, Result };
enum class ES08MatchOutcome : uint8 { Win, Lose, Aborted };

/** What the adapter applies this frame: the layer gains (0..1, before the Music bus volume) and the stings to start. */
struct UNMATCHED_API FS08MusicMix {
  FString Theme;          // bank id prefix: MUS-MENU / MUS-MAP-MARMOREAL / MUS-MAP-SARPEDON ("" = none)
  float L1 = 0.0f;
  float L2 = 0.0f;
  bool bThemeChanged = false;  // the adapter (re)starts both layers at sample 0 together
};

class UNMATCHED_API FS08MusicDirector {
public:
  static constexpr float CombatBoostDb = 4.0f;    // L2 in combat (01-inventory: L2 adds only ~0.3 LU at 0 dB)
  static constexpr float FinalStandDb = -8.0f;
  static constexpr int32 CombatInMs = 400;
  static constexpr int32 CombatOutMs = 2500;
  static constexpr int32 CombatTailMs = 4000;
  static constexpr int32 IntroMs = 2000;
  static constexpr int32 FallenMs = 1200;
  static constexpr int32 ResultGapMs = 2000;
  static constexpr int32 MenuFadeInMs = 3000;

  /** The menu / lobby theme (quiet = L1 only in the lobby and after the result). */
  void Menu(int64 TMs, bool bQuiet, TArray<FString>& OutLines);
  /** A match on MapKey (MARMOREAL / SARPEDON / ...): STG-MATCH-START now, the map theme L1 after it. */
  void StartMatch(const FString& MapKey, int64 TMs, TArray<FString>& OutLines);
  void CombatBegin(int64 TMs, TArray<FString>& OutLines);
  void CombatEnd(int64 TMs, TArray<FString>& OutLines);
  /** A hero's HP after a change; <= 25 % of its max (and alive) starts the final stand once. */
  void HeroHp(int32 Hp, int32 MaxHp, int64 TMs, TArray<FString>& OutLines);
  void HeroFallen(int64 TMs, TArray<FString>& OutLines);
  /** CUE-016: the sting of the own hero and outcome (STG-WIN-ARTHUR, STG-LOSE-MEDUSA; STG-WIN / STG-LOSE for a hero
   *  without a motif; STG-ABORTED), then 2 s of silence and the quiet menu theme. Returns the sting bank id. */
  FString Result(ES08MatchOutcome Outcome, const FString& OwnHeroKey, int64 TMs, TArray<FString>& OutLines);
  /** A sting over the theme (sidekick down, hand limit): duck -6 dB for StingMs. */
  void Sting(const FString& BankId, int32 StingMs, int64 TMs, TArray<FString>& OutLines);
  void SetVoActive(bool bActive, int64 TMs);
  void SetPaused(bool bPaused, int64 TMs);
  void SetDisconnected(bool bDisconnected, int64 TMs, TArray<FString>& OutLines);

  /** The gains at TMs (smooth ramps); bThemeChanged once per theme switch. */
  FS08MusicMix Mix(int64 TMs);
  /** The stings due (started by the calls above), oldest first; cleared by the call. */
  TArray<FString> TakeStings();

  ES08MusicState GetState() const { return State; }
  bool IsFinalStand() const { return bFinalStand; }
  const FString& GetTheme() const { return Theme; }

private:
  struct FRamp {
    float From = 0.0f;
    float To = 0.0f;
    int64 StartMs = 0;
    int32 LenMs = 0;
    float At(int64 TMs) const;
    void Go(float Target, int64 TMs, int32 Ms, float Current);
  };
  ES08MusicState State = ES08MusicState::Silent;
  FString Theme;
  FString PendingTheme;
  int64 ThemeAtMs = -1;  // a delayed theme start (after the result gap)
  bool bThemeChanged = false;
  bool bFinalStand = false;
  bool bInCombat = false;
  int64 CombatEndAtMs = -1;
  FRamp L1;
  FRamp L2;
  int64 DuckUntilMs = -1;
  bool bVo = false;
  bool bPaused = false;
  bool bDisconnected = false;
  TArray<FString> Stings;

  static float Db(float Db) { return FMath::Pow(10.0f, Db / 20.0f); }
  float DuckGain(int64 TMs) const;
  void Trace(const TCHAR* StateName, int64 TMs, TArray<FString>& OutLines, const FString& Sting = FString(),
             const TCHAR* Reason = nullptr) const;
  void SetTheme(const FString& NewTheme, int64 TMs);
  float L2Rest() const { return bFinalStand ? Db(FinalStandDb) : 0.0f; }
};

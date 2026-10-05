// DE-019 (W-16; 01 F-09, D-DE-09, "Резолюция ревью" п. 7; 02 SD-07, SD-09; CUE-DISPATCHER.md §3.1): death by stages
// and the way to the result screen - world-free, like the combat staging (S09CombatStage.h).
//
// One scheme for all six v2 figures, from the contact frame of the killing blow (DE-018):
//   HitReact + red tint 0-450 -> DeathSettle 450-1325 (CUE-013) -> heart mark +1100 -> still (hero 300, sidekick 0)
//   -> dissolve (hero 500, sidekick 400) -> gone (hero ~2125, sidekick ~1725) -> result screen = hero gone + 1000
//   (CUE-016; only a hero's death ends the game, so a sidekick's death never opens it). Hit -> screen ~3.1 s.
// The figure actor runs its own death on the world clock (AS08FighterActor, S08HeroesV2::FDeathPlan); this model
// writes the trace at the scheduled times and holds the result screen until the hero is gone + 1000 ms. The game
// state never waits: the GAME_OVER snapshot is applied at once, only its PRESENTATION (the result panel) is held.
//
// Trace (gated by cue_contract.py check-trace DS1-DS5, CUE-DISPATCHER.md §5-§6):
//   CUE death seq=<n> stage=fall t=<ms> fighter=<id> hero=<0|1> staged=<0|1> settle=<ms> still=<ms> dissolve=<ms>
//             style=<fade|ash|none> gone=<ms>
//   CUE death seq=<n> stage=mark t=<ms> fighter=<id> heart=<dark|crossed>     (contact + 1100 = fall + 650)
//   CUE death seq=<n> stage=dissolve t=<ms> fighter=<id> ms=<len>             (only with a dissolve)
//   CUE death seq=<n> stage=gone t=<ms> fighter=<id>
//   RESULT screen seq=<n> t=<ms> due=<ms> gameOver=<ms> heroGone=<ms|-> wait=<ms>
// and the `CUE fx id=CUE-013 subject=<fighter>` show from the fall through FS08CueDispatcher.
#pragma once

#include "CoreMinimal.h"

class FS08CueDispatcher;

/** 01 F-09 at x1 (ms). The death is not scaled by the animation speed (W-24 lists the step, LungeAttack and "-N"). */
struct UNMATCHED_API FS09DeathTiming {
  static constexpr int32 FallAfterContactMs = 450;   // DeathSettle starts after HitReact + tint (= FS09CombatTiming::FallMs)
  static constexpr int32 SettleMs = 875;             // AM_<Key>_DeathSettle, 21 frames at 24 fps
  static constexpr int32 MarkAfterContactMs = 1100;  // the cross on the plate heart (SD-38)
  static constexpr int32 MarkAfterFallMs = MarkAfterContactMs - FallAfterContactMs;
  static constexpr int32 StillHeroMs = 300;
  static constexpr int32 StillSidekickMs = 0;
  static constexpr int32 DissolveHeroMs = 500;
  static constexpr int32 DissolveSidekickMs = 400;
  static constexpr int32 ResultAfterGoneMs = 1000;   // CUE-016: the result screen 1000 ms after the hero is gone
  /** Gone after the contact frame for a v2 figure with its clip and dissolve: hero 2125, sidekick 1725. */
  static constexpr int32 GoneAfterContactMs(bool bHero) {
    return FallAfterContactMs + SettleMs + (bHero ? StillHeroMs + DissolveHeroMs : StillSidekickMs + DissolveSidekickMs);
  }
};

/** What the adapter knows at the fall: the fighter, the snapshot and the figure's own plan (AS08FighterActor::
 *  GetDeathPlan; all 0 for a figure that hides at once - the grey slice, a legacy figure). */
struct UNMATCHED_API FS09DeathInput {
  FString FighterId;
  bool bHero = false;
  int32 Seq = -1;
  bool bStaged = false;      // the fall of a staged combat (CUE combat stage=fall), else a death at the snapshot
  int32 SettleMs = 0;
  int32 StillMs = 0;
  int32 DissolveMs = 0;
  FString Style = TEXT("none");  // fade | ash | none (no dissolve MIC / no v2 figure)
};

/** The plate heart of a fallen fighter (SD-38, W-15 / DE-023 draws it): alive until the mark, then dark - the
 *  fallback until the user accepts the cross glyph of DE-012 - or crossed. */
enum class ES09HeartState : uint8 { Alive, Dark, Crossed };
UNMATCHED_API const TCHAR* S09HeartStateName(ES09HeartState State);

class UNMATCHED_API FS09DeathStage {
public:
  /** A figure falls at NowMs (the start of DeathSettle). Writes the fall line and the CUE-013 show; later lines come
   *  from Tick. False (nothing written) for an empty id or a fighter whose death is already staged. */
  bool Begin(const FS09DeathInput& In, int64 NowMs, FS08CueDispatcher& Cues, TArray<FString>& OutLines,
             bool bCrossGlyph = false);
  /** Emits every stage due at or before NowMs, in time order. */
  void Tick(int64 NowMs, TArray<FString>& OutLines);

  bool IsStaged(const FString& FighterId) const { return Find(FighterId) != nullptr; }
  /** Scheduled gone time of the latest hero death (-1: no hero fell). */
  int64 LatestHeroGoneMs() const;
  /** Scheduled gone time of a fighter (-1 unknown). */
  int64 GoneMs(const FString& FighterId) const;
  ES09HeartState HeartState(const FString& FighterId, int64 NowMs) const;
  int32 Num() const { return Entries.Num(); }

private:
  struct FEntry {
    FS09DeathInput In;
    bool bCross = false;
    int64 FallMs = 0;
    int64 MarkMs = 0;
    int64 DissolveMs = 0;  // dissolve start (= gone without a dissolve)
    int64 GoneMs = 0;
    uint8 Emitted = 0;     // bit 0 mark, bit 1 dissolve, bit 2 gone
  };
  TArray<FEntry> Entries;
  const FEntry* Find(const FString& FighterId) const;
};

/** The result screen (CUE-016) after GAME_OVER: at once when no hero death is staged, otherwise not before the
 *  hero's figure is gone + 1000 ms; never while a staged lethal blow on a hero has not reached its fall yet. A
 *  safety cap opens it MaxWaitMs after GAME_OVER whatever happens. Once open it stays open. */
class UNMATCHED_API FS09ResultGate {
public:
  static constexpr int32 MaxWaitMs = 10000;

  void Reset() { *this = FS09ResultGate(); }
  /** One tick: bGameOver = the applied phase is GAME_OVER; bHeroFallPending = a staging holds a lethal blow on a hero
   *  whose fall has not come yet; HeroGoneMs = FS09DeathStage::LatestHeroGoneMs (-1 none); StagingEndMs = the end of
   *  the combat staging still playing (-1 none; review IMPL 2026-10-05: a death at the snapshot - staged=0 - lands
   *  while the previous combat is still staged, and the screen must not cut that staging). True on the tick the
   *  screen opens (OutLine = the RESULT screen trace line, "+ staging=<ms>" when the staging held it). */
  bool Update(int64 NowMs, int32 Seq, bool bGameOver, bool bHeroFallPending, int64 HeroGoneMs, FString& OutLine,
              int64 StagingEndMs = -1);
  bool IsShown() const { return bShown; }
  bool IsGameOver() const { return GameOverMs >= 0; }
  int64 GetGameOverMs() const { return GameOverMs; }
  int64 GetShownMs() const { return ShownMs; }
  /** When the screen is due now (-1: no game over, or a hero's fall is still pending). */
  int64 DueMs(bool bHeroFallPending) const;

private:
  int64 GameOverMs = -1;
  int64 HeroGoneMs = -1;
  int64 ShownMs = -1;
  // run I acceptance: the latest staging end seen after GAME_OVER. The staging goes inactive on the very tick it ends,
  // which is the tick the held screen opens - the gate keeps the end so that tick still knows (and traces) the hold.
  int64 HeldStagingEndMs = -1;
  bool bShown = false;
};

// DE-029 (W-17; 01 F-06, D-DE-06, D-DE-09; 02 SD-24, SD-39, SD-45; 02-ux-ui-spec §2.9 UI-SCR-GAMEOVER): the result
// screen of a FINISHED duel - world-free, like the death staging (S09DeathStage.h) that decides WHEN it opens.
//
//   - FS09ResultSummary: what the screen says, from real fields only (02 §2.9 "Поля итога"): the outcome of the
//     GD-036 model (phase GAME_OVER + metadata.winnerId), the headline by the WINNING HERO - never by the fighter that
//     struck the last blow (s04: a harpy killed, the screen said Medusa) - the reason from the loser hero's HP, the
//     turnCount of the snapshot and the duration endedAt - startedAt of the game(id) row. Rounds, damage and played
//     cards have no ready field (02 §2.9: "до сверки на экране не показывать") and are not shown.
//     The two sides: left the winner, right the loser drawn as a silhouette (SD-45 p. 2); on a draw / no verdict the
//     viewer stays left and nobody is a silhouette.
//   - FS09ResultView: the screen's modes. Results (the modal) <-> Board ("посмотреть доску"), a 250 ms crossfade
//     (SD-24 p. 1, F-06); the first entry fades in over 500 ms (SD-45 p. 3), a re-entry from the board has no intro.
//     Nothing time-based ever closes it (F-06: no auto-close; DE s05 stood 28.4 s). Keys (02 §2.9): Enter / Esc / L =
//     lobby on the results; on the board Esc = back to the results, Enter / L = lobby; V toggles.
//   - "Play again" (Q-203 (b), DE-027 spike: VS_AI only) and the ABORTED screen wait for GD-040 (IMPL p. 4) - the
//     summary carries no button for them.
//
// Trace: 'RESULT summary outcome=<word> winnerHero=<name|-> loserHero=<name|-> reason=<hp0|draw|verdict|unknown>
//          turn=<n> duration=<s|-> left=<viewer|opponent> silhouette=<0|1>' once per shown screen and
//        'RESULT view mode=<results|board> t=<ms> intro=<ms> fade=<ms> why=<key|button|open>' on every mode change.
#pragma once

#include "CoreMinimal.h"

struct FS08Snapshot;
struct FS09HudModel;

/** One side of the result screen: the player's hero from the public fighters projection. */
struct UNMATCHED_API FS09ResultSide {
  FString PlayerId;
  FString HeroName;          // the HERO / HUGE fighter's name ('' when the projection has none)
  FString HeroFighterId;
  int32 Hp = -1;             // final hero HP (valid only with bHpKnown)
  bool bHpKnown = false;
  int32 MaxHp = -1;
  bool bViewer = false;
  bool bWinner = false;
  bool bAlive = true;        // players[].isAlive (absent = alive)
  bool bSilhouette = false;  // the loser of a decided duel: the avatar is drawn dark (SD-45 p. 2)
  bool IsKnown() const { return !PlayerId.IsEmpty(); }
};

enum class ES09ResultReason : uint8 {
  HeroHpZero,  // the loser hero's HP reached 0 (02 §2.9: "HP <героя> достигли 0")
  Draw,        // mutual destruction (no winnerId, nobody alive)
  Verdict,     // the server named a winner, the loser hero still has HP (any other terminal rule)
  Unknown      // no derivable verdict
};

struct UNMATCHED_API FS09ResultSummary {
  bool bValid = false;       // GAME_OVER applied
  FString Outcome;           // VICTORY / DEFEAT / DRAW / OUTCOME UNAVAILABLE (FS09HudModel::OutcomeWord)
  FString Headline;          // "MEDUSA WINS" / "MUTUAL DESTRUCTION" / "NO SERVER VERDICT"
  ES09ResultReason Reason = ES09ResultReason::Unknown;
  FString ReasonText;        // "King Arthur's HP reached 0" ...
  int32 TurnCount = 0;
  int32 DurationSec = -1;    // endedAt - startedAt of the game(id) row (-1: not known yet)
  FS09ResultSide Left;       // the winner (the viewer without a winner)
  FS09ResultSide Right;      // the loser (the opponent without a winner)

  /** Derives the summary from the GD-036 model and the applied terminal snapshot. StartedAt / EndedAt are the ISO 8601
   *  strings of the game(id) row ('' = not loaded yet: the duration stays unknown). */
  static FS09ResultSummary Build(const FS09HudModel& Hud, const FS08Snapshot& Snapshot, const FString& StartedAt,
                                 const FString& EndedAt);
  /** Whole seconds between two ISO 8601 instants; -1 when either is missing / unparsable or the order is wrong. */
  static int32 DurationSeconds(const FString& StartedAt, const FString& EndedAt);
  /** "m:ss" under an hour, "h:mm:ss" from an hour, "-" when unknown. */
  static FString FormatDuration(int32 Seconds);
  /** "Turn 7 · 12:05" (the duration only when known). */
  FString StatsLine() const;
  static const TCHAR* ReasonName(ES09ResultReason Reason);
  FString TraceLine() const;
};

enum class ES09ResultMode : uint8 { Hidden, Results, Board };
enum class ES09ResultKey : uint8 { Enter, Escape, L, V };
enum class ES09ResultAction : uint8 { None, Lobby, ToggleBoard };

class UNMATCHED_API FS09ResultView {
public:
  static constexpr int32 IntroMs = 500;      // SD-45 p. 3: the modal fades in ~500 ms (DE s04 1179.0-1179.5)
  static constexpr int32 CrossfadeMs = 250;  // SD-24 p. 1, F-06: "посмотреть доску" <-> "к итогам" (DE 250-300)

  /** The result gate opened the screen at NowMs: Results with the intro. A second Open keeps the current mode. */
  bool Open(int64 NowMs);
  /** Results <-> Board with the crossfade; false while hidden. */
  bool ToggleBoard(int64 NowMs);
  void Reset() { *this = FS09ResultView(); }

  ES09ResultMode Mode() const { return CurrentMode; }
  bool IsOpen() const { return CurrentMode != ES09ResultMode::Hidden; }
  bool IsBoardView() const { return CurrentMode == ES09ResultMode::Board; }
  /** Opacity of the results modal (dim + panel) at NowMs: the intro ramp on the first entry, the crossfade on a toggle;
   *  exactly 1 at rest on the results and exactly 0 at rest on the board. */
  float ResultsAlpha(int64 NowMs) const;
  /** Opacity of the board-view bar ("VIEW RESULTS" / "LOBBY"): the complement of the crossfade, 0 on the results. */
  float BoardBarAlpha(int64 NowMs) const;
  /** The modal takes clicks only while it is (becoming) the results - never during the fade to the board. */
  bool ResultsHitTestable() const { return CurrentMode == ES09ResultMode::Results; }
  /** Key routing of the open screen (02 §2.9). */
  ES09ResultAction OnKey(ES09ResultKey Key) const;
  int64 OpenedMs() const { return OpenMs; }
  int32 Toggles() const { return ToggleCount; }

private:
  ES09ResultMode CurrentMode = ES09ResultMode::Hidden;
  int64 OpenMs = -1;
  int64 ChangeMs = -1;   // the last toggle (-1: none yet)
  float FromAlpha = 0.0f;  // results alpha at the last toggle (a toggle mid-fade starts from where it stands)
  int32 ToggleCount = 0;
};

// DE-032 (W-25; 02 SD-51, R-12; CUE-DISPATCHER.md §3.2): the sound of the CUE sync points, world-free. It decides
// WHEN a sound plays and with which gain - never what the sound is: the asset paths come with DE-013 / ART-010 (a
// licensed library, no DE sounds - EULA). Until then every point is a fallback show: the trace line is written, nothing
// plays, no error is logged (CUE-DISPATCHER.md §4 D10).
//
// The sync points (SD-51 pp. 1-5, the sound column of 07):
//   ui     - CUE-002 (own figure picked), CUE-003 (a choice accepted / a HUD press acted), CUE-004 (refused): in the
//            frame of the visual response of the release (UI-INP-011, SD-46);
//   hit    - CUE-011: in the contact frame of the lunge (the combat staging), not when the damage snapshot applies;
//   step   - CUE-007: one sound per edge of a move, at the frame the figure starts that edge; a snapped move (reduced
//            motion, speed "none", past the seq cap) gives one sound at its landing;
//   turn   - CUE-015: the chime of the OWN turn only; the opponent's turn start is silent (WF1 AV-05);
//   result - CUE-016: the result sting starts with the result screen (RESULT screen line).
//
// The volumes (DE-025 storage, SD-55): "master" is the whole output (the adapter sets the audio device's transient
// primary volume), "ambience" is the backdrop sound class (no backdrop sound exists yet). They apply at once: a saved
// change writes `CUE audio … applied=change` and every later sound uses the new gain, no restart.
//
// Trace (CUE-DISPATCHER.md §5; gate AU1-AU7 in tools/s08/cue_contract/cue_contract.py check-trace):
//   CUE audio master=<0-100> master_mute=<0|1> ambience=<0-100> ambience_mute=<0|1> gain_master=<g> gain_ambience=<g>
//             t=<ms> applied=<start|change>
//   CUE sound id=<CUE-NNN> point=<ui|hit|step|turn|result> subject=<id|-> seq=<N|-> t=<ms> event_t=<ms> dt=<ms>
//             class=<UI|SFX|Music|Ambience> sound=<name|missing|none> gain=<g> result=<played|fallback|silent|throttled>
//             [turn=own|opp] [edge=<k>/<n>|edge=snap due=<ms>] [reason=<opponent|muted>]
//   CUE sound drop point=step seq=<N> fighter=<id|*> t=<ms> count=<n> reason=<skip|replace>
#pragma once

#include "CoreMinimal.h"
#include "S08UserSettings.h"

enum class ES08SoundPoint : uint8 { Ui, Hit, Step, Turn, Result };
enum class ES08SoundResult : uint8 { Played, Fallback, Silent, Throttled };

/** One sound row: the sfx block of a cue-table.json row, reduced to what the sound points decide on. */
struct UNMATCHED_API FS08SoundRow {
  FString CueId;
  FString SoundClass;  // UI / SFX / Music (cue-table sound_class); Ambience is the backdrop class (no CUE row yet)
  int32 Priority = 1;
  int32 RetriggerMs = 0;  // D8: concurrency.retrigger_ms
  FString SoundPath;      // soft path /Game/...; empty while cue-table sfx.sound is null (ART-010 / DE-013)
};

namespace S08SoundRows {
/** CUE-002, 003, 004, 007, 011, 015, 016 as cue-table.json writes their sfx block (Unmatched.S08.CueSound.Table). */
UNMATCHED_API const TArray<FS08SoundRow>& All();
UNMATCHED_API const FS08SoundRow* Find(const FString& CueId);
UNMATCHED_API const TCHAR* PointName(ES08SoundPoint Point);
/** Short asset name of a soft path (/Game/Audio/SW_Hit.SW_Hit -> SW_Hit); empty for an empty path. */
UNMATCHED_API FString ShortName(const FString& SoftPath);
/** The ui CUE of a board release (07 CUE-002/003/004): refused (a toast / an illegal space) -> CUE-004; a command
 *  sent or a choice accepted -> CUE-003; an own figure picked -> CUE-002; another selection change -> CUE-003;
 *  nothing changed -> nullptr (no sound: the release had no visible response). */
UNMATCHED_API const TCHAR* BoardUiCue(bool bRefused, bool bCommand, bool bPickedOwn, bool bSelectionChanged);
}  // namespace S08SoundRows

/** One sound request at a sync point. EventMs is the frame time of the visual event the sound belongs to (the
 *  release response, the contact stage, the edge start, the banner, the result screen). */
struct UNMATCHED_API FS08SoundRequest {
  ES08SoundPoint Point = ES08SoundPoint::Ui;
  FString CueId;
  FString Subject;      // fighter / pressed id; empty = "-"
  int32 Seq = -1;       // -1 = "-"
  int64 EventMs = 0;
  bool bOwnTurn = true; // Turn only: false = the opponent's turn start (silent)
  int32 Edge = -1;      // Step only: edge index (0-based); -1 = a snapped move (one landing sound)
  int32 Edges = 0;      // Step only: edges of the move
  int64 DueMs = -1;     // Step only: the scheduled edge start (the schedule; the frame may land a bit later)
};

/** What the adapter does with a decision: play SoundPath (if any) at Gain, as a UI sound when bUiSound. */
struct UNMATCHED_API FS08SoundDecision {
  ES08SoundResult Result = ES08SoundResult::Fallback;
  FString SoundPath;
  float ClassGain = 1.0f;  // the class volume WITHOUT master (master is the device volume)
  float Gain = 1.0f;       // the effective gain (master x class), traced
  bool bUiSound = false;
};

/** A scheduled step sound of a move (one per edge, or one landing sound of a snapped move). */
struct UNMATCHED_API FS08StepSound {
  FString FighterId;
  int32 Seq = -1;
  int64 DueMs = 0;
  int32 Edge = -1;
  int32 Edges = 0;
};

class UNMATCHED_API FS08CueSound {
public:
  /** Short asset name of a row's sound, or empty when the asset is not there (the adapter loads it). Unset: the paths
   *  are taken as they are (empty = missing). */
  TFunction<FString(const FS08SoundRow& Row)> AssetResolver;

  /** The volumes in force from TMs (`CUE audio … applied=start|change`). A call with unchanged values writes nothing
   *  (false). */
  bool SetAudio(const FS08AudioSettings& Audio, int64 TMs, bool bStart, TArray<FString>& OutLines);
  const FS08AudioSettings& GetAudio() const { return Audio; }
  /** The gain of a sound class without master (Ambience: its volume and mute; the others 1) and with it. */
  float ClassGain(const FString& SoundClass) const;
  float EffectiveGain(const FString& SoundClass) const;

  /** One sound at a sync point, decided at NowMs (the frame it plays in). Unknown CueId: nothing, Silent. */
  FS08SoundDecision Play(const FS08SoundRequest& Request, int64 NowMs, TArray<FString>& OutLines);

  /** CUE-007: the step sounds of one move - one per edge from StartMs every StepMs, or one at StartMs when snapped. */
  void ScheduleSteps(const FString& FighterId, int32 Seq, int64 StartMs, double StepMs, int32 Steps, bool bSnapped);
  /** The step sounds due at NowMs, in schedule order (each plays in this frame). */
  void TakeDueSteps(int64 NowMs, TArray<FS08StepSound>& OutDue);
  /** The pending step sounds are dropped - every one (a skip landed every move, reason=skip) or only FighterId's (its
   *  new move replaced the old one at its final pose, reason=replace): one `CUE sound drop` line per seq. */
  int32 DropSteps(int64 NowMs, const TCHAR* Reason, TArray<FString>& OutLines, const FString& FighterId = FString());
  int32 PendingSteps() const { return Steps.Num(); }

private:
  FS08AudioSettings Audio;
  bool bAudioSet = false;
  TMap<FString, int64> LastPlayed;  // D8 per CUE
  TArray<FS08StepSound> Steps;      // sorted by DueMs (stable)
};

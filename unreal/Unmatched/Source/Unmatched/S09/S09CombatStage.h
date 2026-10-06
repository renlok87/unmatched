// DE-018 (W-14; 01 F-01, F-03, F-04 and "Резолюция ревью" п. 1, 4; 02 SD-03..06, SD-27, SD-48, SD-49): the combat
// staging - a world-free timeline that turns the snapshot of a combat result into the sequence
//   reveal (CUE-010 flip) -> read hold -> effect lines -> slam + outcome label -> pause "score" 300 ->
//   LungeAttack -> contact frame -> HitReact + hit tint (450 / lethal 550), "-N" +60, HP +80 -> end (CUE-011 900).
// The game state never waits for it (the snapshot is applied at once); only the PRESENTATION of the target's HP,
// its fall and the damage number is held until the contact frame (FS09CombatHold). The camera does not move (D-10).
//
// Numbers (x1, 01 F-01 / CUE-DISPATCHER.md §3.1): CUE-010 animation 800 = flip 620 + slam 180, the holds sit between
// flip and slam inside CUE-010; readHold 1000 only when a revealed card carries effect text; effectStep 600 per
// fired line (highlight 400 scaled + 200); slamToLunge 300; contact = the AnimNotify "Contact" of the attacker's
// LungeAttack (DE-010), fallback the profile frame. Holds never scale with the animation speed; the flip, the slam,
// the highlight, the lunge and the "-N" do. A skip (click / Space / Enter) zeroes every remaining hold (read, effect
// lines, pause); the clips (lunge, HitReact <= 0.9 s) are never cut.
//
// Trace (gated by cue_contract.py check-trace C1-C6, CUE-DISPATCHER.md §5-§6):
//   CUE combat seq=<n> stage=start t=<ms> attacker=<id> target=<id> text=<0|1> lines=<n> damage=<n> lethal=<0|1>
//              shown=<0|1> speed=<x> flip=<ms> contact=<ms> src=<notify|profile|default> a=<A> d=<D> outcome=<win|hold>
//   CUE combat seq=<n> stage=read|effect|pause t=<end> ms=<actual> skipped=<0|1> [i=<k>]
//   CUE combat seq=<n> stage=slam t=<ms> | lunge | contact | hit tint=<ms> | minus amount=<n> | hp from=<a> to=<b>
//              | fall | skip src=<click|space|enter|catchup>
//              | end total=<ms> skipped=<0|1> cut=<0|replace|reconnect|catchup>
//   (src=catchup / cut=catchup: R-03, the catch-up policy of S09PresentationCatchup.h - the short version / the
//   instant result of a staging that lags behind newer applied snapshots)
//   (the lunge line carries rate=<LungeAttack play rate> since DE-025)
// and the `CUE fx` lines of CUE-010 (subject=scene, done with hold=) and CUE-011 (subject=target, from contact)
// through FS08CueDispatcher.
#pragma once

#include "CoreMinimal.h"
#include "S09CombatEffectLog.h"
#include "S09HudModel.h"
#include "../S08/S08BoardModel.h"

class FS08CueDispatcher;

/** 01 F-01 / F-03 / F-04 / F-09 at speed x1 (ms). */
struct UNMATCHED_API FS09CombatTiming {
  static constexpr int32 DeclareMs = 600;          // CUE-008: aim ring + direction flash (no clip)
  static constexpr int32 RevealMs = 800;           // CUE-010 animation = flip + slam
  static constexpr int32 SlamMs = 180;             // the slam part of CUE-010
  static constexpr int32 FlipMs = RevealMs - SlamMs;
  static constexpr int32 DefenseFlipDelayMs = 120; // the defense card turns ~120 ms after the attack card
  static constexpr int32 ReadHoldMs = 1000;        // combat.readHoldMs
  static constexpr int32 EffectStepMs = 600;       // combat.effectStepMs = highlight + 200
  static constexpr int32 EffectHighlightMs = 400;
  static constexpr int32 SlamToLungeMs = 300;      // combat.slamToLungeMs
  static constexpr int32 FaceTurnMs = 120;         // AN-24 (ВР-06): the attacker turns to the target before the lunge
  static constexpr int32 HitWindowMs = 900;        // CUE-011 duration from the contact frame
  static constexpr int32 HitTintMs = 450;
  static constexpr int32 HitTintLethalMs = 550;
  static constexpr int32 FallMs = 450;             // F-09: DeathSettle starts after HitReact + tint (0-450)
  static constexpr int32 MinusDelayMs = 60;        // "-N" = contact + 60
  static constexpr int32 HpDelayMs = 80;           // new HP number = contact + 80
  static constexpr int32 MinusLifeMs = 900;        // "-N" lifetime x speed (F-04)
  static constexpr int32 DefaultContactMs = 292;   // no v2 clip: Arthur's profile frame k.7 (the shortest)
  static constexpr int32 MaxBlockingMs = 1000;     // 08 §6.1 P3: an input block is never longer than 1 s
};

/** What the staging needs from the snapshots (built by AS08FlowGameMode::TrackCombatResult). */
struct UNMATCHED_API FS09CombatStageInput {
  int32 Seq = -1;               // the snapshot that closed the combat
  FString AttackerId;
  FString TargetId;
  FString AttackerLabel;
  FString TargetLabel;
  bool bHasEffectText = false;  // a revealed card carries effect text (read hold 1000)
  int32 EffectLines = 0;        // fired effect lines (R-02: from metadata.lastCombat, S09CombatEffectLog::Lines)
  TArray<FS09CombatEffectLine> Effects;  // R-02: what the card panels print, index-aligned with the lines (display)
  int32 Damage = 0;             // HP the target lost in this combat (>= 0)
  bool bLethal = false;         // the target fell
  bool bDamageShown = false;    // the damage was already presented while the combat was paused (no second "-N")
  int32 HpBefore = -1;
  int32 HpAfter = -1;
  int32 TargetX = -1;           // the target's cell before the blow (the board keeps it standing until the fall)
  int32 TargetY = -1;
  int32 ContactMs = FS09CombatTiming::DefaultContactMs;  // contact frame of the attacker's LungeAttack at x1
  FString ContactSource = TEXT("default");               // notify | profile | default
  float SpeedMul = 1.0f;        // 0 = "none" (instant animations), 0.5 fast, 1 normal, 1.5 slow (03 §5)
  FS09CombatReveal Reveal;      // the cards for the edge-of-field HUD layer (SD-48 p. 4)
};

// AU-S4: FlipAttack / FlipDefense (the reveal flips, the defense +120 ms), Effect (a fired effect line), Slam and
// Block (the contact frame of a combat without damage) - the sound of the staging (02-audio-design §4.5).
// AN-24 (ВР-06): Face - the attacker's turn to the target 120 ms before the lunge (inside the pause "score").
enum class ES09CombatEvent : uint8 { Lunge, HitReact, Minus, Hp, Fall, End, FlipAttack, FlipDefense, Effect, Slam,
                                     Block, Face };
struct UNMATCHED_API FS09CombatStageEvent {
  ES09CombatEvent Type = ES09CombatEvent::End;
  int64 AtMs = 0;
};
UNMATCHED_API const TCHAR* S09CombatEventName(ES09CombatEvent Event);

/** Presentation hold of the target (the snapshot already carries the result). The HUD view keeps the old HP until
 *  contact + 80; the board view also keeps the figure standing until contact + 450 when the blow is lethal. */
struct UNMATCHED_API FS09CombatHold {
  FString FighterId;
  int32 HeldHealth = 0;
  int32 HeldX = -1;
  int32 HeldY = -1;
  bool bHpHeld = false;
  bool bAliveHeld = false;
  bool IsSet() const { return !FighterId.IsEmpty() && (bHpHeld || bAliveHeld); }
  void Reset() { *this = FS09CombatHold(); }
  /** Patches the target's entry of Fighters in place to the fighter before the blow (HP, cell, defeat flag): the HUD
   *  view while the HP is held, the board view while the HP or the fall is held. */
  void Apply(TArray<FS08BoardFighter>& Fighters, bool bBoardView) const;
};

enum class ES09CombatStagePhase : uint8 { Idle, Flip, Read, Effects, Slam, Pause, Lunge, Hit, Done };

class UNMATCHED_API FS09CombatStage {
public:
  /** Starts a staging at NowMs (the reveal). A running staging is cut first (cut=replace). Writes the start line and
   *  the CUE-010 show; the first Tick emits what is due. Returns false (nothing started) for an input without a
   *  seq or fighters, and for the seq of the last staging (ACC-012: a repeated seq never shows a second blow). */
  bool Start(const FS09CombatStageInput& InInput, int64 NowMs, FS08CueDispatcher& Cues, TArray<FString>& OutLines,
             TArray<FS09CombatStageEvent>& OutEvents);
  /** Emits every boundary due at or before NowMs, in time order: lines (with their scheduled time) and events for
   *  the adapter. */
  void Tick(int64 NowMs, FS08CueDispatcher& Cues, TArray<FString>& OutLines, TArray<FS09CombatStageEvent>& OutEvents);
  /** A skip (click / Space / Enter): the remaining holds become 0 from NowMs. False when nothing is skippable now
   *  (the input is then left to its usual handler). */
  bool Skip(int64 NowMs, const TCHAR* Source, FS08CueDispatcher& Cues, TArray<FString>& OutLines,
            TArray<FS09CombatStageEvent>& OutEvents);
  /** Ends a running staging now (a new combat result, a reconnect): the state events still pending (HP, fall,
   *  end) are emitted at NowMs so the presentation catches up with the snapshot; the visual ones are dropped. */
  void Cut(int64 NowMs, const TCHAR* Reason, FS08CueDispatcher& Cues, TArray<FString>& OutLines,
           TArray<FS09CombatStageEvent>& OutEvents);

  bool IsActive() const { return Phase != ES09CombatStagePhase::Idle && Phase != ES09CombatStagePhase::Done; }
  bool IsSkippable(int64 NowMs) const { return IsActive() && NowMs < PauseEndMs && !bAllHoldsSkipped; }
  ES09CombatStagePhase GetPhase() const { return Phase; }
  const FS09CombatStageInput& GetInput() const { return Input; }
  int32 GetSeq() const { return Input.Seq; }
  /** The hold of the target for the adapter's fighter views (empty when no staging holds anything). */
  const FS09CombatHold& GetHold() const { return Hold; }

  // ---- HUD queries (edge cards, outcome label) ----
  bool ShowsCards(int64 NowMs) const { return IsActive() && NowMs >= StartMs; }
  bool ShowsDefenseFace(int64 NowMs) const { return ShowsCards(NowMs) && NowMs >= StartMs + DefenseFlipMs; }
  /** The outcome label lives from the slam to the end (~1.5 s, F-01). */
  bool ShowsOutcome(int64 NowMs) const { return IsActive() && NowMs >= SlamStartMs; }
  bool AttackerWins() const { return Input.Damage > 0; }
  /** R-02 (F-01): effect lines on the card panels. Line k appears when its 600 ms step starts and stays until the
   *  end; a skip drops the remaining steps, so every line is on the panel from the skip on (nothing is hidden). */
  int32 EffectLinesShown(int64 NowMs) const;
  /** The line whose highlight (400 x speed from its start) runs now, -1 when none. */
  int32 HighlightedEffectLine(int64 NowMs) const;

  // ---- schedule (absolute ms; tests and the adapter) ----
  int64 GetStartMs() const { return StartMs; }
  int64 GetSlamStartMs() const { return SlamStartMs; }
  int64 GetLungeMs() const { return PauseEndMs; }
  int64 GetContactMs() const { return ContactAtMs; }
  int64 GetEndMs() const { return EndMs; }
  /** AN-24 (ВР-06): the Face event fires here (max(SlamEnd, lunge - 120)); with the pause skipped it equals the
   *  lunge time - the turn then runs with the first 120 ms of the clip. */
  int64 GetFaceMs() const { return FaceAtMs; }
  /** Total combat time of the F-01 scale: CUE-008 (declare) + reveal..end. */
  int64 TotalMs() const { return Scaled(FS09CombatTiming::DeclareMs) + (EndMs - StartMs); }
  int32 GetHitTintMs() const {
    return Input.bLethal ? FS09CombatTiming::HitTintLethalMs : FS09CombatTiming::HitTintMs;
  }
  /** "-N" lifetime (ms) at the input speed (F-04: 900 x speed; "none" keeps the fast 450). */
  int32 MinusLifeMs() const { return MinusLifeMsAt(Input.SpeedMul); }
  static int32 MinusLifeMsAt(float SpeedMul);
  /** DE-025 (SD-49): play rate of the attacker's LungeAttack at the input speed - 1 / speed (fast 2, slow 0.67), so
   *  the clip's contact frame lands on the scaled contact; 0 for "none" (instant animations: the clip is not played,
   *  the contact is the lunge frame). */
  float LungePlayRate() const { return LungePlayRateAt(Input.SpeedMul); }
  static float LungePlayRateAt(float SpeedMul);

private:
  FS09CombatStageInput Input;
  FS09CombatHold Hold;
  ES09CombatStagePhase Phase = ES09CombatStagePhase::Idle;
  int32 LastStartedSeq = -1;     // one staging per result seq: a repeated seq never plays the blow again
  bool bAllHoldsSkipped = false;
  bool bSkipped = false;
  // lengths (ms) fixed at Start
  int32 FlipLenMs = 0;           // CUE-010 flip part (shown CUE-010 x 620/800)
  int32 SlamLenMs = 0;           // CUE-010 slam part
  int32 DefenseFlipMs = 0;
  int32 ContactOffsetMs = 0;     // contact frame at the input speed
  int32 HitWindowMs = 0;         // CUE-011 shown from contact
  // actual holds (a skip shortens them)
  int32 ReadMs = 0;
  bool bReadSkipped = false;
  TArray<int32> EffectMs;
  TArray<bool> EffectSkipped;
  int32 PauseMs = 0;
  bool bPauseSkipped = false;
  // schedule (absolute ms; Reschedule derives it from StartMs and the lengths above)
  int64 StartMs = 0;
  int64 FlipEndMs = 0;
  int64 SlamStartMs = 0;
  int64 SlamEndMs = 0;
  int64 FaceAtMs = 0;            // AN-24: the attacker's turn to the target, max(SlamEndMs, PauseEndMs - FaceTurnMs)
  int64 PauseEndMs = 0;          // = lunge start
  int64 ContactAtMs = 0;
  int64 EndMs = 0;
  // emission cursor over the boundary order of this staging
  int32 NextBoundary = 0;

  int32 Scaled(int32 Ms) const;
  int32 HoldTotalMs() const;
  void Reschedule();
  int64 BoundaryTime(uint8 Kind, int32 Index) const;
  int64 EffectLineStartMs(int32 Index) const;
  FString Prefix(const TCHAR* Stage, int64 TMs) const;
  void Release(ES09CombatEvent Type, int64 AtMs, TArray<FS09CombatStageEvent>& OutEvents);
};

// GD-029/030/031: BOOT -> LOGIN -> LOBBY -> ROOM -> BOARD grey flow.
// Phase 2 renders the authoritative board + fighters from the applied
// snapshot (GD-030) and drives gameplay commands through the single state
// store with an in-flight gate (GD-031). Packaged demo drive:
//   -S08Auto -S08Create (host) or -S08Code=XXXXXX (joiner),
//   -S08HeroId=<prisma id>, -S08Maneuver (auto maneuver when the board is
//   live and it is this client's turn; -S08ManeuverPlan=boost3 fills the
//   opened draft with a boost card and three moves before the confirm - M1,
//   MS-AT-32), -S08Shot=<abs path> (1920x1080
//   HighResShot after the maneuver), -S08DropWsAfter=<seconds> (test hook:
//   abrupt WS loss mid-run to prove reconnect convergence),
//   -S08ExitAfter=<seconds>.
// Demo credentials NEVER travel on the process command line (visible to any
// local process listing): the driver injects them as the per-process
// environment variables S08_EMAIL / S08_PASSWORD.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "S08FlowController.h"
#include "S08BoardModel.h"
#include "S08ArtHud.h"
#include "../S09/S09HudModel.h"
#include "../S09/S09ManeuverUi.h"
#include "../S09/S09MoveInput.h"
#include "../S09/S09HudPress.h"
#include "../S09/S09CombatStage.h"
#include "../S09/S09PresentationCatchup.h"
#include "../S09/S09DeathStage.h"
#include "../S09/S09ResultScreen.h"
#include "../S09/S09DeckPanel.h"
#include "../S09/S09PendingPresent.h"
#include "../S09/S09OpponentView.h"
#include "../S09/S09TurnStatus.h"
#include "../S09/S09TurnHud.h"
#include "../S09/S09HandLimit.h"
#include "../S09/S09CardSlot.h"
#include "S08CueDispatcher.h"
#include "S08CueSound.h"
#include "S08MusicDirector.h"
#include "S08VoDirector.h"
#include "S08Ambience.h"
#include "S08AudioCues.h"
#include "S08MoveAnim.h"
#include "S08ShotQueue.h"
#include "S08TurnPortraitWidget.h"
#include "S08FlowGameMode.generated.h"

struct FS08MoveDraftView;
namespace S08HeroesV2 {
struct FBenchClipPoseSpec;
}

class SEditableTextBox;
class SConstraintCanvas;
class STextBlock;
class SVerticalBox;
class SHorizontalBox;
class AS08BoardActor;
class ACameraActor;
class UUserWidget;

/** Bounded auto-send accounting for one command head (S10 review P1(1)):
 *  attempts are counted ONLY when the command actually left the client - a
 *  gate-blocked tick (stream reconnecting, recovery lock held) consumes no
 *  budget, so a temporarily disconnected head is not silently exhausted and
 *  permanently held. An Observe() with a changed key starts a fresh window
 *  (per pending head / per turn). Pure state machine - unit-testable
 *  without a world. */
struct FS09AutoSendBudget {
  explicit FS09AutoSendBudget(int32 InMax) : Max(InMax) {}
  /** Fresh window when the head key changed (new head / new turn). */
  void Observe(const FString& Key) {
    if (Key != CurrentKey) {
      CurrentKey = Key;
      Sends = 0;
    }
  }
  bool Exhausted() const { return Sends >= Max; }
  /** Count one ACTUAL dispatch - callers invoke this only on a confirmed
   *  send (or a definitive server rejection of one), never on a gate block. */
  void CountSend() { ++Sends; }
  int32 Sends = 0;
  const int32 Max;
private:
  FString CurrentKey;
};

/** Sol6 review P2(5): the EXACT draft transitions the S09AUTO driver
 *  performs, extracted as pure functions so the production paths (RunS09Auto
 *  / the OnCommandRejected handler) and their tests cannot diverge. No
 *  world, no UI - state in, state out. */
struct FS09AutoDraftTransitions {
  /** RunS09Auto pending auto-answer: the bounded budget counts ONLY an
   *  actual dispatch. A gate-blocked tick (recovery lock held / stream
   *  reconnecting) consumes nothing and the draft stays intact for a later
   *  tick - a temporarily blocked head is never silently exhausted.
   *  Pass-through of bDispatched (the caller traces "picked" on true). */
  static bool PendingAutoAnswer(bool bDispatched, FS09AutoSendBudget& Budget) {
    if (bDispatched) Budget.CountSend();
    return bDispatched;
  }
  /** Definitive server rejection of a DISPATCHED attack (OnCommandRejected -
   *  the server answered, so the command is provably NOT applied; unknown
   *  outcomes never route here, they arm the controller's recovery lock
   *  instead): close the draft, count one bounded retry, hold the next
   *  attempt for a second. Returns the new NextCommandAt. */
  static float AttackDraftRejected(ES09CommandMode& Mode, FString& AttackerId,
                                   FString& TargetId, FString& CardId,
                                   FS09AutoSendBudget& Budget, float Elapsed) {
    Mode = ES09CommandMode::None;
    AttackerId.Reset();
    TargetId.Reset();
    CardId.Reset();
    Budget.CountSend();
    return Elapsed + 1.0f;
  }
};


/** S10/GD-040: the EXACT step order the opt-in packaged ABORTED-proof drive
 *  (-S10AbortProof) performs, extracted as a pure function so the drive and
 *  its test cannot diverge. Without the flag NOTHING ever leaves Idle (no
 *  auto path touches the normal UI). The single leaveGame fires only AFTER
 *  the interrupted-screen evidence settled, the lobby shot only once the
 *  post-leave Lobby stage arrived, and completion only after that shot
 *  settled. No world, no UI, no screenshots - step state in, step out. */
struct FS10AbortProofTransitions {
  enum class EStep { Idle, ScreenShotWait, LeaveOnce, LobbyShotWait, Complete };
  /** @param bAbortProofEnabled the -S10AbortProof CLI opt-in.
   *  @param bAbortedLive authoritative ABORTED room row on the live match
   *  (Stage Started) - the only thing that can wake the drive.
   *  @param bInLobby post-leave Lobby stage (this drive's own leave).
   *  @param bEvidenceSettled the current shot's file exists (or its bounded
   *  wait expired - "proceeding without the shot" is a settled state too). */
  static EStep Advance(EStep Step, bool bAbortProofEnabled, bool bAbortedLive,
                       bool bInLobby, bool bEvidenceSettled) {
    if (!bAbortProofEnabled) return EStep::Idle;
    switch (Step) {
      case EStep::Idle:
        return bAbortedLive ? EStep::ScreenShotWait : EStep::Idle;
      case EStep::ScreenShotWait:
        return bAbortedLive && bEvidenceSettled ? EStep::LeaveOnce : EStep::ScreenShotWait;
      case EStep::LeaveOnce:
        return bInLobby && !bAbortedLive ? EStep::LobbyShotWait : EStep::LeaveOnce;
      case EStep::LobbyShotWait:
        return bEvidenceSettled ? EStep::Complete : EStep::LobbyShotWait;
      case EStep::Complete:
        return EStep::Complete;
    }
    return EStep::Idle;
  }
};


/** AU-S4: a one-shot due later (a dissolve after the settle, a VO answer, the result line). */
struct FS08DelayedSound {
  int64 DueMs = 0;
  FString BankId;      // a bank id, or the VO event for SoundClass "VO"
  FString SoundClass;  // UI / SFX / Music / Ambience / VO
  FString Tag;         // trace tag, or the VO speaker key
  bool bAnswer = false;
};

/** AU-S4: a hit of this frame - hits of one frame are one sound (02-audio-design §4.5). */
struct FS08PendingHit {
  FS08SoundRequest Request;
  int32 Damage = 0;
  bool bStaged = false;
};

UCLASS()
class AS08FlowGameMode : public AGameModeBase {
  GENERATED_BODY()
public:
  AS08FlowGameMode();
  ~AS08FlowGameMode() override;
  virtual void BeginPlay() override;
  virtual void Tick(float DeltaSeconds) override;
  virtual void EndPlay(const EEndPlayReason::Type Reason) override;

  /** Inspector lines from one card view: identity/type/values/full printed
   *  text for a public face, a single faceless line for a placeholder. Pure
   *  (no UI state) so the privacy of the hidden branch is unit-testable. */
  static void BuildInspectorLines(const FS09CardView& Card, TArray<FString>& OutLines);
  /** S10/GD-040: a terminal screen owns the keyboard - the GAME_OVER result
   *  panel or the live-room ABORTED interruption panel (both promise "L or
   *  Enter returns you to the lobby"). Every gameplay binding is dead there,
   *  and L/Enter must map to the lobby return instead of sinking into the
   *  gameplay key handler. Pure, unit-testable without a world. */
  static bool TerminalScreenOwnsKeys(ES08Stage Stage, bool bGameOver, bool bRoomAborted);

  // ---- AU-S6 (docs/game-design/audio/08-screen-audio-hooks.md): the sound API of the screens and modals
  /** A sound of a screen or modal by its bank id (UI bus; STG-* on the music bus). Unknown id: a trace line, silence. */
  UFUNCTION(BlueprintCallable, Category = "Unmatched|Audio")
  void PlayScreenSound(FName BankId);
  /** The pause screen is open: the music ducks -10 dB while it stays open. */
  UFUNCTION(BlueprintCallable, Category = "Unmatched|Audio")
  void SetAudioPaused(bool bPaused);
  /** The hero confirmed in the room: its select sting (STG-SELECT-<HERO>) when the bank has one. */
  UFUNCTION(BlueprintCallable, Category = "Unmatched|Audio")
  void PlayHeroSelectSting(const FString& HeroName);

private:
  void BuildUi();
  void RefreshUi();
  void RunAutoDrive();
  void AutoAdvance();
  // ---- GD-030 board ----
  void HandleApplied(const FS08Snapshot& Snapshot, ES08SeqDecision Decision);
  void HandleCues(const TArray<FS08Cue>& Cues);
  void SyncBoardFromApplied();
  void SyncCombatFocus();
  void SetupCameraForBoard();
  void UpdateBoardCamera(float DeltaSeconds);
  // ---- TASK-022 input ----
  void HandleClick();
  void SelectFighter(const FString& FighterId);
  void TryManeuverTo(int32 CellX, int32 CellY);
  void FinishPendingManeuver(int32 CellX, int32 CellY);
  // ---- GD-032/033 HUD + command UI ----
  void RefreshHud();
  void BuildHudWidgets();
  void HandleHudKeys();
  void HandleHandCardClick(int32 HandIndex, ES09InputSource Source = ES09InputSource::Click);
  void InspectCard(const FS09CardView& Card);
  // ---- GD-032 public discard browser ----
  /** Selects a card of one PUBLIC pile (0 = own, 1 = opponent) into the
   *  inspector. Read-only browsing: never mutates a draft, a hand pick or a
   *  server command; hidden entries still inspect as faceless placeholders. */
  void HandleDiscardCardClick(int32 PileIndex, int32 CardIndex);
  /** Arrow navigation while the browser is open: bSwitchPile toggles own
   *  <-> opponent, Direction -1/+1 steps the selection (wraps), 0 keeps it. */
  void StepDiscardBrowserSelection(bool bSwitchPile, int32 Direction);
  void BeginManeuverCommand();
  void ConfirmDraft();
  void CancelDraft();
  void EndTurnCommand();
  // ---- MS-T-06: reasons by key (move-selection 02 §1.1, 03 §8.2) ----
  /** Toast of a why.* / ms.* reason by key (FS09Reason::Text: EN table,
   *  CellLabel, no grid coordinates) for Seconds; trace "TOAST why=<key>". */
  void ShowReason(const FS09Reason& Reason, float Seconds = 4.0f);
  /** A classified server rejection (FS08FlowController::OnRejection): banner
   *  4 s, the named space marked (CUE-004 ring); the draft reaction itself is
   *  the refetched snapshot (class И keeps, С rebuilds or closes). */
  void HandleRejection(const FS08Rejection& Rejection);
  // ---- MS-T-07: move-selection input (03 §3, 04 §6.2) ----
  /** The space under the cursor - a ray to the board plane (decor and figures
   *  never pick it) - and the fighter actor hit; false off the board. */
  bool PickBoardUnderCursor(class APlayerController* PC, FIntPoint& OutCell, FString& OutFighterId) const;
  /** Applies an FS09MoveInput result: sends, toasts, D/I closing, the board
   *  highlight. */
  void ApplyMoveInput(const FS09InputResult& Result);
  // ---- DE-014 (W-21, UI-INP-011): HUD presses never lost, never silent ----
  /** One pressable HUD element (S09HudPress.h) with the SButton look of
   *  Padding / Tint / Label (hit-test invisible); on the click Blocked() is
   *  asked AT THAT MOMENT - a reason shows CUE-004 (toast by key), none runs
   *  Action. The look is dimmed when Blocked() already holds at build time. */
  TSharedRef<SWidget> MakeHudPress(FName Id, TFunction<FS09Reason()> Blocked, TFunction<void()> Action,
                                   const FMargin& Padding, const FLinearColor& Tint,
                                   const TSharedRef<SWidget>& Label);
  /** The arbiter resolved a release: trace HUD-PRESS, then the action or CUE-004. */
  void HandleHudPressOutcome(const FS09HudPressOutcome& Outcome, const TFunction<FS09Reason()>& Blocked,
                             const TFunction<void()>& Action);
  /** The press reason of a command blocked by the in-flight gate. */
  FS09Reason HudBusyReason() const;
  /** DE-015: the first answered board release of the own turn closes the
   *  TURN-INPUT watch (src=board; refused = a CUE-004 key). */
  void NoteTurnBoardInput(const FIntPoint& Cell, const FString& FighterId, const FS09InputResult& Result);
  /** The one send path of a confirmed maneuver (Enter in FS09MoveInput, the
   *  older ConfirmDraft, the -S08Maneuver driver). */
  void SubmitConfirmedManeuver(const FS09ManeuverCommand& Command);
  FS09InputView MoveInputView() const;
  /** The game viewport has the OS focus (MS-E-104). */
  bool ViewportHasFocus() const;
  // ---- GD-034 combat UI ----
  void BeginAttackDraft();        // A: open the local attack draft
  void NoDefenseCommand();        // N: defender closes the window (no card)
  void ResolveCombatCommand();    // R: resolve (COMBAT_RESOLVE / no-defense)
  void DeclinePendingChoiceCommand(); // X: decline an optional boost choice
  void StayPendingInPlaceCommand();   // MS-T-12: "Stay in place" of a pending MOVE (zero-step resolve)
  // ---- DE-020 (W-11; SD-10, SD-19, SD-28, SD-56) ----
  /** After a player's attack pick (click / key): a complete draft goes at once (no confirm), or opens the hero
   *  ability prompt (King Arthur) - the deferred choice without a timer. */
  void AfterAttackPick(ES09InputSource Source);
  /** The ability prompt's "Attack without BOOST" (N / button). */
  void AttackWithoutAbilityBoostCommand();
  /** C / the plate / the toast's details: collapse or expand the own pending choice. */
  void TogglePendingCollapseCommand();
  /** Skipped-effect notes (toast + CUE-004) and the presentation of the own head, per applied snapshot. */
  void FeedPendingPresentation(const FS08Snapshot& Snapshot);
  void PlaySchemeCommand();       // G: open/close the EXACT-instance scheme picker
  /** Enter inside the scheme picker: sends the selected EXACT instance or
   *  rejects a stale/dead selection (never substitutes another card). */
  void ConfirmSchemeCommand();
  /** Enter dispatch by the open combat mode (attack/defense/boost confirm). */
  /** @return true when the command was actually dispatched (S09AUTO uses the
   * false case to back out of the draft instead of parking in it - the P1
   * regression where "ATTACK sent" was logged while the controller had
   * dropped the command). */
  bool ConfirmCombat();
  /** Detects the combat-closed transition and freezes LastCombatResult. */
  void TrackCombatResult(const FS08Snapshot& Snapshot, ES08SeqDecision Decision);
  // ---- DE-018 (W-14) combat staging: the result snapshot is applied at once, its presentation runs the F-01
  // scale (reveal -> holds -> slam -> pause -> LungeAttack -> contact -> HitReact / "-N" / HP) ----
  /** Builds the staging input from the last open-combat snapshot and the closing one and starts it. */
  void StartCombatStage(const FS08Snapshot& Closing, const FS08Snapshot& Baseline, const FS08CombatInfo& Combat,
                        int32 Damage, int32 HpBefore);
  /** Emits the due staging boundaries (lines + events) - every tick, and before any other cue is fed. */
  void TickCombatStage();
  /** Click / Space / Enter during a staging hold: skips the holds (true = the input was consumed). */
  bool TryCombatSkip();
  /** R-03: the catch-up policy of the staging (S09PresentationCatchup.h) - per applied snapshot (Applied) or on the
   *  game clock (nullptr): a staging lagging behind newer snapshots plays its short version or is cut. */
  void RunPresentationCatchup(const FS08Snapshot* Applied);
  void RunCombatEvents(const TArray<FS09CombatStageEvent>& Events);
  void WriteCueLines(const TArray<FString>& Lines);
  /** CUE-011 pieces outside or inside a staging: the damage number (+ evidence shot scheduling) and the hit. */
  void PresentDamageNumber(const FString& FighterId, int32 Damage, int32 Seq, float LifeSeconds);
  /** DE-032: DueMs = the contact boundary of a staged hit (its sound's `due`), -1 for an unstaged one. */
  void PresentHit(const FString& FighterId, int32 Seq, int32 TintMs, int64 DueMs = -1);
  // ---- MS-T-16 move animation (CUE-007, S08MoveAnim.h) ----
  /** Any key or mouse button but Space and the wheel while a figure travels: every move jumps to its final pose in the
   *  same frame (MS-E-70 / MS-E-110). The input is not consumed - it acts on the logical (snapshot) state as usual. */
  void TryMoveSkip();
  /** Damage cues that wait for the arrival of their moving target (MS-E-48 cascade), presented when due. */
  void TickDeferredDamage();
  /** Re-derives ShownFighters (HUD view) and, with bSyncBoard, pushes the board view to the board actor. */
  void RefreshShownFighters(bool bSyncBoard);
  /** Fighters as the HUD shows them: the staging holds the target's HP until contact + 80 ms. */
  const TArray<FS08BoardFighter>& HudFighters() const;
  const FS08BoardFighter* FindShownFighter(const FString& FighterId) const;
  /** Edge-of-field cards (SD-48 p. 4) and the outcome label of the running staging (RefreshHud). */
  void BuildCombatStageHud();
  // ---- DE-019 death by stages and the result gate (S09DeathStage.h) ----
  /** After a board sync: every fighter that was alive on the board and is not any more falls now - its death is
   *  staged with the figure's own plan (the CUE death trace, CUE-013). */
  void NoteBoardDeaths(const TArray<FS08BoardFighter>& BoardView);
  /** Death lines due now and the result gate; the tick the result screen opens rebuilds the HUD. */
  void TickDeathStage();
  /** The result screen (GD-036 panel) is shown: GAME_OVER is applied AND the gate opened (the hero's death played
   *  out + 1000 ms). Before that the GAME_OVER state is applied but presented as the board. */
  bool IsResultScreenShown() const { return Hud.bGameOver && ResultGate.IsShown(); }
  int64 NowMs() const { return static_cast<int64>(FMath::RoundToDouble(static_cast<double>(Elapsed) * 1000.0)); }
  void RunS09Auto();
  void TakeS09Shots();
  /** Run F G-LIVE (DE-031): the deck side panel frames of the S09 auto client (S08FlowGameModeDeckPanel.cpp). */
  void TakeS09DeckPanelShots();
  // ---- GD-036 result screen + lobby return ----
  /** LeaveGame from the result screen; safe to press repeatedly (one send). */
  void ReturnToLobbyCommand();
  /** S09AUTO tail: result shot -> leaveGame -> lobby shot -> early exit. */
  void DriveS09ResultFlow();
  /** S10/GD-040 opt-in (-S10AbortProof) packaged ABORTED proof: interruption
   *  screen shot -> ONE leaveGame -> lobby shot -> clean early exit. Dormant
   *  without the flag; never sends a gameplay command after the abort. */
  void RunS10AbortProof();
  /** Public name of a committed combat card instance (own/opponent discard
   *  piles, both already revealed to this seat); falls back to a placeholder
   *  that leaks no identity. Used by the resolve AND pending panels. */
  FString CommittedCardLabel(const FString& InstanceId) const;
  void RunS09HudProbe();
  void SimulateSlateKeyProbe(const FKey& Key, bool bUp);
  void UpdateLegacyRootVisibility();
  /** Stage transition hook: entering Started resets the previous duel's
   *  result-drive state; leaving Started tears the runtime board AND the
   *  gameplay HUD down so the post-duel Lobby cannot render stale in-game
   *  artifacts (manual leave and S09AUTO alike). */
  void OnStageChanged(ES08Stage OldStage, ES08Stage NewStage);
  /** Drops every gameplay-scoped view model (HUD, command UI, combat result
   *  tracking, hand baseline, discard browser, inspector, maneuver draft) and
   *  re-renders. Idempotent; called on every exit from Started. */
  void ClearGameplayHud();
  /** MS-T-04 (MS-R-55): binds the command UI's draft write-through / read-back
   *  to the controller's maneuver draft cache (survives ClearGameplayHud). */
  void BindManeuverDraftCache();
  /** GD-036: user-facing Lobby entry panel (authenticated user) rendered in
   *  the HUD overlay - the legacy grey-flow form stays an F10 overlay. */
  void BuildLobbyPanel();
  // Probe mode has no backend: handlers must read the fixture snapshot.
  const FS08Snapshot& EffectiveSnapshot() const {
    return bS09Probe ? S09ProbeSnapshot : Flow->GetAppliedSnapshot();
  }
  // ---- demo drive ----
  void RunAutoManeuver();
  /** Evidence PNG (InPath empty = AutoShotPath). I-03 (D-1 of run H): at most one FScreenshotRequest per frame - a
   *  shot asked while one is in flight (or after another one this frame) waits in EvidenceShotQueue and is captured in
   *  a following frame under its own name ("SHOT queued" / "SHOT dequeued"); the SHOT ctx / RENDER / fighter lines are
   *  written when the request really leaves. */
  void TakeEvidenceShot(const FString& InPath);
  void CaptureEvidenceShot(const FString& BasePath);
  /** Start of Tick: lets the oldest queued evidence shot out when no capture is in flight and none left this frame. */
  void DrainEvidenceShotQueue();
  bool IsEvidenceCaptureBusy() const;
  // ---- ART-004 stage 3 T2.2: art HUD (plate, compact labels, exact-size
  // combat icon), zoom config and INPUT/CAMERA/PLATE/SHOT traces ----
  void BuildArtHudWidgets(const TSharedRef<SConstraintCanvas>& Canvas);
  void UpdateArtHud(float DeltaSeconds);
  void UpdateHover();
  void UpdateCombatIcon(bool bActive);
  void UpdatePlate(bool bActive);
  /** W5b-R D-1/D-5: screen tags, the combat icon anchor and the damage number, one deterministic layout per change
   *  of its inputs (plate -> target tag -> icon -> damage number -> other tags, far to near). */
  void UpdateBoardLabels(bool bActive, const FString& IconTarget, const FString& IconSource);
  /** W5b-R: honest SHOT lines - the widget / icon / tag / damage / HUD panel lines of the shots requested in this
   *  frame, written at the END of the frame from the widgets' actual visibility and painted geometry (the T5.2 icon
   *  was traced visible=1 at request time and hidden later in the same tick). */
  void HandleEndFrame();
  void WriteArtHudLateLines(const FString& File, uint64 RequestFrame);
  /** UGameViewportClient::OnScreenshotCaptured: the engine hands the captured pixels to this delegate INSTEAD of
   *  writing the file - it saves the PNG and writes "SHOT captured file= frame= px= sha256=" (pixel provenance). */
  void HandleScreenshotCaptured(int32 Width, int32 Height, const TArray<FColor>& Colors);
  /** Viewport rect of a figure's on-screen box keyed by fighter id (alive fighters with a projection). */
  TMap<FString, FS08ScreenRect> FigureScreenRects() const;
  void ApplyWheel(int32 Direction, ES08InputSource Source);
  void ApplySpace(ES08InputSource Source);
  void TraceOsClick(const FKey& Button);
  void RunArtPreviewInputPlan();
  void EmulateInputStep(ES08InputStep Step);
  void WriteArtHudShotLines();
  /** W4-C: `SHOT widget id=<ui-id> impl=<umg|slate> ...` painted bboxes of
   *  every plate/icon part of every view (compare mode: UMG + Slate twin).
   *  Prefix "HUD sample=N " = the compare-mode periodic parity samples. */
  void WriteArtHudWidgetLines(const FString& Prefix = FString(), bool bLate = false);
  /** Viewport-pixel projection (same call as the SHOT fighter lines). */
  bool ProjectToViewport(const FVector& World, FVector2D& OutScreen) const;
  /** On-screen box of a fighter's visible figure (base disc to figure top). */
  bool FigureScreenRect(const FString& FighterId, FS08ScreenRect& OutRect) const;
  /** The current selection whose destination cells the plate must not cover:
   *  pending draft > maneuver draft > plain board selection. */
  void CurrentSelection(FString& OutFighterId, TSet<uint64>& OutLegalCells) const;
  TArray<FS08CellQuad> ProjectCells(const TArray<FIntPoint>& Cells) const;
  /** Painted geometry of a HUD widget in viewport pixels. */
  bool WidgetViewportRect(const TSharedPtr<SWidget>& Widget, FS08ScreenRect& OutRect) const;
  /** Viewport pixels per HUD canvas slate unit (1.0 at 1920x1080). */
  float HudPixelsPerUnit() const;
  FString PlateFighterIdNow() const;
  const FS08BoardFighter* FindFighter(const FString& FighterId) const;

  TUniquePtr<FS08FlowController> Flow;
  TWeakPtr<SEditableTextBox> EmailBox;
  TWeakPtr<SEditableTextBox> PasswordBox;
  TWeakPtr<SEditableTextBox> CodeBox;
  TWeakPtr<STextBlock> StatusLine;
  TWeakPtr<STextBlock> RoomLine;
  TWeakPtr<STextBlock> PlayersLine;
  TWeakPtr<STextBlock> ProblemLine;
  TWeakPtr<STextBlock> BoardLine;
  TWeakPtr<STextBlock> ToastLine;
  TSharedPtr<SVerticalBox> TraceBox;
  TArray<FString> TraceLines;
  // Legacy login/lobby/debug Root (room code + traces live here): collapsed
  // during gameplay and in probe mode so published shots cannot leak codes;
  // F10 re-opens it as an operator-only debug overlay.
  TSharedPtr<SVerticalBox> LegacyRoot;
  bool bDebugPanelForced = false;
  TSharedPtr<SVerticalBox> HandBox;     // GD-032 own hand strip (exact ids)
  TSharedPtr<SVerticalBox> PanelsBox;   // GD-032 counters + inspector
  TSharedPtr<SVerticalBox> CommandBox;  // GD-033 draft/action panel
  TSharedPtr<SVerticalBox> CombatEdgeLeft;    // DE-018: attack card at the left edge of the field
  TSharedPtr<SVerticalBox> CombatEdgeRight;   // DE-018: defense card / cross at the right edge
  TSharedPtr<SVerticalBox> CombatOutcomeBox;  // DE-018: "A vs D" + outcome label, top centre
  TWeakPtr<STextBlock> ToastHudLine;    // gameplay toast (legacy panel hidden)
  TWeakPtr<class SBorder> ToastHudBorder;
  TSharedPtr<class SConstraintCanvas> HudCanvas; // root of the HUD overlay
  TWeakPtr<SEditableTextBox> LobbyCodeBox; // HUD lobby panel join-code field
  // S10/GD-039: the visible lobby mode control (checkbox pair) - the next
  // createGame carries this mode; VS_AI starts one human + the server bot.
  FString LobbyCreateMode = TEXT("ONE_V_ONE");
  // Capture mechanism: "request" = FScreenshotRequest(bShowUI=true) [default],
  // "slate" = FSlateApplication::TakeScreenshot of the HUD canvas widget.
  FString S09ShotMode;

  // ---- GD-032/033 state ----
  FS09HudModel Hud;
  FS09CommandUi CommandUi;
  TSet<FString> PreviousOwnHandIds;

  // ---- GD-034 combat state ----
  /** Readable post-combat summary (privacy-safe: own committed values and
   *  the damage number only - never the opponent's card or values). */
  struct FS09CombatResult {
    bool bValid = false;
    int32 SequenceNumber = 0;
    int32 Damage = -1;         // net health lost; -1 when the opening snapshot is unavailable
    FString TargetFighterId;  // attacked fighter (own or enemy - public board id)
    bool bViewerWasDefender = false;
    bool bViewerWasAttacker = false;
    int32 OwnCommittedValue = -1; // attack (attacker) / defense (defender) value
    FString OutcomeLine;          // prebuilt human-readable result
    float ShownAt = -1.0f;
  };
  FS09CombatResult LastCombatResult;
  FS08Snapshot PrevApplied;    // combat-close detection baseline
  bool bHasPrevApplied = false;
  FString CombatStartTargetId;
  int32 CombatStartTargetHealth = -1;
  // DE-018: the CUE dispatcher (CUE-008..011 lines, dedupe per seq) and the combat staging. The attacker's
  // LungeAttack is no longer sent at COMBAT_RESOLVE: the staging plays it after the slam + 300 ms (01 F-03).
  FS08CueDispatcher CueDispatcher;
  FS09CombatStage CombatStage;
  // DE-032 (W-25, SD-51; S08FlowGameModeSound.cpp): the sound of the CUE sync points - ui in the release response
  // frame, the hit in the contact frame, one step per edge, the chime of the own turn only, the result sting with the
  // screen - and the volumes "master" / "ambience" applied without a restart. No asset yet: fallback lines only.
  FS08CueSound CueSound;
  void InitCueSound();
  /** The saved volumes in force now (`CUE audio`): master = the audio device's transient primary volume. */
  void ApplyAudioSettings(bool bStart);
  void PlayCueSound(const FS08SoundRequest& Request);
  /** A ui sound (CUE-002/003/004) in this frame - the frame of the visual response of the release. */
  void PlayUiSound(const TCHAR* CueId, const FString& Subject);
  void PlayBoardUiSound(const FS09InputResult& Result, const FString& FighterId);
  /** CUE-007: one step sound per edge of every plan of this seq (a replaced move drops its pending steps). */
  void ScheduleStepSounds(const TArray<FS08MovePlan>& Plans);
  void TickStepSounds();
  void PlayHitSound(const FString& FighterId, int32 Seq, int64 DueMs);
  void PlayTurnSound(int32 Seq, bool bOwnTurn);
  void PlayResultSting(int32 Seq, int64 ScreenMs);
  // ---- AU-S4 (S08FlowGameModeAudio.cpp, docs/game-design/audio/02-audio-design.md): the music of the match, the hero
  // lines with subtitles, the map ambience and the extra CUE sounds (005/006/008/009/010/012/013/014).
  FS08MusicDirector Music;
  FS08VoDirector Vo;
  FS08AmbienceScheduler Ambience;
  FRandomStream AudioRng;
  TArray<FS08DelayedSound> DelayedSounds;
  TArray<FS08PendingHit> PendingHits;
  TMap<FString, int32> AudioLastHp;
  TSet<FString> AudioLowHpDone;
  FString AudioMapKey;
  FString AudioOwnHeroKey;
  FString AudioMatchGameId;
  bool bAudioMatchStarted = false;
  bool bAudioDiscardDraft = false;
  bool bVoPlaying = false;
  bool bIdleOffered = false;
  int32 AudioIdleCount = 0;
  int32 AudioOwnTurns = 0;
  int32 AudioOwnHand = -1;
  int32 AudioOppHand = -1;
  int64 AudioLastInputMs = 0;
  int64 AudioHandLimitMs = MIN_int64 / 2;
  int64 SubtitleUntilMs = 0;
  TSharedPtr<class SBox> SubtitleBox;
  TSharedPtr<class STextBlock> SubtitleText;
  void InitAudioRuntime();
  void ShutdownAudioRuntime();
  void TickAudioRuntime();
  void FlushPendingHits();
  class USoundBase* LoadAudio(const FString& SoftPath);
  void PlayBankSfx(const FString& BankId, const TCHAR* SoundClass, const TCHAR* Tag, float GainMul = 1.0f);
  void PlayCueBank(const TCHAR* CueId, const FString& Subject, int32 Seq, const FString& BankId);
  void DelaySound(int32 InMs, const FString& BankId, const TCHAR* SoundClass, const TCHAR* Tag);
  void DelaySoundVo(const FString& Event, const FString& Speaker, int32 InMs, bool bAnswer = false);
  void StartTheme(const FString& Theme);
  void StartAmbience(const FString& MapKey, TArray<FString>& OutLines);
  void OfferVoLine(const FString& Event, const FString& SpeakerKey, bool bAnswer = false, int32 HarpyIndex = 1);
  FString AudioKeyOf(const FString& FighterId, int32* OutHarpyIndex = nullptr) const;
  FString HeroKeyOfOwner(const FString& OwnerId) const;
  void AudioOnApplied(const FS08Snapshot& Snapshot, const TArray<FS08BoardFighter>& Before);
  void AudioOnAttackDeclared(const FString& AttackerId, int32 Seq, bool bAbilityBoost = false);
  void AudioOnDefensePlayed(const FString& TargetId, int32 Seq);
  void AudioOnCombatEvent(const FS09CombatStageEvent& Event);
  void AudioOnHit(const FString& FighterId, int32 Seq, int64 DueMs);
  void AudioOnDeath(const FString& FighterId, bool bHero, int32 Seq, int32 DissolveAtMs);
  void AudioOnCardSlot(const FS09SlotCard& Card);
  void AudioOnTurn(bool bOwnTurn);
  /** CUE-016: the director picks the sting of the own hero and outcome; returns its bank id. */
  FString AudioOnResult();
  void NoteAudioInput();
  // ---- AU-S5 (07-production-log §9): the sounds wired after AU-S4 and the mix recording
  /** The flow stage changed: a fresh match resets the per-match audio; the lobby / room plays the menu theme; the
   *  login success / failure plays its UI sound. */
  void AudioOnStage(ES08Stage OldStage, ES08Stage NewStage);
  void ResetAudioMatch();
  void StopMatchVoice(const TCHAR* Reason);
  /** FX-GAZE-REQUEST: an own Medusa gaze head opened (it sounds once the combat staging is over). */
  void AudioOnPendingOpen(const FString& HeadId);
  /** The own pending head was answered: FX-GAZE-BEAM (CUE-014) when the gaze was used, FX-GAZE-DECLINE when declined. */
  void AudioOnPendingAnswered(const FString& HeadId, const FString& FighterId, bool bUsed,
                              const FString& Type = FString());
  /** UI-ROOM-*: a room answer (create / join / leave / ready). */
  void AudioOnRoom(const FS08RoomState& Room);
  /** FX-HARPY-RETURN: a defeated figure is back on the board (Medusa's harpies return). */
  void AudioOnRevive(const FString& FighterId);
  /** FX-NO-TARGET: an effect had nothing to target (skipped-effect note), once per frame. */
  void AudioOnSkippedEffect();
  /** CUE-007 kind=place: the move of this figure and seq is a placement (BRD-PLACE instead of a step). */
  void AudioNotePlace(const FString& FighterId, int32 Seq);
  /** The panel / inspector / boost-slot watchers of the frame (UI-PANEL-*, CRD-INSPECT-*, CRD-BOOST-PLACE). */
  void TickAudioWatchers();
  FS08RoomState AudioRoom;
  TSet<FString> AudioPlaceSteps;
  bool bAudioDeckPanelOpen = false;
  bool bAudioDiscardOpen = false;
  bool bAudioInspecting = false;
  FString AudioInspectedId;
  FString AudioBoostCardId;
  uint64 AudioNoTargetFrame = 0;
  // AU-S6: the live stream of the match - lost for 1.5 s plays CUE-017 and ducks the music, back plays CUE-018
  bool bAudioStreamSeenReady = false;
  bool bAudioNetLost = false;
  int64 AudioStreamDownSinceMs = -1;
  int64 AudioRoomCountGoMs = MIN_int64 / 2;  // the countdown screen played the start (SC-18)
  /** BRD-CANDIDATES: a maneuver draft opened with more than one figure to move (once per pendingManeuver.id). */
  void AudioOnDraftOpen(const FString& ManeuverId, int32 Movable);
  /** BRD-PUSH: the enemy figures an EFFECT trail of this seq moved (their step sounds get the push whistle). */
  void AudioOnEffectTrail(int32 Seq, const TArray<FString>& Pushed);
  /** UI-TIMER-*: the own defense window deadline (called with the HUD refresh, 4 times a second). */
  void AudioTickDeadline();
  /** -S08AudioRecord=<file.wav>: the whole output of this client from the match start to the result + 8 s (or the
   *  exit from the match), written synchronously as a 16-bit WAV for the loudness pass (tools/audio/mix_check.py).
   *  While it records, the client's speakers are silent (main submix output 0, recorded before that gain). */
  void StartAudioRecording();
  /** The mix bus (02 §5.3): US08MixLimiterPreset on the main submix - the make-up gain that brings a match at the
   *  default volumes to -20 LUFS-I (measured AU-S5, 07 §9) and a look-ahead peak limiter at -1.5 dBFS.
   *  -S08MixMakeupDb=<dB> overrides the gain for a tuning run; -S08MixLegacy (rollback) leaves the main submix bare. */
  void InstallMasterLimiter();
  void RemoveMasterLimiter();
  void StopAudioRecording(const TCHAR* Why);
  FS08DeadlineBeeper DeadlineBeeper;
  FString AudioGazeHeadId;
  bool bAudioGazeRequestDue = false;
  FString AudioDraftManeuverId;
  TMap<int32, TArray<FString>> AudioPushBySeq;
  bool bAudioBoostDeclared = false;  // the local attacker heard FX-ARTHUR-BOOST at the declaration of this combat
  bool bAudioBoostFizzle = false;    // the staged combat cancelled the attack card with its boost
  FString AudioRecordFile;
  bool bAudioRecording = false;
  bool bS09SlowDefenseDone = false;    // AU-S6 'slowdefense': the held first defense went
  bool bS09SlowDefenseTraced = false;
  int64 AudioRecordStopMs = -1;
  float AudioRecordPrevUnfocused = 0.0f;
  // MS-T-16: the motion settings (US08UserSettings + flags, read at BeginPlay), the move pose parameters and the
  // damage cues held until their target arrives. DE-025: re-read when the settings are saved (US08UserSettings::
  // OnChanged) - the next move seq and the next combat staging use them, no restart.
  FS08MotionSettings MoveMotion;
  FDelegateHandle SettingsChangedHandle;
  void RefreshMotionSettings();
  /** DE-025 (UI-ACC-013, SD-49): the combat animation multiplier - 0 none, 0.5 fast, 1 normal, 1.5 slow. */
  float CombatSpeedMul() const { return static_cast<float>(S08Motion::SpeedMul(MoveMotion.Speed)); }
  FS08MoveAnimParams MoveAnimParams;
  struct FDeferredDamage {
    FString FighterId;
    int32 Damage = 0;
    int32 Seq = 0;
    int64 DueMs = 0;
  };
  TArray<FDeferredDamage> DeferredDamage;
  FS09DeathStage DeathStage;
  FS09ResultGate ResultGate;
  // ---- DE-029 (W-17; 01 F-06, D-DE-06; 02 SD-24, SD-45; 02-ux-ui-spec §2.9): the full-screen result modal and
  // "посмотреть доску" (S09/S09ResultScreen.h, S08FlowGameModeResult.cpp) ----
  /** The modal (dim + centred panel) over the whole canvas and the board-view bar; built once with the HUD. */
  void BuildResultScreenWidgets(const TSharedRef<class SConstraintCanvas>& Canvas);
  /** RefreshHud on GAME_OVER after the gate: the summary and the panel content (state-driven, idempotent). */
  void RebuildResultScreen();
  /** Every frame: opens the view when the gate opens; the intro / crossfade opacity and the hit-test of both layers. */
  void TickResultScreen();
  /** "Посмотреть доску" <-> "К итогам" (250 ms crossfade). */
  void ToggleResultBoard(const TCHAR* Why);
  /** The keys of the open result screen (02 §2.9); true when a key was taken. */
  bool HandleResultKeys(class APlayerController* PC);
  /** DE-029 review tooling (-Bench -BenchResult=results|board [-BenchResultLoser]): the bench fixture turned into the
   *  server's terminal body of a hero kill (GAME_OVER, winnerId, the loser hero at HP 0) and the result screen opened
   *  over it - the frame of the modal and of the final board on a real map. No room row: the duration stays unknown. */
  void BenchResultBegin(const FS08Snapshot& Fixture, bool bBoard, bool bViewerLoses);
  bool bBenchResult = false;
  FS08Snapshot BenchResultSnapshot;
  FS09ResultView ResultView;
  FS09ResultSummary ResultSummary;
  FString ResultSummaryTraced;
  TSharedPtr<class SBorder> ResultOverlay;
  TSharedPtr<class SBox> ResultPanelBox;
  TSharedPtr<class SBorder> ResultBoardBar;
  // ---- DE-030 (W-19; 01 F-05; 02 SD-29, SD-41): the deck side panel (S09/S09DeckPanel.h,
  // S08FlowGameModeDeckPanel.cpp) ----
  /** The persistent canvas slot of the panel (content by RefreshHud, opacity by TickDeckPanel). */
  void BuildDeckPanelWidgets(const TSharedRef<class SConstraintCanvas>& Canvas);
  /** RefreshHud: the auto-close on a new input demand, the deck-list prefetch, the content while visible. */
  void RefreshDeckPanel();
  void RebuildDeckPanelContent();
  void TickDeckPanel();
  /** K / Shift+K / the side buttons and tabs: open Side, or close it when it is the open one. */
  void ToggleDeckPanel(ES09DeckSide Side, const TCHAR* Why);
  void CloseDeckPanel(const TCHAR* Why);
  /** K, Shift+K and Esc (while open) - true when the key was the panel's. */
  bool HandleDeckPanelKeys(class APlayerController* PC);
  /** What asks me for input now (S09DeckPanel::InputDemandKey). */
  FString DeckDemandKeyNow() const;
  /** Re-parses the controller's deck lists when their revision changed. */
  void SyncDeckLists();
  /** Review tooling (-Bench -BenchDeckPanel=own|opp -BenchDeckLists=<file>): the panel over the bench scene. */
  bool BenchDeckPanelBegin(const FS08Snapshot& Fixture, const FString& SideName, const FString& ListsPath);
  FS09DeckPanelView DeckPanel;
  TArray<FS09DeckList> DeckLists;
  int32 DeckListsRevision = -1;
  bool bBenchDeckPanel = false;
  FString DeckPanelSelected;  // the row showing its card text (read-only)
  FString DeckModelTraced;
  TSharedPtr<class SBorder> DeckPanelBorder;
  TSharedPtr<class SBox> DeckPanelBox;
  TMap<FString, bool> BoardAliveById;      // DE-019: the board view's alive flags of the last sync
  int32 FallSeq = -1;                      // DE-019: seq of the staged fall being released (RunCombatEvents)
  TArray<FS08BoardFighter> ShownFighters;  // HudFighters() while the staging holds the target
  bool bCombatDamageShownEarly = false;    // the target's damage was shown while the combat was paused
  bool bCombatOutcomeShown = false;        // the HUD was rebuilt for the outcome label of this staging
  int32 CombatEffectHudKey = -1;           // R-02: effect lines shown / highlighted at the last HUD rebuild
  FS09PresentationCatchup PresentationCatchup;  // R-03: bounded lag of the staging behind the applied state
  uint64 CombatSkipFrame = MAX_uint64;     // frame whose click / Space / Enter was a staging skip
  // auto plan tokens: attack | defend | nodefense | resolve | scheme
  TArray<FString> S09CombatPlan;
  bool bS09ShotDefense = false;
  bool bS09ShotResolve = false;
  bool bS09ShotResult = false;
  bool bS09ShotResolveRevealed = false; // resolve window AFTER the reveal (GD-033 proof)
  bool bS09ShotDamage = false;
  float DamageShotAtElapsed = -1.0f;
  // W5b-R: the damage number of the first COMBAT (host evidence; the first damage of a game can be an ability).
  bool bS09ShotDamageCombat = false;
  float DamageCombatShotAtElapsed = -1.0f;
  float DamageCombatShotDeadline = -1.0f;
  FString LastTeamMappingLine;
  FDelegateHandle EndFrameHandle;
  FDelegateHandle ScreenshotCapturedHandle;
  FString S09ShotDefensePath;
  FString S09ShotResolvePath;
  FString S09ShotResultPath;
  FString S09ShotResolveRevealedPath;
  // Bounded UI-capture waits (GD-034 rework): -1 = not requested; the drive
  // proceeds WITHOUT the shot once Elapsed passes the request + 12s, and the
  // missing file is reported instead of silently claimed.
  float ShotDefenseAtElapsed = -1.0f;
  float ShotResolveAtElapsed = -1.0f;
  float ShotPendingAtElapsed = -1.0f;
  float ShotBlockedAtElapsed = -1.0f;
  float ShotResultAtElapsed = -1.0f;
  float HudTickAccumulator = 0.0f; // countdown re-render while combat is open
  int32 LastAutoMode = -1; // S09AUTO drive diagnostics: last logged mode
  // Seq the previous-hand baseline was taken from; a same-seq re-apply (WS
  // push + HTTP refetch of one state) must not absorb the freshly drawn
  // card into the baseline or the *new* marker dies before the boost pick.
  int32 PreviousHandSeq = 0;
  FS09CardView InspectedCard;
  bool bInspecting = false;
  int32 InspectedHandIndex = -1;
  // ---- GD-032 public discard browser (both piles are public information;
  // the model only ever holds server-filtered faces) ----
  bool bDiscardBrowserOpen = false;
  int32 DiscardBrowserPile = 0;   // 0 = own discard, 1 = opponent discard
  int32 DiscardBrowserIndex = -1; // selected card in the open pile
  int32 InspectedSource = 0;      // 0 hand, 1 own discard, 2 opponent discard
  int32 OwnTurnIndex = -1;   // S09 auto: how many own turns already driven
  int32 TurnStartSeq = -1;   // S09 auto: seq when the current own turn opened
  float NextCommandAt = 0.0f; // S09 rate limit between server commands
  bool bAutoS09 = false;
  bool bAutoS09Boost = false; // joiner variant: boost with the newly drawn card
  int32 S09FirstConfirmSeq = -1; // seq after the first confirmed maneuver
  bool bS09ShotHud = false;
  bool bS09ShotDiscard = false;
  bool bS09ShotDraft = false;  // live shot with the FIRST maneuver draft open
  FString S09ShotDiscardPath; // UI capture writes a few frames late: hold the
                              // discard confirm until this file exists.
  FString S09ShotDraftPath;   // same hold for the first maneuver draft shot
  FString S09ShotPendingPath;   // hold the auto-answer until this file exists
  // One queue-head UI shot per distinct variety type:stage:mode (GD-035):
  // captures the stage-2 replacement head too, not only the first head.
  TSet<FString> S09PendingShotKeys;
  float ShotDraftAtElapsed = -1.0f;
  float ShotHudAtElapsed = -1.0f;
  float ShotDiscardAtElapsed = -1.0f;
  // Run D G-LIVE (move-selection 06 MS-AT-30): the opponent-client frames - the first opponent move in flight (its
  // first plan's mid point, MS-T-16 / DE-021) and its last-move highlight + feed line just after it (MS-T-17).
  bool bS09ShotOppMove = false;
  bool bS09ShotOppLast = false;
  float ShotOppMoveAtElapsed = -1.0f;
  float ShotOppLastAtElapsed = -1.0f;
  // Run E G-LIVE: one frame each of the S11e HUD moments that only a live match shows - the first own-turn banner
  // (DE-023), the first hand-limit rule toast (DE-024) and the first source-card slot per owner (DE-026).
  bool bS09ShotBanner = false;
  bool bS09ShotHint = false;
  bool bS09ShotSlotOpp = false;
  bool bS09ShotSlotOwn = false;
  float ShotBannerAtElapsed = -1.0f;
  float ShotHintAtElapsed = -1.0f;
  float ShotSlotOppAtElapsed = -1.0f;
  float ShotSlotOwnAtElapsed = -1.0f;
  // Run I acceptance (AB-8): one frame of the first "no defense" stamp (marker-x-stamp) in the combat panel.
  bool bS09ShotStamp = false;
  float ShotStampAtElapsed = -1.0f;
  // Run F G-LIVE (DE-031): the deck side panel (DE-030) in a live match - the auto client opens it in the opponent's
  // turn once both discard piles hold a card, frames my deck, then the opponent's, and leaves it open so my next turn
  // closes it (trace 'DECK panel close ... why=input:turn'); the final board of the result screen (DE-029).
  bool bS09ShotDeckOwn = false;
  bool bS09ShotDeckOpp = false;
  int32 S09DeckShotStage = 0;  // 0 idle, 1 own open, 2 own shot asked, 3 opp open, 4 done
  int32 S09DeckShotTries = 0;
  int32 S09DeckShotTurn = -1;  // one attempt per opponent turn (the auto client's turns are short)
  float S09DeckShotAt = -1.0f;
  bool bS09ShotResultBoard = false;
  float ShotResultBoardAtElapsed = -1.0f;
  FString S09ShotResultBoardPath;
  // Run F G-LIVE (DE-026 tail): -S09SchemeQuiet=<s> - after its own scheme the auto client waits this long before its
  // next ACTION (the scheme's own choices are still answered at once), so the opponent's slot releases the held
  // scheme by time (release=time) instead of by the next action. 0 (default) = off.
  float S09SchemeQuietSec = 0.0f;
  float S09SchemeQuietUntil = -1.0f;
  int32 LastSeenTurnCount = -1; // S09 auto: own-turn boundary detection
  // Rate-limited diagnostics (a stranded mandatory head used to emit one
  // trace line per tick - 98k lines / 9.7 MB in the GD-035 capture).
  FString S09PendingWaitTraceKey; // head id already logged as unanswerable
  // Bounded auto-answers per pending head: once
  // that many ACTUALLY DISPATCHED server commands left the SAME head open
  // (server reject / lost mutation), the driver stops re-answering it - one
  // diagnostic, the stuck head stays visibly blocked instead of flooding the
  // trace with retries. Gate-blocked ticks consume no budget (P1(1)).
  FS09AutoSendBudget S09PendingAutoBudget{3};
  // S10 review P1(5): bounded attack retries per turn - every definitive
  // server rejection of a dispatched attack (e.g. the 401-answered case)
  // closes the AttackDraft and counts here; a fresh turn re-opens the window.
  FS09AutoSendBudget S09AttackAutoBudget{3};
  FString S09AttackRejectTraceKey; // turn already traced as retry-exhausted
  FString S09RevealTraceKey;      // combat target+seq already traced revealed
  FString S09PendingRevealTraceKey;  // same, for the owner PENDING panel's revealed line
  // DE-020: the deferred-choice service (skipped-effect notes, modal / compact / toast, collapse, memory).
  FS09SkippedEffectsFeed SkippedEffects;
  FS09PendingPresenter PendingPresenter;
  FString PendingStepTraceKey;      // MS-PENDING step=... once per (head, step)
  FString PendingNoTargetsTraceKey; // MS-REJECT pending.no.targets once per head
  FString S09ResolveBlockedTraceKey; // pending head already traced as blocking resolve
  FString S09ShotBlockedPath;     // resolve window blocked by the other seat's pending
  FString S09BoostHoldKey;        // BOOST_CHOICE head already held for the reveal capture
  float S09BoostHoldUntil = -1.0f;
  FString S09ShotDir;
  // ---- GD-036 result/lobby-return drive state ----
  bool bS09ShotResultScreen = false;   // result-screen capture requested
  FString S09ShotResultScreenPath;     // hold the lobby leave until it exists
  float ShotResultScreenAtElapsed = -1.0f; // bounded 12s wait for that file
  // Elapsed when the result panel was first BUILT; the capture waits a
  // settle interval past it so Slate has painted many full frames before
  // the shot (the 11:47 run caught the host panel mid-paint).
  float ResultPanelBuiltAtElapsed = -1.0f;
  bool bS09LobbyReturnSent = false;    // leaveGame sent exactly once
  bool bS09AutoLeaveRetryBlocked = false; // a failed auto leave needs a manual retry
  bool bS09ShotLobby = false;          // lobby-arrival capture requested
  FString S09ShotLobbyPath;
  float ShotLobbyAtElapsed = -1.0f;
  // Lobby capture waits until the transition toast cleared + a settle beat.
  float LobbyShotNotBeforeElapsed = -1.0f;
  bool bS09DuelComplete = false;       // result+lobby evidence done -> exit
  int32 S09ResultTraceSeq = -1;        // dedupe: one RESULT trace line per seq
  // ---- S10/GD-040 packaged ABORTED proof drive (opt-in -S10AbortProof) ----
  bool bS10AbortProof = false;
  FS10AbortProofTransitions::EStep S10AbortProofStep =
      FS10AbortProofTransitions::EStep::Idle;
  bool bS10AbortScreenShotTaken = false; // one s10-aborted-screen.png request
  FString S10AbortScreenShotPath;
  float S10AbortScreenShotAtElapsed = -1.0f; // bounded 12s wait for that file
  float S10AbortPanelBuiltAtElapsed = -1.0f; // interruption-panel paint settle
  bool bS10AbortLeaveSent = false;        // one leaveGame - the only post-abort send
  bool bS10AbortLobbyShotTaken = false;   // one s10-aborted-lobby.png request
  FString S10AbortLobbyShotPath;
  float S10AbortLobbyShotAtElapsed = -1.0f;
  float S10AbortLobbyNotBeforeElapsed = -1.0f; // toast cleared + settle beat
  bool bS10AbortProofComplete = false;    // early exit fired exactly once
  // W4-A -Bench: backend-less render bench on a captured game state of an original map
  // (default Config/Bench/S08BenchMarmoreal.json): warm-up, per-view frame/GPU timing,
  // ProfileGPU, optional CSV GPU stats and one shot per view (K1, K2 5x) with
  // the RENDER fingerprint. Driver: tools/art/render/render_bench.py.
  bool bBench = false;
  FString BenchViewerId;   // fixture player whose fighters are "own" (blue)
  FString BenchBoardId;    // Board row id of the fixture (art profile match)
  void RunRenderBench();
  // ---- MS-T-08 move plates (S08MoveHighlight.h, S08FlowGameModeMoveDraft.cpp) ----
  /** The board's view provider: the plates of the CommandUi draft (draft / inspection / pending MOVE-PLACE); false =
   *  the plain reachable set (legacy quick select, other pending types). */
  bool BuildMoveDraftViewFor(const FString& FighterId, const TSet<uint64>& Reachable, FS08MoveDraftView& OutView);
  /** Tick: re-draws the plates when the draft changed without a selection change (assign, boost, order, in flight). */
  void SyncMovePlates();
  /** -BenchMoveDraft=<abs path> (04 §6.4): the draft of the fixture file over the bench game state; false with the
   *  reason (a 'MS-BENCH mismatch id=' id, a refused operation) - the bench then takes no frame. */
  bool ApplyBenchMoveDraft(const FS08Snapshot& Snapshot, const FString& Path, FString& OutError);
  bool bBenchMoveDraft = false;
  /** -BenchMovePose=<ms> (DE-021, W-12 A/B frames for DE-028): a hero plays a two-edge move onto its own fixture cell
   *  (FS08MoveAnim::ReviewPath) with the -S08MoveHop= / -S08MoveLean= / -S08MoveEase parameters, held <ms> into the
   *  move for every view (the move clock stays at BenchMovePoseClockMs). The figure: -BenchMovePoseFighter=<id>, else
   *  the viewer's hero (PreferredId), else the first other hero, else any fighter with a free two-edge approach.
   *  OutPosedId = that figure (the K2 views focus it); false with the reason. */
  bool ApplyBenchMovePose(const FString& PreferredId, double HoldMs, FString& OutPosedId, FString& OutError);
  bool bBenchMovePose = false;
  int64 BenchMovePoseClockMs = 0;
  // ---- Z-1 figures (S08FlowGameModeFigures.cpp, ВР-Z1R-01): the clip-pose stand and the facing adapters ----
  /** AN-17 (ВР-17): -BenchClipPose=<Clip>@<f1>,<f2>[;<Clip>@...] (+ -BenchClipPoseFighter=<key|id>, which sets
   *  InOutHeroId for the K2 views) of Cmd; true with at least one pose. A bad list is traced and gives no poses. */
  bool BenchParseClipPoses(const TCHAR* Cmd, TArray<S08HeroesV2::FBenchClipPoseSpec>& OutPoses, FString& InOutHeroId,
                           int32 ViewCount);
  /** AN-17: every living v2 figure holds Spec (frozen); traced per figure + one summary; returns the posed count. */
  int32 BenchHoldClipPoses(const S08HeroesV2::FBenchClipPoseSpec& Spec, int32 PoseNumber, int32 PoseCount);
  /** AN-17: bench-<view>-<clip>-f<NN>|-q<pct>-1920x1080.png. */
  static FString BenchClipPoseShotName(const FString& View, const S08HeroesV2::FBenchClipPoseSpec& Spec);
  /** AN-17 (ВР-17): 'ARTPREVIEW figrect fighter=<id> view=<view> x y w h' per living v2 figure of a -BenchClipPose
   *  view - the screen rectangle of the figure with its pedestal (the component bounds, projected). */
  void BenchTraceFigRects(const FString& View);
  /** AN-24 / AN-25 (ВР-06): the figure side of one combat staging event - Face turns the attacker to the target,
   *  Lunge commits a deferred snap (reduced motion / speed "none"), End returns an attacker that played no clip. */
  void FiguresOnCombatEvent(const FS09CombatStageEvent& Event);
  /** F4: hands the game clock (NowMs) to a freshly spawned board actor for the FACING traces. */
  void FiguresAttachBoard();
  /** Space under the cursor of the plates (MS-T-09 drives it live; the bench fixture's "hover" now). */
  FIntPoint MoveHoverCell = FIntPoint(-1, -1);
  uint32 MovePlatesKey = 0;
  // ---- MS-T-17 the opponent view (S09OpponentView.h, S08FlowGameModeOpponent.cpp) ----
  /** An applied snapshot: the planning indicator (MS-S-11, 'MS-OPP planning='), the MS-P-03 tracker and the feed. */
  void FeedOpponentView(const FS08Snapshot& Snapshot);
  /** Tick: the reveal after the move animation, the fade, the event-feed line, the edge arrow. */
  void TickOpponentView();
  /** V-14 / V-15 of the tracker for the plates (empty when nothing is drawn). */
  FS08MoveDraftInput::FLastMove LastMovePlateInput() const;
  /** The edge-arrow slot of the HUD canvas (BuildHudWidgets). */
  void BuildOpponentHudWidgets(const TSharedRef<SConstraintCanvas>& Canvas);
  /** The indicator and the feed lines of RefreshHud (side panel / over the hand). */
  void AddOpponentPanelLines();
  void AddEventFeedLines();
  FS09LastMoveTracker LastMoveTracker;
  FS09EventFeed EventFeed;
  bool bOpponentPlanning = false;
  bool bOpponentPlanningKnown = false;
  S09OpponentView::FEdgeArrow EdgeArrowNow;
  FString EdgeArrowTraceKey;
  SConstraintCanvas::FSlot* EdgeArrowSlot = nullptr;
  TSharedPtr<STextBlock> EdgeArrowGlyph;
  // ---- DE-022 (W-13): the opponent's verb, the action tracker, my fighter moved by the opponent's effect and the
  // "what to do now" line (S09OpponentView.h, S09TurnStatus.h, S08FlowGameModeOpponent.cpp) ----
  /** The tracker row of a side ("actions" + one block per slot, spent = opacity 0.4 as the v3 spend). */
  void AddActionTrackerRow(bool bOpponent);
  /** "Your fighter X: Y effect" over the feed while the opponent's effect moves my fighter. */
  void AddYoursCalloutLine();
  /** The "what to do now" line over the hand (traced 'MS-STATUS text=' on change). */
  void AddTurnStatusLine();
  FS09TurnStatusInput BuildTurnStatusInput() const;
  /** The hero name of a player (the feed's {player}); "You" / "Opponent" without a hero on the board. */
  FString PlayerHeroName(const FString& PlayerId) const;
  FString ViewerIdNow() const;
  ES09OpponentVerb OpponentVerbNow = ES09OpponentVerb::None;
  bool bOpponentVerbKnown = false;
  FS09ActionTracker ActionTracker;
  FS09EffectSources EffectSources;
  /** The EFFECT trail of the last applied seq: its source card and my fighters it moved (the feed line at reveal). */
  int32 EffectTrailSeq = -1;
  FString EffectTrailCard;
  TArray<FString> EffectTrailYours;
  /** The callout of 03 §7 п. 3: from the trail's snapshot until its move animation ended and >= 1000 ms passed. */
  bool bYoursCallout = false;
  FString YoursCalloutText;
  double YoursCalloutSinceMs = 0.0;
  FString TurnStatusTraceKey;
  // ---- DE-023 (W-15 HUD; 01 F-07, F-12): the persistent UMG portraits (ring, tracker, heart) and the "Your turn"
  // banner (S09/S09TurnHud.h, S08/S08TurnPortraitWidget.h, S08FlowGameModeTurnHud.cpp) ----
  /** Builds the two portraits (bottom-left column: the opponent above, mine below) and the banner; art look only. */
  void BuildTurnHudWidgets(const TSharedRef<SConstraintCanvas>& Canvas);
  /** VS-3 (VS-2 review): the UMG root failed without -S08SlateHud - the Slate portrait column after all (UmSlatePortraits.h). */
  void BuildTurnPortraitFallback(const TCHAR* Reason);
  TWeakPtr<SConstraintCanvas> TurnHudCanvas;
  /** An applied snapshot: the turn cue (ring, banner), the tracker's server marks and turn reset. */
  void FeedTurnHud(const FS08Snapshot& Snapshot);
  /** Every frame: names / HP / heart events from the HUD fighters, the tracker marks (local choice), the opponent
   *  tracker fade, the banner opacity, visibility. */
  void TickTurnHud();
  /** The own action was just chosen and sent (beginManeuver / attack / scheme): the tracker marks it before the answer. */
  void NoteActionChosen(const TCHAR* What);
  /** True while the portraits carry the trackers (the Slate tracker rows of DE-022 are then not drawn). */
  bool TurnHudTrackers() const { return OwnPortrait != nullptr; }
  FS08TurnHudLook TurnHudLook;
  FS09TurnCue TurnCue;
  FS09TrackerMarks TrackerMarks;
  FS09HeartWatch OwnHeart;
  FS09HeartWatch OpponentHeart;
  /** Run I (AB-7): the type of the own action last chosen (NoteActionChosen) - the DE slot of the local mark. */
  FName OwnChosenType;
  bool bTrackerResetPending = true;
  bool bTurnRingAtRest = false;
  FString TurnHudShownKey;
  TSharedPtr<class SBorder> TurnBanner;
  /** The bottom-left column of the two portraits (an obstacle of the hand panel and of the fighter plate). */
  TSharedPtr<class SVerticalBox> TurnPortraitColumn;
  /** Run E review: the right edge of the portrait column (slate units) while it is shown, else 0. */
  float HandObstacleRightSu() const;
  FString HandLayoutTraceKey;
  // ---- DE-024 (W-23; 02 SD-42, SD-43): the hand limit - the one-shot rule toast (UI-ACC-012) over the hand strip and
  // one discard picker for the limit and an effect's DISCARD_CARDS (S09/S09HandLimit.h, S08FlowGameModeHandLimit.cpp) ----
  /** The persistent rule toast (built once inside the hand panel, collapsed until shown; a hit-test target only over
   *  itself, never focusable - keys and board clicks stay with the game). */
  TSharedRef<SWidget> BuildHandLimitHint();
  /** An applied snapshot: the toast shows the first time in the match the own hand grows to the limit, closes at the
   *  end of that turn or GAME_OVER. */
  void FeedHandLimitHint(const FS08Snapshot& Snapshot);
  /** A click on the toast closes it for the rest of the match. */
  void DismissHandLimitHint();
  void ApplyHandLimitHintVisibility();
  FS09HandLimitHint HandLimitHint;
  bool bRuleHints = true;
  bool bRuleHintOffTraced = false;
  TSharedPtr<class SBox> HandHintBox;
  TSharedPtr<class STextBlock> HandHintText;
  // ---- DE-026 (W-18; 01 F-10; 02 SD-02, SD-26, SD-28 п. 4, SD-54): the hand lowered during a board pick and the
  // source-card slot (S09/S09CardSlot.h, S08FlowGameModeCardSlot.cpp) ----
  /** The slot at the top left, under the command panel (built once; hit-test invisible - a click on it is a click
   *  on the field, i.e. the skip of the opponent's scheme hold). */
  void BuildCardSlotWidgets(const TSharedRef<SConstraintCanvas>& Canvas);
  /** An applied snapshot (before the board sync): a new seq releases a held effect, a played card enters the slot;
   *  the opponent's scheme holds the fighters of FightersBefore and the cues of its seq. */
  void FeedCardSlot(const FS08Snapshot& Snapshot, const TArray<FS08BoardFighter>& FightersBefore);
  /** Every frame: the slot's times, the release of the held effect, the hand lowering, the widgets. */
  void TickCardSlot();
  /** A click / Space / Enter during the hold of the opponent's scheme starts its effect. True when the input is
   *  consumed (the hold hides my own choice it opened, or the skip happened in the opponent's turn). */
  bool TryCardSlotSkip();
  /** HandleCues: the cues of the held seq and of its continuations wait for the release (true = held). */
  bool HoldCardSlotCues(const TArray<FS08Cue>& Cues);
  /** HandleCues: the held moves released by this newer seq join its own cues (true, OutJoined = the set to play). */
  bool TakeCardSlotCarry(const TArray<FS08Cue>& Cues, TArray<FS08Cue>& OutJoined);
  /** The carried held moves play alone (the newer seq brought no cues, or other cues came first). */
  void FlushCardSlotCarry();
  /** The fighters as they stood before the held opponent's scheme (HUD view and board view). */
  void ApplyCardSlotHold(TArray<FS08BoardFighter>& View) const;
  /** The held effect starts: the board and the HUD go to the snapshot, the held cues play (bPlayCues) or are
   *  dropped. CarryToSeq >= 0: released inside the apply of that newer seq - the held moves wait for its cues and
   *  play joined with them (run E review: never dropped). */
  void OnCardSlotReleased(bool bPlayCues, const TCHAR* Why, int32 CarryToSeq = -1);
  void RebuildCardSlotWidget();
  /** The OS cursor is over a HUD panel (the lowered hand counts with its raised rectangle). False without a cursor. */
  bool CursorOverHud() const;
  FS09PlayedCardWatch PlayedCards;
  FS09SourceSlot CardSlot;
  FS09HandLower HandLower;
  TArray<FS08BoardFighter> SlotHeldFighters;
  TArray<FS08Cue> SlotHeldCues;
  TArray<FS08Cue> SlotCarryCues;  // released held moves waiting for the cues of SlotCarrySeq (same frame)
  int32 SlotCarrySeq = -1;
  uint32 CardSlotBuiltRevision = MAX_uint32;
  bool bCardSlotHidesChoice = false;
  bool bHandPreviewHidden = false;
  bool bCardSlotQueueOpen = false;    // pendingEffects of the last applied snapshot not empty (the effect runs)
  bool bCardSlotBuiltHolding = false;
  float HandOffsetApplied = 0.0f;
  TSharedPtr<class SBox> CardSlotBox;
  /** One -Bench view's camera: selection + zoom per the view name, traced 'BENCH view=...' (RunRenderBench case 2;
   *  also the live-tune shot). */
  void BenchSetupView(const FString& View, const FString& HeroId);
  /** RunRenderBench case 3: the camera within 1 % / 1 uu of its target. */
  bool BenchCameraSettled() const;
  // ENV-MAPS live tune (S08LiveTune.h, S08FlowGameModeLiveTune.cpp): -ArtLiveTune=<dir> with the -Bench flags turns the
  // bench into a file-protocol server after its fixture init. Null without the flag.
  TSharedPtr<struct FS08LiveTuneSession> LiveTune;
  /** Bench init: the session (journal marks) before the board build; called by RunRenderBench. */
  void LiveTuneBeforeBuild();
  void LiveTuneAfterBuild(float BenchWarmup, float BenchSettle, float BenchMeasure, float BenchFps, const FString& Fixture,
                          const FString& HeroId);
  void RunLiveTune();
  void LiveTuneHandleCommand(const FString& Path, int32 Seq);
  void LiveTuneReload(const struct FS08LiveCommand& Cmd, struct FS08LiveResult& Result);
  void LiveTuneStartShot();
  void LiveTuneShotTick();
  void LiveTuneFinishShot(bool bOk, const FString& Error);
  void LiveTuneSetClocks(float Target, const FString& View);
  void LiveTuneWriteDone(struct FS08LiveResult& Result);
  TSharedPtr<class FJsonObject> LiveTuneState() const;
  // Art Tuner M1 (S08ArtView.h, S08FlowGameModeArtView.cpp, docs/art-pipeline/ART-TUNER-PLAN.md): -ArtView=<map> = the -Bench
  // fixture init without a backend and without the view walk, a free camera and live fx. Null without the flag.
  TSharedPtr<struct FS08ArtViewSession> ArtView;
  void ArtViewBegin();
  void ArtViewAfterBuild(const FString& HeroId);
  void ArtViewTick(float DeltaSeconds);
  void ArtViewSetView(const FString& View);
  void ArtViewRefreshOverlay();
  /** -ArtTuner on the command line (the panel; S08ArtTuner.h). */
  bool ArtTunerEnabled() const;
  // HUD icon motion v3 (S08AnimatedIconWidget.h, S08FlowGameModeIconGallery.cpp, ICON-MOTION-PLAN.md):
  // -S08IconGallery = backend-less gallery of every icon looping its demo script; -S08IconGalleryShots=<dir>
  // with -S08IconGalleryTimes=<ms,ms,...> freezes the clock at each time and takes a UI shot, then exits.
  bool IconGalleryBegin();
  void IconGalleryTick(float DeltaSeconds);
  /** DE-023 review tooling (-S08IconGallery -S08IconGalleryPortraits): the two turn portraits over the gallery with
   *  sample data, replayed at the gallery clock (ring appear, a spent slot and the heart damage all start at 0).
   *  bFromBenchFixture (DE-028, -Bench -BenchTurnHud=<ms>): the names, HP and team colours of the bench fixture's two
   *  heroes instead of the sample, over the real board - the A/B sheet frames of the ring, the tracker and the heart. */
  void GalleryPortraitsBegin(bool bFromBenchFixture = false);
  void GalleryPortraitsAt(float TMs);
  bool bIconGallery = false;
  FString IconGalleryShotDir;
  TArray<float> IconGalleryTimes;
  int32 IconGalleryShot = 0;
  int32 IconGalleryWait = 0;
  bool bIconGalleryShotPending = false;
  int32 IconGalleryPerfLeft = -1;
  int32 IconGalleryPerfTotal = 0;
  TArray<float> IconGalleryGtMs;
  TArray<float> IconGalleryGtHiddenMs;
  // Art Tuner M2/M3 (S08ArtTuner.h, S08FlowGameModeArtTuner.cpp, S08ArtTunerPanel.cpp): the panel's model, apply, save and
  // the live-tune actions tune / tunerState / tunerSave / tunerReset / tunerPanel / artView. Null without -ArtTuner.
  TSharedPtr<struct FS08ArtTunerSession> ArtTuner;
  bool bArtTunerFlag = false;
  /** The profiles path of the last live-tune reload (the tuner's base; empty = the startup source). */
  FString ArtTunerProfilesPath;
  void ArtTunerTick();
  bool ArtTunerBegin();
  void ArtTunerEnd();
  bool ArtTunerRebase(const FString& ProfilesPath, TArray<FString>& OutWarnings);
  /** The one path of a value change (panel row, live-tune "tune", the saved file at start): registry row -> validated
   *  writes -> the model -> the profile parser; a refused document leaves the model unchanged. */
  bool ArtTunerSetValue(const FString& PointerOrId, const TSharedPtr<class FJsonValue>& Value, FString& OutError);
  /** Pushes the pending document onto the board (throttled unless bForce). */
  void ArtTunerApplyPending(bool bForce);
  bool ArtTunerSave(const FString& PathOverride, FString& OutPath, FString& OutError);
  /** One group (empty = all) back to the profile file's values. */
  void ArtTunerReset(const FString& GroupId);
  void ArtTunerSetPanelOpen(bool bOpen);
  /** One row back to the profile file's value (the panel's reset arrow). */
  void ArtTunerResetRow(const FString& RowId);
  TSharedPtr<class FJsonObject> ArtTunerState() const;
  void LiveTuneTuner(const struct FS08LiveCommand& Cmd, struct FS08LiveResult& Result);
  void LiveTuneArtView(const struct FS08LiveCommand& Cmd, struct FS08LiveResult& Result);
  // -S09HudProbe=<dir>: backend-less packaged probe - renders the fixture-04
  // HUD states and captures UI-inclusive shots + a Slate key-input check.
  bool bS09Probe = false;
  FString S09ProbeDir;
  int32 S09ProbeStep = 0;
  float S09ProbeNextAt = 0.0f;
  int32 S09KeyProbeSeen = 0;
  // Key-route split (P1): 1 = armed for the real Slate event path, 2 = armed
  // for the direct PlayerController::InputKey fallback, 0 = idle.
  int32 S09KeyRouteArmed = 0;
  int32 S09SlateKeySeen = 0;
  int32 S09DirectKeySeen = 0;
  int32 S09ProbePickCount = -1;
  FS08Snapshot S09ProbeSnapshot;
  TSet<FString> S09ProbePreviousIds;

  UPROPERTY()
  TObjectPtr<AS08BoardActor> BoardActor;

  UPROPERTY()
  TObjectPtr<ACameraActor> BoardCamera;

  // D-10 wheel/Space/flag zoom (distance + follow focus); parameters in
  // FS08CameraZoomConfig (ART-004 T2.2 - values are Q-302 proposals).
  FS08CameraZoom CameraZoom;
  FS08ArtHudRuntime ArtHud;
  // Keeps the exact-size combat icon textures alive while the brush uses them.
  UPROPERTY()
  TArray<TObjectPtr<UObject>> ArtHudAssets;
  // DE-032: the loaded CUE sounds by soft path (null entries = a path that did not load; warned once).
  UPROPERTY()
  TMap<FString, TObjectPtr<UObject>> CueSoundAssets;
  // AU-S4: the two layers of the theme, the VO voice and the ambience beds.
  UPROPERTY()
  TObjectPtr<class UAudioComponent> MusicL1;
  UPROPERTY()
  TObjectPtr<class UAudioComponent> MusicL2;
  UPROPERTY()
  TObjectPtr<class UAudioComponent> VoAudio;
  UPROPERTY()
  TArray<TObjectPtr<class UAudioComponent>> AmbBeds;
  // AU-S5: the limiter with the make-up gain on the main submix (null with -S08MixLegacy).
  UPROPERTY()
  TObjectPtr<class USoundEffectSubmixPreset> MasterLimiter;
  // W4-C: the UMG art HUD widgets (plate, icon) hosted in HudCanvas slots.
  UPROPERTY()
  TArray<TObjectPtr<UUserWidget>> ArtHudWidgets;
  // -S08IconGallery: the gallery widget (null without the flag).
  UPROPERTY()
  TObjectPtr<class US08IconGalleryWidget> IconGallery;
  // DE-023: the persistent portraits (null without the art look).
  UPROPERTY()
  TObjectPtr<US08TurnPortraitWidget> OwnPortrait;
  UPROPERTY()
  TObjectPtr<US08TurnPortraitWidget> OpponentPortrait;
  UPROPERTY()
  TArray<TObjectPtr<US08TurnPortraitWidget>> GalleryPortraits;
  // Run I (AB-8): the marker-x-stamp of "no defense" in the combat panel - one persistent widget (RefreshHud rebuilds
  // the panel; the stamp plays its appear once per combat, NoDefenseStampKey).
  UPROPERTY()
  TObjectPtr<class US08AnimatedIconWidget> NoDefenseStamp;
  FString NoDefenseStampKey;
  // ---- VS-6 Z-2 FX base (S08/Fx/S08CueFxSpawner.h, the adapter in S08FlowGameModeFx.cpp) ----
  /** FX-03: the registry spawner (prewarm, spawn, grade) of the combat VFX base. */
  UPROPERTY()
  TObjectPtr<class US08CueFxSpawnerComponent> CueFxSpawner;
  /** FX-03: prewarm + the dispatcher's vfx / clip / sfx asset resolver + the profile grade; once per board. */
  void S08FxBoardReady();
  /** FX-06: the hover moved between figures (or left): the CUE-001 row + the rim of FX-05. */
  void S08FxHoverChanged(const FString& NewId, const FString& OldId);
  /** FX-17: CUE-009 defense played - the cream rim pulse on the defender (ВР-23). */
  void S08FxDefensePlayed(const FString& DefenderId);
  /** Z-2: -BenchFx=<mode> - a deterministic FX state for the bench views (the FX-02 placard; the rim / flash
   *  channel frames of FX-06/17/19 written straight to CPD, the curves stay in the unit tests and the demo). */
  void S08FxBenchStep(const FString& Spec);
  // ---- VS-2 HB-06: the UMG HUD root, its layout / FIELD and the H2 layout fixes of the Slate blocks
  // (S08FlowGameModeUmHud.cpp; rollback -S08SlateHud[=<blocks>]) ----
  void BuildUmHud();
  void UpdateUmHudField(const FVector& CameraLocation, const FRotator& CameraRotation, float HFovDeg);
  void RefreshUmHudLayout();
  void HandleUmHudScaleChanged(const struct FUmHudScaleState& State);
  void HandleUmHudEndPlay();
  void WriteUmHudShotLines();
  void TickUmHud();
  void UmHudDeckPanelLayering(float DeckAlpha);
  bool UmHudBlockOnSlate(const TCHAR* Key) const;
  TSharedRef<SWidget> UmHudWrapEdge(const TSharedRef<SWidget>& Edge, bool bLeft);
  float UmHudHandLowerCap(float OffsetSu) const;
  FMargin UmHudToastOffset() const;
  void UmGalleryBegin(int32 SizePx);
  /** VS-3: the gallery clock reaches the card sheets (-S08IconGalleryCards). */
  void UmGalleryAt(float TMs);
  // VS-2 HB-14...HB-16: TOP + CONN, STATUS and the banner (S08/UI/UmHudTop, UmHudStatusLine, UmHudBanner)
  void BuildUmTopStrip();
  void TickUmTopStrip();
  /** The UMG STATUS took the line (false: -S08SlateHud=status, the Slate text in the hand panel stays). */
  bool ApplyUmHudStatus(const FS09TurnStatusInput& In);
  void HandleUmTopPress(const TCHAR* What);
  // VS-2 HB-18...HB-21: PANEL-LOC, PANEL-OPP, OPP-HAND (S08/UI/UmHudPanels.h)
  void BuildUmPanels();
  void TickUmPanels();
  /** The right edge of PANEL-LOC (su) for the hand obstacle; -1 when the panels are on the Slate path. */
  float UmHudPanelLocRightSu() const;
  // VS-3 HB-24 / HB-25: HAND (S08/UI/UmHudHand.h; rollback -S08SlateHud=hand)
  void BuildUmHand();
  /** Feeds the UMG hand from the applied snapshot and the command state; false = the Slate chips draw the hand. */
  bool RefreshUmHand();
  bool UmHandOnUmg() const;
  void HandleUmHandPress(const FS09HudPressOutcome& Outcome, const FString& InstanceId);
  void HandleUmHandPlay(const FString& InstanceId);
  void HandleUmHandInspect(const FString& InstanceId);
  /** The pointer (viewport px) is over the UMG hand (its resting rows, raised): the SD-26 lowering waits. */
  bool UmHudCursorOverHand(float X, float Y) const;
  // VS-3 HB-27 / HB-28 / HB-47: DECKS and the deck panel (S08/UI/UmHudDeckBlocks.h, UmHudDecks.h, UmHudDeckPanel.h; rollback
  // -S08SlateHud=decks|deckpanel)
  void BuildUmDecks();
  /** Feeds the chips and the visible panel (the applied snapshot, the deck lists, the side, the filter). */
  void RefreshUmDecks();
  /** The UMG panel's opacity and skeleton each frame; false = the Slate panel draws (TickDeckPanel goes on). */
  bool TickUmDeckPanel(float Alpha);
  bool UmDeckPanelOnUmg() const;
  /** D and the discard chip: the panel on «Ваша» with «Только сброс» (the Slate discard browser merged into it). */
  void OpenUmDeckDiscard(const TCHAR* Why);
  void HandleUmDeckRowInspect(const FString& CardId);
  bool UmHudCursorOverDeckPanel(float X, float Y) const;
  // VS-3 HB-30...HB-33: the combat edges and centre (S08/UI/UmHudCombatBlocks.h; rollback -S08SlateHud=combat |
  // combatcenter); fed every frame (the staging's clock, the 4 Hz timer runs in the edge)
  void BuildUmCombat();
  void RefreshUmCombat();
  /** The UMG edges draw the combat (the Slate edge panels stay empty). */
  bool UmCombatOnUmg() const;
  /** The UMG centre draws the score and the outcome (the Slate outcome box stays empty). */
  bool UmCombatCenterOnUmg() const;
  /** The UMG edge draws the defense window now and no gate layer asks for the Slate block (-S09Markers). */
  bool UmCombatOwnsDefenseWindow() const;
  // VS-4 HB-35 / HB-37 (S08/UI/UmHudPending.h, UmHudSourceSlot.h; rollback -S08SlateHud=pending | slot): the deferred
  // choice at CENTER and the source card at SLOT
  void BuildUmPending();
  /** Feeds UUmHudPending (RefreshHud and a cheap per-frame key: staging, slot hold, command in flight). */
  void RefreshUmPending();
  /** The UMG block draws the deferred choices: the Slate command panel gives up its pending / discard / ability / wait
   *  blocks and the lines of the attack draft and the resolve window (not under -S09Markers, ВР-VS4-02). */
  bool UmPendingOwnsCommandPanel() const;
  /** Esc with an own choice open: «Назад» or why.choice.required (true = answered). */
  bool UmPendingEscape();
  /** The source of the open own head as the UI names it ('' unknown) - STATUS «Сделайте выбор: {choice}». */
  FString UmPendingSourceName() const;
  bool UmSlotOnUmg() const;
  /** Every frame from TickCardSlot: FS09SourceSlot -> UUmHudSourceSlot. */
  void TickUmSourceSlot();
  // VS-4 HB-39...HB-41 (S08/UI/UmHudFeedBlocks.h; rollback -S08SlateHud=log | toast | sub): the log, the toasts, the
  // subtitle - the hooks of the feed, the toast producers, the VO line, the board refusal
  void BuildUmFeed();
  void TickUmFeed();
  /** A revealed trail's line (TickOpponentView, after FS09EventFeed took it). */
  void UmHudLogTrail(const struct FS09LastMovement& Trail, const FString& CardName, const TArray<FString>& YourFighters);
  /** ShowReason: the UMG toast of a keyed message (CUE-004 refusals, the skipped effect, ...). */
  void UmHudToastReason(const FS09Reason& Reason, float Seconds);
  /** RefreshUi: what the Slate toast line still shows - all of it with -S08SlateHud=toast, the non-keyed developer
   *  strings under -S09Markers, nothing in the default view (the keyed ones are UMG toasts). */
  FString UmHudSlateToast(const FString& Shown) const;
  /** OfferVoLine: the UMG capsule shows the line (true: the Slate SubtitleBox stays collapsed). */
  bool UmHudShowSubtitle(const FString& SpeakerName, const FString& Line, int64 DurationMs);
  void UmHudHideSubtitle();
  /** ApplyHandLimitHintVisibility: the hand-limit rule as a sticky warning toast (true: the Slate hint stays collapsed). */
  bool UmHudSyncHandLimit();
  /** A refused space (ShowIllegalCell): badge-refuse over it for 350 ms. */
  void UmHudRefuseCell(int32 CellX, int32 CellY);
  /** A refused HUD press (HandleHudPressOutcome): badge-refuse next to the button for 350 ms. */
  void UmHudRefusePress(FName PressedId);
  /** The open class S log list or a sticky toast's cross under the cursor (CursorOverHud). */
  bool UmHudCursorOverFeed(float X, float Y) const;
  // VS-4 HB-43 (S08/UI/UmHudActions.h; rollback -S08SlateHud=actions): ACTIONS - the four disc buttons; a click is the
  // key's command (DE-015: PressUmActionKey, the same path as M / A / G / E); UI-ACC-017 key hints (HUD-KEYHINTS)
  void BuildUmActions();
  /** Feeds UUmHudActions from the applied snapshot and the command state (RefreshHud and a cheap per-frame key). */
  void RefreshUmActions();
  bool UmActionsOnUmg() const;
  /** The command of a key: 0 M (maneuver), 1 A (attack draft toggle), 2 G (scheme; closes a local attack draft first,
   *  ВР-VS4-41), 3 E (end turn). The keys and the UMG cells call it. */
  void PressUmActionKey(int32 Key);
  /** Run B G-LIVE flag step 'hudendturn' on the UMG cell: a press and a release through UUmButton's handlers; false
   *  without the UMG block (the Slate element then). */
  bool PressUmEndTurnForFlag();
  /** UI-ACC-017 of this run (US08UserSettings::KeyHintsNow), traced 'HUD-KEYHINTS mode= shown=' on a change. */
  bool UmKeyHintsNow();
  /** VS-4 FX-38 (S08/UI/UmZoneBadges.h; rollback -S08SlateHud=zone): the zone icons of the hovered space, every frame. */
  void TickUmZoneBadges();
  // VS-4 V4 (H13) SC-21...SC-23 / CP-22: the UMG INSPECT modal (UI/UmScreenInspect.h; rollback -S08SlateHud=inspect)
  void BuildUmInspect();
  void TickUmInspect();
  bool UmInspectOnUmg() const;
  bool UmInspectShown() const;
  /** The open modal owns the keys; a right click on the slot card and the key I open it. True = input consumed. */
  bool UmInspectOwnsInput();
  struct FUmInspectContext UmInspectContextNow() const;
  void NoteUmInspectSource(uint8 Source);
  void OpenUmInspectDeck(bool bOwnSide);
  void HandleUmLogInspect(const FString& CardId);
  // VS-4 CP-21: the G-CUE lines of the played-card flash (CUE-006 subject=card)
  void UmNoteCardFlashes(const TArray<float>& Flashes, int32 Seq);
  void TickUmCardFlashCue();
  // VS-4 V4 evidence (opt-in -S08InspectShots): the H13 states and the HB-47 skeleton in a live match
  void NoteUmInspectShotsTurn(bool bOwn, bool bInitial, bool bGameOver);
  void TickUmInspectShots();
  /** VS-3 SC-01 (ВР-SC14): -S08ScreenShots - one evidence frame per new UI-SCR-* id + state (<UI-ID>-<state>.png). */
  void TickUmScreenShots();
  // VS-2 exit frames (opt-in -S08ExitShots): own / opponent turn start + 0.5 s and + 3 s
  void NoteUmExitShotsTurn(bool bOwn, bool bInitial, bool bGameOver);
  /** ВР-VS2-77: the late SHOT lines of the VS-2 blocks first shown in the shot frame. */
  void WriteUmHudLateLines();
  void TickUmExitShots();
  // VS-3 exit frames (opt-in -S08ExitShots, 05 §3 VS-3 sets A and C): the hover, the hand of 3 / 7 / 9, the attack
  // selected, the defense window on both clients, the reveal, the stamp; the auto attack / defense hold for their frames
  bool UmExitShotsOn();
  void TickUmExitShotsVs3();
  bool HoldUmExitAttack();
  void ResumeUmExitAttack();
  bool HoldUmExitDefense();
  // VS-4 exit frames (opt-in -S08ExitShots, HB-49 sets D and the VS-2 leftovers): the own pending head collapsed, the
  // software cursor over a hand card and a button (HB-12), the link states syncing / lost (HB-14), the turn banner
  // under the combat centre
  void TickUmExitShotsVs4();
  bool HoldUmExitPending();
  // VS-3 HUD budget (opt-in -S08HudPerf, HUD-RULES П8, UI/UmHudPerf.h): the UMG root collapsed / shown in blocks
  void TickUmHudPerf();
  void FinishUmHudPerf(const TCHAR* Why);
  UPROPERTY()
  TObjectPtr<class UUmHudRoot> UmHudRoot;
  UPROPERTY()
  TObjectPtr<UUserWidget> UmGallery;
  TSharedPtr<struct FUmHudRuntime> UmHud;

  FS08BoardModel BoardModel;
  TArray<FS08BoardFighter> Fighters;
  FString SelectedFighterId;
  TSet<uint64> ReachableCells;
  FString Toast;
  float ToastUntil = 0.0f;
  float IllegalUntil = 0.0f;
  bool bCommandSlowShown = false; // MS-E-89: the 3 s why.syncing banner of the open command
  // MS-T-07: input state of the move selection (boost panel, MS-S-04, the press).
  FS09MoveInput MoveInput;
  // DE-014: press arbitration of the Slate HUD by element id (survives RefreshHud).
  TSharedPtr<FS09HudPressArbiter> HudPress = MakeShared<FS09HudPressArbiter>();
  // DE-015: the TURN-INPUT trace pair - own-turn input open from the applied snapshot (SD-47).
  FS09TurnInputWatch TurnInputWatch;
  bool bLegacyQuickMove = false;      // -S08LegacyQuickMove: TASK-022 two-click move (MS-R-32)
  bool bAutoManeuverAwaitDraft = false; // -S08Maneuver: confirm once the draft opens (MS-R-62)
  FString AutoManeuverPlan;             // -S08ManeuverPlan=<plan>: run on the opened draft first (M1)
  bool bAutoManeuverNoStepTraced = false; // M1: "no free hero step" traced once
  // Run B G-LIVE (opt-in evidence): -S08ManeuverDraftHold=<s> keeps the opened draft (MS-S-06, the V-17 rings of
  // DE-017) s seconds before the plan / confirm; -S08ManeuverDraftShot=<abs png> takes the frame of it.
  float AutoManeuverDraftHold = 0.0f;
  FString AutoManeuverDraftShot;
  float AutoDraftOpenAt = -1.0f;
  bool bAutoDraftShotTaken = false;
  // Run B G-LIVE: the live element of each HUD id (MakeHudPress), for the flag step 'hudendturn' (DE-014).
  TMap<FName, TWeakPtr<SS09HudPress>> HudPressWidgets;
  FString TracedToast;             // the last toast written to the trace (MS-AT-18)
  int32 ManeuverTargetX = -1;
  int32 ManeuverTargetY = -1;
  bool bAwaitManeuverFinish = false; // begin leg sent, waiting for pending id
  int32 ManeuverStartSeq = 0;
  float ShotAtElapsed = -1.0f;

  float PollAccumulator = 0.0f;
  float Elapsed = 0.0f;
  bool bAuto = false;
  bool bAutoCreate = false;
  bool bAutoManeuver = false;
  bool bShotTaken = false;
  FS08ShotQueue EvidenceShotQueue; // I-03: one FScreenshotRequest per frame, FIFO
  bool bAutoManeuverDone = false;
  bool bSawCue = false; // joiner evidence shot trigger: an authoritative event arrived
  FString AutoEmail, AutoPassword, AutoCode, AutoHeroId, AutoShotPath;
  FString AutoCreateMode = TEXT("ONE_V_ONE"); // -S08Mode=VS_AI drives the auto create
  float AutoExitAfter = 0.0f;
  float AutoDropWsAfter = 0.0f; // >0: drop the live WS at this elapsed time
  bool bWsDroppedForTest = false;
  float AutoManeuverAfter = 0.0f; // >0: hold the auto maneuver until this elapsed time
  float ArtPreviewShotAfter = -1.0f; // optional live-board still when movement is blocked
  float ArtPreviewFocusZoom = 0.0f; // opt-in K2 probe: overview distance / zoom
  bool bArtPreviewSelectOwnHero = false;
  bool bArtPreviewDidSelectOwnHero = false;
  int32 AutoStep = 0;
  int32 AppliedCount = 0;
};

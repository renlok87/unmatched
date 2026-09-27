// GD-029/030/031: BOOT -> LOGIN -> LOBBY -> ROOM -> BOARD grey flow.
// Phase 2 renders the authoritative board + fighters from the applied
// snapshot (GD-030) and drives gameplay commands through the single state
// store with an in-flight gate (GD-031). Packaged demo drive:
//   -S08Auto -S08Create (host) or -S08Code=XXXXXX (joiner),
//   -S08HeroId=<prisma id>, -S08Maneuver (auto maneuver when the board is
//   live and it is this client's turn), -S08Shot=<abs path> (1920x1080
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
#include "../S09/S09HudModel.h"
#include "../S09/S09ManeuverUi.h"
#include "S08FlowGameMode.generated.h"

class SEditableTextBox;
class STextBlock;
class SVerticalBox;
class SHorizontalBox;
class AS08BoardActor;
class ACameraActor;

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

private:
  void BuildUi();
  void RefreshUi();
  void RunAutoDrive();
  void AutoAdvance();
  // ---- GD-030 board ----
  void HandleApplied(const FS08Snapshot& Snapshot, ES08SeqDecision Decision);
  void HandleCues(const TArray<FS08Cue>& Cues);
  void SyncBoardFromApplied();
  void SetupCameraForBoard();
  // ---- TASK-022 input ----
  void HandleClick();
  void SelectFighter(const FString& FighterId);
  void TryManeuverTo(int32 CellX, int32 CellY);
  void FinishPendingManeuver(int32 CellX, int32 CellY);
  // ---- GD-032/033 HUD + command UI ----
  void RefreshHud();
  void BuildHudWidgets();
  void HandleHudKeys();
  void HandleHandCardClick(int32 HandIndex);
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
  // ---- GD-034 combat UI ----
  void BeginAttackDraft();        // A: open the local attack draft
  void NoDefenseCommand();        // N: defender closes the window (no card)
  void ResolveCombatCommand();    // R: resolve (COMBAT_RESOLVE / no-defense)
  void DeclinePendingChoiceCommand(); // X: decline an optional boost choice
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
  void RunS09Auto();
  void TakeS09Shots();
  // ---- GD-036 result screen + lobby return ----
  /** LeaveGame from the result screen; safe to press repeatedly (one send). */
  void ReturnToLobbyCommand();
  /** S09AUTO tail: result shot -> leaveGame -> lobby shot -> early exit. */
  void DriveS09ResultFlow();
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
  /** GD-036: user-facing Lobby entry panel (authenticated user) rendered in
   *  the HUD overlay - the legacy grey-flow form stays an F10 overlay. */
  void BuildLobbyPanel();
  // Probe mode has no backend: handlers must read the fixture snapshot.
  const FS08Snapshot& EffectiveSnapshot() const {
    return bS09Probe ? S09ProbeSnapshot : Flow->GetAppliedSnapshot();
  }
  // ---- demo drive ----
  void RunAutoManeuver();
  void TakeEvidenceShot(const FString& InPath);

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
  TWeakPtr<STextBlock> ToastHudLine;    // gameplay toast (legacy panel hidden)
  TWeakPtr<class SBorder> ToastHudBorder;
  TSharedPtr<class SConstraintCanvas> HudCanvas; // root of the HUD overlay
  TWeakPtr<SEditableTextBox> LobbyCodeBox; // HUD lobby panel join-code field
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
    int32 Damage = 0;          // health the target lost in this combat
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
  // auto plan tokens: attack | defend | nodefense | resolve | scheme
  TArray<FString> S09CombatPlan;
  bool bS09ShotDefense = false;
  bool bS09ShotResolve = false;
  bool bS09ShotResult = false;
  bool bS09ShotResolveRevealed = false; // resolve window AFTER the reveal (GD-033 proof)
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
  int32 LastSeenTurnCount = -1; // S09 auto: own-turn boundary detection
  // Rate-limited diagnostics (a stranded mandatory head used to emit one
  // trace line per tick - 98k lines / 9.7 MB in the GD-035 capture).
  FString S09PendingWaitTraceKey; // head id already logged as unanswerable
  // Bounded auto-answers per pending head: once S09PendingAutoMaxSends server
  // commands left the SAME head open (server reject / lost mutation), the
  // driver stops re-answering it - one diagnostic, the stuck head stays
  // visibly blocked instead of flooding the trace with retries.
  FString S09PendingAutoKey;
  int32 S09PendingAutoSends = 0;
  FString S09RevealTraceKey;      // combat target+seq already traced revealed
  FString S09PendingRevealTraceKey;  // same, for the owner PENDING panel's revealed line
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

  FS08BoardModel BoardModel;
  TArray<FS08BoardFighter> Fighters;
  FString SelectedFighterId;
  TSet<uint64> ReachableCells;
  FString Toast;
  float ToastUntil = 0.0f;
  float IllegalUntil = 0.0f;
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
  bool bAutoManeuverDone = false;
  bool bSawCue = false; // joiner evidence shot trigger: an authoritative event arrived
  FString AutoEmail, AutoPassword, AutoCode, AutoHeroId, AutoShotPath;
  float AutoExitAfter = 0.0f;
  float AutoDropWsAfter = 0.0f; // >0: drop the live WS at this elapsed time
  bool bWsDroppedForTest = false;
  float AutoManeuverAfter = 0.0f; // >0: hold the auto maneuver until this elapsed time
  int32 AutoStep = 0;
  int32 AppliedCount = 0;
};

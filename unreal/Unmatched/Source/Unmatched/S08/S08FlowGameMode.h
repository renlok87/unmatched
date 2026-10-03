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
#include "S08ArtHud.h"
#include "../S09/S09HudModel.h"
#include "../S09/S09ManeuverUi.h"
#include "S08FlowGameMode.generated.h"

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
  // Wave 5c-B -ArtPreviewHeroesV2: the attacker's LungeAttack fires once per combat (at COMBAT_RESOLVE, or at
  // the close when the resolve snapshot was merged away).
  bool bCombatLungeSent = false;
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
  // W4-A -Bench: backend-less render bench on a captured Cobble game state
  // (Config/Bench/S08BenchCobble.json): warm-up, per-view frame/GPU timing,
  // ProfileGPU, optional CSV GPU stats and one shot per view (K1, K2 5x) with
  // the RENDER fingerprint. Driver: tools/art/render/render_bench.py.
  bool bBench = false;
  FString BenchViewerId;   // fixture player whose fighters are "own" (blue)
  FString BenchBoardId;    // Board row id of the fixture (art profile match)
  void RunRenderBench();
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
  // W4-C: the UMG art HUD widgets (plate, icon) hosted in HudCanvas slots.
  UPROPERTY()
  TArray<TObjectPtr<UUserWidget>> ArtHudWidgets;

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

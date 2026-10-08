// GD-029: BOOT -> LOGIN -> LOBBY -> ROOM grey flow over the GD-028 transport.
// Contract notes (unmatched-net/1):
//   - gameStateUpdated is the only authoritative state/recovery stream;
//     named lobby events carry no snapshot barrier, so lobby freshness comes
//     from mutation responses + game(id)/myGames re-query (recovery path).
//   - createGame retries reuse one stable idempotency key: a double create
//     must not produce a second room.
//   - joinGame takes gameId; the displayed room code is resolved safely via
//     the scoped gameByCode query (LOBBY + free slot only).
#pragma once

#include "CoreMinimal.h"
#include "S08BoardModel.h"
#include "S08Contracts.h"
#include "S08GraphqlClient.h"
#include "S08GraphqlWs.h"

enum class ES08Stage : uint8 { Boot, Login, Lobby, Room, Started, Failed };

struct FS08RoomPlayer {
  FString UserId;
  FString Username;
  FString HeroId;
  bool bIsReady = false;
  int32 SeatOrder = 0;
};

struct FS08RoomState {
  FString GameId;
  FString Code;
  FString Status;    // LOBBY | IN_PROGRESS | ...
  FString Mode;
  FString HostId;
  FString BoardId;
  FString StartedAt;  // DE-029: ISO 8601 from game(id) ('' = not read / null)
  FString EndedAt;    // set when the row went FINISHED
  TArray<FS08RoomPlayer> Players;
  bool IsHost(const FString& UserId) const { return UserId == HostId; }
};

/** Hero entry for the grey pick-a-pair screen (hero + sidekicks). */
struct FS08HeroEntry {
  FString Id;
  FString Name;
  int32 Health = 0;
  int32 SidekickCount = 0;
};

/** GD-031: presentation-layer cue derived from ONE authoritative state
 *  transition (a seq the store actually applied, not a same-seq merge).
 *  HTTP echo + WS event of the same seq produce exactly one cue set. */
/** VS-6 F2 FX-25 (ВР-FX13): FighterHealed - the HP of a fighter alive before and after the transition grew (Damage
 *  then carries the healed amount, HP after - HP before); after the damage cues of the seq. */
/** VS-6 F3 FX-28 (CUE-014): AbilityTriggered - Medusa's pending `ability-medusa-target-p<n>` (TARGET_FIGHTER) of the
 *  previous applied state is gone from metadata.pendingEffects and one of its targets lost HP; FighterId = Medusa's
 *  fighter, TargetId = the target, Damage = the HP it lost, HeroKey = Medusa. Before the damage cues of the seq. A
 *  decline (no HP lost) or no pending gives none. */
enum class ES08CueType : uint8 { FighterMoved, FighterDamaged, FighterHealed, AbilityTriggered };

/** MS-T-15 (move-selection 04 §4.6): how a FighterMoved cue travels - Move
 *  step by step along Path, Place as one jump to the last cell (steps = 1). */
enum class ES08MoveKind : uint8 { Move, Place };
/** MS-T-15 (04 §4.6, MS-R-48): where the Path of a FighterMoved cue comes
 *  from. Trail = metadata.lastMovement of this very seq; Canonical = the
 *  client canonical path on the positions BEFORE the snapshot with no step
 *  limit; Straight = from -> to when no such path exists. */
enum class ES08PathSource : uint8 { None, Trail, Canonical, Straight };

struct UNMATCHED_API FS08Cue {
  ES08CueType Type;
  int32 SequenceNumber = 0;
  FString FighterId;
  int32 FromX = 0, FromY = 0, ToX = 0, ToY = 0; // move
  int32 Damage = 0;                             // health decrease
  // ---- VS-6 F3 FX-28: AbilityTriggered only ----
  FString TargetId;                             // the fighter the ability damaged
  FString HeroKey;                              // S08HeroesV2 key of the hero (Medusa)
  int32 TargetHpBefore = -1;                    // FromX / FromY carry the target's cell before the blow
  // ---- MS-T-15: FighterMoved only ----
  /** Cells WITH the start: Path[0] = from, Path.Last() = to. Place: [from, to]. */
  TArray<FIntPoint> Path;
  /** 0..n-1 among the move cues of this seq: the trail's moves[] order
   *  first, then the fighters without a trail entry in fighters[] order. */
  int32 OrderInSeq = 0;
  ES08MoveKind Kind = ES08MoveKind::Move;
  ES08PathSource PathSource = ES08PathSource::None;
  /** The trail of this seq listed the fighter but did not match the snapshot
   *  (its from / last cell differ from the positions, e.g. an ability moved
   *  the fighter further in the same seq): the path fell back to Canonical /
   *  Straight (trace `trail=mismatch`). */
  bool bTrailMismatch = false;
  /** Animation steps of CUE-007: path cells without the start; Place = 1. */
  int32 Steps() const {
    return Kind == ES08MoveKind::Place ? 1 : FMath::Max(1, Path.Num() - 1);
  }
};

/** MS-T-15: CUE-007 timing - docs/unreal/contracts/cue-dispatcher/cue-table.json
 *  CUE-007 duration_per_step_ms, cap_subject_ms, cap_seq_ms, min_step_ms,
 *  overlap, place_ms (MS-D-14). The defaults ARE the contract values
 *  (Unmatched.S08.MoveAnim.CueTrace compares them with the table). */
struct UNMATCHED_API FS08MoveCueParams {
  double StepMs = 280.0;
  double CapSubjectMs = 1400.0;
  double CapSeqMs = 2400.0;
  double MinStepMs = 90.0;  // not scaled by the speed multiplier
  double Overlap = 0.3;
  double PlaceMs = 240.0;
};

/** MS-T-16 (S08MoveAnim.h): the speed / reduced-motion inputs of the CUE-007 schedule. */
/** UI-ACC-013 animation speed (03 §5): none = every move snaps, fast x0.5, normal x1, slow x1.5. */
enum class ES08AnimSpeed : uint8 { None, Fast, Normal, Slow };

/** The player's motion settings (US08UserSettings, overridden by the command-line flags). */
struct UNMATCHED_API FS08MotionSettings {
  bool bReducedMotion = false;  // UI-ACC-005/006 (-S08ReducedMotion, s08.ReducedMotion)
  ES08AnimSpeed Speed = ES08AnimSpeed::Normal;  // UI-ACC-013 (-S08AnimSpeed=<none|fast|normal|slow>)
  bool bScreenShake = true;  // UI-ACC-005 "no shake" = false (V-08 / CUE-004 shake; no shake exists in the client yet)
  /** Every move snaps (reduced motion or speed none). */
  bool SnapsMoves() const { return bReducedMotion || Speed == ES08AnimSpeed::None; }
  bool operator==(const FS08MotionSettings& Other) const {
    return bReducedMotion == Other.bReducedMotion && Speed == Other.Speed && bScreenShake == Other.bScreenShake;
  }
};

/** One move of a seq for the schedule. */
struct UNMATCHED_API FS08MoveCueInput {
  ES08MoveKind Kind = ES08MoveKind::Move;
  int32 Steps = 1;
};

/** Schedule entry of one move (milliseconds from the first move's start). */
struct UNMATCHED_API FS08MoveCueTiming {
  double StartMs = 0.0;
  double StepMs = 0.0;     // per step; 0 when snapped
  int32 Steps = 0;
  double DurationMs = 0.0; // StepMs * Steps; 0 when snapped
  bool bSnapped = false;   // did not fit the seq cap: snaps at StartMs
};

/** 04 §6.3 schedule of one seq's moves in OrderInSeq order - a pure
 *  function, mirrored by tools/s08/cue_contract/cue_contract.py
 *  move_schedule (check-trace verifies the MS-CUE `ms=`). SpeedMul: Fast
 *  0.5, Normal 1, Slow 1.5; MS-T-15 traces Normal. Reduced motion and the
 *  speed setting are MS-T-16 (FS08MoveAnim). */
struct UNMATCHED_API FS08MoveCueSchedule {
  static TArray<FS08MoveCueTiming> Compute(const TArray<FS08MoveCueInput>& Moves,
                                           const FS08MoveCueParams& Params = FS08MoveCueParams(),
                                           double SpeedMul = 1.0);
  /** The move cues of Cues (any order) sorted by OrderInSeq, then Compute. */
  static TArray<FS08MoveCueTiming> ForCues(const TArray<FS08Cue>& Cues, TArray<const FS08Cue*>& OutMovesInOrder,
                                           const FS08MoveCueParams& Params = FS08MoveCueParams(),
                                           double SpeedMul = 1.0);
};

/** One maneuver move: fighter id + orthogonal step path. */
struct UNMATCHED_API FS08ManeuverMove {
  FString FighterId;
  TArray<FIntPoint> Path;
};

/** MS-T-04 (MS-R-55, move-selection 04 §5): the viewer's local maneuver draft
 *  kept by the controller, so it survives the gameplay-HUD reset of a
 *  re-entry into the SAME match inside one process (a session expiry and a
 *  re-login tear the stream down but keep this). The draft owner
 *  (FS09CommandUi) writes it on every draft operation and reads it back only
 *  when a snapshot reopens exactly this pendingManeuver.id for the same user
 *  in the same match. */
struct UNMATCHED_API FS08ManeuverDraftCache {
  FString GameId;              // the match (stamped by the controller)
  FString UserId;              // the viewer (stamped by the controller)
  FString ManeuverId;          // pendingManeuver.id; empty = no draft
  TArray<FString> FighterIds;  // moves[] order
  TArray<FIntPoint> Dests;     // same index as FighterIds
  FString BoostCardId;
  bool IsEmpty() const { return ManeuverId.IsEmpty(); }
};

class UNMATCHED_API FS08FlowController {
public:
  FS08FlowController(FString HttpUrl, FString WsUrl, FString InViewerId = FString());

  // ---- Observers ----
  DECLARE_MULTICAST_DELEGATE_OneParam(FOnStage, ES08Stage);
  DECLARE_MULTICAST_DELEGATE_OneParam(FOnRoom, const FS08RoomState&);
  DECLARE_MULTICAST_DELEGATE_OneParam(FOnFlowError, const FS08GraphQLError&);
  DECLARE_MULTICAST_DELEGATE_OneParam(FOnLeaveFailed, const FS08GraphQLError&);
  DECLARE_MULTICAST_DELEGATE_OneParam(FOnTrace, const FString&);
  DECLARE_MULTICAST_DELEGATE_TwoParams(FOnApplied, const FS08Snapshot&, ES08SeqDecision);
  DECLARE_MULTICAST_DELEGATE_OneParam(FOnCues, const TArray<FS08Cue>&);
  /** Tag is the trace tag of the command ("ATTACK", "PEND resolve", ...). */
  DECLARE_MULTICAST_DELEGATE_TwoParams(FOnCommandRejected, const FString& /*Tag*/,
                                       const FString& /*Reason*/);
  DECLARE_MULTICAST_DELEGATE_OneParam(FOnRejection, const FS08Rejection&);

  FOnStage OnStage;
  FOnRoom OnRoom;
  FOnFlowError OnFlowError;
  FOnLeaveFailed OnLeaveFailed;
  FOnTrace OnTrace;
  /** Fires after every applied or merged snapshot (render entry point). */
  FOnApplied OnApplied;
  /** Fires once per authoritative event (seq transition) - never for a
   *  same-seq merge, so HTTP+WS duplicates cannot double-fire cues. */
  FOnCues OnCues;
  /** VS-6 F3 FX-30: the cues of the transition being applied - valid only inside OnApplied (empty otherwise). */
  const TArray<FS08Cue>& GetApplyingCues() const { return ApplyingCues; }
  /** S10 review P1(5): fired when a DISPATCHED gameplay command was
   *  DEFINITIVELY rejected by the server (a 401-answered auth rejection or a
   *  GraphQL/4xx rejection - the command is provably NOT applied). NEVER
   *  fired for an unknown outcome (lost/5xx/unparseable answers): those arm
   *  the recovery lock instead, and a resend of the same command is out of
   *  the question. A driver holding a local draft for the command (e.g.
   *  S09AUTO's AttackDraft) uses this to reset that draft so its next
   *  decision happens against fresh authoritative state. */
  FOnCommandRejected OnCommandRejected;
  /** MS-T-06 (move-selection 02 §1.1): a DEFINITIVE rejection of
   *  beginManeuver / maneuver / a pending-choice resolve, classified (why.*
   *  key, class И/С); also the auth-refresh answer of a maneuver command
   *  (why.auth.refreshed - the command is not resent). Never fired for an
   *  unknown outcome: that arms the recovery lock. Trace: MS-REJECT. */
  FOnRejection OnRejection;

  /** MS-T-06 (MS-E-89, 04 §5): seconds a beginManeuver / maneuver command may
   *  wait for its HTTP answer: after Slow the UI shows why.syncing, at the
   *  Deadline the request is cancelled and the outcome is unknown (recovery,
   *  no resend). */
  static constexpr float CommandSlowSeconds = 3.0f;
  static constexpr float CommandDeadlineSeconds = 10.0f;
  /** True while the open beginManeuver / maneuver has waited >= 3 s. */
  bool IsCommandSlow() const { return InFlightOp != EManeuverOp::None && bInFlightSlow; }
  /** The why.* key CanIssueGameplayCommand refuses with (NAME_None = open):
   *  why.syncing (not started, stream not ready, recovery, in flight, invalid
   *  critical fields), why.not.your.turn, why.state.changed (over, aborted). */
  FName GameplayGateKey() const;

  /** Public content heroes (id/name/health/sidekickCount) for the pick UI. */
  const TArray<FS08HeroEntry>& GetHeroes() const { return Heroes; }
  void FetchHeroes();

  // ---- VS-7 SC-03...SC-05: the BOOT pass after the login (S08FlowControllerBoot.cpp; no stage change) ----
  enum class EBootQuery : uint8 { Idle, Loading, Done, Failed };
  /** heroList answers that failed so far (BOOT shows its error banner on a new one). */
  int32 GetHeroesFailures() const { return HeroesFailures; }
  /** boardList (Board rows id -> name): the boards stage and the board name of the resume line. */
  void FetchBoards();
  EBootQuery GetBoardsState() const { return BoardsState; }
  const TMap<FString, FString>& GetBoardNames() const { return BoardNames; }
  /** myGames(status: IN_PROGRESS): the own live match after a restart; GetActiveGame().GameId empty = none. */
  void FetchActiveGame();
  EBootQuery GetActiveGameState() const { return ActiveGameState; }
  const FS08RoomState& GetActiveGame() const { return ActiveGame; }
  /** «Вернуться в партию»: the found match becomes the room and its stream attaches (the guest's IN_PROGRESS path). */
  bool ResumeActiveGame();
  // ---- VS-7 SC-08...SC-13: the LOBBY list (S08FlowControllerLobby.cpp; no stage change) ----
  struct FLobbyGame { FString Id, Code, Status, Mode, HostId, BoardId; int32 Players = 0; TArray<FString> HeroIds; };
  /** availableGames(mode: ONE_V_ONE) (ВР-VS4-SC08-01): the open rooms; a newer request supersedes an older answer. */
  void FetchAvailableGames();
  EBootQuery GetAvailableState() const { return AvailableState; }
  const TArray<FLobbyGame>& GetAvailableGames() const { return AvailableGames; }
  int32 GetAvailableAnswers() const { return AvailableAnswers; }
  /** joinGame(gameId) of a list row (the code lookup is not needed: the row carries the id). */
  void JoinRoomById(const FString& GameId);

  ES08Stage GetStage() const { return Stage; }
  const FS08RoomState& GetRoom() const { return Room; }
  const FString& GetUserId() const { return UserId; }
  const FString& GetUsername() const { return Username; }
  const FS08Snapshot& GetAppliedSnapshot() const { return Applied; }
  bool IsMyTurn() const {
    return !UserId.IsEmpty() && Applied.CurrentTurnPlayerId == UserId;
  }
  /** Input gate: while critical fields of the applied snapshot are invalid,
   *  gameplay input must stay blocked (GD-028 acceptance). */
  bool IsInputBlocked() const { return !CriticalProblems.IsEmpty(); }
  const TArray<FString>& GetCriticalProblems() const { return CriticalProblems; }

  /** GD-037 (ACC-012): true while a gameplay command's outcome is unknown
   *  (lost mutation response) and the client waits for the authoritative
   *  state. Gameplay input is locked - a resend could repeat the spend. */
  bool IsAwaitingStateRecovery() const { return bMutationRecoveryActive; }
  /** GD-038 (ACC-021): true once the session is dead (refresh failed/expired
   *  and no credential is held) - the UI must route to login. */
  bool IsSessionExpired() const { return bSessionExpired; }
#if WITH_AUTOMATION_TESTS
  /** Test seam: has the CURRENT operation ever delivered a frame? (S10
   *  review P1(3): the input gate requires a proven-live operation.) */
  bool IsGameStateOpLiveForTest() const { return bGameStateOpLive; }
#endif

  /** GD-031 action gate (consistent with the phase1 critical-field gate):
   *  returns an empty string when a gameplay command may be issued. */
  bool CanIssueGameplayCommand(FString& OutReason) const;
  /** GD-034 combat gate: like CanIssueGameplayCommand but WITHOUT the
   *  turn-owner check - the defender acts during the attacker's turn, and
   *  any participant may resolve in COMBAT_RESOLVE. Started + valid critical
   *  fields + not in flight still apply. */
  bool CanIssueCombatCommand(FString& OutReason) const;
  /** endTurn phase gate: mirrors the server's network guard (game-turn.guard
   *  ActionEconomy) - legal ONLY in ACTION_MANEUVER/ACTION_ATTACK. The S09
   *  run 2026-09-26 sent 8 endTurn mutations from COMBAT/COMBAT_RESOLVE and
   *  burned authoritative 'Invalid phase' rejections; this gate stops the
   *  send before the network. */
  static bool IsEndTurnPhase(const FString& Phase) {
    return Phase == TEXT("ACTION_MANEUVER") || Phase == TEXT("ACTION_ATTACK");
  }
  /** Full endTurn gate: IsEndTurnPhase + CanIssueGameplayCommand. */
  bool CanIssueEndTurn(FString& OutReason) const;
  /** True while a beginManeuver/maneuver pair is between its two HTTP legs. */
  bool IsManeuverInFlight() const { return bManeuverInFlight; }
#if WITH_AUTOMATION_TESTS
  /** Test seam: true once a barrier body reconciled the live stream (see
   *  IsStreamReady). */
  bool IsStreamReconciledForTest() const { return bStreamReconciled; }
#endif

  // ---- BOOT -> LOGIN ----
  void Login(const FString& Email, const FString& Password);

  // ---- LOGIN -> LOBBY ----
  void EnterLobby(); // recovery: myGames(LOBBY) returns an existing room
  // ---- LOBBY ----
  void CreateRoom(const FString& Mode, const FString& InBoardId = FString());  // VS-7 SC-09: the board of the LOBBY
  void JoinRoomByCode(const FString& Code);
  // ---- ROOM ----
  void SelectHero(const FString& HeroId);
  void ToggleReady();
  void StartGame();
  void LeaveRoom();
  // ROOM -> Started: authoritative state stream
  void AttachGameStateStream();

  // ---- GD-028 transport recovery ----
  /** Drives the bounded-backoff WS reconnect: called every game tick.
   *  On the retry boundary it rebuilds the socket; on connection_ack it
   *  refetches gameState over HTTP and resubscribes from the applied seq. */
  void TickConnectivity(float DeltaSeconds);
  /** Test hook: simulate an abrupt transport loss of the live stream. */
  void DropWsForTest();
  bool IsStreamAttached() const { return Ws.IsValid(); }
  /** GD-037/S10: true only while a live, READY state stream exists - the
   *  gameplay-command gate and the reconnect banner both key off this. An
   *  acked socket alone does not count (S10 review P1(3)), and neither does
   *  a LOCALLY registered operation id awaiting server acceptance (Sol6
   *  review P1(3)): the state subscription must be PROVEN live (it has
   *  delivered at least one frame) AND reconciled - a barrier body (HTTP
   *  gameState read or delivered WS snapshot) proved the channel carries
   *  current server truth. A subscribe that keeps failing - or whose error
   *  lands after the read reconciled - leaves the gate closed even though
   *  connection_ack succeeded. */
  bool IsStreamReady() const {
    return Ws.IsValid() && Ws->IsAcked() && !GameStateOpId.IsEmpty() && bGameStateOpLive &&
           bStreamReconciled;
  }

  /** Applies an incoming snapshot through the seq guard and critical-field
   *  validation. Returns the decision taken (Ignore/Merge/Apply). */
  ES08SeqDecision ApplySnapshot(const FS08Snapshot& Snapshot);

  /** Cues for one authoritative transition (old vs new fighters, by id) -
   *  pure. MS-T-15 (04 §4.6): every FighterMoved cue carries its Path (with
   *  the start), OrderInSeq, Kind and PathSource - the trail
   *  (Metadata.lastMovement, used only when its seq == Seq and its entry for
   *  the fighter starts at the old position and ends at the new one), else
   *  FS08BoardModel::BuildCanonicalPath on Board over the OLD fighters with
   *  no step limit, else Straight. Metadata is the snapshot's OWN metadata
   *  (absent = no trail). Move cues come first in OrderInSeq order, then
   *  the damage cues in fighters[] order. A fighter whose position did not
   *  change gets no move cue even when the trail lists it. */
  static void ComputeCues(int32 Seq, const TSharedPtr<FJsonValue>& OldFighters,
                          const TSharedPtr<FJsonValue>& NewFighters, const FS08BoardModel& Board,
                          const TSharedPtr<FJsonValue>& Metadata, TArray<FS08Cue>& OutCues);
  /** VS-6 F3 FX-28: the same with the OLD (applied) metadata - its pendingEffects give the AbilityTriggered cues. */
  static void ComputeCues(int32 Seq, const TSharedPtr<FJsonValue>& OldFighters,
                          const TSharedPtr<FJsonValue>& NewFighters, const FS08BoardModel& Board,
                          const TSharedPtr<FJsonValue>& Metadata, const TSharedPtr<FJsonValue>& OldMetadata,
                          TArray<FS08Cue>& OutCues);
  /** MS-T-15 (04 §9) trace lines of the move cues of one seq, in
   *  OrderInSeq order, timed by FS08MoveCueSchedule (Normal speed):
   *  "MS-CUE move seq=<n> fighter=<id> order=<k> of=<n> kind=<move|place>
   *   steps=<n> source=<trail|canonical|straight> start=<ms> ms=<ms>
   *   snapped=<0|1> path=<A>B>C>[ trail=mismatch]" - cells as
   *  Board.CellLabel. cue_contract.py check-trace verifies steps, path and
   *  ms against cue-table.json CUE-007. MS-T-16: with Motion the schedule
   *  takes its speed / reduced motion (FS08MoveAnim::Schedule) and the line
   *  ends with " speed=<none|fast|normal|slow> reduced=<0|1>". */
  static void MoveCueTraceLines(const TArray<FS08Cue>& Cues, const FS08BoardModel& Board,
                                TArray<FString>& OutLines, const FS08MotionSettings* Motion = nullptr);
  /** MS-T-16: the motion settings the client animates with - the MS-CUE lines
   *  of every applied seq are scheduled and tagged with them from now on. */
  void SetMoveMotion(const FS08MotionSettings& Motion) {
    MoveMotion = Motion;
    bMoveMotionSet = true;
  }

#if WITH_AUTOMATION_TESTS
  /** Offline harness: attach the state stream against a socket-less
   * (fake-acked) WS so server frames can be injected without a network. */
  void AttachStreamHarnessForTest(const FString& GameId);
  /** Feeds a raw graphql-transport-ws server frame into the live stream. */
  void InjectWsFrameForTest(const FString& RawFrame) {
    if (Ws.IsValid()) Ws->InjectServerFrameForTest(RawFrame);
  }
  bool HasGameStateOpForTest() const { return !GameStateOpId.IsEmpty(); }
  int32 GetOpRecoveryAttemptsForTest() const { return OpRecoveryAttempts; }
  /** GD-037/038 test seams. */
  bool IsMutationRecoveryActiveForTest() const { return bMutationRecoveryActive; }
  int32 GetMutationRecoveryAttemptsForTest() const { return MutationRecoveryAttempts; }
  /** Pending-choice id the recovery lock is currently holding on (P2(8)). */
  const FString& GetMutationRecoveryPendingChoiceIdForTest() const {
    return MutationRecoveryPendingChoiceId;
  }
  int32 GetTestHttpSendCountForTest() const { return TestHttpSendCount; }
  /** Variables of the last SendHttp (harness + network) - the wire shape of a
   *  command (MS-R-44: no empty path in maneuver.moves). */
  TSharedPtr<FJsonObject> GetLastHttpVariablesForTest() const { return TestLastHttpVariables; }
  /** MS-T-06: how many SendHttp documents contained Needle (e.g. "beginManeuver(",
   *  "maneuver(input", "gameState(") - which command went out, not just how many. */
  int32 CountHttpSendsForTest(const FString& Needle) const {
    int32 Count = 0;
    for (const FString& Query : TestHttpQueries) Count += Query.Contains(Needle, ESearchCase::CaseSensitive) ? 1 : 0;
    return Count;
  }
  void SetAuthForTest(const FString& InAccessToken, const FString& InRefreshToken) {
    Http.SetAccessToken(InAccessToken);
    RefreshToken = InRefreshToken;
    bSessionExpired = false;
  }
  FString GetAccessTokenForTest() const { return Http.GetAccessToken(); }
  int32 GetRefreshCountForTest() const { return RefreshCount; }
  bool IsRefreshInFlightForTest() const { return bRefreshInFlight; }
  bool IsSessionExpiredForTest() const { return bSessionExpired; }
  int32 GetWsGenerationForTest() const { return WsGeneration; }
  /** S10/GD-039 test seam: the idempotency key the next createGame intent
   *  would carry (rotation proofs live here, see CreateRoom). */
  const FString& GetIdempotencyKeyForTest() const { return IdempotencyKey; }
  /** Test seam: drive the WS transport-close path (4403/4408/...) without a
   *  socket - same handler the OnClosedTransport delegate binds. */
  void HandleWsClosedForTest(int32 StatusCode, const FString& Reason) {
    OnWsTransportClosed(StatusCode, Reason);
  }
  /** Offline HTTP harness: the next controller-issued Execute path resolves
   *  with this queued result instead of the network. InRawBody (optional) is
   *  parsed into the Data object AND passed through as the raw body, so room
   *  responses (createGame/startGame/poll/...) and mutation echoes
   *  (beginManeuver/...) both work. With bDeferDelivery the answer only
   *  fires on DeliverQueuedHttpForTest(), so a late answer can be simulated
   *  after the room/match changed. */
  void QueueHttpResultForTest(bool bOk, TArray<FS08GraphQLError> InErrors = {},
                              bool bDeferDelivery = false,
                              const FString& InRawBody = FString());
  /** Delivers a deferred harness result (see QueueHttpResultForTest). Index
   *  defaults to FIFO head; an explicit index lets a test deliver answers OUT
   *  OF ORDER (e.g. an older request's reply landing after a newer one). */
  void DeliverQueuedHttpForTest(int32 Index = 0);
  /** Seeds room id + stage so leave paths can be driven without a login. */
  void SetRoomForTest(const FString& GameId, ES08Stage InStage);
  /** Match generation as observed by the guard logic (see MatchGeneration). */
  int32 GetMatchGenerationForTest() const { return MatchGeneration; }
#endif

  // ---- GD-031 gameplay commands (routed through the same store) ----
  // Every command returns TRUE only when it was actually dispatched: a gate
  // block (stream not ready, recovery lock, wrong turn, in flight) returns
  // false WITHOUT a send. Callers that advance a local state machine on the
  // answer (S09AUTO) must do so ONLY on true - a false left unobserved
  // stalled the packaged duel at seq 1 (the mode logged "sent", the
  // controller dropped the command, no snapshot ever came).
  /** beginManeuver(expectedSequenceNumber = local seq). On success the store
   *  holds the pending maneuver id (see PendingManeuverId()). */
  bool BeginManeuver();
  /** Completes the open maneuver: one move per fighter, orthogonal steps.
   *  GD-033: optional BoostCardId - an exact hand instance id (the card drawn
   *  by beginManeuver is a legal boost: ACC-006/R-03). Empty = no boost.
   *  MS-R-44: a move with an empty path ("stay") is never serialized (the
   *  server answers EMPTY_PATH for the whole maneuver) - dropped with a trace. */
  bool SubmitManeuver(const FString& ManeuverId, const TArray<FS08ManeuverMove>& Moves,
                      const FString& BoostCardId = FString());
  /** MS-T-04 draft cache (see FS08ManeuverDraftCache): Store stamps the
   *  current match and user (an empty ManeuverId clears it); Recall answers
   *  only for the same match, the same user AND the same maneuver id; an
   *  accepted leaveGame clears it. */
  void StoreManeuverDraft(const FS08ManeuverDraftCache& Draft);
  bool RecallManeuverDraft(const FString& ManeuverId, FS08ManeuverDraftCache& OutDraft) const;
  /** GD-033: endTurn - legal only when actionsRemaining == 0 and no pending
   *  choice (server rejects otherwise; error surfaces through OnFlowError). */
  bool EndTurn();
  /** GD-033: discardToLimit - EXACT pending.count own hand instance ids of
   *  the open TURN_END discard choice. */
  bool DiscardToLimit(const FString& PendingId, const TArray<FString>& CardInstanceIds);

  // ---- GD-034 combat commands (same store: every echo routes through
  //      ApplySnapshot; the WS duplicate of the same seq merges) ----
  /** attack(attackerId, cardId, targetId) - cardId is the hand INSTANCE id.
   *  Legal for the turn owner in ACTION_* with melee adjacency (server
   *  authoritative; local UI gates mirror it). */
  bool Attack(const FString& AttackerFighterId, const FString& CardInstanceId,
              const FString& TargetFighterId);
  /** DE-020 (SD-56): the same attack with the hero ability boost (abilityBoostCardId - King Arthur; the
   *  server re-checks the hand and abilityBoostAllowed). An empty id sends the plain attack. */
  bool Attack(const FString& AttackerFighterId, const FString& CardInstanceId,
              const FString& TargetFighterId, const FString& AbilityBoostCardId);
  /** playDefense(cardId) - defender-only during COMBAT (server deadline
   *  applies; the local UI blocks an expired window). */
  bool PlayDefense(const FString& CardInstanceId);
  /** playScheme(cardId) - turn owner in ACTION_*. */
  bool PlayScheme(const FString& CardInstanceId);
  /** resolveCombat(): defender "no defense" in COMBAT; ANY participant in
   *  COMBAT_RESOLVE (server rejects everyone else). */
  bool ResolveCombat();
  /** GD-035 pending-queue-head resolve. Payload per server
   *  ResolvePendingEffectDto: MOVE/PLACE need FighterId+bHasCell(x,y);
   *  CHOOSE_SPACE bHasCell only; TARGET_FIGHTER FighterId only; CHOOSE_ONE
   *  bHasOption index; DISCARD_CARDS/BOOST_CHOICE/DECK_TOP_PICK exact
   *  CardIds (ORDER = full top->bottom order). declinePendingEffect stays
   *  optional-only. */
  bool ResolvePendingEffect(const FString& EffectId, const FString& FighterId,
                            bool bHasCell, int32 X, int32 Y, bool bHasOption,
                            int32 OptionIndex, const TArray<FString>& CardIds);
  bool DeclinePendingEffect(const FString& EffectId);

  /** GD-032 freshness: seq of the last body that actually carried the
   *  projection (0 = never seen). WS events omit decks, so counts go
   *  honestly stale ("~") until the next full HTTP body / mutation echo. */
  int32 GetDecksSeq() const { return DecksSeq; }
  int32 GetDiscardPilesSeq() const { return DiscardPilesSeq; }

  /** DE-030 (W-19; 01 F-05): the public deck lists of the match (gameDeckLists - the composition grouped by catalog
   *  id, no order, no instance id). Static for the whole match: one request per match, no automatic retry; a failed
   *  answer stays Failed until EnsureDeckLists(true) (the panel's next open). */
  enum class EDeckListsState : uint8 { None, Loading, Loaded, Failed };
  void EnsureDeckLists(bool bRetryFailed = false);
  EDeckListsState GetDeckListsState() const {
    return DeckListsGameId == Room.GameId ? DeckListsState : EDeckListsState::None;
  }
  /** The `data` object of the answer (gameDeckLists array inside); null unless Loaded for the current room. */
  TSharedPtr<FJsonObject> GetDeckListsData() const {
    return GetDeckListsState() == EDeckListsState::Loaded ? DeckListsData : nullptr;
  }
  /** Bumps on every install/reset - the HUD re-parses only on change. */
  int32 GetDeckListsRevision() const { return DeckListsRevision; }

  /** Lobby freshness via game(id) re-query (named subscriptions have no
   *  snapshot barrier, so they cannot carry room state). */
  void PollRoom();
  /** True while the lobby/room view needs game(id) re-query polling.
   *  S10/GD-040: ALSO true while a match is live - the room row (not a stale
   *  snapshot or a named CUE) is the only authoritative source for the
   *  IN_PROGRESS -> ABORTED/FINISHED transition; the poll stops once a
   *  terminal status is installed. */
  bool WantsPolling() const {
    if (Stage == ES08Stage::Room && Room.Status == TEXT("LOBBY")) return true;
    return Stage == ES08Stage::Started &&
           (Room.Status == TEXT("IN_PROGRESS") || Room.Status == TEXT("PAUSED"));
  }
  /** S10/GD-040: the authoritative room row is terminal (FINISHED or ABORTED).
   *  A live match blocks all gameplay input once this holds; only LeaveRoom
   *  remains. */
  bool IsRoomTerminal() const {
    return Room.Status == TEXT("FINISHED") || Room.Status == TEXT("ABORTED");
  }
  /** S10/GD-040: the room row says the match was INTERRUPTED (ABORTED) - never
   *  a victory/defeat verdict, and never inferred from a snapshot/CUE. */
  bool IsRoomAborted() const { return Room.Status == TEXT("ABORTED"); }
  /** S10/GD-039: VS_AI room - the second seat is the server bot (room
   *  metadata), added by the server on startGame. */
  bool IsVsAiRoom() const { return Room.Mode == TEXT("VS_AI"); }
  /** S10/GD-039: true while the server bot holds the turn of a live VS_AI
   *  match - drives the waiting indicator from the AUTHORITATIVE state
   *  (applied turn owner), never a fixed timer. */
  bool IsBotActing() const {
    return Stage == ES08Stage::Started && IsVsAiRoom() && !IsRoomTerminal() &&
           Applied.Phase != TEXT("GAME_OVER") && !UserId.IsEmpty() &&
           !Applied.CurrentTurnPlayerId.IsEmpty() && Applied.CurrentTurnPlayerId != UserId;
  }

private:
  // MS-T-16: motion settings of the MS-CUE trace (unset = the MS-T-15 Normal lines without speed= / reduced=).
  FS08MotionSettings MoveMotion;
  bool bMoveMotionSet = false;
  /** Shared executor for the GD-034 combat mutations: in-flight flag, error
   *  broadcast, GameMutationResult parse, ApplySnapshot routing, trace tag.
   *  Traces carry NO card/opponent values (privacy: published logs stay
   *  reveal-free). Returns true only when the mutation was dispatched. */
  bool RunCombatMutation(const FString& Tag, const TCHAR* Field, const FString& Mutation,
                         const TSharedRef<FJsonObject>& Variables,
                         const FString& PendingChoiceId = FString());
  void SetStage(ES08Stage NewStage);
  /** Room-entry gate (recovery/create/join): while Stage == Started the
   *  membership and the state stream belong to the live match - replacing the
   *  room without an accepted LeaveRoom would strand the old WS op id (it
   *  blocks the next room's subscribe) and implicitly abandon the server-side
   *  membership. Entry is refused until the leave path lands in Lobby. */
  bool CanEnterRoomFlow(const TCHAR* Action);
  /** Deferred room-entry answer gate: the entry (recovery/create/join) is
   *  dispatched while Stage == Room, but the SAME room can go Started (host
   *  startGame, poll flip) before the answer lands - a transition that does
   *  NOT bump MatchGeneration, so the request-identity gate alone passes.
   *  The live match owns the room, the stage and the stream; the late answer
   *  (success, error or room rewrite) must drop BEFORE any side effect. */
  bool CanApplyRoomEntryAnswer(const TCHAR* Action);
  /** Accepted-leave teardown: drops the old game's WS subscription + socket
   *  and any pending reconnect, and clears every match-scoped field (applied
   *  snapshot, seq guard, freshness seqs, critical problems, recovery and
   *  in-flight flags), so a later match starts from a clean slate. */
  void TeardownGameStateStream();
  /** Request-identity gate for room-scoped responses: TRUE only while the
   *  controller still serves the exact match the callback was dispatched for
   *  (same room id at the same MatchGeneration). A delayed answer for a
   *  left/replaced/re-joined match must drop BEFORE any side effect: no room
   *  rewrite, no stream attach, no in-flight-flag clear, no error broadcast,
   *  no snapshot apply. */
  bool IsSameMatchRequest(const FString& DispatchedGameId,
                          int32 DispatchedGeneration) const {
    return Room.GameId == DispatchedGameId && MatchGeneration == DispatchedGeneration;
  }
  /** Live-path apply gate: routes through the seq guard but refuses bodies
   *  that arrive after the match was left - a delayed HTTP/WS answer must
   *  not resurrect the torn-down game. */
  ES08SeqDecision ApplyMatchSnapshot(const FS08Snapshot& Snapshot);
  void Trace(const FString& Line);
  void HandleRoomResponse(TSharedPtr<FJsonObject> Data, const FString& Field);
  void ParseRoomFrom(const TSharedPtr<FJsonObject>& Game);
  void FetchGameState(); // full HTTP snapshot (barrier counterpart)
  void SubscribeAfterSnapshot(int32 Since); // idempotent WS attach
  /** (Re)creates the WS: binds ack/close handlers and starts the connect. */
  void MakeWs();
  /** Binds the WS delegates (shared by MakeWs and the offline test harness). */
  void BindWsHandlers();
  /** Closes the stream view of the transport and arms the reconnect timer. */
  void ScheduleWsReconnect(const FString& Reason);
  /** Operation-level 'error'/'complete' on an open socket: clears the dead
   *  op id and triggers a BOUNDED refetch+resubscribe (see OpRecoveryAttempts). */
  void HandleOperationEnded(const FString& OpId, const FString& Reason);
  /** Unparseable server frame on an open socket: no readable id, so the live
   *  subscription (if any) is treated as poisoned and driven through the
   *  same BOUNDED refetch+resubscribe path - never a silent stale-seq hang. */
  void HandleStreamPoisoned(const FString& Reason);
  // ---- GD-037: lost mutation response recovery (ACC-012) ----
  /** True when the failure means the server may STILL have applied the
   *  command (no HTTP answer, or a 5xx after the request reached it). A
   *  GraphQL rejection is a definitive NOT-applied answer instead. */
  static bool IsOutcomeUnknown(const TArray<FS08GraphQLError>& Errors);
  /** Locks gameplay input and starts the bounded authoritative-state refetch
   *  (no resend of the lost command, ever). PendingChoiceId (when non-empty)
   *  is a pending-queue id the lost command was resolving: the lock then
   *  holds until THAT choice is provably settled (gone from the pending
   *  queue), not merely until any seq advance. bPendingIsDiscard marks a
   *  discardToLimit choice (settled through pendingHandDiscard / a complete
   *  full state) vs a pendingEffects resolve. */
  void EnterMutationRecovery(const FString& Reason, const FString& PendingChoiceId,
                             bool bPendingIsDiscard = false);
  /** One bounded refetch attempt while recovery is armed; arms the backoff
   *  timer on failure inside FetchGameState's failure path. */
  void AttemptMutationRecoveryRefetch();
  /** Bounded failure tail of a recovery read (transport loss, 5xx or an
   *  unparseable HTTP 200): re-arms the backoff ladder, or surfaces the
   *  visible exhaustion error while the input lock stays. */
  void HandleMutationRecoveryReadFailed();
  /** Shared parse-failure tail of every gameplay mutation: an unreadable HTTP
   *  200 body after the request reached the server is an outcome-UNKNOWN
   *  answer (the server may have committed) - recovery, never a resend. */
  void HandleMutationParseFailure(const FString& Tag, const FString& PendingChoiceId,
                                  bool bPendingIsDiscard = false);
  // ---- GD-038: authorization recovery (ACC-021) ----
  static bool IsAuthError(const TArray<FS08GraphQLError>& Errors);
  static bool IsRateLimited(const TArray<FS08GraphQLError>& Errors);
  /** Single-flight refreshTokens call. Rotates the token pair, arms the WS
   *  recreation (the live socket was authenticated with the dead token) and
   *  retries the triggering READ once. Returns false when the session is
   *  already dead (the caller must not retry). */
  bool TryRefreshAuth();
  /** Terminal: clears both tokens, broadcasts SESSION_EXPIRED and routes the
   *  flow to the login screen. No further automatic request is issued. */
  void EnterSessionExpired(const FString& Why);
  /** Drops the live socket and arms the fast reconnect so the next
   *  MakeWs() authenticates with the rotated token (GD-038: WS recreation
   *  after refresh). */
  void RecreateWsAfterAuthRotation();
  /** WS transport close routing: 4403 goes through the refresh path (a
   *  dead token must not loop reconnects), other codes reconnect boundedly.
   *  The server-supplied Reason is REDACTED before any trace line: only the
   *  numeric code and a fixed description are ever logged (canary-tested). */
  void OnWsTransportClosed(int32 StatusCode, const FString& Reason);
  /** Fixed, client-side description of a WS close code. Never derived from
   *  server-controlled text. */
  static const TCHAR* WsCloseDescription(int32 StatusCode);
  /** Central HTTP send (harness-aware): every controller request goes
   *  through here so tests can count real sends. Returns the network request
   *  (null for a harness answer). */
  FHttpRequestPtr SendHttp(const FString& Query, const TSharedPtr<FJsonObject>& Variables,
                           FS08GraphqlClient::FResult&& OnDone);
  // ---- MS-T-06: the beginManeuver / maneuver command in flight (04 §5) ----
  enum class EManeuverOp : uint8 { None, Begin, Maneuver };
  static const TCHAR* ManeuverOpName(EManeuverOp Op);
  /** Opens the command: in-flight gate, a fresh token, the deadline clock,
   *  the seq it was sent at and (maneuver) the pendingManeuver id it closes. */
  int32 StartManeuverOp(EManeuverOp Op, const FString& ManeuverId);
  /** The HTTP answer of Token: true when it is the open command (which it
   *  closes); false - traced as MS-NET late-reply - when a snapshot or the
   *  deadline already settled it. */
  bool TakeManeuverOpAnswer(int32 Token, EManeuverOp Op, bool bOk);
  /** A late SUCCESS answer is still merged through the seq guard (decks are
   *  only in HTTP bodies); no gate change, no error. */
  void MergeLateManeuverAnswer(const FString& RawBody, const TCHAR* Field);
  /** Closes the open command (gate, clock, request handle). */
  void EndManeuverOp();
  /** 3 s -> slow (why.syncing); 10 s -> request cancelled, MS-NET deadline,
   *  EnterMutationRecovery (no resend, MS-E-89). */
  void TickCommandDeadline(float DeltaSeconds);
  /** MS-E-90: an applied snapshot that settles the open command (begin: my
   *  pendingManeuver is open; maneuver: its pendingManeuver id is closed) at a
   *  seq past the send releases the gate before the HTTP answer. */
  void ReleaseManeuverGateBySnapshot(const FS08Snapshot& Snapshot);
  /** Classify (FS08RuleCodes), trace MS-REJECT, broadcast OnRejection and
   *  re-read the snapshot when the class asks for it. */
  void HandleRejection(const TArray<FS08GraphQLError>& Errors, ES08RejectOp Op,
                       const TArray<FIntPoint>& Destinations);
  /** MS-E-92: a maneuver command answered 401 - the token is being refreshed,
   *  the command is NOT resent; the player confirms again (why.auth.refreshed). */
  void NotifyAuthRefreshed(ES08RejectOp Op);
  EManeuverOp InFlightOp = EManeuverOp::None;
  int32 InFlightToken = 0;
  int32 NextCommandToken = 0;
  float InFlightAge = 0.0f;
  bool bInFlightSlow = false;
  int32 InFlightBaseSeq = 0;
  FString InFlightManeuverId;
  FHttpRequestPtr InFlightRequest;
  /** Tokens settled before their answer (snapshot / deadline): the answer is
   *  only traced (MS-NET late-reply). Bounded. */
  TMap<int32, FString> RetiredCommandTokens;
  /** The space of the last pending-choice resolve ((-1,-1) without one). */
  FIntPoint PendingResolveCell = FIntPoint(-1, -1);
  FS08GraphqlClient Http;
  TUniquePtr<FS08GraphqlWs> Ws;
  FString WsUrl;
  FString UserId;
  FString Username;
  FString IdempotencyKey;   // stable across create retries in this session
  // S10/GD-039: room id the CURRENT key's create intent already resolved to.
  // Non-empty => that intent is complete; the NEXT CreateRoom call is a NEW
  // intent and rotates the key first (two successive rooms get distinct keys).
  // A create with no resolved room yet (lost answer, answered failure) keeps
  // the key - a retry of the SAME intent redelivers the SAME room - UNLESS the
  // intent was SUPERSEDED (below): then its answer is stale-dropped and a
  // further create is logically NEW.
  FString CreateKeyRoomId;
  // S10 review M1: MatchGeneration at the CURRENT key's last createGame
  // dispatch. When the live generation has moved past it (a concurrent JOIN /
  // accepted leave won the race), that intent's answer can never be applied -
  // the stale gates drop it - and a retry under the SAME key would make the
  // server redeliver the ABANDONED room for the new intent. INDEX_NONE = no
  // dispatch is outstanding for this key.
  int32 CreateKeyDispatchGen = INDEX_NONE;
  FString GameStateOpId;
  ES08Stage Stage = ES08Stage::Boot;
  FS08RoomState Room;
  // Request identity: bumps on an accepted leave and whenever Room.GameId
  // changes (new room, or a re-join of the same id after a leave). Callbacks
  // capture (GameId, MatchGeneration) at dispatch; comparing against the live
  // pair is the stale-response gate - a GameId-only check cannot tell a
  // re-joined same-id room from the original request's room.
  int32 MatchGeneration = 0;
  FS08Snapshot Applied;
  FS08SeqGuard SeqGuard;
  TArray<FS08Cue> ApplyingCues;  // VS-6 F3: GetApplyingCues
  // GD-032: seq of the last body that carried decks/discardPiles (0 = never).
  int32 DecksSeq = 0;
  int32 DiscardPilesSeq = 0;
  // DE-030: the public deck lists of DeckListsGameId (EnsureDeckLists).
  EDeckListsState DeckListsState = EDeckListsState::None;
  FString DeckListsGameId;
  TSharedPtr<FJsonObject> DeckListsData;
  int32 DeckListsRevision = 0;
  TArray<FString> CriticalProblems;
  TArray<FS08HeroEntry> Heroes;
  bool bManeuverInFlight = false; // INT-005: one logical command at a time
  // MS-T-04: the viewer's maneuver draft of this match (StoreManeuverDraft).
  FS08ManeuverDraftCache ManeuverDraftCache;
  // WS recovery state: <0 = idle, otherwise seconds until the retry.
  float WsReconnectCountdown = -1.0f;
  float WsReconnectBackoff = 1.0f; // doubles per failure, capped in cpp
  bool bWsReconnectAckPending = false; // ack of a RETRYED connection
  // Operation-level recovery (socket healthy, subscription ended): bounded
  // attempts; reset by the first successfully delivered snapshot. Prevents
  // an error/complete loop (e.g. server rejecting the query) from spinning.
  static constexpr int32 MaxOpRecoveryAttempts = 3;
  int32 OpRecoveryAttempts = 0;
  // GD-037 lost-response recovery: while active, gameplay commands are
  // locked and the authoritative state is refetched on a bounded backoff
  // ladder (the lost command is NEVER resent - the server may have applied
  // it). Any applied/merged body (HTTP refetch or live WS) releases the lock.
  static constexpr int32 MaxMutationRecoveryAttempts = 5;
  bool bMutationRecoveryActive = false;
  int32 MutationRecoveryAttempts = 0;
  float MutationRecoveryRetryCountdown = -1.0f; // <0 = disarmed
  float MutationRecoveryBackoff = 1.0f;
  // S10 review P1(1): the lock releases ONLY on a verified fresh result.
  // Baseline = the local seq at arm time; a same-or-lower-seq WS body is a
  // pre-command state (or its replay) and must NOT unlock. An HTTP gameState
  // read dispatched while the lock is held is fresh by construction and may
  // unlock at ANY seq (it proves the current server state, including
  // "the command was never applied").
  int32 MutationRecoveryBaselineSeq = 0;
  bool bMutationRecoveryHasBaseline = false;
  bool bMutationRecoveryFreshRead = false; // set around the HTTP-barrier apply
  // S10 review P2(8): when the lost command was resolving a pending-queue
  // head (or a discard-to-limit choice), a bare seq advance proves nothing -
  // an UNRELATED event moves the seq while the choice stays open. The lock
  // holds until this id disappears from metadata.pendingEffects (or the
  // pendingHandDiscard for a discard command).
  FString MutationRecoveryPendingChoiceId;
  // Sol6 review P1(1): settle by choice KIND. A discardToLimit choice is
  // settled by the pendingHandDiscard projection (a complete full state may
  // omit the field once resolved); a pendingEffects resolve is settled by a
  // strictly valid pendingEffects array lacking the id.
  bool bMutationRecoveryPendingChoiceIsDiscard = false;
  // S10 review P1(3): a body from the HTTP gameState barrier (reconnect or
  // recovery refetch) is a reconciliation read, never a live transition -
  // its diff fires NO cues regardless of gap size (a contiguous local+1
  // barrier body would otherwise emit a stale CUE).
  bool bBarrierHttpBody = false;
  // S10 review P1(2): the FIRST 'next' a fresh gameStateUpdated subscription
  // delivers is the server's barrier snapshot (current state at subscribe
  // time), not a live transition - its diff fires no cues either. The slot
  // closes on the first delivered frame or on a fresh HTTP reconciliation
  // read that landed after the subscribe; later frames are live again.
  bool bWsAwaitingBarrierFrame = false;
  bool bWsBarrierFrame = false; // set around the first WS frame's apply
  // S10 review P1(3): reconciliation proof for IsStreamReady - set by the
  // first applied/merged barrier body or delivered WS snapshot, reset by
  // every teardown/reconnect/operation-end/auth-rotation.
  bool bStreamReconciled = false;
  // Sol6 review P1(3): the operation named by GameStateOpId has DELIVERED at
  // least one frame (the server accepted the subscribe). A locally
  // registered id is NOT live yet: its replacement subscribe may still be
  // answered by an operation error, and a read that lands in between must
  // not open the input gate. Set on the first frame of the current op;
  // cleared with every GameStateOpId reset/replacement.
  bool bGameStateOpLive = false;
  // GD-038 auth state: the refresh token is held in memory only (never
  // traced); a failed/expired refresh is terminal for the session.
  FString RefreshToken;
  bool bRefreshInFlight = false;
  bool bSessionExpired = false;
  // S10 review P1(4): bumped on every identity/session change (login,
  // session expiry). Refresh callbacks capture it at dispatch; a deferred
  // answer from the PREVIOUS identity is dropped instead of installing its
  // tokens over the new session.
  int32 AuthGeneration = 0;
  int32 RefreshCount = 0;      // refreshTokens calls issued this session
  int32 RefreshStreak = 0;     // refreshes without a successful response in
                               // between; >= 2 means rotation is not taking
  int32 WsGeneration = 0;      // MakeWs() invocations (WS recreation proof)
  // VS-7 BOOT pass (S08FlowControllerBoot.cpp)
  int32 HeroesFailures = 0;
  EBootQuery BoardsState = EBootQuery::Idle;
  TMap<FString, FString> BoardNames;
  EBootQuery ActiveGameState = EBootQuery::Idle;
  FS08RoomState ActiveGame;
  TSharedPtr<FJsonObject> ActiveGameRow;
  // VS-7 LOBBY (S08FlowControllerLobby.cpp)
  EBootQuery AvailableState = EBootQuery::Idle;
  TArray<FLobbyGame> AvailableGames;
  int32 AvailableAnswers = 0;
  int32 AvailableSerial = 0;
#if WITH_AUTOMATION_TESTS
  int32 TestHttpSendCount = 0; // real SendHttp calls (harness + network)
  TSharedPtr<FJsonObject> TestLastHttpVariables; // variables of the last SendHttp
  TArray<FString> TestHttpQueries; // documents of every SendHttp (bounded)
#endif

#if WITH_AUTOMATION_TESTS
  // Offline HTTP harness state (see QueueHttpResultForTest). A deferred
  // answer pairs its payload snapshot with the callback it resolves, FIFO -
  // so multiple in-flight harness requests (e.g. an old game's echo AND the
  // new game's command) coexist and deliver in order.
  struct FQueuedHttpResult {
    bool bOk = false;
    bool bDeferred = false;
    TArray<FS08GraphQLError> Errors;
    FString RawBody;
  };
  struct FDeferredHttp {
    FQueuedHttpResult Result;
    FS08GraphqlClient::FResult OnDone;
  };
  // FIFO of pre-seeded answers: several results may be queued BEFORE the
  // request that consumes the first one is issued (e.g. poll 401 -> refresh
  // ok -> retried poll); a single slot would silently drop all but the last.
  TArray<FQueuedHttpResult> QueuedHttpFifo;
  TArray<FDeferredHttp> DeferredHttpQueue;
  /** Runs OnDone on the queued result; false = no harness result, use HTTP. */
  bool DispatchQueuedHttpForTest(FS08GraphqlClient::FResult&& OnDone);
  void InvokeQueuedHttpForTest(const FQueuedHttpResult& Result,
                               FS08GraphqlClient::FResult&& OnDone);
#endif
};

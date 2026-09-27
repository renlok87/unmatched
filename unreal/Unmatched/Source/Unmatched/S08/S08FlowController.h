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
enum class ES08CueType : uint8 { FighterMoved, FighterDamaged };

struct UNMATCHED_API FS08Cue {
  ES08CueType Type;
  int32 SequenceNumber = 0;
  FString FighterId;
  int32 FromX = 0, FromY = 0, ToX = 0, ToY = 0; // move
  int32 Damage = 0;                             // health decrease
};

/** One maneuver move: fighter id + orthogonal step path. */
struct UNMATCHED_API FS08ManeuverMove {
  FString FighterId;
  TArray<FIntPoint> Path;
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

  /** Public content heroes (id/name/health/sidekickCount) for the pick UI. */
  const TArray<FS08HeroEntry>& GetHeroes() const { return Heroes; }
  void FetchHeroes();

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

  // ---- BOOT -> LOGIN ----
  void Login(const FString& Email, const FString& Password);

  // ---- LOGIN -> LOBBY ----
  void EnterLobby(); // recovery: myGames(LOBBY) returns an existing room
  // ---- LOBBY ----
  void CreateRoom(const FString& Mode);
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

  /** Applies an incoming snapshot through the seq guard and critical-field
   *  validation. Returns the decision taken (Ignore/Merge/Apply). */
  ES08SeqDecision ApplySnapshot(const FS08Snapshot& Snapshot);

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
  /** Delivers a deferred harness result (see QueueHttpResultForTest). */
  void DeliverQueuedHttpForTest();
  /** Seeds room id + stage so leave paths can be driven without a login. */
  void SetRoomForTest(const FString& GameId, ES08Stage InStage);
  /** Match generation as observed by the guard logic (see MatchGeneration). */
  int32 GetMatchGenerationForTest() const { return MatchGeneration; }
#endif

  // ---- GD-031 gameplay commands (routed through the same store) ----
  /** beginManeuver(expectedSequenceNumber = local seq). On success the store
   *  holds the pending maneuver id (see PendingManeuverId()). */
  void BeginManeuver();
  /** Completes the open maneuver: one move per fighter, orthogonal steps.
   *  GD-033: optional BoostCardId - an exact hand instance id (the card drawn
   *  by beginManeuver is a legal boost: ACC-006/R-03). Empty = no boost. */
  void SubmitManeuver(const FString& ManeuverId, const TArray<FS08ManeuverMove>& Moves,
                      const FString& BoostCardId = FString());
  /** GD-033: endTurn - legal only when actionsRemaining == 0 and no pending
   *  choice (server rejects otherwise; error surfaces through OnFlowError). */
  void EndTurn();
  /** GD-033: discardToLimit - EXACT pending.count own hand instance ids of
   *  the open TURN_END discard choice. */
  void DiscardToLimit(const FString& PendingId, const TArray<FString>& CardInstanceIds);

  // ---- GD-034 combat commands (same store: every echo routes through
  //      ApplySnapshot; the WS duplicate of the same seq merges) ----
  /** attack(attackerId, cardId, targetId) - cardId is the hand INSTANCE id.
   *  Legal for the turn owner in ACTION_* with melee adjacency (server
   *  authoritative; local UI gates mirror it). */
  void Attack(const FString& AttackerFighterId, const FString& CardInstanceId,
              const FString& TargetFighterId);
  /** playDefense(cardId) - defender-only during COMBAT (server deadline
   *  applies; the local UI blocks an expired window). */
  void PlayDefense(const FString& CardInstanceId);
  /** playScheme(cardId) - turn owner in ACTION_*. */
  void PlayScheme(const FString& CardInstanceId);
  /** resolveCombat(): defender "no defense" in COMBAT; ANY participant in
   *  COMBAT_RESOLVE (server rejects everyone else). */
  void ResolveCombat();
  /** GD-035 pending-queue-head resolve. Payload per server
   *  ResolvePendingEffectDto: MOVE/PLACE need FighterId+bHasCell(x,y);
   *  CHOOSE_SPACE bHasCell only; TARGET_FIGHTER FighterId only; CHOOSE_ONE
   *  bHasOption index; DISCARD_CARDS/BOOST_CHOICE/DECK_TOP_PICK exact
   *  CardIds (ORDER = full top->bottom order). declinePendingEffect stays
   *  optional-only. */
  void ResolvePendingEffect(const FString& EffectId, const FString& FighterId,
                            bool bHasCell, int32 X, int32 Y, bool bHasOption,
                            int32 OptionIndex, const TArray<FString>& CardIds);
  void DeclinePendingEffect(const FString& EffectId);

  /** GD-032 freshness: seq of the last body that actually carried the
   *  projection (0 = never seen). WS events omit decks, so counts go
   *  honestly stale ("~") until the next full HTTP body / mutation echo. */
  int32 GetDecksSeq() const { return DecksSeq; }
  int32 GetDiscardPilesSeq() const { return DiscardPilesSeq; }

  /** Lobby freshness via game(id) re-query (named subscriptions have no
   *  snapshot barrier, so they cannot carry room state). */
  void PollRoom();
  /** True while the lobby/room view needs game(id) re-query polling. */
  bool WantsPolling() const {
    return Stage == ES08Stage::Room && Room.Status == TEXT("LOBBY");
  }

private:
  /** Shared executor for the GD-034 combat mutations: in-flight flag, error
   *  broadcast, GameMutationResult parse, ApplySnapshot routing, trace tag.
   *  Traces carry NO card/opponent values (privacy: published logs stay
   *  reveal-free). */
  void RunCombatMutation(const FString& Tag, const TCHAR* Field, const FString& Mutation,
                         const TSharedRef<FJsonObject>& Variables);
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
  /** Cues for one authoritative transition (old vs new fighters), by id. */
  static void ComputeCues(int32 Seq, const TSharedPtr<FJsonValue>& OldFighters,
                          const TSharedPtr<FJsonValue>& NewFighters,
                          TArray<FS08Cue>& OutCues);

  FS08GraphqlClient Http;
  TUniquePtr<FS08GraphqlWs> Ws;
  FString WsUrl;
  FString UserId;
  FString Username;
  FString IdempotencyKey;   // stable across create retries in this session
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
  // GD-032: seq of the last body that carried decks/discardPiles (0 = never).
  int32 DecksSeq = 0;
  int32 DiscardPilesSeq = 0;
  TArray<FString> CriticalProblems;
  TArray<FS08HeroEntry> Heroes;
  bool bManeuverInFlight = false; // INT-005: one logical command at a time
  // WS recovery state: <0 = idle, otherwise seconds until the retry.
  float WsReconnectCountdown = -1.0f;
  float WsReconnectBackoff = 1.0f; // doubles per failure, capped in cpp
  bool bWsReconnectAckPending = false; // ack of a RETRYED connection
  // Operation-level recovery (socket healthy, subscription ended): bounded
  // attempts; reset by the first successfully delivered snapshot. Prevents
  // an error/complete loop (e.g. server rejecting the query) from spinning.
  static constexpr int32 MaxOpRecoveryAttempts = 3;
  int32 OpRecoveryAttempts = 0;

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
  bool bHttpResultQueued = false;
  FQueuedHttpResult QueuedHttp;
  TArray<FDeferredHttp> DeferredHttpQueue;
  /** Runs OnDone on the queued result; false = no harness result, use HTTP. */
  bool DispatchQueuedHttpForTest(FS08GraphqlClient::FResult&& OnDone);
  void InvokeQueuedHttpForTest(const FQueuedHttpResult& Result,
                               FS08GraphqlClient::FResult&& OnDone);
#endif
};

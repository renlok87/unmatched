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
  DECLARE_MULTICAST_DELEGATE_OneParam(FOnTrace, const FString&);
  DECLARE_MULTICAST_DELEGATE_TwoParams(FOnApplied, const FS08Snapshot&, ES08SeqDecision);
  DECLARE_MULTICAST_DELEGATE_OneParam(FOnCues, const TArray<FS08Cue>&);

  FOnStage OnStage;
  FOnRoom OnRoom;
  FOnFlowError OnFlowError;
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
#endif

  // ---- GD-031 gameplay commands (routed through the same store) ----
  /** beginManeuver(expectedSequenceNumber = local seq). On success the store
   *  holds the pending maneuver id (see PendingManeuverId()). */
  void BeginManeuver();
  /** Completes the open maneuver: one move per fighter, orthogonal steps. */
  void SubmitManeuver(const FString& ManeuverId, const TArray<FS08ManeuverMove>& Moves);

  /** Lobby freshness via game(id) re-query (named subscriptions have no
   *  snapshot barrier, so they cannot carry room state). */
  void PollRoom();
  /** True while the lobby/room view needs game(id) re-query polling. */
  bool WantsPolling() const {
    return Stage == ES08Stage::Room && Room.Status == TEXT("LOBBY");
  }

private:
  void SetStage(ES08Stage NewStage);
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
  FS08Snapshot Applied;
  FS08SeqGuard SeqGuard;
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
};

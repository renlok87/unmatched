// GD-028: graphql-transport-ws client (the protocol Apollo's 'graphql-ws'
// library speaks; the backend enables subscriptions['graphql-ws'] = true).
// connection_init carries the JWT via connectionParams.authorization - the
// backend context factory maps it onto req.headers.authorization for the
// GqlAuthGuard. Only gameStateUpdated is subscribed: named CUE events have
// no snapshot barrier (unmatched-net/1 section 4) and must not carry state.
#pragma once

#include "CoreMinimal.h"
#include "S08Contracts.h"
#include "IWebSocket.h"

class UNMATCHED_API FS08GraphqlWs {
public:
  using FSnapshotHandler = TFunction<void(const FS08Snapshot&)>;
  using FErrorHandler = TFunction<void(const FS08GraphQLError&)>;

  FS08GraphqlWs(FString InUrl, FString InAccessToken);
  /** Closes a socket that is still open or connecting: the WebSockets manager keeps the socket alive until its final
   *  close event, so an open one dropped here would live on as a zombie connection (2026-10-21 recheck). */
  ~FS08GraphqlWs();
  FS08GraphqlWs(const FS08GraphqlWs&) = delete;
  FS08GraphqlWs& operator=(const FS08GraphqlWs&) = delete;

  /** Fired once the server accepts connection_init (auth passed). */
  DECLARE_MULTICAST_DELEGATE(FOnAcked);
  FOnAcked OnAcked;

  /** Fired when the transport dies (server close, network error, local Close).
   *  The owner decides what to do: this class never reconnects on its own.
   *  Delivery happens on the game thread. Destroy this object from a deferred
   *  (timer/tick) context; a listener of this delegate may destroy it too (the
   *  listeners run on a copy, 2026-10-21 recheck), the other delegates not. */
  DECLARE_MULTICAST_DELEGATE_TwoParams(FOnWsClosed, int32, const FString&);
  FOnWsClosed OnClosedTransport;

  /** Fired when the server ends a TRACKED operation: a subscription-level
   *  'error' or 'complete' frame, or a 'next' frame that cannot yield a
   *  snapshot (errors[] instead of data, data.gameStateUpdated absent/null,
   *  contract-parse failure) - while the socket itself stays open. The
   *  operation id is already unregistered (Pending removed) - a resubscribe
   *  on this socket must use a NEW id. Not fired for transport closes (see
   *  OnClosedTransport) or for frames of already-unregistered ids. */
  DECLARE_MULTICAST_DELEGATE_TwoParams(FOnOperationEnded, const FString& /*OpId*/,
                                       const FString& /*Reason*/);
  FOnOperationEnded OnOperationEnded;

  /** Fired when a server frame cannot be parsed at all (truncated/garbled
   *  text rejected by the crash-safe pre-scan). The frame cannot be
   *  attributed to an operation id, so this class deliberately leaves its
   *  pending operations untouched: the OWNER decides whether the live
   *  stream is poisoned (bounded refetch/resubscribe or a visible error)
   *  instead of silently waiting on a seq that may never arrive. */
  DECLARE_MULTICAST_DELEGATE_OneParam(FOnMalformedFrame, const FString& /*Problem*/);
  FOnMalformedFrame OnMalformedFrame;

  void Connect();
  void Close();
  bool IsAcked() const { return bAcked; }

  /** Subscribes to gameStateUpdated(gameId, since). Returns the operation id
   *  (empty on immediate failure). The snapshot handler runs for every
   *  'next' message; parse failures go to the error handler. */
  FString SubscribeGameStateUpdated(const FString& GameId, int32 Since,
                                    FSnapshotHandler OnSnapshot, FErrorHandler OnError);
  void Unsubscribe(const FString& OperationId);

#if WITH_AUTOMATION_TESTS
  /** Test seams: drive the protocol state machine without a socket. */
  void ForceAckedForTest() { bAcked = true; }
  void InjectServerFrameForTest(const FString& Raw) { HandleMessage(Raw); }
  /** Every outgoing frame (subscribe/complete/pong), including the ones a
   *  socket-less harness produces - proves client->server traffic. */
  const TArray<FString>& GetSentFramesForTest() const { return SentFramesForTest; }
  /** The exact callable the socket's OnClosed / OnConnectionError bindings
   *  run (it may outlive this object, as a socket callback does). */
  TFunction<void(int32, const FString&)> TransportEndedHandlerForTest() { return MakeTransportEndedHandler(); }
#endif

private:
  void SendMessage(const TSharedRef<FJsonObject>& Message);
  void HandleMessage(const FString& Raw);
  /** connection_init with the JWT (the socket's OnConnected). */
  void SendConnectionInit();
  /** The socket closed or failed: drop the ack and the operations, tell the owner (OnClosedTransport). */
  void HandleTransportEnded(int32 StatusCode, const FString& Reason);
  /** The socket's close / error callback: HandleTransportEnded on the game thread while this object lives. */
  TFunction<void(int32, const FString&)> MakeTransportEndedHandler();
  /** Best-effort graphql-transport-ws "complete" for an operation id. */
  void SendComplete(const FString& OperationId);
  /** "message" fields from a GraphQL errors[] array, joined with '; '.
   *  Tolerates missing/non-object entries (partial errors). */
  static FString JoinErrorMessages(const TArray<TSharedPtr<FJsonValue>>& Errors);

  struct FPending {
    FSnapshotHandler OnSnapshot;
    FErrorHandler OnError;
  };
  FString Url;
  FString AccessToken;
  TSharedPtr<IWebSocket> Socket;
  TMap<FString, FPending> Pending;
  int32 NextOperationId = 0;
  bool bAcked = false;
  /** The socket reported its end (closed / failed) or Close() asked for it: the destructor does not close it again. */
  bool bSocketEnded = false;
  /** 2026-10-21 recheck (dev client: MTAccessDetector ensure in the close lambda of Connect, then an access violation,
   *  on a backend restart): the socket outlives this object - the WebSockets manager holds it until its final close
   *  event - so its callbacks hold this token weakly and do nothing once it is gone, and they reach this object only
   *  on the game thread (queued there when a callback ever comes from another thread). */
  TSharedRef<bool, ESPMode::ThreadSafe> AliveToken = MakeShared<bool, ESPMode::ThreadSafe>(true);
#if WITH_AUTOMATION_TESTS
  TArray<FString> SentFramesForTest;
#endif
};

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

  /** Fired once the server accepts connection_init (auth passed). */
  DECLARE_MULTICAST_DELEGATE(FOnAcked);
  FOnAcked OnAcked;

  /** Fired when the transport dies (server close, network error, local Close).
   *  The owner decides what to do: this class never reconnects on its own.
   *  Delivery happens on the game thread; it is safe to destroy this object
   *  from a deferred (timer/tick) context, but NOT from inside the delegate. */
  DECLARE_MULTICAST_DELEGATE_TwoParams(FOnWsClosed, int32, const FString&);
  FOnWsClosed OnClosedTransport;

  /** Fired when the server ends a TRACKED operation: a subscription-level
   *  'error' or 'complete' frame while the socket itself stays open. The
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
#endif

private:
  void SendMessage(const TSharedRef<FJsonObject>& Message);
  void HandleMessage(const FString& Raw);
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
};

#include "S08GraphqlWs.h"
#include "CoreMinimal.h"
#include "S08Contracts.h"
#include "WebSocketsModule.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

static const TCHAR* GQLWsQuery =
    TEXT("subscription G($gameId: String!, $since: Float) { gameStateUpdated(gameId: $gameId, since: $since) {")
    TEXT(" gameId sequenceNumber phase turnCount currentTurnPlayerId")
    TEXT(" players fighters handZones discardPiles boardState metadata } }");

FS08GraphqlWs::FS08GraphqlWs(FString InUrl, FString InAccessToken)
    : Url(MoveTemp(InUrl)), AccessToken(MoveTemp(InAccessToken)) {}

void FS08GraphqlWs::Connect() {
  // A dead socket object (closed transport) is replaced here, on the game
  // thread - never from inside the old socket's own close delegate.
  if (Socket.IsValid() && Socket->IsConnected()) return;
  Socket = FWebSocketsModule::Get().CreateWebSocket(Url, TEXT("graphql-transport-ws"));
  if (!Socket.IsValid()) return;

  Socket->OnConnected().AddLambda([this]() {
    // Auth happens at connection level: the backend reads
    // connectionParams.authorization before the GqlAuthGuard runs.
    TSharedRef<FJsonObject> Init = MakeShared<FJsonObject>();
    Init->SetStringField(TEXT("type"), TEXT("connection_init"));
    TSharedRef<FJsonObject> Params = MakeShared<FJsonObject>();
    Params->SetStringField(TEXT("authorization"), TEXT("Bearer ") + AccessToken);
    Init->SetObjectField(TEXT("payload"), Params);
    SendMessage(Init);
  });
  Socket->OnMessage().AddLambda([this](const FString& Message) { HandleMessage(Message); });
  Socket->OnConnectionError().AddLambda([this](const FString& Error) {
    bAcked = false;
    Pending.Reset();
    OnClosedTransport.Broadcast(-1, Error);
  });
  Socket->OnClosed().AddLambda([this](int32 StatusCode, const FString& Reason, bool) {
    bAcked = false;
    Pending.Reset();
    OnClosedTransport.Broadcast(StatusCode, Reason);
  });
  Socket->Connect();
}

void FS08GraphqlWs::Close() {
  // The ack state dies with the close even without a live transport (a
  // force-acked test harness has no Socket): IsStreamReady() must observe
  // the drop immediately, not only after a close handshake.
  bAcked = false;
  Pending.Reset();
  if (!Socket.IsValid()) return;
  // Unconditional: Close() on a socket whose connect is still in flight
  // cancels it. Gating on IsConnected() lets a dropped socket complete its
  // handshake afterwards and ack as a zombie - its OnAcked would subscribe
  // through an object that is about to be destroyed.
  Socket->Close();
}

void FS08GraphqlWs::SendMessage(const TSharedRef<FJsonObject>& Message) {
  if (!Socket.IsValid() || !Socket->IsConnected()) return;
  FString Serialized;
  TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Serialized);
  FJsonSerializer::Serialize(Message, Writer);
  Socket->Send(Serialized);
}

FString FS08GraphqlWs::SubscribeGameStateUpdated(const FString& GameId, int32 Since,
                                                 FSnapshotHandler OnSnapshot,
                                                 FErrorHandler OnError) {
  if (!bAcked) {
    OnError({TEXT("PROTOCOL"), TEXT("Subscribe before connection_ack - wait for the handshake"), FString()});
    return FString();
  }
  const FString OperationId = FString::Printf(TEXT("s08-%d"), ++NextOperationId);
  Pending.Add(OperationId, {MoveTemp(OnSnapshot), MoveTemp(OnError)});

  TSharedRef<FJsonObject> Subscribe = MakeShared<FJsonObject>();
  Subscribe->SetStringField(TEXT("id"), OperationId);
  Subscribe->SetStringField(TEXT("type"), TEXT("subscribe"));
  TSharedRef<FJsonObject> Payload = MakeShared<FJsonObject>();
  Payload->SetStringField(TEXT("query"), GQLWsQuery);
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), GameId);
  Variables->SetNumberField(TEXT("since"), Since);
  Payload->SetObjectField(TEXT("variables"), Variables);
  Subscribe->SetObjectField(TEXT("payload"), Payload);
  SendMessage(Subscribe);
  return OperationId;
}

void FS08GraphqlWs::Unsubscribe(const FString& OperationId) {
  if (!Pending.Contains(OperationId)) return;
  Pending.Remove(OperationId);
  TSharedRef<FJsonObject> Complete = MakeShared<FJsonObject>();
  Complete->SetStringField(TEXT("id"), OperationId);
  Complete->SetStringField(TEXT("type"), TEXT("complete"));
  SendMessage(Complete);
}

void FS08GraphqlWs::HandleMessage(const FString& Raw) {
  // Truncated/malformed frames are dropped here, BEFORE UE's reader: its
  // ParseStringToken crashes fatally on truncated-string shapes (the
  // crash-safe pre-scan in TryParseJsonObject rejects them instead).
  TSharedPtr<FJsonObject> Message;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(Raw, Message, Problem)) {
    UE_LOG(LogTemp, Warning, TEXT("S08 WS: dropped malformed message (%s)"), *Problem);
    // Not silently swallowed: the frame has no readable id, so the owner is
    // notified and decides (bounded recovery or a visible error). This class
    // keeps its pending operations registered - see OnMalformedFrame.
    OnMalformedFrame.Broadcast(Problem);
    return;
  }
  const FString Type = Message->GetStringField(TEXT("type"));
  const FString Id = Message->GetStringField(TEXT("id"));

  if (Type == TEXT("connection_ack")) {
    bAcked = true;
    OnAcked.Broadcast();
    return;
  }
  if (Type == TEXT("ping")) {
    TSharedRef<FJsonObject> Pong = MakeShared<FJsonObject>();
    Pong->SetStringField(TEXT("type"), TEXT("pong"));
    SendMessage(Pong);
    return;
  }
  if (Type == TEXT("pong")) return;

  FPending* Handler = Pending.Find(Id);
  if (!Handler) return; // complete/next after unsubscribe

  if (Type == TEXT("next")) {
    const TSharedPtr<FJsonObject>* Payload = nullptr;
    Message->TryGetObjectField(TEXT("payload"), Payload);
    // Partial failure: 'next' can carry errors[] alongside (or instead of)
    // data - surface them instead of silently parsing an absent field.
    if (Payload && Payload->IsValid()) {
      const TArray<TSharedPtr<FJsonValue>>* NextErrors = nullptr;
      if ((*Payload)->TryGetArrayField(TEXT("errors"), NextErrors) && NextErrors &&
          NextErrors->Num() > 0) {
        const FString Reason = JoinErrorMessages(*NextErrors);
        Handler->OnError({TEXT("PROTOCOL"),
                          Reason.IsEmpty() ? TEXT("gameStateUpdated 'next' failed") : Reason,
                          FString()});
        return;
      }
    }
    const TSharedPtr<FJsonObject>* Data = nullptr;
    if (Payload && Payload->IsValid() && (*Payload)->TryGetObjectField(TEXT("data"), Data) &&
        Data && Data->IsValid()) {
      const TSharedPtr<FJsonObject>* Event = nullptr;
      if ((*Data)->TryGetObjectField(TEXT("gameStateUpdated"), Event) && Event && Event->IsValid()) {
        FS08Snapshot Snapshot;
        FS08GraphQLError Error;
        if (FS08Contracts::ParseGameStateUpdated(Event->ToSharedRef(), Snapshot, Error)) {
          Handler->OnSnapshot(Snapshot);
        } else {
          Handler->OnError(Error);
        }
        return;
      }
    }
    Handler->OnError({TEXT("PARSE"), TEXT("gameStateUpdated 'next' payload has unexpected shape"),
                      FString()});
    return;
  }
  if (Type == TEXT("error")) {
    // graphql-transport-ws sends 'error' with an ARRAY of GraphQL error
    // objects; older servers send a single object. Accept both.
    FString Reason = TEXT("subscription failed");
    const TArray<TSharedPtr<FJsonValue>>* ErrorArray = nullptr;
    if (Message->TryGetArrayField(TEXT("payload"), ErrorArray) && ErrorArray) {
      const FString Joined = JoinErrorMessages(*ErrorArray);
      if (!Joined.IsEmpty()) Reason = Joined;
    } else {
      const TSharedPtr<FJsonObject>* Payload = nullptr;
      if (Message->TryGetObjectField(TEXT("payload"), Payload) && Payload->IsValid()) {
        const FString Single = (*Payload)->GetStringField(TEXT("message"));
        if (!Single.IsEmpty()) Reason = Single;
      }
    }
    Handler->OnError({TEXT("PROTOCOL"), Reason, FString()});
    Pending.Remove(Id);
    // Operation-level failure on a healthy socket: the id is dead but the
    // transport is not - surface it so the owner can resubscribe with a new
    // id (ScheduleWsReconnect covers the transport-level counterpart).
    OnOperationEnded.Broadcast(Id, Reason);
    return;
  }
  if (Type == TEXT("complete")) {
    Pending.Remove(Id);
    OnOperationEnded.Broadcast(Id, TEXT("complete"));
  }
}

FString FS08GraphqlWs::JoinErrorMessages(const TArray<TSharedPtr<FJsonValue>>& Errors) {
  TArray<FString> Messages;
  for (const TSharedPtr<FJsonValue>& Value : Errors) {
    const TSharedPtr<FJsonObject>* Object = nullptr;
    if (!Value.IsValid() || !Value->TryGetObject(Object) || !Object || !Object->IsValid()) continue;
    const FString Message = (*Object)->GetStringField(TEXT("message"));
    if (!Message.IsEmpty()) Messages.Add(Message);
  }
  return FString::Join(Messages, TEXT("; "));
}

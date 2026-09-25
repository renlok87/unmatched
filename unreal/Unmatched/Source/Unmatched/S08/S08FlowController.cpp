#include "S08FlowController.h"
#include "Dom/JsonObject.h"
#include "Misc/Guid.h"

// Operations verified against the live SDL (evidence/S08/live-schema.graphql):
// login(input: LoginDto!), myGames(filters), game(id), gameByCode(code),
// createGame(input, idempotencyKey), joinGame(input), selectHero,
// toggleReady, startGame, gameState(gameId).
static const TCHAR* LoginQuery =
    TEXT("mutation L($input: LoginDto!) { login(input: $input) {")
    TEXT(" accessToken refreshToken user { id username } } }");

static const TCHAR* MyGamesQuery =
    TEXT("query M($status: GameStatus) { myGames(filters: { status: $status }) {")
    TEXT(" id code status mode hostId boardId")
    TEXT(" players { userId username heroId isReady seatOrder } } }");

static const TCHAR* GameQuery =
    TEXT("query G($id: String!) { game(id: $id) {")
    TEXT(" id code status mode hostId boardId")
    TEXT(" players { userId username heroId isReady seatOrder } } }");

static const TCHAR* GameByCodeQuery =
    TEXT("query C($code: String!) { gameByCode(code: $code) {")
    TEXT(" id code status mode hostId boardId")
    TEXT(" players { userId username heroId isReady seatOrder } } }");

static const TCHAR* CreateGameMutation =
    TEXT("mutation Cr($input: CreateGameDto!, $idempotencyKey: String) {")
    TEXT(" createGame(input: $input, idempotencyKey: $idempotencyKey) {")
    TEXT(" id code status mode hostId boardId")
    TEXT(" players { userId username heroId isReady seatOrder } } }");

static const TCHAR* JoinGameMutation =
    TEXT("mutation J($input: JoinGameDto!) { joinGame(input: $input) {")
    TEXT(" id code status mode hostId boardId")
    TEXT(" players { userId username heroId isReady seatOrder } } }");

static const TCHAR* SelectHeroMutation =
    TEXT("mutation S($gameId: String!, $heroId: String!) {")
    TEXT(" selectHero(gameId: $gameId, heroId: $heroId) {")
    TEXT(" id code status mode hostId boardId")
    TEXT(" players { userId username heroId isReady seatOrder } } }");

static const TCHAR* ToggleReadyMutation =
    TEXT("mutation R($gameId: String!) { toggleReady(gameId: $gameId) {")
    TEXT(" id code status mode hostId boardId")
    TEXT(" players { userId username heroId isReady seatOrder } } }");

static const TCHAR* StartGameMutation =
    TEXT("mutation St($gameId: String!) { startGame(gameId: $gameId) {")
    TEXT(" id code status mode hostId boardId")
    TEXT(" players { userId username heroId isReady seatOrder } } }");

static const TCHAR* LeaveGameMutation =
    TEXT("mutation Lv($gameId: String!) { leaveGame(gameId: $gameId) }");

static const TCHAR* GameStateQuery =
    TEXT("query GS($gameId: String!) { gameState(gameId: $gameId) {")
    TEXT(" id gameId state sequenceNumber phase turnCount currentTurnPlayerId updatedAt } }");

FS08FlowController::FS08FlowController(FString HttpUrl, FString WsUrlIn, FString InViewerId)
    : Http(MoveTemp(HttpUrl)), WsUrl(MoveTemp(WsUrlIn)), UserId(MoveTemp(InViewerId)) {
  // One stable key per client session: createGame retries (double click,
  // lost answer) resolve to the SAME room instead of creating a duplicate.
  IdempotencyKey = TEXT("s08-") + FGuid::NewGuid().ToString(EGuidFormats::Digits);
}

// Hero pick uses the PRISMA hero list (cuid ids): selectHero/joinGame
// validate heroId against the database, while the content `heroes` query
// serves scraped slug ids from static files - a different id space.
static const TCHAR* HeroesQuery =
    TEXT("query HL($limit: Int) { heroList(limit: $limit) { items { id name health } } }");

void FS08FlowController::FetchHeroes() {
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetNumberField(TEXT("limit"), 200);
  Http.Execute(HeroesQuery, Variables,
               [this](bool bOk, const TArray<FS08GraphQLError>& Errors,
                      TSharedPtr<FJsonObject> Data, const FString&) {
                 if (!bOk) {
                   Trace(TEXT("HEROES failed: ") + (Errors.Num() ? Errors[0].Message : TEXT("?")));
                   return;
                 }
                 Heroes.Reset();
                 const TSharedPtr<FJsonObject>* List = nullptr;
                 const TArray<TSharedPtr<FJsonValue>>* Items = nullptr;
                 if (Data.IsValid() && Data->TryGetObjectField(TEXT("heroList"), List) && List &&
                     (*List)->TryGetArrayField(TEXT("items"), Items) && Items) {
                   for (const TSharedPtr<FJsonValue>& Value : *Items) {
                     const TSharedPtr<FJsonObject>* Hero = nullptr;
                     if (!Value.IsValid() || !Value->TryGetObject(Hero) || !Hero->IsValid()) continue;
                     FS08HeroEntry Entry;
                     Entry.Id = (*Hero)->GetStringField(TEXT("id"));
                     Entry.Name = (*Hero)->GetStringField(TEXT("name"));
                     double Number = 0.0;
                     if ((*Hero)->TryGetNumberField(TEXT("health"), Number)) Entry.Health = static_cast<int32>(Number);
                     Heroes.Add(MoveTemp(Entry));
                   }
                 }
                 Trace(FString::Printf(TEXT("HEROES loaded %d"), Heroes.Num()));
                 OnRoom.Broadcast(Room); // refresh pick UI
               });
}

void FS08FlowController::SetStage(ES08Stage NewStage) {
  if (Stage == NewStage) return;
  Stage = NewStage;
  OnStage.Broadcast(Stage);
}

void FS08FlowController::Trace(const FString& Line) { OnTrace.Broadcast(Line); }

void FS08FlowController::Login(const FString& Email, const FString& Password) {
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  TSharedRef<FJsonObject> Input = MakeShared<FJsonObject>();
  Input->SetStringField(TEXT("email"), Email);
  Input->SetStringField(TEXT("password"), Password);
  Variables->SetObjectField(TEXT("input"), Input);
  Http.Execute(LoginQuery, Variables,
               [this](bool bOk, const TArray<FS08GraphQLError>& Errors,
                      TSharedPtr<FJsonObject> Data, const FString& RawBody) {
                 FString AccessToken, RefreshToken, UserId, Username;
                 FS08GraphQLError Error;
                 // Two-stage: contract parser handles the login envelope.
                 if (FS08Contracts::ParseAuthResponse(RawBody, AccessToken, RefreshToken, UserId,
                                                      Username, Error)) {
                   this->UserId = UserId;
                   this->Username = Username;
                   Http.SetAccessToken(AccessToken);
                   Trace(TEXT("LOGIN ok user=") + Username);
                   SetStage(ES08Stage::Login);
                 } else {
                   Trace(TEXT("LOGIN failed: ") + Error.Message);
                   OnFlowError.Broadcast(Error);
                   SetStage(ES08Stage::Failed);
                 }
               });
}

void FS08FlowController::EnterLobby() {
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("status"), TEXT("LOBBY"));
  Http.Execute(MyGamesQuery, Variables,
               [this](bool bOk, const TArray<FS08GraphQLError>& Errors,
                      TSharedPtr<FJsonObject> Data, const FString&) {
                 if (!bOk) {
                   Trace(TEXT("MYGAMES failed: ") + (Errors.Num() ? Errors[0].Message : TEXT("?")));
                   SetStage(ES08Stage::Lobby); // fresh lobby without recovery
                   return;
                 }
                 // Recovery: a missed PLAYER_JOINED is irrelevant - the room
                 // itself (if any) is re-derived from myGames, not from
                 // cached lobby events.
                 const TArray<TSharedPtr<FJsonValue>>* Games = nullptr;
                 if (Data.IsValid() && Data->TryGetArrayField(TEXT("myGames"), Games) &&
                     Games && Games->Num() > 0) {
                   const TSharedPtr<FJsonObject>* First = nullptr;
                   if ((*Games)[0]->TryGetObject(First) && First && First->IsValid()) {
                     ParseRoomFrom(*First);
                     Trace(TEXT("RECOVER room=") + Room.GameId + TEXT(" code=") + Room.Code);
                     SetStage(ES08Stage::Room);
                     return;
                   }
                 }
                 Trace(TEXT("LOBBY fresh (no rooms)"));
                 SetStage(ES08Stage::Lobby);
               });
}

void FS08FlowController::CreateRoom(const FString& Mode) {
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  TSharedRef<FJsonObject> Input = MakeShared<FJsonObject>();
  Input->SetStringField(TEXT("mode"), Mode.IsEmpty() ? TEXT("ONE_V_ONE") : Mode);
  Variables->SetObjectField(TEXT("input"), Input);
  Variables->SetStringField(TEXT("idempotencyKey"), IdempotencyKey);
  Http.Execute(CreateGameMutation, Variables,
               [this](bool bOk, const TArray<FS08GraphQLError>& Errors,
                      TSharedPtr<FJsonObject> Data, const FString&) {
                 if (!bOk) {
                   Trace(TEXT("CREATE failed: ") + (Errors.Num() ? Errors[0].Message : TEXT("?")));
                   OnFlowError.Broadcast(Errors.Num() ? Errors[0]
                                                      : FS08GraphQLError{TEXT("TRANSPORT"), TEXT("create failed"), FString()});
                   return;
                 }
                 HandleRoomResponse(Data, TEXT("createGame"));
               });
}

void FS08FlowController::JoinRoomByCode(const FString& Code) {
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("code"), Code);
  Http.Execute(GameByCodeQuery, Variables,
               [this, Code](bool bOk, const TArray<FS08GraphQLError>& Errors,
                            TSharedPtr<FJsonObject> Data, const FString&) {
                 if (!bOk) {
                   Trace(TEXT("CODE LOOKUP failed: ") + (Errors.Num() ? Errors[0].Message : TEXT("?")));
                   OnFlowError.Broadcast(Errors.Num() ? Errors[0]
                                                      : FS08GraphQLError{TEXT("TRANSPORT"), TEXT("code lookup failed"), FString()});
                   return;
                 }
                 const TSharedPtr<FJsonObject>* ByCode = nullptr;
                 if (Data.IsValid() && Data->TryGetObjectField(TEXT("gameByCode"), ByCode) &&
                     ByCode && ByCode->IsValid()) {
                   // gameByCode returns the room fields directly (id/code/...)
                   // or null when the code is unknown/full/already started.
                   const FString GameId = (*ByCode)->GetStringField(TEXT("id"));
                   if (!GameId.IsEmpty()) {
                     Trace(TEXT("CODE resolved -> ") + GameId);
                     TSharedRef<FJsonObject> JoinVars = MakeShared<FJsonObject>();
                     TSharedRef<FJsonObject> JoinInput = MakeShared<FJsonObject>();
                     JoinInput->SetStringField(TEXT("gameId"), GameId);
                     JoinVars->SetObjectField(TEXT("input"), JoinInput);
                     Http.Execute(JoinGameMutation, JoinVars,
                                  [this](bool bOk2, const TArray<FS08GraphQLError>& Errors2,
                                         TSharedPtr<FJsonObject> Data2, const FString&) {
                                    if (!bOk2) {
                                      Trace(TEXT("JOIN failed: ") +
                                            (Errors2.Num() ? Errors2[0].Message : TEXT("?")));
                                      OnFlowError.Broadcast(Errors2.Num()
                                                                ? Errors2[0]
                                                                : FS08GraphQLError{TEXT("TRANSPORT"), TEXT("join failed"), FString()});
                                      return;
                                    }
                                    HandleRoomResponse(Data2, TEXT("joinGame"));
                                  });
                     return;
                   }
                   {
                     FS08GraphQLError Error{TEXT("NOT_FOUND"),
                                            TEXT("Room code not found or no longer joinable"),
                                            FString()};
                     Trace(TEXT("CODE not found: ") + Code);
                     OnFlowError.Broadcast(Error);
                   }
                 } else {
                  // null game: unknown/full/started codes are indistinguishable.
                   FS08GraphQLError Error{TEXT("NOT_FOUND"),
                                          TEXT("Room code not found or no longer joinable"),
                                          FString()};
                   Trace(TEXT("CODE not found: ") + Code);
                   OnFlowError.Broadcast(Error);
                 }
               });
}

void FS08FlowController::SelectHero(const FString& HeroId) {
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Variables->SetStringField(TEXT("heroId"), HeroId);
  Http.Execute(SelectHeroMutation, Variables,
               [this](bool bOk, const TArray<FS08GraphQLError>& Errors,
                      TSharedPtr<FJsonObject> Data, const FString&) {
                 if (!bOk) {
                   Trace(TEXT("SELECT failed: ") + (Errors.Num() ? Errors[0].Message : TEXT("?")));
                   OnFlowError.Broadcast(Errors.Num() ? Errors[0]
                                                      : FS08GraphQLError{TEXT("TRANSPORT"), TEXT("select failed"), FString()});
                   return;
                 }
                 HandleRoomResponse(Data, TEXT("selectHero"));
               });
}

void FS08FlowController::ToggleReady() {
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Http.Execute(ToggleReadyMutation, Variables,
               [this](bool bOk, const TArray<FS08GraphQLError>& Errors,
                      TSharedPtr<FJsonObject> Data, const FString&) {
                 if (!bOk) {
                   Trace(TEXT("READY failed: ") + (Errors.Num() ? Errors[0].Message : TEXT("?")));
                   OnFlowError.Broadcast(Errors.Num() ? Errors[0]
                                                      : FS08GraphQLError{TEXT("TRANSPORT"), TEXT("ready failed"), FString()});
                   return;
                 }
                 HandleRoomResponse(Data, TEXT("toggleReady"));
               });
}

void FS08FlowController::StartGame() {
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Http.Execute(StartGameMutation, Variables,
               [this](bool bOk, const TArray<FS08GraphQLError>& Errors,
                      TSharedPtr<FJsonObject> Data, const FString&) {
                 if (!bOk) {
                   Trace(TEXT("START failed: ") + (Errors.Num() ? Errors[0].Message : TEXT("?")));
                   OnFlowError.Broadcast(Errors.Num() ? Errors[0]
                                                      : FS08GraphQLError{TEXT("TRANSPORT"), TEXT("start failed"), FString()});
                   return;
                 }
                 HandleRoomResponse(Data, TEXT("startGame"));
                 if (Room.Status == TEXT("IN_PROGRESS")) {
                   AttachGameStateStream();
                 }
               });
}

void FS08FlowController::LeaveRoom() {
  if (Room.GameId.IsEmpty()) return;
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  const FString GameId = Room.GameId;
  Http.Execute(LeaveGameMutation, Variables,
               [this, GameId](bool bOk, const TArray<FS08GraphQLError>&,
                              TSharedPtr<FJsonObject>, const FString&) {
                 Trace(bOk ? TEXT("LEFT room=") + GameId
                           : TEXT("LEAVE reported failure (room may already be gone)"));
                 Room = FS08RoomState();
                 SetStage(ES08Stage::Lobby);
               });
}

void FS08FlowController::MakeWs() {
  Ws = MakeUnique<FS08GraphqlWs>(WsUrl, Http.GetAccessToken());
  BindWsHandlers();
  Ws->Connect();
}

void FS08FlowController::BindWsHandlers() {
  Ws->OnAcked.AddLambda([this]() {
    WsReconnectBackoff = 1.0f; // healthy handshake resets the growth
    SubscribeAfterSnapshot(SeqGuard.HasLocal ? SeqGuard.Local : 0);
    if (bWsReconnectAckPending) {
      bWsReconnectAckPending = false;
      // Recovery: the refetch carries anything published while offline; the
      // resubscribe above already runs with since = applied seq, so the two
      // channels converge through the seq guard.
      Trace(TEXT("WS reconnected - refetching gameState"));
      FetchGameState();
    }
  });
  Ws->OnClosedTransport.AddLambda([this](int32 StatusCode, const FString& Reason) {
    if (Stage == ES08Stage::Started) {
      ScheduleWsReconnect(FString::Printf(TEXT("code %d %s"), StatusCode, *Reason));
    }
  });
  Ws->OnOperationEnded.AddLambda([this](const FString& OpId, const FString& Reason) {
    HandleOperationEnded(OpId, Reason);
  });
  Ws->OnMalformedFrame.AddLambda([this](const FString& Problem) {
    HandleStreamPoisoned(FString::Printf(TEXT("malformed frame: %s"), *Problem));
  });
}

void FS08FlowController::HandleOperationEnded(const FString& OpId, const FString& Reason) {
  // Stale notification: the op was already replaced by a recovery resubscribe.
  if (GameStateOpId != OpId) return;
  GameStateOpId.Reset();
  if (Stage != ES08Stage::Started) return;
  if (OpRecoveryAttempts >= MaxOpRecoveryAttempts) {
    // Bounded: an error/complete loop (server keeps rejecting the operation)
    // must not spin forever on an otherwise healthy socket.
    Trace(FString::Printf(TEXT("WS subscription failed %d times - giving up (%s)"),
                          MaxOpRecoveryAttempts, *Reason));
    OnFlowError.Broadcast(FS08GraphQLError{TEXT("PROTOCOL"), Reason, FString()});
    return;
  }
  ++OpRecoveryAttempts;
  Trace(FString::Printf(TEXT("WS operation ended (%s) - refetch + resubscribe %d/%d"),
                        *Reason, OpRecoveryAttempts, MaxOpRecoveryAttempts));
  // Same open socket, NEW operation id: the HTTP barrier refetch closes the
  // gap and its callback resubscribes from the fetched seq; on fetch failure
  // the resubscribe still runs from the local seq (server barrier snapshot
  // corrects any gap).
  FetchGameState();
  if (Ws.IsValid() && Ws->IsAcked()) {
    SubscribeAfterSnapshot(SeqGuard.HasLocal ? SeqGuard.Local : 0);
  }
}

void FS08FlowController::HandleStreamPoisoned(const FString& Reason) {
  // An unparseable frame carries no readable operation id: if a live
  // subscription exists, it is dropped (best-effort 'complete' to the
  // server) and driven through the SAME bounded refetch+resubscribe path
  // as an operation-level failure, so a server that keeps emitting garbage
  // surfaces through OnFlowError after MaxOpRecoveryAttempts instead of the
  // client silently hanging on a stale applied seq. No live operation
  // (e.g. garbage during the handshake) leaves nothing to poison.
  if (Stage != ES08Stage::Started || GameStateOpId.IsEmpty()) return;
  const FString PoisonedId = GameStateOpId;
  if (Ws.IsValid()) Ws->Unsubscribe(PoisonedId);
  HandleOperationEnded(PoisonedId, Reason);
}

#if WITH_AUTOMATION_TESTS
void FS08FlowController::AttachStreamHarnessForTest(const FString& GameId) {
  Room.GameId = GameId;
  if (!Ws.IsValid()) {
    Ws = MakeUnique<FS08GraphqlWs>(WsUrl, FString());
    BindWsHandlers();
  }
  Ws->ForceAckedForTest();
  SetStage(ES08Stage::Started);
  SubscribeAfterSnapshot(0);
}
#endif

void FS08FlowController::AttachGameStateStream() {
  // Barrier protocol (unmatched-net/1 section 4): the ORDER of HTTP snapshot
  // and WS subscribe does not need to be strict - the subscription is opened
  // with since = local seq and the server delivers a barrier snapshot when
  // the state moved past it; duplicates collapse in the seq guard.
  FetchGameState();
  if (!Ws.IsValid()) {
    MakeWs();
  }
  SetStage(ES08Stage::Started);
}

void FS08FlowController::ScheduleWsReconnect(const FString& Reason) {
  // The dead FS08GraphqlWs object is destroyed on the next retry boundary
  // (TickConnectivity), never from inside its own close delegate.
  GameStateOpId.Reset();
  if (WsReconnectCountdown >= 0.0f) return; // already armed
  static constexpr float MaxBackoffSeconds = 15.0f;
  WsReconnectCountdown = WsReconnectBackoff;
  WsReconnectBackoff = FMath::Min(WsReconnectBackoff * 2.0f, MaxBackoffSeconds);
  Trace(FString::Printf(TEXT("WS closed (%s) - reconnect in %.0fs"), *Reason,
                        WsReconnectCountdown));
}

void FS08FlowController::TickConnectivity(float DeltaSeconds) {
  if (WsReconnectCountdown < 0.0f) return;
  WsReconnectCountdown -= DeltaSeconds;
  if (WsReconnectCountdown > 0.0f) return;
  WsReconnectCountdown = -1.0f;
  Trace(TEXT("WS reconnect attempt"));
  if (Ws.IsValid()) Ws.Reset();
  // A zombie subscribe id (registered by a dying socket between the close
  // and this reset) must never block the fresh handshake's resubscribe.
  GameStateOpId.Reset();
  bWsReconnectAckPending = true;
  MakeWs();
}

void FS08FlowController::DropWsForTest() {
  if (!Ws.IsValid()) return;
  Trace(TEXT("WS DROPPED (test-initiated transport loss)"));
  Ws->Close();
  // Deterministic arming even if the close handshake's OnClosed is delayed.
  if (Stage == ES08Stage::Started) ScheduleWsReconnect(TEXT("test drop"));
}

void FS08FlowController::SubscribeAfterSnapshot(int32 Since) {
  if (!GameStateOpId.IsEmpty() || !Ws.IsValid() || !Ws->IsAcked()) return;
  GameStateOpId = Ws->SubscribeGameStateUpdated(
      Room.GameId, Since,
      [this](const FS08Snapshot& Snapshot) {
        // A delivered snapshot proves the recovered operation works - the
        // bounded operation-level recovery counter starts over.
        OpRecoveryAttempts = 0;
        const ES08SeqDecision Decision = ApplySnapshot(Snapshot);
        if (Decision == ES08SeqDecision::Ignore) return;
        Trace(FString::Printf(TEXT("WS seq=%d phase=%s (%s)"), Snapshot.SequenceNumber,
                              *Snapshot.Phase,
                              Decision == ES08SeqDecision::Apply ? TEXT("apply") : TEXT("merge")));
      },
      [this](const FS08GraphQLError& Error) {
        Trace(TEXT("WS error: ") + Error.Message);
        OnFlowError.Broadcast(Error);
      });
  Trace(FString::Printf(TEXT("SUBSCRIBED gameStateUpdated since=%d"), Since));
}

void FS08FlowController::FetchGameState() {
  if (Room.GameId.IsEmpty()) return;
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Http.Execute(GameStateQuery, Variables,
               [this](bool bOk, const TArray<FS08GraphQLError>& Errors,
                      TSharedPtr<FJsonObject> Data, const FString& RawBody) {
                 if (!bOk) {
                   if (FS08Contracts::IsLobbyPhaseAbsent(Errors)) {
                     Trace(TEXT("STATE: not started yet (lobby)"));
                     return;
                   }
                   Trace(TEXT("STATE failed: ") + (Errors.Num() ? Errors[0].Message : TEXT("?")));
                   OnFlowError.Broadcast(Errors.Num() ? Errors[0]
                                                      : FS08GraphQLError{TEXT("TRANSPORT"), TEXT("state failed"), FString()});
                   return;
                 }
                 FS08Snapshot Snapshot;
                 FString RawState;
                 FS08GraphQLError Error;
                 if (FS08Contracts::ParseGameStateQuery(RawBody, Snapshot, RawState, Error)) {
                   const ES08SeqDecision Decision = ApplySnapshot(Snapshot);
                   Trace(FString::Printf(TEXT("STATE seq=%d -> %s"), Snapshot.SequenceNumber,
                                         Decision == ES08SeqDecision::Apply ? TEXT("apply")
                                                                            : TEXT("merge")));
                   SubscribeAfterSnapshot(Snapshot.SequenceNumber);
                 } else {
                   Trace(TEXT("STATE parse error: ") + Error.Message);
                   OnFlowError.Broadcast(Error);
                 }
               });
}

void FS08FlowController::PollRoom() {
  if (Room.GameId.IsEmpty()) return;
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("id"), Room.GameId);
  Http.Execute(GameQuery, Variables,
               [this](bool bOk, const TArray<FS08GraphQLError>& Errors,
                      TSharedPtr<FJsonObject> Data, const FString&) {
                 if (!bOk) {
                   Trace(TEXT("POLL failed: ") + (Errors.Num() ? Errors[0].Message : TEXT("?")));
                   return;
                 }
                 HandleRoomResponse(Data, TEXT("game"));
               });
}

bool FS08FlowController::CanIssueGameplayCommand(FString& OutReason) const {
  OutReason.Reset();
  if (IsInputBlocked()) {
    OutReason = TEXT("critical fields invalid: ") +
                FString::Join(CriticalProblems, TEXT("; "));
    return false;
  }
  if (Stage != ES08Stage::Started) {
    OutReason = TEXT("match is not started");
    return false;
  }
  if (!IsMyTurn()) {
    OutReason = TEXT("not your turn");
    return false;
  }
  if (bManeuverInFlight) {
    OutReason = TEXT("a command is already in flight");
    return false;
  }
  return true;
}

void FS08FlowController::ComputeCues(int32 Seq, const TSharedPtr<FJsonValue>& OldFighters,
                                     const TSharedPtr<FJsonValue>& NewFighters,
                                     TArray<FS08Cue>& OutCues) {
  OutCues.Reset();
  if (!OldFighters.IsValid() || !NewFighters.IsValid()) return;
  const TArray<TSharedPtr<FJsonValue>>* OldArray = nullptr;
  const TArray<TSharedPtr<FJsonValue>>* NewArray = nullptr;
  if (!OldFighters->TryGetArray(OldArray) || !NewFighters->TryGetArray(NewArray)) return;

  auto ReadPosition = [](const TSharedPtr<FJsonObject>& Fighter, int32& OutX, int32& OutY) {
    OutX = OutY = -1;
    const TSharedPtr<FJsonObject>* Position = nullptr;
    if (Fighter.IsValid() && Fighter->TryGetObjectField(TEXT("position"), Position) &&
        Position->IsValid()) {
      bool Present = false;
      FS08Contracts::ReadIntLike(Position->ToSharedRef(), TEXT("x"), OutX, Present);
      FS08Contracts::ReadIntLike(Position->ToSharedRef(), TEXT("y"), OutY, Present);
    }
  };
  for (const TSharedPtr<FJsonValue>& NewValue : *NewArray) {
    const TSharedPtr<FJsonObject>* NewFighter = nullptr;
    if (!NewValue.IsValid() || !NewValue->TryGetObject(NewFighter) || !NewFighter->IsValid()) {
      continue;
    }
    const FString Id = (*NewFighter)->GetStringField(TEXT("id"));
    const TSharedPtr<FJsonObject>* OldFighter = nullptr;
    for (const TSharedPtr<FJsonValue>& OldValue : *OldArray) {
      const TSharedPtr<FJsonObject>* Candidate = nullptr;
      if (OldValue.IsValid() && OldValue->TryGetObject(Candidate) && Candidate->IsValid() &&
          (*Candidate)->GetStringField(TEXT("id")) == Id) {
        OldFighter = Candidate;
        break;
      }
    }
    if (!OldFighter || !OldFighter->IsValid()) continue; // first sighting: no transition cue

    int32 OldX, OldY, NewX, NewY;
    ReadPosition(*OldFighter, OldX, OldY);
    ReadPosition(*NewFighter, NewX, NewY);
    if (OldX >= 0 && NewX >= 0 && (OldX != NewX || OldY != NewY)) {
      FS08Cue Cue;
      Cue.Type = ES08CueType::FighterMoved;
      Cue.SequenceNumber = Seq;
      Cue.FighterId = Id;
      Cue.FromX = OldX; Cue.FromY = OldY; Cue.ToX = NewX; Cue.ToY = NewY;
      OutCues.Add(MoveTemp(Cue));
    }
    bool Present = false;
    int32 OldHealth = 0, NewHealth = 0;
    FS08Contracts::ReadIntLike(OldFighter->ToSharedRef(), TEXT("health"), OldHealth, Present);
    FS08Contracts::ReadIntLike(NewFighter->ToSharedRef(), TEXT("health"), NewHealth, Present);
    if (NewHealth < OldHealth) {
      FS08Cue Cue;
      Cue.Type = ES08CueType::FighterDamaged;
      Cue.SequenceNumber = Seq;
      Cue.FighterId = Id;
      Cue.Damage = OldHealth - NewHealth;
      OutCues.Add(MoveTemp(Cue));
    }
  }
}

ES08SeqDecision FS08FlowController::ApplySnapshot(const FS08Snapshot& Snapshot) {
  const ES08SeqDecision Decision = SeqGuard.Decide(Snapshot.SequenceNumber);
  if (Decision == ES08SeqDecision::Ignore) {
    Trace(FString::Printf(TEXT("SEQ %d < local %d: ignored"), Snapshot.SequenceNumber,
                          SeqGuard.Local));
    return Decision;
  }
  // Cues are derived ONLY from an authoritative transition (seq > local):
  // a same-seq merge may enrich panel data but must never re-fire
  // presentation effects (ACC-011: duplicate HTTP+WS -> one visual event).
  TArray<FS08Cue> Cues;
  if (Decision == ES08SeqDecision::Apply) {
    ComputeCues(Snapshot.SequenceNumber, Applied.Fighters, Snapshot.Fighters, Cues);
  }
  // Merge semantics: absent fields keep their local copies (never null out).
  if (Snapshot.Players.IsValid()) Applied.Players = Snapshot.Players;
  if (Snapshot.Fighters.IsValid()) Applied.Fighters = Snapshot.Fighters;
  if (Snapshot.HandZones.IsValid()) Applied.HandZones = Snapshot.HandZones;
  if (Snapshot.DiscardPiles.IsValid()) Applied.DiscardPiles = Snapshot.DiscardPiles;
  if (Snapshot.BoardState.IsValid()) Applied.BoardState = Snapshot.BoardState;
  if (Snapshot.Metadata.IsValid()) Applied.Metadata = Snapshot.Metadata;
  Applied.SequenceNumber = Snapshot.SequenceNumber;
  Applied.Phase = Snapshot.Phase;
  Applied.TurnCount = Snapshot.TurnCount;
  Applied.CurrentTurnPlayerId = Snapshot.CurrentTurnPlayerId;
  SeqGuard.Commit(Snapshot.SequenceNumber);

  // GD-028 acceptance: critically incomplete state BLOCKS input with an
  // actionable message instead of guessing.
  CriticalProblems.Reset();
  FS08Contracts::ValidateCriticalFields(Applied, UserId, CriticalProblems);
  if (!CriticalProblems.IsEmpty()) {
    Trace(TEXT("CRITICAL FIELDS INVALID: ") + FString::Join(CriticalProblems, TEXT("; ")));
  } else {
    Trace(FString::Printf(TEXT("SNAPSHOT applied seq=%d phase=%s"), Applied.SequenceNumber,
                          *Applied.Phase));
  }
  OnApplied.Broadcast(Applied, Decision);
  if (Cues.Num() > 0) OnCues.Broadcast(Cues);
  return Decision;
}

void FS08FlowController::HandleRoomResponse(TSharedPtr<FJsonObject> Data, const FString& Field) {
  if (!Data.IsValid()) return;
  const TSharedPtr<FJsonObject>* Game = nullptr;
  if (Data->TryGetObjectField(Field, Game) && Game && Game->IsValid()) {
    ParseRoomFrom(*Game);
    if (Stage != ES08Stage::Room && Stage != ES08Stage::Started && Room.Status == TEXT("LOBBY")) {
      SetStage(ES08Stage::Room);
    }
    Trace(Field + TEXT(" -> room=") + Room.GameId + TEXT(" code=") + Room.Code +
          TEXT(" status=") + Room.Status);
    OnRoom.Broadcast(Room);
    // The guest learns about the start through polling (named events carry
    // no snapshot barrier); it attaches the same stream the host uses.
    if (Stage == ES08Stage::Room && Room.Status == TEXT("IN_PROGRESS")) {
      AttachGameStateStream();
    }
  }
}

void FS08FlowController::ParseRoomFrom(const TSharedPtr<FJsonObject>& Game) {
  FS08RoomState NewRoom;
  NewRoom.GameId = Game->GetStringField(TEXT("id"));
  // Nullable string fields: GetStringField returns an empty FString for null,
  // which reads as "unset" for the lobby view.
  NewRoom.Code = Game->GetStringField(TEXT("code"));
  NewRoom.Status = Game->GetStringField(TEXT("status"));
  NewRoom.Mode = Game->GetStringField(TEXT("mode"));
  NewRoom.HostId = Game->GetStringField(TEXT("hostId"));
  NewRoom.BoardId = Game->GetStringField(TEXT("boardId"));
  const TArray<TSharedPtr<FJsonValue>>* Players = nullptr;
  if (Game->TryGetArrayField(TEXT("players"), Players) && Players) {
    for (const TSharedPtr<FJsonValue>& Value : *Players) {
      const TSharedPtr<FJsonObject>* Player = nullptr;
      if (!Value.IsValid() || !Value->TryGetObject(Player) || !Player->IsValid()) continue;
      FS08RoomPlayer Entry;
      Entry.UserId = (*Player)->GetStringField(TEXT("userId"));
      Entry.Username = (*Player)->GetStringField(TEXT("username"));
      Entry.HeroId = (*Player)->GetStringField(TEXT("heroId"));
      bool bReady = false;
      (*Player)->TryGetBoolField(TEXT("isReady"), bReady);
      Entry.bIsReady = bReady;
      double Seat = 0.0;
      (*Player)->TryGetNumberField(TEXT("seatOrder"), Seat);
      Entry.SeatOrder = static_cast<int32>(Seat);
      NewRoom.Players.Add(MoveTemp(Entry));
    }
  }
  NewRoom.Players.Sort([](const FS08RoomPlayer& A, const FS08RoomPlayer& B) {
    return A.SeatOrder < B.SeatOrder;
  });
  Room = MoveTemp(NewRoom);
}

// ---- GD-031 gameplay commands -------------------------------------------
// beginManeuver/maneuver (INT-009: the deprecated moveFighter is never used).
// Both responses carry GameMutationResult with the full viewer-projected
// state; they are routed through ApplySnapshot like every other source, so
// HTTP echo, WS event and recovery query converge in ONE store.
static const TCHAR* BeginManeuverMutation =
    TEXT("mutation B($gameId: String!, $expectedSequenceNumber: Int!) {")
    TEXT(" beginManeuver(input: { gameId: $gameId,")
    TEXT("   expectedSequenceNumber: $expectedSequenceNumber }) {")
    TEXT(" state sequenceNumber phase turnCount currentTurnPlayerId } }");

static const TCHAR* ManeuverMutation =
    TEXT("mutation M($gameId: String!, $maneuverId: String!,")
    TEXT("        $moves: [ManeuverMoveInput!]!) {")
    TEXT(" maneuver(input: { gameId: $gameId, maneuverId: $maneuverId, moves: $moves }) {")
    TEXT(" state sequenceNumber phase turnCount currentTurnPlayerId } }");

void FS08FlowController::BeginManeuver() {
  FString Reason;
  if (!CanIssueGameplayCommand(Reason)) {
    Trace(TEXT("MANEUVER begin blocked: ") + Reason);
    return;
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Variables->SetNumberField(TEXT("expectedSequenceNumber"), SeqGuard.Local);
  bManeuverInFlight = true;
  Http.Execute(BeginManeuverMutation, Variables,
               [this](bool bOk, const TArray<FS08GraphQLError>& Errors,
                      TSharedPtr<FJsonObject>, const FString& RawBody) {
                 bManeuverInFlight = false;
                 if (!bOk) {
                   Trace(TEXT("MANEUVER begin failed: ") +
                         (Errors.Num() ? Errors[0].Message : TEXT("?")));
                   OnFlowError.Broadcast(Errors.Num() ? Errors[0]
                                                      : FS08GraphQLError{TEXT("TRANSPORT"),
                                                                         TEXT("beginManeuver failed"),
                                                                         FString()});
                   return;
                 }
                 FS08Snapshot Snapshot;
                 FS08GraphQLError Error;
                 if (!FS08Contracts::ParseMutationResult(RawBody, TEXT("beginManeuver"),
                                                         Snapshot, Error)) {
                   Trace(TEXT("MANEUVER begin parse error: ") + Error.Message);
                   OnFlowError.Broadcast(Error);
                   return;
                 }
                 const ES08SeqDecision Decision = ApplySnapshot(Snapshot);
                 const FString PendingId = FS08Contracts::PendingManeuverId(Applied);
                 Trace(FString::Printf(TEXT("MANEUVER begin seq=%d (%s) pending=%s"),
                                       Snapshot.SequenceNumber,
                                       Decision == ES08SeqDecision::Apply ? TEXT("apply")
                                                                          : TEXT("merge"),
                                       *PendingId));
               });
}

void FS08FlowController::SubmitManeuver(const FString& ManeuverId,
                                        const TArray<FS08ManeuverMove>& Moves) {
  if (ManeuverId.IsEmpty() || Moves.IsEmpty()) {
    Trace(TEXT("MANEUVER submit blocked: no pending maneuver or no moves"));
    return;
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Variables->SetStringField(TEXT("maneuverId"), ManeuverId);
  TArray<TSharedPtr<FJsonValue>> MoveValues;
  for (const FS08ManeuverMove& Move : Moves) {
    TSharedRef<FJsonObject> MoveObject = MakeShared<FJsonObject>();
    MoveObject->SetStringField(TEXT("fighterId"), Move.FighterId);
    TArray<TSharedPtr<FJsonValue>> PathValues;
    for (const FIntPoint& Step : Move.Path) {
      TSharedRef<FJsonObject> Position = MakeShared<FJsonObject>();
      Position->SetNumberField(TEXT("x"), Step.X);
      Position->SetNumberField(TEXT("y"), Step.Y);
      PathValues.Add(MakeShared<FJsonValueObject>(Position));
    }
    MoveObject->SetArrayField(TEXT("path"), PathValues);
    MoveValues.Add(MakeShared<FJsonValueObject>(MoveObject));
  }
  Variables->SetArrayField(TEXT("moves"), MoveValues);
  bManeuverInFlight = true;
  Http.Execute(ManeuverMutation, Variables,
               [this](bool bOk, const TArray<FS08GraphQLError>& Errors,
                      TSharedPtr<FJsonObject>, const FString& RawBody) {
                 bManeuverInFlight = false;
                 if (!bOk) {
                   Trace(TEXT("MANEUVER failed: ") +
                         (Errors.Num() ? Errors[0].Message : TEXT("?")));
                   OnFlowError.Broadcast(Errors.Num() ? Errors[0]
                                                      : FS08GraphQLError{TEXT("TRANSPORT"),
                                                                         TEXT("maneuver failed"),
                                                                         FString()});
                   return;
                 }
                 FS08Snapshot Snapshot;
                 FS08GraphQLError Error;
                 if (!FS08Contracts::ParseMutationResult(RawBody, TEXT("maneuver"),
                                                         Snapshot, Error)) {
                   Trace(TEXT("MANEUVER parse error: ") + Error.Message);
                   OnFlowError.Broadcast(Error);
                   return;
                 }
                 const ES08SeqDecision Decision = ApplySnapshot(Snapshot);
                 Trace(FString::Printf(TEXT("MANEUVER done seq=%d (%s) fighters=%d"),
                                       Snapshot.SequenceNumber,
                                       Decision == ES08SeqDecision::Apply ? TEXT("apply")
                                                                          : TEXT("merge"),
                                       FS08Contracts::EntryCount(Applied.Fighters)));
                 // The move was accepted; the same seq will also arrive over
                 // the WS stream and collapse in the seq guard (merge).
               });
}

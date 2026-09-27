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

bool FS08FlowController::CanEnterRoomFlow(const TCHAR* Action) {
  if (Stage != ES08Stage::Started) return true;
  Trace(FString(Action) +
        TEXT(" blocked: match is live - leave the room first (F10 recovery/create/join stays a no-op during Started)"));
  return false;
}

bool FS08FlowController::CanApplyRoomEntryAnswer(const TCHAR* Action) {
  if (Stage != ES08Stage::Started) return true;
  Trace(FString(Action) +
        TEXT(" late answer ignored: the room went live while the request was in flight"));
  return false;
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
  if (!CanEnterRoomFlow(TEXT("MYGAMES"))) return;
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("status"), TEXT("LOBBY"));
  const int32 Gen = MatchGeneration;
  FS08GraphqlClient::FResult OnDone =
      [this, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors,
                  TSharedPtr<FJsonObject> Data, const FString&) {
        // Stale answer: a room was left/joined before myGames resolved - a
        // late recovery must not resurrect the old room (or force a stage
        // change on the newer one).
        if (MatchGeneration != Gen) {
          Trace(TEXT("MYGAMES stale answer ignored"));
          return;
        }
        // Room->Started keeps the generation: the room went live while this
        // myGames was in flight - the answer must not rewrite Room, demote
        // the stage or surface an error over the live match.
        if (!CanApplyRoomEntryAnswer(TEXT("MYGAMES"))) return;
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
      };
#if WITH_AUTOMATION_TESTS
  if (DispatchQueuedHttpForTest(MoveTemp(OnDone))) return;
#endif
  Http.Execute(MyGamesQuery, Variables, MoveTemp(OnDone));
}

void FS08FlowController::CreateRoom(const FString& Mode) {
  if (!CanEnterRoomFlow(TEXT("CREATE"))) return;
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  TSharedRef<FJsonObject> Input = MakeShared<FJsonObject>();
  Input->SetStringField(TEXT("mode"), Mode.IsEmpty() ? TEXT("ONE_V_ONE") : Mode);
  Variables->SetObjectField(TEXT("input"), Input);
  Variables->SetStringField(TEXT("idempotencyKey"), IdempotencyKey);
  const int32 Gen = MatchGeneration;
  FS08GraphqlClient::FResult OnDone =
      [this, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors,
                  TSharedPtr<FJsonObject> Data, const FString&) {
        // Stale answer: the player already left/joined elsewhere before the
        // create resolved - the created room must not clobber the newer one.
        if (MatchGeneration != Gen) {
          Trace(TEXT("CREATE stale answer ignored"));
          return;
        }
        if (!CanApplyRoomEntryAnswer(TEXT("CREATE"))) return;
        if (!bOk) {
          Trace(TEXT("CREATE failed: ") + (Errors.Num() ? Errors[0].Message : TEXT("?")));
          OnFlowError.Broadcast(Errors.Num() ? Errors[0]
                                             : FS08GraphQLError{TEXT("TRANSPORT"), TEXT("create failed"), FString()});
          return;
        }
        HandleRoomResponse(Data, TEXT("createGame"));
      };
#if WITH_AUTOMATION_TESTS
  if (DispatchQueuedHttpForTest(MoveTemp(OnDone))) return;
#endif
  Http.Execute(CreateGameMutation, Variables, MoveTemp(OnDone));
}

void FS08FlowController::JoinRoomByCode(const FString& Code) {
  if (!CanEnterRoomFlow(TEXT("JOIN"))) return;
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("code"), Code);
  const int32 Gen = MatchGeneration;
  FS08GraphqlClient::FResult OnLookupDone =
      [this, Code, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors,
                        TSharedPtr<FJsonObject> Data, const FString&) {
                 // Stale answer: the join intent predates the current room
                 // state - a late lookup must not fire a joinGame against the
                 // resolved old id.
                 if (MatchGeneration != Gen) {
                   Trace(TEXT("JOIN stale answer ignored"));
                   return;
                 }
                 // The room went live mid-lookup: the resolved id must not
                 // fire a joinGame (or a NOT_FOUND error) over the match.
                 if (!CanApplyRoomEntryAnswer(TEXT("JOIN lookup"))) return;
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
                     FS08GraphqlClient::FResult OnJoinDone =
                         [this, Gen](bool bOk2, const TArray<FS08GraphQLError>& Errors2,
                                     TSharedPtr<FJsonObject> Data2, const FString&) {
                           // Same stale gate as the lookup leg: the joinGame
                           // answer must not install its room over a newer
                           // room state.
                           if (MatchGeneration != Gen) {
                             Trace(TEXT("JOIN stale answer ignored"));
                             return;
                           }
                           // Same room->Started race as the lookup leg: the
                           // joinGame echo must not install its room (or a
                           // failure) over the live match.
                           if (!CanApplyRoomEntryAnswer(TEXT("JOIN"))) return;
                           if (!bOk2) {
                             Trace(TEXT("JOIN failed: ") +
                                   (Errors2.Num() ? Errors2[0].Message : TEXT("?")));
                             OnFlowError.Broadcast(Errors2.Num()
                                                       ? Errors2[0]
                                                       : FS08GraphQLError{TEXT("TRANSPORT"), TEXT("join failed"), FString()});
                             return;
                           }
                           HandleRoomResponse(Data2, TEXT("joinGame"));
                         };
#if WITH_AUTOMATION_TESTS
                     if (DispatchQueuedHttpForTest(MoveTemp(OnJoinDone))) return;
#endif
                     Http.Execute(JoinGameMutation, JoinVars, MoveTemp(OnJoinDone));
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
      };
#if WITH_AUTOMATION_TESTS
  if (DispatchQueuedHttpForTest(MoveTemp(OnLookupDone))) return;
#endif
  Http.Execute(GameByCodeQuery, Variables, MoveTemp(OnLookupDone));
}

void FS08FlowController::SelectHero(const FString& HeroId) {
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Variables->SetStringField(TEXT("heroId"), HeroId);
  const FString GameId = Room.GameId;
  const int32 Gen = MatchGeneration;
  FS08GraphqlClient::FResult OnDone =
      [this, GameId, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors,
                          TSharedPtr<FJsonObject> Data, const FString&) {
        if (!IsSameMatchRequest(GameId, Gen)) {
          Trace(FString::Printf(TEXT("SELECT stale answer room=%s ignored"), *GameId));
          return;
        }
        if (!bOk) {
          Trace(TEXT("SELECT failed: ") + (Errors.Num() ? Errors[0].Message : TEXT("?")));
          OnFlowError.Broadcast(Errors.Num() ? Errors[0]
                                             : FS08GraphQLError{TEXT("TRANSPORT"), TEXT("select failed"), FString()});
          return;
        }
        HandleRoomResponse(Data, TEXT("selectHero"));
      };
#if WITH_AUTOMATION_TESTS
  if (DispatchQueuedHttpForTest(MoveTemp(OnDone))) return;
#endif
  Http.Execute(SelectHeroMutation, Variables, MoveTemp(OnDone));
}

void FS08FlowController::ToggleReady() {
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  const FString GameId = Room.GameId;
  const int32 Gen = MatchGeneration;
  FS08GraphqlClient::FResult OnDone =
      [this, GameId, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors,
                          TSharedPtr<FJsonObject> Data, const FString&) {
        if (!IsSameMatchRequest(GameId, Gen)) {
          Trace(FString::Printf(TEXT("READY stale answer room=%s ignored"), *GameId));
          return;
        }
        if (!bOk) {
          Trace(TEXT("READY failed: ") + (Errors.Num() ? Errors[0].Message : TEXT("?")));
          OnFlowError.Broadcast(Errors.Num() ? Errors[0]
                                             : FS08GraphQLError{TEXT("TRANSPORT"), TEXT("ready failed"), FString()});
          return;
        }
        HandleRoomResponse(Data, TEXT("toggleReady"));
      };
#if WITH_AUTOMATION_TESTS
  if (DispatchQueuedHttpForTest(MoveTemp(OnDone))) return;
#endif
  Http.Execute(ToggleReadyMutation, Variables, MoveTemp(OnDone));
}

void FS08FlowController::StartGame() {
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  const FString GameId = Room.GameId;
  const int32 Gen = MatchGeneration;
  FS08GraphqlClient::FResult OnDone =
      [this, GameId, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors,
                          TSharedPtr<FJsonObject> Data, const FString&) {
        // P1 gate: a delayed successful startGame answer for a room that was
        // left/replaced must not repopulate that room or attach its stream.
        if (!IsSameMatchRequest(GameId, Gen)) {
          Trace(FString::Printf(TEXT("START stale answer room=%s ignored"), *GameId));
          return;
        }
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
      };
#if WITH_AUTOMATION_TESTS
  if (DispatchQueuedHttpForTest(MoveTemp(OnDone))) return;
#endif
  Http.Execute(StartGameMutation, Variables, MoveTemp(OnDone));
}

void FS08FlowController::LeaveRoom() {
  if (Room.GameId.IsEmpty()) return;
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  const FString GameId = Room.GameId;
  const int32 Gen = MatchGeneration;
  FS08GraphqlClient::FResult OnLeaveDone =
      [this, GameId, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors,
                          TSharedPtr<FJsonObject>, const FString&) {
        // Stale answer: the user joined another room (or a re-join of this
        // same id bumped the generation) before this leave was answered -
        // the result must not clobber the newer room state.
        if (!IsSameMatchRequest(GameId, Gen)) {
          Trace(FString::Printf(TEXT("LEAVE stale answer room=%s ignored"), *GameId));
          return;
        }
        if (!bOk) {
          // Rejected leave: membership is still live server-side, so the room
          // and the stage survive and the rejection surfaces as an
          // actionable error. Clearing them here would strand the player in
          // the lobby with a ghost membership.
          Trace(TEXT("LEAVE failed: ") + (Errors.Num() ? Errors[0].Message : TEXT("?")));
          const FS08GraphQLError Failure = Errors.Num()
                                               ? Errors[0]
                                               : FS08GraphQLError{TEXT("TRANSPORT"),
                                                                  TEXT("leaveGame failed"),
                                                                  FString()};
          OnFlowError.Broadcast(Failure);
          OnLeaveFailed.Broadcast(Failure);
          return;
        }
        Trace(TEXT("LEFT room=") + GameId);
        Room = FS08RoomState();
        // Stage first: the teardown below can observe WS close side effects,
        // and a reconnect must only ever arm while the match is live.
        SetStage(ES08Stage::Lobby);
        TeardownGameStateStream();
      };
#if WITH_AUTOMATION_TESTS
  if (DispatchQueuedHttpForTest(MoveTemp(OnLeaveDone))) return;
#endif
  Http.Execute(LeaveGameMutation, Variables, MoveTemp(OnLeaveDone));
}

void FS08FlowController::MakeWs() {
  Ws = MakeUnique<FS08GraphqlWs>(WsUrl, Http.GetAccessToken());
  BindWsHandlers();
  Ws->Connect();
}

void FS08FlowController::TeardownGameStateStream() {
  // The accepted leave ends the match: every callback still in flight for it
  // must fail its request-identity check from here on.
  ++MatchGeneration;
  if (Ws.IsValid()) {
    // Best-effort server-side stop for the live operation; the object (and
    // its delegates) then dies synchronously - no close can arm a reconnect
    // or deliver a late frame for the old game.
    if (!GameStateOpId.IsEmpty()) Ws->Unsubscribe(GameStateOpId);
    Ws.Reset();
  }
  GameStateOpId.Reset();
  WsReconnectCountdown = -1.0f; // disarm a retry the old game armed
  WsReconnectBackoff = 1.0f;
  bWsReconnectAckPending = false;
  OpRecoveryAttempts = 0;
  bManeuverInFlight = false;
  Applied = FS08Snapshot();
  SeqGuard = FS08SeqGuard();
  DecksSeq = 0;
  DiscardPilesSeq = 0;
  CriticalProblems.Reset();
  Trace(TEXT("STREAM torn down (left match)"));
}

ES08SeqDecision FS08FlowController::ApplyMatchSnapshot(const FS08Snapshot& Snapshot) {
  if (Stage != ES08Stage::Started) {
    Trace(FString::Printf(TEXT("SEQ %d dropped: match no longer live (stage != Started)"),
                          Snapshot.SequenceNumber));
    return ES08SeqDecision::Ignore;
  }
  return ApplySnapshot(Snapshot);
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
/** Queued harness body -> the "data" object a real response would carry
 *  (room responses read Data; mutation echoes read the raw body). */
static TSharedPtr<FJsonObject> HarnessDataFromForTest(const FString& RawBody) {
  if (RawBody.IsEmpty()) return nullptr;
  TSharedPtr<FJsonObject> Parsed;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(RawBody, Parsed, Problem) || !Parsed.IsValid()) {
    return nullptr;
  }
  const TSharedPtr<FJsonObject>* Data = nullptr;
  if (Parsed->TryGetObjectField(TEXT("data"), Data) && Data) return *Data;
  return nullptr;
}

void FS08FlowController::AttachStreamHarnessForTest(const FString& GameId) {
  if (Room.GameId != GameId) ++MatchGeneration;
  Room.GameId = GameId;
  if (!Ws.IsValid()) {
    Ws = MakeUnique<FS08GraphqlWs>(WsUrl, FString());
    BindWsHandlers();
  }
  Ws->ForceAckedForTest();
  SetStage(ES08Stage::Started);
  SubscribeAfterSnapshot(0);
}

void FS08FlowController::QueueHttpResultForTest(bool bOk,
                                                TArray<FS08GraphQLError> InErrors,
                                                bool bDeferDelivery,
                                                const FString& InRawBody) {
  bHttpResultQueued = true;
  QueuedHttp = FQueuedHttpResult{bOk, bDeferDelivery, MoveTemp(InErrors), InRawBody};
}

void FS08FlowController::DeliverQueuedHttpForTest() {
  if (DeferredHttpQueue.Num() == 0) return;
  FDeferredHttp Entry = MoveTemp(DeferredHttpQueue[0]);
  DeferredHttpQueue.RemoveAt(0);
  InvokeQueuedHttpForTest(Entry.Result, MoveTemp(Entry.OnDone));
}

void FS08FlowController::InvokeQueuedHttpForTest(const FQueuedHttpResult& Result,
                                                 FS08GraphqlClient::FResult&& OnDone) {
  OnDone(Result.bOk, Result.Errors, HarnessDataFromForTest(Result.RawBody), Result.RawBody);
}

void FS08FlowController::SetRoomForTest(const FString& GameId, ES08Stage InStage) {
  const bool bRoomChanged = Room.GameId != GameId;
  Room = FS08RoomState();
  Room.GameId = GameId;
  if (bRoomChanged) ++MatchGeneration; // mirror the live room-change bump
  Stage = InStage; // direct seed: no stage broadcast, tests read GetStage()
}

bool FS08FlowController::DispatchQueuedHttpForTest(FS08GraphqlClient::FResult&& OnDone) {
  if (!bHttpResultQueued) return false;
  bHttpResultQueued = false;
  if (QueuedHttp.bDeferred) {
    FDeferredHttp Entry;
    Entry.Result = MoveTemp(QueuedHttp);
    Entry.OnDone = MoveTemp(OnDone);
    DeferredHttpQueue.Add(MoveTemp(Entry));
    return true; // answer held back until DeliverQueuedHttpForTest()
  }
  InvokeQueuedHttpForTest(QueuedHttp, MoveTemp(OnDone));
  return true;
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
  const FString SubGameId = Room.GameId;
  const int32 SubGen = MatchGeneration;
  GameStateOpId = Ws->SubscribeGameStateUpdated(
      Room.GameId, Since,
      [this, SubGameId, SubGen](const FS08Snapshot& Snapshot) {
        // A frame from a subscription registered for a previous match
        // incarnation (same socket reused across a room change without a
        // teardown) must not reach the current seq guard.
        if (!IsSameMatchRequest(SubGameId, SubGen)) {
          Trace(FString::Printf(TEXT("WS stale frame room=%s ignored"), *SubGameId));
          return;
        }
        // A delivered snapshot proves the recovered operation works - the
        // bounded operation-level recovery counter starts over.
        OpRecoveryAttempts = 0;
        const ES08SeqDecision Decision = ApplyMatchSnapshot(Snapshot);
        if (Decision == ES08SeqDecision::Ignore) return;
        Trace(FString::Printf(TEXT("WS seq=%d phase=%s (%s)"), Snapshot.SequenceNumber,
                              *Snapshot.Phase,
                              Decision == ES08SeqDecision::Apply ? TEXT("apply") : TEXT("merge")));
      },
      [this, SubGameId, SubGen](const FS08GraphQLError& Error) {
        if (!IsSameMatchRequest(SubGameId, SubGen)) return;
        Trace(TEXT("WS error: ") + Error.Message);
        OnFlowError.Broadcast(Error);
      });
  Trace(FString::Printf(TEXT("SUBSCRIBED gameStateUpdated since=%d"), Since));
}

void FS08FlowController::FetchGameState() {
  if (Room.GameId.IsEmpty()) return;
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  const FString GameId = Room.GameId;
  const int32 Gen = MatchGeneration;
  FS08GraphqlClient::FResult OnDone =
      [this, GameId, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors,
                          TSharedPtr<FJsonObject> Data, const FString& RawBody) {
        // Stale answer: the match was left (or another room joined, or the
        // same id re-joined) before the fetch resolved - it must not
        // resurrect state.
        if (!IsSameMatchRequest(GameId, Gen)) {
          Trace(FString::Printf(TEXT("STATE stale answer room=%s ignored"), *GameId));
          return;
        }
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
          const ES08SeqDecision Decision = ApplyMatchSnapshot(Snapshot);
          Trace(FString::Printf(TEXT("STATE seq=%d -> %s"), Snapshot.SequenceNumber,
                                Decision == ES08SeqDecision::Apply ? TEXT("apply")
                                                                   : TEXT("merge")));
          SubscribeAfterSnapshot(Snapshot.SequenceNumber);
        } else {
          Trace(TEXT("STATE parse error: ") + Error.Message);
          OnFlowError.Broadcast(Error);
        }
      };
#if WITH_AUTOMATION_TESTS
  if (DispatchQueuedHttpForTest(MoveTemp(OnDone))) return;
#endif
  Http.Execute(GameStateQuery, Variables, MoveTemp(OnDone));
}

void FS08FlowController::PollRoom() {
  if (Room.GameId.IsEmpty()) return;
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("id"), Room.GameId);
  const FString GameId = Room.GameId;
  const int32 Gen = MatchGeneration;
  FS08GraphqlClient::FResult OnDone =
      [this, GameId, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors,
                          TSharedPtr<FJsonObject> Data, const FString&) {
        // Stale answer: the room was left (or replaced, or this same id was
        // re-joined after a leave) before the poll resolved - it must not
        // resurrect the old room view.
        if (!IsSameMatchRequest(GameId, Gen)) {
          Trace(FString::Printf(TEXT("POLL stale answer room=%s ignored"), *GameId));
          return;
        }
        if (!bOk) {
          Trace(TEXT("POLL failed: ") + (Errors.Num() ? Errors[0].Message : TEXT("?")));
          return;
        }
        HandleRoomResponse(Data, TEXT("game"));
      };
#if WITH_AUTOMATION_TESTS
  if (DispatchQueuedHttpForTest(MoveTemp(OnDone))) return;
#endif
  Http.Execute(GameQuery, Variables, MoveTemp(OnDone));
}

bool FS08FlowController::CanIssueGameplayCommand(FString& OutReason) const {
  OutReason.Reset();
  if (Applied.Phase == TEXT("GAME_OVER")) {
    OutReason = TEXT("the duel is over - gameplay input is disabled on the result screen");
    return false;
  }
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
  if (Snapshot.DiscardPiles.IsValid()) {
    Applied.DiscardPiles = Snapshot.DiscardPiles;
    DiscardPilesSeq = Snapshot.SequenceNumber;
  }
  if (Snapshot.Decks.IsValid()) {
    Applied.Decks = Snapshot.Decks;
    DecksSeq = Snapshot.SequenceNumber;
  }
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
  // A different room id (new room, or a re-join of this id after a leave)
  // starts a new match generation: callbacks still in flight for the
  // previous incarnation must not act on the new one.
  if (NewRoom.GameId != Room.GameId) ++MatchGeneration;
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
    TEXT("        $moves: [ManeuverMoveInput!]!, $boostCardId: String) {")
    TEXT(" maneuver(input: { gameId: $gameId, maneuverId: $maneuverId, moves: $moves,")
    TEXT("                  boostCardId: $boostCardId }) {")
    TEXT(" state sequenceNumber phase turnCount currentTurnPlayerId } }");

static const TCHAR* EndTurnMutation =
    TEXT("mutation E($gameId: String!) { endTurn(input: { gameId: $gameId }) {")
    TEXT(" state sequenceNumber phase turnCount currentTurnPlayerId } }");

static const TCHAR* DiscardToLimitMutation =
    TEXT("mutation D($gameId: String!, $pendingId: String!, $cardIds: [String!]!) {")
    TEXT(" discardToLimit(input: { gameId: $gameId, pendingId: $pendingId,")
    TEXT("                       cardIds: $cardIds }) {")
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
  const FString GameId = Room.GameId;
  const int32 Gen = MatchGeneration;
  bManeuverInFlight = true;
  FS08GraphqlClient::FResult OnDone =
      [this, GameId, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors,
                          TSharedPtr<FJsonObject>, const FString& RawBody) {
        // Stale answer for a left/replaced match: drop BEFORE the in-flight
        // clear - the flag now belongs to the CURRENT match's command.
        if (!IsSameMatchRequest(GameId, Gen)) {
          Trace(FString::Printf(TEXT("MANEUVER begin stale answer room=%s ignored"),
                                *GameId));
          return;
        }
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
        const ES08SeqDecision Decision = ApplyMatchSnapshot(Snapshot);
        const FString PendingId = FS08Contracts::PendingManeuverId(Applied);
        Trace(FString::Printf(TEXT("MANEUVER begin seq=%d (%s) pending=%s"),
                              Snapshot.SequenceNumber,
                              Decision == ES08SeqDecision::Apply ? TEXT("apply")
                                                                 : TEXT("merge"),
                              *PendingId));
      };
#if WITH_AUTOMATION_TESTS
  if (DispatchQueuedHttpForTest(MoveTemp(OnDone))) return;
#endif
  Http.Execute(BeginManeuverMutation, Variables, MoveTemp(OnDone));
}

void FS08FlowController::SubmitManeuver(const FString& ManeuverId,
                                        const TArray<FS08ManeuverMove>& Moves,
                                        const FString& BoostCardId) {
  // Maneuver completion happens on the mover's own turn; the gate's
  // bManeuverInFlight check also blocks a double-Enter from firing two
  // maneuver() legs against the same pending id (the second would fail).
  FString Reason;
  if (!CanIssueGameplayCommand(Reason)) {
    Trace(TEXT("MANEUVER submit blocked: ") + Reason);
    return;
  }
  // ACC-006: zero moves is a legal maneuver completion (draw + no movement).
  if (ManeuverId.IsEmpty()) {
    Trace(TEXT("MANEUVER submit blocked: no pending maneuver"));
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
  if (BoostCardId.IsEmpty()) {
    Variables->SetField(TEXT("boostCardId"), MakeShared<FJsonValueNull>());
  } else {
    Variables->SetStringField(TEXT("boostCardId"), BoostCardId);
  }
  const FString GameId = Room.GameId;
  const int32 Gen = MatchGeneration;
  bManeuverInFlight = true;
  FS08GraphqlClient::FResult OnDone =
      [this, GameId, Gen, BoostCardId](bool bOk, const TArray<FS08GraphQLError>& Errors,
                                       TSharedPtr<FJsonObject>, const FString& RawBody) {
        if (!IsSameMatchRequest(GameId, Gen)) {
          Trace(FString::Printf(TEXT("MANEUVER stale answer room=%s ignored"), *GameId));
          return;
        }
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
        const ES08SeqDecision Decision = ApplyMatchSnapshot(Snapshot);
        Trace(FString::Printf(TEXT("MANEUVER done seq=%d (%s) fighters=%d boost=%s"),
                              Snapshot.SequenceNumber,
                              Decision == ES08SeqDecision::Apply ? TEXT("apply")
                                                                 : TEXT("merge"),
                              FS08Contracts::EntryCount(Applied.Fighters),
                              BoostCardId.IsEmpty() ? TEXT("no") : TEXT("card")));
        // The move was accepted; the same seq will also arrive over
        // the WS stream and collapse in the seq guard (merge).
      };
#if WITH_AUTOMATION_TESTS
  if (DispatchQueuedHttpForTest(MoveTemp(OnDone))) return;
#endif
  Http.Execute(ManeuverMutation, Variables, MoveTemp(OnDone));
}

bool FS08FlowController::CanIssueEndTurn(FString& OutReason) const {
  if (!CanIssueGameplayCommand(OutReason)) return false;
  if (!IsEndTurnPhase(Applied.Phase)) {
    OutReason = TEXT("phase ") + Applied.Phase +
                TEXT(" is not an end-turn action phase (ACTION_MANEUVER/ACTION_ATTACK)");
    return false;
  }
  return true;
}

void FS08FlowController::EndTurn() {
  FString Reason;
  if (!CanIssueEndTurn(Reason)) {
    Trace(TEXT("ENDTURN blocked: ") + Reason);
    return;
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  const FString GameId = Room.GameId;
  const int32 Gen = MatchGeneration;
  bManeuverInFlight = true;
  FS08GraphqlClient::FResult OnDone =
      [this, GameId, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors,
                          TSharedPtr<FJsonObject>, const FString& RawBody) {
        if (!IsSameMatchRequest(GameId, Gen)) {
          Trace(FString::Printf(TEXT("ENDTURN stale answer room=%s ignored"), *GameId));
          return;
        }
        bManeuverInFlight = false;
        if (!bOk) {
          Trace(TEXT("ENDTURN failed: ") +
                (Errors.Num() ? Errors[0].Message : TEXT("?")));
          OnFlowError.Broadcast(Errors.Num() ? Errors[0]
                                             : FS08GraphQLError{TEXT("TRANSPORT"),
                                                                TEXT("endTurn failed"),
                                                                FString()});
          return;
        }
        FS08Snapshot Snapshot;
        FS08GraphQLError Error;
        if (!FS08Contracts::ParseMutationResult(RawBody, TEXT("endTurn"),
                                                Snapshot, Error)) {
          Trace(TEXT("ENDTURN parse error: ") + Error.Message);
          OnFlowError.Broadcast(Error);
          return;
        }
        ApplyMatchSnapshot(Snapshot);
        Trace(FString::Printf(TEXT("ENDTURN done seq=%d phase=%s"),
                              Snapshot.SequenceNumber, *Snapshot.Phase));
      };
#if WITH_AUTOMATION_TESTS
  if (DispatchQueuedHttpForTest(MoveTemp(OnDone))) return;
#endif
  Http.Execute(EndTurnMutation, Variables, MoveTemp(OnDone));
}

void FS08FlowController::DiscardToLimit(const FString& PendingId,
                                        const TArray<FString>& CardInstanceIds) {
  // No-turn-owner gate (like the combat commands): the TURN_END discard can
  // open after the turn already flipped to the opponent, so IsMyTurn() must
  // NOT gate it - but started/valid-critical-fields/in-flight still apply.
  // The in-flight check blocks a double-Enter: two discardToLimit legs with
  // the SAME pending id would race and the second fails spuriously.
  FString Reason;
  if (!CanIssueCombatCommand(Reason)) {
    Trace(TEXT("DISCARD blocked: ") + Reason);
    return;
  }
  if (PendingId.IsEmpty() || CardInstanceIds.IsEmpty()) {
    Trace(TEXT("DISCARD blocked: no pending choice or no cards"));
    return;
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Variables->SetStringField(TEXT("pendingId"), PendingId);
  TArray<TSharedPtr<FJsonValue>> Ids;
  for (const FString& Id : CardInstanceIds) {
    Ids.Add(MakeShared<FJsonValueString>(Id));
  }
  Variables->SetArrayField(TEXT("cardIds"), Ids);
  const FString GameId = Room.GameId;
  const int32 Gen = MatchGeneration;
  bManeuverInFlight = true;
  const int32 Count = CardInstanceIds.Num();
  FS08GraphqlClient::FResult OnDone =
      [this, GameId, Gen, Count](bool bOk, const TArray<FS08GraphQLError>& Errors,
                                 TSharedPtr<FJsonObject>, const FString& RawBody) {
        if (!IsSameMatchRequest(GameId, Gen)) {
          Trace(FString::Printf(TEXT("DISCARD stale answer room=%s ignored"), *GameId));
          return;
        }
        bManeuverInFlight = false;
        if (!bOk) {
          Trace(TEXT("DISCARD failed: ") +
                (Errors.Num() ? Errors[0].Message : TEXT("?")));
          OnFlowError.Broadcast(Errors.Num() ? Errors[0]
                                             : FS08GraphQLError{TEXT("TRANSPORT"),
                                                                TEXT("discardToLimit failed"),
                                                                FString()});
          return;
        }
        FS08Snapshot Snapshot;
        FS08GraphQLError Error;
        if (!FS08Contracts::ParseMutationResult(RawBody, TEXT("discardToLimit"),
                                                Snapshot, Error)) {
          Trace(TEXT("DISCARD parse error: ") + Error.Message);
          OnFlowError.Broadcast(Error);
          return;
        }
        ApplyMatchSnapshot(Snapshot);
        Trace(FString::Printf(TEXT("DISCARD done seq=%d phase=%s count=%d"),
                              Snapshot.SequenceNumber, *Snapshot.Phase, Count));
      };
#if WITH_AUTOMATION_TESTS
  if (DispatchQueuedHttpForTest(MoveTemp(OnDone))) return;
#endif
  Http.Execute(DiscardToLimitMutation, Variables, MoveTemp(OnDone));
}

// ---- GD-034 combat commands -------------------------------------------------
// All six mutations return GameMutationResult; echoes route through the SAME
// store (ApplySnapshot), so HTTP echo + WS event of one seq collapse in the
// seq guard (no double animation/state on a single seq).

static const TCHAR* AttackMutation =
    TEXT("mutation A($gameId: String!, $attackerId: String!, $cardId: String!,")
    TEXT("        $targetId: String!) {")
    TEXT(" attack(input: { gameId: $gameId, attackerId: $attackerId, cardId: $cardId,")
    TEXT("              targetId: $targetId }) {")
    TEXT(" state sequenceNumber phase turnCount currentTurnPlayerId } }");

static const TCHAR* PlayDefenseMutation =
    TEXT("mutation P($gameId: String!, $cardId: String!) {")
    TEXT(" playDefense(input: { gameId: $gameId, cardId: $cardId }) {")
    TEXT(" state sequenceNumber phase turnCount currentTurnPlayerId } }");

static const TCHAR* PlaySchemeMutation =
    TEXT("mutation S($gameId: String!, $cardId: String!) {")
    TEXT(" playScheme(input: { gameId: $gameId, cardId: $cardId }) {")
    TEXT(" state sequenceNumber phase turnCount currentTurnPlayerId } }");

static const TCHAR* ResolveCombatMutation =
    TEXT("mutation R($gameId: String!) {")
    TEXT(" resolveCombat(input: { gameId: $gameId }) {")
    TEXT(" state sequenceNumber phase turnCount currentTurnPlayerId } }");

static const TCHAR* ResolvePendingEffectMutation =
    TEXT("mutation RP($gameId: String!, $effectId: String!, $fighterId: String,")
    TEXT("             $x: Int, $y: Int, $optionIndex: Int, $cardIds: [String!]) {")
    TEXT(" resolvePendingEffect(input: { gameId: $gameId, effectId: $effectId,")
    TEXT("                        fighterId: $fighterId, x: $x, y: $y,")
    TEXT("                        optionIndex: $optionIndex, cardIds: $cardIds }) {")
    TEXT(" state sequenceNumber phase turnCount currentTurnPlayerId } }");

static const TCHAR* DeclinePendingEffectMutation =
    TEXT("mutation DP($gameId: String!, $effectId: String!) {")
    TEXT(" declinePendingEffect(input: { gameId: $gameId, effectId: $effectId }) {")
    TEXT(" state sequenceNumber phase turnCount currentTurnPlayerId } }");

void FS08FlowController::RunCombatMutation(const FString& Tag, const TCHAR* Field,
                                           const FString& Mutation,
                                           const TSharedRef<FJsonObject>& Variables) {
  const FString GameId = Room.GameId;
  const int32 Gen = MatchGeneration;
  bManeuverInFlight = true;
  FS08GraphqlClient::FResult OnDone =
      [this, Tag, Field, GameId, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors,
                                      TSharedPtr<FJsonObject>, const FString& RawBody) {
        if (!IsSameMatchRequest(GameId, Gen)) {
          Trace(FString::Printf(TEXT("%s stale answer room=%s ignored"), *Tag, *GameId));
          return;
        }
        bManeuverInFlight = false;
        if (!bOk) {
          Trace(Tag + TEXT(" failed: ") +
                (Errors.Num() ? Errors[0].Message : TEXT("?")));
          OnFlowError.Broadcast(Errors.Num() ? Errors[0]
                                             : FS08GraphQLError{TEXT("TRANSPORT"),
                                                                Tag + TEXT(" failed"),
                                                                FString()});
          return;
        }
        FS08Snapshot Snapshot;
        FS08GraphQLError Error;
        if (!FS08Contracts::ParseMutationResult(RawBody, Field, Snapshot, Error)) {
          Trace(Tag + TEXT(" parse error: ") + Error.Message);
          OnFlowError.Broadcast(Error);
          return;
        }
        const ES08SeqDecision Decision = ApplyMatchSnapshot(Snapshot);
        // Privacy-safe trace: seq/decision/phase only - never card
        // ids, never opponent values (published evidence stays
        // reveal-free).
        Trace(FString::Printf(TEXT("%s done seq=%d (%s) phase=%s"), *Tag,
                              Snapshot.SequenceNumber,
                              Decision == ES08SeqDecision::Apply ? TEXT("apply")
                                                                 : TEXT("merge"),
                              *Snapshot.Phase));
      };
#if WITH_AUTOMATION_TESTS
  if (DispatchQueuedHttpForTest(MoveTemp(OnDone))) return;
#endif
  Http.Execute(Mutation, Variables, MoveTemp(OnDone));
}

bool FS08FlowController::CanIssueCombatCommand(FString& OutReason) const {
  OutReason.Reset();
  if (Applied.Phase == TEXT("GAME_OVER")) {
    OutReason = TEXT("the duel is over - gameplay input is disabled on the result screen");
    return false;
  }
  if (IsInputBlocked()) {
    OutReason = TEXT("critical fields invalid: ") +
                FString::Join(CriticalProblems, TEXT("; "));
    return false;
  }
  if (Stage != ES08Stage::Started) {
    OutReason = TEXT("match is not started");
    return false;
  }
  // DELIBERATELY no turn-owner check: the defender acts in the attacker's
  // COMBAT window and any participant may resolve in COMBAT_RESOLVE. Role
  // legality is server-authoritative; the local UI gates mirror it.
  if (bManeuverInFlight) {
    OutReason = TEXT("a command is already in flight");
    return false;
  }
  return true;
}

void FS08FlowController::Attack(const FString& AttackerFighterId,
                                const FString& CardInstanceId,
                                const FString& TargetFighterId) {
  FString Reason;
  if (!CanIssueGameplayCommand(Reason)) {
    Trace(TEXT("ATTACK blocked: ") + Reason);
    return;
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Variables->SetStringField(TEXT("attackerId"), AttackerFighterId);
  Variables->SetStringField(TEXT("cardId"), CardInstanceId);
  Variables->SetStringField(TEXT("targetId"), TargetFighterId);
  RunCombatMutation(TEXT("ATTACK"), TEXT("attack"), AttackMutation, Variables);
}

void FS08FlowController::PlayDefense(const FString& CardInstanceId) {
  FString Reason;
  if (!CanIssueCombatCommand(Reason)) {
    Trace(TEXT("DEFENSE blocked: ") + Reason);
    return;
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Variables->SetStringField(TEXT("cardId"), CardInstanceId);
  RunCombatMutation(TEXT("DEFENSE"), TEXT("playDefense"), PlayDefenseMutation, Variables);
}

void FS08FlowController::PlayScheme(const FString& CardInstanceId) {
  FString Reason;
  if (!CanIssueGameplayCommand(Reason)) {
    Trace(TEXT("SCHEME blocked: ") + Reason);
    return;
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Variables->SetStringField(TEXT("cardId"), CardInstanceId);
  RunCombatMutation(TEXT("SCHEME"), TEXT("playScheme"), PlaySchemeMutation, Variables);
}

void FS08FlowController::ResolveCombat() {
  FString Reason;
  if (!CanIssueCombatCommand(Reason)) {
    Trace(TEXT("RESOLVE blocked: ") + Reason);
    return;
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  RunCombatMutation(TEXT("RESOLVE"), TEXT("resolveCombat"), ResolveCombatMutation, Variables);
}

void FS08FlowController::ResolvePendingEffect(
    const FString& EffectId, const FString& FighterId, bool bHasCell, int32 X, int32 Y,
    bool bHasOption, int32 OptionIndex, const TArray<FString>& CardIds) {
  FString Reason;
  if (!CanIssueCombatCommand(Reason)) {
    Trace(TEXT("PEND resolve blocked: ") + Reason);
    return;
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Variables->SetStringField(TEXT("effectId"), EffectId);
  if (FighterId.IsEmpty()) {
    Variables->SetField(TEXT("fighterId"), MakeShared<FJsonValueNull>());
  } else {
    Variables->SetStringField(TEXT("fighterId"), FighterId);
  }
  if (bHasCell) {
    Variables->SetNumberField(TEXT("x"), X);
    Variables->SetNumberField(TEXT("y"), Y);
  } else {
    Variables->SetField(TEXT("x"), MakeShared<FJsonValueNull>());
    Variables->SetField(TEXT("y"), MakeShared<FJsonValueNull>());
  }
  if (bHasOption) {
    Variables->SetNumberField(TEXT("optionIndex"), OptionIndex);
  } else {
    Variables->SetField(TEXT("optionIndex"), MakeShared<FJsonValueNull>());
  }
  if (CardIds.Num() == 0) {
    Variables->SetField(TEXT("cardIds"), MakeShared<FJsonValueNull>());
  } else {
    TArray<TSharedPtr<FJsonValue>> Ids;
    for (const FString& Id : CardIds) {
      Ids.Add(MakeShared<FJsonValueString>(Id));
    }
    Variables->SetArrayField(TEXT("cardIds"), Ids);
  }
  RunCombatMutation(TEXT("PEND resolve"), TEXT("resolvePendingEffect"),
                    ResolvePendingEffectMutation, Variables);
}

void FS08FlowController::DeclinePendingEffect(const FString& EffectId) {
  FString Reason;
  if (!CanIssueCombatCommand(Reason)) {
    Trace(TEXT("PEND decline blocked: ") + Reason);
    return;
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Variables->SetStringField(TEXT("effectId"), EffectId);
  RunCombatMutation(TEXT("PEND decline"), TEXT("declinePendingEffect"),
                    DeclinePendingEffectMutation, Variables);
}

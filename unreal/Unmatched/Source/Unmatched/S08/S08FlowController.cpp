#include "S08FlowController.h"
#include "Dom/JsonObject.h"
#include "Misc/CommandLine.h"
#include "Misc/Guid.h"
#include "Misc/Parse.h"

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

// GD-038: rotate the access/refresh pair. The refresh token travels only in
// the request variables - never in a trace line or a URL.
static const TCHAR* RefreshTokensMutation =
    TEXT("mutation RT($refreshToken: String!) {")
    TEXT(" refreshTokens(refreshToken: $refreshToken) {")
    TEXT(" accessToken refreshToken user { id username } } }");

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
  SendHttp(HeroesQuery, Variables,
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

FHttpRequestPtr FS08FlowController::SendHttp(const FString& Query, const TSharedPtr<FJsonObject>& Variables,
                                             FS08GraphqlClient::FResult&& OnDone) {
#if WITH_AUTOMATION_TESTS
  ++TestHttpSendCount;
  TestLastHttpVariables = Variables;
  TestHttpQueries.Add(Query);
  if (TestHttpQueries.Num() > 256) TestHttpQueries.RemoveAt(0);
  if (DispatchQueuedHttpForTest(MoveTemp(OnDone))) return nullptr;
#endif
  return Http.Execute(Query, Variables, MoveTemp(OnDone));
}

void FS08FlowController::Login(const FString& Email, const FString& Password) {
  // Identity change: any refresh still in flight for the PREVIOUS session is
  // void - its deferred answer is dropped by the generation gate below.
  ++AuthGeneration;
  bRefreshInFlight = false;
  // S10 review P1(6): a relogin while a match is live must tear the previous
  // identity's match down BEFORE B's session installs - a surviving old
  // socket/room/op id would block B's subscribe and strand the server-side
  // membership of A's room (same accepted-leave teardown path).
  if (Stage == ES08Stage::Started || Ws.IsValid() || !Room.GameId.IsEmpty()) {
    TeardownGameStateStream();
    Room = FS08RoomState();
    Trace(TEXT("LOGIN identity change: previous match and stream torn down"));
  } else {
    // S10 review P1(4): no live stream/room, but room reads or mutations of
    // the PREVIOUS identity may still be in flight (e.g. a pending myGames).
    // Bump the match generation so their deferred answers fail the
    // request-identity gate - a late A answer must not install A's room for
    // B's fresh session - and drop any stale room view the same way.
    ++MatchGeneration;
    Room = FS08RoomState();
  }
  const int32 Gen = AuthGeneration;
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  TSharedRef<FJsonObject> Input = MakeShared<FJsonObject>();
  Input->SetStringField(TEXT("email"), Email);
  Input->SetStringField(TEXT("password"), Password);
  Variables->SetObjectField(TEXT("input"), Input);
  SendHttp(LoginQuery, Variables,
               [this, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors,
                      TSharedPtr<FJsonObject> Data, const FString& RawBody) {
                 // S10 review P1(5): concurrent logins - the deferred answer
                 // of an OLDER attempt must never install its tokens/user over
                 // the NEWER session (both success and failure are gated).
                 if (AuthGeneration != Gen) {
                   Trace(TEXT("LOGIN stale answer ignored: the session identity changed while the login was in flight"));
                   return;
                 }
                 FString AccessToken, RefreshToken, UserId, Username;
                 FS08GraphQLError Error;
                 // Two-stage: contract parser handles the login envelope.
                 if (FS08Contracts::ParseAuthResponse(RawBody, AccessToken, RefreshToken, UserId,
                                                      Username, Error)) {
                   this->UserId = UserId;
                   this->Username = Username;
                   Http.SetAccessToken(AccessToken);
                   this->RefreshToken = RefreshToken;
                   bSessionExpired = false;
                   RefreshStreak = 0;
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
SendHttp(MyGamesQuery, Variables, MoveTemp(OnDone));
}

void FS08FlowController::CreateRoom(const FString& Mode) {
  if (!CanEnterRoomFlow(TEXT("CREATE"))) return;
  // S10/GD-039: createGame retries of ONE intent reuse its key (a lost answer
  // redelivers the SAME room); a create AFTER this key already resolved to a
  // room is a NEW intent - rotate so two successive rooms get distinct ids.
  // S10 review M1: a key whose dispatch generation the live MatchGeneration
  // has moved past is equally spent - its in-flight answer (success or none)
  // is stale-dropped, so it can never resolve for THIS controller. Reusing it
  // would let the server redeliver the ABANDONED room for a logically new
  // create. A lost answer at an UNCHANGED generation keeps the key.
  if (!CreateKeyRoomId.IsEmpty() ||
      (CreateKeyDispatchGen != INDEX_NONE && CreateKeyDispatchGen != MatchGeneration)) {
    IdempotencyKey = TEXT("s08-") + FGuid::NewGuid().ToString(EGuidFormats::Digits);
    CreateKeyRoomId.Reset();
    Trace(TEXT("CREATE new intent: idempotency key rotated"));
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  TSharedRef<FJsonObject> Input = MakeShared<FJsonObject>();
  Input->SetStringField(TEXT("mode"), Mode.IsEmpty() ? TEXT("ONE_V_ONE") : Mode);
  // The board of the new room, explicit (2026-10-04, real boards only): -S08BoardId=<Board row id> (any run), else
  // the art-review pair -ArtPreview -ArtPreviewBoardId=<id>; without either the backend picks its default board
  // (Marmoreal - original map).
  FString BoardId;
  const TCHAR* BoardSource = TEXT("S08BoardId");
  if (!FParse::Value(FCommandLine::Get(), TEXT("S08BoardId="), BoardId) || BoardId.IsEmpty()) {
    BoardId.Reset();
    BoardSource = TEXT("ArtPreviewBoardId");
    if (FParse::Param(FCommandLine::Get(), TEXT("ArtPreview"))) {
      FParse::Value(FCommandLine::Get(), TEXT("ArtPreviewBoardId="), BoardId);
    }
  }
  if (!BoardId.IsEmpty()) {
    Input->SetStringField(TEXT("boardId"), BoardId);
    Trace(FString::Printf(TEXT("CREATE boardId=%s source=%s"), *BoardId, BoardSource));
  }
  Variables->SetObjectField(TEXT("input"), Input);
  Variables->SetStringField(TEXT("idempotencyKey"), IdempotencyKey);
  const int32 Gen = MatchGeneration;
  CreateKeyDispatchGen = Gen; // M1: pins the retry/stale boundary (see above)
  FS08GraphqlClient::FResult OnDone =
      [this, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors,
                  TSharedPtr<FJsonObject> Data, const FString&) {
        // Stale answer: the player already left/joined elsewhere before the
        // create resolved - the created room must not clobber the newer one.
        // The key is spent either way: the NEXT CreateRoom rotates it (the
        // dispatch-generation check in CreateRoom, M1) instead of redelivering
        // the abandoned room for the new intent.
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
        // The intent resolved to this room: the NEXT CreateRoom rotates the
        // key, a retry of this one (none - it already answered) cannot.
        if (!Room.GameId.IsEmpty()) CreateKeyRoomId = Room.GameId;
      };
SendHttp(CreateGameMutation, Variables, MoveTemp(OnDone));
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
SendHttp(JoinGameMutation, JoinVars, MoveTemp(OnJoinDone));
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
SendHttp(GameByCodeQuery, Variables, MoveTemp(OnLookupDone));
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
SendHttp(SelectHeroMutation, Variables, MoveTemp(OnDone));
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
SendHttp(ToggleReadyMutation, Variables, MoveTemp(OnDone));
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
        // No attach here: HandleRoomResponse already attaches on the
        // Room -> IN_PROGRESS transition (the same path the guest's poll
        // uses), and by the time this line runs that attach has flipped the
        // stage to Started - a second AttachGameStateStream would only issue
        // a duplicate gameState fetch over the already-live stream.
        HandleRoomResponse(Data, TEXT("startGame"));
      };
SendHttp(StartGameMutation, Variables, MoveTemp(OnDone));
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
        // MS-T-04: the player left the match - its maneuver draft goes too (a
        // relogin teardown keeps it: the same user may re-enter the match).
        ManeuverDraftCache = FS08ManeuverDraftCache();
        // Stage first: the teardown below can observe WS close side effects,
        // and a reconnect must only ever arm while the match is live.
        SetStage(ES08Stage::Lobby);
        TeardownGameStateStream();
      };
SendHttp(LeaveGameMutation, Variables, MoveTemp(OnLeaveDone));
}

void FS08FlowController::MakeWs() {
  ++WsGeneration;
  // P1(3): a fresh socket starts unreconciled - ready only after ack +
  // subscribe + the first barrier body (see IsStreamReady).
  bStreamReconciled = false;
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
  EndManeuverOp(); // MS-T-06: the open command (clock, request) belonged to this match
  RetiredCommandTokens.Reset();
  bManeuverInFlight = false;
  bMutationRecoveryActive = false; // the lost command belonged to this match
  MutationRecoveryAttempts = 0;
  MutationRecoveryRetryCountdown = -1.0f;
  MutationRecoveryBackoff = 1.0f;
  MutationRecoveryBaselineSeq = 0;
  bMutationRecoveryHasBaseline = false;
  bMutationRecoveryFreshRead = false;
  bBarrierHttpBody = false;
  bWsAwaitingBarrierFrame = false;
  bWsBarrierFrame = false;
  bStreamReconciled = false;
  bGameStateOpLive = false;
  MutationRecoveryPendingChoiceId.Reset();
  bMutationRecoveryPendingChoiceIsDiscard = false;
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
    OnWsTransportClosed(StatusCode, Reason);
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
  bGameStateOpLive = false;
  // P1(3): the subscription just died - the stream is not ready until the
  // resubscribe below succeeds AND a fresh barrier body reconciles it.
  bStreamReconciled = false;
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

// ---- GD-037: lost mutation response recovery (ACC-012) ----------------------

bool FS08FlowController::IsOutcomeUnknown(const TArray<FS08GraphQLError>& Errors) {
  // No HTTP answer at all (HttpStatus == 0), or a 5xx after the request
  // reached the server: the mutation may have been applied. A 4xx or a
  // GraphQL errors[] body is a definitive answered rejection. A PARSE
  // failure on an HTTP 200 (truncated/malformed body AFTER the server
  // answered) is also outcome-unknown: the commit state is unreadable.
  if (Errors.Num() == 0) return false;
  const int32 Status = Errors[0].HttpStatus;
  const FString& Code = Errors[0].Code;
  if (Code == TEXT("TRANSPORT") && Status == 0) return true;
  if (Code == TEXT("PARSE")) return true;
  if (Status >= 500) return true;
  return false;
}

void FS08FlowController::EnterMutationRecovery(const FString& Reason,
                                               const FString& PendingChoiceId,
                                               bool bPendingIsDiscard) {
  if (bMutationRecoveryActive) return;
  bMutationRecoveryActive = true;
  MutationRecoveryAttempts = 0;
  MutationRecoveryBackoff = 1.0f;
  // P1(1): the unlock baseline. Only a body FRESHER than this (an HTTP read
  // dispatched under the lock, or a WS seq strictly past the baseline) may
  // release it - a same-seq pre-command WS snapshot must not.
  MutationRecoveryBaselineSeq = SeqGuard.Local;
  bMutationRecoveryHasBaseline = SeqGuard.HasLocal;
  // P2(8): a lost pending-choice/discard command holds until THAT choice is
  // settled - a bare seq advance can be an unrelated event.
  MutationRecoveryPendingChoiceId = PendingChoiceId;
  bMutationRecoveryPendingChoiceIsDiscard = bPendingIsDiscard;
  Trace(Reason +
        TEXT(" - outcome unknown: input locked, refetching authoritative state (no resend)"));
  AttemptMutationRecoveryRefetch();
}

void FS08FlowController::HandleMutationParseFailure(const FString& Tag,
                                                    const FString& PendingChoiceId,
                                                    bool bPendingIsDiscard) {
  // S10 review P1(2): an HTTP 200 whose body cannot be parsed arrived AFTER
  // the server answered - the commit state is unknown. Recover through the
  // authoritative refetch; a manual resend could repeat the spend.
  EnterMutationRecovery(Tag + TEXT(" parse error: outcome unknown"), PendingChoiceId,
                        bPendingIsDiscard);
}

void FS08FlowController::HandleMutationRecoveryReadFailed() {
  // S10 review P1(4): shared bounded tail for a FAILED recovery read (no
  // HTTP answer, 5xx, or an HTTP 200 body that cannot be parsed). The old
  // parse-error path broadcast the error but never re-armed the ladder -
  // the mutation lock then held forever with zero retries left ticking.
  if (!bMutationRecoveryActive) return;
  if (MutationRecoveryAttempts >= MaxMutationRecoveryAttempts) {
    MutationRecoveryRetryCountdown = -1.0f;
    Trace(TEXT("STATE recovery exhausted - manual action required; input stays locked"));
    OnFlowError.Broadcast(FS08GraphQLError{
        TEXT("PROTOCOL"), TEXT("could not restore the game state after a lost response"),
        FString()});
    return;
  }
  MutationRecoveryRetryCountdown = MutationRecoveryBackoff;
  MutationRecoveryBackoff = FMath::Min(MutationRecoveryBackoff * 2.0f, 15.0f);
  Trace(FString::Printf(TEXT("RECOVERY refetch failed - retry in %.0fs"),
                        MutationRecoveryRetryCountdown));
}

void FS08FlowController::AttemptMutationRecoveryRefetch() {
  if (!bMutationRecoveryActive) return;
  if (MutationRecoveryAttempts >= MaxMutationRecoveryAttempts) {
    MutationRecoveryRetryCountdown = -1.0f;
    return;
  }
  ++MutationRecoveryAttempts;
  MutationRecoveryRetryCountdown = -1.0f; // re-armed by the failure path
  Trace(FString::Printf(TEXT("RECOVERY refetch %d/%d"), MutationRecoveryAttempts,
                        MaxMutationRecoveryAttempts));
  FetchGameState();
}

// ---- GD-038: authorization recovery (ACC-021) -------------------------------

bool FS08FlowController::IsAuthError(const TArray<FS08GraphQLError>& Errors) {
  // S10 review P1(1): classify against the shapes the BACKEND actually sends
  // (verified live, evidence/S08 + backend e2e): HTTP 200 GraphQL errors[]
  // carry extensions.code = UNAUTHENTICATED (Nest 401), and the throttler
  // uses TOO_MANY_REQUESTS. The legacy AUTH/UNAUTHORIZED spellings and the
  // web-client's AUTH_TOKEN_EXPIRED/AUTH_INVALID_TOKEN set stay recognized.
  for (const FS08GraphQLError& Error : Errors) {
    if (Error.HttpStatus == 401) return true;
    if (Error.Code == TEXT("AUTH") || Error.Code == TEXT("UNAUTHORIZED") ||
        Error.Code == TEXT("UNAUTHENTICATED") || Error.Code == TEXT("AUTH_TOKEN_EXPIRED") ||
        Error.Code == TEXT("AUTH_INVALID_TOKEN")) {
      return true;
    }
  }
  return false;
}

bool FS08FlowController::IsRateLimited(const TArray<FS08GraphQLError>& Errors) {
  for (const FS08GraphQLError& Error : Errors) {
    if (Error.HttpStatus == 429) return true;
    if (Error.Code == TEXT("RATE_LIMIT") || Error.Code == TEXT("TOO_MANY_REQUESTS")) {
      return true;
    }
  }
  return false;
}

bool FS08FlowController::TryRefreshAuth() {
  if (bSessionExpired) return false;
  if (bRefreshInFlight) return true; // single flight; the caller drops
  if (RefreshToken.IsEmpty()) {
    EnterSessionExpired(TEXT("no refresh token is held"));
    return false;
  }
  if (RefreshStreak >= 2) {
    // A freshly rotated token was rejected again - rotation is not taking
    // effect; looping refreshes would hammer the auth endpoint.
    EnterSessionExpired(TEXT("the rotated token was rejected again"));
    return false;
  }
  bRefreshInFlight = true;
  ++RefreshCount;
  const int32 Gen = AuthGeneration;
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("refreshToken"), RefreshToken);
  SendHttp(RefreshTokensMutation, Variables,
           [this, Gen](bool bOk, const TArray<FS08GraphQLError>& Errors,
                  TSharedPtr<FJsonObject>, const FString& RawBody) {
             // S10 review P2(7): generation check FIRST. A stale callback
             // (its identity was replaced mid-flight by a relogin) must not
             // clear bRefreshInFlight either - a NEWER refresh may be in
             // flight under the current identity, and clearing the flag here
             // would let a second concurrent refresh slip through the
             // single-flight gate.
             if (AuthGeneration != Gen) {
               Trace(TEXT("AUTH refresh answer dropped: the session identity changed while the refresh was in flight"));
               return;
             }
             bRefreshInFlight = false;
             if (bSessionExpired) return;
             FString AccessToken, RefreshToken, UserId, Username;
             FS08GraphQLError Error;
             if (bOk && FS08Contracts::ParseAuthResponse(
                            RawBody, AccessToken, RefreshToken, UserId, Username, Error,
                            TEXT("refreshTokens"))) {
               // P1(4): belt-and-braces identity check - a refresh answer for
               // a DIFFERENT user than the signed-in one is anomalous and is
               // never allowed to rotate the token pair.
               if (!UserId.IsEmpty() && !this->UserId.IsEmpty() && UserId != this->UserId) {
                 Trace(TEXT("AUTH refresh answer dropped: returned user differs from the signed-in identity"));
                 return;
               }
               Http.SetAccessToken(AccessToken);
               if (!RefreshToken.IsEmpty()) this->RefreshToken = RefreshToken;
               ++RefreshStreak;
               Trace(TEXT("AUTH refreshed - token pair rotated; WS will be recreated"));
               RecreateWsAfterAuthRotation();
               // Retry the triggering READ exactly once with the new token
               // (never a gameplay mutation - its outcome may be applied).
               if (Stage == ES08Stage::Started) {
                 FetchGameState();
               } else if (Stage == ES08Stage::Room) {
                 PollRoom();
               }
               return;
             }
             if (IsRateLimited(Errors)) {
               // 429 is "later", not "expired": surface it, never auto-retry.
               Trace(TEXT("AUTH refresh rate limited - no automatic retry"));
               OnFlowError.Broadcast(Errors.Num() ? Errors[0]
                                                  : FS08GraphQLError{TEXT("RATE_LIMIT"),
                                                                     TEXT("refresh throttled"),
                                                                     FString()});
               return;
             }
             EnterSessionExpired(Errors.Num() ? Errors[0].Message
                                              : FString(TEXT("token refresh failed")));
           });
  return true;
}

void FS08FlowController::EnterSessionExpired(const FString& Why) {
  if (bSessionExpired) return;
  bSessionExpired = true;
  ++AuthGeneration; // a refresh still in flight belongs to the dead session
  Http.SetAccessToken(FString());
  RefreshToken.Reset();
  bMutationRecoveryActive = false;
  MutationRecoveryRetryCountdown = -1.0f;
  EndManeuverOp(); // MS-T-06: no deadline / recovery for a dead session
  // The socket was authenticated with the dead token: drop it and disarm the
  // reconnect ladder (it would loop with 4403s forever).
  if (Ws.IsValid()) {
    if (!GameStateOpId.IsEmpty()) Ws->Unsubscribe(GameStateOpId);
    Ws.Reset();
  }
  GameStateOpId.Reset();
  WsReconnectCountdown = -1.0f;
  bStreamReconciled = false;
  bGameStateOpLive = false;
  bWsAwaitingBarrierFrame = false;
  Trace(TEXT("SESSION expired: ") + Why + TEXT(" - sign in again"));
  OnFlowError.Broadcast(FS08GraphQLError{TEXT("SESSION_EXPIRED"),
                                         TEXT("Session expired - sign in again"), FString()});
  SetStage(ES08Stage::Failed);
}

void FS08FlowController::RecreateWsAfterAuthRotation() {
  if (Stage != ES08Stage::Started) return;
  // The live socket was authenticated with the (now rotated-away) token:
  // rebuild it so connection_init carries the fresh one. The armed reconnect
  // reuses the existing ack path (subscribe from local seq + barrier fetch).
  if (Ws.IsValid()) {
    if (!GameStateOpId.IsEmpty()) Ws->Unsubscribe(GameStateOpId);
    Ws.Reset();
  }
  GameStateOpId.Reset();
  WsReconnectBackoff = 1.0f;
  if (WsReconnectCountdown < 0.0f) WsReconnectCountdown = 0.5f;
  bWsReconnectAckPending = true;
  bStreamReconciled = false;
  bGameStateOpLive = false;
  Trace(TEXT("AUTH: socket dropped - WS recreation armed with the rotated token"));
}

void FS08FlowController::OnWsTransportClosed(int32 StatusCode, const FString& Reason) {
  if (bSessionExpired) return;
  // The close reason string is server-controlled text: it never reaches a
  // trace line. Only the numeric code and a fixed client-side description
  // are logged (S10 review P2(8), canary-tested).
  if (StatusCode == 4403) {
    // graphql-ws "Forbidden": connection_init auth was rejected. Reconnecting
    // with the same dead token would loop 4403s - go through the refresh path
    // instead (rotation arms the socket recreation itself).
    Trace(FString::Printf(TEXT("WS closed %d (auth rejected) - refreshing the token"),
                          StatusCode));
    if (TryRefreshAuth()) return;
    if (bSessionExpired) return; // terminal; nothing left to reconnect with
  }
  if (StatusCode == 4408 || StatusCode == 4409) {
    Trace(FString::Printf(TEXT("WS closed %d (graphql-ws control close: %s)"), StatusCode,
                          WsCloseDescription(StatusCode)));
  } else {
    // Any other code still owes the trace line its numeric code (canary-
    // tested: the server-controlled reason text never appears).
    Trace(FString::Printf(TEXT("WS closed %d (%s)"), StatusCode,
                          WsCloseDescription(StatusCode)));
  }
  if (Stage == ES08Stage::Started) {
    ScheduleWsReconnect(FString::Printf(TEXT("code %d (%s)"), StatusCode,
                                        WsCloseDescription(StatusCode)));
  }
}

const TCHAR* FS08FlowController::WsCloseDescription(int32 StatusCode) {
  switch (StatusCode) {
    case -1:   return TEXT("connection failed");
    case 1000: return TEXT("normal closure");
    case 1001: return TEXT("going away");
    case 1006: return TEXT("abnormal closure");
    case 1011: return TEXT("server error");
    case 4400: return TEXT("invalid message");
    case 4401: return TEXT("unauthorized: connection_init required");
    case 4403: return TEXT("forbidden: connection_init rejected");
    case 4408: return TEXT("connection acknowledgement timeout");
    case 4409: return TEXT("subscriber already exists");
    case 4429: return TEXT("too many initialisation requests");
    default:   return TEXT("closed");
  }
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
  QueuedHttpFifo.Add(FQueuedHttpResult{bOk, bDeferDelivery, MoveTemp(InErrors), InRawBody});
}

void FS08FlowController::DeliverQueuedHttpForTest(int32 Index) {
  if (Index < 0 || Index >= DeferredHttpQueue.Num()) return;
  FDeferredHttp Entry = MoveTemp(DeferredHttpQueue[Index]);
  DeferredHttpQueue.RemoveAt(Index);
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
  if (QueuedHttpFifo.Num() == 0) return false;
  FQueuedHttpResult Result = MoveTemp(QueuedHttpFifo[0]);
  QueuedHttpFifo.RemoveAt(0);
  if (Result.bDeferred) {
    FDeferredHttp Entry;
    Entry.Result = MoveTemp(Result);
    Entry.OnDone = MoveTemp(OnDone);
    DeferredHttpQueue.Add(MoveTemp(Entry));
    return true; // answer held back until DeliverQueuedHttpForTest()
  }
  InvokeQueuedHttpForTest(Result, MoveTemp(OnDone));
  return true;
}
#endif

void FS08FlowController::AttachGameStateStream() {
  // Stage FIRST: the barrier fetch below can resolve synchronously (offline
  // harness), and its snapshot must pass ApplyMatchSnapshot's Started gate -
  // on a live network the answer arrives later and the old order was safe,
  // but the Room->IN_PROGRESS host/guest path with a synchronous harness
  // dropped the barrier body ("match no longer live").
  SetStage(ES08Stage::Started);
  // Barrier protocol (unmatched-net/1 section 4): the ORDER of HTTP snapshot
  // and WS subscribe does not need to be strict - the subscription is opened
  // with since = local seq and the server delivers a barrier snapshot when
  // the state moved past it; duplicates collapse in the seq guard.
  FetchGameState();
  if (!Ws.IsValid()) {
    MakeWs();
  }
}

void FS08FlowController::ScheduleWsReconnect(const FString& Reason) {
  // The dead FS08GraphqlWs object is destroyed on the next retry boundary
  // (TickConnectivity), never from inside its own close delegate.
  GameStateOpId.Reset();
  bGameStateOpLive = false;
  bStreamReconciled = false; // P1(3): reconnect owes a fresh reconciliation
  if (WsReconnectCountdown >= 0.0f) return; // already armed
  static constexpr float MaxBackoffSeconds = 15.0f;
  WsReconnectCountdown = WsReconnectBackoff;
  WsReconnectBackoff = FMath::Min(WsReconnectBackoff * 2.0f, MaxBackoffSeconds);
  Trace(FString::Printf(TEXT("WS closed (%s) - reconnect in %.0fs"), *Reason,
                        WsReconnectCountdown));
}

void FS08FlowController::TickConnectivity(float DeltaSeconds) {
  // MS-T-06: the 3 s / 10 s clock of a beginManeuver / maneuver command.
  TickCommandDeadline(DeltaSeconds);
  // GD-037: the lost-response recovery ladder ticks independently of the WS
  // transport ladder (a dead HTTP path must not wait for a socket cycle).
  if (MutationRecoveryRetryCountdown >= 0.0f) {
    MutationRecoveryRetryCountdown -= DeltaSeconds;
    if (MutationRecoveryRetryCountdown <= 0.0f) {
      MutationRecoveryRetryCountdown = -1.0f;
      AttemptMutationRecoveryRefetch();
    }
  }
  if (WsReconnectCountdown < 0.0f) return;
  WsReconnectCountdown -= DeltaSeconds;
  if (WsReconnectCountdown > 0.0f) return;
  WsReconnectCountdown = -1.0f;
  Trace(TEXT("WS reconnect attempt"));
  if (Ws.IsValid()) Ws.Reset();
  // A zombie subscribe id (registered by a dying socket between the close
  // and this reset) must never block the fresh handshake's resubscribe.
  GameStateOpId.Reset();
  bGameStateOpLive = false;
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
  // Sol6 review P1(3) liveness probe: the server emits its barrier snapshot
  // only while state.seq > since, so a subscribe at exactly the current seq
  // would never deliver a frame and the operation could not prove itself
  // live (a quiet game would deadlock the input gate). Asking for one seq
  // less forces the barrier snapshot; its duplicate collapses in the seq
  // guard and its cues are suppressed by the barrier slot.
  const int32 ProbeSince = FMath::Max(0, Since - 1);
  // P1(2): the first 'next' this fresh subscription delivers is the server's
  // barrier snapshot (state at subscribe time) - a reconciliation body, its
  // diff fires no cues.
  bWsAwaitingBarrierFrame = true;
  // The NEW operation id is only locally registered here: it is not live
  // until the server accepts it (first delivered frame) - see bGameStateOpLive.
  bGameStateOpLive = false;
  GameStateOpId = Ws->SubscribeGameStateUpdated(
      Room.GameId, ProbeSince,
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
        // Sol6 review P1(3): a delivered frame proves the server ACCEPTED
        // this subscription - the operation is live.
        bGameStateOpLive = true;
        // P1(2): consume the barrier slot on the first delivered frame.
        const bool bFirstFrame = bWsAwaitingBarrierFrame;
        bWsAwaitingBarrierFrame = false;
        bWsBarrierFrame = bFirstFrame;
        const ES08SeqDecision Decision = ApplyMatchSnapshot(Snapshot);
        bWsBarrierFrame = false;
        // P1(3): a delivered frame proves the live subscription carries
        // server truth - the stream is reconciled.
        bStreamReconciled = true;
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
  // A read dispatched while the recovery lock is held is FRESH evidence by
  // construction when its answer arrives (P1(1)); one dispatched before the
  // lock armed is not, and must not unlock at a same-seq body.
  const bool bRecoveryArmedAtDispatch = bMutationRecoveryActive;
  FS08GraphqlClient::FResult OnDone =
      [this, GameId, Gen, bRecoveryArmedAtDispatch](bool bOk, const TArray<FS08GraphQLError>& Errors,
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
          // GD-038: a rejected access token triggers ONE refresh; the rotated
          // token also re-runs this fetch (reads may retry - never mutations).
          if (IsAuthError(Errors) && !bSessionExpired) {
            Trace(TEXT("STATE auth rejected - refreshing the session"));
            if (TryRefreshAuth()) return;
            if (bSessionExpired) return;
          }
          // GD-038: 429 is "try later": surface once, never auto-retry (and
          // disarm the GD-037 recovery ladder so it cannot hammer the limit).
          if (IsRateLimited(Errors)) {
            MutationRecoveryRetryCountdown = -1.0f;
            Trace(TEXT("STATE rate limited - no automatic retry"));
            OnFlowError.Broadcast(Errors[0]);
            return;
          }
          Trace(TEXT("STATE failed: ") + (Errors.Num() ? Errors[0].Message : TEXT("?")));
          // GD-037: a lost recovery refetch retries on the bounded backoff
          // ladder; the bound exhausted surfaces a visible error and KEEPS
          // the input lock (any command would be a blind resend). While the
          // lock is held it owns the error surface - the transient read
          // failure is not broadcast as a flow error.
          if (bMutationRecoveryActive) {
            HandleMutationRecoveryReadFailed();
            return;
          }
          OnFlowError.Broadcast(Errors.Num() ? Errors[0]
                                             : FS08GraphQLError{TEXT("TRANSPORT"), TEXT("state failed"), FString()});
          return;
        }
        FS08Snapshot Snapshot;
        FString RawState;
        FS08GraphQLError Error;
        if (FS08Contracts::ParseGameStateQuery(RawBody, Snapshot, RawState, Error)) {
          bBarrierHttpBody = true;            // reconciliation read: no cues
          bMutationRecoveryFreshRead = bRecoveryArmedAtDispatch; // fresh evidence (P1(1))
          const ES08SeqDecision Decision = ApplyMatchSnapshot(Snapshot);
          bMutationRecoveryFreshRead = false;
          bBarrierHttpBody = false;
          Trace(FString::Printf(TEXT("STATE seq=%d -> %s"), Snapshot.SequenceNumber,
                                Decision == ES08SeqDecision::Apply ? TEXT("apply")
                                                                   : TEXT("merge")));
          SubscribeAfterSnapshot(Snapshot.SequenceNumber);
          // Sol6 review P1(2): this HTTP read must NOT clear the first-WS-
          // frame barrier slot. Read-first/WS-second order: the read applies
          // seq 10, the subscription's opening snapshot is the server's
          // barrier body at seq 11 - treating it as a live transition would
          // replay an old CUE. The slot closes only on the first delivered
          // WS frame (or a teardown); a same-or-older duplicate merges in
          // the seq guard afterwards.
        } else {
          Trace(TEXT("STATE parse error: ") + Error.Message);
          // P1(4): an unreadable HTTP 200 recovery read is a FAILED read for
          // the lock's purposes: bounded retry ladder, visible exhaustion
          // error, lock stays - never a silent dead end.
          if (bMutationRecoveryActive) {
            HandleMutationRecoveryReadFailed();
            return;
          }
          OnFlowError.Broadcast(Error);
        }
      };
SendHttp(GameStateQuery, Variables, MoveTemp(OnDone));
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
          // GD-038: room reads share the auth recovery path (one refresh, no
          // blind retry of anything).
          if (IsAuthError(Errors) && !bSessionExpired) {
            Trace(TEXT("POLL auth rejected - refreshing the session"));
            if (TryRefreshAuth()) return;
            if (bSessionExpired) return;
          }
          if (IsRateLimited(Errors)) {
            Trace(TEXT("POLL rate limited - no automatic retry"));
            OnFlowError.Broadcast(Errors[0]);
            return;
          }
          Trace(TEXT("POLL failed: ") + (Errors.Num() ? Errors[0].Message : TEXT("?")));
          return;
        }
        HandleRoomResponse(Data, TEXT("game"));
      };
SendHttp(GameQuery, Variables, MoveTemp(OnDone));
}

bool FS08FlowController::CanIssueGameplayCommand(FString& OutReason) const {
  OutReason.Reset();
  if (Stage == ES08Stage::Started && IsRoomAborted()) {
    // S10/GD-040: the room row (not a snapshot/CUE) proved the match was
    // interrupted - every gameplay command must stop; only leave remains.
    OutReason = TEXT("the match was interrupted (room aborted) - gameplay input is disabled");
    return false;
  }
  if (IsRoomTerminal()) {
    OutReason = TEXT("the duel is over - gameplay input is disabled on the result screen");
    return false;
  }
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
  if (!IsStreamReady()) {
    OutReason = TEXT("live stream is reconnecting - commands wait until the state stream is back");
    return false;
  }
  if (bMutationRecoveryActive) {
    OutReason = TEXT("restoring authoritative state after a lost response - commands are locked");
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
  // Cues are derived ONLY from a CONTIGUOUS authoritative transition
  // (incoming == local + 1): a same-seq merge may enrich panel data but must
  // never re-fire presentation effects (ACC-011: duplicate HTTP+WS -> one
  // visual event), and a GAP (reconnect barrier snapshot spanning missed
  // events) carries no intermediate transitions - diffing across it would
  // fabricate stale animations (ACC-012: old CUEs are not replayed).
  TArray<FS08Cue> Cues;
  if (Decision == ES08SeqDecision::Apply) {
    if (bBarrierHttpBody || bWsBarrierFrame) {
      // P1(3)/P1(2): an HTTP gameState body (reconnect barrier or recovery
      // refetch) AND the first WS frame of a fresh subscription (the server's
      // barrier snapshot at subscribe time) are reconciliation reads, not
      // live transitions - their diffs fire NO cues at ANY gap size,
      // contiguous included (local 10 -> barrier 11 must not animate).
      if (SeqGuard.HasLocal) {
        Trace(FString::Printf(TEXT("SEQ %d barrier body: cues suppressed"),
                              Snapshot.SequenceNumber));
      }
    } else if (SeqGuard.HasLocal && Snapshot.SequenceNumber == SeqGuard.Local + 1) {
      ComputeCues(Snapshot.SequenceNumber, Applied.Fighters, Snapshot.Fighters, Cues);
    } else if (SeqGuard.HasLocal) {
      Trace(FString::Printf(TEXT("SEQ %d gap from %d: cues suppressed"), Snapshot.SequenceNumber,
                            SeqGuard.Local));
    }
  }
  // P1(3): an applied/merged body reconciles the store with server truth.
  bStreamReconciled = true;
  // S10 review P1(1): the GD-037 lost-response lock releases ONLY on a
  // verified fresh result - an HTTP gameState read dispatched while the lock
  // was held (fresh by construction, any seq) or a WS body strictly past the
  // baseline captured at arm time. A same-or-older-seq WS snapshot is the
  // pre-command state and keeps the lock.
  if (bMutationRecoveryActive) {
    bool bFreshResult = bMutationRecoveryFreshRead || !bMutationRecoveryHasBaseline ||
                        Snapshot.SequenceNumber > MutationRecoveryBaselineSeq;
    // P2(8) + Sol6 review P1(1)/P2(4): when the lost command was resolving a
    // pending choice, fresh is not enough - the body must PROVE the choice
    // settled, and it proves that BY CHOICE KIND. A pendingEffects resolve
    // settles on a strictly valid pendingEffects array lacking the id (a
    // malformed entry like [null] leaves the whole queue unverifiable);
    // a discardToLimit settles through pendingHandDiscard - a different open
    // discard id, or the field absent from a COMPLETE full state (the
    // backend removes it as undefined once resolved). A PARTIAL body (a WS
    // event without the field) proves nothing: the applied store keeps the
    // stale metadata through merge semantics, so "absent" must read as
    // "unknown", never "gone" - releasing on it would allow a double submit.
    if (bFreshResult && !MutationRecoveryPendingChoiceId.IsEmpty()) {
      const bool bValidMeta = Snapshot.Metadata.IsValid() &&
                              Snapshot.Metadata->AsObject().IsValid();
      bool bStillOpen = false;
      bool bSettledProof = false;
      if (bMutationRecoveryPendingChoiceIsDiscard) {
        FS08PendingHandDiscard Discard;
        bool bFieldPresent = false;
        if (FS08Contracts::PendingHandDiscardStrict(Snapshot, Discard, bFieldPresent)) {
          // Only one discard choice can be open at a time: a different id
          // means ours was authoritatively closed (or replaced).
          if (Discard.Id == MutationRecoveryPendingChoiceId) {
            bStillOpen = true;
          } else {
            bSettledProof = true;
          }
        } else if (!bFieldPresent && bBarrierHttpBody && bValidMeta) {
          // Release on absence ONLY: the key is truly gone from a complete
          // authoritative body. A present-but-invalid field (null, wrong
          // type, object without an id) is unverifiable, not settled.
          bSettledProof = true;
        }
      } else {
        TArray<FS08PendingEffect> PendingQueue;
        bool bArrayPresent = false;
        if (FS08Contracts::PendingEffectsStrict(Snapshot, PendingQueue, bArrayPresent)) {
          for (const FS08PendingEffect& Effect : PendingQueue) {
            if (Effect.Id == MutationRecoveryPendingChoiceId) {
              bStillOpen = true;
              break;
            }
          }
          if (!bStillOpen) bSettledProof = true;
        } else if (!bArrayPresent && bBarrierHttpBody && bValidMeta) {
          bSettledProof = true;
        }
      }
      if (bStillOpen) {
        bFreshResult = false;
        Trace(FString::Printf(
            TEXT("RECOVERY held: pending choice %s is still open at seq %d"),
            *MutationRecoveryPendingChoiceId, Snapshot.SequenceNumber));
      } else if (!bSettledProof) {
        bFreshResult = false;
        Trace(FString::Printf(
            TEXT("RECOVERY held: pending choice %s unverifiable at seq %d (no valid pending metadata - stale metadata is not proof)"),
            *MutationRecoveryPendingChoiceId, Snapshot.SequenceNumber));
      }
    }
    if (bFreshResult) {
      bMutationRecoveryActive = false;
      MutationRecoveryRetryCountdown = -1.0f;
      MutationRecoveryPendingChoiceId.Reset();
      bMutationRecoveryPendingChoiceIsDiscard = false;
      Trace(FString::Printf(TEXT("RECOVERY complete: authoritative state at seq %d"),
                            Snapshot.SequenceNumber));
    } else if (MutationRecoveryPendingChoiceId.IsEmpty()) {
      Trace(FString::Printf(
          TEXT("RECOVERY held: seq %d is not fresher than the locked baseline %d"),
          Snapshot.SequenceNumber, MutationRecoveryBaselineSeq));
    }
  }
  RefreshStreak = 0;
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
  // MS-E-90: the snapshot may settle the open maneuver command before its
  // HTTP answer - the gate opens before the render/HUD sees this state.
  ReleaseManeuverGateBySnapshot(Snapshot);
  OnApplied.Broadcast(Applied, Decision);
  if (Cues.Num() > 0) OnCues.Broadcast(Cues);
  return Decision;
}

void FS08FlowController::HandleRoomResponse(TSharedPtr<FJsonObject> Data, const FString& Field) {
  if (!Data.IsValid()) return;
  RefreshStreak = 0; // a successful response proves the current token works
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
    // S10/GD-040: a terminal room row installed while the match is LIVE is
    // authoritative (fresh poll/mutation answer - every caller sits behind the
    // stale gates, and a named CUE or an old snapshot never routes here).
    // ABORTED: an interruption, never a verdict - gameplay input blocks via
    // IsRoomTerminal() and only LeaveRoom remains. FINISHED: if the terminal
    // GAME_OVER snapshot has not arrived yet (the stream may have died), one
    // fresh HTTP read delivers the authoritative phase + winner.
    if (Stage == ES08Stage::Started) {
      if (IsRoomAborted()) {
        Trace(TEXT("ROOM aborted: the live match was interrupted - input disabled, leave remains"));
        if (Ws.IsValid() && !GameStateOpId.IsEmpty()) {
          // The room is dead server-side; stop the subscription so a dead
          // stream cannot spin the bounded operation recovery while the
          // interruption screen waits for the leave.
          Ws->Unsubscribe(GameStateOpId);
          GameStateOpId.Reset();
          bGameStateOpLive = false;
          bStreamReconciled = false;
        }
        // The dead room must not keep any timer alive either: a WS reconnect
        // armed by an earlier transport loss would reconnect and resubscribe
        // to a room that no longer serves state (a spurious error loop), and
        // the GD-037 mutation-recovery ladder would keep refetching a dead
        // game and broadcast its failures over the interruption screen.
        // Cancel both ladders; the request-identity/stale gates stay intact
        // so late answers for this match still drop at the usual places.
        WsReconnectCountdown = -1.0f;
        bWsReconnectAckPending = false;
        OpRecoveryAttempts = 0;
        bMutationRecoveryActive = false;
        MutationRecoveryAttempts = 0;
        MutationRecoveryRetryCountdown = -1.0f;
        MutationRecoveryBackoff = 1.0f;
        MutationRecoveryBaselineSeq = 0;
        bMutationRecoveryHasBaseline = false;
        MutationRecoveryPendingChoiceId.Reset();
        bMutationRecoveryPendingChoiceIsDiscard = false;
        EndManeuverOp(); // MS-T-06: its 10 s deadline must not re-arm the recovery
        bManeuverInFlight = false;
      } else if (Room.Status == TEXT("FINISHED") && Applied.Phase != TEXT("GAME_OVER")) {
        Trace(TEXT("ROOM finished without a local GAME_OVER body - refetching state"));
        FetchGameState();
      }
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
  if (NewRoom.GameId != Room.GameId) {
    ++MatchGeneration;
    EndManeuverOp(); // MS-T-06: the command belonged to the previous room
  }
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

bool FS08FlowController::BeginManeuver() {
  FString Reason;
  if (!CanIssueGameplayCommand(Reason)) {
    Trace(TEXT("MANEUVER begin blocked: ") + Reason);
    return false;
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Variables->SetNumberField(TEXT("expectedSequenceNumber"), SeqGuard.Local);
  const FString GameId = Room.GameId;
  const int32 Gen = MatchGeneration;
  const int32 Token = StartManeuverOp(EManeuverOp::Begin, FString());
  FS08GraphqlClient::FResult OnDone =
      [this, GameId, Gen, Token](bool bOk, const TArray<FS08GraphQLError>& Errors,
                                 TSharedPtr<FJsonObject>, const FString& RawBody) {
        // Stale answer for a left/replaced match: drop BEFORE the in-flight
        // clear - the flag now belongs to the CURRENT match's command.
        if (!IsSameMatchRequest(GameId, Gen)) {
          Trace(FString::Printf(TEXT("MANEUVER begin stale answer room=%s ignored"),
                                *GameId));
          return;
        }
        // MS-E-90 / MS-E-89: a snapshot or the deadline settled the command
        // first - the late answer changes no gate and shows no error; a late
        // SUCCESS body is still merged (it carries the decks the WS omits).
        if (!TakeManeuverOpAnswer(Token, EManeuverOp::Begin, bOk)) {
          if (bOk) MergeLateManeuverAnswer(RawBody, TEXT("beginManeuver"));
          return;
        }
        if (!bOk) {
          if (IsAuthError(Errors) && !bSessionExpired) {
            // P2(5): 401 ANSWERED the command (definitely not applied):
            // refresh once, then converge through the authoritative read -
            // the command itself is never replayed.
            Trace(TEXT("MANEUVER begin auth rejected - refreshing; the command is not resent"));
            if (TryRefreshAuth()) {
              NotifyAuthRefreshed(ES08RejectOp::Begin);
              return;
            }
            if (bSessionExpired) return;
          }
          if (IsOutcomeUnknown(Errors)) {
            // GD-037: the command MAY have been applied - never resend it;
            // the locked recovery refetch converges on the server truth.
            EnterMutationRecovery(TEXT("MANEUVER begin failed: outcome unknown"), FString());
            return;
          }
          Trace(TEXT("MANEUVER begin failed: ") +
                (Errors.Num() ? Errors[0].Message : TEXT("?")));
          // MS-T-06: classified by 02 §1.1; never re-sent automatically
          // (STATE_CHANGED -> refetch only, MS-E-50).
          HandleRejection(Errors, ES08RejectOp::Begin, {});
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
          HandleMutationParseFailure(TEXT("MANEUVER begin"), FString());
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
  FHttpRequestPtr Request = SendHttp(BeginManeuverMutation, Variables, MoveTemp(OnDone));
  // A harness answer may have closed the command synchronously.
  if (InFlightOp != EManeuverOp::None && InFlightToken == Token) InFlightRequest = Request;
  return true;
}

bool FS08FlowController::SubmitManeuver(const FString& ManeuverId,
                                        const TArray<FS08ManeuverMove>& Moves,
                                        const FString& BoostCardId) {
  // Maneuver completion happens on the mover's own turn; the gate's
  // bManeuverInFlight check also blocks a double-Enter from firing two
  // maneuver() legs against the same pending id (the second would fail).
  FString Reason;
  if (!CanIssueGameplayCommand(Reason)) {
    Trace(TEXT("MANEUVER submit blocked: ") + Reason);
    return false;
  }
  // ACC-006: zero moves is a legal maneuver completion (draw + no movement).
  if (ManeuverId.IsEmpty()) {
    Trace(TEXT("MANEUVER submit blocked: no pending maneuver"));
    return false;
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Variables->SetStringField(TEXT("maneuverId"), ManeuverId);
  TArray<TSharedPtr<FJsonValue>> MoveValues;
  int32 ZeroLength = 0;
  for (const FS08ManeuverMove& Move : Moves) {
    // MS-R-44 (B-01): "stay" is no entry in moves[] - an empty path would
    // fail the whole maneuver with EMPTY_PATH.
    if (Move.Path.IsEmpty()) {
      ++ZeroLength;
      continue;
    }
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
  if (ZeroLength > 0) {
    Trace(FString::Printf(TEXT("MANEUVER zero-length moves dropped=%d sent=%d (MS-R-44)"), ZeroLength,
                          MoveValues.Num()));
  }
  if (BoostCardId.IsEmpty()) {
    Variables->SetField(TEXT("boostCardId"), MakeShared<FJsonValueNull>());
  } else {
    Variables->SetStringField(TEXT("boostCardId"), BoostCardId);
  }
  const FString GameId = Room.GameId;
  const int32 Gen = MatchGeneration;
  // PATH_BLOCKED_BY_ENEMY on an end cell is why.cell.enemy (02 §1.1).
  TArray<FIntPoint> Destinations;
  for (const FS08ManeuverMove& Move : Moves) {
    if (!Move.Path.IsEmpty()) Destinations.Add(Move.Path.Last());
  }
  const int32 Token = StartManeuverOp(EManeuverOp::Maneuver, ManeuverId);
  FS08GraphqlClient::FResult OnDone =
      [this, GameId, Gen, BoostCardId, Token, Destinations](bool bOk, const TArray<FS08GraphQLError>& Errors,
                                                            TSharedPtr<FJsonObject>, const FString& RawBody) {
        if (!IsSameMatchRequest(GameId, Gen)) {
          Trace(FString::Printf(TEXT("MANEUVER stale answer room=%s ignored"), *GameId));
          return;
        }
        if (!TakeManeuverOpAnswer(Token, EManeuverOp::Maneuver, bOk)) {
          if (bOk) MergeLateManeuverAnswer(RawBody, TEXT("maneuver"));
          return;
        }
        if (!bOk) {
          if (IsAuthError(Errors) && !bSessionExpired) {
            Trace(TEXT("MANEUVER auth rejected - refreshing; the command is not resent"));
            if (TryRefreshAuth()) {
              // MS-E-92: the draft stays; the player confirms again.
              NotifyAuthRefreshed(ES08RejectOp::Maneuver);
              return;
            }
            if (bSessionExpired) return;
          }
          if (IsOutcomeUnknown(Errors)) {
            // GD-037: the command MAY have been applied - never resend it;
            // the locked recovery refetch converges on the server truth.
            EnterMutationRecovery(TEXT("MANEUVER failed: outcome unknown"), FString());
            return;
          }
          Trace(TEXT("MANEUVER failed: ") +
                (Errors.Num() ? Errors[0].Message : TEXT("?")));
          HandleRejection(Errors, ES08RejectOp::Maneuver, Destinations);
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
          HandleMutationParseFailure(TEXT("MANEUVER"), FString());
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
  FHttpRequestPtr Request = SendHttp(ManeuverMutation, Variables, MoveTemp(OnDone));
  if (InFlightOp != EManeuverOp::None && InFlightToken == Token) InFlightRequest = Request;
  return true;
}

// ---- MS-T-06: the maneuver command in flight (move-selection 04 §5) ----------

const TCHAR* FS08FlowController::ManeuverOpName(EManeuverOp Op) {
  switch (Op) {
    case EManeuverOp::Begin: return TEXT("begin");
    case EManeuverOp::Maneuver: return TEXT("maneuver");
    default: return TEXT("none");
  }
}

int32 FS08FlowController::StartManeuverOp(EManeuverOp Op, const FString& ManeuverId) {
  bManeuverInFlight = true;
  InFlightOp = Op;
  InFlightToken = ++NextCommandToken;
  InFlightAge = 0.0f;
  bInFlightSlow = false;
  InFlightBaseSeq = SeqGuard.Local;
  InFlightManeuverId = ManeuverId;
  InFlightRequest.Reset();
  return InFlightToken;
}

void FS08FlowController::EndManeuverOp() {
  if (InFlightOp != EManeuverOp::None) bManeuverInFlight = false;
  InFlightOp = EManeuverOp::None;
  InFlightToken = 0;
  InFlightAge = 0.0f;
  bInFlightSlow = false;
  InFlightManeuverId.Reset();
  InFlightRequest.Reset();
}

bool FS08FlowController::TakeManeuverOpAnswer(int32 Token, EManeuverOp Op, bool bOk) {
  if (InFlightOp != EManeuverOp::None && Token == InFlightToken) {
    EndManeuverOp();
    return true;
  }
  const FString* Why = RetiredCommandTokens.Find(Token);
  Trace(FString::Printf(TEXT("MS-NET late-reply op=%s ok=%d settled=%s"), ManeuverOpName(Op), bOk ? 1 : 0,
                        Why ? **Why : TEXT("unknown")));
  RetiredCommandTokens.Remove(Token);
  return false;
}

void FS08FlowController::MergeLateManeuverAnswer(const FString& RawBody, const TCHAR* Field) {
  // The WS events omit decks (S08GraphqlWs): the HTTP body is their only fresh
  // source after the own begin / maneuver. Through the seq guard a same-seq
  // body merges without cues; a newer one applies (e.g. after the deadline the
  // recovery lock releases on it - it IS the outcome).
  FS08Snapshot Snapshot;
  FS08GraphQLError Error;
  if (!FS08Contracts::ParseMutationResult(RawBody, Field, Snapshot, Error)) return;
  const ES08SeqDecision Decision = ApplyMatchSnapshot(Snapshot);
  Trace(FString::Printf(TEXT("MS-NET late-reply merged seq=%d (%s)"), Snapshot.SequenceNumber,
                        Decision == ES08SeqDecision::Apply   ? TEXT("apply")
                        : Decision == ES08SeqDecision::Merge ? TEXT("merge")
                                                             : TEXT("ignore")));
}

void FS08FlowController::TickCommandDeadline(float DeltaSeconds) {
  if (InFlightOp == EManeuverOp::None) return;
  if (bSessionExpired || Stage != ES08Stage::Started || IsRoomAborted() || IsRoomTerminal()) {
    // The match or the session is gone: no clock may lock what follows.
    EndManeuverOp();
    return;
  }
  InFlightAge += DeltaSeconds;
  const EManeuverOp Op = InFlightOp;
  if (!bInFlightSlow && InFlightAge >= CommandSlowSeconds) {
    bInFlightSlow = true;
    Trace(FString::Printf(TEXT("MS-NET slow op=%s after=%.0fs why=why.syncing"), ManeuverOpName(Op),
                          CommandSlowSeconds));
  }
  if (InFlightAge < CommandDeadlineSeconds) return;
  // MS-E-89: no answer in 10 s - the request is cancelled and its outcome is
  // unknown (the server may have applied it): recovery lock, never a resend.
  Trace(FString::Printf(TEXT("MS-NET deadline op=%s after=%.0fs - request cancelled, outcome unknown"),
                        ManeuverOpName(Op), CommandDeadlineSeconds));
  const FHttpRequestPtr Request = InFlightRequest;
  if (RetiredCommandTokens.Num() >= 64) RetiredCommandTokens.Reset();
  RetiredCommandTokens.Add(InFlightToken, TEXT("deadline"));
  EndManeuverOp();
  EnterMutationRecovery(FString::Printf(TEXT("MANEUVER %s deadline %.0fs"), ManeuverOpName(Op),
                                        CommandDeadlineSeconds),
                        FString());
  // Its completion (if the HTTP module reports one) is a late reply.
  if (Request.IsValid()) Request->CancelRequest();
}

void FS08FlowController::ReleaseManeuverGateBySnapshot(const FS08Snapshot& Snapshot) {
  if (InFlightOp == EManeuverOp::None || Snapshot.SequenceNumber <= InFlightBaseSeq) return;
  // The proof must be in THIS body: a partial WS body keeps stale metadata in
  // the applied store (merge semantics) and proves nothing.
  const TSharedPtr<FJsonObject> Meta =
      Snapshot.Metadata.IsValid() ? Snapshot.Metadata->AsObject() : TSharedPtr<FJsonObject>();
  if (!Meta.IsValid()) return;
  FString PendingId;
  FString PendingPlayer;
  const TSharedPtr<FJsonObject>* Pending = nullptr;
  if (Meta->TryGetObjectField(TEXT("pendingManeuver"), Pending) && Pending && Pending->IsValid()) {
    (*Pending)->TryGetStringField(TEXT("id"), PendingId);
    (*Pending)->TryGetStringField(TEXT("playerId"), PendingPlayer);
  }
  const bool bSettled =
      InFlightOp == EManeuverOp::Begin
          ? !PendingId.IsEmpty() && PendingPlayer.Equals(UserId, ESearchCase::CaseSensitive)
          : !PendingId.Equals(InFlightManeuverId, ESearchCase::CaseSensitive);
  if (!bSettled) return;
  Trace(FString::Printf(TEXT("MS-NET gate released by snapshot op=%s seq=%d (before the HTTP answer)"),
                        ManeuverOpName(InFlightOp), Snapshot.SequenceNumber));
  if (RetiredCommandTokens.Num() >= 64) RetiredCommandTokens.Reset();
  RetiredCommandTokens.Add(InFlightToken, TEXT("snapshot"));
  EndManeuverOp();
}

void FS08FlowController::HandleRejection(const TArray<FS08GraphQLError>& Errors, ES08RejectOp Op,
                                         const TArray<FIntPoint>& Destinations) {
  if (bSessionExpired) return; // the login screen owns the flow; a refetch would fail
  const FS08Rejection Rejection = FS08RuleCodes::Classify(Errors, Op, Destinations);
  Trace(FString::Printf(TEXT("MS-REJECT code=%s why=%s class=%s op=%s"),
                        Rejection.RuleCode.IsEmpty() ? TEXT("-") : *Rejection.RuleCode,
                        *Rejection.WhyKey.ToString(), Rejection.ClassLetter(), FS08Rejection::OpName(Op)));
  OnRejection.Broadcast(Rejection);
  if (Rejection.bRefetch) {
    // 02 §1.1: both classes re-read the authoritative snapshot (И: the draft
    // is re-checked on it; С: it is rebuilt or closed). Never a resend.
    Trace(TEXT("MS-REJECT refetch: re-reading the authoritative snapshot (no resend)"));
    FetchGameState();
  }
}

void FS08FlowController::NotifyAuthRefreshed(ES08RejectOp Op) {
  FS08Rejection Rejection;
  Rejection.Op = Op;
  Rejection.RuleCode = TEXT("AUTH");
  Rejection.WhyKey = FName(TEXT("why.auth.refreshed"));
  Rejection.Class = ES08RejectClass::Fixable;
  Rejection.bRefetch = false;
  Trace(FString::Printf(TEXT("MS-REJECT code=AUTH why=why.auth.refreshed class=%s op=%s (not resent)"),
                        Rejection.ClassLetter(), FS08Rejection::OpName(Op)));
  OnRejection.Broadcast(Rejection);
}

FName FS08FlowController::GameplayGateKey() const {
  FString Reason;
  if (CanIssueGameplayCommand(Reason)) return NAME_None;
  if ((Stage == ES08Stage::Started && IsRoomAborted()) || IsRoomTerminal() ||
      Applied.Phase == TEXT("GAME_OVER")) {
    return FName(TEXT("why.state.changed"));
  }
  if (!IsInputBlocked() && Stage == ES08Stage::Started && IsStreamReady() && !bMutationRecoveryActive &&
      !IsMyTurn()) {
    return FName(TEXT("why.not.your.turn"));
  }
  return FName(TEXT("why.syncing"));
}

void FS08FlowController::StoreManeuverDraft(const FS08ManeuverDraftCache& Draft) {
  if (Draft.IsEmpty()) {
    ManeuverDraftCache = FS08ManeuverDraftCache();
    return;
  }
  ManeuverDraftCache = Draft;
  ManeuverDraftCache.GameId = Room.GameId;
  ManeuverDraftCache.UserId = UserId;
}

bool FS08FlowController::RecallManeuverDraft(const FString& ManeuverId, FS08ManeuverDraftCache& OutDraft) const {
  if (ManeuverDraftCache.IsEmpty() || ManeuverId.IsEmpty() || Room.GameId.IsEmpty() ||
      !ManeuverDraftCache.ManeuverId.Equals(ManeuverId, ESearchCase::CaseSensitive) ||
      !ManeuverDraftCache.GameId.Equals(Room.GameId, ESearchCase::CaseSensitive) ||
      !ManeuverDraftCache.UserId.Equals(UserId, ESearchCase::CaseSensitive)) {
    return false;
  }
  OutDraft = ManeuverDraftCache;
  return true;
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

bool FS08FlowController::EndTurn() {
  FString Reason;
  if (!CanIssueEndTurn(Reason)) {
    Trace(TEXT("ENDTURN blocked: ") + Reason);
    return false;
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
          if (IsAuthError(Errors) && !bSessionExpired) {
            Trace(TEXT("ENDTURN auth rejected - refreshing; the command is not resent"));
            if (TryRefreshAuth()) return;
            if (bSessionExpired) return;
          }
          if (IsOutcomeUnknown(Errors)) {
            // GD-037: the command MAY have been applied - never resend it;
            // the locked recovery refetch converges on the server truth.
            EnterMutationRecovery(TEXT("ENDTURN failed: outcome unknown"), FString());
            return;
          }
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
          HandleMutationParseFailure(TEXT("ENDTURN"), FString());
          return;
        }
        ApplyMatchSnapshot(Snapshot);
        Trace(FString::Printf(TEXT("ENDTURN done seq=%d phase=%s"),
                              Snapshot.SequenceNumber, *Snapshot.Phase));
      };
SendHttp(EndTurnMutation, Variables, MoveTemp(OnDone));
  return true;
}

bool FS08FlowController::DiscardToLimit(const FString& PendingId,
                                        const TArray<FString>& CardInstanceIds) {
  // No-turn-owner gate (like the combat commands): the TURN_END discard can
  // open after the turn already flipped to the opponent, so IsMyTurn() must
  // NOT gate it - but started/valid-critical-fields/in-flight still apply.
  // The in-flight check blocks a double-Enter: two discardToLimit legs with
  // the SAME pending id would race and the second fails spuriously.
  FString Reason;
  if (!CanIssueCombatCommand(Reason)) {
    Trace(TEXT("DISCARD blocked: ") + Reason);
    return false;
  }
  if (PendingId.IsEmpty() || CardInstanceIds.IsEmpty()) {
    Trace(TEXT("DISCARD blocked: no pending choice or no cards"));
    return false;
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
      [this, GameId, Gen, Count, PendingId](bool bOk, const TArray<FS08GraphQLError>& Errors,
                                 TSharedPtr<FJsonObject>, const FString& RawBody) {
        if (!IsSameMatchRequest(GameId, Gen)) {
          Trace(FString::Printf(TEXT("DISCARD stale answer room=%s ignored"), *GameId));
          return;
        }
        bManeuverInFlight = false;
        if (!bOk) {
          if (IsAuthError(Errors) && !bSessionExpired) {
            Trace(TEXT("DISCARD auth rejected - refreshing; the command is not resent"));
            if (TryRefreshAuth()) return;
            if (bSessionExpired) return;
          }
          if (IsOutcomeUnknown(Errors)) {
            // GD-037: the command MAY have been applied - never resend it;
            // the locked recovery refetch converges on the server truth.
            // P2(8): the lock holds until THIS discard choice settles.
            EnterMutationRecovery(TEXT("DISCARD failed: outcome unknown"), PendingId,
                                  /*bPendingIsDiscard=*/true);
            return;
          }
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
          HandleMutationParseFailure(TEXT("DISCARD"), PendingId, /*bPendingIsDiscard=*/true);
          return;
        }
        ApplyMatchSnapshot(Snapshot);
        Trace(FString::Printf(TEXT("DISCARD done seq=%d phase=%s count=%d"),
                              Snapshot.SequenceNumber, *Snapshot.Phase, Count));
      };
SendHttp(DiscardToLimitMutation, Variables, MoveTemp(OnDone));
  return true;
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

bool FS08FlowController::RunCombatMutation(const FString& Tag, const TCHAR* Field,
                                           const FString& Mutation,
                                           const TSharedRef<FJsonObject>& Variables,
                                           const FString& PendingChoiceId) {
  const FString GameId = Room.GameId;
  const int32 Gen = MatchGeneration;
  bManeuverInFlight = true;
  FS08GraphqlClient::FResult OnDone =
      [this, Tag, Field, GameId, Gen, PendingChoiceId](bool bOk,
                                      const TArray<FS08GraphQLError>& Errors,
                                      TSharedPtr<FJsonObject>, const FString& RawBody) {
        if (!IsSameMatchRequest(GameId, Gen)) {
          Trace(FString::Printf(TEXT("%s stale answer room=%s ignored"), *Tag, *GameId));
          return;
        }
        bManeuverInFlight = false;
        if (!bOk) {
          if (IsAuthError(Errors) && !bSessionExpired) {
            // P2(5): 401 ANSWERED the command (definitely not applied):
            // refresh once, then converge through the authoritative read -
            // the command itself is never replayed.
            Trace(Tag + TEXT(" auth rejected - refreshing; the command is not sent again"));
            // P1(5): definitive rejection - a local draft waiting on this
            // command (S09AUTO AttackDraft) must reset, never park forever.
            OnCommandRejected.Broadcast(Tag, Errors.Num() ? Errors[0].Message : FString());
            if (TryRefreshAuth()) return;
            if (bSessionExpired) return;
          }
          if (IsOutcomeUnknown(Errors)) {
            // GD-037: the command MAY have been applied - never resend it;
            // the locked recovery refetch converges on the server truth.
            // P2(8): a pending-head resolve holds until THAT head settles.
            EnterMutationRecovery(Tag + TEXT(" failed: outcome unknown"), PendingChoiceId);
            return;
          }
          Trace(Tag + TEXT(" failed: ") +
                (Errors.Num() ? Errors[0].Message : TEXT("?")));
          // MS-T-06: a pending-choice resolve (MOVE/PLACE codes of 02 §1.1)
          // is classified like a maneuver command.
          if (Tag == TEXT("PEND resolve")) {
            TArray<FIntPoint> Cell;
            if (PendingResolveCell.X >= 0) Cell.Add(PendingResolveCell);
            HandleRejection(Errors, ES08RejectOp::PendingEffect, Cell);
          }
          // Answered GraphQL/4xx rejection: definitely not applied - notify
          // the draft holders, then surface the error as before.
          OnCommandRejected.Broadcast(Tag, Errors.Num() ? Errors[0].Message : FString());
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
          HandleMutationParseFailure(Tag, PendingChoiceId);
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
SendHttp(Mutation, Variables, MoveTemp(OnDone));
  return true;
}

bool FS08FlowController::CanIssueCombatCommand(FString& OutReason) const {
  OutReason.Reset();
  if (Stage == ES08Stage::Started && IsRoomAborted()) {
    OutReason = TEXT("the match was interrupted (room aborted) - gameplay input is disabled");
    return false;
  }
  if (IsRoomTerminal()) {
    OutReason = TEXT("the duel is over - gameplay input is disabled on the result screen");
    return false;
  }
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
  if (!IsStreamReady()) {
    OutReason = TEXT("live stream is reconnecting - commands wait until the state stream is back");
    return false;
  }
  if (bMutationRecoveryActive) {
    OutReason = TEXT("restoring authoritative state after a lost response - commands are locked");
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

bool FS08FlowController::Attack(const FString& AttackerFighterId,
                                const FString& CardInstanceId,
                                const FString& TargetFighterId) {
  FString Reason;
  if (!CanIssueGameplayCommand(Reason)) {
    Trace(TEXT("ATTACK blocked: ") + Reason);
    return false;
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Variables->SetStringField(TEXT("attackerId"), AttackerFighterId);
  Variables->SetStringField(TEXT("cardId"), CardInstanceId);
  Variables->SetStringField(TEXT("targetId"), TargetFighterId);
  return RunCombatMutation(TEXT("ATTACK"), TEXT("attack"), AttackMutation, Variables);
}

bool FS08FlowController::PlayDefense(const FString& CardInstanceId) {
  FString Reason;
  if (!CanIssueCombatCommand(Reason)) {
    Trace(TEXT("DEFENSE blocked: ") + Reason);
    return false;
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Variables->SetStringField(TEXT("cardId"), CardInstanceId);
  return RunCombatMutation(TEXT("DEFENSE"), TEXT("playDefense"), PlayDefenseMutation,
                           Variables);
}

bool FS08FlowController::PlayScheme(const FString& CardInstanceId) {
  FString Reason;
  if (!CanIssueGameplayCommand(Reason)) {
    Trace(TEXT("SCHEME blocked: ") + Reason);
    return false;
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Variables->SetStringField(TEXT("cardId"), CardInstanceId);
  return RunCombatMutation(TEXT("SCHEME"), TEXT("playScheme"), PlaySchemeMutation, Variables);
}

bool FS08FlowController::ResolveCombat() {
  FString Reason;
  if (!CanIssueCombatCommand(Reason)) {
    Trace(TEXT("RESOLVE blocked: ") + Reason);
    return false;
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  return RunCombatMutation(TEXT("RESOLVE"), TEXT("resolveCombat"), ResolveCombatMutation,
                           Variables);
}

bool FS08FlowController::ResolvePendingEffect(
    const FString& EffectId, const FString& FighterId, bool bHasCell, int32 X, int32 Y,
    bool bHasOption, int32 OptionIndex, const TArray<FString>& CardIds) {
  FString Reason;
  if (!CanIssueCombatCommand(Reason)) {
    Trace(TEXT("PEND resolve blocked: ") + Reason);
    return false;
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Variables->SetStringField(TEXT("effectId"), EffectId);
  PendingResolveCell = bHasCell ? FIntPoint(X, Y) : FIntPoint(-1, -1); // MS-T-06: the space a rejection names
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
  return RunCombatMutation(TEXT("PEND resolve"), TEXT("resolvePendingEffect"),
                           ResolvePendingEffectMutation, Variables, EffectId);
}

bool FS08FlowController::DeclinePendingEffect(const FString& EffectId) {
  FString Reason;
  if (!CanIssueCombatCommand(Reason)) {
    Trace(TEXT("PEND decline blocked: ") + Reason);
    return false;
  }
  TSharedRef<FJsonObject> Variables = MakeShared<FJsonObject>();
  Variables->SetStringField(TEXT("gameId"), Room.GameId);
  Variables->SetStringField(TEXT("effectId"), EffectId);
  return RunCombatMutation(TEXT("PEND decline"), TEXT("declinePendingEffect"),
                           DeclinePendingEffectMutation, Variables, EffectId);
}

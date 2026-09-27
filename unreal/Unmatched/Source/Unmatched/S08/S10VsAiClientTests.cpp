// S10 GD-039/040: client VS_AI slice. The server contract (backend
// game.service.ts) is: createGame(mode: VS_AI) opens a LOBBY room with ONE
// human seat; startGame auto-adds the server bot as the second seat and flips
// the row to IN_PROGRESS; a terminal row is FINISHED (verdict lives in the
// GAME_OVER snapshot + winnerId) or ABORTED (interruption, never a verdict);
// leaveGame on a terminal row is accepted and only navigates away. These
// tests pin the client side through the offline HTTP + WS harnesses:
//   1. create VS_AI installs the bot-mode room (visible lobby mode control);
//   2. one-seat start: the host starts alone, the bot seat appears in the
//      startGame echo, live state attaches without a second human and the
//      bot-turn waiting indicator follows the AUTHORITATIVE turn owner;
//   3. a live room row ABORTED (fresh poll - never a snapshot/CUE) disables
//      gameplay input, drops the dead subscription and keeps only leave;
//      the accepted leave returns a clean lobby;
//   4. FINISHED distinguishes itself from ABORTED: an already-applied
//      GAME_OVER snapshot is the result (no refetch), a FINISHED row without
//      one triggers exactly one state refetch that delivers the verdict;
//   5. idempotency: a lost-reply retry keeps the key (same intent - the
//      server redelivers the same room), a create after a resolved intent
//      rotates it (two successive rooms get distinct keys); a create
//      SUPERSEDED by a concurrent join (stale answer or none) rotates too -
//      reusing the key would redeliver the abandoned room (M1);
//   6. a late ABORTED poll answer for a left match cannot abort the newer
//      room (stale-response gate).
#if WITH_AUTOMATION_TESTS

#include "S08Contracts.h"
#include "S08FlowController.h"
#include "S08FlowGameMode.h"
#include "Dom/JsonObject.h"
#include "Misc/AutomationTest.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace {

const TCHAR* HostId = TEXT("p-host");
const TCHAR* BotId = TEXT("ai-bot-user");

FString RoomBody(const FString& Id, const TCHAR* Status, const TCHAR* Mode,
                 const FString& PlayersJson) {
  return FString::Printf(
      TEXT("{\"id\":\"%s\",\"code\":\"C1\",\"status\":\"%s\",\"mode\":\"%s\",")
      TEXT("\"hostId\":\"%s\",\"players\":%s}"),
      *Id, Status, Mode, HostId, *PlayersJson);
}

FString CreateGameBody(const FString& Id, const TCHAR* Mode, const FString& PlayersJson) {
  return TEXT("{\"data\":{\"createGame\":") + RoomBody(Id, TEXT("LOBBY"), Mode, PlayersJson) +
         TEXT("}}");
}

FString StartGameBody(const FString& Id, const TCHAR* Mode, const FString& PlayersJson) {
  return TEXT("{\"data\":{\"startGame\":") + RoomBody(Id, TEXT("IN_PROGRESS"), Mode, PlayersJson) +
         TEXT("}}");
}

FString GameRowBody(const FString& Id, const TCHAR* Status, const TCHAR* Mode,
                    const FString& PlayersJson) {
  return TEXT("{\"data\":{\"game\":") + RoomBody(Id, Status, Mode, PlayersJson) + TEXT("}}");
}

const FString OneHumanSeat =
    TEXT("[{\"userId\":\"p-host\",\"username\":\"host\",\"heroId\":\"h1\",\"isReady\":true,"
         "\"seatOrder\":0}]");
const FString HumanAndBotSeats =
    TEXT("[{\"userId\":\"p-host\",\"username\":\"host\",\"heroId\":\"h1\",\"isReady\":true,"
         "\"seatOrder\":0},{\"userId\":\"ai-bot-user\",\"username\":\"ai\",\"heroId\":\"h2\","
         "\"isReady\":true,\"seatOrder\":1}]");

/** gameState query body (two-stage contract: `state` is a JSON string).
 *  MetadataJson (optional) rides inside the inner state as the string-encoded
 *  metadata projection (escape backslashes first, then quotes). */
FString GameStateBody(int32 Seq, const TCHAR* Phase, const TCHAR* TurnPlayer,
                      const TCHAR* MetadataJson = nullptr) {
  FString MetadataField;
  if (MetadataJson) {
    const FString EscapedMeta = FString(MetadataJson)
                                    .Replace(TEXT("\\"), TEXT("\\\\"))
                                    .Replace(TEXT("\""), TEXT("\\\""));
    MetadataField = TEXT(",\"metadata\":\"") + EscapedMeta + TEXT("\"");
  }
  const FString Inner = FString::Printf(
      TEXT("{\"players\":[{\"userId\":\"p-host\"},{\"userId\":\"%s\"}],")
      TEXT("\"fighters\":[{\"id\":\"f1\",\"health\":10,\"position\":{\"x\":2,\"y\":2}},")
      TEXT("{\"id\":\"f2\",\"health\":10,\"position\":{\"x\":0,\"y\":0}}],")
      TEXT("\"handZones\":{\"p-host\":[],\"%s\":[]},")
      TEXT("\"boardState\":{\"cells\":[[0,0],[1,0]]}%s}"),
      BotId, BotId, *MetadataField);
  const FString Escaped = Inner.Replace(TEXT("\\"), TEXT("\\\\"))
                               .Replace(TEXT("\""), TEXT("\\\""));
  return FString::Printf(
      TEXT("{\"data\":{\"gameState\":{\"id\":\"gs\",\"gameId\":\"g1\",\"state\":\"%s\",")
      TEXT("\"sequenceNumber\":%d,\"phase\":\"%s\",\"turnCount\":1,")
      TEXT("\"currentTurnPlayerId\":\"%s\",\"updatedAt\":0}}}"),
      *Escaped, Seq, Phase, TurnPlayer);
}

/** Raw graphql-transport-ws 'next' frame carrying one gameStateUpdated event
 *  (projections as embedded JSON strings - two-stage contract). */
FString WsNextFrame(const FString& OpId, int32 Seq, const TCHAR* Phase,
                    const TCHAR* TurnPlayer) {
  TSharedRef<FJsonObject> Frame = MakeShared<FJsonObject>();
  Frame->SetStringField(TEXT("type"), TEXT("next"));
  Frame->SetStringField(TEXT("id"), OpId);
  TSharedRef<FJsonObject> Payload = MakeShared<FJsonObject>();
  TSharedRef<FJsonObject> Data = MakeShared<FJsonObject>();
  TSharedRef<FJsonObject> Event = MakeShared<FJsonObject>();
  Event->SetNumberField(TEXT("sequenceNumber"), Seq);
  Event->SetStringField(TEXT("phase"), Phase);
  Event->SetNumberField(TEXT("turnCount"), 1);
  Event->SetStringField(TEXT("currentTurnPlayerId"), TurnPlayer);
  Event->SetStringField(
      TEXT("players"),
      FString::Printf(TEXT("[{\"userId\":\"p-host\"},{\"userId\":\"%s\"}]"), BotId));
  Event->SetStringField(
      TEXT("fighters"),
      TEXT("[{\"id\":\"f1\",\"health\":10,\"position\":{\"x\":2,\"y\":2}},")
      TEXT("{\"id\":\"f2\",\"health\":10,\"position\":{\"x\":0,\"y\":0}}]"));
  Event->SetStringField(
      TEXT("handZones"),
      FString::Printf(TEXT("{\"p-host\":[],\"%s\":[]}"), BotId));
  // boardState keeps ValidateCriticalFields quiet: a WS frame without it
  // leaves the input gate closed (IsInputBlocked) and gates a dispatched
  // command off before the test can arm the recovery path.
  Event->SetStringField(
      TEXT("boardState"),
      TEXT("{\"cells\":[[0,0],[1,0]]}"));
  Data->SetObjectField(TEXT("gameStateUpdated"), Event);
  Payload->SetObjectField(TEXT("data"), Data);
  Frame->SetObjectField(TEXT("payload"), Payload);
  FString Out;
  auto Writer = TJsonWriterFactory<>::Create(&Out);
  FJsonSerializer::Serialize(Frame, Writer);
  return Out;
}

/** In-memory snapshot with full valid projections (ApplySnapshot path). */
FS08Snapshot MakeSnap(int32 Seq, const TCHAR* Phase, const TCHAR* TurnPlayer) {
  FS08Snapshot S;
  S.SequenceNumber = Seq;
  S.Phase = Phase;
  S.TurnCount = 1;
  S.CurrentTurnPlayerId = TurnPlayer;
  FString Problem;
  FS08Contracts::TryParseJsonValue(
      FString::Printf(TEXT("[{\"userId\":\"p-host\"},{\"userId\":\"%s\"}]"), BotId), S.Players,
      Problem);
  FS08Contracts::TryParseJsonValue(
      TEXT("[{\"id\":\"f1\",\"health\":10,\"position\":{\"x\":2,\"y\":2}},")
      TEXT("{\"id\":\"f2\",\"health\":10,\"position\":{\"x\":0,\"y\":0}}]"),
      S.Fighters, Problem);
  FS08Contracts::TryParseJsonValue(
      FString::Printf(TEXT("{\"p-host\":[],\"%s\":[]}"), BotId), S.HandZones, Problem);
  FS08Contracts::TryParseJsonValue(TEXT("{\"cells\":[[0,0],[1,0]]}"), S.BoardState, Problem);
  return S;
}

struct FVsAiCapture {
  TArray<FString> Traces;
  void Bind(FS08FlowController& Flow) {
    Flow.OnTrace.AddLambda([this](const FString& Line) { Traces.Add(Line); });
  }
  bool SawTrace(const TCHAR* Needle) const {
    for (const FString& Line : Traces) {
      if (Line.Contains(Needle)) return true;
    }
    return false;
  }
};

} // namespace

// ---- 1. mode control: create VS_AI installs the bot-mode room --------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10VsAiCreateModeTest,
    "Unmatched.S10.VsAiClient.create VS_AI installs bot-mode room from the lobby mode control",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10VsAiCreateModeTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), HostId);
  Flow.QueueHttpResultForTest(true, {}, false,
                              CreateGameBody(TEXT("g-1"), TEXT("VS_AI"), OneHumanSeat));
  Flow.CreateRoom(TEXT("VS_AI"));
  TestTrue("room installed", Flow.GetRoom().GameId == TEXT("g-1"));
  TestTrue("room mode is VS_AI (bot mode from room metadata)",
           Flow.GetRoom().Mode == TEXT("VS_AI"));
  TestTrue("IsVsAiRoom follows the room row", Flow.IsVsAiRoom());
  TestTrue("one human seat only", Flow.GetRoom().Players.Num() == 1);
  TestTrue("stage room", Flow.GetStage() == ES08Stage::Room);

  // Contrast: the default PvP control path stays a ONE_V_ONE room.
  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  TestTrue("left to lobby", Flow.GetStage() == ES08Stage::Lobby);
  Flow.QueueHttpResultForTest(true, {}, false,
                              CreateGameBody(TEXT("g-2"), TEXT("ONE_V_ONE"), OneHumanSeat));
  Flow.CreateRoom(TEXT("ONE_V_ONE"));
  TestFalse("pvp room is not VS_AI", Flow.IsVsAiRoom());
  return true;
}

// ---- 2. one-seat start + authoritative bot-turn indicator -------------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10VsAiOneSeatStartTest,
    "Unmatched.S10.VsAiClient.one human seat starts VS_AI; bot seat appears and the waiting "
    "indicator follows the authoritative turn owner",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10VsAiOneSeatStartTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), HostId);
  Flow.QueueHttpResultForTest(true, {}, false,
                              CreateGameBody(TEXT("g-1"), TEXT("VS_AI"), OneHumanSeat));
  Flow.CreateRoom(TEXT("VS_AI"));
  TestTrue("one human seat in the lobby", Flow.GetRoom().Players.Num() == 1);

  // Harness socket first, then the REAL host stage: the startGame answer
  // lands while Stage == Room (SetRoomForTest mirrors the pre-start stage),
  // so the attach must come from HandleRoomResponse's Room -> IN_PROGRESS
  // branch - exactly the live host path. A duplicate second attach (the old
  // StartGame OnDone branch) would issue a second gameState fetch (4 sends).
  Flow.AttachStreamHarnessForTest(TEXT("g-1"));
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);

  // The host starts ALONE: the startGame echo carries the bot seat and
  // IN_PROGRESS - the client never waits for a second human.
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true,
                              StartGameBody(TEXT("g-1"), TEXT("VS_AI"), HumanAndBotSeats));
  // The attach's NESTED FetchGameState() send inside the delivery callback
  // must consume this queued answer - an unqueued send would hit the network
  // and its late callback would deref this stack Flow after destruction.
  Flow.QueueHttpResultForTest(true, {}, false,
                              GameStateBody(9, TEXT("ACTION_MANEUVER"), HostId));
  Flow.StartGame();
  Flow.DeliverQueuedHttpForTest();

  TestTrue("started", Flow.GetStage() == ES08Stage::Started);
  TestEqual("live state attached from the queued gameState (no real send)",
            Flow.GetAppliedSnapshot().SequenceNumber, 9);
  TestEqual("create + startGame + ONE gameState fetch (no duplicate attach)",
            Flow.GetTestHttpSendCountForTest(), 3);
  TestEqual("bot seat present after start", Flow.GetRoom().Players.Num(), 2);
  TestTrue("room still VS_AI", Flow.IsVsAiRoom());
  TestTrue("room row in progress", Flow.GetRoom().Status == TEXT("IN_PROGRESS"));

  // The waiting indicator follows the AUTHORITATIVE turn owner (applied
  // snapshot), never a fixed timer: bot turn -> on, human turn -> off,
  // terminal phase -> off regardless of the owner.
  Flow.InjectWsFrameForTest(WsNextFrame(TEXT("s08-1"), 10, TEXT("ACTION_MANEUVER"), BotId));
  TestTrue("bot holds the turn -> waiting indicator on", Flow.IsBotActing());
  TestTrue("live room polls while started", Flow.WantsPolling());

  Flow.InjectWsFrameForTest(WsNextFrame(TEXT("s08-1"), 11, TEXT("ACTION_MANEUVER"), HostId));
  TestFalse("indicator off on the human turn", Flow.IsBotActing());

  Flow.InjectWsFrameForTest(WsNextFrame(TEXT("s08-1"), 12, TEXT("GAME_OVER"), BotId));
  TestFalse("indicator off on GAME_OVER", Flow.IsBotActing());
  return true;
}

// ---- 3. live ABORTED: disable input, keep leave, clean lobby ----------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10VsAiAbortedRoomTest,
    "Unmatched.S10.VsAiClient.aborted live room disables input and leaves to a clean lobby",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10VsAiAbortedRoomTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), HostId);
  FVsAiCapture Cap;
  Cap.Bind(Flow);
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Started);
  Flow.AttachStreamHarnessForTest(TEXT("g-1"));
  Flow.InjectWsFrameForTest(WsNextFrame(TEXT("s08-1"), 10, TEXT("ACTION_MANEUVER"), HostId));
  TestTrue("baseline live", Flow.HasGameStateOpForTest());

  // A stale snapshot (e.g. a replayed old body) must NEVER install an abort:
  // only a fresh room row can.
  Flow.ApplySnapshot(MakeSnap(9, TEXT("ACTION_MANEUVER"), BotId));
  TestFalse("no abort inferred from snapshots", Flow.IsRoomAborted());

  // Poll ladder: IN_PROGRESS keeps polling; the ABORTED row stops it.
  Flow.QueueHttpResultForTest(true, {}, false,
                              GameRowBody(TEXT("g-1"), TEXT("IN_PROGRESS"), TEXT("VS_AI"),
                                          HumanAndBotSeats));
  Flow.PollRoom();
  TestTrue("in_progress row keeps polling", Flow.WantsPolling());

  Flow.QueueHttpResultForTest(true, {}, false,
                              GameRowBody(TEXT("g-1"), TEXT("ABORTED"), TEXT("VS_AI"),
                                          HumanAndBotSeats));
  Flow.PollRoom();
  TestTrue("room row proved the interruption", Flow.IsRoomAborted());
  TestTrue("terminal", Flow.IsRoomTerminal());
  TestFalse("polling stops once terminal", Flow.WantsPolling());
  TestFalse("dead subscription dropped", Flow.HasGameStateOpForTest());
  TestTrue("abort traced", Cap.SawTrace(TEXT("aborted")));

  FString Reason;
  TestFalse("gameplay gate closed", Flow.CanIssueGameplayCommand(Reason));
  TestTrue("gate names the interruption",
           Reason.Contains(TEXT("interrupted")) && Reason.Contains(TEXT("aborted")));
  TestFalse("combat gate closed too", Flow.CanIssueCombatCommand(Reason));
  TestFalse("bot indicator off after abort", Flow.IsBotActing());

  // Leave stays available; the accepted leave returns a CLEAN lobby.
  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  TestTrue("clean lobby", Flow.GetStage() == ES08Stage::Lobby);
  TestTrue("room cleared", Flow.GetRoom().GameId.IsEmpty());
  TestFalse("not terminal after leave", Flow.IsRoomTerminal());
  return true;
}

// ---- 4a. FINISHED after an applied GAME_OVER: no refetch, gate closed ------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10VsAiFinishedWithGameOverTest,
    "Unmatched.S10.VsAiClient.finished row after applied GAME_OVER does not refetch",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10VsAiFinishedWithGameOverTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), HostId);
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Started);
  Flow.AttachStreamHarnessForTest(TEXT("g-1"));
  Flow.ApplySnapshot(MakeSnap(11, TEXT("GAME_OVER"), HostId));
  TestEqual("verdict snapshot applied", Flow.GetAppliedSnapshot().SequenceNumber, 11);

  const int32 SendsBefore = Flow.GetTestHttpSendCountForTest();
  Flow.QueueHttpResultForTest(true, {}, false,
                              GameRowBody(TEXT("g-1"), TEXT("FINISHED"), TEXT("VS_AI"),
                                          HumanAndBotSeats));
  Flow.PollRoom();
  TestTrue("finished, not aborted", Flow.IsRoomTerminal() && !Flow.IsRoomAborted());
  // +1 = the poll itself; the verdict snapshot was already applied, so the
  // terminal branch must NOT have issued a state refetch.
  TestEqual("no refetch - GAME_OVER already applied",
            Flow.GetTestHttpSendCountForTest(), SendsBefore + 1);

  FString Reason;
  TestFalse("gameplay gate closed on the result", Flow.CanIssueGameplayCommand(Reason));
  TestTrue("gate names the result screen", Reason.Contains(TEXT("duel is over")));
  TestFalse("polling stops once terminal", Flow.WantsPolling());
  return true;
}

// ---- 4b. FINISHED without a GAME_OVER body: one refetch delivers it --------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10VsAiFinishedRefetchTest,
    "Unmatched.S10.VsAiClient.finished row without GAME_OVER body triggers one state refetch",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10VsAiFinishedRefetchTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), HostId);
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Started);
  Flow.AttachStreamHarnessForTest(TEXT("g-1"));
  Flow.ApplySnapshot(MakeSnap(10, TEXT("ACTION_MANEUVER"), HostId));

  // FIFO: the poll answer, then the state refetch the terminal branch issues.
  Flow.QueueHttpResultForTest(true, {}, false,
                              GameRowBody(TEXT("g-1"), TEXT("FINISHED"), TEXT("VS_AI"),
                                          HumanAndBotSeats));
  Flow.QueueHttpResultForTest(true, {}, false,
                              GameStateBody(12, TEXT("GAME_OVER"), HostId,
                                            TEXT("{\"winnerId\":\"p-host\"}")));
  // Before the poll: the pre-terminal store holds no winner at all (the
  // baseline MakeSnap carries no metadata) - the verdict below can only come
  // from the refetch body, never from a pre-existing local value.
  TestTrue("no winner in the pre-terminal store",
           !Flow.GetAppliedSnapshot().Metadata.IsValid() ||
               Flow.GetAppliedSnapshot().Metadata->AsObject()->GetStringField(
                   TEXT("winnerId")).IsEmpty());
  Flow.PollRoom();

  TestTrue("finished installed", Flow.IsRoomTerminal() && !Flow.IsRoomAborted());
  TestTrue("verdict snapshot delivered by the refetch",
           Flow.GetAppliedSnapshot().Phase == TEXT("GAME_OVER"));
  TestEqual("refetch applied the terminal seq", Flow.GetAppliedSnapshot().SequenceNumber, 12);
  // The verdict is the AUTHORITATIVE winner from the refetch body, not merely
  // a terminal phase: the metadata winnerId is the server's exact verdict
  // (the human seat, and specifically NOT the bot - a phase-only check could
  // not tell them apart).
  const TSharedPtr<FJsonObject> Verdict =
      Flow.GetAppliedSnapshot().Metadata.IsValid()
          ? Flow.GetAppliedSnapshot().Metadata->AsObject()
          : nullptr;
  TestTrue("authoritative winnerId present in the applied metadata", Verdict.IsValid());
  if (Verdict.IsValid()) {
    TestEqual("authoritative winner is the human seat",
              Verdict->GetStringField(TEXT("winnerId")), FString(HostId));
    TestFalse("bot not declared the winner",
              Verdict->GetStringField(TEXT("winnerId")) == FString(BotId));
  }
  TestEqual("exactly one poll + one refetch, no extra sends",
            Flow.GetTestHttpSendCountForTest(), 2);

  FString Reason;
  TestFalse("input disabled on the result", Flow.CanIssueGameplayCommand(Reason));
  return true;
}

// ---- 5. idempotency: retry keeps the key, new intent rotates ----------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10VsAiIdempotencyKeyTest,
    "Unmatched.S10.VsAiClient.lost-reply retry keeps the idempotency key; a new create intent "
    "rotates it",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10VsAiIdempotencyKeyTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), HostId);
  const FString Key0 = Flow.GetIdempotencyKeyForTest();
  TestFalse("key initialized", Key0.IsEmpty());

  // Same-intent retry: the create answers are LOST (transport) - every retry
  // must carry the SAME key so the server redelivers the same room.
  TArray<FS08GraphQLError> TransportLost;
  TransportLost.Add(FS08GraphQLError{TEXT("TRANSPORT"), TEXT("no answer"), FString()});
  Flow.QueueHttpResultForTest(false, TransportLost);
  Flow.CreateRoom(TEXT("VS_AI"));
  Flow.QueueHttpResultForTest(false, TransportLost);
  Flow.CreateRoom(TEXT("VS_AI")); // the retry
  TestTrue("retry keeps the key", Flow.GetIdempotencyKeyForTest() == Key0);

  // The retry succeeds: the intent RESOLVED to g-1 - this key is spent.
  Flow.QueueHttpResultForTest(true, {}, false,
                              CreateGameBody(TEXT("g-1"), TEXT("VS_AI"), OneHumanSeat));
  Flow.CreateRoom(TEXT("VS_AI"));
  TestTrue("room resolved", Flow.GetRoom().GameId == TEXT("g-1"));

  // Leave, then a NEW create intent: a fresh key (two successive rooms get
  // distinct ids - the server cannot dedupe the second room into the first).
  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  TestTrue("back to lobby", Flow.GetStage() == ES08Stage::Lobby);
  Flow.QueueHttpResultForTest(true, {}, false,
                              CreateGameBody(TEXT("g-2"), TEXT("VS_AI"), OneHumanSeat));
  Flow.CreateRoom(TEXT("VS_AI"));
  TestTrue("second room installed", Flow.GetRoom().GameId == TEXT("g-2"));
  TestTrue("new intent rotated the key", Flow.GetIdempotencyKeyForTest() != Key0);
  return true;
}

// ---- 5b. M1: a create superseded by a concurrent JOIN rotates its key ------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10VsAiSupersededCreateKeyTest,
    "Unmatched.S10.VsAiClient.a create superseded by a concurrent join (stale answer or none) "
    "rotates the idempotency key for the next intent",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10VsAiSupersededCreateKeyTest::RunTest(const FString&) {
  // One race, two endings, SAME fix: the create answer can never apply once a
  // concurrent JOIN bumped the generation - so a later create is a NEW intent
  // and must NOT reuse the key (the server would redeliver the abandoned room).
  auto RunRace = [this](bool bDeliverStaleAnswer) {
    FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), HostId);
    FVsAiCapture Cap;
    Cap.Bind(Flow);
    const FString Key0 = Flow.GetIdempotencyKeyForTest();

    // The create is dispatched and the server SUCCEEDS - but the answer is
    // held back, so the key's intent looks unresolved.
    Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true,
                                CreateGameBody(TEXT("g-abandoned"), TEXT("VS_AI"), OneHumanSeat));
    Flow.CreateRoom(TEXT("VS_AI"));

    // A concurrent JOIN wins: lookup + joinGame land, g-joined installs and
    // bumps the generation past the create dispatch.
    Flow.QueueHttpResultForTest(true, {}, false,
        TEXT("{\"data\":{\"gameByCode\":") +
        RoomBody(TEXT("g-joined"), TEXT("LOBBY"), TEXT("ONE_V_ONE"), OneHumanSeat) + TEXT("}}"));
    Flow.QueueHttpResultForTest(true, {}, false,
        TEXT("{\"data\":{\"joinGame\":") +
        RoomBody(TEXT("g-joined"), TEXT("LOBBY"), TEXT("ONE_V_ONE"), OneHumanSeat) + TEXT("}}"));
    Flow.JoinRoomByCode(TEXT("C9"));
    TestTrue("join installed its room", Flow.GetRoom().GameId == TEXT("g-joined"));

    if (bDeliverStaleAnswer) {
      Flow.DeliverQueuedHttpForTest(); // the stale successful CREATE answer
      TestTrue("stale create dropped", Cap.SawTrace(TEXT("CREATE stale answer ignored")));
      TestTrue("newer room intact", Flow.GetRoom().GameId == TEXT("g-joined"));
    }
    // else: the CREATE answer never arrives - the superseded key is spent
    // regardless (the dispatch generation no longer matches).

    Flow.QueueHttpResultForTest(true);
    Flow.LeaveRoom();
    TestTrue("back to lobby", Flow.GetStage() == ES08Stage::Lobby);
    Flow.QueueHttpResultForTest(true, {}, false,
                                CreateGameBody(TEXT("g-fresh"), TEXT("VS_AI"), OneHumanSeat));
    Flow.CreateRoom(TEXT("VS_AI"));
    TestTrue("fresh room installed, not the abandoned one",
             Flow.GetRoom().GameId == TEXT("g-fresh"));
    TestTrue("superseded intent rotated the key", Flow.GetIdempotencyKeyForTest() != Key0);
  };

  RunRace(/*bDeliverStaleAnswer=*/true);
  RunRace(/*bDeliverStaleAnswer=*/false);
  return true;
}

// ---- 6. stale terminal answer cannot abort the newer room ------------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10VsAiStaleTerminalAnswerTest,
    "Unmatched.S10.VsAiClient.late aborted poll answer for a left match cannot abort the newer "
    "room",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10VsAiStaleTerminalAnswerTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), HostId);
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Started);
  Flow.AttachStreamHarnessForTest(TEXT("g-1"));

  // The abort poll is dispatched, but its answer lands only after the player
  // left g-1 and created g-2.
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true,
                              GameRowBody(TEXT("g-1"), TEXT("ABORTED"), TEXT("VS_AI"),
                                          HumanAndBotSeats));
  Flow.PollRoom();

  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  TestTrue("left g-1", Flow.GetStage() == ES08Stage::Lobby);

  Flow.QueueHttpResultForTest(true, {}, false,
                              CreateGameBody(TEXT("g-2"), TEXT("VS_AI"), OneHumanSeat));
  Flow.CreateRoom(TEXT("VS_AI"));
  TestTrue("new room g-2", Flow.GetRoom().GameId == TEXT("g-2"));

  Flow.DeliverQueuedHttpForTest(0); // the late ABORTED answer for g-1

  TestTrue("new room not aborted by the stale answer", !Flow.IsRoomAborted());
  TestTrue("new room row intact", Flow.GetRoom().GameId == TEXT("g-2"));
  TestTrue("stage intact", Flow.GetStage() == ES08Stage::Room);
  return true;
}

// ---- 7. authoritative ABORTED cancels armed WS reconnect + recovery --------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10VsAiAbortedCancelsTimersTest,
    "Unmatched.S10.VsAiClient.aborted room cancels the armed WS reconnect and the mutation "
    "recovery ladder - no spurious reconnect or errors",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10VsAiAbortedCancelsTimersTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), HostId);
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Started);
  Flow.AttachStreamHarnessForTest(TEXT("g-1"));
  Flow.InjectWsFrameForTest(WsNextFrame(TEXT("s08-1"), 10, TEXT("ACTION_MANEUVER"), HostId));
  FString Reason;
  TestTrue("input gate open before the interruption",
           Flow.CanIssueGameplayCommand(Reason));

  // A lost attack answer arms the GD-037 recovery ladder (lock + refetch).
  // BOTH answers must be queued up front: the harness delivers the attack
  // failure synchronously, and its EnterMutationRecovery refetch fires while
  // Attack() is still on the stack - an empty FIFO there would fall through
  // to a real network send whose late callback outlives the controller.
  TArray<FS08GraphQLError> TransportLost;
  TransportLost.Add(FS08GraphQLError{TEXT("TRANSPORT"), TEXT("no answer"), FString()});
  Flow.QueueHttpResultForTest(false, TransportLost); // the attack answer
  Flow.QueueHttpResultForTest(false, TransportLost); // the recovery refetch
  TestTrue("attack dispatched", Flow.Attack(TEXT("f1"), TEXT("c1"), TEXT("f2")));
  TestTrue("mutation recovery armed by the unknown outcome",
           Flow.IsAwaitingStateRecovery());

  // A transport loss arms the WS reconnect ladder on top.
  Flow.DropWsForTest();
  TestFalse("stream not ready after the drop", Flow.IsStreamReady());

  // The authoritative ABORTED room row cancels BOTH ladders.
  Flow.QueueHttpResultForTest(true, {}, false,
                              GameRowBody(TEXT("g-1"), TEXT("ABORTED"), TEXT("VS_AI"),
                                          HumanAndBotSeats));
  Flow.PollRoom();
  TestTrue("room aborted", Flow.IsRoomAborted());
  TestTrue("mutation recovery cancelled by the abort",
           !Flow.IsAwaitingStateRecovery());

  // Nothing may fire across any backoff window: no WS recreation (reconnect
  // would resubscribe to the dead room) and no gameState refetch (recovery
  // would hammer and broadcast a dead game's failures).
  const int32 Sends = Flow.GetTestHttpSendCountForTest();
  const int32 WsGen = Flow.GetWsGenerationForTest();
  Flow.TickConnectivity(30.0f);
  Flow.TickConnectivity(30.0f);
  TestEqual("no spurious refetch after the abort", Flow.GetTestHttpSendCountForTest(), Sends);
  TestEqual("no spurious WS recreation after the abort",
            Flow.GetWsGenerationForTest(), WsGen);
  TestTrue("recovery stays cancelled",
           !Flow.IsAwaitingStateRecovery());

  // Leave still works from the interruption screen and returns a clean lobby.
  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  TestTrue("clean lobby after the interrupted match",
           Flow.GetStage() == ES08Stage::Lobby && Flow.GetRoom().GameId.IsEmpty());
  return true;
}

// ---- 8. terminal screens own the keyboard (the L/Enter promise) -------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10VsAiTerminalKeysTest,
    "Unmatched.S10.VsAiClient.aborted and result screens own L/Enter for the lobby return",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10VsAiTerminalKeysTest::RunTest(const FString&) {
  // The interrupted-room screen renders "L or Enter returns you to the lobby"
  // - its key routing must own the keyboard exactly like the result screen,
  // or the keys sink into the gameplay handler (a blocked ConfirmDraft/Enter
  // that never sends the leave).
  TestTrue("aborted room screen owns the keys",
           AS08FlowGameMode::TerminalScreenOwnsKeys(ES08Stage::Started, false, true));
  TestTrue("GAME_OVER result screen owns the keys",
           AS08FlowGameMode::TerminalScreenOwnsKeys(ES08Stage::Started, true, false));
  TestFalse("live gameplay keeps the gameplay bindings",
            AS08FlowGameMode::TerminalScreenOwnsKeys(ES08Stage::Started, false, false));
  // An ABORTED row can only install on a live match; other stages keep their
  // own routing (the lobby panel owns its keys).
  TestFalse("non-started stages never route L to the lobby return",
            AS08FlowGameMode::TerminalScreenOwnsKeys(ES08Stage::Room, false, true));
  return true;
}

// ---- 9. opt-in -S10AbortProof: pure step machine -----------------------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10AbortProofTransitionsTest,
    "Unmatched.S10.VsAiClient.abort proof stays dormant without the opt-in flag and orders screen "
    "shot -> one leave -> lobby shot -> exit",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10AbortProofTransitionsTest::RunTest(const FString&) {
  using EStep = FS10AbortProofTransitions::EStep;
  const auto Armed = [](EStep S, bool bLive, bool bLobby, bool bSettled) {
    return FS10AbortProofTransitions::Advance(
        S, /*bAbortProofEnabled=*/true, bLive, bLobby, bSettled);
  };

  // Opt-in gate: without the flag NOTHING ever advances - even a live
  // interruption with settled evidence stays Idle (no auto path touches the
  // normal UI).
  TestTrue("no flag -> Idle from Idle",
           FS10AbortProofTransitions::Advance(EStep::Idle, false, true, false, true) ==
               EStep::Idle);
  TestTrue("no flag -> Idle from every armed step",
           FS10AbortProofTransitions::Advance(EStep::LeaveOnce, false, true, true, true) ==
               EStep::Idle);

  // Dormant before the interruption: live-match ticks change nothing.
  TestTrue("armed idle stays idle while the match is live",
           Armed(EStep::Idle, false, false, true) == EStep::Idle);
  // The authoritative ABORTED row wakes the drive - and nothing earlier.
  TestTrue("abort row wakes the drive",
           Armed(EStep::Idle, true, false, false) == EStep::ScreenShotWait);

  // The interrupted-screen evidence must settle BEFORE the single leave -
  // never alongside it (the leave would repaint the screen mid-capture).
  TestTrue("leave waits for the screen evidence",
           Armed(EStep::ScreenShotWait, true, false, false) == EStep::ScreenShotWait);
  TestTrue("settled screen evidence advances to the one leave",
           Armed(EStep::ScreenShotWait, true, false, true) == EStep::LeaveOnce);

  // The leave step holds until THIS drive's leave reached the Lobby stage.
  TestTrue("leave step holds while the stage is unchanged",
           Armed(EStep::LeaveOnce, true, false, false) == EStep::LeaveOnce);
  TestTrue("lobby arrival advances to the lobby shot",
           Armed(EStep::LeaveOnce, false, true, false) == EStep::LobbyShotWait);

  // The clean exit only after the lobby evidence settled.
  TestTrue("exit waits for the lobby evidence",
           Armed(EStep::LobbyShotWait, false, true, false) == EStep::LobbyShotWait);
  TestTrue("settled lobby evidence completes the drive",
           Armed(EStep::LobbyShotWait, false, true, true) == EStep::Complete);
  TestTrue("complete is terminal",
           Armed(EStep::Complete, false, false, true) == EStep::Complete);
  return true;
}

#endif

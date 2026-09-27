// S09 review P2 regression: room recovery/entry while Stage Started.
// EnterLobby (F10 "RECOVER MY ROOM", auto-recovery, programmatic callers) used
// to run myGames and install its first room over the live match's Room
// (bumping MatchGeneration) WITHOUT an accepted LeaveRoom: the old
// GameStateOpId survived and later blocked SubscribeAfterSnapshot for the next
// room, while the active server membership was implicitly abandoned. Same
// exposure for CreateRoom/JoinRoomByCode. These tests pin:
//   1. EnterLobby/CreateRoom/JoinRoomByCode during Started are no-ops (room,
//      stage, generation, socket, subscription untouched);
//   2. the DEFERRED variant of the same race: the entry was dispatched while
//      Stage == Room, but the room went Started before the answer landed. A
//      Room->Started transition does NOT bump MatchGeneration, so the
//      request-identity gate passes and the late answer used to install a new
//      Room (or demote the stage, or broadcast an error) over the live match
//      while the old WS stream stayed attached. Covered for myGames,
//      createGame, the gameByCode lookup and the joinGame second leg, success
//      AND failure answers;
//   3. after a VALID leave the same recovery path works again and the new
//      room attaches a fresh stream.
// The "valid leave tears the stream down" half is pinned separately by
// S08LeaveLifecycleTests (accepted leave: teardown + new match's lower
// sequences apply).
#if WITH_AUTOMATION_TESTS

#include "S08FlowController.h"
#include "Misc/AutomationTest.h"

namespace {

FString RoomJson(const FString& Id) {
  return FString::Printf(TEXT(
      "{\"id\":\"%s\",\"code\":\"C1\",\"status\":\"LOBBY\",\"mode\":\"ONE_V_ONE\","
      "\"hostId\":\"h-1\",\"players\":[]}"),
      *Id);
}

FString MyGamesBody(const FString& Id) {
  return TEXT("{\"data\":{\"myGames\":[") + RoomJson(Id) + TEXT("]}}");
}

FString CreateGameBody(const FString& Id) {
  return TEXT("{\"data\":{\"createGame\":") + RoomJson(Id) + TEXT("}}");
}

FString GameByCodeBody(const FString& Id) {
  return TEXT("{\"data\":{\"gameByCode\":") + RoomJson(Id) + TEXT("}}");
}

FString JoinGameBody(const FString& Id) {
  return TEXT("{\"data\":{\"joinGame\":") + RoomJson(Id) + TEXT("}}");
}

struct FGuardCapture {
  int32 Errors = 0;
  int32 Rooms = 0;
  TArray<FString> Traces;

  void Bind(FS08FlowController& Flow) {
    Flow.OnFlowError.AddLambda([this](const FS08GraphQLError&) { ++Errors; });
    Flow.OnRoom.AddLambda([this](const FS08RoomState&) { ++Rooms; });
    Flow.OnTrace.AddLambda([this](const FString& Line) { Traces.Add(Line); });
  }

  bool SawTrace(const TCHAR* Needle) const {
    for (const FString& Line : Traces) {
      if (Line.Contains(Needle)) return true;
    }
    return false;
  }
};

/** Drives the deferred race once: dispatch InEntry at Stage == Room, hold the
 *  answer, flip the SAME room to Started with a live stream (no generation
 *  bump - exactly the live Room->Started transition), then deliver. Returns
 *  the generation observed while Started. */
int32 DispatchThenStartAndDeliver(FS08FlowController& Flow, TFunction<void()> InEntry) {
  InEntry();
  Flow.AttachStreamHarnessForTest(TEXT("g-1"));
  const int32 Gen = Flow.GetMatchGenerationForTest();
  Flow.DeliverQueuedHttpForTest();
  return Gen;
}

} // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08RoomEntryGuardDuringStartedTest,
    "Unmatched.S08.RoomEntryGuard.EnterLobby create and join during Started are no-ops",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08RoomEntryGuardDuringStartedTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"));
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Started);
  Flow.AttachStreamHarnessForTest(TEXT("g-1"));
  TestTrue("subscription live", Flow.HasGameStateOpForTest());
  const int32 Gen = Flow.GetMatchGenerationForTest();

  // Each queued answer holds a DIFFERENT room: without the guard the entry
  // leg would install g-2 over the live match and strand the g-1 op id.
  Flow.QueueHttpResultForTest(true, {}, false, MyGamesBody(TEXT("g-2")));
  Flow.EnterLobby();
  TestTrue("mygames no-op: room kept", Flow.GetRoom().GameId == TEXT("g-1"));
  TestTrue("mygames no-op: stage kept", Flow.GetStage() == ES08Stage::Started);
  TestTrue("mygames no-op: generation kept", Flow.GetMatchGenerationForTest() == Gen);
  TestTrue("mygames no-op: subscription kept", Flow.HasGameStateOpForTest());
  TestTrue("mygames no-op: socket kept", Flow.IsStreamAttached());

  Flow.QueueHttpResultForTest(true, {}, false, CreateGameBody(TEXT("g-2")));
  Flow.CreateRoom(TEXT("ONE_V_ONE"));
  TestTrue("create no-op: room kept", Flow.GetRoom().GameId == TEXT("g-1"));
  TestTrue("create no-op: stage kept", Flow.GetStage() == ES08Stage::Started);
  TestTrue("create no-op: subscription kept", Flow.HasGameStateOpForTest());

  Flow.QueueHttpResultForTest(true, {}, false, GameByCodeBody(TEXT("g-2")));
  Flow.JoinRoomByCode(TEXT("C1"));
  TestTrue("join no-op: room kept", Flow.GetRoom().GameId == TEXT("g-1"));
  TestTrue("join no-op: stage kept", Flow.GetStage() == ES08Stage::Started);
  TestTrue("join no-op: subscription kept", Flow.HasGameStateOpForTest());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08RoomEntryAfterValidLeaveTest,
    "Unmatched.S08.RoomEntryGuard.EnterLobby recovery works after a valid leave",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08RoomEntryAfterValidLeaveTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"));
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Started);
  Flow.AttachStreamHarnessForTest(TEXT("g-1"));
  TestTrue("subscription live before leave", Flow.HasGameStateOpForTest());

  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  TestTrue("left to lobby", Flow.GetStage() == ES08Stage::Lobby);
  TestTrue("room cleared", Flow.GetRoom().GameId.IsEmpty());
  TestFalse("stream torn down", Flow.IsStreamAttached());
  TestFalse("subscription torn down", Flow.HasGameStateOpForTest());

  // Post-leave recovery (the same route the post-GAME_OVER lobby return
  // lands on): entry re-opens and installs the recovered room.
  Flow.QueueHttpResultForTest(true, {}, false, MyGamesBody(TEXT("g-2")));
  Flow.EnterLobby();
  TestTrue("recovery re-opened the room", Flow.GetRoom().GameId == TEXT("g-2"));
  TestTrue("recovery stage is Room", Flow.GetStage() == ES08Stage::Room);

  // The stale g-1 op id is gone: the new room's stream attaches fresh.
  Flow.AttachStreamHarnessForTest(TEXT("g-2"));
  TestTrue("fresh subscription", Flow.HasGameStateOpForTest());
  TestTrue("fresh socket", Flow.IsStreamAttached());
  return true;
}

// ---- deferred variant: dispatched at Room, answer lands while Started ----

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08DeferredEntryAfterRoomWentStartedTest,
    "Unmatched.S08.RoomEntryGuard.deferred entry answers after the room went Started are dropped",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08DeferredEntryAfterRoomWentStartedTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"));
  FGuardCapture Cap;
  Cap.Bind(Flow);

  // --- myGames leg: recovery answer for g-2 lands while g-1 is live. ---
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, MyGamesBody(TEXT("g-2")));
  int32 Gen = DispatchThenStartAndDeliver(Flow, [&Flow]() { Flow.EnterLobby(); });
  TestTrue("mygames deferred: room kept", Flow.GetRoom().GameId == TEXT("g-1"));
  TestTrue("mygames deferred: stage kept", Flow.GetStage() == ES08Stage::Started);
  TestTrue("mygames deferred: generation kept", Flow.GetMatchGenerationForTest() == Gen);
  TestTrue("mygames deferred: socket kept", Flow.IsStreamAttached());
  TestTrue("mygames deferred: subscription kept", Flow.HasGameStateOpForTest());
  TestTrue("mygames deferred: drop trace", Cap.SawTrace(TEXT("MYGAMES late answer ignored")));

  // --- createGame leg ---
  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, CreateGameBody(TEXT("g-2")));
  Gen = DispatchThenStartAndDeliver(Flow, [&Flow]() { Flow.CreateRoom(TEXT("ONE_V_ONE")); });
  TestTrue("create deferred: room kept", Flow.GetRoom().GameId == TEXT("g-1"));
  TestTrue("create deferred: stage kept", Flow.GetStage() == ES08Stage::Started);
  TestTrue("create deferred: generation kept", Flow.GetMatchGenerationForTest() == Gen);
  TestTrue("create deferred: subscription kept", Flow.HasGameStateOpForTest());
  TestTrue("create deferred: drop trace", Cap.SawTrace(TEXT("CREATE late answer ignored")));

  // --- gameByCode lookup leg: resolves while Started, must not fire joinGame ---
  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, GameByCodeBody(TEXT("g-2")));
  Gen = DispatchThenStartAndDeliver(Flow, [&Flow]() { Flow.JoinRoomByCode(TEXT("C1")); });
  TestTrue("lookup deferred: room kept", Flow.GetRoom().GameId == TEXT("g-1"));
  TestTrue("lookup deferred: stage kept", Flow.GetStage() == ES08Stage::Started);
  TestTrue("lookup deferred: generation kept", Flow.GetMatchGenerationForTest() == Gen);
  TestTrue("lookup deferred: subscription kept", Flow.HasGameStateOpForTest());
  TestTrue("lookup deferred: drop trace", Cap.SawTrace(TEXT("JOIN lookup late answer ignored")));

  // --- joinGame second leg: lookup resolves at Room, the join echo lands
  //     while Started. The harness holds BOTH answers (deferred FIFO). ---
  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, GameByCodeBody(TEXT("g-2")));
  Flow.JoinRoomByCode(TEXT("C1"));
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, JoinGameBody(TEXT("g-2")));
  Flow.DeliverQueuedHttpForTest(); // lookup resolves at Room -> joinGame dispatched
  TestTrue("join leg dispatched at Room", Flow.GetStage() == ES08Stage::Room);
  Flow.AttachStreamHarnessForTest(TEXT("g-1")); // same-id start: no generation bump
  Gen = Flow.GetMatchGenerationForTest();
  Flow.DeliverQueuedHttpForTest();
  TestTrue("join deferred: room kept", Flow.GetRoom().GameId == TEXT("g-1"));
  TestTrue("join deferred: stage kept", Flow.GetStage() == ES08Stage::Started);
  TestTrue("join deferred: generation kept", Flow.GetMatchGenerationForTest() == Gen);
  TestTrue("join deferred: subscription kept", Flow.HasGameStateOpForTest());
  TestTrue("join deferred: drop trace", Cap.SawTrace(TEXT("JOIN late answer ignored")));

  // No path broadcast an error or rewrote the room along the way.
  TestEqual("no flow error on any deferred drop", Cap.Errors, 0);

  // --- accepted leave re-opens entry: the recovery works afterwards. ---
  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  TestTrue("left to lobby", Flow.GetStage() == ES08Stage::Lobby);
  TestFalse("stream torn down", Flow.IsStreamAttached());
  Flow.QueueHttpResultForTest(true, {}, false, MyGamesBody(TEXT("g-3")));
  Flow.EnterLobby();
  TestTrue("recovery after leave installs the room", Flow.GetRoom().GameId == TEXT("g-3"));
  TestTrue("recovery stage is Room", Flow.GetStage() == ES08Stage::Room);
  Flow.AttachStreamHarnessForTest(TEXT("g-3"));
  TestTrue("fresh subscription", Flow.HasGameStateOpForTest());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08DeferredEntryFailureAfterRoomWentStartedTest,
    "Unmatched.S08.RoomEntryGuard.deferred entry failure answers after the room went Started stay silent",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08DeferredEntryFailureAfterRoomWentStartedTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"));
  FGuardCapture Cap;
  Cap.Bind(Flow);
  TArray<FS08GraphQLError> Rejection;
  Rejection.Add(FS08GraphQLError{TEXT("FORBIDDEN"), TEXT("no"), FString()});

  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);
  Flow.QueueHttpResultForTest(false, Rejection, /*bDeferDelivery=*/true);
  DispatchThenStartAndDeliver(Flow, [&Flow]() { Flow.EnterLobby(); });
  TestTrue("mygames failure: stage kept", Flow.GetStage() == ES08Stage::Started);

  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);
  Flow.QueueHttpResultForTest(false, Rejection, /*bDeferDelivery=*/true);
  DispatchThenStartAndDeliver(Flow, [&Flow]() { Flow.CreateRoom(TEXT("ONE_V_ONE")); });
  TestTrue("create failure: stage kept", Flow.GetStage() == ES08Stage::Started);

  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);
  Flow.QueueHttpResultForTest(false, Rejection, /*bDeferDelivery=*/true);
  DispatchThenStartAndDeliver(Flow, [&Flow]() { Flow.JoinRoomByCode(TEXT("C1")); });
  TestTrue("lookup failure: stage kept", Flow.GetStage() == ES08Stage::Started);

  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, GameByCodeBody(TEXT("g-2")));
  Flow.JoinRoomByCode(TEXT("C1"));
  Flow.QueueHttpResultForTest(false, Rejection, /*bDeferDelivery=*/true);
  Flow.DeliverQueuedHttpForTest(); // lookup at Room -> joinGame dispatched
  Flow.AttachStreamHarnessForTest(TEXT("g-1"));
  Flow.DeliverQueuedHttpForTest(); // join failure lands while Started
  TestTrue("join failure: room kept", Flow.GetRoom().GameId == TEXT("g-1"));
  TestTrue("join failure: stage kept", Flow.GetStage() == ES08Stage::Started);

  // A stale failure must neither broadcast nor trace as a live failure: the
  // old code surfaced create/lookup/join rejections over the live match.
  TestEqual("no flow error for any deferred failure", Cap.Errors, 0);
  TestFalse("no live failure trace", Cap.SawTrace(TEXT("CREATE failed")));
  TestFalse("no live lookup trace", Cap.SawTrace(TEXT("CODE LOOKUP failed")));
  TestFalse("no live join trace", Cap.SawTrace(TEXT("JOIN failed")));
  return true;
}

#endif

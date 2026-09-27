// S08 P1 regression (request identity): a delayed HTTP answer for a
// left/replaced match used to act on the CURRENT controller state with no
// dispatch-time identity check:
//   - a late successful startGame repopulated the old Room and attached its
//     stream (P1);
//   - a late gameplay mutation echo passed ApplyMatchSnapshot (Stage ==
//     Started for the NEW match) with a higher seq and contaminated it;
//   - old callbacks cleared the new match's in-flight flag and broadcast
//     stale errors;
//   - a GameId-only check could not tell a re-joined same-id room from the
//     original request's room.
// The controller now captures (GameId, MatchGeneration) at dispatch and
// drops a mismatched answer BEFORE any side effect (generation bumps on an
// accepted leave and on every room-id change). Legit same-match answers -
// including in-flight ones - still apply. Driven through the deferred HTTP
// harness (QueueHttpResultForTest + DeliverQueuedHttpForTest) and the WS
// frame harness.
#if WITH_AUTOMATION_TESTS

#include "S08Contracts.h"
#include "S08FlowController.h"
#include "Dom/JsonObject.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace {

const TCHAR* HostId = TEXT("p-host");
const TCHAR* GuestId = TEXT("p-guest");

struct FStaleCapture {
  int32 Errors = 0;
  int32 Rooms = 0;
  int32 Applied = 0;
  int32 LastAppliedSeq = -1;
  TArray<FString> Traces;

  void Bind(FS08FlowController& Flow) {
    Flow.OnFlowError.AddLambda([this](const FS08GraphQLError&) { ++Errors; });
    Flow.OnRoom.AddLambda([this](const FS08RoomState&) { ++Rooms; });
    Flow.OnTrace.AddLambda([this](const FString& Line) { Traces.Add(Line); });
    Flow.OnApplied.AddLambda([this](const FS08Snapshot& S, ES08SeqDecision D) {
      if (D != ES08SeqDecision::Ignore) {
        ++Applied;
        LastAppliedSeq = S.SequenceNumber;
      }
    });
  }

  bool SawTrace(const TCHAR* Needle) const {
    for (const FString& Line : Traces) {
      if (Line.Contains(Needle)) return true;
    }
    return false;
  }
};

/** gameState query body (envelope scalars + the state projection string) the
 *  attach path's HTTP barrier fetch resolves with. */
FString GameStateBody(int32 Seq, const TCHAR* Phase) {
  const FString State =
      TEXT("{\\\"players\\\":[{\\\"userId\\\":\\\"p-host\\\"},{\\\"userId\\\":\\\"p-guest\\\"}],")
      TEXT("\\\"fighters\\\":[{\\\"id\\\":\\\"f1\\\"},{\\\"id\\\":\\\"f2\\\"}],")
      TEXT("\\\"boardState\\\":{\\\"cells\\\":[]},")
      TEXT("\\\"handZones\\\":{\\\"p-host\\\":[],\\\"p-guest\\\":[]}}");
  return FString::Printf(
      TEXT("{\"data\":{\"gameState\":{\"id\":\"gs-1\",\"gameId\":\"g-1\",")
      TEXT("\"state\":\"%s\",\"sequenceNumber\":%d,\"phase\":\"%s\",")
      TEXT("\"turnCount\":1,\"currentTurnPlayerId\":\"p-host\",\"updatedAt\":0}}}"),
      *State, Seq, Phase);
}

/** GraphQL body whose data.<Field> carries a full room (id/code/status...),
 *  as startGame/createGame/game/joinGame echoes do. */
FString RoomBody(const TCHAR* Field, const TCHAR* GameId, const TCHAR* Status) {
  return FString::Printf(
      TEXT("{\"data\":{\"%s\":{\"id\":\"%s\",\"code\":\"AAA111\",")
      TEXT("\"status\":\"%s\",\"mode\":\"ONE_V_ONE\",")
      TEXT("\"hostId\":\"p-host\",\"boardId\":\"b-1\",")
      TEXT("\"players\":[]}}}"),
      Field, GameId, Status);
}

/** GameMutationResult echo body (state projection string + envelope
 *  scalars) for the beginManeuver field. The state value is a JSON string,
 *  so its inner quotes stay escaped. */
FString BeginManeuverEchoBody(int32 Seq, const TCHAR* Phase) {
  const FString State =
      TEXT("{\\\"players\\\":[{\\\"userId\\\":\\\"p-host\\\"},{\\\"userId\\\":\\\"p-guest\\\"}],")
      TEXT("\\\"fighters\\\":[{\\\"id\\\":\\\"f1\\\"},{\\\"id\\\":\\\"f2\\\"}],")
      TEXT("\\\"boardState\\\":{\\\"cells\\\":[]},")
      TEXT("\\\"handZones\\\":{\\\"p-host\\\":[],\\\"p-guest\\\":[]}}");
  return FString::Printf(
      TEXT("{\"data\":{\"beginManeuver\":{\"state\":\"%s\",")
      TEXT("\"sequenceNumber\":%d,\"phase\":\"%s\",\"turnCount\":2,")
      TEXT("\"currentTurnPlayerId\":\"p-host\"}}}"),
      *State, Seq, Phase);
}

/** Sol6 review P1(3): first delivered frame on the current op - proves the
 *  operation live (the command gate opens only after it). Merge at the
 *  baseline seq: no state change, no cues. */
void ProveOpLiveFrame(FS08FlowController& Flow, int32 Seq, const TCHAR* OpId) {
  Flow.InjectWsFrameForTest(FString::Printf(
      TEXT("{\"type\":\"next\",\"id\":\"%s\",\"payload\":{\"data\":{\"gameStateUpdated\":")
      TEXT("{\"sequenceNumber\":%d,\"phase\":\"ACTION_MANEUVER\",\"turnCount\":1,")
      TEXT("\"currentTurnPlayerId\":\"p-host\",")
      TEXT("\"players\":\"[{\\\"userId\\\":\\\"p-host\\\"},{\\\"userId\\\":\\\"p-guest\\\"}]\",")
      TEXT("\"fighters\":\"[{\\\"id\\\":\\\"f1\\\"},{\\\"id\\\":\\\"f2\\\"}]\",")
      TEXT("\"handZones\":\"{\\\"p-host\\\":[],\\\"p-guest\\\":[]}\"}}}}"),
      OpId, Seq));
}

/** Viewer-valid started snapshot (passes ValidateCriticalFields for the
 *  given viewer when CurrentTurnPlayerId is theirs). */
FS08Snapshot ValidStartedSnapshot(int32 Seq, const TCHAR* Phase, const TCHAR* TurnPlayerId) {
  FS08Snapshot S;
  S.SequenceNumber = Seq;
  S.Phase = Phase;
  S.TurnCount = 1;
  S.CurrentTurnPlayerId = TurnPlayerId;
  TSharedRef<FJsonObject> Host = MakeShared<FJsonObject>();
  Host->SetStringField(TEXT("userId"), HostId);
  TSharedRef<FJsonObject> Guest = MakeShared<FJsonObject>();
  Guest->SetStringField(TEXT("userId"), GuestId);
  TArray<TSharedPtr<FJsonValue>> Players = {MakeShared<FJsonValueObject>(Host),
                                            MakeShared<FJsonValueObject>(Guest)};
  S.Players = MakeShared<FJsonValueArray>(Players);
  TSharedRef<FJsonObject> F1 = MakeShared<FJsonObject>();
  F1->SetStringField(TEXT("id"), TEXT("f1"));
  TSharedRef<FJsonObject> F2 = MakeShared<FJsonObject>();
  F2->SetStringField(TEXT("id"), TEXT("f2"));
  TArray<TSharedPtr<FJsonValue>> Fighters = {MakeShared<FJsonValueObject>(F1),
                                             MakeShared<FJsonValueObject>(F2)};
  S.Fighters = MakeShared<FJsonValueArray>(Fighters);
  TSharedRef<FJsonObject> Board = MakeShared<FJsonObject>();
  Board->SetArrayField(TEXT("cells"), {});
  S.BoardState = MakeShared<FJsonValueObject>(Board);
  TSharedRef<FJsonObject> Hands = MakeShared<FJsonObject>();
  Hands->SetArrayField(HostId, {});
  Hands->SetArrayField(GuestId, {});
  S.HandZones = MakeShared<FJsonValueObject>(Hands);
  return S;
}

FString StaleFixturePath() {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S08Fixtures="), Dir) || Dir.IsEmpty()) {
    Dir = FPaths::Combine(FPaths::ProjectDir(),
                          TEXT("../../docs/game-design/evidence/S08/fixtures"));
  }
  return FPaths::Combine(Dir, TEXT("07-ws-game-state-updated-next.json"));
}

TSharedPtr<FJsonObject> StaleWsEvent() {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *StaleFixturePath())) return nullptr;
  TSharedPtr<FJsonValue> Root;
  FString Problem;
  if (!FS08Contracts::TryParseJsonValue(Text, Root, Problem)) return nullptr;
  const TSharedPtr<FJsonObject>* RootObject = nullptr;
  const TSharedPtr<FJsonObject>* Raw = nullptr;
  const TSharedPtr<FJsonObject>* Data = nullptr;
  const TSharedPtr<FJsonObject>* Event = nullptr;
  if (!Root->TryGetObject(RootObject) || !(*RootObject)->TryGetObjectField(TEXT("raw"), Raw) ||
      !(*Raw)->TryGetObjectField(TEXT("data"), Data) ||
      !(*Data)->TryGetObjectField(TEXT("gameStateUpdated"), Event) || !Event->IsValid()) {
    return nullptr;
  }
  return *Event;
}

FString StaleNextFrame(const FString& OpId, const TSharedPtr<FJsonObject>& Event, int32 Seq) {
  TSharedRef<FJsonObject> Copy = MakeShared<FJsonObject>(*Event);
  Copy->SetNumberField(TEXT("sequenceNumber"), Seq);
  TSharedRef<FJsonObject> Frame = MakeShared<FJsonObject>();
  Frame->SetStringField(TEXT("type"), TEXT("next"));
  Frame->SetStringField(TEXT("id"), OpId);
  TSharedRef<FJsonObject> Payload = MakeShared<FJsonObject>();
  TSharedRef<FJsonObject> Data = MakeShared<FJsonObject>();
  Data->SetObjectField(TEXT("gameStateUpdated"), Copy);
  Payload->SetObjectField(TEXT("data"), Data);
  Frame->SetObjectField(TEXT("payload"), Payload);
  FString Out;
  auto Writer = TJsonWriterFactory<>::Create(&Out);
  FJsonSerializer::Serialize(Frame, Writer);
  return Out;
}

} // namespace

// ---- P1: late startGame -------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LateStartGameSuccessIgnoredTest,
    "Unmatched.S08.StaleGuards.late startGame success after accepted leave cannot repopulate old room or attach stream",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LateStartGameSuccessIgnoredTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), HostId);
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);
  FStaleCapture Cap;
  Cap.Bind(Flow);

  // startGame dispatched for g-1; the successful answer is held back.
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true,
                              RoomBody(TEXT("startGame"), TEXT("g-1"), TEXT("IN_PROGRESS")));
  Flow.StartGame();
  TestTrue("start deferred: room untouched so far", Flow.GetRoom().GameId == TEXT("g-1"));

  // Accepted leave, then a new room before the old answer lands.
  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  TestTrue("left to lobby", Flow.GetStage() == ES08Stage::Lobby);
  Flow.SetRoomForTest(TEXT("g-2"), ES08Stage::Room);
  const int32 RoomsBefore = Cap.Rooms;
  const int32 AppliedBefore = Cap.Applied;

  Flow.DeliverQueuedHttpForTest();

  TestTrue("old room not repopulated", Flow.GetRoom().GameId == TEXT("g-2"));
  TestTrue("old payload fields not installed", Flow.GetRoom().Code.IsEmpty());
  TestTrue("stage untouched", Flow.GetStage() == ES08Stage::Room);
  TestFalse("old stream not attached", Flow.IsStreamAttached());
  TestEqual("no room broadcast", Cap.Rooms, RoomsBefore);
  TestEqual("no snapshot applied", Cap.Applied, AppliedBefore);
  TestEqual("no flow error", Cap.Errors, 0);
  TestTrue("stale trace", Cap.SawTrace(TEXT("START stale answer room=g-1 ignored")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LateStartGameFailureSilentTest,
    "Unmatched.S08.StaleGuards.late startGame failure after accepted leave broadcasts nothing",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LateStartGameFailureSilentTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), HostId);
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);
  FStaleCapture Cap;
  Cap.Bind(Flow);

  TArray<FS08GraphQLError> Rejection;
  Rejection.Add(FS08GraphQLError{TEXT("FORBIDDEN"), TEXT("cannot start"), FString()});
  Flow.QueueHttpResultForTest(false, Rejection, /*bDeferDelivery=*/true);
  Flow.StartGame();

  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  Flow.SetRoomForTest(TEXT("g-2"), ES08Stage::Room);

  Flow.DeliverQueuedHttpForTest();

  TestEqual("stale failure stays silent", Cap.Errors, 0);
  TestTrue("newer room untouched", Flow.GetRoom().GameId == TEXT("g-2"));
  TestTrue("stage untouched", Flow.GetStage() == ES08Stage::Room);
  TestTrue("stale trace", Cap.SawTrace(TEXT("START stale answer room=g-1 ignored")));
  TestFalse("no failure trace for stale answer", Cap.SawTrace(TEXT("START failed")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LegitStartGameAttachesTest,
    "Unmatched.S08.StaleGuards.startGame answer for the current room still attaches the stream",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LegitStartGameAttachesTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), HostId);
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);
  FStaleCapture Cap;
  Cap.Bind(Flow);
  // Pre-attach the harness socket: the startGame attach then takes the
  // socket-reuse branch instead of opening a real connection (which would
  // outlive the test controller).
  Flow.AttachStreamHarnessForTest(TEXT("g-1"));

  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true,
                              RoomBody(TEXT("startGame"), TEXT("g-1"), TEXT("IN_PROGRESS")));
  Flow.StartGame();
  // The attach's HTTP barrier fetch must also resolve through the harness -
  // a real request would outlive the test controller (deferred FIFO keeps
  // both answers paired to their callbacks).
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/false,
                              GameStateBody(1, TEXT("ACTION_MANEUVER")));
  Flow.DeliverQueuedHttpForTest();

  TestTrue("room installed", Flow.GetRoom().GameId == TEXT("g-1"));
  TestTrue("status applied", Flow.GetRoom().Status == TEXT("IN_PROGRESS"));
  TestTrue("stage started", Flow.GetStage() == ES08Stage::Started);
  TestTrue("stream attached", Flow.IsStreamAttached());
  TestEqual("no flow error", Cap.Errors, 0);
  TestTrue("no stale trace", !Cap.SawTrace(TEXT("stale answer")));
  return true;
}

// ---- late gameplay mutation echo ----------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LateManeuverEchoAfterNewMatchTest,
    "Unmatched.S08.StaleGuards.late beginManeuver echo after a new match started is ignored; in-flight flag and seq survive",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LateManeuverEchoAfterNewMatchTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), HostId);
  FStaleCapture Cap;
  Cap.Bind(Flow);

  // Match 1 (g-1): valid started state at seq 5, beginManeuver dispatched,
  // its seq-9 echo held back (deferred FIFO entry 1).
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Started);
  Flow.AttachStreamHarnessForTest(TEXT("g-1")); // S10: commands need a live stream
  Flow.ApplySnapshot(ValidStartedSnapshot(5, TEXT("ACTION_MANEUVER"), HostId));
  ProveOpLiveFrame(Flow, 5, TEXT("s08-1")); // Sol6 P1(3): op must prove live
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true,
                              BeginManeuverEchoBody(9, TEXT("ACTION_ATTACK")));
  Flow.BeginManeuver();
  TestTrue("legit dispatch was in flight", Flow.IsManeuverInFlight());

  // Accepted leave tears the match down; a new match g-2 starts at seq 1
  // and issues its own command (deferred FIFO entry 2 - stays in flight).
  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  Flow.SetRoomForTest(TEXT("g-2"), ES08Stage::Started);
  Flow.AttachStreamHarnessForTest(TEXT("g-2"));
  Flow.ApplySnapshot(ValidStartedSnapshot(1, TEXT("ACTION_MANEUVER"), HostId));
  ProveOpLiveFrame(Flow, 1, TEXT("s08-1")); // fresh harness socket: ids restart
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true,
                              BeginManeuverEchoBody(2, TEXT("ACTION_MANEUVER")));
  Flow.BeginManeuver();
  TestTrue("new match command in flight", Flow.IsManeuverInFlight());
  const int32 AppliedBefore = Cap.Applied;

  // Entry 1 first: the OLD match's echo.
  Flow.DeliverQueuedHttpForTest();

  TestEqual("old seq 9 did not apply", Flow.GetAppliedSnapshot().SequenceNumber, 1);
  TestTrue("old phase did not apply", Flow.GetAppliedSnapshot().Phase == TEXT("ACTION_MANEUVER"));
  TestEqual("no snapshot event", Cap.Applied, AppliedBefore);
  TestTrue("new in-flight flag not cleared", Flow.IsManeuverInFlight());
  TestEqual("no flow error", Cap.Errors, 0);
  TestTrue("stale trace", Cap.SawTrace(TEXT("MANEUVER begin stale answer room=g-1 ignored")));

  // Entry 2: the new match's OWN answer must still apply and clear its flag.
  Flow.DeliverQueuedHttpForTest();
  TestEqual("own answer applied", Flow.GetAppliedSnapshot().SequenceNumber, 2);
  TestFalse("own answer cleared in-flight", Flow.IsManeuverInFlight());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LegitDeferredManeuverAnswerAppliesTest,
    "Unmatched.S08.StaleGuards.deferred beginManeuver answer for the same match applies and clears in-flight",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LegitDeferredManeuverAnswerAppliesTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), HostId);
  FStaleCapture Cap;
  Cap.Bind(Flow);

  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Started);
  Flow.AttachStreamHarnessForTest(TEXT("g-1")); // S10: commands need a live stream
  Flow.ApplySnapshot(ValidStartedSnapshot(1, TEXT("ACTION_MANEUVER"), HostId));
  ProveOpLiveFrame(Flow, 1, TEXT("s08-1")); // Sol6 P1(3): op must prove live

  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true,
                              BeginManeuverEchoBody(2, TEXT("ACTION_MANEUVER")));
  Flow.BeginManeuver();
  TestTrue("in flight while deferred", Flow.IsManeuverInFlight());

  Flow.DeliverQueuedHttpForTest();

  TestTrue("same-match answer applied", Flow.GetAppliedSnapshot().SequenceNumber == 2);
  TestFalse("in-flight cleared by own answer", Flow.IsManeuverInFlight());
  TestEqual("no flow error", Cap.Errors, 0);
  TestTrue("no stale trace", !Cap.SawTrace(TEXT("stale answer")));
  TestTrue("apply trace", Cap.SawTrace(TEXT("MANEUVER begin seq=2 (apply)")));
  return true;
}

// ---- re-joined same id: generation, not GameId ---------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LatePollAfterSameIdRejoinTest,
    "Unmatched.S08.StaleGuards.poll answer for a re-joined same-id room is ignored via generation",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LatePollAfterSameIdRejoinTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), HostId);
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);
  FStaleCapture Cap;
  Cap.Bind(Flow);

  // Poll dispatched for the ORIGINAL g-1 incarnation; its answer (a room
  // now IN_PROGRESS) is held back.
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true,
                              RoomBody(TEXT("game"), TEXT("g-1"), TEXT("IN_PROGRESS")));
  Flow.PollRoom();

  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  // Re-join the SAME id: Room.GameId matches the captured one again, only
  // the generation separates the old request from the new incarnation.
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);
  TestTrue("same id re-joined", Flow.GetRoom().GameId == TEXT("g-1"));

  Flow.DeliverQueuedHttpForTest();

  TestTrue("old status not installed", Flow.GetRoom().Status != TEXT("IN_PROGRESS"));
  TestTrue("stage not flipped", Flow.GetStage() == ES08Stage::Room);
  TestFalse("stream not attached", Flow.IsStreamAttached());
  TestEqual("no flow error", Cap.Errors, 0);
  TestTrue("stale trace", Cap.SawTrace(TEXT("POLL stale answer room=g-1 ignored")));
  return true;
}

// ---- late WS frame from an old subscription ------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LateWsFrameFromOldSubscriptionTest,
    "Unmatched.S08.StaleGuards.WS frame from the old subscription after a room change is ignored",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LateWsFrameFromOldSubscriptionTest::RunTest(const FString&) {
  const TSharedPtr<FJsonObject> Event = StaleWsEvent();
  if (!Event.IsValid()) {
    AddError("fixture 07 failed to parse");
    return true;
  }
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), HostId);
  FStaleCapture Cap;
  Cap.Bind(Flow);

  // Match 1 stream live at seq 5 (harness sub id "s08-1"), then the player
  // lands in another room WITHOUT a teardown: the old subscription lives on
  // the reused socket and its frames must not reach the new seq guard.
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Started);
  Flow.AttachStreamHarnessForTest(TEXT("g-1"));
  Flow.InjectWsFrameForTest(StaleNextFrame(TEXT("s08-1"), Event, 5));
  TestEqual("old stream seq applied", Flow.GetAppliedSnapshot().SequenceNumber, 5);

  Flow.SetRoomForTest(TEXT("g-2"), ES08Stage::Started);
  Flow.InjectWsFrameForTest(StaleNextFrame(TEXT("s08-1"), Event, 6));

  TestEqual("stale frame not applied", Flow.GetAppliedSnapshot().SequenceNumber, 5);
  TestTrue("stale trace", Cap.SawTrace(TEXT("WS stale frame room=g-1 ignored")));
  return true;
}

// ---- late createGame answer ----------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LateCreateAnswerIgnoredTest,
    "Unmatched.S08.StaleGuards.late createGame answer after another room became active is ignored",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LateCreateAnswerIgnoredTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), HostId);
  Flow.SetRoomForTest(TEXT("g-9"), ES08Stage::Lobby);
  FStaleCapture Cap;
  Cap.Bind(Flow);

  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true,
                              RoomBody(TEXT("createGame"), TEXT("g-new"), TEXT("LOBBY")));
  Flow.CreateRoom(TEXT("ONE_V_ONE"));

  Flow.SetRoomForTest(TEXT("g-10"), ES08Stage::Room);
  Flow.DeliverQueuedHttpForTest();

  TestTrue("created room did not clobber the newer room",
           Flow.GetRoom().GameId == TEXT("g-10"));
  TestEqual("no room broadcast", Cap.Rooms, 0);
  TestTrue("stale trace", Cap.SawTrace(TEXT("CREATE stale answer ignored")));
  return true;
}

// ---- generation lifecycle -------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MatchGenerationLifecycleTest,
    "Unmatched.S08.StaleGuards.match generation bumps on leave and room change only",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MatchGenerationLifecycleTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"), HostId);
  TestEqual("starts at zero", Flow.GetMatchGenerationForTest(), 0);

  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);
  TestEqual("room change bumps", Flow.GetMatchGenerationForTest(), 1);
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Started);
  TestEqual("same id does not bump", Flow.GetMatchGenerationForTest(), 1);

  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  TestEqual("accepted leave bumps", Flow.GetMatchGenerationForTest(), 2);

  Flow.SetRoomForTest(TEXT("g-2"), ES08Stage::Started);
  TestEqual("new room bumps", Flow.GetMatchGenerationForTest(), 3);
  Flow.SetRoomForTest(TEXT("g-2"), ES08Stage::Started);
  TestEqual("re-seed same id does not bump", Flow.GetMatchGenerationForTest(), 3);
  return true;
}

#endif

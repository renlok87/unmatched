// S08 regression: LeaveRoom used to clear Room and force the Lobby stage even
// when the leaveGame mutation was REJECTED (GraphQL error or transport
// failure) - the player landed in the lobby with a ghost server-side
// membership and no actionable error. Driven through the offline HTTP harness
// (QueueHttpResultForTest), these tests pin:
//   1. rejected leave (server error): room + stage survive, the PROVIDED
//      error is broadcast, an explicit "LEAVE failed" trace fires;
//   2. rejected leave (no errors in the answer): a TRANSPORT error is
//      synthesized and room + stage still survive;
//   3. accepted leave: the "LEFT room=" trace stays, room clears, stage
//      becomes Lobby;
//   4. stale answer: a leave answered after another room became active is
//      ignored (newer room untouched, no error broadcast).
#if WITH_AUTOMATION_TESTS

#include "S08Contracts.h"
#include "S08FlowController.h"
#include "Misc/AutomationTest.h"

namespace {

struct FLeaveCapture {
  int32 Errors = 0;
  int32 LeaveFailures = 0;
  FString LastErrorCode;
  FString LastErrorMessage;
  TArray<FString> Traces;

  void Bind(FS08FlowController& Flow) {
    Flow.OnFlowError.AddLambda([this](const FS08GraphQLError& Error) {
      ++Errors;
      LastErrorCode = Error.Code;
      LastErrorMessage = Error.Message;
    });
    Flow.OnLeaveFailed.AddLambda([this](const FS08GraphQLError&) { ++LeaveFailures; });
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LeaveRejectedKeepsRoomTest,
    "Unmatched.S08.LeaveRoom.rejected leave keeps room and stage; broadcasts provided error",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LeaveRejectedKeepsRoomTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"));
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);
  FLeaveCapture Cap;
  Cap.Bind(Flow);

  TArray<FS08GraphQLError> Rejection;
  Rejection.Add(FS08GraphQLError{TEXT("FORBIDDEN"), TEXT("host cannot leave mid-game"),
                                 FString()});
  Flow.QueueHttpResultForTest(false, Rejection);
  Flow.LeaveRoom();

  TestTrue("room retained", Flow.GetRoom().GameId == TEXT("g-1"));
  TestTrue("stage retained", Flow.GetStage() == ES08Stage::Room);
  TestEqual("one flow error", Cap.Errors, 1);
  TestEqual("one leave failure", Cap.LeaveFailures, 1);
  TestTrue("provided error code preserved", Cap.LastErrorCode == TEXT("FORBIDDEN"));
  TestTrue("provided error message preserved",
           Cap.LastErrorMessage == TEXT("host cannot leave mid-game"));
  TestTrue("explicit failure trace", Cap.SawTrace(TEXT("LEAVE failed")));
  TestFalse("no success trace", Cap.SawTrace(TEXT("LEFT room=")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LeaveTransportFailureTest,
    "Unmatched.S08.LeaveRoom.transport failure synthesizes TRANSPORT error",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LeaveTransportFailureTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"));
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Started);
  FLeaveCapture Cap;
  Cap.Bind(Flow);

  Flow.QueueHttpResultForTest(false); // transport failure: empty error list
  Flow.LeaveRoom();

  TestTrue("room retained", Flow.GetRoom().GameId == TEXT("g-1"));
  TestTrue("stage retained", Flow.GetStage() == ES08Stage::Started);
  TestEqual("one flow error", Cap.Errors, 1);
  TestEqual("one leave failure", Cap.LeaveFailures, 1);
  TestTrue("TRANSPORT synthesized", Cap.LastErrorCode == TEXT("TRANSPORT"));
  TestFalse("message not empty", Cap.LastErrorMessage.IsEmpty());
  TestTrue("explicit failure trace", Cap.SawTrace(TEXT("LEAVE failed")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LeaveAcceptedTest,
    "Unmatched.S08.LeaveRoom.accepted leave clears room and returns to lobby",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LeaveAcceptedTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"));
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);
  FLeaveCapture Cap;
  Cap.Bind(Flow);

  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();

  TestTrue("room cleared", Flow.GetRoom().GameId.IsEmpty());
  TestTrue("stage lobby", Flow.GetStage() == ES08Stage::Lobby);
  TestTrue("success trace kept", Cap.SawTrace(TEXT("LEFT room=g-1")));
  TestEqual("no flow error", Cap.Errors, 0);
  TestEqual("no leave failure", Cap.LeaveFailures, 0);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LeaveStaleAnswerTest,
    "Unmatched.S08.LeaveRoom.stale answer after joining another room is ignored",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LeaveStaleAnswerTest::RunTest(const FString&) {
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"));
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Room);
  FLeaveCapture Cap;
  Cap.Bind(Flow);

  // Deferred delivery: the answer to the g-1 leave arrives only after the
  // player already joined g-2.
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true);
  Flow.LeaveRoom();
  TestTrue("room untouched before delivery", Flow.GetRoom().GameId == TEXT("g-1"));

  Flow.SetRoomForTest(TEXT("g-2"), ES08Stage::Room);
  Flow.DeliverQueuedHttpForTest();

  TestTrue("newer room untouched", Flow.GetRoom().GameId == TEXT("g-2"));
  TestTrue("stage untouched", Flow.GetStage() == ES08Stage::Room);
  TestEqual("no flow error", Cap.Errors, 0);
  TestEqual("no leave failure", Cap.LeaveFailures, 0);
  TestTrue("stale trace", Cap.SawTrace(TEXT("LEAVE stale answer room=g-1 ignored")));
  TestFalse("no success trace", Cap.SawTrace(TEXT("LEFT room=")));
  return true;
}

#endif

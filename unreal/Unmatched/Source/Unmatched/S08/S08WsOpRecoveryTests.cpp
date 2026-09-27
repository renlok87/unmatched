// S08 P1 regression: subscription-level 'error'/'complete' frames arrive on
// a HEALTHY socket. The WS layer used to just drop the operation from
// Pending while the flow controller kept GameStateOpId set - the stream then
// never delivered again and never resubscribed (the transport-level reconnect
// path never fired because the socket was fine). These tests inject raw
// graphql-transport-ws server frames into the socket-less test seam and pin:
//   1. WS layer: error/complete fire OnOperationEnded, drop the dead id and
//      ignore its late frames; a resubscribe on the SAME object gets a fresh
//      id that receives 'next' again.
//   2. Flow level: the operation id is cleared and a BOUNDED refetch +
//      resubscribe runs on the same open socket; a delivered snapshot resets
//      the bound; after the bound is exhausted the failure surfaces through
//      OnFlowError instead of spinning.
#if WITH_AUTOMATION_TESTS

#include "S08Contracts.h"
#include "S08FlowController.h"
#include "S08GraphqlWs.h"
#include "Dom/JsonObject.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace {

FString OpFixturePath() {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S08Fixtures="), Dir) || Dir.IsEmpty()) {
    Dir = FPaths::Combine(FPaths::ProjectDir(),
                          TEXT("../../docs/game-design/evidence/S08/fixtures"));
  }
  return FPaths::Combine(Dir, TEXT("07-ws-game-state-updated-next.json"));
}

/** data.gameStateUpdated object from the captured live WS 'next' fixture. */
TSharedPtr<FJsonObject> WsNextPayloadFromFixture() {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *OpFixturePath())) return nullptr;
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

FString MakeNextFrame(const FString& OpId, const TSharedPtr<FJsonObject>& Event) {
  TSharedRef<FJsonObject> Frame = MakeShared<FJsonObject>();
  Frame->SetStringField(TEXT("type"), TEXT("next"));
  Frame->SetStringField(TEXT("id"), OpId);
  TSharedRef<FJsonObject> Payload = MakeShared<FJsonObject>();
  TSharedRef<FJsonObject> Data = MakeShared<FJsonObject>();
  Data->SetObjectField(TEXT("gameStateUpdated"), Event);
  Payload->SetObjectField(TEXT("data"), Data);
  Frame->SetObjectField(TEXT("payload"), Payload);
  FString Out;
  auto Writer = TJsonWriterFactory<>::Create(&Out);
  FJsonSerializer::Serialize(Frame, Writer);
  return Out;
}

} // namespace

// ---- WS layer: 'error' frame ------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08WsErrorFrameTest,
    "Unmatched.S08.WsOp.error frame ends operation; resubscribe gets fresh working id",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08WsErrorFrameTest::RunTest(const FString&) {
  FS08GraphqlWs Ws(TEXT("ws://test.invalid"), FString());
  Ws.ForceAckedForTest();

  const TSharedPtr<FJsonObject> Event = WsNextPayloadFromFixture();
  if (!Event.IsValid()) {
    AddError("fixture 07 failed to parse");
    return true;
  }

  int32 Snapshots = 0;
  TArray<FString> ErrorMessages;
  TArray<FString> EndedIds;
  Ws.OnOperationEnded.AddLambda([&](const FString& Id, const FString& Reason) {
    EndedIds.Add(Id + TEXT("|") + Reason);
  });

  const FString OpA = Ws.SubscribeGameStateUpdated(
      TEXT("g1"), 0, [&](const FS08Snapshot&) { ++Snapshots; },
      [&](const FS08GraphQLError& E) { ErrorMessages.Add(E.Message); });
  TestFalse("subscribe returned an id", OpA.IsEmpty());

  // Server rejects the subscription (e.g. auth lost mid-flight).
  Ws.InjectServerFrameForTest(
      TEXT("{\"type\":\"error\",\"id\":\"") + OpA +
      TEXT("\",\"payload\":[{\"message\":\"subscription rejected\"}]}"));
  TestEqual("error surfaced once", ErrorMessages.Num(), 1);
  TestTrue("error reason kept", ErrorMessages[0].Contains(TEXT("subscription rejected")));
  TestEqual("operation ended once", EndedIds.Num(), 1);
  TestTrue("ended id matches op", EndedIds[0].StartsWith(OpA + TEXT("|")));
  TestTrue("ended reason carried", EndedIds[0].Contains(TEXT("subscription rejected")));

  // Late 'next' for the DEAD id must be ignored (Pending removed).
  Ws.InjectServerFrameForTest(MakeNextFrame(OpA, Event));
  TestEqual("dead id delivers nothing", Snapshots, 0);

  // Resubscribe on the SAME socket object: fresh id, deliveries work again.
  const FString OpB = Ws.SubscribeGameStateUpdated(
      TEXT("g1"), 1, [&](const FS08Snapshot&) { ++Snapshots; },
      [&](const FS08GraphQLError& E) { ErrorMessages.Add(E.Message); });
  TestFalse("resubscribe returned an id", OpB.IsEmpty());
  TestTrue("fresh id differs", OpA != OpB);
  Ws.InjectServerFrameForTest(MakeNextFrame(OpB, Event));
  TestEqual("fresh id delivers", Snapshots, 1);
  return true;
}

// ---- WS layer: 'complete' frame ----------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08WsCompleteFrameTest,
    "Unmatched.S08.WsOp.complete frame ends operation without an error",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08WsCompleteFrameTest::RunTest(const FString&) {
  FS08GraphqlWs Ws(TEXT("ws://test.invalid"), FString());
  Ws.ForceAckedForTest();

  const TSharedPtr<FJsonObject> Event = WsNextPayloadFromFixture();
  if (!Event.IsValid()) {
    AddError("fixture 07 failed to parse");
    return true;
  }

  int32 Snapshots = 0;
  int32 Errors = 0;
  TArray<FString> EndedIds;
  Ws.OnOperationEnded.AddLambda([&](const FString& Id, const FString& Reason) {
    EndedIds.Add(Id + TEXT("|") + Reason);
  });

  const FString OpA = Ws.SubscribeGameStateUpdated(
      TEXT("g1"), 0, [&](const FS08Snapshot&) { ++Snapshots; },
      [&](const FS08GraphQLError&) { ++Errors; });

  // Server completes the subscription (normal end, not a failure).
  Ws.InjectServerFrameForTest(TEXT("{\"type\":\"complete\",\"id\":\"") + OpA + TEXT("\"}"));
  TestEqual("no error surfaced for complete", Errors, 0);
  TestEqual("operation ended once", EndedIds.Num(), 1);
  TestTrue("ended id matches", EndedIds[0].StartsWith(OpA + TEXT("|")));
  TestTrue("reason is complete", EndedIds[0].Contains(TEXT("complete")));

  Ws.InjectServerFrameForTest(MakeNextFrame(OpA, Event));
  TestEqual("dead id delivers nothing", Snapshots, 0);

  const FString OpB = Ws.SubscribeGameStateUpdated(
      TEXT("g1"), 1, [&](const FS08Snapshot&) { ++Snapshots; },
      [&](const FS08GraphQLError&) { ++Errors; });
  TestTrue("fresh id differs", OpA != OpB);
  Ws.InjectServerFrameForTest(MakeNextFrame(OpB, Event));
  TestEqual("fresh id delivers", Snapshots, 1);
  return true;
}

// ---- S10 review: a REJECTED 'next' must stop the server-side subscription ----
// The WS layer ends the LOCAL operation for every 'next' frame that cannot
// yield a snapshot (errors[], null/unexpected shape, contract-parse failure),
// but a 'next' frame is NOT terminal for the server: the subscription it
// belongs to keeps streaming. Without an explicit client 'complete' the dead
// operation survives server-side forever while the owner resubscribes with a
// fresh id - two live subscriptions for one client. The socket-less harness
// records every outgoing frame, so the test proves the 'complete' left.
namespace {
// Outgoing frames serialize pretty-printed: match by content pair, not layout.
int32 CountSentFrames(const FS08GraphqlWs& Ws, const TCHAR* Needle) {
  int32 Count = 0;
  for (const FString& Frame : Ws.GetSentFramesForTest()) {
    if (Frame.Contains(Needle)) ++Count;
  }
  return Count;
}
int32 CountCompletesFor(const FS08GraphqlWs& Ws, const FString& OpId) {
  const FString IdNeedle = TEXT("\"") + OpId + TEXT("\"");
  int32 Count = 0;
  for (const FString& Frame : Ws.GetSentFramesForTest()) {
    if (Frame.Contains(IdNeedle) && Frame.Contains(TEXT("complete"))) ++Count;
  }
  return Count;
}
} // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08WsRejectedNextSendsCompleteTest,
    "Unmatched.S08.WsOp.rejected next frame sends complete for the dead operation",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08WsRejectedNextSendsCompleteTest::RunTest(const FString&) {
  FS08GraphqlWs Ws(TEXT("ws://test.invalid"), FString());
  Ws.ForceAckedForTest();

  const TSharedPtr<FJsonObject> Event = WsNextPayloadFromFixture();
  if (!Event.IsValid()) {
    AddError("fixture 07 failed to parse");
    return true;
  }
  // Contract-parse failure shape: valid JSON object, missing sequenceNumber.
  TSharedRef<FJsonObject> Unparsable = MakeShared<FJsonObject>(*Event);
  Unparsable->RemoveField(TEXT("sequenceNumber"));

  int32 Snapshots = 0;
  int32 Errors = 0;
  TArray<FString> EndedIds;
  Ws.OnOperationEnded.AddLambda([&](const FString& Id, const FString&) { EndedIds.Add(Id); });

  // (a) null gameStateUpdated (unexpected shape): complete for THAT id.
  {
    const FString Op = Ws.SubscribeGameStateUpdated(
        TEXT("g1"), 0, [&](const FS08Snapshot&) { ++Snapshots; },
        [&](const FS08GraphQLError&) { ++Errors; });
    Ws.InjectServerFrameForTest(
        TEXT("{\"type\":\"next\",\"id\":\"") + Op +
        TEXT("\",\"payload\":{\"data\":{\"gameStateUpdated\":null}}}"));
    TestEqual("null next ends the operation", EndedIds.Num(), 1);
    TestEqual("complete sent for the null-next id", CountCompletesFor(Ws, Op), 1);
  }
  // (b) errors[] 'next': complete for that id.
  {
    const FString Op = Ws.SubscribeGameStateUpdated(
        TEXT("g1"), 0, [&](const FS08Snapshot&) { ++Snapshots; },
        [&](const FS08GraphQLError&) { ++Errors; });
    Ws.InjectServerFrameForTest(
        TEXT("{\"type\":\"next\",\"id\":\"") + Op +
        TEXT("\",\"payload\":{\"errors\":[{\"message\":\"resolver blew up\"}]}}"));
    TestEqual("errors next ends the operation", EndedIds.Num(), 2);
    TestEqual("complete sent for the errors-next id", CountCompletesFor(Ws, Op), 1);
  }
  // (c) contract-parse failure inside data.gameStateUpdated: complete for that id.
  {
    const FString Op = Ws.SubscribeGameStateUpdated(
        TEXT("g1"), 0, [&](const FS08Snapshot&) { ++Snapshots; },
        [&](const FS08GraphQLError&) { ++Errors; });
    Ws.InjectServerFrameForTest(MakeNextFrame(Op, Unparsable));
    TestEqual("unparsable event ends the operation", EndedIds.Num(), 3);
    TestEqual("complete sent for the unparsable-next id", CountCompletesFor(Ws, Op), 1);
  }

  // (d) Semantic guards: a VALID 'next' delivers and sends NO complete; a
  // server 'error'/'complete' frame is ALREADY terminal server-side - echoing
  // our own complete back would risk a loop, so none is sent.
  {
    const FString Op = Ws.SubscribeGameStateUpdated(
        TEXT("g1"), 0, [&](const FS08Snapshot&) { ++Snapshots; },
        [&](const FS08GraphQLError&) { ++Errors; });
    const int32 CompleteBefore = CountSentFrames(Ws, TEXT("complete"));
    Ws.InjectServerFrameForTest(MakeNextFrame(Op, Event));
    TestEqual("valid next delivered", Snapshots, 1);
    TestEqual("valid next sends no complete",
              CountSentFrames(Ws, TEXT("complete")), CompleteBefore);

    Ws.InjectServerFrameForTest(
        TEXT("{\"type\":\"error\",\"id\":\"") + Op +
        TEXT("\",\"payload\":[{\"message\":\"rejected\"}]}"));
    TestEqual("server error needs no client complete",
              CountSentFrames(Ws, TEXT("complete")), CompleteBefore);

    const FString Op2 = Ws.SubscribeGameStateUpdated(
        TEXT("g1"), 0, [&](const FS08Snapshot&) { ++Snapshots; },
        [&](const FS08GraphQLError&) { ++Errors; });
    Ws.InjectServerFrameForTest(TEXT("{\"type\":\"complete\",\"id\":\"") + Op2 + TEXT("\"}"));
    TestEqual("server complete needs no client complete",
              CountSentFrames(Ws, TEXT("complete")), CompleteBefore);
  }

  // (e) Unsubscribe still sends exactly one complete for the operation.
  {
    const FString Op = Ws.SubscribeGameStateUpdated(
        TEXT("g1"), 0, [&](const FS08Snapshot&) { ++Snapshots; },
        [&](const FS08GraphQLError&) { ++Errors; });
    Ws.Unsubscribe(Op);
    TestEqual("unsubscribe complete sent once", CountCompletesFor(Ws, Op), 1);
  }
  return true;
}

// ---- WS + flow level: malformed (unparseable) server frame -------------------
// A frame that fails the crash-safe pre-scan has NO readable operation id.
// The WS layer used to only log a warning and return - the flow controller
// then waited on an operation that could be dead forever (stale-seq silent
// hang). Now the WS layer notifies OnMalformedFrame (leaving its pending
// ops registered - the OWNER decides), and the flow controller poisons its
// live subscription through the SAME bounded refetch+resubscribe path as an
// operation-level failure: bounded recovery, then a visible OnFlowError.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08WsMalformedFrameTest,
    "Unmatched.S08.WsOp.malformed frame notifies owner; flow recovers boundedly then errors visibly",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08WsMalformedFrameTest::RunTest(const FString&) {
  const TSharedPtr<FJsonObject> Event = WsNextPayloadFromFixture();
  if (!Event.IsValid()) {
    AddError("fixture 07 failed to parse");
    return true;
  }
  const FString Malformed = TEXT("{\"type\":\"next\",\"id\":\"s08-1\",\"payload\":{\"data\":\"trunc");

  // 1) WS layer: the unparseable frame is rejected by the crash-safe scanner,
  //    OnMalformedFrame fires with the problem, and the pending operation is
  //    left registered (a valid 'next' on the same id still delivers).
  {
    FS08GraphqlWs Ws(TEXT("ws://test.invalid"), FString());
    Ws.ForceAckedForTest();
    TArray<FString> Problems;
    Ws.OnMalformedFrame.AddLambda([&](const FString& Problem) { Problems.Add(Problem); });
    int32 Snapshots = 0;
    const FString OpId = Ws.SubscribeGameStateUpdated(
        TEXT("g1"), 0, [&](const FS08Snapshot&) { ++Snapshots; },
        [](const FS08GraphQLError&) {});
    Ws.InjectServerFrameForTest(Malformed);
    TestEqual("malformed frame notified once", Problems.Num(), 1);
    TestTrue("problem text carried", Problems[0].Contains(TEXT("unterminated")));
    Ws.InjectServerFrameForTest(MakeNextFrame(OpId, Event));
    TestEqual("op still delivers after notification", Snapshots, 1);
  }

  // 2) Flow level: the live subscription is poisoned -> bounded refetch +
  //    resubscribe on the same open socket; a delivered snapshot resets the
  //    bound; exhausting it surfaces through OnFlowError (no silent hang).
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), TEXT("viewer-1"));
  TArray<FString> Traces;
  TArray<FString> FlowErrors;
  Flow.OnTrace.AddLambda([&](const FString& Line) { Traces.Add(Line); });
  Flow.OnFlowError.AddLambda([&](const FS08GraphQLError& E) { FlowErrors.Add(E.Message); });

  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  TestTrue("operation registered", Flow.HasGameStateOpForTest());
  const auto TraceAll = [&]() {
    FString Joined;
    for (const FString& Line : Traces) Joined += Line + TEXT("\n");
    return Joined;
  };

  Flow.InjectWsFrameForTest(Malformed);
  TestTrue("resubscribed after malformed frame", Flow.HasGameStateOpForTest());
  TestEqual("one bounded attempt", Flow.GetOpRecoveryAttemptsForTest(), 1);
  TestFalse("no transport reconnect fired", TraceAll().Contains(TEXT("WS reconnect")));
  TestFalse("no WS close fired", TraceAll().Contains(TEXT("WS closed")));
  TestTrue("poison traced", TraceAll().Contains(TEXT("malformed frame")));

  // The recovered operation works - the bound resets.
  Flow.InjectWsFrameForTest(MakeNextFrame(TEXT("s08-2"), Event));
  TestEqual("bound reset by delivery", Flow.GetOpRecoveryAttemptsForTest(), 0);
  TestEqual("snapshot applied", Flow.GetAppliedSnapshot().SequenceNumber, 1);

  // Malformed loop: three more recoveries then give-up (visible error).
  Flow.InjectWsFrameForTest(Malformed);
  TestEqual("attempt 1", Flow.GetOpRecoveryAttemptsForTest(), 1);
  Flow.InjectWsFrameForTest(Malformed);
  TestEqual("attempt 2", Flow.GetOpRecoveryAttemptsForTest(), 2);
  Flow.InjectWsFrameForTest(Malformed);
  TestEqual("attempt 3", Flow.GetOpRecoveryAttemptsForTest(), 3);
  Flow.InjectWsFrameForTest(Malformed);
  TestFalse("give-up: no resubscribe", Flow.HasGameStateOpForTest());
  TestEqual("bound stays at max", Flow.GetOpRecoveryAttemptsForTest(), 3);
  TestTrue("failure surfaced", FlowErrors.Num() >= 1 &&
      FlowErrors.Last().Contains(TEXT("malformed frame")));
  TestTrue("give-up traced", TraceAll().Contains(TEXT("giving up")));
  return true;
}



IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08FlowOpRecoveryTest,
    "Unmatched.S08.WsOp.flow: complete->resubscribe, snapshot resets bound, errors give up",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08FlowOpRecoveryTest::RunTest(const FString&) {
  const TSharedPtr<FJsonObject> Event = WsNextPayloadFromFixture();
  if (!Event.IsValid()) {
    AddError("fixture 07 failed to parse");
    return true;
  }

  // Empty HTTP URL: the barrier refetch fails fast without a dangling async
  // request outliving the test object.
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), TEXT("viewer-1"));
  TArray<FString> Traces;
  TArray<FString> FlowErrors;
  Flow.OnTrace.AddLambda([&](const FString& Line) { Traces.Add(Line); });
  Flow.OnFlowError.AddLambda([&](const FS08GraphQLError& E) { FlowErrors.Add(E.Message); });

  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  TestTrue("operation registered", Flow.HasGameStateOpForTest());
  const auto TraceAll = [&]() {
    FString Joined;
    for (const FString& Line : Traces) Joined += Line + TEXT("\n");
    return Joined;
  };

  // 1) server completes the operation: id cleared then RESUBSCRIBED on the
  //    same socket (no transport reconnect), bound counter at 1.
  Flow.InjectWsFrameForTest(TEXT("{\"type\":\"complete\",\"id\":\"s08-1\"}"));
  TestTrue("resubscribed after complete", Flow.HasGameStateOpForTest());
  TestEqual("one bounded attempt", Flow.GetOpRecoveryAttemptsForTest(), 1);
  TestFalse("no transport reconnect fired", TraceAll().Contains(TEXT("WS reconnect")));
  TestFalse("no WS close fired", TraceAll().Contains(TEXT("WS closed")));
  TestTrue("recovery traced", TraceAll().Contains(TEXT("WS operation ended (complete)")));

  // 2) a delivered snapshot on the recovered op proves it works - bound resets.
  Flow.InjectWsFrameForTest(MakeNextFrame(TEXT("s08-2"), Event));
  TestEqual("bound reset by delivery", Flow.GetOpRecoveryAttemptsForTest(), 0);
  TestEqual("snapshot applied", Flow.GetAppliedSnapshot().SequenceNumber, 1);

  // 3) error/complete loop: three more recoveries, then the next end gives up
  //    (surfaces through OnFlowError, no further resubscribe).
  Flow.InjectWsFrameForTest(
      TEXT("{\"type\":\"error\",\"id\":\"s08-2\",\"payload\":[{\"message\":\"boom-1\"}]}"));
  TestTrue("resubscribed after error 1", Flow.HasGameStateOpForTest());
  TestEqual("attempt 1", Flow.GetOpRecoveryAttemptsForTest(), 1);
  Flow.InjectWsFrameForTest(
      TEXT("{\"type\":\"error\",\"id\":\"s08-3\",\"payload\":[{\"message\":\"boom-2\"}]}"));
  TestEqual("attempt 2", Flow.GetOpRecoveryAttemptsForTest(), 2);
  Flow.InjectWsFrameForTest(
      TEXT("{\"type\":\"error\",\"id\":\"s08-4\",\"payload\":[{\"message\":\"boom-3\"}]}"));
  TestEqual("attempt 3", Flow.GetOpRecoveryAttemptsForTest(), 3);
  Flow.InjectWsFrameForTest(
      TEXT("{\"type\":\"error\",\"id\":\"s08-5\",\"payload\":[{\"message\":\"boom-4\"}]}"));
  TestFalse("give-up: no resubscribe", Flow.HasGameStateOpForTest());
  TestEqual("bound stays at max", Flow.GetOpRecoveryAttemptsForTest(), 3);
  TestTrue("failure surfaced", FlowErrors.Num() >= 1 && FlowErrors.Last().Contains(TEXT("boom-4")));
  TestTrue("give-up traced", TraceAll().Contains(TEXT("giving up")));
  return true;
}

#endif

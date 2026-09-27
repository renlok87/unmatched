// S08 P1 regression (match lifecycle): an accepted LeaveRoom used to clear
// Room and set the Lobby stage but left the WS subscription, the applied
// snapshot and the seq guard attached to the old game - a later match then
// failed to subscribe (stale op id) or had its LOW sequences rejected by the
// stale guard. Driven through the offline HTTP + WS harnesses, these tests
// pin:
//   1. accepted leave tears down the stream: subscription gone, socket gone,
//      applied snapshot + seq guard reset;
//   2. a NEW match after the leave attaches fresh and APPLIES its lower
//      sequences (seq 1 after the old game sat at seq 5);
//   3. a deferred (stale) leave answer arriving after the new match attached
//      is ignored - the new stream and applied state survive;
//   4. a REJECTED leave keeps room/stage/stream intact and the stream keeps
//      applying frames (the FAILED path must not tear anything down).
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

FString LifecycleFixturePath() {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S08Fixtures="), Dir) || Dir.IsEmpty()) {
    Dir = FPaths::Combine(FPaths::ProjectDir(),
                          TEXT("../../docs/game-design/evidence/S08/fixtures"));
  }
  return FPaths::Combine(Dir, TEXT("07-ws-game-state-updated-next.json"));
}

/** data.gameStateUpdated object from the captured live WS 'next' fixture
 *  (sequenceNumber 1). Returns a deep-enough copy callers may retag. */
TSharedPtr<FJsonObject> LifecycleWsEvent() {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *LifecycleFixturePath())) return nullptr;
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

FString MakeLifecycleNextFrame(const FString& OpId, const TSharedPtr<FJsonObject>& Event) {
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

/** Event copy with sequenceNumber retagged (the harness sub id of a fresh
 *  FS08GraphqlWs is deterministic: first subscribe = "s08-1"). */
TSharedPtr<FJsonObject> EventWithSeq(const TSharedPtr<FJsonObject>& Event, int32 Seq) {
  if (!Event.IsValid()) return nullptr;
  TSharedRef<FJsonObject> Copy = MakeShared<FJsonObject>(*Event);
  Copy->SetNumberField(TEXT("sequenceNumber"), Seq);
  return Copy;
}

} // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LeaveTearsDownStreamTest,
    "Unmatched.S08.LeaveLifecycle.accepted leave tears down stream, applied state and seq guard",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LeaveTearsDownStreamTest::RunTest(const FString&) {
  const TSharedPtr<FJsonObject> Event = LifecycleWsEvent();
  if (!Event.IsValid()) {
    AddError("fixture 07 failed to parse");
    return true;
  }
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"));
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Started);
  Flow.AttachStreamHarnessForTest(TEXT("g-1"));
  TestTrue("subscription live before leave", Flow.HasGameStateOpForTest());
  TestTrue("socket live before leave", Flow.IsStreamAttached());

  // Old match progresses to seq 5 through the LIVE WS path.
  Flow.InjectWsFrameForTest(MakeLifecycleNextFrame(TEXT("s08-1"), EventWithSeq(Event, 1)));
  Flow.InjectWsFrameForTest(MakeLifecycleNextFrame(TEXT("s08-1"), EventWithSeq(Event, 5)));
  TestEqual("old match seq applied", Flow.GetAppliedSnapshot().SequenceNumber, 5);

  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();

  TestTrue("stage lobby", Flow.GetStage() == ES08Stage::Lobby);
  TestTrue("room cleared", Flow.GetRoom().GameId.IsEmpty());
  TestFalse("subscription torn down", Flow.HasGameStateOpForTest());
  TestFalse("socket torn down", Flow.IsStreamAttached());
  TestEqual("applied snapshot reset", Flow.GetAppliedSnapshot().SequenceNumber, 0);
  TestTrue("applied phase reset", Flow.GetAppliedSnapshot().Phase.IsEmpty());
  TestFalse("no command left in flight", Flow.IsManeuverInFlight());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LeaveNewMatchSeqAcceptanceTest,
    "Unmatched.S08.LeaveLifecycle.new match after manual leave applies its lower sequences",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LeaveNewMatchSeqAcceptanceTest::RunTest(const FString&) {
  const TSharedPtr<FJsonObject> Event = LifecycleWsEvent();
  if (!Event.IsValid()) {
    AddError("fixture 07 failed to parse");
    return true;
  }
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"));

  // Match 1: live stream at seq 5, then an accepted manual leave.
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Started);
  Flow.AttachStreamHarnessForTest(TEXT("g-1"));
  Flow.InjectWsFrameForTest(MakeLifecycleNextFrame(TEXT("s08-1"), EventWithSeq(Event, 5)));
  TestEqual("match 1 seq", Flow.GetAppliedSnapshot().SequenceNumber, 5);
  Flow.QueueHttpResultForTest(true);
  Flow.LeaveRoom();
  TestTrue("left to lobby", Flow.GetStage() == ES08Stage::Lobby);

  // Match 2 (new room): a FRESH stream must attach and its seq 1 - LOWER
  // than the dead game's seq 5 - must APPLY, not be swallowed by a stale
  // seq guard left over from match 1.
  Flow.SetRoomForTest(TEXT("g-2"), ES08Stage::Started);
  Flow.AttachStreamHarnessForTest(TEXT("g-2"));
  TestTrue("fresh subscription", Flow.HasGameStateOpForTest());
  TestTrue("fresh socket", Flow.IsStreamAttached());

  int32 Applied = 0;
  int32 LastDecision = -1;
  Flow.OnApplied.AddLambda([&](const FS08Snapshot&, ES08SeqDecision Decision) {
    ++Applied;
    LastDecision = static_cast<int32>(Decision);
  });
  Flow.InjectWsFrameForTest(
      MakeLifecycleNextFrame(TEXT("s08-1"), EventWithSeq(Event, 1)));

  TestEqual("new match seq 1 delivered", Applied, 1);
  TestEqual("decision was Apply", LastDecision, static_cast<int32>(ES08SeqDecision::Apply));
  TestEqual("applied seq is 1", Flow.GetAppliedSnapshot().SequenceNumber, 1);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LeaveStaleAnswerAfterNewMatchTest,
    "Unmatched.S08.LeaveLifecycle.stale leave answer after a new match attached is ignored",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LeaveStaleAnswerAfterNewMatchTest::RunTest(const FString&) {
  const TSharedPtr<FJsonObject> Event = LifecycleWsEvent();
  if (!Event.IsValid()) {
    AddError("fixture 07 failed to parse");
    return true;
  }
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"));

  // Deferred leave for g-1; the answer is held back until a new match live.
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Started);
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true);
  Flow.LeaveRoom();

  // New match g-2 attaches and applies before the old answer lands.
  Flow.SetRoomForTest(TEXT("g-2"), ES08Stage::Started);
  Flow.AttachStreamHarnessForTest(TEXT("g-2"));
  Flow.InjectWsFrameForTest(MakeLifecycleNextFrame(TEXT("s08-1"), EventWithSeq(Event, 1)));
  TestEqual("new match seq applied", Flow.GetAppliedSnapshot().SequenceNumber, 1);

  Flow.DeliverQueuedHttpForTest();

  TestTrue("stale answer did not clear the room", Flow.GetRoom().GameId == TEXT("g-2"));
  TestTrue("stage untouched", Flow.GetStage() == ES08Stage::Started);
  TestTrue("stream survived", Flow.IsStreamAttached());
  TestTrue("subscription survived", Flow.HasGameStateOpForTest());
  TestEqual("applied seq survived", Flow.GetAppliedSnapshot().SequenceNumber, 1);

  // The stream must keep applying frames after the stale answer.
  Flow.InjectWsFrameForTest(MakeLifecycleNextFrame(TEXT("s08-1"), EventWithSeq(Event, 2)));
  TestEqual("stream still applies", Flow.GetAppliedSnapshot().SequenceNumber, 2);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LeaveRejectedKeepsStreamTest,
    "Unmatched.S08.LeaveLifecycle.rejected leave keeps stream; later frames still apply",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LeaveRejectedKeepsStreamTest::RunTest(const FString&) {
  const TSharedPtr<FJsonObject> Event = LifecycleWsEvent();
  if (!Event.IsValid()) {
    AddError("fixture 07 failed to parse");
    return true;
  }
  FS08FlowController Flow(TEXT("http://test.invalid"), TEXT("ws://test.invalid"));
  Flow.SetRoomForTest(TEXT("g-1"), ES08Stage::Started);
  Flow.AttachStreamHarnessForTest(TEXT("g-1"));
  Flow.InjectWsFrameForTest(MakeLifecycleNextFrame(TEXT("s08-1"), EventWithSeq(Event, 5)));
  TestEqual("seq 5 applied", Flow.GetAppliedSnapshot().SequenceNumber, 5);

  int32 LeaveFailures = 0;
  Flow.OnLeaveFailed.AddLambda([&](const FS08GraphQLError&) { ++LeaveFailures; });

  TArray<FS08GraphQLError> Rejection;
  Rejection.Add(FS08GraphQLError{TEXT("FORBIDDEN"), TEXT("leave rejected"), FString()});
  Flow.QueueHttpResultForTest(false, Rejection);
  Flow.LeaveRoom();

  TestEqual("leave failure broadcast", LeaveFailures, 1);
  TestTrue("room retained", Flow.GetRoom().GameId == TEXT("g-1"));
  TestTrue("stage retained", Flow.GetStage() == ES08Stage::Started);
  TestTrue("stream retained", Flow.IsStreamAttached());
  TestTrue("subscription retained", Flow.HasGameStateOpForTest());
  TestEqual("applied seq retained", Flow.GetAppliedSnapshot().SequenceNumber, 5);

  // The FAILED path must not tear the live match down: the next frame applies.
  Flow.InjectWsFrameForTest(MakeLifecycleNextFrame(TEXT("s08-1"), EventWithSeq(Event, 6)));
  TestEqual("later frame applies", Flow.GetAppliedSnapshot().SequenceNumber, 6);
  return true;
}

#endif

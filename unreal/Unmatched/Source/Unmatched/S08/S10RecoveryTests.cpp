// S10 GD-037: recovery after a lost mutation response and a dropped
// subscription (ACC-012). The client must NEVER blindly resend a gameplay
// command whose outcome is unknown: input locks, the authoritative state is
// refetched (bounded, backoff), and any applied/merged body - HTTP refetch or
// live WS - releases the lock. Cues derived from a seq GAP are suppressed:
// the client cannot know the intermediate transitions, so replaying a diff
// across a gap would fabricate "old CUEs" (unmatched-net/1 section 1).
#if WITH_AUTOMATION_TESTS

#include "S08Contracts.h"
#include "S08FlowController.h"
#include "Dom/JsonObject.h"
#include "Misc/AutomationTest.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace {

const TCHAR* HostId = TEXT("p-host");
const TCHAR* GuestId = TEXT("p-guest");
// Refetch failures queued for the exhaustion ladder (one per retry boundary).
constexpr int32 MaxRecoveryRefetchFailures = 5;

FS08Snapshot StartedSnapshot(int32 Seq, const TCHAR* Phase, const TCHAR* TurnPlayer,
                             int32 F1X, int32 F1Y, int32 F1Hp,
                             const TCHAR* MetadataJson = nullptr) {
  FS08Snapshot S;
  S.SequenceNumber = Seq;
  S.Phase = Phase;
  S.TurnCount = 1;
  S.CurrentTurnPlayerId = TurnPlayer;
  FString Problem;
  FS08Contracts::TryParseJsonValue(
      TEXT("[{\"userId\":\"p-host\"},{\"userId\":\"p-guest\"}]"), S.Players, Problem);
  FS08Contracts::TryParseJsonValue(
      FString::Printf(TEXT("[{\"id\":\"f1\",\"health\":%d,\"position\":{\"x\":%d,\"y\":%d}},")
                      TEXT("{\"id\":\"f2\",\"health\":10,\"position\":{\"x\":0,\"y\":0}}]"),
                      F1Hp, F1X, F1Y),
      S.Fighters, Problem);
  FS08Contracts::TryParseJsonValue(
      TEXT("{\"p-host\":[],\"p-guest\":[]}"), S.HandZones, Problem);
  FS08Contracts::TryParseJsonValue(
      TEXT("{\"cells\":[[0,0],[1,0]]}"), S.BoardState, Problem);
  if (MetadataJson) {
    FS08Contracts::TryParseJsonValue(MetadataJson, S.Metadata, Problem);
  }
  return S;
}

/** Fighters projection as the embedded JSON STRING the WS event carries. */
FString FightersProjection(int32 F1X, int32 F1Y, int32 F1Hp) {
  return FString::Printf(
      TEXT("[{\"id\":\"f1\",\"health\":%d,\"position\":{\"x\":%d,\"y\":%d}},")
      TEXT("{\"id\":\"f2\",\"health\":10,\"position\":{\"x\":0,\"y\":0}}]"),
      F1Hp, F1X, F1Y);
}

/** Raw graphql-transport-ws 'next' frame carrying one gameStateUpdated event
 *  with fighters/players encoded as JSON strings (two-stage contract). */
FString WsNextFrame(const FString& OpId, int32 Seq, const TCHAR* Phase,
                    const TCHAR* TurnPlayer, const FString& FightersEscaped,
                    const FString& MetadataEscaped = FString()) {
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
  Event->SetStringField(TEXT("players"),
                        TEXT("[{\"userId\":\"p-host\"},{\"userId\":\"p-guest\"}]"));
  Event->SetStringField(TEXT("fighters"), FightersEscaped);
  Event->SetStringField(TEXT("handZones"), TEXT("{\"p-host\":[],\"p-guest\":[]}"));
  if (!MetadataEscaped.IsEmpty()) {
    Event->SetStringField(TEXT("metadata"), MetadataEscaped);
  }
  Data->SetObjectField(TEXT("gameStateUpdated"), Event);
  Payload->SetObjectField(TEXT("data"), Data);
  Frame->SetObjectField(TEXT("payload"), Payload);
  FString Out;
  auto Writer = TJsonWriterFactory<>::Create(&Out);
  FJsonSerializer::Serialize(Frame, Writer);
  return Out;
}

FS08GraphQLError TransportLost() {
  return FS08GraphQLError{TEXT("TRANSPORT"),
                          TEXT("Network request failed - backend unreachable"), FString()};
}

FS08GraphQLError HttpError(int32 Status) {
  return FS08GraphQLError{TEXT("TRANSPORT"),
                          FString::Printf(TEXT("HTTP %d from server"), Status), FString(),
                          Status};
}

/** HTTP 200 whose body could not be parsed (truncated after server commit). */
FS08GraphQLError ParseFailure(int32 Status = 200) {
  return FS08GraphQLError{TEXT("PARSE"),
                          TEXT("Response is not valid JSON (truncated body)"), FString(),
                          Status};
}

/** gameState query body with an inner state carrying real fighter positions
 *  (two-stage contract: `state` is a JSON string). */
FString GameStateBody(int32 Seq, const TCHAR* Phase, const TCHAR* TurnPlayer,
                      int32 F1X, int32 F1Y, int32 F1Hp) {
  const FString Inner = FString::Printf(
      TEXT("{\"players\":[{\"userId\":\"p-host\"},{\"userId\":\"p-guest\"}],")
      TEXT("\"fighters\":[{\"id\":\"f1\",\"health\":%d,\"position\":{\"x\":%d,\"y\":%d}},")
      TEXT("{\"id\":\"f2\",\"health\":10,\"position\":{\"x\":0,\"y\":0}}],")
      TEXT("\"handZones\":{\"p-host\":[],\"p-guest\":[]}}"),
      F1Hp, F1X, F1Y);
  const FString Escaped = Inner.Replace(TEXT("\""), TEXT("\\\""));
  return FString::Printf(
      TEXT("{\"data\":{\"gameState\":{\"id\":\"gs\",\"gameId\":\"g1\",\"state\":\"%s\",")
      TEXT("\"sequenceNumber\":%d,\"phase\":\"%s\",\"turnCount\":1,")
      TEXT("\"currentTurnPlayerId\":\"%s\",\"updatedAt\":0}}}"),
      *Escaped, Seq, Phase, TurnPlayer);
}

struct FRecoveryCapture {
  int32 Errors = 0;
  TArray<FString> FlowErrorMessages;
  TArray<FString> FlowErrorCodes;
  TArray<FString> Traces;
  struct FCueEvent {
    int32 Seq = 0;
    int32 CueCount = 0;
  };
  TArray<FCueEvent> CueEvents;
  int32 LastAppliedSeq = -1;

  void Bind(FS08FlowController& Flow) {
    Flow.OnFlowError.AddLambda([this](const FS08GraphQLError& E) {
      ++Errors;
      FlowErrorMessages.Add(E.Message);
      FlowErrorCodes.Add(E.Code);
    });
    Flow.OnTrace.AddLambda([this](const FString& Line) { Traces.Add(Line); });
    Flow.OnApplied.AddLambda([this](const FS08Snapshot& S, ES08SeqDecision D) {
      if (D != ES08SeqDecision::Ignore) LastAppliedSeq = S.SequenceNumber;
    });
    Flow.OnCues.AddLambda([this](const TArray<FS08Cue>& Cues) {
      FCueEvent Event;
      Event.CueCount = Cues.Num();
      if (Cues.Num() > 0) Event.Seq = Cues[0].SequenceNumber;
      CueEvents.Add(MoveTemp(Event));
    });
  }

  bool SawTrace(const TCHAR* Needle) const {
    for (const FString& Line : Traces) {
      if (Line.Contains(Needle)) return true;
    }
    return false;
  }

  FString AllTraces() const {
    FString Joined;
    for (const FString& Line : Traces) Joined += Line + TEXT("\n");
    return Joined;
  }
};

} // namespace

// ---- GD-037: lost mutation RESPONSE locks input, refetches, never resends --
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10LostMutationResponseTest,
    "Unmatched.S10.Recovery.lost mutation response locks input and refetches; no resend",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10LostMutationResponseTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FRecoveryCapture Cap;
  Cap.Bind(Flow);
  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  // Baseline authoritative state: the viewer's ACTION_MANEUVER turn.
  Flow.ApplySnapshot(StartedSnapshot(10, TEXT("ACTION_MANEUVER"), HostId, 2, 2, 10));
  TestEqual("baseline applied", Flow.GetAppliedSnapshot().SequenceNumber, 10);
  TestEqual("no sends yet", Flow.GetTestHttpSendCountForTest(), 0);

  // Deferred harness FIFO: [mutation transport loss] -> [recovery refetch ok].
  Flow.QueueHttpResultForTest(false, {TransportLost()}, /*bDeferDelivery=*/true);
  Flow.QueueHttpResultForTest(
      true, {}, /*bDeferDelivery=*/true,
      TEXT("{\"data\":{\"gameState\":{\"id\":\"gs\",\"gameId\":\"g1\",")
      TEXT("\"state\":\"{\\\"players\\\":[{\\\"userId\\\":\\\"p-host\\\"},")
      TEXT("{\\\"userId\\\":\\\"p-guest\\\"}],\\\"fighters\\\":[{\\\"id\\\":\\\"f1\\\"},")
      TEXT("{\\\"id\\\":\\\"f2\\\"}],\\\"handZones\\\":{\\\"p-host\\\":[],")
      TEXT("\\\"p-guest\\\":[]}}\",\"sequenceNumber\":11,")
      TEXT("\"phase\":\"ACTION_MANEUVER\",\"turnCount\":1,")
      TEXT("\"currentTurnPlayerId\":\"p-host\",\"updatedAt\":0}}}"));

  // The beginManeuver answer never arrives (transport loss = outcome unknown:
  // the server may have applied the draw).
  Flow.BeginManeuver();
  TestEqual("mutation leg sent", Flow.GetTestHttpSendCountForTest(), 1);
  Flow.DeliverQueuedHttpForTest(); // transport loss
  TestTrue("outcome unknown -> recovery armed", Flow.IsMutationRecoveryActiveForTest());
  TestTrue("recovery traced (no resend promise)", Cap.SawTrace(TEXT("no resend")));
  TestTrue("lock traced", Cap.SawTrace(TEXT("input locked")));

  // Input gate: a second BeginManeuver during recovery must NOT send.
  FString Reason;
  TestFalse("commands locked during recovery", Flow.CanIssueGameplayCommand(Reason));
  TestTrue("lock reason actionable", Reason.Contains(TEXT("restoring")));
  const int32 SendsBefore = Flow.GetTestHttpSendCountForTest();
  Flow.BeginManeuver();
  TestEqual("no resend while locked", Flow.GetTestHttpSendCountForTest(), SendsBefore);
  TestTrue("blocked send traced", Cap.SawTrace(TEXT("MANEUVER begin blocked")));

  // The auto-refetch (send #2) is answered with the authoritative seq 11:
  // the lost command WAS applied server-side - convergence, no resend.
  TestEqual("recovery refetch sent", Flow.GetTestHttpSendCountForTest(), 2);
  Flow.DeliverQueuedHttpForTest();
  TestFalse("recovery cleared by authoritative state",
            Flow.IsMutationRecoveryActiveForTest());
  TestEqual("converged to server seq", Flow.GetAppliedSnapshot().SequenceNumber, 11);
  TestTrue("unlocks after convergence", Flow.CanIssueGameplayCommand(Reason));
  return true;
}

// ---- GD-037: lost defense response converges through the LIVE WS ----------
// The subscription is still alive; its next event proves the defense applied.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10LostDefenseResponseTest,
    "Unmatched.S10.Recovery.lost defense response converges via live WS snapshot",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10LostDefenseResponseTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), GuestId);
  FRecoveryCapture Cap;
  Cap.Bind(Flow);
  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  // Defender's COMBAT window (viewer = guest = defender; combat gate has no
  // turn-owner check by design).
  Flow.ApplySnapshot(StartedSnapshot(10, TEXT("COMBAT"), HostId, 2, 2, 10));
  FString Reason;
  TestTrue("defense legal at baseline", Flow.CanIssueCombatCommand(Reason));

  Flow.QueueHttpResultForTest(false, {TransportLost()});
  Flow.PlayDefense(TEXT("card-1"));
  TestTrue("outcome unknown -> recovery armed", Flow.IsMutationRecoveryActiveForTest());
  TestFalse("combat commands locked", Flow.CanIssueCombatCommand(Reason));

  // The recovery refetch fails (queue empty; empty URL fails fast) - the
  // bounded retry timer arms instead of spinning.
  TestTrue("first recovery attempt counted", Flow.GetMutationRecoveryAttemptsForTest() >= 1);

  // The live WS delivers the authoritative seq 11: the defense WAS applied,
  // the server moved to COMBAT_RESOLVE. Convergence releases the lock.
  Flow.InjectWsFrameForTest(WsNextFrame(TEXT("s08-1"), 11, TEXT("COMBAT_RESOLVE"), GuestId,
                                        FightersProjection(2, 2, 10)));
  TestEqual("WS state applied", Flow.GetAppliedSnapshot().SequenceNumber, 11);
  TestFalse("recovery cleared by WS snapshot", Flow.IsMutationRecoveryActiveForTest());
  TestTrue("input restored", Flow.CanIssueCombatCommand(Reason));
  return true;
}

// ---- GD-037: bounded recovery refetch with backoff, then a visible error ---
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10RecoveryExhaustionTest,
    "Unmatched.S10.Recovery.refetch retries boundedly then surfaces visible error",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10RecoveryExhaustionTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FRecoveryCapture Cap;
  Cap.Bind(Flow);
  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  Flow.ApplySnapshot(StartedSnapshot(10, TEXT("ACTION_MANEUVER"), HostId, 2, 2, 10));

  // Mutation answer lost; every recovery refetch then fails (queued transport
  // losses keep the ladder deterministic - no reliance on empty-URL HTTP).
  Flow.QueueHttpResultForTest(false, {TransportLost()});
  for (int32 I = 0; I < MaxRecoveryRefetchFailures; ++I) {
    Flow.QueueHttpResultForTest(false, {TransportLost()});
  }
  Flow.BeginManeuver();
  TestTrue("recovery armed", Flow.IsMutationRecoveryActiveForTest());
  TestEqual("attempt 1 (immediate)", Flow.GetMutationRecoveryAttemptsForTest(), 1);

  // Backoff ladder: each timer boundary fires exactly one refetch.
  Flow.TickConnectivity(1.1f);
  TestEqual("attempt 2", Flow.GetMutationRecoveryAttemptsForTest(), 2);
  Flow.TickConnectivity(2.1f);
  TestEqual("attempt 3", Flow.GetMutationRecoveryAttemptsForTest(), 3);
  Flow.TickConnectivity(4.1f);
  TestEqual("attempt 4", Flow.GetMutationRecoveryAttemptsForTest(), 4);
  Flow.TickConnectivity(8.1f);
  TestEqual("attempt 5", Flow.GetMutationRecoveryAttemptsForTest(), 5);

  // Bound reached: visible error, no further refetch, input STAYS locked
  // (any command would be a blind resend).
  TestTrue("exhaustion traced", Cap.SawTrace(TEXT("exhausted")));
  TestTrue("failure surfaced", Cap.FlowErrorCodes.Contains(TEXT("PROTOCOL")));
  const int32 Sends = Flow.GetTestHttpSendCountForTest();
  Flow.TickConnectivity(15.0f);
  Flow.TickConnectivity(15.0f);
  TestEqual("no refetch after exhaustion", Flow.GetMutationRecoveryAttemptsForTest(), 5);
  FString Reason;
  TestFalse("input stays locked", Flow.CanIssueGameplayCommand(Reason));
  return true;
}

// ---- GD-037 + S10 review P1(2): WS frame ordering after a (re)subscribe ------
// The FIRST 'next' a fresh subscription delivers is the server's barrier
// snapshot (state at subscribe time): a reconciliation body, its diff fires no
// cues even when the seq is contiguous (local 10 -> barrier 11). The SECOND
// frame is live again; gaps still suppress; same-seq merges never fire.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10GapCueSuppressionTest,
    "Unmatched.S10.Recovery.WS ordering: barrier frame silent, then live cues, gaps muted",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10GapCueSuppressionTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FRecoveryCapture Cap;
  Cap.Bind(Flow);
  Flow.AttachStreamHarnessForTest(TEXT("g1")); // subscribe since=0: barrier slot armed
  Flow.ApplySnapshot(StartedSnapshot(10, TEXT("ACTION_MANEUVER"), HostId, 2, 2, 10));
  TestEqual("no cues on first apply", Cap.CueEvents.Num(), 0);

  // Barrier frame: CONTIGUOUS 10 -> 11 with a fighter move, but it is the
  // subscription's opening snapshot - the exact P1(2) regression shape. No cue.
  Flow.InjectWsFrameForTest(WsNextFrame(TEXT("s08-1"), 11, TEXT("ACTION_MANEUVER"), HostId,
                                        FightersProjection(3, 2, 10)));
  TestEqual("barrier state applied", Flow.GetAppliedSnapshot().SequenceNumber, 11);
  TestEqual("contiguous barrier frame fires no cues", Cap.CueEvents.Num(), 0);
  TestTrue("barrier suppression traced", Cap.SawTrace(TEXT("barrier body: cues suppressed")));

  // Live frame (11 -> 12, contiguous): exactly one move cue.
  Flow.InjectWsFrameForTest(WsNextFrame(TEXT("s08-1"), 12, TEXT("ACTION_MANEUVER"), HostId,
                                        FightersProjection(4, 2, 10)));
  if (Cap.CueEvents.Num() != 1) {
    AddError(FString::Printf(TEXT("live 11->12: cues=%d appliedSeq=%d traces:\n%s"),
                             Cap.CueEvents.Num(), Flow.GetAppliedSnapshot().SequenceNumber,
                             *Cap.AllTraces()));
  }
  TestEqual("one cue event for the live transition", Cap.CueEvents.Num(), 1);
  if (Cap.CueEvents.Num() >= 1) {
    TestEqual("live cue is the seq-12 move", Cap.CueEvents[0].Seq, 12);
  }

  // GAP (12 -> 15, events 13-14 lost offline): state applies, NO cues - the
  // client cannot know the intermediate transitions, a diff would fabricate
  // stale animations (ACC-012 "old CUEs are not replayed").
  Flow.InjectWsFrameForTest(WsNextFrame(TEXT("s08-1"), 15, TEXT("ACTION_ATTACK"), HostId,
                                        FightersProjection(6, 2, 8)));
  TestEqual("gap state applied", Flow.GetAppliedSnapshot().SequenceNumber, 15);
  TestEqual("no cue events for the gap", Cap.CueEvents.Num(), 1);
  TestTrue("gap suppression traced", Cap.SawTrace(TEXT("gap from")));

  // Same-seq duplicate (15 again): merge, no cue.
  Flow.InjectWsFrameForTest(WsNextFrame(TEXT("s08-1"), 15, TEXT("ACTION_ATTACK"), HostId,
                                        FightersProjection(6, 2, 8)));
  TestEqual("merge fired no cues", Cap.CueEvents.Num(), 1);

  // Next contiguous transition (15 -> 16) fires cues again.
  Flow.InjectWsFrameForTest(WsNextFrame(TEXT("s08-1"), 16, TEXT("ACTION_ATTACK"), HostId,
                                        FightersProjection(7, 2, 8)));
  TestEqual("cues resume after gap", Cap.CueEvents.Num(), 2);
  if (Cap.CueEvents.Num() >= 2) {
    TestEqual("resumed cue seq", Cap.CueEvents[1].Seq, 16);
  }
  return true;
}

// ---- GD-037: outcome classification ----------------------------------------
// HTTP 5xx = the server may have applied the command (unknown outcome) ->
// recovery. A GraphQL rejection = the server ANSWERED (definitely not
// applied) -> normal error, controls unlock.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10OutcomeClassificationTest,
    "Unmatched.S10.Recovery.HTTP 5xx is unknown outcome; GraphQL rejection unlocks",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10OutcomeClassificationTest::RunTest(const FString&) {
  // 5xx: unknown outcome -> recovery.
  {
    FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
    FRecoveryCapture Cap;
    Cap.Bind(Flow);
    Flow.AttachStreamHarnessForTest(TEXT("g1"));
    Flow.ApplySnapshot(StartedSnapshot(10, TEXT("ACTION_MANEUVER"), HostId, 2, 2, 10));
    Flow.QueueHttpResultForTest(false, {HttpError(502)});
    Flow.EndTurn();
    TestTrue("502 arms recovery", Flow.IsMutationRecoveryActiveForTest());
  }
  // GraphQL rejection: answered rejection, no recovery lock.
  {
    FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
    FRecoveryCapture Cap;
    Cap.Bind(Flow);
    Flow.AttachStreamHarnessForTest(TEXT("g1"));
    Flow.ApplySnapshot(StartedSnapshot(10, TEXT("ACTION_MANEUVER"), HostId, 2, 2, 10));
    FS08GraphQLError Rejection{TEXT("GRAPHQL"), TEXT("Invalid phase"), FString()};
    Flow.QueueHttpResultForTest(false, {Rejection});
    Flow.EndTurn();
    TestFalse("answered rejection: no recovery", Flow.IsMutationRecoveryActiveForTest());
    TestTrue("rejection surfaced", Cap.Errors >= 1);
    FString Reason;
    TestTrue("controls unlocked after rejection", Flow.CanIssueGameplayCommand(Reason));
  }
  return true;
}

// ---- GD-037/038: a 429-answered recovery refetch pauses, never hammers ----
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10RecoveryRateLimitTest,
    "Unmatched.S10.Recovery.429-answered recovery refetch stops the retry timer",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10RecoveryRateLimitTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FRecoveryCapture Cap;
  Cap.Bind(Flow);
  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  Flow.ApplySnapshot(StartedSnapshot(10, TEXT("ACTION_MANEUVER"), HostId, 2, 2, 10));

  // Mutation lost; the recovery refetch is answered 429: the bounded retry
  // timer must DISARM (no blind retry) and surface the error.
  Flow.QueueHttpResultForTest(false, {TransportLost()}, /*bDeferDelivery=*/true);
  Flow.QueueHttpResultForTest(false,
                              {FS08GraphQLError{TEXT("RATE_LIMIT"),
                                                TEXT("HTTP 429 from server"), FString(), 429}},
                              /*bDeferDelivery=*/true);
  Flow.BeginManeuver();
  Flow.DeliverQueuedHttpForTest(); // mutation transport loss -> recovery armed
  Flow.DeliverQueuedHttpForTest(); // refetch answered 429
  TestEqual("one recovery attempt, then 429", Flow.GetMutationRecoveryAttemptsForTest(), 1);
  TestTrue("rate limit surfaced", Cap.FlowErrorCodes.Contains(TEXT("RATE_LIMIT")));
  const int32 Sends = Flow.GetTestHttpSendCountForTest();
  Flow.TickConnectivity(15.0f);
  Flow.TickConnectivity(15.0f);
  TestEqual("no refetch after 429", Flow.GetMutationRecoveryAttemptsForTest(), 1);
  TestTrue("recovery stays armed (state still unknown)",
           Flow.IsMutationRecoveryActiveForTest());

  // A live WS snapshot still releases the lock (the 429 pause is not a dead
  // end - the subscription path converges).
  Flow.InjectWsFrameForTest(WsNextFrame(TEXT("s08-1"), 11, TEXT("ACTION_MANEUVER"), HostId,
                                        FightersProjection(2, 2, 10)));
  TestFalse("WS releases the paused recovery", Flow.IsMutationRecoveryActiveForTest());
  return true;
}

// ---- S10 review P1(1): a same-seq STALE WS snapshot must NOT unlock ------
// The lost command's pre-mutation state can still arrive over the live
// subscription (same seq = server never moved). It is a merge, not proof of
// reconciliation: only the fresh recovery read (or a seq past the arm-time
// baseline) releases the lock.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10StaleSnapshotHoldsLockTest,
    "Unmatched.S10.Recovery.stale same-seq WS snapshot keeps the recovery lock",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10StaleSnapshotHoldsLockTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FRecoveryCapture Cap;
  Cap.Bind(Flow);
  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  Flow.ApplySnapshot(StartedSnapshot(10, TEXT("ACTION_MANEUVER"), HostId, 2, 2, 10));

  // Lost mutation answer; the recovery refetch's answer is held back and the
  // server truth it will carry is seq 10 (the command was NEVER applied).
  Flow.QueueHttpResultForTest(false, {TransportLost()}, /*bDeferDelivery=*/true);
  Flow.QueueHttpResultForTest(
      true, {}, /*bDeferDelivery=*/true,
      GameStateBody(10, TEXT("ACTION_MANEUVER"), HostId, 2, 2, 10));

  Flow.BeginManeuver();                       // send 1 (deferred)
  Flow.DeliverQueuedHttpForTest();            // transport loss -> lock armed
  TestTrue("recovery armed", Flow.IsMutationRecoveryActiveForTest());
  TestEqual("refetch dispatched under the lock", Flow.GetTestHttpSendCountForTest(), 2);

  // Stale same-seq WS snapshot (the pre-command state re-pushed): merge, but
  // it is NOT fresher than the arm-time baseline 10 - the lock holds.
  Flow.InjectWsFrameForTest(WsNextFrame(TEXT("s08-1"), 10, TEXT("ACTION_MANEUVER"), HostId,
                                        FightersProjection(2, 2, 10)));
  TestTrue("stale same-seq WS keeps the lock", Flow.IsMutationRecoveryActiveForTest());
  TestTrue("hold traced", Cap.SawTrace(TEXT("RECOVERY held")));
  FString Reason;
  TestFalse("commands stay locked", Flow.CanIssueGameplayCommand(Reason));

  // The fresh recovery read (dispatched under the lock) proves the CURRENT
  // server state is still seq 10 - outcome known (not applied) - and only
  // now the lock releases.
  Flow.DeliverQueuedHttpForTest();
  TestFalse("fresh read releases the lock", Flow.IsMutationRecoveryActiveForTest());
  TestTrue("completion traced", Cap.SawTrace(TEXT("RECOVERY complete")));
  TestTrue("commands restored", Flow.CanIssueGameplayCommand(Reason));
  return true;
}

// ---- S10 review P1(1) reverse: a FRESH WS seq past the baseline unlocks ---
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10FreshWsReleasesLockTest,
    "Unmatched.S10.Recovery.WS seq past the arm baseline releases the lock",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10FreshWsReleasesLockTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FRecoveryCapture Cap;
  Cap.Bind(Flow);
  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  Flow.ApplySnapshot(StartedSnapshot(10, TEXT("ACTION_MANEUVER"), HostId, 2, 2, 10));

  // Consume the subscription's barrier slot BEFORE the loss, so the seq-11
  // frame below is a LIVE transition (same-seq merge carries no cues either).
  Flow.InjectWsFrameForTest(WsNextFrame(TEXT("s08-1"), 10, TEXT("ACTION_MANEUVER"), HostId,
                                        FightersProjection(2, 2, 10)));

  Flow.QueueHttpResultForTest(false, {TransportLost()}, /*bDeferDelivery=*/true);
  Flow.QueueHttpResultForTest(
      true, {}, /*bDeferDelivery=*/true,
      GameStateBody(11, TEXT("ACTION_MANEUVER"), HostId, 3, 2, 10));
  Flow.BeginManeuver();                       // send 1 (deferred)
  Flow.DeliverQueuedHttpForTest();            // loss -> armed; refetch send 2 held

  // The live WS delivers seq 11 (> baseline 10): the command WAS applied -
  // fresh authoritative evidence releases the lock even before the HTTP
  // refetch answer lands.
  Flow.InjectWsFrameForTest(WsNextFrame(TEXT("s08-1"), 11, TEXT("ACTION_MANEUVER"), HostId,
                                        FightersProjection(3, 2, 10)));
  TestFalse("fresh WS seq releases the lock", Flow.IsMutationRecoveryActiveForTest());
  TestEqual("state applied", Flow.GetAppliedSnapshot().SequenceNumber, 11);

  // The late HTTP refetch of the same seq merges without double cues.
  Flow.DeliverQueuedHttpForTest();
  TestEqual("same seq merged", Flow.GetAppliedSnapshot().SequenceNumber, 11);
  TestEqual("exactly one live cue event", Cap.CueEvents.Num(), 1);
  return true;
}

// ---- S10 review P1(2): unreadable HTTP 200 after commit = unknown ---------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10TruncatedMutationReplyTest,
    "Unmatched.S10.Recovery.truncated or malformed mutation reply locks recovery",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10TruncatedMutationReplyTest::RunTest(const FString&) {
  // (a) HTTP 200 with a truncated body: JSON parse fails after the server
  // answered - outcome unknown, never a manual resend.
  {
    FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
    FRecoveryCapture Cap;
    Cap.Bind(Flow);
    Flow.AttachStreamHarnessForTest(TEXT("g1"));
    Flow.ApplySnapshot(StartedSnapshot(10, TEXT("ACTION_MANEUVER"), HostId, 2, 2, 10));
    Flow.QueueHttpResultForTest(false, {ParseFailure()});
    Flow.EndTurn();
    TestTrue("truncated 200 arms recovery", Flow.IsMutationRecoveryActiveForTest());
    TestTrue("no-resend promise traced", Cap.SawTrace(TEXT("no resend")));
    FString Reason;
    TestFalse("controls locked", Flow.CanIssueGameplayCommand(Reason));
    TestEqual("no error broadcast (recovery owns the surface)", Cap.Errors, 0);
  }
  // (b) HTTP 200, valid JSON, but the mutation payload is unusable
  // (data:null): the parse tail must arm recovery the same way.
  {
    FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
    FRecoveryCapture Cap;
    Cap.Bind(Flow);
    Flow.AttachStreamHarnessForTest(TEXT("g1"));
    Flow.ApplySnapshot(StartedSnapshot(10, TEXT("ACTION_MANEUVER"), HostId, 2, 2, 10));
    Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/false,
                                TEXT("{\"data\":null}"));
    Flow.EndTurn();
    TestTrue("unusable payload arms recovery", Flow.IsMutationRecoveryActiveForTest());
    TestTrue("parse-failure recovery traced",
             Cap.SawTrace(TEXT("ENDTURN parse error: outcome unknown")));
  }
  return true;
}

// ---- S10 review P1(3): barrier/recovery bodies fire NO cues at any gap ----
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10BarrierCueSuppressionTest,
    "Unmatched.S10.Recovery.barrier body with a contiguous move fires no cues",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10BarrierCueSuppressionTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FRecoveryCapture Cap;
  Cap.Bind(Flow);
  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  Flow.ApplySnapshot(StartedSnapshot(10, TEXT("ACTION_MANEUVER"), HostId, 2, 2, 10));

  // Recovery refetch returns seq 11 with f1 moved to (3,2): contiguous with
  // the local 10, but it is an HTTP barrier read, not a live transition -
  // the diff must NOT fire a move cue.
  Flow.QueueHttpResultForTest(false, {TransportLost()}, /*bDeferDelivery=*/true);
  Flow.QueueHttpResultForTest(
      true, {}, /*bDeferDelivery=*/true,
      GameStateBody(11, TEXT("ACTION_MANEUVER"), HostId, 3, 2, 10));
  Flow.BeginManeuver();
  Flow.DeliverQueuedHttpForTest(); // loss -> armed; refetch dispatched (held)
  Flow.DeliverQueuedHttpForTest(); // barrier body seq 11 applied
  TestEqual("barrier state applied", Flow.GetAppliedSnapshot().SequenceNumber, 11);
  TestEqual("no cue events for the barrier body", Cap.CueEvents.Num(), 0);
  TestTrue("barrier suppression traced", Cap.SawTrace(TEXT("barrier body: cues suppressed")));

  // The NEXT live WS transition (11 -> 12) fires cues again - suppression is
  // scoped to reconciliation bodies, not a permanent mute.
  Flow.InjectWsFrameForTest(WsNextFrame(TEXT("s08-1"), 12, TEXT("ACTION_MANEUVER"), HostId,
                                        FightersProjection(4, 2, 10)));
  TestEqual("live cues resume", Cap.CueEvents.Num(), 1);
  if (Cap.CueEvents.Num() >= 1) {
    TestEqual("resumed cue is the seq-12 move", Cap.CueEvents[0].Seq, 12);
  }
  return true;
}

// ---- S10 review P2(5): 401 on a mutation - refresh once, never replay -----
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10MutationAuthRefreshTest,
    "Unmatched.S10.Recovery.401 gameplay mutation refreshes once and refetches state; no replay",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10MutationAuthRefreshTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FRecoveryCapture Cap;
  Cap.Bind(Flow);
  Flow.SetAuthForTest(TEXT("access-1"), TEXT("refresh-1"));
  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  Flow.ApplySnapshot(StartedSnapshot(10, TEXT("ACTION_ATTACK"), HostId, 2, 2, 10));

  // Deferred FIFO: [attack 401] -> [refresh ok] -> [authoritative state 11].
  Flow.QueueHttpResultForTest(false,
                              {FS08GraphQLError{TEXT("AUTH"),
                                                TEXT("HTTP 401 from server"), FString(), 401}},
                              /*bDeferDelivery=*/true);
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true,
                              TEXT("{\"data\":{\"refreshTokens\":{\"accessToken\":\"access-2\",")
                              TEXT("\"refreshToken\":\"refresh-2\",\"user\":{\"id\":\"p-host\",")
                              TEXT("\"username\":\"h\"}}}}"));
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true,
                              GameStateBody(11, TEXT("ACTION_ATTACK"), HostId, 2, 2, 10));

  Flow.Attack(TEXT("f1"), TEXT("card-1"), TEXT("f2"));
  Flow.DeliverQueuedHttpForTest(); // 401: answered rejection -> refresh path
  TestEqual("one refresh issued", Flow.GetRefreshCountForTest(), 1);
  TestTrue("no-replay traced", Cap.SawTrace(TEXT("command is not sent again")));
  TestFalse("no recovery lock for an answered 401",
            Flow.IsMutationRecoveryActiveForTest());
  Flow.DeliverQueuedHttpForTest(); // refresh ok -> rotation + state refetch
  Flow.DeliverQueuedHttpForTest(); // authoritative state applied
  TestEqual("state converged after refresh", Flow.GetAppliedSnapshot().SequenceNumber, 11);
  // attack, refresh, state refetch - and NOTHING else (no mutation replay).
  TestEqual("exactly three sends (no replay)", Flow.GetTestHttpSendCountForTest(), 3);
  return true;
}

// ---- S10 review P2(6): commands gate on a live, acked state stream --------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10StreamGateTest,
    "Unmatched.S10.Recovery.commands are gated until the state stream is ready",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10StreamGateTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FRecoveryCapture Cap;
  Cap.Bind(Flow);
  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  Flow.ApplySnapshot(StartedSnapshot(10, TEXT("ACTION_MANEUVER"), HostId, 2, 2, 10));
  FString Reason;
  TestTrue("commands allowed while acked", Flow.CanIssueGameplayCommand(Reason));
  TestTrue("stream ready", Flow.IsStreamReady());

  // Transport loss: the socket object survives but is no longer acked - the
  // banner's "input locked" promise is now real: no command leaves.
  Flow.DropWsForTest();
  TestFalse("stream not ready after drop", Flow.IsStreamReady());
  TestFalse("commands blocked while reconnecting", Flow.CanIssueGameplayCommand(Reason));
  TestTrue("block reason names the stream", Reason.Contains(TEXT("state stream")));
  const int32 Sends = Flow.GetTestHttpSendCountForTest();
  Flow.BeginManeuver();
  TestEqual("no send while the stream is down", Flow.GetTestHttpSendCountForTest(), Sends);
  TestTrue("blocked send traced", Cap.SawTrace(TEXT("MANEUVER begin blocked")));

  // A re-acked stream reopens the gate.
  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  Flow.ApplySnapshot(StartedSnapshot(10, TEXT("ACTION_MANEUVER"), HostId, 2, 2, 10));
  TestTrue("stream ready again", Flow.IsStreamReady());
  TestTrue("commands allowed after re-ack", Flow.CanIssueGameplayCommand(Reason));
  return true;
}

// ---- S10 review P2(8): a lost pending-choice resolve holds until the choice
// is REALLY settled - an unrelated seq advance must not release the lock ------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10PendingChoiceFaultTest,
    "Unmatched.S10.Recovery.pending choice lock holds through unrelated seq advances",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10PendingChoiceFaultTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FRecoveryCapture Cap;
  Cap.Bind(Flow);
  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  // Real pending head: metadata.pendingEffects[0] = eff-1 (BOOST_CHOICE).
  const TCHAR* PendingMeta =
      TEXT("{\"pendingEffects\":[{\"id\":\"eff-1\",\"playerId\":\"p-host\",")
      TEXT("\"type\":\"BOOST_CHOICE\",\"optional\":true}]}");
  Flow.ApplySnapshot(StartedSnapshot(10, TEXT("COMBAT"), HostId, 2, 2, 10, PendingMeta));

  Flow.QueueHttpResultForTest(false, {TransportLost()}, /*bDeferDelivery=*/true);
  Flow.ResolvePendingEffect(TEXT("eff-1"), FString(), false, 0, 0, false, 0, {});
  Flow.DeliverQueuedHttpForTest(); // transport loss -> recovery armed
  TestTrue("outcome unknown -> recovery armed", Flow.IsMutationRecoveryActiveForTest());
  TestEqual("lock holds on the real pending id",
            Flow.GetMutationRecoveryPendingChoiceIdForTest(), TEXT("eff-1"));
  FString Reason;
  TestFalse("combat commands locked", Flow.CanIssueCombatCommand(Reason));

  // UNRELATED seq advance (11, turn passes to the guest) while eff-1 is STILL
  // in the server queue: fresh seq alone proves nothing - the lock must hold.
  Flow.InjectWsFrameForTest(WsNextFrame(TEXT("s08-1"), 11, TEXT("COMBAT"), GuestId,
                                        FightersProjection(2, 2, 10), PendingMeta));
  TestEqual("unrelated advance applied", Flow.GetAppliedSnapshot().SequenceNumber, 11);
  TestTrue("lock holds while the choice is still open",
           Flow.IsMutationRecoveryActiveForTest());
  TestTrue("hold traced with the pending id",
           Cap.SawTrace(TEXT("RECOVERY held: pending choice eff-1 is still open")));
  TestFalse("commands stay locked", Flow.CanIssueCombatCommand(Reason));

  // The choice settles server-side (eff-1 gone from the queue at seq 12):
  // authoritative outcome determined - only now the lock releases.
  const TCHAR* SettledMeta = TEXT("{\"pendingEffects\":[]}");
  Flow.InjectWsFrameForTest(WsNextFrame(TEXT("s08-1"), 12, TEXT("COMBAT_RESOLVE"), HostId,
                                        FightersProjection(2, 2, 10), SettledMeta));
  TestFalse("lock released once the choice settled",
            Flow.IsMutationRecoveryActiveForTest());
  TestTrue("commands restored", Flow.CanIssueCombatCommand(Reason));
  return true;
}

// ---- S10 review P1(4): an unparseable HTTP 200 recovery read re-arms the
// bounded ladder instead of hanging the mutation lock forever ------------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10RecoveryReadParseFailureTest,
    "Unmatched.S10.Recovery.malformed recovery read retries the ladder instead of hanging",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10RecoveryReadParseFailureTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FRecoveryCapture Cap;
  Cap.Bind(Flow);
  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  Flow.ApplySnapshot(StartedSnapshot(10, TEXT("ACTION_MANEUVER"), HostId, 2, 2, 10));

  // Deferred FIFO: [mutation loss] -> [refetch HTTP 200 with garbage body]
  // -> [second refetch, healthy].
  Flow.QueueHttpResultForTest(false, {TransportLost()}, /*bDeferDelivery=*/true);
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true,
                              TEXT("{\"data\":{\"gameState\":{\"state\":\"NOT-JSON"));
  Flow.QueueHttpResultForTest(
      true, {}, /*bDeferDelivery=*/true,
      GameStateBody(11, TEXT("ACTION_MANEUVER"), HostId, 3, 2, 10));
  Flow.BeginManeuver();
  Flow.DeliverQueuedHttpForTest(); // loss -> armed, refetch 1 dispatched (held)
  TestEqual("refetch attempt 1 dispatched", Flow.GetMutationRecoveryAttemptsForTest(), 1);

  // HTTP 200, body unparseable: a FAILED read for the lock - the ladder must
  // re-arm (not disarm) and the lock must stay.
  Flow.DeliverQueuedHttpForTest();
  TestEqual("parse failure counted one attempt, no extra sends",
            Flow.GetMutationRecoveryAttemptsForTest(), 1);
  TestTrue("refetch retry armed", Cap.SawTrace(TEXT("RECOVERY refetch failed - retry in")));
  TestTrue("parse error traced", Cap.SawTrace(TEXT("STATE parse error")));
  TestTrue("lock survives the malformed read", Flow.IsMutationRecoveryActiveForTest());
  TestTrue("no premature flow error (lock owns the surface)", Cap.Errors == 0);

  // The retry boundary fires the second refetch; the healthy body converges.
  Flow.TickConnectivity(1.1f);
  TestEqual("refetch attempt 2 dispatched", Flow.GetMutationRecoveryAttemptsForTest(), 2);
  Flow.DeliverQueuedHttpForTest();
  TestFalse("healthy read releases the lock", Flow.IsMutationRecoveryActiveForTest());
  TestEqual("converged", Flow.GetAppliedSnapshot().SequenceNumber, 11);
  return true;
}

// ---- S10 review P1(3): an acked socket with a DEAD subscription is not ready -
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10SubscribeFailureStreamGateTest,
    "Unmatched.S10.Recovery.acked socket with dead subscription fails the stream gate",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10SubscribeFailureStreamGateTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FRecoveryCapture Cap;
  Cap.Bind(Flow);
  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  Flow.ApplySnapshot(StartedSnapshot(10, TEXT("ACTION_MANEUVER"), HostId, 2, 2, 10));
  TestTrue("ready while subscribed and reconciled", Flow.IsStreamReady());

  // The operation dies (server 'complete'/'error'): op id cleared, socket
  // STILL acked - the gate must be CLOSED regardless (P1(3) regression: an
  // acked socket alone passed it). The operation-level recovery immediately
  // dispatches an HTTP barrier read (queued BEFORE the kill so the harness
  // owns it).
  Flow.QueueHttpResultForTest(
      true, {}, /*bDeferDelivery=*/true,
      GameStateBody(11, TEXT("ACTION_MANEUVER"), HostId, 2, 2, 10));
  Flow.InjectWsFrameForTest(TEXT("{\"type\":\"complete\",\"id\":\"s08-1\"}"));
  TestFalse("not ready after the subscription died", Flow.IsStreamReady());
  FString Reason;
  TestFalse("commands gated while unreconciled", Flow.CanIssueGameplayCommand(Reason));
  const int32 Sends = Flow.GetTestHttpSendCountForTest();
  Flow.BeginManeuver();
  TestEqual("no send through the dead stream", Flow.GetTestHttpSendCountForTest(), Sends);

  // The barrier read the recovery dispatched reconciles the stream.
  Flow.DeliverQueuedHttpForTest();
  TestTrue("resubscribed with a live op id", Flow.HasGameStateOpForTest());
  TestTrue("reconciled after the barrier read", Flow.IsStreamReconciledForTest());
  TestTrue("stream ready again", Flow.IsStreamReady());
  TestTrue("commands re-allowed", Flow.CanIssueGameplayCommand(Reason));
  return true;
}

// ---- S10 packaged-run P1 regression: a gate-blocked command must report it --
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10BlockedCommandReturnsFalseTest,
    "Unmatched.S10.Recovery.gate-blocked command returns false without sending",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10BlockedCommandReturnsFalseTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FRecoveryCapture Cap;
  Cap.Bind(Flow);
  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  Flow.ApplySnapshot(StartedSnapshot(10, TEXT("ACTION_MANEUVER"), HostId, 2, 2, 10));

  // Happy path: dispatched commands return true.
  Flow.QueueHttpResultForTest(false, {TransportLost()}, /*bDeferDelivery=*/true);
  TestTrue("open gate dispatches", Flow.BeginManeuver());
  Flow.DeliverQueuedHttpForTest(); // transport loss -> recovery armed

  // Blocked path (the packaged-run shape): the gate is closed (recovery lock),
  // the command returns FALSE and nothing is sent - GameMode/S09AUTO must key
  // their "sent" logs and mode advances off this return value.
  const int32 Sends = Flow.GetTestHttpSendCountForTest();
  TestFalse("locked gate returns false", Flow.BeginManeuver());
  TestFalse("attack returns false through the lock",
            Flow.Attack(TEXT("f1"), TEXT("card-1"), TEXT("f2")));
  TestFalse("endTurn returns false through the lock", Flow.EndTurn());
  TestEqual("no send happened", Flow.GetTestHttpSendCountForTest(), Sends);
  return true;
}

#endif

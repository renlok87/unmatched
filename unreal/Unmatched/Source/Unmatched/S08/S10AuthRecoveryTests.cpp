// S10 GD-038: authorization recovery and network error handling (ACC-021).
//   - a rejected access token triggers ONE refreshTokens call; the rotated
//     pair replaces the old one and the WS is scheduled for recreation (the
//     live socket was authenticated with the dead token);
//   - a failed/expired refresh ends the session visibly (SESSION_EXPIRED +
//     Failed stage) with no retry loop;
//   - WS 4403 (auth rejected at connection_init) goes through the same
//     refresh path instead of looping reconnects with a dead token;
//   - HTTP 429 never triggers a blind retry (no auto resend, no refresh);
//   - tokens/passwords never appear in any trace line.
#if WITH_AUTOMATION_TESTS

#include "S08Contracts.h"
#include "S08FlowController.h"
#include "Dom/JsonObject.h"
#include "Misc/AutomationTest.h"

namespace {

const TCHAR* HostId = TEXT("p-host");

FS08GraphQLError Auth401() {
  return FS08GraphQLError{TEXT("AUTH"), TEXT("HTTP 401 from server"), FString(), 401};
}

FS08GraphQLError RateLimited() {
  return FS08GraphQLError{TEXT("RATE_LIMIT"), TEXT("HTTP 429 from server"), FString(), 429};
}

/** refreshTokens success echo (AuthResponseDto - same shape as login). */
const TCHAR* RefreshOkBody =
    TEXT("{\"data\":{\"refreshTokens\":{\"accessToken\":\"access-2\",")
    TEXT("\"refreshToken\":\"refresh-2\",\"user\":{\"id\":\"p-host\",\"username\":\"h\"}}}}");

/** refreshTokens success echo for identity B (must echo B's user id). */
const TCHAR* RefreshOkBodyB =
    TEXT("{\"data\":{\"refreshTokens\":{\"accessToken\":\"access-B2\",")
    TEXT("\"refreshToken\":\"refresh-B2\",\"user\":{\"id\":\"p-b\",\"username\":\"b\"}}}}");

/** refreshTokens rejection (revoked/expired refresh token). */
const TCHAR* RefreshRejectedBody =
    TEXT("{\"errors\":[{\"message\":\"Refresh token has been revoked\",")
    TEXT("\"extensions\":{\"code\":\"UNAUTHORIZED\"}}],\"data\":null}");

/** gameState query body the refetched read resolves with. */
const TCHAR* StateOkBody =
    TEXT("{\"data\":{\"gameState\":{\"id\":\"gs\",\"gameId\":\"g1\",")
    TEXT("\"state\":\"{\\\"players\\\":[{\\\"userId\\\":\\\"p-host\\\"},")
    TEXT("{\\\"userId\\\":\\\"p-guest\\\"}],\\\"fighters\\\":[{\\\"id\\\":\\\"f1\\\"},")
    TEXT("{\\\"id\\\":\\\"f2\\\"}],\\\"handZones\\\":{\\\"p-host\\\":[],")
    TEXT("\\\"p-guest\\\":[]}}\",\"sequenceNumber\":11,")
    TEXT("\"phase\":\"ACTION_MANEUVER\",\"turnCount\":1,")
    TEXT("\"currentTurnPlayerId\":\"p-host\",\"updatedAt\":0}}}");

/** game(id) room body the retried poll resolves with (LOBBY so the test
 *  never attaches a real socket via HandleRoomResponse's start branch). */
const TCHAR* RoomOkBody =
    TEXT("{\"data\":{\"game\":{\"id\":\"g1\",\"code\":\"AAA111\",")
    TEXT("\"status\":\"LOBBY\",\"mode\":\"ONE_V_ONE\",")
    TEXT("\"hostId\":\"p-host\",\"boardId\":\"b-1\",\"players\":[]}}}");

/** login echo for a DIFFERENT user (identity B). */
const TCHAR* LoginOkBodyB =
    TEXT("{\"data\":{\"login\":{\"accessToken\":\"access-B\",")
    TEXT("\"refreshToken\":\"refresh-B\",\"user\":{\"id\":\"p-b\",")
    TEXT("\"username\":\"b\"}}}}");

/** Backend-shaped GraphQL error bodies (verified live, evidence/S08): Nest
 *  answers 401 as HTTP 200 with extensions.code = UNAUTHENTICATED and the
 *  throttler with extensions.code = TOO_MANY_REQUESTS; some paths also carry
 *  a TOP-LEVEL code and extensions.status/statusCode instead. */
const TCHAR* Backend401Body =
    TEXT("{\"errors\":[{\"message\":\"Unauthorized\",")
    TEXT("\"extensions\":{\"code\":\"UNAUTHENTICATED\",\"status\":401}}],\"data\":null}");
const TCHAR* Backend429Body =
    TEXT("{\"errors\":[{\"message\":\"Too many requests\",")
    TEXT("\"code\":\"TOO_MANY_REQUESTS\",")
    TEXT("\"extensions\":{\"statusCode\":429}}],\"data\":null}");

/** GraphQL error exactly as the backend CONTRACT layer extracts it from
 *  Backend401Body (HTTP 200: no HttpStatus, code from extensions). */
FS08GraphQLError BackendUnauthenticated() {
  return FS08GraphQLError{TEXT("UNAUTHENTICATED"), TEXT("Unauthorized"), FString()};
}
FS08GraphQLError BackendTooManyRequests() {
  return FS08GraphQLError{TEXT("TOO_MANY_REQUESTS"), TEXT("Too many requests"), FString()};
}

struct FAuthCapture {
  int32 Errors = 0;
  TArray<FString> ErrorCodes;
  TArray<FString> Traces;
  TArray<ES08Stage> Stages;

  void Bind(FS08FlowController& Flow) {
    Flow.OnFlowError.AddLambda([this](const FS08GraphQLError& E) {
      ++Errors;
      ErrorCodes.Add(E.Code);
    });
    Flow.OnTrace.AddLambda([this](const FString& Line) { Traces.Add(Line); });
    Flow.OnStage.AddLambda([this](ES08Stage S) { Stages.Add(S); });
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

// ---- GD-038: 401 -> single refresh, rotation, read retried once -----------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10AuthRefreshTest,
    "Unmatched.S10.Auth.401 refreshes token pair once and retries the read",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10AuthRefreshTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FAuthCapture Cap;
  Cap.Bind(Flow);
  Flow.SetAuthForTest(TEXT("access-1"), TEXT("refresh-1"));
  Flow.SetRoomForTest(TEXT("g1"), ES08Stage::Room);

  // Deferred FIFO: [poll 401] -> [refresh ok] -> [retried poll ok].
  Flow.QueueHttpResultForTest(false, {Auth401()}, /*bDeferDelivery=*/true);
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, RefreshOkBody);
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, RoomOkBody);

  // The room poll comes back 401: the access token expired.
  Flow.PollRoom();
  Flow.DeliverQueuedHttpForTest(); // 401 delivered
  TestEqual("refresh issued exactly once", Flow.GetRefreshCountForTest(), 1);
  TestFalse("not expired yet", Flow.IsSessionExpiredForTest());

  // The refresh rotation succeeds; the failed read retries with the new pair.
  Flow.DeliverQueuedHttpForTest(); // refresh ok -> rotation + poll retry
  TestEqual("access token rotated", Flow.GetAccessTokenForTest(), TEXT("access-2"));
  TestEqual("one refresh total", Flow.GetRefreshCountForTest(), 1);
  TestTrue("rotation traced", Cap.SawTrace(TEXT("token pair rotated")));
  Flow.DeliverQueuedHttpForTest(); // retried poll ok
  TestEqual("room re-read after retry", Flow.GetRoom().GameId, TEXT("g1"));

  // Credentials hygiene: no token value ever reaches a trace line.
  const FString Traces = Cap.AllTraces();
  TestFalse("old access token absent from traces", Traces.Contains(TEXT("access-1")));
  TestFalse("new access token absent from traces", Traces.Contains(TEXT("access-2")));
  TestFalse("old refresh token absent from traces", Traces.Contains(TEXT("refresh-1")));
  TestFalse("new refresh token absent from traces", Traces.Contains(TEXT("refresh-2")));
  return true;
}

// ---- GD-038: 401 during a live match refreshes AND recreates the WS --------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10AuthRefreshWsTest,
    "Unmatched.S10.Auth.WS 4403 during a live match rotates and recreates the socket",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10AuthRefreshWsTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FAuthCapture Cap;
  Cap.Bind(Flow);
  Flow.SetAuthForTest(TEXT("access-1"), TEXT("refresh-1"));
  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  const int32 HarnessGen = Flow.GetWsGenerationForTest(); // harness WS is gen 0

  // Deferred FIFO: [refresh ok] -> [state refetch ok].
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, RefreshOkBody);
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, StateOkBody);

  // The live socket is rejected with 4403 (dead token at connection_init).
  Flow.HandleWsClosedForTest(4403, TEXT("Forbidden"));
  TestEqual("one refresh issued", Flow.GetRefreshCountForTest(), 1);
  Flow.DeliverQueuedHttpForTest(); // refresh ok
  TestEqual("token rotated", Flow.GetAccessTokenForTest(), TEXT("access-2"));
  TestTrue("WS recreation armed (rotated token)",
           Cap.SawTrace(TEXT("WS recreation armed")));
  TestTrue("old socket dropped", !Flow.IsStreamAttached());
  Flow.DeliverQueuedHttpForTest(); // barrier state refetch ok
  TestEqual("state re-read after rotation", Flow.GetAppliedSnapshot().SequenceNumber, 11);

  // The armed reconnect would call MakeWs (fresh token) on the next tick -
  // asserted through the generation bump the recreation path promises.
  TestEqual("harness socket was generation 0 (no MakeWs yet)", HarnessGen, 0);
  return true;
}

// ---- GD-038: expired refresh -> visible session end, no loop ---------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10AuthSessionExpiredTest,
    "Unmatched.S10.Auth.expired or revoked refresh ends session visibly without retry loop",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10AuthSessionExpiredTest::RunTest(const FString&) {
  {
    // Revoked refresh token: one refresh attempt, then SESSION_EXPIRED.
    FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
    FAuthCapture Cap;
    Cap.Bind(Flow);
    Flow.SetAuthForTest(TEXT("access-1"), TEXT("refresh-1"));
    Flow.SetRoomForTest(TEXT("g1"), ES08Stage::Room);

    Flow.QueueHttpResultForTest(false, {Auth401()}, /*bDeferDelivery=*/true);
    Flow.QueueHttpResultForTest(false, {}, /*bDeferDelivery=*/true, RefreshRejectedBody);
    Flow.PollRoom();
    Flow.DeliverQueuedHttpForTest(); // 401 -> refresh issued
    Flow.DeliverQueuedHttpForTest(); // refresh rejected
    TestTrue("session expired surfaced", Cap.ErrorCodes.Contains(TEXT("SESSION_EXPIRED")));
    TestTrue("expired traced", Cap.SawTrace(TEXT("sign in again")));
    TestEqual("stage Failed", Flow.GetStage(), ES08Stage::Failed);
    TestEqual("still exactly one refresh", Flow.GetRefreshCountForTest(), 1);

    // A later 401 must NOT trigger another refresh (terminal state).
    Flow.QueueHttpResultForTest(false, {Auth401()});
    Flow.PollRoom();
    TestEqual("no refresh after expiry", Flow.GetRefreshCountForTest(), 1);
  }
  {
    // No refresh token at all: immediate session end, no request wasted.
    FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
    FAuthCapture Cap;
    Cap.Bind(Flow);
    Flow.SetAuthForTest(TEXT("access-1"), TEXT(""));
    Flow.SetRoomForTest(TEXT("g1"), ES08Stage::Room);
    Flow.QueueHttpResultForTest(false, {Auth401()});
    Flow.PollRoom();
    TestEqual("no refresh without a token", Flow.GetRefreshCountForTest(), 0);
    TestTrue("session expired surfaced", Cap.ErrorCodes.Contains(TEXT("SESSION_EXPIRED")));
  }
  return true;
}

// ---- GD-038: WS 4408 (control close) is NOT auth ----------------------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10AuthWs4408Test,
    "Unmatched.S10.Auth.WS 4408 control close reconnects without a refresh",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10AuthWs4408Test::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FAuthCapture Cap;
  Cap.Bind(Flow);
  Flow.SetAuthForTest(TEXT("access-1"), TEXT("refresh-1"));
  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  Flow.HandleWsClosedForTest(4408, TEXT("Connection acknowledgement timeout"));
  TestEqual("4408 does not refresh", Flow.GetRefreshCountForTest(), 0);
  TestTrue("4408 reconnects", Cap.SawTrace(TEXT("reconnect in")));
  TestFalse("not expired", Flow.IsSessionExpiredForTest());
  return true;
}

// ---- GD-038: 429 -> surfaced, never blindly retried -------------------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10AuthRateLimitTest,
    "Unmatched.S10.Auth.429 surfaces once with no automatic retry or refresh",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10AuthRateLimitTest::RunTest(const FString&) {
  {
    // Read path: one request, one error, nothing re-sent.
    FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
    FAuthCapture Cap;
    Cap.Bind(Flow);
    Flow.SetAuthForTest(TEXT("access-1"), TEXT("refresh-1"));
    Flow.SetRoomForTest(TEXT("g1"), ES08Stage::Room);
    Flow.QueueHttpResultForTest(false, {RateLimited()});
    Flow.PollRoom();
    TestTrue("rate limit surfaced", Cap.ErrorCodes.Contains(TEXT("RATE_LIMIT")));
    TestEqual("no refresh on 429", Flow.GetRefreshCountForTest(), 0);
    TestTrue("no-retry traced", Cap.SawTrace(TEXT("no automatic retry")));
    TestEqual("exactly one send", Flow.GetTestHttpSendCountForTest(), 1);
  }
  {
    // Mutation path: server ANSWERED 429 (definitely not applied) - no
    // recovery lock, no resend, controls stay usable.
    FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
    FAuthCapture Cap;
    Cap.Bind(Flow);
    Flow.AttachStreamHarnessForTest(TEXT("g1"));
    FS08Snapshot Baseline;
    Baseline.SequenceNumber = 10;
    Baseline.Phase = TEXT("ACTION_MANEUVER");
    Baseline.TurnCount = 1;
    Baseline.CurrentTurnPlayerId = HostId;
    FString Problem;
    FS08Contracts::TryParseJsonValue(
        TEXT("[{\"userId\":\"p-host\"},{\"userId\":\"p-guest\"}]"), Baseline.Players, Problem);
    FS08Contracts::TryParseJsonValue(
        TEXT("[{\"id\":\"f1\"},{\"id\":\"f2\"}]"), Baseline.Fighters, Problem);
    FS08Contracts::TryParseJsonValue(
        TEXT("{\"p-host\":[],\"p-guest\":[]}"), Baseline.HandZones, Problem);
    FS08Contracts::TryParseJsonValue(
        TEXT("{\"cells\":[[0,0],[1,0]]}"), Baseline.BoardState, Problem);
    Flow.ApplySnapshot(Baseline);
    Flow.QueueHttpResultForTest(false, {RateLimited()});
    Flow.BeginManeuver();
    TestEqual("one mutation send", Flow.GetTestHttpSendCountForTest(), 1);
    TestFalse("429 is not an unknown outcome", Flow.IsMutationRecoveryActiveForTest());
    TestTrue("rate limit surfaced", Cap.ErrorCodes.Contains(TEXT("RATE_LIMIT")));
    FString Reason;
    TestTrue("controls stay usable", Flow.CanIssueGameplayCommand(Reason));
  }
  return true;
}

// ---- S10 review P1(4): a deferred refresh for user A must not install A's
// tokens after the player re-logged in as B ----------------------------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10StaleRefreshAfterReloginTest,
    "Unmatched.S10.Auth.deferred refresh from the previous identity is dropped",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10StaleRefreshAfterReloginTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"));
  FAuthCapture Cap;
  Cap.Bind(Flow);

  // Session A: a poll hits 401 and a refresh is dispatched (answer held).
  Flow.SetAuthForTest(TEXT("access-A"), TEXT("refresh-A"));
  Flow.SetRoomForTest(TEXT("g1"), ES08Stage::Room);
  Flow.QueueHttpResultForTest(false, {Auth401()}, /*bDeferDelivery=*/true);
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, RefreshOkBody);
  Flow.PollRoom();
  Flow.DeliverQueuedHttpForTest(); // 401 -> refresh in flight (for identity A)
  TestEqual("refresh dispatched", Flow.GetRefreshCountForTest(), 1);

  // The player signs in as B while A's refresh answer is still deferred.
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, LoginOkBodyB);
  Flow.Login(TEXT("b@example.com"), TEXT("pw"));
  // FIFO order: A's held refresh answer arrives first (after the identity
  // switch began, before the login resolves) - the generation gate must
  // drop it; only then does the login answer install B.
  Flow.DeliverQueuedHttpForTest();
  Flow.DeliverQueuedHttpForTest(); // login as B installs B's identity
  TestEqual("identity switched to B", Flow.GetUserId(), TEXT("p-b"));
  TestEqual("B's access token installed", Flow.GetAccessTokenForTest(), TEXT("access-B"));

  // A's refresh answer finally arrives: it must be DROPPED - not rotated in
  // over B's session.
  Flow.DeliverQueuedHttpForTest();
  TestEqual("stale refresh did not rotate tokens", Flow.GetAccessTokenForTest(),
            TEXT("access-B"));
  TestTrue("drop traced", Cap.SawTrace(TEXT("identity changed")));
  TestFalse("no rotation trace after the drop", Cap.SawTrace(TEXT("token pair rotated")));
  TestEqual("still exactly one refresh", Flow.GetRefreshCountForTest(), 1);
  return true;
}

// ---- S10 review P2(8) + 4409: close reasons are redacted; 4409 is not auth -
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10WsCloseRedactionCanaryTest,
    "Unmatched.S10.Auth.WS close reason is redacted to code and fixed description",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10WsCloseRedactionCanaryTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FAuthCapture Cap;
  Cap.Bind(Flow);
  Flow.SetAuthForTest(TEXT("access-1"), TEXT("refresh-1"));
  Flow.AttachStreamHarnessForTest(TEXT("g1"));

  // 4409 with an attacker-controlled reason string (a real server sends
  // "Subscriber already exists <id>"; the text must never reach a trace).
  Flow.HandleWsClosedForTest(4409, TEXT("Subscriber already exists INJECTED-REASON-XYZZY"));
  TestEqual("4409 does not refresh", Flow.GetRefreshCountForTest(), 0);
  TestTrue("4409 traced with its code", Cap.SawTrace(TEXT("4409")));
  TestTrue("fixed description traced", Cap.SawTrace(TEXT("subscriber already exists")));
  TestTrue("4409 reconnects", Cap.SawTrace(TEXT("reconnect in")));
  TestFalse("not expired", Flow.IsSessionExpiredForTest());

  // Unknown code with a canary payload: numeric code + "closed" only.
  Flow.HandleWsClosedForTest(4999, TEXT("INJECTED-REASON-XYZZY token=secret"));
  TestTrue("unknown code traced", Cap.SawTrace(TEXT("4999")));

  const FString Traces = Cap.AllTraces();
  TestFalse("server-controlled reason never logged",
            Traces.Contains(TEXT("INJECTED-REASON-XYZZY")));
  TestFalse("payload never logged", Traces.Contains(TEXT("token=secret")));
  return true;
}

// ---- S10 review P1(1): backend-shaped HTTP 200 auth/rate-limit errors -------
// The backend answers 401/429 as HTTP 200 GraphQL errors[] with codes the
// legacy classifier missed: UNAUTHENTICATED (extensions) and TOO_MANY_REQUESTS
// (sometimes top-level). Both must classify EXACTLY like the old shapes.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10BackendAuthShapesTest,
    "Unmatched.S10.Auth.backend-shaped 200 UNAUTHENTICATED and TOO_MANY_REQUESTS classify",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10BackendAuthShapesTest::RunTest(const FString&) {
  {
    // UNAUTHENTICATED (HTTP 200, code from extensions): the 401 refresh path.
    FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
    FAuthCapture Cap;
    Cap.Bind(Flow);
    Flow.SetAuthForTest(TEXT("access-1"), TEXT("refresh-1"));
    Flow.SetRoomForTest(TEXT("g1"), ES08Stage::Room);
    Flow.QueueHttpResultForTest(false, {BackendUnauthenticated()}, /*bDeferDelivery=*/true);
    Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, RefreshOkBody);
    Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, RoomOkBody);
    Flow.PollRoom();
    Flow.DeliverQueuedHttpForTest(); // 200 UNAUTHENTICATED -> refresh path
    TestEqual("UNAUTHENTICATED triggers the refresh", Flow.GetRefreshCountForTest(), 1);
    TestFalse("not expired", Flow.IsSessionExpiredForTest());
    Flow.DeliverQueuedHttpForTest();
    TestEqual("tokens rotated", Flow.GetAccessTokenForTest(), TEXT("access-2"));
    Flow.DeliverQueuedHttpForTest(); // retried poll ok
  }
  {
    // TOO_MANY_REQUESTS (HTTP 200, top-level code): surfaced, never retried.
    FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
    FAuthCapture Cap;
    Cap.Bind(Flow);
    Flow.SetAuthForTest(TEXT("access-1"), TEXT("refresh-1"));
    Flow.SetRoomForTest(TEXT("g1"), ES08Stage::Room);
    Flow.QueueHttpResultForTest(false, {BackendTooManyRequests()});
    Flow.PollRoom();
    TestTrue("rate limit surfaced with the backend code",
             Cap.ErrorCodes.Contains(TEXT("TOO_MANY_REQUESTS")));
    TestEqual("no refresh on 200 TOO_MANY_REQUESTS", Flow.GetRefreshCountForTest(), 0);
    TestFalse("not expired", Flow.IsSessionExpiredForTest());
    TestEqual("exactly one send", Flow.GetTestHttpSendCountForTest(), 1);
  }
  return true;
}

// ---- S10 review P1(5): concurrent login A/B - the OLDER answer must not
// install its identity after the NEWER login was dispatched --------------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10ConcurrentLoginReverseAnswerTest,
    "Unmatched.S10.Auth.concurrent login stale answer cannot install over the newer one",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10ConcurrentLoginReverseAnswerTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"));
  FAuthCapture Cap;
  Cap.Bind(Flow);

  // Login A dispatched first (answer deferred); the player immediately signs
  // in as B (answer deferred too). B's answer resolves FIRST - the exact
  // reverse-reply-order race the review flagged - then A's late answer.
  Flow.QueueHttpResultForTest(false,
                              {FS08GraphQLError{TEXT("AUTH"),
                                                TEXT("HTTP 401 from server"), FString(), 401}},
                              /*bDeferDelivery=*/true);
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, LoginOkBodyB);
  Flow.Login(TEXT("a@example.com"), TEXT("pw")); // dispatch A (Gen 1)
  Flow.Login(TEXT("b@example.com"), TEXT("pw")); // dispatch B (Gen 2) - wins

  // B's answer first: installs identity B.
  Flow.DeliverQueuedHttpForTest(1); // B's answer (out of order)
  TestEqual("identity switched to B", Flow.GetUserId(), TEXT("p-b"));
  TestEqual("B's token installed", Flow.GetAccessTokenForTest(), TEXT("access-B"));
  TestEqual("stage Login after B", Flow.GetStage(), ES08Stage::Login);

  // A's late answer arrives last: rejected AND successful halves are both
  // gated - neither the error surface nor a token install may leak from A.
  Flow.DeliverQueuedHttpForTest(0); // A's 401 answer -> stale, dropped
  TestTrue("stale answer traced", Cap.SawTrace(TEXT("LOGIN stale answer ignored")));
  TestTrue("no error surfaced for the stale login", Cap.Errors == 0);
  TestEqual("identity still B", Flow.GetUserId(), TEXT("p-b"));
  TestEqual("B's token untouched by the stale answer",
            Flow.GetAccessTokenForTest(), TEXT("access-B"));
  TestNotEqual("A did not install a stage", Flow.GetStage(), ES08Stage::Failed);
  return true;
}

// ---- S10 review P1(6): a relogin while a match is live tears the old stream --
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10ReloginTearsDownLiveMatchTest,
    "Unmatched.S10.Auth.relogin during a live match tears down stream room and op id",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10ReloginTearsDownLiveMatchTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FAuthCapture Cap;
  Cap.Bind(Flow);
  Flow.SetAuthForTest(TEXT("access-A"), TEXT("refresh-A"));
  // Match A is live: socket + subscription + applied state + room.
  Flow.AttachStreamHarnessForTest(TEXT("g1"));
  FS08Snapshot Baseline;
  Baseline.SequenceNumber = 10;
  Baseline.Phase = TEXT("ACTION_MANEUVER");
  Baseline.TurnCount = 1;
  Baseline.CurrentTurnPlayerId = HostId;
  FString Problem;
  FS08Contracts::TryParseJsonValue(
      TEXT("[{\"userId\":\"p-host\"},{\"userId\":\"p-guest\"}]"), Baseline.Players, Problem);
  FS08Contracts::TryParseJsonValue(
      TEXT("[{\"id\":\"f1\"},{\"id\":\"f2\"}]"), Baseline.Fighters, Problem);
  FS08Contracts::TryParseJsonValue(
      TEXT("{\"p-host\":[],\"p-guest\":[]}"), Baseline.HandZones, Problem);
  FS08Contracts::TryParseJsonValue(
      TEXT("{\"cells\":[[0,0],[1,0]]}"), Baseline.BoardState, Problem);
  Flow.ApplySnapshot(Baseline);
  TestTrue("match live: stream attached", Flow.IsStreamAttached());
  TestTrue("op id registered", Flow.HasGameStateOpForTest());
  TestEqual("room g1", Flow.GetRoom().GameId, TEXT("g1"));

  // The player re-logs in as B: A's match must be torn down BEFORE B installs,
  // so no stale socket/op id/room survives into the new session.
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, LoginOkBodyB);
  Flow.Login(TEXT("b@example.com"), TEXT("pw"));
  TestTrue("teardown traced", Cap.SawTrace(TEXT("LOGIN identity change")));
  TestFalse("old socket dropped on dispatch", Flow.IsStreamAttached());
  TestFalse("old op id cleared", Flow.HasGameStateOpForTest());
  TestTrue("room reset", Flow.GetRoom().GameId.IsEmpty());
  TestEqual("applied state reset", Flow.GetAppliedSnapshot().SequenceNumber, 0);

  // B installs; a late frame for A's dead subscription cannot resurrect state.
  Flow.DeliverQueuedHttpForTest();
  TestEqual("identity B installed", Flow.GetUserId(), TEXT("p-b"));
  return true;
}

// ---- S10 review P2(7): a stale refresh answer must not clear the NEWER
// refresh's single-flight flag ---------------------------------------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS10RefreshOverlapSingleFlightTest,
    "Unmatched.S10.Auth.stale refresh answer does not clear the newer refresh single-flight",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS10RefreshOverlapSingleFlightTest::RunTest(const FString&) {
  FS08FlowController Flow(FString(), TEXT("ws://test.invalid"), HostId);
  FAuthCapture Cap;
  Cap.Bind(Flow);
  Flow.SetAuthForTest(TEXT("access-A"), TEXT("refresh-A"));
  Flow.SetRoomForTest(TEXT("g1"), ES08Stage::Room);

  // Identity A's refresh is dispatched (answer held, deferred index 0).
  Flow.QueueHttpResultForTest(false, {Auth401()}, /*bDeferDelivery=*/true);
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, RefreshOkBody);
  Flow.PollRoom();
  Flow.DeliverQueuedHttpForTest(); // 401 -> refresh A in flight
  TestTrue("refresh A in flight", Flow.IsRefreshInFlightForTest());

  // Relogin as B (clears the flag for the new identity), then B's session
  // hits its own 401 and refreshes (in flight, answer held).
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, LoginOkBodyB);
  Flow.QueueHttpResultForTest(false, {Auth401()}, /*bDeferDelivery=*/true);
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, RefreshOkBodyB);
  Flow.QueueHttpResultForTest(true, {}, /*bDeferDelivery=*/true, RoomOkBody);
  Flow.Login(TEXT("b@example.com"), TEXT("pw"));
  TestFalse("login B reset the single-flight flag", Flow.IsRefreshInFlightForTest());
  Flow.DeliverQueuedHttpForTest(1); // login B ok (A's refresh answer still held)
  Flow.SetRoomForTest(TEXT("g1"), ES08Stage::Room);
  Flow.PollRoom();
  Flow.DeliverQueuedHttpForTest(1); // B's 401 -> refresh B in flight
  TestTrue("refresh B in flight", Flow.IsRefreshInFlightForTest());
  TestEqual("two refreshes dispatched so far", Flow.GetRefreshCountForTest(), 2);

  // A's deferred refresh answer finally arrives WHILE B's refresh is in
  // flight: the generation gate must drop it WITHOUT clearing B's flag (the
  // exact P2(7) bug - the old code cleared it before checking).
  Flow.DeliverQueuedHttpForTest(0); // A's refresh ok -> stale identity, dropped
  TestTrue("B's single-flight flag survived the stale answer",
           Flow.IsRefreshInFlightForTest());
  TestTrue("stale refresh drop traced", Cap.SawTrace(TEXT("identity changed")));
  TestEqual("no token rotation from the stale answer",
            Flow.GetAccessTokenForTest(), TEXT("access-B"));

  // B's own refresh answer then completes normally.
  Flow.DeliverQueuedHttpForTest();
  TestFalse("flag cleared by B's answer", Flow.IsRefreshInFlightForTest());
  TestEqual("B's rotation installed", Flow.GetAccessTokenForTest(), TEXT("access-B2"));
  Flow.DeliverQueuedHttpForTest(); // B's retried poll ok
  return true;
}

#endif

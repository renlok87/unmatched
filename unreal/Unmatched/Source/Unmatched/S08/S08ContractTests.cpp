// GD-028: automation tests over the captured contract fixtures
// (docs/game-design/evidence/S08/fixtures). Run headless:
//   UnrealEditor-Cmd.exe Unmatched.uproject -ExecCmds="Automation RunTests Unmatched.S08; Quit" \
//     -S08Fixtures=<abs path to fixtures dir> -unattended -nosplash -nullrhi
// Fixtures were captured from the live backend (see capture-fixtures.mjs);
// these tests prove the UE parser tolerates reordered/partial bodies and
// rejects wrong scalars / malformed payloads with actionable errors.
#if WITH_AUTOMATION_TESTS

#include "S08Contracts.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

namespace {
FString FixturePath(const TCHAR* Name) {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S08Fixtures="), Dir) || Dir.IsEmpty()) {
    Dir = FPaths::Combine(FPaths::ProjectDir(),
                          TEXT("../../docs/game-design/evidence/S08/fixtures"));
  }
  return FPaths::Combine(Dir, Name);
}

FString RawOf(const TCHAR* Name) {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *FixturePath(Name))) return FString();
  // The wrapper itself may BE the malformed payload (fixture 11 is truncated
  // mid-string) - so it must go through the crash-safe entry too; UE's raw
  // reader would read past the end of the buffer.
  TSharedPtr<FJsonValue> Value;
  FString Problem;
  if (!FS08Contracts::TryParseJsonValue(Text, Value, Problem)) return Text;
  // Fixtures wrap the transport payload in {kind, httpStatus?, raw}. Most
  // keep raw as a JSON object, malformed/truncated ones as a string.
  const TSharedPtr<FJsonObject>* Root = nullptr;
  if (Value->TryGetObject(Root) && Root->IsValid()) {
    FString Inner;
    if ((*Root)->TryGetStringField(TEXT("raw"), Inner)) return Inner;
    const TSharedPtr<FJsonObject>* RawObject = nullptr;
    if ((*Root)->TryGetObjectField(TEXT("raw"), RawObject) && RawObject->IsValid()) {
      FString Serialized;
      const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Serialized);
      FJsonSerializer::Serialize(RawObject->ToSharedRef(), Writer);
      return Serialized;
    }
  }
  return Text;
}

FString FixtureRawBody(const TCHAR* Name) {
  const FString Wrapped = RawOf(Name);
  return Wrapped;
}
} // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LoginParseTest,
    "Unmatched.S08.Login parse (fixture 01)", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LoginParseTest::RunTest(const FString&) {
  const FString Body = RawOf(TEXT("01-login-response.json"));
  TestTrue("fixture loaded", !Body.IsEmpty());
  FString Access, Refresh, UserId, Username;
  FS08GraphQLError Error;
  const bool bOk = FS08Contracts::ParseAuthResponse(Body, Access, Refresh, UserId, Username, Error);
  TestTrue("login parses", bOk);
  if (bOk) {
    TestTrue("access token present", Access.StartsWith(TEXT("ey")) || Access.Len() > 20);
    TestEqual("username", Username, TEXT("TestPlayer1"));
    TestFalse("user id empty", UserId.IsEmpty());
  } else {
    AddError(Error.Message);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08GameStateFullTest,
    "Unmatched.S08.gameState query full two-stage parse (fixture 04)", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08GameStateFullTest::RunTest(const FString&) {
  const FString Body = RawOf(TEXT("04-game-state-query-host.json"));
  TestTrue("fixture loaded", !Body.IsEmpty());
  FS08Snapshot Snapshot;
  FString RawState;
  FS08GraphQLError Error;
  const bool bOk = FS08Contracts::ParseGameStateQuery(Body, Snapshot, RawState, Error);
  TestTrue("gameState parses", bOk);
  if (!bOk) { AddError(Error.Message); return true; }
  // Float scalar on the wire (NestJS number) must land as int.
  TestEqual("sequenceNumber", Snapshot.SequenceNumber, 1);
  TestEqual("phase", Snapshot.Phase, TEXT("ACTION_MANEUVER"));
  TestTrue("state was a JSON string", !RawState.IsEmpty());
  TestTrue("players decoded", Snapshot.Players.IsValid() && FS08Contracts::EntryCount(Snapshot.Players) == 2);
  TestTrue("fighters decoded", Snapshot.Fighters.IsValid() && FS08Contracts::EntryCount(Snapshot.Fighters) >= 2);
  TestTrue("handZones decoded", Snapshot.HandZones.IsValid() && FS08Contracts::EntryCount(Snapshot.HandZones) == 2);
  TestTrue("discardPiles decoded (S05 reveal)", Snapshot.DiscardPiles.IsValid());
  TestTrue("boardState decoded", Snapshot.BoardState.IsValid() && Snapshot.BoardState->AsObject().IsValid() &&
           Snapshot.BoardState->AsObject()->HasField(TEXT("cells")));
  // Critical validation against the real viewer id must pass.
  TArray<FString> Problems;
  const bool bValid = FS08Contracts::ValidateCriticalFields(Snapshot, TEXT("cmugykjjb0000wi9w2nq4qlkj"), Problems);
  TestTrue("critical fields valid for viewer", bValid);
  if (!bValid) AddError(FString::Join(Problems, TEXT("; ")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ReorderedPartialTest,
    "Unmatched.S08.gameState reordered+partial body parses and merges (fixture 06)", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ReorderedPartialTest::RunTest(const FString&) {
  const FString Body = RawOf(TEXT("06-game-state-query-reordered-partial.json"));
  TestTrue("fixture loaded", !Body.IsEmpty());
  FS08Snapshot Snapshot;
  FString RawState;
  FS08GraphQLError Error;
  const bool bOk = FS08Contracts::ParseGameStateQuery(Body, Snapshot, RawState, Error);
  TestTrue("reordered partial parses", bOk);
  if (!bOk) { AddError(Error.Message); return true; }
  TestEqual("sequenceNumber", Snapshot.SequenceNumber, 1);
  // Partial body: discardPiles/metadata were removed by the fixture builder.
  TestFalse("discardPiles absent (partial)", Snapshot.DiscardPiles.IsValid());
  TestFalse("metadata absent (partial)", Snapshot.Metadata.IsValid());
  // Absent optional fields must NOT block input for this snapshot.
  TArray<FString> Problems;
  const bool bValid = FS08Contracts::ValidateCriticalFields(Snapshot, TEXT("cmugykjjb0000wi9w2nq4qlkj"), Problems);
  TestTrue("critical fields still valid", bValid);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08WsNextTest,
    "Unmatched.S08.gameStateUpdated WS next parses (fixture 07)", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08WsNextTest::RunTest(const FString&) {
  const FString Body = RawOf(TEXT("07-ws-game-state-updated-next.json"));
  TestTrue("fixture loaded", !Body.IsEmpty());
  TSharedPtr<FJsonObject> Root;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(Body, Root, Problem)) {
    AddError(FString::Printf(TEXT("fixture is not JSON (%s)"), *Problem)); return true;
  }
  const TSharedPtr<FJsonObject>* Data = nullptr;
  if (!Root->TryGetObjectField(TEXT("data"), Data) || !Data->IsValid()) {
    AddError("fixture has no data"); return true;
  }
  const TSharedPtr<FJsonObject>* Event = nullptr;
  if (!(*Data)->TryGetObjectField(TEXT("gameStateUpdated"), Event) || !Event->IsValid()) {
    AddError("fixture has no gameStateUpdated event"); return true;
  }
  FS08Snapshot Snapshot;
  FS08GraphQLError Error;
  const bool bOk = FS08Contracts::ParseGameStateUpdated(Event->ToSharedRef(), Snapshot, Error);
  TestTrue("WS next parses", bOk);
  if (!bOk) { AddError(Error.Message); return true; }
  TestEqual("WS sequenceNumber", Snapshot.SequenceNumber, 1);
  TestTrue("WS players decoded (JSON string decoded)",
           Snapshot.Players.IsValid() && FS08Contracts::EntryCount(Snapshot.Players) == 2);
  TestTrue("WS discardPiles decoded", Snapshot.DiscardPiles.IsValid());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08WrongScalarTest,
    "Unmatched.S08.wrong scalar state rejected with actionable error (fixture 10)", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08WrongScalarTest::RunTest(const FString&) {
  const FString Body = RawOf(TEXT("10-wrong-scalar-state-object.json"));
  TestTrue("fixture loaded", !Body.IsEmpty());
  FS08Snapshot Snapshot;
  FString RawState;
  FS08GraphQLError Error;
  const bool bOk = FS08Contracts::ParseGameStateQuery(Body, Snapshot, RawState, Error);
  TestFalse("wrong scalar rejected", bOk);
  if (!bOk) {
    TestEqual("error code", Error.Code, TEXT("PARSE"));
    TestTrue("error mentions the field", Error.Message.Contains(TEXT("state")));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MalformedTest,
    "Unmatched.S08.malformed truncated body rejected (fixture 11)", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MalformedTest::RunTest(const FString&) {
  const FString Body = RawOf(TEXT("11-malformed-truncated.json"));
  TestTrue("fixture loaded", !Body.IsEmpty());
  FS08Snapshot Snapshot;
  FString RawState;
  FS08GraphQLError Error;
  const bool bOk = FS08Contracts::ParseGameStateQuery(Body, Snapshot, RawState, Error);
  TestFalse("malformed rejected", bOk);
  if (!bOk) {
    TestEqual("error code", Error.Code, TEXT("PARSE"));
    // Crash regression: the truncated network shape (fixture ends mid-string)
    // must be rejected by the pre-scan with an actionable reason instead of
    // fatally crashing inside TJsonReader::ParseStringToken.
    TestTrue("actionable reason (unterminated string)",
             Error.Message.Contains(TEXT("unterminated string")));
    TestTrue("reason carries an offset", Error.Message.Contains(TEXT("offset")));
  }
  return true;
}

// Crash regression (production blocker): UE's TJsonReader::ParseStringToken
// reads past the end of truncated network text (fatal crash in
// FBufferReaderBase::Serialize). Every malformed shape below reproduced that
// crash class before the bounds-checked pre-scan existed; each must now be
// REJECTED with an actionable PARSE error, and the valid body must parse.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MalformedShapesTest,
    "Unmatched.S08.crash-shaped malformed bodies rejected before UE reader (trailing backslash, partial u-escape, unterminated, nested truncated; valid parses)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MalformedShapesTest::RunTest(const FString&) {
  struct FCase {
    const TCHAR* Name;
    FString Body;
    const TCHAR* ExpectReason;
  };
  const TArray<FCase> Cases = {
    {TEXT("trailing backslash"),
     TEXT("{\"data\":{\"gameState\":{\"sequenceNumber\":1,\"phase\":\"P\",\"state\":\"{\\"),
     TEXT("trailing backslash")},
    {TEXT("partial \\u escape"),
     TEXT("{\"data\":{\"gameState\":{\"state\":\"x\\u00"),
     TEXT("\\u escape")},
    {TEXT("unterminated string"),
     TEXT("{\"data\":{\"gameState\":{\"id\":\"abc"),
     TEXT("unterminated string")},
    {TEXT("nested escaped state truncated (fixture 11 shape)"),
     TEXT("{\"data\":{\"gameState\":{\"id\":\"g1-state\",\"gameId\":\"g1\",\"state\":\"{\\\"gameId\\\":"),
     TEXT("unterminated string")},
  };
  for (const FCase& Case : Cases) {
    FS08Snapshot Snapshot;
    FString RawState;
    FS08GraphQLError Error;
    const bool bOk = FS08Contracts::ParseGameStateQuery(Case.Body, Snapshot, RawState, Error);
    TestFalse(FString::Printf(TEXT("%s: rejected"), Case.Name), bOk);
    if (!bOk) {
      TestEqual(FString::Printf(TEXT("%s: code PARSE"), Case.Name), Error.Code, TEXT("PARSE"));
      TestTrue(FString::Printf(TEXT("%s: actionable reason"), Case.Name),
               Error.Message.Contains(Case.ExpectReason));
      TestTrue(FString::Printf(TEXT("%s: offset in reason"), Case.Name),
               Error.Message.Contains(TEXT("offset")));
    }
  }
  // Control: a well-formed two-stage body still parses end to end.
  FS08Snapshot Snapshot;
  FString RawState;
  FS08GraphQLError Error;
  const FString Valid = TEXT("{\"data\":{\"gameState\":{\"sequenceNumber\":2,\"phase\":\"SETUP\",")
                        TEXT("\"state\":\"{\\\"sequenceNumber\\\":2,\\\"phase\\\":\\\"SETUP\\\",")
                        TEXT("\\\"players\\\":[{\\\"id\\\":\\\"p1\\\"},{\\\"id\\\":\\\"p2\\\"}]}\"}}}");
  const bool bValidOk = FS08Contracts::ParseGameStateQuery(Valid, Snapshot, RawState, Error);
  TestTrue("valid body still parses", bValidOk);
  if (!bValidOk) { AddError(Error.Message); return true; }
  TestEqual("valid sequenceNumber", Snapshot.SequenceNumber, 2);
  TestEqual("valid phase", Snapshot.Phase, TEXT("SETUP"));
  TestTrue("valid players decoded",
           Snapshot.Players.IsValid() && FS08Contracts::EntryCount(Snapshot.Players) == 2);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08AuthFailureTest,
    "Unmatched.S08.auth failure surfaces errors[] on HTTP 200 (fixture 08)", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08AuthFailureTest::RunTest(const FString&) {
  const FString Body = RawOf(TEXT("08-auth-failure-errors.json"));
  TestTrue("fixture loaded", !Body.IsEmpty());
  TSharedPtr<FJsonObject> Root;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(Body, Root, Problem)) {
    AddError(FString::Printf(TEXT("fixture is not JSON (%s)"), *Problem)); return true;
  }
  TArray<FS08GraphQLError> Errors;
  TestTrue("errors[] extracted on HTTP 200", FS08Contracts::ExtractGraphQLErrors(Root.ToSharedRef(), Errors));
  if (Errors.Num() > 0) {
    TestEqual("code", Errors[0].Code, TEXT("UNAUTHENTICATED"));
    TestFalse("message empty", Errors[0].Message.IsEmpty());
  }
  // The same body must NOT parse as a state snapshot.
  FS08Snapshot Snapshot; FString RawState; FS08GraphQLError ParseError;
  TestFalse("state parse blocked by errors[]",
            FS08Contracts::ParseGameStateQuery(Body, Snapshot, RawState, ParseError));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ErrorCodePlacementTest,
    "Unmatched.S08.error code placement normalized (extensions, top-level, status)", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ErrorCodePlacementTest::RunTest(const FString&) {
  auto Extract = [this](const TCHAR* Body, FS08GraphQLError& Out) {
    TSharedPtr<FJsonObject> Root;
    FString Problem;
    if (!FS08Contracts::TryParseJsonObject(Body, Root, Problem)) {
      AddError(FString::Printf(TEXT("body is not JSON (%s)"), *Problem));
      return false;
    }
    TArray<FS08GraphQLError> Errors;
    if (!FS08Contracts::ExtractGraphQLErrors(Root.ToSharedRef(), Errors) || Errors.Num() == 0) {
      AddError(TEXT("no errors[] extracted"));
      return false;
    }
    Out = Errors[0];
    return true;
  };
  // (a) extensions.code (the backend's primary 401 shape on HTTP 200).
  {
    FS08GraphQLError E;
    TestTrue("extensions.code body extracted",
             Extract(TEXT("{\"errors\":[{\"message\":\"Unauthorized\",")
                         TEXT("\"extensions\":{\"code\":\"UNAUTHENTICATED\"}}]}"), E));
    TestEqual("extensions.code wins", E.Code, TEXT("UNAUTHENTICATED"));
    TestEqual("no status -> 0", E.HttpStatus, 0);
  }
  // (b) TOP-LEVEL code (some backend paths) + extensions.statusCode.
  {
    FS08GraphQLError E;
    TestTrue("top-level code body extracted",
             Extract(TEXT("{\"errors\":[{\"message\":\"Too many requests\",")
                         TEXT("\"code\":\"TOO_MANY_REQUESTS\",")
                         TEXT("\"extensions\":{\"statusCode\":429}}]}"), E));
    TestEqual("top-level code kept", E.Code, TEXT("TOO_MANY_REQUESTS"));
    TestEqual("statusCode lifts HttpStatus", E.HttpStatus, 429);
  }
  // (c) extensions.status variant + message-only fallback.
  {
    FS08GraphQLError E;
    TestTrue("status variant extracted",
             Extract(TEXT("{\"errors\":[{\"message\":\"x\",")
                         TEXT("\"extensions\":{\"code\":\"FORBIDDEN\",\"status\":403}}]}"), E));
    TestEqual("code from extensions", E.Code, TEXT("FORBIDDEN"));
    TestEqual("status lifts HttpStatus", E.HttpStatus, 403);
  }
  {
    FS08GraphQLError E;
    TestTrue("message-only extracted",
             Extract(TEXT("{\"errors\":[{\"message\":\"boom\"}]}"), E));
    TestEqual("fallback code GRAPHQL", E.Code, TEXT("GRAPHQL"));
    TestEqual("fallback status 0", E.HttpStatus, 0);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08SeqGuardTest,
    "Unmatched.S08.seq guard semantics (< ignore, == merge, > apply)", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08SeqGuardTest::RunTest(const FString&) {
  FS08SeqGuard Guard;
  TestEqual("first applies", static_cast<uint8>(Guard.Decide(3)), static_cast<uint8>(ES08SeqDecision::Apply));
  Guard.Commit(3);
  TestEqual("stale ignored", static_cast<uint8>(Guard.Decide(2)), static_cast<uint8>(ES08SeqDecision::Ignore));
  TestEqual("same merges", static_cast<uint8>(Guard.Decide(3)), static_cast<uint8>(ES08SeqDecision::Merge));
  TestEqual("newer applies (gap allowed)", static_cast<uint8>(Guard.Decide(7)), static_cast<uint8>(ES08SeqDecision::Apply));
  Guard.Commit(7);
  TestEqual("guard keeps max on stale commit", Guard.Local, 7);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CriticalBlockTest,
    "Unmatched.S08.critically incomplete state blocks input", EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CriticalBlockTest::RunTest(const FString&) {
  FS08Snapshot Snapshot;
  Snapshot.SequenceNumber = 5;
  Snapshot.Phase = TEXT("ACTION_MANEUVER");
  const TSharedRef<FJsonObject> TwoPlayers = MakeShared<FJsonObject>();
  TwoPlayers->SetStringField(TEXT("a"), TEXT("a"));
  TwoPlayers->SetStringField(TEXT("b"), TEXT("b"));
  Snapshot.Players = MakeShared<FJsonValueObject>(TwoPlayers);
  // fighters, boardState, handZones deliberately missing.
  TArray<FString> Problems;
  const bool bValid = FS08Contracts::ValidateCriticalFields(Snapshot, TEXT("a"), Problems);
  TestFalse("incomplete state invalid", bValid);
  bool bMentionsFighters = false, bMentionsBoard = false, bMentionsHand = false;
  for (const FString& Problem : Problems) {
    bMentionsFighters |= Problem.Contains(TEXT("fighters"));
    bMentionsBoard |= Problem.Contains(TEXT("boardState"));
    bMentionsHand |= Problem.Contains(TEXT("handZones"));
  }
  TestTrue("actionable: fighters problem named", bMentionsFighters);
  TestTrue("actionable: boardState problem named", bMentionsBoard);
  TestTrue("actionable: handZones problem named", bMentionsHand);
  return true;
}

#endif

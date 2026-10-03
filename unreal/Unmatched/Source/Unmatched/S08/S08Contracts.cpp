#include "S08Contracts.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace {
// Bounds on pre-scanned text: a runaway/truncated body is rejected by size
// before the walk, and pathological nesting never recurses unboundedly.
constexpr int32 MaxJsonTextChars = 8 * 1024 * 1024;
constexpr int32 MaxJsonDepth = 64;

bool IsWs(const TCHAR C) {
  return C == TEXT(' ') || C == TEXT('\t') || C == TEXT('\n') || C == TEXT('\r');
}
bool IsDigit(const TCHAR C) { return C >= TEXT('0') && C <= TEXT('9'); }
bool IsHexDigit(const TCHAR C) {
  return (C >= TEXT('0') && C <= TEXT('9')) || (C >= TEXT('a') && C <= TEXT('f')) ||
         (C >= TEXT('A') && C <= TEXT('F'));
}

/** Bounds-checked JSON structural scanner. Every parse of network text goes
 *  through this FIRST: UE's TJsonReader::ParseStringToken can read past the
 *  end of a truncated string (trailing backslash, partial \u escape,
 *  unterminated string) and fatally crash, so FJsonSerializer must only ever
 *  see text this scan accepted. The walk itself can never run off the buffer:
 *  every dereference is guarded by P < End. */
struct FJsonScanner {
  const TCHAR* Start;
  const TCHAR* P;
  const TCHAR* End;
  FString Problem;

  bool Fail(const TCHAR* What) {
    Problem = FString::Printf(TEXT("%s at offset %d"), What,
                              static_cast<int32>(P - Start));
    return false;
  }
  void SkipWs() { while (P < End && IsWs(*P)) ++P; }

  bool ScanString() {
    ++P; // opening quote
    for (;;) {
      if (P >= End) return Fail(TEXT("unterminated string"));
      const TCHAR C = *P;
      if (C == TEXT('"')) { ++P; return true; }
      if (C == TEXT('\\')) {
        ++P;
        if (P >= End) return Fail(TEXT("trailing backslash escape at end of text"));
        switch (*P) {
          case TEXT('"'): case TEXT('\\'): case TEXT('/'):
          case TEXT('b'): case TEXT('f'): case TEXT('n'):
          case TEXT('r'): case TEXT('t'):
            ++P; break;
          case TEXT('u'): {
            ++P;
            for (int32 i = 0; i < 4; ++i) {
              if (P >= End) return Fail(TEXT("partial \\u escape at end of text"));
              if (!IsHexDigit(*P)) return Fail(TEXT("invalid hex digit in \\u escape"));
              ++P;
            }
            break;
          }
          default: return Fail(TEXT("invalid escape character"));
        }
        continue;
      }
      // Raw control characters inside strings are left to the UE reader
      // (it tolerates them): the pre-scan must never be stricter than the
      // reader it guards, only catch the shapes that crash it.
      ++P;
    }
  }

  bool ScanNumber() {
    if (P < End && *P == TEXT('-')) ++P;
    if (P >= End) return Fail(TEXT("unterminated number"));
    if (*P == TEXT('0')) {
      ++P;
    } else if (IsDigit(*P)) {
      while (P < End && IsDigit(*P)) ++P;
    } else {
      return Fail(TEXT("invalid number"));
    }
    if (P < End && *P == TEXT('.')) {
      ++P;
      if (P >= End || !IsDigit(*P)) return Fail(TEXT("digits missing after decimal point"));
      while (P < End && IsDigit(*P)) ++P;
    }
    if (P < End && (*P == TEXT('e') || *P == TEXT('E'))) {
      ++P;
      if (P < End && (*P == TEXT('+') || *P == TEXT('-'))) ++P;
      if (P >= End || !IsDigit(*P)) return Fail(TEXT("digits missing in exponent"));
      while (P < End && IsDigit(*P)) ++P;
    }
    return true;
  }

  bool ScanLiteral(const TCHAR* Word) {
    for (const TCHAR* W = Word; *W; ++W, ++P) {
      if (P >= End || *P != *W) return Fail(TEXT("invalid literal token"));
    }
    return true;
  }

  bool ScanValue(int32 Depth) {
    SkipWs();
    if (P >= End) return Fail(TEXT("value expected but text ended"));
    if (Depth > MaxJsonDepth) return Fail(TEXT("nesting too deep"));
    const TCHAR C = *P;
    if (C == TEXT('{')) {
      ++P;
      SkipWs();
      if (P < End && *P == TEXT('}')) { ++P; return true; }
      for (;;) {
        SkipWs();
        if (P >= End || *P != TEXT('"')) return Fail(TEXT("object key string expected"));
        if (!ScanString()) return false;
        SkipWs();
        if (P >= End || *P != TEXT(':')) return Fail(TEXT("':' expected after object key"));
        ++P;
        if (!ScanValue(Depth + 1)) return false;
        SkipWs();
        if (P >= End) return Fail(TEXT("unterminated object"));
        if (*P == TEXT(',')) { ++P; continue; }
        if (*P == TEXT('}')) { ++P; return true; }
        return Fail(TEXT("',' or '}' expected in object"));
      }
    }
    if (C == TEXT('[')) {
      ++P;
      SkipWs();
      if (P < End && *P == TEXT(']')) { ++P; return true; }
      for (;;) {
        if (!ScanValue(Depth + 1)) return false;
        SkipWs();
        if (P >= End) return Fail(TEXT("unterminated array"));
        if (*P == TEXT(',')) { ++P; continue; }
        if (*P == TEXT(']')) { ++P; return true; }
        return Fail(TEXT("',' or ']' expected in array"));
      }
    }
    if (C == TEXT('"')) return ScanString();
    if (C == TEXT('-') || IsDigit(C)) return ScanNumber();
    if (C == TEXT('t')) return ScanLiteral(TEXT("true"));
    if (C == TEXT('f')) return ScanLiteral(TEXT("false"));
    if (C == TEXT('n')) return ScanLiteral(TEXT("null"));
    return Fail(TEXT("unexpected character"));
  }
};

bool ParseJsonString(const FString& Text, TSharedPtr<FJsonObject>& OutObject, FString& OutProblem) {
  return FS08Contracts::TryParseJsonObject(Text, OutObject, OutProblem);
}

bool ParseJsonValue(const FString& Text, TSharedPtr<FJsonValue>& OutValue, FString& OutProblem) {
  if (!FS08Contracts::TryParseJsonValue(Text, OutValue, OutProblem)) return false;
  if (OutValue->IsNull()) {
    OutProblem = TEXT("value is null");
    return false;
  }
  return true;
}

FString DottedPath(const TArray<FString>& Path) {
  FString Out;
  for (int32 i = 0; i < Path.Num(); ++i) {
    if (i > 0) Out.AppendChar(TEXT('.'));
    Out.Append(Path[i]);
  }
  return Out;
}

/** Reads a string field through the Values map to distinguish absent
 *  (merge-legal) from present-but-wrong-scalar (error). */
bool ReadStringPresence(const TSharedRef<FJsonObject> Object, const FString& FieldName,
                        FString& OutValue, bool& OutWasPresent) {
  OutWasPresent = false;
  const TSharedPtr<FJsonValue> Field = Object->TryGetField(FieldName);
  if (!Field.IsValid()) return true; // absent
  OutWasPresent = true;
  if (Field->IsNull()) return true; // explicit null: unset
  return Field->TryGetString(OutValue);
}
} // namespace

bool FS08Contracts::ValidateJsonText(const FString& Text, FString& OutProblem) {
  OutProblem.Reset();
  if (Text.Len() > MaxJsonTextChars) {
    OutProblem = FString::Printf(TEXT("text too large (%d chars, max %d)"),
                                 Text.Len(), MaxJsonTextChars);
    return false;
  }
  if (Text.IsEmpty()) {
    OutProblem = TEXT("empty body");
    return false;
  }
  FJsonScanner Scanner{*Text, *Text, *Text + Text.Len()};
  if (Scanner.P < Scanner.End && *Scanner.P == 0xFEFF) ++Scanner.P; // BOM
  if (!Scanner.ScanValue(1)) {
    OutProblem = Scanner.Problem;
    return false;
  }
  Scanner.SkipWs();
  if (Scanner.P < Scanner.End) {
    Scanner.Fail(TEXT("trailing characters after JSON value"));
    OutProblem = Scanner.Problem;
    return false;
  }
  return true;
}

bool FS08Contracts::TryParseJsonObject(const FString& Text, TSharedPtr<FJsonObject>& OutObject,
                                       FString& OutProblem) {
  OutProblem.Reset();
  OutObject.Reset();
  if (!ValidateJsonText(Text, OutProblem)) return false;
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
  if (!FJsonSerializer::Deserialize(Reader, OutObject) || !OutObject.IsValid()) {
    OutProblem = TEXT("internal reader rejected the text");
    return false;
  }
  return true;
}

bool FS08Contracts::TryParseJsonValue(const FString& Text, TSharedPtr<FJsonValue>& OutValue,
                                      FString& OutProblem) {
  OutProblem.Reset();
  OutValue.Reset();
  if (!ValidateJsonText(Text, OutProblem)) return false;
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
  if (!FJsonSerializer::Deserialize(Reader, OutValue) || !OutValue.IsValid()) {
    OutProblem = TEXT("internal reader rejected the text");
    return false;
  }
  return true;
}

ES08SeqDecision FS08SeqGuard::Decide(int32 Incoming) {
  if (!HasLocal) return ES08SeqDecision::Apply;
  if (Incoming < Local) return ES08SeqDecision::Ignore;
  if (Incoming == Local) return ES08SeqDecision::Merge;
  return ES08SeqDecision::Apply;
}

void FS08SeqGuard::Commit(int32 Incoming) {
  if (!HasLocal || Incoming > Local) {
    Local = Incoming;
    HasLocal = true;
  }
}

bool FS08Contracts::ExtractGraphQLErrors(const TSharedRef<FJsonObject> Root,
                                         TArray<FS08GraphQLError>& OutErrors) {
  OutErrors.Reset();
  const TArray<TSharedPtr<FJsonValue>>* RawErrors = nullptr;
  if (!Root->TryGetArrayField(TEXT("errors"), RawErrors)) return false;
  for (const TSharedPtr<FJsonValue>& Value : *RawErrors) {
    const TSharedPtr<FJsonObject>* ErrorObj = nullptr;
    if (!Value.IsValid() || !Value->TryGetObject(ErrorObj) || !ErrorObj->IsValid()) continue;
    FS08GraphQLError Error;
    (*ErrorObj)->TryGetStringField(TEXT("message"), Error.Message);
    // S10 review P1(1): the backend places the machine code in
    // extensions.code, but other shapes exist in the wild (code directly on
    // the error object; extensions.status/statusCode carrying the HTTP code
    // for a 200-wrapped GraphQL error). All placements are normalized here so
    // the controller classifies on Code/HttpStatus alone.
    (*ErrorObj)->TryGetStringField(TEXT("code"), Error.Code);
    const TSharedPtr<FJsonObject>* Extensions = nullptr;
    if ((*ErrorObj)->TryGetObjectField(TEXT("extensions"), Extensions) && Extensions->IsValid()) {
      if (Error.Code.IsEmpty()) {
        (*Extensions)->TryGetStringField(TEXT("code"), Error.Code);
      }
      // MS-T-06: the rule code of a gameplay rejection (formatGraphqlError
      // keeps it in development and production).
      (*Extensions)->TryGetStringField(TEXT("ruleCode"), Error.RuleCode);
      double ExtStatus = 0.0;
      if (Error.HttpStatus == 0 &&
          ((*Extensions)->TryGetNumberField(TEXT("status"), ExtStatus) ||
           (*Extensions)->TryGetNumberField(TEXT("statusCode"), ExtStatus))) {
        Error.HttpStatus = static_cast<int32>(ExtStatus);
      }
    }
    const TArray<TSharedPtr<FJsonValue>>* Path = nullptr;
    if ((*ErrorObj)->TryGetArrayField(TEXT("path"), Path) && Path) {
      TArray<FString> Segments;
      for (const TSharedPtr<FJsonValue>& Segment : *Path) {
        FString Part;
        if (Segment.IsValid() && Segment->TryGetString(Part)) {
          Segments.Add(Part);
        } else if (Segment.IsValid()) {
          double Index = 0.0;
          if (Segment->TryGetNumber(Index)) Segments.Add(FString::Printf(TEXT("%d"), static_cast<int32>(Index)));
        }
      }
      Error.Path = DottedPath(Segments);
    }
    if (Error.Code.IsEmpty()) Error.Code = TEXT("GRAPHQL");
    OutErrors.Add(MoveTemp(Error));
  }
  return OutErrors.Num() > 0;
}

bool FS08Contracts::IsLobbyPhaseAbsent(const TArray<FS08GraphQLError>& Errors) {
  for (const FS08GraphQLError& Error : Errors) {
    // GameStateService.loadState throws NotFoundException (HTTP 200 +
    // errors[]): the room exists but the match has not started yet.
    if (Error.Message.Contains(TEXT("not found"), ESearchCase::IgnoreCase) ||
        Error.Code == TEXT("NOT_FOUND")) {
      return true;
    }
  }
  return false;
}

bool FS08Contracts::DecodeJsonStringField(const TSharedRef<FJsonObject> Object,
                                          const FString& FieldName,
                                          TSharedPtr<FJsonValue>& OutValue,
                                          bool& OutWasPresent, FS08GraphQLError& OutError) {
  OutWasPresent = false;
  OutValue.Reset();
  const TSharedPtr<FJsonValue> Field = Object->TryGetField(FieldName);
  if (!Field.IsValid()) return true; // absent: merge keeps local
  OutWasPresent = true;
  if (Field->IsNull()) return true; // explicit null: unset
  FString Raw;
  if (Field->TryGetString(Raw)) {
    // WS gameStateUpdated ships projections as JSON strings: second stage.
    if (Raw.IsEmpty()) return true; // empty string: unset
    TSharedPtr<FJsonValue> Decoded;
    FString Problem;
    if (!ParseJsonValue(Raw, Decoded, Problem)) {
      OutError = {TEXT("PARSE"),
                  FString::Printf(TEXT("Field '%s' is not valid embedded JSON (%s)"),
                                  *FieldName, *Problem),
                  FieldName};
      return false;
    }
    OutValue = Decoded;
    return true;
  }
  // HTTP state embeds projections natively (players/fighters arrays, the
  // rest objects) - take them as-is.
  OutValue = Field;
  return true;
}

int32 FS08Contracts::EntryCount(const TSharedPtr<FJsonValue>& Value) {
  if (!Value.IsValid() || Value->IsNull()) return 0;
  const TArray<TSharedPtr<FJsonValue>>* Array = nullptr;
  if (Value->TryGetArray(Array) && Array) return Array->Num();
  const TSharedPtr<FJsonObject>* Object = nullptr;
  if (Value->TryGetObject(Object) && Object && Object->IsValid()) {
    return (*Object)->Values.Num();
  }
  return 0;
}

bool FS08Contracts::ReadIntLike(const TSharedRef<FJsonObject> Object, const FString& FieldName,
                                int32& OutValue, bool& OutWasPresent) {
  OutWasPresent = false;
  const TSharedPtr<FJsonValue> Field = Object->TryGetField(FieldName);
  if (!Field.IsValid() || Field->IsNull()) return true; // absent: caller decides
  double AsDouble = 0.0;
  if (Field->TryGetNumber(AsDouble)) {
    OutValue = static_cast<int32>(AsDouble);
    OutWasPresent = true;
    return true;
  }
  // Stringified numbers appear in reordered/partial fixtures; other types
  // are a wrong-scalar situation the caller reports.
  FString AsString;
  if (Field->TryGetString(AsString) && AsString.IsNumeric()) {
    OutValue = FCString::Atoi(*AsString);
    OutWasPresent = true;
    return true;
  }
  return false;
}

bool FS08Contracts::ParseAuthResponse(const FString& Body, FString& OutAccessToken,
                                      FString& OutRefreshToken, FString& OutUserId,
                                      FString& OutUsername, FS08GraphQLError& OutError,
                                      const TCHAR* FieldName) {
  TSharedPtr<FJsonObject> Root;
  FString Problem;
  if (!ParseJsonString(Body, Root, Problem)) {
    OutError = {TEXT("PARSE"),
                FString::Printf(TEXT("Auth response is not valid JSON (%s)"), *Problem),
                FString()};
    return false;
  }
  TArray<FS08GraphQLError> Errors;
  if (ExtractGraphQLErrors(Root.ToSharedRef(), Errors)) {
    OutError = Errors[0];
    return false;
  }
  const TSharedPtr<FJsonObject>* Data = nullptr;
  if (!Root->TryGetObjectField(TEXT("data"), Data) || !Data->IsValid()) {
    OutError = {TEXT("PARSE"), TEXT("Auth response has no data object"), FString()};
    return false;
  }
  const TSharedPtr<FJsonObject>* Login = nullptr;
  if (!(*Data)->TryGetObjectField(FieldName, Login) || !Login->IsValid()) {
    OutError = {TEXT("PARSE"),
                FString::Printf(TEXT("Auth response has no %s payload"), FieldName),
                FString()};
    return false;
  }
  const TSharedRef<FJsonObject> LoginRef = Login->ToSharedRef();
  bool Present = false;
  FString Token;
  ReadStringPresence(LoginRef, TEXT("accessToken"), Token, Present);
  if (!Present || Token.IsEmpty()) {
    OutError = {TEXT("PARSE"), TEXT("Auth response missing accessToken"),
                FString(FieldName) + TEXT(".accessToken")};
    return false;
  }
  OutAccessToken = Token;
  ReadStringPresence(LoginRef, TEXT("refreshToken"), OutRefreshToken, Present);
  const TSharedPtr<FJsonObject>* User = nullptr;
  if (LoginRef->TryGetObjectField(TEXT("user"), User) && User->IsValid()) {
    ReadStringPresence(User->ToSharedRef(), TEXT("id"), OutUserId, Present);
    ReadStringPresence(User->ToSharedRef(), TEXT("username"), OutUsername, Present);
  }
  return true;
}

bool FS08Contracts::ParseGameStateQuery(const FString& Body, FS08Snapshot& OutSnapshot,
                                        FString& OutRawState, FS08GraphQLError& OutError) {
  TSharedPtr<FJsonObject> Root;
  FString Problem;
  if (!ParseJsonString(Body, Root, Problem)) {
    OutError = {TEXT("PARSE"),
                FString::Printf(TEXT("gameState response is not valid JSON (%s)"), *Problem),
                FString()};
    return false;
  }
  TArray<FS08GraphQLError> Errors;
  if (ExtractGraphQLErrors(Root.ToSharedRef(), Errors)) {
    OutError = Errors[0];
    return false;
  }
  const TSharedPtr<FJsonObject>* Data = nullptr;
  if (!Root->TryGetObjectField(TEXT("data"), Data) || !Data->IsValid()) {
    OutError = {TEXT("PARSE"), TEXT("gameState response has no data object"), FString()};
    return false;
  }
  const TSharedPtr<FJsonObject>* State = nullptr;
  if (!(*Data)->TryGetObjectField(TEXT("gameState"), State) || !State->IsValid()) {
    OutError = {TEXT("PARSE"), TEXT("gameState response has no gameState payload (room not started?)"),
                TEXT("gameState")};
    return false;
  }
  const TSharedRef<FJsonObject> Payload = State->ToSharedRef();

  bool Present = false;
  if (!ReadIntLike(Payload, TEXT("sequenceNumber"), OutSnapshot.SequenceNumber, Present) || !Present) {
    OutError = {TEXT("PARSE"), TEXT("gameState missing sequenceNumber (wrong scalar)"),
                TEXT("gameState.sequenceNumber")};
    return false;
  }
  FString Phase;
  ReadStringPresence(Payload, TEXT("phase"), Phase, Present);
  if (!Present) {
    OutError = {TEXT("PARSE"), TEXT("gameState missing phase"), TEXT("gameState.phase")};
    return false;
  }
  OutSnapshot.Phase = Phase;
  ReadIntLike(Payload, TEXT("turnCount"), OutSnapshot.TurnCount, Present);
  ReadStringPresence(Payload, TEXT("currentTurnPlayerId"), OutSnapshot.CurrentTurnPlayerId, Present);

  // Stage one: the state field is a JSON STRING. Stage two: decode it.
  FString RawState;
  ReadStringPresence(Payload, TEXT("state"), RawState, Present);
  if (!Present || RawState.IsEmpty()) {
    OutError = {TEXT("PARSE"), TEXT("gameState.state missing or empty (wrong scalar?)"),
                TEXT("gameState.state")};
    return false;
  }
  OutRawState = RawState;
  TSharedPtr<FJsonObject> StateObject;
  FString StateProblem;
  if (!ParseJsonString(RawState, StateObject, StateProblem)) {
    OutError = {TEXT("PARSE"),
                FString::Printf(TEXT("gameState.state is not valid embedded JSON (%s)"),
                                *StateProblem),
                TEXT("gameState.state")};
    return false;
  }
  const TSharedRef<FJsonObject> Inner = StateObject.ToSharedRef();
  return DecodeInnerState(Inner, OutSnapshot, OutError);
}

bool FS08Contracts::DecodeInnerState(const TSharedRef<FJsonObject> Inner,
                                     FS08Snapshot& OutSnapshot, FS08GraphQLError& OutError) {
  bool Present = false;
  // Inner state carries its own scalars; when both envelope and inner exist
  // the inner value wins (both derive from the same server document).
  int32 InnerSeq = 0;
  if (ReadIntLike(Inner, TEXT("sequenceNumber"), InnerSeq, Present) && Present) {
    OutSnapshot.SequenceNumber = InnerSeq;
  }
  FString InnerPhase;
  if (ReadStringPresence(Inner, TEXT("phase"), InnerPhase, Present) && Present) {
    OutSnapshot.Phase = InnerPhase;
  }
  ReadStringPresence(Inner, TEXT("currentTurnPlayerId"), OutSnapshot.CurrentTurnPlayerId, Present);
  ReadIntLike(Inner, TEXT("turnCount"), OutSnapshot.TurnCount, Present);
  if (!DecodeJsonStringField(Inner, TEXT("players"), OutSnapshot.Players, Present, OutError)) return false;
  if (!DecodeJsonStringField(Inner, TEXT("fighters"), OutSnapshot.Fighters, Present, OutError)) return false;
  if (!DecodeJsonStringField(Inner, TEXT("handZones"), OutSnapshot.HandZones, Present, OutError)) return false;
  if (!DecodeJsonStringField(Inner, TEXT("discardPiles"), OutSnapshot.DiscardPiles, Present, OutError)) return false;
  if (!DecodeJsonStringField(Inner, TEXT("decks"), OutSnapshot.Decks, Present, OutError)) return false;
  if (!DecodeJsonStringField(Inner, TEXT("boardState"), OutSnapshot.BoardState, Present, OutError)) return false;
  if (!DecodeJsonStringField(Inner, TEXT("metadata"), OutSnapshot.Metadata, Present, OutError)) return false;
  return true;
}

bool FS08Contracts::ParseMutationResult(const FString& Body, const FString& FieldName,
                                        FS08Snapshot& OutSnapshot, FS08GraphQLError& OutError) {
  TSharedPtr<FJsonObject> Root;
  FString Problem;
  if (!ParseJsonString(Body, Root, Problem)) {
    OutError = {TEXT("PARSE"),
                FString::Printf(TEXT("mutation response is not valid JSON (%s)"), *Problem),
                FieldName};
    return false;
  }
  TArray<FS08GraphQLError> Errors;
  if (ExtractGraphQLErrors(Root.ToSharedRef(), Errors)) {
    OutError = Errors[0];
    return false;
  }
  const TSharedPtr<FJsonObject>* Data = nullptr;
  if (!Root->TryGetObjectField(TEXT("data"), Data) || !Data->IsValid()) {
    OutError = {TEXT("PARSE"), TEXT("mutation response has no data object"), FieldName};
    return false;
  }
  const TSharedPtr<FJsonObject>* Field = nullptr;
  if (!(*Data)->TryGetObjectField(FieldName, Field) || !Field->IsValid()) {
    OutError = {TEXT("PARSE"),
                FString::Printf(TEXT("mutation response has no %s payload"), *FieldName),
                FieldName};
    return false;
  }
  const TSharedRef<FJsonObject> Payload = Field->ToSharedRef();
  bool Present = false;
  if (!ReadIntLike(Payload, TEXT("sequenceNumber"), OutSnapshot.SequenceNumber, Present) || !Present) {
    OutError = {TEXT("PARSE"), TEXT("mutation result missing sequenceNumber"),
                FieldName + TEXT(".sequenceNumber")};
    return false;
  }
  ReadStringPresence(Payload, TEXT("phase"), OutSnapshot.Phase, Present);
  if (!Present) {
    OutError = {TEXT("PARSE"), TEXT("mutation result missing phase"),
                FieldName + TEXT(".phase")};
    return false;
  }
  ReadIntLike(Payload, TEXT("turnCount"), OutSnapshot.TurnCount, Present);
  ReadStringPresence(Payload, TEXT("currentTurnPlayerId"), OutSnapshot.CurrentTurnPlayerId, Present);
  // GameMutationResult.state: full viewer-projected state as JSON string.
  // null state (defensive server shape) leaves projections unset - the
  // seq-guarded store then waits for the WS event instead of guessing.
  FString RawState;
  ReadStringPresence(Payload, TEXT("state"), RawState, Present);
  if (!Present || RawState.IsEmpty()) return true;
  TSharedPtr<FJsonObject> StateObject;
  FString StateProblem;
  if (!ParseJsonString(RawState, StateObject, StateProblem)) {
    OutError = {TEXT("PARSE"),
                FString::Printf(TEXT("mutation result state is not valid embedded JSON (%s)"),
                                *StateProblem),
                FieldName + TEXT(".state")};
    return false;
  }
  return DecodeInnerState(StateObject.ToSharedRef(), OutSnapshot, OutError);
}

FString FS08Contracts::PendingManeuverId(const FS08Snapshot& Snapshot) {
  if (!Snapshot.Metadata.IsValid()) return FString();
  const TSharedPtr<FJsonObject> Meta = Snapshot.Metadata->AsObject();
  if (!Meta.IsValid()) return FString();
  const TSharedPtr<FJsonObject>* Pending = nullptr;
  if (!Meta->TryGetObjectField(TEXT("pendingManeuver"), Pending) || !Pending->IsValid()) {
    return FString();
  }
  return (*Pending)->GetStringField(TEXT("id"));
}

bool FS08Contracts::PendingHandDiscard(const FS08Snapshot& Snapshot,
                                       FS08PendingHandDiscard& OutPending) {
  OutPending = FS08PendingHandDiscard();
  if (!Snapshot.Metadata.IsValid()) return false;
  const TSharedPtr<FJsonObject> Meta = Snapshot.Metadata->AsObject();
  if (!Meta.IsValid()) return false;
  const TSharedPtr<FJsonObject>* Pending = nullptr;
  if (!Meta->TryGetObjectField(TEXT("pendingHandDiscard"), Pending) || !Pending->IsValid()) {
    return false;
  }
  OutPending.Id = (*Pending)->GetStringField(TEXT("id"));
  OutPending.PlayerId = (*Pending)->GetStringField(TEXT("playerId"));
  bool Present = false;
  int32 Count = 0;
  if (ReadIntLike(Pending->ToSharedRef(), TEXT("count"), Count, Present) && Present) {
    OutPending.Count = Count;
  }
  return !OutPending.Id.IsEmpty();
}

bool FS08Contracts::PendingHandDiscardStrict(const FS08Snapshot& Snapshot,
                                             FS08PendingHandDiscard& OutPending,
                                             bool& bOutFieldPresent) {
  OutPending = FS08PendingHandDiscard();
  bOutFieldPresent = false;
  if (!Snapshot.Metadata.IsValid()) return false;
  const TSharedPtr<FJsonObject> Meta = Snapshot.Metadata->AsObject();
  if (!Meta.IsValid()) return false;
  if (!Meta->HasField(TEXT("pendingHandDiscard"))) return false; // absent key
  bOutFieldPresent = true;
  const TSharedPtr<FJsonObject>* Pending = nullptr;
  if (!Meta->TryGetObjectField(TEXT("pendingHandDiscard"), Pending) || !Pending->IsValid()) {
    return false; // present but null / wrong type: unverifiable
  }
  OutPending.Id = (*Pending)->GetStringField(TEXT("id"));
  OutPending.PlayerId = (*Pending)->GetStringField(TEXT("playerId"));
  bool Present = false;
  int32 Count = 0;
  if (ReadIntLike(Pending->ToSharedRef(), TEXT("count"), Count, Present) && Present) {
    OutPending.Count = Count;
  }
  return !OutPending.Id.IsEmpty(); // present but no id: unverifiable
}

double FS08CombatInfo::SecondsUntilDeadline() const {
  if (!bHasTimeoutAt) return -1.0; // no parseable deadline: treat as closed
  return (TimeoutAt - FDateTime::UtcNow()).GetTotalSeconds();
}

bool FS08Contracts::CombatInfo(const FS08Snapshot& Snapshot, FS08CombatInfo& Out) {
  Out = FS08CombatInfo();
  if (!Snapshot.Metadata.IsValid()) return false;
  const TSharedPtr<FJsonObject> Meta = Snapshot.Metadata->AsObject();
  if (!Meta.IsValid()) return false;
  const TSharedPtr<FJsonObject>* Combat = nullptr;
  if (!Meta->TryGetObjectField(TEXT("combatInfo"), Combat) || !Combat->IsValid()) {
    return false;
  }
  const TSharedRef<FJsonObject> C = Combat->ToSharedRef();
  Out.bPresent = true;
  Out.AttackerId = C->GetStringField(TEXT("attackerId"));
  Out.DefenderId = C->GetStringField(TEXT("defenderId"));
  Out.TargetFighterId = C->GetStringField(TEXT("targetFighterId"));
  Out.AttackerCardId = C->GetStringField(TEXT("attackerCardId"));
  Out.DefenderCardId = C->GetStringField(TEXT("defenderCardId"));
  Out.CardBoostCardId = C->GetStringField(TEXT("cardBoostCardId"));
  Out.AbilityBoostCardId = C->GetStringField(TEXT("abilityBoostCardId"));
  Out.bHasAttackerCard = C->HasField(TEXT("attackerCardId")) && !Out.AttackerCardId.IsEmpty();
  Out.bHasDefenderCard = C->HasField(TEXT("defenderCardId")) && !Out.DefenderCardId.IsEmpty();
  Out.bHasCardBoostCardId =
      C->HasField(TEXT("cardBoostCardId")) && !Out.CardBoostCardId.IsEmpty();
  Out.bHasAbilityBoostCardId =
      C->HasField(TEXT("abilityBoostCardId")) && !Out.AbilityBoostCardId.IsEmpty();
  bool Present = false;
  int32 Value = 0;
  if (ReadIntLike(C, TEXT("attackValue"), Value, Present) && Present) {
    Out.bHasAttackValue = true;
    Out.AttackValue = Value;
  }
  if (ReadIntLike(C, TEXT("defenseValue"), Value, Present) && Present) {
    Out.bHasDefenseValue = true;
    Out.DefenseValue = Value;
  }
  if (ReadIntLike(C, TEXT("boostValue"), Value, Present) && Present) {
    Out.bHasBoostValue = true;
    Out.BoostValue = Value;
  }
  // ISO 8601 with fractional seconds + 'Z' (NestJS Date serialization).
  auto ParseIso = [](const FString& Text, FDateTime& OutTime) {
    FString Normalized = Text;
    int32 DotIndex = INDEX_NONE;
    if (Normalized.FindChar(TEXT('.'), DotIndex)) {
      // Trim the fraction to UE's expected 3 fractional digits, keep the tail.
      const int32 FractionStart = DotIndex + 1;
      int32 FractionEnd = FractionStart;
      while (FractionEnd < Normalized.Len() &&
             Normalized[FractionEnd] >= TEXT('0') && Normalized[FractionEnd] <= TEXT('9')) {
        ++FractionEnd;
      }
      const int32 FractionLen = FractionEnd - FractionStart;
      if (FractionLen > 3) {
        Normalized = Normalized.Left(FractionStart + 3) + Normalized.RightChop(FractionEnd);
      }
    }
    return FDateTime::ParseIso8601(*Normalized, OutTime);
  };
  FString Started = C->GetStringField(TEXT("startedAt"));
  if (!Started.IsEmpty() && ParseIso(Started, Out.StartedAt)) Out.bHasStartedAt = true;
  FString Timeout = C->GetStringField(TEXT("timeoutAt"));
  if (!Timeout.IsEmpty() && ParseIso(Timeout, Out.TimeoutAt)) Out.bHasTimeoutAt = true;
  // Reveal = the opponent's committed identity is visible in THIS body:
  // both committed cards present regardless of which seat is viewing.
  Out.bRevealed = Out.bHasAttackerCard && Out.bHasDefenderCard;
  return true;
}

namespace {
/** One pendingEffects array entry -> FS08PendingEffect (fields as sent). */
void ParsePendingEffectEntry(const TSharedRef<FJsonObject>& Obj, FS08PendingEffect& Entry) {
  Entry = FS08PendingEffect();
  Entry.Id = Obj->GetStringField(TEXT("id"));
  Entry.PlayerId = Obj->GetStringField(TEXT("playerId"));
  Entry.Type = Obj->GetStringField(TEXT("type"));
  bool bFlag = false;
  if (Obj->TryGetBoolField(TEXT("optional"), bFlag)) Entry.bOptional = bFlag;
  int32 Number = 0;
  bool bPresent = false;
  if (FS08Contracts::ReadIntLike(Obj, TEXT("value"), Number, bPresent) && bPresent) {
    Entry.Value = Number;
    Entry.bHasValue = true;
  }
  Entry.FighterName = Obj->GetStringField(TEXT("fighterName"));
  if (Obj->TryGetBoolField(TEXT("targetsOpponent"), bFlag)) Entry.bTargetsOpponent = bFlag;
  if (Obj->TryGetBoolField(TEXT("canPassThroughEnemies"), bFlag)) Entry.bCanPassThroughEnemies = bFlag;
  if (Obj->TryGetBoolField(TEXT("restoreFullHealth"), bFlag)) Entry.bRestoreFullHealth = bFlag;
  if (Obj->TryGetBoolField(TEXT("anyOwner"), bFlag)) Entry.bAnyOwner = bFlag;
  Entry.ZoneFighterName = Obj->GetStringField(TEXT("zoneFighterName"));
  Entry.Mode = Obj->GetStringField(TEXT("mode"));
  Entry.Text = Obj->GetStringField(TEXT("text"));
  if (FS08Contracts::ReadIntLike(Obj, TEXT("damage"), Number, bPresent) && bPresent) {
    Entry.Damage = Number;
    Entry.bHasDamage = true;
  }
  if (FS08Contracts::ReadIntLike(Obj, TEXT("stage"), Number, bPresent) && bPresent) {
    Entry.Stage = Number;
  }
  if (FS08Contracts::ReadIntLike(Obj, TEXT("drawIfDefeated"), Number, bPresent) && bPresent) {
    Entry.DrawIfDefeated = Number;
  }
  if (FS08Contracts::ReadIntLike(Obj, TEXT("revealedCount"), Number, bPresent) && bPresent) {
    Entry.RevealedCount = Number;
    Entry.bHasRevealedCount = true;
  }
  if (FS08Contracts::ReadIntLike(Obj, TEXT("chooseCount"), Number, bPresent) && bPresent && Number >= 1) {
    Entry.ChooseCount = Number;
  }
  const TSharedPtr<FJsonObject>* Anchor = nullptr;
  if (Obj->TryGetObjectField(TEXT("anchor"), Anchor) && Anchor->IsValid()) {
    bool bCoord = false;
    if (FS08Contracts::ReadIntLike(Anchor->ToSharedRef(), TEXT("x"), Entry.AnchorX, bCoord) && bCoord) {
      if (FS08Contracts::ReadIntLike(Anchor->ToSharedRef(), TEXT("y"), Entry.AnchorY, bCoord) && bCoord) {
        Entry.bHasAnchor = true;
      }
    }
  }
  const TArray<TSharedPtr<FJsonValue>>* Ids = nullptr;
  if (Obj->TryGetArrayField(TEXT("fighterIds"), Ids) && Ids) {
    for (const TSharedPtr<FJsonValue>& Id : *Ids) {
      const FString Parsed = Id.IsValid() ? Id->AsString() : FString();
      if (!Parsed.IsEmpty()) Entry.FighterIds.Add(Parsed);
    }
  }
  if (Obj->TryGetArrayField(TEXT("targetFighterIds"), Ids) && Ids) {
    for (const TSharedPtr<FJsonValue>& Id : *Ids) {
      const FString Parsed = Id.IsValid() ? Id->AsString() : FString();
      if (!Parsed.IsEmpty()) Entry.TargetFighterIds.Add(Parsed);
    }
  }
  const TArray<TSharedPtr<FJsonValue>>* Options = nullptr;
  if (Obj->TryGetArrayField(TEXT("options"), Options) && Options) {
    for (const TSharedPtr<FJsonValue>& Option : *Options) {
      const TSharedPtr<FJsonObject>* OptionObj = nullptr;
      if (!Option.IsValid() || !Option->TryGetObject(OptionObj) || !OptionObj->IsValid()) {
        continue;
      }
      FS08PendingOption Parsed;
      bool bIndex = false;
      if (FS08Contracts::ReadIntLike(OptionObj->ToSharedRef(), TEXT("index"), Parsed.Index, bIndex) && bIndex) {
        Parsed.Label = (*OptionObj)->GetStringField(TEXT("label"));
        Entry.Options.Add(MoveTemp(Parsed));
      }
    }
  }
  // Owner-only projection (the opponent's copy has no revealedCards).
  const TSharedPtr<FJsonValue> Cards = Obj->TryGetField(TEXT("revealedCards"));
  if (Cards.IsValid() && !Cards->IsNull() && Cards->Type == EJson::Array) {
    Entry.RevealedCards = Cards;
  }
}
} // namespace

bool FS08Contracts::PendingEffects(const FS08Snapshot& Snapshot,
                                   TArray<FS08PendingEffect>& OutEffects) {
  OutEffects.Reset();
  if (!Snapshot.Metadata.IsValid()) return false;
  const TSharedPtr<FJsonObject> Meta = Snapshot.Metadata->AsObject();
  if (!Meta.IsValid()) return false;
  const TArray<TSharedPtr<FJsonValue>>* Effects = nullptr;
  if (!Meta->TryGetArrayField(TEXT("pendingEffects"), Effects) || !Effects) return false;
  for (const TSharedPtr<FJsonValue>& Value : *Effects) {
    const TSharedPtr<FJsonObject>* Effect = nullptr;
    if (!Value.IsValid() || !Value->TryGetObject(Effect) || !Effect->IsValid()) continue;
    FS08PendingEffect Entry;
    ParsePendingEffectEntry(Effect->ToSharedRef(), Entry);
    if (!Entry.Id.IsEmpty()) OutEffects.Add(MoveTemp(Entry));
  }
  return OutEffects.Num() > 0;
}

bool FS08Contracts::PendingEffectsStrict(const FS08Snapshot& Snapshot,
                                         TArray<FS08PendingEffect>& OutEffects,
                                         bool& bOutArrayPresent) {
  OutEffects.Reset();
  bOutArrayPresent = false;
  if (!Snapshot.Metadata.IsValid()) return false;
  const TSharedPtr<FJsonObject> Meta = Snapshot.Metadata->AsObject();
  if (!Meta.IsValid()) return false;
  const TArray<TSharedPtr<FJsonValue>>* Effects = nullptr;
  if (!Meta->TryGetArrayField(TEXT("pendingEffects"), Effects) || !Effects) {
    // The KEY exists but the value is not an array (e.g. pendingEffects:null):
    // present-but-invalid, never "absent" - a complete body cannot prove
    // resolution through it.
    bOutArrayPresent = Meta->HasField(TEXT("pendingEffects"));
    return false;
  }
  bOutArrayPresent = true;
  for (const TSharedPtr<FJsonValue>& Value : *Effects) {
    const TSharedPtr<FJsonObject>* Effect = nullptr;
    if (!Value.IsValid() || !Value->TryGetObject(Effect) || !Effect->IsValid()) {
      // Malformed entry: the queue is UNVERIFIABLE - never read it as empty.
      OutEffects.Reset();
      return false;
    }
    FS08PendingEffect Entry;
    ParsePendingEffectEntry(Effect->ToSharedRef(), Entry);
    if (Entry.Id.IsEmpty()) {
      OutEffects.Reset();
      return false;
    }
    OutEffects.Add(MoveTemp(Entry));
  }
  return true;
}

bool FS08Contracts::IsHiddenCardId(const FString& InstanceId) {
  // Server placeholder convention (GameStateService.filterPrivateData):
  // id `hidden-<index>`, cardId `hidden`, name `???`.
  return InstanceId.StartsWith(TEXT("hidden-")) || InstanceId == TEXT("hidden");
}

bool FS08Contracts::IsHiddenCard(const TSharedPtr<FJsonValue>& CardValue) {
  const TSharedPtr<FJsonObject>* Card = nullptr;
  if (!CardValue.IsValid() || !CardValue->TryGetObject(Card) || !Card->IsValid()) {
    return false;
  }
  if (IsHiddenCardId((*Card)->GetStringField(TEXT("id")))) return true;
  if ((*Card)->GetStringField(TEXT("cardId")) == TEXT("hidden")) return true;
  return false;
}

bool FS08Contracts::ParseGameStateUpdated(const TSharedRef<FJsonObject> Data,
                                          FS08Snapshot& OutSnapshot, FS08GraphQLError& OutError) {
  bool Present = false;
  if (!ReadIntLike(Data, TEXT("sequenceNumber"), OutSnapshot.SequenceNumber, Present) || !Present) {
    OutError = {TEXT("PARSE"), TEXT("gameStateUpdated event missing sequenceNumber"),
                TEXT("sequenceNumber")};
    return false;
  }
  FString Phase;
  ReadStringPresence(Data, TEXT("phase"), Phase, Present);
  if (!Present) {
    OutError = {TEXT("PARSE"), TEXT("gameStateUpdated event missing phase"), TEXT("phase")};
    return false;
  }
  OutSnapshot.Phase = Phase;
  ReadIntLike(Data, TEXT("turnCount"), OutSnapshot.TurnCount, Present);
  ReadStringPresence(Data, TEXT("currentTurnPlayerId"), OutSnapshot.CurrentTurnPlayerId, Present);
  if (!DecodeJsonStringField(Data, TEXT("players"), OutSnapshot.Players, Present, OutError)) return false;
  if (!DecodeJsonStringField(Data, TEXT("fighters"), OutSnapshot.Fighters, Present, OutError)) return false;
  if (!DecodeJsonStringField(Data, TEXT("handZones"), OutSnapshot.HandZones, Present, OutError)) return false;
  if (!DecodeJsonStringField(Data, TEXT("discardPiles"), OutSnapshot.DiscardPiles, Present, OutError)) return false;
  // Live WS events omit decks (merge keeps the last counts); decoding here
  // anyway makes a future contract addition backward-compatible for free.
  if (!DecodeJsonStringField(Data, TEXT("decks"), OutSnapshot.Decks, Present, OutError)) return false;
  if (!DecodeJsonStringField(Data, TEXT("boardState"), OutSnapshot.BoardState, Present, OutError)) return false;
  if (!DecodeJsonStringField(Data, TEXT("metadata"), OutSnapshot.Metadata, Present, OutError)) return false;
  return true;
}

bool FS08Contracts::ValidateCriticalFields(const FS08Snapshot& Snapshot,
                                           const FString& ViewerPlayerId,
                                           TArray<FString>& OutProblems) {
  OutProblems.Reset();
  if (Snapshot.SequenceNumber < 1) {
    OutProblems.Add(TEXT("sequenceNumber must be >= 1 for an applied snapshot"));
  }
  if (Snapshot.Phase.IsEmpty()) {
    OutProblems.Add(TEXT("phase is missing - cannot determine game stage"));
  }
  // Validation runs on the MERGED applied snapshot (ApplySnapshot keeps
  // local copies of absent projections), so a missing/short projection here
  // is a real gap and must block input.
  if (!Snapshot.Players.IsValid() || EntryCount(Snapshot.Players) < 2) {
    OutProblems.Add(TEXT("players projection missing or has fewer than 2 entries"));
  }
  if (!Snapshot.Fighters.IsValid() || EntryCount(Snapshot.Fighters) < 2) {
    OutProblems.Add(TEXT("fighters projection missing or has fewer than 2 entries"));
  }
  if (!Snapshot.BoardState.IsValid()) {
    OutProblems.Add(TEXT("boardState is missing - board cannot be rendered"));
  } else {
    const TSharedPtr<FJsonObject> BoardObject = Snapshot.BoardState->AsObject();
    const TSharedPtr<FJsonValue> Cells =
        BoardObject.IsValid() ? BoardObject->TryGetField(TEXT("cells")) : nullptr;
    if (!Cells.IsValid() || Cells->IsNull()) {
      OutProblems.Add(TEXT("boardState.cells is missing - board layout unknown"));
    }
  }
  if (ViewerPlayerId.IsEmpty()) {
    OutProblems.Add(TEXT("viewer identity unknown - hand zone cannot be resolved"));
  } else if (Snapshot.HandZones.IsValid()) {
    const TSharedPtr<FJsonObject> HandObject = Snapshot.HandZones->AsObject();
    if (!HandObject.IsValid() || !HandObject->HasField(ViewerPlayerId)) {
      OutProblems.Add(FString::Printf(TEXT("handZones has no entry for viewer '%s'"), *ViewerPlayerId));
    }
  } else {
    OutProblems.Add(TEXT("handZones missing - own hand cannot be displayed"));
  }
  return OutProblems.Num() == 0;
}

// ---- MS-T-06: rule codes (move-selection 02 §1.1) ------------------------------

const TCHAR* FS08Rejection::ClassLetter() const {
  // Cyrillic I / S of the 02 §1.1 class column (the trace file is UTF-8).
  return Class == ES08RejectClass::Fixable ? TEXT("И") : TEXT("С");
}

const TCHAR* FS08Rejection::OpName(ES08RejectOp InOp) {
  switch (InOp) {
    case ES08RejectOp::Begin: return TEXT("begin");
    case ES08RejectOp::Maneuver: return TEXT("maneuver");
    default: return TEXT("pending");
  }
}

namespace {
struct FS08RuleRow {
  const TCHAR* Code;
  const TCHAR* ManeuverKey; // begin / maneuver
  const TCHAR* EffectKey;   // resolvePendingEffect (MOVE/PLACE)
  ES08RejectClass ManeuverClass;
  ES08RejectClass EffectClass;
};
// The rows of 02 §1.1, in its order. PATH_BLOCKED_BY_ENEMY's key depends on the
// cell (Classify); "why.cell.enemy.path" here is its off-target form.
constexpr ES08RejectClass S08RcFixable = ES08RejectClass::Fixable;
constexpr ES08RejectClass S08RcState = ES08RejectClass::State;
const FS08RuleRow GS08RuleRows[] = {
    {TEXT("FIGHTER_NOT_FOUND"), TEXT("why.client.desync"), TEXT("why.client.desync"), S08RcState, S08RcState},
    {TEXT("NOT_YOUR_FIGHTER"), TEXT("why.fighter.not.yours"), TEXT("why.fighter.not.yours"), S08RcFixable, S08RcFixable},
    {TEXT("FIGHTER_DEFEATED"), TEXT("why.fighter.defeated"), TEXT("why.fighter.defeated"), S08RcState, S08RcState},
    {TEXT("FIGHTER_IMMOBILIZED"), TEXT("why.immobilized"), TEXT("why.immobilized"), S08RcFixable, S08RcFixable},
    {TEXT("INVALID_PHASE"), TEXT("why.maneuver.not.open"), TEXT("why.maneuver.not.open"), S08RcState, S08RcState},
    {TEXT("HAND_NOT_FOUND"), TEXT("why.client.desync"), TEXT("why.client.desync"), S08RcState, S08RcState},
    {TEXT("CARD_NOT_IN_HAND"), TEXT("why.boost.card.gone"), TEXT("why.boost.card.gone"), S08RcFixable, S08RcFixable},
    {TEXT("EMPTY_PATH"), TEXT("why.client.desync"), TEXT("why.client.desync"), S08RcState, S08RcState},
    {TEXT("INVALID_POSITION"), TEXT("why.client.desync"), TEXT("why.cell.not.space"), S08RcState, S08RcFixable},
    {TEXT("NOT_ENOUGH_MOVEMENT"), TEXT("why.cell.unreachable"), TEXT("why.cell.unreachable"), S08RcFixable, S08RcFixable},
    {TEXT("INVALID_STEP"), TEXT("why.client.desync"), TEXT("why.client.desync"), S08RcState, S08RcState},
    {TEXT("PATH_BLOCKED_BY_ENEMY"), TEXT("why.cell.enemy.path"), TEXT("why.cell.enemy.path"), S08RcFixable, S08RcFixable},
    {TEXT("POSITION_OCCUPIED"), TEXT("why.cell.ally"), TEXT("why.cell.occupied"), S08RcFixable, S08RcFixable},
    {TEXT("NOT_YOUR_TURN"), TEXT("why.not.your.turn"), TEXT("why.not.your.turn"), S08RcState, S08RcState},
    {TEXT("PLAYER_NOT_IN_GAME"), TEXT("why.client.desync"), TEXT("why.client.desync"), S08RcState, S08RcState},
    {TEXT("BEGIN_NOT_ALLOWED"), TEXT("why.client.desync"), TEXT("why.client.desync"), S08RcState, S08RcState},
    {TEXT("STATE_CHANGED"), TEXT("why.state.changed"), TEXT("why.state.changed"), S08RcState, S08RcState},
    {TEXT("PENDING_CHOICE_OPEN"), TEXT("why.state.changed"), TEXT("why.state.changed"), S08RcState, S08RcState},
    {TEXT("COMBAT_IN_PROGRESS"), TEXT("why.state.changed"), TEXT("why.state.changed"), S08RcState, S08RcState},
    {TEXT("GAME_OVER"), TEXT("why.state.changed"), TEXT("why.state.changed"), S08RcState, S08RcState},
    {TEXT("MANEUVER_NOT_OPEN"), TEXT("why.maneuver.not.open"), TEXT("why.maneuver.not.open"), S08RcState, S08RcState},
    {TEXT("DUPLICATE_FIGHTER"), TEXT("why.client.desync"), TEXT("why.client.desync"), S08RcState, S08RcState},
    {TEXT("PENDING_WRONG_FIGHTER"), TEXT("why.client.desync"), TEXT("why.client.desync"), S08RcState, S08RcState},
    {TEXT("PLACE_OUTSIDE_ZONE"), TEXT("why.place.zone"), TEXT("why.place.zone"), S08RcFixable, S08RcFixable},
    {TEXT("BOOST_NO_VALUE"), TEXT("why.boost.no.value"), TEXT("why.boost.no.value"), S08RcFixable, S08RcFixable},
};

bool S08RcParseIntAt(const FString& Text, int32& InOutIndex, int32& OutValue) {
  int32 Index = InOutIndex;
  const bool bNegative = Index < Text.Len() && Text[Index] == TEXT('-');
  if (bNegative) ++Index;
  const int32 Start = Index;
  int64 Value = 0;
  while (Index < Text.Len() && FChar::IsDigit(Text[Index]) && Index - Start < 9) {
    Value = Value * 10 + (Text[Index] - TEXT('0'));
    ++Index;
  }
  if (Index == Start) return false;
  OutValue = static_cast<int32>(bNegative ? -Value : Value);
  InOutIndex = Index;
  return true;
}

/** Numbers of a message in reading order ("Путь длиной 3 ... (2)" -> 3, 2). */
TArray<int32> S08RcNumbersIn(const FString& Text) {
  TArray<int32> Out;
  for (int32 Index = 0; Index < Text.Len();) {
    int32 Value = 0;
    int32 Cursor = Index;
    if (FChar::IsDigit(Text[Index]) && S08RcParseIntAt(Text, Cursor, Value)) {
      Out.Add(Value);
      Index = Cursor;
    } else {
      ++Index;
    }
  }
  return Out;
}
} // namespace

bool FS08RuleCodes::CellInMessage(const FString& Message, FIntPoint& OutCell) {
  // The last "(x, y)" / "(x,y)" group of the text.
  for (int32 Open = Message.Len() - 1; Open >= 0; --Open) {
    if (Message[Open] != TEXT('(')) continue;
    int32 Index = Open + 1;
    int32 X = 0, Y = 0;
    if (!S08RcParseIntAt(Message, Index, X)) continue;
    if (Index >= Message.Len() || Message[Index] != TEXT(',')) continue;
    ++Index;
    while (Index < Message.Len() && Message[Index] == TEXT(' ')) ++Index;
    if (!S08RcParseIntAt(Message, Index, Y)) continue;
    if (Index >= Message.Len() || Message[Index] != TEXT(')')) continue;
    OutCell = FIntPoint(X, Y);
    return true;
  }
  return false;
}

const TArray<FString>& FS08RuleCodes::KnownCodes() {
  static const TArray<FString> Codes = [] {
    TArray<FString> Out;
    for (const FS08RuleRow& Row : GS08RuleRows) Out.Add(Row.Code);
    return Out;
  }();
  return Codes;
}

FS08Rejection FS08RuleCodes::Classify(const TArray<FS08GraphQLError>& Errors, ES08RejectOp Op,
                                      const TArray<FIntPoint>& Destinations) {
  FS08Rejection Out;
  Out.Op = Op;
  const FS08GraphQLError* First = Errors.Num() > 0 ? &Errors[0] : nullptr;
  if (First) {
    Out.RuleCode = First->RuleCode;
    Out.Message = First->Message;
  }
  bool bRateLimited = false;
  for (const FS08GraphQLError& Error : Errors) {
    bRateLimited |= Error.HttpStatus == 429 || Error.Code == TEXT("RATE_LIMIT") ||
                    Error.Code == TEXT("TOO_MANY_REQUESTS");
  }
  if (bRateLimited) {
    // 02 §1.1: the throttle answer - why.syncing, repeated only by the player.
    Out.WhyKey = FName(TEXT("why.syncing"));
    Out.Class = ES08RejectClass::Fixable;
    Out.bRefetch = false;
    return Out;
  }
  const FS08RuleRow* Row = nullptr;
  for (const FS08RuleRow& Candidate : GS08RuleRows) {
    if (Out.RuleCode.Equals(Candidate.Code, ESearchCase::CaseSensitive)) Row = &Candidate;
  }
  if (!Row) {
    // MS-E-93: a guard rejection without a code or an unknown code.
    Out.WhyKey = FName(TEXT("why.command.rejected"));
    Out.Class = ES08RejectClass::State;
    return Out;
  }
  const bool bEffect = Op == ES08RejectOp::PendingEffect;
  Out.WhyKey = FName(bEffect ? Row->EffectKey : Row->ManeuverKey);
  Out.Class = bEffect ? Row->EffectClass : Row->ManeuverClass;
  FIntPoint Cell;
  if (CellInMessage(Out.Message, Cell)) {
    Out.Cell = Cell;
  } else if (Destinations.Num() == 1 &&
             (Out.WhyKey.ToString().StartsWith(TEXT("why.cell.")) || Out.WhyKey == FName(TEXT("why.place.zone")))) {
    // One end cell in the command: the space the rejection is about.
    Out.Cell = Destinations[0];
  }
  if (Out.RuleCode == TEXT("PLACE_OUTSIDE_ZONE")) {
    // "Клетка должна быть в зоне «{fighterName}»"
    const int32 Open = Out.Message.Find(TEXT("«"));
    const int32 Close = Out.Message.Find(TEXT("»"), ESearchCase::CaseSensitive, ESearchDir::FromEnd);
    if (Open != INDEX_NONE && Close > Open + 1) Out.WhyArgs.Add(TEXT("fighterName"), Out.Message.Mid(Open + 1, Close - Open - 1));
  }
  if (Out.RuleCode == TEXT("PATH_BLOCKED_BY_ENEMY")) {
    // The validator checks every path cell including the target (MS-E-21).
    if (Out.Cell.X >= 0 && Destinations.Contains(Out.Cell)) Out.WhyKey = FName(TEXT("why.cell.enemy"));
  } else if (Out.RuleCode == TEXT("NOT_ENOUGH_MOVEMENT")) {
    const TArray<int32> Numbers = S08RcNumbersIn(Out.Message);
    if (!bEffect && Numbers.Num() >= 2) {
      // "Путь длиной {need} превышает очки движения бойца ({have})"
      Out.WhyArgs.Add(TEXT("need"), FString::FromInt(Numbers[0]));
      Out.WhyArgs.Add(TEXT("have"), FString::FromInt(Numbers[1]));
    } else if (bEffect && Numbers.Num() >= 3) {
      // "До клетки (x, y) не добраться за {have} шаг(ов)"
      Out.WhyArgs.Add(TEXT("have"), FString::FromInt(Numbers[2]));
    }
  }
  return Out;
}

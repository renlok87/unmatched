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
    const TSharedPtr<FJsonObject>* Extensions = nullptr;
    if ((*ErrorObj)->TryGetObjectField(TEXT("extensions"), Extensions) && Extensions->IsValid()) {
      (*Extensions)->TryGetStringField(TEXT("code"), Error.Code);
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
                                      FString& OutUsername, FS08GraphQLError& OutError) {
  TSharedPtr<FJsonObject> Root;
  FString Problem;
  if (!ParseJsonString(Body, Root, Problem)) {
    OutError = {TEXT("PARSE"),
                FString::Printf(TEXT("Login response is not valid JSON (%s)"), *Problem),
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
    OutError = {TEXT("PARSE"), TEXT("Login response has no data object"), FString()};
    return false;
  }
  const TSharedPtr<FJsonObject>* Login = nullptr;
  if (!(*Data)->TryGetObjectField(TEXT("login"), Login) || !Login->IsValid()) {
    OutError = {TEXT("PARSE"), TEXT("Login response has no login payload"), FString()};
    return false;
  }
  const TSharedRef<FJsonObject> LoginRef = Login->ToSharedRef();
  bool Present = false;
  FString Token;
  ReadStringPresence(LoginRef, TEXT("accessToken"), Token, Present);
  if (!Present || Token.IsEmpty()) {
    OutError = {TEXT("PARSE"), TEXT("Login response missing accessToken"), TEXT("login.accessToken")};
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

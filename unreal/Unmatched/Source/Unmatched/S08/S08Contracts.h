// GD-028: wire contracts and two-stage JSON-string parsing for the
// unmatched-net/1 protocol. Scalars follow the live SDL dumped to
// docs/game-design/evidence/S08/live-schema.graphql:
//   - GameStateResponse.sequenceNumber/turnCount arrive as Float (NestJS number)
//   - GameState (WS event) sequenceNumber is Int
//   - DateTime (updatedAt) serializes as epoch-milliseconds number
//   - GameStateResponse.state and GameState players/fighters/handZones/
//     discardPiles/boardState/metadata are JSON STRINGS: the parser must
//     decode them in a second stage (two-stage parsing).
#pragma once

#include "CoreMinimal.h"

/** Actionable client-facing error extracted from a GraphQL response. */
struct UNMATCHED_API FS08GraphQLError {
  FString Code;    // extensions.code or "GRAPHQL" / "TRANSPORT" / "PARSE"
  FString Message; // human-readable, safe to show (backend sanitizes)
  FString Path;    // dotted response path when present
};

/** Snapshot of a viewer-projected game state (HTTP query gameState and WS
 *  gameStateUpdated). Merge semantics per unmatched-net/1 section 2: absent
 *  fields stay untouched on the client copy - the server may omit them.
 *  Projections are kept as FJsonValue because the wire encodes players/
 *  fighters as JSON ARRAYS and the rest as objects; the WS variant ships
 *  every projection as a JSON STRING that needs second-stage decoding. */
struct UNMATCHED_API FS08Snapshot {
  int32 SequenceNumber = 0;
  FString Phase;
  int32 TurnCount = 0;
  FString CurrentTurnPlayerId;
  // Second-stage decoded projections (arrays or objects; raw text kept for
  // diagnostics in ParseGameStateQuery's OutRawState).
  TSharedPtr<FJsonValue> Players;
  TSharedPtr<FJsonValue> Fighters;
  TSharedPtr<FJsonValue> HandZones;
  TSharedPtr<FJsonValue> DiscardPiles; // S05: reveal faces of committed combat cards
  TSharedPtr<FJsonValue> BoardState;
  TSharedPtr<FJsonValue> Metadata;
};

enum class ES08SeqDecision : uint8 { Ignore, Merge, Apply };

/** Sequence guard per unmatched-net/1 section 1: '<' stale -> ignore,
 *  '==' same -> merge (idempotency), '>' newer -> apply (gap allowed). */
struct UNMATCHED_API FS08SeqGuard {
  int32 Local = 0;
  bool HasLocal = false;
  ES08SeqDecision Decide(int32 Incoming);
  void Commit(int32 Incoming);
};

class UNMATCHED_API FS08Contracts {
public:
  // ---- Auth ----
  static bool ParseAuthResponse(const FString& Body, FString& OutAccessToken,
                                FString& OutRefreshToken, FString& OutUserId,
                                FString& OutUsername, FS08GraphQLError& OutError);

  // ---- HTTP query gameState(gameId) ----
  // Returns false with OutError on GraphQL errors[], malformed body or
  // missing critical envelope fields (gameId/sequenceNumber/state).
  static bool ParseGameStateQuery(const FString& Body, FS08Snapshot& OutSnapshot,
                                  FString& OutRawState, FS08GraphQLError& OutError);

  // ---- WS gameStateUpdated payload (data field of "next") ----
  static bool ParseGameStateUpdated(const TSharedRef<FJsonObject> Data,
                                    FS08Snapshot& OutSnapshot, FS08GraphQLError& OutError);

  // ---- Gameplay mutation result (beginManeuver/maneuver/...).
  // GameMutationResult ships the full viewer-projected state as a JSON
  // STRING plus envelope scalars (sequenceNumber/phase/...). Parsed through
  // the same inner-state decoder, so mutation echoes and WS events of the
  // same seq produce identical FS08Snapshot values (ACC-011 dedupe basis).
  static bool ParseMutationResult(const FString& Body, const FString& FieldName,
                                  FS08Snapshot& OutSnapshot, FS08GraphQLError& OutError);

  /** Inner-state decoder shared by gameState query, WS events and mutation
   *  results: merges envelope fields (envelope wins) and decodes projections
   *  (arrays/objects natively, JSON strings via DecodeJsonStringField). */
  static bool DecodeInnerState(const TSharedRef<FJsonObject> Inner,
                               FS08Snapshot& OutSnapshot, FS08GraphQLError& OutError);

  /** pendingManeuver id from the decoded metadata projection ('' when the
   *  state has no open maneuver choice). */
  static FString PendingManeuverId(const FS08Snapshot& Snapshot);

  // ---- Critical-field validation (unmatched-net/1: incomplete state must
  //      BLOCK input instead of guessing). Returns the list of problems. ----
  static bool ValidateCriticalFields(const FS08Snapshot& Snapshot,
                                     const FString& ViewerPlayerId,
                                     TArray<FString>& OutProblems);

  // ---- Helpers ----
  /** Structural JSON validation with a bounds-checked scanner (pure TCHAR
   *  walk, never crashes). UE's TJsonReader::ParseStringToken can read past
   *  the end of a truncated string (trailing backslash / partial \u escape /
   *  unterminated string) and fatally crash, so EVERY network text must pass
   *  this scan BEFORE FJsonSerializer::Deserialize is invoked. OutProblem is
   *  human-readable and includes the offending offset. */
  static bool ValidateJsonText(const FString& Text, FString& OutProblem);
  /** Crash-safe object parse: ValidateJsonText first, then the UE reader. */
  static bool TryParseJsonObject(const FString& Text, TSharedPtr<FJsonObject>& OutObject,
                                 FString& OutProblem);
  /** Crash-safe value parse: ValidateJsonText first, then the UE reader. */
  static bool TryParseJsonValue(const FString& Text, TSharedPtr<FJsonValue>& OutValue,
                                FString& OutProblem);
  /** Extracts a readable summary of GraphQL errors[] on HTTP 200. */
  static bool ExtractGraphQLErrors(const TSharedRef<FJsonObject> Root,
                                   TArray<FS08GraphQLError>& OutErrors);
  /** True when the error means "no state yet" (lobby phase) - recoverable,
   *  not fatal: recovery re-polls the room instead of blocking input. */
  static bool IsLobbyPhaseAbsent(const TArray<FS08GraphQLError>& Errors);
  /** Two-stage decode of a projection field. The WS event ships projections
   *  as JSON strings (decoded here); the HTTP state embeds them as native
   *  arrays/objects (taken as-is). Null/absent -> unset (merge semantics
   *  allow partial bodies). Invalid JSON string -> error. */
  static bool DecodeJsonStringField(const TSharedRef<FJsonObject> Object,
                                    const FString& FieldName,
                                    TSharedPtr<FJsonValue>& OutValue,
                                    bool& OutWasPresent, FS08GraphQLError& OutError);
  /** Entry count of a decoded projection: array length or object key count. */
  static int32 EntryCount(const TSharedPtr<FJsonValue>& Value);
  /** Reads Int-or-Float scalars (NestJS emits Float for untyped numbers). */
  static bool ReadIntLike(const TSharedRef<FJsonObject> Object, const FString& FieldName,
                          int32& OutValue, bool& OutWasPresent);
};

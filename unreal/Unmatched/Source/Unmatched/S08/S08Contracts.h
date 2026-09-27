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
  FString Code;    // extensions.code or "GRAPHQL" / "TRANSPORT" / "PARSE" /
                   // "AUTH" / "RATE_LIMIT" / "SESSION_EXPIRED"
  FString Message; // human-readable, safe to show (backend sanitizes)
  FString Path;    // dotted response path when present
  int32 HttpStatus = 0; // raw HTTP status when the response was not 200
                        // (0 = no HTTP answer at all / transport loss)
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
  // GD-032: deck projections. The HTTP gameState query and every mutation
  // echo carry `decks` (hidden placeholders, array LENGTH = live count); the
  // WS gameStateUpdated event does NOT (unmatched-net/1 section 2 - merge,
  // never replace: an event without decks keeps the last known counts and
  // the HUD marks them stale until the next full body arrives).
  TSharedPtr<FJsonValue> Decks;
  TSharedPtr<FJsonValue> BoardState;
  TSharedPtr<FJsonValue> Metadata;
};

/** GD-033: TURN_END discard-to-limit choice (metadata.pendingHandDiscard). */
struct UNMATCHED_API FS08PendingHandDiscard {
  FString Id;
  FString PlayerId;
  int32 Count = 0; // EXACT number of own hand instances to discard
};

/** GD-034: metadata.combatInfo - the authoritative combat window. Presence of
 *  a value field is itself the privacy contract (filterPrivateData cuts the
 *  opponent's committed value/card before reveal): bHasAttackValue is TRUE
 *  only for the attacker (or after reveal), bHasDefenderCard only for the
 *  defender (or after reveal). Clients must render from these flags, never
 *  guess a missing value. */
struct UNMATCHED_API FS08CombatInfo {
  bool bPresent = false;
  FString AttackerId;      // attacking fighter id
  FString DefenderId;      // DEFENDING USER id (target's owner)
  FString TargetFighterId; // attacked fighter id
  bool bHasAttackerCard = false;
  FString AttackerCardId;
  bool bHasDefenderCard = false;
  FString DefenderCardId;
  bool bHasAttackValue = false;
  int32 AttackValue = 0;
  bool bHasDefenseValue = false;
  int32 DefenseValue = 0;
  bool bHasBoostValue = false;
  int32 BoostValue = 0;
  bool bHasCardBoostCardId = false;
  FString CardBoostCardId;
  bool bHasAbilityBoostCardId = false;
  FString AbilityBoostCardId;
  FDateTime StartedAt;  // server wall clock (ISO 8601)
  bool bHasStartedAt = false;
  FDateTime TimeoutAt;  // server-authoritative stage deadline (ISO 8601)
  bool bHasTimeoutAt = false;

  /** Seconds until the deadline (negative when expired). Falls back to a
   *  conservative closed window when the timestamp never parsed. */
  double SecondsUntilDeadline() const;
  /** Reveal (both cards visible) = opponent's committed identity arrived. */
  bool bRevealed = false;
};

/** GD-035: one labeled option of a CHOOSE_ONE pending (server options[]). */
struct UNMATCHED_API FS08PendingOption {
  int32 Index = -1;
  FString Label;
};

/** GD-034/035: one metadata.pendingEffects queue entry (head = the choice
 *  the server is waiting on). Mirrors backend PendingEffect
 *  (game-state.model.ts): every field is optional on the wire and parsed
 *  defensively - a malformed entry degrades to its defaults and is only
 *  dropped when the id is missing. Privacy (ACC-018/GameStateService
 *  filterPrivateData): revealedCards ships ONLY in the owner's projection -
 *  the opponent's entry carries RevealedCount instead; this struct never
 *  decodes card faces, it keeps the raw array for the owner-side UI. */
struct UNMATCHED_API FS08PendingEffect {
  FString Id;
  FString PlayerId;
  FString Type; // MOVE | PLACE | CHOOSE_ONE | TARGET_FIGHTER | DISCARD_CARDS | BOOST_CHOICE | CHOOSE_SPACE | DECK_TOP_PICK
  bool bOptional = false; // true ONLY when the server sends optional:true ("You may …")
  // MOVE distance / DISCARD_CARDS exact count / DECK_TOP_PICK pick count
  int32 Value = 0;
  bool bHasValue = false;
  FString FighterName;            // MOVE/PLACE banner restriction from card text
  bool bTargetsOpponent = false;  // PLACE moves the OPPONENT's fighter
  TArray<FString> FighterIds;     // fighters the effect may move/target
  TArray<FString> TargetFighterIds; // TARGET_FIGHTER legal damage targets
  int32 Damage = 0;
  bool bHasDamage = false;
  bool bCanPassThroughEnemies = false; // MOVE: enemies do not block the path
  FString ZoneFighterName;        // PLACE/CHOOSE_SPACE stage 1: cell must share this fighter's zone
  bool bRestoreFullHealth = false; // PLACE revive (defeated fighter allowed)
  bool bAnyOwner = false;         // MOVE (Skirmish): any fighter of the effect list
  int32 Stage = 0;                // CHOOSE_SPACE: 1 | 2 (0 = absent)
  bool bHasAnchor = false;        // CHOOSE_SPACE stage 2 anchor of adjacency
  int32 AnchorX = 0, AnchorY = 0;
  int32 DrawIfDefeated = 0;       // CHOOSE_SPACE conditional draw
  int32 RevealedCount = 0;        // DECK_TOP_PICK: how many are revealed (opponent view)
  bool bHasRevealedCount = false;
  FString Mode;                   // DECK_TOP_PICK: "PICK" | "ORDER"
  FString Text;                   // source card text (log/UI prompt)
  TArray<FS08PendingOption> Options; // CHOOSE_ONE labeled options
  int32 ChooseCount = 1;          // CHOOSE_ONE remaining picks (multi-step)
  TSharedPtr<FJsonValue> RevealedCards; // owner-only raw array (never for the opponent)
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
  /** AuthResponseDto parser shared by login and refreshTokens (FieldName
   *  picks the data.<Field> payload; both return the same shape). */
  static bool ParseAuthResponse(const FString& Body, FString& OutAccessToken,
                                FString& OutRefreshToken, FString& OutUserId,
                                FString& OutUsername, FS08GraphQLError& OutError,
                                const TCHAR* FieldName = TEXT("login"));

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

  /** GD-033: pendingHandDiscard from the metadata projection. False when the
   *  state carries no open discard-to-limit choice. */
  static bool PendingHandDiscard(const FS08Snapshot& Snapshot,
                                 FS08PendingHandDiscard& OutPending);

  /** GD-034: metadata.combatInfo. False when no combat window is open. Field
   *  presence mirrors the viewer projection (see FS08CombatInfo). */
  static bool CombatInfo(const FS08Snapshot& Snapshot, FS08CombatInfo& Out);

  /** GD-034: metadata.pendingEffects queue (server order; [0] is the choice
   *  being waited on). False when the queue is absent/empty. */
  static bool PendingEffects(const FS08Snapshot& Snapshot,
                             TArray<FS08PendingEffect>& OutEffects);

  /** GD-032 privacy: a hand/discard entry is a server-side hidden
   *  placeholder (viewer may not learn its identity). Such cards carry no
   *  face into any HUD list, inspector or trace line - count only. */
  static bool IsHiddenCard(const TSharedPtr<FJsonValue>& CardValue);
  static bool IsHiddenCardId(const FString& InstanceId);

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

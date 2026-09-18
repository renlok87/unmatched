// UmModel/Public/UmDto.h
// USTRUCT-DTO GraphQL-ответов (ярус 1 двухфазного парсинга — ADR §5.2, §4.2 «UmApiDtos.h»).
//
// ВНИМАНИЕ (уточнение к ADR): ADR §3.3 называет этот файл `UmApiDtos.h`; здесь он записан как `UmDto.h` по заданию группы
// сниппетов. При материализации проекта имя файла должно совпасть с ADR (`UmApiDtos.h`) — содержимое не меняется.
//
// Конвенции (ADR §3.6):
//  * UPROPERTY — PascalCase; сопоставление с camelCase-ключами JSON регистронезависимое: FJsonObjectConverter ищет ключ через
//    TMap<FString,…>::Find, а хэш/сравнение FString регистронезависимы (JsonObjectConverter.cpp:1338-1339).
//    Поэтому bool-поля, приходящие с провода, названы БЕЗ префикса `b` (`IsReady` ↔ "isReady"); поля, вычисляемые
//    парсером/клиентом, — с префиксом `b` (их ключей в JSON нет).
//  * Wire-enum'ы хранятся как FString + аксессор через UmEnums::Parse<E> (толерантно, ADR §5.2).
//  * Скаляры, которые в живой схеме `Float` (R3 §2.4: GameStateResponse.sequenceNumber/turnCount, GamePlayerResponse.seatOrder,
//    GameResponse.version, Presence.lastSeenAt, HeartbeatResponse.ttl) — double + аксессор в int64/int32.
//  * `DateTime` в GraphQL-полях — epoch-миллисекунды (число), внутри JSON-состояния — ISO-строки (R3 §2.4, §2.11).
//    FUmDateTime принимает оба формата через CustomImportCallback (R8 §2.4: колбэк имеет приоритет над дефолтом,
//    JsonObjectConverter.cpp:584-590). JSON null пропускается конвертером (JsonObjectConverter.cpp:1356) — поле остаётся bSet=false.
//  * Парсинг: FUmDtoJson::FromJsonObject<T>(...) — JsonObjectToUStruct(bStrictMode=false): отсутствующие поля допустимы
//    (JsonObjectConverter.cpp:1341-1353), лишние — игнорируются.
//
// Источники полей: R1 §2.7-2.8 (auth/users), R2 §2.2 (лобби, матчмейкинг, presence), R3 §2.5, §2.8, §2.12 (игра),
// R5 §2.3 (контент), R6 §2.2 (admin-списки).

#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "JsonObjectConverter.h"
#include "Misc/DateTime.h"
#include "Misc/Timespan.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/UnrealType.h"
#include "UmEnums.h"

#include "UmDto.generated.h"

// =====================================================================================================================
// FUmDateTime — дата в двух wire-форматах (ADR §4.2)
// =====================================================================================================================

/** Дата из GraphQL `DateTime` (epoch-ms число — date-time.scalar.ts:13-16) либо ISO-8601-строка (даты внутри JSON-состояния). */
USTRUCT()
struct UMMODEL_API FUmDateTime
{
	GENERATED_BODY()

	/** Момент в UTC. Валиден только при bSet. */
	UPROPERTY()
	FDateTime Utc;

	/** true, если значение пришло и распознано; false — поле отсутствовало/null/мусор. */
	UPROPERTY()
	bool bSet = false;

	/** Исходные epoch-миллисекунды (для чисел — как пришло; для ISO — пересчитано). */
	UPROPERTY()
	int64 EpochMs = 0;

	static FDateTime UnixEpoch() { return FDateTime(1970, 1, 1); }

	static FUmDateTime FromEpochMs(int64 InEpochMs)
	{
		FUmDateTime Out;
		Out.EpochMs = InEpochMs;
		Out.Utc = UnixEpoch() + FTimespan(InEpochMs * ETimespan::TicksPerMillisecond);
		Out.bSet = true;
		return Out;
	}

	static bool FromIso8601(const FString& Iso, FUmDateTime& Out)
	{
		FDateTime Parsed;
		if (!FDateTime::ParseIso8601(*Iso, Parsed))
		{
			return false;
		}
		Out.Utc = Parsed;
		Out.EpochMs = (Parsed - UnixEpoch()).GetTicks() / ETimespan::TicksPerMillisecond;
		Out.bSet = true;
		return true;
	}

	/** Число → epoch-ms; строка → ISO 8601 (fallback FDateTime::Parse); null/прочее → bSet=false. Возвращает true, если значение потреблено. */
	static bool FromJsonValue(const TSharedPtr<FJsonValue>& Value, FUmDateTime& Out)
	{
		Out = FUmDateTime();
		if (!Value.IsValid() || Value->IsNull())
		{
			return true;
		}
		if (Value->Type == EJson::Number)
		{
			int64 Ms = 0;
			if (Value->TryGetNumber(Ms))
			{
				Out = FromEpochMs(Ms);
			}
			return true;
		}
		if (Value->Type == EJson::String)
		{
			const FString Str = Value->AsString();
			if (!FromIso8601(Str, Out))
			{
				FDateTime Parsed;
				if (FDateTime::Parse(Str, Parsed))
				{
					Out.Utc = Parsed;
					Out.EpochMs = (Parsed - UnixEpoch()).GetTicks() / ETimespan::TicksPerMillisecond;
					Out.bSet = true;
				}
			}
			return true;
		}
		return false;
	}
};

// =====================================================================================================================
// FUmDtoJson — единая точка конвертации JSON → DTO (bStrictMode=false + колбэк FUmDateTime)
// =====================================================================================================================

struct UMMODEL_API FUmDtoJson
{
	/** CustomImportCallback: перехватывает только FUmDateTime; для остальных свойств возвращает false («fall through to default»). */
	static bool ImportProperty(const TSharedPtr<FJsonValue>& JsonValue, FProperty* Property, void* Value)
	{
		if (const FStructProperty* StructProperty = CastField<FStructProperty>(Property))
		{
			if (StructProperty->Struct == FUmDateTime::StaticStruct())
			{
				return FUmDateTime::FromJsonValue(JsonValue, *static_cast<FUmDateTime*>(Value));
			}
		}
		return false;
	}

	static const FJsonObjectConverter::CustomImportCallback& GetImportCallback()
	{
		static const FJsonObjectConverter::CustomImportCallback Callback =
			FJsonObjectConverter::CustomImportCallback::CreateStatic(&FUmDtoJson::ImportProperty);
		return Callback;
	}

	/** JSON-объект → USTRUCT. Нестрогий режим; неизвестные ключи игнорируются; при ошибке импорта поля — false + OutFailReason. */
	template <typename T>
	static bool FromJsonObject(const TSharedPtr<FJsonObject>& Object, T& Out, FText* OutFailReason = nullptr)
	{
		if (!Object.IsValid())
		{
			return false;
		}
		return FJsonObjectConverter::JsonObjectToUStruct(
			Object.ToSharedRef(), T::StaticStruct(), &Out,
			/*CheckFlags*/ 0, /*SkipFlags*/ 0, /*bStrictMode*/ false, OutFailReason, &GetImportCallback());
	}

	/** JSON-строка (объект) → USTRUCT. */
	template <typename T>
	static bool FromJsonString(const FString& Json, T& Out, FText* OutFailReason = nullptr)
	{
		TSharedPtr<FJsonObject> Object;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
		if (!FJsonSerializer::Deserialize(Reader, Object) || !Object.IsValid())
		{
			return false;
		}
		return FromJsonObject<T>(Object, Out, OutFailReason);
	}

	/** JSON-массив объектов → TArray<USTRUCT>. Элементы, не являющиеся объектами, пропускаются. */
	template <typename T>
	static bool FromJsonArray(const TArray<TSharedPtr<FJsonValue>>& Array, TArray<T>& Out, FText* OutFailReason = nullptr)
	{
		Out.Reset(Array.Num());
		bool bAllOk = true;
		for (const TSharedPtr<FJsonValue>& Item : Array)
		{
			const TSharedPtr<FJsonObject>* ItemObject = nullptr;
			if (!Item.IsValid() || !Item->TryGetObject(ItemObject) || !ItemObject || !ItemObject->IsValid())
			{
				continue;
			}
			T& Element = Out.AddDefaulted_GetRef();
			bAllOk &= FromJsonObject<T>(*ItemObject, Element, OutFailReason);
		}
		return bAllOk;
	}
};

// =====================================================================================================================
// Auth / users — R1 §2.7-2.8
// =====================================================================================================================

/** AuthUserResponse / UserResponse — auth-response.dto.ts:19-53; R1 §2.7. */
USTRUCT()
struct UMMODEL_API FUmAuthUserDto
{
	GENERATED_BODY()

	UPROPERTY() FString Id;
	UPROPERTY() FString Email;
	UPROPERTY() FString Username;
	UPROPERTY() FString Avatar;          // nullable
	UPROPERTY() FString Role;            // enum UserRole: USER | ADMIN | MODERATOR
	UPROPERTY() FUmDateTime CreatedAt;
	UPROPERTY() FUmDateTime EmailVerified; // nullable

	EUmUserRole GetRole() const { return UmEnums::ParseUserRole(Role); }
};

/** AuthResponseDto — auth-response.dto.ts:19-53 (мутации register/login/refreshTokens; R1 §2.7). */
USTRUCT()
struct UMMODEL_API FUmAuthResponseDto
{
	GENERATED_BODY()

	UPROPERTY() FString AccessToken;
	UPROPERTY() FString RefreshToken;
	UPROPERTY() FUmAuthUserDto User;
};

/** UserSettingsResponse / UserSettingsGraphql — settings.dto.ts:39-61; R1 §2.8. */
USTRUCT()
struct UMMODEL_API FUmUserSettingsDto
{
	GENERATED_BODY()

	UPROPERTY() FString Id;
	UPROPERTY() FString Theme;      // light | dark | auto
	UPROPERTY() FString Language;   // ru | en
	UPROPERTY() bool SoundEnabled = true;
	UPROPERTY() bool MusicEnabled = true;
	UPROPERTY() bool ProfileVisible = true;
	UPROPERTY() bool ShowOnlineStatus = true;
};

/** UserWithSettingsResponse (query me) — R1 §2.8; `me.id` — единственный источник userId (ADR §4.1 UUmAuthSubsystem). */
USTRUCT()
struct UMMODEL_API FUmMeDto
{
	GENERATED_BODY()

	UPROPERTY() FString Id;
	UPROPERTY() FString Email;
	UPROPERTY() FString Username;
	UPROPERTY() FString Avatar;
	UPROPERTY() FString Role;
	UPROPERTY() FUmDateTime CreatedAt;
	UPROPERTY() FUmDateTime EmailVerified;
	UPROPERTY() FUmUserSettingsDto Settings; // nullable: при null остаётся дефолт (Settings.Id пуст)

	EUmUserRole GetRole() const { return UmEnums::ParseUserRole(Role); }
	bool HasSettings() const { return !Settings.Id.IsEmpty(); }
};

/** PublicUserResponse — R1 §2.8 (при profileVisible=false — username "Hidden"). */
USTRUCT()
struct UMMODEL_API FUmPublicUserDto
{
	GENERATED_BODY()

	UPROPERTY() FString Id;
	UPROPERTY() FString Username;
	UPROPERTY() FString Avatar;
	UPROPERTY() FUmDateTime CreatedAt;
};

/** FavoriteHero — R1 §2.8. */
USTRUCT()
struct UMMODEL_API FUmFavoriteHeroDto
{
	GENERATED_BODY()

	UPROPERTY() FString Id;
	UPROPERTY() FString Name;
	UPROPERTY() FString NameEn;
	UPROPERTY() FString NameRu;
};

/** UserStatsResponse (myStats/stats) — R1 §2.8. */
USTRUCT()
struct UMMODEL_API FUmUserStatsDto
{
	GENERATED_BODY()

	UPROPERTY() FString UserId;
	UPROPERTY() int32 GamesPlayed = 0;
	UPROPERTY() int32 GamesWon = 0;
	UPROPERTY() int32 GamesLost = 0;
	UPROPERTY() double WinRate = 0.0;   // Float!
	UPROPERTY() int32 CurrentElo = 0;
	UPROPERTY() int32 PeakElo = 0;
	UPROPERTY() FUmDateTime LastPlayedAt; // nullable
	UPROPERTY() int32 TotalPlayTime = 0;
	UPROPERTY() FUmFavoriteHeroDto FavoriteHero; // nullable
};

// =====================================================================================================================
// Лобби / игра — R2 §2.2; R3 §2.5, §2.8, §2.12
// =====================================================================================================================

/** GamePlayerResponse — game-player.model.ts:4-28; R3 §2.5. `seatOrder: Float!` (R3 §2.4). */
USTRUCT()
struct UMMODEL_API FUmGamePlayerDto
{
	GENERATED_BODY()

	UPROPERTY() FString Id;        // у host/opponent = User.id, у players[] = id записи GamePlayer (R2 §2.2) — идентифицировать по UserId
	UPROPERTY() FString UserId;
	UPROPERTY() FString Username;
	UPROPERTY() FString Avatar;    // nullable
	UPROPERTY() FString HeroId;    // nullable; Prisma cuid героя
	UPROPERTY() bool IsReady = false;
	UPROPERTY() bool HasPassed = false;
	UPROPERTY() double SeatOrder = 0.0; // Float!

	int32 GetSeatOrder() const { return static_cast<int32>(SeatOrder); }
};

/** GameResponse — game.model.ts:6-63; R3 §2.5. `version: Float!`; `phase/currentTurn` — лоббийные поля Prisma, для геймплея ненадёжны (R3 §4.16). */
USTRUCT()
struct UMMODEL_API FUmGameResponseDto
{
	GENERATED_BODY()

	UPROPERTY() FString Id;
	UPROPERTY() FString Code;       // nullable
	UPROPERTY() FString Status;     // enum GameStatus
	UPROPERTY() FString Mode;       // enum GameMode
	UPROPERTY() FString HostId;
	UPROPERTY() FUmGamePlayerDto Host;
	UPROPERTY() FString OpponentId; // nullable
	UPROPERTY() FUmGamePlayerDto Opponent; // nullable → дефолт (см. HasOpponent)
	UPROPERTY() FString BoardId;
	UPROPERTY() FString BoardState; // nullable, для игры не нужно (R3 §2.11)
	UPROPERTY() FUmDateTime CreatedAt;
	UPROPERTY() FUmDateTime UpdatedAt;
	UPROPERTY() FUmDateTime StartedAt; // nullable
	UPROPERTY() FUmDateTime EndedAt;   // nullable
	UPROPERTY() FString WinnerId;      // nullable
	UPROPERTY() double Version = 0.0;  // Float!
	UPROPERTY() TArray<FUmGamePlayerDto> Players;
	UPROPERTY() FString Phase;         // enum GamePhase, nullable
	UPROPERTY() int32 CurrentTurn = -1; // Int, nullable (−1 = отсутствует)

	EUmGameStatus GetStatus() const { return UmEnums::ParseGameStatus(Status); }
	EUmGameMode GetMode() const { return UmEnums::ParseGameMode(Mode); }
	EUmGamePhase GetPhase() const { return UmEnums::ParseGamePhase(Phase); }
	int64 GetVersion() const { return static_cast<int64>(Version); }
	/** Уточнение к ADR (там `bHasOpponent` от парсера): признак вычисляется по `opponentId`/`opponent.userId`, флаг не нужен. */
	bool HasOpponent() const { return !OpponentId.IsEmpty() || !Opponent.UserId.IsEmpty(); }
};

/** GameStateResponse (query gameState) — game.model.ts:66-90; R3 §2.5. `sequenceNumber/turnCount: Float!`, `phase: String!` (не enum). */
USTRUCT()
struct UMMODEL_API FUmGameStateResponseDto
{
	GENERATED_BODY()

	UPROPERTY() FString Id;        // "<gameId>-state"
	UPROPERTY() FString GameId;
	UPROPERTY() FString State;     // JSON полного GameState (с decks/discardPiles) → FUmGameStateParser::ParseFull
	UPROPERTY() double SequenceNumber = 0.0; // Float!
	UPROPERTY() FString CurrentTurnPlayerId; // nullable
	UPROPERTY() FString Phase;
	UPROPERTY() double TurnCount = 0.0;      // Float!
	UPROPERTY() FUmDateTime UpdatedAt;       // = metadata.lastActionAt

	int64 GetSequenceNumber() const { return static_cast<int64>(SequenceNumber); }
	int32 GetTurnCount() const { return static_cast<int32>(TurnCount); }
	EUmGamePhase GetPhase() const { return UmEnums::ParseGamePhase(Phase); }
};

/** GameMutationResult — единый ответ 11 gameplay-мутаций; gameplay.dto.ts:437-458; R3 §2.8. `timestamp` — epoch-ms. */
USTRUCT()
struct UMMODEL_API FUmGameMutationResultDto
{
	GENERATED_BODY()

	UPROPERTY() FString State;     // nullable по схеме, на практике всегда JSON полного состояния
	UPROPERTY() int32 SequenceNumber = 0; // Int!
	UPROPERTY() FUmDateTime Timestamp;    // DateTime! (момент ответа сервера)
	UPROPERTY() FString Phase;            // GamePhase!
	UPROPERTY() FString CurrentTurnPlayerId; // nullable
	UPROPERTY() int32 TurnCount = 0;      // Int!

	EUmGamePhase GetPhase() const { return UmEnums::ParseGamePhase(Phase); }
};

/** GameState (payload подписки gameStateUpdated) — gameplay.dto.ts:461-495; R3 §2.12. Пять JSON-строк, БЕЗ decks/discardPiles. */
USTRUCT()
struct UMMODEL_API FUmGameStateSubscriptionDto
{
	GENERATED_BODY()

	UPROPERTY() FString GameId;
	UPROPERTY() int32 SequenceNumber = 0;  // Int!
	UPROPERTY() FString Phase;             // GamePhase!
	UPROPERTY() int32 TurnCount = 0;       // Int!
	UPROPERTY() FString CurrentTurnPlayerId; // String! (non-null в подписке — R3 §4.14)
	UPROPERTY() FString Players;    // JSON-строка GameStatePlayer[]
	UPROPERTY() FString Fighters;   // JSON-строка Fighter[]
	UPROPERTY() FString HandZones;  // JSON-строка Record<userId, HandZone>
	UPROPERTY() FString BoardState; // JSON-строка BoardState
	UPROPERTY() FString Metadata;   // JSON-строка GameStateMetadata

	EUmGamePhase GetPhase() const { return UmEnums::ParseGamePhase(Phase); }
};

/** GameEvent — gameplay.dto.ts:395-413; R3 §2.12. `payload` — JSON-строка {phase, turnCount, currentTurnPlayerId} | null;
 *  для eventsSince — {action, input} (R3 §2.5); для лобби — {userId, username} / {userId} / {reason, abortedBy} (R2 §2.6). */
USTRUCT()
struct UMMODEL_API FUmGameEventDto
{
	GENERATED_BODY()

	UPROPERTY() FString Type;      // GameEventType! (в eventsSince — Prisma GameActionType, подмножество)
	UPROPERTY() FString GameId;
	UPROPERTY() int32 SequenceNumber = 0; // Int!
	UPROPERTY() FUmDateTime Timestamp;    // epoch-ms публикации; не использовать для дедлайнов (R3 §3.12)
	UPROPERTY() FString Payload;          // nullable JSON-строка

	EUmGameEventType GetType() const { return UmEnums::ParseGameEventType(Type); }
};

/** TurnState (подписка turnChanged) — gameplay.dto.ts:380-392; `playerId` = следующий игрок (R3 §2.12). Молчит при авто-передаче хода (R4 §3.3). */
USTRUCT()
struct UMMODEL_API FUmTurnStateDto
{
	GENERATED_BODY()

	UPROPERTY() FString PlayerId;
	UPROPERTY() int32 TurnCount = 0;
	UPROPERTY() FString Phase; // GamePhase!

	EUmGamePhase GetPhase() const { return UmEnums::ParseGamePhase(Phase); }
};

/** EventsSinceResponse — gameplay.dto.ts:569-582; R3 §2.5 (≤100 событий; журнал неполон — R3 §4.10). */
USTRUCT()
struct UMMODEL_API FUmEventsSinceDto
{
	GENERATED_BODY()

	UPROPERTY() FString GameId;
	UPROPERTY() TArray<FUmGameEventDto> Events;
	UPROPERTY() int32 LastSequence = 0; // Int!
	UPROPERTY() bool HasMore = false;
};

/** StanceOptionDto (query heroStances) — gameplay.dto.ts:362-375; R3 §2.5; R4 §2.13. */
USTRUCT()
struct UMMODEL_API FUmStanceOptionDto
{
	GENERATED_BODY()

	UPROPERTY() FString Id;    // 'big' | 'small' | 'float' | 'sting' (ability-config.ts:850-893)
	UPROPERTY() FString Label;
	UPROPERTY() bool IsDefault = false;
};

// =====================================================================================================================
// Контент — R5 §2.3 (content.dto.ts)
// =====================================================================================================================

/** HeroAbility — content.dto.ts; R5 §2.3 (у скрапнутых героев: name = "Ability", trigger = PASSIVE). */
USTRUCT()
struct UMMODEL_API FUmHeroAbilityDto
{
	GENERATED_BODY()

	UPROPERTY() FString Id;
	UPROPERTY() FString Name;
	UPROPERTY() FString Text;
	UPROPERTY() FString Trigger; // enum AbilityTrigger

	EUmAbilityTrigger GetTrigger() const { return UmEnums::ParseAbilityTrigger(Trigger); }
};

/** HeroUrls — R5 §2.3: avatar = avatarUrl; mini/cardCover = imageUrl || avatarUrl. */
USTRUCT()
struct UMMODEL_API FUmHeroUrlsDto
{
	GENERATED_BODY()

	UPROPERTY() FString Avatar;
	UPROPERTY() FString Mini;
	UPROPERTY() FString CardCover;
};

/** CardEffect (контентный) — только {id, text}; `timing` не выбирается (R5 §4.1; ADR §4.2). */
USTRUCT()
struct UMMODEL_API FUmContentEffectDto
{
	GENERATED_BODY()

	UPROPERTY() FString Id;
	UPROPERTY() FString Text;
};

/** Card (контент) — content.dto.ts:69-100; R5 §2.3. `id` = Prisma cuid шаблона (в игре HandCard.cardId). */
USTRUCT()
struct UMMODEL_API FUmCardDto
{
	GENERATED_BODY()

	UPROPERTY() FString Id;
	UPROPERTY() FString Title;
	UPROPERTY() FString Type;          // контентный CardType (MANEUVER/UNIVERSAL → VERSATILE на сервере)
	UPROPERTY() int32 Value = 0;       // attackValue ?? defenseValue ?? boostValue ?? 0 — для SCHEME это BOOST (R5 §2.3)
	UPROPERTY() int32 Boost = 0;
	UPROPERTY() int32 Quantity = 0;    // число копий в колоде
	UPROPERTY() FString CharacterName; // = название карты (nameEn || name), НЕ banner (R5 §2.3)
	UPROPERTY() FString ImageUrl;      // nullable
	UPROPERTY() FString ImageUrlRu;    // nullable
	UPROPERTY() TArray<FUmContentEffectDto> Effects;

	EUmContentCardType GetType() const { return UmEnums::ParseContentCardType(Type); }
};

/** Hero (контент) — content.dto.ts:102-155; R5 §2.3. `id` = Hero.name (не cuid); `movement` — константа 3, не доверять. */
USTRUCT()
struct UMMODEL_API FUmHeroDto
{
	GENERATED_BODY()

	UPROPERTY() FString Id;
	UPROPERTY() FString Name;
	UPROPERTY() FString NameEn;
	UPROPERTY() FString NameRu;
	UPROPERTY() int32 Health = 0;
	UPROPERTY() int32 Movement = 0;      // всегда 3 (content.mapper.ts:64,200) — реальное движение в Fighter.movement
	UPROPERTY() FString Set;
	UPROPERTY() TArray<FUmHeroAbilityDto> Abilities;
	UPROPERTY() TArray<FUmCardDto> Cards; // field-resolver, выбирается в hero(id)
	UPROPERTY() FString FighterType;     // контентный FighterType (HERO/SIDEKICK); в hero/heroesBySet всегда HERO (R5 §4.7)
	UPROPERTY() int32 SidekickCount = -1; // nullable (−1 = отсутствует)
	UPROPERTY() int32 SidekickHealth = -1; // nullable; никем не пишется → всегда null (R5 §2.3)
	UPROPERTY() FUmHeroUrlsDto Urls;     // nullable
	UPROPERTY() FString ImageUrl;        // только heroes/heroesPaginated
	UPROPERTY() FString AvatarUrl;       // только heroes/heroesPaginated
	UPROPERTY() FUmDateTime CreatedAt;   // только heroes/heroesPaginated
	UPROPERTY() FUmDateTime UpdatedAt;

	EUmContentFighterType GetFighterType() const { return UmEnums::ParseContentFighterType(FighterType); }
};

/** Позиция клетки контентной доски (BoardSpace.position) — content.dto.ts:157-203. */
USTRUCT()
struct UMMODEL_API FUmBoardPositionDto
{
	GENERATED_BODY()

	UPROPERTY() int32 X = 0;
	UPROPERTY() int32 Y = 0;
};

/** BoardSpace — content.dto.ts:157-203; R5 §2.3. `zones` — GraphQL-enum Zone (UPPER). `startingPositionsJson` не заполняется. */
USTRUCT()
struct UMMODEL_API FUmBoardSpaceDto
{
	GENERATED_BODY()

	UPROPERTY() FUmBoardPositionDto Position;
	UPROPERTY() TArray<FString> Zones;
	UPROPERTY() bool IsObstacle = false; // nullable

	TArray<EUmZone> GetZones() const
	{
		TArray<EUmZone> Out;
		Out.Reserve(Zones.Num());
		for (const FString& Zone : Zones) { Out.Add(UmEnums::ParseZone(Zone)); }
		return Out;
	}
};

/** Board (контент) — content.dto.ts:157-203; R5 §2.3. `id` = Board.name; width/height у скрапнутых досок — пиксели! Размер сетки — из spaces (R5 §3.5). */
USTRUCT()
struct UMMODEL_API FUmBoardDto
{
	GENERATED_BODY()

	UPROPERTY() FString Id;
	UPROPERTY() FString Name;
	UPROPERTY() int32 Width = 0;
	UPROPERTY() int32 Height = 0;
	UPROPERTY() int32 RecommendedPlayers = 2; // константа 2
	UPROPERTY() TArray<FUmBoardSpaceDto> Spaces;
	UPROPERTY() FString ImageUrl; // nullable

	/** Размер сетки по spaces: (max x + 1, max y + 1); (0,0) если spaces пуст. */
	FIntPoint GetGridSize() const
	{
		FIntPoint Size(0, 0);
		for (const FUmBoardSpaceDto& Space : Spaces)
		{
			Size.X = FMath::Max(Size.X, Space.Position.X + 1);
			Size.Y = FMath::Max(Size.Y, Space.Position.Y + 1);
		}
		return Size;
	}
};

/** ContentSummary — content.dto.ts:245-260; ADR §4.2. */
USTRUCT()
struct UMMODEL_API FUmContentSummaryDto
{
	GENERATED_BODY()

	UPROPERTY() FString Version;
	UPROPERTY() int32 HeroesCount = 0;
	UPROPERTY() int32 BoardsCount = 0;
	UPROPERTY() int32 SetsCount = 0;
	UPROPERTY() TArray<FString> Sets;
};

/** Элемент admin `heroList` (cuid) — R6 §2.2 п.3/4; ADR §4.2. Нужен для связки GamePlayer.heroId (cuid) ↔ контент. */
USTRUCT()
struct UMMODEL_API FUmHeroListItemDto
{
	GENERATED_BODY()

	UPROPERTY() FString Id;   // Prisma cuid
	UPROPERTY() FString Name;
	UPROPERTY() FString NameEn;
	UPROPERTY() FString NameRu;
	UPROPERTY() FString Set;
	UPROPERTY() FString FighterType;
	UPROPERTY() FString Ability;
	UPROPERTY() FString ImageUrl;
	UPROPERTY() FString AvatarUrl;
	UPROPERTY() double Health = 0.0; // Float
	UPROPERTY() FUmDateTime CreatedAt;
};

/** Элемент admin `boardList` (cuid) — R6 §2.2 п.9/10; ADR §4.2. `boardId` в createGame — cuid. */
USTRUCT()
struct UMMODEL_API FUmBoardListItemDto
{
	GENERATED_BODY()

	UPROPERTY() FString Id;   // Prisma cuid
	UPROPERTY() FString Name;
	UPROPERTY() FString Set;
	UPROPERTY() FString ImageUrl;
	UPROPERTY() FString ImageUrlDark;
	UPROPERTY() int32 Width = 0;
	UPROPERTY() int32 Height = 0;
	UPROPERTY() FUmDateTime CreatedAt;
};

// TODO(C4): форма ответов `heroesPaginated`/`boardsPaginated` (обёртка пагинации) в R5 §2.2 — добавить FUmHeroesPaginatedDto
// после сверки полей с introspection (unreal/Schema/schema.introspection.json — ADR §3.7).

// =====================================================================================================================
// Матчмейкинг / presence — R2 §2.2 (под feature-flag Feature.Matchmaking / Feature.Presence, ADR §3.5)
// =====================================================================================================================

/** QueueStatusResponse — queue-status-response.dto.ts:3-22. */
USTRUCT()
struct UMMODEL_API FUmQueueStatusDto
{
	GENERATED_BODY()

	UPROPERTY() bool InQueue = false;
	UPROPERTY() FString Mode;          // nullable
	UPROPERTY() int32 Position = -1;   // nullable Int
	UPROPERTY() int32 TotalPlayers = 0;
	UPROPERTY() int32 EstimatedWaitTime = 0;
	UPROPERTY() FUmDateTime JoinedAt;  // nullable
};

/** MatchFoundResponse (подписка matchFound(userId)) — match-found-response.dto.ts:3-22. */
USTRUCT()
struct UMMODEL_API FUmMatchFoundDto
{
	GENERATED_BODY()

	UPROPERTY() FString GameId;
	UPROPERTY() FString OpponentId;
	UPROPERTY() FString OpponentUsername;
	UPROPERTY() int32 OpponentRating = 0;
	UPROPERTY() FString Mode;
	UPROPERTY() FUmDateTime ExpiresAt;
};

/** PenaltyInfoDto — penalty-info.dto.ts:3-19. */
USTRUCT()
struct UMMODEL_API FUmPenaltyInfoDto
{
	GENERATED_BODY()

	UPROPERTY() bool CanJoinQueue = true;
	UPROPERTY() int32 DeclineCount = 0;
	UPROPERTY() FUmDateTime TempBanUntil; // nullable
	UPROPERTY() int32 PenaltyElo = 0;     // nullable
	UPROPERTY() FString Reason;           // nullable
};

/** Presence — presence.dto.ts:9-40. `lastSeenAt: Float!` — epoch-ms числом (R2 §2.2). */
USTRUCT()
struct UMMODEL_API FUmPresenceDto
{
	GENERATED_BODY()

	UPROPERTY() FString UserId;
	UPROPERTY() FString Status;        // enum PresenceStatus
	UPROPERTY() FString CurrentGameId; // nullable
	UPROPERTY() double LastSeenAt = 0.0; // Float! epoch-ms

	EUmPresenceStatus GetStatus() const { return UmEnums::ParsePresenceStatus(Status); }
	FUmDateTime GetLastSeenAt() const { return FUmDateTime::FromEpochMs(static_cast<int64>(LastSeenAt)); }
};

/** HeartbeatResponse — heartbeat.dto.ts:4-11. `ttl: Float!`. */
USTRUCT()
struct UMMODEL_API FUmHeartbeatDto
{
	GENERATED_BODY()

	UPROPERTY() FUmPresenceDto Presence;
	UPROPERTY() double Ttl = 0.0;
};

/** OnlineUsersResponse — R2 §2.2. `count: Float!`. */
USTRUCT()
struct UMMODEL_API FUmOnlineUsersDto
{
	GENERATED_BODY()

	UPROPERTY() TArray<FString> UserIds;
	UPROPERTY() double Count = 0.0;
};

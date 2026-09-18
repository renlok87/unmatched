// UmModel/Public/UmEnums.h
// Все wire-enum'ы контракта бэкенда + толерантные парсеры (ADR §4.2 «UmEnums.h»; R3 §2.3).
//
// Принципы (ADR §5.2, К1 §3.4.1 п.2):
//  * На проводе enum'ы приходят строками. В USTRUCT-DTO они хранятся как FString,
//    а в UENUM переводятся ТОЛЬКО через UmEnums::Parse<E>() — толерантно: неизвестная строка → E::Unknown
//    (FJsonObjectConverter при неизвестном значении UENUM ломает импорт всей структуры — R8 §2.4, JsonObjectConverter.cpp:593-616).
//  * Списки могут расти (EffectType содержит UNSUPPORTED — R3 §2.3.2), поэтому у каждого enum есть Unknown.
//  * Два разных набора для одного имени: контентные CardType/FighterType/EffectTiming (GraphQL-схема, R3 §2.3.1)
//    и engine-строки внутри JSON-состояния (R3 §2.3.2). Не смешивать (R3 §3.5).
//
// Идентификаторы — английские; wire-строки — точно как в источниках (регистр при парсинге игнорируется).

#pragma once

#include "CoreMinimal.h"
#include "Containers/StringView.h"
#include "Logging/LogMacros.h"

#include "UmEnums.generated.h"

// Категория логов модуля модели (ADR §3.6 «Логи»: LogUmModel). Объявлена здесь, т.к. UmEnums.h — базовый заголовок модуля
// (уточнение к ADR: место объявления категории в ADR не задано).
UMMODEL_API DECLARE_LOG_CATEGORY_EXTERN(LogUmModel, Log, All);

// ---------------------------------------------------------------------------------------------------------------------
// GraphQL-enum'ы (зарегистрированы в схеме; на проводе — имя члена в UPPER_SNAKE) — R3 §2.3.1
// ---------------------------------------------------------------------------------------------------------------------

/** GamePhase — R3 §2.3.1; backend/src/game-engine/models/game-state.model.ts:15-24. Основной поток:
 *  ACTION_MANEUVER ↔ COMBAT → COMBAT_RESOLVE → ACTION_MANEUVER … → GAME_OVER; SETUP/TURN_START/TURN_END — легаси, принимать без падения (R3 §4.15). */
UENUM()
enum class EUmGamePhase : uint8
{
	Setup,            // "SETUP"
	TurnStart,        // "TURN_START"
	ActionManeuver,   // "ACTION_MANEUVER"
	ActionAttack,     // "ACTION_ATTACK" (легаси-фаза idle-состояний до фикса — game-turn.guard.ts:130-134)
	Combat,           // "COMBAT"
	CombatResolve,    // "COMBAT_RESOLVE"
	TurnEnd,          // "TURN_END"
	GameOver,         // "GAME_OVER"
	Unknown
};

/** GameStatus — R3 §2.3.1; backend/src/games/dto/create-game.dto.ts:16-23. */
UENUM()
enum class EUmGameStatus : uint8
{
	Pending,      // "PENDING"
	Lobby,        // "LOBBY"
	InProgress,   // "IN_PROGRESS"
	Paused,       // "PAUSED"
	Finished,     // "FINISHED"
	Aborted,      // "ABORTED"
	Unknown
};

/** GameMode — R3 §2.3.1; create-game.dto.ts:9-14. Unknown — уточнение к ADR (единое правило толерантности). */
UENUM()
enum class EUmGameMode : uint8
{
	OneVOne,      // "ONE_V_ONE"
	TwoVTwo,      // "TWO_V_TWO"
	FreeForAll,   // "FREE_FOR_ALL"
	VsAi,         // "VS_AI"
	Unknown
};

/** GameEventType (22) — R3 §2.3.1; backend/src/games/dto/gameplay.dto.ts:24-48.
 *  Prisma GameActionType (тип события в eventsSince) — подмножество из 19 значений (R3 §2.3.2), парсится этим же enum'ом. */
UENUM()
enum class EUmGameEventType : uint8
{
	AttackInitiated,   // "ATTACK_INITIATED"
	DefensePlayed,     // "DEFENSE_PLAYED"
	CombatResolved,    // "COMBAT_RESOLVED"
	TurnChanged,       // "TURN_CHANGED" (никем не публикуется — R3 §2.12)
	PlayerJoined,      // "PLAYER_JOINED"
	PlayerLeft,        // "PLAYER_LEFT"
	GameEnded,         // "GAME_ENDED"
	FighterMoved,      // "FIGHTER_MOVED"
	DoorToggled,       // "DOOR_TOGGLED"
	Maneuver,          // "MANEUVER"
	TurnEnded,         // "TURN_ENDED"
	CardPlayed,        // "CARD_PLAYED"
	GameCreated,       // "GAME_CREATED"
	GameJoined,        // "GAME_JOINED"
	GameStarted,       // "GAME_STARTED"
	GameAborted,       // "GAME_ABORTED"
	TurnStarted,       // "TURN_STARTED"
	Passed,            // "PASSED"
	CardDiscarded,     // "CARD_DISCARDED"
	Placed,            // "PLACED"
	EffectApplied,     // "EFFECT_APPLIED"
	SpecialAbility,    // "SPECIAL_ABILITY" (setStance — R4 §2.13)
	Unknown
};

/** UserRole — R1 §2.7; backend/prisma/schema.prisma:17-21. */
UENUM()
enum class EUmUserRole : uint8
{
	User,        // "USER"
	Admin,       // "ADMIN"
	Moderator,   // "MODERATOR"
	Unknown
};

/** PresenceStatus — GraphQL-имена OFFLINE/ONLINE/INGAME/INQUEUE, внутренние строки lowercase (R2 §2.2); парсер принимает оба регистра. */
UENUM()
enum class EUmPresenceStatus : uint8
{
	Offline,   // "OFFLINE"
	Online,    // "ONLINE"
	InGame,    // "INGAME"
	InQueue,   // "INQUEUE"
	Unknown
};

/** Контентный CardType (content-API) — R3 §2.3.1; R5 §2.3: ATTACK/DEFENSE/SCHEME/VERSATILE. MANEUVER/UNIVERSAL сервер маппит в VERSATILE (content.mapper.ts:395-410). */
UENUM()
enum class EUmContentCardType : uint8
{
	Attack,      // "ATTACK"
	Defense,     // "DEFENSE"
	Scheme,      // "SCHEME"
	Versatile,   // "VERSATILE"
	Unknown
};

/** Контентный FighterType — R3 §2.3.1; hero-definition.interface.ts:61-64. НЕ равен engine Fighter.type (EUmFighterType). */
UENUM()
enum class EUmContentFighterType : uint8
{
	Hero,       // "HERO"
	Sidekick,   // "SIDEKICK"
	Unknown
};

/** Контентный EffectTiming (GraphQL) — R3 §2.3.1; R5 §2.3. Поле cards.effects.timing клиентом НЕ выбирается (риск ошибки сериализации — R5 §4.1). */
UENUM()
enum class EUmContentEffectTiming : uint8
{
	Immediately,     // "IMMEDIATELY"
	DuringCombat,    // "DURING_COMBAT"
	AfterCombat,     // "AFTER_COMBAT"
	StartOfTurn,     // "START_OF_TURN"
	EndOfTurn,       // "END_OF_TURN"
	WhenPlayed,      // "WHEN_PLAYED"
	WhenAttacked,    // "WHEN_ATTACKED"
	WhenDefending,   // "WHEN_DEFENDING"
	Unknown
};

/** AbilityTrigger — R3 §2.3.1; R5 §2.3 (у скрапнутых героев всегда PASSIVE). */
UENUM()
enum class EUmAbilityTrigger : uint8
{
	Passive,         // "PASSIVE"
	StartOfTurn,     // "START_OF_TURN"
	DuringCombat,    // "DURING_COMBAT"
	WhenAttacked,    // "WHEN_ATTACKED"
	WhenDefending,   // "WHEN_DEFENDING"
	EndOfTurn,       // "END_OF_TURN"
	Unknown
};

/** Zone (12 цветов) — R3 §2.3.1; board-definition.interface.ts:43-56. В GraphQL — UPPER, в JSON-состоянии (Cell.zone/zones) — lowercase (К1 §3.4.2). */
UENUM()
enum class EUmZone : uint8
{
	Blue,     // "BLUE" / "blue"
	Green,    // "GREEN"
	Yellow,   // "YELLOW"
	Red,      // "RED"
	Purple,   // "PURPLE"
	Brown,    // "BROWN"
	Gray,     // "GRAY"
	Orange,   // "ORANGE"
	Pink,     // "PINK"
	White,    // "WHITE"
	Gold,     // "GOLD"
	Beige,    // "BEIGE"
	Unknown
};

// ---------------------------------------------------------------------------------------------------------------------
// Строковые «enum'ы» внутри JSON-состояния (НЕ в GraphQL-схеме) — R3 §2.3.2
// ---------------------------------------------------------------------------------------------------------------------

/** Fighter.type — fighter.model.ts:10-14. Сайдкики → MINION (game-initialization.service.ts:157). */
UENUM()
enum class EUmFighterType : uint8
{
	Hero,     // "HERO"
	Minion,   // "MINION"
	Huge,     // "HUGE"
	Unknown
};

/** Fighter.attackType — fighter.model.ts:56-58,90-104: 'melee' | 'ranged'; БД хранит 'range' (R4 §2.5.3); отсутствие/мусор → melee (серверная семантика, поэтому без Unknown). */
UENUM()
enum class EUmAttackType : uint8
{
	Melee,   // "melee" (fallback)
	Ranged   // "ranged" (также принимается "range")
};

/** FighterEffect.duration — fighter.model.ts:27-33 (уточнение к ADR: enum добавлен для FUmFighterEffect). */
UENUM()
enum class EUmEffectDuration : uint8
{
	Permanent,   // "permanent"
	Turn,        // "turn"
	Round,       // "round"
	Unknown
};

/** Engine Card.cardType — card.model.ts:10-19. */
UENUM()
enum class EUmCardType : uint8
{
	Attack,      // "ATTACK"
	Defense,     // "DEFENSE"
	Scheme,      // "SCHEME"
	Universal,   // "UNIVERSAL" (legacy)
	Versatile,   // "VERSATILE"
	Maneuver,    // "MANEUVER"
	Unknown
};

/** CardEffect.type (EffectType, 21) — card.model.ts:153-189. */
UENUM()
enum class EUmEffectType : uint8
{
	ModifyAttack,      // "MODIFY_ATTACK"
	ModifyDefense,     // "MODIFY_DEFENSE"
	Damage,            // "DAMAGE"
	Heal,              // "HEAL"
	Move,              // "MOVE"
	Place,             // "PLACE"
	DrawCard,          // "DRAW_CARD"
	Discard,           // "DISCARD"
	ModifyValue,       // "MODIFY_VALUE"
	SetValue,          // "SET_VALUE"
	ValuePerCount,     // "VALUE_PER_COUNT"
	Boost,             // "BOOST"
	CancelEffects,     // "CANCEL_EFFECTS"
	OpponentDiscard,   // "OPPONENT_DISCARD"
	ReturnToHand,      // "RETURN_TO_HAND"
	Immobilize,        // "IMMOBILIZE"
	GainAction,        // "GAIN_ACTION"
	PreventDamage,     // "PREVENT_DAMAGE"
	EndTurn,           // "END_TURN"
	ChooseOne,         // "CHOOSE_ONE"
	Unsupported,       // "UNSUPPORTED"
	Unknown
};

/** CardEffect.timing (engine EffectTiming, 8) — card.model.ts:191-204. Не путать с EUmContentEffectTiming. */
UENUM()
enum class EUmEffectTiming : uint8
{
	BeforeCombat,   // "BEFORE_COMBAT"
	DuringCombat,   // "DURING_COMBAT"
	AfterCombat,    // "AFTER_COMBAT"
	OnPlay,         // "ON_PLAY"
	OnDiscard,      // "ON_DISCARD"
	TurnStart,      // "TURN_START"
	TurnEnd,        // "TURN_END"
	OnReveal,       // "ON_REVEAL"
	Unknown
};

/** CardEffect.target (EffectTarget, 10) — card.model.ts:206-226. */
UENUM()
enum class EUmEffectTarget : uint8
{
	Attacker,                 // "ATTACKER"
	Defender,                 // "DEFENDER"
	Self,                     // "SELF"
	AllEnemies,               // "ALL_ENEMIES"
	AllAllies,                // "ALL_ALLIES"
	OpposingFighter,          // "OPPOSING_FIGHTER"
	EnemiesAdjacentToSelf,    // "ENEMIES_ADJACENT_TO_SELF"
	AdjacentEnemy,            // "ADJACENT_ENEMY"
	NamedFighter,             // "NAMED_FIGHTER"
	OpponentPlayer,           // "OPPONENT_PLAYER"
	Unknown
};

/** CardEffect.when.kind (EffectConditionKind, 14) — card.model.ts:86-102. */
UENUM()
enum class EUmEffectConditionKind : uint8
{
	WonCombat,                     // "WON_COMBAT"
	LostCombat,                    // "LOST_COMBAT"
	IsAttacking,                   // "IS_ATTACKING"
	IsDefending,                   // "IS_DEFENDING"
	AdjacentToOpponent,            // "ADJACENT_TO_OPPONENT"
	NotAdjacentToOpponent,         // "NOT_ADJACENT_TO_OPPONENT"
	DeckEmpty,                     // "DECK_EMPTY"
	HandCountAtMost,               // "HAND_COUNT_AT_MOST"
	HandCountAtLeast,              // "HAND_COUNT_AT_LEAST"
	HealthAtMost,                  // "HEALTH_AT_MOST"
	MovedThisTurn,                 // "MOVED_THIS_TURN"
	OpponentIsHero,                // "OPPONENT_IS_HERO"
	SharesZoneWithOpponent,        // "SHARES_ZONE_WITH_OPPONENT"
	NotSharesZoneWithOpponent,     // "NOT_SHARES_ZONE_WITH_OPPONENT"
	Unknown
};

/** CardEffect.count.source (CountSource, 5) — card.model.ts:122-131. */
UENUM()
enum class EUmCountSource : uint8
{
	FriendlyAdjacentToOpponent,   // "FRIENDLY_ADJACENT_TO_OPPONENT"
	CardsInHand,                  // "CARDS_IN_HAND"
	DiscardNamePrefix,            // "DISCARD_NAME_PREFIX"
	DamageDealt,                  // "DAMAGE_DEALT"
	DamageTaken,                  // "DAMAGE_TAKEN"
	Unknown
};

/** CardEffect.boostSource (BoostSource) — card.model.ts:142-149. None = поле отсутствует (BOOST из руки по умолчанию — R4 §2.7.2). */
UENUM()
enum class EUmBoostSource : uint8
{
	None,                 // поле отсутствует
	PlayerChoiceHand,     // "PLAYER_CHOICE_HAND"
	SelfDeckTop,          // "SELF_DECK_TOP"
	OpponentRandomHand,   // "OPPONENT_RANDOM_HAND"
	Unknown
};

/** Cell.type — board.model.ts:24-26. */
UENUM()
enum class EUmCellType : uint8
{
	Normal,     // "normal"
	Wall,       // "wall"
	Obstacle,   // "obstacle"
	Door,       // "door"
	ZoneLine,   // "zone-line"
	Unknown
};

/** PendingEffect.type — game-state.model.ts:132-139; R4 §2.10. */
UENUM()
enum class EUmPendingEffectType : uint8
{
	Move,        // "MOVE"
	Place,       // "PLACE"
	ChooseOne,   // "CHOOSE_ONE"
	Unknown
};

// ---------------------------------------------------------------------------------------------------------------------
// Толерантные парсеры / сериализаторы (ADR §4.2: UmEnums::Parse<E>(FStringView) → E, ToWire(E) → FString)
// ---------------------------------------------------------------------------------------------------------------------

namespace UmEnums
{
	// Именованные парсеры: регистр игнорируется, пробелы по краям обрезаются; неизвестное → Unknown (для EUmAttackType → Melee).
	// bOutKnown (опционально) — false, если строка не распознана: парсер состояния кладёт такие строки в FUmParseReport (ADR §5.2).
	UMMODEL_API EUmGamePhase           ParseGamePhase(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmGameStatus          ParseGameStatus(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmGameMode            ParseGameMode(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmGameEventType       ParseGameEventType(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmUserRole            ParseUserRole(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmPresenceStatus      ParsePresenceStatus(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmContentCardType     ParseContentCardType(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmContentFighterType  ParseContentFighterType(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmContentEffectTiming ParseContentEffectTiming(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmAbilityTrigger      ParseAbilityTrigger(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmZone                ParseZone(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmFighterType         ParseFighterType(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmAttackType          ParseAttackType(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmEffectDuration      ParseEffectDuration(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmCardType            ParseCardType(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmEffectType          ParseEffectType(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmEffectTiming        ParseEffectTiming(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmEffectTarget        ParseEffectTarget(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmEffectConditionKind ParseEffectConditionKind(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmCountSource         ParseCountSource(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmBoostSource         ParseBoostSource(FStringView Wire, bool* bOutKnown = nullptr); // пустая строка → None (известное)
	UMMODEL_API EUmCellType            ParseCellType(FStringView Wire, bool* bOutKnown = nullptr);
	UMMODEL_API EUmPendingEffectType   ParsePendingEffectType(FStringView Wire, bool* bOutKnown = nullptr);

	// Обратное преобразование в wire-строку (GraphQL-имя / engine-строка). Unknown (и BoostSource::None) → пустая строка.
	UMMODEL_API FString ToWire(EUmGamePhase V);
	UMMODEL_API FString ToWire(EUmGameStatus V);
	UMMODEL_API FString ToWire(EUmGameMode V);
	UMMODEL_API FString ToWire(EUmGameEventType V);
	UMMODEL_API FString ToWire(EUmUserRole V);
	UMMODEL_API FString ToWire(EUmPresenceStatus V);
	UMMODEL_API FString ToWire(EUmContentCardType V);
	UMMODEL_API FString ToWire(EUmContentFighterType V);
	UMMODEL_API FString ToWire(EUmContentEffectTiming V);
	UMMODEL_API FString ToWire(EUmAbilityTrigger V);
	UMMODEL_API FString ToWire(EUmZone V);            // GraphQL-форма (UPPER); для JSON-состояния используйте ToWireLower
	UMMODEL_API FString ToWire(EUmFighterType V);
	UMMODEL_API FString ToWire(EUmAttackType V);
	UMMODEL_API FString ToWire(EUmEffectDuration V);
	UMMODEL_API FString ToWire(EUmCardType V);
	UMMODEL_API FString ToWire(EUmEffectType V);
	UMMODEL_API FString ToWire(EUmEffectTiming V);
	UMMODEL_API FString ToWire(EUmEffectTarget V);
	UMMODEL_API FString ToWire(EUmEffectConditionKind V);
	UMMODEL_API FString ToWire(EUmCountSource V);
	UMMODEL_API FString ToWire(EUmBoostSource V);
	UMMODEL_API FString ToWire(EUmCellType V);
	UMMODEL_API FString ToWire(EUmPendingEffectType V);

	/** Зона в форме JSON-состояния (lowercase: "blue"…), см. Cell.zone/zones — board.model.ts:29-32. */
	UMMODEL_API FString ToWireLower(EUmZone V);

	/** Обобщённый парсер (ADR §4.2: UmEnums::Parse<E>). Реализован диспетчеризацией на именованные функции. */
	template <typename E>
	E Parse(FStringView Wire, bool* bOutKnown = nullptr)
	{
		if constexpr (std::is_same_v<E, EUmGamePhase>)                { return ParseGamePhase(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmGameStatus>)          { return ParseGameStatus(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmGameMode>)            { return ParseGameMode(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmGameEventType>)       { return ParseGameEventType(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmUserRole>)            { return ParseUserRole(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmPresenceStatus>)      { return ParsePresenceStatus(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmContentCardType>)     { return ParseContentCardType(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmContentFighterType>)  { return ParseContentFighterType(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmContentEffectTiming>) { return ParseContentEffectTiming(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmAbilityTrigger>)      { return ParseAbilityTrigger(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmZone>)                { return ParseZone(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmFighterType>)         { return ParseFighterType(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmAttackType>)          { return ParseAttackType(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmEffectDuration>)      { return ParseEffectDuration(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmCardType>)            { return ParseCardType(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmEffectType>)          { return ParseEffectType(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmEffectTiming>)        { return ParseEffectTiming(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmEffectTarget>)        { return ParseEffectTarget(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmEffectConditionKind>) { return ParseEffectConditionKind(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmCountSource>)         { return ParseCountSource(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmBoostSource>)         { return ParseBoostSource(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmCellType>)            { return ParseCellType(Wire, bOutKnown); }
		else if constexpr (std::is_same_v<E, EUmPendingEffectType>)   { return ParsePendingEffectType(Wire, bOutKnown); }
		else
		{
			static_assert(sizeof(E) == 0, "UmEnums::Parse: enum type has no wire table");
		}
	}

	/** Синоним Parse<E> в терминах задания (FromWire/ToWire). */
	template <typename E>
	FORCEINLINE E FromWire(FStringView Wire, bool* bOutKnown = nullptr) { return Parse<E>(Wire, bOutKnown); }

	/** true, если строка — известное значение enum'а E (без выделения результата). */
	template <typename E>
	FORCEINLINE bool IsKnown(FStringView Wire)
	{
		bool bKnown = false;
		(void)Parse<E>(Wire, &bKnown);
		return bKnown;
	}
}

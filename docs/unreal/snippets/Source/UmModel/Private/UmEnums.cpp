// UmModel/Private/UmEnums.cpp
// Таблицы wire-строк и толерантные парсеры (ADR §4.2; R3 §2.3.1-2.3.2).

#include "UmEnums.h"

DEFINE_LOG_CATEGORY(LogUmModel);

namespace
{
	template <typename E>
	struct FUmWirePair
	{
		E Value;
		const TCHAR* Wire;
	};

	/** Линейный поиск по таблице: регистр игнорируется, пробелы по краям обрезаются. */
	template <typename E, SIZE_T N>
	E ParseFromTable(const FUmWirePair<E> (&Table)[N], FStringView Wire, E Fallback, bool* bOutKnown)
	{
		const FStringView Trimmed = Wire.TrimStartAndEnd();
		for (const FUmWirePair<E>& Pair : Table)
		{
			if (Trimmed.Equals(Pair.Wire, ESearchCase::IgnoreCase))
			{
				if (bOutKnown) { *bOutKnown = true; }
				return Pair.Value;
			}
		}
		if (bOutKnown) { *bOutKnown = false; }
		return Fallback;
	}

	/** Первая wire-строка для значения (первая запись в таблице — каноническая). */
	template <typename E, SIZE_T N>
	FString ToWireFromTable(const FUmWirePair<E> (&Table)[N], E Value)
	{
		for (const FUmWirePair<E>& Pair : Table)
		{
			if (Pair.Value == Value)
			{
				return FString(Pair.Wire);
			}
		}
		return FString();
	}
}

// Макрос: таблица + Parse + ToWire для одного enum'а. Первая запись каждого значения — каноническая (используется ToWire).
#define UM_DEFINE_ENUM_WIRE(EnumType, ParseName, FallbackValue, ...)                                      \
	static const FUmWirePair<EnumType> G##EnumType##Wire[] = { __VA_ARGS__ };                             \
	EnumType UmEnums::ParseName(FStringView Wire, bool* bOutKnown)                                       \
	{                                                                                                     \
		return ParseFromTable(G##EnumType##Wire, Wire, EnumType::FallbackValue, bOutKnown);               \
	}                                                                                                     \
	FString UmEnums::ToWire(EnumType Value)                                                               \
	{                                                                                                     \
		return ToWireFromTable(G##EnumType##Wire, Value);                                                 \
	}

// ---- GraphQL-enum'ы (R3 §2.3.1) --------------------------------------------------------------------------------------

UM_DEFINE_ENUM_WIRE(EUmGamePhase, ParseGamePhase, Unknown,
	{ EUmGamePhase::Setup,          TEXT("SETUP") },
	{ EUmGamePhase::TurnStart,      TEXT("TURN_START") },
	{ EUmGamePhase::ActionManeuver, TEXT("ACTION_MANEUVER") },
	{ EUmGamePhase::ActionAttack,   TEXT("ACTION_ATTACK") },
	{ EUmGamePhase::Combat,         TEXT("COMBAT") },
	{ EUmGamePhase::CombatResolve,  TEXT("COMBAT_RESOLVE") },
	{ EUmGamePhase::TurnEnd,        TEXT("TURN_END") },
	{ EUmGamePhase::GameOver,       TEXT("GAME_OVER") })

UM_DEFINE_ENUM_WIRE(EUmGameStatus, ParseGameStatus, Unknown,
	{ EUmGameStatus::Pending,    TEXT("PENDING") },
	{ EUmGameStatus::Lobby,      TEXT("LOBBY") },
	{ EUmGameStatus::InProgress, TEXT("IN_PROGRESS") },
	{ EUmGameStatus::Paused,     TEXT("PAUSED") },
	{ EUmGameStatus::Finished,   TEXT("FINISHED") },
	{ EUmGameStatus::Aborted,    TEXT("ABORTED") })

UM_DEFINE_ENUM_WIRE(EUmGameMode, ParseGameMode, Unknown,
	{ EUmGameMode::OneVOne,    TEXT("ONE_V_ONE") },
	{ EUmGameMode::TwoVTwo,    TEXT("TWO_V_TWO") },
	{ EUmGameMode::FreeForAll, TEXT("FREE_FOR_ALL") },
	{ EUmGameMode::VsAi,       TEXT("VS_AI") })

UM_DEFINE_ENUM_WIRE(EUmGameEventType, ParseGameEventType, Unknown,
	{ EUmGameEventType::AttackInitiated, TEXT("ATTACK_INITIATED") },
	{ EUmGameEventType::DefensePlayed,   TEXT("DEFENSE_PLAYED") },
	{ EUmGameEventType::CombatResolved,  TEXT("COMBAT_RESOLVED") },
	{ EUmGameEventType::TurnChanged,     TEXT("TURN_CHANGED") },
	{ EUmGameEventType::PlayerJoined,    TEXT("PLAYER_JOINED") },
	{ EUmGameEventType::PlayerLeft,      TEXT("PLAYER_LEFT") },
	{ EUmGameEventType::GameEnded,       TEXT("GAME_ENDED") },
	{ EUmGameEventType::FighterMoved,    TEXT("FIGHTER_MOVED") },
	{ EUmGameEventType::DoorToggled,     TEXT("DOOR_TOGGLED") },
	{ EUmGameEventType::Maneuver,        TEXT("MANEUVER") },
	{ EUmGameEventType::TurnEnded,       TEXT("TURN_ENDED") },
	{ EUmGameEventType::CardPlayed,      TEXT("CARD_PLAYED") },
	{ EUmGameEventType::GameCreated,     TEXT("GAME_CREATED") },
	{ EUmGameEventType::GameJoined,      TEXT("GAME_JOINED") },
	{ EUmGameEventType::GameStarted,     TEXT("GAME_STARTED") },
	{ EUmGameEventType::GameAborted,     TEXT("GAME_ABORTED") },
	{ EUmGameEventType::TurnStarted,     TEXT("TURN_STARTED") },
	{ EUmGameEventType::Passed,          TEXT("PASSED") },
	{ EUmGameEventType::CardDiscarded,   TEXT("CARD_DISCARDED") },
	{ EUmGameEventType::Placed,          TEXT("PLACED") },
	{ EUmGameEventType::EffectApplied,   TEXT("EFFECT_APPLIED") },
	{ EUmGameEventType::SpecialAbility,  TEXT("SPECIAL_ABILITY") })

UM_DEFINE_ENUM_WIRE(EUmUserRole, ParseUserRole, Unknown,
	{ EUmUserRole::User,      TEXT("USER") },
	{ EUmUserRole::Admin,     TEXT("ADMIN") },
	{ EUmUserRole::Moderator, TEXT("MODERATOR") })

// GraphQL-имена UPPER; внутренние строки lowercase совпадают с точностью до регистра (R2 §2.2) — одна таблица.
UM_DEFINE_ENUM_WIRE(EUmPresenceStatus, ParsePresenceStatus, Unknown,
	{ EUmPresenceStatus::Offline, TEXT("OFFLINE") },
	{ EUmPresenceStatus::Online,  TEXT("ONLINE") },
	{ EUmPresenceStatus::InGame,  TEXT("INGAME") },
	{ EUmPresenceStatus::InQueue, TEXT("INQUEUE") })

UM_DEFINE_ENUM_WIRE(EUmContentCardType, ParseContentCardType, Unknown,
	{ EUmContentCardType::Attack,    TEXT("ATTACK") },
	{ EUmContentCardType::Defense,   TEXT("DEFENSE") },
	{ EUmContentCardType::Scheme,    TEXT("SCHEME") },
	{ EUmContentCardType::Versatile, TEXT("VERSATILE") })

UM_DEFINE_ENUM_WIRE(EUmContentFighterType, ParseContentFighterType, Unknown,
	{ EUmContentFighterType::Hero,     TEXT("HERO") },
	{ EUmContentFighterType::Sidekick, TEXT("SIDEKICK") })

UM_DEFINE_ENUM_WIRE(EUmContentEffectTiming, ParseContentEffectTiming, Unknown,
	{ EUmContentEffectTiming::Immediately,   TEXT("IMMEDIATELY") },
	{ EUmContentEffectTiming::DuringCombat,  TEXT("DURING_COMBAT") },
	{ EUmContentEffectTiming::AfterCombat,   TEXT("AFTER_COMBAT") },
	{ EUmContentEffectTiming::StartOfTurn,   TEXT("START_OF_TURN") },
	{ EUmContentEffectTiming::EndOfTurn,     TEXT("END_OF_TURN") },
	{ EUmContentEffectTiming::WhenPlayed,    TEXT("WHEN_PLAYED") },
	{ EUmContentEffectTiming::WhenAttacked,  TEXT("WHEN_ATTACKED") },
	{ EUmContentEffectTiming::WhenDefending, TEXT("WHEN_DEFENDING") })

UM_DEFINE_ENUM_WIRE(EUmAbilityTrigger, ParseAbilityTrigger, Unknown,
	{ EUmAbilityTrigger::Passive,       TEXT("PASSIVE") },
	{ EUmAbilityTrigger::StartOfTurn,   TEXT("START_OF_TURN") },
	{ EUmAbilityTrigger::DuringCombat,  TEXT("DURING_COMBAT") },
	{ EUmAbilityTrigger::WhenAttacked,  TEXT("WHEN_ATTACKED") },
	{ EUmAbilityTrigger::WhenDefending, TEXT("WHEN_DEFENDING") },
	{ EUmAbilityTrigger::EndOfTurn,     TEXT("END_OF_TURN") })

// Zone: GraphQL "BLUE" и JSON-состояние "blue" различаются только регистром — парсер общий.
UM_DEFINE_ENUM_WIRE(EUmZone, ParseZone, Unknown,
	{ EUmZone::Blue,   TEXT("BLUE") },
	{ EUmZone::Green,  TEXT("GREEN") },
	{ EUmZone::Yellow, TEXT("YELLOW") },
	{ EUmZone::Red,    TEXT("RED") },
	{ EUmZone::Purple, TEXT("PURPLE") },
	{ EUmZone::Brown,  TEXT("BROWN") },
	{ EUmZone::Gray,   TEXT("GRAY") },
	{ EUmZone::Orange, TEXT("ORANGE") },
	{ EUmZone::Pink,   TEXT("PINK") },
	{ EUmZone::White,  TEXT("WHITE") },
	{ EUmZone::Gold,   TEXT("GOLD") },
	{ EUmZone::Beige,  TEXT("BEIGE") })

FString UmEnums::ToWireLower(EUmZone Value)
{
	return ToWire(Value).ToLower();
}

// ---- Engine-строки JSON-состояния (R3 §2.3.2) ------------------------------------------------------------------------

UM_DEFINE_ENUM_WIRE(EUmFighterType, ParseFighterType, Unknown,
	{ EUmFighterType::Hero,   TEXT("HERO") },
	{ EUmFighterType::Minion, TEXT("MINION") },
	{ EUmFighterType::Huge,   TEXT("HUGE") })

// 'range' — форма из БД (R4 §2.5.3, fighter.model.ts:96-105 normalizeAttackType); мусор → melee (серверная семантика).
UM_DEFINE_ENUM_WIRE(EUmAttackType, ParseAttackType, Melee,
	{ EUmAttackType::Melee,  TEXT("melee") },
	{ EUmAttackType::Ranged, TEXT("ranged") },
	{ EUmAttackType::Ranged, TEXT("range") })

UM_DEFINE_ENUM_WIRE(EUmEffectDuration, ParseEffectDuration, Unknown,
	{ EUmEffectDuration::Permanent, TEXT("permanent") },
	{ EUmEffectDuration::Turn,      TEXT("turn") },
	{ EUmEffectDuration::Round,     TEXT("round") })

UM_DEFINE_ENUM_WIRE(EUmCardType, ParseCardType, Unknown,
	{ EUmCardType::Attack,    TEXT("ATTACK") },
	{ EUmCardType::Defense,   TEXT("DEFENSE") },
	{ EUmCardType::Scheme,    TEXT("SCHEME") },
	{ EUmCardType::Universal, TEXT("UNIVERSAL") },
	{ EUmCardType::Versatile, TEXT("VERSATILE") },
	{ EUmCardType::Maneuver,  TEXT("MANEUVER") })

UM_DEFINE_ENUM_WIRE(EUmEffectType, ParseEffectType, Unknown,
	{ EUmEffectType::ModifyAttack,    TEXT("MODIFY_ATTACK") },
	{ EUmEffectType::ModifyDefense,   TEXT("MODIFY_DEFENSE") },
	{ EUmEffectType::Damage,          TEXT("DAMAGE") },
	{ EUmEffectType::Heal,            TEXT("HEAL") },
	{ EUmEffectType::Move,            TEXT("MOVE") },
	{ EUmEffectType::Place,           TEXT("PLACE") },
	{ EUmEffectType::DrawCard,        TEXT("DRAW_CARD") },
	{ EUmEffectType::Discard,         TEXT("DISCARD") },
	{ EUmEffectType::ModifyValue,     TEXT("MODIFY_VALUE") },
	{ EUmEffectType::SetValue,        TEXT("SET_VALUE") },
	{ EUmEffectType::ValuePerCount,   TEXT("VALUE_PER_COUNT") },
	{ EUmEffectType::Boost,           TEXT("BOOST") },
	{ EUmEffectType::CancelEffects,   TEXT("CANCEL_EFFECTS") },
	{ EUmEffectType::OpponentDiscard, TEXT("OPPONENT_DISCARD") },
	{ EUmEffectType::ReturnToHand,    TEXT("RETURN_TO_HAND") },
	{ EUmEffectType::Immobilize,      TEXT("IMMOBILIZE") },
	{ EUmEffectType::GainAction,      TEXT("GAIN_ACTION") },
	{ EUmEffectType::PreventDamage,   TEXT("PREVENT_DAMAGE") },
	{ EUmEffectType::EndTurn,         TEXT("END_TURN") },
	{ EUmEffectType::ChooseOne,       TEXT("CHOOSE_ONE") },
	{ EUmEffectType::Unsupported,     TEXT("UNSUPPORTED") })

UM_DEFINE_ENUM_WIRE(EUmEffectTiming, ParseEffectTiming, Unknown,
	{ EUmEffectTiming::BeforeCombat, TEXT("BEFORE_COMBAT") },
	{ EUmEffectTiming::DuringCombat, TEXT("DURING_COMBAT") },
	{ EUmEffectTiming::AfterCombat,  TEXT("AFTER_COMBAT") },
	{ EUmEffectTiming::OnPlay,       TEXT("ON_PLAY") },
	{ EUmEffectTiming::OnDiscard,    TEXT("ON_DISCARD") },
	{ EUmEffectTiming::TurnStart,    TEXT("TURN_START") },
	{ EUmEffectTiming::TurnEnd,      TEXT("TURN_END") },
	{ EUmEffectTiming::OnReveal,     TEXT("ON_REVEAL") })

UM_DEFINE_ENUM_WIRE(EUmEffectTarget, ParseEffectTarget, Unknown,
	{ EUmEffectTarget::Attacker,              TEXT("ATTACKER") },
	{ EUmEffectTarget::Defender,              TEXT("DEFENDER") },
	{ EUmEffectTarget::Self,                  TEXT("SELF") },
	{ EUmEffectTarget::AllEnemies,            TEXT("ALL_ENEMIES") },
	{ EUmEffectTarget::AllAllies,             TEXT("ALL_ALLIES") },
	{ EUmEffectTarget::OpposingFighter,       TEXT("OPPOSING_FIGHTER") },
	{ EUmEffectTarget::EnemiesAdjacentToSelf, TEXT("ENEMIES_ADJACENT_TO_SELF") },
	{ EUmEffectTarget::AdjacentEnemy,         TEXT("ADJACENT_ENEMY") },
	{ EUmEffectTarget::NamedFighter,          TEXT("NAMED_FIGHTER") },
	{ EUmEffectTarget::OpponentPlayer,        TEXT("OPPONENT_PLAYER") })

UM_DEFINE_ENUM_WIRE(EUmEffectConditionKind, ParseEffectConditionKind, Unknown,
	{ EUmEffectConditionKind::WonCombat,                 TEXT("WON_COMBAT") },
	{ EUmEffectConditionKind::LostCombat,                TEXT("LOST_COMBAT") },
	{ EUmEffectConditionKind::IsAttacking,               TEXT("IS_ATTACKING") },
	{ EUmEffectConditionKind::IsDefending,               TEXT("IS_DEFENDING") },
	{ EUmEffectConditionKind::AdjacentToOpponent,        TEXT("ADJACENT_TO_OPPONENT") },
	{ EUmEffectConditionKind::NotAdjacentToOpponent,     TEXT("NOT_ADJACENT_TO_OPPONENT") },
	{ EUmEffectConditionKind::DeckEmpty,                 TEXT("DECK_EMPTY") },
	{ EUmEffectConditionKind::HandCountAtMost,           TEXT("HAND_COUNT_AT_MOST") },
	{ EUmEffectConditionKind::HandCountAtLeast,          TEXT("HAND_COUNT_AT_LEAST") },
	{ EUmEffectConditionKind::HealthAtMost,              TEXT("HEALTH_AT_MOST") },
	{ EUmEffectConditionKind::MovedThisTurn,             TEXT("MOVED_THIS_TURN") },
	{ EUmEffectConditionKind::OpponentIsHero,            TEXT("OPPONENT_IS_HERO") },
	{ EUmEffectConditionKind::SharesZoneWithOpponent,    TEXT("SHARES_ZONE_WITH_OPPONENT") },
	{ EUmEffectConditionKind::NotSharesZoneWithOpponent, TEXT("NOT_SHARES_ZONE_WITH_OPPONENT") })

UM_DEFINE_ENUM_WIRE(EUmCountSource, ParseCountSource, Unknown,
	{ EUmCountSource::FriendlyAdjacentToOpponent, TEXT("FRIENDLY_ADJACENT_TO_OPPONENT") },
	{ EUmCountSource::CardsInHand,                TEXT("CARDS_IN_HAND") },
	{ EUmCountSource::DiscardNamePrefix,          TEXT("DISCARD_NAME_PREFIX") },
	{ EUmCountSource::DamageDealt,                TEXT("DAMAGE_DEALT") },
	{ EUmCountSource::DamageTaken,                TEXT("DAMAGE_TAKEN") })

// Пустая строка = поле отсутствует → None (известное значение, а не ошибка).
UM_DEFINE_ENUM_WIRE(EUmBoostSource, ParseBoostSource, Unknown,
	{ EUmBoostSource::None,               TEXT("") },
	{ EUmBoostSource::PlayerChoiceHand,   TEXT("PLAYER_CHOICE_HAND") },
	{ EUmBoostSource::SelfDeckTop,        TEXT("SELF_DECK_TOP") },
	{ EUmBoostSource::OpponentRandomHand, TEXT("OPPONENT_RANDOM_HAND") })

UM_DEFINE_ENUM_WIRE(EUmCellType, ParseCellType, Unknown,
	{ EUmCellType::Normal,   TEXT("normal") },
	{ EUmCellType::Wall,     TEXT("wall") },
	{ EUmCellType::Obstacle, TEXT("obstacle") },
	{ EUmCellType::Door,     TEXT("door") },
	{ EUmCellType::ZoneLine, TEXT("zone-line") })

UM_DEFINE_ENUM_WIRE(EUmPendingEffectType, ParsePendingEffectType, Unknown,
	{ EUmPendingEffectType::Move,      TEXT("MOVE") },
	{ EUmPendingEffectType::Place,     TEXT("PLACE") },
	{ EUmPendingEffectType::ChooseOne, TEXT("CHOOSE_ONE") })

#undef UM_DEFINE_ENUM_WIRE

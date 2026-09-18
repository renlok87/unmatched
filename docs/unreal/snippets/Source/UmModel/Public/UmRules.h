// UmModel/Public/UmRules.h
// Правила-подсказки — клиентское зеркало точечных функций бэкенда (ADR §4.3 FUmRules, §5.7 таблица паритета).
// Источники: game-rules.validator.ts:559-604 (bannerAllows), game-action-executor.service.ts:136-154 (boostAllowed),
// :1008-1058 (досягаемость атаки), :432-520 (pending), generic-hero-ability.handler.ts:100-111, 635-645
// (стойка/дальность), ms-marvel.handler.ts:22,75, arthur.handler.ts:22-30, ability-config.ts:365-413.
//
// Принцип: «строже сервера — можно, мягче — нельзя» (candidate-2 §3.5.1 п.4), а там, где сервер
// принимает решение по данным, которых у клиента нет (строка DT_AttackRange отсутствует), — НЕ блокировать
// (ADR §5.7 «Дальность attackRange»).

#pragma once

#include "CoreMinimal.h"
#include "Math/IntPoint.h"
#include "UmGameState.h"
#include "UmTableRows.h"  // FUmAttackRangeRow { HeroSlug, StanceId, Range } — ADR §4.3
#include "UmApiDtos.h"    // FUmStanceOptionDto { Id, Label, bIsDefault } — ADR §4.2 (heroStances)
#include "UmRules.generated.h"

/** Роль карты при проверке BOOST — соответствует `role: 'attack' | 'defense'` (executor:136-154). */
UENUM(BlueprintType)
enum class EUmBoostRole : uint8
{
	Attack,
	Defense
};

/** Обёртка списка стоек для TMap<FString, …> внутри USTRUCT (UHT не допускает TMap<K, TArray<V>>). */
USTRUCT(BlueprintType)
struct UMMODEL_API FUmStanceOptionDtoList
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Um|Rules")
	TArray<FUmStanceOptionDto> Items;
};

/**
 * Таблица способностей, нужная зеркалу (уточнение к ADR: ADR §4.3 передаёт в FUmLegalActions только
 * `ranges`; стойки и boost-герои нужны там же, поэтому объединены в одну структуру, заполняемую
 * UUmContentSubsystem из DT_AttackRange (export-ability-table.ts — ADR §3.7) и кэша `heroStances`).
 */
USTRUCT(BlueprintType)
struct UMMODEL_API FUmAbilityTable
{
	GENERATED_BODY()

	/** Строки DT_AttackRange: bullseye 5, t-rex 2, ms-marvel 2, muhammad-ali/float 2 (ADR §4.3; R4 §2.7.1 п.4). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Rules")
	TArray<FUmAttackRangeRow> Ranges;

	/** heroSlug → стойки из `query heroStances(heroSlug)`; для не-стоечных героев пусто (R4 §2.13). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Rules")
	TMap<FString, FUmStanceOptionDtoList> Stances;

	/** Герои с `allowsAttackBoost` — сейчас только `king-arthur` (arthur.handler.ts:22-30). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Rules")
	TSet<FString> AttackBoostHeroSlugs;

	/** Герои с `allowsDefenseBoost` — в реестре не найдено (R4 §2.7.2); пусто. */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Rules")
	TSet<FString> DefenseBoostHeroSlugs;

	FUmAbilityTable();

	/** Стойка по умолчанию: `default: true` или первая; пусто для не-стоечных (generic-hero-ability.handler.ts:100-103). */
	FString DefaultStanceId(const FString& HeroSlug) const;

	/**
	 * Текущая стойка владельца: `metadata.heroStances[ownerId]` с фолбэком на дефолтную
	 * (generic-hero-ability.handler.ts:107-111). Пусто, если герой не стоечный.
	 */
	FString CurrentStanceId(const FUmGameState& State, const FString& OwnerUserId, const FString& HeroSlug) const;

	/**
	 * Эффективная дальность: `stance.attackRange ?? config.attackRange`
	 * (generic-hero-ability.handler.ts:641-644). Возвращает false, если строки нет (у героя нет
	 * расширенной дальности ИЛИ таблица не заполнена — различить нельзя, см. ADR §5.7).
	 */
	bool FindEffectiveRange(const FString& HeroSlug, const FString& StanceId, int32& OutRange) const;
};

/** Результат проверки досягаемости — для тоста/подсказки WhyNot. */
UENUM(BlueprintType)
enum class EUmRangeVerdict : uint8
{
	/** Смежная цель (любой тип атаки). */
	Adjacent,
	/** Ranged и совпадает legacy `cell.zone` (adjacency.service.ts:214-218). */
	SameZone,
	/** Манхэттен ≤ effectiveRange героя/стойки (DT_AttackRange). */
	AbilityRange,
	/** Не достаёт по известным клиенту правилам. */
	OutOfRange
};

/**
 * Чистые правила-подсказки. Все функции статические; UObject не используются.
 * Spec: `Unmatched.Model.Banner`, `Unmatched.Model.RulesParity` (ADR §4.8).
 */
struct UMMODEL_API FUmRules
{
	// ---------------------------------------------------------------- фазы и экономика

	/** `phase ∈ {ACTION_MANEUVER, ACTION_ATTACK}` — единственные action-фазы (R4 §2.2; validator.ts:309-315). */
	static bool IsActionPhase(const FString& Phase);

	/** `phase ∈ {COMBAT, COMBAT_RESOLVE}` — фазы, в которых валиден `resolveCombat` (game-turn.guard.ts:225-283). */
	static bool IsCombatPhase(const FString& Phase);

	/** `actionsRemaining`: отсутствие/мусор → 2 (game-state.model.ts:172-175; парсер уже подставил 2, здесь — клэмп ≥ 0). */
	static int32 ActionsRemaining(const FUmGameState& State);

	/** `canPlayerAct`: `currentTurnPlayerId == userId` и игрок жив (game-rules.validator.ts:219-227). */
	static bool CanPlayerAct(const FUmGameState& State, const FString& UserId);

	/** Эффект `immobilized` (любой duration) блокирует манёвр/moveFighter (validator.ts:300-305, 395-400). */
	static bool IsImmobilized(const FUmFighter& Fighter);

	/** Живой: `health > 0 && !isDefeated` (candidate-1 §3.4.4 `IsAlive`). */
	static bool IsAlive(const FUmFighter& Fighter);

	// ---------------------------------------------------------------- типы карт

	/** `ATTACK | VERSATILE | UNIVERSAL` (validator.ts `INVALID_CARD_TYPE`, R4 §2.7.1). */
	static bool IsAttackCard(const FUmCard& Card);

	/** `DEFENSE | VERSATILE | UNIVERSAL` (validator.ts:440-466). */
	static bool IsDefenseCard(const FUmCard& Card);

	/** Только `SCHEME` (VERSATILE не принимается — executor:1296-1305). */
	static bool IsSchemeCard(const FUmCard& Card);

	// ---------------------------------------------------------------- banner (validator.ts:559-604)

	/** `sing()`: `ies$→y`, `ves$→f`, `([^s])s$→$1` — последовательно, как три `.replace` сервера. */
	static FString Singularize(const FString& Word);

	/**
	 * `bannerAllows(banner, fighter)`: регистронезависимо; «Harpy» = «Harpy 2» (срез `\s+\d+$`),
	 * «Arthur» = слово в «King Arthur», «Harpies» = «Harpy». Пустой банер/`Any` здесь НЕ обрабатывается —
	 * см. BannerPermits.
	 */
	static bool BannerAllows(const FString& Banner, const FString& FighterName);

	/**
	 * `validateBanner`: пусто/`any` → ok; матч → ok; банер не матчит НИ ОДНОГО бойца партии → ok (warn,
	 * «грязные данные»); иначе `BANNER_MISMATCH`. Мягкий гейт по ADR §5.7 — предупреждение, не блок.
	 * @param bOutUnknownBanner  true, если разрешено только потому, что банер никому не известен.
	 */
	static bool BannerPermits(const FUmGameState& State, const FString& Banner, const FUmFighter& Fighter, bool* bOutUnknownBanner = nullptr);

	// ---------------------------------------------------------------- BOOST (executor:136-154, 1066-1084)

	/**
	 * `boostAllowed(playedCard, fighter, role)`: карта имеет эффект `BOOST` с `boostSource ∈ {PLAYER_CHOICE_HAND, null}`
	 * (FUmCardEffect::IsBoostFromHand) ИЛИ герой (`heroSlug ?? heroId`) в списке `allowsAttackBoost/allowsDefenseBoost`.
	 */
	static bool BoostAllowed(const FUmCard& PlayedCard, const FUmFighter& Fighter, EUmBoostRole Role, const FUmAbilityTable& Abilities);

	/** Нельзя бустить той же картой (`boostCard.id === playedCard.id` — executor:1076-1080, 1210-1214). */
	static bool CanBoostWith(const FUmCard& PlayedCard, const FUmCard& BoostCard);

	// ---------------------------------------------------------------- досягаемость (executor:1008-1058)

	/**
	 * Порядок сервера: adjacent → (`ranged` && SameLegacyZone) → `canAttackAtRange(slug, manhattan, heroStances[owner])`.
	 * Хук дальности только добавляет разрешение. При отсутствии строки в таблице — OutOfRange, но вызывающий код
	 * (FUmLegalActions) не должен блокировать клик по такой цели (ADR §5.7).
	 */
	static EUmRangeVerdict AttackRangeVerdict(const FUmGameState& State, const FUmFighter& Attacker, const FUmFighter& Target, const FUmAbilityTable& Abilities);

	/** Удобная обёртка: `AttackRangeVerdict != OutOfRange`. */
	static bool IsInAttackRange(const FUmGameState& State, const FUmFighter& Attacker, const FUmFighter& Target, const FUmAbilityTable& Abilities);

	// ---------------------------------------------------------------- pending (executor:432-520)

	/**
	 * Боец подходит под MOVE/PLACE-pending: жив; владелец — свой, либо чужой при `targetsOpponent`
	 * (`pending.targetsOpponent ? owner === me → отказ : owner !== me → отказ`); `fighterName` через BannerAllows.
	 */
	static bool FighterFitsPending(const FUmPendingEffect& Pending, const FUmFighter& Fighter, const FString& MyUserId);

	/**
	 * Целевая клетка MOVE/PLACE: в границах, не `obstacle/wall`, не занята живым (executor:454-470).
	 * Для MOVE дополнительно BFS-достижимость за `value ?? 1` шагов с блокировкой чужими живыми — см.
	 * FUmLegalActions::PendingTargets.
	 */
	static bool IsPendingCellFree(const FUmGameState& State, const FIntPoint& P, const FString& MovingFighterId);

	/** Дистанция MOVE-pending: `pending.value ?? 1` (R4 §2.10). Парсер хранит 1 при отсутствии; клэмп ≥ 1. */
	static int32 PendingMoveDistance(const FUmPendingEffect& Pending);
};

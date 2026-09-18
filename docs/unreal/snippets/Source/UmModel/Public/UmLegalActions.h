// UmModel/Public/UmLegalActions.h
// Единственная точка вычисления аффордансов (ADR §4.3 FUmLegalActions; §5.6 — теги Action.*; §5.7 — паритет).
// Реализует таблицу R4 §2.18 «механика → когда доступно → что подсветить» и guard'ы бэкенда
// (game-turn.guard.ts:163-283, game-rules.validator.ts:135-550, game-action-executor.service.ts:432-520, 1296-1322, 1898-1934).
//
// Потребители: UUmGameHudModel.LegalSet/WhyNot (ADR §4.6), FUmInputStateMachine (ADR §4.7),
// UUmHudLibrary::GetWhyNot. Spec: `Unmatched.Model.LegalActions`, `Unmatched.Model.RulesParity` (ADR §4.8).

#pragma once

#include "CoreMinimal.h"
#include "Math/IntPoint.h"
#include "GameplayTagContainer.h"
#include "UmGameState.h"
#include "UmRules.h"
#include "UmLegalActions.generated.h"

/** Причина отказа для одной кнопки/жеста — источник `WhyNot` в UUmHudLibrary (ADR §4.6, G16). */
USTRUCT(BlueprintType)
struct UMMODEL_API FUmRejection
{
	GENERATED_BODY()

	/** Тег действия `Action.*` (ADR §5.6). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	FGameplayTag Action;

	/**
	 * Машинный код причины (уточнение к ADR: ADR §4.3 задаёт `{Action, Reason}`; код добавлен для тестов
	 * паритета и локализации). Значения — см. namespace UmReason.
	 */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	FName ReasonTag;

	/** Локализованный текст для подсказки (ST_UI). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	FText Reason;
};

/** Коды причин отказа (FUmRejection::ReasonTag). Соответствуют кодам/сообщениям сервера, где они есть. */
namespace UmReason
{
	inline const FName GameOver(TEXT("GameOver"));                       // phase == GAME_OVER
	inline const FName NotYourTurn(TEXT("NotYourTurn"));                 // NOT_YOUR_TURN (validator.ts:219-221)
	inline const FName PlayerNotAlive(TEXT("PlayerNotAlive"));           // PLAYER_NOT_IN_GAME (validator.ts:223-226)
	inline const FName InvalidPhase(TEXT("InvalidPhase"));               // INVALID_PHASE
	inline const FName NoActionsLeft(TEXT("NoActionsLeft"));             // actionsRemaining == 0 (R4 §2.3)
	inline const FName Immobilized(TEXT("Immobilized"));                 // FIGHTER_IMMOBILIZED
	inline const FName NoLivingFighters(TEXT("NoLivingFighters"));
	inline const FName NoReachableCells(TEXT("NoReachableCells"));
	inline const FName NoAttackCards(TEXT("NoAttackCards"));             // INVALID_CARD_TYPE / рука без ATTACK|VERSATILE
	inline const FName NoTargetsInRange(TEXT("NoTargetsInRange"));       // 'Melee/Ranged attack: target must be …'
	inline const FName NoSchemeCards(TEXT("NoSchemeCards"));
	inline const FName NotInCombat(TEXT("NotInCombat"));                 // 'No combat in progress' / 'Not in combat phase'
	inline const FName NotDefender(TEXT("NotDefender"));                 // 'Only defender can play defense'
	inline const FName NoDefenseCards(TEXT("NoDefenseCards"));
	inline const FName NotParticipant(TEXT("NotParticipant"));           // 'Only combat participants can resolve combat'
	inline const FName AwaitingDefense(TEXT("AwaitingDefense"));         // клиентская строгость: атакующий в COMBAT (ADR §5.7)
	inline const FName PendingBlockedByCombat(TEXT("PendingBlockedByCombat")); // G19 (ADR §5.5)
	inline const FName NoPending(TEXT("NoPending"));
	inline const FName NoStances(TEXT("NoStances"));                     // 'У этого героя нет стоек'
	inline const FName NoHero(TEXT("NoHero"));                           // 'У игрока нет героя на доске'
	inline const FName ExternalGateClosed(TEXT("ExternalGateClosed"));   // Input.Mode.Busy / Match.Sync != Live
}

/** Достижимые клетки одного бойца (moveFighter/manёвр/pending MOVE). */
USTRUCT(BlueprintType)
struct UMMODEL_API FUmFighterMoveTargets
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	FString FighterId;

	/** Клетка → число шагов (BFS, старт исключён). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	TMap<FIntPoint, int32> Cells;
};

/** Вариант атаки: боец × карта × цель (ADR §4.3 `Attacks[{attackerId, cardId, targetId, bBoostAllowed}]`). */
USTRUCT(BlueprintType)
struct UMMODEL_API FUmAttackOption
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	FString AttackerId;

	/** Instance id карты (`<cardId>::n`) — именно его слать в `cardId` (R3 §2.9.4). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	FString CardId;

	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	FString TargetId;

	/** Как цель достигается — для подсветки (AbilityRange рисуется иначе, чем Adjacent). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	EUmRangeVerdict Range = EUmRangeVerdict::OutOfRange;

	/** Показывать слот BOOST (FUmRules::BoostAllowed). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	bool bBoostAllowed = false;

	/** Банер карты не матчит бойца, но разрешён как «неизвестный» (мягкий гейт — предупреждение). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	bool bBannerWarning = false;
};

/** Карта защиты с признаком BOOST-слота. */
USTRUCT(BlueprintType)
struct UMMODEL_API FUmDefenseOption
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	FString CardId;

	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	bool bBoostAllowed = false;

	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	bool bBannerWarning = false;
};

/** Один мой pending с уже вычисленными допустимыми вариантами. */
USTRUCT(BlueprintType)
struct UMMODEL_API FUmPendingChoice
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	FUmPendingEffect Pending;

	/** MOVE/PLACE: бойцы, подходящие под FighterFitsPending. */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	TArray<FString> EligibleFighterIds;

	/** MOVE: BFS-достижимые клетки для каждого eligible-бойца за `value ?? 1`; PLACE: все свободные проходимые. */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	TArray<FUmFighterMoveTargets> Targets;

	/** CHOOSE_ONE: допустимые индексы `options[].index`. */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	TArray<int32> OptionIndices;
};

/**
 * Полный набор допустимых действий для локального игрока в данном снапшоте.
 * Имена полей — ADR §4.3; булевы сводки добавлены как удобство для FGameplayTagQuery-гейтов (уточнение к ADR).
 */
USTRUCT(BlueprintType)
struct UMMODEL_API FUmLegalSet
{
	GENERATED_BODY()

	// ---- сводки
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal") bool bCanManeuver = false;
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal") bool bCanMoveFighter = false;
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal") bool bCanAttack = false;
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal") bool bCanScheme = false;
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal") bool bCanDefend = false;
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal") bool bCanResolveCombat = false;
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal") bool bCanEndTurn = false;
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal") bool bCanPass = false;
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal") bool bCanSetStance = false;
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal") bool bHasPending = false;

	// ---- движение
	/** `moveFighter`: BFS за `Movement`, блок — живые бойцы и закрытые двери (R4 §2.6.3). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	TArray<FUmFighterMoveTargets> MoveTargets;

	/** `maneuver` без BOOST: BFS за `Movement`; промежуточные — только wall/obstacle, конечная свободна (R4 §2.6.2). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	TArray<FUmFighterMoveTargets> ManeuverTargets;

	/**
	 * Клетки, которые сервер примет (путь «сквозь» бойца), но клиент по умолчанию не подсвечивает —
	 * пунктир `MI_Highlight_ServerWouldAllow` (ADR §5.7 «Промежуточные клетки манёвра»).
	 */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	TArray<FUmFighterMoveTargets> ServerWouldAllow;

	// ---- атака / карты
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	TArray<FUmAttackOption> Attacks;

	/** Instance id карт SCHEME, играбельных сейчас. */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	TArray<FString> PlayableSchemes;

	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	TArray<FUmDefenseOption> PlayableDefenses;

	// ---- pending
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	TArray<FUmPendingChoice> MyPending;

	/** Есть мои pending, но фаза COMBAT — баннер «после боя» (G19). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	bool bPendingBlockedByCombat = false;

	// ---- стойки
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	TArray<FUmStanceOptionDto> Stances;

	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	FString CurrentStanceId;

	// ---- причины
	UPROPERTY(BlueprintReadOnly, Category = "Um|Legal")
	TArray<FUmRejection> WhyNot;

	/** Первая причина отказа для тега действия или пустой FText. */
	FText WhyNotFor(const FGameplayTag& ActionTag) const;
};

/**
 * Перечислитель. Чистая функция состояния: `Enumerate(State, MyUserId, Abilities, bExternalGateOpen)`.
 * `bExternalGateOpen` — внешний гейт (ADR §4.3 `phaseGate`): false, когда стоит `Input.Mode.Busy`
 * (in-flight мутация / воспроизведение) или `Match.Sync != Live`; тогда все действия закрыты с причиной
 * ExternalGateClosed, но подсветки всё равно вычисляются (HUD показывает их полупрозрачно).
 */
struct UMMODEL_API FUmLegalActions
{
	static FUmLegalSet Enumerate(const FUmGameState& State, const FString& MyUserId, const FUmAbilityTable& Abilities, bool bExternalGateOpen = true);

	/**
	 * Цели манёвра для конкретного бойца с учётом BOOST-карты: `Movement + BoostValue`
	 * (validator.ts:320-330, 69-73 `allowance`). Вызывается FUmInputStateMachine при выборе boost.
	 */
	static FUmFighterMoveTargets ManeuverTargetsFor(const FUmGameState& State, const FUmFighter& Fighter, int32 BoostValue, TMap<FIntPoint, int32>* OutServerWouldAllow = nullptr);

	/** Цели pending MOVE/PLACE для бойца (executor:485-520). */
	static FUmFighterMoveTargets PendingTargetsFor(const FUmGameState& State, const FUmPendingEffect& Pending, const FUmFighter& Fighter);

private:
	static void Reject(FUmLegalSet& Set, const FGameplayTag& Action, const FName& ReasonTag, const FText& Reason);
};

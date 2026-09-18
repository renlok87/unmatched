// UmModel/Public/UmSnapshotDiff.h
// Диф двух снапшотов → список событий партии (ADR §4.2 FUmSnapshotDiff; §5.6 теги Match.Event.*;
// §4.7 — потребитель UUmPresentationSubsystem/UUmMatchCueSubsystem).
//
// Почему диф, а не событийные подписки: `turnChanged` молчит при авто-передаче хода (R4 §4.21),
// `combatSummary` не экспортируется (R4 §2.8, §3.12), auto-resolve публикует только STATE_UPDATED (R3 §2.13),
// ходы бота — серия STATE_UPDATED (R4 §2.16). Единственный надёжный источник — сравнение состояний (ADR §5.5).
//
// Ожидаемые декларации в UmTags.h (группа тегов; уточнение к ADR — соглашение об идентификаторах:
// `namespace UmTags { UE_DECLARE_GAMEPLAY_TAG_EXTERN(Match_Event_Fighter_Moved); … }`, имя тега с точками
// заменяется на подчёркивания; см. $UE/Source/Runtime/GameplayTags/Public/NativeGameplayTags.h:31):
//   Match_Event_Fighter_{Moved,Damaged,Healed,Defeated,Immobilized}
//   Match_Event_Combat_{Declared,DefenseRevealed,Resolved,AutoResolved}
//   Match_Event_Card_{Played,Drawn,Discarded}   Match_Event_Decks_Refreshed
//   Match_Event_Turn_Changed  Match_Event_Actions_Changed  Match_Event_Phase_Changed (уточнение к ADR §5.6)
//   Match_Event_Pending_{Added,Removed}  Match_Event_Stance_Changed  Match_Event_Game_Over
//   Action_{Maneuver,MoveFighter,Attack,PlayDefense,PlayScheme,ResolveCombat,EndTurn,Pass,SetStance,ToggleDoor,Pending_Move,Pending_Place,Pending_ChooseOne}

#pragma once

#include "CoreMinimal.h"
#include "Math/IntPoint.h"
#include "GameplayTagContainer.h"
#include "UmGameState.h"
#include "UmSnapshotDiff.generated.h"

/**
 * Одно событие партии. Поля — ADR §4.2 (`EventTag, FighterId, Magnitude, From, To, CardId, UserId`);
 * `Value` добавлен (уточнение к ADR) для строковых полезных нагрузок: id стойки, имя фазы, id pending.
 * Не все поля заполнены для каждого тега — см. таблицу в FUmSnapshotDiff::Compute.
 */
USTRUCT(BlueprintType)
struct UMMODEL_API FUmMatchEvent
{
	GENERATED_BODY()

	/** `Match.Event.*` (ADR §5.6). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Event")
	FGameplayTag EventTag;

	/** Боец-субъект (Moved/Damaged/Healed/Defeated/Immobilized; Combat.Declared — атакующий). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Event")
	FString FighterId;

	/** Второй боец (Combat.Declared — цель `targetFighterId`). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Event")
	FString OtherFighterId;

	/** Величина: урон/лечение (>0), число добранных/сброшенных карт, новое `actionsRemaining`, суммарный урон боя. */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Event")
	int32 Magnitude = 0;

	/** Позиция «до» (Moved). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Event")
	FIntPoint From = FIntPoint::ZeroValue;

	/** Позиция «после» (Moved) / позиция цели (Combat.Declared). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Event")
	FIntPoint To = FIntPoint::ZeroValue;

	/** Instance id карты (Card.Played/Discarded, Combat.Declared — `attackerCardId`, DefenseRevealed — `defenderCardId`). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Event")
	FString CardId;

	/** userId-субъект (владелец бойца, чей ход, чья рука/сброс, чья стойка, победитель). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Event")
	FString UserId;

	/** Строковая нагрузка: stanceId (Stance.Changed), фаза (Phase.Changed), pending id (Pending.*). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Event")
	FString Value;
};

/**
 * Чистое сравнение `Prev → Next`. Не зависит от источника снапшота; `Match.Event.Decks.Refreshed`
 * добавляет FUmGameSnapshotStore (ADR §5.2), а не диф.
 *
 * Таблица «изменение → событие» (порядок эмиссии — как ниже, важен для очереди презентации ADR §4.7):
 *
 * | Изменение                                                                  | Событие                         | Поля |
 * |----------------------------------------------------------------------------|---------------------------------|------|
 * | `Phase` изменилась                                                          | `Phase.Changed`                 | Value = Next.Phase |
 * | `!Prev.bHasCombatInfo && Next.bHasCombatInfo`                               | `Combat.Declared`               | FighterId = AttackerId, OtherFighterId = TargetFighterId, CardId = AttackerCardId, Magnitude = AttackValue, UserId = owner(attacker), To = pos(target) |
 * | combatInfo в обоих; `!Prev.bHasDefenderCard && Next.bHasDefenderCard`       | `Combat.DefenseRevealed`        | CardId = DefenderCardId, Magnitude = DefenseValue, UserId = DefenderId |
 * | combatInfo в обоих; Prev COMBAT → Next COMBAT_RESOLVE и `!bHasDefenderCard` | `Combat.AutoResolved`           | UserId = DefenderId (таймаут 30 с — R4 §2.7.4) |
 * | Fighters[id].Position изменилась                                           | `Fighter.Moved`                 | FighterId, From, To, UserId = owner |
 * | Fighters[id].Health уменьшилась                                            | `Fighter.Damaged`               | FighterId, Magnitude = delta, UserId |
 * | Fighters[id].Health увеличилась                                            | `Fighter.Healed`                | FighterId, Magnitude |
 * | `!Prev.bIsDefeated && Next.bIsDefeated` (или Health пересёк 0 вниз)         | `Fighter.Defeated`              | FighterId, UserId |
 * | появился effect `immobilized`                                              | `Fighter.Immobilized`           | FighterId |
 * | `Prev.bHasCombatInfo && !Next.bHasCombatInfo` (и не GAME_OVER-очистка без урона) | `Combat.Resolved`          | FighterId = AttackerId(Prev), OtherFighterId = TargetFighterId(Prev), Magnitude = суммарный урон обеих сторон |
 * | HandZones[u].Cards.Num() вырос                                             | `Card.Drawn`                    | UserId, Magnitude = +n |
 * | DiscardPiles[u] получил новые instance id (при bHasDiscardPiles в обоих)   | `Card.Played` / `Card.Discarded`| CardId, UserId. Played — если id ∈ {AttackerCardId, DefenderCardId} нового/старого combatInfo или рука u уменьшилась в action-фазе (scheme/boost); иначе Discarded |
 * | без сбросов (partial-подписка): HandZones[u].Cards.Num() уменьшился        | `Card.Played`                   | UserId, Magnitude = n, CardId пуст |
 * | `Metadata.ActionsRemaining` изменился                                      | `Actions.Changed`               | Magnitude = новое значение, UserId = CurrentTurnPlayerId |
 * | `CurrentTurnPlayerId` или `TurnCount` изменились                           | `Turn.Changed`                  | UserId = новый игрок, Magnitude = TurnCount |
 * | pendingEffects: новый id                                                   | `Pending.Added`                 | Value = id, UserId = PlayerId |
 * | pendingEffects: исчезнувший id                                             | `Pending.Removed`               | Value = id, UserId = PlayerId |
 * | `HeroStances[u]` изменилась/появилась                                      | `Stance.Changed`                | UserId, Value = stanceId (авто-флип Ali — R4 §2.13) |
 * | Next.Phase == GAME_OVER (и Prev != GAME_OVER) или появился WinnerId         | `Game.Over`                     | UserId = WinnerId (пусто при 0 живых — R4 §2.8 п.8) |
 *
 * Чужая рука: только `Cards.Num()` (ADR §5.2 «Приватность»); id чужих карт из руки не читаются.
 */
struct UMMODEL_API FUmSnapshotDiff
{
	static TArray<FUmMatchEvent> Compute(const FUmGameState& Prev, const FUmGameState& Next);

	/** Есть ли в дифе событие с тегом (точное совпадение). */
	static bool Contains(const TArray<FUmMatchEvent>& Events, const FGameplayTag& Tag);
};

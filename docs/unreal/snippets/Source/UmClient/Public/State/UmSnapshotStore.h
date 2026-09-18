// UmClient/Public/State/UmSnapshotStore.h
// FUmGameSnapshotStore — seq-дедупликация и мерж снапшотов (ADR §4.4; правила §5.2; факт §1.3 п.8; G12, G23).
// Примечание: ADR §3.3 называет файл `State/UmGameSnapshotStore.h`; в этой группе сниппетов имя файла —
// `UmSnapshotStore.h` (задание C5); имя класса — по ADR (`FUmGameSnapshotStore`), при переносе в проект
// переименовать файл по ADR.
//
// Источники поведения: R3 §2.11 (partial-подписка без decks/discardPiles), §2.13 (семантика seq, gap →
// только полный `gameState`), R4 §2.16 (бурсты бота), candidate-1 §3.5.1, candidate-2 §3.4.4.

#pragma once

#include "CoreMinimal.h"
#include "Delegates/Delegate.h"
#include "UmGameState.h"
#include "UmSnapshotDiff.h"
#include "UmSnapshotStore.generated.h"

/** Откуда пришёл снапшот (ADR §4.4 `EUmSnapshotSource {Query, Mutation, Subscription}`). */
UENUM(BlueprintType)
enum class EUmSnapshotSource : uint8
{
	/** `query gameState` — полный JSON с decks/discardPiles (R3 §2.5, §2.9.1). */
	Query,
	/** `GameMutationResult.state` — полный JSON (R3 §2.8). */
	Mutation,
	/** `subscription gameStateUpdated` — пять строк, БЕЗ decks/discardPiles (R3 §2.12). */
	Subscription
};

/**
 * Исход применения (ADR §4.4 `EApplyResult {Applied, DroppedStale, GapDetected}`; `ReplacedSameSeq` —
 * уточнение к ADR: отдельный исход для строки §5.2 «Source ∈ {Query, Mutation} && Seq == LastSeq → применить»,
 * чтобы презентация не проигрывала диф повторно).
 */
UENUM(BlueprintType)
enum class EUmApplyResult : uint8
{
	/** Применён; `Diff` содержит события для очереди презентации. */
	Applied,
	/** Отброшен как устаревший (эхо подписки после ответа мутации — норма). */
	DroppedStale,
	/** Применён, но `Seq > LastSeq + 1` — вызван OnRefetchNeeded; промежуточные состояния потеряны. */
	GapDetected,
	/** Тот же seq из Query/Mutation поверх partial-подписки: заменены decks/discardPiles, диф — только Decks.Refreshed. */
	ReplacedSameSeq
};

/** Результат Apply (ADR §4.4 `FUmApplyResult { EApplyResult; bool bDecksStale; TArray<FUmMatchEvent> Diff }`). */
USTRUCT(BlueprintType)
struct UMCLIENT_API FUmApplyResult
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Um|Sync")
	EUmApplyResult Result = EUmApplyResult::DroppedStale;

	/** Состояние флага после применения (см. FUmGameSnapshotStore::IsDecksStale). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Sync")
	bool bDecksStale = false;

	/** События `Prev → Next` (пусто для DroppedStale). */
	UPROPERTY(BlueprintReadOnly, Category = "Um|Sync")
	TArray<FUmMatchEvent> Diff;

	UPROPERTY(BlueprintReadOnly, Category = "Um|Sync")
	int32 PrevSeq = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Um|Sync")
	int32 NewSeq = 0;
};

/**
 * Хранилище текущего авторитетного снапшота. Не UObject — принадлежит UUmStateSubsystem (ADR §4.4),
 * тестируется на фикстурах без движка (spec `Unmatched.Client.SnapshotStore`, ADR §4.8).
 *
 * Правила Apply (ADR §5.2, таблица), в порядке проверки:
 *  1. `Source == Subscription && Seq <= LastSeq`                      → DroppedStale.
 *  2. `Source ∈ {Query, Mutation} && Seq <  LastSeq`                  → DroppedStale.
 *  3. `Source ∈ {Query, Mutation} && Seq == LastSeq`                  → ReplacedSameSeq: Current заменяется целиком
 *     (полный снапшот), Diff = [Decks.Refreshed], bDecksStale = false. Это единственный снапшот с
 *     decks/discardPiles для этого seq, если эхо подписки пришло первым (факт §1.3 п.8).
 *  4. `Source == Subscription && !Incoming.bHasDecks`                 → мерж Decks/DiscardPiles из Current
 *     (bHasDecks/bHasDiscardPiles копируются); если после мержа изменились размер руки/сброса любого игрока,
 *     фаза, bHasCombatInfo или bHasDefenderCard (ADR §5.2) — либо диф содержит события соперника
 *     Combat.Declared / Combat.DefenseRevealed / Card.Played / Card.Drawn (candidate-2 §3.4.4:
 *     ATTACK_INITIATED/DEFENSE_PLAYED/MANEUVER/CARD_PLAYED) — bDecksStale = true, OnDecksStale.
 *     Атрибуция «соперника» не нужна: свои мутации приходят полным ответом (Mutation) раньше эха,
 *     поэтому любой применённый partial — чужое действие, ход бота или auto-resolve.
 *  5. `LastSeq == 0 || Seq == LastSeq + 1`                             → Applied.
 *  6. `Seq > LastSeq + 1`                                              → GapDetected: применить (снапшот полный
 *     для Query/Mutation; partial — с мержем п.4) и вызвать OnRefetchNeeded(LastSeq, Seq) — единственный
 *     надёжный способ закрыть дыру — повторный `query gameState` (R3 §2.13 п.7); `eventsSince` не используется.
 *  7. Ответ Query/Mutation применён                                    → bDecksStale = false.
 */
class UMCLIENT_API FUmGameSnapshotStore
{
public:
	/** (LastSeq, IncomingSeq) — владелец должен выполнить RefetchState() (ADR §5.2). */
	DECLARE_MULTICAST_DELEGATE_TwoParams(FOnRefetchNeeded, int32 /*LastSeq*/, int32 /*IncomingSeq*/);
	/** bDecksStale стал true — владелец запускает RefreshFullStateDebounced(300 мс). */
	DECLARE_MULTICAST_DELEGATE(FOnDecksStale);

	FOnRefetchNeeded OnRefetchNeeded;
	FOnDecksStale OnDecksStale;

	/** Применить снапшот по правилам выше. Rvalue-версия — основная (ADR §4.4 `Apply(FUmGameState&&, …)`). */
	FUmApplyResult Apply(FUmGameState&& Incoming, EUmSnapshotSource Source);

	/** Удобная копирующая перегрузка (задание C5: `Apply(const FUmGameState&, …)`). */
	FUmApplyResult Apply(const FUmGameState& Incoming, EUmSnapshotSource Source);

	/**
	 * Принудительная замена (реконнект: `gameSequence > LastSeq` → `gameState` → ForceReplace — ADR §5.2).
	 * Seq-guard игнорируется, bDecksStale = false, Diff вычисляется относительно предыдущего Current
	 * (для презентации — fast-forward без анимаций решает вызывающий).
	 */
	FUmApplyResult ForceReplace(FUmGameState&& Full);

	/** Сброс при ExitGame. */
	void Reset();

	bool HasState() const { return bHasState; }
	const FUmGameState& Current() const { return CurrentState; }
	int32 LastSeq() const { return bHasState ? CurrentState.SequenceNumber : 0; }
	bool IsDecksStale() const { return bDecksStale; }
	const FString& GameId() const { return CurrentState.GameId; }

private:
	/** Мерж Decks/DiscardPiles из Current в Incoming при отсутствии их в partial (R3 §2.11). */
	static void MergeDecksFrom(const FUmGameState& From, FUmGameState& Into);

	/** Проверка условий ADR §5.2 для bDecksStale после мержа. */
	static bool DetectDecksStale(const FUmGameState& Prev, const FUmGameState& Merged, const TArray<FUmMatchEvent>& Diff);

	FUmGameState CurrentState;
	bool bHasState = false;
	bool bDecksStale = false;
};

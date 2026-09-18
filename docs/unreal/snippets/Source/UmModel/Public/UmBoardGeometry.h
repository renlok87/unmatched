// UmModel/Public/UmBoardGeometry.h
// Геометрия доски — клиентское зеркало backend/src/game-engine/engine/adjacency.service.ts.
// ADR §4.3 (FUmBoardGeometry); R4 §2.6.1; candidate-2 §3.5.2 (FUnmGeometry) и Приложение A.
//
// Принцип (ADR §5.7): зеркало советует, сервер решает. Всё, что здесь вычисляется, —
// подсказки для подсветки/гейтов; любая мутация всё равно уходит на сервер.
//
// Зависимости на wire-модель (UmGameState.h, группа C3): FUmBoardState { Width, Height,
// Rows[y].Cells[x], Doors }, FUmCell { Type, Zone, Zones, X, Y, bIsOpen }, FUmFighter
// { Id, Position{X,Y}, Health, bIsDefeated }, FUmGameState { Fighters, BoardState }.
// Имена — PascalCase по ADR §3.6 (camelCase JSON сопоставляется регистронезависимо).

#pragma once

#include "CoreMinimal.h"
#include "Math/IntPoint.h"
#include "Containers/Map.h"
#include "Containers/Set.h"
#include "UmGameState.h"

/**
 * Статические функции геометрии доски. Никаких UObject, всё чистое и тестируемое
 * на фикстурах (spec `Unmatched.Model.Geometry`, ADR §4.8).
 *
 * Все позиции — FIntPoint(X, Y) в grid-координатах 0..Width-1 / 0..Height-1,
 * индексация клеток `Rows[Y].Cells[X]` (R3 §2.9.6: `cells[y][x]`).
 */
struct UMMODEL_API FUmBoardGeometry
{
	/** Максимально допустимая координата в DTO мутаций: `@Min(0) @Max(19)` (R4 §2.17). */
	static constexpr int32 MaxMutationCoord = 19;

	/** Ключ клетки в формате сервера `"x:y"` (board.model.ts:110-112; R4 §2.5.5). */
	static FString CellKey(const FIntPoint& P);

	/** Манхэттенское расстояние (adjacency.service.ts:181). */
	static int32 Manhattan(const FIntPoint& A, const FIntPoint& B);

	/** Смежность = манхэттен ровно 1; диагональ НЕ смежна (adjacency.service.ts:201-204; R4 §2.6.1). */
	static bool IsAdjacent(const FIntPoint& A, const FIntPoint& B);

	/** Клетка в границах `Width × Height` (game-rules.validator.ts:232-240). */
	static bool IsInBounds(const FUmBoardState& Board, const FIntPoint& P);

	/** Указатель на клетку или nullptr, если вне границ / доска неполна (fallback 20×20 — R4 §2.6.5). */
	static const FUmCell* FindCell(const FUmBoardState& Board, const FIntPoint& P);

	/**
	 * Непроходимость для BFS: `wall`, `obstacle`, `door && !isOpen`
	 * (adjacency.service.ts:146-150 `isCellBlocked`). Отсутствующая клетка считается проходимой
	 * `normal` (сервер при дырах в `cells` создаёт `normal` — R4 §2.6.5).
	 */
	static bool IsCellBlocked(const FUmCell* Cell);

	/**
	 * Валидность позиции для манёвра/pending: в границах и не `wall/obstacle`
	 * (game-rules.validator.ts:232-247 `isValidPosition`). Закрытые двери здесь НЕ проверяются —
	 * это намеренная разница с BFS `moveFighter` (R4 §2.6.2 п.4; ADR §5.7 «Закрытые двери в манёвре»).
	 */
	static bool IsValidPosition(const FUmBoardState& Board, const FIntPoint& P);

	/** Четыре ортогональных соседа в границах доски (adjacency.service.ts:53-84, диагонали выключены). */
	static void GetOrthogonalNeighbours(const FUmBoardState& Board, const FIntPoint& P, TArray<FIntPoint>& Out);

	/**
	 * BFS 4-связности — зеркало `getReachableCells(board, start, maxCost, { blockedPositions })`
	 * (adjacency.service.ts:90-141).
	 *
	 * @param Blocked  Клетки, в которые нельзя войти и которые не расширяются (живые бойцы — см. LivingFighterCells).
	 * @param bBlockClosedDoors  true — использовать `IsCellBlocked` (как `moveFighter`, R4 §2.6.3);
	 *                           false — только `wall/obstacle` (как промежуточные клетки манёвра, R4 §2.6.2 п.4).
	 * @return Map «клетка → стоимость (число шагов)», стартовая клетка НЕ включена (cost > 0 — `:112-117`).
	 */
	static TMap<FIntPoint, int32> Reachable(
		const FUmBoardState& Board,
		const FIntPoint& Start,
		int32 MaxSteps,
		const TSet<FIntPoint>& Blocked,
		bool bBlockClosedDoors = true);

	/**
	 * Кратчайший путь BFS (те же правила проходимости, что и Reachable). Возвращает путь БЕЗ стартовой
	 * клетки — именно такой `path` ждёт `ManeuverMoveInput` (R4 §2.6.2 п.7: «стартовая не включается»).
	 * Если Goal == Start — возвращает true и пустой путь (сервер: перемещение в свою клетку — no-op, R4 §2.6.3).
	 * @return false, если Goal недостижима за MaxSteps.
	 */
	static bool ShortestPath(
		const FUmBoardState& Board,
		const FIntPoint& Start,
		const FIntPoint& Goal,
		int32 MaxSteps,
		const TSet<FIntPoint>& Blocked,
		TArray<FIntPoint>& OutPath,
		bool bBlockClosedDoors = true);

	/**
	 * Legacy-зона: `cells[a].zone === cells[b].zone`, оба непусты (adjacency.service.ts:214-218 `isInSameZone`).
	 * Именно это использует сервер для ranged-досягаемости (R4 §2.7.1 п.3; ADR §5.7 «Ranged-досягаемость»).
	 * На fallback-доске 20×20 зон нет → всегда false → ranged деградирует до смежности (R4 §2.6.5).
	 */
	static bool SameLegacyZone(const FUmBoardState& Board, const FIntPoint& A, const FIntPoint& B);

	/** Зоны клетки: `zones[]` → фолбэк `[zone]` → `[]` (board.model.ts:41-45 `getCellZones`). */
	static TArray<FString> CellZones(const FUmCell* Cell);

	/**
	 * Пересечение `zones[]` двух клеток (мультизонные клетки Cobble City (1,1), (3,1), (1,2) —
	 * cobble-city.ts:14-53). Используется ТОЛЬКО для условий эффектов `SHARES_ZONE_WITH_OPPONENT`
	 * и превью; НЕ для атаки (ADR §4.3; R4 §4.1).
	 */
	static bool SharesAnyZone(const FUmBoardState& Board, const FIntPoint& A, const FIntPoint& B);

	/**
	 * Множество клеток, занятых живыми бойцами (`health > 0 && !isDefeated`), кроме ExceptFighterId —
	 * `blockedPositions` сервера (game-rules.validator.ts:414-418; R4 §2.6.3).
	 */
	static TSet<FIntPoint> LivingFighterCells(const FUmGameState& State, const FString& ExceptFighterId = FString());

	/** Есть ли живой боец на клетке (проверка занятости конечной клетки — game-rules.validator.ts:235-249). */
	static bool IsOccupiedByLiving(const FUmGameState& State, const FIntPoint& P, const FString& ExceptFighterId = FString());

	/** Позиция бойца как FIntPoint (обёртка над FUmPosition {X, Y}). */
	static FIntPoint PositionOf(const FUmFighter& Fighter);
};

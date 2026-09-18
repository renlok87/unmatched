// UmModel/Private/UmBoardGeometry.cpp
// Зеркало backend/src/game-engine/engine/adjacency.service.ts (см. ссылки в заголовке).

#include "UmBoardGeometry.h"
#include "Containers/Queue.h"

FString FUmBoardGeometry::CellKey(const FIntPoint& P)
{
	// board.model.ts:110-112 — `${x}:${y}`
	return FString::Printf(TEXT("%d:%d"), P.X, P.Y);
}

int32 FUmBoardGeometry::Manhattan(const FIntPoint& A, const FIntPoint& B)
{
	return FMath::Abs(A.X - B.X) + FMath::Abs(A.Y - B.Y);
}

bool FUmBoardGeometry::IsAdjacent(const FIntPoint& A, const FIntPoint& B)
{
	// adjacency.service.ts:201-204 — `manhattanDistance(a, b) === 1`
	return Manhattan(A, B) == 1;
}

bool FUmBoardGeometry::IsInBounds(const FUmBoardState& Board, const FIntPoint& P)
{
	return P.X >= 0 && P.Y >= 0 && P.X < Board.Width && P.Y < Board.Height;
}

const FUmCell* FUmBoardGeometry::FindCell(const FUmBoardState& Board, const FIntPoint& P)
{
	if (!IsInBounds(Board, P))
	{
		return nullptr;
	}
	if (!Board.Rows.IsValidIndex(P.Y))
	{
		return nullptr;
	}
	const FUmCellRow& Row = Board.Rows[P.Y];
	if (!Row.Cells.IsValidIndex(P.X))
	{
		return nullptr;
	}
	return &Row.Cells[P.X];
}

bool FUmBoardGeometry::IsCellBlocked(const FUmCell* Cell)
{
	// adjacency.service.ts:146-150
	if (Cell == nullptr)
	{
		return false; // дыра в cells → сервер трактует как normal (game-initialization.service.ts:320-349)
	}
	if (Cell->Type == TEXT("wall") || Cell->Type == TEXT("obstacle"))
	{
		return true;
	}
	if (Cell->Type == TEXT("door") && !Cell->bIsOpen)
	{
		return true;
	}
	return false;
}

bool FUmBoardGeometry::IsValidPosition(const FUmBoardState& Board, const FIntPoint& P)
{
	// game-rules.validator.ts:232-247 — границы + не wall/obstacle (двери не проверяются)
	if (!IsInBounds(Board, P))
	{
		return false;
	}
	const FUmCell* Cell = FindCell(Board, P);
	if (Cell == nullptr)
	{
		// Сервер: `!cell → false`. На практике cells всегда заполнены (fallback 20×20 создаёт все клетки),
		// поэтому отсутствие клетки при валидных границах — неполная доска в фикстуре; считаем непроходимой,
		// как сервер.
		return false;
	}
	return !(Cell->Type == TEXT("wall") || Cell->Type == TEXT("obstacle"));
}

void FUmBoardGeometry::GetOrthogonalNeighbours(const FUmBoardState& Board, const FIntPoint& P, TArray<FIntPoint>& Out)
{
	// adjacency.service.ts:53-84 — порядок N/S/E/W не влияет на результат BFS по стоимости,
	// но влияет на выбор одного из равных кратчайших путей; фиксируем порядок сервера: (0,-1),(0,1),(1,0),(-1,0).
	static const FIntPoint Offsets[4] = { FIntPoint(0, -1), FIntPoint(0, 1), FIntPoint(1, 0), FIntPoint(-1, 0) };
	Out.Reset(4);
	for (const FIntPoint& O : Offsets)
	{
		const FIntPoint N = P + O;
		if (IsInBounds(Board, N))
		{
			Out.Add(N);
		}
	}
}

TMap<FIntPoint, int32> FUmBoardGeometry::Reachable(
	const FUmBoardState& Board,
	const FIntPoint& Start,
	int32 MaxSteps,
	const TSet<FIntPoint>& Blocked,
	bool bBlockClosedDoors)
{
	// adjacency.service.ts:90-141
	TMap<FIntPoint, int32> Result;
	if (MaxSteps <= 0)
	{
		return Result;
	}

	TSet<FIntPoint> Visited;
	Visited.Add(Start);

	TArray<TPair<FIntPoint, int32>> Queue; // (позиция, стоимость); используем индексный «head» вместо TQueue ради детерминизма
	Queue.Emplace(Start, 0);
	int32 Head = 0;

	TArray<FIntPoint> Neighbours;
	while (Head < Queue.Num())
	{
		const TPair<FIntPoint, int32> Cur = Queue[Head++];
		if (Cur.Value > 0)
		{
			Result.Add(Cur.Key, Cur.Value);
		}
		if (Cur.Value >= MaxSteps)
		{
			continue;
		}

		GetOrthogonalNeighbours(Board, Cur.Key, Neighbours);
		for (const FIntPoint& N : Neighbours)
		{
			const FUmCell* Cell = FindCell(Board, N);
			const bool bBlockedByTerrain = bBlockClosedDoors
				? IsCellBlocked(Cell)
				: (Cell != nullptr && (Cell->Type == TEXT("wall") || Cell->Type == TEXT("obstacle")));
			if (bBlockedByTerrain || Blocked.Contains(N))
			{
				continue; // `:124-126` — заблокированные не входят и не расширяются
			}
			if (Visited.Contains(N))
			{
				continue;
			}
			Visited.Add(N);
			Queue.Emplace(N, Cur.Value + 1); // стоимость ортогонального шага = 1 (`:75` диагонали выключены)
		}
	}
	return Result;
}

bool FUmBoardGeometry::ShortestPath(
	const FUmBoardState& Board,
	const FIntPoint& Start,
	const FIntPoint& Goal,
	int32 MaxSteps,
	const TSet<FIntPoint>& Blocked,
	TArray<FIntPoint>& OutPath,
	bool bBlockClosedDoors)
{
	OutPath.Reset();
	if (Start == Goal)
	{
		return true; // no-op перемещение валидно на сервере (R4 §2.6.3)
	}
	if (MaxSteps <= 0)
	{
		return false;
	}

	TMap<FIntPoint, FIntPoint> Parent;
	TMap<FIntPoint, int32> Cost;
	Cost.Add(Start, 0);

	TArray<FIntPoint> Queue;
	Queue.Add(Start);
	int32 Head = 0;

	TArray<FIntPoint> Neighbours;
	while (Head < Queue.Num())
	{
		const FIntPoint Cur = Queue[Head++];
		const int32 CurCost = Cost[Cur];
		if (CurCost >= MaxSteps)
		{
			continue;
		}
		GetOrthogonalNeighbours(Board, Cur, Neighbours);
		for (const FIntPoint& N : Neighbours)
		{
			if (Cost.Contains(N))
			{
				continue;
			}
			const FUmCell* Cell = FindCell(Board, N);
			const bool bBlockedByTerrain = bBlockClosedDoors
				? IsCellBlocked(Cell)
				: (Cell != nullptr && (Cell->Type == TEXT("wall") || Cell->Type == TEXT("obstacle")));
			if (bBlockedByTerrain || Blocked.Contains(N))
			{
				continue;
			}
			Cost.Add(N, CurCost + 1);
			Parent.Add(N, Cur);
			if (N == Goal)
			{
				// восстановление пути без стартовой клетки
				FIntPoint Step = Goal;
				while (Step != Start)
				{
					OutPath.Insert(Step, 0);
					Step = Parent[Step];
				}
				return true;
			}
			Queue.Add(N);
		}
	}
	return false;
}

bool FUmBoardGeometry::SameLegacyZone(const FUmBoardState& Board, const FIntPoint& A, const FIntPoint& B)
{
	// adjacency.service.ts:214-218 — `za != null && za === zb`, читает legacy `zone`
	const FUmCell* CA = FindCell(Board, A);
	const FUmCell* CB = FindCell(Board, B);
	if (CA == nullptr || CB == nullptr)
	{
		return false;
	}
	if (CA->Zone.IsEmpty() || CB->Zone.IsEmpty())
	{
		return false;
	}
	return CA->Zone == CB->Zone; // регистрозависимо, как `===` на сервере
}

TArray<FString> FUmBoardGeometry::CellZones(const FUmCell* Cell)
{
	// board.model.ts:41-45
	TArray<FString> Zones;
	if (Cell == nullptr)
	{
		return Zones;
	}
	if (Cell->Zones.Num() > 0)
	{
		Zones = Cell->Zones;
	}
	else if (!Cell->Zone.IsEmpty())
	{
		Zones.Add(Cell->Zone);
	}
	return Zones;
}

bool FUmBoardGeometry::SharesAnyZone(const FUmBoardState& Board, const FIntPoint& A, const FIntPoint& B)
{
	const TArray<FString> ZA = CellZones(FindCell(Board, A));
	const TArray<FString> ZB = CellZones(FindCell(Board, B));
	for (const FString& Z : ZA)
	{
		if (ZB.Contains(Z))
		{
			return true;
		}
	}
	return false;
}

TSet<FIntPoint> FUmBoardGeometry::LivingFighterCells(const FUmGameState& State, const FString& ExceptFighterId)
{
	// game-rules.validator.ts:414-418 — занятые живыми бойцами клетки
	TSet<FIntPoint> Cells;
	for (const FUmFighter& F : State.Fighters)
	{
		if (!ExceptFighterId.IsEmpty() && F.Id == ExceptFighterId)
		{
			continue;
		}
		if (F.Health > 0 && !F.bIsDefeated)
		{
			Cells.Add(PositionOf(F));
		}
	}
	return Cells;
}

bool FUmBoardGeometry::IsOccupiedByLiving(const FUmGameState& State, const FIntPoint& P, const FString& ExceptFighterId)
{
	for (const FUmFighter& F : State.Fighters)
	{
		if (!ExceptFighterId.IsEmpty() && F.Id == ExceptFighterId)
		{
			continue;
		}
		if (F.Health > 0 && !F.bIsDefeated && PositionOf(F) == P)
		{
			return true;
		}
	}
	return false;
}

FIntPoint FUmBoardGeometry::PositionOf(const FUmFighter& Fighter)
{
	return FIntPoint(Fighter.Position.X, Fighter.Position.Y);
}

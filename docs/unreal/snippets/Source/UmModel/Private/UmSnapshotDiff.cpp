// UmModel/Private/UmSnapshotDiff.cpp
// Реализация таблицы «изменение → событие» из UmSnapshotDiff.h.

#include "UmSnapshotDiff.h"
#include "UmTags.h"
#include "UmRules.h"

namespace
{
	FUmMatchEvent& Emit(TArray<FUmMatchEvent>& Out, const FGameplayTag& Tag)
	{
		FUmMatchEvent& E = Out.AddDefaulted_GetRef();
		E.EventTag = Tag;
		return E;
	}

	const FUmFighter* FindFighter(const FUmGameState& S, const FString& Id)
	{
		for (const FUmFighter& F : S.Fighters)
		{
			if (F.Id == Id)
			{
				return &F;
			}
		}
		return nullptr;
	}

	FString OwnerOf(const FUmGameState& S, const FString& FighterId)
	{
		const FUmFighter* F = FindFighter(S, FighterId);
		return F ? F->OwnerId : FString();
	}

	int32 HandCount(const FUmGameState& S, const FString& UserId)
	{
		const FUmHandZone* H = S.HandZones.Find(UserId);
		return H ? H->Cards.Num() : 0;
	}

	bool HasImmobilized(const FUmFighter& F)
	{
		return FUmRules::IsImmobilized(F);
	}
}

bool FUmSnapshotDiff::Contains(const TArray<FUmMatchEvent>& Events, const FGameplayTag& Tag)
{
	for (const FUmMatchEvent& E : Events)
	{
		if (E.EventTag == Tag)
		{
			return true;
		}
	}
	return false;
}

TArray<FUmMatchEvent> FUmSnapshotDiff::Compute(const FUmGameState& Prev, const FUmGameState& Next)
{
	TArray<FUmMatchEvent> Out;

	const FUmGameStateMetadata& PM = Prev.Metadata;
	const FUmGameStateMetadata& NM = Next.Metadata;

	// -------------------------------------------------------------- фаза
	if (Prev.Phase != Next.Phase)
	{
		FUmMatchEvent& E = Emit(Out, UmTags::Match_Event_Phase_Changed);
		E.Value = Next.Phase;
	}

	// -------------------------------------------------------------- бой: объявление / защита / auto-resolve
	const bool bCombatAppeared = !PM.bHasCombatInfo && NM.bHasCombatInfo;
	const bool bCombatBoth = PM.bHasCombatInfo && NM.bHasCombatInfo;
	const bool bCombatGone = PM.bHasCombatInfo && !NM.bHasCombatInfo;

	if (bCombatAppeared)
	{
		// executor:1086-1120 — combatInfo пишется при attack; карта атаки уже в сбросе
		FUmMatchEvent& E = Emit(Out, UmTags::Match_Event_Combat_Declared);
		E.FighterId = NM.CombatInfo.AttackerId;
		E.OtherFighterId = NM.CombatInfo.TargetFighterId;
		E.CardId = NM.CombatInfo.AttackerCardId;
		E.Magnitude = NM.CombatInfo.AttackValue;
		E.UserId = OwnerOf(Next, NM.CombatInfo.AttackerId);
		if (const FUmFighter* T = FindFighter(Next, NM.CombatInfo.TargetFighterId))
		{
			E.To = FIntPoint(T->Position.X, T->Position.Y);
		}
	}
	if (bCombatBoth && !PM.CombatInfo.bHasDefenderCard && NM.CombatInfo.bHasDefenderCard)
	{
		// executor:1150-1260 — playDefense → COMBAT_RESOLVE, defenderCardId
		FUmMatchEvent& E = Emit(Out, UmTags::Match_Event_Combat_DefenseRevealed);
		E.CardId = NM.CombatInfo.DefenderCardId;
		E.Magnitude = NM.CombatInfo.DefenseValue;
		E.UserId = NM.CombatInfo.DefenderId;
	}
	if (bCombatBoth && Prev.Phase == TEXT("COMBAT") && Next.Phase == TEXT("COMBAT_RESOLVE") && !NM.CombatInfo.bHasDefenderCard)
	{
		// combat-timeout.service.ts:260-282 — только смена фазы, defenseValue 0, урона нет
		FUmMatchEvent& E = Emit(Out, UmTags::Match_Event_Combat_AutoResolved);
		E.UserId = NM.CombatInfo.DefenderId;
		E.FighterId = NM.CombatInfo.AttackerId;
	}

	// -------------------------------------------------------------- бойцы
	int32 TotalCombatDamage = 0;
	for (const FUmFighter& NF : Next.Fighters)
	{
		const FUmFighter* PF = FindFighter(Prev, NF.Id);
		if (PF == nullptr)
		{
			continue; // новых бойцов по ходу партии сервер не создаёт (R3 §2.15)
		}
		if (PF->Position.X != NF.Position.X || PF->Position.Y != NF.Position.Y)
		{
			FUmMatchEvent& E = Emit(Out, UmTags::Match_Event_Fighter_Moved);
			E.FighterId = NF.Id;
			E.UserId = NF.OwnerId;
			E.From = FIntPoint(PF->Position.X, PF->Position.Y);
			E.To = FIntPoint(NF.Position.X, NF.Position.Y);
		}
		if (NF.Health < PF->Health)
		{
			FUmMatchEvent& E = Emit(Out, UmTags::Match_Event_Fighter_Damaged);
			E.FighterId = NF.Id;
			E.UserId = NF.OwnerId;
			E.Magnitude = PF->Health - NF.Health;
			TotalCombatDamage += E.Magnitude;
		}
		else if (NF.Health > PF->Health)
		{
			FUmMatchEvent& E = Emit(Out, UmTags::Match_Event_Fighter_Healed);
			E.FighterId = NF.Id;
			E.UserId = NF.OwnerId;
			E.Magnitude = NF.Health - PF->Health;
		}
		const bool bWasAlive = PF->Health > 0 && !PF->bIsDefeated;
		const bool bIsAlive = NF.Health > 0 && !NF.bIsDefeated;
		if (bWasAlive && !bIsAlive)
		{
			// executor:1561-1601 — `health <= 0 && !isDefeated → isDefeated = true`
			FUmMatchEvent& E = Emit(Out, UmTags::Match_Event_Fighter_Defeated);
			E.FighterId = NF.Id;
			E.UserId = NF.OwnerId;
		}
		if (!HasImmobilized(*PF) && HasImmobilized(NF))
		{
			FUmMatchEvent& E = Emit(Out, UmTags::Match_Event_Fighter_Immobilized);
			E.FighterId = NF.Id;
			E.UserId = NF.OwnerId;
		}
	}

	// -------------------------------------------------------------- бой: резолв
	if (bCombatGone)
	{
		// executor:1637-1668 — combatInfo = undefined после резолва; checkAndApplyGameOver тоже чистит (:657-671).
		// Итоги — по диффу Health (combatSummary не приходит — R4 §3.12).
		FUmMatchEvent& E = Emit(Out, UmTags::Match_Event_Combat_Resolved);
		E.FighterId = PM.CombatInfo.AttackerId;
		E.OtherFighterId = PM.CombatInfo.TargetFighterId;
		E.UserId = OwnerOf(Prev, PM.CombatInfo.AttackerId);
		E.Magnitude = TotalCombatDamage;
		E.CardId = PM.CombatInfo.AttackerCardId;
	}

	// -------------------------------------------------------------- карты: рука и сброс по игрокам
	for (const FUmGameStatePlayer& P : Next.Players)
	{
		const FString& U = P.UserId;
		const int32 PrevHand = HandCount(Prev, U);
		const int32 NextHand = HandCount(Next, U);

		if (NextHand > PrevHand)
		{
			FUmMatchEvent& E = Emit(Out, UmTags::Match_Event_Card_Drawn);
			E.UserId = U;
			E.Magnitude = NextHand - PrevHand;
		}

		const FUmCardList* PrevPile = Prev.bHasDiscardPiles ? Prev.DiscardPiles.Find(U) : nullptr;
		const FUmCardList* NextPile = Next.bHasDiscardPiles ? Next.DiscardPiles.Find(U) : nullptr;
		if (PrevPile && NextPile)
		{
			TSet<FString> PrevIds;
			for (const FUmCard& C : PrevPile->Cards)
			{
				PrevIds.Add(C.Id);
			}
			const bool bHandShrank = NextHand < PrevHand;
			for (const FUmCard& C : NextPile->Cards)
			{
				if (PrevIds.Contains(C.Id))
				{
					continue;
				}
				// recycleDeck перекладывает сброс в колоду (deck-management.service.ts:216-240) — тогда
				// сброс уменьшается, новых id нет; здесь только рост.
				const bool bIsCombatCard =
					(NM.bHasCombatInfo && (C.Id == NM.CombatInfo.AttackerCardId || C.Id == NM.CombatInfo.DefenderCardId)) ||
					(PM.bHasCombatInfo && (C.Id == PM.CombatInfo.AttackerCardId || C.Id == PM.CombatInfo.DefenderCardId));
				const bool bPlayed = bIsCombatCard || (bHandShrank && (U == Prev.CurrentTurnPlayerId || U == PM.CombatInfo.DefenderId));
				FUmMatchEvent& E = Emit(Out, bPlayed ? UmTags::Match_Event_Card_Played : UmTags::Match_Event_Card_Discarded);
				E.UserId = U;
				E.CardId = C.Id;
				E.Magnitude = 1;
			}
		}
		else if (NextHand < PrevHand)
		{
			// Partial-подписка без сбросов: знаем только, что рука уменьшилась
			FUmMatchEvent& E = Emit(Out, UmTags::Match_Event_Card_Played);
			E.UserId = U;
			E.Magnitude = PrevHand - NextHand;
		}
	}

	// -------------------------------------------------------------- экономика и ход
	if (PM.ActionsRemaining != NM.ActionsRemaining)
	{
		FUmMatchEvent& E = Emit(Out, UmTags::Match_Event_Actions_Changed);
		E.Magnitude = NM.ActionsRemaining;
		E.UserId = Next.CurrentTurnPlayerId;
	}
	if (Prev.CurrentTurnPlayerId != Next.CurrentTurnPlayerId || Prev.TurnCount != Next.TurnCount)
	{
		// advanceTurn (executor:168-262); `turnChanged` при авто-передаче не публикуется (R4 §4.21)
		FUmMatchEvent& E = Emit(Out, UmTags::Match_Event_Turn_Changed);
		E.UserId = Next.CurrentTurnPlayerId;
		E.Magnitude = Next.TurnCount;
	}

	// -------------------------------------------------------------- pending
	{
		TSet<FString> PrevIds, NextIds;
		for (const FUmPendingEffect& P : PM.PendingEffects) { PrevIds.Add(P.Id); }
		for (const FUmPendingEffect& P : NM.PendingEffects) { NextIds.Add(P.Id); }
		for (const FUmPendingEffect& P : NM.PendingEffects)
		{
			if (!PrevIds.Contains(P.Id))
			{
				FUmMatchEvent& E = Emit(Out, UmTags::Match_Event_Pending_Added);
				E.Value = P.Id;
				E.UserId = P.PlayerId;
			}
		}
		for (const FUmPendingEffect& P : PM.PendingEffects)
		{
			if (!NextIds.Contains(P.Id))
			{
				FUmMatchEvent& E = Emit(Out, UmTags::Match_Event_Pending_Removed);
				E.Value = P.Id;
				E.UserId = P.PlayerId;
			}
		}
		// CHOOSE_ONE с chooseCount > 1 остаётся с тем же id и меньшим chooseCount (R4 §2.10) — событие не эмитим;
		// HUD перечитает options из Next.
	}

	// -------------------------------------------------------------- стойки
	for (const TPair<FString, FString>& It : NM.HeroStances)
	{
		const FString* PrevStance = PM.HeroStances.Find(It.Key);
		if (PrevStance == nullptr || *PrevStance != It.Value)
		{
			FUmMatchEvent& E = Emit(Out, UmTags::Match_Event_Stance_Changed);
			E.UserId = It.Key;
			E.Value = It.Value;
		}
	}

	// -------------------------------------------------------------- конец партии
	const bool bGameOverNow = Next.Phase == TEXT("GAME_OVER") && Prev.Phase != TEXT("GAME_OVER");
	const bool bWinnerAppeared = PM.WinnerId.IsEmpty() && !NM.WinnerId.IsEmpty();
	if (bGameOverNow || bWinnerAppeared)
	{
		FUmMatchEvent& E = Emit(Out, UmTags::Match_Event_Game_Over);
		E.UserId = NM.WinnerId; // пусто при 0 живых (executor:657-671)
	}

	return Out;
}

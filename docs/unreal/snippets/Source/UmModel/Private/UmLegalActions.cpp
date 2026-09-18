// UmModel/Private/UmLegalActions.cpp
// Реализация таблицы R4 §2.18 и паритета ADR §5.7. Ссылки на бэкенд — у каждого блока.

#include "UmLegalActions.h"
#include "UmBoardGeometry.h"
#include "UmTags.h"   // UmTags::Action_* (нативные теги ADR §5.6; идентификаторы — см. UmSnapshotDiff.h)

#define LOCTEXT_NAMESPACE "UmLegal"

FText FUmLegalSet::WhyNotFor(const FGameplayTag& ActionTag) const
{
	for (const FUmRejection& R : WhyNot)
	{
		if (R.Action == ActionTag)
		{
			return R.Reason;
		}
	}
	return FText::GetEmpty();
}

void FUmLegalActions::Reject(FUmLegalSet& Set, const FGameplayTag& Action, const FName& ReasonTag, const FText& Reason)
{
	FUmRejection& R = Set.WhyNot.AddDefaulted_GetRef();
	R.Action = Action;
	R.ReasonTag = ReasonTag;
	R.Reason = Reason;
}

namespace
{
	const FUmGameStatePlayer* FindPlayer(const FUmGameState& State, const FString& UserId)
	{
		for (const FUmGameStatePlayer& P : State.Players)
		{
			if (P.UserId == UserId)
			{
				return &P;
			}
		}
		return nullptr;
	}

	const FUmHandZone* FindHand(const FUmGameState& State, const FString& UserId)
	{
		// Своя рука — HandZones[myUserId].Cards (ADR §5.2 «Приватность»)
		return State.HandZones.Find(UserId);
	}

	const FUmFighter* FindFighter(const FUmGameState& State, const FString& Id)
	{
		for (const FUmFighter& F : State.Fighters)
		{
			if (F.Id == Id)
			{
				return &F;
			}
		}
		return nullptr;
	}

	/** Общий гейт «мой ход + action-фаза + есть действия» для maneuver/moveFighter/attack/scheme/pass. */
	bool ActionGate(const FUmGameState& State, const FString& MyUserId, FName& OutReason, FText& OutText, bool bNeedsAction = true)
	{
		if (State.Phase == TEXT("GAME_OVER"))
		{
			OutReason = UmReason::GameOver; OutText = LOCTEXT("GameOver", "Партия завершена"); return false;
		}
		if (State.CurrentTurnPlayerId != MyUserId)
		{
			OutReason = UmReason::NotYourTurn; OutText = LOCTEXT("NotYourTurn", "Сейчас ход соперника"); return false;
		}
		const FUmGameStatePlayer* Me = FindPlayer(State, MyUserId);
		if (Me == nullptr || !Me->bIsAlive)
		{
			OutReason = UmReason::PlayerNotAlive; OutText = LOCTEXT("PlayerNotAlive", "Вы выбыли из партии"); return false;
		}
		if (!FUmRules::IsActionPhase(State.Phase))
		{
			OutReason = UmReason::InvalidPhase; OutText = LOCTEXT("InvalidPhase", "Недоступно в текущей фазе"); return false;
		}
		if (bNeedsAction && FUmRules::ActionsRemaining(State) <= 0)
		{
			OutReason = UmReason::NoActionsLeft; OutText = LOCTEXT("NoActionsLeft", "Действия на этот ход закончились"); return false;
		}
		return true;
	}
}

FUmFighterMoveTargets FUmLegalActions::ManeuverTargetsFor(const FUmGameState& State, const FUmFighter& Fighter, int32 BoostValue, TMap<FIntPoint, int32>* OutServerWouldAllow)
{
	// validator.ts:278-372 + executor:796-812:
	//  - allowance = movement + boostValue;
	//  - промежуточные клетки: только wall/obstacle (isValidPosition), двери и бойцы НЕ проверяются;
	//  - конечная клетка: не занята живым бойцом.
	// Клиентская строгость (ADR §5.7): основной набор — BFS с блокировкой живыми; разница — в ServerWouldAllow.
	FUmFighterMoveTargets Out;
	Out.FighterId = Fighter.Id;

	const int32 Allowance = FMath::Max(0, Fighter.Movement) + FMath::Max(0, BoostValue);
	const FIntPoint Start = FUmBoardGeometry::PositionOf(Fighter);
	const TSet<FIntPoint> Living = FUmBoardGeometry::LivingFighterCells(State, Fighter.Id);

	// строгий набор: сквозь бойцов нельзя, двери не учитываются (как сервер для манёвра)
	Out.Cells = FUmBoardGeometry::Reachable(State.BoardState, Start, Allowance, Living, /*bBlockClosedDoors*/ false);

	if (OutServerWouldAllow)
	{
		// серверный набор: бойцы прозрачны, но конечная должна быть свободна
		TMap<FIntPoint, int32> Loose = FUmBoardGeometry::Reachable(State.BoardState, Start, Allowance, TSet<FIntPoint>(), false);
		OutServerWouldAllow->Reset();
		for (const TPair<FIntPoint, int32>& It : Loose)
		{
			if (!Living.Contains(It.Key) && !Out.Cells.Contains(It.Key))
			{
				OutServerWouldAllow->Add(It.Key, It.Value);
			}
		}
	}
	return Out;
}

FUmFighterMoveTargets FUmLegalActions::PendingTargetsFor(const FUmGameState& State, const FUmPendingEffect& Pending, const FUmFighter& Fighter)
{
	// executor:485-520: клетка в границах, не obstacle/wall, не занята живым; MOVE — BFS за value ?? 1
	// с blockedPositions = чужие живые (R4 §2.10 «чужие живые — blockedPositions»). PLACE — любая свободная валидная.
	FUmFighterMoveTargets Out;
	Out.FighterId = Fighter.Id;
	const FIntPoint Start = FUmBoardGeometry::PositionOf(Fighter);

	if (Pending.Type == TEXT("MOVE"))
	{
		TSet<FIntPoint> Blocked;
		for (const FUmFighter& F : State.Fighters)
		{
			if (F.Id != Fighter.Id && F.OwnerId != Fighter.OwnerId && FUmRules::IsAlive(F))
			{
				Blocked.Add(FUmBoardGeometry::PositionOf(F));
			}
		}
		// TODO(parity): проверить по executor:503-520, блокирует ли BFS pending-MOVE и СВОИХ живых бойцов
		// (R4 §2.10 говорит «чужие живые»); при расхождении заменить фильтр на LivingFighterCells(State, Fighter.Id).
		TMap<FIntPoint, int32> Reach = FUmBoardGeometry::Reachable(State.BoardState, Start, FUmRules::PendingMoveDistance(Pending), Blocked, true);
		for (const TPair<FIntPoint, int32>& It : Reach)
		{
			if (FUmRules::IsPendingCellFree(State, It.Key, Fighter.Id))
			{
				Out.Cells.Add(It.Key, It.Value);
			}
		}
	}
	else if (Pending.Type == TEXT("PLACE"))
	{
		for (int32 Y = 0; Y < State.BoardState.Height; ++Y)
		{
			for (int32 X = 0; X < State.BoardState.Width; ++X)
			{
				const FIntPoint P(X, Y);
				if (P != Start && FUmRules::IsPendingCellFree(State, P, Fighter.Id))
				{
					Out.Cells.Add(P, FUmBoardGeometry::Manhattan(Start, P));
				}
			}
		}
	}
	return Out;
}

FUmLegalSet FUmLegalActions::Enumerate(const FUmGameState& State, const FString& MyUserId, const FUmAbilityTable& Abilities, bool bExternalGateOpen)
{
	FUmLegalSet Set;

	const FUmHandZone* Hand = FindHand(State, MyUserId);
	const bool bGameOver = State.Phase == TEXT("GAME_OVER");

	// Мои живые бойцы
	TArray<const FUmFighter*> MyLiving;
	const FUmFighter* MyHero = nullptr;
	for (const FUmFighter& F : State.Fighters)
	{
		if (F.OwnerId == MyUserId && FUmRules::IsAlive(F))
		{
			MyLiving.Add(&F);
			if (F.Type == TEXT("HERO") && MyHero == nullptr)
			{
				MyHero = &F;
			}
		}
	}

	// ------------------------------------------------------------------ внешний гейт
	if (!bExternalGateOpen)
	{
		const FText Busy = LOCTEXT("ExternalGate", "Подождите: выполняется предыдущее действие или синхронизация");
		for (const FGameplayTag& T : { FGameplayTag(UmTags::Action_Maneuver), FGameplayTag(UmTags::Action_MoveFighter), FGameplayTag(UmTags::Action_Attack),
		                               FGameplayTag(UmTags::Action_PlayDefense), FGameplayTag(UmTags::Action_PlayScheme), FGameplayTag(UmTags::Action_ResolveCombat),
		                               FGameplayTag(UmTags::Action_EndTurn), FGameplayTag(UmTags::Action_Pass), FGameplayTag(UmTags::Action_SetStance),
		                               FGameplayTag(UmTags::Action_Pending_Move), FGameplayTag(UmTags::Action_Pending_Place), FGameplayTag(UmTags::Action_Pending_ChooseOne) })
		{
			Reject(Set, T, UmReason::ExternalGateClosed, Busy);
		}
	}

	// ------------------------------------------------------------------ движение (maneuver / moveFighter)
	{
		FName Reason; FText Text;
		const bool bGate = ActionGate(State, MyUserId, Reason, Text);
		if (!bGate)
		{
			Reject(Set, UmTags::Action_Maneuver, Reason, Text);
			Reject(Set, UmTags::Action_MoveFighter, Reason, Text);
		}
		else if (MyLiving.Num() == 0)
		{
			Reject(Set, UmTags::Action_Maneuver, UmReason::NoLivingFighters, LOCTEXT("NoLiving", "Нет живых бойцов"));
			Reject(Set, UmTags::Action_MoveFighter, UmReason::NoLivingFighters, LOCTEXT("NoLiving", "Нет живых бойцов"));
		}
		else
		{
			bool bAnyMobile = false;
			for (const FUmFighter* F : MyLiving)
			{
				if (FUmRules::IsImmobilized(*F))
				{
					continue; // FIGHTER_IMMOBILIZED — боец пропускается, манёвр остальными возможен
				}
				bAnyMobile = true;

				// maneuver
				TMap<FIntPoint, int32> Loose;
				FUmFighterMoveTargets Man = ManeuverTargetsFor(State, *F, 0, &Loose);
				if (Loose.Num() > 0)
				{
					FUmFighterMoveTargets& SW = Set.ServerWouldAllow.AddDefaulted_GetRef();
					SW.FighterId = F->Id;
					SW.Cells = MoveTemp(Loose);
				}
				Set.ManeuverTargets.Add(MoveTemp(Man));

				// moveFighter: BFS за movement, блок — живые + закрытые двери (validator.ts:374-436)
				FUmFighterMoveTargets Mv;
				Mv.FighterId = F->Id;
				Mv.Cells = FUmBoardGeometry::Reachable(State.BoardState, FUmBoardGeometry::PositionOf(*F), FMath::Max(0, F->Movement),
					FUmBoardGeometry::LivingFighterCells(State, F->Id), true);
				Set.MoveTargets.Add(MoveTemp(Mv));
			}
			if (!bAnyMobile)
			{
				Reject(Set, UmTags::Action_Maneuver, UmReason::Immobilized, LOCTEXT("Immobilized", "Все бойцы обездвижены до конца хода"));
				Reject(Set, UmTags::Action_MoveFighter, UmReason::Immobilized, LOCTEXT("Immobilized", "Все бойцы обездвижены до конца хода"));
			}
			else
			{
				// Манёвр без движения (только добор) сервер принимает: `moves[]` может быть пустым (R4 §2.6.2 п.6
				// «манёвр без карты валиден»). TODO(parity): подтвердить живой проверкой, что `moves: []` не даёт EMPTY_PATH.
				Set.bCanManeuver = bExternalGateOpen;
				bool bAnyMove = false;
				for (const FUmFighterMoveTargets& T : Set.MoveTargets)
				{
					bAnyMove |= T.Cells.Num() > 0;
				}
				Set.bCanMoveFighter = bExternalGateOpen && bAnyMove;
				if (!bAnyMove)
				{
					Reject(Set, UmTags::Action_MoveFighter, UmReason::NoReachableCells, LOCTEXT("NoReach", "Нет достижимых клеток"));
				}
			}
		}
	}

	// ------------------------------------------------------------------ атака (validator.ts:135-217; executor:1008-1058)
	{
		FName Reason; FText Text;
		if (!ActionGate(State, MyUserId, Reason, Text))
		{
			Reject(Set, UmTags::Action_Attack, Reason, Text);
		}
		else
		{
			TArray<const FUmCard*> AttackCards;
			if (Hand)
			{
				for (const FUmCard& C : Hand->Cards)
				{
					if (FUmRules::IsAttackCard(C))
					{
						AttackCards.Add(&C);
					}
				}
			}
			if (AttackCards.Num() == 0)
			{
				Reject(Set, UmTags::Action_Attack, UmReason::NoAttackCards, LOCTEXT("NoAttackCards", "В руке нет карт атаки"));
			}
			else
			{
				for (const FUmFighter* Att : MyLiving)
				{
					for (const FUmFighter& Tgt : State.Fighters)
					{
						if (Tgt.OwnerId == MyUserId || !FUmRules::IsAlive(Tgt))
						{
							continue;
						}
						const EUmRangeVerdict Verdict = FUmRules::AttackRangeVerdict(State, *Att, Tgt, Abilities);
						if (Verdict == EUmRangeVerdict::OutOfRange)
						{
							// ADR §5.7: при отсутствии строки DT_AttackRange — не подсвечивать, но не блокировать клик;
							// клик по неподсвеченной цели обрабатывает FUmInputStateMachine (отправка как есть + тост).
							continue;
						}
						for (const FUmCard* Card : AttackCards)
						{
							bool bUnknownBanner = false;
							if (!FUmRules::BannerPermits(State, Card->BannerName, *Att, &bUnknownBanner))
							{
								continue; // BANNER_MISMATCH — сервер отклонит
							}
							FUmAttackOption& Opt = Set.Attacks.AddDefaulted_GetRef();
							Opt.AttackerId = Att->Id;
							Opt.CardId = Card->Id;
							Opt.TargetId = Tgt.Id;
							Opt.Range = Verdict;
							Opt.bBoostAllowed = FUmRules::BoostAllowed(*Card, *Att, EUmBoostRole::Attack, Abilities);
							Opt.bBannerWarning = bUnknownBanner;
						}
					}
				}
				if (Set.Attacks.Num() == 0)
				{
					Reject(Set, UmTags::Action_Attack, UmReason::NoTargetsInRange, LOCTEXT("NoTargets", "Нет целей в досягаемости"));
				}
				Set.bCanAttack = bExternalGateOpen && Set.Attacks.Num() > 0;
			}
		}
	}

	// ------------------------------------------------------------------ scheme (executor:1286-1392)
	{
		FName Reason; FText Text;
		if (!ActionGate(State, MyUserId, Reason, Text))
		{
			Reject(Set, UmTags::Action_PlayScheme, Reason, Text);
		}
		else if (Hand)
		{
			for (const FUmCard& C : Hand->Cards)
			{
				if (!FUmRules::IsSchemeCard(C))
				{
					continue;
				}
				// executor:1309-1322: если есть живые свои бойцы — нужен хотя бы один, проходящий banner
				bool bBannerOk = MyLiving.Num() == 0;
				for (const FUmFighter* F : MyLiving)
				{
					if (FUmRules::BannerPermits(State, C.BannerName, *F))
					{
						bBannerOk = true;
						break;
					}
				}
				if (bBannerOk)
				{
					Set.PlayableSchemes.Add(C.Id);
				}
			}
			if (Set.PlayableSchemes.Num() == 0)
			{
				Reject(Set, UmTags::Action_PlayScheme, UmReason::NoSchemeCards, LOCTEXT("NoScheme", "Нет играбельных карт SCHEME"));
			}
			Set.bCanScheme = bExternalGateOpen && Set.PlayableSchemes.Num() > 0;
		}
	}

	// ------------------------------------------------------------------ pass / endTurn (validator.ts:471-520; R4 §2.3)
	{
		FName Reason; FText Text;
		if (ActionGate(State, MyUserId, Reason, Text, /*bNeedsAction*/ true))
		{
			Set.bCanPass = bExternalGateOpen; // тратит действие, карту не сбрасывает — подпись «Пропустить действие» (ADR §5.7)
		}
		else
		{
			Reject(Set, UmTags::Action_Pass, Reason, Text);
		}
		// endTurn: без требования к actionsRemaining; фазы ACTION_MANEUVER/ACTION_ATTACK/TURN_END (validator.ts:476-480)
		if (ActionGate(State, MyUserId, Reason, Text, /*bNeedsAction*/ false) || (!bGameOver && State.CurrentTurnPlayerId == MyUserId && State.Phase == TEXT("TURN_END")))
		{
			Set.bCanEndTurn = bExternalGateOpen;
		}
		else
		{
			Reject(Set, UmTags::Action_EndTurn, Reason, Text);
		}
	}

	// ------------------------------------------------------------------ защита (game-turn.guard.ts:163-222; validator.ts:440-466)
	{
		const FUmGameStateMetadata& Meta = State.Metadata;
		if (State.Phase != TEXT("COMBAT") || !Meta.bHasCombatInfo)
		{
			Reject(Set, UmTags::Action_PlayDefense, UmReason::NotInCombat, LOCTEXT("NotInCombat", "Нет активного боя"));
		}
		else if (Meta.CombatInfo.DefenderId != MyUserId)
		{
			Reject(Set, UmTags::Action_PlayDefense, UmReason::NotDefender, LOCTEXT("NotDefender", "Защищается соперник"));
		}
		else if (Hand)
		{
			// banner — против атакованного бойца; фолбэк — первый боец защитника (R4 §2.7.3)
			const FUmFighter* Target = FindFighter(State, Meta.CombatInfo.TargetFighterId);
			if (Target == nullptr)
			{
				for (const FUmFighter& F : State.Fighters)
				{
					if (F.OwnerId == MyUserId) { Target = &F; break; }
				}
			}
			for (const FUmCard& C : Hand->Cards)
			{
				if (!FUmRules::IsDefenseCard(C))
				{
					continue;
				}
				bool bUnknownBanner = false;
				if (Target && !FUmRules::BannerPermits(State, C.BannerName, *Target, &bUnknownBanner))
				{
					continue;
				}
				FUmDefenseOption& D = Set.PlayableDefenses.AddDefaulted_GetRef();
				D.CardId = C.Id;
				D.bBoostAllowed = Target ? FUmRules::BoostAllowed(C, *Target, EUmBoostRole::Defense, Abilities) : false;
				D.bBannerWarning = bUnknownBanner;
			}
			if (Set.PlayableDefenses.Num() == 0)
			{
				Reject(Set, UmTags::Action_PlayDefense, UmReason::NoDefenseCards, LOCTEXT("NoDefense", "Нет карт защиты — можно только принять удар"));
			}
			Set.bCanDefend = bExternalGateOpen && Set.PlayableDefenses.Num() > 0;
		}
	}

	// ------------------------------------------------------------------ resolveCombat (game-turn.guard.ts:225-283; ADR §5.5, §5.7)
	{
		const FUmGameStateMetadata& Meta = State.Metadata;
		if (!FUmRules::IsCombatPhase(State.Phase) || !Meta.bHasCombatInfo)
		{
			Reject(Set, UmTags::Action_ResolveCombat, UmReason::NotInCombat, LOCTEXT("NotInCombat", "Нет активного боя"));
		}
		else
		{
			const FUmFighter* Attacker = FindFighter(State, Meta.CombatInfo.AttackerId);
			const bool bIAmAttacker = Attacker && Attacker->OwnerId == MyUserId;
			const bool bIAmDefender = Meta.CombatInfo.DefenderId == MyUserId;
			if (!bIAmAttacker && !bIAmDefender)
			{
				Reject(Set, UmTags::Action_ResolveCombat, UmReason::NotParticipant, LOCTEXT("NotParticipant", "Вы не участник боя"));
			}
			else if (bIAmAttacker && State.Phase == TEXT("COMBAT"))
			{
				// Сервер пустил бы (guard без проверки таймаута — R4 §4.4); клиент намеренно не предлагает (честная игра).
				Reject(Set, UmTags::Action_ResolveCombat, UmReason::AwaitingDefense, LOCTEXT("AwaitingDefense", "Ждём защиту соперника"));
			}
			else
			{
				// Защитник в COMBAT — «Без защиты»; любой участник в COMBAT_RESOLVE — «Разрешить бой»
				Set.bCanResolveCombat = bExternalGateOpen;
			}
		}
	}

	// ------------------------------------------------------------------ pending (executor:432-520; guard'ов фазы нет; G19)
	{
		for (const FUmPendingEffect& P : State.Metadata.PendingEffects)
		{
			if (P.PlayerId != MyUserId)
			{
				continue;
			}
			FUmPendingChoice& Choice = Set.MyPending.AddDefaulted_GetRef();
			Choice.Pending = P;
			if (P.Type == TEXT("CHOOSE_ONE"))
			{
				for (const FUmPendingOption& O : P.Options)
				{
					Choice.OptionIndices.Add(O.Index);
				}
			}
			else
			{
				for (const FUmFighter& F : State.Fighters)
				{
					if (FUmRules::FighterFitsPending(P, F, MyUserId))
					{
						Choice.EligibleFighterIds.Add(F.Id);
						Choice.Targets.Add(PendingTargetsFor(State, P, F));
					}
				}
			}
		}
		Set.bHasPending = Set.MyPending.Num() > 0;
		if (Set.bHasPending && State.Phase == TEXT("COMBAT"))
		{
			// ADR §5.5: resolvePendingEffect в COMBAT ломает auto-resolve (R3 §4.12) → блок до конца боя
			Set.bPendingBlockedByCombat = true;
			const FText T = LOCTEXT("PendingBlocked", "Отложенный эффект можно применить после боя");
			Reject(Set, UmTags::Action_Pending_Move, UmReason::PendingBlockedByCombat, T);
			Reject(Set, UmTags::Action_Pending_Place, UmReason::PendingBlockedByCombat, T);
			Reject(Set, UmTags::Action_Pending_ChooseOne, UmReason::PendingBlockedByCombat, T);
		}
		else if (!Set.bHasPending)
		{
			const FText T = LOCTEXT("NoPending", "Нет отложенных эффектов");
			Reject(Set, UmTags::Action_Pending_Move, UmReason::NoPending, T);
			Reject(Set, UmTags::Action_Pending_Place, UmReason::NoPending, T);
			Reject(Set, UmTags::Action_Pending_ChooseOne, UmReason::NoPending, T);
		}
	}

	// ------------------------------------------------------------------ стойки (executor:1898-1934; ADR §5.7 «setStance вне своего хода»)
	{
		FName Reason; FText Text;
		if (!ActionGate(State, MyUserId, Reason, Text, /*bNeedsAction*/ false))
		{
			Reject(Set, UmTags::Action_SetStance, Reason, Text);
		}
		else if (MyHero == nullptr)
		{
			Reject(Set, UmTags::Action_SetStance, UmReason::NoHero, LOCTEXT("NoHero", "У вас нет героя на доске"));
		}
		else
		{
			const FString Slug = MyHero->HeroSlug.IsEmpty() ? MyHero->HeroId : MyHero->HeroSlug;
			if (const FUmStanceOptionDtoList* List = Abilities.Stances.Find(Slug))
			{
				Set.Stances = List->Items;
			}
			Set.CurrentStanceId = Abilities.CurrentStanceId(State, MyUserId, Slug);
			if (Set.Stances.Num() == 0)
			{
				Reject(Set, UmTags::Action_SetStance, UmReason::NoStances, LOCTEXT("NoStances", "У героя нет стоек")); // WBP_StanceBar скрыт
			}
			Set.bCanSetStance = bExternalGateOpen && Set.Stances.Num() > 0;
		}
	}

	return Set;
}

#undef LOCTEXT_NAMESPACE

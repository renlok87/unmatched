// UmModel/Private/UmRules.cpp
// Зеркало точечных правил бэкенда (ссылки на файл:строку — у каждой функции).

#include "UmRules.h"
#include "UmBoardGeometry.h"
#include "Logging/LogMacros.h"

DEFINE_LOG_CATEGORY_STATIC(LogUmModel, Log, All);

// ============================================================================ FUmAbilityTable

FUmAbilityTable::FUmAbilityTable()
{
	// arthur.handler.ts:22-30 — `heroId: 'king-arthur', allowsAttackBoost: true`
	AttackBoostHeroSlugs.Add(TEXT("king-arthur"));
}

FString FUmAbilityTable::DefaultStanceId(const FString& HeroSlug) const
{
	// generic-hero-ability.handler.ts:100-103 — `(stances.find(s => s.default) ?? stances[0]).id`
	const FUmStanceOptionDtoList* List = Stances.Find(HeroSlug);
	if (List == nullptr || List->Items.Num() == 0)
	{
		return FString();
	}
	for (const FUmStanceOptionDto& S : List->Items)
	{
		if (S.bIsDefault)
		{
			return S.Id;
		}
	}
	return List->Items[0].Id;
}

FString FUmAbilityTable::CurrentStanceId(const FUmGameState& State, const FString& OwnerUserId, const FString& HeroSlug) const
{
	// generic-hero-ability.handler.ts:107-111
	if (const FString* Explicit = State.Metadata.HeroStances.Find(OwnerUserId))
	{
		return *Explicit;
	}
	return DefaultStanceId(HeroSlug);
}

bool FUmAbilityTable::FindEffectiveRange(const FString& HeroSlug, const FString& StanceId, int32& OutRange) const
{
	// generic-hero-ability.handler.ts:641-644: stanceCfg?.attackRange ?? config.attackRange
	const FUmAttackRangeRow* Base = nullptr;
	const FUmAttackRangeRow* ForStance = nullptr;
	for (const FUmAttackRangeRow& Row : Ranges)
	{
		if (Row.HeroSlug != HeroSlug)
		{
			continue;
		}
		if (Row.StanceId.IsEmpty())
		{
			Base = &Row;
		}
		else if (!StanceId.IsEmpty() && Row.StanceId == StanceId)
		{
			ForStance = &Row;
		}
	}
	const FUmAttackRangeRow* Chosen = ForStance ? ForStance : Base;
	if (Chosen == nullptr)
	{
		return false;
	}
	OutRange = Chosen->Range;
	return true;
}

// ============================================================================ фазы и экономика

bool FUmRules::IsActionPhase(const FString& Phase)
{
	return Phase == TEXT("ACTION_MANEUVER") || Phase == TEXT("ACTION_ATTACK");
}

bool FUmRules::IsCombatPhase(const FString& Phase)
{
	return Phase == TEXT("COMBAT") || Phase == TEXT("COMBAT_RESOLVE");
}

int32 FUmRules::ActionsRemaining(const FUmGameState& State)
{
	// game-state.model.ts:172-175 — отрицательное/мусор → 2; парсер уже выставил дефолт 2 при отсутствии поля
	const int32 Raw = State.Metadata.ActionsRemaining;
	return Raw < 0 ? 2 : Raw;
}

bool FUmRules::CanPlayerAct(const FUmGameState& State, const FString& UserId)
{
	// game-rules.validator.ts:219-227
	if (State.CurrentTurnPlayerId != UserId)
	{
		return false;
	}
	for (const FUmGameStatePlayer& P : State.Players)
	{
		if (P.UserId == UserId)
		{
			return P.bIsAlive;
		}
	}
	return false;
}

bool FUmRules::IsImmobilized(const FUmFighter& Fighter)
{
	// game-rules.validator.ts:300-305 — `effects.some(e => e.type === 'immobilized')`
	for (const FUmFighterEffect& E : Fighter.Effects)
	{
		if (E.Type == TEXT("immobilized"))
		{
			return true;
		}
	}
	return false;
}

bool FUmRules::IsAlive(const FUmFighter& Fighter)
{
	return Fighter.Health > 0 && !Fighter.bIsDefeated;
}

// ============================================================================ типы карт

bool FUmRules::IsAttackCard(const FUmCard& Card)
{
	return Card.CardType == TEXT("ATTACK") || Card.CardType == TEXT("VERSATILE") || Card.CardType == TEXT("UNIVERSAL");
}

bool FUmRules::IsDefenseCard(const FUmCard& Card)
{
	return Card.CardType == TEXT("DEFENSE") || Card.CardType == TEXT("VERSATILE") || Card.CardType == TEXT("UNIVERSAL");
}

bool FUmRules::IsSchemeCard(const FUmCard& Card)
{
	return Card.CardType == TEXT("SCHEME");
}

// ============================================================================ banner

FString FUmRules::Singularize(const FString& Word)
{
	// game-rules.validator.ts:592-593:
	//   w.replace(/ies$/, 'y').replace(/ves$/, 'f').replace(/([^s])s$/, '$1')
	// Порядок важен: три замены применяются последовательно к результату предыдущей.
	FString W = Word;
	if (W.EndsWith(TEXT("ies")))
	{
		W.LeftInline(W.Len() - 3);
		W += TEXT("y");
	}
	if (W.EndsWith(TEXT("ves")))
	{
		W.LeftInline(W.Len() - 3);
		W += TEXT("f");
	}
	// `([^s])s$` — последняя буква 's', предпоследняя есть и не 's' («dogs» → «dog», «boss» остаётся)
	if (W.Len() >= 2 && W[W.Len() - 1] == TEXT('s') && W[W.Len() - 2] != TEXT('s'))
	{
		W.LeftInline(W.Len() - 1);
	}
	return W;
}

namespace
{
	/** `full.replace(/\s+\d+$/, '')` — срез числового суффикса вида « 2». */
	FString StripNumericSuffix(const FString& Full)
	{
		int32 End = Full.Len();
		// цифры
		int32 I = End;
		while (I > 0 && FChar::IsDigit(Full[I - 1]))
		{
			--I;
		}
		if (I == End)
		{
			return Full; // цифр в конце нет
		}
		// хотя бы один пробельный символ перед цифрами
		int32 J = I;
		while (J > 0 && FChar::IsWhitespace(Full[J - 1]))
		{
			--J;
		}
		if (J == I)
		{
			return Full; // «Harpy2» без пробела — regex не матчит
		}
		return Full.Left(J);
	}

	/** `split(/\s+/)` без пустых элементов. */
	void SplitWords(const FString& S, TArray<FString>& Out)
	{
		Out.Reset();
		FString Cur;
		for (const TCHAR C : S)
		{
			if (FChar::IsWhitespace(C))
			{
				if (!Cur.IsEmpty())
				{
					Out.Add(Cur);
					Cur.Reset();
				}
			}
			else
			{
				Cur.AppendChar(C);
			}
		}
		if (!Cur.IsEmpty())
		{
			Out.Add(Cur);
		}
	}
}

bool FUmRules::BannerAllows(const FString& Banner, const FString& FighterName)
{
	// game-rules.validator.ts:591-603
	const FString B = Singularize(Banner.TrimStartAndEnd().ToLower());
	const FString Full = FighterName.TrimStartAndEnd().ToLower();
	const FString Base = StripNumericSuffix(Full);
	if (B == Singularize(Full) || B == Singularize(Base))
	{
		return true;
	}
	TArray<FString> Words;
	SplitWords(Base, Words);
	for (const FString& W : Words)
	{
		if (Singularize(W) == B)
		{
			return true;
		}
	}
	return false;
}

bool FUmRules::BannerPermits(const FUmGameState& State, const FString& Banner, const FUmFighter& Fighter, bool* bOutUnknownBanner)
{
	// game-rules.validator.ts:559-585
	if (bOutUnknownBanner)
	{
		*bOutUnknownBanner = false;
	}
	const FString Trimmed = Banner.TrimStartAndEnd();
	if (Trimmed.IsEmpty() || Trimmed.ToLower() == TEXT("any"))
	{
		return true;
	}
	if (BannerAllows(Trimmed, Fighter.Name))
	{
		return true;
	}
	for (const FUmFighter& F : State.Fighters)
	{
		if (BannerAllows(Trimmed, F.Name))
		{
			return false; // банер известен в партии, но не этот боец → BANNER_MISMATCH
		}
	}
	UE_LOG(LogUmModel, Warning, TEXT("bannerName '%s' не матчит ни одного бойца партии — разрешено (грязные данные?)"), *Trimmed);
	if (bOutUnknownBanner)
	{
		*bOutUnknownBanner = true;
	}
	return true;
}

// ============================================================================ BOOST

bool FUmRules::BoostAllowed(const FUmCard& PlayedCard, const FUmFighter& Fighter, EUmBoostRole Role, const FUmAbilityTable& Abilities)
{
	// game-action-executor.service.ts:136-154
	for (const FUmCardEffect& E : PlayedCard.Effects)
	{
		if (E.IsBoostFromHand())
		{
			return true;
		}
	}
	const FString Slug = Fighter.HeroSlug.IsEmpty() ? Fighter.HeroId : Fighter.HeroSlug; // `fighter.heroSlug ?? fighter.heroId`
	return Role == EUmBoostRole::Attack
		? Abilities.AttackBoostHeroSlugs.Contains(Slug)
		: Abilities.DefenseBoostHeroSlugs.Contains(Slug);
}

bool FUmRules::CanBoostWith(const FUmCard& PlayedCard, const FUmCard& BoostCard)
{
	return !BoostCard.Id.IsEmpty() && BoostCard.Id != PlayedCard.Id;
}

// ============================================================================ досягаемость

EUmRangeVerdict FUmRules::AttackRangeVerdict(const FUmGameState& State, const FUmFighter& Attacker, const FUmFighter& Target, const FUmAbilityTable& Abilities)
{
	// game-action-executor.service.ts:1008-1058
	const FIntPoint A = FUmBoardGeometry::PositionOf(Attacker);
	const FIntPoint T = FUmBoardGeometry::PositionOf(Target);

	if (FUmBoardGeometry::IsAdjacent(A, T))
	{
		return EUmRangeVerdict::Adjacent;
	}
	// getFighterAttackType: парсер уже нормализовал 'range'/мусор → 'melee' (fighter.model.ts:96-104)
	if (Attacker.AttackType == TEXT("ranged") && FUmBoardGeometry::SameLegacyZone(State.BoardState, A, T))
	{
		return EUmRangeVerdict::SameZone;
	}
	const FString Slug = Attacker.HeroSlug.IsEmpty() ? Attacker.HeroId : Attacker.HeroSlug;
	const FString Stance = Abilities.CurrentStanceId(State, Attacker.OwnerId, Slug);
	int32 EffectiveRange = 0;
	if (Abilities.FindEffectiveRange(Slug, Stance, EffectiveRange) && FUmBoardGeometry::Manhattan(A, T) <= EffectiveRange)
	{
		return EUmRangeVerdict::AbilityRange;
	}
	return EUmRangeVerdict::OutOfRange;
}

bool FUmRules::IsInAttackRange(const FUmGameState& State, const FUmFighter& Attacker, const FUmFighter& Target, const FUmAbilityTable& Abilities)
{
	return AttackRangeVerdict(State, Attacker, Target, Abilities) != EUmRangeVerdict::OutOfRange;
}

// ============================================================================ pending

bool FUmRules::FighterFitsPending(const FUmPendingEffect& Pending, const FUmFighter& Fighter, const FString& MyUserId)
{
	// game-action-executor.service.ts:466-482
	if (!IsAlive(Fighter))
	{
		return false;
	}
	const bool bMine = Fighter.OwnerId == MyUserId;
	if (Pending.bTargetsOpponent ? bMine : !bMine)
	{
		return false; // «Эффект двигает не этого бойца»
	}
	if (!Pending.FighterName.IsEmpty() && !BannerAllows(Pending.FighterName, Fighter.Name))
	{
		return false; // «Эффект двигает только «…»»
	}
	return true;
}

bool FUmRules::IsPendingCellFree(const FUmGameState& State, const FIntPoint& P, const FString& MovingFighterId)
{
	// game-action-executor.service.ts:485-502 — границы, не obstacle/wall, не занята живым
	if (!FUmBoardGeometry::IsValidPosition(State.BoardState, P))
	{
		return false;
	}
	return !FUmBoardGeometry::IsOccupiedByLiving(State, P, MovingFighterId);
}

int32 FUmRules::PendingMoveDistance(const FUmPendingEffect& Pending)
{
	// `pending.value ?? 1` (R4 §2.10); FUmPendingEffect::Value = 1 по умолчанию (candidate-1 §3.4.4)
	return FMath::Max(1, Pending.Value);
}

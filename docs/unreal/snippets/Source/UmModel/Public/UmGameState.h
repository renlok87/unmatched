// UmModel/Public/UmGameState.h
// Wire-модель JSON-состояния GameState (ярус 2 двухфазного парсинга — ADR §5.2; таблица классов ADR §4.2 «UmGameState.h»).
//
// Что это: точная проекция engine-формы GameState (backend/src/game-engine/models/*.ts), которую сервер отдаёт в
// `GameStateResponse.state`, `GameMutationResult.state` (полная, с decks/discardPiles) и в пяти строках подписки
// `gameStateUpdated` (без decks/discardPiles) — R3 §2.9, §2.11; R4 §2.5.6.
//
// Конвенции (ADR §3.6): USTRUCT wire-состояния — `FUm<Name>` без суффикса; UPROPERTY — PascalCase, сопоставляется с camelCase-ключом
// JSON регистронезависимо (FJsonObjectConverter, см. UmDto.h). Поля с провода — без префикса `b` (`IsDefeated` ↔ "isDefeated");
// поля, вычисляемые парсером, — с префиксом `b` (`bHasCombatInfo`, `bHidden`), в JSON их ключей нет.
// Wire-enum'ы — FString + аксессор `Get*()` через UmEnums::Parse<E> (толерантно).
// Серверные дефолты зашиты в значения по умолчанию полей (ADR §5.2): Movement = 2, AttackType = "melee", ActionsRemaining = 2,
// флаги *ThisTurn = false, MaxSize = 7, PendingEffect.Value = 1, ChooseCount = 1.
// Отсутствующие числа карт — `-1` (ADR §4.2 FUmCard).
//
// Заполняется ТОЛЬКО через FUmGameStateParser (UmGameStateParser.h): конвертер + «ремонт» по DOM
// (cells[y][x] → Rows, строковые handZones.cards, флаги bHas*, RawJson эффектов, отчёт FUmParseReport).

#pragma once

#include "CoreMinimal.h"
#include "JsonObjectWrapper.h"
#include "UmDto.h"
#include "UmEnums.h"

#include "UmGameState.generated.h"

// =====================================================================================================================
// Примитивы
// =====================================================================================================================

/** Position — fighter.model.ts:19-22. Координаты клетки доски: x — столбец, y — строка (cells[y][x], R3 §2.9.6). */
USTRUCT()
struct UMMODEL_API FUmPosition
{
	GENERATED_BODY()

	UPROPERTY() int32 X = 0; // источник: Position.x
	UPROPERTY() int32 Y = 0; // источник: Position.y

	FIntPoint ToIntPoint() const { return FIntPoint(X, Y); }
	bool operator==(const FUmPosition& Other) const { return X == Other.X && Y == Other.Y; }
	bool operator!=(const FUmPosition& Other) const { return !(*this == Other); }
};

// =====================================================================================================================
// Бойцы и игроки
// =====================================================================================================================

/** FighterEffect — fighter.model.ts:27-33 (R3 §2.9.3): { type, value?, duration?: 'permanent'|'turn'|'round', expiresAt?, source? }. */
USTRUCT()
struct UMMODEL_API FUmFighterEffect
{
	GENERATED_BODY()

	UPROPERTY() FString Type;       // источник: FighterEffect.type (свободная строка движка)
	UPROPERTY() int32 Value = 0;    // источник: FighterEffect.value? (отсутствует → 0)
	UPROPERTY() FString Duration;   // источник: FighterEffect.duration? — permanent | turn | round
	UPROPERTY() int32 ExpiresAt = -1; // источник: FighterEffect.expiresAt? (−1 = отсутствует)
	UPROPERTY() FString Source;     // источник: FighterEffect.source?

	EUmEffectDuration GetDuration() const { return UmEnums::ParseEffectDuration(Duration); }
};

/** Fighter — fighter.model.ts:38-62; R3 §2.9.3; R4 §2.5.3. */
USTRUCT()
struct UMMODEL_API FUmFighter
{
	GENERATED_BODY()

	UPROPERTY() FString Id;        // источник: Fighter.id — "f-<seat>-hero" / "f-<seat>-sk<i>" (game-initialization.service.ts:140,154)
	UPROPERTY() FString OwnerId;   // источник: Fighter.ownerId — userId
	UPROPERTY() FString HeroId;    // источник: Fighter.heroId — Prisma cuid героя
	UPROPERTY() FString Name;      // источник: Fighter.name
	UPROPERTY() FString Type;      // источник: Fighter.type — HERO | MINION | HUGE
	UPROPERTY() int32 Health = 0;  // источник: Fighter.health
	UPROPERTY() int32 MaxHealth = 0; // источник: Fighter.maxHealth
	UPROPERTY() FUmPosition Position; // источник: Fighter.position
	UPROPERTY() TArray<FUmFighterEffect> Effects; // источник: Fighter.effects
	UPROPERTY() bool HasSidekick = false; // источник: Fighter.hasSidekick
	UPROPERTY() TArray<FString> SidekickIds; // источник: Fighter.sidekickIds?
	UPROPERTY() bool IsDefeated = false;  // источник: Fighter.isDefeated?
	UPROPERTY() int32 Movement = 2;       // источник: Fighter.movement? — DEFAULT_FIGHTER_MOVEMENT = 2 (fighter.model.ts:65-73)
	UPROPERTY() FString AttackType = TEXT("melee"); // источник: Fighter.attackType? — melee | ranged; мусор → melee (fighter.model.ts:90-104)
	UPROPERTY() FString HeroSlug;         // источник: Fighter.heroSlug? — ключ heroStances(heroSlug) и DT_AttackRange (ADR §3.6)

	EUmFighterType GetType() const { return UmEnums::ParseFighterType(Type); }
	EUmAttackType GetAttackType() const { return UmEnums::ParseAttackType(AttackType); }
	/** Серверная семантика getFighterMovement: мусор/≤0 → 2. */
	int32 GetMovement() const { return Movement > 0 ? Movement : 2; }
	bool IsAlive() const { return !IsDefeated && Health > 0; }
	bool IsHero() const { return GetType() == EUmFighterType::Hero; }
	/** Есть эффект обездвиживания (движок: "Боец обездвижен до конца хода (эффект карты)" — R3 §2.7.3).
	 *  Точная строка FighterEffect.type для IMMOBILIZE в research не зафиксирована — сравнение по подстроке "immobil"; требует живой проверки. */
	bool IsImmobilized() const
	{
		for (const FUmFighterEffect& Effect : Effects)
		{
			if (Effect.Type.Contains(TEXT("immobil"), ESearchCase::IgnoreCase)) { return true; }
		}
		return false;
	}
};

/** GameStatePlayer — game-state.model.ts:60-67; R3 §2.9.2. */
USTRUCT()
struct UMMODEL_API FUmGameStatePlayer
{
	GENERATED_BODY()

	UPROPERTY() FString UserId;    // источник: GameStatePlayer.userId
	UPROPERTY() FString HeroId;    // источник: GameStatePlayer.heroId — Prisma cuid (не slug)
	UPROPERTY() int32 Health = 0;  // источник: GameStatePlayer.health
	UPROPERTY() int32 MaxHealth = 0; // источник: GameStatePlayer.maxHealth
	UPROPERTY() TArray<FString> FighterIds; // источник: GameStatePlayer.fighterIds — [heroFighterId, ...sidekickIds]
	UPROPERTY() bool IsAlive = true; // источник: GameStatePlayer.isAlive
};

// =====================================================================================================================
// Карты
// =====================================================================================================================

/** CardEffect — card.model.ts:50-84; R3 §2.9.4; R4 §2.5.4.
 *  Клиент читает type/boostSource/text/optional (решение «показывать ли слот BOOST», лог) — К1 §3.4.1 п.6;
 *  вложенные структуры (when, count, options[].effects) доступны через RawJson и GetOptionEffects(). */
USTRUCT()
struct UMMODEL_API FUmCardEffect
{
	GENERATED_BODY()

	UPROPERTY() FString Id;           // источник: CardEffect.id
	UPROPERTY() FString Type;         // источник: CardEffect.type — EffectType (21)
	UPROPERTY() FString Timing;       // источник: CardEffect.timing — engine EffectTiming (8)
	UPROPERTY() FString Target;       // источник: CardEffect.target? — EffectTarget (10)
	UPROPERTY() int32 Value = 0;      // источник: CardEffect.value?
	UPROPERTY() FString Condition;    // источник: CardEffect.condition? (legacy-строка)
	UPROPERTY() bool Optional = false; // источник: CardEffect.optional? (ADR называет bOptional; без префикса ради автосопоставления ключа)
	UPROPERTY() FString FighterName;  // источник: CardEffect.fighterName?
	UPROPERTY() FString BoostSource;  // источник: CardEffect.boostSource? — PLAYER_CHOICE_HAND | SELF_DECK_TOP | OPPONENT_RANDOM_HAND
	UPROPERTY() bool Blind = false;   // источник: CardEffect.blind? (ADR: bBlind)
	UPROPERTY() int32 ChooseCount = 1; // источник: CardEffect.chooseCount? (default 1)
	UPROPERTY() FString Text;         // источник: CardEffect.text?
	UPROPERTY() FString Source;       // источник: CardEffect.source? — parser | manual
	UPROPERTY() int32 ParserVersion = 0; // источник: CardEffect.parserVersion?

	/** Парсер: options[].label (CHOOSE_ONE). */
	UPROPERTY() TArray<FString> OptionLabels;
	/** Парсер: исходный объект эффекта целиком (when, count, options[].effects, …) — R8 §2.4 FJsonObjectWrapper. */
	UPROPERTY() FJsonObjectWrapper RawJson;

	EUmEffectType GetType() const { return UmEnums::ParseEffectType(Type); }
	EUmEffectTiming GetTiming() const { return UmEnums::ParseEffectTiming(Timing); }
	EUmEffectTarget GetTarget() const { return UmEnums::ParseEffectTarget(Target); }
	EUmBoostSource GetBoostSource() const { return UmEnums::ParseBoostSource(BoostSource); }
	/** BOOST из руки: тип BOOST и источник PLAYER_CHOICE_HAND либо не указан (R4 §2.7.2; ADR §4.2). */
	bool IsBoostFromHand() const
	{
		return GetType() == EUmEffectType::Boost
			&& (BoostSource.IsEmpty() || GetBoostSource() == EUmBoostSource::PlayerChoiceHand);
	}
	/** Рекурсия CHOOSE_ONE: options[OptionIndex].effects из RawJson → TArray<FUmCardEffect> (через парсер).
	 *  Реализовано в UmGameStateParser.cpp (UHT запрещает TArray<Self> как UPROPERTY — UhtArrayProperty.cs:220). */
	TArray<FUmCardEffect> GetOptionEffects(int32 OptionIndex) const;
};

/** Card / HandCard — card.model.ts:25-48,282-284; R3 §2.9.4; фильтрация чужих карт — R3 §2.10. */
USTRUCT()
struct UMMODEL_API FUmCard
{
	GENERATED_BODY()

	UPROPERTY() FString Id;        // источник: Card.id — instance id "<prismaCardId>::<copy>" — именно его слать в cardId/boostCardId (R3 §3.10)
	UPROPERTY() FString CardId;    // источник: Card.cardId — Prisma cuid шаблона (контент FUmCardDto.Id)
	UPROPERTY() FString Name;      // источник: Card.name — у чужих "???"
	UPROPERTY() FString NameEn;    // источник: Card.nameEn — у чужих "Hidden"
	UPROPERTY() FString NameRu;    // источник: Card.nameRu — у чужих "Скрыто"
	UPROPERTY() FString CardType;  // источник: Card.cardType — ATTACK|DEFENSE|SCHEME|UNIVERSAL|VERSATILE|MANEUVER
	UPROPERTY() int32 AttackValue = -1;  // источник: Card.attackValue? (−1 = отсутствует; у чужих удалён)
	UPROPERTY() int32 DefenseValue = -1; // источник: Card.defenseValue?
	UPROPERTY() int32 BoostValue = -1;   // источник: Card.boostValue?
	UPROPERTY() TArray<FUmCardEffect> Effects; // источник: Card.effects? (у чужих удалены)
	UPROPERTY() FString Text;      // источник: Card.text? (у чужих удалён)
	UPROPERTY() FString BannerName; // источник: Card.bannerName? — 'Any'/пусто = любой боец; у чужих НЕ удаляется (не использовать в UI — R3 §3.13)
	UPROPERTY() bool IsVisible = false; // источник: HandCard.isVisible — НЕ признак «своя карта» (R3 §2.9.4)

	/** Парсер: Name == "???" (обезличенная чужая карта — game-state.service.ts:503-524). */
	UPROPERTY() bool bHidden = false;

	EUmCardType GetCardType() const { return UmEnums::ParseCardType(CardType); }
	bool HasAttackValue() const { return AttackValue >= 0; }
	bool HasDefenseValue() const { return DefenseValue >= 0; }
	bool HasBoostValue() const { return BoostValue >= 0; }
	int32 GetBoostValueOrZero() const { return BoostValue >= 0 ? BoostValue : 0; }
	/** Банер «любой боец»: пусто или "Any" (game-rules.validator.ts:559-585). */
	bool IsBannerAny() const { return BannerName.IsEmpty() || BannerName.Equals(TEXT("Any"), ESearchCase::IgnoreCase); }
	/** Можно играть как атаку: ATTACK/VERSATILE (validator :203). */
	bool CanAttack() const { const EUmCardType T = GetCardType(); return T == EUmCardType::Attack || T == EUmCardType::Versatile; }
	/** Можно играть как защиту: DEFENSE/VERSATILE/UNIVERSAL (validator :460). */
	bool CanDefend() const { const EUmCardType T = GetCardType(); return T == EUmCardType::Defense || T == EUmCardType::Versatile || T == EUmCardType::Universal; }
	bool IsScheme() const { return GetCardType() == EUmCardType::Scheme; }
	/** Есть эффект BOOST из руки → показывать слот boost-карты (R4 §2.7.2). */
	bool HasHandBoostEffect() const
	{
		for (const FUmCardEffect& Effect : Effects) { if (Effect.IsBoostFromHand()) { return true; } }
		return false;
	}
};

/** Обёртка массива карт для TMap-значений (discardPiles: Record<userId, Card[]>) — ADR §4.2 FUmCardList. */
USTRUCT()
struct UMMODEL_API FUmCardList
{
	GENERATED_BODY()

	UPROPERTY() TArray<FUmCard> Cards;
};

/** DeckState — card.model.ts:289-293; R3 §2.9.5. drawPile — ПОЛНЫЕ объекты карт; чужой drawPile клиентом не читается (утечка — R3 §4.11, ADR §5.2). */
USTRUCT()
struct UMMODEL_API FUmDeckState
{
	GENERATED_BODY()

	UPROPERTY() TArray<FUmCard> Cards;    // источник: DeckState.cards — полный список колоды
	UPROPERTY() TArray<FUmCard> DrawPile; // источник: DeckState.drawPile
	UPROPERTY() FUmCard TopCard;          // источник: DeckState.topCard? (у чужой колоды удалён)
	/** Парсер: topCard присутствует. */
	UPROPERTY() bool bHasTopCard = false;

	int32 DrawPileCount() const { return DrawPile.Num(); }
};

/** HandZone — card.model.ts:298-301; R3 §2.9.5. `cards` может прийти JSON-строкой → второй парс (R6 §2.6). */
USTRUCT()
struct UMMODEL_API FUmHandZone
{
	GENERATED_BODY()

	UPROPERTY() TArray<FUmCard> Cards; // источник: HandZone.cards
	UPROPERTY() int32 MaxSize = 7;     // источник: HandZone.maxSize (= 7 при инициализации, game-initialization.service.ts:40,227)

	const FUmCard* FindCard(const FString& InstanceOrCardId) const
	{
		for (const FUmCard& Card : Cards)
		{
			if (Card.Id == InstanceOrCardId || Card.CardId == InstanceOrCardId) { return &Card; }
		}
		return nullptr;
	}
};

// =====================================================================================================================
// Доска
// =====================================================================================================================

/** Cell — board.model.ts:24-35; R3 §2.9.6; R4 §2.5.5. */
USTRUCT()
struct UMMODEL_API FUmCell
{
	GENERATED_BODY()

	UPROPERTY() FString Type;   // источник: Cell.type — normal | wall | obstacle | door | zone-line
	UPROPERTY() int32 X = 0;    // источник: Cell.x
	UPROPERTY() int32 Y = 0;    // источник: Cell.y
	UPROPERTY() FString Zone;   // источник: Cell.zone? — deprecated, первая зона (lowercase); ranged-атака — по ней (R4 §2.6.1)
	UPROPERTY() TArray<FString> Zones; // источник: Cell.zones? — 1–2 зоны (lowercase)
	UPROPERTY() bool IsOpen = false;      // источник: Cell.isOpen?
	UPROPERTY() bool IsHighGround = false; // источник: Cell.isHighGround?

	EUmCellType GetType() const { return UmEnums::ParseCellType(Type); }
	/** getCellZones: zones → fallback [zone] → [] (board.model.ts:41-45). */
	TArray<FString> GetZoneStrings() const
	{
		if (Zones.Num() > 0) { return Zones; }
		TArray<FString> Out;
		if (!Zone.IsEmpty()) { Out.Add(Zone); }
		return Out;
	}
	TArray<EUmZone> GetZones() const
	{
		TArray<EUmZone> Out;
		for (const FString& Z : GetZoneStrings()) { Out.Add(UmEnums::ParseZone(Z)); }
		return Out;
	}
	/** Legacy-зона (первая): Zone, иначе Zones[0]; Unknown если нет. */
	EUmZone GetLegacyZone() const
	{
		if (!Zone.IsEmpty()) { return UmEnums::ParseZone(Zone); }
		return Zones.Num() > 0 ? UmEnums::ParseZone(Zones[0]) : EUmZone::Unknown;
	}
	/** Проходимость по adjacency.service.ts:90-150 (ADR §4.3 FUmBoardGeometry): непроходимы wall/obstacle/door && !isOpen. Занятость бойцами — отдельно. */
	bool IsPassable() const
	{
		switch (GetType())
		{
		case EUmCellType::Wall:
		case EUmCellType::Obstacle: return false;
		case EUmCellType::Door: return IsOpen;
		default: return true;
		}
	}
};

/** Строка клеток (cells[y]) — обёртка, т.к. TArray<TArray<…>> недопустим как UPROPERTY. */
USTRUCT()
struct UMMODEL_API FUmCellRow
{
	GENERATED_BODY()

	UPROPERTY() TArray<FUmCell> Cells; // cells[y][x]
};

/** BoardState — board.model.ts:12-20; R3 §2.9.6. Индексация cells[y][x]; ключ дверей/тумана "<x>:<y>" (board.model.ts:110-112). */
USTRUCT()
struct UMMODEL_API FUmBoardState
{
	GENERATED_BODY()

	UPROPERTY() int32 Width = 20;   // источник: BoardState.width (fallback 20×20 — game-initialization.service.ts:43,277-300)
	UPROPERTY() int32 Height = 20;  // источник: BoardState.height
	UPROPERTY() TArray<FUmCellRow> Rows; // парсер: BoardState.cells[y][x]
	UPROPERTY() TMap<FString, bool> Doors; // источник: BoardState.doors — Record<"x:y", boolean>
	UPROPERTY() TMap<FString, bool> Fog;   // источник: BoardState.fog — всегда {} по коду (R3 §2.9.6)
	UPROPERTY() FJsonObjectWrapper Tokens; // источник: BoardState.tokens — Record<string, any>, всегда {} (R3 §2.9.6)

	static FString CellKey(int32 X, int32 Y) { return FString::Printf(TEXT("%d:%d"), X, Y); }
	bool IsInside(int32 X, int32 Y) const { return X >= 0 && Y >= 0 && X < Width && Y < Height; }
	const FUmCell* FindCell(int32 X, int32 Y) const
	{
		if (!Rows.IsValidIndex(Y) || !Rows[Y].Cells.IsValidIndex(X)) { return nullptr; }
		return &Rows[Y].Cells[X];
	}
	/** Дверь по ключу "x:y": есть ли запись и открыта ли (validateToggleDoor: "No door at (x, y)" — game-rules.validator.ts:546). */
	bool HasDoor(int32 X, int32 Y) const { return Doors.Contains(CellKey(X, Y)); }
	bool IsDoorOpen(int32 X, int32 Y) const { const bool* bOpen = Doors.Find(CellKey(X, Y)); return bOpen && *bOpen; }
};

// =====================================================================================================================
// Метаданные: бой, отложенные эффекты, стойки
// =====================================================================================================================

/** CombatState (engine, metadata.combatInfo) — game-state.model.ts:73-84; R3 §2.9.8; R4 §2.5.2.
 *  ВНИМАНИЕ: attackerId — id БОЙЦА, defenderId — userId (R3 §3.9). timeoutAt никогда не выставляется — дедлайн = startedAt + 30 с (R3 §4.2). */
USTRUCT()
struct UMMODEL_API FUmCombatState
{
	GENERATED_BODY()

	UPROPERTY() FString AttackerId;      // источник: CombatState.attackerId — id бойца-атакующего
	UPROPERTY() FString DefenderId;      // источник: CombatState.defenderId — userId защитника (target.ownerId)
	UPROPERTY() FString TargetFighterId; // источник: CombatState.targetFighterId? (легаси-сейвы без поля → первый боец защитника)
	UPROPERTY() FString AttackerCardId;  // источник: CombatState.attackerCardId — instance id
	UPROPERTY() FString DefenderCardId;  // источник: CombatState.defenderCardId? — после playDefense
	UPROPERTY() int32 AttackValue = 0;   // источник: CombatState.attackValue — значение карты + boost (до модификаторов)
	UPROPERTY() int32 DefenseValue = 0;  // источник: CombatState.defenseValue — 0 до защиты
	UPROPERTY() FUmDateTime StartedAt;   // источник: CombatState.startedAt — ISO-строка (ADR: FDateTime; обёрнут в FUmDateTime ради bSet — уточнение)
	UPROPERTY() FUmDateTime TimeoutAt;   // источник: CombatState.timeoutAt? — в коде никогда не пишется

	/** Парсер: defenderCardId присутствует и непуст. */
	UPROPERTY() bool bHasDefenderCard = false;
	/** Парсер: targetFighterId присутствует. */
	UPROPERTY() bool bHasTargetFighterId = false;

	bool HasTimeoutAt() const { return TimeoutAt.bSet; }
};

/** PendingEffect.options[] — game-state.model.ts:132-163; R4 §2.10: { index, label }. */
USTRUCT()
struct UMMODEL_API FUmPendingOption
{
	GENERATED_BODY()

	UPROPERTY() int32 Index = 0;  // источник: option.index → ResolvePendingEffectDto.optionIndex
	UPROPERTY() FString Label;    // источник: option.label
};

/** PendingEffect — game-state.model.ts:132-163; R3 §2.9.9; R4 §2.10. Резолв — mutation resolvePendingEffect (без фазового guard'а). */
USTRUCT()
struct UMMODEL_API FUmPendingEffect
{
	GENERATED_BODY()

	UPROPERTY() FString Id;          // источник: PendingEffect.id → effectId ("<effect.id>-p<n>", "ability-<heroId>-move-p<n>")
	UPROPERTY() FString Type;        // источник: PendingEffect.type — MOVE | PLACE | CHOOSE_ONE
	UPROPERTY() FString PlayerId;    // источник: PendingEffect.playerId — чей выбор (userId)
	UPROPERTY() int32 Value = 1;     // источник: PendingEffect.value? — дистанция MOVE (сервер: value ?? 1 — R4 §2.10)
	UPROPERTY() FString FighterName; // источник: PendingEffect.fighterName? — ограничение бойца (bannerAllows)
	UPROPERTY() bool TargetsOpponent = false; // источник: PendingEffect.targetsOpponent? — двигается боец противника
	UPROPERTY() FString Text;        // источник: PendingEffect.text?
	UPROPERTY() TArray<FUmPendingOption> Options; // источник: PendingEffect.options? (CHOOSE_ONE)
	UPROPERTY() int32 ChooseCount = 1; // источник: PendingEffect.chooseCount? (default 1)
	UPROPERTY() FUmCard Card;        // источник: PendingEffect.card? — карта-источник
	/** Парсер: card присутствует. */
	UPROPERTY() bool bHasCard = false;
	/** Парсер: исходный объект (в т.ч. optionEffects: CardEffect[][]). */
	UPROPERTY() FJsonObjectWrapper RawJson;

	EUmPendingEffectType GetType() const { return UmEnums::ParsePendingEffectType(Type); }
	bool IsChooseOne() const { return GetType() == EUmPendingEffectType::ChooseOne; }
	bool RequiresFighterAndCell() const { const EUmPendingEffectType T = GetType(); return T == EUmPendingEffectType::Move || T == EUmPendingEffectType::Place; }
	/** Шаги для MOVE: value ?? 1 (executor: BFS-достижимость за value шагов — R4 §2.10). */
	int32 GetMoveDistance() const { return Value > 0 ? Value : 1; }
	/** optionEffects[OptionIndex] из RawJson (параллельно options) — реализовано в UmGameStateParser.cpp. */
	TArray<FUmCardEffect> GetOptionEffects(int32 OptionIndex) const;
};

/** GameStateMetadata — game-state.model.ts:90-130; R3 §2.9.7; R4 §2.5.1. */
USTRUCT()
struct UMMODEL_API FUmGameStateMetadata
{
	GENERATED_BODY()

	UPROPERTY() FUmDateTime LastActionAt; // источник: metadata.lastActionAt — ISO 8601
	UPROPERTY() FString LastActionBy;     // источник: metadata.lastActionBy — userId | "system"
	UPROPERTY() int32 Version = 0;        // источник: metadata.version
	UPROPERTY() bool Compressed = false;  // источник: metadata.compressed?
	UPROPERTY() FUmCombatState CombatInfo; // источник: metadata.combatInfo? — между attack и resolveCombat/game-over
	/** Парсер: combatInfo присутствует (объект). */
	UPROPERTY() bool bHasCombatInfo = false;
	UPROPERTY() int32 PassCount = 0;      // источник: metadata.passCount?
	UPROPERTY() FString WinnerId;         // источник: metadata.winnerId? — при GAME_OVER
	UPROPERTY() int32 ActionsRemaining = 2; // источник: metadata.actionsRemaining? — отсутствие/мусор → 2 (game-state.model.ts:172-175)
	UPROPERTY() TMap<FString, FUmPosition> TurnStartPositions; // источник: metadata.turnStartPositions? — Record<fighterId, {x,y}>
	UPROPERTY() TArray<FUmPendingEffect> PendingEffects; // источник: metadata.pendingEffects?
	UPROPERTY() bool ManeuveredThisTurn = false; // источник: metadata.maneuveredThisTurn? (отсутствие → false)
	UPROPERTY() bool AttackedThisTurn = false;   // источник: metadata.attackedThisTurn?
	UPROPERTY() bool LostCombatThisTurn = false; // источник: metadata.lostCombatThisTurn?
	UPROPERTY() TMap<FString, FString> HeroStances; // источник: metadata.heroStances? — Record<userId, stanceId>; на game-init не заполняется (R4 §2.13)

	/** getActionsRemaining: мусор/отрицательное → 2 (game-state.model.ts:172-175). */
	int32 GetActionsRemaining() const { return ActionsRemaining >= 0 ? ActionsRemaining : 2; }
};

// =====================================================================================================================
// Корень
// =====================================================================================================================

/** GameState — game-state.model.ts:30-53; R3 §2.9.1. Снимок; клиент не мутирует (ADR §5.2). */
USTRUCT()
struct UMMODEL_API FUmGameState
{
	GENERATED_BODY()

	UPROPERTY() FString GameId;            // источник: GameState.gameId — cuid
	UPROPERTY() int64 SequenceNumber = 0;  // источник: GameState.sequenceNumber — монотонный, старт 1 (в GraphQL-обёртках приходит и как Float → int64)
	UPROPERTY() FString Phase;             // источник: GameState.phase — GamePhase
	UPROPERTY() int32 TurnCount = 0;       // источник: GameState.turnCount — старт 1
	UPROPERTY() FString CurrentTurnPlayerId; // источник: GameState.currentTurnPlayerId — userId
	UPROPERTY() TArray<FUmGameStatePlayer> Players; // источник: GameState.players
	UPROPERTY() TArray<FUmFighter> Fighters; // источник: GameState.fighters — все, включая поверженных
	UPROPERTY() TMap<FString, FUmDeckState> Decks; // источник: GameState.decks — Record<userId, DeckState>; ОТСУТСТВУЕТ в подписке
	UPROPERTY() TMap<FString, FUmCardList> DiscardPiles; // источник: GameState.discardPiles — Record<userId, Card[]>; ОТСУТСТВУЕТ в подписке
	UPROPERTY() TMap<FString, FUmHandZone> HandZones; // источник: GameState.handZones — Record<userId, HandZone>
	UPROPERTY() FUmBoardState BoardState;  // источник: GameState.boardState
	UPROPERTY() FUmGameStateMetadata Metadata; // источник: GameState.metadata

	/** Парсер: decks присутствовали в JSON (полный снапшот). В ParsePartial не меняется — мерж делает FUmGameSnapshotStore (ADR §5.2). */
	UPROPERTY() bool bHasDecks = false;
	/** Парсер: discardPiles присутствовали в JSON. */
	UPROPERTY() bool bHasDiscardPiles = false;

	// ---- Хелперы (ADR §4.2: GetPhase, FindFighter, MyHand, IsMyTurn, AmIDefender, MyPendingEffects, MyStance) ----

	EUmGamePhase GetPhase() const { return UmEnums::ParseGamePhase(Phase); }
	bool IsGameOver() const { return GetPhase() == EUmGamePhase::GameOver; }
	/** Action-фазы, в которых разрешены maneuver/moveFighter/attack/playScheme/endTurn/pass/toggleDoor/setStance (ActionPhaseGuard — R3 §2.2). */
	bool IsActionPhase() const { const EUmGamePhase P = GetPhase(); return P == EUmGamePhase::ActionManeuver || P == EUmGamePhase::ActionAttack; }

	const FUmFighter* FindFighter(const FString& FighterId) const
	{
		for (const FUmFighter& Fighter : Fighters) { if (Fighter.Id == FighterId) { return &Fighter; } }
		return nullptr;
	}
	const FUmGameStatePlayer* FindPlayer(const FString& UserId) const
	{
		for (const FUmGameStatePlayer& Player : Players) { if (Player.UserId == UserId) { return &Player; } }
		return nullptr;
	}
	/** HERO-боец игрока (нужен для setStance: "У игрока нет героя на доске" — R4 §2.13). */
	const FUmFighter* FindHeroFighter(const FString& UserId) const
	{
		for (const FUmFighter& Fighter : Fighters)
		{
			if (Fighter.OwnerId == UserId && Fighter.IsHero()) { return &Fighter; }
		}
		return nullptr;
	}
	/** Своя рука — по ключу handZones[myUserId], НЕ по isVisible (R3 §3.13; ADR §5.2). */
	const FUmHandZone* MyHand(const FString& MyUserId) const { return HandZones.Find(MyUserId); }
	bool IsMyTurn(const FString& MyUserId) const { return !MyUserId.IsEmpty() && CurrentTurnPlayerId == MyUserId; }
	bool HasCombat() const { return Metadata.bHasCombatInfo; }
	/** Защитник: combatInfo.defenderId == myUserId (R3 §3.9). */
	bool AmIDefender(const FString& MyUserId) const { return HasCombat() && Metadata.CombatInfo.DefenderId == MyUserId; }
	/** Атакующий: владелец бойца combatInfo.attackerId (attackerId — боец!). */
	bool AmIAttacker(const FString& MyUserId) const
	{
		if (!HasCombat()) { return false; }
		const FUmFighter* Attacker = FindFighter(Metadata.CombatInfo.AttackerId);
		return Attacker && Attacker->OwnerId == MyUserId;
	}
	/** Цель боя: targetFighterId, fallback — первый живой боец защитника (легаси-сейвы — R3 §2.9.8). */
	const FUmFighter* CombatTarget() const
	{
		if (!HasCombat()) { return nullptr; }
		if (const FUmFighter* Target = FindFighter(Metadata.CombatInfo.TargetFighterId)) { return Target; }
		for (const FUmFighter& Fighter : Fighters)
		{
			if (Fighter.OwnerId == Metadata.CombatInfo.DefenderId && Fighter.IsAlive()) { return &Fighter; }
		}
		return nullptr;
	}
	TArray<const FUmPendingEffect*> MyPendingEffects(const FString& MyUserId) const
	{
		TArray<const FUmPendingEffect*> Out;
		for (const FUmPendingEffect& Pending : Metadata.PendingEffects)
		{
			if (Pending.PlayerId == MyUserId) { Out.Add(&Pending); }
		}
		return Out;
	}
	/** Текущая стойка: heroStances[userId], иначе isDefault из heroStances(heroSlug), иначе первая, иначе пусто (R3 §2.9.7; R4 §2.13). */
	FString MyStance(const FString& MyUserId, const TArray<FUmStanceOptionDto>& Options) const
	{
		if (const FString* Stance = Metadata.HeroStances.Find(MyUserId))
		{
			if (!Stance->IsEmpty()) { return *Stance; }
		}
		for (const FUmStanceOptionDto& Option : Options) { if (Option.IsDefault) { return Option.Id; } }
		return Options.Num() > 0 ? Options[0].Id : FString();
	}
	int32 GetActionsRemaining() const { return Metadata.GetActionsRemaining(); }
	/** Дедлайн защиты: startedAt + DefenseTimeoutSec (timeoutAt не приходит — R3 §3.8). Невалиден, если нет боя/даты. */
	bool GetDefenseDeadline(double DefenseTimeoutSec, FDateTime& OutDeadlineUtc) const
	{
		if (!HasCombat() || !Metadata.CombatInfo.StartedAt.bSet) { return false; }
		OutDeadlineUtc = Metadata.CombatInfo.StartedAt.Utc + FTimespan::FromSeconds(DefenseTimeoutSec);
		return true;
	}
};

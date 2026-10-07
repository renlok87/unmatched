#include "S09HudModel.h"
#include "Dom/JsonObject.h"

FString FS09CardView::ChipText() const {
  FString Chip = FString::Printf(TEXT("[%s] %s"), *CardType, *Name);
  if (AttackValue > 0) Chip += FString::Printf(TEXT(" A%d"), AttackValue);
  if (DefenseValue > 0) Chip += FString::Printf(TEXT(" D%d"), DefenseValue);
  if (BoostValue > 0) Chip += FString::Printf(TEXT(" B%d"), BoostValue);
  if (!BannerName.IsEmpty()) Chip += TEXT(" (") + BannerName + TEXT(")");
  return Chip;
}

bool FS09HudFactory::CardFromJson(const TSharedPtr<FJsonValue>& Value,
                                  FS09CardView& OutCard) {
  const TSharedPtr<FJsonObject>* Object = nullptr;
  if (!Value.IsValid() || !Value->TryGetObject(Object) || !Object->IsValid()) {
    return false;
  }
  const TSharedRef<FJsonObject> Card = Object->ToSharedRef();
  OutCard = FS09CardView();
  OutCard.InstanceId = Card->GetStringField(TEXT("id"));
  OutCard.CardId = Card->GetStringField(TEXT("cardId"));
  OutCard.Name = Card->GetStringField(TEXT("name"));
  OutCard.NameRu = Card->GetStringField(TEXT("nameRu"));
  OutCard.CardType = Card->GetStringField(TEXT("cardType"));
  OutCard.BannerName = Card->GetStringField(TEXT("bannerName"));
  OutCard.Text = Card->GetStringField(TEXT("text"));
  bool bVisible = false;
  Card->TryGetBoolField(TEXT("isVisible"), bVisible);
  OutCard.bVisible = bVisible;
  auto ReadValue = [&Card](const TCHAR* Field, int32& Out) {
    bool Present = false;
    int32 Value = 0;
    if (FS08Contracts::ReadIntLike(Card, Field, Value, Present) && Present) Out = Value;
  };
  ReadValue(TEXT("attackValue"), OutCard.AttackValue);
  ReadValue(TEXT("defenseValue"), OutCard.DefenseValue);
  ReadValue(TEXT("boostValue"), OutCard.BoostValue);
  {
    const TArray<TSharedPtr<FJsonValue>>* Effects = nullptr;
    if (Card->TryGetArrayField(TEXT("effects"), Effects) && Effects) {
      OutCard.EffectCount = Effects->Num();
      for (const TSharedPtr<FJsonValue>& E : *Effects) {  // VS-3 HB-33: the printed sentences of the card
        const TSharedPtr<FJsonObject>* EO = nullptr;
        FString T;
        // VS-4 review (SC-21): the parsed effects of one printed text each carry that whole text (Regroup: two
        // effects, one sentence pair) - a text already taken is not appended again
        if (E.IsValid() && E->TryGetObject(EO) && EO && (*EO)->TryGetStringField(TEXT("text"), T) && !T.IsEmpty() &&
            !OutCard.EffectText.Contains(T, ESearchCase::CaseSensitive)) {
          OutCard.EffectText += (OutCard.EffectText.IsEmpty() ? TEXT("") : TEXT(" ")) + T;
        }
      }
    }
  }
  {
    const TSharedPtr<FJsonValue> Boost = Card->TryGetField(TEXT("boostValue"));
    double BoostNumber = 0.0;
    OutCard.bHasBoostValue = Boost.IsValid() && Boost->Type == EJson::Number && Boost->TryGetNumber(BoostNumber) &&
                             FMath::IsFinite(BoostNumber);
  }
  if (FS08Contracts::IsHiddenCard(Value)) {
    // Strip every identity field: a placeholder carries no face anywhere.
    OutCard = HiddenCard(OutCard.InstanceId);
  }
  return true;
}

FS09CardView FS09HudFactory::HiddenCard(const FString& PlaceholderId) {
  FS09CardView Card;
  Card.bHidden = true;
  Card.InstanceId = PlaceholderId; // "hidden-N" - safe: conveys only position
  return Card;
}

namespace {
const TArray<TSharedPtr<FJsonValue>>* HandEntries(const TSharedPtr<FJsonObject>& Hands,
                                                  const FString& PlayerId) {
  const TSharedPtr<FJsonValue> Hand = Hands->TryGetField(PlayerId);
  if (!Hand.IsValid()) return nullptr;
  const TSharedPtr<FJsonObject> HandObject = Hand->AsObject();
  if (!HandObject.IsValid()) return nullptr;
  const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
  if (!HandObject->TryGetArrayField(TEXT("cards"), Cards) || !Cards) return nullptr;
  return Cards;
}

const TArray<TSharedPtr<FJsonValue>>* PileEntries(const TSharedPtr<FJsonObject>& Piles,
                                                  const FString& PlayerId) {
  const TSharedPtr<FJsonValue> Pile = Piles->TryGetField(PlayerId);
  if (!Pile.IsValid()) return nullptr;
  const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
  if (!Pile->TryGetArray(Cards) || !Cards) return nullptr;
  return Cards;
}

int32 DeckCount(const TSharedPtr<FJsonValue>& Decks, const FString& PlayerId) {
  if (!Decks.IsValid()) return 0;
  const TSharedPtr<FJsonObject> DecksObject = Decks->AsObject();
  if (!DecksObject.IsValid()) return 0;
  const TSharedPtr<FJsonValue> Deck = DecksObject->TryGetField(PlayerId);
  if (!Deck.IsValid()) return 0;
  const TSharedPtr<FJsonObject> DeckObject = Deck->AsObject();
  if (!DeckObject.IsValid()) return 0;
  // drawPile: hidden placeholders whose LENGTH is the live count. The
  // entries themselves are never inspected (no order, no topCard).
  const TArray<TSharedPtr<FJsonValue>>* Pile = nullptr;
  if (DeckObject->TryGetArrayField(TEXT("drawPile"), Pile) && Pile) {
    return Pile->Num();
  }
  return 0;
}
} // namespace

void FS09HudModel::Build(const FS08Snapshot& Snapshot, const FString& ViewerId,
                         const TSet<FString>& PreviousOwnHandIds, int32 DecksSeq,
                         int32 DiscardPilesSeq) {
  Panels.Reset();
  SequenceNumber = Snapshot.SequenceNumber;
  Phase = Snapshot.Phase;
  TurnCount = Snapshot.TurnCount;
  bViewerTurn = !ViewerId.IsEmpty() && Snapshot.CurrentTurnPlayerId == ViewerId;
  bHasPendingDiscard = FS08Contracts::PendingHandDiscard(Snapshot, PendingDiscard);
  ActionsRemaining = -1;
  bValid = false;

  const TSharedPtr<FJsonObject> Hands = Snapshot.HandZones.IsValid()
                                            ? Snapshot.HandZones->AsObject()
                                            : nullptr;
  const TSharedPtr<FJsonObject> Piles = Snapshot.DiscardPiles.IsValid()
                                            ? Snapshot.DiscardPiles->AsObject()
                                            : nullptr;
  if (Snapshot.Metadata.IsValid()) {
    const TSharedPtr<FJsonObject> Meta = Snapshot.Metadata->AsObject();
    bool Present = false;
    int32 Actions = 0;
    if (FS08Contracts::ReadIntLike(Meta.ToSharedRef(), TEXT("actionsRemaining"), Actions,
                                   Present) &&
        Present) {
      ActionsRemaining = Actions;
    }
  }

  // Both seats from the players projection; viewer first.
  const TArray<TSharedPtr<FJsonValue>>* Players = nullptr;
  const TArray<TSharedPtr<FJsonValue>>* FighterEntries = nullptr; // GD-036 result
  if (Snapshot.Players.IsValid() && Snapshot.Players->TryGetArray(Players) && Players) {
    for (const TSharedPtr<FJsonValue>& Value : *Players) {
      const TSharedPtr<FJsonObject>* Player = nullptr;
      if (!Value.IsValid() || !Value->TryGetObject(Player) || !Player->IsValid()) continue;
      FS09PlayerPanel Panel;
      Panel.PlayerId = (*Player)->GetStringField(TEXT("userId"));
      Panel.bIsViewer = Panel.PlayerId == ViewerId;
      bool bAlive = true;
      (*Player)->TryGetBoolField(TEXT("isAlive"), bAlive);
      Panel.bIsAlive = bAlive;
      if (Panel.bIsViewer && Panels.Num() > 0 && Panels[0].bIsViewer) continue;
      Panels.Add(MoveTemp(Panel));
    }
  }
  Panels.Sort([](const FS09PlayerPanel& A, const FS09PlayerPanel& B) {
    return (A.bIsViewer ? 0 : 1) < (B.bIsViewer ? 0 : 1);
  });
  if (Panels.Num() > 2) Panels.SetNum(2);

  for (FS09PlayerPanel& Panel : Panels) {
    // Own hand: decode every entry (exact instance ids). Opponent hand:
    // COUNT ONLY - entries are never decoded (privacy by construction).
    if (Hands.IsValid()) {
      const TArray<TSharedPtr<FJsonValue>>* Cards = HandEntries(Hands, Panel.PlayerId);
      if (Cards) {
        Panel.HandCount = Cards->Num();
        if (Panel.bIsViewer) {
          for (const TSharedPtr<FJsonValue>& Value : *Cards) {
            FS09CardView Card;
            if (FS09HudFactory::CardFromJson(Value, Card)) {
              Card.bNew = !PreviousOwnHandIds.IsEmpty() &&
                          !PreviousOwnHandIds.Contains(Card.InstanceId);
              Panel.Cards.Add(MoveTemp(Card));
            }
          }
        }
        const TSharedPtr<FJsonValue> HandValue = Hands->TryGetField(Panel.PlayerId);
        const TSharedPtr<FJsonObject> HandObject =
            HandValue.IsValid() ? HandValue->AsObject() : nullptr;
        if (HandObject.IsValid()) {
          bool Present = false;
          int32 MaxSize = 0;
          if (FS08Contracts::ReadIntLike(HandObject.ToSharedRef(), TEXT("maxSize"),
                                         MaxSize, Present) &&
              Present) {
            Panel.HandMaxSize = MaxSize;
          }
        }
      }
    }
    if (Piles.IsValid()) {
      const TArray<TSharedPtr<FJsonValue>>* Pile = PileEntries(Piles, Panel.PlayerId);
      if (Pile) {
        for (const TSharedPtr<FJsonValue>& Value : *Pile) {
          FS09CardView Card;
          if (FS09HudFactory::CardFromJson(Value, Card)) {
            Panel.Discard.Add(MoveTemp(Card));
          }
        }
      }
    }
    Panel.DeckCount = DeckCount(Snapshot.Decks, Panel.PlayerId);
    Panel.bDeckCountStale = DecksSeq < Snapshot.SequenceNumber;
    Panel.bDiscardStale = DiscardPilesSeq < Snapshot.SequenceNumber;
  }

  const FS09PlayerPanel* Viewer = ViewerPanel();
  bValid = Viewer != nullptr && Viewer->HandMaxSize > 0;

  // ---- GD-036 terminal result ----
  bGameOver = Snapshot.Phase == TEXT("GAME_OVER");
  WinnerPlayerId.Reset();
  bWinnerKnown = false;
  bViewerWon = false;
  bAnyPlayerAlive = Panels.Num() == 0; // no players info = verdict unknowable
  for (const FS09PlayerPanel& Panel : Panels) {
    if (Panel.bIsAlive) { bAnyPlayerAlive = true; break; }
  }
  bDraw = false;
  bOutcomeUnknown = false;
  WinnerHeroName.Reset();
  if (bGameOver && Snapshot.Metadata.IsValid()) {
    const TSharedPtr<FJsonObject> Meta = Snapshot.Metadata->AsObject();
    if (Meta.IsValid()) {
      WinnerPlayerId = Meta->GetStringField(TEXT("winnerId"));
    }
  }
  if (!WinnerPlayerId.IsEmpty()) {
    for (const FS09PlayerPanel& Panel : Panels) {
      if (Panel.PlayerId == WinnerPlayerId) {
        bWinnerKnown = true;
        bViewerWon = Panel.bIsViewer;
        break;
      }
    }
  }
  if (bGameOver) {
    // Server contract: applyTerminalState writes winnerId = alive[0]?.userId.
    // Absent winnerId + nobody alive IS the mutual-destruction draw; absent
    // winnerId with a living player (or a winnerId naming nobody) carries no
    // verdict - OUTCOME UNAVAILABLE, never an invented draw or win.
    bDraw = !bWinnerKnown && WinnerPlayerId.IsEmpty() && !bAnyPlayerAlive;
    bOutcomeUnknown = !bWinnerKnown && !bDraw;
  }
  if (bWinnerKnown) {
    // Winner's hero name from the PUBLIC fighters projection (any fighter of
    // the winner, hero first - defeated sidekicks do not change the name).
    if (Snapshot.Fighters.IsValid() &&
        Snapshot.Fighters->TryGetArray(FighterEntries) && FighterEntries) {
      for (const TSharedPtr<FJsonValue>& Value : *FighterEntries) {
        const TSharedPtr<FJsonObject>* Fighter = nullptr;
        if (!Value.IsValid() || !Value->TryGetObject(Fighter) || !Fighter->IsValid()) continue;
        const FString OwnerId = (*Fighter)->GetStringField(TEXT("ownerId"));
        if (OwnerId != WinnerPlayerId) continue;
        const FString Type = (*Fighter)->GetStringField(TEXT("type"));
        const FString Name = (*Fighter)->GetStringField(TEXT("name"));
        if (Type == TEXT("HERO") || Type == TEXT("HUGE")) {
          WinnerHeroName = Name; // hero wins over any sidekick
          break;
        }
        if (WinnerHeroName.IsEmpty()) WinnerHeroName = Name;
      }
    }
  }
}

FString FS09HudModel::OutcomeWord() const {
  if (bWinnerKnown) return bViewerWon ? TEXT("VICTORY") : TEXT("DEFEAT");
  if (bDraw) return TEXT("DRAW");
  return TEXT("OUTCOME UNAVAILABLE");
}

FString FS09HudModel::SummaryLine() const {
  const FS09PlayerPanel* Viewer = ViewerPanel();
  const FS09PlayerPanel* Opponent = OpponentPanel();
  const int32 OwnHidden = Viewer
                              ? Viewer->Cards.FilterByPredicate(
                                    [](const FS09CardView& C) { return C.bHidden; })
                                    .Num()
                              : 0;
  FString Line = FString::Printf(TEXT("HUD seq=%d phase=%s turn=%s hand=%d"),
                                 SequenceNumber, *Phase, bViewerTurn ? TEXT("you") : TEXT("opp"),
                                 Viewer ? Viewer->HandCount : -1);
  if (Viewer && OwnHidden > 0) Line += FString::Printf(TEXT("(%d hidden)"), OwnHidden);
  if (Opponent) {
    Line += FString::Printf(TEXT(" oppHand=%d(hidden) oppDeck=%d%s"), Opponent->HandCount,
                            Opponent->DeckCount, Opponent->bDeckCountStale ? TEXT("~") : TEXT(""));
  }
  if (Viewer) {
    Line += FString::Printf(TEXT(" deck=%d%s discard=%d%s"), Viewer->DeckCount,
                            Viewer->bDeckCountStale ? TEXT("~") : TEXT(""), Viewer->Discard.Num(),
                            Viewer->bDiscardStale ? TEXT("~") : TEXT(""));
  }
  if (bHasPendingDiscard) {
    Line += FString::Printf(TEXT(" pendingDiscard=%d"), PendingDiscard.Count);
  }
  return Line;
}

// ---- DE-018: combat panel model ----

ES09DefenseSlot S09DefenseSlotState(const FString& Phase, bool bViewerDefender, bool bDraftPicked,
                                    bool bRevealedNoDefense) {
  if (bRevealedNoDefense) return ES09DefenseSlot::NoDefense;
  if (Phase == TEXT("COMBAT_RESOLVE")) return ES09DefenseSlot::CardBack;
  if (Phase == TEXT("COMBAT") && bViewerDefender && bDraftPicked) return ES09DefenseSlot::CardBack;
  return ES09DefenseSlot::Shield;
}

const TCHAR* S09DefenseSlotName(ES09DefenseSlot Slot) {
  switch (Slot) {
    case ES09DefenseSlot::CardBack: return TEXT("card-back");
    case ES09DefenseSlot::NoDefense: return TEXT("no-defense");
    default: return TEXT("shield");
  }
}

bool FS09CombatReveal::HasEffectText() const {
  auto Has = [](const FS09CardView& Card) { return !Card.bHidden && (!Card.Text.IsEmpty() || Card.EffectCount > 0); };
  return (bAttackKnown && Has(Attack)) || (bDefenseKnown && Has(Defense));
}

namespace {
/** One owner's pile as card views (empty when absent). */
TArray<FS09CardView> PileCards(const TSharedPtr<FJsonValue>& Piles, const FString& OwnerId) {
  TArray<FS09CardView> Out;
  if (!Piles.IsValid() || OwnerId.IsEmpty()) return Out;
  const TSharedPtr<FJsonObject> Object = Piles->AsObject();
  if (!Object.IsValid()) return Out;
  const TArray<TSharedPtr<FJsonValue>>* Entries = PileEntries(Object, OwnerId);
  if (!Entries) return Out;
  for (const TSharedPtr<FJsonValue>& Value : *Entries) {
    FS09CardView Card;
    if (FS09HudFactory::CardFromJson(Value, Card)) Out.Add(MoveTemp(Card));
  }
  return Out;
}

const FS09CardView* CardById(const TArray<FS09CardView>& Pile, const FString& InstanceId) {
  if (InstanceId.IsEmpty()) return nullptr;
  return Pile.FindByPredicate([&InstanceId](const FS09CardView& Card) { return Card.InstanceId == InstanceId; });
}

/** Indices of the face-down placeholders of a baseline pile, oldest first. */
TArray<int32> HiddenIndices(const TArray<FS09CardView>& Pile) {
  TArray<int32> Out;
  for (int32 I = 0; I < Pile.Num(); ++I) {
    if (Pile[I].bHidden) Out.Add(I);
  }
  return Out;
}

/** The public face at Index of the closing pile (nullptr when absent or still hidden). */
const FS09CardView* FaceAt(const TArray<FS09CardView>& Pile, int32 Index) {
  return Pile.IsValidIndex(Index) && !Pile[Index].bHidden ? &Pile[Index] : nullptr;
}
}  // namespace

FS09CombatReveal FS09CombatReveal::Derive(const FS08CombatInfo& Combat, const FString& AttackerOwnerId,
                                          const TSharedPtr<FJsonValue>& BaselinePiles,
                                          const TSharedPtr<FJsonValue>& ClosingPiles) {
  FS09CombatReveal Out;
  if (!Combat.bPresent) return Out;
  const TArray<FS09CardView> AttackBase = PileCards(BaselinePiles, AttackerOwnerId);
  const TArray<FS09CardView> AttackNow = PileCards(ClosingPiles, AttackerOwnerId);
  const TArray<FS09CardView> DefenseBase = PileCards(BaselinePiles, Combat.DefenderId);
  const TArray<FS09CardView> DefenseNow = PileCards(ClosingPiles, Combat.DefenderId);

  // Attack card + boosts: by instance id when this seat saw them, else by the placeholder positions.
  TArray<int32> AttackHidden = HiddenIndices(AttackBase);
  if (const FS09CardView* Card = Combat.bHasAttackerCard ? CardById(AttackNow, Combat.AttackerCardId) : nullptr) {
    Out.Attack = *Card;
    Out.bAttackKnown = true;
  } else if (AttackHidden.Num() > 0) {
    if (const FS09CardView* Face = FaceAt(AttackNow, AttackHidden[0])) {
      Out.Attack = *Face;
      Out.bAttackKnown = true;
    }
    AttackHidden.RemoveAt(0);
  }
  for (const FString& BoostId : {Combat.bHasAbilityBoostCardId ? Combat.AbilityBoostCardId : FString(),
                                 Combat.bHasCardBoostCardId ? Combat.CardBoostCardId : FString()}) {
    if (const FS09CardView* Card = CardById(AttackNow, BoostId)) Out.Boosts.Add(*Card);
  }
  if (Out.Boosts.Num() == 0) {
    for (const int32 Index : AttackHidden) {
      if (const FS09CardView* Face = FaceAt(AttackNow, Index)) Out.Boosts.Add(*Face);
    }
  }
  if (Out.bAttackKnown) {
    int32 Boost = 0;
    if (Combat.bHasBoostValue) {
      Boost = Combat.BoostValue;
    } else {
      for (const FS09CardView& Card : Out.Boosts) Boost += Card.BoostValue;
    }
    Out.AttackValue = Out.Attack.AttackValue + Boost;
  }

  // Defense card: the defender's own id, else the placeholder the defender's pile held in the baseline.
  const TArray<int32> DefenseHidden = HiddenIndices(DefenseBase);
  if (const FS09CardView* Card = Combat.bHasDefenderCard ? CardById(DefenseNow, Combat.DefenderCardId) : nullptr) {
    Out.Defense = *Card;
    Out.bDefenseKnown = true;
  } else if (DefenseHidden.Num() > 0) {
    if (const FS09CardView* Face = FaceAt(DefenseNow, DefenseHidden.Last())) {
      Out.Defense = *Face;
      Out.bDefenseKnown = true;
    }
  } else if (!Combat.bHasDefenderCard) {
    Out.bNoDefense = true;
  }
  Out.DefenseValue = Out.bDefenseKnown ? Out.Defense.DefenseValue : Out.bNoDefense ? 0 : -1;
  return Out;
}

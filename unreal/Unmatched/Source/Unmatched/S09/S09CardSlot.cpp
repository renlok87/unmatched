// DE-026 (W-18): the hand and the played cards - see S09CardSlot.h.
#include "S09CardSlot.h"

// ---------------------------------------------------------------------------------------------------- hand (SD-26)

const TCHAR* S09BoardPickName(ES09BoardPick Pick) {
  switch (Pick) {
    case ES09BoardPick::Cell: return TEXT("cell");
    case ES09BoardPick::Target: return TEXT("target");
    default: return TEXT("none");
  }
}

ES09BoardPick S09BoardPickOf(const FS09CommandUi& Ui, bool bViewerTurn) {
  switch (Ui.Mode) {
    case ES09CommandMode::ManeuverDraft:
      // MS-S-07: a fighter of the draft is selected - its destination is the next board click
      return Ui.SelectedFighterId.IsEmpty() ? ES09BoardPick::None : ES09BoardPick::Cell;
    case ES09CommandMode::AttackDraft:
      return !Ui.AttackAttackerId.IsEmpty() && Ui.AttackTargetId.IsEmpty() ? ES09BoardPick::Target
                                                                            : ES09BoardPick::None;
    case ES09CommandMode::PendingChoice: {
      const FString& Type = Ui.PendingChoice.Type;
      if (Type == TEXT("TARGET_FIGHTER")) return ES09BoardPick::Target;
      if (Type == TEXT("CHOOSE_SPACE")) return ES09BoardPick::Cell;
      if (Type == TEXT("MOVE") || Type == TEXT("PLACE")) {
        return Ui.PendingFighterId.IsEmpty() ? ES09BoardPick::Target : ES09BoardPick::Cell;
      }
      return ES09BoardPick::None;  // CHOOSE_ONE, DISCARD_CARDS, BOOST_CHOICE, DECK_TOP_PICK: the hand / the panel
    }
    case ES09CommandMode::None:
      // MS-S-02 / MS-S-03: an own fighter selected before the draft shows its reachable cells
      return bViewerTurn && !Ui.SelectedFighterId.IsEmpty() && Ui.ReachableCells.Num() > 0 ? ES09BoardPick::Cell
                                                                                             : ES09BoardPick::None;
    default:
      return ES09BoardPick::None;
  }
}

FString FS09HandLower::Update(ES09BoardPick Pick, bool bCursorOverHud, double NowMs) {
  const bool bWant = Pick != ES09BoardPick::None && !bCursorOverHud;
  if (bWant == bLowered) return FString();
  FromSu = OffsetSu(NowMs, /*bReducedMotion=*/false);
  bLowered = bWant;
  ChangedMs = NowMs;
  return FString::Printf(TEXT("HUD-HAND lower=%d pick=%s cursor=%s preview=%s"), bLowered ? 1 : 0,
                         S09BoardPickName(Pick), bCursorOverHud ? TEXT("hud") : TEXT("board"),
                         bLowered ? TEXT("hidden") : TEXT("shown"));
}

float FS09HandLower::OffsetSu(double NowMs, bool bReducedMotion) const {
  const float Target = bLowered ? LowerSu : 0.0f;
  if (bReducedMotion || SlideMs <= 0.0) return Target;
  const float T = FMath::Clamp(static_cast<float>((NowMs - ChangedMs) / SlideMs), 0.0f, 1.0f);
  const float Ease = 1.0f - (1.0f - T) * (1.0f - T);
  return FMath::Lerp(FromSu, Target, Ease);
}

bool FS09HandLower::IsSliding(double NowMs, bool bReducedMotion) const {
  return !bReducedMotion && NowMs - ChangedMs < SlideMs;
}

// ---------------------------------------------------------------------------------------------------- watch

const TCHAR* S09SlotRibbonName(ES09SlotRibbon Ribbon) {
  switch (Ribbon) {
    case ES09SlotRibbon::Boosted: return TEXT("boosted");
    case ES09SlotRibbon::Discarded: return TEXT("discarded");
    default: return TEXT("scheme");
  }
}

const TCHAR* S09SlotRibbonLabel(ES09SlotRibbon Ribbon) {
  switch (Ribbon) {
    case ES09SlotRibbon::Boosted: return TEXT("BOOSTED");
    case ES09SlotRibbon::Discarded: return TEXT("DISCARDED");
    default: return TEXT("SCHEME");
  }
}

bool FS09PlayedCardWatch::OnApplied(const FS09HudModel& Hud, const TArray<FS08PendingEffect>& Queue,
                                    const FS09LastMovement& Trail, const FString& ViewerId, FS09SlotCard& Out) {
  if (!Hud.bValid) return false;
  // the cards that entered each public pile since the last applied snapshot (oldest first, as delivered)
  struct FNew {
    const FS09PlayerPanel* Panel = nullptr;
    TArray<const FS09CardView*> Cards;
  };
  TArray<FNew> News;
  for (const FS09PlayerPanel& Panel : Hud.Panels) {
    if (Panel.PlayerId.IsEmpty() || Panel.bDiscardStale) continue;  // a stale pile is read when it arrives
    TSet<FString>& Seen = PileIds.FindOrAdd(Panel.PlayerId);
    FNew Entry;
    Entry.Panel = &Panel;
    for (const FS09CardView& Card : Panel.Discard) {
      if (Card.bHidden || Card.InstanceId.IsEmpty()) continue;  // a face-down combat card has no identity yet
      bool bAlready = false;
      Seen.Add(Card.InstanceId, &bAlready);
      if (!bAlready) Entry.Cards.Add(&Card);
    }
    News.Add(Entry);
  }
  const bool bWasPrimed = bPrimed;
  const bool bCombatPrev = bCombatBefore;
  const TSet<FString> OpenBefore = DiscardOpen;
  bPrimed = true;
  bCombatBefore = IsCombatPhase(Hud.Phase);
  DiscardOpen.Reset();
  if (Hud.bHasPendingDiscard && !Hud.PendingDiscard.PlayerId.IsEmpty()) DiscardOpen.Add(Hud.PendingDiscard.PlayerId);
  for (const FS08PendingEffect& Effect : Queue) {
    if (Effect.Type == TEXT("DISCARD_CARDS") || Effect.Type == TEXT("BOOST_CHOICE")) DiscardOpen.Add(Effect.PlayerId);
  }
  const bool bBoostTrail = Trail.bValid && Trail.Seq == Hud.SequenceNumber && Trail.Source == TEXT("MANEUVER") &&
                           Trail.bBoost && !Trail.PlayerId.IsEmpty() && Trail.PlayerId != ViewerId;
  if (!bWasPrimed) {
    if (bBoostTrail) BoostSeqSeen = Trail.Seq;  // entry / reconnect: an old boost is not replayed
    return false;
  }
  const bool bCombat = bCombatPrev || bCombatBefore;  // combat cards (attack, defense, boosts) are the staging's

  // the opponent's maneuver boost (SD-54): its card face from the pile (newest of that name), else the trail
  const FS09CardView* BoostCard = nullptr;
  bool bBoost = false;
  FS09SlotCard Boost;
  if (bBoostTrail && Trail.Seq != BoostSeqSeen) {
    BoostSeqSeen = Trail.Seq;
    bBoost = true;
    for (const FNew& Entry : News) {
      if (Entry.Panel->PlayerId != Trail.PlayerId) continue;
      for (int32 I = Entry.Cards.Num() - 1; I >= 0 && !BoostCard; --I) {
        if (Entry.Cards[I]->Name.Equals(Trail.BoostName, ESearchCase::IgnoreCase)) BoostCard = Entry.Cards[I];
      }
      for (int32 I = Entry.Panel->Discard.Num() - 1; I >= 0 && !BoostCard; --I) {
        const FS09CardView& Card = Entry.Panel->Discard[I];
        if (!Card.bHidden && Card.Name.Equals(Trail.BoostName, ESearchCase::IgnoreCase)) BoostCard = &Card;
      }
    }
    if (BoostCard) {
      Boost.Card = *BoostCard;
    } else {
      Boost.Card.Name = Trail.BoostName.IsEmpty() ? FString(TEXT("?")) : Trail.BoostName;
      Boost.Card.BoostValue = Trail.BoostValue;
      Boost.Card.bHasBoostValue = true;
    }
    Boost.OwnerId = Trail.PlayerId;
    Boost.bOpponent = true;
    Boost.Ribbon = ES09SlotRibbon::Boosted;
    Boost.Seq = Hud.SequenceNumber;
  }

  // a scheme: the newest SCHEME card that entered a pile outside combat and outside an open discard of its owner (the
  // played scheme goes to the pile after its own effects - executePlayScheme)
  if (!bCombat) {
    for (const FNew& Entry : News) {
      if (OpenBefore.Contains(Entry.Panel->PlayerId)) continue;
      for (int32 I = Entry.Cards.Num() - 1; I >= 0; --I) {
        const FS09CardView* Card = Entry.Cards[I];
        if (Card == BoostCard || Card->CardType != TEXT("SCHEME")) continue;
        Out = FS09SlotCard();
        Out.Card = *Card;
        Out.OwnerId = Entry.Panel->PlayerId;
        Out.bOpponent = !Entry.Panel->bIsViewer;
        Out.Ribbon = ES09SlotRibbon::Scheme;
        Out.Seq = Hud.SequenceNumber;
        return true;
      }
    }
  }
  if (bBoost) {
    Out = Boost;
    return true;
  }
  // the opponent's discard to an open discard (the hand limit, an effect's DISCARD_CARDS)
  if (!bCombat) {
    for (const FNew& Entry : News) {
      if (Entry.Panel->bIsViewer || !OpenBefore.Contains(Entry.Panel->PlayerId)) continue;
      TArray<const FS09CardView*> Dropped;
      for (const FS09CardView* Card : Entry.Cards) {
        if (Card != BoostCard) Dropped.Add(Card);
      }
      if (Dropped.Num() == 0) continue;
      Out = FS09SlotCard();
      Out.Card = *Dropped.Last();
      Out.OwnerId = Entry.Panel->PlayerId;
      Out.bOpponent = true;
      Out.Ribbon = ES09SlotRibbon::Discarded;
      Out.Count = Dropped.Num();
      Out.Seq = Hud.SequenceNumber;
      return true;
    }
  }
  return false;
}

// ---------------------------------------------------------------------------------------------------- slot

const TCHAR* FS09SourceSlot::StateName(ES09SlotState InState) {
  switch (InState) {
    case ES09SlotState::Fly: return TEXT("fly");
    case ES09SlotState::Hold: return TEXT("hold");
    case ES09SlotState::Show: return TEXT("show");
    case ES09SlotState::Fade: return TEXT("fade");
    default: return TEXT("idle");
  }
}

bool FS09SourceSlot::Show(const FS09SlotCard& InCard, int64 NowMs, bool bReducedMotion, TArray<FString>& OutLines,
                          bool& bOutReleased) {
  bOutReleased = false;
  if (IsVisible() && InCard.Ribbon == ES09SlotRibbon::Discarded && Card.Ribbon == ES09SlotRibbon::Scheme) {
    OutLines.Add(FString::Printf(TEXT("HUD-SLOT drop seq=%d ribbon=discarded count=%d reason=scheme-shown"), InCard.Seq,
                                 InCard.Count));
    return false;
  }
  if (bHolding) {
    Release(NowMs, TEXT("replace"), OutLines);
    bOutReleased = true;
  }
  if (IsVisible()) Off(NowMs, TEXT("replace"), OutLines);
  Card = InCard;
  bReduced = bReducedMotion;
  StartMs = NowMs;
  ArriveMs = NowMs + (bReduced ? 0 : FlyMs);
  const bool bOppScheme = Card.Ribbon == ES09SlotRibbon::Scheme && Card.bOpponent;
  bHolding = bOppScheme;
  ReleaseMs = bOppScheme ? ArriveMs + OppSchemeHoldMs : ArriveMs;
  MinEndMs = Card.Ribbon == ES09SlotRibbon::Scheme ? (bOppScheme ? ReleaseMs : ArriveMs + OwnSchemeMs)
                                                   : StartMs + MinShowMs;
  State = bReduced ? (bHolding ? ES09SlotState::Hold : ES09SlotState::Show) : ES09SlotState::Fly;
  ++Revision;
  OutLines.Add(FString::Printf(
      TEXT("HUD-SLOT show seq=%d ribbon=%s owner=%s card=\"%s\" count=%d fly=%d hold=%d min=%d reduced=%d"), Card.Seq,
      S09SlotRibbonName(Card.Ribbon), Card.bOpponent ? TEXT("opp") : TEXT("own"), *Card.Card.Name, Card.Count,
      static_cast<int32>(ArriveMs - StartMs), static_cast<int32>(ReleaseMs - ArriveMs),
      static_cast<int32>(MinEndMs - StartMs), bReduced ? 1 : 0));
  return true;
}

void FS09SourceSlot::Release(int64 NowMs, const TCHAR* How, TArray<FString>& OutLines) {
  if (!bHolding) return;
  bHolding = false;
  OutLines.Add(FString::Printf(TEXT("HUD-SLOT effect seq=%d release=%s afterArrive=%d"), Card.Seq, How,
                               static_cast<int32>(FMath::Max<int64>(0, NowMs - ArriveMs))));
  // the effect starts: the card stays while it runs (no new minimum)
  MinEndMs = FMath::Min(MinEndMs, NowMs);
  if (State == ES09SlotState::Hold) State = ES09SlotState::Show;
}

void FS09SourceSlot::Off(int64 NowMs, const TCHAR* Reason, TArray<FString>& OutLines) {
  if (State == ES09SlotState::Idle) return;
  OutLines.Add(FString::Printf(TEXT("HUD-SLOT off seq=%d ribbon=%s shown=%d reason=%s"), Card.Seq,
                               S09SlotRibbonName(Card.Ribbon), static_cast<int32>(NowMs - StartMs), Reason));
  State = ES09SlotState::Idle;
  bHolding = false;
  ++Revision;
}

void FS09SourceSlot::Tick(int64 NowMs, bool bEffectBusy, TArray<FString>& OutLines, bool& bOutReleased) {
  bOutReleased = false;
  if (State == ES09SlotState::Idle) return;
  if (State == ES09SlotState::Fly && NowMs >= ArriveMs) State = bHolding ? ES09SlotState::Hold : ES09SlotState::Show;
  if (bHolding) {
    if (NowMs < ReleaseMs) return;
    Release(NowMs, TEXT("time"), OutLines);
    bOutReleased = true;
    return;  // the effect starts this frame: whether it runs is known from the next frame on
  }
  if (State == ES09SlotState::Show) {
    const bool bCap = NowMs - StartMs >= MaxShowMs;
    if (NowMs >= MinEndMs && (!bEffectBusy || bCap)) {
      const TCHAR* Reason = bEffectBusy ? TEXT("cap") : TEXT("done");
      if (Card.Ribbon == ES09SlotRibbon::Scheme || bReduced || FadeMs <= 0) {
        Off(NowMs, Reason, OutLines);  // DE: the scheme card leaves in one frame
        return;
      }
      State = ES09SlotState::Fade;
      FadeStartMs = NowMs;
    }
  }
  if (State == ES09SlotState::Fade && NowMs - FadeStartMs >= FadeMs) Off(NowMs, TEXT("done"), OutLines);
}

bool FS09SourceSlot::Skip(int64 NowMs, const TCHAR* Source, TArray<FString>& OutLines) {
  if (!bHolding) return false;
  Release(NowMs, Source, OutLines);
  return true;
}

void FS09SourceSlot::Cut(int64 NowMs, const TCHAR* Reason, TArray<FString>& OutLines, bool& bOutReleased) {
  bOutReleased = false;
  if (bHolding) {
    Release(NowMs, Reason, OutLines);
    bOutReleased = true;
  }
  Off(NowMs, Reason, OutLines);
}

bool FS09SourceSlot::ReleaseForSeq(int32 Seq, int64 NowMs, TArray<FString>& OutLines) {
  if (!bHolding || Seq == Card.Seq) return false;
  Release(NowMs, TEXT("newseq"), OutLines);
  return true;
}

float FS09SourceSlot::FlyT(int64 NowMs) const {
  if (State == ES09SlotState::Idle) return 0.0f;
  if (ArriveMs <= StartMs) return 1.0f;
  const float T = FMath::Clamp(static_cast<float>(NowMs - StartMs) / static_cast<float>(ArriveMs - StartMs), 0.0f, 1.0f);
  return 1.0f - FMath::Pow(1.0f - T, 3.0f);
}

float FS09SourceSlot::Alpha(int64 NowMs) const {
  if (State == ES09SlotState::Idle) return 0.0f;
  if (State != ES09SlotState::Fade) return 1.0f;
  return FMath::Clamp(1.0f - static_cast<float>(NowMs - FadeStartMs) / static_cast<float>(FadeMs), 0.0f, 1.0f);
}

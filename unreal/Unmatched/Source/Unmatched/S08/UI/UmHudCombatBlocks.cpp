// VS-3 HB-30...HB-33: the game mode's side of the combat blocks - see UmHudCombatBlocks.h.
#include "UmHudCombatBlocks.h"

#include "UmCardWidget.h"
#include "UmGameHud.h"

namespace {
bool UmCombatStaged(const FUmCombatInput& In) {
  return In.Stage && In.Stage->IsActive() && In.Stage->ShowsCards(In.NowMs);
}

/** The face of a public card under the combat's stable instance id (the widget keys the flip by it). */
void UmCombatFace(FUmCombatEdgeModel& M, const FS09CardView& Src) {
  const FString Id = M.Card.InstanceId;
  M.Card = Src;
  M.Card.InstanceId = Id;
  M.Card.bHidden = false;
  M.bFace = true;
}

bool UmCombatPublic(const FS09CardView& C) { return !C.bHidden && !C.Name.IsEmpty(); }
}  // namespace

TArray<FString> FUmCombatBlocks::Build(UUmGameHud& Game, const S08ArtLook::FS08SlateHudBlocks& Blocks,
                                       const TSharedPtr<FS09HudPressArbiter>& Arbiter, FCallbacks Callbacks) {
  TArray<FString> Lines;
  if (Blocks.IsSlate(FName(TEXT("combat")))) {
    Lines.Add(TEXT("HUD-COMBAT-UMG impl=slate reason=-S08SlateHud=combat"));
    return Lines;
  }
  for (int32 I = 0; I < 2; ++I) {
    const EUmEdgeSide Side = I == 0 ? EUmEdgeSide::Own : EUmEdgeSide::Opp;
    UUmHudCombatEdge* E = CreateWidget<UUmHudCombatEdge>(&Game, UUmHudCombatEdge::WidgetClass());
    if (!E || !Game.SetBlock(I == 0 ? EUmGameSlot::CombatEdgeL : EUmGameSlot::CombatEdgeR, E)) {
      Lines.Add(FString::Printf(TEXT("HUD-COMBAT-UMG edge=%s created=0 reason=create-failed"), I == 0 ? TEXT("own") : TEXT("opp")));
      continue;
    }
    E->SetSide(Side);
    E->SetInput(Arbiter, Callbacks.OnDefend, Callbacks.OnNoDefense, Callbacks.OnInspect);
    (I == 0 ? EdgeOwn : EdgeOpp) = E;
    FString Missing;
    Lines.Add(FString::Printf(TEXT("HUD-COMBAT-UMG edge=%s created=1 source=%s parts=%d missing=%s"), I == 0 ? TEXT("own") : TEXT("opp"),
                              *E->SourceName(), E->HasAllParts(&Missing) ? 1 : 0, Missing.IsEmpty() ? TEXT("-") : *Missing));
  }
  if (Blocks.IsSlate(FName(TEXT("combatcenter")))) {
    Lines.Add(TEXT("HUD-COMBAT-UMG center=slate reason=-S08SlateHud=combatcenter"));
    return Lines;
  }
  UUmHudCombatCenter* C = CreateWidget<UUmHudCombatCenter>(&Game, UUmHudCombatCenter::WidgetClass());
  if (!C || !Game.SetBlock(EUmGameSlot::CombatCenter, C)) {
    Lines.Add(TEXT("HUD-COMBAT-UMG center=umg created=0 reason=create-failed"));
    return Lines;
  }
  Center = C;
  FString Missing;
  Lines.Add(FString::Printf(TEXT("HUD-COMBAT-UMG center=umg created=1 source=%s parts=%d missing=%s"), *C->SourceName(),
                            C->HasAllParts(&Missing) ? 1 : 0, Missing.IsEmpty() ? TEXT("-") : *Missing));
  return Lines;
}

TArray<FUmCenterLine> FUmCombatBlocks::CenterLines(const FS09CombatStage& Stage, int64 NowMs, bool bRu, int32& OutCurrent) {
  TArray<FUmCenterLine> Out;
  OutCurrent = -1;
  const FS09CombatStageInput& SI = Stage.GetInput();
  const FS09CombatReveal& R = SI.Reveal;
  // the title in the UI language when the data has it (Card.nameRu), else as the data has it
  auto TitleOf = [&R, bRu](const FString& Name) {
    TArray<const FS09CardView*> Cards = {&R.Attack, &R.Defense};
    for (const FS09CardView& B : R.Boosts) Cards.Add(&B);
    for (const FS09CardView* C : Cards) {
      if (bRu && C->Name == Name && !C->NameRu.IsEmpty()) return C->NameRu;
    }
    return Name;
  };
  const int32 Shown = FMath::Clamp(Stage.EffectLinesShown(NowMs), 0, SI.Effects.Num());
  const int32 Lit = Stage.HighlightedEffectLine(NowMs);
  // ВР-VS3-52: the attack card's effects were cancelled - its line right after the first defender line (the canceller),
  // appearing with it; its X stamps in (200 ms) while the canceller is lit (HB-29: Уловка lit + Swift Strike X); with no
  // defender line - after the last line
  const bool bCancel = SI.bAttackCardCancelled && R.bAttackKnown && (R.Attack.EffectCount > 0 || !R.Attack.Text.IsEmpty());
  int32 CancelAfter = INDEX_NONE;
  if (bCancel) {
    for (int32 K = 0; K < SI.Effects.Num(); ++K) {
      if (!SI.Effects[K].bAttackerSide) {
        CancelAfter = K;
        break;
      }
    }
  }
  auto Cancelled = [&](bool bStamp) {
    FUmCenterLine L;
    L.Title = TitleOf(R.Attack.Name);
    L.Text = !R.Attack.Text.IsEmpty() ? R.Attack.Text : R.Attack.EffectText;
    L.bCancelled = true;
    L.bStamp = bStamp;
    return L;
  };
  for (int32 K = 0; K < Shown; ++K) {
    const FS09CombatEffectLine& E = SI.Effects[K];
    FUmCenterLine L;
    L.Title = TitleOf(E.CardName);
    L.Text = E.bPrintedText ? E.Text : FString();  // never the parser's kind / value prose
    if (K == Lit) OutCurrent = Out.Num();
    Out.Add(MoveTemp(L));
    if (K == CancelAfter) Out.Add(Cancelled(true));
  }
  if (bCancel && CancelAfter == INDEX_NONE && Shown == SI.Effects.Num()) Out.Add(Cancelled(true));
  return Out;
}

void FUmCombatBlocks::Gather(const FUmCombatInput& In, const FString& InKey, FUmCombatEdgeModel& OutOwn,
                             FUmCombatEdgeModel& OutOpp, FUmCombatCenterModel& OutCenter, bool bDeclaring) {
  OutOwn = FUmCombatEdgeModel();
  OutOpp = FUmCombatEdgeModel();
  OutCenter = FUmCombatCenterModel();
  if (!In.bLive || InKey.IsEmpty()) return;
  const bool bStaged = UmCombatStaged(In);
  if (!bStaged && !In.bOpen) return;
  const bool bViewerAttacker = !In.ViewerId.IsEmpty() && In.Attacker.OwnerId == In.ViewerId;
  const bool bViewerDefender = !bViewerAttacker && !In.ViewerId.IsEmpty() && In.Target.OwnerId == In.ViewerId;
  // ВР-H04: the viewer's fighter on the left whatever its role (a spectator: the attacker on the left)
  FUmCombatEdgeModel& AttackM = bViewerDefender ? OutOpp : OutOwn;
  FUmCombatEdgeModel& DefenseM = bViewerDefender ? OutOwn : OutOpp;
  const int32 Seq = bStaged ? In.Stage->GetSeq() : In.AppliedSeq;
  auto Base = [&InKey, Seq](FUmCombatEdgeModel& M, EUmEdgeRole Role, const FUmCombatFighter& F, const TCHAR* Part) {
    M.bShow = true;
    M.Role = Role;
    M.CombatKey = InKey;
    M.Seq = Seq;
    M.FighterName = F.Name;
    M.TeamSlot = F.TeamSlot;
    M.HeroSlug = F.DeckSlug;
    M.Card.InstanceId = FString::Printf(TEXT("combat.%s.%s"), *InKey, Part);
    M.Card.bHidden = true;
    M.Boost = UmCardWidget::NoBoostChip;
  };
  Base(AttackM, EUmEdgeRole::Attack, In.Attacker, TEXT("attack"));
  Base(DefenseM, EUmEdgeRole::Defense, In.Target, TEXT("defense"));
  const float DefenseDelay = UmCardWidget::DefenseFlipDelayMs(In.SpeedMul);
  if (bStaged) {
    // the staging: the closing snapshot made both cards public (CUE-010)
    const FS09CombatReveal& R = In.Stage->GetInput().Reveal;
    AttackM.State = EUmEdgeState::Reveal;
    if (R.bAttackKnown && UmCombatPublic(R.Attack)) {
      UmCombatFace(AttackM, R.Attack);
      const int32 Boost = R.AttackValue >= 0 ? R.AttackValue - R.Attack.AttackValue : 0;
      if (Boost > 0) AttackM.Boost = Boost;
    }
    if (R.bNoDefense) {
      DefenseM.State = EUmEdgeState::NoDefense;
    } else {
      DefenseM.State = EUmEdgeState::Reveal;
      if (R.bDefenseKnown && UmCombatPublic(R.Defense)) {
        UmCombatFace(DefenseM, R.Defense);
        DefenseM.FlipDelayMs = DefenseDelay;
      }
    }
  } else {
    // the open combat: the resolve window may already carry both cards (the server reveals in COMBAT_RESOLVE)
    const bool bRevealed = In.bResolvePhase && In.Combat.bRevealed;
    AttackM.State = bRevealed ? EUmEdgeState::Reveal : EUmEdgeState::Back;
    // privacy: the attack face on the attacker's own HUD, on the other HUD only once revealed
    if ((bViewerAttacker || bRevealed) && In.Combat.bHasAttackerCard && UmCombatPublic(In.AttackCard)) {
      UmCombatFace(AttackM, In.AttackCard);
      if (In.Combat.bHasBoostValue && In.Combat.BoostValue > 0) AttackM.Boost = In.Combat.BoostValue;
    }
    if (!In.bResolvePhase) {
      // the defense window: the defender's own pick shows the back; the attacker sees the shield (S09DefenseSlotState)
      DefenseM.State = bViewerDefender && !In.DraftDefenseId.IsEmpty() ? EUmEdgeState::Chosen : EUmEdgeState::Shield;
      if (bViewerDefender) {
        DefenseM.bButtons = true;
        DefenseM.DefendWhy = In.BusyWhy.IsSet()       ? In.BusyWhy
                             : !In.bHasLegalDefense    ? FS09Reason::Make(TEXT("why.defense.none"))
                             : In.DraftDefenseId.IsEmpty() ? FS09Reason::Make(TEXT("why.defense.pick"))
                                                           : FS09Reason();
        DefenseM.NoDefenseWhy = In.BusyWhy;
        if (In.DeadlineSec > 0.0) {
          DefenseM.bTimer = true;
          DefenseM.DeadlineSec = In.DeadlineSec;
          DefenseM.WindowSec = FMath::Max(1.0f, In.WindowSec);
        }
      }
    } else if (bRevealed && In.Combat.bHasDefenderCard && UmCombatPublic(In.DefenseCard)) {
      DefenseM.State = EUmEdgeState::Reveal;
      UmCombatFace(DefenseM, In.DefenseCard);
      DefenseM.FlipDelayMs = DefenseDelay;
    } else {
      DefenseM.State = EUmEdgeState::Chosen;  // CUE-009: committed face down
    }
    if (In.bResolvePhase && In.bResolveButton && (bViewerAttacker || bViewerDefender)) {
      OutOwn.bResolve = true;  // VS-5 E4: «Завершить бой» on the viewer's own edge (any participant resolves)
      OutOwn.ResolveWhy = In.ResolveWhy;
    }
  }
  // CUE-008: the declare shows the attacker's card and its ribbon only (the slot and the window follow)
  if (bDeclaring && !bStaged && !In.bResolvePhase) {
    DefenseM = FUmCombatEdgeModel();
    return;
  }
  // ---- the centre ----
  if (!bStaged) {
    // 04 §2.7: the attacker waits for the defense in the defense window (after CUE-009 the slot says it)
    if (In.bOpen && !In.bResolvePhase && bViewerAttacker) {
      OutCenter.State = EUmCenterState::Wait;
      OutCenter.Seq = Seq;
    }
    return;
  }
  const FS09CombatStage& S = *In.Stage;
  const FS09CombatStageInput& SI = S.GetInput();
  OutCenter.Seq = Seq;
  OutCenter.Lines = CenterLines(S, In.NowMs, In.bRu, OutCenter.Current);
  OutCenter.bScore = SI.Reveal.AttackValue >= 0 && SI.Reveal.DefenseValue >= 0;
  OutCenter.AttackValue = SI.Reveal.AttackValue;
  OutCenter.DefenseValue = SI.Reveal.DefenseValue;
  OutCenter.bAttackerWins = S.AttackerWins();
  OutCenter.AttackerName = In.Attacker.Name.IsEmpty() ? SI.AttackerLabel : In.Attacker.Name;
  if (S.ShowsOutcome(In.NowMs)) {
    OutCenter.State = In.NowMs >= S.GetContactMs() ? EUmCenterState::Hit : EUmCenterState::Slam;
  } else if (S.EffectLinesShown(In.NowMs) > 0 || OutCenter.Lines.Num() > 0) {
    OutCenter.State = EUmCenterState::Effects;
  } else {
    OutCenter.State = EUmCenterState::Read;
  }
}

FString FUmCombatBlocks::KeyFor(const FUmCombatInput& In) {
  if (!In.bLive) return FString();
  if (UmCombatStaged(In)) {
    const FS09CombatStageInput& SI = In.Stage->GetInput();
    const FString Pair = SI.AttackerId + TEXT("|") + SI.TargetId;
    const int32 Seq = In.Stage->GetSeq();
    if (bKeyStaged && KeyStageSeq == Seq) return Key;  // the same staging
    if (!bKeyStaged && !Key.IsEmpty() && KeyPair == Pair) {
      // the open combat went on into its staging: the same cards (the flip of a face that was a back)
      bKeyStaged = true;
      KeyStageSeq = Seq;
      return Key;
    }
    Key = FString::Printf(TEXT("s%d"), Seq);  // a staging without its open combat on this client (a reconnect)
    KeyPair = Pair;
    bKeyStaged = true;
    KeyStageSeq = Seq;
    return Key;
  }
  if (In.bOpen) {
    const FString Pair = In.Combat.AttackerId + TEXT("|") + In.Combat.TargetFighterId;
    if (!bKeyStaged && !Key.IsEmpty() && KeyPair == Pair) return Key;
    Key = FString::Printf(TEXT("c%d"), In.AppliedSeq);  // a new combat (CUE-008)
    KeyPair = Pair;
    bKeyStaged = false;
    KeyStageSeq = -1;
    KeyOpenedMs = In.NowMs;
    return Key;
  }
  return FString();
}

TArray<FString> FUmCombatBlocks::Refresh(const FUmCombatInput& InRaw) {
  TArray<FString> Trace;
  if (!InRaw.Layout) return Trace;
  // VS-5 E4 (VS-4 «Открыто» п. 2): a new combat opens while the last one is still staged - the open combat (its defense
  // window and timer) takes the edges at once; the staging keeps running for the board, only the HUD lets it go (the
  // Slate defense window drew over it before)
  FUmCombatInput Yield;
  const bool bYield = InRaw.bOpen && UmCombatStaged(InRaw);
  if (bYield) {
    Yield = InRaw;
    Yield.Stage = nullptr;
  }
  const FUmCombatInput& In = bYield ? Yield : InRaw;
  if (bYield != bStageYield) {
    bStageYield = bYield;
    if (bYield) Trace.Add(FString::Printf(TEXT("HUD-COMBAT stage-yield staged=%d open=%d"), InRaw.Stage->GetSeq(), InRaw.AppliedSeq));
  }
  const FUmHudLayout& L = *In.Layout;
  const bool bStaged = In.bLive && UmCombatStaged(In);
  const FString NewKey = KeyFor(In);
  const float DeclareMs = In.DeclareMs >= 0.0f ? In.DeclareMs : FS09CombatTiming::DeclareMs * FMath::Max(0.0f, In.SpeedMul);
  const bool bDeclaring = !bStaged && In.bOpen && !In.bResolvePhase && !bKeyStaged && In.NowMs < KeyOpenedMs + static_cast<int64>(DeclareMs);
  FUmCombatEdgeModel Own, Opp;
  FUmCombatCenterModel Ctr;
  Gather(In, NewKey, Own, Opp, Ctr, bDeclaring);
  const bool bShown = Own.bShow || Opp.bShow;
  // HB-32: the staging ended - the cards leave (fade 150 + flight 200); an open combat gone without a staging (a cut,
  // a reconnect, the result screen) disappears at once
  if (!bShown && bWasShown) {
    if (bWasStaged) {
      for (UUmHudCombatEdge* E : {EdgeOwn.Get(), EdgeOpp.Get()}) {
        if (E) E->StartLeave();
      }
      Trace.Add(FString::Printf(TEXT("HUD-COMBAT leave seq=%d key=%s"), StagedSeq, *Key));
    }
    Key.Reset();
    KeyPair.Reset();
    bKeyStaged = false;
    KeyStageSeq = -1;
  }
  // the frames (the layout's rects; a change of class / scale / FIELD moves them)
  const FVector2D CardL = UmHudCombatEdge::CardSize(L.bClassS);
  for (int32 I = 0; I < 2; ++I) {
    UUmHudCombatEdge* E = I == 0 ? EdgeOwn.Get() : EdgeOpp.Get();
    if (!E) continue;
    const FBox2D Block = L.Rect(I == 0 ? EUmHudBlock::CombatL : EUmHudBlock::CombatR);
    FUmCombatEdgeFrame F;
    F.bClassS = L.bClassS;
    F.PxPerSu = L.PxPerSu;
    F.OriginSu = UmGameHudSlots::SlotRect(L, I == 0 ? EUmGameSlot::CombatEdgeL : EUmGameSlot::CombatEdgeR).Min;
    if (Block.bIsValid) F.CardSu = FBox2D(Block.Min, Block.Min + CardL);
    const FBox2D Defend = L.Rect(EUmHudBlock::Defend);
    if (I == 0 && Defend.bIsValid) {
      const float H = L.bClassS ? 40.0f : 48.0f;
      F.DefendSu = FBox2D(Defend.Min, FVector2D(Defend.Max.X, Defend.Min.Y + H));
      F.NoDefenseSu = FBox2D(FVector2D(Defend.Min.X, Defend.Max.Y - H), Defend.Max);
    }
    F.LeaveToSu = I == 0 ? L.DiscardChipCentreSu() : FVector2D(L.Rect(EUmHudBlock::PanelOpp).GetCenter());
    F.SpeedMul = FMath::Max(0.0f, In.SpeedMul);
    E->SetFrame(F);
    E->ApplyModel(I == 0 ? Own : Opp);
    E->Step();
    Trace.Append(E->TakeTrace());
  }
  if (UUmHudCombatCenter* C = Center.Get()) {
    FUmCombatCenterFrame F;
    F.bClassS = L.bClassS;
    F.PxPerSu = L.PxPerSu;
    F.CanvasSu = L.CanvasSu;
    F.OriginSu = UmGameHudSlots::SlotRect(L, EUmGameSlot::CombatCenter).Min;
    F.StatusBottomSu = Ctr.State == EUmCenterState::Wait ? In.StatusBottomSu : -1.0f;
    F.SpeedMul = FMath::Max(0.0f, In.SpeedMul);
    C->SetFrame(F);
    C->ApplyModel(Ctr);
    const FString Line = FString::Printf(TEXT("HUD-COMBAT center=%s seq=%d lines=%d current=%d"),
                                         Ctr.State == EUmCenterState::Hidden ? TEXT("hidden") : UmHudCombatCenter::StateName(Ctr.State),
                                         Ctr.Seq, Ctr.Lines.Num(), Ctr.Current);
    if (Line != LastCenterLine) {
      LastCenterLine = Line;
      Trace.Add(Line);
    }
  }
  bWasShown = bShown;
  bWasStaged = bStaged && bShown;
  if (bStaged) StagedSeq = In.Stage->GetSeq();
  // the defense window is the UMG edge's from the CUE-008 frame on (the declare hold included: no Slate flicker)
  bDefenseWindowShown = EdgesOnUmg() && In.bLive && In.bOpen && !In.bResolvePhase && !bStaged && !In.ViewerId.IsEmpty() &&
                        In.Target.OwnerId == In.ViewerId;
  return Trace;
}

void FUmCombatBlocks::CollectShotLines(TArray<FString>& Out) const {
  if (const UUmHudCombatEdge* E = EdgeOwn.Get()) E->CollectShotLines(Out);
  if (const UUmHudCombatEdge* E = EdgeOpp.Get()) E->CollectShotLines(Out);
  if (const UUmHudCombatCenter* C = Center.Get()) C->CollectShotLines(Out);
}

// VS-2 HB-18...HB-21: the panels runtime - see UmHudPanels.h.
#include "UmHudPanels.h"

#include "../S08HeroesV2.h"
#include "../S08TurnPortraitWidget.h"
#include "UmGameHud.h"
#include "UmPortrait.h"
#include "Blueprint/UserWidget.h"
#include "Components/Border.h"

namespace UmHudPanel {
int32 SidekickNumber(const FString& Label) {
  // Z-1 (ВР-07): one number rule for the HUD badge, the base digit, the tag and the audio key - a label that ends in a
  // number after a name carries it, and the number is S08HeroesV2::HarpyNumber's (the last digit, 1..3); a label
  // without one (Merlin) or of digits alone has no badge (0)
  const FString Trimmed = Label.TrimStartAndEnd();
  int32 Digits = 0;
  while (Digits < Trimmed.Len() && FChar::IsDigit(Trimmed[Trimmed.Len() - 1 - Digits])) ++Digits;
  if (Digits == 0 || Digits == Trimmed.Len()) return 0;
  FS08BoardFighter Fighter;
  Fighter.Label = Trimmed;
  return S08HeroesV2::HarpyNumber(Fighter);
}

FName SidekickKey(const FString& HeroSlug, const FString& Label) {
  FString Base = Label.TrimStartAndEnd();
  while (Base.Len() > 0 && FChar::IsDigit(Base[Base.Len() - 1])) Base.LeftChopInline(1);
  const FString Slug = UmPortrait::SlugOf(Base.TrimStartAndEnd());
  if (HeroSlug.IsEmpty() || Slug.IsEmpty()) return NAME_None;
  return FName(*FString::Printf(TEXT("%s/%s"), *HeroSlug, *Slug));
}

FUmPlayerPanelModel Gather(EUmPanelSide Side, const FString& PlayerId, const FString& HeroName,
                           const TArray<FS08BoardFighter>& Fighters, bool bSideTurn, bool bBotActing, bool bGameOver,
                           TFunctionRef<bool(const FString&)> IsFallen, FSideMemory& Memory) {
  FUmPlayerPanelModel M;
  const FS08BoardFighter* Hero = nullptr;
  for (const FS08BoardFighter& F : Fighters) {
    if (F.OwnerId == PlayerId && F.bIsHero) {
      Hero = &F;
      break;
    }
  }
  if (Hero && Hero->Id != Memory.HeroId) {
    // a new hero id = a new game (or the first frame): the sidekicks seen start again
    Memory = FSideMemory();
    Memory.HeroId = Hero->Id;
  }
  if (Hero) Memory.HeroMaxHp = FMath::Max(Memory.HeroMaxHp, Hero->MaxHealth);
  const FString FighterName = Hero ? (Hero->Label.IsEmpty() ? Hero->Name : Hero->Label) : FString();
  M.HeroName = !HeroName.IsEmpty() ? HeroName : !FighterName.IsEmpty() ? FighterName : Memory.HeroName;
  Memory.HeroName = M.HeroName;
  M.bHasHp = Hero != nullptr || !Memory.HeroId.IsEmpty();
  M.Hp = Hero ? Hero->Health : 0;
  M.MaxHp = Hero ? Hero->MaxHealth : Memory.HeroMaxHp;
  // the sidekicks: every fighter of the player that is not the hero; a fallen one keeps its plate (04 §2.2)
  TSet<FString> Seen;
  for (const FS08BoardFighter& F : Fighters) {
    if (F.OwnerId != PlayerId || F.bIsHero) continue;
    Seen.Add(F.Id);
    FUmSidekickView* S = Memory.Sidekicks.Find(F.Id);
    if (!S) {
      S = &Memory.Sidekicks.Add(F.Id);
      Memory.Order.Add(F.Id);
    }
    S->Id = F.Id;
    S->Name = F.Label.IsEmpty() ? F.Name : F.Label;
    S->Number = SidekickNumber(S->Name);
    S->Key = SidekickKey(F.HeroSlug, S->Name);
    S->Hp = F.Health;
    S->MaxHp = FMath::Max(S->MaxHp, F.MaxHealth);
    S->bFallen = IsFallen(F.Id);
  }
  for (const FString& Id : Memory.Order) {
    FUmSidekickView& S = Memory.Sidekicks[Id];
    if (!Seen.Contains(Id)) {
      // left the projection: it fell (the death stage is over)
      S.bFallen = true;
      S.Hp = 0;
    }
    M.Sidekicks.Add(S);
  }
  // the harpies 1..3 in their order (ВР-72), a named sidekick first
  M.Sidekicks.StableSort([](const FUmSidekickView& A, const FUmSidekickView& B) { return A.Number < B.Number; });
  // the state of 04 §7.1
  if (!Memory.HeroId.IsEmpty() && IsFallen(Memory.HeroId)) {
    M.State = EUmPanelState::Fallen;
  } else if (bSideTurn && !bGameOver) {
    M.State = Side == EUmPanelSide::Own ? EUmPanelState::Own : (bBotActing ? EUmPanelState::Ai : EUmPanelState::Opp);
  } else {
    M.State = EUmPanelState::Wait;
  }
  return M;
}
}  // namespace UmHudPanel

TArray<FString> FUmPanels::Build(UUmGameHud& Game, const S08ArtLook::FS08SlateHudBlocks& Blocks, const FS08TurnHudLook& Look,
                                 const FLinearColor& OwnTeam, const FLinearColor& OppTeam,
                                 const TSharedPtr<FS09HudPressArbiter>& Arbiter,
                                 TFunction<void(const FS09HudPressOutcome&, const TCHAR*)> OnPress,
                                 TFunction<void()> OnInspectHidden) {
  TArray<FString> Fields;
  auto Wire = [&Arbiter, &OnPress](const TCHAR* Which) {
    TFunction<void(const FS09HudPressOutcome&, const TCHAR*)> Press = OnPress;
    return FS09OnHudPressOutcome::CreateLambda([Press, Which](const FS09HudPressOutcome& O) {
      if (Press) Press(O, Which);
    });
  };
  if (!Blocks.IsSlate(FName(TEXT("panels")))) {
    Loc = CreateWidget<UUmHudPlayerPanel>(&Game, UUmHudPlayerPanel::WidgetClass(EUmPanelSide::Own));
    Opp = CreateWidget<UUmHudPlayerPanel>(&Game, UUmHudPlayerPanel::WidgetClass(EUmPanelSide::Opp));
    const bool bOk = Loc.IsValid() && Opp.IsValid() && Loc->Portrait && Opp->Portrait &&
                     Game.SetBlock(EUmGameSlot::PanelLoc, Loc.Get()) && Game.SetBlock(EUmGameSlot::PanelOpp, Opp.Get());
    if (bOk) {
      Loc->Setup(EUmPanelSide::Own, Look, OwnTeam);
      Opp->Setup(EUmPanelSide::Opp, Look, OppTeam);
      Loc->SetPress(FName(TEXT("hud.panel.loc")), Arbiter, Wire(TEXT("own")));
      Opp->SetPress(FName(TEXT("hud.panel.opp")), Arbiter, Wire(TEXT("opp")));
      for (UUmHudPlayerPanel* P : {Loc.Get(), Opp.Get()}) P->SetVisibility(ESlateVisibility::Collapsed);  // Tick shows them
      Fields.Add(FString::Printf(TEXT("loc=umg locSource=%s opp=umg oppSource=%s portrait=%s"), *Loc->SourceName(),
                                 *Opp->SourceName(), Loc->Portrait->UsesCodeDefaultTree() ? TEXT("code-default")
                                                                                          : *Loc->Portrait->GetClass()->GetPathName()));
    } else {
      Loc = nullptr;
      Opp = nullptr;
      Fields.Add(TEXT("loc=failed opp=failed"));
    }
  } else {
    Fields.Add(TEXT("loc=slate opp=slate"));
  }
  if (!Blocks.IsSlate(FName(TEXT("opphand")))) {
    OppHand = CreateWidget<UUmHudOppHand>(&Game, UUmHudOppHand::WidgetClass());
    if (OppHand.IsValid() && Game.SetBlock(EUmGameSlot::OppHand, OppHand.Get())) {
      OppHand->SetPress(FName(TEXT("hud.opp.hand")), Arbiter, Wire(TEXT("opp")), MoveTemp(OnInspectHidden));
      OppHand->SetVisibility(ESlateVisibility::Collapsed);
      Fields.Add(FString::Printf(TEXT("opphand=umg opphandSource=%s"), *OppHand->SourceName()));
    } else {
      OppHand = nullptr;
      Fields.Add(TEXT("opphand=failed"));
    }
  } else {
    Fields.Add(TEXT("opphand=slate(none)"));  // before HB-21 the hand was the debug line only (-S09Markers)
  }
  return {TEXT("HUD-PANELS ") + FString::Join(Fields, TEXT(" "))};
}

void FUmPanels::SetFrame(bool bInClassS, float InPxPerSu, float InOppHandWidthSu) {
  bClassS = bInClassS;
  PxPerSu = InPxPerSu > 0.0f ? InPxPerSu : 1.0f;
  OppHandWidthSu = InOppHandWidthSu > 0.0f ? InOppHandWidthSu : 300.0f;
}

void FUmPanels::Tick(const FUmPanelsTick& T) {
  const bool bShow = T.bShow && T.Fighters;
  if (!bShownKnown || bShow != bShown) {
    bShownKnown = true;
    bShown = bShow;
    // the panels take the mouse (a click opens the deck panel), the slot around them does not
    const ESlateVisibility Vis = bShown ? ESlateVisibility::Visible : ESlateVisibility::Collapsed;
    if (UUmHudPlayerPanel* L = Loc.Get()) L->SetVisibility(Vis);
    if (UUmHudPlayerPanel* O = Opp.Get()) O->SetVisibility(Vis);
    if (UUmHudOppHand* H = OppHand.Get()) H->SetVisibility(Vis);
  }
  if (!bShown) return;
  auto Fallen = [&T](const FString& Id) { return T.IsCrossed ? T.IsCrossed(Id) : false; };
  if (UUmHudPlayerPanel* L = Loc.Get()) {
    if (T.Own) {
      FUmPlayerPanelModel M = UmHudPanel::Gather(EUmPanelSide::Own, T.Own->PlayerId, T.OwnHeroName, *T.Fighters,
                                                 T.bViewerTurn, false, T.bGameOver, Fallen, OwnMemory);
      M.bClassS = bClassS;
      M.PxPerSu = PxPerSu;
      L->ApplyModel(M);
    }
  }
  if (UUmHudPlayerPanel* O = Opp.Get()) {
    if (T.Opp) {
      FUmPlayerPanelModel M = UmHudPanel::Gather(EUmPanelSide::Opp, T.Opp->PlayerId, T.OppHeroName, *T.Fighters,
                                                 !T.bViewerTurn, T.bBotActing, T.bGameOver, Fallen, OppMemory);
      M.bClassS = bClassS;
      M.PxPerSu = PxPerSu;
      O->ApplyModel(M);
    }
  }
  if (UUmHudOppHand* H = OppHand.Get()) {
    if (T.Opp) {
      FUmOppHandModel M;
      M.HandCount = T.Opp->HandCount;
      M.DeckCount = T.Opp->DeckCount;
      M.DiscardCount = T.Opp->Discard.Num();
      M.bDeckStale = T.Opp->bDeckCountStale;
      for (const FS08BoardFighter& F : *T.Fighters) {
        if (F.OwnerId == T.Opp->PlayerId && !F.HeroSlug.IsEmpty()) {
          M.HeroSlug = F.HeroSlug;
          break;
        }
      }
      M.WidthSu = OppHandWidthSu;
      M.PxPerSu = PxPerSu;
      H->ApplyModel(M);
    }
  }
}

void FUmPanels::CollectShotLines(TArray<FString>& Out, TFunctionRef<FS08ScreenRect(UWidget*)> RectOf) const {
  for (const UUmHudPlayerPanel* P : {Loc.Get(), Opp.Get()}) {
    if (P && UmGameHudSlots::ShownByProperty(P)) {
      P->CollectShotLines(Out, RectOf(P->Panel.Get()));
      P->CollectPortraitLines(Out);  // VS-2 CP-10 / CP-12: the sidekick mini portraits (ВР-CP10)
    }
  }
  if (const UUmHudOppHand* H = OppHand.Get()) {
    if (UmGameHudSlots::ShownByProperty(H)) H->CollectShotLines(Out, RectOf(H->Panel.Get()));
  }
}
